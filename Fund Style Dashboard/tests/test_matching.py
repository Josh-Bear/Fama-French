"""test_matching.py — Phase 2-3 ด้วย fixture ที่รู้คำตอบล่วงหน้า (เร็ว ไม่แตะไฟล์จริง)."""

import numpy as np
import pandas as pd

import config
from analysis import matching, metrics
from analysis.matching import FUND_COL


def _fixture(seed=0, n=300, k=5):
    """สร้าง index level 5 ตัวแบบ random walk อิสระ + กองที่ track คอลัมน์ 'C' เป๊ะ."""
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2021-01-01", periods=n)
    cols = list("ABCDE")[:k]
    levels = pd.DataFrame(
        100 * np.exp(np.cumsum(rng.normal(0, 0.01, size=(n, k)), axis=0)),
        index=dates, columns=cols)
    fund_nav = levels["C"].copy()  # กอง track 'C' เป๊ะ
    return fund_nav, levels


def test_build_fund_returns_shape_and_winsor():
    fund_nav, levels = _fixture()
    aligned = matching.build_fund_returns(fund_nav, levels)
    assert FUND_COL in aligned.columns
    assert list(aligned.columns[:-1]) == list(levels.columns)  # index cols ก่อน, fund ท้าย
    assert aligned.isna().sum().sum() == 0
    # winsorize: ค่าไม่หลุด 1st/99th percentile (clip ไม่ drop -> จำนวนแถวเท่ากับ pct_change-1)
    assert len(aligned) == len(fund_nav) - 1


def test_constant_nav_zero_return():
    dates = pd.bdate_range("2021-01-01", periods=50)
    levels = pd.DataFrame({"A": np.linspace(100, 120, 50), "B": np.linspace(50, 40, 50)}, index=dates)
    fund_nav = pd.Series(10.0, index=dates)  # NAV คงที่
    aligned = matching.build_fund_returns(fund_nav, levels)
    assert np.allclose(aligned[FUND_COL].values, 0.0)


def test_match_primary_is_true_index():
    fund_nav, levels = _fixture()
    aligned = matching.build_fund_returns(fund_nav, levels)
    res = matching.match_exposure(aligned)
    assert res["primary"] == "C"       # กอง track 'C' -> primary ต้องเป็น C
    assert res["r2"] > 0.9             # tracking เป๊ะ -> R² สูง


def test_classify_exposure_band():
    """ฟังก์ชันกลาง: primary = |coef| มากสุด, secondary = ตัวที่ >= 70% ของ primary."""
    s = pd.Series({"A": 1.0, "B": -0.80, "C": 0.60, "D": 0.0})
    primary, secondary = matching.classify_exposure(s)
    assert primary == "A"
    assert secondary == ["B"]          # B=80% ผ่าน, C=60% ไม่ผ่าน, D=0 ถูกตัด
    # หลาย secondary ได้
    assert matching.classify_exposure(pd.Series({"A": 1.0, "B": 0.95, "C": 0.75}))[1] == ["B", "C"]
    # coefficient ศูนย์หมด
    assert matching.classify_exposure(pd.Series({"A": 0.0, "B": 0.0})) == (None, [])


def test_get_funds_matching_index():
    """คืนกองที่ index เป็น primary หรือ secondary — และไม่คืนกองที่ index เป็นแค่ 'อื่นๆ'."""
    rows = []
    for fund, vals in {"F1": {"X": 1.0, "Y": 0.9, "Z": 0.1},     # X=primary, Y=secondary
                       "F2": {"X": 0.2, "Y": 1.0, "Z": 0.0}}.items():  # Y=primary, X เป็นอื่นๆ
        for ix, v in vals.items():
            rows.append({"FundCode": fund, "scope": "country", "index": ix, "elastic": v})
    co = pd.DataFrame(rows)
    assert matching.get_funds_matching_index(co, "X", "country") == ["F1"]   # F2 ไม่ติด (X แค่ 20%)
    assert matching.get_funds_matching_index(co, "Y", "country") == ["F1", "F2"]
    assert matching.get_funds_matching_index(co, "Z", "country") == []


def test_get_index_matches_band_pct():
    """band_pct ส่งต่อถึง classify_exposure (หน้า 6 ใช้ STYLE_SECONDARY_BAND_PCT แยกจาก country/sector)."""
    co = pd.DataFrame([{"FundCode": "F1", "scope": "style", "index": ix, "elastic": v}
                       for ix, v in {"X": 1.0, "Y": 0.6}.items()])
    assert matching.get_funds_matching_index(co, "Y", "style") == []                     # default 30%: 60% ไม่ผ่าน
    assert matching.get_funds_matching_index(co, "Y", "style", band_pct=0.5) == ["F1"]   # band 50%: ผ่าน


def test_match_exposure_without_alternatives():
    """alternatives=False ข้าม Lasso/Ridge แต่ ElasticNet (ที่ใช้จัดอันดับ) ต้องได้ผลเดิมเป๊ะ."""
    fund_nav, levels = _fixture()
    aligned = matching.build_fund_returns(fund_nav, levels)
    full, lite = matching.match_exposure(aligned), matching.match_exposure(aligned, alternatives=False)
    assert lite["lasso_coef"] is None and lite["ridge_coef"] is None
    assert lite["primary"] == full["primary"] and np.allclose(lite["coef"], full["coef"])


def test_get_index_matches_returns_role():
    """คืนบทบาทด้วย: index เป็น primary หรือ secondary ของกองนั้น."""
    rows = []
    for fund, vals in {"F1": {"X": 1.0, "Y": 0.9},      # X=primary, Y=secondary
                       "F2": {"X": 0.2, "Y": 1.0}}.items():   # Y=primary, X เป็นอื่นๆ
        for ix, v in vals.items():
            rows.append({"FundCode": fund, "scope": "country", "index": ix, "elastic": v})
    co = pd.DataFrame(rows)
    assert matching.get_index_matches(co, "X", "country").set_index("FundCode")["role"].to_dict() == {"F1": "primary"}
    assert matching.get_index_matches(co, "Y", "country").set_index("FundCode")["role"].to_dict() == {
        "F1": "secondary", "F2": "primary"}
    empty = matching.get_index_matches(co, "Z", "country")
    assert empty.empty and list(empty.columns) == ["FundCode", "role"]   # ว่างแต่คอลัมน์ครบ


def test_fund_return_stats_is_not_inflated_by_sparse_nav():
    """กองโต 10%/ปีแบบทบต้นต่อเนื่อง รายงาน NAV แค่วันเว้นวัน -> CAGR ≈ 10% (สูตร 252/n เดิมจะได้ ~21%)."""
    days = pd.bdate_range("2022-01-03", periods=600)
    lv = pd.DataFrame({"X": np.linspace(100, 110, len(days))}, index=days)
    sparse = days[::2]
    t = (sparse - sparse[0]).days / config.DAYS_PER_YEAR
    nav = pd.Series(100 * 1.10 ** t, index=sparse)
    s = matching.fund_return_stats(nav, lv)
    assert abs(s["ann_return"] - 0.10) < 1e-9
    old = metrics.annualized_return(nav.pct_change().dropna())
    assert old > 0.18                                     # ยืนยันว่าบั๊กเดิมมีจริง (ทบต้นเกิน)
    assert abs(s["periods_per_year"] - config.DAYS_PER_YEAR / ((sparse[-1] - sparse[0]).days / (len(sparse) - 1))) < 1e-6


def test_fund_return_stats_drops_gap_returns_from_vol_but_keeps_them_in_cagr():
    """รู 40 วันทำการ: return ข้ามรู (+50%) ไม่เข้า vol แต่ CAGR ยังนับ (ผลที่นักลงทุนได้จริง)."""
    days = pd.bdate_range("2022-01-03", periods=300)
    lv = pd.DataFrame({"X": np.linspace(100, 110, len(days))}, index=days)
    navd = list(days[:100]) + list(days[140:])
    vals = [100.0] * 100 + [150.0] * 160
    nav = pd.Series(vals, index=pd.DatetimeIndex(navd))
    s = matching.fund_return_stats(nav, lv)
    assert s["ann_vol"] < 1e-9                            # มีแค่ return 0 นอกจุดที่คร่อมรู
    assert s["ann_return"] > 0.4


def test_fund_return_stats_vol_is_robust_to_a_single_nav_glitch():
    """NAV พลาดวันเดียว (−56% แล้ว +152%) ต้องไม่ทำให้ vol พุ่ง — winsorize 1–99% แบบเดียวกับ regression."""
    days = pd.bdate_range("2022-01-03", periods=600)
    lv = pd.DataFrame({"X": np.linspace(100, 110, len(days))}, index=days)
    rng = np.random.default_rng(0)
    nav = pd.Series(100 * np.cumprod(1 + rng.normal(0, 0.01, len(days))), index=days)
    clean = matching.fund_return_stats(nav, lv)["ann_vol"]
    bad = nav.copy()
    bad.iloc[300] *= 0.44                                   # glitch วันเดียว แล้วกลับมาเท่าเดิมวันถัดไป
    glitch = matching.fund_return_stats(bad, lv)["ann_vol"]
    assert glitch < clean * 1.2
