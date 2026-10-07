"""test_tf_model.py — regression ของโมเดลหน้า 9 เทียบผล backtest ของทีม quant (ต้องตรงทุกไตรมาส).

- ชุดหลักรันบนข้อมูลแช่แข็ง (tests/tf_frozen.py) -> แดง = โค้ดเปลี่ยนผล ไม่ขึ้นกับการ rebuild ข้อมูล
- ชุด live รันบนข้อมูลจริง: ข้อมูลถึง TF_EVAL_END ไม่ตรงกับชุดแช่แข็ง -> skip พร้อมบอกว่าข้อมูลเปลี่ยน (ผล backtest อาจเปลี่ยน)
"""

import json
import os

import pandas as pd
import pytest

import config
import data_access
from analysis import fund_backtest as fb
from analysis import tf_model as tm
from analysis.fund_fees import FeeData
from tests import tf_frozen

FIX = os.path.join(os.path.dirname(__file__), "fixtures")
LAST_Q = "2025-09-30"


def _walk(inp):
    qs = tm.complete_quarters(inp.calendar, config.TF_START_Q, LAST_Q)
    return inp, qs, tm.walk_forward(inp, qs)


def _check_weights(inp, res):
    ref = pd.read_csv(os.path.join(FIX, "tf_reference_weights.csv"), parse_dates=["t"])
    mine = tm.holdings_frame(res, inp.calendar)[["t", "FundCode", "weight"]]
    m = ref.merge(mine, on=["t", "FundCode"], how="outer", suffixes=("_ref", "_new"))
    assert m["weight_ref"].notna().all() and m["weight_new"].notna().all()
    assert (m["weight_ref"] - m["weight_new"]).abs().max() < 1e-9


def _check_sharpe(inp, qs, res, fee):
    ref = json.load(open(os.path.join(FIX, "tf_reference_metrics.json")))
    for series, plan in ((config.TF_MODEL_ID, tm.build_plan(res, inp.calendar)), ("B0", tm.b0_plan(inp, qs))):
        for case, (v, _) in tm.run_cases(inp, plan, fee).items():
            assert fb.summarize(v, config.TF_RF_SIM)["sharpe"] == pytest.approx(ref[series][case], abs=1e-5), (series, case)


# ---------------- ข้อมูลแช่แข็ง: ตรวจโค้ด ----------------

@pytest.fixture(scope="module")
def frozen():
    if not tf_frozen.available():
        pytest.fail("ไม่มี tests/fixtures/tf_frozen/ — สร้างด้วย `PYTHONPATH=. ./.venv/bin/python -m tests.tf_frozen`")
    inp, fee = tf_frozen.load()
    return (*_walk(inp), fee)


def test_weights_match_the_validated_backtest(frozen):
    inp, _, res, _ = frozen
    _check_weights(inp, res)


def test_sharpe_matches_the_validated_backtest(frozen):
    inp, qs, res, fee = frozen
    _check_sharpe(inp, qs, res, fee)


def test_live_selection_at_a_backtest_quarter_equals_walk_forward(frozen):
    inp, qs, res, _ = frozen
    held, pf = res[-2]["held_after"], res[-2]["prev_fallback_after"]
    live = tm.select_at(inp, qs[-1], held, pf)
    assert live["weights"] == pytest.approx(res[-1]["weights"])


def test_selection_is_point_in_time(frozen):
    """ตัด NAV หลัง t ทิ้งแล้วผล ณ t ต้องเหมือนเดิม."""
    inp, qs, res, _ = frozen
    t = qs[5]
    cut = tm.ModelInputs(nav=inp.nav[inp.nav["NAVDate"] <= t], calendar=inp.calendar[inp.calendar <= t],
                         trend_index=inp.trend_index.loc[:t], groups=inp.groups)
    r = tm.select_at(cut, t, res[4]["held_after"], res[4]["prev_fallback_after"])
    assert r["weights"] == pytest.approx(res[5]["weights"])


# ---------------- ข้อมูลจริง: ตรวจว่าข้อมูลหลัง TF_EVAL_END ไม่รั่วเข้า backtest ----------------

def _drift(live: dict, frozen_raw: dict) -> list[str]:
    """รายการส่วนของข้อมูลจริงที่ไม่ตรงกับชุดแช่แข็ง (ว่าง = ตรงทุกส่วน)."""
    out = []
    for k in ("nav", "calendar", "acwi", "fees", "profile"):
        a, b = live[k].reset_index(drop=True), frozen_raw[k].reset_index(drop=True)
        try:
            pd.testing.assert_frame_equal(a, b, check_dtype=False, check_exact=True)
        except AssertionError:
            if k == "nav":
                key = ["FundCode", "NAVDate"]
                m = a.merge(b, on=key, how="outer", suffixes=("_live", "_frozen"), indicator=True)
                diff = m[(m["_merge"] != "both") | (m["NAV_live"] != m["NAV_frozen"])]
                out.append(f"NAV ≤ {config.TF_EVAL_END} ต่าง {len(diff)} แถว ใน {diff['FundCode'].nunique()} กอง "
                           f"(เช่น {', '.join(diff['FundCode'].drop_duplicates().head(5))})")
            else:
                out.append(f"{k} ต่าง ({len(a)} vs {len(b)} แถว)")
    if live["groups"] != frozen_raw["groups"]:
        out.append("share_class_groups ต่าง")
    return out


@pytest.fixture(scope="module")
def live():
    if not os.path.exists(config.NAV_CLEAN_PARQUET):
        pytest.skip("ไม่มี cache/nav_clean.parquet")
    drift = _drift(tf_frozen.slice_live(), tf_frozen.read_raw())
    if drift:
        pytest.skip("ข้อมูลจริงถึง TF_EVAL_END เปลี่ยนจากชุดที่ทีม quant ตรวจ — ผล backtest อาจเปลี่ยน "
                    "(ไม่ใช่โค้ดพัง · ชุดแช่แข็งยังตรวจโค้ดอยู่): " + " · ".join(drift))
    inp = data_access._tf_inputs()
    return (*_walk(inp), FeeData(sorted(inp.nav["FundCode"].unique())))


def test_live_data_reproduces_the_validated_backtest(live):
    """ข้อมูลจริงทั้งชุด (รวม NAV ปี 2026) ต้องได้ผลเท่าเดิม — ข้อมูลหลัง TF_EVAL_END ไม่รั่วเข้า backtest."""
    inp, qs, res, fee = live
    _check_weights(inp, res)
    _check_sharpe(inp, qs, res, fee)
