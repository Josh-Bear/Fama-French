# MSCI Fund Country/Sector Classification Dashboard

Streamlit app จัดกลุ่ม **กองทุนไทย (FIF)** ตาม **exposure ประเทศ/sector** —
regress ผลตอบแทนกองทุนกับ **MSCI index ทั้งชุด** (18 country / 10 sector) พร้อมกันด้วย ElasticNet
แล้วดูว่ากองโหลดหนักที่ index ไหน (primary/secondary) พร้อม scatter return–volatility
+ vol forecast ของ index (หน้า 4-5) · **style tilt** ของกองหุ้น — Momentum/Quality/Value/Low-Vol (หน้า 6)
และ **ความไวต่อ macro 7 ตัว** — Oil/Gold/USDTHB/Copper/DXY/VIX/US10Y (หน้า 7)

> 📚 **เอกสารระบบฉบับเต็ม: [`docs/`](docs/README.md)** — อธิบายแต่ละหน้า แหล่งข้อมูล และวิธีคำนวณ
> (แผนงาน/บันทึกการตัดสินใจเดิมย้ายไป [`docs/archive/`](docs/archive/README.md))
> (โปรเจกต์นี้แยกจาก Fama French SET50 โดยสมบูรณ์ — คนละโฟลเดอร์ คนละแอป)

---

## Quickstart

```bash
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt
./.venv/bin/python data_access.py          # build cache ครั้งแรก (~75 วิ: nav 336MB + clean + regress 209 กอง E × 2 scope)
./.venv/bin/python data_access.py vol      # build vol forecast cache (~10 วิ: EWMA/GARCH 28 index)
./.venv/bin/python data_access.py style-download   # snapshot ETF style -> base_data/ (ต้องต่อเน็ต — ครั้งแรก/อัปเดต)
./.venv/bin/python data_access.py style    # build style cache หน้า 6 (~15 วิ: 209 กอง E)
./.venv/bin/python data_access.py macro-download   # snapshot macro 7 ตัว (yfinance + FRED) -> base_data/ (ต้องต่อเน็ต)
./.venv/bin/python data_access.py macro    # build macro cache หน้า 7 (~5 วิ: 209 กอง E)
./.venv/bin/python data_access.py score    # refit country ชุด VIF-cleaned หน้า 8 (~15 วิ: 209 กอง E)
./.venv/bin/streamlit run app.py
```

เปิด http://localhost:8501 — โหลดจาก `cache/*.csv` (เร็ว); ปุ่ม **🔄 Rebuild** ในแอป build ใหม่จาก base_data

รัน checkpoint / test:
```bash
./.venv/bin/python checkpoint1.py     # Phase 1: filter 715 -> nav 680 -> threshold 368 -> policy E 313
./.venv/bin/python -m pytest -q       # unit tests (filter, matching, metrics, viz, vol, style, macro, score screen, TF model + หน้า 9)
```

---

## หน้าเว็บ (9 หน้า)

| หน้า | ทำอะไร |
|---|---|
| 🌍 **Country Match** | scatter กอง × exposure ประเทศ — x=ann return, y=ann vol, สี=4 quadrant (AUM/n_obs ดูใน hover) + filter |
| 🏭 **Sector Match** | เหมือน Country แต่จับคู่กับ MSCI sector 10 ตัว |
| 📊 **Match Strength** | เลือกกอง → bar standardized coefficient แต่ละ index (🔵 primary · 🟢 secondary = **≥70% ของ primary** · ⚪ อื่นๆ) toggle country/sector + โมเดล |
| 🔮 **Vol Forecast** | ทำนาย vol ของ MSCI index 21 วันข้างหน้า — EWMA vs GARCH(1,1) + walk-forward backtest + RMSE/MAE/QLIKE (ดู [`docs/pages/4-vol-forecast.md`](docs/pages/4-vol-forecast.md)) |
| 📉 **Filtered Scatter** | index scatter: x=return 21d, y=forecast vol (GARCH t-dist) + คลิกจุดดูกองทุนที่ match (ดู [`docs/pages/5-filtered-scatter.md`](docs/pages/5-filtered-scatter.md)) |
| 🎯 **Style Match** | scatter กอง E × style tilt (Momentum/Quality/Value/Low-Vol) — ป้ายดูเครื่องหมาย (Value− = Growth, LowVol− = High-Beta) + incremental R² (ดู [`docs/pages/6-style-match.md`](docs/pages/6-style-match.md)) |
| 🌐 **Macro Chain** | เลือกกอง E → bar ความไวต่อ macro 7 ตัว (% ต่อ 1 SD) — 🔵 implied (chain ผ่าน country/sector) คู่ 🟠 direct (regress NAV ตรง) + ◆ median กอง E (ดู [`docs/pages/7-macro-chain.md`](docs/pages/7-macro-chain.md)) |
| 🧭 **Score Screen** | 3 ส่วน: คะแนนโซน country × sector (momentum 12-1 + vol ทำนายต่ำ) → คัดกองที่ผ่านเกณฑ์ (score ≥ 0.7) ไม่ซ้ำการเดิมพัน สูงสุด 5 กอง (โหมดเริ่มต้นได้ 4) → **efficient frontier** ของกองชุดนั้น (Σ = B·F·Bᵀ+D · μ = Black-Litterman) (ดู [`docs/pages/8-score-screen.md`](docs/pages/8-score-screen.md)) |
| 📈 **TF Portfolio** | โมเดล M004-TF-FX ที่ผ่าน walk-forward backtest ของทีม quant: พอร์ตแนะนำ ณ วันที่เลือก (8 กอง SR12 · ERC · เงินสด 25% เมื่อ ACWI < SMA200) + ผลย้อนหลังด้วยค่าธรรมเนียมจริง (Sharpe 0.71 · ไม่ใช่คำแนะนำการลงทุน) (ดู [`docs/pages/9-tf-portfolio.md`](docs/pages/9-tf-portfolio.md)) |

---

## Pipeline (6 Phase)

```
FundProfile.csv ──filter 9 เกณฑ์──> 715 กอง (E600/F77/O38)         [Phase 1]
nav_history_db.csv ──chunked + dedupe(UpdateTime)──> 680 มี nav
                    ──threshold >600 จุด (NAVDate)──> 368 กอง
                    ──เฉพาะ policy E (config.APP_POLICY)──> 313 กอง
                    ──ตัด NAV เก่า >90 วัน / กองเลิกแล้ว──> 209 กองหุ้น เข้า regression   (-> cache/nav_clean.parquet)
สำหรับแต่ละกอง:
  NAV ──align NAVDate + ทบต้น index ตลอด gap + winsorize 1–99%──> return series   [Phase 2]
  return ──StandardScaler + ElasticNetCV(+Lasso/Ridge) vs 18/10 index──> coef, R²  [Phase 3]
           primary/secondary = |standardized coef| มากสุด
  NAV ──CAGR (วันปฏิทิน), std×√(จุดต่อปีจริง)──> annualized return/volatility       [Phase 4]
──> cache/results.csv + cache/coefs.csv ──> Streamlit 4 หน้า                        [Phase 5]

หน้า 4 (แยกอิสระ): MSCI index ──EWMA + GARCH(1,1), walk-forward──> vol forecast + backtest
──> cache/vol_forecast_{backtest,latest}.csv   (ดู docs/pages/4-vol-forecast.md)

หน้า 6 (ต่อจาก results.csv): กอง E 209 กอง ──regress vs [control ×3 + style ×4]──> ป้าย style ตามเครื่องหมาย + incremental R²
──> cache/style_{results,coefs}.csv   (ดู docs/pages/6-style-match.md)

หน้า 7 (ต่อจาก coefs.csv): Stage 1 = 28 index ~ macro 7 ตัว (OLS รายเดือน)
  implied = coef กอง (unstandardize) × Stage 1 เฉลี่ย country/sector · direct = NAV รายเดือน ~ macro
──> cache/macro_{loadings,index_betas}.csv   (ดู docs/pages/7-macro-chain.md)

หน้า 8 (ต่อจาก results.csv + index snapshot): โซน = percentile(return 252d ข้าม 21 วันล่าสุด ÷ realized vol ช่วงเดียวกัน)
  score กอง = R²(country×sector) × โซนของคู่ primary → greedy เลือกไม่ซ้ำ country/sector + score ≥ 0.7 → สูงสุด 5 กอง
  กองที่เลือก ──joint refit 3 ปี + Ledoit-Wolf──> Σ = B·F·Bᵀ+D ──Π = γΣ_sys·w_ref──> enumerate น้ำหนักจำนวนเต็ม % → Pareto frontier
──> cache/country_matches_clean11.csv (Σ/Π fit สดไม่ cache)   (ดู docs/pages/8-score-screen.md)
```

## โครงสร้าง

```
config.py            ค่าคงที่ทั้งหมด (path, filter criteria, column list, params)
data_access.py       orchestration + cache (build_pipeline) + UI layer (@st.cache_data)
viz.py               helper กราฟ plotly (scatter + quadrant, match strength bar)
page_common.py       shared helper หน้า scatter (guard + Country/Sector/Style page)
app.py               landing + ปุ่ม rebuild (build_pipeline + vol + style + macro cache)
pages/               1_Country_Match · 2_Sector_Match · 3_Match_Strength · 4_Vol_Forecast · 5_Filtered_Scatter · 6_Style_Match · 7_Macro_Chain · 8_Score_Screen · 9_TF_Portfolio
data/
  fund_profile.py    load + filter FundProfile.csv (9 เกณฑ์)
  nav_loader.py      chunked load nav_history + dedupe(FundCode,NAVDate keep UpdateTime ล่าสุด)
  msci_index.py      load MSCI country/sector + daily return
  style_factor.py    snapshot iShares factor ETF (yfinance) + style relative level + control (หน้า 6)
  macro_factor.py    snapshot macro 7 ตัว (yfinance + FRED) + แปลง % return / Δ รายเดือน (หน้า 7)
analysis/
  matching.py        build_fund_returns (Phase 2) + match_exposure (Phase 3) + nested_r2 (หน้า 6-7)
  metrics.py         annualized return/volatility (Phase 4)
  vol_forecast.py    EWMA + GARCH(1,1) + walk-forward + eval metrics (หน้า 4)
  macro_chain.py     Stage 1 + unstandardize + chain เฉลี่ย scope + direct OLS (หน้า 7)
  screening.py       คะแนนโซน country × sector + คะแนนกอง + greedy เลือกไม่ซ้ำ (หน้า 8 ส่วน 1-2)
  portfolio.py       Σ=B·F·Bᵀ+D · Black-Litterman Π · กริดน้ำหนัก + Pareto frontier (หน้า 8 ส่วน 3)
checkpoint1.py       Phase 1 recheck (715/680/368/E 313 + MSCI)
base_data/           raw MSCI csv/pdf (input — user วางเอง) + STYLE_FACTOR_ETF.csv / MACRO_FACTOR.csv (จาก *-download)
cache/               results.csv · coefs.csv · vol_forecast_* · style_* · macro_* · country_matches_clean11 (regenerate ได้ — gitignore)
tests/               test_filters · test_matching · test_metrics · test_smoke · test_viz · test_vol_forecast · test_style_* · test_macro_* · test_screening · test_portfolio
docs/                เอกสารระบบ (overview · ต่อหน้า · ภาคผนวก · archive)
```

---

## ผลที่ verify แล้ว (snapshot)

- filter → **715** กอง (E600/F77/O38) · join nav → **680** · threshold >600 → **368** · เฉพาะ policy E → **313** (reproduce เป๊ะกับข้อมูลจริง) · ตัด NAV เก่า/เลิกกอง → **209** (2026-09-30)
- **R² เฉลี่ยกอง E: country 0.57 · sector 0.42** — (ตอนที่ยังรวมทุก policy: F=0.15 · O=0.17 คือเหตุผลที่ตัดออก)
- validate กองจริง: K-INDIA→INDIA (R²0.74), ABJO→JAPAN (0.73), ABEG→EUROPE, **BCARE→sector Health Care (0.70)**
- NAVDate join corr (K-INDIA 0.765, ABJO 0.718) ยืนยันว่า MSCI เป็น THB แล้ว (ไม่มี FX noise)
- **style (หน้า 6, 313 กอง E · ก่อน clean NAV)**: กอง Utilities 10/10 และ Health Care 15/19 → Low-Vol · MGMVOL (Minimum Volatility fund) → Low-Vol ด้วย incremental R² สูงสุด 0.37 · กอง IT → Growth/High-Beta 53/68 · กอง Financials → Value 9/20
- **macro (หน้า 7, 313 กอง E · ก่อน clean NAV)**: Stage 1 R² เฉลี่ย 0.395 (66 เดือน) · implied กับ direct สอดคล้องข้ามกอง (corr VIX 0.84 · USDTHB 0.79 · US10Y 0.73) · ตัด F/O เพราะ chain มองไม่เห็นทอง/บอนด์ (กองทอง direct Gold 0.69–0.93 แต่ implied ~0.11)

---

## Known Limitations / Assumptions

1. **เฉพาะกองหุ้น 209 กอง (policy E)** — กอง F (ตราสารหนี้) / O (ทอง/REIT) ถูกตัดตั้งแต่ pipeline (`config.APP_POLICY`, 2026-09-29)
   เพราะ 28 ดัชนีที่ใช้เป็นดัชนีหุ้นล้วน (R² เฉลี่ยกอง F 0.15 · O 0.17) · และกองที่รายงาน NAV น้อย (< 600 จุด) ถูกตัดก่อนหน้านั้นแล้ว
   · กองที่ NAV ล่าสุดช้ากว่าดัชนีเกิน 90 วัน หรือเลิกกองแล้ว ก็ถูกตัด (313 → 209) และ return ที่คร่อมรูข้อมูลเกิน 10 วันทำการไม่ถูกใช้
   (ดู [data-sources](docs/appendix/data-sources.md)) · class ปันผล (-D) ใช้ NAV ที่ไม่รวมปันผล → return ต่ำกว่าผลตอบแทนรวมจริง
2. **Collinearity 18 country index** — ACWI/WORLD/EM/ACWI_EX_US ซ้อนกับ single-market (condition number 726)
   → บางกอง (โดยเฉพาะกอง US) ถูก aggregate แย่ง primary ไป (ตัดสินใจเก็บครบ 18 ตัว — ดู [data-sources](docs/appendix/data-sources.md))
3. **primary จาก |coefficient|** — บางกองอาจได้ coefficient ค่าลบเป็น primary (5/209 กองหลัง clean NAV)
4. **MSCI ไม่มี index ไทยตรงๆ** (ใกล้สุด = ASEAN)
5. **annualized return/vol** = CAGR ตามวันปฏิทิน · vol × √(จุด NAV ต่อปีจริง) (แก้จาก 252/n_obs เมื่อ 2026-10-02 — เดิม overstate ได้ถึง ~2 เท่า) · `n_obs` ยังแสดงใน hover + ตาราง
6. NAVDate สูงสุด 2026-08 > MSCI 2026-07 → NAV ~1 เดือนท้ายถูก inner join ตัด (ปกติ)
7. **Data cleaning (จาก code-review)**: ตัด NAV≤0/NaN **ก่อน** dedup · dedup เก็บแถว UpdateTime ล่าสุด (stable sort, ข้าม NaT) · guard `MIN_REGRESSION_OBS=30`+try/except ต่อกอง กัน build ล้มทั้งชุด
8. **Vol Forecast (หน้า 4) ไม่ winsorize raw index return โดยตั้งใจ** — ต่างจาก fund pipeline (Phase 2 ที่ winsorize 1–99%) เพราะ vol forecasting มาตรฐานต้องการให้โมเดล react ต่อ tail event จริง (เช่น regime Korea ผันผวนสูง มิ.ย. 2026 ที่โมเดลจับได้ถูกต้อง) · แต่ถ้ามี data error จริงจะไม่มีตัวกัน
9. **Style (หน้า 6) ใช้ ETF ที่ปิดตามเวลา NY (USD)** ขณะที่ NAV/MSCI ใช้ราคาปิดท้องถิ่น (THB) — สองโลกนี้ corr กันแค่ 0.78 จึงต้องคุมตลาดทั้งสองฝั่ง (MSCI_ACWI + ACWI_ETF) ไม่งั้น LowVol จะอุดส่วนต่างจนกองส่วนใหญ่ได้ป้าย High-Beta ปลอม · incremental R² median 0.038 (ต่ำเป็นปกติ) · snapshot ETF ไม่อัปเดตเอง
10. **Macro (หน้า 7) implied เป็นค่าอนุมานผ่าน index หุ้น** — มองไม่เห็นทอง/บอนด์/FX hedge จึงใช้เฉพาะกอง E และแสดง direct (regress NAV รายเดือนตรง) คู่เสมอ · coef ใน coefs.csv เป็น standardized ต้อง unstandardize ก่อน chain และ country/sector ต้องเฉลี่ย (รวมกัน = นับตลาดซ้ำ) · USDTHB กับ DXY แยกผลกันไม่เสถียร (corr 0.71) · snapshot macro ไม่อัปเดตเอง

## Open Items
- ลอง prune ชุด country index (เหลือ single-market) เทียบผล primary — ยังไม่ทำ (เก็บ 18 ตามที่ตัดสินใจ)
- ราคาหุ้นไทยตรงๆ / hedge FX per fund — ยังไม่แยก
- ~~annualize ด้วยเวลาจริงแทน 252/n_obs~~ (ทำแล้ว 2026-10-02) · รวมปุ่ม rebuild ทำแล้ว (build_pipeline + vol + style + macro)
- เพิ่ม scope "style" ในหน้า 3 Match Strength — ยังไม่ทำ (นอก scope หน้า 6)
- macro: USDCNY เป็น factor ที่ 8 · residual diagnostic — ยังไม่ทำ (นอก scope หน้า 7)
