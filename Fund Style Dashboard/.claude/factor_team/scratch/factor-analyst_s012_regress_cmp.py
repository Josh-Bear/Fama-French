import hashlib, json
from pathlib import Path
T = Path(".claude/factor_team"); S = T/"scratch"
h = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
EXC = {"results.md","run.log","run_meta.json","run.py","pytest_all.log","decisions_pre_run.md"}
out = {}; allok = True
s10 = json.load(open(T/"runs/S010/run_meta.json"))["lib_sha256"]
lib_now = {p.name: h(p) for p in sorted((T/"lib").glob("*.py"))}
base_lib = {k: v for k, v in lib_now.items() if k != "l1eo.py"}
lib_ok = base_lib == s10
out["lib_sha256_original_15_equal_S010_run_meta"] = lib_ok; out["lib_files_now"] = sorted(lib_now); allok &= lib_ok
out["run_py_sha256"] = {"S003": h(T/"runs/S003/run.py"), "S006": h(T/"runs/S006/run.py")}
out["run_py_sha_expected"] = {"S003": "9f21e388306cea0f63d6591580f03c505006fd6ca8d6161e2ef13cfcdce5590f", "S006": "5515b2893fe0188c9135fa7728dd45f091534f03754bf529609b244c03c4f760"}
allok &= out["run_py_sha256"] == out["run_py_sha_expected"]
for sid in ("S003", "S006"):
    a = T/"runs"/sid; b = S/f"factor-analyst_s012_regress_{sid.lower()}"
    rep = {}; ok = True; n = 0
    for p in sorted(a.rglob("*")):
        if not p.is_file(): continue
        rel = p.relative_to(a)
        if p.name in EXC or p.name.startswith("repro_check") or p.name.startswith("regression_") or "__pycache__" in str(rel): continue
        q = b/rel
        if p.name in ("placebo_rule.json", "placebo_C.json"):
            x, y = json.load(open(p)), (json.load(open(q)) if q.exists() else None)
            x.pop("timestamp", None)
            if y: y.pop("timestamp", None)
            same = (x == y)
        else:
            same = q.exists() and h(p) == h(q)
        n += 1; ok &= bool(same)
        rep[str(rel)] = dict(orig=h(p), new=h(q) if q.exists() else None, identical=bool(same))
    extra = [str(q.relative_to(b)) for q in b.rglob("*") if q.is_file() and not (a/q.relative_to(b)).exists() and q.name not in EXC]
    out[sid] = dict(n_files=n, all_identical=ok, extra_new_files=extra, files=rep)
    allok &= ok and not extra
    print(sid, n, ok, extra)
out["note"] = "S006 รันในต้นไม้ scratch (lib 13 ไฟล์ · ไม่มี l4.py/p2.py/l1eo.py) เพราะ run.py ของ S006 assert รายชื่อ lib = S005 + l3.py (วิธีเดียวกับ S010)"
out["all_pass"] = bool(allok)
json.dump(out, open(T/"runs/S012/regression_S003_S006.json", "w"), indent=1, ensure_ascii=False)
print("ALL", allok, "lib_ok", lib_ok)
