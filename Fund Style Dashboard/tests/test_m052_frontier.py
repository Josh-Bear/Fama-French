"""test_m052_frontier.py — หน้า 11 (M052 Frontier): ไฟล์อ้างอิง · จุด Model = น้ำหนักที่ถือจริง · ผลจริงต่อกันได้เส้น M052 ของหน้า 9 · หน้า render ได้."""

import json
import os

import numpy as np
import pandas as pd
import pytest

import config
import data_access
from analysis import gc75_frontier as gf


@pytest.fixture(scope="module")
def ref():
    return data_access.load_m052_frontier()


def test_reference_holdings_shape_and_signals(ref):
    h, w = ref["holdings"], ref["weekly"]
    assert h["t"].nunique() == 15 and h["t"].min() == pd.Timestamp("2022-03-31")
    g = h.groupby("t")
    assert (g["weight"].sum() - 1).abs().max() < 1e-9
    assert (g["kind"].apply(lambda s: (s == "E").sum()) == 3).all() and (g["kind"].apply(lambda s: (s != "E").sum()) <= 1).all()
    assert "K-GOLD-C(A)" not in set(h["FundCode"]) and (w["week"] <= w["t"]).all()
    per_q = g[["gc_k", "x_gc", "canary_b", "vsl_mult", "x_model"]].nunique()
    assert (per_q == 1).all().all()                                                     # สัญญาณเป็นค่าเดียวต่อไตรมาส
    q = g[["x_gc", "canary_b", "vsl_mult", "x_model"]].first()
    assert np.allclose(q["x_model"], np.maximum(0.25, np.minimum(q["x_gc"] * q["vsl_mult"], 1 - q["canary_b"] / 2)))   # สูตร M052


def test_model_point_is_the_held_portfolio_and_realized_chains_to_m052(ref):
    r = ref["realized"]
    assert r is not None and len(r) == 15 * 3 * 2
    for t, h_t in ref["holdings"].groupby("t"):
        held = h_t.set_index("FundCode")["weight"]
        res = gf.frontier_case(h_t, ref["weekly"][ref["weekly"]["t"] == t], model_weights=held)
        assert np.allclose(res["weights"]["ERC (กติกาโมเดล)"].reindex(held.index), held)
        for name in res["weights"].columns:
            w = json.loads(r[(r["t"] == t) & (r["portfolio"] == name)]["weights"].iloc[0])
            assert max(abs(w.get(f, 0.0) - x) for f, x in res["weights"][name].items()) < 1e-9, (t, name)
    q = r[(r["portfolio"] == "ERC (กติกาโมเดล)") & (r["horizon"] == "Q")].sort_values("t")
    curve = data_access.load_tf_top3()["curves"].query("series == 'M052' and case == 'full'")
    assert float(np.prod(1 + q["ret"])) == pytest.approx(curve["value"].iloc[-1] / curve["value"].iloc[0], rel=1e-9)


def test_page_renders_four_frontiers():
    from streamlit.testing.v1 import AppTest
    page = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "pages", "11_🧭_M052_Frontier.py")
    at = AppTest.from_file(page, default_timeout=120).run()
    assert not at.exception, [e.value for e in at.exception]
    n = config.GC75_FRONTIER_N_QUARTERS
    assert len(at.subheader) == n and not at.error
    assert not at.warning or all("ไม่ใช่คำแนะนำ" in w.value for w in at.warning)
    tables = [d.value for d in at.dataframe if "Exp vol" in d.value.columns]
    assert len(tables) == n and all(list(t.index) == ["MVP", "Max Sharpe", "Model Portfolio"] for t in tables)
