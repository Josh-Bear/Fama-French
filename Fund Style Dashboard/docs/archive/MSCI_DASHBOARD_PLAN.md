# แผนงาน: MSCI Fund Country/Sector Classification Dashboard

สถานะ: **ร่างแผน — ยังไม่เริ่ม implement**
วันที่ร่าง: 2026-09-01
ขอบเขต: แยกเป็นแอปใหม่ ไม่ผูกกับโปรเจกต์ Fama French เดิม (ตามที่ยืนยัน: ก. รวมกอง F เข้า regression ไปเลย / ข. แยกโฟลเดอร์ แยกแอป)

---

## 0. สรุปสิ่งที่ยืนยันแล้วก่อนเข้าแผน (อัปเดตรอบล่าสุด)

| หัวข้อ | สิ่งที่ยืนยัน |
|---|---|
| ขอบเขตกองทุน (v2) | Project Retail Type = R, Tax Type ว่าง, buy period flag = N, sell period flag = N, switch_in flag = Y, switch_out flag = Y, Fund Policy ≠ M, Plain/Complex Fund ≠ C, FIF Flag = Y → **715 กอง** (E=600, F=77, O=38) |
| Match กับ nav_history_db | **680/715 กอง** มีประวัติ NAV ให้ใช้ regress ได้ → หลังกรอง threshold >600 จุดข้อมูล (นับด้วย NAVDate, re-verify แล้ว) เหลือ **368 กอง** ที่จะใช้ regress จริงในรอบแรก |
| Outlier handling | Return series (ทั้งกองทุนและ MSCI index) จะ winsorize ที่ 1st–99th percentile ก่อนใช้คำนวณ/regress เพื่อลด extreme value — รายละเอียดใน Phase 2 |
| ค่าเงิน (confirmed) | **MSCI_COUNTRY_ETF.csv / MSCI_SECTOR_ETF.csv แปลงเป็น THB ไว้แล้ว** ไม่ต้องแก้ Phase 2.5 เรื่องค่าเงินอีก — R² ต่ำที่เจอในการทดลองเป็นผลจาก date-mismatch (ปัญหาที่ 1+2 ด้านล่าง) ไม่ใช่ปัญหาค่าเงิน |
| วิธี match ประเทศ/sector (v2 — แทนที่ single-index best-match เดิมแล้ว) | **Multi-factor regression** — regress ผลตอบแทนกองกับ index ทั้ง 18 (country) / 10 (sector) พร้อมกันในโมเดลเดียว ด้วย **ElasticNetCV** (Lasso/Ridge รันคู่ไว้เทียบ) — primary/secondary match นิยามจาก **ขนาด standardized coefficient** ไม่ใช่ R² ต่อ index แยกแบบเดิม — รายละเอียดใน Phase 3 |
| กอง F (fixed income) | **รวมเข้า regression ไปเลย** ไม่แยกออก — ใช้ R² เป็นตัวบ่งชี้ความมั่นใจของ match บนกราฟ |
| ช่วงข้อมูล/ความถี่ | Daily, เต็มช่วง 2021-01 ถึง 2026-08, join ด้วย **NAVDate** (ไม่ใช่ AsOfDate) |
| Dashboard | 3 chart: Chart 1-2 = scatter (แยกประเทศ, แยก sector) x=annualized return, y=annualized volatility, สี=4-quadrant (เขียว/เหลือง/แดง/น้ำเงิน), ขนาดจุด=AUM; Chart 3 = bar chart แยกต่างหาก โชว์ primary(น้ำเงิน)/secondary(เขียว)/อื่นๆ(เทา) ต่อกอง — รายละเอียดใน Phase 5 |
| Deploy | แอป Streamlit ใหม่ แยกโฟลเดอร์ต่างหาก (ไม่ใช่หน้าเพิ่มใน Fama French app) |
| ข้อจำกัดข้อมูลที่รู้อยู่แล้ว | MSCI_COUNTRY_ETF.csv ไม่มี index ประเทศไทยตรงๆ (ใกล้เคียงสุด = ASEAN) |

> หมายเหตุ: ขอบเขตกองทุนแคบลงจากรอบก่อน (1,103 → 715 / 985 → 680) เพราะเพิ่มเงื่อนไข buy/sell period flag = N และ Plain/Complex Fund ≠ C เข้ามา

---

## 0.1 ผลรีวิว/verify กับข้อมูลจริง (2026-09-01, ก่อนเริ่ม Phase 1)

รัน script อ่านข้อมูลจริงใน `base_data/` เทียบตัวเลขในแผน — **ตัวเลขหลัก reproduce เป๊ะทุกตัว:**

| แผนอ้าง | ตรวจจริง |
|---|---|
| กรอง → 715 (E600/F77/O38), dup=0 | ✅ 715 (E600/F77/O38), dup=0 |
| join nav → 680 (35 ไม่มี nav) | ✅ 680 |
| threshold >600 → 368 | ✅ 368 (all-time = ใน window ก็ 368) |
| MSCI 18/10 col, 0 NaN, 2021-01-01→2026-07-31 | ✅ ตรง |
| NAVDate join corr 0.360/0.765/0.564/0.718 | ✅ เป๊ะทั้ง 4 คู่ |

**ประเด็นที่รีวิวเพิ่มเติม + การตัดสินใจ:**
1. **ค่าเงิน THB** — ยืนยันด้วยหลักฐาน: corr K-INDIA/ABJO = 0.72–0.77 (ถ้า MSCI ไม่ใช่ THB จะมี FX noise จน corr สูงขนาดนี้ไม่ได้) → ปิดประเด็น ไม่ต้องแก้ค่าเงิน
2. **⚠️ Collinearity ของ 18 country index (known risk — ตัดสินใจ: เก็บครบ 18 ตาม user 2026-09-01)** — 6 คู่ r>0.9 (ACWI~WORLD 0.99, USA~WORLD 0.96 ฯลฯ), condition number full-18 = 726 vs pruned-11 = 6 · ผลข้างเคียง: กองที่ควร match ชัด เช่น K-USA-A(A) รัน 18 ตัวได้ primary=ACWI และ USA ติดลบ (−0.039) — ต้องรับรู้ว่า "primary country" ของบางกอง (โดยเฉพาะกองที่ตลาดตรงกับ index รวม เช่น US) อาจถูก aggregate (ACWI/WORLD) แย่ง primary ไป
3. **นิยาม primary จาก |coefficient| (ตัดสินใจ: ตามแผนเดิม)** — ยอมรับได้ว่าบางกอง primary อาจเป็น coefficient ค่าลบ
4. **ไม่มี prototype gate ท้าย Phase 2 (ตัดสินใจ: ตามแผนเดิม)** — build ตามทฤษฎี cumulative-window เลย แล้วดูผลรวมทีหลัง

**Minor (flag ไว้ทำตอน implement):**
- NAVDate สูงสุด 2026-08-24 > MSCI 2026-07-31 → NAV ~1 เดือนท้ายไม่มี index จับคู่ (inner join ตัดทิ้ง — ปกติ)
- Dashboard ครอบคลุม 368/715 กอง (~51%) → ควร label ให้ชัดว่าไม่ใช่ทุกกอง FIF
- AUM ขนาดจุด scatter: ต้องเลือก snapshot (ล่าสุด/เฉลี่ย) ใน Phase 4/5
- StandardScaler ต้อง fit ภายใน CV fold (ใช้ sklearn Pipeline) กัน data leakage
- Sector model (10 ตัว MSCI_ACWI_*) แชร์ market factor เดียวกัน → เช็ค collinearity ด้วยตอน Phase 3 (คาดว่าเบากว่า country)

---

## Phase 0 — Project Scaffold

> ✅ **Confirmed & ทำแล้ว 2026-09-01** — จัดโครงสร้างโฟลเดอร์บนเครื่องจริงเรียบร้อยแล้ว (แยกโปรเจกต์ + ย้าย base data) รายละเอียดด้านล่าง

**โครงสร้างโฟลเดอร์จริงตอนนี้ (บนเครื่องผู้ใช้):**
```
/Users/doyinratnavardhana/Fama French/                 <- path หลัก เดิม (ไม่เปลี่ยนชื่อ)
    Fama French SET50/                                   <- ย้ายไฟล์แอป Fama French เดิมทั้งหมดมาไว้ที่นี่
        app.py, config.py, data_access.py, README.md, requirements.txt,
        streamlit_app_plan.md, CODE_REVIEW.md, SYSTEM_ANALYSIS.md, KNOWLEDGE_BASE.md,
        analysis/, data/, pages/, tests/, input/, raw_data/, .git, .gitignore, .venv
    Fund Style Dashboard/                                 <- โปรเจกต์ใหม่ (MSCI dashboard) แยกต่างหาก
        MSCI_DASHBOARD_PLAN.md                              <- ไฟล์แผนนี้
        base_data/                                           <- ย้ายมาจาก Downloads/MSCI ทั้งโฟลเดอร์
            FundProfile.csv, nav_history_db.csv,
            MSCI_COUNTRY_ETF.csv, MSCI_SECTOR_ETF.csv,
            SecFundFee.csv, TopHolding.csv,
            FUNDPROFILE_SECFUNDFEE_SCHEMA.pdf
```
(Downloads/MSCI ถูกลบแล้วหลังย้ายไฟล์เสร็จ ไม่มีข้อมูลซ้ำซ้อนสองที่)

**✅ Phase 0 scaffold — เสร็จแล้ว 2026-09-01** (สร้างโครงโค้ด + venv + ผ่าน checkpoint)
โครงจริงบนเครื่อง (เลียนแบบ pattern Fama French SET50, `data/` อ่านจาก `base_data/` ผ่าน `config.py` ล้วน):
```
Fund Style Dashboard/
  app.py                 # landing: สถานะไฟล์ base_data/ + ภาพรวม (boot ได้ ไม่โหลด data หนัก)
  config.py              # single source: path + filter criteria + column list + params ทั้งหมด
  requirements.txt       # streamlit, pandas, numpy, scikit-learn, plotly, pytest
  conftest.py            # ให้ pytest หา import เจอ
  .gitignore
  base_data/             # (มีอยู่แล้ว — raw MSCI csv/pdf)
  data/
    fund_profile.py      # load + filter FundProfile.csv          [stub -> Phase 1]
    nav_loader.py        # chunked load + dedupe nav_history_db.csv [stub -> Phase 1-2]
    msci_index.py        # load MSCI_*_ETF.csv + daily return       [stub -> Phase 1]
  analysis/
    matching.py          # return series + multi-factor ElasticNet  [stub -> Phase 2-3]
    metrics.py           # annualized return/volatility             [stub -> Phase 4]
  pages/
    1_🌍_Country_Match.py · 2_🏭_Sector_Match.py · 3_📊_Match_Strength.py   (placeholder)
  tests/
    test_smoke.py · test_filters.py · test_matching.py · test_metrics.py
```
> หมายเหตุ: เพิ่ม `pages/3_📊_Match_Strength.py` (Chart 3 แยกหน้า — confirmed) และ `conftest.py`/`.gitignore` เกินจากร่างเดิม

**✅ Unit test / Recheck — ผ่านหมด**
- `pytest` 8/8 passed · `py_compile` ทุกไฟล์ผ่าน
- boot `streamlit run app.py` จริง + เปิดครบทั้ง 4 หน้าในเบราว์เซอร์ ไม่มี error/traceback ใน log
- path ไฟล์ดิบทั้ง 6 ชี้ไปที่ `base_data/` ครบ (landing page ตรวจเจอไฟล์ ✅ ทั้งหมด ไม่มี path ค้าง Downloads/MSCI)

---

## Phase 1 — Data Ingestion & Filtering

**ทำอะไร**
1. โหลด `FundProfile.csv` (encoding='utf-8-sig') กรองตามเงื่อนไข 9 ข้อในตาราง Section 0 (v2)
2. โหลด `nav_history_db.csv` แบบ chunked/usecols (ไฟล์ 336MB ห้ามโหลดเต็มทั้งไฟล์ทีเดียวถ้าไม่จำเป็น) — ดึงคอลัมน์ `NAVDate` (และ `AsOfDate` ไว้ใช้ tie-break) มาด้วย (ใช้ NAVDate เป็นวันที่หลักแทน AsOfDate ตามที่เจอใน Phase 2) — filter เฉพาะ FundCode ที่อยู่ใน fund list จาก ข้อ 1 ตั้งแต่ตอนอ่าน chunk เพื่อลด memory — **dedupe ที่ (FundCode, NAVDate) โดยเก็บแถวที่ `UpdateTime` ล่าสุดไว้เมื่อชนกัน** (confirmed 2026-09-01, ดู item 7 ท้ายไฟล์ — ตัด NAV≤0/NaN ก่อน dedupe + stable sort ให้ reproducible)
3. โหลด `MSCI_COUNTRY_ETF.csv` (18 คอลัมน์) และ `MSCI_SECTOR_ETF.csv` (10 คอลัมน์) → คำนวณ daily return (`pct_change()`) ต่อ index

**Unit test / Recheck**
- `assert len(filtered_funds) == 715` และ breakdown E=600/F=77/O=38 (ตัวเลขอ้างอิงที่เช็คไว้แล้วตอน planning — ถ้าตอน implement จริงได้ตัวเลขไม่ตรง แปลว่ามี fund profile เปลี่ยนหรือ filter logic ผิด ต้องหยุดเช็คก่อน)
- `assert fp['Fund Code'].duplicated().sum() == 0` (ไม่มี fund code ซ้ำหลัง filter)
- `assert len(matched_with_nav) == 680` (join กับ nav_history_db)
- เช็ค missing values ใน MSCI index columns (ควรไม่มี NaN กลางช่วง ยกเว้นวันหยุดตลาดที่ต่างกันในแต่ละตลาด)
- สุ่มเช็คกอง 2-3 กองที่รู้จักหน้าตาอยู่แล้ว (เช่นกองหุ้นไทยล้วน) ว่า Fund Policy = E ตรงกับที่คาดไว้จริง
- `assert` จำนวนกองที่ผ่าน threshold >600 จุด (นับด้วย NAVDate หลัง dedupe) = **368/680** ตามที่ re-verify ไว้แล้ว — ถ้าไม่ตรงแปลว่า dedupe logic เขียนผิดจากที่ตั้งใจ
- สุ่มดูกองที่จำนวนแถว AsOfDate vs NAVDate ต่างกันเยอะที่สุด (ต่างกัน 387 แถวตามที่เจอตอน planning) ว่าเป็น data quality issue จริงหรือเป็นเรื่องปกติของกองนั้น

---

## Phase 2 — Return Series Construction (จุดที่ต้องระวังที่สุด)

**ปัญหาที่ต้องออกแบบก่อนเขียนโค้ด**

กองทุนรายงาน NAV ไม่ครบทุกวัน ถ้าเอา `.pct_change()` ตรงๆ บน series ที่มีวันหายไป จะได้ "daily return" ที่จริงๆ ครอบคลุมหลายวัน (เช่น NAV กระโดดจากวันจันทร์ไปวันศุกร์ ถูกนับเป็น 1 return แถวเดียว) ทำให้ regress กับ daily index return แบบวันต่อวันไม่ตรงกัน (date-mismatch bias)

**ข้อมูลจริงที่เช็คแล้ว — จำนวนจุดข้อมูล NAV ต่อกอง (จาก 680 กองที่มีประวัติ, ช่วงข้อมูลเต็ม ~1,259 วันทำการที่เป็นไปได้สูงสุด, แบ่งช่องทุก 100)**

| ช่วงจำนวนจุดข้อมูล | จำนวนกอง |
|---|---|
| 1–100 | 93 |
| 101–200 | 44 |
| 201–300 | 59 |
| 301–400 | 66 |
| 401–500 | 23 |
| 501–600 | 17 |
| 601–700 | 26 |
| 701–800 | 35 |
| 801–900 | 25 |
| 901–1,000 | 42 |
| 1,001–1,100 | 54 |
| 1,101–1,200 | 165 |
| 1,201–1,300 | 31 |
| **รวม** | **680** |

สังเกต: การกระจายเป็นสองกลุ่มชัดเจน (bimodal) — กลุ่มใหญ่สุดคือ 1,101–1,200 จุด (165 กอง, รายงานเกือบทุกวันทำการจริง) กับอีกกลุ่มที่ข้อมูลน้อยมาก 1–100 จุด (93 กอง, ~14% ของทั้งหมด) ซึ่งกลุ่มหลังนี้ regress แล้ว R² จะไม่น่าเชื่อถือเท่าไหร่ — ตัวเลขนี้จะใช้ประกอบการตัดสินใจ threshold ใน Phase 2 จริง (ยังไม่ fix เลข N วันนี้ รอดูอีกทีตอน implement ว่าจะตัดที่ไหน เช่น ตัดที่ <100 จุด หรือ <200 จุด)

**แนวทางที่เสนอ (default):**
- Reindex ผลตอบแทนกองทุนและ index ให้อยู่บนวันที่ที่ "กองทุนมีข้อมูลจริง" เท่านั้น (inner join บนวันที่ ไม่ forward-fill NAV ของกองทุน) แล้วคำนวณ return ระหว่างวันที่ที่มีข้อมูลจริงสองจุดติดกันของกองทุนนั้นๆ เทียบกับ **ผลตอบแทนสะสมของ index ในช่วงเดียวกัน** (ไม่ใช่ index daily return ตรงๆ) — วิธีนี้จะตัด noise จากช่วงที่กองทุนไม่รายงานออกไปแทนที่จะสร้าง return เทียมด้วย fill

**Threshold ขั้นต่ำ (confirmed, re-verify แล้วด้วย NAVDate 2026-09-01):** ตัดที่ **> 600 จุดข้อมูล** (คือช่วง 601–1,300+ ในตาราง)

> ✅ **อัปเดตจาก review pass — re-run นับด้วย NAVDate จริงแล้ว (แก้ item 6 ในรายการ confirm)**: ตัวเลข 680 กองเดิมนับ group ตาม `AsOfDate` ก่อนเจอเรื่อง NAVDate พอนับใหม่ด้วย `NAVDate` (dedupe ตาม FundCode+NAVDate) ได้ผลว่า **368/680 กอง** ผ่านเกณฑ์ >600 จุด (ลดจากตัวเลขเดิม 378 กอง) ส่วนกองที่ไม่ผ่านเกณฑ์คือ **312 กอง** (ไม่ใช่ 302 ตามตัวเลขเดิม) — **368/680 นี้คือตัวเลขที่ใช้จริงต่อไป**
>
> พบข้อมูลเพิ่มที่สำคัญระหว่างเช็ค: มี **408 กอง (จาก 680)** ที่จำนวนแถวนับด้วย AsOfDate กับ NAVDate ไม่เท่ากัน และกองที่ต่างมากที่สุดต่างกันถึง **387 แถว** — แปลว่าบางกองมีหลายแถวที่ AsOfDate ต่างกันแต่ NAVDate ซ้ำกัน (น่าจะเป็นการรายงาน/แก้ไข NAV ย้อนหลังสำหรับวันเดิม) **ยังไม่เคย confirm กติกาว่าถ้าเจอแถวซ้ำ NAVDate จะเก็บแถวไหนไว้** — เสนอ default: เก็บแถวที่ `AsOfDate` (หรือ `UpdateTime`) ล่าสุดไว้ (สมมติว่าเป็นค่าที่แก้ไข/ยืนยันล่าสุด ถูกต้องกว่าค่าที่เผยแพร่ก่อนหน้า) — เพิ่มเป็นจุด confirm ใหม่ท้ายไฟล์ และควรสุ่มเช็คกองที่ต่างกัน 387 แถวนั้นเป็นรายกรณีตอน implement ว่าเป็น data quality issue จริงหรือเปล่า

**เจาะลึก date-mismatch (ทดสอบเพิ่มวันนี้ด้วย K-USA-A(A) vs MSCI_USA) — พบว่ามี 2 ปัญหาแยกกัน ไม่ใช่ปัญหาเดียว**

ปัญหาที่ 1 — **ช่วงห่างการรายงานไม่สม่ำเสมอ (gap)**: เช็คช่วงห่างระหว่างวันที่ K-USA-A(A) รายงาน NAV จริงพบว่า median = 1 วัน (ปกติ) แต่ 25% ของช่วงห่าง ≥ 3 วัน (เช่นวันหยุดสุดสัปดาห์/นักขัตฤกษ์) และมี outlier สูงสุดถึง 54 วัน — เวลาทำ `.pct_change()` ตรงๆ บน series ที่มีช่วงห่างแบบนี้ แถวที่มีช่วงห่าง 3 วันจะถูกนับเป็น "1 return" เดียว ทั้งที่จริงคือผลรวมของ 3 วัน

ปัญหาที่ 2 — **NAV lag (พบใหม่ วันนี้ ยังไม่เคยพูดถึง) สำคัญกว่าปัญหาที่ 1 มาก**: ทดสอบ 3 วิธีกับคู่ K-USA-A(A) ↔ MSCI_USA (n=994 คู่):

| วิธี | corr |
|---|---|
| [A] Naive same-day join (สิ่งที่ demo เมื่อกี้ใช้) | **-0.022** |
| [B] Cumulative-window join (fix ที่เสนอไว้สำหรับปัญหาที่ 1) | 0.051 (ดีขึ้นนิดเดียว) |
| [C] Naive join แต่ shift index ไปข้างหน้า 2 วันทำการ | **0.424** |

Approach [C] คือทดสอบว่าถ้าเลื่อน index return ไปข้างหน้า (ใช้ MSCI_USA return ของอีก 2 วันทำการถัดไป มาเทียบกับ fund return ของวันนี้) แล้ว correlation จะเปลี่ยนไหม — ผลคือกระโดดจาก -0.02 เป็น 0.42 ทันที (สูงกว่า approach [B] ถึง 8 เท่า) นี่คือหลักฐานชัดว่า **NAV ของกองทุนนี้มี lag ประมาณ 2 วันทำการ เทียบกับราคาจริงของตลาดสหรัฐ** ซึ่งสมเหตุสมผลมาก เพราะกองทุนไทยที่ลงทุนต่างประเทศ (FIF) มักคำนวณ NAV จากราคาปิดตลาดต่างประเทศที่ล่าช้ากว่า 1-2 วันทำการ (เหตุผลหลักคือ time zone: ตลาดสหรัฐปิดตอนดึกๆ ตามเวลาไทย + cut-off time ของ back office/นายทะเบียนกองทุนที่ประมวลผลราคาไม่ทันวันเดียวกัน)

**สรุป**: fix ที่เสนอไว้เดิม (cumulative-window join) แก้ปัญหาที่ 1 ได้ แต่ไม่ได้แก้ปัญหาที่ 2 (NAV lag) ซึ่งจากตัวอย่างนี้ดูจะเป็นปัญหาที่ใหญ่กว่ามาก ต้องแก้ทั้งคู่พร้อมกัน

**ยืนยันแนวทางแก้ทั้ง 2 ปัญหา (confirmed 2026-09-01):**
- **ปัญหาที่ 1** แก้ด้วยการ **compound (ทบต้น) ผลตอบแทนของ index ตลอดช่วงที่กองไม่ได้รายงาน** แล้วเทียบกับ return ของกองในแถวนั้น (ไม่ใช่บวกเลขตรงๆ แบบบวกกัน เพราะ return ต้องทบต้นแบบ (1+r1)×(1+r2)×...−1) — ตรงกับที่เข้าใจไว้
- **ปัญหาที่ 2** เช็คแล้วว่า **lag ไม่คงที่เท่ากันทุกประเทศ** ทดสอบ lag-scan กับ 4 คู่กอง/index ที่ชื่อกองบอกตรงๆ:

  | กอง vs index | ตลาดปิดกี่โมง (เวลาไทย โดยประมาณ) | lag ที่ correlation สูงสุด | corr ที่ lag นั้น |
  |---|---|---|---|
  | K-USA-A(A) vs MSCI_USA | ~ตี 4–5 เช้า (ข้ามคืน) | **+2 วันทำการ** | 0.424 |
  | K-INDIA vs MSCI_INDIA | ~18:00 | **+1 วันทำการ** | 0.718 |
  | ABEG vs MSCI_EUROPE | ~23:30 | **+1 วันทำการ** | 0.536 |
  | ABJO vs MSCI_JAPAN | ~15:00 (ในเวลาทำการไทย) | **+1 วันทำการ** | 0.689 |

  สังเกต: สหรัฐฯ (ตลาดปิดดึกที่สุดเทียบเวลาไทย) มี lag มากกว่าตลาดอื่น (+2 vs +1) ส่วนญี่ปุ่น/อินเดีย/ยุโรป แม้ตลาดปิดในช่วงเวลาทำการไทยหรือใกล้เคียงก็ยังมี lag ขั้นต่ำ +1 วันเหมือนกันหมด (น่าจะมาจาก administrative processing lag ของนายทะเบียน/ผู้ดูแลกองที่เป็น baseline อยู่แล้ว ไม่เกี่ยวกับ time zone อย่างเดียว)

  **สรุปคือ lag ไม่ใช่ค่าคงที่ตัวเดียวใช้กับทุกกอง/ทุกประเทศ** — แต่แนวทาง calibrate lag แยกต่อประเทศที่เสนอไว้ข้างบน **ถูกแทนที่แล้วด้วยวิธีที่ดีกว่ามาก ดูหัวข้อถัดไป**

> ⚠️ **อัปเดตสำคัญ 2026-09-01 (รอบ 2) — เจอ root cause ที่แท้จริงของปัญหาที่ 2 แล้ว ไม่ต้อง calibrate lag เอง**

**ค้นพบ: nav_history_db.csv มีคอลัมน์ NAVDate แยกจาก AsOfDate อยู่แล้ว**

`AsOfDate` = วันที่ระบบบันทึก/เผยแพร่ NAV ส่วน **`NAVDate` = วันที่ที่ NAV นั้นสะท้อนราคาจริง** (ตรวจสอบแล้วพบว่า AsOfDate − NAVDate ส่วนใหญ่ = 1 วัน โดยมี 2,3,4+ วันสำหรับกรณีวันหยุดสุดสัปดาห์/นักขัตฤกษ์) — พูดง่ายๆ คือไฟล์นี้บอก lag ที่แท้จริงไว้ให้แล้วในตัวเอง ไม่ต้องเดา/calibrate เอง

ทดสอบ join ด้วย **NAVDate แทน AsOfDate** (ไม่ shift อะไรเพิ่ม) กับ 4 คู่เดิม:

| กอง vs index | join ด้วย AsOfDate (เดิม) | join ด้วย NAVDate (ใหม่) | ดีขึ้น |
|---|---|---|---|
| K-USA-A(A) vs MSCI_USA | corr = −0.022 | **corr = 0.360** | ดีขึ้นมาก |
| K-INDIA vs MSCI_INDIA | corr = 0.068 | **corr = 0.765** | ดีขึ้นมาก (ดีกว่าวิธี lag-scan เดิมที่ได้ 0.718 ด้วยซ้ำ) |
| ABEG vs MSCI_EUROPE | corr = −0.031 | **corr = 0.564** | ดีขึ้นมาก (ดีกว่า lag-scan เดิม 0.536) |
| ABJO vs MSCI_JAPAN | corr = −0.092 | **corr = 0.718** | ดีขึ้นมาก (ดีกว่า lag-scan เดิม 0.689) |

ทดสอบ lag-scan ซ้ำบนฐาน NAVDate ดูอีกที (เผื่อยังเหลือ lag ตกค้าง) พบว่า **lag=0 คือค่าที่ดีที่สุดแล้วสำหรับทั้ง 4 คู่** ไม่ต้อง shift เพิ่มอีก (ยกเว้น K-USA ที่ยังพอมีช่องให้ปรับปรุงอีกเล็กน้อยเทียบกับที่เคย hand-tune ได้ 0.42 — น่าจะเป็นเรื่อง time zone ของสหรัฐฯ ที่ยังละเอียดอ่อนกว่าตลาดอื่นเล็กน้อย แต่ไม่ใช่ปัญหาใหญ่แล้ว)

**เปลี่ยนแนวทาง Phase 2 ทั้งหมดเป็นดังนี้ (ง่ายกว่าที่เสนอไว้เดิมมาก ไม่ต้อง calibrate lag เอง):**
1. โหลด `nav_history_db.csv` ให้รวมคอลัมน์ `NAVDate` ด้วย (ไม่ใช่แค่ `AsOfDate`)
2. ใช้ **NAVDate เป็นวันที่หลักในการ index/join** กับ MSCI index แทน AsOfDate ตลอดทั้ง pipeline
3. ยังคงต้องทำ **cumulative-window join** ตามปัญหาที่ 1 อยู่ (เพราะ NAVDate ก็ยังมีช่วงห่างไม่สม่ำเสมอได้เหมือนกันถ้ากองไม่รายงานหลายวันติด) — สองปัญหานี้แก้ร่วมกันได้ในขั้นตอนเดียว: ใช้ NAVDate เป็นจุดอ้างอิง + compound ผลตอบแทน index ระหว่างสอง NAVDate ที่ติดกัน
4. ตัด workflow "calibrate lag ต่อประเทศ" ที่เสนอไว้ก่อนหน้าออกทั้งหมด — ไม่จำเป็นแล้ว

**Outlier winsorization (confirmed)**
- Return series ทุกตัว (ทั้งของกองทุนและของ MSCI index) จะ clip ที่ 1st percentile และ 99th percentile **แยกทีละกอง/ทีละ index** (ไม่ pool รวม) ก่อนนำไปใช้คำนวณ annualized return/volatility และก่อน regress — ตัดค่า extreme ที่อาจเกิดจาก data error หรือ corporate action ที่ไม่ได้ปรับ (เช่น NAV split) โดยไม่ตัดทั้งแถวทิ้ง

**Unit test / Recheck**
- ทดสอบกับกองทุนสมมติที่สร้างขึ้นเอง (fixture data) ที่รู้คำตอบล่วงหน้า เช่น NAV คงที่ (return ต้อง=0 ทุกจุด), NAV เพิ่มเป็นเส้นตรง (return สม่ำเสมอ)
- เทียบ annualized return ที่คำนวณได้ กับการคำนวณแบบ (NAV_end/NAV_start)^(252/n_days)-1 ของกองเดียวกันแบบ manual (ไม่ผ่าน pipeline) — ต้องตรงกันในหลักทศนิยมที่ยอมรับได้
- เช็คว่า winsorize แล้วจำนวนจุดข้อมูลไม่หาย (clip ไม่ใช่ drop) และค่า min/max ของแต่ละ series ใหม่ตรงกับ 1st/99th percentile ที่คำนวณเอง
- นับจำนวนกองที่โดน flag ข้อมูลไม่พอตาม threshold ที่เลือก รายงานให้เห็นก่อน confirm

---

## Phase 3 — Country / Sector Multi-Factor Regression

> 📌 methodology เดิมของ phase นี้คือ "single-index best-match" (loop regress ทีละ index แยก, secondary match นิยามจาก R² ในช่วง R²max×0.9) — **ถูกแทนที่ทั้งหมดด้วย multi-factor ElasticNet ด้านล่างแล้ว** ตามผลทดลอง demo prototype (ดูตารางผลทดลองถัดไป) เก็บสรุปสั้นๆ ไว้ในบรรทัดนี้เผื่ออ้างอิงย้อนหลัง ไม่ต้องอ่านของเดิมอีก

**Multi-factor exposure model (methodology ปัจจุบัน)**
- แทนที่จะ regress ทีละ index แยกกัน จะ regress ผลตอบแทนกองทุนกับ **MSCI Country index ทั้ง 18 ตัวพร้อมกัน** ในโมเดลเดียว (ทำแบบเดียวกันแยกกับ 10 sector index) เพื่อดู "สัดส่วนผสม" ที่กองทุนถือจริงๆ
- ใช้ **ElasticNetCV** เป็นหลัก (เหตุผลละเอียดในหัวข้อผลทดลองด้านล่าง) แต่จะรัน Lasso และ Ridge เก็บผลไว้เปรียบเทียบ/แสดงในหน้า dashboard ด้วย (ให้ผู้ใช้สลับดูได้ว่าแต่ละโมเดลให้ผลต่างกันแค่ไหน)
- Standardize X (18 หรือ 10 columns) ด้วย StandardScaler ก่อน fit ทุกครั้ง (ตาม convention เดียวกับที่ใช้ในโปรเจกต์ Fama French เดิม)

**นิยาม primary/secondary/others ในโลก multi-factor (เพิ่มใหม่ — เดิมยังไม่เคยนิยามไว้ชัดหลังเปลี่ยนมาเป็น multi-factor)**
เนื่องจากตอนนี้เป็นโมเดลเดียวที่มีหลาย coefficient พร้อมกัน (ไม่ใช่หลาย R² แยกจากหลายโมเดลแบบเดิม) นิยามใหม่คือ: ในบรรดา index ที่ ElasticNet ให้ coefficient ไม่เป็นศูนย์ (non-zero) — **primary = index ที่ |standardized coefficient| มากที่สุด, secondary = index ที่มากเป็นอันดับ 2, ที่เหลือ = "อื่นๆ"** (ใช้ตรงกับที่ Chart 3 ใน Phase 5 ต้องการพอดี) — ถ้ากองไหน ElasticNet ตัด coefficient เหลือ 0 ทั้งหมด (แบบ ASP-CHINABOND-A ในผลทดลองข้างล่าง) ก็จะไม่มี primary/secondary เลย ต้องมี fallback แสดงผลบนกราฟ (เช่น จัดเป็นกลุ่ม "ไม่พบ exposure ชัดเจน") — จุดนี้ยังไม่เคย confirm เพิ่มไว้ในรายการท้ายไฟล์

**ผลทดลอง Lasso / Ridge / ElasticNet (demo prototype, รันแล้ววันนี้ — ยังไม่ใช่ final pipeline)**

รันกับ 4 กองตัวอย่าง (K-USA-A(A)=หุ้นสหรัฐ, K-INDIA=หุ้นอินเดีย, BCARE=global healthcare sector, ASP-CHINABOND-A=ตราสารหนี้จีน) โดยใช้วิธี "naive" คือ pct_change ตรงๆ บนวันที่กองทุนรายงานจริง แล้ว inner-join กับ daily index return (**ยังไม่ได้ทำ fix แบบ cumulative-window ที่เสนอไว้ใน Phase 2**) ผลสรุป:

| กอง | เทียบกับ | Lasso R² | Ridge R² | ElasticNet R² | หมายเหตุ |
|---|---|---|---|---|---|
| K-USA-A(A) | Country (18) | 0.058 | 0.028 | 0.058 | เลือก WORLD/ACWI/WORLD_EX_US ไม่ใช่ USA ตรงๆ |
| K-INDIA | Country (18) | 0.044 | 0.042 | 0.044 | เลือก TAIWAN/VIETNAM/JAPAN/KOREA ไม่ใช่ INDIA |
| BCARE | Sector (10) | 0.003 | 0.007 | 0.003 | คาดว่าควรโหลดหนักที่ HEALTH CARE แต่แทบไม่มีอะไร explain ได้เลย |
| ASP-CHINABOND-A | Country/Sector | 0.000 | ~0.01–0.02 | 0.000 | Lasso/ElasticNet ตัด coefficient เหลือศูนย์หมด — สอดคล้องกับที่คาดว่ากองบอนด์ไม่ควร fit กับ index หุ้น |

**สิ่งที่เห็นจากผลทดลองนี้ (สำคัญ):**
1. **พฤติกรรมโมเดลตรงตามทฤษฎี**: Ridge ไม่เคยตัด coefficient เป็นศูนย์เลย (เก็บครบ 18/10 ตัวเสมอ) ส่วน Lasso/ElasticNet ตัดตัวที่ไม่ช่วยทิ้งจนเหลือไม่กี่ตัว หรือศูนย์หมดถ้าไม่มีอะไร explain ได้จริง (เคส ASP-CHINABOND-A) — ตรงกับที่อธิบายไว้ก่อนหน้านี้
2. **R² ต่ำผิดปกติในทุกกรณี แม้แต่กองที่ควรจะ fit ชัดเจน** (K-USA ควร fit กับ USA สูง, BCARE ควร fit กับ Health Care สูง) — จุดนี้เป็น**สัญญาณเตือนว่า pipeline การจับคู่วันที่ยังไม่ถูกต้อง** ไม่ใช่ว่ากองทุนไม่ track ดัชนีจริง เหตุผลที่น่าจะเป็นไปได้ 2 อย่าง:
   - **Date-mismatch ที่ Phase 2 เตือนไว้แล้ว**: demo นี้ยังใช้วิธี naive (pct_change ตรงๆ + inner join วันเดียว) ยังไม่ได้ทำ fix แบบเทียบกับ cumulative return ของ index ในช่วงเดียวกัน — ต้องแก้ตาม Phase 2 ก่อนถึงจะเชื่อตัวเลขได้
   - **ค่าเงิน (พบใหม่วันนี้)**: เช็คแล้ว NAV ของทั้ง 4 กองอยู่ในสกุล **THB** ทั้งหมด ขณะที่ MSCI index (18+10 ตัว) ไม่ได้ปรับเป็น THB — ถ้ากองทุนไม่ได้ hedge FX เต็มจำนวน ความผันผวนของอัตราแลกเปลี่ยน USD/THB (หรือสกุลอื่นตามแต่ละประเทศ) จะปนเข้าไปใน return ของกองทุนแต่ไม่มีใน index ทำให้ correlation ต่ำลงมาก แม้กองทุนจะถือหุ้นตรงตามชื่อจริงๆ ก็ตาม
3. **ยังสรุปไม่ได้ว่า multi-factor + ElasticNet ให้ผลลัพธ์ที่ใช้งานได้จริง** จนกว่าจะแก้ 2 จุดข้างบน — แนะนำเพิ่ม **Phase 2.5: แก้ปัญหาค่าเงิน** (หา FX rate เช่น USD/THB มาแปลง MSCI index เป็น THB terms ก่อน regress — อาจดึงจาก yfinance เหมือนที่ analysis/data ฝั่ง Fama French project ใช้อยู่แล้ว) ควบคู่กับการแก้ date-alignment ใน Phase 2 แล้วรัน demo นี้ซ้ำอีกรอบก่อนเริ่ม build จริง

**Unit test / Recheck**
- รันกับ subset กองที่รู้จักหน้าตาก่อน (เช่น กองที่ชื่อมี "US EQUITY", "CHINA", "JAPAN" ตรงๆ ใน Fund Name EN) → เช็คว่า best-match country ตรงกับชื่อกองหรือไม่ (sanity check เชิงคุณภาพ ไม่ต้อง match 100% แต่ควรตรงเป็นส่วนใหญ่ ถ้าไม่ตรงเลยแปลว่า pipeline ผิดที่ใดที่หนึ่ง)
- เช็ค R² แปลกๆ: R² ที่ = 1.0 เป๊ะ (สงสัยว่า series ซ้ำกันเอง/bug) หรือ R² ที่คำนวณไม่ได้ (NaN จาก division by zero เมื่อ variance ของกองทุน = 0)
- ดูการกระจายของ R² แยกตาม Fund Policy (E ควรมี R² เฉลี่ยสูงกว่ากลุ่ม F อย่างชัดเจนตามที่คาดไว้ในเชิงทฤษฎี — ถ้าไม่ใช่แบบนั้นต้องกลับไปเช็ค Phase 2)
- เช็ค secondary-match logic ด้วยเคสสมมติ (fixture) ที่รู้ค่า R² ล่วงหน้าทุกตัว ว่าตัวที่อยู่ในช่วง [R²max−10%, R²max) ถูกจับมาครบ ไม่เกิน ไม่ขาด

---

## Phase 4 — Fund-Level Metrics (Annualized Return / Volatility)

**ทำอะไร**
- คำนวณ annualized return และ annualized volatility ต่อกอง จาก daily return series ที่ได้จาก Phase 2 (ใช้ observation ที่มีจริงของกองนั้น ไม่ใช้วันที่ fill)
- ใช้ convention เดียวกับที่ใช้ในโปรเจกต์ Fama French เดิม (annualize ด้วย 252 trading days) เพื่อให้เทียบกันได้ในอนาคตถ้าต้องการ

**Unit test / Recheck**
- ตรวจสูตร annualize ให้ตรงกับที่ระบุใน KNOWLEDGE_BASE.md ของโปรเจกต์เดิม (ความสม่ำเสมอของ convention)
- สุ่มเช็ค 3-5 กอง คำนวณมือเทียบกับผลจาก pipeline

---

## Phase 5 — Dashboard (Streamlit, แอปแยก)

> ⚠️ **อัปเดต 2026-09-01 — เปลี่ยน color scheme ของ chart 1-2 เป็น quadrant + เพิ่ม chart 3 ใหม่ (primary/secondary strength)**

**Chart 1 — Country scatter**
- แกน x = annualized return, แกน y = annualized volatility (เหมือนเดิม), ขนาดจุด = AUM (เหมือนเดิม)
- **สีเปลี่ยนจาก "best-match country" เป็น 4-quadrant แทน**: แบ่งกราฟด้วยเส้น 2 เส้น — เส้นแนวตั้งที่ return = 0% (บวก/ลบ) และเส้นแนวนอนที่ **median volatility ของกองทั้งหมดในกราฟ** (เสนอ ใช้ median เพราะ robust กว่า mean กับ outlier) — ได้ 4 quadrant ตามนี้:

  | Quadrant | ตำแหน่งบนกราฟ | เงื่อนไข | สี |
  |---|---|---|---|
  | Q1 | บนขวา | return > 0, volatility > median | 🟢 เขียว |
  | Q2 | บนซ้าย | return < 0, volatility > median | 🟡 เหลือง |
  | Q3 | ล่างซ้าย | return < 0, volatility < median | 🔴 แดง |
  | Q4 | ล่างขวา | return > 0, volatility < median | 🔵 น้ำเงิน |

  (นี่คือการตีความตาม convention คณิตศาสตร์มาตรฐาน Q1=บนขวา วนทวนเข็มนาฬิกา — ถ้าคุณนึกภาพ quadrant ไว้คนละแบบ เช่น Q1=บนซ้าย หรือแบ่งเส้นด้วยค่าอื่นที่ไม่ใช่ median volatility บอกได้เลย จะแก้ตาม)
- ประเทศที่ match ได้ (เดิมเคยใช้เป็นสี) ย้ายไปอยู่ใน **hover tooltip แทน** (พร้อม Fund Code/ชื่อกอง/Fund Policy/R²/AUM เหมือนเดิม) และเพิ่ม dropdown/multiselect filter ให้เลือกดูเฉพาะบางประเทศได้ถ้าต้องการ
- **(confirmed)** กองที่ ElasticNet ตัด coefficient เหลือ 0 หมด (ไม่มี primary/secondary เลย) ยังคงแสดงจุดบนกราฟตามปกติ (ตำแหน่ง quadrant ไม่ขึ้นกับ coefficient) แต่ hover tooltip ช่อง "ประเทศที่ match" จะขึ้นข้อความ **"ไม่พบ exposure ชัดเจน"** แทนชื่อประเทศ

**Chart 2 — Sector scatter**: เหมือน Chart 1 ทุกอย่าง แต่จับคู่กับ sector index แทน country

**Chart 3 — Primary vs Secondary match strength (ใหม่)**
- แยกออกมาต่างหากจาก 2 chart บน ไม่ใช่ scatter แต่เป็น **bar chart ต่อกองทุน** แสดงว่ากองนั้นสัมพันธ์กับ index ที่ match ได้แต่ละตัวมากน้อยแค่ไหน
- แกน x = ชื่อ index ที่กองนั้น match ได้ (เรียงจากมากไปน้อยตามน้ำหนัก)
- **แกน y (confirmed): ใช้ |standardized coefficient| จากโมเดล ElasticNet** (ไม่ใช่ R² เดี่ยวของแต่ละ index) — เหตุผล: การจัดลำดับว่าตัวไหนเป็น primary/secondary (นิยามไว้ใน Phase 3) ก็มาจากขนาด coefficient อยู่แล้ว ถ้าแกน y ของกราฟใช้คนละตัวชี้วัดกับที่ใช้จัดอันดับ (เช่นใช้ R² แทน) จะเกิดกรณีแปลกๆ ได้ เช่นแท่งที่ถูก label ว่า "primary" (สีน้ำเงิน) ดันไม่ใช่แท่งที่สูงที่สุดในกราฟ เพราะ R² เดี่ยวของ index อื่นอาจสูงกว่าทั้งที่ในโมเดลรวมมันไม่ใช่ตัวหลัก (เกิดจาก index หลายตัวสัมพันธ์กันเอง) — ใช้ coefficient ตัวเดียวกันทั้งการจัดอันดับและความสูงของแท่ง จะได้กราฟที่สอดคล้องในตัวเอง
  - เพิ่มเติม (ไม่บังคับ): โชว์ R² เดี่ยวของแต่ละ index เป็นตัวเลขเสริมใน tooltip ของแต่ละแท่งได้ ไว้ช่วยตีความ แต่ไม่ใช้กำหนดความสูงแท่งหรือลำดับ
- สี: **primary match = น้ำเงิน, secondary match = เขียว, ตัวอื่นๆ ที่เหลือ (non-zero coefficient แต่ไม่ใช่ primary/secondary) = สีเทา/สีอื่น**
- เข้าถึงยังไง **(confirmed 2026-09-01): แยกเป็นหน้าที่ 3 ต่างหาก `pages/3_📊_Match_Strength.py`** มี dropdown/search เลือกกองทีละ 1 กอง (ไม่ทำ interactive popup จากการคลิก Chart 1/2 — Streamlit ทำ click-callback ยุ่งและเปราะกว่า) — หน้านี้สร้าง placeholder ไว้แล้วใน Phase 0
- ใช้ได้ทั้ง country และ sector (เลือกสลับได้ว่าจะดู breakdown ฝั่งไหน)
- **(confirmed)** ถ้าเลือกกองที่ ElasticNet ตัด coefficient เหลือ 0 หมด (ไม่มี primary/secondary) Chart 3 จะไม่มี bar ให้แสดง — ให้ขึ้นข้อความ placeholder แทนกราฟ เช่น "กองนี้ไม่พบ exposure ชัดเจนกับ index กลุ่มนี้ (ElasticNet ตัด coefficient เหลือ 0 ทุกตัว)"

**Control เพิ่มเติม (เสนอ ไม่บังคับ)**: slider กรองขั้นต่ำ R² ของ primary match (ซ่อนกองที่ match ไม่มั่นใจ), toggle เลือกแสดง/ซ่อน Fund Policy (E/F/O), search box หากองทุนจากชื่อ

**Unit test / Recheck**
- หน้าเว็บโหลดได้ไม่ error ทั้ง 3 chart
- สุ่มคลิก/hover เช็คว่าตัวเลขที่แสดงตรงกับตารางผลลัพธ์จาก Phase 3-4
- เช็คการแบ่ง quadrant ด้วยมือ 3-5 กอง (คำนวณ return/volatility เอง เทียบกับ median แล้วดูว่าตกลง quadrant ที่ถูกต้องไหม)
- เช็คว่า filter/slider ทำงานถูกต้อง (จำนวนจุดบนกราฟลดลงตามที่ควรเมื่อขยับ R² threshold)
- เช็ค Chart 3 กับกองที่รู้ผลจาก Phase 3 อยู่แล้ว (เช่นกองที่มี secondary match ชัดเจนอย่าง K-USA-A(A) ที่เคย match ทั้ง USA/WORLD/ACWI) ว่า bar สีน้ำเงิน/เขียว/เทาตรงกับลำดับ coefficient จริง

---

## Phase 6 — Documentation & Final Recheck (ตาม project convention เดิม)

**ทำอะไร**
- เขียน README สั้นๆ อธิบาย: ที่มาของข้อมูล, filter ที่ใช้, วิธี match, ข้อจำกัดที่รู้อยู่แล้ว (ไม่มี Thailand index ตรงๆ, กอง F ถูก match แบบ low-confidence โดยเจตนา, threshold ขั้นต่ำของจำนวนจุดข้อมูลที่ใช้)
- Final recheck 3 เรื่องตาม workflow ของโปรเจกต์: (1) โค้ดที่เพิ่งเขียนถูกต้องหรือไม่ (2) ไม่กระทบระบบ Fama French เดิม (เพราะแยกแอปคนละโฟลเดอร์ ความเสี่ยงต่ำอยู่แล้ว แต่ต้องเช็คว่าไม่ได้ import/แก้ไฟล์ฝั่ง Fama French โดยไม่ตั้งใจ) (3) โครงสร้างโดยรวมยังสมเหตุสมผล ไม่ซับซ้อนเกินจำเป็น

---

## จุดที่ยังต้อง confirm ระหว่างทาง (ไม่ใช่ตอนนี้ แต่ flag ไว้ล่วงหน้า)

1. ~~ชื่อ/ตำแหน่งโฟลเดอร์แอปใหม่~~ ✅ confirmed และจัดโครงสร้างโฟลเดอร์จริงเสร็จแล้ว (ดู Phase 0)
2. ~~หน้าตา/สีของกราฟหลัก~~ ✅ confirmed เป็น 4-quadrant (เขียว/เหลือง/แดง/น้ำเงิน) แล้ว — แต่ยังมีจุดย่อยที่ต้อง confirm: การตีความตำแหน่ง Q1-Q4 บนกราฟ (สมมติ Q1=บนขวาตาม convention คณิตศาสตร์) และเส้นแบ่ง volatility ใช้ median (เสนอไว้ ยังไม่ confirm)
3. ~~secondary match แสดงผลยังไง~~ ✅ confirmed เป็น Chart 3 แยกต่างหาก (primary=น้ำเงิน, secondary=เขียว, อื่นๆ=เทา) — ~~(ก) แกน y~~ ✅ ใช้ |standardized coefficient| — ~~(ข) popup vs หน้าแยก~~ ✅ **confirmed 2026-09-01: แยกเป็นหน้า `pages/3_📊_Match_Strength.py` ต่างหาก** (ไม่ใช่ popup)
4. ~~Phase 3 methodology~~ ✅ confirmed เป็น multi-factor ElasticNet/Lasso/Ridge แล้ว (ดู Phase 3)
5. ~~กองที่ ElasticNet ตัด coefficient เหลือ 0 หมด แสดงผลยังไง~~ ✅ confirmed — จัดเป็นกลุ่ม "ไม่พบ exposure ชัดเจน" ทั้งใน hover tooltip (Chart 1/2) และ placeholder message (Chart 3) แล้ว
6. ~~ตัวเลข 378/680~~ ✅ confirmed — re-run ด้วย NAVDate จริงแล้ว ได้ **368/680 กอง** ผ่านเกณฑ์ (ดู Phase 2)
7. ~~แถวซ้ำ NAVDate เก็บแถวไหน~~ ✅ **confirmed 2026-09-01: เก็บแถวที่ `UpdateTime` ล่าสุด** (ไม่ใช่ AsOfDate — ใช้ timestamp อัปเดตจริงเป็นตัวตัดสิน) กรณีชน (FundCode, NAVDate) — 408/680 กองมีจำนวนแถวไม่ตรงกันระหว่าง AsOfDate/NAVDate, มากสุดต่าง 387 แถว · ยังควรสุ่มเช็คกองที่ต่าง 387 แถวเป็นรายกรณีตอน implement Phase 1

8. **(guard เพิ่มตอน implement — บันทึกให้แผน sync กับโค้ด)** `MIN_REGRESSION_OBS = 30` ใน `data_access.build_pipeline`: กองที่มี return "ในช่วง MSCI" (หลัง align) < 30 จุด จะถูก **ข้ามทั้งกอง** (try/except ต่อกอง) กัน `ElasticNetCV(cv=5)` ล้ม/ได้ผลมั่วตอนข้อมูลน้อย — เพราะ threshold `>600` นับ NAVDate ทั้ง history แต่ regression ใช้เฉพาะช่วง 2021+ → กองจำนวนจริงที่เข้า dashboard **อาจ < 368** ได้ (หน้าแรกจึงโชว์ `len(results)` จริง ไม่ hardcode)

---

**สถานะ**: ✅ **เสร็จทุก Phase (0–6) 2026-09-01** — pipeline build 368 กอง cache แล้ว, แอป 3 หน้ารันได้, pytest ผ่าน
- Phase 1: filter 715 → nav 680 → threshold 368 (checkpoint1.py ผ่าน)
- Phase 2-3: build_fund_returns (NAVDate+cumulative-window+winsorize) + match_exposure (ElasticNet/Lasso/Ridge)
- Phase 4: annualized return/volatility · Phase 5: 3 หน้า (Country/Sector scatter + Match Strength)
- ผล: R² by policy E=0.57/F=0.15/O=0.17 (ตรงทฤษฎี), K-INDIA→INDIA, BCARE→Health Care
- Phase 6: README + final recheck
