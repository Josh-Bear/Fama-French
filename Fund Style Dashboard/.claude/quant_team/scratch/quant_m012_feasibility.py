"""M012 feasibility (read-only): AUM units/duplication, gaps, history length, counts per quarter.
No returns / Sharpe computed. Run: ./.venv/bin/python .claude/quant_team/scratch/quant_m012_feasibility.py
"""
import sys
sys.path.insert(0, ".")
import numpy as np
import pandas as pd
import data_access
from analysis import fund_signals as fs

nav = pd.read_parquet("cache/nav_clean.parquet", columns=["FundCode", "NAVDate", "NAV", "AUM"])
nav["NAVDate"] = pd.to_datetime(nav["NAVDate"])
groups = data_access.share_class_groups()

print("rows", len(nav), "AUM NaN share", nav["AUM"].isna().mean().round(4), "AUM==0 share", (nav["AUM"] == 0).mean().round(4))
print("AUM quantiles (raw):", nav["AUM"].quantile([.01, .1, .5, .9, .99]).round(0).to_dict())
# units: AUM / NAV = implied units outstanding
x = nav.dropna(subset=["AUM"])
x = x[x["AUM"] > 0]
print("implied units median", float((x["AUM"] / x["NAV"]).median()))

# per-class vs whole-fund AUM: within a family, same date, are AUMs identical?
fam = {fc: fs.family_of(fc, groups)[0] for fc in nav["FundCode"].unique()}
nav["family"] = nav["FundCode"].map(fam)
last = nav[nav["NAVDate"] <= "2025-12-31"].dropna(subset=["AUM"])
d = last[last["NAVDate"] == last.groupby("FundCode")["NAVDate"].transform("max")]
multi = d.groupby(["family", "NAVDate"]).filter(lambda g: len(g) > 1)
same = multi.groupby(["family", "NAVDate"])["AUM"].agg(lambda s: s.nunique() == 1)
print("multi-class family-dates", len(same), "share with identical AUM across classes", round(same.mean(), 3))
print(multi.sort_values(["family", "FundCode"]).head(12)[["family", "FundCode", "NAVDate", "AUM"]].to_string())

# gap: days since last non-null positive AUM at each quarter end, for funds with fresh NAV
first_nav = nav.groupby("FundCode")["NAVDate"].min()
print("first NAVDate distribution (year):", first_nav.dt.year.value_counts().sort_index().to_dict())

qs = pd.to_datetime(["2022-03-31", "2022-06-30", "2022-09-30", "2022-12-30", "2023-03-31", "2023-06-30",
                     "2023-09-29", "2023-12-29", "2024-03-29", "2024-06-28", "2024-09-30", "2024-12-31",
                     "2025-03-31", "2025-06-30", "2025-09-30", "2025-12-31"])
pos = nav[(nav["AUM"] > 0)]
rows = []
for t in qs:
    sub = nav[nav["NAVDate"] <= t]
    g = sub.groupby("FundCode")["NAVDate"]
    lastd = g.max()
    fresh = lastd[(t - lastd).dt.days <= 10].index
    fresh = [f for f in fresh if not fs.is_tax_class(f)]
    p = pos[(pos["NAVDate"] <= t) & (pos["FundCode"].isin(fresh))]
    lp = p.sort_values("NAVDate").groupby("FundCode").tail(1).set_index("FundCode")
    age_aum = (t - lp["NAVDate"]).dt.days
    aum_ok_class = lp["AUM"].where(age_aum <= 90)
    df = pd.DataFrame({"FundCode": fresh})
    df["family"] = df["FundCode"].map(fam)
    df["aum"] = df["FundCode"].map(aum_ok_class)
    df["first"] = df["FundCode"].map(first_nav)
    famdf = df.groupby("family").agg(aum_sum=("aum", lambda s: s.sum(min_count=1)), aum_max=("aum", "max"),
                                     first=("first", "min"))
    n = len(famdf)
    aum_missing = famdf["aum_sum"].isna().sum()
    pass_aum = (famdf["aum_sum"] >= 1e8).sum()
    pass_age = (famdf["first"] <= t - pd.Timedelta(days=730)).sum()
    both = ((famdf["aum_sum"] >= 1e8) & (famdf["first"] <= t - pd.Timedelta(days=730))).sum()
    rows.append(dict(t=t.date(), fam_fresh=n, aum_missing90=aum_missing, pass_aum=pass_aum,
                     pass_age2y=pass_age, pass_both=both))
print(pd.DataFrame(rows).to_string(index=False))
