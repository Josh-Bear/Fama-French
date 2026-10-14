"""run_m021.py — M021-LC5-GCGOLD: การคัดกองแบบ M019 กับ N = 5 · กลุ่มผู้สมัคร/ถือต่อ ≤ 15 · ERC เพดาน 40% · GC75 + กองทอง
spec: specs/M021_lowcorr_5fund_gold.md · trial #47 · DSR@47 · regression = M018-N5-GCGOLD ทุกบิต
ตั้ง N/NMIN ของ run_m019 ผ่านตัวแปรระดับโมดูล (select_lc อ่านตอนเรียก) — ไม่แก้ไฟล์ run_m019.py
รัน: PYTHONPATH=. ./.venv/bin/python .claude/quant_team/backtest/run_m021.py
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
import run_m015 as r15
import run_m018 as m18
import run_m019 as m19
import run_m020 as m20
import fulluniv_run as fu

TEAM = os.path.dirname(THIS)
RES = common.RESULTS_DIR
TRIALS = os.path.join(TEAM, "trials.csv")
MODEL, POOL, POOL_REG, N_TRIALS, KINDS = "M021-LC5-GCGOLD", 15, 10, 47, m18.KINDS
m19.N, m19.NMIN = 5, 3


def main():
    t0 = time.time()
    holder = {}
    E, P, X = fu.build_env_and_plans(0, holder)
    FD = holder["FD"]
    m20.assert_no_future(E)
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

    print("[1/4] regression vs M018-N5-GCGOLD", flush=True)
    s_rg, _ = m19.stream_lc(E["ctx_h"], E["quals"], POOL_REG, ordered=True)
    plan_rg = m19.gc_gold_plan(E, X, GS, s_rg)
    ref = pd.read_csv(os.path.join(RES, "M018_weights.csv"), parse_dates=["t"]).query("model == 'M018-N5-GCGOLD'")
    m = ref.merge(m18.weights_frame(plan_rg, "x"), on=["t", "FundCode"], how="outer", suffixes=("_ref", "_new"))
    dw = float((m["weight_ref"] - m["weight_new"]).abs().max()) if m[["weight_ref", "weight_new"]].notna().all().all() else np.inf
    base = sim(plan_rg)
    sh_rg = rr.metrics(base["full"]["values"], real)["sharpe"]
    sh_ref = float(pd.read_csv(os.path.join(RES, "M018_results.csv")).set_index("model_id").loc["M018-N5-GCGOLD", "sharpe_full"])
    print(f"  max|Δw| {dw:.2e} · Sharpe {sh_rg:.6f} (ref {sh_ref:.6f})", flush=True)
    if not (dw < 1e-12 and abs(sh_rg - sh_ref) < 5e-7):
        print("REGRESSION FAIL — หยุด ไม่บันทึก trial"); sys.exit(2)

    print("[2/4] M021 offset 0", flush=True)
    sleeves, recs = m19.stream_lc(E["ctx_h"], E["quals"], POOL, ordered=False)
    plan = m19.gc_gold_plan(E, X, GS, sleeves)
    s = sim(plan)
    M = {k: rr.metrics(s[k]["values"], real) for k in KINDS}
    r, rfm = M["full"]["r"], M["full"]["rfm"]
    lo, hi = rr.boot_ci(r, rfm)
    dlo, dhi, dpt = r11.paired_real(r, rr.metrics(base["full"]["values"], real)["r"], rfm)
    res = {"model_id": MODEL, **{f"sharpe_{k}": M[k]["sharpe"] for k in KINDS}, "cagr_full": M["full"]["cagr"],
           "cagr_nofront": M["nofront"]["cagr"], "vol": M["full"]["vol"], "max_dd": M["full"]["max_dd"], "ci_lo": lo, "ci_hi": hi,
           "dsr47": rr.dsr_s(r, rfm, N_TRIALS), **m18.year_returns(s["full"]["values"]), "cost_bp_yr": s["full"]["cost_bp_yr"],
           "turn_yr": s["full"]["turn_yr"], "d_vs_N5GCGOLD": dpt, "d_ci_lo": dlo, "d_ci_hi": dhi,
           "n_fallback_b0": sum(1 for x in recs[:15] if x["fallback"]),
           "n_lt5": sum(1 for x in recs[:15] if not x["fallback"] and len(x["S"]) < 5)}
    qlog = []
    for qi, rec in enumerate(recs[:15]):
        fcs = list(rec["S"].values())
        rho = [r10.rho_adj_pair(E["ctx_h"][qi]["wk"][a], E["ctx_h"][qi]["wk"][b]) for i, a in enumerate(fcs) for b in fcs[i + 1:]]
        qlog.append({"t": E["q15"][qi], "funds": " · ".join(fcs), "ranks": " · ".join(str(rec["ranks"][f]) for f in rec["S"]),
                     "kept": len(rec["kept"]), "max_pair_rho_adj": np.nanmax(rho) if rho else np.nan})

    print("[3/4] offset 0/1/2", flush=True)
    off = []
    for k in (0, 1, 2):
        Ek, Pk, Xk = (E, P, X) if k == 0 else fu.build_env_and_plans(k, holder)
        if k:
            m20.assert_no_future(Ek)
        GSk = GS if k == 0 else m18.gold_sels(GD, Ek)
        for tag, ordered, pool in ((MODEL, False, POOL), ("M018-N5-GCGOLD", True, POOL_REG)):
            sl, _ = m19.stream_lc(Ek["ctx_h"], Ek["quals"], pool, ordered)
            w = ro.win_metrics(sim(m19.gc_gold_plan(Ek, Xk, GSk, sl), ["full"], Ek)["full"]["values"], real)
            off.append({"model_id": tag, "offset": k, "sharpe": w["sharpe"], "cagr": w["cagr"], "max_dd": w["max_dd"]})
    OFF = pd.DataFrame(off)
    om = OFF[OFF.model_id == MODEL]["sharpe"]
    res["offset_sharpe_min"], res["offset_sharpe_max"] = om.min(), om.max()

    print("[4/4] บันทึก", flush=True)
    pd.DataFrame([res]).to_csv(os.path.join(RES, "M021_results.csv"), index=False)
    m18.weights_frame(plan, MODEL).to_csv(os.path.join(RES, "M021_weights.csv"), index=False)
    pd.DataFrame(qlog).to_csv(os.path.join(RES, "M021_quarters.csv"), index=False)
    OFF.to_csv(os.path.join(RES, "M021_offsets.csv"), index=False)
    shutil.copy(TRIALS, os.path.join(TEAM, f"trials.backup_{pd.Timestamp.now():%Y%m%dT%H%M%S}.csv"))
    cols = next(csv.reader(open(TRIALS, encoding="utf-8", newline="")))
    raw = open(TRIALS, "rb").read()
    last_n = max(int(float(x["n_trials_cumulative"])) for x in csv.DictReader(open(TRIALS, encoding="utf-8", newline="")) if x["n_trials_cumulative"])
    assert last_n == 46, f"trials.csv อยู่ที่ n = {last_n} ไม่ใช่ 46"
    row = {"model_id": MODEL, "run_at": pd.Timestamp.now().isoformat(), "spec_file": "M021_lowcorr_5fund_gold.md",
           "params": "M021: N=5;pool=rank<=15;keep if rank<=15;fill=min max rho_adj (lead-lag);fallback<3;ERC cap40%;GC75 k->x;leg=gold(AUM max)->MMF;SR12' real rf;quality S;full universe",
           "period_start": "2022-03-31", "period_end": "2025-12-31", "rf_source": "BOT policy rate daily (TH_POLICY_RATE.csv)",
           "cost_assumption": "real fees SecFundFee FEEUH (full; FeeData legacy=False; E/F/O separate)",
           "sharpe": round(res["sharpe_full"], 4), "cagr": round(res["cagr_full"], 4), "vol": round(res["vol"], 4), "max_dd": round(res["max_dd"], 4),
           "turnover": round(res["turn_yr"], 4), "n_trials_cumulative": 47, "deflated_sharpe": round(res["dsr47"], 4), "status": "ok",
           "notes": (f"POST-HOC LABEL (สืบทอด M019 + ขาทอง); dSharpe vs M018-N5-GCGOLD {dpt:.3f} CI ({dlo:.3f};{dhi:.3f}); "
                     f"Sharpe 0%={res['sharpe_c0']:.3f} flat={res['sharpe_flat']:.3f} nofront={res['sharpe_nofront']:.3f}; "
                     f"CI95 ({lo:.3f};{hi:.3f}); offset {om.min():.3f}-{om.max():.3f}")}
    eol = "\r\n" if raw.count(b"\r\n") > raw.count(b"\n") / 2 else "\n"
    buf = io.StringIO()
    csv.writer(buf, lineterminator=eol).writerow([str(row[c]) for c in cols])
    with open(TRIALS, "ab") as f:
        f.write((b"" if raw.endswith(b"\n") else eol.encode()) + buf.getvalue().encode("utf-8"))
    pd.set_option("display.width", 250)
    print(pd.Series(res).to_string())
    print(OFF.to_string())
    print(pd.DataFrame(qlog).to_string())
    print(f"done {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
