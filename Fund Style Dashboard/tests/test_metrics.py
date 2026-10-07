"""test_metrics.py — Phase 4 ด้วย fixture ที่คำนวณมือได้ (เร็ว)."""

import numpy as np
import pandas as pd

import config
from analysis import metrics


def test_trading_days_convention():
    assert config.TRADING_DAYS == 252


def test_constant_return_series():
    """return คงที่ 1%/period, n periods -> ann_return = 1.01^252 - 1, vol = 0."""
    r = pd.Series([0.01] * 60)
    assert abs(metrics.annualized_return(r) - (1.01 ** config.TRADING_DAYS - 1)) < 1e-9
    assert metrics.annualized_volatility(r) < 1e-12


def test_annret_matches_growth_formula():
    """เทียบกับสูตร (NAV_end/NAV_start)^(252/n) - 1 จาก NAV series."""
    nav = pd.Series([10, 10.5, 10.2, 11.0, 11.3, 10.9])
    r = nav.pct_change().dropna()
    growth = nav.iloc[-1] / nav.iloc[0]
    expected = growth ** (config.TRADING_DAYS / len(r)) - 1
    assert abs(metrics.annualized_return(r) - expected) < 1e-9


def test_edge_cases():
    assert np.isnan(metrics.annualized_return(pd.Series([], dtype=float)))
    assert np.isnan(metrics.annualized_volatility(pd.Series([0.01])))  # <2 obs


def test_recent_return():
    """cumulative return ดิบของ window ล่าสุด + ต้อง sort เองได้ + ข้อมูลสั้นคืน NaN."""
    idx = pd.bdate_range("2021-01-01", periods=30)
    s = pd.Series(range(100, 130), index=idx, dtype=float)
    # series 30 ตัว (100..129): จุดสุดท้าย=129, ย้อนไป 21 จุด = iloc[-22] = ตำแหน่ง 8 = 108
    assert abs(metrics.recent_return(s, 21) - (129 / 108 - 1)) < 1e-12
    # สลับลำดับแล้วต้องได้ค่าเดิม (sort_index ภายใน)
    assert abs(metrics.recent_return(s.sample(frac=1, random_state=0), 21)
               - metrics.recent_return(s, 21)) < 1e-12
    # ข้อมูลน้อยกว่า window+1 -> NaN
    assert np.isnan(metrics.recent_return(s.iloc[:10], 21))


def test_recent_return_skip_drops_the_latest_month():
    """momentum 12-1 (หน้า 8): วัดจาก t−window ถึง t−skip ไม่ใช่ถึง t — กัน short-term reversal."""
    s = pd.Series(range(1, 302), index=pd.bdate_range("2021-01-01", periods=301), dtype=float)
    # window=252, skip=21 -> s[-22] / s[-253] - 1
    expected = float(s.iloc[-22] / s.iloc[-253] - 1.0)
    assert np.isclose(metrics.recent_return(s, window=252, max_gap_days=None, skip=21), expected)
    # skip=0 ต้องได้ค่าเดิมเหมือนก่อนแก้ (หน้า 5 ไม่กระทบ)
    assert np.isclose(metrics.recent_return(s, window=252, max_gap_days=None),
                      float(s.iloc[-1] / s.iloc[-253] - 1.0))


# --- NAV กองที่รายงานไม่ครบทุกวัน: annualize ด้วยวันปฏิทินจริง ---
def test_cagr_uses_calendar_days():
    """NAV 100 -> 121 ในเวลา 2 ปีปฏิทินพอดี -> CAGR 10% ไม่ว่าจะมีกี่จุดระหว่างทาง."""
    idx = pd.to_datetime(["2022-01-01", "2022-07-01", "2024-01-01"])
    nav = pd.Series([100.0, 105.0, 121.0], index=idx)
    days = (idx[-1] - idx[0]).days
    assert abs(metrics.cagr(nav) - (1.21 ** (config.DAYS_PER_YEAR / days) - 1)) < 1e-12
    assert np.isnan(metrics.cagr(nav.iloc[:1]))


def test_periods_per_year_counts_real_observations():
    """return ทุก 2 วันปฏิทิน -> 365.25/2 จุดต่อปี."""
    assert abs(metrics.periods_per_year(pd.Series([2.0] * 50)) - config.DAYS_PER_YEAR / 2) < 1e-9


def test_irregular_vol_scales_with_observation_frequency():
    """return ชุดเดียวกัน แต่ห่างกัน 2 เท่า -> vol รายปีต่างกัน √2 เท่า."""
    r = pd.Series([0.01, -0.01, 0.02, -0.02, 0.005] * 20)
    v1 = metrics.irregular_annualized_volatility(r, pd.Series(1.0, index=r.index))
    v2 = metrics.irregular_annualized_volatility(r, pd.Series(2.0, index=r.index))
    assert abs(v1 / v2 - np.sqrt(2)) < 1e-9
    assert abs(v1 - r.std(ddof=1) * np.sqrt(config.DAYS_PER_YEAR)) < 1e-12
