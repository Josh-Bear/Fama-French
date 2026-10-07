"""modeler_explore_style_macro.py — Step 1 สำรวจ (ไม่ใช่ trial, ไม่มี forward return ใดๆ)

ณ แต่ละสิ้นไตรมาส t (2022-03..2025-09): fit exposure ของกองต่อ style / macro factor แบบ point-in-time (weekly, ข้อมูล <= t)
รายงาน coverage, R², stability (t vs t-1q, t vs t-4q), cluster vs theme ของพอร์ตที่ถือ (M004-TF-FX_weights = holdings เท่านั้น),
และความต่างของน้ำหนัก ERC ระหว่าง Σ_LW (ปัจจุบัน) กับ Σ = B F Bᵀ + D (ไม่คำนวณ return/Sharpe ใดๆ หลัง t)

รัน: PYTHONPATH=. ./.venv/bin/python .claude/quant_team/scratch/modeler_explore_style_macro.py  (จาก root)
"""
from __future__ import annotations

import os
import re
import sys
import warnings

import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import fcluster, linkage
from scipy.spatial.distance import squareform
from scipy.stats import spearmanr
from sklearn.covariance import LedoitWolf

warnings.filterwarnings("ignore")
ROOT = os.getcwd()
BT = os.path.join(ROOT, ".claude", "quant_team", "backtest")
sys.path.insert(0, ROOT)
sys.path.insert(0, BT)
import common  # noqa: E402
import config  # noqa: E402
import fund_signals as fs  # noqa: E402
import weighting as wt  # noqa: E402

OUT = os.path.join(ROOT, ".claude", "quant_team", "scratch", "modeler_explore_out")
os.makedirs(OUT, exist_ok=True)

STYLE = ["Momentum", "Quality", "Value", "LowVol"]
MACRO = ["Oil_Brent", "Gold", "USDTHB", "Copper", "DXY", "VIX", "US10Y"]
CTRL = ["MSCI_ACWI", "US_VS_ACWI", "ACWI_ETF"]
THEMES = [("infra", r"INFRA"), ("india", r"INDIA|BHARAT|\bIN\b|TISCOIN"), ("tech", r"TECH|NASDAQ|NGF|INNOV|SEMI|DIGI|ROBO|\bAI\b|NDQ"),
          ("vietnam", r"VIET|VN"), ("china", r"CHINA|CHN|\bCN\b"), ("japan", r"JAP|JP"), ("gold", r"GOLD"),
          ("europe", r"EU|EURO"), ("us", r"\bUS\b|USA|SP500|S&P")]


def theme_of(fc):
    for name, pat in THEMES:
        if re.search(pat, fc.upper()):
            return name
    return "other"


# ---------------- factor levels (daily) ----------------
c_lv = __import__("data.msci_index", fromlist=["x"]).load_country_index()
st = pd.read_csv(config.STYLE_FACTOR_CSV, parse_dates=["Date"]).set_index("Date").sort_index()
mc = pd.read_csv(config.MACRO_FACTOR_CSV, parse_dates=["Date"]).set_index("Date").sort_index()
r = st.pct_change()
lev = {}
for f, (us, intl) in config.STYLE_TICKERS.items():
    rb = r[us] if intl is None else config.STYLE_US_WEIGHT * r[us] + (1 - config.STYLE_US_WEIGHT) * r[intl]
    lv = (1 + rb.fillna(0)).cumprod()
    lev[f] = lv / (st[config.STYLE_BENCHMARK_TICKER] / st[config.STYLE_BENCHMARK_TICKER].iloc[0])
style_lv = pd.DataFrame(lev)
style_lv.columns = STYLE if list(style_lv.columns) != STYLE else style_lv.columns
ctrl = pd.DataFrame({"MSCI_ACWI": c_lv["MSCI_ACWI"], "US_VS_ACWI": c_lv["MSCI_USA"] / c_lv["MSCI_ACWI"]})
fac_daily = pd.concat([ctrl, st[[config.STYLE_BENCHMARK_TICKER]].rename(columns={"ACWI": "ACWI_ETF"}), style_lv, mc[MACRO]], axis=1)
fac_daily = fac_daily.sort_index().ffill(limit=10)


def factor_weekly(weeks):
    """weekly factor returns (Δ for VIX/US10Y) ที่ week points (ข้อมูล <= week point เท่านั้น)."""
    rows = []
    for w in weeks:
        sub = fac_daily.loc[:w]
        assert sub.index.max() <= w
        last = sub.iloc[-1] if len(sub) else pd.Series(np.nan, index=fac_daily.columns)
        rows.append(last)
    lv = pd.DataFrame(rows, index=weeks)
    out = lv.pct_change()
    for d in config.MACRO_DELTA_COLS:
        out[d] = lv[d].diff()
    return out.iloc[1:]


def ols(y, X):
    """OLS + intercept · คืน beta (ต่อ 1 SD ของ factor), t-stat, R², adjR²."""
    m = ~(np.isnan(y) | np.isnan(X).any(1))
    y, X = y[m], X[m]
    n, k = X.shape
    if n < k + 10:
        return None
    sd = X.std(0, ddof=1)
    sd[sd == 0] = 1
    Z = np.column_stack([np.ones(n), (X - X.mean(0)) / sd])
    beta, *_ = np.linalg.lstsq(Z, y, rcond=None)
    res = y - Z @ beta
    s2 = res @ res / (n - k - 1)
    cov = s2 * np.linalg.pinv(Z.T @ Z)
    tt = beta / np.sqrt(np.clip(np.diag(cov), 1e-30, None))
    r2 = 1 - (res @ res) / ((y - y.mean()) @ (y - y.mean()))
    adj = 1 - (1 - r2) * (n - 1) / (n - k - 1)
    return {"beta": beta[1:], "t": tt[1:], "r2": r2, "adj": adj, "n": n, "resvar": s2}


def fund_weekly(arrs, weeks_np):
    dates, values = arrs
    wp = np.array([fs._asof(dates, values, w) for w in weeks_np], dtype=float)
    with np.errstate(invalid="ignore", divide="ignore"):
        return wp[1:] / wp[:-1] - 1.0


# ---------------- data ----------------
nav = common.load_nav()
nav_by_fund = common.build_nav_by_fund(nav)
nav_arrays = fs._prep_arrays(nav_by_fund)
calendar = common.load_calendar()
groups = common.load_groups()
W = pd.read_csv(os.path.join(BT, "results", "M004-TF-FX_weights.csv"), parse_dates=["t"])
quarters = common.quarter_ends(calendar, "2022-03-01", "2025-09-30")

MODELS = {"S": CTRL + STYLE, "M": ["MSCI_ACWI"] + MACRO, "A": ["MSCI_ACWI"]}
rows, betas_by_t, cl_rows, rm_rows, b_rows = [], {}, [], [], []
for t in quarters:
    u_t = common.universe_at(nav, t)
    qctx = fs.QuarterContext(nav_arrays, calendar, t)
    sig = fs.compute_quarter_signals(qctx, list(u_t["FundCode"]))
    I_t, _, _ = fs.investable_set(t, u_t, sig, groups, family_fix=True)
    funds = list(I_t["FundCode"])
    for win, nweeks, min_obs in (("52w", 53, 40), ("104w", 105, 80)):
        weeks = fs.weekly_points(calendar, t, nweeks)
        fw = factor_weekly(weeks)
        fac_ok = fw.notna().all(1).sum()
        wnp = [np.datetime64(w.date()) for w in weeks]
        recs = {}
        for fc in funds:
            y = fund_weekly(nav_arrays[fc], wnp)
            if np.isfinite(y).sum() < min_obs or fac_ok < min_obs:
                continue
            fits = {m: ols(y, fw[cols].to_numpy(float)) for m, cols in MODELS.items()}
            if any(v is None for v in fits.values()):
                continue
            recs[fc] = fits
        n_ok = len(recs)
        if n_ok:
            r2S = np.array([v["S"]["r2"] for v in recs.values()])
            r2M = np.array([v["M"]["r2"] for v in recs.values()])
            r2A = np.array([v["A"]["r2"] for v in recs.values()])
            tS = np.array([v["S"]["t"][3:] for v in recs.values()])
            tM = np.array([v["M"]["t"][1:] for v in recs.values()])
        rows.append({"t": t.date(), "win": win, "n_investable": len(funds), "n_fit": n_ok, "factor_weeks_ok": int(fac_ok),
                     "r2A_med": np.median(r2A) if n_ok else np.nan, "r2S_med": np.median(r2S) if n_ok else np.nan,
                     "r2M_med": np.median(r2M) if n_ok else np.nan,
                     "incS_med": np.median(r2S - r2A) if n_ok else np.nan, "incM_med": np.median(r2M - r2A) if n_ok else np.nan,
                     "fracS_style_t2": np.mean(np.abs(tS) > 2) if n_ok else np.nan,
                     "fracM_macro_t2": np.mean(np.abs(tM) > 2) if n_ok else np.nan})
        if win != "52w" or not n_ok:
            continue
        B = pd.DataFrame({fc: np.r_[v["S"]["beta"][3:], v["M"]["beta"][1:]] for fc, v in recs.items()}, index=STYLE + MACRO).T
        betas_by_t[t] = B
        # route (b): beta ที่จะใช้เป็นสัญญาณ vs SR12 (ซ้ำกันไหม)
        sr = I_t.set_index("FundCode")["SR12"].reindex(B.index)
        for f in ["Quality", "LowVol", "VIX", "US10Y"]:
            b_rows.append({"t": t.date(), "factor": f, "spearman_vs_SR12": spearmanr(B[f], sr, nan_policy="omit")[0],
                           "med_abs_t": np.median(np.abs([recs[fc]["S"]["t"][3 + STYLE.index(f)] if f in STYLE
                                                          else recs[fc]["M"]["t"][1 + MACRO.index(f)] for fc in B.index]))})
        # ---- route (a): clusters on I_t ----
        Z = (B - B.mean()) / B.std()
        lab_exp = pd.Series(fcluster(linkage(Z.to_numpy(), "ward"), 10, "maxclust"), index=B.index)
        R = pd.DataFrame({fc: fund_weekly(nav_arrays[fc], [np.datetime64(w.date()) for w in weeks]) for fc in B.index})
        C = R.corr(min_periods=40).fillna(0).to_numpy().copy()
        np.fill_diagonal(C, 1)
        D = np.clip(1 - C, 0, 2)
        lab_cor = pd.Series(fcluster(linkage(squareform(D, checks=False), "average"), 0.25, "distance"), index=B.index)
        cty = pd.read_parquet(os.path.join(BT, "cache", f"exposure_country_11c_{t.date()}.parquet")).set_index("FundCode")["primary"]
        sec = pd.read_parquet(os.path.join(BT, "cache", f"exposure_sector_10c_{t.date()}.parquet")).set_index("FundCode")["primary"]
        h = W[W["t"] == t].set_index("FundCode")["weight"]
        h = h / h.sum()
        for name, lab in (("exp_k10", lab_exp), ("corr_rho75", lab_cor), ("msci_country", cty), ("msci_sector", sec)):
            g = lab.reindex(h.index).fillna("NA").astype(str)
            gw = h.groupby(g).sum()
            ths = h.index.map(theme_of)
            same, diff = [], []
            hl = list(h.index)
            for i in range(len(hl)):
                for j in range(i + 1, len(hl)):
                    (same if ths[i] == ths[j] and ths[i] != "other" else diff).append(g.iloc[i] == g.iloc[j])
            cl_rows.append({"t": t.date(), "method": name, "n_groups_univ": lab.nunique(), "n_held": len(h),
                            "n_groups_held": gw.size, "max_group_w": gw.max(), "bind35": gw.max() > 0.35,
                            "theme_pairs": len(same), "theme_recall": np.mean(same) if same else np.nan,
                            "false_merge": np.mean(diff) if diff else np.nan, "missing": int((g == "NA").sum())})
        # ---- route (c): ERC weights Σ_LW vs Σ_factor (เฉพาะชุดที่ถือ) ----
        held = [f for f in h.index if f in recs]
        wr = {fc: qctx.weekly_return_series(fc) for fc in held}
        S_lw, kind = wt.covariance_or_fallback(held, wr, {})
        if S_lw is None:
            continue
        w_lw = wt.erc_weights(S_lw, held)
        sd_lw = np.sqrt(np.diag(S_lw))
        corr_lw = S_lw / np.outer(sd_lw, sd_lw)
        iu = np.triu_indices(len(held), 1)
        for mname in ("S", "M"):
            cols = MODELS[mname]
            Fw = fw[cols].dropna()
            Fcov = LedoitWolf().fit(((Fw - Fw.mean()) / Fw.std()).to_numpy()).covariance_ * 52
            Bm = np.array([recs[fc][mname]["beta"] for fc in held])
            Dm = np.diag([recs[fc][mname]["resvar"] * 52 for fc in held])
            Sf = Bm @ Fcov @ Bm.T + Dm
            w_f = wt.erc_weights(Sf, held)
            sd_f = np.sqrt(np.diag(Sf))
            corr_f = Sf / np.outer(sd_f, sd_f)
            rm_rows.append({"t": t.date(), "model": mname, "n_held": len(held), "L1_w_vs_LW": float(np.abs(w_f - w_lw).sum()),
                            "max_abs_dw": float(np.abs(w_f - w_lw).max()), "avgcorr_LW": corr_lw[iu].mean(),
                            "avgcorr_F": corr_f[iu].mean(), "sys_share": float(1 - np.trace(Dm) / np.trace(Sf)),
                            "vol_ratio_F_LW": float(np.sqrt(np.diag(Sf)).mean() / sd_lw.mean())})

summ = pd.DataFrame(rows)
# stability: cross-sectional spearman ของ beta (52w) t vs t-1q, t vs t-4q
st_rows = []
ts = sorted(betas_by_t)
for lag in (1, 4):
    for i in range(lag, len(ts)):
        a, b = betas_by_t[ts[i]], betas_by_t[ts[i - lag]]
        com = a.index.intersection(b.index)
        for f in STYLE + MACRO:
            st_rows.append({"lag_q": lag, "t": ts[i].date(), "factor": f, "rho": spearmanr(a.loc[com, f], b.loc[com, f])[0], "n": len(com)})
stab = pd.DataFrame(st_rows)
cl, rm, bb = pd.DataFrame(cl_rows), pd.DataFrame(rm_rows), pd.DataFrame(b_rows)
for name, df in (("coverage_r2", summ), ("stability", stab), ("clusters", cl), ("riskmodel", rm), ("selection_beta", bb)):
    df.to_csv(os.path.join(OUT, f"{name}.csv"), index=False)

pd.set_option("display.width", 220, "display.max_columns", 30, "display.precision", 3)
print("== coverage / R2 ==\n", summ.groupby("win")[["n_investable", "n_fit", "r2A_med", "r2S_med", "r2M_med", "incS_med", "incM_med",
                                                   "fracS_style_t2", "fracM_macro_t2"]].agg(["min", "median", "max"]).T)
print(summ[summ.win == "104w"][["t", "n_fit", "factor_weeks_ok"]].to_string())
print("== stability (median rho over t) ==\n", stab.groupby(["factor", "lag_q"])["rho"].median().unstack())
print("== clusters ==\n", cl.groupby("method")[["n_groups_univ", "n_groups_held", "max_group_w", "bind35", "theme_recall", "false_merge", "missing"]].mean())
print(cl[cl.t.astype(str).isin(["2022-03-31", "2023-12-29", "2024-06-28", "2025-06-30"])].to_string())
print("== risk model ERC ==\n", rm.groupby("model")[["L1_w_vs_LW", "max_abs_dw", "avgcorr_LW", "avgcorr_F", "sys_share", "vol_ratio_F_LW"]].median())
print("== selection betas ==\n", bb.groupby("factor")[["spearman_vs_SR12", "med_abs_t"]].median())
