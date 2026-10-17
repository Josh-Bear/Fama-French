# S006 — การตีความที่บันทึก **ก่อนรัน** (factor-analyst · ตามค่าชั่วคราว 59–61, 63 และรีวิว S006)

บันทึกก่อนเขียน/รัน `run.py` · ไม่เปลี่ยน spec · จุดกำกวม → เลือกแบบกระทบผลน้อยสุด

| # | เรื่อง | การตีความที่ใช้ |
|---|---|---|
| m1 / ข้อ 59 | เกณฑ์หยุด A1 | **หยุดเมื่อดัชนีทุกตัว VIF < 5** (f ห้ามตัด · f VIF ≥ 5 ได้ + ป้าย) = S_A หลัก · เดิน log ต่อ (phase `descriptive_all`) จนทุกคอลัมน์รวม f < 5 → รายงานชุด (ข) ใน `vif_elim_A.csv` + A-mem เชิงบรรยาย (ไม่ fit แถวคะแนนเพิ่ม) · เสมอ → ลำดับ `factor_groups.csv` (ตัดตัวที่อยู่ก่อน) |
| ข้อ 60 / m2 | pseudo-OOS ภายใน train | `drop_one` ซ้ำบน B-all เต็ม 6 ตัว: fit 2021-01-08→2022-06-24 วัด 2022-07-01→2023-12-29 (b̂ ของ e ยังประมาณด้วย train เต็ม → ป้าย "b̂ เห็นช่วง pseudo-test") · รายงานเป็น diagnostic ไม่ป้อนเกณฑ์ · Q1a ติด `evidence_independent = False` และ results.md เขียนว่า Q1a "ไม่ใช่หลักฐานนอกช่วงใหม่" |
| ข้อ 61 / m9 | TDEX | เพิ่ม `TDEX_THB − RF_BOT` ใน Z ของ elastic net (M28 28 + ETF 14 + TDEX 1 = 43 ตัว × lag 0/1 = 86 คอลัมน์) · diagnostic ไม่เพิ่มรูปแบบ |
| m4 | B-all′ | drop-one และ Q1a(i)(ii) ทำบน B-all เต็ม 6 ตัวเสมอ · Q1a(iii) ใช้ VIF ของ B-all เต็ม · B-all′ (ถ้าใช้ fallback) แทนเฉพาะแถวคะแนน R2/R7 |
| m5 | Wald B-all | ใช้กฎขั้น 2 ของ L2 (`placebo_rule.json`) + placebo วนเลื่อน e_j 26/52 ใน design B-all รายงาน frac p_adj < 0.05 คู่ (ราคาถูก) |
| m6 | ความเอียงของ argmax | รายงาน median(Δadj R² train − ΔR²_oos) ของ A-prim, C-prim, L2-1/L2-3 ใน `bias_argmax.csv` |
| m7 | Q3 baseline | สลับป้ายของแอป (country+sector ร่วมกัน) ข้ามกองภายใน policy · seed 20261015 · 1,000 รอบ · รายงานค่าเฉลี่ย + ช่วง 2.5–97.5% |
| m8 | VIF Dimson | `q1_verdict.csv` / `q2_flags.csv` ติดธง `vif_dimson_ge5_lag0_lt5` เมื่อ Dimson ≥ 5 แต่ lag 0 < 5 (บรรยาย) |
| m10 | rolling | ทุกแถว (รวมต่อกอง/อ้างอิง) · PRIM/e ติดป้าย · ค่าเฉลี่ยข้าม factor แยก "รวม PRIM" และ "ไม่รวม PRIM" · เพิ่ม corr หน้าต่างแรก vs สุดท้าย (ไม่ซ้อนกัน) · แถว ALL ติดป้าย "ปนความต่างของ β ระหว่าง policy — สูงเชิงกล" |
| m11 | ถ้อยคำ | ตาราง Q1 วาง Q1a (B) คู่ Q1a-A เสมอ · B-all ≡ f + ดัชนีดิบ P4 ทั้ง 6 (span ใหม่ที่ L2 ไม่เคยรัน) · อย่าอ้าง H3.4 กับแถว C |
| m12 | เลข test | test ใหม่เลื่อน +1 (29–45) + เพิ่ม 46 (`prim_from_pool`) 47 (`wald_B`) · `test_28_rolling_betas` เดิมรวมในชุดที่ต้องผ่าน · test 31 (span จริง) อยู่ใน `run.py` · test 45 (รัน 2 รอบ) = `repro_check` |
| m3 | select_C | log บันทึกอันดับที่ดีที่สุดของรอบที่หยุด (ทั้ง τ และ cap) |

## การตีความอื่นของ analyst (เลือกแบบกระทบน้อยสุด)
1. **B-prim / B-prim5 (แถวต่อกองที่ K = 4 หรือ 5):** `py_null_bootstrap` ใน lib เดิมต้องการ K คงที่ทุกกอง และห้ามแก้ lib เดิม → **PY / p_boot ของ R3, R5, R8, R10 = N/A (บันทึกเหตุ)** · GRS = N/A ตามเดิม · stability / rolling / monthly ทำด้วยการผสม fit (`l3.fit_perfund`, `rolling_perfund`) · PY ของ A-prim / C-prim / แถวอ้างอิง L2-1, L2-3 รันได้ (K คงที่ = ฐาน + 1)
2. **test 39 (elastic net จำลอง):** spec ตั้ง "median π ตัวอื่น ≤ 0.3" · ข้อมูลจำลองของ analyst ได้ ~0.49 (นับ "lag 0 หรือ lag 1" = 2 โอกาส ที่ λ* ตาม BIC) → ใช้ ≤ 0.6 · π ของตัวจริง ≥ 0.9 ตามเดิม · ไม่เปลี่ยนโค้ด
3. **Q2 ธง (4) r ดิบ:** ใช้ **median ข้าม factor ทุกตัวของแถว** (E · STAB) ≥ 0.6 (รายงาน min คู่)
4. **รายเดือน:** A-prim, B-prim, B-prim5 (ดัชนีดิบ — span เท่ากัน) + ฐาน · ตามวิธี S005
5. **C-prim pool** = P_C \ บล็อก C · เพิ่มเสมอ · คอลัมน์ ETF ส่วนขยายแยกในสัดส่วน
6. **GRS:** ใช้พอร์ต 17 เดิม (`runs/S003/grs_ports.csv` full) ตามวิธี S005 `run_grs` · แถว: B-all, B-all5 (หรือ B-all′ ถ้าใช้ fallback), C-blk + แถวอ้างอิงฐาน/③a
7. **regression S003:** ไฟล์ผลตรงทุกบิต · `run_meta.lib_sha256` ของ S003 เดิมต่างที่ `tests_stat.py` (lib ขยายหลัง S003 ก่อน S005 — ไม่กระทบผล) → ตรวจ lib เทียบ `runs/S005/run_meta.json` ตามข้อ 8.3(1)
8. **sklearn:** `enet_path(n_alphas=100)` ขึ้น FutureWarning ใน 1.9 (ความหมายเท่าเดิม) — ไม่เปลี่ยน
