"""S007 (L4) — ตรวจโครงข้อมูลเท่านั้น (factor-designer).
ไม่อ่านค่าผลตอบแทน · ไม่ fit model · ไม่อ่านคอลัมน์ผล (alpha / r2 / beta) ของ runs/*
พิมพ์: sha256 ของไฟล์ที่ spec จะ pin · ชื่อคอลัมน์ · จำนวนกองต่อป้ายกลุ่ม · ความครอบคลุมของคุณลักษณะกอง
"""
import hashlib, json, re, sys
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
T = ROOT / ".claude" / "factor_team"
out = {}


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


pins = [
    "data/panel_weekly.parquet", "data/panel_monthly.parquet", "data/factors_weekly.parquet",
    "data/factors_monthly.parquet", "data/factors_ext_weekly.parquet", "data/universe.csv",
    "data/dup_pairs.csv", "data/factor_groups.csv", "data/aum_weekly.parquet",
    "runs/S003/factors_S003_weekly.parquet", "runs/S003/fund_level.csv", "runs/S003/run.py",
    "runs/S003/grs_ports.csv", "runs/S005/primary_index.csv", "runs/S005/fund_clusters.csv",
    "runs/S005/criteria_P4.json", "runs/S005/run.py", "runs/S005/fund_level.csv",
    "runs/S006/run.py", "runs/S006/fund_level.csv", "runs/S006/resid_B_coef.csv",
    "runs/S006/run_meta.json", "runs/S006/primary_A.csv",
]
out["sha256"] = {p: sha(T / p) for p in pins if (T / p).exists()}
out["missing"] = [p for p in pins if not (T / p).exists()]
for p in ["base_data/SecFundFee.csv", "base_data/FundProfile.csv", "base_data/share_class_groups.csv"]:
    if (ROOT / p).exists():
        out["sha256"][p] = sha(ROOT / p)

# lib hash ปัจจุบัน vs S006 run_meta
meta = json.loads((T / "runs/S006/run_meta.json").read_text())
lib_meta = meta.get("lib_sha256", {})
lib_now = {f.name: sha(f) for f in sorted((T / "lib").glob("*.py"))}
out["lib_match_S006"] = {k: (lib_meta.get(k) == v) for k, v in lib_now.items()}
out["lib_extra_vs_meta"] = sorted(set(lib_now) - set(lib_meta))
out["run_meta_keys"] = list(meta.keys())

# คอลัมน์ (ชื่อเท่านั้น)
U = pd.read_csv(T / "data/universe.csv")
out["universe_cols"] = list(U.columns)
fl6 = pd.read_csv(T / "runs/S006/fund_level.csv", nrows=3)
out["S006_fund_level_cols"] = list(fl6.columns)
fl3 = pd.read_csv(T / "runs/S003/fund_level.csv", nrows=3)
out["S003_fund_level_cols"] = list(fl3.columns)
pi = pd.read_csv(T / "runs/S005/primary_index.csv")
out["primary_index_cols"] = list(pi.columns)
fc = pd.read_csv(T / "runs/S005/fund_clusters.csv")
out["fund_clusters_cols"] = list(fc.columns)
Fw = pd.read_parquet(T / "data/factors_weekly.parquet")
out["factors_weekly_cols_fx_rate"] = [c for c in Fw.columns if re.search(r"RF|SHV|DTB|USDTHB|TB3|FED|SOFR", c, re.I)]
out["factors_weekly_shape"] = list(Fw.shape)
out["S006_files"] = sorted(p.name for p in (T / "runs/S006").iterdir())

json.dump(out, sys.stdout, ensure_ascii=False, indent=1, default=str)
print()
