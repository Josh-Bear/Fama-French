"""l4 — ฟังก์ชันใหม่ของ L4 (S007 + S008 + S009) · ไม่แก้ไฟล์ lib เดิม
FX/SPOT/CARRY · e จาก S006 · TER (กติกา actual_first) + QA · FXβ · ป้ายกลุ่ม/ตัวแทน cluster · ธีม ACWI_CD · ตาราง α (BH/BY/MDA) ·
FF 2010 block bootstrap · residual panel · factor กลุ่ม (PCA/mean · LOO) · null แบบ (b) · WLS ข้ามกอง (CR1/HC1) · FX gap · carry_diag · Q2"""
import re

import numpy as np
import pandas as pd
from scipy import stats

import external as ex
import l2
import nfactors as nf
import pca as pc
import regress as rg
import tests_stat as ts

SEED = 20261015
CUT = pd.Timestamp("2026-01-01")
ANN = 52
Z975, Z80 = stats.norm.ppf(0.975), stats.norm.ppf(0.80)


# ───────────────────────── factor ─────────────────────────
def fx_factor(F):
    """FX = SHV_THB − RF_BOT (= external.line3(F,'3a')['FX']) ตัดแถว ≥ 2026"""
    s = ex.line3(F, "3a")["FX"]
    return s[s.index < CUT].rename("FX")


def spot_carry(F):
    """SPOT = SHV_THB − SHV_USD · CARRY = SHV_USD − RF_BOT · SPOT + CARRY = FX"""
    F = F[F.index < CUT]
    return pd.DataFrame({"SPOT": F["SHV_THB"] - F["SHV_USD"], "CARRY": F["SHV_USD"] - F["RF_BOT"]})


def ref3a_factors(F):
    """MKT, BOND, GOLD, FX = external.line3(F,'3a') ตัดแถว ≥ 2026"""
    o = ex.line3(F, "3a")
    return o[o.index < CUT]


def e_from_s006(I, f, coef_csv, base):
    """e_j = I_j − b̂_j'f ทุก t โดย b̂ จาก runs/S006/resid_B_coef.csv (ไม่ประมาณใหม่) · คอลัมน์ตามลำดับในไฟล์"""
    co = pd.read_csv(coef_csv)
    co = co[co["base"] == base]
    fv = f.to_numpy(float)
    E = pd.DataFrame(index=I.index)
    for _, r in co.iterrows():
        b = np.array([r["b_" + c] for c in f.columns], float)
        E[r["index"]] = I[r["index"]].to_numpy(float) - fv @ b
    return E


# ───────────────────────── TER ─────────────────────────
def parse_fee(s):
    """"ไม่มี/ยกเว้น/ไม่เรียกเก็บ" → 0 · "0.535%" / "0.535" → 0.535 · อื่น → NaN"""
    if s is None or (isinstance(s, float) and np.isnan(s)):
        return np.nan
    s = str(s).strip()
    if s == "":
        return np.nan
    if any(w in s for w in ("ไม่มี", "ยกเว้น", "ไม่เรียกเก็บ")):
        return 0.0
    m = re.fullmatch(r"([0-9]*\.?[0-9]+)\s*%?", s)
    return float(m.group(1)) if m else np.nan


def _tt(fee, funds, code="TT"):
    d = fee[(fee["Complex Type Code"] == "FEEMF") & (fee["Code"] == code) & fee["Fund Code"].isin(set(funds))].copy()
    d["asof"] = pd.to_datetime(d["As of Date"].astype(str), format="%Y%m%d")
    d["a"] = d["Actual Value"].map(parse_fee)
    d["r"] = d["Rate"].map(parse_fee)
    return d.sort_values(["Fund Code", "asof"], kind="stable")


def ter_table(fee, funds, rule="actual_first", cutoff="2025-12-31"):
    """กติกา S009 1.1 (actual_first): Actual ≤ cutoff → Actual หลัง cutoff → Rate ≤ cutoff → Rate หลัง cutoff · as-of เร็วสุดในขั้น ·
    rule='vintage_first' = กติกา S008 (เพื่อทดสอบเท่านั้น) · คืน FundCode, ter, ter_src, ter_asof, ter_vintage, d_v2026, d_rate +
    rate_same (Rate ที่แถวเดียวกัน) · rate_le_first (Rate ≤ cutoff เร็วสุด) · act_le_first · act_y26_first"""
    cut = pd.Timestamp(cutoff)
    d = _tt(fee, funds)
    d["vint"] = np.where(d["asof"] <= cut, "le2025", "y2026")
    if rule == "actual_first":
        order = [("actual", "le2025"), ("actual", "y2026"), ("rate", "le2025"), ("rate", "y2026")]
    elif rule == "vintage_first":
        order = [("actual", "le2025"), ("rate", "le2025"), ("actual", "y2026"), ("rate", "y2026")]
    else:
        raise ValueError(rule)
    col = {"actual": "a", "rate": "r"}
    rows = []
    g_ = {k: v for k, v in d.groupby("Fund Code")}
    for f in funds:
        g = g_.get(f)
        row = dict(FundCode=f, ter=np.nan, ter_src=None, ter_asof=pd.NaT, ter_vintage=None, rate_same=np.nan, rate_le_first=np.nan,
                   act_le_first=np.nan, act_y26_first=np.nan)
        if g is not None:
            for src, v in order:
                h = g[(g["vint"] == v) & g[col[src]].notna()]
                if len(h):
                    row.update(ter=float(h.iloc[0][col[src]]), ter_src=src, ter_asof=h.iloc[0]["asof"], ter_vintage=v, rate_same=h.iloc[0]["r"])
                    break
            h = g[(g["vint"] == "le2025") & g["r"].notna()]
            row["rate_le_first"] = float(h.iloc[0]["r"]) if len(h) else np.nan
            h = g[(g["vint"] == "le2025") & g["a"].notna()]
            row["act_le_first"] = float(h.iloc[0]["a"]) if len(h) else np.nan
            h = g[(g["vint"] == "y2026") & g["a"].notna()]
            row["act_y26_first"] = float(h.iloc[0]["a"]) if len(h) else np.nan
        rows.append(row)
    out = pd.DataFrame(rows)
    out["d_v2026"] = (out["ter_vintage"] == "y2026").astype(int)
    out["d_rate"] = (out["ter_src"] == "rate").astype(int)
    return out


def _qstats(x):
    x = pd.Series(x).dropna()
    if len(x) == 0:
        return dict(n=0)
    return dict(n=int(len(x)), median=float(x.median()), q25=float(x.quantile(.25)), q75=float(x.quantile(.75)),
                frac_pos_or_zero=float((x >= -1e-12).mean()))


def ter_qa(fee, sel, pol=None, thr=0.90, cutoff="2025-12-31"):
    """QA ของ TER (S008 B.5 · S009 1.3): ตาราง vintage × src (× policy) · TT ≥ OF บน as-of ที่เลือก · NaN · ธง ter_dropped ·
    ตาราง Rate − Actual (ก) แถวเดียวกัน (ข) Rate ≤ cutoff เร็วสุด − Actual ที่เลือก · ตารางความเสถียรข้ามรุ่น (p1 ของรีวิว S009)"""
    funds = list(sel["FundCode"])
    out = {}
    s = sel.copy()
    if pol is not None:
        s["policy"] = s["FundCode"].map(pol)
    cols = ["ter_vintage", "ter_src"] + (["policy"] if pol is not None else [])
    cells = s.fillna({"ter_vintage": "none", "ter_src": "none"}).groupby(cols).size()
    out["cells"] = [dict(zip(cols, k if isinstance(k, tuple) else (k,)), n=int(v)) for k, v in cells.items()]
    out["n_nan"] = int(s["ter"].isna().sum())
    of = _tt(fee, funds, "OF")[["Fund Code", "asof", "a"]].rename(columns={"a": "of_a"})
    A = s[s["ter_src"] == "actual"].merge(of, left_on=["FundCode", "ter_asof"], right_on=["Fund Code", "asof"], how="left").dropna(subset=["of_a"])
    frac = float((A["ter"] >= A["of_a"] - 1e-12).mean()) if len(A) else float("nan")
    out["tt_ge_of"] = dict(n=int(len(A)), frac=frac, thr=thr)
    out["ter_dropped"] = bool(not (frac >= thr))
    Ac = s[s["ter_src"] == "actual"]
    out["rate_minus_actual_same_row"] = _qstats(Ac["rate_same"] - Ac["ter"])
    out["rate_le2025_minus_actual_chosen"] = _qstats(Ac["rate_le_first"] - Ac["ter"])
    both = s.dropna(subset=["act_le_first", "act_y26_first"])
    dd = both["act_y26_first"] - both["act_le_first"]
    st = _qstats(dd)
    st["corr"] = float(np.corrcoef(both["act_le_first"], both["act_y26_first"])[0, 1]) if len(both) > 2 else float("nan")
    out["cross_vintage_stability"] = st
    out["rate_funds"] = list(s.loc[s["ter_src"] == "rate", "FundCode"])
    return out


# ───────────────────────── FXβ ─────────────────────────
def fx_beta(R, F, mask_tr, funds):
    """Dimson b0+b1 ของ FX ใน y ~ [MKT, FX] (train) · MKT = MSCI_ACWI − RF_BOT"""
    rf = F["RF_BOT"]
    X = pd.DataFrame({"MKT": F["MSCI_ACWI"] - rf, "FX": F["SHV_THB"] - rf})
    fit = rg.fit_funds(R, rg.CommonFactors(X), mask_tr, 52, funds=list(funds))
    return pd.Series(fit.beta[:, 1], index=list(funds), name="FXb")


# ───────────────────────── กลุ่ม ─────────────────────────
def group_labels(prim, pol, funds, merge=None, excl=None):
    """G-E = ดัชนีหลักของ L2 (เฉพาะ policy E) · F → 'G-F' · O → 'G-O' · merge: {ตัวที่ถูกรวม: ตัวแทน} → ตัดตัวที่ถูกรวมทิ้ง ·
    excl: {ดัชนี: [กอง]} → กองนั้นไม่นับในกลุ่มธีมของดัชนี (ตกไป G-policy)"""
    merge = merge or {}
    excl = excl or {}
    rows = []
    for c in funds:
        if c in merge:
            continue
        p = pol[c]
        if p == "E":
            g = prim[c]
            if c in excl.get(g, []):
                g = "G-E?"
        else:
            g = "G-" + p
        rows.append(dict(FundCode=c, group=g, policy=p))
    return pd.DataFrame(rows)


def cluster_reps(codes, clusters):
    """ตัวแทน cluster: FundCode น้อยสุด (ลำดับตัวอักษร) ต่อกลุ่มกองอิสระ → dict cluster_id → FundCode"""
    reps = {}
    for c in sorted(codes):
        reps.setdefault(clusters[c], c)
    return reps


def group_table(labels, clusters, full_train, min_pca=10, min_loo=5):
    """ต่อกลุ่ม: n · n_indep_all · n_tr · n_indep_tr · reps · วิธี (S008 E.1–E.2) · full_train = Series FundCode→bool (ครบ train)"""
    rows = []
    for g, d in labels.groupby("group", sort=True):
        mem = list(d["FundCode"])
        tr = [c for c in mem if bool(full_train.get(c, False))]
        reps = list(cluster_reps(tr, clusters).values())
        n_all = int(pd.Series([clusters[c] for c in mem]).nunique())
        n_tr = len(tr)
        n_itr = len(reps)
        method = "PCA" if n_itr >= min_pca else ("LOO-mean" if n_all >= min_loo else "small")
        rows.append(dict(group=g, policy=d["policy"].iloc[0], n=len(mem), n_indep_all=n_all, n_tr=n_tr, n_indep_tr=n_itr, n_rep=len(reps),
                         method=method, dummy=bool(g.startswith("MSCI_") and d["policy"].iloc[0] == "E" and n_all >= min_pca),
                         members=";".join(sorted(mem)), reps=";".join(sorted(reps))))
    return pd.DataFrame(rows)


THEMES_ACWI_CD = {
    "ASP-DISRUPT": "เทคโนโลยี", "KT-WTAI-A": "เทคโนโลยี", "LHINNO-A": "เทคโนโลยี", "MFTECH": "เทคโนโลยี", "MGTECH": "เทคโนโลยี",
    "PRINCIPAL GCLOUD-A": "เทคโนโลยี", "PRINCIPAL GINNO-A": "เทคโนโลยี", "TNEXTGEN-A": "เทคโนโลยี", "UNI": "เทคโนโลยี",
    "ASP-IHEALTH": "Healthcare", "LHHEALTH-A": "Healthcare", "PRINCIPAL GHEALTH-A": "Healthcare", "TBIOTECH": "Healthcare",
    "TGENOME": "Healthcare", "TGHDIGI": "Healthcare",
    "LHMOBILITY-A": "EV", "TNEWENGY": "EV", "UEV": "EV",
    "LHESPORT-A": "Consumer", "LHGLIFEE-A": "Consumer", "MCANN": "Consumer", "ONE-GECOM": "Consumer",
    "ABAGS": "Global", "ABGS-A": "Global", "ASP-X": "Global", "B-USALPHA": "Global", "K-USA-A(A)": "Global", "LHGEQ-A": "Global",
    "MGAG": "Global", "MGAPVD": "Global", "ONE-DISC-RA": "Global", "ONE-UGG-RA": "Global", "PRINCIPAL GOPP-A": "Global",
    "ABWOOF": "Sustainable", "B-SIP": "Sustainable", "K-CHANGE-A(A)": "Sustainable",
    "B-FUTURE": "หลายธีม", "KKP G-THEME-H": "หลายธีม", "UGSE": "หลายธีม",
    "M-SUKUK": "ผิดกลุ่ม",
}


# ───────────────────────── α ─────────────────────────
def alpha_se(fit, R=None, prov=None, mask=None, L=4):
    """se_HAC(α̂) = |α̂/t_HAC| (m4) · t = 0 หรือ NaN → คำนวณตรงจาก ols_hac (ต้องให้ R, prov, mask) → (se, fallback_flag)"""
    a, t = fit.alpha, fit.t_alpha_hac
    good = np.isfinite(t) & (t != 0) & np.isfinite(a)
    se = np.where(good, np.abs(a / np.where(good, t, 1.0)), np.nan)
    fb = np.zeros(len(a), bool)
    if R is not None:
        Rv = R[fit.codes].to_numpy(float)
        mask = np.asarray(mask, bool)
        for j, c in enumerate(fit.codes):
            if fit.ok[j] and not good[j]:
                D = prov.design(c)
                ok = mask & np.isfinite(Rv[:, j]) & np.isfinite(D).all(1)
                r = rg.ols_hac(Rv[ok, j], np.column_stack([np.ones(int(ok.sum())), D[ok]]), L)
                se[j] = r["se"][0]
                fb[j] = True
    return se, fb


def alpha_table(fit, se=None, N_mt=None, ann=ANN, q=0.10):
    """α %/ปี · se · t · p (สองด้าน normal) · BH · BY · MDA (power 80%) · MDA_mt (Bonferroni ของการปฏิเสธตัวแรก) · index = fit.codes"""
    t = np.asarray(fit.t_alpha_hac, float)
    a = np.asarray(fit.alpha, float)
    if se is None:
        se = alpha_se(fit)[0]
    ok = np.asarray(fit.ok, bool) & np.isfinite(t)
    p = np.full(len(a), np.nan)
    p[ok] = 2 * stats.norm.sf(np.abs(t[ok]))
    bh = np.zeros(len(a), bool)
    bha = np.full(len(a), np.nan)
    by_ = np.zeros(len(a), bool)
    bya = np.full(len(a), np.nan)
    if ok.sum():
        bh[ok], bha[ok] = ts.bh(p[ok], q)
        by_[ok], bya[ok] = l2.by(p[ok], q)
    N = int(ok.sum()) if N_mt is None else int(N_mt)
    sp = se * ann * 100
    zmt = stats.norm.ppf(1 - q / (2 * max(N, 1)))
    return pd.DataFrame(dict(alpha_pct=a * ann * 100, se_pct=sp, t=t, p=p, bh=bh, bh_adj=bha, by=by_, by_adj=bya,
                             mda=(Z975 + Z80) * sp, mda_mt=(zmt + Z80) * sp, n_obs=np.asarray(fit.n)), index=list(fit.codes))


# ───────────────────────── FF 2010 block bootstrap ─────────────────────────
def ff_bootstrap(R, prov, funds, mask, alpha_hat, B=999, block=4, seed=SEED, min_rows=104, pcts=(1, 5, 10, 50, 90, 95, 99), is_E=None, L=4):
    """null: y*_it = y_it − α̂_i (บังคับ α = 0 พร้อมกัน) · สุ่ม moving block ของแถวเวลาของช่วง mask ร่วมทุกกอง (แถว [y*, X_t, X_t−1] ทั้งแถว) ·
    กองเข้ารอบเมื่อมี ≥ min_rows แถวไม่ขาด · คืน (rounds DataFrame, actual dict, summary DataFrame)"""
    funds = list(funds)
    rows_all = np.where(np.asarray(mask, bool))[0]
    Tw = len(rows_all)
    Rv = R[funds].to_numpy(float)
    ah = np.asarray(alpha_hat, float)
    prep = {}
    for j, c in enumerate(funds):
        if not np.isfinite(ah[j]):
            continue
        D = prov.design(c)[rows_all]
        y = Rv[rows_all, j]
        ok = np.isfinite(y) & np.isfinite(D).all(1)
        if ok.sum() < min_rows:
            continue
        pos = np.full(Tw, -1, int)
        pos[ok] = np.arange(int(ok.sum()))
        prep[j] = (np.column_stack([np.ones(int(ok.sum())), D[ok]]), y[ok] - ah[j], y[ok], pos)
    js = sorted(prep)
    E_ = np.zeros(len(js), bool) if is_E is None else np.asarray(is_E, bool)[js]
    t_act = np.array([rg.ols_hac(prep[j][2], prep[j][0], L)["t"][0] for j in js])
    p_act = 2 * stats.norm.sf(np.abs(t_act))

    def stat(t, e):
        o = {}
        pa = 2 * stats.norm.sf(np.abs(t))
        for q in pcts:
            o[f"p{q}_ALL"] = float(np.percentile(t, q))
            if e.any():
                o[f"p{q}_E"] = float(np.percentile(t[e], q))
        o["n_funds"] = int(len(t))
        o["n_bh"] = int(ts.bh(pa, 0.10)[0].sum())
        o["frac_bh"] = o["n_bh"] / len(t)
        o["n_t_lt_m196"] = int((t < -1.96).sum())
        o["n_t_gt_p196"] = int((t > 1.96).sum())
        return o

    actual = stat(t_act, E_)
    rng = np.random.default_rng(seed)
    IX = ts.block_indices(Tw, B, block, rng)
    rounds = []
    for b in range(B):
        ix = IX[b]
        tb = np.full(len(js), np.nan)
        for m, j in enumerate(js):
            Xc, yc, _, pos = prep[j]
            k = pos[ix]
            k = k[k >= 0]
            if len(k) < min_rows:
                continue
            tb[m] = rg.ols_hac(yc[k], Xc[k], L)["t"][0]
        okb = np.isfinite(tb)
        o = stat(tb[okb], E_[okb])
        o["round"] = b
        rounds.append(o)
    rd = pd.DataFrame(rounds)
    summ = []
    for k, v in actual.items():
        if k not in rd.columns:
            continue
        js_ = rd[k].to_numpy(float)
        js_ = js_[np.isfinite(js_)]
        pu = ts.p_boot_value(v, js_)
        pl = ts.p_boot_value(-v, -js_)
        summ.append(dict(stat=k, actual=v, null_mean=float(js_.mean()), null_p5=float(np.percentile(js_, 5)), null_p95=float(np.percentile(js_, 95)),
                         p_boot_upper=pu, p_boot_lower=pl))
    return rd, actual, pd.DataFrame(summ)


# ───────────────────────── residual · factor กลุ่ม ─────────────────────────
def resid_panel(R, prov, fit_tr, funds):
    """u_it = y_it − [1, D_it] coef_train ทุก t (รวม test)"""
    funds = list(funds)
    out = np.full((len(R.index), len(funds)), np.nan)
    Rv = R[funds].to_numpy(float)
    for j, c in enumerate(funds):
        jj = fit_tr.codes.index(c)
        if not fit_tr.ok[jj]:
            continue
        D = prov.design(c)
        cf = np.asarray(fit_tr.coef[jj], float)
        if len(cf) - 1 != D.shape[1]:  # coef ของ fit ผสม (l3.merge_fits) ถูกเติม NaN ที่คอลัมน์ PRIM สำหรับกองที่ใช้ฐานล้วน
            cf = cf[np.isfinite(cf)]
        out[:, j] = Rv[:, j] - rg.predict_oos(cf, D)
    return pd.DataFrame(out, index=R.index, columns=funds)


def group_k(u, reps, mask_tr, kmax=3, n_perm=500, seed=SEED, ed_fn=None):
    """k_g = min(k_ED, k_PA) บน correlation ของ u (train) ของตัวแทน cluster · คืน dict(k_ed, k_pa, k_g, flag, eig5)
    flag: ed_small (ตัวแทน < kmax+5) · ed_none (ED ไม่ลู่เข้า) · ''"""
    ed_fn = ed_fn or nf.onatski_ed
    reps = list(reps)
    res = dict(k_ed=None, k_pa=None, k_g=None, flag="", eig5=[])
    if len(reps) < kmax + 5:
        res["flag"] = "ed_small"
        return res
    U = u[reps].to_numpy(float)[np.asarray(mask_tr, bool)]
    U = U[np.isfinite(U).all(1)]
    Z = (U - U.mean(0)) / U.std(0)
    eig = nf.corr_eig(Z)
    res["eig5"] = [float(x) for x in eig[:5]]
    res["k_pa"] = int(nf.parallel_analysis(Z, n_perm, 0.95, seed))
    k_ed = ed_fn(eig, kmax)
    if k_ed is None:
        res["flag"] = "ed_none"
        return res
    res["k_ed"] = int(k_ed)
    res["k_g"] = int(min(k_ed, res["k_pa"]))
    return res


def peer_factor(u, peers, method, k, mask_tr, min_frac=0.5):
    """factor ของเพื่อน (T × k) · mean: ค่าเฉลี่ย u ของเพื่อน ณ t (ต้อง ≥ 3 กอง มิฉะนั้น NaN) · pca: น้ำหนัก train ตรึง (corr) + factor_returns"""
    P = u[list(peers)].to_numpy(float)
    if method == "mean":
        cnt = np.isfinite(P).sum(1)
        s = np.where(np.isfinite(P), P, 0.0).sum(1)
        return np.where(cnt >= 3, s / np.maximum(cnt, 1), np.nan).reshape(-1, 1)
    tr = P[np.asarray(mask_tr, bool)]
    tr = tr[np.isfinite(tr).all(1)]
    Lam, mu, sd, _ = pc.pca_fit(tr, k, "corr")
    return pc.factor_returns(P, Lam, sd, min_frac)


def group_factor_loo(u, members, clusters, method, k, mask_tr, reps=None, min_peer=8):
    """ต่อกอง i ใน members: factor ของเพื่อน (ไม่รวม i และกองใน cluster เดียวกับ i)
    PCA → peers = ตัวแทน cluster (reps) นอก cluster ของ i (ถ้า < min_peer → LOO-mean + flag peer_small) · mean → สมาชิกทุกกองนอก cluster ของ i
    คืน dict กอง → dict(g (T×k), flag, peers, method)"""
    out = {}
    for i in members:
        ci = clusters[i]
        if method == "pca":
            peers = [r for r in reps if clusters[r] != ci]
            if len(peers) >= min_peer:
                out[i] = dict(g=peer_factor(u, peers, "pca", k, mask_tr), flag="", peers=peers, method="pca")
                continue
            flag = "peer_small"
            peers = [m for m in members if clusters[m] != ci]
            out[i] = dict(g=peer_factor(u, peers, "mean", 1, mask_tr), flag=flag, peers=peers, method="mean")
        else:
            peers = [m for m in members if clusters[m] != ci]
            out[i] = dict(g=peer_factor(u, peers, "mean", 1, mask_tr), flag="", peers=peers, method="mean")
    return out


def fit_with_factor(y, D, g, mask_tr, mask_te, L=4, min_obs=52, min_te=20):
    """y ~ X_i (D = [cur|lag]) เทียบ y ~ X_i + g (Dimson ทั้งคู่) บนแถว train เดียวกัน → Δadj R² · ΔBIC · ΔR²_oos · α ใหม่ · residual"""
    y = np.asarray(y, float)
    g = np.asarray(g, float).reshape(len(y), -1)
    K = D.shape[1] // 2
    gl = rg.lag_stack(g)
    D2 = np.hstack([D[:, :K], g, D[:, K:], gl[:, g.shape[1]:]])
    ok = np.asarray(mask_tr, bool) & np.isfinite(y) & np.isfinite(D2).all(1) & np.isfinite(D).all(1)
    n = int(ok.sum())
    nan = dict(n=n, d_adj_r2=np.nan, d_bic=np.nan, d_r2_oos=np.nan, alpha_new=np.nan, alpha_old=np.nan, resid_new=None, ok=False)
    if n < max(min_obs, D2.shape[1] + 4):
        return nan
    X1 = np.column_stack([np.ones(n), D[ok]])
    X2 = np.column_stack([np.ones(n), D2[ok]])
    r1, r2 = rg.ols_hac(y[ok], X1, L), rg.ols_hac(y[ok], X2, L)
    bic = lambda r: n * np.log(r["ssr"] / n) + r["p"] * np.log(n)
    te = np.asarray(mask_te, bool) & np.isfinite(y) & np.isfinite(D2).all(1) & np.isfinite(D).all(1)
    d_ro = np.nan
    if te.sum() >= min_te:
        y1 = rg.predict_oos(r1["coef"], D[te])
        y2 = rg.predict_oos(r2["coef"], D2[te])
        d_ro = rg.r2_oos(y[te], y2) - rg.r2_oos(y[te], y1)
    res = np.full(len(y), np.nan)
    res[ok] = r2["resid"]
    return dict(n=n, d_adj_r2=r2["adj_r2"] - r1["adj_r2"], d_bic=bic(r2) - bic(r1), d_r2_oos=d_ro, alpha_new=r2["coef"][0],
                alpha_old=r1["coef"][0], resid_new=res, ok=True)


def random_group_null(delta_fn, members, pool_fn, n_peer, method, k, u, mask_tr, n_draw=200, seed=SEED, min_frac=0.5):
    """null แบบ (b): ต่อ draw · ต่อสมาชิกจริง i สุ่ม n_peer[i] กองจาก pool_fn(i) แบบไม่ใส่คืน → factor ด้วยวิธีเดียวกัน (PCA ใช้ k ของกลุ่มจริง) →
    delta_fn(i, g) = ΔR²_oos(i) (y_i / X_i ของสมาชิกจริงไม่ถูกแตะ) · สถิติต่อ draw = median ของสมาชิก · คืน array (n_draw,)"""
    rng = np.random.default_rng(seed)
    pools = {i: sorted(pool_fn(i)) for i in members}
    out = np.full(n_draw, np.nan)
    for d in range(n_draw):
        vals = []
        for i in members:
            pl = pools[i]
            m = int(n_peer[i])
            if m > len(pl):
                continue
            peers = [pl[x] for x in rng.choice(len(pl), size=m, replace=False)]
            g = peer_factor(u, peers, method, k, mask_tr, min_frac)
            v = delta_fn(i, g)
            if np.isfinite(v):
                vals.append(v)
        out[d] = np.median(vals) if vals else np.nan
    return out


def null_summary(true_med, draws):
    """percentile 95 ของ null · p_null = (1 + #{null ≥ จริง}) / (n + 1)"""
    d = np.asarray(draws, float)
    d = d[np.isfinite(d)]
    return dict(null_p95=float(np.percentile(d, 95)), null_median=float(np.median(d)), p_null=float((1 + np.sum(d >= true_med)) / (len(d) + 1)), n_draw=int(len(d)))


def max_abs_corr(u, i, peers, mask_tr):
    """max |corr(u_i, u_peer)| (train) และกองที่ให้ค่านั้น"""
    m = np.asarray(mask_tr, bool)
    best, who = np.nan, ""
    yi = u[i].to_numpy(float)
    for p in peers:
        yp = u[p].to_numpy(float)
        ok = m & np.isfinite(yi) & np.isfinite(yp)
        if ok.sum() < 30:
            continue
        c = abs(float(np.corrcoef(yi[ok], yp[ok])[0, 1]))
        if not np.isfinite(best) or c > best:
            best, who = c, p
    return best, who


# ───────────────────────── cross-section ─────────────────────────
def build_x(df, cont, binary, group_cols, min_n=3, rate_rule=True):
    """สร้าง X ตามกติกาชุดย่อย (S008 C.4 · S009 1.4): กลุ่ม dummy ที่มี < min_n กอง → รวมฐาน (ตัดคอลัมน์) · binary ที่ค่า 0 หรือ 1 มี < min_n → ตัดคอลัมน์ ·
    d_rate: ถ้ามีกอง d_rate=1 อยู่ 1..min_n−1 กอง → ตัดคอลัมน์และตัดกองนั้นออกจาก regression (TER = NaN)
    คืน (X DataFrame มี const, df ที่เหลือ, dict dropped)"""
    d = df.copy()
    dropped = dict(cols=[], funds=[])
    if rate_rule and "d_rate" in binary and "d_rate" in d.columns:
        nr = int((d["d_rate"] == 1).sum())
        if 0 < nr < min_n:
            dropped["funds"] = list(d.index[d["d_rate"] == 1])
            d = d[d["d_rate"] != 1]
    cols = list(cont)
    for b in binary:
        n1 = int((d[b] == 1).sum())
        n0 = int((d[b] == 0).sum())
        if n1 < min_n or n0 < min_n:
            dropped["cols"].append(b)
        else:
            cols.append(b)
    for g in group_cols:
        if int((d[g] == 1).sum()) < min_n:
            dropped["cols"].append(g)
        else:
            cols.append(g)
    X = d[cols].astype(float).copy()
    X.insert(0, "const", 1.0)
    return X, d, dropped


def xsec_wls(y, se, X, clusters, weights="inv_var", wald_cols=None, policy=None, level=0.95):
    """WLS (w = 1/se²) หรือ OLS · SE: CR1 ตามกลุ่มกองอิสระ [G/(G−1)·(N−1)/(N−K)] + HC1 [N/(N−K)] · CI แบบ t(G−1) ·
    Wald ร่วมของ wald_cols (cluster · χ²) · Kish n_eff · top10_share · สัดส่วนน้ำหนักต่อ policy"""
    y = np.asarray(y, float)
    Xv = X.to_numpy(float)
    N, K = Xv.shape
    w = 1.0 / np.asarray(se, float) ** 2 if weights == "inv_var" else np.ones(N)
    sw = np.sqrt(w)
    Xt, yt = Xv * sw[:, None], y * sw
    A = np.linalg.inv(Xt.T @ Xt)
    b = A @ (Xt.T @ yt)
    e = yt - Xt @ b
    cl = np.asarray(clusters)
    G = len(np.unique(cl))
    meat = np.zeros((K, K))
    for g in np.unique(cl):
        s = (Xt[cl == g] * e[cl == g][:, None]).sum(0)
        meat += np.outer(s, s)
    V_cr = (G / (G - 1.0)) * ((N - 1.0) / (N - K)) * A @ meat @ A
    Xe = Xt * e[:, None]
    V_hc = (N / (N - K)) * A @ (Xe.T @ Xe) @ A
    sec, seh = np.sqrt(np.diag(V_cr)), np.sqrt(np.diag(V_hc))
    tc = stats.t.ppf(0.5 + level / 2, G - 1)
    tab = pd.DataFrame(dict(coef=b, se_cr1=sec, t_cr1=b / sec, p_cr1=2 * stats.t.sf(np.abs(b / sec), G - 1), ci_lo=b - tc * sec, ci_hi=b + tc * sec,
                            se_hc1=seh, ci_lo_hc1=b - tc * seh, ci_hi_hc1=b + tc * seh), index=list(X.columns))
    out = dict(coef=tab, N=N, K=K, G=G, kish_n=float(w.sum() ** 2 / (w ** 2).sum()), top10_share=float(np.sort(w)[::-1][:10].sum() / w.sum()))
    if wald_cols:
        ii = [list(X.columns).index(c) for c in wald_cols]
        W = float(b[ii] @ np.linalg.solve(V_cr[np.ix_(ii, ii)], b[ii]))
        out["wald"] = dict(q=len(ii), W=W, p=float(stats.chi2.sf(W, len(ii))))
    if policy is not None:
        pol = np.asarray(policy)
        out["policy_share"] = {g: float(w[pol == g].sum() / w.sum()) for g in np.unique(pol)}
    return out


def fx_gap(alpha_a, alpha_b, fxb, groups, min_n=10, min_gap=0.5, min_groups=3):
    """gap = median α̂(FXβ ต่ำกว่ามัธยฐานกลุ่ม) − median α̂(สูงกว่า) · a = ไม่มี FX · b = มี FX · ratio = |gap_b|/|gap_a| (N/A เมื่อ |gap_a| < min_gap) ·
    คืน (ตารางต่อกลุ่ม, dict สรุป: median ratio เฉพาะกลุ่มที่คำนวณได้ · N/A ถ้าได้ < min_groups)"""
    rows = []
    for g, mem in groups.groupby(groups):
        mem = [c for c in mem.index if c in fxb.index and np.isfinite(fxb[c]) and np.isfinite(alpha_a.get(c, np.nan)) and np.isfinite(alpha_b.get(c, np.nan))]
        if len(mem) < min_n:
            continue
        med = np.median(fxb[mem])
        lo = [c for c in mem if fxb[c] < med]
        hi = [c for c in mem if fxb[c] > med]
        ga = float(np.median(alpha_a[lo]) - np.median(alpha_a[hi]))
        gb = float(np.median(alpha_b[lo]) - np.median(alpha_b[hi]))
        ok = abs(ga) >= min_gap
        rows.append(dict(group=g, n=len(mem), n_low=len(lo), n_high=len(hi), fxb_median=float(med), gap_noFX=ga, gap_FX=gb,
                         ratio=(abs(gb) / abs(ga) if ok else np.nan), gap_diff=gb - ga))
    tab = pd.DataFrame(rows)
    n_ok = int(tab["ratio"].notna().sum()) if len(tab) else 0
    summ = dict(n_groups=len(tab), n_computable=n_ok, median_ratio=(float(tab["ratio"].median()) if n_ok >= min_groups else np.nan),
                na=bool(n_ok < min_groups))
    return tab, summ


def carry_diag(F):
    """ช่วง full: R² ของ CARRY บน [1, trend] · uncentered share = mean²/(mean²+var) · corr(CARRY_t, CARRY_t−1)"""
    c = spot_carry(F)["CARRY"].to_numpy(float)
    t = np.arange(len(c), dtype=float)
    X = np.column_stack([np.ones(len(c)), t])
    b = np.linalg.lstsq(X, c, rcond=None)[0]
    res = c - X @ b
    r2 = 1 - (res @ res) / ((c - c.mean()) ** 2).sum()
    m2, v = c.mean() ** 2, c.var()
    return dict(r2_trend=float(r2), uncentered_share=float(m2 / (m2 + v)), lag1_corr=float(np.corrcoef(c[1:], c[:-1])[0, 1]), n=int(len(c)))


def q2_verdict(tab, p_boot_gt=False):
    """ตาราง F ของ S008: คอลัมน์ bh1, bh2 (BH full M1/M2), sg1, sg2 (เครื่องหมาย train = test = full), div, alpha1 (α full M1) ·
    คืน DataFrame verdict / div_note / label"""
    both = tab["bh1"].astype(bool) & tab["bh2"].astype(bool)
    one = tab["bh1"].astype(bool) ^ tab["bh2"].astype(bool)
    sg = tab["sg1"].astype(bool) & tab["sg2"].astype(bool)
    v = np.where(both & sg, "มีหลักฐาน α", np.where(both, "บางส่วน (ไม่ซ้ำในช่วง test)", np.where(one, "บางส่วน (ฐานเดียว)", "ไม่พบ")))
    note = np.where((v != "ไม่พบ") & tab["div"].astype(bool) & (tab["alpha1"] < 0), "อาจเป็นผลปันผล", "")
    out = pd.DataFrame(dict(verdict=v, div_note=note), index=tab.index)
    out["label"] = np.where(out["verdict"] != "ไม่พบ", "แยกจากโชคไม่ได้" if p_boot_gt else "", "")
    return out


class MixedProvider:
    """provider ของ model α: base (+ per_fund: dict กอง → Series 1 ตัว = e_p(i)) · กองที่ไม่อยู่ใน per_fund ใช้ base ล้วน (K ต่างกันได้ ·
    ใช้กับ resid_panel / ff_bootstrap / fit_with_factor ที่เรียกเฉพาะ .design(code) · ห้ามส่งเข้า rg.fit_funds ตรงๆ — ใช้ l3.fit_perfund)"""

    def __init__(self, base, per_fund=None):
        self.per_fund = per_fund or {}
        self.pb = rg.CommonFactors(base)
        self.pa = l2.AugmentedFactors(base, per_fund=self.per_fund) if self.per_fund else None

    def design(self, code=None):
        if self.pa is not None and code in self.per_fund:
            return self.pa.design(code)
        return self.pb.design(code)


def sub_fit(fit, idx):
    """มุมมองย่อยของ FitResult (codes / alpha / t_alpha_hac / ok / n) สำหรับ alpha_table"""
    import types
    ns = types.SimpleNamespace()
    ns.codes = [fit.codes[i] for i in idx]
    for nm in ("alpha", "t_alpha_hac", "ok", "n"):
        setattr(ns, nm, np.asarray(getattr(fit, nm))[idx])
    return ns
