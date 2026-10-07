import warnings; warnings.filterwarnings("ignore")
import sys; sys.path.insert(0,".")
import numpy as np, pandas as pd
pd.set_option("display.width",250); pd.set_option("display.max_columns",30)
import config, data_access
from analysis import portfolio, screening
snap = data_access._load_index_snapshot()
res = data_access._load_results().set_index("FundCode")
def run(clean, strict, sec, n=5):
    m = data_access.score_matches(clean)
    ids = config.SCORE_COUNTRY_CLEAN if clean else config.MSCI_COUNTRY_COLS
    c = screening.zone_scores(snap,"country", config.SCORE_COUNTRY_CLEAN if clean else None)
    s = screening.zone_scores(snap,"sector")
    sc = screening.fund_scores(m, screening.score_matrix(c,s))
    sel = screening.greedy_select(sc, n=20, use_secondary=sec, strict_and=strict, min_score=0.7)
    return sel, ids
for (clean,strict,sec) in [(True,True,True),(False,True,True),(True,False,True)]:
    sel, ids = run(clean,strict,sec)
    p = sel[sel.eligible].head(5)
    print("=== clean",clean,"AND",strict,"sec",sec); print(p[["FundCode","pair","used_country","used_sector","pair_score","country_r2","sector_r2"]])
    funds = tuple(p.FundCode)
    sigma, info = data_access.portfolio_risk_model(funds, tuple(ids))
    w_ref = portfolio.reference_weights(res.loc[list(funds),"aum"])
    ss = portfolio.systematic_covariance(sigma, info["idio_vol"].astype(float)**2)
    mu = portfolio.implied_returns(ss, w_ref)
    info["vol_sigma"] = np.sqrt(np.diag(sigma)); info["Pi"]=mu; info["aum"]=res.loc[list(funds),"aum"]
    info["sys_vol"]=np.sqrt(np.diag(ss))
    print(info.round(3))
    print("corr:\n", (sigma/np.outer(np.sqrt(np.diag(sigma)),np.sqrt(np.diag(sigma)))).round(2))
