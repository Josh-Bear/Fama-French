# Handoff — MSCI Fund Style Dashboard · TF Portfolio (quant modeling)

อัปเดตล่าสุด: 2026-10-07 · ภาษาที่ใช้คุยกับผู้ใช้: **ไทยเสมอ** (ดู `~/.claude/CLAUDE.md`)

---

## 1. Goal

- สร้างโมเดลจัดพอร์ตกองทุน (ไทย, long-only) สำหรับลูกค้า/พี่ที่ปรึกษา ผ่าน Streamlit "MSCI Fund Style Dashboard" (หน้า 9 = TF Portfolio)
- เป้าหลัก: **Sharpe ≥ 0.95 แบบ out-of-sample walk-forward** หลังหักค่าธรรมเนียมจริง
- โจทย์รอง (ล่าสุด): ลูกค้ารับความเสี่ยงได้มาก → อยากได้ **return 10–15%/ปี โดย Max DD ไม่เกิน −20%**
- ห้ามบิดนิยาม Sharpe / ช่วงวัดผล / universe เพื่อให้ถึงเป้า และห้ามใช้โมเดลที่เลือกหลังเห็นผล (post-hoc)

## 2. Current state

**TOP3 ที่ใช้จริง** (universe = ทุก class ซื้อได้ · rf จริง ธปท. · ค่าธรรมเนียมจริง FEEUH Actual Value · เม.ย. 2022–ธ.ค. 2025 · 45 เดือน)

| โมเดล | Sharpe | Return/ปี | MaxDD | ต้นทุน/ปี | DSR |
|---|---|---|---|---|---|
| ① GC75 + กองตลาดเงิน (M015-FAUM) ⚠️ | 0.751 | 8.07% | −7.59% | 1.50% | 0.14 |
| ② Trend 25 (M004-TF-FX) | 0.719 | 9.09% | −11.16% | 1.85% | 0.17 |
| ③ M012-QF-S (Trend 25 + rf จริง + เกณฑ์คุณภาพ) | 0.660 | 8.33% | −10.22% | 1.69% | 0.14 |
| B0 (benchmark) | 0.076 | 1.96% | −21.4% | — | — |

- ยกเว้น front-end fee: 0.94 / 0.91 / 0.84 · flat 0.5%/ข้าง: 0.68 / 0.73 / 0.67
- offset sensitivity: ① 0.35–0.98 · ② 0.41–1.00 · CI ของ Sharpe ทุกตัวคร่อม 0
- **ยังไม่มีโมเดลใดถึง 0.95 หรือ return ≥ 10% หลังหักค่าธรรมเนียม (แบบไม่ post-hoc)**
- `trials.csv` = **35 trials** (ล่าสุด M016-CW #33, M017-IDX #34, M017-CC #35 — ไม่ผ่านทั้งหมด)
- หน้า 9 section 2 แสดง TOP3 แล้ว (verify ใน browser port 8502) · pytest 179 ผ่าน
- รายงาน `reports/TOP3_portfolio_logic.{md,pdf,docx}` อัปเดตตรงกับหน้า 9 แล้ว (ส่งผู้ใช้แล้ว)
- **รอข้อมูล**: ผู้ใช้กำลังขอ NAV ปี 2026 (ม.ค.–ส.ค. รวมต้น ก.ค.) มาทำ holdout — ตอนนี้ NAV 2026 มีรูใหญ่ (กองสด 395 → 66 ใน มี.ค. 2026) จึงยังทำ holdout ไม่ได้

## 3. Key decisions & constraints

**กติกาโมเดล (ตกลงกับผู้ใช้แล้ว)**
- Universe = **ทุก class ซื้อได้** (ลูกค้าซื้อ class สถาบันได้) · 1 class ต่อ family
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
- `config.py` — `TF_TOP3_CURVES_CSV`, `TF_TOP3_METRICS_CSV`, `TF_TOP3_SERIES`, `TF_TOP3_N_TRIALS=32`
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
- `backtest/` — `run_m0xx.py`, `common.py`, `selection.py`, `weighting.py`, `simulate.py`, `fees.py`, `exposure.py`, `export_top3.py`
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
6. ถ้าเพิ่ม trial ใหม่ ต้องอัปเดต DSR ของ TOP3 (`TF_TOP3_N_TRIALS` ยังเป็น 32 · trials จริง 35) — **ถามผู้ใช้ก่อนแก้หน้า 9/รายงาน**

## 8. Lessons learned

- **รับความเสี่ยงเพิ่ม ≠ return เพิ่ม** ในข้อมูลนี้: ลงหุ้น 100% (8.6%) < Trend 25 (9.1%) · ถือน้อยกอง → DD ลึกขึ้น return ไม่ขึ้น
- **ค่าธรรมเนียมกิน ~1.5–2%/ปี** (front-end ≈ 95% ของต้นทุน) — คันโยก return ที่ชัดที่สุดคือลดต้นทุน ไม่ใช่โมเดล
- **2022 regime** (เงินเฟ้อ, Fed ขึ้นดอกเบี้ยเร็ว, หุ้น+บอนด์ลงพร้อมกัน, ตลาดเวียดนามร่วง) = ขาลงเดียวในช่วงวัดผล → Q2/2022 ตัดสินผลเกือบทุกโมเดล · momentum crash ตอนเปลี่ยน regime
- **ERC แบ่งความเสี่ยงต่อกอง ไม่ใช่ต่อธีม** — กองซ้ำกัน 3 กองยังได้ risk 3/N · ต้องคุมที่ขั้นคัดกอง (dedupe/1 index ต่อกอง/cap ประเทศ)
- **ประเทศของกอง = ElasticNet country_primary** (11 index VIF-clean) ไม่ใช่ prospectus · ไม่มี index ไทย (ใช้ ASEAN) · กองโลกมักออก USA · ต้องดู R²
- **ผลไวต่อวัน rebalance (offset) มาก** — ตัวเลข offset 0 อย่างเดียวหลอกได้ ต้องรายงานช่วง 0/1/2 เสมอ
- **35 trials บนข้อมูลเดียว ไม่มี holdout** → DSR ต่ำ (~0.1–0.17) · ยิ่งลองยิ่งเสี่ยง overfit → holdout ปี 2026 สำคัญที่สุด
- อย่าเดาจากชื่อกอง — ตรวจจากข้อมูล (เคยพลาดนับกองเวียดนาม 3 แทน 4)
- ข้อผิดพลาดที่เคยสื่อสารผิดแล้วแก้: rf เฉลี่ยที่ใช้ใน Sharpe = 1.79% (1.30% คือ yield เงินสดที่ได้จริง) · tranche ไม่ได้ทำให้ต้นทุน ×3 · NAV ใช้ได้จริงเริ่มปลาย 2020 / MSCI เริ่ม 2021-01
- กองตลาดเงินได้ ~1.2%/ปี ต่ำกว่า policy rate 1.59% (หลังค่าธรรมเนียม)
