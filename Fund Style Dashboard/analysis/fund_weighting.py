"""fund_weighting.py — คัดกองและให้น้ำหนักของโมเดลหน้า 9 (M004-TF-FX).

พอร์ตจากโค้ด backtest ของทีม quant โดยไม่เปลี่ยนตรรกะ (ตัวเลขต้องตรง backtest)
1. ตัวแทน family = class ที่ SR12 สูงสุด (หรือ class ที่ถืออยู่แล้ว — ไม่สลับ class)
2. hysteresis: กองที่ถืออยู่และยังติดอันดับ ≤ K ถือต่อ · เติมอันดับสูงสุดจนครบ N · ได้ < TF_MIN_FUNDS -> fallback B0
3. ERC (ทุกกองมีส่วนในความเสี่ยงเท่ากัน) จาก covariance รายสัปดาห์ 52 สัปดาห์แบบ Ledoit-Wolf · เพดานต่อกอง
4. trend filter: MSCI ACWI < SMA200 -> ถือเงินสด
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from sklearn.covariance import LedoitWolf

import config


def family_representatives(df_it: pd.DataFrame, held_funds: set[str]) -> dict[str, dict]:
    """{family: {FundCode, signal, vol52}} — class SR12 สูงสุด เว้นแต่ family นั้นมี class ที่ถืออยู่."""
    reps = {}
    for fam, g in df_it.groupby("family"):
        held_rows = g[g["FundCode"].isin(held_funds)]
        if len(held_rows):
            row = held_rows.iloc[0]
        else:
            row = g.sort_values(["SR12", "vol52", "FundCode"], ascending=[False, True, True]).iloc[0]
        reps[fam] = {"FundCode": row["FundCode"], "signal": row["SR12"], "vol52": row["vol52"]}
    return reps


def rank_families(reps: dict[str, dict]) -> dict[str, int]:
    """อันดับ 1.. ตาม signal มากไปน้อย · เสมอกันใช้ vol ต่ำก่อน แล้วชื่อกอง · NaN ไปท้าย."""
    items = sorted(reps.items(), key=lambda kv: (-kv[1]["signal"] if kv[1]["signal"] == kv[1]["signal"] else np.inf,
                                                   kv[1]["vol52"] if kv[1]["vol52"] == kv[1]["vol52"] else np.inf,
                                                   kv[1]["FundCode"]))
    return {fam: i + 1 for i, (fam, _) in enumerate(items)}


def hysteresis_select(reps: dict[str, dict], ranks: dict[str, int], held_map: dict[str, str],
                      n_target: int | None = None, k_drop: int | None = None) -> dict:
    """held_map: family -> FundCode ที่ถืออยู่ · คืน {S: family->FundCode, kept, added, fallback}."""
    n_target = config.TF_N_FUNDS if n_target is None else n_target
    k_drop = config.TF_HYSTERESIS_K if k_drop is None else k_drop
    selected: dict[str, str] = {}
    kept = []
    for fam, fc in held_map.items():
        if fam in reps and ranks.get(fam, 10**9) <= k_drop and reps[fam]["FundCode"] == fc:
            selected[fam] = fc
            kept.append(fam)
    for fam in sorted(reps.keys(), key=lambda f: ranks.get(f, 10**9)):
        if len(selected) >= n_target:
            break
        if fam not in selected:
            selected[fam] = reps[fam]["FundCode"]
    added = [f for f in selected if f not in kept]
    return {"S": selected, "kept": kept, "added": added,
            "fallback": "b0" if len(selected) < config.TF_MIN_FUNDS else None}


def apply_cap(w: pd.Series, cap: float | None = None, max_iter: int = 50, tol: float = 1e-12) -> pd.Series:
    """ตัดน้ำหนักที่เกิน cap แล้วเกลี่ยส่วนเกินให้กองที่ยังไม่ชนเพดานตามสัดส่วน (ผลรวมเท่าเดิม)."""
    cap = config.TF_WEIGHT_CAP if cap is None else cap
    w = w.copy().astype(float)
    total = w.sum()
    if total <= 0:
        return w
    w = w / total
    for _ in range(max_iter):
        over = w[w > cap + tol]
        if len(over) == 0:
            break
        excess = float((over - cap).sum())
        w[over.index] = cap
        under_mask = w < cap - tol
        under_sum = float(w[under_mask].sum())
        if under_sum <= 0:               # ทุกตัวติดเพดานพอดี (N เล็ก) -> กระจายเท่ากันเท่าที่ทำได้
            w[under_mask] = w[under_mask] + excess / max(under_mask.sum(), 1)
            break
        w[under_mask] = w[under_mask] + excess * (w[under_mask] / under_sum)
    return w * total


def weekly_covariance(funds: list[str], weekly_returns: dict[str, pd.Series]) -> np.ndarray | None:
    """Ledoit-Wolf × 52 จากสัปดาห์ที่ทุกกองมีข้อมูล · สัปดาห์ร่วม < TF_COV_MIN_WEEKS -> None."""
    mat = pd.DataFrame({fc: weekly_returns.get(fc, pd.Series(dtype=float)) for fc in funds}).dropna(how="any")
    if len(mat) >= config.TF_COV_MIN_WEEKS and mat.shape[1] == len(funds):
        return LedoitWolf().fit(mat.to_numpy()).covariance_ * 52.0
    return None


def erc_weights(sigma: np.ndarray, funds: list[str]) -> pd.Series:
    """Equal Risk Contribution: min ½yᵀΣy − (1/n)Σ log y แล้ว normalize (Spinu 2013)."""
    n = len(funds)
    x0 = 1.0 / np.sqrt(np.clip(np.diag(sigma), 1e-12, None))

    def obj(y):
        y = np.clip(y, 1e-10, None)
        return 0.5 * y @ sigma @ y - np.sum(np.log(y)) / n

    def grad(y):
        y = np.clip(y, 1e-10, None)
        return sigma @ y - (1.0 / n) / y

    res = minimize(obj, x0, jac=grad, method="L-BFGS-B", bounds=[(1e-10, None)] * n)
    y = np.clip(res.x, 1e-10, None)
    return pd.Series(y / y.sum(), index=funds)


def risk_parity_weights(funds: list[str], weekly_returns: dict[str, pd.Series],
                        vol52: dict[str, float]) -> tuple[pd.Series, str]:
    """ERC ถ้าคำนวณ covariance ได้ · ไม่งั้น inverse-vol จาก vol52 · คืน (น้ำหนัก, ที่มา)."""
    if len(funds) == 1:
        return pd.Series([1.0], index=funds), "single"
    sigma = weekly_covariance(funds, weekly_returns)
    if sigma is None:
        inv = np.array([1.0 / max(vol52.get(f, np.nan), 1e-6) if vol52.get(f, np.nan) == vol52.get(f, np.nan)
                        else 0.0 for f in funds])
        if inv.sum() <= 0:
            inv = np.ones(len(funds))
        return pd.Series(inv / inv.sum(), index=funds), "ivol"
    return erc_weights(sigma, funds), "ledoit_wolf"


def trend_state(index_level: pd.Series, t: pd.Timestamp) -> dict:
    """{level, sma, below, cash} ณ t (ใช้ข้อมูล ≤ t) · ข้อมูล < SMA วัน -> ไม่ถือเงินสด."""
    s = index_level.loc[:t]
    if len(s) < config.TF_TREND_SMA:
        return {"level": float(s.iloc[-1]) if len(s) else np.nan, "sma": np.nan, "below": False, "cash": 0.0}
    sma = float(s.iloc[-config.TF_TREND_SMA:].mean())
    level = float(s.iloc[-1])
    below = level < sma
    return {"level": level, "sma": sma, "below": below, "cash": config.TF_TREND_CASH if below else 0.0}
