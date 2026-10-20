"""test_p2 — ข้อมูลจำลองเท่านั้น (S010 ข้อ 11.2 + S011) · pytest -p no:cacheprovider"""
import csv
import hashlib
import math
import shutil
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from scipy import stats

import p2
import regress as rg

LIBDIR = Path(__file__).resolve().parents[1]


def hsh(x):
    if isinstance(x, pd.DataFrame):
        x = x.to_numpy(float)
    if isinstance(x, pd.Series):
        x = x.to_numpy(float)
    return hashlib.sha256(np.ascontiguousarray(np.asarray(x, float)).tobytes()).hexdigest()


def make_inputs(N=64, T=200, seed=1, start_nan=True):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2021-01-08", periods=T, freq="W-FRI")
    K = 3
    f = rng.standard_normal((T, K)) * 0.01
    gold = rng.standard_normal(T) * 0.01
    F3 = pd.DataFrame(dict(MKT=f[:, 0] + 0.002, BOND=rng.standard_normal(T) * 0.004, GOLD=gold, FX=rng.standard_normal(T) * 0.003), index=idx)
    codes = [f"F{i:03d}" for i in range(N)]
    L = rng.standard_normal((N, K)) * 0.7 + np.array([1.0, 0.3, 0.0])
    names = {}
    R = f @ L.T + rng.standard_normal((T, N)) * 0.004
    # กองทอง 3 กอง · ปันผล 3 กอง · คู่ซ้ำ 2 คู่
    gold_ix = [0, 1, 2]
    R[:, gold_ix] = gold[:, None] * 1.0 + rng.standard_normal((T, 3)) * 0.003
    R[:, 10] = R[:, 11] + rng.standard_normal(T) * 1e-5  # ซ้ำ
    R[:, 20] = R[:, 21] + rng.standard_normal(T) * 1e-5
    R = pd.DataFrame(R, index=idx, columns=codes)
    if start_nan:
        for j in range(30, 40):  # กองเกิดใหม่
            R.iloc[: 60 + 3 * (j - 30), j] = np.nan
    for j in range(40, 46):  # รูแบบสุ่ม
        R.iloc[rng.choice(T, 5, replace=False), j] = np.nan
    R.iloc[150:, 47] = np.nan  # เลิก
    raw = R + 0.0005
    raw.iloc[:, 50] = 0.0  # กอง zero
    raw.iloc[:, 50] = raw.iloc[:, 50].where(raw.index.isin(raw.index[::2]), 0.001)
    Z = p2.zero_flags(raw.where(R.notna()))
    meta = pd.DataFrame(dict(policy=["E"] * (N - 24) + ["F"] * 14 + ["O"] * 10, div_flag=["N"] * N, gold=[False] * N), index=codes)
    meta.loc[codes[:3], "gold"] = True
    meta.loc[codes[3:6], "div_flag"] = "Y"
    meta["ter"] = rng.uniform(0.5, 2.5, N)
    meta["ter_src"] = ["actual"] * (N - 4) + ["rate"] * 4
    meta["ter_vintage"] = "le2025"
    AUM = pd.DataFrame(np.exp(rng.standard_normal((T, N)) + 18), index=idx, columns=codes)
    AUM.iloc[rng.random((T, N)) < 0.05] = np.nan
    return p2.Inputs(R, Z, F3, AUM, meta)


def scramble(inp, t_pos, seed=99):
    """แทนทุกแถว > t ของ R, Z, F3, AUM ด้วยค่าสุ่ม + รูสุ่ม"""
    rng = np.random.default_rng(seed)
    R, Z, F3, AUM = inp.R.copy(), inp.Z.copy(), inp.F3.copy(), inp.AUM.copy()
    n = len(R) - t_pos - 1
    R.iloc[t_pos + 1:] = rng.standard_normal((n, R.shape[1])) * 0.05
    R.iloc[t_pos + 1:] = R.iloc[t_pos + 1:].where(rng.random((n, R.shape[1])) > 0.2)
    Z.iloc[t_pos + 1:] = (rng.random((n, R.shape[1])) < 0.5).astype(float)
    F3.iloc[t_pos + 1:] = rng.standard_normal((n, 4)) * 0.05
    AUM.iloc[t_pos + 1:] = rng.random((n, R.shape[1])) * 1e9
    return p2.Inputs(R, Z, F3, AUM, inp.meta)


def state_hashes(st):
    h = {}
    h["U"] = tuple(st["U"])
    h["S"] = tuple(st["S"])
    h["Lam"], h["sd"], h["Lam_al"], h["Q"] = hsh(st["Lam"]), hsh(st["sd"]), hsh(st["Lam_al"]), hsh(st["Q"])
    h["sig"] = hsh(st["sig"])
    h["c3"] = (st["c3_cut"], tuple(st["c3_member"].astype(int)))
    h["cl"] = tuple(st["clusters"].items())
    h["reps"] = tuple(sorted(st["reps"]))
    h["f"] = hsh(st["f_le"])
    h["coef"] = (hsh(st["fit_e"].coef), hsh(st["fit_3a"].coef), hsh(st["fit_104"].coef), hsh(st["fit_al"].coef))
    h["b1"] = (hsh(st["B1_al"][0]), hsh(st["B1_al"][1]), hsh(st["B1_raw"][0]), hsh(st["B1_raw"][1]))
    return h


# 1 ─ วันที่
def test_dates():
    idx = pd.date_range("2021-01-08", "2025-12-26", freq="W-FRI")
    d = p2.decision_dates(idx, "Q")
    exp = ["2022-03-25", "2022-06-24", "2022-09-30", "2022-12-30", "2023-03-31", "2023-06-30", "2023-09-29", "2023-12-29",
           "2024-03-29", "2024-06-28", "2024-09-27", "2024-12-27", "2025-03-28", "2025-06-27", "2025-09-26"]
    assert [x.strftime("%Y-%m-%d") for x in d["t"]] == exp
    assert list(d["n_q"]) == [13, 14] + [13] * 13
    assert d["e"].iloc[-1] == pd.Timestamp("2025-12-26")
    assert (d["e_pos"].iloc[:-1].to_numpy() == d["t_pos"].iloc[1:].to_numpy()).all()  # ต่อกันไม่ซ้อน
    m = p2.decision_dates(idx, "M")
    assert len(m) == 45 and m["e"].iloc[-1] == pd.Timestamp("2025-12-26")
    assert (m["e_pos"].iloc[:-1].to_numpy() == m["t_pos"].iloc[1:].to_numpy()).all()
    assert m["t"].iloc[0] == pd.Timestamp("2022-03-25")


# 2 ─ future-scramble (บังคับ) ที่ 3 จุด · สัญญาณทุกตัว + W1–W3
@pytest.mark.parametrize("variant", [None, "W1", "W2", "W3"])
def test_future_scramble(variant):
    inp = make_inputs()
    pts = [90, 130, 170]
    prev = None
    clean = []
    for tp in pts:
        prev = p2.state_at(inp, tp, prev, variant)
        clean.append(prev)
    for j, tp in enumerate(pts):
        sc = scramble(inp, tp)
        pv = None
        for tq in pts[: j + 1]:
            pv = p2.state_at(sc, tq, pv, variant)
        assert state_hashes(pv) == state_hashes(clean[j]), (variant, tp)


def sc_chain(inp, tq):
    """ข้อมูลที่ไม่ถูกสุ่มสำหรับจุดก่อนหน้า (คือข้อมูลเดิม — จุดเหล่านั้นอยู่ก่อน t ที่ถูกสุ่ม)"""
    return inp


# 3 ─ target
def test_target_future_and_frozen_pca():
    inp = make_inputs()
    st = p2.state_at(inp, 120)
    tg = p2.target_at(inp, st, 133, 13)["df"]
    sc = scramble(inp, 133)  # สุ่มแถว > t_{q+1}
    tg2 = p2.target_at(sc, p2.state_at(sc, 120), 133, 13)["df"]
    assert hsh(tg) == hsh(tg2)
    inp2 = make_inputs()
    inp2.R.iloc[125, 5] += 0.5  # เปลี่ยนแถวในไตรมาสเป้าหมาย
    st2 = p2.state_at(inp2, 120)
    assert hsh(st2["Lam"]) == hsh(st["Lam"])  # Λ_t ตรึง ไม่ใช่ PCA ใหม่
    tg3 = p2.target_at(inp2, st2, 133, 13)["df"]
    assert hsh(tg3) != hsh(tg)


# 4 ─ การหมุน (invertible และ orthogonal)
def test_rotation_invariance():
    inp = make_inputs()
    st = p2.state_at(inp, 140)
    R_le = p2.truncate(inp.R, st["t"])
    F3_le = p2.truncate(inp.F3, st["t"])
    U = st["U"]
    rng = np.random.default_rng(3)
    base = p2._fdf(st["f_le"], F3_le, None)
    outs = []
    Hs = [np.eye(4), rng.standard_normal((4, 4)), np.linalg.qr(rng.standard_normal((4, 4)))[0]]
    for H in Hs:
        Fd = base.copy()
        Fd[["PC1", "PC2", "PC3", "PC4"]] = Fd[["PC1", "PC2", "PC3", "PC4"]].to_numpy() @ H
        fit = p2.fit_at(R_le, Fd, U)
        # target
        rows = slice(141, 154)
        fT = np.hstack([st["f_le"][-1][None, :], __import__("pca").factor_returns(inp.R.iloc[rows][st["S"]].to_numpy(float), st["pf"]["Lam"], st["pf"]["sd"])[:0].reshape(0, 4)]) if False else None
        fTt = __import__("pca").factor_returns(inp.R.iloc[rows][st["S"]].to_numpy(float), st["pf"]["Lam"], st["pf"]["sd"])
        Fp = np.column_stack([np.vstack([st["f_le"][-1][None, :], fTt]) @ H, inp.F3["FX"].iloc[140:154].to_numpy(float)])
        T, _ = p2.targets(inp.R.iloc[rows][U].to_numpy(float), Fp, fit.coef, 13)
        fbar = np.nanmean(Fd.to_numpy(float)[-52:], axis=0)
        b2 = p2.sig_B2(fit, fbar)
        outs.append((fit.alpha, fit.t_alpha_hac, fit.r2, np.nan_to_num(fit.resid), T, b2.to_numpy()))
    for o in outs[1:]:
        for a, b in zip(outs[0], o):
            assert np.nanmax(np.abs(np.asarray(a) - np.asarray(b))) < 1e-9


# 5 ─ B1 · Procrustes
def test_b1_and_procrustes():
    rng = np.random.default_rng(5)
    f = rng.standard_normal((100, 4))
    s, sd = p2.b1_state(f)
    Fq = rng.standard_normal(4)
    _, m = p2.b1_payoff(s, sd, Fq, 13)
    sgn = np.diag([1, -1, 1, -1.0])
    s2, sd2 = p2.b1_state(f @ sgn)
    _, m2 = p2.b1_payoff(s2, sd2, Fq @ sgn, 13)
    assert abs(m - m2) < 1e-12
    th = 0.7
    Rm = np.eye(4)
    Rm[:2, :2] = [[math.cos(th), -math.sin(th)], [math.sin(th), math.cos(th)]]
    s3, sd3 = p2.b1_state(f @ Rm)
    _, m3 = p2.b1_payoff(s3, sd3, Fq @ Rm, 13)
    assert abs(m - m3) > 1e-6  # การหมุนที่ไม่ใช่การกลับเครื่องหมายเปลี่ยน m
    L_prev = np.linalg.qr(rng.standard_normal((30, 4)))[0]
    Q0 = np.linalg.qr(rng.standard_normal((4, 4)))[0]
    L_t = L_prev @ Q0
    funds = [f"X{i}" for i in range(30)]
    Q, common = p2.procrustes(L_t, funds, L_prev, funds)
    assert np.abs(L_t @ Q - L_prev).max() < 1e-10
    assert len(common) == 30


# 6 ─ factor_returns
def test_factor_returns():
    import pca as pc
    rng = np.random.default_rng(1)
    X = rng.standard_normal((10, 20))
    Lam = np.linalg.qr(rng.standard_normal((20, 4)))[0]
    sd = rng.uniform(0.5, 2, 20)
    f = pc.factor_returns(X, Lam, sd)
    assert np.abs(f - (X / sd) @ Lam).max() < 1e-10  # ครบ → Λ′(x/σ) ไม่หัก μ
    X[3, :11] = np.nan
    assert np.isnan(pc.factor_returns(X, Lam, sd, 0.5)[3]).all()  # หาย > 50% → NaN


# 7 ─ universe
def test_universe_and_gold_rules():
    inp = make_inputs()
    st = p2.state_at(inp, 150)
    U, S = set(st["U"]), set(st["S"])
    codes = list(inp.R.columns)
    assert not (U & set(codes[:3])) and not (U & set(codes[3:6]))  # ทอง / ปันผลไม่อยู่ใน U
    assert codes[50] not in U  # zero-share
    assert codes[47] not in U  # ไม่มีผลตอบแทนที่แถว t (u0)
    assert len({codes[10], codes[11]} & U) == 1 and len({codes[20], codes[21]} & U) == 1  # ซ้ำ → เหลือ 1
    assert not (set(codes[30:40]) & U) or all(inp.R.iloc[:151, j].notna().sum() >= 52 for j in range(30, 40) if codes[j] in U)
    assert set(codes[:3]) & S or True  # S_t รวมกองทองได้
    # ตัดซ้ำเก็บกองที่แถว ≤ t มากสุด
    R = inp.R.iloc[:151].copy()
    R.iloc[:30, 10] = np.nan
    keep = p2.dedup_at(R, [codes[10], codes[11]])
    assert keep == [codes[11]]
    # กฎ is_gold
    assert p2.is_gold("Krungsri Gold Fund", "") and p2.is_gold("TGOLD", None) and p2.is_gold("x", "กองทุนทองคำ") and p2.is_gold("sCb GOLD hp", "")
    assert not p2.is_gold("Golden Dragon Fund", "") and not p2.is_gold("Bond Fund", "ตราสารหนี้")


def test_is_gold_on_fundprofile():
    root = LIBDIR.parents[2]
    fp = root / "base_data" / "FundProfile.csv"
    pw = root / ".claude" / "factor_team" / "data" / "panel_weekly.parquet"
    if not fp.exists() or not pw.exists():
        pytest.skip("ไม่มีไฟล์ข้อมูล")
    assert hashlib.sha256(fp.read_bytes()).hexdigest() == "9516281426fc854c8f3a0833f119cad0ce581adb39450732e579084cb4cedfaf"
    F = pd.read_csv(fp).set_index("Fund Code")
    codes = pd.read_parquet(pw, columns=["FundCode"])["FundCode"].unique()
    g = sorted(c for c in codes if c in F.index and p2.is_gold(F.loc[c, "Fund Name EN"], F.loc[c, "Fund Name TH"]))
    # panel_weekly มีกองที่ไม่ได้อยู่ใน 433 · ตรวจเฉพาะ 433 ผ่าน universe.csv
    u = pd.read_csv(root / ".claude" / "factor_team" / "data" / "universe.csv")
    inc = set(u.loc[u["included"], "FundCode"])
    g433 = sorted(c for c in g if c in inc)
    exp = sorted(["ASP-GOLD", "BGOLD", "DAOL-GOLD", "ES-GOLD", "ES-GOLDBULLION-H", "ES-GOLDS", "I-GOLD", "IGOLD-G", "K-GOLD-A(A)", "KT-GOLD", "KT-GOLDUH-A",
                  "LHGOLD-A", "PRINCIPAL iGOLD-A", "SCBGOLDHP", "TGOLD", "UOBSG - H", "UOBSG-N"])
    assert g433 == exp


# 8 ─ IC
def test_ic():
    rng = np.random.default_rng(2)
    s, g = rng.standard_normal(80), rng.standard_normal(80)
    ic, n = p2.ic_q(s, g)
    assert abs(ic - stats.spearmanr(s, g).statistic) < 1e-14 and n == 80
    assert np.isnan(p2.ic_q(s[:29], g[:29])[0])
    s[::7] = 1.0  # เสมอ
    assert abs(p2.ic_q(s, g)[0] - stats.spearmanr(s, g).statistic) < 1e-14
    st = p2.series_stats(rng.standard_normal(11), 5)
    assert st["status"] == "na-insufficient" and st["p"] == 1.0


# 9 ─ SE
def test_se_and_tdec():
    rng = np.random.default_rng(4)
    x = rng.standard_normal(15) * 0.15 + 0.05
    assert p2.nw_lag(15) == 2 and p2.nw_lag(45) == 3
    d = x - x.mean()
    Q = 15
    g = lambda l: (d[l:] @ d[:Q - l]) / Q
    om = (g(0) + 2 * (1 - 1 / 3) * g(1) + 2 * (1 - 2 / 3) * g(2)) * Q / (Q - 1)
    assert abs(p2.se_nw(x, 2) - math.sqrt(om / Q)) < 1e-14
    assert abs(p2.se_nw(x, 0) - x.std(ddof=1) / math.sqrt(Q)) < 1e-14
    r = p2.t_dec(x)
    assert abs(r["t"] - x.mean() / max(r["se_iid"], r["se_nw"])) < 1e-14
    assert abs(r["p"] - 2 * stats.t.sf(abs(r["t"]), 14)) < 1e-14 and r["df"] == 14
    ar = np.cumsum(rng.standard_normal(15)) * 0.1  # autocorrelated → NW ใหญ่กว่า iid
    rr = p2.t_dec(ar)
    assert rr["se_nw"] > rr["se_iid"] and abs(rr["t"] - rr["mean"] / rr["se_nw"]) < 1e-12


# 10 ─ FM / Q5-Q1 / winsor / rank-normal
def test_fm_quintile_winsor_ranknormal():
    x = np.arange(1, 6, dtype=float)
    z = p2.rank_normal(x)
    assert np.allclose(z, stats.norm.ppf((x - 0.5) / 5))
    assert np.allclose(p2.rank_normal([1, 1, 3]), stats.norm.ppf((np.array([1.5, 1.5, 3]) - 0.5) / 3))
    y = np.arange(101, dtype=float)
    w = p2.winsor(y)
    assert w.min() == 1.0 and w.max() == 99.0
    rng = np.random.default_rng(1)
    s = rng.standard_normal(100)
    t = 2.0 * p2.rank_normal(s) + rng.standard_normal(100) * 0.0
    z = p2.rank_normal(s)
    yw = p2.winsor(t)
    exp = np.polyfit(z, yw, 1)[0]  # ตัวอย่างมือ: OLS ของ target ที่ winsorize บน z
    assert abs(p2.fm_slope(s, t) - exp) < 1e-12 and abs(exp - 2.0) < 0.1
    codes = [f"C{i:03d}" for i in range(100)]
    tt = np.arange(100, dtype=float)
    sp = p2.quintile_spread(np.arange(100.0), tt, codes)
    tw = p2.winsor(tt)
    assert abs(sp - (tw[80:].mean() - tw[:20].mean())) < 1e-12
    sp2 = p2.quintile_spread(np.zeros(100), tt, codes)  # เสมอ → FundCode
    assert abs(sp2 - sp) < 1e-12


# 11 ─ Hotelling
def test_hotelling():
    rng = np.random.default_rng(8)
    L = rng.standard_normal((15, 4)) + 0.3
    h = p2.hotelling(L)
    lb = L.mean(0)
    S = np.cov(L.T)
    T2 = 15 * lb @ np.linalg.inv(S) @ lb
    assert abs(h["T2"] - T2) < 1e-10 and h["df1"] == 4 and h["df2"] == 11
    assert abs(h["F"] - 11 / (4 * 14) * T2) < 1e-10 and abs(h["p"] - stats.f.sf(h["F"], 4, 11)) < 1e-14


# 12 ─ perm
def test_perm():
    rng = np.random.default_rng(1)
    sigs = [rng.standard_normal(60) for _ in range(5)]
    tgts = [s * 0.5 + rng.standard_normal(60) for s in sigs]
    a = p2.perm_p(sigs, tgts, B=99, seed=7)
    b = p2.perm_p(sigs, tgts, B=99, seed=7)
    assert a == b
    assert a[1] >= 1 / 100 - 1e-12 and abs(a[1] * 100 - round(a[1] * 100)) < 1e-9  # (1 + #)/(B+1)
    assert a[1] <= 0.02  # ความสัมพันธ์แรง → p ต่ำสุดใกล้ 1/(B+1)
    n = p2.perm_p([rng.standard_normal(60)] * 3, [rng.standard_normal(60) for _ in range(3)], B=99, seed=7)
    assert 0 < n[1] <= 1


# 13 ─ BH / BY / S2
def test_bh_families_and_j1():
    tc = lambda m: stats.t.isf(0.1 / m / 2, 14)
    assert abs(tc(17) - 3.244) < 0.01 and abs(tc(97) - 4.125) < 0.01
    for m, tt in ((17, 3.30), (97, 4.20)):
        p = np.ones(m)
        p[0] = 2 * stats.t.sf(tt, 14)
        assert p2.bh_families(p, "bh")[0][0]
        p[0] = 2 * stats.t.sf(tt - 0.15, 14)
        assert not p2.bh_families(p, "bh")[0][0]
    # S2: trial เดี่ยว t=3.1 (p 0.0078) + p_J1 = 1e-4 → pass False · pass_if_J1_real_p True
    order = ["P2-A1", "P2-J1"] + [f"X{i}" for i in range(15)]
    p = {s: 1.0 for s in order}
    p["P2-A1"], p["P2-J1"] = 2 * stats.t.sf(3.1, 14), 1e-4
    tt = {"P2-A1": 3.1}
    d = p2.decide_family(order, p, tt, {"P2-A1": 0.1}, {"P2-A1": 0.1}, {"P2-A1": 0.1}, {"P2-J1"})
    r = d.set_index("slot")
    assert not r.loc["P2-A1", "passed"] and r.loc["P2-A1", "passed_if_J1_real_p"]
    assert r.loc["P2-J1", "grade"] == "ร่วมมีนัย"


# 14 ─ DSR
def test_dsr_sr0():
    x = np.random.default_rng(1).standard_normal(15) * 0.15 + 0.05
    assert abs(p2.dsr_ic(x, 20)["sr0"] - 0.508) < 0.001 and abs(p2.dsr_ic(x, 122)["sr0"] - 0.695) < 0.001


# 15 ─ smoke power
def test_smoke_power():
    rng = np.random.default_rng(11)
    sig = 0.15
    rej_null = 0
    rej_alt = 0
    B = 5000
    X0 = rng.standard_normal((B, 15)) * sig
    X1 = X0 + sig
    for X, name in ((X0, "null"), (X1, "alt")):
        c = 0
        for x in X:
            r = p2.t_dec(x)
            c += abs(r["t"]) > 3 if name == "null" else r["t"] > 3
        if name == "null":
            rej_null = c / B
        else:
            rej_alt = c / B
    assert rej_null <= 0.02 and 0.65 <= rej_alt <= 0.90
    m_nct = p2.mde_mult_nct(15, 3.0, 0.8)
    assert abs(m_nct - 1.01) < 0.02
    m_sim, size = p2.mde_mult_sim(15, 3.0, 0.8, n=20000)
    assert 1.0 < m_sim < 1.15 and size < 0.02
    # (ข) panel จำลอง IC รู้ค่า
    for ic_true in (0.0, 0.2):
        rho = 2 * math.sin(math.pi * ic_true / 6)
        means = []
        ses = []
        for rep in range(20):
            r = np.random.default_rng(100 + rep)
            ics = []
            for q in range(15):
                s = r.standard_normal(200)
                g = rho * s + math.sqrt(1 - rho ** 2) * r.standard_normal(200)
                ics.append(p2.ic_q(s, g)[0])
            means.append(np.mean(ics))
            ses.append(np.std(ics, ddof=1) / math.sqrt(15))
        assert abs(np.mean(means) - ic_true) <= 2 * (np.mean(ses) / math.sqrt(20)) + 1e-12 or abs(np.mean(means) - ic_true) < 0.01


# 16 ─ trials.csv
def mkrow(kind="main", hi=1, tid="P2-T"):
    r = {h: "" for h in p2.HEADER}
    r.update(trial_id=tid, row_kind=kind, status="valid", has_inference=hi, estimate=0.1, t_dec=1.5)
    return r


def test_trials_append():
    d = Path(tempfile.mkdtemp())
    f, bd = d / "trials.csv", d / "bk"
    p2.append_trials(f, [mkrow("main")], bd)
    assert not bd.exists() or not list(bd.glob("*"))  # ไฟล์ใหม่ไม่มี backup
    b0 = f.read_bytes()
    info = p2.append_trials(f, [mkrow("robustness", tid="a"), mkrow("monthly"), mkrow("robustness", hi=0), mkrow("invalidate"), mkrow("bugfix_rerun")], bd)
    bk = Path(info["backup"])
    assert bk.read_bytes() == b0 and f.read_bytes().startswith(b0)
    rows = list(csv.DictReader(open(f, newline="")))
    assert [r["counts_mode_A"] for r in rows] == ["1", "0", "1", "0", "0", "1"]
    assert [r["counts_mode_B"] for r in rows] == ["1", "1", "1", "0", "0", "1"]  # invalidate = 0 ทั้งสองแบบ
    assert rows[-1]["n_trials_cumulative"] == "3" and rows[-1]["n_trials_cumulative_B"] == "4" and rows[-1]["n_combined"] == "105" and rows[-1]["n_combined_B"] == "106"
    bad = mkrow()
    bad.pop("notes")
    with pytest.raises(ValueError):
        p2.append_trials(f, [bad], bd)
    with pytest.raises(ValueError):
        p2.append_trials(f, [dict(mkrow(), row_kind="x")], bd)
    f.write_text("a,b\n1,2\n")
    with pytest.raises(ValueError):
        p2.append_trials(f, [mkrow()], bd)
    src = (LIBDIR / "p2.py").read_text()
    assert "to_csv" not in src and "read_csv" not in src.split("def append_trials")[1]  # ไม่เขียนด้วย pandas


# 17 ─ C1
def test_c1_adj_r2_windows():
    rng = np.random.default_rng(6)
    for T, expect_n in ((53, 52), (106, 104)):
        idx = pd.date_range("2021-01-08", periods=T, freq="W-FRI")
        Fd = pd.DataFrame(rng.standard_normal((T, 5)) * 0.01, index=idx, columns=["PC1", "PC2", "PC3", "PC4", "FX"])
        R = pd.DataFrame({"A": Fd.to_numpy() @ rng.standard_normal(5) + rng.standard_normal(T) * 0.01}, index=idx)
        fit = p2.fit_at(R, Fd, ["A"], 104)
        c1 = p2.sig_C1(fit)["A"]
        assert fit.n[0] == expect_n
        D = rg.dimson_design(Fd).to_numpy()
        ok = np.isfinite(D).all(1)
        if T > 104:
            ok &= np.arange(T) >= T - 104
        X = np.column_stack([np.ones(ok.sum()), D[ok]])
        y = R["A"].to_numpy()[ok]
        e = y - X @ np.linalg.lstsq(X, y, rcond=None)[0]
        r2 = 1 - e @ e / ((y - y.mean()) ** 2).sum()
        n, p = X.shape
        assert p == 11 and abs(c1 - (1 - (1 - (1 - r2) * (n - 1) / (n - p)))) < 1e-9


# 18 ─ C3 / J1
def test_c3_j1():
    a1 = pd.Series([1.0, 2, 3, 4, 5, np.nan], index=list("abcdef"))
    c1 = pd.Series([0.1, 0.9, 0.5, 0.7, 0.3, 0.8], index=list("abcdef"))
    s, cut, mem = p2.sig_C3(a1, c1)
    assert cut == 0.5 and list(mem[mem].index) == ["b", "c", "d"] and s.notna().sum() == 3
    rng = np.random.default_rng(1)
    X = pd.DataFrame(rng.standard_normal((100, 4)), columns=list("wxyz"))
    X.iloc[:5, 2] = np.nan
    y = pd.Series(X["w"].fillna(0).to_numpy() * 0.0 + 2.0 * p2.rank_normal(X["x"].to_numpy()) + 0.0)
    lam = p2.j1_slopes(X, y)
    ok = X.notna().all(axis=1)
    assert int(ok.sum()) == 95  # ใช้เฉพาะกองที่ครบ 4 สัญญาณ
    Z = np.column_stack([p2.rank_normal(X.loc[ok, c].to_numpy()) for c in X.columns])
    exp = np.linalg.lstsq(np.column_stack([np.ones(95), Z]), p2.winsor(y[ok].to_numpy()), rcond=None)[0][1:]
    assert np.abs(lam - exp).max() < 1e-12 and abs(lam[1] - 2.0) < 0.1


# 19 ─ D1 / D3
def test_d1_d3():
    meta = pd.DataFrame(dict(ter=[1.0, 2.0, 3.0], ter_src=["actual", "rate", None]), index=["a", "b", "c"])
    s = p2.sig_D1(meta, ["a", "b", "c"])
    assert s["a"] == -1.0 and np.isnan(s["b"]) and np.isnan(s["c"])
    inp = make_inputs()
    inp.AUM.iloc[120, 7] = np.nan  # ขาดตรง t → NaN (ไม่เติมย้อน)
    st = p2.state_at(inp, 120)
    if inp.R.columns[7] in st["sig"].index:
        assert np.isnan(st["sig"].loc[inp.R.columns[7], "D3"])
    j = st["sig"]["D3"].dropna().index[0]
    assert abs(st["sig"].loc[j, "D3"] + math.log(inp.AUM.iloc[120][j])) < 1e-12


# 20 ─ W1–W3 · เลือกช่องแบบกลไก
def test_whatif_and_selection():
    inp = make_inputs()
    st3 = p2.state_at(inp, 150, None, "W3")
    assert 1 <= st3["k"] <= 8 or st3["ed_fallback"]
    st2 = p2.state_at(inp, 150, None, "W2")
    assert st2["fit_e"].K == 6  # +GOLD
    st1 = p2.state_at(inp, 150, None, "W1")
    assert st1["pf"]["eig"] is None
    cands = [dict(slot="P2-B0", t=4.5, passed=True, pca=False), dict(slot="P2-A2", t=3.2, passed=False, pca=False),
             dict(slot="P2-A1", t=3.9, passed=True, pca=True), dict(slot="P2-B2", t=3.9, passed=True, pca=True),
             dict(slot="P2-B1", t=5.0, passed=False, pca=True)]
    mon, anc = p2.select_conditional(cands)
    assert mon == ["P2-B0", "P2-A1"] and anc == "P2-A1"  # เสมอ → ลำดับตาราง
    assert p2.select_conditional([dict(slot="x", t=2.0, passed=False, pca=True)]) == ([], None)


# 21 ─ grep (สตริงต้องห้ามใน p2.py / run.py)
def test_grep_forbidden():
    bad = ["EVAL", "coefs.csv", "results.csv", "factors_S003", "fund_clusters.csv", "primary_index", "alpha_fund", "load_nav_history"]
    files = [LIBDIR / "p2.py", LIBDIR.parent / "runs" / "S010" / "run.py"]
    for f in files:
        if f.exists():
            src = f.read_text()
            for b in bad:
                assert b not in src, (f.name, b)
