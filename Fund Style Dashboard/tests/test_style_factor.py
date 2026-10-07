"""test_style_factor.py — การสร้าง style factor ของหน้า 6 (de-market, blend, ค่าเงิน, ปฏิทิน)."""

import numpy as np
import pandas as pd

import config
from data import style_factor as sf


def _etf(n=300, seed=0):
    """ราคา ETF สมมติแบบ random walk ครบทุก ticker ที่ config ต้องใช้."""
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2021-01-01", periods=n)
    ticks = sf._all_tickers()
    levels = 100 * np.exp(np.cumsum(rng.normal(0, 0.01, (n, len(ticks))), axis=0))
    return pd.DataFrame(levels, index=dates, columns=ticks)


def test_columns_start_and_no_nan():
    lv = sf.build_style_levels(_etf())
    assert list(lv.columns) == config.STYLE_FACTOR_COLS
    assert np.allclose(lv.iloc[0].to_numpy(), 1.0)
    assert lv.isna().sum().sum() == 0


def test_relative_return_formula():
    """return ของ relative level = (1 + w·r_US + (1−w)·r_Intl) / (1 + r_ACWI) − 1 เป๊ะ."""
    etf, w = _etf(), 0.6
    lv = sf.build_style_levels(etf, us_weight=w)
    r = etf.pct_change()
    expected = (1 + w * r["MTUM"] + (1 - w) * r["IMTM"]) / (1 + r["ACWI"]) - 1
    assert np.allclose(lv["Momentum"].pct_change().iloc[1:], expected.iloc[1:])


def test_lowvol_is_acwv_over_acwi():
    etf = _etf()
    ratio = etf["ACWV"] / etf["ACWI"]
    assert np.allclose(sf.build_style_levels(etf)["LowVol"], ratio / ratio.iloc[0])


def test_fx_cancels():
    """แปลงทุก ETF เป็นอีกสกุลด้วย FX เดียวกัน -> relative level ต้องเท่าเดิม (USD÷USD หักล้าง)."""
    etf = _etf()
    rng = np.random.default_rng(9)
    fx = pd.Series(35 * np.exp(np.cumsum(rng.normal(0, 0.005, len(etf)))), index=etf.index)
    a = sf.build_style_levels(etf)
    b = sf.build_style_levels(etf.mul(fx, axis=0))
    assert np.allclose(a.to_numpy(), b.to_numpy())


def test_late_starting_ticker_is_trimmed():
    """ticker เริ่มช้ากว่าตัวอื่น -> ตัดแถวต้นทิ้ง ไม่ปล่อยให้ level แบนปลอมขณะ benchmark ขยับ."""
    etf = _etf()
    etf.iloc[:5, etf.columns.get_loc("MTUM")] = np.nan
    lv = sf.build_style_levels(etf)
    assert lv.index.min() == etf.index[5]


def test_early_ending_ticker_is_trimmed():
    """ticker หมดก่อนตัวอื่น -> ตัดปลายทิ้ง ไม่ ffill ต่อเป็น level แบน (relative return จะกลายเป็น −ACWI ปลอม)."""
    etf = _etf()
    etf.iloc[-7:, etf.columns.get_loc("MTUM")] = np.nan
    lv = sf.build_style_levels(etf)
    assert lv.index.max() == etf.index[-8]
    assert lv.isna().sum().sum() == 0


def test_combine_levels_trims_and_ffills():
    """ปฏิทินต่างกัน: วันหยุด US -> ffill · ตัดปลายที่ชุดที่หมดก่อน · ไม่มี NaN."""
    wk = pd.bdate_range("2021-01-01", "2021-03-31")                      # MSCI: ทุก weekday
    msci = pd.DataFrame({"A": np.arange(len(wk), dtype=float) + 1}, index=wk)
    nyse = wk.delete([10, 11])                                            # ETF: หยุด 2 วัน
    etf = pd.DataFrame({"B": np.arange(len(nyse), dtype=float) + 1}, index=nyse).loc[:"2021-03-15"]
    out = sf.combine_levels(msci, etf)
    assert out.isna().sum().sum() == 0
    assert out.index.max() == pd.Timestamp("2021-03-15")                 # ETF หมดก่อน -> ตัดตรงนั้น
    assert out.loc[wk[10], "B"] == out.loc[wk[9], "B"]                   # วันหยุด US -> ราคาเดิม


def test_assemble_regressors_order_and_etf_market():
    """ครบ control ×3 + style ×4 เรียงตาม config · ACWI_ETF = ราคา ACWI ETF ดิบ (USD) · ไม่มี NaN."""
    etf = _etf()
    msci = pd.DataFrame({"MSCI_ACWI": np.linspace(100, 120, len(etf)),
                         "US_VS_ACWI": np.linspace(1.0, 1.1, len(etf))}, index=etf.index)
    out = sf.assemble_regressors(msci, etf)
    assert list(out.columns) == config.STYLE_CONTROL_COLS + config.STYLE_FACTOR_COLS
    assert np.allclose(out["ACWI_ETF"], etf["ACWI"].loc[out.index])
    assert out.isna().sum().sum() == 0


def test_controls_from_base_data():
    """control ฝั่ง MSCI = MSCI_ACWI + US÷ACWI จากไฟล์ MSCI (THB)."""
    ctrl = sf.build_controls()
    assert list(ctrl.columns) == ["MSCI_ACWI", "US_VS_ACWI"]
    from data import msci_index
    cty = msci_index.load_country_index()
    assert np.allclose(ctrl["US_VS_ACWI"], cty["MSCI_USA"] / cty["MSCI_ACWI"])
