import sys; sys.path.insert(0, ".")
import pandas as pd, numpy as np
from data.nav_loader import _detect_and_fix_spikes
d = pd.read_parquet("/private/tmp/claude-501/-Users-doyinratnavardhana-Fama-French/6c152800-b697-48fc-bf2e-df01662e9e0e/scratchpad/fnav.parquet")
p = pd.read_csv("base_data/FundProfile.csv", dtype=str, encoding="utf-8-sig"); p.columns=[c.strip() for c in p.columns]; p=p.drop_duplicates("Fund Code").set_index("Fund Code")
w = d[(d.NAVDate>="2021-01-01")&(d.NAVDate<="2025-12-31")]
F = p[p["Fund Policy"]=="F"]
base = F[(F["Tax Type"].isna())&(F["buy period flag"]=="N")&(F["Project Retail Type"]=="R")&(pd.to_numeric(F["fst_lowbuy_val"],errors="coerce")<=1e5)]
base = base[~base["Fund Name EN"].fillna("").str.contains("Not for Retail|NOT FOR RETAIL|TEST")]
rows=[]
for fc, g in w[w.FundCode.isin(base.index)].groupby("FundCode"):
    if len(g)<252: continue
    v=g.NAV.to_numpy(float); lr=np.diff(np.log(v))
    _,fl=_detect_and_fix_spikes(v)
    rows.append((fc, int(np.sum(fl)), int((np.abs(lr)>0.01).sum()), int((np.abs(lr)>0.05).sum()), float(np.median(np.abs(lr-np.median(lr)))*1.4826), p.loc[fc,"Fund Risk Level"], p.loc[fc,"FIF Flag"]))
r=pd.DataFrame(rows,columns=["fc","spk","n|r|>1%","n|r|>5%","mad","risk","fif"])
print(r[r.spk>0].to_string(index=False))
print("funds with any |r|>5%:", int((r["n|r|>5%"]>0).sum()), "| any |r|>1%:", int((r["n|r|>1%"]>0).sum()), "| domestic with |r|>1%:", int(((r["n|r|>1%"]>0)&(r.fif=="N")).sum()))
print("mad==0 funds:", int((r.mad==0).sum()))
# AUM class vs fund level: families with >1 class in F, same date
fam = p["Fund Class"]
x = w[w.FundCode.isin(F.index)].copy(); x["fam"]=x.FundCode.map(fam)
mc = x.groupby(["fam","NAVDate"]).agg(n=("FundCode","nunique"), nu=("AUM","nunique"))
mc = mc[mc.n>1]
print("multi-class (fam,date) rows:", len(mc), "| share where AUM identical across classes:", round(float((mc.nu==1).mean()),3))
mmf = base[base["Fund Risk Level"].isin(["1","2"])]
print("MMF (risk1-2) eligible names sample:", mmf["Fund Name EN"].head(12).tolist())
print("risk distribution eligible:", base["Fund Risk Level"].value_counts().to_dict())
print("Fund Class missing among eligible:", int(base["Fund Class"].isna().sum()))
