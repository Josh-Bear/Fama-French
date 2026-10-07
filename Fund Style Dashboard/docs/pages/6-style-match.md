# 🎯 หน้า 6 — Style Match

**ไฟล์:** `pages/6_🎯_Style_Match.py` → `page_common.scatter_page("style", results=merged)` · ข้อมูล `data_access.get_style_results()` · factor `data/style_factor.py`

## หน้านี้ทำอะไร
หน้า 1-2 บอกว่ากอง **"ลงทุนที่ไหน"** ส่วนหน้านี้บอกว่ากอง **"ลงทุนหุ้นแบบไหน"** — เอียงไปทาง style ใดใน 4 แบบ
(Momentum / Quality / Value / Low-Vol — หลักเดียวกับ factor model ของ Fama-French / Carhart)

- ใช้เฉพาะกอง **E** (209 กอง หลัง clean NAV 2026-09-30) เพราะกอง F/O ไม่มีความหมายกับ style ของหุ้น
- ใช้ scatter เดียวกับหน้า 1/2 (x = ann return, y = ann vol, 4 quadrant และ filter ชุดเดิม) แต่ primary = **ป้าย style**
  - ซ่อนตัวกรอง Fund Policy (`scatter_page(policy_filter=False)`) เพราะมีแต่กอง E
- ตารางใน expander มีคอลัมน์เพิ่มคือ `mkt_beta` และ `style_r2_full`
- filter R² ของหน้านี้เป็น **incremental R²** สเกล 0–0.20 (step 0.01) เพราะค่าส่วนใหญ่ต่ำกว่า 0.1

## ป้าย style (ดูเครื่องหมายด้วย)
| factor | coef บวก | coef ลบ |
|---|---|---|
| Momentum | **Momentum** | **Contrarian** |
| Quality | **Quality** | **Junk** |
| Value | **Value** | **Growth** |
| LowVol | **Low-Vol** | **High-Beta** |

หน้า 1-3 ดูแค่ `|coef|` เพราะสำหรับประเทศ/sector coef ติดลบไม่มีความหมายพิเศษ
แต่ coef ของ style ที่ติดลบหมายถึง**ขั้วตรงข้าม** ถ้าดูแค่ขนาด กอง tech จะถูกเรียกว่า "Value"
**การจัดอันดับ** primary/secondary จึงยังใช้ `|coef|` และ band 30% ผ่าน `matching.classify_exposure` ตัวเดียวกับหน้า 3
ส่วน**ชื่อป้าย**ดูจากเครื่องหมาย (`style_factor.style_label`)

---

## โมเดล

```
fund_return ~ [MSCI_ACWI, US_VS_ACWI, ACWI_ETF]  +  [Momentum, Quality, Value, LowVol]
              └──── control (ไม่นับเป็น style) ─┘     └── style factor (de-market แล้ว) ──┘
```

ใช้ pipeline เดิมทั้งหมด คือ `build_fund_returns` (align ด้วย NAVDate, ทบต้นช่วง gap, winsorize) แล้วต่อด้วย `match_exposure` (StandardScaler + ElasticNetCV)
logic เดิมใน `matching.py` ไม่เปลี่ยน — เพิ่มแค่ `nested_r2` และ option ที่ค่า default คงพฤติกรรมเดิม
(`match_exposure(alternatives=False)` ข้าม Lasso/Ridge · `get_index_matches(band_pct=...)`)

### 1. สร้าง style factor (`data/style_factor.py::build_style_levels`)
iShares MSCI factor ETF เป็น long-only จึงเคลื่อนตามตลาดมาก (corr กับ ACWI 0.80-0.95)
ถ้า regress ตรงๆ ทั้ง 4 ตัวจะวัด "ตลาด" ซ้ำกัน 4 ครั้ง จึงต้อง **de-market** ก่อน:

```
r_blend  = 0.6·r_US + 0.4·r_Intl       ← blend ใน return space (ห้าม blend level)
level    = cumprod(1 + r_blend)
relative = level ÷ ACWI ETF            ← USD ÷ USD -> ค่าเงินหักล้างพอดี
LowVol   = ACWV ÷ ACWI                 ← ACWV เป็น global อยู่แล้ว ไม่ต้อง blend
```

| factor | US | Intl |
|---|---|---|
| Momentum | MTUM | IMTM |
| Quality | QUAL | IQLT |
| Value | VLUE | IVLU |
| LowVol | ACWV (global) | — |

- **ผล:** |pairwise corr| เฉลี่ยของ 4 factor ลดจาก **0.73** (ETF ดิบ) เหลือ **0.17** (relative)
- **ทำไมคืนเป็น level ไม่ใช่ return:** `build_fund_returns` ใช้ `reindex(ffill)` บน NAVDate แล้วคิดอัตราส่วน level จึงทบต้นช่วงที่กองไม่รายงานให้อัตโนมัติ
- **ทำไม weight 0.6:** ใกล้สัดส่วน US ใน ACWI · ตอน data gate กวาด 0.40-0.80 แล้ว corr ของ style กับ "US ชนะโลก" ต่ำสุดที่ 0.60 · ใช้ค่าเดียวทุกกอง ไม่ derive รายกอง
  เพราะถ้าหักด้วย ACWI แล้ว weight ต่างจากสัดส่วนใน ACWI จะทำให้ทุก factor มี country bet (US−Intl) ปนเท่ากัน

### 2. ตัวแปรควบคุม 3 ตัว (`config.STYLE_CONTROL_COLS`)
| control | ที่มา | ดูดอะไรออก |
|---|---|---|
| `MSCI_ACWI` | base_data (THB, ราคาปิดท้องถิ่น) | market beta ของกองใน "โลก MSCI" ซึ่งตรงกับ NAV |
| `US_VS_ACWI` | `MSCI_USA ÷ MSCI_ACWI` (THB÷THB) | "US ชนะโลก" · ถ้าไม่คุม Value/LowVol relative จะสัมพันธ์กับตัวนี้ −0.26/−0.43 และกองหนัก US จะดูเป็น Growth เกินจริง |
| `ACWI_ETF` | snapshot (USD, ปิดที่ NY) | ตลาดโลกใน "โลก ETF" ซึ่งตรงกับ style factor |

control ถูก**ตัดออกก่อนจัด primary/secondary** และเก็บใน `style_coefs.csv` ด้วย `scope = "style_control"`
`get_index_matches(coefs, ix, "style", band_pct=config.STYLE_SECONDARY_BAND_PCT)` จึงไม่หยิบ control ขึ้นมาจัดอันดับ (ชื่อที่ได้ยังไม่ติดเครื่องหมาย ต้องผ่าน `style_label` ต่อ)

**ทำไมต้องคุมตลาดทั้งสองโลก (บทเรียนจาก sanity check 2026-09-15):**
NAV ของกองและดัชนี MSCI ใช้ราคาปิดท้องถิ่นเป็น THB ส่วน style ETF ใช้ราคาปิดที่ NY เป็น USD
return ของ MSCI_ACWI กับ ACWI ETF จึง corr กันแค่ **0.78**
ถ้าคุมแค่ MSCI_ACWI ตัวเดียว regression จะใช้ LowVol relative (ACWV÷ACWI ซึ่ง corr **−0.79** กับ ACWI ETF) มาอุดส่วนต่างของสองโลก
ผลคือ coef ติดลบปลอม กองส่วนใหญ่จึงได้ป้าย High-Beta
ตรวจสาเหตุอื่นแล้วไม่ใช่: ไม่ใช่ FX hedge (corr ของ FX แฝงกับ THB=X = −0.07) และไม่ใช่วันที่เหลื่อมกัน (corr สูงสุดที่ lag 0 และวันหยุด US ตรงกันทุกแหล่ง)

| | control 2 ตัว (เดิม) | **control 3 ตัว (ปัจจุบัน)** |
|---|---|---|
| กองที่ได้ High-Beta เป็น primary | 236 / 313 (75%) | **92 / 313** |
| partial market beta ในโมเดลเต็ม (median) — ยิ่งต่ำ = style ถูกใช้ดูดตลาดแทน | 0.57 | **0.88** |
| กอง defensive (primary sector = HC/CS/UT) ได้ Low-Vol | 3 / 32 | **26 / 32** |

`mkt_beta` (คอลัมน์ในตาราง) = OLS coef ของ MSCI_ACWI + ACWI_ETF **จากโมเดลที่มีแค่ control** (`config.STYLE_MARKET_COLS`) = beta ตลาดรวมจริงของกอง
ไม่ใช้ coef จากโมเดลเต็ม เพราะ style relative มีขาตลาดในตัว (LowVol_rel มี beta −0.49 ต่อ ACWI_ETF) coef ตลาดตรงนั้นจึงเป็น partial beta
ตัวอย่างที่เจอตอน code review: กอง semiconductor ได้ partial beta 0.7-0.9 ทั้งที่ beta จริง ~1.8 · กอง Low-Vol ได้ ~1 ทั้งที่จริง ~0.5-0.7

### 3. R² ของหน้านี้คือ incremental R²
ใส่ market control แล้ว R² รวมจะสูงเพราะตลาดอธิบายกองหุ้นไปเกือบหมด หน้านี้จึงแสดง**ส่วนที่ style อธิบายเพิ่ม**:

```
style_r2      = R²(control + style) − R²(control)   ← OLS nested (matching.nested_r2) ≥ 0 เสมอ
style_r2_full = R²(control + style)
```

ผลจริง: incremental median **0.038** (p25 0.015 · p75 0.062 · p90 0.094) · full median **0.49**
ค่าต่ำเป็นเรื่องปกติ ไม่ได้แปลว่าโมเดลผิด · ElasticNet ใช้แค่จัดอันดับ ไม่ได้ใช้คิด R²

### 4. primary / secondary (`config.STYLE_SECONDARY_BAND_PCT = 0.30`)
แยก band ของ style ออกจาก country/sector เพราะ factor มีแค่ 4 ตัว · calibrate จาก distribution จริงแล้วยังใช้ 30% เท่าเดิม:

| band | ไม่มี secondary | secondary ≥ 2 |
|---|---|---|
| 20% | 75.4% | 1.0% |
| **30%** | **63.6%** | **7.3%** |
| 40% | 52.1% | 13.4% |
| 50% | 38.7% | 23.0% |
| *(อ้างอิง) country / sector ที่ 30%* | *64.1% / 63.3%* | *9.8% / 9.0%* |

มี **6 กอง**ที่ ElasticNet ตัด coef ของ style เหลือ 0 ทั้ง 4 ตัว จึงไม่มีป้าย และขึ้นเป็น "ไม่พบ exposure ชัดเจน"
กลุ่มนี้มี incremental R² < 0.013 ทุกกอง (ABAGS · JSM · UOBSJSM · KT-VIETNAM-A · KT-VIETNAM-SSF · TBIOTECH)

---

## ผล sanity check (2026-09-15, 313 กอง)
**Distribution:** Growth 111 · High-Beta 92 · Low-Vol 48 · Value 14 · Junk 13 · Momentum 13 · Quality 8 · Contrarian 8 · ไม่มีป้าย 6

| primary sector ของกอง (หน้า 2) | ป้าย style ที่ได้ |
|---|---|
| Utilities (10) | Low-Vol **10/10** |
| Health Care (19) | Low-Vol **15/19** |
| Information Technology (68) | Growth 28 · High-Beta 25 · Low-Vol 6 · Momentum 6 · Value 2 |
| Financials (20) | **Value 9** · Low-Vol 5 · Momentum 3 |

**ตัวอย่างกองจริง:**
- MGMVOL (MFC Global *Minimum Volatility*) ได้ **Low-Vol** และมี incremental R² สูงสุดของทั้งชุด (0.37)
- กอง Global Infrastructure (B-GLOB-INFRA, PRINCIPAL GIF, KKP GINFRAEQ) ได้ **Low-Vol**
- TUSFIN-A (TISCO US Financial) ได้ **Value**
- K-USA-A ได้ **Growth**
- ES-USTECH และ DAOL-GTECH ได้ **High-Beta**

---

## ข้อมูลและคำสั่ง
| ไฟล์ | รายละเอียด |
|---|---|
| `base_data/STYLE_FACTOR_ETF.csv` | snapshot ราคา ETF 8 ตัว (auto_adjust = รวมปันผล, USD) · 1,472 แถว · 2020-11-02 → 2026-09-14 |
| regressor หลังรวมปฏิทิน | 1,456 แถว · 2021-01-01 → 2026-07-31 (ถูกจำกัดโดย MSCI) |
| `cache/style_results.csv` | 209 × 9 — `FundCode, n_obs_style, style_primary, style_primary_factor, style_primary_coef, style_secondary, style_r2, style_r2_full, mkt_beta` |
| `cache/style_coefs.csv` | 1,463 × 4 (209 กอง × 7 regressor) — ElasticNet เท่านั้น (ข้าม Lasso/Ridge เพราะยังไม่มีหน้าที่ใช้) · scope `style` / `style_control` |

```bash
./.venv/bin/python data_access.py style-download   # ดึง snapshot จาก yfinance (ต้องต่อเน็ต — ครั้งแรก/อัปเดต)
./.venv/bin/python data_access.py style            # build style cache (~40 วิ · ต้องมี results.csv ก่อน)
```

- ปฏิทิน MSCI (ทุกวันจันทร์-ศุกร์) กับ NYSE ต่างกัน จึงรวมด้วย `combine_levels` แบบ union → ffill → ตัดเฉพาะช่วงที่ทุกชุดมีข้อมูล ทำให้ไม่มี NaN และไม่มี return 0 ปลอมหลังชุดใดหมด
- แอป**ไม่ดึงเน็ตเอง** ถ้ายังไม่มี snapshot หน้า 6 จะเตือนพร้อมบอกคำสั่ง ส่วนปุ่ม 🔄 Rebuild จะ build style ต่อท้าย (หลัง `build_pipeline` เพราะต้องใช้รายชื่อกอง E) เฉพาะเมื่อมี snapshot แล้ว

## ⚠️ ข้อควรระวัง
1. **ETF ทุกตัวปิดตามเวลา NY** — กองที่ลงทุนเอเชียจึง fit หยาบกว่า (ข้อจำกัดเดียวกับ MSCI_USA ในหน้า 1) · control ACWI_ETF ช่วยได้มากแต่ไม่ได้กำจัดความต่างของสองโลกหมด
2. **incremental R² ต่ำเป็นปกติ** แต่ป้ายของกองที่ `style_r2` ต่ำมาก (≲ 0.01) ไม่ควรเชื่อมาก ให้ดู R² ประกอบเสมอ
3. **LowVol เป็น factor ที่แยกจาก market beta ได้ยากที่สุด** (ACWV÷ACWI มี beta −0.49 ต่อตลาด) ป้าย Low-Vol/High-Beta จึงสะท้อน beta รวมของกองด้วย — ดูคู่กับ `mkt_beta` (median: High-Beta 1.22 · Low-Vol 0.60 · ทั้งชุด 0.94)
4. **snapshot ไม่อัปเดตเอง** ต้องรัน `style-download` ใหม่ · ช่วงที่ใช้ regress ยังถูกจำกัดโดยปลาย MSCI (2026-07-31)
5. **เป็นความสัมพันธ์เชิงสถิติ ไม่ใช่พอร์ตถือครองจริง**
6. *(ยังไม่ทำ)* ยังไม่มี scope style ในหน้า 3 Match Strength
