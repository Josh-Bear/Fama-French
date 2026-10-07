import sys
sys.path.insert(0, ".")
sys.path.insert(0, ".claude/quant_team/backtest")
import numpy as np
import pandas as pd
from scipy import stats
import simulate

RESULTS = ".claude/quant_team/backtest/results/"

trials = {
    "M002-SR": 3, "M002-MOM": 4, "M002-NOH": 5, "M003-ERC": 6, "M003-HRP": 7,
    "M004-VT": 8, "M004-TF": 9, "M005": 10, "M005-N5": 11, "M005-N10": 12, "M005-NODD": 13,
}

PRIMARY_END = pd.Timestamp("2025-12-31")


def load_monthly_returns(trial):
    fp = f"{RESULTS}M002-M005_{trial}_equity_curve.csv"
    s = pd.read_csv(fp, index_col=0, parse_dates=True)["value"]
    s = s.sort_index()
    prim = s.loc[:PRIMARY_END]
    return prim.pct_change().dropna()


def psr_dsr_monthly(r, n_trials, rf_annual=0.02):
    """Corrected: work in MONTHLY units throughout (sr, SE, SR0 all monthly), not annualized sr plugged
    into per-period SE — this is the fix for the unit-mismatch bug (annualized sr inflates z by ~sqrt(12))."""
    r = pd.Series(r).dropna()
    n_eff = simulate.effective_n(r)
    rf_m = rf_annual / 12.0
    sr_m = (r - rf_m).mean() / r.std(ddof=1)  # monthly Sharpe (NOT annualized)
    skew = float(stats.skew(r.to_numpy(), bias=False)) if len(r) > 2 else 0.0
    kurt = float(stats.kurtosis(r.to_numpy(), fisher=False, bias=False)) if len(r) > 3 else 3.0
    se = np.sqrt(max((1 - skew * sr_m + (kurt - 1) / 4.0 * sr_m ** 2) / max(n_eff - 1, 1e-6), 1e-12))
    # PSR: n_trials=1 -> sr0=0
    z_psr = (sr_m - 0.0) / se
    psr = float(stats.norm.cdf(z_psr))
    if n_trials <= 1:
        sr0 = 0.0
    else:
        euler = 0.5772156649
        sr0 = ((1 - euler) * stats.norm.ppf(1 - 1.0 / n_trials) +
               euler * stats.norm.ppf(1 - 1.0 / (n_trials * np.e))) / np.sqrt(max(n_eff, 2.0))
    z_dsr = (sr_m - sr0) / se
    dsr = float(stats.norm.cdf(z_dsr))
    return psr, dsr, n_eff, sr_m


print("=== 1) Corrected monthly-unit PSR/DSR vs code's as-reported (annualized-sr-in-monthly-formula bug) ===")
print(f"{'trial':10s} {'sr_ann(reported)':>16s} {'DSR(code,buggy)':>16s} {'PSR(fix)':>9s} {'DSR(fix)':>9s} {'n_eff':>7s}")
for t, ntr in trials.items():
    r = load_monthly_returns(t)
    sr_ann = simulate.sharpe(r, 0.02)
    dsr_code = simulate.deflated_sharpe(r, 0.02, ntr)
    psr_fix, dsr_fix, n_eff, sr_m = psr_dsr_monthly(r, ntr)
    print(f"{t:10s} {sr_ann:16.4f} {dsr_code:16.4f} {psr_fix:9.4f} {dsr_fix:9.4f} {n_eff:7.2f}")

print()
print("=== 2) Holdout period (2026-01-30 .. 2026-07-31, ~7 months after primary) Sharpe, no CI (too few obs) ===")
for t in ["M002-SR", "M003-ERC", "M004-TF", "M005", "M005-N5", "M005-NODD"]:
    fp = f"{RESULTS}M002-M005_{t}_equity_curve.csv"
    s = pd.read_csv(fp, index_col=0, parse_dates=True)["value"].sort_index()
    hold = s.loc["2025-12-31":]
    r = hold.pct_change().dropna()
    sh = simulate.sharpe(r, 0.02)
    tot_ret = hold.iloc[-1] / hold.iloc[0] - 1
    print(f"{t:10s} n_months={len(r)} total_ret={tot_ret:+.3f} sharpe_ann={sh:.3f} monthly_rets={[round(x,4) for x in r.tolist()]}")

print()
print("=== 3) Drop best quarter: recompute monthly-return Sharpe after removing the single best QUARTER's months ===")
# quarter boundaries within primary (rebalance dates from plan): use calendar quarters of the monthly index
for t in ["M002-SR", "M004-TF", "M005", "M005-N5"]:
    r = load_monthly_returns(t)
    q = r.index.to_period("Q")
    qret = r.groupby(q).apply(lambda x: (1 + x).prod() - 1)
    best_q = qret.idxmax()
    r_drop = r[q != best_q]
    sh_full = simulate.sharpe(r, 0.02)
    sh_drop = simulate.sharpe(r_drop, 0.02)
    print(f"{t:10s} best_q={best_q} best_q_ret={qret.max():+.3f} sharpe_full={sh_full:.3f} sharpe_drop_best_q={sh_drop:.3f}  n_months_drop={len(r_drop)}")

print()
print("=== 3b) Drop best SINGLE MONTH too (more aggressive check) ===")
for t in ["M002-SR", "M004-TF", "M005", "M005-N5"]:
    r = load_monthly_returns(t)
    best_m = r.idxmax()
    r_drop = r.drop(best_m)
    sh_full = simulate.sharpe(r, 0.02)
    sh_drop = simulate.sharpe(r_drop, 0.02)
    print(f"{t:10s} best_month={best_m.date()} ret={r.max():+.3f} sharpe_full={sh_full:.3f} sharpe_drop_best_month={sh_drop:.3f}")
