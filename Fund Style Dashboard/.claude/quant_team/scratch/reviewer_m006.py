import sys; sys.path.insert(0,"."); sys.path.insert(0,".claude/quant_team/backtest")
import pandas as pd, numpy as np, re
import common, fund_signals as fs, simulate
R=".claude/quant_team/backtest/results/"
groups=common.load_groups()
w=pd.read_csv(R+"M004-TF-FX_weights.csv")
w=w[w.FundCode!="__CASH__"]
w["fam"]=[fs.family_of(f,groups,True)[0] for f in w.FundCode]
g=w.groupby(["t","fam"]).weight.sum().reset_index()
print("n_quarters",w.t.nunique(),"max fam weight",g.weight.max())
print("fam held twice:",(w.groupby(["t","fam"]).FundCode.nunique()>1).sum())
print("max fund w",w.weight.max()); print(g.sort_values("weight",ascending=False).head(6))
print("sum w per q (equity)",w.groupby("t").weight.sum().round(3).to_dict())
# theme concentration: top families by avg weight
print(g.groupby("fam").weight.mean().sort_values(ascending=False).head(8))
# AMC proxy: first token
w["amc"]=w.FundCode.str.split(r"[-\s]").str[0]
a=w.groupby(["t","amc"]).weight.sum().reset_index(); print(a.sort_values("weight",ascending=False).head(6)); print("amc>25% quarters",(a.weight>0.25).sum(),"of",w.t.nunique())
# other family leaks: same family core ignoring suffixes
w["core"]=w.FundCode.str.replace(r"[-\s](H|UH|F|U|A|D|E|P|I|R|X|RA|RD)\b","",regex=True)
print("core dup", (w.groupby(["t","core"]).FundCode.nunique()>1).sum())
for t,gr in w.groupby("t"):
    print(t, [ (f,round(x,3)) for f,x in zip(gr.FundCode,gr.weight)])
# equity curves
def load(n):
    s=pd.read_csv(R+f"M006-M007_{n}_equity_curve.csv",index_col=0,parse_dates=True).iloc[:,0]; return s
rf=0.02
res={}
for n in ["M004-TF-FX","M006-TC","M006-TCQ"]:
    s=load(n); r=simulate.monthly_returns(s); res[n]=r
    print(n,round(simulate.sharpe(r,rf),3),len(r))
# drop best quarter (calendar quarter blocks of the monthly returns) for FX
for n in ["M004-TF-FX","M006-TC","M006-TCQ"]:
    r=res[n]; qs=r.groupby(r.index.to_period("Q")).apply(lambda x:(1+x).prod()-1)
    best=qs.idxmax(); r2=r[r.index.to_period("Q")!=best]
    r3=r[~r.index.to_period("Q").isin(qs.nlargest(2).index)]
    print(n,"best Q",best,round(qs.max(),3),"Sharpe drop1",round(simulate.sharpe(r2,rf),3),"drop2",round(simulate.sharpe(r3,rf),3))
    r12=r[(r.index>="2022-04-01")&(r.index<="2022-12-31")]
    v=load(n); v22=v[v.index<="2022-12-31"]
    print("  2022 ret",round(v22.iloc[-1]/100-1,4),"maxDD22",round((v22/v22.cummax()-1).min(),4),"vol",round(r12.std()*12**.5,3))
# TC vs TCQ monthly diff
d=(res["M006-TC"]-res["M006-TCQ"]); 
x=pd.DataFrame({"TC":res["M006-TC"],"TCQ":res["M006-TCQ"],"FX":res["M004-TF-FX"],"d":d})
print(x.round(4).to_string())
print("cum d top neg months"); print(d.sort_values().head(6).round(4)); print(d.sort_values().tail(4).round(4))
