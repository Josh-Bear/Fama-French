# PAGE7_MACRO_CHAIN_PLAN.md — หน้า 7: Macro Factor Chain

> เอกสารนี้เขียนแยกจาก `PAGE6_STYLE_FACTOR_PLAN.md` (ตาม convention ของโปรเจกต์ที่แยกไฟล์ต่อหน้า) สืบเนื่องจาก §7 "Future Plan" ของไฟล์นั้น ซึ่งตอนนี้ผ่านขั้น**ตรวจสอบเชิงประจักษ์เบื้องต้นแล้ว** (Stage 1 validation รันจริงแล้วในช่วงคุยแผนนี้ ไม่ใช่แค่สมมติฐาน) — ยังไม่ implement โค้ดจริง เอกสารนี้คือแผนสำหรับ implement ต่อ

---

## 0. สรุปสั้น

หน้า 7 ตอบคำถาม "กองทุนแต่ละกองมีความอ่อนไหว (implied) ต่อปัจจัยมหภาคตัวไหนบ้าง" โดยไม่ต้อง regress NAV กองทุนกับ macro factor โดยตรง (ซึ่งจะมีปัญหาเรื่อง n_obs น้อยระดับกองทุนรายตัว) แต่ใช้วิธี **2-stage chain**:

1. **Stage 1** — regress 28 MSCI country+sector index (ที่มีอยู่แล้วในระบบ) กับ 7 macro factor → ได้ว่า "แต่ละ index ไวต่อ macro แค่ไหน"
2. **Stage 2 (chain)** — เอาผลจาก Stage 1 ไปคูณทะลุกับ coefficient ที่กองทุนแต่ละกองมีต่อ 28 index นั้นอยู่แล้ว (จาก pages 1-3, `cache/coefs.csv`) → ได้ "กองทุนแต่ละกองไวต่อ macro แค่ไหน" แบบ **implied/look-through** ไม่ใช่ empirical

ข้อจำกัดสำคัญที่ต้องสื่อสารกับผู้ใช้เสมอ: นี่คือค่า "โดยอนุมาน" ผ่านโครงสร้าง country/sector ที่โมเดลมีอยู่ ไม่ใช่พฤติกรรมจริงของกองทุน (พลาดจับ FX hedging, active selection ที่เบี่ยงจาก index ไป)

---

## 1. ทำไมต้องมีหน้านี้

- หน้า 1-6 บอกได้ว่ากองทุนเคลื่อนไหวตาม index/factor ไหน แต่ไม่บอกว่า "ทำไม" ในเชิงมหภาค (เช่น กองที่ overweight พลังงาน จะไวต่อราคาน้ำมันแค่ไหน, กองที่ต่างประเทศเยอะ จะไวต่อค่าเงินแค่ไหน)
- เป็น input ที่จำเป็นสำหรับหน้า 8 (Portfolio Optimize) ที่วางแผนจะใช้ risk model แบบ Barra-style (Σ = B·F·Bᵗ + D) ซึ่งต้องมี factor loading ครบทุก scope รวม macro ด้วย
- Stage 1 validation ที่รันจริงแล้ว (ดู §4.3) ยืนยันว่ามหภาคมีสัญญาณจริงต่อ 28 index (R² เฉลี่ย 0.395, ไม่ใช่ noise ล้วนๆ) — สมควรไปต่อ

---

## 2. Scope: ครอบคลุมทุกกองทุน (ต่างจากหน้า 6)

หน้า 6 (Style) จำกัดเฉพาะกอง policy `"E"` เพราะ style factor เกี่ยวกับหุ้นเท่านั้น แต่หน้า 7 **ไม่ต้องกรอง policy** เพราะ chain ผ่าน country+sector coefficient (`cache/coefs.csv`) ที่มีครบทุกกอง (368/368) อยู่แล้วไม่ว่า policy จะเป็น E/F/O — กองตราสารหนี้ก็ยังมี country/sector coefficient (แม้จะอ่อนกว่ากองหุ้น) จึงยัง chain ต่อได้ตามปกติ

---

## 3. Data source: 7 macro factor (ขยายจากแผนเดิม 5 ตัว)

แผนเดิมใน PAGE6 §7 ระบุไว้ 5 ตัว (Oil, VIX, Gold, Exchange, US10Y) แต่หลัง Stage 1 validation พบว่า EM/Asia index อธิบายได้แย่มาก (ไม่มีตัวไหนเป็น "non-US world factor" แท้ๆ) จึงเพิ่ม Copper + DXY เข้ามา รวมเป็น 7 ตัว:

| Factor | Ticker/Source | หน่วยดิบ | การแปลงก่อนเข้า regression |
|---|---|---|---|
| Oil_Brent | yfinance `BZ=F` | USD/barrel | % return |
| Gold | yfinance `GC=F` | USD/oz | % return |
| USDTHB | yfinance `THB=X` | บาท/ดอลลาร์ | % return |
| Copper | yfinance `HG=F` | USD/lb | % return |
| DXY | yfinance `DX-Y.NYB` (fallback `DX=F`) | ดัชนี | % return |
| VIX | yfinance `^VIX` | ดัชนี level | **ผลต่างระดับ (Δ)** ไม่ใช่ % return |
| US10Y | FRED `DGS10` (CSV ตรง ไม่ผ่าน pandas_datareader) | % yield | **ผลต่างระดับ (Δ)** ไม่ใช่ % return |

**เหตุผลที่ VIX/US10Y ใช้ Δ ไม่ใช่ % return**: ทั้งคู่ไม่ใช่ "ราคาสินทรัพย์" แต่เป็น index/yield ที่ mean-revert การใช้ % return ของตัวเลขที่ไม่ใช่ราคา (เช่น yield 4.78%→4.80%) จะตีความผิดเพี้ยน (จะกลายเป็น "return" +0.42% ทั้งที่จริงคือขยับ 2bp เท่านั้น) — มาตรฐานงานวิจัย factor model ใช้ first-difference กับตัวแปรประเภทนี้

**ความถี่**: รายเดือน (month-end, ใช้ราคา/ค่าวันสุดท้ายของเดือนที่มีข้อมูลจริง) — ต่างจากหน้า 6 ที่ใช้ daily เพราะ macro factor effect ชัดในกรอบเดือนมากกว่า ลด noise ของ noise วันเดียว

**ช่วงข้อมูล**: fetch เริ่ม 2020-11-01 (เผื่อก่อนช่วง MSCI base_data 2021-01-01 ให้มี return วันแรก) ยืนยันแล้วว่าครอบคลุมช่วง base_data ทั้งหมด (base_data: 2021-01-01 ถึง 2026-07-31)

**ข้อจำกัดการ fetch**: sandbox/Cowork VM block ทั้ง Yahoo Finance และ FRED (403/ConnectionError ยืนยันซ้ำหลายรอบ) — ต้อง fetch บนเครื่องผู้ใช้จริงเท่านั้น เหมือนที่ทำไปแล้วรอบนี้ (`fetch_macro_test.py`, ผลลัพธ์ `macro_factor_test.csv` มีครบ 7/7 คอลัมน์, 1,528 แถว, null 1-63 จุด/คอลัมน์ซึ่งเป็นวันหยุดตลาดปกติ ไม่ใช่บั๊ก)

---

## 4. Methodology

### 4.1 Stage 1 — regress 28 MSCI index กับ 7 macro factor

สำหรับแต่ละ index ใน 28 ตัว (18 country + 10 sector, ไม่มีคอลัมน์ซ้ำกัน):

```
index_return_i = β0 + β1·Oil_ret + β2·Gold_ret + β3·USDTHB_ret
                    + β4·Copper_ret + β5·DXY_ret + β6·VIX_delta + β7·US10Y_delta + ε
```

OLS ธรรมดา (ไม่มี penalty แบบ ElasticNet เหมือน country/sector matching เดิม เพราะจุดประสงค์ต่างกัน — ที่นี่ต้องการ coefficient ตรงไปตรงมาของทุกตัวแปรเพื่อ chain ต่อ ไม่ใช่การเลือก sparse feature) resample ทั้ง index level และ macro level เป็น month-end ก่อน แล้วค่อยแปลงเป็น return/delta คนละสูตรตาม §3

### 4.2 Stage 2 — Chain (matrix multiply) เพื่อได้ fund-level implied loading

```
fund_macro_loading[fund, factor] = Σ (over 28 index) coef_country_sector[fund, index] × B_stage1[index, factor]
```

โดย `coef_country_sector[fund, index]` คือ **ElasticNet coefficient ทั้งหมด 28 ตัว** (ไม่ใช่แค่ primary/secondary) จาก `cache/coefs.csv` (คอลัมน์ `elastic`, ทั้ง scope `country` และ `sector` รวมกัน) — ใช้ค่า ElasticNet เต็มชุดเพราะ ElasticNet เองมี L1 penalty ที่ sparsify ให้อยู่แล้ว การใช้ raw coefficient ทั้งหมดจะรักษาข้อมูล diversification ของกองไว้ได้ดีกว่าตัด primary/secondary ทิ้ง (แนวทางนี้สอดคล้องกับ Barra-style look-through risk model ที่วางแผนไว้สำหรับหน้า 8)

ผลลัพธ์คือ matrix ขนาด FundCode × 7 factor — เป็นค่า "sensitivity โดยอนุมาน" (implied) ของกองทุนต่อ macro factor แต่ละตัว

### 4.3 ผล Stage 1 validation จริง (รันแล้วในเซสชันนี้ — ไม่ใช่การคาดการณ์)

- n = 66 เดือน (2021-02 ถึง 2026-07) หลัง align ระหว่าง MSCI index กับ macro factor
- R² ทั้ง 28 index (7 factor): **เฉลี่ย 0.395, มัธยฐาน 0.41, ต่ำสุด 0.089 (China A-shares), สูงสุด 0.647 (MSCI World)**
- เทียบกับชุด 5-factor เดิม (ไม่มี Copper/DXY): เฉลี่ย 0.345 → เพิ่มขึ้นทุก index หลังเพิ่ม 2 ตัว โดยเฉพาะกลุ่ม EM/Asia (MSCI_EM +0.091, Asia ex-Japan +0.091, Taiwan +0.068, Brazil +0.065, Korea +0.054, Vietnam +0.053, กลุ่ม China +0.047 ถึง +0.049)
- Multicollinearity: ตรวจด้วย VIF แล้ว — ทุกตัวอยู่ที่ 1.17–2.91 (เกณฑ์อันตรายคือ >5/>10) **ไม่มีปัญหา** สูงสุดคือ DXY (2.91, เพราะ correlate กับ USDTHB 0.708 และ US10Y 0.597 ตามธรรมชาติ)
- Coefficient เฉลี่ยมีเครื่องหมายสมเหตุสมผลทางเศรษฐศาสตร์ทุกตัว: VIX ลบ, US10Y ลบ, USDTHB บวกแรงสุด (0.52), Copper บวก (0.16), Gold บวกอ่อน, Oil ~0, DXY ~0 เฉลี่ย (แต่แปรผันตาม index)

---

## 5. โครงสร้างโค้ดที่ต้องเพิ่ม (ยังไม่เขียน — สำหรับ implement จริง)

- **`data/macro_factor.py`** (ใหม่) — คล้าย `data/style_factor.py`: `_all_tickers()`, `download_snapshot()`/`load_snapshot()` (yfinance 6 ticker + FRED US10Y แยก endpoint), `build_macro_returns()` (resample month-end แล้วแปลงตาม `MACRO_RETURN_COLS`/`MACRO_DELTA_COLS`)
- **`config.py`** เพิ่ม: `MACRO_FACTOR_CSV`, `MACRO_SNAPSHOT_START = "2020-11-01"`, `MACRO_TICKERS` (mapping 6 yfinance ticker), `MACRO_FACTOR_COLS = ["Oil_Brent","Gold","USDTHB","Copper","DXY","VIX","US10Y"]`, `MACRO_RETURN_COLS`/`MACRO_DELTA_COLS` (แยกสูตรแปลงตาม §3), `MACRO_FREQ = "ME"`, `MACRO_SECONDARY_BAND_PCT` (ต้อง empirically sweep เหมือน `STYLE_SECONDARY_BAND_PCT` ตอน implement จริง ถ้าจะทำ primary/secondary label)
- **`analysis/macro_chain.py`** (ใหม่ แยกจาก `matching.py`) — Stage 1/Stage 2 เป็นคนละรูปแบบจาก fund-vs-index matching เดิม (regress index-vs-macro ไม่ใช่ fund-vs-index) จึงไม่ reuse `nested_r2`/`classify_exposure` โดยตรง แต่แยกฟังก์ชันใหม่: `regress_indices_on_macro(idx_returns, macro_returns) -> coef_df, r2_df` และ `chain_fund_loadings(coefs_country_sector, stage1_coef) -> fund_loading_df` (เป็น matrix multiply ล้วนๆ ด้วย numpy/pandas)
- **`data_access.py`** เพิ่ม: `build_macro_pipeline()` เขียน 2 cache ไฟล์แยกจาก `results.csv`/`coefs.csv` เดิม (ดู §6)
- **`pages/7_🌐_Macro_Chain.py`** (ใหม่) — bar chart ต่อกอง (เลือกกองจาก dropdown → แสดง 7-factor loading เป็นแท่ง บวก/ลบ) ไม่ใช่ scatter แบบหน้า 1-2/6 เพราะ "macro loading" ไม่ใช่ exposure classification แบบ primary/secondary ในความหมายเดียวกัน — ต้องมี caveat banner ชัดเจน (ดู §8)
- **`viz.py`** — ยังไม่มีฟังก์ชัน bar chart แบบนี้ ต้องเขียนใหม่ (ต่างจาก `match_strength_bar` ที่ออกแบบมาสำหรับ index-level ไม่ใช่ factor-level ต่อกอง) — ต้องอ่าน `viz.py` เต็มไฟล์อีกรอบตอน implement จริงเพื่อเช็คว่า reuse ได้บางส่วนไหม

---

## 6. Cache/output design

- **`cache/macro_index_coefs.csv`** (Stage 1 ผลลัพธ์) — long-form: `index, factor, coef, r2, n_obs` (28 index × 7 factor = 196 แถว, `r2`/`n_obs` ซ้ำกันภายในกลุ่ม index เดียวกัน — denormalized ตั้งใจเพื่อให้อ่านง่าย สอดคล้องกับ style ไฟล์อื่นในโปรเจกต์)
- **`cache/macro_coefs.csv`** (Stage 2 ผลลัพธ์) — **schema เดียวกับ `coefs.csv` เดิมทุกประการ**: `FundCode, scope="macro", index=<ชื่อ factor เช่น "Oil_Brent">, elastic=<loading>, is_primary, is_secondary` (368 กอง × 7 factor = 2,576 แถว) — ข้อดีของการทำ schema เดียวกัน: reuse `classify_exposure()` จาก `matching.py` ได้ทันทีเพื่อหา "macro factor หลัก" ของแต่ละกอง โดยไม่ต้องเขียน logic ใหม่ (ไม่มี `lasso`/`ridge` เพราะ Stage 2 เป็น matrix multiply ล้วนๆ ไม่ใช่การ fit โมเดลใหม่ — ใส่ค่า None/NaN ในสองคอลัมน์นี้)
- ไฟล์แยกจาก `coefs.csv`/`style_coefs.csv` เดิมโดยเจตนา (เหมือนที่หน้า 6 แยก `style_coefs.csv` ไว้แล้ว) — ป้องกันไม่ให้ macro factor ถูกนับปนกับ country/sector ตอนเรียก `get_index_matches()`/`get_funds_matching_index()` แบบ scope เดิมโดยไม่ตั้งใจ

---

## 7. Checklist ก่อน implement จริง

- [x] ทดสอบ fetch 7 ticker + FRED จริงบนเครื่องผู้ใช้ — สำเร็จ (7/7 คอลัมน์, 1,528 แถว)
- [x] Validate Stage 1 R² เบื้องต้น — ผ่าน (เฉลี่ย 0.395, ทุก index ดีขึ้นหลังเพิ่ม Copper/DXY)
- [x] เช็ค multicollinearity ระหว่าง 7 factor — ผ่าน (VIF ทุกตัว < 3)
- [ ] ตัดสินใจว่าจะเพิ่ม USDCNY อีกหรือไม่ (พิจารณาไว้แต่ยังไม่เลือกเพิ่มรอบนี้ — เปิดไว้เป็นตัวเลือกอนาคต)
- [ ] อ่าน `matching.py`/`data_access.py`/`viz.py` เต็มไฟล์อีกรอบตอน implement จริง (เคยอ่านตอน review หน้า 6 แต่ควร re-verify เพราะอาจมีการแก้เพิ่มระหว่างนี้)
- [ ] เช็คว่า FundCode set ตรงกันระหว่าง scope `country` และ `sector` ใน `coefs.csv` ก่อน concat เป็น 28-column matrix สำหรับ chain (ควรจะตรงกัน 368 กองทั้งคู่ แต่ต้อง assert ไว้ในโค้ดกันเหนียว)
- [ ] รัน `pytest -q` หลังแก้ ยืนยันไม่กระทบ country/sector/style pipeline เดิม
- [ ] เขียน unit test ใหม่: `tests/test_macro_factor.py` (สูตรแปลงค่า % return vs Δ ถูกต้อง, calendar/resample ถูกต้อง), `tests/test_macro_chain.py` (มิติ matrix multiply ถูก, ลำดับคอลัมน์ 28 index ตรงกันระหว่าง Stage 1/Stage 2, ทุกกองมี loading ครบไม่กรอง policy, cache แยกจากไฟล์เดิมจริง)
- [ ] ทดสอบ UI กับกองตัวอย่าง 2-3 กองเทียบกับสามัญสำนึก (เช่น กอง Oil & Gas ควรมี Oil_Brent loading เป็นบวกชัดเจน, กองพันธบัตรเก็งกำไร duration ควรไวต่อ US10Y)

---

## 8. ข้อจำกัดที่ต้องสื่อสารในหน้า UI (caveat banner)

1. **Implied ไม่ใช่ empirical** — เป็นการมองผ่าน (look-through) จาก country/sector holdings ที่โมเดลอนุมานไว้เท่านั้น ไม่ใช่การ regress NAV กองจริงกับ macro โดยตรง จึงพลาดจับพฤติกรรมจริง เช่น FX hedging ของกอง หรือ active security selection ที่เบี่ยงจาก index
2. **กองกลุ่ม EM/China จะมีความน่าเชื่อถือต่ำกว่า** เพราะ Stage 1 R² ของ index กลุ่มนั้นต่ำมาก (China A-shares R²=0.089) — ไม่ใช่ข้อผิดพลาดของโมเดล แต่เป็นข้อจำกัดของ macro factor ระดับโลกที่จับตลาดควบคุมเงินทุนเข้มงวดไม่ได้อยู่แล้วโดยธรรมชาติ
3. **USDTHB มีน้ำหนักสูงสุดใน Stage 1** (avg coef 0.52) — loading ส่วนใหญ่ที่เห็นในหน้านี้อาจสะท้อนความอ่อนไหวค่าเงินเป็นหลัก มากกว่าปัจจัยมหภาคอื่นๆ
4. **Europe-related loading ควรตีความคู่กับ DXY อย่างระวัง** เพราะ DXY มี EUR เป็นสัดส่วนหลักของตะกร้า (~58%) ความสัมพันธ์ที่เห็นอาจ "ใกล้ tautology" มากกว่าการค้นพบ sensitivity ใหม่จริงๆ
5. **n=66 เดือนใน Stage 1 ถือว่าตัวอย่างไม่ใหญ่มาก** (observation:parameter ratio ~8:1) ควรรีเฟรช/ตรวจ stability ของ coefficient เมื่อมีข้อมูลสะสมมากขึ้นในอนาคต

---

## 9. Decision log (สรุปการตัดสินใจของหน้า 7 ตามลำดับที่คุยกัน)

1. Macro factor เริ่มจากแผนเดิม 5 ตัว (Oil, VIX, Gold, USDTHB, US10Y) — หน่วยดิบทุกตัว ไม่แปลงเป็นบาท (เหตุผล: Oil/Gold คง USD, VIX ไม่มีหน่วยเงิน, US10Y เป็น % yield ไม่มีหน่วยเงิน, USDTHB คือตัวแปร FX เองอยู่แล้ว การให้เป็น regressor แยกช่วยให้โมเดลแยกผล FX ออกจากผล commodity/macro อื่นได้)
2. ความถี่: **monthly** (ไม่ใช้ daily เหมือนหน้า 6) — ลด noise, macro factor effect ชัดในกรอบเดือนมากกว่า
3. สูตรแปลง: ราคาสินทรัพย์ (Oil/Gold/USDTHB) ใช้ % return `(P_i-P_i-1)/P_i-1`, VIX/US10Y ใช้ผลต่างระดับ Δ (ไม่หารอะไรเลย) เพราะเป็น index/yield ไม่ใช่ราคาสินทรัพย์
4. Fetch เจอปัญหา `pandas_datareader` ชนกับ pandas รุ่นใหม่ตอนดึง US10Y — แก้ด้วยการดึง FRED CSV ตรง แทน pandas_datareader
5. Stage 1 validation รอบแรก (5 factor) พบว่า EM/Asia index อธิบายได้แย่มาก (R² 0.04-0.18) เพราะไม่มี factor ไหนเป็น "non-US world factor" แท้ๆ เลย (Gold/Oil กว้างเกินไป, VIX/US10Y/USDTHB ล้วนมีเงาสหรัฐฯ)
6. เพิ่ม Copper (HG=F, "Dr. Copper" — global industrial demand/China proxy) และ DXY (Dollar Index เทียบตะกร้า 6 สกุล) รวมเป็น 7 factor — ผู้ใช้เลือก 2 ตัวนี้จาก 3 candidate ที่เสนอ (Copper, USDCNY, DXY) โดยไม่เลือก USDCNY
7. Stage 1 validation รอบสอง (7 factor) — R² ดีขึ้นทุก index โดยเฉพาะ EM/Asia แต่ China A-shares ยังอ่อนสุด (0.089) — ยอมรับเป็นข้อจำกัดที่แก้ด้วย macro โลกไม่ได้จริงๆ ไม่ใช่บั๊ก
8. เช็ค multicollinearity ด้วย VIF — ผ่าน ไม่มีตัวไหนเกินเกณฑ์อันตราย ยืนยันชุด 7 factor นี้ใช้งานต่อได้โดยไม่ต้องตัดตัวไหนออก
9. Scope: **ครอบคลุมทุกกอง** ไม่จำกัดแค่ policy E เหมือนหน้า 6 — เพราะ chain ผ่าน country+sector coefficient ที่มีครบทุกกองอยู่แล้ว
10. Chain ใช้ ElasticNet coefficient เต็มชุด 28 ตัว (ไม่ตัดเหลือแค่ primary/secondary) เพื่อรักษาข้อมูล diversification ของกองไว้ให้มากที่สุด
11. Residual diagnostic (แนวทางเดิมที่เคยพิจารณาว่าอาจแม่นกว่าเพราะเป็น empirical ล้วน) — **ตัดสินใจไม่ทำในรอบนี้** เพราะต้องพึ่ง residual จาก country/sector regression ที่ R² เฉลี่ยเพียง ~0.51 (country) / ~0.38 (sector) เหลือ residual พอจะลองในอนาคตแต่ scope ใหญ่กว่ามาก ให้เป็น phase ถัดไปถ้า chain นี้ใช้งานได้ผลดีก่อน
