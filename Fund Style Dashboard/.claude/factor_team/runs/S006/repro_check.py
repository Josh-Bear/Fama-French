"""เทียบ sha256 ของไฟล์ผล (.csv/.parquet) ระหว่างรัน 2 รอบ + placebo_C.json (ตัด timestamp) → repro_check.json · ใช้: python repro_check.py DIR1 DIR2 OUT.json"""
import hashlib, json, sys
from pathlib import Path
a, b, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
h = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
res, ok = {}, True
for p in sorted(a.rglob("*")):
    if p.is_file() and p.suffix in (".csv", ".parquet"):
        rel = p.relative_to(a); q = b / rel
        same = q.exists() and h(p) == h(q)
        ok &= same
        res[str(rel)] = dict(run1=h(p), run2=h(q) if q.exists() else None, identical=same)
r1, r2 = json.load(open(a / "placebo_C.json")), json.load(open(b / "placebo_C.json"))
r1.pop("timestamp"); r2.pop("timestamp")
res["placebo_C.json(ตัด timestamp)"] = dict(identical=r1 == r2)
ok &= r1 == r2
extra = sorted(str(q.relative_to(b)) for q in b.rglob("*") if q.is_file() and q.suffix in (".csv", ".parquet") and not (a / q.relative_to(b)).exists())
ok &= not extra
json.dump(dict(all_identical=ok, n_files=len(res), extra_in_run2=extra, excluded="results.md, run.log, run_meta.json, run.py, repro_check.*, pytest_all.log, regression_*.json, decisions_pre_run.md (มีเวลา/เมตา); placebo_C.json เทียบเนื้อหาไม่รวม timestamp", files=res), open(out, "w"), indent=1, ensure_ascii=False)
print("all_identical", ok, "n_files", len(res))
