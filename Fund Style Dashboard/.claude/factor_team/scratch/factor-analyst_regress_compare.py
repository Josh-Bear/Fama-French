import hashlib, json
from pathlib import Path
ROOT = Path("/Users/doyinratnavardhana/Fama French/Fund Style Dashboard/.claude/factor_team")
h = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
out = {"note": "รัน run.py ของ S003/S005/S006/S009(+run_addendum) ใหม่ลง scratch/factor-analyst_s010_regress_* แล้วเทียบ sha256 กับ run1 ใน runs/S###/repro_check.json และไฟล์จริงใน runs/S###/ (S006 รันในต้นไม้ scratch ที่ lib ไม่มี l4.py เพราะ S006 assert lib = S005 + l3.py)"}
allok = True
for s in ("S003", "S005", "S006", "S009"):
    rc = json.load(open(ROOT / "runs" / s / "repro_check.json"))
    new = ROOT / "scratch" / f"factor-analyst_s010_regress_{s}"
    res = {}
    for rel, v in rc["files"].items():
        if "(ตัด timestamp)" in rel:
            rr = rel.replace("(ตัด timestamp)", "")
            x = json.load(open(ROOT / "runs" / s / rr)); y = json.load(open(new / rr)); x.pop("timestamp", None); y.pop("timestamp", None)
            res[rel] = dict(identical=(x == y), json_without_timestamp=True)
            continue
        a = h(ROOT / "runs" / s / rel)
        n = new / rel
        b = h(n) if n.exists() else None
        res[rel] = dict(repro_run1=v["run1"], runs_file=a, new=b, identical=(b == v["run1"] == a))
    ok = all(x["identical"] for x in res.values())
    # ไฟล์ csv/parquet ที่เพิ่มใหม่ที่ไม่อยู่ใน repro_check
    extra = sorted(str(p.relative_to(new)) for p in new.rglob("*") if p.is_file() and p.suffix in (".csv", ".parquet") and str(p.relative_to(new)) not in rc["files"] and p.suffix in (".csv", ".parquet"))
    allok &= ok and not extra
    out[s] = dict(n_files=len(res), all_identical=ok, extra_new_csv=extra, files=res)
# lib sha ที่ใช้ตอนรันใหม่
for s in ("S003", "S005", "S009"):
    rm_old = json.load(open(ROOT / "runs" / s / "run_meta.json")); rm_new = json.load(open(ROOT / "scratch" / f"factor-analyst_s010_regress_{s}" / "run_meta.json"))
    out[s]["lib_sha256_equal_run_meta"] = rm_old.get("lib_sha256") == rm_new.get("lib_sha256")
    out[s]["data_sha256_equal_run_meta"] = rm_old.get("data_sha256") == rm_new.get("data_sha256")
rm_old = json.load(open(ROOT / "runs/S006/run_meta.json")); rm_new = json.load(open(ROOT / "scratch/factor-analyst_s010_regress_S006/run_meta.json"))
out["S006"]["lib_sha256_equal_run_meta"] = rm_old.get("lib_sha256") == rm_new.get("lib_sha256")
out["all_pass"] = allok
json.dump(out, open(ROOT / "runs/S010/regression_phase1.json", "w"), indent=1, ensure_ascii=False)
print({k: (v["all_identical"], v["n_files"], v["extra_new_csv"], v.get("lib_sha256_equal_run_meta")) for k, v in out.items() if k.startswith("S")}, allok)
