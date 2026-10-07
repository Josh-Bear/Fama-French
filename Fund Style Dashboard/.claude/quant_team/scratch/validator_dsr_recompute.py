"""validator_dsr_recompute.py -- recompute DSR (unit-fixed) + PSR(N=1) จาก equity curve ที่ save ไว้แล้ว
(cost=0.5%/side, rf=2%, primary period <=2025-12-31) -- ไม่ rerun backtest ใดๆ ทั้งสิ้น, อ่านไฟล์ผลลัพธ์เดิมเท่านั้น.
"""
import sys
import pandas as pd

sys.path.insert(0, ".")
sys.path.insert(0, ".claude/quant_team/backtest")
import simulate  # noqa: E402

RESULTS_DIR = ".claude/quant_team/backtest/results"
PRIMARY_END = pd.Timestamp("2025-12-31")
RF_PRIMARY = 0.02

# model_id -> (equity_curve file, n_trials_cumulative ตามที่บันทึกล่าสุดใน trials.csv, sharpe ที่รายงาน)
TRIALS = {
    "M001-MS": ("M001_MS_equity_curve.csv", 1, 0.2506),
    "M001-EW": ("M001_EW_equity_curve.csv", 2, 0.1344),
    "M002-SR": ("M002-M005_M002-SR_equity_curve.csv", 3, 0.6357),
    "M002-MOM": ("M002-M005_M002-MOM_equity_curve.csv", 4, 0.2192),
    "M002-NOH": ("M002-M005_M002-NOH_equity_curve.csv", 5, 0.4447),
    "M003-ERC": ("M002-M005_M003-ERC_equity_curve.csv", 6, 0.6492),
    "M003-HRP": ("M002-M005_M003-HRP_equity_curve.csv", 7, 0.6026),
    "M004-VT": ("M002-M005_M004-VT_equity_curve.csv", 8, 0.5001),
    "M004-TF": ("M002-M005_M004-TF_equity_curve.csv", 9, 0.7378),
    "M005": ("M002-M005_M005_equity_curve.csv", 10, 0.4547),
    "M005-N5": ("M002-M005_M005-N5_equity_curve.csv", 11, 0.8448),
    "M005-N10": ("M002-M005_M005-N10_equity_curve.csv", 12, 0.5143),
    "M005-NODD": ("M002-M005_M005-NODD_equity_curve.csv", 13, 0.6415),
}

# reviewer appendix (M002-M005_review.md) -- DSR แก้ unit แล้ว, ใช้ n_trials=13 คงที่ทุกแถว
REVIEWER_APPENDIX_FLAT13 = {
    "M002-SR": 0.316, "M002-MOM": 0.103, "M002-NOH": 0.200,
    "M003-ERC": 0.326, "M003-HRP": 0.285, "M004-VT": 0.238, "M004-TF": 0.359,
    "M005": 0.168, "M005-N5": 0.447, "M005-N10": 0.202, "M005-NODD": 0.321,
}

rows = []
for mid, (fname, n_trials_cum, sh_reported) in TRIALS.items():
    vals = pd.read_csv(f"{RESULTS_DIR}/{fname}", index_col=0, parse_dates=True)["value"]
    r = simulate.monthly_returns(vals)
    r_primary = r[r.index <= PRIMARY_END]
    n_months = len(r_primary)
    sh_recomputed = simulate.sharpe(r_primary, RF_PRIMARY)
    dsr_ownrow = simulate.deflated_sharpe(r_primary, RF_PRIMARY, n_trials_cum)      # n_trials = แถวของตัวเอง
    dsr_flat13 = simulate.deflated_sharpe(r_primary, RF_PRIMARY, 13)                # n_trials = 13 คงที่ (ตาม reviewer)
    psr_n1 = simulate.deflated_sharpe(r_primary, RF_PRIMARY, 1)                     # PSR, N=1, ไม่มี deflation
    rows.append({
        "model_id": mid, "n_months": n_months,
        "sharpe_reported": sh_reported, "sharpe_recomputed": round(sh_recomputed, 4),
        "n_trials_own_row": n_trials_cum,
        "dsr_own_n_trials": round(dsr_ownrow, 4),
        "dsr_flat_n13": round(dsr_flat13, 4),
        "psr_N1": round(psr_n1, 4),
        "reviewer_appendix_flat13": REVIEWER_APPENDIX_FLAT13.get(mid),
    })

df = pd.DataFrame(rows)
df["diff_own_vs_reviewer"] = (df["dsr_own_n_trials"] - df["reviewer_appendix_flat13"]).round(4)
df["diff_flat13_vs_reviewer"] = (df["dsr_flat_n13"] - df["reviewer_appendix_flat13"]).round(4)
pd.set_option("display.width", 200)
pd.set_option("display.max_columns", 20)
print(df.to_string(index=False))
