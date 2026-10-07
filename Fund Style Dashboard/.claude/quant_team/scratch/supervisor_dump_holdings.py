"""Read-only: dump per-quarter weights of M002-M005 trials (runner doesn't save them). No result files written."""
import sys, os
sys.path.insert(0, ".claude/quant_team/backtest")
import pandas as pd
import common, simulate, run_m002_m005 as R
OUT = ".claude/quant_team/scratch/supervisor_holdings"
common.RESULTS_DIR = OUT            # family-map write goes to scratch, not results/
class Stop(Exception): pass
def grab(*a, **k):
    tr = sys._getframe(2).f_locals.get("trial_records") or sys._getframe(1).f_locals.get("trial_records")
    rows = [{"trial": tid, "t": r["t"].date(), "e": r["e"].date(), "FundCode": fc, "weight": w}
            for tid, recs in tr.items() for r in recs for fc, w in r["weights"].items()]
    pd.DataFrame(rows).to_csv(os.path.join(OUT, "weights_by_quarter.csv"), index=False)
    raise Stop
simulate.simulate_path = grab
R.simulate.simulate_path = grab
try:
    R.run()
except Stop:
    print("saved", flush=True)
