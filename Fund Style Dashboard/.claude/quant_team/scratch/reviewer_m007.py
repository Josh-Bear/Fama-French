import pandas as pd, numpy as np
R=".claude/quant_team/backtest/results/"
for n in ["M007-6M","M007-12M","M006-TC","M006-TCQ"]:
    w=pd.read_csv(R+n+"_weights.csv")
    print(n, w.columns.tolist())
    f=w[w.kind=="full"] if "kind" in w else w
    print(f.groupby("offset").t.unique().apply(lambda a:list(a)).to_string())
    # cash/equity per entry
    eq=w[w.FundCode!="__CASH__"].groupby(["offset","t"]).weight.sum()
    cs=w[w.FundCode=="__CASH__"].groupby(["offset","t"]).weight.sum()
    print("equity sum range",eq.min().round(3),eq.max().round(3),"cash max",cs.max() if len(cs) else 0)
    print(w.groupby("offset").kind.value_counts().to_string())
# TC vs TCQ cumulative
def load(n): return pd.read_csv(R+f"M006-M007_{n}_equity_curve.csv",index_col=0,parse_dates=True).iloc[:,0]
a,b,c=load("M006-TC"),load("M006-TCQ"),load("M004-TF-FX")
print(a.iloc[[0,1,-1]].round(2).tolist(),b.iloc[-1].round(2),c.iloc[-1].round(2))
print(c.iloc[:3].round(3).tolist())
ra,rb=a.pct_change().dropna(),b.pct_change().dropna()
d=(ra-rb); print("sum diff",d.sum().round(4)); 
for lo,hi in [("2022-04","2022-12"),("2023-01","2023-12"),("2024-01","2024-12"),("2025-01","2025-12")]:
    print(lo,round(d[lo:hi].sum(),4))
