from base import *
import time
pd.set_option("display.width",250); pd.set_option("display.max_columns",30)
res = data_access.get_results().set_index("FundCode")
def run(clean, sec, strict, lookback=None, quiet=False):
    sel,scored,matrix = selected_for(clean, sec, strict)
    picked = sel[sel.eligible].head(5)
    funds = tuple(picked.FundCode)
    cols = tuple(config.SCORE_COUNTRY_CLEAN if clean else config.MSCI_COUNTRY_COLS)
    if lookback: config.PORTFOLIO_LOOKBACK_DAYS = lookback
    sigma, info = data_access.portfolio_risk_model(funds, cols)
    return funds, sigma, info, res.loc[list(funds), "aum"]
def frontier_stats(funds, sigma, info, aum, mode="equal", gamma=2.5, ret_override=None, minw=.05, maxw=.40):
    wref = portfolio.reference_weights(aum, mode)
    ss = portfolio.systematic_covariance(sigma, info["idio_vol"].astype(float)**2)
    mu = portfolio.implied_returns(ss, wref, gamma) if ret_override is None else ret_override
    grid = portfolio.weight_grid(len(funds), minw, maxw, .01)
    pts = portfolio.portfolio_points(grid, mu, sigma)
    mask = portfolio.pareto_mask(pts.risk.values, pts.ret.values)
    fr = pts[mask].sort_values("risk").reset_index(drop=True)
    fw = grid[mask][pts[mask].risk.values.argsort()]
    i = portfolio.max_sharpe_index(fr)
    w = pd.Series(fw[i], index=sigma.index)
    rc = portfolio.risk_contribution(w, sigma)
    return mu, w, rc, fr.iloc[i], fr, fw
