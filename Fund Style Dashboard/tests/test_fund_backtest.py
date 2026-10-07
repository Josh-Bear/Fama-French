"""test_fund_backtest.py — จำลองพอร์ต/ค่าธรรมเนียม/ตัวชี้วัดรายเดือนของโมเดลหน้า 9."""

import numpy as np
import pandas as pd
import pytest

from analysis import fund_backtest as fb
from analysis.fund_fees import FeeModel


def _nav(days, start=100.0, g=0.0):
    return pd.Series(start * (1 + g) ** np.arange(len(days)), index=days)


def test_buy_and_hold_value_and_cash_leg():
    days = pd.bdate_range("2024-01-01", "2024-03-31")
    navs = {"A": _nav(days, g=0.001)}
    plan = [{"t": days[0], "e": days[1], "weights": {"A": 0.5, fb.CASH: 0.5}}]
    months = fb.month_ends(days, days[1], days[-1])
    v, entries = fb.simulate_path(plan, navs, months, rf_annual=0.0, cost_side=0.0)
    expected = 50 * navs["A"].loc[:months[-1]].iloc[-1] / navs["A"].iloc[1] + 50
    assert v.iloc[0] == 100.0 and v.iloc[-1] == pytest.approx(expected)
    assert entries[0]["turnover"] == pytest.approx(0.25)


def test_flat_cost_charged_per_side_and_not_on_cash():
    days = pd.bdate_range("2024-01-01", "2024-02-29")
    navs = {"A": _nav(days), "B": _nav(days)}
    plan = [{"t": days[0], "e": days[1], "weights": {"A": 1.0}},
            {"t": days[20], "e": days[21], "weights": {"B": 0.5, fb.CASH: 0.5}}]
    months = fb.month_ends(days, days[1], days[-1])
    _, ent = fb.simulate_path(plan, navs, months, rf_annual=0.0, cost_side=0.005)
    assert ent[0]["cost"] == pytest.approx(0.005)                 # ซื้อ A 100%
    assert ent[1]["cost"] == pytest.approx(0.005 * (1.0 + 0.5))  # ขาย A 100% + ซื้อ B 50% (เงินสดฟรี)


def test_unbuyable_fund_becomes_cash():
    days = pd.bdate_range("2024-01-01", "2024-03-29")
    navs = {"A": _nav(days[:5])}                                   # หยุดรายงานก่อนวันซื้อ
    plan = [{"t": days[10], "e": days[11], "weights": {"A": 1.0}}]
    v, _ = fb.simulate_path(plan, navs, fb.month_ends(days, days[11], days[-1]), rf_annual=0.0)
    assert np.allclose(v.to_numpy(), 100.0)


class _Fees:
    amc = {"A": "X", "B": "X", "C": "Y"}
    rates = {("A", "BF"): 0.0, ("A", "SO"): 0.0, ("B", "FF"): 1.5, ("B", "SI"): 0.5, ("C", "FF"): 1.0, ("C", "SI"): 0.0}

    def rate(self, fc, code, e):
        return self.rates.get((fc, code), 0.0)


def test_fee_model_uses_the_cheaper_switch_channel_within_an_amc():
    fm = FeeModel(_Fees(), "full")
    cost, d = fm.entry_cost(pd.Timestamp("2024-01-02"), {"A": 1.0}, {"B": 0.6, "C": 0.4})
    assert cost == pytest.approx(0.6 * 0.005 + 0.4 * 0.01)    # A->B สับเปลี่ยน (SI 0.5%) · C ต่าง บลจ. = FF 1%
    assert d["switch_vol"] == pytest.approx(0.6)
    assert FeeModel(_Fees(), "nofront").entry_cost(pd.Timestamp("2024-01-02"), {"A": 1.0}, {"C": 1.0})[0] == 0.0


def test_flat_fee_model_equals_constant_cost():
    fm = FeeModel(None, "flat", flat_rate=0.005)
    cost, _ = fm.entry_cost(pd.Timestamp("2024-01-02"), {"A": 0.7, "B": 0.3}, {"A": 0.2, "C": 0.8})
    assert cost == pytest.approx(0.005 * (0.5 + 0.3 + 0.8))


def test_monthly_metrics_known_values():
    v = pd.Series([100.0, 110.0, 99.0, 108.9], index=pd.to_datetime(["2024-01-31", "2024-02-29", "2024-03-31", "2024-04-30"]))
    r = fb.monthly_returns(v)
    assert r.round(6).tolist() == [0.1, -0.1, 0.1]
    assert fb.max_drawdown(v) == pytest.approx(-0.1)
    assert fb.portfolio_sharpe(r, 0.0) == pytest.approx(r.mean() * 12 / (r.std(ddof=1) * np.sqrt(12)))


def test_deflated_sharpe_decreases_with_more_trials():
    r = pd.Series(np.random.default_rng(1).normal(0.01, 0.03, 48))
    assert fb.deflated_sharpe(r, 0.02, 20) < fb.deflated_sharpe(r, 0.02, 5) < fb.deflated_sharpe(r, 0.02, 1)


def test_universe_at_uses_only_data_up_to_t():
    days = pd.bdate_range("2021-01-01", "2023-12-29")
    nav = pd.DataFrame({"FundCode": "A", "NAVDate": days, "NAV": 1.0, "AUM": 1.0})
    t = pd.Timestamp("2022-06-30")
    u = fb.universe_at(nav, t)
    assert list(u["FundCode"]) == ["A"] and u["last_nav_date"].iloc[0] <= t
    assert fb.universe_at(nav, pd.Timestamp("2021-06-30")).empty      # ประวัติยังไม่ถึง 252 วัน


def test_simulate_path_refuses_plans_that_would_lose_money():
    days = pd.bdate_range("2024-01-01", "2024-03-29")
    navs = {"A": _nav(days)}
    months = fb.month_ends(days, days[1], days[-1])
    with pytest.raises(ValueError):                                   # น้ำหนักรวม 0.25 -> เงิน 75% จะหายเงียบๆ
        fb.simulate_path([{"t": days[0], "e": days[1], "weights": {fb.CASH: 0.25}}], navs, months, 0.0)

    class _NanFees:
        def entry_cost(self, e, d, t):
            return float("nan"), {}
    with pytest.raises(ValueError):                                   # ต้นทุน NaN ต้องไม่ไหลเข้า equity curve
        fb.simulate_path([{"t": days[0], "e": days[1], "weights": {"A": 1.0}}], navs, months, 0.0, fee_model=_NanFees())


def test_simulate_path_reports_unbuyable_and_stale_holdings():
    days = pd.bdate_range("2024-01-01", "2024-09-30")
    navs = {"A": _nav(days[:5]), "B": _nav(days[:30])}                 # A หยุดก่อนซื้อ · B หยุดหลังซื้อ (NAV ค้าง)
    plan = [{"t": days[10], "e": days[11], "weights": {"A": 0.5, "B": 0.5}}]
    _, ent = fb.simulate_path(plan, navs, fb.month_ends(days, days[11], days[-1]), rf_annual=0.0)
    assert ent[0]["cannot_buy"] == ["A"] and ent[0]["stale_marks"] == ["B"]


def test_fee_median_falls_back_to_flat_cost_when_a_code_has_no_valid_rows(tmp_path):
    import config
    from analysis.fund_fees import FeeData
    fee = tmp_path / "fee.csv"
    fee.write_text("As of Date,Fund Code,Complex Type Code,Code,Rate,Unit Rate,Actual Value\n"
                   "20240101,A,FEEUH,FF,1.5,,1.5\n20240101,A,FEEUH,BF,0,,200\n", encoding="utf-8-sig")
    prof = tmp_path / "prof.csv"
    prof.write_text("Fund Code,AMC_CODE\nA,X\n")
    fd = FeeData(["A"], fee_csv=str(fee), profile_csv=str(prof))
    assert "BF" in fd.median_fallback and fd.median["BF"] == config.TF_COST_FLAT * 100
