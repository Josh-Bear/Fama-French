# F-R004 — deep search ก่อน L3 (VIF-cleaned) และ L4 (กลุ่ม / รายกอง) · 2026-10-16

ผู้เขียน: factor-researcher · ผู้ใช้สั่ง "เพิ่มเงื่อนไข deep search แล้วลองใหม่" (BRIEF ตารางการตัดสินใจ 2026-10-16) · ชั้นที่ป้อน: L3, L4 (บางข้อป้อนระยะ 2)
อ่านก่อนเขียน: role `factor-researcher.md` · `BRIEF.md` (ครบ · ค่า 1–44) · `research/INDEX.md` + F-R001–F-R003 · `reports/L1_summary.md` · `runs/S005/results.md` (ครบ 898 บรรทัด) · `data/QA_L0.md` · `data/external/NOTES.md` · `config.py` บรรทัด 256–270 (`SCORE_COUNTRY_CLEAN`)
**ไม่ค้นซ้ำ:** GRS, PY, BH/BY-PRDS, Huberman–Kandel, Bai–Ng, APB (Hunter et al.), Sharpe 1992, CPZ 2013, Carhart, Amihud–Goyenko (อยู่ใน F-R001/F-R003 แล้ว — อ้างต่อเท่านั้น)
ข้อจำกัดของรายงาน: ส่วนใหญ่ยืนยันระดับ **บทคัดย่อ / หน้าผลค้น** (ป้ายในบรรณานุกรม) · ไม่ได้อ่านฉบับเต็มเรื่องใด · ไม่รันโค้ด · ตัวเลขของทีมที่ยกมา = อ่านจาก `runs/S005/results.md` / `L1_summary.md` (ไม่ได้ตรวจซ้ำเอง) · **ไม่พบหน้าเว็บที่มีข้อความสั่งการ**

## บทสรุป 5 บรรทัด
1. **L3 — ปัญหาไม่ใช่ "ดัชนีไหนต้องตัด" แต่เป็น 2 คำถามที่ปนกัน:** (ก) จะใช้ปริภูมิ (span) ไหน (ข) จะ parametrize อย่างไรให้ตีความได้ · VIF backward elimination เปลี่ยนทั้งสองพร้อมกัน ส่วน **การ residualize ตามลำดับชั้น** (โลก → ภูมิภาค → ประเทศในภูมิภาค · sector บนโลก) เปลี่ยนแค่ (ข) — R² และ α ของกองเท่าเดิมทุกตัว แต่ VIF ต่ำลงตามโครงสร้างและ coefficient อ่านเป็น "exposure เกินจากที่ beta โลกบอก" ได้
2. หลักฐานเรื่องลำดับชั้นมาจากวรรณกรรม country-vs-industry: Heston–Rouwenhorst 1994 (country effect เด่น) · Brooks–Del Negro (ราวครึ่งหนึ่งของ "country effect" เป็น region effect) · Bekaert–Hodrick–Zhang 2009 (factor model แบบ risk-based ไม่กี่ตัวจับ covariance ดีกว่า HR) → ความซ้ำซ้อน 21/28 ของ L2 ส่วนใหญ่เป็น **เชิงบัญชี** (ดัชนีรวมคือผลรวมของดัชนีย่อย) ไม่ใช่ข้อมูลบังเอิญ
3. **L4 — α รายกองกับ T 104–260 สัปดาห์มี power ต่ำมาก:** Andrikogiannopoulou–Papakonstantinou 2019 ชี้ว่า FDR ของ BSW จัดกอง α ±2%/ปี ผิดเป็น α = 0 ถึง 65% (สหรัฐฯ ข้อมูลหลายสิบปี) · BSW ตอบกลับว่าเหลือ 32% ในช่วงยาวขึ้น → BH 10% ตาม BRIEF ควรคู่กับ **bootstrap แบบสุ่มเวลาร่วมทุกกอง (Fama–French 2010)** + **ค่า α ต่ำสุดที่ตรวจจับได้** (ไม่ใช่ fund-by-fund แบบ KTWW ซึ่ง Harvey–Liu 2022 ว่า over-reject)
4. **hedge FX ตาม CIP ถูก span โดย factor FX ของทีมอยู่แล้ว** (`SHV_THB − RF_BOT` ค่าชั่วคราว 20): กอง hedge เต็มควรได้ β_FX ≈ −β_หุ้น และ α ≈ 0 ถ้า model มี factor นี้ → **model ของ L4 ต้องมี FX แยก** ไม่งั้นค่าเฉลี่ยของ FX factor (carry ดอกเบี้ยสหรัฐฯ − ไทย ซึ่งเฉลี่ย 2021–2025 เป็นบวก + ค่าเฉลี่ยค่าเงิน) จะไหลไปอยู่ใน α · Greger–Scholz (twin share class) สนับสนุนว่า factor model ที่ไม่มี hedging factor วัด α ของกอง hedge ผิด
5. **ดาวน์โหลดที่คุ้มสุด:** ETF ธีม (กองธีม 37–42 กองที่ primary = ACWI_CD มี β ไม่เสถียร r 0.15–0.25) · ETF ประเทศอาเซียน (THD/EIDO/EPHE/EWM/EWS) · REIT / infra / commodities สำหรับกอง O (ชุด MSCI ของแอปไม่มี Real Estate — `config.py`) · hedged ETF ลำดับรอง · ดัชนี SET ฉบับทางการเป็น **ข้อมูลเสียเงิน** → ผู้ใช้ตัดสินใจ

---

## ข้อเท็จจริงจากชั้นก่อนที่รายงานนี้ต้องตอบ (อ่านจากไฟล์ · ไม่ได้ตรวจซ้ำเอง)
- L2 (`runs/S005/results.md` §6.7): ดัชนี **21/28** มี R² บนดัชนีอื่น ≥ 0.90 · VIF สูงสุด MSCI_WORLD 82,976 / ACWI 54,279 / USA 8,907 · คลัสเตอร์ใหญ่สุด = {USA, ACWI, WORLD}
- §8.1 m2: เกณฑ์ P1(ก) (n_groups_sig ≥ 7 และ n_funds_sig ≥ 7) **ไม่คัดดัชนีใดออก** (ผ่านทั้ง 28 บน ①a/①c) · m4: เป็นเรื่อง power ของ T = 155 × 28 ดัชนี ไม่ใช่ size หลุด
- P4 ส่งต่อ L3 (k = 4): **ACWI_HC, ACWI_UT, EUROPE, INDIA, JAPAN, VIETNAM** · k = 3/5 ต่างกัน 1 ดัชนี (ASEAN / ACWI_IN)
- §5.1: β ของ primary index ไม่เสถียรในกลุ่ม **PRIM:MSCI_ACWI_CD** (37 กอง · r ดิบ 0.252 บน ①a, 0.151 บน ①c) และ CHINA_ALL (0.19/0.25) เทียบกับ ACWI_IT 0.92 · m6: กลุ่ม ACWI_CD 40 กองเป็นกองธีม (เช่น ASP-DISRUPT, TBIOTECH, TGENOME, TNEWENGY, MGTECH)
- `config.SCORE_COUNTRY_CLEAN` (แอป) = 11 ประเทศ: BRAZIL, CHINA_A, CHINA_H, EUROPE, INDIA, JAPAN, KOREA, ASEAN, TAIWAN, USA, VIETNAM (ตัดดัชนีรวม ACWI/World/EM/Asia ex Japan/China All ออก) · คอมเมนต์ในไฟล์: ชุด sector ของแอป **ไม่มี Real Estate**
- L1 9b: α ของ ③a ฝั่ง FX beta ต่ำ vs สูงต่างกัน 1.7–19.2 %/ปี และ **ยังไม่เท่ากันหลังใช้ FX = SHV − rf**

---

## ตารางอันดับไอเดีย
คะแนน = (หลักฐาน 1–3 × เข้ากับข้อมูล 1–3) ÷ ความซับซ้อน 1–3 · จัดตามสายของ F-R001 (① stat · ② จากกอง · ③ ภายนอก/ดัชนี · ④ ใหม่) + คอลัมน์ชั้น

| # | ไอเดีย | สาย | ชั้น | หลักฐาน | เข้ากับข้อมูล | ซับซ้อน | คะแนน |
|---|---|---|---|---|---|---|---|
| **L3-1** | **residualize ตามลำดับชั้น** (โลก → ภูมิภาค → ประเทศในภูมิภาค · sector บนโลก) แทน/คู่กับ VIF elimination | ③ | L3 | ปานกลาง (2) | สูง (3) | 1 | **6.0** |
| **L3-2** | **ดัชนี P4 ที่ residualize บน factor L1** (ส่วนเพิ่มของดัชนีที่ตั้งฉากกับ ①a/①c) | ④ hybrid | L3 | ปานกลาง (2) | สูง (3) | 1 | **6.0** |
| **L4-1** | **FX factor บังคับใน model α** (hedge ตาม CIP ถูก span โดย SHV_THB − RF_BOT) | ③ | L4 | ปานกลาง (2) | สูง (3) | 1 | **6.0** |
| **L4-2** | **α̂ ข้ามกอง ~ คุณลักษณะกอง** (TER · hedge/FX beta · ธง class ปันผล · AUM · 1 − R² · policy · กลุ่ม) แบบ WLS + cluster ตามกลุ่มกองอิสระ | ② | L4 | แข็ง (3) | กลาง (2) | 1 | **6.0** |
| L4-3 | การอนุมาน α: BH/BY + **bootstrap สุ่มเวลาร่วม (FF 2010) แบบ block** + ค่า α ต่ำสุดที่ตรวจจับได้ | ① | L4 | แข็ง (3) | สูง (3) | 2 | 4.5 |
| L4-4 | factor กลุ่มจาก residual: ค่าเฉลี่ย residual แบบ leave-one-out (กลุ่ม < 10 กอง) · PCA + ED/PA (กลุ่ม ≥ 10) | ①/② | L4 | ปานกลาง (2) | สูง (3) | 2 | 3.0 |
| L4-5 | ETF ธีมเป็นตัวเทียบ/ชื่อของ factor กลุ่มกองธีม (ต้องดาวน์โหลด) | ③ | L4 | อ่อน–ปานกลาง (1.5) | กลาง (2) | 1 | 3.0 |
| L3-3 | VIF < 5 backward elimination (BRIEF · แอปใช้) = **เส้นฐานบังคับ** | ③ | L3 | อ่อน (1) — กฎหัวแม่มือ ไม่มีหลักฐานว่าดีที่สุด | สูง (3) | 1 | 3.0 |
| L3-4 | ตัวแทนคลัสเตอร์ความซ้ำซ้อน (1 ดัชนี หรือ PC1 ต่อคลัสเตอร์) | ③ | L3 | อ่อน (1) | สูง (3) | 1 | 3.0 |
| L3-5 | Sharpe RBSA แบบมีข้อจำกัด (w ≥ 0, Σw = 1) + CI | ③ | L4 (บรรยายรายกอง) | แข็ง (3) | กลาง (2) — กอง hedge ทำให้ w ≥ 0 ผิดรูป · Dimson lag | 2 | 3.0 |
| L3-6 | elastic net / LASSO สองขั้น (stability selection) | ① | L3 diagnostic | อ่อน–ปานกลาง (1.5) | กลาง (2) | 2 | 1.5 |
| L4-6 | ธง feeder fund / ค่าธรรมเนียมสองชั้น | ② | L4 | อ่อน (1) — ไม่พบงานวิจัยกอง feeder ไทย | ต่ำ (1) — ยังไม่รู้ว่ามี field ใน FundProfile | 1 | 1.0 |

---

## รายละเอียดต่อไอเดีย

### L3-1 residualize ตามลำดับชั้น (hierarchical orthogonalization)
| หัวข้อ | เนื้อหา |
|---|---|
| ไอเดีย + กลไก | ดัชนีรวม (ACWI, World, EM, Asia ex Japan, China All) **เป็นผลรวมถ่วงน้ำหนักของดัชนีย่อย** → collinearity เกิดจากนิยาม ไม่ใช่สถิติ · การตัดตาม VIF จึงเลือกทิ้ง "ตัวไหนก็ได้" ในคู่ที่แทบเหมือนกัน (ผลขึ้นกับลำดับ) · ทางที่มีกลไกกว่า: นิยามตัวแปรใหม่ตามชั้น — G = ACWI · R_r = ภูมิภาค r ที่ residualize บน G · C_c = ประเทศ c ที่ residualize บน (G, R_ภูมิภาคของ c) · S_s = sector s ที่ residualize บน G · coefficient ของ C_c = "exposure ต่อประเทศ c **เกิน**จากที่ beta โลก/ภูมิภาคบอก" |
| ข้อเท็จจริงเชิงพีชคณิต (เหตุผลของผู้เขียน · ไม่ใช่ข้ออ้างจากวรรณกรรม) | ถ้า auxiliary regression มีค่าคงที่และตัวแปรชุดเดิม ปริภูมิ {1, G, R, C, S} = ปริภูมิ {1, ดัชนีดิบชุดเดียวกัน} → **R², fitted, residual และ α ของกองไม่เปลี่ยน** · เปลี่ยนเฉพาะ coefficient รายตัว, SE และ VIF → แยก "ผลของการเลือกดัชนี" ออกจาก "ผลของการตั้งชื่อ" ได้ชัด (VIF elimination ทำสองอย่างพร้อมกัน) · ข้อแม้: β ของ auxiliary ประมาณจาก train แล้วตรึงไว้ในช่วง test → ช่วง test ตั้งฉากโดยประมาณเท่านั้น (รายงาน corr ที่เหลือ) |
| หลักฐาน | Heston & Rouwenhorst 1994 (JFE 36, ยุโรป 12 ประเทศ 1978–1992): โครงสร้างอุตสาหกรรมอธิบายความต่างของดัชนีประเทศได้น้อย country effect เด่น · Griffin–Karolyi 1998 (25 ประเทศ): อุตสาหกรรมอธิบาย ~4% (ผ่านแหล่งรอง) · Brooks & Del Negro (Atlanta Fed WP 2002/2004 · ตลาดพัฒนาแล้วและเกิดใหม่): **ราวครึ่งหนึ่งของ country effect เป็น region effect** ส่วนที่เหลือเป็น within-region country · Bekaert, Hodrick & Zhang 2009 (JF 64(6) · พอร์ต country-industry / country-style): **factor model แบบ risk-based ไม่กี่ตัวจับ covariance ดีกว่า HR** และการขึ้นของ industry effect เป็นช่วงสั้น · Klein & Chow 2013 (QREF 53(2)): orthogonalize ทั้งเมทริกซ์เพื่อแยกส่วน R² · งานที่ใช้ต่อรายงานว่า factor ใหม่ยัง corr สูงกับ factor เดิม (ตีความต่อได้) · Bodson–Coën–Hübner 2010 ใช้ PC ของ benchmark ที่เลือกแล้วเพื่อเลี่ยง multicollinearity ใน style analysis · ความแรง: **ปานกลาง** (ตัวแบ่งชั้นมีหลักฐานแข็ง · การใช้กับการ regress กองทุนเป็นการต่อยอด) · ข้อโต้แย้ง: Roll 1992 ว่าอุตสาหกรรมสำคัญ · การ orthogonalize แบบลำดับขึ้นกับลำดับที่เลือก (Klein–Chow, Adcock et al. ผ่านผลค้น) |
| เข้ากับข้อมูล | สูง — M28 มีโลก (ACWI/World), ภูมิภาค (Europe, Asia ex Japan, EM, ASEAN), ประเทศ, sector 10 ตัวครบ · ไม่ต้องดาวน์โหลด |
| ชั้น | **L3** (รูปแบบหลักที่แนะนำ) · ป้อน L4 (ชื่อกลุ่ม) |
| วิธีสร้าง | (1) ลำดับชั้นล็อกก่อนรัน: G = MSCI_ACWI → ภูมิภาค = {USA, EUROPE, JAPAN, ASIA_EX_JAPAN} (resid บน G) → ประเทศเอเชีย {CHINA_ALL, INDIA, KOREA, TAIWAN, ASEAN, VIETNAM} resid บน (G, ASIA_EX_JAPAN) · CHINA_A/H resid บน (G, ASIA_EX_JAPAN, CHINA_ALL) ถ้าใช้ · sector 10 resid บน G (2) auxiliary OLS มีค่าคงที่ ช่วง train 2021–2023 (3) ตรึง β ใช้ในช่วง test (4) ใส่เฉพาะตัวที่ผ่านเกณฑ์ L3 ที่ล็อกใหม่ (ดูคำแนะนำ) · Dimson lag 0 + 1 ตาม BRIEF |
| ร่างสมมติฐาน | H-L3-1a: VIF สูงสุดของชุดลำดับชั้น < 5 โดยไม่ต้องตัดตัวแปร (คาด — ไม่ใช่ผล) · H-L3-1b: R²/α ของกองใน L3-1 เท่ากับชุดดิบที่ span เดียวกันทุกบิต (ตรวจความถูกต้องของโค้ด) · H-L3-1c: ชื่อ primary ของกองภายใต้ลำดับชั้น ตรงกับ primary ของแอปหน้า 1–3 ≥ X% (designer ตั้ง) — ส่วนที่ไม่ตรงคือกองที่ "beta โลก" กลืนสัญญาณประเทศ |

### L3-2 ดัชนี P4 ที่ residualize บน factor ของ L1
| หัวข้อ | เนื้อหา |
|---|---|
| ไอเดีย + กลไก | factor ①a/①c (k = 4) จับโลก/จีน/ดอกเบี้ย/อินเดีย-เวียดนามแล้ว · สิ่งที่ L3 ต้องการคือ "ส่วนเพิ่ม" ของ 6 ดัชนี P4 (HC, UT, Europe, India, Japan, Vietnam) ที่ตั้งฉากกับ factor ชุดหลัก → ได้ factor เพิ่มที่ VIF ต่ำโดยโครงสร้าง และตอบคำถาม L3 ตรงๆ ว่า "ผลยังอยู่ไหมเมื่อตัด collinearity" |
| หลักฐาน | Connor & Korajczyk 1991 hybrid (F-R001 ④-1) · L2 ของทีมเอง (spanning ไปข้างหน้า = residual ชนิดเดียวกัน) · Klein–Chow 2013 · ความแรง: **ปานกลาง** |
| เข้ากับข้อมูล | สูง — ทุกอย่างมีใน `runs/S005/` |
| ชั้น | **L3** |
| วิธีสร้าง | e_j,t = I_j,t − (a_j + b_j′ f_t + c_j′ f_t−1) จาก train · ตรึง a, b, c ในช่วง test · regress กองบน f (lag 0+1) + e_j ที่ผ่าน P4 · รายงาน VIF และ corr ระหว่าง e_j (ใน train ≈ 0 กับ f แต่ e_j กันเองอาจยัง corr) · **ไม่ใช่ข้อมูลใหม่จาก L2 ในเชิง R²** (span เดียวกับ L2-1/L2-3 ที่เพิ่มดัชนีเดียว) — ส่วนที่ใหม่คือรวม 6 ตัวพร้อมกันในชุดเดียว |
| ร่างสมมติฐาน | H-L3-2: median ΔR²_oos (E) ของ ①a + e(P4 6 ตัว) เทียบ ①a ≥ เกณฑ์ที่ล็อก และ ΔBIC ≤ 0 · ถ้า ΔBIC > 0 (แบบ REG8 ใน L2: +31) แปลว่าการรวม 6 ตัวให้ทุกกองไม่คุ้ม → ใช้ e_j เฉพาะกองที่ e_j เป็น primary (แบบ L2-1) |

### L3-3 VIF < 5 backward elimination (เส้นฐานตาม BRIEF)
- BRIEF สั่งไว้ · แอปใช้ `SCORE_COUNTRY_CLEAN` 11 ตัว + `SCORE_VIF_MAX = 5.0` · **ไม่พบงานที่แสดงว่า VIF < 5 เป็นเกณฑ์ที่ดีที่สุด** — เป็นกฎหัวแม่มือ (ค่าตัด 5/10 ใช้กันในตำรา · ยังไม่ยืนยันแหล่ง) · ข้อเสีย: ผลขึ้นกับลำดับการตัด, ตัดดัชนีรวมที่ "ตีความง่าย" ทิ้ง, เปลี่ยน span → R²/α เปลี่ยนแบบแยกสาเหตุไม่ได้
- ใช้เป็น **ตัวเทียบกับแอป** (เชิงบรรยาย) ตาม BRIEF · H-L3-3: ชุด 11 ประเทศของแอป + sector ที่เหลือหลัง VIF < 5 ให้ R²_oos ไม่ต่ำกว่า L3-1 เกิน 0.02 (ถ้าต่ำกว่ามาก = การตัดทิ้งเสียข้อมูล)

### L3-4 ตัวแทนคลัสเตอร์
- `redundancy.csv` ของ L2 มีเลขคลัสเตอร์แล้ว (24 คลัสเตอร์ · ใหญ่สุด 3 ตัว) → ตัวแทน 1 ตัว/คลัสเตอร์ (ตัวที่ตีความง่ายสุด) หรือ PC1 ของคลัสเตอร์ · ง่ายแต่ไม่มีหลักฐานเฉพาะ · ใกล้เคียงกับที่แอปทำ → ไม่แนะนำเป็นรูปแบบแยก (ซ้อนกับ L3-3)

### L3-5 Sharpe RBSA แบบมีข้อจำกัด (ย้ายไปใช้ที่ L4 เชิงบรรยาย)
| หัวข้อ | เนื้อหา |
|---|---|
| กลไก | w ≥ 0 และ Σw = 1 ทำให้ ‖w‖₁ = 1 คงที่ = **การ regularize แบบ L1 ในตัว** (เหตุผลเชิงพีชคณิตของผู้เขียน) → ทนต่อ collinearity ได้ดีกว่า OLS และได้ "สัดส่วนสินทรัพย์" ที่อ่านง่าย |
| หลักฐาน | Sharpe 1992 (F-R001) · Lobosco & DiBartolomeo 1997 (FAJ): สูตรประมาณ CI ของ style weight + ตรวจด้วย Monte Carlo · ใช้ช่วยตัดสินว่าดัชนีไหนควรอยู่ในชุด · งาน SSRN 2001 ใช้ Kuhn–Tucker + simulation หา CI (กองหุ้น UK) · Bodson–Coën–Hübner 2010 เพิ่ม Kalman/EIV · ความแรง **แข็ง** (วิธี) |
| เข้ากับข้อมูล | กลาง — (1) กอง hedge FX มี exposure ติดลบต่อ USD → ต้องใส่ "สินทรัพย์" FX ที่ยอมให้ติดลบ หรือ hedged index (2) Dimson lag: ผลรวม lag 0+1 เป็นน้ำหนักได้ แต่แต่ละ lag ไม่ใช่ → ใช้กับข้อมูลรายเดือน (lag น้อยลง) หรือบังคับที่ผลรวม (3) กอง O (REIT/infra) ไม่มีดัชนีให้ → ต้องดาวน์โหลด |
| ชั้น | **L4** (โปรไฟล์รายกอง + CI) · ไม่ใช่ factor set ร่วม |
| ร่างสมมติฐาน | H-L3-5: สำหรับกอง E ที่ R² ≥ 0.8 น้ำหนัก RBSA ตัวใหญ่สุดตรงกับ primary ของ L3-1 ≥ X% · CI แบบ bootstrap (block 4 สัปดาห์) ของน้ำหนักตัวใหญ่สุดไม่คร่อม 0 |

### L3-6 elastic net / LASSO (diagnostic เท่านั้น)
- หลักฐาน: EFMA 2024 "Sharpening the Sharpe Analysis with Machine Learning" — LASSO สองขั้นเลือก 9 จาก 32 style ที่ลงทุนได้ (กองสหรัฐฯ 1996–2020 รายเดือน) และเตือนว่า LASSO ธรรมดาเลือกผิดได้เมื่อ style มีมิติสูง (ผลค้น · ฉบับเต็มเปิดไม่ได้ HTTP 503) · Giuzio et al. (Annals OR) LASSO/log-penalty กับ style analysis (คำสำคัญเท่านั้น) · elastic net ถูกออกแบบมาสำหรับตัวแปรที่ corr สูง (Zou–Hastie 2005 — ยังไม่ยืนยันแหล่ง)
- ปัญหากับงานเรา: ต้อง tune λ (ขัดหลัก "ไม่ tune") · ชุดที่เลือกต่างกันรายกอง = ไม่ใช่ factor ร่วม · ไม่เสถียรเมื่อ corr > 0.95 (คลัสเตอร์ USA/ACWI/World)
- ใช้ได้เป็น **stability selection**: ในช่วง train เท่านั้น สุ่มครึ่งสัปดาห์แบบ block 100 รอบ λ จาก BIC → รายงานความถี่ที่ดัชนีถูกเลือก (บรรยาย · ไม่ใช่รูปแบบใหม่)

### L4-1 FX factor บังคับใน model α (hedge mechanics)
| หัวข้อ | เนื้อหา |
|---|---|
| ไอเดีย + กลไก | ตาม CIP กอง hedge เต็มได้ ≈ R_สินทรัพย์(USD) + (r_TH − r_US) · กองไม่ hedge ได้ ≈ R_สินทรัพย์(USD) + %ΔUSDTHB → ส่วนต่าง (ไม่ hedge − hedge) ≈ %ΔUSDTHB + r_US − r_TH ≈ **SHV_THB − RF_BOT** = factor FX ของทีม (ค่าชั่วคราว 20) · ดังนั้นกอง hedge ใน model ที่มี MSCI(THB) + FX ควรได้ β_FX ≈ −β_หุ้น และ α ≈ 0 · ถ้า model ไม่มี FX (เช่น ①a ที่ FX แค่ปนใน PC3) **ค่าเฉลี่ยของ FX factor (= carry r_US − r_TH + ค่าเฉลี่ย %ΔUSDTHB) จะไปอยู่ใน α** ของกอง hedge ด้วยเครื่องหมายลบ (QA_L0: ระดับเฉลี่ย DTB3 ≈ 3.23% vs RF_BOT ≈ 1.48%/ปี ช่วง 2021–2025 · ไม่ได้ตรวจซ้ำเอง) |
| หลักฐาน | Greger & Scholz (FAU · SSRN 4565638): factor model มาตรฐานวัดผลงานกอง hedge ผิดเพราะไม่มีผลตอบแทนจากการ hedge · เพิ่ม hedging factor แล้วจับได้ · ทดสอบด้วย **twin share classes** กองหุ้นญี่ปุ่น (พอร์ตเดียวกัน ต่างแค่ hedge) · flow ตามผลจากการ hedge · Opie & Riddiough 2025 WP (กองสหรัฐฯ 1,279 กอง): การจัดการค่าเงินกระทบผลงานรวมน้อยเพราะทำได้ไม่ดี · CIP มีส่วนเบี่ยง (basis) — ขนาดในบาทยังไม่ยืนยันแหล่ง · ความแรง: **ปานกลาง** |
| เข้ากับข้อมูล | สูง — มี SHV_THB, RF_BOT, DTB3, USDTHB · **คู่ hedge/unhedge (twin) ส่วนใหญ่ถูกยุบเป็น family เดียว** ตาม Universe ข้อ 4 (QA_L0 Q3: KKP NDQ100-H-F กับ -UH-F → family KKP NDQ100) แต่บางคู่อยู่ใน panel แยก family (เช่น K-GHEALTH กับ K-GHEALTH(UH) ในรายชื่อ class ปันผลของ Q3) · คู่ที่ถูกยุบอ่านจาก `base_data/` แบบ read-only ได้เป็นชุดตรวจแยก (designer/data-engineer ตัดสิน) |
| ชั้น | **L4** · (ระยะ 2 ถ้าจะทำนาย) |
| วิธีสร้าง | (1) model α ของ L4 = factor ชุดสุดท้ายของ L3 **+ FX ทุกกรณี** (ถ้าชุด L3 ไม่มี) (2) ตรวจ twin: คู่ hedge/unhedge ของ family เดียวกัน (ถ้ามี) → R_unh − R_h ~ FX: คาด slope ≈ สัดส่วนหุ้นต่างประเทศ, intercept ≈ 0 (3) ตาราง 9b ของ L1 ทำซ้ำด้วย model สุดท้าย |
| ร่างสมมติฐาน | H-L4-1a: ใน model ที่มี FX α ของกลุ่ม FX beta ต่ำ vs สูง (ภูมิภาคเดียวกัน) ต่างกัน < 1 %/ปี — ถ้ายังต่าง (เหมือน L1 9b) แปลว่าความต่างมาจากคุณลักษณะอื่น → ส่งต่อ L4-2 · H-L4-1b: คู่ twin มี |intercept| < 1 %/ปี และ slope บน FX ใกล้ 1 |

### L4-2 α̂ ข้ามกอง ~ คุณลักษณะกอง (เชิงอธิบาย · ระยะ 1)
| หัวข้อ | เนื้อหา |
|---|---|
| ไอเดีย + กลไก | α ที่เหลือหลังหัก factor = ค่าธรรมเนียม + ต้นทุน hedge + cash drag + ทักษะ + สิ่งที่ factor ขาด · การ regress α̂ บนคุณลักษณะแยกส่วนเหล่านี้ได้บางส่วน |
| หลักฐาน | Elton–Gruber–Blake 1993 (F-R001): ค่าใช้จ่ายลดผลงานราว 1:1 · Carhart 1997 · **Ferreira, Keswani, Miguel & Ramos 2013** (RoF 17(2) · กองหุ้นเชิงรุก 27 ประเทศ): ตัวกำหนดผลงานในสหรัฐฯ ต่างจากที่อื่น · **ขนาดกองไม่ลดผลงานนอกสหรัฐฯ และสำหรับกองที่ลงทุนต่างประเทศ** · ประเทศที่ตลาดสภาพคล่องสูง/กฎหมายดีมีผลงานดีกว่า · **Cremers, Ferreira, Matos & Starks 2016** (JFE · 32 ประเทศ): α เฉลี่ยของกองเชิงรุกสูงกว่าในประเทศที่มี explicit indexing มาก ต่ำกว่าเมื่อ closet indexing มาก · Amihud–Goyenko 2013 (F-R001) R² ต่ำ ↔ α · ความแรง: **แข็ง** (ข้ามประเทศ) |
| เข้ากับข้อมูล | กลาง — TER จาก `SecFundFee.csv` (F-R001) · FX beta / 1 − R² คำนวณจาก NAV ช่วง train · **ธง class ปันผล 27 กอง (NAV ไม่รวมปันผล → α ติดลบเชิงกล ≈ อัตราปันผล) ต้องเป็นตัวควบคุมบังคับ** · AUM มีรู · FundProfile เป็น snapshot |
| ชั้น | **L4** (บรรยาย) · การใช้ α ≤ t ทำนาย = ระยะ 2 |
| วิธีสร้าง | α̂_i (Dimson α · HAC) จาก model สุดท้าย ช่วง train และช่วงเต็ม 2021–2025 · WLS น้ำหนัก 1/se²(α̂_i) · SE แบบ cluster ตาม **กลุ่มกองอิสระ** (single linkage corr ≥ 0.95 ค่าชั่วคราว 38) · ตัวแปร: TER, ธงปันผล, FX beta (หรือ hedge flag), 1 − R², policy, dummy กลุ่ม primary, log AUM (ถ้ามี) · ห้ามเลือกตัวแปรหลังเห็นผล |
| ร่างสมมติฐาน | H-L4-2a: slope ของ TER ≈ −1 (CI ครอบ −1) · H-L4-2b: ธงปันผลติดลบ · H-L4-2c: หลังคุม TER/ธงปันผล/FX ความต่าง α ระหว่างกลุ่ม FX beta ต่ำ/สูง (L1 9b) ลดลง ≥ ครึ่ง |

### L4-3 การอนุมาน α รายกองเมื่อ N ใหญ่ T สั้น
| หัวข้อ | เนื้อหา |
|---|---|
| ไอเดีย + กลไก | BH 10% ตาม BRIEF ควบคุม FDR แต่ (1) PRDS ไม่ครอบคลุม t สองด้าน (F-R003 → BY คู่) (2) **power ต่ำ** เมื่อ T สั้น → "ไม่พบกองที่มี α" ไม่ใช่หลักฐานว่าไม่มี (3) residual ของกองสัมพันธ์กันมาก ((N−1)ρ̄² > 1 ทุกแถวใน L2) → bootstrap ต้องรักษา cross-correlation |
| หลักฐาน | Barras–Scaillet–Wermers 2010 (F-R001) · **Andrikogiannopoulou & Papakonstantinou 2019** (JF 74(5)): จำลองด้วยพารามิเตอร์จากข้อมูล → FDR ของ BSW อนุรักษ์เกิน · กอง α ±2% ถูกจัดเป็น 0 ถึง 65% เพราะ signal-to-noise ต่ำ · **BSW ตอบกลับ** (SFI 19-61 → JF 2020): ปรับพารามิเตอร์แล้ว bias ลด · ช่วง 1975–2018 เหลือ 32% · สรุปว่าต้องประเมิน DGP ก่อนใช้ FDR **โดยเฉพาะตัวอย่างเล็ก** · **Fama & French 2010** (JF 65(5)): bootstrap ทั้ง cross-section (สุ่มเดือนร่วมทุกกอง → รักษา correlation) · **Kosowski–Timmermann–Wermers–White 2006** (JF 61(6)): bootstrap residual รายกอง · **Harvey & Liu 2022** (JF): FF 2010 มีปัญหา undersampling (ไม่ปฏิเสธแม้มีกอง α สูง) ส่วน KTWW over-reject แม้ทุกกอง α = 0 · **Harvey & Liu 2020** (JF 75(5)): double bootstrap ให้ hurdle t ตาม FDR ที่ต้องการ + คุม Type II · ความแรง: **แข็ง** (มีทั้งต้นฉบับ งานแย้ง และงานตอบ) |
| เข้ากับข้อมูล | สูง — แต่ T = 104 (test) / 155 (train) / ~260 (เต็ม) สั้นกว่างานสหรัฐฯ มาก → คาด power ต่ำกว่า AP 2019 อีก (ความคาดหมาย ไม่ใช่ผล) |
| ชั้น | **L4** |
| วิธีสร้าง | (1) α รายกอง t_HAC → BH 10% (หลัก ตาม BRIEF) + BY คู่ (2) bootstrap แบบ FF 2010 **ปรับเป็น moving block 4 สัปดาห์** (สอดคล้องค่าชั่วคราว 29) บน residual ที่บังคับ α = 0 ทุกกองพร้อมกัน B = 999 seed เดิม → การแจกแจงของ t(α) ที่ percentile 1/5/10/90/95/99 เทียบของจริง (3) **ค่า α ต่ำสุดที่ตรวจจับได้** ต่อกอง (power 80% ที่ α = 5% สองด้าน จาก se จริง) — รายงานเป็น %/ปี (4) ตัดกองซ้ำ corr > 0.99 ก่อน (BRIEF 4) และรายงานนับเป็นกลุ่มกองอิสระ |
| ร่างสมมติฐาน | H-L4-3a: จำนวนกองที่ผ่าน BH ≤ จำนวนที่คาดจากบังเอิญภายใต้ bootstrap null (คือไม่ต่างจากโชค) · H-L4-3b: median α ต่ำสุดที่ตรวจจับได้ของกอง E > 5 %/ปี → ระบุชัดในรายงานว่า "ไม่มีหลักฐาน" ≠ "ไม่มี α" |

### L4-4 factor กลุ่มจาก residual
- กลไก: กองในกลุ่มเดียวกันถือสินทรัพย์ที่ดัชนีไม่ครอบ (เช่น small/mid cap อินเดีย/เวียดนาม · ธีมเทคโนโลยี) → residual สัมพันธ์กันในกลุ่ม · Hunter et al. 2014 APB (F-R001) ลด residual corr ภายในกลุ่ม · Brooks–Del Negro: within-region country effect เป็นอีกครึ่งของ country effect
- ปัญหาขนาดกลุ่ม: primary India 8 · Vietnam 6 · HC 7 · IT 13–16 · China All 20–21 · ACWI_CD 37–42 (§5.1/§6.6 ของ S005) → PCA ในกลุ่ม < 10 กองไม่เสถียร และ IC ชน kmax มาแล้วใน L1
- วิธี: กลุ่ม < 10 กอง → **ค่าเฉลี่ย residual แบบ leave-one-out (= APB ของ residual · k = 1)** · กลุ่ม ≥ 10 → PCA ของ residual + จำนวน factor จาก ED และ PA (ไม่ใช้ IC) kmax 3 · ทั้งหมดประมาณใน train ใช้น้ำหนักตรึงใน test · ตั้งชื่อโดยเทียบกับ ETF ธีม (L4-5) ถ้าดาวน์โหลด
- H-L4-4: factor กลุ่มลด mean |corr| ของ residual ภายในกลุ่มลง ≥ ครึ่ง และเพิ่ม median R²_oos ของกลุ่ม ≥ 0.02 · ถ้าไม่ลด = residual เป็นของเฉพาะกอง (ทักษะ/ค่าธรรมเนียม/noise)

### L4-5 ETF ธีมเป็นตัวเทียบ factor กลุ่มกองธีม (ต้องดาวน์โหลด)
- กลไก: กองธีม (disruptive/genome/clean energy/semis/biotech) ลงทุนในกลุ่มหุ้นที่ MSCI ACWI sector ไม่ตรง · หลักการ index-based model (Sharpe 1992 · CPZ 2013 ใน F-R001) — ดัชนีที่ลงทุนได้และ "ตรงกลยุทธ์" ให้ α ที่ตีความได้ · หลักฐานเฉพาะว่า ETF ธีมอธิบายกองธีม: **ไม่พบ** (ไม่ได้ค้นลึก) → อ่อน–ปานกลาง
- หลักฐานจากข้อมูลของเรา: β ต่อ ACWI_CD ของกลุ่มนี้ไม่เสถียร (r 0.15–0.25) → ACWI_CD น่าจะเป็นตัวแทนที่ผิด
- H-L4-5: ใน 40 กองกลุ่ม ACWI_CD ETF ธีมที่ corr สูงสุดกับ residual factor กลุ่ม (L4-4) มี |corr| ≥ 0.7 ช่วง train และความเสถียร β (r ดิบ) ≥ 0.6

### L4-6 feeder fund / ค่าธรรมเนียมสองชั้น
- กอง FIF ไทย = ลงทุนต่างประเทศ ≥ 80% ของ NAV · feeder ลงทุนในกองหลัก (master) กองเดียว (หน้า SCB ผ่านผลค้น) · ค่าธรรมเนียมเก็บทั้งชั้น feeder และ master (แหล่งทั่วไป · ไม่ใช่งานวิจัย) · **ไม่พบงานวิจัยผลงาน feeder ไทยเทียบ master** (ค้นแล้ว)
- กลไกที่คาด: α_feeder ≈ α_master − TER_feeder − ต้นทุน/ผล hedge − cash drag · ทำได้เมื่อมีธง feeder (ให้ data-engineer ตรวจ field ใน FundProfile — ไม่ได้ตรวจเอง) · ถ้าไม่มี ให้ใช้ TER ใน L4-2 แทน

---

## ไอเดียที่ไม่ควรลอง
| ไอเดีย | เหตุผล |
|---|---|
| Heston–Rouwenhorst dummy regression เต็มรูป | ต้องใช้ผลตอบแทนรายหุ้น/พอร์ต country × industry — เรามีแค่ดัชนี (ใช้แนวคิดลำดับชั้นแทน = L3-1) |
| BHZ risk-based model ประมาณเอง | ต้องใช้พอร์ต country-industry/style ระดับหุ้น · ใช้ข้อสรุป (factor ไม่กี่ตัวดีกว่า dummy) เป็นเหตุผลเท่านั้น |
| LASSO/elastic net เป็นชุด factor สุดท้าย | ต้อง tune λ · เลือกต่างกันรายกอง · ไม่เสถียรในคลัสเตอร์ corr > 0.95 · ใช้เป็น diagnostic เท่านั้น (L3-6) |
| bootstrap แบบ KTWW (รายกองอิสระ) เป็นตัวหลัก | over-reject ตาม Harvey–Liu 2022 · ทำลาย cross-correlation ที่เรามีมาก |
| ประมาณ π₀ / สัดส่วนกองมีทักษะแบบ BSW เป็นพาดหัว | T สั้น → power ต่ำ (AP 2019 · BSW reply เตือนตัวอย่างเล็ก) · รายงานได้เป็นภาคผนวกพร้อมป้าย |
| Kalman filter / style แปรตามเวลา (Bodson et al.) | T 155 สัปดาห์ · พารามิเตอร์มาก · rolling 104 ของ L2 ตอบเรื่องความเสถียรแล้ว → ระยะ 2 ถ้าจำเป็น |
| Fama–MacBeth ทำนาย α / loading ไตรมาสถัดไป | เป็นการทำนาย = ระยะ 2 (นับ trial) |
| ดัชนี MSCI hedged-to-THB / THB forward points | ไม่ยืนยันว่ามีแหล่งฟรี · factor FX = SHV − rf ครอบกลไกเดียวกันแล้ว (L4-1) |
| holdings-based / active share | ไม่มี holdings (เหมือน F-R001) |

---

## คำแนะนำถึง factor-designer

### L3 — แนะนำ **3 รูปแบบ + 1 diagnostic** (ทุกรูปแบบบน ①a และ ①c · k = 4 · ภาคผนวก k = 3/5 แบบ L2)
| รูปแบบ | เนื้อหา | ตอบคำถามอะไร |
|---|---|---|
| **L3-A (บังคับตาม BRIEF / ตัวเทียบแอป)** | factor L1 + `SCORE_COUNTRY_CLEAN` 11 ตัว + sector 10 ตัว → backward elimination จน VIF < 5 บน **ชุดรวม factor + ดัชนี** · ล็อกลำดับการตัด (VIF สูงสุดก่อน · เสมอกันตามชื่อ) | ผลของ L2 อยู่ไหมเมื่อตัดตามแบบแอป |
| **L3-B (แนะนำเป็นรูปแบบหลัก)** | factor L1 + ดัชนี P4 6 ตัว **residualize บน factor L1** (β จาก train ตรึง) · ใส่เฉพาะกองที่ดัชนีนั้นเป็น primary (แบบ L2-1) และแบบใส่ทุกกอง (แบบ REG8) | ส่วนเพิ่มของดัชนีที่ตั้งฉากกับ factor หลัก · VIF ต่ำโดยโครงสร้าง |
| **L3-C (ตัวเทียบที่ลงทุนได้/ตีความได้ทั้งหมด)** | ไม่มี PCA: ACWI + ภูมิภาค resid + ประเทศในภูมิภาค resid + sector resid (ลำดับชั้น L3-1) + FX + ทอง + AGG · เลือกตัวที่เข้าตามเกณฑ์ L3 ที่ล็อก | ชุดดัชนีที่ตีความได้ทั้งหมดใกล้ ①a แค่ไหน (③b ใน L1 ได้ R²_oos E 0.470) |
| diagnostic (ไม่นับเป็นรูปแบบ) | stability selection ด้วย elastic net (train เท่านั้น) · ตรวจว่า L3-B/C เท่ากับชุดดิบ span เดียวกันทุกบิต (test ของโค้ด) · condition number + VIF ทุกรูปแบบ | ความถูกต้อง + ความทนทานของการเลือก |

**ข้อแนะนำเรื่องเกณฑ์ L3 (ล็อกก่อนรัน):** P1(ก) แบบนับกองที่ significant ไม่แยกแยะที่ T = 155 (L2 m2/m4) → เกณฑ์ L3 ควรใช้ **median ΔR²_oos (กอง primary และทุกกอง) + ΔBIC + VIF/condition number** เป็นหลัก · นับเป็นกลุ่มกองอิสระ · ติดป้าย "ช่วง test ใช้เลือกแล้วตั้งแต่ L1" ทุกตาราง · การเปลี่ยนเกณฑ์แบบนี้เป็น **เกณฑ์ของชั้นใหม่** (ไม่ใช่แก้ P1 ของ L2 ย้อนหลัง) แต่ยังต้องบันทึกว่าออกแบบหลังเห็นผล L2 (ข้อ 31/44)

### L4 — โครงที่แนะนำ
1. model α = ชุดสุดท้ายของ L3 **+ FX (บังคับ)** (L4-1)
2. α รายกอง: BH 10% (หลัก) + BY + **bootstrap FF 2010 แบบ block 4 สัปดาห์** + α ต่ำสุดที่ตรวจจับได้ (L4-3)
3. α ข้ามกอง ~ TER + ธงปันผล + FX beta + 1 − R² + policy + กลุ่ม (WLS · cluster กลุ่มกองอิสระ) (L4-2)
4. factor กลุ่ม: LOO-mean residual (< 10 กอง) / PCA + ED/PA (≥ 10 กอง) · ตั้งชื่อด้วย ETF ธีม/ประเทศที่ดาวน์โหลด (L4-4/5)
5. RBSA รายกอง + CI เชิงบรรยาย (L3-5) — ไม่บังคับ

---

## รายการดาวน์โหลดที่เสนอ (session หลักดาวน์โหลด · ข้อมูลตลาดสาธารณะ · เก็บ `.claude/factor_team/data/external/`)
ช่วง 2020-11-02 → ปัจจุบัน รายวัน adjusted close (USD) → แปลงบาทด้วย USDTHB แบบ AGG (งาน data-engineer) · ขนาดประมาณ ~1,500 แถว × จำนวน ticker → ราว 50–150 KB ต่อไฟล์ (ประมาณการ ไม่ได้วัด)

| ลำดับ | ไฟล์ที่เสนอ | แหล่ง / ticker | เหตุผล (ชั้น) | สถานะการยืนยัน |
|---|---|---|---|---|
| 1 | `THEMATIC_ETF.csv` | Yahoo: QQQ, SOXX, ARKK, ICLN, IBB (หรือ XBI), KWEB | ตั้งชื่อ/factor ของกลุ่มกองธีม 37–42 กองที่ β ต่อ ACWI_CD ไม่เสถียร · กองเทค/จีนเทค (L4-4/5) | ticker เป็นที่รู้จัก แต่ **ไม่ได้ยืนยัน inception รายตัว** ในรอบนี้ (ทั้งหมดคาดว่าเริ่มก่อน 2020 — ให้ data-engineer ตรวจแถวแรก) |
| 2 | `ASEAN_COUNTRY_ETF.csv` | Yahoo: THD (MSCI Thailand IMI 25/50 · เริ่ม 2008-03-26), EIDO (2010-05-05), EPHE (2010-09-28), EWM (1996-03-12), EWS (Singapore) | MSCI Thailand แทน TDEX ที่สภาพคล่องต่ำ (SET50) · แยกประเทศในกองอาเซียน (ธง nonFX_eq เช่น KT-ASEAN-A) · L3-1 ชั้น "ประเทศในภูมิภาค" | THD/EIDO/EPHE/EWM ยืนยันวันเริ่มจากหน้า iShares/ผลค้น · EWS ไม่ได้ตรวจ · ETF ปิดเวลา NY → Dimson lag สำคัญ |
| 3 | `REAL_ASSETS_ETF.csv` | Yahoo: REET (Global REIT · 2014-07-08), IGF (Global Infrastructure · 2007-12-10), DBC (Commodity · 2006-02-03), GSG (S&P GSCI · 2006) | กอง O / กอง REIT-infra (เช่น IREITG, PRINCIPAL GREITs, K-GINFRA-A(D), ONE-APACPROP-RD ในรายชื่อ QA_L0 Q3) · ชุด MSCI ของแอป**ไม่มี Real Estate** · RBSA ของกอง O (L3-5/L4) | วันเริ่มจากผลค้น (GSG ต่างกันระหว่างแหล่ง มิ.ย./ก.ค. 2006 — ไม่กระทบช่วง 2021+) |
| 4 | `HEDGED_EQUITY_ETF.csv` | Yahoo: HEWJ (Japan hedged → USD) + EWJ, HEFA (EAFE hedged) + EFA | แยกชั้นค่าเงินที่สาม (JPY/EUR ต่อ USD) ของกองญี่ปุ่น/ยุโรป hedge (L4-1) · **ลำดับรอง** เพราะ hedge ไป USD ไม่ใช่ THB | HEWJ ยืนยันว่ามีข้อมูลถึง ก.ค. 2026 (ผลค้น) · HEFA ไม่ยืนยันสถานะปัจจุบัน · HAWX / DBEF / HEZU ไม่ยืนยัน → ไม่เสนอ |
| — | ดัชนี SET ฉบับทางการ | SET Information Services (ประวัติตั้งแต่ 1975 · **USD 80 ต่อปีข้อมูล** · ใช้ภายใน) | แทน TDEX | **เสียเงิน → อยู่นอกขอบเขตการอนุญาต** (ผู้ใช้ตัดสินใจ · Yahoo ^SET.BK ใช้ไม่ได้ตาม NOTES) |

ไม่เสนอ: ดัชนี hedged-to-THB (ไม่ยืนยันแหล่งฟรี) · THB forward points (ไม่พบแหล่งฟรีที่ยืนยัน) · ETF ประเทศที่ซ้ำกับ M28 (อินเดีย/เวียดนาม/จีน)

---

## ต้องให้ผู้ใช้ตัดสินใจ
1. **รายการดาวน์โหลด 1–4** อยู่ในขอบเขตที่อนุญาตแล้ว (ข้อมูลตลาดสาธารณะ · Yahoo) — session หลักดำเนินการได้ · ผู้ใช้อาจตัดลำดับ 4 (ประโยชน์รอง)
2. **SET ทางการแบบเสียเงิน** (USD 80/ปีข้อมูล) — ซื้อหรือไม่ (agent ซื้อเองไม่ได้) · ทางเลือกฟรี = THD
3. **L3 ใช้ 3 รูปแบบ (A/B/C) ตามข้อแนะนำ** หรือเฉพาะ A (BRIEF) + B
4. **เกณฑ์คัดดัชนีของ L3** ใช้ ΔR²_oos/ΔBIC/VIF แทนการนับกอง significant (ระบุว่าออกแบบหลังเห็นผล L2)
5. **α ของ 27 กอง class ปันผล** — รวมในการจัดอันดับ α รายกองพร้อมธงควบคุม หรือแยกออก (แนะนำ: แยกตารางและใส่ธงใน L4-2)

---

## บรรณานุกรม
ป้าย: **[อ่านเอง-abs]** = เปิดหน้าบทคัดย่อเอง · **[ผลค้น]** = ยืนยันจากผลค้นที่ยกเนื้อหา (ไม่ได้เปิดหน้า) · **[ชื่อเท่านั้น]** · **[ยังไม่ยืนยันแหล่ง]** = จากความจำ
- Heston, S. & Rouwenhorst, K.G. (1994) Does industrial structure explain the benefits of international diversification? JFE 36, 3–27. https://academicnewsletter.sufe.edu.cn/info/358216 [ผลค้น] · แหล่งรอง Flavin (JIMF 2004) https://mural.maynoothuniversity.ie/id/eprint/7999/1/Flavin_JIMF_2004.pdf [ผลค้น] · Phylaktis https://www.bayes.city.ac.uk/__data/assets/pdf_file/0004/29074/Phylaktis_ChangingRoles.pdf [ผลค้น]
- Griffin & Karolyi (1998) · Roll (1992) — ผ่านแหล่งรองในผลค้นเท่านั้น [ผลค้น · แหล่งรอง]
- Bekaert, G., Hodrick, R. & Zhang, X. (2009) International Stock Return Comovements. JF 64(6), 2591–2626. https://www.nber.org/papers/w11906 [อ่านเอง-abs]
- Brooks, R. & Del Negro, M. Country versus region effects / International stock returns and market integration: a regional perspective. Atlanta Fed WP. https://www.atlantafed.org/research/publications/wp/2002/20.aspx [ผลค้น] (สถานะตีพิมพ์ยังไม่ยืนยัน)
- Klein, R. & Chow, V. (2013) Orthogonalized factors and systematic risk decomposition. QREF 53(2), 175–187. https://ideas.repec.org/a/eee/quaeco/v53y2013i2p175-187.html [ผลค้น]
- Lobosco, A. & DiBartolomeo, D. (1997) Approximating the confidence intervals for Sharpe style weights. FAJ. https://rpc.cfainstitute.org/research/financial-analysts-journal/1997/approximating-the-confidence-intervals-for-sharpe-style-weights [ผลค้น]
- Bodson, Coën & Hübner (2010) Dynamic hedge fund style analysis with errors-in-variables. JFR. https://orbi.uliege.be/handle/2268/9994 [ผลค้น]
- "Sharpening the Sharpe Analysis with Machine Learning" (EFMA 2024). https://www.efmaefm.org/0EFMAMEETINGS/EFMA%20ANNUAL%20MEETINGS/2024-Lisbon/papers/SharpeningtheSharpeAnalysiswithMachineLearning20231206.pdf [ผลค้น · เปิดแล้ว HTTP 503] · Giuzio et al. (Annals OR) https://unimore.unifind.cineca.it/resource/item/153332 [ชื่อเท่านั้น] · ter Horst, Nijman & de Roon "Evaluating style analysis" https://research.tilburguniversity.edu/en/publications/evaluating-style-analysis/ [ชื่อเท่านั้น]
- Zou & Hastie (2005) elastic net [ยังไม่ยืนยันแหล่ง]
- Andrikogiannopoulou, A. & Papakonstantinou, F. (2019) Reassessing False Discoveries in Mutual Fund Performance: Skill, Luck, or Lack of Power? JF 74(5), 2667–2688. https://academicnewsletter.sufe.edu.cn/info/359431 [ผลค้น]
- Barras, Scaillet & Wermers (2019/2020) Reply. SFI 19-61. https://sfi.ch/en/publications/n-19-61-reassessing-false-discoveries-in-mutual-fund-performance-skill-luck-or-lack-of-power-a-reply [อ่านเอง-abs]
- Fama, E. & French, K. (2010) Luck versus Skill in the Cross-Section of Mutual Fund Returns. JF 65(5), 1915–1947. https://ideas.repec.org/a/bla/jfinan/v65y2010i5p1915-1947.html [ผลค้น]
- Kosowski, Timmermann, Wermers & White (2006) Can Mutual Fund "Stars" Really Pick Stocks? JF 61(6), 2551–2595. https://ideas.repec.org/a/bla/jfinan/v61y2006i6p2551-2595.html [ผลค้น] · replication (Riley & Walton) https://alphaarchitect.com/are-fund-managers-stars-skilled-at-picking-stocks-an-out-of-sample-test/ [ผลค้น]
- Harvey, C. & Liu, Y. (2020) False (and Missed) Discoveries in Financial Economics. JF 75(5), 2503–2553. https://arxiv.org/abs/2006.04269v1 [ผลค้น] · Harvey & Liu (2022) Luck versus Skill … Reexamining the Evidence. JF. https://people.duke.edu/~charvey/Research/Published_Papers/P151_Luck_versus_skill.pdf [ผลค้น]
- Ferreira, Keswani, Miguel & Ramos (2013) The Determinants of Mutual Fund Performance: A Cross-Country Study. RoF 17(2), 483–525. https://openaccess.city.ac.uk/13633 [ผลค้น]
- Cremers, Ferreira, Matos & Starks (2016) Indexing and Active Fund Management: International Evidence. JFE. https://run.unl.pt/handle/10362/14561 [ผลค้น]
- Greger, L. & Scholz, H. Currency-Hedged Equity Funds: Performance and Fund Flows. SSRN 4565638. https://cris.fau.de/publications/318180820 [อ่านเอง-abs]
- Opie & Riddiough (2025 WP) — F-R001 + https://www.aeaweb.org/conference/2026/program/paper/ab4B3esy [ผลค้น]
- FIF/feeder ไทย: https://www.scb.co.th/en/personal-banking/stories/grow-your-wealth/foreign-investment-funds [ผลค้น] · ESMA Q&A (ค่าธรรมเนียม feeder ในยุโรป · เทียบเท่านั้น) https://www.esma.europa.eu/node/220779 [ผลค้น]
- ข้อมูล ETF: iShares THD https://www.ishares.com/uk/professional/en/products/239688/ishares-msci-thailand-capped-etf · EPHE https://www.ishares.com/uk/professional/en/products/239675/ishares-msci-philippines-etf · EWM fact sheet https://www.ishares.com/us/literature/fact-sheet/ewm-ishares-msci-malaysia-etf-fund-fact-sheet-en-us.pdf · EIDO https://stockanalysis.com/etf/EIDO/ · REET https://www.tradingview.com/symbols/AMEX-REET/ · IGF https://stockanalysis.com/etf/igf/ · DBC (SEC) https://www.sec.gov/Archives/edgar/data/0001328237/000119312518329088/d655228dfwp.htm · GSG https://www.trackinsight.com/en/fund/GSG · HEWJ https://etf.pionline.com/fund/HEWJ · HEFA https://www.etfrc.com/HEFA [ผลค้นทั้งหมด]
- SET Information Services (ข้อมูลย้อนหลังเสียเงิน) https://www.set.or.th/en/services/connectivity-and-data/data/historical [ผลค้น]

## สิ่งที่ยังค้าง
- ยังไม่ได้อ่านฉบับเต็ม: HR 1994 (สมการ dummy), BHZ 2009 (ชุด factor ที่ชนะ), Brooks–Del Negro, AP 2019 (พารามิเตอร์จำลอง), FF 2010 (รายละเอียด bootstrap), Greger–Scholz (สมการ hedging factor), EFMA 2024 (503)
- ยังไม่ได้ยืนยัน: inception ของ ETF ธีม / EWS · สถานะปัจจุบันของ HEFA · ขนาดส่วนเบี่ยง CIP ของบาท · field feeder ใน FundProfile
