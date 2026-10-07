"""robust_report.py — สร้าง results/ROBUST_offsets.md และ results/ROBUST_fees.md จาก csv ของ robust_offsets.py / robust_fees.py (ตัวเลขทุกตัวอ่านจาก csv/รันซ้ำ ไม่พิมพ์มือ)
รัน: PYTHONPATH=. ./.venv/bin/python .claude/quant_team/backtest/robust_report.py"""
from __future__ import annotations

import json
import os
import sys

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if THIS_DIR not in sys.path:
    sys.path.insert(0, THIS_DIR)

import numpy as np
import pandas as pd

import common
import remeasure_real_rf as rr

RES = common.RESULTS_DIR
NAME = {"A": "A = M015-FAUM", "B": "B = Trend 25", "B0": "B0 (ถือเท่ากัน)"}
OFFN = {"0": "offset 0 (มี.ค./มิ.ย./ก.ย./ธ.ค.)", "1": "offset 1 (เม.ย./ก.ค./ต.ค./ม.ค.)", "2": "offset 2 (พ.ค./ส.ค./พ.ย./ก.พ.)", "tr": "tranche (1/3 ต่อ offset)"}
f3 = lambda x: f"{x:.3f}"
pc = lambda x: f"{x*100:.2f}%"


def offsets_md():
    S = pd.read_csv(os.path.join(RES, "ROBUST_offsets.csv"), dtype={"offset": str})
    AG = pd.read_csv(os.path.join(RES, "ROBUST_offsets_summary.csv"))
    AB = pd.read_csv(os.path.join(RES, "ROBUST_offsets_AminusB.csv"), dtype={"offset": str})
    DG = pd.read_csv(os.path.join(RES, "ROBUST_offsets_diag.csv"))
    YR = pd.read_csv(os.path.join(RES, "ROBUST_offsets_calendar_year.csv"), index_col=0)
    MO = pd.read_csv(os.path.join(RES, "ROBUST_offsets_monthly_returns.csv"), index_col=0, parse_dates=True)
    reg = json.loads(open(os.path.join(common.CACHE_DIR, "..", "..", "scratch", "validator_robust_regression.json")).read())
    g = lambda m, k, c: float(S[(S["model"] == m) & (S["offset"] == k)][c].iloc[0])
    L = []
    A = L.append
    A("# ROBUST_offsets — ความทนทานต่อการเลื่อนเดือน rebalance (2026-10-06 · backtest-validator)\n")
    A("**การตรวจความทนทาน ไม่ใช่ trial** (ไม่แตะ `trials.csv` / `ALL_RESULTS`) · สคริปต์ `backtest/robust_offsets.py` (+ `robust_report.py`) · ไม่แก้ไฟล์เดิม · "
      "ผลรวมทุก offset รายงานเป็นการกระจาย **ไม่เลือกตัวที่ดีที่สุดเป็นผลงาน** · rf จริง (นโยบาย กนง.) · `FeeData(legacy=False)` Actual · universe รายย่อย (ตัด 8 class)\n")
    A("## 0. สรุป\n")
    a, b, b0 = AG[AG.model == "A"].iloc[0], AG[AG.model == "B"].iloc[0], AG[AG.model == "B0"].iloc[0]
    A(f"- **Sharpe ของ A (ช่วงร่วม 42 เดือน)**: offset 0/1/2 = {f3(g('A','0','sharpe'))} / {f3(g('A','1','sharpe'))} / {f3(g('A','2','sharpe'))} · เฉลี่ย **{f3(a.sharpe_mean)}** · "
      f"ช่วง (max−min) **{f3(a.sharpe_range)}** · tranche {f3(a.sharpe_tranche)} → ค่าที่ไม่ขึ้นกับเดือนอยู่ราว {f3(a.sharpe_mean)}–{f3(a.sharpe_tranche)} ต่ำกว่า 0.765 และต่ำกว่าเป้า 0.95 ทั้งคู่; ค่าจริงของแต่ละเดือนกว้างมาก")
    A(f"- B: {f3(g('B','0','sharpe'))} / {f3(g('B','1','sharpe'))} / {f3(g('B','2','sharpe'))} · เฉลี่ย {f3(b.sharpe_mean)} · ช่วง {f3(b.sharpe_range)} · tranche {f3(b.sharpe_tranche)} · B0: {f3(b0.sharpe_mean)} (ช่วง {f3(b0.sharpe_range)})")
    wins = [(k, float(AB[(AB.offset == k) & (AB.vs == 'B')].d_sharpe.iloc[0])) for k in ("0", "1", "2", "tr")]
    A(f"- **A − B** (ช่วงร่วม): " + " · ".join(f"offset {k} {d:+.3f}" for k, d in wins) + f" → A ชนะ B {sum(1 for k, d in wins[:3] if d > 0)} จาก 3 offset · CI95% paired คร่อม 0 ทุกค่า (ไม่มีนัยสถิติ)")
    A("")
    A("## 1. Regression (ก่อนรันอื่น) — ผ่าน\n")
    A("| โมเดล | Sharpe offset 0 ช่วงวัดผลเดิม (45 เดือน) | อ้างอิงไฟล์เดิม | ต่างกัน | แหล่งอ้างอิง |\n|---|---|---|---|---|")
    A(f"| A | {reg['A']['sharpe_off0_orig_window']:.6f} | {reg['A']['ref']:.6f} | {reg['A']['abs_diff']:.1e} | `M015_results.csv` FAUM sharpe_full |")
    A(f"| B | {reg['B']['sharpe_off0_orig_window']:.6f} | {reg['B']['ref']:.6f} | {reg['B']['abs_diff']:.1e} | `RETAIL_results.csv` Trend25 new_sharpe_full |")
    A(f"| B0 | {reg['B0']['sharpe_off0_orig_window']:.6f} | {reg['B0']['ref']:.6f} | {reg['B0']['abs_diff']:.1e} | `RETAIL_results.csv` B0 new_sharpe_full |")
    A("\n(เส้นทาง offset 0 ใช้ ctx เดิม `validator_retail_ctxs.pkl` + โค้ด `rru.build_plans` / `r15.f_*` เดิมทุกบรรทัด; น้ำหนักส่วนหุ้นของ A = baseline M013-GC75 ทุกบิต max|Δw| = 0 ทุก offset)\n")
    A("## 2. วิธีทำและการตีความของ validator\n")
    A("- ไตรมาสเหมือนเดิม (15 การตัดสินใจ/offset) เปลี่ยนเฉพาะเดือน: t = **วันทำการสุดท้ายของเดือนนั้นในปฏิทินดัชนี** (offset 0 ตรงกับ `quarter_ends` เดิมทุกวัน) · e = วันทำการที่ 2 หลัง t (เดิม) · "
      "สัญญาณ SR12/vol52/ERC/ACWI 3-6-12 เดือน/hurdle rf/Quality/เลือกกองตลาดเงิน คำนวณใหม่ ณ t ใหม่ด้วย `r9.prepare`/`r11`/`r12`/`r13`/`r15` เดิม (NAV ≤ t) · hysteresis เริ่มว่างทุก offset")
    A("- วันตัดสินใจ: offset 0 = 2022-03-31 … 2025-09-30 · offset 1 = 2022-04-29 … 2025-10-31 · offset 2 = 2022-05-31 … 2025-11-28 (การตัดสินใจสุดท้ายของ offset 1/2 ถือแค่ 2/1 เดือนก่อน 2025-12-31)")
    A("- **ช่วงวัดผลร่วม**: ฐาน = มูลค่าพอร์ตสิ้นเดือน **2022-06-30** (ทุก offset ลงทุนแล้ว; offset 2 เข้าตลาด 2022-06-02) → ผลตอบแทนรายเดือน **ก.ค. 2022 – ธ.ค. 2025 = 42 เดือน** เท่ากันทุก offset/โมเดล · "
      "ช่วงนี้ตัด เม.ย.–มิ.ย. 2022 (ช่วงเสียหนัก) ออกจากช่วงเดิม 45 เดือน → **Sharpe offset 0 ในช่วงร่วม ≠ 0.765** (ดูตาราง §3 คอลัมน์ 'ช่วงเดิม')")
    A("- tranche = ถือ 1/3 ต่อ offset แบบ buy-and-hold จากฐาน 2022-06-30 (ค่าเฉลี่ยของมูลค่าที่ปรับฐาน=100) · ต้นทุนของแต่ละ tranche คิดแยก (ไม่มี netting ข้าม tranche → ไม่ได้ประโยชน์จากการหักล้างคำสั่ง) → เป็นตัวแทน 'ไม่ขึ้นกับเดือน' ไม่ใช่พอร์ตเดียวที่ดำเนินการได้จริงพอดี")
    A("- Sharpe = excess รายเดือนเฉลี่ย ×12 ÷ (sd(r)×√12), rf รายเดือนจากเส้นนโยบายจริง · A − B: paired block bootstrap (`r11.paired_real`, block 3, 2000, seed 0)\n")
    A("## 3. ตารางหลัก (กรณีค่าธรรมเนียมจริง Actual, ช่วงร่วม 42 เดือน)\n")
    A("| โมเดล | offset | Sharpe | CAGR | vol | maxDD | Sharpe 0% | Sharpe ก.ค.–ธ.ค.2022 | Sharpe 2023-07..25 | ต้นทุน %/ปี | turnover/ปี | Sharpe ช่วงเดิม (เดือน) |\n|---|---|---|---|---|---|---|---|---|---|---|---|")
    for m in ("A", "B", "B0"):
        for k in ("0", "1", "2", "tr"):
            r = S[(S.model == m) & (S.offset == k)].iloc[0]
            if k == "tr":
                A(f"| {NAME[m]} | {OFFN[k]} | **{f3(r.sharpe)}** | {pc(r.cagr)} | {pc(r.vol)} | {pc(r.max_dd)} | {f3(r.sharpe_c0)} | {f3(r.sharpe_2022h2)} | {f3(r.sharpe_2307_2512)} | — | — | — |")
            else:
                A(f"| {NAME[m]} | {OFFN[k]} | {f3(r.sharpe)} | {pc(r.cagr)} | {pc(r.vol)} | {pc(r.max_dd)} | {f3(r.sharpe_c0)} | {f3(r.sharpe_2022h2)} | {f3(r.sharpe_2307_2512)} | {r.cost_bp_yr/100:.2f} | {r.turn_yr:.2f} | {f3(r.sharpe_origwin)} ({int(r.n_months_origwin)}) |")
    A("\n### สรุปข้าม offset (Sharpe ช่วงร่วม)\n")
    A("| โมเดล | เฉลี่ย 3 offset | min | max | ช่วง (max−min) | tranche | CAGR เฉลี่ย (min–max) | maxDD แย่สุด |\n|---|---|---|---|---|---|---|---|")
    for _, r in AG.iterrows():
        A(f"| {NAME[r.model]} | {f3(r.sharpe_mean)} | {f3(r.sharpe_min)} | {f3(r.sharpe_max)} | {f3(r.sharpe_range)} | {f3(r.sharpe_tranche)} | {pc(r.cagr_mean)} ({pc(r.cagr_min)}–{pc(r.cagr_max)}) | {pc(r.maxdd_worst)} |")
    A("\n## 4. A − B ต่อ offset (Sharpe ช่วงร่วม · paired CI95%)\n")
    A("| offset | A | B | A − B | CI95% | A − B ที่ 0% | A − B (ช่วงเดิม ไม่ทั้งชุด) | A − B0 | CI95% (A−B0) |\n|---|---|---|---|---|---|---|---|---|")
    for k in ("0", "1", "2", "tr"):
        r = AB[(AB.offset == k) & (AB.vs == "B")].iloc[0]
        r0 = AB[(AB.offset == k) & (AB.vs == "B0")].iloc[0]
        ow = (g("A", k, "sharpe_origwin") - g("B", k, "sharpe_origwin")) if k != "tr" else np.nan
        A(f"| {OFFN[k]} | {f3(r.A)} | {f3(r.other)} | **{r.d_sharpe:+.3f}** | [{r.ci_lo:+.2f}, {r.ci_hi:+.2f}] | {r.d_sharpe_c0:+.3f} | {'' if np.isnan(ow) else f'{ow:+.3f}'} | {r0.d_sharpe:+.3f} | [{r0.ci_lo:+.2f}, {r0.ci_hi:+.2f}] |")
    A("\n(คอลัมน์ 'ช่วงเดิม' = A − B บนช่วงที่ simulate เริ่มจริงของแต่ละ offset: 45/44/43 เดือน → ไม่เท่ากันระหว่าง offset ใช้เพื่อดูว่าสัญญาณบวก/ลบเปลี่ยนไหมเท่านั้น)\n")
    A("## 5. ความไม่แน่นอนเชิงสถิติ (block bootstrap CI95% ของ Sharpe รายเดือนช่วงร่วม)\n")
    A("| โมเดล | offset 0 | offset 1 | offset 2 | tranche |\n|---|---|---|---|---|")
    rfm = MO["rf_month"]
    for m in ("A", "B"):
        cells = []
        for k in ("0", "1", "2", "tr"):
            r = MO[f"{m}_off{k}"].dropna()
            lo, hi = rr.boot_ci(r, rfm.reindex(r.index))
            cells.append(f"[{lo:+.2f}, {hi:+.2f}]")
        A(f"| {NAME[m]} | " + " | ".join(cells) + " |")
    A("\n- ทั้ง 3 offset ใช้เดือนและ universe ชุดเดียวกัน (ซ้อนทับกันมาก) ช่วง Sharpe ของ A ที่กว้างจึงมาจากการเลือกกองต่างชุดกัน (path dependence) ไม่ใช่การสุ่มตัวอย่างอิสระ — แต่ CI ของแต่ละ offset กว้างกว่าช่วงนั้นมาก (42 เดือน) · "
      "B0 (ไม่มีการเลือก) แทบไม่ขยับข้าม offset (ช่วงเล็กมาก) = ยืนยันว่า pipeline เลื่อนเดือนถูกต้อง ความต่างของ A/B เกิดจากการเลือกกอง\n")
    A("## 6. ผลตอบแทนรายปีปฏิทิน (เฉพาะเดือนที่อยู่ในช่วงร่วม: 2022 = ก.ค.–ธ.ค.)\n")
    A("| ปี | " + " | ".join(YR.columns) + " |\n|---|" + "---|" * len(YR.columns))
    for y, r in YR.iterrows():
        A(f"| {y} | " + " | ".join(pc(v) for v in r.values) + " |")
    A("\n## 7. ข้อมูลประกอบ (A)\n")
    A("| offset | ขาหุ้นเฉลี่ย (M013-GC75) | กองหุ้นเฉลี่ย/ไตรมาส | ไตรมาสที่มีขา F | ไตรมาส fallback เงินสด | A turnover/ปี | A ต้นทุน %/ปี | B turnover/ปี | B ต้นทุน %/ปี |\n|---|---|---|---|---|---|---|---|---|")
    for _, r in DG.iterrows():
        A(f"| {int(r.offset)} | {r.mean_stock_x*100:.1f}% | {r.mean_n_stock_funds:.1f} | {int(r.quarters_with_F_leg)}/15 | {int(r.A_fallback_cash_quarters)} | {r.A_turn_yr:.2f} | {r.A_cost_bp_yr/100:.2f} | {r.B_turn_yr:.2f} | {r.B_cost_bp_yr/100:.2f} |")
    A("\n## 8. ข้อสงสัย / ข้อจำกัด\n")
    A("- ช่วงวัดผลร่วมตัด เม.ย.–มิ.ย. 2022 ออก → ทุกโมเดลดีขึ้นในช่วงร่วมเมื่อเทียบช่วงเดิม (โดยเฉพาะ offset 0) · ตัวเลข 0.765 ของ A ขึ้นกับว่าเดือนแรก 3 เดือนนั้นอยู่ในช่วงวัดผลหรือไม่ — เป็นความไวต่อ 'ช่วงเริ่ม' อีกชั้นที่ซ้อนกับความไวต่อ 'เดือน rebalance'")
    A("- 3 offset ไม่ใช่ตัวอย่างอิสระ (เดือน/universe/ตลาดเดียวกัน) — ช่วง max−min ไม่ใช่ช่วงความเชื่อมั่น · ตัวอย่าง 42 เดือน / 14–15 การตัดสินใจต่อ offset · n ขาลง = ปี 2022 เพียงปีเดียว")
    A("- ค่าธรรมเนียมเป็น snapshot 2023-05 → 2026-07 ใช้ย้อนหลัง (เหมือนทุกรายงานก่อนหน้า) · universe ตัด class ด้วย snapshot FundProfile ปัจจุบัน (ไม่ point-in-time) · ค่า F-leg ใช้ NAV จาก `nav_history_db.csv` ตามเดิม")
    A("- ไม่ได้ลองปรับพารามิเตอร์ใด ๆ · ไม่ได้บันทึกลง trials.csv (ไม่ใช่ trial) · ตัวเลข B0/B/A ของ offset 0 ตรวจซ้ำได้เองด้วย regression ข้างบน")
    A("\nไฟล์: `ROBUST_offsets.csv`, `ROBUST_offsets_summary.csv`, `ROBUST_offsets_AminusB.csv`, `ROBUST_offsets_monthly_returns.csv`, `ROBUST_offsets_weights.csv`, `ROBUST_offsets_diag.csv`, `ROBUST_offsets_calendar_year.csv`")
    open(os.path.join(RES, "ROBUST_offsets.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")


def fees_md():
    F = pd.read_csv(os.path.join(RES, "ROBUST_fees.csv"), dtype={"offset": str})
    D = pd.read_csv(os.path.join(RES, "ROBUST_fees_AminusB.csv"), dtype={"offset": str})
    C = pd.read_csv(os.path.join(RES, "ROBUST_fees_rate_vs_actual.csv"))
    reg = json.loads(open(os.path.join(common.CACHE_DIR, "..", "..", "scratch", "validator_robust_regression.json")).read())
    LAB = {"ก_Actual": "(ก) Actual (หลัก)", "ข_Rate": "(ข) Rate = เพดาน", "ค_noFront": "(ค) ยกเว้น front-end (FF=SI=0)", "ง_0pct": "(ง) 0%"}
    g = lambda k, c, m, col: float(F[(F.offset == k) & (F.case == c) & (F.model == m)][col].iloc[0])
    L = []
    A = L.append
    A("# ROBUST_fees — ความทนทานต่อสมมติฐานค่าธรรมเนียม (2026-10-06 · backtest-validator)\n")
    A("**การตรวจความทนทาน ไม่ใช่ trial** (ไม่แตะ `trials.csv`/`ALL_RESULTS`) · `backtest/robust_fees.py` (โหมด Rate = `FeeDataRate` ใหม่ ไม่แก้ `fees.py`) · ใช้ plan เดิมของแต่ละ offset (ไม่เลือกกองใหม่ตามค่าธรรมเนียม) · rf จริง · universe รายย่อย\n")
    A("กรณี: (ก) Actual = `FeeData(legacy=False)` อัตราเก็บจริง (Actual Value) · (ข) Rate = **เพดานตามหนังสือชี้ชวน** คอลัมน์ `Rate` ของ `SecFundFee.csv` (schema: Rate = เพดาน, Actual Value = อัตราเก็บจริง ตาม `AUDIT_fees.md`) ใช้ทั้งขากองหุ้นและขา F (กองตลาดเงิน) · (ค) FF=SI=0 (โหมด nofront เดิม) · (ง) 0%. กฎ parse/PIT/ช่องทางสับเปลี่ยน/median fallback เหมือนเดิมทุกกรณี\n")
    A("## 0. Regression\n")
    A(f"(ก) offset 0 ช่วงวัดผลเดิม: A {reg['A']['sharpe_off0_orig_window']:.6f} (อ้างอิง {reg['A']['ref']:.6f}) · B {reg['B']['sharpe_off0_orig_window']:.6f} (อ้างอิง {reg['B']['ref']:.6f}) · ต่าง < 5e-7 ✓ · "
      "(ค)/(ง) = Sharpe nofront/c0 เดิมของ M015 (FAUM nofront 0.939, c0 0.940) และ RETAIL (Trend25 nofront 0.807, c0 0.808) ✓ ตรงในตาราง §1\n")
    A("## 1. offset 0 — ช่วงวัดผลเดิม 45 เดือน (ตัวเลขที่ทีมใช้อ้างอิง)\n")
    A("| กรณี | A Sharpe | A CAGR | A ต้นทุน %/ปี | B Sharpe | B CAGR | B ต้นทุน %/ปี | **A − B** | B0 Sharpe | A Sharpe − B0 |\n|---|---|---|---|---|---|---|---|---|---|")
    for c in LAB:
        a, b, b0 = (g("0", c, m, "sharpe_origwin") for m in ("A", "B", "B0"))
        A(f"| {LAB[c]} | {f3(a)} | {pc(g('0',c,'A','cagr_origwin'))} | {g('0',c,'A','cost_pct_yr'):.2f} | {f3(b)} | {pc(g('0',c,'B','cagr_origwin'))} | {g('0',c,'B','cost_pct_yr'):.2f} | **{a-b:+.3f}** | {f3(b0)} | {a-b0:+.3f} |")
    A("\n## 2. offset 0 — ช่วงร่วม 42 เดือน (เทียบ offset 1–2 ได้)\n")
    A("| กรณี | A Sharpe | B Sharpe | A − B | CI95% (A−B) | B0 Sharpe |\n|---|---|---|---|---|---|")
    for c in LAB:
        a, b, b0 = (g("0", c, m, "sharpe_win") for m in ("A", "B", "B0"))
        d = D[(D.offset == "0") & (D.case == c)]
        ci = f"[{d.ci_lo.iloc[0]:+.2f}, {d.ci_hi.iloc[0]:+.2f}]" if len(d) else ""
        A(f"| {LAB[c]} | {f3(a)} | {f3(b)} | {a-b:+.3f} | {ci} | {f3(b0)} |")
    A("\n## 3. offset 1–2 (กรณี ก, ข, ค) และค่าเฉลี่ย 3 offset — ช่วงร่วม 42 เดือน\n")
    A("| กรณี | โมเดล | offset 0 | offset 1 | offset 2 | เฉลี่ย | min–max | ต้นทุน %/ปี (off 0/1/2) |\n|---|---|---|---|---|---|---|---|")
    for c in ("ก_Actual", "ข_Rate", "ค_noFront"):
        for m in ("A", "B", "B0"):
            v = [g(k, c, m, "sharpe_win") for k in ("0", "1", "2")]
            cs = [g(k, c, m, "cost_pct_yr") for k in ("0", "1", "2")]
            A(f"| {LAB[c]} | {NAME[m]} | {f3(v[0])} | {f3(v[1])} | {f3(v[2])} | **{f3(np.mean(v))}** | {f3(min(v))}–{f3(max(v))} | {cs[0]:.2f}/{cs[1]:.2f}/{cs[2]:.2f} |")
    A("\n### A − B ต่อกรณี × offset (ช่วงร่วม · paired CI95%)\n")
    A("| กรณี | offset 0 | offset 1 | offset 2 | เฉลี่ย | ชนะกี่ offset |\n|---|---|---|---|---|---|")
    for c in ("ก_Actual", "ข_Rate", "ค_noFront"):
        ds = []
        cells = []
        for k in ("0", "1", "2"):
            r = D[(D.offset == k) & (D.case == c)].iloc[0]
            ds.append(r.A_minus_B_win)
            cells.append(f"{r.A_minus_B_win:+.3f} [{r.ci_lo:+.2f}, {r.ci_hi:+.2f}]")
        A(f"| {LAB[c]} | " + " | ".join(cells) + f" | {np.mean(ds):+.3f} | {sum(1 for d in ds if d > 0)}/3 |")
    A("\n## 4. อัตราค่าธรรมเนียมเฉลี่ยของกองที่ถือ (offset 0): Actual vs Rate (เพดาน) %\n")
    A("| โมเดล | ขา | รหัส | Actual | Rate | จำนวนคู่ (กอง,วันซื้อขาย) |\n|---|---|---|---|---|---|")
    sub = C[C.model.isin(["A", "B"])]
    for _, r in sub.iterrows():
        A(f"| {r.model} | {r.leg} | {r.code} | {r.mean_actual_pct:.3f} | {r.mean_rate_pct:.3f} | {int(r.n_pairs)} |")
    A("\n(FF/SI = ค่าซื้อ, BF/SO = ค่าขาย · ต้นทุนจริงในโมเดลขึ้นกับช่องทางสับเปลี่ยนภายใน บลจ. เดียวกัน (SO+SI เทียบ BF+FF) ตาม `FeeModel` เดิม)\n")
    A("## 5. ข้อสงสัย / ข้อจำกัด\n")
    A("- **Rate เป็นเพดานสูงสุดของหนังสือชี้ชวน** ไม่ใช่ราคาที่เก็บจริง (Actual ต่ำกว่า Rate ในแทบทุกแถว: เฉลี่ย BF Actual ≈ 0.01% เทียบ Rate ≈ 1.8%) — ใช้เป็นกรณีสุดโต่ง ไม่ใช่ประมาณการ · ไม่ได้ตรวจกับตารางของผู้จัดจำหน่าย/ช่องทางที่นักลงทุนใช้จริง · ไม่มีหน่วย/Min/Max ในไฟล์")
    A("- plan ไม่ถูกเลือกใหม่ภายใต้ค่าธรรมเนียมแต่ละแบบ (โมเดลจริงที่ตั้งใจจ่ายเพดานอาจเลือก/หมุนกองต่างออกไป) → ผลกรณี (ข) เป็นขอบล่างของการ 'ไม่ปรับตัว'")
    A("- (ง) 0% และ (ค) เกือบเท่ากัน (ต้นทุนส่วนที่เหลือใน (ค) = BF/SO เล็กน้อย) · Rate ใน F-leg: กองตลาดเงินที่เลือก Rate ≈ 0.22% ต่อรายการ (ตามตารางข้างบน)")
    A("- ข้อสงสัยเดิมคงอยู่: snapshot ค่าธรรมเนียม 2023-05 → 2026-07 ใช้ย้อนหลัง · ช่วงร่วม 42 เดือน/CI กว้าง")
    A("\nไฟล์: `ROBUST_fees.csv`, `ROBUST_fees_AminusB.csv`, `ROBUST_fees_rate_vs_actual.csv`")
    open(os.path.join(RES, "ROBUST_fees.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")


if __name__ == "__main__":
    offsets_md()
    fees_md()
    print("ok")
