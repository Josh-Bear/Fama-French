"""reviewer S006: ตรวจเหตุผลเชิงพีชคณิตข้อ 3.4 ด้วยข้อมูลจำลอง (ไม่ใช้ข้อมูลจริง)"""
import numpy as np
rng = np.random.default_rng(1)
T, Ttr, K = 260, 155, 4
f = rng.standard_normal((T, K)) * 0.02
I = 0.003 + f @ np.array([0.8, -0.3, 0.5, 0.2]) + 0.6 * np.r_[np.zeros((1, K)), f[:-1]] @ np.array([0.2, 0.1, 0, 0]) + rng.standard_normal(T) * 0.01
y = 0.001 + f @ np.array([1, .5, -.2, .3]) + 0.4 * I + 0.2 * np.r_[0, I[:-1]] + rng.standard_normal(T) * 0.01
tr = np.arange(T) < Ttr; tr[0] = False; te = ~tr; te[0] = False
def lag(x): return np.r_[np.full((1,) + x.shape[1:], np.nan), x[:-1]]
def dim(*cols):
    X = np.column_stack(cols); return np.column_stack([np.ones(T), X, lag(X)])
def fit(X):
    ok = tr & np.isfinite(X).all(1)
    b = np.linalg.lstsq(X[ok], y[ok], rcond=None)[0]
    e = y[ok] - X[ok] @ b; r2 = 1 - e @ e / ((y[ok] - y[ok].mean()) ** 2).sum()
    okt = te & np.isfinite(X).all(1); et = y[okt] - X[okt] @ b
    r2o = 1 - et @ et / ((y[okt] - y[okt].mean()) ** 2).sum()
    # HAC NW L=4 se of alpha
    Xo = X[ok]; n = len(e); XtXi = np.linalg.inv(Xo.T @ Xo); u = Xo * e[:, None]; S = u.T @ u
    for l in range(1, 5):
        w = 1 - l / 5; G = u[l:].T @ u[:-l]; S += w * (G + G.T)
    V = XtXi @ S @ XtXi
    return dict(alpha=b[0], t=b[0] / np.sqrt(V[0, 0]), r2=r2, r2oos=r2o)
# auxiliary (train) : I on [1, f]
okA = tr.copy()
A = np.column_stack([np.ones(T), f]); ab = np.linalg.lstsq(A[okA], I[okA], rcond=None)[0]
e_keep = I - f @ ab[1:]          # spec 3.4: เก็บค่าคงที่
e_dem = I - ab[0] - f @ ab[1:]   # หัก â
A2 = np.column_stack([np.ones(T), f, lag(f)]); ok2 = tr & np.isfinite(A2).all(1)
ab2 = np.linalg.lstsq(A2[ok2], I[ok2], rcond=None)[0]
e_lag = I - ab2[0] - f @ ab2[1:K+1] - lag(f) @ ab2[K+1:]   # แบบ F-R004 (a + b f_t + c f_t-1)
e_lag_keep = I - f @ ab2[1:K+1] - lag(f) @ ab2[K+1:]
raw = fit(dim(f, I))
for nm, e in (("keep-const lag0", e_keep), ("demean lag0", e_dem), ("F-R004 a+b f_t+c f_t-1", e_lag), ("F-R004 แต่เก็บ a", e_lag_keep)):
    r = fit(dim(f, e)); print(f"{nm:26s}", {k: f"{r[k]-raw[k]:+.2e}" for k in r})
# Dimson β ของดัชนี (b0+b1) และ α ที่เปลี่ยนเมื่อหัก â
Xr = dim(f, e_dem); ok = tr & np.isfinite(Xr).all(1); b = np.linalg.lstsq(Xr[ok], y[ok], rcond=None)[0]
print("alpha(demean)-alpha(raw) =", b[0] - raw["alpha"], " (b0+b1)*a_hat =", (b[1+K] + b[1+(K+1)+K]) * ab[0])
