import hashlib, json
from pathlib import Path
T = Path(".claude/factor_team"); S = T/"scratch"
h = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
EXC = {"results.md","run.log","run_meta.json","run.py","pytest_all.log","decisions_pre_run.md"}
out = {}; allok = True
s6meta = json.load(open(T/"runs/S006/run_meta.json"))
lib_now = {p.name: h(p) for p in sorted((T/"lib").glob("*.py"))}
lib_ok = lib_now == s6meta["lib_sha256"]
out["lib_sha256_equals_S006_run_meta"] = lib_ok; out["lib_files"] = len(lib_now); allok &= lib_ok
for sid in ("S003","S005","S006"):
    a = T/"runs"/sid; b = S/f"factor-analyst_{sid.lower()}_regress4"
    rep = {}; ok = True; n = 0
    for p in sorted(a.rglob("*")):
        if not p.is_file(): continue
        rel = p.relative_to(a)
        if p.name in EXC or p.name.startswith("repro_check") or p.name.startswith("regression_"): continue
        if "__pycache__" in str(rel): continue
        q = b/rel
        if p.name in ("placebo_rule.json","placebo_C.json"):
            x, y = json.load(open(p)), (json.load(open(q)) if q.exists() else None)
            x.pop("timestamp", None)
            if y: y.pop("timestamp", None)
            same = (x == y)
        else:
            same = q.exists() and h(p) == h(q)
        n += 1; ok &= bool(same)
        rep[str(rel)] = dict(orig=h(p), new=h(q) if q.exists() else None, identical=bool(same))
    extra = [str(q.relative_to(b)) for q in b.rglob("*") if q.is_file() and not (a/q.relative_to(b)).exists() and q.name not in EXC]
    ma, mb = json.load(open(a/"run_meta.json")), json.load(open(b/"run_meta.json"))
    ign = {"created","runtime_sec","lib_sha256","placebo_rule","pinned_sha256","regression"}
    meta_same = {k: (ma.get(k) == mb.get(k)) for k in ma if k not in ign}
    if "placebo_rule" in ma:
        x, y = dict(ma["placebo_rule"]), dict(mb["placebo_rule"]); x.pop("timestamp", None); y.pop("timestamp", None); meta_same["placebo_rule_no_ts"] = (x == y)
    rc = json.load(open(a/"repro_check.json"))["files"]
    rc_ok = all(rc[k]["run1"] == v["new"] for k, v in rep.items() if k in rc)
    out[sid] = dict(n_files=n, all_identical=ok, matches_repro_check_json=rc_ok, extra_new_files=extra, run_meta_fields_equal=meta_same, files=rep)
    allok &= ok and rc_ok and all(meta_same.values()) and not extra
    print(sid, n, ok, rc_ok, [k for k,v in meta_same.items() if not v], extra)
out["all_pass"] = allok
(T/"runs/S009").mkdir(exist_ok=True)
json.dump(out, open(T/"runs/S009/regression_S003_S005_S006.json","w"), indent=1, ensure_ascii=False)
print("ALL", allok, "lib_ok", lib_ok)
