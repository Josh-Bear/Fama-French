# Handoff — MSCI Fund Style Dashboard · TF Portfolio (quant modeling)

อัปเดตล่าสุด: 2026-10-14 (บ่าย) · ภาษาที่ใช้คุยกับผู้ใช้: **ไทยเสมอ** (ดู `~/.claude/CLAUDE.md`)

---

## 1. Goal

- สร้างโมเดลจัดพอร์ตกองทุน (ไทย, long-only) สำหรับลูกค้า/พี่ที่ปรึกษา ผ่าน Streamlit "MSCI Fund Style Dashboard" (หน้า 9 = TF Portfolio)
- เป้าหลัก: **Sharpe ≥ 0.95 แบบ out-of-sample walk-forward** หลังหักค่าธรรมเนียมจริง
- โจทย์รอง (ล่าสุด): ลูกค้ารับความเสี่ยงได้มาก → อยากได้ **return 10–15%/ปี โดย Max DD ไม่เกิน −20%**
- ห้ามบิดนิยาม Sharpe / ช่วงวัดผล / universe เพื่อให้ถึงเป้า และห้ามใช้โมเดลที่เลือกหลังเห็นผล (post-hoc)

## 2. Current state

**TOP3 ที่ใช้จริง** (universe = ทุก class ซื้อได้ · rf จริง ธปท. · ค่าธรรมเนียมจริง FEEUH Actual Value · เม.ย. 2022–ธ.ค. 2025 · 45 เดือน)

| โมเดล | Sharpe | Return/ปี | MaxDD | ต้นทุน/ปี | DSR@102 |
|---|---|---|---|---|---|
| ★ M052 (M019 + ลดค่าธรรมเนียม + CANARY บอนด์ AGG + VSL) ⚠️ post-hoc | 1.532 | 19.77% | −11.35% | 0.92% | 0.41 |
| M019 (หุ้น 3 กอง LC + ERC 40% + GC75 + ขาทอง) ⚠️ post-hoc | 1.098 | 14.59% | −12.91% | 1.38% | 0.15 |
| ① GC75 + กองตลาดเงิน (M015-FAUM) ⚠️ | 0.751 | 8.07% | −7.59% | 1.50% | 0.07 |
| ② Trend 25 (M004-TF-FX) | 0.719 | 9.09% | −11.16% | 1.85% | 0.09 |
| ③ M012-QF-S (Trend 25 + rf จริง + เกณฑ์คุณภาพ) | 0.660 | 8.33% | −10.22% | 1.69% | 0.07 |
| B0 (benchmark) | 0.076 | 1.96% | −21.4% | — | — |

- ยกเว้น front-end fee: 0.94 / 0.91 / 0.84 · flat 0.5%/ข้าง: 0.68 / 0.73 / 0.67
- offset sensitivity: ① 0.35–0.98 · ② 0.41–1.00 · CI ของ Sharpe ทุกตัวคร่อม 0
- **ยังไม่มีโมเดลใดถึง 0.95 หรือ return ≥ 10% หลังหักค่าธรรมเนียม (แบบไม่ post-hoc)**
- `trials.csv` = **102 trials** (#89–#96 = CANARY บอนด์จริง AGG/IEF · #97–#102 = what-if ตาราง GC บน M052/M019) (#36–#48 M018–M022 · #49–#88 debate researcher vs modeler 5 รอบ · #65–#72 ถูกแทนด้วย #73–#80 หลังแก้ข้อมูลทอง)
- **debate 5 รอบ (2026-10-12/13)**: สรุป `.claude/quant_team/debate/DEBATE_SUMMARY.md` · ตัวที่เก็บไว้ `debate/TOP5.md`
  (M046 1.587 · M042 1.547 · M041 1.532 · M036 1.495 · M033 1.204 — ทั้งหมด post-hoc · ระดับที่ทนต่อเดือน rebalance ≈ 1.1–1.3)
- **หน้า 9**: ส่วนที่ 1 = Trend 25 สด + **พอร์ต M052 และ M019 จากไฟล์อ้างอิง** (ไตรมาสล่าสุด ≤ วันที่เลือก · ล่าสุดในไฟล์ 2025-09-30) · ส่วนที่ 2 = M052 + M019 + TOP3 + B0 (DSR@102)
- **ตัวดีสุดตอนนี้ = M052** (M041 + CANARY ใช้บอนด์จริง AGG · Sharpe 1.532 · offset 1.92/1.01/1.50) — ทดสอบบอนด์จริงแล้ว ENS พึ่งบอนด์จำลอง (`specs/M051_canary_real_bond.md`) · TOP5 อัปเดตเป็นเวอร์ชันบอนด์จริง · trials = 102
- **benchmark หุ้น 57% + ทอง 43% คงที่** (หุ้นแบบ M033) ได้ Sharpe 1.41 · เฉลี่ย offset 1.61 (ทนกว่า M052) → ผลส่วนใหญ่ของ M052 มาจากถือทองมาก การจับจังหวะเพิ่ม ~+0.12 (`run_r6.py bench` · `reports/M052_portfolio_logic.md` §4.7)
- **หน้า 11 = 🧭 M052 Frontier** (ส่วนแสดงผลร่วมกับหน้า 10 ใน `page_frontier.py`) · หน้า 9 มี M052 ทั้งส่วนที่ 1 และ 2
- **หน้า 10 = 🗺 M019 Frontier** (เดิม GC75+MMF): หุ้น 3 กอง 0–40% ทีละ 1% (231 พอร์ต) ขาทองล็อก · 4 ไตรมาสสุ่มคงที่ · ตัวเลขตรวจอิสระแล้ว (≤ 2e-15)
- pytest ผ่านทั้งชุด
- รายงาน `reports/TOP3_portfolio_logic.{md,pdf,docx}` อัปเดตตรงกับหน้า 9 แล้ว (ส่งผู้ใช้แล้ว)
- **รอข้อมูล**: ผู้ใช้กำลังขอ NAV ปี 2026 (ม.ค.–ส.ค. รวมต้น ก.ค.) มาทำ holdout — ตอนนี้ NAV 2026 มีรูใหญ่ (กองสด 395 → 66 ใน มี.ค. 2026) จึงยังทำ holdout ไม่ได้

## 3. Key decisions & constraints

**กติกาโมเดล (ตกลงกับผู้ใช้แล้ว)**
- Universe = **ทุก class ที่ขายรายย่อย (Project Retail Type = R) โดยไม่ตัด class ขั้นต่ำซื้อสูง** (`fst_lowbuy_val` > 100,000 ยังอยู่) · class สถาบันที่ไม่ใช่ R ไม่อยู่ใน universe · 1 class ต่อ family · FIF Flag = Y มีกองหุ้นไทยปน (เช่น FCSCBSETE)
- **Rebalance รายไตรมาสตามปฏิทิน** (วันทำการสุดท้าย มี.ค./มิ.ย./ก.ย./ธ.ค.) · execution = NAV วันทำการที่ 2 หลัง t (`TF_EXEC_LAG=2`)
- **ไม่แบ่งลงเงิน 3 รอบ (tranche)** — ผู้ใช้ปฏิเสธ (คำนวณ/รายงานยาก)
- rf = ดอกเบี้ยนโยบาย ธปท. จริง (`base_data/TH_POLICY_RATE.csv`, daily step, มีผลวันถัดจากประกาศ)
- Sharpe = mean(r − rf_month)×12 / (std×√12) · block bootstrap 3 เดือน · DSR ด้วย n_trials ตามจริง
- ค่าธรรมเนียม: FEEUH **Actual Value** (ไม่ใช่ Rate = เพดาน prospectus) · "ไม่มี/ยกเว้น/ไม่เรียกเก็บ" = 0 · แถวซ้ำเลือกค่าสูงกว่า
- **ไม่เอาโมเดล post-hoc** (เช่น M006-TCQ 0.92, M005-N5 10.4%) ใน TOP3 · ไม่แสดง M001 ในหน้า 9
- ทุกไอเดียใหม่ = **trial ใหม่ ต้องล็อก spec ก่อนรัน** · ห้าม tune หลังเห็นผล

**กติกาการทำงาน**
- ทำตาม `~/.claude/CLAUDE.md`: ตอบไทย · อ่านไฟล์ครบ · **ถาม AskUserQuestion ก่อน execute** · rethink ×3 · recheck โค้ด/ระบบเดิม/โครงสร้าง
- Agents (`.claude/agents/`): read-only ต่อโค้ดแอป, `cache/`, `base_data/` · เขียนได้เฉพาะ `.claude/quant_team/`
- ห้าม agent เรียก `nav_loader.load_nav_history` หรือ `data_access.build_*`
- ห้ามใช้ `coefs.csv`/`results.csv` ของแอปใน backtest (fit ทั้งช่วง = look-ahead) → ใช้ `backtest/exposure.py` (expanding ≤ t)
- `trials.csv`: ห้ามลบ/แก้แถว · backup (timestamp) ก่อน append ทุกครั้ง
- pytest ใช้ `-p no:cacheprovider` เสมอ
- **ไม่แก้หน้า 9 / รายงาน จนกว่าผู้ใช้สั่ง**
- ดาวน์โหลดไฟล์ต้องขออนุญาตทุกครั้ง · ห้ามให้คำแนะนำการลงทุนเฉพาะบุคคล
- Agent types ในโปรเจกต์ (`quant-modeler`, `quant-researcher`, `backtest-validator`, …) ไม่ถูก register ใน session ที่ cwd = `Fama French/` → ใช้ general-purpose agent แล้วสั่งให้อ่าน `.claude/agents/<role>.md` ก่อน

## 4. Active files

(path สัมพันธ์กับ `Fund Style Dashboard/`)

**แอป**
- `pages/9_📈_TF_Portfolio.py` — หน้า 9 (section 2 = TOP3)
- `data_access.py` — `load_tf_top3()` / `get_tf_top3`
- `config.py` — `TF_TOP3_CURVES_CSV`, `TF_TOP3_METRICS_CSV`, `TF_TOP3_SERIES` (+M052, M019), `TF_TOP3_N_TRIALS=102` · `M052_FRONTIER_*` (หน้า 11) · `GC75_FRONTIER_*` (หน้า 10 · `GC75_FRONTIER_MODEL_CAP` = เพดาน ERC ของ M019 แยกจากเพดานกริด)
- `pages/10_🗺_M019_Frontier.py` · `analysis/gc75_frontier.py` · `base_data/reference/gc75_frontier_{holdings,weekly}.csv` (พอร์ต M019 ทุกไตรมาส · ใช้ทั้งหน้า 9 และ 10) — ชื่อ gc75 คงไว้ (M019 ใช้ GC75)
- `viz.py` — สี/label TOP3, `TF_SERIES_BOLD`
- `page_common.py` — `TABLE_WIDTH` / `CHART_WIDTH` (compat Streamlit ทุกเวอร์ชัน)
- `analysis/fund_fees.py` — `FeeData`, `FeeModel`, `parse_fee_value`
- `base_data/reference/tf_top3_curves.csv`, `tf_top3_metrics.csv` — ผล TOP3 แบบ static (มี provenance header)
- `base_data/TH_POLICY_RATE.csv` — 85 มติ กนง. ตั้งแต่ 2015

**Tests**
- `tests/test_tf_top3_reference.py`, `tests/test_page9_ui.py`, `tests/test_fund_fees.py`, `tests/test_page_common.py`, `tests/test_tf_model.py`, `tests/tf_frozen.py`, `tests/fixtures/tf_reference_metrics.json`

**Quant team** (`.claude/quant_team/`)
- `BRIEF.md` — กติกาทีม/การตัดสินใจ
- `trials.csv` (+ `trials.backup_*.csv`)
- `specs/` — M001–M017, `M017CC_country_cap.md`, `COST_real_fees.md`
- `backtest/` — `run_m0xx.py`, `run_r1.py`–`run_r5.py` (debate), `common.py`, `selection.py`, `weighting.py`, `simulate.py`, `fees.py`, `exposure.py`,
  `export_top3.py` (TOP3 + M019 · อ่าน N_TRIALS จาก ledger · เขียน `base_data/reference/tf_top3_*` เอง ×100 + header), `export_gc75_frontier.py` (M019 · regression = `M019_weights.csv`)
- `debate/` — `DEBATE_BRIEF.md`, `R{1..5}_{researcher,modeler,results}.md`, `DEBATE_SUMMARY.md`, `TOP5.md`
- `backtest/results/` — `EXPORT_top3_*`, `FULLUNIV_*`, `ROBUST_*`, `AUDIT_fees`, `M016_*`, `M017_*`, `M017CC_*`
- `research/` — R001–R005 + INDEX
- `scratch/validator_m01x_*.json|log` — regression checks

**รายงาน/เอกสาร**
- `reports/TOP3_portfolio_logic.{md,pdf,docx}` (backup ฉบับก่อน: scratchpad `report_backup_20261005/`)
- `docs/pages/9-tf-portfolio.md`

## 5. Changes made

- **Streamlit compat**: แทน `use_container_width`/`width="stretch"` ด้วย helper ใน `page_common.py` (24 จุด) — แก้กราฟไม่ขึ้นบน Streamlit 1.40
- **ค่าธรรมเนียม**: "ไม่มี" = 0 (เดิมไป median) · แถวซ้ำเลือกค่าสูงกว่าแบบ stable (ทั้งแอปและ backtest `FeeData(legacy=False)`)
- **rf จริง**: สร้าง `TH_POLICY_RATE.csv` (แก้ parse วันที่ 2017–2018 `%d-%b-%Y`)
- **หน้า 9**: section 2 = "ผล backtest walk-forward — TOP3" + radio fee full/nofront/flat + กราฟ + ตาราง Sharpe/Return/Vol/MaxDD/ต้นทุน/DSR/รายปี + caption offset sensitivity · banner บนใช้ Trend 25
- **Reference CSV** TOP3 (4 series × 3 cases × 46 จุด, scale 100) + test
- **รายงาน TOP3** เขียนใหม่ทั้ง MD/PDF (4 หน้า)/DOCX ตามหน้า 9
- **Agent ใหม่**: `quant-researcher.md` (Opus, WebSearch/WebFetch, ไม่มี Bash) · `quant-modeler.md` อ่าน `research/`
- **Trials ใหม่** M009–M017CC + robustness (offset, fee, settlement) + export TOP3
- README/test ค้างจาก review (หน้า 9 test, regression แบบ frozen input) เสร็จแล้ว

## 6. Failed attempts

| Trial | ไอเดีย | ผล (full fee) | เหตุผลที่ไม่ผ่าน |
|---|---|---|---|
| M009-NC | หักค่าธรรมเนียมใน SR12 ก่อนสลับกอง | 0.50 | แย่ลง — ลด turnover ไม่คุ้ม |
| M010-LLD | ตัดกองซ้ำ corr > 0.85 (lead-lag) | 0.60 | แย่กว่า base |
| M014-SR05 | gate SR12' > 0.50 | 0.63 / 0.55 | ถือเงินสดมากเกิน |
| M007 | rebalance ช้าลง 6M/12M | 0.41 / 0.15 | momentum เสื่อม |
| M008 | style/macro group cap, defensive tilt | 0.54 / 0.27 | beta macro ไม่เสถียร |
| M016-CW | N=5 ถ่วงคะแนน SR12 cap 35% | 0.54 · 7.85% · DD −19.7% | Q2/2022 ถือเวียดนาม 4 กอง (61% ของพอร์ต) ขาดทุน −13.5% |
| M017-IDX | คัด index (SR12 28 ตัว) → กอง primary + SR12 · 1 index/กอง · corr ≤ 0.85 · ERC | 0.48 · 6.71% · DD −12.5% | index อันดับต้นไม่มีกองตาม (EN ปี 2022) · index รวม 7 ตัวไม่มีกองมีสิทธิ์ |
| M017-CC | M017 + เพดานประเทศ 40% ของส่วนหุ้น | 0.49 · 6.92% · DD −12.5% | cap ทำงานถูก แต่ return ยังต่ำ |
| — | tranche 3 รอบ | — | ผู้ใช้ปฏิเสธ |
| — | ผ่อนเกณฑ์ NAV สด 10 → 15 วัน เพื่อใช้ข้อมูล 2026 | — | ไม่ช่วย รูข้อมูลยังใหญ่ |
| post-hoc | M006-TCQ 0.92, M005-N5 10.4% | — | เลือกหลังเห็นผล → ตัดออกจาก TOP3 |

## 7. Specific next steps

1. **รอ NAV 2026** จากผู้ใช้ → ทำ holdout ม.ค.–มิ.ย. 2026 (ต้องมี NAV ต้น ก.ค. สำหรับ execution lag) กับ TOP3 ที่ล็อกแล้ว **ห้ามแก้พารามิเตอร์ก่อน holdout**
2. (ถ้าผู้ใช้สั่ง) เขียน **forward-test lock document** ล็อก spec TOP3 ก่อนเห็นข้อมูลใหม่
3. (ข้อเสนอ) ตารางฉากทัศน์ "ถ้าต่อรอง front-end fee ได้" ของ TOP3 → Trend 25 ≈ 11%/ปี — ไม่ใช่ trial ใหม่
4. (ทางเลือก, trial #36) fit exposure กับ MSCI ครบ 18 index ให้ index รวม (ACWI/World/EM) มีกองตามได้ — ต้องล็อก spec ก่อน
5. (ทางเลือก) 0% cash sensitivity · port GC75/M012 เข้า live portfolio ของแอป (ต้องผ่าน fullstack-planner)
6. ถ้าเพิ่ม trial ใหม่ ต้องอัปเดต DSR: รัน `export_top3.py` (อ่าน n จาก trials.csv · เขียนไฟล์อ้างอิงเอง) → แก้ `TF_TOP3_N_TRIALS` (test เทียบ ledger) + ค่า DSR ใน test + รายงาน — **ถามผู้ใช้ก่อนแก้หน้า 9/รายงาน** · ตอนนี้ตรงที่ 102 · M052 ต้องรัน `run_r6.py export52` ก่อน `export_top3.py` (รายงาน TOP3 MD = 35 · PDF/DOCX = 32 ยังไม่อัปเดต)
7. **ข้อมูลทอง**: NAV `K-GOLD-C(A)` ผิดตั้งแต่ 2024-04-23 (class กำลังปิด) → ใช้ `run_r5.clean_gold_v2` (ผู้ใช้อนุมัติ: ต่อราคาด้วย K-GOLD-A(A)) ในทุก backtest ที่ถือทอง · M019 offset 0 ไม่เคยถือ class นี้ (assert ใน export)
8. ขั้นที่ให้หลักฐานจริงของ M019/TOP5: ล็อกกติกาแล้ว forward test กับ NAV 2026 เมื่อครบ — ไม่ปรับบนข้อมูล 2022–2025 อีก

## 8. Lessons learned

- **รับความเสี่ยงเพิ่ม ≠ return เพิ่ม** ในข้อมูลนี้: ลงหุ้น 100% (8.6%) < Trend 25 (9.1%) · ถือน้อยกอง → DD ลึกขึ้น return ไม่ขึ้น
- **ค่าธรรมเนียมกิน ~1.5–2%/ปี** (front-end ≈ 95% ของต้นทุน) — คันโยก return ที่ชัดที่สุดคือลดต้นทุน ไม่ใช่โมเดล
- **2022 regime** (เงินเฟ้อ, Fed ขึ้นดอกเบี้ยเร็ว, หุ้น+บอนด์ลงพร้อมกัน, ตลาดเวียดนามร่วง) = ขาลงเดียวในช่วงวัดผล → Q2/2022 ตัดสินผลเกือบทุกโมเดล · momentum crash ตอนเปลี่ยน regime
- **ERC แบ่งความเสี่ยงต่อกอง ไม่ใช่ต่อธีม** — กองซ้ำกัน 3 กองยังได้ risk 3/N · ต้องคุมที่ขั้นคัดกอง (dedupe/1 index ต่อกอง/cap ประเทศ)
- **ประเทศของกอง = ElasticNet country_primary** (11 index VIF-clean) ไม่ใช่ prospectus · ไม่มี index ไทย (ใช้ ASEAN) · กองโลกมักออก USA · ต้องดู R²
- **ผลไวต่อวัน rebalance (offset) มาก** — ตัวเลข offset 0 อย่างเดียวหลอกได้ ต้องรายงานช่วง 0/1/2 เสมอ
- **35 trials บนข้อมูลเดียว ไม่มี holdout** → DSR ต่ำ (~0.13–0.16) · ยิ่งลองยิ่งเสี่ยง overfit → holdout ปี 2026 สำคัญที่สุด
- อย่าเดาจากชื่อกอง — ตรวจจากข้อมูล (เคยพลาดนับกองเวียดนาม 3 แทน 4)
- ข้อผิดพลาดที่เคยสื่อสารผิดแล้วแก้: rf เฉลี่ยที่ใช้ใน Sharpe = 1.79% (1.30% คือ yield เงินสดที่ได้จริง) · tranche ไม่ได้ทำให้ต้นทุน ×3 · NAV ใช้ได้จริงเริ่มปลาย 2020 / MSCI เริ่ม 2021-01
- กองตลาดเงินได้ ~1.2%/ปี ต่ำกว่า policy rate 1.59% (หลังค่าธรรมเนียม)
