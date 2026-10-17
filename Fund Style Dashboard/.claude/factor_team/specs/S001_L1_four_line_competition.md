# S001_L1 — การแข่ง L1 ทั้ง 4 สายบนตารางคะแนนกลาง (spec ลงทะเบียนล่วงหน้า)

ผู้เขียน: factor-designer · วันที่ 2026-10-15 · ชั้น: L1 (ระยะ 1 — อธิบาย · ไม่นับ trial) · สถานะ: **รอรีวิว** (reviewer → ผู้ใช้สั่งรัน)
อ้างอิง: `BRIEF.md` (ตารางคะแนนกลาง lock · การตัดสินใจผู้ใช้ 2026-10-15 · "ค่าชั่วคราวจาก L0" 7 ข้อ) · `research/F-R001_literature_4lines_model_tests.md` ·
`data/QA_L0.md` · `reports/L0_summary.md` · `data/manifest.json`
การตรวจโครงข้อมูลของ designer (นับกอง/สัปดาห์เท่านั้น — **ไม่ได้ดูค่าผลตอบแทนกอง ไม่ได้ fit model**): `scratch/factor-designer_s001_structure.py`

> ทุกตัวเลขขนาดตัวอย่างในไฟล์นี้มาจากสคริปต์ข้างบน (รันเอง) หรือ `QA_L0.md` (data-engineer — ไม่ได้ตรวจซ้ำเองทุกตัว ยกเว้นที่ระบุ)
> ผลที่ขึ้นกับ "ค่าชั่วคราวจาก L0" ข้อ 1/3/4/5/7 ต้องติดป้าย **"ค่าชั่วคราว"** ในรายงานผล

---

## 0. ข้อเท็จจริงเชิงโครงสร้างที่กำหนด spec นี้ (ตรวจเอง)

| เรื่อง | ค่า | ผลต่อ spec |
|---|---|---|
| สัปดาห์ช่วงหลัก | 260 (2021-01-08 → 2025-12-26) · train 156 (→ 2023-12-29) · test 104 (2024-01-05 →) | Dimson ทำให้ train ใช้ได้ 155 แถว (สัปดาห์แรกไม่มี lag) · test ใช้ได้ 104 (lag ของสัปดาห์แรก test = สัปดาห์สุดท้าย train ซึ่งเป็นค่า factor ที่รู้แล้ว) |
| panel | 433 กอง (E 357 / F 49 / O 27) | — |
| **FIF Flag ใน panel** | **Y ทั้ง 433 กอง** · FX Risk Flag = N เพียง 29 กอง (E24/F2/O3) · Tax Type ว่างทั้งหมด · ETF Flag = N ทั้งหมด | ไม่มีกองหุ้นไทยในประเทศใน universe → TDEX เป็นตัวเสริม ไม่ใช่ factor หลัก · FundProfile ไม่มีประเทศ/sector → กลุ่ม (ภูมิภาค) ต้องกำหนดจาก NAV ช่วง train |
| กองซ้ำ corr > 0.99 | 32 กลุ่ม · ตัดได้ 50 กอง (ทั้งหมดอยู่ใน panel) | ดูข้อ 2.3 |
| ชุดประเมิน **EVAL** (ตัดซ้ำ · ≥104 สัปดาห์ใน train และ ≥52 ใน test) | **207 กอง (E 175 / F 18 / O 14)** | ชุดหลักของคะแนนข้อ 1–5 ทุก model |
| EVAL52 (ตัดซ้ำ · ≥52 / ≥52) | 268 (E 231 / F 22 / O 15) | ชุดเสริม (คะแนนข้อ 1–2 เท่านั้น) |
| balanced train (ตัดซ้ำ · ครบ 156 สัปดาห์ train) | **134 (E 110 / F 15 / O 9)** | sample ของ ①a / ①b / ④a |
| unbalanced train (ตัดซ้ำ · ≥52 สัปดาห์ train) | 277 (E 238 / F 23 / O 16) | sample ของ ①c และฐานจัดกลุ่มสาย ② |
| จำนวนกองต่อสัปดาห์ (ไม่ตัดซ้ำ) ต่ำสุด | train E120 / F19 / O10 · test E273 / F35 / O21 | APB ของ O มี ≥ 9 กองหลัง leave-one-out (ผ่านเกณฑ์ ≥ 5 ต่อสัปดาห์) |
| factor inputs ช่วงหลัก | ไม่มี NaN (ยกเว้น `*_late` ที่ห้ามใช้) | ไม่ต้อง impute factor |
| AUM มีค่า | ม.ค. 2021: 187 กอง · ธ.ค. 2023: 337 กอง | ใช้ค่ามัธยฐานช่วง train (ข้อ 3.② SIZE) |
| ไลบรารี | statsmodels 0.15.0 · scipy 1.18.1 ใน `.venv` | ใช้เป็นตัวเทียบใน test ได้ |

---

## 1. สมมติฐาน (ล็อกก่อนรัน)

- **H0 (หลัก):** มีชุด factor ≤ 6 ตัว ที่ให้ median adj R² ของกอง E ในช่วง train ≥ 0.60 และ R² นอกช่วง (2024–2025) ลดลงไม่เกิน 0.15 จากในช่วง
- **H①** (F-R001 ①-1): จำนวน factor ตามเกณฑ์รวม (ข้อ 3.①) อยู่ระหว่าง 2–6 · PC1 มี |corr| > 0.8 กับ ACWI(THB)−rf
- **H①b** (F-R001 ①-3): factor ของ ①c (unbalanced) กับ ①a (balanced) มี canonical correlation ทุกคู่ > 0.9 ในช่วง train — ถ้าไม่ แสดงว่า balanced panel มี selection bias
- **H②a** (F-R001 ②-1): APB ตาม policy (leave-one-out) ให้ median R² นอกช่วงของกอง E ไม่ต่ำกว่า ③a เกิน 0.05
- **H②b** (F-R001 ②-2): FX-hedge factor มี corr < −0.5 กับ ΔUSDTHB และเพิ่ม median adj R² ของ E ≥ 0.02 เหนือ ②a
- **H③** (F-R001 ③-1/③-2): ③a อธิบายกอง E ได้ใกล้ ① (ห่าง median R² นอกช่วง ≤ 0.05) · ③b เพิ่ม R² ของกอง F อย่างชัดเจน (median +0.05 ขึ้นไป) จาก bond spread
- **H④a** (F-R001 ④-1): k_res ≥ 1 · residual PC1 มี |corr| ≥ 0.5 กับ ΔUSDTHB หรือ FX-hedge factor หรือ MSCI ภูมิภาคเอเชีย/จีน (= สิ่งที่ ③a ขาด)

เกณฑ์ตัวเลขใน H เป็น **ความคาดหมายที่ใช้ตรวจตัวเองภายหลัง** ไม่ใช่เกณฑ์ผ่านอัตโนมัติ (BRIEF: ผู้ใช้เลือก)

---

## 2. ข้อมูล

### 2.1 ไฟล์ (sha256 จาก `data/manifest.json` — analyst ต้องตรวจ hash ก่อนรัน ถ้าไม่ตรง → หยุด)

| ไฟล์ | ใช้ทำ | sha256 |
|---|---|---|
| `.claude/factor_team/data/panel_weekly.parquet` | ผลตอบแทนกองรายสัปดาห์ (long: FundCode, date, ret = ผลตอบแทนเลขคณิต) | `95c16ee651d3a936788b7cb3c6372bbf5f1e84cb39daf5680343771dca24270b` |
| `.claude/factor_team/data/panel_monthly.parquet` | ตรวจซ้ำรายเดือน | `e8e8cb5d5f04fba9bb35558ef7c3d8195c656334119e56f82775cc1ae21ccaed` |
| `.claude/factor_team/data/factors_weekly.parquet` | factor inputs + RF_BOT | `115b87139d2bec0fd57a77a1593c46d36bb23f3f35f83236cdb07be642af47a8` |
| `.claude/factor_team/data/factors_monthly.parquet` | factor รายเดือน | `f7c4248b4fa889853024449e72ae8909cf1f8d3226a54eebc37448a2a485bb72` |
| `.claude/factor_team/data/aum_weekly.parquet` | SIZE (②c) | `48c34c73ae22ebffc6112f93e03f729223a496297bb65c324b693b817a723d26` |
| `.claude/factor_team/data/universe.csv` | policy · included · n_weeks · div_flag | `fdfb7830df78ce032465ac9d8cddc2c98f9aa86cfa0f3925fdb83026aa3f7252` |
| `.claude/factor_team/data/dup_pairs.csv` | กลุ่มกองซ้ำ | `b1f0f0c745947fa70803a4f40526c0a1967c72925be985a2bedc1057d8b8aef3` |
| `.claude/factor_team/data/factor_groups.csv` | ตรวจว่าไม่ใช้คอลัมน์ `FRED_spread_NOT_USABLE_MAIN` | `42bf1cfb270721ae6112799ab795ebc4c91212e7584d5cdfee23b9b70b1b1731` |
| (P0 ถ้าผู้ใช้อนุมัติ) `.claude/factor_team/data/panel_weekly_pre2021.parquet` | ใช้ **เฉพาะ** formation ของ MOM | ยังไม่มี — data-engineer สร้าง + ลง manifest |

### 2.2 นิยามตัวแปร
- excess return กอง: `x_i,t = ret_i,t − RF_BOT_t` (บาท) · factor ที่เป็นผลตอบแทนบาท: `− RF_BOT` · factor ส่วนต่าง (A − B) ไม่หัก rf · `USDTHB` = %Δ (บวก = บาทอ่อน) ไม่หัก rf · `*_d` = Δระดับ ไม่หัก rf
- ห้ามใช้: `*_late_*` · `*_lvl` (ระดับ) · `*_est_ret` (ค่าชั่วคราวข้อ 2 — ใช้ Δyield แทน) · ข้อมูล 2026 (ค่าชั่วคราวข้อ 6)
- ช่วง: **train** = 2021-01-08 → 2023-12-29 (156 สัปดาห์) · **test** = 2024-01-05 → 2025-12-26 (104) · **H1** = 2021-01-08 → 2023-06-30 (130) · **H2** = 2023-07-07 → 2025-12-26 (130)

### 2.3 ชุดกองต่อวิธี (ค่าชั่วคราวข้อ 4 · ตัดซ้ำ = เหลือ 1 กองต่อกลุ่ม connected component ของ `dup_pairs.csv` · เก็บกองที่ n_weeks มากสุด · เสมอ → FundCode ตามตัวอักษร)

| ใช้ทำ | ชุด | เหตุผล |
|---|---|---|
| สร้าง factor ① / ④ (PCA) | **ตัดซ้ำ** | กองซ้ำสร้าง eigenvalue ปลอม (กองเดียวกันนับ 2–7 ครั้ง) |
| สร้าง factor ② (EW / long–short) | **ตัดซ้ำ** | กันกองซ้ำได้น้ำหนักเกิน |
| ประเมินคะแนนข้อ 1, 2, 3 (|α|, PY, BH), 5 | **ตัดซ้ำ (EVAL)** = หลัก · ชุดเต็มไม่ตัดซ้ำ (≥104/≥52) = ภาคผนวก | median ไม่ถูกกองซ้ำถ่วง · PY/BH ต้องการ cross-correlation อ่อน (F-R001) |
| พอร์ต GRS | สมาชิกจากชุดตัดซ้ำ | เหมือนกัน |
| class ปันผล 27 กอง | **คงไว้** (ค่าชั่วคราวข้อ 5) · รายงาน |α| เฉลี่ยซ้ำโดยตัด `div_flag` ออก | NAV ไม่รวมปันผล → α ต่ำกว่าจริง (กระทบค่าเฉลี่ย ไม่ใช่ covariance) |

### 2.4 การจัดการ missing
- **ผลตอบแทนกอง:** ไม่ impute ใน regression ใด ๆ — ใช้เฉพาะแถวที่มีค่า (factor ไม่มี NaN) · ยกเว้น ①c ที่ใช้ EM ตามวิธี
- **factor ที่สร้างจากกอง (EW):** ค่าเฉลี่ยของสมาชิกที่มีค่าในสัปดาห์นั้น · ถ้าสมาชิก (หลัง leave-one-out) < 5 → factor = NaN สัปดาห์นั้น → แถวนั้นตกจาก regression ที่ใช้ factor นั้น (รายงานจำนวนสัปดาห์ที่ตก — คาดว่า 0)
- **factor PCA ในช่วง test:** projection บนกองที่มีค่า (ข้อ 3.①) · ถ้ามีค่า < 50% ของกองใน Λ → NaN
- เกณฑ์ขั้นต่ำต่อกอง: **≥ 104 แถวใน train และ ≥ 52 ใน test** (EVAL) · H1/H2 ต้อง ≥ 52 ต่อครึ่ง · rolling ต้อง ≥ 78 ใน 104 · รายเดือน: train ≥ 24 เดือน test ≥ 12

---

## 3. วิธี (10 รูปแบบ: ① 3 · ② 3 · ③ 3 · ④ 1 — ลองนอกจากนี้ = spec ใหม่)

### กติการ่วมทุกรูปแบบ
- regression รายกอง: `x_i,t = α_i + Σ_k (b0_ik f_k,t + b1_ik f_k,t−1) + e_i,t` (**Dimson lag 1** · β_ik = b0+b1 · SE ของ β จาก HAC ของผลรวม)
- **HAC Newey–West, Bartlett, lag L = 4** รายสัปดาห์ (= floor(4(T/100)^{2/9}) ที่ T = 155 และ 104 ได้ 4 ทั้งคู่) · รายเดือน L = 3 (T = 35)
- จำนวนพารามิเตอร์ p = 2K + 1 · adj R² = 1 − (1−R²)(n−1)/(n−p)
- factor ทุกตัวที่สร้างจากกอง (①, ②, ④) **ประมาณน้ำหนัก/กลุ่มด้วย train เท่านั้น** แล้วค่าในช่วง test = ใช้น้ำหนัก/กลุ่มเดิมกับผลตอบแทน test (ตารางคะแนนข้อ 2)
- เมล็ดสุ่ม (permutation): `20261015` · ทุกการเรียงลำดับใช้ `kind="stable"`

### สาย ① pure stat (F-R001 ①-1/①-2/①-3 · Bai–Ng 2002, Ahn–Horenstein 2013, Onatski 2010, Horn 1965, Connor–Korajczyk, Xiong–Pelger)

| | ①a correlation-PCA (หลัก · ผู้ใช้ตัดสิน) | ①b covariance-PCA (เสริม) | ①c missing-data PCA |
|---|---|---|---|
| sample | balanced train ตัดซ้ำ 134 กอง × 156 สัปดาห์ | เดียวกับ ①a | unbalanced train ตัดซ้ำ 277 กอง (≥52 สัปดาห์) |
| เตรียม X | z_i,t = (x_i,t − μ_i)/σ_i (μ,σ ของ train) | d_i,t = x_i,t − μ_i | z ตามค่าที่มี (μ,σ จากแถวที่มี) |
| k | **k\* = floor(มัธยฐานของ {IC_p2, ER, ED, PA})** · kmax = 10 · บังคับ k\* ≥ 1 | = k\* ของ ①a (ไม่เลือกใหม่) | = k\* |
| ประมาณ | eigen ของ X'X/T (N×N) → Λ = eigenvector k\* ตัวแรก (‖λ‖=1) | eigen ของ covariance | EM (Stock–Watson): เริ่มเติม 0 → SVD rank k\* → แทนค่าที่ขาด → วนจน ‖Δ‖_F/‖X_miss‖_F < 1e-6 หรือ 1,000 รอบ · ไม่สุ่ม · Λ = loadings ปรับ ‖λ‖=1 |

- **เกณฑ์จำนวน factor** (คำนวณบน z ของ ①a): IC_p2 (Bai–Ng: ln V(k) + k(N+T)/(NT)·ln min(N,T)) · ER = argmax_k λ_k/λ_{k+1} (Ahn–Horenstein) · ED (Onatski 2010 ขั้นตอน iterative calibration ตามบทความ, kmax 10) · PA: 500 permutation สลับแต่ละคอลัมน์อิสระ เก็บ k = จำนวน eigenvalue จริงที่ > percentile 95 ของ eigenvalue ลำดับเดียวกัน · รายงานทั้ง 4 ค่า + IC_p1 และ GR (บรรยาย ไม่ใช้)
- **factor return (ทุกช่วง)** = cross-sectional projection: f_t = (Λ_A'Λ_A)^{-1} Λ_A' z_A,t · A = กองใน Λ ที่มีค่าในสัปดาห์ t (balanced train → = Λ'z_t พอดี) · test ใช้ μ,σ,Λ ของ train
- **เครื่องหมาย:** PC แต่ละตัวกลับเครื่องหมายให้ผลรวม Λ ≥ 0 (ไม่กระทบ R²)
- **บรรยายเพิ่ม (ไม่ใช่รูปแบบที่แข่ง ไม่ใช้เลือก k):** เส้น median adj R² (train) และ R² นอกช่วง ของ ①a ที่ k = 1…8 แยก E/F/O
- ① ไม่ทำ leave-one-out (ผู้ใช้กำหนด LOO เฉพาะสาย ②) → **รายงานคะแนนข้อ 1–2 แยก "กองที่อยู่ใน sample PCA" กับ "ไม่อยู่"** เพื่อวัด circularity

### สาย ② Fama-French ของกองทุน (F-R001 ②-1/②-2/②-3/②-4/②-5 · Hunter et al. 2014, Carhart 1997, Amihud–Goyenko 2013) — **leave-one-out ทุกตัว**

ฐานจัดกลุ่ม = unbalanced train ตัดซ้ำ (277) · คุณลักษณะคำนวณจาก **train เท่านั้น** แล้วตรึงกลุ่มไว้ตลอด test (ยกเว้น MOM ที่ rebalance รายไตรมาสด้วยข้อมูลในอดีตเท่านั้น) · กองที่ไม่มีข้อมูล train ไม่อยู่ใน factor

**การกำหนดภูมิภาค (ใช้กับ FXH, ACT, พอร์ต GRS):** กอง E/O ทุกกองในฐาน → Dimson regression ทีละดัชนีบน {MSCI_USA, MSCI_EUROPE, MSCI_JAPAN, MSCI_CHINA_ALL_SHARES, MSCI_ASIA_EX_JAPAN, MSCI_INDIA, MSCI_VIETNAM, MSCI_ACWI} (−rf · ช่วง train) → ภูมิภาค = ดัชนีที่ให้ R² สูงสุด (เสมอ → ลำดับในวงเล็บ) · บันทึก `runs/S001/regions.csv`

| factor | นิยาม |
|---|---|
| APB_E, APB_F, APB_O | EW ของ x ของกองใน policy นั้น · เมื่อ regress กอง i ใน policy g → APB_g สร้างโดย**ไม่รวม i** (LOO) |
| FXH (hedged − unhedged) | กอง E: Dimson regression `x ~ [R_ภูมิภาค(THB)−rf, USDTHB]` ใน train → FX beta = b0+b1 ของ USDTHB (≈ 0 = ไม่ hedge · ติดลบ = hedge) · เรียง**ภายในภูมิภาค** (ภูมิภาคที่มี < 10 กอง → รวมเป็นกลุ่ม "อื่น") ที่ 30/40/30 → FXH = EW(FX beta ต่ำ 30%) − EW(สูง 30%) รวมทุกภูมิภาค |
| MOM (52-4) | ทุกสิ้นไตรมาส τ (ศุกร์สุดท้ายของ มี.ค./มิ.ย./ก.ย./ธ.ค.) · กอง E ที่มี ≥ 40 สัปดาห์ในช่วง (τ−52, τ−4] · ผลตอบแทนทบต้นช่วงนั้น → 30/40/30 → MOM = EW(บน) − EW(ล่าง) ถือสัปดาห์ τ+1 ถึง τ ถัดไป · **ห้ามใช้ข้อมูลหลัง τ** · formation ก่อน 2021 ใช้ P0 (ดู "ต้องให้ผู้ใช้ตัดสินใจ" ข้อ 1) |
| SIZE (small − big) | กอง E: มัธยฐาน log AUM ช่วง train (กองไม่มี AUM ใน train → ไม่อยู่ในการเรียง) → 30/40/30 → EW(เล็ก) − EW(ใหญ่) |
| ACT (active − passive) | กอง E: 1 − R² ของ Dimson regression บนดัชนีภูมิภาคตัวเดียว (train) → 30/40/30 → EW(1−R² สูง) − EW(ต่ำ) |

- long–short ทั้งหมดสร้างจากกอง E เท่านั้น (F 23 / O 16 กองในฐาน → ขา 30% เหลือ 5–7 กอง ไม่พอ) · LOO: กอง i ถูกตัดจากทุกขาที่ตนอยู่
- **②a** = {APB_E, APB_F, APB_O} (K=3) · **②b** = ②a + FXH + MOM (K=5) · **②c** = ②b + SIZE + ACT (K=7 · ตัวเสี่ยง overfit)
- long–short ระหว่างกองเป็นเชิงอธิบาย (BRIEF: กองทุนไทยขายชอร์ตไม่ได้ · ห้ามสรุปว่าลงทุนได้)

### สาย ③ factor ภายนอก (F-R001 ③-1/③-2/③-3/③-4 · Sharpe 1992, EGB 1993/1995, CPZ 2013, Fung–Hsieh 2004)

| รูปแบบ | factor (คอลัมน์ใน `factors_weekly`) | K |
|---|---|---|
| **③a** | MKT = MSCI_ACWI−rf · BOND = AGG_THB−rf · GOLD = Gold_THB−rf · FX = USDTHB | 4 |
| **③b** | ③a + EMDM = MSCI_EM − MSCI_WORLD · USX = MSCI_USA − MSCI_ACWI · TH = TDEX_THB−rf (ผู้ใช้: TDEX แทน SET · ค่าชั่วคราวข้อ 7) · TERM = IEF_THB − SHV_THB · IG = LQD_THB − IEF_THB · HY = HYG_THB − LQD_THB · EMD = EMB_THB − IEF_THB | 11 |
| **③c** | ③b + Momentum · Quality · Value · LowVol (de-market แล้ว) · VIX_d · US10Y_d · Oil_Brent · TH5Y_d (Δyield ไทย เป็นตัวเสริมตามค่าชั่วคราวข้อ 2) | 19 |

- bond spread ใน ③b เป็นส่วนต่างของ ETF บาทสองตัว (USDTHB หักล้างกันโดยประมาณ) · ไม่ใช้ IG/HY OAS (มีแค่ 2023-10+)
- ③c: VIX_d / US10Y_d / TH5Y_d ลงทุนไม่ได้ → ไม่ใช้ใน spanning (ข้อ 4.4) · GRS ยังรายงานได้ (ทดสอบ α ของ test asset)

### สาย ④ factor ใหม่ (F-R001 ④-1 · Connor–Korajczyk 1991)
- **④a** = ③a + residual PC: กองใน balanced train ตัดซ้ำ (134) → regress บน ③a (Dimson, train) → residual ê → correlation-PCA ของ ê → **k_res = IC_p2 บน ê, kmax = 5** (ถ้า 0 → ④a = ③a และรายงานว่า "ไม่มี residual factor") · test: ê_test = x − α̂ − β̂'f (β̂ ของ train ไม่ fit ใหม่) → projection แบบ ①
- เกณฑ์บรรยาย Harvey–Liu–Zhu: residual PC "มีนัย" เมื่อ |t_HAC| > 3 ใน ≥ 10% ของกอง EVAL
- **④b hedge-cost — ตัดออกจาก L1:** BRIEF/F-R001 ระบุว่าไม่มีข้อมูล · ข้อเท็จจริงที่ตรวจพบ: ใน `factors_weekly` มี `DTB3_lvl` และ `TH_TBILL3M_lvl` (ดอกเบี้ย 3 เดือนสองสกุล) อยู่แล้ว แต่ carry ของการ hedge ตาม CIP รายสัปดาห์ ≈ (i_TH − i_US)/52 เป็นอนุกรมที่เปลี่ยนช้าเกือบคงที่ → กระทบ**ค่าเฉลี่ย**ผลตอบแทนกองที่ hedge ไม่ใช่ความแปรปรวนร่วม → ไม่เหมาะเป็น factor ร่วมของ L1 · เสนอไปทดสอบที่ L4 เป็นตัวอธิบาย α ของกองที่ hedge (ผู้ใช้ตัดสินใจ ข้อ 2)
- ④-2 Thai-domestic factor: ไม่ทำเป็นรูปแบบแยก เพราะ panel เป็น FIF ทั้งหมด · TH อยู่ใน ③b แล้ว

---

## 4. การทดสอบ

### 4.1 regression รายกอง (ทุก 10 รูปแบบ · ชุด EVAL + EVAL52 + ชุดเต็มภาคผนวก)
- train: α̂, β̂ (Dimson), t_HAC, adj R², BIC ต่อกอง
- test (นอกช่วง): ŷ_i,t = α̂_i^train + Σ (b̂0 f_t + b̂1 f_t−1) · f ของ test สร้างตามข้อ 3 (ไม่ fit ใหม่) · **R²_oos,i = 1 − Σ(x−ŷ)² / Σ(x − x̄_i^test)²** (ติดลบได้ — รายงานตามจริง)

### 4.2 GRS บนพอร์ตกลุ่ม (Gibbons–Ross–Shanken 1989)
- **พอร์ต (≤ 20 · ล็อกก่อนรัน · จากข้อมูล train เท่านั้น ไม่ใช้ผลตอบแทน test):**
  - E: ภูมิภาคตามข้อ 3.② (8 กลุ่ม) · ภูมิภาคที่มี ≥ 10 กอง → แบ่งครึ่งตามมัธยฐาน FX beta (hedge / ไม่ hedge) · ภูมิภาคที่มี < 5 กอง → รวมเข้า ACWI
  - F: 2 พอร์ตตามมัธยฐาน σ ผลตอบแทนช่วง train · O: 2 พอร์ตแบบเดียวกัน
  - สมาชิก = กองในฐาน unbalanced train ตัดซ้ำ · พอร์ต = EW ของสมาชิกที่มีค่า (≥ 3 กองต่อสัปดาห์ ไม่งั้นตัดสัปดาห์นั้นทั้งระบบ — รายงานจำนวน)
- สูตร: GRS = ((T−N−L)/N) · α̂'Σ̂⁻¹α̂ / (1 + μ̄'Ω̂⁻¹μ̄) ~ F(N, T−N−L) · L = 2K (รวม lag) · Σ̂ ใช้ dof T−L−1 · Ω̂ = covariance ของ regressor
- ช่วง: **test (หลัก · T = 104 · factor OOS)** และ train (T = 155) · รายงาน F, p, N, L, mean|α̂| ของพอร์ต (%/ปี = ×52)
- ข้อจำกัดที่ล็อกไว้: ③c ใน test มี T−N−L = 104−20−38 = 46 (ยังคำนวณได้แต่ power ต่ำ) · **สาย ② ใช้ factor ไม่ LOO ใน GRS** (GRS ต้องใช้ factor ชุดเดียวกันทุกพอร์ต) → ติดป้าย "circular" · สาย ② ใช้ PY (ข้อ 4.3) เป็นตัวหลักของคะแนนข้อ 3

### 4.3 Pesaran–Yamagata (2024) — α = 0 ทุกกองพร้อมกัน (N > T)
- ชุด EVAL ตัดซ้ำ · ทั้ง train และ test · t_i จาก OLS ตามบทความ (หลัก) และ HAC (sensitivity) · v_i = T_i − p − 1 (ต้อง > 4)
- J_α = N^{-1/2} Σ_i [t_i² − v_i/(v_i−2)] / sqrt( 2·(1 + (N−1)ρ̄²_N) · mean_i[(v_i/(v_i−2))²·(v_i−1)/(v_i−4)] ) โดย ρ̄²_N = ค่าเฉลี่ย ρ_ij² ของคู่ residual ที่ผ่าน threshold Bailey–Pesaran–Smith: |ρ_ij| > Φ⁻¹(1 − p/(2f(N)))/√T_ij · p = 0.10 · f(N) = N(N−1)/2 · คู่ที่ทับกัน < 52 สัปดาห์ = 0 · **analyst ต้องเทียบสูตรกับบทความต้นฉบับก่อน implement** และถ้าต่าง ให้ยึดบทความ + บันทึกใน run log
- รายงาน J_α, p (ข้างเดียว N(0,1)) แยก ALL / E (F และ O ตัวอย่างเล็ก — รายงานพร้อมคำเตือน)

### 4.4 ตัวเสริม (ไม่อยู่ในตารางคะแนนกลาง · ไม่ใช้ตัดสิน)
- **BH (FDR 10%)** ของ α รายกอง (t_HAC · train) → จำนวนกองที่ α ≠ 0 แยก E/F/O
- **Spanning / Barillas–Shanken** เฉพาะรูปแบบฐาน ①a, ②a, ③a, ④a (ล็อกก่อนรัน ไม่เลือกตัวดีที่สุดหลังเห็นผล): factor แต่ละตัวของ A ~ factor ของ B (Dimson · HAC · ช่วง test) → α, R² · Wald joint α = 0 ต่อคู่ (A,B)
- **lead diagnostic ครั้งเดียว:** ③a + lead 1 ทุกตัว (train) → % กอง EVAL ที่ |t_lead| > 2 (ไม่ใช้ใน model หลัก)
- **residual correlation ภายใน policy:** mean |corr(ê_i, ê_j)| ภายใน E/F/O (train) ต่อรูปแบบ (F-R001 H②a)
- **H①b:** canonical correlations ระหว่าง factor ①c กับ ①a ในช่วง train
- **ตรวจซ้ำรายเดือน:** คะแนนข้อ 1–2 ด้วย panel/factor รายเดือน (Dimson lag 1 เดือน · HAC L=3) · ①/④: projection ผลตอบแทนรายเดือนบน Λ ของ train (μ,σ รายเดือนของ train) · ②: EW รายเดือนของกลุ่มเดิม · รายงานเฉพาะรูปแบบที่ p ≤ 17 (≈ ครึ่งของ 35 เดือน) · ที่เหลือ = "N/A (พารามิเตอร์เกิน)"

---

## 5. ตารางคะแนนที่รายงาน (ตารางกลางของ BRIEF ครบ 6 ข้อ · ทุกข้อแยก E / F / O / ALL พร้อม n)

| ข้อ | ตัวชี้ | นิยามที่ล็อก |
|---|---|---|
| 1 R² รายกอง | median, IQR ของ adj R² | train · ชุด EVAL (หลัก) · EVAL52 + ชุดเต็ม (ภาคผนวก) · ① แยกใน/นอก sample PCA |
| 2 R² นอกช่วง | median, IQR ของ R²_oos · median(R²_train − R²_oos) | ข้อ 4.1 · test 2024–2025 · factor และ loading จาก train |
| 3 pricing error | mean|α̂| (%/ปี) รายกอง train · GRS F/p (test หลัก, train รอง) · PY J_α/p | ข้อ 4.2–4.3 · mean|α̂| ซ้ำโดยตัด class ปันผล |
| 4 ความประหยัด | K · p = 2K+1 · median BIC_i และ median ΔBIC_i เทียบ ③a | BIC_i = n_i ln(SSR_i/n_i) + p ln n_i (train · EVAL) |
| 5 ความเสถียร | (ก) corr ข้ามกองของ β_ik ระหว่าง H1 กับ H2 ต่อ factor + ค่าเฉลี่ย (ข) rolling 104 สัปดาห์ เลื่อนทีละ 4 (40 หน้าต่าง) → corr ข้ามกองของ β ในหน้าต่างกับ β ทั้งช่วงหลัก: มัธยฐาน และ ค่าต่ำสุด ต่อ factor | อนุกรม factor = ฉบับที่สร้างด้วยน้ำหนัก train · กองต้อง ≥ 52 แถวต่อครึ่ง / ≥ 78 ต่อหน้าต่าง |
| 6 ตีความได้ | ต่อ factor: 3 อันดับ |corr| สูงสุดกับชุดอ้างอิง I (MSCI 28 −rf · style 4 · Gold_THB, AGG/IEF/SHV/LQD/HYG/EMB_THB −rf · USDTHB · TDEX−rf · Oil · VIX_d · US10Y_d · TH5Y_d · DTB3_d) ช่วงหลักทั้งหมด · R² ของ factor ~ ③b · ชื่อ: max|corr| ≥ 0.7 → "≈ ชื่ออนุกรม" · 0.5–0.7 → "คล้าย …" · < 0.5 → "ไม่มีชื่อ" | สาย ③ ตีความได้ตามนิยาม (รายงาน corr ภายในชุดแทน) |

ตัวเพิ่มของชั้นนี้: k ของทุกเกณฑ์ + เส้น R² k=1…8 · H①b · spanning · BH · lead · residual corr · รายเดือน

ไฟล์ผล: `runs/S001/scorecard.csv` (1 แถว/รูปแบบ × policy) · `fund_level.csv` (กอง × รูปแบบ: α, t, adj R², R²_oos, BIC) · `factors_S001_weekly.parquet` · `nfactors.csv` · `grs.csv` · `py.csv` · `stability.csv` · `interpret.csv` · `spanning.csv` · `regions.csv` · `run_meta.json` (sha256 ข้อมูลตาม manifest + sha256 ทุกไฟล์ใน `lib/` + เวอร์ชันแพ็กเกจ)

---

## 6. โมดูลใน `.claude/factor_team/lib/` (analyst เขียน · ทุกฟังก์ชันมี test)

| โมดูล | ฟังก์ชัน (input → output) |
|---|---|
| `io_l1.py` | `verify_manifest(paths) → None` (raise ถ้า sha256 ไม่ตรง) · `load_returns(freq) → DataFrame T×N` (excess) · `load_factors(freq) → DataFrame T×75` · `lib_hash() → dict` |
| `samples.py` | `dedup_keep(dup_pairs, n_weeks) → set` · `window_mask(index, name) → bool array` (train/test/H1/H2) · `eligible(R, rules) → list` (EVAL, EVAL52, balanced, unbalanced) |
| `regress.py` | `dimson_design(F, lags=1) → DataFrame` · `ols_hac(y, X, L=4) → dict(coef, cov, t, resid, r2, adj_r2, bic, n)` · `fit_funds(R, F, mask, min_obs) → DataFrame` · `predict_oos(coef, F_test) → DataFrame` · `r2_oos(y, yhat) → float` |
| `nfactors.py` | `bai_ng_ic(Z, kmax) → dict(IC_p1, IC_p2)` · `ahn_horenstein(eig, kmax) → (ER, GR)` · `onatski_ed(eig, kmax) → int` · `parallel_analysis(Z, n_perm=500, q=0.95, seed) → int` · `combine_k(ks) → int` (floor ของมัธยฐาน, ≥1) |
| `pca.py` | `pca_fit(X, k, kind='corr'|'cov') → (Λ, μ, σ, eig)` · `em_pca(X, k, tol=1e-6, maxit=1000) → (Λ, F, n_iter)` · `project(X_t, Λ, μ, σ, min_frac=0.5) → DataFrame T×k` · `sign_fix(Λ)` |
| `fundff.py` | `assign_region(R, idx, mask) → Series` · `fx_beta(R, F, region, mask) → Series` · `sort_legs(char, groups, q=(.3,.7)) → dict` · `ew_factor(R, members, exclude=None, min_n=5) → Series` · `apb(R, policy, loo) → DataFrame` · `momentum(R, form=52, skip=4, min_obs=40, rebalance='Q') → (Series, membership)` |
| `external.py` | `line3(F, variant) → DataFrame` (③a/③b/③c ตามตาราง) |
| `tests_stat.py` | `grs(R_port, X) → dict(F, p, N, L)` · `pesaran_yamagata(t, v, resid, p=0.10) → dict(J, p, rho2)` · `bh(pvals, q=0.10) → bool array` · `spanning(fA, fB, L=4) → DataFrame` |
| `scorecard.py` | `score_model(...) → DataFrame` (6 ข้อ แยก policy) · `stability_halves(...)` · `stability_rolling(win=104, step=4, min_obs=78)` · `interpret(fac, ref_set) → DataFrame` |
| `run_s001.py` | สคริปต์รันเดียวจบ → `runs/S001/` |

### test ที่ต้องผ่านก่อนรัน (`pytest -p no:cacheprovider .claude/factor_team/lib/tests/`)
1. `ols_hac` ตรงกับ statsmodels OLS `cov_type='HAC', maxlags=4` (Bartlett · ไม่มี small-sample correction ทั้งคู่ — ตั้งให้ตรงกัน) ที่ 1e-8
2. `dimson_design` lag ถูกตำแหน่ง · แถวแรกของ train ตก · แถวแรกของ test ใช้ค่า lag จาก train
3. `nfactors`: ข้อมูลจำลอง N=134, T=156, k จริง = 3, SNR ปานกลาง → IC_p2, ER, PA ได้ 3 · `combine_k([2,3,4,6]) = 3`
4. `em_pca`: ข้อมูลจำลอง k=3, ขาดสุ่ม 30% → canonical corr ของ factor กับของจริง > 0.95 · deterministic (2 รอบเท่ากันทุกบิต)
5. `project`: กองครบ → เท่ากับ Λ'z · ตัดกองครึ่งหนึ่งจาก model ที่ไม่มี noise → ได้ factor เดิม
6. `apb` / `ew_factor`: LOO ไม่รวมกองตัวเองจริง (เปลี่ยนค่ากอง i แล้ว factor ของ i ไม่เปลี่ยน) · min_n → NaN
7. **no look-ahead:** แก้ผลตอบแทนหลังวัน τ แล้ว membership ของ MOM ที่ τ, ภูมิภาค, FX beta, Λ, β̂ train ไม่เปลี่ยน
8. `predict_oos` ไม่ fit ใหม่ (coef ที่ใช้ = coef train ทุกบิต)
9. `grs`: ตรงสูตรปิดกับตัวอย่างคำนวณมือ · simulation 1,000 รอบใต้ H0 (N=20, T=104, L=8) → อัตราปฏิเสธ 5% อยู่ใน [3.5%, 6.5%]
10. `pesaran_yamagata`: simulation ใต้ H0 (N=200, T=104, error อิสระ) → อัตราปฏิเสธ 5% อยู่ใน [3%, 8%]
11. `bh`: ตรงกับ `statsmodels.stats.multitest.multipletests(method='fdr_bh')`
12. `verify_manifest` raise เมื่อแก้ไฟล์ 1 byte · `run_s001.py` รัน 2 รอบได้ไฟล์ผล sha256 เท่ากัน
13. ไม่มีคอลัมน์ `*_late*`, `*_lvl`, `*_est_ret` หรือวันที่ ≥ 2026-01-01 ในข้อมูลที่ส่งเข้า regression

---

## 7. เกณฑ์ผ่าน/ไม่ผ่าน (ข้อเสนอของ designer · ผู้ใช้เป็นคนเลือก · BRIEF: ไม่มีเกณฑ์อัตโนมัติ)

**การรันถือว่าใช้ได้ (technical validity)** เมื่อ: test ทั้ง 13 ข้อในหัวข้อ 6 ผ่าน · hash ตรง manifest · รันซ้ำตรงทุกบิต · ไม่มีรูปแบบใดที่ fit ไม่ได้ (ถ้ามี → รายงาน ไม่แก้ spec ระหว่างรัน)

**ข้อเสนอเกณฑ์ "ผู้เข้ารอบ" ไป L2** (ต้องผ่านทุกข้อ · ประเมินแยกกอง E เป็นหลัก · F/O รายงานแต่ n เล็ก):
1. median R²_oos (E) ≥ 0.9 × ค่าสูงสุดในบรรดา 10 รูปแบบ
2. median(R²_train − R²_oos) (E) ≤ 0.15
3. ความเสถียร: ค่าเฉลี่ย corr β ระหว่าง H1/H2 ≥ 0.6
4. ΔBIC median ≤ 0 เทียบรูปแบบที่เล็กกว่าในสายเดียวกัน (ไม่งั้นเลือกตัวที่เล็กกว่า)
5. factor ทุกตัวได้ชื่อ (max |corr| ≥ 0.5) หรือเป็นนิยามตรง (สาย ②/③)
- GRS / PY: ใช้เรียงลำดับและบรรยาย ไม่ใช้ตัดออก (คาดว่าปฏิเสธเกือบทุกรูปแบบเพราะ power สูง — Lewellen–Nagel–Shanken 2010)
- ถ้าไม่มีรูปแบบใดผ่าน → รายงานตามจริงว่า "ไม่มีชุดที่ผ่าน" + เหตุผล (BRIEF เกณฑ์ความสำเร็จ)

---

## 8. ผลลัพธ์ที่คาดไว้ล่วงหน้า (เขียนก่อนเห็นผล · ใช้ตรวจตัวเอง)

1. k\* ของ ①a = 3–5 · ER มักให้ 1 (PC แรกแรงมาก) · PA ให้มากสุด · PC1 ≈ ตลาดหุ้นโลก (|corr| > 0.8 กับ MSCI_ACWI−rf) · PC2/3 ≈ ภูมิภาค (จีน/เอเชีย vs สหรัฐฯ) หรือ บอนด์/ค่าเงิน
2. median adj R² train (E): ① ≈ 0.70–0.85 > ③b ≈ 0.65–0.80 > ③a ≈ 0.55–0.75 · ②a ≈ ③a · ส่วนต่าง ①−③ ใน R²_oos แคบกว่าใน train
3. กอง F: R² ต่ำทุกรูปแบบ (median 0.2–0.5) · ③b ดีขึ้นจาก ③a ชัดที่สุด (credit/term) · APB_F ช่วย F มากกว่า ③a
4. กอง O: อยู่ระหว่าง E กับ F
5. ③c train R² สูงสุดในสาย ③ แต่ BIC แย่กว่า ③b และ R²_oos ไม่ดีกว่า ③b
6. ②c: SIZE และ ACT แทบไม่เพิ่ม R² (< 0.01) · FXH มี corr ติดลบกับ USDTHB ชัด · MOM เพิ่มน้อย
7. ①c ≈ ①a (canonical corr > 0.9) · กองใน sample PCA มี R² สูงกว่ากองนอก sample ≈ 0.02–0.05
8. ④a: k_res = 1–3 · residual PC1 สัมพันธ์กับจีน/เอเชีย หรือ hedge
9. GRS (test) ปฏิเสธ α = 0 ที่ 5% ในเกือบทุกรูปแบบ · PY ปฏิเสธเช่นกัน
10. ความเสถียร: β ของ factor ตลาด/APB_E corr H1–H2 > 0.8 · long–short (FXH, MOM, SIZE, ACT) < 0.5
11. lead diagnostic: < 10% ของกองมี |t_lead| > 2 (ถ้ามากกว่านี้ = การจัดสัปดาห์มีปัญหา → ต้องแจ้ง data-engineer)

---

## 9. ข้อจำกัด (ติดไปกับรายงานผล)
- FundProfile เป็น snapshot · class ปันผล 27 กองไม่รวมปันผล · spike F 119 จุดยังไม่แก้ (ค่าชั่วคราวข้อ 3 — กระทบ F ที่ vol ต่ำ) · ETF/MSCI ปิดคนละเวลา (Dimson ช่วยบางส่วน) · TDEX = SET50 สภาพคล่องต่ำ
- balanced sub-panel มี survivorship (กองอายุยาว) — ①c / EVAL52 ใช้เทียบ
- F (18) และ O (14) ใน EVAL เล็ก → median/IQR ไม่นิ่ง · PY/GRS แยก F/O power ต่ำ
- กลุ่มภูมิภาคมาจาก R² ช่วง train (ไม่ใช่ประกาศของกอง) — test window ไม่ถูกแตะ แต่ในช่วง train เป็น circular เล็กน้อย
- GRS ของสาย ② circular (factor รวมสมาชิกพอร์ต)

---

## ต้องให้ผู้ใช้ตัดสินใจ

1. **ข้อมูลก่อน 2021 สำหรับ MOM (P0):** MOM 52-4 ต้องมีผลตอบแทนย้อน 52 สัปดาห์ → ถ้าไม่มี MOM จะเริ่มได้ ม.ค. 2022 และ ②b/②c ใช้ช่วง train ไม่เท่ารูปแบบอื่น · **ค่าเริ่มต้นที่เสนอ:** ให้ data-engineer สร้าง `panel_weekly_pre2021.parquet` (2019-12-27 → 2020-12-25 · pipeline เดียวกับ L0 · ไฟล์ NAV มีในเครื่องแล้ว ไม่ต้องดาวน์โหลด) ใช้กับ formation ของ MOM เท่านั้น · ถ้าไม่อนุมัติ → ย้าย MOM ไป ②c และให้ ②c ใช้ train 2022–2023 พร้อมป้าย "ไม่เทียบตรง"
2. **④b hedge-cost:** ตัดออกจาก L1 (กลไกกระทบค่าเฉลี่ย ไม่ใช่ covariance) · มีข้อมูล DTB3 + T-bill 3M ไทยอยู่แล้ว → เสนอทดสอบที่ L4 เป็นตัวอธิบาย α ของกองที่ hedge — ยืนยัน/ปฏิเสธ
3. **เกณฑ์ชุดประเมิน EVAL** (≥104 train / ≥52 test · 207 กอง: E175/F18/O14) เทียบทางเลือก ≥52/≥52 (268 กอง) ที่มีกองมากกว่าแต่ ③c เหลือ dof ต่ำ (52 − 39) — เสนอ EVAL เป็นหลัก EVAL52 เป็นภาคผนวก
4. **universe เป็น FIF ทั้งหมด (433/433)** → ไม่มีกองหุ้นไทยในประเทศ · คง TDEX ใน ③b ตามที่ตัดสินแล้ว หรือถอดออกเพื่อลด K
5. **เกณฑ์ผู้เข้ารอบ L2 ในข้อ 7** — ยืนยัน/แก้ค่าก่อนรัน (หลังเห็นผลห้ามแก้)
6. ค่าชั่วคราวจาก L0 (ข้อ 1/3/4/5/7) ยังรอยืนยันตอนจบ L1 ตาม BRIEF
