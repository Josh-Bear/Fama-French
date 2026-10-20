"""reviewer — รีวิวผล S010 รอบ 2 (อ่านอย่างเดียว · ไม่เขียนใน runs/ · ไม่แตะ trials.csv)
ใช้ (จาก Fund Style Dashboard/): ./.venv/bin/python .claude/factor_team/scratch/factor-reviewer_s010_r2_check.py
เขียนเฉพาะ scratch/factor-reviewer_s010_r2_fam/ (ผลของ family_m97.py --out) + scratch/factor-reviewer_s010_r2_check.json
"""
import ast, csv, datetime as dt, hashlib, json, subprocess, sys
from pathlib import Path
import numpy as np

ROOT = Path(".").resolve()
TEAM = ROOT / ".claude/factor_team"
RUN = TEAM / "runs/S010"
OUTD = TEAM / "scratch/factor-reviewer_s010_r2_fam"
OUT = {}
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
mt = lambda p: dt.datetime.fromtimestamp(Path(p).stat().st_mtime).isoformat(timespec="seconds")


def snapshot():
    snap = {}
    for p in TEAM.rglob("*"):
        if p.is_file() and "scratch" not in p.parts and "reviews" not in p.parts and "__pycache__" not in p.parts:
            snap[str(p.relative_to(TEAM))] = (sha(p), p.stat().st_mtime_ns)
    return snap


# ── 0. ไฟล์ก่อนรัน ──
before = snapshot()
r1 = json.load(open(TEAM / "scratch/factor-reviewer_s010_result_check.json"))

# ── 1. รัน family_m97.py ลง scratch ──
cp = subprocess.run([sys.executable, str(RUN / "family_m97.py"), "--out", str(OUTD)], capture_output=True, text=True, cwd=str(ROOT))
after = snapshot()
changed = sorted(k for k in set(before) | set(after) if before.get(k) != after.get(k))
F = dict(returncode=cp.returncode, stdout=cp.stdout.strip().splitlines()[-2:], stderr_tail=cp.stderr.strip().splitlines()[-3:],
         files_changed_outside_scratch=changed,
         sha_mine=sha(OUTD / "family_m97.csv"), sha_runs=sha(RUN / "family_m97.csv"))
F["csv_identical"] = F["sha_mine"] == F["sha_runs"]
F["check_json_identical"] = (OUTD / "family_m97_check.json").read_bytes() == (RUN / "family_m97_check.json").read_bytes()
OUT["F_family_rerun"] = F

# ── 2. exec segment ของ run.py: ปลอดภัยไหม (AST) ──
src = (RUN / "run.py").read_text(encoding="utf-8")
a = src.index("XS = [")
b = src.index("\n", src.index("ORDER17 = SLOTS_MAIN + COND"))
seg = src[a:b]
tree = ast.parse(seg)
calls = sorted({ast.unparse(n.func) for n in ast.walk(tree) if isinstance(n, ast.Call)})
names_loaded = sorted({n.id for n in ast.walk(tree) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)})
E = dict(count_XS=src.count("XS = ["), count_ORDER17=src.count("ORDER17 = SLOTS_MAIN + COND"),
         line_start=src[:a].count("\n") + 1, line_end=src[:b].count("\n") + 1,
         top_stmt_types=sorted({type(s).__name__ for s in tree.body}), calls=calls, names_loaded=names_loaded,
         has_import=any(isinstance(n, (ast.Import, ast.ImportFrom)) for n in ast.walk(tree)),
         assert_line_excluded="assert len(ORDER97)" not in seg, run_py_sha=sha(RUN / "run.py"), run_py_mtime=mt(RUN / "run.py"))
OUT["E_exec_segment"] = E

# ── 3. คำนวณ BH / BY เอง (ไม่ใช้ lib) จาก trials.csv ──
rows = list(csv.reader(open(TEAM / "trials.csv", newline="", encoding="utf-8")))
H, D = rows[0], rows[1:]
ix = {h: i for i, h in enumerate(H)}
pmap = {r[ix["trial_id"]]: (float(r[ix["p_two"]]) if r[ix["p_two"]] not in ("", "nan") else 1.0) for r in D}
fam = list(csv.DictReader(open(RUN / "family_m97.csv", encoding="utf-8")))
order = [r["slot"] for r in fam]
main = ["P2-B0", "P2-A2", "P2-C1", "P2-A1", "P2-A3", "P2-C2", "P2-D1", "P2-C3", "P2-D3", "P2-B2", "P2-B1", "P2-J1"]
cond = ["P2-M1", "P2-M2", "P2-W1", "P2-W2", "P2-W3"]
r1_order = main + cond + [t for t in pmap if t not in main] + [f"{c}.R{i}" for c in cond for i in range(1, 6)]
J1N = {"P2-J1"} | {f"P2-J1.S{i}" for i in range(1, 5)}


def my_bh(p, q=0.10, by=False):
    p = np.asarray(p, float); m = len(p)
    c = sum(1.0 / i for i in range(1, m + 1)) if by else 1.0
    o = np.argsort(p, kind="mergesort"); ps = p[o]
    thr = np.arange(1, m + 1) * q / (m * c)
    k = np.where(ps <= thr)[0]
    rej = np.zeros(m, bool)
    if len(k):
        rej[o[: k.max() + 1]] = True
    adj_s = np.minimum.accumulate((ps * m * c / np.arange(1, m + 1))[::-1])[::-1]
    adj = np.empty(m); adj[o] = np.minimum(adj_s, 1.0)
    return rej, adj


C = dict(order_prefix_equal=order[:17] == main + cond, order_set_equal_r1=set(order) == set(r1_order), n=len(order),
         roles={k: sum(r["role"] == k for r in fam) for k in ("main", "conditional", "robustness")},
         n_label_rob=sum(r["label"] != "" for r in fam), n_ran=sum(r["ran"] == "True" for r in fam))
for tag, pj in (("J1eq1", True), ("J1real", False)):
    p = np.array([1.0 if (pj and s in J1N) else pmap.get(s, 1.0) for s in order])
    pf = np.array([float(r[f"p_{tag}"]) for r in fam])
    rej, adj = my_bh(p); rby, _ = my_bh(p, by=True)
    f_rej = np.array([r[f"BH_reject_m97_{tag}"] == "True" for r in fam]); f_by = np.array([r[f"BY_reject_m97_{tag}"] == "True" for r in fam])
    f_adj = np.array([float(r[f"BH_adj_p_{tag}"]) for r in fam])
    C[tag] = dict(p_equal=bool(np.array_equal(p, pf)), bh_rej=[order[i] for i in np.where(rej)[0]], by_rej=[order[i] for i in np.where(rby)[0]],
                  bh_equal_file=bool((rej == f_rej).all()), by_equal_file=bool((rby == f_by).all()), adj_maxdiff=float(np.abs(adj - f_adj).max()),
                  C1R5_adj=float(adj[order.index("P2-C1.R5")]), smallest=sorted(zip(p.tolist(), order))[:5])
# m = 17 · ไม่มี R5
p17 = np.array([pmap.get(s, 1.0) if s != "P2-J1" else 1.0 for s in main + cond])
C["bh17_rej"] = [(main + cond)[i] for i in np.where(my_bh(p17)[0])[0]]
pnoR5 = np.array([1.0 if (s in J1N or s.endswith(".R5")) else pmap.get(s, 1.0) for s in order])
C["noR5_bh_rej"] = [order[i] for i in np.where(my_bh(pnoR5)[0])[0]]
C["noR5_by_rej"] = [order[i] for i in np.where(my_bh(pnoR5, by=True)[0])[0]]
C["equals_round1"] = (C["J1eq1"]["bh_rej"] == [x[0] for x in r1["C_family"]["bh97_rejected"]]
                      and C["J1real"]["bh_rej"] == r1["C_family"]["bh97_rejected_realJ1"] and C["J1eq1"]["by_rej"] == r1["C_family"]["by97_rejected"])
# lib ที่ family_m97 ใช้ = lib ของ run (run_meta)
meta = json.load(open(RUN / "run_meta.json"))
C["lib_equal_run_meta"] = {k: sha(TEAM / "lib" / k) == v for k, v in meta["lib_sha256"].items()} if isinstance(meta["lib_sha256"], dict) else str(type(meta["lib_sha256"]))
OUT["C_family_mine"] = C

# ── 4. trials.csv ไม่ถูกแตะ ──
bk = sorted((RUN / "trials_backup").glob("trials.backup_*.csv"), key=lambda p: len(p.read_bytes()))
final = (TEAM / "trials.csv").read_bytes()
T = dict(n_lines=final.count(b"\n"), n_data_rows=len(D), sha=sha(TEAM / "trials.csv"), mtime=mt(TEAM / "trials.csv"),
         mtime_ns=(TEAM / "trials.csv").stat().st_mtime_ns,
         backups=len(bk), last_backup=bk[-1].name, last_backup_mtime=mt(bk[-1]),
         all_backups_prefix=all(final.startswith(p.read_bytes()) for p in bk),
         run_at=sorted({r[ix["run_at"]] for r in D}), run_dir=sorted({r[ix["run_dir"]] for r in D}),
         p_same_as_round1_smallest=sorted(((v, k) for k, v in pmap.items()))[:6] == [tuple(x) for x in r1["C_family"]["smallest_p"]],
         quant_trials_mtime=mt(ROOT / ".claude/quant_team/trials.csv") if (ROOT / ".claude/quant_team/trials.csv").exists() else None)
OUT["T_trials"] = T

# ── 5. ไฟล์ผลเดิมใน runs/S010 ──
rc = json.load(open(RUN / "repro_check.json"))
R = dict(repro_csv_equal={f: sha(RUN / f) == v["run1"] for f, v in rc["files"].items()})
R["all_repro_equal"] = all(R["repro_csv_equal"].values())
osha = meta.get("output_sha256", {})
R["run_meta_output_equal"] = {f: (sha(RUN / f) == v) for f, v in osha.items() if (RUN / f).exists()}
R["mtimes"] = {p.name: mt(p) for p in sorted(RUN.iterdir()) if p.is_file()}
R["newer_than_1024"] = sorted(k for k, v in R["mtimes"].items() if v > "2026-10-20T10:24:00")
OUT["R_runs_files"] = R

# ── 6. pre_check ของ analyst เทียบไฟล์ phase pre เดิม ──
PC = TEAM / "scratch/factor-analyst_s010_pre_check"
P = {}
for f in ("decisions_pre_run.md", "pre_run_numbers.json", "universe_by_quarter.csv", "run_pre.log"):
    x, y = (PC / f).read_bytes(), (RUN / f).read_bytes()
    lx, ly = x.decode().splitlines(), y.decode().splitlines()
    diff = [(i + 1, u[:120], v[:120]) for i, (u, v) in enumerate(zip(lx, ly)) if u != v]
    P[f] = dict(identical=x == y, n_lines=(len(lx), len(ly)), diff_lines=diff[:6], n_diff=len(diff) + abs(len(lx) - len(ly)))
P["pre_check_mtimes"] = {p.name: mt(p) for p in sorted(PC.iterdir())}
OUT["P_pre_check"] = P

# ── 7. sim (10:22) เทียบหัวคอลัมน์ csv ──
SIM = TEAM / "scratch/factor-analyst_sim"
S = {}
for f in sorted(rc["files"]):
    if (SIM / f).exists():
        S[f] = (SIM / f).read_text().splitlines()[0] == (RUN / f).read_text().splitlines()[0]
S["sim_run_meta_lib_equal"] = json.load(open(SIM / "run_meta.json")).get("lib_sha256") == meta["lib_sha256"]
OUT["S_sim_headers"] = S

(TEAM / "scratch/factor-reviewer_s010_r2_check.json").write_text(json.dumps(OUT, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
print(json.dumps(OUT, ensure_ascii=False, indent=1, default=str))
