"""test_eo_01 … test_eo_15 (S012 + S013 · ข้อ 11.2 ที่ S013 แก้) + test ฟังก์ชันใหม่ของ lib/l1eo.py
ข้อมูลจำลองเท่านั้น (test ที่ต้องอ่านผลตอบแทนจริงติดป้าย `real` และรันเมื่อ S012_REAL=1 — หลังเขียน decisions_pre_run.md) ·
รัน: PYTHONPATH=. ./.venv/bin/python -m pytest -p no:cacheprovider .claude/factor_team/lib/tests/test_l1eo.py"""
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import io_l1
import l1eo
import l2
import l3
import l4
import regress as rg
import samples as sp
from samples import window_mask

real = pytest.mark.skipif(os.environ.get("S012_REAL") != "1", reason="ต้องอ่านผลตอบแทนจริง — รันหลังเขียน decisions_pre_run.md (S012_REAL=1)")
TEAM = io_l1.TEAM
SEED = 20261015


# ───────────────────────── ข้อมูลจำลอง ─────────────────────────
@pytest.fixture(scope="module")
def world():
    F0, Feo0, Fext0 = io_l1.load_factors("W"), l1eo.load_eo("W"), l1eo.load_ext("W")
    F, Feo, Fext = l1eo.sim_factors(F0, 11), l1eo.sim_factors(Feo0, 12), l1eo.sim_factors(Fext0, 13)
    units = [f"E{i:02d}" for i in range(50)] + [f"O{i}" for i in range(6)]
    pol = pd.Series({u: ("O" if u.startswith("O") else "E") for u in units})
    R = l1eo.sim_returns(units, pol, F, Feo, Fext, seed=14)
    term = (F["IEF_USD"] - F["SHV_USD"]).to_numpy()
    for u in units:
        if pol[u] == "E":
            R[u] = R[u] + 1.2 * term                       # โครงสร้างให้ stepwise เลือก TERM (test future-scramble ไม่ว่างเปล่า)
    idx = R.index
    masks = {n: window_mask(idx, n) for n in ("train", "test", "H1", "H2", "full")}
    masks["pos1"] = np.arange(len(idx)) >= 1
    masks["ptr"] = masks["train"] & (idx <= pd.Timestamp("2022-06-24"))
    masks["pte"] = masks["train"] & (idx >= pd.Timestamp("2022-07-01"))
    return dict(F=F, Feo=Feo, Fext=Fext, R=R, units=units, pol=pol, idx=idx, masks=masks, E=[u for u in units if pol[u] == "E"])


# ───────────────────────── 01 · U ─────────────────────────
def test_eo_01_universe_structure():
    """U ไม่มีกอง F · U_E 218 / U_O 14 รหัส · 215 / 13 หน่วย · ทุกกองใน CSV อยู่ใน U และกลับกัน (โครงเท่านั้น · ไม่อ่านผลตอบแทน)"""
    A = pd.read_parquet(TEAM / "data" / "aum_fam.parquet")
    U = A[A["in_U"]]
    assert (U["policy"] != "F").all()
    assert int((U["policy"] == "E").sum()) == 218 and int((U["policy"] == "O").sum()) == 14
    g = l1eo.load_group_map()
    assert set(g["FundCode"]) == set(U["FundCode"]) and len(g) == 232
    assert g.loc[g.policy == "E", "unit"].nunique() == 215 and g.loc[g.policy == "O", "unit"].nunique() == 13
    assert set(g["splice_id"][g["splice_id"] != ""]) == set(l1eo.SPLICE_TABLE)
    S = pd.read_csv(TEAM / "specs" / "S013_pca_sets.csv")
    assert set(S["unit"]) == set(g["unit"]) and len(S) == 228


@real
def test_eo_01b_sets_equal_s013_csv():
    """รายชื่อหน่วยทุกชุดตรง S013_pca_sets.csv ทุกหน่วย (ไม่ใช่แค่จำนวน)"""
    g = l1eo.load_group_map()
    R = io_l1.load_returns("W")
    R = R[list(g["FundCode"])]
    RU, _ = l1eo.splice_units(R)
    pol = g.drop_duplicates("unit").set_index("unit")["policy"]
    sets = l1eo.eo_sets(RU, pol, io_l1.load_dup_pairs())
    diff = l1eo.compare_sets(sets, pd.read_csv(TEAM / "specs" / "S013_pca_sets.csv"))
    assert diff == {}, diff
    cnt = sets.groupby("policy")[l1eo.SET_COLS].sum()
    assert cnt.loc["E"].tolist() == [163, 160, 196, 141, 199, 97, 185]


# ───────────────────────── 02 · AUM ≤ 2023-12-31 ─────────────────────────
def test_eo_02_aum_window():
    A = pd.read_parquet(TEAM / "data" / "aum_fam.parquet")
    U = A[A["in_U"]]
    d = pd.to_datetime(U["last_aum_date"])
    assert d.notna().all()
    assert d.min() >= pd.Timestamp("2023-10-02") and d.max() <= pd.Timestamp("2023-12-31")
    assert (U["age_days_2025"] >= 730).all() and (U["aum_fam_2023"] >= 1e8).all()


# ───────────────────────── 03 · ไม่มีแถว > 2025-12-26 ─────────────────────────
def test_eo_03_no_rows_after_main_end(world):
    end = pd.Timestamp(io_l1.MAIN_END)
    for freq, e in (("W", end), ("M", pd.Timestamp(io_l1.MONTH_END))):
        assert l1eo.load_eo(freq).index.max() <= e and l1eo.load_ext(freq).index.max() <= e
    Feo = l1eo.load_eo("W")
    assert Feo.loc[:, [c for c in Feo.columns if c.startswith("JKP_")]].notna().all().all()  # JKP NaN (2026) ไม่เข้า
    w = world
    core, pool, _ = l1eo.pool_E(w["F"], w["Fext"], w["Feo"], w["masks"]["train"])
    assert pool.index.max() <= end and core.index.max() <= end
    ep = l1eo.epca_build(w["R"], w["E"], w["E"], w["masks"]["train"], n_perm=10)
    assert ep["a1"].index.max() <= end and ep["a2"].index.max() <= end
    og = l1eo.o_factors(w["F"], w["Fext"], w["Feo"], w["masks"]["train"])
    assert all(og[k].index.max() <= end for k in ("gold", "reit", "gold_simple", "reit_simple"))


# ───────────────────────── 04 · future-scramble ─────────────────────────
def _scramble(df, mask, seed):
    rng = np.random.default_rng(seed)
    out = df.copy()
    v = out.to_numpy(float).copy()
    v[mask] = rng.normal(scale=np.nanstd(v, axis=0, keepdims=True) + 1e-9, size=(int(mask.sum()), v.shape[1]))
    return pd.DataFrame(v, index=df.index, columns=df.columns)


def _pipeline(w, R, F, Feo, Fext):
    m = w["masks"]
    mtr = m["train"]
    E = w["E"]
    out = {}
    reps, cl = l1eo.sel_reps(R, E, mtr)
    out["reps"] = reps
    core, pool, coef = l1eo.pool_E(F, Fext, Feo, mtr)
    out["china_coef"] = coef
    pl = l1eo.placebo_eo(R, core, pool, mtr, list(reps.rep), pseudo=(m["ptr"], m["pte"]))
    out["placebo_tau"] = pl["tau"]
    out["placebo_logs"] = pl["logs"]
    sel, lg, ac = l1eo.stepwise_eo(R, core, pool, mtr, list(reps.rep), tau=pl["tau"], pseudo=(m["ptr"], m["pte"]), resid_spec=l1eo.resid_spec_E(F))
    out["sel"], out["step_log"], out["step_all"] = sel, lg, ac
    X1 = pd.concat([core, pool[sel]], axis=1) if sel else core
    gm = pd.DataFrame({"unit": E, "group_factor": [["e_USA", "e_HC", "ไม่มี", "e_ASIA", "e_CHINA(grp)"][i % 5] for i in range(len(E))]})
    Eg, pf, pfn, gcoef, span = l1eo.group_factors(gm, F, Fext, X1, mtr)
    out["group_coef"] = gcoef
    og = l1eo.o_factors(F, Fext, Feo, mtr)
    out["reit_coef"] = og["reit_coef"]
    ep = l1eo.epca_build(R, E, E, mtr, n_perm=20)
    out["epca"] = (ep["Lam_a"], ep["sd_a"], ep["k"], ep["Lam_c"], ep["sd_c"])
    hy = l1eo.hybrid_eo(R, X1, mtr, E)
    out["hybrid"] = (hy["W"], hy["s"], hy["coef"], hy["k_res"])
    return out


def _eq(a, b):
    if isinstance(a, pd.DataFrame):
        return a.equals(b)
    if isinstance(a, (tuple, list)):
        return all(_eq(x, y) for x, y in zip(a, b)) and len(a) == len(b)
    if isinstance(a, np.ndarray):
        return np.array_equal(a, b, equal_nan=True)
    return a == b


def test_eo_04_future_scramble(world):
    """สุ่มแทนผลตอบแทนกองและ factor ทุกแถว ≥ 2024-01-05 → ตัวแทน · log stepwise/placebo · τ · β residualize · Λ/σ/k* · hybrid · เท่าเดิมทุกบิต"""
    w = world
    te = w["idx"] >= pd.Timestamp("2024-01-05")
    base = _pipeline(w, w["R"], w["F"], w["Feo"], w["Fext"])
    assert base["sel"] and base["sel"][0] == "TERM" and base["hybrid"][3] >= 0
    R2, F2, Feo2, Fext2 = (_scramble(w["R"], te, 1), _scramble(w["F"], te, 2), _scramble(w["Feo"], te, 3), _scramble(w["Fext"], te, 4))
    assert not np.allclose(R2.loc[te].to_numpy(), w["R"].loc[te].to_numpy())
    scr = _pipeline(w, R2, F2, Feo2, Fext2)
    for k in base:
        assert _eq(base[k], scr[k]), f"future-scramble: {k} เปลี่ยน"


# ───────────────────────── 05 · splice ─────────────────────────
def _splice_world():
    idx = pd.date_range("2021-01-08", periods=260, freq="W-FRI")
    rng = np.random.default_rng(5)
    R = pd.DataFrame(index=idx)
    wk = pd.Timestamp(l1eo.SPLICE_WEEK)
    for u, (o, n) in l1eo.SPLICE_TABLE.items():
        old = pd.Series(rng.normal(size=260) * 0.01, index=idx)
        new = pd.Series(rng.normal(size=260) * 0.01, index=idx)
        old[old.index > wk] = np.nan
        old.loc[wk] = 0.0                       # NAV ค้างของรหัสเก่า
        old.iloc[0] = np.nan
        new[new.index < wk] = np.nan
        R[o], R[n] = old, new
    R["PLAIN"] = rng.normal(size=260) * 0.01
    return R, wk


def test_eo_05_splice_rule():
    """สัปดาห์ซ้อน (2023-12-08) ใช้รหัสใหม่ทุกบิต · ไม่มีแถวซ้ำ · หลังต่อ train 155 / test 104 · ไม่มีค่า 0 ปลอมจากรหัสเก่า"""
    R, wk = _splice_world()
    RU, tbl = l1eo.splice_units(R)
    assert set(tbl["unit"]) == set(l1eo.SPLICE_TABLE) and len(tbl) == 4
    assert not RU.columns.duplicated().any() and RU.index.is_unique
    assert RU.equals(l1eo.splice_monthly(R))                     # combine_first (รายเดือน) ให้อนุกรมเดียวกับกติกาสัปดาห์ในข้อมูลนี้
    for u, (o, n) in l1eo.SPLICE_TABLE.items():
        assert o not in RU.columns and n not in RU.columns
        assert RU.loc[wk, u] == R.loc[wk, n] and RU.loc[wk, u] != R.loc[wk, o]            # แถวซ้อน = ค่าของรหัสใหม่ทุกบิต
        before = RU.loc[RU.index < wk, u]
        assert before.equals(R.loc[R.index < wk, o])                                       # ก่อนซ้อน = รหัสเก่า (รวมสัปดาห์ 2023-12-01)
        assert RU.loc[RU.index >= wk, u].equals(R.loc[R.index >= wk, n])
        idx = RU.index
        ntr = RU[u].loc[window_mask(idx, "train") & (np.arange(len(idx)) >= 1)].notna().sum()
        nte = RU[u].loc[window_mask(idx, "test")].notna().sum()
        assert (ntr, nte) == (155, 104)
    assert (tbl["old_ret_at_week"] == 0.0).all() and (tbl["old_rows_after_week"] == 0).all() and (tbl["new_rows_before_week"] == 0).all()


def test_eo_05b_detect_pairs_rule():
    """กติกา 2.3 (ก–จ): พบ 4 คู่ครบ · class คู่ขนานของ Fund Class เดียวกัน (MGA · MGF · MCHINA) ไม่ถูกต่อ"""
    idx = pd.date_range("2021-01-08", periods=60, freq="W-FRI")
    NN = pd.DataFrame(False, index=idx, columns=["OLD1", "NEW1", "OLD2", "NEW2", "MGAG", "MGAI", "X"])
    NN.loc[idx[:30], "OLD1"] = True
    NN.loc[idx[29:], "NEW1"] = True      # ซ้อน 1
    NN.loc[idx[:30], "OLD2"] = True
    NN.loc[idx[20:], "NEW2"] = True      # ซ้อนมาก → ไม่ต่อ
    NN["MGAG"] = True
    NN["MGAI"] = True                    # class คู่ขนาน ซ้อนทั้งช่วง
    NN["X"] = True
    meta = pd.DataFrame({"policy": "E", "name_en": ["Foo Fund", "Eastspring Foo Fund", "Bar Fund", "Bar Fund", "MG Asia", "MG Asia", "Other"],
                         "reg_date": ["d1", "d1", "d2", "d2", "d3", "d3", "d4"], "fund_class": ["F1", "F2", "B", "B", "MGA", "MGA", "X"]},
                        index=NN.columns)
    pairs = l1eo.detect_splice_pairs(meta, NN)
    assert [(p["old"], p["new"]) for p in pairs] == [("OLD1", "NEW1")]


@real
def test_eo_05c_real_pairs_and_panel_untouched():
    g = l1eo.load_group_map()
    A = pd.read_parquet(TEAM / "data" / "aum_fam.parquet").set_index("FundCode")
    fp = pd.read_csv(io_l1.ROOT / "base_data" / "FundProfile.csv", usecols=["Fund Code", "Fund Class", "Registration_date"], encoding="utf-8-sig",
                     low_memory=False).drop_duplicates("Fund Code").set_index("Fund Code")
    meta = pd.DataFrame({"policy": g.set_index("FundCode")["policy"], "name_en": g.set_index("FundCode")["name_en"],
                         "reg_date": fp.loc[g["FundCode"], "Registration_date"].values, "fund_class": fp.loc[g["FundCode"], "Fund Class"].values}, index=g["FundCode"])
    P = pd.read_parquet(TEAM / "data" / "panel_weekly.parquet", columns=["FundCode", "date", "ret"])
    P = P[P.FundCode.isin(set(g.FundCode))]
    NN = P.assign(v=P.ret.notna()).pivot(index="date", columns="FundCode", values="v").fillna(False).astype(bool)
    pairs = l1eo.detect_splice_pairs(meta, NN)
    assert {(p["old"], p["new"]) for p in pairs} == set(l1eo.SPLICE_TABLE.values())
    assert io_l1.sha256_file(TEAM / "data" / "panel_weekly.parquet") == l1eo.S013_PINS[("team", "data/panel_weekly.parquet")]


# ───────────────────────── 06 · Shapley ─────────────────────────
def test_eo_06_shapley():
    rng = np.random.default_rng(6)
    T = 200
    a, b, c = rng.normal(size=T), rng.normal(size=T), rng.normal(size=T)
    y = 0.5 * a + 0.3 * b + 0.2 * rng.normal(size=T)
    blocks = [np.column_stack([a, np.r_[0, a[:-1]]]), np.column_stack([b, np.r_[0, b[:-1]]]), np.column_stack([c, np.r_[0, c[:-1]]])]
    s = l1eo.shapley_r2(y, blocks)
    # Σφ = R² เต็ม (1e-10) · ผู้เล่นคู่ lag = ผู้เล่นเดียว (K = 3 ไม่ใช่ 6)
    X = np.column_stack([np.ones(T)] + blocks)
    r = rg.ols_hac(y, X, 4)
    assert abs(s["phi"].sum() - r["r2"]) < 1e-10 and abs(s["r2"] - r["r2"]) < 1e-10 and len(s["phi"]) == 3
    assert s["phi"][0] > s["phi"][1] > s["phi"][2] - 1e-3
    # ผู้เล่นสมมาตรได้ค่าเท่ากัน
    sym = l1eo.shapley_r2(y, [np.column_stack([a]), np.column_stack([a]), np.column_stack([b])])
    assert abs(sym["phi"][0] - sym["phi"][1]) < 1e-12 and abs(sym["phi"].sum() - sym["r2"]) < 1e-10
    # ผู้เล่นศูนย์ได้ 0
    z = l1eo.shapley_r2(y, [np.column_stack([a]), np.zeros((T, 1)), np.column_stack([b])])
    assert abs(z["phi"][1]) < 1e-12 and abs(z["phi"].sum() - z["r2"]) < 1e-10
    # K = 1 → φ = R²
    one = l1eo.shapley_r2(y, [blocks[0]])
    assert abs(one["phi"][0] - one["r2"]) < 1e-12
    # แถวที่ factor ไม่ครบตก · rows mask
    b2 = [blocks[0].copy()]
    b2[0][:5] = np.nan
    assert l1eo.shapley_r2(y, b2)["n"] == T - 5
    # Shapley ของ R²_oos: Σφ = v(เต็ม) − v(∅)
    so = l1eo.shapley_oos(y, blocks, np.arange(T) < 140, np.arange(T) >= 140)
    assert abs(so["phi"].sum() - (so["v_full"] - so["v_empty"])) < 1e-10


# ───────────────────────── 07 · stepwise ─────────────────────────
def _toy_step(seed=7, T=260, loads=(("c1", 1.0), ("c2", 0.6)), n_pool=10, nf=40, g_only_first_half=None):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2021-01-08", periods=T, freq="W-FRI")
    mkt = rng.normal(size=T) * 0.01
    pool = pd.DataFrame({f"c{i + 1}": rng.normal(size=T) * 0.01 for i in range(n_pool)}, index=idx)
    core = pd.DataFrame({"MKT": mkt}, index=idx)
    R = pd.DataFrame(index=idx)
    mtr = window_mask(idx, "train")
    ptr = mtr & (idx <= pd.Timestamp("2022-06-24"))
    pte = mtr & (idx >= pd.Timestamp("2022-07-01"))
    for i in range(nf):
        y = 0.8 * mkt + 0.004 * rng.normal(size=T)
        for nm, b in loads:
            y = y + b * pool[nm].to_numpy()
        if g_only_first_half is not None:
            y = y + 3.0 * np.where(ptr, pool[g_only_first_half].to_numpy(), 0.0)
        R[f"u{i:02d}"] = y
    return R, core, pool, mtr, ptr, pte


def test_eo_07_stepwise_toy():
    R, core, pool, mtr, ptr, pte = _toy_step()
    reps = list(R.columns)
    sel, lg, ac = l1eo.stepwise_eo(R, core, pool, mtr, reps, tau=-2.0, pseudo=(ptr, pte))
    assert sel == ["c1", "c2"]                                   # เลือก 2 ตามลำดับความแรงแล้วหยุด
    assert lg["action"].tolist()[:2] == ["added", "added"] and lg["action"].iloc[-1] == "stop_tau"
    assert "share_reps_dBIC_le_m2" in ac.columns and ac[(ac["round"] == 1) & (ac["rank"] == 1)]["candidate"].iloc[0] == "c1"
    # deterministic
    sel2, lg2, _ = l1eo.stepwise_eo(R, core, pool, mtr, reps, tau=-2.0, pseudo=(ptr, pte))
    assert sel2 == sel and lg2.equals(lg)


def test_eo_07b_cap_and_ties():
    loads = tuple((f"c{i + 1}", 0.9 - 0.05 * i) for i in range(8))
    R, core, pool, mtr, ptr, pte = _toy_step(loads=loads, n_pool=9)
    sel, lg, _ = l1eo.stepwise_eo(R, core, pool, mtr, list(R.columns), tau=-2.0, pseudo=(ptr, pte))
    assert len(sel) == 5 and lg["action"].iloc[-1] == "stop_cap" and 1 + len(sel) == 6    # เพดาน MKT + 5 = 6
    # เสมอ → ลำดับใน pool (คอลัมน์ซ้ำกันทุกบิต)
    R2, core2, pool2, mtr2, ptr2, pte2 = _toy_step(loads=(("c1", 1.0),), n_pool=4)
    pool2["c2"] = pool2["c1"]
    sel2, _, ac2 = l1eo.stepwise_eo(R2, core2, pool2, mtr2, list(R2.columns), tau=-2.0, pseudo=(ptr2, pte2))
    assert sel2[0] == "c1"


def test_eo_07c_g3_blocks_pseudo_train_only():
    """candidate ที่มีสัญญาณเฉพาะ pseudo-train ถูกด่าน G3 หยุด (แม้ ΔBIC ผ่าน τ)"""
    R, core, pool, mtr, ptr, pte = _toy_step(loads=(), n_pool=5, g_only_first_half="c3")
    sel, lg, ac = l1eo.stepwise_eo(R, core, pool, mtr, list(R.columns), tau=-2.0, pseudo=(ptr, pte))
    assert sel == [] and lg["action"].iloc[0] == "stop_g3_pseudo_oos"
    assert lg["best"].iloc[0] == "c3" and bool(lg["g2_score_ok"].iloc[0]) and not bool(lg["g3_pseudo_ok"].iloc[0])
    # ไม่มี pseudo → ผ่านด่าน (เพื่อให้เห็นว่า G3 เป็นตัวหยุดจริง)
    sel2, _, _ = l1eo.stepwise_eo(R, core, pool, mtr, list(R.columns), tau=-2.0, pseudo=None)
    assert sel2 and sel2[0] == "c3"


# ───────────────────────── 08 · placebo / τ ─────────────────────────
def test_eo_08_tau_rule_and_zero_shift():
    # ตัวอย่างมือ
    assert l1eo.tau_from_placebo([0, 0], [3.0, 4.0]) == (-2.0, False)
    t, a = l1eo.tau_from_placebo([0, 2], [-1.0, -5.5])
    assert a and t == -5.5
    t, a = l1eo.tau_from_placebo([1, 0], [-1.5, -0.5])
    assert a and t == -2.0                                       # min(−2, min τ_s) = −2 เมื่อ τ_s ดีกว่า −2 ไม่ถึง
    # shift = 0 → เท่ากับ stepwise
    R, core, pool, mtr, ptr, pte = _toy_step()
    reps = list(R.columns)
    pl = l1eo.placebo_eo(R, core, pool, mtr, reps, shifts=(0,), tau0=-2.0, pseudo=(ptr, pte))
    sel, lg, _ = l1eo.stepwise_eo(R, core, pool, mtr, reps, tau=-2.0, pseudo=(ptr, pte), resid_spec=None)
    assert pl["shifts"][0]["selected"] == sel and pl["any_selected"]
    # shift จริงบนข้อมูลที่ไม่มีสัญญาณ → ไม่เลือก · τ = −2
    pl2 = l1eo.placebo_eo(R, core, pool, mtr, reps, shifts=(26, 52), pseudo=(ptr, pte))
    assert pl2["tau"] <= -2.0 and pl2["n_candidates_evaluated"] > 0


# ───────────────────────── 09 · factor กลุ่ม ─────────────────────────
def _gm(units, names):
    return pd.DataFrame({"unit": units, "group_factor": names})


def test_eo_09_group_factors(world):
    w = world
    mtr = w["masks"]["train"]
    core, pool, _ = l1eo.pool_E(w["F"], w["Fext"], w["Feo"], mtr)
    X1 = pd.concat([core, pool[["e_CHINA", "TERM"]]], axis=1)
    E = w["E"]
    names = [["e_USA", "e_HC", "ไม่มี", "e_ASIA", "e_CHINA(grp)", "e_IT", "e_ARKK"][i % 7] for i in range(len(E))]
    Eg, pf, pfn, coef, span = l1eo.group_factors(_gm(E, names), w["F"], w["Fext"], X1, mtr)
    X1v = X1.to_numpy(float)
    for c in Eg.columns:
        for j in range(X1.shape[1]):
            cc = np.corrcoef(Eg[c].to_numpy()[mtr], X1v[mtr, j])[0, 1]
            assert abs(cc) <= 1e-12, (c, j, cc)                                    # ตั้งฉาก X1 ใน train
        a_hat = float(coef.set_index("index").loc[c, "a"])
        assert abs(Eg[c].to_numpy()[mtr].mean() - a_hat) < 1e-12                  # mean(e_g, train) = â
    assert "e_AH" in Eg.columns and "e_CHINAg" not in Eg.columns                  # e_CHINA ∈ X1 → CHINA ใช้ A − H
    assert span.set_index("factor").loc["e_AH", "raw_China_All_in_span"]          # China All อยู่ใน span ของ X1 จริง
    assert not span.set_index("factor").loc["e_AH", "in_span_of_X1"]
    assert len(pf) == sum(1 for n in names if n != "ไม่มี") and all(isinstance(pf[u], pd.Series) for u in pf)  # ≤ 1 ตัวต่อกอง
    # ไม่มี e_CHINA ใน X1 → ใช้ China All
    Eg2, _, _, _, span2 = l1eo.group_factors(_gm(E, names), w["F"], w["Fext"], core, mtr)
    assert "e_CHINAg" in Eg2.columns and "e_AH" not in Eg2.columns


def test_eo_09b_groups_lt5_and_designer_labels():
    rows = []
    def add(code, name, policy="E", fc=None):
        rows.append(dict(FundCode=code, name_en=name, fund_class=fc if fc else code, splice_id="", policy=policy))
    for i in range(5):
        add(f"US{i}", f"Foo US Equity {i}")           # 5 กอง → ผ่าน
    for i in range(4):
        add(f"CL{i}", f"Foo Clean Energy {i}")        # 4 กอง → ไม่มี factor
    for i in range(7):
        add(f"CO{i}", f"Foo Consumer Brands {i}")     # ป้าย designer → ไม่มี factor ไม่ว่ากี่กอง
        add(f"GL{i}", f"Foo Global Equity {i}")
        add(f"EM{i}", f"Foo Emerging Markets {i}")
    for i in range(3):
        add(f"IN{i}", f"Foo India Equity {i}")        # < 5 → ไปกลุ่มแม่ ASIA
    for i in range(3):
        add(f"AS{i}", f"Foo Asia Equity {i}")
    E = l1eo.build_groups(pd.DataFrame(rows)).set_index("FundCode")
    assert (E.loc[[f"US{i}" for i in range(5)], "group_factor"] == "e_USA").all()
    assert (E.loc[[f"CL{i}" for i in range(4)], "group_factor"] == "ไม่มี").all()
    for pre in ("CO", "GL", "EM"):
        assert (E.loc[[f"{pre}{i}" for i in range(7)], "group_factor"] == "ไม่มี").all()
    assert (E.loc[[f"IN{i}" for i in range(3)], "group"] == "ASIA").all() and (E.loc[[f"IN{i}" for i in range(3)], "group_factor"] == "e_ASIA").all()
    assert (E.loc[[f"AS{i}" for i in range(3)], "group_factor"] == "e_ASIA").all()


# ───────────────────────── 10 · กฎชื่อ ─────────────────────────
def test_eo_10_name_rules_reproduce_csv():
    g = l1eo.load_group_map()
    E = l1eo.build_groups(g[["FundCode", "name_en", "fund_class", "splice_id", "policy"]]).set_index("FundCode")
    c = g.set_index("FundCode").loc[E.index]
    c_name = c["name_group"].fillna("NONE")
    assert (E["name_group"] == c_name).all(), E.index[E["name_group"] != c_name].tolist()
    assert (E["group"] == c["group"]).all()
    assert (E["group_factor"] == c["group_factor"]).all()
    assert (E["alt_factor_no_synonym"] == c["alt_factor_no_synonym"]).all()
    assert (E["group_n_U"] == c["group_n_U"]).all()


def test_eo_10b_cut_words_not_in_allowed_regex():
    for lvl, key, rx, rxs, fac, col, src, allowed in l1eo.RULES:
        if not allowed:
            continue
        for w in l1eo.CUT_WORDS:
            n = l1eo.norm_name(w)
            assert not re.search(rx, n) and not (rxs and re.search(rxs, n)), (key, w)
    # ex-Japan / ex-US ถูกตัด (มี \b นำหน้า · m13) · 'TEXAS' ไม่โดน
    assert l1eo.apply_name_rules("Tisco Asia Pacific ex Japan Equity")[1] == "ASIA"
    assert l1eo.apply_name_rules("Foo FLEX US Fund")[1] == "USA"


# ───────────────────────── 11 · O ─────────────────────────
def test_eo_11_o_factors(world):
    w = world
    mtr = w["masks"]["train"]
    o = l1eo.o_factors(w["F"], w["Fext"], w["Feo"], mtr)
    assert np.allclose(o["gold"]["GOLD_XS"], w["Feo"]["GLD_USD"] - w["F"]["SHV_USD"], atol=1e-15)
    assert np.allclose(o["reit"]["TERM"], w["F"]["IEF_USD"] - w["F"]["SHV_USD"], atol=1e-15)
    mk = o["reit"]["MKT"].to_numpy()
    assert abs(np.corrcoef(o["reit"]["REIT_e"].to_numpy()[mtr], mk[mtr])[0, 1]) < 1e-12        # REIT_e ⟂ MKT ใน train
    assert np.allclose(o["gold"]["FX"], l4.fx_factor(w["F"]), atol=0) and np.allclose(o["reit"]["FX"], l4.fx_factor(w["F"]), atol=0)
    assert list(o["reit"].columns) == ["MKT", "REIT_e", "FX", "TERM"] and list(o["gold"].columns) == ["GOLD_XS", "FX"]


# ───────────────────────── 12 · sig_count / placebo shift ─────────────────────────
def test_eo_12_sig_count_and_shift():
    # ตัวอย่างมือ: p ที่ BH ปฏิเสธ 10%
    se = np.ones(6)
    beta = np.array([4.0, 3.2, 2.9, 0.3, -3.5, 0.1])
    cl = {"a": 1, "b": 1, "c": 2, "d": 3, "e": 4, "f": 5}
    codes = list("abcdef")
    r = l1eo.sig_count(beta, se, codes, cl)
    from scipy import stats
    p = 2 * stats.norm.sf(np.abs(beta))
    o = np.argsort(p)
    adj = np.minimum.accumulate((p[o] * 6 / (np.arange(6) + 1))[::-1])[::-1]
    n_rej = int((adj <= 0.10).sum())
    assert r["n_sig"] == n_rej == 4 and r["n_pos"] == 3 and r["n_neg"] == 1
    assert r["n_groups"] == 3                                    # กองที่ผ่าน a,b (กลุ่ม 1) · c (กลุ่ม 2) · e (กลุ่ม 4) → กลุ่มไม่ซ้ำ 3
    # circular_shift = permutation ภายใน train (นอก train = NaN)
    idx = pd.date_range("2021-01-08", periods=260, freq="W-FRI")
    mtr = window_mask(idx, "train")
    I = pd.DataFrame({"x": np.arange(260.0)}, index=idx)
    S = l2.circular_shift(I, mtr, 26)
    assert S["x"][~mtr].isna().all() and sorted(S["x"][mtr].tolist()) == sorted(I["x"][mtr].tolist()) and not S["x"][mtr].equals(I["x"][mtr])


# ───────────────────────── 15 · cluster_bootstrap ─────────────────────────
def test_eo_15_cluster_bootstrap():
    cl = np.array([1, 1, 1, 2, 2, 3, 4, 4, 4, 4])
    seen = []

    def stat(idx):
        seen.append(np.bincount(idx, minlength=len(cl)))
        return np.array([np.mean(idx), 1.0])

    out = l1eo.cluster_bootstrap(stat, cl, n=300, seed=SEED)
    for cnt in seen:                                              # กลุ่มทั้งก้อนเข้า/ออกพร้อมกัน
        for g in np.unique(cl):
            c = cnt[cl == g]
            assert (c == c[0]).all()
    out2 = l1eo.cluster_bootstrap(stat, cl, n=300, seed=SEED)
    assert np.array_equal(out["draws"], out2["draws"])           # deterministic ที่ seed
    S = np.random.default_rng(1).normal(size=(10, 2))
    S[:, 1] = S[:, 0]                                             # สองแถวเท่ากัน → ส่วนต่างจับคู่ = 0 ทั้งช่วง
    out3 = l1eo.cluster_bootstrap(lambda i: np.array([np.median(S[i, 0]) - np.median(S[i, 1])]), cl, n=200, seed=SEED)
    assert out3["lo"][0] == 0.0 and out3["hi"][0] == 0.0


# ───────────────────────── ฟังก์ชันอื่น ─────────────────────────
def test_eo_sets_on_sim_and_compare():
    idx = pd.date_range("2021-01-08", periods=260, freq="W-FRI")
    rng = np.random.default_rng(3)
    RU = pd.DataFrame(rng.normal(size=(260, 8)) * 0.01, index=idx, columns=list("ABCDEFGH"))
    RU.loc[idx[:100], "C"] = np.nan                              # เริ่มช้า → ไม่ครบ train
    RU.loc[idx[:5], "D"] = np.nan                                # ไม่ balanced · ยังเข้า unbal52
    RU.loc[idx[:200], "E"] = np.nan                              # ไม่มี train
    pol = pd.Series({c: ("O" if c in "GH" else "E") for c in RU.columns})
    dup = pd.DataFrame({"a": ["A", "F"], "b": ["B", "C"]})
    s = l1eo.eo_sets(RU, pol, dup)
    L = l1eo.set_lists(s)
    assert "E" not in L["sel"] and "C" not in L["pca_balanced"] and "D" in L["pca_unbal52"] and "D" not in L["pca_balanced"]
    assert ("A" in L["dedup_keep"]) != ("B" in L["dedup_keep"])
    assert l1eo.compare_sets(s, s.copy()) == {}
    s2 = s.copy()
    s2.loc[s2.unit == "A", "sel"] = False
    assert "sel" in l1eo.compare_sets(s2, s)


def test_eo_epca_hybrid_group_report_smoke(world):
    """pipeline ครบบนข้อมูลจำลอง: E-PCA · hybrid · factor_report (Shapley รวม = R²) · GRS พอร์ต · lead diagnostic"""
    w = world
    m, R = w["masks"], w["R"]
    mtr = m["train"]
    E = w["E"]
    ep = l1eo.epca_build(R, E, E, mtr, n_perm=20)
    assert ep["a1"].shape == (260, ep["k"]) and ep["Lam_a"].shape == (len(E), ep["k"])
    core, pool, _ = l1eo.pool_E(w["F"], w["Fext"], w["Feo"], mtr)
    X1 = pd.concat([core, pool[["TERM", "FX"]]], axis=1)
    hy = l1eo.hybrid_eo(R, X1, mtr, E)
    assert hy["EH"].shape[1] == X1.shape[1] + hy["k_res"]
    model = l1eo.Model("E-X1", X1)
    fit, ro = l1eo.fit_model(R, model, mtr, m["test"], E)
    ref = pd.concat([(w["F"][c] - w["F"]["RF_BOT"]).rename(c) for c in ["MSCI_USA", "MSCI_CHINA_ALL_SHARES"]], axis=1)
    ctx = dict(masks=m, stab=E, clusters={u: i for i, u in enumerate(E)}, group=pd.Series({u: "G" for u in E}), ref=ref, a1=ep["a1"],
               axis="MKT", axis_series=core["MKT"])
    rep = l1eo.factor_report(R, model, fit, ro, E, ctx, interpret_names=(), with_oos_shap=True)
    assert list(rep["factor"]) == list(X1.columns) and rep["n_ref"].min() == len(E)
    sh = l1eo.shapley_table(R, model, E[:5], m, with_oos=False)
    g = sh.groupby("unit").agg(s=("phi", "sum"), r=("r2_full", "first"))
    assert np.allclose(g["s"], g["r"], atol=1e-10)
    assert (rep["vif_dimson"] < 5).all()
    ports = l1eo.grs_ports(pd.Series({u: ("A" if i < 20 else ("B" if i < 40 else "C")) for i, u in enumerate(E)}))
    cols, X, C = l1eo.port_returns(R, ports)
    d = l1eo.run_grs(cols, X, C, rg.lag_stack(X1.to_numpy(float)), m["test"] & m["pos1"])
    assert d["N_ports"] == 3 and np.isfinite(d["p"])
    ld = l1eo.lead_diag(R, X1, ["TERM", "FX"], E, mtr)
    assert set(ld) == {"TERM", "FX"} and all(0.0 <= v <= 1.0 for v in ld.values())


def test_eo_06b_shapley_table_dimson_real_path(world):
    """S2: เส้นทางจริง Model.players → shapley_table ใช้คู่ Dimson (lag 0 + lag 1 เป็นผู้เล่นเดียว) · Σφ = R² ของ fit_model บนแถวเดียวกัน (1e-10)"""
    w = world
    m, R = w["masks"], w["R"]
    mtr = m["train"]
    core, pool, _ = l1eo.pool_E(w["F"], w["Fext"], w["Feo"], mtr)
    X1 = pd.concat([core, pool[["TERM", "FX"]]], axis=1)
    E = w["E"][:12]
    gm = _gm(w["E"], [["e_USA", "e_HC", "ไม่มี"][i % 3] for i in range(len(w["E"]))])
    Eg, pf, pfn, _, _ = l1eo.group_factors(gm, w["F"], w["Fext"], X1, mtr)
    for model in (l1eo.Model("x1", X1), l1eo.Model("x2", X1, per_fund=pf, pf_name=pfn)):
        fit, _ = l1eo.fit_model(R, model, mtr, m["test"], E)
        sh = l1eo.shapley_table(R, model, E, m, with_oos=True)
        g = sh.groupby("unit").agg(s=("phi", "sum"), r=("r2_full", "first"), n=("factor", "size"))
        r2fit = pd.Series(fit.r2, index=fit.codes)
        assert np.allclose(g["s"], g["r"], atol=1e-10)
        assert np.allclose(g.loc[E, "r"].to_numpy(), r2fit[E].to_numpy(), atol=1e-10)          # = R² เต็มของโมเดล Dimson (ไม่ใช่ lag 0 อย่างเดียว)
        assert (g["n"] == (model.K + np.array([u in model.per_fund for u in g.index]))).all()   # ผู้เล่นต่อกอง = K (+1 factor กลุ่ม) ไม่ใช่ 2K
    u0 = E[0]
    lag0 = l1eo.shapley_r2(R[u0].to_numpy(float), [X1[c].to_numpy(float) for c in X1.columns], rows=mtr & m["pos1"])
    assert lag0["r2"] < fit.r2[0] - 1e-6                                                         # lag 0 อย่างเดียวให้ R² ต่ำกว่า Dimson (กันถอยกลับไปแบบเดิม)


def test_eo_pins_check_function():
    d = l1eo.check_pins({k: v for k, v in l1eo.S013_PINS.items() if k[1] in ("specs/S012_group_map.csv", "specs/S013_pca_sets.csv")})
    assert len(d) == 2
    with pytest.raises(ValueError):
        l1eo.check_pins({("team", "specs/S012_group_map.csv"): "0" * 64})


@real
def test_eo_14_m1_matches_s009():
    """M1 ของ S012 (fit train) เทียบ runs/S009/alpha_fund.csv แถว M1 · train · alpha_pct และ t · เฉพาะรหัสที่ไม่ใช่หน่วยต่อ · ≤ 1e-8"""
    from external import line3  # noqa: F401
    g = l1eo.load_group_map()
    F = io_l1.load_factors("W")
    R = io_l1.load_returns("W")
    mtr, mte = window_mask(R.index, "train"), window_mask(R.index, "test")
    a = pd.read_csv(TEAM / "runs" / "S009" / "alpha_fund.csv")
    a = a[(a["row"] == "M1") & (a["window"] == "train")].set_index("FundCode")
    spl = set(l1eo.code_to_unit())
    codes = [c for c in a.index if c in R.columns and c not in spl]
    base1a = l2.load_l1_factors(TEAM / "runs" / "S003" / "factors_S003_weekly.parquet", "1a")
    base_df, pf = l1eo.build_M1(F, base1a, TEAM / "runs" / "S005" / "primary_index.csv", TEAM / "runs" / "S006" / "resid_B_coef.csv", codes)
    fit, ro, _ = l3.fit_perfund(R, base_df, pf, mtr, mte, codes, 52)
    al = pd.Series(fit.alpha * 5200, index=fit.codes)
    t = pd.Series(fit.t_alpha_hac, index=fit.codes)
    assert len(codes) > 150
    assert np.nanmax(np.abs(al.to_numpy() - a.loc[fit.codes, "alpha_pct"].to_numpy())) <= 1e-8
    assert np.nanmax(np.abs(t.to_numpy() - a.loc[fit.codes, "t"].to_numpy())) <= 1e-8


@real
def test_eo_13_run_twice_same_sha(tmp_path):
    """run.py 2 รอบ (โหมด --sim --smoke) → sha256 ไฟล์ผลเท่ากันทุกไฟล์ (ยกเว้น log · เวลาใน run_meta)"""
    run = TEAM / "runs" / "S012" / "run.py"
    root = io_l1.ROOT
    outs = []
    for k in (1, 2):
        out = tmp_path / f"o{k}"
        for ph in ("pre", "full"):
            r = subprocess.run([sys.executable, str(run), "--sim", "--smoke", "--phase", ph, "--out", str(out)], cwd=root, capture_output=True, text=True,
                               env={**os.environ, "PYTHONPATH": "."})
            assert r.returncode == 0, r.stdout[-2000:] + r.stderr[-2000:]
        outs.append(out)
    skip = {"run.log", "run_pre.log", "run_meta.json", "run_meta_pre.json", "repro_check.json", "run_pre.py", "results.md"}
    h = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    a = {p.name: h(p) for p in sorted(outs[0].iterdir()) if p.is_file() and p.name not in skip}
    b = {p.name: h(p) for p in sorted(outs[1].iterdir()) if p.is_file() and p.name not in skip}
    assert a.keys() == b.keys() and len(a) > 20
    diff = [k for k in a if a[k] != b[k]]
    assert not diff, diff
