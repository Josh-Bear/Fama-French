"""test_fund_weighting.py — คัดกอง/น้ำหนัก/trend filter ของโมเดลหน้า 9."""

import numpy as np
import pandas as pd
import pytest

import config
from analysis import fund_weighting as fw


def _reps(n):
    return {f"F{i}": {"FundCode": f"F{i}-A", "signal": float(n - i), "vol52": 0.2} for i in range(n)}


def test_rank_breaks_ties_by_lower_vol_then_name():
    reps = {"a": {"FundCode": "Z", "signal": 1.0, "vol52": 0.3}, "b": {"FundCode": "Y", "signal": 1.0, "vol52": 0.1},
            "c": {"FundCode": "X", "signal": np.nan, "vol52": 0.1}}
    assert fw.rank_families(reps) == {"b": 1, "a": 2, "c": 3}


def test_hysteresis_keeps_held_funds_within_k_and_fills_to_n():
    reps = _reps(20)
    ranks = fw.rank_families(reps)
    held = {"F15": "F15-A", "F17": "F17-A"}                # อันดับ 16 = คงไว้ · อันดับ 18 = หลุด
    sel = fw.hysteresis_select(reps, ranks, held, n_target=8, k_drop=16)
    assert sel["kept"] == ["F15"] and len(sel["S"]) == 8
    assert set(sel["S"]) == {"F15", "F0", "F1", "F2", "F3", "F4", "F5", "F6"}
    assert sel["fallback"] is None


def test_hysteresis_does_not_keep_a_held_fund_whose_class_changed():
    reps = _reps(10)
    sel = fw.hysteresis_select(reps, fw.rank_families(reps), {"F9": "F9-D"}, n_target=3, k_drop=16)
    assert sel["kept"] == []


def test_hysteresis_falls_back_when_too_few_families():
    reps = _reps(config.TF_MIN_FUNDS - 1)
    assert fw.hysteresis_select(reps, fw.rank_families(reps), {})["fallback"] == "b0"


def test_family_representative_prefers_the_held_class():
    df = pd.DataFrame({"family": ["X", "X"], "FundCode": ["X-A", "X-H"], "SR12": [0.5, 0.9], "vol52": [0.2, 0.2]})
    assert fw.family_representatives(df, set())["X"]["FundCode"] == "X-H"
    assert fw.family_representatives(df, {"X-A"})["X"]["FundCode"] == "X-A"


def test_apply_cap_redistributes_excess_proportionally():
    w = fw.apply_cap(pd.Series({"a": 0.5, "b": 0.3, "c": 0.1, "d": 0.1}), cap=0.4)
    assert w.sum() == pytest.approx(1.0) and w["a"] == pytest.approx(0.4)
    assert w["b"] / w["c"] == pytest.approx(3.0)            # ส่วนเกินแจกตามสัดส่วนเดิม


def test_erc_equalizes_risk_contribution():
    rng = np.random.default_rng(0)
    a = rng.normal(size=(500, 3)) @ np.array([[1, 0.3, 0.1], [0, 1, 0.4], [0, 0, 1]]) * [0.01, 0.02, 0.04]
    sigma = np.cov(a, rowvar=False)
    w = fw.erc_weights(sigma, ["a", "b", "c"]).to_numpy()
    rc = w * (sigma @ w)
    assert np.allclose(rc / rc.sum(), 1 / 3, atol=1e-4) and w.sum() == pytest.approx(1.0)


def test_risk_parity_uses_inverse_vol_without_enough_common_weeks():
    wk = {"a": pd.Series([0.01] * 10), "b": pd.Series([0.02] * 10)}
    w, src = fw.risk_parity_weights(["a", "b"], wk, {"a": 0.1, "b": 0.2})
    assert src == "ivol" and w["a"] == pytest.approx(2 / 3)


def test_trend_state_holds_cash_only_below_the_sma():
    idx = pd.bdate_range("2024-01-01", periods=config.TF_TREND_SMA + 10)
    up = pd.Series(np.linspace(100, 200, len(idx)), index=idx)
    assert fw.trend_state(up, idx[-1])["cash"] == 0.0
    down = pd.Series(np.linspace(200, 100, len(idx)), index=idx)
    s = fw.trend_state(down, idx[-1])
    assert s["below"] and s["cash"] == config.TF_TREND_CASH
    assert fw.trend_state(up, idx[50])["cash"] == 0.0       # ประวัติไม่ถึง SMA วัน -> ไม่ถือเงินสด
