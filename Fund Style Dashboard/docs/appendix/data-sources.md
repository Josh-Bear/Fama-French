# ภาคผนวก: แหล่งข้อมูล

ไฟล์ดิบทั้งหมดอยู่ใน `base_data/` — **user เป็นคนวางเอง** ยกเว้น `STYLE_FACTOR_ETF.csv` และ `MACRO_FACTOR.csv` ที่ดึงจาก
yfinance / FRED ด้วยคำสั่งแยก (`data_access.py style-download` / `macro-download`) ครั้งเดียวแล้วใช้ offline · ระบบ**ไม่ดึงข้อมูลเอง**ตอน build หรือเปิดแอป
ทุก path อ้างอิงจาก `config.py` (ผูกกับ `BASE_DIR`) → ย้ายทั้งโฟลเดอร์ได้โดยไม่พัง

## สรุปไฟล์

| ไฟล์ | ขนาด | ระบบใช้ไหม | ใช้ทำอะไร |
|---|---|---|---|
| `FundProfile.csv` | 2.1 MB | ✅ | ทะเบียนกองทุน — กรองขอบเขต 715 กอง + ชื่อ/ประเภทกอง |
| `nav_history_db.csv` | **336 MB** | ✅ | ประวัติ NAV รายวัน — แหล่งผลตอบแทนของกอง |
| `MSCI_COUNTRY_ETF.csv` | 343 KB | ✅ | ดัชนีประเทศ 18 ตัว (ตัวแปรอิสระฝั่ง country) |
| `MSCI_SECTOR_ETF.csv` | 228 KB | ✅ | ดัชนี sector 10 ตัว (ตัวแปรอิสระฝั่ง sector) |
| `STYLE_FACTOR_ETF.csv` | 226 KB | ✅ | ราคา iShares factor ETF 8 ตัว (USD) — style factor หน้า 6 (snapshot จาก yfinance) |
| `MACRO_FACTOR.csv` | 176 KB | ✅ | level ดิบ macro 7 ตัว — หน้า 7 (snapshot จาก yfinance + FRED) |
| `SecFundFee.csv` | 11.3 MB | ✅ หน้า 9 | ค่าธรรมเนียมผู้ถือหน่วย (FEEUH: front-end/back-end/สับเปลี่ยน · `Actual Value`) — backtest ค่าธรรมเนียมจริง (`analysis/fund_fees.py`) |
| `TopHolding.csv` | 126 KB | ❌ ยังไม่ใช้ | หุ้นที่กองถือ — เผื่อ cross-check exposure ในอนาคต |
| `FUNDPROFILE_SECFUNDFEE_SCHEMA.pdf` | 378 KB | 📄 อ้างอิง | คำอธิบาย schema ของ 2 ไฟล์แรก |

---

## 1. FundProfile.csv

ทะเบียนกองทุนทั้งหมด **3,982 กอง** (อ่านด้วย `encoding="utf-8-sig"` เพื่อตัด BOM)

**คอลัมน์ที่ระบบใช้** (ชื่อต้องตรงเป๊ะ — `config.FILTER_EQ/NEQ/EMPTY`):

| คอลัมน์ | ใช้ทำอะไร |
|---|---|
| `Fund Code` | คีย์เชื่อมกับ nav (หมายเหตุ: ในไฟล์ nav ชื่อ `FundCode` ไม่มีเว้นวรรค) |
| `Fund Name EN` | ชื่อกองแสดงในตาราง/hover |
| `Fund Policy` | E=equity · F=fixed income · O=other · M=money market (กรอง M ออก) |
| `Project Retail Type` · `Tax Type` · `FIF Flag` · `buy/sell period flag` · `switch_in/out flag` · `Plain / Complex Fund` | 9 เงื่อนไขกรองขอบเขต |

**เกณฑ์กรอง 9 ข้อ → เหลือ 715 กอง (E=600 / F=77 / O=38)**

| ต้องเท่ากับ | ต้อง**ไม่**เท่ากับ | ต้องว่าง |
|---|---|---|
| Project Retail Type = `R` (ขายรายย่อย) | Fund Policy ≠ `M` | Tax Type (ไม่เอา RMF/SSF/LTF) |
| FIF Flag = `Y` (ลงทุนต่างประเทศ) | Plain / Complex Fund ≠ `C` | |
| buy period flag = `N` · sell period flag = `N` | | |
| switch_in flag = `Y` · switch_out flag = `Y` | | |

---

## 2. nav_history_db.csv (336 MB — ห้ามโหลดทั้งไฟล์)

~3.0 ล้านแถว → อ่านแบบ **chunked** (`config.NAV_CHUNKSIZE = 500,000`) + `usecols` + กรองเฉพาะกองที่สนใจตั้งแต่ตอนอ่าน
→ เหลือ ~450k แถวในหน่วยความจำ

**คอลัมน์ที่อ่าน** (`config.NAV_USECOLS`): `FundCode`, `NAV`, `NAVDate`, `UpdateTime`, `AUM`
(ไฟล์จริงมี `AsOfDate`, `OfferNAV`, `BidNAV`, `SwitchIn/OutNAV`, `AMCCode` ด้วย แต่ไม่ได้ใช้ — ไม่ parse เพื่อประหยัดเวลา)

### 🔑 ทำไมต้องใช้ `NAVDate` ไม่ใช่ `AsOfDate`
สองคอลัมน์นี้ต่างกัน:
- `AsOfDate` = วันที่**ระบบบันทึก/เผยแพร่** NAV
- `NAVDate` = วันที่ที่ NAV นั้น**สะท้อนราคาจริง**

กองไทยที่ลงทุนต่างประเทศคำนวณ NAV จากราคาปิดตลาดต่างประเทศที่ช้ากว่า 1-2 วันทำการ (time zone + cut-off ของนายทะเบียน)
ถ้า join ด้วย `AsOfDate` จะเกิด **NAV lag** ทำให้ correlation พังทันที — พิสูจน์ด้วยข้อมูลจริง:

| กอง vs ดัชนี | join ด้วย AsOfDate | join ด้วย **NAVDate** |
|---|---|---|
| K-USA-A(A) vs MSCI_USA | −0.022 | **+0.360** |
| K-INDIA vs MSCI_INDIA | +0.068 | **+0.765** |
| ABEG vs MSCI_EUROPE | −0.031 | **+0.564** |
| ABJO vs MSCI_JAPAN | −0.092 | **+0.718** |

> ผลข้างเคียงที่ยืนยันเพิ่ม: correlation สูงถึง 0.72–0.77 **เป็นไปไม่ได้ถ้าดัชนี MSCI ยังเป็นสกุลอื่น** → ยืนยันว่าไฟล์ MSCI แปลงเป็น THB มาแล้วจริง

### การทำความสะอาดข้อมูล
1. **ตัดแถวเสียก่อน dedupe** — `NAV` เป็น NaN หรือ `NAV ≤ 0` (กองยังไม่เปิด/ระงับ) ตัดทิ้ง
   ทำ**ก่อน** dedupe เพื่อไม่ให้แถวที่ใหม่กว่าแต่ NAV เสีย ไปเบียดแถวเก่าที่ใช้ได้ออก
2. **dedupe `(FundCode, NAVDate)`** — เก็บแถวที่ `UpdateTime` ล่าสุด
   - `UpdateTime` มี 3 รูปแบบปนกัน (`…SS.fff` ~97% · `…SS` · ISO `…Z` ที่เป็น UTC) → `nav_loader.parse_update_time`
     อ่านครบทุกแบบและแปลง UTC เป็นเวลาไทยก่อนเทียบ (เดิมอ่านไม่ได้ 10,606 แถวในกอง E · ตรวจแล้วเลือก NAV ตรงกับเดิมทุกคู่)
   - เรียงด้วย `na_position="first"` → แถวที่ UpdateTime parse ไม่ได้ (NaT) ไปอยู่หน้า จึงไม่ถูกเลือก
   - `kind="stable"` → ผลลัพธ์เหมือนเดิมทุกครั้งที่รัน (reproducible)

### เกณฑ์คัดกอง
- นับจำนวน `NAVDate` ที่ไม่ซ้ำต่อกอง → **ต้อง > 600 จุด** (`config.MIN_DATA_POINTS`)
- 715 กอง → **680 กองมีประวัติ NAV** → **368 กองผ่านเกณฑ์** → **313 กอง policy E** (`config.APP_POLICY`)
  → ตัดกอง NAV เก่า/เลิกกอง (หัวข้อถัดไป) → **209 กอง** เข้า pipeline
- การกระจายเป็น bimodal ชัด: กองใหญ่สุดรายงานเกือบทุกวันทำการ (1,100-1,200 จุด) อีกกลุ่มรายงานน้อยมาก (<100 จุด)

### ความสดของ NAV และรูข้อมูล (เพิ่ม 2026-09-30 · ตกลงกับผู้ใช้หลัง dry run)
ไฟล์ NAV มีรูใหญ่ที่เกิด**พร้อมกันหลายร้อยกอง** — น่าจะมาจากการเก็บข้อมูลต้นทาง ไม่ใช่กองหยุดรายงานเอง:
**7 ม.ค. → พ.ค./มิ.ย. 2026** (133 กองมีรู 31–90 วันทำการ) และ **27 ม.ค. → 22 มี.ค. 2021** (กองตระกูล K-*) · 94 กองหยุดที่ ม.ค. 2026 เลย

| กติกา | ค่า | ผล (กอง E) |
|---|---|---|
| **กองเลิกแล้ว** — มีแถว NAV ≤ 0 ลงวันที่หลังวันสุดท้ายที่ NAV ใช้ได้ (`nav_loader.closed_funds`) | ตัดเสมอ | 2 กอง (PRINCIPAL GEF-C / GEF-X) |
| **NAV เก่า** — NAV ล่าสุดช้ากว่าวันล่าสุดของดัชนี MSCI เกิน `NAV_STALE_MAX_DAYS` วันปฏิทิน | 90 | 102 กอง |
| **return คร่อมรู** — NAV 2 จุดติดกันมีวันทำการของดัชนีหายไประหว่างกันเกิน `NAV_MAX_GAP_BDAYS` → ทิ้ง return ช่วงนั้น ทั้งฝั่งกองและดัชนี (ไม่เติมค่า) · ใน `matching.build_fund_returns` จึงมีผลทุกหน้า | 10 | 159 กอง · 340 จุด |

- ผลรวม: **313 → 209 กอง** · ในกองที่เหลือ R²/vol แทบไม่เปลี่ยน แต่ primary country เปลี่ยน 33 กอง (ส่วนใหญ่สลับระหว่าง
  ดัชนีรวมที่คล้ายกัน) · ตัวอย่าง return ที่ถูกทิ้ง: M-ASIA 7 ม.ค. → 12 มิ.ย. 2026 = +18.5% ใน "จุดเดียว"
- รูเล็กที่ขาดทีละ 1–7 วันยังทบต้นแบบเดิม (รูสั้นสุดที่เจอคือ 12 วันทำการ → เกณฑ์ 10 แยกสองกลุ่มได้สะอาด)
- **ไม่ได้แก้:** class ปันผล (-D) ใช้ NAV ที่ยังไม่บวกปันผลคืน (ไฟล์ไม่มีข้อมูลปันผล) → return ต่ำกว่าผลตอบแทนรวมจริง

### ไฟล์ผลลัพธ์
- `cache/nav_clean.parquet` (`config.NAV_CLEAN_PARQUET`, ~5 MB) — NAV ที่ clean แล้วของกอง E ทั้ง universe เขียนโดย
  `build_pipeline` · คอลัมน์ `FundCode, NAVDate, NAV, AUM, spike_fixed, status` (`keep` / `stale` / `closed` / `few_points`)
  · ขั้น style / macro / score / risk model อ่านจากไฟล์นี้ (~0.1 วิ) แทนการสแกนไฟล์ดิบ 336 MB ซ้ำ
- `base_data/share_class_groups.csv` (`config.SHARE_CLASS_CSV`) — กลุ่ม share class ของกองเดียวกัน 32 กลุ่ม 70 กอง
  (จัดจากชื่อที่ต่างแค่ท้าย -A/-D/-H/-SSF …) · **แก้ด้วยมือได้** · ใช้ในหน้า 8 ให้เลือกได้ไม่เกิน 1 class ต่อกลุ่ม
  (ทุกหน้ายังเห็นทุก class เพราะ return ต่างกันจริงจากค่าธรรมเนียม/ปันผล/hedge แม้ corr รายวันจะ ~0.99)

---

## 3. MSCI_COUNTRY_ETF.csv / MSCI_SECTOR_ETF.csv

| | Country | Sector |
|---|---|---|
| จำนวนดัชนี | **18** | **10** |
| แถว | 1,456 | 1,456 |
| ช่วงวันที่ | 2021-01-01 → 2026-07-31 | เหมือนกัน |
| ค่าที่เก็บ | **ระดับราคา (level)** ไม่ใช่ return | เหมือนกัน |
| NaN | 0 | 0 |
| สกุลเงิน | **แปลงเป็น THB แล้ว** | เหมือนกัน |

**Country 18 ตัว:** ASIA_EX_JAPAN, BRAZIL, CHINA_A_SHARES, CHINA_H_SHARES, CHINA_ALL_SHARES, EM, EUROPE, INDIA, JAPAN, KOREA, ASEAN, TAIWAN, USA, VIETNAM, ACWI, WORLD, WORLD_EX_US, ACWI_EX_US

**Sector 10 ตัว (ฐาน ACWI):** CD=consumer discretionary · CS=consumer staples · EN=energy · FN=financials · HC=health care · IN=industrials · IT=information technology · MT=materials · TC=communication services · UT=utilities

### ⚠️ ข้อจำกัดสำคัญ 2 ข้อ
1. **ไม่มีดัชนีประเทศไทย** — ใกล้เคียงที่สุดคือ ASEAN
2. **ดัชนีซ้อนทับกันเอง (collinearity)** — เพราะ 18 ตัวปนทั้งดัชนีรายประเทศและดัชนีรวม
   วัดจริงพบ 6 คู่ที่ correlation > 0.9:

   | คู่ | r |
   |---|---|
   | ACWI ~ WORLD | 0.990 |
   | ASIA_EX_JAPAN ~ EM | 0.988 |
   | USA ~ WORLD | 0.962 |
   | WORLD_EX_US ~ ACWI_EX_US | 0.948 |
   | USA ~ ACWI | 0.935 |
   | EUROPE ~ WORLD_EX_US | 0.932 |

   **condition number = 726** (ชุดเต็ม 18 ตัว) เทียบกับ **6** ถ้าตัดเหลือเฉพาะดัชนีรายตลาด 11 ตัว
   ผลกระทบจริง: กองหุ้นสหรัฐฯ อาจถูก ACWI/WORLD แย่ง primary ไป
   👉 **ตัดสินใจไว้ว่าคงครบ 18 ตัว** (เพื่อจับกองที่เป็น global tracker ได้ด้วย) — จึงต้องอ่าน R² ประกอบเสมอ
   · ยกเว้น**หน้า 8** ที่มีตัวเลือกชุด VIF-cleaned 11 ตัว (`SCORE_COUNTRY_CLEAN` — ตัดด้วย VIF < 5 บนข้อมูล 2026-09-22:
   condition number 492 → 3.5 ต่างจากตัวเลข 726 → 6 ข้างบนที่วัดตอนวางแผนแรกคนละช่วงข้อมูล)

---

## 4. STYLE_FACTOR_ETF.csv (หน้า 6)

| | |
|---|---|
| ที่มา | yfinance `auto_adjust=True` (ราคารวมปันผลแล้ว) — `data_access.py style-download` |
| ticker (8) | MTUM · IMTM · QUAL · IQLT · VLUE · IVLU · ACWV · **ACWI** (benchmark + control `ACWI_ETF`) |
| แถว / ช่วง | 1,472 · 2020-11-02 → 2026-09-14 (เริ่มก่อน MSCI เผื่อ ffill) |
| ค่าที่เก็บ | ระดับราคา (level) · **USD** · ปฏิทิน NYSE (ทุกตัวจดทะเบียนที่ US) |

- ต่างจาก MSCI ในข้อ 3 สองเรื่อง คือ **สกุลเงิน (USD vs THB)** และ**เวลาปิด (NY vs ท้องถิ่น)** — จึงต้องใส่ control ตลาดทั้งสองฝั่ง (ดู [หน้า 6](../pages/6-style-match.md))
- ใช้แบบ relative (÷ ACWI) เท่านั้น ค่าเงินจึงหักล้างกันพอดี

---

## 5. MACRO_FACTOR.csv (หน้า 7)

| | |
|---|---|
| ที่มา | yfinance `auto_adjust=True` 6 ตัว + FRED `DGS10` (CSV ตรง · "." = NaN) — `data_access.py macro-download` |
| คอลัมน์ (7) | Oil_Brent (`BZ=F`) · Gold (`GC=F`) · USDTHB (`THB=X`) · Copper (`HG=F`) · DXY (`DX-Y.NYB`, fallback `DX=F`) · VIX (`^VIX`) · US10Y (`DGS10`) |
| แถว / ช่วง | 1,528 · 2020-11-02 → 2026-09-15 (USDTHB ถึง 09-14 · US10Y ถึง 09-11) |
| ค่าที่เก็บ | level ดิบหน่วยดั้งเดิม (USD / บาทต่อ USD / จุด / % yield) · ไม่แปลงสกุลเงิน |

- ใช้เป็น**รายเดือน** (ค่าสุดท้ายที่มีจริงของเดือน) · ราคาสินทรัพย์ → % return · VIX / US10Y → Δ ระดับ (ดู [หน้า 7](../pages/7-macro-chain.md))
- NaN 52–63 จุดต่อคอลัมน์ = วันหยุดคนละปฏิทิน (ปกติ ไม่ใช่บั๊ก) · เดือนสุดท้ายที่ยังไม่จบถูกทิ้งตอนคำนวณ
- Oil / Gold / Copper เป็น futures ต่อเนื่อง — มี roll gap เล็กน้อยในรอบเปลี่ยนสัญญา

---

## ช่วงข้อมูลที่ใช้ได้จริง

- **ตัวตั้งต้น**: MSCI มีถึง 2026-07-31 · NAVDate มีถึง 2026-08-24
- → NAV ~1 เดือนสุดท้ายไม่มีดัชนีจับคู่ ถูก inner join ตัดออก (ปกติ)
- NAVDate เก่าสุดที่พบคือ 2005 แต่ regression ใช้เฉพาะช่วงที่ MSCI มี (2021+) เท่านั้น
