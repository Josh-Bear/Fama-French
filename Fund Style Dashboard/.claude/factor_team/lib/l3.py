"""l3 — เครื่องมือ L3 (VIF-cleaned) ตาม S006 · ไฟล์ใหม่ ไม่แก้ฟังก์ชันของ lib เดิม"""
import copy
import warnings

import numpy as np
import pandas as pd

import l2
import regress as rg
import tests_stat as ts

SEED = 20261015

# ───────────── ค่าคงที่ (ข้อ 3) ─────────────
C11 = ["MSCI_BRAZIL", "MSCI_CHINA_A_SHARES", "MSCI_CHINA_H_SHARES", "MSCI_EUROPE", "MSCI_INDIA", "MSCI_JAPAN",
       "MSCI_KOREA", "MSCI_ASEAN", "MSCI_TAIWAN", "MSCI_USA", "MSCI_VIETNAM"]
SECT = ["CD", "CS", "EN", "FN", "HC", "IN", "IT", "MT", "TC", "UT"]
S10 = ["MSCI_ACWI_" + s for s in SECT]
P4 = ["MSCI_ACWI_HC", "MSCI_ACWI_UT", "MSCI_EUROPE", "MSCI_INDIA", "MSCI_JAPAN", "MSCI_VIETNAM"]
P4_STRICT = [c for c in P4 if c != "MSCI_VIETNAM"]
EXT14 = ["QQQ", "SOXX", "ARKK", "ICLN", "IBB", "KWEB", "THD", "EIDO", "EPHE", "EWM", "EWS", "REET", "IGF", "DBC"]
# ลำดับชั้น (ข้อ 4.3): (แม่, ลูก) · "MKT" = ACWI − rf (C0)
HIER = [
    (("MKT",), ["MSCI_USA", "MSCI_EUROPE", "MSCI_JAPAN", "MSCI_ASIA_EX_JAPAN", "MSCI_BRAZIL"]),
    (("MKT",), list(S10)),
    (("MKT",), ["REET", "IGF", "DBC"]),
    (("MKT", "MSCI_ASIA_EX_JAPAN"), ["MSCI_CHINA_ALL_SHARES", "MSCI_INDIA", "MSCI_KOREA", "MSCI_TAIWAN", "MSCI_ASEAN", "MSCI_VIETNAM"]),
    (("MKT", "MSCI_ASIA_EX_JAPAN", "MSCI_CHINA_ALL_SHARES"), ["MSCI_CHINA_A_SHARES", "MSCI_CHINA_H_SHARES", "KWEB"]),
    (("MKT", "MSCI_ASIA_EX_JAPAN", "MSCI_ASEAN"), ["THD", "EIDO", "EPHE", "EWM", "EWS"]),
    (("MKT", "MSCI_ACWI_IT"), ["QQQ", "SOXX", "ARKK"]),
    (("MKT", "MSCI_ACWI_HC"), ["IBB"]),
    (("MKT", "MSCI_ACWI_UT"), ["ICLN"]),
]
HIER_CHILDREN = [c for _, ch in HIER for c in ch]


def ext_excess(Fext, F):
    """<ETF>_THB − RF_BOT ของ EXT14 ตาม index ของ F (ตัดแถว ≥ 2026-01-01) → DataFrame 14 คอลัมน์"""
    idx = F.index[F.index < pd.Timestamp("2026-01-01")]
    out = pd.DataFrame(index=idx)
    for c in EXT14:
        out[c] = Fext[c + "_THB"].reindex(idx) - F["RF_BOT"].reindex(idx)
    return out


# ───────────── residualize ─────────────
def residualize(I, P, mask_tr):
    """ข้อ 3.4: OLS I = a + b'P (train) → e = I − b̂'P ทุก t (lag 0 · เก็บค่าคงที่ไว้ ไม่หัก â) → (E, coef)"""
    if isinstance(I, pd.Series):
        I = I.to_frame()
    Pv = P.to_numpy(float)
    mask_tr = np.asarray(mask_tr, bool)
    E = pd.DataFrame(np.nan, index=I.index, columns=I.columns)
    rows = []
    for c in I.columns:
        y = I[c].to_numpy(float)
        ok = mask_tr & np.isfinite(y) & np.isfinite(Pv).all(1)
        X = np.column_stack([np.ones(int(ok.sum())), Pv[ok]])
        b = np.linalg.lstsq(X, y[ok], rcond=None)[0]
        res = y[ok] - X @ b
        sst = ((y[ok] - y[ok].mean()) ** 2).sum()
        E[c] = y - Pv @ b[1:]
        row = dict(index=c, a=float(b[0]), r2_train=float(1 - res @ res / sst), n=int(ok.sum()), parents=";".join(P.columns))
        for i, p in enumerate(P.columns):
            row["b_" + p] = float(b[i + 1])
        rows.append(row)
    return E, pd.DataFrame(rows)


def hier_residuals(I_all, mask_tr, hier=HIER):
    """e ของลูกทั้งหมดตาม HIER (แม่แบบ raw) → (E 37 คอลัมน์ ตามลำดับ HIER, coef log)"""
    parts, logs = [], []
    for parents, children in hier:
        E, co = residualize(I_all[list(children)], I_all[list(parents)], mask_tr)
        parts.append(E)
        logs.append(co)
    return pd.concat(parts, axis=1), pd.concat(logs, ignore_index=True)


# ───────────── VIF ─────────────
def _fin_rows(X, mask_tr):
    Xv = X.to_numpy(float)
    return np.asarray(mask_tr, bool) & np.isfinite(Xv).all(1)


def _vif_safe(Xv):
    with np.errstate(divide="ignore", invalid="ignore"):
        v = ts.vif(Xv)
    return np.where(np.isfinite(v) & (v > 0), v, np.inf)


def cond_number(X, mask_tr):
    """κ = √(λmax/λmin) ของ corr matrix (train)"""
    Xv = X.to_numpy(float)[_fin_rows(X, mask_tr)]
    w = np.linalg.eigvalsh(np.corrcoef(Xv, rowvar=False))
    return float(np.sqrt(w.max() / w.min())) if w.min() > 0 else np.inf


def vif_table(X, mask_tr):
    """→ (DataFrame(col, vif), κ) · ใช้ tests_stat.vif บนแถว train ที่ครบ"""
    Xv = X.to_numpy(float)[_fin_rows(X, mask_tr)]
    return pd.DataFrame(dict(col=list(X.columns), vif=_vif_safe(Xv))), cond_number(X, mask_tr)


def vif_backward(X, mask_tr, protect, order, thr=5.0, continue_all=False):
    """ตัดดัชนี VIF สูงสุดทีละตัว (protect ห้ามตัด · เสมอ → ตามลำดับ `order`) · เกณฑ์หยุดหลัก (ค่าชั่วคราว 59):
    หยุดเมื่อคอลัมน์ที่ไม่ใช่ protect ทุกตัว VIF < thr (protect VIF ≥ thr ได้ → note) ·
    continue_all=True: เดิน log ต่อ (phase=descriptive_all) จนทุกคอลัมน์รวม protect < thr หรือไม่มีดัชนีเหลือ ·
    คืน (kept ณ ท้ายเฟสหลัก, log DataFrame)"""
    protect = list(protect)
    opos = {c: i for i, c in enumerate(order)}
    ok = _fin_rows(X, mask_tr)
    Xv = X.to_numpy(float)[ok]
    cols = list(X.columns)
    kept = list(cols)
    log = []
    kept_main = None
    step = 0
    phase = "main"
    while True:
        sub = Xv[:, [cols.index(c) for c in kept]]
        v = pd.Series(_vif_safe(sub), index=kept)
        cand = [c for c in kept if c not in protect]
        vmax_idx = float(v[cand].max()) if cand else np.nan
        vmax_all = float(v.max())
        if phase == "main":
            stop = (not cand) or vmax_idx < thr
            if stop:
                note = ""
                prot = [c for c in kept if c in protect and v[c] >= thr]
                if prot:
                    note = "STOP: ดัชนีทุกตัว VIF < thr แต่ protect VIF ≥ thr: " + ",".join(f"{c}={v[c]:.2f}" for c in prot)
                log.append(dict(step=step, dropped="", vif_max_idx=vmax_idx, vif_max_all=vmax_all, phase="main", n_remaining=len(kept), note=note))
                kept_main = list(kept)
                if not continue_all or not cand or vmax_all < thr:
                    break
                phase = "descriptive_all"
                continue
        else:
            if (not cand) or vmax_all < thr:
                log.append(dict(step=step, dropped="", vif_max_idx=vmax_idx, vif_max_all=vmax_all, phase=phase, n_remaining=len(kept),
                                note="STOP(ข): ทุกคอลัมน์ < thr" if vmax_all < thr else "STOP(ข): ไม่มีดัชนีให้ตัด"))
                break
        mx = float(v[cand].max())
        ties = [c for c in cand if (np.isinf(mx) and np.isinf(v[c])) or v[c] >= mx * (1 - 1e-9)]
        drop = min(ties, key=lambda c: opos.get(c, 10 ** 6))
        step += 1
        log.append(dict(step=step, dropped=drop, vif_max_idx=mx, vif_max_all=vmax_all, phase=phase, n_remaining=len(kept) - 1, note=""))
        kept.remove(drop)
    return kept_main, pd.DataFrame(log)


# ───────────── OLS เร็ว (ไม่ HAC) ─────────────
def _quick(y, X):
    """X รวมค่าคงที่แล้ว → (ssr, adj_r2, bic, n, p) ด้วยสูตรเดียวกับ regress.ols_hac"""
    n, p = X.shape
    XtX = X.T @ X
    try:
        A = np.linalg.inv(XtX)
    except np.linalg.LinAlgError:
        A = np.linalg.pinv(XtX)
    coef = A @ (X.T @ y)
    e = y - X @ coef
    ssr = float(e @ e)
    sst = float(((y - y.mean()) ** 2).sum())
    r2 = 1.0 - ssr / sst if sst > 0 else np.nan
    adj = 1.0 - (1.0 - r2) * (n - 1) / (n - p) if n > p else np.nan
    return ssr, adj, n * np.log(ssr / n) + p * np.log(n), n, p


def bic_rows(y, X):
    """BIC แบบ OLS (ไม่ HAC) · X ไม่รวมค่าคงที่ (ใส่ให้) · ต้องเท่ากับ fit_funds"""
    y = np.asarray(y, float)
    X = np.asarray(X, float)
    return _quick(y, np.column_stack([np.ones(len(y)), X]))[2]


def _delta_table(R, funds, mask_tr, Dcore, cands, min_rows=52):
    """ต่อกอง × candidate: ΔBIC และ Δadj R² ของ core → core + e_j (Dimson) บนแถว train เดียวกัน · cands: dict name→(T×2)"""
    Rv = R[list(funds)].to_numpy(float)
    mask_tr = np.asarray(mask_tr, bool)
    names = list(cands)
    dB = np.full((len(funds), len(names)), np.nan)
    dA = np.full((len(funds), len(names)), np.nan)
    fin_core = np.isfinite(Dcore).all(1)
    fin_c = {c: np.isfinite(cands[c]).all(1) for c in names}
    for i in range(len(funds)):
        y = Rv[:, i]
        ok0 = mask_tr & np.isfinite(y) & fin_core
        n0 = int(ok0.sum())
        if n0 < max(min_rows, Dcore.shape[1] + 8):
            continue
        X0 = np.column_stack([np.ones(n0), Dcore[ok0]])
        b0 = _quick(y[ok0], X0)
        for j, c in enumerate(names):
            ok = ok0 & fin_c[c]
            n = int(ok.sum())
            if n < max(min_rows, Dcore.shape[1] + 10):
                continue
            if n == n0:
                bb, XA = b0, X0
            else:
                XA = np.column_stack([np.ones(n), Dcore[ok]])
                bb = _quick(y[ok], XA)
            ba = _quick(y[ok], np.column_stack([XA, cands[c][ok]]))
            dB[i, j] = ba[2] - bb[2]
            dA[i, j] = ba[1] - bb[1]
    return dB, dA, names


def _cand_dict(pool, names=None):
    names = list(pool.columns) if names is None else list(names)
    return {c: rg.lag_stack(pool[[c]].to_numpy(float)) for c in names}


def forward_select(R, core, pool, mask_tr, funds, tau=0.0, kmax=8, L=4):
    """forward selection (train เท่านั้น): score_j = median_i ΔBIC_ij · เลือก argmin (เสมอ → ลำดับใน pool) ·
    เพิ่มเมื่อ score < tau และ |บล็อก| < kmax · คืน (selected, log) · log บันทึกอันดับที่ดีที่สุดของรอบที่หยุดด้วย"""
    selected, log = [], []
    cand_all = _cand_dict(pool)
    r = 0
    while True:
        r += 1
        rest = [c for c in pool.columns if c not in selected]
        if not rest:
            log.append(dict(round=r, candidate="", score=np.nan, second="", second_score=np.nan, tau=tau, action="stop_no_candidate", n_selected=len(selected)))
            break
        M = pd.concat([core, pool[selected]], axis=1) if selected else core
        Dcore = rg.lag_stack(M.to_numpy(float))
        dB, _, names = _delta_table(R, funds, mask_tr, Dcore, {c: cand_all[c] for c in rest})
        sc_ = np.nanmedian(dB, axis=0)
        order = np.argsort(np.where(np.isfinite(sc_), sc_, np.inf), kind="stable")
        j = int(order[0])
        sec = int(order[1]) if len(order) > 1 else None
        add = bool(np.isfinite(sc_[j]) and sc_[j] < tau and len(selected) < kmax)
        why = "added" if add else ("stop_cap" if (np.isfinite(sc_[j]) and sc_[j] < tau) else "stop_tau")
        log.append(dict(round=r, candidate=names[j], score=float(sc_[j]), second=names[sec] if sec is not None else "",
                        second_score=float(sc_[sec]) if sec is not None else np.nan, tau=tau, action=why, n_selected=len(selected) + int(add)))
        if not add:
            break
        selected.append(names[j])
    return selected, pd.DataFrame(log)


def placebo_forward(R, core, pool, mask_tr, funds, shifts=(26, 52), kmax=8):
    """รัน forward_select (tau = 0) กับ pool ที่เลื่อนวนภายใน train (core ไม่เลื่อน) → dict(shifts, tau, rule)
    กฎ: ไม่มี shift ใดเลือก → τ = 0 · เลือก ≥ 1 → τ = min(0, min_s τ_s)"""
    out, taus = {}, []
    for s in shifts:
        P = l2.circular_shift(pool, mask_tr, s) if s else pool
        sel, lg = forward_select(R, core, P, mask_tr, funds, tau=0.0, kmax=kmax)
        b1 = float(lg.score.iloc[0])
        out[int(s)] = dict(selected=sel, n_selected=len(sel), best_score_step1=b1)
        taus.append(b1)
    any_sel = any(v["n_selected"] > 0 for v in out.values())
    tau = min(0.0, min(taus)) if any_sel else 0.0
    return dict(shifts=out, tau=tau, any_selected=any_sel,
                rule="placebo เลือก ≥1 → τ = min(0, min τ_s) + ป้ายปรับเกณฑ์" if any_sel else "placebo เลือก 0 → τ = 0")


def prim_from_pool(R, core, pool, mask_tr, funds):
    """ต่อกอง: argmax_j Δadj R² (train · Dimson) ของ core → core + e_j · เสมอ → ลำดับ pool · เพิ่มเสมอ"""
    Dcore = rg.lag_stack(core.to_numpy(float))
    _, dA, names = _delta_table(R, funds, mask_tr, Dcore, _cand_dict(pool))
    rows = []
    for i, code in enumerate(funds):
        v = dA[i]
        if not np.isfinite(v).any():
            rows.append(dict(FundCode=code, index=None, d_adj_r2=np.nan))
            continue
        j = int(np.argmax(np.where(np.isfinite(v), v, -np.inf)))
        rows.append(dict(FundCode=code, index=names[j], d_adj_r2=float(v[j])))
    return pd.DataFrame(rows)


# ───────────── drop-one · Wald ─────────────
def drop_one(R, base, block, mask_tr, mask_te, funds, L=4, min_obs=52):
    """ต่อ j ∈ block: Δ = full(base+block) − fit(base+block\\j) แถวเดียวกัน → long (FundCode, index, d_r2_oos, d_bic, d_adj_r2)"""
    funds = list(funds)
    pf = l2.AugmentedFactors(base, extra=block)
    full = rg.fit_funds(R, pf, mask_tr, min_obs, L, funds)
    rf = rg.oos_r2_funds(R, pf, full, mask_te) if mask_te is not None else np.full(len(funds), np.nan)
    rows = []
    for j in block.columns:
        pj = l2.AugmentedFactors(base, extra=block.drop(columns=[j]))
        fj = rg.fit_funds(R, pj, mask_tr, min_obs, L, funds)
        rj = rg.oos_r2_funds(R, pj, fj, mask_te) if mask_te is not None else np.full(len(funds), np.nan)
        rows.append(pd.DataFrame(dict(FundCode=funds, index=j, d_r2_oos=rf - rj, d_bic=full.bic - fj.bic, d_adj_r2=full.adj_r2 - fj.adj_r2)))
    return pd.concat(rows, ignore_index=True)


def wald_B(R, base, E, mask_tr, funds, L=4, min_obs=52):
    """Wald (b0_j, b1_j) = 0 ต่อกอง × e_j ใน design f + E (Dimson · HAC) → long (FundCode, index, n, W, p, p_adj)"""
    prov = l2.AugmentedFactors(base, extra=E)
    K, kb = prov.K, base.shape[1]
    Rv = R[list(funds)].to_numpy(float)
    D = prov.design()
    fin = np.isfinite(D).all(1)
    mask_tr = np.asarray(mask_tr, bool)
    rows = []
    for i, code in enumerate(funds):
        y = Rv[:, i]
        ok = mask_tr & np.isfinite(y) & fin
        n = int(ok.sum())
        if n < max(min_obs, 2 * K + 3):
            continue
        X = np.column_stack([np.ones(n), D[ok]])
        r = rg.ols_hac(y[ok], X, L)
        for j, c in enumerate(E.columns):
            W, _, p = l2.wald_subset(r["coef"], r["V"], [1 + kb + j, 1 + K + kb + j])
            rows.append(dict(FundCode=code, index=c, n=n, W=W, p=p, p_adj=float(l2.wald_p_dfadj(W, 2, n, X.shape[1]))))
    return pd.DataFrame(rows)


# ───────────── แถวต่อกองที่ผสม (บางกอง = ฐาน) ─────────────
def perfund_from_primary(E, prim, funds, exclude=()):
    """dict กอง → Series e_p(i) เฉพาะกองที่ primary ∈ E.columns และไม่อยู่ใน exclude (กองอื่น = ฐาน)"""
    out = {}
    for c in funds:
        p = prim.get(c)
        if p is not None and p in E.columns and p not in exclude:
            out[c] = E[p]
    return out


def _pad_cols(a, Ka, Kb, coef=False):
    """ขยายอาร์เรย์ของฐาน (Kb) ให้เป็น Ka = Kb + 1 โดยเติม NaN ที่คอลัมน์ PRIM"""
    if not coef:
        return np.hstack([a, np.full(a.shape[:-1] + (Ka - Kb,), np.nan)])
    out = np.full(a.shape[:-1] + (1 + 2 * Ka,), np.nan)
    out[..., 0] = a[..., 0]
    out[..., 1:1 + Kb] = a[..., 1:1 + Kb]
    out[..., 1 + Ka:1 + Ka + Kb] = a[..., 1 + Kb:]
    return out


def merge_fits(fit_a, fit_b, use_a):
    """fit_a (K_a = K_b+1 · per-fund PRIM) + fit_b (ฐาน) → fit เดียวต่อกอง (use_a True = a)"""
    use_a = np.asarray(use_a, bool)
    Ka, Kb = fit_a.K, fit_b.K
    out = copy.copy(fit_a)
    for nm in ("alpha", "t_alpha_hac", "t_alpha_ols", "r2", "adj_r2", "bic", "n", "ssr", "ok"):
        out.__dict__[nm] = np.where(use_a, getattr(fit_a, nm), getattr(fit_b, nm))
    for nm in ("b0", "b1", "beta", "se_beta", "t_b1"):
        out.__dict__[nm] = np.where(use_a[:, None], getattr(fit_a, nm), _pad_cols(getattr(fit_b, nm), Ka, Kb))
    out.coef = np.where(use_a[:, None], fit_a.coef, _pad_cols(fit_b.coef, Ka, Kb, coef=True))
    out.resid = np.where(use_a[None, :], fit_a.resid, fit_b.resid)
    out.n = out.n.astype(int)
    out.ok = out.ok.astype(bool)
    return out


def fit_perfund(R, base, per_fund, mask_tr, mask_te, funds, min_obs=52, L=4):
    """แถวต่อกอง: กองใน per_fund = base + 1 ตัว (PRIM) · กองอื่น = base · คืน (fit, r2_oos, provider_a|None)"""
    funds = list(funds)
    use = np.array([c in per_fund for c in funds])
    fb = rg.fit_funds(R, base, mask_tr, min_obs, L, funds)
    rb = rg.oos_r2_funds(R, base, fb, mask_te) if mask_te is not None else np.full(len(funds), np.nan)
    if not use.any():
        return fb, rb, None
    pa = l2.AugmentedFactors(base, per_fund=per_fund)
    fa = rg.fit_funds(R, pa, mask_tr, min_obs, L, funds)
    ra = rg.oos_r2_funds(R, pa, fa, mask_te) if mask_te is not None else np.full(len(funds), np.nan)
    if use.all():
        return fa, ra, pa
    return merge_fits(fa, fb, use), np.where(use, ra, rb), pa


def rolling_perfund(R, base, per_fund, funds, base_mask, **kw):
    """rolling β ของแถวต่อกอง (กองนอก per_fund = ฐาน · คอลัมน์ PRIM = NaN) → (bw W×N×K, full N×K, starts)"""
    funds = list(funds)
    use = np.array([c in per_fund for c in funds])
    if use.all():
        return l2.rolling_betas(R, l2.AugmentedFactors(base, per_fund=per_fund), funds, base_mask, **kw)
    bwb, fb, st = l2.rolling_betas(R, rg.CommonFactors(base), funds, base_mask, **kw)
    if not use.any():
        return bwb, fb, st
    sub = [c for c, u in zip(funds, use) if u]
    bwa, fa, _ = l2.rolling_betas(R, l2.AugmentedFactors(base, per_fund=per_fund), sub, base_mask, **kw)
    Ka = fa.shape[1]
    bw = np.full((bwb.shape[0], len(funds), Ka), np.nan)
    bw[:, :, :Ka - 1] = bwb
    bw[:, use, :] = bwa
    full = np.full((len(funds), Ka), np.nan)
    full[:, :Ka - 1] = fb
    full[use, :] = fa
    return bw, full, st


# ───────────── elastic net stability selection (diagnostic) ─────────────
def enet_stability(R, f, Z, mask_tr, funds, l1_ratio=0.5, n_sub=100, block=4, frac=0.5, seed=SEED):
    """ข้อ 4.4: partial out [1, f_t, f_t−1] จาก y และ Z (lag 0, 1) ด้วยแถว train → standardize (sd train) →
    λ* = argmin BIC บน enet_path (100 ค่า · eps 1e-3 · df = จำนวนสัมประสิทธิ์ ≠ 0) → subsample 100 รอบ
    (บล็อก 4 สัปดาห์ติดกัน สุ่มครึ่งหนึ่งแบบไม่คืน) → π_ij = สัดส่วนรอบที่ lag 0 หรือ lag 1 ≠ 0 ·
    rng ใหม่ต่อการเรียก (กองเรียงตาม FundCode) → long (FundCode, index, pi, lambda_star, n_rows)"""
    from sklearn.exceptions import ConvergenceWarning
    from sklearn.linear_model import ElasticNet, enet_path
    Pn = Z.shape[1]
    Zl = rg.lag_stack(Z.to_numpy(float))
    Wm = np.column_stack([np.ones(len(Z)), rg.lag_stack(f.to_numpy(float))])
    fin = np.isfinite(Wm).all(1) & np.isfinite(Zl).all(1)
    mask_tr = np.asarray(mask_tr, bool)
    rng = np.random.default_rng(seed)
    rows = []
    for code in sorted(funds):
        y = R[code].to_numpy(float)
        ok = mask_tr & fin & np.isfinite(y)
        n = int(ok.sum())
        if n < 52:
            continue
        W, yy, Zz = Wm[ok], y[ok], Zl[ok]
        yt = yy - W @ np.linalg.lstsq(W, yy, rcond=None)[0]
        Zt = Zz - W @ np.linalg.lstsq(W, Zz, rcond=None)[0]
        sd = Zt.std(0)
        sd[sd == 0] = np.inf
        Zs = Zt / sd
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", ConvergenceWarning)
            warnings.simplefilter("ignore", FutureWarning)  # sklearn 1.9: n_alphas deprecated (ความหมายเท่าเดิม)
            alphas, coefs, _ = enet_path(Zs, yt, l1_ratio=l1_ratio, n_alphas=100, eps=1e-3)
            res = yt[:, None] - Zs @ coefs
            ssr = (res ** 2).sum(0)
            df = (coefs != 0).sum(0)
            bic = n * np.log(np.maximum(ssr, 1e-300) / n) + df * np.log(n)
            lam = float(alphas[int(np.argmin(bic))])
            nb = -(-n // block)
            cnt = np.zeros(Pn)
            for _ in range(n_sub):
                pick = rng.choice(nb, size=int(nb * frac), replace=False)
                rws = np.concatenate([np.arange(b * block, min((b + 1) * block, n)) for b in sorted(pick)])
                m = ElasticNet(alpha=lam, l1_ratio=l1_ratio, fit_intercept=False, max_iter=10000, tol=1e-6, selection="cyclic").fit(Zs[rws], yt[rws])
                cf = m.coef_
                cnt += ((cf[:Pn] != 0) | (cf[Pn:] != 0))
        for j, c in enumerate(Z.columns):
            rows.append(dict(FundCode=code, index=c, pi=cnt[j] / n_sub, lambda_star=lam, n_rows=n))
    return pd.DataFrame(rows)


# ───────────── Q3: เทียบ primary กับแอป ─────────────
def primary_match(ours, app):
    """ours: Series กอง→ชื่อดัชนี · app: DataFrame (index FundCode; country_primary, sector_primary) → ต่อกอง (เฉพาะกองที่อยู่ทั้งสองชุด)"""
    common = [c for c in ours.index if c in app.index and isinstance(ours[c], str)]
    d = pd.DataFrame(dict(FundCode=common, ours=[ours[c] for c in common],
                          app_country=[app.loc[c, "country_primary"] for c in common],
                          app_sector=[app.loc[c, "sector_primary"] for c in common]))
    d["match_country"] = d.ours == d.app_country
    d["match_sector"] = d.ours == d.app_sector
    d["match_either"] = d.match_country | d.match_sector
    d["category"] = np.where(d.match_country, "country", np.where(d.match_sector, "sector", "ไม่ตรง"))
    return d


def primary_agreement(ours, app, groups, n_perm=0, seed=SEED):
    """ตารางอัตราตรงต่อกลุ่ม + ALL · n_perm > 0: baseline สลับป้ายของแอปข้ามกองภายในกลุ่ม (ค่าเฉลี่ย + ช่วง 2.5–97.5%)"""
    d = primary_match(ours, app)
    d["group"] = [groups[c] for c in d.FundCode]
    rng = np.random.default_rng(seed)
    rows = []
    for g in sorted(d.group.unique()) + ["ALL"]:
        s = d if g == "ALL" else d[d.group == g]
        row = dict(group=g, n=len(s), n_country=int(s.match_country.sum()), n_sector=int(s.match_sector.sum()), n_either=int(s.match_either.sum()),
                   rate_country=float(s.match_country.mean()), rate_sector=float(s.match_sector.mean()), rate_either=float(s.match_either.mean()))
        if n_perm:
            o = s.ours.to_numpy()
            ac, as_ = s.app_country.to_numpy(), s.app_sector.to_numpy()
            if g == "ALL":
                grp = s.group.to_numpy()
                rates = []
                for _ in range(n_perm):
                    ix = np.arange(len(s))
                    pm = ix.copy()
                    for gg in sorted(set(grp)):
                        w = np.where(grp == gg)[0]
                        pm[w] = rng.permutation(w)
                    rates.append(float(((o == ac[pm]) | (o == as_[pm])).mean()))
            else:
                rates = []
                for _ in range(n_perm):
                    pm = rng.permutation(len(s))
                    rates.append(float(((o == ac[pm]) | (o == as_[pm])).mean()))
            row.update(base_either_mean=float(np.mean(rates)), base_either_lo=float(np.percentile(rates, 2.5)), base_either_hi=float(np.percentile(rates, 97.5)))
        rows.append(row)
    return pd.DataFrame(rows)
