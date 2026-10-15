# 📚 เอกสารระบบ — MSCI Fund Style Dashboard

เอกสารชุดนี้อธิบาย **ระบบที่ทำงานอยู่จริง** (system documentation) — ว่าแต่ละหน้าทำอะไร ใช้ข้อมูลจากไหน โมเดลคำนวณยังไง
แยกออกจากเอกสารเชิงประวัติ (แผนงาน/บันทึกการตัดสินใจ/code review) ที่ย้ายไป [`archive/`](archive/) แล้ว

> อัปเดตล่าสุด: 2026-09-15 · โค้ดอ้างอิง: `config.py`, `data/`, `analysis/`, `pages/`

---

## ระบบนี้ทำอะไร

จัดกลุ่ม **กองทุนรวมไทยประเภท FIF (ลงทุนต่างประเทศ)** ว่าแต่ละกองมี **exposure** ไปที่ประเทศไหน / sector ไหน
โดยไม่ต้องพึ่งพอร์ตถือครองจริง — ใช้วิธี **regress ผลตอบแทน NAV ของกองกับดัชนี MSCI ทั้งชุดพร้อมกัน**
แล้วดูว่ากองโหลดน้ำหนักไปที่ดัชนีตัวไหน (เหมือนหลักการ factor model ของ Fama-French)

พร้อมส่วนเสริม: ทำนายความผันผวน (volatility) ของดัชนี MSCI ล่วงหน้า 21 วัน
**style tilt** ของกองหุ้น (Momentum / Quality / Value / Low-Vol) เทียบกับ iShares MSCI factor ETF
และ **ความไวต่อปัจจัยมหภาค 7 ตัว** (Oil, Gold, USDTHB, Copper, DXY, VIX, US10Y) ของกองหุ้น

**ครอบคลุม 209 กองหุ้น** (policy E — จาก 600 กอง E ที่เข้าเกณฑ์ ในทั้งหมด 715 กอง · กอง F/O ถูกตัดตั้งแต่ pipeline · ตัดกอง NAV เก่า/เลิกกองแล้ว) · ช่วงข้อมูล 2021-01 → 2026-07

---

## สารบัญ

### หน้าเว็บ (10 หน้า)
| เอกสาร | หน้า | สรุป |
|---|---|---|
| [1-country-match](pages/1-country-match.md) | 🌍 Country Match | scatter กองทุน × exposure **ประเทศ** (18 ดัชนี) |
| [2-sector-match](pages/2-sector-match.md) | 🏭 Sector Match | scatter กองทุน × exposure **sector** (10 ดัชนี) |
| [3-match-strength](pages/3-match-strength.md) | 📊 Match Strength | เจาะรายกอง — bar ความแรงของแต่ละดัชนี |
| [4-vol-forecast](pages/4-vol-forecast.md) | 🔮 Vol Forecast | ทำนาย vol ดัชนี 21 วัน (EWMA vs GARCH) |
| [5-filtered-scatter](pages/5-filtered-scatter.md) | 📉 Filtered Scatter | index scatter (return ที่ผ่านมา × vol ที่ทำนาย) + drill-down กองทุน |
| [6-style-match](pages/6-style-match.md) | 🎯 Style Match | scatter กอง E × **style tilt** (4 factor, ป้ายตามเครื่องหมาย) + incremental R² |
| [7-macro-chain](pages/7-macro-chain.md) | 🌐 Macro Chain | เจาะรายกอง E — ความไวต่อ **macro 7 ตัว** (% ต่อ 1 SD) · implied (chain ผ่าน country/sector) คู่ direct (regress NAV ตรง) |
| [8-score-screen](pages/8-score-screen.md) | 🧭 Score Screen | คะแนนโซน country × sector → คัดกองที่ผ่านเกณฑ์ไม่ซ้ำการเดิมพัน (สูงสุด 5 · โหมดเริ่มต้นได้ 4) → efficient frontier ของกองชุดนั้น |
| [9-tf-portfolio](pages/9-tf-portfolio.md) | 📈 TF Portfolio | โมเดล M004-TF-FX ที่ผ่าน walk-forward backtest — พอร์ตแนะนำ ณ วันที่เลือก (8 กอง SR12 + ERC + เงินสดตาม trend) + ผลย้อนหลังด้วยค่าธรรมเนียมจริง |
| [10-gc75-frontier](pages/10-gc75-frontier.md) | 🗺 M019 Frontier | efficient frontier ของกองที่ M019 (หุ้น 3 กอง + ขาทอง) ถือจริง 4 ไตรมาส + จุด MVP / max Sharpe / ERC · เทียบ max Sharpe กับ ERC |
| [11-m052-frontier](pages/11-m052-frontier.md) | 🧭 M052 Frontier | frontier แบบหน้า 10 ของพอร์ตที่ M052 ถือจริง (CANARY บอนด์ AGG + VSL) · คาดหวัง vs จริง |

### ภาคผนวก
| เอกสาร | เนื้อหา |
|---|---|
| [data-sources](appendix/data-sources.md) | ไฟล์ข้อมูลดิบทุกไฟล์ · schema · ที่มา · ข้อจำกัด |
| [methodology](appendix/methodology.md) | วิธีคำนวณทั้งหมด — filter, return series, ElasticNet, metrics, EWMA/GARCH, style factor |

---

## ภาพรวม pipeline

```
base_data/FundProfile.csv ──กรอง 9 เกณฑ์──────────────> 715 กอง (E=600 / F=77 / O=38)
base_data/nav_history_db.csv ──chunked + dedupe───────> 680 กองมีประวัติ NAV
                              ──ตัด NAVDate ≤ 600 จุด──> 368 กอง
                              ──เฉพาะ policy E (APP_POLICY)──> 313 กอง
                              ──ตัด NAV เก่า >90 วัน / กองเลิก──> 209 กองหุ้น เข้า regression
                              ──> cache/nav_clean.parquet (NAV ที่ clean แล้ว · ขั้นหลังอ่านจากนี่)

ต่อ 1 กอง:
  NAV ──align ด้วย NAVDate + ทบต้นดัชนีช่วงที่กองไม่รายงาน + ทิ้ง return คร่อมรู >10 วัน + winsorize 1–99%──> return series
  return ──StandardScaler + ElasticNetCV (เทียบ Lasso/Ridge) vs 18/10 ดัชนี──> coefficient + R²
  NAV ──CAGR ตามวันปฏิทิน · std×√(จุด NAV ต่อปีจริง)──────────────────────────> annualized return / vol
                                          ↓
              cache/results.csv (209×16) + cache/coefs.csv (5,852×8)
                                          ↓
                        หน้า 1 · 2 · 3 (Streamlit)

แยกอิสระ (ไม่พึ่งข้อมูลกองทุน):
  MSCI 28 ดัชนี ──EWMA + GARCH(1,1) walk-forward──> cache/vol_forecast_*.csv ──> หน้า 4

ต่อจากผลกองทุน (เฉพาะกอง E 209 กอง):
  base_data/STYLE_FACTOR_ETF.csv (snapshot iShares factor ETF) ──de-market ÷ ACWI──> style factor 4 ตัว
  return กอง ──regress vs [control ×3 + style ×4]──> ป้าย style ตามเครื่องหมาย + incremental R²
          ──> cache/style_results.csv + style_coefs.csv ──> หน้า 6

ต่อจากผลกองทุน (เฉพาะกอง E 209 กอง):
  base_data/MACRO_FACTOR.csv (snapshot yfinance + FRED) ──month-end · % return / Δ──> macro 7 ตัว
  MSCI 28 ดัชนี ──OLS รายเดือน vs macro──> Stage 1 (B: ดัชนี × macro)
  coef กอง (unstandardize) × B เฉลี่ย country/sector ──> implied · NAV รายเดือน ──OLS──> direct
          ──> cache/macro_loadings.csv + macro_index_betas.csv ──> หน้า 7

ต่อจากผลกองทุน (เฉพาะกอง E 209 กอง):
  MSCI 28 ดัชนี ──percentile(return 252d ข้าม 21 วันล่าสุด ÷ realized vol ช่วงเดียวกัน)──> คะแนนโซน
  กอง E ──refit กับ country ชุด VIF-cleaned 11 ตัว──> cache/country_matches_clean11.csv
          ──คะแนน = R²(c×s) × โซนของคู่ primary + greedy ไม่ซ้ำ country/sector + score ≥ 0.7──> สูงสุด 5 กอง
  กองที่เลือก ──joint refit 3 ปี + Ledoit-Wolf + Π = γΣ_sys·w_ref──> enumerate น้ำหนัก + Pareto──> หน้า 8 ส่วนที่ 3
```

---

## วิธีรัน

```bash
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt

./.venv/bin/python data_access.py        # build cache กองทุน (~2-3 นาที)
./.venv/bin/python data_access.py vol    # build cache vol forecast (~10 วิ)
./.venv/bin/python data_access.py style-download   # snapshot ETF style (ต้องต่อเน็ต — ครั้งแรก/อัปเดตเท่านั้น)
./.venv/bin/python data_access.py style  # build cache style หน้า 6 (~40 วิ)
./.venv/bin/python data_access.py macro-download   # snapshot macro 7 ตัว (ต้องต่อเน็ต — ครั้งแรก/อัปเดตเท่านั้น)
./.venv/bin/python data_access.py macro  # build cache macro หน้า 7 (~15 วิ)
./.venv/bin/python data_access.py score  # refit country ชุด VIF-cleaned หน้า 8 (~35 วิ)
./.venv/bin/python data_access.py tf     # backtest + replay โมเดลหน้า 9 (~10 วิ)
./.venv/bin/streamlit run app.py         # เปิดที่ http://localhost:8501
```

ปุ่ม **🔄 Rebuild** ในแอป build ทุก cache รวดเดียว (style/macro จะ build เฉพาะเมื่อมี snapshot แล้ว — แอปไม่ดึงเน็ตเอง)

**ตรวจสอบระบบ:**
```bash
./.venv/bin/python checkpoint1.py            # ตรวจ 715 / 680 / 368 / E 313 + MSCI
./.venv/bin/python -m pytest -q              # unit tests
```

---

## โครงสร้างโค้ด

| ส่วน | ไฟล์ | หน้าที่ |
|---|---|---|
| **ค่าคงที่** | `config.py` | path, เกณฑ์กรอง, รายชื่อดัชนี, พารามิเตอร์โมเดลทั้งหมด (single source) |
| **โหลดข้อมูล** | `data/fund_profile.py` · `nav_loader.py` · `msci_index.py` · `style_factor.py` · `macro_factor.py` | อ่าน+กรอง base_data · สร้าง style / macro factor |
| **คำนวณ** | `analysis/matching.py` · `metrics.py` · `vol_forecast.py` · `macro_chain.py` · `screening.py` · `portfolio.py` · `fund_signals.py` · `fund_weighting.py` · `fund_backtest.py` · `fund_fees.py` · `tf_model.py` | return series, regression, metrics, forecast, macro chain, คะแนนโซน/คัดกอง, risk model + frontier, โมเดลหน้า 9 (สัญญาณ/ERC/backtest/ค่าธรรมเนียม) |
| **ประสาน+cache** | `data_access.py` | รัน pipeline → เขียน cache → ป้อน UI (`@st.cache_data`) |
| **UI** | `app.py` · `pages/` · `viz.py` · `page_common.py` | หน้าเว็บ + กราฟ |
| **ตรวจสอบ** | `checkpoint1.py` · `tests/` | recheck ตัวเลข + unit tests |

---

## ข้อจำกัดสำคัญที่ต้องรู้ก่อนใช้ผล

1. **เฉพาะกองหุ้น 209 กอง (policy E)** — กอง F/O ถูกตัดตั้งแต่ pipeline (ดัชนีที่ใช้เป็นดัชนีหุ้นล้วน) กองที่รายงาน NAV น้อยกว่า 600 จุด และกองที่ NAV ล่าสุดเก่ากว่าดัชนีเกิน 90 วัน/เลิกกองแล้วถูกตัด — ไม่ใช่ทุกกอง FIF
2. **ดัชนี 18 ตัวซ้อนทับกันเอง (collinearity)** — ACWI/WORLD/EM ครอบ single-market อยู่แล้ว
   บางกอง (โดยเฉพาะกองหุ้นสหรัฐฯ) จึงถูกดัชนีรวมแย่ง primary ไป → **ต้องดู R² ประกอบเสมอ**
3. **ไม่มีดัชนีประเทศไทยตรงๆ** — ใกล้สุดคือ ASEAN
4. **annualized return/vol ของกองเป็นข้อมูลอดีตทั้งช่วง** — return = CAGR ตามวันปฏิทิน · vol ปรับตามจำนวนจุด NAV ต่อปีจริง
   (แก้จากสูตร 252/n_obs เมื่อ 2026-10-02 — รายละเอียดใน [methodology](appendix/methodology.md))
5. **หน้า 6 (style) ใช้ ETF ที่ปิดตามเวลา NY** — ต้องคุมตลาดทั้งฝั่ง MSCI และฝั่ง ETF · incremental R² ต่ำ (~0.04) เป็นปกติ
   (รายละเอียดใน [6-style-match](pages/6-style-match.md))
6. **หน้า 7 (macro) implied เป็นค่าอนุมานผ่านหุ้นเท่านั้น** — มองไม่เห็นทอง/บอนด์/FX hedge จึงใช้เฉพาะกอง E และแสดง direct คู่เสมอ
   (รายละเอียดใน [7-macro-chain](pages/7-macro-chain.md))
7. **หน้า 8 (score) ใช้ return ที่เกิดไปแล้วเป็นสัญญาณ** — 252 วันย้อนหลังโดยข้าม 21 วันล่าสุด (momentum 12-1) หารด้วย realized vol ช่วงเดียวกัน
   ระบบยังไม่มีโมเดลพยากรณ์ผลตอบแทน · น้ำหนักพอร์ตในส่วนที่ 3 มาจาก Π ที่ถอดกลับจากน้ำหนักเท่ากัน (ไม่ได้ใช้สัญญาณคัดกอง) และ Σ ยังมีข้อจำกัดที่รู้แล้ว (รายละเอียดใน [8-score-screen](pages/8-score-screen.md))
8. **เป็นการวิเคราะห์เชิงสถิติ ไม่ใช่คำแนะนำการลงทุน**
