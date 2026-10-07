# R001 — สัญญาณคัดกองทุน (fund selection signals)

ผู้เขียน: quant-researcher · วันที่ 2026-10-03 · ฐานที่เทียบ: **M004-TF-FX** (SR12 ของ NAV กอง · ERC · trend cash 25%)
อ่านก่อนเขียน: `BRIEF.md`, `backtest/results/ALL_RESULTS.md`, `M006-M007_results.md`, `docs/pages/9-tf-portfolio.md`
(ยังไม่ได้อ่านหัวข้อสมมติฐานใน `specs/` ทีละไฟล์ เพราะ session นี้ไม่มีเครื่องมือ list ไฟล์ — ดู "สิ่งที่ยังไม่ได้ทำ")

## บทสรุป 5 บรรทัด
1. หลักฐานกระแสหลัก: **persistence จาก return ดิบระยะยาวหายไปแล้ว** (Choi & Zhao: ไม่มีนัยสำคัญช่วง 1994–2018) ส่วนที่เหลืออยู่คือ persistence ระยะสั้น (ไตรมาสถัดไป) ของ abnormal return
2. ตัวทำนายผลกองที่ตีพิมพ์ **อ่อนลงอย่างน้อยครึ่งหนึ่งหลังตีพิมพ์** (Jones & Mo 2021) → ทุกตัวเลขในตารางให้หาร 2 ก่อนคิด
3. กองหุ้นต่างประเทศ/global: ส่วนใหญ่ของ "persistence" มาจาก **country/sector momentum** (Breloer et al. 2014) — แปลว่า SR12 ของเราน่าจะจับ momentum ของดัชนีประเทศ/sector มากกว่า skill ผู้จัดการ
4. ตัวกรองที่หลักฐานแข็งที่สุดและข้อมูลเรามี: **ต้นทุน/ค่าธรรมเนียม** (Morningstar: กองถูกสุดสำเร็จ 2–3 เท่าของกองแพงสุด รวม international equity) + ต้นทุนสลับกองเป็นตัวถ่วงหลักของเราอยู่แล้ว
5. คาดหวังเชิงสมจริง: สัญญาณคัดกองเพิ่ม Sharpe ได้น้อย (ระดับ +0.0x ไม่ใช่ +0.2) — **เป้า 0.95 ไม่น่าถึงได้จากการเปลี่ยนสัญญาณคัดกองอย่างเดียว** จุดอ่อนจริงคือปี 2022 (ตลาดขาลง) ซึ่งงานกลุ่มนี้ไม่ได้แก้

## ตารางอันดับไอเดีย
คะแนน = (หลักฐาน 1–3 × เข้ากับข้อมูล 1–3) ÷ trial

| # | ไอเดีย | ต่อยอด/แทนที่ส่วนไหนของ M004-TF-FX | หลักฐาน | เข้ากับข้อมูล | trial | คะแนน |
|---|---|---|---|---|---|---|
| 1 | **SR12 สุทธิต้นทุน** (หักต้นทุนเข้า-ออกจริงต่อกองก่อนจัดอันดับ) | ต่อยอดขั้น "เลือก" (สัญญาณ SR12 + hysteresis) | ปานกลาง–แข็ง (2) | สูง (3) — `SecFundFee.csv` มีแล้ว ใช้ในแอปแล้ว | 1 | 6.0 |
| 2 | **ตัวกรอง alpha เทียบดัชนีของกองเอง** (index-based alpha 12-1 > 0) | ต่อยอดขั้น "คัดได้ I_t" (ตัวกรองก่อนจัดอันดับ SR12) | ปานกลาง (2) | กลาง–สูง (2) — ต้องจับคู่กองกับดัชนี MSCI แบบ point-in-time | 1 | 4.0 |
| 3 | **R² ต่ำ × alpha บวก** (Amihud–Goyenko) | แทนที่/เสริมสัญญาณ SR12 ด้วยตัวคูณ selectivity | ปานกลาง แต่มี decay (2) | กลาง (2) — ต้อง rolling regression ณ วัน t (exposure ปัจจุบันใช้ทั้งช่วง = look-ahead) | 2 | 2.0 |
| 4 | flow/AUM momentum | เสริมสัญญาณ | ปานกลาง (US, รายเดือน) | ต่ำ (1) — AUM มีรู · flow ต้องอนุมาน | 2+ | 1.0 → ไม่แนะนำตอนนี้ |

---

## รายละเอียดต่อไอเดีย

### ไอเดีย 1 — SR12 สุทธิต้นทุน (cost-aware ranking)
| หัวข้อ | เนื้อหา |
|---|---|
| ไอเดีย + กลไก | ค่าธรรมเนียมเป็นสิ่งเดียวที่รู้ล่วงหน้าแน่นอนและไม่มี noise ส่วน alpha ในอดีตส่วนใหญ่เป็นโชค (Fama & French 2010: แทบไม่มีกองที่ชนะ benchmark หลังหักต้นทุน) → การเปลี่ยนกองจาก A ไป B คุ้มเฉพาะเมื่อส่วนต่างสัญญาณที่คาดว่าจะคงอยู่ > ต้นทุนเข้า-ออก ในกรณีเรา front-end เปลี่ยน Sharpe จาก 0.89 → 0.71 (หน้า 9) = ต้นทุนกิน Sharpe มากกว่าที่สัญญาณใหม่ใดๆ ในวรรณกรรมน่าจะเพิ่มให้ |
| หลักฐาน | Kinnel (Morningstar 2016): success ratio กองถูกสุด vs แพงสุด — international equity 51% vs 21%, US equity 62% vs 20% (กอง US, ไม่ระบุช่วงปีใน press release) · ผลเดียวกันทุกหมวด → **แข็ง** สำหรับ "ค่าธรรมเนียมทำนายผลได้" · Fama & French 2010 (กองหุ้น US): ต้นทุนการบริหารแสดงออกเต็มๆ ใน return ที่ต่ำลง · ข้อสังเกต: Ferreira et al. (working paper, 19 ประเทศ 1999–2005) พบตรงข้ามว่ากองค่าธรรมเนียมสูงผลดีกว่า → หลักฐานนอกสหรัฐฯ ไม่เป็นเอกฉันท์ → รวมเป็น **ปานกลาง–แข็ง** |
| เข้ากับข้อมูลเรา | ใช้ `SecFundFee.csv` (front/back-end/สับเปลี่ยน) ที่ `analysis/fund_fees.py` ใช้คิดต้นทุนอยู่แล้ว · NAV หัก TER แล้ว จึงไม่ต้องหัก TER ซ้ำใน SR12 · **ยังไม่รู้ว่ามี TER/ค่าจัดการแยกในไฟล์หรือไม่** (ถ้ามี ใช้เป็นตัว tie-break ได้) |
| ผลที่คาด | งานวิจัยไม่ได้ให้ตัวเลข Sharpe ของแบบนี้โดยตรง · ทิศทาง: turnover ↓, ต้นทุน bp/ปี ↓ (ตอนนี้ ~171 bp/ปี ที่ 0.5%/ข้าง ตาม M006-M007_results — ไม่ได้ตรวจซ้ำเอง) · drawdown ไม่ควรเปลี่ยน |
| ต้นทุนเชิงสถิติ | 1 trial · พารามิเตอร์เสี่ยง = ระยะถือที่ใช้ amortize ต้นทุน → **ไม่ tune** ใช้ระยะถือเฉลี่ยจริงของ M004-TF-FX ที่วัดได้จาก turnover (≈ 1/turnover ต่อปี) หรือ 1 ปีตาม lookback 12 เดือน |
| ร่างสมมติฐาน | "การจัดอันดับด้วย SR12 − (ต้นทุนเข้า + ต้นทุนออกจริงของกอง ÷ ระยะถือที่คาด) ÷ vol52 สำหรับกองที่ยังไม่ถือ (กองที่ถืออยู่ต้นทุนเข้า = 0) จะลด turnover และต้นทุนต่อปีโดยไม่ลด Sharpe ก่อนต้นทุน" · เทียบ M004-TF-FX ด้วย paired Δ Sharpe ที่ค่าธรรมเนียมจริง (ไม่ใช่ 0.5% คงที่) |

### ไอเดีย 2 — ตัวกรอง alpha เทียบดัชนีของกองเอง
| หัวข้อ | เนื้อหา |
|---|---|
| ไอเดีย + กลไก | แยก SR12 เป็น (a) momentum ของดัชนีที่กองลงทุน (country/sector) กับ (b) ส่วนเกินของกองเหนือดัชนีนั้น · (a) คือแหล่ง return หลักที่เราได้อยู่ (country/sector momentum) ส่วน (b) ถ้าติดลบต่อเนื่อง = กองแพง/hedge ผิดทาง/tracking แย่ → ควรเลือก class/กองอื่นที่จับธีมเดียวกันได้ถูกกว่า · ใช้ benchmark เป็น **ดัชนีที่ซื้อขายได้** แทน factor ทางวิชาการ เพราะ Cremers et al. พบว่า factor แบบ Fama-French ให้ alpha ปลอมแม้แต่กับดัชนี passive |
| หลักฐาน | Bollen & Busse 2005 (กองหุ้น US, return รายวัน, จัดอันดับรายไตรมาส): top decile abnormal return ไตรมาสถัดไป 39 bp และหายไปเมื่อวัดช่วงยาว · Hammouda et al. 2023 (2,734 กอง 5 ประเทศยุโรป 1990–2022): persistence ไตรมาสถัดไปมีนัยสำคัญทุก decile = ทดสอบซ้ำนอกสหรัฐฯ ผ่าน · Kaniel et al. 2023 (3,275 กอง US 1980–2019): fund momentum = abnormal return 12 เดือนข้ามเดือนล่าสุด เป็นตัวทำนายสำคัญที่สุดคู่กับ flow · Breloer et al. 2014 (กอง international/global): > 50% ของกองมี exposure ต่อ country/sector momentum และการใส่ factor นี้เปลี่ยนข้อสรุปเรื่อง persistence · ข้อโต้แย้ง: Jones & Mo 2021 ความสามารถทำนายลดลง ≥ ครึ่งหลังตีพิมพ์ · Choi & Zhao 2021 persistence ของ Carhart หายไปหลังปี 1994 ส่วนหนึ่งเพราะ "กองชนะแพ้หลังปรับ style" → **ปานกลาง** |
| เข้ากับข้อมูลเรา | ต้องจับคู่กองกับดัชนี MSCI 1 ตัว (18 country + 10 sector + ACWI) แบบ point-in-time — **ห้ามใช้ exposure ElasticNet ใน `cache/coefs.csv`** (fit ทั้งช่วง) · ทางที่ไม่มี look-ahead: ใช้ดัชนีที่ R² สูงสุดในหน้าต่าง 52 สัปดาห์ก่อน t หรือใช้ benchmark ตามหนังสือชี้ชวน (ถ้ามีใน FundProfile) · 45 เดือน × ~200 กองพอสำหรับตัวกรองแบบ binary (ไม่ประมาณพารามิเตอร์ต่อเนื่อง) · ปัญหา NAV เอเชียช้ากว่าดัชนี (จุดอ่อน #5) → ใช้ return รายสัปดาห์หรือรายเดือน ไม่ใช่รายวัน |
| ผลที่คาด | วรรณกรรมให้ผลที่ระดับ 39 bp/ไตรมาส (US) ก่อน decay → หลัง decay ~≤ 20 bp/ไตรมาส · ในพอร์ต long-only 8 กองที่ถูกกรองก่อนอยู่แล้วด้วย SR12 ผลส่วนเพิ่มน่าจะเล็กกว่านี้อีก · ไม่ควรคาดว่าแก้ปี 2022 |
| ต้นทุนเชิงสถิติ | 1 trial ถ้าใช้ค่ามาตรฐาน: หน้าต่าง 12-1 เดือน (ตรงกับ SR12 และ Kaniel et al.) · เกณฑ์ alpha > 0 (ไม่ tune เป็น percentile) · เสี่ยง overfit ที่วิธีเลือกดัชนีคู่ → ล็อกวิธีก่อนรัน |
| ร่างสมมติฐาน | "ตัดกองที่ return 12-1 ต่ำกว่าดัชนี MSCI คู่ของตัวเอง (เลือกดัชนีคู่จาก R² 52 สัปดาห์ก่อน t) ออกจาก I_t ก่อนจัดอันดับ SR12 จะไม่ลด Sharpe และลดการถือกองที่ lag ดัชนี" · วัด: paired Δ Sharpe, จำนวนกองที่ถูกตัดต่อไตรมาส, ผลของกองที่ถูกตัด (ต้องแย่กว่าจริง) |

### ไอเดีย 3 — R² ต่ำ × alpha บวก (selectivity)
| หัวข้อ | เนื้อหา |
|---|---|
| ไอเดีย + กลไก | R² ต่ำต่อ benchmark = ผู้จัดการเบี่ยงจากดัชนีมาก (active) · ถ้ามีฝีมือ ส่วนเบี่ยงนั้นคือที่มาของ alpha · คู่กับ alpha อดีตบวกเพื่อแยก "active และเก่ง" ออกจาก "active แต่โชคร้าย" |
| หลักฐาน | Amihud & Goyenko 2013 (กองหุ้น US): quintile R² ต่ำสุด × alpha สูงสุด ให้ alpha 3.8%/ปี · Huij & Derwall 2011 (กอง global equity, JBF): กองกระจุก/tracking error สูงผลดีกว่า — สนับสนุนทิศทางเดียวกันในกอง global · ข้อโต้แย้ง: Jones & Mo 2021 รวม R² อยู่ในกลุ่มตัวทำนายที่ decay (ไม่ได้เปิดอ่านตัวเลขรายตัวเอง — ดูบรรณานุกรม) → **ปานกลาง** |
| เข้ากับข้อมูลเรา | **ขัดกับหน้า 8 ปัจจุบัน** ที่คูณคะแนนด้วย R² (ให้รางวัลกอง R² สูง = exposure บริสุทธิ์) · กอง FIF ไทยส่วนใหญ่เป็น feeder ที่ถือกองแม่กองเดียว → R² สะท้อนความ active ของกองแม่ ใช้ได้ในหลักการ · ต้อง rolling regression ณ วัน t ใหม่ทั้งหมด (exposure ปัจจุบันมี look-ahead) · กองที่ R² ต่ำอาจเป็นเพราะ NAV มีรู/ช้า (ข้อมูลแย่) ไม่ใช่ active → ต้องกันด้วยเกณฑ์จำนวนสัปดาห์ร่วมขั้นต่ำ (มีแล้วใน ERC = 30) |
| ผลที่คาด | 3.8%/ปี (US, ก่อน decay, long–short-ish quintile) → คาดจริง ≤ ครึ่ง และในพอร์ต long-only 8 กองน้อยกว่านั้น · อาจเพิ่ม tracking error และความผันผวนเฉพาะกอง |
| ต้นทุนเชิงสถิติ | 2 trial (ทางเลือกนิยาม benchmark: ดัชนีคู่เดียว vs ชุดดัชนีหลายตัว) · พารามิเตอร์เสี่ยง: หน้าต่าง regression, ชุด factor, วิธีรวม R² กับ alpha · ใช้หน้าต่าง 52 สัปดาห์เดียวกับ vol52 เพื่อไม่เพิ่มพารามิเตอร์ |
| ร่างสมมติฐาน | "ในกองที่ผ่าน SR12 อันดับ ≤ 16 ให้จัดอันดับซ้ำด้วย (1 − R²) เฉพาะกองที่ alpha 52 สัปดาห์ > 0 แล้วเลือก 8 อันดับแรก จะให้ Sharpe สูงกว่า M004-TF-FX" · ต้องทำหลังไอเดีย 2 (ใช้ขั้นตอนจับคู่ดัชนีเดียวกัน) |

---

## ไอเดียที่ไม่ควรลอง (และเหตุผล)
| ไอเดีย | เหตุผล |
|---|---|
| จัดอันดับด้วย alpha/return ช่วงสั้น (1–3 เดือน) เพื่อจับ short-term persistence | ผลในวรรณกรรมระดับ ~39 bp/ไตรมาส (Bollen & Busse, US ก่อน decay) แต่ต้องหมุนกองทุกไตรมาส · ต้นทุนเรา ~0.54%/ข้าง ≈ 1% ต่อรอบเข้า-ออก → ผลถูกต้นทุนกินหมด · M007 (ลด turnover ด้วย tranche) ก็ไม่ช่วย → อย่าเพิ่ม turnover |
| persistence จาก return ดิบระยะยาว (3–5 ปี) / Carhart-style ranking | Choi & Zhao 2021: หายไปหลังปี 1994 · ข้อมูลเรามี 45 เดือน หน้าต่าง 3 ปีจะเหลือจุดประเมินน้อยมาก |
| active share, return gap, industry concentration, holdings-based skill | ต้องใช้ holdings รายไตรมาสย้อนหลัง (เราไม่มี มีแค่ top holdings ปัจจุบัน) → look-ahead แน่นอน |
| fund flow / AUM momentum | หลักฐาน (Kaniel et al.) เป็นกอง US รายเดือน + ขึ้นกับ sentiment + neural net · AUM ของเรามีรู ต้องอนุมาน flow จาก ΔAUM − return · กลไก Berk–Green (flow ไหลเข้ากองเก่ง → ขนาดใหญ่ขึ้น → alpha ลด) ทำให้ทิศทางไม่ชัด (ยังไม่ยืนยันแหล่ง Berk & Green 2004 — ไม่ได้เปิดอ่าน) · พักไว้จนกว่า data-qa ยืนยันคุณภาพ AUM |
| ML / neural net คัดกอง (Kaniel et al., DeMiguel et al.) | ต้องใช้ตัวอย่างใหญ่ (หลายพันกอง หลายสิบปี) · เรามี 45 เดือน และ trial เดียวของ ML มี degrees of freedom ซ่อนสูงมาก → DSR จะยิ่งแย่ |
| Quality/LowVol tilt ของกอง | ทำแล้วใน M008-SQ (paired Δ −0.437 ไม่ผ่าน) |

## งานกองทุนไทย / ตลาดเกิดใหม่
- พบวิทยานิพนธ์ PhD (Univ. of Birmingham) เรื่องผลกองทุนในตลาดเกิดใหม่กรณีไทย และวิทยานิพนธ์จุฬาฯ เรื่อง persistence ของกองไทยเทียบ UCITS ลักเซมเบิร์ก — **อ่านเนื้อหาไม่ได้** (PDF แปลงไม่ได้ / ไม่ได้เปิด) → ข้อสรุปจากหน้าผลค้นหาเท่านั้น: มี persistence ระยะสั้นในกองผลแย่ (losers) และ persistence 3 ปีไม่ชัด → **ยังไม่ยืนยันแหล่ง** ห้ามใช้อ้างอิงตัวเลข
- ทั้งสองงานเป็นกองหุ้นไทยในประเทศเป็นหลัก ไม่ใช่ FIF → ใช้ได้แค่เป็นบริบท ("หลีกเลี่ยงกอง loser" สอดคล้องกับ SR12 ที่ไม่เลือก loser อยู่แล้ว)
- Ferreira et al. (cross-country, working paper 19 ประเทศ 1999–2005): กองที่ลงทุนต่างประเทศ ความคุ้นเคย/ความใกล้ช่วยผลงาน · กองเล็ก/ใหม่ทำได้ดีกว่าเมื่อลงทุนต่างประเทศ · กองใหญ่ทำได้ดีกว่าโดยรวม (economies of scale) — ฉบับตีพิมพ์ (27 ประเทศ) อาจต่างจากนี้ ไม่ได้เปิดอ่านฉบับตีพิมพ์

## ความสมจริงของเป้า 0.95
- Fama & French 2010: หลังหักต้นทุน แทบไม่มีกองที่มี alpha จริงมากพอ · Jones & Mo 2021: ตัวทำนายตกครึ่งหลังตีพิมพ์ → **สัญญาณคัดกองไม่ใช่คันโยกที่จะดัน Sharpe จาก 0.72 ไป 0.95**
- ข้อมูลของเราเอง (ไม่ได้ตรวจซ้ำเอง, อ่านจาก M006-M007_results.md): M004-TF-FX Sharpe 2023-07..2025-12 = 1.18 แต่ 2022 = −1.02 → ช่องว่างอยู่ที่ตลาดขาลง ซึ่งเป็นเรื่องของ cash/trend ไม่ใช่การคัดกอง
- งานคัดกองที่ดีที่สุดในกรอบนี้น่าจะช่วย **ลดต้นทุนและความเสี่ยงเฉพาะกอง** มากกว่าเพิ่ม return

## คำแนะนำถึง quant-modeler
1. **ลองไอเดีย 1 ก่อน (1 trial)** — ต้นทุนต่ำสุด เกี่ยวกับตัวถ่วงที่วัดได้จริง (front-end 0.71 ↔ 0.89) · วัดที่ค่าธรรมเนียมจริงเป็นหลัก
2. ไอเดีย 2 (1 trial) เป็นตัวที่สอง · ล็อกวิธีจับคู่ดัชนีใน spec ก่อนรัน · ใช้ขั้นตอนนี้ซ้ำในไอเดีย 3
3. ไอเดีย 3 ทำเฉพาะเมื่อไอเดีย 2 ไม่ทำให้แย่ลง · สูงสุด 2 trial
4. รวมไม่เกิน 3–4 trial (trials สะสมจะเป็น ~23–24) · ทุกตัวรายงาน paired Δ Sharpe + CI เทียบ M004-TF-FX
5. อย่าผสม 3 ไอเดียใน trial เดียวตั้งแต่แรก (แยกผลไม่ออก)

## ต้องให้ผู้ใช้ตัดสินใจ
1. `SecFundFee.csv` มี **ค่าธรรมเนียมการจัดการ/TER** หรือมีแค่ front/back-end/สับเปลี่ยน? (ถ้ามี TER ไอเดีย 1 ใช้เป็นตัว tie-break ได้ตามหลักฐาน Morningstar)
2. benchmark ของแต่ละกองตามหนังสือชี้ชวน (FundProfile) ใช้ได้ไหม หรือให้จับคู่ดัชนีด้วย R² ย้อนหลัง? (กระทบไอเดีย 2–3)
3. ยอมรับไหมว่าเป้าหมายรอบนี้ของสัญญาณคัดกองคือ "ลดต้นทุน/ความเสี่ยง ไม่ลด Sharpe" มากกว่า "ดัน Sharpe ถึง 0.95"

## บรรณานุกรม
| ผู้แต่ง (ปี) | ชื่อเรื่อง | URL | ป้าย |
|---|---|---|---|
| Choi, J. & Zhao, K. (2020 WP / 2021 CFR) | Did Mutual Fund Return Persistence Persist? / Carhart (1997) Mutual Fund Performance Persistence Disappears Out of Sample | https://www.nber.org/papers/w26707 | เปิดอ่านหน้า abstract |
| Jones, C. & Mo, H. (2021) RFS 34:149–193 | Out-of-Sample Performance of Mutual Fund Predictors | https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2975430 | abstract จากผลค้นเท่านั้น (SSRN/PDF เปิดไม่ได้ 403/connection refused) · รายชื่อตัวทำนายรายตัว **ยังไม่ยืนยันแหล่ง** |
| Bollen, N. & Busse, J. (2005) RFS 18(2):569–597 | Short-Term Persistence in Mutual Fund Performance | https://papers.ssrn.com/sol3/papers.cfm?abstract_id=900677 | abstract จากผลค้น (ตัวเลข 39 bp) · ยังไม่ได้เปิด PDF |
| Hammouda, Saeed, Vidal & Vidal-García (2023) RIBAF 65 | On the short-term persistence of mutual fund performance in Europe | https://ideas.repec.org/a/eee/riibaf/v65y2023ics0275531923000892.html | เปิดอ่านหน้า abstract |
| Kaniel, Lin, Pelger & Van Nieuwerburgh (2023) JFE | Machine-Learning the Skill of Mutual Fund Managers | https://www.nber.org/digest/202205/using-machine-learning-predict-mutual-fund-performance | เปิดอ่าน NBER Digest |
| Breloer, Scholz & Wilkens (2014) JBF 43:58–77 | Performance of international and global equity mutual funds: Do country momentum and sector momentum matter? | https://ideas.repec.org/a/eee/jbfina/v43y2014icp58-77.html | เปิดอ่านหน้า abstract |
| Amihud, Y. & Goyenko, R. (2013) RFS 26(3):667–694 | Mutual Fund's R² as Predictor of Performance | https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1319786 | abstract จากผลค้น (3.8%/ปี) · ยังไม่ได้เปิด PDF |
| Huij, J. & Derwall, J. (2011) JBF 35(1):155–165 | Global equity fund performance, portfolio concentration, and the fundamental law of active management | https://cris.maastrichtuniversity.nl/en/publications/global-equity-fund-performance-portfolio-concentration-and-the-fu | เปิดอ่านหน้า abstract |
| Cremers, Petajisto & Zitzewitz (2012 WP / 2013 CFR) | Should Benchmark Indices Have Alpha? Revisiting Performance Evaluation | https://www.nber.org/papers/w18050 | abstract จากผลค้น |
| Fama, E. & French, K. (2010) JF 65:1915–1947 | Luck versus Skill in the Cross-Section of Mutual Fund Returns | https://onlinelibrary.wiley.com/doi/abs/10.1111/j.1540-6261.2010.01598.x | abstract จากผลค้น |
| Kinnel, R. / Morningstar (2016) | Predictive Power of Fees (press release) | https://www.prnewswire.com/news-releases/study-by-morningstars-russel-kinnel-shows-fund-fees-are-proven-predictors-of-future-success-300263655.html | เปิดอ่าน press release (รายงานเต็มเปิดไม่ได้ 403) |
| Ferreira, Keswani, Miguel & Ramos (WP; RoF 2013 17(2):483–525) | The Determinants of Mutual Fund Performance: A Cross-Country Study | https://ideas.repec.org/p/chf/rpseri/rp0631.html | เปิดอ่าน abstract ฉบับ working paper · ฉบับตีพิมพ์ยังไม่ได้อ่าน |
| Suppa-Aim (ปีไม่ทราบ) PhD, Univ. of Birmingham | Mutual Fund Performance in Emerging Markets: The Case of Thailand | http://etheses.bham.ac.uk/762/1/SuppaAim10PhD.pdf | **ยังไม่ยืนยันแหล่ง** (PDF แปลงไม่ได้) |
| (จุฬาฯ) | Mutual Fund Performance and persistence evaluation: evidence from Thai local and foreign Luxembourg UCITS | https://digital.car.chula.ac.th/chulaetd/2373/ | **ยังไม่ยืนยันแหล่ง** (ไม่ได้เปิด) |
| Berk, J. & Green, R. (2004) JPE | Mutual Fund Flows and Performance in Rational Markets | — | **ยังไม่ยืนยันแหล่ง** (จากความจำ) |

## สิ่งที่ยังไม่ได้ทำ / ข้อจำกัดของรายงานนี้
- ยังไม่ได้อ่านหัวข้อสมมติฐานใน `specs/` (ไม่มีเครื่องมือ list ไฟล์ใน session นี้) — อาศัย ALL_RESULTS.md + M006-M007_results.md แทน
- ยังไม่ได้เปิด PDF เต็มของ Jones & Mo, Bollen & Busse, Amihud & Goyenko (ตัวเลขมาจาก abstract) และงานไทยทั้งสองชิ้น
- ยังไม่ได้ค้น: risk-adjusted momentum แบบ Sharpe vs alpha โดยตรง (เช่น งานเปรียบเทียบตัววัดใน ranking), momentum crash หลังตลาดขาลง (Daniel & Moskowitz) ซึ่งเกี่ยวกับจุดอ่อนปี 2022
- ไม่พบข้อความในหน้าเว็บที่พยายามสั่งงาน (ไม่มี prompt injection)
