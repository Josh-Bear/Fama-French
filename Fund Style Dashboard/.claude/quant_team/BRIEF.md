# BRIEF — ทีม Quant (ใช้ร่วมกันทุก agent) · อัปเดต 2026-09-30

## เป้าหมายของงาน
งาน **Quantitative modeler** เพื่อเสนอลูกค้า (เสนอพี่เลี้ยงก่อน): โมเดลคัดกองทุน + จัดน้ำหนักพอร์ต จากกองหุ้นต่างประเทศ (FIF) ของไทย

**เป้าหมายหลัก: Sharpe ≥ 0.95 แบบ backtest นอกตัวอย่าง (out-of-sample walk-forward)** — นิยามตายตัว (ห้ามเปลี่ยนเอง):
- rebalance **รายไตรมาส** · ทุกการตัดสินใจ ณ วัน t ใช้ **เฉพาะข้อมูลที่มีจริง ณ วันนั้น** (ไม่มี look-ahead)
- Sharpe = (ผลตอบแทนพอร์ตรายปี − **rf ไทย**) ÷ vol พอร์ตรายปี · **หักต้นทุนการสลับกอง** (ดู "ต้นทุน")
- universe **point-in-time**: ณ วัน t ใช้กองที่มี NAV สด ณ วันนั้น ไม่ใช่รายชื่อกองที่ยังอยู่วันนี้ (กัน survivorship)
- **ถ้าทำไม่ถึง 0.95 แบบซื่อสัตย์ → รายงานค่าที่ดีที่สุดตามจริง** พร้อมเหตุผลว่าติดอะไร และต้องเปลี่ยนอะไรถึงจะถึง — ห้ามปรับนิยาม/ช่วงเวลา/พารามิเตอร์เพื่อให้ตัวเลขถึงเป้า
- ⚠️ Sharpe ที่หน้า 8 แสดงตอนนี้ (Π ÷ risk, rf = 0) **ไม่ใช่ตัววัดผล** — Π ถอดจาก γΣw จึงขึ้นกับ γ เกือบทั้งหมด (ปรับ γ ≈ 6.8 ก็ได้ 0.95) ห้ามใช้อ้างอิงผลงาน
- ความคาดหวังเชิงสมจริง: พอร์ตกองหุ้นต่างประเทศ long-only ช่วง 2021–2026 (มีปี 2022 ร่วงหนัก) มัก Sharpe ~0.4–0.7

**ขอบเขตโมเดล (ผู้ใช้กำหนด)**: เฉพาะ **กองหุ้น policy E** · **long-only** (กองทุนไทยขายชอร์ตไม่ได้) · เปลี่ยนวิธีได้ทั้งหมด —
สัญญาณ, การคัดกอง, risk model, การจัดน้ำหนัก, ความถี่/กติกา rebalance (แต่วัดผลด้วยนิยามข้างบนเสมอ)

## ผล M001 + การตัดสินใจหลัง M001 (2026-09-30)
- **M001 (หน้า 8 ปัจจุบัน, out-of-sample 2022-03→2025-12, ต้นทุน 0.5%/ข้าง, rf 2%)**: MS 0.25 · EW 0.13 · **B0 (ถือทุกกองเท่ากัน) 0.28**
  · ต้นทุน 0% → MS 0.50 · turnover ~67%/ไตรมาส (ตัวถ่วงหลัก) · CI95% กว้าง ~[-0.6, 1.4] · รายละเอียด `backtest/results/M001_baseline.md`, `reviews/M001_review.md`
- **บริบทตลาด (ช่วงเดียวกัน)**: MSCI ACWI (บาท) CAGR 10.1% vol 12.9% **Sharpe 0.65** · กองทุน 250 กองที่ข้อมูลครบ CAGR median **1.5%**
  ต่ำกว่าดัชนีหลักของกอง −6.6 pt/ปี (class -D −9.3 pt เพราะ NAV ไม่รวมปันผล · กอง passive ห่างดัชนี ~3 pt = ค่าธรรมเนียม/ภาษี/hedge
  → ข้อมูล NAV/ดัชนีถูกต้อง) · KT-JPFUND-A (hedge เยน) 16.8% vs MSCI Japan 8.8% → การ hedge ค่าเงินมีผลมาก
- **เพดาน hindsight (ห้ามเสนอเป็นผลงาน)**: long-only max Sharpe ย้อนหลัง 1.76 · 4 กอง 1.74 (ASP-NGF, M-EUBANK, KT-JPFUND-A, TISCOINA-A) ·
  กองเดี่ยว Sharpe ≥ 0.95 มี 4 กอง · correlation รายเดือนระหว่างกอง median 0.49 (10% ของคู่ < 0.09) → เป้า ~1 เป็นไปได้ในหลักการ
- **ผู้ใช้อนุญาตเพิ่ม**: พอร์ต **4–10 กอง** · ถือ **เงินสด/กองตลาดเงินได้ไม่เกิน 25%** (เงินสดได้ rf 2%/ปี) · วิธีจัดพอร์ตแบบอื่นได้ทั้งหมด
- **แนวทางที่ผู้ใช้ให้ลองใน M002–M005 (ทั้งหมด)**: (1) คัดกองจาก Sharpe/momentum ของ NAV ตัวกองเอง (2) risk parity / HRP
  (3) ลดการหมุนกอง (band/hysteresis) + ใช้ class -A แทน -D (4) trend filter / vol targeting (ใช้เงินสดได้ ≤ 25%)
- **deflated Sharpe**: สูตรเดิมใช้ n_obs ผิด → ใช้ **CI95% (block bootstrap) เป็นตัวเทียบรุ่นหลัก** จนกว่า validator แก้สูตร (คิด autocorrelation)
- **trials.csv**: ห้ามลบแถวเด็ดขาด · รันที่พังให้บันทึก status="crashed" · สำรองไฟล์ก่อนทุกรัน

## ทีมและลำดับงาน
`quant-researcher` ค้นงานวิจัย (`research/R###`, ใช้เมื่อต้องการไอเดีย/หลักฐานใหม่) → `quant-modeler` ออกแบบ (spec) → `data-qa` ตรวจข้อมูล (ถ้าข้อมูลเปลี่ยน) → `backtest-validator` วัดผลด้วยเครื่องมือกลาง
→ `model-reviewer` หาจุดอ่อน/ข้อผิด logic → วนจนผ่าน → `fullstack-planner` เขียนแผนแก้โค้ดแอป → **ผู้ใช้อนุมัติ** → ค่อยลงมือแก้
- **ไม่มีใครใน 6 ตัวนี้แก้โค้ดแอป** (pages/, analysis/, data/, data_access.py, config.py, viz.py, tests/, cache/, base_data/) — การแก้จริงเกิดหลังผู้ใช้อนุมัติแผนเท่านั้น
- sub agent ถามผู้ใช้ตรงๆ ไม่ได้ → เจอเรื่องที่ต้องตัดสินใจ (นิยาม, ข้อมูลที่ขาด, trade-off) ให้ **หยุด แล้วใส่หัวข้อ "ต้องให้ผู้ใช้ตัดสินใจ"** ในรายงาน
- ตอบ/เขียนรายงาน **ภาษาไทย** · ตัวเลขทุกตัวต้องมาจากการรันหรืออ่านไฟล์เอง (รับต่อจากคนอื่นให้เขียนว่า "ไม่ได้ตรวจซ้ำเอง")

## ประหยัดโควตา (ผู้ใช้ใช้ Claude Pro · ตกลง 2026-09-30)
- **รันทีละตัว** ห้ามแตก sub agent ต่อเอง · ทำงานให้จบภายใน `maxTurns` ของตัวเอง — ใกล้หมดให้สรุปสิ่งที่ได้ + สิ่งที่เหลือ แทนการทำต่อจนโดนตัด
- โมเดลไม่เกิน **5 เวอร์ชัน** (M001–M005) ก่อนคุยกับผู้ใช้อีกครั้ง · M001 = baseline ของโมเดลหน้า 8 ปัจจุบัน
- ใช้สคริปต์ซ้ำ (เครื่องมือ backtest กลาง, `qa/checks/`) แทนการเขียนใหม่ · อ่านไฟล์เฉพาะส่วนที่ต้องใช้ · รายงานสั้นตามจำนวนคำที่กำหนด
- data-qa ใช้เมื่อข้อมูลเปลี่ยนเท่านั้น · fullstack-planner ใช้ครั้งเดียวเมื่อได้โมเดลสุดท้ายที่ผ่านรีวิว

## โฟลเดอร์งานของทีม (`.claude/quant_team/`)
| โฟลเดอร์/ไฟล์ | เจ้าของ | เนื้อหา |
|---|---|---|
| `research/` | quant-researcher | สรุปงานวิจัย 1 ไฟล์ต่อหัวข้อ (`R###_<หัวข้อ>.md`) + `INDEX.md` — ไอเดียจัดอันดับ, หลักฐาน, แหล่งอ้างอิง |
| `specs/` | quant-modeler | spec โมเดล 1 ไฟล์ต่อเวอร์ชัน (`M###_<ชื่อ>.md`) — สมมติฐาน, สูตร, พารามิเตอร์, เหตุผล |
| `backtest/` | backtest-validator | เครื่องมือ backtest กลาง (โค้ด Python) + ผลรัน (`results/M###_*.csv/md`) |
| `trials.csv` | backtest-validator | **บันทึกทุกการรัน** (รวมที่ล้มเหลว) — model_id, วันที่, พารามิเตอร์, Sharpe, n_trials สะสม → ใช้คำนวณ deflated Sharpe |
| `reviews/` | model-reviewer | รีวิวต่อเวอร์ชัน |
| `qa/` | data-qa | รายงานคุณภาพข้อมูล |
| `plans/` | fullstack-planner | แผนแก้โค้ดแอป |
| `scratch/` | ทุกคน | สคริปต์ชั่วคราว (ตั้งชื่อนำหน้าด้วยชื่อ agent) |

## ระบบปัจจุบัน (อ่านโค้ดจริงประกอบ — path จาก root โปรเจกต์)
- **universe**: กอง E 209 กอง หลัง clean NAV · `cache/nav_clean.parquet` (NAV ที่ clean แล้วของกอง E ทั้ง universe 570 กอง
  2005-11 → 2026-08 · คอลัมน์ `FundCode, NAVDate, NAV, AUM, spike_fixed, status` — status keep 209 / few_points 203 / stale 156 / closed 2)
  → **สำหรับ backtest ใช้ประวัติจากไฟล์นี้ได้ทุกกอง** (รวมกองที่วันนี้ stale) เพื่อสร้าง universe ณ วันนั้น
- **ดัชนี**: MSCI 18 country + 10 sector (THB) `base_data/MSCI_COUNTRY_ETF.csv` / `MSCI_SECTOR_ETF.csv` ถึง 2026-07-31 · โหลดด้วย `data/msci_index.py`
- **pipeline**: `data_access.py` (`build_pipeline` → `cache/results.csv`, `coefs.csv` · exposure ElasticNet ต่อกอง **ใช้ข้อมูลทั้งช่วง** = ใช้ใน backtest ตรงๆ ไม่ได้ ต้อง fit แบบ rolling ณ วัน t)
- **return กอง**: `analysis/matching.build_fund_returns` (align NAVDate, ทบต้นดัชนีช่วงที่กองไม่รายงาน, ทิ้ง return คร่อมรู > 10 วันทำการ, winsorize 1–99%)
- **หน้า 8** (`pages/8_🧭_Score_Screen.py`, `analysis/screening.py`, `analysis/portfolio.py`): คะแนนโซน = percentile(return 12-1 ÷ realized vol)
  × R² ของกอง → greedy คัดไม่ซ้ำ country/sector (≤ 1 share class ต่อกลุ่ม · `base_data/share_class_groups.csv`) → risk model Σ = B·F·Bᵀ + D
  (756 วัน · Ledoit-Wolf) → Π = 2.5·Σ_sys·(1/N) → frontier จากกริดน้ำหนัก 5–40%
- **สเปก/ประวัติการตัดสินใจ**: `PAGE8_PORTFOLIO_OPTIMIZE_PLAN.md` (§12.13, §12.14, §19–§23) · `docs/pages/8-score-screen.md` · `docs/appendix/data-sources.md`

## หลักฐานที่มีแล้ว (dry run 2026-09-30 — มี look-ahead ของ exposure + survivorship → ตัวเลขจริงน่าจะต่ำกว่า)
- คะแนนโซนใหม่ IC ต่อ return กองจริง 63 วัน 0.132 (t 4.05) · สูตรเดิม 0.104 · return 12-1 ล้วน 0.132
- พอร์ต Top 5 equal weight ชนะค่าเฉลี่ยกอง +2.4%/63 วัน (t 5.6) — **ยังไม่ใช่ Sharpe out-of-sample ตามนิยามข้างบน**
- ระดับดัชนี: ไม่มีสูตรไหนผ่าน t = 2 · สูตรถูกเลือกจาก dry run ชุดเดียวกัน (selection bias)

## จุดอ่อนที่รู้แล้ว (อย่าค้นพบซ้ำ — ถ้าพูดถึงต้องเพิ่มมุมใหม่หรือตัวเลขใหม่)
1. greedy mark แค่คู่ที่ใช้ → กอง profile ซ้ำหลุดเข้ามาทางคู่สำรอง · 2. D คิดต่อ observation × 252 (กอง NAV ห่างโดนลงโทษ)
3. Ledoit-Wolf ในชุด 18 บิด correlation · 4. F รายวันจับ correlation ข้ามเขตเวลาต่ำเกินจริง · 5. NAV กองเอเชียช้ากว่าดัชนี
6. Π ไม่มีสัญญาณจากคะแนน (max Sharpe ≈ equal weight) · 7. class ปันผล (-D) ใช้ NAV ไม่รวมปันผล (ผู้ใช้เลือกไม่แก้)
8. ไฟล์ NAV มีรูพร้อมกันหลายร้อยกอง ม.ค.→มิ.ย. 2026 และ ม.ค.→มี.ค. 2021 · 9. cache ต่างรุ่นกัน/ไม่มี provenance (ฝั่งแอป)

## ข้อมูลที่ยัง **ไม่มี** ในระบบ (ต้องแจ้งผู้ใช้ ห้ามสมมติเอง)
- **rf ไทยรายวัน/รายเดือน** (เช่น BOT policy rate หรือผลตอบแทนพันธบัตร/ตั๋ว ธปท. 3 เดือน) — backtest-validator ต้องหยุดและขอข้อมูล
  (รายงานคู่กับ rf = 0 ได้ แต่ต้องติดป้ายชัด)
- **ต้นทุนการสลับกอง**: NAV หักค่าใช้จ่ายกองแล้ว · ค่าธรรมเนียมขาย/รับซื้อคืน/สับเปลี่ยนอยู่ใน `base_data/SecFundFee.csv`
  (schema: `base_data/FUNDPROFILE_SECFUNDFEE_SCHEMA.pdf` · รหัสกองเป็นเลข ต้อง map กับ FundCode) — ถ้า map ไม่ได้ให้ใช้สมมติฐานคงที่และติดป้าย

## กฎเหล็ก (ทุก agent)
- **READ-ONLY ต่อโค้ดแอป / cache / base_data** — เขียนได้เฉพาะในโฟลเดอร์ของตัวเองใน `.claude/quant_team/`
- **ห้ามเรียก** `data.nav_loader.load_nav_history`, `data_access.build_*`, `data_access.rebuild`, `data_access.portfolio_risk_model`
  กับกองชุดใดๆ (เขียนทับ `cache/nav_spike_fixes.csv` / ช้า) → อ่าน NAV จาก `cache/nav_clean.parquet` (pandas `read_parquet(filters=...)`)
- ใช้ `./.venv/bin/python` จาก root โปรเจกต์ (`sys.path.insert(0, ".")`) · ห้ามเปิด server / Streamlit
- อย่ารัน `pytest` โดยไม่ใส่ `-p no:cacheprovider` (กันเขียน `.pytest_cache`)

## หลัง M002–M005 (2026-09-30) — ผลและการตัดสินใจของผู้ใช้
- ผล primary (44 เดือน เม.ย. 2022–ธ.ค. 2025, cost 0.5%/ข้าง, rf 2%): M002-SR 0.636 · M003-ERC 0.649 · M004-VT 0.500 · **M004-TF 0.738** ·
  M005 (headline) 0.455 · M005-N5 0.845 (post-hoc) · DSR แก้หน่วยแล้ว (n_trials=13) ทุกตัว < 0.45 · ทุกตัวแพ้หนักปี 2022 (Sharpe −0.6 ถึง −1.1)
  แต่ 2023-07..2025-12 ≈ 1.0–1.1 → **จุดอ่อนหลัก = ตลาดขาลง** · vol-target ลด Sharpe อย่างมีนัย (Δ −0.149 CI ไม่คร่อม 0) → อย่าใช้ซ้ำ
- `simulate.deflated_sharpe` แก้บั๊กหน่วยแล้ว (ใช้ SR รายเดือน) — ตัวเลข DSR ก่อนหน้านี้ทั้งหมดผิด
- **holdout 2026 ใช้ไม่ได้** (QA_2026-09-30_holdout.md: กองที่ถือ Q1 2026 มี NAV 2–4 จาก 64 วันทำการ → vol ต่ำเกินจริง)
  ผู้ใช้เลือก: **ไม่มีไฟล์ NAV ใหม่ → วัดผลถึง ธ.ค. 2025 ถาวร ไม่มี holdout** → ทุก trial ใหม่ใช้ชุดข้อมูลเดิม → DSR/จำนวน trials สำคัญยิ่งขึ้น
- ผู้ใช้เลือกทิศทางต่อ: **ยังเป็นกองหุ้น E ล้วน · ผ่อนเงินสดได้เกิน 25% · ใช้ขากันแบบสลับตาม trend filter** (ไม่เพิ่มบอนด์/ทอง, ไม่ risk parity ข้ามสินทรัพย์)
- share class: suffix `-F` (เช่น `KKP GINFRAEQ-H` / `KKP GINFRAEQ-H-F`) = กองเดียวกัน → family map ต้องรวม (validator ต้องแก้ `fund_signals.family_of` + test)
- DAOL-GOLD = กองหุ้นเหมืองทอง (policy E ถูกต้อง) แต่เป็น concentration risk ที่ต้องเปิดเผย

## แอปเปลี่ยนแล้ว (2026-10-02) — ผลต่อการรัน M001 ซ้ำ
`analysis.screening.greedy_select` (V1: นับคู่สำรองเป็น used) · `analysis.portfolio.factor_covariance` (shrink แบบ constant correlation)
· risk model D (× จุดต่อปีจริง) เปลี่ยนในแอปแล้ว — `backtest/selection.py` เรียกฟังก์ชันชุดนี้ จึง**รัน M001 ซ้ำจะไม่ได้ผลเดิม** (0.080/0.105)
ผลอ้างอิงของ M001 อยู่ที่ `base_data/reference/m001_backtest_curves.csv` (คงที่) · ถ้าจะทดสอบโมเดลหน้า 8 ปัจจุบันต้องลงทะเบียนเป็น trial ใหม่

## การตัดสินใจผู้ใช้ 2026-10-07 — universe = ซื้อได้ทุก class
- ลูกค้าซื้อได้ทุก class (รวม class สถาบัน -IA ขั้นต่ำสูง) → **ฐานวัดผลหลัก = universe เต็ม** (ไม่ตัด class ตามขั้นต่ำการซื้อ) + rf จริง + `FeeData(legacy=False)` · ผลบน universe รายย่อย (`results/RETAIL_universe.md`) เก็บไว้เป็น sensitivity
- 2026-10-07: **ไม่ใช้การแบ่งเงิน 3 รอบ (tranche)** — ใช้ rebalance รายไตรมาสตามปฏิทินเดิม (ตัดสินใจสิ้น มี.ค./มิ.ย./ก.ย./ธ.ค. · ซื้อขายวันทำการที่ 2) เป็นตัวเลขหลัก · ผลเลื่อนเดือน (offset 1/2) รายงานเป็นช่วงความไวเท่านั้น
