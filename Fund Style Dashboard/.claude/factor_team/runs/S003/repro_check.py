"""เทียบ sha256 ของไฟล์ผล (.csv/.parquet) ระหว่างรัน 2 รอบ → repro_check.json"""
import hashlib, json, sys
from pathlib import Path
a, b, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
h = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
res, ok = {}, True
for p in sorted(a.iterdir()):
    if p.suffix in (".csv", ".parquet"):
        q = b / p.name
        same = q.exists() and h(p) == h(q)
        ok &= same
        res[p.name] = dict(run1=h(p), run2=h(q) if q.exists() else None, identical=same)
json.dump(dict(all_identical=ok, n_files=len(res), excluded="results.md, run.log, run_meta.json, run.py (มีเวลา/เมตา)", files=res), open(out, "w"), indent=1)
print("all_identical", ok, "n_files", len(res))
