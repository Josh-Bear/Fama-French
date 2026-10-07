# PAGE6_STYLE_FACTOR_PLAN.md — หน้า 6: Style Factor Match (Momentum/Quality/Low-Vol/Value)

> สถานะ: **แผน — ยังไม่ execute code** (ตาม workflow ของโปรเจกต์: ต้อง confirm แผนก่อนเริ่มเขียนโค้ดจริง)
> ที่มา: อ่าน `fund_management_factors_TH.md` (งานวิจัย factor ที่ hedge fund/quant fund ใช้จริง) แล้วประยุกต์กับระบบนี้ 2026-09-14
> คู่กับแผนนี้ (ยังไม่เขียนละเอียด — ดู §7 Future Plan): หน้า 7 = Macro Factor Chain (Oil/VIX/Gold/Exchange/US10Y), หน้า 8 = Portfolio Optimize

---

## 0. สรุปสั้น

สร้าง **scope ใหม่ "style"** เทียบเท่า country(18)/sector(10) ที่มีอยู่แล้ว — regress กองทุน**เฉพาะ policy "E" (equity)** กับ **4 style factor index**: Momentum, Quality, Low-Volatility, Value โดยใช้ ElasticNet pipeline **เดิมทุกอย่าง** (ไม่ใช่ 2-stage chain แบบที่วางแผนไว้สำหรับ macro factor) เพราะ style factor index เป็น "investable index return" ประเภทเดียวกับ MSCI country/sector — regress ตรงกับกองได้เลย

---

## 1. ทำไมต้องมีหน้านี้ (จากเอกสารวิจัย)

- **Equity style factor ≠ macro factor** — style factor คือ cross-sectional ภายใน universe หุ้น (จัดอันดับหุ้นดี/แย่) ส่วน macro factor (Oil/VIX/rates) คือ exposure เชิงทิศทางข้าม asset class **ห้ามยำรวมกันในสมการเดียว** → ต้องแยกเป็นหน้า/regression คนละชุด
- **หลักฐานเฉพาะไทย (SET50) ใช้กับกองเราไม่ได้** — กองทุนในระบบนี้เป็น FIF (FIF Flag=Y) **ไม่ถือหุ้นไทยเลย** ลงทุนต่างประเทศผ่าน MSCI ล้วนๆ หลักฐานเรื่อง book-to-market อ่อนในไทย/low-beta แข็งในไทย เป็นของโปรเจกต์พี่น้อง "Fama French SET50" คนละบริบท
- **หลักฐานระดับโลกที่ใช้ได้จริงกับกองเรา**: Momentum, Quality/Profitability, Low-Vol/BAB "เดินทางข้ามประเทศได้ดีที่สุด" (BAB ข้าม 20 ตลาด, QMJ ข้าม 24 ประเทศ) ตรงกับกองทุนที่กระจายทั่วโลกผ่าน MSCI Value regime-dependent กว่าแต่ spread กว้างสุดใน EM (เรามี exposure เยอะ: ASEAN/China/India) — เก็บไว้ด้วย Size/Carry หลักฐานอ่อนสุด **ไม่เอา**
- **เอกสารเห็นด้วยกับสถาปัตยกรรมที่มีอยู่แล้ว** — Section 3 ของเอกสาร: "integrated multivariate scoring" (regress ทุก factor รวมกันในสมการเดียว — ที่ ElasticNet ทำอยู่แล้วในหน้า 1-3) ดีกว่า "mixed sleeve" (แยก regression ทีละ factor) → ไม่ต้องเปลี่ยน pipeline หลัก แค่เพิ่ม scope ใหม่

---

## 2. Scope: เฉพาะกอง "E" เท่านั้น

- เหตุผล: style factor (Momentum/Quality/Value/Low-Vol) เป็นแนวคิดเฉพาะตลาดหุ้น ไม่มีความหมายกับกอง Fixed Income (F)/Other (O)
- จำนวนกองที่เข้าเงื่อนไข: **313/368 กอง** (ตรวจกับ `cache/results.csv` จริงแล้ว — `policy == "E"`)
- Filter จุดนี้ทำที่ไหน: เพิ่ม guard ใน pipeline ของ style scope โดยเฉพาะ (`data_access.build_pipeline` หรือฟังก์ชันแยกสำหรับ style) — **ไม่แก้ filter ของ country/sector เดิม** (ยังคง regress ทั้ง 368 กองเหมือนเดิมสำหรับ 2 scope นั้น)

---

## 3. Data source: 4 style factor, ผสม US+Intl

ใช้ iShares MSCI Factor ETF (yfinance) เป็น proxy ของ MSCI factor index จริง — **เหตุผลที่มั่นใจว่าน่าจะดึงได้**: โปรเจกต์พี่น้อง "Fama French SET50" ใช้ yfinance ดึง Oil(BZ=F)/VIX(^VIX)/Gold(GC=F)/Exchange(THB=X) สำเร็จมาแล้วจริง (validate 10/10) เป็น data provider เดียวกัน — **แต่ยังไม่ทดสอบ ticker พวกนี้จริงเพราะ sandbox ที่ใช้ตอนวางแผนบล็อก network ทั้ง cloud กับ device — ต้อง verify ตอน implement จริงบนเครื่องผู้ใช้**

| Factor | US ticker | Intl (ex-US) ticker | สูตรผสม |
|---|---|---|---|
| Momentum | MTUM | IMTM | 0.6×MTUM + 0.4×IMTM |
| Quality | QUAL | IQLT | 0.6×QUAL + 0.4×IQLT |
| Value | VLUE | IVLU | 0.6×VLUE + 0.4×IVLU |
| Low-Volatility | USMV | — | ใช้ **ACWV** (global ACWI-based) เดี่ยวๆ ไม่ต้องผสม |

สัดส่วนผสม 60/40 = ประมาณสัดส่วน US ต่อ non-US ใน MSCI ACWI จริง (ค่า default ที่เสนอ — **ยังไม่ empirically validate**, เป็นจุดที่ควร sensitivity-check ตอน implement เช่น ลองเปลี่ยนเป็น 50/50 ดูว่า loading เปลี่ยนมากไหม)

คำนวณ return รายวัน (pct change ของราคาปรับ dividend แล้ว, `auto_adjust=True`) แล้ว align กับ NAVDate ของกองแบบเดียวกับที่ country/sector ทำอยู่ในปัจจุบัน (ไม่ resample เป็น monthly —ใช้ frequency เดียวกับ country/sector regression ที่มีอยู่แล้ว เพราะเป็น direct regression ไม่ใช่ chain)

---

## 4. Methodology — เหมือนหน้า 1-2 ทุกประการ

```
กอง E (313 กอง) return series (winsorize แล้ว, Phase 2 เดิม)
        │
        ▼
ElasticNetCV (+ Lasso/Ridge เก็บเทียบ) vs [Momentum, Quality, LowVol, Value] (4 ตัวพร้อมกัน)
        │
        ▼
style_primary = index ที่ |standardized coef| มากสุด
style_secondary = band-based ตาม config.SECONDARY_BAND_PCT (ใช้ค่าเดิม 0.30 ตัวเดียวกับ country/sector
                   — ต้องเช็คการกระจายจริงหลัง fit แล้วว่าเหมาะไหม เพราะมีแค่ 4 factor ไม่ใช่ 18/10 ตัว)
style_r2 = R² ของ regression นี้
```

**ไม่ใช้ chain 2 ชั้น** (ที่วางแผนไว้สำหรับ macro factor หน้า 7) เพราะ style factor index เป็น investable return series แบบเดียวกับ MSCI — regress ตรงกับกองได้ ไม่ต้องผ่าน index ก่อน

---

## 5. โครงสร้างโค้ดที่ต้องเพิ่ม (ยังไม่เขียน — สำหรับ implement จริง)

- **`data/style_factor.py`** (ใหม่) — คล้าย `data/msci_index.py`: ดึง 4 ticker (+ 3 ticker เสริมสำหรับผสม Intl) ผ่าน yfinance, คำนวณ blended return ตามสูตร §3, คืน long-form/wide-form เหมือน MSCI loader
- **`config.py`** — เพิ่ม `STYLE_FACTOR_COLS = ["Momentum", "Quality", "LowVol", "Value"]`, ticker mapping, blend weight constant (`STYLE_US_WEIGHT = 0.6`), และ guard สำหรับ `policy == "E"` เท่านั้น
- **`analysis/matching.py`** — ต้องอ่าน source จริงก่อนแก้ (ยังไม่ได้เปิดดูรอบนี้) เพื่อเพิ่ม branch `scope="style"` ให้ `classify_exposure()`/`get_index_matches()`/`get_funds_matching_index()` ใช้ได้กับ scope ใหม่โดยไม่พังของเดิม
- **`data_access.py`** — เพิ่ม pipeline สำหรับ style scope (filter policy=="E" ก่อน regress), cache แยก (เช่น `cache/style_coefs.csv`) ไม่ปนกับ `coefs.csv` เดิม (หรือเพิ่มคอลัมน์ scope="style" ในไฟล์เดิม — ต้องดูโครงสร้างไฟล์จริงก่อนตัดสินใจ)
- **`pages/6_🎯_Style_Match.py`** (ใหม่) — โครงเดียวกับ `pages/1_🌍_Country_Match.py`/`2_🏭_Sector_Match.py`: scatter ann_return vs ann_vol, สี=quadrant, filter ตาม style_primary (เฉพาะกอง E ปรากฏในหน้านี้)
- **`viz.py`** — reuse `scatter()`/`add_quadrant()` เดิมได้เลย (ฟังก์ชันกลาง ไม่ผูกกับ scope)

---

## 6. Checklist ก่อน implement จริง (ตาม convention ของโปรเจกต์นี้)

- [ ] ทดสอบ fetch 7 ticker จริง (MTUM, IMTM, QUAL, IQLT, VLUE, IVLU, USMV/ACWV) บนเครื่องผู้ใช้จริง — ยืนยัน history ยาวพอ (ต้องครอบคลุม 2021+ อย่างน้อย)
- [ ] เช็คการกระจายตัวจริงของ style_secondary หลัง fit (เหมือนที่เคยเช็ค SECONDARY_BAND_PCT=0.30 กับ country/sector) — 4 factor อาจต้องปรับ band % ต่างจาก 18/10 ตัว
- [ ] อ่าน `analysis/matching.py` เต็มไฟล์ก่อนแก้ (รอบนี้ยังไม่ได้เปิด)
- [ ] รัน `pytest -q` หลังแก้ ยืนยันไม่กระทบ country/sector pipeline เดิม
- [ ] เทียบ style_primary distribution กับสามัญสำนึก (เช่น กอง tech-heavy ควรได้ Momentum/Quality primary ไม่ใช่ Value)

---

## 7. Future Plan (ยังไม่ลงรายละเอียด — แค่กันที่ไว้)

- **หน้า 7 — Macro Factor Chain**: Oil(Brent)/VIX/Gold/Exchange(USD-THB)/US10Y(FRED DGS10), monthly, 2-stage chain (regress 28 MSCI index กับ macro ก่อน → chain ทวนคูณด้วย country/sector coefficient ที่มีอยู่ → ได้ fund-level implied macro loading) เช็ค residual ของกองกับข้อมูลจริงก่อนตัดสินใจว่าต้องเพิ่ม step ไหม UI = bar chart ต่อกองสำหรับ QA
- **หน้า 8 — Portfolio Optimize**: ใช้ loading จาก country+sector+style+macro (ทั้ง 4 scope) เป็น risk model แบบ Barra-style (Σ = B·F·Bᵗ + D) — objective (mean-variance / min-risk / risk-parity) **ยังไม่ตัดสินใจ** รอคุยตอนเริ่มทำหน้านี้จริง

---

## 8. Decision log (สรุปการตัดสินใจทั้งหมดของหน้า 6 ตามลำดับที่คุยกัน)

1. Style factor ≠ macro factor → แยกหน้า (เดิมจะรวม แต่เปลี่ยนใจหลังอ่านเอกสารวิจัย)
2. Scope เฉพาะกอง E (313/368 กอง) — F/O ไม่เกี่ยวกับ style factor
3. ใช้ MSCI Factor Index (ผ่าน ETF proxy) เป็น scope ใหม่ เทียบเท่า country/sector — ไม่ใช้ chain
4. เลือก 4 factor ครบ: Momentum, Quality, Low-Volatility, Value (ตัดทิ้ง Size, Carry — หลักฐานอ่อน)
5. ผสม US+Intl ticker ต่อ factor (60/40) เป็น default — ยังไม่ empirically validate
6. UI เต็มรูปแบบเหมือนหน้า 1-2 (ไม่ใช่แค่ bar chart QA)
7. Renumber หน้าถัดๆไป: macro chain → หน้า 7, portfolio optimize → หน้า 8 (เห็นด้วยแล้ว แต่ยังไม่เขียนละเอียด)
