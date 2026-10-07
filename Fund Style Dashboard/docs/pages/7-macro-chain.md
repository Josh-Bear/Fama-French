# 🌐 หน้า 7 — Macro Chain

**ไฟล์:** `pages/7_🌐_Macro_Chain.py`
- ข้อมูล: `data_access.get_macro_loadings()` / `get_macro_index_betas()`
- factor: `data/macro_factor.py`
- คณิต: `analysis/macro_chain.py`
- กราฟ: `viz.macro_bar`

## หน้านี้ทำอะไร
- หน้า 1-2 บอกว่ากอง **"ลงทุนที่ไหน"**
- หน้า 6 บอกว่ากอง **"ลงทุนหุ้นแบบไหน"**
- หน้านี้บอกว่ากอง **"ไวต่อปัจจัยมหภาคตัวไหน"** จาก 7 ตัว: Oil, Gold, USDTHB, Copper, DXY, VIX, US10Y

รายละเอียดของหน้า:
- ใช้**เฉพาะกอง E (209 กอง หลัง clean NAV 2026-09-30)** เหมือนหน้า 6 — กรองตั้งแต่ pipeline (`config.MACRO_POLICY`)
  - เหตุผล: implied มองผ่าน index หุ้นเท่านั้น จึงมองไม่เห็นความไวของกองบอนด์/ทอง (ดู "implied มองไม่เห็นอะไร")
  - ผู้ใช้ตัดสินใจ 2026-09-15 (เดิมแสดงทุกกอง 368 กองพร้อม banner เตือน F/O)
- **ใช้งาน:** เลือกกองจาก dropdown → กราฟ bar แสดง 2 วิธีคู่กันต่อ factor
  - 🔵 **implied**
  - 🟠 **direct**
  - ◆ = median ของกอง E
- **metric:** R² implied · R² direct · จำนวนเดือน
- **expander ตาราง:**
  - impact ของทุกกอง (เรียงคอลัมน์ได้ เช่นหากองที่ไวต่อน้ำมันที่สุด)
  - ตาราง Stage 1 (index ไวต่อ macro แค่ไหน)
- **ไม่มีป้าย primary/secondary** เพราะหลังปรับหน่วยแล้ว VIX เป็นตัวหลักของกอง E ถึง 196/313 กอง ป้ายนี้จึงไม่ให้ข้อมูล

---

## 7 macro factor (`config.MACRO_*`)
| factor | แหล่ง | หน่วยดิบ | แปลงรายเดือน |
|---|---|---|---|
| Oil_Brent | yfinance `BZ=F` | USD/barrel | % return |
| Gold | yfinance `GC=F` | USD/oz | % return |
| USDTHB | yfinance `THB=X` | บาทต่อ USD (ขึ้น = บาทอ่อน) | % return |
| Copper | yfinance `HG=F` | USD/lb | % return |
| DXY | yfinance `DX-Y.NYB` (fallback `DX=F`) | ดัชนี | % return |
| VIX | yfinance `^VIX` | จุด | **Δ ระดับ** |
| US10Y | FRED `DGS10` (CSV ตรง) | % yield | **Δ ระดับ (pp)** |

- **VIX / US10Y ใช้ Δ ไม่ใช่ % return** เพราะไม่ใช่ราคาสินทรัพย์
  เช่น yield ขยับจาก 4.78% เป็น 4.80% คือ +0.02pp ไม่ใช่ "return" +0.42%
- **ความถี่รายเดือน (month-end)** ใช้ค่าสุดท้ายที่มีจริงของเดือน · ช่วงข้อมูล = ช่วงร่วมของ MSCI กับ snapshot
- **กติกาเดือนสุดท้าย** (`macro_chain.month_end_levels`): ถ้าข้อมูลหมดกลางเดือน ค่า "สิ้นเดือน" ของแต่ละชุดจะเป็นคนละวัน
  (FRED ช้ากว่า yfinance ~4 วัน) จึงทิ้งเดือนที่ยังไม่จบ · เดือนที่จบวันเสาร์-อาทิตย์ยังนับว่าครบ

---

## โมเดล

```
Stage 1   index_return[i]  ~ 7 macro                      (OLS รายเดือน, 28 index)   -> B[index, factor]
implied   loading[fund]    = ½ Σ_scope Σ_i β_raw[fund,i] × B[i, :]                   (chain ผ่าน country/sector)
direct    fund_return      ~ 7 macro                      (OLS รายเดือน, ≥ 36 เดือน)
แสดงผล    impact_1sd       = loading × σ(factor)          (% return ต่อ macro ขยับ 1 SD)
```

### 1. Stage 1 — index ไวต่อ macro แค่ไหน (`macro_chain.stage1_betas`)
- OLS ธรรมดา ไม่มี penalty เพราะต้องใช้ coef ของทุกตัวไป chain ต่อ ไม่ได้ต้องการเลือกตัวแปร
- ใช้ `matching.nested_r2` ที่มีอยู่แล้ว (base ว่าง = intercept อย่างเดียว)
- **ผล (66 เดือน, 2021-02 → 2026-07):**
  - R² เฉลี่ย **0.395** · median 0.41
  - สูงสุด MSCI_WORLD 0.647 · ต่ำสุด China A 0.089
  - VIF ของ 7 factor อยู่ที่ 1.2–2.9
  - จำนวน index (จาก 28) ที่ |t| > 2:

    | VIX | USDTHB | Copper | US10Y | Gold | DXY | Oil |
    |---|---|---|---|---|---|---|
    | 22 | 16 | 10 | 8 | 3 | 3 | 2 |

  - Energy index ไวต่อ Oil ชัด: β 0.355, t = 7.0

### 2. implied — chain ผ่าน country/sector (`macro_chain.unstandardize` + `implied_loadings`)
ต้องกันกับดัก 2 ข้อ (พบตอน review แผนด้วยข้อมูลจริง 2026-09-15):

1. **coef ใน `coefs.csv` เป็น standardized** (StandardScaler บน X แล้วเข้า ElasticNet — y ไม่ scale)
   - ต้อง unstandardize ก่อนเสมอ: `β_raw = coef ÷ σ`
     - σ = SD (ddof=0) ของ index return ใน aligned ชุดเดียวกับที่ fit
     - ค่านี้ตรงกับ scaler ที่ refit บน X เต็ม จึงแปลงได้ exact
     - pipeline จึงต้องโหลด nav แล้ว `build_fund_returns` ใหม่ต่อกอง
   - ถ้าไม่แปลง loading จะเล็กเกินจริง **~64 เท่า**
2. **country กับ sector เป็นคนละ regression**
   - แต่ละชุดอธิบาย return ของกองทั้งก้อน (ผลรวม β_raw ของกอง E: country 0.71 · sector 0.62)
   - ถ้ารวม 28 ตัวจะนับตลาด 2 รอบ → คำนวณแยกทีละ scope แล้ว**เฉลี่ย**
   - join ตามชื่อ index (ไม่ใช่ตำแหน่ง) และตรวจว่าชุด index ครบตรงกัน

| วิธี chain (ตอน review: ทุกกอง ≥ 36 เดือน) | corr² กับ return จริง | slope (ควร ≈ 1) |
|---|---|---|
| standardized รวม 28 (แผนเดิม) | 0.286 | 63.7 |
| β_raw country | 0.264 | 1.15 |
| β_raw sector | 0.293 | 1.21 |
| β_raw รวม 28 (นับซ้ำ) | 0.293 | 0.62 |
| **β_raw เฉลี่ย 2 scope (ใช้จริง)** | **0.293** | **1.25** |

slope 1.25 คือ implied เล็กกว่าจริงราว 20% เพราะ ElasticNet หดค่า coef (เฉพาะกอง E: slope 1.16)
ไม่แก้ เพื่อให้สอดคล้องกับหน้า 1-3

### 3. direct — regress NAV ตรง (`macro_chain.ols_loadings`)
- return รายเดือนของกอง (NAV สิ้นเดือน · กติกาเดือนสุดท้ายเดียวกัน) ~ 7 macro ด้วย OLS
- **ทำไมทำได้:** กอง E มีข้อมูล median 60 เดือน และ 309/313 กองมี ≥ 36 เดือน ใกล้กับ Stage 1 เอง (66 เดือน)
  - เหตุผลเดิมที่เลี่ยงวิธีนี้ (n_obs ระดับกองน้อย) จึงใช้ไม่ได้
  - กองที่ < `MACRO_MIN_MONTHS` (36) มี 4 กอง → ไม่มีค่า direct
- **R² (กอง E):**
  - direct = R² ของ OLS (median 0.42 · อยู่ในตัวอย่าง จึงสูงเกินจริงเล็กน้อย)
  - implied = corr² ของค่าที่ chain ทำนายกับ return จริง (median 0.28 · ไม่ได้ fit กับกองเลย)

### 4. หน่วยแสดงผล — impact ต่อ 1 SD
- **ปัญหา:** loading ดิบมีหน่วยต่างกัน (ต่อ return 100% / ต่อ VIX 1 จุด / ต่อ yield 1pp) เทียบข้าม factor ไม่ได้
  - ตัวอย่าง: "USDTHB coef เฉลี่ย 0.52 สูงสุด" ที่แผนเดิมสรุปไว้เป็นผลของหน่วยล้วนๆ
- **วิธีแก้:** แสดง `impact_1sd = loading × σ(factor)` = กองขยับกี่ % ในเดือนที่ macro ขยับ 1 SD
  - σ คำนวณจากช่วง Stage 1
  - ขนาด 1 SD ของแต่ละ factor แสดงใต้ชื่อบนกราฟ

**ขนาด 1 SD รายเดือน (66 เดือน):**

| Oil | Gold | USDTHB | Copper | DXY | VIX | US10Y |
|---|---|---|---|---|---|---|
| 11.7% | 4.8% | 2.7% | 6.3% | 2.1% | 4.7 จุด | 0.27pp |

**กอง E — implied impact (% ต่อ 1 SD):**

| | Oil | Gold | USDTHB | Copper | DXY | VIX | US10Y |
|---|---|---|---|---|---|---|---|
| p10 | −0.61 | −0.44 | −0.25 | 0.38 | −0.51 | −2.80 | −1.76 |
| **median** | **−0.21** | **0.02** | **1.13** | **0.93** | **0.17** | **−1.53** | **−0.78** |
| p90 | 0.21 | 0.34 | 1.58 | 1.46 | 1.08 | −0.20 | −0.12 |

---

## ผลตรวจ (chain gate 2026-09-15)
- **implied กับ direct ไปทางเดียวกันข้ามกอง** (corr ของ loading · กอง E 309 กองที่มี direct):

  | VIX | USDTHB | US10Y | DXY | Copper | Gold | Oil |
  |---|---|---|---|---|---|---|
  | 0.84 | 0.79 | 0.73 | 0.66 | 0.61 | 0.40 | 0.35 |

- **implied มองไม่เห็นอะไร** (ตรวจตอนยังรวมทุกกอง 368 กอง — เป็นเหตุผลที่ตัด F/O):
  chain ผ่านได้แค่ index หุ้น จึงพลาดกองที่ exposure หลักไม่ใช่หุ้น

  | กลุ่มกอง | factor | direct | implied |
  |---|---|---|---|
  | กองทอง 14 กอง (O) | Gold | 0.69–0.93 (median 0.77) | median 0.11 |
  | REIT / property 14 กอง | US10Y | median −0.087 (ติดลบทุกกอง) | median −0.018 |
  | กองบอนด์ (F) | US10Y | −0.03 ถึง −0.06 | −0.001 ถึง −0.006 |

  จึงตัดกอง F/O ออกจากหน้านี้ · กอง E ที่ถือสินทรัพย์ลักษณะนี้ผ่านหุ้น (เช่น หุ้นเหมืองทอง · REIT) ยังเห็นความต่างได้จาก direct ที่แสดงคู่เสมอ
- **ไม่มีกองพลังงานจริงในชุด** — 4 กองที่ `sector_primary = EN` เป็นกองบอนด์ที่ coef EN ≈ −0.0007
  (artifact ของ |coef| ที่เล็กมาก) จึงใช้ sanity check เรื่องน้ำมันกับกองทุนไม่ได้

---

## ข้อมูลและคำสั่ง
| ไฟล์ | รายละเอียด |
|---|---|
| `base_data/MACRO_FACTOR.csv` | snapshot level ดิบ 7 factor · 1,528 แถว · 2020-11-02 → 2026-09-15 (USDTHB ถึง 09-14 · US10Y ถึง 09-11) |
| `cache/macro_loadings.csv` | 2,926 × 7 (209 กอง E × 7 factor × 2 วิธี) — `FundCode, method, factor, loading, impact_1sd, r2, n_months` |
| `cache/macro_index_betas.csv` | 196 × 8 (28 index × 7 factor) — `index, scope, factor, beta, impact_1sd, factor_sd, r2, n_obs` |

```bash
./.venv/bin/python data_access.py macro-download   # ดึง snapshot (ต้องต่อเน็ต — ครั้งแรก/อัปเดต)
./.venv/bin/python data_access.py macro            # build macro cache (~15 วิ · ต้องมี results.csv + coefs.csv ก่อน)
```

- แอป**ไม่ดึงเน็ตเอง** — ถ้ายังไม่มี snapshot หน้า 7 จะเตือนพร้อมบอกคำสั่ง
- ปุ่ม 🔄 Rebuild จะ build macro ต่อท้าย (หลัง `build_pipeline` เพราะอ่าน `coefs.csv`) เฉพาะเมื่อมี snapshot แล้ว
- cache เก็บ `loading` หน่วยจริงไว้ด้วย สำหรับ risk model หน้า 8 ในอนาคต (Σ = B·F·Bᵗ + D)
- สคริปต์ exploratory ตอนวางแผน (`fetch_macro_exploratory.py`, `stage1_macro_exploratory.py`, `macro_factor_test.csv`) ย้ายไป `docs/archive/`

## ⚠️ ข้อควรระวัง
1. **implied ไม่ใช่พฤติกรรมจริง** — ไม่เห็น FX hedge, การเลือกหุ้นที่เบี่ยงจาก index หรือสินทรัพย์นอกหุ้น · ให้ดู direct ประกอบเสมอ
2. **VIX ≈ proxy ตลาดหุ้นโลก** (corr −0.66 กับ MSCI_ACWI) — กองหุ้นเกือบทุกกองจึงติดลบกับ VIX มากสุด
3. **USDTHB กับ DXY เคลื่อนด้วยกัน (corr 0.71)** แยกผลกันไม่เสถียร
   - กอง E: direct USDTHB median −0.17 แต่ implied +0.42
   - ดูผลรวมสองตัวจะนิ่งกว่า (direct 0.11 · implied 0.37 · corr 0.68)
4. **Oil / Gold / DXY มีนัยสำคัญใน Stage 1 เพียงไม่กี่ index** — implied ของ 3 ตัวนี้ส่วนใหญ่เป็น noise (ยกเว้น Energy กับ Oil)
5. **กอง EM / China เชื่อได้น้อยกว่า** — Stage 1 R² ของ index กลุ่มนี้ต่ำ (China A 0.089)
6. **Oil / Gold / Copper เป็น futures ต่อเนื่อง** มี roll gap เล็กน้อยในรอบเปลี่ยนสัญญา
7. **ตัวอย่าง 66 เดือน** (obs:parameter ~8:1) — ควรดูความเสถียรของ coef เมื่อข้อมูลสะสมมากขึ้น · snapshot ไม่อัปเดตเอง
8. *(ยังไม่ทำ)*
   - USDCNY เป็น factor ที่ 8
   - residual diagnostic (regress residual ของ country/sector กับ macro)
