"""reviewer S006: ตรวจโครงข้อมูล / hash / ตัวเลข §5.2 (ไม่ fit model)"""
import sys, json, hashlib, ast, re
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path("/Users/doyinratnavardhana/Fama French/Fund Style Dashboard")
T = ROOT / ".claude/factor_team"
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
spec = (T / "specs/S006_L3_vif_cleaned.md").read_text()
# 1) sha256 เต็มทุกค่าที่ spec ระบุ
pairs = re.findall(r"`([^`]+\.(?:parquet|csv|json|py))`[^\n]*?`([0-9a-f]{64})`", spec)
files = {"data/panel_weekly.parquet":"95c16ee651d3a936788b7cb3c6372bbf5f1e84cb39daf5680343771dca24270b",
 "data/panel_monthly.parquet":"e8e8cb5d5f04fba9bb35558ef7c3d8195c656334119e56f82775cc1ae21ccaed",
 "data/factors_weekly.parquet":"115b87139d2bec0fd57a77a1593c46d36bb23f3f35f83236cdb07be642af47a8",
 "data/factors_monthly.parquet":"f7c4248b4fa889853024449e72ae8909cf1f8d3226a54eebc37448a2a485bb72",
 "data/factors_ext_weekly.parquet":"3105b6e7fe32ffd3648e8feac8dbd03a8db22b7e8eb245c5faf462b14da5e296",
 "runs/S003/factors_S003_weekly.parquet":"be3ceb2e34b0df1f1a3db27d59e1a103cf5f5a5ca38f2e87f7c812c1c53944ac",
 "runs/S003/fund_level.csv":"36b41161d6a13c1184a4052d9e799f660f431c2694dc57fafd747f8e695bf8cf",
 "runs/S003/grs_ports.csv":"d55011094898acdf6e0419c90a3b2713479451380cacc0bf950559c43b98ba19",
 "runs/S003/regions.csv":"2fa3ce691c9dd66ef523e1baca228a635369d2971857797a05c105c1306e6866",
 "runs/S005/primary_index.csv":"5a94ab9b498bb107600938d37f665c7263d9f0a5973460159c09ae83a799275c",
 "runs/S005/fund_clusters.csv":"072cd97ade7e01a32edb9aaf5b949381d1500dcb1ed909558bee3a373e2fc0cb",
 "runs/S005/criteria_P4.json":"0db21831202f8ff2378923740074d2517be1a37563d5f09a64e103d8651cbfb2",
 "runs/S005/fund_level.csv":"1be9d49e70f385cd9a6e09d586f16ec3677622ee87b598826a34bebd69a89cf5",
 "runs/S005/placebo_rule.json":"0460b5b2ff9721c3be97c134fd15c19d28c6596c0a5f6ad5dd08d842ec3f78dc",
 "specs/S005_L2_addendum_to_S004.md":"c71ad963b64347d463c8d8a30fe55240b851be85d364f35a6ab121a7112f8468"}
for f, h in files.items():
    print("sha", f, sha(T / f) == h)
print("sha config.py", sha(ROOT / "config.py") == "711d5738ecf25fc0064e10134ae4cf5d8cfb0cee22d8dd5fbf0174fe925a7d66")
print("sha cache/results.csv", sha(ROOT / "cache/results.csv") == "7c0ce137c4a8692e0136cefe1c4ddbad4cea42cca5e0af8aaa8bb36a05239cfc")
print("run.py S003", sha(T / "runs/S003/run.py")[:8], sha(T / "runs/S003/run.py")[-4:], "S005", sha(T / "runs/S005/run.py")[:8], sha(T / "runs/S005/run.py")[-4:])
me = json.loads((T / "data/manifest_ext.json").read_text())
txt = json.dumps(me)
print("ext sha in manifest_ext:", "3105b6e7fe32ffd3648e8feac8dbd03a8db22b7e8eb245c5faf462b14da5e296" in txt)
m0 = json.dumps(json.loads((T / "data/manifest.json").read_text()))
for h in ("95c16ee651d3a936788b7cb3c6372bbf5f1e84cb39daf5680343771dca24270b", "115b87139d2bec0fd57a77a1593c46d36bb23f3f35f83236cdb07be642af47a8"):
    print("manifest has", h[:8], h in m0)
# 2) config AST
tree = ast.parse((ROOT / "config.py").read_text())
for n in ast.walk(tree):
    if isinstance(n, ast.Assign) and any(getattr(t, "id", "") in ("SCORE_COUNTRY_CLEAN", "SCORE_VIF_MAX") for t in n.targets):
        print("config", n.targets[0].id, ast.literal_eval(n.value) if not isinstance(n.value, ast.Name) else n.value.id)
print([l for l in (ROOT / "config.py").read_text().splitlines() if re.search(r"SECTOR|sector", l)][:12])
# 3) ext columns + F columns
Fe = pd.read_parquet(T / "data/factors_ext_weekly.parquet"); F = pd.read_parquet(T / "data/factors_weekly.parquet")
print("ext cols THB", [c for c in Fe.columns if c.endswith("_THB")])
print("F cols MSCI", [c for c in F.columns if c.startswith("MSCI")], "TDEX" , [c for c in F.columns if "TDEX" in c])
print("ext index == F index (main)", Fe.index[Fe.index <= "2025-12-31"].equals(F.index[F.index <= "2025-12-31"]))
# 4) primary sets for P4 across forms
pi = pd.read_csv(T / "runs/S005/primary_index.csv")
P4 = ["MSCI_ACWI_HC", "MSCI_ACWI_UT", "MSCI_EUROPE", "MSCI_INDIA", "MSCI_JAPAN", "MSCI_VIETNAM"]
sets = {fm: {j: set(pi[(pi.form == fm) & (pi["index"] == j)].FundCode) for j in P4} for fm in ("none", "1a@4", "1c@4")}
for j in P4:
    print("prim", j, {fm: len(sets[fm][j]) for fm in sets}, "same none/1a/1c:", sets["none"][j] == sets["1a@4"][j] == sets["1c@4"][j])
# 5) fund_level precision
fl = (T / "runs/S005/fund_level.csv").read_text().splitlines()[:3]
print("fund_level head", fl[0][:200]); print(fl[1][:300])
# 6) tests numbering
for f in ("test_l2.py", "test_core.py", "test_models.py"):
    names = re.findall(r"def (test_\w+)", (T / "lib/tests" / f).read_text())
    print(f, len(names), names[-4:])
# 7) §5.2 table vs CSV
rl = pd.read_csv(T / "runs/S005/rolling_104.csv")
g = rl[rl.policy.isin(["E", "ALL"]) & (rl.factor != "PRIM")].groupby(["model", "policy"]).agg(m=("roll_median", "mean"), mn=("roll_min", "min")).round(3)
md = (T / "runs/S005/results.md").read_text().split("### 5.2")[1].split("ไฟล์เต็ม")[0]
rows = re.findall(r"\| (\S+(?: \S+)?) \| (E|ALL) \| ([-\d.]+) \| ([-\d.]+) \|", md)
bad = [(a, b, c, d, g.loc[(a, b)].tolist()) for a, b, c, d in rows if abs(float(c) - g.loc[(a, b), "m"]) > 1e-9 or abs(float(d) - g.loc[(a, b), "mn"]) > 1e-9]
print("§5.2 rows", len(rows), "mismatch", bad)
gp = rl[rl.policy.isin(["E"])].groupby("model").agg(m=("roll_median", "mean")).round(3)
print("incl PRIM (E):", gp.loc[["L2-1", "L2-3", "L2-5", "L2-6", "L2-7"]].m.to_dict())
print("PRIM rows E", rl[(rl.factor == "PRIM") & (rl.policy == "E")][["model", "roll_median", "roll_min"]].round(3).values.tolist())
print("n_windows unique", rl.n_windows.unique(), "n_funds by policy", rl.groupby("policy").n_funds.unique().to_dict(), "models", rl.model.unique().tolist())
for k in ("appendix_k3", "appendix_k5"):
    a = pd.read_csv(T / f"runs/S005/{k}/rolling_104.csv"); print(k, a.shape, a.model.unique().tolist(), a.n_windows.unique())
ov = json.loads((T / "scratch/factor-analyst_old_vs_new.json").read_text())
print("old_vs_new keys", list(ov)[:10] if isinstance(ov, dict) else type(ov))
