"""run_r3.py — debate รอบ 3 (spec: debate/R3_modeler.md §2–§3): D3-FRONTIER (0 trial) · overlay M034-VSL · M035-CAP75 · M036-CANARY · M037-RB2 (sensitivity)
· signal M038-NH52 · M039-RESID · M040-FIP · M041-STACK · ฐาน = M033-STACK (run_r2 plans(siw=True, band=0.05)) · ไม่แก้ไฟล์เดิม
รัน: PYTHONPATH=. ./.venv/bin/python .claude/quant_team/backtest/run_r3.py
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

    olog = []

    def make_xfun(cfg, k, sl, recs):
        Ek = envs[k][0]
        T = CAP75 if cfg.table == "CAP75" else GC75

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
            b = canary_b(t) if cfg.canary else 0
            x = max(0.25, min(T[kt] * m, 1 - b / 2))
            if cfg.rb2:
                g = list(GS[k][qi][0])
                if g and sS == sS:
                    sG = ann_sd(fs.QuarterContext(GD.arrays, cal, t).weekly_return_series(g[0]))
                x = max(0.25, min(GC75[kt], sG / (sS + sG))) if sG == sG else GC75[kt]
            row.update({"sigma_S": sS, "sigma_A": sA, "sigma_G": sG, "b": b, "x": x})
            olog.append(row)
            return x
        return xf

    def plans3(cfg, tag=""):
        out = {}
        for k, (Ek, _, Xk) in envs.items():
            sl, recs = stream_sig(Ek["ctx_h"], Ek["quals"], fee, cfg, aux)
            n0 = len(olog)
            p = gc_gold_plan_x(Ek, Xk, GS[k], sl, make_xfun(cfg, k, sl, recs))
            for r in olog[n0:]:
                r["model"] = tag
            out[k] = R2.band_plan(p, nav_all, arrays, BAND)
        return out

    def sim(plan, kinds, Ex=E):
        return r15.sim_cases_x(plan, nav_all, Ex["months"], fee, real, fset=fset, kinds=kinds, log_full="full" in kinds)

    vals = {}

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
        x["d_vs_M033"] = x["sharpe"] - M033_SHARPE
        x["pass_1p4"] = bool(x["sharpe"] > 1.4)
        print(f"   {tag}: Sharpe {x['sharpe']:.4f} · CAGR {x['cagr']:.2%} · vol {x['vol']:.2%} · DD {x['max_dd']:.2%} · exQ2'22 {x['sh_exQ222']:.3f} · "
              f"off {offs[0]:.3f}/{offs[1]:.3f}/{offs[2]:.3f} mean {x['off_mean']:.3f} · x̄ {x['x_mean']:.2f} ทอง {x['gold_mean']:.2f}", flush=True)
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

    # ---------------- D3 FRONTIER (offset 0) ----------------
    Ek, _, Xk = envs[0]
    sl, _ = R2.stream_siw(Ek["ctx_h"], Ek["quals"], fee, True)
    pS = [{"t": p["t"], "e": p["e"], "weights": {f: float(v) / float(sl[qi][sl[qi] > 0].sum()) for f, v in sl[qi].items() if v > 0}}
          for qi, p in enumerate(base[0])]
    pG = [{"t": p["t"], "e": p["e"], "weights": dict(GS[0][qi][0] or Xk["sels"]["FAUM"][qi][0])} for qi, p in enumerate(base[0])]
    rS = rr.metrics(sim(R2.band_plan(pS, nav_all, arrays, BAND), ["full"])["full"]["values"], real)
    rG = rr.metrics(sim(R2.band_plan(pG, nav_all, arrays, BAND), ["full"])["full"]["values"], real)
    rfm = rS["rfm"]
    eS, eG = rS["r"] - rfm, rG["r"] - rfm
    mu = np.array([eS.mean(), eG.mean()])
    C = np.cov(np.vstack([eS, eG]))
    wtan = np.linalg.solve(C, mu)
    wtan = wtan / wtan.sum()
    grid = np.round(np.arange(0.25, 1.0001, 0.01), 2)
    mix = {w: rr.sharpe_s(w * rS["r"] + (1 - w) * rG["r"], rfm) for w in grid}
    wbest = max(mix, key=mix.get)
    xbar = round(B["x_mean"], 2)
    fr = {"sharpe_S": rS["sharpe"], "sharpe_G": rG["sharpe"], "vol_S": rS["vol"], "vol_G": rG["vol"], "rho_SG": float(np.corrcoef(eS, eG)[0, 1]),
          "w_tangency_S": wtan[0], "best_fixed_wS": wbest, "best_fixed_sharpe": mix[wbest], "xbar": xbar,
          "fixed_at_xbar": mix[min(grid, key=lambda g: abs(g - xbar))]}
    fr["timing_value"] = M033_SHARPE - fr["fixed_at_xbar"]
    for y in (2022, 2023, 2024, 2025):
        m = eS.index.year == y
        fr[f"rho_{y}"] = float(np.corrcoef(eS[m], eG[m])[0, 1])
    pd.Series(fr).to_csv(os.path.join(RES, "R3_frontier.csv"))
    print("[D3] FRONTIER\n" + pd.Series(fr).round(4).to_string(), flush=True)

    # ---------------- candidates ----------------
    specs = [("M034-VSL", Cfg(vsl=True), "overlay"), ("M035-CAP75", Cfg(table="CAP75"), "overlay"), ("M036-CANARY", Cfg(canary=True), "overlay"),
             ("M037-RB2", Cfg(rb2=True), "sens"), ("M038-NH52", Cfg(sigs=("SR", "NH")), "signal"), ("M039-RESID", Cfg(sigs=("RS",)), "signal"),
             ("M040-FIP", Cfg(sigs=("SR", "ID")), "signal")]
    R, kind, P = {}, {}, {}
    for tag, cfg, kd in specs:
        print(f"[run] {tag}", flush=True)
        pk = plans3(cfg, tag)
        if all(a["weights"] == b["weights"] for k in envs for a, b in zip(base[k], pk[k])):
            print("   no-op (plan = M033) → ไม่นับ trial", flush=True)
            continue
        if kd != "signal":
            for k in envs:
                assert R2.eq_sets(pk[k], fset) == eq_base[k], (tag, k)
        else:
            print("   ไตรมาสที่ชุดกองหุ้นต่าง: " + str({k: sum(a != b for a, b in zip(R2.eq_sets(pk[k], fset), eq_base[k])) for k in envs}), flush=True)
        R[tag], kind[tag], P[tag] = single(tag, pk), kd, cfg
        if kd == "sens":
            R[tag]["sensitivity"] = True

    ok_o = [t for t in R if kind[t] == "overlay" and R[t]["sharpe"] > M033_SHARPE + 4e-6 and R[t]["off_mean"] >= 1.0 and R[t]["sh_exQ222"] >= B["sh_exQ222"]]
    ok_s = [t for t in R if kind[t] == "signal" and R[t]["sharpe"] > M033_SHARPE + 4e-6 and R[t]["off_mean"] >= 1.0798]
    print(f"[M041] ผ่านกติกา: overlay {ok_o} · signal {ok_s}", flush=True)
    if len(ok_o) + len(ok_s) >= 2:
        sig_map = {"M038-NH52": "NH", "M039-RESID": "RS", "M040-FIP": "ID"}
        sigs = tuple(["SR"] + [sig_map[t] for t in ok_s]) if ok_s else ()
        cfg = Cfg(sigs=sigs, vsl="M034-VSL" in ok_o, table="CAP75" if "M035-CAP75" in ok_o else "GC75", canary="M036-CANARY" in ok_o)
        # regression: เปิดส่วนประกอบเดียว = แบบเดี่ยว (RESID ใน STACK ผสม ½SR12 จึงไม่เทียบ)
        for t in ok_o + [t for t in ok_s if t != "M039-RESID"]:
            one = Cfg(sigs=P[t].sigs, vsl=P[t].vsl, table=P[t].table, canary=P[t].canary)
            pa, pb = plans3(one, "regS"), plans3(P[t], "regS")
            assert all(a["weights"] == b["weights"] for k in envs for a, b in zip(pa[k], pb[k])), t
        R["M041-STACK"], kind["M041-STACK"] = single("M041-STACK", plans3(cfg, "M041-STACK")), "stack"
        R["M041-STACK"]["components"] = "+".join(ok_o + ok_s)

    # ---------------- บันทึก ----------------
    q = pd.DataFrame({t: v.resample("QE").last().pct_change() for t, v in vals.items()}).dropna()
    qd = q.drop(columns="M033-STACK(reg)").sub(q["M033-STACK(reg)"], axis=0)
    qd.to_csv(os.path.join(RES, "R3_qdelta.csv"))
    for t in qd.columns:
        tot, late = qd[t].sum(), qd[t][qd.index.year >= 2024].sum()
        if t in R:
            R[t]["gold_boom_flag"] = bool(tot > 0 and late > tot)
    out = pd.DataFrame([{c: v for c, v in x.items() if c not in ("r", "rfm")} for x in [B, *R.values()]]).set_index("model_id")
    out.to_csv(os.path.join(RES, "R3_results.csv"))
    pd.DataFrame([r for r in olog if r.get("model") not in ("reg", "regS")]).to_csv(os.path.join(RES, "R3_overlay_log.csv"), index=False)
    shutil.copy(TRIALS, os.path.join(TEAM, f"trials.backup_{pd.Timestamp.now():%Y%m%dT%H%M%S}.csv"))
    cols = next(csv.reader(open(TRIALS, encoding="utf-8", newline="")))
    raw = open(TRIALS, "rb").read()
    n = max(int(float(x["n_trials_cumulative"])) for x in csv.DictReader(open(TRIALS, encoding="utf-8", newline="")) if x["n_trials_cumulative"])
    assert n == 72, n
    new = []
    for tag, x in R.items():
        n += 1
        new.append({"model_id": tag + "-r", "run_at": pd.Timestamp.now().isoformat(), "spec_file": "debate/R3_modeler.md",
                    "params": "R3 debate · base M033-STACK · " + tag + (" · " + x["components"] if "components" in x else ""),
                    "period_start": "2022-03-31", "period_end": "2025-12-31",
                    "rf_source": "BOT policy rate daily (TH_POLICY_RATE.csv)", "cost_assumption": "real fees SecFundFee FEEUH (full; FeeData legacy=False; E/F/O separate)",
                    "sharpe": round(x["sharpe"], 4), "cagr": round(x["cagr"], 4), "vol": round(x["vol"], 4), "max_dd": round(x["max_dd"], 4),
                    "turnover": round(x["turn_yr"], 4), "n_trials_cumulative": n, "deflated_sharpe": round(rr.dsr_s(x["r"], x["rfm"], n), 4),
                    "status": "ok", "notes": "RERUN after K-GOLD-C(A) NAV plateau fix (2024-04-23..05-06) — supersedes #65-#72; " + ("SENSITIVITY not candidate; " if x.get("sensitivity") else "")
                    + f"off_mean={x['off_mean']:.3f}; exQ2_22={x['sh_exQ222']:.3f}; d_vs_M033={x['d_vs_M033']:.3f}; gold_boom={x.get('gold_boom_flag')}"})
    eol = "\r\n" if raw.count(b"\r\n") > raw.count(b"\n") / 2 else "\n"
    buf = io.StringIO()
    csv.writer(buf, lineterminator=eol).writerows([[str(r[c]) for c in cols] for r in new])
    with open(TRIALS, "ab") as f:
        f.write((b"" if raw.endswith(b"\n") else eol.encode()) + buf.getvalue().encode("utf-8"))
    pd.set_option("display.width", 300)
    print(out.round(4).to_string())
    print(qd.round(4).to_string())
    print(f"trials ถึง n = {n} · done {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
