# PAGE7_MACRO_CHAIN_PLAN_REVIEW.md — Review แผนหน้า 7 เทียบกับระบบจริง

> เอกสารนี้เขียนแยกจาก `PAGE7_MACRO_CHAIN_PLAN.md` (ตาม convention เดียวกับ `PAGE6_STYLE_FACTOR_PLAN_REVIEW.md`) — **ไม่แก้ไฟล์แผนเดิม** เป็นแค่บันทึกจุดที่ต้องแก้ก่อน implement จริง ได้จากการอ่านโค้ดจริงเทียบกับสิ่งที่แผนเขียนไว้ (`analysis/matching.py`, `data_access.py`, `config.py`, `viz.py`, `app.py`, `page_common.py`, `pages/3_📊_Match_Strength.py`)

---

## สรุปจุดที่ต้องแก้ (เรียงตามความสำคัญ)

### 1. [Critical] Schema ของ `cache/macro_coefs.csv` ที่แผนเสนอไว้ผิด

แผน §6 เขียนว่า "schema เดียวกับ `coefs.csv` เดิมทุกประการ" (`FundCode, scope, index, elastic, lasso, ridge, is_primary, is_secondary`) แต่ precedent ที่ใกล้เคียงกว่า (`style_coefs.csv` — scope เสริมที่เพิ่งทำเหมือนกัน) ใช้แค่ **4 คอลัมน์**: `FundCode, index, scope, elastic` (ดู `data_access.py::build_style_pipeline` บรรทัด 254-262) — ไม่มี lasso/ridge/is_primary/is_secondary เลย primary/secondary คำนวณสดตอน query ผ่าน `classify_exposure()` แทนการ bake ไว้ในไฟล์

ยิ่งไปกว่านั้น แม้แต่ `is_primary`/`is_secondary` ใน `coefs.csv` เดิมเองก็**ไม่ใช่ band-based** (แค่ rank 1/rank 2 ตรงๆ จาก `match_exposure()` บรรทัด 144-146 ของ `matching.py`) คนละนิยามกับ `classify_exposure()` แบบ band-based ที่ query จริงใช้ — ถ้า bake ตามแผนเดิมจะยิ่งสร้างความไม่สอดคล้องเพิ่ม

**แก้**: ตัด lasso/ridge/is_primary/is_secondary ออก ใช้ 4-column schema แบบ `style_coefs.csv` (`FundCode, index, scope="macro", elastic`) — กระทบ §5 และ §6 ของแผนเดิม

---

### 2. [Simplification] `viz.py` ไม่ต้องเขียนฟังก์ชันใหม่ — reuse ได้ทันที

แผน §5 เขียนว่า "ยังไม่มีฟังก์ชัน bar chart แบบนี้ ต้องเขียนใหม่" — ไม่จริง `viz.match_strength_bar(coefs, fundcode, scope, model)` เป็น generic function (ต้องการแค่คอลัมน์ FundCode/scope/index/<model> ในตารางที่ส่งเข้ามา ไม่ผูกกับ scope ไหนเป็นพิเศษ) เรียกด้วย `scope="macro", model="elastic"` ได้ทันทีถ้า schema ตรงตามข้อ 1 — ไม่ต้องมี radio เลือก lasso/ridge เหมือนหน้า 3 ด้วยซ้ำ เพราะ Stage 2 เป็น matrix multiply ไม่ใช่การ fit โมเดล

**gap เล็กที่เจอในโค้ดจริงระหว่างตรวจ**: `match_strength_bar()` เรียก `classify_exposure()` โดย**ไม่ส่ง `band_pct`** (บรรทัด 136) จึงใช้ `config.SECONDARY_BAND_PCT` (0.30) ตายตัวเสมอ ไม่รองรับ scope-specific band แบบที่ `get_index_matches()` ทำได้ (ที่หน้า 6 ใช้ `STYLE_SECONDARY_BAND_PCT` ผ่าน parameter ได้) — ถ้าจะให้ `MACRO_SECONDARY_BAND_PCT` ต่างจาก 0.30 ต้องแก้ `match_strength_bar()` เพิ่ม parameter `band_pct: float | None = None` ส่งต่อเข้า `classify_exposure()` ด้วย (การแก้เล็ก แต่จำเป็นถ้าจะทำ empirical sweep ตามแผน)

**แก้**: ลบข้อความ "ต้องเขียนใหม่" ออกจาก §5, เพิ่มหมายเหตุ reuse `match_strength_bar()` + แก้เล็ก 1 บรรทัดเพิ่ม `band_pct` param

---

### 3. [Simplification] Stage 1 reuse `matching.nested_r2()` ได้ — ไม่ต้องมี `analysis/macro_chain.py`

`nested_r2(aligned, base_cols=[], extra_cols=MACRO_FACTOR_COLS)` เมื่อส่ง `base_cols=[]` จะได้ `X = column_stack([ones(n)])` (intercept-only) → `r2_base ≈ 0` และ `r2_full` = ผล OLS เต็ม 7 factor พอดี — ตรงกับสิ่งที่ Stage 1 ต้องการเป๊ะ (coefficient + R² ต่อ index) โดยไม่ต้องเขียน OLS ใหม่เอง แค่สร้าง aligned DataFrame ต่อ index หนึ่งตัว (rename return column เป็น `matching.FUND_COL`) แล้ววนเรียกทีละ 28 ครั้ง

แผน §5 เสนอ `analysis/macro_chain.py` (module ใหม่) สำหรับทั้ง Stage 1 และ Stage 2 — เกินความจำเป็น เพราะ Stage 1 reuse ของเดิมได้เกือบหมด และ precedent ของหน้า 6 (style) เองก็ไม่ได้เพิ่ม analysis module ใหม่เลย (reuse `matching.py` ทั้งหมด logic ใหม่อยู่ใน `data_access.py`/`data/style_factor.py`)

**แก้**: ตัด `analysis/macro_chain.py` ออกจาก §5 ทั้งหมด ย้าย Stage 1 loop (เรียก `nested_r2`) และ Stage 2 (matrix multiply) ไปเป็นฟังก์ชันธรรมดาใน `data_access.py` แทน (เหมือน `style_match_one`/`build_style_pipeline`) — สอดคล้องกับ convention เดิมของโปรเจกต์ และตรงกับหลัก "ไม่ทำให้ซับซ้อนขึ้นโดยไม่จำเป็น"

---

### 4. [Correctness] Stage 2 ต้อง join ด้วยชื่อ index ไม่ใช่ตำแหน่ง array

ตอน chain (`fund_coef_vector @ stage1_coef_matrix`) ต้อง pivot ทั้งสองฝั่งเป็น DataFrame ที่ index/column เป็น**ชื่อ index** (เช่น `pivot(index="FundCode", columns="index", values="elastic")` และ Stage 1 ผลลัพธ์ pivot เป็น `index × factor`) แล้วใช้ `.dot()`/join ของ pandas ที่ align ด้วย label อัตโนมัติ — ไม่ใช่ numpy array ดิบที่พึ่งพาลำดับคอลัมน์ตรงกันเองแบบที่ `stage1_macro_test.py` (สคริปต์ exploratory) ทำ ซึ่งใช้ได้เพราะควบคุม order เองในสคริปต์เดียว แต่พอแยกเป็น 2 stage คนละฟังก์ชัน/คนละไฟล์ ควรกัน silent bug นี้ไว้ตั้งแต่ต้น

**แก้**: เพิ่มหมายเหตุนี้ใน §4.2 ของแผนเดิม — ระบุชัดว่า Stage 2 implementation ต้อง join by label เสมอ ห้ามใช้ positional numpy array ข้าม stage

---

### 5. [Completeness] จุดที่ต้องแตะไฟล์เดิมแต่แผนไม่ได้พูดถึงเลย

- **`data_access.py`**: ต้องเพิ่ม `_load_macro_coefs()`/`get_macro_coefs()` — และพบ **gap ที่มีอยู่แล้วจริงในโค้ดปัจจุบัน**: `get_style_coefs()`/`_load_style_coefs()` ไม่มีอยู่เลย (`style_coefs.csv` ถูกเขียนโดย `build_style_pipeline` แต่ไม่เคยถูกอ่านกลับที่ไหนในแอปเลย) หน้า 6 เลยไม่มี bar chart ต่อกองแบบหน้า 3 — page 7 ต้องไม่พลาดจุดนี้ซ้ำ (และอาจคุ้มค่าจะแก้ style ที่ค้างไว้ด้วยพร้อมกันทีหลัง แต่นอก scope ของหน้า 7)
- **CLI block** (`if __name__ == "__main__":` ท้าย `data_access.py`) ต้องเพิ่ม subcommand `macro-download`/`macro` เหมือน `style-download`/`style`
- **`rebuild()`** ต้องเพิ่มเงื่อนไข `if os.path.exists(config.MACRO_FACTOR_CSV): build_macro_pipeline()` ต่อจาก style (บรรทัด 322-323 ของ `data_access.py`)
- **`app.py`** ต้องอัปเดต caption เมนู (บรรทัด 30-31) และข้อความ spinner ตอน rebuild (บรรทัด 57) ให้มี "🌐 Macro Chain" — แผนไม่ได้กล่าวถึง `app.py` เลยทั้งไฟล์

**แก้**: เพิ่มรายการทั้งหมดนี้เข้า checklist §7 ของแผนเดิม

---

## สิ่งที่แผนเดิมถูกต้องแล้ว (ไม่ต้องแก้)

- **Scope ครอบคลุมทุกกอง** — ยืนยันจาก `coefs.csv` จริงมี 368×28 แถวครบทุกกอง (6,624 country + 3,680 sector) ไม่มีกองไหนขาดหาย ไม่มี NaN ให้กังวลตอน pivot
- **แยกหน้า `pages/7` ต่างหาก แทนที่จะแก้ `pages/3`** — ถูกทางแล้ว เพราะ `pages/3` hardcode `scope = st.radio(..., ["country", "sector"])` และอ่านแค่ `data_access.get_coefs()` (coefs.csv เดิม) อยู่แล้ว ตรงกับที่หน้า 6 ก็แยกหน้าเหมือนกัน ไม่ได้ยัดเข้า pages/3
- **สูตรแปลงค่า (% return vs Δ)**, **ความถี่ monthly**, **7 factor final set**, **ผล Stage 1 validation (R², VIF)** — ทั้งหมดนี้ผ่านการรันจริงและตรวจสอบแล้วในเซสชันที่เขียนแผน ไม่มีข้อขัดแย้งกับระบบจริง

---

## Impact summary table

| Finding | กระทบ section ไหนของ `PAGE7_MACRO_CHAIN_PLAN.md` |
|---|---|
| 1. Schema `macro_coefs.csv` | §5 (โครงสร้างโค้ด), §6 (Cache design) |
| 2. `viz.py` reuse ได้ (+ band_pct gap) | §5 (โครงสร้างโค้ด) |
| 3. ตัด `analysis/macro_chain.py` ออก | §5 (โครงสร้างโค้ด) |
| 4. Join by name ไม่ใช่ position | §4.2 (Methodology — Stage 2) |
| 5. touch point ที่ขาด (data_access/CLI/rebuild/app.py) | §7 (Checklist) |
