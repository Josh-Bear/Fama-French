"""run_m020.py — M020-LC3-GCMMF: การคัดกองของ M019 (อันดับ 1 + correlation ต่ำสุดจาก ≤ 9) แต่ขากัน = กองตลาดเงิน (M015-FAUM)
spec: specs/M020_lowcorr_3fund_mmf.md · trial #46 · DSR@46 · regression = M018-N3-GCMMF ทุกบิต
รัน: PYTHONPATH=. ./.venv/bin/python .claude/quant_team/backtest/run_m020.py
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
import run_m011 as r11
import run_m013 as r13
import run_m015 as r15
import run_m018 as m18
import run_m019 as m19
import fulluniv_run as fu

TEAM = os.path.dirname(THIS)
RES = common.RESULTS_DIR
TRIALS = os.path.join(TEAM, "trials.csv")
MODEL, N_TRIALS, KINDS = "M020-LC3-GCMMF", 46, m18.KINDS


def gc_mmf_plan(E, X, sleeves):
    """สัดส่วนหุ้น GC75 · ส่วนที่เหลือ (รวมส่วนหุ้นที่เหลือจากเพดาน) = กองตลาดเงิน — สูตรน้ำหนักเดียวกับ run_m019.gc_gold_plan."""
    kmap = dict(zip(E["sig"]["t"], E["sig"]["k"]))
    base = []
    for qi, t in enumerate(E["q15"]):
        c = 1.0 - r13.TABLES["GC75"][kmap[t]]
        w = sleeves[qi]
        wf = {fc: (1.0 - c) * float(v) for fc, v in w.items() if v > 0}
        left = (1.0 - c) * (1.0 - float(w.sum())) if 1.0 - float(w.sum()) > 1e-9 else 0.0
        if c + left > 0:
            wf["__CASH__"] = c + left
        base.append({"t": t, "e": common.execution_date(E["calendar"], t), "weights": wf})
    plan = r15.make_plan_F(base, X["sels"]["FAUM"])[0]
    for p in plan:
        assert abs(sum(p["weights"].values()) - 1) < 1e-9, p["t"]
    return plan


def assert_no_future(E):
    """weekly return ที่ใช้คิด ρ_adj / ERC ของทุกกองใน I_t ต้องมีวันที่ ≤ t."""
    for ctx in E["ctx_h"][:15]:
        for fc, s in ctx["wk"].items():
            assert len(s) == 0 or s.index.max() <= ctx["t"], (ctx["t"], fc, s.index.max())


def main():
    t0 = time.time()
    holder = {}
    E, P, X = fu.build_env_and_plans(0, holder)
    FD = holder["FD"]
    assert_no_future(E)
    profile = r15.load_profile()
    f_codes = sorted(FD.profile.index[FD.profile["Fund Policy"] == "F"])
    GD = m18.GData(profile, E, f_codes)                       # ใช้แค่เพื่อให้ fee/nav เส้นทางเดียวกับ M018/M019 (ไม่มีกองทองในพอร์ต)
    fee = m18.Fee3(E["fd_sim"], fees.FeeData(f_codes), f_codes, fees.FeeData(GD.codes), GD.codes)
    nav_all = {**E["nav_by_fund"], **FD.nav_by_fund, **GD.nav_by_fund}
    fset = set(FD.codes) | set(GD.codes)
    real = E["real"]

    def sim(plan, kinds=KINDS, Ex=E):
        return r15.sim_cases_x(plan, nav_all, Ex["months"], fee, real, fset=fset, kinds=kinds, log_full="full" in kinds)

    print("[1/4] regression vs M018-N3-GCMMF", flush=True)
    s_rg, _ = m19.stream_lc(E["ctx_h"], E["quals"], 6, ordered=True)
    plan_rg = gc_mmf_plan(E, X, s_rg)
    ref = pd.read_csv(os.path.join(RES, "M018_weights.csv"), parse_dates=["t"]).query("model == 'M018-N3-GCMMF'")
    m = ref.merge(m18.weights_frame(plan_rg, "x"), on=["t", "FundCode"], how="outer", suffixes=("_ref", "_new"))
    dw = float((m["weight_ref"] - m["weight_new"]).abs().max()) if m[["weight_ref", "weight_new"]].notna().all().all() else np.inf
    base = sim(plan_rg)
    sh_rg = rr.metrics(base["full"]["values"], real)["sharpe"]
    R18 = pd.read_csv(os.path.join(RES, "M018_results.csv")).set_index("model_id")
    sh_ref = float(R18.loc["M018-N3-GCMMF", "sharpe_full"])
    print(f"  max|Δw| {dw:.2e} · Sharpe {sh_rg:.6f} (ref {sh_ref:.6f})", flush=True)
    if not (dw < 1e-12 and abs(sh_rg - sh_ref) < 5e-7):
        print("REGRESSION FAIL — หยุด ไม่บันทึก trial"); sys.exit(2)

    print("[2/4] M020 offset 0", flush=True)
    sleeves, recs = m19.stream_lc(E["ctx_h"], E["quals"], m19.POOL, ordered=False)
    s19, _ = m19.stream_lc(E["ctx_h"], E["quals"], m19.POOL, ordered=False)
    assert all((sleeves[q] == s19[q]).all() for q in range(15))      # การคัดกอง = M019 ทุกบิต (ต่างแค่ขากัน)
    plan = gc_mmf_plan(E, X, sleeves)
    s = sim(plan)
    M = {k: rr.metrics(s[k]["values"], real) for k in KINDS}
    r, rfm = M["full"]["r"], M["full"]["rfm"]
    lo, hi = rr.boot_ci(r, rfm)
    dlo, dhi, dpt = r11.paired_real(r, rr.metrics(base["full"]["values"], real)["r"], rfm)
    GS = m18.gold_sels(GD, E)
    r19 = rr.metrics(sim(m19.gc_gold_plan(E, X, GS, sleeves), ["full"])["full"]["values"], real)["r"]
    glo, ghi, gpt = r11.paired_real(r19, r, rfm)
    res = {"model_id": MODEL, **{f"sharpe_{k}": M[k]["sharpe"] for k in KINDS}, "cagr_full": M["full"]["cagr"],
           "cagr_nofront": M["nofront"]["cagr"], "vol": M["full"]["vol"], "max_dd": M["full"]["max_dd"], "ci_lo": lo, "ci_hi": hi,
           "dsr46": rr.dsr_s(r, rfm, N_TRIALS), **m18.year_returns(s["full"]["values"]), "cost_bp_yr": s["full"]["cost_bp_yr"],
           "turn_yr": s["full"]["turn_yr"], "d_vs_N3GCMMF": dpt, "d_ci_lo": dlo, "d_ci_hi": dhi,
           "d_gold_minus_mmf": gpt, "d_gold_ci_lo": glo, "d_gold_ci_hi": ghi}

    print("[3/4] offset 0/1/2", flush=True)
    off = []
    for k in (0, 1, 2):
        Ek, Pk, Xk = (E, P, X) if k == 0 else fu.build_env_and_plans(k, holder)
        if k:
            assert_no_future(Ek)
        for tag, ordered, pool in ((MODEL, False, m19.POOL), ("M018-N3-GCMMF", True, 6)):
            sl, _ = m19.stream_lc(Ek["ctx_h"], Ek["quals"], pool, ordered)
            w = ro.win_metrics(sim(gc_mmf_plan(Ek, Xk, sl), ["full"], Ek)["full"]["values"], real)
            off.append({"model_id": tag, "offset": k, "sharpe": w["sharpe"], "cagr": w["cagr"], "max_dd": w["max_dd"]})
    OFF = pd.DataFrame(off)
    om = OFF[OFF.model_id == MODEL]["sharpe"]
    res["offset_sharpe_min"], res["offset_sharpe_max"] = om.min(), om.max()

    print("[4/4] บันทึก", flush=True)
    pd.DataFrame([res]).to_csv(os.path.join(RES, "M020_results.csv"), index=False)
    m18.weights_frame(plan, MODEL).to_csv(os.path.join(RES, "M020_weights.csv"), index=False)
    OFF.to_csv(os.path.join(RES, "M020_offsets.csv"), index=False)
    shutil.copy(TRIALS, os.path.join(TEAM, f"trials.backup_{pd.Timestamp.now():%Y%m%dT%H%M%S}.csv"))
    cols = next(csv.reader(open(TRIALS, encoding="utf-8", newline="")))
    raw = open(TRIALS, "rb").read()
    last_n = max(int(float(x["n_trials_cumulative"])) for x in csv.DictReader(open(TRIALS, encoding="utf-8", newline="")) if x["n_trials_cumulative"])
    assert last_n == 45, f"trials.csv อยู่ที่ n = {last_n} ไม่ใช่ 45"
    row = {"model_id": MODEL, "run_at": pd.Timestamp.now().isoformat(), "spec_file": "M020_lowcorr_3fund_mmf.md",
           "params": "M020: = M019 selection (N=3;pool<=9;keep<=9;min max rho_adj) ;ERC cap40%;GC75 k->x;leg=MMF (M015-FAUM);SR12' real rf;quality S;full universe",
           "period_start": "2022-03-31", "period_end": "2025-12-31", "rf_source": "BOT policy rate daily (TH_POLICY_RATE.csv)",
           "cost_assumption": "real fees SecFundFee FEEUH (full; FeeData legacy=False; E/F/O separate)",
           "sharpe": round(res["sharpe_full"], 4), "cagr": round(res["cagr_full"], 4), "vol": round(res["vol"], 4), "max_dd": round(res["max_dd"], 4),
           "turnover": round(res["turn_yr"], 4), "n_trials_cumulative": 46, "deflated_sharpe": round(res["dsr46"], 4), "status": "ok",
           "notes": (f"POST-HOC LABEL (สืบทอด M019); dSharpe vs M018-N3-GCMMF {dpt:.3f} CI ({dlo:.3f};{dhi:.3f}); "
                     f"M019(gold) - M020 {gpt:.3f} CI ({glo:.3f};{ghi:.3f}); Sharpe 0%={res['sharpe_c0']:.3f} flat={res['sharpe_flat']:.3f} "
                     f"nofront={res['sharpe_nofront']:.3f}; CI95 ({lo:.3f};{hi:.3f}); offset {om.min():.3f}-{om.max():.3f}")}
    eol = "\r\n" if raw.count(b"\r\n") > raw.count(b"\n") / 2 else "\n"
    buf = io.StringIO()
    csv.writer(buf, lineterminator=eol).writerow([str(row[c]) for c in cols])
    with open(TRIALS, "ab") as f:
        f.write((b"" if raw.endswith(b"\n") else eol.encode()) + buf.getvalue().encode("utf-8"))
    print(pd.Series(res).to_string())
    print(OFF.to_string())
    print(f"done {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
