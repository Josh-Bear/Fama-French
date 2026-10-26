"""check_navdate_one (m5 · รีวิวผล S014): วันในสัปดาห์ของ NAVDate ของ ONE-INDIAOPP-RA (เทียบ K-GOLD-A(A)) ในช่วงก่อน/หลังช่องว่าง NAV ศุกร์ (2023-12-15)
อ่านเฉพาะคอลัมน์ FundCode · NAVDate จาก base_data/nav_history_db.csv (อ่านอย่างเดียว · ไม่อ่านค่า NAV) → navdate_check.csv + sha256 ของสคริปต์ / ไฟล์ NAV
ใช้ (จาก root): ./.venv/bin/python .claude/factor_team/runs/S014/check_navdate_one.py"""
import hashlib
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
NAV = ROOT / "base_data" / "nav_history_db.csv"
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
rows = []
for ch in pd.read_csv(NAV, usecols=["FundCode", "NAVDate"], chunksize=500000):
    rows.append(ch[ch.FundCode.isin(["ONE-INDIAOPP-RA", "K-GOLD-A(A)"])])
d = pd.concat(rows).drop_duplicates()
d["NAVDate"] = pd.to_datetime(d["NAVDate"])
out = []
for code, g in d.groupby("FundCode"):
    for lab, lo, hi in (("ก่อนช่องว่าง", "2023-01-01", "2023-12-08"), ("หลังช่องว่าง", "2023-12-15", "2025-12-26"), ("2024-Q4", "2024-09-23", "2024-12-31")):
        s = g[(g.NAVDate >= lo) & (g.NAVDate <= hi)]
        vc = s.NAVDate.dt.day_name().value_counts()
        out.append(dict(FundCode=code, window=lab, start=lo, end=hi, n_navdate=len(s), n_friday=int(vc.get("Friday", 0)),
                        by_weekday=";".join(f"{k}:{int(v)}" for k, v in vc.items())))
res = pd.DataFrame(out)
res["script_sha256"] = sha(__file__)
res["nav_file_sha256"] = sha(NAV)
res.to_csv(HERE / "navdate_check.csv", index=False)
print(res.drop(columns=["script_sha256", "nav_file_sha256"]).to_string())
