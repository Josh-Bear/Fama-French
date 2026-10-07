"""selection.py — คะแนนโซน momentum 12-1/vol, คัดกอง (screening.*), risk model (Σ,Π), ตัดสินน้ำหนัก MS/EW.
ใช้ analysis.screening / analysis.portfolio / analysis.macro_chain / analysis.matching ตรงๆ (read-only)."""
from __future__ import annotations

import numpy as np
import pandas as pd

import config
from analysis import macro_chain, matching, metrics, portfolio, screening


def zone_snapshot(levels_country: pd.DataFrame, levels_sector: pd.DataFrame, t: pd.Timestamp) -> pd.DataFrame:
    rows = []
    for scope, levels, cols in (("country", levels_country, config.SCORE_COUNTRY_CLEAN),
                                 ("sector", levels_sector, config.MSCI_SECTOR_COLS)):
        sub = levels.loc[:t]
        assert sub.index.max() <= t
        for ix in cols:
            s = sub[ix]
            ret = metrics.recent_return(s, window=config.SCORE_RETURN_WINDOW, max_gap_days=None,
                                         skip=config.SCORE_RETURN_SKIP)
            vol = screening.realized_vol_window(s)
            rows.append({"scope": scope, "index": ix, config.SCORE_RETURN_COL: ret, config.SCORE_VOL_COL: vol})
    return pd.DataFrame(rows)


def zone_scores(levels_country, levels_sector, t):
    snap = zone_snapshot(levels_country, levels_sector, t)
    country_z = screening.zone_scores(snap, "country", config.SCORE_COUNTRY_CLEAN)
    sector_z = screening.zone_scores(snap, "sector", config.MSCI_SECTOR_COLS)
    matrix = screening.score_matrix(country_z, sector_z)
    return country_z, sector_z, matrix


def pick_funds(matches_t: pd.DataFrame, matrix: pd.DataFrame, groups: dict) -> pd.DataFrame:
    if matches_t.empty:
        return matches_t.assign(pair=None, eligible=False)
    scored = screening.fund_scores(matches_t, matrix)
    selected = screening.greedy_select(scored, n=config.SCORE_TOP_N, use_secondary=True, strict_and=True,
                                        min_score=config.SCORE_MIN_ELIGIBLE, groups=groups)
    picked = selected[selected["eligible"]].head(config.PORTFOLIO_TOP_N)
    return picked.reset_index(drop=True)


def risk_model_at(picked_funds: list[str], nav_by_fund: dict[str, pd.Series], levels21: pd.DataFrame,
                   t: pd.Timestamp, min_obs: int | None = None) -> dict | None:
    """Σ = B F Bᵀ + D, Π = γ Σ_sys w_ref (w_ref=equal 1/N) — สูตรเดียวกับ portfolio_risk_model หน้า 8."""
    min_obs = config.MIN_REGRESSION_OBS if min_obs is None else min_obs
    levels_t = levels21.loc[:t].iloc[-756:]
    assert levels_t.index.max() <= t
    F = portfolio.factor_covariance(levels_t.pct_change())
    betas, idio, kept = {}, {}, []
    for fc in picked_funds:
        nav_t = nav_by_fund[fc].loc[:t]
        assert len(nav_t) == 0 or nav_t.index.max() <= t
        aligned = matching.build_fund_returns(nav_t, levels_t)
        if len(aligned) < min_obs:
            continue
        res = matching.match_exposure(aligned, alternatives=False)
        b = macro_chain.unstandardize(res["coef"], aligned)
        fund_ret = aligned[matching.FUND_COL]
        total_var = metrics.annualized_volatility(fund_ret) ** 2
        if np.isnan(total_var):
            continue
        d = max(total_var * (1 - res["r2"]), 0.0)
        betas[fc] = b
        idio[fc] = d
        kept.append(fc)
    if not kept:
        return None
    B = pd.DataFrame(betas).T
    D = pd.Series(idio)
    Sigma = portfolio.fund_covariance(B, F, D)
    Sigma_sys = portfolio.systematic_covariance(Sigma, D)
    w_ref = pd.Series(1.0 / len(kept), index=kept)
    Pi = portfolio.implied_returns(Sigma_sys, w_ref, gamma=config.PORTFOLIO_GAMMA)
    return {"kept": kept, "Sigma": Sigma, "Pi": Pi}


def decide_weights(risk_res: dict | None, b0_weights: pd.Series) -> dict:
    if risk_res is None or len(risk_res["kept"]) == 0:
        return {"ms": b0_weights.copy(), "ew": b0_weights.copy(), "fallback": "b0", "n_ok": 0, "kept": []}
    kept = risk_res["kept"]
    n_ok = len(kept)
    ew = pd.Series(1.0 / n_ok, index=kept)
    if n_ok < 3:
        return {"ms": ew.copy(), "ew": ew.copy(), "fallback": "small_n", "n_ok": n_ok, "kept": kept}
    grid = portfolio.weight_grid(n_ok, config.PORTFOLIO_MIN_W, config.PORTFOLIO_MAX_W, config.PORTFOLIO_STEP_W)
    points = portfolio.portfolio_points(grid, risk_res["Pi"], risk_res["Sigma"])
    mask = portfolio.pareto_mask(points["risk"].to_numpy(), points["ret"].to_numpy())
    fgrid = grid[mask]
    fpoints = points[mask].reset_index(drop=True)
    idx = portfolio.max_sharpe_index(fpoints, risk_free=0.0)
    ms = pd.Series(fgrid[idx], index=kept)
    return {"ms": ms, "ew": ew, "fallback": None, "n_ok": n_ok, "kept": kept}
