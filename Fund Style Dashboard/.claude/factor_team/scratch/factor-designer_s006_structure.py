"""S006 โครงข้อมูลเท่านั้น (ชื่อคอลัมน์ / แถว / NaN / sha256 / จำนวนกองต่อป้าย) — ไม่ดูค่าผลตอบแทน ไม่ fit model"""
import hashlib, json, sys
from pathlib import Path
import pandas as pd
ROOT = Path(".")
T = ROOT / ".claude/factor_team"
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
fe = pd.read_parquet(T / "data/factors_ext_weekly.parquet")
fs = pd.read_parquet(T / "runs/S003/factors_S003_weekly.parquet")
fw = pd.read_parquet(T / "data/factors_weekly.parquet")
print("ext shape", fe.shape, "cols", list(fe.columns))
main = (fe.index >= "2021-01-01") & (fe.index <= "2025-12-31")
print("ext main rows", int(main.sum()), "NaN in main", int(fe[main].isna().sum().sum()))
print("ext idx == factors_weekly idx:", fe.index.equals(fw.index), "| S003 rows", fs.shape, "S003 idx subset of ext:", fs.index.isin(fe.index).all())
print("S003 cols 1a/1c:", [c for c in fs.columns if c.startswith(("1a__", "1c__"))])
print("needed in factors_weekly:", {c: (c in fw.columns) for c in ["RF_BOT", "SHV_THB", "Gold_THB", "AGG_THB", "MSCI_ACWI"]})
meta = json.load(open(T / "runs/S005/run_meta.json"))
cur = {p.name: sha(p) for p in sorted((T / "lib").glob("*.py"))}
print("lib now vs S005 run_meta:", {k: (cur.get(k) == v) for k, v in meta["lib_sha256"].items()}, "| extra files now:", sorted(set(cur) - set(meta["lib_sha256"])))
try:
    import sklearn; print("sklearn", sklearn.__version__)
except Exception as e:
    print("sklearn: NOT available", e)
for f in ["cache/results.csv", "cache/coefs.csv"]:
    p = ROOT / f
    if p.exists():
        h = pd.read_csv(p, nrows=0); n = sum(1 for _ in open(p)) - 1
        print(f, "rows", n, "cols", list(h.columns)[:40])
fl = pd.read_csv(T / "runs/S005/fund_level.csv", nrows=0); print("S005 fund_level cols", list(fl.columns)[:30])
pi = pd.read_csv(T / "runs/S005/primary_index.csv")
pin = pi[pi.form == "none"]
p4 = ["MSCI_ACWI_HC", "MSCI_ACWI_UT", "MSCI_EUROPE", "MSCI_INDIA", "MSCI_JAPAN", "MSCI_VIETNAM"]
print("primary(form=none) n", len(pin), "| P4 counts", pin["index"].value_counts().reindex(p4).to_dict())
print("primary in app-11:", int(pin["index"].isin(["MSCI_BRAZIL","MSCI_CHINA_A_SHARES","MSCI_CHINA_H_SHARES","MSCI_EUROPE","MSCI_INDIA","MSCI_JAPAN","MSCI_KOREA","MSCI_ASEAN","MSCI_TAIWAN","MSCI_USA","MSCI_VIETNAM"]).sum()),
      "| in sectors:", int(pin["index"].str.startswith("MSCI_ACWI_").sum() - (pin["index"] == "MSCI_ACWI_EX_US").sum()),
      "| aggregates:", pin["index"].isin(["MSCI_ACWI","MSCI_WORLD","MSCI_WORLD_EX_US","MSCI_ACWI_EX_US","MSCI_EM","MSCI_ASIA_EX_JAPAN","MSCI_CHINA_ALL_SHARES"]).sum())
print("forms in primary_index.csv", pi.form.unique().tolist())
