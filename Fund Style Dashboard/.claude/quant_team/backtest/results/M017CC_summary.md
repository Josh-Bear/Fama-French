# M017-CC — M017-IDX + เพดานประเทศ 40% ของส่วนหุ้น — ผลวัด

รันเมื่อ 2026-10-07T11:09:41.069191 · spec `specs/M017CC_country_cap.md` (ลงทะเบียนก่อนรัน) · **trial #35** · ทุกอย่างอื่น = M017-IDX · โค้ด `backtest/run_m017cc.py`

**Regression (ผ่าน)**: ปิดกฎประเทศ → sleeves = M017-IDX ทุก offset (True) · M017-IDX full 0.477003 (= `M017_results.csv`) · M012-QF-S 0.659648 · Trend 25 0.719313 · offset M017-IDX max|Δ| 0.0e+00

## 1. ผลตามเกณฑ์ที่ล็อก (fee full): **ไม่ผ่าน**
- CAGR 6.92% (> 9.09%: ✗) · maxDD -12.50% (≥ −20%: ✓) · Sharpe 0.490

## 2. ตารางหลัก (offset 0, 45 เดือน, rf จริง)

| โมเดล | fee | Sharpe | CAGR | vol | maxDD | ต้นทุน %/ปี | turnover/ปี | DSR@35 | CI95% | 2022 (เม.ย.–) | 2023 | 2024 | 2025 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| M017-CC | full | 0.490 | 6.92% | 11.26% | -12.50% | 1.57 | 1.44 | 0.095 | [-0.50, 1.49] | -9.9% | 13.4% | 13.6% | 10.7% |
| M017-CC | nofront | 0.636 | 8.60% | 11.10% | -10.28% | 0.02 | 1.44 | 0.142 | [-0.34, 1.64] | -8.7% | 14.9% | 15.4% | 12.5% |
| M017-CC | flat 0.5%/ข้าง | 0.495 | 6.96% | 11.21% | -12.35% | 1.54 | 1.44 | 0.096 | [-0.50, 1.49] | -9.3% | 12.8% | 13.9% | 10.4% |
| M017-CC | 0% | 0.638 | 8.62% | 11.10% | -10.28% | 0.00 | 1.44 | 0.143 | [-0.34, 1.65] | -8.7% | 14.9% | 15.4% | 12.5% |
| M017-IDX | full | 0.477 | 6.71% | 11.11% | -12.50% | 1.65 | 1.44 | 0.088 | [-0.50, 1.49] | -9.9% | 13.4% | 13.6% | 9.9% |
| M017-IDX | nofront | 0.632 | 8.47% | 10.96% | -10.28% | 0.02 | 1.44 | 0.135 | [-0.33, 1.65] | -8.7% | 14.9% | 15.4% | 12.0% |
| M017-IDX | flat 0.5%/ข้าง | 0.489 | 6.82% | 11.05% | -12.35% | 1.54 | 1.44 | 0.090 | [-0.49, 1.49] | -9.3% | 12.8% | 13.9% | 9.9% |
| M017-IDX | 0% | 0.634 | 8.48% | 10.96% | -10.28% | 0.00 | 1.44 | 0.136 | [-0.33, 1.66] | -8.7% | 14.9% | 15.4% | 12.0% |
| Trend25 | full | 0.719 | 9.09% | 10.35% | -11.16% | 1.85 | 1.61 | 0.163 | [-0.37, 1.86] | -7.2% | 9.2% | 19.5% | 14.4% |
| Trend25 | nofront | 0.906 | 11.12% | 10.25% | -9.87% | 0.01 | 1.61 | 0.249 | [-0.17, 2.06] | -5.8% | 10.9% | 21.2% | 17.2% |
| Trend25 | flat 0.5%/ข้าง | 0.734 | 9.24% | 10.33% | -10.57% | 1.71 | 1.61 | 0.174 | [-0.36, 1.86] | -6.6% | 9.0% | 18.9% | 14.9% |
| Trend25 | 0% | 0.907 | 11.13% | 10.25% | -9.87% | 0.00 | 1.61 | 0.249 | [-0.17, 2.06] | -5.8% | 10.9% | 21.2% | 17.2% |
| M012-QF-S | full | 0.660 | 8.33% | 10.19% | -10.22% | 1.69 | 1.49 | 0.130 | [-0.48, 1.83] | -6.9% | 9.8% | 21.3% | 8.8% |
| M012-QF-S | nofront | 0.835 | 10.17% | 10.06% | -9.00% | 0.01 | 1.49 | 0.196 | [-0.30, 2.01] | -5.6% | 11.6% | 22.4% | 11.4% |
| M012-QF-S | flat 0.5%/ข้าง | 0.672 | 8.44% | 10.15% | -10.08% | 1.59 | 1.49 | 0.137 | [-0.46, 1.80] | -6.3% | 9.8% | 20.5% | 9.2% |
| M012-QF-S | 0% | 0.836 | 10.18% | 10.06% | -8.97% | 0.00 | 1.49 | 0.197 | [-0.30, 2.02] | -5.6% | 11.6% | 22.4% | 11.4% |

## 3. Paired Δ (M017-CC − อ้างอิง)

| เทียบ | fee | Δ Sharpe | CI95% | Δ CAGR |
|---|---|---|---|---|
| Trend25 | full | -0.229 | [-0.70, +0.33] | -2.17 pt |
| Trend25 | nofront | -0.270 | [-0.78, +0.28] | -2.52 pt |
| Trend25 | flat | -0.239 | [-0.73, +0.31] | -2.28 pt |
| M012-QF-S | full | -0.170 | [-0.65, +0.42] | -1.41 pt |
| M012-QF-S | nofront | -0.199 | [-0.71, +0.40] | -1.57 pt |
| M012-QF-S | flat | -0.178 | [-0.67, +0.42] | -1.48 pt |
| M017-IDX | full | +0.013 | [-0.05, +0.08] | +0.22 pt |
| M017-IDX | nofront | +0.004 | [-0.07, +0.07] | +0.13 pt |
| M017-IDX | flat | +0.006 | [-0.07, +0.07] | +0.13 pt |

## 4. offset 0/1/2 (fee full · ช่วงร่วม 42 เดือน)

| โมเดล | offset | Sharpe | CAGR | vol | maxDD | ต้นทุน %/ปี | ช่วงเต็มของ offset |
|---|---|---|---|---|---|---|---|
| M017-CC | 0 | 0.848 | 11.00% | 10.81% | -7.76% | 1.57 | 0.490 / 6.92% / -12.50% |
| M017-CC | 1 | 0.697 | 8.46% | 9.66% | -9.80% | 1.96 | 0.476 / 6.21% / -9.80% |
| M017-CC | 2 | 0.568 | 6.93% | 9.27% | -9.29% | 1.71 | 0.414 / 5.48% / -9.29% |
| M017-IDX | 0 | 0.839 | 10.76% | 10.65% | -7.76% | 1.65 | 0.477 / 6.71% / -12.50% |
| M017-IDX | 1 | 0.668 | 8.14% | 9.62% | -9.80% | 1.99 | 0.448 / 5.91% / -9.80% |
| M017-IDX | 2 | 0.557 | 6.83% | 9.28% | -9.29% | 1.66 | 0.404 / 5.38% / -9.29% |
| Trend25 | 0 | 0.995 | 12.16% | 10.21% | -8.76% | 1.85 | 0.719 / 9.09% / -11.16% |
| Trend25 | 1 | 0.411 | 5.69% | 10.14% | -9.25% | 2.29 | 0.235 / 3.77% / -10.72% |
| Trend25 | 2 | 0.442 | 5.83% | 9.63% | -13.32% | 2.40 | 0.314 / 4.55% / -13.32% |
| M012-QF-S | 0 | 0.933 | 11.32% | 10.07% | -9.92% | 1.69 | 0.660 / 8.33% / -10.22% |
| M012-QF-S | 1 | 0.425 | 6.16% | 11.09% | -12.30% | 1.97 | 0.272 / 4.32% / -12.30% |
| M012-QF-S | 2 | 0.763 | 9.22% | 9.75% | -9.46% | 2.01 | 0.607 / 7.69% / -9.46% |

## 5. กลไก (offset 0)

- ปัดเพราะกฎประเทศ รวม 5 ครั้ง · ไตรมาสที่มีเงินสดจาก infeasible 0/15 (สูงสุด 0.0% ของพอร์ตรวม) · B0 0 · ประเทศเฉลี่ย 4.20 · ประเทศสูงสุด 40.0% ของส่วนหุ้น (ไม่รวมเงินสด Trend)
- offset 0: rej_country 5 · ไตรมาสมีเงินสด infeasible 0 (สูงสุด 0.0%) · B0 0
- offset 1: rej_country 0 · ไตรมาสมีเงินสด infeasible 0 (สูงสุด 0.0%) · B0 0
- offset 2: rej_country 23 · ไตรมาสมีเงินสด infeasible 0 (สูงสุด 0.0%) · B0 0

| t | กองที่เลือก → ดัชนี | ปัด ประเทศ/corr | ประเทศ | ประเทศสูงสุด (ส่วนหุ้น) | เงินสด infeasible | B0 |
|---|---|---|---|---|---|---|
| 2022-03-31 | B-BHARATA->INDIA;TUSEQ-UH->USA;EHD->ACWI_FN;ASP-VIET->VIETNAM;TGHSTARP->ACWI_HC | 0/0 | 4 | USA 39.0% | 0.0% | - |
| 2022-06-30 | B-BHARATA->INDIA(keep);TUSEQ-UH->USA(keep);EHD->ACWI_FN(keep);TGHSTARP->ACWI_HC(keep);K-AEC->ASEAN | 0/0 | 4 | USA 37.2% | 0.0% | - |
| 2022-09-30 | B-BHARATA->INDIA(keep);TUSEQ-UH->USA(keep);TGHSTARP->ACWI_HC(keep);K-AEC->ASEAN(keep);B-ASIA->CHINA_H_SHARES | 0/0 | 4 | USA 35.8% | 0.0% | - |
| 2022-12-30 | B-BHARATA->INDIA(keep);TGHSTARP->ACWI_HC(keep);K-AEC->ASEAN(keep);B-ASIA->CHINA_H_SHARES(keep);KKP GINFRAEQ-H-F->ACWI_UT | 0/0 | 4 | USA 39.0% | 0.0% | - |
| 2023-03-31 | TGHSTARP->ACWI_HC(keep);B-ASIA->CHINA_H_SHARES(keep);K-EUX->EUROPE;ASP-NGF->JAPAN;K-CHX->CHINA_A_SHARES | 0/2 | 5 | CHINA_A_SHARES 22.4% | 0.0% | - |
| 2023-06-30 | K-EUX->EUROPE(keep);ASP-NGF->JAPAN(keep);LHSEMICON-A->ACWI_IT;KT-INDIA-A->INDIA;MATECH-A->TAIWAN | 0/1 | 5 | INDIA 25.0% | 0.0% | - |
| 2023-09-29 | K-EUX->EUROPE(keep);ASP-NGF->JAPAN(keep);LHSEMICON-A->ACWI_IT(keep);K-ATECH->KOREA;MFTECH->ACWI_CD | 0/3 | 4 | USA 30.8% | 0.0% | - |
| 2023-12-29 | ASP-NGF->JAPAN(keep);LHSEMICON-A->ACWI_IT(keep);MFTECH->ACWI_CD(keep);MATECH-A->TAIWAN;K-EUX->EUROPE | 0/1 | 4 | USA 30.3% | 0.0% | - |
| 2024-03-29 | ASP-NGF->JAPAN(keep);LHSEMICON-A->ACWI_IT(keep);TISCOINA-A->INDIA;ONE-GLOBFIN-IA->ACWI_FN;DAOL-CYBER->ACWI_CD | 0/0 | 4 | USA 25.2% | 0.0% | - |
| 2024-06-28 | LHSEMICON-A->ACWI_IT(keep);TISCOINA-A->INDIA(keep);ONE-GLOBFIN-IA->ACWI_FN(keep);MATECH-A->TAIWAN;ASP-NGF->JAPAN | 0/0 | 5 | INDIA 25.0% | 0.0% | - |
| 2024-09-30 | LHSEMICON-A->ACWI_IT(keep);TISCOINA-A->INDIA(keep);ONE-GLOBFIN-IA->ACWI_FN(keep);MATECH-A->TAIWAN(keep);B-GLOB-INFRA->ACWI_UT | 0/0 | 4 | USA 35.6% | 0.0% | - |
| 2024-12-31 | LHSEMICON-A->ACWI_IT(keep);ONE-GLOBFIN-IA->ACWI_FN(keep);B-GLOB-INFRA->ACWI_UT(keep);KT-ASEAN-A->ASEAN;MATECH-A->ACWI_CD | 5/2 | 4 | USA 36.5% | 0.0% | - |
| 2025-03-31 | ONE-GLOBFIN-IA->ACWI_FN(keep);B-GLOB-INFRA->ACWI_UT(keep);TCHT5M4->CHINA_H_SHARES;M-ASIA->TAIWAN;TNEXTGEN-A->USA | 0/0 | 4 | USA 38.0% | 0.0% | - |
| 2025-06-30 | ONE-GLOBFIN-IA->ACWI_FN(keep);B-GLOB-INFRA->ACWI_UT(keep);TCHT5M4->CHINA_H_SHARES(keep);KT-ASEAN-A->ASEAN;KT-EUROSM->EUROPE | 0/1 | 4 | EUROPE 36.8% | 0.0% | - |
| 2025-09-30 | ONE-GLOBFIN-IA->ACWI_FN(keep);TCHT5M4->CHINA_H_SHARES(keep);KT-VIETNAM-A->VIETNAM;UCI->CHINA_A_SHARES;K-EUX->EUROPE | 0/3 | 4 | EUROPE 40.0% | 0.0% | - |

## 6. ไฟล์
`M017CC_results.csv`, `M017CC_paired.csv`, `M017CC_offsets.csv`, `M017CC_quarter_diag.csv`, `M017CC_quarter_diag_offsets.csv`, `M017CC_weights.csv`, `M017CC_equity_curve.csv`
