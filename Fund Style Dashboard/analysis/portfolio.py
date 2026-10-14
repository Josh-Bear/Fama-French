"""portfolio.py — คณิตของ efficient frontier หน้า 8 ส่วนที่ 3 (pure functions — test ได้ตรงๆ).

Σ = B·F·Bᵀ + D   (Barra-style factor risk model)
  B = exposure ของกองต่อ factor (beta หน่วยจริง — unstandardize แล้ว)
  F = covariance ของ factor รายวัน (Ledoit-Wolf shrinkage) annualize แล้ว
  D = idiosyncratic variance ต่อกอง = (1 − R²) × variance รวมของกอง

μ = Π = γ · Σ_sys · w_ref   (Black-Litterman reverse optimization)
  Σ_sys = B·F·Bᵀ **ไม่รวม D** — ความเสี่ยงเฉพาะตัวกระจายทิ้งได้ ในสมดุลไม่ได้ค่าตอบแทน (ไม่งั้นกอง vol เฉพาะตัวสูงได้ Π สูง)
  γ คงที่ (config.PORTFOLIO_GAMMA) · w_ref = น้ำหนักอ้างอิง (config.PORTFOLIO_REF_WEIGHT: equal 1/N หรือ aum)
  ส่วน Σ เต็ม (รวม D) ยังใช้หาความเสี่ยงพอร์ตเหมือนเดิม

frontier หาโดย **enumerate ทุกน้ำหนักจำนวนเต็ม %** ที่ผ่านเงื่อนไข ไม่ใช้ solver
-> ไม่มีปัญหา convergence · น้ำหนักที่ได้ซื้อขายได้จริง · เห็น "พื้นที่ที่เป็นไปได้" ทั้งหมด ไม่ใช่แค่เส้น
"""

from __future__ import annotations

import numpy as np
import pandas as pd

import config


def market_weights(aum: pd.Series, cap: float | None = None) -> pd.Series:
    """สัดส่วน AUM -> น้ำหนักตลาดของ BL · กองเดียวห้ามเกิน cap ส่วนเกินเกลี่ยให้กองที่เหลือเท่าๆ กัน (วนจนผ่าน).

    AUM ว่าง/เป็น 0 ทั้งชุด -> เท่ากันทุกกอง (ไม่มีข้อมูลให้ถ่วงน้ำหนัก)
    """
    cap = config.PORTFOLIO_MARKET_CAP_W if cap is None else cap
    w = aum.astype(float).clip(lower=0.0)
    n = len(w)
    if n == 0:
        return w
    if cap * n < 1.0 - 1e-12:                    # cap ต่ำเกินจะรวมได้ 100% -> เท่ากันทุกกอง
        return pd.Series(1.0 / n, index=w.index)
    w = pd.Series(1.0 / n, index=w.index) if w.sum() <= 0 else w / w.sum()
    capped = pd.Series(False, index=w.index)
    for _ in range(n):                           # อย่างมาก n รอบ (แต่ละรอบ cap อย่างน้อย 1 กองเพิ่ม)
        over = (w > cap + 1e-12) & ~capped
        if not over.any():
            break
        capped |= over
        w[capped] = cap                          # กองที่ cap แล้วตรึงไว้ ไม่รับส่วนเกินรอบถัดไป (ไม่งั้นเด้งเกิน cap ซ้ำ)
        free = ~capped
        if not free.any():
            break
        w[free] = w[free] + (1.0 - float(w.sum())) / int(free.sum())   # เกลี่ยส่วนที่ขาดเท่าๆ กัน
    return w


def reference_weights(aum: pd.Series, mode: str | None = None) -> pd.Series:
    """น้ำหนักอ้างอิงของ BL — "equal" = 1/N (ค่าเริ่มต้น) · "aum" = สัดส่วน AUM (market_weights).

    ทำไม equal: AUM ของกองที่คัดมาเองไม่ใช่ "พอร์ตตลาด" ที่สมมติฐาน BL ต้องการ (ใช้ได้กับหุ้น/market cap)
    """
    mode = config.PORTFOLIO_REF_WEIGHT if mode is None else mode
    if mode == "aum":
        return market_weights(aum)
    if mode == "equal":
        return pd.Series(1.0 / len(aum), index=aum.index) if len(aum) else aum.astype(float)
    raise ValueError(f"PORTFOLIO_REF_WEIGHT ต้องเป็น 'equal' หรือ 'aum' ไม่ใช่ {mode!r}")


def systematic_covariance(sigma: pd.DataFrame, idio_var: pd.Series) -> pd.DataFrame:
    """Σ_sys = Σ − diag(D) = B·F·Bᵀ (เฉพาะส่วนที่มาจาก factor ร่วม) — align ตามชื่อกอง."""
    d = idio_var.reindex(sigma.index).to_numpy(dtype=float)
    return pd.DataFrame(sigma.to_numpy() - np.diag(d), index=sigma.index, columns=sigma.columns)


def implied_returns(sigma: pd.DataFrame, w_market: pd.Series, gamma: float | None = None) -> pd.Series:
    """Black-Litterman implied return Π = γ Σ w  — ส่ง Σ_sys (systematic_covariance) ไม่ใช่ Σ เต็ม."""
    gamma = config.PORTFOLIO_GAMMA if gamma is None else gamma
    w = w_market.reindex(sigma.index)
    return pd.Series(gamma * (sigma.to_numpy() @ w.to_numpy()), index=sigma.index, name="implied_return")


def shrink_constant_correlation(x: np.ndarray) -> tuple[np.ndarray, float]:
    """Ledoit & Wolf (2004) "Honey, I Shrunk the Sample Covariance Matrix" — shrink เข้าหาเป้า constant correlation.

    เป้า F: variance เดิม · covariance = r̄·σ_i·σ_j (r̄ = correlation เฉลี่ย) · Σ = δF + (1−δ)S
    δ = max(0, min(1, (π − ρ) / γ / T)) — ความเข้มที่เหมาะสมตามสูตรต้นฉบับ (S หารด้วย T)
    ทำไมไม่ใช้เป้า μI ของ sklearn: ดัชนีชุด 18 ซ้อนกันเอง (ACWI ⊃ USA) ElasticNet ให้ beta หักล้างกัน (+/− แรง)
    การดึง covariance เข้าหา 0 จึงบิด correlation ระหว่างกอง (review 2026-09-29) · เป้า constant correlation เก็บโครงสร้าง
    correlation ไว้ (dry run 2026-10-02 · 40 กอง: MAE corr เทียบ weekly จริง 11: 0.147 → 0.143 · 18: 0.163 → 0.160)
    """
    x = x - x.mean(axis=0)
    t, n = x.shape
    s = x.T @ x / t
    sd = np.sqrt(np.diag(s))
    if t < 3 or n < 2 or np.any(sd < 1e-12):
        # สูตร constant correlation หารด้วย SD -> factor ที่ค่าไม่ขยับ (หรือข้อมูลน้อยเกิน) ได้ NaN ทั้งตาราง
        # กรณีนี้ใช้ Ledoit-Wolf เป้า μI แบบเดิม (sklearn) ซึ่งให้ผลจำกัดค่าเสมอ
        from sklearn.covariance import LedoitWolf
        lw = LedoitWolf(assume_centered=True).fit(x)
        return lw.covariance_, float(lw.shrinkage_)
    corr = s / np.outer(sd, sd)
    r_bar = (corr.sum() - n) / (n * (n - 1))
    target = r_bar * np.outer(sd, sd)
    np.fill_diagonal(target, np.diag(s))
    pi_mat = (x ** 2).T @ (x ** 2) / t - s ** 2
    theta = (x ** 3).T @ x / t - np.diag(s)[:, None] * s          # θ[i, j] = E[(x_i² − s_ii)(x_i x_j − s_ij)]
    rho = np.trace(pi_mat) + r_bar * ((np.outer(1 / sd, sd) * theta).sum() - np.trace(theta))
    gamma = ((target - s) ** 2).sum()
    delta = float(max(0.0, min(1.0, (pi_mat.sum() - rho) / gamma / t))) if gamma > 0 else 0.0
    return delta * target + (1 - delta) * s, delta


def factor_covariance(factor_returns: pd.DataFrame) -> pd.DataFrame:
    """covariance ของ factor รายวัน ด้วย shrinkage แบบ constant correlation (shrink_constant_correlation) แล้ว annualize.

    raw sample covariance ของดัชนี MSCI เกือบ singular (ดัชนีรวมซ้อนกับรายตลาด) -> optimizer จะไปเกาะ
    near-linear-dependence จนได้น้ำหนักสุดโต่ง · shrink เพียงไม่กี่ % ก็ลด condition number ลงหลายร้อยเท่า
    (ข้อมูลจริง: ชุด 11 2,808 → 197 · ชุด 18 1.7 ล้าน → 802)
    """
    x = factor_returns.dropna()
    cov, _ = shrink_constant_correlation(x.to_numpy())
    return pd.DataFrame(cov * config.TRADING_DAYS, index=x.columns, columns=x.columns)


def fund_covariance(betas: pd.DataFrame, factor_cov: pd.DataFrame, idio_var: pd.Series) -> pd.DataFrame:
    """Σ = B F Bᵀ + diag(D) — align ตามชื่อ factor/กอง ไม่ใช่ตำแหน่ง."""
    b = betas[factor_cov.index]
    sigma = b.to_numpy() @ factor_cov.to_numpy() @ b.to_numpy().T
    sigma = sigma + np.diag(idio_var.reindex(betas.index).to_numpy())
    sigma = (sigma + sigma.T) / 2.0                 # กัน asymmetry จาก floating point
    return pd.DataFrame(sigma, index=betas.index, columns=betas.index)


def weight_grid(n: int, min_w: float | None = None, max_w: float | None = None,
                step: float | None = None) -> np.ndarray:
    """ทุกชุดน้ำหนักจำนวนเต็ม step ที่ min ≤ w_i ≤ max และรวมได้ 100% พอดี -> array (combinations × n).

    คืน array ว่างถ้าเงื่อนไขเป็นไปไม่ได้ (min×n > 100% หรือ max×n < 100%)
    step ต้องหาร 100% ลงตัว (ไม่งั้น raise ValueError — เช่น 3% จะกลายเป็นหน่วยละ 3.03%)
    min/max ที่ไม่ลงตัวกับ step ปัด**เข้าใน**ช่วง (min ปัดขึ้น · max ปัดลง) — ไม่มีน้ำหนักหลุดเงื่อนไขที่ตั้งไว้
    """
    min_w = config.PORTFOLIO_MIN_W if min_w is None else min_w
    max_w = config.PORTFOLIO_MAX_W if max_w is None else max_w
    step = config.PORTFOLIO_STEP_W if step is None else step
    unit_f = 1.0 / step
    unit = int(round(unit_f))                       # ทำงานบนจำนวนเต็ม "หน่วย step" กัน floating error
    if unit <= 0 or abs(unit_f - unit) > 1e-9:
        raise ValueError(f"step {step:.2%} หาร 100% ไม่ลงตัว — ใช้ 1, 2, 4, 5, 10, 20 หรือ 25%")
    lo, hi = int(np.ceil(min_w * unit - 1e-9)), int(np.floor(max_w * unit + 1e-9))
    if n <= 0 or lo * n > unit or hi * n < unit:
        return np.empty((0, max(n, 0)), dtype=float)
    if n == 1:
        return np.array([[1.0]]) if lo <= unit <= hi else np.empty((0, 1), dtype=float)
    if (hi - lo + 1) ** (n - 1) > config.PORTFOLIO_MAX_COMBOS:
        raise ValueError(f"กริดใหญ่เกินไป ({(hi - lo + 1) ** (n - 1):,} จุดก่อนกรอง) — เพิ่ม step หรือแคบช่วง min/max")
    vals = np.arange(lo, hi + 1)
    grid = np.stack([g.ravel() for g in np.meshgrid(*([vals] * (n - 1)), indexing="ij")], axis=1)
    last = unit - grid.sum(axis=1)
    ok = (last >= lo) & (last <= hi)
    return np.column_stack([grid[ok], last[ok]]) / unit


def composition_grid(n: int, step: float, max_w: float = 1.0) -> np.ndarray:
    """ทุกชุดน้ำหนัก 0–max_w ทีละ step ที่รวมได้ 100% พอดี -> array (combinations × n).

    ต่างจาก weight_grid ที่สร้าง meshgrid ทุกค่าก่อนกรอง — ที่นี่ต่อทีละกองและตัดกิ่งที่เกินเพดาน/เติมไม่ถึง 100% ทันที
    จึงใช้กับกองจำนวนมากได้ (หน้า 10: หุ้น 8 กอง ทีละ 5% เพดาน 40% = 634,446 ชุด · weight_grid ต้องสร้าง 9⁷ ≈ 4.8 ล้านจุดก่อนกรอง)
    max_w ที่ไม่ลงตัวกับ step ปัดลง (ไม่มีน้ำหนักเกินเพดาน) · เงื่อนไขเป็นไปไม่ได้ (max_w × n < 100%) -> array ว่าง
    """
    unit_f = 1.0 / step
    units = int(round(unit_f))
    if units <= 0 or abs(unit_f - units) > 1e-9:
        raise ValueError(f"step {step:.2%} หาร 100% ไม่ลงตัว")
    cap = min(int(np.floor(max_w * units + 1e-9)), units)
    if n <= 0 or cap * n < units:
        return np.empty((0, max(n, 0)), dtype=float)
    parts = np.zeros((1, 0), dtype=np.int16)
    for i in range(n - 1):                                   # กองที่ i: ใส่ได้ 0..cap หน่วย โดยกองที่เหลือยังเติมถึง 100% ได้
        v = np.arange(cap + 1, dtype=np.int16)
        parts = np.column_stack([np.repeat(parts, len(v), axis=0), np.tile(v, len(parts))])
        left = units - parts.sum(axis=1)
        parts = parts[(left >= 0) & (left <= cap * (n - 1 - i))]
    last = units - parts.sum(axis=1)                         # กองสุดท้าย = ส่วนที่เหลือ (อยู่ใน 0..cap แล้วจากเงื่อนไขข้างบน)
    return np.column_stack([parts, last]).astype(float) / units


def portfolio_points(weights: np.ndarray, mu: pd.Series, sigma: pd.DataFrame) -> pd.DataFrame:
    """risk (annualized vol) กับ return ของทุกชุดน้ำหนัก -> DataFrame[risk, ret]."""
    s, m = sigma.to_numpy(), mu.reindex(sigma.index).to_numpy()
    var = np.einsum("ij,jk,ik->i", weights, s, weights)
    return pd.DataFrame({"risk": np.sqrt(np.clip(var, 0.0, None)), "ret": weights @ m})


def pareto_mask(risk: np.ndarray, ret: np.ndarray) -> np.ndarray:
    """จุดที่ไม่มีใครดีกว่า: ไล่จาก risk น้อยไปมาก เก็บเฉพาะจุดที่ return ทำ new high (efficient frontier)."""
    order = np.lexsort((-ret, risk))              # risk น้อยก่อน · risk เท่ากันเอา return มากก่อน
    keep = np.zeros(len(risk), dtype=bool)
    best = -np.inf
    for i in order:
        if ret[i] > best:
            keep[i] = True
            best = ret[i]
    return keep


def max_sharpe_index(points: pd.DataFrame, risk_free: float = 0.0) -> int:
    """ตำแหน่ง (positional) ของพอร์ตที่ (return − rf) ÷ risk สูงสุด = tangency portfolio.

    rf = 0 โดยค่าเริ่มต้น เพราะระบบไม่มี risk-free rate (γ ใช้ค่าคงที่แล้วจึงไม่ต้องนำเข้าข้อมูล rf)
    -> ตัวเลข Sharpe ที่ได้เป็น "return ต่อหนึ่งหน่วยความเสี่ยง" ไม่ใช่ Sharpe ratio ตามนิยามเต็มที่หัก rf
    """
    risk = points["risk"].to_numpy()
    sharpe = np.where(risk > 0, (points["ret"].to_numpy() - risk_free) / np.where(risk > 0, risk, 1.0), -np.inf)
    return int(np.argmax(sharpe))


def risk_contribution(w: pd.Series, sigma: pd.DataFrame) -> pd.Series:
    """ส่วนแบ่งความเสี่ยงของแต่ละกอง = w_i × (Σw)_i ÷ variance รวม (รวมกันได้ 1)."""
    ww = w.reindex(sigma.index).to_numpy()
    mrc = sigma.to_numpy() @ ww
    total = float(ww @ mrc)
    if total <= 0:
        return pd.Series(np.nan, index=sigma.index)
    return pd.Series(ww * mrc / total, index=sigma.index)
