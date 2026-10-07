# R003 — จำนวนกองในพอร์ตแบบ dynamic (ไม่ล็อก N = 8)

ผู้เขียน: quant-researcher · วันที่ 2026-10-06 · ฐานที่เทียบ: **Trend 25 / M004-TF-FX** (SR12 · top N=8 · hysteresis K=16 · ERC LW 52 สัปดาห์ · cap 25% · ACWI < SMA200 → เงินสด 25%)
อ่านก่อนเขียน: `BRIEF.md`, `research/INDEX.md`, `R001`, `R002`, `backtest/results/ALL_RESULTS.md`, `specs/M002-M005_plan.md` (§1–C8), `specs/M005_composite.md`,
`specs/M008_style_macro.md` (§0–§5), `reports/TOP3_portfolio_logic.md` · ไม่ค้นซ้ำ: persistence/ค่าธรรมเนียม (R001), momentum crash/vol scaling/trend cash (R002)
ตัวเลขของทีมที่อ้าง (ไม่ได้ตรวจซ้ำเอง — รับจากผู้สั่งงานและไฟล์): M005 N5 0.81 / N8 0.35 / N10 0.44 · M009 เปลี่ยนกองเดียวไตรมาสแรก Sharpe ขยับ ~0.2 ·
correlation รายเดือนระหว่างกอง median 0.49 (BRIEF) · front-end ~1.5%/การซื้อ

## บทสรุป 5 บรรทัด
1. **ระดับกองทุน ประโยชน์การกระจายหมดเร็วมาก**: งานจำลองพอร์ตกองทุน (US: O'Neal 1997; ออสเตรเลีย: Brands & Gallagher 2005) พบว่าความเสี่ยงรายงวดลดลงน้อย และประโยชน์ส่วนใหญ่ได้ภายใน ~4–6 กอง (ส่วนที่ได้เพิ่มคือลดการกระจายของความมั่งคั่งปลายทาง/โชค) → ช่วง 4–10 ของผู้ใช้อยู่ในโซนที่ "N ไหนก็กระจายพอ" ส่วนต่าง 8 vs 5 vs 10 ด้าน vol มีแค่ระดับไม่กี่ %
2. **ความไวของ Sharpe ต่อ N ใน M005 (0.81/0.35/0.44 ไม่เรียงตาม N) คือ noise ของการเลือกกอง ไม่ใช่สัญญาณว่ามี N ที่ดีที่สุด** — สอดคล้องกับ M009 (กองเดียวขยับ ~0.2) และเกณฑ์ใน spec M005 §5 เองที่ว่า Δ > 0.3 = ผลไม่เสถียร
3. **ไม่พบหลักฐานที่เปิดอ่านได้ว่า dynamic N ชนะ fixed N นอกตัวอย่าง** — วิธีที่มี (เกณฑ์คะแนน, ENB/DR, ถ่วงตามสัญญาณ, cardinality optimizer, N ตามภาวะ) หลักฐานส่วนใหญ่เป็นเรื่อง "วัด/ควบคุมความเสี่ยง" ไม่ใช่เพิ่ม Sharpe · ผลหลักคือ **เปลี่ยนรูปแบบความเสี่ยง + เพิ่ม turnover (ทุกครั้งที่ N เพิ่ม = ซื้อใหม่ ~1.5%)**
4. วิธีที่พึ่ง correlation (ENB, DR, dedupe) **เจอ bias จาก NAV ไม่พร้อมกัน** ซึ่งทำให้ correlation ต่ำเกินจริง → นับ "จำนวนเดิมพันอิสระ" เกินจริง · วิธีแก้มาตรฐาน: ความถี่ต่ำลง หรือรวม cross-covariance lag ±1 (Scholes–Williams/Dimson; Burns–Engle–Mezrich 1998) — ใช้ได้กับข้อมูลเรา
5. **คำแนะนำตรงๆ**: ถ้าจะลอง ให้ลองเพื่อ "ลดความเปราะต่อการเลือก N" (ensemble หลาย N, 1 trial) ไม่ใช่เพื่อหา N ที่ดีที่สุด · ห้ามเลือก N=5 จากผล M005 · ไม่น่าดัน Sharpe ไปถึง 0.95

## ตารางอันดับไอเดีย
คะแนน = (หลักฐาน 1–3 × เข้ากับข้อมูล 1–3) ÷ trial (diagnostic ที่ไม่นับ trial ให้ทำก่อนเสมอ)

| # | ไอเดีย | ต่อยอด/แทนที่ส่วนไหนของ M004-TF-FX | หลักฐาน | เข้ากับข้อมูล | trial | คะแนน |
|---|---|---|---|---|---|---|
| 0 | **Diagnostic: correlation แบบปรับ lead-lag** (Γ0 + Γ1 + Γ1ᵀ ของ return รายสัปดาห์) เทียบ correlation ปัจจุบัน + จำนวนเดิมพันอิสระ (DR²) ของพอร์ตที่ถือ | ไม่เปลี่ยนโมเดล — วัดว่า N=8 "กระจายจริง" แค่ไหน | แข็ง (3) สำหรับ "async ทำให้ ρ ต่ำเกินจริง" | สูง (3) — weekly NAV มีแล้ว | 0 | ทำก่อน |
| 1 | **N-ensemble**: น้ำหนักหุ้น = ค่าเฉลี่ยของพอร์ต top-N สำหรับ N = 5…10 (แต่ละตัว K = 2N, ERC, cap 25%) | แทนที่ขั้น "คัด N=8" + ขั้นน้ำหนัก (ได้ 5–10 กอง น้ำหนักลดตามอันดับ) | ปานกลาง–อ่อน (1.5) — หลักการ parameter averaging/1/N robustness · ไม่มีงานเฉพาะกองทุน | สูง (3) | 1 | 4.5 |
| 2 | **N จาก DR² (effective number of independent bets)** ภายใน [6, 10] ด้วย covariance ปรับ lead-lag | แทนที่ "N=8 คงที่" | อ่อน–ปานกลาง (1.5) — Choueifaty: DR² = จำนวนเดิมพันอิสระ (การวัด) · ไม่มีงานที่ใช้เป็นกติกาเลือก N | กลาง (2) — Σ 52 สัปดาห์ของ ~10–20 กองมี noise | 1 | 3.0 |
| 3 | **เกณฑ์คะแนนขั้นต่ำ + min/max** (เช่น SR12 > 0, คง 4–10) | แทนที่ N คงที่ | ปานกลาง (2) ระดับสินทรัพย์ (Antonacci absolute momentum: ลด vol/DD) | **ต่ำ (1)** — กองที่ผ่าน SR12 > 0 มีมากกว่า 10 เกือบทุกไตรมาส → กลายเป็น N=10 คงที่ · M006-TCA (ตัวกรองรายกอง) ทำงานน้อยมากแล้ว | 1 | 2.0 → ไม่แนะนำ |
| — | ถ่วงตามความแรงสัญญาณแล้วตัดตัวน้ำหนักต่ำ · cardinality/min-weight optimizer · N ตามภาวะตลาด · grid N | — | ดู "ไม่ควรลอง" | — | — | **ไม่ควรลอง** |

---

## ส่วนที่ 1 — ถือกี่กองแล้วประโยชน์การกระจายหมด

### 1.1 ระดับหุ้นรายตัว (บริบท ไม่ใช่กรณีเรา)
- Statman (1987, JFQA, หุ้น US): พอร์ตหุ้นสุ่มต้อง ≥ 30 ตัว (ผู้กู้) / ≥ 40 ตัว (ผู้ให้กู้) จึงคุ้มต้นทุน — ค้านความเชื่อเดิม "~10 ตัวพอ" · Statman (2004, FAJ): ภายใต้ mean-variance ระดับเหมาะสม > 300 ตัว · Domian, Louton & Racine (2007, Financial Review): "100 ตัวยังไม่พอ" เมื่อวัดด้วยความเสี่ยงความมั่งคั่งระยะยาว (ข้อมูลจากผลค้น/abstract)
- นัยต่อเรา: **กอง FIF แต่ละกองถือหุ้นหลายสิบถึงหลายร้อยตัวอยู่แล้ว** → ความเสี่ยงเฉพาะหุ้นถูกกระจายไปแล้วในตัวกอง สิ่งที่เหลือให้กระจายคือ **ความเสี่ยงเฉพาะธีม/ประเทศ/ผู้จัดการ** ซึ่งระหว่างกองมี correlation สูง (median 0.49) → ประโยชน์ส่วนเพิ่มต่อกองหมดเร็วกว่าหุ้นมาก

### 1.2 ระดับกองทุน / fund-of-funds / multi-manager
| งาน | ตัวอย่าง | ข้อค้นพบ | ป้าย |
|---|---|---|---|
| O'Neal (1997, FAJ 53(2):37–46) | กอง US growth 103 กอง + growth & income 65 กอง, 1976–1994, จำลองพอร์ตสุ่ม | ความเสี่ยงรายงวด (time-series) ลดลง **น้อยมาก** เมื่อเพิ่มกอง · แต่การกระจายของความมั่งคั่งปลายทางลดลงมาก: 4 กองลดลงราวครึ่ง (ถือ 5–19 ปี) · 1→5 กอง growth (10 ปี) 23% → 10% · downside risk ลดลงเมื่อเพิ่มกอง | abstract (ผลค้น) + ตัวเลขจากบทความสรุปรอง (theskilledinvestor) — PDF/หน้า T&F เปิดไม่ได้ (403) |
| Brands & Gallagher (2005, Accounting & Finance) | กองหุ้น active ออสเตรเลีย, จำลอง FoF | ประโยชน์การกระจายส่วนใหญ่ได้ที่ **~6 กอง** | ผลค้นเท่านั้น (Wiley/ResearchGate 403 · PDF UNSW แปลงไม่ได้) — **ยังไม่ยืนยันแหล่ง** สำหรับตัวเลขย่อย |
| Louton & Saraoglu (2008, J. Investing 17(3):47–63) | พอร์ต asset-allocated หลายประเภทสินทรัพย์ | ต้อง **≥ 10 กอง** (เพราะกระจายข้ามหลายหมวด ไม่ใช่กองหุ้นหมวดเดียว) | ผลค้นเท่านั้น — ยังไม่ยืนยันแหล่ง |
| multi-manager (Vanguard 2024 "Combining active managers"; บทความ NISA "Siren song of manager diversification") | ผู้จัดการ active หลายราย | เพิ่มผู้จัดการ → tracking error/active share ลด เข้าใกล้ดัชนี ("closet index") · ประโยชน์ขึ้นกับ correlation ของ excess return | ผลค้นเท่านั้น (PDF Vanguard แปลงไม่ได้ · NISA DNS ล้ม) — ยังไม่ยืนยันแหล่ง |

**ข้อสรุปเชิงตัวเลขแบบเลขคณิต (ไม่ใช่ backtest)**: ถ้า vol กองเท่ากันและ correlation เฉลี่ย ρ, variance พอร์ตเท่ากันต่อ variance กองเดี่ยว = ρ + (1 − ρ)/N
ใช้ ρ = 0.49 (median ใน BRIEF): N=4 → vol 0.79 ของกองเดี่ยว · N=5 → 0.77 · N=8 → 0.74 · N=10 → 0.74 · N→∞ → 0.70
→ **8 → 5 กอง vol สูงขึ้นแค่ ~3–4% แบบสัมพัทธ์ · 8 → 10 แทบไม่ต่าง** · และกองที่ momentum คัดมามักธีมเดียวกัน (M008: cluster ใหญ่สุด 45–63%) → ρ ในพอร์ตจริงสูงกว่า 0.49 → ส่วนต่างยิ่งเล็ก
→ ในช่วง 4–10 **จำนวนกองไม่ใช่คันโยกด้านความเสี่ยง** · สิ่งที่ N เปลี่ยนจริงคือ (ก) ความเข้มข้นของสัญญาณ (N เล็ก = เอาเฉพาะอันดับต้น) (ข) **ความเสี่ยงจากโชคของการเลือกกอง** (O'Neal: dispersion ปลายทาง) ซึ่งตรงกับอาการที่เราเห็น (กองเดียวขยับ Sharpe ~0.2)

### 1.3 ความไวต่อ N ของเรา อ่านอย่างไร
- Grinold (1989) fundamental law (อ้างใน M005 §2): IR ∝ IC·√breadth → N มากขึ้นช่วยถ้า IC ของอันดับลึกๆ ยังบวก · N น้อยดีกว่าเฉพาะเมื่อ IC กระจุกที่อันดับต้นจริง
- ผลเรา N5 > N10 > N8 **ไม่ monotonic** → ขัดกับทั้งสองเรื่องราว (ทั้ง "เข้มข้นดี" และ "กระจายดี") → อธิบายได้ดีที่สุดด้วย noise ของการเลือกกองไม่กี่ตัว · CI95% ของ Sharpe แต่ละตัวกว้าง ~±1.1 → ส่วนต่าง 0.46 อยู่ในช่วง noise
- **ข้อห้าม**: การเลือก N=5 จาก M005 = post-hoc selection (DSR ต้องนับ trial ทุกตัวในกริด) · การ "ทำ N ให้ dynamic" โดยมีพารามิเตอร์ที่ทำให้ได้ N ≈ 5 ช่วงที่ดี = overfit ในรูปใหม่

---

## ส่วนที่ 2 — วิธีกำหนด N แบบ dynamic: หลักฐาน ต้นทุน ความเสี่ยง overfit

| วิธี | หลักฐาน | ปัญหาเฉพาะกรณีเรา | สรุป |
|---|---|---|---|
| (1) เกณฑ์คะแนนขั้นต่ำ (SR12 > 0 / absolute momentum) + min/max | Antonacci (dual momentum, SSRN 2042750): absolute momentum ลด vol/drawdown มากกว่า relative momentum — ระดับ **สินทรัพย์/ดัชนี** · Keller & Keuning (DAA 2018): ใช้ "breadth" (จำนวนสินทรัพย์ momentum ไม่บวก) คุม **สัดส่วนเงินสด** ไม่ใช่จำนวนสินทรัพย์ | universe 160–310 family → กอง SR12 > 0 เกิน 10 เกือบทุกไตรมาส ยกเว้นขาลง → **ได้ N=10 คงที่แทบตลอด** · ขาลงมีครั้งเดียว · M006-TCA (12-1 < rf → เงินสด) ทำงานน้อยมาก (เงินสด 38% → 40%) และ Sharpe ลดลง · ถ้าตั้งเกณฑ์สูงกว่า 0 (เช่น z > 1) = ค่าไม่มีมาตรฐาน → tune | ไม่แนะนำ (ซ้ำกับ trend cash ที่มีแล้ว) |
| (2) ENB (Meucci) / Diversification ratio (Choueifaty) | Meucci (2009/2010): ENB = exp(entropy) ของสัดส่วนความเสี่ยงบนปัจจัยไม่สัมพันธ์ · รุ่น PCA ให้ผลกลับหัว (กองแทบไม่สัมพันธ์กันได้ ENB ≈ 1) → Meucci, Santangelo & Deguest (2015) แก้ด้วย minimum-torsion · ENB มักประเมินการกระจายเกินจริงเมื่อ universe มีความซ้ำซ้อนแฝง (portfoliooptimizer.io) · Choueifaty & Coignard (2008): DR = Σwᵢσᵢ / σ_p; DR² ตีความเป็นจำนวนเดิมพันอิสระ (Choueifaty et al. 2013) · งานเปรียบเทียบ: max-diversification/min-variance **ไวต่อ covariance ผิดมากที่สุด** | ต้องใช้ Σ ของกองที่ correlation ต่ำเกินจริง (async) → นับเดิมพันเกิน → เติมกองน้อยเกินไป · Σ 52 สัปดาห์ของ 10–20 กอง noisy · ไม่มีงานที่ใช้ ENB/DR เป็น **กติกาเลือก N** (ใช้เป็นตัววัด) | ใช้เป็น **diagnostic** ได้ดี · เป็นกติกา = หลักฐานอ่อน |
| (3) ถ่วงตามความแรงสัญญาณ แล้วตัดน้ำหนักต่ำ | ระดับหุ้นมีงาน signal-weighting แต่ DeMiguel, Garlappi & Uppal (2009 RFS): การใช้ค่าคาดหมาย return ประมาณจากอดีตแพ้ 1/N นอกตัวอย่าง — 25 สินทรัพย์ต้องใช้ข้อมูล > 3,000 เดือนจึงชนะ | ขัดกับ ERC (ทีมเลือก ERC เพราะ "Π ไม่มีสัญญาณ") · ระดับ SR12 ข้ามกองไม่เสถียร → น้ำหนักแกว่ง → turnover/ต้นทุนเพิ่ม · เกณฑ์ตัด (เช่น < 5%) ไม่มีค่ามาตรฐาน | ไม่ควรลอง |
| (4) optimizer มี cardinality / min-weight | DeMiguel et al. 2009 (ข้างบน): optimizer แบบใช้ค่าประมาณแพ้ 1/N เมื่อข้อมูลสั้น · cardinality = mixed-integer + ขึ้นกับ μ, Σ ทั้งคู่ | 45 เดือน, μ ไม่มีสัญญาณที่เชื่อได้ · ผลไวต่อ covariance ที่ bias | ไม่ควรลอง |
| (5) ปรับ N ตามภาวะตลาด (เช่น ขาลงถือมากขึ้น/น้อยลง) | ไม่พบงานที่เปิดอ่านได้ที่ทดสอบ "จำนวนสินทรัพย์ตามภาวะ" ใน long-only fund portfolio · งานใกล้เคียง (DAA, R002) ใช้ภาวะคุม **เงินสด** | ขาลงครั้งเดียวใน 45 เดือน (R002) → ทดสอบไม่ได้ · ซ้อนกับ trend cash | ไม่ควรลอง |
| (ไอเดีย 1) N-ensemble (เฉลี่ยพอร์ต N = 5…10) | ไม่มีงานเฉพาะ · หลักการ: เมื่อเลือกพารามิเตอร์ไม่ได้ทางสถิติ ให้เฉลี่ยข้ามพารามิเตอร์ (เทียบกับ 1/N robustness ของ DeMiguel et al. และ tranching ข้ามเวลา) · แนวคิด "parameter diversification / timing luck" ของ Newfound Research — **ยังไม่ยืนยันแหล่ง** (ไม่ได้เปิดอ่าน) | น้ำหนักลดตามอันดับ (อันดับ 1–5 อยู่ทุก N, อันดับ 10 อยู่แค่ N=10) → เข้มข้นที่ต้น + กระจายที่ท้าย · ไม่ต้องใช้ correlation | ทดสอบได้ 1 trial |

### ต้นทุน turnover ของ dynamic N (กลไก ไม่ใช่ตัวเลขจากงานวิจัย)
- N เพิ่มขึ้น → ต้องซื้อกองใหม่ → front-end ~1.5% บนน้ำหนักที่ซื้อ (TOP3: front-end คือต้นทุนเกือบทั้งหมด, Sharpe 0.89 → 0.71)
- N ลดลง → ขายกอง (back-end ส่วนใหญ่ 0) แต่ถ้า N กลับขึ้นไตรมาสถัดไป = ซื้อใหม่อีกรอบ → **whipsaw ของ N แพงกว่า whipsaw ของเงินสด** (เงินสดไม่มีต้นทุนขา `__CASH__` ตาม C7)
- ดังนั้นกติกา dynamic N ทุกแบบต้องมี hysteresis ทั้ง "ตัวกอง" และ "จำนวนกอง" — ไม่งั้นต้นทุนกินก่อนจะเห็นผล

---

## ส่วนที่ 3 — correlation ต่ำเกินจริงจาก NAV ไม่พร้อมกัน (asynchronous)

**ปัญหา (มุมใหม่จาก BRIEF จุดอ่อน #4–#5)**: NAV กองไทย FIF สะท้อนราคาตลาดปลายทางที่ปิดคนละเวลา (เอเชียปิดก่อน US) และบางกองใช้ราคา T−1 → return รายวัน/รายสัปดาห์ของกองหนึ่ง "ตามหลัง" อีกกอง → correlation ร่วมเวลา (lag 0) ต่ำเกินจริง และมี cross-autocorrelation ที่ lag 1
- Burns, Engle & Mezrich (1998, J. Derivatives): ราคาปิดต่างเวลา → return ดูเหมือนทำนายได้และ **correlation ถูกประเมินต่ำ** → เสนอ "synchronize" ราคา (abstract จากผลค้น — SSRN 403)
- Scholes & Williams (1977) / Dimson (1979): ใส่ return ตลาด lag/lead แล้ว **รวมสัมประสิทธิ์** แก้ beta ที่ bias จากการซื้อขายไม่ต่อเนื่อง (ผลค้น)
- Getmansky, Lo & Makarov (2004, JFE 74(3)): return ที่ "smoothed" (ราคาค้าง/ไม่สภาพคล่อง) มี serial correlation → vol ต่ำเกินจริง Sharpe สูงเกินจริง · มีโมเดล MA(2) ของ smoothing profile (ผลค้น + หน้า MIT)

**ผลต่อวิธีที่พึ่ง correlation ของเรา**: ERC (กองที่ ρ ต่ำหลอกได้น้ำหนักมากเกิน) · M005 dedupe ρ ≤ 0.85 (ปล่อยกองซ้ำผ่าน) · M008 cluster (แยกกลุ่มเกิน) · ENB/DR (นับเดิมพันเกิน → N ที่ "พอ" ต่ำเกินไป)

**วิธีแก้มาตรฐาน (เรียงจากง่าย)**
1. ใช้ความถี่ต่ำลง — ทีมใช้รายสัปดาห์แล้ว (C3) ซึ่งลด bias ได้บางส่วน · รายเดือนแก้ได้มากกว่าแต่ 52 สัปดาห์ = 12 จุดรายเดือน → ประมาณ Σ ไม่ได้ · ต้องหน้าต่าง 36 เดือนขึ้นไป (ชนกับประวัติกองที่สั้น)
2. **lead-lag adjustment แบบ Scholes–Williams/Dimson ในรูป covariance**: Σ_adj = Γ0 + Γ1 + Γ1ᵀ (Γ1 = cross-covariance lag 1 สัปดาห์) — ใช้ข้อมูลรายสัปดาห์เดิม ไม่เพิ่มพารามิเตอร์ (lag = 1 ตามมาตรฐาน) · ต้องตรวจว่า Σ_adj ยัง positive definite (ถ้าไม่ ให้ shrink ด้วย LW เดิม)
3. synchronize แบบ Burns–Engle–Mezrich (VAR + ราคาตลาดที่ยังเปิด) — ซับซ้อนเกินสำหรับ 45 เดือน → ไม่แนะนำ

---

## ส่วนที่ 4 — band / hysteresis บนเกณฑ์ (เข้าที่ค่าหนึ่ง ออกที่อีกค่า)
- Novy-Marx & Velikov (2016 RFS 29(1):104–147, 23 anomaly หุ้น US): **buy/hold spread เป็นวิธีลดต้นทุนแบบง่ายที่ได้ผลที่สุด** · กลยุทธ์ที่ turnover ข้างเดียว < 50%/เดือน ยังรอดหลังต้นทุนเมื่อใช้วิธีลดต้นทุน (abstract/ผลค้น NBER w20721)
- ทีมใช้แล้ว: K = 2N (top 8 เข้า / หลุด top 16) อ้าง NMV ใน spec C5 · ค่า buy/hold ที่แน่นอนในต้นฉบับ (เช่น ซื้อ decile 1 ถือจนหลุด quintile/decile ใด) **ยังไม่ยืนยันแหล่ง** (ไม่ได้เปิด PDF)
- ถ้าจะทำ dynamic N ด้วยเกณฑ์: ใช้หลักเดียวกัน "เข้าเข้มกว่าออก" กับ **ทั้งตัวกองและจำนวนกอง** — เช่น เพิ่ม N เมื่อสัญญาณชัด ลด N เฉพาะเมื่อกองหลุด K (ไม่ลดเพราะเกณฑ์ใหม่) · ค่ามาตรฐานที่ไม่ต้อง tune = ratio 2:1 แบบ K = 2N ที่ใช้อยู่ (อย่าสร้าง band ใหม่ที่มีพารามิเตอร์อิสระ)
- หลักฐานทีมเอง: M002-NOH (ไม่มี hysteresis) Sharpe −0.10, ต้นทุน 2.2%/ปี (TOP3) → band คือสิ่งที่พิสูจน์แล้วว่าสำคัญกว่าการเลือก N

---

## ส่วนที่ 5 — รายละเอียดต่อไอเดีย

### ไอเดีย 0 (diagnostic ไม่นับ trial) — correlation ปรับ lead-lag + DR² ของพอร์ตที่ถือ
| หัวข้อ | เนื้อหา |
|---|---|
| ไอเดีย + กลไก | ก่อนตัดสินใจเรื่อง N ต้องรู้ว่าพอร์ต 8 กองมี "เดิมพันอิสระ" กี่ตัวจริง · ถ้า ρ ปรับ lag แล้วสูงขึ้นมาก แปลว่า ERC/dedupe/cluster ทุกตัวประเมินการกระจายเกิน |
| หลักฐาน | แข็งว่า async ทำให้ ρ ต่ำ (BEM 1998; Scholes–Williams/Dimson; Getmansky et al. 2004) · DR² เป็นตัววัดมาตรฐาน (Choueifaty) |
| เข้ากับข้อมูลเรา | return รายสัปดาห์ ≤ t จาก `qctx.weekly_return_series` ที่มีแล้ว · ≥ 30 สัปดาห์ร่วม (เกณฑ์ ERC) · ใช้เฉพาะ holdings ที่บันทึกไว้ของ M004-TF-FX (ไม่ดู forward return) |
| ผลที่คาด | ไม่มีผลต่อ Sharpe (ไม่ใช่ trial) · ได้ตัวเลข: median ρ lag-0 vs ปรับ lag · DR² ต่อไตรมาส (เช่น 8 กองอาจเท่ากับเดิมพันอิสระ ~2–4 ตัว — **คาดการณ์ ไม่ใช่ข้อมูล**) |
| ต้นทุนเชิงสถิติ | 0 trial — แต่ห้ามใช้ผลไปเลือก N ที่ "ดี" ย้อนหลัง |
| ร่าง | "คำนวณ ρ_adj = corr จาก Γ0 + Γ1 + Γ1ᵀ ของ weekly return 52 สัปดาห์ ≤ t สำหรับคู่กองที่ถือแต่ละไตรมาส + DR² ของน้ำหนักจริง ทั้งแบบ lag-0 และแบบปรับ · รายงาน distribution ไม่รายงาน return" |

### ไอเดีย 1 — N-ensemble (เฉลี่ยพอร์ต top-N, N = 5…10)
| หัวข้อ | เนื้อหา |
|---|---|
| ไอเดีย + กลไก | เราเลือก N ทางสถิติไม่ได้ (CI กว้าง, ผลไม่ monotonic) → แทนที่จะเดิมพันกับ N เดียว ให้ถือค่าเฉลี่ยของทุก N ในกรอบผู้ใช้ (ใช้ 5–10 แทน 4–10 เพราะ 4 = จุด fallback) · ผลเชิงกลไก: น้ำหนักลดตามอันดับ (อันดับต้นได้มากสุด) โดยไม่ต้องประมาณ μ · ลดความเปราะ "กองเดียวขยับ Sharpe 0.2" เพราะกองชายขอบได้น้ำหนักน้อย |
| หลักฐาน | ไม่มีงานเฉพาะกองทุน · หลักการ robustness: DeMiguel et al. 2009 (กฎง่ายที่ไม่ประมาณค่าทนกว่า) · parameter averaging (Newfound — ยังไม่ยืนยันแหล่ง) · O'Neal 1997 (ลดความกระจายจากโชค) → **ปานกลาง–อ่อน** |
| เข้ากับข้อมูลเรา | ใช้ของเดิมทั้งหมด (SR12, family, hysteresis, ERC, cap, trend cash) · แต่ละ sub-portfolio N มี hysteresis K = 2N ของตัวเอง (ตาม C5) แล้วเฉลี่ยน้ำหนักหุ้น → ERC ทำในแต่ละ sub ก่อนเฉลี่ย (ไม่ต้อง Σ ของ 10 กองพร้อมกัน) |
| ผลที่คาด | ไม่มีตัวเลข Sharpe จากวรรณกรรม · ทิศทาง: Sharpe ใกล้ค่าเฉลี่ยของ N5…N10 (ไม่ใช่สูงสุด) · ความแกว่งของผลต่อการเปลี่ยนกองชายขอบลดลง · turnover ใกล้ N=10/K=20 (อาจต่ำกว่า N=8 เพราะ K ใหญ่สุด 20) · จำนวนกองจริง 5–10 |
| ต้นทุนเชิงสถิติ | **1 trial** · ไม่มีพารามิเตอร์ใหม่ (ช่วง N = กรอบผู้ใช้, K = 2N ตาม C5, เฉลี่ยเท่ากัน) · ห้ามถ่วงน้ำหนักข้าม N |
| ร่างสมมติฐาน | "น้ำหนักหุ้น = (1/6)·Σ_{N=5..10} w_N โดย w_N = พอร์ต M004-TF-FX ที่ N, K = 2N · trend cash ใช้กับผลรวม · จะได้ Sharpe ไม่ต่ำกว่า M004-TF-FX (paired Δ CI ไม่ต่ำกว่า −0.1) และ **ความไวต่อการตัดกองที่ contribution สูงสุด 1 กอง ลดลง**" · diagnostic หลัก = Sharpe เมื่อแทนกอง top contribution ด้วย B0 (plan §5 ข้อ 3) เทียบ base |

### ไอเดีย 2 — N จาก DR² ภายใน [6, 10] (ใช้ Σ ปรับ lead-lag)
| หัวข้อ | เนื้อหา |
|---|---|
| ไอเดีย + กลไก | ถ้ากองต้นๆ ธีมซ้ำ (ρ สูง) เดิมพันอิสระน้อย → เติมกองอันดับถัดไปจนการกระจายไม่เพิ่ม · ถ้ากองต้นๆ ต่างกันดี → ถือน้อยลงเพื่อความเข้มข้น · ต่างจาก M005 dedupe (ตัดกองซ้ำ = เสียกองอันดับดี) และ M008-GC (cap กลุ่ม) ตรงที่ **เพิ่ม** กองแทนการตัด |
| หลักฐาน | DR²/ENB เป็นตัววัดที่ยอมรับ (Choueifaty & Coignard 2008; Meucci 2010; Meucci et al. 2015) แต่ไม่พบงานที่ใช้เป็นกติกาเลือก N และชนะ fixed N นอกตัวอย่าง · max-diversification ไวต่อ Σ ผิด → **อ่อน–ปานกลาง** |
| เข้ากับข้อมูลเรา | ต้องใช้ Σ_adj ของไอเดีย 0 · ≥ 30 สัปดาห์ร่วม · noise ของ Σ 52 สัปดาห์สำหรับ 10 กองยังสูง |
| ผลที่คาด | ทิศทาง: N เฉลี่ยสูงขึ้นในไตรมาสที่ธีมกระจุก (2023-12 tech, 2024-06 India ตาม M008 §0) · ลด concentration แต่ M008-GC ชี้ว่าลดธีมที่ชนะทำให้ Sharpe ลด (Δ −0.17) → คาดผลเป็นกลางถึงลบ |
| ต้นทุนเชิงสถิติ | 1 trial · กติกาไม่ต้องมี threshold: เลือก N ∈ {6..10} ที่ DR²(ERC บน top-N) สูงสุด, เสมอ → N น้อยกว่า · N ลดได้เฉพาะเมื่อกองหลุด K (hysteresis ของจำนวน) · เสี่ยง overfit ที่นิยาม DR (ล็อก Choueifaty DR² ห้ามสลับ ENB) |
| ร่างสมมติฐาน | "ณ t จัดอันดับ SR12 + hysteresis เหมือนเดิม แต่ N_t = argmax_{N∈[6,10]} DR²(ERC_N; Σ_adj) จะลดน้ำหนักธีมสูงสุดโดยไม่ลด Sharpe" · **ทำเฉพาะเมื่อไอเดีย 0 พบว่า ρ_adj สูงกว่า ρ lag-0 อย่างชัด** (ไม่งั้นไม่มีเหตุผลเชิงกลไก) |

---

## ไอเดียที่ไม่ควรลอง (และเหตุผล)
| ไอเดีย | เหตุผล |
|---|---|
| เลือก N=5 (หรือ N ใดๆ) จากผล M005 / รัน grid N เพิ่ม | post-hoc · ผลไม่ monotonic = noise · DSR ต้องนับทุกจุดในกริด · spec M005 §5 ระบุเองว่า Δ > 0.3 = ไม่เสถียร |
| เกณฑ์ SR12 > 0 / absolute momentum รายกองเป็นตัวกำหนด N | กองที่ผ่านมีเกิน 10 เกือบตลอด → ได้ N=10 คงที่ · M006-TCA (ตัวกรองรายกอง → เงินสด) ทำงานน้อยและไม่ช่วย · เกณฑ์ > 0 ไม่มีค่ามาตรฐาน |
| ถ่วงน้ำหนักตามระดับ SR12 แล้วตัดน้ำหนักต่ำ | แทน ERC ที่พิสูจน์แล้ว (+0.04) ด้วยการใช้ μ ที่ noisy (DeMiguel et al. 2009) · น้ำหนักแกว่ง → turnover/front-end 1.5% |
| optimizer ที่มี cardinality / min-weight / max-diversification | ต้องการ μ และ Σ ที่แม่น · ข้อมูล 45 เดือน + Σ bias จาก async · ผลไวต่อ covariance ผิดมากที่สุด |
| N ตามภาวะตลาด (bull ถือน้อย / bear ถือมาก หรือกลับกัน) | ไม่มีหลักฐานที่เปิดอ่านได้ · ขาลง 1 ครั้ง (R002) · ซ้อนกับ trend cash ที่เป็นตัวคุมภาวะอยู่แล้ว |
| ENB แบบ PCA (Meucci 2009 รุ่นแรก) | ให้ผลกลับหัวเมื่อสินทรัพย์ไม่สัมพันธ์กัน · ถ้าจะวัดให้ใช้ minimum-torsion หรือ DR² |
| synchronize ราคาแบบ BEM (VAR) | ซับซ้อนเกิน · ประมาณค่าจาก 45 เดือนไม่นิ่ง · lead-lag lag 1 ให้ประโยชน์ส่วนใหญ่ด้วยต้นทุนน้อยกว่า |

## ตอบตรงๆ: dynamic N ดีกว่า fixed N หรือไม่
- **ไม่พบหลักฐานที่เปิดอ่านได้ว่า dynamic N ให้ Sharpe สูงกว่า fixed N นอกตัวอย่าง** ในพอร์ตกองทุน long-only · วรรณกรรมเรื่องจำนวนกองบอกแค่ว่า "เกิน ~4–6 กองประโยชน์การกระจายน้อยลงมาก" ซึ่งทั้งช่วง 4–10 ผ่าน
- dynamic N ส่วนใหญ่ **เปลี่ยนรูปแบบความเสี่ยง** (ความเข้มข้นแปรตามเวลา, tracking ต่อ universe แปรตามเวลา) + **เพิ่ม turnover** · ในกรณีเราที่ front-end คือต้นทุนหลัก ผลสุทธิมีแนวโน้มเป็นลบถ้าไม่มี hysteresis ของจำนวนกอง
- สิ่งที่ข้อมูลเราบอกจริง (ความไวสูงต่อ N และต่อกองเดียว) คือ **ปัญหาความเปราะของการเลือก** → แก้ด้วยการเฉลี่ย (ไอเดีย 1) ไม่ใช่ด้วยการหา N ที่ดีที่สุด
- เป้า 0.95: ไม่มีอะไรในหัวข้อนี้ที่คาดว่าจะเพิ่ม Sharpe ระดับ +0.2 อย่างเป็นระบบ

## ทดสอบอะไรได้จริงด้วยข้อมูล 45 เดือน (งบ ≤ 2 trials)
- **ทดสอบได้**: ไอเดีย 0 (diagnostic, 0 trial) · ไอเดีย 1 (1 trial) · ไอเดีย 2 (1 trial, มีเงื่อนไข) — เกณฑ์ผ่านควรเป็น "ไม่แย่ลง + ความเปราะลด/การกระจายเพิ่มตามกลไก" ไม่ใช่ "Sharpe ดีขึ้นอย่างมีนัย" (CI ~±1.1 กว้างกว่าผลที่คาด)
- **ค่ามาตรฐานแทนการ tune**: ช่วง N = กรอบผู้ใช้ (5–10) · K = 2N (NMV, C5 เดิม) · lag = 1 สัปดาห์ (Scholes–Williams/Dimson) · DR² ของ Choueifaty (ไม่ใช่ ENB PCA) · ≥ 30 สัปดาห์ร่วม (เดิม) · ล็อกใน spec ก่อนรัน ห้ามรัน sensitivity ภายใต้ชื่อเดียวกัน
- **พิสูจน์ไม่ได้**: "N ไหนดีที่สุด" · "dynamic N ป้องกันขาลง"

## คำแนะนำถึง quant-modeler
1. **ทำไอเดีย 0 ก่อน (0 trial)** — ใช้ holdings ที่บันทึกแล้ว ไม่ดู return ไปข้างหน้า · ผลนี้กระทบ ERC/M005 dedupe/M008 cluster ด้วย ควรรายงานแยก
2. **ไอเดีย 1 (1 trial)** เป็นตัวหลักของ R003 · base = M004-TF-FX (ไม่ผสม M009 ที่ไม่ผ่าน) · รายงาน paired Δ + CI, จำนวนกองเฉลี่ย, turnover/cost bp ที่ค่าธรรมเนียมจริง, diagnostic ตัดกอง top contribution
3. ไอเดีย 2 (1 trial) **เฉพาะเมื่อ** ไอเดีย 0 พบ ρ_adj สูงกว่า lag-0 ชัด และผู้ใช้อนุมัติ trial ที่ 2 · ไม่รวมกับไอเดีย 1 ใน trial เดียว
4. รวม ≤ 2 trial (n_trials สะสม ~22–23 หลัง M009 = 21) · ถ้าไอเดีย 0 ทำให้ต้องเปลี่ยน Σ ใน ERC ด้วย = trial แยกอีกตัว ให้ผู้ใช้ตัดสินก่อน

## ต้องให้ผู้ใช้ตัดสินใจ
1. ยอมรับไหมว่าเป้าของหัวข้อนี้คือ **"ลดความเปราะต่อการเลือก N/กองเดียว"** ไม่ใช่ "หา N ที่ให้ Sharpe สูงสุด" (และยอมรับว่า N=5 จาก M005 ใช้อ้างไม่ได้)
2. ช่วง N ใน ensemble ใช้ **5–10** (ตัด 4 เพราะเป็นจุด fallback) หรือ 4–10 ตามกรอบเดิม — ตัดสินก่อนรัน ห้ามรันทั้งสองแบบ
3. ถ้าไอเดีย 0 พบ correlation ต่ำเกินจริงมาก จะให้แก้ Σ ใน ERC ของ Trend 25 (กระทบโมเดลที่นำเสนอ + เป็น trial ใหม่) หรือแค่เปิดเผยเป็นข้อจำกัด

## บรรณานุกรม
| ผู้แต่ง (ปี) | ชื่อเรื่อง | URL | ป้าย |
|---|---|---|---|
| Statman, M. (1987) JFQA | How Many Stocks Make a Diversified Portfolio? | https://www.cambridge.org/core/journals/journal-of-financial-and-quantitative-analysis/article/abs/how-many-stocks-make-a-diversified-portfolio/CE5CDF2C7225FC1E0EDE3E700A3C66A7 | ผลค้น/abstract (30/40 หุ้น) |
| Statman, M. (2004) FAJ | The Diversification Puzzle | — | ผลค้นเท่านั้น (> 300 หุ้น) · ยังไม่ยืนยันแหล่ง |
| Domian, Louton & Racine (2007) Financial Review | Diversification in Portfolios of Individual Stocks: 100 Stocks Are Not Enough | https://onlinelibrary.wiley.com/doi/abs/10.1111/j.1540-6288.2007.00183.x | ผลค้น (ชื่อเรื่อง) |
| O'Neal, E. (1997) FAJ 53(2):37–46 | How Many Mutual Funds Constitute a Diversified Mutual Fund Portfolio? | https://www.tandfonline.com/doi/abs/10.2469/faj.v53.n2.2070 | abstract จากผลค้น (T&F 403) · ตัวเลขย่อยจาก https://www.theskilledinvestor.com/wp/how-many-mutual-funds-are-needed-for-a-well-diversified-portfolio-evidence-168.htm (เปิดอ่าน — แหล่งรอง) |
| Brands, S. & Gallagher, D. (2005) Accounting & Finance | Portfolio selection, diversification and fund-of-funds: a note | https://onlinelibrary.wiley.com/doi/abs/10.1111/j.1467-629x.2004.00130.x | ผลค้นเท่านั้น (~6 กอง) · Wiley/RG 403, PDF UNSW แปลงไม่ได้ · **ยังไม่ยืนยันแหล่ง** |
| Louton, D. & Saraoglu, H. (2008) J. Investing 17(3):47–63 | How Many Mutual Funds Are Needed to Form a Well Diversified Asset Allocated Portfolio? | https://www.researchgate.net/publication/240315811 | ผลค้นเท่านั้น (≥ 10 กอง) · ยังไม่ยืนยันแหล่ง |
| Vanguard (2024) | Combining active managers: a practical approach | https://corporate.vanguard.com/content/dam/corp/research/pdf/combining_active_managers_a_practical_approach.pdf | PDF แปลงไม่ได้ · ยังไม่ยืนยันแหล่ง |
| NISA | The Siren Song of Manager Diversification | https://www.nisa.com/perspectives/the-siren-song-of-manager-diversification/ | เปิดไม่ได้ (DNS) · ยังไม่ยืนยันแหล่ง |
| Meucci, A. (2009/2010) | Managing Diversification | https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1358533 | abstract จากผลค้น |
| Meucci, Santangelo & Deguest (2015) | Risk Budgeting and Diversification Based on Optimized Uncorrelated Factors (minimum-torsion) | https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2276632 | ผลค้น |
| portfoliooptimizer.io | The Effective Number of Bets: Measuring Portfolio Diversification | https://portfoliooptimizer.io/blog/the-effective-number-of-bets-measuring-portfolio-diversification/ | เปิดอ่าน (แหล่งรอง — ปัญหา PCA, overestimation) |
| Choueifaty, Y. & Coignard, Y. (2008) JPM 35(1):40 | Toward Maximum Diversification | https://jpm.pm-research.com/content/35/1/40.abstract | ผลค้น |
| Choueifaty, Froidure & Reynier (2013) J. Investment Strategies 2(2) | Properties of the Most Diversified Portfolio | https://www.tobam.fr/wp-content/uploads/2021/07/2013-choueifatyfroidurereynier-properties-of-the-most-diversified-portfolio-jis.pdf | ผลค้นเท่านั้น (การตีความ DR² = จำนวนเดิมพันอิสระ — **ยังไม่ยืนยันแหล่ง** จากต้นฉบับ) |
| DeMiguel, Garlappi & Uppal (2009) RFS 22(5):1915–1953 | Optimal Versus Naive Diversification: How Inefficient is the 1/N Portfolio Strategy? | https://academic.oup.com/rfs/article-abstract/22/5/1915/1592901 | abstract จากผลค้น (> 3,000 เดือนสำหรับ 25 สินทรัพย์) |
| Burns, Engle & Mezrich (1998) J. Derivatives 5(4) | Correlations and Volatilities of Asynchronous Data | https://papers.ssrn.com/sol3/papers.cfm?abstract_id=64188 | abstract จากผลค้น (SSRN 403) |
| Dimson, E. (1979) JFE / Scholes & Williams (1977) JFE | Risk measurement when shares are subject to infrequent trading / Estimating betas from nonsynchronous data | https://www.semanticscholar.org/paper/Risk-measurement-when-shares-are-subject-to-trading-Dimson/3beb84cbfffc2478b048f16b281ba21467ddc59f | ผลค้น (วิธีรวม lead/lag) |
| Getmansky, Lo & Makarov (2004) JFE 74(3):529–609 | An Econometric Model of Serial Correlation and Illiquidity in Hedge Fund Returns | https://www.nber.org/papers/w9571 | ผลค้น |
| Novy-Marx, R. & Velikov, M. (2016) RFS 29(1):104–147 | A Taxonomy of Anomalies and Their Trading Costs | https://www.nber.org/papers/w20721 | abstract จากผลค้น · ค่า buy/hold ที่แน่นอนยังไม่ยืนยันแหล่ง |
| Antonacci, G. (2012/2017) | Risk Premia Harvesting Through Dual Momentum | https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2042750 | abstract จากผลค้น |
| Keller, W. & Keuning, J. W. (2018) | Breadth Momentum and the Canary Universe: Defensive Asset Allocation (DAA) | https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3212862 | abstract จากผลค้น |
| Grinold, R. (1989) JPM | The Fundamental Law of Active Management | — | อ้างจาก spec M005 · ไม่ได้เปิดอ่าน · ยังไม่ยืนยันแหล่ง |
| Newfound Research | parameter diversification / rebalance timing luck | https://blog.thinknewfound.com/tag/terminal-wealth-dispersion/ | เห็นในผลค้น ไม่ได้เปิด · **ยังไม่ยืนยันแหล่ง** |

## สิ่งที่ยังไม่ได้ทำ / ข้อจำกัดของรายงานนี้
- **PDF เต็มเปิดไม่ได้เกือบทั้งหมด** (WebFetch แปลง PDF ไม่ได้, ไม่มี pdftoppm, Wiley/T&F/SSRN/ResearchGate 403) → ตัวเลข Brands & Gallagher, Louton & Saraoglu, Vanguard, NMV buy/hold ยังไม่ยืนยันจากต้นฉบับ
- ไม่มี Glob ใน session นี้ → ไม่ได้ list `specs/` ทั้งหมด (อ่านเฉพาะ 3 spec ที่สั่ง + R001/R002 + TOP3)
- ยังไม่ได้ค้น: งาน fund-of-funds ในตลาดเกิดใหม่/ไทย, งาน concentrated vs diversified momentum (จำนวนหลักทรัพย์ใน long-only momentum), งาน hierarchical/cluster-based N, งานเปรียบเทียบ ENB-targeting โดยตรง
- ตัวเลข vol ใน §1.2 เป็นเลขคณิตจาก ρ = 0.49 ใน BRIEF (สมมติ vol เท่ากัน) ไม่ใช่ผลจากข้อมูลพอร์ต
- ไม่พบข้อความในหน้าเว็บที่พยายามสั่งงาน (ไม่มี prompt injection)
