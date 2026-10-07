# M017-IDX — คัดดัชนี MSCI ก่อน แล้วเลือกกองที่ตามดัชนี (index-first) บน M012-QF-S — ผลวัด

รันเมื่อ 2026-10-07T11:08:59.115582 · spec `specs/M017_index_first.md` (ลงทะเบียนก่อนรัน) · **trial #34** · universe เต็ม · rf จริง · FeeData(legacy=False) Actual · เม.ย. 2022–ธ.ค. 2025 (45 เดือน) · Sharpe = mean(r−rf)×12/(sd(r)×√12) · โค้ด `backtest/run_m017.py`

**Regression (ผ่าน)**: M012-QF-S full 0.659648 (ref 0.659648) · Trend 25 0.719313 (ref 0.719313) · Trend 25 offset 0/1/2 = `FULLUNIV_offsets.csv` (max|Δ| 5.6e-17) · refit exposure ไม่ใช้ cache 72 กอง-scope = cache (True) · assert ไม่มีข้อมูลหลัง t: index levels<=t, weekly<=t, exposure fit<=t (cache key=t + refit), quality<=t

## 1. ผลตามเกณฑ์ที่ล็อก (fee full): **ไม่ผ่าน**

- CAGR 6.71% (เกณฑ์ > 9.09%: ✗) · maxDD -12.50% (เกณฑ์ ≥ −20%: ✓) · Sharpe 0.477

## 2. ตารางหลัก (offset 0, 45 เดือน, rf จริง)

| โมเดล | fee | Sharpe | CAGR | vol | maxDD | ต้นทุน %/ปี | turnover/ปี | DSR@34 | CI95% Sharpe | 2022 (เม.ย.–) | 2023 | 2024 | 2025 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **M017-IDX** | full (จริง) | 0.477 | 6.71% | 11.11% | -12.50% | 1.65 | 1.44 | 0.090 | [-0.50, 1.49] | -9.9% | 13.4% | 13.6% | 9.9% |
| **M017-IDX** | nofront | 0.632 | 8.47% | 10.96% | -10.28% | 0.02 | 1.44 | 0.138 | [-0.33, 1.65] | -8.7% | 14.9% | 15.4% | 12.0% |
| **M017-IDX** | flat 0.5%/ข้าง | 0.489 | 6.82% | 11.05% | -12.35% | 1.54 | 1.44 | 0.092 | [-0.49, 1.49] | -9.3% | 12.8% | 13.9% | 9.9% |
| **M017-IDX** | 0% | 0.634 | 8.48% | 10.96% | -10.28% | 0.00 | 1.44 | 0.138 | [-0.33, 1.66] | -8.7% | 14.9% | 15.4% | 12.0% |
| Trend25 | full (จริง) | 0.719 | 9.09% | 10.35% | -11.16% | 1.85 | 1.61 | 0.165 | [-0.37, 1.86] | -7.2% | 9.2% | 19.5% | 14.4% |
| Trend25 | nofront | 0.906 | 11.12% | 10.25% | -9.87% | 0.01 | 1.61 | 0.253 | [-0.17, 2.06] | -5.8% | 10.9% | 21.2% | 17.2% |
| Trend25 | flat 0.5%/ข้าง | 0.734 | 9.24% | 10.33% | -10.57% | 1.71 | 1.61 | 0.177 | [-0.36, 1.86] | -6.6% | 9.0% | 18.9% | 14.9% |
| Trend25 | 0% | 0.907 | 11.13% | 10.25% | -9.87% | 0.00 | 1.61 | 0.253 | [-0.17, 2.06] | -5.8% | 10.9% | 21.2% | 17.2% |
| M012-QF-S | full (จริง) | 0.660 | 8.33% | 10.19% | -10.22% | 1.69 | 1.49 | 0.132 | [-0.48, 1.83] | -6.9% | 9.8% | 21.3% | 8.8% |
| M012-QF-S | nofront | 0.835 | 10.17% | 10.06% | -9.00% | 0.01 | 1.49 | 0.200 | [-0.30, 2.01] | -5.6% | 11.6% | 22.4% | 11.4% |
| M012-QF-S | flat 0.5%/ข้าง | 0.672 | 8.44% | 10.15% | -10.08% | 1.59 | 1.49 | 0.140 | [-0.46, 1.80] | -6.3% | 9.8% | 20.5% | 9.2% |
| M012-QF-S | 0% | 0.836 | 10.18% | 10.06% | -8.97% | 0.00 | 1.49 | 0.200 | [-0.30, 2.02] | -5.6% | 11.6% | 22.4% | 11.4% |

(DSR@34 ของ Trend 25 / M012-QF-S คำนวณที่ n = 34 เพื่อเทียบเท่านั้น · M016-CW อ้างอิงจาก `M016_results.csv`: 0.541 / 7.85% / −19.73% — ไม่ได้รันซ้ำ)

## 3. Paired Δ (M017-IDX − อ้างอิง, block bootstrap 3, 2000, seed 0)

| เทียบ | fee | Δ Sharpe | CI95% | Δ CAGR |
|---|---|---|---|---|
| Trend25 | full | -0.242 | [-0.71, +0.29] | -2.38 pt |
| Trend25 | nofront | -0.274 | [-0.77, +0.27] | -2.65 pt |
| Trend25 | flat | -0.245 | [-0.72, +0.29] | -2.41 pt |
| M012-QF-S | full | -0.183 | [-0.65, +0.40] | -1.62 pt |
| M012-QF-S | nofront | -0.203 | [-0.70, +0.38] | -1.70 pt |
| M012-QF-S | flat | -0.183 | [-0.67, +0.39] | -1.61 pt |

## 4. เลื่อนเดือน rebalance (fee full · ช่วงร่วม ก.ค. 2022–ธ.ค. 2025 = 42 เดือน)

| โมเดล | offset | Sharpe | CAGR | vol | maxDD | ต้นทุน %/ปี | turnover/ปี | Sharpe/CAGR/maxDD ช่วงเต็มของ offset |
|---|---|---|---|---|---|---|---|---|
| M017-IDX | 0 | 0.839 | 10.76% | 10.65% | -7.76% | 1.65 | 1.44 | 0.477 / 6.71% / -12.50% (45m) |
| M017-IDX | 1 | 0.668 | 8.14% | 9.62% | -9.80% | 1.99 | 1.63 | 0.448 / 5.91% / -9.80% (44m) |
| M017-IDX | 2 | 0.557 | 6.83% | 9.28% | -9.29% | 1.66 | 1.40 | 0.404 / 5.38% / -9.29% (43m) |
| Trend25 | 0 | 0.995 | 12.16% | 10.21% | -8.76% | 1.85 | 1.61 | 0.719 / 9.09% / -11.16% (45m) |
| Trend25 | 1 | 0.411 | 5.69% | 10.14% | -9.25% | 2.29 | 1.94 | 0.235 / 3.77% / -10.72% (44m) |
| Trend25 | 2 | 0.442 | 5.83% | 9.63% | -13.32% | 2.40 | 2.03 | 0.314 / 4.55% / -13.32% (43m) |
| M012-QF-S | 0 | 0.933 | 11.32% | 10.07% | -9.92% | 1.69 | 1.49 | 0.660 / 8.33% / -10.22% (45m) |
| M012-QF-S | 1 | 0.425 | 6.16% | 11.09% | -12.30% | 1.97 | 1.69 | 0.272 / 4.32% / -12.30% (44m) |
| M012-QF-S | 2 | 0.763 | 9.22% | 9.75% | -9.46% | 2.01 | 1.76 | 0.607 / 7.69% / -9.46% (43m) |

| โมเดล | Sharpe เฉลี่ย 3 offset (min–max) | CAGR เฉลี่ย (min–max) | maxDD แย่สุด |
|---|---|---|---|
| M017-IDX | 0.688 (0.557–0.839) | 8.58% (6.83%–10.76%) | -9.80% |
| Trend25 | 0.616 (0.411–0.995) | 7.89% (5.69%–12.16%) | -13.32% |
| M012-QF-S | 0.707 (0.425–0.933) | 8.90% (6.16%–11.32%) | -12.30% |

## 5. กลไกต่อไตรมาส (offset 0)

- fallback B0: **0/15** ไตรมาส · กองเฉลี่ย 5.00 · ถือต่อเฉลี่ย 2.80 · ปัดเพราะ corr รวม 13 · ปัดเพราะกฎ 1 ดัชนี→1 กอง 15 · family ซ้ำ 0
- ดัชนีที่ถูกข้าม (รวม 15 ไตรมาส): เชิงโครงสร้าง (ดัชนีรวม ไม่มีใน exposure) 26 · ไม่มีกองมีสิทธิ์ 30 · ช่องถูกครอง 41 · มีกองแต่ถูกปัดหมด 8
- จำนวนประเทศ (country_primary) เฉลี่ย 4.13 (min 3) · น้ำหนักรวมใน 1 ประเทศสูงสุด 53.2% ของพอร์ตรวม / 53.2% ของส่วนหุ้น · กองเดียวสูงสุด 25.0%
- offset 0: B0 0 · กองเฉลี่ย 5.00 · ปัด corr 13 · ประเทศเฉลี่ย 4.13 · ประเทศสูงสุด 53.2%
- offset 1: B0 0 · กองเฉลี่ย 5.00 · ปัด corr 5 · ประเทศเฉลี่ย 4.40 · ประเทศสูงสุด 49.0%
- offset 2: B0 0 · กองเฉลี่ย 5.00 · ปัด corr 24 · ประเทศเฉลี่ย 4.00 · ประเทศสูงสุด 54.1%

| t | top-5 ดัชนี (SR12_idx) | กองที่เลือก → ดัชนี | ข้าม (โครงสร้าง/ไม่มีกอง/ครอง/ปัดหมด) | ปัด b / corr | B0 | ประเทศ | ประเทศสูงสุด (พอร์ตรวม) |
|---|---|---|---|---|---|---|---|
| 2022-03-31 | ACWI_EN:1.65;ACWI_CS:1.23;INDIA:1.14;USA:0.96;ACWI_FN:0.93 | B-BHARATA->INDIA;TUSEQ-UH->USA;EHD->ACWI_FN;ASP-VIET->VIETNAM;TGHSTARP->ACWI_HC | 0/3/0/0 | 2 / 0 | - | 4 | USA 29.3% |
| 2022-06-30 | ACWI_EN:1.92;ACWI_UT:1.27;ASEAN:0.53;INDIA:0.49;ACWI_CS:0.37 | B-BHARATA->INDIA(keep);TUSEQ-UH->USA(keep);EHD->ACWI_FN(keep);TGHSTARP->ACWI_HC(keep);K-AEC->ASEAN | 0/2/0/0 | 0 / 0 | - | 4 | USA 27.9% |
| 2022-09-30 | ACWI_EN:1.37;ACWI_UT:1.01;BRAZIL:0.56;ACWI_CS:0.44;INDIA:0.23 | B-BHARATA->INDIA(keep);TUSEQ-UH->USA(keep);TGHSTARP->ACWI_HC(keep);K-AEC->ASEAN(keep);B-ASIA->CHINA_H_SHARES | 0/4/4/0 | 0 / 0 | - | 4 | USA 26.9% |
| 2022-12-30 | ACWI_EN:1.49;BRAZIL:0.66;INDIA:0.14;ASEAN:0.08;ACWI_UT:0.01 | B-BHARATA->INDIA(keep);TGHSTARP->ACWI_HC(keep);K-AEC->ASEAN(keep);B-ASIA->CHINA_H_SHARES(keep);KKP GINFRAEQ-H-F->ACWI_UT | 0/2/2/0 | 0 / 0 | - | 4 | USA 29.2% |
| 2023-03-31 | ACWI_EN:0.44;EUROPE:0.23;ACWI_IN:0.09;ACWI_CS:0.07;ACWI_FN:0.01 | TGHSTARP->ACWI_HC(keep);B-ASIA->CHINA_H_SHARES(keep);K-EUX->EUROPE;ASP-NGF->JAPAN;K-CHX->CHINA_A_SHARES | 3/3/2/1 | 3 / 2 | - | 5 | CHINA_A_SHARES 22.4% |
| 2023-06-30 | ACWI_IT:1.09;EUROPE:0.81;ACWI_IN:0.77;JAPAN:0.66;WORLD_EX_US:0.65 | K-EUX->EUROPE(keep);ASP-NGF->JAPAN(keep);LHSEMICON-A->ACWI_IT;KT-INDIA-A->INDIA;MATECH-A->TAIWAN | 4/1/3/1 | 1 / 1 | - | 5 | INDIA 25.0% |
| 2023-09-29 | ACWI_IT:1.68;ACWI_IN:1.56;EUROPE:1.52;WORLD_EX_US:1.34;WORLD:1.32 | K-EUX->EUROPE(keep);ASP-NGF->JAPAN(keep);LHSEMICON-A->ACWI_IT(keep);K-ATECH->KOREA;MFTECH->ACWI_CD | 4/2/4/1 | 1 / 3 | - | 4 | USA 30.8% |
| 2023-12-29 | ACWI_IT:2.69;ACWI_TC:1.98;USA:1.72;WORLD:1.60;ACWI:1.53 | ASP-NGF->JAPAN(keep);LHSEMICON-A->ACWI_IT(keep);MFTECH->ACWI_CD(keep);MATECH-A->TAIWAN;K-EUX->EUROPE | 2/3/4/0 | 0 / 1 | - | 4 | USA 30.3% |
| 2024-03-29 | INDIA:3.74;USA:2.64;ACWI_FN:2.58;WORLD:2.47;ACWI_IT:2.39 | ASP-NGF->JAPAN(keep);LHSEMICON-A->ACWI_IT(keep);TISCOINA-A->INDIA;ONE-GLOBFIN-IA->ACWI_FN;DAOL-CYBER->ACWI_CD | 2/3/3/0 | 3 / 0 | - | 4 | USA 25.2% |
| 2024-06-28 | INDIA:2.46;ACWI_FN:2.44;WORLD:2.00;USA:1.98;ACWI_TC:1.96 | LHSEMICON-A->ACWI_IT(keep);TISCOINA-A->INDIA(keep);ONE-GLOBFIN-IA->ACWI_FN(keep);MATECH-A->TAIWAN;ASP-NGF->JAPAN | 4/3/5/1 | 1 / 0 | - | 5 | INDIA 25.0% |
| 2024-09-30 | INDIA:2.06;ACWI_FN:1.90;TAIWAN:1.85;ACWI_UT:1.81;USA:1.57 | LHSEMICON-A->ACWI_IT(keep);TISCOINA-A->INDIA(keep);ONE-GLOBFIN-IA->ACWI_FN(keep);MATECH-A->TAIWAN(keep);B-GLOB-INFRA->ACWI_UT | 0/0/3/0 | 1 / 0 | - | 4 | USA 26.7% |
| 2024-12-31 | ACWI_FN:2.25;USA:1.92;ACWI_TC:1.74;WORLD:1.68;ACWI_UT:1.63 | LHSEMICON-A->ACWI_IT(keep);ONE-GLOBFIN-IA->ACWI_FN(keep);B-GLOB-INFRA->ACWI_UT(keep);KT-ASEAN-A->ASEAN;LHESPORT-A->ACWI_CD | 2/1/4/2 | 1 / 2 | - | 3 | USA 53.2% |
| 2025-03-31 | CHINA_H_SHARES:1.08;ACWI_FN:0.98;ACWI_TC:0.91;CHINA_ALL_SHARES:0.64;ACWI_UT:0.46 | ONE-GLOBFIN-IA->ACWI_FN(keep);B-GLOB-INFRA->ACWI_UT(keep);LHESPORT-A->ACWI_CD(keep);TCHT5M4->CHINA_H_SHARES;M-ASIA->TAIWAN | 1/1/2/0 | 0 / 0 | - | 4 | USA 30.2% |
| 2025-06-30 | ACWI_FN:0.76;ACWI_UT:0.52;CHINA_H_SHARES:0.49;ASEAN:0.34;CHINA_ALL_SHARES:0.28 | ONE-GLOBFIN-IA->ACWI_FN(keep);B-GLOB-INFRA->ACWI_UT(keep);TCHT5M4->CHINA_H_SHARES(keep);KT-ASEAN-A->ASEAN;KT-EUROSM->EUROPE | 2/1/3/1 | 1 / 1 | - | 4 | EUROPE 36.8% |
| 2025-09-30 | VIETNAM:1.90;ACWI_TC:1.53;CHINA_H_SHARES:1.43;ACWI_FN:1.40;WORLD_EX_US:0.95 | ONE-GLOBFIN-IA->ACWI_FN(keep);TCHT5M4->CHINA_H_SHARES(keep);KT-VIETNAM-A->VIETNAM;UCI->CHINA_A_SHARES;K-EUX->EUROPE | 2/1/2/1 | 1 / 3 | - | 4 | EUROPE 40.1% |

## 6. ไฟล์
`M017_results.csv`, `M017_paired.csv`, `M017_offsets.csv`, `M017_quarter_diag.csv`, `M017_quarter_diag_offsets.csv`, `M017_index_scores.csv`, `M017_weights.csv`, `M017_equity_curve.csv`, `scratch/validator_m017_regression.json`
