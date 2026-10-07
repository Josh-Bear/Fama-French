import pandas as pd, numpy as np
R=".claude/quant_team/backtest/results/"
w=pd.read_csv(R+"M006-TC_weights.csv",parse_dates=["t","e"])
s=w[(w.kind=="scale")&(w.FundCode!="__CASH__")]
nav=pd.read_parquet("cache/nav_clean.parquet",columns=["FundCode","NAVDate","NAV"],filters=[("FundCode","in",list(s.FundCode.unique()))])
nav["NAVDate"]=pd.to_datetime(nav.NAVDate)
g={k:v.sort_values("NAVDate").NAVDate.values for k,v in nav.groupby("FundCode")}
gaps=[];fw=[]
for _,r in s.iterrows():
    d=g[r.FundCode]; i=np.searchsorted(d,np.datetime64(r.e),side="right")-1
    back=(r.e-pd.Timestamp(d[i])).days if i>=0 else 999
    j=np.searchsorted(d,np.datetime64(r.e),side="left")
    fwd=(pd.Timestamp(d[j])-r.e).days if j<len(d) else 999
    gaps.append(back); fw.append(fwd)
gaps=np.array(gaps);fw=np.array(fw)
print(len(gaps),"back>0:",(gaps>0).mean().round(3),"back>=3d",(gaps>=3).mean().round(3),"max",gaps.max(),"| fwd>0",(fw>0).mean().round(3))
