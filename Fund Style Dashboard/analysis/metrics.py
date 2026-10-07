"""metrics.py — annualized return / volatility.

**ซีรีส์รายวันครบทุกวัน (ดัชนี MSCI)** — annualize ด้วย config.TRADING_DAYS (252):
- annualized_return = (∏(1+r))^(252/n) − 1   (geometric, ทบต้น)
- annualized_volatility = std(r, ddof=1) × √252

**NAV กอง (รายงานไม่ครบทุกวัน ~74% ของวันทำการ MSCI)** — ห้ามใช้ 252/n (ทบต้นเกินจริง ~1.35 เท่า):
- cagr = (NAV สุดท้าย ÷ NAV แรก)^(365.25 / จำนวนวันปฏิทิน) − 1
- irregular_annualized_volatility = std(r, ddof=1) × √(จำนวนจุดต่อปีจริง)
  จำนวนจุดต่อปี = จำนวน return ÷ (ผลรวมวันปฏิทินที่ return เหล่านั้นครอบคลุม ÷ 365.25)
"""

from __future__ import annotations

import numpy as np
import pandas as pd

import config


def annualized_return(returns: pd.Series) -> float:
    """geometric annualized return จาก return series ของกอง."""
    r = returns.dropna()
    if len(r) == 0:
        return np.nan
    growth = float((1.0 + r).prod())
    if growth <= 0:
        return np.nan  # NAV ติดลบ/ผิดปกติ — กันรากของเลขติดลบ
    return growth ** (config.TRADING_DAYS / len(r)) - 1.0


def annualized_volatility(returns: pd.Series) -> float:
    """annualized volatility = std(daily, ddof=1) × √252."""
    r = returns.dropna()
    if len(r) < 2:
        return np.nan
    return float(r.std(ddof=1) * np.sqrt(config.TRADING_DAYS))


def recent_return(series: pd.Series, window: int | None = None,
                  max_gap_days: int | None = -1, skip: int = 0) -> float:
    """cumulative return ดิบ (ไม่ annualize) ของ window ค่าล่าสุด — ใช้ได้ทั้ง price level และ NAV.

    series : ราคา/NAV (ไม่ใช่ return) index=วันที่
    ต้องมีอย่างน้อย window+1 จุด ไม่งั้นคืน NaN (กันกองใหม่/ข้อมูลสั้น)

    sort_index() เสมอ — ป้องกัน series ดิบที่ยังไม่เรียงตามวันที่ (เช่นที่ได้จาก groupby)
    ถ้าไม่เรียง iloc[-1] / iloc[-(window+1)] จะไม่ใช่จุดล่าสุด/จุดที่ต้องการจริง

    ⚠️ สำหรับกองทุน นี่คือ "ย้อนไป window observation" ไม่ใช่ "window วันทำการตามปฏิทิน"
       กองที่รายงาน NAV ไม่ครบทุกวันจะคลาดเคลื่อนไปบ้าง (ข้อจำกัดเดียวกับ n_obs ที่ document ไว้แล้ว)
       ส่วน index MSCI ไม่มีปัญหานี้เพราะข้อมูลครบทุกวันทำการ

    เพิ่ม (2026-09-09): ถ้าช่วงปฏิทินจริงของ window+1 จุดล่าสุด (ปลาย−ต้น เป็นวัน) ยาวเกิน
    config.RECENT_RETURN_MAX_GAP_DAYS -> คืน NaN แทน แปลว่ากองนั้นรายงาน NAV ห่างเกินไปในช่วงนี้
    จนตัวเลข "return 21 วัน" ที่ได้จริง ๆ ครอบคลุมหลายเดือน ไม่ใช่ ~1 เดือนตามที่ตั้งใจ (เทียบกับ
    index ที่ไม่มีปัญหานี้เพราะข้อมูลครบทุกวันทำการ) เกณฑ์ 42 วัน validate จาก distribution จริงของ
    368 กอง — ดู comment ที่ config.RECENT_RETURN_MAX_GAP_DAYS
    """
    window = config.RECENT_RETURN_WINDOW if window is None else window
    # skip: ข้าม observation ล่าสุดกี่จุด (momentum แบบ 12-1 ใช้ skip=21) -> วัดจาก t−window ถึง t−skip
    # max_gap_days: -1 (default) = ใช้ค่า config · None = ไม่เช็คเลย (index ที่ข้อมูลครบทุกวันทำการ
    # เช่น window 252 ซึ่งกินเวลาจริง ~365 วันปฏิทิน เกินเกณฑ์ 60 วันเสมอ ทั้งที่ไม่ได้ขาดข้อมูล)
    max_gap_days = config.RECENT_RETURN_MAX_GAP_DAYS if max_gap_days == -1 else max_gap_days
    s = series.sort_index().dropna()
    if len(s) < window + 1:
        return np.nan
    start_date, end_date = s.index[-(window + 1)], s.index[-(skip + 1)]
    if max_gap_days is not None and (end_date - start_date).days > max_gap_days:
        return np.nan
    return float(s.iloc[-(skip + 1)] / s.iloc[-(window + 1)] - 1.0)


def cagr(nav: pd.Series) -> float:
    """CAGR จาก NAV จุดแรกถึงจุดสุดท้าย ตามจำนวนวันปฏิทินจริง (index = วันที่)."""
    s = nav.dropna().sort_index()
    if len(s) < 2:
        return np.nan
    days = (s.index[-1] - s.index[0]).days
    if days <= 0 or s.iloc[0] <= 0 or s.iloc[-1] <= 0:
        return np.nan
    return float((s.iloc[-1] / s.iloc[0]) ** (config.DAYS_PER_YEAR / days) - 1.0)


def periods_per_year(interval_days: pd.Series) -> float:
    """จำนวน observation ต่อปีจริง จากความยาว (วันปฏิทิน) ของแต่ละช่วง return."""
    d = interval_days.dropna()
    total = float(d.sum())
    if len(d) == 0 or total <= 0:
        return np.nan
    return len(d) / (total / config.DAYS_PER_YEAR)


def irregular_annualized_volatility(returns: pd.Series, interval_days: pd.Series) -> float:
    """std(r, ddof=1) × √(periods_per_year) — สำหรับ return ที่ห่างไม่เท่ากัน (NAV กอง)."""
    r = returns.dropna()
    if len(r) < 2:
        return np.nan
    ppy = periods_per_year(interval_days.reindex(r.index))
    return float(r.std(ddof=1) * np.sqrt(ppy))
