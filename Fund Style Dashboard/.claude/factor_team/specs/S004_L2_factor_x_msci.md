# S004_L2 — factor × MSCI (spec ลงทะเบียนล่วงหน้า)

ผู้เขียน: factor-designer · วันที่ 2026-10-15 · ชั้น: **L2** (ระยะ 1 — อธิบาย · ไม่นับ trial) · สถานะ: **รอรีวิว** (reviewer → ผู้ใช้สั่งรัน)
อ้างอิง: `BRIEF.md` (แถว "gate L1" · ค่าที่ยืนยันแล้ว 1–21 · ตารางชั้น L2 · ตารางคะแนนกลางที่ lock) · `reports/L1_summary.md` ·
`specs/S002_L1_four_line_competition_rev1.md` + `specs/S003_L1_addendum_to_S002.md` (เรียกรวมว่า "S003") · `runs/S003/results.md` ·
`reviews/S003_result_review.md` + `S003_result_review_r2.md` (PASS) · `research/F-R001_literature_4lines_model_tests.md` · `research/F-R002_verify_ED_PY.md` (ค่าชั่วคราว 22–24) · `data/manifest.json` · `data/factor_groups.csv`
การตรวจโครงข้อมูลของ designer (ชื่อคอลัมน์ / จำนวนแถว / NaN / sha256 เท่านั้น — **ไม่ได้ดูค่าผลตอบแทน ไม่ได้ fit model**): `scratch/factor-designer_s004_structure.py`

> **ป้ายที่ต้องติดในรายงานผลทุกตาราง:**
> (ก) **"ED ตรงกับแหล่งรอง (R `cate::EigenDiff`) · ยังไม่เปิดต้นฉบับ Onatski 2010"** (ค่าชั่วคราวข้อ 22 · `research/F-R002_verify_ED_PY.md`) — ทุกผลของ ①a / ①c / ①b · k\* = 4 (ดูหัวข้อ 3.6) · โค้ด ED ไม่แก้ระหว่าง L2 (ข้อ 23)
> (ก2) PY: ตรงต้นฉบับ JFEc 2024 แล้ว (ข้อ 24) แต่**คงป้าย (N−1)ρ̄² > 1** ทุกแถว + รายงาน p แบบ null bootstrap คู่ (ข้อ 4)
> (ข) **"ช่วง test 2024–2025 ถูกใช้เลือกรูปแบบใน L1 แล้ว — ไม่ใช่หลักฐานนอกช่วงที่อิสระ"** — ทุกตัวเลข R²_oos / ΔR²_oos / ชื่อ factor ช่วง test
> (ค) เลขค่าที่ยืนยันแล้วที่ผลขึ้นกับ (BRIEF 1–21): panel 1/3/4/5/7 · EVAL 10 · STAB 15 · FX 20 · ③b 11 · PY 14 · ภูมิภาค/ธง 17/21 (เฉพาะพอร์ต GRS) · ED 22–23 · PY 24

---

## 0. ข้อเท็จจริงเชิงโครงสร้าง (ตรวจเอง · `factor-designer_s004_structure.py`)

| เรื่อง | ค่า | ผลต่อ spec |
|---|---|---|
| สัปดาห์ช่วงหลัก | 260 (2021-01-08 → 2025-12-26) · train 156 (Dimson 155) · test 104 | เหมือน S003 |
| MSCI 28 ใน `factors_weekly` | country/region 18 + ACWI sector 10 · **NaN = 0** ในช่วงหลัก | ใช้ได้ทุกตัว |
| style 4 (`style_relative`: Momentum, Quality, Value, LowVol) | NaN = 0 | ใช้ได้ |
| macro 7 (`macro` 5: Oil_Brent, Gold, USDTHB, Copper, DXY · `macro_delta` 2: VIX_d, US10Y_d) | NaN = 0 | ดูการแทนค่าในข้อ 2.2 |
| อนุกรม factor ของ L1 `runs/S003/factors_S003_weekly.parquet` | 260 × 69 · มี `1a__PC1..4`, `1b__PC1..4`, `1c__PC1..4`, `3b__*` (11), `4a__*` (9) · NaN = 0 ยกเว้น `4a__RPC1..5` = 1 แถว (2021-01-08) | ใช้อนุกรมนี้ตรง (ไม่ประมาณใหม่) + ตรวจสร้างซ้ำ (test 1) |
| ชุดกอง (จาก `runs/S003/results.md` §0) | EVAL 207 (E175/F18/O14) · STAB 191 (E159/F18/O14) · E67 · PY_test 206 · ฐาน 277 | ใช้ชุดเดิมทั้งหมด |
| ไม่มี MSCI Thailand ใน 28 ตัว | — | กองหุ้นไทย FIF ไม่มีดัชนี MSCI ตรง (ข้อจำกัด) |

---

## 1. คำถามและสมมติฐาน (ล็อกก่อนรัน)

**คำถาม L2 (BRIEF):** Q1 MSCI ตัวไหนเพิ่มคำอธิบายจาก factor ของ L1 **จริง** · Q2 factor ทางสถิติตรงกับดัชนีอะไร · Q3 ดัชนีไหนซ้ำซ้อน

- **H2.1 (Q2 · Bai–Ng 2006 / Connor–Korajczyk 1991):** ปริภูมิของ ①a (k = 4) บรรจุดัชนีกว้าง (ACWI, ACWI ex US, World, EM, Asia ex Japan, China All Shares) ได้เกือบทั้งหมด — R²_rev ≥ 0.80 ในช่วง train · ดัชนีประเทศเล็ก (Vietnam, India, Brazil, Korea, Taiwan) และ sector ส่วนใหญ่ R²_rev < 0.60
- **H2.2 (Q2 · การหมุน):** หลังหมุนไปหาดัชนีเป้า factor 2 ตัวแรกได้ชื่อ "≈" (|corr| ≥ 0.7) ทั้ง train และ test · ตัวที่ 3–4 อย่างมาก "คล้าย" (ตรงกับ L1 — การหมุนไม่สร้างชื่อที่ข้อมูลไม่มี)
- **H2.3 (Q1):** การเพิ่มดัชนีหลักของกอง (primary index · 1 ตัวต่อกอง) บน ①a ให้ median ΔR²_oos (E) อยู่ระหว่าง 0.01–0.06 · เพิ่มมากในกองธีม/ประเทศเดี่ยว · กอง F ≈ 0
- **H2.4 (Q1 ตัวเทียบ):** ส่วนเพิ่มจาก primary index บน ③b > บน ①a > บน ④a (④a มี factor 9 ตัวและ residual PC ดูดส่วนของประเทศ/จีนไปแล้ว)
- **H2.5 (Q3):** ดัชนีอย่างน้อย 8 ใน 28 ตัวมี R² บนดัชนีอื่น ≥ 0.90 (กลุ่ม ACWI/World/ACWI ex US/World ex US · กลุ่มจีน All/H/A · EM/Asia ex Japan)

ตัวเลขใน H เป็น**ความคาดหมายสำหรับตรวจตัวเอง** ไม่ใช่เกณฑ์ผ่านอัตโนมัติ (BRIEF: ผู้ใช้เลือก)

---

## 2. ข้อมูล

### 2.1 ไฟล์ (ตรวจ sha256 ก่อนรัน · ไม่ตรง → หยุด)

| ไฟล์ | ใช้ทำ | sha256 |
|---|---|---|
| `.claude/factor_team/data/panel_weekly.parquet` | ผลตอบแทนกองรายสัปดาห์ | `95c16ee651d3a936788b7cb3c6372bbf5f1e84cb39daf5680343771dca24270b` |
| `.claude/factor_team/data/panel_monthly.parquet` | ตรวจซ้ำรายเดือน | `e8e8cb5d5f04fba9bb35558ef7c3d8195c656334119e56f82775cc1ae21ccaed` |
| `.claude/factor_team/data/factors_weekly.parquet` | MSCI 28 · style 4 · macro · RF_BOT | `115b87139d2bec0fd57a77a1593c46d36bb23f3f35f83236cdb07be642af47a8` |
| `.claude/factor_team/data/factors_monthly.parquet` | รายเดือน | `f7c4248b4fa889853024449e72ae8909cf1f8d3226a54eebc37448a2a485bb72` |
| `.claude/factor_team/data/universe.csv` | policy · div_flag | `fdfb7830df78ce032465ac9d8cddc2c98f9aa86cfa0f3925fdb83026aa3f7252` |
| `.claude/factor_team/data/dup_pairs.csv` | ตัดซ้ำ (เหมือน S003) | `b1f0f0c745947fa70803a4f40526c0a1967c72925be985a2bedc1057d8b8aef3` |
| `.claude/factor_team/data/factor_groups.csv` | รายชื่อ MSCI 28 / style / macro | `42bf1cfb270721ae6112799ab795ebc4c91212e7584d5cdfee23b9b70b1b1731` |
| `.claude/factor_team/data/aum_weekly.parquet` | ไม่ใช้ (ระบุเพื่อ verify ชุดเดียวกับ S003) | `48c34c73ae22ebffc6112f93e03f729223a496297bb65c324b693b817a723d26` |
| `.claude/factor_team/runs/S003/factors_S003_weekly.parquet` | อนุกรม factor ①a ①b ①c ③b ④a (**ไม่ประมาณใหม่**) | `be3ceb2e34b0df1f1a3db27d59e1a103cf5f5a5ca38f2e87f7c812c1c53944ac` |
| `.claude/factor_team/runs/S003/fund_level.csv` | ธง in_EVAL / in_E67 / in_PCA_sample · ค่าฐานของ ΔR² (test 1) | `36b41161d6a13c1184a4052d9e799f660f431c2694dc57fafd747f8e695bf8cf` |
| `.claude/factor_team/runs/S003/regions.csv`, `grs_ports.csv` | พอร์ต GRS ชุดเดิม (17 พอร์ต · ฐาน 277) | analyst บันทึก sha256 ใน `run_meta.json` (ไฟล์ผลของ S003 ที่ reviewer ยืนยันแล้ว) |

### 2.2 ชุดดัชนี I_L2 (39 ตัว · ตาม BRIEF "MSCI 28 + style + macro") — ทุกตัวเป็นรายสัปดาห์ ช่วงหลัก

| บล็อก | ตัวแปร | นิยาม | ลงทุนได้ (ใช้ทดสอบ α ได้)? |
|---|---|---|---|
| **M28** | MSCI 18 country/region + 10 ACWI sector | `MSCI_x − RF_BOT` | ✓ |
| **S4** | Momentum, Quality, Value, LowVol | ตามไฟล์ (de-market แล้ว · ส่วนต่าง ไม่หัก rf) | ✓ (long–short) |
| **X7** | Oil_Brent · Copper · DXY | %Δ ราคา (ตามไฟล์) | ✗ ไม่ใช่ผลตอบแทนส่วนเกินบาท |
| | GOLD = `Gold_THB − RF_BOT` (แทน `Gold` USD) | ให้ตรง ③a และเป็นผลตอบแทนบาท | ✓ |
| | FX = `SHV_THB − RF_BOT` (แทน `USDTHB` · ค่าที่ยืนยันข้อ 20) | ผลตอบแทนส่วนเกินของการถือเงินดอลลาร์ | ✓ |
| | VIX_d · US10Y_d | Δระดับ | ✗ ลงทุนไม่ได้ |

- เหตุผลของการแทน Gold/USDTHB: ข้อ 20 ยืนยันแล้วว่า FX ของทุกการ spanning = SHV_THB − RF_BOT · ทองใช้ฉบับบาทให้ตรง ③a · `Gold` (USD) และ `USDTHB` **ไม่อยู่ใน I_L2** (ไม่นับเป็นรูปแบบเพิ่ม — เป็นนิยามตัวแปร)
- **I_inv** (ใช้ทดสอบ α = 0) = M28 + S4 + GOLD + FX (34 ตัว) · X7 ส่วนที่ลงทุนไม่ได้ (Oil, Copper, DXY, VIX_d, US10Y_d) ใช้เฉพาะ R² (ตาม F-R001: spanning ใช้ได้เฉพาะ factor ที่ลงทุนได้)
- **REG8** = 8 ดัชนีภูมิภาคเดิมของ L1 (`external.REGION_IDX`) − rf
- ห้ามใช้: `*_late_*` · `*_lvl` · `*_est_ret` · ข้อมูล ≥ 2026-01-01 (ค่าที่ยืนยันข้อ 2, 6)

### 2.3 ชุด factor ฐาน (ผู้ใช้ตัดสินที่ gate L1 · ไม่มีชุดอื่น)

| บทบาท | ชุด | K | คอลัมน์ใน `factors_S003_weekly` |
|---|---|---|---|
| **หลัก** | ①a correlation-PCA | 4 | `1a__PC1..PC4` |
| **หลัก** | ①c missing-data PCA | 4 | `1c__PC1..PC4` |
| ตัวเทียบ | ③b factor ภายนอก | 11 | `3b__*` |
| ตัวเทียบ | ④a ③a + residual PC | 9 | `4a__*` (train 154 แถวตาม S003) |
| ตัวเทียบ | ①b covariance-PCA | 4 | `1b__PC1..PC4` |

### 2.4 ช่วงเวลาและชุดกอง (เหมือน L1 ทุกประการ)
- train 2021-01-08 → 2023-12-29 · test 2024-01-05 → 2025-12-26 · H1/H2 ตาม S002 2.2
- คะแนนข้อ 1–4: **EVAL 207** (หลัก) · **E67** (กอง E นอก sample PCA — ภาคผนวก ตัวกันวงกลมของ ①a/①b) · ข้อ 5: **STAB 191** · GRS: 17 พอร์ตเดิม (`runs/S003/grs_ports.csv`) · PY: PY_test 206 (ฉบับต้นฉบับ · ค่าที่ยืนยันข้อ 14)
- ไม่มีการ impute · แถวที่ factor/ดัชนีเป็น NaN ตก

---

## 3. วิธี

### กติการ่วม (เหมือน S003)
- regression รายกอง/รายอนุกรม: **Dimson lag 1** (β = b0 + b1) · **HAC Newey–West Bartlett L = 4** (รายเดือน L = 3) · seed `20261015` · เรียง `kind="stable"`
- ทุกน้ำหนัก / การเลือก (primary index, เป้าการหมุน, เมทริกซ์หมุน, คลัสเตอร์ดัชนี) **ประมาณจาก train เท่านั้น** แล้วตรึงใช้ใน test
- R²_oos = 1 − Σ(y − ŷ)²/Σ(y − ȳ_test)² · ŷ ใช้ coef ของ train (ไม่ fit ใหม่)

### 3.1 Q2 — factor ตรงกับดัชนีอะไร (ทำกับทั้ง 5 ชุดฐาน)

**(ก) spanning ไปข้างหน้า: factor ~ บล็อกดัชนี** (Huberman–Kandel 1987 — ยังไม่ยืนยันแหล่ง · F-R001 ตาราง "วิธีทดสอบ" ระบุไว้สำหรับ L2 ตรงๆ)
- f_k,t = a_k + Σ_j (b0_kj I_j,t + b1_kj I_j,t−1) + e · บล็อกซ้อนกัน 4 ชั้น: **B1 = REG8 (16 regressor) · B2 = M28 (56) · B3 = M28 + S4 (64) · B4 = I_L2 ทั้งหมด (78)**
- รายงานต่อ factor k: R² และ adj R² (train) · R²_oos (test · coef train) · α̂ (%/ปี ×52) และ t_HAC
- **Wald ร่วม α = 0 (HAC ร่วมทุกสมการ · `tests_stat.spanning`) เฉพาะ B1 บน train** — B2–B4 มี regressor 57–79 ตัวต่อ 155 แถว เมทริกซ์ HAC ร่วม (K·p มิติ) เกินจำนวนแถว → รายงานเฉพาะ t_HAC ของ α รายสมการ · B4 ไม่ทดสอบ α (มีตัวลงทุนไม่ได้)
- อ่าน: R² ต่ำใน B4 = factor มีส่วนที่ดัชนีทั้งชุดไม่มี (สิ่งที่ "PCA จับแต่ดัชนีไม่จับ" — F-R001 ④-1)
- ③b / ④a: factor ที่เป็นดัชนี/ผลต่างของดัชนีใน M28 อยู่แล้ว (MKT = ACWI−rf · EMDM · USX) ได้ R² = 1 เชิงกล → ติดป้าย **"เชิงนิยาม"** และไม่นับในการตีความ

**(ข) spanning ย้อนกลับ: ดัชนี ~ ปริภูมิ factor** (Bai & Ng 2006, J. Econometrics "Evaluating latent and observed factors" — **ยังไม่ยืนยันแหล่ง** · ขอ researcher ตรวจ)
- I_j,t = c_j + Σ_k (d0_jk f_k,t + d1_jk f_k,t+1) + u · ใช้ **lead 1 ของ factor** เพื่อให้แนวเวลาตรงกับ Dimson (NAV สะท้อนดัชนีของสัปดาห์ก่อนบางส่วน) · แถวสุดท้ายของ test ไม่มี f_t+1 ในช่วงหลัก → ตก (ไม่ใช้ปี 2026)
- ต่อดัชนี j × ชุดฐาน: **R²_rev,j (train)** และ R²_rev,oos,j (test · coef train) · canonical correlations ระหว่าง [f] กับ M28 (train · `scorecard.canonical_corr`) เชิงบรรยาย
- ตีความ: R²_rev ≥ 0.80 = "ดัชนีอยู่ในปริภูมิ factor" · 0.50–0.80 = "บางส่วน" · < 0.50 = "นอกปริภูมิ" (ค่าตัดเชิงบรรยาย ล็อกก่อนรัน)

**(ค) การหมุนไปหาดัชนีเป้า (target rotation) — ใช้เพื่อ "ตั้งชื่อ" เท่านั้น**
- เหตุผล: factor ของ ① ระบุได้เพียงถึงการหมุน (rotational indeterminacy — Connor & Korajczyk 1991 อ้างใน F-R001 ④-1 · อ่านเฉพาะบทคัดย่อ) → ชื่อของ "PC3" ขึ้นกับการหมุนที่ PCA เลือกตามความแปรปรวน ไม่ใช่ตามความหมาย · การหมุน**ไม่เปลี่ยน**ปริภูมิ จึงไม่เปลี่ยน R², α, BIC ของกองใดเลย (test 3) — ตารางคะแนนกลางใช้ factor ไม่หมุน
- แนวทาง: oblique target rotation แบบ "factor-mimicking projection" — Procrustes/target rotation ในวรรณกรรม factor analysis (Browne 2001 · Schönemann 1966 — **ยังไม่ยืนยันแหล่ง**) ปรับให้เป้าเป็นดัชนีที่สังเกตได้ (แนวเดียวกับ hybrid ของ Connor–Korajczyk)
- **เฉพาะ ①a, ①c, ①b** (③b เป็นดัชนีตามนิยามอยู่แล้ว · ④a หมุนเฉพาะ RPC1–5 ภายในปริภูมิ residual — ภาคผนวก)
- ขั้นตอน (train · ค่าทั้งหมดล็อก):
  1. ต่อดัชนี j ∈ I_L2: B_j = (f'f)⁻¹ f' I_j (regress I_j บน f_t lag 0 + ค่าคงที่ · ไม่ใช้ lead ในการหมุน เพื่อให้ f̃ เป็นการรวมเชิงเส้นของ f ณ เวลาเดียวกัน) · ĝ_j = f B_j · R²_0,j = R² ของ regression นี้
  2. **เลือกเป้าแบบ greedy:** C = ∅ · รอบ m = 1…k: เลือก j ∉ C ที่ให้ score_j = R²_0,j × (1 − R²(ĝ_j | ĝ_C)) สูงสุด (R²(ĝ_j | ĝ_C) = R² ของ ĝ_j บน {ĝ_c} ของเป้าที่เลือกแล้ว · รอบแรก = R²_0,j) · เสมอ → ลำดับใน `factor_groups.csv` · **หยุดเมื่อ score สูงสุด < 0.25** (เป้าที่เหลือไม่มี)
  3. f̃ = f [B_c1 … B_cm] (+ ถ้า m < k: ส่วนเติมเต็มที่ตั้งฉากกับ ĝ_C ในเมตริก cov(f) ของ train · เรียงตามความแปรปรวน · ชื่อ "R-ไม่มีเป้า")
  4. ชื่อ: corr(f̃_m, I_cm) ใน **train** (= √R²_0 ตามโครงสร้าง จึงรายงานอย่างเดียว) และใน **test** ด้วย B ตรึงจาก train (ตัวที่ใช้ตัดสินชื่อ) · ป้ายตามเกณฑ์ L1: ≥ 0.7 "≈" · 0.5–0.7 "คล้าย" · < 0.5 "ไม่มีชื่อ"
  5. รายงานเป้าที่ลงทุนไม่ได้ (VIX_d, US10Y_d, Oil, Copper, DXY) ด้วยป้าย "เป้าลงทุนไม่ได้ — ชื่อเชิงบรรยาย"
- ไม่ทำการหมุนแบบอื่น (varimax ฯลฯ) — ลองนอกนี้ = spec ใหม่

### 3.2 Q1 — MSCI ตัวไหนเพิ่มคำอธิบายจาก factor ของ L1 จริง (รายกอง)

**(ก) สแกนดัชนีเดี่ยว (mapping · ไม่ใช่รูปแบบที่แข่ง):** ต่อชุดฐาน S × ดัชนี j ∈ M28 × กอง i ∈ EVAL:
- fit base: x_i ~ S (Dimson) · fit aug: x_i ~ S + I_j (Dimson · +2 regressor) · **ชุดแถวเดียวกัน**ทั้งสองโมเดล (แถวที่ทั้งคู่ไม่ NaN)
- รายงาน: ΔadjR² (train) · ΔR²_oos (test · coef train) · ΔBIC · **Wald HAC ของ (b0_j, b1_j) = 0** (train · χ²(2)) → p_ij
- **ดัชนีที่อยู่ในปริภูมิของ S เชิงนิยาม** (rank ของ design ไม่เพิ่ม · tol 1e-10 · เช่น ③b/④a + ACWI · ③b + USA) → ไม่ fit · ป้าย "ซ้ำเชิงนิยาม"
- multiple testing → ข้อ 3.4

**(ข) primary index ต่อกอง (รูปแบบที่ให้คะแนน · ข้อ 3.5):** I_p(i) = argmax_j R² ของ Dimson regression x_i ~ I_j ตัวเดียว (j ∈ M28 · train · `fundff.single_index_r2`) · เสมอ → ลำดับใน `factor_groups.csv` · บันทึก `primary_index.csv` **ก่อน fit รูปแบบใด** · ถ้าดัชนีนั้นซ้ำเชิงนิยามกับ S → ใช้อันดับถัดไปที่ไม่ซ้ำ (บันทึก)
- เหตุผลที่ใช้ M28 ไม่ใช่ REG8: กองธีม/sector/ประเทศเล็กอยู่นอก 8 ภูมิภาค (L1: ธง nonFX_eq ติดกองหุ้นต่างประเทศเชิงธีมเพราะไม่มีดัชนี sector/ASEAN — `L1_summary` ข้อ 3)
- ข้อระวังที่ล็อกไว้: การเลือก argmax ใน train ทำให้ ΔadjR² train ของ primary index **เอียงขึ้น** → ตัวเลขหลักของ Q1 คือ **ΔR²_oos** · Wald ของ primary index รายงานเชิงบรรยาย (ไม่เข้า BH — เพราะถูกเลือกด้วยข้อมูลเดียวกัน)

**(ค) บล็อก REG8 (รูปแบบที่ให้คะแนน · เฉพาะชุดหลัก):** x_i ~ S + REG8 (Dimson) · ①a: 2·12 + 1 = 25 พารามิเตอร์ · ใช้กับ ①a/①c เท่านั้น — ③b + REG8 และ ④a + REG8 **singular เชิงนิยาม** (USX = USA − ACWI, MKT = ACWI − rf) · ①b ไม่ทำ (จำกัดจำนวนรูปแบบ)

### 3.3 Q3 — ดัชนีไหนซ้ำซ้อน

- **(ก) ซ้ำกับดัชนีอื่น:** ต่อ j ∈ M28: R² ของ I_j บนอีก 27 ตัว (lag 0 · train) และ VIF (`tests_stat.vif`) · คลัสเตอร์: hierarchical complete linkage บนระยะ 1 − |corr| (train · lag 0) **ตัดที่ 0.10** (|corr| ≥ 0.90 ทุกคู่ในคลัสเตอร์) · ตัวแทนคลัสเตอร์ = ตัวที่ R²_rev บน ①a สูงสุด (ข้อมูลเพื่อ L3 · **ไม่ตัดดัชนีที่ L2**)
- **(ข) ซ้ำกับ factor:** ตามเกณฑ์ข้อ 7 P3 (R²_rev สูง + ไม่เพิ่มคำอธิบายรายกอง)
- ทำซ้ำ (ก) กับ I_L2 ทั้ง 39 ตัวเป็นภาคผนวก (ป้อน L3 ซึ่งจะทำ VIF < 5 ตาม BRIEF)

### 3.4 multiple testing (ล็อก)

| ตระกูลการทดสอบ | จำนวนโดยประมาณ | วิธีหลัก | ภาคผนวก |
|---|---|---|---|
| Q1 สแกนดัชนีเดี่ยว ต่อชุดฐาน S: กอง × ดัชนี | ①a, ①c, ①b: 207 × 28 = **5,796** · ③b/④a: 207 × (28 − ดัชนีซ้ำเชิงนิยาม) | **BH FDR 10% บนทั้งตระกูล (กอง × ดัชนี) แยกต่อชุดฐาน** (`tests_stat.bh`) | BH แยกต่อดัชนี (207 ต่อตระกูล) · **Benjamini–Yekutieli** (ทนทุกรูปแบบ dependence — ยังไม่ยืนยันแหล่ง) บนตระกูลเต็ม |
| Q2 spanning ไปข้างหน้า (t ของ α รายสมการ) | 5 ชุด × K × 4 บล็อก ≈ 128 | BH FDR 10% บนทุก t_α ของ B1–B3 รวมกัน | — |
| Q2 Wald ร่วม B1 | 5 | รายงาน p ดิบ + Holm 5 ตัว | — |
| คะแนนข้อ 3 (α รายกอง) | ต่อรูปแบบ 207 | BH FDR 10% (เหมือน L1) | — |

- เหตุที่ใช้ BH ตระกูลเต็ม: คำถาม Q1 คือ "คู่ (กอง, ดัชนี) ใดมีส่วนเพิ่มจริง" — ตระกูลธรรมชาติคือทุกคู่ · การทดสอบสัมพันธ์บวกกันมาก (กองซ้ำแนว · ดัชนีซ้อนกัน) → BH อาจไม่คุม FDR ได้ตรง จึงมี BY เป็นขอบล่างที่อนุรักษ์
- ไม่รวมตระกูลข้ามชุดฐาน (เป็นคำถามคนละข้อ) · ระยะ 1 ไม่นับ trial

### 3.5 รูปแบบที่ให้คะแนน (**7 รูปแบบหลัก + 4 ภาคผนวก k** — ลองนอกนี้ = spec ใหม่)

| รหัส | ฐาน | ส่วนเพิ่ม | K (per fund) | หมายเหตุ |
|---|---|---|---|---|
| **L2-1** | ①a | primary index | 5 | หลัก |
| **L2-2** | ①a | REG8 | 12 | หลัก |
| **L2-3** | ①c | primary index | 5 | หลัก |
| **L2-4** | ①c | REG8 | 12 | หลัก |
| L2-5 | ③b | primary index | 12 | ตัวเทียบ |
| L2-6 | ④a | primary index | 10 | ตัวเทียบ |
| L2-7 | ①b | primary index | 5 | ตัวเทียบ |
| L2-1k3 / L2-1k5 | ①a k = 3 / 5 | primary index | 4 / 6 | **ภาคผนวกความไว k** (ข้อ 3.6) |
| L2-3k3 / L2-3k5 | ①c k = 3 / 5 | primary index | 4 / 6 | ภาคผนวกความไว k |

- ชุดฐาน 5 ชุดรายงานซ้ำเป็นแถวอ้างอิง (ต้องตรงกับ `runs/S003` — test 1) ไม่นับเป็นรูปแบบใหม่
- สแกนดัชนีเดี่ยว (3.2 ก) และ spanning (3.1) เป็น mapping ไม่ใช่รูปแบบที่ให้คะแนน

### 3.6 การจัดการถ้า k\* ควรเปลี่ยน (ไม่ต้องเขียน spec ใหม่ทั้งฉบับ)

> **สถานะ ณ วันเขียน:** F-R002 เสร็จแล้ว — **ไม่พบเหตุให้เปลี่ยน k\*** (ED ตรงกับขั้นตอนของแหล่งรอง · k\* = 4 คงเดิม · ค่าชั่วคราวข้อ 22) · ข้อ 23: ไม่แก้ `≥`/`>` ในโค้ด ED ระหว่าง L2 · กลไกด้านล่างคงไว้สำหรับกรณีที่การเปิดต้นฉบับ Onatski (2010) ภายหลังให้ ED ต่างไป (หรือผู้ใช้เปลี่ยน k\* ที่ gate L2) · ภาคผนวก k = 3 / 5 เป็น**ความไวที่ลงทะเบียนล่วงหน้า** (bootstrap ของ reviewer S003: k\* ∈ 3–5) ไม่ใช่เพราะคาดว่าจะเปลี่ยน

- กฎ k\* ของ S002 = floor(มัธยฐาน{IC_p2, ER, ED, PA}) · ค่าจาก `runs/S003/nfactors.csv`: IC_p2 10 · ER 1 · PA 6 → **k\* ขึ้นกับ ED เท่านั้น**: ED′ ≤ 1 → 3 · ED′ ∈ {2, 3} → 4 · ED′ ∈ {4, 5} → 5 · ED′ ≥ 6 → floor((6 + min(ED′,10))/2) = 6–8
- **ล็อกไว้ล่วงหน้า:** รัน k = 3 และ 5 ของ ①a / ①c คู่กับ k = 4 ในการรันเดียว (L2-1k3/k5, L2-3k3/k5 + ข้อ 3.1 ข/ค ครบ) — สร้าง factor ด้วย `forms.build_line1(..., kstar=k)` (น้ำหนัก train เดิม · ①a ที่ k ใหม่ซ้อนกับ k = 4 · ①c ประมาณ EM ใหม่ที่ k นั้น)
- กรณี F-R002 ได้ k\*′ ∈ {3, 5} → **ไม่รันใหม่** · ผลอยู่ในภาคผนวกแล้ว · designer สลับเป็นตัวหลักใน L2_summary พร้อมป้าย "k\* เปลี่ยนตาม F-R002 — ใช้ผลภาคผนวกที่ลงทะเบียนล่วงหน้า"
- กรณี k\*′ ≥ 6 → analyst รันสคริปต์เดิมด้วยพารามิเตอร์ `--k k*′` (โค้ด/พารามิเตอร์อื่นเหมือนเดิมทุกบิต) ลง `runs/S004/appendix_k{k*′}/` · บันทึกเหตุใน `run.log` · **ไม่ใช่รูปแบบใหม่** · reviewer ตรวจเฉพาะส่วนต่าง
- กรณีปัจจุบัน (F-R002: ED = 2 ตามแหล่งรอง) → k\* = 4 คงเดิม · ป้าย (ก) ตามข้อ 22 จนกว่าจะเปิดต้นฉบับ
- **ไม่เปลี่ยนในทุกกรณี:** ชุดตัวเทียบ (③b, ④a, ①b) · เกณฑ์ข้อ 7 · การจัดการ L1 ที่ k ใหม่ (คะแนน L1 ของ ① ที่ k\*′ เป็นเรื่องของ L1 — ผู้ใช้ตัดสินที่ gate L2 ว่าจะต้องให้คะแนน L1 ใหม่หรือไม่)
- ①b ตัวเทียบใช้ k = 4 เสมอ (ตัวเทียบ ไม่ใช่ผู้เข้ารอบ)

### 3.7 ตรวจซ้ำรายเดือน
- L2-1, L2-3, L2-7 (p ≤ 13) และสแกน 3.2 (ก) ของ ①a: Dimson lag 1 เดือน · HAC L = 3 · factor รายเดือนตามสูตร S002 4.4 (Λ train · σ_m รายเดือน) · primary index ใช้ป้ายจากรายสัปดาห์ (ไม่เลือกใหม่) · L2-2/L2-4/L2-5/L2-6 = N/A (p > 17 กับ ~35 แถว)

---

## 4. การทดสอบทางสถิติ (สรุป)
- ต่อรูปแบบ: regression รายกอง train → α̂, β̂, t_HAC, adj R², BIC · test → R²_oos (ไม่ fit ใหม่) · ส่วนเพิ่มเทียบฐาน = ค่าของรูปแบบ − ค่าของฐานบนกองชุดเดียวกัน
- **GRS** (17 พอร์ตเดิม · fit ใหม่ในแต่ละช่วงบนอนุกรม factor น้ำหนัก train ตาม S003 4.2 ก): **เฉพาะ L2-2, L2-4** (factor ร่วม) · L = 2K = 24 · T−N−L ช่วง test = 104 − 17 − 24 = 63 · รูปแบบ primary index = **N/A (ไม่ใช่ factor ร่วม)**
- **PY** (ฉบับต้นฉบับ · PY_test 206 · ช่วง test · fit ใหม่ในช่วง): L2-2, L2-4 + แถวฐาน 5 ชุด · ป้าย (N−1)ρ̄² ตามเดิม · รูปแบบ primary index = รายงาน J พร้อมป้าย "regressor ต่างกันรายกอง — นอกกรอบทฤษฎี (บรรยาย)"
- **PY null bootstrap p (ค่าชั่วคราวข้อ 24 · ตามรีวิว S003 R4 + F-R002):** ทุกแถวที่รายงาน PY (L2-1…L2-7 + ฐาน 5 ชุด · test · และ train เป็นภาคผนวก)
  1. fit OLS รายกอง (Dimson · ชุด PY_test · แถวครบ T) → β̂_i, ê_i,t
  2. **บังคับ α = 0:** y\*_i,t = Σ(b̂0_i f_t + b̂1_i f_t−1) + ê\*_i,t — regressor คงที่ (fixed-design) · ê\* มาจาก **moving block bootstrap ตามเวลา** ความยาวบล็อก **4 สัปดาห์** (= L ของ HAC) · สุ่มดัชนีเวลาชุดเดียว**ใช้พร้อมกันทุกกอง** (คง cross-correlation ระหว่างกอง) · บล็อกต่อกันจนได้ T แถวแล้วตัดส่วนเกิน · ê ใช้ค่าดิบ (ค่าเฉลี่ย OLS = 0 อยู่แล้ว) — ต่างจากของ reviewer ที่สุ่มแถวเดี่ยว (ไม่คง autocorrelation)
  3. fit OLS ใหม่บน y\* → J\*_b ด้วย `tests_stat.pesaran_yamagata` เดิม (ρ̄² คำนวณใหม่ทุกรอบ)
  4. **B = 999 รอบ · `np.random.default_rng(20261015)` ใหม่ต่อแถวของตาราง** (ลำดับแถวล็อกตาม `scorecard.csv`) · **p_boot = (1 + #{J\*_b ≥ J}) / (B + 1)** (ข้างเดียว)
  5. รายงาน: J, p (asymptotic), p_boot, อัตราที่ p asymptotic ของ J\* < 0.05 (= size จริงภายใต้ null ของข้อมูลเรา), sd(J\*)
  - การอ่าน: p_boot เป็นตัวหลักในการบรรยาย PY ของ L2 · p asymptotic เป็นตัวอ้างอิง · ทั้งคู่ไม่ใช้ตัดสินเกณฑ์ (เหมือน L1)
  - ฟังก์ชันใหม่: `tests_stat.py_null_bootstrap(R, provider, funds, mask, B=999, block=4, seed=20261015)` → dict(J, p, p_boot, size05, sd_J, B) · test 14
- **bootstrap CI** (2,000 รอบ · seed 20261015 · สุ่มกองภายใน policy · `tests_stat.bootstrap_median`): median ΔR²_oos ของแต่ละรูปแบบเทียบฐาน (ส่วนต่างจับคู่) แยก E/F/O/ALL
- ความเสถียรของ β ดัชนีที่เพิ่ม: r ดิบ H1/H2 บน STAB (ค่าที่ยืนยันข้อ 18)

---

## 5. ตารางคะแนนที่รายงาน (ตารางกลาง 6 ข้อ + ตัวเพิ่มของ L2 · แยก E/F/O/ALL พร้อม n · EVAL หลัก · E67 ภาคผนวก)

| ข้อ | ตัวชี้ (ทุกรูปแบบ L2-1…L2-7 + แถวฐาน 5 ชุด) | หมายเหตุ |
|---|---|---|
| 1 R² รายกอง | median, IQR ของ adj R² (train) + **ΔadjR² เทียบฐาน** + CI | ส่วนเพิ่มของ primary index เอียงขึ้นใน train (3.2 ข) |
| 2 R² นอกช่วง | median, IQR ของ R²_oos + **ΔR²_oos เทียบฐาน** + CI · gap train − oos | **ตัวเลขหลักของ Q1** · ป้าย (ข) |
| 3 pricing error | mean\|α̂\| (%/ปี) · signed mean · BH count · GRS (L2-2/4) · PY | primary-index: GRS N/A |
| 4 ความประหยัด | K · median BIC_i · **median ΔBIC_i เทียบฐาน** | |
| 5 ความเสถียร | r ดิบ H1/H2 (E · STAB) ของทุก factor + ของ β ดัชนีที่เพิ่ม · rolling 104 (ภาคผนวก) | primary index: r ข้ามกองของ β_index (กองต่างดัชนีกัน → แยกรายงานตามดัชนีที่มี ≥ 10 กอง) |
| 6 ตีความได้ | ชื่อหลังหมุน (3.1 ค) ทั้ง train/test · ดัชนีที่เพิ่มมีชื่อตามนิยาม | |

**ตัวชี้วัดเฉพาะ L2 (ไฟล์ `runs/S004/`):**
- `span_forward.csv` — factor × บล็อก B1–B4: R², adj R², R²_oos, α, t_α, BH · `span_forward_wald.csv` (B1)
- `span_reverse.csv` — ดัชนี 39 × ชุดฐาน: R²_rev (train), R²_rev,oos (test), ป้ายปริภูมิ · `canon_M28.csv`
- `rotation.csv` — ชุด × factor หมุน: เป้า, score, corr train/test, ป้ายชื่อ, ลงทุนได้? · `rotation_B.csv` (เมทริกซ์ B)
- `scan_single.csv` — ชุดฐาน × กอง × ดัชนี: ΔadjR², ΔR²_oos, ΔBIC, p Wald, BH (ตระกูลเต็ม/ต่อดัชนี), BY, ป้ายซ้ำเชิงนิยาม
- `scan_by_index.csv` — ต่อชุดฐาน × ดัชนี: จำนวน/สัดส่วนกอง BH-significant แยก E/F/O · median ΔR²_oos ทั้งหมด และในกองที่ดัชนีนั้นเป็น primary · n กองที่เป็น primary
- `primary_index.csv` (เขียนก่อน fit) · `redundancy.csv` (R² บนดัชนีอื่น, VIF, คลัสเตอร์, ตัวแทน) · `map_factor_index.csv` (**แผนที่ factor ↔ ดัชนี** = ผลที่ BRIEF ต้องการ: ต่อ factor: ดัชนีอันดับ 1–3 ตาม |corr|, R² บล็อก, เป้าหลังหมุน · ต่อดัชนี: ป้ายตามเกณฑ์ P1/P3)
- `scorecard.csv` · `fund_level.csv` · `bootstrap.csv` · `stability.csv` · `grs.csv` · `py.csv` · `monthly.csv` · `appendix_k/` · `expectations_vs_results.csv` · `results.md` · `run.log` · `run_meta.json` (sha256 ข้อมูล + ไฟล์ S003 ที่ใช้ + lib)
- **ลำดับเขียนบังคับ:** `primary_index.csv` → `rotation_targets` (ส่วนเป้าของ `rotation.csv` · train) → `redundancy.csv` (คลัสเตอร์ · train) → เริ่ม fit รูปแบบ · timestamp ใน `run.log`

---

## 6. โค้ด (`.claude/factor_team/lib/` · analyst เขียน · ทุกฟังก์ชันใหม่มี test)

**ใช้ของเดิม:** `io_l1.verify_manifest / load_returns / load_factors / lib_hash` · `samples.window_mask / eligible / dedup_keep` · `regress.dimson_design / lag_stack / ols_hac / fit_funds / CommonFactors / oos_r2_funds` · `fundff.single_index_r2` · `forms.build_line1 / build_line1_k` (k ภาคผนวก) · `tests_stat.spanning / bh / vif / grs / pesaran_yamagata / bootstrap_median` · `scorecard.score_model / stability_halves / interpret / canonical_corr` · `external.REGION_IDX`

**ฟังก์ชันใหม่ — โมดูล `lib/l2.py`:**

| ฟังก์ชัน | input → output |
|---|---|
| `index_set(F)` | factors raw → DataFrame I_L2 (39) + dict บล็อก {M28, S4, X7, REG8, I_inv} ตามข้อ 2.2 |
| `load_l1_factors(path, form)` | parquet S003 + รหัสชุด → DataFrame (ตรวจ sha256 ก่อน) |
| `in_span(Fbase, col, tol=1e-10)` | → bool (rank ของ [1, D_base, D_col] เพิ่มหรือไม่) |
| `AugmentedFactors(base, extra=None, per_fund=None)` | provider ที่มี `.design(code)` `.names` `.K` สำหรับ `fit_funds` · extra = DataFrame ร่วม (REG8) · per_fund = dict กอง → Series ดัชนี (primary index) |
| `primary_index(R, IDX, mask, funds, base=None)` | → DataFrame (FundCode, index, r2, rank_used, skipped_reason) · ใช้ `single_index_r2` |
| `wald_subset(coef, V, idx)` | → (W, df, p) χ² |
| `incremental_scan(R, base, IDX, mask_tr, mask_te, funds, L=4)` | → long DataFrame กอง × ดัชนี (ΔadjR², ΔR²_oos, ΔBIC, p_wald, n, defn_dup) · ฐานและ aug ใช้แถวเดียวกัน |
| `reverse_span(I, f, mask_tr, mask_te, lead=1)` | → DataFrame ดัชนี × (R²_rev, R²_rev_oos, n) |
| `forward_span(f, blocks, mask_tr, mask_te, L=4)` | → ต่อ factor × บล็อก (R², adjR², R²_oos, α, t_α) · Wald ร่วมผ่าน `tests_stat.spanning` เฉพาะ B1 |
| `target_rotation(f, I, mask_tr, k, min_score=0.25, order=None)` | → dict(targets, scores, B, f_rot) ตามข้อ 3.1 ค |
| `index_clusters(I, mask_tr, cut=0.10)` | → DataFrame (index, r2_on_others, vif, cluster) · scipy `linkage(method="complete")` |
| `by(pvals, q=0.10)` | Benjamini–Yekutieli |
| `tests_stat.py_null_bootstrap(R, provider, funds, mask, B=999, block=4, seed=20261015)` (เพิ่มในโมดูลเดิม · ไม่แก้ฟังก์ชันเดิม) | → dict(J, p, p_boot, size05, sd_J, B) ตามข้อ 4 · ใช้ `pesaran_yamagata` เดิมภายใน |
| `run_s004.py` (`runs/S004/`) | สคริปต์รันเดียวจบ · อาร์กิวเมนต์ `--k` (ค่าเริ่ม 4 + ภาคผนวก 3, 5) |

### test ที่ต้องผ่านก่อนรัน (`pytest -p no:cacheprovider .claude/factor_team/lib/tests/` · ของเดิม 19 ข้อยังต้องผ่าน)
1. **สร้างซ้ำ L1:** `forms.build_line1(kstar=4)` บนข้อมูลจริงได้ ①a/①b/①c ตรงคอลัมน์ใน `factors_S003_weekly.parquet` (max |diff| ≤ 1e-12) · fit ฐานบน EVAL ได้ adj_r2 / r2_oos ตรง `runs/S003/fund_level.csv` (≤ 1e-10) — ไม่ผ่าน → หยุด (ตรวจโค้ด ไม่ใช่การดูผล: ค่าเหล่านี้รายงานแล้วใน L1)
2. `AugmentedFactors` + `fit_funds` = OLS ตรงบน design ที่ต่อคอลัมน์มือ (1e-10) · per_fund ใช้ดัชนีของกองนั้นจริง
3. **การหมุนไม่เปลี่ยนผลรายกอง:** f̃ = f·B (B เต็มยศ) → fitted, resid, R², R²_oos, BIC ของทุกกองเท่าเดิม (1e-8) · α เท่าเดิม
4. `target_rotation` ข้อมูลจำลอง: f = [I_a, I_b, n1]·A (A สุ่มเต็มยศ) + noise เล็ก → เป้าที่เลือก = {a, b} · corr(f̃, I) > 0.99 · factor ที่ 3 = "R-ไม่มีเป้า" · deterministic
5. `wald_subset` ตรงกับ statsmodels `OLS.fit(cov_type='HAC', cov_kwds={'maxlags':4,'use_correction':False}).wald_test` (1e-8)
6. `in_span`: ③b + ACWI → True · ③b + USA → True · ③b + EM → False · ④a + ACWI → True
7. `incremental_scan` = ผลต่างของสอง `fit_funds` ที่รันแยกบนแถวเดียวกัน (1e-12)
8. `reverse_span`: lead อยู่ถูกตำแหน่ง · แถวสุดท้ายของ test ตก · ไม่มีแถว ≥ 2026-01-01
9. `index_clusters`: ข้อมูลจำลอง 3 กลุ่ม (corr ภายใน 0.95 · ข้าม 0.3) → 3 คลัสเตอร์
10. `by` ตรงกับ `multipletests(method='fdr_by')`
11. **no look-ahead:** แก้ผลตอบแทน/ดัชนีในช่วง test → `primary_index.csv`, เป้า + B ของการหมุน, คลัสเตอร์, coef train ไม่เปลี่ยน
12. `verify_manifest` + sha256 ไฟล์ S003 ที่ใช้ · `run_s004.py` รัน 2 รอบ → ไฟล์ผลทุกไฟล์ sha256 เท่ากัน
13. ไม่มี `*_late*`, `*_lvl`, `*_est_ret`, `Gold` (USD), `USDTHB` ใน I_L2 regression
14. `py_null_bootstrap`: (ก) deterministic ที่ seed เดียวกัน · (ข) y\* มี α̂ เฉลี่ย ≈ 0 (|mean α̂\*| < 1e-4 ต่อสัปดาห์ในข้อมูลจำลอง) และดัชนีเวลาที่สุ่มเป็นชุดเดียวกันทุกกอง · (ค) ข้อมูลจำลอง H0 (N = 100, T = 104, K = 4 · error สัมพันธ์แบบบล็อกละ 5 กอง corr 0.5 + AR(1) 0.2) 200 ชุด × B = 199 → อัตรา p_boot < 0.05 อยู่ใน [2%, 9%] · (ง) p_boot = (1 + #)/(B + 1) ตรงตัวอย่างคำนวณมือ

---

## 7. เกณฑ์ (ข้อเสนอของ designer · **ผู้ใช้เลือก** · ห้ามแก้หลังเห็นผล)

**technical validity:** test ใหม่ 14 + เดิม 19 ผ่าน · hash ตรง · รันซ้ำตรงทุกบิต · ไฟล์เลือก/เป้า/คลัสเตอร์เขียนก่อน fit

**P1 — ดัชนี j "เพิ่มคำอธิบายจาก S จริง"** (ต่อชุดฐาน · ต้องผ่านทั้งสอง):
- (ก) BH-significant (ตระกูลเต็ม · FDR 10% · train) ใน ≥ 5 กอง **และ** ≥ 3% ของกอง EVAL
- (ข) median ΔR²_oos ≥ 0.02 ในกองที่ j เป็น primary index (ต้องมี ≥ 5 กอง) — ถ้า < 5 กอง ใช้ median ΔR²_oos ในกองที่ BH-significant แทน + ป้าย "n เล็ก"
- รายงานคู่ด้วย BY (ภาคผนวก) — ถ้าผ่านด้วย BH แต่ไม่ผ่านด้วย BY ติดป้าย "ไวต่อ dependence"

**P2 — factor k "ตรงกับดัชนี j" (ชื่อ):** หลังหมุน corr(f̃_k, I_j) ≥ 0.7 ใน train **และ** ≥ 0.6 ใน test (ป้าย (ข)) · 0.5–0.7 = "คล้าย" · ชื่อเดียวกันใน ①a และ ①c = "ทนต่อชุดกอง"

**P3 — ดัชนี j "ซ้ำซ้อน":**
- ซ้ำกับ factor: R²_rev ≥ 0.80 (train) และ R²_rev,oos ≥ 0.70 **และ** ไม่ผ่าน P1
- ซ้ำกับดัชนีอื่น: R² บนอีก 27 ตัว ≥ 0.90 (VIF ≥ 10) หรืออยู่ในคลัสเตอร์ตัด 0.10 ที่ไม่ใช่ตัวแทน
- ไม่เกี่ยว: R²_rev < 0.50 และไม่ผ่าน P1

**P4 — ข้อเสนอสิ่งที่ส่งต่อ L3 (VIF-cleaned):** ชุดฐานที่ผู้ใช้เลือก + {ดัชนีที่ผ่าน P1 บนชุดหลักทั้ง ①a และ ①c} → L3 ตรวจ VIF < 5 · ถ้าไม่มีดัชนีใดผ่าน → ข้อสรุป "MSCI ไม่เพิ่มคำอธิบายเหนือ factor ของ L1 อย่างมีนัย" (เป็นผลที่ยอมรับได้)
- REG8 (L2-2/L2-4) ใช้ตัดสินว่า "บล็อกภูมิภาคทั้งชุด" คุ้มไหม: ΔR²_oos (E) ≥ 0.02 **และ** median ΔBIC ≤ 0 — ไม่ใช่เกณฑ์ตัดดัชนีรายตัว
- ไม่มีเกณฑ์อัตโนมัติ · ตัวเทียบ (③b, ④a, ①b) ใช้อ่านเทียบ ไม่ใช้เลือก

---

## 8. ผลลัพธ์ที่คาดไว้ล่วงหน้า (เขียนก่อนเห็นผล)

1. **Q2 ①a:** R²_rev ≥ 0.80 สำหรับ ACWI, ACWI ex US, World, World ex US, EM, Asia ex Japan, China All Shares · < 0.60 สำหรับ Vietnam, India, Brazil, ASEAN และ sector ≥ 6 ใน 10 ตัว · ①c คล้ายกันแต่ Vietnam สูงกว่า ①a (PC3 ของ ①c คล้าย Vietnam ใน L1)
2. **การหมุน ①a:** เป้า 1 = ดัชนีโลกกว้าง (ACWI ex US หรือ ACWI · corr test ≥ 0.85) · เป้า 2 = China All Shares (≥ 0.8) · เป้า 3–4 ≤ "คล้าย" ใน test · มีอย่างน้อย 1 เป้าที่ลงทุนไม่ได้ (US10Y_d) ใน ①a · ①a กับ ①c ได้เป้า 1–2 เดียวกัน · เป้า 3–4 ต่างกันอย่างน้อย 1 ตัว (canonical 0.831 ใน L1)
3. **forward spanning:** PC1–2 R² บน B2 ≥ 0.80 · PC3–4 R² บน B4 ≤ 0.70 (มีส่วนที่ดัชนีไม่มี) · R²_oos ของ B4 ต่ำกว่า B2 (overfit 78 regressor)
4. **Q1 ①a + primary index (L2-1):** median ΔR²_oos E 0.01–0.06 · O ≥ E · F ≤ 0.01 · ΔBIC median ≤ 0 ใน E · กอง EVAL ที่มีดัชนีเดี่ยว BH-significant ≥ 1 ตัว 30–60%
5. ดัชนีที่คาดว่าผ่าน P1 บน ①a: Vietnam, India, Japan, Korea/Taiwan อย่างน้อย 1 ตัว และ sector อย่างน้อย 1 ตัว (HC หรือ IT) · ACWI/World/EM **ไม่ผ่าน** (ซ้ำกับ factor)
6. **REG8 (L2-2/L2-4):** ΔadjR² train > ΔR²_oos · median ΔR²_oos (E) ระหว่าง −0.02 ถึง +0.04 · ΔBIC > 0 (ไม่คุ้ม)
7. **ตัวเทียบ:** ΔR²_oos ของ primary index: ③b (L2-5) 0.08–0.20 > ①a ≈ ①b > ④a (L2-6) · ①b ใกล้ ①a (±0.02)
8. **Q3:** ≥ 8 ใน 28 ดัชนี R² บนดัชนีอื่น ≥ 0.90 · คลัสเตอร์ใหญ่สุดมี ACWI/World/ACWI ex US/World ex US
9. **ความไว k:** ข้อสรุป P1 (ดัชนีที่ผ่าน) ที่ k = 3 กับ k = 5 ต่างจาก k = 4 ไม่เกิน 2 ดัชนี · ส่วนเพิ่มลดลงเมื่อ k เพิ่ม
10. **PY bootstrap:** size จริงของ p asymptotic ภายใต้ null ของข้อมูลเรา 6–15% (สูงกว่า 5% · สอดคล้องกับรีวิว R4 ที่ไม่ได้ตรวจซ้ำเอง) · p_boot ≥ p asymptotic ในทุกแถว · ไม่มีแถวใดที่ p_boot < 0.05 ช่วง test
11. รายเดือน: ΔR²_oos ของ primary index สูงกว่ารายสัปดาห์ (เพราะ factor รายเดือนอธิบายได้น้อยกว่าใน L1)

---

## 9. ข้อจำกัด (ติดไปกับรายงานผล)
- **ช่วง test 2024–2025 ถูกใช้เลือกชุด factor ใน L1 แล้ว** (เกณฑ์ข้อ 1–2 ของ L1) → ΔR²_oos และชื่อใน test เป็นหลักฐานที่ไม่อิสระ · ไม่มี holdout อื่น (NAV 2026 มีรู) · การเลือก primary index / เป้าการหมุน / คลัสเตอร์ใช้ train เท่านั้น จึงไม่เพิ่มการใช้ test ซ้ำ
- **k\* = 4** — ED ตรงกับแหล่งรองแต่ยังไม่เปิดต้นฉบับ (ข้อ 22) — จัดการตามข้อ 3.6
- PY: (N−1)ρ̄² > 1 (เงื่อนไข cross-correlation อ่อนไม่เป็นจริง) · null bootstrap คง cross-correlation และ autocorrelation สั้น (บล็อก 4) แต่ถือ regressor คงที่ และไม่คงความแปรปรวนที่เปลี่ยนตามเวลาเกินบล็อก
- "MSCI" ในระบบเป็นอนุกรมจาก ETF (`MSCI_COUNTRY_ETF.csv` / `MSCI_SECTOR_ETF.csv`) — มีค่าธรรมเนียม/tracking error · ปิดเวลา NY · Dimson ช่วยได้บางส่วน (L1 lead diagnostic: 22% ของกองมี |t_lead| > 2 อย่างน้อย 1 factor)
- ไม่มี MSCI Thailand · กองหุ้นไทย FIF และกอง F ไม่มีดัชนีตรงใน I_L2 → ΔR² ของกลุ่มนี้คาดว่าใกล้ 0 โดยโครงสร้าง (ไม่ใช่หลักฐานว่าไม่มี factor)
- ①a/①b สร้างจาก balanced 134 กอง (survivorship) · กองใน sample PCA ได้เปรียบเชิงกล → รายงาน E67 คู่
- factor ของ ① เป็นพอร์ตกองที่มีน้ำหนักติดลบ → เชิงอธิบายเท่านั้น
- การทดสอบรายกองสัมพันธ์กันมาก → BH อาจคุม FDR ไม่ตรง (BY ภาคผนวก) · F (18) / O (14) n เล็ก
- spanning B2–B4 มี regressor มากเทียบ T (155) → R² train สูงเชิงกล · ใช้ adj R² และ R²_oos · ไม่มี Wald ร่วม
- ค่าตัด R²_rev 0.80/0.50, การหมุน min_score 0.25, คลัสเตอร์ 0.10 = ค่าที่ designer ตั้ง (ติดป้าย) · วิธีหมุนและ Bai–Ng 2006 ยังไม่ยืนยันแหล่ง
- ทั่วไป: FundProfile snapshot · NAV class ปันผลไม่รวมปันผล · spike F 119 จุดยังไม่แก้ (ข้อ 3)

---

## ต้องให้ผู้ใช้ตัดสินใจ
1. **เกณฑ์ P1–P4** (ข้อ 7) — ค่าที่เสนอ: BH ≥ 5 กองและ ≥ 3% · ΔR²_oos ≥ 0.02 · ชื่อ train ≥ 0.7 / test ≥ 0.6 · ซ้ำซ้อน R²_rev ≥ 0.80 / R² บนดัชนีอื่น ≥ 0.90 — เปลี่ยนได้**ก่อนรันเท่านั้น**
2. **primary index เลือกจาก MSCI 28** (ข้อเสนอ · ครอบคลุม sector/ประเทศเล็ก) หรือจาก REG8 ตาม L1 (สอดคล้อง L1 แต่พลาดกองธีม)
3. **นิยาม macro ใน I_L2:** ใช้ `Gold_THB − rf` และ `SHV_THB − rf` แทน `Gold` (USD) และ `USDTHB` (ข้อเสนอ · ตามข้อ 20) — หรือคง USD/USDTHB ตามรายชื่อเดิมของ BRIEF
4. **ภาคผนวก k = 3 / 5** (ข้อเสนอ: คงไว้เป็นความไวที่ลงทะเบียนล่วงหน้า แม้ F-R002 ไม่พบเหตุให้เปลี่ยน k\*) หรือตัดออก (ลดงาน 4 รูปแบบ)
5. **PY null bootstrap** (ข้อ 24): ค่าที่ designer ตั้ง — บล็อก 4 สัปดาห์ · B = 999 · fixed-design · ใช้ p_boot เป็นตัวบรรยายหลักของ PY — เปลี่ยนได้ก่อนรันเท่านั้น
6. **ขอ researcher ตรวจแหล่งเพิ่มใน F-R003:** Bai & Ng (2006) evaluating observed factors · Huberman–Kandel (1987) · target/Procrustes rotation · Benjamini–Yekutieli (2001) — ถ้าวิธีในแหล่งต่างจาก spec ให้ยึดแหล่งและบันทึก (ไม่เปลี่ยนจำนวนรูปแบบ)
