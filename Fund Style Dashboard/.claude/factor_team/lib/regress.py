"""regress — OLS + Dimson lag 1 + HAC Newey-West (Bartlett) + OOS"""
import numpy as np
import pandas as pd


def ols_hac(y, X, L=4):
    """OLS + SE แบบ HAC (Bartlett, ไม่ปรับ small-sample = use_correction False) · X รวมค่าคงที่แล้ว"""
    y = np.asarray(y, float)
    X = np.asarray(X, float)
    n, p = X.shape
    XtX = X.T @ X
    try:
        A = np.linalg.inv(XtX)
    except np.linalg.LinAlgError:
        A = np.linalg.pinv(XtX)
    coef = A @ (X.T @ y)
    e = y - X @ coef
    Xe = X * e[:, None]
    S = Xe.T @ Xe
    for l in range(1, L + 1):
        if l >= n:
            break
        G = Xe[l:].T @ Xe[:-l]
        S = S + (1.0 - l / (L + 1.0)) * (G + G.T)
    V = A @ S @ A
    ssr = float(e @ e)
    ybar = y.mean()
    sst = float(((y - ybar) ** 2).sum())
    r2 = 1.0 - ssr / sst if sst > 0 else np.nan
    adj = 1.0 - (1.0 - r2) * (n - 1) / (n - p) if n > p else np.nan
    se = np.sqrt(np.maximum(np.diag(V), 0))
    s2 = ssr / (n - p) if n > p else np.nan
    se_ols = np.sqrt(np.maximum(np.diag(A) * s2, 0))
    with np.errstate(divide="ignore", invalid="ignore"):
        t = coef / se
        t_ols = coef / se_ols
    return dict(coef=coef, se=se, t=t, V=V, resid=e, ssr=ssr, sst=sst, r2=r2, adj_r2=adj, n=n, p=p,
                se_ols=se_ols, t_ols=t_ols)


def lag_stack(A, lags=1):
    """[A_t, A_{t-1}] ตามแกนเวลา (แถวแรกของ lag = NaN)"""
    A = np.asarray(A, float)
    parts = [A]
    for l in range(1, lags + 1):
        sh = np.full_like(A, np.nan)
        sh[l:] = A[:-l]
        parts.append(sh)
    return np.hstack(parts)


def dimson_design(F, lags=1):
    """F: DataFrame (T x K) → DataFrame (T x K(1+lags)) คอลัมน์ [f..., f_l1...] · lag อ้างอิงตาม index ทั้งชุด
    (แถวแรกของ index ไม่มี lag → NaN · แถวแรกของ test ใช้ lag จาก train)"""
    D = lag_stack(F.to_numpy(float), lags)
    cols = list(F.columns) + [f"{c}_l{l}" for l in range(1, lags + 1) for c in F.columns]
    return pd.DataFrame(D, index=F.index, columns=cols)


class CommonFactors:
    """factor ชุดเดียวทุกกอง"""

    def __init__(self, F):
        self.F = F
        self.names = list(F.columns)
        self.index = F.index
        self.K = F.shape[1]
        self._D = dimson_design(F).to_numpy()

    def design(self, code=None):
        return self._D


class FitResult:
    pass


def fit_funds(R, F, mask, min_obs, L=4, funds=None):
    """OLS Dimson รายกอง · F: DataFrame หรือ object ที่มี .design(code) (T x 2K) .names .K
    mask: boolean ความยาว T · แถวที่ NaN ในกอง/factor ตกอัตโนมัติ"""
    if isinstance(F, pd.DataFrame):
        F = CommonFactors(F)
    funds = list(R.columns) if funds is None else list(funds)
    T = len(R.index)
    K = F.K
    N = len(funds)
    mask = np.asarray(mask, bool)
    out = FitResult()
    out.codes = funds
    out.names = list(F.names)
    out.K = K
    nan = lambda *s: np.full(s, np.nan)
    out.alpha = nan(N)
    out.b0 = nan(N, K)
    out.b1 = nan(N, K)
    out.beta = nan(N, K)
    out.se_beta = nan(N, K)
    out.t_b1 = nan(N, K)
    out.t_alpha_hac = nan(N)
    out.t_alpha_ols = nan(N)
    out.r2 = nan(N)
    out.adj_r2 = nan(N)
    out.bic = nan(N)
    out.n = np.zeros(N, int)
    out.ssr = nan(N)
    out.coef = nan(N, 1 + 2 * K)
    out.resid = nan(T, N)
    out.ok = np.zeros(N, bool)
    Rv = R[funds].to_numpy(float)
    for j, code in enumerate(funds):
        y = Rv[:, j]
        D = F.design(code)
        ok = mask & np.isfinite(y) & np.isfinite(D).all(axis=1)
        n = int(ok.sum())
        out.n[j] = n
        if n < max(min_obs, 2 * K + 3):
            continue
        X = np.column_stack([np.ones(n), D[ok]])
        r = ols_hac(y[ok], X, L)
        c = r["coef"]
        V = r["V"]
        out.coef[j] = c
        out.alpha[j] = c[0]
        out.b0[j] = c[1:1 + K]
        out.b1[j] = c[1 + K:]
        out.beta[j] = c[1:1 + K] + c[1 + K:]
        a = np.arange(1, 1 + K)
        b = a + K
        var = V[a, a] + V[b, b] + 2 * V[a, b]
        out.se_beta[j] = np.sqrt(np.maximum(var, 0))
        out.t_b1[j] = c[b] / r["se"][b]
        out.t_alpha_hac[j] = r["t"][0]
        out.t_alpha_ols[j] = r["t_ols"][0]
        out.r2[j] = r["r2"]
        out.adj_r2[j] = r["adj_r2"]
        out.ssr[j] = r["ssr"]
        out.bic[j] = n * np.log(r["ssr"] / n) + r["p"] * np.log(n)
        tmp = np.full(T, np.nan)
        tmp[ok] = r["resid"]
        out.resid[:, j] = tmp
        out.ok[j] = True
    return out


def predict_oos(coef, Xdes):
    """ŷ = coef[0] + Xdes @ coef[1:] — ไม่ fit ใหม่"""
    coef = np.asarray(coef, float)
    return coef[0] + np.asarray(Xdes, float) @ coef[1:]


def r2_oos(y, yhat):
    """R²_oos = 1 - Σ(y-ŷ)²/Σ(y - ȳ_test)² (ติดลบได้) · ใช้เฉพาะแถวที่ทั้งคู่ไม่ NaN"""
    y = np.asarray(y, float)
    yhat = np.asarray(yhat, float)
    ok = np.isfinite(y) & np.isfinite(yhat)
    if ok.sum() < 2:
        return np.nan
    yy, hh = y[ok], yhat[ok]
    den = ((yy - yy.mean()) ** 2).sum()
    if den <= 0:
        return np.nan
    return 1.0 - ((yy - hh) ** 2).sum() / den


def oos_r2_funds(R, F, fit, mask_test):
    """R²_oos รายกอง ด้วย coef จาก fit (train) บน design ช่วง test (ไม่ fit ใหม่)"""
    if isinstance(F, pd.DataFrame):
        F = CommonFactors(F)
    mask_test = np.asarray(mask_test, bool)
    Rv = R[fit.codes].to_numpy(float)
    out = np.full(len(fit.codes), np.nan)
    for j, code in enumerate(fit.codes):
        if not fit.ok[j]:
            continue
        D = F.design(code)
        yh = predict_oos(fit.coef[j], D)
        m = mask_test
        out[j] = r2_oos(Rv[m, j], yh[m])
    return out
