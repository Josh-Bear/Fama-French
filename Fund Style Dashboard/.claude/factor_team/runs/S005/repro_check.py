"""เทียบ sha256 ของไฟล์ผล (.csv/.parquet/criteria_P4.json ทั้งโฟลเดอร์ย่อย) ระหว่างรัน 2 รอบ + placebo_rule.json (ตัด timestamp) → repro_check.json"""
import hashlib, json, sys
from pathlib import Path
a, b, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
h = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
res, ok = {}, True
for p in sorted(a.rglob("*")):
    if p.is_file() and (p.suffix in (".csv", ".parquet") or p.name == "criteria_P4.json"):
        rel = p.relative_to(a)
        q = b / rel
        same = q.exists() and h(p) == h(q)
        ok &= same
        res[str(rel)] = dict(run1=h(p), run2=h(q) if q.exists() else None, identical=same)
r1, r2 = json.load(open(a / "placebo_rule.json")), json.load(open(b / "placebo_rule.json"))
r1.pop("timestamp"); r2.pop("timestamp")
res["placebo_rule.json(ตัด timestamp)"] = dict(identical=r1 == r2)
ok &= r1 == r2
json.dump(dict(all_identical=ok, n_files=len(res), excluded="results.md, run.log, run_meta.json, run.py, repro_check.* (มีเวลา/เมตา); placebo_rule.json เทียบเนื้อหาไม่รวม timestamp", files=res), open(out, "w"), indent=1)
print("all_identical", ok, "n_files", len(res))
