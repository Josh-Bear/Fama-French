# S006_L3 — VIF-cleaned: ผลของ L2 อยู่ไหมเมื่อจัดการ collinearity · ชุด factor + ดัชนีสุดท้ายที่สะอาด (spec ลงทะเบียนล่วงหน้า)

ผู้เขียน: factor-designer · วันที่ 2026-10-16 · ชั้น: **L3** (ระยะ 1 — อธิบาย · ไม่นับ trial) · สถานะ: **รอรีวิว** (reviewer → session หลักสั่งรันตาม auto run)
อ้างอิง: `BRIEF.md` (ค่าที่ยืนยัน 1–21 · ค่าชั่วคราว 22–56 โดยเฉพาะ **45, 46, 51, 56** · ตารางชั้น L3 · ตารางคะแนนกลาง) · `reports/L1_summary.md` · `reports/L2_summary.md` ·
`specs/S004_L2_factor_x_msci.md` + `specs/S005_L2_addendum_to_S004.md` (sha256 S005 = `c71ad963b64347d463c8d8a30fe55240b851be85d364f35a6ab121a7112f8468`) · `runs/S005/results.md` ·
`research/F-R004_deep_search_L3_L4.md` (L3-1, L3-2, L3-3, L3-6) · F-R001 (④-1 hybrid) · F-R003 (ป้ายวิธี) · `data/manifest.json`, `data/manifest_ext.json`, `data/QA_L0_ext.md` · `config.py` (`SCORE_COUNTRY_CLEAN` · อ่านอย่างเดียว)
การตรวจของ designer: `scratch/factor-designer_s006_structure.py` (ชื่อคอลัมน์ / จำนวนแถว / NaN / sha256 / จำนวนกองต่อป้าย primary เท่านั้น) — **ไม่ได้ดูค่าผลตอบแทน ไม่ได้ fit model ไม่ได้คำนวณ VIF ใหม่**

> **ป้ายบังคับทุกตารางผล:**
> (ก) ED ตรงกับแหล่งรอง (R `cate::EigenDiff`) · ยังไม่เปิดต้นฉบับ Onatski 2010 [22, 47] — ทุกผลของ ①a / ①c (k\* = 4) ·
> (ก2) PY ตรงต้นฉบับ JFEc 2024 [24] แต่คงป้าย (N−1)ρ̄² > 1 + p_boot ·
> (ข) **ช่วง test 2024–2025 ถูกใช้เลือกรูปแบบตั้งแต่ L1 และใช้ตัดสินเกณฑ์ P1(ข) ของ L2 แล้ว — ไม่ใช่หลักฐานนอกช่วงที่อิสระ** ·
> (ค) ผลขึ้นกับค่าที่ยืนยัน 1–21 และค่าชั่วคราว 22–56 ·
> (ง) **เกณฑ์ L3 ทั้งหมดในข้อ 7 "ออกแบบหลังเห็นผล L2"** (ข้อ 31, 44, 51) — เป็นเกณฑ์ของชั้นใหม่ ไม่ใช่การแก้ P1–P4 ของ L2 ย้อนหลัง ·
> (จ) แถวชุดเข้ม (5 ดัชนี ไม่มี Vietnam · ข้อ 45) = **"เกณฑ์เปลี่ยนหลังเห็นผล"**

---

## 0. ข้อเท็จจริงเชิงโครงสร้าง (ตรวจเอง · `factor-designer_s006_structure.py`)

| เรื่อง | ค่า | ผลต่อ spec |
|---|---|---|
| `factors_ext_weekly.parquet` | 291 × 38 (`<ETF>_USD`, `<ETF>_THB` 19 ETF) · ช่วงหลัก 260 แถว · **NaN = 0** · index ตรง `factors_weekly` | ใช้เฉพาะ `_THB` − RF_BOT (ข้อ 3.3) |
| `runs/S003/factors_S003_weekly.parquet` | 260 × 69 · `1a__PC1..4`, `1c__PC1..4` · sha256 ตรง pin | ฐาน L3 (ข้อ 46) |
| คอลัมน์ที่ต้องใช้ใน `factors_weekly` | RF_BOT, SHV_THB, Gold_THB, AGG_THB, MSCI_ACWI มีครบ | C0 = ③a (`external.line3(F, "3a")`) |
| lib ปัจจุบัน vs `runs/S005/run_meta.json` | sha256 ตรงทั้ง 12 ไฟล์ · ไม่มีไฟล์เกิน | regression baseline (ข้อ 8.3) |
| sklearn | 1.9.0 (มีใน `.venv`) | elastic net diagnostic |
| `runs/S005/primary_index.csv` (form = none · EVAL 207) | กองหลักของ P4: HC 7 · UT 5 · Europe 6 · India 8 · Japan 8 · Vietnam 6 (รวม 40) · primary อยู่ใน 11 ประเทศของแอป 46 กอง · sector 75 · ดัชนีรวม 86 | B-prim มีส่วนเพิ่มได้ ≤ 40 กอง · ดัชนีรวมเป็น primary ของ 86 กอง → A ต้องเลือก primary ใหม่ |
| `cache/results.csv` (แอป · อ่านอย่างเดียว) | 209 แถว · `country_primary` (มีดัชนีรวม เช่น ACWI / ACWI_EX_US / ASIA_EX_JAPAN) · `sector_primary` · `*_r2` | เทียบ Q3 เชิงบรรยาย (ข้อ 4.5) |

---

## 1. คำถามและสมมติฐาน

**คำถาม L3 (BRIEF):** **Q1** ผลของ L2 (P4 6 ดัชนี) ยังอยู่ไหมเมื่อจัดการ collinearity · **Q2** ชุด factor + ดัชนีสุดท้ายที่สะอาด (VIF < 5) คืออะไร · **Q3** primary ของทีมเทียบกับที่แอปให้ (เชิงบรรยาย)

แนวคิด (F-R004 L3-1): VIF elimination เปลี่ยนทั้ง **ปริภูมิ (span)** และ **การตั้งชื่อ (parametrization)** พร้อมกัน · การ residualize เปลี่ยนเฉพาะการตั้งชื่อ → ใช้ 3 รูปแบบเพื่อแยกสองเรื่องนี้:
**A** = ตัดแบบแอป (เปลี่ยน span) · **B (หลัก)** = ดัชนี P4 residualize บน factor L1 (span เท่า L2) · **C** = ชุดดัชนีลำดับชั้นไม่มี PCA (span ใหม่ที่ตีความ/ลงทุนได้ทั้งหมด)

- **H3.1 (Q1 · B):** e(P4) ตั้งฉากกับ f ในช่วง train โดยโครงสร้าง → VIF สูงสุดของ design B-all < 5 โดยไม่ต้องตัด · แต่ละดัชนีใน P4 ยังเพิ่ม R²_oos ในกองหลักของตัวเองเมื่ออยู่ร่วมกันทั้ง 6 ตัว (drop-one ≈ single-index ของ L2) · ทั้งบล็อกให้ทุกกองไม่คุ้ม (ΔBIC > 0 เหมือน REG8)
- **H3.2 (Q1 · A):** ตัดแบบแอปแล้ว P4 รอด ≥ 4 ใน 6 ตัวทั้ง ①a และ ①c (Vietnam / India / UT รอดแน่ · Europe / HC / Japan เสี่ยง) · A-prim เสียส่วนเพิ่มเทียบ L2-1 / L2-3 ไม่เกิน 0.01 (E)
- **H3.3 (Q2 · C):** ชุดดัชนีลำดับชั้นที่เลือกด้วย BIC (train) + ③a อธิบายกอง E ได้ต่ำกว่า ①a (R²_oos) แต่สูงกว่า ③a/③b ของ L1 · placebo ไม่เลือกตัวใด
- **H3.4 (ความถูกต้อง):** residualize แบบ lag-0 ที่เก็บค่าคงที่ไว้ไม่เปลี่ยน R², R²_oos, α, BIC ของกองใด (ภายใน 1e-10)
- **H3.5 (Q3):** primary ของทีมตรงกับ primary ของแอป (country หรือ sector ตัวใดตัวหนึ่ง) ≥ 50% ของกองที่อยู่ทั้งสองชุด

ตัวเลขใน H = ความคาดหมายสำหรับตรวจตัวเอง ไม่ใช่เกณฑ์ผ่านอัตโนมัติ

---

## 2. ข้อมูล (ตรวจ sha256 ก่อนรัน · ไม่ตรง → หยุด)

| ไฟล์ | ใช้ทำ | sha256 |
|---|---|---|
| `data/panel_weekly.parquet` | ผลตอบแทนกอง | `95c16ee651d3a936788b7cb3c6372bbf5f1e84cb39daf5680343771dca24270b` |
| `data/panel_monthly.parquet` | ตรวจซ้ำรายเดือน | `e8e8cb5d5f04fba9bb35558ef7c3d8195c656334119e56f82775cc1ae21ccaed` |
| `data/factors_weekly.parquet` | M28 · RF_BOT · ③a | `115b87139d2bec0fd57a77a1593c46d36bb23f3f35f83236cdb07be642af47a8` |
| `data/factors_monthly.parquet` | รายเดือน | `f7c4248b4fa889853024449e72ae8909cf1f8d3226a54eebc37448a2a485bb72` |
| `data/factors_ext_weekly.parquet` | ETF ส่วนขยาย (ข้อ 56) | `3105b6e7fe32ffd3648e8feac8dbd03a8db22b7e8eb245c5faf462b14da5e296` |
| `data/universe.csv` · `dup_pairs.csv` · `factor_groups.csv` | ชุดกอง · ลำดับเสมอ | `fdfb7830…f7252` · `b1f0f0c7…aef3` · `42bf1cfb…1731` (เต็มใน manifest) |
| `runs/S003/factors_S003_weekly.parquet` | ①a / ①c k = 4 (**ไม่ประมาณใหม่**) | `be3ceb2e34b0df1f1a3db27d59e1a103cf5f5a5ca38f2e87f7c812c1c53944ac` |
| `runs/S003/fund_level.csv` | ธง EVAL / E67 / STAB | `36b41161d6a13c1184a4052d9e799f660f431c2694dc57fafd747f8e695bf8cf` |
| `runs/S003/grs_ports.csv` · `regions.csv` | พอร์ต GRS 17 | `d55011094898acdf6e0419c90a3b2713479451380cacc0bf950559c43b98ba19` · `2fa3ce691c9dd66ef523e1baca228a635369d2971857797a05c105c1306e6866` |
| `runs/S005/primary_index.csv` | primary ของ L2 (form `1a@4`, `1c@4`, `none`) | `5a94ab9b498bb107600938d37f665c7263d9f0a5973460159c09ae83a799275c` |
| `runs/S005/fund_clusters.csv` | กลุ่มกองอิสระ 168 กลุ่ม | `072cd97ade7e01a32edb9aaf5b949381d1500dcb1ed909558bee3a373e2fc0cb` |
| `runs/S005/criteria_P4.json` | รายชื่อ P4 | `0db21831202f8ff2378923740074d2517be1a37563d5f09a64e103d8651cbfb2` |
| `runs/S005/fund_level.csv` | ค่าอ้างอิง L2-1 / L2-3 / ฐาน (test 30) | `1be9d49e70f385cd9a6e09d586f16ec3677622ee87b598826a34bebd69a89cf5` |
| `runs/S005/placebo_rule.json` | ขั้น C.2 = 2 (p_adj + BH) ที่ใช้กับตัวนับ Wald ข้อ 5.3 | `0460b5b2ff9721c3be97c134fd15c19d28c6596c0a5f6ad5dd08d842ec3f78dc` |
| `config.py` (แอป · อ่านอย่างเดียวแบบ text/AST ไม่ import) | `SCORE_COUNTRY_CLEAN` | `711d5738ecf25fc0064e10134ae4cf5d8cfb0cee22d8dd5fbf0174fe925a7d66` |
| `cache/results.csv` (แอป · อ่านอย่างเดียว) | Q3 เชิงบรรยายเท่านั้น (BRIEF: ระยะ 1 เทียบได้) | `7c0ce137c4a8692e0136cefe1c4ddbad4cea42cca5e0af8aaa8bb36a05239cfc` |

ช่วงเวลา / ชุดกอง **เหมือน L1–L2 ทุกประการ:** train 2021-01-08 → 2023-12-29 (Dimson 155 แถว) · test 2024-01-05 → 2025-12-26 (104) · H1/H2 ตาม S002 ·
EVAL 207 (E175/F18/O14 · ข้อ 1–4 · เกณฑ์) · E67 (ภาคผนวก) · STAB 191 (ข้อ 5) · PY_test 206 · GRS 17 พอร์ตเดิม · ห้ามใช้ข้อมูล ≥ 2026-01-01 (ข้อ 6) · `*_late_*`, `*_lvl`, `*_est_ret`, `Gold` (USD), `USDTHB` ไม่ใช้

---

## 3. ตัวแปร

### 3.1 factor ฐาน (ข้อ 46)
f = ①a (`1a__PC1..4`) หรือ ①c (`1c__PC1..4`) ที่ k = 4 ผ่าน `l2.load_l1_factors` (ตรวจ sha256) · ไม่มีภาคผนวก k = 3 / 5 (ดู "ต้องให้ผู้ใช้ตัดสินใจ" ข้อ 9)

### 3.2 ดัชนี (excess · `l2.index_set`)
- **C11** = `config.SCORE_COUNTRY_CLEAN` (BRAZIL, CHINA_A, CHINA_H, EUROPE, INDIA, JAPAN, KOREA, ASEAN, TAIWAN, USA, VIETNAM) · hardcode ใน `l3.py` + test 41 ยืนยันว่าตรงกับ config (อ่าน AST)
- **S10** = ACWI sector 10 ตัว (CD, CS, EN, FN, HC, IN, IT, MT, TC, UT · ไม่มี Real Estate ตาม config)
- **P4** = HC, UT, EUROPE, INDIA, JAPAN, VIETNAM (`criteria_P4.json` · ข้อ 45) · **P4′** = P4 − VIETNAM (ชุดเข้ม ⚠️)

### 3.3 ETF ส่วนขยาย (ข้อ 56) — ใช้ที่ไหนและทำไม
**ใช้:** `<ETF>_THB − RF_BOT` 14 ตัว: ธีม QQQ, SOXX, ARKK, ICLN, IBB, KWEB · อาเซียน THD, EIDO, EPHE, EWM, EWS · real assets REET, IGF, DBC
**ไม่ใช้:** `_USD` ทุกตัว (M28 เป็นบาท · ไม่ผสมสกุล) · GSG (ซ้ำบทบาท DBC) · HEWJ/EWJ/HEFA/EFA (เรื่อง hedge → L4 ตาม F-R004 L4-1)
**ใส่เฉพาะใน C (pool ลำดับชั้น) และ diagnostic elastic net — ไม่ใส่ใน A และ B** เหตุผล: (1) A คือ "ชุดของแอป" ตามนิยาม · (2) B คือ "ผลที่ L2 ส่งต่อ" — ETF ใหม่ไม่ผ่านการคัดของ L2 การเติมเข้า B = คัดใหม่ในชั้นที่ไม่ได้ออกแบบมาคัด · (3) C เป็นสายดัชนีที่ตีความได้ซึ่งลำดับชั้นรองรับ ETF เป็น "ใบ" ได้โดยธรรมชาติ (THD ใต้ ASEAN · ธีมใต้ sector) โดย**ไม่เพิ่มจำนวนรูปแบบ** · (4) กองธีม 40 กองที่ primary = ACWI_CD และกองหุ้นไทย FIF ไม่มีดัชนีตรงใน M28 — C-prim เป็นที่เดียวที่ทดสอบได้ว่า ETF ช่วยไหม · ข้อระวัง: ETF ปิดเวลา NY (Dimson ช่วยบางส่วน) · THD vs TDEX รายสัปดาห์ corr 0.76 (QA_L0_ext §4)

### 3.4 การ residualize (นิยามกลาง · ใช้ทั้ง B และ C)
ต่อดัชนี j ที่มี "แม่" P_j (ชุดคอลัมน์ lag 0):
1. OLS ช่วง train (แถวที่ไม่ NaN ทั้งหมด): I_j,t = a_j + b_j′ P_t + u_j,t
2. **e_j,t = I_j,t − b̂_j′ P_t** ทุก t (train + test · b̂ ตรึงจาก train) → ในช่วง train e_j = â_j + û_j (**เก็บค่าคงที่ไว้**)
3. **lag 0 เท่านั้น** (ไม่ใส่ P_t−1 / P_t+1 ใน auxiliary)

เหตุผลเชิงพีชคณิต (ตรวจด้วย test 29–30): ถ้า P_j ⊂ design ของกอง แล้ว e_j,t และ e_j,t−1 เป็นผลรวมเชิงเส้นของ {I_j,t, P_t} และ {I_j,t−1, P_t−1} ซึ่งอยู่ใน Dimson design อยู่แล้ว → การแปลงคอลัมน์เป็นเมทริกซ์เต็มยศเดียวกันทั้ง train และ test → fitted, residual, R², R²_oos, BIC **เท่าเดิม** · และเพราะ e ไม่หักค่าคงที่ → **α เท่าเดิม** ·
ถ้าหัก â (ใช้ û) α ของกองจะเปลี่ยนเป็น α + β_j â_j · ถ้าใส่ P_t−1 ใน auxiliary e_j,t−1 จะพา P_t−2 เข้ามา (span เปลี่ยน) · ถ้าใส่ P_t+1 = look-ahead → ห้ามทั้งสามแบบ
- ช่วง train: corr(e_j, P) = 0 ตามโครงสร้าง · ช่วง test ตั้งฉากโดยประมาณเท่านั้น → รายงาน corr(e_j, P) และ corr(e_j, e_k) ช่วง test
- แม่ที่เป็น raw หรือ residualized ให้ e เท่ากัน (span ของแม่เท่ากัน) → ใช้แม่แบบ raw

---

## 4. รูปแบบ (**3 รูปแบบ · 8 แถวหลัก + 4 แถวชุดเข้ม = 12 แถว** — ลองนอกนี้ = spec ใหม่)

| แถว | รูปแบบ | ฐาน | สิ่งที่เพิ่ม | ชนิด | K (ต่อกอง) |
|---|---|---|---|---|---|
| R1 / R6 | **A-prim** | ①a / ①c | primary 1 ตัวต่อกองจาก S_A(ฐาน) (ดัชนีดิบ) | ต่อกอง | 5 |
| R2 / R7 | **B-all** (หลัก) | ①a / ①c | e(P4) 6 ตัว ทุกกอง | factor ร่วม | 10 |
| R3 / R8 | **B-prim** | ①a / ①c | e_p(i) ถ้า primary ของ L2 ∈ P4 (40 กอง) · กองอื่น = ฐาน | ต่อกอง | 5 หรือ 4 |
| R4 / R9 ⚠️ | B-all5 | ①a / ①c | e(P4′) 5 ตัว | factor ร่วม | 9 |
| R5 / R10 ⚠️ | B-prim5 | ①a / ①c | เหมือน B-prim แต่กองหลัก Vietnam = ฐาน | ต่อกอง | 5 หรือ 4 |
| R11 | **C-blk** | ไม่มี PCA | C0 (③a 4 ตัว) + บล็อกลำดับชั้นที่เลือก (ข้อ 4.3) | factor ร่วม | 4 + m (m ≤ 8) |
| R12 | **C-prim** | ไม่มี PCA | C-blk + e 1 ตัวต่อกองจาก pool ที่เหลือ | ต่อกอง | 5 + m |

**แถวอ้างอิง (ไม่ใช่รูปแบบใหม่ · ต้องตรงกับผลเดิม — test 30):** ฐาน ①a · ฐาน ①c · L2-1 · L2-3 (จาก S005) · ③a (= C0 · ต้องตรงแถว ③a ของ `runs/S003/fund_level.csv`)
**diagnostic (ไม่ใช่รูปแบบ · ไม่มีตารางคะแนนเต็ม):** drop-one ใน B-all (6 × 2 ฐาน) · span test · elastic net stability selection · VIF / condition number ทุกแถว · placebo ของ C
ถ้า B-all ต้องใช้ fallback ตามข้อ 4.2 (3) → แถว B-all′ **แทน** B-all (ไม่เพิ่มแถว) และบันทึก

### 4.1 รูปแบบ A — ตัดแบบแอป (ตัวเทียบแอป · F-R004 L3-3)
- **A0 (บรรยาย):** VIF (`tests_stat.vif` · lag 0 · train) และ condition number κ = √(λmax/λmin) ของ corr matrix สำหรับ (i) C11 ลำพัง (ทั้ง train และ 2021–2025 เพื่อเทียบคำกล่าวในแอป "VIF < 5") (ii) S10 ลำพัง (iii) C11 + S10 (iv) f + C11 + S10 · ต่อฐาน
- **A1 backward elimination (ต่อฐาน):** X = [f (4 · **ห้ามตัด**), C11, S10] (25 คอลัมน์ · lag 0 · แถว train ครบ) → วน: คำนวณ VIF ทุกคอลัมน์ · ถ้า max < 5 → หยุด · มิฉะนั้นตัด**ดัชนี**ที่ VIF สูงสุด (เสมอ → ลำดับ `factor_groups.csv`) · ถ้าเหลือแต่ f ที่ VIF ≥ 5 → หยุดและติดป้าย · ผล = **S_A(ฐาน)** + ลำดับการตัด (`vif_elim_A.csv`) · VIF แบบ Dimson design (2 × คอลัมน์) รายงานคู่ (บรรยาย)
- **A-mem (ตอบ Q1 แบบแอป):** ดัชนีใน P4 ตัวใดอยู่ใน S_A ทั้งสองฐาน
- **A-prim:** primary ต่อกอง = `l2.primary_index(R, IDX[S_A], mask_tr, EVAL)` (argmax R² Dimson ตัวเดียว · train · เหมือน L2) → fit f + primary (ดัชนีดิบ) ด้วย `l2.AugmentedFactors(per_fund=…)` · บันทึก `primary_A.csv` ก่อน fit · VIF ต่อกอง (ดัชนีกับ f) รายงาน max / median

### 4.2 รูปแบบ B (หลัก) — ดัชนี P4 residualize บน factor L1 (F-R004 L3-2 · ข้อ 51)
1. e_j = residualize(I_j, P = f ของฐานนั้น) ตามข้อ 3.4 · j ∈ P4 → `resid_B_coef.csv` (a, b, R² train, corr test)
2. **B-all:** f + e(P4) ทุกกอง (`AugmentedFactors(base, extra=E)`) · **B-all5:** f + e(P4′)
3. VIF ของ design [f, e(P4)] (lag 0 · train) — ถ้า max ≥ 5 → backward elimination **เฉพาะ e** (กติกาเดียวกับ A1) → B-all′ (บันทึกเหตุ) · κ รายงานทุกกรณี
4. **B-prim:** p(i) = primary ของ L2 จาก `primary_index.csv` form `1a@4` / `1c@4` (ไม่เลือกใหม่) · ถ้า p(i) ∈ P4 → f + e_p(i) · มิฉะนั้น = ฐาน · **B-prim5:** เหมือนกันแต่ p(i) = VIETNAM → ฐาน
5. **drop-one (diagnostic):** ต่อ j ∈ P4: fit B-all \ {e_j} บนแถวเดียวกัน → ต่อกอง Δ_j R²_oos = R²_oos(B-all) − R²_oos(B-all \ j) · Δ_j BIC = BIC(B-all) − BIC(B-all \ j) · Δ_j adj R² · สรุป median ในกองหลักของ j และในทุกกอง EVAL + จำนวนกลุ่มกองอิสระที่ Δ_j R²_oos ≥ 0.02 (บรรยาย · ข้อ 42)
6. Wald (b0_j, b1_j) = 0 ต่อกองใน B-all → ข้อ 5.3 (บรรยาย)

### 4.3 รูปแบบ C — ชุดดัชนีลำดับชั้น residualize ไม่มี PCA (F-R004 L3-1)
**C0** = ③a = {MKT = ACWI − rf, BOND = AGG_THB − rf, GOLD = Gold_THB − rf, FX = SHV_THB − rf} (`external.line3(F, "3a")` · ข้อ 20 / 27)

**ลำดับชั้น (ล็อก · กติกาของ designer · ติดป้าย):** e_child = residualize(child, P = แม่) ตามข้อ 3.4

| แม่ (P) | ลูก | จำนวน |
|---|---|---|
| {MKT} | ภูมิภาค: USA, EUROPE, JAPAN, ASIA_EX_JAPAN · ประเทศนอกเอเชีย: BRAZIL | 5 |
| {MKT} | sector: CD, CS, EN, FN, HC, IN, IT, MT, TC, UT | 10 |
| {MKT} | real assets: REET, IGF, DBC | 3 |
| {MKT, ASIA_EX_JAPAN} | CHINA_ALL, INDIA, KOREA, TAIWAN, ASEAN, VIETNAM | 6 |
| {MKT, ASIA_EX_JAPAN, CHINA_ALL} | CHINA_A, CHINA_H, KWEB | 3 |
| {MKT, ASIA_EX_JAPAN, ASEAN} | THD, EIDO, EPHE, EWM, EWS | 5 |
| {MKT, IT} | QQQ, SOXX, ARKK | 3 |
| {MKT, HC} | IBB | 1 |
| {MKT, UT} | ICLN | 1 |
| **pool P_C** | | **37** |

ไม่อยู่ใน pool: WORLD, WORLD_EX_US, ACWI_EX_US, EM (ดัชนีรวมที่ซ้อนกับ MKT / ASIA_EX_JAPAN · คลัสเตอร์ใน `redundancy.csv`) · ACWI (= MKT ใน C0)

**C-blk — forward selection (train เท่านั้น · ล็อก):**
- เริ่ม M = C0 · รอบ m = 1, 2, …: ต่อ candidate j ∈ P_C \ M: ต่อกอง i ∈ EVAL 207 (ทุก policy) fit Dimson y_i ~ M และ y_i ~ M + e_j **บนแถว train เดียวกัน** → ΔBIC_ij · score_j = **median_i ΔBIC_ij**
- เลือก j\* = argmin score (เสมอ → ลำดับในตารางลำดับชั้นข้างบน) · เพิ่มเมื่อ score_j\* < τ **และ** |บล็อก| < 8 · มิฉะนั้นหยุด · τ ตามกฎ placebo ด้านล่าง
- cap 8 (กติกาของ designer): K ≤ 12 → GRS ทำได้ (L = 24 · T − N − L = 63 เท่ากับ REG8 ใน L2) และ p = 2K + 1 ≤ 25 ต่อ 155 แถว
- ไม่บังคับให้แม่ต้องอยู่ในบล็อกก่อนลูก (ตัวแปรนิยามแล้วว่า "เกินจากแม่" · ป้าย)

**placebo ของ C (ทำก่อน selection จริง · ค่าชั่วคราว 37 แนวเดียวกับ L2):** รัน algorithm เดิมทุกขั้นโดยแทน e_j ทุกตัวด้วย `l2.circular_shift(e_j, mask_tr, s)` s ∈ {26, 52} (C0 ไม่เลื่อน) → บันทึกจำนวนที่ถูกเลือก + score ดีที่สุดรอบแรก (τ_s) ลง `placebo_C.json` **ก่อน** selection จริง ·
**กฎ:** ถ้า placebo เลือก 0 ตัวทั้งสอง shift → τ = 0 · ถ้าเลือก ≥ 1 ตัวที่ shift ใด → τ = min(0, min_s τ_s) (ต้องดีกว่า candidate ปลอมที่ดีที่สุด) + ป้าย "selection ต้องปรับเกณฑ์ตาม placebo"

**C-prim:** ต่อกอง j(i) = argmax_{j ∈ P_C \ บล็อก} Δadj R² (train · Dimson) ของการเพิ่ม e_j บน C-blk · **เพิ่มเสมอ** (เหมือน L2-1) · บันทึก `primary_C.csv` ก่อน fit แถวที่ให้คะแนน · รายงานสัดส่วนกองที่ j(i) เป็น ETF ส่วนขยาย แยกตามกลุ่ม primary ของ L2 (โดยเฉพาะ ACWI_CD 40 กอง)

### 4.4 diagnostic
- **span test (ข้อมูลจริง):** (i) B-all แบบ e(P4) เทียบแบบดัชนีดิบ P4 บน EVAL ทั้งสองฐาน · (ii) B-prim (กองหลัก P4) เทียบ L2-1 / L2-3 ใน `runs/S005/fund_level.csv` · (iii) C closure: C0 + e ทั้ง 37 เทียบ C0 + ดิบทั้ง 37 (p = 83 ต่อ 155 แถว) → max |Δ| ของ adj R², R²_oos, α, BIC: (i)(ii) ≤ **1e-10** (ไม่ผ่าน → หยุด) · (iii) ≤ 1e-8 (บรรยาย · design ใหญ่ condition number สูง)
  - หมายเหตุ "ทุกบิต": ค่าเท่ากันทางคณิตศาสตร์ แต่ลำดับการคำนวณ floating point ต่างกัน → ใช้ tolerance แทนการเทียบ hash (ดู "ต้องให้ผู้ใช้ตัดสินใจ" ข้อ 6)
- **elastic net stability selection (F-R004 L3-6 · บรรยายเท่านั้น):** ต่อฐาน × กอง EVAL: candidate Z = M28 + ETF ส่วนขยาย 14 (ดิบ excess · lag 0 และ 1 → 84 คอลัมน์) · partial out [1, f_t, f_t−1] จาก y และ Z ด้วยแถว train (FWL = f ไม่ถูก penalize) · standardize ด้วย sd train · `sklearn.linear_model.ElasticNet(l1_ratio=0.5, fit_intercept=False, max_iter=10000, tol=1e-6, selection="cyclic")` · λ\* ต่อกอง = argmin BIC บน `enet_path` (100 ค่า · eps 1e-3) df = จำนวนสัมประสิทธิ์ ≠ 0 (ป้าย: df ของ EN เป็นค่าประมาณ — Zou–Hastie–Tibshirani 2007 พิสูจน์สำหรับ lasso · ยังไม่ยืนยันแหล่ง) · subsample 100 รอบ: บล็อกต่อเนื่อง 4 สัปดาห์ของ train สุ่มครึ่งหนึ่งของบล็อกแบบไม่คืน · `np.random.default_rng(20261015)` ใหม่ต่อฐาน · กองเรียงตาม FundCode · fit ที่ λ\* · ดัชนี "ถูกเลือก" เมื่อ lag 0 หรือ lag 1 ≠ 0 → π_ij
  - รายงานต่อดัชนี: จำนวนกอง / กลุ่มกองอิสระที่ π ≥ 0.6 และ ≥ 0.8 · median π ในกองหลักของ L2 · เทียบเซตกับ P4, S_A, บล็อก C · **ไม่ใช้เลือกอะไร** (ต้อง tune λ · เลือกต่างกันรายกอง — F-R004)
- **VIF / κ ทุกแถว:** factor ร่วม = design ร่วม (lag 0 และ Dimson) · ต่อกอง = max / median ข้ามกอง · ช่วง test รายงาน corr ที่เหลือระหว่าง e กับ f / แม่

### 4.5 Q3 — เทียบ primary กับแอป (บรรยาย · ไม่มีเกณฑ์)
แหล่ง primary: (a) L2 (`primary_index.csv` form none · M28 รวมดัชนีรวม) · (b) A-prim ต่อฐาน · (c) C-prim (ชื่อลูกในลำดับชั้น) · (d) แอป `cache/results.csv` `country_primary`, `sector_primary` (ElasticNet ทั้งช่วงของแอป · มี look-ahead · คนละ universe 209 กอง)
รายงานบนกอง EVAL ∩ แอป (n แยก E/F/O): อัตราตรงกับ country_primary · กับ sector_primary · ตรงตัวใดตัวหนึ่ง · cross-tab 15 คู่ที่ไม่ตรงบ่อยสุด · แยกกลุ่มที่ L2 primary เป็นดัชนีรวม (86 กอง) · C-prim: เทียบด้วย "ดัชนีลูก" (ETF ไม่มีในแอป → นับเป็นไม่ตรง และรายงานแยก)

---

## 5. การทดสอบทางสถิติ

### 5.1 กติการ่วม (เหมือน S003 / S005)
Dimson lag 1 (β = b0 + b1) · HAC Newey–West Bartlett L = 4 (รายเดือน L = 3) · seed 20261015 · เรียง `kind="stable"` · ทุกน้ำหนัก / β auxiliary / การเลือก (S_A, primary, บล็อก C, λ\*) ประมาณจาก **train เท่านั้น** แล้วตรึง · R²_oos = 1 − Σ(y − ŷ)²/Σ(y − ȳ_test)² ด้วย coef train · Δ ทุกตัวเทียบแถวอ้างอิงบน**กองและแถวเดียวกัน**: A/B เทียบฐานของตัวเอง · C-blk เทียบ ③a · C-prim เทียบ C-blk และเทียบ ①a (บรรยาย)

### 5.2 ต่อแถว (ตารางคะแนนกลาง 6 ข้อ)
fit รายกอง train → α̂, β̂, t_HAC, adj R², BIC · test → R²_oos · **GRS** (17 พอร์ตเดิม · fit ใหม่ในแต่ละช่วง) เฉพาะแถว factor ร่วม: B-all (L = 20 · T−N−L = 67) · B-all5 (L = 18) · C-blk (L = 2(4 + m)) · แถวต่อกอง = N/A ·
**PY + null bootstrap** ทุกแถวหลัก + แถวอ้างอิง (B = 999 · บล็อก 4 · fixed-design · `default_rng(20261015)` ใหม่ต่อแถว · ลำดับ R1…R12 แล้วอ้างอิง) · แถวต่อกองติดป้าย "regressor ต่างกันรายกอง — นอกกรอบทฤษฎี (บรรยาย)" ·
**bootstrap CI** ของ median Δ (2,000 รอบ · seed 20261015 · ป้าย "CI สุ่มกองแบบอิสระภายใน policy — กองสัมพันธ์กัน → CI แคบกว่าจริง") ·
**ความเสถียร** r ดิบ H1/H2 (STAB) ของ β ทุกตัวรวม e · β ของ index ต่อกองแยกตามดัชนีที่มี ≥ 10 กอง · **rolling 104** (`l2.rolling_betas`) เฉพาะแถว factor ร่วม ·
**รายเดือน:** แถวที่ p ≤ 13 (A-prim, B-prim, B-prim5 · ใช้ดัชนีดิบซึ่ง span เท่ากัน) · แถวอื่น N/A

### 5.3 multiple testing (ล็อก)
| ตระกูล | จำนวน | วิธีหลัก | ภาคผนวก |
|---|---|---|---|
| α รายกอง (ข้อ 3) ต่อแถว | 207 | BH FDR 10% (เหมือน L1–L2) | BY |
| Wald (b0_j, b1_j) = 0 ใน B-all ต่อฐาน (บรรยาย · ไม่ใช่เกณฑ์) | 207 × 6 = 1,242 | p_adj (F(2, n − p) · `l2.wald_p_dfadj`) + BH FDR 10% — ใช้ขั้น 2 ของ L2 (`placebo_rule.json`) ไม่สแกน placebo ใหม่ · ป้าย "คาลิเบรตจาก single-index ของ L2" | BY |
| forward selection ของ C (สแกน 37 ตัว × ≤ 8 รอบ) | ≤ 296 การเปรียบเทียบ | **placebo วน 26/52 สัปดาห์ + กฎ τ** (ข้อ 4.3) · ไม่ใช้ p-value | — |
| argmax primary (A-prim, C-prim) | 1 ต่อกอง | ไม่ทดสอบ · ป้องกันการเลือกเกินด้วย **ΔR²_oos** (ข้อ ข) | — |
| Q1 drop-one (6 ดัชนี × 2 ฐาน) | 12 การตัดสิน | กฎเชิงขนาด (ข้อ 7) ไม่ใช่ p-value · ป้าย | — |
| elastic net | — | บรรยาย ไม่ทดสอบ | — |
ไม่รวมตระกูลข้ามฐาน · ระยะ 1 ไม่นับ trial

---

## 6. ตารางคะแนนที่รายงาน + ตัวชี้เฉพาะ L3 (`runs/S006/`)

ตารางกลาง 6 ข้อ (แยก E/F/O/ALL + n · EVAL หลัก · E67 ภาคผนวก): **1** median/IQR adj R² + Δ + CI · **2** median/IQR R²_oos + Δ + CI · gap · **3** mean|α̂| · signed · BH · GRS · PY p / p_boot · **4** K · median BIC · ΔBIC · **5** r ดิบ · rolling 104 · **6** ชื่อ (ดัชนี / "เกินจากแม่" / "P4 ส่วนที่ตั้งฉากกับ factor")

ไฟล์เฉพาะ L3: `vif_A0.csv` · `vif_elim_A.csv` (ลำดับการตัด · S_A) · `primary_A.csv` · `resid_B_coef.csv` · `vif_rows.csv` (ทุกแถว: VIF max/median lag 0 + Dimson · κ · corr test ที่เหลือ) · `drop_one_B.csv` · `q1_verdict.csv` · `hier_coef.csv` · `placebo_C.json` · `select_C.csv` (log ทุกรอบ) · `primary_C.csv` · `span_test.csv` · `enet_stability.csv` + `enet_by_index.csv` · `q3_primary_vs_app.csv` · `q2_flags.csv` · `scorecard.csv` · `fund_level.csv` · `bootstrap.csv` · `grs.csv` · `py.csv` · `stability.csv` · `rolling_104.csv` · `monthly.csv` · `wald_B.csv` · `expectations_vs_results.csv` · `results.md` · `run.log` · `run_meta.json` (sha256 ข้อมูล + ไฟล์ pin + lib + regression ข้อ 8.3)

**ลำดับเขียนบังคับ (timestamp ใน run.log):** regression S003/S005 (ข้อ 8.3) → `vif_A0.csv` → `vif_elim_A.csv` → `primary_A.csv` → `resid_B_coef.csv` → `hier_coef.csv` → `placebo_C.json` → `select_C.csv` → `primary_C.csv` → span test → เริ่ม fit แถวที่ให้คะแนน

---

## 7. เกณฑ์ L3 (ล็อกก่อนรัน · ⚠️ ออกแบบหลังเห็นผล L2 · ผู้ใช้เลือกชุดสุดท้าย)

**technical validity:** test ใหม่ 28–44 + เดิม 1–27 + 19 ผ่าน · regression S003/S005 ผ่าน (ข้อ 8.3) · span test (i)(ii) ≤ 1e-10 · ไฟล์เลือกเขียนก่อน fit · รันซ้ำ 2 รอบได้ sha256 เท่ากันทุกไฟล์ผล

**Q1 — ผล L2 ยังอยู่ไหม** (ตัวเลข 0.02 / ΔBIC ≤ 0 / 5 / 7 = ค่าที่ล็อกแล้วใน L2 และ BRIEF · ไม่มีพารามิเตอร์ใหม่)
- **Q1a (ต่อดัชนี j ∈ P4 · รูปแบบ B):** "ยังอยู่" เมื่อ**ทั้ง ①a และ ①c**: (i) median Δ_j R²_oos (drop-one) ในกองหลักของ j ≥ 0.02 **และ** (ii) median Δ_j BIC ในกองหลักของ j ≤ 0 **และ** (iii) VIF ของ e_j ใน design B-all (lag 0 · train) < 5 · ผ่านฐานเดียว = "ยังอยู่บางส่วน"
- **Q1a-A (แบบแอป · รายงานคู่):** j ∈ S_A ทั้งสองฐาน = "รอดการตัดแบบแอป"
- **Q1b (ทั้งบล็อก):** B-all คุ้มเมื่อ median ΔR²_oos (E) เทียบฐาน ≥ 0.02 **และ** median ΔBIC (E) ≤ 0 (กติกาเดียวกับ REG8 ใน S005 P4)
- อ่าน: Q1a ตอบ "ดัชนีนี้ยังมีส่วนเพิ่มเฉพาะกลุ่มเมื่อ collinearity ถูกจัดการ" · Q1b ตอบ "ควรเป็น factor ร่วมไหม" — ผลแบบ L2 (ช่วยกองหลักแต่ไม่คุ้มเป็น factor ร่วม) จะได้ Q1a ผ่าน / Q1b ไม่ผ่าน

**Q2 — ธงของชุดสุดท้ายที่เป็นไปได้** (`q2_flags.csv` · ต่อแถว R1–R12 · ไม่มีการเลือกอัตโนมัติ)
(1) VIF สูงสุด (lag 0 · train) < 5 · (2) median ΔR²_oos (E) ≥ 0 เทียบแถวอ้างอิง · (3) median ΔBIC (E) ≤ 0 · (4) r ดิบ (E · STAB) ≥ 0.6 · (5) gap (E) ≤ 0.15 · (6) ตัวแปรที่เพิ่มทุกตัวมีชื่อ
(เกณฑ์ (4)(5)(6) = เกณฑ์ผู้เข้ารอบ L2 ของ L1 · ค่าที่ยืนยัน 12/18) · ตัวเทียบสำหรับ C: แถว C ต้องติดธงเพิ่ม "R²_oos E ต่ำกว่า ①a เท่าใด" (บรรยาย)

**Q3:** บรรยายเท่านั้น (ข้อ 4.5)

---

## 8. โค้ด (`lib/l3.py` ใหม่ · analyst เขียน · **ไม่แก้ฟังก์ชันหรือไฟล์ lib เดิม**)

### 8.1 ใช้ของเดิม
`io_l1.verify_manifest / load_returns / load_factors / sha256_file` · `samples.window_mask / eligible / dedup_keep` · `regress.dimson_design / lag_stack / ols_hac / fit_funds / CommonFactors / oos_r2_funds` · `fundff.single_index_r2` · `external.line3` · `tests_stat.vif / bh / grs / pesaran_yamagata / py_null_bootstrap / bootstrap_median` · `scorecard.score_model / stability_halves` · `l2.load_l1_factors / index_set / fund_sets / AugmentedFactors / primary_index / wald_subset / wald_p_dfadj / circular_shift / by / deltas / rolling_betas / count_groups`

### 8.2 ฟังก์ชันใหม่ (`lib/l3.py`)
| ฟังก์ชัน | input → output |
|---|---|
| `C11`, `S10`, `P4`, `P4_STRICT`, `EXT14`, `HIER` (ค่าคงที่) | รายชื่อตามข้อ 3 / ตารางลำดับชั้น 4.3 |
| `ext_excess(Fext, F)` | → DataFrame 14 คอลัมน์ `<ETF>_THB − RF_BOT` (ตัดแถว ≥ 2026-01-01) |
| `residualize(I, P, mask_tr)` | → (E, coef DataFrame: a, b…, r2_train, n) ตามข้อ 3.4 (lag 0 · เก็บค่าคงที่) |
| `hier_residuals(I_all, mask_tr, hier=HIER)` | → (E 37 คอลัมน์, coef log) |
| `vif_table(X, mask_tr)` | → DataFrame (col, vif) + κ (ใช้ `tests_stat.vif`) |
| `vif_backward(X, mask_tr, protect, order, thr=5.0)` | → (kept, log: step, dropped, vif_max) |
| `bic_rows(y, X)` | BIC แบบ OLS ไม่คำนวณ HAC (เร็ว · ต้องเท่ากับ `fit_funds` — test 36) |
| `forward_select(R, core, pool, mask_tr, funds, tau=0.0, kmax=8, L=4)` | → (selected, log) |
| `placebo_forward(R, core, pool, mask_tr, funds, shifts=(26, 52), kmax=8)` | → dict ต่อ shift (selected, best_score_step1) + τ ตามกฎ |
| `prim_from_pool(R, core, pool, mask_tr, funds)` | → DataFrame (FundCode, index, d_adj_r2) |
| `drop_one(R, base, block, mask_tr, mask_te, funds, L=4)` | → long DataFrame (fund, index, d_r2_oos, d_bic, d_adj_r2) |
| `enet_stability(R, f, Z, mask_tr, funds, l1_ratio=0.5, n_sub=100, block=4, frac=0.5, seed=20261015)` | → long DataFrame (fund, index, pi, lambda_star) |
| `cond_number(X, mask_tr)` | → κ |
| `primary_agreement(ours, app, groups)` | → ตาราง Q3 |
| `runs/S006/run.py` | รันเดียวจบตามลำดับข้อ 6 |

### 8.3 regression (ทำก่อนรัน S006 · ไม่ผ่าน → หยุด)
1. sha256 ของ lib เดิม 12 ไฟล์ = ค่าใน `runs/S005/run_meta.json` (`lib_sha256`) — เพิ่มได้เฉพาะ `l3.py` (และ test ใหม่)
2. รัน `runs/S003/run.py` (sha256 `9f21e388…590f`) และ `runs/S005/run.py` (sha256 `c51e3d61…8fee`) ลง `scratch/factor-analyst_s003_regress3/`, `scratch/factor-analyst_s005_regress3/` (ห้ามเขียนทับ `runs/S003`, `runs/S005`) → sha256 ทุกไฟล์ผล (รวม `appendix_k3/`, `appendix_k5/`, `rolling_104.csv`) **ตรงกับไฟล์เดิม** · ยกเว้น `results.md`, `run.log`, `run_meta.json`, `repro_check.*` (มีเวลา/เมตา) · `run_meta.json` เทียบทุก field ยกเว้น `created`, `runtime_sec`, `lib_sha256` (ซึ่งต้องตรงทุก entry เดิม · entry ใหม่ = l3.py เท่านั้น) · `placebo_rule.json` เทียบเนื้อหาไม่รวม timestamp (แบบ `factor-analyst_old_vs_new.json`)
3. ผลลง `runs/S006/regression_S003_S005.json`

### 8.4 test ใหม่ (`lib/tests/test_l3.py` · `pytest -p no:cacheprovider` · ของเดิม 1–27 + 19 ต้องผ่าน)
28. `residualize`: corr(e, P) train ≤ 1e-12 · mean(e_train) = â (1e-12) · แก้ข้อมูล test → b̂ ไม่เปลี่ยน · ไม่มี lag/lead ใน auxiliary
29. **span invariance (ข้อมูลจำลอง):** Dimson y ~ f + I เทียบ y ~ f + e → fitted, resid, R², R²_oos, **α**, BIC เท่ากัน (1e-10) · ตัวควบคุม: ถ้าหัก â แล้ว α ต่าง (ยืนยันเหตุผลข้อ 3.4) · ถ้าใส่ P_t−1 ใน auxiliary แล้ว R² ต่าง
30. span test บนข้อมูลจริงตามข้อ 4.4 (i)(ii) + แถวอ้างอิง (ฐาน ①a/①c · L2-1/L2-3 · ③a) ตรง `runs/S005/fund_level.csv` / `runs/S003/fund_level.csv` (1e-10) — อยู่ใน run.py เป็นเงื่อนไขก่อนรายงาน
31. `vif_backward`: x3 = x1 + x2 + noise 1e-3 → ตัดตัวที่ VIF สูงสุด · คอลัมน์ protect ไม่ถูกตัด · เสมอ → ตาม order · deterministic · ผลลัพธ์ VIF < thr
32. `vif_table` = `tests_stat.vif` · κ ตรง numpy (1e-10)
33. `HIER`: 37 ลูก · แม่มีจริง · ไม่มีวงวน · ไม่มี WORLD / WORLD_EX_US / ACWI_EX_US / EM / GSG / hedged / `_USD` · e_child ⟂ แม่ในช่วง train
34. `forward_select`: ข้อมูลจำลองที่กองโหลด 2 จาก 10 candidate → เลือกตรง 2 ตัวตามลำดับความแรงแล้วหยุด (τ = 0) · kmax เคารพ · แก้ข้อมูล test → ผลเลือกไม่เปลี่ยน · deterministic
35. `placebo_forward`: shift = 0 → ผลเท่า `forward_select` · ข้อมูลที่เลื่อนเป็น permutation ของบล็อก train · กฎ τ ตรงตัวอย่างมือทั้งสองกรณี
36. `bic_rows` = BIC ของ `fit_funds` บนแถวเดียวกัน (1e-10)
37. `drop_one` = ผลต่างของสอง `fit_funds` ที่รันแยก (1e-12)
38. `enet_stability`: ข้อมูลจำลองที่ y ขึ้นกับ Z1 → π(Z1) ≥ 0.9 · median π ตัวอื่น ≤ 0.3 · deterministic ที่ seed · partial out ใช้แถว train เท่านั้น
39. `primary_agreement`: ตัวอย่างมือ (ตรง country / sector / ทั้งคู่ / ไม่ตรง)
40. **no look-ahead:** แก้ผลตอบแทน/ดัชนีช่วง test → b̂ ของ B และลำดับชั้น · S_A · primary_A · บล็อก C · primary_C · λ\* / π ไม่เปลี่ยน
41. `C11` = `SCORE_COUNTRY_CLEAN` อ่านจาก `config.py` ด้วย `ast` (ไม่ import แอป)
42. `ext_excess`: ใช้ `_THB` เท่านั้น · ไม่มี GSG / hedged · ไม่มีแถว ≥ 2026-01-01 · = THB − RF_BOT (1e-15)
43. `B-prim` ใช้ primary จาก `primary_index.csv` form `1a@4` / `1c@4` ตรงตัว (ไม่เลือกใหม่)
44. `run.py` 2 รอบ → sha256 ทุกไฟล์ผลเท่ากัน (ยกเว้นไฟล์เวลา ตามแบบ L2)

---

## 9. ผลลัพธ์ที่คาดไว้ล่วงหน้า (เขียนก่อนเห็นผล · `expectations_vs_results.csv` ต้องมีทุกข้อ)

1. **A0:** C11 ลำพัง max VIF < 5 ทั้ง train และ 2021–2025 · S10 ลำพังมี ≥ 1 ตัว VIF ≥ 5 · f + C11 + S10 มี ≥ 5 ตัว VIF ≥ 5 ก่อนตัด
2. **A1:** ตัด 4–10 ดัชนี (USA ถูกตัดทั้งสองฐาน · sector ที่ถูกตัด ≥ 3 ตัว จาก IT/CD/FN/IN/TC) · P4 อยู่ใน S_A ≥ 4 ใน 6 ทั้งสองฐาน (Vietnam, India, UT อยู่แน่)
3. **A-prim:** median ΔR²_oos (E) เทียบฐาน 0.010–0.030 (①a) และ ≤ L2-1 · ต่ำกว่า L2-1/L2-3 ไม่เกิน 0.01
4. **B VIF:** max VIF ของ [f, e(P4)] < 5 ทั้งสองฐาน (ไม่ต้องใช้ fallback) · |corr(e_j, e_k)| train ≤ 0.6 ทุกคู่ · corr(e, f) ช่วง test |·| ≤ 0.3
5. **B-all:** median ΔR²_oos (E) −0.01 ถึง +0.02 · median ΔBIC (E) > 0 → **Q1b ไม่ผ่าน** ทั้งสองฐาน · GRS / PY ไม่ปฏิเสธที่ 5% ช่วง test
6. **B-prim:** median ΔR²_oos (E) 0.005–0.020 (ต่ำกว่า L2-1 0.027 / L2-3 0.015 เพราะได้ส่วนเพิ่มเฉพาะ 40 กอง) · ΔBIC ≤ 0
7. **drop-one (Q1a):** median Δ_j R²_oos ในกองหลักอยู่ภายใน ±0.03 ของค่า single-index ใน L2 (`criteria_P1.csv`) ทุกดัชนี · ผ่าน Q1a ทั้งสองฐาน ≥ 5 ใน 6 ดัชนี (Vietnam บน ①c เสี่ยง: L2 0.066)
8. **span test** (i)(ii) ≤ 1e-12 จริง (เกณฑ์ 1e-10) · (iii) ≤ 1e-9
9. **C placebo:** เลือก 0 ตัวทั้ง shift 26 และ 52 → τ = 0
10. **C-blk:** m = 2–5 · ตัวแรก ∈ {CHINA_ALL, ASIA_EX_JAPAN, USA, IT} (residual) · R²_oos E 0.40–0.55 (สูงกว่า ③a 0.326 · ต่ำกว่า ①a 0.618) · median ΔBIC (E) เทียบ ③a < −20
11. **C-prim:** เพิ่ม R²_oos E จาก C-blk 0.02–0.06 · ยังต่ำกว่า ①a · ในกลุ่ม ACWI_CD 40 กอง ETF ธีม (ARKK/QQQ/SOXX/IBB/ICLN) เป็นตัวเลือก ≥ 15 กอง · THD เป็นตัวเลือกของกองที่ L2 primary = ASEAN อย่างน้อย 1 กอง
12. **elastic net:** ดัชนีที่ π ≥ 0.6 ใน ≥ 7 กลุ่มกอง (①a) ครอบ P4 ≥ 4 ตัว · Europe ได้ π ต่ำกว่า India/Vietnam/HC (แบ่งการเลือกกับดัชนีรวม) · ETF ธีม ≥ 1 ตัวถึงเกณฑ์
13. **Q3:** ตรงกับแอป (country หรือ sector) 50–75% · กลุ่มที่ L2 primary เป็นดัชนีรวมตรงกับ country_primary ของแอปสูงกว่ากลุ่มอื่น (แอปก็ใช้ดัชนีรวมในหน้า 1)
14. **ความเสถียร:** r ดิบ (E) ของ B-all ≥ 0.6 แต่ต่ำกว่าฐาน (0.804) · β ของ e(P4) ไม่มีค่าสำหรับดัชนีที่กองหลัก < 10 (เหมือน L2)
15. **รายเดือน:** ΔR²_oos ของ A-prim / B-prim สูงกว่ารายสัปดาห์ (ตาม L2 8.11)

---

## 10. ข้อจำกัด (ติดไปกับรายงานผล)
- **ช่วง test ถูกใช้เลือกรูปแบบตั้งแต่ L1 และใช้ตัดสิน P1(ข) ของ L2** → ΔR²_oos ของ L3 เป็นหลักฐานไม่อิสระ (ป้าย ข) · ไม่มี holdout อื่น (NAV 2026 มีรู)
- **เกณฑ์ L3 ออกแบบหลังเห็นผล L2** (ป้าย ง) · ค่าตัดนำมาจากค่าที่ล็อกแล้ว แต่การเลือกใช้ drop-one / ΔBIC แทนการนับกอง significant ทำหลังรู้ว่า P1(ก) ไม่แยกแยะ (L2 m2)
- P4 เองถูกเลือกด้วย ΔR²_oos ช่วง test → Q1a ที่ใช้ ΔR²_oos ซ้ำจะ**เอียงไปทาง "ยังอยู่"** (regression to the mean ไม่ถูกทดสอบ) · ตัวถ่วง = ΔBIC (train) และ VIF
- residualize ตรึง β จาก train → ช่วง test ตั้งฉากโดยประมาณ · e ไม่ใช่สินทรัพย์ที่ลงทุนได้ตรง (f เป็นพอร์ตกองที่มีน้ำหนักติดลบ) → α ของ B เป็นเชิงอธิบาย
- ลำดับชั้นของ C (การจัดแม่-ลูก · ธีมใต้ sector · Brazil ใต้ MKT · Vietnam ใต้ Asia ex Japan) = กติกาของ designer · การ orthogonalize ตามลำดับขึ้นกับลำดับที่เลือก (Klein–Chow ผ่าน F-R004) · cap 8 และ τ = กติกาของ designer
- forward selection ใช้ median ΔBIC ข้ามทุกกอง → เอียงไปหาดัชนีกว้าง · ดัชนีที่ช่วยกลุ่มเล็กเข้าได้เฉพาะใน C-prim
- argmax primary (A-prim, C-prim) เลือกจาก train → Δadj R² train เอียงขึ้น · C-prim มี pool 37 ตัว (มากกว่า L2 28) → เอียงมากกว่า
- elastic net: df เป็นค่าประมาณ · λ tune ต่อกอง · บรรยายเท่านั้น
- ETF ส่วนขยาย: ปิดเวลา NY · มีค่าธรรมเนียม · ไม่ผ่านการคัดของ L2 · THD vs TDEX รายสัปดาห์ corr 0.76 · panel ext ถึง 2026-07-31 (ไม่ใช้ปี 2026)
- แอป: primary มาจาก ElasticNet ทั้งช่วง (look-ahead) · universe 209 กองต่างจาก EVAL · หน้า 1 ใช้ country 18 ตัว (มีดัชนีรวม) ไม่ใช่ชุด 11 → Q3 เป็นการเทียบเชิงบรรยายเท่านั้น
- Wald counts ใน B-all ใช้กฎ placebo ของ L2 (single-index) โดยไม่คาลิเบรตใหม่ (design ใหญ่กว่า) · ป้าย
- span test ใช้ tolerance ไม่ใช่ "ทุกบิต" (floating point)
- ทั่วไป: F (18) / O (14) n เล็ก · FundProfile snapshot · NAV class ปันผลไม่รวมปันผล · spike F 119 จุดยังไม่แก้ (ข้อ 3) · ไม่มี MSCI Thailand ใน M28 (THD อยู่เฉพาะ C)

---

## 11. จำนวนรูปแบบและงาน
**3 รูปแบบ (A, B, C) · 8 แถวหลัก (A-prim ×2 · B-all ×2 · B-prim ×2 · C-blk · C-prim) + 4 แถวชุดเข้ม ⚠️ (B-all5 ×2 · B-prim5 ×2) = R1–R12** · แถวอ้างอิง 5 (ไม่ใช่รูปแบบใหม่) · diagnostic: drop-one 12 fit · span test 3 ชุด · placebo C 2 shift · elastic net 2 ฐาน × 207 กอง × 100 subsample · ไม่มีภาคผนวก k
งานรันโดยประมาณ: forward selection ≤ 37 × 8 × 207 fit × 3 (จริง + placebo 2) · PY bootstrap 17 แถว × 999 — ระยะ 1 ไม่นับ trial

---

## ต้องให้ผู้ใช้ตัดสินใจ (ทุกข้อมี **ค่าเริ่มต้นที่แนะนำ** ให้ session หลักใช้ระหว่าง auto run — เปลี่ยนได้ก่อนรันเท่านั้น · หลังเห็นผลต้องติดป้ายตามข้อ 31)
1. **เกณฑ์ L3 (ข้อ 7: Q1a drop-one ≥ 0.02 + ΔBIC ≤ 0 + VIF < 5 ทั้งสองฐาน · Q1b ≥ 0.02 + ΔBIC ≤ 0 · ธง Q2 6 ข้อ)** — แนะนำ: **ใช้ตามนี้** (ใช้ค่าที่ล็อกแล้วทั้งหมด · ติดป้าย "ออกแบบหลังเห็นผล L2")
2. **รูปแบบ A / B / C ครบ** หรือเฉพาะ A + B — แนะนำ: **ครบ 3** (C ตอบว่าชุดดัชนีที่ตีความได้ใกล้ ①a แค่ไหน และเป็นที่เดียวที่ทดสอบ ETF ส่วนขยาย)
3. **ETF ส่วนขยายใช้เฉพาะ C + elastic net** (ไม่ใส่ A/B) — แนะนำ: **ตามนี้** · ทางเลือก: เติมเข้า B (= คัดดัชนีใหม่ ต้องมี scan + placebo แบบ L2 → spec ใหม่) หรือไม่ใช้เลย
4. **ลำดับชั้นของ C** (ตาราง 4.3 · ธีมใต้ sector · cap 8 · กฎ τ จาก placebo) — แนะนำ: **ตามนี้**
5. **e เก็บค่าคงที่ไว้** (α ของกองเท่าเดิม) แทนการใช้ residual ที่หักค่าเฉลี่ย (α เปลี่ยน) — แนะนำ: **เก็บค่าคงที่**
6. **"ทุกบิต" ของ span test = tolerance 1e-10** (floating point ทำให้ hash เท่ากันไม่ได้แม้คณิตศาสตร์เท่ากัน) · regression S003/S005 ใช้ hash เท่ากันทุกบิตตามเดิม — แนะนำ: **ยอมรับ**
7. **B-all ใช้ fallback (ตัด e ตาม VIF) ถ้า VIF ≥ 5** — แนะนำ: **ใช่** (บันทึกเป็น B-all′ แทนแถวเดิม)
8. **เทียบกับแอปด้วย `cache/results.csv`** (อ่านอย่างเดียว · ระยะ 1 · บรรยาย) — แนะนำ: **ใช่**
9. **ภาคผนวก k = 3 / 5** — แนะนำ: **ไม่ทำ** (L2 แสดงว่าแกน P4 และชื่อ factor 1–2 ไม่เปลี่ยนข้าม k · ลดงาน) · ถ้าต้องการ = เพิ่ม B-all/B-prim ที่ k = 3/5 เป็นภาคผนวก (spec addendum)
10. **ฐาน ①a + ①c ทั้งคู่** (ข้อ 46) — แนะนำ: **ทั้งคู่** (Q1a ต้องผ่านทั้งสองฐาน)
