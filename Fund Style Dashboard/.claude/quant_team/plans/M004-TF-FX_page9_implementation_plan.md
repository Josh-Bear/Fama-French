# แผน implement หน้า 9 — โมเดล M004-TF-FX

**สถานะ: implement แล้ว 2026-10-02** (supervisor · regression ตรง validator ทุกหลัก · test 151 ผ่าน)
ผู้เขียน: fullstack-planner · วันที่ 2026-10-02 · ไม่มีการแก้โค้ดแอปในรอบนี้

อ้างอิง: `BRIEF.md` · `specs/M002-M005_plan.md` (C2–C10) · `specs/M006_trend_cash.md` §2 · `specs/M007_slow_rebalance.md` §4 · `specs/COST_real_fees.md`
· `backtest/results/ALL_RESULTS.md`, `COST_real_fees_results.md`, `M004-TF-FX_weights.csv` · `reviews/M006-M007_review.md` (ผ่านแบบมีเงื่อนไข)
โค้ดต้นทาง (อ่านแล้ว): `backtest/{fund_signals,weighting,common,fees,simulate,run_m006_m007}.py`

## 0. ขอบเขตและสิ่งที่พบจากโค้ด/ข้อมูลจริง (ตัวเลขวัดแล้ว)

**ขอบเขต (ตามผู้ใช้ 2026-10-02):** หน้า 9 ใหม่ (live portfolio + backtest) · พอร์ตโค้ดโมเดลเข้า `analysis/` (แอปห้าม import จาก `.claude/`) ·
หน้า 8 แก้เฉพาะ caption + ลิงก์ · ตัวเลขต้องตรง validator (Sharpe 0.7205 @0.5%/ข้าง, 0.7061 ค่าธรรมเนียมจริงเต็ม, น้ำหนักต่อไตรมาสเท่า `M004-TF-FX_weights.csv`)

**ข้อค้นพบที่กระทบการออกแบบ:**
1. **ข้อมูล NAV ปี 2026 บางมาก** (วัดจาก `cache/nav_clean.parquet`, ข้อมูลถึง 2026-08-24, ดัชนี MSCI ถึง 2026-07-31):
   กองที่ NAV สด ≤ 10 วัน ณ t = **492 กอง (2025-12-31)** → **76 (2026-03-31)** → **192 (2026-06-30)** → **107 (2026-07-31)** ·
   รายวันมีกองรายงานแค่ ~125 กองจาก ~560 · ดังนั้น "ผลแนะนำ ณ วันล่าสุด" ใช้ pool เล็กกว่าที่ backtest ตรวจสอบไว้ 3–5 เท่า → ต้องมีแถบเตือน + ตัวชี้วัดความครอบคลุมเสมอ
2. **hysteresis ต้องการ "กองที่ถือก่อนหน้า"** → แอปไม่มีสถานะจริง → ใช้ **replay ไตรมาสจาก 2022-03-31** (กำหนดผลแน่นอน) แต่ไตรมาส 2026-03-31 (76 กองสด) จะทำให้สถานะเพี้ยน → ต้องตัดสินใจ (ข้อ D2)
3. **ตัวคัดกอง/น้ำหนักไม่ใช้ ElasticNet/exposure cache เลย** (สัญญาณ SR12 จาก NAV กองเอง + Ledoit-Wolf 52 สัปดาห์) → พอร์ตได้ตรงๆ ไม่แตะ `data_access.build_*` · ต้องใช้แค่ `cache/nav_clean.parquet`, MSCI CSV, `share_class_groups.csv`, `SecFundFee.csv`, `FundProfile.csv`
4. M001-MS (เส้นเทียบ) ต้องใช้ ElasticNet rolling + risk model → **ไม่พอร์ต** (หนักและไม่เกี่ยวกับโมเดลหน้า 9) → ใช้ไฟล์อ้างอิงคงที่ (ข้อ D4)
5. `simulate_path` / `FeeModel` มี regression ที่ validator พิสูจน์แล้ว (flat 0.5% ตรง cost เดิมระดับ 1e-14) → **พอร์ตตรงตัว ไม่เขียนใหม่ ไม่ "ปรับปรุง"**
6. `analysis/metrics.py` เดิมมี `cagr/annualized_return/annualized_volatility` คนละนิยาม (NAV รายวัน/วันปฏิทิน) → ห้ามใช้แทนตัวชี้วัดรายเดือนของ validator (จะทำให้ Sharpe ไม่ตรง) · ตั้งชื่อฟังก์ชันใหม่ไม่ชนกัน

## 1. สถาปัตยกรรมที่เสนอ

- **โค้ดโมเดล = ฟังก์ชันบริสุทธิ์ใน `analysis/`** (รับ DataFrame/dict คืนผล · ไม่แตะดิสก์ ยกเว้นตัวโหลดข้อมูลใน `data_access`)
- **backtest + replay สถานะ = รันใน CLI/ปุ่ม rebuild แล้ว cache ลง `cache/`** (ตามแพตเทิร์นเดิม vol/style/score: CLI `data_access.py m004tf`, ปุ่ม Rebuild เรียกต่อท้าย, อ่านผ่าน `_versioned`) —
  เหตุผล: walk-forward 15 ไตรมาส + sim 3 โหมดต้นทุน ×3 พอร์ต ใช้เวลาหลายสิบวินาที-นาที ไม่ควรรันตอนเปิดหน้า · ผลต้องนิ่ง (deterministic) ตามวันที่ cache
- **ผลแนะนำสด ณ วันล่าสุด = คำนวณเมื่อเปิดหน้า** (`get_m004tf_live`, `_versioned` ผูก mtime ของ NAV parquet + MSCI CSV + cache replay) — 1 ครั้งต่อ 1 t (~วินาที) ใช้สถานะถือครองจาก cache replay → ตอบ "ข้อมูลใหม่เข้า แต่ยังไม่ rebuild" ได้โดยไม่ต้องรัน backtest ซ้ำ
- **staleness ของ cache:** ไฟล์ cache เก็บ provenance (`nav_max_date`, mtime NAV parquet, hash ค่า `M004TF_*` ใน config) แล้วเทียบตอนโหลด (เลียนแบบ `_score_matches_clean_is_stale`) → ไม่ตรง = แสดง warning ไม่ใช่ crash เงียบ (ปัญหา 9 ใน BRIEF)
- **ไม่ยุ่งกับ pipeline เดิม:** ไม่แก้ `build_pipeline`/`results.csv`/`coefs.csv` · ไม่เพิ่มการพึ่งพา `portfolio_risk_model`

## 2. ไฟล์ / สิ่งที่ทำ / เหตุผล

| # | ไฟล์ | เพิ่ม/แก้ | สิ่งที่ทำ | เหตุผล |
|---|---|---|---|---|
| 1 | `config.py` | แก้ (เพิ่มบล็อก `M004TF_*`) | ประกาศที่เดียว: `M004TF_ID="M004-TF-FX"`, `M004TF_N=8`, `M004TF_K=16`, `M004TF_CAP=0.25`, `M004TF_TREND_SMA=200`, `M004TF_TREND_CASH=0.25`, `M004TF_RF_SIGNAL=0.02`, `M004TF_RF_SIM=0.02`, `M004TF_FRESH_DAYS=10`, `M004TF_MIN_HISTORY_NAVDATES=252`, `M004TF_WEEKS=53`, `M004TF_MIN_COV_WEEKS=30`, `M004TF_START_Q="2022-03-31"`, `M004TF_EVAL_END="2025-12-31"`, `M004TF_COST_FLAT=0.005`, `M004TF_N_TRIALS=20`, path cache (`M004TF_CACHE_*`) | กฎ "config ประกาศที่เดียว" · ค่าทั้งหมดมาจาก spec/validator ห้ามเปลี่ยนค่า |
| 2 | `analysis/fund_signals.py` | เพิ่ม | พอร์ตจาก `fund_signals.py`: `is_tax_class`, `is_dividend(fixed)`, `family_of(fixed)`, `QuarterContext` (weekly/month-end anchors, `fund_signal` → R12_1/vol52/SR12, `weekly_return_series`), `investable_set` · **เก็บเฉพาะ family_fix=True (M006 §2: token F/U, ตัดท้ายได้ 3 ครั้ง)** ตัดพฤติกรรม M002–M005 เดิมทิ้ง · `FRESH_DAYS` อ่านจาก config (เดิม hardcode 10) | โมเดลสร้างสัญญาณจาก NAV ล้วน · ตัด dual-mode ลดความซับซ้อน (regression ยืนยันด้วย weights csv ซึ่งเป็น fx=True อยู่แล้ว) |
| 3 | `analysis/fund_weighting.py` | เพิ่ม | พอร์ต: `family_representatives`, `rank_families`, `hysteresis_select` (**ตัด dedupe_corr ที่ไม่ใช้**), `apply_cap`, `covariance_or_fallback` (Ledoit-Wolf ×52, ≥30 สัปดาห์), `erc_weights`, `risk_parity_weights(method="erc")` (+fallback ivol), `trend_filter_cash` · **ไม่พอร์ต** HRP, vol_target | เฉพาะที่ M004-TF-FX ใช้ · scipy/sklearn มีใน venv อยู่แล้ว (ตรวจที่ขั้น 0) |
| 4 | `analysis/fund_backtest.py` | เพิ่ม | (ก) `quarter_ends`, `month_ends`, `execution_date`, `universe_at`, `b0_universe` · (ข) `simulate_path` (รวมโหมด scale ไม่ต้อง → **พอร์ตเฉพาะโหมด full ที่ M004-TF-FX ใช้** + `include_start=True`) + `_nav_last/_exec_nav/_grow_cash` · (ค) `FeeData/FeeModel` (full/nofront/flat) อ่าน `config.SEC_FUND_FEE_CSV` + `FundProfile.csv` · (ง) ตัวชี้วัดรายเดือน `monthly_returns, sharpe_monthly, cagr_monthly, ann_vol_monthly, max_drawdown, sortino, deflated_sharpe, block_bootstrap_ci, paired_bootstrap_diff_ci` (ชื่อไม่ชน `metrics.py`) | ตัวเลขต้องตรง validator · แยกไฟล์ตามหน้าที่ (sim/fee/metrics) ถ้าเกิน ~350 บรรทัดให้แตก `analysis/fund_fees.py` |
| 5 | `analysis/tf_model.py` | เพิ่ม | ตัวประสานระดับโมเดล: `walk_forward(nav, nav_by_fund, calendar, acwi, groups, quarter_ts) -> list[QuarterResult]` (ต่อไตรมาส: U/I counts, ตาราง signal+rank ต่อ family, hysteresis kept/added/dropped, ERC raw/cap weights, cash flag + ACWI/SMA200, fallback B0) · `live_recommendation(..., t, prev_holdings)` (ไม่มี execution date) · `build_plans(results, calendar)` → plan สำหรับ simulate (น้ำหนัก×(1−cash) + `__CASH__`) · `run_backtest(...)` → equity curves 3 โหมดต้นทุน + metrics + holdings | โลจิกจาก `run_m006_m007.py` สาย NEWQ + `old_style_plan` + `tf_cash` เท่านั้น (ไม่มี state/tranche/M007) |
| 6 | `data_access.py` | แก้ (เพิ่มฟังก์ชัน ไม่แตะเดิม) | `build_m004tf_cache(verbose)` → เขียน `cache/m004tf_*.csv` + `m004tf_meta.json` (ใช้ `_write_cache` pattern: ผลว่าง = raise ไม่เขียนทับ; เขียนไฟล์ชั่วคราวแล้ว rename) · `_load_m004tf_*` + `get_m004tf_*` ผ่าน `_versioned` (ทั้งสาขา streamlit และ fallback `ModuleNotFoundError`) · `get_m004tf_live(as_of)` · `m004tf_cache_is_stale()` · CLI `python data_access.py m004tf` · เพิ่มต่อท้าย `rebuild()` (หลัง `build_score_matches`) · อัปเดต docstring หัวไฟล์ | แพตเทิร์น cache เดิมทุกอย่าง · อ่าน NAV จาก parquet โดย `pd.read_parquet` (ห้ามเรียก `nav_loader.load_nav_history`) |
| 7 | `pages/9_📈_TF_Portfolio.py` | เพิ่ม | หน้า 9 (ดู §4) | ข้อ 1–2 ของผู้ใช้ |
| 8 | `viz.py` | แก้ (เพิ่ม 3 ฟังก์ชัน) | `equity_curves_chart` (3 เส้น log/linear), `drawdown_chart`, `weights_bar` (ฟังก์ชันละ ≤30 บรรทัด ใช้สี/ธีมเดิมใน `viz.py`) | แพตเทิร์นเดิม: กราฟอยู่ `viz.py` ไม่ใช่หน้า |
| 9 | `pages/8_🧭_Score_Screen.py` | แก้ (+ ≈4 บรรทัด) | `st.warning`/`st.caption` ใต้ title: walk-forward ของโมเดลหน้า 8 (M001) ได้ Sharpe 0.07–0.08 ที่ 0.5%/ข้าง ต่ำกว่า equal weight ของ… (ตัวเลขดึงจาก cache หน้า 9 หรือค่าคงที่ใน config) + `st.page_link("pages/9_…py")` · **ไม่แตะโลจิกอื่น** | ข้อ 1 ของผู้ใช้ · ตัวเลขต้องยืนยันก่อนเขียน (ดู D5) |
| 10 | `app.py` | แก้ (1 ประโยค) | เพิ่มชื่อหน้า 9 ในกล่อง info | ความสอดคล้อง (ค่าเดิมระบุ 8 หน้า) |
| 11 | `tests/test_fund_signals.py` | เพิ่ม | ดู §6 | known-answer |
| 12 | `tests/test_fund_weighting.py` | เพิ่ม | ดู §6 | |
| 13 | `tests/test_fund_backtest.py` | เพิ่ม | ดู §6 | |
| 14 | `tests/test_tf_model.py` | เพิ่ม | regression ต่อ validator + point-in-time/canary | |
| 15 | `tests/fixtures/m004tf_ref_weights.csv`, `m004tf_ref_metrics.json`, `m001_reference_curves.csv` | เพิ่ม | สำเนาเล็กจาก `.claude/.../results/` (น้ำหนัก 126 แถว, ตัวเลข Sharpe อ้างอิง, เส้น M001-MS/B0 ถ้าเลือก D4=ไฟล์คงที่) | test/แอปห้าม import/อ่านตรงจาก `.claude/` |
| 16 | `base_data/` หรือ `data/reference/m001_curves.csv` | เพิ่ม (ถ้า D4=คงที่) | เส้น M001-MS รายเดือน 3 เงื่อนไขต้นทุน + metadata (วันที่/สร้างโดยใคร) | M001 ต้อง ElasticNet rolling → ไม่คำนวณในแอป |
| 17 | `docs/pages/9-tf-portfolio.md` | เพิ่ม | อธิบายระบบจริง: กฎคัดกอง/ERC/trend, replay, cache, ข้อจำกัด | |
| 18 | `docs/README.md` | แก้ | "8 หน้า"→"9 หน้า", แถวตารางหน้า 9, คำสั่ง `data_access.py m004tf`, วัน "อัปเดตล่าสุด" | |
| 19 | `docs/pages/8-score-screen.md` | แก้ (ย่อหน้าสั้น) | บันทึกผล walk-forward ของ M001 + ลิงก์หน้า 9 | |
| 20 | `docs/appendix/data-sources.md` | แก้ (ถ้ามีตาราง cache) | เพิ่ม `m004tf_*` cache + `SecFundFee.csv` ที่ใช้เป็นครั้งแรกในแอป | |

หน้าอื่น (1–7) ไม่แก้ · `analysis/{matching,metrics,portfolio,screening,macro_chain,vol_forecast}.py` ไม่แก้ (หน้า 9 ไม่เรียก)

## 3. ขั้นตอน implement (เรียงลำดับ · ทุกขั้นเช็ค 3 ข้อ: **ก** โค้ดที่เขียนถูกไหม · **ข** ของเดิมยังรันได้ไหม · **ค** โครงสร้างยังดีไหม)

**ขั้น 0 — baseline ก่อนแก้ (เล็ก):** `git status`; `./.venv/bin/python -m pytest -q -p no:cacheprovider` เก็บจำนวน pass; รัน `checkpoint1.py`; สำรอง `cache/` ทั้งโฟลเดอร์เป็น `cache_backup_<วันที่>/` (นอก git) โดยเฉพาะ `nav_clean.parquet`, `results.csv`; บันทึก mtime ของ cache เดิม · ตรวจ `import scipy, sklearn` · สั่ง validator ส่งออกไฟล์อ้างอิง (ข้อ 15)
 ข: baseline pass ครบก่อนเริ่ม · ค: ยืนยันว่า `analysis/` ไม่มีชื่อชน

**ขั้น 1 — config (เล็ก):** เพิ่มบล็อก `M004TF_*` · ก: ค่าตรงสเปก/`run_m006_m007.py` (SEL_N/K, 0.25, SMA200 ฯลฯ) ทีละบรรทัด · ข: `_cache_stamp` hash config → cache เดิมที่ผูก stamp จะ invalid ครั้งเดียว (คาดหมาย, ไม่ใช่บั๊ก ต้องแจ้งผู้ใช้) · ค: ไม่มีค่า hardcode ซ้ำในโมดูล

**ขั้น 2 — `fund_signals.py` + test (กลาง):** พอร์ต + test ก่อนไปต่อ · ก: test รู้คำตอบ (ดู §6) + เทียบฟังก์ชันกับต้นฉบับบน NAV จริง ณ t 3 ค่า (ผลตรงทศนิยม 1e-12 — สคริปต์ชั่วคราวใน scratchpad ไม่ commit) · ข: pytest เดิมผ่านเท่า baseline · ค: ไม่มี import จาก `.claude/`

**ขั้น 3 — `fund_weighting.py` + test (กลาง):** ก: เทียบ ERC/cap/hysteresis กับต้นฉบับบน input เดียวกัน (น้ำหนัก ≤ 1e-9) · ข/ค: เช่นเดิม

**ขั้น 4 — `fund_backtest.py` + test (ใหญ่):** พอร์ต sim/fees/metrics · ก: (1) โหมด flat 0.5% = cost_side 0.5% (1e-12) (2) สร้างเส้น B0 จาก NAV จริง ต้องได้ Sharpe 0.0707 @0.5%/0.0596 เต็ม (3) ตัวชี้วัดเทียบ `simulate.py` ต้นฉบับบน series เดียวกัน · ข: เดิมผ่าน · ค: ถ้าไฟล์ > ~350 บรรทัด แตก fees ออกเป็น `fund_fees.py`

**ขั้น 5 — `tf_model.py` + regression เต็ม (ใหญ่ · ขั้นเสี่ยงสุด):** รัน walk-forward 15 ไตรมาส (2022-03-31..2025-09-30) → เทียบ **ทุกไตรมาส**: รายชื่อกอง 8 ตัว, น้ำหนัก (|Δw| ≤ 1e-9; เกณฑ์ผ่อนสูงสุด 1e-6 กรณีต่างเวอร์ชัน sklearn/scipy — ถ้าเกินหยุดและรายงาน), cash flag ต่อไตรมาส, จำนวน fallback B0 → sim ได้ **Sharpe 0.7205 (0.5%) / 0.7061 (เต็ม) / 0.8933 (ยกเว้น front) / CAGR 9.17% / maxDD −10.4%** (4 ตำแหน่ง) · canary: ตัดข้อมูล NAV หลัง t ทิ้งแล้วผลต้องเหมือนเดิม (point-in-time) · ก/ข/ค ตามกติกา · **ห้ามไปขั้น 6 ถ้า regression ไม่ผ่าน**

**ขั้น 6 — replay + live + cache ใน `data_access.py` (กลาง):** replay ไตรมาสถึงไตรมาสล่าสุด (นโยบายตาม D2), `live_recommendation` ที่ t ล่าสุด (D1) · เขียน cache แบบ atomic · ก: ผล replay 15 ไตรมาสแรก = ผลขั้น 5 เป๊ะ (state เดียวกัน) · ข: ไม่แตะ `rebuild` เดิมจนกว่าขั้นนี้ผ่าน แล้วจึงเพิ่มต่อท้าย (ในบล็อก try/finally เดิมที่ล้าง cache ให้แล้ว) · ค: ฟังก์ชัน `_versioned` ใหม่ทั้งสองสาขา (streamlit/fallback) ครบ

**ขั้น 7 — viz + หน้า 9 (กลาง):** ดู §4 · รัน `streamlit` ผ่านเครื่องมือตรวจ UI (ตามกฎ BRIEF ห้ามเปิด server ใน quant team แต่ขั้นนี้เป็นงาน implement หลังอนุมัติ — ใช้ skill `run`) · ก: ตัวเลขบนหน้า = cache = validator · ข: เปิดหน้า 1–8 ครบไม่ error (โดยเฉพาะ 8) · ค: ตรรกะไม่ซ้ำใน page (อยู่ใน analysis/viz)

**ขั้น 8 — หน้า 8 caption + app.py (เล็ก):** ก: ตัวเลข/ลิงก์ถูก (`st.page_link` ชื่อไฟล์ตรง) · ข: หน้า 8 เปิดได้ ตารางเดิม/frontier ไม่เปลี่ยน (เทียบ screenshot/ค่าก่อนแก้) · ค: ไม่เพิ่ม logic

**ขั้น 9 — docs (เล็ก):** ข้อ 17–20 · ค: ตัวเลขในเอกสารตรงกับ cache จริง ณ วันนั้น

**ขั้น 10 — ตรวจรวมท้าย (เล็ก):** pytest ทั้งชุด ≥ baseline + test ใหม่ · `checkpoint1.py` · `data_access.py m004tf` รันซ้ำสองครั้ง → ผลเท่ากันทุก byte (determinism) · `grep -r "\.claude" analysis pages data_access.py` ต้องไม่พบการ import/อ่านไฟล์ · `git status` เห็นเฉพาะไฟล์ในตาราง · ให้ model-reviewer/code-reviewer ตรวจก่อนปิด

## 4. หน้า 9 — โครงหน้า

1. **หัว + แถบสถานะ:** ชื่อโมเดล, วัน as-of, วันข้อมูล NAV ล่าสุด, อายุ cache, ป้าย "ไม่ใช่คำแนะนำการลงทุน", **warning ถาวร**: DSR 0.22 @20 trials · ไม่มี holdout (วัดผลถึง 2025-12) · NAV ปี 2026 มีรู (กองสดเหลือ x/y ณ t) · theme concentration (เช่น DAOL-GOLD, เวียดนาม)
2. **(a) ผลแนะนำปัจจุบัน:** metric 4 ช่อง (สถานะ trend: ACWI vs SMA200 → เงินสด 25%/0%; จำนวนกอง; pool ที่ผ่าน I_t/U_t; coverage freshness) · ตาราง 8 กอง + เงินสด: FundCode, family, น้ำหนักหลัง ERC/cap, น้ำหนักสุดท้ายหลังเงินสด, R12-1, vol52, SR12, rank, สถานะ (คงไว้ ← อยู่ใน K=16 / เพิ่มใหม่ / ตกออก) · ตารางกองที่ถูกตัดออกจาก hysteresis (ถือเดิมแต่ rank > 16) · expander "สัญญาณทั้ง pool" เรียงตาม SR12 · expander "ไตรมาสที่ replay มา (state)" แสดง holdings แต่ละไตรมาส + ป้าย coverage ต่ำ
3. **(b) backtest:** กราฟ equity (M004-TF-FX vs B0 vs M001-MS) + drawdown · ตารางตัวชี้วัด 3 เงื่อนไขต้นทุน (0.5%/ข้าง, ค่าธรรมเนียมจริงเต็ม, ยกเว้น front-end): Sharpe, CAGR, vol, maxDD, DSR@20, CI95% bootstrap · ตารางน้ำหนักถือครองต่อไตรมาส (pivot) · ผลรายปี (2022 แพ้, 2023–25 ชนะ) · expander ข้อจำกัด (DSR 0.22, CI [−0.37, 1.86] คร่อม 0, ตัดไตรมาสดีสุดเหลือ 0.41, ไม่มี holdout, รู NAV 2026, DAOL-GOLD/theme, rf คงที่ 2%, M008 ลอง cluster cap/quality tilt แล้วไม่ดีกว่า)
4. ทุก error จาก cache/ข้อมูล = `st.error` + คำสั่งแก้ (`./.venv/bin/python data_access.py m004tf`) ไม่ปล่อย traceback · `st.stop()` ถ้าไม่มี cache

## 5. ตัวเลขอ้างอิง/เกณฑ์ regression (จาก validator)

| รายการ | ค่าเป้า |
|---|---|
| M004-TF-FX Sharpe @0.5%/ข้าง (rf 2%, 2022-04..2025-12, นับเดือนแรก) | 0.7205 |
| ค่าธรรมเนียมจริงเต็ม / ยกเว้น front-end | 0.7061 / 0.8933 |
| CAGR (0.5% / เต็ม) · vol · maxDD | 9.3% / 9.17% · 10.3% · −10.4% |
| DSR @n=20 (เต็ม) | 0.223 (ต้นฉบับ DSR@20 ตามตารางรายงานคือ ~0.22) |
| B0 Sharpe 0.5% / เต็ม | 0.071 / 0.060 |
| น้ำหนัก | 126 แถว/15–16 ไตรมาส ตรง `M004-TF-FX_weights.csv` (|Δ| ≤ 1e-9) · แถว `__CASH__` ตรง (6 แถว) |

หมายเหตุ: ต้องยืนยันว่าตัวเลข DSR/CAGR ที่ใช้อ้างในหน้า = ค่าจาก `COST_real_fees_summary.csv` (คอลัมน์ `dsr20_full`, `cagr_full`) ที่ขั้น 0 ก่อนเขียน fixture

## 6. Test ใหม่ (known-answer + edge case)

- `test_fund_signals.py`: family_of (`KKP GINFRAEQ-H-F`→กลุ่มเดียวกับ `-H`; `-F`, `-U`, `X-D-F` เป็น dividend; ตัดท้าย 3 ครั้ง; csv map มาก่อน suffix) · `is_tax_class` (SSF/RMF/TESG/THAIESGX) · SR12 บน NAV สังเคราะห์โตคงที่ (R12-1, vol52 รู้คำตอบ) · vol52 = NaN เมื่อ zero_frac > 0.2 หรือ < 40 สัปดาห์ หรือ vol < 0.02 · asof tol 10 วัน (ขอบ 10/11 วัน) · `investable_set`: ตัด stale>10, tax, dividend ที่มี non-div ในครอบครัวเดียวกัน, NaN signal · **point-in-time:** เปลี่ยน NAV หลัง t แล้วผลไม่เปลี่ยน
- `test_fund_weighting.py`: representatives เลือก class ที่ถืออยู่ (ไม่สลับ class) · rank tie-break (vol ต่ำก่อน, ชื่อ) · hysteresis: คงไว้เมื่อ rank ≤ 16, ตัดเมื่อ > 16, เติมให้ครบ 8, fallback b0 เมื่อ < 4 · `apply_cap` (ผลรวม 1, ไม่เกิน 25%, N เล็ก cap×N≈1) · ERC: Σ แนวทแยง → inverse-vol; 2 สินทรัพย์รู้ผลปิด; risk contribution เท่ากัน (1e-6) · fallback ivol เมื่อ < 30 สัปดาห์ · `trend_filter_cash` (SMA200 ขอบ A_t = SMA, < 200 จุด = 0)
- `test_fund_backtest.py`: `simulate_path` (ไตรมาสเดียว ซื้อถือ, ต้นทุน flat, `__CASH__` ไม่เสียต้นทุน, ซื้อไม่ได้→เงินสด, assert น้ำหนักรวม) · FeeModel (flat = cost_side; สับเปลี่ยนใน AMC เดียวกันเลือกช่องถูกกว่า; FEEUH > 10 → median; ก่อน snapshot แรก ใช้เก่าสุด) · sharpe/cagr/maxDD/sortino ค่ารู้คำตอบ · deflated_sharpe หน่วยรายเดือน (regression ค่า 0.223) · `execution_date` = วันทำการที่ 2 · `universe_at` (ไม่ดูคอลัมน์ status, ตัดเก่า > 90 วัน/ประวัติ < 252)
- `test_tf_model.py`: regression เทียบ fixture (มาร์ก skip ถ้าไม่มี `cache/nav_clean.parquet`) · determinism (รัน 2 ครั้งเท่ากัน) · live ที่ t = ไตรมาส backtest ได้พอร์ตเดียวกับ walk-forward · live เมื่อ coverage ต่ำ → คืน flag/ข้อความเตือน ไม่ crash · ไม่มีกองใน pool → คืนผลว่างอย่างปลอดภัย
- test เดิมที่ต้องปรับ: ไม่มี (ยกเว้นถ้า `test_smoke.py` นับจำนวนหน้า — ขั้น 0 ตรวจ)

## 7. ผลกระทบต่อหน้าอื่น / จุดร่วม

| จุด | ผลกระทบ | ต้องเช็คหลังแก้ |
|---|---|---|
| `config.py` hash ใน `_cache_stamp` | เพิ่มค่า → ทุก `_versioned` cache in-memory หมดอายุหนึ่งครั้ง | หน้า 1–8 โหลดได้ปกติ |
| `data_access.rebuild()` | เพิ่มขั้นท้าย | ขั้น m004tf ล้มต้องไม่ทำให้ cache เดิมเสีย (try/finally เดิมล้าง in-memory) · เวลา rebuild เพิ่ม (วัดจริงแล้วแจ้ง) |
| `nav_clean.parquet` | อ่านอย่างเดียว (`read_parquet`) | ไม่เขียน/ไม่เรียก `build_*` |
| `build_fund_returns`, snapshot หน้า 8 | ไม่เกี่ยว (โมเดลใหม่ไม่ใช้) | หน้า 8 เทียบก่อน/หลัง |
| memory | อ่าน parquet ทั้งไฟล์ (~ใหญ่) ตอน live | วัด memory/เวลาเปิดหน้า · ใช้ `columns=` ที่จำเป็น |
| `SecFundFee.csv` | ครั้งแรกที่แอปอ่าน (อยู่ใน config แล้ว) | encoding `utf-8-sig`, dtype=str |

## 8. ความเสี่ยง

| ความเสี่ยง | ระดับ | การจัดการ |
|---|---|---|
| ตัวเลขไม่ตรง validator (floating/sklearn version/ลำดับ tie-break/ลำดับ groupby) | กลาง | regression ทุกไตรมาส · พอร์ตตรงตัวไม่ refactor ลอจิก · เกณฑ์ 1e-9 |
| **NAV 2026 เป็นรู** ทำให้ผลสด/state replay เพี้ยน (pool 76–192 vs ~490) | **สูง** | ป้ายเตือน + coverage · ตัดสินใจ D1/D2 · อย่าอ้างผลสดว่าผ่านการตรวจสอบ |
| ผู้ใช้ตีความเป็นคำแนะนำซื้อขาย (DSR 0.22, CI คร่อม 0, ไม่มี holdout) | สูง | warning ถาวรบนหน้า + disclaimer |
| theme concentration (DAOL-GOLD, เวียดนาม, ธีมซ้ำข้าม family) | กลาง | คอลัมน์/ป้ายธีมเท่าที่ทำได้โดยไม่เปลี่ยนโมเดล (ชื่อกอง) · ระบุใน limitations |
| cache เก่า/ไม่ตรงข้อมูล | กลาง | provenance + staleness warning |
| การ rebuild ช้า/ทับ cache เดิมถ้า error | ต่ำ | เขียน atomic, ผลว่าง=raise |
| import จาก `.claude/` หลุดเข้ามาโดยไม่ตั้งใจ | ต่ำ | grep ในขั้น 10 + test |
| ปรับปรุงโมเดลระหว่างพอร์ต (scope creep) | กลาง | กฎ: ห้ามเปลี่ยนโมเดล — ข้อเสนอแก้ไขให้ไปรอบ quant-modeler |
| DSR/trials เพิ่มในอนาคต (n=20 ตายตัวใน config) | ต่ำ | config ตัวเดียว + บอกวันที่ที่ n ถูกตรึง |

## 9. ขนาดงาน

| ขั้น | ขนาด | ขั้น | ขนาด |
|---|---|---|---|
| 0 baseline | เล็ก | 6 replay+live+cache | กลาง |
| 1 config | เล็ก | 7 viz+หน้า 9 | กลาง–ใหญ่ |
| 2 signals | กลาง | 8 หน้า 8/app | เล็ก |
| 3 weighting | กลาง | 9 docs | เล็ก |
| 4 backtest/fees/metrics | ใหญ่ | 10 ตรวจรวม | เล็ก–กลาง |
| 5 tf_model+regression | ใหญ่ | **รวม** | ไฟล์ใหม่ 10 (โมดูล 4 · หน้า 1 · test 4 · docs 1) + fixture 3 · ไฟล์แก้ 8 · 11 ขั้น |

## 10. ต้องให้ผู้ใช้ตัดสินใจ

- **D1 — วัน as-of ของ "ผลแนะนำสด":** (ก) วันข้อมูลล่าสุดของดัชนี 2026-07-31 (กองสดเพียง 107) · (ข) สิ้นไตรมาสล่าสุด 2026-06-30 (192 กอง) · (ค) ให้ผู้ใช้เลือกวันบนหน้า (selectbox) default = (ก) พร้อมแถบ coverage · **แนะนำ (ค)** เพราะความต่างของ coverage ชัดและไม่ต้องล็อกสมมติ
- **D2 — state ของ hysteresis:** (ก) replay ทุกไตรมาสถึง 2026-06-30 ตามกฎ freshness (กำหนดผลแน่นอน แต่ 2026-03-31 มีกองสดแค่ 76 → ถือกองผิดปกติ) · (ข) replay ถึง 2025-12-31 (ช่วงที่ validator ตรวจ) แล้วคิดผลสดโดยสมมติถือพอร์ต ธ.ค. 2025 · (ค) replay ทุกไตรมาสแต่ "ข้าม" ไตรมาสที่ coverage < เกณฑ์ (carry state) — **แนะนำ (ค) เกณฑ์ = กองสด ≥ 50% ของจำนวนกอง U_t ที่ไตรมาส 2025-12-31** (ระบุเกณฑ์ใน config, ทั้ง 2026-03/06 จะถูกข้าม) · ตัวเลือกใดก็แสดง state ที่ใช้บนหน้า
- **D3 — ถ้า coverage ต่ำกว่าเกณฑ์ ณ as-of:** (ก) แสดงผลพร้อมเตือน (ข) ไม่แสดงน้ำหนัก แสดงแต่ตารางสัญญาณ · แนะนำ (ก) ถ้า coverage ≥ 25%, ต่ำกว่านั้น (ข)
- **D4 — เส้น M001-MS บนกราฟเทียบ:** (ก) ไฟล์คงที่สำเนาจาก validator (แนะนำ · มีวันที่/ที่มาติดป้าย) · (ข) พอร์ต rolling ElasticNet+risk model เข้าแอป (ใหญ่ ไม่แนะนำ) · (ค) ไม่แสดง M001 แสดงแต่ B0 · (B0 คำนวณสดในแอปได้)
- **D5 — ถ้อยคำ/ตัวเลขใน caption หน้า 8:** ใช้ผล M001 ที่ validator วัด: Sharpe MS 0.080 / EW −0.024 / B0 0.071 @0.5%/ข้าง (full fee 0.105/−0.006/0.060) — ผู้ใช้ระบุว่า "แพ้ equal weight" แต่ตัวเลข @0.5% ของ MS (0.080) **สูงกว่า** EW (−0.024) เล็กน้อย; จึงขอยืนยันถ้อยคำ: "ไม่ชนะ B0/equal weight แบบมีนัย" หรือ "แพ้ EW" ตามเงื่อนไขไหน (ฐานเทียบเป็น B0 = 1 class/กลุ่ม)
- **D6 — วัดผลใช้ n_trials = 20:** ตรึงใน config (DSR 0.22) · ยอมรับไหมว่าต่อไปถ้ามี trial เพิ่มต้องแก้ค่านี้เอง
- **D7 — rebuild:** เพิ่ม m004tf ในปุ่ม Rebuild เดียวกัน (เวลารวมเพิ่ม ~?? วินาที วัดจริงขั้น 6) หรือแยกปุ่ม/CLI อย่างเดียว · แนะนำ CLI + ปุ่ม rebuild เดียวกัน
- **D8 — เลขหน้า/ชื่อไฟล์:** `pages/9_📈_TF_Portfolio.py` ชื่อหน้า "TF Portfolio" ตกลงไหม (หรือชื่ออื่น เช่น "Model Portfolio")
- **D9 — ไฟล์ fixture/ข้อมูลอ้างอิง** (`tests/fixtures/*`, `data/reference/m001_curves.csv`) commit เข้า git ได้ไหม (ขนาดเล็ก < 100KB) — `cache/` ถูก gitignore อยู่แล้ว

## ผู้ใช้ตัดสินใจแล้ว (2026-10-02)
- **D1** วัน as-of ของผลสด: **ให้เลือกบนหน้า** · ค่าเริ่มต้น = สิ้นไตรมาสล่าสุดที่กองสดพอ · แสดงจำนวนกองสด ณ วันนั้นเสมอ
- **D2** hysteresis: **replay ทุกไตรมาส แต่ข้ามไตรมาสที่กองสด < 50% ของ U_t ณ 2025-12-31** (คงสถานะเดิม) · แสดงบนหน้าว่าข้ามไตรมาสไหน
- **D3** กองสดน้อย: **แสดงพอร์ต + กล่องเตือนแรง** (บอกว่าเลือกจากกองน้อยกว่าปกติกี่เท่า)
- **D4** เส้น M001: **ไฟล์อ้างอิงคงที่จาก validator** (ไม่พอร์ต ElasticNet rolling)
- D5–D9: รอผู้ใช้ยืนยัน (supervisor เสนอค่าเริ่มต้นแล้ว)
- **D5** caption หน้า 8: "ใกล้เคียง B0 (0.06) และต่ำกว่าหน้า 9 (0.71)" ด้วยค่าธรรมเนียมจริง · **D6–D9** ตามค่าเสนอ · **อนุมัติให้ implement 2026-10-02**

## หมายเหตุการ implement (2026-10-02)
- โมดูล: `analysis/fund_signals.py`, `fund_weighting.py`, `fund_backtest.py`, `fund_fees.py`, `tf_model.py` · config บล็อก `TF_*` · CLI `data_access.py tf`
- D2 ตีความ: กองสด ณ t < 50% ของกองสด ณ 2025-12-31 (395) และ t > 2025-12-31 → ข้าม (2026-03 = 66 · 2026-06 = 155 ถูกข้าม)
- เส้น M001 = `base_data/reference/m001_backtest_curves.csv` (ไฟล์คงที่) · B0 คำนวณในแอป
