"""factor-designer · L1EO_summary · คำนวณจาก CSV ของ runs/S012 อย่างเดียว (ไม่ fit · ไม่อ่าน panel)
median R²_oos ต่อกลุ่มชื่อ (EVAL) ต่อแถว · จำนวนกองที่แถวใดชนะรายกอง · class ปันผลใน E"""
import csv, json, hashlib, statistics as st, collections
from pathlib import Path
R = Path(__file__).resolve().parents[1] / "runs" / "S012"
f = R / "fund_level_E.csv"
rows = [x for x in csv.DictReader(open(f)) if x["in_EVAL"] == "True"]
ROWS = ["E-PCA-a1", "E-PCA-a2", "E-X1", "E-X2", "E-H", "①a", "①c", "③a", "M1"]
by = collections.defaultdict(dict)
for x in rows:
    if x["row"] in ROWS and x["r2_oos"] not in ("", "nan"):
        by[x["unit"]][x["row"]] = float(x["r2_oos"])
grp = {x["unit"]: x["group"] for x in rows}
hasg = {x["unit"]: x["has_group_factor"] for x in rows}
out = {}
groups = collections.defaultdict(list)
for u, g in grp.items():
    groups[g].append(u)
tab = []
for g, us in sorted(groups.items(), key=lambda kv: -len(kv[1])):
    row = dict(group=g, n=len(us), has_group_factor=hasg[us[0]])
    for r in ROWS:
        v = [by[u][r] for u in us if r in by[u]]
        row[r] = round(st.median(v), 3) if v else None
    comp = {r: row[r] for r in ["E-PCA-a1", "E-X2", "E-H", "③a"] if row[r] is not None}
    row["best_of_PCAa1_EX2_EH_3a"] = max(comp, key=comp.get)
    tab.append(row)
# per-fund winner among E-PCA-a1 vs E-X2
w = collections.Counter()
for u, d in by.items():
    if "E-PCA-a1" in d and "E-X2" in d:
        w["E-X2 > a1" if d["E-X2"] > d["E-PCA-a1"] else "a1 >= E-X2"] += 1
div = sorted({x["unit"] for x in rows if x["div_class"] == "True"})
out = dict(source_sha=hashlib.sha256(f.read_bytes()).hexdigest(), n_eval=len(by), per_group=tab, fund_winner_a1_vs_EX2=dict(w), div_units_eval=div)
(Path(__file__).with_suffix(".json")).write_text(json.dumps(out, ensure_ascii=False, indent=1))
for t in tab:
    print(t)
print(dict(w), len(div), div)
