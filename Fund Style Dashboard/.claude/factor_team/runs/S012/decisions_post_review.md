# decisions_post_review — แก้ตามรีวิวผล S012 (REVISE · BRIEF 118) · เขียนก่อนรัน phase pre/full รอบใหม่

เขียนโดย factor-analyst · 2026-10-24 · ไม่นับ trial · ไม่แตะ `trials.csv` · ไม่ใช้ AQR · เกณฑ์ข้อ 8 / ค่าที่ล็อกใน `decisions_pre_run.md` **ไม่เปลี่ยน** (คำตัดสินทุกข้อต้องเท่าเดิม)

**สถานะก่อนแก้ (v1):** run.py sha `a691dcff5e4619536a46c9292504fba092cd98ca95a9faf4d9fb2b26717023c9` (เก็บ `run_v1.py` · `run_pre_v1.log` · `run_v1.log`) · l1eo.py sha `b1a8842aaa8f62721e788fdd68fea5bcdba151dc235aae458de8af1d2497364b` (เก็บ `l1eo_v1_before_S2.py`) · ผล v1 เก็บ `v1_before_S2/` (shapley · factor_report · expectations · results.md ฯลฯ) · sha ไฟล์ phase pre ของ v1: `v1_before_S2/pre_files_sha.txt` (15 ไฟล์)

| ข้อ | การแก้ | ผลที่คาด |
|---|---|---|
| S1 | เพิ่ม `paired_lens_E.csv` ใน run.py + `addendum_s1.py` (สร้างซ้ำจาก `fund_level_E.csv` + `eval_clusters.csv` · บันทึก sha ของ run.py/สคริปต์) · แก้ถ้อยคำ §9/§13: Q-E1 'แทนได้ตามเกณฑ์ที่ล็อก' + CI ล่าง < ขอบ → ยืนยัน non-inferiority ไม่ได้ + มุมจับคู่ + 'ไม่พบความต่าง ≠ เทียบเท่า' · Q-E2 'ดีกว่าตามเกณฑ์ที่ล็อก' + มุมจับคู่ไม่ถึง 0.05 | คำตัดสินที่ล็อกไม่เปลี่ยน (BRIEF 118(1)) |
| S2 | `l1eo.shapley_table` ส่ง `rg.lag_stack` ต่อผู้เล่น (คู่ Dimson lag 0 + lag 1 = ผู้เล่นเดียว) ทั้ง `shapley_r2` และ `shapley_oos` · test ใหม่ `test_eo_06b` (Model.players → shapley_table → Σφ = R² ของ `fit_model` บนแถวเดียวกัน 1e-10 · ทั้งแถวร่วมและแถวมี factor กลุ่มรายกอง) | ไฟล์ phase pre เท่าเดิมทุกบิต · เปลี่ยนเฉพาะ shapley_E/O · factor_report (คอลัมน์ Shapley) · ข้อความข้อ 7 ของความคาดหมาย · results.md |
| m1 | `expectations_vs_results.csv` เพิ่ม `sub_ok` (ส่วนย่อยที่ตรง x/y) · ข้ออ้างแบบ 'ทุกแถว' (ข้อ 15) ตัดสินแบบ universal · รายการ 'ส่วนใหญ่ไม่ตรง' (sub_ok < ครึ่ง) · แก้ข้อ 3 ให้ตรงกัน (ตาราง = §13) | สถานะข้อ 15 เปลี่ยนจาก 'บางส่วน' เป็น 'ไม่ตรง' (ตามตัวอักษรของข้ออ้าง) |
| m2 | `fund_level_O.csv` เพิ่ม `div_class` · ตาราง §5 + `bh_alpha_O.csv` เพิ่มรายชื่อ class ปันผลที่ BH ปฏิเสธ · เพิ่มบรรทัดข้อจำกัด 'ปันผล' | – |
| m3 | ทองตาม BRIEF 118(2): Δ ระหว่าง +0.02 ถึง +0.05 → 'ดีกว่า ③a เล็กน้อย ไม่ถึงเกณฑ์' (คอลัมน์ `direction_note` · ไม่ตั้งคำตัดสินใหม่) · ตาราง FX Risk Flag เทียบ β(FX) + ข้อความว่าตีความ hedge ตาม Flag ไม่ได้ | – |
| m4 | แก้ถ้อยคำ E-H: K จริง (ไม่ใช่ 9 ตัว/19 พารามิเตอร์ — เป็นเพดานของ spec) | – |
| m5 | `criteria_8_1.csv` M1 `passed_8_1` = 'N/A (ตัวเทียบ · ไม่มี factor report)' | – |
| m6 | `factor_report` เพิ่มคอลัมน์ `nonpc_*` (ชื่อจากชุดอ้างอิงที่ไม่ใช่ PC) + ตารางใน results · ไม่เปลี่ยน C5 | – |
| m7 | CMA เขียน 'ผ่านแบบขอบ' (`factor_verdicts.csv` คอลัมน์ note) + ตารางตัวชี้ประกอบ | – |
| m8 | `n_tried.csv` เพิ่มแถวภาคผนวก (A1 · A3 · A5 · O-PCA/O-tilt) | – |
| m9 | `o_verdicts.csv` คอลัมน์ `flag_n` (REIT n = 5 · แกว่งง่าย) | – |

**ข้อกำหนดการรันใหม่:** phase pre ต้องได้ไฟล์ 15 ไฟล์เท่า `pre_files_sha.txt` ทุกบิต (run.py ตรวจและรายงานใน results §12) · run.py phase pre = phase full (sha เท่ากัน) + สำเนา `run_pre.py` · repro ใหม่ตรงทุกบิต (รวม addendum) · pytest ทั้งหมดผ่าน (`S012_REAL=1`) · regression S003/S006 ไม่กระทบ (ไม่ import l1eo)
**หมายเหตุความโปร่งใส:** การรันใหม่นี้ทำหลังเห็นผล v1 และรีวิวผล · การแก้ทั้งหมดเป็นการแก้ตามข้อเสนอรีวิว/BRIEF 118 ไม่ใช่การเปลี่ยนเกณฑ์หรือรูปแบบ
