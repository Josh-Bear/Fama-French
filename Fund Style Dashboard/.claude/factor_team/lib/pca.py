"""pca — PCA / EM-PCA / factor returns (ไม่หักค่าเฉลี่ย)"""
import numpy as np


def sign_fix(L):
    """กลับเครื่องหมายคอลัมน์ให้ผลรวม >= 0"""
    L = np.array(L, float, copy=True)
    s = np.where(L.sum(axis=0) < 0, -1.0, 1.0)
    return L * s


def pca_fit(X, k, kind="corr"):
    """X (T x N) ครบ · kind corr: z=(x-μ)/σ · cov: d=x-μ · → (Λ N x k ‖λ‖=1, μ, σ, eig ทั้งหมด จาก Z'Z/T)"""
    X = np.asarray(X, float)
    T = X.shape[0]
    mu = X.mean(axis=0)
    sd = X.std(axis=0, ddof=0)
    Z = (X - mu) / sd if kind == "corr" else (X - mu)
    w, V = np.linalg.eigh(Z.T @ Z / T)
    order = np.argsort(w)[::-1]
    w, V = w[order], V[:, order]
    return sign_fix(V[:, :k]), mu, sd, w


def em_pca(X, k, tol=1e-6, maxit=1000):
    """Stock-Watson EM บน z (μ,σ จากแถวที่มีค่า): เติม 0 → SVD rank k → แทนค่าที่ขาด → วนจน
    ‖Δ‖_F/‖Z_filled‖_F < tol หรือ maxit · ไม่สุ่ม · → (Λ N x k, μ, σ, n_iter, converged)"""
    X = np.asarray(X, float)
    miss = np.isnan(X)
    mu = np.nanmean(X, axis=0)
    sd = np.nanstd(X, axis=0, ddof=0)
    Z = (X - mu) / sd
    Zf = np.where(miss, 0.0, Z)
    conv = False
    it = 0
    for it in range(1, maxit + 1):
        U, S, Vt = np.linalg.svd(Zf, full_matrices=False)
        Zh = (U[:, :k] * S[:k]) @ Vt[:k]
        Zn = np.where(miss, Zh, Z)
        d = np.linalg.norm(Zn - Zf)
        den = np.linalg.norm(Zn)
        Zf = Zn
        if den > 0 and d / den < tol:
            conv = True
            break
    U, S, Vt = np.linalg.svd(Zf, full_matrices=False)
    return sign_fix(Vt[:k].T), mu, sd, it, conv


def factor_returns(X_raw, Lam, sigma=None, min_frac=0.5):
    """f_t = (Λ_A'Λ_A)^{-1} Λ_A' (x_A,t/σ_A) · A = กองใน Λ ที่มีค่าที่ t · **ไม่หัก μ** ·
    < min_frac ของกองใน Λ → NaN · sigma=None → ไม่หารด้วย σ (แบบ covariance)"""
    X = np.asarray(X_raw, float)
    Lam = np.asarray(Lam, float)
    T, N = X.shape
    k = Lam.shape[1]
    out = np.full((T, k), np.nan)
    Xs = X if sigma is None else X / np.asarray(sigma, float)
    for t in range(T):
        a = np.isfinite(Xs[t])
        if a.sum() < min_frac * N or a.sum() < k:
            continue
        La = Lam[a]
        out[t] = np.linalg.lstsq(La, Xs[t, a], rcond=None)[0]
    return out
