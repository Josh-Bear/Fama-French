# M010-LLD — Trend 25 + ตัดกองซ้ำด้วย ρ_adj (lead-lag) (n_trials = 22) — ผลวัด (validator)

รันเมื่อ 2026-10-06T10:09:59.510374 · spec `specs/M010_leadlag_dedupe.md` + การตัดสินใจผู้ใช้ 2026-10-06 (ผ่าน = กลไกทำงาน และ Δ Sharpe full ≥ 0 เท่านั้น) · primary เม.ย. 2022 → 2025-12-31 (45 เดือน) · rf 2% · ไม่ปรับพารามิเตอร์ (ρ_adj > 0.85, lag 1 น้ำหนักเต็ม, 52 สัปดาห์, ขั้นต่ำ 30, K_fill 16) · ไม่มี holdout

## 1. Regression ก่อนรัน (threshold 1.01)

- น้ำหนักเทียบ `M004-TF-FX_weights.csv`: max|Δw| = 9.71e-17 · แถว 126 vs 126 · คีย์ฝั่งเดียว 0 → **PASS**
- Sharpe full/flat/nofront = 0.706119 / 0.720494 / 0.893296 (อ้างอิง 0.706119 / 0.720494 / 0.893296) → **PASS**
- จำนวน skip ที่ threshold 1.01 = 0 (ต้อง 0) · คู่ ρ_adj เป็น NaN (n<30/S≤0) ระหว่างรัน = 0 · ไม่ crash
- sanity ρ_adj ณ 2025-12-31 vs `DIAG_leadlag_pairs.csv`: 28 คู่ · |ต่าง| median 0.000 · max 0.009 · สัดส่วนคู่ที่ห่าง ≤ 0.05 = 100.0% · KKP GINFRAEQ-H vs ES-GINFRA-A: ของเรา 0.988 (DIAG 0.988) ≥ 0.85 → **PASS**

## 2. ตารางผลหลัก (ค่าธรรมเนียมจริง FEEUH full, rf 2%)

| โมเดล | Sharpe | CAGR | vol | maxDD | cost bp/ปี | turnover/ปี | CI95% Sharpe |
|---|---|---|---|---|---|---|---|
| **M010-LLD** | 0.600 | 0.0819 | 0.1073 | -0.1257 | 177.7 | 1.571 | [-0.50, 1.83] |
| M004-TF-FX (Trend 25) | 0.706 | 0.0917 | 0.1034 | -0.1100 | 184.8 | 1.615 | [-0.39, 1.87] |
| M001-MS (อ้างอิง COST_real_fees) | 0.105 | 0.0260 | 0.1116 | -0.1482 | 242.2 | — | — |
| B0 (อ้างอิง COST_real_fees) | 0.060 | 0.0196 | 0.1302 | -0.2142 | 53.2 | — | — |

## 3. ตัวชี้วัดหลัก + เกณฑ์ (ผู้ใช้ 2026-10-06)

- Δ Sharpe_full (M010-LLD − M004-TF-FX) paired block bootstrap (block 3, 2000, seed 0) = **-0.1060** CI95% **[-0.308, +0.187]** (คร่อม 0)
- กลไก: skip 106 ครั้ง ใน 14 ไตรมาส · mean G_t M010 0.045 vs TF 0.510 · mean DR² M010 2.136 vs TF 1.884 → **กลไกทำงาน**
- **ผลตามเกณฑ์: ไม่ผ่าน** — Δ Sharpe full < 0 (เกณฑ์ผู้ใช้ 2026-10-06)

- Δ ที่ cost 0.5%/ข้าง คงที่ (ประกอบ): -0.1097 CI [-0.318, +0.182] · Δ เฉพาะ 2023-07..2025-12 (full): -0.0328 CI [-0.223, +0.240]

## 4. กลไก (15 ไตรมาส 2022-03…2025-09, ใช้นิยาม ρ_adj §2 เดียวกัน)

| ตัวชี้วัด | M010 mean (median) | Trend 25 mean (median) |
|---|---|---|
| G_t (น้ำหนักกลุ่มซ้ำสูงสุด, ส่วนหุ้น normalize) | 0.045 (0.000) | 0.510 (0.545) |
| จำนวนคู่ ρ_adj > 0.85 ในพอร์ต | 0.13 (0.0) | 6.67 (7.0) |
| DR² (Σ_adj 8×8, หลัก) | 2.136 (2.057) | 1.884 (1.846) |
| ENB (Meucci PCA — กลับหัวได้) | 1.541 (1.579) | 1.508 (1.497) |

G_t รายไตรมาส (M010 / TF): 2022-03-31: 0.00/0.60 · 2022-06-30: 0.00/0.56 · 2022-09-30: 0.00/0.48 · 2022-12-30: 0.00/0.37 · 2023-03-31: 0.00/0.45 · 2023-06-30: 0.00/0.58 · 2023-09-29: 0.00/0.38 · 2023-12-29: 0.00/0.63 · 2024-03-29: 0.00/0.69 · 2024-06-28: 0.00/0.58 · 2024-09-30: 0.00/0.58 · 2024-12-31: 0.28/0.48 · 2025-03-31: 0.39/0.52 · 2025-06-30: 0.00/0.54 · 2025-09-30: 0.00/0.21
- จำนวน skip = 106 · ไตรมาสที่มี skip = 14/15 (2022-03-31, 2022-06-30, 2022-12-30, 2023-03-31, 2023-06-30, 2023-09-29, 2023-12-29, 2024-03-29, 2024-06-28, 2024-09-30, 2024-12-31, 2025-03-31, 2025-06-30, 2025-09-30) · อันดับลึกสุดที่ไล่ถึง 16 · ไตรมาส |S|<8 (ไม่ fallback): ['2023-03-31', '2023-06-30', '2023-12-29', '2024-03-29', '2024-09-30', '2025-03-31', '2025-06-30'] · fallback B0 (15 ไตรมาส): M010 0 / TF 0
- skip ที่ ρ_lag0 ≤ 0.85 แต่ ρ_adj > 0.85 (ส่วนที่ M005 ทำไม่ได้): 13/106

### ตาราง skip (ทั้ง 16 ไตรมาส รวม 2025-12-31 ที่ติดป้าย)

| t | family | กองที่ข้าม | rank | กองที่ชน | ρ_adj | ρ_lag0 |
|---|---|---|---|---|---|---|
| 2022-03-31 | ONE-VIETNAM | ONE-VIETNAM-RA | 2 | ASP-VIET | 0.924 | 0.904 |
| 2022-03-31 | UVO | UVO | 3 | ASP-VIET | 0.943 | 0.903 |
| 2022-03-31 | PRINCIPAL VNEQ | PRINCIPAL VNEQ-A | 4 | ASP-VIET | 0.891 | 0.909 |
| 2022-03-31 | K-VIETNAM | K-VIETNAM | 6 | ASP-VIET | 0.865 | 0.882 |
| 2022-03-31 | TMBGINFRA | TMBGINFRA | 7 | KKP GINFRAEQ-H-F | 0.997 | 0.996 |
| 2022-03-31 | PRINCIPAL GIF | PRINCIPAL GIF | 8 | KKP GINFRAEQ-H-F | 1.000 | 0.836 |
| 2022-03-31 | TISCOINA | TISCOINA-A | 11 | B-BHARATA | 0.957 | 0.935 |
| 2022-03-31 | TISCOGIF | TISCOGIF-R | 15 | KKP GINFRAEQ-H-F | 0.859 | 0.728 |
| 2022-06-30 | TMBGINFRA | TMBGINFRA | 2 | KKP GINFRAEQ-H-F | 0.999 | 0.992 |
| 2022-06-30 | PRINCIPAL GIF | PRINCIPAL GIF | 3 | KKP GINFRAEQ-H-F | 1.000 | 0.885 |
| 2022-06-30 | TISCOGIF | TISCOGIF-R | 5 | KKP GINFRAEQ-H-F | 0.855 | 0.781 |
| 2022-06-30 | TISCOINA | TISCOINA-A | 10 | B-BHARATA | 0.973 | 0.945 |
| 2022-06-30 | TISCOIN | TISCOIN | 11 | B-BHARATA | 0.926 | 0.870 |
| 2022-12-30 | PRINCIPAL GIF | PRINCIPAL GIF | 6 | KKP GINFRAEQ-H-F | 0.998 | 0.989 |
| 2022-12-30 | TMBGINFRA | TMBGINFRA | 8 | KKP GINFRAEQ-H-F | 0.996 | 0.924 |
| 2023-03-31 | K-EUX | K-EUX | 2 | EHD | 0.984 | 0.983 |
| 2023-03-31 | TISCOEU | TISCOEU-A | 5 | EHD | 0.981 | 0.982 |
| 2023-03-31 | ONE-EUROEQ | ONE-EUROEQ | 6 | EHD | 0.934 | 0.921 |
| 2023-03-31 | UOBSJSM | UOBSJSM | 8 | JSM | 1.000 | 1.000 |
| 2023-03-31 | MEURO | MEURO | 9 | EHD | 0.912 | 0.858 |
| 2023-03-31 | ONE-GLOBFIN | ONE-GLOBFIN-IA | 12 | M-EUBANK | 0.942 | 0.810 |
| 2023-03-31 | ASP-IHEALTH | ASP-IHEALTH | 13 | TBIOTECH | 0.961 | 0.887 |
| 2023-03-31 | MCHEVO | MCHEVO | 14 | TCHCON | 0.939 | 0.863 |
| 2023-03-31 | K-EUSMALL | K-EUSMALL | 15 | EHD | 0.947 | 0.781 |
| 2023-06-30 | K-EUX | K-EUX | 1 | EHD | 0.988 | 0.976 |
| 2023-06-30 | TISCOEU | TISCOEU-A | 2 | EHD | 0.984 | 0.979 |
| 2023-06-30 | MEURO | MEURO | 4 | EHD | 0.916 | 0.851 |
| 2023-06-30 | KT-JPFUND | KT-JPFUND-A | 8 | TISCOJP | 0.999 | 0.998 |
| 2023-06-30 | ASP-TOPBRAND | ASP-TOPBRAND | 9 | EHD | 0.907 | 0.861 |
| 2023-06-30 | ONE-UJE | ONE-UJE-RA | 10 | TISCOJP | 0.954 | 0.926 |
| 2023-06-30 | ONE-EUROEQ | ONE-EUROEQ | 12 | EHD | 0.955 | 0.927 |
| 2023-06-30 | MRENEW-PVD | MRENEW-PVD | 14 | EHD | 0.934 | 0.782 |
| 2023-06-30 | MRENEW | MRENEW-A | 15 | EHD | 0.934 | 0.782 |
| 2023-06-30 | PRINCIPAL EUEQ | PRINCIPAL EUEQ-A | 16 | EHD | 0.947 | 0.906 |
| 2023-09-29 | K-EUX | K-EUX | 2 | EHD | 0.991 | 0.974 |
| 2023-09-29 | K-USXNDQ | K-USXNDQ-A(A) | 5 | KKP NDQ100-H-F | 0.999 | 0.998 |
| 2023-09-29 | KKP TECH | KKP TECH-H | 6 | KKP SEMICON-H | 0.860 | 0.876 |
| 2023-09-29 | TISCOEU | TISCOEU-A | 7 | EHD | 0.985 | 0.978 |
| 2023-09-29 | TLUSNDQ | TLUSNDQ-H-A | 10 | KKP NDQ100-H-F | 0.999 | 0.999 |
| 2023-09-29 | LHSEMICON | LHSEMICON-A | 11 | KKP SEMICON-H | 0.997 | 0.990 |
| 2023-09-29 | ONE-UJE | ONE-UJE-RA | 12 | TISCOJP | 0.941 | 0.923 |
| 2023-09-29 | KT-JPFUND | KT-JPFUND-A | 14 | TISCOJP | 0.999 | 0.999 |
| 2023-12-29 | TUSTECH | TUSTECH-A | 1 | KKP NDQ100-H-F | 0.976 | 0.957 |
| 2023-12-29 | K-USXNDQ | K-USXNDQ-A(A) | 3 | KKP NDQ100-H-F | 1.000 | 0.980 |
| 2023-12-29 | KKP TECH | KKP TECH-H | 4 | KKP NDQ100-H-F | 0.983 | 0.980 |
| 2023-12-29 | ES-USTECH | ES-USTECH | 5 | KKP NDQ100-H-F | 0.973 | 0.893 |
| 2023-12-29 | TISTECH | TISTECH-A | 7 | KKP NDQ100-H-F | 0.941 | 0.933 |
| 2023-12-29 | KT-JPFUND | KT-JPFUND-A | 10 | TISCOJP | 0.999 | 0.999 |
| 2023-12-29 | B-INNOTECH | B-INNOTECH | 11 | KKP NDQ100-H-F | 0.874 | 0.864 |
| 2023-12-29 | ONE-METAVERSE | ONE-METAVERSE | 13 | KKP NDQ100-H-F | 0.925 | 0.949 |
| 2023-12-29 | DAOL-GTECH | DAOL-GTECH | 14 | KKP NDQ100-H-F | 0.946 | 0.941 |
| 2023-12-29 | M-META | M-META | 15 | KKP NDQ100-H-F | 0.917 | 0.947 |
| 2024-03-29 | B-BHARATA | B-BHARATA | 2 | TISCOINA-A | 0.906 | 0.854 |
| 2024-03-29 | TISCOIN | TISCOIN | 3 | TISCOINA-A | 0.949 | 0.922 |
| 2024-03-29 | ABIG | ABIG | 4 | TISCOINA-A | 0.929 | 0.903 |
| 2024-03-29 | LHINDIAE | LHINDIAE-A | 7 | KT-INDIA-A | 0.897 | 0.883 |
| 2024-03-29 | K-JPX | K-JPX-A(A) | 8 | ASP-NGF | 0.973 | 0.875 |
| 2024-03-29 | TSTAR | TSTAR-UH | 10 | TUSEQ-UH | 0.982 | 0.934 |
| 2024-03-29 | KT-JPFUND | KT-JPFUND-A | 13 | TISCOJP | 0.999 | 0.998 |
| 2024-03-29 | KT-US | KT-US-A | 15 | KKP TECH-H | 0.915 | 0.908 |
| 2024-03-29 | B-GLOBAL | B-GLOBAL | 16 | TUSEQ-UH | 0.928 | 0.863 |
| 2024-06-28 | B-BHARATA | B-BHARATA | 2 | TISCOINA-A | 0.932 | 0.884 |
| 2024-06-28 | ABIG | ABIG | 3 | TISCOINA-A | 0.887 | 0.900 |
| 2024-06-28 | TISCOIN | TISCOIN | 6 | TISCOINA-A | 0.951 | 0.922 |
| 2024-06-28 | TSTAR | TSTAR-UH | 8 | TUSEQ-UH | 0.986 | 0.941 |
| 2024-06-28 | ONE-GLOBFIN | ONE-GLOBFIN-IA | 10 | M-EUBANK | 0.852 | 0.818 |
| 2024-06-28 | LHINDIAE | LHINDIAE-A | 12 | KT-INDIA-A | 0.939 | 0.948 |
| 2024-09-30 | TUSFIN | TUSFIN-A | 2 | KT-FINANCE-A | 0.907 | 0.870 |
| 2024-09-30 | B-BHARATA | B-BHARATA | 3 | TISCOINA-A | 0.928 | 0.902 |
| 2024-09-30 | LHINDIAE | LHINDIAE-A | 4 | KT-INDIA-A | 0.926 | 0.945 |
| 2024-09-30 | LHUSFIN | LHUSFIN-A | 5 | KT-FINANCE-A | 0.905 | 0.875 |
| 2024-09-30 | KT-WEQ | KT-WEQ-A | 9 | K-US500X-A(A) | 0.976 | 0.929 |
| 2024-09-30 | TISCOUS | TISCOUS-A | 10 | K-US500X-A(A) | 1.000 | 0.981 |
| 2024-09-30 | MGMVOL | MGMVOL | 11 | ES-LOVE | 0.917 | 0.815 |
| 2024-09-30 | MGFPVD | MGFPVD | 13 | K-US500X-A(A) | 0.979 | 0.943 |
| 2024-09-30 | MGFGA | MGFGA | 14 | K-US500X-A(A) | 0.979 | 0.943 |
| 2024-09-30 | ABIG | ABIG | 15 | TISCOINA-A | 0.925 | 0.926 |
| 2024-12-31 | TUSFIN | TUSFIN-A | 2 | KT-FINANCE-A | 0.975 | 0.893 |
| 2024-12-31 | LHUSFIN | LHUSFIN-A | 3 | KT-FINANCE-A | 0.985 | 0.909 |
| 2024-12-31 | DAOL-PLAY | DAOL-PLAY | 4 | K-US500X-A(A) | 0.853 | 0.721 |
| 2024-12-31 | PRINCIPAL GOPP | PRINCIPAL GOPP-C | 9 | K-US500X-A(A) | 0.908 | 0.620 |
| 2024-12-31 | TISCOUS | TISCOUS-A | 10 | K-US500X-A(A) | 0.999 | 0.999 |
| 2024-12-31 | B-GLOBAL | B-GLOBAL | 11 | K-US500X-A(A) | 0.941 | 0.934 |
| 2025-03-31 | TISCOC19 | TISCOC19 | 3 | TISCOC21 | 1.000 | 1.000 |
| 2025-03-31 | TISCOC20 | TISCOC20 | 4 | TISCOC21 | 1.000 | 1.000 |
| 2025-03-31 | TCHT5M4 | TCHT5M4 | 5 | TISCOC21 | 1.000 | 1.000 |
| 2025-03-31 | TISCOCH | TISCOCH | 6 | TISCOC21 | 1.000 | 1.000 |
| 2025-03-31 | TCHT5M2 | TCHT5M2 | 7 | TISCOC21 | 0.999 | 0.999 |
| 2025-03-31 | DAOL-PLAY | DAOL-PLAY | 8 | LHESPORT-A | 0.999 | 0.998 |
| 2025-03-31 | ASP-HSI | ASP-HSI | 10 | TISCOC21 | 0.991 | 0.990 |
| 2025-03-31 | TUSFIN | TUSFIN-A | 12 | KT-FINANCE-A | 0.922 | 0.887 |
| 2025-03-31 | LHUSFIN | LHUSFIN-A | 15 | KT-FINANCE-A | 0.968 | 0.902 |
| 2025-03-31 | BIC | BIC | 16 | TISCOC21 | 1.000 | 0.720 |
| 2025-06-30 | PRINCIPAL GIF | PRINCIPAL GIF | 2 | KKP GINFRAEQ-H-F | 0.992 | 0.988 |
| 2025-06-30 | ES-GINFRA | ES-GINFRA-A | 3 | KKP GINFRAEQ-H-F | 0.991 | 0.985 |
| 2025-06-30 | DAOL-PLAY | DAOL-PLAY | 5 | LHESPORT-A | 0.999 | 0.997 |
| 2025-06-30 | TISCOGIF | TISCOGIF-R | 8 | KKP GINFRAEQ-H-F | 0.945 | 0.925 |
| 2025-06-30 | UINFRA-N | UINFRA-N | 10 | KKP GINFRAEQ-H-F | 0.908 | 0.898 |
| 2025-06-30 | TNEXTGEN | TNEXTGEN-A | 12 | DAOL-CYBER | 0.990 | 0.989 |
| 2025-06-30 | TISCOCH | TISCOCH | 14 | TISCOC21 | 1.000 | 1.000 |
| 2025-06-30 | TISCOC19 | TISCOC19 | 15 | TISCOC21 | 1.000 | 1.000 |
| 2025-06-30 | TCHT5M4 | TCHT5M4 | 16 | TISCOC21 | 1.000 | 1.000 |
| 2025-09-30 | DAOL-PLAY | DAOL-PLAY | 2 | LHESPORT-A | 0.999 | 0.997 |
| 2025-09-30 | TNEXTGEN | TNEXTGEN-A | 7 | DAOL-CYBER | 0.985 | 0.984 |
| 2025-09-30 | DAOL-GEDUCATION | DAOL-GEDUCATION | 9 | ONE-GLOBFIN-RA | 0.864 | 0.756 |
| 2025-09-30 | B-FINTECH | B-FINTECH | 10 | ONE-GLOBFIN-RA | 0.853 | 0.898 |
| 2025-12-31 (นอกช่วงตัดสิน) | PRINCIPAL KEQ | PRINCIPAL KEQ | 3 | DAOL-KOREAEQ | 0.995 | 0.939 |
| 2025-12-31 (นอกช่วงตัดสิน) | ES-GINFRA | ES-GINFRA-A | 5 | KKP GINFRAEQ-H | 0.988 | 0.981 |
| 2025-12-31 (นอกช่วงตัดสิน) | PRINCIPAL GIF | PRINCIPAL GIF | 8 | KKP GINFRAEQ-H | 0.991 | 0.987 |

## 5. ไตรมาสที่ชุดกองต่างจาก Trend 25

- ต่างทั้งหมด 15/15: **ต่างเพราะ skip ตรงๆ (ไตรมาสนั้นมี skip) 14** (2022-03-31, 2022-06-30, 2022-12-30, 2023-03-31, 2023-06-30, 2023-09-29, 2023-12-29, 2024-03-29, 2024-06-28, 2024-09-30, 2024-12-31, 2025-03-31, 2025-06-30, 2025-09-30) · **ต่างเพราะสืบทอดผ่าน hysteresis 1** (2022-09-30) · ไตรมาสที่มี skip แต่ชุดเท่ากัน: 0

## 6. รายงานคู่ (ไม่ใช้ตัดสิน) — ต่อกรณีต้นทุน

| ต้นทุน | M010 Sharpe | CAGR | vol | maxDD | TF Sharpe | CAGR | vol | maxDD |
|---|---|---|---|---|---|---|---|---|
| 0% | 0.772 | 0.1014 | 0.1065 | -0.1022 | 0.894 | 0.1121 | 0.1024 | -0.0971 |
| 0.5%/ข้าง | 0.611 | 0.0831 | 0.1072 | -0.1235 | 0.720 | 0.0931 | 0.1032 | -0.1041 |
| 1%/ข้าง | 0.449 | 0.0650 | 0.1084 | -0.1465 | 0.546 | 0.0744 | 0.1045 | -0.1111 |
| flat 0.5% (fee model) | 0.611 | 0.0831 | 0.1072 | -0.1235 | 0.720 | 0.0931 | 0.1032 | -0.1041 |
| ค่าธรรมเนียมจริง full | 0.600 | 0.0819 | 0.1073 | -0.1257 | 0.706 | 0.0917 | 0.1034 | -0.1100 |
| nofront | 0.771 | 0.1013 | 0.1065 | -0.1022 | 0.893 | 0.1120 | 0.1024 | -0.0971 |

| ตัวชี้วัด | M010 | TF |
|---|---|---|
| turnover/ปี | 1.571 | 1.615 |
| cost bp/ปี (full) | 177.7 | 184.8 |
| กองใหม่ต่อไตรมาส (2–15) | 3.00 | 3.43 |
| ระยะถือเฉลี่ย (ไตรมาส; กองที่เข้าหลังไตรมาสแรก) | 1.90 | 2.15 |
| ระยะถือเฉลี่ยทุกช่วงถือ | 2.18 | 2.14 |

## 7. ผลย่อยช่วงเวลา (Sharpe, full)

| ช่วง | M010 | TF |
|---|---|---|
| 2022 (เม.ย.–ธ.ค.) | -1.524 | -1.106 |
| 2023-07..2025-12 | 1.170 | 1.203 |
| 2022-04..2023-06 | -0.670 | -0.354 |
| drop-best-quarter (ตัดไตรมาสปฏิทินที่ดีสุด) | 0.300 (ตัด 2024Q1) | 0.394 (ตัด 2024Q1) |

## 8. DSR / ความเชื่อมั่น

- **DSR@22 (full) M010-LLD = 0.1530** (c50 = 0.1584) · CI95% Sharpe M010 [-0.504, 1.827] · TF [-0.393, 1.866] · เป้า 0.95: ไม่ถึง (0.600)

## 9. พอร์ต ณ 2025-12-31 (พอร์ตแนะนำหน้า 9 — รายงานแยก ไม่ใช้ตัดสิน)

- M010 (ส่วนกอง, ก่อนเงินสด trend): KKP GINFRAEQ-H 0.240; ASP-NGF 0.147; TISCONA 0.130; UCI 0.115; DAOL-KOREAEQ 0.112; M-EUBANK 0.091; KT-MINING 0.087; DAOL-GOLD 0.078
- Trend 25: KKP GINFRAEQ-H 0.197; ES-GINFRA-A 0.196; ASP-NGF 0.135; UCI 0.106; PRINCIPAL KEQ 0.102; DAOL-KOREAEQ 0.098; M-EUBANK 0.087; DAOL-GOLD 0.079
- skip ที่ 2025-12-31: PRINCIPAL KEQ ชน DAOL-KOREAEQ (ρ_adj 1.00, rank 3); ES-GINFRA-A ชน KKP GINFRAEQ-H (ρ_adj 0.99, rank 5); PRINCIPAL GIF ชน KKP GINFRAEQ-H (ρ_adj 0.99, rank 8)
- G_t / DR² ที่ 2025-12-31: M010 0.000 / 3.073 · TF 0.393 / 3.468

## 10. สมมติฐาน / การตีความของ validator

- reuse `run_m009.prepare/sim_cases/regression/holdings/entry_stats` (import ไม่แก้ไฟล์เดิม) · selection เขียนใหม่ใน `select_lld` (ขั้น 6 เท่านั้น) · ขั้นอื่น (family_representatives, rank_families, ERC LW, cap 25%, trend cash, fallback B0, ต้นทุน) เรียกใช้ซ้ำจาก weighting/run_m006_m007
- ρ_adj คำนวณจาก `QuarterContext.weekly_return_series` (ชุดเดียวกับ ERC) ตาม §2 ทุกบรรทัด (S_aa=Γ0+2Γ1, ตัวหาร n−1, L ใช้ตำแหน่งสัปดาห์ก่อนหน้าบนกริด) · เทียบกับทุกกองใน S ขณะนั้น · กองถือต่อไม่ถูกตัด · n<30/S≤0 = ผ่าน
- ไล่เติมถึง min(16, จำนวน family) ตาม §3 · ใช้ rank จาก SR12 (ไม่มี pen)
- กลไก G_t/DR²/ENB คำนวณกับพอร์ตจริงของทั้งสองโมเดลที่ 15 ไตรมาส (น้ำหนัก ERC หลัง cap, normalize=1) ใต้ Σ_adj จากสัปดาห์ร่วม listwise ของกองในพอร์ต (cov_leadlag เหมือน diag_leadlag รวม PSD clip) · ไตรมาสที่ fallback B0 ข้ามการคำนวณ
- 'กลไกทำงาน' = skip ≥ 1 และ mean G ลดลง และ mean DR²_adj ไม่ลดลง (เทียบ mean 15 ไตรมาส) ตาม §6 · 'ต่างเพราะ skip ตรงๆ' = ไตรมาสนั้นมี skip ≥ 1 และชุดต่าง; 'สืบทอด' = ชุดต่างแต่ไตรมาสนั้นไม่มี skip
- ไตรมาส 2025-12-31 (16th) ใช้ selection ต่อจากสายเดียวกัน (ไม่มีผลต่อไตรมาสก่อนหน้า) แต่ไม่อยู่ใน plan/Sharpe/กลไก 15 ไตรมาส
- Δ หลัก = full-fee 45 เดือน (เหมือน M009) · DSR = simulate.deflated_sharpe @22

## 11. ไฟล์
`M010_results.csv`, `M010_equity_curve.csv`, `M010-LLD_weights.csv`, `M010_skip_log.csv`, `M010_mechanism_quarterly.csv`, `M010_quarter_diag.csv`, `scratch/validator_m010_regression.json`, `scratch/validator_m010_sanity_rho.csv`
