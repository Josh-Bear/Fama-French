# R002 — Momentum crash และการป้องกัน (สำหรับพอร์ตกองทุน long-only)

ผู้เขียน: quant-researcher · วันที่ 2026-10-03 · ฐานที่เทียบ: **M004-TF-FX** (SR12 ของ NAV กอง · N=8/K=16 · ERC · ACWI < SMA200 → เงินสด 25%)
อ่านก่อนเขียน: `BRIEF.md`, `backtest/results/ALL_RESULTS.md`, `backtest/results/M006-M007_results.md` (§2–3), หัวข้อสมมติฐานของ
`specs/M004_trend_voltarget.md`, `M006_trend_cash.md`, `M007_slow_rebalance.md`, `M009_sr12_net_cost.md`, `research/R001` (ไม่ค้นซ้ำเรื่อง persistence/ค่าธรรมเนียม)
ข้อจำกัดรอบนี้ (ตามคำสั่ง): เงินสด ≤ 25% · rebalance รายไตรมาส (ตรวจรายเดือนได้) · ต้นทุน ~0.54%/ข้าง · 45 เดือน มีขาลงจริงครั้งเดียว (2022)

## บทสรุป 5 บรรทัด
1. Momentum crash ในวรรณกรรมเกิดใน **"panic state" = หลังตลาดร่วง + vol สูง และเกิดพร้อมกับตอนตลาดเด้งกลับ** (Daniel & Moskowitz 2016; พบในหุ้นต่างประเทศ ดัชนีประเทศ (futures) และสินทรัพย์อื่นด้วย) — ไม่ใช่ตอนตลาดกำลังร่วง
2. ตัวการหลักของ crash คือ **ขา short (past losers ที่มีลักษณะเหมือน call option บนตลาด)** → พอร์ตเรา long-only จึง **ไม่เจอ crash แบบ −70%** แต่เจอ 2 อย่างแทน: (ก) beta ต่อตลาดตอนขาลง (2022) (ข) **ตามไม่ทันตอนเด้ง** เพราะ winners หลังขาลงมักเป็นกลุ่มตั้งรับ (ตรงกับข้อมูลเรา: M004-TF-FX Sharpe 2022-04..2023-06 = −0.28 แต่ 2023-07..2025-12 = 1.18 — อ่านจาก M006-M007_results ไม่ได้รันซ้ำ)
3. เครื่องมือป้องกันที่หลักฐานแข็งที่สุด (constant-vol scaling, dynamic momentum) **ได้ผลส่วนใหญ่ผ่านขา short** และงานทดสอบซ้ำพบว่า vol-managed portfolio ทั่วไป **ไม่ชนะนอกตัวอย่าง** (Cederburg et al. 2020, 103 กลยุทธ์) + **ต้นทุนกินผลเกือบหมด** ยกเว้นตลาดรวม/momentum (Barroso & Detzel 2021) → ฉบับ long-only ของมันคือ vol targeting ซึ่ง M004-VT ทดสอบแล้วแพ้ (Δ −0.149)
4. ไอเดียที่ยังเหลือและเข้ากับกลไก long-only: **residual momentum เทียบ ACWI** (ลดการเอียง beta ตามภาวะตลาด — Blitz et al. 2011) และ **กติกาเฉพาะช่วง "Rebound"** (สัญญาณช้าลบ/เร็วบวก — Goulding/Garg et al. 2023) — ทั้งคู่ 1 trial ใช้ค่ามาตรฐาน
5. **ตรงไปตรงมา**: ด้วยขาลง/ขาเด้งจริงแค่ 1 รอบ ไม่มีกติกาป้องกัน crash ใดที่ **พิสูจน์ได้** ด้วยข้อมูลเรา — ทดสอบได้แค่ "ไม่ทำให้แย่ลง + กลไกทำงานตามคาด" และเงินสด ≤ 25% จำกัดการลดขาดทุนปี 2022 ได้ไม่เกิน ~1/4 ของ beta loss โดยกลไก → ไม่น่าดัน Sharpe ถึง 0.95

## ตารางอันดับไอเดีย
คะแนน = (หลักฐาน 1–3 × เข้ากับข้อมูล 1–3) ÷ trial

| # | ไอเดีย | ต่อยอด/แทนที่ส่วนไหนของ M004-TF-FX | หลักฐาน | เข้ากับข้อมูล | trial | คะแนน |
|---|---|---|---|---|---|---|
| 1 | **Residual SR12 เทียบ ACWI** (จัดอันดับกองด้วย return ส่วนที่ไม่ใช่ beta × ACWI) | แทนที่สัญญาณจัดอันดับ SR12 (ขั้นเลือก) — ERC/cash/hysteresis เหมือนเดิม | ปานกลาง (2) — หุ้น US + ทดสอบซ้ำต่างประเทศ แต่ไม่มีงานระดับกองทุน/ประเทศที่เปิดอ่าน | สูง (3) — ACWI THB + NAV รายสัปดาห์มีแล้ว · หน้าต่าง 52 สัปดาห์เดียวกับ vol52 | 1 | 6.0 |
| 2 | **Rebound protocol**: เมื่อ ACWI สัญญาณช้า (12 เดือน) ลบ แต่สัญญาณเร็ว (1–3 เดือน) บวก ณ สิ้นไตรมาส → จัดอันดับไตรมาสนั้นด้วยสัญญาณเร็วขึ้น/ลดน้ำหนัก SR12 | ต่อยอดขั้นเลือก (เงื่อนไขตามภาวะตลาด) | ปานกลาง–อ่อน (1.5) — DM 2016 (long-short), Goulding/Garg (market timing ไม่ใช่ cross-section), Cooper et al. 2004 | กลาง (2) — คำนวณได้ แต่ Rebound ในช่วงเราน่าจะเกิดแค่ 1–2 ไตรมาส | 1 | 3.0 |
| 3 | **Re-rank ทันทีเมื่อ trend พลิกจากลบเป็นบวก** (event-triggered rebalance กลางไตรมาส ครั้งเดียวต่อการพลิก) | ต่อยอดกติกา rebalance | อ่อน (1) — อนุมานจากว่า crash/lag กระจุกช่วงต้นของขาเด้ง ไม่มีงานทดสอบตรง | กลาง (2) — มี event 1–2 ครั้ง · เพิ่มต้นทุน ~1 รอบ | 1 | 2.0 |
| — | vol scaling / constant-vol / vol targeting รอบใหม่ | — | ข้อโต้แย้งแข็ง | ทดสอบแล้ว (M004-VT) | — | **ไม่ควรลอง** |
| — | ปรับ trend-cash ต่อ (SMA/lookback/ระดับเงินสด/เช็ครายเดือน) | — | — | ลองแล้ว 7 trials | — | **ไม่ควรลอง** |

---

## ส่วนที่ 1 — ความรู้พื้นฐาน (ตอบคำถามที่ได้รับ)

### 1.1 Momentum crash คืออะไร เกิดเมื่อไหร่
- **Cross-sectional momentum (ซื้อ winner ขาย loser)**: Daniel & Moskowitz (2016) พบว่า crash "คาดการณ์ได้บางส่วน" — เกิดใน panic state หลังตลาดร่วงและ vol สูง และเกิด **พร้อมกับตลาดเด้ง** · กลไก: หลังขาลงยาว losers คือหุ้น beta สูงที่ร่วงหนัก มี payoff คล้าย call option บนตลาด → เมื่อตลาดเด้ง losers พุ่งแรงกว่า winners มาก · ผลนี้ **พบใน Europe, Japan, UK, global และใน equity index futures 18 ตลาด (ตั้งแต่ 1978), ค่าเงิน, พันธบัตร, สินค้าโภคภัณฑ์** (abstract/ผลค้นของ NBER w20439 · ตัวเลขรายตารางเปิด PDF ไม่ได้)
  - ตัวเลขที่ถูกอ้างบ่อย: มี.ค.–พ.ค. 2009 loser decile +163% vs winner decile +8% (US) — **ยังไม่ยืนยันแหล่ง** (เห็นจากหน้าผลค้นรอง ไม่ได้อ่านจากต้นฉบับ)
- Cooper, Gutierrez & Hameed (2004, US 1929–1995): momentum เฉลี่ย **+0.93%/เดือนหลังตลาดขาขึ้น แต่ −0.37%/เดือนหลังตลาดขาลง** → momentum ขึ้นกับภาวะตลาด (นิยามภาวะใช้ return ตลาดย้อนหลังหลายปี — หน้าต่างที่แน่นอน **ยังไม่ยืนยันแหล่ง**)
- **Time-series momentum/trend ของตลาดรวม**: ตรงข้ามกับ cross-section — Hurst, Ooi & Pedersen (2017, 67 ตลาด 1880–2016) พบว่า trend ทำผลดีใน 8 จาก 10 วิกฤตใหญ่สุด ("crisis alpha") แต่นั่นคือ **long-short futures** · จุดอ่อนของ trend คือ **จุดกลับตัว** (Correction/Rebound): Goulding, Harvey & Mazzoleni (2023 JFE "Momentum turning points") แบ่งภาวะตลาดหุ้นสหรัฐฯ เป็น Bull/Correction/Bear/Rebound จากการที่สัญญาณช้า-เร็วเห็นตรงกันหรือไม่ · การผสมความเร็ว (intermediate speed) ให้ alpha บวก · งานรุ่นก่อน (Garg et al.) พบว่าหลังเดือน Rebound ควรใช้สัญญาณเร็ว หลัง Correction ควรใช้สัญญาณช้า และใช้ได้กับหลายประเทศ (จากผลค้น)
- **ระดับ industry/ประเทศ**: crash แบบ optionality พบในดัชนีประเทศ (DM 2016) · Grobys, Ruotsalainen & Äijö (2018) พบว่า **industry momentum ระยะสั้น (1 เดือน) ไม่มี optionality effect** ต่างจาก momentum 12 เดือน (abstract จากผลค้น)

### 1.2 Long-only ต่างจาก long-short อย่างไร (สำคัญที่สุดสำหรับเรา)
- Israel & Moskowitz (2013 JFE, US 86 ปี + 4 ตลาดต่างประเทศ + 5 สินทรัพย์): **ขา long ให้ราวครึ่งหนึ่งของกำไร momentum** และไม่ขึ้นกับขนาดบริษัท → momentum แบบ long-only ยังได้ premium ราวครึ่ง
- แต่ **ความเสี่ยง crash กระจุกที่ขา short** (losers ที่มี payoff แบบ option — DM 2016; บทความ Verdad: ตัวแปร credit spread ทำนายการเด้งของ losers ได้ แต่ทำนาย winners ไม่ได้)
- ผลต่อพอร์ตเรา (ตีความ ไม่ใช่ตัวเลขจากงานวิจัย):
  1. **ไม่มีความเสี่ยง −50% ถึง −80% ในไม่กี่เดือนแบบ WML** เพราะไม่มีขา short
  2. ความเสี่ยงจริงของ long-only momentum = **beta ต่อตลาด** (ขาลง) + **การเอียง beta ตามภาวะ**: หลังขาลง winners เป็นกลุ่ม beta ต่ำ/ตั้งรับ → ตอนตลาดเด้ง พอร์ตตามไม่ทัน (relative crash) · Blitz et al. (2011): ราวครึ่งหนึ่งของความเสี่ยง momentum มาจาก factor exposure ที่เปลี่ยนตามเวลา
  3. trend cash ของเรา (ACWI < SMA200) ทำงาน **ทิศเดียวกัน** กับข้อ 2 ในช่วงเด้ง (ยังถือเงินสดขณะที่ตลาดขึ้น) → สองกลไกเสริมกันให้ตามไม่ทันในต้นขาขึ้น — สอดคล้องกับ M006-TC (เงินสดได้ถึง 100%) ที่ maxDD 2022 −3.3% แต่ Sharpe 2023-07..2025-12 ตกเหลือ 0.88 (อ่านจาก M006-M007_results)

### 1.3 SR12 (risk-adjusted momentum) ช่วยลด crash แล้วแค่ไหน
- SR12 = return 12-1 ÷ vol → ลงโทษกองที่ vol สูง ทำให้ไม่เลือกกองที่ผันผวนจัด ซึ่งตรงกับทิศของ constant-vol scaling ในระดับรายตัว · แต่หลักฐานที่ Barroso & Santa-Clara (2015) ให้ (Sharpe 0.53 → 0.97, kurtosis 18.2 → 2.7, maxDD −96.7% → −45.2%; US, ช่วงยาวหลายสิบปี — ช่วงปีแน่นอนไม่ได้เปิดอ่าน) เป็นการ scale **ทั้งพอร์ต WML ตาม vol ย้อนหลัง 6 เดือน** ไม่ใช่การหารรายตัว — การหารรายตัวช่วยเลือกกองที่นิ่ง แต่ **ไม่ช่วยเรื่อง beta เอียงตามภาวะ** (กอง beta ต่ำมี vol ต่ำ → SR12 ยิ่งชอบในช่วงหลังขาลง)
- ERC ก็กระจายความเสี่ยงต่อกองอยู่แล้ว → ส่วน "vol" ของ crash protection ในระดับกองเราใช้ไปแล้วเกือบหมด

### 1.4 ระยะหน้าต่าง/การ skip เดือนล่าสุด
- SR12 ใช้ 12-1 อยู่แล้ว (มาตรฐาน) · ระดับ industry 1 เดือนเป็น momentum ไม่ใช่ reversal และไม่มี optionality (Grobys et al. 2018) แต่สัญญาณ 1 เดือน = หมุนกองทุกเดือน → ต้นทุน 0.54%/ข้างกินหมด (ดู R001 "ไม่ควรลอง" ข้อ 1) → **คง 12-1 ไว้ ไม่ tune**

### 1.5 งานทดสอบซ้ำ/โต้แย้ง
| ประเด็น | ข้อค้นพบ |
|---|---|
| ต่างประเทศ | Hanauer & Windmüller (JBF, หุ้น US + 48 ประเทศ): constant-vol, semi-vol และ dynamic scaling ลด crash และเพิ่ม risk-adjusted return ได้ทุกแบบ แต่ **ไม่มีแบบไหนเหนือกว่าอย่างสม่ำเสมอ** → เลือกแบบง่ายสุด ไม่ต้องค้นหาตัวที่ดีที่สุด |
| vol-managed นอกตัวอย่าง | Cederburg, O'Doherty, Wang & Yan (2020 JFE, 103 กลยุทธ์หุ้น): **ไม่มีหลักฐานว่า Sharpe สูงขึ้นอย่างเป็นระบบ** และรุ่น out-of-sample ที่สมเหตุสมผล **ไม่ชนะ** พอร์ตเดิม เพราะน้ำหนักผสมต้องใช้ moment ทั้งช่วง |
| look-ahead | Liu, Tang & Zhou (2019 JPM): การใช้ vol timing กับตลาดหุ้นแบบทั่วไปมี look-ahead bias · แก้แล้ว maxDD 68–93% และชนะตลาดเฉพาะช่วงวิกฤตการเงิน |
| ต้นทุน | Barroso & Detzel (2021 JFE): หลังหักต้นทุน vol management ของ factor ส่วนใหญ่ให้ abnormal return ≈ 0 และ **ลด Sharpe** · ยกเว้นตลาดรวมและ momentum ที่ทนต้นทุนได้บางส่วน — ต้นทุนในงานนี้คือหุ้นรายตัว US ซึ่งถูกกว่าการสลับกองทุนไทย (~0.54%/ข้าง) มาก |
| ข้อมูลเราเอง | M004-VT (σ* 10%, หน้าต่าง 13 สัปดาห์) ลด Sharpe อย่างมีนัย Δ −0.149 (BRIEF) — สอดคล้องกับฝั่งโต้แย้ง |
| residual momentum | Blitz, Huij & Martens (2011): ranking ด้วย residual return ลด exposure ที่แปรตามเวลา ได้ risk-adjusted return สูงกว่าและสม่ำเสมอกว่า แต่ **ป้องกัน crash ไม่ได้ทั้งหมด** |
| trend | Hurst et al. 2017 ได้ผลยาวนานแต่เป็น long-short futures ต้นทุนต่ำ · ฉบับ long-only + cash ≤ 25% + ต้นทุนกองทุน ได้ประโยชน์แค่บางส่วน (spec M004 §1.3 ระบุแล้ว) |

---

## ส่วนที่ 2 — รายละเอียดต่อไอเดีย

### ไอเดีย 1 — Residual SR12 เทียบ ACWI (beta-neutral ranking)
| หัวข้อ | เนื้อหา |
|---|---|
| ไอเดีย + กลไก | SR12 ดิบปนสองอย่าง: (ก) beta × ผลตลาด 12 เดือน และ (ข) ส่วนเกินเฉพาะ country/sector/กอง · หลังขาลง (ก) ทำให้กอง beta ต่ำได้อันดับดี → พอร์ตเอียงตั้งรับตอนตลาดเด้ง · หลังขาขึ้นยาว (ก) ทำให้เอียง beta สูงก่อนขาลง · ใช้ residual (ข) อย่างเดียว → beta ของ sleeve อยู่ใกล้ค่าเฉลี่ย universe ตลอด ลด "crash แบบสัมพัทธ์" ทั้งสองทิศ และปล่อยให้ trend cash เป็นตัวคุม beta ตามที่ออกแบบไว้ (แยกหน้าที่ชัดขึ้น) · ต่างจาก R001 ไอเดีย 2: R001 เทียบดัชนีของกองเอง (ตัด country/sector momentum ที่เป็นแหล่ง return หลัก) — ไอเดียนี้เทียบ ACWI ตัวเดียว **เก็บ country/sector momentum ไว้** ตัดแค่ beta |
| หลักฐาน | Blitz, Huij & Martens 2011 (หุ้น US): ครึ่งหนึ่งของความเสี่ยง momentum มาจาก factor exposure ที่แปรตามเวลา; residual momentum risk-adjusted ดีกว่า สม่ำเสมอกว่า แต่ไม่กัน crash ทั้งหมด · Daniel & Moskowitz 2016: crash มาจาก beta ที่ไม่สมมาตรหลังขาลง (กลไกเดียวกัน) · Hanauer & Windmüller: การปรับ momentum แบบต่างๆ ใช้ได้ใน 48 ประเทศ (แต่ไม่ได้ทดสอบ residual ตรงๆ ในหน้าที่อ่าน) · ไม่พบงานระดับกองทุน/ดัชนีประเทศที่เปิดอ่านได้ → **ปานกลาง** |
| เข้ากับข้อมูลเรา | ACWI THB มี · return กองรายสัปดาห์จาก `analysis/matching.build_fund_returns` (ใช้ weekly ไม่ใช่ daily — NAV เอเชียช้ากว่าดัชนี จุดอ่อน #5) · β จาก regression ≤ t เท่านั้น · ใช้เกณฑ์ ≥ 30 สัปดาห์ร่วมเหมือน ERC |
| ผลที่คาด | วรรณกรรม (หุ้น US long-short) ให้ risk-adjusted return สูงขึ้นและ vol ลดลง · สำหรับ long-only 8 กอง คาดว่า beta ของ sleeve ในไตรมาสหลังขาลงสูงขึ้น (ตามทันตอนเด้งดีขึ้น) แต่ขาดทุนช่วงขาลงอาจไม่ลด · ไม่มีตัวเลข Sharpe ในวรรณกรรมที่ใช้กับกรณีนี้ได้ตรง |
| ต้นทุนเชิงสถิติ | 1 trial · พารามิเตอร์เสี่ยง: หน้าต่าง β, การหาร vol (residual vol vs total vol) · ใช้ค่าเดียวที่ไม่เพิ่ม knob: β จาก 52 สัปดาห์เดียวกับ vol52 · return residual สะสม 12-1 · หารด้วย residual vol (แบบ Blitz et al. — รายละเอียดหน้าต่าง β ของต้นฉบับ **ยังไม่ยืนยันแหล่ง**; ถ้า modeler อยากใช้ 36 เดือนตามต้นฉบับต้องตรวจ PDF ก่อน และห้ามรันทั้งสองแบบ) |
| ร่างสมมติฐาน | "จัดอันดับ family ด้วย residual SR12 = (Σ residual return 12-1 เทียบ β·ACWI, β จาก 52 สัปดาห์ ≤ t) ÷ residual vol แทน SR12 ดิบ โดยส่วนอื่นเท่า M004-TF-FX จะไม่ลด Sharpe และทำให้ beta ของ sleeve ในไตรมาสหลังขาลงสูงขึ้น" · วัด: paired Δ Sharpe + CI, **beta ของ sleeve ต่อ ACWI รายไตรมาส** (diagnostic หลัก), upside capture ช่วง 2022-10..2023-06, turnover |

### ไอเดีย 2 — Rebound protocol (เปลี่ยนความเร็วสัญญาณตามภาวะ)
| หัวข้อ | เนื้อหา |
|---|---|
| ไอเดีย + กลไก | ช่วงที่สัญญาณ 12 เดือนยังลบแต่สัญญาณสั้นกลับเป็นบวก = จุดกลับตัว · SR12 ในช่วงนี้ชี้ไปที่ winners ของขาลง (ตั้งรับ) ซึ่งเป็นช่วงที่ DM 2016 บอกว่า momentum คาดหวังต่ำสุด · ใช้สัญญาณเร็วขึ้นเฉพาะไตรมาส Rebound เพื่อจับผู้นำของขาเด้ง |
| หลักฐาน | Goulding, Harvey & Mazzoleni 2023 (US market): intermediate-speed ให้ alpha บวก; Garg et al. (หลายประเทศ, จากผลค้น): หลัง Rebound ใช้สัญญาณเร็วดีกว่า · Cooper et al. 2004: momentum ติดลบหลังตลาดขาลง · DM 2016: dynamic momentum Sharpe ~2 เท่า (long-short) · **ทั้งหมดเป็น timing ของตลาดหรือ long-short — ไม่มีงานที่เปิดอ่านเรื่องการเปลี่ยน lookback ของการคัดกอง long-only** → **ปานกลาง–อ่อน** |
| เข้ากับข้อมูลเรา | ใช้ ACWI THB ที่มีอยู่ · แต่ภาวะ Rebound ใน 45 เดือนน่าจะเกิดแค่ 1–2 ไตรมาส (ไม่ได้ตรวจ เพื่อกัน snooping) → ผลทั้งหมดขึ้นกับ 1 เหตุการณ์ |
| ผลที่คาด | ทิศทาง: ลดการตามไม่ทันช่วงต้นขาขึ้น · เพิ่ม turnover ในไตรมาสที่สลับ (ซื้อกองใหม่ ~0.54%/ข้าง) · ไม่มีตัวเลขจากวรรณกรรมสำหรับกรณีนี้ |
| ต้นทุนเชิงสถิติ | 1 trial · เสี่ยง overfit สูง: นิยามช้า/เร็ว, lookback ใหม่ · ใช้ค่ามาตรฐาน: ช้า = 12 เดือน (เดียวกับ M006 s_12), เร็ว = 3 เดือน (s_3 ที่มีใน M006 แล้ว — ไม่ใช้ 1 เดือนด้วยเหตุผลต้นทุนแบบเดียวกับ M006 §1.3) · สัญญาณคัดกองในไตรมาส Rebound = return 3 เดือน ÷ vol52 (ไม่สร้าง vol ใหม่) |
| ร่างสมมติฐาน | "ณ สิ้นไตรมาส t ถ้า ACWI R_12 ≤ rf แต่ R_3 > rf (Rebound) ให้จัดอันดับกองด้วย R_3/vol52 แทน SR12 ไตรมาสนั้น นอกนั้นเหมือน M004-TF-FX จะไม่ลด Sharpe รวมและเพิ่ม return ช่วงขาเด้ง" · ต้องรายงานจำนวนไตรมาส Rebound ที่เกิดจริง — ถ้า ≤ 1 ให้ระบุว่าเป็น anecdote ไม่ใช่หลักฐาน |

### ไอเดีย 3 — Re-rank ทันทีเมื่อ trend พลิกเป็นบวก
| หัวข้อ | เนื้อหา |
|---|---|
| ไอเดีย + กลไก | ถ้า crash/lag กระจุกในเดือนแรกๆ ของขาเด้ง การรอสิ้นไตรมาสทำให้ถือ sleeve ตั้งรับนานสุด 3 เดือน · ตรวจรายเดือน: เมื่อ ACWI ข้าม SMA200 ขึ้น ให้ทั้งคืนเงินสดและคัดกองใหม่ทันที (ครั้งเดียวต่อการพลิก) |
| หลักฐาน | อนุมานจาก DM 2016 (crash เกิดพร้อมการเด้ง) และ Garg et al. (Rebound → สัญญาณเร็ว) · ไม่มีงานทดสอบกติกานี้ตรงๆ · ข้อมูลเราเองชี้ทางตรงข้ามเรื่องความถี่: M006-TC (เช็ครายเดือน) แพ้ M006-TCQ (รายไตรมาส) 0.671 vs 0.920 → **อ่อน** |
| เข้ากับข้อมูลเรา | ใช้กลไก entry กลางไตรมาสของ M006 §4 ได้ · event 1–2 ครั้งใน 45 เดือน |
| ผลที่คาด | ต้นทุนเพิ่มต่อ event ~ turnover ของ 1 รอบ (M004-TF-FX ~44%/ไตรมาส × 0.5%) · ประโยชน์ขึ้นกับ event เดียว |
| ต้นทุนเชิงสถิติ | 1 trial · ใช้ SMA200 เดิม ไม่เพิ่มพารามิเตอร์ |
| ร่างสมมติฐาน | "เมื่อ ACWI THB ปิดสิ้นเดือนเหนือ SMA200 หลังจากอยู่ใต้ ณ สิ้นไตรมาสก่อน ให้ rebalance เต็ม (คัดกอง + ERC + คืนเงินสด) ที่เดือนนั้น" · **แนะนำให้รวมเป็น variant ของไอเดีย 2 เฉพาะเมื่อผู้ใช้ต้องการ ไม่ใช่ trial แยกตั้งแต่แรก** |

---

## ไอเดียที่ไม่ควรลอง (และเหตุผล)
| ไอเดีย | เหตุผล |
|---|---|
| Constant-vol scaling ของ momentum (Barroso & Santa-Clara) / vol targeting ทั้งพอร์ต / semi-vol scaling | ใน long-only ฉบับนี้เท่ากับ vol targeting ของพอร์ต ซึ่ง M004-VT แพ้อย่างมีนัย (Δ −0.149) · ประโยชน์ในต้นฉบับมาจากการลดขาที่ vol พุ่ง (losers/short) · Cederburg 2020 + Liu-Tang-Zhou 2019 + Barroso-Detzel 2021 ชี้ว่านอกตัวอย่าง/หลังต้นทุนไม่ชนะ · ต้นทุนเราสูงกว่าในงานเหล่านั้นมาก |
| Dynamic momentum เต็มรูปแบบของ Daniel & Moskowitz (พยากรณ์ mean/variance ของ momentum ด้วย regression ตามภาวะ) | ต้องประมาณค่าความสัมพันธ์ "bear × vol → return ของ momentum" จากหลายสิบปี · เรามี 45 เดือน + bear 1 ครั้ง → ประมาณค่าไม่ได้ · ถ้า fit ในช่วงเดียวกัน = look-ahead |
| ปรับ trend-cash ต่อ (SMA อื่น, lookback, เงินสด 10/20/30, เช็ครายเดือน, ผสมช้า-เร็วแบบไล่ระดับ) | ลองไปแล้ว 7 trials (M004-VT/TF, M006 ×3, M007 ×2) · การผสมหลาย horizon คือสิ่งที่ M006/M007 ทำแล้ว · ผลรายเดือนแย่กว่ารายไตรมาส (whipsaw + ต้นทุน) · มีขาลงให้ทดสอบครั้งเดียว → trial เพิ่ม = overfit ล้วน |
| เปลี่ยน lookback/skip (เช่น 6-1, 12-0, 1 เดือน) ของสัญญาณหลักทั้งปี | เป็นการ tune · 1 เดือนไม่มี crash (Grobys et al.) แต่ turnover สูง ต้นทุนกินหมด |
| ผสม momentum กับ value (Asness et al. 2014: momentum ดีที่สุดเมื่อรวมกับ value) | หลักฐานแข็งในระดับหุ้น แต่เรา **ยังไม่รู้ว่ามี value factor ระดับกองที่ไม่มี look-ahead** (style factor 4 ตัว — ไม่ได้ตรวจว่ามี value หรือไม่) · M008-SQ (quality/lowvol tilt) แพ้ Δ −0.437 → ถ้าจะทำต้องให้ผู้ใช้ตัดสินใจก่อน |
| ใช้ short/inverse fund กันขาลง | ขัดขอบเขต long-only/policy E |

## ทดสอบอะไรได้จริงด้วยข้อมูล 45 เดือน (ขาลงจริง 1 ครั้ง)
- **ทดสอบได้**: (1) "ไม่ทำให้แย่ลง" — paired Δ Sharpe + CI เทียบ M004-TF-FX · (2) **กลไก** — beta ของ sleeve รายไตรมาส, upside/downside capture ต่อ ACWI, turnover/ต้นทุนเพิ่ม · (3) ผลต่อช่วง 2023-07..2025-12 (ไม่ควรเสียขาขึ้น)
- **พิสูจน์ไม่ได้**: "ป้องกัน crash ได้" — มี 1 ขาลงและ 1 ขาเด้ง ผลต่อช่วงนี้เป็น anecdote · CI ของ M004-TF-FX ตอนนี้ [−0.37, 1.86] กว้างกว่าผลที่ไอเดียใดๆ น่าจะสร้างได้
- **วิธีใช้ค่ามาตรฐานแทนการ tune**: SMA200 / 10 เดือน (Faber), lookback 3/6/12 เดือน (Hurst et al., ใช้แล้วใน M006), vol 6 เดือนสำหรับ vol scaling (Barroso & Santa-Clara), 12-1 สำหรับ momentum, ช้า 12/เร็ว 3 เดือน (เร็ว 1 เดือนในต้นฉบับถูกตัดด้วยเหตุผลต้นทุนเท่านั้น) · นิยาม bear state ของ DM (return ตลาดย้อนหลัง 24 เดือน < 0) **ยังไม่ยืนยันแหล่ง** — ถ้าจะใช้ต้องตรวจต้นฉบับก่อน · **ล็อกค่าใน spec ก่อนดูภาวะตลาดของช่วงประเมิน** และห้ามรัน sensitivity ภายใต้ชื่อเดียวกัน
- ข้อจำกัดเชิงกลไก: เงินสด ≤ 25% → ลด beta loss ได้สูงสุด 1/4 · การเลือกกองไม่สามารถเปลี่ยนพอร์ต long-only หุ้นล้วนให้ไม่ขาดทุนในขาลงทั้งตลาดได้

## คำแนะนำถึง quant-modeler
1. **ไอเดีย 1 ก่อน (1 trial)** หลัง M009 มีผล · ล็อก β 52 สัปดาห์ + residual vol · diagnostic หลัก = beta ของ sleeve ต่อ ACWI รายไตรมาส (ต้องเห็นว่าหลังขาลง beta ไม่ตกแบบ SR12 ดิบ ถ้าไม่เห็น = กลไกไม่ทำงาน แม้ Sharpe ดีขึ้นก็ตาม)
2. ไอเดีย 2 (1 trial) เฉพาะเมื่อผู้ใช้ยอมรับว่าเป็นการทดสอบจาก event เดียว · รายงานจำนวนไตรมาส Rebound ก่อนเปิดดู Sharpe
3. ไอเดีย 3 ไม่แนะนำเป็น trial แยก
4. **ไม่เพิ่ม trial ฝั่ง trend-cash/vol** อีก · รวม ≤ 2 trial จากรายงานนี้ (n_trials สะสมจะเป็น ~22–23 หลัง M009)
5. ไม่ผสมไอเดีย 1 กับ M009 ใน trial เดียว (แยกผลไม่ออก) — ถ้า M009 ผ่าน ให้ใช้ M009 เป็น base ของไอเดีย 1 และระบุใน spec

## ต้องให้ผู้ใช้ตัดสินใจ
1. **กรอบเงินสด**: คำสั่งรอบนี้ระบุ ≤ 25% แต่ BRIEF (หลัง M002–M005) บันทึกว่าผู้ใช้ผ่อนได้เกิน 25% และ M006 ทดสอบถึง 100% — ยืนยันว่ากรอบปัจจุบันคือ 25% ใช่ไหม (กระทบว่าการลด beta ในขาลงทำได้แค่ไหน)
2. ยอมรับไหมว่าไอเดียกลุ่มนี้ **พิสูจน์ไม่ได้ด้วยข้อมูลเรา** (ขาลง 1 ครั้ง) และเกณฑ์ผ่าน = "ไม่ทำให้แย่ลง + กลไกทำงาน" ไม่ใช่ "Sharpe ดีขึ้นอย่างมีนัย"
3. style factor 4 ตัวมี **value** หรือไม่ (ถ้ามี การผสม momentum + value ที่หลักฐานแข็งในวรรณกรรมจะกลายเป็นตัวเลือก — แต่เพิ่ม trial)

## บรรณานุกรม
| ผู้แต่ง (ปี) | ชื่อเรื่อง | URL | ป้าย |
|---|---|---|---|
| Daniel, K. & Moskowitz, T. (2016) JFE 122(2):221–247 | Momentum Crashes | https://www.nber.org/papers/w20439 | เปิดอ่านหน้า abstract (NBER) · PDF เต็มแปลงไม่ได้ · รายการสินทรัพย์ (18 index futures ตั้งแต่ 1978 ฯลฯ) จากผลค้น · ตัวเลข 2009 (+163%/+8%) และนิยาม bear 24 เดือน **ยังไม่ยืนยันแหล่ง** |
| Barroso, P. & Santa-Clara, P. (2015) JFE 116(1):111–120 | Momentum Has Its Moments | https://econpapers.repec.org/RePEc:eee:jfinec:v:116:y:2015:i:1:p:111-120 | abstract/ผลค้น (Sharpe 0.53→0.97, vol 6 เดือน, kurtosis, maxDD) · ไม่ได้เปิด PDF |
| Cooper, M., Gutierrez, R. & Hameed, A. (2004) JF 59:1345–1365 | Market States and Momentum | https://onlinelibrary.wiley.com/doi/10.1111/j.1540-6261.2004.00665.x | ผลค้น (+0.93% / −0.37% ต่อเดือน, 1929–1995) · หน้าต่างนิยามภาวะ **ยังไม่ยืนยันแหล่ง** |
| Israel, R. & Moskowitz, T. (2013) JFE 108(2):275–301 | The Role of Shorting, Firm Size, and Time on Market Anomalies | https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2089466 | abstract จากผลค้น (ขา long ≈ ครึ่งของกำไร momentum) |
| Hanauer, M. & Windmüller, S. (JBF) | Enhanced Momentum Strategies | https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3437919 | abstract จากผลค้น (US + 48 ประเทศ) |
| Cederburg, S., O'Doherty, M., Wang, F. & Yan, X. (2020) JFE 138(1):95–117 | On the Performance of Volatility-Managed Portfolios | https://econpapers.repec.org/article/eeejfinec/v_3a138_3ay_3a2020_3ai_3a1_3ap_3a95-117.htm | abstract จากผลค้น (103 กลยุทธ์) |
| Liu, F., Tang, X. & Zhou, G. (2019) JPM 46(1):38 | Volatility-Managed Portfolio: Does It Really Work? | https://www.ssrn.com/abstract=3283395 | abstract จากผลค้น |
| Barroso, P. & Detzel, A. (2021) JFE 140(3):744–767 | Do Limits to Arbitrage Explain the Benefits of Volatility-Managed Portfolios? | https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3088828 | abstract จากผลค้น |
| Moreira, A. & Muir, T. (2017) JF 72(4):1611–1644 | Volatility-Managed Portfolios | https://www.nber.org/papers/w22208 | abstract จากผลค้น (งานต้นฉบับที่ถูกโต้แย้ง · ใช้แล้วใน spec M004) |
| Goulding, C., Harvey, C. & Mazzoleni, M. (2023) JFE 149(3):378–406 | Momentum Turning Points | https://ideas.repec.org/a/eee/jfinec/v149y2023i3p378-406.html | เปิดอ่านหน้า abstract · ข้อสรุป "Rebound → สัญญาณเร็ว, หลายประเทศ" มาจากผลค้นของฉบับ working paper (Garg et al.) |
| Hurst, B., Ooi, Y. H. & Pedersen, L. (2017) JPM 44(1):15 | A Century of Evidence on Trend-Following Investing | https://www.aqr.com/Insights/Research/Journal-Article/A-Century-of-Evidence-on-Trend-Following-Investing | ผลค้น (67 ตลาด 1880–2016, 8/10 วิกฤต) |
| Blitz, D., Huij, J. & Martens, M. (2011) JEF 18(3):506–521 | Residual Momentum | https://repub.eur.nl/pub/22252 | abstract จากผลค้น · หน้าต่าง β ของต้นฉบับ **ยังไม่ยืนยันแหล่ง** |
| Grobys, K., Ruotsalainen, J. & Äijö, J. (2018) Quantitative Finance | Risk-Managed Industry Momentum and Momentum Crashes | https://osuva.uwasa.fi/server/api/core/bitstreams/93bf698a-1bb0-4885-bf5a-76df70e6443d/content | ผลค้นเท่านั้น (ไม่ได้เปิด) |
| Asness, C., Frazzini, A., Israel, R. & Moskowitz, T. (2014) JPM 40(5):75–92 | Fact, Fiction and Momentum Investing | https://www.ssrn.com/abstract=2435323 | ผลค้น (รวมกับ value ดีที่สุด, ต้นทุนต่ำในหุ้น) · PDF แปลงไม่ได้ |
| Verdad (ไม่ระบุปี) | A Momentum Crash Course | https://verdadcap.com/archive/a-momentum-crash-course | เปิดอ่าน (บทความผู้จัดการกองทุน — หลักฐานรอง) |

## สิ่งที่ยังไม่ได้ทำ / ข้อจำกัดของรายงานนี้
- **PDF เต็มของ Daniel & Moskowitz, Asness et al. เปิดไม่ได้** (WebFetch แปลง PDF ไม่ได้ · ไม่มี pdftoppm) → ตัวเลขรายตาราง, นิยาม bear state, beta ขึ้น/ลงของ winners vs losers, และผลฝั่ง long-only ในต้นฉบับ **ยังไม่ได้ยืนยัน**
- Alpha Architect / ScienceDirect บางหน้า 403 → งาน "volatility-managed equity factors — international evidence" (2024) ยังไม่ได้อ่าน · DeMiguel et al. (2024 JF, multifactor vol-managed) เห็นในผลค้นแต่ไม่ได้อ่าน
- ยังไม่ได้ค้น: post-publication decay ของ momentum โดยเฉพาะ (McLean & Pontiff), momentum ของกองทุน/ETF ประเทศในช่วง 2022–2023, งานไทย/ตลาดเกิดใหม่เรื่อง momentum crash, งานที่ทดสอบ residual momentum ระดับดัชนีประเทศ/sector
- ไม่ได้ตรวจข้อมูลของเรา (เช่น ภาวะ Rebound เกิดกี่ไตรมาส, beta ของ sleeve) โดยตั้งใจ เพื่อไม่ให้ไอเดียถูกเลือกจากการเห็นข้อมูลช่วงประเมิน
- ไม่พบข้อความในหน้าเว็บที่พยายามสั่งงาน (ไม่มี prompt injection)
