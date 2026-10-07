import warnings; warnings.filterwarnings("ignore")
import sys; sys.path.insert(0,".")
import numpy as np, pandas as pd
import config, data_access
from data import msci_index, nav_loader
res = data_access._load_results()
funds = data_access.policy_universe(res, config.SCORE_POLICY)
nav = data_access._nav_by_fund(nav_loader.load_nav_history(funds))
cty = msci_index.load_country_index()[config.SCORE_COUNTRY_CLEAN]
lv = pd.concat([cty, msci_index.load_sector_index()],axis=1).iloc[-config.PORTFOLIO_LOOKBACK_DAYS:]
print("index window", lv.index[0], lv.index[-1], len(lv))
rows=[]
from analysis import matching
for f in funds:
    a = matching.build_fund_returns(nav[f], lv)
    d = a.index.to_series().diff().dt.days.dropna()
    rows.append((f,len(a), d.median() if len(d) else np.nan, d.mean() if len(d) else np.nan))
df = pd.DataFrame(rows, columns=["f","n","med_gap","mean_gap"]).set_index("f")
print(df.n.describe()); print((df.n<200).sum(), (df.n<100).sum(), (df.n<252).sum(), len(df))
print(df.med_gap.value_counts().head())
print(df.loc[["KT-MFE-A","PRINCIPAL GEF-X","KT-JPFUND-A","K-AEC","TMBGINFRA","LHGREEN-D","TUSFIN-A"]])
print(nav["TMBGINFRA"].index[[0,-1]], len(nav["TMBGINFRA"]))
print((df.n/ (len(lv)-1)).describe())
