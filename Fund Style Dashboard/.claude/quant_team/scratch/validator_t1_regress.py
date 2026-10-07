import sys,os
ROOT="/Users/doyinratnavardhana/Fama French/Fund Style Dashboard"
sys.path.insert(0,ROOT); sys.path.insert(0,ROOT+"/.claude/quant_team/backtest"); os.chdir(ROOT)
import pandas as pd, numpy as np
import common, fees, simulate
import run_m009 as r9, run_m006_m007 as r67
nav=common.load_nav(); nbf=common.build_nav_by_fund(nav); cal=common.load_calendar()
codes=sorted(nav.FundCode.unique())
for lg in (True, False):
    fd=fees.FeeData(codes, legacy=lg); print("legacy",lg,"rows",fd.n_rows,"invalid",fd.n_invalid, fd.median)
    q=common.quarter_ends(cal,"2022-03-31","2025-09-30")
    months=[m for m in common.month_ends(cal, common.execution_date(cal,q[0]),"2026-03-31") if m<=q[-1]+pd.Timedelta(days=75)+pd.Timedelta(days=31)]
    # trend 25 plan from csv weights
    for tid,f in (("M004-TF-FX","M004-TF-FX_weights.csv"),):
        d=pd.read_csv(common.RESULTS_DIR+"/"+f,parse_dates=["t","e"]) 
        print(d.columns.tolist()[:6]); 
        plan=[{"t":t,"e":e,"weights":dict(zip(g.FundCode,g.weight))} for (t,e),g in d.groupby(["t","e"],sort=True)]
        sims=r9.sim_cases(plan,nbf,months,fd)
        print(tid,{k:round(sims[k]["metrics"]["sharpe"],6) for k in ("full","flat","nofront")})
