"""run_m019.py — M019-LC3-GCGOLD: หุ้น 3 กอง "อันดับ 1 + correlation ต่ำสุด" จากอันดับ ≤ 9 · ERC เพดาน 40% · GC75 + กองทอง
spec: specs/M019_lowcorr_3fund.md (ผู้ใช้อนุมัติ 2026-10-12) · trial #45 · DSR@45 · base = M018-N3-GCGOLD (run_m018.py)
regression: ขั้นเติมแบบเรียงอันดับ + กลุ่ม/ถือต่อ ≤ 6 ต้องได้น้ำหนัก = M018-N3-GCGOLD ทุกบิต (ไม่ผ่าน = หยุด ไม่บันทึก trial)
รัน: PYTHONPATH=. ./.venv/bin/python .claude/quant_team/backtest/run_m019.py
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
import remeasure_real_rf as rr
import robust_offsets as ro
import run_m010 as r10
import run_m011 as r11
import run_m013 as r13
import run_m015 as r15
import run_m018 as m18
import weighting as wt
import fulluniv_run as fu

TEAM = os.path.dirname(THIS)
RES = common.RESULTS_DIR
TRIALS = os.path.join(TEAM, "trials.csv")
MODEL = "M019-LC3-GCGOLD"
N, POOL, CAP, NMIN, N_TRIALS = 3, 9, 0.40, 2, 45
KINDS = m18.KINDS


def select_lc(ctx, held, prev_fb, qual, pool_k, ordered=False):
    """§2: ถือต่อ (อยู่ในอันดับ ≤ pool_k และ class เดิม) -> ว่างให้เริ่มที่อันดับ 1 -> เติมกองที่ max ρ_adj กับที่เลือกแล้วต่ำสุด.
    ordered=True = เติมตามอันดับ (เส้นทาง regression)."""
    i_t = ctx["i_t"]
    H_map = {} if prev_fb else held
    fam_ok = set(qual.index[qual["pass_q1"] & qual["pass_q2"]])
    it = i_t[i_t["family"].isin(fam_ok)]
    reps = wt.family_representatives(it, "SR12", held_funds=set(held.values()))
    ranks = wt.rank_families(reps)
    pool = [f for f in sorted(reps, key=lambda f: ranks[f]) if ranks[f] <= pool_k]
    S = {fam: fc for fam, fc in H_map.items() if fam in pool and reps[fam]["FundCode"] == fc}
    pairs = []
    if ordered:
        for fam in pool:
            if len(S) >= N:
                break
            S.setdefault(fam, reps[fam]["FundCode"])
    else:
        if not S and pool:
            S[pool[0]] = reps[pool[0]]["FundCode"]
        while len(S) < N:
            cands = [f for f in pool if f not in S]
            if not cands:
                break
            def score(f):
                rh = [r10.rho_adj_pair(ctx["wk"][reps[f]["FundCode"]], ctx["wk"][fc]) for fc in S.values()]
                return max(1.0 if np.isnan(x) else x for x in rh)
            sc = {f: score(f) for f in cands}
            best = min(cands, key=lambda f: (sc[f], ranks[f]))
            pairs.append({"fund": reps[best]["FundCode"], "rank": ranks[best], "max_rho_adj": sc[best]})
            S[best] = reps[best]["FundCode"]
    return {"S": S, "fallback": len(S) < NMIN, "ranks": ranks, "reps": reps, "pairs": pairs,
            "kept": [fam for fam in H_map if fam in S and S[fam] == H_map[fam]]}


def stream_lc(ctxs, quals, pool_k, ordered):
    held, prev_fb = {}, False
    sleeves, recs = {}, []
    for ctx in ctxs:
        qi = ctx["qi"]
        rec = select_lc(ctx, held, prev_fb, quals[qi], pool_k, ordered)
        recs.append(rec)
        if rec["fallback"]:
            held, prev_fb = {}, True
            sleeves[qi] = ctx["b0_w"]
            continue
        held, prev_fb = dict(rec["S"]), False
        funds = list(rec["S"].values())
        w, _ = wt.risk_parity_weights(funds, ctx["wk"], ctx["vol_map"], method="erc")
        sleeves[qi] = wt.apply_cap(w, CAP)
    return sleeves, recs


def gc_gold_plan(E, X, GS, sleeves):
    """สัดส่วนหุ้น GC75 · ส่วนหุ้นที่เหลือจากเพดาน (ได้ < 3 กอง) -> ขากัน · ขากัน = กองทอง (ไม่มี -> กองตลาดเงิน)."""
    kmap = dict(zip(E["sig"]["t"], E["sig"]["k"]))
    base = []
    for qi, t in enumerate(E["q15"]):
        c = 1.0 - r13.TABLES["GC75"][kmap[t]]
        w = sleeves[qi]
        wf = {fc: (1.0 - c) * float(v) for fc, v in w.items() if v > 0}            # สูตรเดียวกับ r67.old_style_plan
        left = (1.0 - c) * (1.0 - float(w.sum())) if 1.0 - float(w.sum()) > 1e-9 else 0.0
        if c + left > 0:
            wf["__CASH__"] = c + left
        base.append({"t": t, "e": common.execution_date(E["calendar"], t), "weights": wf})
    g1, _ = r15.make_plan_F(base, GS)
    plan = r15.make_plan_F(g1, X["sels"]["FAUM"])[0]
    for p in plan:
        assert abs(sum(p["weights"].values()) - 1) < 1e-9 and "__CASH__" not in p["weights"], p["t"]
    return plan


def main():
    t0 = time.time()
    holder = {}
    E, P, X = fu.build_env_and_plans(0, holder)
    FD = holder["FD"]
    profile = r15.load_profile()
    f_codes = sorted(FD.profile.index[FD.profile["Fund Policy"] == "F"])
    GD = m18.GData(profile, E, f_codes)
    GS = m18.gold_sels(GD, E)
    fee = m18.Fee3(E["fd_sim"], fees.FeeData(f_codes), f_codes, fees.FeeData(GD.codes), GD.codes)
    nav_all = {**E["nav_by_fund"], **FD.nav_by_fund, **GD.nav_by_fund}
    fset = set(FD.codes) | set(GD.codes)
    real = E["real"]

    def sim(plan, kinds=KINDS, Ex=E):
        return r15.sim_cases_x(plan, nav_all, Ex["months"], fee, real, fset=fset, kinds=kinds, log_full="full" in kinds)

    print("[1/4] regression vs M018-N3-GCGOLD", flush=True)
    s_rg, _ = stream_lc(E["ctx_h"], E["quals"], 6, ordered=True)
    plan_rg = gc_gold_plan(E, X, GS, s_rg)
    ref = pd.read_csv(os.path.join(RES, "M018_weights.csv"), parse_dates=["t"]).query("model == 'M018-N3-GCGOLD'")
    mine = m18.weights_frame(plan_rg, "x")
    m = ref.merge(mine, on=["t", "FundCode"], how="outer", suffixes=("_ref", "_new"))
    dw = float((m["weight_ref"] - m["weight_new"]).abs().max()) if m[["weight_ref", "weight_new"]].notna().all().all() else np.inf
    base_vals = sim(plan_rg)
    sh_rg = rr.metrics(base_vals["full"]["values"], real)["sharpe"]
    sh_ref = float(pd.read_csv(os.path.join(RES, "M018_results.csv")).set_index("model_id").loc["M018-N3-GCGOLD", "sharpe_full"])
    print(f"  max|Δw| {dw:.2e} · Sharpe {sh_rg:.6f} (ref {sh_ref:.6f})", flush=True)
    if not (dw < 1e-12 and abs(sh_rg - sh_ref) < 5e-7):
        print("REGRESSION FAIL — หยุด ไม่บันทึก trial"); sys.exit(2)

    print("[2/4] M019 offset 0", flush=True)
    sleeves, recs = stream_lc(E["ctx_h"], E["quals"], POOL, ordered=False)
    plan = gc_gold_plan(E, X, GS, sleeves)
    s = sim(plan)
    M = {k: rr.metrics(s[k]["values"], real) for k in KINDS}
    r, rfm = M["full"]["r"], M["full"]["rfm"]
    rb = rr.metrics(base_vals["full"]["values"], real)["r"]
    lo, hi = rr.boot_ci(r, rfm)
    dlo, dhi, dpt = r11.paired_real(r, rb, rfm)
    res = {"model_id": MODEL, **{f"sharpe_{k}": M[k]["sharpe"] for k in KINDS}, "cagr_full": M["full"]["cagr"],
           "cagr_nofront": M["nofront"]["cagr"], "vol": M["full"]["vol"], "max_dd": M["full"]["max_dd"], "ci_lo": lo, "ci_hi": hi,
           "dsr45": rr.dsr_s(r, rfm, N_TRIALS), **m18.year_returns(s["full"]["values"]), "cost_bp_yr": s["full"]["cost_bp_yr"],
           "turn_yr": s["full"]["turn_yr"], "d_vs_N3GCGOLD": dpt, "d_ci_lo": dlo, "d_ci_hi": dhi,
           "n_fallback_b0": sum(1 for x in recs[:15] if x["fallback"]),
           "n_lt3": sum(1 for x in recs[:15] if not x["fallback"] and len(x["S"]) < 3)}
    qlog = []
    for qi, rec in enumerate(recs[:15]):
        fcs = list(rec["S"].values())
        rho = {f"{a}|{b}": r10.rho_adj_pair(E["ctx_h"][qi]["wk"][a], E["ctx_h"][qi]["wk"][b]) for i, a in enumerate(fcs) for b in fcs[i + 1:]}
        qlog.append({"t": E["q15"][qi], "funds": " · ".join(fcs), "ranks": " · ".join(str(rec["ranks"][f]) for f in rec["S"]),
                     "kept": len(rec["kept"]), "max_pair_rho_adj": max(rho.values()) if rho else np.nan, "pairs": rho})

    print("[3/4] offset 0/1/2", flush=True)
    off = []
    for k in (0, 1, 2):
        Ek, Pk, Xk = (E, P, X) if k == 0 else fu.build_env_and_plans(k, holder)
        GSk = GS if k == 0 else m18.gold_sels(GD, Ek)
        for tag, ordered, pool in ((MODEL, False, POOL), ("M018-N3-GCGOLD", True, 6)):
            sl, _ = stream_lc(Ek["ctx_h"], Ek["quals"], pool, ordered)
            w = ro.win_metrics(sim(gc_gold_plan(Ek, Xk, GSk, sl), ["full"], Ek)["full"]["values"], real)
            off.append({"model_id": tag, "offset": k, "sharpe": w["sharpe"], "cagr": w["cagr"], "max_dd": w["max_dd"]})
    OFF = pd.DataFrame(off)
    om = OFF[OFF.model_id == MODEL]["sharpe"]
    res["offset_sharpe_min"], res["offset_sharpe_max"] = om.min(), om.max()

    print("[4/4] บันทึก", flush=True)
    pd.DataFrame([res]).to_csv(os.path.join(RES, "M019_results.csv"), index=False)
    m18.weights_frame(plan, MODEL).to_csv(os.path.join(RES, "M019_weights.csv"), index=False)
    pd.DataFrame(qlog).to_csv(os.path.join(RES, "M019_quarters.csv"), index=False)
    OFF.to_csv(os.path.join(RES, "M019_offsets.csv"), index=False)
    stamp = pd.Timestamp.now().strftime("%Y%m%dT%H%M%S")
    shutil.copy(TRIALS, os.path.join(TEAM, f"trials.backup_{stamp}.csv"))
    cols = next(csv.reader(open(TRIALS, encoding="utf-8", newline="")))
    raw = open(TRIALS, "rb").read()
    last_n = max(int(float(r["n_trials_cumulative"])) for r in csv.DictReader(open(TRIALS, encoding="utf-8", newline="")) if r["n_trials_cumulative"])
    assert last_n == 44, f"trials.csv อยู่ที่ n = {last_n} ไม่ใช่ 44 ตาม spec"
    row = {"model_id": MODEL, "run_at": pd.Timestamp.now().isoformat(), "spec_file": "M019_lowcorr_3fund.md",
           "params": "M019: N=3;pool=rank<=9;keep if rank<=9;fill=min max rho_adj (lead-lag);ERC cap40%;GC75 k->x;leg=gold(AUM max)->MMF;SR12' real rf;quality S;full universe",
           "period_start": "2022-03-31", "period_end": "2025-12-31", "rf_source": "BOT policy rate daily (TH_POLICY_RATE.csv)",
           "cost_assumption": "real fees SecFundFee FEEUH (full; FeeData legacy=False; E/F/O separate)",
           "sharpe": round(res["sharpe_full"], 4), "cagr": round(res["cagr_full"], 4), "vol": round(res["vol"], 4), "max_dd": round(res["max_dd"], 4),
           "turnover": round(res["turn_yr"], 4), "n_trials_cumulative": 45, "deflated_sharpe": round(res["dsr45"], 4), "status": "ok",
           "notes": (f"POST-HOC LABEL (ไอเดียหลังเห็น M018-N3 + ทอง); dSharpe vs M018-N3-GCGOLD {dpt:.3f} CI ({dlo:.3f};{dhi:.3f}); "
                     f"Sharpe 0%={res['sharpe_c0']:.3f} flat={res['sharpe_flat']:.3f} nofront={res['sharpe_nofront']:.3f}; "
                     f"CI95 ({lo:.3f};{hi:.3f}); offset {om.min():.3f}-{om.max():.3f}")}
    eol = "\r\n" if raw.count(b"\r\n") > raw.count(b"\n") / 2 else "\n"
    buf = io.StringIO()
    csv.writer(buf, lineterminator=eol).writerow([str(row[c]) for c in cols])
    with open(TRIALS, "ab") as f:                       # append ต่อท้าย — ไม่แตะแถวเดิม
        f.write((b"" if raw.endswith(b"\n") else eol.encode()) + buf.getvalue().encode("utf-8"))
    pd.set_option("display.width", 250)
    print(pd.Series(res).to_string())
    print(OFF.to_string())
    print(pd.DataFrame(qlog).drop(columns="pairs").to_string())
    print(f"done {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
