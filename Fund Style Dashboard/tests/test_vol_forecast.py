"""test_vol_forecast.py — Phase Vol Forecast (EWMA/GARCH/walk-forward/metrics) fixtures ที่รู้คำตอบ."""

import numpy as np
import pandas as pd

import config
from analysis import vol_forecast as vf


def _normal_returns(sigma_daily=0.01, n=1500, seed=0):
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2021-01-01", periods=n)
    return pd.Series(rng.normal(0, sigma_daily, n), index=dates)


def test_realized_vol_matches_formula():
    r = _normal_returns()
    expected = r.std(ddof=1) * np.sqrt(config.TRADING_DAYS)
    assert abs(vf.realized_vol(r) - expected) < 1e-12


def test_ewma_recovers_constant_vol():
    """iid N(0, 0.01²) -> true annualized vol ≈ 0.01×√252 ≈ 0.159; EWMA ควรอยู่ใกล้เคียง."""
    r = _normal_returns(sigma_daily=0.01, n=2000)
    est = vf.ewma_forecast(r)
    assert 0.10 < est < 0.24     # หลวมพอรับ noise ของ EWMA แต่จับ scale ถูก


def test_garch_positive_and_fallback():
    """GARCH คืน vol เป็นบวก finite เสมอ (รวม path fallback เมื่อ fit ไม่ผ่าน)."""
    vol, fb = vf.garch_forecast(_normal_returns(n=800))
    assert np.isfinite(vol) and vol > 0 and isinstance(fb, bool)
    # series ผันผวนน้อยมาก (เกือบคงที่) -> fit อาจไม่ converge -> ต้อง fallback ไม่ crash
    tiny = _normal_returns(sigma_daily=1e-6, n=400)
    vol2, fb2 = vf.garch_forecast(tiny)
    assert np.isfinite(vol2) and vol2 > 0


def test_walk_forward_window_count():
    """จำนวน window = floor((n - horizon - min_train)/step) + 1 (เฉพาะ window ที่มีอนาคตครบ)."""
    n, mt, step, hz = 400, 252, 21, 21
    r = _normal_returns(n=n)
    df = vf.walk_forward_backtest(r, "TEST", min_train=mt, step=step, horizon=hz)
    expected = (n - hz - mt) // step + 1
    assert len(df) == expected
    assert set(df.columns) >= {"index", "window_start", "window_end",
                               "ewma_forecast", "garch_forecast", "garch_fallback", "realized_vol"}
    assert (df["realized_vol"] > 0).all()


def test_evaluation_metrics_toy():
    """toy: ewma/garch forecast=[0.2,0.3], realized=[0.1,0.3] -> คำนวณมือเทียบ."""
    df = pd.DataFrame({
        "index": ["X", "X"],
        "ewma_forecast": [0.2, 0.3], "garch_forecast": [0.2, 0.3],
        "realized_vol": [0.1, 0.3],
    })
    m = vf.evaluation_metrics(df)
    row = m[(m["index"] == "ALL") & (m["model"] == "ewma")].iloc[0]
    assert abs(row["RMSE"] - np.sqrt((0.01 + 0.0) / 2)) < 1e-9      # sqrt(mean([0.1²,0]))
    assert abs(row["MAE"] - 0.05) < 1e-9                            # mean([0.1,0])
    fv = np.array([0.04, 0.09]); av = np.array([0.01, 0.09])
    assert abs(row["QLIKE"] - np.mean(av / fv + np.log(fv))) < 1e-9
    assert row["n"] == 2
