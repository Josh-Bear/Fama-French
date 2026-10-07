import warnings; warnings.filterwarnings("ignore")
import sys; sys.path.insert(0,".")
import numpy as np, pandas as pd
import config, data_access
from data import msci_index, nav_loader
from analysis import matching, portfolio
funds=["KT-MFE-A","PRINCIPAL GEF-X","LHGREEN-D","TUSFIN-A"]
sigma, info = data_access.portfolio_risk_model(tuple(funds), tuple(config.SCORE_COUNTRY_CLEAN))
corr_m = sigma/np.outer(np.sqrt(np.diag(sigma)),np.sqrt(np.diag(sigma)))
nav = data_access._nav_by_fund(nav_loader.load_nav_history(funds))
lo=pd.Timestamp("2023-09-08")
print("model corr\n", corr_m.round(2))
print("realized corr on common NAV dates (win 3y) [n common dates]")
for i,a in enumerate(funds):
    for b in funds[i+1:]:
        x = nav[a][nav[a].index>=lo]; y = nav[b][nav[b].index>=lo]
        idx = x.index.intersection(y.index)
        ra = x.loc[idx].pct_change(); rb = y.loc[idx].pct_change()
        d = pd.concat([ra,rb],axis=1).dropna()
        d = d.clip(d.quantile(.01),d.quantile(.99),axis=1)
        print(a,b,"realized %.2f model %.2f n=%d"%(d.corr().iloc[0,1], corr_m.loc[a,b], len(d)))
# closed form tangency vs equal
res = data_access._load_results().set_index("FundCode")
w_ref = portfolio.reference_weights(res.loc[funds,"aum"])
ss = portfolio.systematic_covariance(sigma, info["idio_vol"].astype(float)**2)
mu = portfolio.implied_returns(ss, w_ref)
wt = np.linalg.solve(sigma.to_numpy(), mu.to_numpy()); wt/=wt.sum()
print("unconstrained tangency", dict(zip(funds,wt.round(3))))
D = info["idio_vol"].astype(float)**2
print("idio share of variance", (D/np.diag(sigma)).round(2).to_dict())
eq = np.full((1,len(funds)),1/len(funds))
pe = portfolio.portfolio_points(eq, mu, sigma).iloc[0]
g = portfolio.weight_grid(len(funds)); pts = portfolio.portfolio_points(g, mu, sigma); i=portfolio.max_sharpe_index(pts)
print("equal SR %.3f max SR %.3f  w*=%s"%(pe.ret/pe.risk, pts.ret[i]/pts.risk[i], g[i].round(2)))
print("grid n", len(g))
