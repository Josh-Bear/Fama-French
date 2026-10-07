import sys; sys.path.insert(0, ".claude/quant_team/backtest"); sys.path.insert(0,".")
import pandas as pd, fees
p = pd.read_csv("base_data/FundProfile.csv", dtype=str, encoding="utf-8-sig"); p.columns=[c.strip() for c in p.columns]
F = sorted(p.loc[p["Fund Policy"]=="F","Fund Code"].unique())
fd = fees.FeeData(F)
print("F FeeData rows", fd.n_rows, "invalid", fd.n_invalid, "funds", fd.n_funds_fee, "median%", {k: round(v,3) for k,v in fd.median.items()})
ids = set(pd.read_csv("base_data/nav_history_db.csv", usecols=["FundCode"], dtype=str)["FundCode"].unique())
print("nav codes", len(ids), "not in FundProfile", len(ids - set(p["Fund Code"])))
