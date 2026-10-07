"""quant-modeler M001: read-only feasibility (date ranges, PIT universe counts, ElasticNet timing). ไม่รายงาน Sharpe."""
import sys, time
sys.path.insert(0, ".")
import numpy as np, pandas as pd
import config
from data import msci_index
from analysis import matching

cty = msci_index.load_country_index()[config.SCORE_COUNTRY_CLEAN]
sec = msci_index.load_sector_index()
idx = pd.concat([cty, sec], axis=1)
print("index", idx.index.min().date(), idx.index.max().date(), len(idx), "rows; NaN cells", int(idx.isna().sum().sum()))
d = idx.index
print("date at pos 252/253/756:", d[252].date(), d[253].date(), d[min(756, len(d)-1)].date())

nav = pd.read_parquet("cache/nav_clean.parquet", columns=["FundCode", "NAVDate", "NAV", "status"])
nav["NAVDate"] = pd.to_datetime(nav["NAVDate"])
print("nav funds", nav.FundCode.nunique(), nav.NAVDate.min().date(), nav.NAVDate.max().date())
qe = pd.Series(d, index=d).groupby(d.to_period("Q")).max()
g = nav.groupby("FundCode")
rows = []
for t in qe:
    sub = nav[nav.NAVDate <= t]
    last = sub.groupby("FundCode").NAVDate.max()
    cnt = sub.groupby("FundCode").NAVDate.nunique()
    cnt21 = sub[sub.NAVDate >= d[0]].groupby("FundCode").NAVDate.nunique()
    fresh = last[(t - last).dt.days <= config.NAV_STALE_MAX_DAYS].index
    u600 = [f for f in fresh if cnt.get(f, 0) > config.MIN_DATA_POINTS]
    u252 = [f for f in fresh if cnt21.get(f, 0) >= 252]
    rows.append((t.date(), len(fresh), len(u600), len(u252), len(set(u600) & set(u252))))
print(pd.DataFrame(rows, columns=["t", "fresh90", "fresh&>600", "fresh&>=252_since2021", "both"]).to_string(index=False))

# timing: one fund, country11 + sector10 ElasticNetCV
f = nav[nav.status == "keep"].FundCode.iloc[0]
s = nav[nav.FundCode == f].set_index("NAVDate").NAV
t0 = time.time()
for lv in (cty, sec):
    al = matching.build_fund_returns(s, lv)
    matching.match_exposure(al, alternatives=False)
print("ElasticNetCV 2 scopes, 1 fund:", round(time.time() - t0, 2), "s  n_obs", len(al))
sc = pd.read_csv(config.SHARE_CLASS_CSV, encoding="utf-8-sig", dtype=str)
print("share_class_groups rows", len(sc), "groups", sc["group"].nunique())
fee = pd.read_csv("base_data/SecFundFee.csv", nrows=3, encoding="utf-8-sig")
print("SecFundFee cols", list(fee.columns)[:25])
