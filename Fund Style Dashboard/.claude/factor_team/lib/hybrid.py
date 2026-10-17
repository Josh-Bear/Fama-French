"""hybrid — ④a = ③a + residual PC (S002 ข้อ 3.④ · factor return ไม่หัก α̂)"""
import numpy as np
import pandas as pd

from nfactors import bai_ng_ic
from pca import factor_returns, sign_fix
from regress import fit_funds, CommonFactors, lag_stack


def residual_pc(R, F3a, mask_train, funds, kmax=5, L=4):
    """R (T x N ทุกกอง) · funds = balanced train ตัดซ้ำ · ê = residual Dimson บน ③a (train)
    → dict(W, s, coef, k_res, eig, funds)"""
    fit = fit_funds(R, F3a, mask_train, min_obs=50, L=L, funds=funds)
    E = fit.resid[np.asarray(mask_train, bool)]
    ok = np.isfinite(E).all(axis=1)
    E = E[ok]
    T, N = E.shape
    s = E.std(axis=0, ddof=1)
    Z = (E - E.mean(axis=0)) / E.std(axis=0, ddof=0)
    w, V = np.linalg.eigh(Z.T @ Z / T)
    o = np.argsort(w)[::-1]
    w, V = w[o], V[:, o]
    k_res = bai_ng_ic(w, N, T, kmax, "p2")
    W = sign_fix(V[:, :k_res]) if k_res > 0 else np.zeros((N, 0))
    return dict(W=W, s=s, coef=fit.coef, k_res=k_res, eig=w, funds=list(funds), T=T, fit=fit)


def hybrid_factor(R, F3a, W, s, coef, funds, min_frac=0.5):
    """u_i,t = x − Σ(b̂0 f_t + b̂1 f_{t−1}) (ไม่หัก α̂) → g_t = (W_A'W_A)^{-1} W_A' (u_A,t / s_A) · สูตรเดียวทุกช่วง"""
    k = W.shape[1]
    D = lag_stack(F3a.to_numpy(float))
    X = R[funds].to_numpy(float)
    U = np.full_like(X, np.nan)
    for j in range(len(funds)):
        b = coef[j, 1:]
        U[:, j] = X[:, j] - D @ b
    if k == 0:
        return pd.DataFrame(index=R.index, columns=[])
    g = factor_returns(U, W, sigma=s, min_frac=min_frac)
    return pd.DataFrame(g, index=R.index, columns=[f"RPC{i + 1}" for i in range(k)])
