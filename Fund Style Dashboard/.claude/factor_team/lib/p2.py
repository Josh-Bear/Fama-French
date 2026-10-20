"""p2 — ระยะ 2 (S010 + S011): อำนาจทำนายแบบ walk-forward รายไตรมาส · ไม่แก้ lib เดิม (เรียกใช้เท่านั้น)

หลักการ: ทุกฟังก์ชันที่คำนวณ "สัญญาณ ณ t" รับข้อมูลที่ผ่าน `truncate` (แถว ≤ t) เท่านั้น · target คำนวณแยกใน `target_at`
ข้อมูลจริงเข้ามาผ่าน `Inputs` (R · Z · F3 · AUM · meta) · test ใช้ข้อมูลจำลองเท่านั้น
"""
import csv
import hashlib
import math
import re
import shutil
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

import l2
import nfactors as nf
import pca as pc
import regress as rg
import samples as sm
import tests_stat as ts

SEED = 20261015
K_PC = 4
MIN_OBS = 52
HAC_L = 4
N_QUANT_PRIOR = 102  # quant_team ณ 2026-10-15 ตาม BRIEF (ไม่ได้ตรวจซ้ำเอง)
PCNAMES = ["PC1", "PC2", "PC3", "PC4", "PC5", "PC6", "PC7", "PC8"]

# ───────────────────────── วันที่ (ข้อ 3.1) ─────────────────────────


def decision_dates(index, freq="Q"):
    """วันตัดสินใจ = แถวสุดท้าย ≤ สิ้นไตรมาส (Q: 2022-03 → 2025-09 = 15 จุด) / สิ้นเดือน (M: 2022-03 → 2025-11 = 45 จุด)
    window target = แถว (t_j, t_{j+1}] · จุดสุดท้ายจบที่แถวสุดท้ายของ index"""
    idx = pd.DatetimeIndex(index)
    if freq == "Q":
        ends = pd.date_range("2022-03-31", "2025-09-30", freq="QE")
    elif freq == "M":
        ends = pd.date_range("2022-03-31", "2025-11-30", freq="ME")
    else:
        raise ValueError(freq)
    pos = [int(idx.searchsorted(e, side="right")) - 1 for e in ends]
    pos.append(len(idx) - 1)
    rows = []
    for j in range(len(pos) - 1):
        rows.append(dict(j=j, t_pos=pos[j], t=idx[pos[j]], e_pos=pos[j + 1], e=idx[pos[j + 1]], n_q=pos[j + 1] - pos[j]))
    return pd.DataFrame(rows)


def truncate(obj, t):
    """คืนเฉพาะแถว ≤ t (index เป็นวันที่)"""
    t = pd.Timestamp(t)
    return obj.loc[np.asarray(obj.index <= t)]


# ───────────────────────── ชื่อกองทอง / universe (ข้อ 3.2 · S011 ข้อ 1–2) ─────────────────────────
_GOLD_RE = re.compile(r"gold(?!en)")


def is_gold(name_en, name_th):
    """กองทอง: EN มี 'gold' (ไม่สนตัวพิมพ์ · ไม่รวม 'golden') หรือ TH มี 'ทองคำ' (S011 ข้อ 1.1)"""
    en = name_en.lower() if isinstance(name_en, str) else ""
    th = name_th if isinstance(name_th, str) else ""
    return bool(_GOLD_RE.search(en)) or ("ทองคำ" in th)


def zero_flags(raw):
    """raw ret (T x N) → 1.0 ถ้า ret == 0 · 0.0 ถ้า ≠ 0 · NaN ถ้าไม่มีข้อมูล"""
    return (raw == 0).astype(float).where(raw.notna())


def dedup_at(R_le, funds, thr=0.99, min_overlap=MIN_OBS):
    """ตัดซ้ำ ≤ t: คู่ corr > thr (overlap ≥ min_overlap) → connected components → เก็บกองที่มีแถว ≤ t มากสุด (เสมอ → FundCode)"""
    funds = sorted(funds)
    if len(funds) == 0:
        return []
    X = R_le[funds]
    A = X.corr(min_periods=min_overlap).to_numpy()
    ia, ib = np.triu_indices(len(funds), 1)
    sel = np.isfinite(A[ia, ib]) & (A[ia, ib] > thr)
    pairs = pd.DataFrame({"a": [funds[i] for i in ia[sel]], "b": [funds[i] for i in ib[sel]]}, columns=["a", "b"])
    return sm.dedup_keep(pairs, X.notna().sum(axis=0))


def clusters_at(R_le, funds, thr=0.95, min_overlap=MIN_OBS):
    """cluster corr ≥ thr ≤ t (l2.fund_clusters) → Series FundCode→group_id"""
    m = np.ones(len(R_le), bool)
    d = l2.fund_clusters(R_le, m, list(funds), thr, min_overlap)
    return d.set_index("FundCode")["group_id"]


def dimson_rows(R_le, F3_le):
    """จำนวนแถว Dimson ต่อกอง: pos ≥ 1 และ r มีค่า และ factor ③a แถวนั้น + แถวก่อนหน้าครบ"""
    f_ok = np.isfinite(F3_le.to_numpy(float)).all(axis=1)
    ok_row = f_ok.copy()
    ok_row[1:] &= f_ok[:-1]
    ok_row[0] = False
    return R_le.notna().mul(ok_row, axis=0).sum(axis=0)


def zero_frac(Z_le):
    n = Z_le.notna().sum(axis=0)
    return (Z_le == 1).sum(axis=0) / n.replace(0, np.nan)


def universe_pre(R_le, Z_le, F3_le, meta):
    """U_t^pre = (u0)–(u5) (S011 ข้อ 2.1) · ใช้แถว ≤ t เท่านั้น · คืน dict(U, counts)"""
    cols = list(R_le.columns)
    c = {}
    u0 = R_le.iloc[-1].notna()
    c["n_u1"] = len(cols)
    c["n_gone_u0"] = int((~u0 & (R_le.notna().sum(axis=0) >= 1)).sum())
    n52 = dimson_rows(R_le, F3_le)
    u2 = n52 >= MIN_OBS
    c["n_pass52"] = int(u2.sum())
    u3 = zero_frac(Z_le.reindex(columns=cols)).fillna(1.0) <= 0.10
    base = u0 & u2 & u3
    c["n_gone_u0_among_52"] = int((~u0 & u2 & u3).sum())
    gold = meta["gold"].reindex(cols).fillna(False).astype(bool)
    div = (meta["div_flag"].reindex(cols) == "Y")
    c["n_gold_cut"] = int((base & gold).sum())
    c["n_div_cut"] = int((base & div).sum())
    c["n_gold_div_cut"] = int((base & (gold | div)).sum())
    u4 = base & ~gold & ~div
    c["n_pre_dedup"] = int(u4.sum())
    keep = dedup_at(R_le, list(np.array(cols)[u4.to_numpy()]))
    c["n_dup_cut"] = c["n_pre_dedup"] - len(keep)
    return dict(U=keep, counts=c)


def pca_sample(R_le, Z_le, kind="balanced", gold=None):
    """S_t: balanced (ครบทุกแถว ≤ t) + (u3) + ตัดซ้ำ ≤ t · kind='em' → ≥ 52 แถวที่มีค่า (W1) · รวมกองทอง / ปันผล"""
    cols = list(R_le.columns)
    u3 = zero_frac(Z_le.reindex(columns=cols)).fillna(1.0) <= 0.10
    if kind == "balanced":
        ok = R_le.notna().all(axis=0) & u3
    else:
        ok = (R_le.notna().sum(axis=0) >= MIN_OBS) & u3
    cand = list(np.array(cols)[ok.to_numpy()])
    return dedup_at(R_le, cand)


# ───────────────────────── PCA / factor / Procrustes (ข้อ 3.3) ─────────────────────────


def expanding_pca(R_le, S, k=K_PC, kind="balanced"):
    """PCA corr บน S (balanced) · หรือ EM-PCA (W1) · คืน dict(Lam, sd, eig, funds, k)"""
    X = R_le[S].to_numpy(float)
    if kind == "balanced":
        Lam, mu, sd, eig = pc.pca_fit(X, k, "corr")
    else:
        Lam, mu, sd, it, conv = pc.em_pca(X, k)
        eig = None
    return dict(Lam=Lam, mu=mu, sd=sd, eig=eig, funds=list(S), k=k)


def procrustes(L_t, funds_t, L_prev, funds_prev):
    """Q = UVᵀ จาก SVD ของ L_t[C]ᵀ L_prev[C] · C = funds_t ∩ funds_prev · คืน (Q, common)"""
    common = sorted(set(funds_t) & set(funds_prev))
    it = {c: i for i, c in enumerate(funds_t)}
    ip = {c: i for i, c in enumerate(funds_prev)}
    A = L_t[[it[c] for c in common]]
    B = L_prev[[ip[c] for c in common]]
    U, _, Vt = np.linalg.svd(A.T @ B)
    return U @ Vt, common


def tucker(A, B):
    """Tucker congruence ต่อคอลัมน์"""
    num = (A * B).sum(axis=0)
    return num / (np.linalg.norm(A, axis=0) * np.linalg.norm(B, axis=0))


def factor_series(R, pf, rows_mask_or_slice, Lam=None, names=None):
    """factor จาก pf (น้ำหนักตรึง) บนแถวที่เลือก · min_frac 0.5 · ไม่หัก μ"""
    X = R.loc[rows_mask_or_slice, pf["funds"]].to_numpy(float)
    L = pf["Lam"] if Lam is None else Lam
    f = pc.factor_returns(X, L, pf["sd"], min_frac=0.5)
    return f


def fit_at(R_le, Fdf, funds, window=None):
    """M ณ t: Dimson + HAC L=4 · window=None → expanding · window=104 → 104 แถวล่าสุด ≤ t (index สั้นกว่า → ทุกแถว)"""
    T = len(R_le)
    mask = np.ones(T, bool)
    if window is not None and T > window:
        mask[: T - window] = False
    return rg.fit_funds(R_le, Fdf, mask, MIN_OBS, HAC_L, funds=funds)


# ───────────────────────── สัญญาณ (ข้อ 4.1) ─────────────────────────


def sig_B0(R_le, funds):
    L = R_le[funds].iloc[-52:]
    cnt = L.notna().sum(axis=0)
    return (52.0 * L.mean(axis=0)).where(cnt >= 47)


def sig_C2(R_le, funds):
    L = R_le[funds].iloc[-52:]
    cnt = L.notna().sum(axis=0)
    return (-L.std(axis=0, ddof=1)).where(cnt >= 47)


def sig_alpha_t(fit):
    return pd.Series(fit.t_alpha_hac, index=fit.codes)


def sig_C1(fit104):
    """1 − adj R² (S011 ข้อ 6)"""
    return pd.Series(1.0 - fit104.adj_r2, index=fit104.codes)


def sig_D1(meta, funds):
    """−TER (ter_src = actual เท่านั้น · rate/ไม่มี → NaN)"""
    ter = meta["ter"].reindex(funds)
    src = meta["ter_src"].reindex(funds)
    return (-ter).where(src == "actual")


def sig_D3(aum_row, funds):
    """−ln(AUM ที่แถว t) · ไม่เติมย้อน"""
    a = aum_row.reindex(funds).astype(float)
    return pd.Series(np.where(a > 0, -np.log(a.where(a > 0)), np.nan), index=funds)


def sig_C3(a1, c1):
    """C3: ค่าตัด = มัธยฐานของ C1 บน (ชุดที่ส่งเข้ามา = U_t^pre ∩ {A1, C1}) · สมาชิก = C1 ≥ ค่าตัด · คืน (สัญญาณ A1 ของสมาชิก, ค่าตัด, mask)"""
    ok = a1.notna() & c1.notna()
    if ok.sum() == 0:
        return a1 * np.nan, np.nan, ok & False
    cut = float(np.median(c1[ok].to_numpy(float)))
    mem = ok & (c1 >= cut)
    return a1.where(mem), cut, mem


def sig_B2(fit_al, fbar):
    """52 × Σ_k β̂_k f̄_k (β̂ = b0 + b1)"""
    return pd.Series(52.0 * np.nansum(fit_al.beta * np.asarray(fbar)[None, :], axis=1), index=fit_al.codes).where(fit_al.ok)


def b1_state(f_le_al):
    """s_k = sign(Σ 52 แถวล่าสุด) · σ̂_k = sd (ddof 1) ของ f ทุกแถว ≤ t"""
    A = np.asarray(f_le_al, float)
    s = np.sign(np.nansum(A[-52:], axis=0))
    sd = np.nanstd(A, axis=0, ddof=1)
    return s, sd


def b1_payoff(s, sd, Fq, n_q):
    """π_k = s_k F_k /(σ_k √n_q) · m = mean_k π_k"""
    pi = s * np.asarray(Fq, float) / (sd * math.sqrt(n_q))
    return pi, float(np.mean(pi))


# ───────────────────────── target (ข้อ 3.5 · แยกจากสัญญาณ) ─────────────────────────


def targets(Rw, Fprev, coef, n_q, kind="resid", drop_first=False):
    """Rw: (n x N) ผลตอบแทนส่วนเกินในไตรมาสเป้าหมาย · Fprev: (n+1 x K) factor แถว t ถึงแถวสุดท้าย (แถวแรก = lag ของสัปดาห์แรก)
    coef: (N x (1+2K)) = [α, b0, b1] จาก fit ณ t · kind 'resid' = r − b0'f_s − b1'f_{s−1} (ไม่หัก α) · 'tot' = r
    สเกล n_q/|W_i| · คืน (T, |W|)"""
    Rw = np.asarray(Rw, float)
    n = Rw.shape[0]
    if kind == "tot":
        res = Rw.copy()
        okrow = np.ones(n, bool)
    else:
        Fp = np.asarray(Fprev, float)
        K = Fp.shape[1]
        D = np.hstack([Fp[1:], Fp[:-1]])
        okrow = np.isfinite(D).all(axis=1)
        pred = np.nan_to_num(D) @ np.asarray(coef, float)[:, 1:].T
        res = Rw - pred
    valid = np.isfinite(res) & okrow[:, None]
    if drop_first:
        valid = valid.copy()
        valid[0, :] = False
        nq = n_q - 1
    else:
        nq = n_q
    W = valid.sum(axis=0)
    S = np.where(valid, res, 0.0).sum(axis=0)
    with np.errstate(divide="ignore", invalid="ignore"):
        T = np.where(W > 0, nq / W * S, np.nan)
    return T, W


# ───────────────────────── Inputs / state_at / target_at ─────────────────────────


class Inputs:
    """R (ส่วนเกิน RF) · Z (zero flag) · F3 (MKT,BOND,GOLD,FX) · AUM · meta (policy, div_flag, gold, ter, ter_src, ter_vintage)"""

    def __init__(self, R, Z, F3, AUM, meta):
        self.R, self.Z, self.F3, self.AUM, self.meta = R, Z, F3, AUM, meta


def _fdf(f_le, F3_le, variant):
    k = f_le.shape[1]
    D = pd.DataFrame(f_le, index=F3_le.index, columns=PCNAMES[:k])
    D["FX"] = F3_le["FX"].to_numpy(float)
    if variant == "W2":
        D["GOLD"] = F3_le["GOLD"].to_numpy(float)
    return D


def state_at(inp, t_pos, prev=None, variant=None, k=K_PC):
    """ทุกอย่างที่รู้ ณ t (ใช้แถว ≤ t เท่านั้น — truncate ก่อนเริ่ม) · prev = state ก่อนหน้า (ของ variant เดียวกัน) สำหรับ Procrustes
    variant: None · 'W1' (EM-PCA) · 'W2' (+GOLD) · 'W3' (k ตาม ED ≤ t)"""
    t = inp.R.index[t_pos]
    R_le = truncate(inp.R, t)
    Z_le = truncate(inp.Z, t)
    F3_le = truncate(inp.F3, t)
    aum_t = truncate(inp.AUM, t)
    aum_row = aum_t.iloc[-1] if (len(aum_t) and aum_t.index[-1] == t) else pd.Series(dtype=float)
    meta = inp.meta
    st = dict(t=t, t_pos=t_pos, variant=variant)
    up = universe_pre(R_le, Z_le, F3_le, meta)
    U = up["U"]
    st["U"], st["counts"] = U, up["counts"]
    S = pca_sample(R_le, Z_le, "em" if variant == "W1" else "balanced")
    st["S"] = S
    ed_fallback = False
    kk = k
    if variant == "W3":
        P8 = expanding_pca(R_le, S, 8, "balanced")
        try:
            ed = nf.onatski_ed(P8["eig"], 8)
        except Exception:
            ed = None
        if ed is None:
            ed_fallback = True
            kk = K_PC
        else:
            kk = max(1, int(ed))
    st["k"], st["ed_fallback"] = kk, ed_fallback
    pf = expanding_pca(R_le, S, kk, "em" if variant == "W1" else "balanced")
    st["pf"] = pf
    if prev is None or prev["k"] != kk:
        Q = np.eye(kk)
        common = []
    else:
        Q, common = procrustes(pf["Lam"], S, prev["Lam_al"], prev["S"])
    Lam_al = pf["Lam"] @ Q
    st["Q"], st["Lam_al"], st["n_common"] = Q, Lam_al, len(common)
    st["tucker"] = tucker(Lam_al[[S.index(c) for c in common]], prev["Lam_al"][[prev["S"].index(c) for c in common]]) if (len(common) and prev is not None and prev["k"] == kk) else np.full(kk, np.nan)
    f_le = pc.factor_returns(R_le[S].to_numpy(float), pf["Lam"], pf["sd"], 0.5)
    f_al = pc.factor_returns(R_le[S].to_numpy(float), Lam_al, pf["sd"], 0.5)
    st["f_le"], st["f_al"] = f_le, f_al
    Fd = _fdf(f_le, F3_le, variant)
    Fd_al = _fdf(f_al, F3_le, variant)
    st["fit_e"] = fit_at(R_le, Fd, U)
    st["fit_104"] = fit_at(R_le, Fd, U, 104)
    st["fit_al"] = fit_at(R_le, Fd_al, U)
    st["fit_3a"] = fit_at(R_le, F3_le[["MKT", "BOND", "GOLD", "FX"]], U)
    sig = pd.DataFrame(index=U)
    sig["B0"] = sig_B0(R_le, U)
    sig["A2"] = sig_alpha_t(st["fit_3a"])
    sig["C1"] = sig_C1(st["fit_104"])
    sig["A1"] = sig_alpha_t(st["fit_e"])
    sig["C2"] = sig_C2(R_le, U)
    sig["D1"] = sig_D1(meta, U)
    sig["D3"] = sig_D3(aum_row, U)
    fbar = np.nanmean(Fd_al.to_numpy(float)[-52:], axis=0)
    sig["B2"] = sig_B2(st["fit_al"], fbar)
    c3, cut, mem = sig_C3(sig["A1"], sig["C1"])
    sig["C3"] = c3
    st["sig"], st["c3_cut"], st["c3_member"] = sig, cut, mem
    st["B1_al"] = b1_state(f_al)
    st["B1_raw"] = b1_state(f_le)
    st["clusters"] = clusters_at(R_le, U) if len(U) else pd.Series(dtype=int)
    n_le = R_le[U].notna().sum(axis=0)
    rep = {}
    for g, grp in st["clusters"].groupby(st["clusters"]):
        codes = sorted(grp.index, key=lambda c: (-int(n_le[c]), c))
        rep[g] = codes[0]
    st["reps"] = set(rep.values())
    st["n_rows_le"] = n_le
    st["Lam"], st["sd"] = pf["Lam"], pf["sd"]
    return st


def target_at(inp, st, e_pos, n_q):
    """target ไตรมาส (t, e] ด้วยน้ำหนัก PCA ที่ตรึง ณ t (ไม่ fit ใหม่) · คืน dict(df, B1)"""
    t_pos = st["t_pos"]
    rows = slice(t_pos + 1, e_pos + 1)
    Rw_df = inp.R.iloc[rows]
    U = st["U"]
    S = st["S"]
    Rw = Rw_df[U].to_numpy(float)
    X = Rw_df[S].to_numpy(float)
    fT = pc.factor_returns(X, st["pf"]["Lam"], st["pf"]["sd"], 0.5)
    fT_al = pc.factor_returns(X, st["Lam_al"], st["pf"]["sd"], 0.5)
    F3w = inp.F3.iloc[t_pos: e_pos + 1]
    fx = F3w["FX"].to_numpy(float)
    gold = F3w["GOLD"].to_numpy(float)
    f0 = st["f_le"][-1][None, :]
    Fp = np.column_stack([np.vstack([f0, fT]), fx])
    if st["variant"] == "W2":
        Fp = np.column_stack([Fp, gold])
    F3p = F3w[["MKT", "BOND", "GOLD", "FX"]].to_numpy(float)
    df = pd.DataFrame(index=U)
    for nm, drop in (("", False), ("_d1", True)):
        T, W = targets(Rw, Fp, st["fit_e"].coef, n_q, "resid", drop)
        df["T_PCA" + nm] = T
        T, _ = targets(Rw, F3p, st["fit_3a"].coef, n_q, "resid", drop)
        df["T_3a" + nm] = T
        T, _ = targets(Rw, None, None, n_q, "tot", drop)
        df["T_tot" + nm] = T
    df["n_tgt"] = np.isfinite(Rw).sum(axis=0)
    # B1: payoff (aligned / raw)
    out = dict(df=df)
    for nm, fq, state in (("al", fT_al, st["B1_al"]), ("raw", fT, st["B1_raw"])):
        ok = np.isfinite(fq).all(axis=1)
        if ok.sum() == 0:
            out["B1_" + nm] = (np.full(fq.shape[1], np.nan), np.nan, 0)
            continue
        Fq = (n_q / ok.sum()) * fq[ok].sum(axis=0)
        pi, m = b1_payoff(state[0], state[1], Fq, n_q)
        out["B1_" + nm] = (pi, m, int(ok.sum()))
    out["fT"] = fT
    out["fT_al"] = fT_al
    out["Fp"] = Fp
    out["Rw"] = Rw
    return out


# ───────────────────────── สถิติ (ข้อ 5) ─────────────────────────


def ic_q(sig, tgt, min_n=30):
    """Spearman (อันดับเฉลี่ยเมื่อเสมอ) บนกองที่มีทั้งคู่ · N < min_n → NaN · คืน (ic, n)"""
    s = np.asarray(sig, float)
    g = np.asarray(tgt, float)
    ok = np.isfinite(s) & np.isfinite(g)
    n = int(ok.sum())
    if n < min_n or np.unique(s[ok]).size < 2 or np.unique(g[ok]).size < 2:
        return np.nan, n
    return float(stats.spearmanr(s[ok], g[ok]).statistic), n


def nw_lag(Q):
    return int(math.floor(4 * (Q / 100.0) ** (2.0 / 9.0)))


def se_nw(x, L=None):
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    Q = len(x)
    if L is None:
        L = nw_lag(Q)
    d = x - x.mean()
    om = float(d @ d) / Q
    for l in range(1, L + 1):
        if l >= Q:
            break
        om += 2.0 * (1.0 - l / (L + 1.0)) * float(d[l:] @ d[:-l]) / Q
    om *= Q / (Q - 1.0)
    return math.sqrt(max(om, 0.0) / Q)


def t_dec(x):
    """คืน dict(Q, mean, s, se_iid, se_nw, L, t, df, p) · t = x̄/max(SE_iid, SE_NW) · p สองด้านที่ df = Q−1"""
    a = np.asarray(x, float)
    a = a[np.isfinite(a)]
    Q = len(a)
    if Q < 3:
        return dict(Q=Q, mean=np.nan, s=np.nan, se_iid=np.nan, se_nw=np.nan, L=nw_lag(max(Q, 1)), t=np.nan, df=max(Q - 1, 0), p=np.nan)
    m = float(a.mean())
    s = float(a.std(ddof=1))
    se_i = s / math.sqrt(Q)
    L = nw_lag(Q)
    se_n = se_nw(a, L)
    den = max(se_i, se_n)
    t = m / den if den > 0 else np.nan
    p = float(2.0 * stats.t.sf(abs(t), Q - 1)) if np.isfinite(t) else np.nan
    return dict(Q=Q, mean=m, s=s, se_iid=se_i, se_nw=se_n, L=L, t=t, df=Q - 1, p=p)


def halves(x, n1):
    """ค่าเฉลี่ยครึ่งแรก (n1 จุดแรก) / ครึ่งหลัง (ที่เหลือ) · ข้าม NaN"""
    a = np.asarray(x, float)
    h1, h2 = a[:n1], a[n1:]
    f = lambda v: float(np.nanmean(v)) if np.isfinite(v).any() else np.nan
    return f(h1), f(h2)


def series_stats(x, n1, q_min=12):
    """สถิติรวมของอนุกรมตัวตัดสิน · Q_eff < q_min → status na-insufficient (p = 1)"""
    d = t_dec(x)
    h1, h2 = halves(x, n1)
    d["x_h1"], d["x_h2"] = h1, h2
    d["status"] = "valid" if d["Q"] >= q_min else "na-insufficient"
    if d["status"] != "valid":
        d["p"] = 1.0
    xx = np.asarray(x, float)
    xx = xx[np.isfinite(xx)]
    d["lag1"] = float(np.corrcoef(xx[:-1], xx[1:])[0, 1]) if len(xx) > 3 else np.nan
    return d


def rank_normal(x):
    x = np.asarray(x, float)
    r = stats.rankdata(x, method="average")
    return stats.norm.ppf((r - 0.5) / len(x))


def winsor(x, lo=1, hi=99):
    x = np.asarray(x, float)
    a, b = np.percentile(x, [lo, hi])
    return np.clip(x, a, b)


def fm_slope(sig, tgt, min_n=30):
    """slope ของ target (winsorize 1/99) บน z = rank-normal(สัญญาณ) ในไตรมาสเดียว (หน่วยของ target ต่อ 1 หน่วย z)"""
    s, g = np.asarray(sig, float), np.asarray(tgt, float)
    ok = np.isfinite(s) & np.isfinite(g)
    if ok.sum() < min_n:
        return np.nan
    z = rank_normal(s[ok])
    y = winsor(g[ok])
    zc = z - z.mean()
    return float(zc @ (y - y.mean()) / (zc @ zc))


def quintile_spread(sig, tgt, codes, min_n=30):
    """แบ่ง 5 กลุ่มเท่ากันตามอันดับสัญญาณ (เสมอ → FundCode) · mean(target winsorize) กลุ่มสูงสุด − ต่ำสุด"""
    s, g = np.asarray(sig, float), np.asarray(tgt, float)
    ok = np.isfinite(s) & np.isfinite(g)
    if ok.sum() < min_n:
        return np.nan
    s, g, c = s[ok], winsor(g[ok]), np.asarray(codes)[ok]
    order = sorted(range(len(s)), key=lambda i: (s[i], c[i]))
    n = len(order)
    grp = np.empty(n, int)
    for pos, i in enumerate(order):
        grp[i] = min(4, (5 * pos) // n)
    return float(g[grp == 4].mean() - g[grp == 0].mean())


def hotelling(lams):
    """lams: Q x p · T² = Q λ̄'S⁻¹λ̄ · F = (Q−p)/(p(Q−1)) T² ~ F(p, Q−p) → dict"""
    L = np.asarray(lams, float)
    L = L[np.isfinite(L).all(axis=1)]
    Q, p = L.shape
    if Q <= p + 1:
        return dict(Q=Q, T2=np.nan, F=np.nan, p=np.nan, df1=p, df2=Q - p)
    lb = L.mean(axis=0)
    S = np.cov(L, rowvar=False, ddof=1)
    T2 = float(Q * lb @ np.linalg.solve(S, lb))
    F = (Q - p) / (p * (Q - 1.0)) * T2
    return dict(Q=Q, T2=T2, F=F, p=float(stats.f.sf(F, p, Q - p)), df1=p, df2=Q - p)


def perm_p(sigs, tgts, B=999, seed=SEED, min_n=30):
    """สลับสัญญาณข้ามกองภายในไตรมาส · mean IC เฉลี่ยข้ามไตรมาส · p = (1 + #{|mean*| ≥ |mean|})/(B+1)"""
    rng = np.random.default_rng(seed)
    zs, zt = [], []
    for s, g in zip(sigs, tgts):
        s, g = np.asarray(s, float), np.asarray(g, float)
        ok = np.isfinite(s) & np.isfinite(g)
        if ok.sum() < min_n or np.unique(s[ok]).size < 2 or np.unique(g[ok]).size < 2:
            continue
        a, b = stats.rankdata(s[ok]), stats.rankdata(g[ok])
        a, b = a - a.mean(), b - b.mean()
        zs.append(a / np.linalg.norm(a))
        zt.append(b / np.linalg.norm(b))
    if len(zs) == 0:
        return np.nan, np.nan
    obs = float(np.mean([a @ b for a, b in zip(zs, zt)]))
    acc = np.zeros(B)
    for a, b in zip(zs, zt):
        perm = np.argsort(rng.random((B, len(a))), axis=1)
        acc += a[perm] @ b
    mean_star = acc / len(zs)
    cnt = int((np.abs(mean_star) >= abs(obs) - 1e-15).sum())
    return obs, (1.0 + cnt) / (B + 1.0)


# ───────────────────────── MDE / BH / DSR ─────────────────────────


def mde_mult_nct(Q=15, tc=3.0, power=0.80):
    """ตัวคูณ σ_IC ของ IC ต่ำสุดที่ตรวจจับได้: noncentral t (df Q−1) · P(t > tc) = power · = δ/√Q"""
    from scipy.optimize import brentq
    df = Q - 1
    f = lambda d: stats.nct.sf(tc, df, d) - power
    d = brentq(f, 0.0, 15.0)
    return d / math.sqrt(Q)


def mde_mult_sim(Q=15, tc=3.0, power=0.80, n=20000, seed=SEED, rho=0.0):
    """จำลองภายใต้กฎจริง max(SE_iid, SE_NW) · IC ~ N(μ,1) iid (ρ>0 → AR(1)) · หา μ ที่ P(t_dec > tc) = power (bisection · random numbers คงที่)"""
    rng = np.random.default_rng(seed)
    Z = rng.standard_normal((n, Q))
    if rho > 0:
        for j in range(1, Q):
            Z[:, j] = rho * Z[:, j - 1] + math.sqrt(1 - rho ** 2) * Z[:, j]
    L = nw_lag(Q)

    def rate(mu):
        X = Z + mu
        m = X.mean(axis=1)
        s = X.std(axis=1, ddof=1)
        D = X - m[:, None]
        om = (D * D).sum(axis=1) / Q
        for l in range(1, L + 1):
            om += 2 * (1 - l / (L + 1.0)) * (D[:, l:] * D[:, :-l]).sum(axis=1) / Q
        om *= Q / (Q - 1.0)
        den = np.maximum(s / math.sqrt(Q), np.sqrt(np.maximum(om, 0) / Q))
        return float(np.mean(m / den > tc))

    lo, hi = 0.0, 3.0
    for _ in range(40):
        mid = (lo + hi) / 2
        if rate(mid) < power:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2, rate(0.0)


def bh_families(p, mode="bh", q=0.10):
    """BH / BY บนเวกเตอร์ p (ช่องที่ไม่ได้รันใส่ 1 มาแล้ว) · คืน (reject, adj p)"""
    p = np.asarray(p, float)
    if mode == "bh":
        return ts.bh(p, q)
    return l2.by(p, q)


def dsr_ic(x, n, direction=1.0):
    """DSR ของอนุกรมตัวตัดสิน (S010 ข้อ 9) · SR ต่อไตรมาส · V = 1/(Q−1) · skew / kurt (ไม่หัก 3) จากอนุกรมเอง"""
    a = direction * np.asarray(x, float)
    a = a[np.isfinite(a)]
    Q = len(a)
    if Q < 5 or a.std(ddof=1) == 0:
        return dict(sr=np.nan, sr0=np.nan, dsr=np.nan, skew=np.nan, kurt=np.nan)
    sr = float(a.mean() / a.std(ddof=1))
    g3 = float(stats.skew(a))
    g4 = float(stats.kurtosis(a, fisher=False))
    gam = 0.5772156649015329
    sr0 = math.sqrt(1.0 / (Q - 1)) * ((1 - gam) * stats.norm.ppf(1 - 1.0 / n) + gam * stats.norm.ppf(1 - 1.0 / (n * math.e)))
    den = 1 - g3 * sr + (g4 - 1) * sr ** 2 / 4.0
    z = (sr - sr0) * math.sqrt(Q - 1) / math.sqrt(den) if den > 0 else np.nan
    return dict(sr=sr, sr0=sr0, dsr=float(stats.norm.cdf(z)) if np.isfinite(z) else np.nan, skew=g3, kurt=g4)


def decide(t, x_mean, x_h1, x_h2, p_reject_bh, p_reject_by, tmin=3.0):
    """ข้อ 6: ผ่านเมื่อ t>3 · BH ปฏิเสธ · x̄>0 · ครึ่ง H1,H2 > 0 · เกรดตาม BY"""
    ok = bool(np.isfinite(t) and t > tmin and p_reject_bh and x_mean > 0 and x_h1 > 0 and x_h2 > 0)
    if not ok:
        return False, "ไม่ผ่าน — power ไม่พอ / ไม่มีหลักฐาน"
    return True, "ผ่าน (ทน BY)" if p_reject_by else "ผ่าน (BH เท่านั้น)"


# ───────────────────────── trials.csv (ข้อ 10) ─────────────────────────
HEADER = ("trial_id,row_kind,parent_id,run_at,spec_file,line,signal,target,universe,params,freq,period_start,period_end,rf_source,"
          "n_periods,n_funds_median,n_funds_min,stat_name,estimate,sd_series,se_iid,se_nw,nw_lag,t_dec,df,p_two,has_inference,"
          "expected_sign,sign_ok,est_h1,est_h2,halves_ok,ic_min80_exante,ic_min80_realized,skew,kurt,dsr_n20,dsr_n122,"
          "counts_mode_A,counts_mode_B,n_trials_cumulative,n_trials_cumulative_B,n_combined,n_combined_B,status,data_sha256,lib_sha256,run_dir,notes").split(",")
ALLOWED_KIND = {"main", "robustness", "monthly", "whatif", "bugfix_rerun", "invalidate", "forward"}
ALLOWED_STATUS = {"valid", "invalid-bug", "na-insufficient"}


def row_counts(row):
    """(counts_mode_A, counts_mode_B) ตามข้อ 10.1"""
    k = row["row_kind"]
    a = 1 if k in ("main", "monthly", "whatif", "bugfix_rerun") else 0
    hi = str(row.get("has_inference", "")) in ("1", "1.0", "True", "true")
    b = 1 if (hi and k != "invalidate") else 0
    return a, b


def _fmt(v):
    if v is None:
        return ""
    if isinstance(v, (float, np.floating)):
        return "" if not np.isfinite(v) else repr(float(v))
    if isinstance(v, (bool, np.bool_)):
        return "1" if v else "0"
    if isinstance(v, (int, np.integer)):
        return str(int(v))
    return str(v).replace("\n", " ").replace("\r", " ")


def read_trials(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.reader(f))


def append_trials(path, rows, backup_dir, now=None):
    """append แบบ text · header ต้องตรง · backup ก่อน · ตัวนับสะสม A/B จากแถวเดิม · ตรวจ prefix + จำนวนบรรทัดหลังเขียน (ผิด → คืนจาก backup + raise)
    rows: list ของ dict ที่คีย์ = HEADER ทุกตัว (counts_mode_*/n_trials_*/n_combined* ถูกคำนวณที่นี่ — ถ้าส่งมาต้องตรง)"""
    path = Path(path)
    backup_dir = Path(backup_dir)
    for r in rows:
        if set(r.keys()) != set(HEADER):
            raise ValueError(f"key ไม่ตรง header: {set(r.keys()) ^ set(HEADER)}")
        if r["row_kind"] not in ALLOWED_KIND:
            raise ValueError(f"row_kind ไม่อนุญาต: {r['row_kind']}")
        if r["status"] not in ALLOWED_STATUS:
            raise ValueError(f"status ไม่อนุญาต: {r['status']}")
    existed = path.exists()
    cumA = cumB = 0
    n_lines0 = 0
    backup = None
    old_bytes = b""
    if existed:
        old_bytes = path.read_bytes()
        data = read_trials(path)
        if data[0] != HEADER:
            raise ValueError("header ของ trials.csv ไม่ตรง spec 10.1")
        ia, ib = HEADER.index("counts_mode_A"), HEADER.index("counts_mode_B")
        cumA = sum(int(r[ia]) for r in data[1:])
        cumB = sum(int(r[ib]) for r in data[1:])
        n_lines0 = len(data)
        backup_dir.mkdir(parents=True, exist_ok=True)
        ts_ = (now or datetime.now()).strftime("%Y%m%dT%H%M%S")
        backup = backup_dir / f"trials.backup_{ts_}.csv"
        k = 0
        while backup.exists():
            k += 1
            backup = backup_dir / f"trials.backup_{ts_}_{k}.csv"
        shutil.copy2(path, backup)
        assert backup.read_bytes() == old_bytes
    out = []
    for r in rows:
        a, b = row_counts(r)
        for key, v in (("counts_mode_A", a), ("counts_mode_B", b)):
            if str(r[key]) not in ("", str(v)):
                raise ValueError(f"{key} ที่ส่งมา ({r[key]}) ไม่ตรงกฎ ({v})")
        cumA += a
        cumB += b
        rr = dict(r)
        rr.update(counts_mode_A=a, counts_mode_B=b, n_trials_cumulative=cumA, n_trials_cumulative_B=cumB,
                  n_combined=N_QUANT_PRIOR + cumA, n_combined_B=N_QUANT_PRIOR + cumB)
        out.append([_fmt(rr[h]) for h in HEADER])
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f, quoting=csv.QUOTE_MINIMAL, lineterminator="\n")
        if not existed:
            w.writerow(HEADER)
        for line in out:
            w.writerow(line)
    new_bytes = path.read_bytes()
    exp = (n_lines0 if existed else 1) + len(out)
    ok = new_bytes.startswith(old_bytes) and len(read_trials(path)) == exp
    if not ok:
        if existed:
            shutil.copy2(backup, path)
        else:
            path.unlink()
        raise RuntimeError("ตรวจหลัง append ไม่ผ่าน — คืนไฟล์จาก backup")
    return dict(backup=str(backup) if backup else None, n_written=len(out), cumA=cumA, cumB=cumB)


# ───────────────────────── J1 · ตัดสินระดับ family · เลือกช่องเงื่อนไข ─────────────────────────


def j1_slopes(X, y, min_n=30):
    """OLS ของ winsorize(y) บน 1 + rank-normal z ของสัญญาณ 4 ตัว (เฉพาะกองที่มีครบ 4 สัญญาณและ target) → slope 4 ตัว"""
    ok = X.notna().all(axis=1) & y.notna()
    if int(ok.sum()) < min_n:
        return np.full(X.shape[1], np.nan)
    Z = np.column_stack([rank_normal(X.loc[ok, c].to_numpy(float)) for c in X.columns])
    A = np.column_stack([np.ones(int(ok.sum())), Z])
    return np.linalg.lstsq(A, winsor(y[ok].to_numpy(float)), rcond=None)[0][1:]


def decide_family(order, p, tstat, xbar, h1, h2, j1_names, q=0.10, tmin=3.0):
    """BH/BY บน family `order` (p ช่องที่ไม่ได้รัน = 1) · ตัดสิน trial เดี่ยวด้วย p ของ j1_names = 1 (S011 ข้อ 3) ·
    pass_if_J1_real_p = บรรยาย · แถวของ j1_names รายงาน 'ร่วมมีนัย' ด้วย p จริง"""
    pr = np.array([1.0 if not np.isfinite(p.get(s, np.nan)) else float(p[s]) for s in order])
    pi = pr.copy()
    for i, s in enumerate(order):
        if s in j1_names:
            pi[i] = 1.0
    rej_i, _ = bh_families(pi, "bh", q)
    by_i, _ = bh_families(pi, "by", q)
    rej_r, adj_r = bh_families(pr, "bh", q)
    by_r, _ = bh_families(pr, "by", q)
    rows = []
    for i, s in enumerate(order):
        tt, xm, a, b = tstat.get(s, np.nan), xbar.get(s, np.nan), h1.get(s, np.nan), h2.get(s, np.nan)
        if s in j1_names:
            rows.append(dict(slot=s, p_used=pr[i], bh_reject=bool(rej_r[i]), by_reject=bool(by_r[i]), passed=False,
                             grade="ร่วมมีนัย" if rej_r[i] else "ไม่มีนัย", passed_if_J1_real_p=False, p_J1_used_for_individual=1))
            continue
        ok, grade = decide(tt, xm, a, b, rej_i[i], by_i[i], tmin) if np.isfinite(tt) else (False, "ไม่ผ่าน — power ไม่พอ / ไม่มีหลักฐาน")
        ok2, _ = decide(tt, xm, a, b, rej_r[i], by_r[i], tmin) if np.isfinite(tt) else (False, "")
        rows.append(dict(slot=s, p_used=pi[i], bh_reject=bool(rej_i[i]), by_reject=bool(by_i[i]), passed=ok, grade=grade,
                         passed_if_J1_real_p=ok2, p_J1_used_for_individual=1))
    return pd.DataFrame(rows)


def select_conditional(cands):
    """cands: list ของ dict(slot, t, passed, pca) ตามลำดับตาราง 4.1 (ไม่รวม J1) → (monthly ≤2 ตัว |t| สูงสุด · anchor what-if หรือ None)"""
    passed = [c for c in cands if c["passed"]]
    order = sorted(range(len(passed)), key=lambda i: (-abs(passed[i]["t"]), i))
    monthly = [passed[i]["slot"] for i in order[:2]]
    pc_ = [c for c in passed if c["pca"]]
    o2 = sorted(range(len(pc_)), key=lambda i: (-abs(pc_[i]["t"]), i))
    anchor = pc_[o2[0]]["slot"] if o2 else None
    return monthly, anchor
