# รีวิวผล S012 + S013 รอบ 2 (หลังแก้ตาม `S012_result_review.md` · BRIEF 118)

ผู้รีวิว: factor-reviewer · 2026-10-24 · รีวิวเฉพาะส่วนที่แก้
- **ขอบเขต:**
  - S1 · S2 · m1–m9
  - การรันใหม่ (run.py `c15ba054…` · l1eo `4c828e3b…`)
  - `decisions_post_review.md` · `analyst_notes.md` · `addendum_s1.py` / `.csv` / `_check.json`
  - `paired_lens_E.csv` · `s2_shapley_before_after.csv` · `eval_clusters.csv`
  - `v1_before_S2/` · `run_v1.py` · `l1eo_v1_before_S2.py` · `test_eo_06b`
- **อ่านแล้ว:**
  - BRIEF 118
  - decisions_post_review ครบ · analyst_notes ครบ
  - `diff` ของ l1eo v1 → ปัจจุบัน (ทั้งหมด) · `diff` ของ run_v1.py → run.py (ทั้งหมด 194 บรรทัด)
  - results.md: §1 / §8 / §9 / §10 / §12 / §13
  - test_eo_06b
- **สคริปต์ของ reviewer** (อ่านอย่างเดียว):
  - `scratch/factor-reviewer_s012_r2_check.py` → `.json` (Shapley คู่ Dimson ด้วย numpy ล้วน · อ่าน parquet ตรง · ต่อรหัสเอง)
  - repro ลง `scratch/factor-reviewer_s012_repro_r2/`
  - pytest ที่ reviewer รันเอง (`S012_REAL=1`): **177 passed**

## สรุป

แก้ครบทุกข้อและถูกต้อง · คำตัดสินที่ล็อกไม่เปลี่ยน · ไม่พบปัญหาระดับร้ายแรง / สำคัญใหม่ · มีข้อสังเกตเล็ก n1–n4 ที่ไม่ขวาง PASS

---

## การตรวจ

**1. ลำดับเวลา — ผ่าน**

birth / mtime ของไฟล์ (macOS):
- 10:08:31 สำรอง v1 → `v1_before_S2/` (15 ไฟล์ + `pre_files_sha.txt`) · `run_v1.py` · log v1
- 10:08:40 `l1eo_v1_before_S2.py`
- 10:08:57 แก้ l1eo / test
- 10:11:48 แก้ run.py
- 10:12:00–43 smoke `--sim` ลง `scratch/factor-analyst_sim_out2` (log `sim=True`)
- **10:13:17 `decisions_post_review.md` เกิด**
- 10:13:24 phase pre จริง → 10:16:34–10:17:12 phase full จริง
- pytest 10:15:59 · repro 10:18:52

สรุปลำดับ:
- decisions_post_review เขียน**ก่อน**รันข้อมูลจริงรอบแก้
- เขียนหลังแก้โค้ด ซึ่งยอมรับได้ เพราะการแก้ถูกกำหนดไว้ล่วงหน้าโดยรีวิวผลและ BRIEF 118 และผล v1 เป็นที่รู้อยู่แล้ว
- `decisions_pre_run.md` ไม่ถูกแตะ (sha `874bcf02…` เท่ารอบแรก)

**2. ไฟล์ phase pre และคำตัดสินที่ล็อก — ไม่เปลี่ยน**
- ไฟล์ phase pre 15/15 sha เท่า `v1_before_S2/pre_files_sha.txt` ทุกบิต (reviewer hash เอง) → การคัดเลือกไม่กระทบ
- `diff` ของ run.py เริ่มที่บรรทัด 490 → ส่วน phase pre (≤ บรรทัด ~300) ไม่ถูกแก้
- คำตัดสินที่ล็อก (reviewer เทียบ v1 กับปัจจุบันเอง):
  - `qe_verdicts.csv`: verdict / diff / CI เท่าเดิม · เปลี่ยนแค่ข้อความ extra ของ Q-E4 (m4)
  - `criteria_8_1.csv`: ทุกคอลัมน์ C1–C5 เท่าเดิม · `passed_8_1` เปลี่ยนเฉพาะ M1 ✗ → "N/A (ตัวเทียบ)" (m5)
  - `o_verdicts.csv`: `rule_8_3` / `descriptive` เท่าเดิม · เพิ่ม `direction_note` / `flag_n` / `n_fund_positive_vs_3a`
  - `factor_verdicts.csv`: verdict เท่าเดิม · เพิ่ม `note` (CMA "ผ่านแบบขอบ")
- `factor_report_E/O.csv`:
  - คอลัมน์ตัวเลขที่ไม่ใช่ Shapley เท่าเดิมทุกคอลัมน์
  - เปลี่ยนเฉพาะ `shap_*` และเพิ่ม `nonpc_*`
- `fund_level_E.csv` sha เท่ารอบแรก (`10574ff1…`)
- รายการไฟล์ที่เปลี่ยนตาม `run_meta.output_sha256` ตรงกับที่ analyst ประกาศ (13 ไฟล์ + ไฟล์ใหม่ 3)

**3. S2 — แก้ถูกต้อง**
- diff ของ l1eo มีแค่ 2 จุด:
  - `shapley_table` ส่ง `rg.lag_stack(b.reshape(-1, 1))` ทั้ง `shapley_r2` และ `shapley_oos`
  - เลนส์ชื่อ `nonpc_*` (m6)
- reviewer คำนวณ Shapley คู่ Dimson เองด้วย numpy (exact 2^K) บน EVAL ทั้งหมด:
  - E-X1 160 กอง: |Δφ| สูงสุดเทียบไฟล์ใหม่ **5.6e-16** · Σφ = R² ของ `fund_level_E` (E-X1) ต่างสูงสุด **2.8e-16**
  - E-X2 112 กองที่มี factor กลุ่ม: |Δφ| **6.7e-16**
  - O-X ทอง / REIT 12 กอง: |Δφ| **5.6e-16**
- median share ใน `s2_shapley_before_after.csv` และความคาดหมายข้อ 7 ตรงกับค่าที่ reviewer รายงานในรอบแรก (MKT 0.508 · e_VIETNAM 0.843 · e_CHINAg 0.776 · e_IT 0.022 · CMA 0.305)
- `test_eo_06b` ตรวจเส้นทางจริง Model → `shapley_table` → Σφ = R² ของ `fit_model` (1e-10) และจำนวนผู้เล่น = K (+1) ไม่ใช่ 2K → กันบั๊กเดิมได้

**4. S1 — แก้ครบ**
- `paired_lens_E.csv` (10 แถว: Q-E1 / Q-E2 × 5 ชุดย่อย) ตรงกับค่าที่ reviewer คำนวณในรอบแรก:
  - Q-E1 median รายกอง −0.0268 · แย่ลง 56.9%
  - มี / ไม่มี factor กลุ่ม +0.043 / −0.105
  - Q-E2 +0.0275 · ดีขึ้น 69.4%
  - CI ต่างกันในทศนิยมตำแหน่งที่ 3 เพราะ RNG
- `addendum_s1.py` สร้างซ้ำจาก `fund_level_E.csv` + `eval_clusters.csv` ได้ตรงตาราง run.py (1.5e-16) และบันทึก sha ของ run.py / สคริปต์ / l1eo / fund_level
- ถ้อยคำ §1 / §9 / §13:
  - "แทนได้ / ดีกว่า **ตามเกณฑ์ที่ล็อก**"
  - "CI ล่าง −0.046 ต่ำกว่าขอบ → ยืนยัน non-inferiority ไม่ได้"
  - "'ไม่พบความต่าง' ≠ 'เทียบเท่า'"
  - มุมจับคู่ไม่ถึง 0.05
  - ประโยคเดิม "ไม่ต่างจาก PCA … อย่างมีหลักฐาน" ถูกลบแล้ว (grep ไม่พบ)

**5. m1–m9 — ทำครบ**

| ข้อ | สิ่งที่แก้ | ผลตรวจ |
|---|---|---|
| m1 | คอลัมน์ `sub_ok` · ข้อ 15 แบบ universal → "ไม่ตรง" · ข้อ 3 ตาราง = notes (บางส่วน 4/6) · ยอดใหม่ ตรง 7 · บางส่วน 8 · ไม่ตรง 2 · "ส่วนใหญ่ไม่ตรง: 7, 9, 10, 12" | เปลี่ยนสถานะเฉพาะข้อ 15 ✓ |
| m2 | `div_class` ใน `fund_level_O` · `units_rejected_div_class` = IREITG; PRINCIPAL GREITs · บรรทัดข้อจำกัด §10 | ✓ |
| m3 | `direction_note` "ดีกว่า ③a เล็กน้อย ไม่ถึงเกณฑ์" (BRIEF 118(2)) · ตาราง Flag เทียบ β(FX) + ข้อความว่าตีความ hedge ตาม Flag ไม่ได้ | ✓ |
| m4 | E-H = 6 factor / 13 พารามิเตอร์ (เพดาน 9 / 19) | ✓ |
| m5 | M1 = N/A · `PASS81` ใช้ `is True` | Q-E1 ยังอ่านค่า E-X2 = True ถูก ✓ |
| m6 | เลนส์ `nonpc_*` (ชุดอ้างอิง `REF_BASE` ไม่มี PC ของ ①a / ①c) · E-H RPC3 = "ไม่มีชื่อ" (KF_DEV_SMB −0.35) · C5 ไม่เปลี่ยน | ✓ |
| m7 | CMA "ผ่านแบบขอบ" + ตารางตัวชี้ | ✓ |
| m8 | `n_tried` เพิ่ม 5 แถวภาคผนวก (A1 1 · A3 5 + 2 · A5 5 · O-PCA / O-tilt 4) | ✓ |
| m9 | `flag_n` REIT "n = 5 · แกว่งง่าย (พลิก 1 กองเหลือ 3/5 < 2/3)" | ✓ |

**6. repro / regression / pytest ที่ reviewer ทำเอง — ผ่าน**
- repro: run.py pre + full + `addendum_s1.py --out` ลง `scratch/factor-reviewer_s012_repro_r2/`
  - **54 ไฟล์ sha เท่า `runs/S012/` ทุกบิต** (รวม results.md ทั้งไฟล์ · `paired_lens_E` · `s2_shapley_before_after` · `addendum_s1.csv`) · ไม่มีไฟล์เกิน
  - addendum check = true (1.5e-16)
- regression: lib เดิม 15 ไฟล์ยังเท่ากับ `runs/S010` · S003 / S006 ไม่ import l1eo
  - ผล regression S003 ที่ reviewer รันเองในรอบแรก (22 ไฟล์ตรง) ยังใช้ได้
  - `regression_S003_S006.json` all_pass = true
- pytest (`S012_REAL=1`): 177 passed (176 เดิม + `test_eo_06b`)
- trials.csv mtime 10-20 10:23 · quant_team 10-15 → ไม่ถูกแตะ · ไม่มีคอลัมน์ AQR ในการรัน

---

## ข้อสังเกตเล็ก (ไม่ขวาง PASS · ทำพร้อม L1EO_summary ได้)

**n1 — มีการรัน phase full จริงก่อนรอบที่ log บันทึก 1 ครั้ง**
- หลักฐาน: `paired_lens_E.csv` · `s2_shapley_before_after.csv` · `eval_clusters.csv` เกิด 10:14:03–05 ขณะที่ `run.log` บันทึกรอบ 10:16:34
- run.py (10:11:48) และ l1eo (10:08:57) ไม่ถูกแก้ระหว่างสองรอบ → ผลเหมือนกัน ยกเว้น results.md ที่ฝัง `analyst_notes.md` (เขียน 10:16:33)
- ไม่กระทบผล แต่ตามบทเรียนข้อ 66 ให้เพิ่ม 1 บรรทัดใน §12

**n2 — `flag_n` ของทองเขียน "n = 7 · แกว่งง่าย" ทั้งที่การคำนวณของตัวเองได้ 5/7 ≥ 2/3**
- คำตัดสินทองขึ้นกับ median Δ < 0.05 ไม่ใช่สัดส่วนกอง
- summary ควรเขียนทองเป็น "n = 7 (N น้อย)" ไม่ใช่ "แกว่งง่าย"

**n3 — `test_eo_06b` assertion สุดท้ายเทียบ R² ต่างโมเดลกัน**
- lag 0 ของ X1 ถูกเทียบกับ R² Dimson ของแถว x2 ซึ่งมี factor กลุ่ม → ไม่ใช่ตัวกันถอยกลับที่สะอาด
- assertion ก่อนหน้า (Σφ = R² ของ fit_model) กันบั๊กได้พออยู่แล้ว · แก้ตอนแก้ lib ครั้งถัดไปได้

**n4 — ข้อมูลใหม่จากตาราง paired lens ที่ summary ควรใช้**
- ในชุด PCA(97) มุมจับคู่ Q-E1 = −0.035 (CI −0.069…−0.003 ไม่คร่อม 0) · นอกชุด = +0.008 (CI −0.072…+0.028)
- → ส่วนหนึ่งของการที่ PCA ชนะรายกองมาจาก self-inclusion
- E-PCA-a1 PC3 "คล้าย KF_NA_HML" (0.58) มี corr ช่วง test แค่ 0.22 → ชื่อไม่ยืนนอกช่วง

---

## ส่งต่อ designer สำหรับ `reports/L1EO_summary.md` (อัปเดตจากรอบแรก)

ใช้รายการ 10 ข้อใน `S012_result_review.md` โดยแก้ / เพิ่มดังนี้:
1. **Shapley:** ใช้ตัวเลขฉบับคู่ Dimson ใน `shapley_*.csv` / `factor_report_*.csv` / `s2_shapley_before_after.csv` เท่านั้น · ห้ามใช้ `v1_before_S2/`
2. **Q-E1 / Q-E2:** ยกถ้อยคำจาก results.md §9 และตาราง `paired_lens_E.csv`
   - เพิ่ม n4: มุมจับคู่ในชุด PCA −0.035 เทียบนอกชุด +0.008 → self-inclusion
   - ทั้งหมดเป็นเลนส์บรรยายตาม BRIEF 118(1)
3. **ทอง:**
   - "ไม่ดีกว่าตามเกณฑ์ที่ล็อก · ดีกว่า ③a เล็กน้อย ไม่ถึงเกณฑ์ (+0.032 · 6/7 · ΔBIC −7.1)" ตาม BRIEF 118(2)
   - ป้าย "n = 7 (N น้อย)" (n2)
   - Flag ไม่สอดคล้องกับ β(FX)
   - ห้ามเขียน "ชุดกลไกใช้ไม่ได้กับทอง"
4. **REIT:** ดีกว่าตัวเทียบ +0.302 · n = 5 แกว่งง่าย · α ของ 2 ใน 3 กองที่ BH ปฏิเสธมาจาก class ปันผล
5. **ความคาดหมาย:** ตรง 7 · บางส่วน 8 · ไม่ตรง 2 · ส่วนใหญ่ไม่ตรง ข้อ 7, 9, 10, 12 · ไม่ใช่หลักฐานว่าเกณฑ์ดี
6. **ชื่อของ factor สถิติ:** ใช้เลนส์ `nonpc_*`
   - PC1 ≈ ตลาด (KF MKT 0.91) · PC2 ≈ จีน (0.79)
   - PC3 / RPC3 ไม่มีชื่อที่ยืนนอกช่วง
7. **ส่วนอื่นตามรอบแรก:** CMA ผ่านแบบขอบ · factor กลุ่ม 10/11 + ป้าย · ข้อจำกัดครบ · รายเดือนห้ามสรุปทิศ

## ต้องให้ผู้ใช้ตัดสินใจ (ตอนสรุป · ไม่ขวางรีวิวนี้)
1. ยืนยันเกณฑ์ข้อ 8 และนิยามผลต่างของ median ตามที่ session หลักใช้ค่าเริ่มต้นใน BRIEF 118(1)
   - ถ้าเปลี่ยนเป็นมุมจับคู่ = "เกณฑ์เปลี่ยนหลังเห็นผล" → รายงานทั้งสองชุด
   - Q-E2 จะเป็น "ไม่ดีกว่า"
2. ไฟล์ AQR: ลบ / ไม่ commit / คงไว้ (BRIEF 118(4))

VERDICT: PASS
