"""test_tf_top3_reference.py — ไฟล์อ้างอิง TOP3 ของหน้า 9 ครบและสอดคล้องกับตัวเลขที่ validator ตรวจแล้ว."""

import pytest

import config
import data_access


@pytest.fixture(scope="module")
def top3():
    return data_access.load_tf_top3()


def test_every_series_has_every_case(top3):
    c, m = top3["curves"], top3["metrics"]
    assert list(c["series"].drop_duplicates()) == list(config.TF_TOP3_SERIES)
    for s in config.TF_TOP3_SERIES:
        for case in ("full", "nofront", "flat"):
            g = c[(c["series"] == s) & (c["case"] == case)]
            assert len(g) == 46 and g["value"].iloc[0] == pytest.approx(100.0)
            assert g["date"].is_monotonic_increasing and g["date"].max().strftime("%Y-%m-%d") == config.TF_EVAL_END
            assert ((m["series"] == s) & (m["case"] == case)).sum() == 1


def test_headline_sharpe_matches_validated_export(top3):
    m = top3["metrics"].set_index(["series", "case"])["sharpe"]
    for s, v in {"GC75_MMF": 0.751, "TREND25": 0.719, "M012_QFS": 0.660, "B0": 0.076}.items():
        assert m[(s, "full")] == pytest.approx(v, abs=5e-4)


def test_cagr_matches_curve_endpoints(top3):
    c, m = top3["curves"], top3["metrics"].set_index(["series", "case"])
    for (s, case), g in c.groupby(["series", "case"]):
        years = (g["date"].iloc[-1] - g["date"].iloc[0]).days / config.DAYS_PER_YEAR
        cagr = (g["value"].iloc[-1] / g["value"].iloc[0]) ** (1 / years) - 1
        assert cagr == pytest.approx(m.loc[(s, case), "cagr"], abs=2e-3), (s, case)
