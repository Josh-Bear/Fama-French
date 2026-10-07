"""Read-only: full-fee equity curves for the mentor report (reuses validator_fee_plans.pkl). Writes only to scratchpad."""
import os, sys, pickle, json
ROOT = os.getcwd(); BT = ROOT + "/.claude/quant_team/backtest"; SC = ROOT + "/.claude/quant_team/scratch"
sys.path.insert(0, ROOT); sys.path.insert(0, BT)
import pandas as pd, numpy as np
import common, simulate, fees, run_m006_m007 as r67
OUT = sys.argv[1]
PE, RF = r67.PRIMARY_END, 0.02
nav = common.load_nav(); nbf = common.build_nav_by_fund(nav)
p67 = pickle.load(open(SC + "/validator_plans_r67.pkl", "rb")); MONTHS = p67[2]["months"]
PLANS = pickle.load(open(SC + "/validator_fee_plans.pkl", "rb"))
FD = fees.FeeData(sorted(nav["FundCode"].unique()))
summ = pd.read_csv(BT + "/results/COST_real_fees_summary.csv").set_index("trial")
res = {"curves": {}, "years": {}, "metrics": []}
for tid, plans in PLANS.items():
    vals = []
    for plan in plans:
        v, *_ = simulate.simulate_path(plan, nbf, MONTHS, 0.0, RF, include_start=True, fee_model=fees.FeeModel(FD, "full"))
        vals.append(v)
    e = (pd.concat(vals, axis=1).mean(axis=1) if len(vals) > 1 else vals[0])
    e = e[e.index <= PE]
    res["curves"][tid] = [[d.strftime("%Y-%m-%d"), round(float(x), 2)] for d, x in e.items()]
    yy = {}
    for y in (2022, 2023, 2024, 2025):
        prev = e[e.index < pd.Timestamp(f"{y}-01-01")]; s0 = prev.iloc[-1] if len(prev) else e.iloc[0]
        yy[str(y)] = round(float(e[e.index <= pd.Timestamp(f"{y}-12-31")].iloc[-1] / s0 - 1), 4)
    res["years"][tid] = yy
    s = summ.loc[tid]
    r = simulate.monthly_returns(e)
    res["metrics"].append(dict(id=tid, sharpe=round(s.sharpe_full, 4), cagr=round(s.cagr_full, 4), vol=round(s.vol_full, 4),
        maxdd=round(s.maxdd_full, 4), dsr18=round(s.dsr20_full, 4), psr=round(simulate.deflated_sharpe(r, RF, 1), 4),
        s0=round(s.sharpe_c0, 4), s50=round(s.sharpe_c50, 4), snf=round(s.sharpe_nofront, 4), cost=round(s.cost_bp_yr_full, 1),
        chk=round(float(r67.per_metrics(e, RF)["sharpe"]), 4)))
json.dump(res, open(OUT, "w"), ensure_ascii=False)
print([(m["id"], m["sharpe"], m["chk"]) for m in res["metrics"]])
