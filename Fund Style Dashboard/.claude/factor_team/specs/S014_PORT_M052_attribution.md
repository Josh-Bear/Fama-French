# S014_PORT — อธิบายพอร์ต M052 ด้วย factor ของ F5-EO (spec ลงทะเบียนล่วงหน้า · ส่วน (ก) ของงาน PORT-FX)

ผู้เขียน: factor-designer · วันที่ 2026-10-24 · งาน **PORT-FX ส่วน (ก)** (BRIEF 122) · **เชิงอธิบาย · ไม่นับ trial · ไม่แตะ `factor_team/trials.csv` และ `quant_team/trials.csv`** · สถานะ: รอรีวิว spec
ส่วน (ข) (กติกาคุมความเสี่ยงตอนเลือกกอง) **ยังไม่อยู่ใน spec นี้** — เขียนหลังเห็นผลส่วน (ก) (จุดหยุดของ BRIEF 122)

อ้างอิง (อ่านครบ): BRIEF 108–122 · `reports/L1EO_summary.md` (รวม Addendum BRIEF 121) · spec S012 + S013 · `runs/S012/results.md` · `lib/l1eo.py` · `data/QA_GOLD.md` · `data/QA_FRIDAY_GAP.md` ·
`base_data/reference/m052_frontier_holdings.csv` / `_weekly.csv` / `_realized.csv` (อ่านอย่างเดียว) · `quant_team/specs/M051_canary_real_bond.md` · `quant_team/backtest/run_r6.py` (`make_xfun` · `export_m052`) · `quant_team/backtest/frontier_export.py` (`holdings_weekly`) · `quant_team/backtest/results/EXPORT_m052_*`
การตรวจของ designer: `scratch/factor-designer_s014_structure.py` → `.csv` (จำนวนแถวที่มีผลตอบแทนของ holding ต่อหน้าต่าง · notna เท่านั้น · ไม่ fit)
**การเปิดเผย:** ตอนอ่านโครงไฟล์ designer เห็นแถวแรกของ `m052_frontier_realized.csv` (MVP / max Sharpe / ERC ของไตรมาส 2022-03-31 · ผลตอบแทนไตรมาสราว −8%) และตัวเลขสรุปของ M052 ใน `EXPORT_m052_metrics.csv` (Sharpe 1.53 · CAGR 19.8% · MaxDD −11.3% ซึ่งรู้กันอยู่แล้วจากงาน quant) · ไม่ได้เปิดผลตอบแทนรายกองหรือ factor ช่วงถือ · ความคาดหมายข้อ 9 ไม่ใช้ตัวเลขเหล่านี้

> **ป้ายบังคับ (ทุกตารางผล):**
> (P1) **เชิงอธิบาย** — exposure / ที่มาผลตอบแทนของพอร์ตที่สร้างแล้ว ไม่ใช่การทำนาย · factor ส่วนใหญ่ลงทุนไม่ได้ (long–short / ส่วนตั้งฉาก)
> (P2) **ช่วง 2022-04 → 2025-12 คือช่วงเดียวกับที่ทีม quant ใช้เลือก M052** → ผลไม่ใช่หลักฐานอิสระ
> (P3) **ชุด factor (MKT · FX · CMA) ถูกคัดใน S012 ด้วยข้อมูล 2021–2023** → ไตรมาสที่ถือก่อน 2024 มี look-ahead ของ "การเลือกชุด" (β ยังประมาณด้วยข้อมูล ≤ t)
> (P4) **NAV ศุกร์ขาด (BRIEF 121):** ตั้งแต่ ธ.ค. 2023 กองที่ NAVDate = AsOfDate ไม่มี NAV วันศุกร์ (asof ตกวันพฤหัส · เหลื่อมจาก factor ศุกร์) — holding ที่โดน: **K-GOLD-A(A)** (ถือ 6 ไตรมาสในช่วงช่องว่าง) · **TISCOCH** (ถือ 2025-Q2) · ช่วงก่อนช่องว่าง (FCSCBSETE · TISCOJP · BGOLD · SCBGOLDHP) ไม่โดนตอนถือ แต่หน้าต่างประมาณ β ของไตรมาสหลัง 2023-12 มีสัปดาห์ช่องว่างปน
> (P5) **ไม่ใช่คำแนะนำการลงทุน** · ห้ามใช้เลือกกอง

---

## 0. ข้อเท็จจริงเชิงโครงสร้าง (designer อ่านเอง)

**0.1 โครงของ M052** (`run_r6.py` · `frontier_export.holdings_weekly`)
- M052-STACK-AGG = M033 (FEE0 + SIW + BAND5 · ขาหุ้น E) + **CANARY** (สัญญาณ MSCI EM + AGG) + **VSL** (ตัวคูณความผันผวน) · offset 0 · ตัดสินใจสิ้นไตรมาส t · ซื้อ e = t + 2 วันทำการ · buy-and-hold ทั้งไตรมาส
- **สัดส่วนหุ้น x** = max(0.25, min(GC75[k] × VSL, 1 − b/2)) (k = สัญญาณ GC · b = สัญญาณ CANARY 0–2) · ส่วนที่เหลือ 1 − x ไป**กองทอง 1 กอง** (kind = G) · **CANARY และบอนด์ AGG เป็นสัญญาณเท่านั้น ไม่ได้ถือ** · ไม่มีขาเงินสด / บอนด์ / ตลาดเงิน (แผนมี assert ว่าไม่มี `__CASH__` และขาตั้งรับ ≤ 1 กองต่อไตรมาส)
- holding: **15 ไตรมาส** (t = 2022-03-31 → 2025-09-30) · **58 แถว** (E 45 · G 13) · **Σw = 1 ทุกไตรมาส** · กอง E 3 กองต่อไตรมาส · x_model 0.25–1.0
- ไฟล์อ้างอิง (sha256): holdings `b877510f177bc5a113b6587393dbdc543c63f033d9573a169172e403658e233d` · weekly `2e1ccdbae5a646e8ec633b786e560f827648c82ddc001d1c99fe04824c6e7600` (ผลตอบแทน 52 สัปดาห์**ย้อนหลัง ≤ t** ของ holding — ไม่มีช่วงถือ) · realized `488c38e5d0f749979ceaa49a682cd792e2710dbfffd8dd319427dda0ad1efe43` (ผลจริงรายไตรมาส · แถว `portfolio = ERC (กติกาโมเดล)` = น้ำหนักเท่า holdings) · `EXPORT_m052_curves.csv` `714b4dad…` · `EXPORT_m052_metrics.csv` `76c6b661…`

**0.2 การจับคู่ holding → หน่วยของ panel** (24 รหัส · `scratch/factor-designer_s014_structure.csv`)

| holding | kind | หน่วย panel | วิธีจับคู่ | ใน U | factor กลุ่ม / ชุด | ไตรมาสที่ถือ |
|---|---|---|---|---|---|---|
| ASP-NGF | E | ASP-NGF | รหัสเดียวกัน | U_E | e_JAPAN | 6 |
| ASP-VIET | E | ASP-VIET | เดียวกัน | U_E | e_VIETNAM | 1 |
| B-BHARATA | E | B-BHARATA | เดียวกัน | U_E | e_INDIA (คำพ้อง BHARAT · 115(6)) | 2 |
| DAOL-GOLD | E | DAOL-GOLD | เดียวกัน | U_E | **ไม่มี** (ป้าย METAL) → ภาคผนวก P-A | 3 |
| FCSCBSETE | E | FCSCBSETE | เดียวกัน | U_E | **ไม่มี** (ป้าย TH · กองดัชนี SET) → ภาคผนวก P-A | 3 |
| K-EUX | E | K-EUX | เดียวกัน | U_E | e_EUROPE | 3 |
| K-GINFRA-A(D) | E | K-GINFRA-A(D) | เดียวกัน | U_E | e_IGF | 1 |
| **KKP GINFRAEQ-H-F** | E | KKP GINFRAEQ-H | **ตัวแทน family** (class F ไม่อยู่ใน panel) | U_E | e_IGF | 4 |
| KKP TECH-H | E | KKP TECH-H | เดียวกัน | U_E | e_IT | 2 |
| KT-INDIA-A | E | KT-INDIA-A | เดียวกัน | U_E | e_INDIA | 4 |
| **LHJAPE-A** | E | LHJAPE-A | เดียวกัน | **ไม่อยู่ใน U_E** | e_JAPAN (กฎชื่อเดียวกัน: "LH JAPAN - E FUND") | 1 |
| **ONE-INDIAOPP-IA** | E | ONE-INDIAOPP-RA | **ตัวแทน family** | **ไม่อยู่ใน U_E** | e_INDIA (กฎชื่อ: "ONE INDIA OPPORTUNITY") | 1 |
| **PRINCIPAL GOPP-C** | E | PRINCIPAL GOPP-A | **ตัวแทน family** | U_E | ไม่มี (GLOBAL) | 1 |
| TBIOTECH | E | TBIOTECH | เดียวกัน | U_E | e_HC | 1 |
| TISCOCH | E | TISCOCH | เดียวกัน | U_E | e_CHINA(grp) | 1 |
| TISCOJP | E | TISCOJP | เดียวกัน | U_E | e_JAPAN | 1 |
| TNEXTGEN-A | E | TNEXTGEN-A | เดียวกัน | U_E | e_ARKK | 2 |
| TUSEQ-UH | E | TUSEQ-UH | เดียวกัน | U_E | e_USA | 4 |
| TUSFIN-A | E | TUSFIN-A | เดียวกัน | U_E | e_USA | 3 |
| UCI | E | UCI | เดียวกัน | U_E | e_CHINA(grp) | 1 |
| K-GOLD-A(A) | G | K-GOLD-A(A) | เดียวกัน | U_O | **ชุดทอง: GOLD_XS + FX** | 10 |
| BGOLD | G | BGOLD | เดียวกัน | U_O | GOLD_XS + FX | 1 |
| **SCBGOLDHP** | G | SCBGOLDHP | เดียวกัน | **ไม่อยู่ใน U_O** (AUM) | GOLD_XS + FX (กฎเดียวกับกองทอง) | 2 |

- ทุก holding มีผลตอบแทนใน panel ≥ 64 สัปดาห์ก่อน t (ไตรมาสแรก 64 · ภายหลังถึงเพดาน 156) และครบทุกสัปดาห์ของช่วงถือ (13–14 สัปดาห์ต่อไตรมาส)
- class ต่างใช้ผลตอบแทนของตัวแทน family (ค่าธรรมเนียมต่างกัน → ส่วนต่างเข้า "ส่วนต่างจากผลทางการ" ข้อ 4.4) · ป้าย "class ต่าง"

---

## 1. คำถามและสมมติฐาน

**คำถาม:** (Q1) พอร์ต M052 มี exposure ต่อ factor ใดบ้างในแต่ละไตรมาส · (Q2) ความเสี่ยงของพอร์ตกระจุกที่ factor ใด · (Q3) ผลตอบแทนจริงมาจาก factor ใด (ตลาดโลก · FX · CMA · ทอง · factor กลุ่ม · ส่วนที่เหลือ) ทั้งรายไตรมาส รวม และ**ปี 2022** (จุดอ่อนขาลง)

| # | สมมติฐาน (ความคาดหมายตรวจตัวเอง · ไม่ใช่เกณฑ์) |
|---|---|
| H1 | exposure ต่อ MKT ของพอร์ตเดินตาม x_model (สัดส่วนหุ้น) · ขาทองทำให้ GOLD_XS เป็นแหล่งความเสี่ยงหลักในไตรมาสที่ x ต่ำ |
| H2 | ขาหุ้น 3 กองต่อไตรมาสทำให้ factor กลุ่ม (ประเทศ / ธีม) เป็นแหล่งความเสี่ยงสำคัญอันดับรองในไตรมาสที่ x สูง |
| H3 | ส่วนที่ factor อธิบายไม่ได้ (ε) ของพอร์ตเล็กกว่ากองรายตัว เพราะขาทอง (R² สูงรายเดือน) ครองน้ำหนักบ่อย |

---

## 2. ข้อมูล (ตรวจ sha256 เต็มก่อนรัน · ไม่ตรง → หยุด)

| ไฟล์ | ใช้ทำ | sha256 |
|---|---|---|
| `data/panel_weekly.parquet` | ผลตอบแทนรายสัปดาห์ของหน่วย | `95c16ee651d3a936788b7cb3c6372bbf5f1e84cb39daf5680343771dca24270b` |
| `data/factors_weekly.parquet` | MSCI · RF_BOT · SHV_THB · SHV_USD · TDEX | `115b87139d2bec0fd57a77a1593c46d36bb23f3f35f83236cdb07be642af47a8` |
| `data/factors_ext_weekly.parquet` | ARKK · IGF (THB) | `3105b6e7fe32ffd3648e8feac8dbd03a8db22b7e8eb245c5faf462b14da5e296` |
| `data/factors_eo_noaqr_weekly.parquet` (**ไม่มี AQR** · BRIEF 120–122) | KF_DEV_CMA · GLD_USD | `715b4b252235b49b155c9d53554c00380d4d4430eb5c2c2e25751a3678570b3a` (`manifest_eo_noaqr.json` `6be080b1…76c9`) |
| `data/universe.csv` · `specs/S012_group_map.csv` · `base_data/FundProfile.csv` | family / ตัวแทน · factor กลุ่ม · ชื่อ | `fdfb7830…7252` · `898a86867b3f832060f7620d039fd95338d24e1bb71f531d76bb58004223fceb` · `9516281426fc854c8f3a0833f119cad0ce581adb39450732e579084cb4cedfaf` |
| `base_data/reference/m052_frontier_holdings.csv` / `_realized.csv` (อ่านอย่างเดียว) | น้ำหนัก · ผลจริงทางการ | ข้อ 0.1 |
| `quant_team/backtest/results/EXPORT_m052_curves.csv` (อ่านอย่างเดียว) | เส้นมูลค่าพอร์ตจริง (ค่าธรรมเนียมจริง · case full) | `714b4dada62432e8d4fc18af0844a09e4491a9805a9fae9fc0f929b5f88a1bdb` |

ห้ามใช้: คอลัมน์ AQR (assert) · `manifest_eo.json` / `factors_eo_*.parquet` เดิม · `cache/` ของแอป · แถว > 2025-12-26 · `load_nav_history`

---

## 3. วิธี

### 3.1 ชุด factor (นิยามเดียวกับ S012 · ทุกตัวเป็นผลตอบแทนส่วนเกินหรือส่วนต่าง)
- **ขา E (E-X2):** MKT = `MSCI_ACWI − RF_BOT` · FX = `SHV_THB − RF_BOT` · CMA = `KF_DEV_CMA` · factor กลุ่ม e_g ≤ 1 ตัวต่อกองตาม `S012_group_map.csv` (กองนอก map ใช้ `l1eo.apply_name_rules` กติกาเดียวกัน · ข้อ 0.2) · I_g ตาม S012 ข้อ 3.2 (China All · Asia ex Japan · Europe · USA · Japan · Vietnam · India · ACWI HC · ACWI IT · ARKK · IGF) · กติกา e_AH ไม่ใช้ (e_CHINA ไม่อยู่ในชุดร่วม)
- **ขาทอง (kind G):** GOLD_XS = `GLD_USD − SHV_USD` · FX (ชุด O-X ทองของ S012)
- **factor ของพอร์ตต่อไตรมาส** = ยูเนียนของ {MKT · FX · CMA · GOLD_XS · e_g ของกลุ่มที่ถือ}

### 3.2 β รายกอง ณ วันตัดสินใจ t (ข้อมูล ≤ t เท่านั้น · ไม่ใช้ β ทั้งช่วง)
- **หน้าต่าง:** สัปดาห์ (anchor ศุกร์) ที่ ≤ t และ > t − 156 สัปดาห์ · ต้องมีผลตอบแทนของหน่วย ≥ 52 แถว (ทุก holding ผ่าน · ข้อ 0.2) · ข้อมูลเริ่ม 2021-01-08 → ไตรมาสแรก ๆ เป็นหน้าต่างขยาย (64–155 แถว) · ตั้งแต่ 2023-12-29 เป็น rolling 156
- **ตั้งฉาก factor กลุ่ม ณ t:** e_g,t = I_g − b̂′[MKT, FX, CMA] โดย b̂ ประมาณจาก**หน้าต่างเดียวกันของไตรมาสนั้น** (`l3.residualize` · lag 0 · เก็บค่าคงที่) → ใช้ b̂ นี้สร้าง e_g ทั้งในหน้าต่างและในช่วงถือของไตรมาสนั้น (b̂ ใหม่ทุกไตรมาส)
- **regression รายกอง:** Dimson lag 1 (`regress.fit_funds` · HAC L = 4) · ได้ α, b0, b1, **β = b0 + b1**, ความแปรปรวน residual σ²_ε (ในหน้าต่าง)
- min_obs = 52 · ถ้า fit ไม่ได้ (ไม่ควรเกิด) → ใช้ median β ของกอง U_E ในกลุ่มเดียวกันจากหน้าต่างเดียวกัน + ธง `beta_fallback` (ไม่ลองวิธีอื่น)

### 3.3 exposure และการกระจุก (ณ t)
- **exposure ของพอร์ต** B_k,q = Σ_i w_i,q β_ik,q (w = น้ำหนักเป้าหมายใน holdings · Σw = 1) · รายงานคู่ x_model · สัดส่วนน้ำหนักต่อกลุ่ม · HHI ของน้ำหนัก
- **ความแปรปรวนที่คาด (รายสัปดาห์):** V_q = B′Σ_f B + Σ_i w_i² σ²_ε,i · Σ_f = covariance ของ factor (lag 0) ในหน้าต่างเดียวกัน · ส่วนเฉพาะตัวสมมติว่าอิสระข้ามกอง (ป้าย: กองกลุ่มเดียวกันอาจสัมพันธ์กัน)
- **การกระจุก (Euler):** share_k = B_k (Σ_f B)_k / V_q · share_ε = Σ w² σ²_ε / V_q · รายงานเป็น % ของ V_q และของส่วน systematic · factor ที่ครองสูงสุด · ความผันผวนรายปีที่คาด √(52 V_q)

### 3.4 attribution ผลตอบแทนจริง (ช่วงถือของไตรมาส q)
- **สัปดาห์ช่วงถือ** = anchor ใน (t_q, t_{q+1}] (ไตรมาสสุดท้าย → ถึง 2025-12-26) · ประมาณช่วงถือจริง (e → e ถัดไป) ด้วยสัปดาห์ศุกร์
- **น้ำหนักลอย (buy-and-hold):** w_i,s = w_i,q Π(1 + r_i) ของสัปดาห์ก่อนหน้าในไตรมาส แล้ว normalize (Σ = 1 ทุกสัปดาห์)
- **เอกลักษณ์รายสัปดาห์ (lens หลัก L1):** r_p,s − rf_s = Σ_i w_i,s−1 (r_i,s − rf_s) = Σ_k C_k,s + A_s + E_s · C_k,s = Σ_i w_i,s−1 (b0_ik f_k,s + b1_ik f_k,s−1) · A_s = Σ_i w_i,s−1 α_i · E_s = ส่วนที่เหลือ (นอกหน้าต่าง) · ต้องเท่ากันพอดี (1e-12)
- **รวมต่อไตรมาส** = ผลรวมเลขคณิตของสัปดาห์ · รายงาน: ตลาดโลก (MKT) · FX · CMA · ทอง (GOLD_XS) · **แต่ละ factor กลุ่ม** · α · ε · ผลรวม · คู่กับผลตอบแทนพอร์ตแบบทบต้น
- **lens ทนทาน L2 (รายไตรมาส · ลดผลของเวลาตีราคา · BRIEF 121(4)):** R_q^off,ex = ผลจริงทางการแบบ gross (`realized.csv` แถว ERC · horizon Q · `ret_gross`) − rf ของไตรมาส · ส่วนอธิบาย = Σ_k B_k,q × F_k,q (F = ผลรวม f รายสัปดาห์ในช่วงถือ) · ε_L2 = ส่วนที่เหลือ
- **ส่วนต่างจากผลทางการ** = R_q^off (gross · วันซื้อจริง · NAV รายวัน) − R_q^panel (ทบต้นจาก panel) · ต้นทุน = ret_gross − ret ของ realized · ป้ายเหตุ: วันซื้อ e vs ศุกร์ · class ต่าง · NAV ศุกร์ขาด
- **ช่วงสรุป:** รายไตรมาส 15 · รวมทั้งช่วง (2022-04 → 2025-12) · **ปี 2022 แยก** = ช่วงถือของ t = 2022-03-31 / 06-30 / 09-30 (เม.ย.–ธ.ค. 2022 · M052 เริ่มถือ 2022-04-04) · รายปีปฏิทิน 2023 / 2024 / 2025 (บรรยาย)

### 3.5 ภาคผนวก (ลงทะเบียนล่วงหน้า · บรรยาย · ไม่ใช้สรุปหลัก)
- **P-A กองที่ E-X2 ไม่มี factor ตรงสินทรัพย์:** DAOL-GOLD (หุ้นเหมืองทอง / เงิน) + GOLD_XS · FCSCBSETE (ดัชนี SET) + `TDEX_THB − RF_BOT` → รายงาน R² ในหน้าต่าง · ส่วนที่เหลือของกองนั้น และผลต่อ ε ของพอร์ต (แถวพอร์ตแบบเปลี่ยนเฉพาะ 2 กองนี้)
- **P-B ตัด CMA** (CMA "ผ่านแบบขอบ" ใน S012): exposure / attribution ด้วย MKT + FX + factor กลุ่ม (+ GOLD_XS ขาทอง) เพื่อดูว่าข้อสรุปไวต่อ CMA ไหม
- **P-C ผลของการแบ่งหุ้น / ทอง (ไม่ใช่ factor attribution):** R_E,q (ขาหุ้นที่ normalize) · R_G,q (ขาทอง) · ผลการจัดสรร = (x_q − 0.57)(R_E,q − R_G,q) เทียบสัดส่วนหุ้นคงที่ 0.57 (= ค่าเฉลี่ยของ M052 · benchmark FIX57 ใน `run_r6.py`) · ตอบว่าการตัดสินใจ x (GC · CANARY · VSL) ช่วยหรือทำร้ายในปี 2022
- **P-D β จากไฟล์ weekly ของ quant (52 สัปดาห์ ≤ t):** สำหรับ holding ทุกตัว fit E-X2 / ชุดทองบน 52 แถวของ `m052_frontier_weekly.csv` แล้วเทียบ β กับข้อ 3.2 (ตรวจว่าใช้ผลตอบแทนชุดเดียวกับที่ทีม quant เห็น · บรรยาย)

---

## 4. ตารางที่รายงาน (`runs/S014/`)
1. `mapping.csv` — ข้อ 0.2 + จำนวนแถวในหน้าต่าง / ช่วงถือ · ธง class ต่าง / นอก U / NAV ศุกร์ขาด
2. `betas.csv` — ต่อ (t, holding): α · b0 · b1 · β ทุก factor · σ²_ε · adj R² ในหน้าต่าง · n · ธง fallback
3. `exposure.csv` — ต่อไตรมาส: B_k ทุก factor · x_model · น้ำหนักต่อกลุ่ม · HHI
4. `concentration.csv` — ต่อไตรมาส: share Euler ต่อ factor + ε (% ของ V และของ systematic) · vol ที่คาด · factor ที่ครองสูงสุด
5. `attribution_weekly.csv` / `attribution_q.csv` — L1 รายสัปดาห์ / รายไตรมาส · `attribution_L2.csv` · `attribution_summary.csv` (รวม · ปี 2022 · รายปี) · `reconcile.csv` (panel vs ทางการ · ต้นทุน)
6. ภาคผนวก `appendix_PA.csv` · `appendix_PB.csv` · `appendix_PC.csv` · `appendix_PD.csv`
7. `expectations_vs_results.csv` · `results.md` · `run.log` · `run_meta.json` · `repro_check.json`

ไม่มีเกณฑ์ผ่าน / ไม่ผ่าน (เชิงอธิบาย) · ไม่มี p-value ที่ใช้ตัดสิน · ถ้อยคำในรายงานผลห้ามอ่านเป็นการทำนายหรือคำแนะนำ

---

## 5. ผลลัพธ์ที่คาดไว้ล่วงหน้า (ช่วงกว้าง · ระยะ 1 คาดผิดบ่อย)
1. **mapping:** 24 รหัส → 24 หน่วย · ตัวแทน family 3 (KKP GINFRAEQ-H-F · ONE-INDIAOPP-IA · PRINCIPAL GOPP-C) · นอก U 3 (LHJAPE-A · ONE-INDIAOPP · SCBGOLDHP) · ไม่มี fallback ของ β
2. **exposure MKT:** corr ข้ามไตรมาสระหว่าง B_MKT กับ x_model ≥ 0.8 · B_MKT อยู่ในช่วง 0.15–1.0
3. **exposure GOLD_XS** ≈ (1 − x) × 0.85–1.0 ทุกไตรมาส
4. **การกระจุก:** ไตรมาสที่น้ำหนักทอง ≥ 0.5 (8 ไตรมาส) → GOLD_XS ≥ 50% ของ V · ไตรมาสที่ x ≥ 0.75 → MKT ≥ 35% ของ V และ factor กลุ่มรวม 10–45%
5. **FX:** B_FX อยู่ระหว่าง −0.8 ถึง +0.4 · ส่วนแบ่ง V ของ FX < 15% ทุกไตรมาส
6. **ε ของพอร์ต:** share_ε 5–30% ของ V · ในหน่วยผลตอบแทน |ε ไตรมาส| ≤ 3% ใน ≥ 10 จาก 15 ไตรมาส (L1)
7. **ส่วนต่าง panel vs ทางการ** |Δ| ≤ 1% ใน ≥ 12 จาก 15 ไตรมาส
8. **CMA:** |ผลรวม contribution ทั้งช่วง| < 2% · ไม่เปลี่ยนข้อสรุปหลัก (P-B)
9. **ปี 2022:** factor ที่ |contribution| มากสุดคือ GOLD_XS หรือ MKT (ไม่ใช่ factor กลุ่ม) · P-C: ผลการจัดสรรปี 2022 เป็นบวก (x ต่ำในช่วงหุ้นลง)
10. **P-A:** DAOL-GOLD เพิ่ม GOLD_XS แล้ว adj R² เพิ่ม ≥ 0.15 · FCSCBSETE เพิ่ม TDEX แล้ว adj R² เพิ่ม ≥ 0.20
11. **P-D:** β (52 สัปดาห์ของ quant) กับ β (ข้อ 3.2) มี corr ข้าม holding × factor ≥ 0.7 (หน้าต่างยาวต่างกัน)

---

## 6. decisions_pre_run (analyst เขียน**ก่อน**แตะข้อมูลจริงครั้งแรก · smoke ด้วยข้อมูลจำลองเท่านั้น)
1. sha256 เต็มของไฟล์ข้อ 2 + lib เดิม 16 ไฟล์ = `runs/S012/run_meta.json` `lib_sha256` (รวม `l1eo.py` `4c828e3bbfb7cade9868f6a884d0169fa2094c6defc4fc2636d74697ab523170`) · เพิ่มได้เฉพาะ `lib/port.py` + `lib/tests/test_port.py`
2. sha256 ของ `runs/S014/run.py` ณ เริ่ม phase pre + สำเนา `run_pre.py` (BRIEF 106)
3. ตาราง mapping ข้อ 0.2 (ต้องตรงทุกแถว · ไม่ตรง → หยุด)
4. หน้าต่าง 156 / min 52 · anchor ศุกร์ · ช่วงถือ (t_q, t_{q+1}] · ไตรมาสสุดท้ายถึง 2025-12-26
5. ชุด factor ต่อขา (ข้อ 3.1) · รายชื่อคอลัมน์ · assert ไม่มี AQR
6. การตั้งฉาก e_g ด้วย b̂ ของหน้าต่างไตรมาส (lag 0 · เก็บค่าคงที่)
7. นิยาม rf ของไตรมาสสำหรับ L2 (ผลรวม RF_BOT รายสัปดาห์ในช่วงถือ) · คอลัมน์ realized ที่ใช้ (`portfolio = ERC (กติกาโมเดล)` · `horizon = Q` · `ret_gross` · `ret`)
8. นิยามปี 2022 / รายปี (ข้อ 3.4)
9. ภาคผนวก P-A–P-D ตามข้อ 3.5 (ไม่เพิ่ม)
10. ไม่มีการเลือกหลังเห็นผล · ถ้าต้องแก้โค้ดหลังรันจริง → diff ใน results.md

---

## 7. implement (analyst)

### 7.1 `lib/port.py` (ใหม่ · ใช้ของเดิมให้มาก: `regress.fit_funds` · `l3.residualize` · `l3.ext_excess` · `l1eo.apply_name_rules` · `l1eo.o_factors` (ส่ง frame ไม่มี AQR) · `io_l1.sha256_file`)

| ฟังก์ชัน | input → output |
|---|---|
| `load_m052(ref_dir, pins)` | holdings / realized (ตรวจ sha · ข้าม comment `#`) |
| `load_eo_noaqr(freq)` | ตรวจ `manifest_eo_noaqr.json` · assert ไม่มีคอลัมน์ `AQR` |
| `map_holdings(H, universe, gmap, profile)` | ตาราง mapping ข้อ 0.2 (รหัสเดียวกัน → ตัวแทน family → กฎชื่อ) |
| `factor_frames(F, Fext, Feo)` | MKT · FX · CMA · GOLD_XS · I_g ทั้งหมด · TDEX (ภาคผนวก) |
| `window_mask(index, t, weeks=156)` | mask หน้าต่าง ≤ t |
| `group_factors_at(I, X1, mask)` | e_g ของไตรมาส + coef |
| `betas_at(R, unit, factors, mask)` | α · b0 · b1 · β · σ²_ε · adj R² · n (ผ่าน `fit_funds`) |
| `exposure(w, betas)` · `var_decomp(B, Sigma_f, w, s2eps)` | B · share Euler |
| `drift_weights(w0, R_hold)` | น้ำหนักลอยรายสัปดาห์ (Σ = 1) |
| `attribute_weekly(...)` / `attribute_quarter(...)` / `attribute_L2(...)` | ข้อ 3.4 |
| `reconcile(R_panel_q, realized)` | ส่วนต่าง + ต้นทุน |
| `runs/S014/run.py` | 2 phase: pre (mapping · หน้าต่าง · β · e_g · exposure · concentration) → full (attribution · ภาคผนวก · รายงาน) |

### 7.2 test `lib/tests/test_port.py` (ชื่อ `test_port_NN`)
1. **Σw = 1** ทุกไตรมาสของ holdings และของน้ำหนักลอยทุกสัปดาห์ (1e-12)
2. **future-scramble ของ β:** สุ่มแทนผลตอบแทนหน่วยและ factor ทุกแถว > t → β · α · σ²_ε · b̂ ของ e_g · Σ_f · exposure · share ของไตรมาส t **เท่าเดิมทุกบิต**
3. **เอกลักษณ์ attribution:** Σ_k C_k,s + A_s + E_s = r_p,s − rf_s ทุกสัปดาห์ (1e-12) · ผลรวมไตรมาสเท่ากัน
4. Euler: Σ share = 1 (1e-12) · ข้อมูลจำลอง factor ตั้งฉาก → share = B_k² σ²_k / V
5. mapping: 24 รหัสครบ · class F / C / IA → ตัวแทน family · LHJAPE-A / ONE-INDIAOPP → e_JAPAN / e_INDIA ด้วย `apply_name_rules` · kind G → ชุดทอง
6. ไม่มีคอลัมน์ AQR · ไม่มีแถว > 2025-12-26 ในการ fit / ตั้งฉาก / Σ_f
7. ข้อมูลจำลอง: พอร์ตที่สร้างจาก factor ล้วน (α = 0 · ε = 0) → attribution คืน B × F ตรง (1e-10) และ ε = 0
8. `run.py` 2 รอบ → sha256 ไฟล์ผลเท่ากันทุกบิต (ยกเว้น `run.log` · field เวลา)
- test เดิมทั้งหมด (`lib/tests/`) ผ่าน · `pytest -p no:cacheprovider`

### 7.3 การรันและความสอดคล้อง
- `run_meta.json` + บรรทัดแรกของ log ทุก phase: sha256 ของ `run.py` (BRIEF 106) · ถ้า pre ≠ full → diff ใน results.md
- ไฟล์ phase pre ถูกคำนวณซ้ำใน phase full และต้องตรงทุกบิต · repro 2 รอบ → `repro_check.json`
- regression: lib เดิม 16 ไฟล์ sha ไม่เปลี่ยน (ไม่ต้องรัน S003 / S006 / S012 ใหม่ เพราะไม่แตะ lib เดิม)

---

## 8. ข้อจำกัด
- ป้าย (P1)–(P5) · 15 ไตรมาส · กองหุ้น 3 กองต่อไตรมาส → exposure ของกลุ่มแกว่งตามการหมุนกอง
- β จากหน้าต่าง 64–156 สัปดาห์ (9 พารามิเตอร์ต่อกองใน E-X2) → ความคลาดเคลื่อนของ β สูงในไตรมาสแรก ๆ
- ช่วงถือใช้สัปดาห์ศุกร์ ไม่ใช่วันซื้อจริง · class ต่างใช้ตัวแทน family · K-GOLD-A(A) โดน NAV ศุกร์ขาดตลอดช่วง 2024–2025 (lens L2 ช่วยลดผลเวลาตีราคา แต่ β ยังประมาณจากข้อมูลรายสัปดาห์)
- ความแปรปรวนเฉพาะตัวสมมติอิสระข้ามกอง · Σ_f ใช้ lag 0
- DAOL-GOLD / FCSCBSETE ไม่มี factor ตรงสินทรัพย์ในชุดหลัก (ภาคผนวก P-A) · CMA ผ่านแบบขอบใน S012 (ภาคผนวก P-B)
- CANARY / VSL / GC เป็นกติกาจัดสรร ไม่ใช่ factor → ผลของการจัดสรรอยู่ในภาคผนวก P-C เท่านั้น

---

## 9. ต้องให้ผู้ใช้ตัดสินใจ (ค่าเริ่มต้นใช้ระหว่าง auto run · เปลี่ยนได้ก่อนรันเท่านั้น)

| # | เรื่อง | ค่าเริ่มต้นที่แนะนำ | ทางเลือก |
|---|---|---|---|
| 1 | หน้าต่างประมาณ β | rolling 156 สัปดาห์ (ขยายจาก 2021-01 ในไตรมาสแรก ๆ) · min 52 | rolling 104 (ไตรมาสแรก ๆ ยังเป็นหน้าต่างขยาย) · หรือ 52 สัปดาห์แบบทีม quant (= ภาคผนวก P-D) |
| 2 | lens หลักของ attribution | L1 รายสัปดาห์ (เอกลักษณ์ตรง) + L2 รายไตรมาสคู่กัน | L2 เป็นหลัก (ลดผลเวลาตีราคาของทอง · BRIEF 121(4)) |
| 3 | class ที่ไม่อยู่ใน panel | ใช้ตัวแทน family + ป้าย | ให้ data-engineer สร้างผลตอบแทนของ class จริงจาก `nav_history_db.csv` (อ่านอย่างเดียว · งานเพิ่ม) |
| 4 | CMA อยู่ในชุดหลัก | ใช่ (ตาม E-X2 ของ S012) + ภาคผนวก P-B ตัด CMA | ตัด CMA ออกจากชุดหลัก |
| 5 | factor เพิ่มให้ DAOL-GOLD / FCSCBSETE | ภาคผนวก P-A เท่านั้น | ใส่ในชุดหลัก (= ออกนอกกติกา E-X2 · ป้าย) |
| 6 | ปี 2022 | เม.ย.–ธ.ค. 2022 (ช่วงถือของ 3 ไตรมาสแรก) | – |
| 7 | ภาคผนวก P-C (ผลการจัดสรรหุ้น / ทอง เทียบ 0.57) | ทำ (ป้อนส่วน (ข)) | ไม่ทำ |
