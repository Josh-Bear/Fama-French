import hashlib, json, sys
from pathlib import Path
T=Path(".claude/factor_team"); S=T/"scratch"
h=lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
EXC={"results.md","run.log","run_meta.json","run.py"}
out={}; allok=True
for sid in ("S003","S005"):
    a=T/"runs"/sid; b=S/f"factor-analyst_{sid.lower()}_regress3"
    rep={}; ok=True; n=0
    for p in sorted(a.rglob("*")):
        if not p.is_file(): continue
        rel=p.relative_to(a)
        if p.name in EXC or p.name.startswith("repro_check"): continue
        q=b/rel
        if p.name=="placebo_rule.json":
            x,y=json.load(open(p)),json.load(open(q)); x.pop("timestamp",None); y.pop("timestamp",None)
            same=(x==y)
        else:
            same=q.exists() and h(p)==h(q)
        n+=1; ok&=same
        rep[str(rel)]=dict(orig=h(p),new=h(q) if q.exists() else None,identical=bool(same))
    # extra files in new not in orig
    extra=[str(q.relative_to(b)) for q in b.rglob("*") if q.is_file() and not (a/q.relative_to(b)).exists()]
    # run_meta compare
    ma,mb=json.load(open(a/"run_meta.json")),json.load(open(b/"run_meta.json"))
    ign={"created","runtime_sec","lib_sha256","placebo_rule"}
    meta_same={k:(ma.get(k)==mb.get(k)) for k in ma if k not in ign}
    m5=json.load(open(T/"runs/S005/run_meta.json"))["lib_sha256"]
    lib_same=all(mb["lib_sha256"].get(k)==v for k,v in m5.items() if k in mb["lib_sha256"]) and all(__import__("hashlib").sha256((T/"lib"/k).read_bytes()).hexdigest()==v for k,v in m5.items())
    if "placebo_rule" in ma:
        x,y=dict(ma["placebo_rule"]),dict(mb["placebo_rule"]); x.pop("timestamp",None); y.pop("timestamp",None); meta_same["placebo_rule_no_ts"]=(x==y)
    s003_note = "lib_sha256 ใน run_meta ของ S003 เดิมต่างที่ tests_stat.py (lib ถูกขยายหลัง S003 ก่อน S005 · ไฟล์ผล S003 ตรงทุกบิต)" if sid=="S003" else ""
    # compare also with original repro_check run1 hashes
    rc=json.load(open(a/"repro_check.json"))["files"]
    rc_ok=all(rc[k]["run1"]==v["new"] for k,v in rep.items() if k in rc)
    out[sid]=dict(note=s003_note,n_files=n,all_identical=ok,matches_repro_check_json=rc_ok,extra_new_files=extra,run_meta_fields_equal=meta_same,lib_sha256_equal=lib_same,files=rep)
    allok&=ok and rc_ok and lib_same and all(meta_same.values())
    print(sid,n,ok,rc_ok,lib_same,[k for k,v in meta_same.items() if not v],extra)
out["all_pass"]=allok
Path(T/"runs/S006").mkdir(exist_ok=True)
json.dump(out,open(T/"runs/S006/regression_S003_S005.json","w"),indent=1)
print("ALL",allok)
