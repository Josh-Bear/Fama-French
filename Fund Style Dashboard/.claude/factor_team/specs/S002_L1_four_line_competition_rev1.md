# S002_L1 — การแข่ง L1 ทั้ง 4 สาย (ฉบับแก้ของ S001 · spec ลงทะเบียนล่วงหน้า)

ผู้เขียน: factor-designer · วันที่ 2026-10-15 · ชั้น: L1 (ระยะ 1 — อธิบาย · ไม่นับ trial) · สถานะ: **รอรีวิว** (reviewer → ผู้ใช้สั่งรัน)
**แทนที่:** `specs/S001_L1_four_line_competition.md` (ไม่แก้ไฟล์เดิม) · **ตอบรีวิว:** `reviews/S001_spec_review.md` (VERDICT: REVISE · R1–R6 + m1–m5)
อ้างอิง: `BRIEF.md` (ตารางคะแนนกลาง lock · การตัดสินใจผู้ใช้ 2026-10-15 · **ค่าชั่วคราว 16 ข้อ**: L0 ข้อ 1–7 · S001 ข้อ 8–12 · หลังรีวิว ข้อ 13–16) ·
`research/F-R001_literature_4lines_model_tests.md` · `data/QA_L0.md` · `data/manifest.json`
การตรวจโครงข้อมูลของ designer (นับกอง/สัปดาห์เท่านั้น — **ไม่ได้ดูค่าผลตอบแทน ไม่ได้ fit model**): `scratch/factor-designer_s001_structure.py` + `scratch/factor-designer_s002_structure.py`

> ทุกตัวเลขขนาดตัวอย่างในไฟล์นี้มาจากสคริปต์ข้างบน (รันเอง) หรือ `QA_L0.md` / รีวิว S001 (ระบุแหล่ง)
> ผลที่ขึ้นกับค่าชั่วคราวต้องติดป้าย **"ค่าชั่วคราว ข้อ n"** ในรายงานผล: ข้อ 1/3/4/5/7 (panel) · **ข้อ 8 (②c ทั้งหมด)** · **ข้อ 10 (ชุด EVAL)** · ข้อ 11 (③b) · **ข้อ 13 (GRS/|α| ของ ②)** · **ข้อ 14 (PY)** · **ข้อ 15 (ความเสถียร)** · **ข้อ 16 (H1 ของ ②c)**

---

## A. ตารางข้อรีวิว → ส่วนที่แก้

| ข้อรีวิว | ระดับ | แก้ที่ | สาระของการแก้ |
|---|---|---|---|
| R1 MOM ทางสำรอง / ②c ไม่มีกองผ่าน EVAL | ร้ายแรง | 2.1, 2.2, 2.4, 3.② (ตาราง ②), 4.2, 4.4, 5 ข้อ 5, 8 ข้อ 6 | ลบ P0 · **②b = ②a + FXH (K=4)** · **②c = ②b + MOM + SIZE + ACT (K=7)** · train ②c = 2022-01-14 → 2023-12-29 (103 แถว) · ขั้นต่ำ ≥ 78 แถว (ผ่าน 207/207) · H1 ②c = 2022-01-14 → 2023-06-30 (ค่าชั่วคราวข้อ 16) · rolling ②c 26 หน้าต่าง · GRS train T = 103 · รายเดือน ②c = N/A · ป้าย "ไม่เทียบตรง" |
| R2 α ของ ① ไม่ใช่ pricing error · ④a ดูด α ช่วง test | ร้ายแรง | 3.① "factor return", 3.④, 6 test 5/14 | eigen จากข้อมูลหักค่าเฉลี่ย แต่ **factor return = พอร์ตของผลตอบแทนที่ไม่หักค่าเฉลี่ย** ทุกช่วง · ④a: factor = W × (x − β̂'f) **ไม่หัก α̂** |
| R3 สูตร PY | สำคัญ | 4.3, 6 test 10 | f(N) = N · I[√v·\|ρ̂\| > c_p(N)] · ฉบับหลัก = ต้นฉบับ (กองครบทุกแถว: 148 / 206 / ②c 200) · v_i เป็นภาคผนวก · รายงาน ρ̄², (N−1)ρ̄² · test แบบ block |
| R4 GRS ของ ② circular · \|α\| peer-relative · ช่วง test fit ใหม่ไหม | สำคัญ | 4.2 (ข), 4.2 (ค), 5 ข้อ 3 | GRS ของ ② = split-half (ค่าชั่วคราวข้อ 13) · PY เป็นหลักของ ② · signed mean α + ป้าย "peer-relative" · **GRS/PY ช่วง test fit α, β ใหม่ในช่วง test บนอนุกรม factor ที่สร้างด้วยน้ำหนัก/กลุ่มของ train** · Ω̂ = MLE |
| R5 ความเสถียร: noise ปน dof | สำคัญ | 5 ข้อ 5, 7 ข้อ 3 | ชุด STAB = 191 กองทุกรูปแบบ (ค่าชั่วคราวข้อ 15) · แยก factor ร่วม · **แยก noise 2 วิธี**: corr แก้ attenuation (reliability) + เพดานคี่/คู่ |
| R6.1 Onatski ED | สำคัญ | 3.① เกณฑ์จำนวน factor | เขียนขั้นตอน iterative ครบ + ให้ analyst เทียบบทความ |
| R6.2 ภูมิภาค/กองไม่ใช่หุ้น · กฎรวมกลุ่ม | สำคัญ | 3.② "การกำหนดภูมิภาค", 4.2 (ก) | max R² < 0.30 → "อื่น" · **กฎเดียว: กลุ่ม < 10 กอง → "อื่น"** ใช้ทั้ง FXH และ GRS · ไฟล์จัดกลุ่มเขียนก่อน fit |
| R6.3 ใน/นอก sample PCA | สำคัญ | 3.① ท้าย, 5 ข้อ 1–2 | ตัวเทียบหลักของ ① = E นอก sample (67) · F/O = "n ไม่พอ" · ①c = "ไม่มีกลุ่มนอก sample" · ทุกรูปแบบรายงานบน E67 ด้วย |
| R6.4 test statsmodels | สำคัญ | 6 test 1 | `cov_kwds={'maxlags':4,'use_correction':False}` |
| m1 bootstrap CI | เล็กน้อย | 4.4 | 2,000 รอบ · seed 20261015 · CI ของ median และส่วนต่างจับคู่ |
| m2 VIF ③c | เล็กน้อย | 4.4 | VIF ของ ③b/③c (lag 0 และ design เต็ม) เชิงบรรยาย |
| m3 ช่วง test ถูกใช้เลือก | เล็กน้อย | 9 | ข้อจำกัด: L2–L4 ห้ามอ้าง 2024–25 เป็นหลักฐานนอกช่วงอิสระ |
| m4 Dimson ของ factor จากกอง | เล็กน้อย | 4.4 | รายงานสัดส่วนกองที่ \|t(b1)\| > 2 ต่อ factor |
| m5 survivorship จาก ≥ 52 สัปดาห์ test | เล็กน้อย | 9 | ข้อจำกัด (11 กองจบก่อนสิ้น 2025 — QA_L0) |
| หัว spec 7 ข้อ → 16 ข้อ · ย้ายเรื่องที่ตัดสินแล้ว | เล็กน้อย | หัว spec, "ต้องให้ผู้ใช้ตัดสินใจ" | ค่าชั่วคราวข้อ 9–12 ย้ายเป็น "ตัดสินแล้ว" |

**ไม่เปลี่ยนจาก S001:** สมมติฐาน (ยกเว้นถ้อยคำ H②b ให้ตรง ②b ใหม่ — เนื้อหาเดิม) · ข้อมูลและ hash · ช่วงเวลา train/test/H1/H2 · ชุด EVAL/EVAL52/balanced/unbalanced · ③a/③b/③c · จำนวนรูปแบบ **10** · ตารางคะแนนกลาง 6 ข้อ

---

## 0. ข้อเท็จจริงเชิงโครงสร้าง (ตรวจเอง · S001 ข้อ 0 ยังใช้ได้ทั้งหมด · เพิ่มเติมจาก `factor-designer_s002_structure.py`)

| เรื่อง | ค่า | ผลต่อ spec |
|---|---|---|
| สัปดาห์ช่วงหลัก | 260 · train 156 (Dimson 155) · test 104 · H1 130 · H2 130 | เหมือน S001 |
| EVAL (ตัดซ้ำ · ≥104 แถว Dimson train · ≥52 test) | 207 (E175/F18/O14) | ชุดหลักข้อ 1–4 |
| แถวของกอง EVAL ใน 2022-01-14 → 2023-12-29 (train ②c) | min 100 · **≥ 78 ทั้ง 207** · ครบ 103 แถว = 200 (E169/F18/O13) | ②c ใช้ EVAL ทั้ง 207 · PY ②c train = 200 กอง |
| STAB (EVAL ที่ ≥104 แถวทั้ง H1 และ H2) | **191 (E159/F18/O14)** | ชุดข้อ 5 ทุกรูปแบบ |
| แถวของ STAB ใน H1 ของ ②c (2022-01-14 → 2023-06-30) | 74–77 (ทุกกอง ≥ 60) | ②c H1 รันได้ทุกกอง (p = 15 → dof ≥ 59) |
| rolling 104 / step 4 | 40 หน้าต่าง · STAB ทุกกอง ≥ 78 แถวทุกหน้าต่าง · หน้าต่างที่เริ่ม ≥ 2022-01-14 = **26** (แรก = 2022-02-04) | ②c ใช้ 26 หน้าต่าง |
| PY ฉบับต้นฉบับ (EVAL ครบทุกแถว) | train 155 แถว = 148 · test 104 แถว = 206 · ②c train 103 แถว = 200 | N ของ PY หลัก |
| split-half ของฐาน 277 (แบ่งตาม policy · seed 20261015) | A: E119/F11/O8 · B: E119/F12/O8 · กองต่อสัปดาห์ต่ำสุด train: A (E53/F6/**O4**) · B (E61/F10/O6) · test: A (E116/F11/O8) · B (E114/F11/O7) | APB ใน split-half ใช้ min_n = 3 (ไม่ใช่ 5) — ดู 4.2 (ข) |
| EVAL นอก sample ①a/①b (รีวิว S001 — ไม่ได้ตรวจซ้ำเอง) | 75 (E67/F3/O5) | ตัวเทียบหลัก ① = E67 |
| EVAL ⊂ ฐาน ①c (277) | ตามนิยาม (≥104 ≥ 52 แถว train · ตัดซ้ำชุดเดียวกัน) | ①c ไม่มีกลุ่มนอก sample |

---

## 1. สมมติฐาน (ล็อกก่อนรัน · เหมือน S001)

- **H0 (หลัก):** มีชุด factor ≤ 6 ตัว ที่ให้ median adj R² ของกอง E ในช่วง train ≥ 0.60 และ R² นอกช่วง (2024–2025) ลดลงไม่เกิน 0.15 จากในช่วง
- **H①** (F-R001 ①-1): จำนวน factor ตามเกณฑ์รวม (ข้อ 3.①) อยู่ระหว่าง 2–6 · PC1 มี |corr| > 0.8 กับ ACWI(THB)−rf
- **H①b** (F-R001 ①-3): factor ของ ①c กับ ①a มี canonical correlation ทุกคู่ > 0.9 ในช่วง train
- **H②a** (F-R001 ②-1): APB ตาม policy (LOO) ให้ median R² นอกช่วงของกอง E ไม่ต่ำกว่า ③a เกิน 0.05
- **H②b** (F-R001 ②-2): FXH มี corr < −0.5 กับ ΔUSDTHB และ ②b (= ②a + FXH) เพิ่ม median adj R² ของ E ≥ 0.02 เหนือ ②a *(ถ้อยคำปรับให้ตรง ②b ใหม่ — เนื้อหาเดิม เพราะ S001 ก็เทียบ FXH กับ ②a)*
- **H③** (F-R001 ③-1/③-2): ③a อธิบาย E ใกล้ ① (ห่าง median R²_oos ≤ 0.05) · ③b เพิ่ม median R² ของ F ≥ 0.05 จาก bond spread (ตีความคู่กับ bootstrap CI ข้อ 4.4)
- **H④a** (F-R001 ④-1): k_res ≥ 1 · residual PC1 มี |corr| ≥ 0.5 กับ ΔUSDTHB หรือ FXH หรือ MSCI เอเชีย/จีน

เกณฑ์ตัวเลขใน H เป็น**ความคาดหมายที่ใช้ตรวจตัวเองภายหลัง** ไม่ใช่เกณฑ์ผ่านอัตโนมัติ (BRIEF: ผู้ใช้เลือก)

---

## 2. ข้อมูล

### 2.1 ไฟล์ (sha256 จาก `data/manifest.json` · ตรวจก่อนรัน ไม่ตรง → หยุด) — **ลบแถว P0 ของ S001** (ค่าชั่วคราวข้อ 8: ไม่สร้างข้อมูลปี 2020)

| ไฟล์ | ใช้ทำ | sha256 |
|---|---|---|
| `.claude/factor_team/data/panel_weekly.parquet` | ผลตอบแทนกองรายสัปดาห์ (FundCode, date, ret) | `95c16ee651d3a936788b7cb3c6372bbf5f1e84cb39daf5680343771dca24270b` |
| `.claude/factor_team/data/panel_monthly.parquet` | ตรวจซ้ำรายเดือน | `e8e8cb5d5f04fba9bb35558ef7c3d8195c656334119e56f82775cc1ae21ccaed` |
| `.claude/factor_team/data/factors_weekly.parquet` | factor inputs + RF_BOT | `115b87139d2bec0fd57a77a1593c46d36bb23f3f35f83236cdb07be642af47a8` |
| `.claude/factor_team/data/factors_monthly.parquet` | factor รายเดือน | `f7c4248b4fa889853024449e72ae8909cf1f8d3226a54eebc37448a2a485bb72` |
| `.claude/factor_team/data/aum_weekly.parquet` | SIZE (②c) | `48c34c73ae22ebffc6112f93e03f729223a496297bb65c324b693b817a723d26` |
| `.claude/factor_team/data/universe.csv` | policy · included · n_weeks · div_flag | `fdfb7830df78ce032465ac9d8cddc2c98f9aa86cfa0f3925fdb83026aa3f7252` |
| `.claude/factor_team/data/dup_pairs.csv` | กลุ่มกองซ้ำ | `b1f0f0c745947fa70803a4f40526c0a1967c72925be985a2bedc1057d8b8aef3` |
| `.claude/factor_team/data/factor_groups.csv` | ตรวจว่าไม่ใช้ `FRED_spread_NOT_USABLE_MAIN` | `42bf1cfb270721ae6112799ab795ebc4c91212e7584d5cdfee23b9b70b1b1731` |

### 2.2 นิยามตัวแปรและช่วง
- excess return กอง `x_i,t = ret_i,t − RF_BOT_t` · factor ที่เป็นผลตอบแทนบาท `− RF_BOT` · factor ส่วนต่าง (A − B) ไม่หัก rf · `USDTHB` = %Δ (บวก = บาทอ่อน) · `*_d` = Δระดับ
- ห้ามใช้: `*_late_*` · `*_lvl` · `*_est_ret` (ค่าชั่วคราวข้อ 2) · ข้อมูล 2026 (ข้อ 6)
- ช่วง: **train** 2021-01-08 → 2023-12-29 (156; Dimson 155) · **test** 2024-01-05 → 2025-12-26 (104) · **H1** 2021-01-08 → 2023-06-30 · **H2** 2023-07-07 → 2025-12-26
- **ช่วงเฉพาะ ②c (ค่าชั่วคราวข้อ 8, 16):** train_c = 2022-01-14 → 2023-12-29 (103 แถว Dimson · MOM มีค่าครั้งแรก 2022-01-07 จึงเป็น lag ของแถวแรก) · test เหมือนเดิม · H1_c = 2022-01-14 → 2023-06-30 · H2 เหมือนเดิม · ช่วงเต็มสำหรับ rolling/คี่-คู่ = 2022-01-14 → 2025-12-26

### 2.3 ชุดกองต่อวิธี (ค่าชั่วคราวข้อ 4 · ตัดซ้ำ = 1 กองต่อ connected component ของ `dup_pairs.csv` · เก็บ n_weeks มากสุด · เสมอ → FundCode ตามตัวอักษร)

| ใช้ทำ | ชุด | เหตุผล |
|---|---|---|
| สร้าง factor ① / ④ (PCA) | ตัดซ้ำ | กองซ้ำสร้าง eigenvalue ปลอม |
| สร้าง factor ② (EW / long–short) | ตัดซ้ำ (ฐาน 277) | กันกองซ้ำได้น้ำหนักเกิน |
| คะแนนข้อ 1, 2, 3 (\|α\|, BH), 4 | **EVAL 207** (หลัก · ค่าชั่วคราวข้อ 10) · EVAL52 + ชุดเต็มไม่ตัดซ้ำ = ภาคผนวก | — |
| PY หลัก (ข้อ 3) | EVAL ที่ครบทุกแถวในหน้าต่าง: train 148 · test 206 · ②c train 200 (ค่าชั่วคราวข้อ 14) | ต้นฉบับต้องการ T ร่วม |
| คะแนนข้อ 5 | **STAB 191** ทุกรูปแบบ (ค่าชั่วคราวข้อ 15) | กัน dof/ชุดกองต่างกันปนผล |
| พอร์ต GRS | สมาชิกจากฐาน 277 | — |
| class ปันผล 27 กอง | คงไว้ (ข้อ 5) · รายงาน mean\|α̂\| ซ้ำโดยตัด `div_flag` | NAV ไม่รวมปันผล |

### 2.4 missing และขั้นต่ำ
- ผลตอบแทนกอง: ไม่ impute ใน regression (ยกเว้น EM ของ ①c) · factor ภายนอกไม่มี NaN
- factor ที่สร้างจากกอง (EW): ค่าเฉลี่ยของสมาชิกที่มีค่า · สมาชิก (หลัง LOO) < 5 → NaN (split-half: < 3 → NaN · ข้อ 4.2 ข) · แถวที่ factor เป็น NaN ตกจาก regression ของรูปแบบนั้น (รายงานจำนวน)
- factor PCA: projection บนกองที่มีค่า · มี < 50% ของกองใน Λ → NaN
- ขั้นต่ำต่อกอง: EVAL (≥104 train · ≥52 test) · **②c: ≥ 78 แถวใน train_c** (ผ่านทั้ง 207) · STAB ≥ 104 ต่อครึ่ง (②c H1_c: ≥ 60 — ทุกกองผ่าน) · rolling ≥ 78 ใน 104 · รายเดือน train ≥ 24 test ≥ 12

---

## 3. วิธี (**10 รูปแบบ: ① 3 · ② 3 · ③ 3 · ④ 1** — ลองนอกจากนี้ = spec ใหม่)

### กติการ่วม
- regression รายกอง `x_i,t = α_i + Σ_k (b0_ik f_k,t + b1_ik f_k,t−1) + e_i,t` (**Dimson lag 1** · β = b0 + b1 · SE ของ β จาก HAC ของผลรวม)
- **HAC Newey–West Bartlett L = 4** รายสัปดาห์ (floor(4(T/100)^{2/9}) = 4 ที่ T = 103, 104, 155) · รายเดือน L = 3
- p = 2K + 1 · adj R² = 1 − (1−R²)(n−1)/(n−p)
- factor ที่สร้างจากกอง (①②④) ประมาณน้ำหนัก/กลุ่ม**ด้วย train เท่านั้น** แล้วใช้กับผลตอบแทนทุกช่วง (ยกเว้น MOM ที่ rebalance ด้วยข้อมูล ≤ τ)
- **α เป็น pricing error ในทุกสาย (R2):** factor ทุกตัวต้องเป็นผลตอบแทนส่วนเกิน (excess return) หรือส่วนต่างของผลตอบแทนที่**ไม่ได้หักค่าเฉลี่ยของตัวอย่าง** (ยกเว้น factor ที่ลงทุนไม่ได้ของ ③c: VIX_d / US10Y_d / TH5Y_d ตามนิยาม)
- seed: `20261015` (numpy `default_rng`) · การเรียงทุกครั้ง `kind="stable"`

### สาย ① pure stat (F-R001 ①-1/①-2/①-3)

| | ①a correlation-PCA (หลัก) | ①b covariance-PCA (เสริม) | ①c missing-data PCA |
|---|---|---|---|
| sample | balanced train ตัดซ้ำ 134 × 156 | เดียวกับ ①a | unbalanced train ตัดซ้ำ 277 (≥52 สัปดาห์) |
| ข้อมูลสำหรับ **eigen** | z = (x − μ_i)/σ_i (μ,σ ของ train) | d = x − μ_i | z ตามค่าที่มี (μ,σ จากแถวที่มี) |
| k | **k\* = floor(มัธยฐาน{IC_p2, ER, ED, PA})** · kmax 10 · ≥ 1 | = k\* | = k\* |
| ประมาณ Λ | eigenvector k\* ตัวแรกของ Z'Z/T (‖λ‖ = 1) | ของ D'D/T | EM (Stock–Watson): เติม 0 → SVD rank k\* → แทนค่าที่ขาด → วนจน ‖Δ‖_F/‖X_miss‖_F < 1e-6 หรือ 1,000 รอบ · ไม่สุ่ม · ‖λ‖ = 1 |
| **factor return (ทุกช่วง · R2)** | f_t = (Λ_A'Λ_A)⁻¹ Λ_A' (x_A,t / σ_A) | f_t = (Λ_A'Λ_A)⁻¹ Λ_A' x_A,t | f_t = (Λ_A'Λ_A)⁻¹ Λ_A' (x_A,t / σ_A) |

- A = กองใน Λ ที่มีค่าในสัปดาห์ t · σ_A, Λ จาก train เสมอ · **ไม่หัก μ** → f เป็นพอร์ตของผลตอบแทนส่วนเกิน (น้ำหนัก λ_i/σ_i) ค่าเฉลี่ยไม่ถูกบังคับเป็น 0 → α̂ = pricing error เทียบกับพอร์ต PC (แก้ R2 ของ S001 ที่ α̂ = ค่าเฉลี่ยกอง) · R² ไม่เปลี่ยนจาก S001 (ต่างแค่ค่าคงที่)
- เครื่องหมาย: กลับให้ผลรวม Λ ≥ 0
- **เกณฑ์จำนวน factor** (บน Z ของ ①a · eigenvalue λ_1 ≥ … ≥ λ_N ของ Z'Z/T):
  - IC_p2 (Bai–Ng 2002): argmin_k ln V(k) + k·((N+T)/(NT))·ln min(N,T) · รายงาน IC_p1 ด้วย (บรรยาย)
  - ER (Ahn–Horenstein 2013): argmax_{1≤k≤kmax} λ_k/λ_{k+1} · GR บรรยาย
  - **ED (Onatski 2010) — ขั้นตอน (R6.1):** (1) j ← kmax + 1 · (2) OLS ของ (λ_j, …, λ_{j+4}) บนค่าคงที่ และ ((j−1)^{2/3}, …, (j+3)^{2/3}) → slope β̂ · δ ← 2|β̂| · (3) k̂ ← max{ i ≤ kmax : λ_i − λ_{i+1} ≥ δ } (ไม่มี → 0) · (4) j ← k̂ + 1 แล้วกลับไป (2) จน k̂ ไม่เปลี่ยน (สูงสุด 100 รอบ · ไม่ลู่เข้า → รายงาน "ไม่ลู่เข้า" และ ED ไม่ถูกนับในมัธยฐาน) · **ที่มา:** จากความจำของ designer + รีวิว S001 R6.1 — **ยังไม่ยืนยันแหล่ง** → analyst ต้องเทียบกับ Onatski (2010, REStat 92(4)) ส่วน "calibration" ก่อน implement · ต่าง → ยึดบทความ + บันทึกใน `run_log.md`
  - PA (Horn 1965): 500 permutation สลับแต่ละคอลัมน์ของ Z อิสระ · k = จำนวน λ_k จริงที่ > percentile 95 ของ λ_k จาก permutation (นับจาก k = 1 จนตัวแรกที่ไม่ผ่าน)
- บรรยายเพิ่ม (ไม่แข่ง ไม่ใช้เลือก k): median adj R² train และ R²_oos ของ ①a ที่ k = 1…8 แยก E/F/O
- **ใน/นอก sample PCA (R6.3):** ①a/①b รายงานคะแนนข้อ 1–2 แยก "ใน sample" (132) กับ "นอก sample" (E67 / F3 / O5) · **F/O นอก sample = "n ไม่พอ"** · ①c: EVAL ⊂ ฐาน 277 → "ไม่มีกลุ่มนอก sample" · **ตัวเทียบหลักของ ① กับสายอื่นในข้อ 1–2 = กลุ่ม E67** (ทุก 10 รูปแบบรายงานคะแนนข้อ 1–2 บน E67 ชุดเดียวกันด้วย)

### สาย ② Fama-French ของกองทุน (F-R001 ②-1 ถึง ②-5) — **LOO ทุกตัว** (ยกเว้น split-half ข้อ 4.2 ข ที่ใช้กองคนละชุดแทน)

ฐาน = unbalanced train ตัดซ้ำ (277) · คุณลักษณะจาก **train เท่านั้น** ตรึงกลุ่มตลอด test (ยกเว้น MOM) · กองที่ไม่มีข้อมูล train ไม่อยู่ใน factor

**การกำหนดภูมิภาค (R6.2 · ใช้กับ FXH, ACT, พอร์ต GRS · เขียน `runs/S002/regions.csv` ก่อน fit รูปแบบใด):**
1. กอง E/O ทุกกองในฐาน → Dimson regression ทีละดัชนีบน {MSCI_USA, MSCI_EUROPE, MSCI_JAPAN, MSCI_CHINA_ALL_SHARES, MSCI_ASIA_EX_JAPAN, MSCI_INDIA, MSCI_VIETNAM, MSCI_ACWI} (−rf · train)
2. ภูมิภาค = ดัชนีที่ R² สูงสุด (เสมอ → ลำดับในวงเล็บ) · **ถ้า max R² < 0.30 → "อื่น"** (กองที่ไม่ใช่หุ้น เช่น ทอง/REIT/โครงสร้างพื้นฐาน · ค่า 0.30 ล็อกโดย designer — เหตุผล: หุ้นภูมิภาครายสัปดาห์ในบาทควรอธิบายกองหุ้นที่ตรงภูมิภาคได้มากกว่านี้มาก · ผู้ใช้เปลี่ยนได้ก่อนรัน)
3. **กฎรวมกลุ่มเดียว (FXH และ GRS ใช้ร่วมกัน):** นับเฉพาะกอง E ในฐาน · ภูมิภาคที่มี < 10 กอง → รวมเข้า "อื่น" · ถ้า "อื่น" เองมี < 10 กอง → รวม "อื่น" เข้า MSCI_ACWI (ACWI = ภูมิภาค "ทั่วโลก" ที่ใกล้ที่สุดทางความหมาย) · เหตุผลของ 10: FXH ต้องได้ขาละ ≥ 3 กอง (30% ของ 10) และพอร์ต GRS ต้อง ≥ 3 กองต่อสัปดาห์
4. บันทึก: R² ทั้ง 8 ค่า · ภูมิภาคก่อน/หลังรวม · FX beta ต่อกอง

| factor | นิยาม (ทุกตัวเป็นผลตอบแทนส่วนเกินหรือส่วนต่าง ไม่หักค่าเฉลี่ย) |
|---|---|
| APB_E, APB_F, APB_O | EW ของ x ของกองใน policy นั้น · regress กอง i ใน policy g → APB_g ไม่รวม i (LOO) |
| FXH (hedged − unhedged) | กอง E: Dimson `x ~ [R_ภูมิภาค(THB)−rf, USDTHB]` ใน train (กลุ่ม "อื่น" ใช้ MSCI_ACWI) → FX beta = b0+b1 ของ USDTHB · เรียง**ภายในกลุ่มหลังรวม (ข้อ 3)** ที่ 30/40/30 → FXH = EW(FX beta ต่ำ 30%) − EW(สูง 30%) รวมทุกกลุ่ม |
| MOM (52-4) · **②c เท่านั้น** | ทุกสิ้นไตรมาส τ (ศุกร์สุดท้ายของ มี.ค./มิ.ย./ก.ย./ธ.ค.) · กอง E ที่มี ≥ 40 สัปดาห์ใน (τ−52, τ−4] · ผลตอบแทนทบต้น → 30/40/30 → EW(บน) − EW(ล่าง) ถือ τ+1 ถึง τ ถัดไป · ใช้เฉพาะข้อมูล ≤ τ · **ไม่มีข้อมูลก่อน 2021** → τ แรกที่ใช้ได้ = 2021-12-31 (τ = 2021-09-24 มี 34 สัปดาห์ < 40 — รีวิว S001) → MOM มีค่าตั้งแต่ 2022-01-07 · ก่อนหน้านั้น = NaN · ในช่วง test membership ใช้ข้อมูล ≤ τ (รวมผลตอบแทน test ก่อน τ — เป็น point-in-time ไม่ใช่ look-ahead) |
| SIZE (small − big) · ②c | กอง E: มัธยฐาน log AUM ช่วง train (ไม่มี AUM ใน train → ไม่อยู่ในการเรียง) → 30/40/30 → EW(เล็ก) − EW(ใหญ่) |
| ACT (active − passive) · ②c | กอง E: 1 − R² ของ Dimson บนดัชนีภูมิภาคตัวเดียว (ภูมิภาคหลังรวม · "อื่น" ใช้ ACWI · train) → 30/40/30 → EW(1−R² สูง) − EW(ต่ำ) |

- long–short สร้างจากกอง E เท่านั้น · LOO: กอง i ถูกตัดจากทุกขาที่ตนอยู่
- **②a** = {APB_E, APB_F, APB_O} (K = 3) · **②b = ②a + FXH (K = 4)** · **②c = ②b + MOM + SIZE + ACT (K = 7)** (R1 · ค่าชั่วคราวข้อ 8)
- **②c ใช้ train_c (103 แถว) · กองขั้นต่ำ ≥ 78 แถว · ชุดกอง EVAL 207 เดิม** · ทุกที่ที่ ②c อยู่ในตารางคะแนนติดป้าย **"ไม่เทียบตรง (ค่าชั่วคราวข้อ 8)"** · ตัวเทียบจับคู่ (ภาคผนวก · ไม่ใช่รูปแบบใหม่ — นิยามเดิม ช่วงต่าง): ②b และ ③a fit บน train_c ชุดกองเดียวกัน เพื่อวัด incremental R² ของ MOM+SIZE+ACT แบบเทียบตรง
- long–short ระหว่างกองเป็นเชิงอธิบาย (ห้ามสรุปว่าลงทุนได้)

### สาย ③ factor ภายนอก (เหมือน S001)

| รูปแบบ | factor (คอลัมน์ใน `factors_weekly`) | K |
|---|---|---|
| **③a** | MKT = MSCI_ACWI−rf · BOND = AGG_THB−rf · GOLD = Gold_THB−rf · FX = USDTHB | 4 |
| **③b** | ③a + EMDM = MSCI_EM − MSCI_WORLD · USX = MSCI_USA − MSCI_ACWI · TH = TDEX_THB−rf (ค่าชั่วคราวข้อ 7, 11) · TERM = IEF_THB − SHV_THB · IG = LQD_THB − IEF_THB · HY = HYG_THB − LQD_THB · EMD = EMB_THB − IEF_THB | 11 |
| **③c** | ③b + Momentum · Quality · Value · LowVol (de-market) · VIX_d · US10Y_d · Oil_Brent · TH5Y_d (ค่าชั่วคราวข้อ 2) | 19 |

- ③c: VIX_d / US10Y_d / TH5Y_d ลงทุนไม่ได้ → ไม่ใช้ใน spanning · α ของ ③c ไม่ใช่ pricing error เต็มรูป (ติดป้าย) · GRS/PY ยังรายงาน

### สาย ④ factor ใหม่ (F-R001 ④-1)
- **④a = ③a + residual PC** · กอง balanced train ตัดซ้ำ (134) → Dimson regression บน ③a (train) → ê_i,t = x − α̂ − β̂'f (train) → s_i = sd(ê_i) · W = eigenvector ของ correlation ของ ê · **k_res = IC_p2 บน ê/s, kmax = 5** (0 → ④a = ③a + รายงาน "ไม่มี residual factor")
- **factor return ทุกช่วง (R2):** u_i,t = x_i,t − Σ_k (b̂0_ik f_k,t + b̂1_ik f_k,t−1) (β̂ จาก train · **ไม่หัก α̂**) → g_t = (W_A'W_A)⁻¹ W_A' (u_A,t / s_A) · ใช้สูตรเดียวทั้ง train และ test → g เป็นพอร์ตของกองที่ hedge ③a ออกแล้ว ค่าเฉลี่ยไม่ถูกบังคับ → residual PC ไม่ดูด α ของช่วง test (แก้ R2 ของ S001)
- เกณฑ์บรรยาย Harvey–Liu–Zhu: residual PC "มีนัย" เมื่อ |t_HAC| > 3 ใน ≥ 10% ของกอง EVAL
- **④b ตัดออกจาก L1 → L4 (ตัดสินแล้ว · ค่าชั่วคราวข้อ 9)** · ④-2 ไม่ทำแยก (panel FIF ทั้งหมด · TH อยู่ใน ③b)

---

## 4. การทดสอบ

### 4.1 regression รายกอง (10 รูปแบบ · EVAL + EVAL52 + ชุดเต็ม (ภาคผนวก) + E67)
- train (②c: train_c): α̂, β̂ (Dimson), t_HAC, adj R², BIC ต่อกอง
- test: ŷ = α̂^train + Σ(b̂0 f_t + b̂1 f_t−1) · f ของ test ตามข้อ 3 (ไม่ fit ใหม่) · **R²_oos,i = 1 − Σ(x−ŷ)²/Σ(x − x̄_i^test)²** (ติดลบได้)

### 4.2 GRS (Gibbons–Ross–Shanken 1989)

**(ก) พอร์ต (≤ 20 · จาก train เท่านั้น · เขียน `runs/S002/grs_ports.csv` ก่อน fit รูปแบบใด):**
- E: กลุ่มภูมิภาคหลังรวม (ข้อ 3.② กฎเดียวกับ FXH) · กลุ่มที่มี ≥ 20 กอง → แบ่งครึ่งตามมัธยฐาน FX beta (hedge / ไม่ hedge) · ถ้ารวมแล้ว > 20 พอร์ต → ยกเลิกการแบ่งของกลุ่มที่เล็กที่สุดทีละกลุ่มจน ≤ 20
- F: 2 พอร์ตตามมัธยฐาน σ ผลตอบแทน train · O: 2 พอร์ตแบบเดียวกัน
- สมาชิก = ฐาน 277 · พอร์ต = EW ของสมาชิกที่มีค่า (≥ 3 กองต่อสัปดาห์ ไม่งั้นตัดสัปดาห์นั้นทั้งระบบ — รายงานจำนวน)
- สูตร: GRS = ((T−N−L)/N)·α̂'Σ̂⁻¹α̂/(1 + μ̄'Ω̂⁻¹μ̄) ~ F(N, T−N−L) · L = 2K · Σ̂ dof T−L−1 · **Ω̂ = covariance แบบ MLE (หาร T) ของ regressor ทั้ง 2K ตัว** · μ̄ = ค่าเฉลี่ย regressor
- **การ fit ในแต่ละช่วง (R4):** GRS (และ PY) ของช่วงใด → **fit α, β ใหม่ด้วยข้อมูลของช่วงนั้น** โดยใช้อนุกรม factor ที่สร้างด้วยน้ำหนัก/กลุ่มของ train (ช่วง test: factor OOS ตามข้อ 3 · ไม่ใช่ α̂ ของ train) — คือคำถาม "factor ชุดนี้ price พอร์ตในช่วงนั้นได้ไหม"
- ช่วง: **test หลัก (T = 104)** · train รอง (T = 155 · ②c T = 103) · รายงาน F, p, N, L, T−N−L, mean|α̂| พอร์ต (%/ปี ×52)
- ③c test: T−N−L = 104 − 20 − 38 = 46 → รันได้ · power ต่ำ (ข้อจำกัด)

**(ข) สาย ② = split-half (ค่าชั่วคราวข้อ 13 · R4):**
- แบ่งฐาน 277 เป็นครึ่ง A/B **แยกตาม policy**: แต่ละ policy (ลำดับ E, F, O) เรียง FundCode → `default_rng(20261015).permutation` (generator เดียวต่อเนื่องทั้ง 3 policy) → floor(n/2) ตัวแรกของ permutation = A · ที่เหลือ = B (ได้ A: E119/F11/O8 · B: E119/F12/O8) · เขียน `runs/S002/halves.csv`
- ทิศ A→B: factor ② ทุกตัว (APB, FXH, MOM, SIZE, ACT) สร้างจากกองครึ่ง A เท่านั้น ตามนิยามข้อ 3.② (ภูมิภาค / FX beta / คุณลักษณะรายกองใช้ค่าเดิมของกองนั้น · เกณฑ์กลุ่ม < 10 นับในครึ่ง A) · **ไม่ทำ LOO** (กองคนละชุด) · **min_n = 3** ต่อ APB/ขา (ครึ่ง A มี O ต่ำสุด 4 กองต่อสัปดาห์ใน train — ข้อ 0) · พอร์ต GRS สร้างจากกองครึ่ง B ด้วยกติกา (ก) (เกณฑ์นับในครึ่ง B) · ทิศ B→A สลับกัน
- รายงาน GRS ทั้งสองทิศ (train + test) แยกกัน · **ไม่รวมเป็นค่าเดียว** · เรียงลำดับสาย ② ด้วย PY (ข้อ 4.3) เป็นหลัก · GRS split-half เป็นตัวรอง
- เพื่อเทียบกับสายอื่นบนพอร์ตชุดเดียวกัน: **รายงาน GRS ของอีก 7 รูปแบบ (①③④) บนพอร์ตครึ่ง A และครึ่ง B ด้วย** (ภาคผนวก · ①/④ ใช้ factor เดิมที่สร้างจาก sample PCA ของตน — ติดป้ายว่า sample PCA ซ้อนกับพอร์ต)

**(ค) |α| ของ ② (R4):** รายงาน mean|α̂| **และ signed mean α̂** ติดป้าย **"peer-relative — เทียบกับสายอื่นตรงๆ ไม่ได้"** (APB เป็นค่าเฉลี่ยกองชุดเดียวกัน)

### 4.3 Pesaran–Yamagata (2024) — ฉบับหลัก = ต้นฉบับ (ค่าชั่วคราวข้อ 14 · R3)
- ชุด: EVAL ที่ครบทุกแถวในหน้าต่าง (train N = 148, T = 155 · test N = 206, T = 104 · ②c train N = 200, T = 103) · fit ใหม่ในหน้าต่างนั้น (ข้อ 4.2 ก) · m = 2K regressor · **v = T − m − 1** (ต้อง > 4)
- t_i = t-stat ของ α̂_i แบบ OLS (หลัก ตามบทความ) · HAC = sensitivity · สาย ②: t_i จาก factor LOO ของกอง i
- ρ̂_ij = correlation ของ residual OLS ของกอง i, j (T แถวร่วม) · **c_p(N) = Φ⁻¹(1 − p/(2f(N))) · f(N) = N** (δ = 1 ตามต้นฉบับ) · p = 0.10
- ρ̄²_N = [2/(N(N−1))] Σ_{i<j} ρ̂_ij² · I[ **√v · |ρ̂_ij| > c_p(N)** ]
- J_α = N^{-1/2} Σ_i [t_i² − v/(v−2)] / sqrt( 2·((v−1)/(v−4))·(v/(v−2))²·(1 + (N−1)ρ̄²_N) ) · p-value ข้างเดียว N(0,1) (ปฏิเสธเมื่อ J_α ใหญ่)
- รายงาน J_α, p, N, T, v, **ρ̄²_N, (N−1)ρ̄²_N** · ถ้า (N−1)ρ̄²_N > 1 → เขียนกำกับ "เงื่อนไข cross-correlation อ่อนน่าจะไม่เป็นจริง — ตีความ PY ระวัง"
- แยก ALL / E (F, O = รายงานพร้อมคำเตือน n เล็ก)
- **analyst ต้องเทียบสมการ (42)–(46) และ (61)–(64) ของบทความก่อน implement** (รีวิว S001 ประกอบสูตรจากข้อความที่ไม่มีเครื่องหมายราก — ยังไม่ยืนยันทุกตัวอักษร) · ต่าง → ยึดบทความ + บันทึก `run_log.md`
- **ภาคผนวก (sensitivity):** ฉบับขยาย v_i = T_i − m − 1 บน EVAL ทั้งหมด · ρ จากคู่ที่ทับกัน ≥ 52 สัปดาห์ (ไม่มีทฤษฎีรองรับ — ติดป้าย)

### 4.4 ตัวเสริม (ไม่อยู่ในตารางคะแนนกลาง · ไม่ใช้ตัดสิน)
- **BH (FDR 10%)** ของ α รายกอง (t_HAC · train) → จำนวนกอง α ≠ 0 แยก E/F/O
- **Spanning / Barillas–Shanken** เฉพาะ ①a, ②a, ③a, ④a (ล็อก): factor ของ A ~ factor ของ B (Dimson · HAC · test) → α, R², Wald joint α = 0 · ②a ใน spanning ใช้ APB แบบไม่ LOO (factor ชุดเดียว) — ติดป้าย
- **lead diagnostic ครั้งเดียว:** ③a + lead 1 (train) → % กอง EVAL ที่ |t_lead| > 2
- **Dimson ของ factor จากกอง (m4):** ต่อรูปแบบและ factor → สัดส่วนกอง EVAL ที่ |t_HAC(b1)| > 2 (train) · แยกสาย
- **residual correlation ภายใน policy:** mean |corr(ê_i, ê_j)| ภายใน E/F/O (train)
- **H①b:** canonical correlations ระหว่าง factor ①c กับ ①a (train)
- **bootstrap CI (m1):** สุ่มกองใหม่แบบใส่คืน**ภายใน policy** 2,000 รอบ · `default_rng(20261015)` · percentile 95% ของ (1) median adj R² train (2) median R²_oos (3) ส่วนต่างจับคู่ median R²_oos(รูปแบบ) − median R²_oos(③a) บนกองชุดเดียวกันในรอบเดียวกัน · แยก E/F/O/ALL · ทุก 10 รูปแบบ (②c บน EVAL เดียวกัน · ป้าย "ไม่เทียบตรง")
- **VIF (m2):** VIF ของ factor ③b และ ③c ช่วง train — (i) lag 0 อย่างเดียว (11 / 19 ตัว) (ii) design Dimson เต็ม (22 / 38) · เชิงบรรยาย (ป้อน L3) · ไม่ตัด factor
- **ตรวจซ้ำรายเดือน:** คะแนนข้อ 1–2 ด้วยรายเดือน (Dimson lag 1 เดือน · HAC L = 3) · ①: f = Λ'(x/σ_m) (σ_m รายเดือนของ train · ไม่หักค่าเฉลี่ย) · ②a/②b: EW รายเดือนของกลุ่มเดิม (APB LOO · FXH ขาเดิม) · ④a: β̂ รายเดือนของ ③a (train) → u = x − β̂'f → g = W'(u/s_m) · รายงานเฉพาะรูปแบบที่ p ≤ 17 · **②c = N/A** (train_c รายเดือน ≈ 23 เดือน · p = 15 · และ MOM รายไตรมาสไม่ได้นิยามรายเดือน) · ③c = N/A (p = 39)

---

## 5. ตารางคะแนนที่รายงาน (ตารางกลางของ BRIEF ครบ 6 ข้อ · แยก E / F / O / ALL พร้อม n)

| ข้อ | ตัวชี้ | นิยามที่ล็อก |
|---|---|---|
| 1 R² รายกอง | median, IQR ของ adj R² + bootstrap CI | train (②c: train_c) · EVAL หลัก · EVAL52 + ชุดเต็ม ภาคผนวก · **E67 (ตัวเทียบ ①)** · ① แยกใน/นอก sample |
| 2 R² นอกช่วง | median, IQR ของ R²_oos · median(R²_train − R²_oos) + CI | ข้อ 4.1 · test 2024–2025 · factor/loading จาก train · E67 ด้วย |
| 3 pricing error | mean\|α̂\| (%/ปี · train) ทุกสาย (② + signed mean · ป้าย peer-relative) · GRS F/p (test หลัก · train รอง · ②: split-half 2 ทิศ) · **PY J_α/p (หลักของ ②)** · ρ̄², (N−1)ρ̄² | 4.2–4.3 · mean\|α̂\| ซ้ำโดยตัด class ปันผล · ③c ป้าย "มี factor ลงทุนไม่ได้" |
| 4 ความประหยัด | K · p = 2K+1 · median BIC_i · median ΔBIC_i เทียบ ③a | BIC_i = n_i ln(SSR_i/n_i) + p ln n_i (train · EVAL) · ②c เทียบ ③a บน train_c (ภาคผนวกข้อ 3.②) |
| 5 ความเสถียร | ดูด้านล่าง | **ชุด STAB 191 ทุกรูปแบบ** · อนุกรม factor ฉบับน้ำหนัก train |
| 6 ตีความได้ | ต่อ factor: 3 อันดับ \|corr\| สูงสุดกับชุดอ้างอิง I (MSCI 28 −rf · style 4 · Gold_THB, AGG/IEF/SHV/LQD/HYG/EMB_THB −rf · USDTHB · TDEX−rf · Oil · VIX_d · US10Y_d · TH5Y_d · DTB3_d) ช่วงหลัก (②c MOM: ช่วงที่มีค่า) · R² ของ factor ~ ③b · ชื่อ: ≥ 0.7 "≈ ชื่ออนุกรม" · 0.5–0.7 "คล้าย …" · < 0.5 "ไม่มีชื่อ" | สาย ③ ตีความได้ตามนิยาม (รายงาน corr ภายในชุด) |

**ข้อ 5 ความเสถียร (R5 · ค่าชั่วคราวข้อ 15, 16):**
- (ก) **H1/H2:** fit แยก H1 และ H2 (②c: H1_c / H2) → ต่อ factor k: r_k = corr ข้ามกอง (STAB) ของ β̂_ik ระหว่างสองครึ่ง · รายงานต่อ factor + ค่าเฉลี่ยทุก factor + **แยก factor ร่วม** (①: PC1 · ②: APB_E · ③/④: MKT)
- (ข) **แยก noise ออกจากการเปลี่ยนจริง — 2 วิธี:**
  - (ข1) **corr แก้ attenuation:** rel_h,k = (var_i(β̂_ik,h) − mean_i(SE²_ik,h)) / var_i(β̂_ik,h) (SE จาก HAC ของ b0+b1) · r\*_k = r_k / sqrt(rel_H1,k · rel_H2,k) · ถ้า rel ใดน้อยกว่า 0.10 → r\* = "N/A (noise ครอบงำ)" · r\* อาจเกิน 1 — รายงานตามจริง ไม่ตัด
  - (ข2) **เพดานภายใต้ β คงที่:** แบ่งสัปดาห์ช่วงหลักทั้งหมด (②c: 2022-01-14 → 2025-12-26) เป็นสัปดาห์ลำดับคี่ / คู่ (แต่ละชุด ≈ จำนวนแถวเท่า H1/H2 · แถวยังใช้ lag ของสัปดาห์ก่อนหน้าจริง) → fit แยก → r^ceil_k = corr ข้ามกองของ β̂ คี่ vs คู่ · รายงาน r_k / r^ceil_k (≈ 1 = ความไม่เสถียรมาจาก noise · ≪ 1 = exposure เปลี่ยนจริง)
- (ค) **rolling:** หน้าต่าง 104 สัปดาห์ เลื่อนทีละ 4 (40 หน้าต่าง · **②c: 26 หน้าต่างที่เริ่ม ≥ 2022-01-14**) · กอง STAB ที่ ≥ 78 แถวในหน้าต่าง · corr ข้ามกองของ β ในหน้าต่างกับ β ทั้งช่วงหลัก (②c: 2022-01-14 → 2025-12-26) → มัธยฐาน และ ค่าต่ำสุด ต่อ factor

ตัวเพิ่มของชั้นนี้: k ทุกเกณฑ์ + เส้น R² k = 1…8 · H①b · spanning · BH · lead · Dimson b1 · residual corr · bootstrap CI · VIF · รายเดือน · GRS split-half + GRS ทุกรูปแบบบนพอร์ตครึ่ง A/B

ไฟล์ผล `runs/S002/`: `scorecard.csv` (1 แถว/รูปแบบ × policy × ชุดกอง) · `fund_level.csv` · `factors_S002_weekly.parquet` · `nfactors.csv` · `regions.csv` · `grs_ports.csv` · `halves.csv` · `grs.csv` · `grs_split.csv` · `py.csv` · `stability.csv` · `bootstrap.csv` · `vif.csv` · `interpret.csv` · `spanning.csv` · `run_log.md` · `run_meta.json` (sha256 ข้อมูลตาม manifest + sha256 ทุกไฟล์ใน `lib/` + เวอร์ชันแพ็กเกจ)
**ลำดับเขียนไฟล์ (บังคับ):** `regions.csv` → `grs_ports.csv` → `halves.csv` → (เริ่ม fit รูปแบบ) — บันทึก timestamp ใน `run_log.md`

---

## 6. โมดูลใน `.claude/factor_team/lib/` (analyst เขียน · ทุกฟังก์ชันมี test)

| โมดูล | ฟังก์ชัน (input → output) |
|---|---|
| `io_l1.py` | `verify_manifest(paths)` · `load_returns(freq)` (excess) · `load_factors(freq)` · `lib_hash()` |
| `samples.py` | `dedup_keep(dup_pairs, n_weeks)` · `window_mask(index, name)` (train / test / H1 / H2 / train_c / H1_c / full_c / odd / even) · `eligible(R, rules)` (EVAL, EVAL52, balanced, unbalanced, STAB, E67, PY_complete) · `split_halves(base, policy, seed)` |
| `regress.py` | `dimson_design(F, lags=1)` · `ols_hac(y, X, L=4)` · `fit_funds(R, F, mask, min_obs)` · `predict_oos(coef, F_test)` · `r2_oos(y, yhat)` |
| `nfactors.py` | `bai_ng_ic` · `ahn_horenstein` · `onatski_ed(eig, kmax, maxit=100)` (ขั้นตอนข้อ 3.①) · `parallel_analysis(Z, n_perm=500, q=0.95, seed)` · `combine_k(ks)` |
| `pca.py` | `pca_fit(X, k, kind)` → (Λ, μ, σ, eig) · `em_pca(X, k, tol, maxit)` · `factor_returns(X_raw, Λ, σ=None, min_frac=0.5)` (**ไม่หัก μ**) · `sign_fix(Λ)` |
| `fundff.py` | `assign_region(R, idx, mask, r2_min=0.30, min_group=10)` · `fx_beta(...)` · `sort_legs(char, groups, q=(.3,.7))` · `ew_factor(R, members, exclude=None, min_n=5)` · `apb(R, policy, loo)` · `momentum(R, form=52, skip=4, min_obs=40, rebalance='Q')` · `build_line2(R, members, variant, loo, min_n)` (ใช้ทั้ง LOO และ split-half) |
| `external.py` | `line3(F, variant)` |
| `hybrid.py` | `residual_pc(R, F3a, mask, kmax=5)` → (W, s, β̂, k_res) · `hybrid_factor(R, F3a, W, s, β̂)` (**ไม่หัก α̂**) |
| `tests_stat.py` | `grs(R_port, X)` (Ω̂ MLE) · `pesaran_yamagata(t, resid, T, m, p=0.10, f='N')` → dict(J, p, rho2, Nrho2) · `py_extended(...)` · `bh(pvals, q)` · `spanning(fA, fB, L)` · `vif(X)` · `bootstrap_median(...)` |
| `scorecard.py` | `score_model(...)` · `stability_halves(...)` · `stability_disattenuated(beta1, se1, beta2, se2, rel_min=0.10)` · `stability_ceiling(odd/even)` · `stability_rolling(win=104, step=4, min_obs=78, start_min=None)` · `interpret(fac, ref_set)` |
| `run_s002.py` | สคริปต์รันเดียวจบ → `runs/S002/` |

### test ที่ต้องผ่านก่อนรัน (`pytest -p no:cacheprovider .claude/factor_team/lib/tests/`)
1. `ols_hac` ตรงกับ statsmodels `OLS(...).fit(cov_type='HAC', cov_kwds={'maxlags':4,'use_correction':False})` ที่ 1e-8 (R6.4)
2. `dimson_design`: lag ถูกตำแหน่ง · แถวแรก train ตก · แถวแรก test ใช้ lag จาก train · แถวแรกของ train_c ใช้ lag MOM ของ 2022-01-07
3. `nfactors`: ข้อมูลจำลอง N=134, T=156, k จริง = 3, SNR ปานกลาง → IC_p2, ER, PA, ED ได้ 3 · `combine_k([2,3,4,6]) = 3` · `onatski_ed` deterministic และหยุดภายใน maxit
4. `em_pca`: k=3 ขาดสุ่ม 30% → canonical corr กับของจริง > 0.95 · deterministic
5. `factor_returns`: กองครบ → = Λ'(x/σ) **(ไม่หัก μ)** · ตัดกองครึ่งหนึ่งจาก model ที่ไม่มี noise → factor เดิม · ค่าเฉลี่ยของ f ใน train ≠ 0 เมื่อข้อมูลจำลองมีค่าเฉลี่ย ≠ 0
6. `apb` / `ew_factor`: LOO ไม่รวมกองตัวเอง · min_n → NaN
7. **no look-ahead:** แก้ผลตอบแทนหลัง τ → membership MOM ที่ τ, ภูมิภาค, FX beta, Λ, W, β̂ train, `grs_ports`, `halves` ไม่เปลี่ยน
8. `predict_oos` ไม่ fit ใหม่ (coef = coef train ทุกบิต)
9. `grs`: ตรงสูตรปิด (Ω̂ หาร T) กับตัวอย่างคำนวณมือ · simulation 1,000 รอบใต้ H0 (N=20, T=104, L=8) → อัตราปฏิเสธ 5% ใน [3.5%, 6.5%]
10. `pesaran_yamagata` (R3): (ก) error อิสระ N=200, T=104 → อัตราปฏิเสธ 5% ใน [3%, 8%] (ข) **error สัมพันธ์แบบ block** (บล็อกละ 5 กอง corr ภายในบล็อก 0.5 · ข้ามบล็อก 0) → ใน [2%, 10%] (ค) c_p ใช้ f(N) = N และ √v · ผ่านไม่ได้ → หยุดแล้วรายงาน (ไม่แก้ spec ระหว่างรัน)
11. `bh` ตรงกับ `statsmodels.stats.multitest.multipletests(method='fdr_bh')`
12. `verify_manifest` raise เมื่อแก้ไฟล์ 1 byte · `run_s002.py` รัน 2 รอบได้ไฟล์ผล sha256 เท่ากัน
13. ไม่มี `*_late*`, `*_lvl`, `*_est_ret` หรือวันที่ ≥ 2026-01-01 ใน regression
14. **α เป็น pricing error (R2):** ข้อมูลจำลอง x = B·F + e (F มีค่าเฉลี่ย ≠ 0, α จริง = 0) → ①a/①b/①c และ ④a ให้ mean|α̂| ≈ 0 (ไม่ใช่ ≈ ค่าเฉลี่ย x) · ④a: บวก α จริงให้กองในช่วง test → α̂ ของ GRS test ยังจับได้ (residual PC ไม่ดูด)
15. `split_halves`: A ∩ B = ∅ · A ∪ B = ฐาน 277 · ขนาดตรงข้อ 0 · deterministic · factor ทิศ A→B ไม่เปลี่ยนเมื่อแก้ผลตอบแทนกองใน B
16. `assign_region`: กองจำลองที่ max R² < 0.30 → "อื่น" · กลุ่ม < 10 → "อื่น" · "อื่น" < 10 → ACWI · ใช้ label ชุดเดียวกันใน FXH และ GRS
17. `stability_disattenuated`: β จริงคงที่ + noise รู้ค่า → r\* ≈ 1 · rel < 0.10 → N/A

---

## 7. เกณฑ์ผ่าน/ไม่ผ่าน (ข้อเสนอของ designer · **ผู้ใช้เลือกที่ gate L1** · ค่าชั่วคราวข้อ 12)

**technical validity:** test 17 ข้อผ่าน · hash ตรง · รันซ้ำตรงทุกบิต · ไฟล์จัดกลุ่มเขียนก่อน fit · ไม่มีรูปแบบที่ fit ไม่ได้ (ถ้ามี → รายงาน ไม่แก้ spec)

**ข้อเสนอเกณฑ์ "ผู้เข้ารอบ" ไป L2** (ทุกข้อ · กอง E เป็นหลัก):
1. median R²_oos (E · EVAL) ≥ 0.9 × ค่าสูงสุดในบรรดา 10 รูปแบบ (②c ใช้ค่าของตัวเองพร้อมป้าย "ไม่เทียบตรง")
2. median(R²_train − R²_oos) (E) ≤ 0.15
3. **ความเสถียร: ค่าเฉลี่ย r\* (แก้ attenuation) ระหว่าง H1/H2 ≥ 0.6** — *เปลี่ยนจาก S001 (r ดิบ) เพราะรีวิว R5: r ดิบลงโทษรูปแบบที่ p ใหญ่จาก noise ไม่ใช่จาก exposure เปลี่ยน · r ดิบและ r/r^ceil ยังรายงาน* · ถ้า factor ใดเป็น N/A → ใช้ค่าเฉลี่ยของที่เหลือ + ระบุ
4. ΔBIC median ≤ 0 เทียบรูปแบบที่เล็กกว่าในสายเดียวกัน
5. factor ทุกตัวได้ชื่อ (max |corr| ≥ 0.5) หรือเป็นนิยามตรง (สาย ②/③)
- GRS / PY ใช้เรียงลำดับและบรรยาย ไม่ใช้ตัดออก · ไม่มีรูปแบบใดผ่าน → รายงาน "ไม่มีชุดที่ผ่าน" + เหตุผล
- เกณฑ์นี้ห้ามแก้หลังเห็นผลเพื่อเข้าข้างรูปแบบใด

---

## 8. ผลลัพธ์ที่คาดไว้ล่วงหน้า (เขียนก่อนเห็นผล · คงจาก S001 · ข้อที่ปรับระบุเหตุผล)

1. k\* ของ ①a = 3–5 · ER มักให้ 1 · PA ให้มากสุด · PC1 ≈ ตลาดหุ้นโลก (|corr| > 0.8 กับ MSCI_ACWI−rf) · PC2/3 ≈ ภูมิภาค (จีน/เอเชีย vs สหรัฐฯ) หรือ บอนด์/ค่าเงิน
2. median adj R² train (E): ① ≈ 0.70–0.85 > ③b ≈ 0.65–0.80 > ③a ≈ 0.55–0.75 · ②a ≈ ③a · ส่วนต่าง ①−③ ใน R²_oos แคบกว่าใน train
3. กอง F: R² ต่ำทุกรูปแบบ (median 0.2–0.5) · ③b ดีขึ้นจาก ③a ชัดที่สุด · APB_F ช่วย F มากกว่า ③a
4. กอง O: อยู่ระหว่าง E กับ F
5. ③c train R² สูงสุดในสาย ③ แต่ BIC แย่กว่า ③b และ R²_oos ไม่ดีกว่า ③b
6. **(ปรับ — เพราะนิยาม ②b/②c เปลี่ยนตาม R1)** ②b: FXH มี corr ติดลบกับ USDTHB ชัด · ②c เทียบ ②b บน train_c ชุดเดียวกัน: MOM + SIZE + ACT รวมกันเพิ่ม median adj R² (E) < 0.01 (เดิม: SIZE/ACT < 0.01 · MOM เพิ่มน้อย — สาระเดิม เปลี่ยนแค่ว่าวัดเป็นกลุ่มบน train_c)
7. **(ปรับ — เพราะตัวเทียบนอก sample เปลี่ยนตาม R6.3)** ①c ≈ ①a (canonical corr > 0.9) · ①a: กองใน sample PCA มี R² สูงกว่ากอง E67 นอก sample ≈ 0.02–0.05 · ①c ไม่มีกลุ่มนอก sample
8. ④a: k_res = 1–3 · residual PC1 สัมพันธ์กับจีน/เอเชีย หรือ hedge
9. **(ปรับ — เพราะนิยาม α ของ ①/④a และวิธี GRS/PY ของ ② เปลี่ยนตาม R2–R4)** GRS (test) ปฏิเสธ α = 0 ที่ 5% ในเกือบทุกรูปแบบ รวม ④a (เมื่อ residual PC ไม่ดูด α แล้ว) และ ② split-half ทั้งสองทิศ · PY (f(N) = N) ปฏิเสธเช่นกัน · (N−1)ρ̄² > 1 ในรูปแบบที่ K เล็ก (③a, ②a)
10. **(ปรับ — เพราะชุดกองและการแยก noise เปลี่ยนตาม R5)** บนชุด STAB 191: β ของ factor ร่วม (MKT / PC1 / APB_E) r ดิบ H1–H2 > 0.8 · long–short (FXH, MOM, SIZE, ACT) r ดิบ < 0.5 · r\* > r ดิบ ทุก factor และส่วนต่างมากสุดในรูปแบบ p ใหญ่ (③c, ②c)
11. lead diagnostic: < 10% ของกองมี |t_lead| > 2 (ถ้ามากกว่า = การจัดสัปดาห์มีปัญหา → แจ้ง data-engineer)

---

## 9. ข้อจำกัด (ติดไปกับรายงานผล)
- FundProfile เป็น snapshot · class ปันผล 27 กองไม่รวมปันผล · spike F 119 จุดยังไม่แก้ (ค่าชั่วคราวข้อ 3) · ETF/MSCI ปิดคนละเวลา · TDEX = SET50 สภาพคล่องต่ำ
- balanced sub-panel มี survivorship (กองอายุยาว) — ①c / EVAL52 ใช้เทียบ
- **survivorship เบาจากเงื่อนไข EVAL ≥ 52 สัปดาห์ใน test (m5):** กองที่เลิกก่อนกลางปี 2025 หลุดจากชุดประเมิน (QA_L0: 11 กองใน panel จบก่อน 2025-12-31 — ไม่ได้ตรวจซ้ำเองว่ากี่กองหลุด EVAL)
- **ช่วง test 2024–2025 ถูกใช้เลือกรูปแบบแล้ว (m3)** ผ่านเกณฑ์ผู้เข้ารอบข้อ 1–2 → ชั้น L2–L4 ห้ามอ้างช่วงนี้เป็นหลักฐานนอกช่วงที่เป็นอิสระ · ไม่มี holdout อื่น (NAV 2026 มีรู)
- F (18) และ O (14) ใน EVAL เล็ก → ใช้ bootstrap CI ประกอบ · PY/GRS แยก F/O power ต่ำ
- กลุ่มภูมิภาคมาจาก R² ช่วง train (ไม่ใช่ประกาศของกอง) · เกณฑ์ 0.30 และ 10 กองตั้งโดย designer
- ②c ใช้ train สั้นกว่า (103 แถว · ค่าชั่วคราวข้อ 8) → "ไม่เทียบตรง" กับรูปแบบอื่น · MOM ในช่วง test ใช้ข้อมูล test ก่อน τ (point-in-time)
- GRS ของ ② = split-half ใช้พอร์ตครึ่งเดียว (N เล็กลง power ต่ำลง) · |α| ของ ② peer-relative (ค่าชั่วคราวข้อ 13)
- PY ฉบับหลักใช้เฉพาะกองที่ครบทุกแถว (148/206/200) → อาจเอียงไปทางกองอายุยาว (ค่าชั่วคราวข้อ 14)
- ③c มี factor ลงทุนไม่ได้ 3 ตัว → α ไม่ใช่ pricing error เต็มรูป · collinearity (ดู VIF)
- Dimson lag ของ factor ที่สร้างจากกองไม่มีเหตุผลเรื่องเวลา (NAV ออกพร้อมกัน) — ทำตาม BRIEF · ดูสัดส่วน b1 มีนัย (4.4)

---

## ตัดสินแล้ว (ย้ายจาก "ต้องให้ผู้ใช้ตัดสินใจ" ของ S001)
- ข้อมูลก่อน 2021 สำหรับ MOM → ไม่สร้าง · ใช้ทางสำรอง (ค่าชั่วคราวข้อ 8) · ④b → L4 (ข้อ 9) · EVAL ≥104/≥52 หลัก (ข้อ 10) · คง TDEX ใน ③b (ข้อ 11) · เกณฑ์ผู้เข้ารอบเป็นข้อเสนอ ผู้ใช้เลือกที่ gate L1 (ข้อ 12)
- ข้อตัดสินใจ 4 ข้อในรีวิว S001 → GRS ② split-half (ข้อ 13) · PY ต้นฉบับ (ข้อ 14) · STAB 191 (ข้อ 15) · H1 ②c = 2022-01-14 → 2023-06-30 (ข้อ 16)

## ต้องให้ผู้ใช้ตัดสินใจ
1. **ค่าชั่วคราว 16 ข้อ** ยังรอยืนยันตอนจบ L1 (BRIEF) — ผลที่ขึ้นกับแต่ละข้อติดป้ายตามหัว spec
2. **เกณฑ์ภูมิภาคที่ designer ตั้ง** (max R² < 0.30 → "อื่น" · กลุ่ม < 10 กอง → "อื่น") — เปลี่ยนได้ก่อนรันเท่านั้น
3. **เกณฑ์ผู้เข้ารอบข้อ 3 เปลี่ยนเป็น r\* (แก้ attenuation)** แทน r ดิบของ S001 — ยืนยันหรือให้ใช้ r ดิบตามเดิม (ตัดสินที่ gate L1 แต่ห้ามเปลี่ยนเพราะเห็นผล)
4. ตัวเทียบจับคู่ของ ②c (②b และ ③a บน train_c · ภาคผนวก) — ถ้าผู้ใช้ถือว่าเป็นการ "ลองเพิ่ม" ให้ตัดออก (designer เห็นว่าไม่ใช่รูปแบบใหม่ เพราะนิยามเดิม ต่างแค่ช่วง)
