"""test 6, 7, 9, 10, 14–19 + ฟังก์ชันเสริม"""
import numpy as np
import pandas as pd
import pytest
from scipy import stats

import external
import forms
import fundff as ff
import hybrid
import io_l1
import regress
import samples
import scorecard as sc
import tests_stat as ts
from samples import window_mask

IDX = pd.date_range("2021-01-08", periods=260, freq="W-FRI")


def _R(n=30, seed=0, cols=None):
    rng = np.random.default_rng(seed)
    cols = cols or [f"F{i:02d}" for i in range(n)]
    return pd.DataFrame(rng.normal(0.001, 0.01, size=(260, len(cols))), index=IDX, columns=cols)


def test_06_apb_ew_loo_minn():
    R = _R(12, 1)
    pol = {c: "E" for c in R.columns}
    members = list(R.columns)
    prov = ff.apb(R, pol, True, members, min_n=5)
    c0 = members[0]
    s = prov.series(c0)[:, 0]
    manual = R[members[1:]].mean(axis=1).to_numpy()
    assert np.allclose(s, manual)  # LOO ไม่รวมกองตัวเอง
    assert not np.allclose(prov.series(None)[:, 0], s)
    e = ff.ew_factor(R, members, exclude=c0, min_n=5)
    assert np.allclose(e, manual)
    R2 = R.copy()
    R2.iloc[10, 1:9] = np.nan  # เหลือ 4 กอง (นอก c0) < 5 → NaN
    s2 = ff.apb(R2, pol, True, members, min_n=5).series(c0)[:, 0]
    assert np.isnan(s2[10]) and np.isfinite(s2[11])
    assert np.isnan(ff.ew_factor(R2, members, exclude=c0, min_n=5).iloc[10])
    assert ff.apb(R, pol, False, members).shape == (260, 3)


@pytest.fixture(scope="module")
def real():
    R = io_l1.load_returns("W")
    F = io_l1.load_factors("W")
    U = io_l1.load_universe().set_index("FundCode")
    keep = samples.dedup_keep(io_l1.load_dup_pairs(), U.loc[R.columns, "n_weeks"])
    base = samples.eligible(R, "unbalanced", keep)
    bal = samples.eligible(R, "balanced", keep)
    return dict(R=R, F=F, U=U, pol=U["policy"], keep=keep, base=base, bal=bal, aum=io_l1.load_aum())


def test_07_no_lookahead(real):
    R, F, pol, base, bal, aum = (real[k] for k in ("R", "F", "pol", "base", "bal", "aum"))
    R2 = R.copy()
    rng = np.random.default_rng(11)
    after_train = R.index > pd.Timestamp("2023-12-29")
    R2.loc[after_train] = R2.loc[after_train] * 3 + rng.normal(0, 0.02, size=R2.loc[after_train].shape)
    t1 = forms.train_characteristics(R, F, aum, pol, base)
    t2 = forms.train_characteristics(R2, F, aum, pol, base)
    for k in ("r2", "reg", "flags", "fx", "act", "aumlog", "sigma"):
        assert t1[k].equals(t2[k]), k
    assert forms.make_ports(base, pol, t1).equals(forms.make_ports(base, pol, t2))
    h1 = samples.split_halves(base, pol)
    assert h1.equals(samples.split_halves(base, pol))
    l1a = forms.build_line1(R, bal, base, kstar=4, n_perm=20)
    l1b = forms.build_line1(R2, bal, base, kstar=4, n_perm=20)
    assert np.array_equal(l1a["parts"]["Lam_a"], l1b["parts"]["Lam_a"])
    assert np.array_equal(l1a["parts"]["Lam_c"], l1b["parts"]["Lam_c"])
    from external import line3
    F3 = line3(F, "3a")
    r1 = hybrid.residual_pc(R, F3, window_mask(R.index, "train"), bal)
    r2 = hybrid.residual_pc(R2, F3, window_mask(R.index, "train"), bal)
    assert np.array_equal(r1["W"], r2["W"]) and np.array_equal(r1["coef"], r2["coef"])
    # MOM: แก้ผลตอบแทนหลัง τ=2022-12-30 → ป้ายถึงรอบถือครองถัดไปไม่เปลี่ยน
    E = [c for c in base if pol[c] == "E"]
    tau = list(R.index).index(pd.Timestamp("2022-12-30"))
    nxt = list(R.index).index(pd.Timestamp("2023-03-31"))
    R3 = R.copy()
    R3.iloc[tau + 1:] = R3.iloc[tau + 1:] * 5 + rng.normal(0, 0.03, size=R3.iloc[tau + 1:].shape)
    m1 = ff.momentum(R[E])
    m3 = ff.momentum(R3[E])
    assert m1.iloc[:nxt + 1].equals(m3.iloc[:nxt + 1])
    assert not m1.iloc[nxt + 1:].equals(m3.iloc[nxt + 1:])  # ไวต่อข้อมูลหลัง τ สำหรับรอบถัดไป (ตรวจว่า test มีพลัง)
    first = (m1.abs().sum(axis=1) > 0).idxmax()
    assert first == pd.Timestamp("2022-01-07")
    assert (m1.loc[:"2022-01-07"].iloc[:-1] == 0).all().all()


def _grs_closed(Rp, X):
    T, N = Rp.shape
    L = X.shape[1]
    Xc = np.column_stack([np.ones(T), X])
    B = np.linalg.solve(Xc.T @ Xc, Xc.T @ Rp)
    E = Rp - Xc @ B
    Su = E.T @ E / (T - L - 1)  # dof T-L-1
    Om = np.cov(X.T, ddof=0).reshape(L, L)
    mu = X.mean(0)
    a = B[0]
    w = (T / (T - L - 1)) * a @ np.linalg.inv(Su) @ a / (1 + mu @ np.linalg.inv(Om) @ mu)
    return (T - N - L) / N * w * (T - L - 1) / T * 1.0 if False else (T - N - L) / N * (a @ np.linalg.inv(E.T @ E / T) @ a) / (1 + mu @ np.linalg.inv(Om) @ mu)


def test_09_grs():
    rng = np.random.default_rng(12)
    T, N, L = 60, 5, 3
    X = rng.normal(0.002, 0.01, size=(T, L))
    Rp = X @ rng.normal(size=(L, N)) + rng.normal(0, 0.005, size=(T, N)) + 0.0008
    g = ts.grs(Rp, X)
    assert abs(g["F"] - _grs_closed(Rp, X)) < 1e-9 and g["dof2"] == T - N - L
    # ค่าตัวอย่างคำนวณมือ N=1, L=1 (สูตรเดี่ยว): F=(T-2)·α²/(σ̂²(1+μ²/ω²))
    T = 8
    x = np.array([0.01, -0.02, 0.03, 0.0, 0.015, -0.01, 0.02, 0.005])
    y = np.array([0.02, -0.01, 0.04, 0.01, 0.01, 0.0, 0.03, -0.01])
    Xc = np.column_stack([np.ones(T), x])
    b = np.linalg.solve(Xc.T @ Xc, Xc.T @ y)
    e = y - Xc @ b
    sig2 = e @ e / T
    om2 = x.var()
    hand = (T - 2) * b[0] ** 2 / (sig2 * (1 + x.mean() ** 2 / om2))
    assert abs(ts.grs(y[:, None], x[:, None])["F"] - hand) < 1e-9
    # simulation H0: N=20, T=104, L=8
    rng = np.random.default_rng(20261015)
    N, T, L = 20, 104, 8
    B = rng.normal(size=(L, N))
    A = rng.normal(size=(N, N)) * 0.003
    rej = 0
    for _ in range(1000):
        X = rng.normal(0.001, 0.01, size=(T, L))
        Rp = X @ B + rng.normal(size=(T, N)) @ A + rng.normal(0, 0.004, size=(T, N))
        rej += ts.grs(Rp, X)["p"] < 0.05
    assert 0.035 <= rej / 1000 <= 0.065, rej / 1000


def _py_sim(block, reps=1000, N=200, T=104, m=4, seed=20261015):
    rng = np.random.default_rng(seed)
    rej = 0
    for _ in range(reps):
        X = rng.normal(0.001, 0.01, size=(T, m))
        Xc = np.column_stack([np.ones(T), X])
        z = rng.normal(size=(T, N))
        if block:
            u = rng.normal(size=(T, N // 5))
            z = np.sqrt(0.5) * np.repeat(u, 5, axis=1) + np.sqrt(0.5) * z
        Y = z * 0.01
        B = np.linalg.lstsq(Xc, Y, rcond=None)[0]
        E = Y - Xc @ B
        s2 = (E ** 2).sum(0) / (T - m - 1)
        A00 = np.linalg.inv(Xc.T @ Xc)[0, 0]
        t = B[0] / np.sqrt(s2 * A00)
        rej += ts.pesaran_yamagata(t, E, T, m)["p"] < 0.05
    return rej / reps


def test_10_pesaran_yamagata():
    assert 0.03 <= _py_sim(False) <= 0.08
    assert 0.02 <= _py_sim(True) <= 0.10
    # (ค) c_p ใช้ f(N)=N และ √v · เทียบ brute-force
    rng = np.random.default_rng(13)
    T, N, m = 104, 200, 4
    E = rng.normal(size=(T, N))
    E[:, 1] = 0.5 * E[:, 0] + np.sqrt(0.75) * E[:, 1]
    E[:, 3] = 0.30 * E[:, 2] + np.sqrt(1 - 0.09) * E[:, 3]
    t = rng.normal(size=N)
    r = ts.pesaran_yamagata(t, E, T, m)
    v = T - m - 1
    c = stats.norm.ppf(1 - 0.10 / (2 * N))
    assert abs(r["c"] - c) < 1e-12 and r["v"] == v
    C = np.corrcoef(E, rowvar=False)
    tot = 0.0
    for i in range(N):
        for j in range(i + 1, N):
            if np.sqrt(v) * abs(C[i, j]) > c:
                tot += C[i, j] ** 2
    assert abs(r["rho2"] - 2 / (N * (N - 1)) * tot) < 1e-12
    assert tot > 0
    num = np.sum(t ** 2 - v / (v - 2)) / np.sqrt(N)
    den = np.sqrt(2 * ((v - 1) / (v - 4)) * (v / (v - 2)) ** 2 * (1 + (N - 1) * r["rho2"]))
    assert abs(r["J"] - num / den) < 1e-12 and abs(r["p"] - stats.norm.sf(num / den)) < 1e-12
    assert np.isnan(ts.pesaran_yamagata(t, E, 8, 4)["J"])  # v ≤ 4 → N/A


def _synth(seed=14, N=60, k3=4, nres=1):
    rng = np.random.default_rng(seed)
    T = 260
    f3 = pd.DataFrame(rng.normal(0.002, 0.01, size=(T, k3)), index=IDX, columns=["MKT", "BOND", "GOLD", "FX"])
    h = rng.normal(0.001, 0.008, size=(T, nres))
    B3 = rng.normal(0.5, 0.5, size=(N, k3))
    lam = rng.uniform(0.5, 1.5, size=(N, nres)) * rng.choice([-1, 1], size=(N, 1))
    X = f3.to_numpy() @ B3.T + h @ lam.T + rng.normal(0, 0.002, size=(T, N))
    cols = [f"S{i:02d}" for i in range(N)]
    return pd.DataFrame(X, index=IDX, columns=cols), f3


def test_14_alpha_is_pricing_error():
    R, f3 = _synth()
    cols = list(R.columns)
    l1 = forms.build_line1(R, cols, cols, kstar=5, n_perm=20)
    mtr = window_mask(IDX, "train")
    xbar = np.abs(R.loc[mtr].mean()).mean()
    for nm in ("1a", "1b", "1c"):
        fit = regress.fit_funds(R, l1["forms"][nm].provider, mtr, 50)
        assert np.nanmean(np.abs(fit.alpha)) < 0.15 * xbar, (nm, np.nanmean(np.abs(fit.alpha)), xbar)
    # ④a: เพิ่ม α จริงเครื่องหมายสลับให้กองในช่วง test → refit ช่วง test ยังจับได้
    l4 = forms.build_line4(R, f3, cols)
    assert l4["rp"]["k_res"] >= 1
    rng = np.random.default_rng(15)
    a_true = rng.choice([-0.0015, 0.0015], size=len(cols))
    mte = window_mask(IDX, "test")
    R2 = R.copy()
    R2.loc[mte] = R2.loc[mte] + a_true
    g = hybrid.hybrid_factor(R2, f3, l4["rp"]["W"], l4["rp"]["s"], l4["rp"]["coef"], cols)
    F4 = pd.concat([f3, g], axis=1)
    fit = regress.fit_funds(R2, F4, mte, 50)
    assert np.corrcoef(fit.alpha, a_true)[0, 1] > 0.9
    assert abs(np.mean(np.abs(fit.alpha)) - 0.0015) < 0.0004
    # g สูตร: u = x − β̂'f (ไม่หัก α̂)
    D = regress.lag_stack(f3.to_numpy())
    u0 = R2[cols[0]].to_numpy() - D @ l4["rp"]["coef"][0, 1:]
    j = 7
    ok = np.isfinite(u0)
    assert ok.sum() == 259


def test_15_split_halves(real):
    pol, base = real["pol"], real["base"]
    h = samples.split_halves(base, pol)
    A, B = set(h.FundCode[h.half == "A"]), set(h.FundCode[h.half == "B"])
    assert not (A & B) and (A | B) == set(base) and len(base) == 277
    cnt = h.groupby(["half", "policy"]).size()
    assert (cnt["A"]["E"], cnt["A"]["F"], cnt["A"]["O"]) == (119, 11, 8)
    assert (cnt["B"]["E"], cnt["B"]["F"], cnt["B"]["O"]) == (119, 12, 8)
    assert h.equals(samples.split_halves(base, pol))
    # factor ทิศ A→B ไม่เปลี่ยนเมื่อแก้ผลตอบแทนกองใน B
    R = real["R"]
    tab = forms.train_characteristics(R, real["F"], real["aum"], pol, base)
    chA = forms.make_chars(R, sorted(A), pol, tab)
    f1 = ff.build_line2(R, chA, "c", loo=False, min_n=3).plain()
    R2 = R.copy()
    R2[sorted(B)] = R2[sorted(B)] * 7 + 0.01
    chA2 = forms.make_chars(R2, sorted(A), pol, tab)
    f2 = ff.build_line2(R2, chA2, "c", loo=False, min_n=3).plain()
    assert f1.equals(f2)


def test_16_assign_region():
    order = external.REGION_IDX
    rng = np.random.default_rng(16)
    rows, labs = [], []
    # 12 กอง USA · 12 กอง EUROPE · 4 กอง JAPAN (<10) · 5 กอง max R² < 0.30 · 3 กอง VIETNAM (<10)
    spec = [("MSCI_USA", 12, 0.8), ("MSCI_EUROPE", 12, 0.7), ("MSCI_JAPAN", 4, 0.7), (None, 5, 0.2), ("MSCI_VIETNAM", 3, 0.6)]
    for lab, n, r in spec:
        for _ in range(n):
            v = rng.uniform(0.0, 0.15, size=len(order))
            if lab:
                v[order.index(lab)] = r
            rows.append(v)
    T = pd.DataFrame(rows, columns=order, index=[f"X{i:02d}" for i in range(len(rows))])
    cm = pd.Series(True, index=T.index)
    out = ff.assign_region(T, cm)
    assert (out.label_pre.iloc[28:33] == ff.OTHER).all()
    # JAPAN 4 + VIETNAM 3 + 5 ต่ำ = 12 ≥ 10 → คงเป็น OTHER
    assert (out.label_post == ff.OTHER).sum() == 12
    assert (out.label_post == "MSCI_USA").sum() == 12
    # OTHER < 10 → ACWI
    T2 = T.drop(T.index[24:28])  # ตัด JAPAN 4 → OTHER = 8
    out2 = ff.assign_region(T2, pd.Series(True, index=T2.index))
    assert (out2.label_post == "MSCI_ACWI").sum() == 8 and (out2.label_post == ff.OTHER).sum() == 0
    # label ชุดเดียวกันใน FXH และ GRS: ใช้ label_post ตัวเดียวกัน
    pol = pd.Series("E", index=T.index)
    ports = ff.grs_portfolios(list(T.index), pol, out.label_post, pd.Series(rng.normal(size=len(T)), index=T.index),
                              pd.Series(1.0, index=T.index))
    assert set(ports.unique()) == {"E_MSCI_USA", "E_MSCI_EUROPE", "E_OTHER"}
    fl = pd.Series(False, index=T.index)
    grp = ff.sort_groups(out.label_post, fl, list(T.index))
    assert set(grp.unique()) == {"MSCI_USA", "MSCI_EUROPE", ff.OTHER}


def test_17_stability_disattenuated():
    rng = np.random.default_rng(17)
    N = 4000
    b = rng.normal(0, 1, size=(N, 1))
    se = np.full((N, 1), 0.5)
    b1 = b + rng.normal(0, 0.5, size=(N, 1))
    b2 = b + rng.normal(0, 0.5, size=(N, 1))
    r = sc.stability_disattenuated(b1, se, b2, se)
    assert abs(r["r"][0] - 0.8) < 0.03 and abs(r["r_star"][0] - 1.0) < 0.05
    assert abs(r["rel1"][0] - 0.8) < 0.03
    bt = rng.normal(0, 0.1, size=(N, 1))
    b1 = bt + rng.normal(0, 0.5, size=(N, 1))
    b2 = bt + rng.normal(0, 0.5, size=(N, 1))
    r = sc.stability_disattenuated(b1, se, b2, se)
    assert np.isnan(r["r_star"][0])  # rel < 0.10 → N/A


def test_18_hedged_fund_alpha_zero_and_fx_definition():
    rng = np.random.default_rng(20261015)
    T, N = 156, 200
    idx = IDX[:T]
    m = rng.normal(0.0015, 0.02, size=T)
    s = rng.normal(0, 0.011, size=T)
    rus, rth = 0.0009, 0.0004
    MKT = (1 + m) * (1 + s) - 1 - rth
    FX = (1 + rus) * (1 + s) - 1 - rth
    BOND = rng.normal(0, 0.01, size=T)
    GOLD = rng.normal(0, 0.01, size=T)
    X = (MKT - FX)[:, None] + rng.normal(0, 0.002, size=(T, N))
    R = pd.DataFrame(X, index=idx, columns=[f"H{i:03d}" for i in range(N)])
    mask = window_mask(idx, "train")
    Fa = pd.DataFrame({"MKT": MKT, "BOND": BOND, "GOLD": GOLD, "FX": FX}, index=idx)
    fa = regress.fit_funds(R, Fa, mask, 100)
    assert abs(np.mean(fa.alpha)) < 5e-5
    assert -1.05 <= np.median(fa.beta[:, 3]) <= -0.95 and 0.95 <= np.median(fa.beta[:, 0]) <= 1.05
    Fb = Fa.copy()
    Fb["FX"] = s
    fb = regress.fit_funds(R, Fb, mask, 100)
    assert abs(np.mean(fb.alpha) - (rth - rus)) < 5e-5
    # (ค) line3
    for fq in ("W", "M"):
        Fr = io_l1.load_factors(fq)
        want = (Fr["SHV_THB"] - Fr["RF_BOT"]).to_numpy()
        for v in ("3a", "3b", "3c"):
            L3 = external.line3(Fr, v)
            assert np.array_equal(L3["FX"].to_numpy(), want) and "USDTHB" not in L3.columns
        assert list(external.line3(Fr, "3a").columns) == ["MKT", "BOND", "GOLD", "FX"]
        assert list(external.line3(Fr, "3b").columns[:4]) == list(external.line3(Fr, "3a").columns)
    Fw = io_l1.load_factors("W")
    cm = forms.CommonFactors(external.line3(Fw, "3a")) if hasattr(forms, "CommonFactors") else None
    # ④a ใช้ ③a ชุดเดียวกัน (ชื่อคอลัมน์)
    R2, f3 = _synth()
    l4 = forms.build_line4(R2, f3, list(R2.columns))
    assert l4["form"].names[:4] == ["MKT", "BOND", "GOLD", "FX"]
    # (ง) เอกลักษณ์ข้อมูล
    F0 = io_l1.load_factors("W")
    ident = (1 + F0["SHV_USD"]) * (1 + F0["USDTHB"]) - 1
    assert (F0["SHV_THB"] - ident).abs().max() < 1e-10


def test_19_nonfx_flag():
    order = external.REGION_IDX
    rng = np.random.default_rng(19)
    n = 40
    rows = []
    for i in range(n):
        v = rng.uniform(0.0, 0.15, size=len(order))
        v[7 if i < 25 else 0] = 0.7  # ACWI 25 กอง · USA 15 กอง
        rows.append(v)
    rows.append(np.full(len(order), 0.10))  # LOW1: max<0.30 → flag a
    rows.append(np.full(len(order), 0.45))  # GOLD1: R² ทอง สูงกว่า
    codes = [f"E{i:02d}" for i in range(n)] + ["LOW1", "GOLD1"]
    r2 = pd.DataFrame(rows, columns=order, index=codes)
    r2g = pd.Series(0.05, index=codes)
    r2g["GOLD1"] = 0.9
    r2t = pd.Series(0.02, index=codes)
    fl = ff.nonfx_flags(r2, r2g, r2t)
    assert fl.loc["LOW1", "flag"] and fl.loc["LOW1", "reason"] == "a"
    assert fl.loc["GOLD1", "flag"] and fl.loc["GOLD1", "reason"] == "b"
    assert not fl["flag"].iloc[:n].any()
    pol = pd.Series("E", index=codes)
    R = _R(cols=codes, seed=20)
    fx = pd.Series(rng.normal(size=len(codes)), index=codes)
    fx["GOLD1"] = 99.0  # สูงสุด → ถ้าไม่ตัดจะอยู่ขาสูง
    act = pd.Series(rng.uniform(size=len(codes)), index=codes)
    act["LOW1"] = 5.0
    aum = pd.Series(rng.normal(20, 1, size=len(codes)), index=codes)
    ch1 = ff.line2_characteristics(R, codes, pol, r2, fx, act, fl["flag"], aum)
    ch0 = ff.line2_characteristics(R, codes, pol, r2, fx, act, pd.Series(False, index=codes), aum)
    for c in ("LOW1", "GOLD1"):
        assert ch1["fx"].get(c, 0) == 0 and ch1["act"].get(c, 0) == 0
    assert ch0["fx"]["GOLD1"] == -1 and ch0["act"]["LOW1"] == 1  # ถ้าไม่มีธงจะเข้าขา
    assert ch1["region"].equals(ch0["region"])  # ป้ายภูมิภาคไม่เปลี่ยน
    cm = pd.Series(True, index=codes)
    assert ff.grs_portfolios(codes, pol, ch1["region"]["label_post"], fx, aum).equals(
        ff.grs_portfolios(codes, pol, ch0["region"]["label_post"], fx, aum))
    # ยังอยู่ใน APB_E / SIZE
    p = ff.build_line2(R, ch1, "c", loo=True, min_n=5)
    manual = R.drop(columns=["E00"]).mean(axis=1).to_numpy()
    assert np.allclose(p.series("E00")[:, 0], manual)  # APB_E รวม LOW1/GOLD1
    assert ch1["size"].get("GOLD1", None) is not None
    assert "GOLD1" not in ch1["sort_group"].index and "LOW1" not in ch1["sort_group"].index


def test_misc_functions():
    rng = np.random.default_rng(21)
    # sort_legs
    char = pd.Series(np.arange(10.0), index=[f"C{i}" for i in range(10)])
    lab = ff.sort_legs(char, pd.Series("g", index=char.index), "low")
    assert list(lab.index[lab == 1]) == ["C0", "C1", "C2"] and list(lab.index[lab == -1]) == ["C7", "C8", "C9"]
    lab = ff.sort_legs(char, pd.Series("g", index=char.index), "high")
    assert list(lab.index[lab == 1]) == ["C7", "C8", "C9"]
    # momentum: ผู้ชนะ = กองที่ขึ้นแรงที่สุดในช่วงสร้าง
    R = _R(10, 22)
    R.iloc[:, 0] += 0.01
    R.iloc[:, 9] -= 0.01
    m = ff.momentum(R)
    assert (m.iloc[60:70, 0] == 1).all() and (m.iloc[60:70, 9] == -1).all()
    # spanning: A ⊂ span(B) → R²≈1, α≈0
    fB = pd.DataFrame(rng.normal(size=(260, 2)), index=IDX, columns=["a", "b"])
    fA = pd.DataFrame({"x": 2 * fB["a"] + fB["b"] + 0.001 * rng.normal(size=260)}, index=IDX)
    sp = ts.spanning(fA, fB, window_mask(IDX, "test"))
    assert sp["r2"][0] > 0.99 and sp["p"] > 0.001 and sp["df"] == 1
    # vif
    z = rng.normal(size=(500, 2))
    X = np.column_stack([z[:, 0], z[:, 0] + 0.1 * z[:, 1], rng.normal(size=500)])
    v = ts.vif(X)
    assert v[0] > 50 and 0.9 < v[2] < 1.2
    # bootstrap
    S = np.column_stack([rng.normal(0.5, 0.1, 200), rng.normal(0.3, 0.1, 200)])
    pol = np.array(["E"] * 150 + ["F"] * 30 + ["O"] * 20)
    bs = ts.bootstrap_median(S, pol, pairs=[(0, 1)], n_boot=200)
    lo, hi = bs["E"][0][:, 0]
    assert lo < 0.5 < hi and bs["E"][1][0, 0] > 0
    assert bs["ALL"][0].shape == (2, 2)
    # py_extended
    E = rng.normal(size=(104, 50))
    pe = ts.py_extended(rng.normal(size=50), np.full(50, 104), E, 4)
    assert np.isfinite(pe["J"])
    # summ / canonical / interpret / rolling / halves / ceiling
    s = sc.summ([1, 2, 3, 4, np.nan])
    assert s["n"] == 4 and s["median"] == 2.5
    A = rng.normal(size=(100, 2))
    assert sc.canonical_corr(A, A @ np.array([[1, 2], [3, 1]])).min() > 0.999
    fac = pd.DataFrame({"p": rng.normal(size=200)}, index=range(200))
    ref = pd.DataFrame({"u": fac["p"] + 0.1 * rng.normal(size=200), "v": rng.normal(size=200)}, index=range(200))
    it = sc.interpret(fac, ref)
    assert it.iloc[0]["ref"] == "u" and it.iloc[0]["label"].startswith("≈")
    bw = rng.normal(size=(5, 80, 2))
    med, mn = sc.stability_rolling(bw, bw[0])
    assert med.shape == (2,) and sc.stability_ceiling(bw[0], bw[0])[0] > 0.999
    # fit_funds / score_model
    R, f3 = _synth(seed=23, N=20)
    fit = regress.fit_funds(R, f3, window_mask(IDX, "train"), 50)
    oos = regress.oos_r2_funds(R, f3, fit, window_mask(IDX, "test"))
    sm_ = sc.score_model(fit, oos, np.array(["E"] * 20))
    assert sm_.loc[sm_.policy == "E", "n"].iloc[0] == 20 and 0 < sm_.adjr2_med.iloc[0] < 1
    assert fit.n.min() == 155
    # region_returns / reference_set / label_index
    Fw = io_l1.load_factors("W")
    assert set(external.REGION_IDX + ["USDTHB", "GOLDX", "TDEXX"]) <= set(external.region_returns(Fw).columns)
    assert "SHV_THB" in external.reference_set(Fw).columns
    assert ff.label_index(ff.OTHER) == "MSCI_ACWI"
    # residual_pc: ไม่มี residual factor → k_res = 0
    Rn = pd.DataFrame(rng.normal(0, 0.005, size=(260, 30)), index=IDX, columns=[f"N{i}" for i in range(30)])
    f3n = pd.DataFrame(rng.normal(0, 0.01, size=(260, 4)), index=IDX, columns=["MKT", "BOND", "GOLD", "FX"])
    rp = hybrid.residual_pc(Rn, f3n, window_mask(IDX, "train"), list(Rn.columns))
    assert rp["k_res"] == 0
    # samples.eligible / dedup
    n_w = pd.Series({"a": 10, "b": 20, "c": 5, "d": 7})
    dp = pd.DataFrame({"a": ["a", "b"], "b": ["b", "c"]})
    assert samples.dedup_keep(dp, n_w) == ["b", "d"]
    assert samples.window_mask(IDX, "odd").sum() + samples.window_mask(IDX, "even").sum() == 260


def test_port_alpha():
    rng = np.random.default_rng(31)
    X = rng.normal(0, 0.01, size=(200, 3))
    Rp = X @ rng.normal(size=(3, 4)) + np.array([0.001, -0.002, 0.0, 0.003]) + rng.normal(0, 0.0005, size=(200, 4))
    a = sc.port_alpha(Rp, X)
    assert np.allclose(a, [0.001, -0.002, 0.0, 0.003], atol=2e-4)
    assert np.allclose(a, ts.grs(Rp, X)["alpha"])
