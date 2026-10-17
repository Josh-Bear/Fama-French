"""S004 structure check — ชื่อคอลัมน์ / จำนวนแถว / NaN เท่านั้น (ไม่ดูค่าผลตอบแทน ไม่ fit)"""
import pandas as pd, hashlib, json
root = ".claude/factor_team/"
def sha(p): return hashlib.sha256(open(p,'rb').read()).hexdigest()
F = pd.read_parquet(root+"data/factors_weekly.parquet")
g = pd.read_csv(root+"data/factor_groups.csv")
main = (F.index >= "2021-01-01") & (F.index <= "2025-12-31")
for grp in ["MSCI_country","MSCI_sector","style_relative","macro","macro_delta"]:
    cols = [c for c in g.factor[g.group==grp] if c in F.columns]
    print(grp, len(cols), "NaN in main:", {c:int(F.loc[main,c].isna().sum()) for c in cols if F.loc[main,c].isna().any()})
print("rows main", int(main.sum()))
S = pd.read_parquet(root+"runs/S003/factors_S003_weekly.parquet")
print("S003 factors shape", S.shape, "index", S.index.min(), S.index.max())
print("cols", list(S.columns))
print("NaN per col (main)", S.loc[(S.index>="2021-01-01")&(S.index<="2025-12-31")].isna().sum().to_dict())
print("sha S003 factors", sha(root+"runs/S003/factors_S003_weekly.parquet"))
print("sha fund_level", sha(root+"runs/S003/fund_level.csv"))
fl = pd.read_csv(root+"runs/S003/fund_level.csv", nrows=3)
print("fund_level cols", list(fl.columns)[:40])
m = json.load(open(root+"runs/S003/run_meta.json")); print("run_meta keys", list(m.keys()))
