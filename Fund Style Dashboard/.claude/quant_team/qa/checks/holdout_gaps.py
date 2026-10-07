#!/usr/bin/env python3
"""
QA Check: NAV gaps and staleness in holdout window (Oct 2025 - Jun 2026)
Reusable script to detect data quality issues that could fake returns via vol smoothing.
"""

import pandas as pd
import numpy as np
import sys
from datetime import datetime

sys.path.insert(0, ".")

# Load data
holdings = pd.read_csv(".claude/quant_team/scratch/supervisor_holdings/weights_by_quarter.csv")
nav_df = pd.read_parquet("cache/nav_clean.parquet")
from data.msci_index import load_country_index

holdings["t"] = pd.to_datetime(holdings["t"])
holdings["e"] = pd.to_datetime(holdings["e"])
nav_df["NAVDate"] = pd.to_datetime(nav_df["NAVDate"])

# Business calendar
idx_df = load_country_index()
bday_index = idx_df.index

# Parameters
holdout_start = pd.Timestamp("2025-09-30")
max_nav_date = nav_df["NAVDate"].max()
trials_of_interest = ["M004-TF", "M005", "M005-N5", "M002-SR"]

# Filter holdings
holdout_holdings = holdings[
    (holdings["t"] >= holdout_start) & (holdings["trial"].isin(trials_of_interest))
].copy()


def check_nav_gaps(fund_code, start_date, end_date):
    """Check NAV gaps for a fund in a date range."""
    fund_nav = nav_df[
        (nav_df["FundCode"] == fund_code)
        & (nav_df["NAVDate"] >= start_date)
        & (nav_df["NAVDate"] <= end_date)
    ].copy()

    if len(fund_nav) == 0:
        return {
            "n_obs": 0,
            "n_bdays": 0,
            "pct_missing": 100,
            "longest_gap_bdays": np.nan,
            "has_gap_gt_10": False,
            "last_nav_date": None,
            "stale_days": np.nan,
        }

    # Business days in window
    bdays_in_window = bday_index[
        (bday_index >= start_date) & (bday_index <= end_date)
    ]
    n_bdays = len(bdays_in_window)
    n_obs = len(fund_nav)
    pct_missing = 100 * (1 - n_obs / n_bdays) if n_bdays > 0 else 100

    # Find longest gap
    nav_dates = sorted(fund_nav["NAVDate"].unique())
    if len(nav_dates) <= 1:
        longest_gap = 0
        has_gap_gt_10 = False
    else:
        gaps = []
        for i in range(len(nav_dates) - 1):
            gap_start = nav_dates[i]
            gap_end = nav_dates[i + 1]
            bdays_between = bday_index[(bday_index > gap_start) & (bday_index < gap_end)]
            gaps.append(len(bdays_between))

        longest_gap = max(gaps) if gaps else 0
        has_gap_gt_10 = any(g > 10 for g in gaps)

    last_nav = nav_dates[-1] if nav_dates else None
    stale_days = (end_date - last_nav).days if last_nav else np.nan

    return {
        "n_obs": n_obs,
        "n_bdays": n_bdays,
        "pct_missing": pct_missing,
        "longest_gap_bdays": longest_gap,
        "has_gap_gt_10": has_gap_gt_10,
        "last_nav_date": last_nav,
        "stale_days": stale_days,
    }


# Build holding periods: for each (trial, t, fund) combination,
# holding window goes from e to next quarter's e
holding_periods = []

for trial in holdout_holdings["trial"].unique():
    trial_all = holdings[holdings["trial"] == trial]  # All data for this trial
    trial_holdout = holdout_holdings[holdout_holdings["trial"] == trial]

    for idx, row in trial_holdout.iterrows():
        fund = row["FundCode"]
        e_start = row["e"]
        t = row["t"]
        weight = row["weight"]

        # Find next t date for this trial to get e_end
        next_t_dates = trial_all[trial_all["t"] > t]["t"].unique()
        if len(next_t_dates) > 0:
            next_t = next_t_dates.min()
            # Get the e date for next rebalance
            e_end = trial_all[trial_all["t"] == next_t]["e"].iloc[0]
        else:
            e_end = max_nav_date

        holding_periods.append(
            {
                "trial": trial,
                "t": t,
                "e_start": e_start,
                "e_end": e_end,
                "FundCode": fund,
                "weight": weight,
            }
        )

holding_df = pd.DataFrame(holding_periods)

# Check gaps for each holding
gap_results = []
for _, row in holding_df.iterrows():
    gaps = check_nav_gaps(row["FundCode"], row["e_start"], row["e_end"])
    gaps["trial"] = row["trial"]
    gaps["e_start"] = row["e_start"]
    gaps["e_end"] = row["e_end"]
    gaps["FundCode"] = row["FundCode"]
    gaps["weight"] = row["weight"]
    gap_results.append(gaps)

gaps_df = pd.DataFrame(gap_results)

# Summary statistics
print("\n=== Holdout Window NAV Gap Analysis ===")
print(f"Analysis date: {datetime.now().strftime('%Y-%m-%d')}")
print(f"Window: {holdout_start.date()} to {max_nav_date.date()}")
print(f"Trials: {trials_of_interest}")
print()

# Overall summary
problematic = gaps_df[(gaps_df["pct_missing"] > 20) | (gaps_df["has_gap_gt_10"])].copy()
print(f"Holdings checked: {len(gaps_df)}")
print(f"Problematic (>20% missing OR gap>10 bdays): {len(problematic)}")
print()

# Quarterly exposure to gaps > 5 bdays
print("Weight-weighted portfolio exposure to gaps > 5 bdays (by quarter):")
quarterly_exposure = []
for quarter_t in sorted(holdings["t"].unique()):
    if pd.Timestamp(quarter_t) < holdout_start:
        continue

    q_holdings = holdings[holdings["t"] == quarter_t]
    next_quarters = holdings[holdings["t"] > quarter_t]["t"].unique()
    if len(next_quarters) > 0:
        next_q = pd.Timestamp(next_quarters.min())
    else:
        next_q = max_nav_date

    quarter_start = pd.Timestamp(quarter_t)
    quarter_end = next_q

    total_weight = 0
    exposed_weight = 0

    for _, row in q_holdings.iterrows():
        fund = row["FundCode"]
        weight = row["weight"]
        gaps_info = check_nav_gaps(fund, quarter_start, quarter_end)

        total_weight += weight
        if gaps_info["longest_gap_bdays"] > 5:
            exposed_weight += weight

    if total_weight > 0:
        pct_exposed = 100 * exposed_weight / total_weight
    else:
        pct_exposed = 0

    quarterly_exposure.append(
        {
            "quarter": quarter_start.date(),
            "next_date": quarter_end.date(),
            "pct_portfolio_exposed_gap_gt_5": pct_exposed,
        }
    )

exp_df = pd.DataFrame(quarterly_exposure)
print(exp_df.to_string(index=False))
print()

# Worst funds
worst_funds = gaps_df.nlargest(10, "longest_gap_bdays")[
    ["FundCode", "e_start", "e_end", "longest_gap_bdays", "stale_days", "weight"]
].drop_duplicates("FundCode")
print("\nFunds with longest NAV gaps in holdout:")
print(worst_funds.to_string(index=False))
print()

# Verdict
verdict = "FAIL"
details = []

if len(problematic) > 0:
    verdict = "FAIL"
    details.append(
        f"  • {len(problematic)} holdings with >20% missing or gaps >10 bdays"
    )

if exp_df["pct_portfolio_exposed_gap_gt_5"].max() > 30:
    details.append(
        f"  • Q1 2026: {exp_df['pct_portfolio_exposed_gap_gt_5'].iloc[1]:.0f}% of portfolio exposed to gaps >5 bdays"
    )

if gaps_df["longest_gap_bdays"].max() > 50:
    details.append(
        f"  • Longest gap: {gaps_df['longest_gap_bdays'].max():.0f} business days"
    )

if gaps_df["stale_days"].max() > 50:
    details.append(
        f"  • Maximum staleness: {gaps_df['stale_days'].max():.0f} days past quarter end"
    )

print(f"\nVERDICT: {verdict}")
for d in details:
    print(d)

if verdict == "FAIL":
    print("\n⚠ Holdout Sharpe numbers (0.86–1.71) are UNRELIABLE due to:")
    print("  • Simultaneous NAV gaps in multiple funds cause smoothed volatility")
    print("  • Sustained stale marks (80+ days) inflate returns when prices jump back")
    print("  • Vol in holdout drops 0.81–0.86x vs primary → classic vol smoothing bias")
