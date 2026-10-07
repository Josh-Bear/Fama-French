import warnings; warnings.filterwarnings("ignore")
import sys; sys.path.insert(0,".")
import numpy as np, pandas as pd
pd.set_option("display.width",250)
import config, data_access
from analysis import portfolio
res = data_access._load_results().set_index("FundCode")
def frontier(sigma, mu, n):
    grid = portfolio.weight_grid(n)
    pts = portfolio.portfolio_points(grid, mu, sigma)
    i = portfolio.max_sharpe_index(pts)
    return grid[i], pts.iloc[i], grid, pts
def report(tag, sigma, mu):
    n=len(sigma); w,pt,grid,pts = frontier(sigma,mu,n)
    rc = portfolio.risk_contribution(pd.Series(w,index=sigma.index), sigma)
    print(tag, "w=",dict(zip(sigma.index,np.round(w,2))), "RC=",np.round(rc.values,2), "risk %.3f ret %.3f SR %.2f"%(pt.risk,pt.ret,pt.ret/pt.risk), "| at bound:", int(((np.isclose(w,0.4))|(np.isclose(w,0.05))).sum()),"of",n)
sets = {"A4":(("KT-MFE-A","PRINCIPAL GEF-X","KT-JPFUND-A","K-AEC"), config.SCORE_COUNTRY_CLEAN),
        "B5":(("KT-MFE-A","PRINCIPAL GEF-X","LHGREEN-D","TUSFIN-A","TMBGINFRA"), config.SCORE_COUNTRY_CLEAN)}
which = sys.argv[1]
funds, ids = sets[which]
for lb in (504, 756, 1008):
    config.PORTFOLIO_LOOKBACK_DAYS = lb
    try:
        sigma, info = data_access.portfolio_risk_model(funds, tuple(ids))
    except Exception as e:
        print(which, lb, "ERR", e); continue
    idio = info["idio_vol"].astype(float)**2
    w_eq = portfolio.reference_weights(res.loc[list(funds),"aum"], "equal")
    w_aum = portfolio.reference_weights(res.loc[list(funds),"aum"], "aum")
    ss = portfolio.systematic_covariance(sigma, idio)
    print(f"--- {which} lookback {lb} n_obs", info.n_obs.astype(int).to_dict(), "r2", info.r2.astype(float).round(2).to_dict())
    report("equal ref", sigma, portfolio.implied_returns(ss, w_eq))
    report("aum   ref", sigma, portfolio.implied_returns(ss, w_aum))
    report("gamma x4 ", sigma, portfolio.implied_returns(ss, w_eq, gamma=10))
    if lb==756:
        # D corrected for NAV gaps: scale idio by 1/k using per-fund ratio (approx values measured)
        ratio = pd.Series({"KT-MFE-A":1.68,"PRINCIPAL GEF-X":1.33,"KT-JPFUND-A":1.23,"K-AEC":1.36,"TMBGINFRA":1.09,"TUSFIN-A":1.30,"LHGREEN-D":1.3}).reindex(sigma.index)
        s2 = sigma - np.diag(idio.to_numpy()*(1-1/ratio.to_numpy()))
        report("D gap-corrected", s2, portfolio.implied_returns(portfolio.systematic_covariance(s2, idio/ratio), w_eq))
        # pi
        print("Pi eq", portfolio.implied_returns(ss,w_eq).round(4).to_dict())
