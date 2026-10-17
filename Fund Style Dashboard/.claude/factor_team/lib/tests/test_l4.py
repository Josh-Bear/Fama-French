"""test ของ L4 (S007 ข้อ 8.4 + S008 I.2 + S009 1.7/2) · เลข spec 48–68 · ชื่อฟังก์ชันขึ้นต้น test_s9_<เลข> เพื่อไม่ให้ชนกับ test_NN เดิม
(test_l3.py เดิมใช้เลขถึง 49) · test 60 ส่วน "run.py 2 รอบ sha256 เท่ากัน" ทำใน runs/S009/repro_check เป็นเงื่อนไขก่อนรายงาน"""
import re

import numpy as np
import pandas as pd
import pytest
from scipy import stats

import external as ex
import io_l1
import l2
import l3
import l4
import nfactors as nf
import regress as rg
import tests_stat as ts
from samples import window_mask

IDX = pd.date_range("2021-01-08", periods=260, freq="W-FRI")
MTR, MTE = window_mask(IDX, "train"), window_mask(IDX, "test")
S006 = io_l1.TEAM / "runs" / "S006"
S005 = io_l1.TEAM / "runs" / "S005"


def _sim(N=20, seed=3, alpha=None, K=2):
    rng = np.random.default_rng(seed)
    f = pd.DataFrame(rng.normal(0, 0.02, (260, K)), index=IDX, columns=[f"f{i}" for i in range(K)])
    Y = {}
    for i in range(N):
        a = 0.0 if alpha is None else alpha.get(i, 0.0)
        Y[f"s{i}"] = a + f.to_numpy() @ rng.normal(0.6, 0.3, K) + rng.normal(0, 0.01, 260)
    return f, pd.DataFrame(Y, index=IDX)


@pytest.fixture(scope="module")
def real():
    F = io_l1.load_factors("W")
    return F


def test_s9_48_fx_spot_carry(real):
    F = real
    fx = l4.fx_factor(F)
    assert np.allclose(fx.to_numpy(), ex.line3(F, "3a")["FX"].to_numpy(), atol=1e-15, rtol=0)
    sc = l4.spot_carry(F)
    assert np.abs(sc["SPOT"] + sc["CARRY"] - fx).max() <= 1e-15
    assert fx.index.max() < pd.Timestamp("2026-01-01") and sc.index.max() < pd.Timestamp("2026-01-01")
    src = open(l4.__file__, encoding="utf-8").read()
    assert not re.search(r"F\[[\"'](USDTHB|[A-Za-z_]*_lvl)", src)  # ไม่อ่านคอลัมน์ USDTHB / *_lvl จาก F
    assert not any(("USDTHB" in c or "_lvl" in c) for c in sc.columns)


def test_s9_49_e_from_s006(real):
    F = real
    I, blocks = l2.index_set(F)
    M28 = I[blocks["M28"]]
    f = l2.load_l1_factors(io_l1.TEAM / "runs" / "S003" / "factors_S003_weekly.parquet", "1a")
    E_ref, _ = l3.residualize(M28[l3.P4], f, MTR)
    E = l4.e_from_s006(M28, f, S006 / "resid_B_coef.csv", "1a")
    assert list(E.columns) == l3.P4
    assert np.nanmax(np.abs(E.to_numpy() - E_ref.to_numpy())) <= 1e-12
    M2 = M28.copy()
    M2.loc[MTE, "MSCI_JAPAN"] += 0.5
    E2 = l4.e_from_s006(M2, f, S006 / "resid_B_coef.csv", "1a")
    assert np.array_equal(E2.to_numpy()[MTR], E.to_numpy()[MTR])


def test_s9_50_ref_L3B_matches_S006(real):
    F = real
    R = io_l1.load_returns("W")
    U = io_l1.load_universe().set_index("FundCode")
    S = l2.fund_sets(R, U, io_l1.load_dup_pairs())
    EVAL = S["EVAL"]
    I, blocks = l2.index_set(F)
    M28 = I[blocks["M28"]]
    fp = io_l1.TEAM / "runs" / "S003" / "factors_S003_weekly.parquet"
    f = l2.load_l1_factors(fp, "1a")
    E = l4.e_from_s006(M28, f, S006 / "resid_B_coef.csv", "1a")
    prim = pd.read_csv(S005 / "primary_index.csv")
    prim = prim[prim.form == "1a@4"].set_index("FundCode")["index"]
    pf = l3.perfund_from_primary(E, prim, EVAL)
    fit, ro, _ = l3.fit_perfund(R, f, pf, MTR, MTE, EVAL, 52)
    ref = pd.read_csv(S006 / "fund_level.csv")
    ref = ref[ref.row == "R3"].set_index("FundCode").loc[EVAL]
    for nm, arr in (("alpha", fit.alpha), ("t_alpha_hac", fit.t_alpha_hac), ("adj_r2", fit.adj_r2), ("bic", fit.bic), ("r2_oos", ro)):
        assert np.nanmax(np.abs(arr - ref[nm].to_numpy())) <= 1e-10, nm


FEE_COLS = ["As of Date", "Fund Code", "Complex Type Code", "Code", "Rate", "Unit Rate", "Actual Value"]


def _fee(rows):
    return pd.DataFrame([dict(zip(FEE_COLS, r)) for r in rows], dtype=str)


def test_s9_51_parse_fee():
    assert l4.parse_fee("ไม่มี") == 0 and l4.parse_fee("ยกเว้น") == 0
    assert l4.parse_fee("0.535%") == 0.535 and l4.parse_fee("0.535") == 0.535 and l4.parse_fee(" 1 ") == 1.0
    assert np.isnan(l4.parse_fee("abc")) and np.isnan(l4.parse_fee(np.nan)) and np.isnan(l4.parse_fee(None)) and np.isnan(l4.parse_fee(""))


def test_s9_52_themes_match_md():
    txt = open(io_l1.DATA / "QA_ACWI_CD_group.md", encoding="utf-8").read()
    sec = txt.split("## ตารางกอง (40)")[1].split("## จำนวนต่อ บลจ.")[0]
    rows = [ln.split("|")[1:3] for ln in sec.splitlines() if ln.startswith("|") and not ln.startswith("|---") and "FundCode" not in ln]
    tm = {b.strip(): a.strip() for a, b in rows}
    assert len(tm) == 40 and len(l4.THEMES_ACWI_CD) == 40
    key = {"เทคโนโลยี": "เทคโนโลยี", "Healthcare": "Healthcare", "EV": "EV", "Consumer": "Consumer", "Global": "Global", "Sustainable": "Sustainable",
           "หลายธีม": "หลายธีม", "ผิดกลุ่ม": "ผิดกลุ่ม"}
    for c, g in tm.items():
        assert l4.THEMES_ACWI_CD[c] == key[g], c
    assert l4.THEMES_ACWI_CD["M-SUKUK"] == "ผิดกลุ่ม"


def _grp_setup():
    funds = [f"A{i:02d}" for i in range(14)] + ["F1", "F2", "O1", "MGAPVD", "MGAG", "M-SUKUK"]
    pol = pd.Series({**{f"A{i:02d}": "E" for i in range(14)}, "F1": "F", "F2": "F", "O1": "O", "MGAPVD": "E", "MGAG": "E", "M-SUKUK": "F"})
    prim = pd.Series({**{f"A{i:02d}": ("X" if i < 11 else "Y") for i in range(14)}, "F1": "X", "F2": "X", "O1": "X", "MGAPVD": "MSCI_ACWI_CD", "MGAG": "MSCI_ACWI_CD", "M-SUKUK": "MSCI_ACWI_CD"})
    cl = pd.Series({c: i for i, c in enumerate(funds)})
    cl["A01"] = cl["A00"]
    cl["A03"] = cl["A02"]
    return funds, pol, prim, cl


def test_s9_53_group_labels():
    funds, pol, prim, cl = _grp_setup()
    lab = l4.group_labels(prim, pol, funds, merge={"MGAPVD": "MGAG"}, excl={"MSCI_ACWI_CD": ["M-SUKUK"]})
    d = lab.set_index("FundCode")["group"]
    assert "MGAPVD" not in d.index and d["MGAG"] == "MSCI_ACWI_CD" and d["M-SUKUK"] == "G-F"
    assert d["F1"] == "G-F" and d["O1"] == "G-O" and d["A00"] == "X" and d["A12"] == "Y"


def test_s9_62_group_table_rules():
    funds, pol, prim, cl = _grp_setup()
    lab = l4.group_labels(prim, pol, funds, merge={"MGAPVD": "MGAG"})
    full = pd.Series({c: True for c in funds})
    for c in ["A06", "A07", "A08", "A09", "A10"]:
        full[c] = False
    gt = l4.group_table(lab, cl, full).set_index("group")
    x = gt.loc["X"]
    assert x["n"] == 11 and x["n_indep_all"] == 9 and x["n_tr"] == 6 and x["n_indep_tr"] == 4
    assert x["method"] == "LOO-mean" and x["reps"].split(";")[0] == "A00"
    assert gt.loc["Y", "method"] == "small"
    big = pd.DataFrame(dict(FundCode=[f"B{i:02d}" for i in range(24)], group="MSCI_ACWI_CD", policy="E"))
    clb = pd.Series({c: i // 1 for i, c in enumerate(big.FundCode)})
    clb["B01"] = clb["B00"]
    g2 = l4.group_table(big, clb, pd.Series({c: True for c in big.FundCode}), ).iloc[0]
    assert g2["method"] == "PCA" and g2["n_indep_tr"] == 23 and g2["dummy"] and "B00" in g2["reps"] and "B01" not in g2["reps"]
    assert l4.cluster_reps(["B05", "B01", "B00"], clb)[clb["B00"]] == "B00"


def test_s9_54_alpha_table():
    f, Y = _sim(N=30, alpha={0: 0.004, 1: -0.004})
    prov = rg.CommonFactors(f)
    m = np.ones(260, bool)
    m[0] = False
    fit = rg.fit_funds(Y, prov, m, 52)
    se, fb = l4.alpha_se(fit)
    A = l4.alpha_table(fit, se)
    j = 5
    D = prov.design()
    ok = m & np.isfinite(D).all(1)
    r = rg.ols_hac(Y.iloc[:, j].to_numpy()[ok], np.column_stack([np.ones(ok.sum()), D[ok]]), 4)
    assert abs(se[j] - r["se"][0]) <= 1e-12
    assert abs(A.alpha_pct.iloc[j] - fit.alpha[j] * 5200) <= 1e-12
    assert abs(A.mda.iloc[j] - (stats.norm.ppf(0.975) + stats.norm.ppf(0.8)) * se[j] * 5200) <= 1e-10
    z = stats.norm.ppf(1 - 0.10 / 60)
    assert abs(A.mda_mt.iloc[j] - (z + stats.norm.ppf(0.8)) * se[j] * 5200) <= 1e-10
    p = 2 * stats.norm.sf(np.abs(fit.t_alpha_hac))
    assert np.array_equal(A.bh.to_numpy(), ts.bh(p, 0.10)[0]) and np.array_equal(A.by.to_numpy(), l2.by(p, 0.10)[0])
    assert (A.by.sum() <= A.bh.sum()) and A.bh.iloc[0] and A.bh.iloc[1]
    fit.t_alpha_hac[7] = 0.0
    se2, fb2 = l4.alpha_se(fit, Y, prov, m)
    assert fb2[7] and np.isfinite(se2[7])


def test_s9_55_ff_bootstrap():
    f, Y = _sim(N=20, alpha={0: 0.006, 1: -0.006, 2: 0.006})
    Y["dup"] = Y["s5"]
    prov = rg.CommonFactors(f)
    m = np.ones(260, bool)
    m[0] = False
    fit = rg.fit_funds(Y, prov, m, 52)
    kw = dict(B=60, block=4, seed=7, min_rows=104)
    rd, act, sm = l4.ff_bootstrap(Y, prov, list(Y.columns), m, fit.alpha, **kw)
    rd2, _, sm2 = l4.ff_bootstrap(Y, prov, list(Y.columns), m, fit.alpha, **kw)
    assert rd.equals(rd2) and sm.equals(sm2)
    assert rd["frac_bh"].mean() <= 0.10 + 0.08
    s = sm.set_index("stat")
    assert s.loc["p99_ALL", "p_boot_upper"] < 0.05 and s.loc["p1_ALL", "p_boot_lower"] < 0.05
    # บล็อกเดียวกันทุกกอง: กองซ้ำได้ t* เท่ากันทุกรอบ → สองกองที่เหมือนกันไม่ทำให้จำนวนกองต่อรอบเปลี่ยน
    Yd = Y[["s5", "dup"]]
    fd = rg.fit_funds(Yd, prov, m, 52)
    rdd, _, _ = l4.ff_bootstrap(Yd, prov, ["s5", "dup"], m, fd.alpha, **kw)
    assert (rdd["p1_ALL"] == rdd["p99_ALL"]).all() and (rdd["n_funds"] == 2).all()
    # จำนวนกองต่อรอบไม่เท่ากันไม่ error: กองที่ขาดข้อมูล
    Ym = Y.copy()
    Ym.iloc[:150, 3] = np.nan
    fm = rg.fit_funds(Ym, prov, m, 52)
    rdm, _, smm = l4.ff_bootstrap(Ym, prov, list(Ym.columns), m, fm.alpha, **kw)
    assert rdm["n_funds"].min() >= 1 and np.isfinite(smm.set_index("stat").loc["frac_bh", "p_boot_upper"])


def _upanel(N=14, seed=5, k=1, load=1.0):
    rng = np.random.default_rng(seed)
    g = rng.normal(0, 1, (260, k))
    U = {f"g{i}": (g @ rng.normal(load, 0.2, k) if load else 0) + rng.normal(0, 0.6, 260) for i in range(N)}
    return pd.DataFrame(U, index=IDX)


def test_s9_56_group_factor_loo():
    u = _upanel(N=14, load=0.8)
    codes = list(u.columns)
    cl = pd.Series({c: i for i, c in enumerate(codes)})
    cl["g1"] = cl["g0"]
    reps = [c for c in codes if c != "g1" and c != "g13"]  # g13 = กองที่ไม่ใช่ตัวแทน
    base = l4.group_factor_loo(u, codes, cl, "pca", 1, MTR, reps=reps, min_peer=3)
    assert "g1" not in base["g0"]["peers"] and "g0" not in base["g0"]["peers"] and "g13" not in base["g5"]["peers"]
    u2 = u.copy()
    u2["g0"] = u2["g0"] * 3 + 1
    ch = l4.group_factor_loo(u2, codes, cl, "pca", 1, MTR, reps=reps, min_peer=3)
    assert np.array_equal(ch["g0"]["g"], base["g0"]["g"], equal_nan=True) and np.array_equal(ch["g1"]["g"], base["g1"]["g"], equal_nan=True)
    assert not np.allclose(ch["g5"]["g"][MTR], base["g5"]["g"][MTR])
    u3 = u.copy()
    u3["g13"] = u3["g13"] + 5
    ch3 = l4.group_factor_loo(u3, codes, cl, "pca", 1, MTR, reps=reps, min_peer=3)
    assert np.array_equal(ch3["g5"]["g"], base["g5"]["g"])
    u4 = u.copy()
    u4.loc[MTE] = u4.loc[MTE] * 2 + 1
    ch4 = l4.group_factor_loo(u4, codes, cl, "pca", 1, MTR, reps=reps, min_peer=3)
    assert np.array_equal(ch4["g5"]["g"][MTR], base["g5"]["g"][MTR])  # น้ำหนักจาก train ตรึง
    mn = l4.group_factor_loo(u, codes, cl, "mean", 1, MTR)
    assert "g1" not in mn["g0"]["peers"] and mn["g2"]["g"].shape == (260, 1)
    ps = l4.group_factor_loo(u, codes, cl, "pca", 1, MTR, reps=reps[:5], min_peer=8)
    assert ps["g5"]["flag"] == "peer_small" and ps["g5"]["method"] == "mean"


def test_s9_57_group_k_and_null():
    u1 = _upanel(N=14, load=1.2)
    r1 = l4.group_k(u1, list(u1.columns), MTR, n_perm=200)
    assert r1["k_pa"] == 1 and r1["k_g"] == 1
    u0 = _upanel(N=14, load=0)
    r0 = l4.group_k(u0, list(u0.columns), MTR, n_perm=200)
    assert r0["k_g"] == 0
    assert l4.group_k(u1, list(u1.columns), MTR, n_perm=200) == r1
    rng = np.random.default_rng(11)
    # null: factor จริงมีผล → ΔR²_oos จริง > null
    g = u1.mean(axis=1).to_numpy()
    y = {c: 0.8 * g + rng.normal(0, 0.3, 260) for c in u1.columns}
    codes = list(u1.columns)
    D = np.column_stack([rng.normal(0, 1, 260), rng.normal(0, 1, 260)])
    D = np.hstack([D, rg.lag_stack(D)[:, 2:]])
    pool = [f"p{i}" for i in range(20)]
    upool = _upanel(N=20, seed=9, load=0)
    upool.columns = pool
    uall = pd.concat([u1, upool], axis=1)

    def dfn(i, gg):
        out = l4.fit_with_factor(y[i], D, gg, MTR, MTE)
        return out["d_r2_oos"]

    n_peer = {c: 12 for c in codes[:6]}
    peers_real = {c: [x for x in codes if x != c] for c in codes[:6]}
    true = np.median([dfn(c, l4.peer_factor(uall, peers_real[c], "mean", 1, MTR)) for c in codes[:6]])
    d1 = l4.random_group_null(dfn, codes[:6], lambda i: pool, n_peer, "mean", 1, uall, MTR, n_draw=20, seed=3)
    d2 = l4.random_group_null(dfn, codes[:6], lambda i: pool, n_peer, "mean", 1, uall, MTR, n_draw=20, seed=3)
    assert np.array_equal(d1, d2)
    sm = l4.null_summary(true, d1)
    assert sm["p_null"] < 0.1 and true > sm["null_p95"]


def test_s9_58_xsec_wls():
    rng = np.random.default_rng(2)
    N = 40
    X = pd.DataFrame(dict(const=1.0, a=rng.normal(size=N), b=rng.normal(size=N)))
    se = rng.uniform(0.5, 2, N)
    y = 0.3 + 0.5 * X.a.to_numpy() + rng.normal(0, se)
    cl = np.arange(N) // 2
    r = l4.xsec_wls(y, se, X, cl, wald_cols=["a", "b"])
    w = 1 / se ** 2
    Xv = X.to_numpy()
    A = np.linalg.inv(Xv.T @ (Xv * w[:, None]))
    b = A @ (Xv.T @ (w * y))
    assert np.abs(r["coef"].coef.to_numpy() - b).max() <= 1e-10
    e = y - Xv @ b
    meat = sum(np.outer((Xv[cl == g] * (w * e)[cl == g][:, None]).sum(0), (Xv[cl == g] * (w * e)[cl == g][:, None]).sum(0)) for g in np.unique(cl))
    G, K = len(np.unique(cl)), 3
    V = G / (G - 1) * (N - 1) / (N - K) * A @ meat @ A
    assert np.abs(r["coef"].se_cr1.to_numpy() - np.sqrt(np.diag(V))).max() <= 1e-10
    bs = b[1:]
    W = bs @ np.linalg.solve(V[1:, 1:], bs)
    assert abs(r["wald"]["W"] - W) <= 1e-9
    r1 = l4.xsec_wls(y, se, X, np.arange(N))
    assert np.abs(r1["coef"].se_cr1.to_numpy() - r1["coef"].se_hc1.to_numpy()).max() <= 1e-10


def test_s9_59_fx_gap_and_68():
    codes = [f"c{i}" for i in range(12)]
    fxb = pd.Series(np.arange(12, dtype=float), index=codes) + 0.5
    a_no = pd.Series([-1.0] * 6 + [-5.0] * 6, index=codes)
    a_fx = pd.Series([-2.0] * 6 + [-2.5] * 6, index=codes)
    grp = pd.Series("G1", index=codes)
    tab, sm = l4.fx_gap(a_no, a_fx, fxb, grp, min_n=10, min_groups=1)
    assert abs(tab.gap_noFX[0] - 4.0) < 1e-12 and abs(tab.gap_FX[0] - 0.5) < 1e-12 and abs(tab.ratio[0] - 0.125) < 1e-12
    # N/A เมื่อ |gap_noFX| < 0.5
    a_small = pd.Series([-1.0] * 6 + [-1.2] * 6, index=codes)
    tab2, sm2 = l4.fx_gap(a_small, a_fx, fxb, grp, min_n=10, min_groups=1)
    assert np.isnan(tab2.ratio[0]) and sm2["na"]
    # กลุ่มเล็กกว่า min_n ไม่เข้า · คำนวณได้ < min_groups → N/A
    tab3, sm3 = l4.fx_gap(a_no, a_fx, fxb, grp, min_n=13, min_groups=1)
    assert len(tab3) == 0
    tab4, sm4 = l4.fx_gap(a_no, a_fx, fxb, grp, min_n=10, min_groups=3)
    assert sm4["na"] and np.isnan(sm4["median_ratio"])


def test_s9_68_carry_diag(real):
    d = l4.carry_diag(real)
    c = l4.spot_carry(real)["CARRY"].to_numpy()
    assert abs(d["uncentered_share"] - c.mean() ** 2 / (c.mean() ** 2 + c.var())) <= 1e-12
    assert abs(d["lag1_corr"] - np.corrcoef(c[1:], c[:-1])[0, 1]) <= 1e-12 and 0 <= d["r2_trend"] <= 1


def test_s9_60_no_lookahead_fx_beta_group(real):
    F = real
    R = io_l1.load_returns("W")
    funds = list(R.columns[:15])
    b1 = l4.fx_beta(R, F, MTR, funds)
    R2 = R.copy()
    R2.loc[MTE] = R2.loc[MTE] * 3 + 0.01
    F2 = F.copy()
    F2.loc[MTE, "SHV_THB"] += 0.02
    b2 = l4.fx_beta(R2, F2, MTR, funds)
    assert np.array_equal(b1.to_numpy(), b2.to_numpy(), equal_nan=True)
    u = _upanel(N=14)
    u2 = u.copy()
    u2.loc[MTE] = u2.loc[MTE] * 2
    assert l4.group_k(u, list(u.columns), MTR, n_perm=100) == l4.group_k(u2, list(u.columns), MTR, n_perm=100)


def test_s9_61_ter_table_cases():
    rows = [
        # (ก) as-of แรกไม่มี Actual (≤2025) แต่ถัดไปมี → ใช้ตัวถัดไป
        ("20230510", "A", "FEEMF", "TT", "3.0", "", ""), ("20231031", "A", "FEEMF", "TT", "3.0", "", "1.5"), ("20260630", "A", "FEEMF", "TT", "3.0", "", "1.7"),
        # (จ) มีทั้ง Rate ≤ 2025 และ Actual ปี 2026 → Actual 2026
        ("20230510", "B", "FEEMF", "TT", "2.5", "", ""), ("20260630", "B", "FEEMF", "TT", "2.5", "", "1.2"),
        # (ฉ) แค่ Rate
        ("20230510", "C", "FEEMF", "TT", "2.0", "", ""),
        # (ช) Actual ≤ 2025 อยู่ as-of หลัง Rate ≤ 2025 → Actual ≤ 2025
        ("20230510", "D", "FEEMF", "TT", "2.0", "", ""), ("20231031", "D", "FEEMF", "TT", "2.0", "", "0.9"),
        # (ค) แค่ Actual 2026 · (ง) ไม่มีเลย
        ("20260630", "E", "FEEMF", "TT", "", "", "1.1"),
        ("20230510", "H", "FEEMF", "OF", "1.0", "", "0.5"),
        # Rate 2026 เท่านั้น
        ("20260630", "I", "FEEMF", "TT", "4.0", "", ""),
        # OF สำหรับ QA
        ("20231031", "A", "FEEMF", "OF", "1.0", "", "1.0"), ("20260630", "E", "FEEMF", "OF", "1.0", "", "0.8"),
        ("20231031", "D", "FEEMF", "OF", "1.0", "", "1.5"),
    ]
    fee = _fee(rows)
    t = l4.ter_table(fee, ["A", "B", "C", "D", "E", "H", "I"]).set_index("FundCode")
    assert (t.loc["A", "ter"], t.loc["A", "ter_src"], t.loc["A", "ter_vintage"]) == (1.5, "actual", "le2025") and t.loc["A", "ter_asof"] == pd.Timestamp("2023-10-31")
    assert (t.loc["B", "ter"], t.loc["B", "ter_src"], t.loc["B", "ter_vintage"]) == (1.2, "actual", "y2026") and t.loc["B", "d_v2026"] == 1 and t.loc["B", "d_rate"] == 0
    assert (t.loc["C", "ter"], t.loc["C", "ter_src"], t.loc["C", "ter_vintage"]) == (2.0, "rate", "le2025") and t.loc["C", "d_rate"] == 1
    assert (t.loc["D", "ter"], t.loc["D", "ter_src"]) == (0.9, "actual")
    assert (t.loc["E", "ter"], t.loc["E", "ter_vintage"]) == (1.1, "y2026")
    assert np.isnan(t.loc["H", "ter"]) and pd.isna(t.loc["H", "ter_src"])
    assert (t.loc["I", "ter_src"], t.loc["I", "ter_vintage"]) == ("rate", "y2026")
    # ตัวอย่างมือของ S008 (vintage_first): B → Rate ≤ 2025 (ลำดับเดิม) ต่างจากกติกาใหม่
    t8 = l4.ter_table(fee, ["B"], rule="vintage_first").set_index("FundCode")
    assert (t8.loc["B", "ter"], t8.loc["B", "ter_src"]) == (2.5, "rate")
    # ตาราง Rate − Actual และความเสถียรข้ามรุ่น (A: Actual 1.5 → 1.7)
    qa = l4.ter_qa(fee, t.reset_index(), pol=pd.Series({c: "E" for c in "ABCDEHI"}), thr=0.5)
    sa = qa["rate_minus_actual_same_row"]  # A 3.0−1.5 · B 2.5−1.2 · D 2.0−0.9 (E: Rate ว่างที่แถวนั้น → ตัด)
    assert sa["n"] == 3 and abs(sa["median"] - 1.3) < 1e-12 and sa["frac_pos_or_zero"] == 1.0
    sb = qa["rate_le2025_minus_actual_chosen"]  # A 1.5 · B 1.3 · D 1.1
    assert sb["n"] == 3 and abs(sb["median"] - 1.3) < 1e-12
    cv = qa["cross_vintage_stability"]  # เฉพาะ A มี Actual ทั้งสองรุ่น
    assert cv["n"] == 1 and abs(cv["median"] - 0.2) < 1e-12
    assert qa["n_nan"] == 1 and set(qa["rate_funds"]) == {"C", "I"}
    # TT ≥ OF บน as-of ที่เลือก: A ✓ · D ✗ (0.9 < 1.5) · E ✓ · B ไม่มี OF ที่ as-of นั้น → n=3 frac=2/3
    assert qa["tt_ge_of"]["n"] == 3 and abs(qa["tt_ge_of"]["frac"] - 2 / 3) < 1e-12 and qa["ter_dropped"] is False
    assert l4.ter_qa(fee, t.reset_index(), thr=0.9)["ter_dropped"] is True
    assert {(c["ter_vintage"], c["ter_src"], c["policy"]): c["n"] for c in qa["cells"]}[("le2025", "actual", "E")] == 2


def test_s9_61b_build_x_rules():
    n = 30
    df = pd.DataFrame(dict(TER=np.linspace(0, 2, n), DIV=[1] * 5 + [0] * 25, d_v2026=[1] * 15 + [0] * 15, d_rate=[0] * 29 + [1],
                           G1=[1] * 10 + [0] * 20, G2=[0] * 28 + [1, 1]), index=[f"f{i}" for i in range(n)])
    X, d, dr = l4.build_x(df, ["TER"], ["DIV", "d_v2026", "d_rate"], ["G1", "G2"])
    assert "d_rate" not in X.columns and dr["funds"] == ["f29"] and len(X) == 29 and "G2" in dr["cols"] and "G1" in X.columns
    assert "d_v2026" in X.columns and "DIV" in X.columns and X["const"].eq(1).all()
    df2 = df.copy()
    df2["d_v2026"] = [1] * 2 + [0] * 28
    X2, _, dr2 = l4.build_x(df2, ["TER"], ["DIV", "d_v2026", "d_rate"], ["G1"])
    assert "d_v2026" not in X2.columns and "d_v2026" in dr2["cols"] and len(X2) == 29


def test_s9_63_group_k_fallback():
    u = _upanel(N=6, load=1.0)
    r = l4.group_k(u, list(u.columns), MTR, n_perm=50)
    assert r["flag"] == "ed_small" and r["k_g"] is None
    u2 = _upanel(N=12, load=1.0)
    rr = l4.group_k(u2, list(u2.columns), MTR, n_perm=50, ed_fn=lambda e, k: None)
    assert rr["flag"] == "ed_none" and rr["k_g"] is None


def test_s9_64_random_null_pool_and_nopeer_overlap():
    u = _upanel(N=10, load=0.5)
    pool = [f"q{i}" for i in range(15)]
    up = _upanel(N=15, seed=8, load=0)
    up.columns = pool
    uall = pd.concat([u, up], axis=1)
    seen = []

    def dfn(i, g):
        return float(np.nanmean(g)) + 0.0

    members = list(u.columns)[:4]
    orig = l4.peer_factor

    def spy(u_, peers, *a, **k):
        seen.append(list(peers))
        return orig(u_, peers, *a, **k)

    l4.peer_factor = spy
    try:
        d = l4.random_group_null(dfn, members, lambda i: pool, {c: 7 for c in members}, "mean", 1, uall, MTR, n_draw=5, seed=2)
    finally:
        l4.peer_factor = orig
    assert len(d) == 5 and all(len(p) == 7 and set(p) <= set(pool) and len(set(p)) == 7 for p in seen)
    assert len(seen) == 5 * len(members)
    # median บนสมาชิกจริงเท่านั้น · deterministic
    d2 = l4.random_group_null(dfn, members, lambda i: pool, {c: 7 for c in members}, "mean", 1, uall, MTR, n_draw=5, seed=2)
    assert np.array_equal(d, d2)
    s = l4.null_summary(0.5, np.array([0.1] * 199 + [0.6]))
    assert abs(s["p_null"] - 2 / 201) < 1e-12 or abs(s["p_null"] - (1 + 1) / 201) < 1e-12


def test_s9_65_q2_verdict():
    tab = pd.DataFrame(dict(bh1=[1, 1, 1, 0, 1], bh2=[1, 1, 0, 0, 1], sg1=[1, 0, 1, 1, 1], sg2=[1, 1, 1, 1, 1], div=[0, 0, 0, 0, 1], alpha1=[-1, -1, -1, 1, -2.0]),
                       index=list("abcde"))
    v = l4.q2_verdict(tab)
    assert list(v.verdict) == ["มีหลักฐาน α", "บางส่วน (ไม่ซ้ำในช่วง test)", "บางส่วน (ฐานเดียว)", "ไม่พบ", "มีหลักฐาน α"]
    assert v.div_note["e"] == "อาจเป็นผลปันผล" and v.div_note["a"] == ""
    assert l4.q2_verdict(tab, p_boot_gt=True).label["a"] == "แยกจากโชคไม่ได้" and l4.q2_verdict(tab, p_boot_gt=True).label["d"] == ""


def test_s9_66_ref3a(real):
    r = l4.ref3a_factors(real)
    assert list(r.columns) == ["MKT", "BOND", "GOLD", "FX"] and r.index.max() < pd.Timestamp("2026-01-01")
    assert np.abs(r.to_numpy() - ex.line3(real, "3a").to_numpy()).max() <= 1e-15


def test_s9_67_kish_top10():
    N = 30
    X = pd.DataFrame(dict(const=1.0, a=np.arange(N, dtype=float)))
    se = np.r_[np.full(10, 0.5), np.full(20, 1.0)]
    r = l4.xsec_wls(np.arange(N) * 0.1 + np.sin(np.arange(N)), se, X, np.arange(N), policy=np.array(["E"] * 20 + ["F"] * 10))
    w = 1 / se ** 2
    assert abs(r["kish_n"] - w.sum() ** 2 / (w ** 2).sum()) <= 1e-12 and abs(r["top10_share"] - np.sort(w)[::-1][:10].sum() / w.sum()) <= 1e-12
    assert abs(r["policy_share"]["F"] - w[20:].sum() / w.sum()) <= 1e-12


def test_s9_69_mixed_provider_and_sub_fit():
    f, Y = _sim(N=6)
    e = pd.Series(np.random.default_rng(1).normal(0, 0.02, 260), index=IDX)
    pf = {"s0": e}
    mp = l4.MixedProvider(f, pf)
    assert mp.design("s0").shape[1] == 2 * (f.shape[1] + 1) and mp.design("s1").shape[1] == 2 * f.shape[1]
    m = np.ones(260, bool)
    fit, ro, _ = l3.fit_perfund(Y, f, pf, m, None, list(Y.columns), 52)
    sf = l4.sub_fit(fit, np.array([1, 3]))
    assert sf.codes == ["s1", "s3"] and np.array_equal(sf.alpha, fit.alpha[[1, 3]])
    D = mp.design("s0")
    ok = np.isfinite(D).all(1)
    r = rg.ols_hac(Y["s0"].to_numpy()[ok], np.column_stack([np.ones(ok.sum()), D[ok]]), 4)
    assert abs(r["coef"][0] - fit.alpha[0]) <= 1e-12


def test_s9_69b_resid_panel_mixed_fit():
    f, Y = _sim(N=6)
    e = pd.Series(np.random.default_rng(1).normal(0, 0.02, 260), index=IDX)
    pf = {"s0": e, "s2": e * 2}
    mp = l4.MixedProvider(f, pf)
    fit, ro, _ = l3.fit_perfund(Y, f, pf, MTR, MTE, list(Y.columns), 52)
    u = l4.resid_panel(Y, mp, fit, list(Y.columns))
    for j, c in enumerate(Y.columns):
        D = mp.design(c)
        ok = MTR & np.isfinite(D).all(1)
        r = rg.ols_hac(Y[c].to_numpy()[ok], np.column_stack([np.ones(ok.sum()), D[ok]]), 4)
        assert np.nanmax(np.abs(u[c].to_numpy()[ok] - r["resid"])) <= 1e-10, c
