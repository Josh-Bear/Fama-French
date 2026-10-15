"""run_r6.py — M051–M058: CANARY ใช้บอนด์จริง (ETF AGG / IEF) แทนบอนด์จำลองจาก US10Y (spec: specs/M051_canary_real_bond.md)
สำเนาจาก run_r5.py (ใช้ clean_gold_v2) · ไม่แก้ไฟล์เดิม · regression: bond="synth" = ค่าฐาน R5_d0_rebaseline.csv ทุกบิต
รัน: PYTHONPATH=. ./.venv/bin/python .claude/quant_team/backtest/run_r6.py
"""
from __future__ import annotations

import csv
import io
import os
import shutil
import sys
import time
from dataclasses import dataclass

THIS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, THIS)

import numpy as np
import pandas as pd

import common
import fees
import fund_signals as fs
import remeasure_real_rf as rr
import robust_offsets as ro
import run_m010 as r10
import run_m012 as r12
import run_m013 as r13
import run_m015 as r15
import run_m018 as m18
import run_m019 as m19
import run_r1 as r1
import run_r2 as R2
import weighting as wt
import fulluniv_run as fu
from data import msci_index

TEAM = os.path.dirname(THIS)
RES = common.RESULTS_DIR
TRIALS = os.path.join(TEAM, "trials.csv")
BAND = 0.05
STAGE = sys.argv[1] if len(sys.argv) > 1 else "full"
M033_SHARPE, M033_OFFS = 1.2040035525, (1.591009, 0.603307, 1.045082)
GC75 = r13.TABLES["GC75"]
CAP75 = {3: 0.75, 2: 0.75, 1: 0.50, 0: 0.25}
# what-if ตาราง GC (ผู้ใช้ 2026-10-14 · dry run ไม่บันทึก trial) — k = 3/2/1/0
GC_TABLES = {"GC75": GC75, "CAP75": CAP75,
             "GC90": {3: 1.00, 2: 0.90, 1: 0.80, 0: 0.70},
             "GC85": {3: 1.00, 2: 0.85, 1: 0.70, 0: 0.65},
             "GC80": {3: 1.00, 2: 0.80, 1: 0.60, 0: 0.40},
             "FIX57": {3: 0.57, 2: 0.57, 1: 0.57, 0: 0.57}}   # benchmark หุ้น/ทองคงที่ (= สัดส่วนหุ้นเฉลี่ยของ M052) · ไม่ใช่ trial


@dataclass(frozen=True)
class Cfg:
    sigs: tuple = ()          # องค์ประกอบคะแนน: "SR" "NH" "RS" "ID" (ว่าง = อันดับ SR12 เดิม)
    vsl: bool = False
    table: str = "GC75"
    canary: bool = False
    rb2: bool = False
    ens: bool = False
    smooth: int = 1
    vote: bool = False
    defmmf: bool = False
    aclr: bool = False
    sr3m: int = 1
    bond: str = "synth"          # "synth" = จำลองจาก US10Y (เดิม) · "AGG" / "IEF" = ราคา ETF ปรับปันผล


def pctrank(d: dict) -> pd.Series:
    return pd.Series(d, dtype=float).rank(pct=True)


# ---------------- สัญญาณใหม่ (ข้อมูล ≤ t) ----------------
def sig_nh(arr, t):
    if arr is None:
        return np.nan
    d, v = arr
    t_np = np.datetime64(t.date())
    m = (d > t_np - np.timedelta64(364, "D")) & (d <= t_np)
    if m.sum() < 200:
        return np.nan
    return fs._asof(d, v, t_np) / float(v[m].max())


def sig_rs(r, a):
    df = pd.DataFrame({"r": r, "a": a, "al": a.shift(1)}).dropna()
    if len(df) < 40:
        return np.nan
    X = df[["a", "al"]].to_numpy()
    b, *_ = np.linalg.lstsq(X, df["r"].to_numpy(), rcond=None)
    u = pd.Series(df["r"].to_numpy() - X @ b, index=df.index)
    cut = r.index[-4] if len(r) >= 4 else r.index[-1]
    uu = u[u.index < cut]
    sd = u.std(ddof=1)
    return float(uu.sum() / (sd * np.sqrt(len(uu)))) if len(uu) > 1 and sd > 0 else np.nan


def sig_id(arr, t):
    if arr is None:
        return np.nan
    d, v = arr
    a, b = np.datetime64((t - pd.Timedelta(days=365)).date()), np.datetime64((t - pd.Timedelta(days=30)).date())
    m = (d > a) & (d <= b)
    x = v[m]
    if len(x) < 151:
        return np.nan
    rr_ = x[1:] / x[:-1] - 1.0
    p0, p1 = fs._asof(d, v, a), fs._asof(d, v, b)
    if not (p0 == p0 and p1 == p1):
        return np.nan
    pret = p1 / p0 - 1.0
    return float(np.sign(pret) * ((rr_ < 0).sum() - (rr_ > 0).sum()) / len(rr_))


# ---------------- การคัดกอง = R2.select_siw(siw=True) + ranks จากคะแนนใหม่ ----------------
def select_sig(ctx, held, prev_fb, qual, fee, cfg, aux):
    t = ctx["t"]
    H_map = {} if prev_fb else held
    fam_ok = set(qual.index[qual["pass_q1"] & qual["pass_q2"]])
    it = ctx["i_t"][ctx["i_t"]["family"].isin(fam_ok)]
    reps = wt.family_representatives(it, "SR12", held_funds=set(held.values()))
    ranks = wt.rank_families(reps)
    if cfg.sigs:
        sr = pctrank({f: reps[f]["signal"] for f in reps})
        comps = []
        for s in cfg.sigs:
            if s == "SR":
                comps.append(sr)
                continue
            if s == "NH":
                raw = {f: sig_nh(aux["e_arr"].get(reps[f]["FundCode"]), t) for f in reps}
            elif s == "RS":
                raw = {f: sig_rs(ctx["wk"][reps[f]["FundCode"]], aux["acwi_wk"](t)) for f in reps}
            else:
                raw = {f: (-sig_id(aux["e_arr"].get(reps[f]["FundCode"]), t)) for f in reps}
            pr = pctrank(raw)
            comps.append(pr.where(pr.notna(), sr))
        score = sum(comps) / len(comps)
        ranks = wt.rank_families({f: {**reps[f], "signal": float(score[f])} for f in reps})
    if cfg.sr3m > 1:
        ms = fs.month_end_points(aux["cal"], t, cfg.sr3m)
        assert ms[-1] == t and not cfg.sigs
        P = []
        for m in ms:
            cm = ctx if m == t else aux["ctx_by_t"].get(m)
            if cm is None:
                continue
            assert cm["t"] <= t
            sr_m = cm["i_t"].set_index("FundCode")["SR12"]
            assert sr_m.index.is_unique
            P.append(pctrank({f: sr_m.get(reps[f]["FundCode"], np.nan) for f in reps}))
        P = [x.where(x.notna(), P[-1]) for x in P]
        ranks = wt.rank_families({f: {**reps[f], "signal": float(sum(P)[f] / len(P))} for f in reps})
    pool_all = sorted(reps, key=lambda f: ranks[f])
    S_keep = {fam: fc for fam, fc in H_map.items() if fam in reps and ranks[fam] <= r1.POOL and reps[fam]["FundCode"] == fc}
    D = [fc for fc in H_map.values() if fc not in S_keep.values()]

    def cost(c):
        ff = fee.rate(c, "FF", t)
        so = [fee.rate(d, "SO", t) for d in D if fee.amc.get(d, d) == fee.amc.get(c, c)]
        return min(ff, fee.rate(c, "SI", t) + min(so)) if so else ff

    for fam, rep in list(reps.items()):
        if fam in held:
            continue
        g = it[(it["family"] == fam) & (it["SR12"] >= rep["signal"] - r1.EPS)]
        best = sorted(g.itertuples(), key=lambda r: (cost(r.FundCode), -r.SR12, r.FundCode))[0].FundCode
        reps[fam] = {**rep, "FundCode": best}
    pool = [f for f in pool_all if ranks[f] <= r1.POOL]
    S = dict(S_keep)
    if not S and pool:
        S[pool[0]] = reps[pool[0]]["FundCode"]
    while len(S) < r1.N:
        cands = [f for f in pool if f not in S]
        if not cands:
            break
        sc = {}
        for f in cands:
            rh = [r10.rho_adj_pair(ctx["wk"][reps[f]["FundCode"]], ctx["wk"][fc]) for fc in S.values()]
            sc[f] = max(1.0 if np.isnan(x) else x for x in rh)
        s_star = min(sc.values())
        C = [f for f in cands if sc[f] <= s_star + r1.DELTA]
        best = min(C, key=lambda f: (cost(reps[f]["FundCode"]), sc[f], ranks[f]))
        S[best] = reps[best]["FundCode"]
    return {"S": S, "fallback": len(S) < r1.NMIN, "ranks": ranks}


def stream_sig(ctxs, quals, fee, cfg, aux):
    held, prev_fb, sleeves, recs = {}, False, {}, []
    for ctx in ctxs:
        qi = ctx["qi"]
        rec = select_sig(ctx, held, prev_fb, quals[qi], fee, cfg, aux)
        recs.append(rec)
        if rec["fallback"]:
            held, prev_fb = {}, True
            sleeves[qi] = ctx["b0_w"]
            continue
        held, prev_fb = dict(rec["S"]), False
        w, _ = wt.risk_parity_weights(list(rec["S"].values()), ctx["wk"], ctx["vol_map"], method="erc")
        sleeves[qi] = wt.apply_cap(w, r1.CAP)
    return sleeves, recs


# ---------------- overlay = m19.gc_gold_plan + x ใหม่ ----------------
def gc_gold_plan_x(E, X, GS, sleeves, xfun):
    kmap = dict(zip(E["sig"]["t"], E["sig"]["k"]))
    base = []
    for qi, t in enumerate(E["q15"]):
        c = 1.0 - xfun(qi, t, kmap[t])
        w = sleeves[qi]
        wf = {fc: (1.0 - c) * float(v) for fc, v in w.items() if v > 0}
        left = (1.0 - c) * (1.0 - float(w.sum())) if 1.0 - float(w.sum()) > 1e-9 else 0.0
        if c + left > 0:
            wf["__CASH__"] = c + left
        base.append({"t": t, "e": common.execution_date(E["calendar"], t), "weights": wf})
    g1, _ = r15.make_plan_F(base, GS)
    plan = r15.make_plan_F(g1, X["sels"]["FAUM"])[0]
    for p in plan:
        assert abs(sum(p["weights"].values()) - 1) < 1e-9 and "__CASH__" not in p["weights"], p["t"]
    return plan


SPLICE_END = pd.Timestamp("2026-03-31")


def clean_gold_v2(GD):
    """K-GOLD-C(A) (AUM ~47k บาท · กำลังปิด class): NAV ตั้งแต่ 2024-04-23 ผิด (พุ่ง +322% แล้วโผล่ 11.78 = −20% หลอก · หยุดหลัง 2024-05-16)
    → แทนทุกแถวตั้งแต่ 2024-04-23 ด้วย C(2024-04-22) × A(d)/A(2024-04-22) บนวันที่ของ K-GOLD-A(A) ถึง SPLICE_END (สุดข้อมูลที่ sim ใช้) · AUM = 0
    ผู้ใช้อนุมัติ 2026-10-12 ("ต่อราคาด้วย class A") · caller ต้อง assert ว่า gold_sels ไม่เปลี่ยน."""
    nav = GD.nav
    c, a = "K-GOLD-C(A)", "K-GOLD-A(A)"
    cut, t_end = pd.Timestamp("2024-04-22"), nav.loc[nav["FundCode"] == c, "NAVDate"].max()
    assert t_end == pd.Timestamp("2024-05-16"), t_end
    old = (nav["FundCode"] == c) & (nav["NAVDate"] > cut)
    assert old.sum() == 11, old.sum()
    c0 = float(nav.loc[(nav["FundCode"] == c) & (nav["NAVDate"] == cut), "NAV"].iloc[0])
    A = nav[(nav["FundCode"] == a)].set_index("NAVDate")["NAV"]
    a0 = float(A.loc[cut])
    seg = A[(A.index > cut) & (A.index <= t_end)]
    new = pd.DataFrame({"FundCode": c, "NAVDate": seg.index, "NAV": c0 * seg.to_numpy() / a0, "AUM": 0.0, "spike_fixed": True})
    GD.nav = pd.concat([nav[~old], new[nav.columns]], ignore_index=True).sort_values(["FundCode", "NAVDate"]).reset_index(drop=True)
    GD.nav_by_fund = {fc: g.sort_values("NAVDate").set_index("NAVDate")["NAV"] for fc, g in GD.nav.groupby("FundCode")}
    GD.arrays = fs._prep_arrays(GD.nav_by_fund)
    GD.Q = r12.Quality(GD.nav, GD.groups)
    # ราคาสำหรับ sim (ไม่ใช่สัญญาณ): ต่อ C ด้วย A ถึง SPLICE_END เพื่อไม่ให้ตำแหน่งที่ยังถืออยู่หลัง 2024-05-16 ใช้ราคาค้าง
    ext = A[(A.index > cut) & (A.index <= SPLICE_END)]
    old_c = GD.nav_by_fund[c]
    return pd.concat([old_c[old_c.index <= cut], pd.Series(c0 * ext.to_numpy() / a0, index=ext.index)]).sort_index()


def clean_gold_plateau(GD):
    """NAV ผิด: K-GOLD-C(A) กระโดด +322% วันที่ 2024-04-23 แล้วกลับ 2024-05-07 (ค้าง 2 สัปดาห์ — กติกา spike เดิมจับไม่ได้) → ตัด 6 แถว
    ตรวจแล้ว: M019–M033 ไม่เคยถือกองนี้ในช่วงนั้น (plan เท่าเดิมทุกบิต) · แต่ R3 รอบแรก (trials #65–#72) ที่ถือทองมากโดนเต็ม."""
    nav = GD.nav
    bad = (nav["FundCode"] == "K-GOLD-C(A)") & (nav["NAVDate"] >= "2024-04-23") & (nav["NAVDate"] < "2024-05-07")
    assert bad.sum() == 6, bad.sum()
    GD.nav = nav[~bad].reset_index(drop=True)
    GD.nav_by_fund = {fc: g.sort_values("NAVDate").set_index("NAVDate")["NAV"] for fc, g in GD.nav.groupby("FundCode")}
    GD.arrays = fs._prep_arrays(GD.nav_by_fund)
    GD.Q = r12.Quality(GD.nav, GD.groups)


def gc_gold_plan_x_mmf(E, X, GS, sleeves, xfun, xbase):
    """= gc_gold_plan_x ยกเว้นส่วนที่ canary ตัด (x_base − x) ไปกองตลาดเงิน FAUM แทนทอง · ส่วน GC75 ยังไปทองตามกติกา AUM."""
    kmap = dict(zip(E["sig"]["t"], E["sig"]["k"]))
    base, ccan = [], []
    for qi, t in enumerate(E["q15"]):
        x = xfun(qi, t, kmap[t])
        xb = xbase[qi]
        c_gc, c_can = 1.0 - xb, xb - x
        assert c_can >= -1e-12 and abs(c_gc + c_can - (1.0 - x)) < 1e-12
        w = sleeves[qi]
        wf = {fc: x * float(v) for fc, v in w.items() if v > 0}
        left = x * (1.0 - float(w.sum())) if 1.0 - float(w.sum()) > 1e-9 else 0.0
        if c_gc + left > 0:
            wf["__CASH__"] = c_gc + left
        base.append({"t": t, "e": common.execution_date(E["calendar"], t), "weights": wf})
        ccan.append(max(c_can, 0.0))
    g1, _ = r15.make_plan_F(base, GS)
    for p, c in zip(g1, ccan):
        if c > 0:
            p["weights"]["__CASH__"] = p["weights"].get("__CASH__", 0.0) + c
    plan = r15.make_plan_F(g1, X["sels"]["FAUM"])[0]
    for p in plan:
        assert abs(sum(p["weights"].values()) - 1) < 1e-9 and "__CASH__" not in p["weights"], p["t"]
    return plan


def ann_sd(s):
    s = s.dropna()
    return float(s.std(ddof=1) * np.sqrt(52)) if len(s) >= 40 else np.nan


def main():
    t0 = time.time()
    holder, envs = {}, {}
    for k in (0, 1, 2):
        envs[k] = fu.build_env_and_plans(k, holder)
    E = envs[0][0]
    FD = holder["FD"]
    profile = r15.load_profile()
    f_codes = sorted(FD.profile.index[FD.profile["Fund Policy"] == "F"])
    GD = m18.GData(profile, E, f_codes)
    GD0 = m18.GData(profile, E, f_codes)
    clean_gold_plateau(GD0)
    c_sim = clean_gold_v2(GD)
    real = E["real"]
    fee = m18.Fee3(E["fd_sim"], fees.FeeData(f_codes), f_codes, fees.FeeData(GD.codes), GD.codes)
    nav_all = {**E["nav_by_fund"], **FD.nav_by_fund, **GD.nav_by_fund, "K-GOLD-C(A)": c_sim}
    arrays = fs._prep_arrays(nav_all)
    fset = set(FD.codes) | set(GD.codes)
    GS = {k: m18.gold_sels(GD, envs[k][0]) for k in envs}
    GS0 = {k: m18.gold_sels(GD0, envs[k][0]) for k in envs}
    for k in envs:
        assert all(GS[k][q][0] == GS0[k][q][0] for q in range(15)), [(k, q, GS[k][q][0], GS0[k][q][0]) for q in range(15) if GS[k][q][0] != GS0[k][q][0]]
    print("[fix] gold_sels หลังต่อราคา = เดิมทุกไตรมาส ทุก offset", flush=True)
    acwi_arr = fs._prep_arrays({"ACWI": E["acwi"]})
    lv = msci_index.load_country_index()
    mac = pd.read_csv(os.path.join(common.PROJECT_ROOT, "base_data", "MACRO_FACTOR.csv"), parse_dates=["Date"]).set_index("Date").sort_index()
    cal = E["calendar"]
    _aw = {}

    def acwi_wk(t):
        if t not in _aw:
            _aw[t] = fs.QuarterContext(acwi_arr, cal, t).weekly_return_series("ACWI")
        return _aw[t]
    ctx_by_t = {c["t"]: c for k in envs for c in envs[k][0]["ctx_h"]}
    assert len(ctx_by_t) == sum(len(envs[k][0]["ctx_h"]) for k in envs)
    aux = {"e_arr": fs._prep_arrays(E["nav_by_fund"]), "acwi_wk": acwi_wk, "cal": cal, "ctx_by_t": ctx_by_t}

    etf = pd.read_csv(os.path.join(common.PROJECT_ROOT, "base_data", "US_BOND_ETF.csv"), comment="#", parse_dates=["Date"]).set_index("Date").sort_index()

    def bond_line(ms, bond):
        if bond == "synth":
            y = np.array([mac["US10Y"].loc[:m].dropna().iloc[-1] / 100 for m in ms])
            L = [1.0]
            for i in range(1, 13):
                L.append(L[-1] * (1 + y[i - 1] / 12 - 6 * (y[i] - y[i - 1])))
            return np.array(L)
        px = []
        for m in ms:
            s_ = etf[bond].loc[:m].dropna()
            assert len(s_) and (m - s_.index[-1]).days <= 7, (bond, m)
            px.append(float(s_.iloc[-1]))
        return np.array(px)

    # ---- ตัวคูณ overlay ต่อ (offset, qi) ----
    def canary_b(t, bond="synth"):
        ms = fs.month_end_points(cal, t, 13)
        assert ms[-1] <= t and len(ms) == 13
        em = np.array([lv["MSCI_EM"].loc[:m].dropna().iloc[-1] for m in ms])
        L = bond_line(ms, bond)

        def mom(z):
            return (12 * (z[12] / z[11] - 1) + 4 * (z[12] / z[9] - 1) + 2 * (z[12] / z[6] - 1) + (z[12] / z[0] - 1)) / 4
        return int(mom(em) <= 0) + int(mom(L) <= 0)

    def canary_ens(m, forms=(("mom", "THB"), ("mom", "USD"), ("sma", "THB"), ("sma", "USD")), bond="synth"):
        ms = fs.month_end_points(cal, m, 13)
        assert ms[-1] <= m and len(ms) == 13
        emT = np.array([lv["MSCI_EM"].loc[:mi].dropna().iloc[-1] for mi in ms])
        fx = np.array([mac["USDTHB"].loc[:mi].dropna().iloc[-1] for mi in ms])
        em = {"THB": emT, "USD": emT / fx}
        L = bond_line(ms, bond)
        f = {"mom": lambda z: (12 * (z[12] / z[11] - 1) + 4 * (z[12] / z[9] - 1) + 2 * (z[12] / z[6] - 1) + (z[12] / z[0] - 1)) / 4,
             "sma": lambda z: z[12] / z.mean() - 1}
        return float(np.mean([int(f[a](em[c]) <= 0) + int(f[a](L) <= 0) for a, c in forms]))

    olog = []

    def make_xfun(cfg, k, sl, recs):
        Ek = envs[k][0]
        T = GC_TABLES[cfg.table]

        xbase, mv, xq = {}, {}, {}

        def xf(qi, t, kt):
            ctx = Ek["ctx_h"][qi]
            row = {"offset": k, "t": t, "k": kt, "x_gc": GC75[kt]}
            m = 1.0
            sS = sA = sG = np.nan
            if cfg.vsl or cfg.rb2:
                w = sl[qi][sl[qi] > 0]
                w = w / w.sum()
                M = wt.build_weekly_matrix(list(w.index), ctx["wk"]).dropna(how="any")
                if len(M) >= 40 and not recs[qi]["fallback"]:
                    sS = ann_sd(M @ w.to_numpy())
                    sA = ann_sd(acwi_wk(t).reindex(M.index))
            if cfg.vsl and sS == sS and sA == sA:
                m = min(1.0, sA / sS)
            ms_s = fs.month_end_points(cal, t, cfg.smooth)
            assert ms_s[-1] == t and len(ms_s) == cfg.smooth
            if cfg.canary:
                b = float(np.mean([(canary_ens(mm, bond=cfg.bond) if cfg.ens else canary_b(mm, bond=cfg.bond)) for mm in ms_s]))
            else:
                b = 0
            Tm = T[kt] * m
            xc = 1 - b / 2 if cfg.canary else 1.0
            x = max(0.25, min(Tm, (Tm + xc) / 2)) if cfg.vote else max(0.25, min(Tm, xc))
            xbase[qi] = max(0.25, Tm)
            if cfg.rb2:
                g = list(GS[k][qi][0])
                if g and sS == sS:
                    sG = ann_sd(fs.QuarterContext(GD.arrays, cal, t).weekly_return_series(g[0]))
                x = max(0.25, min(GC75[kt], sG / (sS + sG))) if sG == sG else GC75[kt]
            row.update({"sigma_S": sS, "sigma_A": sA, "sigma_G": sG, "b": b, "x": x})
            mv[qi], xq[qi] = m, x
            olog.append(row)
            return x
        xf.xbase, xf.mv, xf.xq = xbase, mv, xq
        return xf

    _ks, _bs, aclr_log = {}, {}, []
    MEND = fs.month_end_points(cal, cal[-1], 10 ** 4)

    def ksig(Ek, m):
        if m not in _ks:
            _ks[m] = int(r13.gc_signals({**Ek, "q16": [m]})["k"].iloc[0])
        return _ks[m]

    def bsig(cfg, m):
        key = (cfg.ens, m)
        if key not in _bs:
            _bs[key] = canary_ens(m) if cfg.ens else canary_b(m)
        return _bs[key]

    def add_allclear(plan, Ek, Xk, GSk, sl, xf, cfg, k, tag):
        q = Ek["q15"]
        out = []
        for qi, p in enumerate(plan):
            assert p["t"] == q[qi]
            out.append(p)
            xh = xf.xq[qi]
            t_nx = q[qi + 1] if qi + 1 < len(q) else None
            mids = [m for m in MEND if m > q[qi] and (t_nx is None or m < t_nx)][:2]
            mids = [m for m in mids if common.execution_date(cal, m) <= Ek["months"][-1]]
            for m in mids:
                if ksig(Ek, m) == 3 and bsig(cfg, m) == 0:
                    xn = max(0.25, GC75[3] * xf.mv[qi])
                    if xn >= xh + 0.25 - 1e-12:
                        w = sl[qi]
                        wf = {fc: xn * float(v) for fc, v in w.items() if v > 0}
                        left = xn * (1 - float(w.sum())) if 1 - float(w.sum()) > 1e-9 else 0.0
                        if (1 - xn) + left > 0:
                            wf["__CASH__"] = (1 - xn) + left
                        e0 = {"t": m, "e": common.execution_date(cal, m), "weights": wf}
                        g1, _ = r15.make_plan_F([e0], {0: GSk[qi]})
                        pe = r15.make_plan_F(g1, {0: Xk["sels"]["FAUM"][qi]})[0][0]
                        assert abs(sum(pe["weights"].values()) - 1) < 1e-9 and "__CASH__" not in pe["weights"]
                        pe["aclr"] = True
                        out.append(pe)
                        aclr_log.append({"model": tag, "offset": k, "qi": qi, "m": m, "x_held": xf.xq[qi], "x_new": xn})
                        xh = xn
        es = [p["e"] for p in out]
        assert all(b > a for a, b in zip(es, es[1:]))
        return out

    def plans3(cfg, tag=""):
        out = {}
        for k, (Ek, _, Xk) in envs.items():
            sl, recs = stream_sig(Ek["ctx_h"], Ek["quals"], fee, cfg, aux)
            n0 = len(olog)
            xf = make_xfun(cfg, k, sl, recs)
            p = (gc_gold_plan_x_mmf(Ek, Xk, GS[k], sl, xf, xf.xbase) if cfg.defmmf else gc_gold_plan_x(Ek, Xk, GS[k], sl, xf))
            for r in olog[n0:]:
                r["model"] = tag
            if cfg.aclr:
                assert cfg.canary and not (cfg.vote or cfg.smooth > 1 or cfg.rb2 or cfg.defmmf)
                p = add_allclear(p, Ek, Xk, GS[k], sl, xf, cfg, k, tag)
            out[k] = R2.band_plan(p, nav_all, arrays, BAND)
        return out

    def sim(plan, kinds, Ex=E):
        return r15.sim_cases_x(plan, nav_all, Ex["months"], fee, real, fset=fset, kinds=kinds, log_full="full" in kinds)

    vals = {}
    REF = {}

    def single(tag, pk):
        s = sim(pk[0], ["c0", "full", "nofront"])
        M = {x: rr.metrics(s[x]["values"], real) for x in ("c0", "full", "nofront")}
        offs = [ro.win_metrics(sim(pk[k], ["full"], envs[k][0])["full"]["values"], real)["sharpe"] for k in (0, 1, 2)]
        r, rfm = M["full"]["r"], M["full"]["rfm"]

        def ex(a, b):
            m = ~((r.index >= a) & (r.index <= b))
            return rr.sharpe_s(r[m], rfm.reindex(r.index)[m])
        v = s["full"]["values"]
        vals[tag] = v
        x = {"model_id": tag, "sharpe": M["full"]["sharpe"], "cagr": M["full"]["cagr"], "vol": M["full"]["vol"], "max_dd": M["full"]["max_dd"],
             "sharpe_nofront": M["nofront"]["sharpe"], "sharpe_c0": M["c0"]["sharpe"], **m18.year_returns(v),
             "sh_exQ222": ex("2022-04-01", "2022-06-30"), "sh_exQ225": ex("2025-04-01", "2025-06-30"),
             "sharpe_2022": M["full"]["sharpe_2022"], "sharpe_2307_2512": M["full"]["sharpe_2307_2512"],
             "cost_bp_yr": s["full"]["cost_bp_yr"], "turn_yr": s["full"]["turn_yr"], "off0": offs[0], "off1": offs[1], "off2": offs[2],
             "off_mean": float(np.mean(offs)),
             "x_mean": float(np.mean([sum(w for f, w in p["weights"].items() if f not in fset) for p in pk[0]])),
             "gold_mean": float(np.mean([sum(w for f, w in p["weights"].items() if f in set(GD.codes)) for p in pk[0]])),
             "r": r, "rfm": rfm}
        r0 = REF.get("r", r)
        assert r.index.equals(r0.index)
        mask = (r.index >= "2025-01-01") & (r.index <= "2025-03-31")
        assert mask.sum() == 3
        r2 = r.copy()
        r2[mask] = r0[mask]
        x["sh_c2"] = rr.sharpe_s(r2, rfm.reindex(r2.index))
        x["sh_exQ125"] = ex("2025-01-01", "2025-03-31")
        x["pass1"], x["pass2"], x["pass3"] = bool(x["sharpe"] > 1.4), bool(x["sh_c2"] >= 1.3), bool(x["off_mean"] >= 1.2)
        x["pass_all"] = x["pass1"] and x["pass2"] and x["pass3"]
        x["d_vs_M033"] = x["sharpe"] - M033_SHARPE
        x["pass_1p4"] = bool(x["sharpe"] > 1.4)
        print(f"   {tag}: Sharpe {x['sharpe']:.4f} · CAGR {x['cagr']:.2%} · vol {x['vol']:.2%} · DD {x['max_dd']:.2%} · exQ2'22 {x['sh_exQ222']:.3f} · "
              f"c2 {x['sh_c2']:.4f} · off {offs[0]:.3f}/{offs[1]:.3f}/{offs[2]:.3f} mean {x['off_mean']:.3f} · ผ่าน {x['pass_all']} · x̄ {x['x_mean']:.2f} ทอง {x['gold_mean']:.2f}", flush=True)
        return x

    # ---------------- regression ----------------
    print("[reg] ฐาน = M033-STACK", flush=True)
    ref = {}
    for k, (Ek, _, Xk) in envs.items():
        sl, _ = R2.stream_siw(Ek["ctx_h"], Ek["quals"], fee, True)
        ref[k] = R2.band_plan(m19.gc_gold_plan(Ek, Xk, GS[k], sl), nav_all, arrays, BAND)
    base = plans3(Cfg(), "M033")
    srreg = plans3(Cfg(sigs=("SR",)), "reg")
    for k in envs:
        for a, b, c in zip(ref[k], base[k], srreg[k]):
            assert a["weights"] == b["weights"] == c["weights"], (k, a["t"])
    B = single("M033-STACK(reg)", base)
    assert abs(B["sharpe"] - M033_SHARPE) < 5e-7 and np.allclose([B["off0"], B["off1"], B["off2"]], M033_OFFS, atol=5e-5)
    eq_base = {k: R2.eq_sets(base[k], fset) for k in envs}
    print("  regression ผ่าน", flush=True)
    REF["r"] = B["r"]
    assert np.allclose(B["rfm"], B["rfm"])

    # ---------------- regression รอบ 4 + D0 ----------------
    def check_eq(pk, tag):
        for k in envs:
            assert R2.eq_sets([p for p in pk[k] if not p.get("aclr")], fset) == eq_base[k], (tag, k)

    p36 = plans3(Cfg(canary=True), "M036")
    p41 = plans3(Cfg(vsl=True, canary=True), "M041")
    p34 = plans3(Cfg(vsl=True), "M034")
    check_eq(p36, "M036"); check_eq(p41, "M041")
    D36 = single("M036-CANARY(reg)", p36)
    D41 = single("M041-STACK(reg)", p41)
    D34 = single("M034-VSL(reg)", p34)
    assert abs(D36["sharpe"] - 1.4952624) < 5e-7 and abs(D36["off0"] - 1.858177) < 5e-5, D36["sharpe"]
    assert abs(D36["sh_c2"] - 1.2643) < 5e-5, D36["sh_c2"]
    assert abs(D41["sharpe"] - 1.5324842) < 5e-7 and abs(D41["sh_c2"] - 1.2924) < 5e-5, (D41["sharpe"], D41["sh_c2"])
    # ens ที่จำกัดเหลือ (mom, THB) = canary_b · smooth=1 → ms_s == [t] (assert ใน xf) · vote/defmmf ปิด = เส้นทางเดิม (p36 ผ่านแล้ว)
    for k, (Ek, _, _) in envs.items():
        for t in Ek["q15"]:
            assert canary_ens(t, (("mom", "THB"),)) == canary_b(t), (k, t)
    print("  regression รอบ 4 ผ่าน (M036 · M041 · ens(mom,THB)=canary_b)", flush=True)
    p42 = plans3(Cfg(canary=True, ens=True), "M042")
    p46 = plans3(Cfg(vsl=True, canary=True, ens=True), "M046")
    check_eq(p42, "M042"); check_eq(p46, "M046")
    D42 = single("M042-ENSDEF(reg)", p42)
    D46 = single("M046-STACK5(reg)", p46)
    assert abs(D42["sharpe"] - 1.5471) < 5e-5 and abs(D46["sharpe"] - 1.5874) < 5e-5, (D42["sharpe"], D46["sharpe"])
    if STAGE == "d0":
        d0 = pd.DataFrame([{c: v for c, v in x.items() if c not in ("r", "rfm")} for x in (B, D34, D36, D41, D42, D46)]).set_index("model_id")
        d0.to_csv(os.path.join(RES, "R5_d0_rebaseline.csv"))
        pd.set_option("display.width", 250)
        print(d0[["sharpe", "cagr", "max_dd", "sh_c2", "off0", "off1", "off2", "off_mean", "cost_bp_yr"]].round(4).to_string())
        print(f"D0 done (0 trial) {time.time() - t0:.0f}s")
        return
    print("[D0] sh_c2: " + " · ".join(f"{d['model_id']} {d['sh_c2']:.4f}" for d in (B, D34, D36, D41)), flush=True)

    def bench_and_whatif():
        """(1) benchmark หุ้นแบบ M033 57% + ทอง 43% คงที่ (ไม่ใช่ trial) · (2) บันทึก what-if ตาราง GC 6 แบบเป็น trials #97–#102
        (ผู้ใช้สั่ง 2026-10-14 ตามรีวิวรายงาน M052: ทุกการทดสอบบนข้อมูลชุดเดิมต้องนับเข้า DSR)."""
        res = {}
        res["BENCH-M033-FIX57"] = single("BENCH M033 หุ้น 57% + ทอง 43% คงที่", plans3(Cfg(table="FIX57"), "bench"))
        res["M052 (อ้างอิง)"] = single("M052", plans3(Cfg(vsl=True, canary=True, bond="AGG"), "bench52"))
        res["M033 GC75 (อ้างอิง)"] = single("M033", plans3(Cfg(), "bench33"))
        assert abs(res["M052 (อ้างอิง)"]["sharpe"] - 1.5324842) < 5e-7 and abs(res["M033 GC75 (อ้างอิง)"]["sharpe"] - 1.2040036) < 5e-7
        IDS = {("M052", "GC90"): "M059-M052-GC90", ("M052", "GC85"): "M060-M052-GC85", ("M052", "GC80"): "M061-M052-GC80",
               ("M019", "GC90"): "M062-M019-GC90", ("M019", "GC85"): "M063-M019-GC85", ("M019", "GC80"): "M064-M019-GC80"}
        trials = {}
        for name in ("GC90", "GC85", "GC80"):
            T = GC_TABLES[name]
            trials[IDS[("M052", name)]] = single(f"M052 · {name}", plans3(Cfg(vsl=True, canary=True, bond="AGG", table=name), "wi52"))
            pk = {}
            for k, (Ek, _, Xk) in envs.items():
                sl, _ = m19.stream_lc(Ek["ctx_h"], Ek["quals"], 9, False)
                pk[k] = gc_gold_plan_x(Ek, Xk, GS[k], sl, lambda qi, t, kk, T=T: T[kk])
            trials[IDS[("M019", name)]] = single(f"M019 · {name}", pk)
        dry = pd.read_csv(os.path.join(RES, "DRY_gc_tables.csv"))
        for tag, x in trials.items():                     # = ผล dry run เดิมทุกบิต
            mdl, tb = tag.split("-")[1], tag.split("-")[2]
            assert abs(dry.query("model == @mdl and table == @tb")["sharpe"].iloc[0] - x["sharpe"]) < 1e-9, tag
        cols_out = ["sharpe", "cagr", "vol", "max_dd", "sh_c2", "off0", "off1", "off2", "off_mean", "cost_bp_yr", "x_mean", "gold_mean",
                    "y2022", "y2023", "y2024", "y2025"]
        B = pd.DataFrame({k: {c: v[c] for c in cols_out} for k, v in res.items()}).T
        B.to_csv(os.path.join(RES, "BENCH_fixed_mix.csv"))
        pd.set_option("display.width", 300)
        print(B.round(4).to_string())
        shutil.copy(TRIALS, os.path.join(TEAM, f"trials.backup_{pd.Timestamp.now():%Y%m%dT%H%M%S}.csv"))
        cols = next(csv.reader(open(TRIALS, encoding="utf-8", newline="")))
        raw = open(TRIALS, "rb").read()
        n = max(int(float(r["n_trials_cumulative"])) for r in csv.DictReader(open(TRIALS, encoding="utf-8", newline="")) if r["n_trials_cumulative"])
        assert n == 96, n
        new = []
        for tag, x in trials.items():
            n += 1
            tb = tag.split("-")[2]
            new.append({"model_id": tag, "run_at": pd.Timestamp.now().isoformat(), "spec_file": "reports/M052_portfolio_logic.md (what-if GC)",
                        "params": f"{tag.split('-')[1]} with GC table {tb} k3/2/1/0 = " + "/".join(f"{GC_TABLES[tb][k]:.2f}" for k in (3, 2, 1, 0))
                                  + " · clean_gold_v2 · first run 2026-10-14 as dry run (DRY_gc_tables.csv), recorded on review",
                        "period_start": "2022-03-31", "period_end": "2025-12-31",
                        "rf_source": "BOT policy rate daily (TH_POLICY_RATE.csv)", "cost_assumption": "real fees SecFundFee FEEUH (full; FeeData legacy=False; E/F/O separate)",
                        "sharpe": round(x["sharpe"], 4), "cagr": round(x["cagr"], 4), "vol": round(x["vol"], 4), "max_dd": round(x["max_dd"], 4),
                        "turnover": round(x["turn_yr"], 4), "n_trials_cumulative": n, "deflated_sharpe": round(rr.dsr_s(x["r"], x["rfm"], n), 4),
                        "status": "ok", "notes": f"WHAT-IF GC table; sh_c2={x['sh_c2']:.4f}; off_mean={x['off_mean']:.3f}"})
        eol = "\r\n" if raw.count(b"\r\n") > raw.count(b"\n") / 2 else "\n"
        buf = io.StringIO()
        csv.writer(buf, lineterminator=eol).writerows([[str(r[c]) for c in cols] for r in new])
        with open(TRIALS, "ab") as f:
            f.write((b"" if raw.endswith(b"\n") else eol.encode()) + buf.getvalue().encode("utf-8"))
        print(f"trials ถึง n = {n}: " + ", ".join(trials))

    def gc_dry():
        """what-if ตาราง GC บน M052 และ M019 · ไม่บันทึก trials · M019 = stream_lc + gc_gold_plan_x (ไม่มี FEE0/SIW/BAND5/CANARY/VSL)."""
        rows = []
        for name in ("GC75", "GC90", "GC85", "GC80"):
            T = GC_TABLES[name]
            x52 = single(f"M052 · {name}", plans3(Cfg(vsl=True, canary=True, bond="AGG", table=name), "gcdry"))
            pk = {}
            for k, (Ek, _, Xk) in envs.items():
                sl, _ = m19.stream_lc(Ek["ctx_h"], Ek["quals"], 9, False)
                pk[k] = gc_gold_plan_x(Ek, Xk, GS[k], sl, lambda qi, t, kk, T=T: T[kk])
            x19 = single(f"M019 · {name}", pk)
            for model, x in (("M052", x52), ("M019", x19)):
                rows.append({"model": model, "table": name, "x_k3/2/1/0": "/".join(f"{T[k]:.0%}" for k in (3, 2, 1, 0)),
                             **{c: x[c] for c in ("sharpe", "cagr", "vol", "max_dd", "sh_c2", "off0", "off1", "off2", "off_mean",
                                                   "cost_bp_yr", "x_mean", "gold_mean", "y2022", "y2023", "y2024", "y2025")}})
        D = pd.DataFrame(rows)
        assert abs(D.query("model == 'M052' and table == 'GC75'")["sharpe"].iloc[0] - 1.5324842) < 5e-7
        assert abs(D.query("model == 'M019' and table == 'GC75'")["sharpe"].iloc[0] - 1.0980982) < 5e-7
        D.to_csv(os.path.join(RES, "DRY_gc_tables.csv"), index=False)
        pd.set_option("display.width", 300)
        print(D.round(4).to_string(index=False))

    def export_m052():
        """input หน้า 11 (M052 = M041 + บอนด์ AGG · offset 0) → base_data/reference/m052_frontier_*.csv (ไม่ใช่ trial)."""
        import frontier_export as fx
        import data_access
        from analysis import gc75_frontier as gf
        tag = "M052-STACK-AGG"
        n0 = len(olog)
        pk = plans3(Cfg(vsl=True, canary=True, bond="AGG"), "M052export")
        plan = pk[0]
        x = single(tag + "(export)", pk)
        ref = pd.read_csv(os.path.join(RES, "R6_results.csv")).set_index("model_id").loc[tag]
        assert abs(x["sharpe"] - float(ref["sharpe"])) < 5e-7 and abs(x["off1"] - float(ref["off1"])) < 5e-7, (x["sharpe"], ref["sharpe"])
        sig = {pd.Timestamp(r["t"]): r for r in olog[n0:] if r.get("offset") == 0 and r.get("model") == "M052export"}
        Xk = envs[0][2]

        def info(qi, f, kind):
            if kind == "E":
                it = E["ctx_h"][qi]["i_t"].set_index("FundCode")
                return str(it.loc[f, "family"]), float(it.loc[f, "SR12"]), np.nan
            tab = GS[0][qi][2] if kind == "G" else Xk["sels"]["FAUM"][qi][2]
            return "", float(tab.set_index("FundCode").loc[f, "SR12p"]), np.nan

        def extra(qi):
            r = sig[E["q15"][qi]]
            vsl = min(1.0, r["sigma_A"] / r["sigma_S"]) if r["sigma_S"] == r["sigma_S"] and r["sigma_A"] == r["sigma_A"] else 1.0
            return {"gc_k": int(r["k"]), "x_gc": r["x_gc"], "canary_b": r["b"], "vsl_mult": vsl, "x_model": r["x"]}

        H, W = fx.holdings_weekly(plan, E, set(FD.codes), set(GD.codes), FD, GD, info, extra)
        eqx = H[H["kind"] == "E"].groupby("t")["weight"].sum()
        assert np.allclose(eqx.values, H.groupby("t")["x_model"].first().values, atol=0.15), "สัดส่วนหุ้นห่างจาก x ของโมเดลเกิน drift ของ BAND5"
        REF = os.path.join(common.PROJECT_ROOT, "base_data", "reference")
        src = ("ที่มา: .claude/quant_team/backtest/run_r6.py export52 · M052-STACK-AGG = M033 (FEE0+SIW+BAND5) + CANARY (MSCI EM + AGG) + VSL · "
               "universe เต็ม · offset 0 · clean_gold_v2")
        title = "input efficient frontier หน้า 11 — M052 · ไฟล์อ้างอิงคงที่ (ห้ามแก้มือ)"
        fx.write_reference(os.path.join(REF, "m052_frontier_holdings.csv"), [title, src], H)
        fx.write_reference(os.path.join(REF, "m052_frontier_weekly.csv"), [title, src], W)
        d = data_access.load_m052_frontier()
        R_, chain = fx.realized(d["holdings"], d["weekly"], plan, nav_all, fee, E["rate"], rr.PE, gf.frontier_case, use_held_weights=True)
        v = sim(plan, ["full"])["full"]["values"]
        growth = float(v.loc[rr.PE] / v.iloc[0])
        print(f"REGRESSION ผลจริง M052: ต่อ Model ทุกไตรมาส {chain:.10f} · sim {growth:.10f}", flush=True)
        assert abs(chain / growth - 1) < 1e-9
        fx.write_reference(os.path.join(REF, "m052_frontier_realized.csv"),
                           ["ผลที่เกิดขึ้นจริงของ MVP / max Sharpe / Model Portfolio หน้า 11 (M052) — ไฟล์อ้างอิงคงที่ (ห้ามแก้มือ)",
                            src + " · ต้นทุน = ค่าธรรมเนียมจริงจากพอร์ต M052 ไตรมาสก่อน · buy-and-hold · Q / 1Y (ตัดที่ 2025-12-31)"], R_)
        print(H.groupby("t").agg(x=("x_model", "first"), k=("gc_k", "first"), b=("canary_b", "first"), vsl=("vsl_mult", "first")).round(3).to_string())
        # ---- เส้น/ตัวเลขสำหรับหน้า 9 ส่วนที่ 2 (export_top3.py อ่านไปรวม) · 3 กรณีต้นทุนแบบเดียวกับ TOP3 ----
        n_tr = int(pd.read_csv(TRIALS)["n_trials_cumulative"].max())
        s3 = sim(plan, ["full", "nofront", "flat"])
        curves, mets = [], []
        for c in ("full", "nofront", "flat"):
            v = s3[c]["values"]
            v = v[v.index <= rr.PE]
            m_ = rr.metrics(v, real)
            lo, hi = rr.boot_ci(m_["r"], m_["rfm"])
            curves += [("M052", c, d.date().isoformat(), float(val)) for d, val in (v / v.iloc[0]).items()]
            mets.append({"series": "M052", "case": c, "sharpe": m_["sharpe"], "cagr": m_["cagr"], "vol": m_["vol"], "max_dd": m_["max_dd"],
                         "dsr": rr.dsr_s(m_["r"], m_["rfm"], n_tr), "ci_lo": lo, "ci_hi": hi, "cost_pct_yr": s3[c]["cost_bp_yr"] / 100.0,
                         "turnover_yr": s3[c]["turn_yr"], "n_months": m_["n_months"], "n_trials": n_tr})
        assert abs(mets[0]["sharpe"] - float(ref["sharpe"])) < 5e-7
        pd.DataFrame(curves, columns=["series", "case", "date", "value"]).to_csv(os.path.join(RES, "EXPORT_m052_curves.csv"), index=False)
        pd.DataFrame(mets).to_csv(os.path.join(RES, "EXPORT_m052_metrics.csv"), index=False)
        print(f"EXPORT_m052_* (n_trials {n_tr}):\n" + pd.DataFrame(mets).round(4).to_string(index=False))

    # ---------------- regression: bond="synth" = ค่าฐาน R5 d0 (clean_gold_v2) ทุกบิต ----------------
    d0ref = pd.read_csv(os.path.join(RES, "R5_d0_rebaseline.csv")).set_index("model_id")
    BASE = {"M036": (D36, "M036-CANARY(reg)"), "M041": (D41, "M041-STACK(reg)"), "M042": (D42, "M042-ENSDEF(reg)"), "M046": (D46, "M046-STACK5(reg)")}
    for _, (D, tag) in BASE.items():
        assert np.allclose([D["sharpe"], D["sh_c2"], D["off0"], D["off1"], D["off2"]],
                           d0ref.loc[tag, ["sharpe", "sh_c2", "off0", "off1", "off2"]].astype(float).to_numpy(), atol=5e-7), tag
    print("  regression ผ่าน: บอนด์จำลอง = ค่าฐาน R5 (M036 · M041 · M042 · M046)", flush=True)

    if STAGE == "bench":
        bench_and_whatif()
        return

    if STAGE == "gcdry":
        gc_dry()
        return

    if STAGE == "export52":
        export_m052()
        return

    # ---------------- สัญญาณ b ต่อไตรมาส (offset 0) ----------------
    blog = []
    for t in E["q15"]:
        row = {"t": t.date()}
        for bond in ("synth", "AGG", "IEF"):
            row[f"b_{bond}"] = canary_b(t, bond=bond)
            row[f"bens_{bond}"] = canary_ens(t, bond=bond)
            ms = fs.month_end_points(cal, t, 13)
            L = bond_line(ms, bond)
            row[f"mom_{bond}"] = (12 * (L[12] / L[11] - 1) + 4 * (L[12] / L[9] - 1) + 2 * (L[12] / L[6] - 1) + (L[12] / L[0] - 1)) / 4
        blog.append(row)
    BL = pd.DataFrame(blog)
    BL.to_csv(os.path.join(RES, "R6_bond_signals.csv"), index=False)
    print("[signals offset 0]\n" + BL.round(4).to_string(index=False), flush=True)

    # ---------------- runs ----------------
    SPEC = [("M051-CANARY-AGG", "M036", Cfg(canary=True, bond="AGG")), ("M052-STACK-AGG", "M041", Cfg(vsl=True, canary=True, bond="AGG")),
            ("M053-ENS-AGG", "M042", Cfg(canary=True, ens=True, bond="AGG")), ("M054-STACK5-AGG", "M046", Cfg(vsl=True, canary=True, ens=True, bond="AGG")),
            ("M055-CANARY-IEF", "M036", Cfg(canary=True, bond="IEF")), ("M056-STACK-IEF", "M041", Cfg(vsl=True, canary=True, bond="IEF")),
            ("M057-ENS-IEF", "M042", Cfg(canary=True, ens=True, bond="IEF")), ("M058-STACK5-IEF", "M046", Cfg(vsl=True, canary=True, ens=True, bond="IEF"))]
    R = {}
    for tag, base, cfg in SPEC:
        print(f"[run] {tag} (ฐาน {base})", flush=True)
        pk = plans3(cfg, tag)
        check_eq(pk, tag)
        x = single(tag, pk)
        b0 = BASE[base][0]
        x["base"] = base
        x["d_sharpe_vs_synth"] = x["sharpe"] - b0["sharpe"]
        x["d_offmean_vs_synth"] = x["off_mean"] - b0["off_mean"]
        x["role"] = "หลัก" if tag.endswith("AGG") else "sensitivity"
        R[tag] = x

    # ---------------- บันทึก ----------------
    rows = [{"model_id": f"{k} (บอนด์จำลอง)", **{c: v for c, v in BASE[k][0].items() if c not in ("r", "rfm", "model_id")}} for k in BASE]
    rows += [{c: v for c, v in x.items() if c not in ("r", "rfm")} for x in R.values()]
    out = pd.DataFrame(rows).set_index("model_id")
    out.to_csv(os.path.join(RES, "R6_results.csv"))
    shutil.copy(TRIALS, os.path.join(TEAM, f"trials.backup_{pd.Timestamp.now():%Y%m%dT%H%M%S}.csv"))
    cols = next(csv.reader(open(TRIALS, encoding="utf-8", newline="")))
    raw = open(TRIALS, "rb").read()
    n = max(int(float(x["n_trials_cumulative"])) for x in csv.DictReader(open(TRIALS, encoding="utf-8", newline="")) if x["n_trials_cumulative"])
    assert n == 88, n
    new = []
    for tag, x in R.items():
        n += 1
        new.append({"model_id": tag, "run_at": pd.Timestamp.now().isoformat(), "spec_file": "specs/M051_canary_real_bond.md",
                    "params": f"{x['base']} with CANARY bond leg = {'AGG' if tag.endswith('AGG') else 'IEF'} ETF adjusted close (US_BOND_ETF.csv) instead of US10Y synthetic · clean_gold_v2",
                    "period_start": "2022-03-31", "period_end": "2025-12-31",
                    "rf_source": "BOT policy rate daily (TH_POLICY_RATE.csv)", "cost_assumption": "real fees SecFundFee FEEUH (full; FeeData legacy=False; E/F/O separate)",
                    "sharpe": round(x["sharpe"], 4), "cagr": round(x["cagr"], 4), "vol": round(x["vol"], 4), "max_dd": round(x["max_dd"], 4),
                    "turnover": round(x["turn_yr"], 4), "n_trials_cumulative": n, "deflated_sharpe": round(rr.dsr_s(x["r"], x["rfm"], n), 4),
                    "status": "ok", "notes": ("SENSITIVITY (IEF); " if x["role"] != "หลัก" else "")
                    + f"sh_c2={x['sh_c2']:.4f}; off_mean={x['off_mean']:.3f}; d_vs_synth={x['d_sharpe_vs_synth']:+.3f}"})
    eol = "\r\n" if raw.count(b"\r\n") > raw.count(b"\n") / 2 else "\n"
    buf = io.StringIO()
    csv.writer(buf, lineterminator=eol).writerows([[str(r[c]) for c in cols] for r in new])
    with open(TRIALS, "ab") as f:
        f.write((b"" if raw.endswith(b"\n") else eol.encode()) + buf.getvalue().encode("utf-8"))
    pd.set_option("display.width", 300)
    show = ["sharpe", "cagr", "vol", "max_dd", "sh_c2", "off0", "off1", "off2", "off_mean", "cost_bp_yr", "y2022", "y2023", "y2024", "y2025",
            "d_sharpe_vs_synth", "d_offmean_vs_synth"]
    print(out[[c for c in show if c in out]].round(4).to_string())
    print(f"trials ถึง n = {n} · done {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
