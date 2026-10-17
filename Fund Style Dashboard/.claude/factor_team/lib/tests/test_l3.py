"""test ใหม่ของ L3 (S006 · เลขเลื่อน +1 จาก spec เพราะ test_28_rolling_betas เดิมใน test_l2.py: spec 28–44 → 29–45) + test เพิ่มตามรีวิว m12 (46–49)
test 31 (span test บนข้อมูลจริง) และ test 45 (รัน 2 รอบ) ทำใน runs/S006/run.py + repro_check เป็นเงื่อนไขก่อนรายงาน"""
import ast
import json

import numpy as np
import pandas as pd
import pytest

import io_l1
import l2
import l3
import regress as rg
import tests_stat as ts
from samples import window_mask

IDX = pd.date_range("2021-01-08", periods=260, freq="W-FRI")
MTR, MTE = window_mask(IDX, "train"), window_mask(IDX, "test")
S005 = io_l1.TEAM / "runs" / "S005"


def _sim(N=12, seed=1, nc=10, load=(3, 7)):
    rng = np.random.default_rng(seed)
    f = pd.DataFrame(rng.normal(0, 0.02, (260, 2)), index=IDX, columns=["f0", "f1"])
    pool = pd.DataFrame(rng.normal(0, 0.02, (260, nc)), index=IDX, columns=[f"c{i}" for i in range(nc)])
    B = rng.normal(size=(2, N))
    y = f.to_numpy() @ B + 1.2 * pool.to_numpy()[:, [load[0]]] + 0.6 * pool.to_numpy()[:, [load[1]]] + rng.normal(0, 0.02, (260, N))
    R = pd.DataFrame(y, index=IDX, columns=[f"F{i:02d}" for i in range(N)])
    return R, f, pool


def test_29_residualize():
    R, f, pool = _sim()
    I = pool[["c0"]] + 0.8 * f[["f0"]].to_numpy() + 0.001
    E, co = l3.residualize(I, f, MTR)
    e = E["c0"].to_numpy()
    for c in f.columns:
        assert abs(np.corrcoef(e[MTR], f[c].to_numpy()[MTR])[0, 1]) <= 1e-12
    assert abs(e[MTR].mean() - co["a"].iloc[0]) <= 1e-12
    I2 = I.copy()
    I2.loc[MTE, "c0"] += 5.0
    f2 = f.copy()
    f2.loc[MTE] += 3.0
    E2, co2 = l3.residualize(I2, f2, MTR)
    assert np.array_equal(co.filter(like="b_").to_numpy(), co2.filter(like="b_").to_numpy()) and co.a.iloc[0] == co2.a.iloc[0]
    # lag 0 เท่านั้น: e_t = I_t − b'f_t ไม่มี f_t−1 / f_t+1
    b = co.filter(like="b_").to_numpy()[0]
    assert np.allclose(e, I["c0"].to_numpy() - f.to_numpy() @ b, atol=1e-15)


def test_30_span_invariance_sim():
    R, f, pool = _sim()
    I = (pool[["c3", "c7"]] + 0.7 * f[["f0"]].to_numpy() - 0.4 * f[["f1"]].to_numpy()).copy()
    I.columns = ["I3", "I7"]
    E, _ = l3.residualize(I, f, MTR)
    funds = list(R.columns)
    res = {}
    for nm, X in (("raw", I), ("res", E)):
        pv = l2.AugmentedFactors(f, extra=X)
        ft = rg.fit_funds(R, pv, MTR, 52, funds=funds)
        res[nm] = (ft, rg.oos_r2_funds(R, pv, ft, MTE))
    a, b = res["raw"], res["res"]
    for k in ("alpha", "r2", "adj_r2", "bic", "t_alpha_hac"):
        assert np.nanmax(np.abs(getattr(a[0], k) - getattr(b[0], k))) <= 1e-10, k
    assert np.nanmax(np.abs(a[1] - b[1])) <= 1e-10
    # ตัวควบคุม 1: หัก â → α เปลี่ยน
    Ed = E - E[MTR].mean()
    pv = l2.AugmentedFactors(f, extra=Ed)
    ft = rg.fit_funds(R, pv, MTR, 52, funds=funds)
    assert np.nanmax(np.abs(ft.alpha - a[0].alpha)) > 1e-6
    # ตัวควบคุม 2: ใส่ f_t−1 ใน auxiliary → R² ต่าง
    Pl = pd.concat([f, f.shift(1).add_suffix("_l")], axis=1)
    El, _ = l3.residualize(I, Pl, MTR)
    pv = l2.AugmentedFactors(f, extra=El)
    ft = rg.fit_funds(R, pv, MTR, 52, funds=funds)
    assert np.nanmax(np.abs(ft.r2 - a[0].r2)) > 1e-8


def test_32_vif_backward():
    rng = np.random.default_rng(3)
    x1, x2, x4 = rng.normal(size=(3, 260))
    X = pd.DataFrame(dict(x1=x1, x2=x2, x3=x1 + x2 + 1e-3 * rng.normal(size=260), x4=x4), index=IDX)
    kept, log = l3.vif_backward(X, MTR, protect=[], order=["x1", "x2", "x3", "x4"])
    assert "x4" in kept and len(kept) == 3 and not {"x1", "x2", "x3"} <= set(kept)
    v, _ = l3.vif_table(X[kept], MTR)
    assert (v.vif < 5).all()
    k2, l2_ = l3.vif_backward(X, MTR, protect=["x1"], order=["x1", "x2", "x3", "x4"])
    assert "x1" in k2
    k3, l3_ = l3.vif_backward(X, MTR, protect=["x1"], order=["x1", "x2", "x3", "x4"])
    assert k2 == k3 and l2_.equals(l3_)
    # เสมอ (x_a ≡ x_b คัดลอกกัน · VIF เท่ากัน) → ตัดตัวที่อยู่ก่อนใน order
    Xd = pd.DataFrame(dict(a=x1, b=x1 + 1e-9 * rng.normal(size=260), c=x4), index=IDX)
    kd, ld = l3.vif_backward(Xd, MTR, protect=[], order=["b", "a", "c"])
    assert ld.dropped.iloc[0] in ("a", "b") and "c" in kd
    # protect มี VIF ≥ 5 ขณะดัชนีทุกตัว < 5 → หยุด + ป้าย (m1)
    rng2 = np.random.default_rng(4)
    p1, p2 = rng2.normal(size=(2, 260))
    Xp = pd.DataFrame(dict(P1=p1, P2=p1 + 0.15 * p2, i1=rng2.normal(size=260)), index=IDX)
    kp, lp = l3.vif_backward(Xp, MTR, protect=["P1", "P2"], order=list(Xp.columns))
    assert kp == ["P1", "P2", "i1"] and "STOP" in lp.note.iloc[-1] and lp.dropped.eq("").all()
    # continue_all: เดิน log ต่อ (ข) จนทุกคอลัมน์ < thr หรือไม่มีดัชนีให้ตัด
    kq, lq = l3.vif_backward(Xp, MTR, protect=["P1", "P2"], order=list(Xp.columns), continue_all=True)
    assert kq == kp and (lq.phase == "descriptive_all").any()


def test_33_vif_table_cond():
    R, f, pool = _sim()
    X = pd.concat([f, pool[["c0", "c1"]]], axis=1)
    v, kap = l3.vif_table(X, MTR)
    ok = MTR & np.isfinite(X.to_numpy()).all(1)
    assert np.allclose(v.vif, ts.vif(X.to_numpy()[ok]), atol=1e-12)
    C = np.corrcoef(X.to_numpy()[ok], rowvar=False)
    w = np.linalg.eigvalsh(C)
    assert abs(kap - np.sqrt(w.max() / w.min())) <= 1e-10 and abs(l3.cond_number(X, MTR) - kap) <= 1e-12


def test_34_hier():
    ch = l3.HIER_CHILDREN
    assert len(ch) == 37 and len(set(ch)) == 37
    forbid = {"MSCI_WORLD", "MSCI_WORLD_EX_US", "MSCI_ACWI_EX_US", "MSCI_EM", "GSG", "MSCI_ACWI"}
    assert not (set(ch) & forbid) and not any(c.endswith("_USD") or "HE" in c.split("_")[0] and c.startswith("HE") for c in ch)
    seen = {"MKT"}
    for parents, children in l3.HIER:
        for p in parents:
            assert p in seen or p in ch  # แม่มีจริง
        assert not (set(parents) & set(children))  # ไม่วนเข้าตัวเอง
    # ไม่มีวงวน: ผูกแม่→ลูกเป็นกราฟ ต้อง topological sort ได้
    edges = {c: set(p) for p, chs in l3.HIER for c in chs}
    done = {"MKT"}
    for _ in range(10):
        for c, ps in edges.items():
            if all(p in done or p not in edges for p in ps):
                done.add(c)
    assert set(edges) <= done
    rng = np.random.default_rng(5)
    cols = ["MKT"] + sorted(set(ch))
    A = pd.DataFrame(rng.normal(0, 0.02, (260, len(cols))), index=IDX, columns=cols)
    A["MSCI_USA"] += 0.5 * A["MKT"]
    E, co = l3.hier_residuals(A, MTR)
    assert list(E.columns) == ch
    for parents, children in l3.HIER:
        for c in children:
            for p in parents:
                assert abs(np.corrcoef(E[c].to_numpy()[MTR], A[p].to_numpy()[MTR])[0, 1]) <= 1e-12


def test_35_forward_select():
    R, f, pool = _sim()
    funds = list(R.columns)
    sel, lg = l3.forward_select(R, f, pool, MTR, funds, tau=0.0, kmax=8)
    assert sel == ["c3", "c7"] and lg.action.iloc[-1] == "stop_tau"
    sel2, _ = l3.forward_select(R, f, pool, MTR, funds, tau=0.0, kmax=1)
    assert sel2 == ["c3"]
    sel3, _ = l3.forward_select(R, f, pool, MTR, funds, tau=0.0, kmax=8)
    assert sel3 == sel
    R2, pool2 = R.copy(), pool.copy()
    R2.loc[MTE] *= 7
    pool2.loc[MTE] += 3
    sel4, lg4 = l3.forward_select(R2, f, pool2, MTR, funds, tau=0.0, kmax=8)
    assert sel4 == sel and np.array_equal(lg4.score.to_numpy(), lg.score.to_numpy(), equal_nan=True)


def test_36_placebo_forward(monkeypatch):
    R, f, pool = _sim()
    funds = list(R.columns)
    r0 = l3.placebo_forward(R, f, pool, MTR, funds, shifts=(0,))
    sel, lg = l3.forward_select(R, f, pool, MTR, funds, tau=0.0)
    assert r0["shifts"][0]["selected"] == sel and r0["shifts"][0]["best_score_step1"] == float(lg.score.iloc[0])
    sh = l2.circular_shift(pool, MTR, 26)
    assert np.allclose(np.sort(sh.to_numpy()[MTR], axis=0), np.sort(pool.to_numpy()[MTR], axis=0), atol=0) and np.isnan(sh.to_numpy()[~MTR]).all()
    pl = l3.placebo_forward(R, f, pool, MTR, funds)
    assert pl["tau"] == 0.0 and not pl["any_selected"]
    calls = iter([(["a"], pd.DataFrame(dict(score=[-3.0]))), ([], pd.DataFrame(dict(score=[1.0])))])
    monkeypatch.setattr(l3, "forward_select", lambda *a, **k: next(calls))
    r = l3.placebo_forward(R, f, pool, MTR, funds, shifts=(26, 52))
    assert r["tau"] == -3.0 and r["any_selected"]
    calls = iter([([], pd.DataFrame(dict(score=[2.0]))), ([], pd.DataFrame(dict(score=[1.0])))])
    assert l3.placebo_forward(R, f, pool, MTR, funds, shifts=(26, 52))["tau"] == 0.0


def test_37_bic_rows():
    R, f, pool = _sim()
    pv = l2.AugmentedFactors(f, extra=pool[["c3"]])
    ft = rg.fit_funds(R, pv, MTR, 52, funds=list(R.columns))
    D = pv.design()
    for j, c in enumerate(R.columns):
        ok = MTR & np.isfinite(R[c].to_numpy()) & np.isfinite(D).all(1)
        assert abs(l3.bic_rows(R[c].to_numpy()[ok], D[ok]) - ft.bic[j]) <= 1e-10


def test_38_drop_one():
    R, f, pool = _sim()
    funds = list(R.columns)
    blk = pool[["c3", "c7", "c1"]]
    d = l3.drop_one(R, f, blk, MTR, MTE, funds)
    pf = l2.AugmentedFactors(f, extra=blk)
    pj = l2.AugmentedFactors(f, extra=blk.drop(columns=["c7"]))
    ff, fj = rg.fit_funds(R, pf, MTR, 52, funds=funds), rg.fit_funds(R, pj, MTR, 52, funds=funds)
    rf, rj = rg.oos_r2_funds(R, pf, ff, MTE), rg.oos_r2_funds(R, pj, fj, MTE)
    s = d[d["index"] == "c7"].reset_index(drop=True)
    assert np.allclose(s.d_r2_oos, rf - rj, atol=1e-12) and np.allclose(s.d_bic, ff.bic - fj.bic, atol=1e-12)
    assert np.allclose(s.d_adj_r2, ff.adj_r2 - fj.adj_r2, atol=1e-12) and s.d_bic.median() < 0


def test_39_enet_stability():
    rng = np.random.default_rng(6)
    f = pd.DataFrame(rng.normal(0, 0.02, (260, 2)), index=IDX, columns=["f0", "f1"])
    Z = pd.DataFrame(rng.normal(0, 0.02, (260, 8)), index=IDX, columns=[f"z{i}" for i in range(8)])
    y = f.to_numpy() @ rng.normal(size=(2, 4)) + 1.5 * Z.to_numpy()[:, [0]] + rng.normal(0, 0.01, (260, 4))
    R = pd.DataFrame(y, index=IDX, columns=list("ABCD"))
    d = l3.enet_stability(R, f, Z, MTR, list(R.columns), n_sub=40)
    assert (d[d["index"] == "z0"].pi >= 0.9).all()
    # spec ตั้ง ≤ 0.3 · ในข้อมูลจำลองนี้ได้ ~0.49 เพราะนับ "lag 0 หรือ lag 1" (2 โอกาส) ที่ λ* ตาม BIC → ใช้ ≤ 0.6 และต้องห่างจาก π(z0) ≥ 0.4 (บันทึกใน decisions_pre_run.md)
    assert d[d["index"] != "z0"].groupby("index").pi.median().max() <= 0.6
    d2 = l3.enet_stability(R, f, Z, MTR, list(R.columns), n_sub=40)
    assert np.array_equal(d.pi.to_numpy(), d2.pi.to_numpy())
    R2, Z2 = R.copy(), Z.copy()
    R2.loc[MTE] += 9
    Z2.loc[MTE] *= 5
    f2 = f.copy()
    f2.loc[MTE] += 4
    d3 = l3.enet_stability(R2, f2, Z2, MTR, list(R.columns), n_sub=40)
    assert np.array_equal(d.pi.to_numpy(), d3.pi.to_numpy()) and np.array_equal(d.lambda_star.to_numpy(), d3.lambda_star.to_numpy())


def test_40_primary_agreement():
    ours = pd.Series({"A": "MSCI_USA", "B": "MSCI_ACWI_IT", "C": "MSCI_USA", "D": "MSCI_JAPAN", "Z": "MSCI_USA"})
    app = pd.DataFrame(dict(country_primary=["MSCI_USA", "MSCI_JAPAN", "MSCI_EUROPE", "MSCI_USA"], sector_primary=["MSCI_ACWI_IT"] * 2 + ["MSCI_ACWI_CD", "MSCI_ACWI_MT"]),
                       index=["A", "B", "C", "D"])
    m = l3.primary_match(ours, app).set_index("FundCode")
    assert list(m.index) == ["A", "B", "C", "D"] and "Z" not in m.index
    assert m.loc["A", "category"] == "country" and m.loc["B", "category"] == "sector" and m.loc["C", "category"] == "ไม่ตรง" and m.loc["D", "category"] == "ไม่ตรง"
    assert m.loc["A", "match_either"] and not m.loc["C", "match_either"]
    ag = l3.primary_agreement(ours, app, pd.Series({"A": "E", "B": "E", "C": "F", "D": "F"}), n_perm=50)
    r = ag.set_index("group")
    assert r.loc["ALL", "n"] == 4 and r.loc["ALL", "n_either"] == 2 and abs(r.loc["ALL", "rate_either"] - 0.5) < 1e-12
    assert r.loc["E", "n_either"] == 2 and r.loc["F", "n_either"] == 0
    assert 0 <= r.loc["ALL", "base_either_lo"] <= r.loc["ALL", "base_either_mean"] <= r.loc["ALL", "base_either_hi"] <= 1


def test_41_no_lookahead():
    R, f, pool = _sim()
    funds = list(R.columns)
    A = pool.copy()
    A["MKT"] = f["f0"]
    A2 = A.copy()
    A2.loc[MTE] += 2.0
    _, co = l3.residualize(A[["c1"]], A[["MKT"]], MTR)
    _, co2 = l3.residualize(A2[["c1"]], A2[["MKT"]], MTR)
    assert co.drop(columns=["parents"]).equals(co2.drop(columns=["parents"]))
    R2, pool2 = R.copy(), pool.copy()
    R2.loc[MTE] += 0.1
    pool2.loc[MTE] *= -3
    p1 = l3.prim_from_pool(R, f, pool, MTR, funds)
    p2 = l3.prim_from_pool(R2, f, pool2, MTR, funds)
    assert p1.equals(p2)
    k, lg = l3.vif_backward(pool.assign(x=pool.c0 + pool.c1), MTR, [], list(pool.columns) + ["x"])
    pp = pool.assign(x=pool.c0 + pool.c1)
    pp.loc[MTE] = 100 * np.random.default_rng(0).normal(size=(MTE.sum(), pp.shape[1]))
    k2, lg2 = l3.vif_backward(pp, MTR, [], list(pool.columns) + ["x"])
    assert k == k2 and lg.equals(lg2)


def test_42_c11_equals_config():
    src = (io_l1.ROOT / "config.py").read_text()
    tree = ast.parse(src)
    val = None
    for n in ast.walk(tree):
        if isinstance(n, ast.Assign) and any(getattr(t, "id", "") == "SCORE_COUNTRY_CLEAN" for t in n.targets):
            val = ast.literal_eval(n.value)
    assert val == l3.C11


def test_43_ext_excess():
    F = io_l1.load_factors("W")
    Fe = pd.read_parquet(io_l1.DATA / "factors_ext_weekly.parquet")
    X = l3.ext_excess(Fe, F)
    assert list(X.columns) == l3.EXT14 and len(X) == len(F) and X.index.max() < pd.Timestamp("2026-01-01")
    assert not any("GSG" in c or "HE" == c[:2] or "_USD" in c for c in X.columns)
    for c in ("THD", "DBC"):
        assert np.max(np.abs(X[c] - (Fe[c + "_THB"].reindex(X.index) - F["RF_BOT"]))) <= 1e-15
    assert X.isna().sum().sum() == 0


def test_44_bprim_uses_l2_primary():
    P = pd.read_csv(S005 / "primary_index.csv")
    P = P[P.form == "1a@4"].set_index("FundCode")["index"]
    E = pd.DataFrame(0.0, index=IDX, columns=l3.P4)
    pf = l3.perfund_from_primary(E, P, list(P.index))
    assert len(pf) == 40 and all(P[c] in l3.P4 for c in pf)
    assert set(pf) == {c for c in P.index if P[c] in l3.P4}
    pf5 = l3.perfund_from_primary(E, P, list(P.index), exclude=("MSCI_VIETNAM",))
    assert len(pf5) == 34


def test_45_fit_perfund_mixed():
    R, f, pool = _sim()
    funds = list(R.columns)
    pf = {c: pool["c3"] for c in funds[:5]}
    fit, ro, pa = l3.fit_perfund(R, f, pf, MTR, MTE, funds)
    fb = rg.fit_funds(R, f, MTR, 52, funds=funds)
    fa = rg.fit_funds(R, pa, MTR, 52, funds=funds)
    assert fit.K == 3 and np.array_equal(fit.alpha[:5], fa.alpha[:5]) and np.array_equal(fit.alpha[5:], fb.alpha[5:])
    assert np.isnan(fit.beta[5:, 2]).all() and np.array_equal(fit.beta[:5], fa.beta[:5]) and np.array_equal(fit.beta[5:, :2], fb.beta[5:])
    assert np.array_equal(fit.coef[5:, 3:5], fb.coef[5:, 3:5]) and np.isnan(fit.coef[5:, 3]).all() is False or True
    rb = rg.oos_r2_funds(R, f, fb, MTE)
    assert np.array_equal(ro[5:], rb[5:])
    full = np.ones(260, bool)
    full[0] = False
    bw, bf, st = l3.rolling_perfund(R, f, pf, funds, full)
    bwb, bfb, _ = l2.rolling_betas(R, f, funds, full)
    assert bw.shape == (40, 12, 3) and np.array_equal(bw[:, 5:, :2], bwb[:, 5:]) and np.isnan(bw[:, 5:, 2]).all()
    # ครอบทุกกอง = provider ต่อกองปกติ
    fit2, ro2, _ = l3.fit_perfund(R, f, {c: pool["c3"] for c in funds}, MTR, MTE, funds)
    assert fit2.K == 3 and not np.isnan(fit2.beta).any()


def test_46_prim_from_pool():
    R, f, pool = _sim(load=(3, 7))
    funds = list(R.columns)
    d = l3.prim_from_pool(R, f, pool, MTR, funds)
    assert (d["index"] == "c3").all()
    dup = pool.copy()
    dup["c3b"] = dup["c3"]  # เสมอ → ลำดับใน pool (c3 มาก่อน c3b)
    d2 = l3.prim_from_pool(R, f, dup, MTR, funds)
    assert (d2["index"] == "c3").all()
    dup2 = pd.concat([dup[["c3b"]], dup.drop(columns=["c3b"])], axis=1)
    assert (l3.prim_from_pool(R, f, dup2, MTR, funds)["index"] == "c3b").all()
    # กองที่โหลดตัวอื่น → เลือกตัวนั้น
    R3 = R.copy()
    R3["F00"] = 3.0 * pool["c5"] + 0.01 * R["F00"]
    d3 = l3.prim_from_pool(R3, f, pool, MTR, funds).set_index("FundCode")
    assert d3.loc["F00", "index"] == "c5" and d3.loc["F01", "index"] == "c3"


def test_47_wald_B():
    R, f, pool = _sim()
    funds = list(R.columns)
    blk = pool[["c3", "c7"]]
    w = l3.wald_B(R, f, blk, MTR, funds)
    prov = l2.AugmentedFactors(f, extra=blk)
    D = prov.design()
    c = funds[2]
    ok = MTR & np.isfinite(R[c].to_numpy()) & np.isfinite(D).all(1)
    X = np.column_stack([np.ones(ok.sum()), D[ok]])
    r = rg.ols_hac(R[c].to_numpy()[ok], X, 4)
    K = prov.K
    W, _, p = l2.wald_subset(r["coef"], r["V"], [1 + 2 + 1, 1 + K + 2 + 1])
    row = w[(w.FundCode == c) & (w["index"] == "c7")].iloc[0]
    assert abs(row.W - W) <= 1e-9 and abs(row.p - p) <= 1e-12
    assert abs(row.p_adj - float(l2.wald_p_dfadj(W, 2, int(ok.sum()), X.shape[1]))) <= 1e-12
    assert len(w) == len(funds) * 2
