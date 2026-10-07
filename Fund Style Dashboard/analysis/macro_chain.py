"""macro_chain.py — คณิตของหน้า 7 Macro Chain (pure functions — test ได้ตรงๆ).

Stage 1  : monthly return ของ 28 MSCI index ~ 7 macro factor (OLS) -> B (index × factor)
Stage 2  : implied loading ของกอง = Σ β_raw[index] × B[index, :]  (look-through ผ่าน country/sector)
Direct   : monthly return ของกอง ~ 7 macro factor (OLS) — ตัวอ้างอิงเชิงประจักษ์ วางคู่กับ implied

กับดักที่ต้องกัน (พบตอน review 2026-09-15 — ดู docs/pages/7-macro-chain.md):
  1) coefs.csv เป็น **standardized** coef (StandardScaler บน X) -> ต้อง unstandardize ก่อน chain
     ไม่งั้น loading เล็กเกินจริง ~64 เท่า
  2) country กับ sector เป็นคนละ regression ต่างอธิบาย return กองทั้งก้อน -> chain แยก scope แล้ว**เฉลี่ย**
     (รวม 28 ตัว = นับตลาด 2 รอบ ใหญ่เกิน ~1.6 เท่า)
  3) หน่วย factor ต่างกัน (return / จุด VIX / pp yield) -> เทียบข้าม factor ด้วย impact ต่อ 1 SD เท่านั้น
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from analysis import matching


def _month_complete(end: pd.Timestamp) -> bool:
    """end ถึงวันทำการสุดท้ายของเดือนแล้วหรือยัง (เดือนที่จบวันหยุดสุดสัปดาห์ก็นับว่าครบ)."""
    last_bday = pd.offsets.BMonthEnd().rollback(end + pd.offsets.MonthEnd(0))
    return end >= last_bday


def month_end_levels(levels: pd.DataFrame | pd.Series, start, end) -> pd.DataFrame | pd.Series:
    """level ณ สิ้นเดือน (ค่าสุดท้ายที่มีจริงในเดือน) ในช่วง [start, end] — ทิ้งเดือนสุดท้ายถ้ายังไม่จบ.

    ใช้กติกาเดียวกันทั้ง macro / MSCI / NAV กอง: ถ้าข้อมูลหมดกลางเดือน ค่า "สิ้นเดือน" ของแต่ละชุดจะเป็นคนละวัน
    (เช่น US10Y ของ FRED ช้ากว่า yfinance 4 วัน) -> return เดือนนั้นเทียบกันไม่ได้ จึงตัดทิ้ง
    """
    end = pd.Timestamp(end)
    m = levels.loc[start:end].resample("ME").last()
    return m if _month_complete(end) else m.iloc[:-1]


def ols_loadings(y: pd.Series, factors: pd.DataFrame,
                 min_obs: int = 0) -> tuple[pd.Series, float, int]:
    """OLS y ~ factors (มี intercept) -> (loading, R², n). n < min_obs -> loading NaN (ไม่ fit).

    ใช้ matching.nested_r2 ที่มีอยู่แล้ว (base ว่าง = โมเดล intercept อย่างเดียว -> R² full คือ R² ปกติ)
    """
    cols = list(factors.columns)
    d = factors.join(y.rename(matching.FUND_COL), how="inner").dropna()
    if len(d) < max(min_obs, len(cols) + 2):
        return pd.Series(np.nan, index=cols), np.nan, len(d)
    r2, _, coef, _ = matching.nested_r2(d, [], cols)
    return coef, r2, len(d)


def stage1_betas(idx_m: pd.DataFrame, macro_m: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series, pd.Series]:
    """Stage 1: monthly return ของแต่ละ index ~ macro -> (B index×factor, R² ต่อ index, n ต่อ index)."""
    fits = {ix: ols_loadings(idx_m[ix], macro_m) for ix in idx_m.columns}
    B = pd.DataFrame({ix: f[0] for ix, f in fits.items()}).T[list(macro_m.columns)]
    return B, pd.Series({ix: f[1] for ix, f in fits.items()}), pd.Series({ix: f[2] for ix, f in fits.items()})


def unstandardize(coef_std: pd.Series, aligned: pd.DataFrame) -> pd.Series:
    """standardized coef -> coef หน่วยจริง (return กอง ต่อ return index) = coef / σ.

    σ = SD แบบ ddof=0 ของคอลัมน์ใน aligned ชุดเดียวกับที่ fit — ตรงกับ StandardScaler ที่ refit บน X เต็ม
    (คอลัมน์คงที่ StandardScaler ใช้ scale 1 -> ทำเหมือนกัน)
    """
    sd = aligned[coef_std.index].std(ddof=0).replace(0.0, 1.0)
    return coef_std / sd


def implied_loadings(raw_by_scope: dict[str, pd.Series], B: pd.DataFrame) -> pd.Series:
    """Stage 2: chain ทีละ scope (align ตามชื่อ index ไม่ใช่ตำแหน่ง) แล้วเฉลี่ยทุก scope -> loading ต่อ factor."""
    parts = []
    for scope, raw in raw_by_scope.items():
        unknown = sorted(set(raw.index) - set(B.index))
        if unknown:
            raise KeyError(f"{scope}: ไม่มีผล Stage 1 ของ {unknown}")
        parts.append(raw @ B.loc[raw.index])
    return sum(parts) / len(parts)


def implied_fit_r2(fund_m: pd.Series, macro_m: pd.DataFrame, loading: pd.Series,
                   min_obs: int = 0) -> tuple[float, int]:
    """implied อธิบาย return รายเดือนจริงของกองได้แค่ไหน = corr(macro·loading, return)² (ไม่ fit กับกองเลย)."""
    d = macro_m.join(fund_m.rename(matching.FUND_COL), how="inner").dropna()
    if len(d) < max(min_obs, 3):
        return np.nan, len(d)
    pred = d[loading.index].to_numpy() @ loading.to_numpy()
    y = d[matching.FUND_COL].to_numpy()
    if np.std(pred) == 0 or np.std(y) == 0:
        return np.nan, len(d)
    return float(np.corrcoef(pred, y)[0, 1] ** 2), len(d)
