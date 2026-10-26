# decisions_pre_run — S014 + S015 (PORT-FX ก · เขียนก่อนรัน run.py บนข้อมูลจริงครั้งแรก · ก่อนคำนวณผลใดๆ)

เขียนโดย factor-analyst · 2026-10-24 · spec = S014 + S015 (S015 ชนะเมื่อขัดกัน) · เชิงอธิบาย · ไม่นับ trial · **ไม่แตะ `trials.csv` ของทั้งสองทีม** · ใช้ factor ไฟล์ `factors_eo_noaqr_*` + `manifest_eo_noaqr.json` เท่านั้น (ไม่เรียก `l1eo.load_eo` · run.py / port.py ไม่มีสตริงต้องห้าม — `test_port_16`)

## 0. สิ่งที่ทำก่อนไฟล์นี้ (การเปิดเผย)
- เขียน `lib/port.py` + `lib/tests/test_port.py` และรัน test ด้วยข้อมูลจำลอง (ดัชนี/คอลัมน์ของ factor จริงเฉพาะรูปร่าง · ค่าจำลองทั้งหมด) · smoke ของ `run.py` ด้วย `--sim --smoke` ลง scratch · ไม่ได้รัน test `real`
- test โครงสร้าง (ไม่ใช้ผลตอบแทน): ตาราง mapping / ธง / ตารางไตรมาสเทียบ CSV ของ designer (ใช้ holdings · realized เฉพาะคอลัมน์ `t · portfolio · horizon · e · end · days · truncated` · FundProfile · universe · group_map)
- **เห็นค่าโดยไม่ได้ตั้งใจ (ตอนดูหัวไฟล์เพื่อดูรูปแบบคอลัมน์):** `m052_frontier_realized.csv` แถวแรก = MVP ไตรมาส 2022-03-31 `cost` 0.00175 · `ret` −0.0829 (ค่าเดียวกับที่ designer เปิดเผยใน S014) · `m052_frontier_weekly.csv` แถวแรก = ASP-VIET สัปดาห์ 2021-04-09 ผลตอบแทน +0.0117 · **ไม่ใช้ตัวเลขทั้งสองในการออกแบบ / เลือกใดๆ** · นอกนั้นไม่ได้เปิดค่าผลตอบแทนของ realized / weekly · ไม่ได้เปิดผลตอบแทนกองใน panel เพื่อทำอะไร
- n1 (รีวิว S015 · ไม่บังคับ): อ่าน `nav_history_db.csv` แบบอ่านอย่างเดียว (เฉพาะ FundCode · NAVDate · ไม่อ่านค่า NAV): **ONE-INDIAOPP-RA** NAVDate ตั้งแต่ 2023-12-15 → 2025-12-26 = 391 วัน: ศุกร์ 104 · อังคาร 100 · พุธ 95 · จันทร์ 88 · พฤหัส 4 (ช่วง 2024-Q4: ศุกร์ 14 จาก 52) → **มี NAV วันศุกร์** (ต่างจาก K-GOLD-A(A): ศุกร์ 6 จาก 366) → น่าจะไม่โดนช่องว่างศุกร์ · **ธงในตารางล็อก S015 ยังคง `na` / "ไม่ทราบ"** (ไม่เปลี่ยนตารางล็อก — test_port_14 ตรวจเทียบ CSV ของ designer) · บันทึกข้อสังเกตนี้ใน results.md เป็นข้อมูลประกอบ

## 1. sha256 เต็มที่ตรวจ (`port.check_pins()` ผ่าน ณ เวลาเขียน · run.py ตรวจซ้ำทุก phase · ไม่ตรง → หยุด)
| ไฟล์ | sha256 |
|---|---|
| data/panel_weekly.parquet | `95c16ee651d3a936788b7cb3c6372bbf5f1e84cb39daf5680343771dca24270b` |
| data/factors_weekly.parquet | `115b87139d2bec0fd57a77a1593c46d36bb23f3f35f83236cdb07be642af47a8` |
| data/factors_ext_weekly.parquet | `3105b6e7fe32ffd3648e8feac8dbd03a8db22b7e8eb245c5faf462b14da5e296` |
| data/factors_eo_noaqr_weekly.parquet | `715b4b252235b49b155c9d53554c00380d4d4430eb5c2c2e25751a3678570b3a` |
| data/manifest_eo_noaqr.json | `6be080b10ee236937e401e9ac1680671b31b279292e3e392e482e6de78f476c9` |
| data/universe.csv | `fdfb7830df78ce032465ac9d8cddc2c98f9aa86cfa0f3925fdb83026aa3f7252` |
| specs/S012_group_map.csv | `898a86867b3f832060f7620d039fd95338d24e1bb71f531d76bb58004223fceb` |
| base_data/FundProfile.csv | `9516281426fc854c8f3a0833f119cad0ce581adb39450732e579084cb4cedfaf` |
| base_data/reference/m052_frontier_holdings.csv | `b877510f177bc5a113b6587393dbdc543c63f033d9573a169172e403658e233d` |
| base_data/reference/m052_frontier_realized.csv | `488c38e5d0f749979ceaa49a682cd792e2710dbfffd8dd319427dda0ad1efe43` |
| base_data/reference/m052_frontier_weekly.csv (P-D) | `2e1ccdbae5a646e8ec633b786e560f827648c82ddc001d1c99fe04824c6e7600` |
| data/qa_friday_gap_E_units.csv | `1756f83765dc2fe41654ceb4f90b2bd6dae4ceb9be1e7c8df88b601dd78ef6e9` |
| data/QA_GOLD.md | `1955b2813e89a3d3c2b1b9bf244803a1a3f79124ef18695c69b7bdd490bc02e7` |
| specs/S014_PORT_M052_attribution.md | `e3864a965a88e5f181e9a242b69efa78de4701e883306946b33bff3fdbad9310` |
| specs/S015_PORT_addendum_to_S014.md | `f6b84aa4a147e66d7ba4f206d0ae684728b32c324cb7d12db45ff1c530a5145f` (ตรงค่าที่ reviewer บันทึก) |
| scratch/factor-designer_s015_quarters.csv · _holdings.csv | `d6ad3ac3…33dd` · `c8d3d66e…52db` (เต็มใน `port.PINS`) |
ไม่โหลด: `EXPORT_m052_curves.csv` (ตัดตาม m13) · `factors_eo_weekly/monthly.parquet` · `manifest_eo.json` · `cache/` · แถว > 2025-12-26
lib เดิม 16 ไฟล์ = `runs/S012/run_meta.json` `lib_sha256` ทุกไฟล์ (ตรวจแล้ว: รวม `l1eo.py` `4c828e3b…3170`) · ไฟล์ที่เพิ่ม = `lib/port.py` (`7005ca61…b2f2` ณ เวลาเขียน) + `lib/tests/test_port.py` เท่านั้น · ไม่ต้อง regression S003/S006/S012 (ไม่แตะ lib เดิม)

## 2. run.py
- `run.py` sha256 ณ ก่อนเริ่ม phase pre = `a81a840219a22e71217145b3fd200d70f4b31df3ffc0d2964d5fcb2445cb2747` (run.py บันทึกเองใน `run_meta_pre.json` / `run_meta.json` / บรรทัดแรกของ log ทุก phase · เก็บสำเนา `run_pre.py` ตอนเริ่ม phase pre · phase full คำนวณไฟล์ phase pre ซ้ำแล้วต้องตรงทุกบิต · ถ้า sha ต่างระหว่าง phase → diff ใน results.md)
- ไฟล์ phase pre: `mapping_codes.csv` · `mapping.csv` · `quarters.csv` · `betas.csv` · `exposure.csv` · `concentration.csv` · `eg_coef.csv` (ไม่ใช้ค่าผลตอบแทนช่วงถือ / realized / weekly ของ quant) · phase full: attribution L1 (main · P-A · P-B) · L2 · reconcile · ภาคผนวก P-A…P-E · ความคาดหมาย · results.md

## 3. กติกาเปิดคอลัมน์ realized (S015 ข้อ 4.9 · m12)
- phase pre / test โครงสร้าง / ก่อนไฟล์นี้: เปิดเฉพาะ `t · portfolio · horizon · e · end · days · truncated` (`port.load_realized(full=False)` ใช้ `usecols`)
- phase full เท่านั้น: `cost · ret · ret_gross · rf_ann · weights` (L2 · reconcile · test 12) · ห้ามเปิด `ret_ann · vol_ann · sharpe · n_days · exp_*` (ไม่อยู่ใน usecols) · `m052_frontier_weekly.csv` เปิดค่า `ret` เฉพาะ phase full (P-D) · ไม่โหลด `EXPORT_m052_curves.csv`
- แถว realized: `portfolio = ERC (กติกาโมเดล)` · `horizon = Q` · 15 แถว · `t` ตรง holdings · `e`/`end` ตรงตารางข้อ 1 (assert)

## 4. ตาราง mapping / ไตรมาส (ต้องตรงทุกช่อง · ไม่ตรง → หยุด · assert ใน run.py ทุก phase)
ตาราง 0.2 ฉบับ S015 (23 แถว) และตารางไตรมาส 15 แถว เทียบ `scratch/factor-designer_s015_holdings.csv` / `_quarters.csv` (pin sha) · 23 รหัส → 23 หน่วย (E 20 · G 3) · ตัวแทน family 3 (KKP GINFRAEQ-H-F → KKP GINFRAEQ-H · ONE-INDIAOPP-IA → ONE-INDIAOPP-RA · PRINCIPAL GOPP-C → PRINCIPAL GOPP-A · ตรวจกับ `universe.csv` family) · นอก U 3 · FX flag ต่าง 1 · factor กลุ่มของ LHJAPE-A / ONE-INDIAOPP-RA ด้วย `l1eo.apply_name_rules` (กฎชื่อ + เกณฑ์กลุ่ม ≥ 5 ใน U_E) · ช่วงถือ = anchor ศุกร์ใน (e_q, e_{q+1}] · 13 สัปดาห์ · ไตรมาสสุดท้ายถึง 2025-12-26 · anchor 2022-04-01 ไม่เป็นของไตรมาสใด · anchor 2022-07-01 เป็นของไตรมาส 2022-03-31 · ปี 2022 = 39 · 2023/2024/2025 = 52 · ทั้งช่วง 195

## 5. ชุด factor · β · ตัวประมาณ (S014 ข้อ 3.1–3.3 · S015 ข้อ 5.2 ข้อ 4–6 · 14)
- ขา E: MKT = `MSCI_ACWI − RF_BOT` · FX = `SHV_THB − RF_BOT` · CMA = `KF_DEV_CMA` (noaqr) · e_g ≤ 1 ต่อกอง (I_g ตาม S012 ข้อ 3.2 · `l1eo.group_I` · e_AH ไม่ใช้) · ขาทอง: GOLD_XS = `GLD_USD − SHV_USD` + FX (ไม่ใช้ MKT / CMA) · ไม่เรียก `o_factors` (สูตร GOLD_XS เหมือนกันทุกบิต — ใช้นิยามตรงใน `port.factor_frames`) · assert ไม่มี AQR
- หน้าต่าง = anchor ศุกร์ ≤ t และ > t − 156 สัปดาห์ · min_obs 52 · Dimson lag 1 + HAC L = 4 (`regress.fit_funds`) · β = b0 + b1 · σ²_ε = ssr/(n − p) · p = 1 + 2K · SE ของ β = `se_beta` (HAC ของผลรวม)
- e_g,q = I_g − b̂′[MKT, FX, CMA] (`l3.residualize` · lag 0 · เก็บค่าคงที่ · b̂ จากหน้าต่างของไตรมาสนั้น · ใช้ทั้งในหน้าต่างและช่วงถือ รวมค่าล่าช้าสัปดาห์แรก)
- Σ_f = covariance ตัวอย่าง ddof 1 (lag 0) บนแถวหน้าต่างที่ factor ของพอร์ตครบ · V = B′Σ_f B + Σ w² σ²_ε (V_def = longrun) · Euler share = B_k (Σ_f B)_k / V · SE ของ B = √(Σ w² se²) (ไม่รวม cov ข้ามกอง)
- ไม่มี fallback ของ β (fit ไม่ได้ → raise · spec: ไม่ควรเกิด)

## 6. attribution · กระทบยอด (S015 ข้อ 1–2 · 4.3)
- L1: น้ำหนักลอยเริ่มจาก w ณ e (w = `weight` ใน holdings) · r_p,s = Σ w_{s−1} r_i,s (ผลตอบแทนรวม = ส่วนเกิน + RF_BOT) · x_s = r_p,s − rf_s = Σ_k C_k,s + A_s + E_s (E = Σ w ε รายสัปดาห์ · id_err ≤ 1e-12 · assert)
- กระทบยอดแบบ (ก): CEX = Π(1 + r_p) − Π(1 + rf) · K = CEX − SUM · หน่วย pp · ส่วนแบ่ง % = ΣC / CEX (แถว A · E · K · เฉพาะช่วงสรุป · |CEX| < 2 pp → N/A) · ไม่ใช้ Carino
- L2: R^off,ex = `ret_gross` − rf_off · rf_off = `rf_ann × days / 365` · B ใช้น้ำหนักต้นไตรมาส · A_q = (Σ w α) × 13 · ε_L2 = ส่วนที่เหลือ · หลายไตรมาส: CEX^off = Π(1 + ret_gross) − Π(1 + rf_off)
- reconcile: Δ_q = `ret_gross` − R_panel (R_panel ทบต้นบนช่วงถือข้อ 1) · ต้นทุน = `ret_gross` − `ret` · flags (class ต่าง · fx_flag_diff · nav_fri_gap · start/end_mis) · ป้ายปลายช่วง panel 2025-12-26 vs ทางการ 2025-12-31
- ช่วงสรุป: 15 ไตรมาส · ปี 2022 (39) · 2023 · 2024 · 2025 (52) · ทั้งช่วง (195)

## 7. ภาคผนวก (ไม่เพิ่มอีก)
- P-A: DAOL-GOLD + GOLD_XS · FCSCBSETE + TDEXX (`TDEX_THB − RF_BOT` ไม่ตั้งฉาก) · แถวพอร์ตแบบเปลี่ยนเฉพาะ 2 กองนี้ (L1) · รายงาน adj R² / ΣE / contribution ของ factor เพิ่ม / share_ε
- P-B: ตัด CMA (E: MKT + FX + e_g · e_g ตั้งฉากบน [MKT, FX]) · P-C: x_q = Σ w ขา E · R_E / R_G จาก panel · x = 1 → R_G* = Π(1 + GLD_THB) − 1 + ธง `RG_proxy` · AE = (x − 0.57)(R_E − R_G) · รายงานทั้งรวม / ไม่นับไตรมาสธง
- P-D: ตัดแถวที่ไม่ใช่ศุกร์ (28 แถว · 7 ไตรมาส) · y = ret − RF_BOT ที่ anchor ศุกร์เดียวกัน · fit บน 51/52 แถว (Dimson lag จาก factor anchor ก่อนหน้า) ด้วย design เดียวกับข้อ 5 (e_g,q) · บันทึก n · เทียบ β กับ main · ตรวจความตรงของผลตอบแทนกับ panel (รหัสเดียวกับหน่วย)
- P-E: Ω = Ẽ′Ẽ / n_common (ไม่ demean) บนแถวร่วมของ residual ทุกกองที่ถือ · share_ε^full vs ^diag

## 8. เกณฑ์ตัดสินความคาดหมาย 11 ข้อ (ตัดสินด้วยตัวเลขเดียวกับ S014 ข้อ 5 · นิยามที่ใช้จริง · 'ตรง' ต้องครบทุกส่วนย่อย · รายงาน x/11 และไม่นับข้อ 9 y/10)
1 mapping: [23→23 · ตัวแทน 3 ตรงชุด · นอก U 3 ตรงชุด · FX ต่าง = PRINCIPAL GOPP-C เท่านั้น · fallback 0] · 2 [corr(B_MKT, x_model) ≥ 0.8 ข้าม 15 ไตรมาส · B_MKT ∈ [0.15, 1.0] ทุกไตรมาส] · 3 [ไตรมาสที่มีขาทอง: B_GOLD_XS/(1 − x_hold) ∈ [0.85, 1.0] ทุกไตรมาส · ไตรมาส x = 1: B_GOLD_XS = 0] · 4 [ไตรมาสทอง ≥ 0.5: share GOLD_XS ≥ 0.5 ทุกไตรมาส · ไตรมาส x ≥ 0.75: share MKT ≥ 0.35 · ผลรวม share factor กลุ่ม ∈ [0.10, 0.45]] · 5 [B_FX ∈ [−0.8, 0.4] · share FX < 0.15 ทุกไตรมาส] · 6 [share_ε ∈ [0.05, 0.30] ทุกไตรมาส · |ΣE_s ไตรมาส| ≤ 3% ใน ≥ 10/15] · 7 [|ret_gross − R_panel| ≤ 1% ใน ≥ 12/15] · 8 [|ΣC_CMA ทั้งช่วง| < 2% · factor ที่ |ΣC| มากสุดของชุดหลักเท่ากับของ P-B] · 9 [factor ที่ |ΣC| มากสุดใน L1 ปี 2022 ∈ {GOLD_XS, MKT} · ΣAE ปี 2022 (รวมทุกไตรมาส) > 0] **ป้าย: designer เห็นผลจริงไตรมาสแรกของ ERC แล้ว (ราว −8% ขณะถือทอง 75%) — ไม่อิสระบางส่วน** · 10 [median Δadj R² ข้ามไตรมาสที่ถือ: DAOL-GOLD + GOLD_XS ≥ 0.15 · FCSCBSETE + TDEX ≥ 0.20] · 11 [corr(β P-D, β main) ข้ามทุก (t · holding · factor) ≥ 0.7]

## 9. ไม่มีการเลือกหลังเห็นผล · แก้โค้ดหลังรันจริง → diff ใน results.md · เรื่องที่ spec ไม่ระบุละเอียด (ตัดสินแล้ว): `mapping.csv` ต่อ (t · holding) 58 แถว + `mapping_codes.csv` ต่อรหัส 23 แถว · ตัวแปรกลุ่ม factor ใช้ชื่อคอลัมน์ `e_<กลุ่ม>` (CHINA = `e_CHINAg`) · ผลลัพธ์ตารางใน results.md แสดง pp (CSV เก็บเป็นสัดส่วน)
