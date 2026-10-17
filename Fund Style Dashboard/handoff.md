# Handoff — MSCI Fund Style Dashboard · TF Portfolio (quant modeling)

อัปเดตล่าสุด: 2026-10-15 · commit ล่าสุดบน `main` = `44a1c88` (push แล้ว) · ภาษาที่ใช้คุยกับผู้ใช้: **ไทยเสมอ**
path ทั้งหมดในไฟล์นี้สัมพันธ์กับ `Fund Style Dashboard/` (repo root = `Fama French/`)

---

## 1. Goal

- สร้างโมเดลจัดพอร์ตกองทุนไทย (long-only) สำหรับลูกค้า/พี่ที่ปรึกษา แสดงผลใน Streamlit "MSCI Fund Style Dashboard"
  (หน้า 9 = TF Portfolio · หน้า 10 = M019 Frontier · หน้า 11 = M052 Frontier)
- เป้าเดิม: Sharpe ≥ 0.95 แบบ walk-forward หลังค่าธรรมเนียมจริง · ลูกค้ารับความเสี่ยงได้ → return 10–15%/ปี · MaxDD ไม่เกิน −20%
- เป้าใน debate (ผู้ใช้ตั้ง 2026-10-12 → 13): Sharpe > 1.2 & CAGR > 12% → Sharpe > 1.4 → ทนต่อไตรมาส 1 ปี 2025 / ทุก offset ≥ 0.9
- **เป้าที่เหลือจริง:** ล็อกกติกาโมเดลที่ดีที่สุด (M052) แล้วพิสูจน์กับข้อมูลนอกช่วง (NAV ปี 2026) — ห้ามปรับเพิ่มบนข้อมูล 2022–2025

## 2. Rules

**กติกาการทำงาน (จาก `~/.claude/CLAUDE.md` · บังคับทุก session)**
- ตอบเป็นภาษาไทยเสมอ · อ่านไฟล์ที่เกี่ยวข้องให้ครบก่อนตอบ
- **ห้าม execute/เขียนโค้ดทันที** — ถามคำถามแบบเลือกตอบ (AskUserQuestion) เพื่อ clarify ก่อน
- คิดทบทวน ≥ 3 รอบก่อนตอบ · ระหว่างเขียนโค้ด recheck: ตรรกะใหม่ถูกไหม · ระบบเดิมยังทำงานไหม · โครงสร้างยังสมเหตุสมผลไหม
- ผู้ใช้เน้น: ระวัง code architecture · อ่านไฟล์อีกรอบก่อนแก้ · ห้ามแก้สิ่งที่ไม่ได้อธิบายไว้

**กติกาโครงการ / ทีม quant**
- Agents (`.claude/agents/`): read-only ต่อโค้ดแอป, `cache/`, `base_data/` · เขียนได้เฉพาะ `.claude/quant_team/`
  · agent types ของโปรเจกต์ไม่ถูก register เมื่อ cwd = `Fama French/` → ใช้ general-purpose agent แล้วสั่งให้อ่าน `.claude/agents/<role>.md` ก่อน
- ห้าม agent เรียก `nav_loader.load_nav_history` หรือ `data_access.build_*` · ห้ามใช้ `coefs.csv`/`results.csv` ของแอปใน backtest (look-ahead)
- **`trials.csv`: ห้ามลบ/แก้แถว · backup (timestamp) ก่อน append ทุกครั้ง · append แบบ text/binary เท่านั้น** (pandas round-trip เคยเปลี่ยน format แถวเก่า)
- **ทุกการทดสอบบนข้อมูลชุดเดิมต้องนับเป็น trial** (รวม what-if) — DSR ใช้ n ตามจริง · benchmark/diagnostic ที่ไม่ใช่ผู้สมัครไม่ต้องนับ
- ทุก run ต้องมี regression (ปิดสวิตช์ใหม่ = ผลเดิมทุกบิต) · ไม่ผ่าน = หยุด ไม่บันทึก
- ทุก backtest ที่ถือทองต้องใช้ข้อมูลทองที่แก้แล้ว (`run_r5.clean_gold_v2`)
- pytest ใช้ `-p no:cacheprovider` เสมอ
- ดาวน์โหลดไฟล์ต้องขออนุญาตทุกครั้ง (ระบุชื่อไฟล์/แหล่ง/ขนาด) · ห้ามให้คำแนะนำการลงทุนเฉพาะบุคคล
- แก้หน้าแอป/รายงานเมื่อผู้ใช้สั่งเท่านั้น · commit/push เมื่อผู้ใช้สั่ง (ทำบน branch แล้ว fast-forward `main`)

## 3. Current state

**โมเดลที่ดีที่สุด = M052-STACK-AGG** (ค่าธรรมเนียมจริง · rf จริง · เม.ย. 2022 – ธ.ค. 2025 · 45 เดือน · DSR @ n = 102)

| โมเดล | Sharpe | CAGR | MaxDD | ต้นทุน/ปี | offset 0 / 1 / 2 (เฉลี่ย) | DSR |
|---|---|---|---|---|---|---|
| **★ M052** (M019 + FEE0/SIW/BAND5 + CANARY บอนด์ AGG + VSL) ⚠️ post-hoc | **1.532** | 19.8% | −11.3% | 0.92% | 1.92 / 1.01 / 1.50 (1.48) | 0.40 |
| benchmark: หุ้นแบบ M033 57% + ทอง 43% คงที่ (ไม่ใช่ trial) | 1.413 | 16.2% | −12.0% | 0.79% | 1.96 / 1.26 / 1.60 (**1.61**) | — |
| M019 (หุ้น 3 กอง corr ต่ำ + ERC 40% + GC75 + ทอง) ⚠️ | 1.098 | 14.6% | −12.9% | 1.38% | 1.47 / 0.58 / 0.95 (1.00) | 0.15 |
| ① GC75 + กองตลาดเงิน (M015-FAUM) | 0.751 | 8.1% | −7.6% | 1.50% | | 0.06 |
| ② Trend 25 (M004-TF-FX · โมเดลสดของหน้า 9) | 0.719 | 9.1% | −11.2% | 1.85% | | 0.08 |
| ③ M012-QF-S | 0.660 | 8.3% | −10.2% | 1.69% | | 0.06 |
| B0 (ถือทุกกองเท่ากัน) | 0.076 | 2.0% | −21.4% | 0.53% | | 0.01 |

- **ข้อสรุปสำคัญ:** benchmark หุ้น/ทองคงที่ชี้ว่าส่วนที่ M052 ดีกว่า M033 (+0.33) มาจาก **ถือทองมากขึ้น ~+0.21** และ **จับจังหวะ ~+0.12**
  · การจับจังหวะไม่ได้ทนกว่า (ตัดไตรมาส 1 ปี 2025 แล้ว 1.29 vs 1.30 · เฉลี่ย offset 1.48 vs 1.61)
- ระดับที่ "ไม่พึ่งเดือนตัดสินใจ" ของระบบนี้ ≈ Sharpe 1.1–1.3 (M050 SR3M) · ทุกตัวในตาราง post-hoc บนข้อมูลชุดเดียว
- `trials.csv` = **102 trials** (#45 M019 · #49–#59 R1 · #60–#64 R2 · #65–#72 แทนที่ด้วย #73–#80 หลังแก้ทอง · #81–#88 R4–R5 · #89–#96 บอนด์จริง · #97–#102 what-if ตาราง GC)
- **แอป:**
  - หน้า 9: ส่วนที่ 1 = Trend 25 สด + บล็อกพอร์ต M052 และ M019 จากไฟล์อ้างอิง (ไตรมาสล่าสุด ≤ วันที่เลือก · ล่าสุดในไฟล์ 2025-09-30)
    · ส่วนที่ 2 = M052 + M019 + TOP3 + B0 (full / nofront / flat · DSR @ 102)
  - หน้า 10 🗺 M019 Frontier · หน้า 11 🧭 M052 Frontier — 4 ไตรมาสสุ่มคงที่ บนลงล่าง · หุ้น 3 กอง 0–40% ทีละ 1% (231 พอร์ต) ขาทองล็อก ·
    ตาราง `Exp` / `T_*_Q1` / `T_*_Y1` (คาดหวัง vs จริง หลังค่าธรรมเนียม) · หน้า 11 จุด Model = น้ำหนักที่ถือจริง (BAND5)
- **รายงาน:** `reports/M052_portfolio_logic.md` (ส่วนลูกค้า + ภาคผนวกเทคนิค · แก้ตามรีวิว 15 ข้อแล้ว) · `reports/TOP3_portfolio_logic.md` (DSR @ 35 · PDF/DOCX @ 32 — ล้าสมัย)
- pytest 207 ผ่าน · ทุกอย่าง commit + push แล้ว (`44a1c88`) · branch ในเครื่องเหลือ `main` อย่างเดียว
- **รอข้อมูล:** NAV ปี 2026 ยังขาด ม.ค.–ก.ค. (กองสดหายไปเกือบหมด ก.พ.–พ.ค.) → ยังทำ holdout ไม่ได้

## 4. Key decisions & constraints

**นิยาม/กติกาโมเดล (ตกลงกับผู้ใช้แล้ว)**
- Universe = กองหุ้น (Policy E) ที่ FundProfile ติด FIF Flag = Y · **Retail Type = R เท่านั้น** (class สถาบันไม่อยู่) · ไม่ตัด class ขั้นต่ำซื้อ > 100,000 ·
  ไม่ใช่ complex · ไม่มี Tax Type · 1 class ต่อ family · **FIF Flag มีกองหุ้นไทยปน** (เช่น FCSCBSETE) — ผู้ใช้เลือกแก้คำอธิบาย ไม่แก้ตัวกรอง
- ด่าน NAV: ≥ 252 NAVDate ตั้งแต่ 2021 · NAV ≤ 90 วัน (universe) · ≤ 10 วัน (investable) · ≥ 40 weekly obs · zero-return ≤ 20% · vol ≥ 2%
- คุณภาพ: AUM_fam ≥ 100 ล้าน · อายุ family ≥ 730 วัน
- Rebalance สิ้นไตรมาสปฏิทิน · execution NAV วันทำการที่ 2 · ไม่แบ่ง tranche (ผู้ใช้ปฏิเสธ + TR3 แพ้ใน R1)
- rf = ดอกเบี้ยนโยบาย ธปท. จริงรายวัน · Sharpe = mean(r − rf)×12 / (std×√12) · CI block bootstrap 3 เดือน · DSR ด้วย n จริง
- ค่าธรรมเนียม: FEEUH Actual Value (`FeeData(legacy=False)`) · E/F/O แยก (`run_m018.Fee3`) · สับเปลี่ยนใน บลจ. เดียวกันถ้าถูกกว่า
- **ขาทอง:** กองทองที่ AUM ใหญ่สุด (ผู้ใช้เลือกคงกติกา AUM · รับรู้แล้วว่าปี 2022 สลับกองเฮดจ์/ไม่เฮดจ์โดยบังเอิญ) · ไม่มี → กองตลาดเงิน
- **CANARY ใช้บอนด์จริง AGG** (ETF adjusted close · `base_data/US_BOND_ETF.csv` ดาวน์โหลดด้วยความยินยอม) แทนบอนด์จำลองจาก US10Y
- **ข้อมูลทอง:** NAV K-GOLD-C(A) ผิดตั้งแต่ 2024-04-23 → ต่อราคาด้วย K-GOLD-A(A) (ผู้ใช้อนุมัติ) · ข้อมูลสัญญาณหยุดที่ 2024-05-16 · ราคา sim ต่อถึงสิ้นข้อมูล
- Top 5 (ผู้ใช้สั่งเก็บ · เวอร์ชันบอนด์จริง): M052 · M054 · M051 · M053 · M033 — `debate/TOP5.md`
- หน้า 10/11 ใช้ชื่อภายใน `gc75_frontier` / `GC75_FRONTIER_*` ต่อ (ผู้ใช้ตกลง) · เพดาน ERC ของโมเดล (`GC75_FRONTIER_MODEL_CAP`) แยกจากเพดานกริด

**ข้อจำกัดข้อมูล**
- FundProfile เป็น snapshot ปัจจุบัน (ประเภท/สถานะ/ระดับความเสี่ยง ไม่ point-in-time) · ค่าธรรมเนียมก่อน 2023-05 ใช้ snapshot แรก ·
  NAV class ปันผลไม่รวมปันผล · NAV 2026 มีรูใหญ่ · MSCI ถึง 2026-07

## 5. Active files

**แอป**
- `pages/9_📈_TF_Portfolio.py` (Trend 25 สด + `model_block` M052/M019 + TOP3) · `pages/10_🗺_M019_Frontier.py` · `pages/11_🧭_M052_Frontier.py`
- `page_frontier.py` — ส่วนแสดงผลร่วมหน้า 10/11 (กราฟ → ตาราง Exp/T_* → กองที่ถือ)
- `analysis/gc75_frontier.py` — μ/Σ (block shrink · ขาตั้งรับ pairwise) · กริด · `frontier_case(..., model_weights=)` · `model_erc`
- `data_access.py` — `load_tf_top3` · `load_gc75_frontier` · `load_m052_frontier` (+ `get_*` แบบ versioned cache)
- `config.py` — `TF_TOP3_SERIES` (M052, M019, …) · `TF_TOP3_N_TRIALS = 102` · `GC75_FRONTIER_*` · `M052_FRONTIER_*`
- `viz.py` — `frontier_chart(extra_points, axis_titles)` · `weights_compare_bar` · สี/label series
- `base_data/reference/` — `tf_top3_{curves,metrics}.csv` · `gc75_frontier_{holdings,weekly,realized}.csv` · `m052_frontier_{holdings,weekly,realized}.csv`
- `base_data/US_BOND_ETF.csv` (AGG/IEF) · `base_data/US_10y_Bond_Yield.csv` (ผู้ใช้เพิ่ม · เป็น yield ไม่ใช่ราคา · ไม่ได้ใช้ในโมเดล)
- tests: `test_gc75_frontier.py` · `test_m052_frontier.py` · `test_tf_top3_reference.py` · `test_page9_ui.py` · `test_tf_replay.py` …

**Quant team (`.claude/quant_team/`)**
- `backtest/run_r6.py` — ตัวหลักปัจจุบัน (`Cfg(vsl, canary, ens, bond, table, …)` · ใช้ clean_gold_v2) · stage: (ว่าง) = M051–M058 ·
  `export52` · `gcdry` · `bench` · `d0`
- `backtest/run_r1.py`–`run_r5.py` (debate) · `run_m018.py`–`run_m022.py` · `frontier_export.py` (holdings/realized ร่วม) ·
  `export_gc75_frontier.py` (หน้า 10) · `export_top3.py` (หน้า 9 · อ่าน n จาก ledger · รวม `EXPORT_m052_*`)
- `debate/` — `DEBATE_BRIEF.md` · `R{1..5}_{researcher,modeler,results}.md` · `DEBATE_SUMMARY.md` · `TOP5.md`
- `specs/` — M018–M022 · `M051_canary_real_bond.md` (+ ผล) · `results/` — `R{1..6}_*` · `BENCH_fixed_mix.csv` · `DRY_gc_tables.csv` · `EXPORT_*`
- `trials.csv` (+ `trials.backup_*.csv`)

**เอกสาร:** `reports/M052_portfolio_logic.md` · `docs/pages/{9-tf-portfolio,10-gc75-frontier,11-m052-frontier}.md` · `README.md` · `docs/README.md`

**ลำดับรัน export (เมื่อข้อมูล/trials เปลี่ยน):**
```bash
PYTHONPATH=. ./.venv/bin/python .claude/quant_team/backtest/run_r6.py export52      # หน้า 11 + EXPORT_m052_*
PYTHONPATH=. ./.venv/bin/python .claude/quant_team/backtest/export_top3.py          # หน้า 9 ส่วนที่ 2 (ต้องหลัง export52)
PYTHONPATH=. ./.venv/bin/python .claude/quant_team/backtest/export_gc75_frontier.py # หน้า 10 + บล็อก M019 หน้า 9
./.venv/bin/python -m pytest -p no:cacheprovider -q
```
→ ถ้า trials เพิ่ม: แก้ `TF_TOP3_N_TRIALS` + ค่า DSR ใน `tests/test_tf_top3_reference.py` · หลังแก้โมดูลต้องรีสตาร์ต Streamlit

## 6. Changes made (2026-10-07 → 15)

- หน้า 9: แก้ cache เก่า (sha1 แทน mtime) · DSR @ 35 → 88 → 96 → 102 · เพิ่ม M019 และ M052 (ส่วนที่ 1 และ 2)
- หน้า 10: GC75+MMF → **M019** · กริด 5% → 1% · layout บนลงล่าง · ตาราง Exp vs จริง · ตรวจตัวเลขอิสระ (≤ 2e-15)
- หน้า 11 ใหม่ (M052) · refactor `page_frontier.py` + `frontier_export.py` (ผลหน้า 10 เท่าเดิม ≤ 1.3e-15)
- Trials M018–M022 · debate researcher vs modeler 5 รอบ (R1–R5) · CANARY บอนด์จริง (R6) · what-if ตาราง GC · benchmark หุ้น/ทองคงที่
- แก้ข้อมูลทอง K-GOLD-C(A) 2 ขั้น (plateau → splice) · ตัวเลข offset 1/2 ของรอบ 3–4 ที่รายงานไปก่อนต่ำเกินจริง (แก้แล้ว)
- รายงาน M052 (+ แก้ตามรีวิว: เงื่อนไขคัดกองครบ 6 ด่าน · benchmark · ทองซ้อน DAOL-GOLD · เฮดจ์ทอง · ความหมาย DSR)
- code review หน้า 9/10 → แก้ 7 จาก 8 ข้อ (เหลือชื่อ gc75 ตามตกลง)

## 7. Failed attempts

| แบบ | ไอเดีย | ผล | สรุป |
|---|---|---|---|
| M007 / M008 / M009 / M010 / M014 / M016 / M017 | rebalance ช้า · style/macro · หักค่าธรรมเนียมใน SR12 · dedupe · gate · ถ่วงคะแนน · index-first | 0.15–0.63 | แย่กว่าฐาน (ดูตารางเดิมใน git history) |
| M021 / M022 | M019 แบบ 5 กอง | 0.77 / 0.97 | เพิ่มจำนวนกองไม่ช่วย |
| TR3 (R1) | แบ่งเงิน 3 ก้อนคนละเดือน | 0.24–0.82 | แพ้ทุกแบบบน 45 เดือน |
| MH (R1) | คะแนน 3/6/12 เดือน | 0.43 | turnover สูง ต้นทุน 263 bp |
| DEFX (R1) | ขาตั้งรับเลือกตามโมเมนตัม | 0.99 | ปี 2022 เลือกผิด |
| NH52 / RESID / FIP (R3) | สัญญาณคัดกองจากงานวิจัย | 0.89–1.01 | แย่กว่า SR12′ 0.2–0.3 |
| CAP75 / RB2 (R3) | ถือทองถาวรมากขึ้น | 1.15–1.16 | Sharpe ลด |
| SMOOTH3 / VOTE (R4) | เฉลี่ย canary 3 เดือน / โหวต | 1.35 / 1.42 | ไม่ผ่านเป้าความทนทาน |
| ALLCLEAR / SR3M (R5) | เพิ่มหุ้นกลางไตรมาส / อันดับเฉลี่ย 3 เดือน | 1.59 / 1.11 | ขาด offset 1 / offset 0 ตก |
| ENS กับบอนด์จริง (R6) | CANARY 4 นิยาม | 1.47–1.51 | ส่วนเพิ่มพึ่งบอนด์จำลอง → ไม่ใช้ |
| what-if ตาราง GC (#97–#102) | 100/90/80/70 · 100/85/70/65 · 100/80/60/40 | M052 1.55–1.57 · M019 0.93–1.05 | ต่างระดับ noise · ไม่เปลี่ยนกติกา |
| ไฟล์ US_10y_Bond_Yield.csv | ใช้แทนบอนด์จริง | — | เป็น yield (≈ FRED) ไม่ใช่ราคา → ดาวน์โหลด ETF แทน |

## 8. Specific next steps

1. **ล็อกกติกา M052** (เขียน forward-test lock document ถ้าผู้ใช้สั่ง) แล้ว **holdout กับ NAV 2026** เมื่อข้อมูลครบ — ห้ามปรับก่อน
2. ตัดสินใจกับผู้ใช้: นำเสนอ M052 คู่กับ benchmark หุ้น/ทองคงที่ (ทนกว่า · ต้นทุนต่ำกว่า) — ทางเลือกที่ง่ายกว่าอาจเหมาะกว่าสำหรับลูกค้า
3. (ถ้าสั่ง) ทำ `reports/M052_portfolio_logic.md` เป็น PDF/DOCX · อัปเดต `reports/TOP3_portfolio_logic.{md,pdf,docx}` ให้ DSR @ 102
4. (ทางเลือก · ต้องเป็น trial ใหม่) ตัดกองหุ้นไทยที่ติด FIF Flag ออกจาก universe · เพิ่ม correlation กับขาทองในการคัดกองหุ้น (กันทองซ้อน เช่น DAOL-GOLD)
5. (ทางเลือก) ย้ายตรรกะ M052 เข้าแอปเป็นพอร์ตสด (ตอนนี้หน้า 9 แสดงจากไฟล์ export ถึง 2025-09-30) — งานใหญ่: NAV ทอง · ดอกเบี้ย · คุณภาพ · ρ_adj · ETF บอนด์

## 9. Lessons learned

- **ต้องมี benchmark แบบ "ส่วนผสมคงที่" ทุกครั้งที่โมเดลจับจังหวะ** — ไม่งั้นแยกไม่ออกว่าได้จากจังหวะหรือจากถือสินทรัพย์ที่ขึ้น (M052: ส่วนใหญ่มาจากทอง)
- **ผลไวต่อเดือนตัดสินใจมาก** — รายงาน offset 0/1/2 เสมอ · Sharpe 1.5+ ส่วนหนึ่งคือโชคปฏิทินการคัดกอง (SR3M ชี้ระดับจริง ~1.1–1.3)
- **ไตรมาสเดียวพลิกผลได้** — ทดสอบ "ตัดไตรมาสที่ดีที่สุด" ทุกครั้ง (CANARY: +10 จุดจากไตรมาส 1 ปี 2025)
- **ตรวจข้อมูลก่อนเชื่อตัวเลข** — NAV ผิดของ class เล็กที่กำลังปิด (K-GOLD-C(A)) ทำให้ vol 188% และ offset 1/2 ผิด · แก้ครั้งแรกไม่ครบ
- **ทดสอบสัญญาณจำลองกับข้อมูลจริง** — ENS ดูดีกับบอนด์จำลอง แต่หายไปกับ AGG/IEF
- **ต้นทุน = ค่าธรรมเนียมขาเข้าตอนเปลี่ยนกองหุ้น** (≈ 100–180 bp/ปี) ไม่ใช่จำนวนครั้งที่ซื้อขาย · ขาเข้าทอง/ตลาดเงินแทบฟรี
- **flag ในข้อมูลกองทุนไม่ตรงความหมายเสมอ** — FIF Flag = Y มีกองหุ้นไทย · ระดับ hedge ต้องดูจากพฤติกรรม NAV ไม่ใช่ชื่อ/flag
- **การคัดกองด้วย correlation เฉพาะกองหุ้น** ไม่เห็นความเสี่ยงซ้อนกับขาทอง (DAOL-GOLD) และไม่กันธีมซ้ำ (อินเดีย 2 ใน 3)
- **ทุกการลองบนข้อมูลชุดเดิมคือ trial** — what-if ก็ต้องนับ · DSR ปัจจุบัน 0.40 (ต่ำกว่าเกณฑ์ 0.95 มาก)
- regression แบบ "ปิดสวิตช์ = เดิมทุกบิต" + ต่อผลจริงรายไตรมาส = มูลค่า simulate จับบั๊กได้จริงหลายครั้ง (ใช้ต่อ)
- อย่าเดาจากชื่อกอง · ระวัง sed กับภาษาไทยบน macOS (ใช้ python replace) · Streamlit ต้องรีสตาร์ตเมื่อแก้โมดูลที่ import
