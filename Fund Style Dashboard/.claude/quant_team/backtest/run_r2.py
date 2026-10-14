"""run_r2.py — debate รอบ 2 (spec: debate/R2_modeler.md §3): D1 COSTMAP · D2 GOLDFX (0 trial) · M029-BAND5 · M030-SIW · M031-GFX-H · M032-GFX-U (sensitivity) · M033-STACK
ฐาน = M024-FEE0 (run_r1.select_gen + Cfg(fee0=True)) · ไม่แก้ run_r1.py · regression ไม่ผ่าน = หยุด ไม่บันทึก
รัน: PYTHONPATH=. ./.venv/bin/python .claude/quant_team/backtest/run_r2.py
"""
from __future__ import annotations

import csv
import io
import os
import shutil
import sys
import time

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
import run_m015 as r15
import run_m018 as m18
import run_m019 as m19
import run_r1 as r1
import simulate
import weighting as wt
import fulluniv_run as fu

TEAM = os.path.dirname(THIS)
RES = common.RESULTS_DIR
TRIALS = os.path.join(TEAM, "trials.csv")
BAND = 0.05
M024_SHARPE, M024_OFFS = 1.171365, (1.55808, 0.57247, 1.03517)


# ---------------- M030-SIW: select_gen ของ run_r1 + ต้นทุนเข้าที่นับช่องสับเปลี่ยน ----------------
def select_siw(ctx, held, prev_fb, qual, fee, siw):
    """= r1.select_gen(cfg=Cfg(fee0=True)) ทุกบรรทัด ยกเว้นต้นทุน ff → c_eff เมื่อ siw=True."""
    t = ctx["t"]
    H_map = {} if prev_fb else held
    fam_ok = set(qual.index[qual["pass_q1"] & qual["pass_q2"]])
    it = ctx["i_t"][ctx["i_t"]["family"].isin(fam_ok)]
    reps = wt.family_representatives(it, "SR12", held_funds=set(held.values()))
    ranks = wt.rank_families(reps)
    pool_all = sorted(reps, key=lambda f: ranks[f])
    S_keep = {fam: fc for fam, fc in H_map.items() if fam in reps and ranks[fam] <= r1.POOL and reps[fam]["FundCode"] == fc}
    D = [fc for fc in H_map.values() if fc not in S_keep.values()]

    def cost(c):
        ff = fee.rate(c, "FF", t)
        if not siw:
            return ff
        so = [fee.rate(d, "SO", t) for d in D if fee.amc.get(d, d) == fee.amc.get(c, c)]
        return min(ff, fee.rate(c, "SI", t) + min(so)) if so else ff

    for fam, rep in list(reps.items()):
        if fam in held:
            continue
        g = it[(it["family"] == fam) & (it["SR12"] >= rep["signal"] - r1.EPS)]
        best = sorted(g.itertuples(), key=lambda r: (cost(r.FundCode), -r.SR12, r.FundCode))[0].FundCode
        reps[fam] = {**rep, "FundCode": best}
    pool = [f for f in pool_all if ranks[f] <= r1.POOL]
    S = {fam: fc for fam, fc in H_map.items() if fam in reps and ranks[fam] <= r1.POOL and reps[fam]["FundCode"] == fc}
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
    return {"S": S, "fallback": len(S) < r1.NMIN}


def stream_siw(ctxs, quals, fee, siw):
    held, prev_fb, sleeves, recs = {}, False, {}, []
    for ctx in ctxs:
        qi = ctx["qi"]
        rec = select_siw(ctx, held, prev_fb, quals[qi], fee, siw)
        recs.append(rec)
        if rec["fallback"]:
            held, prev_fb = {}, True
            sleeves[qi] = ctx["b0_w"]
            continue
        held, prev_fb = dict(rec["S"]), False
        w, _ = wt.risk_parity_weights(list(rec["S"].values()), ctx["wk"], ctx["vol_map"], method="erc")
        sleeves[qi] = wt.apply_cap(w, r1.CAP)
    return sleeves, recs


# ---------------- M029-BAND5: no-trade band ระดับ plan ----------------
def band_plan(plan, nav_all, arrays, band):
    out, prev = [], None
    for j, p in enumerate(plan):
        wT = {f: w for f, w in p["weights"].items() if w > 0}
        if prev is None or band <= 0:
            new = dict(p["weights"]) if band <= 0 else wT
        else:
            t_np = np.datetime64(p["t"].date())
            wd = {}
            for i, w in prev["weights"].items():
                x0 = simulate._exec_nav(nav_all, i, prev["e"])
                p1 = fs._asof(*arrays[i], t_np) if i in arrays else np.nan
                if w > 0 and x0 is not None and p1 == p1:
                    wd[i] = w * p1 / x0[0]
            sd = sum(wd.values())
            wd = {i: v / sd for i, v in wd.items()}
            F = {i for i in wT if i in wd and abs(wT[i] - wd[i]) <= band}
            T = [i for i in wT if i not in F]
            new = {i: wd[i] for i in F}
            left = 1.0 - sum(new.values())
            sT = sum(wT[i] for i in T)
            if T:
                new.update({i: wT[i] * left / sT for i in T})
            else:
                s = sum(new.values())
                new = {i: v / s for i, v in new.items()}
        q = dict(p)
        q["weights"] = new
        assert abs(sum(new.values()) - 1) < 1e-9
        out.append(q)
        prev = q
    return out


def eq_sets(plan, fset):
    return [frozenset(f for f, w in p["weights"].items() if w > 0 and f not in fset) for p in plan]


# ---------------- M031/M032-GFX: ชั้น hedge ด้วย tracking error 52 สัปดาห์ ≤ t ----------------
def load_gold_px():
    m = pd.read_csv(os.path.join(common.PROJECT_ROOT, "base_data", "MACRO_FACTOR.csv"), parse_dates=["Date"]).set_index("Date").sort_index()
    m = m[["Gold", "USDTHB"]].dropna()
    return fs._prep_arrays({"USD": m["Gold"], "THB": m["Gold"] * m["USDTHB"]})


def hedge_class(GD, gold_arr, cal, t, codes):
    q = fs.QuarterContext(GD.arrays, cal, t)
    qg = fs.QuarterContext(gold_arr, cal, t)
    assert max(q.weeks) <= t
    gu, gt = qg.weekly_return_series("USD"), qg.weekly_return_series("THB")
    out = {}
    for fc in codes:
        r = q.weekly_return_series(fc)
        d = pd.DataFrame({"f": r, "u": gu, "t": gt}).dropna()
        if len(d) < 40:
            continue
        out[fc] = "U" if (d["f"] - d["t"]).std() < (d["f"] - d["u"]).std() else "H"
    return out


def gold_sels_fx(GD, E, gold_arr, mode):
    out, cls_log = {}, []
    for qi, t in enumerate(E["q15"]):
        it, qual, _ = GD.it_at(t)
        if mode is not None and len(it):
            hc = hedge_class(GD, gold_arr, E["calendar"], t, list(it["FundCode"]))
            it = it[it["FundCode"].map(hc) == mode]
        out[qi] = m18.select_gold(it, qual, E["h_by_q"][qi])
    return out


# ---------------- D1 COSTMAP: FeeModel ที่ log ต่อกองต่อ entry ----------------
class MapFee(fees.FeeModel):
    def __init__(self, data, eq_codes, gold_codes, f_codes):
        super().__init__(data, "full")
        self.eq, self.gold, self.f = eq_codes, gold_codes, f_codes
        self.rows = []

    def entry_cost(self, e, drift_w, target_w):
        cost, det = super().entry_cost(e, drift_w, target_w)
        x_d = sum(w for f, w in drift_w.items() if f in self.eq)
        x_t = sum(w for f, w in target_w.items() if f in self.eq)
        b = {"new": 0.0, "topup_x": 0.0, "topup_rest": 0.0, "gold": 0.0, "mmf": 0.0}
        for f, wt_ in target_w.items():
            dlt = wt_ - drift_w.get(f, 0.0)
            if dlt <= 1e-15:
                continue
            ff = self._r(f, "FF", e)
            if f in self.gold:
                b["gold"] += dlt * ff
            elif f in self.f:
                b["mmf"] += dlt * ff
            elif drift_w.get(f, 0.0) <= 1e-12:
                b["new"] += dlt * ff
            else:
                ux = min(dlt, drift_w[f] * max(x_t / x_d - 1.0, 0.0)) if x_d > 0 else 0.0
                b["topup_x"] += ux * ff
                b["topup_rest"] += (dlt - ux) * ff
        self.rows.append({"e": e, "actual": cost, **b, "switch_vol": det["switch_vol"], "buy_vol": det["buy_vol"]})
        return cost, det


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
    real = E["real"]
    fee = m18.Fee3(E["fd_sim"], fees.FeeData(f_codes), f_codes, fees.FeeData(GD.codes), GD.codes)
    nav_all = {**E["nav_by_fund"], **FD.nav_by_fund, **GD.nav_by_fund}
    arrays = fs._prep_arrays(nav_all)
    fset = set(FD.codes) | set(GD.codes)
    GS = {k: m18.gold_sels(GD, envs[k][0]) for k in envs}
    gold_arr = load_gold_px()

    def sim(plan, kinds, Ex=E):
        return r15.sim_cases_x(plan, nav_all, Ex["months"], fee, real, fset=fset, kinds=kinds, log_full="full" in kinds)

    def plans(siw=False, band=0.0, legs=None):
        out = {}
        for k, (Ek, _, Xk) in envs.items():
            sl, _ = stream_siw(Ek["ctx_h"], Ek["quals"], fee, siw)
            p = m19.gc_gold_plan(Ek, Xk, (legs or GS)[k], sl)
            out[k] = band_plan(p, nav_all, arrays, band) if band > 0 else p
        return out

    def single(tag, pk):
        s = sim(pk[0], ["c0", "full", "nofront"])
        M = {x: rr.metrics(s[x]["values"], real) for x in ("c0", "full", "nofront")}
        offs = [ro.win_metrics(sim(pk[k], ["full"], envs[k][0])["full"]["values"], real)["sharpe"] for k in (0, 1, 2)]
        x = {"model_id": tag, "sharpe": M["full"]["sharpe"], "cagr": M["full"]["cagr"], "vol": M["full"]["vol"], "max_dd": M["full"]["max_dd"],
             "sharpe_nofront": M["nofront"]["sharpe"], "sharpe_c0": M["c0"]["sharpe"], **m18.year_returns(s["full"]["values"]),
             "cost_bp_yr": s["full"]["cost_bp_yr"], "turn_yr": s["full"]["turn_yr"], "off0": offs[0], "off1": offs[1], "off2": offs[2],
             "off_mean": float(np.mean(offs)), "r": M["full"]["r"], "rfm": M["full"]["rfm"]}
        x["d_vs_M024"] = x["sharpe"] - M024_SHARPE
        x["pass1"] = bool(x["sharpe"] > 1.2 and x["cagr"] > 0.12)
        x["pass2"] = bool(x["off_mean"] >= 1.0)
        print(f"   {tag}: Sharpe {x['sharpe']:.4f} · CAGR {x['cagr']:.2%} · DD {x['max_dd']:.2%} · cost {x['cost_bp_yr']:.0f}bp · "
              f"off {offs[0]:.3f}/{offs[1]:.3f}/{offs[2]:.3f} mean {x['off_mean']:.3f} · เป้า1 {x['pass1']} เป้า2 {x['pass2']}", flush=True)
        return x

    # ---------------- regression ----------------
    print("[reg] ฐาน = M024-FEE0", flush=True)
    ref = {k: r1.stream_gen(Ek["ctx_h"], Ek["quals"], r1.Cfg(fee0=True), fee)[0] for k, (Ek, _, _) in envs.items()}
    ref = {k: m19.gc_gold_plan(envs[k][0], envs[k][2], GS[k], ref[k]) for k in ref}
    base = plans()
    b0 = plans(band=0.0)
    gnone = {k: gold_sels_fx(GD, envs[k][0], gold_arr, None) for k in envs}
    for k in envs:
        for a, b, c in zip(ref[k], base[k], b0[k]):
            assert a["t"] == b["t"] and a["weights"] == b["weights"] == c["weights"], (k, a["t"])
        assert all(gnone[k][q][0] == GS[k][q][0] for q in range(15))
    B = single("M024-FEE0(reg)", base)
    assert abs(B["sharpe"] - M024_SHARPE) < 5e-7 and np.allclose([B["off0"], B["off1"], B["off2"]], M024_OFFS, atol=5e-5)
    print("  regression ผ่าน", flush=True)
    eq_base = {k: eq_sets(base[k], fset) for k in envs}

    # ---------------- D1 COSTMAP ----------------
    cm = []
    for k in envs:
        fm = MapFee(fee, set(E["nav_by_fund"]), set(GD.codes), set(FD.codes))
        clean = [{c: v for c, v in p.items() if c in ("t", "e", "weights")} for p in base[k]]
        info = {}
        with rr.cash_curve(real):
            simulate.simulate_path(clean, nav_all, envs[k][0]["months"], 0.0, 0.02, include_start=True, info=info, fee_model=fm)
        yrs = (rr.PE - clean[0]["e"]).days / 365.25
        d = pd.DataFrame(fm.rows)
        d = d[d["e"] <= rr.PE]
        row = {"offset": k, **{c: d[c].sum() / yrs * 1e4 for c in ("actual", "new", "topup_x", "topup_rest", "gold", "mmf")},
               "switch_share": d["switch_vol"].sum() / d["buy_vol"].sum()}
        row["gross_ff_sum"] = sum(row[c] for c in ("new", "topup_x", "topup_rest", "gold", "mmf"))
        cm.append(row)
    CM = pd.DataFrame(cm)
    CM.to_csv(os.path.join(RES, "R2_costmap.csv"), index=False)
    print("[D1] COSTMAP bp/ปี\n" + CM.round(2).to_string(index=False), flush=True)

    # ---------------- D2 GOLDFX ----------------
    gx = []
    for k, (Ek, _, _) in envs.items():
        for qi, t in enumerate(Ek["q15"]):
            v, _, reps = GS[k][qi]
            if not v:
                continue
            fc = next(iter(v))
            w = base[k][qi]["weights"].get(fc, 0.0)
            if w <= 0:
                continue
            hc = hedge_class(GD, gold_arr, Ek["calendar"], t, list(reps["FundCode"]))
            alt = reps[reps["FundCode"].map(hc) == ("U" if hc.get(fc) == "H" else "H")].sort_values(["aum_fam", "FundCode"], ascending=[False, True])
            e0 = base[k][qi]["e"]
            e1 = base[k][qi + 1]["e"] if qi + 1 < len(base[k]) else rr.PE

            def ret(f):
                a = simulate._exec_nav(nav_all, f, e0)
                b = simulate._exec_nav(nav_all, f, e1) if e1 < rr.PE else (float(fs._asof(*arrays[f], np.datetime64(e1.date()))), None, None)
                return b[0] / a[0] - 1 if a and b and b[0] == b[0] else np.nan
            ra = ret(fc)
            fb = alt["FundCode"].iloc[0] if len(alt) else None
            rb = ret(fb) if fb else np.nan
            gx.append({"offset": k, "t": t, "gold": fc, "cls": hc.get(fc), "w": w, "r": ra, "alt": fb, "r_alt": rb, "luck": w * (ra - rb)})
    GX = pd.DataFrame(gx)
    GX.to_csv(os.path.join(RES, "R2_goldfx.csv"), index=False)
    print("[D2] GOLDFX\n" + GX.round(4).to_string(index=False), flush=True)
    print("  ผลโชค hedge รวม (Σ w·Δr) ต่อ offset: " + str(GX.groupby("offset")["luck"].sum().round(4).to_dict()), flush=True)

    # ---------------- candidates ----------------
    R = {}
    print("[run] M029-BAND5", flush=True)
    pb = plans(band=BAND)
    for k in envs:
        assert eq_sets(pb[k], fset) == eq_base[k], k
    R["M029-BAND5"] = single("M029-BAND5", pb)
    n_in = sum(1 for k in envs for p0, p1 in zip(base[k], pb[k]) for f in p1["weights"] if abs(p1["weights"][f] - p0["weights"].get(f, 0)) > 1e-12)
    print(f"   fund-quarter ที่น้ำหนักต่างจากเป้า (อยู่ในแถบ+ปรับส่วนที่เหลือ): {n_in}", flush=True)

    print("[run] M030-SIW", flush=True)
    ps = plans(siw=True)
    noop = all(a["weights"] == b["weights"] for k in envs for a, b in zip(base[k], ps[k]))
    if noop:
        print("   SIW = no-op (plan = M024 ทุกบิต) → ไม่นับ trial", flush=True)
    else:
        R["M030-SIW"] = single("M030-SIW", ps)
        for k in envs:
            for a, b in zip(base[k], ps[k]):
                if a["weights"] != b["weights"]:
                    da = {f for f in a["weights"] if f not in fset} ^ {f for f in b["weights"] if f not in fset}
                    print(f"     off{k} {a['t'].date()}: ต่าง {sorted(da)}", flush=True)

    for tag, mode in (("M031-GFX-H", "H"), ("M032-GFX-U", "U")):
        print(f"[run] {tag} (sensitivity)", flush=True)
        legs = {k: gold_sels_fx(GD, envs[k][0], gold_arr, mode) for k in envs}
        pg = plans(legs=legs)
        for k in envs:
            for a, b in zip(base[k], pg[k]):
                assert {f: w for f, w in a["weights"].items() if f not in fset} == {f: w for f, w in b["weights"].items() if f not in fset}
        R[tag] = single(tag, pg)
        R[tag]["sensitivity"] = True

    ok = [c for c in ("M029-BAND5", "M030-SIW") if c in R and R[c]["sharpe"] >= M024_SHARPE and R[c]["off_mean"] >= 1.0]
    print(f"[M033] ผ่านกติกา: {ok}", flush=True)
    if len(ok) == 2:
        pst = plans(siw=True, band=BAND)
        R["M033-STACK"] = single("M033-STACK", pst)

    # ---------------- บันทึก ----------------
    out = pd.DataFrame([{c: v for c, v in x.items() if c not in ("r", "rfm")} for x in [B, *R.values()]]).set_index("model_id")
    out.to_csv(os.path.join(RES, "R2_results.csv"))
    shutil.copy(TRIALS, os.path.join(TEAM, f"trials.backup_{pd.Timestamp.now():%Y%m%dT%H%M%S}.csv"))
    cols = next(csv.reader(open(TRIALS, encoding="utf-8", newline="")))
    raw = open(TRIALS, "rb").read()
    n = max(int(float(x["n_trials_cumulative"])) for x in csv.DictReader(open(TRIALS, encoding="utf-8", newline="")) if x["n_trials_cumulative"])
    assert n == 59, n
    new = []
    for tag, x in R.items():
        n += 1
        new.append({"model_id": tag, "run_at": pd.Timestamp.now().isoformat(), "spec_file": "debate/R2_modeler.md",
                    "params": "R2 debate · base M024-FEE0 · " + tag, "period_start": "2022-03-31", "period_end": "2025-12-31",
                    "rf_source": "BOT policy rate daily (TH_POLICY_RATE.csv)", "cost_assumption": "real fees SecFundFee FEEUH (full; FeeData legacy=False; E/F/O separate)",
                    "sharpe": round(x["sharpe"], 4), "cagr": round(x["cagr"], 4), "vol": round(x["vol"], 4), "max_dd": round(x["max_dd"], 4),
                    "turnover": round(x["turn_yr"], 4), "n_trials_cumulative": n, "deflated_sharpe": round(rr.dsr_s(x["r"], x["rfm"], n), 4),
                    "status": "ok", "notes": ("SENSITIVITY not candidate; " if x.get("sensitivity") else "")
                    + f"off_mean={x['off_mean']:.3f}; sharpe_nofront={x['sharpe_nofront']:.3f}; d_vs_M024={x['d_vs_M024']:.3f}"})
    eol = "\r\n" if raw.count(b"\r\n") > raw.count(b"\n") / 2 else "\n"
    buf = io.StringIO()
    csv.writer(buf, lineterminator=eol).writerows([[str(r[c]) for c in cols] for r in new])
    with open(TRIALS, "ab") as f:
        f.write((b"" if raw.endswith(b"\n") else eol.encode()) + buf.getvalue().encode("utf-8"))
    pd.set_option("display.width", 250)
    print(out.round(4).to_string())
    print(f"trials ถึง n = {n} · done {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
