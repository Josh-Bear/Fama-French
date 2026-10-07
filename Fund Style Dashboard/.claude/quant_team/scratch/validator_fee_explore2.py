import sys, pickle
sys.path.insert(0, ".claude/quant_team/backtest"); sys.path.insert(0, ".")
import pandas as pd, numpy as np
pd.set_option("display.width", 250); pd.set_option("display.max_columns", 50); pd.set_option("display.max_rows", 500)
import audit_fees as af
o = af.main()
E,F,A,FT=o["E"],o["F"],o["A"],o["FT"]
pickle.dump({k:o[k] for k in ["E","F","A","FT","pairs","snap","ec","sens","missing_series","sims_meta","yrs","held","median","dup_groups_held"]}, open(".claude/quant_team/scratch/validator_fee_out.pkl","wb"))
print(E.drop(columns=["t"]).round(5).to_string())
print(o["ec"]["flags"].to_string())
print(o["pairs"].to_string())
print(o["ec"]["cannot_buy"], o["ec"]["exec_late"])
