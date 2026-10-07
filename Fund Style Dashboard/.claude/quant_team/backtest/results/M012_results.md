# M012-QF — เกณฑ์คุณภาพ (AUM_fam ≥ 100 ล้านบาท + อายุแบบ B ≥ 730 วัน) บน M011-RFH — ผลวัด (validator)

รันเมื่อ 2026-10-06T10:37:07.180639 · spec `specs/M012_quality_filter.md` + การตัดสินใจผู้ใช้ 2026-10-06 (อายุแบบ B · 2 ทางเลือก = trial 24 (S) และ 25 (K)) · primary เม.ย. 2022–2025-12-31 (45 เดือน) · วัดด้วย **rf จริง** (นโยบาย ธปท.) ตาม `remeasure_real_rf.py` (ตัวหาร sd(r)) ทุกแขน · baseline = M011-RFH · ไม่มี holdout

- **S** = กองที่ถือต่อและหลุดเกณฑ์ → ขาย · **K** = เกณฑ์ใช้เฉพาะเติมกองใหม่ (กองถือต่อไม่ถูกตัดด้วยเกณฑ์ ยังหลุดได้ตามกติกาเดิม: NAV ไม่สด/อันดับ > K) · รายงานทั้งคู่ ไม่เลือกตัวที่ดีกว่า

## 1. Spot check Registration_date + regression

- Spot check `FundProfile.csv` (570/570 class ใน NAV มีแถว, ไม่ซ้ำ, ไม่ว่าง, รูปแบบ YYYYMMDD ทั้งหมด parse ได้) · Registration_date > NAV แรก 131 class แต่ **ห่างสูงสุด 18 วัน (median 2 วัน)** — ไม่ใช่ median 145 วันตามที่ spec ระบุ (ไม่กระทบเพราะใช้ min กับ NAV แรก) · Reg < NAV แรก 439 class (class เก่าที่ไฟล์ NAV เริ่ม ธ.ค. 2020 หรือ NAV มาทีหลัง) · `scratch/validator_m012_regdate.py`
- AUM หน่วยบาท: ES-GQG family AUM_fam ณ 2025-12-31 = 2.2453e+10 (= ผลรวม class ✓) · DAOL-KOREAEQ first_fam = 2024-06-13 ผ่านอายุ = False · Q1/Q2 ใช้แถว NAVDate ≤ t เท่านั้น (assert ในโค้ด)
- Regression (S, เกณฑ์ปิด, เส้นทางโค้ด wt.hysteresis_select): น้ำหนักเทียบ `M011-RFH_weights.csv` max|Δw| = 9.71e-17 (แถว 126 vs 126, คีย์ฝั่งเดียว 0) → **PASS** · Sharpe c0/c50/flat/full/nofront ตรง `M011_results.csv` (<5e-7) → **PASS** (full 0.648783)
- Regression (K, เกณฑ์ปิด, เส้นทางโค้ด select_K): น้ำหนักเทียบ `M011-RFH_weights.csv` max|Δw| = 9.71e-17 (แถว 126 vs 126, คีย์ฝั่งเดียว 0) → **PASS** · Sharpe c0/c50/flat/full/nofront ตรง `M011_results.csv` (<5e-7) → **PASS** (full 0.648783)
- sleeves จาก stream ใหม่ (เกณฑ์ปิด) = `r9.select_stream` เดิม: PASS

## 2. ตารางหลัก (ค่าธรรมเนียมจริง full, rf จริง, ตัวหาร sd(r))

| โมเดล | Sharpe | CAGR | vol | maxDD | Sharpe 2022 | Sharpe 2023-07..25 | cost bp/ปี | turnover/ปี | CI95% Sharpe | DSR@25 |
|---|---|---|---|---|---|---|---|---|---|---|
| **M012-QF-S** | 0.660 | 0.0833 | 0.1019 | -0.1022 | -1.022 | 1.024 | 168.9 | 1.488 | [-0.48, 1.83] | 0.1621 |
| **M012-QF-K** | 0.661 | 0.0834 | 0.1018 | -0.1022 | -1.022 | 1.027 | 164.4 | 1.489 | [-0.48, 1.83] | 0.1625 |
| M011-RFH | 0.649 | 0.0821 | 0.1020 | -0.1116 | -1.010 | 1.061 | 184.0 | 1.618 | [-0.44, 1.77] | 0.1751 |
| B0 (rf จริง, `REAL_RF_summary.csv`, ไม่ได้ตรวจซ้ำเอง) | 0.076 | 0.0196 | 0.1302 | -0.2142 | -1.487 | 0.641 | — | — | [-0.70, 1.30] | 0.0386 (@22) |

(DSR@25 = นับ 2 trials ของ M012 · DSR@24 ของ S = 0.1664)

## 3. ตัวชี้วัดหลัก + เกณฑ์ (ล็อก: ผ่าน = Δ Sharpe full ≥ 0 · ไม่ผ่าน = ไม่ใช้เกณฑ์คุณภาพ)

- **S: Δ Sharpe_full (M012-QF-S − M011-RFH) = +0.0109** · CI95% paired block bootstrap (block 3, 2000, seed 0) [-0.141, +0.192] (คร่อม 0) · **ผลตามเกณฑ์: ผ่าน**
- **K: Δ Sharpe_full (M012-QF-K − M011-RFH) = +0.0124** · CI95% paired block bootstrap (block 3, 2000, seed 0) [-0.134, +0.198] (คร่อม 0) · **ผลตามเกณฑ์: ผ่าน**

## 4. ตารางต้นทุน (rf จริง)

| ต้นทุน | S Sharpe | S CAGR | S vol | S maxDD | K Sharpe | K CAGR | K vol | K maxDD | M011 Sharpe | M011 CAGR | M011 vol | M011 maxDD |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0% | 0.836 | 0.1018 | 0.1006 | -0.0897 | 0.833 | 0.1014 | 0.1006 | -0.0897 | 0.837 | 0.1023 | 0.1011 | -0.0987 |
| 0.5%/ข้าง | 0.672 | 0.0844 | 0.1015 | -0.1008 | 0.669 | 0.0840 | 0.1013 | -0.1008 | 0.662 | 0.0835 | 0.1018 | -0.1057 |
| flat 0.5% (fee model) | 0.672 | 0.0844 | 0.1015 | -0.1008 | 0.669 | 0.0840 | 0.1013 | -0.1008 | 0.662 | 0.0835 | 0.1018 | -0.1057 |
| ค่าธรรมเนียมจริง full | 0.660 | 0.0833 | 0.1019 | -0.1022 | 0.661 | 0.0834 | 0.1018 | -0.1022 | 0.649 | 0.0821 | 0.1020 | -0.1116 |
| nofront | 0.835 | 0.1017 | 0.1006 | -0.0900 | 0.832 | 0.1012 | 0.1006 | -0.0900 | 0.836 | 0.1021 | 0.1011 | -0.0987 |

- cost bp/ปี c50: S 158.8 · K 158.9 · M011 171.8 · turnover/ปี (full): S 1.488 · K 1.489 · M011 1.618

## 5. จำนวน family ต่อไตรมาส (ใน I_t ของ M011; ตัดด้วยเกณฑ์) + AUM ต่ำสุดในพอร์ต

| t | family ใน I_t | ผ่านทั้งคู่ | ตัดเพราะ AUM เท่านั้น | ตัดเพราะอายุเท่านั้น | ตัดทั้งคู่ | AUM_fam=0 (>90 วัน) |
|---|---|---|---|---|---|---|
| 2022-03-31 | 155 | 96 | 25 | 31 | 3 | 0 |
| 2022-06-30 | 171 | 104 | 26 | 35 | 6 | 0 |
| 2022-09-30 | 189 | 114 | 31 | 40 | 4 | 0 |
| 2022-12-30 | 199 | 125 | 30 | 40 | 4 | 0 |
| 2023-03-31 | 213 | 143 | 31 | 30 | 9 | 0 |
| 2023-06-30 | 217 | 143 | 39 | 27 | 8 | 0 |
| 2023-09-29 | 230 | 160 | 37 | 20 | 13 | 0 |
| 2023-12-29 | 250 | 172 | 47 | 18 | 13 | 0 |
| 2024-03-29 | 255 | 187 | 47 | 12 | 9 | 1 |
| 2024-06-28 | 256 | 187 | 55 | 9 | 5 | 1 |
| 2024-09-30 | 261 | 192 | 59 | 8 | 2 | 1 |
| 2024-12-31 | 261 | 186 | 67 | 6 | 2 | 1 |
| 2025-03-31 | 266 | 193 | 69 | 4 | 0 | 0 |
| 2025-06-30 | 276 | 204 | 67 | 5 | 0 | 0 |
| 2025-09-30 | 290 | 215 | 61 | 13 | 1 | 0 |
| 2025-12-31 (หน้า 9) | 327 | 239 | 63 | 21 | 4 | 0 |

AUM_fam ต่ำสุดในพอร์ต (ล้านบาท) และชุดกองต่างจาก M011:

| t | M011 | S (ต่ำสุด · family) | K (ต่ำสุด · family) | S B0? | K B0? | S ชุดต่าง (ตรง/สืบทอด) | K ชุดต่าง (ตรง/สืบทอด) |
|---|---|---|---|---|---|---|---|
| 2022-03-31 | 102 | 102 · UVO | 102 · UVO | - | - | - | - |
| 2022-06-30 | 72 | 136 · FCSCBSETE | 136 · FCSCBSETE | - | - | ต่าง-ตรง | ต่าง-ตรง |
| 2022-09-30 | 63 | 132 · FCSCBSETE | 132 · FCSCBSETE | - | - | ต่าง-ตรง | ต่าง-สืบทอด |
| 2022-12-30 | 64 | 133 · FCSCBSETE | 133 · FCSCBSETE | - | - | ต่าง-ตรง | ต่าง-ตรง |
| 2023-03-31 | 54 | 117 · ONE-EUROEQ | 117 · ONE-EUROEQ | - | - | ต่าง-ตรง | ต่าง-ตรง |
| 2023-06-30 | 75 | 149 · ONE-UJE | 75 · ONE-EUROEQ | - | - | ต่าง-ตรง | - |
| 2023-09-29 | 219 | 161 · ONE-UJE | 219 · EHD | - | - | ต่าง-ตรง | ต่าง-ตรง |
| 2023-12-29 | 119 | 124 · ONE-UJE | 402 · TISCOJP | - | - | ต่าง-ตรง | ต่าง-ตรง |
| 2024-03-29 | 38 | 132 · TISCOINA | 132 · TISCOINA | - | - | ต่าง-ตรง | ต่าง-ตรง |
| 2024-06-28 | 61 | 115 · ONE-INDIAOPP | 115 · ONE-INDIAOPP | - | - | ต่าง-ตรง | ต่าง-ตรง |
| 2024-09-30 | 4 | 120 · ONE-INDIAOPP | 120 · ONE-INDIAOPP | - | - | ต่าง-ตรง | ต่าง-ตรง |
| 2024-12-31 | 50 | 450 · TISCOINA | 450 · TISCOINA | - | - | ต่าง-ตรง | ต่าง-ตรง |
| 2025-03-31 | 43 | 119 · TCHT5M4 | 119 · TCHT5M4 | - | - | ต่าง-ตรง | ต่าง-ตรง |
| 2025-06-30 | 41 | 119 · TCHT5M4 | 119 · TCHT5M4 | - | - | ต่าง-ตรง | ต่าง-สืบทอด |
| 2025-09-30 | 134 | 134 · DAOL-PLAY | 134 · DAOL-PLAY | - | - | ต่าง-ตรง | ต่าง-ตรง |
| 2025-12-31 | 88 | 213 · TISCOGIF | 213 · TISCOGIF | - | - | ต่าง-ตรง | ต่าง-ตรง |

- **S**: ชุดกองต่างจาก M011 14/15 ไตรมาส (ตรงๆ 14, สืบทอดผ่าน hysteresis 0) · ไตรมาสที่ตก fallback B0 (ใน 15): 0 · พอร์ต 2025-12-31 (หน้า 9) M012 = [DAOL-GOLD;ES-GINFRA-A;KKP GINFRAEQ-H;KT-MINING;M-EUBANK;PRINCIPAL GIF;TISCOGIF-R;UCI] · M011 = [ASP-NGF;DAOL-GOLD;DAOL-KOREAEQ;ES-GINFRA-A;KKP GINFRAEQ-H;M-EUBANK;PRINCIPAL GIF;PRINCIPAL KEQ]
- **K**: ชุดกองต่างจาก M011 13/15 ไตรมาส (ตรงๆ 11, สืบทอดผ่าน hysteresis 2) · ไตรมาสที่ตก fallback B0 (ใน 15): 0 · พอร์ต 2025-12-31 (หน้า 9) M012 = [DAOL-GOLD;ES-GINFRA-A;KKP GINFRAEQ-H;KT-MINING;M-EUBANK;PRINCIPAL GIF;TISCOGIF-R;UCI] · M011 = [ASP-NGF;DAOL-GOLD;DAOL-KOREAEQ;ES-GINFRA-A;KKP GINFRAEQ-H;M-EUBANK;PRINCIPAL GIF;PRINCIPAL KEQ]

## 6. กลไก — กองที่ถูกตัด (ต่อไตรมาส)

**S: กองที่ถือต่อ (ยังอยู่ในอันดับ ≤ K) แต่หลุดเกณฑ์ → ถูกขาย** · **K: กองที่ยังถืออยู่ทั้งที่หลุดเกณฑ์**

| t | S: ขายเพราะหลุดเกณฑ์ | K: ถือต่อทั้งที่หลุดเกณฑ์ | S ชุดกอง | K ชุดกอง | M011 ชุดกอง |
|---|---|---|---|---|---|
| 2022-06-30 | - | - | ASP-NGF;B-BHARATA;FCSCBSETE;K-AEC;KKP GINFRAEQ-H-F;KT-MINING;PRINCIPAL GIF;TMBGINFRA | ASP-NGF;B-BHARATA;FCSCBSETE;K-AEC;KKP GINFRAEQ-H-F;KT-MINING;PRINCIPAL GIF;TMBGINFRA | ASP-NGF;FCSCBSETE;K-AEC;KKP GINFRAEQ-H-F;KT-MINING;PRINCIPAL GIF;TISCOGIF-R;TMBGINFRA |
| 2022-09-30 | - | - | ASP-NGF;B-BHARATA;FCSCBSETE;K-AEC;KKP GINFRAEQ-H-F;KT-MINING;PRINCIPAL GIF;TMBGINFRA | ASP-NGF;B-BHARATA;FCSCBSETE;K-AEC;KKP GINFRAEQ-H-F;KT-MINING;PRINCIPAL GIF;TMBGINFRA | ASP-NGF;FCSCBSETE;K-AEC;KKP GINFRAEQ-H-F;KT-MINING;PRINCIPAL GIF;TISCOGIF-R;TMBGINFRA |
| 2022-12-30 | - | - | ASP-NGF;EHD;FCSCBSETE;K-INDX;KKP GINFRAEQ-H-F;KT-MINING;PRINCIPAL GIF;TMBGINFRA | ASP-NGF;EHD;FCSCBSETE;K-INDX;KKP GINFRAEQ-H-F;KT-MINING;PRINCIPAL GIF;TMBGINFRA | ASP-NGF;FCSCBSETE;KKP GINFRAEQ-H-F;KT-MINING;PRINCIPAL GCLEAN-A;PRINCIPAL GIF;TISCOGIF-R;TMBGINFRA |
| 2023-03-31 | - | - | ASP-NGF;EHD;JSM;K-EUX;MEURO;ONE-EUROEQ;TISCOEU-A;UOBSJSM | ASP-NGF;EHD;JSM;K-EUX;MEURO;ONE-EUROEQ;TISCOEU-A;UOBSJSM | ASP-NGF;EHD;JSM;K-EUX;M-EUBANK;ONE-EUROEQ;TISCOEU-A;UOBSJSM |
| 2023-06-30 | ONE-EUROEQ | ONE-EUROEQ | ASP-IHEALTH;ASP-NGF;EHD;K-EUX;MEURO;ONE-UJE-RA;TISCOEU-A;TISCOJP | ASP-IHEALTH;ASP-NGF;EHD;K-EUX;MEURO;ONE-EUROEQ;TISCOEU-A;TISCOJP | ASP-IHEALTH;ASP-NGF;EHD;K-EUX;MEURO;ONE-EUROEQ;TISCOEU-A;TISCOJP |
| 2023-09-29 | - | - | ASP-NGF;EHD;K-EUX;K-USXNDQ-A(A);KKP SEMICON-H;ONE-UJE-RA;TISCOEU-A;TISCOJP | ASP-NGF;EHD;K-EUX;K-USXNDQ-A(A);KKP SEMICON-H;ONE-EUROEQ;TISCOEU-A;TISCOJP | ASP-NGF;EHD;K-EUX;K-USXNDQ-A(A);KKP NDQ100-H-F;KKP SEMICON-H;TISCOEU-A;TISCOJP |
| 2023-12-29 | - | - | ASP-NGF;K-USXNDQ-A(A);KKP SEMICON-H;KKP TECH-H;ONE-UJE-RA;PRINCIPAL GOPP-X;TISCOJP;TISTECH-A | ASP-NGF;B-INNOTECH;K-USXNDQ-A(A);KKP SEMICON-H;KKP TECH-H;PRINCIPAL GOPP-X;TISCOJP;TISTECH-A | ASP-NGF;ES-USTECH;K-USXNDQ-A(A);KKP NDQ100-H-F;KKP TECH-H;TISCOJP;TISTECH-A;TUSTECH-A |
| 2024-03-29 | - | - | ABIG;ASP-NGF;B-BHARATA;K-JPX-A(A);KKP TECH-H;KT-INDIA-A;TISCOINA-A;TISCOJP | ABIG;ASP-NGF;B-BHARATA;K-JPX-A(A);KKP TECH-H;KT-INDIA-A;TISCOINA-A;TISCOJP | ABIG;ASP-NGF;B-BHARATA;KKP TECH-H;KT-INDIA-A;TISCOIN;TISCOINA-A;TISCOJP |
| 2024-06-28 | - | - | ABIG;ASP-NGF;B-BHARATA;K-JPX-A(A);KKP TECH-H;KT-INDIA-A;ONE-INDIAOPP-IA;TISCOINA-A | ABIG;ASP-NGF;B-BHARATA;K-JPX-A(A);KKP TECH-H;KT-INDIA-A;ONE-INDIAOPP-IA;TISCOINA-A | ABIG;ASP-NGF;B-BHARATA;KT-INDIA-A;M-EUBANK;ONE-INDIAOPP-IA;TISCOIN;TISCOINA-A |
| 2024-09-30 | - | - | ABIG;B-BHARATA;K-US500X-A(A);KKP TECH-H;KT-INDIA-A;ONE-INDIAOPP-IA;TISCOINA-A;TUSFIN-A | ABIG;B-BHARATA;K-US500X-A(A);KKP TECH-H;KT-INDIA-A;ONE-INDIAOPP-IA;TISCOINA-A;TUSFIN-A | B-BHARATA;K-US500X-A(A);KT-INDIA-A;LHINDIAE-A;LHUSFIN-A;ONE-INDIAOPP-IA;TISCOINA-A;TUSFIN-A |
| 2024-12-31 | - | - | ABIG;K-US500X-A(A);KKP TECH-H;KT-FINANCE-A;KT-INDIA-A;LHESPORT-A;TISCOINA-A;TUSFIN-A | ABIG;K-US500X-A(A);KKP TECH-H;KT-FINANCE-A;KT-INDIA-A;LHESPORT-A;TISCOINA-A;TUSFIN-A | DAOL-PLAY;K-US500X-A(A);KT-FINANCE-A;KT-INDIA-A;LHESPORT-A;LHUSFIN-A;TISCOINA-A;TUSFIN-A |
| 2025-03-31 | - | - | DAOL-GOLD;KT-FINANCE-A;LHESPORT-A;LHUSFIN-A;ONE-GLOBFIN-IA;TCHT5M4;TISCOCH;TUSFIN-A | DAOL-GOLD;KT-FINANCE-A;LHESPORT-A;LHUSFIN-A;ONE-GLOBFIN-IA;TCHT5M4;TISCOCH;TUSFIN-A | DAOL-PLAY;KT-FINANCE-A;LHESPORT-A;LHUSFIN-A;M-EUBANK;TISCOC19;TISCOC21;TUSFIN-A |
| 2025-06-30 | - | - | DAOL-GOLD;ES-GINFRA-A;KKP GINFRAEQ-H-F;LHESPORT-A;PRINCIPAL GIF;TCHT5M4;TISCOCH;TUSFIN-A | DAOL-GOLD;ES-GINFRA-A;KKP GINFRAEQ-H-F;LHESPORT-A;PRINCIPAL GIF;TCHT5M4;TISCOCH;TUSFIN-A | DAOL-PLAY;ES-GINFRA-A;KKP GINFRAEQ-H-F;LHESPORT-A;M-EUBANK;PRINCIPAL GIF;TISCOC19;TISCOC21 |
| 2025-09-30 | - | - | DAOL-GOLD;DAOL-PLAY;LHESPORT-A;M-EUBANK;ONE-GLOBFIN-RA;PRINCIPAL GIF;TNEXTGEN-A;UCI | DAOL-GOLD;DAOL-PLAY;LHESPORT-A;M-EUBANK;ONE-GLOBFIN-RA;PRINCIPAL GIF;TNEXTGEN-A;UCI | ASP-NGF;DAOL-GOLD;DAOL-PLAY;LHESPORT-A;M-EUBANK;ONE-GLOBFIN-RA;TNEXTGEN-A;UCI |
| 2025-12-31 | - | - | DAOL-GOLD;ES-GINFRA-A;KKP GINFRAEQ-H;KT-MINING;M-EUBANK;PRINCIPAL GIF;TISCOGIF-R;UCI | DAOL-GOLD;ES-GINFRA-A;KKP GINFRAEQ-H;KT-MINING;M-EUBANK;PRINCIPAL GIF;TISCOGIF-R;UCI | ASP-NGF;DAOL-GOLD;DAOL-KOREAEQ;ES-GINFRA-A;KKP GINFRAEQ-H;M-EUBANK;PRINCIPAL GIF;PRINCIPAL KEQ |

## 7. Path luck

- **S**: Σ(r_M012 − r_M011) เดือนในไตรมาสชุดกอง**เหมือน** +0.0000 (3 เดือน) · **ต่าง** +0.0040 (42 เดือน) · ตัดไตรมาสที่ผลต่างบวกสุด (2023-12-29) → Sharpe M012 0.296 vs M011 0.330 Δ -0.034 · ไตรมาสลบสุด 2025-09-30

| ไตรมาส t | Σ Δr | ชุดกองต่าง |
|---|---|---|
| 2022-03-31 | +0.0000 | เหมือน |
| 2022-06-30 | +0.0103 | ต่าง |
| 2022-09-30 | -0.0075 | ต่าง |
| 2022-12-30 | +0.0038 | ต่าง |
| 2023-03-31 | +0.0002 | ต่าง |
| 2023-06-30 | +0.0001 | ต่าง |
| 2023-09-29 | -0.0072 | ต่าง |
| 2023-12-29 | +0.0182 | ต่าง |
| 2024-03-29 | -0.0052 | ต่าง |
| 2024-06-28 | -0.0022 | ต่าง |
| 2024-09-30 | +0.0040 | ต่าง |
| 2024-12-31 | -0.0122 | ต่าง |
| 2025-03-31 | +0.0001 | ต่าง |
| 2025-06-30 | +0.0167 | ต่าง |
| 2025-09-30 | -0.0153 | ต่าง |

- **K**: Σ(r_M012 − r_M011) เดือนในไตรมาสชุดกอง**เหมือน** -0.0013 (6 เดือน) · **ต่าง** +0.0055 (39 เดือน) · ตัดไตรมาสที่ผลต่างบวกสุด (2025-06-30) → Sharpe M012 0.530 vs M011 0.558 Δ -0.028 · ไตรมาสลบสุด 2025-09-30

| ไตรมาส t | Σ Δr | ชุดกองต่าง |
|---|---|---|
| 2022-03-31 | +0.0000 | เหมือน |
| 2022-06-30 | +0.0103 | ต่าง |
| 2022-09-30 | -0.0075 | ต่าง |
| 2022-12-30 | +0.0038 | ต่าง |
| 2023-03-31 | +0.0002 | ต่าง |
| 2023-06-30 | -0.0013 | เหมือน |
| 2023-09-29 | -0.0039 | ต่าง |
| 2023-12-29 | +0.0126 | ต่าง |
| 2024-03-29 | -0.0012 | ต่าง |
| 2024-06-28 | -0.0022 | ต่าง |
| 2024-09-30 | +0.0040 | ต่าง |
| 2024-12-31 | -0.0122 | ต่าง |
| 2025-03-31 | +0.0001 | ต่าง |
| 2025-06-30 | +0.0167 | ต่าง |
| 2025-09-30 | -0.0153 | ต่าง |

## 8. สมมติฐาน / ที่ validator ตีความเอง

- family = `fs.family_of(fc, groups, fixed=True)` (map เดียวกับ I_t) · AUM_fam = Σ AUM ล่าสุด>0 ภายใน 90 วันของ **ทุก class ของ family ในไฟล์ NAV (570 class)** รวม class ภาษี/ปันผล/ไม่สด · AUM ในหน่วยบาท
- อายุแบบ B: first_c = min(Registration_date ถ้า ≤ t, NAVDate แรก ถ้า ≤ t) · first_fam = min ข้าม class · ผ่านถ้า ≤ t − 730 วัน · class ที่ไม่มีค่าใดๆ ≤ t ไม่นับ (NAVDate แรก = ทั้งไฟล์ ไม่กรอง 2021)
- I_t' = แถวของ I_t (หลังใส่ SR12′ ของ M011 และตัดสด/ภาษี/-D/สัญญาณ) ที่ family ผ่าน Q1 และ Q2 · S: กรองก่อน `family_representatives` และ rank · fallback B0 ใช้ `b0_w` เดิมไม่กรอง
- K: reps = family ที่ผ่านเกณฑ์ + class ที่ถืออยู่ (แม้หลุดเกณฑ์) · อันดับคำนวณรวมกองถือต่อที่หลุดเกณฑ์ · กองถือต่อที่หลุดเกณฑ์ยังหลุดได้ด้วยอันดับ > K / ไม่สด · ขั้น fill ข้าม family ที่หลุดเกณฑ์ (ไม่เติมกองหลุดเกณฑ์ซ้ำแม้เคยถือ) · ถ้า S < 4 → B0 เหมือนเดิม · ตรวจ select_K = `wt.hysteresis_select` เมื่อไม่มี family หลุดเกณฑ์ (assert)
- 'ต่างตรงๆ' = select ด้วยเกณฑ์ + สถานะถือ/prev_fb ของ M011 ณ t เทียบชุดกองของ M011 ณ t · 'ต่างจริง' = ชุดกองใน plan เทียบ M011 · สืบทอด = ต่างจริงแต่ไม่ต่างตรงๆ (เทียบชุด FundCode)
- 'ขายเพราะหลุดเกณฑ์' (S) = family ที่ถือก่อน t, class ตัวแทนยังเป็น class ที่ถือ, อันดับ (ไม่กรอง ภายใต้สถานะถือของ S) ≤ K แต่หลุด Q1/Q2 · เป็นการประมาณเหตุผลเพื่ออธิบาย ไม่ใช่ counterfactual เต็ม
- Δ paired CI: `r11.paired_real` (block 3, 2000, seed 0, rf จริงรายเดือน, ตัวหาร sd(r)) · DSR = `rr.dsr_s` ที่ n_trials = 25 (นับ 2 trials ของ M012) · ต้นทุน/ERC/เพดาน/trend filter/ตารางเวลา/FeeModel เหมือน M011 (import run_m009/run_m011)
- พอร์ต 2025-12-31 (ไตรมาสที่ 16) ไม่อยู่ใน 45 เดือนที่วัด

## 9. ไฟล์
`M012_results.csv`, `M012_equity_curve.csv`, `M012_weights.csv`, `M012_quarter_diag.csv`, `M012_path_luck_by_quarter.csv`, `scratch/validator_m012_regression.json`, `scratch/validator_m012_regdate.py`
