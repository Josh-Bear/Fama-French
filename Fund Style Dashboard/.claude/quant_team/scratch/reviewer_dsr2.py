import sys; sys.path.insert(0,".claude/quant_team/backtest"); sys.path.insert(0,".")
import pandas as pd, simulate
R=".claude/quant_team/backtest/results/"
for n in ["M004-TF-FX","M006-TC","M006-TCQ","M007-6M"]:
    s=pd.read_csv(R+f"M006-M007_{n}_equity_curve.csv",index_col=0,parse_dates=True).iloc[:,0]
    r=simulate.monthly_returns(s)
    print(n,[ (k,round(simulate.deflated_sharpe(r,0.02,k),3)) for k in (9,13,18)])
