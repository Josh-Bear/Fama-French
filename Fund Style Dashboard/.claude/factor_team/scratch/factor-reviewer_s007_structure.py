"""S007 spec review — โครงข้อมูลเท่านั้น (ไม่อ่านค่าผลตอบแทน · ไม่ fit model · ไม่อ่านคอลัมน์ผลของ runs/*)
ตรวจ: (1) sha256 ไฟล์ข้อมูลหลักเทียบ spec (2) n_indep เฉพาะ E ต่อกลุ่มหลังรวม MGAPVD→MGAG และตัด M-SUKUK
(3) จำนวนกองที่ครบทุกแถว train ต่อกลุ่ม (ใช้แค่ ret.notna()) (4) SecFundFee TT: as-of แรกสุด · รูปแบบ Actual Value · TT ≥ OF
"""
import hashlib, json, re, sys
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parents[3]; T = ROOT / ".claude" / "factor_team"; o = {}

def sha(p):
    h = hashlib.sha256(); h.update(Path(p).read_bytes()); return h.hexdigest()

spec_sha = {
    "data/panel_weekly.parquet": "95c16ee651d3a936788b7cb3c6372bbf5f1e84cb39daf5680343771dca24270b",
    "data/factors_weekly.parquet": "115b87139d2bec0fd57a77a1593c46d36bb23f3f35f83236cdb07be642af47a8",
    "data/universe.csv": "fdfb7830df78ce032465ac9d8cddc2c98f9aa86cfa0f3925fdb83026aa3f7252",
    "runs/S005/primary_index.csv": "5a94ab9b498bb107600938d37f665c7263d9f0a5973460159c09ae83a799275c",
    "runs/S005/fund_clusters.csv": "072cd97ade7e01a32edb9aaf5b949381d1500dcb1ed909558bee3a373e2fc0cb",
    "runs/S006/fund_level.csv": "2fc1d735f52669d1034707c5d9c0194b087e91aff5dbfb91b2fd59ac4f85f5d2",
    "runs/S006/resid_B_coef.csv": "71af654fc789a24d79999d96d7149e05e75007ac6e8f83d33bd0355d292eef0b",
    "runs/S003/fund_level.csv": "36b41161d6a13c1184a4052d9e799f660f431c2694dc57fafd747f8e695bf8cf",
}
o["sha_match"] = {k: sha(T / k) == v for k, v in spec_sha.items()}
o["sha_match"]["base_data/SecFundFee.csv"] = sha(ROOT / "base_data/SecFundFee.csv") == "94f0b7716a7979303ef6ba063746061d7e454c8e966731b567aa29316f0134cd"
o["data_QA_ACWI_CD_sha"] = sha(T / "data/QA_ACWI_CD_group.md")

ev = pd.read_csv(T / "runs/S003/fund_level.csv", usecols=["form", "FundCode", "policy", "in_EVAL"])
ev = ev[(ev.form == "1a") & (ev.in_EVAL)].drop_duplicates("FundCode")[["FundCode", "policy"]]
fc = pd.read_csv(T / "runs/S005/fund_clusters.csv", usecols=["FundCode", "group_id"])
pi = pd.read_csv(T / "runs/S005/primary_index.csv", usecols=["form", "FundCode", "index"])
p = pi[pi.form == "1a@4"][["FundCode", "index"]].merge(ev, on="FundCode").merge(fc, on="FundCode", how="left")
o["MGAG_MGAPVD_same_cluster"] = bool(fc.set_index("FundCode").loc["MGAG", "group_id"] == fc.set_index("FundCode").loc["MGAPVD", "group_id"])
p = p[p.FundCode != "MGAPVD"]

# (3) ครบทุกแถว train (2021-01-08 .. 2023-12-29) — นับจาก notna เท่านั้น
R = pd.read_parquet(T / "data/panel_weekly.parquet", columns=["FundCode", "date"] + ["ret"])
R = R[R.FundCode.isin(ev.FundCode)]
R["date"] = pd.to_datetime(R["date"])
tr = R[(R.date >= "2021-01-08") & (R.date <= "2023-12-29")]
ntr = tr.assign(ok=tr["ret"].notna()).groupby("FundCode").ok.sum()
del R, tr  # ไม่ใช้ค่า ret
o["train_rows_max"] = int(ntr.max())
full_tr = set(ntr[ntr >= ntr.max()].index)
p["full_train"] = p.FundCode.isin(full_tr)

E = p[(p.policy == "E")]
g = E.groupby("index").agg(nE=("FundCode", "size"), n_indep_E=("group_id", "nunique"),
                           nE_full_train=("full_train", "sum"),
                           n_indep_full_train=("group_id", lambda s: s[E.loc[s.index, "full_train"]].nunique()))
g = g.sort_values("nE", ascending=False)
g["method"] = np.where(g.n_indep_E >= 10, "PCA", np.where(g.n_indep_E >= 5, "LOO-mean", "none"))
o["E_groups"] = g.reset_index().values.tolist()
for pol in ["F", "O"]:
    q = p[p.policy == pol]
    o[f"G_{pol}"] = dict(n=int(len(q)), n_indep=int(q.group_id.nunique()), n_full_train=int(q.full_train.sum()),
                         n_indep_full_train=int(q[q.full_train].group_id.nunique()))
o["E_all"] = dict(n=int(len(E)), n_indep=int(E.group_id.nunique()), n_full_train=int(E.full_train.sum()))

# (4) SecFundFee TT
fee = pd.read_csv(ROOT / "base_data/SecFundFee.csv", dtype=str, encoding="utf-8-sig")
codes = set(ev.FundCode)
mf = fee[(fee["Complex Type Code"] == "FEEMF") & fee["Fund Code"].isin(codes)].copy()
mf["asof"] = pd.to_datetime(mf["As of Date"], format="%Y%m%d")
tt = mf[mf.Code == "TT"]
first = tt.groupby("Fund Code")["asof"].min()
o["TT_first_asof_hist"] = first.dt.year.value_counts().sort_index().to_dict()
o["TT_first_asof_ge2024"] = int((first >= "2024-01-01").sum())
o["TT_first_asof_ge2026"] = int((first >= "2026-01-01").sum())
o["TT_first_asof_top"] = {str(k.date()): int(v) for k, v in first.value_counts().head(5).items()}
late = set(first[first >= "2024-01-01"].index)
mfl = mf[mf["Fund Code"].isin(late)]
o["late_any_FEEMF_before2024"] = int(mfl[mfl["asof"] < "2024-01-01"]["Fund Code"].nunique())
o["late_codes_before2026"] = mfl[mfl["asof"] < "2026-01-01"].Code.value_counts().to_dict()
o["late_policy"] = ev[ev.FundCode.isin(late)].policy.value_counts().to_dict()
allasof = sorted(fee["As of Date"].unique()); o["asof_2024_2025_n"] = int(sum(1 for a in allasof if "20240101" <= a <= "20251231"))
o["TT_rows_by_year_all_funds"] = fee[(fee["Complex Type Code"]=="FEEMF")&(fee.Code=="TT")]["As of Date"].str[:4].value_counts().sort_index().to_dict()

def parse(s):
    if s is None or (isinstance(s, float) and np.isnan(s)): return np.nan
    s = str(s).strip()
    if any(w in s for w in ["ไม่มี", "ยกเว้น", "ไม่เรียกเก็บ"]): return 0.0
    m = re.fullmatch(r"([0-9]*\.?[0-9]+)\s*%?", s)
    return float(m.group(1)) if m else np.nan

av = tt["Actual Value"].dropna().astype(str)
o["TT_actual_patterns"] = av.str.replace(r"[0-9]", "9", regex=True).value_counts().head(12).to_dict()
o["TT_rate_patterns"] = tt["Rate"].dropna().astype(str).str.replace(r"[0-9]", "9", regex=True).value_counts().head(8).to_dict()
# TT ≥ OF ที่ as-of แรกสุดของ TT
rows = []
for f, d in first.items():
    a = mf[(mf["Fund Code"] == f) & (mf["asof"] == d)]
    t_ = a[a.Code == "TT"]["Actual Value"].map(parse)
    of_ = a[a.Code == "OF"]["Actual Value"].map(parse)
    rows.append((f, t_.iloc[0] if len(t_) else np.nan, of_.iloc[0] if len(of_) else np.nan))
q = pd.DataFrame(rows, columns=["FundCode", "TT", "OF"])
both = q.dropna()
o["TT_OF_both_numeric"] = int(len(both)); o["TT_ge_OF_frac"] = float((both.TT >= both.OF - 1e-12).mean()) if len(both) else None
o["TT_nan_at_first"] = int(q.TT.isna().sum())
o["TT_eq_OF_frac"] = float((np.abs(both.TT - both.OF) < 1e-12).mean()) if len(both) else None
json.dump(o, sys.stdout, ensure_ascii=False, default=str, indent=0); print()
