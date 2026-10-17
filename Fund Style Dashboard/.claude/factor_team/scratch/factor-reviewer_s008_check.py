"""S008 review — ตรวจกติกา TER ใหม่ (B.2) และการนับตัวแทน cluster (โครงข้อมูลเท่านั้น · ไม่อ่านค่าผลตอบแทน)"""
import json, re, sys
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[3]; T = ROOT/".claude"/"factor_team"; o = {}
ev = pd.read_csv(T/"runs/S003/fund_level.csv", usecols=["form","FundCode","policy","in_EVAL"])
ev = ev[(ev.form=="1a") & (ev.in_EVAL)].drop_duplicates("FundCode")[["FundCode","policy"]]
fee = pd.read_csv(ROOT/"base_data/SecFundFee.csv", dtype=str, encoding="utf-8-sig")
def num(s):
    if pd.isna(s): return np.nan
    s=str(s).strip()
    if any(w in s for w in ["ไม่มี","ยกเว้น","ไม่เรียกเก็บ"]): return 0.0
    m=re.fullmatch(r"([0-9]*\.?[0-9]+)\s*%?", s); return float(m.group(1)) if m else np.nan
tt = fee[(fee["Complex Type Code"]=="FEEMF")&(fee.Code=="TT")&fee["Fund Code"].isin(set(ev.FundCode))].copy()
tt["d"]=pd.to_datetime(tt["As of Date"],format="%Y%m%d"); tt["a"]=tt["Actual Value"].map(num); tt["r"]=tt["Rate"].map(num)
sel=[]
for f,g in tt.groupby("Fund Code"):
    g=g.sort_values("d"); le=g[g["d"]<="2025-12-31"]; y6=g[g["d"]>="2026-01-01"]
    for name,sub,col in [("le_act",le,"a"),("le_rate",le,"r"),("y26_act",y6,"a"),("y26_rate",y6,"r")]:
        h=sub[sub[col].notna()]
        if len(h): sel.append((f,name,h.iloc[0]["d"],h.iloc[0][col], (y6["a"].dropna().iloc[0] if y6["a"].notna().any() else np.nan))); break
    else: sel.append((f,"nan",pd.NaT,np.nan,np.nan))
S=pd.DataFrame(sel,columns=["FundCode","rule","asof","ter","ter2026act"])
o["counts"]=S.rule.value_counts().to_dict()
le=S[S.rule.str.startswith("le")]; o["le_asof_year"]=le["asof"].dt.year.value_counts().to_dict()
r=S[S.rule=="le_rate"]; rr=r.dropna(subset=["ter2026act"])
o["le_rate_with_2026_actual"]=int(len(rr)); o["le_rate_minus_2026act_median"]=float((rr.ter-rr.ter2026act).median()) if len(rr) else None
o["le_rate_ge_2026act_frac"]=float((rr.ter>=rr.ter2026act-1e-12).mean()) if len(rr) else None
json.dump(o,sys.stdout,default=str,ensure_ascii=False); print()
