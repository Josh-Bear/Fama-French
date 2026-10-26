"""test_port_01 … test_port_16 (S015 ข้อ 5.4) + test ฟังก์ชันอื่นของ lib/port.py
ข้อมูลจำลองเป็นหลัก (test ที่อ่านผลตอบแทน/ค่า realized จริงติดป้าย `real` และรันเมื่อ S014_REAL=1 — หลังเขียน decisions_pre_run.md)
รัน: PYTHONPATH=. ./.venv/bin/python -m pytest -p no:cacheprovider .claude/factor_team/lib/tests/test_port.py"""
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
import port

real = pytest.mark.skipif(os.environ.get("S014_REAL") != "1", reason="ต้องอ่านผลตอบแทน/ค่า realized จริง — รันหลังเขียน decisions_pre_run.md (S014_REAL=1)")
TEAM = io_l1.TEAM


# ───────────────────────── โลกจำลอง ─────────────────────────
@pytest.fixture(scope="module")
def world():
    return port.sim_world(seed=5)


def _qdefs(w, n_q=4, start=90, step=14):
    """ไตรมาสจำลอง: t = anchor · e = anchor ถัดไป + 1 วัน (ไม่ใช่ศุกร์) · ช่วงถือ = 13 anchor ถัดจาก e"""
    idx = w["idx"]
    qs = []
    for q in range(n_q):
        p = start + q * step
        t = idx[p]
        anchors = idx[p + 1:p + 14]
        hold = pd.DataFrame({"FundCode": ["U0", "U1", "U2"], "kind": ["E", "E", "G"], "weight": [0.2, 0.1, 0.7] if q % 2 == 0 else [0.45, 0.25, 0.3]})
        qs.append((t, anchors, hold))
    return qs


def _mp():
    return pd.DataFrame({"unit": ["U0", "U1", "U2", "U3"], "group_factor": ["e_USA", "ไม่มี", "GOLD_XS + FX", "ไม่มี"]}, index=["U0", "U1", "U2", "U3"])


def _fit_all(w, variant="main"):
    mp = _mp()
    return [(t, a, port.quarter_fit(w["R"], w["FR"], t, h, mp, variant)) for t, a, h in _qdefs(w)]


# ───────────────────────── 01 · Σw = 1 ─────────────────────────
def test_port_01_weights_sum_to_one(world):
    H = port.load_m052()
    assert np.allclose(H.groupby("t")["weight"].sum().to_numpy(), 1.0, atol=1e-12) and H["t"].nunique() == 15 and len(H) == 58
    rng = np.random.default_rng(1)
    Rh = rng.normal(scale=0.03, size=(13, 4))
    W, rp = port.drift_weights([0.4, 0.3, 0.2, 0.1], Rh)
    assert np.allclose(W.sum(axis=1), 1.0, atol=1e-12) and np.allclose(W[0], [0.4, 0.3, 0.2, 0.1])
    assert np.allclose(rp, np.sum(W * Rh, axis=1), atol=1e-15)


# ───────────────────────── 02 · future-scramble ─────────────────────────
def _scr(df, mask, seed):
    rng = np.random.default_rng(seed)
    v = df.to_numpy(float).copy()
    v[mask] = rng.normal(scale=np.nanstd(v, axis=0, keepdims=True) + 1e-9, size=(int(mask.sum()), v.shape[1]))
    return pd.DataFrame(v, index=df.index, columns=df.columns)


def _digest(qf):
    B, seB, w, s2 = port.exposure(qf)
    Sig, n = port.sigma_f(qf)
    d = port.var_decomp(B, Sig, w, s2)
    out = [B, seB, s2, Sig, d["share"], np.array([d["share_eps"], d["V"]]), qf["coef"].select_dtypes("number").to_numpy() if len(qf["coef"]) else np.zeros(1)]
    for f in qf["fits"]:
        out += [np.array([f["alpha"], f["s2"], f["adj_r2"]]), f["b0"], f["b1"], f["beta"], f["se_beta"]]
    return out


def test_port_02_future_scramble(world):
    w = world
    t, a, h = _qdefs(w)[1]
    mp = _mp()
    base = port.quarter_fit(w["R"], w["FR"], t, h, mp)
    te = w["idx"] > t
    R2 = _scr(w["R"], te, 1)
    F2, Fx2, Fe2 = _scr(w["F"], te, 2), _scr(w["Fext"], te, 3), _scr(w["Feo"], te, 4)
    FR2 = port.factor_frames(F2, Fx2, Fe2)
    assert not np.allclose(R2.loc[te].to_numpy(), w["R"].loc[te].to_numpy())
    scr = port.quarter_fit(R2, FR2, t, h, mp)
    for x, y in zip(_digest(base), _digest(scr)):
        assert np.array_equal(x, y, equal_nan=True), "future-scramble: ค่าของไตรมาส t เปลี่ยน"
    assert base["mask"].sum() > 0 and w["idx"][base["mask"]].max() <= t


# ───────────────────────── 03 · เอกลักษณ์ attribution ─────────────────────────
def test_port_03_attribution_identity(world):
    w = world
    rf = w["FR"]["rf"]
    for t, a, qf in _fit_all(w):
        df, W = port.attribute_weekly(qf, a, w["R"], rf)
        assert (df["id_err"].abs() < 1e-12).all()
        comp = df[[c for c in df.columns if c.startswith("C_")]].sum(axis=1) + df["A"] + df["E"]
        assert np.allclose(comp, df["x"], atol=1e-12) and np.allclose(df["x"], df["r_p"] - df["rf"], atol=1e-12)
        rec = port.reconcile_period(df)
        assert abs(sum(rec["components"].values()) - rec["SUM"]) < 1e-12 and abs(rec["SUM"] + rec["K"] - rec["CEX"]) < 1e-12


# ───────────────────────── 04 · Euler ─────────────────────────
def test_port_04_euler(world):
    for t, a, qf in _fit_all(world):
        B, seB, wv, s2 = port.exposure(qf)
        Sig, n = port.sigma_f(qf)
        d = port.var_decomp(B, Sig, wv, s2)
        assert abs(d["share"].sum() + d["share_eps"] - 1.0) < 1e-12 and abs(d["V"] - (d["systematic"] + d["eps"])) < 1e-15
    B = np.array([0.6, -0.2, 0.1])
    sig = np.array([0.03, 0.02, 0.05])
    d = port.var_decomp(B, np.diag(sig ** 2), np.array([0.5, 0.5]), np.array([1e-5, 2e-5]))
    assert np.allclose(d["share"], B ** 2 * sig ** 2 / d["V"], atol=1e-14)               # factor ตั้งฉาก → share = B²σ²/V
    assert abs(d["share"].sum() + d["share_eps"] - 1) < 1e-12


# ───────────────────────── 05 · mapping ─────────────────────────
def _map_inputs():
    H = port.load_m052()
    uni = pd.read_csv(TEAM / "data" / "universe.csv").set_index("FundCode")
    gmap = l1eo.load_group_map()
    prof = pd.read_csv(io_l1.ROOT / "base_data" / "FundProfile.csv", encoding="utf-8-sig", low_memory=False, usecols=["Fund Code", "Fund Name EN", "FX Risk Flag"]
                       ).drop_duplicates("Fund Code").set_index("Fund Code")
    return H, uni, gmap, prof


def test_port_05_mapping():
    H, uni, gmap, prof = _map_inputs()
    mp = port.map_holdings(H, uni, gmap, prof).set_index("FundCode")
    assert H["FundCode"].nunique() == 23 and len(mp) == 23 and mp["unit"].nunique() == 23 and (mp["kind"] == "E").sum() == 20 and (mp["kind"] == "G").sum() == 3
    assert set(mp.index[mp["how"] == "ตัวแทน family"]) == {"KKP GINFRAEQ-H-F", "ONE-INDIAOPP-IA", "PRINCIPAL GOPP-C"}
    assert mp.loc["KKP GINFRAEQ-H-F", "unit"] == "KKP GINFRAEQ-H" and mp.loc["ONE-INDIAOPP-IA", "unit"] == "ONE-INDIAOPP-RA" and mp.loc["PRINCIPAL GOPP-C", "unit"] == "PRINCIPAL GOPP-A"
    assert set(mp.index[~mp["in_U"]]) == {"LHJAPE-A", "ONE-INDIAOPP-IA", "SCBGOLDHP"}
    assert mp.loc["LHJAPE-A", "group_factor"] == "e_JAPAN" and mp.loc["ONE-INDIAOPP-IA", "group_factor"] == "e_INDIA"
    assert set(mp.index[mp["kind"] == "G"]) == {"K-GOLD-A(A)", "BGOLD", "SCBGOLDHP"} and (mp.loc[mp["kind"] == "G", "group_factor"] == "GOLD_XS + FX").all()
    assert list(mp.index[mp["group_factor"] == "ไม่มี"]) == ["DAOL-GOLD", "FCSCBSETE", "PRINCIPAL GOPP-C"]
    assert list(mp.index[mp["fx_flag_diff"]]) == ["PRINCIPAL GOPP-C"]
    ds = pd.read_csv(TEAM / "scratch" / "factor-designer_s015_holdings.csv").drop_duplicates("FundCode").set_index("FundCode")
    assert (ds["unit"] == mp.loc[ds.index, "unit"]).all() and (ds["group"] == mp.loc[ds.index, "group"]).all()


# ───────────────────────── 06 · ไม่มี AQR · ไม่มีแถวเกินช่วง ─────────────────────────
def test_port_06_no_aqr_and_no_late_rows(world):
    for fq in ("W", "M"):
        df = port.load_eo_noaqr(fq)
        assert not any(c.upper().startswith("AQR") for c in df.columns)
        assert df.index.max() <= (pd.Timestamp("2025-12-26") if fq == "W" else pd.Timestamp("2025-12-31"))
    w = world
    for t, a, qf in _fit_all(w):
        assert w["idx"][qf["mask"]].max() <= t and w["idx"][qf["mask"]].max() <= pd.Timestamp("2025-12-26")
        assert qf["FU"].index.max() <= pd.Timestamp("2025-12-26")
        assert all(np.isfinite(f["resid"][qf["mask"]][np.isfinite(f["resid"][qf["mask"]])]).all() for f in qf["fits"])
        assert all(not np.isfinite(f["resid"][~qf["mask"]]).any() for f in qf["fits"])         # ไม่มี residual นอกหน้าต่าง


# ───────────────────────── 07 · พอร์ตจาก factor ล้วน ─────────────────────────
def test_port_07_pure_factor_portfolio(world):
    w = world
    base = w["FR"]["base"]
    R = pd.DataFrame(index=w["idx"])
    alpha = 0.0004
    R["S"] = alpha + 0.8 * base["MKT"] - 0.3 * base["FX"] + 0.15 * base["CMA"]            # b1 = 0 · ε = 0
    t, anchors = w["idx"][120], w["idx"][122:135]
    hold = pd.DataFrame({"FundCode": ["S"], "kind": ["E"], "weight": [1.0]})
    mp = pd.DataFrame({"unit": ["S"], "group_factor": ["ไม่มี"]}, index=["S"])
    qf = port.quarter_fit(R, w["FR"], t, hold, mp)
    f = qf["fits"][0]
    assert np.allclose(f["beta"], [0.8, -0.3, 0.15], atol=1e-9) and abs(f["alpha"] - alpha) < 1e-12 and np.allclose(f["b1"], 0, atol=1e-9)
    df, W = port.attribute_weekly(qf, anchors, R, w["FR"]["rf"])
    B, _, wv, _ = port.exposure(qf)
    F = qf["FU"].loc[anchors].sum().to_numpy()
    assert np.allclose(df[["C_" + c for c in qf["names"]]].sum().to_numpy(), B * F, atol=1e-10) and abs(df["E"].sum()) < 1e-10
    assert abs(df["A"].sum() - alpha * len(anchors)) < 1e-10
    rec = port.reconcile_period(df)
    rf_off = rec["cum_rf"]
    l2 = port.attribute_L2(qf, B, rec["cum_rp"], rf_off, F, len(anchors))
    assert abs(l2["eps"] - rec["K"]) < 1e-10 and abs(l2["A"] - alpha * len(anchors)) < 1e-10
    assert all(abs(l2["BF"][c] - df["C_" + c].sum()) < 1e-10 for c in qf["names"])


# ───────────────────────── 08 · run.py 2 รอบ ─────────────────────────
@real
def test_port_08_run_twice_same_sha(tmp_path):
    run = TEAM / "runs" / "S014" / "run.py"
    outs = []
    for k in (1, 2):
        out = tmp_path / f"o{k}"
        for ph in ("pre", "full"):
            r = subprocess.run([sys.executable, str(run), "--sim", "--smoke", "--phase", ph, "--out", str(out)], cwd=io_l1.ROOT, capture_output=True, text=True,
                               env={**os.environ, "PYTHONPATH": "."})
            assert r.returncode == 0, r.stdout[-2000:] + r.stderr[-2000:]
        outs.append(out)
    skip = {"run.log", "run_pre.log", "run_meta.json", "run_meta_pre.json", "repro_check.json", "run_pre.py", "results.md"}
    h = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    a = {p.name: h(p) for p in sorted(outs[0].iterdir()) if p.is_file() and p.name not in skip}
    b = {p.name: h(p) for p in sorted(outs[1].iterdir()) if p.is_file() and p.name not in skip}
    assert a.keys() == b.keys() and len(a) >= 15
    assert [k for k in a if a[k] != b[k]] == []


# ───────────────────────── 09 · ช่วงถือ ─────────────────────────
def _quarters_real():
    H = port.load_m052()
    RZ = port.load_realized(full=False)
    idx = io_l1.load_factors("W").index
    return port.quarter_table(H, RZ, idx)


def test_port_09_holding_periods():
    QT, anchors = _quarters_real()
    D = pd.read_csv(TEAM / "scratch" / "factor-designer_s015_quarters.csv")
    for c in ("t", "e", "e_next_official", "first_anchor", "last_anchor", "n_weeks", "start_mis_bd", "end_mis_bd", "anchors_t_to_e", "n_hold", "has_gold", "realized_days", "truncated", "t_wd", "e_wd"):
        assert (QT[c].astype(str).to_numpy() == D[c].astype(str).to_numpy()).all(), c
    for c in ("x_hold", "x_model", "w_gold"):
        assert np.allclose(QT[c].to_numpy(float), D[c].to_numpy(float), atol=1e-12), c
    allh = pd.DatetimeIndex(sorted(d for a in anchors.values() for d in a))
    idx = io_l1.load_factors("W").index
    assert len(allh) == 195 and allh.is_unique and (allh == idx[(idx >= allh[0]) & (idx <= pd.Timestamp("2025-12-26"))]).all()
    assert allh[0] == pd.Timestamp("2022-04-08") and allh[-1] == pd.Timestamp("2025-12-26") and (QT["n_weeks"] == 13).all()
    t0, t1 = pd.Timestamp("2022-03-31"), pd.Timestamp("2022-06-30")
    assert pd.Timestamp("2022-04-01") not in allh and pd.Timestamp("2022-07-01") in set(anchors[t0])
    for t, a in anchors.items():
        assert (a > t).all()                                                           # ไม่มีแถวช่วงถือ ≤ t_q
    y22 = [d for t in (pd.Timestamp("2022-03-31"), pd.Timestamp("2022-06-30"), pd.Timestamp("2022-09-30")) for d in anchors[t]]
    assert len(y22) == 39 and min(y22) == pd.Timestamp("2022-04-08") and max(y22) == pd.Timestamp("2022-12-30")
    for yr, n in ((2023, 52), (2024, 52), (2025, 52)):
        ts_ = [t for t in anchors if anchors[t][0].year == yr or anchors[t][-1].year == yr]
        assert sum(int(d.year == yr) for t in ts_ for d in anchors[t]) == n


# ───────────────────────── 10 · ความตั้งฉากของ e_g ─────────────────────────
def test_port_10_group_factor_orthogonality(world):
    w = world
    mp = pd.DataFrame({"unit": ["U0", "U1"], "group_factor": ["e_USA", "e_ASIA"]}, index=["U0", "U1"])
    hold = pd.DataFrame({"FundCode": ["U0", "U1"], "kind": ["E", "E"], "weight": [0.5, 0.5]})
    coefs = []
    for t in (w["idx"][100], w["idx"][140]):
        qf = port.quarter_fit(w["R"], w["FR"], t, hold, mp)
        X1 = w["FR"]["base"][port.CORE].to_numpy(float)
        m = qf["mask"]
        for c in qf["EG"].columns:
            for j in range(3):
                assert abs(np.corrcoef(qf["EG"][c].to_numpy()[m], X1[m, j])[0, 1]) <= 1e-12
            row = qf["coef"].set_index("index").loc[c]
            expect = w["FR"]["I"][c].to_numpy() - X1 @ np.array([row["b_MKT"], row["b_FX"], row["b_CMA"]])
            assert np.allclose(qf["EG"][c].to_numpy(), expect, atol=1e-15)             # ใช้ b̂ ของไตรมาสนั้นทุกแถว (รวมช่วงถือ)
        coefs.append(qf["coef"].set_index("index").loc["e_USA", ["b_MKT", "b_FX", "b_CMA"]].to_numpy())
    assert not np.allclose(coefs[0], coefs[1])                                         # b̂ ใหม่ทุกไตรมาส


# ───────────────────────── 11 · buy-and-hold ─────────────────────────
def test_port_11_buy_and_hold_value():
    rng = np.random.default_rng(11)
    Rh = rng.normal(scale=0.04, size=(13, 5))
    w0 = np.array([0.3, 0.25, 0.2, 0.15, 0.1])
    W, rp = port.drift_weights(w0, Rh)
    assert abs((np.prod(1 + rp) - 1) - float(w0 @ (np.prod(1 + Rh, axis=0) - 1))) < 1e-12


# ───────────────────────── 12 · แถว realized ของ L2 ─────────────────────────
def test_port_12a_realized_meta_rows():
    QT, anchors = _quarters_real()
    Z = port.load_realized(full=False)
    assert len(Z) == 15 and (Z["horizon"] == "Q").all() and (Z["portfolio"] == port.MODEL_ROW).all()
    assert list(Z.columns) == [c for c in port.REALIZED_META if c != "t"]            # โหลดเฉพาะคอลัมน์โครง (ไม่เปิดค่าผลตอบแทน)


@real
def test_port_12_realized_full_columns():
    H = port.load_m052()
    Z = port.load_realized(full=True)
    assert len(Z) == 15 and Z["ret_gross"].notna().all() and Z["rf_ann"].notna().all()
    for t, g in H.groupby("t"):
        wt = port.parse_weights(Z.loc[t, "weights"])
        mine = dict(zip(g["FundCode"], g["weight"]))
        assert set(wt) == set(mine) and max(abs(wt[k] - mine[k]) for k in mine) <= 1e-12, t


def test_port_12b_parse_weights_formats():
    for s in ('{"A": 0.25, "B": 0.75}', "A:0.25;B:0.75", "A=0.25|B=0.75"):
        assert port.parse_weights(s) == {"A": 0.25, "B": 0.75}


# ───────────────────────── 13 · ตัวกระทบยอด S2 ─────────────────────────
def test_port_13_compounding_reconcile(world):
    w = world
    rf = w["FR"]["rf"]
    res = {}
    for variant in ("main", "PB"):
        dfs = []
        for t, a, qf in _fit_all(w, variant):
            df, W = port.attribute_weekly(qf, a, w["R"], rf)
            dfs.append(df)
            rec = port.reconcile_period(df)
            assert abs(sum(rec["components"].values()) + rec["K"] - rec["CEX"]) < 1e-12 and abs(rec["CEX"] - (np.prod(1 + df["r_p"]) - np.prod(1 + df["rf"]))) < 1e-12
        allw = pd.concat(dfs)
        rec = port.reconcile_period(allw)
        assert abs(sum(rec["components"].values()) + rec["K"] - rec["CEX"]) < 1e-12
        res[variant] = rec
        sh = port.shares_table(rec, min_base=-1.0)
        assert abs(sum(sh.values()) - 1.0) < 1e-12                                       # ส่วนแบ่งรวมแถว A · E · K = 100%
    assert abs(res["main"]["K"] - res["PB"]["K"]) < 1e-15 and abs(res["main"]["CEX"] - res["PB"]["CEX"]) < 1e-15          # K เท่ากันทุกการแยก
    assert all(np.isnan(v) for v in port.shares_table(dict(components={"C_MKT": 0.001}, CEX=0.01, K=0.0)).values())      # |CEX| < 2 pp → N/A
    # L2 หลายไตรมาส
    rows = []
    for t, a, qf in _fit_all(w):
        df, W = port.attribute_weekly(qf, a, w["R"], rf)
        rec = port.reconcile_period(df)
        B = port.exposure(qf)[0]
        F = qf["FU"].loc[a].sum().to_numpy()
        rg_, rfo = rec["cum_rp"] + 0.002, rec["cum_rf"] + 0.0003                         # ผลทางการจำลอง
        d = port.attribute_L2(qf, B, rg_, rfo, F, len(a))
        d.update(ret_gross=rg_, rf_off=rfo)
        rows.append(d)
    r2 = port.reconcile_L2(rows)
    assert abs(sum(r2["BF"].values()) + r2["A"] + r2["eps"] + r2["K"] - r2["CEX"]) < 1e-12
    # P-C
    pcs = [port.split_returns(qf, a, w["R"], rf, w["FR"]["gld_thb"], 0.5) for t, a, qf in _fit_all(w)]
    rp_ = port.reconcile_PC(pcs)
    assert abs(rp_["sum_AE"] + rp_["K_PC"] - rp_["diff"]) < 1e-12


# ───────────────────────── 14 · ธง mapping ─────────────────────────
def test_port_14_flags_structural():
    H, uni, gmap, prof = _map_inputs()
    mp = port.map_holdings(H, uni, gmap, prof)
    QT, anchors = _quarters_real()
    qa = pd.read_csv(TEAM / "data" / "qa_friday_gap_E_units.csv").set_index("unit")["grp_A"].astype(bool)
    idx = io_l1.load_factors("W").index
    nn = pd.DataFrame(True, index=idx, columns=sorted(set(mp["unit"])))
    HT = port.holding_table(H, mp, anchors, idx, nn, qa)
    D = pd.read_csv(TEAM / "scratch" / "factor-designer_s015_holdings.csv")
    assert len(HT) == len(D) == 58
    for c in ("t", "FundCode", "kind", "unit", "group", "fx_flag_holding", "fx_flag_unit", "fx_flag_diff", "fri_gap_grpA", "n_gap_anchor_in_hold", "nav_fri_gap", "n_hold_anchor"):
        assert (HT[c].astype(str).to_numpy() == D[c].astype(str).to_numpy()).all(), c
    assert np.allclose(HT["weight"].to_numpy(float), D["weight"].to_numpy(float), atol=1e-9)
    assert int(HT.loc[HT["FundCode"] == "K-GOLD-A(A)", "nav_fri_gap"].sum()) == 7 and int(HT.loc[HT["FundCode"] == "TISCOCH", "nav_fri_gap"].sum()) == 1
    assert HT.loc[(HT["FundCode"] == "ONE-INDIAOPP-IA"), "fri_gap_grpA"].iloc[0] == "na" and int(HT["fx_flag_diff"].sum()) == 1


@real
def test_port_14b_flags_notna_columns():
    H, uni, gmap, prof = _map_inputs()
    mp = port.map_holdings(H, uni, gmap, prof)
    QT, anchors = _quarters_real()
    idx = io_l1.load_factors("W").index
    P = pd.read_parquet(TEAM / "data" / "panel_weekly.parquet", columns=["FundCode", "date", "ret"])
    P = P[P.FundCode.isin(set(mp["unit"]))]
    nn = P.assign(v=P["ret"].notna()).pivot(index="date", columns="FundCode", values="v").reindex(idx).fillna(False).astype(bool)
    qa = pd.read_csv(TEAM / "data" / "qa_friday_gap_E_units.csv").set_index("unit")["grp_A"].astype(bool)
    HT = port.holding_table(H, mp, anchors, idx, nn, qa)
    D = pd.read_csv(TEAM / "scratch" / "factor-designer_s015_holdings.csv")
    for c in ("n_win156", "n_hold_rows"):
        assert (HT[c].to_numpy() == D[c].to_numpy()).all(), c
    assert (HT["n_hold_rows"] == 13).all()


# ───────────────────────── 15 · P-C ─────────────────────────
def test_port_15_pc(world):
    w = world
    rf = w["FR"]["rf"]
    for t, a, qf in _fit_all(w):
        d = port.split_returns(qf, a, w["R"], rf, w["FR"]["gld_thb"], 0.5)
        assert abs(d["id_err"]) < 1e-12 and abs(d["ae_err"]) < 1e-12 and not d["RG_proxy"]
    t, a, _ = _qdefs(w)[0]
    mp = _mp()
    hold = pd.DataFrame({"FundCode": ["U0", "U1"], "kind": ["E", "E"], "weight": [0.6, 0.4]})
    qf = port.quarter_fit(w["R"], w["FR"], t, hold, mp)
    d = port.split_returns(qf, a, w["R"], rf, w["FR"]["gld_thb"], 1.0)
    assert d["RG_proxy"] and abs(d["x_hold"] - 1.0) < 1e-15 and abs(d["R_panel"] - d["R_E"]) < 1e-12
    assert abs(d["AE"] - 0.43 * (d["R_E"] - d["R_G"])) < 1e-12 and abs(d["R_G"] - (np.prod(1 + w["FR"]["gld_thb"].loc[a].to_numpy()) - 1)) < 1e-15


# ───────────────────────── 16 · grep ─────────────────────────
def test_port_16_no_forbidden_strings():
    forbidden = ("load_eo(", "factors_eo_weekly", "factors_eo_monthly", "manifest_eo.json")
    for p in (TEAM / "lib" / "port.py", TEAM / "runs" / "S014" / "run.py"):
        if p.exists():
            s = p.read_text(encoding="utf-8")
            for f in forbidden:
                assert f not in s, (p.name, f)


# ───────────────────────── อื่น ๆ ─────────────────────────
def test_port_pins_and_window():
    d = port.check_pins({k: v for k, v in port.PINS.items() if k[1] in ("m052_frontier_holdings.csv", "specs/S012_group_map.csv")})
    assert len(d) == 2
    with pytest.raises(ValueError):
        port.check_pins({("team", "specs/S012_group_map.csv"): "0" * 64})
    idx = pd.date_range("2021-01-08", periods=260, freq="W-FRI")
    m = port.window_mask(idx, pd.Timestamp("2022-03-31"))
    assert m.sum() == 12 + 0 or m.sum() > 0
    assert idx[m].max() <= pd.Timestamp("2022-03-31") and m.sum() == int((idx <= "2022-03-31").sum())
    m2 = port.window_mask(idx, idx[200])
    assert m2.sum() == 156


def test_port_cov_resid_appendix_and_pd(world):
    w = world
    t, a, qf = _fit_all(w)[0]
    B, seB, wv, s2 = port.exposure(qf)
    Sig, n = port.sigma_f(qf)
    pe = port.cov_resid_appendix(qf, B, Sig)
    assert 0 <= pe["share_eps_full"] < 1 and 0 <= pe["share_eps_diag"] < 1 and pe["n_common"] > 40
    rf = w["FR"]["rf"]
    d = qf["fits"][0]
    anch = w["idx"][qf["mask"]][-52:]
    wk = pd.DataFrame({"FundCode": d["code"], "week": anch, "ret": w["R"][d["unit"]].loc[anch].to_numpy() + rf.loc[anch].to_numpy()})
    out = port.pd_betas(w["R"], w["FR"], dict(fits=[d]), wk, "ret")
    assert out[0]["n_rows"] == 52 and out[0]["n_dropped_nonfri"] == 0 and np.isfinite(out[0]["beta"]).all()
