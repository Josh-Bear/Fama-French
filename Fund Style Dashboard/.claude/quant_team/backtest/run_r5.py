"""run_r5.py — debate รอบ 5 (spec: debate/R5_modeler.md) · สำเนาจาก run_r4.py · แก้ข้อมูลทองด้วย clean_gold_v2 (ผู้ใช้อนุมัติ 2026-10-12: ต่อราคา K-GOLD-C(A) ด้วย K-GOLD-A(A))
STAGE = "d0" → รัน regression + ตัวเลขฐานใหม่ (0 trial) แล้วจบ
รัน: PYTHONPATH=. ./.venv/bin/python .claude/quant_team/backtest/run_r5.py [d0]
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

    # ---- ตัวคูณ overlay ต่อ (offset, qi) ----
    def canary_b(t):
        ms = fs.month_end_points(cal, t, 13)
        assert ms[-1] <= t and len(ms) == 13
        em = np.array([lv["MSCI_EM"].loc[:m].dropna().iloc[-1] for m in ms])
        y = np.array([mac["US10Y"].loc[:m].dropna().iloc[-1] / 100 for m in ms])
        L = [1.0]
        for i in range(1, 13):
            L.append(L[-1] * (1 + y[i - 1] / 12 - 6 * (y[i] - y[i - 1])))
        L = np.array(L)

        def mom(z):
            return (12 * (z[12] / z[11] - 1) + 4 * (z[12] / z[9] - 1) + 2 * (z[12] / z[6] - 1) + (z[12] / z[0] - 1)) / 4
        return int(mom(em) <= 0) + int(mom(L) <= 0)

    def canary_ens(m, forms=(("mom", "THB"), ("mom", "USD"), ("sma", "THB"), ("sma", "USD"))):
        ms = fs.month_end_points(cal, m, 13)
        assert ms[-1] <= m and len(ms) == 13
        emT = np.array([lv["MSCI_EM"].loc[:mi].dropna().iloc[-1] for mi in ms])
        fx = np.array([mac["USDTHB"].loc[:mi].dropna().iloc[-1] for mi in ms])
        em = {"THB": emT, "USD": emT / fx}
        y = np.array([mac["US10Y"].loc[:mi].dropna().iloc[-1] / 100 for mi in ms])
        L = [1.0]
        for i in range(1, 13):
            L.append(L[-1] * (1 + y[i - 1] / 12 - 6 * (y[i] - y[i - 1])))
        L = np.array(L)
        f = {"mom": lambda z: (12 * (z[12] / z[11] - 1) + 4 * (z[12] / z[9] - 1) + 2 * (z[12] / z[6] - 1) + (z[12] / z[0] - 1)) / 4,
             "sma": lambda z: z[12] / z.mean() - 1}
        return float(np.mean([int(f[a](em[c]) <= 0) + int(f[a](L) <= 0) for a, c in forms]))

    olog = []

    def make_xfun(cfg, k, sl, recs):
        Ek = envs[k][0]
        T = CAP75 if cfg.table == "CAP75" else GC75

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
                b = float(np.mean([(canary_ens(mm) if cfg.ens else canary_b(mm)) for mm in ms_s]))
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

    # ---------------- regression รอบ 5 (ค่าฐานใหม่จาก d0 · clean_gold_v2) ----------------
    d0ref = pd.read_csv(os.path.join(RES, "R5_d0_rebaseline.csv")).set_index("model_id")
    for D, tag in ((D42, "M042-ENSDEF(reg)"), (D46, "M046-STACK5(reg)")):
        assert np.allclose([D["sharpe"], D["sh_c2"], D["off0"], D["off1"], D["off2"]],
                           d0ref.loc[tag, ["sharpe", "sh_c2", "off0", "off1", "off2"]].astype(float).to_numpy(), atol=5e-7), tag
    off_pk = plans3(Cfg(canary=True, ens=True, aclr=False, sr3m=1), "regS")
    assert all(a["weights"] == b["weights"] for k in envs for a, b in zip(off_pk[k], p42[k]))
    for j in envs:
        sig = envs[j][0]["sig"]
        for t, kk in zip(sig["t"], sig["k"]):
            if t in set(envs[j][0]["q15"]):
                for kq in envs:
                    assert ksig(envs[kq][0], t) == int(kk), (j, t)
    print("  regression รอบ 5 ผ่าน (ค่าฐาน d0 · ปิดสวิตช์ = M042 · k ข้าม offset ตรงกัน)", flush=True)

    EXPECT = {"M048-ACLR42": {1: {"2023-12-29": (0.25, 1.0), "2024-05-31": (0.5, 1.0), "2025-06-30": (0.25, 1.0)},
                              2: {"2023-12-29": (0.75, 1.0), "2024-03-29": (0.75, 1.0), "2025-06-30": (0.25, 1.0)}},
              "M049-STACK7": {1: {"2023-12-29": (0.25, 0.898), "2024-05-31": (0.5, 1.0), "2025-06-30": (0.25, 0.817)},
                              2: {"2025-06-30": (0.25, 1.0)}}}

    def c0_offs(pk):
        return [ro.win_metrics(r15.sim_cases_x(pk[k], nav_all, envs[k][0]["months"], fee, real, fset=fset, kinds=["c0"])["c0"]["values"], real)["sharpe"]
                for k in envs]

    def finish(tag, pk, base_plans, ncomp):
        x = single(tag, pk)
        x["off_min"] = min(x["off0"], x["off1"], x["off2"])
        x["pass4"] = bool(x["off_min"] >= 0.9)
        x["pass_all"] = bool(x["pass1"] and x["pass2"] and x["pass3"] and x["pass4"])
        x["off_c0"] = "/".join(f"{v:.3f}" for v in c0_offs(pk))
        x["ncomp"] = ncomp
        x["n_aclr"] = "/".join(str(sum(1 for r in aclr_log if r["model"] == tag and r["offset"] == k)) for k in envs)
        x["eq_same_as_base"] = "/".join(str(sum(a == b for a, b in zip(R2.eq_sets([p for p in pk[k] if not p.get("aclr")], fset),
                                                                      R2.eq_sets(base_plans[k], fset)))) for k in envs)
        print(f"     off_min {x['off_min']:.3f} · ผ่านครบ 4 ข้อ {x['pass_all']} · c0 offsets {x['off_c0']} · ALLCLEAR ยิง {x['n_aclr']}", flush=True)
        return x

    def check_fire(tag, pk, base_plans):
        assert sum(1 for r in aclr_log if r["model"] == tag and r["offset"] == 0) == 0, tag
        assert all(a["weights"] == b["weights"] for a, b in zip(pk[0], base_plans[0])), tag
        got = {k: {str(r["m"].date()): (r["x_held"], r["x_new"]) for r in aclr_log if r["model"] == tag and r["offset"] == k} for k in (1, 2)}
        exp = EXPECT.get(tag)
        if exp is None:
            return True
        ok = all(set(got[k]) == set(exp[k]) and all(np.allclose(got[k][d], exp[k][d], atol=1e-3) for d in exp[k]) for k in (1, 2))
        if not ok:
            print(f"   ⚠ วันที่ยิงไม่ตรง spec: ได้ {got} · คาด {exp}", flush=True)
        return ok

    R = {}
    print("[run] M048-ACLR42", flush=True)
    pk = plans3(Cfg(canary=True, ens=True, aclr=True), "M048-ACLR42")
    check_eq(pk, "M048")
    ok48 = check_fire("M048-ACLR42", pk, p42)
    R["M048-ACLR42"] = finish("M048-ACLR42", pk, p42, 3)
    print("[run] M049-STACK7", flush=True)
    pk = plans3(Cfg(vsl=True, canary=True, ens=True, aclr=True), "M049-STACK7")
    check_eq(pk, "M049")
    ok49 = check_fire("M049-STACK7", pk, p46)
    R["M049-STACK7"] = finish("M049-STACK7", pk, p46, 4)
    if not (ok48 and ok49):
        print("REGRESSION (วันที่ยิง) ไม่ตรง spec — หยุด ไม่บันทึก trial")
        pd.DataFrame(aclr_log).to_csv(os.path.join(RES, "R5_aclr_log.csv"), index=False)
        sys.exit(2)
    print("[run] M050-SR3M46", flush=True)
    p50 = plans3(Cfg(vsl=True, canary=True, ens=True, sr3m=3), "M050-SR3M46")
    R["M050-SR3M46"] = finish("M050-SR3M46", p50, p46, 4)
    x50 = R["M050-SR3M46"]
    if x50["pass1"] and x50["pass2"] and not x50["pass4"]:
        print("[run] M051-STACK8 (ตามกติกา)", flush=True)
        pk = plans3(Cfg(vsl=True, canary=True, ens=True, aclr=True, sr3m=3), "M051-STACK8")
        n0 = sum(1 for r in aclr_log if r["model"] == "M051-STACK8" and r["offset"] == 0)
        if n0:
            print(f"   ⚠ ALLCLEAR ยิงที่ offset 0 {n0} ครั้ง (ชุดกองใหม่ — รายงาน ไม่หยุด)", flush=True)
        R["M051-STACK8"] = finish("M051-STACK8", pk, p46, 5)

    cands = [t for t in R if R[t]["pass_all"]]
    if cands:
        win = sorted(cands, key=lambda t: (R[t]["ncomp"], -R[t]["sh_c2"], -R[t]["off_min"]))[0]
        print(f"[ผู้ชนะรอบ 5] {win} (ผ่านครบ 4 ข้อ: {cands})", flush=True)
    else:
        D46["off_min"] = min(D46["off0"], D46["off1"], D46["off2"])
        pool = {**{t: R[t] for t in R if R[t]["pass1"] and R[t]["pass2"] and R[t]["pass3"]}, "M046-STACK5(reg)": D46}
        best = max(pool, key=lambda t: pool[t]["off_min"])
        print(f"[ผู้ชนะรอบ 5] ไม่มีตัวผ่าน · off_min สูงสุด = {best} {pool[best]['off_min']:.4f} (ขาด {0.9 - pool[best]['off_min']:.4f})", flush=True)

    # ---------------- บันทึก ----------------
    pd.DataFrame(aclr_log).to_csv(os.path.join(RES, "R5_aclr_log.csv"), index=False)
    out = pd.DataFrame([{c: v for c, v in x.items() if c not in ("r", "rfm")} for x in [D42, D46, *R.values()]]).set_index("model_id")
    out.to_csv(os.path.join(RES, "R5_results.csv"))
    shutil.copy(TRIALS, os.path.join(TEAM, f"trials.backup_{pd.Timestamp.now():%Y%m%dT%H%M%S}.csv"))
    cols = next(csv.reader(open(TRIALS, encoding="utf-8", newline="")))
    raw = open(TRIALS, "rb").read()
    n = max(int(float(x["n_trials_cumulative"])) for x in csv.DictReader(open(TRIALS, encoding="utf-8", newline="")) if x["n_trials_cumulative"])
    assert n == 85, n
    new = []
    for tag, x in R.items():
        n += 1
        new.append({"model_id": tag, "run_at": pd.Timestamp.now().isoformat(), "spec_file": "debate/R5_modeler.md",
                    "params": "R5 debate · base M042/M046 · clean_gold_v2 (K-GOLD-C(A) spliced with K-GOLD-A(A) from 2024-04-23, user-approved) · " + tag,
                    "period_start": "2022-03-31", "period_end": "2025-12-31",
                    "rf_source": "BOT policy rate daily (TH_POLICY_RATE.csv)", "cost_assumption": "real fees SecFundFee FEEUH (full; FeeData legacy=False; E/F/O separate)",
                    "sharpe": round(x["sharpe"], 4), "cagr": round(x["cagr"], 4), "vol": round(x["vol"], 4), "max_dd": round(x["max_dd"], 4),
                    "turnover": round(x["turn_yr"], 4), "n_trials_cumulative": n, "deflated_sharpe": round(rr.dsr_s(x["r"], x["rfm"], n), 4),
                    "status": "ok", "notes": f"sh_c2={x['sh_c2']:.4f}; off_mean={x['off_mean']:.3f}; off_min={x['off_min']:.3f}; "
                    f"pass1={x['pass1']}; pass2={x['pass2']}; pass3={x['pass3']}; pass4={x['pass4']}"})
    eol = "\r\n" if raw.count(b"\r\n") > raw.count(b"\n") / 2 else "\n"
    buf = io.StringIO()
    csv.writer(buf, lineterminator=eol).writerows([[str(r[c]) for c in cols] for r in new])
    with open(TRIALS, "ab") as f:
        f.write((b"" if raw.endswith(b"\n") else eol.encode()) + buf.getvalue().encode("utf-8"))
    pd.set_option("display.width", 300)
    show = ["sharpe", "cagr", "vol", "max_dd", "sh_c2", "off0", "off1", "off2", "off_mean", "off_min", "off_c0", "n_aclr", "eq_same_as_base",
            "cost_bp_yr", "pass1", "pass2", "pass3", "pass4", "pass_all"]
    print(out[[c for c in show if c in out]].round(4).to_string())
    print(pd.DataFrame(aclr_log).to_string())
    print(f"trials ถึง n = {n} · done {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
