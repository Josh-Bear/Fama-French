"""test_fund_signals.py — สัญญาณระดับกองของโมเดลหน้า 9 (fixture รู้คำตอบ)."""

import numpy as np
import pandas as pd
import pytest

import config
from analysis import fund_signals as fs


@pytest.mark.parametrize("fc, fam", [
    ("KKP GINFRAEQ-H", "KKP GINFRAEQ"), ("KKP GINFRAEQ-H-F", "KKP GINFRAEQ"), ("KKP GINFRAEQ-H-U", "KKP GINFRAEQ"),
    ("TUSEQ-UH", "TUSEQ"), ("ASP-NGF", "ASP-NGF"), ("M-EUBANK", "M-EUBANK"), ("X-UH-A-F", "X"),
])
def test_family_of_strips_class_suffixes_including_f_and_u(fc, fam):
    assert fs.family_of(fc, {}) == (fam, "suffix")


def test_family_of_prefers_the_share_class_csv():
    assert fs.family_of("ABC-A", {"ABC-A": "group1"}) == ("group1", "csv")


def test_tax_and_dividend_classes():
    assert fs.is_tax_class("SCBS&P500-SSF") and fs.is_tax_class("K-USA-THAIESG") and not fs.is_tax_class("K-USA-A")
    assert fs.is_dividend("ABC-D") and fs.is_dividend("ABC-D-F") and not fs.is_dividend("ABC-A")


def _ctx(nav: pd.Series):
    cal = pd.bdate_range("2023-01-02", "2024-12-31")
    return fs.SignalContext(fs.prep_arrays({"F": nav}), cal, cal[-1]), cal


def test_sr12_on_a_known_series():
    """NAV โตคงที่ 0.1%/วันทำการ + แกว่งสลับ ±1% รายวัน -> R12-1 / vol52 / SR12 ตามนิยาม."""
    cal = pd.bdate_range("2023-01-02", "2024-12-31")
    nav = pd.Series(100 * 1.001 ** np.arange(len(cal)) * (1 + 0.01 * (np.arange(len(cal)) % 2)), index=cal)
    ctx, _ = _ctx(nav)
    sig = ctx.fund_signal("F")
    p_m1 = nav.loc[:ctx.months[-2]].iloc[-1]
    p_m12 = nav.loc[:ctx.months[0]].iloc[-1]
    assert sig["R12_1"] == pytest.approx(p_m1 / p_m12 - 1)
    wp = np.array([nav.loc[:w].iloc[-1] for w in ctx.weeks])
    vol = np.std(wp[1:] / wp[:-1] - 1, ddof=1) * np.sqrt(52)
    assert sig["vol52"] == pytest.approx(vol)
    assert sig["SR12"] == pytest.approx((sig["R12_1"] - config.TF_RF_SIGNAL * 11 / 12) / vol)


def test_flat_nav_has_no_usable_vol():
    """NAV ค้าง (return 0 เกิน 20%) -> vol52 = NaN -> ไม่มี SR12."""
    cal = pd.bdate_range("2023-01-02", "2024-12-31")
    ctx, _ = _ctx(pd.Series(100.0, index=cal))
    sig = ctx.fund_signal("F")
    assert np.isnan(sig["vol52"]) and np.isnan(sig["SR12"])


def test_signal_ignores_data_after_t():
    """point-in-time: แก้ NAV หลัง t แล้วสัญญาณ ณ t ต้องเท่าเดิม."""
    cal = pd.bdate_range("2023-01-02", "2024-12-31")
    nav = pd.Series(100 * 1.0005 ** np.arange(len(cal)) * (1 + 0.02 * np.sin(np.arange(len(cal)))), index=cal)
    t = cal[-60]
    a = fs.SignalContext(fs.prep_arrays({"F": nav}), cal, t).fund_signal("F")
    nav2 = nav.copy()
    nav2[nav2.index > t] *= 3
    b = fs.SignalContext(fs.prep_arrays({"F": nav2}), cal, t).fund_signal("F")
    assert a == b


def test_investable_set_drops_stale_tax_and_duplicate_dividend_classes():
    t = pd.Timestamp("2024-06-28")
    stale = t - pd.Timedelta(days=config.TF_FRESH_DAYS + 1)
    u = pd.DataFrame({"FundCode": ["A-A", "A-D", "B-SSF", "C", "D"],
                      "last_nav_date": [t, t, t, stale, t], "last_nav": 1.0, "last_aum": 1.0})
    sig = pd.DataFrame({"FundCode": u["FundCode"], "R12_1": 0.1, "vol52": 0.2, "SR12": 0.4})
    sig.loc[sig["FundCode"] == "D", ["R12_1", "vol52"]] = np.nan
    i_t, counts = fs.investable_set(t, u, sig, {})
    assert list(i_t["FundCode"]) == ["A-A"]
    assert counts == {"n_universe": 5, "n_fresh_cut": 1, "n_tax_cut": 1, "n_div_dropped": 1,
                      "n_signal_cut": 1, "n_investable": 1}
