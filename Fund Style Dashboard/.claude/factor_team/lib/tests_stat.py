"""tests_stat — GRS · Pesaran-Yamagata · BH · spanning · VIF · bootstrap"""
import numpy as np
from scipy import stats

from regress import ols_hac, lag_stack


def grs(Rp, X):
    """GRS (Gibbons-Ross-Shanken 1989) · Rp (T x N พอร์ต) · X (T x L regressor ทุกตัวรวม lag) ·
    Σ̂ = MLE (หาร T) ของ residual · Ω̂ = MLE covariance ของ X · F=((T-N-L)/N) α'Σ⁻¹α/(1+μ'Ω⁻¹μ) ~ F(N, T-N-L)
    (เทียบเท่ารูปที่ใช้ Σ dof T-L-1 คูณ T/(T-L-1)) · คืน dict(F,p,N,L,T,dof2,alpha)"""
    Rp = np.asarray(Rp, float)
    X = np.asarray(X, float)
    T, N = Rp.shape
    L = X.shape[1]
    Xc = np.column_stack([np.ones(T), X])
    B = np.linalg.lstsq(Xc, Rp, rcond=None)[0]
    E = Rp - Xc @ B
    alpha = B[0]
    Sig = E.T @ E / T
    mu = X.mean(axis=0)
    Xd = X - mu
    Om = Xd.T @ Xd / T
    dof2 = T - N - L
    if dof2 <= 0:
        return dict(F=np.nan, p=np.nan, N=N, L=L, T=T, dof2=dof2, alpha=alpha)
    qa = float(alpha @ np.linalg.solve(Sig, alpha))
    qm = float(mu @ np.linalg.solve(Om, mu))
    Fv = dof2 / N * qa / (1.0 + qm)
    return dict(F=Fv, p=float(stats.f.sf(Fv, N, dof2)), N=N, L=L, T=T, dof2=dof2, alpha=alpha)


def pesaran_yamagata(t, resid, T, m, p=0.10, f="N"):
    """Pesaran-Yamagata (2024) ฉบับต้นฉบับ · t (N) = t-stat ของ α̂_i (OLS) · resid (T x N) · m = จำนวน regressor (ไม่รวมค่าคงที่)
    v=T-m-1 (>4) · c_p(N)=Φ⁻¹(1−p/(2f(N))), f(N)=N · ρ̄² = [2/(N(N−1))] Σ_{i<j} ρ̂²_ij·I[√v|ρ̂_ij| > c_p] ·
    J=N^{-1/2} Σ[t²−v/(v−2)] / sqrt(2((v−1)/(v−4))(v/(v−2))²(1+(N−1)ρ̄²)) · p ข้างเดียว N(0,1)"""
    t = np.asarray(t, float)
    resid = np.asarray(resid, float)
    N = len(t)
    v = T - m - 1
    if v <= 4:
        return dict(J=np.nan, p=np.nan, rho2=np.nan, Nrho2=np.nan, N=N, T=T, v=v, c=np.nan)
    fN = N if f == "N" else f(N)
    c = stats.norm.ppf(1.0 - p / (2.0 * fN))
    C = np.corrcoef(resid, rowvar=False)
    iu = np.triu_indices(N, 1)
    r = C[iu]
    keep = np.sqrt(v) * np.abs(r) > c
    rho2 = float(2.0 / (N * (N - 1)) * np.sum(r[keep] ** 2))
    num = np.sum(t ** 2 - v / (v - 2.0)) / np.sqrt(N)
    den = np.sqrt(2.0 * ((v - 1.0) / (v - 4.0)) * (v / (v - 2.0)) ** 2 * (1.0 + (N - 1.0) * rho2))
    J = float(num / den)
    return dict(J=J, p=float(stats.norm.sf(J)), rho2=rho2, Nrho2=float((N - 1) * rho2), N=N, T=T, v=v, c=float(c))


def py_extended(t, Ti, resid_df, m, p=0.10, min_overlap=52):
    """ฉบับขยาย (sensitivity · ไม่มีทฤษฎีรองรับ): v_i=T_i−m−1 · ρ̂_ij จากคู่ที่ทับกัน ≥ min_overlap · เกณฑ์ √v_ij|ρ|>c_p"""
    t = np.asarray(t, float)
    Ti = np.asarray(Ti, float)
    N = len(t)
    v = Ti - m - 1
    ok = v > 4
    E = np.asarray(resid_df, float)
    fN = N
    c = stats.norm.ppf(1.0 - p / (2.0 * fN))
    M = np.isfinite(E).astype(float)
    E0 = np.where(np.isfinite(E), E, 0.0)
    n_ij = M.T @ M
    Sij = E0.T @ E0
    Si = E0.T @ M  # Σ_t e_i over overlap with j
    Sii = (E0 ** 2).T @ M
    with np.errstate(divide="ignore", invalid="ignore"):
        cov = Sij / n_ij - (Si / n_ij) * (Si.T / n_ij)
        vi = Sii / n_ij - (Si / n_ij) ** 2
        vj = vi.T
        rho = cov / np.sqrt(vi * vj)
    iu = np.triu_indices(N, 1)
    r = rho[iu]
    nij = n_ij[iu]
    vij = nij - m - 1
    valid = (nij >= min_overlap) & np.isfinite(r)
    keep = valid & (np.sqrt(np.maximum(vij, 0)) * np.abs(r) > c)
    rho2 = float(2.0 / (N * (N - 1)) * np.sum(r[keep] ** 2))
    vv = v[ok]
    tt = t[ok]
    z = (tt ** 2 - vv / (vv - 2.0)) / np.sqrt(2.0 * ((vv - 1.0) / (vv - 4.0)) * (vv / (vv - 2.0)) ** 2)
    J = float(z.sum() / np.sqrt(ok.sum()) / np.sqrt(1.0 + (N - 1.0) * rho2))
    return dict(J=J, p=float(stats.norm.sf(J)), rho2=rho2, Nrho2=float((N - 1) * rho2), N=int(ok.sum()), T=float(np.mean(Ti)))


def bh(pvals, q=0.10):
    """Benjamini-Hochberg step-up · คืน (reject bool, adj p)"""
    p = np.asarray(pvals, float)
    n = len(p)
    o = np.argsort(p, kind="stable")
    ps = p[o]
    adj = ps * n / (np.arange(n) + 1.0)
    adj = np.minimum.accumulate(adj[::-1])[::-1]
    adj = np.minimum(adj, 1.0)
    out_adj = np.empty(n)
    out_adj[o] = adj
    return out_adj <= q, out_adj


def spanning(fA, fB, rows, L=4):
    """factor ของ A ~ factor ของ B (Dimson lag 1 · HAC · แถว rows) → รายตัวของ A: α, t_α, R², และ Wald joint α=0 (HAC ร่วมทุกสมการ)
    fA, fB: DataFrame index เดียวกัน (lag สร้างจาก index ทั้งชุด) · rows: boolean"""
    DB = lag_stack(fB.to_numpy(float))
    YA = fA.to_numpy(float)
    rows = np.asarray(rows, bool)
    ok = rows & np.isfinite(DB).all(axis=1) & np.isfinite(YA).all(axis=1)
    X = np.column_stack([np.ones(ok.sum()), DB[ok]])
    Y = YA[ok]
    n, p = X.shape
    KA = Y.shape[1]
    A = np.linalg.inv(X.T @ X)
    B = A @ X.T @ Y
    E = Y - X @ B
    # HAC ร่วมของ h_t = [e_1t x_t ; ... ; e_KA,t x_t]
    H = np.hstack([X * E[:, [k]] for k in range(KA)])
    S = H.T @ H
    for l in range(1, L + 1):
        G = H[l:].T @ H[:-l]
        S = S + (1 - l / (L + 1.0)) * (G + G.T)
    big = np.kron(np.eye(KA), A)
    V = big @ S @ big.T
    idx = np.arange(KA) * p
    a = B[0]
    Va = V[np.ix_(idx, idx)]
    wald = float(a @ np.linalg.solve(Va, a))
    r2 = 1 - (E ** 2).sum(0) / ((Y - Y.mean(0)) ** 2).sum(0)
    return dict(alpha=a, t_alpha=a / np.sqrt(np.diag(Va)), r2=r2, wald=wald, p=float(stats.chi2.sf(wald, KA)),
                df=KA, n=n)


def vif(X):
    """VIF_j = 1/(1−R²_j) (ถดถอยคอลัมน์ j บนที่เหลือ + ค่าคงที่)"""
    X = np.asarray(X, float)
    n, k = X.shape
    out = np.empty(k)
    for j in range(k):
        y = X[:, j]
        Z = np.column_stack([np.ones(n), np.delete(X, j, axis=1)])
        b = np.linalg.lstsq(Z, y, rcond=None)[0]
        e = y - Z @ b
        r2 = 1 - e @ e / ((y - y.mean()) ** 2).sum()
        out[j] = 1.0 / (1.0 - r2)
    return out


def bootstrap_median(S, pol, pairs=(), n_boot=2000, seed=20261015, q=(2.5, 97.5)):
    """bootstrap ใส่คืนภายใน policy · S (Nfunds x C) สถิติรายกอง · pol array 'E','F','O' ·
    คืน dict group→(CI median ของแต่ละคอลัมน์ (2 x C), CI ส่วนต่างจับคู่ median(col_a)−median(col_b) ตาม pairs (2 x P))
    group ∈ E,F,O,ALL · ใช้ index ที่สุ่มชุดเดียวกันทุกคอลัมน์ในรอบเดียวกัน"""
    S = np.asarray(S, float)
    pol = np.asarray(pol)
    rng = np.random.default_rng(seed)
    groups = {g: np.where(pol == g)[0] for g in ("E", "F", "O")}
    C = S.shape[1]
    P = len(pairs)
    med = {g: np.full((n_boot, C), np.nan) for g in ("E", "F", "O", "ALL")}
    dif = {g: np.full((n_boot, P), np.nan) for g in ("E", "F", "O", "ALL")}
    for b in range(n_boot):
        draw = {g: rng.choice(ix, size=len(ix), replace=True) for g, ix in groups.items()}
        draw["ALL"] = np.concatenate([draw["E"], draw["F"], draw["O"]])
        for g, ix in draw.items():
            m = np.nanmedian(S[ix], axis=0)
            med[g][b] = m
            for pi, (a, c) in enumerate(pairs):
                dif[g][b, pi] = m[a] - m[c]
    out = {}
    for g in med:
        out[g] = (np.nanpercentile(med[g], q, axis=0), np.nanpercentile(dif[g], q, axis=0) if P else None)
    return out


def block_indices(T, B, block, rng):
    """ดัชนีเวลา moving-block (ชุดเดียวต่อรอบ ใช้ร่วมทุกกอง) → (B x T)"""
    nblk = -(-T // block)
    starts = rng.integers(0, T - block + 1, size=(B, nblk))
    return (starts[:, :, None] + np.arange(block)[None, None, :]).reshape(B, -1)[:, :T]


def p_boot_value(J, Jstar):
    """p_boot = (1 + #{J* ≥ J}) / (B + 1)"""
    Jstar = np.asarray(Jstar, float)
    return float((1 + np.sum(Jstar >= J)) / (len(Jstar) + 1))


def py_null_bootstrap(R, provider, funds, mask, B=999, block=4, seed=20261015, chunk=100):
    """PY null bootstrap (S004 ข้อ 4): fixed-design · บังคับ α=0 · ê* จาก moving-block ตามเวลา (ชุดเดียวทุกกอง) ·
    คืน dict(J, p, p_boot, size05, sd_J, B, mean_alpha_star, rho2, Nrho2, N, T)"""
    from regress import fit_funds
    funds = list(funds)
    mask = np.asarray(mask, bool)
    T = int(mask.sum())
    fit = fit_funds(R, provider, mask, 50, funds=funds)
    if not fit.ok.all() or (fit.n != T).any():
        raise ValueError("py_null_bootstrap: ทุกกองต้องมีครบทุกแถวของ mask")
    N = len(funds)
    mm = 2 * provider.K
    E = fit.resid[mask]
    obs = pesaran_yamagata(fit.t_alpha_ols, E, T, mm)
    fitted = np.empty((T, N))
    Xs, pinv, a00 = [], [], []
    for j, code in enumerate(funds):
        X = np.column_stack([np.ones(T), provider.design(code)[mask]])
        Xs.append(X)
        pinv.append(np.linalg.pinv(X))
        a00.append(np.linalg.inv(X.T @ X)[0, 0])
        fitted[:, j] = X[:, 1:] @ fit.coef[j][1:]  # บังคับ α = 0 (ไม่รวมค่าคงที่)
    p_cols = Xs[0].shape[1]
    rng = np.random.default_rng(seed)
    idxs = block_indices(T, B, block, rng)
    Js, ps = np.empty(B), np.empty(B)
    asum = 0.0
    for c0 in range(0, B, chunk):
        ib = idxs[c0:c0 + chunk]
        nb = len(ib)
        Ys = fitted[None] + E[ib]
        tst = np.empty((nb, N))
        Rst = np.empty((nb, T, N))
        for j in range(N):
            Y = Ys[:, :, j].T
            cf = pinv[j] @ Y
            res = Y - Xs[j] @ cf
            s2 = (res ** 2).sum(0) / (T - p_cols)
            tst[:, j] = cf[0] / np.sqrt(a00[j] * s2)
            Rst[:, :, j] = res.T
            asum += float(cf[0].sum())
        for b in range(nb):
            r = pesaran_yamagata(tst[b], Rst[b], T, mm)
            Js[c0 + b], ps[c0 + b] = r["J"], r["p"]
    return dict(J=obs["J"], p=obs["p"], p_boot=p_boot_value(obs["J"], Js), size05=float(np.mean(ps < 0.05)),
                sd_J=float(np.std(Js, ddof=1)), B=B, mean_alpha_star=asum / (B * N), rho2=obs["rho2"], Nrho2=obs["Nrho2"],
                N=N, T=T)
