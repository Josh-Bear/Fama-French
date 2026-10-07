"""validator_append_trials.py -- append แถวใหม่ (status=dsr-recalc-unitfix) ต่อท้าย trials.csv เท่านั้น
ไม่แก้/ลบแถวเดิม (เพิ่งสำรอง trials.backup_<ts>.csv ไว้ก่อนรันไฟล์นี้แล้ว). ไม่ rerun backtest ใดๆ."""
import csv
import datetime as dt

TRIALS_CSV = ".claude/quant_team/trials.csv"

SPEC_FILE = {
    "M001-MS": "M001_baseline_page8.md", "M001-EW": "M001_baseline_page8.md",
}
for _m in ["M002-SR", "M002-MOM", "M002-NOH", "M003-ERC", "M003-HRP", "M004-VT", "M004-TF",
           "M005", "M005-N5", "M005-N10", "M005-NODD"]:
    SPEC_FILE[_m] = "M002-M005_plan.md"

PARAMS = {
    "M001-MS": "rf=2%;cost=0.5%/side;hist>=252;B0=1classpergroup;primary=2022-03..2025-09(15q);bugfix=cash-on-exec-fail",
    "M001-EW": "rf=2%;cost=0.5%/side;hist>=252;B0=1classpergroup;primary=2022-03..2025-09(15q);bugfix=cash-on-exec-fail",
    "M002-SR": "sel=A(signal=SR12;N=8;K=16;dedupe=False);weight=EW;overlay=None;rf=2%;cost=0.5%/side;primary=2022-03..2025-09(15q)",
    "M002-MOM": "sel=B(signal=R12_1;N=8;K=16;dedupe=False);weight=EW;overlay=None;rf=2%;cost=0.5%/side;primary=2022-03..2025-09(15q)",
    "M002-NOH": "sel=C(signal=SR12;N=8;K=8;dedupe=False);weight=EW;overlay=None;rf=2%;cost=0.5%/side;primary=2022-03..2025-09(15q)",
    "M003-ERC": "sel=A(signal=SR12;N=8;K=16;dedupe=False);weight=ERC;overlay=None;rf=2%;cost=0.5%/side;primary=2022-03..2025-09(15q)",
    "M003-HRP": "sel=A(signal=SR12;N=8;K=16;dedupe=False);weight=HRP;overlay=None;rf=2%;cost=0.5%/side;primary=2022-03..2025-09(15q)",
    "M004-VT": "sel=A(signal=SR12;N=8;K=16;dedupe=False);weight=ERC;overlay=VT;rf=2%;cost=0.5%/side;primary=2022-03..2025-09(15q)",
    "M004-TF": "sel=A(signal=SR12;N=8;K=16;dedupe=False);weight=ERC;overlay=TF;rf=2%;cost=0.5%/side;primary=2022-03..2025-09(15q)",
    "M005": "sel=D(signal=SR12;N=8;K=16;dedupe=True);weight=ERC;overlay=MAX;rf=2%;cost=0.5%/side;primary=2022-03..2025-09(15q)",
    "M005-N5": "sel=E(signal=SR12;N=5;K=10;dedupe=True);weight=ERC;overlay=MAX;rf=2%;cost=0.5%/side;primary=2022-03..2025-09(15q)",
    "M005-N10": "sel=F(signal=SR12;N=10;K=20;dedupe=True);weight=ERC;overlay=MAX;rf=2%;cost=0.5%/side;primary=2022-03..2025-09(15q)",
    "M005-NODD": "sel=A(signal=SR12;N=8;K=16;dedupe=False);weight=ERC;overlay=MAX;rf=2%;cost=0.5%/side;primary=2022-03..2025-09(15q)",
}

# (sharpe_reported, n_trials_cumulative_unchanged, dsr_input_n_trials_used, dsr_new, psr_n1)
ROWS = [
    ("M001-MS",   0.2506, 1,  1,  0.6814, 0.6814),
    ("M001-EW",   0.1344, 2,  2,  0.3979, 0.6001),
    ("M002-SR",   0.6357, 3,  13, 0.3163, 0.8844),
    ("M002-MOM",  0.2192, 4,  13, 0.1025, 0.6607),
    ("M002-NOH",  0.4447, 5,  13, 0.1996, 0.8003),
    ("M003-ERC",  0.6492, 6,  13, 0.3261, 0.8866),
    ("M003-HRP",  0.6026, 7,  13, 0.2847, 0.8606),
    ("M004-VT",   0.5001, 8,  13, 0.2375, 0.8206),
    ("M004-TF",   0.7378, 9,  13, 0.3593, 0.9093),
    ("M005",      0.4547, 10, 13, 0.1677, 0.7642),
    ("M005-N5",   0.8448, 11, 13, 0.4469, 0.9374),
    ("M005-N10",  0.5143, 12, 13, 0.2018, 0.8011),
    ("M005-NODD", 0.6415, 13, 13, 0.3206, 0.8859),
]

run_at = dt.datetime.now().isoformat()
new_rows = []
for model_id, sharpe, n_trials_col, n_trials_used, dsr_new, psr_n1 in ROWS:
    if n_trials_used == n_trials_col:
        n_trials_note = f"n_trials ใช้ในสูตร = {n_trials_used} (เท่ากับ n_trials_cumulative คอลัมน์นี้)"
    else:
        n_trials_note = (f"n_trials ใช้ในสูตร DSR = {n_trials_used} (คือ n_trials_cumulative รวมสุดท้ายของทั้ง"
                          f"โปรเจกต์ ณ ตอนรีวิว ไม่ใช่ {n_trials_col} ของแถวนี้เอง) -- ตั้งใจให้ตรงกับวิธีของ"
                          f"model-reviewer ใน M002-M005_review.md ภาคผนวก (ระบุชัดว่าใช้ n_trials=13 คงที่ทุกแถว) "
                          f"เพื่อให้เทียบตัวเลขกันได้ตรงๆ; ค่า n_trials_cumulative คอลัมน์นี้ไม่เปลี่ยนตามกฎ BRIEF")
    notes = (f"DSR unit-fix 2026-09-30 (backtest-validator แก้บั๊กที่ model-reviewer พบ "
             f"reviews/M002-M005_review.md ข้อ 1: simulate.deflated_sharpe เดิมใส่ sr annualized "
             f"(sharpe() คูณ sqrt12) เข้าสูตร SE/SR0 ที่คิดมาสำหรับ sr รายเดือน -> z เฟ้อ ~sqrt12) | "
             f"แก้: เพิ่ม sr_m = per-period(รายเดือน) excess mean / sd โดยตรงในฟังก์ชัน ใช้ sr_m ทั้ง SE และ "
             f"เทียบ SR0 (n_eff Lo2002 และ skew/kurtosis logic เดิมไม่เปลี่ยน) | {n_trials_note} | "
             f"PSR(N=1; ไม่มี deflation) = {psr_n1} | return series ใช้ backtest/results equity_curve.csv เดิม "
             f"(cost 0.5%/side; rf 2%; primary <=2025-12-31; monthly_returns) ไม่ได้ rerun backtest | "
             f"เทียบ reviewer appendix (n_trials=13 ทุกแถว) ตรงกันในทศนิยมหลักที่ 3-4 สำหรับ 11 trials ของ M002-M005 | "
             f"self-check สูตร: scratch/validator_dsr_check.py (PSR analytic + monotonic ใน n_trials ผ่านทั้งคู่)")
    new_rows.append({
        "model_id": model_id, "run_at": run_at, "spec_file": SPEC_FILE[model_id],
        "params": PARAMS[model_id], "period_start": "2022-03-31", "period_end": "2025-12-31",
        "rf_source": "assumed constant 2%/yr", "cost_assumption": "0.5%/side constant",
        "sharpe": sharpe, "cagr": "", "vol": "", "max_dd": "", "turnover": "",
        "n_trials_cumulative": n_trials_col, "deflated_sharpe": dsr_new,
        "status": "dsr-recalc-unitfix", "notes": notes,
    })

with open(TRIALS_CSV, "r", newline="", encoding="utf-8") as f:
    reader = csv.reader(f)
    header = next(reader)
    existing = list(reader)

fieldnames = header
with open(TRIALS_CSV, "a", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    for row in new_rows:
        writer.writerow(row)

print(f"appended {len(new_rows)} rows to {TRIALS_CSV}; total rows now = {len(existing) + len(new_rows)} (+header)")
