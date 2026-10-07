# M017 — คัดดัชนี MSCI ก่อน แล้วเลือกกองที่ตามดัชนีที่ชนะ (index-first) บน M012-QF-S

สถานะ: **ลงทะเบียนล่วงหน้า 2026-10-07** — เขียนก่อนเขียนโค้ดรัน/ก่อนเห็นผลใดๆ ของแบบนี้ (สำรวจแบบ read-only เฉพาะ: cache exposure ครอบคลุม I_t ทุกไตรมาส,
เวลา fit, จำนวน primary_coef < 0 — `scratch/quant_m017_feas.py` ไม่คำนวณ return) · ผู้ออกแบบ: quant-modeler (ไอเดียจากผู้ใช้ ผ่านหัวหน้าทีม)
model_id: **M017-IDX** · **trial #34 → n_trials_cumulative = 34** (แถวสุดท้ายใน trials.csv = M016-CW, n = 33)
base: **M012-QF-S** ทุกบิตที่ไม่ได้ระบุว่าเปลี่ยน (`specs/M012_quality_filter.md` + การตัดสินใจผู้ใช้ 2026-10-06, โค้ด `backtest/run_m012.py` mode "S")
· universe เต็ม (ซื้อได้ทุก class) · rf จริง (นโยบาย ธปท.) · `FeeData(legacy=False)` Actual FEEUH · **ห้ามมีตัวแปรอื่น/ไม่ tune หลังเห็นผล**

## 1. สมมติฐาน (ex-ante, ซื่อตรง)
- momentum ระดับ "ประเทศ/อุตสาหกรรม" (time-series/cross-sectional momentum ของดัชนี — Moskowitz & Grinblatt 1999 industry momentum, Asness/Moskowitz/Pedersen 2013
  — ไม่ได้เปิดอ่านเอง) อาจเป็นแหล่ง return ที่ทนทานกว่า momentum ของ NAV กองเอง (NAV มี noise จากค่าธรรมเนียม/hedge/ปันผล) → เลือกดัชนีที่ SR12 สูงก่อน แล้วซื้อกองที่ตามดัชนีนั้น
- การกำหนด "1 ดัชนี → 1 กอง" + กรอง correlation บังคับกระจายข้ามธีม (แก้จุดอ่อน greedy เดิมที่กองซ้ำ profile)
- **ข้อควรรู้ก่อน (ex-ante)**: BRIEF ระบุว่าระดับดัชนี "ไม่มีสูตรไหนผ่าน t = 2" (dry run 2026-09-30) → หลักฐานเบื้องต้นไม่สนับสนุน · N = 5 → path luck สูง (เหมือน M016)
  · คาด Sharpe อยู่ในช่วง 0.4–0.8, CAGR ไม่แน่นอน ±3 pt · ไม่คาดว่าแก้ปี 2022
- ข้อจำกัดเชิงโครงสร้าง (รู้ก่อนรัน): exposure ระดับประเทศใน `exposure.py`/cache fit กับ **11 ดัชนี VIF-clean** (`config.SCORE_COUNTRY_CLEAN`) ไม่ใช่ 18
  → ดัชนีรวม 7 ตัว (ACWI, WORLD, WORLD_EX_US, ACWI_EX_US, EM, ASIA_EX_JAPAN, CHINA_ALL_SHARES) **ถูกจัดอันดับร่วมใน 28 ตามคำสั่ง แต่ไม่มีกองใดมีเป็น primary ได้**
  → ถูกข้ามเสมอเมื่อเดินถึง (นับแยกเป็น "ข้ามเชิงโครงสร้าง") และยังกินอันดับใน hysteresis ≤ 10 · ไม่ refit ด้วย 18 ดัชนี (collinear, VIF สูง — เหตุผลเดิมของแอป)

## 2. อัลกอริทึม ณ วันตัดสินใจ t (point-in-time ทั้งหมด)
### 2.1 คะแนนดัชนี SR12_idx (28 ดัชนี รวม country 18 + sector 10 ในชุดเดียว)
- ข้อมูล: level ราคาที่แปลงเป็น **บาท (THB)** ใน `base_data/MSCI_COUNTRY_ETF.csv` / `MSCI_SECTOR_ETF.csv` (โหลดผ่าน `data.msci_index`) — ฐานเดียวกับที่ใช้ fit exposure และ trend filter ACWI
  · ใช้เฉพาะแถว Date ≤ t (assert)
- สูตรเดียวกับ SR12' ของกอง (`fs.QuarterContext.fund_signal` + `r11.with_hurdle`) โดยถือ level ดัชนีเป็น "NAV":
  R12_1 = L(M−1)/L(M−12) − 1 (month-end ของปฏิทินดัชนี, asof ≤ 10 วัน) · vol52 = sd(52 weekly returns, จุดสัปดาห์ = วันทำการสุดท้ายของ ISO week) × √52
  · **SR12_idx = (R12_1 − h_t)/vol52** · h_t = rf นโยบาย ธปท. จริงทบต้นช่วง (M−12, M−1] (`r11.hurdle`, ค่าเดียวกับที่ใช้กับกองไตรมาสนั้น)
- จัดอันดับ 28 ตัวรวมกัน: SR12_idx มาก→น้อย (NaN ท้ายสุด) · เสมอ → ชื่อคอลัมน์ (ตัวอักษร)

### 2.2 exposure + สิทธิ์ของกองต่อดัชนี
- exposure ณ t = `exposure.fit_scope(U_t FundCodes, …, t)` ElasticNet expanding window ≤ t (cache ต่อ t; offset 1/2 ที่ไม่มี cache จะ fit ใหม่และเขียน cache ใน `backtest/cache/`)
  country scope = 11 ดัชนี `SCORE_COUNTRY_CLEAN`, sector scope = 10 ดัชนี `MSCI_SECTOR_COLS`
- **tracks(f)** = { country_primary(f) ถ้า country_r2 ≥ 0.50 และ country_primary_coef > 0 } ∪ { sector_primary(f) ถ้า sector_r2 ≥ 0.50 และ sector_primary_coef > 0 }
  (เงื่อนไข coef > 0 = "ตาม" ดัชนีต้องเป็นทิศบวก · ex-ante พบ coef < 0 ใน sector 0–6 กอง/ไตรมาส, country 0)
- **กอง f มีสิทธิ์ (eligible) สำหรับดัชนี X** ⇔ X ∈ tracks(f) **และ** f เป็น class ตัวแทนของ family ใน **I_t' ของ M012-QF-S**
  (I_t เดิม: สด ≤ 10 วัน, ตัด class ภาษี, ตัด -D ถ้ามี class ไม่ปันผล, สัญญาณครบ · + Q1 AUM_fam ≥ 100 ล้าน + Q2 อายุแบบ B ≥ 730 วัน)
  · class ตัวแทน = `wt.family_representatives(I_t', "SR12", held_funds)` (SR12' สูงสุดในกลุ่ม; ถ้าถือ class ใดอยู่ใช้ class ที่ถือ) → 1 class ต่อ family เหมือน M012

### 2.3 hysteresis (ก่อนเติม)
- กองที่ถือ (fam, fc, X = ดัชนีที่ซื้อมา) **ถือต่อ** ⇔ อันดับของ X ≤ 10 ใน 28 **และ** fc ยังเป็นตัวแทนของ family ใน I_t' (= ผ่านเกณฑ์คุณภาพ + สด) **และ** X ∈ tracks(fc) ณ t
  ไม่งั้นขาย · ถ้าไตรมาสก่อนตก B0 → ไม่มีกองถือต่อ (เหมือน M012)
- กองถือต่อครอบครอง "ช่อง" ของทุกดัชนีใน tracks ของมัน (สำหรับกฎ b) และเข้าเกณฑ์ correlation (กฎ c) · กองถือต่อไม่ถูกตรวจกฎ b/c ระหว่างกันเอง

### 2.4 เติม (fill) จนครบ N = 5
```
chosen = กองถือต่อ ; occupied = ∪ tracks(c) ของ chosen
for X in ดัชนีเรียงอันดับ 1→28:
    if |chosen| == 5: stop
    if X ∈ occupied: ข้าม (นับ "occupied") ; continue
    cands = กองที่ eligible ต่อ X เรียง SR12' มาก→น้อย (เสมอ: vol52 น้อย, FundCode)
    if cands ว่าง: ข้าม (นับ "no_eligible"; ถ้า X อยู่นอก 21 ดัชนีที่ fit ได้ = "structural")
    for c in cands:
        (a) family ของ c ถูกเลือกแล้ว → ปัด (นับ rej_a)
        (b) tracks(c) ∩ occupied ≠ ∅ → ปัด (นับ rej_b)   # 1 ดัชนี → ไม่เกิน 1 กอง
        (c) ρ_adj(c, s) > 0.85 กับ s ใดใน chosen → ปัด (นับ rej_c)
        ผ่านทั้งหมด → เลือก c สำหรับ X ; occupied ∪= tracks(c) ; break
    ถ้าไม่มีใครผ่าน → ข้าม (นับ "blocked")
```
- ρ (กฎ c) = **`run_m010.rho_adj_pair` ของ M010** (weekly return 52 สัปดาห์ ≤ t จาก ctx["wk"], lead-lag lag 1 เต็มน้ำหนัก, สัปดาห์ร่วม < 30 → NaN → ถือว่าผ่าน) เกณฑ์ > 0.85 = ปัด
- ถ้าเดินครบ 28 แล้วได้ < 4 กอง → **fallback B0** (`ctx["b0_w"]` เดิม ไม่กรอง) และไตรมาสถัดไปไม่มีกองถือต่อ — บันทึกจำนวนไตรมาส · ได้ 4 กอง → ใช้ 4 กอง

### 2.5 น้ำหนัก + ส่วนที่เหมือน M012-QF-S
- ERC (`wt.risk_parity_weights` Ledoit-Wolf lag 0 บน weekly 52 สัปดาห์; inverse-vol ถ้าสัปดาห์ร่วม < 30) → `wt.apply_cap(w, 0.25)`
- Trend 25: ACWI < SMA200 ณ t → ส่วนหุ้น × 0.75 + เงินสด 25% (rf จริง) · ตัดสินใจวันทำการสุดท้าย มี.ค./มิ.ย./ก.ย./ธ.ค. · ซื้อขาย NAV วันทำการที่ 2 (`r12.to_plan` / `r9.make_plan`)
- ค่าธรรมเนียม `FeeData(legacy=False)` FEEUH Actual (`ro.sims_for("B", …)` = `r15.sim_cases_x`) · รายงาน full / nofront / flat 0.5%/ข้าง (+ 0%)

## 3. การวัดผล (เหมือนเดิมทุกประการ)
- 45 เดือน เม.ย. 2022 – ธ.ค. 2025 · Sharpe = mean(r − rf_m)×12 / (sd(r)×√12) · rf จริงรายเดือน · CI95% block bootstrap (block 3, 2000, seed 0)
- DSR (`rr.dsr_s`) n_trials = 34 · paired Δ Sharpe (`r11.paired_real`) เทียบ Trend 25 และ M012-QF-S · ผลตอบแทนรายปี 2022 (เม.ย.–ธ.ค.), 2023, 2024, 2025
- offset 0/1/2 (วิธี `ROBUST_offsets`/`M016_offsets`: ช่วงร่วม ก.ค. 2022–ธ.ค. 2025, 42 เดือน) — รายงานเท่านั้น
- regression ก่อนรัน (ไม่ผ่าน = หยุด ไม่นับ trial): pipeline เดียวกันให้ M012-QF-S full = 0.659648 (`M012_results.csv`) และ Trend 25 = 0.719313 · Trend 25 offset = `FULLUNIV_offsets.csv`
  · assert ไม่มีข้อมูลหลัง t: level ดัชนี ≤ t, weekly series ≤ t, cache exposure key = t, Quality ≤ t · spot refit exposure (ไม่ใช้ cache) ของกองตัวอย่างต้องได้ primary/R² เท่า cache
- รายงานต่อไตรมาส: top-5 ดัชนี + SR12_idx, กองที่เลือก + ดัชนีของกอง, ถือต่อกี่กอง, ดัชนีที่ถูกข้าม (structural / no_eligible / occupied / blocked), จำนวนปัดตามกฎ a/b/c, B0
  · จำนวนประเทศ (country_primary) ที่ถือ และน้ำหนักรวมสูงสุดใน 1 ประเทศ (ของพอร์ตรวม และของส่วนหุ้น)

## 4. เกณฑ์ตัดสิน (ล็อก)
| ผล | เงื่อนไข (fee full, rf จริง, offset 0, 45 เดือน) |
|---|---|
| **ผ่าน** | CAGR > 9.09% (CAGR ของ Trend 25) **และ** maxDD ≥ −20% |
| **ไม่ผ่าน** | อย่างใดอย่างหนึ่งไม่เป็นจริง → ไม่รันซ้ำด้วยค่า N/K/เกณฑ์ R²/ρ อื่นภายใต้ชื่อนี้ |
- Sharpe รายงานคู่ (ไม่ใช้ตัดสิน) · อ้างอิง: Trend 25 0.719 / 9.09% / −11.16% · M012-QF-S 0.660 / 8.33% / −10.22% · M016-CW 0.541 / 7.85% / −19.73% (จากไฟล์ผล)
- ผ่านเกณฑ์ ≠ ดีกว่าอย่างมีนัย: อ่านคู่กับ paired CI, offset 1/2, DSR@34

## 5. ความเสี่ยง + สิ่งที่ reviewer ควรตรวจ
- path luck สูง (N = 5) · ดัชนีรวม 7 ตัวกินอันดับแต่ไม่มีกอง → hysteresis ≤ 10 เข้มกว่าที่ตั้งใจ · กองไทยส่วนใหญ่ primary = USA/EUROPE → concentration ระดับประเทศ
- sector exposure ของกองประเทศอาจไม่มีความหมาย (เช่น primary MT จำนวนมาก) แต่ถูกกรองด้วย R² ≥ 0.50
- ตรวจ: (1) ไม่มี look-ahead (§3) (2) กฎ b: ไม่มีดัชนีใดถูก track โดยกองที่เลือกใหม่ > 1 กอง (3) กองถือต่อผ่านเงื่อนไข §2.3 ทุกข้อ (4) regression 6 หลัก

## 6. ต้องให้ผู้ใช้ตัดสินใจ
- ถ้าผ่าน: ยอมรับ concentration ประเทศ/path luck หรือไม่ · ถ้าไม่ผ่าน: คง Trend 25 / M012-QF-S
- ถ้าอยากให้ดัชนีรวม (ACWI/WORLD/EM…) มีกองได้จริง ต้องลงทะเบียน trial ใหม่ที่ fit exposure 18 ดัชนี (ไม่ใช่ปรับ M017)
