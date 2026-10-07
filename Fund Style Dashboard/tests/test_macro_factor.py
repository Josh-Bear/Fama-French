"""test_macro_factor.py — macro factor ของหน้า 7: สูตร % return vs Δ, FRED ".", snapshot หาย, config."""

import io

import numpy as np
import pandas as pd
import pytest

import config
from data import macro_factor as mf
from data.style_factor import SnapshotMissingError


def test_macro_config_consistent():
    """ทุก factor ต้องมีแหล่งดึงหนึ่งแห่งพอดี และสูตรแปลงหนึ่งแบบพอดี."""
    assert set(config.MACRO_YF_TICKERS) | set(config.MACRO_FRED_SERIES) == set(config.MACRO_FACTOR_COLS)
    assert not set(config.MACRO_YF_TICKERS) & set(config.MACRO_FRED_SERIES)
    assert not set(config.MACRO_RETURN_COLS) & set(config.MACRO_DELTA_COLS)
    assert len(config.MACRO_FACTOR_COLS) == 7


def test_factor_changes_return_vs_delta():
    idx = pd.date_range("2021-01-31", periods=3, freq="ME")
    lv = pd.DataFrame({c: [100.0, 110.0, 99.0] for c in config.MACRO_RETURN_COLS}
                      | {"VIX": [20.0, 25.0, 15.0], "US10Y": [4.78, 4.80, 4.50]}, index=idx)
    out = mf.to_factor_changes(lv)
    assert list(out.columns) == config.MACRO_FACTOR_COLS
    assert len(out) == 2                                        # เดือนแรกไม่มี return
    assert np.allclose(out["Oil_Brent"], [0.10, -0.10])         # ราคา -> % return
    assert np.allclose(out["VIX"], [5.0, -10.0])                # index -> Δ จุด
    assert np.allclose(out["US10Y"], [0.02, -0.30])             # yield -> Δ pp (ไม่ใช่ +0.42%)


def test_parse_fred_dot_is_nan():
    csv = io.StringIO("observation_date,DGS10\n2021-01-04,0.93\n2021-01-05,.\n2021-01-06,0.96\n")
    s = mf.parse_fred_csv(csv, "DGS10")
    assert s.index[0] == pd.Timestamp("2021-01-04")
    assert np.isnan(s.iloc[1]) and s.iloc[2] == 0.96


def test_load_snapshot_missing(monkeypatch, tmp_path):
    """ไม่มี snapshot -> SnapshotMissingError (ชนิดเดียวกับหน้า 6) พร้อมบอกคำสั่ง."""
    monkeypatch.setattr(config, "MACRO_FACTOR_CSV", str(tmp_path / "nope.csv"))
    with pytest.raises(SnapshotMissingError, match="macro-download"):
        mf.load_snapshot()
