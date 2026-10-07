import sys,os,pickle
ROOT="/Users/doyinratnavardhana/Fama French/Fund Style Dashboard"
sys.path.insert(0,ROOT); sys.path.insert(0,ROOT+"/.claude/quant_team/backtest"); os.chdir(ROOT)
import pandas as pd, numpy as np
import common, fees, simulate
import run_m009 as r9
nav=common.load_nav(); nbf=common.build_nav_by_fund(nav); cal=common.load_calendar()
codes=sorted(nav.FundCode.unique())
P=pickle.load(open(ROOT+"/.claude/quant_team/scratch/validator_fee_plans.pkl","rb"))
q=common.quarter_ends(cal,"2022-03-31","2025-09-30")
months=[m for m in common.month_ends(cal, common.execution_date(cal,q[0]),"2026-03-31") if m<=q[-1]+pd.Timedelta(days=75)+pd.Timedelta(days=31)]
for lg in (True,False):
    fd=fees.FeeData(codes,legacy=lg)
    for tid in ("B0","M004-TF-FX"):
        res=[]
        for plan in P[tid]:
            clean=[{k:v for k,v in p.items() if k in("t","e","weights")} for p in plan]
            res.append(r9.sim_cases(clean,nbf,months,fd)["full"]["metrics"]["sharpe"])
        print(lg,tid,len(res),np.mean(res))
