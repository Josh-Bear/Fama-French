"""quant-modeler M009 feasibility: fee stats only (read-only, no returns/Sharpe)."""
import sys; sys.path.insert(0, ".")
import pandas as pd, numpy as np
from analysis.fund_fees import FeeData
w = pd.read_csv(".claude/quant_team/backtest/results/M004-TF-FX_weights.csv", parse_dates=["t","e"])
w = w[(w.trial=="M004-TF-FX") & (w.FundCode!="__CASH__")]
nav = pd.read_parquet("cache/nav_clean.parquet", columns=["FundCode"])
codes = sorted(nav.FundCode.unique())
fd = FeeData(codes)
print("median fallback", fd.median, "missing-code", fd.median_fallback)
d = pd.read_csv("base_data/SecFundFee.csv", dtype=str, encoding="utf-8-sig")
d = d[(d["Complex Type Code"]=="FEEUH") & d.Code.isin(["FF","BF","SI","SO"]) & d["Fund Code"].isin(codes)]
print("snapshots", sorted(d["As of Date"].unique())[:3], "...", sorted(d["As of Date"].unique())[-2:], "n", d["As of Date"].nunique())
t = pd.Timestamp("2025-12-31")
rows=[]
for fc in codes:
    r={c: fd.rate(fc,c,t) for c in ["FF","BF","SI","SO"]}; r["fc"]=fc; r["amc"]=fd.amc.get(fc); rows.append(r)
f = pd.DataFrame(rows); f["RT"]=f.FF+f.BF
print("all 570 @2025-12: RT quantiles", f.RT.quantile([.1,.25,.5,.75,.9]).round(2).to_dict(), "share FF==0", round((f.FF==0).mean(),3), "share BF>0", round((f.BF>0).mean(),3))
held = f[f.fc.isin(w.FundCode.unique())]
print("ever-held by M004-TF-FX:", len(held), "RT quantiles", held.RT.quantile([.1,.5,.9]).round(2).to_dict(), "SI<FF share", round((held.SI<held.FF).mean(),2))
# entries per quarter in M004-TF-FX (new funds) and holding length in quarters
qs = sorted(w.t.unique()); prev=set(); new=[]; 
for q in qs:
    cur=set(w[w.t==q].FundCode); new.append(len(cur-prev)); prev=cur
print("quarters", len(qs), "new funds per quarter", new)
spell = w.groupby("FundCode").t.nunique()
print("held-quarters per fund: mean", round(spell.mean(),2), "median", spell.median())
