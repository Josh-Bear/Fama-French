"""test_page9_ui.py — หน้า 9 (TF Portfolio) render ได้จาก cache จริงและสลับค่าได้ไม่ error (Streamlit AppTest)."""

import os

import pytest

import config
import data_access
from viz import TF_SERIES_LABELS

PAGE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "pages", "9_📈_TF_Portfolio.py")
pytestmark = pytest.mark.skipif(not data_access.tf_cache_ready(), reason="ไม่มี cache หน้า 9 (รัน `data_access.py tf`)")


@pytest.fixture(scope="module")
def app():
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(PAGE, default_timeout=180).run()
    assert not at.exception, [e.value for e in at.exception]
    return at


def _metrics_table(at):
    tables = [d.value for d in at.dataframe if "พอร์ต" in d.value.columns]
    assert len(tables) == 1
    return tables[0].set_index("พอร์ต")


def test_page_renders_both_sections(app):
    assert [s.value for s in app.subheader][:2] == ["1 · พอร์ตแนะนำ ณ วันที่เลือก",
                                                    f"2 · ผล backtest walk-forward — TOP3 (ถึง {config.TF_EVAL_END})"]
    assert [m.label for m in app.metric] == ["ACWI vs SMA200", "เงินสด", "กองสด / universe", "คัดได้ (I_t)"]
    assert len(app.selectbox) == 1 and len(app.radio) == 1


def test_every_as_of_date_renders(app):
    cache = data_access.load_tf_cache()
    options = data_access.tf_asof_options(cache)
    assert len(app.selectbox[0].options) == len(options)
    for i in range(len(options)):
        app.selectbox[0].select_index(i).run()
        assert not app.exception, (options[i], [e.value for e in app.exception])
        assert len(app.metric) == 4
        live = data_access.tf_live(str(options[i].date()))
        thin = any("ข้อมูล NAV ณ วันนี้บางมาก" in e.value for e in app.error)
        assert thin == (live["coverage"] < config.TF_COVERAGE_MIN), options[i]


@pytest.mark.parametrize("case", ["full", "nofront", "flat"])
def test_cost_case_switches_the_backtest_table(app, case):
    app.radio[0].set_value(case).run()
    assert not app.exception, [e.value for e in app.exception]
    metrics = data_access.load_tf_top3()["metrics"].set_index(["series", "case"])
    shown = _metrics_table(app)
    assert len(shown) == len(config.TF_TOP3_SERIES)
    for series in config.TF_TOP3_SERIES:
        assert shown.loc[TF_SERIES_LABELS[series], "Sharpe"] == pytest.approx(metrics.loc[(series, case), "sharpe"])
