# M001 — Baseline: โมเดลหน้า 8 ปัจจุบัน แบบ point-in-time รายไตรมาส

- ผู้เขียน: quant-modeler · 2026-09-30 · สถานะ: **pre-registered** (ยังไม่มีผล backtest)
- จุดประสงค์: **ไม่ได้พยายามให้ถึง 0.95** แต่วัดว่าระบบหน้า 8 วันนี้ ถ้าใช้จริงทุกไตรมาสโดยไม่มี look-ahead จะได้ Sharpe
  out-of-sample เท่าไหร่ → ใช้เป็นจุดเทียบของ M002–M005
- ตัวเลขข้อเท็จจริงในไฟล์นี้มาจาก `scratch/quant_m001_feasibility.py` และสคริปต์ inline ที่รันเอง 2026-09-30 (read-only · ไม่ได้คำนวณ Sharpe)

---

## 1. สมมติฐาน + เหตุผล

1. **สัญญาณ**: time-series/cross-sectional momentum 12-1 ระดับดัชนี ปรับด้วย vol (Jegadeesh–Titman 1993; Moskowitz–Ooi–Pedersen 2012;
   Barroso–Santa-Clara 2015 เรื่อง risk-scaled momentum) → โซน country×sector ที่ return ต่อหน่วยความเสี่ยงสูงควรไปต่อใน 1 ไตรมาส
2. **การคัดกอง**: กองที่ R² ต่อโซนสูง = "ตัวแทน" ของโซนนั้นได้ดี → คะแนน = R²c·R²s·คะแนนโซน · greedy ไม่ซ้ำ country/sector = กระจายความเสี่ยง
3. **น้ำหนัก**: Π = γ·Σ_sys·(1/N) (Black–Litterman reverse optimization) → max Sharpe บนกริด 5–40% · รู้อยู่แล้ว (BRIEF จุดอ่อน #6)
   ว่า Π ไม่มีข้อมูลจากคะแนน จึงคาดว่า max Sharpe ≈ equal weight → **รันตัวแปร EW คู่กันเพื่อพิสูจน์**
4. ข้อควรจำ: พารามิเตอร์หลายตัว (skip 21, สูตร §12.14, `SCORE_MIN_ELIGIBLE` 0.7, ชุด VIF-cleaned 11) ถูกเลือกจาก dry run บนข้อมูล
   ช่วงเดียวกัน → ผล M001 **มี selection bias เชิงบวก** แม้จะเป็น point-in-time ทางกลไกแล้ว (ดู §9)

## 2. โมเดลที่รัน (pre-registered · นับ 2 trials)

| ID | กองที่ถือ | น้ำหนัก |
|---|---|---|
| **M001-MS** | กองที่คัดได้ (≤ 5) | จุด max (w·Π)/√(wᵀΣw) บนกริด 5–40% ทีละ 1% (ตรงกับดาวบนหน้า 8) |
| **M001-EW** | กองชุดเดียวกัน | 1/n_ok |
| **B0** (baseline) | ทุกกองใน universe point-in-time ณ t (§4.1) | 1/N_universe |

ห้ามลองค่าพารามิเตอร์อื่นในเวอร์ชันนี้ · การรายงานช่วงย่อย/ต้นทุนหลายระดับจาก **run เดียวกัน** ไม่นับเป็น trial ใหม่
แต่ต้องรายงานทุกตัว (ห้ามเลือกโชว์เฉพาะตัวดี)

## 3. ปฏิทิน · ช่วงเวลา · execution

- ปฏิทินอ้างอิง = วันที่ของไฟล์ดัชนี MSCI (`msci_index.load_country_index()` ∪ sector — 1,456 แถว 2021-01-01 → 2026-07-31 · ไม่มี NaN)
- **วันตัดสินใจ t** = วันสุดท้ายของไตรมาสที่มีในปฏิทินดัชนี (มี.ค./มิ.ย./ก.ย./ธ.ค.) · ข้อมูลที่ใช้ = **NAVDate ≤ t และ Date ดัชนี ≤ t เท่านั้น**
- **warm-up**: momentum ต้องการดัชนี ≥ 253 จุด → จุดที่ 253 = 2021-12-22 · ดัชนีครบ 756 วันที่ 2023-11-27
  - rebalance แรก **t₁ = 2022-03-31** (ดัชนี ~325 วัน) — risk model ใช้ `min(756, ที่มี)` วันล่าสุด (= พฤติกรรม `iloc[-756:]` ของหน้า 8
    ตอนข้อมูลยังไม่ครบ) · เหตุผล: ถ้ารอ 756 วันเต็ม จะเริ่ม 2024-Q1 ได้แค่ ~8 ไตรมาสและตัดปี 2022 ทิ้ง → Sharpe สวยเกินจริง
- **execution lag**: สั่ง ณ วันทำการที่ 2 ของปฏิทินดัชนีหลัง t (= e) · ราคาซื้อ/ขาย = NAV ของ NAVDate แรกที่ ≥ e ของแต่ละกอง
  (สะท้อน NAV กอง FIF ประกาศ T+1–T+2 และ cut-off คำสั่ง)
- **ช่วงประเมินหลัก (primary)**: ผลตอบแทนตั้งแต่ e(2022-03-31) ถึง **2025-12-31** (rebalance 2022-03-31 … 2025-09-30 = **15 ไตรมาส**, ~45 เดือน)
- **ช่วงขยาย (รายงานคู่ จาก run เดียวกัน)**: ต่อถึง 2026-07-31 (rebalance 2025-12-31, 2026-03-31, 2026-06-30 เพิ่ม) — ติดป้าย "ข้อมูลมีรู"
  เพราะ (ตรวจเอง) กองที่รายงาน NAV ต่อเดือน: ธ.ค. 2025 = 492, ม.ค. 2026 = 496, **ก.พ. 2026 = 107**, มี.ค. 163, … มิ.ย. 317
  และ 137 กองมี NAV สุดท้ายเดือน ม.ค. 2026 (น่าจะเป็นขอบเขตไฟล์ ไม่ใช่กองปิดจริง — ต้องให้ผู้ใช้ยืนยัน §10)
- **ช่วงย่อยที่ต้องรายงาน**: (a) 2022-04 → 2023-06 · (b) 2023-07 → 2025-12 · ปีปฏิทิน 2022/2023/2024/2025

## 4. ขั้นตอน ณ วัน t (ทำซ้ำทุกไตรมาส)

### 4.1 Universe point-in-time
แหล่ง: `cache/nav_clean.parquet` ทุก 570 กอง (**ไม่กรองด้วยคอลัมน์ `status`** — status คำนวณจากวันนี้ = look-ahead) · กอง E ทั้งหมดอยู่แล้ว
กองอยู่ใน U_t เมื่อครบทุกข้อ:
1. **NAV สด**: `t − max(NAVDate ≤ t) ≤ 90` วันปฏิทิน (`config.NAV_STALE_MAX_DAYS`)
2. **ประวัติพอ**: จำนวน NAVDate ไม่ซ้ำใน [2021-01-01, t] **≥ 252**
   - ⚠️ ไม่ใช้กฎเดิม `> 600 จุด` ตรงๆ: ตรวจแล้ว NAV ส่วนใหญ่เริ่มปี 2020 (กองแรกเริ่ม: 2020 = 153 กอง, 2021 = 99) → ถ้าใช้ >600 แบบ
     point-in-time จะมี **0 กองจนถึง 2023-03-31** (2023-06 = 75, 2023-09 = 166) = เริ่ม backtest ได้กลาง 2023 เท่านั้น
   - 252 = ขั้นต่ำเท่า momentum 1 ปี / ElasticNet รายวัน 1 ปี · ผลนับ (ตรวจเอง): 2022-03 = 190 กอง, 2022-12 = 248, 2023-12 = 308, 2025-09 = 356
   - ทางเลือก "600 ตามเดิม" อยู่ใน §10 (ถ้าผู้ใช้เลือก = เวอร์ชันใหม่ ไม่ใช่ปรับ M001)
3. ElasticNet ของทั้ง 2 scope (§4.2) รันผ่าน guard (aligned obs ≥ `MIN_REGRESSION_OBS` 30 · ไม่ error) — กองที่ไม่ผ่านไม่เข้าการคัด แต่ **ยังอยู่ใน B0**

### 4.2 Exposure ต่อกอง (แทน `results.csv` + `country_matches_clean11.csv`)
- หน้าต่าง fit: **expanding [2021-01-01, t]** — ตรงกับของจริง (pipeline ใช้ข้อมูลทุกจุดในช่วงดัชนี) แค่ตัดที่ t
- ส่ง `index_levels` ที่ **slice ≤ t แล้ว** เข้า `matching.build_fund_returns(nav_≤t, levels_≤t)` (ฟังก์ชันตัดกองตามช่วง index เอง
  → ถ้าไม่ slice ดัชนี จะรั่ว) · winsorize 1–99% คำนวณภายในหน้าต่าง ≤ t เท่านั้น (พฤติกรรมเดิมของฟังก์ชัน)
- country: `match_exposure(aligned[SCORE_COUNTRY_CLEAN 11 ตัว], alternatives=False)` → `country_primary, country_secondary, country_r2,
  country_primary_coef, country_secondary_coef` (coef มีเครื่องหมาย standardized)
- sector: fit แยกกับ `MSCI_SECTOR_COLS` 10 ตัว → `sector_*` ชุดเดียวกัน (ของจริง sector มาจาก `results.csv` ซึ่ง fit sector แยก scope อยู่แล้ว
  และ secondary coef มาจาก `coefs.csv` แถว `is_secondary`)
- ElasticNetCV ตามโค้ดเดิมทุกค่า: `l1_ratio=[0.1,0.5,0.9,1.0], cv=5, random_state=0, max_iter=5000` ผ่าน `matching._fit` (StandardScaler ใน pipeline)
- ใช้ฟังก์ชันเดิม `analysis.matching.*` ตรงๆ (read-only import) — **ห้ามเรียก** `data_access.build_*` / `portfolio_risk_model` (กฎเหล็ก)

### 4.3 คะแนนโซน (แทน `_load_index_snapshot`)
ต่อดัชนี ix ใช้ level ≤ t (index ครบทุกวันทำการ → นับเป็นตำแหน่ง):
- `ret = metrics.recent_return(level_ix, window=252, max_gap_days=None, skip=21)` = L[t−21]/L[t−252] − 1
- `vol = screening.realized_vol_window(level_ix)` (return รายวันช่วง t−252..t−21, ×√252)
- ใส่ลง DataFrame snapshot (`scope, index, SCORE_RETURN_COL, SCORE_VOL_COL`) แล้วเรียก `screening.zone_scores(snap, "country", SCORE_COUNTRY_CLEAN)`
  (percentile **re-rank ภายใน 11 ตัว**) · `zone_scores(snap, "sector")` · `score_matrix(country, sector)`
- `SCORE_ZONE_METHOD = "ret_over_realized_vol"` (ไม่ใช้ GARCH → ไม่ต้องใช้ cache หน้า 4)

### 4.4 คัดกอง
```
scored   = screening.fund_scores(matches_t, matrix_t)
selected = screening.greedy_select(scored, n=SCORE_TOP_N(20), use_secondary=True, strict_and=True,
                                   min_score=SCORE_MIN_ELIGIBLE(0.7), groups=share_class_groups)
picked   = selected[selected.eligible].head(PORTFOLIO_TOP_N=5)     # ไม่ใช้แถว fill
```
- `groups` = `base_data/share_class_groups.csv` (70 แถว / 32 กลุ่ม) อ่านด้วยวิธีเดียวกับ `data_access.share_class_groups()`

### 4.5 Risk model (แทน `portfolio_risk_model` — เขียนซ้ำเป็นฟังก์ชันใน backtest/ ด้วยสูตรเดียวกัน)
- `levels = concat(country 11, sector 10)[Date ≤ t].iloc[-756:]` · `F = portfolio.factor_covariance(levels.pct_change())` (Ledoit-Wolf ×252)
- ต่อกองใน picked: `aligned = build_fund_returns(nav_≤t, levels)` (21 factor ร่วมกัน · joint ElasticNet) · guard ≥ 30 obs
  `B_f = macro_chain.unstandardize(coef, aligned)` · `total_var = annualized_volatility(fund_ret)²` · `D_f = max(total_var·(1−R²), 0)`
- `Σ = portfolio.fund_covariance(B, F, D)` · `Σ_sys = systematic_covariance(Σ, D)` · `Π = implied_returns(Σ_sys, 1/N, γ=2.5)`
- กองใน picked ที่ fit risk model ไม่ผ่าน → ตัดออกจาก picked (ไม่ดึงกองถัดไปมาแทน — หน้า 8 จริงจะ error แล้วหยุด)

### 4.6 น้ำหนัก
- n_ok = จำนวนกองที่เหลือ
- **n_ok ≥ 3**: MS = `weight_grid(n_ok, 0.05, 0.40, 0.01)` → `portfolio_points(grid, Π, Σ)` → `max_sharpe_index(points, risk_free=0)`
  → ทำ `pareto_mask` ก่อนแล้วหา argmax บน frontier เหมือนหน้า 8 (บรรทัด ~163–177) · Π ติดลบได้ ถ้าจุดดีสุดยังติดลบก็ถือจุดนั้นตามกติกา · EW = 1/n_ok
- **n_ok ∈ {1, 2}**: หน้า 8 ไม่คำนวณ frontier → ทั้ง MS และ EW ถือ 1/n_ok (บันทึก `fallback=small_n`)
- **n_ok = 0**: ถือ B0 ของไตรมาสนั้น (บันทึก `fallback=b0`)
- รายงานจำนวนไตรมาสที่ fallback ต่อโมเดล

### 4.7 การถือระหว่างไตรมาส
- buy-and-hold ตั้งแต่ e ถึง e ถัดไป (น้ำหนักลอยตาม NAV — ไม่ rebalance กลางไตรมาส)
- มูลค่ากองรายวัน (บนปฏิทินดัชนี) = units × NAV ล่าสุดที่ NAVDate ≤ วันนั้น (ffill)
- **กองหยุดรายงานระหว่างไตรมาส**: ถือต่อด้วย NAV ล่าสุด (return 0) · ถ้ากลับมารายงาน return ข้ามรูถูกนับตอนนั้น (เป็นเงินจริง)
  · ถ้าไม่กลับมาจนถึง e ถัดไป → ขายที่ NAV สุดท้าย (มูลค่าคงที่) และบันทึก `frozen_fund` · ไม่เกลี่ยน้ำหนักให้กองอื่นกลางไตรมาส
- ห้ามใช้ `status == "closed"` จากไฟล์เพื่อตัดสินล่วงหน้า (look-ahead)

## 5. การวัดผล

- ผลตอบแทนพอร์ต **รายเดือน** จากมูลค่าสิ้นเดือน (ลด bias ของ NAV ไม่พร้อมกันข้ามเขตเวลา/วันหยุด — BRIEF จุดอ่อน #4, #5)
- **Sharpe (primary)** = (mean(r_m − rf_m)·12) ÷ (sd(r_m)·√12) · รายงานคู่ CAGR, vol, max drawdown, Sortino, hit rate รายไตรมาสเทียบ B0,
  IR และ tracking error เทียบ B0, turnover เฉลี่ย/ไตรมาส, จำนวนกองเฉลี่ย, ค่าต้นทุนรวม (bp/ปี)
  — ถ้า backtest-validator มีนิยามกลางอยู่แล้ว ให้ใช้นิยามกลางและเขียนความต่างไว้
- **rf**: ระบบยังไม่มี rf ไทย → รายงาน **"Sharpe (rf = 0 — ยังไม่ใช่นิยามเป้า)"** และหยุดรอข้อมูลจากผู้ใช้ (§10) ก่อนสรุปเทียบ 0.95
  · ช่วงนี้ rf ไทย ~0.5–2.5%/ปี (ต้องยืนยันด้วยข้อมูลจริง) → Sharpe จริงจะต่ำกว่าค่า rf = 0 ราว 0.1–0.2 สำหรับ vol ~15%
- **ต้นทุนสลับกอง**: turnover วัดเทียบน้ำหนักที่ลอยแล้วก่อน rebalance
  `cost_t = Σ_i c_sell,i·max(w_drift,i − w_new,i, 0) + Σ_i c_buy,i·max(w_new,i − w_drift,i, 0)` หักออกจากมูลค่า ณ e
  1. พยายาม map `base_data/SecFundFee.csv` (คอลัมน์ `As of Date, Fund Code, Complex Type Code, Code, Rate, Unit Rate, Actual Value` · รหัสกองเป็นเลข
     · ความหมาย Code ดู `FUNDPROFILE_SECFUNDFEE_SCHEMA.pdf`) → c_buy = front-end fee, c_sell = back-end fee (ใช้ `Actual Value` ถ้ามี · ค่าที่ As of Date ≤ t)
  2. map ไม่ได้ → ค่าคงที่ **c_buy = c_sell = 0.50%** ติดป้าย "สมมติฐาน" · รายงานคู่ 0% (gross) และ 1.00%/ข้าง (sensitivity — ไม่นับเป็น trial)
  - ต้นทุนใช้กับ B0 ด้วยกติกาเดียวกัน (B0 มี turnover จากกองเข้า/ออก universe)
- sample size: 45 เดือน → SE ของ Sharpe ≈ √((1 + SR²/2)/3.75 ปี) ≈ **0.53–0.61** (SR 0.3–0.9) → ต้องรายงาน CI 95% (bootstrap แบบ block รายเดือน
  หรือสูตร Lo 2002) และ deflated Sharpe ด้วย n_trials จาก `trials.csv` · M001 แยก "0.5 กับ 0.95" ทางสถิติไม่ได้ — เป็นข้อจำกัดของข้อมูล ไม่ใช่ของโมเดล

## 6. ต้นทุนการคำนวณ (ตรวจแล้ว — ไม่ต้องลดรูป)

- ElasticNetCV 2 scope ของ 1 กอง (1,081 obs) ใช้ **0.16 วินาที** (วัดเอง)
- งานทั้งหมด ≈ Σ_t |U_t| ≈ 190…396 กอง × 18 ไตรมาส ≈ 5,000 กอง-ไตรมาส × 0.16 วิ ≈ **~15 นาที core เดียว** + risk model ≤ 5 กอง/ไตรมาส
  + กริด 5 กอง (~885,801 จุด/ไตรมาส) ≈ วินาที
- → **รันเต็มตามสูตรเดิม ไม่ลดรูป** · แนะนำ cache ผล fit ต่อ (FundCode, t) เป็น parquet ใน `backtest/` เพื่อให้ M002+ ใช้ซ้ำ (ประหยัดโควตา)
  · ใช้ `joblib` ขนานได้ (ผลเหมือนเดิมเพราะ `random_state=0`)
- ถ้าวันหน้าต้องลดรูป (ไม่แนะนำสำหรับ M001): refit exposure ปีละครั้ง → primary/secondary ช้ากว่าความจริงสูงสุด 3 ไตรมาส ทำให้ R² และคู่โซนค้าง ผลน่าจะแย่ลงเล็กน้อย

## 7. สิ่งที่ยังเป็น look-ahead ใน M001 (ยอมรับได้สำหรับ baseline แต่ต้องเขียนในรายงาน)

1. ชุด `SCORE_COUNTRY_CLEAN` เลือกด้วย VIF บนข้อมูลทั้งช่วง 2021–2026 (คงไว้ตามระบบจริง)
2. พารามิเตอร์ skip 21 / สูตร §12.14 / min 0.7 ถูกเลือกจาก dry run ช่วงเดียวกัน (selection bias — BRIEF)
3. `nav_clean` แก้ spike ด้วยข้อมูลทั้งช่วง · policy E และ `share_class_groups.csv` เป็นสถานะวันนี้
4. ไม่มีกองที่ถูกลบออกจากฐานข้อมูลก่อนสร้างไฟล์ (survivorship ตกค้างในระดับแหล่งข้อมูล — ตรวจไม่ได้จากฝั่งเรา)

## 8. ความเสี่ยงที่คาด
- **concentration**: 3–5 กอง · อาจกระจุก US/tech (momentum ปี 2023–2024) · รายงานส่วนแบ่ง country/sector ที่ถือทุกไตรมาส
- **turnover สูง**: อันดับโซนเปลี่ยนทุกไตรมาส + greedy ไวต่ออันดับ → ต้นทุนกินผลตอบแทน
- **2022**: momentum ช่วงกลับทิศ (momentum crash) → drawdown อาจแย่กว่า B0
- MS ≈ EW (คาดไว้) · ถ้า MS ดีกว่า EW มากผิดปกติให้สงสัย bug ก่อน

## 9. สิ่งที่ reviewer ควรตรวจเป็นพิเศษ
1. ทุกขั้นใช้ข้อมูล ≤ t (โดยเฉพาะดัชนีที่ส่งเข้า `build_fund_returns` และ winsorize)
2. universe ไม่ได้กรองด้วย `status` ปัจจุบัน · กองที่วันนี้ stale/closed ถูกนับในอดีต
3. percentile country re-rank ภายใน 11 ตัว · secondary band เช็คแบบมีเครื่องหมาย · ≤ 1 share class ต่อกลุ่ม
4. execution lag 2 วันและราคาที่ NAVDate ≥ e · การจัดการกองที่หยุดรายงาน
5. เทียบ picked ของไตรมาสล่าสุดที่มี (2026-06-30) กับหน้า 8 วันนี้ — ต่างกันได้ (exposure fit คนละหน้าต่าง) แต่ควรใกล้เคียง
6. ตัวเลข fallback (small_n / b0) และต้นทุนที่ใช้จริง

## 10. ต้องให้ผู้ใช้ตัดสินใจ
1. **rf ไทย**: ขอไฟล์รายวัน/รายเดือน 2022-01 → 2026-07 (แนะนำ BOT policy rate หรือ ThaiBMA/ธปท. ตั๋ว 3 เดือน) — ก่อนได้ ใช้ rf = 0 ติดป้าย
2. **ต้นทุนสลับกอง**: ถ้า map SecFundFee ไม่ได้ ยอมรับค่าคงที่ 0.50%/ข้างไหม (หรือกำหนดเอง เช่น สลับภายใน บลจ. เดียวไม่มีค่าธรรมเนียม)
3. **กฎประวัติขั้นต่ำ**: ใช้ ≥ 252 NAV ตั้งแต่ 2021 (ค่าเริ่มต้น M001 · เริ่ม 2022-Q1 · รวมปี 2022) หรือ > 600 จุดตามแอป (เริ่มได้ 2023-Q3 · ตัดปี 2022 ทิ้ง · ~10 ไตรมาส)
4. **รู NAV ปี 2026**: 137 กองหยุดที่ ม.ค. 2026 และ ก.พ. 2026 มีกองรายงานแค่ 107 — เป็นขอบเขตไฟล์หรือกองหยุดจริง? ถ้าเป็นขอบเขตไฟล์ ขอข้อมูลเติม
   · ระหว่างนี้ใช้ primary ถึง 2025-12 และรายงานช่วงขยายแยกป้าย
5. **B0** นับทุก share class (ค่าเริ่มต้น) หรือ 1 class ต่อกลุ่ม
6. ยอมรับว่า sample 15 ไตรมาสแยก Sharpe 0.5 กับ 0.95 ทางสถิติไม่ได้ — หากต้องการหลักฐานแน่นกว่านี้ต้องมีข้อมูลดัชนี/NAV ก่อน 2021

## 11. ผู้ใช้ตัดสินใจแล้ว (2026-09-30 · บันทึกโดย session หลัก — ใช้แทนค่าเริ่มต้นในหัวข้อก่อนหน้าถ้าขัดกัน)
1. **rf = 2% ต่อปี คงที่** (สมมติฐาน — ยังไม่มีข้อมูล rf ไทยจริง) · รายงาน Sharpe ที่ rf = 2% เป็นตัวหลัก + คู่ที่ rf = 0 · ติดป้าย "rf คงที่ 2% (สมมติฐาน)"
2. **ต้นทุนสลับกอง**: ถ้า map `SecFundFee` ไม่ได้ ใช้ **0.5% ต่อข้าง คงที่** เป็นตัวหลัก + รายงานคู่ที่ 0% และ 1% · ไม่แยกกรณีสลับภายใน บลจ. เดียวกัน
3. **ประวัติขั้นต่ำ ≥ 252 จุด NAV** (ตามค่าเริ่มต้นของ spec) → ช่วงประเมินหลัก 2022-03-31 → 2025-09-30 (15 ไตรมาส รวมปี 2022)
4. **B0 = 1 share class ต่อกลุ่ม** (`base_data/share_class_groups.csv` · class ที่เลือก = ตัวที่มี NAV สด ณ t และ AUM ล่าสุดมากที่สุด)
5. รู NAV ปี 2026 ยังไม่ทราบสาเหตุ → รายงานช่วงถึง 2026-07 แยกต่างหากพร้อมป้ายเตือนตาม spec · ยอมรับว่า 15 ไตรมาสยืนยันเป้า 0.95 ทางสถิติไม่ได้ (รายงาน CI + deflated Sharpe)
