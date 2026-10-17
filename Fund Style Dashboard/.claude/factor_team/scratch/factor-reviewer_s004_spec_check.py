# factor-reviewer: S004 spec structure check (no model fit, no return values inspected)
import hashlib, json
import pandas as pd
from pathlib import Path
T = Path(".claude/factor_team")
spec = {
 "data/panel_weekly.parquet":"95c16ee651d3a936788b7cb3c6372bbf5f1e84cb39daf5680343771dca24270b",
 "data/panel_monthly.parquet":"e8e8cb5d5f04fba9bb35558ef7c3d8195c656334119e56f82775cc1ae21ccaed",
 "data/factors_weekly.parquet":"115b87139d2bec0fd57a77a1593c46d36bb23f3f35f83236cdb07be642af47a8",
 "data/factors_monthly.parquet":"f7c4248b4fa889853024449e72ae8909cf1f8d3226a54eebc37448a2a485bb72",
 "data/universe.csv":"fdfb7830df78ce032465ac9d8cddc2c98f9aa86cfa0f3925fdb83026aa3f7252",
 "data/dup_pairs.csv":"b1f0f0c745947fa70803a4f40526c0a1967c72925be985a2bedc1057d8b8aef3",
 "data/factor_groups.csv":"42bf1cfb270721ae6112799ab795ebc4c91212e7584d5cdfee23b9b70b1b1731",
 "data/aum_weekly.parquet":"48c34c73ae22ebffc6112f93e03f729223a496297bb65c324b693b817a723d26",
 "runs/S003/factors_S003_weekly.parquet":"be3ceb2e34b0df1f1a3db27d59e1a103cf5f5a5ca38f2e87f7c812c1c53944ac",
 "runs/S003/fund_level.csv":"36b41161d6a13c1184a4052d9e799f660f431c2694dc57fafd747f8e695bf8cf",
}
man = json.load(open(T/"data/manifest.json"))
def find(m, name):
    s = json.dumps(m)
    return name.split("/")[-1] in s
for k,v in spec.items():
    h = hashlib.sha256(open(T/k,"rb").read()).hexdigest()
    inman = v in json.dumps(man)
    print(k, "spec_ok" if h==v else "SPEC_MISMATCH", "in_manifest" if inman else "not_in_manifest")
f = pd.read_parquet(T/"runs/S003/factors_S003_weekly.parquet")
print(f.shape); print([c for c in f.columns if c.startswith(("3b__","4a__"))])
fl = pd.read_csv(T/"runs/S003/fund_level.csv", nrows=3); print(list(fl.columns)[:40])
fl = pd.read_csv(T/"runs/S003/fund_level.csv")
for c in ["in_EVAL","in_E67","in_PCA_sample","in_STAB"]:
    if c in fl.columns: print(c, fl.drop_duplicates("FundCode")[c].sum() if "FundCode" in fl.columns else fl[c].sum())
# dedup check: are dup pairs both in EVAL?
dp = pd.read_csv(T/"data/dup_pairs.csv"); print(dp.columns.tolist(), len(dp))
if "FundCode" in fl.columns and "in_EVAL" in fl.columns:
    ev = set(fl.loc[fl.in_EVAL.astype(bool),"FundCode"])
    a,b = dp.columns[:2]
    print("dup pairs both in EVAL:", sum((x in ev) and (y in ev) for x,y in zip(dp[a],dp[b])))
print(sorted(Path(T/"runs/S003").iterdir())[:60])
