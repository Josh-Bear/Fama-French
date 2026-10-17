"""S007 โครงข้อมูล ส่วน 2 — กลุ่ม / คุณลักษณะ (ไม่อ่านผลตอบแทน · ไม่อ่านคอลัมน์ผล)"""
import json, re, sys
from pathlib import Path
import pandas as pd
ROOT = Path(__file__).resolve().parents[3]; T = ROOT/".claude"/"factor_team"; o = {}
ev = pd.read_csv(T/"runs/S003/fund_level.csv", usecols=["form","FundCode","policy","in_EVAL"])
ev = ev[(ev.form=="1a") & (ev.in_EVAL)].drop_duplicates("FundCode")[["FundCode","policy"]]
o["EVAL_n"] = int(len(ev)); o["EVAL_pol"] = ev.policy.value_counts().to_dict()
U = pd.read_csv(T/"data/universe.csv"); e = ev.merge(U[["FundCode","family","div_flag"]], on="FundCode", how="left")
o["div_in_EVAL"] = e.groupby("policy").div_flag.apply(lambda s: int(s.astype(str).str.upper().isin(["TRUE","1","Y"]).sum())).to_dict()
o["div_flag_values"] = U.div_flag.astype(str).value_counts().to_dict()
pi = pd.read_csv(T/"runs/S005/primary_index.csv", usecols=["form","FundCode","index"])
o["pi_forms"] = sorted(pi.form.unique().tolist())
fc = pd.read_csv(T/"runs/S005/fund_clusters.csv", usecols=["FundCode","group_id"])
for form in ["none","1a@4","1c@4"]:
    p = pi[pi.form==form][["FundCode","index"]].merge(e, on="FundCode").merge(fc, on="FundCode", how="left")
    g = p.groupby("index").agg(n=("FundCode","size"), nE=("policy",lambda s:int((s=="E").sum())), nF=("policy",lambda s:int((s=="F").sum())), nO=("policy",lambda s:int((s=="O").sum())), n_indep=("group_id","nunique")).sort_values("n", ascending=False)
    o[f"groups_{form}"] = g.reset_index().values.tolist()
    o[f"groups_{form}_ge10"] = int((g.n>=10).sum()); o[f"groups_{form}_5to9"] = int(((g.n>=5)&(g.n<10)).sum()); o[f"groups_{form}_lt5"] = int((g.n<5).sum())
o["clusters_in_EVAL"] = int(fc[fc.FundCode.isin(ev.FundCode)].group_id.nunique())
o["MGAG_MGAPVD_in_EVAL"] = [c for c in ["MGAG","MGAPVD","M-SUKUK"] if c in set(ev.FundCode)]
dp = pd.read_csv(T/"data/dup_pairs.csv"); o["dup_cols"]=list(dp.columns)
a,b = dp.columns[0], dp.columns[1]; s=set(ev.FundCode)
o["dup_pairs_both_in_EVAL"] = int(((dp[a].isin(s))&(dp[b].isin(s))).sum())
# twin hedge/unhedge ใน EVAL (จากชื่อ · โครงเท่านั้น)
def stem(c): return re.sub(r"[-(]?(UH|H)\)?(?=([-(]|$))", "", c)
codes = sorted(s); st = {}
for c in codes:
    if re.search(r"(^|[-(])(UH|H)(\)|[-(]|$)", c): st.setdefault(stem(c), []).append(c)
o["hedge_named_in_EVAL"] = st
FP = pd.read_csv(ROOT/"base_data/FundProfile.csv", dtype=str, usecols=["Fund Code","Register ID","Fund Policy","FIF Flag","Dividend_Flag","FX Risk Flag","Registration_date","AMC_CODE","Fund Class","Previous Fund Code"])
fpe = FP[FP["Fund Code"].isin(s)]
o["FP_rows_EVAL"] = int(fpe["Fund Code"].nunique())
for c in ["FIF Flag","Dividend_Flag","FX Risk Flag"]: o["FP_"+c] = fpe[c].value_counts(dropna=False).to_dict()
o["FP_RegisterID_example"] = fpe["Register ID"].head(3).tolist()
o["FP_Registration_nonnull"] = int(fpe.Registration_date.notna().sum())
fee = pd.read_csv(ROOT/"base_data/SecFundFee.csv", dtype=str, encoding="utf-8-sig")
o["fee_cols"] = list(fee.columns); o["fee_asof_n"] = int(fee["As of Date"].nunique()); o["fee_asof_range"] = [fee["As of Date"].min(), fee["As of Date"].max()]
o["fee_complex"] = fee["Complex Type Code"].value_counts().head(12).to_dict()
o["fee_codes_FEEMF"] = fee[fee["Complex Type Code"]=="FEEMF"]["Code"].value_counts().to_dict()
o["fee_fundcode_nuniq"] = int(fee["Fund Code"].nunique())
# key mapping: SecFundFee Fund Code ↔ FundProfile Register ID / Fund Code
fpall = FP.copy()
for k in ["Register ID","Fund Code","Previous Fund Code"]:
    o["fee_key_overlap_"+k] = int(fee["Fund Code"].isin(set(fpall[k].dropna())).sum())
m = fpe[["Fund Code","Register ID"]].dropna()
o["EVAL_with_fee_via_RegisterID"] = int(m["Register ID"].isin(set(fee["Fund Code"])).sum())
o["EVAL_with_TT_via_RegisterID"] = int(m["Register ID"].isin(set(fee[(fee["Complex Type Code"]=="FEEMF")&(fee.Code=="TT")]["Fund Code"])).sum())
o["fee_actual_nonnull_frac_TT"] = float(fee[(fee["Complex Type Code"]=="FEEMF")&(fee.Code=="TT")]["Actual Value"].notna().mean())
o["fee_rows_per_fund_TT_max"] = int(fee[(fee["Complex Type Code"]=="FEEMF")&(fee.Code=="TT")].groupby("Fund Code").size().max())
json.dump(o, sys.stdout, ensure_ascii=False, default=str); print()
