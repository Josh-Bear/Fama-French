# decisions_pre_run — S012 + S013 (เขียนก่อนรัน run.py บนข้อมูลจริงครั้งแรก · ก่อนคำนวณผลใดๆ)

เขียนโดย factor-analyst · วันที่ 2026-10-24 · spec = S012 + S013 (S013 ชนะเมื่อขัดกัน) · งานเชิงอธิบาย · ไม่นับ trial · **ไม่แตะ `trials.csv`**

**ลำดับที่ทำจริงก่อนไฟล์นี้:** (ก) เขียน `lib/l1eo.py` + `lib/tests/test_l1eo.py` และรัน test ด้วยข้อมูลจำลองเท่านั้น (ข) รัน regression S003 / S006 (ต้นฉบับเดิม · ไม่เกี่ยวกับผล S012) → `regression_S003_S006.json` (ค) smoke ของ `run.py` ด้วย `--sim --smoke` (ข้อมูลจำลอง · คอลัมน์/ดัชนีของ factor อ่านเพื่อรูปร่างเท่านั้น · ไม่ใช้ค่า) ลง scratch (ง) คำนวณ sha256 ของไฟล์ (การ hash ไม่อ่านค่าผลตอบแทน) · **ยังไม่ได้อ่านผลตอบแทนกองจริงเพื่อทำอะไรเลย** (ไม่มีการนับ notna ของ panel จริง ไม่มีการ fit จริง) · การตรวจรายชื่อชุดกองกับ `S013_pca_sets.csv` (ซึ่งต้องนับ notna ของ panel จริง) เป็นขั้นแรกของ phase pre ของ run.py และ**หยุดทันทีถ้าไม่ตรง** · ถ้าต้องแก้โค้ดหลังรันข้อมูลจริง → เปิดเผย diff ใน results.md

## 1. sha256 เต็มที่ตรวจแล้ว (S013 §4 · 21 ไฟล์ · `l1eo.check_pins()` ผ่าน ณ เวลาเขียน · run.py ตรวจซ้ำทุก phase และหยุดถ้าไม่ตรง)
| ไฟล์ | sha256 |
|---|---|
| data/panel_weekly.parquet | `95c16ee651d3a936788b7cb3c6372bbf5f1e84cb39daf5680343771dca24270b` |
| data/panel_monthly.parquet | `e8e8cb5d5f04fba9bb35558ef7c3d8195c656334119e56f82775cc1ae21ccaed` |
| data/factors_weekly.parquet | `115b87139d2bec0fd57a77a1593c46d36bb23f3f35f83236cdb07be642af47a8` |
| data/factors_monthly.parquet | `f7c4248b4fa889853024449e72ae8909cf1f8d3226a54eebc37448a2a485bb72` |
| data/factors_ext_weekly.parquet | `3105b6e7fe32ffd3648e8feac8dbd03a8db22b7e8eb245c5faf462b14da5e296` |
| data/factors_ext_monthly.parquet | `ce53d371ae847ee8d8dcd2d33a7b0f30f5db01bb993bef8599598e05af4db792` |
| data/factors_eo_weekly.parquet | `87b793508d83d2a4235eb07f1ff584cd32493375d5f73f8c6711f172f2a0bfca` |
| data/factors_eo_monthly.parquet | `c13c36e7dd2b039116131092b757160ae83460478829af3b7234afdd67bef82f` |
| data/manifest_eo.json | `281756a4787e4ade4b8474571e8c49a9dac4b11b995b21b74d9197334b052681` |
| data/aum_fam.parquet | `e442f6ae8f09ff01fb23a3b25aa89e2b98da8af9134143f0a873913e7ef2db46` |
| data/universe.csv | `fdfb7830df78ce032465ac9d8cddc2c98f9aa86cfa0f3925fdb83026aa3f7252` |
| data/dup_pairs.csv | `b1f0f0c745947fa70803a4f40526c0a1967c72925be985a2bedc1057d8b8aef3` |
| base_data/FundProfile.csv | `9516281426fc854c8f3a0833f119cad0ce581adb39450732e579084cb4cedfaf` |
| specs/S012_group_map.csv | `898a86867b3f832060f7620d039fd95338d24e1bb71f531d76bb58004223fceb` |
| specs/S013_pca_sets.csv | `175023c5cf978c550b40397e608523577e376dcf63d3c43cde38b33ef4770bbf` |
| runs/S003/factors_S003_weekly.parquet | `be3ceb2e34b0df1f1a3db27d59e1a103cf5f5a5ca38f2e87f7c812c1c53944ac` |
| runs/S005/primary_index.csv | `5a94ab9b498bb107600938d37f665c7263d9f0a5973460159c09ae83a799275c` |
| runs/S006/resid_B_coef.csv | `71af654fc789a24d79999d96d7149e05e75007ac6e8f83d33bd0355d292eef0b` |
| runs/S009/alpha_fund.csv | `7a2dea7a928cb529547e8edde8e1f0f31a7ab603bcffd69cd6f2ef6400302894` |
| runs/S003/run.py · runs/S006/run.py | `9f21e388…590f` · `5515b289…c760`→ เต็ม `5515b2893fe0188c9135fa7728dd45f091534f03754bf529609b244c03c4f760` (regression) |

lib เดิม 15 ไฟล์ = `runs/S010/run_meta.json` `lib_sha256` ทุกไฟล์ (ตรวจแล้ว) · ไฟล์ที่เพิ่ม = `l1eo.py` (`b1a8842a…364b` ณ ตอนเขียน) + `tests/test_l1eo.py` เท่านั้น · **regression** S003 (22 ไฟล์) / S006 (32 ไฟล์ · รันในต้นไม้ scratch ที่ lib ไม่มี l4/p2/l1eo เพราะ run.py ของ S006 assert รายชื่อ lib — วิธีเดียวกับ S010) sha256 ตรงทุกไฟล์ → `regression_S003_S006.json` all_pass = true

## 2. run.py
- `run.py` sha256 ณ ก่อนเริ่ม phase pre = `a691dcff5e4619536a46c9292504fba092cd98ca95a9faf4d9fb2b26717023c9` (ถ้าต่างตอนรันจริง run.py บันทึกเองใน `run_meta_pre.json` / `run_meta.json` และบรรทัดแรกของ log) · run.py เก็บสำเนา `run_pre.py` ตอนเริ่ม phase pre · phase full คำนวณไฟล์ selection ซ้ำแล้วต้องตรงทุกบิตกับ phase pre · ถ้า sha ต่างกันระหว่าง phase → diff ใน results.md (BRIEF 106)
- ลำดับเขียน (timestamp ใน `run_pre.log` / `run.log`): regression ผ่าน → decisions_pre_run (ไฟล์นี้) → units_splice → sets → group_map_check → sel_reps → placebo_E → stepwise_E (+ all_candidates) → group_factor_coef → pca_E → hybrid_E → (phase full) fit ทุกแถว → ไฟล์คะแนน

## 3. smoke / การเปลี่ยนแปลง
smoke ใช้**ข้อมูลจำลองเท่านั้น** (`--sim`) · ไม่รันข้อมูลจริงก่อนไฟล์นี้ · ถ้าแก้โค้ดหลังรันข้อมูลจริง → diff ใน results.md

## 4. ตารางต่อรหัส (S013 §2 · วัน NAV จาก `universe.csv` · ใช้ตารางตรงๆ ไม่ตัดสตริง)
| หน่วย | รหัสเก่า (NAV สุดท้าย) | รหัสใหม่ (NAV แรก) | สัปดาห์ที่ใช้รหัสใหม่ | zero_frac รหัสเก่า |
|---|---|---|---|---|
| I-GOLD* | I-GOLD (2023-11-29) | IGOLD-G (2023-11-30) | ≥ 2023-12-08 | 0.006536 |
| ES-GCG* | TMB-ES-GCG (2023-11-28) | ES-GCG-A (2023-11-29) | ≥ 2023-12-08 | 0.006536 |
| ES-GINNO* | TMB-ES-GINNO (2023-11-28) | ES-GINNO-A (2023-11-29) | ≥ 2023-12-08 | 0.006536 |
| ES-GINFRA* | TMBGINFRA (2023-11-28) | ES-GINFRA-A (2023-11-29) | ≥ 2023-12-08 | 0.006536 |

สัปดาห์ซ้อน 2023-12-08 ใช้**รหัสใหม่** (ค่า 0 ของรหัสเก่ามาจาก NAV ค้าง) · สัปดาห์ 2023-12-01 ของรหัสเก่าคงไว้ พร้อมป้าย (ญ) 'สัปดาห์ไม่เต็ม' · หลังต่อ train 155 / test 104 · รายเดือน: ใช้รหัสใหม่ถ้ามีค่า ไม่มีก็รหัสเก่า (`combine_first` · test พิสูจน์ว่าเท่ากับกติกาสัปดาห์) · M1: หน่วยต่อรหัสไม่มี primary → ①a + FX

## 5. ชุดกอง (ต้องตรงตาราง S013 §1 และ `S013_pca_sets.csv` **ทุกหน่วย** ไม่ใช่แค่จำนวน · ไม่ตรง → หยุดและอธิบาย)
E: SEL 163 · EVAL 160 · EVAL52 196 · STAB 141 · ตัดซ้ำ 199 · PCA balanced **97** · unbalanced 185 · O: 12 · 12 · 13 · 12 · 13 · 7 · 13 · n_weeks ของทุกหน่วย = แถวที่มีผลตอบแทนในช่วงหลัก ≤ 2025-12-26 · เสมอ → ตามตัวอักษร (`samples.dedup_keep`) · คู่ซ้ำแปลงเป็นหน่วยก่อน
**n1 (รีวิว S013) แก้ถ้อยคำ:** ข้อความใน S013 §1 ที่ว่า `universe.csv` `n_weeks` 'นับถึง 2026-07-31' และ 'ต่างจากระยะ 1' ผิดข้อเท็จจริง — `n_weeks` ของ universe นับในช่วงหลักและตรงกับ n_weeks_main ทุกหน่วยที่ไม่ใช่หน่วยต่อ (224/224 ตามรีวิว) · นิยามใหม่ต่างจากระยะ 1 เฉพาะหน่วยต่อ 4 หน่วย · ชุดกองไม่เปลี่ยน · ตัวเลข '96' ใน S012 อ่านเป็น 97

## 6. pool (ล็อก) · stepwise
แกน MKT = `MSCI_ACWI − RF_BOT` · pool 11 ตัวตามลำดับตัดสินเสมอ: e_CHINA · EMDM · TERM · SMB · HML · RMW · CMA · WML · JKP_EM_value · JKP_EM_momentum · FX · ช่องที่ 12 ว่าง (ห้ามเติมภายหลัง) · e_CHINA = residualize(China All − RF | MKT · train · lag 0 · เก็บค่าคงที่) · KF = `KF_DEV_*` (ทบรายวัน) · A1 pool 10: แทน KF 5 ตัวด้วย Momentum · Quality · Value · LowVol ของ `factors_weekly` (de-market)
ด่าน (ตามลำดับ · ตกด่านใด หยุดทั้งกระบวนการ): G1 |MKT + ที่เลือก| < 6 ก่อนเพิ่ม · G2 score_j* ≤ τ · G3 median ΔR²_pseudo > 0 · score = median ΔBIC ข้ามตัวแทน (**แถวร่วมของ M และ M + j** · m8 — fit M ใหม่บนแถวที่ design ของ M + j ครบ) · ΔBIC < 0 = ดีขึ้น

## 7. ตัวแทนกลุ่มกองอิสระ
`l2.fund_clusters` (corr ≥ 0.95 · single linkage · ผลตอบแทน train · min_overlap 52) บน SEL_E → ตัวแทน 1 หน่วยต่อกลุ่ม = จำนวนแถว train แบบ Dimson (ไม่นับแถวแรก) มากสุด · เสมอ → ตามตัวอักษร · บันทึก `sel_reps.csv` ก่อนขั้นถัดไป · กลุ่มอิสระของการประเมิน (CI · นับกลุ่ม) = fund_clusters บน EVAL_E

## 8. ด่าน G3
pseudo-train 2021-01-08 → 2022-06-24 · pseudo-test 2022-07-01 → 2023-12-29 · ตัวแทนที่มี < 52 แถวใน pseudo-train หรือ < 26 ใน pseudo-test ไม่นับ (รายงาน n = `g3_n`) · fit M และ M + j* บนแถวร่วม · β ของ e_CHINA (และ e_CHINA ที่ถูกเลือกไว้ก่อนหน้าใน M) ประมาณใหม่จาก pseudo-train ในด่านนี้ · ใน placebo: e_CHINA เลื่อนหลัง residualize และ G3 ไม่ residualize ซ้ำ (m8) · R²_pseudo = R²_oos ด้วย coef ตรึง

## 9. τ · ลำดับเขียน
τ₀ = −2 · placebo (`l2.circular_shift` s ∈ {26, 52} · MKT ไม่เลื่อน) ทุกด่านด้วย τ₀ · เลือก 0 ทั้งสอง → τ = −2 · เลือก ≥ 1 → τ = min(−2, min_s τ_s) (τ_s = score ดีที่สุดรอบแรก) + ป้ายปรับเกณฑ์ · เขียน `placebo_E.json` ก่อน `stepwise_E.csv`

## 10. CHINA → e_AH
ถ้า e_CHINA ∈ E-X1 → I_CHINA = `MSCI_CHINA_A_SHARES − MSCI_CHINA_H_SHARES` (e_AH) · ตรวจ `l2.in_span` (China All ใน span ของ X1 และ A − H ไม่อยู่) บันทึก `group_factor_span.csv` · ไม่ใช่ → China All − RF · factor กลุ่มทุกตัว residualize บน E-X1 (train · lag 0 · เก็บค่าคงที่) · กลุ่ม < 5 หน่วยใน U_E ทั้งหมด (ฐานนับ BRIEF 115(2)) ไม่มี factor · ป้าย designer (TH · METAL · EM · FIN · CONSUMER · STYLE · GLOBAL) ไม่มี factor

## 11. แกน · ชุดอ้างอิง · พอร์ต GRS
- แกน 'ใส่เดี่ยว' (6.2): E = MKT (ทุก factor ของแถว E รวม PC/RPC/factor กลุ่ม) · ทอง = GOLD_XS · REIT = MKT · ตัวที่เป็นแกนรายงานแค่ (i) · Δ = (ii) − แกนเดี่ยว
- ชุดอ้างอิงชื่อ I_EO = `external.reference_set(F)` + EXT14 (`<ETF>_THB − RF`) + คอลัมน์ที่ขึ้นต้น KF_ / JKP_ / GLD_ / VNQ / DTWEX ของ EO (KF_RF ติดมาด้วย — เป็นอัตราไม่ใช่ factor) + PC ของ ①a / ①c (ตัวเองไม่อยู่ในชุดอ้างอิงของตัวเอง) · **ไม่มีคอลัมน์ AQR** · ตั้งชื่อ (interpret) เฉพาะ factor ที่ไม่มีนิยามตรง (PC · RPC · PC ของ ①a/①c) · factor ภายนอก = นิยามตรง + max|corr| กับ PC ของ ①a · ≥ 0.7 '≈' ต้อง corr test ≥ 0.6 มิฉะนั้น '≈ (ไม่ยืนนอกช่วง)'
- GRS 12 พอร์ต: กลุ่มชื่อที่มี ≥ 5 หน่วย EVAL: CHINA · HEALTH · ASIA · TECH · EUROPE · INNOV · USA · JAPAN · VIETNAM · GLOBAL · NONE + OTHER · สมาชิก ≥ 3 ต่อสัปดาห์ (ตัดสัปดาห์) · ช่วง test เป็นหลัก · train รอง · เฉพาะแถว factor ร่วม · O: 2 พอร์ต EW (ทอง 7 · REIT 6) แยก GRS N = 1 ต่อพอร์ตด้วยชุด factor ของแถว (บรรยาย)

## 12. bootstrap · PY · placebo
cluster_bootstrap 2,000 รอบ seed 20261015 (สุ่มกลุ่มอิสระทั้งก้อนบน EVAL_E · ส่วนต่างจับคู่ใช้ชุดสุ่มเดียวกัน · ส่วนต่าง = ผลต่างของ median R²_oos) · PY null bootstrap B 999 block 4 seed 20261015 (PY ฉบับต้นฉบับ · เฉพาะกองครบทุกแถวในหน้าต่าง · แถว factor ร่วม · train และ test) · placebo ของข้อ 6.5: เลื่อน 26/52 ใน train · β/t = หน้าต่าง train (m1) · BH 10% ภายใน factor · สัดส่วน p < 0.05 > 8% → ป้าย 'นับตรงไม่ได้' (ย่อกฎ 3 ขั้นข้อ 37 · m14 ก)

## 13. ค่าเกณฑ์ที่ล็อก (BRIEF 115(4) · คัดลอกตัวเลข) + คำตัดสินบรรยายทอง (S013 §3 · BRIEF 116)
8.1: C1 median R²_oos ≥ 0.9 × สูงสุดของทุกแถว E (รวม ①a ①c ③a M1) · C2 gap (R²train − R²oos) ≤ 0.15 · C3 mean r ดิบ H1/H2 (STAB_E) ≥ 0.6 · C4 median ΔBIC ≤ 0 (E-X1 vs E-X0 · E-H vs E-X1 · E-X2 vs E-X1 บนกองที่มี factor กลุ่ม · แถวอื่น = N/A) · C5 factor ทุกตัวมีชื่อ (|corr| ≥ 0.5) หรือนิยามตรง (E-X0 = MKT นิยามตรง) · ผ่านทุกข้อ
8.2: Q-E1 'แทนได้' ≥ −0.03 และ E-X2 เข้ารอบ · 'ใกล้' −0.06…−0.03 (รวมกรณี ≥ −0.03 แต่ E-X2 ไม่เข้ารอบ — กรณีขอบที่ spec ไม่ระบุ · ตัดสินตามนี้ล่วงหน้า) · 'แทนไม่ได้' < −0.06 · Q-E2 'ดีกว่า' ≥ +0.05 และขอบล่าง CI > 0 · Q-E3 'ดีขึ้น' ขอบล่าง CI > 0 · Q-E4 'มี' k_res ≥ 1 และ ΔR²_oos ≥ 0.02 และ ΔBIC ≤ 0
8.3: factor ร่วม 'ยืนยันนอกช่วง' drop-one median ΔR²_oos > 0 และ VIF Dimson < 5 · 'สำคัญ' = + ≥ 0.005 + β มีนัย (BH) ≥ 7 กลุ่มอิสระและ ≥ 7 กอง + placebo ≤ 8% · factor กลุ่ม 'มี' median drop-one ΔR²_oos ≥ 0.02 และ median ΔBIC ≤ 0 และ VIF Dimson ต่อกอง < 5 · ผ่าน 1 ใน 2 ข้อแรก 'บางส่วน' · EVAL < 5 'n เล็ก' · EVAL 5–7 'แกว่งง่าย' · pseudo-OOS รายงานคู่ (diagnostic) · O: 'ดีกว่าตัวเทียบ' = median ΔR²_oos เทียบตัวที่ median R²_oos สูงสุดใน (①a ①c ③a) ของกลุ่มนั้น ≥ +0.05 และบวก ≥ 2/3 ของกอง (คำนวณบน EVAL_O 12 · ตารางรายกองบน EVAL52_O 13)
**ทอง (S013 §3):** 'เทียบเท่า ③a' เมื่อ |median ΔR²_oos(O-X − ③a)| < 0.02 และ median ΔBIC ≤ 0 · ตาราง 3 ตาราง (T1 vs ③a · T2 vs ตัวดีสุดของ (①a,①c) · T3 vs O-X′ แยก Flag N/Y) · ห้ามเขียน 'ชุดกลไกใช้ไม่ได้กับทอง' จากผล 'ไม่ดีกว่า ③a' · คำพ้อง / CONSUMER ตาม BRIEF 115(6) · ค่าเริ่มต้นของข้อเปิดที่ใช้จริง: คงคำพ้อง · CONSUMER ไม่มี factor (ไม่มีข้อเปิดเหลือ)

## 14. กรณีขอบ
กองที่ fit ไม่ได้ (น้อยกว่า min_obs 104 train / 52 test ตามชุด) → ไม่อยู่ในชุดนั้น · fit ด้วย min_obs 52 บน EVAL52 แล้วคะแนนหลักบน EVAL (≥ 104/≥ 52) · ED คืน None → ไม่นับใน combine_k · k_res = 0 → E-H = E-X1 · E-PCA-a2 NaN ที่แถวที่หน่วยใน Λ มี < ครึ่ง → แถวนั้นตก · ΔBIC/drop-one ใช้แถวร่วมของแถว full

## 15. ป้ายภาคผนวก / what-if ฝั่ง 'ผ่าน'
'ข้อมูลชุดเดียวกัน ไม่ใช่หลักฐานอิสระ' (ข้อ 103 n1) ติดทุกผลภาคผนวก A1 / A3 / A4 / O-tilt / O-PCA

## 16. สถานะ Terms of Use ของ AQR (m12 · n2)
NOTES.md บันทึกแค่ 'ไม่มีหน้ายอมรับเงื่อนไข' ตอนดาวน์โหลด · session หลักอ่าน https://www.aqr.com/Terms-of-Use (as of Dec 2023): ห้าม reproduce/copy/distribute/publish ข้อมูลจากเว็บไซต์โดยไม่ได้รับอนุญาตเป็นลายลักษณ์อักษร → **ถือว่าเงื่อนไข BRIEF 113 ไม่ครบ · ภาคผนวก A2 (AQR) = N/A** (BRIEF 117) · ไม่ใช้คอลัมน์ AQR ในการรัน · เรื่องลบ/ไม่ commit ไฟล์ AQR ให้ผู้ใช้ตัดสินตอนสรุป

## 17. แถวร่วมของ ΔBIC / G3 และการเลื่อน placebo หลัง residualize (m8)
ตามข้อ 6 และ 8 ข้างบน

## 18. C3 ของ E-X2 / E-H · รายเดือน (m5 · m3)
C3: E-X2 = เฉลี่ย r ของ factor ร่วม (STAB_E) + factor กลุ่มที่มี ≥ 10 สมาชิก STAB (คาด CHINA · HC · ASIA · IT — ของ reviewer ไม่ได้ตรวจซ้ำเอง) · E-H รวม RPC · E-PCA ทุก PC · รายเดือน: EVAL รายเดือน = ≥ 24 เดือน train · ≥ 12 เดือน test · E-PCA รายเดือน = Λ จาก train รายสัปดาห์ × ผลตอบแทนรายเดือน ÷ σ รายเดือนช่วง train · ①a / ①c รายเดือน = N/A · KF รายเดือน = `KFM_DEV_*` · L = 3 · ไม่มี null รองรับ

## 19. ทางเลือกการ implement ที่ spec ไม่ระบุละเอียด (ตัดสินล่วงหน้า · ไม่เปลี่ยนหลังเห็นผล)
- fit ทุกแถวบน EVAL52 (min_obs 52) · คะแนนหลัก/CI/คำตัดสินบน EVAL · ชุดย่อย A5 (EVAL ตัดซ้ำ · ตัวแทนกลุ่มอิสระ · ใน/นอก PCA 97 ที่ m6) รายงานคู่
- Shapley R² ผู้เล่นต่อกอง = factor ของกองนั้น (E-X2: X1 + e_g) · v(S) บนแถว train ที่ factor ครบ · Shapley ของ R²_oos เป็นภาคผนวก (ติดลบได้)
- factor_report ของ E-X2 รายงาน Shapley/β มีนัยของ factor ร่วมด้วย แต่ตัวชี้อื่นของ factor ร่วมดูที่แถว E-X1 · M1 ไม่มี factor report
- ความเสถียร: H1 (Dimson) min 104 · H2 min 104 · rolling 104 step 4 (`l2.rolling_betas` default) · corr หน้าต่างแรก vs สุดท้ายเป็นตัวหลัก
- lead diagnostic เฉพาะ factor ที่ทบจากรายวัน: SMB/HML/RMW/CMA/WML/JKP (E-X1 ถ้าถูกเลือก) · GOLD_XS/REIT_e (O) · แถว train ที่ t+1 อยู่ใน train
- O-X: ทอง (GOLD_XS, FX) · REIT (MKT, REIT_e, FX, TERM) fit แยกกลุ่ม · O-PCA em_pca k = 2 บน 13 หน่วย · O-tilt รายกอง
- `n_tried.csv`: ตามรายการ S013 m2 (นับรายการ ไม่ใช่ trial)
- ไม่ commit/ลบไฟล์ใดๆ ของผู้ใช้
