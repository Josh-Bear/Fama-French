# F-R001 — สำรวจวรรณกรรม 4 สาย + วิธีเปรียบเทียบ/ทดสอบ model (kick-off)

ผู้เขียน: factor-researcher · วันที่ 2026-10-15 · ชั้นที่ป้อน: L1 (บางไอเดียป้อน L2–L4 / ระยะ 2)
อ่านก่อนเขียน: `.claude/agents/factor-researcher.md`, `.claude/factor_team/BRIEF.md`, `research/INDEX.md` (ว่าง), `docs/appendix/data-sources.md` (ส่วน MSCI / style / macro),
`quant_team/research/R001_fund_selection_signals.md` (ส่วนหัว — ใช้อ้างอิงเรื่อง persistence/ค่าธรรมเนียม ไม่ค้นซ้ำ)
ข้อจำกัดของรายงานนี้: ส่วนใหญ่ยืนยันจาก **หน้า abstract / หน้าวารสาร / หน้า NBER-SSRN** ที่ค้นเจอ ไม่ได้อ่านฉบับเต็มทุกเรื่อง —
รายละเอียดที่มาจากความจำติดป้าย **"ยังไม่ยืนยันแหล่ง"** · ไม่มีตัวเลขใดมาจากข้อมูลของทีม · ไม่พบหน้าเว็บที่มีข้อความสั่งการ (prompt injection)

## บทสรุป 5 บรรทัด
1. ข้อมูลเราเป็นแบบ **N > T** (กองหลายร้อย × ~260 สัปดาห์ · train 2021–2023 ≈ 156 สัปดาห์) → เครื่องมือที่ออกแบบมาเพื่อ N > T คือ Connor–Korajczyk (APC), Bai–Ng IC, Ahn–Horenstein และสำหรับทดสอบ α ทั้ง universe คือ **Pesaran–Yamagata** (เสนอเพิ่มจาก BRIEF ที่มีแค่ GRS บนพอร์ตกลุ่ม)
2. หลักฐานแข็งสุดสำหรับ "อธิบายผลตอบแทนกอง" คือ **model จากดัชนีที่ลงทุนได้ (index-based / returns-based style)** — Sharpe 1992, Elton–Gruber–Blake, Cremers–Petajisto–Zitzewitz 2013 ชี้ว่าดัชนีลงทุนได้ดีกว่า factor แบบ FF ในการประเมินกอง → สาย ③ น่าจะเป็นคู่แข่งหลัก
3. factor ที่สร้างจาก "ตัวกองเอง" ที่มีหลักฐานดีที่สุดคือ **Active Peer Benchmark** (ค่าเฉลี่ยกองในกลุ่มเดียวกัน — Hunter et al. 2014 + ทดสอบซ้ำ UK + วิทยานิพนธ์ไทย) ส่วน long–short ตามค่าธรรมเนียม / ขนาด มีกลไกอ่อนต่อ "ความแปรปรวนร่วม" (กระทบค่าเฉลี่ยมากกว่า)
4. ไอเดียใหม่ที่คุ้มสุด (④) คือ **hybrid**: factor ภายนอกชุดเล็ก + PC ของ residual 1–3 ตัว (แนวเดียวกับ Connor–Korajczyk 1991 ที่ใช้กับกองทุน) — ตอบคำถาม L2 ไปด้วยว่า PCA จับอะไรที่ดัชนีไม่จับ
5. การเปรียบเทียบข้ามสายควรใช้ **spanning / Barillas–Shanken** (model ไหน price factor ของอีก model ได้) ควบคู่ตารางคะแนนกลาง — ไม่ตัดสินจาก R² ของ test asset อย่างเดียว (Lewellen–Nagel–Shanken 2010) · factor ใหม่ของ ④ ใช้เกณฑ์ t > 3 (Harvey–Liu–Zhu)

---

## ข้อสังเกตเชิงโครงสร้างก่อนดูไอเดีย (สำคัญต่อทุกสาย)
- **E / F / O ต่างความผันผวนมาก** (BRIEF: กอง F ขยับน้อย) → PCA บน covariance จะถูกกองหุ้นครอบงำ PC1 · ควรมีทั้งแบบ correlation (standardize รายกอง) และแบบแยก policy — เป็น trade-off ที่ designer ต้องล็อกก่อนรัน
- **circularity ของสาย ② และ APB**: factor ที่สร้างจากกองชุดเดียวกับ test asset จะดัน R² ขึ้นเชิงกล (กองตัวเองอยู่ในพอร์ต) → แนะนำ leave-one-out (ตัดกองนั้นออกจาก factor ตอน regress กองนั้น) หรืออย่างน้อยกลุ่มต้องใหญ่พอ · ตารางคะแนนข้อ 2 (นอกช่วง) ช่วยได้บางส่วนแต่ไม่หมด
- **ความถี่รายสัปดาห์ช่วยเรื่อง NAV ไม่พร้อมกัน** แต่ไม่หมด — Goetzmann–Ivković–Rouwenhorst 2001 แสดงว่า NAV กองต่างประเทศใช้ราคาปิดเก่า (time zone) ทำให้ผลตอบแทนกองทำนายได้จากตลาดที่ปิดทีหลัง → Dimson lag 1 ตาม BRIEF ถูกทาง

---

## ตารางอันดับไอเดีย
คะแนน = (หลักฐาน 1–3 × เข้ากับข้อมูล 1–3) ÷ ความซับซ้อน 1–3

### สาย ① pure stat
| # | ไอเดีย | หลักฐาน | เข้ากับข้อมูล | ซับซ้อน | คะแนน |
|---|---|---|---|---|---|
| ①-1 | PCA บน balanced sub-panel + เลือก k ด้วยหลายเกณฑ์ (Bai–Ng IC, Ahn–Horenstein ER/GR, Onatski ED, parallel analysis) | แข็ง (3) | สูง (3) | 1 | **9.0** |
| ①-2 | Connor–Korajczyk APC (eigen ของเมทริกซ์ T×T) | แข็ง (3) | สูง (3) — N > T พอดี | 1 | **9.0** (เป็นตัวคำนวณเดียวกับ ①-1 ในทางปฏิบัติ — รวมเป็น variant เดียวได้) |
| ①-3 | PCA รองรับข้อมูลขาด (Xiong–Pelger adjusted-covariance / EM) บน unbalanced panel | ปานกลาง (2) | สูง (3) — กองเลิก/เปิดใหม่ | 2 | 3.0 |
| ①-4 | IPCA ใช้คุณลักษณะกอง (ค่าธรรมเนียม, AUM, FX beta, R², policy) เป็น instrument ของ loading | ปานกลาง (2) — หลักฐานจากหุ้นสหรัฐฯ + มีงานโต้แย้ง | กลาง (2) — คุณลักษณะเป็น snapshot | 3 | 1.3 |

### สาย ② Fama-French ของกองทุน (factor สร้างจากกอง)
| # | ไอเดีย | หลักฐาน | เข้ากับข้อมูล | ซับซ้อน | คะแนน |
|---|---|---|---|---|---|
| ②-1 | **Active Peer Benchmark (APB)** — ค่าเฉลี่ยถ่วงเท่ากันของกองในกลุ่มเดียวกัน (policy / primary country / sector) | แข็ง–ปานกลาง (3) — JFE + UK + ไทย | สูง (3) | 1 | **9.0** |
| ②-2 | **FX-hedge factor** — กอง FX beta ต่ำ (hedge มาก) ลบ FX beta สูง ภายในกลุ่มประเทศเดียวกัน | ปานกลาง (2) | สูง (3) — กอง FIF ไทย hedge ต่างกันมาก | 2 | 3.0 |
| ②-3 | Fund momentum (winners − losers ตามผลตอบแทน 52 สัปดาห์ เว้น 4 สัปดาห์ล่าสุด) | ปานกลาง (2) — Carhart: persistence มาจาก momentum ของหุ้น | สูง (3) | 2 | 3.0 |
| ②-4 | Active − passive (1 − R² ต่อดัชนีหลัก) | ปานกลาง (2) — มี decay/โต้แย้ง | กลาง (2) — ต้องวัดด้วยข้อมูลต้นช่วง | 2 | 2.0 |
| ②-5 | ขนาด AUM (เล็ก − ใหญ่) | อ่อน (1) — กลไกต่อ covariance อ่อน | กลาง (2) — AUM มีรู | 2 | 1.0 |
| ②-6 | ค่าธรรมเนียม (แพง − ถูก) | แข็งต่อ "ค่าเฉลี่ย/α" แต่อ่อนต่อ covariance (1) | สูง (3) — `SecFundFee.csv` | 2 | 1.5 → ใช้เป็นตัวตรวจ α มากกว่าเป็น factor |

### สาย ③ factor ภายนอก
| # | ไอเดีย | หลักฐาน | เข้ากับข้อมูล | ซับซ้อน | คะแนน |
|---|---|---|---|---|---|
| ③-1 | **ชุดเล็ก asset-class (Sharpe/EGB style)**: ACWI(THB)−rf · AGG(THB)−rf · ทอง(THB) · ΔUSDTHB | แข็ง (3) | สูง (3) | 1 | **9.0** |
| ③-2 | ③-1 + EM − DM · US − ACWI (+ SET ถ้าผู้ใช้อนุมัติ) | ปานกลาง–แข็ง (2–3) | สูง (3) | 1 | 6.0–9.0 |
| ③-3 | ③-2 + style ETF 4 (de-market) + macro (Δ US10Y, Δ VIX, oil) | ปานกลาง (2) | กลาง (2) — macro เป็นรายเดือนในแอป ต้องทำรายสัปดาห์ · collinearity | 2 | 2.0 |
| ③-4 | ฝั่งตราสารหนี้ (กอง F): term (IEF − AGG) · Δ US10Y · rf ธปท. | ปานกลาง (2) — EGB 1995 | กลาง (2) — **ไม่มี credit spread / บอนด์ไทย** | 1 | 4.0 |

### สาย ④ factor ใหม่
| # | ไอเดีย | หลักฐาน | เข้ากับข้อมูล | ซับซ้อน | คะแนน |
|---|---|---|---|---|---|
| ④-1 | **Hybrid: ③-1 + PC ของ residual k ตัว** | ปานกลาง (2) — CK 1991 hybrid สำหรับกองทุน | สูง (3) | 2 | **3.0** |
| ④-2 | **Thai-domestic peer factor** สำหรับกองหุ้นไทย (APB ของกองหุ้นไทย หรือ SET) แยกจาก factor โลก | ปานกลาง (2) | สูง (3) ถ้าใช้ APB · ขึ้นกับผู้ใช้ถ้าใช้ SET | 1 | 6.0 (แต่ซ้อนกับ ②-1/③-2 — ใช้เป็น variant) |
| ④-3 | **Hedge-cost factor**: Δ(ดอกเบี้ยระยะสั้นสหรัฐฯ − rf ธปท.) — ต้นทุน hedge ตาม CIP กระทบกองที่ hedge | อ่อน (1) — กลไกชัดแต่ไม่พบงานทดสอบกับกองโดยตรง | ต่ำ (1) — **ไม่มีดอกเบี้ยสั้นสหรัฐฯ ในระบบ** | 2 | 0.5 → รอผู้ใช้ตัดสินใจ |
| ④-4 | Factor momentum (จับจังหวะ factor ตามผลตอบแทน 12 เดือนก่อน) | ปานกลาง–แข็ง (2) | — | — | **ระยะ 2 เท่านั้น** |

---

## รายละเอียดต่อไอเดีย

### ①-1 / ①-2 PCA + การนับจำนวน factor (รวมเป็น variant เดียว)
| หัวข้อ | เนื้อหา |
|---|---|
| ไอเดีย + กลไก | กองส่วนใหญ่ถือสินทรัพย์ไม่กี่กลุ่ม (หุ้นโลก/ไทย, บอนด์, เงินบาท) → covariance ของกองควรมีโครงสร้าง factor แรงไม่กี่ตัว (Sharpe 1992 พบว่า asset class จำนวนน้อย replicate กองสหรัฐฯ ส่วนใหญ่ได้) |
| หลักฐาน | Bai & Ng 2002 (Econometrica): เกณฑ์ IC ประมาณ k ได้คงเส้นคงวาโดยไม่จำกัดความสัมพันธ์ N–T · Alessi–Barigozzi–Capasso 2008 (ECB WP 903) ปรับ penalty ให้ทนทานขึ้น · Ahn & Horenstein 2013 (Econometrica): ratio ของ eigenvalue ติดกัน · Onatski 2010 (REStat): edge distribution · Connor & Korajczyk 1986/1988/1993: APC สำหรับ N ใหญ่ + test จำนวน factor (พบ 1–6 factor ในหุ้น NYSE/AMEX) · Jones 2001 (JFE): ผลขึ้นกับ heteroskedasticity ของ residual · parallel analysis (Horn 1965) ใช้แพร่หลายในจิตวิทยา — **ไม่พบงานการเงินที่ใช้โดยตรง** · ความแรง: **แข็ง** (วิธี) — แต่เกณฑ์ต่างๆ มักให้ k ไม่ตรงกัน |
| เข้ากับข้อมูลเราไหม | ดีมาก · N > T · balanced sub-panel = กองที่มี NAV ครบช่วง train (survivorship เล็กน้อย — ระบุเป็นข้อจำกัด) |
| ชั้นที่ใช้ | L1 (และ L4: PCA ของ residual ภายในกลุ่ม) |
| วิธีสร้าง | excess return รายสัปดาห์ → (ก) standardize รายกอง (correlation PCA) เป็นหลัก (ข) covariance PCA เป็น sensitivity · kmax = 10 (ไม่ tune) · รายงาน IC_p1, IC_p2 (Bai–Ng), ER/GR (A–H), ED (Onatski), parallel analysis (95th percentile, permutation รายคอลัมน์) · OOS: น้ำหนัก PC จาก 2021–2023 → factor return ช่วง 2024–2025 = น้ำหนักเดิม × ผลตอบแทนกองที่ยังอยู่ (normalize น้ำหนักใหม่เมื่อกองหาย) |
| ร่างสมมติฐาน | H①: มี k ≤ 5 factor ที่ให้ median adj R² ของกอง E ≥ ระดับของ ③-1 ทั้งในและนอกช่วง · PC1 มี corr สูงกับ ACWI(THB) · ถ้าเกณฑ์นับ factor ขัดกัน ให้รายงานทุกค่าและใช้ค่ามัธยฐานของเกณฑ์ (ล็อกก่อนรัน) |

### ①-3 PCA กับ panel ที่ข้อมูลขาด
| หัวข้อ | เนื้อหา |
|---|---|
| ไอเดีย + กลไก | กองเลิก/เปิดใหม่ทำให้ balanced panel ตัดกองทิ้งมาก → bias ไปทางกองอายุยาว |
| หลักฐาน | Xiong & Pelger (arXiv 1910.08273, 2019–2022): PCA บน covariance ที่ปรับจากข้อมูลบางส่วน + ทฤษฎีการแจกแจง · Duan–Pelger–Xiong 2023 (Target PCA) · EM แบบ Stock–Watson **ยังไม่ยืนยันแหล่ง** · ความแรง: **ปานกลาง** (ทฤษฎีดี ใช้กับกองทุนน้อย) |
| เข้ากับข้อมูล | สูง — BRIEF ระบุ unbalanced panel อยู่แล้ว |
| ชั้น | L1 (variant ที่ 2 ของสาย ①) |
| วิธีสร้าง | ใช้คู่ (i,j) ที่มีข้อมูลร่วม ≥ 52 สัปดาห์ในการคำนวณ covariance · k ล็อกเท่ากับ ①-1 (ไม่เลือกใหม่) |
| ร่างสมมติฐาน | H①b: factor จาก unbalanced panel มี corr > 0.9 กับ factor จาก balanced panel ในช่วงที่ทับกัน — ถ้าไม่ แสดงว่า balanced panel มี selection bias |

### ①-4 IPCA (ไม่แนะนำสำหรับ L1 รอบแรก)
- Kelly, Pruitt & Su 2019 (JFE 134(3)): characteristic เป็น instrument ของ loading ที่เปลี่ยนตามเวลา · มีงานโต้แย้ง Fieberg et al. 2020 ("Are characteristics covariances?") — ไม่ได้อ่านเนื้อหา
- เหตุผลที่เลื่อน: FundProfile เป็น snapshot ปัจจุบัน (ไม่ใช่ point-in-time) → instrument ที่เปลี่ยนตามเวลาจริงมีแค่ที่คำนวณจาก NAV (momentum, FX beta, R²) · ซับซ้อนสูงเทียบกับ T สั้น · เหมาะเป็นระยะ 2 หรือ L4

### ②-1 Active Peer Benchmark (APB)
| หัวข้อ | เนื้อหา |
|---|---|
| ไอเดีย + กลไก | กองในกลุ่มเดียวกันถือหุ้น/ดัชนีคล้ายกันและตามกลยุทธ์คล้ายกัน → ค่าเฉลี่ยกลุ่มจับ "กลยุทธ์ร่วม" ที่ factor มาตรฐานพลาด |
| หลักฐาน | Hunter, Kandel, Kandel & Wermers 2014 (JFE 112(1)): เพิ่ม APB ใน 4-factor (หุ้น) / 7-factor (ตราสารหนี้) ลด corr ของ residual ระหว่างกองในกลุ่มอย่างมาก · ทดสอบซ้ำ UK: Mateus, Mateus & Todorovic 2019 (EJF) · ไทย: วิทยานิพนธ์จุฬาฯ 2021 (กองหุ้นไทยเชิงรุก 2006–2020) รายงานว่า APB ลด residual corr — **อ่านเฉพาะบทคัดย่อ** · ความแรง: **แข็ง–ปานกลาง** |
| เข้ากับข้อมูล | สูง — ใช้แค่ NAV + กลุ่ม (policy / primary country / sector จากแอป — ระวัง primary จาก `cache/coefs.csv` fit ทั้งช่วง: ระยะ 1 ใช้ได้เชิงบรรยาย แต่ OOS ควรใช้กลุ่มจาก FundProfile หรือ exposure ช่วง train) |
| ชั้น | L1 (สาย ②) · L4 (factor ระดับกลุ่ม) |
| วิธีสร้าง | APB_g,t = ค่าเฉลี่ยถ่วงเท่ากันของ excess return ของกองในกลุ่ม g (leave-one-out เมื่อ regress กองในกลุ่ม) · กลุ่มต้องมี ≥ 10 กอง ไม่งั้นรวมกับกลุ่มใกล้เคียง |
| ร่างสมมติฐาน | H②a: model "ตลาดกองทั้งหมด + APB ตาม policy" ให้ R² นอกช่วงไม่ต่ำกว่า ③-1 สำหรับกอง E · การเพิ่ม APB บน ③-1 ลด mean |corr| ของ residual ภายในกลุ่มลง (คะแนนเสริม — ไม่ได้อยู่ในตารางกลาง ให้ designer พิจารณาใส่เป็นตัวบรรยาย) |

### ②-2 FX-hedge factor
| หัวข้อ | เนื้อหา |
|---|---|
| ไอเดีย + กลไก | กอง FIF ไทยเลือกระดับ hedge ต่างกัน (0–100%) → ผลตอบแทนบาทของกองลงทุนตลาดเดียวกันต่างกันตามการเคลื่อนไหวของเงินบาท — เป็นแหล่ง covariance ที่ดัชนี MSCI(THB) แบบไม่ hedge ไม่จับ |
| หลักฐาน | Opie & Riddiough (2025, working paper — กองหุ้นต่างประเทศสหรัฐฯ): การบริหารค่าเงินมีผลต่อผลงานจำกัดเพราะทำได้ไม่ดี · Benson & Faff 2004 (PBFJ, กองต่างประเทศออสเตรเลีย): กองที่บริหารค่าเงินมี exposure ต่อค่าเงินลดลง · Lustig–Roussanov–Verdelhan 2011 (RFS): ค่าเงินมี factor ร่วม (dollar / slope) — **รายละเอียด dollar factor ยังไม่ยืนยันแหล่ง** · ความแรง: **ปานกลาง** (กลไกชัด หลักฐานกับกองโดยตรงน้อย) |
| เข้ากับข้อมูล | สูง — beta ต่อ ΔUSDTHB จาก NAV ช่วงต้น (ต้องประมาณด้วยข้อมูล ≤ ต้นช่วง) |
| ชั้น | L1 (สาย ②) · L3 (ทดสอบว่าซ้อนกับ ΔUSDTHB ใน ③ แค่ไหน) |
| วิธีสร้าง | regress กองบน [MSCI ประเทศหลัก(THB), ΔUSDTHB] ด้วย 52 สัปดาห์แรก → เรียง FX beta ภายในกลุ่มประเทศ → 30/40/30 (breakpoint แบบ FF) → low − high ถ่วงเท่ากัน |
| ร่างสมมติฐาน | H②b: FX-hedge factor มี corr สูงกับ −ΔUSDTHB และให้ incremental R² เฉพาะกอง FIF · ถ้า incremental R² ≈ 0 เมื่อมี ΔUSDTHB ใน model แล้ว ให้สรุปว่า ③ ครอบคลุมแล้ว |

### ②-3 Fund momentum
- Carhart 1997 (JF): persistence ของกองถูกอธิบายเกือบหมดด้วย 4 factor (รวม momentum หุ้น) + ค่าใช้จ่าย · กองหุ้นไทย: วิทยานิพนธ์ Nottingham 2018 (242 กองหุ้นไทย 2009–2017) รายงานว่า Carhart fit ดีที่สุดและผลงานมาจาก momentum — **อ่านเฉพาะบทคัดย่อ (ฉบับเต็มจำกัดสิทธิ์)**
- ความแรง: **ปานกลาง** · Asness–Moskowitz–Pedersen 2013 (JF): momentum 12-1 มีในดัชนีประเทศด้วย → momentum ของกองต่างประเทศไทยน่าจะเป็น country momentum (สอดคล้อง quant_team R001)
- วิธี: formation 52 สัปดาห์เว้น 4 สัปดาห์ (แปลงจาก 12-1 เดือน) · rebalance รายไตรมาส · 30/40/30 · **ห้ามใช้ข้อมูลหลังวัน formation**
- H②c: fund-momentum factor มี corr กับ "country momentum" ที่สร้างจาก MSCI 28 สูง (ตรวจที่ L2)

### ②-4 ถึง ②-6 (ใส่เฉพาะ variant ขยาย)
- Amihud & Goyenko 2013 (RFS): R² ต่ำ + α สูงทำนาย α (3.8%/ปี ในกองหุ้นสหรัฐฯ) · มีงานโต้แย้ง (Universitat Jaume I) ว่าเกิดจากประเภทหุ้นที่ถือ ไม่ใช่ skill · Brazil นำไปใช้
- Elton–Gruber–Blake 1993 (J. Business): ค่าใช้จ่ายสูงขึ้น ≈ ผลงานลดลงหนึ่งต่อหนึ่ง (กองตราสารหนี้สหรัฐฯ) → ค่าธรรมเนียมกระทบ **ค่าเฉลี่ย** ไม่ใช่ covariance · ใช้เป็นตัวตรวจ α (L4) ดีกว่าเป็น factor
- ขนาด: Fama–French 2012 (JFE, 23 ประเทศพัฒนาแล้ว 1989–2010) พบ size premium ระหว่างประเทศอ่อน · AUM กองไทยมีรู → คะแนนต่ำ

### ③-1 / ③-2 Asset-class factor ชุดเล็ก (index-based model)
| หัวข้อ | เนื้อหา |
|---|---|
| ไอเดีย + กลไก | กองไทยส่วนใหญ่ถือหุ้นโลก/ภูมิภาค บอนด์ ทอง และรับผลค่าเงินบาท — factor ที่เป็นดัชนีลงทุนได้จึงอธิบายได้ตรงกลไกที่สุด และ α ของดัชนีเองควรเป็นศูนย์ |
| หลักฐาน | Sharpe 1992 (JPM): returns-based style analysis — asset class ไม่กี่กลุ่มอธิบายกองสหรัฐฯ ได้มาก (จำกัดเฉพาะกองที่ไม่เทรดเชิงพลวัต) · Cremers, Petajisto & Zitzewitz 2013 (CFR): FF/Carhart ให้ α ไม่เป็นศูนย์แม้กับดัชนี passive · model จากดัชนีลงทุนได้ประเมินกองได้ดีกว่า · Fung & Hsieh 2004 (FAJ): factor จากราคาตลาด 7 ตัวอธิบายได้ถึง 80% ของ hedge fund index · Edelman–Fung–Hsieh–Naik 2012: เพิ่ม EM factor แล้วกลายเป็น factor เด่นช่วง 2005–2010 (สนับสนุน EM − DM) · Fama–French 2012: factor แบบ local อธิบายดีกว่า global (สนับสนุนการมี factor ไทย/ภูมิภาคแยก) · ความแรง: **แข็ง** |
| เข้ากับข้อมูล | สูง — ACWI (ใน MSCI/style ETF), AGG/IEF (แปลงบาท), ทอง, USDTHB มีครบตาม L0 · ระวัง ETF ปิดเวลา NY (BRIEF) → Dimson lag สำคัญ |
| ชั้น | L1 (สาย ③) → L2 (เพิ่ม MSCI 28) |
| วิธีสร้าง | excess return รายสัปดาห์ในรูปบาท − rf ธปท. · ΔUSDTHB เป็น % · EM − DM = MSCI EM(THB) − MSCI World(THB) ถ้ามีในชุด 28 (ให้ data-engineer ยืนยัน) · US − ACWI · lag 0 + lag 1 ทุกตัว |
| ร่างสมมติฐาน | H③: ชุด 4 factor (③-1) ให้ median adj R² ของกอง E ใกล้กับ PCA k = 4 ในช่วงนอกตัวอย่าง (เพราะไม่มีน้ำหนักที่ fit) · ③-2 เพิ่ม R² ให้กองเอเชีย/EM เป็นหลัก |

### ③-3 ชุดขยาย style + macro
- AMP 2013 และ FF 2012 สนับสนุน value/momentum ระดับโลก → style ETF (de-market แบบ `data.style_factor`) มีเหตุผล · VIX / US10Y เป็น factor ที่ **ลงทุนไม่ได้** → ใช้ใน Barillas–Shanken ไม่ได้โดยตรง (ต้องทำ mimicking portfolio) · collinearity สูง (DXY vs USDTHB, VIX vs ACWI) → ตรวจ VIX ที่ L3
- ความแรงต่อกองไทย: **ปานกลาง** · ความเสี่ยง overfit สูงสุดในสาย ③ — ใช้เป็น variant บนสุดเท่านั้น

### ③-4 ฝั่งตราสารหนี้ (กอง F)
- Elton, Gruber & Blake 1995 (JF): index factor อธิบายส่วนใหญ่ของกองตราสารหนี้ ตัวแปรเศรษฐกิจเพิ่มได้อีกพอสมควร · Silva–Cortez–Armada 2003 (กองตราสารหนี้ยุโรป): multi-index เพิ่มคำอธิบายจาก single index
- **ช่องว่างใหญ่**: ไม่มีดัชนีบอนด์ไทย / credit spread ในระบบ — กอง F ไทยส่วนมากน่าจะถือตราสารหนี้ไทยระยะสั้น → R² ของกอง F จากบอนด์สหรัฐฯ น่าจะต่ำ (เป็นความคาดหมาย ไม่ใช่ผล) → ดู "ต้องให้ผู้ใช้ตัดสินใจ"

### ④-1 Hybrid: external + residual PC
| หัวข้อ | เนื้อหา |
|---|---|
| ไอเดีย + กลไก | factor ภายนอกให้การตีความ PC ของ residual จับสิ่งที่ดัชนีไม่มี (ไทย, hedge, กลยุทธ์ร่วม) → ได้ทั้งความตีความได้ (ข้อ 6) และ R² |
| หลักฐาน | Connor & Korajczyk 1991 (RQFA, กองทุนสหรัฐฯ): ใช้ hybrid ระหว่าง factor สถิติกับ factor ที่กำหนดล่วงหน้าเพื่อแก้ rotational indeterminacy — **อ่านเฉพาะบทคัดย่อ** · ความแรง: **ปานกลาง** |
| เข้ากับข้อมูล | สูง |
| ชั้น | L1 (สาย ④) → ป้อน L2 โดยตรง (residual PC ตรงกับดัชนีอะไร) |
| วิธีสร้าง | regress กองบน ③-1 (ช่วง train) → PCA ของ residual บน balanced sub-panel → k_res จาก Bai–Ng IC_p2 บน residual (kmax 5) · OOS: น้ำหนัก PC จาก train |
| ร่างสมมติฐาน | H④a: k_res ≥ 1 ที่มีนัยสำคัญ และ residual PC1 มี corr สูงกับ APB กองหุ้นไทย หรือ ΔUSDTHB-hedge → ถ้าใช่ แปลว่า ③-1 ขาด factor ไทย/hedge |

### ④-2 Thai-domestic factor
- กลไก: กองหุ้นไทย (E ส่วนใหญ่ 600 กอง) ไม่ได้ถูกอธิบายด้วย MSCI Thailand(THB) ครบ (mid/small cap, LTF/SSF/RMF) · FF 2012 สนับสนุน local factor
- ทางเลือก: (ก) APB ของกองหุ้นไทย (ไม่ต้องดาวน์โหลด) (ข) SET จาก `Fama French SET50/` (รอผู้ใช้ตาม BRIEF) · MSCI Thailand อยู่ใน MSCI 28 หรือไม่ ให้ data-engineer ยืนยัน
- H④b: เพิ่ม Thai factor บน ③-1 เพิ่ม median R² ของกอง E ไทย (ไม่ใช่ FIF) อย่างชัดเจน ส่วนกอง FIF แทบไม่เปลี่ยน

### ④-3 Hedge-cost factor (รอผู้ใช้)
- กลไก: ตาม covered interest parity ผลตอบแทนการ hedge ≈ ส่วนต่างดอกเบี้ยระยะสั้นสองสกุล → กองที่ hedge 100% ได้/เสียตามส่วนต่างนี้ · หลักฐานกับกองไทยโดยตรง: **ไม่พบ** · ต้องมีดอกเบี้ยสั้นสหรัฐฯ (ไม่มีในระบบ — US10Y ไม่ใช่ตัวแทนที่ดี) → ความแรง: **อ่อน**

### ④-4 Factor momentum → ระยะ 2
- Ehsani & Linnainmaa 2022 (JF 77(3)): momentum ของหุ้นมาจาก autocorrelation ของ factor · factor ที่มี eigenvalue สูงมี momentum มากกว่า → ทดสอบกับ PC ของกองได้ แต่เป็นการทำนาย = **นับ trial** ระยะ 2

---

## วิธีทดสอบ / เปรียบเทียบ model

| เครื่องมือ | ใช้ทำอะไรในงานเรา | หลักฐาน / ข้อควรระวัง |
|---|---|---|
| **GRS** (Gibbons–Ross–Shanken 1989, Econometrica 57(5)) | α ร่วม = 0 บนพอร์ตกลุ่มกอง (ตามตารางคะแนนข้อ 3) | ต้อง N_พอร์ต ≪ T และ residual ใกล้ปกติ · T_train ≈ 156 → แนะนำ 20–30 พอร์ต (เช่น policy × primary country) · ล็อกการจัดพอร์ตก่อนรัน |
| **Pesaran–Yamagata** (JFEc 2024) | **เสนอเพิ่ม:** ทดสอบ α = 0 ของ *ทุกกอง* โดยตรงเมื่อ N > T | สร้างจาก t รายกอง ไม่ต้อง invert covariance · ทน non-Gaussian และ cross-correlation อ่อน · simulation ดีแม้ T = 60, N = 5,000 · ข้อระวัง: กองไทย cross-correlation ของ residual อาจไม่ "อ่อน" (กองซ้ำ, APB) → ใช้ร่วมกับ GRS ไม่ใช่แทน |
| **Spanning regression** (Huberman–Kandel 1987 — **ยังไม่ยืนยันแหล่ง**) | L1: factor ของ model A ~ factor ของ model B → α = 0 และ R² สูง = B span A · L2: PC ~ MSCI 28 + style + macro | ใช้ได้เฉพาะ factor ที่ลงทุนได้ (PC ของกอง, long–short ของกอง, ดัชนีบาท) · Δ VIX / Δ US10Y ต้องตัดออกหรือทำ mimicking |
| **Barillas–Shanken 2017** (RFS 30(4) "Which Alpha?") | เทียบ model ข้ามสาย: model ที่ดีกว่าคือที่ price factor ของอีก model ได้ — test asset ไม่เกี่ยว (สำหรับ factor ลงทุนได้) | ผลทดสอบซ้ำระดับวิทยานิพนธ์ป.ตรี (Erasmus 2018) ส่วนใหญ่ตรง ยกเว้นเกณฑ์ likelihood — หลักฐานทดสอบซ้ำอ่อน · ในงานเรา: เทียบ Sharpe สูงสุดของ factor ชุดรวม ใช้เป็น **ตัวเสริม** ตารางคะแนนกลาง (ไม่ใช่เกณฑ์ใหม่ เพราะตารางล็อกแล้ว) |
| **Lewellen–Nagel–Shanken 2010** (JFE 96(2)) | เตือนว่า R² สูง / pricing error เล็กบน test asset ที่มี factor structure แรง เป็นหลักฐานอ่อน | รายงาน confidence interval ของสถิติ · test asset ไม่ควรเป็นแค่พอร์ตที่เรียงตามคุณลักษณะเดียวกับ factor (ตรงกับปัญหา circularity ของสาย ②) |
| **Dimson 1979** (JFE 7) | beta = ผลรวม coefficient lag 0 + lag 1 (BRIEF) | กลไกเดิมคือหุ้นซื้อขายบาง · กับกองต่างประเทศ เหตุคือ time zone / ราคาปิดเก่า (Goetzmann–Ivković–Rouwenhorst 2001 JFQA: 391 กองต่างประเทศสหรัฐฯ) · มีงานแย้งว่าบางส่วนเป็น momentum ของตลาด ไม่ใช่ราคาเก่า (Wharton WP "Stale or sticky") · **ข้อเสนอ:** ใส่ lead 1 เป็น diagnostic ครั้งเดียวใน L0/L1 — ถ้า coefficient lead ≠ 0 แปลว่าการจัดสัปดาห์ระหว่าง NAV กับดัชนีคลาดกัน (ไม่ใช้ lead ใน model หลัก) |
| **Harvey–Liu–Zhu 2016** (RFS 29(1)) | factor ใหม่ (สาย ④) ต้อง t > 3.0 | งานแย้ง: arXiv 2206.15365 "Most claimed statistical findings ... are likely true" (อ่านเฉพาะชื่อ/บทคัดย่อ) · ระยะ 1 ไม่นับ trial แต่ยังมีการลองหลาย factor → ใช้ t > 3 เป็นเกณฑ์บรรยาย |
| **Benjamini–Hochberg / FDR กองทุน** (Barras–Scaillet–Wermers 2010, JF 65(1)) | L4: α รายกอง FDR 10% | BSW: กองหุ้นสหรัฐฯ 1975–2006 ~75% α = 0 สุทธิค่าใช้จ่าย · ทน dependence ระหว่างกองได้บางส่วน · กองซ้ำ (corr > 0.99) ต้องตัดก่อน (BRIEF ข้อ 4) |
| การนับ factor หลายเกณฑ์ | ดู ①-1 | เกณฑ์ขัดกันบ่อย → ล็อกกฎรวม (เช่น มัธยฐานของ 4 เกณฑ์) ก่อนเห็นผล |

---

## ไอเดียที่ไม่ควรลอง (ตอนนี้)
| ไอเดีย | เหตุผล |
|---|---|
| Holdings-based (DGTW characteristic benchmark, active share) | ไม่มี holdings |
| Currency carry / HML_FX (Lustig et al.) | ต้องใช้ forward หลายสกุล — ไม่มีในระบบ · กองไทยไม่ได้ทำ carry |
| Fung–Hsieh trend-following (lookback straddle) | ไม่มีข้อมูล · กองไทยเป็น long-only ไม่ใช่ hedge fund |
| FF factor ระดับหุ้นไทย (SMB/HML/RMW จากหุ้น SET) | ต้องมีข้อมูลรายหุ้น + งบการเงิน — อยู่นอกขอบเขต (อาจมีในโปรเจกต์ `Fama French SET50/` — ผู้ใช้ตัดสินใจ) |
| FF factor สหรัฐฯ/ภูมิภาคจาก Ken French library | ต้องดาวน์โหลด · factor ระดับหุ้นในสกุล USD เวลาปิด NY · CPZ 2013 ชี้ว่า index-based ดีกว่าสำหรับประเมินกอง |
| Flow / AUM momentum | ไม่มี flow · AUM มีรู (สอดคล้อง quant_team R001) |
| IPCA เต็มรูป (L1 รอบแรก) | คุณลักษณะเป็น snapshot · ซับซ้อนสูงเทียบ T |
| ค่าธรรมเนียมเป็น factor หลัก | กลไกกระทบค่าเฉลี่ย ไม่ใช่ covariance → ใช้ที่ L4 (α) |

---

## คำแนะนำถึง factor-designer (การแข่ง L1)
รวม **10–11 model** · ทุก model ใช้ excess return บาท − rf ธปท. · lag 0 + lag 1 · HAC · split train 2021–2023 / test 2024–2025 เดียวกัน · พารามิเตอร์ล็อกจากวรรณกรรม (ไม่ tune)

| สาย | variant | เนื้อหา |
|---|---|---|
| ① (3) | ①a | correlation-PCA บน balanced sub-panel · k = มัธยฐานของ {IC_p2, ER, ED, PA} (kmax 10) |
| | ①b | covariance-PCA (k เท่า ①a) — sensitivity เรื่อง E/F/O ต่างความผันผวน |
| | ①c | missing-data PCA บน unbalanced panel (k เท่า ①a) |
| | + | รายงานเส้น R² เทียบ k = 1…8 เพื่อบรรยาย (ไม่ใช้เลือก) |
| ② (3) | ②a | ตลาดกอง (EW ทั้งหมด) + APB ตาม policy E/F/O (leave-one-out) |
| | ②b | ②a + FX-hedge + fund momentum (52-4 สัปดาห์) |
| | ②c | ②b + size + active (1 − R²) — ตัวเสี่ยง overfit |
| ③ (3) | ③a | ACWI(THB) · AGG(THB) · ทอง(THB) · ΔUSDTHB |
| | ③b | ③a + EM − DM · US − ACWI (+ SET หรือ APB หุ้นไทย) |
| | ③c | ③b + style 4 (de-market) + Δ US10Y · Δ VIX · oil |
| ④ (1–2) | ④a | ③a + residual PC (k_res จาก IC_p2, kmax 5) |
| | ④b | (ถ้าผู้ใช้อนุมัติข้อมูล) hedge-cost factor |

เพิ่มในการวิเคราะห์ (ไม่แตะตารางคะแนนที่ล็อก): spanning ระหว่างตัวที่ดีที่สุดของแต่ละสาย (Barillas–Shanken) · Pesaran–Yamagata คู่กับ GRS · diagnostic lead 1 ครั้งเดียว · กำหนดกลุ่มสำหรับ APB/GRS จากข้อมูลที่ไม่ fit ทั้งช่วง

---

## ต้องให้ผู้ใช้ตัดสินใจ
1. **SET จาก `Fama French SET50/`** (มีใน BRIEF แล้ว) — กระทบ ③b / ④-2 · ทางเลือกที่ไม่ต้องใช้ = APB หุ้นไทย
2. **ดาวน์โหลดข้อมูลเพิ่มหรือไม่** (ยังไม่ได้ตรวจขนาด/ชื่อไฟล์ — ให้ data-engineer เสนอ): ดอกเบี้ยสั้นสหรัฐฯ (สำหรับ hedge-cost) · credit spread / ดัชนีบอนด์ไทย (สำหรับกอง F) — ถ้าไม่ดาวน์โหลด กอง F จะถูกอธิบายแย่เป็นข้อจำกัดที่รู้ล่วงหน้า
3. PCA หลักใช้ correlation (standardize) หรือ covariance — แนะนำ correlation เป็นหลัก
4. ยอมรับ circularity ของสาย ② แบบ leave-one-out หรือไม่ (แนะนำให้ใช้)

## บรรณานุกรม
ป้าย: **[ยืนยัน-abs]** = เปิดหน้าบทคัดย่อ/หน้าวารสาร/ผลค้นที่ยกเนื้อหา · **[ยังไม่ยืนยันแหล่ง]** = จากความจำ
- Bai, J. & Ng, S. (2002) Determining the Number of Factors in Approximate Factor Models. Econometrica 70(1). https://www.math.nyu.edu/faculty/avellane/BaiNG2002.pdf [ยืนยัน-abs]
- Alessi, Barigozzi & Capasso (2008) ECB WP 903. https://ECB.eu/pub/pdf/scpwps/ecbwp903.pdf [ยืนยัน-abs]
- Ahn, S. & Horenstein, A. (2013) Eigenvalue Ratio Test for the Number of Factors. Econometrica 81(3). https://www.econometricsociety.org/publications/econometrica/2013/05/01/eigenvalue-ratio-test-number-factors [ยืนยัน-abs]
- Onatski, A. (2010) Determining the Number of Factors from Empirical Distribution of Eigenvalues. REStat 92(4) — กลไกละเอียด [ยังไม่ยืนยันแหล่ง]
- Connor, G. & Korajczyk, R. (1986, 1988, 1991, 1993) — Kellogg pages https://www.kellogg.northwestern.edu/academics-research/research/detail/1991/the-attributes-behavior-and-performance-of-us-mutual-funds/ [ยืนยัน-abs]
- Jones, C. (2001) Extracting factors from heteroskedastic asset returns. JFE [ยืนยัน-abs ผ่านผลค้น]
- Xiong, R. & Pelger, M. Large Dimensional Latent Factor Modeling with Missing Observations. https://arxiv.org/abs/1910.08273v5 [ยืนยัน-abs]
- Kelly, B., Pruitt, S. & Su, Y. (2019) Characteristics Are Covariances. JFE 134(3). https://www.nber.org/papers/w24540 [ยืนยัน-abs] · Fieberg et al. (2020) comment — ชื่อเท่านั้น
- Horn (1965) parallel analysis — https://arxiv.org/pdf/1711.04155 (deterministic PA) [ยืนยัน-abs]
- Sharpe, W. (1992) Asset Allocation: Management Style and Performance Measurement. JPM. https://web.stanford.edu/~wfsharpe/art/sa/sa.htm [ยืนยัน-abs]
- Elton, Gruber & Blake (1993) The Performance of Bond Mutual Funds. J. Business 66(3). https://ideas.repec.org/a/ucp/jnlbus/v66y1993i3p370-403.html [ยืนยัน-abs] · (1995) JF https://archive.nyu.edu/handle/2451/27236 [ยืนยัน-abs]
- Fung, W. & Hsieh, D. (2004) Hedge Fund Benchmarks: A Risk-Based Approach. FAJ 60(5). https://ideas.repec.org/a/taf/ufajxx/v60y2004i5p65-80.html [ยืนยัน-abs] — 3 trend factor [ยังไม่ยืนยันแหล่ง]
- Cremers, Petajisto & Zitzewitz (2013) Should Benchmark Indices Have Alpha? CFR. https://www.nber.org/papers/w18050 [ยืนยัน-abs]
- Hunter, Kandel, Kandel & Wermers (2014) Mutual Fund Performance Evaluation with Active Peer Benchmarks. JFE 112(1). https://ideas.repec.org/a/eee/jfinec/v112y2014i1p1-29.html [ยืนยัน-abs] · Mateus et al. (2019) UK https://openaccess.city.ac.uk/id/eprint/21634 [ยืนยัน-abs]
- Carhart (1997) On Persistence in Mutual Fund Performance. JF. https://www.afajof.org/page/Top50Cited [ยืนยัน-abs ผ่านผลค้น]
- Amihud & Goyenko (2013) Mutual Fund's R² as Predictor of Performance. RFS. https://archive.nyu.edu/handle/2451/28039 [ยืนยัน-abs] · critique https://repositori.uji.es:443/xmlui/handle/10234/204167 [ยืนยัน-abs]
- Fama & French (2012) Size, Value, and Momentum in International Stock Returns. JFE. https://www.johnhcochrane.com/s/Fama_French_size_value_momentum_JFE.pdf [ยืนยัน-abs]
- Asness, Moskowitz & Pedersen (2013) Value and Momentum Everywhere. JF 68(3). https://pages.stern.nyu.edu/~lpederse/papers/ValMomEverywhere.pdf [ยืนยัน-abs]
- Lustig, Roussanov & Verdelhan (2011) Common Risk Factors in Currency Markets. RFS 24(11). https://www.nber.org/papers/w14082.pdf [ยืนยัน-abs] — นิยาม dollar factor [ยังไม่ยืนยันแหล่ง]
- Opie & Riddiough (2025, WP) currency management ของกองหุ้นต่างประเทศสหรัฐฯ — ผ่านผลค้น https://www.aeaweb.org/conference/2026/program/paper/ab4B3esy [ยืนยัน-abs บางส่วน] · Benson & Faff (2004) PBFJ https://research.bond.edu.au/en/publications/the-relationship-between-exchange-rate-exposure-currency-risk-man/ [ยืนยัน-abs]
- Gibbons, Ross & Shanken (1989) A Test of the Efficiency of a Given Portfolio. Econometrica 57(5). https://ideas.repec.org/a/ecm/emetrp/v57y1989i5p1121-52.html [ยืนยัน-abs]
- Pesaran & Yamagata (2024) Testing for Alpha in Linear Factor Pricing Models with a Large Number of Securities. JFEc. https://eprints.whiterose.ac.uk/195190 [ยืนยัน-abs]
- Barillas & Shanken (2017) Which Alpha? RFS 30(4). https://www.nber.org/papers/w21698 [ยืนยัน-abs] · replication https://thesis.eur.nl/pub/43255/Li-Y..pdf [ยืนยัน-abs]
- Huberman & Kandel (1987) mean-variance spanning. JF [ยังไม่ยืนยันแหล่ง]
- Lewellen, Nagel & Shanken (2010) A Skeptical Appraisal of Asset Pricing Tests. JFE 96(2). https://www.nber.org/papers/w12360 [ยืนยัน-abs]
- Dimson (1979) Risk Measurement when Shares are Subject to Infrequent Trading. JFE 7 — ผ่านผลค้นที่อ้างถึง [ยืนยัน-abs บางส่วน] · Scholes–Williams (1977) [ยังไม่ยืนยันแหล่ง]
- Goetzmann, Ivković & Rouwenhorst (2001) Day Trading International Mutual Funds. JFQA. https://depot.som.yale.edu/icf/papers/fileuploads/2447/original/00-03.pdf [ยืนยัน-abs] · Stale or Sticky Stock Prices (Wharton WP) https://faculty.wharton.upenn.edu/wp-content/uploads/2014/03/Stale-or-Sticky-Stock-Prices_6Oct2006.pdf [ยืนยัน-abs]
- Harvey, Liu & Zhu (2016) …and the Cross-Section of Expected Returns. RFS 29(1). https://www.nber.org/papers/w20592 [ยืนยัน-abs] · rebuttal https://arxiv.org/pdf/2206.15365 [ชื่อ/บทคัดย่อ]
- Barras, Scaillet & Wermers (2010) False Discoveries in Mutual Fund Performance. JF 65(1). https://terpconnect.umd.edu/~wermers/FDR_published.pdf [ยืนยัน-abs]
- Ehsani & Linnainmaa (2022) Factor Momentum and the Momentum Factor. JF 77(3). https://www.nber.org/papers/w25551 [ยืนยัน-abs]
- บริบทไทย: Nottingham dissertation (2018) กองหุ้นไทย https://eprints.nottingham.ac.uk/53935 [ยืนยัน-abs] · จุฬาฯ APB (2021) https://digital.car.chula.ac.th/chulaetd/7698 [ยืนยัน-abs] · จุฬาฯ ผู้จัดการกอง (FF3/FF5) https://digital.car.chula.ac.th/chulaetd/11182 [ยืนยัน-abs] · ก.ล.ต. working paper https://www.sec.or.th/TH/Documents/SECWorkingPapersForum/working-paper-forum-25611128-fund2.pdf — **เปิดไม่ได้ (HTTP 403)**

## สิ่งที่ยังค้าง
- ยังไม่ได้อ่านฉบับเต็ม: Onatski 2010, Connor–Korajczyk 1991, Hunter et al. 2014 (ตารางผล), Opie–Riddiough, เอกสาร ก.ล.ต. (403)
- ยังไม่ได้ค้นเฉพาะ: งานกองทุนไทย FIF + การ hedge (ภาษาไทย / AIMC), Huberman–Kandel ต้นฉบับ, Kan–Robotti–Shanken (เทียบ model แบบ non-nested)
- ยังไม่ได้ยืนยันว่า MSCI 28 มี EM / World / Thailand ครบหรือไม่ (ให้ data-engineer ตรวจที่ L0)
