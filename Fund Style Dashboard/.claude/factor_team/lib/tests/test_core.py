"""test 1–5, 8, 11, 12, 13"""
import numpy as np
import pandas as pd
import pytest
import statsmodels.api as sm
from statsmodels.stats.multitest import multipletests

import io_l1
import nfactors
import pca
import regress
import samples
import tests_stat as ts


def test_01_ols_hac_vs_statsmodels():
    rng = np.random.default_rng(1)
    T = 155
    X = np.column_stack([np.ones(T), rng.normal(size=(T, 5))])
    e = np.zeros(T)
    for t in range(1, T):
        e[t] = 0.4 * e[t - 1] + rng.normal()
    y = X @ rng.normal(size=6) + e
    r = regress.ols_hac(y, X, 4)
    m = sm.OLS(y, X).fit(cov_type="HAC", cov_kwds={"maxlags": 4, "use_correction": False})
    assert np.allclose(r["coef"], m.params, atol=1e-8)
    assert np.allclose(r["se"], m.bse, atol=1e-8)
    assert np.allclose(r["V"], m.cov_params(), atol=1e-8)
    assert abs(r["r2"] - m.rsquared) < 1e-10 and abs(r["adj_r2"] - m.rsquared_adj) < 1e-10


def test_02_dimson_design_lags():
    idx = pd.date_range("2021-01-08", periods=260, freq="W-FRI")
    F = pd.DataFrame({"a": np.arange(260.0), "b": np.arange(260.0) * 2}, index=idx)
    D = regress.dimson_design(F)
    assert list(D.columns) == ["a", "b", "a_l1", "b_l1"]
    assert np.isnan(D.iloc[0, 2]) and D["a_l1"].iloc[5] == 4.0  # lag ถูกตำแหน่ง · แถวแรก train ตก
    mtr = samples.window_mask(idx, "train")
    mte = samples.window_mask(idx, "test")
    first_test = np.where(mte)[0][0]
    assert D["a_l1"].iloc[first_test] == F["a"].iloc[first_test - 1]  # แถวแรก test ใช้ lag จาก train
    assert idx[first_test] == pd.Timestamp("2024-01-05") and mtr[first_test - 1]
    # train_c: แถวแรกใช้ lag ของ 2022-01-07 (MOM)
    F2 = F.copy()
    F2.loc[idx < "2022-01-07", "a"] = np.nan
    D2 = regress.dimson_design(F2)
    mc = samples.window_mask(idx, "train_c")
    r0 = np.where(mc)[0][0]
    assert idx[r0] == pd.Timestamp("2022-01-14") and np.isfinite(D2["a_l1"].iloc[r0]) and D2["a_l1"].iloc[r0] == F2["a"].iloc[r0 - 1]
    assert mc.sum() == 103


def _sim_factors(N=134, T=156, k=3, seed=3):
    rng = np.random.default_rng(seed)
    f = rng.normal(size=(T, k))
    B = rng.normal(size=(N, k))
    return f @ B.T + rng.normal(size=(T, N)), f


def test_03_nfactors():
    X, f = _sim_factors()
    Z = (X - X.mean(0)) / X.std(0)
    N, T = Z.shape[1], Z.shape[0]
    eig = nfactors.corr_eig(Z)
    assert nfactors.bai_ng_ic(eig, N, T, 10, "p2") == 3
    assert nfactors.ahn_horenstein(eig, 10)[0] == 3
    assert nfactors.parallel_analysis(Z, 200, 0.95, 20261015) == 3
    ed = nfactors.onatski_ed(eig, 10)
    assert ed == 3 and nfactors.onatski_ed(eig, 10) == ed
    assert nfactors.combine_k([2, 3, 4, 6]) == 3
    assert nfactors.combine_k([None, 5, 1, 1]) == 1
    assert nfactors.combine_k([0, 0, 0, 0]) == 1


def test_04_em_pca():
    X, f = _sim_factors(100, 156, 3, 5)
    rng = np.random.default_rng(6)
    Xm = X.copy()
    Xm[rng.random(X.shape) < 0.30] = np.nan
    Lam, mu, sd, it, conv = pca.em_pca(Xm, 3)
    assert conv
    fe = pca.factor_returns(X, Lam, sd)
    from scorecard import canonical_corr
    cc = canonical_corr(fe, f)
    assert cc.min() > 0.95
    Lam2, *_ = pca.em_pca(Xm, 3)
    assert np.array_equal(Lam, Lam2)


def test_05_factor_returns():
    rng = np.random.default_rng(7)
    X = rng.normal(0.003, 0.01, size=(120, 30))
    Lam, mu, sd, eig = pca.pca_fit(X, 2, "corr")
    f = pca.factor_returns(X, Lam, sd)
    assert np.allclose(f, (X / sd) @ Lam)  # ไม่หัก μ
    assert abs(f.mean(0)).max() > 1e-3  # ค่าเฉลี่ย ≠ 0
    # ตัดกองครึ่งหนึ่ง จาก model ไม่มี noise → factor เดิม
    F0 = rng.normal(0.002, 0.01, size=(100, 2))
    B = rng.normal(size=(40, 2))
    Xn = F0 @ B.T
    sdn = Xn.std(0)
    Lam_n, *_ = pca.pca_fit(Xn, 2, "corr")
    full = pca.factor_returns(Xn, Lam_n, sdn)
    Xh = Xn.copy()
    Xh[:, 20:] = np.nan
    half = pca.factor_returns(Xh, Lam_n, sdn)
    # factor ครึ่งชุด = แปลงเชิงเส้นคงที่ของ factor เต็ม (span เดียวกัน) → R² ของการถดถอย = 1
    A = np.column_stack([np.ones(100), full])
    res = half - A @ np.linalg.lstsq(A, half, rcond=None)[0]
    assert np.abs(res).max() < 1e-8
    # min_frac: มีค่าน้อยกว่า 50% → NaN
    Xs = Xn.copy()
    Xs[3, :25] = np.nan
    assert np.isnan(pca.factor_returns(Xs, Lam_n, sdn)[3]).all()


def test_08_predict_oos_no_refit():
    rng = np.random.default_rng(8)
    X = rng.normal(size=(100, 3))
    y = 1 + X @ [1, 2, 3] + rng.normal(size=100)
    r = regress.ols_hac(y, np.column_stack([np.ones(100), X]), 4)
    Xt = rng.normal(size=(40, 3))
    yh = regress.predict_oos(r["coef"], Xt)
    assert np.array_equal(yh, r["coef"][0] + Xt @ r["coef"][1:])
    yt = 1 + Xt @ [1, 2, 3] + rng.normal(size=40)
    assert regress.r2_oos(yt, yh) > 0.8
    assert regress.r2_oos(yt, np.full(40, yt.mean() + 5)) < 0  # ติดลบได้


def test_11_bh_vs_statsmodels():
    rng = np.random.default_rng(9)
    p = np.concatenate([rng.uniform(0, 0.01, 20), rng.uniform(size=80)])
    rej, adj = ts.bh(p, 0.10)
    r2, a2, *_ = multipletests(p, alpha=0.10, method="fdr_bh")
    assert np.array_equal(rej, r2) and np.allclose(adj, a2)
    # ชุดที่รู้คำตอบ
    p = np.array([0.001, 0.008, 0.039, 0.041, 0.042, 0.06, 0.074, 0.205, 0.212, 0.216])
    rej, _ = ts.bh(p, 0.05)
    assert rej.sum() == 2 and rej[:2].all()


def test_12_verify_manifest(tmp_path):
    f = tmp_path / "a.csv"
    f.write_bytes(b"hello,world\n1,2\n")
    man = tmp_path / "manifest.json"
    import json
    man.write_text(json.dumps({"inputs": [], "outputs": [{"file": "a.csv", "sha256": io_l1.sha256_file(f)}]}))
    assert "a.csv" in io_l1.verify_manifest(["a.csv"], root=tmp_path, manifest_path=man)
    f.write_bytes(b"hello,world\n1,3\n")  # แก้ 1 byte
    with pytest.raises(ValueError):
        io_l1.verify_manifest(["a.csv"], root=tmp_path, manifest_path=man)
    # ไฟล์จริงตรง manifest + spec
    assert len(io_l1.verify_manifest()) == 8
    h = io_l1.lib_hash()
    assert "io_l1.py" in h and len(h["io_l1.py"]) == 64


def test_13_no_forbidden_columns_or_dates():
    for fq in ("W", "M"):
        F = io_l1.load_factors(fq)
        assert not [c for c in F.columns if any(p in c for p in ("_late_", "_lvl", "_est_ret"))]
        assert F.index.max() < pd.Timestamp("2026-01-01")
        R = io_l1.load_returns(fq)
        assert R.index.max() < pd.Timestamp("2026-01-01")
    import external
    F = io_l1.load_factors("W")
    for v in ("3a", "3b", "3c"):
        assert not [c for c in external.line3(F, v).columns if any(p in c for p in ("_late", "_lvl", "_est"))]
    ref = external.reference_set(F)
    assert not [c for c in ref.columns if any(p in c for p in ("_late", "_lvl", "_est"))]
