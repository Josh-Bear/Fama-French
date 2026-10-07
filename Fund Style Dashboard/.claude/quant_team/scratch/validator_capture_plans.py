"""ดักจับ plan จาก runner เดิม (ไม่เขียนทับไฟล์ผลเดิม: ทำ to_csv/write_* เป็น no-op และหยุดทันทีเมื่อได้ plan ครบ)"""
import os, sys, pickle
ROOT = "/Users/doyinratnavardhana/Fama French/Fund Style Dashboard"
sys.path.insert(0, ROOT); sys.path.insert(0, ROOT + "/.claude/quant_team/backtest")
os.chdir(ROOT)
import pandas as pd
pd.DataFrame.to_csv = lambda *a, **k: None
pd.Series.to_csv = lambda *a, **k: None
import run_m006_m007 as r67
which, nwant = sys.argv[1], int(sys.argv[2])
r67.write_trials = lambda *a, **k: None
r67.write_report = lambda *a, **k: None
seen, order = {}, []
class Done(Exception): pass
orig = r67.run_sim
def cap(plan, nav_by_fund, month_ends, cost, rf, include_start):
    if id(plan) not in seen:
        seen[id(plan)] = len(order)
        order.append({"plan": [dict(p) for p in plan], "include_start": include_start, "months": list(month_ends)})
        print("captured", len(order), len(plan), flush=True)
        if len(order) == nwant:
            raise Done
    return orig(plan, nav_by_fund, month_ends, cost, rf, include_start)
r67.run_sim = cap
try:
    if which == "r67":
        r67.run()
    else:
        import run_m008 as r8
        r8.write_trials_and_all = lambda *a, **k: None
        r8.write_report = lambda *a, **k: None
        r8.run()
except Done:
    pass
pickle.dump(order, open(f"/Users/doyinratnavardhana/Fama French/Fund Style Dashboard/.claude/quant_team/scratch/validator_plans_{which}.pkl", "wb"))
print("saved", len(order))
