#!/usr/bin/env python3
"""
Validate TH_POLICY_RATE.csv for use as risk-free rate in backtest.
Checks: structure, internal consistency, coverage, annual averages.
"""
import sys
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, '.')

# File path
DATA_DIR = Path('base_data')
CSV_FILE = DATA_DIR / 'TH_POLICY_RATE.csv'
RESULTS_DIR = Path('.claude/quant_team/qa')
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

# Expected annual averages (team values, weighted daily) - in % form as per CSV
EXPECTED_ANNUAL = {
    2022: 0.68,  # 0.68%
    2023: 1.99,  # 1.99%
    2024: 2.45,  # 2.45%
    2025: 1.77,  # 1.77%
}

# Read file
with open(CSV_FILE) as f:
    lines = f.readlines()

print(f"Reading {CSV_FILE}...")
header_line = None
data_rows = []
comments = []

for i, line in enumerate(lines, 1):
    line = line.rstrip('\n')
    if line.startswith('#'):
        comments.append(line)
    elif line.strip() == '':
        continue
    elif i == 3:  # Expected header
        header_line = line
    else:
        if line:
            data_rows.append(line)

# Parse CSV
df = pd.read_csv(CSV_FILE, comment='#')
print(f"Loaded {len(df)} rows")

# ============================================================================
# 1. STRUCTURE CHECKS
# ============================================================================
print("\n=== 1. STRUCTURE CHECKS ===")

checks = {}

# Parse dates
try:
    df['date'] = pd.to_datetime(df['announce_date'])
    checks['date_parsing'] = {'status': 'PASS', 'note': f'All {len(df)} dates parsed successfully'}
except Exception as e:
    checks['date_parsing'] = {'status': 'FAIL', 'note': f'Error: {e}'}
    sys.exit(1)

# Check sorted and unique
is_sorted = (df['date'] == df['date'].sort_values()).all()
is_unique = df['date'].is_unique
checks['date_sort'] = {'status': 'PASS' if is_sorted else 'WARN',
                       'note': 'Dates in ascending order' if is_sorted else 'Not sorted'}
checks['date_unique'] = {'status': 'PASS' if is_unique else 'FAIL',
                         'note': 'No duplicate dates' if is_unique else 'Duplicates found'}

# Check rates are numeric and in range
try:
    rates_numeric = pd.to_numeric(df['rate_pct'])
    in_range = (rates_numeric >= 0) & (rates_numeric <= 5.0)
    checks['rate_numeric'] = {'status': 'PASS', 'note': f'All rates numeric, range [{rates_numeric.min()}, {rates_numeric.max()}]%'}
    checks['rate_range'] = {'status': 'PASS' if in_range.all() else 'FAIL',
                           'note': 'All rates in [0%, 5%]' if in_range.all() else f'Out of range: {rates_numeric[~in_range].tolist()}'}
except Exception as e:
    checks['rate_numeric'] = {'status': 'FAIL', 'note': f'Error: {e}'}

# Check for nulls
has_nulls = df[['announce_date', 'rate_pct', 'decision']].isnull().any().any()
checks['no_nulls'] = {'status': 'PASS' if not has_nulls else 'FAIL',
                      'note': 'No null values' if not has_nulls else 'Null values found'}

# ============================================================================
# 2. INTERNAL CONSISTENCY
# ============================================================================
print("\n=== 2. INTERNAL CONSISTENCY ===")

df['rate'] = pd.to_numeric(df['rate_pct'])
df['prev_rate'] = df['rate'].shift()
df['rate_change'] = (df['rate'] - df['prev_rate']) * 100  # in bps

consistency_issues = []

for i in range(1, len(df)):
    row = df.iloc[i]
    decision = row['decision']
    change_bps = row['rate_change']

    if decision == 'Hold':
        if not np.isclose(change_bps, 0):
            consistency_issues.append(
                f"Row {i+2}: {row['announce_date']} Hold but rate changed by {change_bps:.1f} bps "
                f"({row['prev_rate']:.2f}% → {row['rate']:.2f}%)"
            )
    elif 'Cut' in decision:
        expected_bps = -int(decision.split()[1])
        if not np.isclose(change_bps, expected_bps):
            consistency_issues.append(
                f"Row {i+2}: {row['announce_date']} {decision} but rate changed by {change_bps:.1f} bps "
                f"(expected {expected_bps})"
            )
    elif 'Raise' in decision:
        expected_bps = int(decision.split()[1])
        if not np.isclose(change_bps, expected_bps):
            consistency_issues.append(
                f"Row {i+2}: {row['announce_date']} {decision} but rate changed by {change_bps:.1f} bps "
                f"(expected {expected_bps})"
            )

if consistency_issues:
    checks['decision_consistency'] = {'status': 'FAIL', 'note': '; '.join(consistency_issues[:3])}
else:
    checks['decision_consistency'] = {'status': 'PASS', 'note': 'All decisions match rate changes'}

# Check meeting intervals
df['days_since_prev'] = df['date'].diff().dt.days
meetings_in_range = df['days_since_prev'].dropna()

unusual_gaps = []
for i in range(1, len(df)):
    gap = df.iloc[i]['days_since_prev']
    if pd.notna(gap) and gap > 200:  # Long gap
        unusual_gaps.append(f"{df.iloc[i]['announce_date']}: {gap:.0f} days")

if unusual_gaps:
    checks['meeting_interval'] = {'status': 'WARN', 'note': f'Large gaps detected: {unusual_gaps[0]} and {len(unusual_gaps)-1} more'}
else:
    checks['meeting_interval'] = {'status': 'PASS', 'note': f'Meeting intervals reasonable (~{meetings_in_range.median():.0f} days median)'}

# ============================================================================
# 3. BACKTEST PERIOD (2021-01 to 2026-08)
# ============================================================================
print("\n=== 3. BACKTEST PERIOD COVERAGE ===")

backtest_start = pd.Timestamp('2021-01-01')
backtest_end = pd.Timestamp('2026-08-31')

df_bt = df[(df['date'] >= backtest_start) & (df['date'] <= backtest_end)].copy()
print(f"Rows in backtest period: {len(df_bt)}")
print(f"Date range: {df_bt['date'].min().date()} to {df_bt['date'].max().date()}")

if df_bt['date'].min() > backtest_start:
    checks['coverage_start'] = {'status': 'WARN', 'note': f'Coverage starts {df_bt["date"].min().date()}, after 2021-01-01'}
else:
    checks['coverage_start'] = {'status': 'PASS', 'note': 'Coverage includes 2021-01'}

if df_bt['date'].max() < backtest_end:
    checks['coverage_end'] = {'status': 'WARN', 'note': f'Coverage ends {df_bt["date"].max().date()}, before 2026-08-31'}
else:
    checks['coverage_end'] = {'status': 'PASS', 'note': f'Coverage includes 2026-08 (latest: {df_bt["date"].max().date()})'}

# Check for gaps
df_bt_sorted = df_bt.sort_values('date').reset_index(drop=True)
gaps = []
for i in range(1, len(df_bt_sorted)):
    gap = (df_bt_sorted.iloc[i]['date'] - df_bt_sorted.iloc[i-1]['date']).days
    if gap > 100:  # Large gap
        gaps.append(f"{df_bt_sorted.iloc[i-1]['announce_date']} → {df_bt_sorted.iloc[i]['announce_date']}: {gap} days")

if gaps:
    checks['coverage_gaps'] = {'status': 'WARN', 'note': f'{len(gaps)} large gap(s): {gaps[0]}'}
else:
    checks['coverage_gaps'] = {'status': 'PASS', 'note': 'No large gaps in period'}

# ============================================================================
# 4. ANNUAL WEIGHTED AVERAGES (effective from day after announcement)
# ============================================================================
print("\n=== 4. ANNUAL WEIGHTED AVERAGES ===")

# Build daily time series (rate effective from day after announcement)
all_dates = pd.date_range(df['date'].min() - timedelta(days=1), df['date'].max() + timedelta(days=365), freq='D')
daily_rate = pd.Series(index=all_dates, dtype=float)

current_rate = df.iloc[0]['rate']
daily_rate[: df.iloc[0]['date']] = current_rate  # Before first announcement

for i in range(len(df)):
    effective_date = df.iloc[i]['date'] + timedelta(days=1)
    if i < len(df) - 1:
        next_date = df.iloc[i+1]['date']
    else:
        next_date = daily_rate.index[-1] + timedelta(days=1)

    daily_rate[effective_date:next_date] = df.iloc[i]['rate']

# Calculate annual averages for 2022-2025
annual_avgs = {}
for year in range(2022, 2026):
    year_start = pd.Timestamp(f'{year}-01-01')
    year_end = pd.Timestamp(f'{year}-12-31')
    year_data = daily_rate[(daily_rate.index >= year_start) & (daily_rate.index <= year_end)]

    if len(year_data) > 0:
        avg = year_data.mean()
        annual_avgs[year] = avg

        expected = EXPECTED_ANNUAL.get(year)
        if expected:
            diff_pct = (avg - expected) / expected * 100
            status = 'PASS' if abs(diff_pct) < 1 else 'WARN'
            checks[f'annual_avg_{year}'] = {
                'status': status,
                'note': f'Calculated {avg:.4f}% vs expected {expected:.4f}% (diff {diff_pct:+.2f}%)'
            }

# ============================================================================
# 5. SUMMARY
# ============================================================================
print("\n=== QA RESULTS SUMMARY ===")

for check_name, result in checks.items():
    status = result['status']
    note = result['note']
    print(f"{status:6} | {check_name:30} | {note}")

# ============================================================================
# 6. RATE CHANGE TABLE (for backtest period)
# ============================================================================
print("\n=== RATE CHANGES IN BACKTEST PERIOD ===")
rate_changes = df_bt[df_bt['decision'] != 'Hold'].copy()
print(f"\nTotal rate changes (2021-01 to 2026-08): {len(rate_changes)}")
print(rate_changes[['announce_date', 'rate_pct', 'decision']].to_string(index=False))

# ============================================================================
# EXPORT RESULTS
# ============================================================================
results = {
    'checks': checks,
    'annual_averages': annual_avgs,
    'rate_changes_backtest': rate_changes[['announce_date', 'rate_pct', 'decision']].to_dict(),
    'date_range': {
        'start': df['date'].min().date().isoformat(),
        'end': df['date'].max().date().isoformat(),
        'backtest_start': df_bt['date'].min().date().isoformat(),
        'backtest_end': df_bt['date'].max().date().isoformat(),
    }
}

# Save summary JSON
import json
summary_file = RESULTS_DIR / 'check_policy_rate_results.json'
with open(summary_file, 'w') as f:
    json.dump(results, f, indent=2, default=str)
print(f"\nResults saved to {summary_file}")
