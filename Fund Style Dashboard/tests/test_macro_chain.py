"""test_macro_chain.py — คณิตหน้า 7: เดือนไม่ครบ, unstandardize, chain ตาม label + เฉลี่ย scope, OLS guard."""

import numpy as np
import pandas as pd
import pytest

import config
import data_access
from analysis import macro_chain as mc
from analysis import matching


def _daily(end, start="2021-01-01"):
    d = pd.bdate_range(start, end)
    return pd.DataFrame({"A": np.arange(len(d), dtype=float) + 1}, index=d)


def test_month_end_drops_incomplete_month():
    assert mc.month_end_levels(_daily("2021-03-15"), "2021-01-01", "2021-03-15").index[-1] == pd.Timestamp("2021-02-28")
    assert mc.month_end_levels(_daily("2021-03-31"), "2021-01-01", "2021-03-31").index[-1] == pd.Timestamp("2021-03-31")
    # 2021-10-31 = วันอาทิตย์ · วันทำการสุดท้าย 29 ต.ค. -> เดือน ต.ค. ต้องนับว่าครบ
    assert mc.month_end_levels(_daily("2021-10-29"), "2021-01-01", "2021-10-29").index[-1] == pd.Timestamp("2021-10-31")


def test_unstandardize_recovers_raw_beta():
    """standardized coef จาก pipeline จริง (StandardScaler + ElasticNet) ÷ σ -> beta หน่วยจริง."""
    rng = np.random.default_rng(0)
    n = 800
    X = pd.DataFrame({"A": rng.normal(0, 0.02, n), "B": rng.normal(0, 0.005, n)})   # สเกลต่างกัน 4 เท่า
    X[matching.FUND_COL] = 0.9 * X["A"] - 0.5 * X["B"] + rng.normal(0, 0.0005, n)
    res = matching.match_exposure(X, alternatives=False)
    raw = mc.unstandardize(res["coef"], X)
    assert abs(raw["A"] - 0.9) < 0.02 and abs(raw["B"] + 0.5) < 0.03
    assert abs(res["coef"]["A"] - 0.9) > 0.5      # ตัว standardized ห่างจาก beta จริงมาก -> ต้องแปลงก่อน chain


def _B():
    return pd.DataFrame(np.arange(28, dtype=float).reshape(4, 7) / 10,
                        index=["A", "B", "C", "D"], columns=config.MACRO_FACTOR_COLS)


def test_implied_label_aligned_and_scope_average():
    B = _B()
    raw = {"country": pd.Series({"B": 1.0, "A": 0.0}), "sector": pd.Series({"D": 1.0, "C": 0.0})}
    out = mc.implied_loadings(raw, B)
    assert np.allclose(out, (B.loc["B"] + B.loc["D"]) / 2)
    shuffled = {"country": raw["country"][["A", "B"]], "sector": raw["sector"][["C", "D"]]}
    assert np.allclose(mc.implied_loadings(shuffled, B.iloc[::-1]), out)   # ลำดับแถว/คอลัมน์ไม่มีผล


def test_implied_not_double_counted():
    """กอง = index เดียวกันทั้งสอง scope -> loading = แถว B นั้น (ไม่ใช่ 2 เท่าแบบรวม 28 ตัว)."""
    B = _B()
    B.loc["C"] = B.loc["A"]
    raw = {"country": pd.Series({"A": 1.0, "B": 0.0}), "sector": pd.Series({"C": 1.0, "D": 0.0})}
    assert np.allclose(mc.implied_loadings(raw, B), B.loc["A"])


def test_implied_unknown_index_raises():
    with pytest.raises(KeyError):
        mc.implied_loadings({"country": pd.Series({"Z": 1.0})}, _B())


def _macro_m(n=66, seed=0):
    rng = np.random.default_rng(seed)
    return pd.DataFrame(rng.normal(0, 0.05, (n, 7)), columns=config.MACRO_FACTOR_COLS,
                        index=pd.date_range("2021-02-28", periods=n, freq="ME"))


def test_ols_loadings_recovers_and_guards():
    m = _macro_m()
    true = pd.Series(np.linspace(-0.5, 0.5, 7), index=m.columns)
    y = m @ true + np.random.default_rng(1).normal(0, 0.001, len(m))
    coef, r2, n = mc.ols_loadings(y, m)
    assert n == 66 and r2 > 0.99 and np.allclose(coef, true, atol=0.01)
    coef, r2, n = mc.ols_loadings(y.iloc[:30], m, min_obs=36)
    assert coef.isna().all() and np.isnan(r2) and n == 30


def test_stage1_shape_and_values():
    m = _macro_m()
    idx = pd.DataFrame({"X": 0.4 * m["Oil_Brent"], "Y": -m["VIX"]}, index=m.index)
    B, r2, n = mc.stage1_betas(idx, m)
    assert list(B.index) == ["X", "Y"] and list(B.columns) == config.MACRO_FACTOR_COLS
    assert abs(B.loc["X", "Oil_Brent"] - 0.4) < 1e-9 and (n == 66).all() and (r2 > 0.999).all()


def _synthetic_fund():
    """กอง = index A (country) = C (sector, สำเนาของ A) · B, D อิสระ."""
    rng = np.random.default_rng(4)
    d = pd.bdate_range("2021-01-01", "2025-12-31")
    lvA, lvB, lvD = (100 * np.cumprod(1 + rng.normal(0, 0.01, len(d))) for _ in range(3))
    levels = {"country": pd.DataFrame({"A": lvA, "B": lvB}, index=d),
              "sector": pd.DataFrame({"C": lvA, "D": lvD}, index=d)}
    nav = pd.Series(lvA / 10, index=d)
    coef_std = {s: matching.match_exposure(matching.build_fund_returns(nav, lv), alternatives=False)["coef"]
                for s, lv in levels.items()}
    return nav, levels, coef_std


def test_macro_match_one_end_to_end():
    """ต่อจาก coef มาตรฐานจริงของ pipeline -> implied ≈ แถว B ของ index ที่กองถือ · impact = loading × σ."""
    nav, levels, coef_std = _synthetic_fund()
    B = _B()
    B.loc["C"] = B.loc["A"]
    m = _macro_m(n=59)                                  # ก.พ. 2021 – ธ.ค. 2025
    df = pd.DataFrame(data_access.macro_match_one(nav, coef_std, levels, B, m, "2021-01-01", "2025-12-31"))
    imp = df[df["method"] == "implied"].set_index("factor")
    assert np.allclose(imp["loading"].reindex(config.MACRO_FACTOR_COLS), B.loc["A"], rtol=0.05, atol=1e-3)
    assert np.allclose(df["impact_1sd"], df["loading"] * m.std().reindex(df["factor"]).to_numpy())
    assert (df["n_months"] == 59).all() and set(df["method"]) == {"implied", "direct"}


def test_macro_universe_is_equity_only():
    """หน้า 7 ใช้เฉพาะกอง E เหมือนหน้า 6 — F/O ไม่หลุดเข้ามา."""
    res = pd.DataFrame({"FundCode": ["B", "A", "C", "D"], "policy": ["E", "E", "F", "O"]})
    assert config.MACRO_POLICY == "E"
    assert data_access.policy_universe(res, config.MACRO_POLICY) == ["A", "B"]


def test_macro_match_one_rejects_mismatched_index_set():
    nav, levels, coef_std = _synthetic_fund()
    coef_std["sector"] = coef_std["sector"].drop("D")    # coefs.csv ไม่ครบ -> ต้องไม่ chain เงียบๆ
    with pytest.raises(ValueError):
        data_access.macro_match_one(nav, coef_std, levels, _B(), _macro_m(n=59), "2021-01-01", "2025-12-31")
