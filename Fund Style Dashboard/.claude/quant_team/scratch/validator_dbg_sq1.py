import sys,os
sys.path.insert(0,"."); sys.path.insert(0,".claude/quant_team/backtest")
import run_m008 as m, common, fund_signals as fs, numpy as np, pandas as pd
nav=common.load_nav(); arr=fs._prep_arrays(common.build_nav_by_fund(nav)); cal=common.load_calendar(); g=common.load_groups(); fd=m.build_factor_daily()
qs=common.quarter_ends(cal,"2022-03-31","2025-09-30")[:15]
state={s:({},False) for s in m.STREAMS}
for t in qs:
    q=m.select_quarter(t,nav,arr,cal,g,fd,state)
    a,b=q["streams"]["BASE"],q["streams"]["SQ_T1"]
    print(t.date(), a["S"]==b["S"], list(a["S"].values())==list(b["S"].values()), (a["sleeve"]-b["sleeve"].reindex(a["sleeve"].index)).abs().max() if not a["fb"] else "fb")
    z=q["scores"]["SQ_T1"]; print(" n |z|=3:", int((z.abs()>=3).sum()))
    for s in state: state[s]=(dict(q["streams"][s]["S"]),q["streams"][s]["fb"])
