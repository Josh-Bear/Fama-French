import sys, pickle
sys.path.insert(0, ".claude/quant_team/backtest"); sys.path.insert(0, ".")
import pandas as pd
pd.set_option("display.width", 250); pd.set_option("display.max_columns", 50); pd.set_option("display.max_rows", 500)
import audit_fees as af
o = af.main()
print("mismatch AFD vs orig:", o["afd_vs_orig_mismatch"][:10], len(o["afd_vs_orig_mismatch"]))
print("median", o["median"], o["median_orig"])
print("dups held", o["dup_groups_held"], "all", o["dup_groups_all"])
print("sims", o["sims_meta"]); print("ref", o["reference"])
print("max diff entry", o["max_abs_diff_entry"])
print("missing", o["missing_series"])
for n, r in o["sens"]:
    print(r"%-60s"%n, {k:(round(v["sharpe"],4), round(v["cost_bp_yr"],1)) for k,v in r.items()})
print("-----")
