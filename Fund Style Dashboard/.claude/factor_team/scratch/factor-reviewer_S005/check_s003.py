import json,hashlib,pathlib
d=pathlib.Path("/Users/doyinratnavardhana/Fama French/Fund Style Dashboard/.claude/factor_team/runs/S003")
rc=json.load(open(d/"repro_check.json"))
files=rc.get("files",{})
bad=[];n=0
for f,v in files.items():
    ref=v.get("run2") or v.get("run1") if isinstance(v,dict) else v
    h=hashlib.sha256(open(d/f,"rb").read()).hexdigest(); n+=1
    if h!=ref: bad.append(f)
print("S003 checked",n,"mismatch",bad)
