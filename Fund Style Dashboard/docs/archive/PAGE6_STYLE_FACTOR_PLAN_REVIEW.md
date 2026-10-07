# PAGE6_STYLE_FACTOR_PLAN_REVIEW.md — Review แผนหน้า 6 (Style Factor Match)

> สถานะ: **Review เท่านั้น — ยังไม่แก้โค้ด ไม่แก้ `PAGE6_STYLE_FACTOR_PLAN.md`**
> อ้างอิงแผนหลัก: `PAGE6_STYLE_FACTOR_PLAN.md` (เขียน 2026-09-14)
> เขียนแยกไฟล์ตามคำขอผู้ใช้ 2026-09-14 (ไม่ปนกับ plan หลัก)
> ลำดับข้อ = ลำดับความสำคัญ (1 = ต้องแก้ก่อน implement, 7 = nice-to-have)

---

## 1. [สำคัญที่สุด] Style ETF เป็น long-only tilted ไม่ใช่ long-short market-neutral — ต้อง de-market ก่อน regress

**ปัญหา**: §3 ของแผนหลักเลือก MTUM/QUAL/VLUE/USMV เป็น proxy — ETF พวกนี้เป็น **long-only** (ถือหุ้นจริง เอียงไปทาง factor ที่ต้องการ) ไม่ใช่ long-short แบบ academic factor (เช่น Fama-French UMD/HML ที่ long winner-short loser) ผลคือ ETF พวกนี้มี correlation กับตลาดกว้าง (MSCI ACWI) สูงมาก ~0.85-0.95 (MTUM/QUAL โดยเฉพาะ ช่วงตลาดขึ้น-ลงพร้อมตลาด)

ถ้า regress กองทุนกับ raw ETF return ตรงๆ ตามที่ §4 เขียนไว้ — ค่า coefficient ที่ได้จะถูก "ตลาดกว้าง" ครอบงำเป็นหลัก ไม่ได้สะท้อน style tilt จริง (เพราะทั้ง 4 factor correlate กันเองสูงผ่าน common market component → ElasticNet จะเลือกตัวใดตัวหนึ่งแบบสุ่มๆ ตาม noise ไม่ใช่ตาม style จริง) — นี่คือปัญหาเดียวกับที่ multicollinearity ทำกับ regression ทั่วไป แต่ในเคสนี้สาเหตุคือ "generic beta" ไม่ใช่แค่ correlation ระหว่าง factor เอง

**Fix ที่เสนอ**: คำนวณ **excess return เทียบ market benchmark** ก่อน regress ทุก factor:

```
Momentum_excess = MTUM_blended_return − MSCI_ACWI_return
Quality_excess  = QUAL_blended_return − MSCI_ACWI_return
Value_excess    = VLUE_blended_return − MSCI_ACWI_return
LowVol_excess   = ACWV_return         − MSCI_ACWI_return
```

ใช้ MSCI_ACWI (มีอยู่แล้วในระบบ หรือ ACWI ETF จาก yfinance) เป็น benchmark เดียวกันทั้ง 4 ตัว — นี่คือวิธีที่ใกล้เคียง academic long-short factor มากที่สุดโดยไม่ต้องสร้าง long-short portfolio เองจริงๆ (ซึ่งทำไม่ได้อยู่แล้วเพราะเราไม่มี security-level holdings)

**ผลกระทบต่อแผน**: ต้องแก้ §3 (data source) และ §4 (methodology) ของแผนหลัก — เพิ่ม step "ลบ market component" ก่อนเข้า ElasticNet, และ §5 (`data/style_factor.py`) ต้องดึง MSCI_ACWI (หรือ ACWI ETF) เพิ่มอีก 1 series เป็น input

**นี่คือจุดที่เป็นการแก้ methodology จริง ไม่ใช่แค่ปรับ parameter — ถ้าไม่ทำ ผลลัพธ์ style_primary ที่ได้มีความเสี่ยงสูงที่จะไม่มีความหมาย (แค่บอกว่ากองไหน beta สูง/ต่ำ ซึ่งรู้อยู่แล้วจาก ann_vol หน้า 1-2)**

---

## 2. สัดส่วนผสม US/Intl (60/40) เป็นสมมติฐานที่ยังไม่ validate — ควรคำนวณจากข้อมูลจริงของเรา

§3 ตาราง blend ใช้ 60/40 (US/Intl) เป็นค่า default ที่อ้างอิง MSCI ACWI ทั่วไป — แต่ตรวจกับ `cache/results.csv` จริงแล้ว (313 กอง E) สัดส่วน `country_primary` ของกองในระบบเรา **เอียงไปทาง non-US มากกว่า** generic ACWI composition (มี exposure เยอะที่ ASEAN/China/India/Europe ตามที่ §1 ของแผนหลักพูดถึงเรื่อง EM เอง)

**Fix ที่เสนอ**: ก่อนเขียนโค้ด `style_factor.py` จริง ให้ derive สัดส่วนจาก distribution จริงของ `country_primary` ใน 313 กอง E (เช่น นับ % ของกองที่ primary เป็น US-related MSCI index เทียบกับกองที่ primary เป็น non-US) แล้วใช้เป็น weight ผสม แทนเลข 60/40 ที่ยกมาแบบ generic — สอดคล้องกับวินัยเดิมของโปรเจกต์นี้ที่ validate parameter กับข้อมูลจริงก่อนใช้ (เช่น NAV gap threshold 42 วันที่มาจากดู distribution จริง ไม่ใช่เดา)

**ระดับความสำคัญ**: ปานกลาง — ถ้าไม่แก้ตอนนี้ ผลลัพธ์ยังพอใช้ได้ (60/40 ไม่ใช่ตัวเลขที่ผิดมาก) แต่ควรทำก่อน implement เพราะทำได้ง่าย (มีข้อมูลอยู่แล้ว ไม่ต้องรอ external data)

---

## 3. `SECONDARY_BAND_PCT = 0.30` ใช้ค่าเดิมกับ 4 factor ไม่ได้ทันที — ต้อง recalibrate

§4 เขียนว่าจะใช้ `config.SECONDARY_BAND_PCT = 0.30` ตัวเดียวกับ country(18)/sector(10) — แต่ค่านี้ calibrate มาจากข้อมูลจริงตอนมี regressor 18-28 ตัว (มี "พื้นที่" ให้ coefficient กระจายมากกว่า) กับกรณีมีแค่ 4 regressor ที่ correlate กันสูง (ดูข้อ 1) พฤติกรรมของ standardized coefficient จะต่างกันมาก — band 30% อาจกว้างเกินไป (ทุกกองมี secondary ทุกตัว ไม่มีความหมาย) หรือแคบเกินไป (ไม่มีกองไหนมี secondary เลย)

**Fix**: ยกจาก checklist (§6 เดิม) ขึ้นมาเป็น **required step ก่อน finalize** — หลัง fit จริงกับ 313 กอง ให้ดู distribution ของ (coef_primary − coef_secondary)/coef_primary จริง แล้วเลือก band % ที่เหมาะกับ 4-factor case โดยเฉพาะ (อาจได้ค่าไม่เท่า 0.30 ก็ได้ — ไม่ต้องพยายามใช้ค่าเดียวกันทั้งระบบถ้าข้อมูลบอกว่าไม่เหมาะ)

---

## 4. R² ของ style regression จะต่ำกว่า country/sector มาก — ควร set expectation ใน UI

Country/sector regression (18-28 ตัว, correlation กับกองต่ำกว่า) ได้ R² สูง เพราะ MSCI country/sector index ครอบคลุม exposure ของกองได้เกือบหมด ส่วน style factor (4 ตัว, เป็น "ส่วนเพิ่ม" หลัง de-market ตามข้อ 1) มีแนวโน้มได้ R² ต่ำกว่ามาก — คาดคร่าวๆ **~0.05-0.20** (เทียบกับ country/sector ที่อาจได้ 0.5+)

**นี่ไม่ใช่ bug หรือความล้มเหลวของโมเดล** — เป็นธรรมชาติของ style factor ที่อธิบายได้แค่ "ส่วนเสี้ยว" ของ return หลังหักตลาด+country+sector ไปแล้ว แต่ถ้า UI หน้า 6 (§5, `pages/6_🎯_Style_Match.py`) โชว์ R² แบบเดียวกับหน้า 1-2 โดยไม่มีคำอธิบาย ผู้ใช้อาจเข้าใจผิดว่าโมเดลพัง

**Fix**: เพิ่ม caption อธิบายไว้ในหน้า 6 ตั้งแต่แรก (ทำนองเดียวกับ caption ที่หน้า 5 อธิบายเรื่อง gap-days) — บอกว่า R² ต่ำเป็นเรื่องคาดหมายได้สำหรับ style factor ไม่ใช่ตัวชี้ว่า primary/secondary ผิด

---

## 5. แยก cache ไฟล์ style ออกจาก `results.csv`/`coefs.csv` เดิม

§5 ทิ้งเป็นตัวเลือกเปิดไว้ ("หรือเพิ่มคอลัมน์ scope=\"style\" ในไฟล์เดิม — ต้องดูโครงสร้างไฟล์จริงก่อนตัดสินใจ") — **แนะนำให้ตัดสินใจล่วงหน้าว่าแยกไฟล์** (`cache/style_coefs.csv`, `cache/style_results.csv`) เพราะ:

- `results.csv`/`coefs.csv` ปัจจุบันครอบคลุมทั้ง 368 กอง (ทุก policy) — ถ้าเพิ่มคอลัมน์ style เข้าไปตรงๆ กอง F/O 55 กองจะเป็น NaN ทั้งหมดในคอลัมน์ใหม่ (ตามข้อ 2 ในแผนหลักที่ scope นี้เฉพาะกอง E)
- หน้า 1-5 ที่มีอยู่แล้วไม่ได้ถูกออกแบบมาให้รับมือกับ NaN pattern ใหม่นี้ — มีความเสี่ยงกระทบ logic เดิมที่ไม่ได้ตั้งใจ (เช่น sort/filter ที่ไม่ได้ check NaN เผื่อไว้)
- แยกไฟล์ทำให้ scope ใหม่เป็น additive ล้วนๆ (ไม่แก้ schema ไฟล์เดิมเลย) ตรงกับหลักการ "ไม่ทำให้ระบบเดิมพัง" ของ workflow โปรเจกต์นี้

---

## 6. อ่าน `analysis/matching.py` เต็มไฟล์ก่อน — ย้ายจาก checklist ไปเป็น step แรกของ implementation

§5/§6 ของแผนหลักบอกไว้แล้วว่ายังไม่ได้เปิดไฟล์นี้ดูจริง (`# ต้องอ่าน source จริงก่อนแก้`) — เพราะ `classify_exposure()`/`get_index_matches()`/`get_funds_matching_index()` เป็นจุดที่ต้องเพิ่ม branch `scope="style"` โดยไม่พังของเดิม **ควร**อ่านไฟล์นี้เต็มๆ**เป็นก้าวแรก** ของการ implement (ก่อนเขียน `data/style_factor.py` ด้วยซ้ำ) เพราะถ้าโครงสร้างภายในไม่รองรับ scope ใหม่ง่ายๆ อาจต้องปรับแผน §5 ทั้งหมด (เช่น ต้อง refactor ฟังก์ชันให้ generic ขึ้นก่อน)

---

## 7. เพิ่ม unit test สำหรับ logic ใหม่ 2 จุด

เสนอเพิ่ม test ใน `tests/` (ถ้ามี suite เดิมอยู่แล้วตาม `pytest -q` ที่ใช้ตรวจ regression ทุกครั้ง):

- **Blend weight logic** — synthetic case: 2 series ที่รู้ค่าแน่นอน → เช็คว่า `0.6×A + 0.4×B` (หรือค่าที่ได้จากข้อ 2) คำนวณถูกจริง รวมถึง edge case ที่ series ใดตัวหนึ่งมี NaN บางวัน (align/ffill ยังไงเมื่อ US ticker กับ Intl ticker ไม่ได้เทรดวันเดียวกันทั้งหมด)
- **E-only filter** — เช็คว่า pipeline style scope กรอง `policy == "E"` ถูกจริง (313 กอง) และกอง F/O **ไม่หลุด**เข้ามาใน cache ใหม่โดยไม่ตั้งใจ

---

## สรุป: ผลกระทบต่อแผนหลักถ้ายอมรับทั้ง 7 ข้อ

| # | จุด | กระทบ §ไหนของแผนหลัก | ระดับ |
|---|---|---|---|
| 1 | De-market ก่อน regress (excess return) | §3, §4, §5 (`style_factor.py`) | **สูง — เปลี่ยน methodology** |
| 2 | Derive blend weight จากข้อมูลจริง | §3 | กลาง |
| 3 | Recalibrate `SECONDARY_BAND_PCT` | §4, §6 | กลาง |
| 4 | Set R² expectation ใน UI | §5 (`pages/6_...py`) | ต่ำ (UI/copy) |
| 5 | แยก cache ไฟล์ style | §5 (`data_access.py`) | กลาง (ตัดสินใจล่วงหน้า กันงานซ้ำ) |
| 6 | อ่าน `matching.py` เป็น step แรก | §5, §6 (ลำดับงาน) | ต่ำ (แค่จัดลำดับ) |
| 7 | เพิ่ม unit test 2 จุด | §6 | ต่ำ |

ข้อ 1 เป็นจุดเดียวที่เปลี่ยนตัวเลขที่ได้จริง (ไม่ใช่แค่ parameter/ลำดับงาน) — ควรตัดสินใจเรื่องนี้ก่อนอื่น ส่วนข้อ 2-7 ทำได้ระหว่าง implement โดยไม่ต้องหยุดรอ
