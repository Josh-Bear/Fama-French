# M008 — style/macro บน M004-TF-FX: (a) group cap จาก cluster · (b) SR12 + defensive style tilt · (c) factor risk model = ตัดทิ้ง

สถานะ: ลงทะเบียนล่วงหน้า 2026-10-02 · ผู้ออกแบบ: quant-modeler · base: **M004-TF-FX** (SR12, N=8, K=16, 1 class/family (F/U fix),
ERC จาก LW 52 สัปดาห์, cap 25%/กอง, เงินสด 25% เมื่อ ACWI < SMA200, รายไตรมาส, วัดผลแบบใหม่ 45 เดือน เม.ย. 2022–ธ.ค. 2025)
**trials: M008-GC = n_trials 19 · M008-SQ = n_trials 20** (ถ้ารันแค่ตัวเดียว ให้ใช้เลขถัดไปตามลำดับจริงใน trials.csv)

## 0. Step 1 — ผลสำรวจ (ไม่มี forward return · ไม่นับ trial)
สคริปต์ `scratch/modeler_explore_style_macro.py` → `scratch/modeler_explore_out/*.csv` · 15 ไตรมาส 2022-03..2025-09 · กองใน I_t (175–320 กอง)
- **หน้าต่าง**: weekly 52 สัปดาห์ (≥ 40 obs) fit ได้ **ครบทุกกองทุกไตรมาส** · 104 สัปดาห์ **fit ไม่ได้เลยที่ 2022-03, 2022-06** (factor มีแค่ 65/78 สัปดาห์
  เพราะ STYLE/MACRO เริ่ม 2020-11) = ตรงช่วงขาลงที่ต้องการแก้ → **ใช้ 52w** · macro รายเดือน 36 เดือน (แบบแอปหน้า 7) ทำได้เร็วสุด ~2023-11 → ใช้ไม่ได้
- **R² median** (52w): ACWI ล้วน 0.35 · 3 controls + 4 style 0.70 (incremental +0.30) · ACWI + 7 macro 0.59 (+0.22) · 104w ใกล้เคียง
- **นัยสำคัญรายกอง**: |t| > 2 เพียง 21% ของ beta style, 17% ของ beta macro · median |t| ของ β_Quality 0.94, β_LowVol 1.02, β_VIX 1.00, β_US10Y 1.09 → noisy
- **stability** (Spearman ข้ามกองของ beta): t vs t−1q (หน้าต่างซ้อน 75%) 0.66–0.89 · **t vs t−4q (ไม่ซ้อน)**: Value 0.58, LowVol 0.49, Copper 0.47,
  Quality 0.38, USDTHB 0.32, VIX 0.17, Momentum 0.11, DXY 0.10, Oil −0.01, US10Y −0.12, Gold −0.16 → **sensitivity ต่อ macro (VIX/US10Y/Gold/Oil) ไม่เสถียร**
- **ซ้ำกับ SR12?** Spearman ข้ามกองกับ SR12: Quality 0.16, LowVol 0.07, VIX 0.06, US10Y −0.04 → ไม่ซ้ำ (เป็นข้อมูลใหม่)
- **cluster vs ธีมในพอร์ตที่ถือ** (holdings M004-TF-FX, น้ำหนัก normalise ในส่วนหุ้น; ธีมจากชื่อกองแบบหยาบ):

| วิธีจัดกลุ่ม (PIT ≤ t) | กลุ่มใน universe | กลุ่มที่ถือ (เฉลี่ย) | max น้ำหนัก/กลุ่ม เฉลี่ย | ไตรมาสที่ cap 35% จะ bind | theme recall | false merge |
|---|---|---|---|---|---|---|
| **corr 52w, average-linkage, ตัด 1−ρ = 0.25** | 39 | 4.7 | 0.44 | **13/15** | 0.77 | **0.14** |
| beta style+macro, Ward k=10 | 10 | 3.2 | 0.57 | 14/15 | 0.90 | 0.30 |
| MSCI country primary (cache ElasticNet PIT) | 10 | 3.8 | 0.47 | 10/15 | 0.92 | 0.19 |
| MSCI sector primary | 8 | 3.7 | 0.47 | 11/15 | 0.63 | 0.24 |

  ตัวอย่าง corr-cluster: 2022-03 กลุ่มใหญ่สุด 44.8% (infra) · 2023-12 62.8% (tech) · 2024-06 57.8% (India) · 2025-06 54.5% (infra) → **cap จะ bind จริง**
  ส่วน beta-cluster k=10 รวมธีมต่างกันมากเกิน (false merge 30%: กลุ่มใหญ่เป็น "กองหุ้นโลก/US" ก้อนเดียว) · MSCI country รวม US ทุกธีมเป็นกลุ่มเดียว
- **risk model B F Bᵀ + D** (ชุดที่ถือ, F = LW ของ factor 52w): ERC weights ต่างจาก Σ_LW แค่ **L1 = 0.05 (style) / 0.07 (macro)**, max |Δw| ≈ 2 pt
  (corr เฉลี่ย 0.30 vs 0.39, systematic share 50%) → ERC ขับด้วย vol เป็นหลัก พอร์ตแทบเหมือนเดิม

**สรุปเส้นทาง**
- (a) **ไปต่อ** — แต่ใช้ cluster จาก correlation ของ return กอง (แยกธีมได้ดีสุด, ไม่มี estimation noise ของ beta) แทน beta style/macro
- (b) **ไปต่อแบบจำกัด** — ใช้เฉพาะ Quality + LowVol (เสถียรพอประมาณ 0.38/0.49) · ตัด VIX/US10Y (ไม่เสถียร, ข้ามปีกลับเครื่องหมาย)
- (c) **ตัดทิ้ง** — เปลี่ยนน้ำหนัก ≤ 2 pt/กอง → ผลคาดว่า ≈ 0 แต่เสีย 1 trial (DSR ลด) · ไม่ลงทะเบียน

## 1. M008-GC — group (cluster) cap
**สมมติฐาน**: กองไทย FIF หลายบริษัทจัดการตามธีมเดียวกัน (feeder ของ master ต่างกันแต่ถือหุ้นชุดคล้ายกัน) · family map จับได้แค่ share class
→ momentum ทำให้พอร์ต N=8 กลายเป็น bet ธีมเดียว 45–63% · การจำกัดน้ำหนักต่อ cluster = กระจายจริง (Markowitz; Lopez de Prado 2016 HRP:
cluster-based allocation ลด concentration ที่ sample Σ มองไม่เห็น; Baltas 2015 sector cap ใน momentum) — ไม่คาดว่าเพิ่ม return แต่ลด tail/DD ของธีม

**อัลกอริทึม (ต่อ M004-TF-FX ทุกข้อ ยกเว้นข้อ 2–4)** ณ t:
1. I_t, SR12, family reps, ranks — เหมือนเดิม
2. **cluster ของ I_t**: R = weekly return 52 สัปดาห์ของทุกกองใน I_t จาก `qctx.weekly_return_series` (ข้อมูล ≤ t) · C = R.corr(min_periods=40), NaN→0, diag=1
   · D = clip(1 − C, 0, 2) · `scipy linkage(squareform(D), "average")` · `fcluster(..., 0.25, "distance")` → label `g(fund)` (เหมือนสคริปต์สำรวจทุกบรรทัด)
3. **selection**: `hysteresis_select` + ข้อจำกัด **≤ 3 กองต่อ cluster**: (i) กองที่ถืออยู่และ rank ≤ K เรียงตาม rank — ถ้า cluster ใดเกิน 3 ตัดตัว rank แย่สุดออก
   (ii) เติมตาม rank จนครบ N=8 ข้ามผู้สมัครที่ cluster เต็ม 3 แล้ว (นับ `n_skipped_cluster`)
4. **weights**: ERC (LW 52w) → `apply_cap` 25%/กอง → **group cap 35% ของส่วนหุ้นต่อ cluster** (water-filling: ส่วนเกินของ cluster ที่เกินแจกให้กองใน cluster
   ที่ยังไม่เต็มตามสัดส่วนน้ำหนัก) → วนซ้ำ cap กอง/cap กลุ่ม จนไม่มีอะไรเกิน (≤ 50 รอบ, tol 1e-9) · ถ้า infeasible (< 3 cluster) ให้ cap กลุ่ม = 1/จำนวนกลุ่ม และ flag
5. trend 25% cash, execution, cost, การวัดผล — เหมือน M004-TF-FX ทุกอย่าง
- พารามิเตอร์ตายตัว (ไม่มี grid): ตัด 0.25, ≤ 3 กอง/cluster, cap 35% · หมายเหตุ: ค่าตัด 0.25 เลือกจากการสำรวจ holdings (ไม่ใช่ return) — เปิดเผยไว้

## 2. M008-SQ — SR12 + defensive style tilt (Quality + LowVol)
**สมมติฐาน**: ตลาดขาลง (2022) หุ้น quality / low-beta ลงน้อยกว่า (Asness–Frazzini–Pedersen 2019 QMJ "flight to quality"; Frazzini–Pedersen 2014 BAB;
Blitz–van Vliet 2007) · กองที่ NAV เคลื่อนไปทาง QUAL/ACWV (เทียบ ACWI) ควรรับแรงขาลงได้ดีกว่า · momentum ล้วนเลือกกองธีม beta สูง (tech/India/Vietnam)
ที่พังตอนกลับทิศ (Daniel–Moskowitz 2016 momentum crash) → ผสม defensive ลด crash risk

**อัลกอริทึม** ณ t (ต่อ M004-TF-FX ยกเว้นตัวแปรที่ใช้ rank):
1. weeks = `fs.weekly_points(calendar, t, 53)` · factor weekly (asof ≤ week point, ffill ≤ 10 วัน): MSCI_ACWI, US_VS_ACWI = MSCI_USA/MSCI_ACWI, ACWI_ETF,
   Momentum/Quality/Value/LowVol relative (blend 0.6 US/0.4 Intl ใน return space ÷ ACWI ETF ตาม `config.STYLE_*` · LowVol = ACWV/ACWI)
2. ต่อกองใน I_t: OLS (มี intercept) weekly return กอง ~ 3 controls + 4 style · ≥ 40 obs · β ต่อ 1 SD ของ factor (`ols()` ในสคริปต์สำรวจ)
3. z-score ข้ามกองใน I_t (winsorize ±3): `score = 0.5·z(SR12) + 0.25·z(β_Quality) + 0.25·z(β_LowVol)` · กองไม่มี fit → ไม่เข้า I_t
4. `family_representatives(i_t, "score", ...)` → rank → hysteresis N=8 K=16 ด้วย score · ที่เหลือ (ERC, cap 25%, trend 25%) เหมือน M004-TF-FX
- น้ำหนัก 0.5/0.25/0.25 ตายตัว (ไม่มี grid) · ไม่ใช้ VIX/US10Y (เหตุผล §0)

## 3. look-ahead guards + sanity tests (ทั้ง 2 trials)
- assert: max date ของ NAV/factor ที่ใช้ ≤ t ทุก fit/cluster · STYLE/MACRO CSV เป็น snapshot adjusted close — ใช้แค่ return (dividend adjust ไม่ทำให้รู้อนาคต)
- **canary**: แทน NAV และ factor หลัง t ด้วย noise → cluster labels, scores, S, weights ณ t ต้องเหมือนเดิม 100% (≥ 5 ไตรมาส)
- T-GC1: ทุกไตรมาส Σ น้ำหนัก/cluster ≤ 0.35 × equity (+1e-9) และ ≤ 3 กอง/cluster · T-GC2: ถ้าตั้ง cap=1, max=8 → ได้ M004-TF-FX ตรงทุกหลัก (regression 0.7205)
- T-SQ1: ตั้งน้ำหนัก (1,0,0) → ได้ M004-TF-FX ตรงทุกหลัก · T-SQ2: β_LowVol ของกอง low-vol ที่รู้จัก (ถ้ามีใน I_t) > 0 · reproducible กับสคริปต์สำรวจ
- regression: M004-TF-FX ต้องได้ 0.7205 ด้วยโค้ดรุ่นใหม่

## 4. รายงาน + เกณฑ์ตัดสิน (ลงทะเบียนก่อนเห็นผล)
รายงาน: Sharpe (cost 0/0.5/1%), CAGR, vol, maxDD, **return & maxDD เม.ย.–ธ.ค. 2022**, Sharpe 2023-07..2025-12, turnover, cost bp/ปี, CI95, **DSR@19 / @20**,
paired ΔSharpe vs M004-TF-FX (CI), Sharpe เมื่อตัดไตรมาสดีสุด, **ตาราง concentration**: max cluster weight, max name-theme (infra/India/tech) ต่อไตรมาส, `n_skipped_cluster`,
`weights.csv` ตาม M007 §5
- **M008-GC ผ่าน** ถ้า (1) max name-theme ≤ 40% ของพอร์ตทุกไตรมาส (เดิม 45–63%) และ (2) Sharpe ≥ 0.67 (≥ base − 0.05) และ (3) maxDD ไม่แย่กว่า base > 1 pt
- **M008-SQ ผ่าน** ถ้า (1) return เม.ย.–ธ.ค. 2022 ≥ −4.4% (ดีกว่า base −6.4% ≥ 2 pt) และ maxDD 2022 ดีกว่า −10.4% ≥ 2 pt และ (2) Sharpe 2023-07..2025-12 ลดไม่เกิน 0.15 จาก 1.183
- ทั้งสอง: ห้ามสลับตัวเสนอเป็น headline เว้นผ่านเกณฑ์ **และ** paired Δ CI ไม่ต่ำกว่า −0.3 · ห้ามรันรุ่นผสม GC+SQ จนกว่าผู้ใช้อนุมัติ (= trial 21)

## 5. ความคาดหวังตามจริง
- GC: Sharpe ≈ 0.55–0.80 (ตัด bet ธีมที่ชนะ เช่น tech 2023–24 ด้วย) · concentration ดีขึ้นแน่นอนเชิงกลไก · DSR@19 ~0.2–0.3
- SQ: Sharpe ≈ 0.50–0.80 · beta noisy (|t|≈1) → tilt ใกล้ random ส่วนหนึ่ง · อาจช่วยปี 2022 1–3 pt · ขาลงมีแค่ครั้งเดียวในช่วงวัดผล → พิสูจน์ไม่ได้
- โอกาสถึง 0.95 ต่ำ (< 15%) — ทั้งสองเป็นการแก้ "คุณภาพพอร์ต" มากกว่าเพิ่ม Sharpe

## 6. reviewer ควรตรวจ
cluster ใช้ข้อมูล ≤ t จริง · ลำดับ cap กอง/กลุ่มลู่เข้า · ค่าตัด 0.25 เลือกจาก holdings (selection bias เบาๆ) · SQ z-score ใน I_t ไม่ใช่ทั้ง universe ·
ETF style (NY close) vs NAV ไทย timing → ใช้ weekly ลดปัญหา

## 7. ต้องให้ผู้ใช้ตัดสินใจ
1. ยอมใช้ cluster จาก correlation ของ return (แทน beta style/macro ซึ่งแยกธีมแย่กว่า) สำหรับ route (a) ไหม · cap 35% / ≤ 3 กอง เหมาะไหม
2. ยืนยันตัด route (c) และตัด VIX/US10Y จาก route (b)
3. รัน 2 trials (n=19, 20) หรือรันแค่ GC (ตัวที่ตอบปัญหา concentration ตรงที่สุด)

## ผู้ใช้ตัดสินใจแล้ว (2026-10-02)
- รัน **ทั้ง M008-GC (n=19) และ M008-SQ (n=20)** · กติกา GC ตาม spec (ρ ≥ 0.75, ≤ 3 กอง/กลุ่ม, ≤ 35% ของส่วนหุ้น)
- ยืนยันตัด route (c) risk model ใหม่ และตัด VIX/US10Y ออกจาก SQ · ไม่รันแบบผสม GC+SQ
