"""run_r4.py — debate รอบ 4 (spec: debate/R4_modeler.md §2–§3): ทำ CANARY ให้ทนทาน · M042-ENSDEF · M043-VOTE · M044-SMOOTH3 · M045-DEFMMF (sensitivity)
· M046-STACK5 (VSL+ENSDEF) · M047-STACK6 (มีเงื่อนไข) · D0 sh_c2 ของ M033/M034/M036/M041 · สำเนาจาก run_r3.py (ไม่แก้ไฟล์เดิม) · ใช้ clean_gold_plateau เสมอ
รัน: PYTHONPATH=. ./.venv/bin/python .claude/quant_team/backtest/run_r4.py
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
    clean_gold_plateau(GD)
    real = E["real"]
    fee = m18.Fee3(E["fd_sim"], fees.FeeData(f_codes), f_codes, fees.FeeData(GD.codes), GD.codes)
    nav_all = {**E["nav_by_fund"], **FD.nav_by_fund, **GD.nav_by_fund}
    arrays = fs._prep_arrays(nav_all)
    fset = set(FD.codes) | set(GD.codes)
    GS = {k: m18.gold_sels(GD, envs[k][0]) for k in envs}
    acwi_arr = fs._prep_arrays({"ACWI": E["acwi"]})
    lv = msci_index.load_country_index()
    mac = pd.read_csv(os.path.join(common.PROJECT_ROOT, "base_data", "MACRO_FACTOR.csv"), parse_dates=["Date"]).set_index("Date").sort_index()
    cal = E["calendar"]
    _aw = {}

    def acwi_wk(t):
        if t not in _aw:
            _aw[t] = fs.QuarterContext(acwi_arr, cal, t).weekly_return_series("ACWI")
        return _aw[t]
    aux = {"e_arr": fs._prep_arrays(E["nav_by_fund"]), "acwi_wk": acwi_wk}

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

        xbase = {}

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
            olog.append(row)
            return x
        xf.xbase = xbase
        return xf

    def plans3(cfg, tag=""):
        out = {}
        for k, (Ek, _, Xk) in envs.items():
            sl, recs = stream_sig(Ek["ctx_h"], Ek["quals"], fee, cfg, aux)
            n0 = len(olog)
            xf = make_xfun(cfg, k, sl, recs)
            p = (gc_gold_plan_x_mmf(Ek, Xk, GS[k], sl, xf, xf.xbase) if cfg.defmmf else gc_gold_plan_x(Ek, Xk, GS[k], sl, xf))
            for r in olog[n0:]:
                r["model"] = tag
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
            assert R2.eq_sets(pk[k], fset) == eq_base[k], (tag, k)

    p36 = plans3(Cfg(canary=True), "M036")
    p41 = plans3(Cfg(vsl=True, canary=True), "M041")
    p34 = plans3(Cfg(vsl=True), "M034")
    check_eq(p36, "M036"); check_eq(p41, "M041")
    D36 = single("M036-CANARY(reg)", p36)
    D41 = single("M041-STACK(reg)", p41)
    D34 = single("M034-VSL(reg)", p34)
    assert abs(D36["sharpe"] - 1.4952624) < 5e-7 and np.allclose([D36["off0"], D36["off1"], D36["off2"]], (1.858177, 0.807576, 1.139239), atol=5e-5), D36["sharpe"]
    assert abs(D36["sh_c2"] - 1.2643) < 5e-5, D36["sh_c2"]
    assert abs(D41["sharpe"] - 1.5324842) < 5e-7 and abs(D41["sh_c2"] - 1.2924) < 5e-5, (D41["sharpe"], D41["sh_c2"])
    # ens ที่จำกัดเหลือ (mom, THB) = canary_b · smooth=1 → ms_s == [t] (assert ใน xf) · vote/defmmf ปิด = เส้นทางเดิม (p36 ผ่านแล้ว)
    for k, (Ek, _, _) in envs.items():
        for t in Ek["q15"]:
            assert canary_ens(t, (("mom", "THB"),)) == canary_b(t), (k, t)
    print("  regression รอบ 4 ผ่าน (M036 · M041 · ens(mom,THB)=canary_b)", flush=True)
    print("[D0] sh_c2: " + " · ".join(f"{d['model_id']} {d['sh_c2']:.4f}" for d in (B, D34, D36, D41)), flush=True)

    # ---------------- candidates ----------------
    specs = [("M042-ENSDEF", Cfg(canary=True, ens=True), "single"), ("M043-VOTE", Cfg(canary=True, vote=True), "single"),
             ("M044-SMOOTH3", Cfg(canary=True, smooth=3), "single"), ("M045-DEFMMF", Cfg(canary=True, defmmf=True), "sens"),
             ("M046-STACK5", Cfg(vsl=True, canary=True, ens=True), "stack")]
    R, ncomp = {}, {"M042-ENSDEF": 2, "M043-VOTE": 2, "M044-SMOOTH3": 2, "M046-STACK5": 3}
    for tag, cfg, kd in specs:
        print(f"[run] {tag}", flush=True)
        pk = plans3(cfg, tag)
        if all(a["weights"] == b["weights"] for k in envs for a, b in zip(p36[k], pk[k])):
            print("   no-op (plan = M036) → ไม่นับ trial", flush=True)
            continue
        if kd != "sens":
            check_eq(pk, tag)
        R[tag] = single(tag, pk)
        R[tag]["kind"] = kd
        if kd == "sens":
            R[tag]["sensitivity"] = True
    gate = [t for t in ("M042-ENSDEF", "M043-VOTE", "M044-SMOOTH3") if t in R and R[t]["sharpe"] > 1.4
            and R[t]["sh_c2"] > D36["sh_c2"] and R[t]["off_mean"] >= D36["off_mean"]]
    print(f"[M047] ผ่านประตู: {gate}", flush=True)
    if gate and set(gate) != {"M042-ENSDEF"}:
        e, v, s_ = "M042-ENSDEF" in gate, "M043-VOTE" in gate, "M044-SMOOTH3" in gate
        if e:   # regression: ปิด vote/smooth = M046
            pa = plans3(Cfg(vsl=True, canary=True, ens=True, vote=False, smooth=1), "regS")
            pb = plans3(Cfg(vsl=True, canary=True, ens=True), "regS")
            assert all(a["weights"] == b["weights"] for k in envs for a, b in zip(pa[k], pb[k]))
        pk = plans3(Cfg(vsl=True, canary=True, ens=e, vote=v, smooth=3 if s_ else 1), "M047-STACK6")
        check_eq(pk, "M047")
        R["M047-STACK6"] = single("M047-STACK6", pk)
        R["M047-STACK6"]["kind"] = "stack"
        R["M047-STACK6"]["components"] = "VSL+CANARY+" + "+".join(gate)
        ncomp["M047-STACK6"] = 2 + len(gate)
    cands = [t for t in R if t in ncomp and R[t]["pass_all"]]
    if cands:
        win = sorted(cands, key=lambda t: (ncomp[t], -R[t]["sh_c2"], -R[t]["off_mean"]))[0]
        print(f"[ผู้ชนะรอบ 4] {win} (ผ่านทั้ง 3 ข้อ: {cands})", flush=True)
    else:
        pool = [t for t in R if t in ncomp and R[t]["pass1"] and R[t]["pass3"]] + ["M041-STACK(reg)"]
        allx = {**R, "M041-STACK(reg)": D41}
        best = max(pool, key=lambda t: allx[t]["sh_c2"])
        print(f"[ผู้ชนะรอบ 4] ไม่มีตัวผ่าน · sh_c2 สูงสุด = {best} {allx[best]['sh_c2']:.4f} (ขาด {1.3 - allx[best]['sh_c2']:.4f})", flush=True)

    # ---------------- บันทึก ----------------
    q = pd.DataFrame({t: v.resample("QE").last().pct_change() for t, v in vals.items()}).dropna()
    qd = pd.concat({"vs_M036": q.drop(columns=["M036-CANARY(reg)"]).sub(q["M036-CANARY(reg)"], axis=0),
                    "vs_M033": q.drop(columns=["M033-STACK(reg)"]).sub(q["M033-STACK(reg)"], axis=0)}, axis=1)
    qd.to_csv(os.path.join(RES, "R4_qdelta.csv"))
    for t in R:
        d = qd[("vs_M036", t)]
        R[t]["d36_Q125"] = float(d[d.index == pd.Timestamp("2025-03-31")].sum())
        R[t]["d36_other"] = float(d.sum() - R[t]["d36_Q125"])
    out = pd.DataFrame([{c: v for c, v in x.items() if c not in ("r", "rfm")} for x in [B, D34, D36, D41, *R.values()]]).set_index("model_id")
    out.to_csv(os.path.join(RES, "R4_results.csv"))
    pd.DataFrame([r for r in olog if r.get("model") not in ("reg", "regS")]).to_csv(os.path.join(RES, "R4_overlay_log.csv"), index=False)
    shutil.copy(TRIALS, os.path.join(TEAM, f"trials.backup_{pd.Timestamp.now():%Y%m%dT%H%M%S}.csv"))
    cols = next(csv.reader(open(TRIALS, encoding="utf-8", newline="")))
    raw = open(TRIALS, "rb").read()
    n = max(int(float(x["n_trials_cumulative"])) for x in csv.DictReader(open(TRIALS, encoding="utf-8", newline="")) if x["n_trials_cumulative"])
    assert n == 80, n
    new = []
    for tag, x in R.items():
        n += 1
        new.append({"model_id": tag, "run_at": pd.Timestamp.now().isoformat(), "spec_file": "debate/R4_modeler.md",
                    "params": "R4 debate · base M036-CANARY/M041-STACK · " + tag + (" · " + x["components"] if "components" in x else ""),
                    "period_start": "2022-03-31", "period_end": "2025-12-31",
                    "rf_source": "BOT policy rate daily (TH_POLICY_RATE.csv)", "cost_assumption": "real fees SecFundFee FEEUH (full; FeeData legacy=False; E/F/O separate)",
                    "sharpe": round(x["sharpe"], 4), "cagr": round(x["cagr"], 4), "vol": round(x["vol"], 4), "max_dd": round(x["max_dd"], 4),
                    "turnover": round(x["turn_yr"], 4), "n_trials_cumulative": n, "deflated_sharpe": round(rr.dsr_s(x["r"], x["rfm"], n), 4),
                    "status": "ok", "notes": ("SENSITIVITY not candidate; " if x.get("sensitivity") else "")
                    + f"sh_c2={x['sh_c2']:.4f}; off_mean={x['off_mean']:.3f}; pass1={x['pass1']}; pass2={x['pass2']}; pass3={x['pass3']}"})
    eol = "\r\n" if raw.count(b"\r\n") > raw.count(b"\n") / 2 else "\n"
    buf = io.StringIO()
    csv.writer(buf, lineterminator=eol).writerows([[str(r[c]) for c in cols] for r in new])
    with open(TRIALS, "ab") as f:
        f.write((b"" if raw.endswith(b"\n") else eol.encode()) + buf.getvalue().encode("utf-8"))
    pd.set_option("display.width", 300)
    show = ["sharpe", "cagr", "vol", "max_dd", "sh_c2", "sh_exQ125", "off0", "off1", "off2", "off_mean", "x_mean", "gold_mean", "cost_bp_yr", "pass1", "pass2", "pass3", "pass_all"]
    print(out[[c for c in show if c in out]].round(4).to_string())
    print(qd.round(4).to_string())
    print(f"trials ถึง n = {n} · done {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
