"""test_gc75_frontier.py — หน้า 10 (M019 Frontier): กริดน้ำหนัก · เลือกกอง/ไตรมาส · frontier + MVP/max Sharpe/ERC · ไฟล์อ้างอิง · หน้า render ได้."""

import os
from math import comb

import numpy as np
import pandas as pd
import pytest

import config
import data_access
from analysis import gc75_frontier as gf
from analysis import portfolio


@pytest.mark.parametrize("n", [1, 3, 6, 9])
def test_composition_grid_is_every_10pct_mix_that_sums_to_one(n):
    g = portfolio.composition_grid(n, 0.1)
    assert len(g) == comb(10 + n - 1, n - 1) and np.allclose(g.sum(axis=1), 1.0)
    assert g.min() >= 0 and len(np.unique(g.round(9), axis=0)) == len(g)
    assert np.allclose(np.round(g * 10), g * 10)                                       # ทีละ 10% พอดี


def test_composition_grid_matches_weight_grid_where_both_apply():
    a = portfolio.composition_grid(4, 0.1)
    b = portfolio.weight_grid(4, 0.0, 1.0, 0.1)
    assert {tuple(r) for r in a.round(9)} == {tuple(r) for r in b.round(9)}
    with pytest.raises(ValueError):
        portfolio.composition_grid(3, 0.03)


@pytest.mark.parametrize("n, step, cap, count", [(5, 0.05, 0.4, 3951), (8, 0.05, 0.4, 634446), (8, 0.1, 0.4, 13140),
                                                 (3, 0.05, 0.4, 15), (3, 0.01, 0.4, 231), (3, 0.1, 0.3, 0)])
def test_composition_grid_respects_the_cap(n, step, cap, count):
    g = portfolio.composition_grid(n, step, cap)                 # count = inclusion–exclusion (คำนวณแยก)
    assert len(g) == count
    if count:
        assert np.allclose(g.sum(axis=1), 1.0) and g.max() <= cap + 1e-9 and len(np.unique(g.round(9), axis=0)) == count


def _synthetic(t="2024-09-30", n_eq=3, kind="G"):
    rng = np.random.default_rng(0)
    funds = [f"E{i}" for i in range(n_eq)] + ["DEF"]
    weeks = pd.date_range("2023-10-06", periods=52, freq="W-FRI")
    sd_def = 0.01 if kind == "G" else 0.0001
    rets = np.column_stack([rng.normal(0.002 + 0.0005 * i, 0.02, 52) for i in range(n_eq)] + [rng.normal(0.0004, sd_def, 52)])
    weekly = pd.DataFrame([{"t": pd.Timestamp(t), "FundCode": f, "week": w, "ret": rets[j, k]}
                           for k, f in enumerate(funds) for j, w in enumerate(weeks)])
    holdings = pd.DataFrame({"t": pd.Timestamp(t), "FundCode": funds, "kind": ["E"] * n_eq + [kind],
                             "weight": [0.5 / n_eq] * n_eq + [0.5], "sr12p": list(range(n_eq, 0, -1)) + [1.0], "rf": 0.02})
    return holdings, weekly


def test_fund_set_is_held_equity_by_sr12_then_defensive_leg():
    h, _ = _synthetic()
    assert list(gf.fund_set(h.iloc[::-1])["FundCode"]) == ["E0", "E1", "E2", "DEF"]
    assert list(gf.fund_set(h[h["kind"] == "E"])["FundCode"]) == ["E0", "E1", "E2"]       # หุ้น 100% ไม่มีขาตั้งรับ


@pytest.mark.parametrize("kind", ["G", "F"])
def test_frontier_case_locks_the_defensive_leg_and_caps_each_equity_fund(kind):
    h, w = _synthetic(kind=kind)
    r = gf.frontier_case(h, w, step=0.01, max_w=0.4)
    assert len(r["points"]) == 231                                                     # 3 กอง × 0–40% ทีละ 1% รวม 100%
    assert r["mvp"]["risk"] == pytest.approx(r["points"]["risk"].min())               # MVP = เสี่ยงต่ำสุดของทุกพอร์ต
    eq = ["E0", "E1", "E2"]
    for name in ("MVP", "max Sharpe"):
        assert r["weights"].loc["DEF", name] == pytest.approx(0.5)
        assert r["weights"].loc[eq, name].max() <= 0.4 * 0.5 + 1e-12
    sh = (r["frontier"]["ret"] - r["rf"]) / r["frontier"]["risk"]
    assert (r["max_sharpe"]["ret"] - r["rf"]) / r["max_sharpe"]["risk"] == pytest.approx(sh.max())
    assert np.allclose(r["weights"].sum(), 1.0)
    erc = r["weights"]["ERC (กติกาโมเดล)"]
    assert erc["DEF"] == pytest.approx(0.5) and erc.drop("DEF").sum() == pytest.approx(0.5) and erc.drop("DEF").max() <= 0.2 + 1e-12
    x = w.pivot(index="week", columns="FundCode", values="ret")
    assert r["sigma"].loc["DEF", "DEF"] == pytest.approx(x["DEF"].var(ddof=0) * 52)   # ขาตั้งรับไม่ถูก shrink


def test_equity_block_is_shrunk_without_the_defensive_leg():
    h, w = _synthetic()
    r = gf.frontier_case(h, w)
    eq = ["E0", "E1", "E2"]
    x = w.pivot(index="week", columns="FundCode", values="ret")[eq].to_numpy()
    assert np.allclose(r["sigma"].loc[eq, eq].to_numpy(), portfolio.shrink_constant_correlation(x)[0] * 52)
    flat = w.copy()
    flat.loc[flat["FundCode"] == "E0", "ret"] = 0.0
    with pytest.raises(ValueError):                                                    # ไม่ตกไปเป้า μI เงียบๆ
        gf.frontier_case(h, flat)


def test_pick_quarters_is_fixed_and_from_the_given_set():
    qs = pd.date_range("2022-03-31", periods=15, freq="QE")
    a, b = gf.pick_quarters(qs), gf.pick_quarters(list(qs)[::-1])
    assert a == b and len(a) == config.GC75_FRONTIER_N_QUARTERS and set(a) <= set(qs) and a == sorted(a)


# ---------------- ไฟล์อ้างอิงจริง (M019) ----------------

@pytest.fixture(scope="module")
def ref():
    return data_access.load_gc75_frontier()


def test_reference_holdings_match_the_m019_model(ref):
    h, w = ref["holdings"], ref["weekly"]
    assert h["t"].nunique() == 15 and h["t"].min() == pd.Timestamp("2022-03-31")
    g = h.groupby("t")
    assert (g["weight"].sum() - 1).abs().max() < 1e-9
    assert (g["kind"].apply(lambda s: (s == "E").sum()) == 3).all() and (g["kind"].apply(lambda s: (s != "E").sum()) <= 1).all()
    assert set(h["kind"]) <= {"E", "G", "F"} and "K-GOLD-C(A)" not in set(h["FundCode"])   # class ที่ NAV ผิดหลัง 2024-04-22
    eq_w = h[h["kind"] == "E"].groupby("t")["weight"].sum().round(9)
    assert set(eq_w) <= {0.25, 0.5, 0.75, 1.0}                                        # สัดส่วนหุ้นตามตาราง GC75
    n_weeks = w.groupby(["t", "FundCode"]).size()
    assert (n_weeks == 52).all() and len(n_weeks) == len(h)
    assert w.loc[w["FundCode"].isin(h.loc[h["kind"] == "E", "FundCode"]), "ret"].notna().all()
    assert (w["week"] <= w["t"]).all()                                                # ไม่มีข้อมูลหลังวันตัดสินใจ


def test_fixed_quarters_and_every_case_computes(ref):
    qs = gf.pick_quarters(ref["holdings"]["t"])
    assert [q.strftime("%Y-%m-%d") for q in qs] == ["2022-09-30", "2024-03-29", "2024-09-30", "2025-09-30"]
    for t in qs:
        h_t = ref["holdings"][ref["holdings"]["t"] == t]
        r = gf.frontier_case(h_t, ref["weekly"][ref["weekly"]["t"] == t])
        d = h_t[h_t["kind"] != "E"].set_index("FundCode")["weight"]
        assert len(r["points"]) == 231 and np.allclose(r["weights"].loc[list(d.index)].to_numpy().T, d.to_numpy())


def test_model_erc_reproduces_the_held_weights_in_every_quarter(ref):
    h, w = ref["holdings"], ref["weekly"]
    for t, h_t in h.groupby("t"):
        erc = gf.model_erc(gf.fund_set(h_t), w[w["t"] == t])
        held = h_t.set_index("FundCode")["weight"].reindex(erc.index)
        assert (erc - held).abs().max() < 1e-12, t


def test_page_renders_four_frontiers():
    from streamlit.testing.v1 import AppTest
    page = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "pages", "10_🗺_M019_Frontier.py")
    at = AppTest.from_file(page, default_timeout=120).run()
    assert not at.exception, [e.value for e in at.exception]
    n = config.GC75_FRONTIER_N_QUARTERS
    assert len(at.subheader) == n and not at.error
    assert len(at.dataframe) == 2 * n                                                  # ตาราง Exp/T_* + น้ำหนักกองที่ถือ
    assert not at.warning or all("ไม่ใช่คำแนะนำ" in w.value for w in at.warning)      # ไฟล์ผลจริงตรงกับกราฟ
    cols = ["Exp vol", "Exp return", "Exp Sharpe", "T_vol_Q1", "T_return_Q1", "T_sharpe_Q1", "T_vol_Y1", "T_return_Y1", "T_sharpe_Y1"]
    tables = [d.value for d in at.dataframe if "Exp vol" in d.value.columns]
    assert len(tables) == n
    for tab in tables:
        assert list(tab.columns) == cols and list(tab.index) == ["MVP", "Max Sharpe", "Model Portfolio"]
        assert (tab[["T_vol_Q1", "T_return_Q1", "T_sharpe_Q1"]] != "-").all().all()
    assert (tables[-1][["T_vol_Y1", "T_return_Y1", "T_sharpe_Y1"]] == "-").all().all()   # 2025-09-30: 1 ปียังไม่ครบ


def test_model_erc_cap_is_independent_of_the_grid_cap(monkeypatch):
    h, w = _synthetic()
    base = gf.model_erc(gf.fund_set(h), w)
    monkeypatch.setattr(config, "GC75_FRONTIER_MAX_W", 0.6)                            # ขยายกริดเพื่อสำรวจ
    assert np.allclose(gf.model_erc(gf.fund_set(h), w), base)                          # จุด ERC ยังเป็นกติกาโมเดลเดิม
    assert len(gf.frontier_case(h, w, step=0.05)["points"]) > 15


def test_defensive_nan_weeks_do_not_shrink_the_equity_sample():
    h, w = _synthetic()
    gap = w.copy()
    gap.loc[(gap["FundCode"] == "DEF") & (gap["week"].isin(gap["week"].unique()[:3])), "ret"] = np.nan
    mu, sigma, n = gf.weekly_mu_sigma(gap, ["E0", "E1", "E2"], ["DEF"])
    mu0, sigma0, _ = gf.weekly_mu_sigma(w, ["E0", "E1", "E2"], ["DEF"])
    eq = ["E0", "E1", "E2"]
    assert n == 52 and np.allclose(sigma.loc[eq, eq], sigma0.loc[eq, eq]) and np.allclose(mu[eq], mu0[eq])
    x = gap.pivot(index="week", columns="FundCode", values="ret")
    assert mu["DEF"] == pytest.approx(x["DEF"].mean() * 52) and sigma.loc["DEF", "DEF"] == pytest.approx(x["DEF"].var(ddof=0) * 52)


# ---------------- ผลที่เกิดขึ้นจริง ----------------

def test_realized_file_matches_the_frontier_weights_and_m019(ref):
    import json
    r = ref["realized"]
    assert r is not None and len(r) == 15 * 3 * 2
    assert set(r["horizon"]) == {"Q", "1Y"} and r[["ret", "vol_ann", "sharpe", "cost"]].notna().all().all()
    assert (r["end"] <= pd.Timestamp(config.TF_EVAL_END)).all() and (r["cost"] >= 0).all()
    for t, h_t in ref["holdings"].groupby("t"):
        res = gf.frontier_case(h_t, ref["weekly"][ref["weekly"]["t"] == t])
        for name in res["weights"].columns:                                            # น้ำหนักในไฟล์ = น้ำหนักบนกราฟ
            w = json.loads(r[(r["t"] == t) & (r["portfolio"] == name)]["weights"].iloc[0])
            assert max(abs(w.get(f, 0.0) - x) for f, x in res["weights"][name].items()) < 1e-9, (t, name)
    erc_q = r[(r["portfolio"] == "ERC (กติกาโมเดล)") & (r["horizon"] == "Q")].sort_values("t")
    growth = float(np.prod(1 + erc_q["ret"]))                                          # ต่อทุกไตรมาส = เส้น M019 หน้า 9
    curve = data_access.load_tf_top3()["curves"].query("series == 'M019' and case == 'full'")
    assert growth == pytest.approx(curve["value"].iloc[-1] / curve["value"].iloc[0], rel=1e-9)
