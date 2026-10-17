"""test 1–27 ของ L2 (S004 test 1–14 + S005 test 15–27)"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import statsmodels.api as sm
from scipy import stats
from statsmodels.stats.multitest import multipletests

import external
import forms
import io_l1
import l2
import regress as rg
import samples
import tests_stat as ts
from samples import window_mask

IDX = pd.date_range("2021-01-08", periods=260, freq="W-FRI")
MTR, MTE = window_mask(IDX, "train"), window_mask(IDX, "test")
S003 = io_l1.TEAM / "runs" / "S003"


def _sim(N=30, K=3, J=4, seed=0):
    rng = np.random.default_rng(seed)
    base = pd.DataFrame(rng.normal(0, 0.02, (260, K)), index=IDX, columns=[f"f{i}" for i in range(K)])
    I = pd.DataFrame(rng.normal(0, 0.02, (260, J)), index=IDX, columns=[f"I{i}" for i in range(J)])
    B = rng.normal(size=(K, N))
    R = pd.DataFrame(base.to_numpy() @ B + 0.5 * I.to_numpy()[:, [0]] + rng.normal(0, 0.02, (260, N)), index=IDX,
                     columns=[f"F{i:02d}" for i in range(N)])
    return R, base, I


@pytest.fixture(scope="module")
def real():
    R = io_l1.load_returns("W")
    F = io_l1.load_factors("W")
    U = io_l1.load_universe().set_index("FundCode")
    S = l2.fund_sets(R, U, io_l1.load_dup_pairs())
    return dict(R=R, F=F, U=U, S=S)


def test_01_reproduce_l1(real):
    R, S = real["R"], real["S"]
    l1 = forms.build_line1(R, S["bal"], S["base"], kstar=4)
    fac = pd.read_parquet(S003 / "factors_S003_weekly.parquet")
    for nm in ("1a", "1b", "1c"):
        mine = l1["forms"][nm].plain
        ref = fac[[f"{nm}__PC{i}" for i in range(1, 5)]]
        assert np.nanmax(np.abs(mine.to_numpy() - ref.to_numpy())) <= 1e-12
    fl = pd.read_csv(S003 / "fund_level.csv")
    fl = fl[(fl.form == "1a") & fl.in_EVAL].set_index("FundCode")
    ev = S["EVAL"]
    f = l1["forms"]["1a"]
    fit = rg.fit_funds(R, f.provider, MTR, 52, funds=ev)
    ro = rg.oos_r2_funds(R, f.provider, fit, MTE)
    assert np.allclose(fit.adj_r2, fl.loc[ev, "adj_r2"].to_numpy(), atol=1e-10)
    assert np.allclose(ro, fl.loc[ev, "r2_oos"].to_numpy(), atol=1e-10)


def test_02_augmented_matches_manual():
    R, base, I = _sim()
    ex = I[["I1", "I2"]]
    fit = rg.fit_funds(R, l2.AugmentedFactors(base, extra=ex), MTR, 52)
    j, code = 3, R.columns[3]
    X = np.column_stack([np.ones(len(IDX)), rg.dimson_design(pd.concat([base, ex], axis=1)).to_numpy()])
    ok = MTR & np.isfinite(X).all(1)
    b = np.linalg.lstsq(X[ok], R[code].to_numpy()[ok], rcond=None)[0]
    assert np.allclose(fit.coef[j], b, atol=1e-10)
    pf = {c: I["I0"] * (1 + i % 3) for i, c in enumerate(R.columns)}
    fit2 = rg.fit_funds(R, l2.AugmentedFactors(base, per_fund=pf), MTR, 52)
    Xp = np.column_stack([np.ones(260), rg.dimson_design(pd.concat([base, pf[code].rename("x")], axis=1)).to_numpy()])
    # layout [cur(all)|lag(all)] ตรงกับ dimson_design ของ [base, x]
    ok = MTR & np.isfinite(Xp).all(1)
    b2 = np.linalg.lstsq(Xp[ok], R[code].to_numpy()[ok], rcond=None)[0]
    assert np.allclose(fit2.coef[j], b2, atol=1e-10)
    assert not np.allclose(fit2.coef[0][1:], fit2.coef[1][1:])


def test_03_rotation_invariance():
    R, base, _ = _sim(K=4)
    rng = np.random.default_rng(5)
    Bm = rng.normal(size=(4, 4))
    rot = pd.DataFrame(base.to_numpy() @ Bm, index=IDX, columns=list("abcd"))
    f0 = rg.fit_funds(R, base, MTR, 52)
    f1 = rg.fit_funds(R, rot, MTR, 52)
    for a in ("alpha", "r2", "adj_r2", "bic"):
        assert np.allclose(getattr(f0, a), getattr(f1, a), atol=1e-8)
    assert np.allclose(np.nan_to_num(f0.resid), np.nan_to_num(f1.resid), atol=1e-8)
    assert np.allclose(rg.oos_r2_funds(R, base, f0, MTE), rg.oos_r2_funds(R, rot, f1, MTE), atol=1e-8)


def test_04_target_rotation_sim():
    rng = np.random.default_rng(1)
    Ia, Ib, n1 = rng.normal(size=(3, 260))
    I = pd.DataFrame({"a": Ia, "b": Ib, "c": rng.normal(size=260), "d": rng.normal(size=260)}, index=IDX)
    A = rng.normal(size=(3, 3))
    f = pd.DataFrame(np.column_stack([Ia, Ib, n1]) @ A + 0.01 * rng.normal(size=(260, 3)), index=IDX, columns=["p1", "p2", "p3"])
    r = l2.target_rotation(f, I, MTR, 3)
    assert set(r["targets"]) == {"a", "b"} and len(r["targets"]) == 2
    for m, c in enumerate(r["targets"]):
        d = pd.concat([r["f_rot"].iloc[:, m], I[c]], axis=1)[MTR]
        assert abs(d.corr().iloc[0, 1]) > 0.99
    assert r["names"][2].startswith("R-ไม่มีเป้า")
    r2 = l2.target_rotation(f, I, MTR, 3)
    assert np.array_equal(r["B"], r2["B"])


def test_05_wald_subset_vs_statsmodels():
    rng = np.random.default_rng(2)
    X = np.column_stack([np.ones(155), rng.normal(size=(155, 5))])
    y = X @ rng.normal(size=6) + rng.normal(size=155)
    r = rg.ols_hac(y, X, 4)
    W, df, p = l2.wald_subset(r["coef"], r["V"], [2, 3])
    m = sm.OLS(y, X).fit(cov_type="HAC", cov_kwds={"maxlags": 4, "use_correction": False})
    w = m.wald_test(np.eye(6)[[2, 3]], scalar=True)
    assert abs(W - float(w.statistic)) < 1e-8 and abs(p - float(w.pvalue)) < 1e-8 and df == 2


def test_06_in_span(real):
    F = real["F"]
    I, _ = l2.index_set(F)
    b3 = external.line3(F, "3b")
    assert l2.in_span(b3, I["MSCI_ACWI"]) and l2.in_span(b3, I["MSCI_USA"]) and not l2.in_span(b3, I["MSCI_EM"])
    b4 = external.line3(F, "3a").copy()
    b4["RPC1"] = np.random.default_rng(0).normal(size=len(b4))
    assert l2.in_span(b4, I["MSCI_ACWI"])


def test_07_incremental_scan_equals_diff():
    R, base, I = _sim(N=6)
    funds = list(R.columns)
    sc = l2.incremental_scan(R, base, I, MTR, MTE, funds)
    fb = rg.fit_funds(R, base, MTR, 52)
    rb = rg.oos_r2_funds(R, base, fb, MTE)
    for c in ("I0", "I2"):
        pf = {k: I[c] for k in funds}
        prov = l2.AugmentedFactors(base, per_fund=pf)
        fa = rg.fit_funds(R, prov, MTR, 52)
        ra = rg.oos_r2_funds(R, prov, fa, MTE)
        s = sc[sc["index"] == c].set_index("FundCode").loc[funds]
        assert np.allclose(s.d_adj_r2, fa.adj_r2 - fb.adj_r2, atol=1e-12)
        assert np.allclose(s.d_bic, fa.bic - fb.bic, atol=1e-9)
        assert np.allclose(s.d_r2_oos, ra - rb, atol=1e-12)


def test_08_reverse_span_lead_and_rows():
    rng = np.random.default_rng(3)
    f = pd.DataFrame(rng.normal(size=(260, 2)), index=IDX, columns=["a", "b"])
    nxt = f.shift(-1)
    I = pd.DataFrame({"x": 1 + 0.5 * f["a"] + 2 * nxt["b"]}, index=IDX)
    r = l2.reverse_span(I, f, MTR, MTE, lead=1)
    assert r.loc["x", "n_tr"] == 155 and r.loc["x", "n_te"] == 103 and r.loc["x", "r2"] > 1 - 1e-10
    assert r.loc["x", "r2_oos"] > 1 - 1e-10
    r0 = l2.reverse_span(I, f, MTR, MTE, lead=0)
    assert r0.loc["x", "n_tr"] == 156 and r0.loc["x", "r2"] < 0.99
    assert IDX.max() < pd.Timestamp("2026-01-01")


def test_09_index_clusters():
    rng = np.random.default_rng(4)
    cols = {}
    for g in range(3):
        base = rng.normal(size=260)
        for i in range(3):
            cols[f"g{g}_{i}"] = base + 0.3 * rng.normal(size=260)
    d = l2.index_clusters(pd.DataFrame(cols, index=IDX), MTR, cut=0.10)
    assert d.cluster.nunique() == 3
    assert all(d[d["index"].str.startswith(f"g{g}")].cluster.nunique() == 1 for g in range(3))


def test_10_by():
    p = np.random.default_rng(6).uniform(size=200) ** 3
    rej, adj = l2.by(p, 0.10)
    r2, a2, _, _ = multipletests(p, alpha=0.10, method="fdr_by")
    assert np.array_equal(rej, r2) and np.allclose(adj, a2)


def test_11_no_lookahead():
    R, base, I = _sim(N=12)
    funds = list(R.columns)
    R2, I2, b2 = R.copy(), I.copy(), base.copy()
    rng = np.random.default_rng(9)
    R2.loc[MTE] = rng.normal(size=R2.loc[MTE].shape)
    I2.loc[MTE] = rng.normal(size=I2.loc[MTE].shape)
    b2.loc[MTE] = rng.normal(size=b2.loc[MTE].shape)
    assert l2.primary_index(R, I, MTR, funds).equals(l2.primary_index(R2, I2, MTR, funds))
    assert np.array_equal(l2.target_rotation(base, I, MTR, 3, min_score=0.0)["B"], l2.target_rotation(b2, I2, MTR, 3, min_score=0.0)["B"])
    assert l2.index_clusters(I, MTR).equals(l2.index_clusters(I2, MTR))
    assert l2.fund_clusters(R, MTR, funds).equals(l2.fund_clusters(R2, MTR, funds))
    f1 = rg.fit_funds(R, base, MTR, 52)
    f2 = rg.fit_funds(R2, b2, MTR, 52)
    assert np.array_equal(f1.coef, f2.coef)
    rv1, rv2 = l2.reverse_span(I, base, MTR, MTE), l2.reverse_span(I2, b2, MTR, MTE)
    assert np.allclose(rv1.r2, rv2.r2) and np.allclose(rv1.adj_r2, rv2.adj_r2)
    c1, c2 = l2.canon_oos(base, I, MTR, MTE), l2.canon_oos(b2, I2, MTR, MTE)
    assert np.allclose(c1.rho_train, c2.rho_train)
    p1 = l2.placebo_scan(R, base, I, MTR, funds[:3])
    p2 = l2.placebo_scan(R2, b2, I2, MTR, funds[:3])
    assert p1.equals(p2)


def test_12_manifest_and_s003_files():
    io_l1.verify_manifest()
    assert io_l1.sha256_file(S003 / "factors_S003_weekly.parquet") == l2.S003_FAC_SHA
    assert io_l1.sha256_file(S003 / "fund_level.csv") == "36b41161d6a13c1184a4052d9e799f660f431c2694dc57fafd747f8e695bf8cf"
    rc = io_l1.TEAM / "runs" / "S005" / "repro_check.json"
    if rc.exists():
        assert json.load(open(rc))["all_identical"]


def test_13_no_forbidden_columns(real):
    I, b = l2.index_set(real["F"])
    assert len(I.columns) == 39 and I.isna().sum().sum() == 0
    for c in I.columns:
        assert not any(p in c for p in io_l1.FORBIDDEN_PATTERNS) and c not in ("Gold", "USDTHB")
    assert len(b["M28"]) == 28 and len(b["I_inv"]) == 34


def _h0_data(N=100, T=105, K=4, seed=0):
    rng = np.random.default_rng(seed)
    f = rng.normal(0, 0.02, (T, K))
    g = rng.normal(size=(T, N // 5))
    w = np.sqrt(0.5) * np.repeat(g, 5, axis=1) + np.sqrt(0.5) * rng.normal(size=(T, N))
    e = np.zeros((T, N))
    for t in range(T):
        e[t] = (0.2 * e[t - 1] if t else 0) + w[t] * 0.01
    B = rng.normal(size=(K, N))
    idx = pd.date_range("2021-01-08", periods=T, freq="W-FRI")
    F = pd.DataFrame(f, index=idx, columns=list("abcd")[:K])
    R = pd.DataFrame(f @ B + e, index=idx, columns=[f"F{i:03d}" for i in range(N)])
    mask = np.ones(T, bool)
    mask[0] = False
    return R, F, mask


def test_14_py_null_bootstrap():
    R, F, mask = _h0_data(N=40, T=105, seed=1)
    prov = rg.CommonFactors(F)
    funds = list(R.columns)
    a = ts.py_null_bootstrap(R, prov, funds, mask, B=999)
    b = ts.py_null_bootstrap(R, prov, funds, mask, B=999)
    assert a == b  # (ก) deterministic
    assert abs(a["mean_alpha_star"]) < 1e-4  # (ข)
    ix = ts.block_indices(104, 5, 4, np.random.default_rng(1))
    assert ix.shape == (5, 104) and (np.diff(ix[:, :4], axis=1) == 1).all()
    assert ts.p_boot_value(2.0, [1.0, 2.0, 3.0, 0.5]) == (1 + 2) / 5  # (ง)
    rej = 0
    nrep = 200
    for s in range(nrep):  # (ค) size ภายใต้ H0
        R, F, mask = _h0_data(N=100, T=105, seed=100 + s)
        r = ts.py_null_bootstrap(R, rg.CommonFactors(F), list(R.columns), mask, B=199)
        rej += r["p_boot"] < 0.05
    assert 0.02 <= rej / nrep <= 0.09, rej / nrep


def test_15_stacking_and_1c_k(real):
    R, S = real["R"], real["S"]
    l4 = forms.build_line1(R, S["bal"], S["base"], kstar=4)
    l3 = forms.build_line1(R, S["bal"], S["base"], kstar=3)
    l5 = forms.build_line1(R, S["bal"], S["base"], kstar=5)
    a4, a3, a5 = (x["forms"]["1a"].plain.to_numpy() for x in (l4, l3, l5))
    # ซ้อนคอลัมน์แน่นอนเฉพาะแถวที่กองใน Λ ครบทุกตัว (LS บนเซตย่อยของ Λ ต่างกันเมื่อมีกองขาด → 80 แถว test ต่างกัน · ไม่ใช่เรื่องเครื่องหมาย)
    full = R[S["bal"]].notna().all(axis=1).to_numpy()
    assert np.nanmax(np.abs(a3 - a4[:, :3])[full]) <= 1e-12 and np.nanmax(np.abs(a4 - a5[:, :4])[full]) <= 1e-12
    assert np.all(np.sign(a3[full].sum(0)) == np.sign(a4[full][:, :3].sum(0)))
    assert (np.abs(a3 - a4[:, :3]).max(1) > 1e-12).sum() == (~full & (np.abs(a3 - a4[:, :3]).max(1) > 1e-12)).sum()
    l3b = forms.build_line1(R, S["bal"], S["base"], kstar=3)
    assert np.array_equal(l3["forms"]["1c"].plain.to_numpy(), l3b["forms"]["1c"].plain.to_numpy(), equal_nan=True)
    assert l3["parts"]["em_conv"] and l5["parts"]["em_conv"]


def test_16_delta_same_k():
    R, base, I = _sim(N=8, K=3)
    fa = rg.fit_funds(R, l2.AugmentedFactors(base, extra=I[["I0"]]), MTR, 52)
    fb = rg.fit_funds(R, base, MTR, 52)
    ra, rb = rg.oos_r2_funds(R, l2.AugmentedFactors(base, extra=I[["I0"]]), fa, MTE), rg.oos_r2_funds(R, base, fb, MTE)
    d = l2.deltas(fa, ra, fb, rb)
    assert np.allclose(d["d_adj_r2"], fa.adj_r2 - fb.adj_r2, atol=1e-12) and np.allclose(d["d_bic"], fa.bic - fb.bic, atol=1e-12)
    with pytest.raises(AssertionError):
        l2.deltas(fa, ra, rg.fit_funds(R, base, MTR, 52, funds=list(R.columns)[::-1]), rb)


def test_17_placebo():
    R, base, I = _sim(N=10)
    sh = l2.circular_shift(I, MTR, 26)
    assert np.isnan(sh.loc[~MTR]).all().all()
    for c in I.columns:
        assert np.allclose(np.sort(sh.loc[MTR, c]), np.sort(I.loc[MTR, c]))
    funds = list(R.columns)[:5]
    real_ = l2.incremental_scan(R, base, I, MTR, MTE, funds).sort_values(["FundCode", "index"]).reset_index(drop=True)
    p0 = l2.placebo_scan(R, base, I, MTR, funds, shifts=(0,)).sort_values(["FundCode", "index"]).reset_index(drop=True)
    assert np.allclose(real_.p, p0.p, atol=1e-12) and np.allclose(real_.p_adj, p0.p_adj, atol=1e-12)
    rng = np.random.default_rng(21)
    N, J = 50, 28
    Rn = pd.DataFrame(rng.normal(0, 0.02, (260, N)), index=IDX, columns=[f"F{i:02d}" for i in range(N)])
    bn = pd.DataFrame(rng.normal(0, 0.02, (260, 4)), index=IDX, columns=list("abcd"))
    In = pd.DataFrame(rng.normal(0, 0.02, (260, J)), index=IDX, columns=[f"I{i:02d}" for i in range(J)])
    pn = l2.placebo_scan(Rn, bn, In, MTR, list(Rn.columns), shifts=(26,))
    assert 0.02 <= (pn.p_adj < 0.05).mean() <= 0.09


def test_18_wald_p_dfadj():
    W, n, p = 5.99, 100, 11
    exp = stats.f.sf((5.99 / 2) * (89 / 100), 2, 89)
    assert abs(l2.wald_p_dfadj(W, 2, n, p) - exp) < 1e-14
    assert l2.wald_p_dfadj(W, 2, n, p) >= stats.chi2.sf(W, 2)
    assert abs(l2.wald_p_dfadj(W, 2, 10 ** 7, p) - stats.chi2.sf(W, 2)) < 1e-5


def test_19_placebo_rule():
    mk = lambda a, b: pd.DataFrame(dict(frac_p05=a, frac_padj05=b))
    assert l2.placebo_rule(mk([0.05, 0.07, 0.04, 0.06], [0.05] * 4))["step"] == 1
    assert l2.placebo_rule(mk([0.05, 0.10, 0.04, 0.06], [0.05, 0.07, 0.04, 0.06]))["step"] == 2
    assert l2.placebo_rule(mk([0.05, 0.10, 0.04, 0.06], [0.05, 0.09, 0.04, 0.06]))["step"] == 3
    assert l2.placebo_rule(mk([0.01, 0.01, 0.01, 0.081], [0.0] * 4))["step"] == 2


def test_20_fund_clusters():
    rng = np.random.default_rng(8)
    z = rng.normal(size=260)
    a = z
    b = 0.96 * z + np.sqrt(1 - 0.96 ** 2) * rng.normal(size=260)
    c = 0.96 * b + np.sqrt(1 - 0.96 ** 2) * rng.normal(size=260)
    R = pd.DataFrame({"A": a, "B": b, "C": c, "D": rng.normal(size=260)}, index=IDX)
    d = l2.fund_clusters(R, MTR, list(R.columns), thr=0.93)
    g = d.set_index("FundCode").group_id
    assert g["A"] == g["B"] == g["C"] != g["D"] and d.group_size.max() == 3
    R2 = R.copy()
    R2.loc[R2.index[:130], "B"] = np.nan  # overlap < 52 (train 156 แถว · เหลือ 26)
    g2 = l2.fund_clusters(R2, MTR, list(R.columns), thr=0.93).set_index("FundCode").group_id
    assert g2["A"] != g2["B"] and g2["B"] != g2["C"]
    assert d.equals(l2.fund_clusters(R, MTR, list(R.columns), thr=0.93))


def test_21_count_groups():
    gm = {"a": 1, "b": 1, "c": 2, "d": 3}
    assert l2.count_groups(["a", "b", "c"], gm) == 2 and l2.count_groups([], gm) == 0


def test_22_forward_span_family():
    rng = np.random.default_rng(12)
    I = pd.DataFrame(rng.normal(size=(260, 8)), index=IDX, columns=[f"I{i}" for i in range(8)])
    f = pd.DataFrame({"mk": I["I0"], "x": rng.normal(size=260) + I["I1"], "y": rng.normal(size=260)}, index=IDX)
    blocks = {"B1": I, "B2": pd.concat([I, pd.DataFrame(rng.normal(size=(260, 5)), index=IDX)], axis=1)}
    blocks["B2"].columns = [str(c) for c in blocks["B2"].columns]
    t = l2.forward_span(f, blocks, MTR, MTE)
    fam = t[t.bh_family]
    assert len(fam) == 2 and set(fam.block) == {"B1"} and t[(t.factor == "mk") & (t.block == "B1")].defn.iloc[0]
    row = t[(t.factor == "y") & (t.block == "B1")].iloc[0]
    assert abs(row.adj_r2 - (1 - (1 - row.r2) * (row.n - 1) / (row.n - row.p))) < 1e-12


def test_23_canon_oos():
    rng = np.random.default_rng(13)
    I = pd.DataFrame(rng.normal(size=(260, 6)), index=IDX)
    f = pd.DataFrame(I.to_numpy() @ rng.normal(size=(6, 3)) + 0.5, index=IDX)
    c = l2.canon_oos(f, I, MTR, MTE)
    assert np.allclose(c.rho_train, 1, atol=1e-8) and np.allclose(c.rho_oos, 1, atol=1e-8)
    import scorecard as sc
    f2 = pd.DataFrame(rng.normal(size=(260, 3)) + I.to_numpy()[:, :3], index=IDX)
    c2 = l2.canon_oos(f2, I, MTR, MTE)
    cc = sc.canonical_corr(f2.loc[MTR].to_numpy(), I.loc[MTR].to_numpy())
    assert np.allclose(c2.rho_train, cc[:3], atol=1e-10)


def test_24_reverse_span_extra():
    rng = np.random.default_rng(14)
    f = pd.DataFrame(rng.normal(size=(260, 2)), index=IDX, columns=["a", "b"])
    I = pd.DataFrame(rng.normal(size=(260, 3)), index=IDX, columns=list("xyz"))
    f2 = f.copy()
    f2.loc[MTE] = 99.0
    a, b = l2.reverse_span(I, f, MTR, MTE), l2.reverse_span(I, f2, MTR, MTE)
    assert np.allclose(a.r2, b.r2) and np.allclose(a.adj_r2, b.adj_r2)  # ไม่ใช้ f ของ test ใน train
    assert l2.reverse_span(I, f, MTR, MTE, lead=0).n_tr.iloc[0] == 156


def test_25_near_dup():
    rng = np.random.default_rng(15)
    base = pd.DataFrame(rng.normal(size=(260, 3)), index=IDX, columns=list("abc"))
    near = base @ np.array([1.0, -2.0, 0.5]) + 1e-6 * rng.normal(size=260)
    assert l2.near_dup_r2(base, near.rename("n"), MTR) >= 0.99
    assert l2.near_dup_r2(base, pd.Series(rng.normal(size=260), index=IDX, name="i"), MTR) < 0.5


def test_26_common_primary():
    d = pd.DataFrame(dict(form=["a", "a", "b", "b"], FundCode=["x", "y", "x", "y"], rank_used=[1, 1, 1, 2]))
    s = l2.common_primary(d)
    assert s["x"] and not s["y"]


def test_27_pinned_files():
    assert io_l1.sha256_file(S003 / "grs_ports.csv") == "d55011094898acdf6e0419c90a3b2713479451380cacc0bf950559c43b98ba19"
    assert io_l1.sha256_file(S003 / "regions.csv") == "2fa3ce691c9dd66ef523e1baca228a635369d2971857797a05c105c1306e6866"
    assert io_l1.sha256_file(io_l1.TEAM / "specs" / "S004_L2_factor_x_msci.md") == "25b929d866f714246d02d7a1fa6fbea6bc341a13c63e3c660438174b5d49d20e"


def test_28_rolling_betas():
    R, base, _ = _sim(N=6)
    full = np.ones(260, bool)
    full[0] = False
    bw, bf, starts = l2.rolling_betas(R, base, list(R.columns), full)
    assert starts[0] == 0 and starts[-1] == 156 and len(starts) == 40 and bw.shape == (40, 6, 3)
    s = starts[5]
    mk = np.zeros(260, bool)
    mk[s:s + 104] = True
    mk &= full
    ft = rg.fit_funds(R, base, mk, 78, funds=list(R.columns))
    assert np.array_equal(bw[5], ft.beta)
    assert np.allclose(bf, rg.fit_funds(R, base, full, 100, funds=list(R.columns)).beta)
    import scorecard as sc
    med, mn = sc.stability_rolling(bw, bf)
    assert (med > 0.5).all() and (mn <= med).all()
