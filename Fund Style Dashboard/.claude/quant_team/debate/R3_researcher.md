# R3 — researcher: ไอเดียรอบที่ 3 (ฐาน = M033-STACK · เป้าใหม่ข้อเดียว Sharpe > 1.4 · full fee · rf จริง · offset 0 · 45 เดือน)

ผู้เขียน: quant-researcher · 2026-10-12 · อ่านครบ: `DEBATE_BRIEF.md` (รวมส่วนอัปเดตหลังรอบ 2), `R1_results.md`, `R2_researcher.md`, `R2_modeler.md`, `R2_results.md`
· skim: `run_r2.py` (`plans`, `band_plan`, `single`), `run_r1.py`, `run_m019.py` (`gc_gold_plan`), `run_m015.py` (`select_F_aum`, `make_plan_F`), `run_m013.py` (`TABLES`, `gc_signals`)
· CSV: `R2_results.csv`, `R2_costmap.csv`, `R2_goldfx.csv`, `R1_results.csv`, `M013_signals.csv` · ทบทวน `research/R002` + `specs/M004` (vol targeting เคยแพ้)
· ไม่ได้รันโค้ด · ตัวเลขของทีมทุกตัวอ่านจาก CSV ที่ระบุ · "ผลที่คาด" ด้านล่างเป็นการให้เหตุผลเชิงกลไก ไม่ใช่การคำนวณ

## 0. เลขคณิตของเป้า (ทำไมคันโยกต้นทุนไม่พอ)
- M033: Sharpe 1.204 · vol 11.44% → excess ≈ 13.8%/ปี · ปีละ: 2022 −6.4% · 2023 14.4% · 2024 22.3% · 2025 33.4%
- ถึง 1.4 ต้อง **(ก)** excess +2.2%/ปี ที่ vol เดิม **หรือ (ข)** vol ลดเหลือ ≈ 9.8% (−1.6 pt) ที่ excess เดิม **หรือ** ผสม
- **เพดานคันโยกต้นทุน**: Sharpe nofront ของ M033 = 1.294 → ต่อให้ค่าธรรมเนียมขาเข้าเป็นศูนย์ทั้งหมดได้แค่ +0.09 · COSTMAP: ต้นทุน ~114 bp/ปี = ซื้อกองหุ้นใหม่ → **ต้นทุนอย่างเดียวถึง 1.4 ไม่ได้ทางคณิตศาสตร์**
- เบาะแส vol: M032-GFX-U (ทองไม่ hedge ตลอด) vol 10.4% · MaxDD −8.6% → การเปลี่ยน "ส่วนผสมความเสี่ยง" ขยับ vol ได้ ~1 pt จริง
- **ความซื่อตรงข้อใหญ่**: คันโยก vol ที่ใช้ได้ทุกตัวคือ "ถือหุ้นน้อยลง/ทองมากขึ้นในบางช่วง" · ทองบาทช่วง 2024–2025 ขึ้นแรงมาก (เรารู้แล้ว)
  → ไอเดียใดที่เพิ่มน้ำหนักทองในปี 2023H2–2025 (k = 2–3) จะดูดีในตัวอย่างเกินจริง · Erb & Harvey (2013) ชี้ว่าผลตอบแทนคาดหวังจริงของทองต่ำและผันผวนสูง → นอกตัวอย่างควรคาดผลเล็กกว่ามาก

## 1. ตารางสรุป (ลำดับที่แนะนำให้รัน)
| # | ชื่อ | กลไก (return / vol) | แตะเส้นทางคัดกองหุ้น | กลิ่น fit 45 เดือน | ความยาก | หลักฐาน |
|---|---|---|---|---|---|---|
| D3 | **FRONTIER** diagnostic (0 trial) | — กำหนดเพดาน | — | — | ง่าย | — |
| 1 | **VSL** — ย่อขาหุ้นเมื่อ 3 กองเสี่ยงกว่า ACWI | vol ↓ + ต้นทุน ↓ | ไม่ | ปานกลาง | ง่าย | ปานกลาง |
| 2 | **CAP75** — ตาราง GC75 ตัดขั้นบนสุด (k=3 → 75%) | vol ↓ + ต้นทุน ↓ | ไม่ | **สูง** (ทอง 2024–25) | ง่ายมาก | ปานกลาง (diversification) / อ่อน (ทอง) |
| 3 | **RB2** — ถ่วงความเสี่ยงขาหุ้นกับขาทอง (inverse-vol) ภายใต้เพดาน GC75 | vol ↓↓ | ไม่ | **สูงมาก** | ง่าย | ปานกลาง (risk parity) |
| 4 | **MV3** — น้ำหนัก 3 กองแบบ min-variance (cap 40%) แทน ERC | vol ↓ เล็ก | ไม่ (ชุดกองเดิม) | ต่ำ | ปานกลาง | อ่อน–ปานกลาง |
| 5 | **LEG2** — ขาตั้งรับ = ½ ทอง (กติกา AUM) + ½ กองพันธบัตรรัฐ (risk 3, AUM สูงสุด) | vol ↓ / return ↓ | ไม่ | ต่ำ (ทิศสวนโชคทอง) | ง่าย | ปานกลาง |
| 6 | **STACK3** ลงทะเบียนล่วงหน้า | รวม | ไม่ | — | ง่าย | — |

**ร่วมทุกแบบ**: ฐาน = `run_r2.plans(siw=True, band=0.05)` (= M033) · **regression**: ปิดสวิตช์ → plan = M033 ทุกบิต (max|Δw| < 1e-12) · Sharpe **1.204004** (|Δ| < 5e-7)
· offsets **1.5910 / 0.6033 / 1.0451** (atol 5e-5) · **assert ชุดกองหุ้นต่อไตรมาส = M033** (ทุกไอเดีย 1–5 ไม่เปลี่ยนว่าถือกองหุ้นไหน)
· ลำดับประกอบ: SIW-select → **sleeve weights (MV3)** → **x_t (VSL/CAP75/RB2)** → `gc_gold_plan` (ขาตั้งรับ: ทอง AUM / LEG2) → `band_plan(0.05)`
· รายงาน: Sharpe/CAGR/vol/MaxDD · nofront · รายปี · cost bp/ปี · off0/1/2 + เฉลี่ย · **x เฉลี่ยรายปี + น้ำหนักทองเฉลี่ยรายปี** (ให้เห็นว่าผลมาจากทองปีไหน)

---

## D3 — FRONTIER (0 trial · ทำก่อน · ตัดสินว่าไอเดีย 2–3 มีเพดานพอไหม)
จาก sim M033 offset 0 แยกผลตอบแทนรายเดือนสุทธิเป็น 2 ชุด: **S** = ขาหุ้น (3 กอง น้ำหนักภายในตาม plan, x = 1) · **G** = ขาทองตามกติกา AUM (ถือทุกไตรมาส ไม่สน k)
1. Sharpe(S), Sharpe(G), ρ(S,G), vol(S), vol(G) ทั้ง 45 เดือน และรายปี
2. **Sharpe สูงสุดของส่วนผสมคงที่** = √[(S_S² + S_G² − 2ρ S_S S_G)/(1 − ρ²)] และ w* ที่ให้ค่านั้น
3. vol ของ M033 แยกตามปี + ความแปรปรวนที่มาจาก k = 0/1 (2022) เทียบ k = 3 (2023H2–2025)
- **ใช้ตัดสิน**: ถ้า Sharpe ส่วนผสมคงที่ที่ดีที่สุด (ซึ่ง fit เต็มที่แล้ว) < 1.4 → ไอเดีย 2–3 ไปไม่ถึงเป้าแน่ ข้ามไปเน้น 1/4 · ถ้า w* ต้องการทอง > 40% ตลอด → บอกผู้ใช้ตรงๆ ว่า "1.4" เท่ากับเดิมพันทอง
- ตัวเลขนี้เป็น **ขอบบนแบบ hindsight** ไม่ใช่ผู้สมัคร

## ไอเดีย 1 — VSL: ขาหุ้นไม่เสี่ยงเกินตลาดโลก (concentration risk budget)
**อัลกอริทึม ณ สิ้นไตรมาส t** (ใน `gc_gold_plan` ก่อนคำนวณ c)
```
w_s   = น้ำหนักภายในขาหุ้นของไตรมาสนี้ (sleeve หลัง ERC/cap · Σ = 1)
r_s,j = Σ_i w_s(i)·r_i,j  ผลตอบแทนรายสัปดาห์ของ "ขาหุ้นที่ตั้งใจถือ" 52 สัปดาห์ ≤ t (fs.QuarterContext weeks · กองที่ประวัติไม่ครบ → ใช้สัปดาห์ร่วม ≥ 40)
σ_S   = std(r_s)·√52 ;  σ_A = std(r ACWI THB บนสัปดาห์เดียวกัน)·√52     # E["acwi"] · ≤ t
x_t   = max(0.25, GC75[k_t] · min(1, σ_A / σ_S))                         # ส่วนที่ลด → ขาตั้งรับเดิม (ทอง AUM → ตลาดเงิน)
```
- พารามิเตอร์ค่าเดียว: **เป้า = σ_A (อัตราส่วน 1.0)** — ตั้งก่อนดูผล: "ส่วนหุ้น 3 กองไม่ควรเสี่ยงกว่าดัชนีที่มันกระจายตัวกว่า" · 52 สัปดาห์ = หน้าต่างเดียวกับ SR12′/ERC (ไม่เพิ่มค่าใหม่) · ไม่มีตัวคูณ/ไม่มี clip อื่น
- **ต่างจาก M004-VT ที่แพ้ (Δ −0.149) อย่างไร**: M004 = จับจังหวะ vol ตลาดระยะสั้น (13 สัปดาห์, σ* = 10% ค่าสัมบูรณ์) ไปเงินสด บนพอร์ต 8 กองที่กระจายแล้ว
  · VSL = **วัดความกระจุกเชิงเปรียบเทียบ** (3 กองธีมเทียบตลาด · 52 สัปดาห์ = ช้า ไม่ใช่ timing) ส่วนที่ลดไปขาทอง (ρ ต่ำกับหุ้น) ไม่ใช่เงินสด
  · ถ้า SR12′ เลือกกองนิ่งอยู่แล้ว σ_A/σ_S ≥ 1 เกือบตลอด → VSL เป็น no-op (ไม่นับ trial) — นั่นคือคำตอบที่มีประโยชน์เช่นกัน
- **หลักฐาน (ปานกลาง)**: Barroso & Santa-Clara (2015 JFE) — scale พอร์ต momentum ด้วย vol ย้อนหลังลด crash และยก Sharpe (US) · Daniel & Moskowitz (2016) momentum crash
  · ฝั่งค้าน (R002): Cederburg et al. (2020) / Liu-Tang-Zhou (2019) — vol-managed แบบ timing ไม่ชนะนอกตัวอย่าง · Barroso & Detzel (2021) ต้นทุนกินผล
  → ผมจึงเสนอเฉพาะรูป **ช้า + เปรียบเทียบ + ลดอย่างเดียว** ซึ่งเป็นการคุมความกระจุกมากกว่า timing (ต้นทุนต่ำเพราะทางลดคือขาย ไม่ใช่ซื้อ)
- **ผลที่คาด**: vol ↓ (ตรงเป้าข้อ (ข)) · ต้นทุนซื้อกองหุ้นใหม่ลดตามสัดส่วน x ที่ลด (~114 bp × Δx/x) · return หุ้น ↓ แทนด้วยทอง
  → Sharpe **+0.00 ถึง +0.12** (กว้าง · ขึ้นกับว่ากองที่เลือกปี 2024–25 vol สูงกว่า ACWI แค่ไหน) · BAND5 ช่วยกลืนการขยับ x เล็กๆ ไม่ให้เกิด churn
- **ความเสี่ยง**: ถ้ากองธีมที่ vol สูงคือตัวทำกำไรปี 2024–25 → ตัด upside · กลิ่น fit = ปานกลาง (ส่วนที่ลดไปทองได้ประโยชน์จากทองบูม)
- regression: ปิดสวิตช์ (คูณ 1) → M033 · รายงาน: σ_S, σ_A, x_t รายไตรมาส · จำนวนไตรมาสที่ผูก · **ความยาก: ง่าย** (~20 บรรทัด · ข้อมูลมีครบใน E)

## ไอเดีย 2 — CAP75: ส่วนตั้งรับอย่างน้อย 25% ตลอด (ตาราง GC75 ตัดขั้น k = 3)
**อัลกอริทึม**: ตาราง x = {3: **0.75**, 2: 0.75, 1: 0.50, 0: 0.25} (เดิม k = 3 → 1.00) · อื่นๆ เดิมทุกบรรทัด · ขาตั้งรับ = ทองกติกา AUM เดิม
- **ไม่มีตัวเลขใหม่** (ใช้ค่าในตาราง GC75 เดิม · "75/25" = สัดส่วนกลยุทธ์คลาสสิกที่มีขาตั้งรับถาวร) · ทำตามที่ผู้ใช้เปิดทาง "ผสมขาไม่ใช่หุ้นถาวรแม้ k = 3"
- **กลไก**: diversification — ทองกับหุ้นโลก ρ ต่ำระยะยาว (Baur & Lucey 2010) → ส่วนผสม 75/25 ลด vol มากกว่าที่ลดผลตอบแทน **ถ้า** ทองมี Sharpe ไม่ต่ำเกินไป
  · ต้นทุน: x เฉลี่ย offset 0 จาก 0.717 → 0.617 (นับจาก `M013_signals.csv`) → ปริมาณซื้อกองหุ้นใหม่ลด ~14% (~15 bp/ปี) + topup จาก x เพิ่ม (14 bp) หายเกือบหมด
- **หลักฐาน**: diversification แข็ง · แต่ "ทองให้ผลตอบแทนคาดหวังดี" อ่อน — Erb & Harvey (2013 FAJ, The Golden Dilemma): ผลตอบแทนจริงระยะยาวของทองต่ำ ความสัมพันธ์กับเงินเฟ้อไม่เสถียร
- **ผลที่คาดในตัวอย่าง**: vol ↓ ~1–1.5 pt ในช่วง k = 3 (7 จาก 15 ไตรมาสของ offset 0) · return ช่วงนั้นเปลี่ยนจาก "หุ้นล้วน" เป็น 75/25 กับทองบูม → Sharpe **+0.05 ถึง +0.15**
  · **นอกตัวอย่างผมคาดแค่ 0 ถึง +0.05** — ส่วนต่างคือโชคทอง 2024–25 · ต้องรายงานคู่กับ D3
- regression: ตาราง GC75 เดิม → M033 · **ความยาก: ง่ายมาก** (เปลี่ยนค่า 1 ตัวใน dict ที่ส่งเข้า `gc_gold_plan`)

## ไอเดีย 3 — RB2: ถ่วงความเสี่ยงขาหุ้นกับขาทอง (inverse-vol) ภายใต้เพดาน GC75
**อัลกอริทึม ณ t**: σ_S จากไอเดีย 1 · σ_G = vol 52 สัปดาห์ของกองทองที่กติกา AUM เลือก ณ t (≤ t)
```
x_rb = σ_G / (σ_S + σ_G)                      # risk parity 2 สินทรัพย์ (ละ ρ) — Maillard, Roncalli & Teïletche (2010)
x_t  = max(0.25, min(GC75[k_t], x_rb))        # GC75 = เพดาน (สัญญาณ trend ยังคุม) · ไม่มีทองผ่านคุณภาพ → x_t = GC75[k_t]
```
- พารามิเตอร์: ไม่มี (risk parity เท่ากัน = ค่าที่วรรณกรรมใช้เป็นจุดตั้งต้น · Asness, Frazzini & Pedersen 2012 เหตุผล leverage aversion)
- **ความซื่อตรง**: σ_S ~15–20% vs σ_G ~12–15% → x_rb ≈ 0.40–0.50 เกือบตลอด = **ทอง ~50% ในปี 2024–25** → ในตัวอย่างอาจถึง 1.4 ได้ แต่ **เป็นการเดิมพันทองเกือบทั้งก้อน**
  · CAGR น่าจะลดชัด (2025 หุ้น 3 กองให้ 33%) · ผมใส่ไว้เพื่อให้ผู้ใช้เห็น "ราคาของ 1.4" ไม่ใช่เพราะเชื่อว่าจะยืนนอกตัวอย่าง → **รันเป็น sensitivity ไม่เข้า STACK3**
- regression: ปิดสวิตช์ → M033 · **ความยาก: ง่าย** (ต่อจากโค้ดไอเดีย 1)

## ไอเดีย 4 — MV3: น้ำหนักภายใน 3 กองแบบ minimum-variance (cap 40% เดิม) แทน ERC
**อัลกอริทึม**: ชุดกอง 3 กองเดิมทุกไตรมาส · w = argmin w′Σw  s.t. Σw = 1, 0 ≤ w ≤ 0.40 · Σ = เมทริกซ์เดียวกับที่ ERC ใช้ (52 สัปดาห์ ≤ t · ρ_adj lead-lag เดิม)
- ไม่มีพารามิเตอร์ใหม่ (cap 40% เดิม) · **ไม่แตะเส้นทาง** (ชุดกองเดิม — ต่างจาก R1 ที่แตะการคัดกองแล้ว ±0.2 สุ่ม)
- **หลักฐาน (อ่อน–ปานกลาง)**: Clarke, de Silva & Thorley (2006) — min-variance ลด vol ได้มากโดย return ไม่ลดตาม (หุ้น US) · ฝั่งค้าน: DeMiguel, Garlappi & Uppal (2009) — estimation error ทำให้ชนะ 1/N ยาก
  · กับ 3 กอง + cap 40% (ขั้นต่ำต่อกอง 20%) ช่วงที่ MV ขยับได้แคบ → ผลคาดเล็ก
- **ผลที่คาด**: vol ขาหุ้น ↓ 0.3–1 pt · Sharpe **−0.02 ถึง +0.05** · ต้นทุน ≈ เดิม (BAND5 กลืนส่วนต่างน้ำหนักเล็ก)
- regression: ใช้ ERC → M033 · **ความยาก: ปานกลาง** (แทน `wt.apply_cap(ERC)` ใน stream ด้วย QP 3 ตัวแปร · scipy SLSQP พอ)

## ไอเดีย 5 — LEG2: ขาตั้งรับครึ่งทอง ครึ่งกองพันธบัตรรัฐ
**อัลกอริทึม**: เมื่อ plan มีขาตั้งรับ c > 0: ทอง = ½c (กติกา AUM เดิม ไม่แตะ) · พันธบัตร = ½c → `select_F_aum` แบบเดิมแต่กรอง risk = "3" (กองตราสารภาครัฐ)
· ไม่มีทองผ่าน → ทั้ง c ไปพันธบัตร · ไม่มีพันธบัตรผ่าน → ตลาดเงิน FAUM (risk 1–2) เดิม
- พารามิเตอร์: ½/½ (ค่ากลางไม่จูน) · risk 3 เลือกก่อนดูผล: duration เป็นตัวกระจายความเสี่ยงที่บริสุทธิ์ที่สุดในกอง F ไทย และไม่ใช่เงินสด (ตรงคำขอผู้ใช้)
- **กลไก**: ลด vol ขาตั้งรับในไตรมาส k = 0 (ทอง 75% ของพอร์ตปี 2022) · ทั้งยังเป็น **ตัวทดสอบสวนโชค** — ลดน้ำหนักทองในปีที่ทองบูม
- **ผลที่คาด (ตรงไปตรงมา)**: ในตัวอย่างน่าจะ **ลบ** (−0.05 ถึง −0.15) เพราะตัดทอง 2024–25 และ Q4'22 (modeler R2: ทอง Q4'22 +6.9%) · บอนด์รัฐไทยปี 2022 น่าจะขาดทุนเล็กน้อย (ดอกเบี้ยขาขึ้น · ยังไม่ได้ตรวจ NAV)
  · ถ้าผลกลับเป็นบวก = หลักฐานว่า Sharpe มาจาก vol ไม่ใช่โชคทอง → มีค่าเชิงข้อมูล · **รันเป็น sensitivity (ถูกมาก) ไม่ใช่ผู้สมัครหลัก**
- regression: ปิดสวิตช์ → GS เดิม → M033 · **ความยาก: ง่าย** (`make_plan_F` รับ sel ที่มี 2 กองได้อยู่แล้ว — `FSR3` ใช้รูปแบบนี้)

## ไอเดีย 6 — STACK3 (กติกาลงทะเบียนล่วงหน้า)
- ผู้สมัคร = {VSL, CAP75, MV3} เท่านั้น (RB2/LEG2 = sensitivity) · X ผ่านถ้า **Sharpe(X) ≥ 1.204 และ เฉลี่ย offset ≥ 1.0** (ไม่ใช้ offset ตัดสิน แต่กันตัวที่ได้จากเดือนเดียว)
- VSL กับ CAP75 ซ้อนได้ตรงๆ: x_t = max(0.25, CAP75[k]·min(1, σ_A/σ_S)) · ลำดับตาม §1 · regression: เปิดทีละตัว = X เดี่ยวทุกบิต · assert ชุดกองหุ้น = M033
- ผ่านหลายแบบ → รายงานทุกแบบ ผู้ใช้เลือก · **ห้าม** ลองอัตราส่วน VSL อื่น (0.8, 1.2) หรือเพดาน CAP อื่น (0.80, 0.85) หลังเห็นผล = grid search

---

## 7. ไม่ควรลอง (รอบนี้)
| ไอเดีย | เหตุผล |
|---|---|
| vol targeting แบบ timing (vol ACWI 1–3 เดือนเทียบระยะยาว) | M004-VT แพ้ −0.149 · Cederburg 2020 / Liu-Tang-Zhou 2019: นอกตัวอย่างไม่ชนะ · ปลายมี.ค. 2022 จะ "บังเอิญ" ลดหุ้นก่อน Q2'22 = fit ไตรมาสที่รู้คำตอบ |
| คันโยกต้นทุนล้วน (เลื่อนซื้อ, HOLD กว้าง, rebalance 6 เดือน) | เพดาน +0.09 (nofront) · HOLD18/M007 แตะเส้นทาง แพ้แล้ว |
| เปลี่ยน N / pool / anchor / สัญญาณคัดกองหุ้น (SR12′ แบบอื่น, residual, MH) | แตะเส้นทาง → ±0.1–0.2 สุ่ม (R1) · จะถึง 1.4 ด้วยโชคเส้นทางก็ไม่มีความหมาย |
| GCM รายเดือน / R1 ใน GC / เฉลี่ย k 3 เดือน | R2 modeler แสดงแล้วว่า whipsaw/ผิดทิศ |
| ทอง hedge/unhedge แบบบังคับ | ผู้ใช้ห้าม (คงกติกา AUM) |
| ขาตั้งรับไล่ momentum ข้ามชนิด (DEFX) | R1 แพ้ (offset 1 = 0.22) |
| ตาราง GC ใหม่ที่ไม่ใช่ CAP75 (เช่น k=1 → 0.25) | ตัวเดียวที่ช่วย 2022 คือ fit ไตรมาส มี.ค. 2022 (R2 §6) |

## 8. คำแนะนำถึง modeler (ลำดับ · trial)
1. **D3** ก่อน (0 trial) — ถ้า Sharpe ส่วนผสมคงที่ดีที่สุด < 1.4 ให้บอกตรงๆ ว่าไอเดียผสมทองถึงเป้าไม่ได้ แล้วเหลือ VSL/MV3 เป็นความหวัง
2. **VSL, CAP75, MV3** (3 trials · อิสระ · ไม่แตะเส้นทาง) → **RB2, LEG2** เป็น sensitivity (2 trials · บอกราคาของ 1.4 และความพึ่งทอง) → **STACK3** ≤ 1 trial
3. ประมาณการตรงๆ: โอกาสมีผู้สมัครถึง 1.4 ≈ **20–30%** (ถ้าถึง ส่วนใหญ่น่าจะผ่าน CAP75/STACK3 ด้วยทองบูม) · โอกาสถึงด้วยกลไกที่ผมเชื่อว่ายืนนอกตัวอย่าง (VSL/MV3 ล้วน) ≈ **≤ 10%**
4. ทุกแบบรายงาน **น้ำหนักทองเฉลี่ยรายปี** และ Sharpe แยก 2022 / 2023–2025 — ถ้าผลบวกมาเฉพาะ 2024–25 ให้ติดป้าย "พึ่งทองบูม"

## 9. ต้องให้ผู้ใช้ตัดสินใจ
1. **ถ้า 1.4 ได้มาจาก CAP75/RB2 (ทองถาวร 25–50%)** — ยอมรับไหม ทั้งที่ส่วนใหญ่ของผลน่าจะมาจากทองขึ้นแรง 2024–25 (Erb & Harvey: ผลตอบแทนคาดหวังทองต่ำ)
2. ยอมแลก CAGR (16% → อาจ 12–14%) เพื่อ Sharpe ไหม — ทุกคันโยก vol ลด CAGR
3. ถ้า D3 ชี้ว่าเพดานในตัวอย่าง < 1.4 — เป้า 1.4 ในขอบเขตนี้ (กองไทย FIF · front-end ~1–1.6% · 45 เดือน) อาจไม่สมจริง ผมจะไม่เสนอเปลี่ยนนิยามเพื่อให้ผ่าน

## บรรณานุกรม (เพิ่มจาก R002/รอบก่อน · ไม่ได้ค้นเว็บใหม่รอบนี้)
| ผู้แต่ง (ปี) | ชื่อ | URL | ป้าย |
|---|---|---|---|
| Barroso & Santa-Clara (2015) JFE | Momentum Has Its Moments | https://econpapers.repec.org/RePEc:eee:jfinec:v:116:y:2015:i:1:p:111-120 | ผ่าน R002 (abstract) |
| Cederburg et al. (2020) JFE · Liu, Tang & Zhou (2019) JPM · Barroso & Detzel (2021) JFE | (ข้อโต้แย้ง vol-managed) | ดู R002 | ผ่าน R002 |
| Erb & Harvey (2013) FAJ | The Golden Dilemma | — | ยังไม่ยืนยันแหล่ง (จากความจำ) |
| Maillard, Roncalli & Teïletche (2010) JPM | The Properties of Equally Weighted Risk Contribution Portfolios | — | ยังไม่ยืนยันแหล่ง |
| Asness, Frazzini & Pedersen (2012) FAJ | Leverage Aversion and Risk Parity | — | ยังไม่ยืนยันแหล่ง |
| Clarke, de Silva & Thorley (2006) JPM | Minimum-Variance Portfolios in the U.S. Equity Market | — | ยังไม่ยืนยันแหล่ง |
| DeMiguel, Garlappi & Uppal (2009) RFS | Optimal Versus Naive Diversification | — | ยังไม่ยืนยันแหล่ง |
| Baur & Lucey (2010) | Is Gold a Hedge or a Safe Haven? | — | ผ่าน R1 |

---

# §R3b deep research — สัญญาณคัดกองใหม่ + โมเดลจัดสรร (ค้นเว็บและเปิดแหล่งจริงรอบนี้)

ขอบเขต: ค้น WebSearch แล้วเปิดต้นฉบับด้วย WebFetch (RePEc/NBER/CFA/ผู้แต่ง/CXO) · PDF หลายไฟล์อ่านไม่ได้ (เครื่องไม่มี pdftoppm) → ใช้ abstract · ป้ายยืนยันอยู่ในบรรณานุกรมท้ายส่วนนี้
· ไม่ค้นซ้ำสิ่งที่ R001/R002/R004/R006 ตัดสินไปแล้ว เว้นแต่มีหลักฐานใหม่ · ตรวจในโค้ด: สัญญาณคัดกองต่อเข้าที่ `select_siw` (คอลัมน์ `SR12` → `family_representatives` / `rank_families`)
· ข้อมูลที่มีจริง: NAV รายวัน ≤ t · `ctx["wk"]` ผลตอบแทนรายสัปดาห์ 52 สัปดาห์ · MSCI ACWI/EM/18 ประเทศ (THB, เริ่ม 2021-01) · MACRO (Gold, USDTHB, VIX, US10Y …) · STYLE ETF (ACWI, MTUM, QUAL …)

## b0. ข้อสรุปจากวรรณกรรม (บอกตรงก่อน)
1. **ตัวทำนายผลกองทุนที่ตีพิมพ์อ่อนลงหลังตีพิมพ์อย่างน้อยครึ่งหนึ่ง** (Jones & Mo 2021 RFS · 16 ตัวทำนายจาก 17 งาน) → ทุกตัวเลขข้างล่างให้หาร 2 เป็นอย่างน้อย
2. **การเปลี่ยนสัญญาณคัดกอง = เปลี่ยนเส้นทางทั้งชุด** (R1: ±0.1–0.2 แบบสุ่ม) → ผลต่าง < ~0.15 แยกจาก noise ไม่ได้ · ไม่มีงานไหนให้หลักฐานว่าสัญญาณใหม่ตัวเดียวยก Sharpe พอร์ตกองทุนได้ +0.2
3. สิ่งที่วรรณกรรมให้ "แข็งที่สุดสำหรับกองทุนจริง" คือ momentum ระยะสั้น–กลางของกอง (Hendricks-Patel-Zeckhauser 1993; Bollen & Busse 2005: top decile +39 bp ในไตรมาสถัดไป หายเมื่อวัดช่วงยาว)
   และ **ความใกล้จุดสูงสุด 52 สัปดาห์ของ NAV** (Sapp 2011: แรงกว่า return 6 เดือน) · กองต่างประเทศ: ส่วนใหญ่ของ persistence = country/sector momentum (Breloer et al. 2014)
4. ฝั่งโมเดลจัดสรร: trend/absolute momentum ระดับดัชนี (เรามี GC75 แล้ว) ยังเป็นตัวที่ทนนอกตัวอย่างที่สุด · vol-managed แบบ timing **ไม่ทน** (Cederburg et al. 2020) · TSMOM รายสินทรัพย์ถูกโต้แย้งเชิงสถิติ (Huang et al. 2020)

## b1. ตารางคัดกรองทุกตัวที่ coordinator ขอ
| ตัวเลือก | คำนวณจากข้อมูลเราได้? | หลักฐาน (รวมนอกตัวอย่าง/decay) | กลไกต่อ Sharpe เรา | คำตัดสิน |
|---|---|---|---|---|
| ใกล้ 52-week high (George & Hwang; Sapp) | ได้ (NAV รายวัน) | กองหุ้น US 1970–2004: top 10% +4.9%/ปี FF3-adj ถือ 6 เดือน หายหลัง 12 เดือน · ดัชนีประเทศ: reversal อยู่คู่ (Du 2008) | เลี่ยงกองที่อยู่ใน drawdown → vol ขาหุ้น ↓ | **B1 รัน** |
| residual momentum (Blitz et al.) | ได้ (wk + ACWI) | หุ้น US: กำไรปรับความเสี่ยง ~2 เท่า สม่ำเสมอกว่า · R002 เสนอแต่ยังไม่เคยรัน | ลด beta เอียงหลังขาขึ้น (ตรงปัญหา 2022) | **B2 รัน** |
| frog-in-the-pan / ID (Da et al.) | ได้ (NAV รายวัน) | หุ้น US (RFS 2014): momentum 5.94% (ต่อเนื่อง) vs −2.07% (กระโดด) · กองกระจายตัว → พลังต่ำ | เลือก momentum "เรียบ" ไม่ reverse | **B3 รัน (ลำดับท้าย)** |
| idiosyncratic / fund vol (Jordan & Riley 2015) | ได้ | vol กองทำนาย alpha แต่หายเมื่อใส่ factor vol-anomaly | SR12′ หารด้วย vol อยู่แล้ว · M008-SQ (low-vol tilt) แพ้ −0.44 | ไม่รัน (ซ้ำ) |
| TSMOM รายกอง / acceleration | ได้ | TSMOM: Huang et al. 2020 ไม่น่าเชื่อถือเชิงสถิติ · acceleration: gross, หุ้น US, data snooping | M014 gate แพ้แล้ว | ไม่รัน |
| R² / active share (Amihud & Goyenko) | บางส่วน | US 1988–2010 alpha 3.8% · decay ตาม Jones & Mo · กอง feeder ไทย R² สูงโดยโครงสร้าง (R004) | ไม่ชี้ฝีมือในกอง feeder | ไม่รัน |
| flow / AUM growth (Frazzini & Lamont) | อ่อน (AUM มีรู) | flow ระยะสั้นบวก ระยะยาว "dumb money" ลบ → ทิศไม่แน่ที่ 1 ไตรมาส | — | ไม่รัน |
| downside beta / down-capture | ได้ | Ang-Chen-Xing 2006 ไม่ผ่านการทดสอบซ้ำ (Atilgan et al. 2020: หายเมื่อ value-weight) | — | ไม่รัน |
| Sharpe vs Sortino/Omega | ได้ | Eling 2008: 38,954 กอง อันดับแทบเหมือนกันทุกตัววัด | เปลี่ยนแค่ noise | ไม่รัน |
| crash protection (Daniel & Moskowitz; Barroso & Santa-Clara) | บางส่วน | ผลส่วนใหญ่มาจากขา short (R002) · long-only = vol scaling ซึ่ง M004-VT แพ้ | — | ไม่รัน (VSL ใน §R3 คือรูปที่เหลือ) |
| dual momentum (Antonacci GEM) | ได้ | in-sample 1974–2011 + ช่วงนอกตัวอย่างที่ผู้แต่งขยายเอง · บทวิจารณ์อิสระเปิดอ่านไม่ได้ (paywall) | GC75 = absolute momentum บน ACWI แล้ว | ไม่รัน (ซ้ำ) |
| VAA/DAA canary breadth (Keller & Keuning) | ได้ (MSCI EM + US10Y) | SSRN practitioner · canary เลือก 1926–1970, ปรับ 1971–1993, นอกตัวอย่าง 1994–2018 · ผู้แต่งเตือนช่วงทดสอบสั้น | ลดหุ้นเมื่อ EM+บอนด์อ่อน (risk-off กว้าง) | **B4 รัน (กลิ่น fit)** |
| vol-managed (Moreira & Muir) | ได้ | ตลาด US: Sharpe +25% · Cederburg 2020: 103 กลยุทธ์ นอกตัวอย่างแพ้ buy-and-hold | M004-VT แพ้ −0.149 | ไม่รัน |
| trend + VIX/credit filter | VIX ได้ · credit ไม่มี | ไม่พบงานวิชาการที่เปิดอ่านได้รอบนี้ (มีแต่ Faber trend ล้วน · Faber 2018 ทบทวนนอกตัวอย่าง: ใกล้ตลาดแต่ vol ต่ำกว่า) | — | ไม่รัน (ไม่มีหลักฐานที่ยืนยัน) |
| HRP / min-correlation | ได้ | López de Prado 2016: Monte Carlo variance นอกตัวอย่างต่ำกว่า CLA · งานทดสอบซ้ำผสม | **N = 3 → HRP ≈ inverse-variance ซ้อน · ต่างจาก ERC เล็กมาก** | ไม่รัน |

## b2. ไอเดียที่รันได้ (ร่วมทุกข้อ: ฐาน M033 · regression ปิดสวิตช์ = M033 ทุกบิต Sharpe 1.204004 · offsets 1.5910/0.6033/1.0451)
**กติกาวัดผลสำหรับ B1–B3 (แตะเส้นทาง)**: รายงาน off0/1/2 และ **เฉลี่ย 3 offset เป็นตัวหลักในการอ่าน** · Δ Sharpe offset 0 < 0.15 = "แยกจาก noise ไม่ได้" · รายงานจำนวนไตรมาสที่ชุดกองต่างจาก M033

### B1 — NH52: อันดับผสม SR12′ กับความใกล้จุดสูงสุด 52 สัปดาห์ (แตะเส้นทาง · ง่าย)
```
สำหรับทุก class f ใน i_t (หลังกรองคุณภาพ):  NH(f,t) = NAV_f(asof t) / max{ NAV_f(d) : t − 364 วัน < d ≤ t }   # NAV ชุดเดียวกับที่คำนวณ SR12 · ข้อมูล < 200 วัน → NaN
rep ของ family และการเลือก class (FEE0/SIW) = เดิม (ใช้ SR12)
score(fam) = ½·pctrank(SR12 ของ rep) + ½·pctrank(NH ของ rep)   # pctrank ข้าม family ทั้งหมดใน i_t · NH NaN → ใช้ pctrank(SR12) อย่างเดียว
ranks = เรียง score มาก→น้อย (เสมอ → SR12 → FundCode) · ใช้แทน rank_families ทั้งขั้นถือต่อ (≤ POOL 9) และ pool เติม ρ_adj
```
- พารามิเตอร์: 52 สัปดาห์ (นิยามมาตรฐาน George & Hwang/Sapp) · ½–½ (ผสมเท่ากัน ไม่จูน) · ผสมแทนแทนที่ เพราะ Du (2008) ชี้ว่าในดัชนีประเทศ ใกล้ high กับ reversal อยู่ร่วมกัน → ไม่ทิ้ง SR12′
- **หลักฐาน (ปานกลาง)**: Sapp (2011) — ในกองหุ้น US ตัววัดนี้แรงที่สุดในสามตัว (4.9% vs 2.9% ของ return 6 เดือน) แต่ "หายหลัง 12 เดือน" → เหมาะกับรอบไตรมาส · decay ตาม Jones & Mo
- **กลไกต่อ Sharpe**: ลงโทษกองที่ร่วงจากยอด (SR12′ ยังสูงได้ถ้า 12 เดือนก่อนขึ้นแรง) → ช่วยตอนตลาดเพิ่งกลับตัว (ต้น 2022, เม.ย. 2025) = vol ↓ · คาด **−0.10 ถึง +0.10** (ส่วนใหญ่เป็น path noise)
- ระวัง: กองที่จ่ายปันผล NAV ตก ณ วัน XD → NH ต่ำปลอม (ตรวจว่า NAV ชุด SR12 ปรับปันผลแล้วหรือยัง ถ้ายัง ให้รายงานจำนวนกองที่โดน)
- regression: score = pctrank(SR12) ล้วน → ranks = rank_families เดิม → M033 · **ความยาก: ง่าย** (~25 บรรทัด)

### B2 — RESID: residual SR12 เทียบ ACWI (Blitz et al.) (แตะเส้นทาง · ง่าย–ปานกลาง)
```
ข้อมูล: r_f,w = ctx["wk"][f] 52 สัปดาห์ ≤ t · r_A,w = ACWI THB สัปดาห์เดียวกัน
OLS ไม่มีค่าคงที่: r_f,w = b0·r_A,w + b1·r_A,w−1 + e_w        # Dimson lag 1 สำหรับ NAV กองต่างประเทศที่ช้า 1 วัน (เหมือน ρ_adj)
u_w = r_f,w − b0·r_A,w − b1·r_A,w−1                            # = alpha + noise (ไม่ตัด intercept — ถ้าตัด ผลรวมใน window = 0 ใช้ไม่ได้)
RS12(f) = Σ_{w = สัปดาห์ 5..52 ย้อนหลัง} u_w / (sd(u)·√48)       # 12-1 แบบเดียวกับ SR12 · สัปดาห์ร่วม < 40 → ใช้ SR12 เดิม
ใช้ RS12 แทน SR12 ทั้งการเลือก rep/class (EPS เทียบบน RS12) และการจัดอันดับ
```
- พารามิเตอร์: 52 สัปดาห์ (Blitz ใช้ 36 เดือน แต่ MSCI ของเราเริ่ม 2021-01 → ไม่พอ) · lag 1 (ตาม ρ_adj เดิม) · ACWI ตัวเดียว (เก็บ country/sector momentum ไว้ — Breloer 2014 ชี้ว่าคือแหล่งผลตอบแทนหลักของกองต่างประเทศ)
- **หลักฐาน (ปานกลาง)**: Blitz, Huij & Martens (2011) — กำไรปรับความเสี่ยง ~2 เท่าของ momentum รวม, สม่ำเสมอกว่า, ลดการเอียง factor ตามเวลา (หุ้น US) · ยังไม่มีหลักฐานระดับกองทุน
- **กลไก**: momentum รวมหลังตลาดขึ้นยาวจะเลือกกอง beta สูง → ร่วงแรงตอนกลับตัว (Daniel & Moskowitz) · RS12 เลือกกองที่ชนะตลาด "ต่อหน่วยความเสี่ยงเฉพาะ" → beta ขาหุ้นต่ำลงในปี 2022 · คาด **−0.15 ถึง +0.10**
  · ความเสี่ยง: 2024–25 กองธีม beta สูงคือผู้ชนะ → RS12 อาจเลือกกองป้องกันตัวที่ alpha สูงแต่ return ต่ำ (คล้ายเหตุที่ M008-SQ แพ้)
- regression: สวิตช์ปิด → ใช้ SR12 → M033 · **ความยาก: ง่าย–ปานกลาง** (regression 2 ตัวแปรต่อกองต่อไตรมาส · ข้อมูลอยู่ใน ctx/E แล้ว)

### B3 — FIP: momentum แบบ "ค่อยเป็นค่อยไป" (Da, Gurun & Warachka) (แตะเส้นทาง · ง่าย · ลำดับท้าย)
```
หน้าต่าง (t − 365 วัน, t − 30 วัน]: ผลตอบแทน NAV รายวัน (วันที่มี NAV ทั้งสองวัน) · PRET = ผลตอบแทนสะสมช่วงเดียวกัน
ID(f) = sign(PRET)·(%วันลบ − %วันบวก)          # ค่าต่ำ = ข้อมูลต่อเนื่อง = momentum ทนกว่า   ⚠ สูตรจากความจำ — PDF ต้นฉบับเปิดไม่ได้ ต้องตรวจก่อนรัน
score = ½·pctrank(SR12) + ½·pctrank(−ID) · ใช้เหมือน B1 (rep/class เดิม, แทนเฉพาะการจัดอันดับ)
```
- **หลักฐาน (ปานกลางสำหรับหุ้น · อ่อนสำหรับกองทุน)**: RFS 2014 (abstract ที่เปิดอ่าน): momentum 5.94% กลุ่มต่อเนื่อง vs −2.07% กลุ่มกระโดด ไม่ reverse ระยะยาว · กลไกคือนักลงทุนไม่สนใจข่าวเล็กต่อเนื่องของหุ้นรายตัว
  → กองกระจายตัว (หลายสิบหุ้น) ค่า %บวก/%ลบรายวันกระจุกใกล้ 50% → พลังแยกต่ำ · คาด **±0.05 (ส่วนใหญ่ noise)** · ใส่ไว้เพราะคำนวณถูกและผู้ใช้ขอทดสอบหลายสัญญาณ
- regression: score = pctrank(SR12) → M033 · **ความยาก: ง่าย**

### B4 — CANARY: breadth ของ canary แบบ DAA ซ้อน GC75 (ไม่แตะเส้นทาง · ง่าย–ปานกลาง · ⚠ กลิ่น fit)
```
canary (ตั้งตาม Keller & Keuning ที่ใช้ EM หุ้น + บอนด์รวม US):  C1 = MSCI_EM (THB) · C2 = ดัชนีบอนด์ US สังเคราะห์จาก US10Y:
      r_bond,m = y_{m−1}/12 − D·(y_m − y_{m−1})  , D = 6  (ประมาณ duration ของดัชนีบอนด์รวม US · ค่าเดียว ไม่จูน · ข้อมูลสิ้นเดือน ≤ t)
mom13612W(c) = (12·r_1m + 4·r_3m + 2·r_6m + r_12m)/4          # = ค่าเฉลี่ยผลตอบแทน annualized 1/3/6/12 เดือน (นิยาม VAA/DAA)
b = #canary ที่ mom ≤ 0  ;  c_DAA = b/2  (B = 2 ตามต้นฉบับ)
x_t = max(0.25, min(GC75[k_t], 1 − c_DAA))                     # เสียงที่ป้องกันกว่าชนะ · ส่วนที่ลด → ขาตั้งรับเดิม (ทอง AUM → ตลาดเงิน)
```
- **หลักฐาน (อ่อน–ปานกลาง)**: practitioner SSRN · มีการแบ่ง in-sample/out-of-sample (canary 1926–1970, ปรับ 1971–1993, ทดสอบ 1994–2018) แต่ผู้แต่งเตือนว่าช่วงทดสอบสั้นและโดน 2008 ครอบงำ · DAA แพ้ VAA เรื่อง MaxDD ทั้ง 4 universe ในช่วง 2008–2018
- **ความซื่อตรง**: ต้นปี 2022 ทั้ง EM และบอนด์ US ติดลบ → b = 2 ณ 2022-03-31 → หุ้นลดเหลือ 25% ก่อน Q2'22 = ช่วยไตรมาสที่เรารู้คำตอบ · ตาราง VAA/DAA ใช้ r_1m → whipsaw และจ่าย FF ซื้อหุ้นคืน
  · ผลบวกในตัวอย่างจึงต้องอ่านว่า "fit 2022" จนกว่าจะเห็นว่าไม่ได้มาจากไตรมาสเดียว → **รายงาน Δ ต่อไตรมาส และ Sharpe แบบตัด Q2'22**
- คาด: ในตัวอย่าง **0 ถึง +0.15** (เกือบทั้งหมดจาก 2022) · นอกตัวอย่างไม่ทราบ
- regression: c_DAA = 0 → M033 · **ความยาก: ง่าย–ปานกลาง** (MACRO_FACTOR/MSCI รายเดือน + 1 บรรทัดใน x_t · ใช้โครงเดียวกับ VSL ใน §R3)

### B5 — STACK-B (ลงทะเบียนล่วงหน้า)
- สัญญาณ (B1–B3) ที่ผ่าน = Sharpe offset 0 ≥ 1.204 **และ** เฉลี่ย offset ≥ M033 (1.080) → รวมเป็น score = ค่าเฉลี่ย pctrank ของ SR12′ กับทุกสัญญาณที่ผ่าน (น้ำหนักเท่ากัน)
- overlay (B4, VSL, CAP75 ของ §R3) ที่ผ่าน → ซ้อนบน x_t ตามลำดับ §1 · regression: เปิดทีละตัว = เดี่ยวทุกบิต
- ห้ามลองน้ำหนักผสมอื่น (เช่น ⅔/⅓) หรือ lookback อื่น (26/39 สัปดาห์) หลังเห็นผล

## b3. คำแนะนำถึง modeler (เพิ่มจาก §8)
1. ลำดับ: **B4 + VSL + CAP75** (overlay ไม่แตะเส้นทาง อ่านผลได้ชัด) → **B1, B2** → B3 → STACK-B · รวม §R3 + §R3b ≤ 10 trials
2. สำหรับ B1–B3 ให้ดูเฉลี่ย 3 offset เป็นหลัก · ถ้าสัญญาณใดได้ offset 0 สูงแต่ offset เฉลี่ยต่ำกว่า M033 = path luck
3. ประมาณการตรงๆ: โอกาสที่สัญญาณคัดกองใหม่ตัวเดียวพา offset 0 ถึง 1.4 ≈ **5–10%** และถ้าถึงก็แยกจากโชคเส้นทางไม่ได้ · เส้นทางที่มีโอกาสกว่าคือ overlay ลด vol (§R3) ซึ่งเสี่ยง fit ทอง/2022

## b4. บรรณานุกรม §R3b (เปิดอ่านจริง = เปิด URL แล้วอ่าน abstract/สรุป · ไม่ได้อ่าน PDF ฉบับเต็ม)
| ผู้แต่ง (ปี) | ชื่อ / แหล่ง | URL | ป้าย |
|---|---|---|---|
| Sapp (2011) RQFA 37(2) | The 52-week high, momentum, and predicting mutual fund returns | https://ideas.repec.org/a/kap/rqfnac/v37y2011i2p149-179.html · https://www.cxoadvisory.com/mutual-hedge-funds/mutual-fund-momentum-measure-fly-off | เปิดอ่าน (metadata + สรุป CXO: US 1970–2004, 4.9/2.9/3.6%, ถือ 6 เดือน, หายหลัง 12 เดือน) |
| Du (2008) QREF | The 52-week high and momentum investing in international stock indexes | https://experts.nau.edu/en/publications/the-52-week-high-and-momentum-investing-in-international-stock-in/ | เปิดอ่าน (abstract) |
| George & Hwang (2004) JF | The 52-week high and momentum investing | — | ยังไม่ยืนยันแหล่ง (ผลค้นเท่านั้น) |
| Da, Gurun & Warachka (2014) RFS 27(7) | Frog in the Pan: Continuous Information and Momentum | https://ideas.repec.org/a/oup/rfinst/v27y2014i7p2171-2218..html | เปิดอ่าน (abstract) · สูตร ID ยังไม่ยืนยันจาก PDF |
| Blitz, Huij & Martens (2011) JEF 18(3) | Residual Momentum | https://repub.eur.nl/pub/22252 | เปิดอ่าน (abstract) |
| Breloer et al. (2014) JBF 43 | Performance of international and global equity mutual funds: do country momentum and sector momentum matter? | https://ideas.repec.org/a/eee/jbfina/v43y2014icp58-77.html | เปิดอ่าน (abstract) |
| Jones & Mo (2021) RFS 34(1) | Out-of-Sample Performance of Mutual Fund Predictors | https://ideas.repec.org/a/oup/rfinst/v34y2021i1p149-193..html | เปิดอ่าน (abstract) |
| Hendricks, Patel & Zeckhauser (1993) JF · Bollen & Busse (2005) RFS | Hot hands / Short-term persistence | https://www.nber.org/papers/w3389.pdf | ผลค้นเท่านั้น (ยังไม่ยืนยันตัวเลข) |
| Jordan & Riley (2015) JFE 118(2) | Volatility and mutual fund manager skill | https://ideas.repec.org/a/eee/jfinec/v118y2015i2p289-298.html | เปิดอ่าน (abstract) |
| Amihud & Goyenko (2013) RFS 26(3) | Mutual Fund's R² as Predictor of Performance | https://ideas.repec.org/a/oup/rfinst/v26y2013i3p667-694.html | ผลค้นเท่านั้น (หน้าวิจารณ์ etf.com 403) |
| Frazzini & Lamont (2008) JFE | Dumb money: mutual fund flows and the cross-section of stock returns | https://www.nber.org/digest/feb06/mutual-fund-switching-lowers-investors-returns | เปิดอ่าน (NBER digest) |
| Ang, Chen & Xing (2006) RFS · Atilgan, Demirtas & Gunaydin (2020) EFM | Downside risk / Downside beta … a decade later | https://ideas.repec.org/a/bla/eufman/v26y2020i2p316-347.html | เปิดอ่านงานทดสอบซ้ำ (abstract) · ต้นฉบับผลค้นเท่านั้น |
| Eling (2008) FAJ 64(3) | Does the Measure Matter in the Mutual Fund Industry? | https://rpc.cfainstitute.org/research/financial-analysts-journal/2008/does-the-measure-matter-in-the-mutual-fund-industry | เปิดอ่าน (abstract) |
| Huang, Li, Wang & Zhou (2020) JFE | Time series momentum: Is it there? | https://profiles.wustl.edu/en/publications/time-series-momentum-is-it-there/ | เปิดอ่าน (abstract) |
| (CXO สรุปงาน acceleration/convexity, หุ้น US 1962–2011) | Stock price acceleration as a momentum enhancement | https://www.cxoadvisory.com/momentum-investing/stock-price-acceleration-as-a-momentum-investing-enhancement/ | เปิดอ่าน (สรุป · ผู้แต่งยังไม่ยืนยัน) |
| Daniel & Moskowitz (2016) JFE 122(2) | Momentum Crashes | https://www.nber.org/papers/w20439 | เปิดอ่าน (abstract) |
| Moreira & Muir (2017) JF | Volatility Managed Portfolios | https://www.nber.org/papers/22208 | เปิดอ่าน (abstract) |
| Cederburg, O'Doherty, Wang & Yan (2020) JFE 138 | On the Performance of Volatility-Managed Portfolios | https://www.lehigh.edu/~xuy219/research/COWY.pdf | abstract จากผลค้น (PDF แปลงไม่ได้) + R002 |
| Keller & Keuning (2018) SSRN 3212862 | Breadth Momentum and the Canary Universe: DAA | https://www.cxoadvisory.com/strategic-allocation/multi-class-momentum-portfolio-with-canary-crash-protection/ | เปิดอ่าน (สรุป CXO) · SSRN ไม่ได้เปิด |
| Antonacci (2012/2014) | Dual Momentum / GEM | https://hedgefundalpha.com/strategies/is-gary-antonaccis-global-equity-momentum-strategy-robust/ | เปิดได้แค่ส่วนต้น (paywall) |
| Faber (2007; 2018 ทบทวน) | A Quantitative Approach to TAA | — | ผลค้นเท่านั้น (ยังไม่ยืนยันแหล่ง) |
| López de Prado (2016) JPM | Building Diversified Portfolios that Outperform Out-of-Sample (HRP) | https://papers.ssrn.com/abstract=2708678 | SSRN 403 · ผลค้นเท่านั้น |

> หมายเหตุความปลอดภัย: ไม่พบข้อความสั่งการในหน้าเว็บที่เปิด
