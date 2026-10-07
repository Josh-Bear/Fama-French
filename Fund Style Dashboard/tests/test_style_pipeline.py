"""test_style_pipeline.py — scope "style" ของหน้า 6: ป้ายตามเครื่องหมาย, incremental R², control ไม่ถูกนับ, E-only."""

import numpy as np
import pandas as pd
import pytest

import config
import data_access
from analysis import matching
from data import style_factor as sf


def test_style_label_uses_sign():
    assert sf.style_label("Value", 0.5) == "Value"
    assert sf.style_label("Value", -0.5) == "Growth"          # กอง growth ต้องไม่ถูกเรียก Value
    assert sf.style_label("LowVol", -0.1) == "High-Beta"
    assert sf.style_label("Quality", -0.2) == "Junk"
    assert sf.style_label(None, 0.1) is None


def test_nested_r2_non_negative_and_detects_extra():
    rng = np.random.default_rng(0)
    n = 500
    base, extra, noise = rng.normal(0, 0.01, n), rng.normal(0, 0.01, n), rng.normal(0, 0.002, n)
    df = pd.DataFrame({"B": base, "E": extra})

    df[matching.FUND_COL] = 1.0 * base + 0.8 * extra + noise      # extra อธิบายเพิ่มจริง
    r2_full, r2_base, coef, coef_base = matching.nested_r2(df, ["B"], ["E"])
    assert r2_full >= r2_base and r2_full - r2_base > 0.3
    assert abs(coef["E"] - 0.8) < 0.05
    assert list(coef_base.index) == ["B"] and abs(coef_base["B"] - 1.0) < 0.05   # coef ของโมเดล base แยกออกมา

    df[matching.FUND_COL] = 1.0 * base + noise                    # extra ไม่มีส่วนเลย
    r2_full, r2_base, _, _ = matching.nested_r2(df, ["B"], ["E"])
    assert 0 <= r2_full - r2_base < 0.01


def _regressors(n=700, seed=1):
    rng = np.random.default_rng(seed)
    cols = config.STYLE_CONTROL_COLS + config.STYLE_FACTOR_COLS
    levels = 100 * np.exp(np.cumsum(rng.normal(0, 0.01, (n, len(cols))), axis=0))
    return pd.DataFrame(levels, index=pd.bdate_range("2021-01-01", periods=n), columns=cols)


def test_control_never_primary_and_signed_label():
    """กองที่ตามตลาดแรงมาก + tilt Value ติดลบ -> primary ต้องเป็น style (ไม่ใช่ MSCI_ACWI) และได้ป้าย Growth."""
    regs = _regressors()
    r = regs.pct_change()
    noise = np.random.default_rng(2).normal(0, 0.001, len(r))
    fund_ret = (1.0 * r["MSCI_ACWI"] - 0.6 * r["Value"]).fillna(0) + noise
    nav = 10 * (1 + fund_ret).cumprod()

    row, _ = data_access.style_match_one(nav, regs)
    assert row["style_primary_factor"] == "Value"
    assert row["style_primary"] == "Growth"
    assert row["style_r2"] > 0.1                               # style อธิบายเพิ่มจากตลาดจริง
    assert abs(row["mkt_beta"] - 1.0) < 0.1


def _lvl(r):
    return 100 * np.cumprod(1 + r)


def test_mkt_beta_is_total_market_beta():
    """กองถือ low-vol ETF (beta 0.6): mkt_beta ต้อง ≈ 0.6 ไม่ใช่ partial beta ~1 ของโมเดลเต็ม.

    LowVol_rel = ACWV÷ACWI มีขา −ACWI ในตัว -> ในโมเดลเต็ม กอง = ตลาด×1 + LowVol_rel×1 (coef ตลาดถูกดันไป ~1)
    ตลาดสองโลก corr กันแต่ไม่เท่ากัน (เหมือนข้อมูลจริง) — test เดิมใช้ random walk อิสระจึงจับไม่ได้
    """
    rng = np.random.default_rng(3)
    n = 700
    r_msci = rng.normal(0, 0.01, n)
    r_etf = 0.8 * r_msci + rng.normal(0, 0.006, n)
    r_acwv = 0.6 * r_etf + rng.normal(0, 0.003, n)
    regs = pd.DataFrame({
        "MSCI_ACWI": _lvl(r_msci), "US_VS_ACWI": _lvl(rng.normal(0, 0.003, n)), "ACWI_ETF": _lvl(r_etf),
        "Momentum": _lvl(rng.normal(0, 0.004, n)), "Quality": _lvl(rng.normal(0, 0.004, n)),
        "Value": _lvl(rng.normal(0, 0.004, n)), "LowVol": _lvl(r_acwv) / _lvl(r_etf),
    }, index=pd.bdate_range("2021-01-01", periods=n))[config.STYLE_CONTROL_COLS + config.STYLE_FACTOR_COLS]
    nav = pd.Series(10 * np.cumprod(1 + r_acwv + rng.normal(0, 0.001, n)), index=regs.index)

    row, _ = data_access.style_match_one(nav, regs)
    assert row["style_primary"] == "Low-Vol"
    assert abs(row["mkt_beta"] - 0.6) < 0.1


def test_style_config_consistent():
    """config ต้องสอดคล้องกัน — ไม่งั้น style_match_one KeyError ทุกกอง -> ทุกกองถูกข้าม."""
    assert set(config.STYLE_MARKET_COLS) <= set(config.STYLE_CONTROL_COLS)
    assert set(config.STYLE_LABELS) == set(config.STYLE_FACTOR_COLS) == set(config.STYLE_TICKERS)
    assert not set(config.STYLE_CONTROL_COLS) & set(config.STYLE_FACTOR_COLS)


def test_write_cache_refuses_empty(tmp_path):
    """ทุกกองพลาด -> raise ไม่เขียน CSV เปล่า (อ่านกลับไม่ได้ + loader ไม่ build ใหม่เพราะไฟล์มีแล้ว)."""
    res_path = tmp_path / "r.csv"
    with pytest.raises(RuntimeError):
        data_access._write_cache(pd.DataFrame(), pd.DataFrame(), str(res_path), str(tmp_path / "c.csv"),
                                 [("F1", "boom")])
    assert not res_path.exists()


def test_style_universe_is_equity_only():
    res = pd.DataFrame({"FundCode": ["B", "A", "C", "D"], "policy": ["E", "E", "F", "O"]})
    assert data_access.style_universe(res) == ["A", "B"]      # F/O ไม่หลุดเข้ามา
