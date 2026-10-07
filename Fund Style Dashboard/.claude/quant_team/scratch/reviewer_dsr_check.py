import sys
sys.path.insert(0, ".")
sys.path.insert(0, ".claude/quant_team/backtest")
import simulate

# reported in trials.csv (bugfix-rerun): n_obs hardcoded = 15 (quarter count, WRONG)
# actual monthly obs in primary period (from M001_summary_metrics.csv n_months) = 44
for label, sh, trials in [("MS", 0.2506, 1), ("EW", 0.1344, 2)]:
    dsr_wrong = simulate.deflated_sharpe(sh, 15, trials)
    dsr_right = simulate.deflated_sharpe(sh, 44, trials)
    print(f"{label}: sharpe={sh} trials={trials}  DSR(n_obs=15,as-reported)={dsr_wrong:.4f}  DSR(n_obs=44,correct)={dsr_right:.4f}")
