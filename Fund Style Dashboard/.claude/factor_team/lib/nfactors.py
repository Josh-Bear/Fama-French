"""nfactors — Bai-Ng IC, Ahn-Horenstein, Onatski ED, parallel analysis, combine_k"""
import numpy as np


def corr_eig(Z):
    """eigenvalue (มาก→น้อย) ของ Z'Z/T"""
    T = Z.shape[0]
    w = np.linalg.eigvalsh(Z.T @ Z / T)
    return w[::-1]


def bai_ng_ic(eig, N, T, kmax, which="p2"):
    """argmin_{k=0..kmax} ln V(k) + k·g(N,T) · V(k) = Σ_{j>k} λ_j / N (eig จาก Z'Z/T)"""
    eig = np.asarray(eig, float)
    best, bk = np.inf, 0
    if which == "p2":
        g = (N + T) / (N * T) * np.log(min(N, T))
    elif which == "p1":
        g = (N + T) / (N * T) * np.log(N * T / (N + T))
    else:
        raise ValueError(which)
    for k in range(0, kmax + 1):
        v = eig[k:].sum() / N
        ic = np.log(v) + k * g
        if ic < best - 1e-15:
            best, bk = ic, k
    return bk


def ahn_horenstein(eig, kmax):
    """ER: argmax_{1<=k<=kmax} λ_k/λ_{k+1} · GR: argmax ln(1+λ_k/V_k)/ln(1+λ_{k+1}/V_{k+1})"""
    eig = np.asarray(eig, float)
    er = eig[:kmax] / eig[1:kmax + 1]
    k_er = int(np.argmax(er)) + 1
    V = np.array([eig[k:].sum() for k in range(len(eig) + 1)])
    mu = eig / V[:len(eig)]  # λ_k / Σ_{j>=k} λ_j
    with np.errstate(divide="ignore", invalid="ignore"):
        gr_vals = []
        for k in range(1, kmax + 1):
            num = np.log(1 + eig[k - 1] / V[k])
            den = np.log(1 + eig[k] / V[k + 1])
            gr_vals.append(num / den)
    k_gr = int(np.nanargmax(gr_vals)) + 1
    return k_er, k_gr


def onatski_ed(eig, kmax, maxit=100):
    """Onatski (2010) edge distribution — ขั้นตอน iterative ตาม S002 ข้อ 3.①
    (1) j=kmax+1 (2) OLS ของ (λ_j..λ_{j+4}) บนค่าคงที่และ ((j-1)^{2/3}..(j+3)^{2/3}) → δ=2|β̂|
    (3) k̂ = max{i<=kmax: λ_i-λ_{i+1} >= δ} (ไม่มี → 0) (4) j=k̂+1 วนจน k̂ ไม่เปลี่ยน · ไม่ลู่เข้า → None"""
    eig = np.asarray(eig, float)
    j = kmax + 1
    prev = None
    for _ in range(maxit):
        y = eig[j - 1:j + 4]
        x = np.arange(j - 1, j + 4, dtype=float)
        x = np.maximum(x, 0.0) ** (2.0 / 3.0)
        X = np.column_stack([np.ones(5), x])
        beta = np.linalg.lstsq(X, y, rcond=None)[0][1]
        delta = 2.0 * abs(beta)
        k = 0
        for i in range(1, kmax + 1):
            if eig[i - 1] - eig[i] >= delta:
                k = i
        if prev is not None and k == prev:
            return int(k)
        prev = k
        j = k + 1
    return None


def parallel_analysis(Z, n_perm=500, q=0.95, seed=20261015):
    """Horn: สลับแต่ละคอลัมน์ของ Z อิสระ n_perm ครั้ง · k = จำนวน λ_k ที่ > percentile q ของ permutation (นับจาก k=1 จนตัวแรกที่ไม่ผ่าน)"""
    Z = np.asarray(Z, float)
    T, N = Z.shape
    rng = np.random.default_rng(seed)
    eig = corr_eig(Z)
    sims = np.empty((n_perm, N))
    for b in range(n_perm):
        Zp = rng.permuted(Z, axis=0)
        sims[b] = corr_eig(Zp)
    thr = np.percentile(sims, 100 * q, axis=0)
    k = 0
    for i in range(N):
        if eig[i] > thr[i]:
            k += 1
        else:
            break
    return k


def combine_k(ks):
    """k* = floor(median) ของ k ที่ใช้ได้ (None ถูกข้าม) · อย่างน้อย 1"""
    v = [k for k in ks if k is not None]
    return max(1, int(np.floor(np.median(v))))
