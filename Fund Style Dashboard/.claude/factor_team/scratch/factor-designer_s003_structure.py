"""S003 (addendum ของ S002) — ตรวจโครงข้อมูลเท่านั้น: ชื่อคอลัมน์ / จำนวนแถว / NaN ของคอลัมน์ที่ใช้สร้าง FX ใหม่
ไม่พิมพ์ค่าผลตอบแทน ไม่ fit model
รัน: cd "<root>" && ./.venv/bin/python .claude/factor_team/scratch/factor-designer_s003_structure.py
"""
import pyarrow.parquet as pq

NEED = ["SHV_THB", "RF_BOT", "SHV_USD", "USDTHB", "MSCI_ACWI", "AGG_THB", "Gold_THB"]
for f in ("factors_weekly", "factors_monthly"):
    t = pq.read_table(f".claude/factor_team/data/{f}.parquet")
    names = t.column_names
    miss = [c for c in NEED if c not in names]
    nulls = {c: t.column(c).null_count for c in NEED if c in names}
    print(f, "rows", t.num_rows, "missing", miss, "nulls", nulls)
