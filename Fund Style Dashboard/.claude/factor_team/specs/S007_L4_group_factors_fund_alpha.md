# S007_L4 — กลุ่ม / รายกอง: factor เฉพาะกลุ่ม · α รายกองหลังหัก factor ชุดสุดท้าย (+ FX) · อะไรอธิบาย α ข้ามกอง (spec ลงทะเบียนล่วงหน้า)

ผู้เขียน: factor-designer · วันที่ 2026-10-17 · ชั้น: **L4** (ชั้นสุดท้ายของระยะ 1 — อธิบาย · ไม่นับ trial) · สถานะ: **รอรีวิว** (reviewer → session หลักสั่งรันตาม auto run)
อ้างอิง: `BRIEF.md` (ค่าที่ยืนยัน 1–21 · ค่าชั่วคราว 22–72 โดยเฉพาะ **52–55, 64, 67–69, 72** · ตารางชั้น L4 · ตารางคะแนนกลาง) · `reports/L1_summary.md` (9b) · `reports/L2_summary.md` · `reports/L3_summary.md` (ข้อ 10–11) ·
`specs/S006_L3_vif_cleaned.md` · `runs/S006/results.md` · `research/F-R004_deep_search_L3_L4.md` (**L4-1, L4-2, L4-3, L4-4, L4-5**) · F-R001 (②-6, ④-3, BSW, EGB 1993, Amihud–Goyenko) · F-R003 (BY/PRDS) ·
`data/QA_ACWI_CD_group.md` · `data/QA_L0.md` · `data/manifest.json` · `data/manifest_ext.json`
การตรวจของ designer: `scratch/factor-designer_s007_structure.py` (+ `.json`) และ `scratch/factor-designer_s007_structure2.py` (+ `.json`) — sha256 · ชื่อคอลัมน์ · จำนวนกองต่อป้าย · ความครอบคลุมของคุณลักษณะ (ค่าธรรมเนียม / ธง) เท่านั้น ·
**ไม่ได้ดูค่าผลตอบแทนกอง ไม่ได้ fit model ไม่ได้อ่านคอลัมน์ผล (alpha / r2 / beta) ของ `runs/*`**

> **ป้ายบังคับทุกตารางผล:**
> (ก) ED ตรงกับแหล่งรอง (R `cate::EigenDiff`) · ยังไม่เปิดต้นฉบับ Onatski 2010 [22, 47] — ทุกผลของ ①a / ①c (k\* = 4) และการนับ factor ในกลุ่ม ·
> (ก2) PY ตรงต้นฉบับ แต่ (N−1)ρ̄² > 1 → อ่าน p_boot ·
> (ข) **ช่วง test 2024–2025 ถูกใช้เลือกรูปแบบตั้งแต่ L1 (และ P4 ถูกเลือกด้วยช่วงนี้ใน L2) — ช่วงเต็ม 2021–2025 ที่ใช้ประมาณ α จึงมีช่วงที่ใช้เลือกรูปแบบแล้ว · ไม่ใช่หลักฐานนอกช่วงที่อิสระ** ·
> (ค) ผลขึ้นกับค่าที่ยืนยัน 1–21 และค่าชั่วคราว 22–72 · (ง) **เกณฑ์ L4 ทั้งหมดในข้อ 7 "ออกแบบหลังเห็นผล L3"** (ข้อ 31) ·
> (จ) แถว ⚠️ (ชุดเข้ม 5 ดัชนี ไม่มี Vietnam · ข้อ 68) = **"เกณฑ์เปลี่ยนหลังเห็นผล"** · (ฉ) ธีม ACWI_CD = **"ธีมจากชื่อกอง"** (ข้อ 53) · (ช) FundProfile / SecFundFee = snapshot ไม่ใช่ point-in-time

---

## 0. ข้อเท็จจริงเชิงโครงสร้าง (ตรวจเอง · ไม่ใช่ผล)

| เรื่อง | ค่า | ผลต่อ spec |
|---|---|---|
| EVAL (`runs/S003/fund_level.csv` form 1a · `in_EVAL`) | 207 (E 175 · F 18 · O 14) · FIF Flag = Y ทั้ง 207 | ชุดหลักเดิม (ไม่เปลี่ยน) |
| กลุ่มกองอิสระ (`runs/S005/fund_clusters.csv` · corr ≥ 0.95 single linkage) | 168 กลุ่มใน EVAL | cluster ของ L4-2 · ตัวนับกลุ่ม |
| คู่ซ้ำ corr > 0.99 (`dup_pairs.csv`) ที่อยู่ใน EVAL ทั้งสองกอง | **0 คู่** | EVAL ตัดซ้ำแล้ว → ไม่ต้องตัดเพิ่ม (BRIEF 4) |
| MGAG / MGAPVD / M-SUKUK | อยู่ใน EVAL ทั้ง 3 | ข้อ 54 (นับ 1) · ข้อ 55 (ไม่อยู่กลุ่มธีม) |
| ธงปันผล (`universe.csv div_flag` = FundProfile `Dividend_Flag`) | panel 27 กอง (E22/F2/O3) · **ใน EVAL 17 กอง (E 14 · F 1 · O 2)** · รวม MGAG+MGAPVD (ทั้งคู่ Y) → 16 | ตาราง α class ปันผลแยก (ข้อ 52) · ตัวควบคุมใน L4-2 |
| FundProfile `FX Risk Flag` = N ใน EVAL | 13 กอง | บรรยายเท่านั้น (ไม่ใช่ตัวแปรหลัก · ใช้ FX β แทน) |
| คู่ hedge / unhedge (twin) ใน EVAL | ชื่อที่มี -H / (UH) 8 กอง · **ไม่มีคู่ twin ใดอยู่ใน EVAL ครบคู่** (ถูกยุบเป็น family ตาม Universe ข้อ 4) | twin test ของ F-R004 L4-1 (2) **ทำไม่ได้ใน panel** → "ต้องให้ผู้ใช้ตัดสินใจ" ข้อ 9 |
| `SecFundFee.csv` | 51,900 แถว · `Fund Code` = FundCode ของ FundProfile · `FEEMF` (TT, OF, FR, SP, EO, IA, UW) / `FEEUH` (ค่าซื้อขาย) · As of 149 วัน (2019-06 → 2026-08) | TER = FEEMF·TT (ข้อ 3.4) |
| FEEMF·TT ของ EVAL | มีทั้ง 207 กอง · `Actual Value` เป็นตัวเลข 205 · `Rate` ตัวเลข 207 · มีค่า as-of ≤ 2023-12-29 แค่ 103 กอง (97 กองเริ่ม 2023-05-10) | point-in-time ณ ต้นช่วงทำไม่ได้ → ใช้ as-of แรกสุดของแต่ละกอง (ป้าย) |
| `aum_weekly.parquet` | long 126,436 × (FundCode, date, aum) | log AUM เป็นภาคผนวกเท่านั้น (AUM มีรู · F-R004) |
| ป้ายกลุ่ม L2 (`primary_index.csv`) | form `none` = `1a@4` = `1c@4` **สมาชิกเหมือนกันทุกกลุ่ม** (ตรวจเอง) | ป้ายกลุ่มเดียวใช้ได้ทั้งสองฐาน |
| ขนาดกลุ่มตาม primary L2 (ทุก policy · n / กลุ่มอิสระ) | ACWI_CD 40/36 · CHINA_ALL 21/16 · ACWI 16/12 · ACWI_IT 15/12 · ASIA_EX_JAPAN 15/15 · ACWI_EX_US 12/11 · WORLD_EX_US 11/9 (E 4 · F 6) · ASEAN 8 (E 3 · O 5) · JAPAN 8/7 · INDIA 8/7 · EM 8/7 · HC 7/4 · EUROPE 6/5 · VIETNAM 6/3 · UT 5/4 (E 3 · F 2) · อื่น 8 กลุ่ม ≤ 4 กอง | กฎขนาดกลุ่ม ข้อ 3.6 (ต้องนับใหม่เฉพาะ E) |
| ปัจจัย FX ใน `factors_weekly` | `SHV_THB`, `SHV_USD` (ผลตอบแทนรายสัปดาห์ · QA_L0 Q8), `RF_BOT` · `USDTHB` / `DTB3_lvl` ห้ามใช้ (ข้อ 27 · `*_lvl`) | FX = SHV_THB − RF_BOT · SPOT/CARRY แยกจาก SHV (ข้อ 3.3) |
| lib ปัจจุบัน vs `runs/S006/run_meta.json` | sha256 ตรงทั้ง 13 ไฟล์ (12 เดิม + `l3.py`) · ไม่มีไฟล์เกิน · test สุดท้ายของ `test_l3.py` = 47 | regression ข้อ 8.3 · test ใหม่เริ่มเลข 48 |

---

## 1. คำถามและสมมติฐาน

**คำถาม L4 (BRIEF):** **Q1** ในกลุ่มเดียวกัน (ดัชนีหลัก / E-F-O / ธีม) มี factor เฉพาะกลุ่มไหม · **Q2** กองไหนมี α จริงหลังหัก factor ชุดสุดท้าย · **Q3** อะไรอธิบาย α ข้ามกอง

- **H4.1 (Q1 · L4-4):** residual ของ model α ยังสัมพันธ์กันภายในกลุ่มกองธีม / ประเทศที่ดัชนีไม่ครอบ → factor กลุ่ม (PCA ใน residual หรือค่าเฉลี่ย residual ของเพื่อนแบบ leave-one-out) เพิ่ม R²_oos ของกองในกลุ่มนั้น มากกว่ากลุ่มสุ่มขนาดเท่ากัน · กลุ่มดัชนีรวม (ACWI · ACWI ex US · World ex US · Asia ex Japan) ไม่มี factor เฉพาะ
- **H4.2 (Q2 · L4-1 + L4-3):** เมื่อใส่ FX factor แล้ว จำนวนกองที่ผ่าน BH (FDR 10%) น้อย และ**ไม่ต่างจากที่คาดภายใต้โชค** (bootstrap แบบ FF 2010) · หาง t(α) ด้านลบหนากว่า null (ค่าธรรมเนียม / ปันผล) ส่วนด้านบวกไม่ · α ต่ำสุดที่ตรวจจับได้ของกอง E ส่วนใหญ่ > 5 %/ปี → "ไม่พบ" ≠ "ไม่มี"
- **H4.3 (Q3 · L4-2):** α̂ ข้ามกองสัมพันธ์ทางลบกับ TER (slope ครอบ −1) และธงปันผล · หลังมี FX ใน model FX β ไม่อธิบาย α แล้ว · ความต่าง α ระหว่างกอง FX β ต่ำ / สูงในกลุ่มเดียวกัน (L1 9b) ลดลง ≥ ครึ่งเมื่อเทียบ model ที่ไม่มี FX
- **H4.4 (ความถูกต้อง):** แถวอ้างอิง L3-B (ไม่มี FX · ช่วง train) ทำซ้ำ `runs/S006/fund_level.csv` แถว R3 / R8 / R5 / R10 ได้ภายใน 1e-10 · SPOT + CARRY = FX ทุกแถว (1e-15)

ตัวเลขใน H = ความคาดหมายสำหรับตรวจตัวเอง ไม่ใช่เกณฑ์ผ่านอัตโนมัติ (เกณฑ์อยู่ข้อ 7)

---

## 2. ข้อมูล (ตรวจ sha256 ก่อนรัน · ไม่ตรง → หยุด)

| ไฟล์ | ใช้ทำ | sha256 |
|---|---|---|
| `data/panel_weekly.parquet` | ผลตอบแทนกอง | `95c16ee651d3a936788b7cb3c6372bbf5f1e84cb39daf5680343771dca24270b` |
| `data/panel_monthly.parquet` | ตรวจซ้ำรายเดือน | `e8e8cb5d5f04fba9bb35558ef7c3d8195c656334119e56f82775cc1ae21ccaed` |
| `data/factors_weekly.parquet` | M28 · RF_BOT · SHV_THB · SHV_USD · ACWI | `115b87139d2bec0fd57a77a1593c46d36bb23f3f35f83236cdb07be642af47a8` |
| `data/factors_monthly.parquet` | รายเดือน | `f7c4248b4fa889853024449e72ae8909cf1f8d3226a54eebc37448a2a485bb72` |
| `data/factors_ext_weekly.parquet` | ETF ส่วนขยาย (ตั้งชื่อ factor กลุ่มเท่านั้น · ข้อ 56) | `3105b6e7fe32ffd3648e8feac8dbd03a8db22b7e8eb245c5faf462b14da5e296` |
| `data/universe.csv` | family · `div_flag` | `fdfb7830df78ce032465ac9d8cddc2c98f9aa86cfa0f3925fdb83026aa3f7252` |
| `data/dup_pairs.csv` · `data/factor_groups.csv` | ตรวจซ้ำ · ลำดับเสมอ | `b1f0f0c745947fa70803a4f40526c0a1967c72925be985a2bedc1057d8b8aef3` · `42bf1cfb270721ae6112799ab795ebc4c91212e7584d5cdfee23b9b70b1b1731` |
| `data/aum_weekly.parquet` | log AUM (ภาคผนวก) | `48c34c73ae22ebffc6112f93e03f729223a496297bb65c324b693b817a723d26` |
| `runs/S003/factors_S003_weekly.parquet` | ①a / ①c k = 4 (ไม่ประมาณใหม่) | `be3ceb2e34b0df1f1a3db27d59e1a103cf5f5a5ca38f2e87f7c812c1c53944ac` |
| `runs/S003/fund_level.csv` | ธง EVAL / STAB | `36b41161d6a13c1184a4052d9e799f660f431c2694dc57fafd747f8e695bf8cf` |
| `runs/S003/grs_ports.csv` | พอร์ต GRS 17 | `d55011094898acdf6e0419c90a3b2713479451380cacc0bf950559c43b98ba19` |
| `runs/S005/primary_index.csv` | ป้ายกลุ่ม (form `1a@4` / `1c@4`) + primary ของ B-prim | `5a94ab9b498bb107600938d37f665c7263d9f0a5973460159c09ae83a799275c` |
| `runs/S005/fund_clusters.csv` | กลุ่มกองอิสระ 168 | `072cd97ade7e01a32edb9aaf5b949381d1500dcb1ed909558bee3a373e2fc0cb` |
| `runs/S005/criteria_P4.json` | P4 | `0db21831202f8ff2378923740074d2517be1a37563d5f09a64e103d8651cbfb2` |
| `runs/S006/fund_level.csv` | ค่าอ้างอิง L3-B (test 50) | `2fc1d735f52669d1034707c5d9c0194b087e91aff5dbfb91b2fd59ac4f85f5d2` |
| `runs/S006/resid_B_coef.csv` | b̂ ของ e_j (ใช้ตรงตัว · ไม่ประมาณใหม่) | `71af654fc789a24d79999d96d7149e05e75007ac6e8f83d33bd0355d292eef0b` |
| `runs/S006/run_meta.json` | lib_sha256 อ้างอิง | `3abb04b19c97223ed72d062a21216d3befc0e67805e3f60298a22e02603ec5ef` |
| `base_data/SecFundFee.csv` (อ่านอย่างเดียว) | TER | `94f0b7716a7979303ef6ba063746061d7e454c8e966731b567aa29316f0134cd` |
| `base_data/FundProfile.csv` (อ่านอย่างเดียว · `load_fund_profile` หรือ pandas) | FX Risk Flag · Registration_date (บรรยาย) | `9516281426fc854c8f3a0833f119cad0ce581adb39450732e579084cb4cedfaf` |
| `data/QA_ACWI_CD_group.md` | ตารางธีม 40 กอง (hardcode ใน `l4.py` + test 52 ตรวจกับไฟล์) | analyst บันทึก sha ใน `run_meta.json` |
| regression: `runs/S003/run.py` · `runs/S005/run.py` · `runs/S006/run.py` | ข้อ 8.3 | `9f21e388…5590f` · `c51e3d61…98fee` · `5515b289…4f760` (เต็มใน structure.json) |

**ช่วงเวลา / ชุดกอง เหมือน L1–L3:** train 2021-01-08 → 2023-12-29 (Dimson 155 แถว) · test 2024-01-05 → 2025-12-26 (104) · **full** = 2021-01-08 → 2025-12-26 (Dimson ≤ 259 แถว · ใหม่ใน L4 สำหรับ α) ·
H1/H2 ตาม S002 · EVAL 207 · STAB 191 · PY_test 206 · ห้ามใช้ข้อมูล ≥ 2026-01-01 (ข้อ 6) · `*_late_*`, `*_lvl`, `*_est_ret`, `Gold` (USD), `USDTHB` ไม่ใช้

---

## 3. ตัวแปร

### 3.1 ชุด factor (ข้อ 67, 68)
- f = ①a (`1a__PC1..4`) หรือ ①c (`1c__PC1..4`) k = 4 ผ่าน `l2.load_l1_factors` · e_j = I_j − b̂_j′f โดย b̂ อ่านจาก `runs/S006/resid_B_coef.csv` (**ไม่ประมาณใหม่** · test 49 ยืนยันว่าเท่ากับ `l3.residualize` บน train 1e-12)
- **L3-B:** ต่อกอง i — ถ้า primary ของ L2 (form `1a@4` / `1c@4`) ∈ P4 → [f, e_p(i)] · มิฉะนั้น [f] (= B-prim ของ S006) · **L3-B5 ⚠️:** เหมือนกันแต่กองหลัก Vietnam = [f]
- UT / Europe คงไว้ใน L3-B พร้อมป้าย "เปราะ (ไม่ผ่านบางเลนส์)" (ข้อ 67)

### 3.2 FX factor บังคับ (F-R004 L4-1 · ข้อ 20)
**FX = SHV_THB − RF_BOT** (`external.line3(F, "3a")["FX"]` · test 48 ยืนยันตรง) — ใส่ใน**ทุก** model α ของ L4 (lag 0 + 1 ตาม Dimson) · ไม่ residualize FX บน f (span เท่ากันอยู่แล้ว · α ไม่ขึ้นกับการตั้งชื่อ)

### 3.3 SPOT / CARRY (hedge-cost · ย้ายจาก L1 ข้อ 9 · ภาคผนวก)
**SPOT = SHV_THB − SHV_USD** (ผลของค่าเงินต่อสินทรัพย์ดอลลาร์ระยะสั้น) · **CARRY = SHV_USD − RF_BOT** (ผลตอบแทนเงินดอลลาร์ระยะสั้นส่วนเกินดอกเบี้ยไทย ≈ ต้นทุน/ผลได้ของการ hedge ตาม CIP) → SPOT + CARRY = FX **เป็นเอกลักษณ์** (test 48) ·
ใช้เฉพาะแถวภาคผนวก H1/H2 (แทน FX ด้วย SPOT + CARRY) · ป้าย: SHV_USD เป็นผลตอบแทน ETF (มีราคาขยับเล็กน้อย) ไม่ใช่อัตราดอกเบี้ยบริสุทธิ์ · CARRY เคลื่อนช้า → อาจแยกจากค่าคงที่ได้ยาก (รายงาน VIF ของ CARRY กับค่าคงที่ = corr(CARRY, 1) ผ่าน R² ของ CARRY บน [1, trend]) · กลไก CIP ผ่าน F-R004 / F-R001 ④-3 (หลักฐาน "อ่อน–ปานกลาง")

### 3.4 คุณลักษณะกอง (L4-2 · เขียน `chars.csv` **ก่อน** fit model α ใดๆ)
| ตัวแปร | นิยาม (ล็อก) | ที่มา |
|---|---|---|
| **TER** (%/ปี) | SecFundFee · `Complex Type Code = FEEMF` · `Code = TT` · `Actual Value` ที่ **As of Date แรกสุดของกองนั้น** (ใกล้ต้นช่วงที่สุดที่มี) · แปลงข้อความ: "ไม่มี / ยกเว้น / ไม่เรียกเก็บ" → 0 · "x%" → x · อ่านไม่ได้ → ใช้ `Rate` แทน + ธง `ter_src = rate` | **ป้าย: ความหมาย TT = "ค่าใช้จ่ายรวม" อนุมานจากโครงไฟล์ ยังไม่ยืนยันกับเอกสาร ก.ล.ต.** · QA ก่อนรัน: สัดส่วนกองที่ TT ≥ OF (ตัวเลขทั้งคู่) ≥ 90% มิฉะนั้นหยุดรายงาน · ภาคผนวก: TER ที่ as-of ล่าสุด ≤ 2025-12-31 (corr กับตัวหลัก · บรรยาย) |
| **DIV** | `universe.csv div_flag` = Y → 1 | NAV ไม่รวมปันผล → α ติดลบเชิงกล (F-R004 L4-2) |
| **FXβ** | Dimson b0 + b1 ของ FX ใน y ~ [MKT, FX] ช่วง **train** (MKT = MSCI_ACWI − RF_BOT) · ทุก policy | นิยามเดียวกับกลไก L4-1 · regressor ที่ประมาณเอง (ป้าย) |
| **1−R²** | 1 − adj R² ของ model α หลัก (M1 / M2) ช่วง train | Amihud–Goyenko 2013 (F-R001) · regressor ที่ประมาณเอง |
| **policy** | dummy F, O (ฐาน = E) | BRIEF |
| **group** | dummy กลุ่ม E ที่ n_indep ≥ 10 (ข้อ 3.6) · กลุ่มอื่นของ E รวม "E-อื่น" (ฐาน) | ข้อ 69 |
| log AUM (ภาคผนวก) | log(aum) สัปดาห์แรกที่มีค่าใน train · ใช้เมื่อครอบคลุม ≥ 80% ของ EVAL มิฉะนั้น N/A | F-R004 · Ferreira et al. 2013 |
| FX Risk Flag (บรรยาย) | FundProfile = N (13 กอง) | snapshot · ไม่เข้า regression (ซ้อนกับ FXβ) |

ไม่ใช้ `FEEUH` (ค่าซื้อขายหน่วย ไม่หักจาก NAV)

### 3.5 ชุดกองของ α (ข้อ 52, 54)
- **α-family N = 206** = EVAL 207 − MGAPVD (**MGAG เป็นตัวแทน** · ชนิดผู้ลงทุนทั่วไป · ข้อ 54) · MGAPVD รายงานค่าเชิงบรรยายในตารางแยก · class ปันผล (16 กองหลังรวม) **อยู่ใน family พร้อมธง** + ตารางแยก (ข้อ 52)
- ทุกจำนวนกองที่รายงานให้นับคู่เป็น**กลุ่มกองอิสระ** (S005 · 168)

### 3.6 ป้ายกลุ่ม (ข้อ 69 · กติกาของ designer · ป้าย)
- **G-E:** กอง E ตามดัชนีหลักของ L2 (`primary_index.csv` form `1a@4` สำหรับ ①a · `1c@4` สำหรับ ①c — สมาชิกเท่ากัน) · M-SUKUK (F) ไม่อยู่กลุ่ม ACWI_CD (ข้อ 55) · MGAG+MGAPVD = 1 (ข้อ 54)
- **G-F / G-O:** กอง F 18 และ O 14 เป็นกลุ่มละ 1 (n เล็ก · primary ผสม)
- **G-T (ชั้นย่อยของ ACWI_CD · บรรยาย):** ธีมจากชื่อกองตาม `QA_ACWI_CD_group.md` (เทคโนโลยี 9 · Healthcare 6 · Global ทั่วไป 10 หลังรวม MGAG · EV 3 · Consumer 4 · ESG 3 · หลายธีม 3) — ป้าย (ฉ)
- **G0 (diagnostic):** กอง E ทั้งหมด 175 — ยังมี factor ร่วมที่ขาดไหม
- **กฎวิธีตามขนาด (ล็อก · นับ n_indep = จำนวนกลุ่มกองอิสระภายในกลุ่ม · F-R004 L4-4):** n_indep ≥ 10 → **PCA กลุ่ม** · 5 ≤ n_indep ≤ 9 → **LOO-mean** (k = 1) · n_indep < 5 → ไม่สร้าง factor กลุ่ม ("กลุ่มเล็กเกิน")
- dummy กลุ่มใน L4-2 ใช้เฉพาะกลุ่ม G-E ที่ n_indep ≥ 10

---

## 4. รูปแบบ (ล็อก — ลองนอกนี้ = spec ใหม่)

### 4.1 model α (fit รายกอง · Dimson lag 0 + 1 · HAC NW L = 4)
| แถว | ชุด | ฐาน | K ต่อกอง | ชนิด |
|---|---|---|---|---|
| **M1** | L3-B + FX | ①a | 5 หรือ 6 | **หลัก** |
| **M2** | L3-B + FX | ①c | 5 หรือ 6 | **หลัก** |
| M3 ⚠️ | L3-B5 + FX | ①a | 5 หรือ 6 | ชุดเข้ม (ข้อ 68) |
| M4 ⚠️ | L3-B5 + FX | ①c | 5 หรือ 6 | ชุดเข้ม |
| H1 / H2 | L3-B + SPOT + CARRY | ①a / ①c | 6 หรือ 7 | ภาคผนวก (hedge-cost / carry) |

**แถวอ้างอิง / diagnostic (ไม่ใช่รูปแบบใหม่):** **ref-L3B** = L3-B ไม่มี FX ช่วง train (ต้องตรง S006 R3 / R8 / R5 / R10 ภายใน 1e-10 · test 50) · **ref-L3B-full** = L3-B ไม่มี FX ช่วง full (เทียบผลของการใส่ FX) · **ref-FX** = f + FX (factor ร่วม · ①a / ①c — ทำ GRS / PY / rolling ได้)
**ช่วงประมาณ α:** **หลัก = full** (power สูงสุด) · train = ภาคผนวก (เทียบ L1–L3 ได้ตรง) · test = ใช้เฉพาะ R²_oos (coef จาก train) และ X3 ข้อ 4.4

### 4.2 การอนุมาน α รายกอง (F-R004 L4-3) — ทำบน M1, M2 (หลัก) และ M3, M4 (BH เท่านั้น)
1. t_HAC(α̂_i) → p สองด้าน (แบบเดียวกับ `fit_funds` / L1–L3) → **BH FDR 10%** (หลัก) + **BY** (คู่ · F-R003 PRDS ไม่ครอบ t สองด้าน) บน N = 206 ต่อแถว · แยก family ต่อแถวและต่อช่วง
2. **bootstrap แบบ Fama–French 2010 (block):** null ต่อกอง y\*_it = y_it − α̂_i (บังคับ α = 0 ทุกกองพร้อมกัน · model หลักช่วง full) · สุ่ม **moving block 4 แถว (สัปดาห์) ของช่วง full ร่วมกันทุกกองและทุก factor** (ดึงแถวของ [y\*, X_t, X_t−1] ทั้งแถว → รักษา cross-correlation และโครง Dimson) · จำนวนบล็อก ⌈T/4⌉ ตัดเหลือ T · B = 999 · `np.random.default_rng(20261015)` ใหม่ต่อแถว · กองเข้าในรอบนั้นเมื่อมี ≥ 104 แถวไม่ขาด ·
   ต่อรอบ: fit ใหม่ → t\*(α) ทุกกอง → percentile ข้ามกอง {1, 5, 10, 50, 90, 95, 99} (ALL และ E) + จำนวน BH reject + จำนวน |t\*| > 1.96 แยกทิศ ·
   **p_boot** ต่อ percentile = สัดส่วนรอบที่ค่าจำลอง ≥ ค่าจริง (percentile บน) / ≤ ค่าจริง (percentile ล่าง) · **p_boot ของจำนวน BH** = สัดส่วนรอบที่จำนวน BH จำลอง ≥ จำนวนจริง · ป้าย Harvey–Liu 2022 (FF 2010 มีปัญหา undersampling — ไม่ปฏิเสธแม้มีกองที่ α สูง)
3. **α ต่ำสุดที่ตรวจจับได้ (power 80% · สองด้าน 5%):** MDA_i = (z₀.₉₇₅ + z₀.₈₀) · se_HAC(α̂_i) · 52 · 100 (%/ปี) · และแบบหลายการทดสอบ MDA_i^mt = (z_{1−0.10/(2N)} + z₀.₈₀) · se · 52 · 100 (ขอบบนแบบ Bonferroni ของการปฏิเสธตัวแรกของ BH — **การประมาณของ designer** · สูตร power มาตรฐาน · ไม่ได้มาจากบทความเฉพาะ) · รายงาน median / IQR ต่อ policy และต่อกลุ่ม
4. **ตาราง class ปันผล (ข้อ 52):** 16 กอง (+ MGAPVD บรรยาย): α̂ · t · BH · MDA · กลุ่ม — α ติดลบของกองกลุ่มนี้ติดธง "อาจเป็นผลของ NAV ไม่รวมปันผล"
5. **ตรวจซ้ำรายเดือน:** M1 / M2 รายเดือน (HAC L = 3 · ใช้ดัชนีหลักดิบแทน e เพราะ span เท่ากัน และ e เก็บค่าคงที่ → α เท่ากันทางคณิตศาสตร์ ตาม S006 ข้อ 3.4) → BH count + Spearman ของ α̂ รายสัปดาห์ vs รายเดือน (บรรยาย)

### 4.3 factor เฉพาะกลุ่ม (F-R004 L4-4 · Q1) — บน residual ของ M1 และ M2 (ไม่ทำกับ M3/M4/H)
- residual u_it = y_it − X_it b̂_i^train (ทุก t · coef จาก train) · train ใช้ประมาณ / test ใช้วัด
- **PCA กลุ่ม (n_indep ≥ 10):** สำหรับแต่ละกอง i ในกลุ่ม: PCA บน correlation ของ u (train · กองในกลุ่มที่ครบทุกแถว train **ไม่รวม i**) → k_g = **min(k_ED, k_PA)** (`nfactors.onatski_ed` / `parallel_analysis` n_perm 500 · q 0.95 · kmax 3 · k_g = 0 ได้) — k_g กำหนดครั้งเดียวต่อกลุ่มจากชุดเต็มของกลุ่ม (รายงาน) แล้วใช้ k_g เดิมใน LOO · factor ของ i = `pca.factor_returns` ของ peer (น้ำหนัก train ตรึง · min_frac 0.5) ทั้ง train และ test
- **LOO-mean (5 ≤ n_indep ≤ 9):** g_{−i,t} = ค่าเฉลี่ย u ของเพื่อนในกลุ่มที่มีค่า ณ t (ต้อง ≥ 3 กอง มิฉะนั้น NaN → แถวหลุด)
- กองซ้ำ corr ≥ 0.95 (กลุ่มกองอิสระเดียวกับ i) **ไม่ถูกนับเป็นเพื่อนของ i** (กัน factor กลุ่มเป็นสำเนาของกองตัวเอง)
- fit: y_i ~ X_i + g_{−i} (Dimson ทั้งคู่) ช่วง train → ΔR²_oos (test) · ΔBIC (train) · Δ adj R² เทียบ model α บนแถวเดียวกัน · mean |corr| ของ u ภายในกลุ่มก่อน / หลัง (train) · α̂ ใหม่ (บรรยาย — factor กลุ่มลงทุนไม่ได้)
- **null กลุ่มสุ่ม:** ต่อกลุ่ม g สุ่มกอง E ที่ไม่อยู่ใน g จำนวน n_g กอง 200 รอบ (`default_rng(20261015)` ใหม่ต่อกลุ่ม × ฐาน · กลุ่มเรียงตามชื่อ) ทำวิธีเดียวกัน (PCA ใช้ k_g ของกลุ่มจริง) → percentile 95 ของ median ΔR²_oos
- **ตั้งชื่อ factor กลุ่ม (บรรยาย · F-R004 L4-5):** corr (train / test) ของ factor กลุ่ม (ฉบับรวมทุกกองในกลุ่ม) กับ e ของ M28 ที่ residualize บน f ด้วย `l3.residualize` และ ETF ส่วนขยาย 14 ตัว (`l3.ext_excess`) — **ไม่ใช้เลือกอะไร** · ป้าย "ชื่อ" เมื่อ |corr| ≥ 0.7 ทั้งสองช่วง · "คล้าย" 0.5–0.7
- G0: PCA ของ u กอง E ทั้งหมด (balanced train) → k_ED, k_PA, eigenvalue 1–5 (diagnostic ว่ายังมี factor ร่วมขาด)
- G-T (ธีม): LOO-mean เฉพาะธีมที่ n ≥ 5 (เทคโนโลยี · Healthcare · Global) บน residual หลังใส่ factor กลุ่ม ACWI_CD แล้ว (ส่วนเพิ่มของธีมเหนือกลุ่ม) · บรรยาย

### 4.4 α ข้ามกอง ~ คุณลักษณะ (F-R004 L4-2 · Q3)
y_i = α̂_i (%/ปี) · น้ำหนัก w_i = 1/se_HAC(α̂_i)² · SE แบบ **cluster CR1** ตามกลุ่มกองอิสระ S005 (คูณ G/(G−1)·(N−1)/(N−K)) + HC1 คู่ · Wald ร่วมของ dummy กลุ่ม (cluster)
| สเปก | α̂ จาก | กอง | ตัวแปร | ใช้กับ |
|---|---|---|---|---|
| **X1 (หลัก)** | M (full) | ALL 206 | 1, TER, DIV, FXβ, 1−R², F, O, dummy กลุ่ม | M1, M2, M3 ⚠️, M4 ⚠️ |
| **X2 (หลัก · E)** | M (full) | E | 1, TER, DIV, FXβ, 1−R², dummy กลุ่ม | M1, M2 |
| X3 (ทนทาน · ไม่ซ้อนช่วง) | model เดียวกัน fit **เฉพาะช่วง test** (T = 104) | ALL | เหมือน X1 (คุณลักษณะจาก train) | M1, M2 |
| X4 (ภาคผนวก) | M (full) | ALL | เหมือน X1 แต่ OLS | M1, M2 |
| X5 (ภาคผนวก) | M (full) | ALL | X1 + log AUM (ถ้าครอบคลุม ≥ 80%) | M1, M2 |
รวม **12 regression** · รายงานสัดส่วนน้ำหนัก WLS ของกอง F (กอง F se เล็ก → อาจครอบงำ) · ห้ามเลือกตัวแปรหลังเห็นผล

### 4.5 ตาราง FX gap (L4-1 · H4.3 ส่วนหลัง)
ต่อกลุ่ม G-E ที่ n ≥ 10 กอง: แบ่งกองที่ FXβ ต่ำกว่า / สูงกว่าค่ามัธยฐานของกลุ่ม → gap = median α̂ (ต่ำ) − median α̂ (สูง) ภายใต้ ref-L3B-full (ไม่มี FX) และ M1 / M2 (มี FX) · ratio = |gap_FX| / |gap_noFX| · บรรยายคู่: Δα_i = α̂_i(ไม่มี FX) − α̂_i(มี FX) เทียบ β̂_FX,i × mean(FX) (ความสัมพันธ์เชิงพีชคณิตของตัวแปรที่ขาด)

---

## 5. การทดสอบทางสถิติ

### 5.1 กติการ่วม (เหมือน S003 / S005 / S006)
Dimson lag 1 (β = b0 + b1) · HAC Newey–West Bartlett L = 4 (รายเดือน L = 3) · seed 20261015 · `kind="stable"` · ทุกน้ำหนัก / b̂ / k_g / ป้ายกลุ่ม / คุณลักษณะ ประมาณจาก **train** แล้วตรึง (ยกเว้น α̂ ช่วง full ที่เป็นเป้าของ L4 และ X3) · R²_oos = 1 − Σ(y − ŷ)²/Σ(y − ȳ_test)² ด้วย coef train · Δ เทียบบนกองและแถวเดียวกัน

### 5.2 multiple testing (ล็อก)
| ตระกูล | จำนวน | วิธีหลัก | คู่ / ภาคผนวก |
|---|---|---|---|
| α รายกอง ต่อแถว M ต่อช่วง | 206 | BH FDR 10% | BY · bootstrap FF 2010 (ระดับ cross-section) |
| factor กลุ่ม (กลุ่มที่สร้างได้ × 2 ฐาน) | ≤ ~12 กลุ่ม | กฎเชิงขนาด + null กลุ่มสุ่ม 95% (ข้อ 7) | — |
| สัมประสิทธิ์ L4-2 | 5 ตัวแปรหลัก × 12 regression | CI 95% cluster · **ไม่แก้ multiple testing** (บรรยาย · ตัวแปรล็อกก่อน) · ป้าย | HC1 |
| FX gap | ≤ 6 กลุ่ม | บรรยาย | — |
ระยะ 1 ไม่นับ trial

---

## 6. ตารางคะแนนที่รายงาน + ตัวชี้เฉพาะ L4 (`runs/S007/`)

**ตารางกลาง 6 ข้อ** (แยก E / F / O / ALL + n · EVAL หลัก) ต่อแถว M1–M4, H1–H2, ref-L3B, ref-L3B-full, ref-FX:
**1** median / IQR adj R² (train) + Δ เทียบ ref-L3B · **2** median / IQR R²_oos + Δ + gap · **3** mean|α̂| (train · เทียบ L1–L3) + mean|α̂| (full) · signed · BH (train / full) · GRS (17 พอร์ต · เฉพาะ ref-FX · L = 10) · PY p / p_boot (ref-FX · แถวต่อกอง N/A แบบ S006) ·
**4** K · median BIC · ΔBIC เทียบ ref-L3B · **5** r ดิบ H1/H2 (STAB · รวม β_FX) · rolling 104 (`l2.rolling_betas` · เฉพาะ ref-FX) · **6** ชื่อ (FX = "เงินดอลลาร์ระยะสั้นส่วนเกิน" · SPOT / CARRY · e = "ส่วนของดัชนีที่ตั้งฉากกับ factor")
bootstrap CI ของ median Δ (2,000 รอบ · ป้าย "CI สุ่มกองอิสระภายใน policy — กองสัมพันธ์กัน → CI แคบกว่าจริง")

**ไฟล์เฉพาะ L4:** `chars.csv` · `ter_qa.json` · `groups.csv` (ป้าย · n · n_indep · วิธี) · `alpha_fund.csv` (ทุกแถว × ช่วง: α̂ %/ปี · se · t · p · BH · BY · MDA · MDA_mt · ธงปันผล / FX flag / กลุ่ม) · `alpha_bh_list.csv` (กองที่ผ่าน BH พร้อมกลุ่มอิสระ) · `alpha_div.csv` · `alpha_by_group.csv` · `ff_boot.csv` + `ff_boot_summary.csv` · `mda.csv` · `group_factor.csv` (ต่อกลุ่ม × ฐาน: วิธี · k_ED · k_PA · k_g · median ΔR²_oos · ΔBIC · null p95 · |corr| ก่อน/หลัง · ชื่อ) · `group_factor_fund.csv` · `group_names.csv` · `g0_pca.csv` · `xsec.csv` (coef · CR1 · HC1 · Wald กลุ่ม · น้ำหนัก F) · `fx_gap.csv` · `carry_diag.csv` · `monthly.csv` · `scorecard.csv` · `fund_level.csv` · `bootstrap.csv` · `grs.csv` · `py.csv` · `stability.csv` · `rolling_104.csv` · `expectations_vs_results.csv` · `results.md` · `run.log` · `run_meta.json` · `regression_S003_S005_S006.json`

**ลำดับเขียนบังคับ (timestamp ใน run.log):** regression (ข้อ 8.3) → `ter_qa.json` → `chars.csv` (TER · DIV · FXβ) → `groups.csv` → fit ref-L3B + test 50 → fit M/H → `alpha_fund.csv` → ff_boot → group factor → xsec → ตารางที่เหลือ
(1−R² ใน `chars.csv` เติมหลัง fit M1/M2 · เป็นคอลัมน์เดียวที่เขียนทีหลัง — ป้าย)

---

## 7. เกณฑ์ L4 (ล็อกก่อนรัน · ⚠️ ออกแบบหลังเห็นผล L3 · ผู้ใช้ตัดสินข้อสรุปสุดท้าย)

**technical validity:** test ใหม่ 48–60 + เดิมทั้งหมดผ่าน · regression S003 / S005 / S006 ตรงทุกบิต · ref-L3B ตรง S006 ≤ 1e-10 · SPOT + CARRY = FX ≤ 1e-15 · ไฟล์ข้อ 6 เขียนก่อน fit ตามลำดับ · รันซ้ำ 2 รอบ sha256 ทุกไฟล์ผลเท่ากัน

**Q1 — กลุ่ม g "มี factor เฉพาะกลุ่ม"** เมื่อ**ทั้ง ①a และ ①c (M1, M2)**: (i) median ΔR²_oos ของกองในกลุ่ม ≥ **0.02** **และ** (ii) median ΔBIC ≤ **0** **และ** (iii) median ΔR²_oos > percentile 95 ของ null กลุ่มสุ่ม · ผ่านฐานเดียว = "บางส่วน" · PCA กลุ่มที่ k_g = 0 = "ไม่มี" โดยตรง (ค่า 0.02 / ΔBIC ≤ 0 = ค่าที่ล็อกแล้วตั้งแต่ L2 · ไม่มีค่าตัดใหม่นอกจาก null 95%)

**Q2 — กอง i "มีหลักฐาน α"** เมื่อ: (i) BH reject (FDR 10%) ช่วง full ใน **M1 และ M2** **และ** (ii) เครื่องหมาย α̂ ช่วง train เดียวกัน · ผ่านฐานเดียว = "บางส่วน" · **ระดับ cross-section:** ถ้า p_boot ของจำนวน BH (M1 และ M2) > 0.10 → ทั้งรายการติดป้าย **"แยกจากโชคไม่ได้"** · α < 0 ของกอง DIV = 1 ติดธง "อาจเป็นผลปันผล" (ไม่นับเป็นหลักฐาน α ติดลบ) · ทุกกองที่ไม่ผ่านรายงานคู่ MDA (ห้ามเขียน "ไม่มี α")

**Q3 — คุณลักษณะ "อธิบาย α"** เมื่อ CI 95% (CR1) ไม่คร่อม 0 ใน X1 ของ**ทั้ง M1 และ M2** · TER: "สอดคล้องค่าธรรมเนียมหัก 1:1" เมื่อ CI ครอบ −1 ทั้งสองฐาน · กลุ่ม: Wald ร่วม (cluster) p < 0.05 ทั้งสองฐาน · X2–X5 = ความทนทาน (รายงานว่าทิศ / ความมีนัยเปลี่ยนไหม)

**FX (H4.3 ส่วนหลัง):** "FX อธิบายความต่างของ L1 9b" เมื่อ median ratio ข้ามกลุ่ม (ข้อ 4.5) ≤ **0.5** ทั้งสองฐาน · ค่า 0.5 = ร่างสมมติฐานของ F-R004 (H-L4-2c "ลดลง ≥ ครึ่ง")

ชุดเข้ม (M3/M4 ⚠️) รายงานคู่ด้วยเกณฑ์ Q2 / Q3 เดียวกัน · ไม่ใช้ตัดสินแทนชุดหลัก

---

## 8. โค้ด (`lib/l4.py` ใหม่ · analyst เขียน · **ไม่แก้ฟังก์ชันหรือไฟล์ lib เดิม**)

### 8.1 ใช้ของเดิม
`io_l1.*` · `samples.window_mask / eligible` · `regress.dimson_design / ols_hac / fit_funds / CommonFactors / oos_r2_funds` · `external.line3` · `nfactors.onatski_ed / parallel_analysis / corr_eig` · `pca.pca_fit / factor_returns` · `tests_stat.bh / grs / pesaran_yamagata / py_null_bootstrap / bootstrap_median / block_indices` · `scorecard.score_model / stability_halves` · `l2.load_l1_factors / index_set / AugmentedFactors / by / rolling_betas / count_groups` · `l3.P4 / P4_STRICT / residualize / ext_excess / perfund_from_primary / fit_perfund / merge_fits / rolling_perfund`

### 8.2 ฟังก์ชันใหม่ (`lib/l4.py`)
| ฟังก์ชัน | input → output |
|---|---|
| `fx_factor(F)` · `spot_carry(F)` | → Series FX · DataFrame (SPOT, CARRY) ตัดแถว ≥ 2026-01-01 |
| `e_from_s006(I, f, coef_csv, base)` | → e_j ของ P4 จาก b̂ ใน `resid_B_coef.csv` |
| `parse_fee(s)` · `ter_table(fee, funds, rule="earliest")` | → DataFrame (FundCode, ter, ter_src, asof) · `ter_qa(fee, funds)` → dict |
| `fx_beta(R, F, mask_tr, funds)` | → Series (Dimson b0+b1 ของ FX ใน y ~ MKT + FX) |
| `group_labels(prim, pol, clusters, themes, merge={"MGAPVD":"MGAG"}, excl={"MSCI_ACWI_CD":["M-SUKUK"]})` | → DataFrame (FundCode, group, n, n_indep, method) ตามกฎข้อ 3.6 |
| `THEMES_ACWI_CD` (ค่าคงที่) | map 40 กอง → ธีม ตาม `QA_ACWI_CD_group.md` |
| `alpha_table(fit, N_mt, ann=52)` | → α %/ปี, se, t, p, BH, BY, MDA, MDA_mt |
| `ff_bootstrap(R, design_fn, funds, mask, alpha_hat, B=999, block=4, seed=20261015, min_rows=104, pcts=(1,5,10,50,90,95,99))` | → long DataFrame ต่อรอบ + สรุป p_boot |
| `resid_panel(R, design_fn, fit_tr, funds)` | → u (ทุก t · coef train) |
| `group_factor_loo(u, members, clusters, method, k, mask_tr)` | → dict กอง → Series factor ของเพื่อน (PCA / mean) |
| `group_k(u, members, mask_tr, kmax=3, n_perm=500, seed)` | → (k_ED, k_PA, k_g) |
| `random_group_null(u, pool, n_g, method, k, n_draw=200, seed)` | → percentile 95 ของ median ΔR²_oos |
| `xsec_wls(y, se, X, clusters, weights="inv_var")` | → coef, CR1, HC1, Wald |
| `fx_gap(alpha_a, alpha_b, fxb, groups, min_n=10)` | → ตาราง gap / ratio |
| `runs/S007/run.py` | รันเดียวจบตามลำดับข้อ 6 |

### 8.3 regression (ทำก่อนรัน S007 · ไม่ผ่าน → หยุด)
1. sha256 ของ lib 13 ไฟล์ = `runs/S006/run_meta.json` (`lib_sha256`) — เพิ่มได้เฉพาะ `l4.py` + `tests/test_l4.py`
2. รัน `runs/S003/run.py`, `runs/S005/run.py`, `runs/S006/run.py` ลง `scratch/factor-analyst_s00{3,5,6}_regress4/` (ห้ามเขียนทับ `runs/`) → sha256 ทุกไฟล์ผลตรงไฟล์เดิม ยกเว้น `results.md`, `run.log`, `run_meta.json`, `repro_check.*` (+ เทียบ field ของ `run_meta.json` ยกเว้นเวลา / lib entry ใหม่ · `placebo_rule.json` เทียบเนื้อหา) → `runs/S007/regression_S003_S005_S006.json`

### 8.4 test ใหม่ (`lib/tests/test_l4.py` · `pytest -p no:cacheprovider` · test เดิมต้องผ่านทั้งหมด)
48. `fx_factor` = `external.line3(F,"3a")["FX"]` (1e-15) · SPOT + CARRY = FX (1e-15) · ไม่มีแถว ≥ 2026 · ไม่ใช้ `USDTHB` / `*_lvl`
49. `e_from_s006` = `l3.residualize(I, f, mask_tr)` (1e-12) · แก้ข้อมูล test → e train ไม่เปลี่ยน
50. ref-L3B (train) ตรง `runs/S006/fund_level.csv` R3 / R8 / R5 / R10: α, t_alpha_hac, adj_r2, bic, r2_oos (1e-10) — อยู่ใน run.py เป็นเงื่อนไขก่อนรายงาน
51. `parse_fee`: "ไม่มี" → 0 · "0.535%" / "0.535" → 0.535 · ข้อความอื่น → NaN · `ter_table` เลือก as-of แรกสุด · fallback `Rate` ติดธง
52. `THEMES_ACWI_CD` ตรงตารางใน `QA_ACWI_CD_group.md` (parse md) · 40 กอง · M-SUKUK = "ผิดกลุ่ม"
53. `group_labels`: MGAPVD → MGAG · M-SUKUK ไม่อยู่ ACWI_CD · n_indep นับตาม cluster · กฎ ≥10 / 5–9 / < 5 ถูกต้องบนตัวอย่างมือ
54. `alpha_table`: MDA ตรงสูตร · α ต่อปี = α สัปดาห์ × 52 × 100 · BH = `tests_stat.bh` · BY = `l2.by`
55. `ff_bootstrap` (ข้อมูลจำลอง): α จริง = 0 ทุกกอง → สัดส่วน BH reject เฉลี่ย ≤ 0.10 + tolerance · กองที่ใส่ α ใหญ่ → percentile 99 จริงเกิน null (p_boot < 0.05) · บล็อกเดียวกันทุกกอง (ตรวจ index) · deterministic ที่ seed · แถวคู่ lag อยู่ด้วยกัน
56. `group_factor_loo`: factor ของ i ไม่ขึ้นกับ y_i (แก้ y_i → factor ของ i ไม่เปลี่ยน) · กองใน cluster เดียวกับ i ไม่ถูกใช้ · PCA ใช้น้ำหนัก train (แก้ข้อมูล test → น้ำหนักไม่เปลี่ยน)
57. `group_k` / `random_group_null`: ข้อมูลจำลองที่มี factor กลุ่ม 1 ตัว → k_g = 1 และผ่าน null · ไม่มี factor → k_g = 0 · deterministic
58. `xsec_wls`: ตรง statsmodels-free การคำนวณมือ (WLS + CR1 · 1e-10) · cluster = กองละ cluster → เท่ากับ HC1 ปรับ df
59. `fx_gap`: ตัวอย่างมือ
60. **no look-ahead:** แก้ผลตอบแทน / factor ช่วง test → `chars.csv` (TER · DIV · FXβ) · `groups.csv` · k_g · น้ำหนัก PCA กลุ่ม ไม่เปลี่ยน · `run.py` 2 รอบ → sha256 เท่ากัน

---

## 9. ผลลัพธ์ที่คาดไว้ล่วงหน้า (เขียนก่อนเห็นผล · `expectations_vs_results.csv` ต้องมีทุกข้อ)

1. **FX ใน model:** median adj R² (E) ของ M1/M2 สูงกว่า ref-L3B ≤ 0.01 · ΔBIC (E) ใกล้ 0 (±3) · กองที่ FX Risk Flag = N (13) มี β_FX ติดลบชัดกว่ากองอื่น · mean|α̂| (train · E) เปลี่ยนจาก L3-B ไม่เกิน ±1 %/ปี
2. **BH (full · FDR 10%):** M1 / M2 ผ่าน 0–8 กอง · BY ≤ BH · "มีหลักฐาน α" ทั้งสองฐาน ≤ 5 กอง · ส่วนใหญ่ α < 0 · M3/M4 ต่างจาก M1/M2 ≤ 1 กอง
3. **bootstrap FF 2010:** p_boot ของจำนวน BH > 0.10 (แยกจากโชคไม่ได้) · percentile 1 และ 5 ของ t จริงต่ำกว่า null (p_boot < 0.05) · percentile 95 / 99 ไม่เกิน null (p_boot > 0.10)
4. **MDA:** median MDA (E · single test) > 5 %/ปี · MDA_mt > 9 %/ปี · กอง F median < 2 %/ปี
5. **signed α (full · E):** median −1 ถึง −4 %/ปี
6. **class ปันผล (16):** median α̂ ต่ำกว่ากองไม่ปันผลใน policy เดียวกัน ≥ 1 %/ปี
7. **L4-2 X1:** slope TER < 0 และ CI ครอบ −1 (อย่างน้อยฐานเดียว) · DIV < 0 (CI ไม่คร่อม 0 อย่างน้อยฐานเดียว) · FXβ CI คร่อม 0 ทั้งสองฐาน · 1−R² CI คร่อม 0 · Wald กลุ่ม p > 0.05 · น้ำหนัก WLS ของกอง F > 30%
8. **FX gap:** median ratio ≤ 0.5 (ไม่ผ่านใน L1 9b ด้วย ③a · คาดว่าผ่านเพราะครั้งนี้ FX อยู่ใน model แบบแยกและ e ตั้งฉาก)
9. **factor กลุ่ม (Q1):** "มี" ใน ACWI_CD และ CHINA_ALL (PCA k_g = 1) · ไม่มีใน ACWI / ACWI_EX_US / ASIA_EX_JAPAN / ACWI_IT · กลุ่ม LOO-mean (India · Japan · EM · Europe · HC · Vietnam ฯลฯ) ผ่าน ≤ 2 กลุ่ม · F: มี (ตลาดเงิน / บอนด์ไทยไม่มี factor ตรง · ข้อ 2) · O: ไม่ผ่าน (กองหลากหลาย)
10. **G0:** k_ED ≥ 1 ใน residual ของกอง E ทั้งหมด (ยังมีโครงร่วมเหลือ) แต่ eigenvalue แรก < 10% ของ trace
11. **ชื่อ factor กลุ่ม:** ACWI_CD ใกล้ ARKK หรือ QQQ (|corr| ≥ 0.5 อย่างน้อย "คล้าย") · CHINA_ALL ใกล้ KWEB หรือ e ของ CHINA_A
12. **carry (H1/H2):** R² ของ CARRY บน [1, trend] ≥ 0.8 (แยกจากค่าคงที่ยาก) · α ของกอง FX flag N เปลี่ยนมากที่สุด
13. **รายเดือน:** Spearman α̂ สัปดาห์ vs เดือน ≥ 0.8 · BH รายเดือน ≤ รายสัปดาห์

---

## 10. ข้อจำกัด (ติดไปกับรายงานผล)
- **ช่วง test ถูกใช้เลือกรูปแบบแล้ว** (ป้าย ข) และ P4 / L3-B ถูกเลือกด้วยช่วงนี้ → α ช่วง full ของกองหลัก P4 ถูกหักด้วย e ที่เลือกมาให้ fit ช่วงนี้ดี → α ของ 38–40 กองนี้เอียงเข้าหา 0 · ไม่มี holdout อื่น (NAV 2026 มีรู)
- **เกณฑ์ L4 ออกแบบหลังเห็นผล L3** (ป้าย ง) · ค่าตัดนำจากค่าที่ล็อกแล้ว ยกเว้น null 95% และ ratio 0.5 (จาก F-R004)
- **T สั้น power ต่ำ** (AP 2019 · BSW reply): ไม่พบ ≠ ไม่มี · FF 2010 undersampling (Harvey–Liu 2022) · ไม่ประมาณ π₀ แบบ BSW
- **FundProfile / SecFundFee เป็น snapshot:** TER ใช้ as-of แรกสุด (97/207 กองเริ่ม 2023-05) ไม่ใช่ต้นช่วง 2021 · ความหมายรหัส TT ยังไม่ยืนยันกับเอกสาร · ธง FX Risk / ปันผล ปัจจุบัน
- **regressor ที่ประมาณเอง** (FXβ, 1−R²) ใช้ข้อมูลซ้อนกับ α̂ → SE ของ L4-2 ไม่รวมความคลาดเคลื่อนขั้นแรก · X3 ลดการซ้อนช่วงแต่ T = 104
- NAV class ปันผลไม่รวมปันผล → α ติดลบเชิงกล · twin test ทำไม่ได้ใน panel · SPOT/CARRY มาจาก ETF SHV (ไม่ใช่ forward points จริง) · CIP basis ของบาทไม่ยืนยันแหล่ง
- factor ① และ e ลงทุนไม่ได้ (พอร์ตกองมีน้ำหนักติดลบ) → α เป็นเชิงอธิบาย · **ระยะ 1 ห้ามสรุปว่า "ลงทุนได้"** · factor กลุ่มเป็นค่าเฉลี่ยของกองเพื่อน (peer-relative แบบ ②) → α หลังใส่ factor กลุ่ม = เทียบเพื่อน ไม่ใช่ตลาด
- กลุ่ม 5–9 กอง (LOO-mean) median แกว่งง่าย · กฎขนาดกลุ่ม / LOO / null 200 รอบ = กติกาของ designer · ธีมจากชื่อกอง (ป้าย ฉ)
- ทั่วไป: F (18) / O (14) n เล็ก · spike F 119 จุดยังไม่แก้ (ข้อ 3) · ไม่ใช้ปี 2026 · ETF / MSCI ปิดเวลา NY · "MSCI" ในระบบมาจาก ETF

---

## 11. จำนวนรูปแบบและงาน
**model α 4 แถวหลัก (M1, M2 + M3 ⚠️, M4 ⚠️) + ภาคผนวก 2 (H1, H2)** · แถวอ้างอิง 6 (ref-L3B ×2 · ref-L3B-full ×2 · ref-FX ×2 · ไม่ใช่รูปแบบใหม่) ·
factor กลุ่ม **1 กฎ × 2 ฐาน** (+ null 200 รอบต่อกลุ่ม · G0 · G-T บรรยาย) · cross-section **12 regression** (X1 ×4 · X2 ×2 · X3 ×2 · X4 ×2 · X5 ×2) · bootstrap FF 2010: M1, M2 × 999 · ไม่มีภาคผนวก k = 3/5 · ไม่ทำ RBSA (L3-5) · ไม่ทำ twin ·
ลองนอกนี้ = spec ใหม่ · ระยะ 1 ไม่นับ trial

---

## ต้องให้ผู้ใช้ตัดสินใจ (ทุกข้อมี **ค่าเริ่มต้นที่แนะนำ** ให้ session หลักใช้ระหว่าง auto run — เปลี่ยนได้ก่อนรันเท่านั้น · หลังเห็นผลต้องติดป้ายตามข้อ 31)
1. **ช่วงประมาณ α หลัก** — แนะนำ: **full 2021–2025** (T ≤ 259 · power สูงสุด) + train เป็นภาคผนวก · ทางเลือก: train เป็นหลัก (เทียบ L1–L3 ตรง แต่ T 155)
2. **FX factor ใน model α** — แนะนำ: **FX = SHV_THB − RF_BOT ทุก model** + SPOT/CARRY เป็นภาคผนวก H1/H2 · ทางเลือก: SPOT/CARRY เป็นหลัก (ระบุ hedge-cost ตรงกว่า แต่ CARRY ซ้อนค่าคงที่)
3. **ตัวแทนของ MGAG / MGAPVD** (ข้อ 54) — แนะนำ: **MGAG** (ชนิดผู้ลงทุนทั่วไป) · MGAPVD บรรยาย
4. **กฎขนาดกลุ่ม** (n_indep ≥ 10 → PCA · 5–9 → LOO-mean · < 5 → ไม่สร้าง · k_g = min(ED, PA) · kmax 3) — แนะนำ: **ตามนี้**
5. **null กลุ่มสุ่ม 200 รอบ + เกณฑ์ percentile 95** — แนะนำ: **ตามนี้** · ทางเลือก: 999 รอบ (ช้ากว่า ~5 เท่า)
6. **นิยาม TER** = FEEMF·TT `Actual Value` ที่ as-of แรกสุด (fallback `Rate`) — แนะนำ: **ตามนี้** + ภาคผนวก as-of ล่าสุด · ทางเลือก: `Rate` (เพดานตามหนังสือชี้ชวน) · ยืนยันความหมายรหัส TT ด้วยเอกสาร ก.ล.ต. (ผู้ใช้จัดหา) หรือยอมรับป้าย
7. **L4-2 ใช้ WLS 1/se² + cluster กลุ่มกองอิสระ** (OLS ภาคผนวก) — แนะนำ: **ตามนี้** · รายงานน้ำหนักของกอง F (ถ้า > 50% ให้อ่าน X2 เป็นหลักสำหรับกอง E — ป้าย)
8. **log AUM เป็นภาคผนวก X5** (เมื่อครอบคลุม ≥ 80%) — แนะนำ: **ใช่**
9. **twin test hedge / unhedge** — แนะนำ: **ไม่ทำ** (ไม่มีคู่ใน EVAL · ต้องให้ data-engineer สร้าง panel class ที่ถูกยุบจาก `base_data/` = ไฟล์ L0 ใหม่ + spec ใหม่)
10. **RBSA รายกอง (F-R004 L3-5)** — แนะนำ: **ไม่ทำในระยะ 1** (จำกัดจำนวนรูปแบบ · กอง hedge ทำให้ w ≥ 0 ผิดรูป)
11. **ชุดเข้ม (ข้อ 68)** ทำเฉพาะ M3/M4 + BH + X1 — แนะนำ: **ตามนี้** (ไม่ทำ factor กลุ่ม / bootstrap บนชุดเข้ม)
12. **π₀ / สัดส่วนกองมีทักษะแบบ BSW** — แนะนำ: **ไม่ทำ** (F-R004: T สั้น) · ทางเลือก: ภาคผนวกพร้อมป้าย
13. **ชื่อ factor กลุ่มด้วย ETF ส่วนขยาย 14 ตัว** (ไม่ดาวน์โหลดใหม่ · บรรยาย) — แนะนำ: **ใช่**
14. **การตรวจแหล่งของวิธีที่ยังไม่ยืนยัน** (ข้อ 72): สูตร MDA_mt (การประมาณของ designer) · FF 2010 ปรับเป็น block (ไม่ใช่สุ่มรายเดือนแบบต้นฉบับ) · CR1 กับ cluster ที่สร้างจากข้อมูล — แนะนำ: **ติดป้ายและรันได้เลย** (ไม่กระทบตัวเลขของวิธีหลัก BH / HAC) · researcher ตรวจคู่ขนานถ้าผู้ใช้ต้องการ
