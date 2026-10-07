"""validator_fee_recalc.py — COST_real_fees: คำนวณทุก trial ใหม่ภายใต้ค่าธรรมเนียมจริง (full / nofront) + regression
เขียนเฉพาะ: results/COST_real_fees_summary.csv, results/COST_real_fees_results.md (ไฟล์ใหม่) · ไม่แตะไฟล์ผลเดิม"""
import os, sys, pickle, time, json
ROOT = "/Users/doyinratnavardhana/Fama French/Fund Style Dashboard"
BT = ROOT + "/.claude/quant_team/backtest"
SC = ROOT + "/.claude/quant_team/scratch"
sys.path.insert(0, ROOT); sys.path.insert(0, BT); os.chdir(ROOT)
import numpy as np, pandas as pd
import common, fund_signals as fs, simulate, weighting as wt, fees
import run_m006_m007 as r67
import run_m002_m005 as r25
from data import msci_index

SMOKE = "smoke" in sys.argv
PE, RF = r67.PRIMARY_END, 0.02
nav = common.load_nav(); nav_by_fund = common.build_nav_by_fund(nav); nav_arrays = fs._prep_arrays(nav_by_fund)
calendar = common.load_calendar(); groups = common.load_groups()
acwi = msci_index.load_country_index()["MSCI_ACWI"]
p67 = pickle.load(open(SC + "/validator_plans_r67.pkl", "rb")); p8 = pickle.load(open(SC + "/validator_plans_r8.pkl", "rb"))
MONTHS = p67[2]["months"]
CLEAN = ("t", "e", "weights", "mode", "equity", "sleeve")
cl = lambda plan: [{k: v for k, v in p.items() if k in CLEAN} for p in plan]
FD = fees.FeeData(sorted(nav["FundCode"].unique()))
print("fee medians", FD.median, "rows", FD.n_rows, "invalid", FD.n_invalid, "funds", FD.n_funds_fee, flush=True)

PLANS = {}   # trial -> (list of plans, include_start)
INC = {}
# --- r67 / r8 captured
PLANS["M004-TF-FX"] = [cl(p67[2]["plan"])]; PLANS["M006-TC"] = [cl(p67[4]["plan"])]; PLANS["M006-TCA"] = [cl(p67[5]["plan"])]
PLANS["M006-TCQ"] = [cl(p67[6]["plan"])]; PLANS["M007-6M"] = [cl(p67[i]["plan"]) for i in (7, 8)]
PLANS["M007-12M"] = [cl(p67[i]["plan"]) for i in (9, 10, 11, 12)]
PLANS["M008-GC"] = [cl(p8[1]["plan"])]; PLANS["M008-SQ"] = [cl(p8[3]["plan"])]
base8 = cl(p8[0]["plan"])
# --- M001 จาก quarterly_weights.csv (selection เดิมของหน้า 8, ไม่ refit)
qw = pd.read_csv(common.RESULTS_DIR + "/M001_quarterly_weights.csv", parse_dates=["t"])
qs = common.quarter_ends(calendar, "2022-03-31", "2025-09-30")
m1_chk = {}
for var, tid in (("B0", "B0"), ("MS", "M001-MS"), ("EW", "M001-EW")):
    plan = []
    for t in qs:
        g = qw[(qw["variant"] == var) & (qw["t"] == t)]
        w = dict(zip(g["FundCode"], g["weight"]))
        m1_chk[(tid, t)] = sum(w.values())
        plan.append({"t": t, "e": common.execution_date(calendar, t), "weights": w})
    PLANS[tid] = [plan]
print("M001 weight sums min/max", min(m1_chk.values()), max(m1_chk.values()), flush=True)

# --- M002-M005 ด้วย family map ใหม่ (family_fix=True)
rec = {tid: [] for tid in r25.TRIALS}
held = {k: {} for k in r25.SELECTIONS}; prevfb = {k: False for k in r25.SELECTIONS}
for qi, t in enumerate(qs if not SMOKE else qs[:2]):
    e = common.execution_date(calendar, t)
    u_t = common.universe_at(nav, t); b0_df = common.b0_universe(u_t, groups)
    b0w = pd.Series(1.0 / len(b0_df), index=b0_df["FundCode"])
    qctx = fs.QuarterContext(nav_arrays, calendar, t)
    sig = fs.compute_quarter_signals(qctx, u_t["FundCode"].tolist())
    i_t, _, _ = fs.investable_set(t, u_t, sig, groups, family_fix=True)
    wr = {fc: qctx.weekly_return_series(fc) for fc in i_t["FundCode"]}
    v52 = dict(zip(i_t["FundCode"], i_t["vol52"]))
    sel_out = {}
    for k, p in r25.SELECTIONS.items():
        reps = wt.family_representatives(i_t, p["signal"], held_funds=set(held[k].values()))
        ranks = wt.rank_families(reps)
        sel = wt.hysteresis_select(reps, ranks, {} if prevfb[k] else held[k], p["N"], p["K"], wr if p["dedupe"] else None, rho_max=0.85)
        sel_out[k] = sel
        if sel["fallback"] == "b0": held[k] = {}; prevfb[k] = True
        else: held[k] = dict(sel["S"]); prevfb[k] = False
    wc = {}
    def getw(k, m):
        if (k, m) in wc: return wc[(k, m)]
        sel = sel_out[k]
        if sel["fallback"] == "b0" or not len(sel["S"]): wc[(k, m)] = None; return None
        fl = list(sel["S"].values())
        w = pd.Series(1.0 / len(fl), index=fl) if m == "EW" else wt.risk_parity_weights(fl, wr, v52, method="erc" if m == "ERC" else "hrp")[0]
        wc[(k, m)] = wt.apply_cap(w, 0.25); return wc[(k, m)]
    for tid, cfg in r25.TRIALS.items():
        w = getw(cfg["sel"], cfg["weight"])
        if w is None:
            wf, c = b0w.to_dict(), 0.0
        else:
            cv = ct = 0.0
            if cfg["overlay"] in ("VT", "MAX"): cv, _ = wt.vol_target_cash(w, wr, sigma_star=0.10)
            if cfg["overlay"] in ("TF", "MAX"): ct = wt.trend_filter_cash(acwi, t, 0.25)
            c = {"VT": cv, "TF": ct, "MAX": min(0.25, max(cv, ct)), None: 0.0}[cfg["overlay"]]
            wf = {fc: (1 - c) * wv for fc, wv in w.items() if wv > 0}
            if c > 0: wf["__CASH__"] = c
        rec[tid].append({"t": t, "e": e, "weights": wf})
    print(f"  M002-5 [{qi+1}/{len(qs)}] {t.date()} I_t={len(i_t)}", flush=True)
for tid in r25.TRIALS: PLANS[tid] = [rec[tid]]
# cross-check: M004-TF (family_fix) == M004-TF-FX captured?
d = max(abs(a["weights"].get(f, 0) - b["weights"].get(f, 0)) for a, b in zip(PLANS["M004-TF"][0], PLANS["M004-TF-FX"][0]) for f in set(a["weights"]) | set(b["weights"])) if not SMOKE else -1
print("M004-TF(new map) vs M004-TF-FX max|dw| =", d, flush=True)
NTR = {"B0": 0, "M001-MS": 1, "M001-EW": 2, **{t: c["n_trials_cum"] for t, c in r25.TRIALS.items()}, "M004-TF-FX": 9,
       "M006-TC": 14, "M006-TCA": 15, "M006-TCQ": 16, "M007-6M": 17, "M007-12M": 18, "M008-GC": 19, "M008-SQ": 20}
ORDER = ["B0", "M001-MS", "M001-EW", "M002-SR", "M002-MOM", "M002-NOH", "M003-ERC", "M003-HRP", "M004-VT", "M004-TF", "M005",
         "M005-N5", "M005-N10", "M005-NODD", "M004-TF-FX", "M006-TC", "M006-TCA", "M006-TCQ", "M007-6M", "M007-12M", "M008-GC", "M008-SQ"]
if SMOKE: ORDER = ["M004-TF-FX", "M001-MS"]

def run_case(plan, cost_side, fm, inc):
    info = {}
    v, tu, ev, _ = simulate.simulate_path(plan, nav_by_fund, MONTHS, cost_side, RF, include_start=inc, info=info, fee_model=fm)
    ent = [x for x in info["entries"] if x["e"] <= PE]
    return v, ent

def case(tid, kind):
    """kind: c0, c50, flat (fee model flat .5%), full, nofront -> (values mean over tranches, cost fraction sum/tranche, fm totals)"""
    vals, costs, tot = [], [], {"sell_vol": 0.0, "buy_vol": 0.0, "switch_vol": 0.0}
    for plan in PLANS[tid]:
        fm = {"full": lambda: fees.FeeModel(FD, "full"), "nofront": lambda: fees.FeeModel(FD, "nofront"),
              "flat": lambda: fees.FeeModel(None, "flat", 0.005)}.get(kind, lambda: None)()
        cs = {"c0": 0.0, "c50": 0.005}.get(kind, 0.0)
        v, ent = run_case(plan, cs, fm, True)
        vals.append(v); costs.append(sum(x["cost"] for x in ent))
        if fm:
            for k in tot: tot[k] += fm.tot[k] / 1.0
    v = pd.concat(vals, axis=1).mean(axis=1) if len(vals) > 1 else vals[0]
    n = len(PLANS[tid])
    return v, float(np.mean(costs)), {k: x / n for k, x in tot.items()}

rows, reg = [], []
t0 = time.time()
for tid in ORDER:
    e_first = PLANS[tid][0][0]["e"]; yrs = (PE - e_first).days / 365.25
    out = {"trial": tid, "n_trials_cum": NTR[tid]}
    cases = {k: case(tid, k) for k in ("c0", "c50", "flat", "full", "nofront")}
    mx = float((cases["flat"][0] - cases["c50"][0]).abs().max())
    reg.append((tid, mx, abs(cases["flat"][1] - cases["c50"][1])))
    for k, tag in (("c0", "c0"), ("c50", "c50"), ("full", "full"), ("nofront", "nofront")):
        m = r67.per_metrics(cases[k][0], RF)
        out.update({f"sharpe_{tag}": m["sharpe"], f"cagr_{tag}": m["cagr"], f"vol_{tag}": m["vol"], f"maxdd_{tag}": m["max_dd"],
                    f"cost_bp_yr_{tag}": cases[k][1] / yrs * 1e4})
    for tag in ("full", "nofront"):
        tot = cases[tag][2]
        out[f"switch_share_{tag}"] = tot["switch_vol"] / tot["sell_vol"] if tot["sell_vol"] > 0 else np.nan
        out[f"avg_fee_pct_{tag}"] = cases[tag][1] / (tot["sell_vol"] + tot["buy_vol"]) * 100 if tot["buy_vol"] + tot["sell_vol"] > 0 else np.nan
    r_full = simulate.monthly_returns(cases["full"][0][cases["full"][0].index <= PE])
    out["dsr20_full"] = simulate.deflated_sharpe(r_full, RF, 20)
    out["n_months"] = len(r_full)
    rows.append(out)
    print(f"{tid:12s} S0={out['sharpe_c0']:.3f} S50={out['sharpe_c50']:.3f} full={out['sharpe_full']:.3f} nofront={out['sharpe_nofront']:.3f} "
          f"bp50={out['cost_bp_yr_c50']:.0f} full={out['cost_bp_yr_full']:.0f} nof={out['cost_bp_yr_nofront']:.0f} sw={out['switch_share_full']:.2f} "
          f"regMax={mx:.1e} ({time.time()-t0:.0f}s)", flush=True)
summ = pd.DataFrame(rows)
print("fallback counts", dict(FD.n_fallback))
print("REG max|Δvalues| flat-fee vs cost_side=0.5%:", max(r[1] for r in reg), "max|Δcost|", max(r[2] for r in reg), flush=True)
# regression ของวิธีวัดเดิม (ไม่นับเดือนแรก) ต่อ M001 เทียบ summary เดิม
old = {}
for tid in ("B0", "M001-MS", "M001-EW"):
    v, _ = run_case(PLANS[tid][0], 0.005, None, False)
    old[tid] = r67.per_metrics(v, RF)["sharpe"]
print("old-measure regression M001:", old, flush=True)
if not SMOKE:
    summ.to_csv(common.RESULTS_DIR + "/COST_real_fees_summary.csv", index=False)
    json.dump({"median": FD.median, "rows": FD.n_rows, "invalid": FD.n_invalid, "fallback": dict(FD.n_fallback),
               "reg_max_dv": max(r[1] for r in reg), "reg_max_dcost": max(r[2] for r in reg), "old_regression": old,
               "tf_vs_fx": d, "w_sum_range": [min(m1_chk.values()), max(m1_chk.values())]}, open(SC + "/validator_fee_meta.json", "w"))
    pickle.dump(PLANS, open(SC + "/validator_fee_plans.pkl", "wb"))
