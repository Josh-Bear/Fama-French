import warnings; warnings.filterwarnings("ignore")
import sys; sys.path.insert(0,".")
import numpy as np, pandas as pd
import config, data_access
from data import msci_index, nav_loader
from analysis import matching, metrics
funds = ["KT-MFE-A","PRINCIPAL GEF-X","KT-JPFUND-A","K-AEC","TMBGINFRA","TUSFIN-A"]
nav = data_access._nav_by_fund(nav_loader.load_nav_history(funds))
cty = msci_index.load_country_index()[config.SCORE_COUNTRY_CLEAN]
lv = pd.concat([cty, msci_index.load_sector_index()],axis=1).iloc[-756:]
rng = np.random.default_rng(0)
print("=== (a) placebo R2: circularly shifted factor returns (null) vs actual")
for f in ["TMBGINFRA","KT-MFE-A","K-AEC"]:
    a = matching.build_fund_returns(nav[f], lv)
    act = matching.match_exposure(a, alternatives=False)["r2"]
    cols=[c for c in a.columns if c!=matching.FUND_COL]
    nulls=[]
    for k in range(12):
        sh = rng.integers(20, len(a)-20)
        b = a.copy(); b[cols] = np.roll(a[cols].to_numpy(), sh, axis=0)
        nulls.append(matching.match_exposure(b, alternatives=False)["r2"])
    print(f, "n=",len(a), "actual R2 %.3f"%act, "null R2 mean %.3f max %.3f"%(np.mean(nulls), np.max(nulls)))
print("=== (b) NAV lag: R2 vs lagged index (fund vs index shifted by 1 index day)")
for f in ["KT-MFE-A","PRINCIPAL GEF-X","KT-JPFUND-A","K-AEC"]:
    out={}
    for lag in (0,1,-1):
        lv2 = lv.shift(lag)   # lag=1 : index level from previous day used at NAVDate t
        a = matching.build_fund_returns(nav[f], lv2.dropna())
        out[lag]=round(matching.match_exposure(a, alternatives=False)["r2"],3)
    print(f,out)
print("=== (c) annualisation: gap-normalised vol vs sqrt(252) naive")
for f in funds:
    a = matching.build_fund_returns(nav[f], lv)
    r = a[matching.FUND_COL]
    gap = pd.Series(a.index).diff().dt.days
    idx_days = lv.index.to_series()
    # trading-day gap
    pos = pd.Series(np.arange(len(lv)), index=lv.index).reindex(a.index, method="ffill").to_numpy()
    tg = np.diff(np.r_[pos[0]-1, pos])
    naive = r.std(ddof=1)*np.sqrt(252)
    adj = (r.to_numpy()/np.sqrt(np.clip(tg,1,None))).std(ddof=1)*np.sqrt(252)
    print(f, "naive %.3f gap-adj %.3f ratio var %.2f mean trading-day gap %.2f"%(naive, adj, (naive/adj)**2, tg.mean()))
