"""scorecard — ตารางคะแนนกลาง 6 ข้อ (สรุปสถิติ · ความเสถียร · การตีความ)"""
import numpy as np
import pandas as pd


def summ(x):
    """median, q25, q75, IQR, n (ข้าม NaN)"""
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    if len(x) == 0:
        return dict(n=0, median=np.nan, q25=np.nan, q75=np.nan, iqr=np.nan)
    q25, med, q75 = np.percentile(x, [25, 50, 75])
    return dict(n=len(x), median=med, q25=q25, q75=q75, iqr=q75 - q25)


def score_model(fit, r2oos, pol, subset=None, k=None, div_flag=None):
    """สรุปข้อ 1–4 ต่อ policy (E/F/O/ALL) · fit = FitResult (train) · r2oos รายกอง · pol array · subset boolean (ตัวเลือก)"""
    pol = np.asarray(pol)
    if subset is None:
        subset = np.ones(len(pol), bool)
    rows = []
    for g in ("E", "F", "O", "ALL"):
        m = subset & (pol == g if g != "ALL" else np.ones(len(pol), bool))
        ok = m & fit.ok
        a = fit.alpha[ok]
        sa = summ(fit.adj_r2[ok])
        so = summ(r2oos[ok])
        gap = summ((fit.r2[ok] - r2oos[ok]))
        nd = ok.copy()
        if div_flag is not None:
            nd = ok & ~np.asarray(div_flag, bool)
        rows.append(dict(policy=g, n=int(ok.sum()), K=fit.K,
                         adjr2_med=sa["median"], adjr2_q25=sa["q25"], adjr2_q75=sa["q75"], adjr2_iqr=sa["iqr"],
                         r2oos_med=so["median"], r2oos_q25=so["q25"], r2oos_q75=so["q75"], r2oos_iqr=so["iqr"],
                         r2gap_med=gap["median"],
                         mean_abs_alpha_pct=float(np.mean(np.abs(a)) * 5200) if len(a) else np.nan,
                         signed_mean_alpha_pct=float(np.mean(a) * 5200) if len(a) else np.nan,
                         mean_abs_alpha_nodiv_pct=float(np.mean(np.abs(fit.alpha[nd])) * 5200) if nd.sum() else np.nan,
                         bic_med=float(np.nanmedian(fit.bic[ok])) if ok.sum() else np.nan,
                         n_obs_med=float(np.median(fit.n[ok])) if ok.sum() else np.nan))
    return pd.DataFrame(rows)


def _corr(a, b):
    ok = np.isfinite(a) & np.isfinite(b)
    if ok.sum() < 3 or np.std(a[ok]) == 0 or np.std(b[ok]) == 0:
        return np.nan
    return float(np.corrcoef(a[ok], b[ok])[0, 1])


def stability_halves(beta1, beta2):
    """r_k = corr ข้ามกองของ β̂_ik ระหว่างครึ่งแรก/หลัง · beta (N x K) → array K"""
    return np.array([_corr(beta1[:, k], beta2[:, k]) for k in range(beta1.shape[1])])


def stability_disattenuated(beta1, se1, beta2, se2, rel_min=0.10):
    """rel_h,k = (var_i(β̂) − mean_i(SE²))/var_i(β̂) · r*_k = r_k/√(rel1·rel2) · rel ใด < rel_min → r*=NaN (N/A)
    คืน dict(r, rel1, rel2, r_star) (array K)"""
    K = beta1.shape[1]
    r = stability_halves(beta1, beta2)
    out = dict(r=r, rel1=np.full(K, np.nan), rel2=np.full(K, np.nan), r_star=np.full(K, np.nan))
    for k in range(K):
        rels = []
        for b, s in ((beta1, se1), (beta2, se2)):
            ok = np.isfinite(b[:, k]) & np.isfinite(s[:, k])
            v = np.var(b[ok, k], ddof=1)
            rels.append((v - np.mean(s[ok, k] ** 2)) / v if v > 0 else np.nan)
        out["rel1"][k], out["rel2"][k] = rels
        if np.all(np.isfinite(rels)) and min(rels) >= rel_min and np.isfinite(r[k]):
            out["r_star"][k] = r[k] / np.sqrt(rels[0] * rels[1])
    return out


def stability_ceiling(beta_odd, beta_even):
    """r^ceil_k = corr ข้ามกองของ β̂ จากสัปดาห์คี่ vs คู่"""
    return stability_halves(beta_odd, beta_even)


def stability_rolling(beta_windows, beta_full):
    """beta_windows (W x N x K) · beta_full (N x K) → (median, min) ของ corr ข้ามกองต่อ factor"""
    W, N, K = beta_windows.shape
    cs = np.array([[_corr(beta_windows[w, :, k], beta_full[:, k]) for k in range(K)] for w in range(W)])
    return np.nanmedian(cs, axis=0), np.nanmin(cs, axis=0)


def interpret(fac, ref, min_obs=100):
    """ต่อ factor: 3 อันดับ |corr| สูงสุดกับชุดอ้างอิง ref (DataFrame index เดียวกัน) + ชื่อตามเกณฑ์ 0.7 / 0.5 ·
    คืน DataFrame(factor, rank, ref, corr, label)"""
    rows = []
    for c in fac.columns:
        cc = {}
        for r in ref.columns:
            d = pd.concat([fac[c], ref[r]], axis=1).dropna()
            if len(d) >= min_obs and d.iloc[:, 0].std() > 0 and d.iloc[:, 1].std() > 0:
                cc[r] = float(d.iloc[:, 0].corr(d.iloc[:, 1]))
        top = sorted(cc.items(), key=lambda kv: (-abs(kv[1]), kv[0]))[:3]
        mx = abs(top[0][1]) if top else np.nan
        label = ("≈ " + top[0][0]) if mx >= 0.7 else (("คล้าย " + top[0][0]) if mx >= 0.5 else "ไม่มีชื่อ")
        for i, (r, v) in enumerate(top):
            rows.append(dict(factor=c, rank=i + 1, ref=r, corr=v, label=label if i == 0 else ""))
    return pd.DataFrame(rows)


def canonical_corr(A, B):
    """canonical correlations ระหว่างคอลัมน์ของ A และ B (แถวที่ไม่ NaN ทั้งคู่)"""
    A = np.asarray(A, float)
    B = np.asarray(B, float)
    ok = np.isfinite(A).all(1) & np.isfinite(B).all(1)
    A, B = A[ok] - A[ok].mean(0), B[ok] - B[ok].mean(0)
    qa, _ = np.linalg.qr(A)
    qb, _ = np.linalg.qr(B)
    return np.sort(np.linalg.svd(qa.T @ qb, compute_uv=False))[::-1]


def port_alpha(Rp, X):
    """α̂ ต่อพอร์ต (OLS บน [1, X]) · Rp (T x N) X (T x L) · คืน array N (ต่อสัปดาห์)"""
    Rp = np.asarray(Rp, float)
    X = np.asarray(X, float)
    Xc = np.column_stack([np.ones(len(X)), X])
    return np.linalg.lstsq(Xc, Rp, rcond=None)[0][0]
