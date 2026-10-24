# S012_L1EO — factor แยกกอง E / กอง O · factor ภายนอกชุดใหม่แข่งกับชุดเดิม · รายงานราย factor (spec ลงทะเบียนล่วงหน้า)

ผู้เขียน: factor-designer · วันที่ 2026-10-23 · งาน **F5-EO** (BRIEF 108–114) · **เชิงอธิบาย · ไม่นับ trial · ไม่แตะ `trials.csv`**
สถานะ: **ฉบับแก้ตามการตัดสินของผู้ใช้หลังดูตารางจับคู่ (BRIEF 115 · 2026-10-23)** → reviewer รีวิว spec → analyst รัน · เกณฑ์ข้อ 8 **ล็อกแล้ว** (BRIEF 115(4) · ยืนยันอีกครั้งตอนสรุป)

อ้างอิง (อ่านครบ): `BRIEF.md` (ข้อ 1–114) · แผน `factors-hazy-thimble.md` · `research/F-R006_external_factors_EO.md` (sha256 `8706cadd…0772`) · `data/QA_EO.md` (`64e12139…c906`) ·
`data/factor_groups_eo.csv` · `data/aum_fam.parquet` · `reports/PHASE1_SUMMARY.md` · `L1_summary.md` · `L3_summary.md` · `L4_summary.md` · `specs/S002` · `S003` · `S006` · `S009` ·
รีวิว spec `S006` · `S007` · `S010` · `S011` · `lib/` (`pca` · `nfactors` · `samples` · `regress` · `scorecard` · `l2` · `l3` · `l4` · `external` · `hybrid` · `io_l1`)

**ไฟล์คู่ของ spec นี้ (ล็อก):** `specs/S012_group_map.csv` (232 กอง · **sha256 `898a86867b3f832060f7620d039fd95338d24e1bb71f531d76bb58004223fceb`** · แทนฉบับที่ผู้ใช้ดู `311ed4c8…16a6`)
สร้างโดย `scratch/factor-designer_s012_structure.py` (sha256 `5d1c84749ca571dac73f26c85e905c2c65a9e52b6226472df4a4526ff28b9e37`) → `scratch/factor-designer_s012_structure.json`
**การตรวจของ designer = โครงข้อมูลเท่านั้น:** ชื่อกอง / รหัส / policy / Fund Class / Registration_date / ธงใน FundProfile · จำนวนแถวที่ไม่ว่างของผลตอบแทน (notna) · คู่ซ้ำ `dup_pairs.csv` ·
นับความครอบคลุมของตัวเทียบ M1 จาก `runs/S005/primary_index.csv` · **ไม่ได้ดูค่าผลตอบแทนกอง ไม่ได้ fit model** · ตัวเลข corr ของ factor ภายนอกยกมาจาก `QA_EO.md` (ไม่ได้ตรวจซ้ำเอง)

> **ป้ายบังคับ (ติดทุกตารางผลตามที่เกี่ยว):**
> (ก) k\* ของ E-PCA ใช้ `combine_k` ที่รวม ED ซึ่งตรงเฉพาะแหล่งรอง [ข้อ 22, 47] ·
> (ข) **ช่วง test 2024–2025 ถูกใช้ซ้ำตั้งแต่ระยะ 1** (เลือก ①a/①c · P4 · L3-B · ช่วงประมาณ α) → R²_oos ของงานนี้ **ไม่ใช่หลักฐานนอกช่วงที่อิสระ** แม้ factor KF / JKP / GLD จะเป็นข้อมูลใหม่ ·
> (ค) **การออกแบบ (pool · กลุ่ม · เกณฑ์) ทำหลังเห็นผลระยะ 1** (F-R006 ใช้บทเรียน L1–L4) ·
> (ง) **U_E / U_O มี look-ahead** (อายุวัด ณ 2025-12-31) และ **survivorship** (BRIEF 109) ·
> (จ) **กอง O มีน้อย** (13 หน่วย · EVAL 12) → รายงานรายกอง / กลุ่มย่อยเป็นหลัก · GRS / ความเสถียรของ O "N น้อย" ·
> (ฉ) factor long–short (KF · JKP · AQR · TERM · REIT_e · e_* · PC · RPC) **ลงทุนไม่ได้** · KF/JKP/AQR/TERM เป็น USD ไม่แปลงบาท (BRIEF 110) ·
> (ช) **KF WML ทบรายวันต่างจากไฟล์รายเดือนทางการ** (corr 0.94 · QA_EO §5) ·
> (ซ) factor กลุ่มกำหนดจาก**ชื่อกอง** (ชื่ออาจไม่ตรงกับสิ่งที่ถือ · Sensoy 2009) · FundProfile เป็น snapshot ·
> (ฌ) α ของแถว PCA = α เทียบพอร์ตกองเพื่อน · α ของแถว X = α เทียบ factor ภายนอก (ซึ่งบางตัวลงทุนไม่ได้) ·
> (ญ) อนุกรม "ต่อรหัส" 4 กองสร้างโดยกติกาของ designer (ข้อ 2.3) ·
> (ฎ) ETF / MSCI ปิดเวลา NY · NAV ไทยออกไม่พร้อมกัน → Dimson lag 1 ·
> (ฏ) JKP จบ 2025-12-31 → ไม่มีมุม 2026

---

## 0. ข้อเท็จจริงเชิงโครงสร้าง (designer นับเอง · notna เท่านั้น)

"หน่วย" = กองหลังต่อรหัส (ข้อ 2.3) · แถว train นับแบบ Dimson (ไม่นับแถวแรก 2021-01-08)

| เรื่อง | E | O | ผลต่อ spec |
|---|---|---|---|
| U (รหัสใน `aum_fam.parquet` · `in_U`) | 218 | 14 (ทอง 8 · REIT 6) | ตรง QA_EO §9.1 · กอง F ใน U = 0 |
| หน่วยหลังต่อรหัส | **215** | **13** (ทอง 7 · REIT 6) | ต่อ 4 คู่ (ข้อ 2.3) |
| fit ได้ (≥ 104 แถว train) = **SEL** | 163 | 12 | ชุดที่ใช้คัด factor (train ล้วน) |
| **EVAL** (≥ 104 train · ≥ 52 test) | **160** | **12** | ชุดคะแนนหลัก |
| EVAL52 (≥ 52 · ≥ 52) | 196 | 13 | ภาคผนวก (O: ตารางรายกองใช้ชุดนี้) |
| **STAB** (EVAL · ≥ 104 แถวทั้ง H1 และ H2) | 141 | 12 | ความเสถียร |
| ตัดซ้ำ (`dedup_keep` · คู่ L0 corr > 0.99 ที่แปลงเป็นหน่วย) | 199 (ตัด 16) | 13 (ตัด 0) | เฉพาะตอนสร้าง PCA |
| PCA balanced (ตัดซ้ำ · ครบ 156 สัปดาห์ train) | **96** | 7 | E-PCA-a1 |
| PCA unbalanced (ตัดซ้ำ · ≥ 52 สัปดาห์ train) | **185** | 13 | E-PCA-a2 · O-PCA |
| ไม่มีแถว train เลย / ไม่มีแถว test เลย | 4 / 0 (หลังต่อ) | 0 / 0 | ASP-INDIA-A · ASP-S&P500-A · ASP-USSMALL-A · K-INDIA-A(A) |
| Fund Class ซ้ำ (หลาย class ของกองเดียว · ไม่ต่อ) | MCHINA 2 · MGA 3 · MGF 3 | – | คงทุกรหัสในการประเมิน (แผนข้อ 9) · นับ 1 ในการนับกลุ่ม |
| class ปันผล | 16 | 2 (IREITG · PRINCIPAL GREITs) | ธง (NAV ไม่รวมปันผล) |
| FX Risk Flag = N (FundProfile) | 18 | 2 (K-GOLD-A(A) · PRINCIPAL iGOLD-A) | กลุ่มย่อยทอง |
| กอง E ที่มี primary ของ L2 (ตัวเทียบ M1) | 146 (primary ∈ P4: 28) | – | M1 ของกองอื่น = ①a + FX |

- เหตุที่ EVAL < U ราว 55 หน่วย: class ตัวแทนของหลาย family ใน panel L0 เริ่มปี 2022–2023 (แถว train < 104) — **ไม่แก้ L0** (เหมือนระยะ 1) · รายชื่ออยู่ใน CSV คอลัมน์ `fit_train` / `eval` / `note`
- กอง Eastspring ที่เปลี่ยนรหัส (E 26 · O 4) **ไม่อยู่ใน U** ตาม BRIEF 114(1) (ติดป้าย · U_O เสีย ES-GOLD / ES-GOLDBULLION-H / ES-GOLDS / ES-GPROP)
- ช่วงข้อมูล: weekly ช่วงหลัก 260 แถว (train 156 · test 104) · factor EO ทุกตัวไม่มี NaN ในช่วงหลัก · JKP NaN ตั้งแต่ 2026-01-02 (QA_EO §1–2)

---

## 1. คำถามและสมมติฐาน

**คำถาม:** (Q1) เมื่อแยก E กับ O และตัด F แล้ว factor ทางสถิติของ E ล้วนเป็นอย่างไร · (Q2) factor ภายนอกชุดใหม่ (ตลาดโลก + factor ร่วมที่คัดด้วยกติกาล็อก + factor กลุ่มจากชื่อกอง) อธิบายกอง E ได้ใกล้ PCA แค่ไหน และดีกว่าชุดเดิมที่ลงทุนได้ (③a) ไหม ·
(Q3) ชุดตายตัวตามกลไก (ทอง / REIT) อธิบายกอง O ได้ดีกว่า ①a / ①c / ③a ไหม · (Q4) **factor แต่ละตัว**มีส่วนแค่ไหน (ใส่เดี่ยว · drop-one · Shapley · กองที่ β มีนัย · ชื่อ · VIF · ความเสถียร)

| # | สมมติฐาน (ความคาดหมายที่ใช้ตรวจตัวเอง · ไม่ใช่เกณฑ์ผ่าน) | ที่มา |
|---|---|---|
| H-E0 | PCA ของ E ล้วนให้ PC1 ≈ ตลาดโลก และ PC2 ≈ จีน เหมือน ①a | L1 · L2 |
| H-E1 | e_CHINA ถูก stepwise เลือกในสองรอบแรก และ drop-one ΔR²_oos (E) > 0 | F-R006 H-E1 |
| H-E2 | factor กลุ่มจากชื่อกองให้ median ΔR²_oos ในกลุ่มตัวเอง ≥ 0.02 ในอย่างน้อยครึ่งหนึ่งของกลุ่มที่ผ่าน ≥ 5 | F-R006 H-E2 / H-E3a |
| H-E7 | style KF ผ่าน stepwise ≤ 2 ตัว · HML มี β ติดลบที่มีนัยในกลุ่ม TECH / INNOV เกินครึ่ง | F-R006 H-E7a/b |
| H-E8 | JKP-EM ช่วยเฉพาะกอง EM / ASIA / CHINA ไม่ใช่กอง GLOBAL | F-R006 H-E8 |
| H-O1 | กองทอง: β(GOLD_XS) ∈ [0.85, 1.05] · β(FX) แยกกอง FX Risk Flag N (≈ 0) กับ Y (> 0.5) · median R²_oos ≥ 0.85 · \|α\| ≈ TER | F-R006 H-O1a–c |
| H-O2 | กอง REIT: O-X ให้ median R²_oos สูงกว่าตัวเทียบที่ดีที่สุด ≥ 0.05 · TERM β > 0 ในกอง REIT ส่วนใหญ่ | F-R006 H-O2 / H-O3 |

---

## 2. ข้อมูลและชุดกอง

### 2.1 ไฟล์ (ตรวจ sha256 ก่อนรัน · ไม่ตรง → หยุด)

| ไฟล์ | ใช้ทำ | sha256 |
|---|---|---|
| `data/panel_weekly.parquet` / `panel_monthly.parquet` | ผลตอบแทนกอง | `95c16ee6…270b` / `e8e8cb5d…ccaed` (manifest.json) |
| `data/factors_weekly.parquet` / `factors_monthly.parquet` | MSCI · RF_BOT · SHV / IEF / AGG · style ETF | `115b8713…7a8` / `f7c4248b…b72` |
| `data/factors_ext_weekly.parquet` / `factors_ext_monthly.parquet` | ARKK · ICLN · REET (THB/USD) | `3105b6e7…e5da5e296` / `ce53d371…db792` |
| `data/factors_eo_weekly.parquet` / `factors_eo_monthly.parquet` | KF · JKP · AQR · GLD · VNQ · REIT เอเชีย · FRED | `87b79350…fca` / `c13c36e7…ef82f` (manifest_eo.json) |
| `data/aum_fam.parquet` | U_E / U_O (`in_U`, `policy`, `o_kind`) | `e442f6ae…db46` |
| `data/universe.csv` · `data/dup_pairs.csv` | n_weeks · div_flag · คู่ซ้ำ | `fdfb7830…7252` · `b1f0f0c7…aef3` |
| `base_data/FundProfile.csv` (อ่านอย่างเดียว) | ชื่อ · Fund Class · Registration_date · FX Risk Flag | `95162814…cfaf` |
| `specs/S012_group_map.csv` | ตารางจับคู่กลุ่ม (ล็อก · BRIEF 115) | `898a8686…fceb` |
| `runs/S003/factors_S003_weekly.parquet` | ①a / ①c (ตัวเทียบ · ไม่ประมาณใหม่) | `be3ceb2e…944ac` |
| `runs/S005/primary_index.csv` · `runs/S006/resid_B_coef.csv` | M1 (ตัวเทียบเท่านั้น) | `5a94ab9b…275c` · `71af654f…eef0b` |

ห้ามใช้: `*_late_*` · `*_lvl` (ยกเว้นไม่มี) · `*_est_ret` · `Gold` (GC=F · ใช้ GLD แทน) · แถว > 2025-12-26 ในทุกการ fit / คัด / residualize

### 2.2 ช่วงเวลาและกติการ่วม (เหมือน S002/S003/S006)
train 2021-01-08 → 2023-12-29 (Dimson 155 แถว) · test 2024-01-05 → 2025-12-26 (104) · H1 2021-01-08 → 2023-06-30 · H2 2023-07-07 → 2025-12-26 ·
pseudo-train 2021-01-08 → 2022-06-24 · pseudo-test 2022-07-01 → 2023-12-29 (เหมือน L3) · Dimson lag 1 ทุก regression (β = b0 + b1 · **lag 0 + lag 1 = factor เดียว** ทุกตาราง) ·
HAC Newey–West Bartlett L = 4 (รายเดือน 3) · excess return ของกอง = ret − RF_BOT (`io_l1.load_returns`) · R²_oos ใช้ coef จาก train ไม่ fit ใหม่ · seed 20261015 · เรียง `kind="stable"`

### 2.3 กติกาต่อรหัส (splice · BRIEF 114(2) · ล็อก)
คู่ใน U ที่ (ก) Registration_date เท่ากัน (ข) policy เดียวกัน (ค) ชื่อ EN เท่ากันหลังตัดคำแบรนด์ `TMB` / `EASTSPRING` / `FUND` (ง) ช่วงที่มีผลตอบแทนซ้อนกัน ≤ 1 สัปดาห์ และ (จ) ไม่ใช่ class คู่ขนานของ Fund Class เดียวกัน → **กองเดียวกันเปลี่ยนรหัส → ต่อเป็น 1 หน่วย** ·
อนุกรม = รหัสเก่าทุกแถว + รหัสใหม่เฉพาะแถวหลังแถวสุดท้ายของรหัสเก่า (สัปดาห์ที่ซ้อนใช้รหัสเก่า) · สร้างใน `runs/S012/` เท่านั้น (ไม่แก้ L0)

| หน่วย | รหัสเก่า → ใหม่ | ซ้อน | หลังต่อ train / test | ผล |
|---|---|---|---|---|
| `I-GOLD*` (O) | I-GOLD → IGOLD-G | 1 สัปดาห์ (2023-12-08) | 155 / 104 | เข้า EVAL_O (ค่าเริ่มต้นของ BRIEF 114(2) = 1 กอง) |
| `ES-GINNO*` (E) | TMB-ES-GINNO → ES-GINNO-A | 1 | 155 / 104 | เข้า EVAL_E (กลุ่ม INNOV) |
| `ES-GCG*` (E) | TMB-ES-GCG → ES-GCG-A | 1 | 155 / 104 | เข้า EVAL_E (GLOBAL) |
| `ES-GINFRA*` (E) | TMBGINFRA → ES-GINFRA-A | 1 | 155 / 104 | เข้า EVAL_E (INFRA) |

3 คู่ของ E เข้ากติกาเดียวกับ I-GOLD ทุกข้อ (Registration_date 2020-10-29 / 2020-07-21 / 2016-08-22 เท่ากันในแต่ละคู่) → **ผู้ใช้อนุมัติให้ต่อ (BRIEF 115(3))** · ต่อใน run เท่านั้น (`l1eo.splice_units` → `runs/S012/units_splice.csv`) · panel L0 ไม่ถูกแก้ · ติดป้าย (ญ) ทุกตารางที่มี 4 หน่วยนี้ · test `test_eo_05` (ข้อ 11.2)

### 2.4 ชุดกองต่อวิธี

| ใช้ทำ | ชุด (หน่วย) | หมายเหตุ |
|---|---|---|
| คัด factor ร่วม (stepwise · placebo · pseudo-OOS) | **SEL_E** 163 → ตัวแทนกลุ่มกองอิสระ (ข้อ 4.2) | train ล้วน · ไม่ใช้ข้อมูล test แม้แต่การมีอยู่ |
| สร้าง E-PCA-a1 / a2 · residual PC ของ E-H | PCA balanced 96 / unbalanced 185 (ตัดซ้ำ) | `samples.dedup_keep` ตอนสร้างเท่านั้น (BRIEF 109) |
| คะแนนข้อ 1–4 · รายงานราย factor | **EVAL_E 160** / **EVAL_O 12** (ไม่ตัดซ้ำ · แผนข้อ 9) | ภาคผนวก: EVAL52 · ตัวแทนกลุ่มกองอิสระ · ชุดตัดซ้ำ |
| ความเสถียร | STAB_E 141 / STAB_O 12 | |
| ตารางรายกอง O | EVAL52_O 13 (DAOL-USREIT train 67 แถว · ติดธง) | |
| กลุ่มกองอิสระ | `l2.fund_clusters` (corr ≥ 0.95 · single linkage · ผลตอบแทน train · min_overlap 52) บน SEL_E / EVAL_E | ข้อ 36, 38 |

---

## 3. ตัวแปร (factor) — ทุกตัวเป็นผลตอบแทนส่วนเกินหรือส่วนต่างที่ไม่หักค่าเฉลี่ย

### 3.1 แกนและ pool factor ร่วมของ E (**ล็อก · 11 ตัว + ช่องสำรองที่ไม่ใช้**)
| ชื่อ | นิยาม (คอลัมน์) | หน่วย | ที่มา |
|---|---|---|---|
| **MKT** (แกนบังคับ) | `MSCI_ACWI − RF_BOT` | THB | E0 |
| e_CHINA | `l3.residualize(MSCI_CHINA_ALL_SHARES − RF_BOT, P=[MKT], train)` (lag 0 · เก็บค่าคงที่ · β ตรึงจาก train) | THB | E1 · **ต่างจากสูตร F-R006 ที่ใส่ ACWI_{t−1}** เพราะ lag ใน auxiliary เปลี่ยน span (รีวิว S006 ข้อ B) |
| EMDM | `MSCI_EM − MSCI_WORLD` | THB | E6 |
| TERM | `IEF_USD − SHV_USD` | USD l/s | E4 |
| SMB · HML · RMW · CMA · WML | `KF_DEV_SMB` … `KF_DEV_WML` (ทบรายวันเป็นสัปดาห์โดย data-engineer) | USD l/s | E7 · style หลัก = KF (BRIEF 113) |
| JKP-EM value · momentum | `JKP_EM_value` · `JKP_EM_momentum` (capped VW) | USD l/s | E8 · 2 theme เลือกจากวรรณกรรม (F-R006) |
| FX | `SHV_THB − RF_BOT` | THB | E5 · **แข่งใน pool** (BRIEF 113) |
| ช่องที่ 12 | **ว่าง (ล็อกว่าห้ามเติมภายหลัง)** | – | กันการเติมหลังเห็นผล |

ไม่อยู่ใน pool: style ETF 4 ตัว (ห้ามคู่กับ KF · ใช้ในภาคผนวก A1 เท่านั้น) · AQR (robustness A2) · KF regional (E9 · ดูข้อ 4.4.5) · credit · ดอลลาร์ (FRED) · commodity · TDEX

### 3.2 factor กลุ่มของ E (ข้อ 4.4 · **11 ตัว**) — `e_g = l3.residualize(I_g, P = factor ร่วมของ E-X1, train)` (lag 0 · เก็บค่าคงที่)
| g | I_g | g | I_g |
|---|---|---|---|
| CHINA | `MSCI_CHINA_ALL_SHARES − RF_BOT` · **ถ้า e_CHINA ∈ E-X1 → `MSCI_CHINA_A_SHARES − MSCI_CHINA_H_SHARES`** (e_AH) | HEALTH | `MSCI_ACWI_HC − RF_BOT` |
| ASIA | `MSCI_ASIA_EX_JAPAN − RF_BOT` | TECH | `MSCI_ACWI_IT − RF_BOT` |
| EUROPE | `MSCI_EUROPE − RF_BOT` | INNOV | `ARKK_THB − RF_BOT` |
| USA | `MSCI_USA − RF_BOT` (→ e_USA ≈ USA − ACWI ตาม E2) | INFRA | `IGF_THB − RF_BOT` |
| JAPAN | `MSCI_JAPAN − RF_BOT` | VIETNAM | `MSCI_VIETNAM − RF_BOT` |
| INDIA | `MSCI_INDIA − RF_BOT` | | |

เหตุของกติกา CHINA: ถ้า e_CHINA อยู่ใน E-X1 แล้ว China All จะอยู่ใน span ของ E-X1 พอดี (residual = ค่าคงที่) → ใช้ A − H (ส่วนต่างในจีน · F-R006 E2) แทน · `l2.in_span` ตรวจก่อน fit

### 3.3 กอง O (**ชุดตายตัวตามกลไก · ไม่มีการคัดเลือก** · BRIEF 110/113)
| กลุ่ม | factor (K) | นิยาม |
|---|---|---|
| ทอง (7 หน่วย) | GOLD_XS · FX (2) | `GLD_USD − SHV_USD` · `SHV_THB − RF_BOT` |
| REIT (6) | MKT · REIT_e · FX · TERM (4) | REIT_e = `l3.residualize(REET_USD − SHV_USD, P=[MKT], train)` |
| O-X′ (ตัวเทียบอย่างง่าย) | ทอง: `GLD_THB − RF_BOT` · REIT: `REET_THB − RF_BOT` (1) | O5 |
| tilt ภูมิภาค (ภาคผนวก · รายกอง) | REIT-US + `VNQ_USD − REET_USD` · REIT-Singapore + `REITCLRSI_THB − REET_THB` | O4 · REIT-Japan ไม่มีใน U_O |

### 3.4 ตัวเทียบเดิม (ไม่ประมาณใหม่ · ใช้เฉพาะเป็นตัวเทียบ · BRIEF 112)
①a = `1a__PC1..4` · ①c = `1c__PC1..4` (`runs/S003/factors_S003_weekly.parquet` · สร้างจาก E/F/O ปน · น้ำหนักจาก train ของระยะ 1) · ③a = `external.line3(F, "3a")` ·
**M1** = ①a + FX + e_p(i) ของ P4 เฉพาะกองที่ primary ของ L2 (form `1a@4`) ∈ P4 (`l4.e_from_s006` + `l3.perfund_from_primary` + `l3.fit_perfund` แบบ `runs/S009/run.py`) · กองที่ไม่มี primary (กองที่ไม่อยู่ใน EVAL ระยะ 1) = ①a + FX ·
ป้าย: ①a/①c/P4/primary ถูกเลือกด้วยช่วง test ของระยะ 1 → ใช้ได้เฉพาะเป็นตัวเทียบ

---

## 4. วิธี — กอง E (แข่งกัน)

### 4.1 (a) E-PCA ของ E ล้วน — 2 รูปแบบ
- **k\*:** บน Z ของ PCA balanced 96 (z จาก μ, σ ของ train) → IC_p2 (kmax 10) · ER (kmax 10) · ED (kmax 10 · `nfactors.onatski_ed`) · PA (500 permutation · seed) → `nfactors.combine_k` · รายงาน IC_p1 · GR · R² ที่ k = 1…8 (บรรยาย)
- **E-PCA-a1 (หลัก):** `pca.pca_fit(X_train, k*, "corr")` บน balanced 96 → Λ, σ · factor return ทุกช่วง = `pca.factor_returns(X, Λ, σ, min_frac=0.5)` (**ไม่หัก μ** → α เป็น pricing error เทียบพอร์ต PC)
- **E-PCA-a2 (EM):** `pca.em_pca(X_train, k*)` บน unbalanced 185 → `factor_returns` แบบเดียวกัน
- ไม่ทำ covariance-PCA (BRIEF: เป็นรูปแบบเสริม · ลดจำนวนรูปแบบ) · ไม่หมุน (ชื่อจาก corr ข้อ 6.6)

### 4.2 (b) E-X0 → E-X1: forward stepwise ของ factor ร่วม (train เท่านั้น · ล็อก)
1. **ตัวแทน:** กลุ่มกองอิสระบน SEL_E (ข้อ 2.4) → ตัวแทน 1 หน่วยต่อกลุ่ม = แถว train มากสุด (เสมอ → FundCode ตามตัวอักษร) · บันทึก `sel_reps.csv` **ก่อน**ขั้นถัดไป
2. **E-X0 = {MKT}** · รอบ r: ทุก candidate j ∈ pool \ ที่เลือกแล้ว → ต่อตัวแทน i: fit Dimson `y_i ~ M` และ `y_i ~ M + j` บนแถว train เดียวกัน → ΔBIC_ij · score_j = **median_i ΔBIC_ij** (median ข้ามกลุ่มกองอิสระ · บทเรียน C-blk) · j\* = argmin (เสมอ → ลำดับใน pool ตามตาราง 3.1)
3. **เพิ่ม j\* เมื่อผ่านทุกด่านตามลำดับ · ด่านใดตก → หยุดทั้งกระบวนการ (ไม่ลองตัวอันดับถัดไป):**
   - (G1) เพดาน: จำนวน factor ร่วมรวม MKT ≤ **6** (เพิ่มได้ ≤ 5 ตัว)
   - (G2) score_j\* ≤ **τ** (τ = −2 ถ้า placebo ไม่เลือกตัวใด · ข้อ 4.3) — ค่าตัด −2 ของ Kass–Raftery **ยังไม่ยืนยันแหล่ง** · เป็นค่าที่ผู้ใช้รับใน BRIEF 113
   - (G3) **pseudo-OOS:** fit `M` และ `M + j*` บน pseudo-train · ทำนาย pseudo-test ด้วย coef ตรึง → median_i (R²_pseudo(M + j\*) − R²_pseudo(M)) ต้อง **> 0** · ตัวแปร residualize (e_CHINA) **ประมาณ β ใหม่จาก pseudo-train** ในด่านนี้ · ตัวแทนที่มี < 52 แถวใน pseudo-train หรือ < 26 ใน pseudo-test ไม่นับ (รายงาน n)
4. **E-X1 = MKT + ตัวที่ถูกเลือก** · log ทุกรอบ: score ของ**ทุก** candidate · อันดับ 1–2 · ผลแต่ละด่าน · เหตุที่หยุด · score ดีที่สุดของรอบที่หยุด (ให้เห็นว่าเพดานผูกมัดไหม)
5. **รายงานจำนวน factor ที่ลองทั้งหมด** = Σ จำนวน candidate ที่ประเมินทุกรอบ (รวม placebo) + factor กลุ่ม 11 + residual PC + PCA

### 4.3 placebo ของ stepwise (ทำ**ก่อน** selection จริง · กฎ τ แบบ L3-C)
รันข้อ 4.2 ทุกขั้น (G1–G3 ด้วย τ₀ = −2) โดยแทน candidate ทุกตัวด้วย `l2.circular_shift(pool, mask_train, s)` s ∈ {26, 52} (MKT ไม่เลื่อน) → บันทึกจำนวนที่ถูกเลือก + score ดีที่สุดรอบแรก τ_s ลง `placebo_E.json` **ก่อน** selection จริง ·
**กฎ:** placebo เลือก 0 ตัวทั้งสอง shift → τ = −2 · เลือก ≥ 1 ตัวที่ shift ใด → τ = min(−2, min_s τ_s) + ป้าย "selection ต้องปรับเกณฑ์ตาม placebo" (= ตีความ F-R006 §4 ข้อ 2(ง) "ถ้าเลื่อนแล้วยังถูกเลือก → หยุด")

### 4.4 (b ต่อ) E-X2: factor กลุ่ม ≤ 1 ตัวต่อกอง จากชื่อกอง (ล็อกก่อนเปิดผลตอบแทน)

#### 4.4.1 กฎคำในชื่อกอง (BRIEF 115(1) · ใช้ชื่อ EN ใน FundProfile · ตัวพิมพ์ใหญ่ · ตัด `EX JAPAN` / `EX US` ก่อน · คำแรกที่ตรงตามลำดับชนะ)
- **คำที่ให้ factor = เฉพาะคำของ F-R006** (§2 สาย ⑤ ตัวอย่างธีม และ E2 ตัวอย่างประเทศ) อ่านเป็น **รากคำที่ขึ้นต้นคำ** (`\bSTEM` · เพราะ F-R006 เขียนเป็นราก เช่น `INNOVAT` · `GENOM` · `RENEW` · `NEWENGY`) → `INDIA` จับ INDIAN · `JAPAN` จับ JAPANESE · `EURO` จับ EUROPE/EUROPEAN · `TECH` จับ TECHNOLOGY/FINTECH (F-R006 รวม fintech เข้า tech)
- **คำที่ designer เพิ่มเองถูกตัดทั้งหมด:** CLEAN (`EV` · `BATTERY` · `TRANSITION` · `PLANETARY` · `GREEN ENERGY`) · TECH (`INTERNET` · `METAVERSE` · `BLOCKCHAIN` · `E-COMMERCE` · `ESPORT` · `ARTIFICIAL`) · HEALTH (`PHARMA`) · PROP (`REAL ESTATE`) · ASEAN (`AEC` · `INDONESIA` · `MALAYSIA` · `PHILIPPIN` · `SINGAPORE` · `SOUTHEAST`) · EUROPE (`CONTINENTAL`) · VIETNAM (`VIET` · `VN`)
- **คำพ้องของประเทศเดียวกัน (ข้อเปิด · ข้อ 14):** `CHINESE` · `BHARAT` · `NIPPON` · `AMERICA` · `U.S.` · `NASDAQ` / `NDQ` — ค่าเริ่มต้นที่ใช้: **คงไว้** (ไม่เปลี่ยนการผ่าน ≥ 5 ของกลุ่มใด · เปลี่ยนสมาชิก 7 กอง · คอลัมน์ `alt_factor_no_synonym`)
- **ป้ายของ designer (ไม่ใช่กลุ่มของ F-R006) → ไม่ให้ factor ไม่ว่ามีกี่กอง:** TH · METAL · EM · FIN · CONSUMER · STYLE · GLOBAL · NONE (ยกเว้น ASIA ซึ่งผู้ใช้รับค่าเริ่มต้นแล้ว · BRIEF 115(5))

| ลำดับ | กลุ่ม | คำตาม F-R006 (`\b` นำหน้า) | คำพ้อง (ข้อเปิด) | I_g | ให้ factor? |
|---|---|---|---|---|---|
| 0 | TH | `SET` · `THAI…` | | (TDEX) | ป้ายเท่านั้น |
| 0 | METAL | `GOLD` · `SILVER` · `MINING` · `METALS?` | | (GLD) | ป้ายเท่านั้น |
| 1 | CHINA | `CHINA` | `CHINESE` | China All / e_AH | ✓ |
| 1 | INDIA | `INDIA…` | `BHARAT…` | MSCI_INDIA | ✓ |
| 1 | VIETNAM | `VIETNAM` | | MSCI_VIETNAM | ✓ |
| 1 | JAPAN | `JAPAN…` | `NIPPON` | MSCI_JAPAN | ✓ |
| 1 | KOREA · TAIWAN · BRAZIL | ชื่อประเทศ (C11) | | C11 | ✓ (ไม่มีกองใน U_E) |
| 1 | ASEAN | `ASEAN` | | MSCI_ASEAN | ✓ |
| 1 | EUROPE | `EURO…` | | MSCI_EUROPE | ✓ |
| 1 | USA | `US` · `USA` · `S&P` (ทั้งคำ) | `U.S.` · `AMERICA…` · `NASDAQ` · `NDQ…` | MSCI_USA | ✓ |
| 1 | ASIA | `ASIA…` · `PACIFIC` · `APAC` | | MSCI_ASIA_EX_JAPAN | ✓ (designer · ผู้ใช้รับ) |
| 1 | EM | `EMERGING` · `EM` · `GEM` | | – | ป้ายเท่านั้น |
| 2 | HEALTH | `HEALTH…` · `MEDIC…` · `BIOTECH` · `GENOM…` | | MSCI_ACWI_HC | ✓ |
| 2 | CLEAN | `CLEAN` · `RENEW…` · `NEW ENERGY` / `NEWENGY` · `CLIMATE` | | ICLN | ✓ |
| 2 | INFRA | `INFRA…` | | IGF | ✓ |
| 2 | PROP | `PROP…` · `REIT…` | | REET | ✓ |
| 2 | FIN | `FINANCIAL` · `FINANCE` · `BANK…` | | – | ป้ายเท่านั้น |
| 2 | CONSUMER | `BRAND(S)` · `LUXURY` · `CONSUMER` · `LIFESTYLE` | | – | ป้ายเท่านั้น |
| 2 | INNOV | `INNOVAT…` · `DISRUPT…` · `NEXT GEN…` / `NEXTGEN` | | ARKK | ✓ |
| 2 | TECH | `TECH` (ในคำ) · `DIGITAL` · `AI` · `ROBOT…` · `CYBER…` · `CLOUD` · `SEMI…` | | MSCI_ACWI_IT | ✓ |
| 3 | STYLE | `DIVIDEND` · `INCOME` · `LOW VOLATILITY` · `VALUE` · `QUALITY` · `MOAT` · `SMALL` · `MID` | | – | ป้ายเท่านั้น |
| 4 | GLOBAL | `GLOBAL` · `WORLD` · `INTERNATIONAL` | | – | ป้ายเท่านั้น |
| – | NONE | ไม่มีคำตรง | | – | – |

**หลักลำดับ:** ประเทศ / ภูมิภาค > ธีม sector (HEALTH · CLEAN · INFRA · PROP) > INNOV > TECH > style > global ·
ตัวอย่างผลของลำดับ: Asia Technology → ASIA · US Technology / US Financial → USA · China Healthcare / China Green Energy → CHINA · Innovative Healthcare → HEALTH · Innovation & Technology / Next Generation Internet / Fintech Innovation → INNOV · Battery and EV **Technology** → TECH

#### 4.4.2 กลุ่มต้อง ≥ 5 กอง + กลุ่มแม่ (ล็อก · BRIEF 115(2))
- **ฐานการนับ:** จำนวนหน่วยใน **U_E ทั้งหมด** ของกลุ่ม (ตามตัวอักษร F-R006 §4 · หน่วยหลังต่อรหัส · Fund Class ซ้ำนับ 1) · รายงาน n ที่ fit ได้ และ n ใน EVAL คู่กัน · กลุ่มที่ผ่านเกณฑ์ U แต่ EVAL < 5 (INDIA 4 · INFRA 3) ติดป้าย **"n เล็ก"** ในคำตัดสินกลุ่ม
- **กลุ่มแม่:** ประเทศเอเชีย (CHINA · INDIA · VIETNAM · ASEAN · KOREA · TAIWAN) ที่มี < 5 กองใน U → **ASIA** (ลำดับชั้น HIER ของ L3) · ผลตามเกณฑ์ U: **INDIA มี 6 กองใน U → เป็นกลุ่มของตัวเอง (e_INDIA)** (ไม่ใช้คำพ้อง `BHARAT` ก็ยังมี 5) · **ASEAN มี 2 → รวมใน ASIA** · VIETNAM 9 → กลุ่มของตัวเอง
- **กลุ่มย่อยที่ไม่ถึง 5 รวมในกลุ่มแม่:** SEMI (3) → TECH · BIOTECH/GENOME (2) → HEALTH · CHINA A-share (4) / China tech (2) → CHINA
- กลุ่มของ F-R006 ที่ < 5 → **ไม่มี factor กลุ่ม:** CLEAN (4) · PROP (2) · กองที่ไม่มี factor กลุ่ม = E-X1 · ไม่ใช้ primary ของ L2 (เลือกด้วยช่วง test) ในการจับคู่

#### 4.4.3 ตารางจำนวนกองต่อ factor กลุ่ม (จาก `S012_group_map.csv` sha `898a8686…fceb`)
หน่วย = กองหลังต่อรหัส · "ใน U (นับกลุ่ม)" = เกณฑ์ ≥ 5 (Fund Class ซ้ำนับ 1) · "EVAL ที่ได้ factor" = จำนวนหน่วยใน EVAL_E ที่ถูก fit ด้วย factor นี้ (MCHINAGA / MCHINAGD นับ 2)

| factor กลุ่ม | I_g | กลุ่มชื่อที่รวม | **ใน U (นับกลุ่ม)** | fit ได้ | EVAL (นับกลุ่ม) | EVAL ที่ได้ factor | ผ่าน ≥ 5 (U) |
|---|---|---|---|---|---|---|---|
| e_CHINA(grp) / e_AH | China All / A − H | CHINA (+ A-share 4 · China tech 2) | **27** | 24 | 24 | 25 | ✓ |
| e_USA | MSCI USA | USA | **16** | 9 | 9 | 9 | ✓ |
| e_HC | ACWI HC | HEALTH (+ BIOTECH 2) | **15** | 14 | 14 | 14 | ✓ |
| e_ASIA | ASIA_EX_JAPAN | ASIA 13 + ASEAN 2 (กลุ่มแม่) | **15** | 13 | 13 | 13 | ✓ |
| e_IT | ACWI IT | TECH (+ SEMI 3) | **15** | 12 | 12 | 12 | ✓ |
| e_EUROPE | MSCI EUROPE | EUROPE | **14** | 10 | 10 | 10 | ✓ |
| e_JAPAN | MSCI JAPAN | JAPAN | **12** | 8 | 7 | 7 | ✓ |
| e_ARKK | ARKK | INNOV (รวม `ES-GINNO*`) | **11** | 10 | 10 | 10 | ✓ |
| e_VIETNAM | MSCI VIETNAM | VIETNAM | **9** | 6 | 5 | 5 | ✓ |
| e_INDIA | MSCI INDIA | INDIA | **6** | 4 | 4 | 4 | ✓ (EVAL n เล็ก) |
| e_IGF | IGF | INFRA (รวม `ES-GINFRA*`) | **6** | 3 | 3 | 3 | ✓ (EVAL n เล็ก) |
| ไม่มี — CLEAN | (ICLN) | CLEAN | 4 | 4 | 4 | – | ✗ |
| ไม่มี — PROP | (REET) | PROP | 2 | 1 | 1 | – | ✗ |
| ไม่มี — ป้าย designer | – | CONSUMER 5 · EM 4 · FIN 2 · METAL 2 · TH 1 | – | – | 1 · 4 · 1 · 1 · 1 | – | ป้ายเท่านั้น |
| ไม่มี — ไม่มีกลุ่ม | – | GLOBAL 25 · NONE 15 · STYLE 4 | – | – | 21 · 10 · 1 | – | – |
| **รวม** | | | U 215 หน่วย: **147 ได้ factor · 68 ไม่มี** | | | **EVAL_E 160: 112 ได้ factor · 48 ไม่มี** | |

**11 factor กลุ่ม** (+ e_AH แทน e_CHINA(grp) แบบมีเงื่อนไข · ใช้ได้ตัวเดียว) · ถ้าไม่ใช้คำพ้อง (ข้อเปิด): ชุด factor เท่าเดิม 11 ตัว · 7 กองย้ายเป็น "ไม่มี" (K-CHX · B-BHARATA · ASP-NGF · B-NIPPON · ABAGS (EVAL) · ASP-USSMALL-A · KKP NDQ100-H) → EVAL ที่ได้ factor 107

**เทียบกับฉบับที่ผู้ใช้ดู (`311ed4c8…`):** + e_INDIA (เดิมรวมใน ASIA) · + e_IGF (เดิมตกเพราะนับ EVAL) · − e_ICLN (CLEAN เหลือ 4 เมื่อตัดคำ EV/BATTERY · UEV ย้ายไป TECH ด้วยคำ TECHNOLOGY · K-PLANET → NONE) · TECH 18 → 15 (M-META · ONE-METAVERSE · LHESPORT → NONE · ONE-GECOM → GLOBAL · + UEV) · ASIA 22 → 15 (India ออก · ES-INDONESIA → NONE) · CONSUMER ยังไม่มี factor (ป้าย designer · 5 กองใน U แต่ไม่ใช่กลุ่ม F-R006)

#### 4.4.4 กองที่จับคู่ไม่ได้ / กำกวม (ทั้งหมดอยู่ในคอลัมน์ `note`)
- **จับคู่ไม่ได้ (NONE · 15):** ASP-X · B-FUTURE · B-SIP · K-CHANGE · KT-MFE · M-EDGE · MEGA10-A · ONE-DISC · UGFT · USUS · **ใหม่จากการตัดคำ:** ES-INDONESIA · K-PLANET · LHESPORT · M-META · ONE-METAVERSE
- **คำพ้อง (ข้อเปิด):** K-CHX (Chinese) · B-BHARATA (Bharata) · ASP-NGF / B-NIPPON (Nippon) · ABAGS (American) · ASP-USSMALL-A (U.S.) · KKP NDQ100-H (NDQ)
- **กำกวม — ลำดับ:** MGTECH (Next Generation Technology) / TNEXTGEN · DAOL-CYBER (Next Generation Internet) → ARKK ไม่ใช่ ACWI IT · K-ATECH · MATECH (Asia Technology) → ASIA · ES-USTECH · TUSTECH · TUSFIN → USA · KT-EUROTECH → EUROPE · UEV (Battery and EV Technology) → TECH
- **ชื่อไม่บอก holding ชัด:** TCHT5M4 (China Equity **Trigger** Fund) · FCSCBSETE (SCB **SET** Index Fund · policy E · FIF Flag = Y แต่ชื่อเป็นดัชนี SET → ป้าย TH) · KT-MINING / DAOL-GOLD (ป้าย METAL)
- **hedge ตามชื่อ (ข้อมูลประกอบ · ไม่ใช้จับคู่):** -H / HEDGED 10 กอง · UH / Unhedged 3 กอง

#### 4.4.5 factor ที่เสนอใน F-R006 แต่ไม่ใช้ (กลุ่มไม่ถึง 5 ใน U)
ICLN (CLEAN 4) · SOXX (SEMI 3) · IBB (BIOTECH 2) · KWEB (China tech 2) · CHINA_A (4) · REET ฝั่ง E (PROP 2) · KF regional SMB (กองหุ้นเล็ก US 2 · Japan 3 · Europe 3 · Asia 1 → แต่ละ factor < 5 · กองหุ้นเล็กได้ factor ประเทศแทน) · ACWI CD (CONSUMER เป็นป้าย designer)

#### 4.4.6 การประมาณ E-X2
ต่อกอง i ที่มี g(i): `l3.fit_perfund(R, base = E-X1, per_fund = {i: e_g(i)}, …)` · กองอื่น = E-X1 · VIF ต่อกอง (lag 0 และ Dimson) ของ [E-X1, e_g] · ไม่มี fallback เมื่อ VIF ≥ 5 (รายงาน + ใช้ในคำตัดสินราย factor ข้อ 8.3)

### 4.5 (c) E-H: hybrid = E-X1 + residual PC
`hybrid.residual_pc(R, F = E-X1, mask_train, funds = PCA balanced 96, kmax = 3)` (k_res = IC_p2 · เพดาน 3 ตาม F-R006) → `hybrid.hybrid_factor` ทุกช่วง (ไม่หัก α̂) → E-H = E-X1 + RPC1…k_res · k_res = 0 → รายงาน "ไม่มี residual factor" (E-H = E-X1)

### 4.6 (d) ตัวเทียบ: ①a · ①c · ③a · M1 (ข้อ 3.4) บน EVAL_E เดียวกัน

### 4.7 จำนวนรูปแบบ (ลองนอกนี้ = spec ใหม่)
- **แถวแข่งของ E 6 แถว:** E-PCA-a1 · E-PCA-a2 · E-X0 (เส้นฐาน) · E-X1 · E-X2 · E-H · **ตัวเทียบ 4:** ①a · ①c · ③a · M1
- **ภาคผนวก (ไม่ใช้ตัดสิน · ติดป้าย):** A1 = stepwise เดิมแต่ใช้ style ETF 4 ตัว (`Momentum` · `Quality` · `Value` · `LowVol`) แทน KF 5 ตัว (pool 10 · ไม่มี factor กลุ่ม) · A2 = ใน E-X1 แทน HML → `AQR_HMLD_GLOBAL` และ RMW → `AQR_QMJ_GLOBAL` (ไม่คัดใหม่ · ไม่ได้ถูกเลือก → N/A) · A3 = ตรวจซ้ำรายเดือน (ข้อ 6.12) · A4 = ชื่อกลุ่มเทียบ primary ของ L2 (`runs/S005/primary_index.csv` form none · บรรยายแบบ Sensoy: สัดส่วนกองที่ I_g = primary) · A5 = ตัวเลขบนตัวแทนกลุ่มกองอิสระ / ชุดตัดซ้ำ
- **ไม่ทำ:** Lucky factors (Harvey–Liu 2021 · ขั้นตอนยังไม่ยืนยัน) · covariance-PCA · ภาคผนวก k = 3 / 5

---

## 5. วิธี — กอง O (ชุดตายตัว)

- **ชุดกอง:** หน่วย 13 (ทอง 7 รวม `I-GOLD*` · REIT 6) · ตารางรายกองบน EVAL52_O 13 · มัธยฐานกลุ่ม / ตารางคะแนนบน EVAL_O 12
- **กลุ่มย่อยที่รายงาน (จากชื่อ / FundProfile · ล็อก):** ทอง-FX Risk Flag N (K-GOLD-A(A) · PRINCIPAL iGOLD-A) · ทอง-Flag Y (BGOLD · `I-GOLD*` · KT-GOLD · TGOLD · UOBSG-N) · REIT-US (DAOL-USREIT · TUSREIT) · REIT-Global (IREITG · LHPROPG-A · PRINCIPAL GREITs) · REIT-Singapore (ONEPROP-SG)
- **แถว:** O-X (หลัก) · O-X′ (ตัวเทียบอย่างง่าย) · ①a · ①c · ③a · ภาคผนวก: O-tilt (รายกอง) · **O-PCA** = `em_pca` บน U_O 13 หน่วย k = 2 คงที่ (ไม่คัด k · ป้าย "N น้อย")
- twin test ตามแผนทำไม่ได้ (KT-GOLDUH ตกอายุ · UOBSG-H ตก AUM · QA_EO §9.2) → ใช้ FX Risk Flag แทน (snapshot · ป้าย)
- α รายกอง (%/ปี · HAC) + BH 10% ภายใน O (12–13 การทดสอบ) · GRS บน 2 พอร์ต EW (ทอง · REIT) ช่วง test (บรรยาย · N น้อย) · PY = N/A (N น้อย)

---

## 6. การทดสอบ และ**รายงานราย factor** (หัวใจของงาน)

ทุกตัวชี้ทำกับ**ทุก factor ของทุกแถวแข่ง** (E-PCA-a1/a2 · E-X1 · E-X2 · E-H · O-X) + factor ของตัวเทียบ (บรรยาย) · ไฟล์ `factor_report_E.csv` / `factor_report_O.csv` (1 แถว = แถวแข่ง × factor) ·
"กลุ่มอ้างอิงของ factor" = EVAL ทั้งหมด (factor ร่วม) หรือสมาชิก EVAL ของกลุ่ม (factor กลุ่ม) หรือกลุ่มย่อย O

| # | ตัวชี้ | นิยามที่ล็อก |
|---|---|---|
| 6.1 | **สัดส่วน variance** | median และ mean ข้ามกองของ Shapley R²_k ÷ R² เต็ม (train) · แถว PCA เพิ่ม λ_k / N ของ Z'Z/T |
| 6.2 | **ใส่เดี่ยว** | (i) factor นั้นตัวเดียว + α · (ii) "แกน + factor" (แกน: E = MKT · REIT = MKT · ทอง = GOLD_XS · ตัวที่เป็นแกนรายงานแค่ (i)) → median adj R² train · R²_oos · Δ (ii) − แกน |
| 6.3 | **drop-one** | ชุดเต็ม − ชุดที่ถอด factor (lag 0+1 ออกพร้อมกัน) บนแถวเดียวกัน → median Δadj R² · ΔR²_oos · ΔBIC (`l3.drop_one` · factor กลุ่ม = E-X2 − E-X1 บนสมาชิก) |
| 6.4 | **Shapley R²** | ผู้เล่น = factor (คู่ lag เป็นผู้เล่นเดียว) · v(S) = R² ของ OLS [1, S] บนแถว train ที่ factor ครบ · คำนวณครบ 2^K ต่อกอง · **Σ_k φ_k = R² เต็ม** (test) · ภาคผนวก: Shapley ของ R²_oos (แต่ละ S fit บน train แล้ววัด test · ติดลบได้ · ป้าย ข) |
| 6.5 | **กองที่ β มีนัย** | β = b0 + b1 · t จาก SE แบบ HAC ของผลรวม · p สองข้าง (normal) · BH 10% ภายใน factor ข้ามกลุ่มอ้างอิง → จำนวนกอง + จำนวนกลุ่มกองอิสระ + แยกเครื่องหมาย · **placebo:** เลื่อน factor นั้นแบบวน 26 / 52 สัปดาห์ในช่วง train (ตัวอื่นคงเดิม) → สัดส่วนกองที่ p < 0.05 · ถ้า > 8% → ป้าย "นับตรงไม่ได้" (ข้อ 32/37) · สัดส่วนกองที่ \|t(b1)\| > 2 (บรรยาย) |
| 6.6 | **ชื่อ** | 3 อันดับ \|corr\| (train) กับชุดอ้างอิง I_EO = `external.reference_set(F)` + EXT14 (`<ETF>_THB − RF_BOT`) + คอลัมน์ KF / JKP / AQR / GLD / VNQ / DTWEX ของ EO + ①a/①c PC · ≥ 0.7 "≈" (ต้อง corr ช่วง test ≥ 0.6 ด้วย มิฉะนั้น "≈ (ไม่ยืนนอกช่วง)" · ข้อ 25) · 0.5–0.7 "คล้าย" · < 0.5 "ไม่มีชื่อ" · factor ภายนอก = นิยามตรง + รายงาน corr สูงสุดกับ PC ของ ①a |
| 6.7 | **VIF** | VIF ภายในชุด (train) แบบ lag 0 และ design Dimson (`tests_stat.vif`) · ต่อกองสำหรับ E-X2 (max / median) · corr สูงสุดกับ factor อื่นช่วง train และ test (ความตั้งฉากหลัง residualize) |
| 6.8 | **ความเสถียร** | r ดิบของ β ระหว่าง H1 / H2 ข้ามกอง STAB (factor กลุ่ม: สมาชิก STAB · < 10 กอง → N/A) · rolling 104 สัปดาห์ step 4 (`l2.rolling_betas`): **corr หน้าต่างแรก vs หน้าต่างสุดท้าย** (ตัวหลัก) + median เทียบช่วงเต็ม (ใช้เทียบอันดับเท่านั้น · รีวิว S006 D5) |
| 6.9 | **กลุ่มกองที่ loading สูงสุด** | median β ต่อกลุ่มชื่อ (คอลัมน์ `group` ของ CSV · กลุ่มที่มี ≥ 5 หน่วย EVAL รวม GLOBAL) → 3 อันดับตาม \|median β\| พร้อมเครื่องหมาย |
| 6.10 | **เทียบชุดเดิม** | ระดับชุด: canonical corr กับ ①a (train · ช่วง test ด้วยน้ำหนักตรึง `l2.canon_oos`) · median ΔBIC เทียบ ①a บนแถวเดียวกัน · spanning สองทิศ (ชุด ~ ①a และ ①a ~ ชุด · Wald α = 0 · ช่วง test · `tests_stat.spanning` · เฉพาะชุด factor ร่วม) · ระดับ factor: max \|corr\| กับ PC ของ ①a |
| 6.11 | **lead diagnostic (ครั้งเดียว)** | E-X1 และ O-X + lead 1 ของ factor ที่ทบจากรายวัน (KF · JKP · GLD · REET/VNQ) → สัดส่วนกองที่ \|t_lead\| > 2 (ถ้า > 10% → แจ้งว่าการจัดสัปดาห์อาจคลาด) |
| 6.12 | **ตรวจซ้ำรายเดือน** | ข้อ 1–2 ของตารางคะแนนสำหรับแถวที่ p = 2K + 1 ≤ 13 (E-PCA · E-X0 · E-X1 ถ้า K ≤ 6 · ①a · ①c · ③a · O-X) · KF ใช้ `KFM_DEV_*` (ไฟล์รายเดือนทางการ · BRIEF 114(3)) · JKP / ETF จาก `factors_eo_monthly` / `factors_ext_monthly` · residualize ด้วย β รายเดือนของ train · ป้าย "ไม่มี null รองรับ" + ป้าย (ช) |

---

## 7. ตารางคะแนนกลาง 6 ข้อ (แยก E / O · ล็อกตาม BRIEF)

| ข้อ | E (EVAL_E 160 · แถวแข่ง 6 + ตัวเทียบ 4) | O (EVAL_O 12 · รายกองบน EVAL52_O 13) |
|---|---|---|
| 1 R² รายกอง | median / IQR adj R² (train) + bootstrap CI (สุ่ม**กลุ่มกองอิสระ**แบบใส่คืน 2,000 รอบ · seed) | รายกอง + median ต่อกลุ่มย่อย |
| 2 R² นอกช่วง | median / IQR R²_oos · gap (R² train − R²_oos) · CI · ส่วนต่างจับคู่กับ E-PCA-a1 และ ③a | รายกอง · ΔR²_oos เทียบ ①a / ①c / ③a รายกอง |
| 3 pricing error | mean\|α̂\| · signed (%/ปี) · BH 10% ของ α · **GRS** ช่วง test (train รอง) บน 12 พอร์ต EW ตามคอลัมน์ `group` ที่มี ≥ 5 หน่วย EVAL: CHINA · HEALTH · ASIA · TECH · EUROPE · INNOV · USA · JAPAN · VIETNAM · GLOBAL · NONE · OTHER (ที่เหลือ: INDIA · INFRA · CLEAN · EM · CONSUMER · PROP · FIN · METAL · TH · STYLE) — สมาชิก ≥ 3 ต่อสัปดาห์ · เฉพาะแถว factor ร่วม · **PY p_boot** (B 999 · block 4 · ข้อ 29) แถว factor ร่วม | α รายกอง + BH ใน O · GRS 2 พอร์ต (บรรยาย) · PY = N/A |
| 4 ความประหยัด | K · median BIC · ΔBIC เทียบ E-X0 และเทียบ ①a | K · BIC รายกอง |
| 5 ความเสถียร | r ดิบ H1/H2 (STAB_E 141 · เฉลี่ยข้าม factor + รายตัว) · rolling แรก–สุดท้าย | r ดิบ (บรรยาย · N น้อย) |
| 6 ตีความได้ | ชื่อ (ข้อ 6.6) · factor ภายนอก = นิยามตรง | นิยามตรง |

ป้ายความเทียบไม่ได้: E-X2 / M1 มี K ต่างรายกอง → GRS / PY = N/A · α ของแถว PCA เทียบพอร์ตกองเพื่อน (ฌ)

---

## 8. เกณฑ์ผ่านของการแข่ง (**ล็อกแล้ว · BRIEF 115(4)** · ค่าที่ designer เสนอ · ผู้ใช้ยืนยันอีกครั้งตอนสรุป)

**8.0 technical validity:** test ใหม่ทั้งหมด + test เดิมผ่าน · sha256 ตรง · regression S003 / S006 ตรง · ไฟล์คัดเลือก (`sel_reps.csv` · `placebo_E.json` · `stepwise_E.csv` · `group_map` sha) เขียนก่อน fit แถวคะแนน · รันซ้ำตรงทุกบิต

**8.1 เกณฑ์ "เข้ารอบ" ของแถว E (ทุกข้อ · ค่าเดิมของ L1 · ข้อ 12/18):**
(C1) median R²_oos ≥ 0.9 × ค่าสูงสุดของ**ทุกแถว E** (รวมตัวเทียบ) · (C2) gap ≤ 0.15 · (C3) ค่าเฉลี่ย r ดิบ (STAB_E) ≥ 0.6 · (C4) median ΔBIC ≤ 0 เทียบแถวที่เล็กกว่าในสายเดียวกัน (E-X1 vs E-X0 · E-H vs E-X1 · E-X2 vs E-X1 วัดบนกองที่มี factor กลุ่ม) · (C5) factor ทุกตัวมีชื่อ (\|corr\| ≥ 0.5) หรือนิยามตรง

**8.2 คำตอบของการแข่ง (ล็อก):**
| คำถาม | กติกา | ค่าที่เสนอ |
|---|---|---|
| Q-E1 ภายนอก (E-X2) แทน PCA ของ E ล้วน (E-PCA-a1) ได้ไหม | ส่วนต่างจับคู่ median R²_oos (E-X2 − E-PCA-a1) | "แทนได้" ≥ −0.03 และ E-X2 เข้ารอบ 8.1 · "ใกล้" −0.06 ถึง −0.03 · "แทนไม่ได้" < −0.06 (ขอบ 0.03 / 0.06 = ค่าของ designer · ป้าย) |
| Q-E2 ภายนอกชุดใหม่ (E-X1) ดีกว่าชุดเดิมที่ลงทุนได้ (③a) | ส่วนต่างจับคู่ + CI แบบสุ่มกลุ่มอิสระ | "ดีกว่า" ≥ +0.05 และขอบล่าง CI > 0 |
| Q-E3 PCA ของ E ล้วนดีกว่า ①a | E-PCA-a1 − ①a | "ดีขึ้น" ขอบล่าง CI > 0 · นอกนั้น "ไม่ต่าง" (บรรยาย) |
| Q-E4 hybrid มีส่วนที่ภายนอกขาด | k_res และ median ΔR²_oos (E-H − E-X1) | "มี" k_res ≥ 1 และ ΔR²_oos ≥ 0.02 และ ΔBIC ≤ 0 |

**8.3 คำตัดสินราย factor (ล็อก · ใช้ค่าที่ล็อกแล้วของ L2–L4 ให้มากที่สุด):**
- **factor ร่วมใน E-X1:** "ยืนนอกช่วง" = drop-one median ΔR²_oos (EVAL_E) > 0 **และ** VIF Dimson < 5 · "สำคัญ" = ยืนนอกช่วง **และ** median ΔR²_oos ≥ 0.005 (ค่าของ designer) **และ** β มีนัย (BH) ใน ≥ 7 กลุ่มกองอิสระและ ≥ 7 กอง (ข้อ 36) โดย placebo ≤ 8% · ΔBIC ≤ −2 บน train ผ่านโดยการคัดอยู่แล้ว (รายงานแต่ไม่ใช้ตัดสิน)
- **factor กลุ่มใน E-X2 (กติกา Q1a ของ L3):** "มี" = ในสมาชิก EVAL ของกลุ่ม median drop-one ΔR²_oos ≥ 0.02 **และ** median ΔBIC ≤ 0 **และ** VIF Dimson ต่อกองสูงสุด < 5 · ผ่าน 1 ใน 2 ข้อแรก = "บางส่วน" · กลุ่มที่ EVAL < 5 (INDIA 4 · INFRA 3) ติดป้าย "n เล็ก — คำตัดสินอ่านไม่ได้" · EVAL 5–7 (VIETNAM · JAPAN) ติดป้าย "แกว่งง่าย" · เลนส์ pseudo-OOS (fit pseudo-train วัด pseudo-test · β ของ e จาก pseudo-train) รายงานคู่ (diagnostic · ข้อ 60)
- **residual PC (E-H) / PC (E-PCA):** บรรยาย (ชื่อ · Shapley · ความเสถียร) ไม่มีคำตัดสิน
- **O:** O-X "ดีกว่าตัวเทียบ" ในกลุ่ม (ทอง / REIT) เมื่อ median ΔR²_oos เทียบตัวเทียบที่ดีที่สุดใน (①a, ①c, ③a) ≥ +0.05 **และ** เป็นบวกใน ≥ 2/3 ของกองในกลุ่ม · factor ของ O รายงานตาม H-O1 / H-O2 (ไม่มีคำตัดสินแยก)

ไม่มีแถวใดผ่าน → รายงาน "ไม่มีชุดที่ผ่าน" + เหตุผล · ห้ามแก้เกณฑ์หลังเห็นผล (ถ้าผู้ใช้เปลี่ยน → ป้าย "เกณฑ์เปลี่ยนหลังเห็นผล" + รายงานทั้งสองชุด · ข้อ 31)

---

## 9. ผลลัพธ์ที่คาดไว้ล่วงหน้า (ช่วงกว้าง · ระยะ 1 คาดผิดบ่อย · `expectations_vs_results.csv` ต้องมีทุกข้อ)

1. k\* ของ E-PCA = 3–6 · PC1 ≈ ACWI / World (\|corr\| ≥ 0.8) · PC2 ≈ จีน (≥ 0.7)
2. placebo เลือก 0 ตัวทั้งสอง shift → τ = −2
3. E-X1 เพิ่ม 2–5 ตัว · หนึ่งในสองตัวแรกคือ e_CHINA หรือ TERM · KF ผ่าน ≤ 2 ตัว · JKP-EM ≤ 1 · FX **ไม่**ถูกเลือก · ด่าน pseudo-OOS หรือ τ หยุดก่อนเพดาน 6
4. median R²_oos (E · EVAL_E): E-PCA-a1 0.58–0.72 · E-PCA-a2 ต่างจาก a1 ไม่เกิน ±0.03 · E-X1 0.40–0.58 · E-X2 0.48–0.65 · E-H ≥ E-PCA-a1 − 0.03 · ③a 0.28–0.40 · ①a ใกล้ E-PCA-a1 (±0.03)
5. Q-E1 = "ใกล้" หรือ "แทนไม่ได้" (E-X2 ต่ำกว่า E-PCA-a1 0.02–0.10) · Q-E2 = "ดีกว่า" · Q-E3 = "ไม่ต่าง" · Q-E4 = "มี" โดย k_res ชนเพดาน 3 ได้
6. factor กลุ่ม "มี" ≥ 4 ใน 11 (คาด JAPAN · EUROPE · VIETNAM · HEALTH) · ASIA และ USA "ไม่มี" หรือ "บางส่วน" · INDIA / INFRA ค่ามัธยฐานแกว่งมาก (n 4 / 3) · e_AH ใช้แทนเมื่อ e_CHINA อยู่ใน E-X1
7. Shapley: MKT ≥ 40% ของ R² ในกองมัธยฐาน · factor กลุ่ม 5–20% ในกลุ่มของตัวเอง · style KF < 5%
8. VIF Dimson ของ E-X1 < 5 ทุกตัว · ต่อกองใน E-X2 < 5 · corr(e_g, factor ร่วม) ช่วง test สูงสุด ≤ 0.55
9. ความเสถียร r ดิบ: MKT และ e_CHINA > 0.8 · style KF < 0.5 · factor กลุ่มที่คำนวณได้ 0.4–0.8 · E-PCA-a1 เฉลี่ย ≥ 0.75
10. กองที่ β มีนัย: MKT เกือบทุกกอง · HML ≥ 7 กลุ่มอิสระ (ติดลบในกลุ่ม TECH/INNOV เกินครึ่ง) · placebo ของ factor ภายนอก ≤ 8%
11. canonical corr E-X1 กับ ①a: คู่แรก ≥ 0.85 · คู่สุดท้าย < 0.6
12. ทอง: β(GOLD_XS) 0.85–1.05 ทุกกอง · β(FX) กอง Flag N 0–0.3 · Flag Y 0.6–1.1 · R²_oos ≥ 0.85 · \|α\| ≤ 3 %/ปี · O-X′ ใกล้ O-X (≤ 0.02) ในกอง Flag Y และแย่กว่าในกอง Flag N
13. REIT: median R²_oos ของ O-X 0.55–0.80 และ ≥ ตัวเทียบที่ดีที่สุด + 0.05 · TERM β > 0 ≥ 4 / 6 กอง · REIT_e β > 0 ทุกกอง
14. ทั้งทองและ REIT: O-X "ดีกว่าตัวเทียบ" (ตัวเทียบที่ดีที่สุดคือ ③a สำหรับทอง · ①c สำหรับ REIT)
15. รายเดือน R²_oos ต่ำกว่ารายสัปดาห์ทุกแถว
16. lead diagnostic < 10% ของกอง
17. Q-E2: E-X1 − ③a ≥ 0.05 แม้ E-X1 ไม่มี factor ทอง / บอนด์

---

## 10. `decisions_pre_run.md` ที่ analyst ต้องเขียน**ก่อนแตะข้อมูลจริงครั้งแรก** (บทเรียน L4 / BRIEF 86)

1. sha256 ของไฟล์ข้อ 2.1 ทุกไฟล์ + `S012_group_map.csv` (= `898a8686…fceb` · ไม่ตรง → หยุด) + lib 15 ไฟล์เดิม (ต้อง = `runs/S010/run_meta.json`)
2. sha256 ของ `runs/S012/run.py` ณ เริ่ม phase pre + สำเนา `run_pre.py` (BRIEF 106)
3. smoke test ใช้**ข้อมูลจำลองเท่านั้น** · ห้ามรันบนข้อมูลจริงก่อนเขียนไฟล์นี้ครบ · ถ้าต้องแก้โค้ดหลังรันข้อมูลจริง → diff ใน results.md
4. ตารางต่อรหัส 4 หน่วยตามข้อ 2.3 (รหัส · สัปดาห์ที่ซ้อน · จำนวนแถวหลังต่อ)
5. จำนวนกองในชุด SEL / EVAL / EVAL52 / STAB / PCA balanced / unbalanced ต้องตรงตารางข้อ 0 (ไม่ตรง → หยุดและอธิบาย)
6. ลำดับ pool 11 ตัวตามตาราง 3.1 (ใช้ตัดสินเสมอ) · ช่องที่ 12 ว่าง
7. นิยามตัวแทนกลุ่มอิสระ (ข้อ 4.2 ข้อ 1) · min_overlap 52 · thr 0.95
8. ด่าน G3: เกณฑ์แถวขั้นต่ำ 52 / 26 · β ของ e_CHINA จาก pseudo-train
9. กฎ τ (ข้อ 4.3) · ลำดับเขียนไฟล์ (ข้อ 11.3)
10. กติกา CHINA → e_AH (ข้อ 3.2) และการตรวจ `l2.in_span`
11. แกนของ "ใส่เดี่ยว" (ข้อ 6.2) · ชุดอ้างอิง I_EO (ข้อ 6.6) · พอร์ต GRS 12 พอร์ต (ข้อ 7)
12. bootstrap สุ่มกลุ่มอิสระ (2,000 · seed) · PY B 999 block 4 · placebo ของข้อ 6.5 (26 / 52)
13. ค่าเกณฑ์ข้อ 8 (ล็อกแล้ว · BRIEF 115(4) · คัดลอกตัวเลขลงไฟล์) · ค่าเริ่มต้นของข้อเปิดในข้อ 14 ที่ใช้จริง
14. การจัดการกรณีขอบ: กองที่ fit ไม่ได้ในบางรูปแบบ (min_obs 104 train / 52 test) · ED คืน None → ไม่นับใน combine_k · k_res = 0
15. ป้าย what-if / ภาคผนวกฝั่ง "ผ่าน": "ข้อมูลชุดเดียวกัน · ไม่ใช่หลักฐานอิสระ" (ข้อ 103 n1)

---

## 11. รายละเอียดการ implement (analyst)

### 11.1 โค้ดใหม่ `lib/l1eo.py` (**ไม่แก้ไฟล์ lib เดิม** · ใช้ของเดิมให้มาก)
ใช้ของเดิม: `io_l1.verify_manifest / load_returns / load_factors / sha256_file` · `samples.window_mask / dedup_keep` · `regress.fit_funds / oos_r2_funds / lag_stack / CommonFactors` ·
`nfactors.*` · `pca.pca_fit / em_pca / factor_returns` · `hybrid.residual_pc / hybrid_factor` · `external.line3 / reference_set` · `scorecard.score_model / stability_halves / interpret / canonical_corr` ·
`tests_stat.vif / bh / grs / pesaran_yamagata / py_null_bootstrap / spanning` · `l2.fund_clusters / circular_shift / in_span / canon_oos / rolling_betas / AugmentedFactors / count_groups` ·
`l3.residualize / ext_excess / drop_one / fit_perfund / perfund_from_primary / _delta_table` · `l4.e_from_s006 / fx_factor / MixedProvider / cluster_reps`

| ฟังก์ชันใหม่ | input → output |
|---|---|
| `load_eo(freq)` | ตรวจ `manifest_eo.json` → factors EO (ตัดแถว > 2025-12-26 สำหรับการ fit) |
| `load_group_map(path, sha)` | CSV → DataFrame (ตรวจ sha · ทุกกอง ≤ 1 factor) |
| `apply_name_rules(name_en)` | กฎข้อ 4.4.1 (ต้องสร้าง CSV ซ้ำได้ตรงทุกแถว — test) |
| `splice_units(R, U, profile)` | กติกาข้อ 2.3 → R ที่มีคอลัมน์หน่วย + ตารางต่อรหัส |
| `eo_sets(R_units, policy, dup_pairs, n_weeks)` | SEL · EVAL · EVAL52 · STAB · PCA balanced / unbalanced (คู่ซ้ำแปลงเป็นหน่วย) |
| `pool_E(F, Fext, Feo, mask_tr)` | DataFrame MKT + pool 11 ตามลำดับ |
| `sel_reps(R, funds, mask_tr)` | ตัวแทนกลุ่มอิสระ (ข้อ 4.2) |
| `stepwise_eo(R, core, pool, mask_tr, reps, tau, k_max=6, pseudo=(…), resid_spec=…)` | (selected, log) ตามข้อ 4.2 |
| `placebo_eo(R, core, pool, mask_tr, reps, shifts=(26,52), tau0=-2.0)` | dict + τ (ข้อ 4.3) |
| `group_factors(gmap, Iraw, X1, mask_tr)` | (E_g, per_fund dict, coef) รวมกติกา e_AH |
| `shapley_r2(y, blocks, rows)` / `shapley_oos(...)` | φ ต่อผู้เล่น (exact 2^K) |
| `sig_count(fit, mask_tr, groups, placebo_shifts)` | จำนวนกอง / กลุ่มอิสระที่ BH + placebo |
| `factor_report(...)` | ตาราง 6.1–6.11 |
| `o_factors(F, Fext, Feo, mask_tr)` | ชุดตายตัวข้อ 3.3 |
| `top_groups(beta, groups, min_n=5)` | ข้อ 6.9 |
| `runs/S012/run.py` | รันเดียวจบ 2 phase (pre · full) |

### 11.2 test ใหม่ `lib/tests/test_l1eo.py` (ชื่อ `test_eo_NN_…` กันเลขชน · `pytest -p no:cacheprovider`)
1. U: ไม่มีกอง F · U_E 218 / U_O 14 รหัส · 215 / 13 หน่วย · ทุกกองใน CSV อยู่ใน U และกลับกัน
2. **AUM ≤ 2023-12-31:** `last_aum_date` ของกองใน U อยู่ใน [2023-10-02, 2023-12-31] · ไม่มีแถว AUM หลัง 2023-12-31 ในการตัดสิน U
3. **ไม่มีแถว > 2025-12-26 ใน fit:** ทุก design / mask / residualize / PCA / stepwise มี index สูงสุด ≤ 2025-12-26 · แถว JKP ที่เป็น NaN ไม่เข้า
4. **future-scramble:** สุ่มแทนผลตอบแทนกองและ factor ทุกแถว ≥ 2024-01-05 (รวม > 2025-12-26) → `sel_reps` · log ของ stepwise / placebo · τ · β ของ residualize (e_CHINA · REIT_e · e_g) · Λ / σ / k\* ของ E-PCA · W / s / coef / k_res ของ hybrid · การจับคู่กลุ่ม **เท่าเดิมทุกบิต**
5. **splice (BRIEF 115(3)):** ตรวจพบคู่ครบ 4 คู่ตามข้อ 2.3 (ไม่มีคู่เกิน) · สัปดาห์ซ้อน (2023-12-08) ใช้รหัสเก่า · ไม่มีแถวซ้ำ · หลังต่อ train 155 / test 104 ทุกหน่วย · class คู่ขนานของ Fund Class เดียวกัน (MGA · MGF · MCHINA) ไม่ถูกต่อ · `panel_weekly.parquet` sha ไม่เปลี่ยนหลังรัน · ตารางผลที่มีหน่วย `*` มีคอลัมน์ป้าย (ญ)
6. **Shapley:** Σφ = R² เต็ม (1e-10) · ผู้เล่นสมมาตรได้ค่าเท่ากัน · ผู้เล่นศูนย์ได้ 0 · คู่ lag เป็นผู้เล่นเดียว · K = 1 → φ = R²
7. **stepwise (ข้อมูลจำลอง):** กองโหลด 2 จาก 10 candidate → เลือก 2 ตัวตามลำดับความแรงแล้วหยุด · เพดาน 6 เคารพ · เสมอ → ลำดับ pool · candidate ที่ fit เฉพาะ pseudo-train ถูกด่าน G3 หยุด · deterministic
8. **placebo / τ:** shift = 0 → เท่ากับ stepwise · กฎ τ ตรงตัวอย่างมือทั้งสองกรณี
9. **factor กลุ่ม:** corr(e_g, X1) ช่วง train ≤ 1e-12 · mean(e_g, train) = â · ≤ 1 ตัวต่อกอง · e_CHINA ∈ X1 → CHINA ใช้ A − H · กลุ่มที่มี < 5 หน่วยใน U ไม่มี factor · ป้าย designer (TH · METAL · EM · FIN · CONSUMER · STYLE · GLOBAL) ไม่มี factor ไม่ว่ามีกี่กอง
10. **กฎชื่อ:** `apply_name_rules` บน FundProfile → ได้คอลัมน์ `name_group` / `group` / `group_factor` / `alt_factor_no_synonym` ตรง CSV ทุกแถว · ไม่มีคำที่ถูกตัดในข้อ 4.4.1 อยู่ใน regex ที่ให้ factor
11. **O:** GOLD_XS = GLD_USD − SHV_USD · TERM = IEF_USD − SHV_USD · REIT_e ⟂ MKT ใน train (1e-12) · FX = `l4.fx_factor`
12. `sig_count`: ตัวอย่างมือ BH + นับกลุ่มอิสระ · placebo shift เป็น permutation ภายใน train
13. `run.py` 2 รอบ → sha256 ไฟล์ผลเท่ากันทุกไฟล์ (ยกเว้น `run.log` · field เวลาใน `run_meta.json`)
14. ตัวเทียบ: ①a / ①c โหลดตรง sha · M1 provider ตรงกับ `runs/S009` บนกองที่ทับกัน (α / R² 1e-10)
- test เดิมทั้งหมดใน `lib/tests/` + `tests/test_team_setup.py` ต้องผ่าน

### 11.3 การรัน `runs/S012/` · ลำดับเขียนบังคับ (timestamp ใน run.log)
**phase pre:** regression (11.4) → `decisions_pre_run.md` (มีอยู่แล้ว) → `units_splice.csv` → `sets.csv` → `group_map_check.json` → `sel_reps.csv` → `placebo_E.json` → `stepwise_E.csv` (+ `stepwise_E_all_candidates.csv`) → `group_factor_coef.csv` → `pca_E.json` (k\*, ทุกเกณฑ์) → `hybrid_E.json` ·
**phase full:** fit ทุกแถว → `scorecard_E.csv` · `scorecard_O.csv` · `fund_level_E.csv` · `fund_level_O.csv` · `factor_report_E.csv` · `factor_report_O.csv` · `shapley_E.csv` · `shapley_O.csv` · `sig_counts.csv` · `vif.csv` · `stability.csv` · `rolling_104.csv` · `interpret.csv` · `canon_spanning.csv` · `grs.csv` · `py.csv` · `bootstrap.csv` · `monthly.csv` · `appendix_A1.csv` · `appendix_A2.csv` · `appendix_A4.csv` · `factors_S012_weekly.parquet` · `expectations_vs_results.csv` · `results.md` · `run.log` · `run_meta.json` · `repro_check.json`
- `run_meta.json` + บรรทัดแรกของ log ทุก phase: sha256 ของ `run.py` (BRIEF 106) · ถ้า phase pre ≠ phase full → diff ใน results.md
- `run_meta.json`: sha256 ข้อมูล · ไฟล์ pin (รวม group map) · lib ทุกไฟล์ · เวอร์ชันแพ็กเกจ · seed · τ · ตัวที่ถูกเลือก · k\* · k_res

### 11.4 regression (ก่อน phase pre · ไม่ผ่าน → หยุด)
1. sha256 lib เดิม 15 ไฟล์ = `runs/S010/run_meta.json` `lib_sha256` · เพิ่มได้เฉพาะ `l1eo.py` + `tests/test_l1eo.py`
2. รัน `runs/S003/run.py` (sha `9f21e388…590f`) และ `runs/S006/run.py` (sha `5515b289…c760`) ลง `scratch/factor-analyst_s012_regress_s003/` · `…_s006/` → sha256 ทุกไฟล์ผลตรงกับของเดิม (ยกเว้นไฟล์เวลา / meta ตามแบบ S006 ข้อ 8.3) → `runs/S012/regression_S003_S006.json`

---

## 12. ข้อจำกัด (ติดไปกับรายงานผล)
- ป้าย (ก)–(ฏ) ข้างบน · ช่วง test ใช้ซ้ำ · ไม่มี holdout (NAV 2026 มีรู)
- **การคัด factor ร่วมยังเป็นการค้นบนข้อมูลชุดเดียวกับระยะ 1** แม้ล็อกกติกาแล้ว: pool 11 × ≤ 6 รอบ (+ placebo 2 ชุด) · ด่าน pseudo-OOS อยู่ใน train · ค่าตัด −2 / เพดาน 6 / pool 12 เป็นค่าตั้ง
- กลุ่มจากชื่อกอง: ชื่ออาจไม่ตรง holding · ลำดับความสำคัญและคำของ designer เป็นกติกาที่ตั้งเอง · นับเกณฑ์ ≥ 5 จาก U_E (BRIEF 115(2)) ทำให้ INDIA (EVAL 4) / INFRA (EVAL 3) มี factor แต่คำตัดสินกลุ่มอ่านไม่ได้ · VIETNAM มี EVAL พอดี 5 · ASIA เป็นกลุ่มผสม (รวม ASEAN 2 กอง) · การตัดคำของ designer ทำให้กองธีมบางกอง (Metaverse · eSports · Planetary Transition · ESG ทั่วไป) ไม่มี factor กลุ่ม
- EVAL_E 160 จาก 215 หน่วย: class ตัวแทนของ L0 หลาย family เริ่ม 2022–2023 → กองใหม่ / class ใหม่ถูกตัดจากการประเมิน (ไม่แก้ L0)
- U_O เสียกอง Eastspring 4 กอง (ข้อ 114(1)) · twin test ทำไม่ได้ · กลุ่มย่อย hedge ของทองใช้ FX Risk Flag (snapshot) · REIT-US 2 / Singapore 1 กอง → รายกองเท่านั้น
- residualize ตรึง β จาก train → ตั้งฉากเฉพาะ train · KF รายวันปิดหลายเวลาและแปลง USD (ยังไม่ยืนยันวิธีของ KF) · JKP ใช้ capped VW · CC BY-NC
- ①a / ①c สร้างจาก E/F/O ปน (balanced 134 / 277) — ตัวเทียบไม่ใช่ "PCA ของ E" · M1 ใช้ primary ที่เลือกด้วยช่วง test
- ระยะ 1 ห้ามสรุปว่า "ลงทุนได้" · α ไม่ใช่หลักฐานฝีมือ

---

## 13. ตัดสินแล้ว (BRIEF 115 · ผู้ใช้ 2026-10-23 หลังดูตารางจับคู่)

| # | เรื่อง | ที่ตัดสิน | ที่มา |
|---|---|---|---|
| 1 | คำในชื่อกอง | ใช้เฉพาะคำของ F-R006 (รากคำ) · ตัดคำที่ designer เพิ่ม (EV / BATTERY ใน CLEAN · คำเพิ่มใน TECH ฯลฯ ตามข้อ 4.4.1) → CLEAN เหลือ 4 → ไม่มี factor ICLN | 115(1) |
| 2 | ฐานการนับ "กลุ่ม ≥ 5 กอง" | หน่วยใน **U_E ทั้งหมด** (Fund Class ซ้ำนับ 1) → e_INDIA และ e_IGF ผ่าน (EVAL 4 / 3 · ป้าย "n เล็ก") | 115(2) |
| 3 | ต่อรหัส TMB → Eastspring 3 คู่ + I-GOLD | ต่อใน run · ไม่แก้ panel L0 · ป้าย (ญ) · test `test_eo_05` | 115(3) · 114(2) |
| 4 | เกณฑ์ผ่านข้อ 8 | ล็อกตามที่เสนอ · ยืนยันอีกครั้งตอนสรุป | 115(4) |
| 5 | ประเทศเอเชียที่ < 5 ไป ASIA | ใช้ (ผลตามเกณฑ์ U: INDIA 6 → กลุ่มของตัวเอง · ASEAN 2 → ASIA) | 115(5) |
| 6 | MSCI_ASIA_EX_JAPAN เป็น factor กลุ่ม | ใช้ (13 หน่วย EVAL) | 115(5) |
| 7 | ลำดับความสำคัญ ประเทศ > ธีม sector > INNOV > TECH | ตามข้อ 4.4.1 | 115(5) |
| 8 | กติกา CHINA → e_AH เมื่อ e_CHINA เป็น factor ร่วม | ตามข้อ 3.2 | 115(5) |
| 9 | ช่องที่ 12 ของ pool | ว่าง (pool 11) | 115(5) |
| 10 | กลุ่มย่อยทองตาม FX Risk Flag (snapshot) | ใช้ | 115(5) |
| 11 | e_CHINA residualize แบบ lag 0 | ใช้ (span ไม่เปลี่ยน · รีวิว S006) | 115(5) |
| 12 | ภาคผนวก A1 (style ETF) · A2 (AQR) · A4 (ชื่อ vs primary L2) | ทำ · ไม่ใช้ตัดสิน | 115(5) |
| 13 | กองที่ไม่อยู่ใน EVAL | ไม่ได้คะแนนหลัก · EVAL52 (196) เป็นภาคผนวก | 115(5) |
| 14 | ป้าย CONSUMER / FIN / EM / TH / METAL (กลุ่มที่ designer ตั้ง ไม่ใช่กลุ่ม F-R006) | **ไม่ให้ factor** แม้ CONSUMER มี 5 กองใน U (ตีความ 115(1): คำ BRAND / LUXURY / LIFESTYLE เป็นคำที่ designer เพิ่ม) | 115(1) (การตีความของ designer) |

## 14. ต้องให้ผู้ใช้ตัดสินใจ (ข้อที่ยังเปิดจริง · ค่าเริ่มต้นใช้ระหว่างรอ · เปลี่ยนได้**ก่อนรัน**เท่านั้น)

| # | เรื่อง | ค่าเริ่มต้น | ทางเลือก / ผลกระทบ |
|---|---|---|---|
| 1 | **คำพ้องของประเทศเดียวกัน** (`CHINESE` · `BHARAT` · `NIPPON` · `AMERICA` · `U.S.` · `NASDAQ` / `NDQ`) — ไม่อยู่ในรายการคำของ F-R006 แต่หมายถึงประเทศ / ดัชนีเดียวกัน · BRIEF 115(1) ระบุเฉพาะคำธีม | **คงไว้** · ไม่เปลี่ยนการผ่าน ≥ 5 ของกลุ่มใด (INDIA ยังมี 5 กองถ้าไม่มี BHARAT) | ตัดออก → 7 กอง (EVAL 5: K-CHX · B-BHARATA · ASP-NGF · B-NIPPON · ABAGS) ไม่มี factor กลุ่ม · ชุด factor ยังเป็น 11 ตัว · คอลัมน์ `alt_factor_no_synonym` |
| 2 | ข้อ 13 ข้อ 14 (CONSUMER ไม่ได้ factor) ถ้าผู้ใช้ตั้งใจให้ CONSUMER เป็นกลุ่ม | ไม่ให้ factor | ให้ factor ACWI CD กับ 5 กอง (EVAL 1 · คำตัดสินกลุ่มไม่มีความหมาย) |
