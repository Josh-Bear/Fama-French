# ภาคผนวก: วิธีการคำนวณ (Methodology)

ทุกพารามิเตอร์ในเอกสารนี้อยู่ใน `config.py` ที่เดียว

---

## 1. สร้าง return series ของกองทุน (`analysis/matching.py::build_fund_returns`)

**โจทย์:** กองไม่ได้รายงาน NAV ทุกวันทำการ ถ้าใช้ `pct_change()` ตรงๆ จะได้ "ผลตอบแทน 1 วัน" ที่จริงกินเวลาหลายวัน
แล้วเอาไปเทียบกับ return รายวันของดัชนีไม่ตรงกัน

**วิธีแก้ (แก้ทั้ง gap และ NAV lag ด้วยขั้นตอนเดียว):**

```
1. ใช้ NAVDate ของกองเป็นแกนเวลาหลัก (ไม่ forward-fill NAV)
2. ตัด NAVDate ที่อยู่นอกช่วงดัชนี MSCI (ก่อน 2021-01-01 / หลัง 2026-07-31)
3. fund_return  = NAV.pct_change()                              ← ผลตอบแทนกองระหว่าง NAVDate ติดกัน
4. index_at     = index_level.reindex(NAVDate, method="ffill")  ← ระดับดัชนี ณ วันเดียวกัน
   index_return = index_at.pct_change()                         ← = ผลตอบแทนดัชนี "ทบต้น" ตลอดช่วงที่กองไม่รายงาน
5. ทิ้งแถวที่คร่อมรูข้อมูล: วันทำการของดัชนีที่หายระหว่าง NAVDate ติดกัน > NAV_MAX_GAP_BDAYS (10)
6. winsorize ทุกคอลัมน์ที่ percentile 1–99 (clip แยกทีละ series ไม่ drop แถว)
```

ขั้น 5 (เพิ่ม 2026-09-30): return ที่ข้ามรูหลายเดือนคือผลรวมหลายเดือนใน "จุดเดียว" (เช่น +18.5%) ปนกับจุดปกติ
จะดึง regression/vol เพี้ยน → ทิ้งทั้งฝั่งกองและดัชนี ไม่เติมค่า · กองที่ NAV เก่า/เลิกกองถูกตัดก่อนหน้านี้แล้ว
ที่ขั้นโหลด NAV (ดู [data-sources](data-sources.md#ความสดของ-nav-และรูข้อมูล-เพิ่ม-2026-09-30--ตกลงกับผู้ใช้หลัง-dry-run))

จุดสำคัญ: ขั้นที่ 4 ใช้**อัตราส่วนของระดับดัชนี** ที่สอง NAVDate → เท่ากับทบต้น return ระหว่างนั้นให้อัตโนมัติ
ไม่ต้องเขียน loop compound เอง

**ผลลัพธ์ที่ยืนยันแล้วว่าวิธีนี้ดีขึ้นจริง:** K-INDIA R² 0.635 → **0.74** · ABJO 0.689 → **0.73**

---

## 2. Multi-factor regression (`analysis/matching.py::match_exposure`)

regress ผลตอบแทนกอง **กับดัชนีทั้งชุดพร้อมกันในโมเดลเดียว** (18 ตัวฝั่ง country / 10 ตัวฝั่ง sector)
ไม่ใช่ regress ทีละดัชนีแยกกัน — เพื่อดู "สัดส่วนผสม" ที่กองถือจริง

```python
Pipeline(StandardScaler(), ElasticNetCV(l1_ratio=[0.1, 0.5, 0.9, 1.0], cv=5))
```

| ประเด็น | รายละเอียด |
|---|---|
| **โมเดลหลัก** | `ElasticNetCV` — ตัด coefficient ที่ไม่ช่วยให้เป็น 0 ได้ (เลือกตัวแปร) |
| **โมเดลเทียบ** | `LassoCV`, `RidgeCV` — เก็บ coefficient ไว้ให้สลับดูในหน้า 3 (Ridge ไม่เคยตัดเป็น 0) |
| **Standardize** | `StandardScaler` อยู่**ใน Pipeline เดียวกับ CV** → scaler fit เฉพาะ train fold ไม่เกิด data leakage |
| **หน่วย coefficient** | อยู่บนสเกล standardized → **เทียบขนาดข้ามดัชนีได้ตรงๆ** (หน้า 7 ต้องแปลงกลับเป็นหน่วยจริงก่อนใช้ — ดู §7) |
| **R²** | in-sample (`pipe.score`) — ใช้เป็นตัวชี้ "ความมั่นใจของ match" ไม่ใช่ผลทำนาย |
| **Guard** | ถ้ามี observation ในช่วง MSCI < 30 (`MIN_REGRESSION_OBS`) → ข้ามกองนั้น + `try/except` ต่อกอง กัน build ล้มทั้งชุด |

### นิยาม primary / secondary

**ในหน้า 1, 2 และ `results.csv` (ระดับ pipeline):**
- `primary` = ดัชนีที่ \|standardized coefficient\| **มากที่สุด** (เฉพาะตัวที่ไม่เป็น 0)
- `secondary` = อันดับ 2
- ใช้ค่าจาก **ElasticNet เสมอ**

**ในหน้า 3 (`viz.match_strength_bar`) — นิยามต่างออกไป:**
- primary = อันดับ 1 เหมือนกัน
- **secondary = ทุกดัชนีที่ \|coef\| ≥ \|primary\| × (1 − `SECONDARY_BAND_PCT`)** → ปัจจุบัน = **≥ 70% ของ primary**
- จึงได้ secondary **0, 1 หรือหลายตัว** ตามข้อมูลจริง (ดู [หน้า 3](../pages/3-match-strength.md))

> ⚠️ ใช้ **ค่าสัมบูรณ์** เทียบ → ดัชนีที่ coefficient เป็นลบแต่ขนาดใหญ่ก็นับเป็น exposure ด้วย
> หลังตัดกอง F/O ออกจาก pipeline (2026-09-29) เหลือ **5/313 กอง** ที่มี primary เป็นค่าลบ (country 4 · sector 1)
> · หลัง clean NAV (2026-09-30) = **5/209 กอง**
> — ตอนที่ยังรวมทุก policy มี 16/368 ซึ่งส่วนใหญ่เป็นกองตราสารหนี้ที่ไม่ได้ track ดัชนีหุ้นจริง

---

## 3. Metrics ระดับกอง (`analysis/metrics.py` · `matching.fund_return_stats`)

NAV กองรายงานไม่ครบทุกวัน (เฉลี่ย ~74% ของวันทำการ MSCI, ช่วง 61–84%) จึง annualize ด้วย **วันปฏิทินจริง** (`DAYS_PER_YEAR = 365.25`)
ไม่ใช้ 252/n · คำนวณในช่วงเดียวกับ regression (ตัด NAV ให้อยู่ในช่วงที่ดัชนี MSCI มีข้อมูล)

| Metric | สูตร |
|---|---|
| Annualized return | CAGR = `(NAV สุดท้าย ÷ NAV แรก)^(365.25 / วันปฏิทิน) − 1` — รวมช่วงรูข้อมูล (ผลที่นักลงทุนได้จริง) |
| Annualized volatility | `std(r, ddof=1) × √(จุดต่อปีจริง)` — r = return ต่อจุด NAV ที่ไม่คร่อมรูเกิน 10 วันทำการ · winsorize 1–99% (กัน NAV ผิดพลาดที่ตัวกรอง spike จับไม่ได้ เช่น KKP SEMICON-H 16 มิ.ย. 2026 −56%/+152%: vol ดิบ 0.84 → 0.33) |
| จุดต่อปีจริง | `จำนวน r ÷ (ผลรวมวันปฏิทินที่ r ครอบคลุม ÷ 365.25)` |

ดัชนี MSCI (มีข้อมูลทุกวันทำการ) ยังใช้ `annualized_return` / `annualized_volatility` แบบ 252 ตามเดิม (คะแนนโซนหน้า 8, vol forecast หน้า 4)

**แก้เมื่อ 2026-10-02** — สูตรเดิม `(∏(1+r))^(252/n) − 1` และ `std × √252` ทบต้น/ขยาย vol เกินจริงสำหรับกองที่รายงานห่าง
และทิ้ง return ช่วงรูข้อมูล ตัวอย่างก่อน → หลัง: DAOL-GOLD 52.0% → 24.0% · M-EUBANK 44.0% → 29.7% · ES-USTECH +34.1% → −1.3% ·
vol median 20.2% → 19.3% · quadrant หน้า 1/2 เปลี่ยน 20 จาก 209 กอง

---

## 4. Vol Forecast (`analysis/vol_forecast.py`)

ทำนาย **annualized volatility ของดัชนี MSCI** ล่วงหน้า 21 วันทำการ (ไม่ใช่ระดับกองทุน)

### นิยามเป้าหมาย (ต้องตรงหน่วยกันทั้ง 3 ทาง)
> **annualized average-daily-vol ตลอด horizon**
> - forecast = `√(ค่าเฉลี่ยของ daily variance ที่ทำนาย h=1..21) × √252`
> - realized = `std(daily return ใน window 21 วัน, ddof=1) × √252`

| โมเดล | รายละเอียด |
|---|---|
| **EWMA** (baseline) | `σ²_t = λσ²_{t−1} + (1−λ)r²_{t−1}`, λ=0.94 (RiskMetrics) · ไม่มี mean-reversion → ทำนายแบนตลอด horizon |
| **GARCH(1,1)** (หลัก) | lib `arch`, `mean="Zero"` · fit บน `returns × 100` (กัน convergence warning) แล้ว**หารกลับ 100²** · เอา variance h=1..21 มา**เฉลี่ย** (ไม่ใช่บวกสะสม) |

**Fallback:** ถ้า GARCH fit ไม่ converge / ได้ variance ไม่ finite → ตกไปใช้ EWMA พร้อมติด flag
(ข้อมูลปัจจุบัน converge ครบ 28 ดัชนี ไม่มี fallback เลย)

### Walk-forward validation
- **expanding window** — ไม่ตัดข้อมูลเก่าทิ้ง
- `min_train = 252` (~1 ปี) · `step = 21` = horizon → **หน้าต่างไม่ทับกัน** (sample independent ขึ้น)
- ได้ **57 หน้าต่าง/ดัชนี** (รวม 1,596 แถว จาก 28 ดัชนี)
- ไม่มี leakage: `train = r[:t]`, `future = r[t:t+21]` แยกกันเด็ดขาด

### Metrics เปรียบเทียบโมเดล (ต่ำ = ดีกว่า)
| Metric | คำนวณบน | สูตร |
|---|---|---|
| RMSE / MAE | **vol** (อ่านง่าย) | error ปกติ |
| QLIKE | **variance** | `mean(realized² / forecast² + log(forecast²))` (Patton 2011 — ลงโทษการทำนายต่ำเกินแรงกว่า เหมาะกับงานความเสี่ยง) |

---

## 5. Caching

| ไฟล์ | ขนาด | สร้างโดย | เวลา |
|---|---|---|---|
| `cache/nav_clean.parquet` | 361,264 × 6 | `data_access.build_pipeline()` | NAV ที่ clean แล้ว + status ต่อกอง (ขั้นอื่นอ่านจากนี่) |
| `cache/results.csv` | 209 × 16 | `data_access.build_pipeline()` | ~75 วิ (เฉพาะ `APP_POLICY` · หลังตัดกอง NAV เก่า/เลิกกอง) |
| `cache/coefs.csv` | 5,852 × 8 | เดียวกัน | (209 กอง × 28 ดัชนี) |
| `cache/vol_forecast_backtest.csv` | 1,596 × 8 | `build_vol_forecast_cache()` | ~10 วิ |
| `cache/vol_forecast_latest.csv` | 28 × 7 | เดียวกัน | |
| `cache/style_results.csv` | 209 × 9 | `build_style_pipeline()` | ~15 วิ (ต้องมี snapshot + results.csv) |
| `cache/style_coefs.csv` | 1,463 × 4 | เดียวกัน | (209 กอง × 7 regressor · ElasticNet เท่านั้น) |
| `cache/macro_loadings.csv` | 2,926 × 7 | `build_macro_pipeline()` | ~15 วิ (ต้องมี snapshot + results/coefs.csv) |
| `cache/macro_index_betas.csv` | 196 × 8 | เดียวกัน | (28 ดัชนี × 7 macro) |
| `cache/country_matches_clean11.csv` | 209 × 6 | `build_score_matches()` | ~15 วิ (refit country 11 ตัว, หน้า 8) |

- UI อ่านผ่าน `@st.cache_data` — ถ้าไม่มีไฟล์จะ build อัตโนมัติ
- cache ทั้งหมด **regenerate ได้** จึง `.gitignore` ไว้
- **ไม่มี auto-invalidation**: ถ้าแก้ `base_data/` ต้องกดปุ่ม 🔄 Rebuild หรือรัน CLI เอง

---

## 6. Style factor regression (หน้า 6 — `data/style_factor.py` + `data_access.style_match_one`)

รายละเอียดเต็มและที่มาของทุกการตัดสินใจอยู่ใน [หน้า 6](../pages/6-style-match.md)

| ขั้น | วิธี |
|---|---|
| universe | กอง E ที่ผ่าน pipeline หลัก (209 กอง) |
| style factor | iShares MSCI factor ETF blend US/Intl 60/40 ใน **return space** → level → **÷ ACWI ETF** (USD÷USD ค่าเงินหักล้าง) · LowVol = ACWV÷ACWI |
| regressor | control ×3 (`MSCI_ACWI` · `US_VS_ACWI` · `ACWI_ETF`) + style ×4 · รวมปฏิทิน MSCI/NYSE ด้วย `combine_levels` (union + ffill + ตัดช่วงซ้อน) |
| return / regression | `build_fund_returns` + `match_exposure` ตัวเดิม (§1-2) |
| primary / secondary | `classify_exposure` บน coef **4 style เท่านั้น** (control ไม่นับ) · band `STYLE_SECONDARY_BAND_PCT` |
| ป้าย | ตาม**เครื่องหมาย** coef — `style_factor.style_label` (Value− = Growth, LowVol− = High-Beta …) |
| R² | **incremental** = R²(control+style) − R²(control) จาก OLS nested (`matching.nested_r2`) → ≥ 0 เสมอ |
| `mkt_beta` | ผลรวม OLS coef ของ `MSCI_ACWI` + `ACWI_ETF` **จากโมเดลที่มีแค่ control** (`STYLE_MARKET_COLS`) = beta ตลาดรวมของกอง |

---

## 7. Macro chain (หน้า 7 — `data/macro_factor.py` + `analysis/macro_chain.py` + `data_access.macro_match_one`)

รายละเอียดเต็มและผลตรวจอยู่ใน [หน้า 7](../pages/7-macro-chain.md)

| ขั้น | วิธี |
|---|---|
| universe | กอง E ที่ผ่าน pipeline หลัก (209 กอง — `MACRO_POLICY`) · F/O ถูกตัดเพราะ implied มองผ่าน index หุ้น จึงมองไม่เห็นบอนด์/ทอง |
| macro factor | level สิ้นเดือน (`month_end_levels` — ทิ้งเดือนที่ยังไม่จบ) → ราคาสินทรัพย์ % return · VIX/US10Y **Δ ระดับ** |
| Stage 1 | return รายเดือนของ 28 ดัชนี ~ 7 macro ด้วย OLS (`matching.nested_r2` base ว่าง) → B (ดัชนี × macro) |
| unstandardize | `β_raw = coef ÷ σ` — σ = SD (ddof=0) ของ index return ใน aligned ชุดที่ fit (= StandardScaler) · ไม่แปลง = เล็กเกิน ~64 เท่า |
| implied | `Σ β_raw × B` **แยก country / sector แล้วเฉลี่ย** (แต่ละชุดอธิบายกองทั้งก้อน · บวกกัน = นับตลาดซ้ำ) · join ตามชื่อดัชนี |
| direct | return รายเดือนของกอง ~ 7 macro ด้วย OLS · ต้อง ≥ `MACRO_MIN_MONTHS` เดือน |
| แสดงผล | `impact_1sd = loading × σ(macro)` — % return ต่อ macro ขยับ 1 SD (หน่วยดิบเทียบข้าม factor ไม่ได้) |
| R² | implied = corr² ของค่าที่ chain ทำนายกับ return จริง (ไม่ fit กับกอง) · direct = R² ของ OLS |

---

## 8. Score screening (หน้า 8 — `analysis/screening.py` + `data_access.build_score_matches`)

รายละเอียดเต็มและผลจริงอยู่ใน [หน้า 8](../pages/8-score-screen.md)

| ขั้น | วิธี |
|---|---|
| universe | กอง E · country เลือกได้ 18 เดิม หรือ 11 ตัวที่ VIF < 5 (`SCORE_COUNTRY_CLEAN`, hardcode + test คุม) · sector ครบ 10 เสมอ |
| โซนของ index | `percentile(return 252d ข้าม 21 วันล่าสุด ÷ realized vol 231 วันช่วงเดียวกัน)` (§12.14 · 2026-09-30 · `SCORE_ZONE_METHOD`) · rescale (0.01, 0.99) · re-rank ภายใน universe ที่เลือก · สูตรเดิม (× อันดับ GARCH กลับด้าน) เลือกได้ 1 รอบเพื่อ A/B |
| ตาราง | `country_sector_score(i,j) = zone(i) × zone(j) × 100` |
| คะแนนกอง | `(R² country × R² sector) × zone ของคู่ primary` · คู่ secondary ได้คะแนนแบบเดียวกัน **ถ้าผ่าน signed band** `[primary_coef × (1 − SCORE_SECONDARY_BAND_PCT), primary_coef]` ทั้ง country และ sector (ไม่ผ่าน = NaN ใช้เป็นคู่สำรองไม่ได้) |
| การเลือก | greedy ไล่ตาม score ของคู่ primary — คู่ primary ก่อน ถ้าชนหรือ score < `SCORE_MIN_ELIGIBLE` (0.7) ลองคู่สำรอง (ต้อง ≥ 0.7 เช่นกัน) · มาร์ค used ทั้ง country และ sector เสมอ |
| เพดาน | AND ≤ จำนวน sector (10) · OR ≤ country + sector − 1 · หน้าเว็บแสดงเฉพาะกองที่ผ่านเกณฑ์ ไม่เกิน `PORTFOLIO_TOP_N` = 5 |

---

## 9. Portfolio / Efficient frontier (หน้า 8 ส่วนที่ 3 — `analysis/portfolio.py` + `data_access.portfolio_risk_model`)

รายละเอียดเต็มอยู่ใน [หน้า 8](../pages/8-score-screen.md)

| ขั้น | วิธี |
|---|---|
| universe | กองที่ผ่านเกณฑ์จากส่วนที่ 2 ไม่เกิน 5 กอง (โหมดเริ่มต้นได้ 4) (ต้องมีอย่างน้อย `PORTFOLIO_MIN_FUNDS` = 3 กอง) |
| หน้าต่าง | rolling `PORTFOLIO_LOOKBACK_DAYS` = 756 แถวของดัชนี (≈ 2.9 ปีปฏิทิน) ทั้ง B, F และ vol — เฉพาะส่วนนี้ ไม่แตะ metric อื่นในระบบ · กองที่ NAV จบก่อนก็ fit เท่าที่มี (ข้อจำกัด — ดูหน้า 8 ข้อควรระวัง 9) |
| B | joint refit ครั้งเดียวกับ [country ตาม toggle + sector 10] ด้วย `match_exposure` แล้ว unstandardize (`macro_chain.unstandardize`) |
| F | `LedoitWolf` บน daily factor return × 252 — raw covariance ของดัชนี MSCI เกือบ singular |
| D | (1 − R²) × variance รวมของกอง (clip ที่ 0) — ⚠️ คนละฐานกับ BFBᵀ จึงทำให้ √diag(Σ) ≠ vol จริงได้หลาย pp |
| Σ | `B·F·Bᵀ + diag(D)` แล้วบังคับ symmetry |
| μ | Black-Litterman `Π = γ Σ_sys w_ref` · Σ_sys = B·F·Bᵀ (ไม่รวม D) · γ = `PORTFOLIO_GAMMA` = 2.5 คงที่ · w_ref = 1/N (`PORTFOLIO_REF_WEIGHT` = "equal" · "aum" = สัดส่วน AUM cap 50%) · ความเสี่ยงพอร์ตยังใช้ Σ เต็ม |
| frontier | enumerate น้ำหนักจำนวนเต็ม % ทุกชุดที่รวม 100% (min/max ปรับได้ · step ต้องหาร 100 ลงตัว) แล้วคัด Pareto — ไม่ใช้ solver · กราฟสุ่มแสดงกลุ่มเมฆไม่เกิน 50,000 จุด |
| จุดอ้างอิง | max Sharpe (`portfolio.max_sharpe_index`, rf = 0 — ระบบไม่มี risk-free rate) · equal weight · ถือกองเดียว 100% |
| cache | ไม่มี — fit สดต่อครั้ง (ผูกกับหน้าต่างล่าสุด) ใช้ `@st.cache_data` กันคำนวณซ้ำระหว่าง rerun |

---

## สรุปพารามิเตอร์สำคัญ (`config.py`)

| ค่า | ปัจจุบัน | ความหมาย |
|---|---|---|
| `APP_POLICY` | E | policy เดียวที่ทั้งแอปใช้ — กรองตั้งแต่ `build_pipeline` (style/macro/score อ้างค่านี้ต่อ) |
| `MIN_DATA_POINTS` | 600 | จำนวน NAVDate ขั้นต่ำที่กองต้องมี (ต้อง > ค่านี้) |
| `MIN_REGRESSION_OBS` | 30 | observation ขั้นต่ำในช่วง MSCI ไม่งั้นข้ามกอง |
| `NAV_STALE_MAX_DAYS` | 90 | NAV ล่าสุดช้ากว่าวันล่าสุดของดัชนีเกินนี้ (วันปฏิทิน) → ตัดกองออกทั้งแอป · กองเลิกแล้วตัดเสมอ |
| `NAV_MAX_GAP_BDAYS` | 10 | return ที่คร่อมรูเกินจำนวนวันทำการนี้ → ไม่ใช้ (ทั้งกองและดัชนี) |
| `WINSOR_LOWER` / `UPPER` | 0.01 / 0.99 | ขอบ clip ของ return |
| `TRADING_DAYS` | 252 | ตัวคูณ annualize |
| `SECONDARY_BAND_PCT` | 0.30 | band ของ secondary ในหน้า 3 (≥70% ของ primary) |
| `STYLE_US_WEIGHT` | 0.60 | สัดส่วน US ใน blend style factor (หน้า 6) |
| `STYLE_CONTROL_COLS` | MSCI_ACWI · US_VS_ACWI · ACWI_ETF | control ของหน้า 6 (ไม่นับเป็น style) |
| `STYLE_SECONDARY_BAND_PCT` | 0.30 | band secondary ของหน้า 6 (calibrate แยกจาก country/sector) |
| `MACRO_FACTOR_COLS` | Oil_Brent · Gold · USDTHB · Copper · DXY · VIX · US10Y | macro 7 ตัวของหน้า 7 (`MACRO_RETURN_COLS` → % return · `MACRO_DELTA_COLS` → Δ) |
| `MACRO_MIN_MONTHS` | 36 | จำนวนเดือนขั้นต่ำของ direct regression (7 factor + intercept) |
| `MACRO_POLICY` | E | หน้า 7 ใช้เฉพาะกองกลุ่มนี้ (กรองตั้งแต่ pipeline) · ◆ median บนกราฟคำนวณจากกลุ่มนี้ |
| `SCORE_RETURN_WINDOW` / `SCORE_RETURN_SKIP` | 252 / 21 | momentum 12-1 ของหน้า 8 — วัดจาก t−252 ถึง t−21 (ข้ามเดือนล่าสุด) |
| `SCORE_COUNTRY_CLEAN` | 11 ดัชนี | country ชุด VIF < 5 ของหน้า 8 (ตัดดัชนีรวมออก) |
| `SCORE_PCT_LO` / `HI` · `SCORE_MATRIX_SCALE` | 0.01 / 0.99 · 100 | ช่วง rescale ของ percentile · ตัวคูณของตารางโซน |
| `SCORE_SECONDARY_BAND_PCT` | 0.30 | signed band ของคู่สำรองหน้า 8 (ทิศเดียวกับ primary + แรง ≥ 70%) |
| `SCORE_TOP_N` | 20 | จำนวนกองสูงสุดที่ greedy ไล่เลือก (ส่วนที่ 2 แสดง `PORTFOLIO_TOP_N` ตัวแรกที่ผ่านเกณฑ์) |
| `SCORE_MIN_ELIGIBLE` | 0.7 | score ขั้นต่ำของคู่ที่ใช้จริงถึงจะนับว่าผ่านเกณฑ์ (หน้า 8 ส่วนที่ 2) |
| `PORTFOLIO_TOP_N` / `MIN_FUNDS` | 5 / 3 | กองที่ส่งเข้า frontier · น้อยกว่า 3 คำนวณไม่ได้ (40% × 2 = 80% < 100%) |
| `PORTFOLIO_LOOKBACK_DAYS` | 756 | หน้าต่าง rolling 3 ปีของ B/Σ/vol |
| `PORTFOLIO_GAMMA` | 2.5 | risk aversion คงที่ของ Black-Litterman |
| `PORTFOLIO_REF_WEIGHT` | equal | น้ำหนักอ้างอิงของ Π (equal = 1/N · aum = สัดส่วน AUM) |
| `PORTFOLIO_MARKET_CAP_W` | 0.50 | เพดานน้ำหนัก AUM ต่อกอง (ใช้เฉพาะโหมด aum) |
| `PORTFOLIO_MIN_W` / `MAX_W` / `STEP_W` | 0.05 / 0.40 / 0.01 | กริดน้ำหนักพอร์ต (ปรับได้ใน UI · step จาก `PORTFOLIO_STEP_CHOICES`) |
| `PORTFOLIO_CLOUD_MAX_POINTS` | 50,000 | จำนวนจุดกลุ่มเมฆสูงสุดที่วาด (คำนวณครบทุกชุดเสมอ) |
| `VOL_FORECAST_HORIZON` / `MIN_TRAIN` / `STEP` | 21 / 252 / 21 | walk-forward ของหน้า 4 |
| `EWMA_LAMBDA` | 0.94 | RiskMetrics |
