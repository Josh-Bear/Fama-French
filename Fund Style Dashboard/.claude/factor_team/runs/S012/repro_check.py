"""repro_check — รัน run.py (phase pre + full) ลงโฟลเดอร์ scratch อีกรอบ แล้วเทียบ sha256 ของไฟล์ผลกับ runs/S012 (ยกเว้น log · เวลาใน run_meta)
ใช้: PYTHONPATH=. ./.venv/bin/python .claude/factor_team/runs/S012/repro_check.py   (รันจาก root)"""
import hashlib, json, subprocess, sys, time
from pathlib import Path

T = Path(".claude/factor_team")
A = T / "runs" / "S012"
B = T / "scratch" / "factor-analyst_s012_repro2"
B.mkdir(parents=True, exist_ok=True)
h = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
t0 = time.time()
for ph in ("pre", "full"):
    r = subprocess.run([sys.executable, str(A / "run.py"), "--phase", ph, "--out", str(B)], capture_output=True, text=True, env={"PYTHONPATH": ".", **__import__("os").environ})
    assert r.returncode == 0, r.stdout[-1500:] + r.stderr[-1500:]
r2_ = subprocess.run([sys.executable, str(A / "addendum_s1.py"), "--out", str(B)], capture_output=True, text=True, env={"PYTHONPATH": ".", **__import__("os").environ})
assert r2_.returncode == 0, r2_.stdout[-1500:] + r2_.stderr[-1500:]
SKIP = {"addendum_s1.py", "run_v1.py", "run_v1.log", "run_pre_v1.log", "l1eo_v1_before_S2.py", "analyst_notes.md", "decisions_post_review.md", "addendum_s1_check.json", "run.log", "run_pre.log", "run_meta.json", "run_meta_pre.json", "repro_check.json", "pytest_all.log", "run_pre.py", "run.py", "decisions_pre_run.md", "repro_check.py",
        "regression_S003_S006.json", "results.md"}
files = {}
ok_all = True
for p in sorted(A.iterdir()):
    if not p.is_file() or p.name in SKIP:
        continue
    q = B / p.name
    same = q.exists() and h(p) == h(q)
    ok_all &= same
    files[p.name] = dict(run1=h(p), run2=h(q) if q.exists() else None, identical=bool(same))
extra = [q.name for q in B.iterdir() if q.is_file() and q.name not in SKIP and not (A / q.name).exists()]
ok_all &= not extra
# results.md: เทียบทั้งไฟล์ (ไม่มีเวลาในเนื้อหา)
res_same = (A / "results.md").read_bytes() == (B / "results.md").read_bytes()
add_same = json.load(open(A / "addendum_s1_check.json"))["identical_to_run_py_table"] and json.load(open(B / "addendum_s1_check.json"))["identical_to_run_py_table"]
out = dict(note="รัน run.py (phase pre + full) ใหม่ลง scratch/factor-analyst_s012_repro2 แล้วเทียบ sha256 กับ runs/S012 (ยกเว้น log · run_meta · ไฟล์สถิตของรอบ v1/notes · results.md เทียบทั้งไฟล์แยกต่างหาก) + addendum_s1.py",
           n_files=len(files), all_identical=bool(ok_all), results_md_identical=bool(res_same), addendum_s1_matches_run_py_table=bool(add_same), extra_files=extra, runtime_sec=round(time.time() - t0, 1), files=files)
json.dump(out, open(A / "repro_check.json", "w"), indent=1, ensure_ascii=False)
print("repro", ok_all, res_same, len(files), extra)
