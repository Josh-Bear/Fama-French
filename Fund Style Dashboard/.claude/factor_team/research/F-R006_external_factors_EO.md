# F-R006 — factor ภายนอกสำหรับกอง E และกอง O แยกกัน (งาน F5-EO · 5 สาย) · 2026-10-20

ผู้เขียน: factor-researcher · งาน F5-EO (BRIEF ข้อ 107–112) · **เชิงอธิบาย · ไม่นับ trial** · ชั้นที่ป้อน: spec `S012_L1EO_*` (designer)

**อ่านก่อนเขียน (ครบไฟล์):**
- role `factor-researcher.md` · `BRIEF.md` (ครบ 285 บรรทัด) · แผน `factors-hazy-thimble.md`
- `research/INDEX.md` · F-R001 · F-R004 (ครบ) · F-R002 / F-R003 / F-R005 (ส่วนหัว: ตรวจวิธี / ทำนาย จึงไม่เกี่ยวกับงานนี้)
- `reports/PHASE1_SUMMARY.md` · `L1_summary.md` · `L3_summary.md`
- `data/external/NOTES.md` · `data/QA_L0.md` · `data/QA_L0_ext.md` · `manifest.json` / `manifest_ext.json` · ชื่อคอลัมน์ของ `factors_weekly.parquet` (75 คอลัมน์) และ `factors_ext_weekly.parquet` (38 คอลัมน์)
- `config.py` (`SCORE_COUNTRY_CLEAN` · `STYLE_TICKERS` · `MACRO_YF_TICKERS`)

**ข้อจำกัดของรายงานนี้**
- หลักฐานส่วนใหญ่ยืนยันระดับ**บทคัดย่อ / หน้าข้อมูล / ผลค้น** และไม่ได้อ่านฉบับเต็มเรื่องใด (ป้ายอยู่ในบรรณานุกรม)
- **ไม่ได้เปิดดูผลตอบแทนกองหรือผลตอบแทน factor** ทุกตัวเลข corr ในรายงานนี้คือ **"คาดการณ์"** (เขียนกำกับไว้ทุกที่) ให้ data-engineer วัดจริงใน QA
- ตัวเลขจำนวนกองตามธีม = **ผมนับเองจากชื่อกองใน FundProfile** (regex บนชื่อ EN + รหัสกอง) ของ panel ระยะ 1 (E 357 · O 27) **ไม่ใช่ U_E / U_O ใหม่** (~209 / ~12 ซึ่งยังไม่ได้สร้าง) · regex พลาดได้ จึงใช้ได้แค่เป็นภาพคร่าวๆ
- ตัวเลขของชั้นก่อนยกมาจากรายงานชั้นนั้น (ไม่ได้ตรวจซ้ำเอง)
- ไม่พบหน้าเว็บที่มีข้อความสั่งการ (prompt injection)

---

## บทสรุป 5 บรรทัด

1. **กอง O ใน universe 9 เกณฑ์มีแค่ 2 ชนิด** คือ**ทอง** (16 กองใน panel · มีทั้งแบบป้องกันความเสี่ยงค่าเงินและไม่ป้องกัน) และ **REIT / อสังหาฯ ต่างประเทศ** (11 กอง: US · Global · Asia · Japan · Singapore) · **ไม่มีกองผสม** → factor ของ O ควรตั้งตาม**กลไก**ล่วงหน้า (ไม่ต้องคัดเลือกจากข้อมูล):
   - ทอง = ผลตอบแทนส่วนเกินของทองคิดเป็น USD (ใช้ GLD ซึ่งเป็นกองหลักของ K-GOLD) + factor FX เดิม (`SHV_THB − RF_BOT`) — loading ของ FX ควร ≈ สัดส่วนที่**ไม่** hedge
   - REIT = ตลาดหุ้นโลก + REIT ส่วนที่ตั้งฉากกับตลาด (REET มีแล้ว · VNQ ใหม่) + FX + TERM
2. **กอง E (FIF ทั้งหมด) ส่วนใหญ่ไม่ต้องดาวน์โหลดเพิ่ม** — หัวใจคือ**วิธีใช้ข้อมูลที่มี:**
   - factor ร่วมแกนเล็ก (ตลาดโลก · จีนที่ตั้งฉากกับตลาดโลก · TERM แทน PC3 ซึ่งคล้ายดอกเบี้ย)
   - บวก factor เฉพาะกลุ่ม **1 ตัวต่อกอง** ที่กำหนด**จากชื่อกองล่วงหน้า** (ประเทศ VIF-cleaned / ธีม ETF ที่มีอยู่) และ residualize บนแกนด้วย β จากช่วง train
   - เหตุผล: ระยะ 1 พบว่าดัชนีช่วยเฉพาะกองกลุ่มตัวเอง ใส่ให้ทุกกองแล้วไม่คุ้ม (ΔBIC +23 ถึง +31)
3. **style factor โลก:**
   - **Ken French Developed 5F + Mom รายวัน** (ข้อมูลถึง ส.ค. 2026) เหมาะเป็นชุด style หลักของกองโลก / สหรัฐฯ / ยุโรป / ญี่ปุ่น
   - **ตลาดเกิดใหม่ (EM) ของ Ken French มีแค่รายเดือน** → ใช้ **JKP รายวัน (region emerging · ถึง ธ.ค. 2025)** แทน
   - ห้ามใส่ Ken French คู่กับ style ETF 4 ตัวเดิมใน pool เดียวกัน (ซ้ำซ้อน · ③c เคย overfit: ΔBIC +53)
4. **กัน overfit (BRIEF 110):**
   - E: pool ล็อกล่วงหน้า ≤ 12 ตัว · factor ร่วม ≤ 6 ตัว (รวมตลาด) · forward stepwise บน train ด้วย median ΔBIC ข้าม**กลุ่มกองอิสระ** ≤ −2 + ด่าน pseudo-OOS ภายใน train + ด่าน placebo · factor เฉพาะกลุ่ม ≤ 1 ตัวต่อกอง และกลุ่มต้องมี ≥ 5 กอง
   - O: ชุดตายตัวตามกลไก ≤ 4 ตัวต่อกอง · **ไม่มีการคัดเลือก**
5. **ดาวน์โหลดจำเป็น 4 ไฟล์ (~6–17 MB ก่อนตัดช่วง · ส่วนใหญ่เป็นของ JKP):** KF Developed 5F รายวัน · KF Developed Mom รายวัน · JKP emerging themes รายวัน · Yahoo GLD / VNQ / VNQI · ส่วน "ถ้ามีก็ดี" อีก 6 รายการ · **ไม่มีข้อมูลที่ต้องจ่ายเงิน**
   - FX carry ทำไม่ได้: DBV เลิกกิจการ มี.ค. 2023 และ AQR มีแค่รายเดือน

---

## 0. สิ่งที่มีอยู่แล้ว และบทเรียนจากระยะ 1 (ห้ามเสนอซ้ำโดยไม่บอก)

### 0.1 ข้อมูล factor ที่มีในระบบ (อ่านจาก manifest / QA · ทุกตัวรายสัปดาห์ 2021-01-08 → 2026-07-31)
| กลุ่ม | คอลัมน์ | หน่วย | ใช้ในระยะ 1 |
|---|---|---|---|
| MSCI 28 (ETF ปิดเวลา NY → THB) | country 18 (รวม ACWI / World / EM / Asia ex Japan / China All / A / H) + sector 10 (**ไม่มี Real Estate**) | THB | L2 / L3 · ③b (EM−DM · US−ACWI) |
| style 4 | Momentum · Quality · Value · LowVol (MTUM/IMTM · QUAL/IQLT · VLUE/IVLU · ACWV · de-market ด้วย ACWI ETF) | USD relative | ③c (overfit) |
| macro 7 | Oil · Gold · USDTHB · Copper · DXY · VIX_d · US10Y_d | USD / Δ | ③c |
| ทอง | `Gold` (GC=F futures ต่อเนื่อง · USD) · `Gold_THB` | USD / THB | ③a |
| บอนด์ / credit สหรัฐฯ | AGG · IEF · SHV · LQD · HYG · EMB (USD และ THB) · DTB3 | USD / THB | ③a / ③b (TERM · IG · HY · EMD) |
| FX | `SHV_THB − RF_BOT` (ข้อ 20) | THB | ③ · ④a · L4 (บังคับ) |
| ไทย | TDEX_THB · TH yields 1Y/5Y/10Y/T-bill · RF_BOT | THB | ③b |
| ETF ส่วนขยาย 19 ตัว | QQQ · SOXX · ARKK · ICLN · IBB · KWEB · THD · EIDO · EPHE · EWM · EWS · **REET** · **IGF** · **DBC** · **GSG** · HEWJ · EWJ · HEFA · EFA (USD และ THB) | USD / THB | L3-C · C-prim (ETF ธีม 23/40 กองในกลุ่ม ACWI CD) |

### 0.2 บทเรียนที่ต้องใช้กับการออกแบบรอบนี้ (จากรายงานชั้น · ไม่ได้ตรวจซ้ำเอง)
| บทเรียน | ที่มา | ผลต่อข้อเสนอนี้ |
|---|---|---|
| ใส่ดัชนีเป็น factor ร่วมให้**ทุกกอง**ไม่คุ้ม (บล็อก 8 ภูมิภาค ΔBIC +31 · e ทั้ง 6 ตัว +22.9 · FX ใน α +5.5) แต่ดัชนีช่วย**กองกลุ่มของตัวเอง**ได้มาก (ΔR²_oos 0.07–0.55) | L2 · L3 · L4 | แยกเป็น 2 ชั้น: factor ร่วมแกนเล็ก + factor เฉพาะกลุ่ม |
| ③b (11 ตัว) / ③c (19 ตัว: + style 4 + VIX / US10Y / น้ำมัน / TH5Y) ได้ R² ในช่วงสูงแต่นอกช่วงต่ำ (gap 0.205 / 0.321) · r ดิบ 0.199 / 0.164 | L1 | style ETF + macro ทั้งชุด = overfit → จำกัด pool และจำนวน |
| C-blk คัดด้วย median ΔBIC ทุกกอง → ได้ ACWI CD (กลุ่มใหญ่สุด) ซึ่งชนะใน train แต่แพ้ใน test (R²_oos −0.024) | L3 §5.3 | median ข้ามทุกกองเอียงหากลุ่มใหญ่ → ใช้ median ข้าม**กลุ่มกองอิสระ** + ด่าน pseudo-OOS |
| pseudo-OOS ภายใน train ช่วยจับดัชนีที่เปราะ (UT · Europe) ได้ | L3 §3 | ใช้เป็นด่านหยุดของ stepwise |
| ①a PC2 ≈ จีน (0.82–0.87) · PC3 คล้าย −ΔUS10Y (0.69–0.78) · PC4 คล้ายอินเดีย / เวียดนาม | L1 · L2 | จีน และ TERM มีเหตุผลเป็น factor ร่วมที่ตีความได้ |
| α ของกองทองหายไปเมื่อเทียบ ref-③a (มี factor ทอง) | L4 ข้อ 83 / 87 | O ต้องมี factor ทองตามกลไก |
| ①a อธิบายกอง O ได้แย่ (R² 0.308 / oos 0.177) · ①c ดีกว่า (0.572 / 0.436) | L1 | O ต้องใช้ factor ของสินทรัพย์ที่ถือจริง |

### 0.3 ภาพ universe จากชื่อกอง (นับเองจาก FundProfile · panel ระยะ 1 · ไม่ใช่ U_E / U_O ใหม่)
- **E 357 กอง: FIF Flag = Y ทุกกอง** → ไม่มีกองหุ้นไทยใน E · TDEX / SET ไม่จำเป็นสำหรับงานนี้
- **O 27 กอง:**
  - ทอง 16 กอง: ASP-GOLD · BGOLD · ES-GOLD · ES-GOLDBULLION-H · ES-GOLDS · I-GOLD · IGOLD-G · K-GOLD-A(A) · KT-GOLD · KT-GOLDUH-A · LHGOLD-A · PRINCIPAL iGOLD-A · SCBGOLDHP · TGOLD · UOBSG-H · UOBSG-N
  - REIT / อสังหาฯ 11 กอง:
    - US: DAOL-USREIT · TUSREIT
    - Global: ES-GPROP · IREITG · LHPROPG-A · PRINCIPAL GREITs · TGREIT
    - Asia / APAC: ONE-APACPROP-RD · TAREIT
    - Japan: TJREIT
    - Singapore: ONEPROP-SG
  - **ไม่มีกองผสม** — ต่างจากที่คาดไว้ในคำสั่งงาน (ดู "ต้องให้ผู้ใช้ตัดสินใจ" ข้อ 5)
  - คู่ hedge / unhedge ที่อยู่**ต่าง family** ใน panel: KT-GOLD กับ KT-GOLDUH-A · UOBSG-H กับ UOBSG-N → ใช้ตรวจกลไก FX ได้ (คล้าย twin test)
  - K-GOLD ลงทุนผ่าน SPDR Gold Trust และระบุว่าป้องกันความเสี่ยงค่าเงิน "ทั้งหมดหรือเกือบทั้งหมด" (ผลค้น finnomena · ไม่ได้เปิดหนังสือชี้ชวน)
- **ธีมของ E** (คำสำคัญในชื่อ · กองหนึ่งนับได้หลายธีม):

| ธีม | จำนวนกอง (ประมาณ) | ข้อมูลที่ใช้แทนได้ (มีอยู่แล้ว) |
|---|---|---|
| GLOBAL / WORLD | 114 | — (ใช้ตลาดโลก + style) |
| tech / นวัตกรรม / ดิจิทัล | ~50 | ACWI IT · QQQ · ARKK |
| semiconductor | 4 | SOXX |
| AI / cyber / cloud / fintech | ≤ 3 ต่อธีม | (น้อยกว่า 5 → รวมเข้า tech) |
| จีน (ทุกแบบ) | 44 (A-share ~6 · tech ~8) | China All / A / H · KWEB |
| healthcare / biotech / genome | 22 | ACWI HC · IBB |
| clean energy / ESG / climate | ~25 (เป็น clean energy จริงราว 8–10) | ICLN |
| Europe | ~23 | MSCI Europe |
| US / NASDAQ | ~30 | MSCI USA · QQQ |
| Japan | ~19 | MSCI Japan · EWJ / HEWJ |
| ASEAN / Asia | ~22 | MSCI ASEAN · THD / EIDO / EPHE / EWM / EWS |
| India | 14 | MSCI India |
| Vietnam | 12 | MSCI Vietnam |
| small / mid cap | 12 (US 2 · Japan 3 · Europe 3 · อื่น) | — (ต้องใช้ SMB) |
| EM | 11 | MSCI EM (EM−DM) |
| infrastructure | 9 | IGF |
| dividend / income | 9 | — (ใช้ HML / RMW) |
| property (policy E) | 4–5 | REET |
| ทอง / เหมือง (policy E) | 2–3 | — (น้อยกว่า 5) |

---

## 1. ตารางจัดอันดับไอเดีย (คะแนน = หลักฐาน 1–3 × เข้ากับข้อมูล 1–3 ÷ ซับซ้อน 1–3)

### 1.1 กอง E
| # | ไอเดีย | สาย | หลักฐาน | เข้ากับข้อมูล | ซับซ้อน | คะแนน | สถานะที่แนะนำ |
|---|---|---|---|---|---|---|---|
| E0 | **ตลาดโลก** `ACWI_THB − RF_BOT` (แกนบังคับ) | — | 3 | 3 | 1 | 9.0 | บังคับ (ตัวเทียบทุกชุด) |
| **E1** | **จีนตั้งฉากกับตลาดโลก** e_CHINA = China All (THB) residualize บน ACWI (β จาก train) | ① | 3 | 3 | 1 | **9.0** | pool factor ร่วม |
| **E2** | **ประเทศ VIF-cleaned เป็น factor เฉพาะกลุ่ม** (India · Vietnam · Japan · Europe · USA−ACWI · ASEAN · China A−H) **กำหนดจากชื่อกอง** · residualize บนแกน | ① | 3 | 3 | 1 | **9.0** | ชั้นเฉพาะกลุ่ม |
| **E3** | **ธีม ETF ที่มีอยู่แล้วเป็น factor เฉพาะกลุ่ม** (ARKK / ACWI IT · ACWI HC · ICLN · IGF · REET · KWEB) กำหนดจากชื่อกอง | ⑤ | 2 | 3 | 1 | **6.0** | ชั้นเฉพาะกลุ่ม |
| **E4** | **TERM** = IEF_USD − SHV_USD (ดอกเบี้ยระยะยาวของหุ้น growth / tech) | ④ | 2 | 3 | 1 | **6.0** | pool factor ร่วม |
| E5 | FX `SHV_THB − RF_BOT` | ④ | 2 | 2 | 1 | 4.0 | pool (หรือบังคับ — ผู้ใช้เลือก) |
| E6 | EM − DM / USA − ACWI (มีอยู่ · ③b) | ① | 2 | 2 | 1 | 4.0 | pool (EM−DM) · USA−ACWI ไปอยู่ใน E2 |
| **E7** | **Ken French Developed 5F + Mom รายวัน** (SMB · HML · RMW · CMA · WML · USD long–short) | ② | 3 | 2 | 2 | **3.0** | pool factor ร่วม (≤ 3 ตัวผ่าน stepwise ได้) |
| E8 | **JKP emerging themes รายวัน** (value · momentum · size · low risk ฯลฯ) | ② | 2 | 2 | 2 | 2.0 | pool ≤ 2 ตัว (เลือกล่วงหน้า) |
| E9 | KF regional SMB (North America / Europe / Japan) ให้กองหุ้นเล็ก | ② | 2 | 2 | 2 | 2.0 | ถ้าดาวน์โหลด → ชั้นเฉพาะกลุ่ม small |
| E10 | AQR QMJ / BAB / HML-Devil รายวัน | ② | 2 | 1 | 2 | 1.0 | robustness เท่านั้น (ไม่อยู่ใน pool) |
| E11 | credit HYG − IEF / LQD − IEF | ④ | 2 | 1 | 1 | 2.0 | ไม่อยู่ใน pool E (คาดว่าซ้อนกับตลาดหุ้น) |
| E12 | ดอลลาร์ (DXY / broad / EM dollar index) | ④ | 2 | 1 | 1 | 2.0 | ไม่อยู่ใน pool E |
| E13 | ดัชนีเอเชียปิดตามเวลาท้องถิ่น (^HSI · ^N225 · ^NSEI ฯลฯ) แทน ETF ที่ปิดเวลา NY | ① | 1.5 | 2 | 3 | 1.0 | ไม่แนะนำรอบนี้ |
| E14 | commodity กว้าง (DBC / GSG) | ③ | 1 | 1 | 1 | 1.0 | ไม่แนะนำ |

### 1.2 กอง O
| # | ไอเดีย | สาย | หลักฐาน | เข้ากับข้อมูล | ซับซ้อน | คะแนน | สถานะที่แนะนำ |
|---|---|---|---|---|---|---|---|
| **O1** | **ทอง:** GOLD_XS = GLD_USD − SHV_USD **+ FX** (กองไม่ hedge loading FX ≈ 1 · กอง hedge ≈ 0) | ③④ | 3 | 3 | 1 | **9.0** | ชุดตายตัวของกองทอง |
| **O2** | **REIT:** MKT (ACWI_THB − RF) + REIT_e (REET_USD − SHV_USD residualize บนตลาด) + FX | ③ | 2 | 3 | 1 | **6.0** | ชุดตายตัวของกอง REIT |
| O3 | TERM (IEF − SHV) ให้กอง REIT | ④ | 2 | 2 | 1 | 4.0 | ใส่ในชุด REIT (ตัวที่ 4) |
| O4 | REIT ตามภูมิภาคจากชื่อกอง (US → VNQ · ex-US → VNQI · Japan → 1343.T · Singapore → CLR.SI) | ③⑤ | 1.5 | 2 | 2 | 1.5 | ภาคผนวก (1–2 กองต่อภูมิภาค) |
| O5 | ทอง: Gold_THB − RF ตัวเดียว (ไม่แยก FX) | ③ | 3 | 2 | 1 | 6.0 | ตัวเทียบของ O1 (แสดงคุณค่าของการแยก FX) |
| O6 | ดอกเบี้ยแท้จริง (TIPS 10Y · FRED DFII10) ให้กองทอง | ④ | 1 | 1 | 1 | 1.0 | ไม่แนะนำ |
| O7 | commodity กว้างให้กองทอง | ③ | 1 | 1 | 1 | 1.0 | ไม่แนะนำ |
| O8 | credit (HYG − IEF) ให้กอง REIT | ④ | 2 | 1 | 1 | 2.0 | ภาคผนวกถ้าจำเป็น |
| O9 | multi-asset / balanced proxy | ③ | — | 0 (ไม่มีกองผสมใน O) | — | — | ไม่ต้องทำ |

**อันดับ 1 ต่อกลุ่ม:** E = E1 / E2 (ประเทศ VIF-cleaned ที่ตั้งฉากกับตลาดโลก ใช้ตามชื่อกอง) · O = O1 (ทอง USD + FX)

---

## 2. รายละเอียดต่อไอเดีย

### สาย ① — factor รายประเทศจากชุด VIF-cleaned (E1 · E2 · E6 · E13) · **ไม่ต้องดาวน์โหลด**

| หัวข้อ | เนื้อหา |
|---|---|
| ไอเดีย + กลไก | กอง FIF ไทยส่วนมากถือหุ้นประเทศ / ภูมิภาคเดียว (จีน 44 · Japan ~19 · Europe ~23 · India 14 · Vietnam 12) · ผลตอบแทนเป็นบาทของกองพวกนี้ = ตลาดโลก + **ส่วนที่ประเทศนั้นเคลื่อนต่างจากโลก** · ส่วนหลังเป็นแหล่ง covariance ร่วมของกองกลุ่มนั้นที่ตลาดโลกไม่จับ |
| หลักฐาน | Heston–Rouwenhorst 1994 · Brooks–Del Negro · BHZ 2009 (F-R004: country effect เด่น · ครึ่งหนึ่งเป็น region effect) · **Hollstein 2022 (JFQA 57(1))**: factor model แบบ local ให้ \|α\| ต่ำกว่าแบบ regional (+1.1 จุด %/ปี) และแบบ global (+1.7 จุด) ในหลายตลาดพัฒนาแล้วและเกิดใหม่ และช่องว่างไม่แคบลงในช่วงหลัง · FF 2012 / 2017: factor แบบ local / regional ดีกว่า global (F-R001 + บทคัดย่อ) · หลักฐานภายใน: L2 / L3 ส่วนเพิ่มของดัชนีในกองหลัก 0.07–0.55 · ความแรง: **แข็ง** (country effect) / ปานกลาง (การใช้กับกองทุน) |
| เข้ากับข้อมูล | สูง — `config.SCORE_COUNTRY_CLEAN` 11 ตัว (BRAZIL · CHINA_A · CHINA_H · EUROPE · INDIA · JAPAN · KOREA · ASEAN · TAIWAN · USA · VIETNAM) + ACWI · ทั้งหมดเป็น THB อยู่แล้ว · ช่วง 2021–2025 ครบ |
| ชั้น | S012 (E) |
| วิธีสร้าง | **(ก) E1 จีนร่วม:** e_CHINA,t = China All_t − (a + b·ACWI_t + c·ACWI_t−1) · a, b, c จาก train 2021–2023 · ตรึงในช่วง test · ใส่ใน pool factor ร่วม · **(ข) E2 เฉพาะกลุ่ม:** ตารางจับคู่ชื่อกอง → ดัชนี ที่ designer ล็อกก่อนรัน (ตัวอย่าง: CHINA → e_CHINA + (A−H) สำหรับชื่อที่มี A-SHARE · INDIA → e_INDIA · VIETNAM → e_VIETNAM · JAPAN → e_JAPAN · EURO/EUROPE → e_EUROPE · US/USA/S&P → e_USA · ASEAN → e_ASEAN) · e_j residualize บน**แกน factor ร่วมที่ stepwise เลือกแล้ว** ด้วย β จาก train (แบบ L3-B) · ใส่ให้เฉพาะกองที่ชื่อตรง ≤ 1 ตัว · กลุ่มที่มี < 5 กองใน U_E → ไม่ให้ (KOREA 2 · TAIWAN 1 · BRAZIL 0 คาดว่าตก) · **(ค) E6:** EM − DM (มีอยู่) อยู่ใน pool · USA − ACWI ย้ายไปเป็น e_USA ใน (ข) |
| ข้อควรระวัง collinearity | (1) **ห้ามใส่ ACWI คู่กับ 11 ประเทศแบบดิบทั้งหมด** — ACWI ≈ ผลรวมถ่วงน้ำหนักของประเทศ (L2: VIF ของ ACWI 54,279 · USA 8,907 ในชุด M28) · ชุด 11 ตัวลำพังมี VIF ≤ 2.70 (L3 A0) แต่เมื่อเติม ACWI จะสูงขึ้นมาก (คาด) (2) USA ≈ 60% ของ ACWI → ใช้แค่ e_USA ห้ามใช้ USA ดิบคู่กับ ACWI (3) China All ≈ ส่วนผสมของ A และ H → ใช้ e_CHINA (All) + (A − H) ไม่ใช้ทั้ง 3 ตัว (4) ความตั้งฉากจริงเฉพาะใน train (L3: corr(e, f) ช่วง test สูงสุด 0.548) → รายงาน corr ช่วง test (5) คำนวณ VIF **รวม lag ของ Dimson** (L3: VIF แบบ Dimson สูงกว่า lag 0 · 5.63 / 6.00 เทียบ 4.49 / 4.67) |
| แปลงบาท / เวลาปิด / ลงทุนได้ | เป็น THB อยู่แล้ว · e_j และ C − ACWI เป็น long–short ระหว่างดัชนีบาท (ค่าเงินดอลลาร์หักล้างกันเกือบหมด เหลือค่าเงินท้องถิ่นเทียบตะกร้า ACWI) · "MSCI" ในระบบมาจาก ETF ที่ปิดเวลา NY → Dimson lag 1 · e_j **ลงทุนไม่ได้** (มี β ที่ประมาณจากข้อมูล · long–short) |
| ความเสี่ยงซ้ำ (คาดการณ์) | e_CHINA กับ ①a PC2: corr ~0.7–0.85 (PC2 ≈ China All 0.82 ใน train) · e_INDIA / e_VIETNAM กับ PC4 ของ ①a / PC3–4 ของ ①c: ~0.5–0.7 · ในชุด PCA ของ E ล้วน (S012 (a)) ตัวเหล่านี้จะถูก PC ดูดไปคล้ายเดิม → การเทียบ (a) กับ (b) จะตอบว่า "PCA ของ E ล้วนตีความเป็นประเทศได้แค่ไหน" |
| ร่างสมมติฐาน | H-E1: e_CHINA ผ่าน stepwise เป็นตัวแรกหรือตัวที่สอง และให้ ΔR²_oos (กอง E ทั้งหมด) > 0 · H-E2: factor เฉพาะกลุ่มจากชื่อกองให้ median ΔR²_oos ในกลุ่มของตัวเอง ≥ 0.02 ในทุกกลุ่มที่มี ≥ 5 กอง และใกล้กับผลของ L2 primary (ซึ่งเลือกโดยใช้ข้อมูล) · ถ้าชื่อกองให้ผลต่ำกว่า L2 primary มาก แปลว่าชื่อกองไม่ตรงกับสิ่งที่ถือจริง (แบบ Sensoy 2009) |

**E13 (ไม่แนะนำรอบนี้):** ดัชนีเอเชียที่ปิดตามเวลาท้องถิ่นจาก Yahoo (^HSI · 000300.SS · ^N225 · ^NSEI · ^KS11 · ^TWII) อาจลดปัญหาเวลาปิดไม่ตรงกัน (Goetzmann–Ivković–Rouwenhorst 2001 · F-R001)
- ข้อเสีย:
  - เป็นดัชนีราคา ไม่รวมปันผล
  - ต้องแปลงค่าเงินหลายสกุล
  - NAV ของ feeder ไทยมักอิงราคากองหลักวันก่อน (ยังไม่ยืนยันแหล่ง) → ไม่แน่ว่าเวลาจะตรงกว่าเดิม
  - เพิ่มคอลัมน์มาก
- เก็บไว้เป็นงานถัดไป ถ้า lead diagnostic ของ S012 ชี้ว่าการจัดสัปดาห์คลาดกัน

### สาย ② — style factor โลก (E7 · E8 · E9 · E10)

| หัวข้อ | เนื้อหา |
|---|---|
| ไอเดีย + กลไก | กอง E ไทยเอียงไปทาง growth / นวัตกรรม (ชื่อ tech ~50 กอง) และมีกองหุ้นเล็ก (12) / ปันผล (9) → exposure ต่อ value (HML ติดลบ) · profitability / investment (บริษัทโตเร็วที่ยังขาดทุน = RMW / CMA ติดลบ) · size · momentum เป็นแหล่ง covariance ร่วมข้ามประเทศที่ตลาดโลกไม่จับ |
| หลักฐาน | **Busse–Goyal–Wahal 2014 (RoF 18(2))**: ประเมินกองหุ้นโลกที่ลงทุนในสหรัฐฯ ด้วย model ที่มี size / value / momentum แยกตลาดพัฒนาแล้วกับเกิดใหม่ → แทบไม่มี α โดยรวม · **Fama–French 2017 (JFE 123)**: 5 factor ในอเมริกาเหนือ ยุโรป เอเชียแปซิฟิก (ญี่ปุ่นไม่มีผล profitability / investment) · **Hou–Karolyi–Kho 2011 (RFS 24(8))**: momentum + cash flow-to-price + ตลาดโลก อธิบายผลตอบแทนหุ้น 49 ประเทศดีกว่า global CAPM / FF3 · **Jensen–Kelly–Pedersen 2023 (JF 78(5))**: factor ส่วนใหญ่ replicate ได้ · จัดเป็น 13 theme · ใช้ได้นอกตัวอย่างใน 93 ประเทศ · AMP 2013 / FF 2012 (F-R001) · **ข้อโต้แย้ง:** Cremers–Petajisto–Zitzewitz 2013 (F-R001) ชี้ว่า factor แบบ FF ให้ α ไม่เป็นศูนย์แม้กับดัชนี passive → ใช้ style เป็น**ตัวเสริม**ของดัชนีที่ลงทุนได้ ไม่ใช่ตัวแทน · Hollstein 2022: factor แบบ global / regional แย่กว่า local · ความแรง: **แข็ง** (style ในหุ้น) / **ปานกลาง** (style อธิบาย covariance ของกอง FIF ไทย — ไม่พบงานกับกองไทยโดยตรง) |
| เข้ากับข้อมูล | **Ken French (KF):** Developed / Developed ex US / Europe / Japan / Asia Pacific ex Japan / North America มี **รายวัน** (3F · 5F · Mom) · ข้อมูลรายวัน 1990-07-01 → **2026-08-31** · USD · rf = T-bill สหรัฐฯ 1 เดือน · **Emerging มีแค่รายเดือน** (5F · Mom · ไม่มี 3F) · Asia Pacific ex Japan ของ KF = ออสเตรเลีย / ฮ่องกง / นิวซีแลนด์ / สิงคโปร์เท่านั้น (ไม่ครอบจีน อินเดีย เกาหลี ไต้หวัน อาเซียน) · **JKP:** factor 153 ตัว · 13 theme · 93 ประเทศ + region (usa · world · developed · emerging) · **รายวันหรือรายเดือน** · ถ่วงแบบ capped VW / VW / EW · อัปเดตถึง **ธ.ค. 2025** (ข่าวในเว็บ เม.ย. 2026) · สัญญาอนุญาต CC BY-NC 4.0 · ไม่ต้อง login สำหรับ factor returns · **AQR:** QMJ / BAB / HML-Devil รายวัน (หน้าลงวันที่ 31 ก.ค. 2026 · อัปเดตรายเดือน · ไฟล์ .xlsx · สหรัฐฯ + 23 ประเทศ) |
| ชั้น | S012 (E) |
| วิธีสร้าง | (1) ใช้ factor long–short **USD ไม่แปลงบาท** (BRIEF 110) · ไม่ใช้ Mkt−RF ของ KF (ซ้ำกับ ACWI) (2) **รวมเป็นรายสัปดาห์:** ทบต้นผลตอบแทนรายวัน Π(1 + r_d) − 1 ของวันทำการใน (ศุกร์ก่อน, ศุกร์นี้] · ถ้าศุกร์เป็นวันหยุดใช้วันล่าสุด ≤ ศุกร์ (asof แบบ L0) · KF / JKP เป็นหน่วย % → หาร 100 (3) **ตรวจรายเดือน:** รวมรายวันเป็นสิ้นเดือน แล้วเทียบกับไฟล์รายเดือนทางการของ KF เป็น QA (คาด corr > 0.99) (4) **pool ที่เสนอ (ล็อกล่วงหน้า):** KF Developed SMB · HML · RMW · CMA · WML (5 ตัว) + JKP emerging **2 theme ที่เลือกจากวรรณกรรมก่อนเห็นข้อมูล** (แนะนำ value และ momentum เพราะ AMP 2013 / HKK 2011 มีหลักฐานข้ามประเทศแข็งสุด) (5) KF regional SMB (E9) ใช้เป็น factor เฉพาะกลุ่มให้กองที่ชื่อมี SMALL / SMID / MID ตามภูมิภาคในชื่อ (ถ้าดาวน์โหลด) (6) AQR (E10) เป็น robustness: แทน HML ด้วย HML-Devil และ RMW ด้วย QMJ ในชุดที่ชนะ แล้วดูว่าข้อสรุปเปลี่ยนไหม — **ไม่อยู่ใน pool** |
| แปลงบาท / เวลาปิด / ลงทุนได้ | ไม่แปลง · ผลตอบแทนรายวันของพอร์ตหลายประเทศรวมราคาปิดต่างเวลาและแปลง USD (วิธีแปลงรายวันของ KF ยังไม่ยืนยันแหล่ง) → Dimson lag 1 · ป้าย **"ลงทุนไม่ได้"** |
| ความเสี่ยงซ้ำ (คาดการณ์) | KF HML กับ Value ETF (de-market) ~0.4–0.7 · KF WML กับ Momentum ETF ~0.4–0.7 · KF RMW กับ Quality ETF ~0.3–0.6 · KF Mkt (Developed) กับ ACWI ETF USD > 0.95 (จึงไม่ใช้) · JKP emerging value กับ KF HML ~0.2–0.4 · **กฎ: ห้ามมี style ETF 4 ตัวเดิมกับ KF อยู่ใน pool เดียวกัน** (แนะนำ KF เป็นหลัก เพราะเป็น long–short มาตรฐานที่ไม่ขึ้นกับค่าธรรมเนียม ETF และการ blend 60/40 ของแอป · style ETF เป็นตัวเทียบ) |
| ร่างสมมติฐาน | H-E7a: HML มี loading ติดลบที่มีนัยในกองชื่อ tech / นวัตกรรมเกินครึ่ง (BH ภายใน factor) · H-E7b: เมื่อมีตลาดโลก + จีน + TERM อยู่แล้ว style KF ผ่าน stepwise ได้ไม่เกิน 2 ตัว และ ΔR²_oos รวม ≤ 0.02 (ความคาดหมาย — ③c ชี้ว่า style ช่วยนอกช่วงน้อย) · H-E8: JKP emerging ให้ส่วนเพิ่มเฉพาะกอง EM / เอเชีย ไม่ใช่กองโลก |

### สาย ③ — สินทรัพย์ทางเลือก (O1 · O2 · O4–O7 · E3 ส่วน IGF / REET)

**O1 ทอง**
| หัวข้อ | เนื้อหา |
|---|---|
| ไอเดีย + กลไก | กองทองไทยเป็น feeder ของกองทองคำแท่ง (K-GOLD → SPDR Gold Trust · ผลค้น) · ตามสมการ covered interest parity (CIP · F-R004 L4-1) ผลตอบแทนส่วนเกินเป็นบาทมีดังนี้: <br>• **ไม่ hedge:** R − rf_TH ≈ (R_gold$ − r_US) + (ΔUSDTHB + r_US − rf_TH) = **GOLD_XS + FX** <br>• **hedge เต็ม:** R − rf_TH ≈ **GOLD_XS** <br>→ loading ของ FX = สัดส่วนที่ไม่ hedge · α ควร ≈ −TER |
| หลักฐาน | กลไกตามนิยาม (ไม่ใช่ข้ออ้างเชิงประจักษ์) · Greger–Scholz (SSRN 4565638 · F-R004): factor model ที่ไม่มี hedging factor วัดกอง hedge ผิด · Sharpe 1992 / CPZ 2013 (F-R001): model ที่ใช้ดัชนีลงทุนได้ตรงกลยุทธ์ · หลักฐานภายใน: α ของกองทองหายเมื่อใช้ ref-③a (L4) · ความแรง: **แข็ง** (กลไก) |
| เข้ากับข้อมูล | มี `Gold` (GC=F) · `Gold_THB` · SHV · RF_BOT แล้ว · **ข้อเสนอใหม่: GLD** เพราะ NAV ของ GLD อิง LBMA Gold Price PM (15:00 London · ตาม GLD FAQ) ซึ่งตรงกับที่กองหลักถือ ส่วน GC=F เป็น futures ต่อเนื่อง ซื้อขายที่ระดับพรีเมียมเหนือ spot และมีรอยต่อตอน roll (`config.py` ระบุว่ามี roll gap ใน BZ=F · ของ GC=F ยังไม่ได้ตรวจ) |
| วิธีสร้าง | GOLD_XS = r(GLD_USD) − r(SHV_USD) · FX เดิม (ข้อ 20) · ทั้งสองตัวรายสัปดาห์ · Dimson lag 0 + 1 · ตรวจคู่ twin: KT-GOLD กับ KT-GOLDUH-A · UOBSG-H กับ UOBSG-N → loading FX คาด ≈ 0 กับ ≈ 1 (บรรยาย) |
| แปลงบาท / เวลาปิด / ลงทุนได้ | แยกเป็น USD excess + FX (เทียบเท่าการแปลงบาท แต่แยกผลของการ hedge ออกมาได้) · GLD ซื้อขายที่ NY (NAV อิงราคา London PM) → Dimson lag 1 · GLD ลงทุนได้ (long) · FX = การถือ SHV เป็นบาท (ลงทุนได้ในทางทฤษฎี) · ระยะ 1 ห้ามสรุปว่าลงทุนได้ |
| ความเสี่ยงซ้ำ (คาดการณ์) | GLD กับ Gold (GC=F) รายสัปดาห์ > 0.98 → **ใช้แทน ไม่ใช้คู่** · GOLD_XS + FX ≈ Gold_THB − RF_BOT (เท่ากันเกือบพอดีตามนิยาม) · ทองกับหุ้นโลก ~0–0.3 |
| ร่างสมมติฐาน | H-O1a: กองทองทุกกองมี β ของ GOLD_XS ใน [0.85, 1.05] · H-O1b: loading ของ FX แยกกอง hedge (≈ 0) กับกองไม่ hedge (≈ 1) ได้ตรงกับชื่อ / class (-H / UH) · H-O1c: median R²_oos ของกองทอง ≥ 0.90 และ \|α\| ≈ TER (ความคาดหมาย ไม่ใช่ผล) |

**O2 / O3 / O4 REIT**
| หัวข้อ | เนื้อหา |
|---|---|
| ไอเดีย + กลไก | กอง REIT ถือหุ้น REIT จดทะเบียน → ผลตอบแทน = ตลาดหุ้น + ส่วนเฉพาะของอสังหาฯ (ค่าเช่า / cap rate) + ความไวต่อดอกเบี้ยระยะยาว + ค่าเงิน · ชุด MSCI sector ของแอป**ไม่มี Real Estate** (`config.py`) จึงเป็นช่องว่างจริง |
| หลักฐาน | **Clayton–MacKinnon 2003 (JREFE 27(1))**: แยกความผันผวนของ REIT เป็นส่วนของหุ้น บอนด์ อสังหาฯ · ทศวรรษ 1990 REIT สัมพันธ์กับหุ้นเล็กและ factor อสังหาฯ มากขึ้น · ส่วนที่ factor อธิบายไม่ได้เพิ่มขึ้นตามเวลา · งานแย้ง (Lee · PRRES) ไม่พบว่า REIT "เหมือนอสังหาฯ มากขึ้น" หลังปี 1992 · ผลค้นงานอื่น: REIT มาเลเซียขับโดยตลาดหุ้นในประเทศเป็นหลัก ดอกเบี้ยรอง · งานสหรัฐฯ: หุ้น + บอนด์อธิบายได้ราว 60% · ความไวต่อดอกเบี้ยขัดกันระหว่างงาน (Chen–Tzang 1988 vs Liang et al. 1995 · ผ่านแหล่งรอง) · ความแรง: **ปานกลาง** |
| เข้ากับข้อมูล | REET (Global REIT · มีแล้ว) · IEF / SHV (มีแล้ว) · **ใหม่: VNQ** (US REIT · 2 กอง: DAOL-USREIT · TUSREIT) · **VNQI** (ex-US) · ถ้ามีก็ดี: **1343.T** (NEXT FUNDS TSE REIT · เริ่ม ก.ย. 2008 · ปิดเวลาโตเกียว) · **CLR.SI** (Lion-Phillip S-REIT · เริ่ม 2017-10-30 · ปิดเวลาสิงคโปร์) — สองตัวหลังต้องใช้ค่าเงิน JPY / SGD เพิ่ม |
| วิธีสร้าง | **ชุดตายตัว (ไม่คัดเลือก):** MKT = ACWI_THB − RF_BOT · REIT_e = (REET_USD − SHV_USD) residualize บน ACWI ด้วย β จาก train · FX · TERM = IEF_USD − SHV_USD → 4 factor × Dimson 2 = 8 coefficient + α บน 156 สัปดาห์ · **ภาคผนวก O4:** กองที่ชื่อระบุภูมิภาคได้ tilt เพิ่ม 1 ตัว (US: VNQ − REET · Japan: 1343.T − REET · Singapore: CLR.SI − REET) — 1–2 กองต่อภูมิภาค จึงเป็นรายกองเชิงบรรยาย |
| แปลงบาท / เวลาปิด / ลงทุนได้ | REIT_e / TERM เป็น long–short USD (ไม่แปลง) · FX แยกตัว · VNQ / REET / VNQI ปิดที่ NY · 1343.T / CLR.SI ปิดเวลาเอเชีย (ใกล้เวลา NAV ไทยกว่า) · Dimson lag 1 ทุกตัว · REIT_e / TERM ลงทุนไม่ได้ (long–short) |
| ความเสี่ยงซ้ำ (คาดการณ์) | REET กับ ACWI ~0.6–0.8 (จึง residualize) · VNQ กับ REET ~0.85–0.95 · TERM กับ −US10Y_d > 0.9 · REIT_e กับ ACWI UT ~0.3–0.5 |
| ร่างสมมติฐาน | H-O2: ชุด O2 + TERM ให้ median R²_oos ของกอง REIT สูงกว่า ①a อย่างน้อย 0.15 (①a ทั้ง O: 0.177) · H-O3: TERM มี loading บวก (REIT ได้ประโยชน์เมื่อดอกเบี้ยลง) ในกอง REIT ส่วนใหญ่ · H-O4: กอง US REIT มี β ต่อ (VNQ − REET) > 0 |

**O5–O7 / E3 / E14 (สรุป)**
- **O5:** ทองแบบ Gold_THB ตัวเดียว = ตัวเทียบของ O1 → แสดงว่าการแยก FX ช่วยกองที่ hedge แค่ไหน
- **O6 ดอกเบี้ยแท้จริง (ไม่แนะนำ):**
  - Erb–Harvey 2013 (FAJ) บอกว่าทองป้องกันเงินเฟ้อได้ไม่ดีในช่วงลงทุนจริง
  - ความสัมพันธ์ทอง–ดอกเบี้ยแท้จริงที่ยกกันมาเป็นแหล่งรอง · บทวิเคราะห์ตลาดชี้ว่าความสัมพันธ์นี้แตกตั้งแต่ปลายปี 2022 (ไม่ใช่งานวิชาการ)
  - กองทองถือทอง ราคาทองจึงรวมผลของดอกเบี้ยแท้จริงไว้แล้ว
  - แบ่ง train / test ตรงจุดที่ความสัมพันธ์เปลี่ยน → เสี่ยงไม่เสถียรสูง
- **O7 commodity กว้าง:** ทองไม่ใช่ตะกร้าสินค้าโภคภัณฑ์ → ไม่ใช้
- **E3 ส่วน IGF / REET:**
  - กอง E ชื่อ INFRA 9 กอง → IGF residualize บนแกน
  - กองอสังหาฯ policy E 4–5 กอง → REET
  - คาดว่า IGF กับ ACWI UT corr ~0.7–0.85 → IGF อาจแทน UT (ใน L3 UT ติดป้าย "เปราะ") ได้ตรงกลุ่มกว่า
- **E14 commodity กว้าง:** มีกอง energy / เหมือง ≤ 3 กอง → ไม่ใช้

### สาย ④ — ดอกเบี้ย / credit / FX (E4 · E5 · E11 · E12 · O3 · O8)

| ไอเดีย | กลไก + หลักฐาน | ข้อมูล | E / O | ความเสี่ยงซ้ำ (คาดการณ์) | สถานะ |
|---|---|---|---|---|---|
| **TERM** = IEF_USD − SHV_USD | หุ้น growth / tech มี duration ยาว → ไวต่อดอกเบี้ยระยะยาว (แนวคิด equity duration · Dechow–Sloan–Soliman 2004 · **ยังไม่ยืนยันแหล่ง**) · TERM ของ Fama–French 1993 / EGB 1995 (F-R001) · หลักฐานภายใน: PC3 ของ ①a คล้าย −ΔUS10Y (L1 / L2) · REIT ไวต่อดอกเบี้ย (หลักฐานขัดกัน) · ความแรง **ปานกลาง** | มีแล้ว · USD long–short · ปิด NY · ลงทุนไม่ได้ (long–short) | E (pool) · O (ชุด REIT) | กับ −US10Y_d > 0.9 · กับ ①a PC3 ~0.6–0.8 · กับ AGG_USD ~0.8 | **แนะนำ** · ใช้แทน US10Y_d (ลงทุนไม่ได้ · ③c) |
| **FX** = SHV_THB − RF_BOT | CIP (F-R004 L4-1) · กอง E ชื่อมี -H / HEDGE ~25 กอง · UH ~9 กอง | มีแล้ว | O **บังคับ** · E pool หรือบังคับ | กับ USDTHB > 0.95 · กับ DXY ~0.4–0.6 | L4 พบว่า FX ทำ ΔBIC ของ E แย่ลง (+5.5) → E ให้ผู้ใช้เลือก (ข้อ 6) |
| credit HYG − IEF / LQD − IEF | DEF ของ FF 1993 (ยังไม่ยืนยันแหล่ง) · IG / HY ใน ③b ไม่ช่วยนอกช่วง | มีแล้ว (IG/HY OAS ของ FRED มีแค่ 2023-10+ → ใช้ ETF) | O ภาคผนวก | HY − IEF กับตลาดหุ้น ~0.5–0.7 | ไม่อยู่ใน pool E |
| ดอลลาร์ (DXY · Fed broad DTWEXBGS · EM DTWEXEMEGS) | **Verdelhan 2018 (JF 73(1))**: factor ดอลลาร์ + carry อธิบายค่าเงินคู่รายเดือนได้ 18–80% · Lustig–Roussanov–Verdelhan 2011 (F-R001) · แต่ MSCI THB รวมผลของค่าเงินท้องถิ่นไว้แล้ว → ส่วนเพิ่มต่อกองคาดว่าน้อย | DXY มีแล้ว · DTWEXEMEGS รายวันถึง 2026-10-16 (หน้า FRED) · DTWEXBGS ไม่ได้เปิดหน้า | E / O ภาคผนวก | DTWEXEMEGS กับ USDTHB ~0.5–0.7 | ถ้ามีก็ดี (ไฟล์เล็ก) |
| FX carry | Lustig et al. 2011 · Verdelhan 2018 | **DBV (Invesco DB G10 Currency Harvest) เลิกซื้อขาย 3 มี.ค. 2023** (SEC filing ผ่านผลค้น) · AQR VME มีแค่รายเดือน → ไม่มีอนุกรมรายวันฟรีที่ครอบ 2021–2025 | — | — | **ไม่ควรลอง** (สอดคล้อง F-R001) |
| ดอกเบี้ยไทย (ΔTH yields) | กองไทยที่ hedge ได้ส่วนต่างดอกเบี้ย (อยู่ใน FX แล้ว) · ไม่มีกอง E / O ที่ถือบอนด์ไทย | มีแล้ว | — | — | ไม่ใช้ (ตัด F ออกแล้ว) |
| EM debt (EMB) | ไม่ตรงกับ E / O | มีแล้ว | — | — | ไม่ใช้ |

### สาย ⑤ — ธีม / sector ที่กองไทยถือเยอะ (E3) · **ส่วนใหญ่ใช้ ETF ที่มีอยู่แล้ว**

| หัวข้อ | เนื้อหา |
|---|---|
| ไอเดีย + กลไก | กองธีมถือหุ้นกลุ่มแคบที่ตลาดโลกและ sector MSCI ไม่ตรง (L2 / L3: β ของกลุ่ม ACWI CD ไม่เสถียร r 0.15–0.25 · C-prim เลือก ETF ธีมให้ 23 / 40 กองในกลุ่มนี้) · ดัชนีธีมที่ลงทุนได้และตรงกลยุทธ์ = แนว index-based model (Sharpe 1992 · CPZ 2013) |
| หลักฐาน | **Ben-David–Franzoni–Kim–Moussawi 2023 (RFS 36(3))**: ETF ธีม / เฉพาะทางถือหุ้นที่มีลักษณะเด่น ผลตอบแทนอดีตสูง เป็นข่าว และมี sentiment · หลังเปิดตัวแพ้ benchmark ราว 30% (ปรับความเสี่ยง) ใน 5 ปีแรก → กองธีมมีแหล่ง covariance ร่วม (หุ้นกระแสเดียวกัน) ที่ factor มาตรฐานไม่จับ · **Sensoy 2009 (JFE 92(1))**: ราว 1/3 ของกองหุ้นสหรัฐฯ ระบุ benchmark ไม่ตรงกับสไตล์จริง → **การจับคู่ด้วยชื่อกองมีโอกาสผิด** ต้องตรวจ · ไม่พบงานที่ทดสอบ ETF ธีมกับกองธีมไทยโดยตรง · ความแรง: **อ่อน–ปานกลาง** |
| เข้ากับข้อมูล | **มีอยู่แล้วเกือบทั้งหมด:** ARKK (นวัตกรรม) · QQQ · SOXX · ACWI IT · ACWI HC · IBB · ICLN · KWEB · IGF · REET · ธีมที่มี < 5 กอง (AI · cyber · cloud · fintech · genome · STAR · EM ex China) **ไม่ต้องดาวน์โหลด** — ยุบเข้าธีมใหญ่ |
| วิธีสร้าง | ตารางจับคู่ชื่อกอง → ETF / ดัชนี ที่ designer **ล็อกก่อนรัน** (ไม่ดูผลตอบแทน) · ตัวอย่าง: INNOVAT / DISRUPT / NEXTGEN → ARKK · TECH / DIGITAL / AI / ROBOT / CYBER / CLOUD / SEMI → ACWI IT (หรือ SOXX ถ้ากลุ่ม SEMI ≥ 5) · HEALTH / MEDIC / BIOTECH / GENOM → ACWI HC · CLEAN / RENEW / NEWENGY / CLIMATE → ICLN (ESG ทั่วไปไม่ได้ factor) · INFRA → IGF · PROP / REIT → REET · CHINA + TECH / INTERNET → KWEB · กติกาเมื่อชื่อเข้าหลายกลุ่ม (เช่น CHINA TECH) ต้องล็อกลำดับไว้ล่วงหน้า (ข้อเสนอ: กองประเทศเดียวใช้ประเทศ ยกเว้นมีคำธีมที่มี ETF เฉพาะ เช่น KWEB) · residualize ETF บนแกน factor ร่วม (β จาก train) · ใช้ THB version (ค่าเงินถูก residualize ออกไปกับ ACWI_THB ส่วนใหญ่) |
| แปลงบาท / เวลาปิด / ลงทุนได้ | `<ETF>_THB` มีแล้ว · ปิดที่ NY → Dimson lag 1 · ETF ลงทุนได้ แต่ส่วน residual ลงทุนไม่ได้ |
| ความเสี่ยงซ้ำ (คาดการณ์) | ARKK กับ QQQ ~0.8 · QQQ กับ ACWI IT ~0.9 · ICLN กับ ACWI UT ~0.4–0.6 · ทุกตัวกับ ①a PC1 สูง (จึงต้อง residualize) |
| ร่างสมมติฐาน | H-E3a: ในกลุ่มธีมที่มี ≥ 5 กอง factor ธีมจากชื่อให้ median ΔR²_oos ≥ 0.02 (เทียบแกน) · H-E3b: สัดส่วนกองที่ factor ธีม "ไม่ช่วย" (ΔR²_oos ≤ 0) ใช้ประเมินว่าชื่อกองหลอกแค่ไหน (แบบ Sensoy) — รายงานเป็นตัวเลขบรรยาย |

---

## 3. ไอเดียที่ไม่ควรลอง (รอบนี้)
| ไอเดีย | เหตุผล |
|---|---|
| Ken French Emerging (5F / Mom) เป็นรายสัปดาห์ | มีแค่รายเดือน → ใช้ JKP emerging รายวันแทน · ไฟล์รายเดือนใช้แค่ตรวจซ้ำรายเดือน |
| KF Asia Pacific ex Japan เป็น factor ของกองเอเชีย | ครอบแค่ AU / HK / NZ / SG — ไม่ตรงกับกองจีน / อินเดีย / เวียดนาม / อาเซียนของไทย |
| FX carry | ไม่มีอนุกรมรายวันฟรี (DBV เลิก มี.ค. 2023 · AQR VME รายเดือน) · กองไทยไม่ได้ทำ carry |
| ดอกเบี้ยแท้จริงให้กองทอง | ความสัมพันธ์ไม่เสถียร (หลักฐานรอง) · ราคาทองรวมผลนี้แล้ว |
| JKP ทั้ง 153 factor / ทั้ง 13 theme ทุก region | factor zoo → overfit แน่นอนบน T = 156 · จำกัด 2 theme · region เดียว |
| style ETF 4 ตัวเดิม + KF ใน pool เดียวกัน | ซ้ำซ้อน · ③c เคย overfit |
| ธีมที่มี < 5 กองเป็น factor แยก | n กองน้อย · ส่วนเพิ่มต่อกลุ่มแกว่ง (L3: n 5–8 กองก็แกว่งแล้ว) |
| ดัชนี MSCI factor / MSCI REIT ทางการ · FTSE EPRA Nareit · BCOM | ต้องยอมรับเงื่อนไขการใช้หรือเสียเงิน → มี ETF ใช้แทน (style ETF · REET / VNQ / VNQI · DBC / GSG) |
| multi-asset / balanced proxy | ไม่มีกองผสมใน O (9 เกณฑ์) |
| SET / TDEX ใน E | E เป็น FIF ทั้งหมด |
| macro ที่ลงทุนไม่ได้ (VIX_d · US10Y_d) ใน pool | ใช้ TERM (ลงทุนได้) แทน US10Y_d · VIX ซ้อนกับตลาด |
| holdings-based | ไม่มี holdings (เหมือน F-R001) |

---

## 4. กติกากัน overfit (BRIEF 110 · เสนอให้ designer ล็อกใน spec)

1. **ขนาด pool และจำนวน factor (ล็อกก่อนรัน · รายงานจำนวนที่ลองทั้งหมด)**
   - **E factor ร่วม:** แกนบังคับ = MKT (+ FX ถ้าผู้ใช้เลือกบังคับ) · pool ≤ 12 = {e_CHINA · EM−DM · TERM · KF SMB · HML · RMW · CMA · WML · JKP-EM value · JKP-EM momentum · FX (ถ้าไม่บังคับ) · สำรอง 1 ช่อง} · **เพดาน K_ร่วม ≤ 6 รวม MKT** → 12 coefficient (Dimson) + α บน 156 สัปดาห์ (~12 สัปดาห์ต่อพารามิเตอร์)
   - **E เฉพาะกลุ่ม:** ≤ 1 ตัวต่อกอง จากตารางชื่อกอง · กลุ่มต้องมี ≥ 5 กองใน U_E (นับก่อนรัน)
   - **O:** ชุดตายตัว ≤ 4 ตัวต่อกอง (ทอง 2 · REIT 4) · ไม่มีการคัดเลือก
2. **กฎคัด factor ร่วมของ E (ใช้เฉพาะ train 2021–2023)**
   - forward stepwise: แต่ละรอบเพิ่มตัวที่ให้ **median ΔBIC ข้ามกลุ่มกองอิสระ** ต่ำสุด (ตัวแทน 1 กองต่อกลุ่ม corr ≥ 0.95 single linkage จากผลตอบแทน train ตามข้อ 38)
   - เหตุผลที่ไม่ใช้ median ทุกกอง: เอียงหากลุ่มใหญ่ (บทเรียน C-blk)
   - **หยุดเมื่อข้อใดข้อหนึ่งเป็นจริง:**
     - (ก) median ΔBIC ของตัวที่ดีที่สุด > −2 (ค่าตัด "positive evidence" ของ Kass–Raftery 1995 · ยังไม่ยืนยันแหล่ง — designer ระบุว่าเป็นค่าตั้ง)
     - (ข) ครบ K_ร่วม = 6
     - (ค) **ด่าน pseudo-OOS:** fit 2021-01 → 2022-06 วัด 2022-07 → 2023-12 แล้ว median ΔR² ≤ 0
     - (ง) **ด่าน placebo:** ถ้าเลื่อน factor แบบวน 26 / 52 สัปดาห์แล้วยังถูกเลือก → หยุด (กฎ τ ของ L3-C)
   - **ทางเลือก robustness (ภาคผนวก):** วิธี "Lucky factors" ของ Harvey–Liu 2021 (JFE 141(2)) = เลือกทีละตัวโดยใช้ bootstrap บน factor ที่ตั้งฉากแล้ว เพื่อบังคับ null ว่า "ไม่มีอำนาจอธิบาย" ซึ่งคุม multiple testing ในตัว (อ่านแค่บทคัดย่อ · ขั้นตอนละเอียดยังไม่ยืนยัน)
3. **test 2024–2025 ใช้วัดอย่างเดียว** · ติดป้าย "ช่วง test ถูกใช้ซ้ำตั้งแต่ระยะ 1" ทุกตาราง (แม้ KF / JKP จะเป็นข้อมูลใหม่ แต่ช่วง test ไม่ใช่)
4. **β ของการ residualize ทุกตัวจาก train เท่านั้น** แล้วตรึงไว้ในช่วง test
5. ตารางชื่อกอง → factor ต้องล็อก**ก่อน**ที่ analyst จะเปิดผลตอบแทนใดๆ ของ U_E / U_O และเก็บเป็นไฟล์ใน spec (sha256)

---

## 5. รายการดาวน์โหลดที่เสนอ (session หลักเป็นผู้ดาวน์โหลด · เก็บ `.claude/factor_team/data/external/` · บันทึก NOTES.md + sha256)

ขนาดทั้งหมดเป็น**ค่าประมาณที่ไม่ได้วัด** · URL ของ KF ใช้รูปแบบ `https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/<ชื่อไฟล์>_CSV.zip` — **รูปแบบนี้มาจากความจำ** ชื่อไฟล์ตรงกับหน้า data library ที่เปิดเอง (ให้ session หลักตรวจลิงก์ในหน้า data library ก่อนโหลด) · Yahoo: adjusted close รายวัน 2020-11-02 → วันโหลด (แบบเดียวกับ `fetch_external.py`) · ตัดแถววันโหลดทิ้งตามบทเรียน EIDO ใน QA_L0_ext

### 5.1 จำเป็น (4 ไฟล์ · ~6–17 MB ก่อนตัดช่วง · ส่วนใหญ่เป็น JKP)
| # | ไฟล์ที่จะเก็บ | แหล่ง / URL | ticker / ชุด | ความถี่ · ช่วง | ขนาดประมาณ | ใช้กับ |
|---|---|---|---|---|---|---|
| 1 | `KF_DEVELOPED_5F_DAILY.csv` (+ zip ต้นฉบับ) | Ken French Data Library · `Developed_5_Factors_Daily_CSV.zip` | Mkt-RF · SMB · HML · RMW · CMA · RF (Developed 23 ประเทศ · USD · %) | รายวัน 1990-07-01 → 2026-08-31 | zip ~0.2–0.4 MB · csv ~0.5–1 MB | E7 |
| 2 | `KF_DEVELOPED_MOM_DAILY.csv` | `Developed_Mom_Factor_Daily_CSV.zip` | WML (Developed) | รายวัน → 2026-08-31 | zip ~0.1–0.2 MB | E7 |
| 3 | `JKP_EMERGING_THEMES_DAILY.csv` | jkpfactors.com/data → Factor returns · Region = Emerging · Theme = all themes · Frequency = Daily · Weighting = Capped value weighted (CC BY-NC 4.0 · ไม่ต้อง login) | 13 theme (ชื่อ theme ยังไม่ยืนยัน — ใช้ value / momentum ตาม pool) | รายวัน → 2025-12 | ~5–15 MB (ตัดเหลือ 2020-11 → 2025-12 ราว 0.5–1 MB) | E8 |
| 4 | `EO_ALT_ETF.csv` | Yahoo Finance | **GLD** (SPDR Gold · 2004) · **VNQ** (US REIT · 2004) · **VNQI** (ex-US RE · 2010) — ปีเริ่มจากความจำ ให้ตรวจแถวแรก | รายวัน 2020-11-02 → วันโหลด | ~0.1–0.15 MB | O1 · O2 · O4 |

### 5.2 ถ้ามีก็ดี (เรียงตามประโยชน์)
| # | ไฟล์ที่จะเก็บ | แหล่ง / URL | ticker / ชุด | ความถี่ · ช่วง | ขนาดประมาณ | ใช้กับ |
|---|---|---|---|---|---|---|
| 5 | `KF_MONTHLY_DEV_EM.csv` | KF · `Developed_5_Factors_CSV.zip` · `Developed_Mom_Factor_CSV.zip` · `Emerging_5_Factors_CSV.zip` · `Emerging_MOM_Factor_CSV.zip` | Developed + Emerging (รายเดือน) | รายเดือน → 2026-08 | รวม ~0.2 MB | ตรวจซ้ำรายเดือน · QA การรวมรายวัน · เทียบ JKP EM |
| 6 | `KF_REGIONAL_DAILY.csv` | KF · `North_America_5_Factors_Daily` · `Europe_5_Factors_Daily` · `Japan_5_Factors_Daily` (+ Mom ของแต่ละภูมิภาค = 6 zip) | SMB / HML / WML ระดับภูมิภาค | รายวัน → 2026-08-31 | รวม ~1–2 MB | E9 (กองหุ้นเล็ก / กองภูมิภาค) |
| 7 | `US_DOLLAR_REALRATE_FRED.csv` | FRED: DTWEXBGS · DTWEXEMEGS · DFII10 | ดอลลาร์กว้าง · ดอลลาร์เทียบ EM · TIPS 10Y | รายวัน → 2026-10 | ~0.1 MB | E12 · O6 (ภาคผนวก) |
| 8 | `ASIA_REIT_LOCAL.csv` | Yahoo: **1343.T** (TSE REIT ETF · ก.ย. 2008) · **CLR.SI** (S-REIT ETF · 2017-10-30) + **JPYTHB=X** · **SGDTHB=X** | REIT ญี่ปุ่น / สิงคโปร์ ปิดเวลาเอเชีย + ค่าเงิน | รายวัน 2020-11-02 → วันโหลด | ~0.2 MB | O4 (TJREIT · ONEPROP-SG) · ยังไม่ยืนยันว่า Yahoo มีข้อมูลครบ |
| 9 | `JKP_DEVELOPED_THEMES_DAILY.csv` | jkpfactors.com · Region = Developed · all themes · Daily · capped VW | 13 theme | รายวัน → 2025-12 | ~5–15 MB | ตรวจว่า KF กับ JKP (developed) สอดคล้องกัน (robustness) |
| 10 | `AQR_QMJ_BAB_HMLD_DAILY.xlsx` (3 ไฟล์) | aqr.com/Insights/Datasets · "Quality Minus Junk: Factors, Daily" · "Betting Against Beta: Equity Factors, Daily" · "The Devil in HML's Details: Factors, Daily" | QMJ · BAB · HML-Devil (+ factor อ้างอิง) · สหรัฐฯ + 23 ประเทศ | รายวัน (หน้าลงวันที่ 31 ก.ค. 2026) | ยังไม่ทราบ (คาด 5–30 MB ต่อไฟล์) · ต้องอ่าน Terms of Use ของ AQR | E10 robustness |

**ไม่เสนอ:** DBV (เลิกแล้ว) · ETF ธีมย่อย (BOTZ / CIBR / SKYY / FINX / ARKG / KSTR / EMXC — กลุ่ม < 5 กอง) · GDX (กองทองหุ้น policy E มี 1–2 กอง) · ดัชนีเอเชียท้องถิ่น (E13) · ดัชนี MSCI / FTSE / Bloomberg ทางการ (ต้องยอมรับเงื่อนไข / เสียเงิน)

---

## 6. ข้อเสนอการออกแบบสำหรับ designer (`S012_L1EO_split_factors`)

### 6.1 ชุดที่แข่งของ E (U_E ~209 · ตารางคะแนนกลาง 6 ข้อ · Dimson lag 1 · HAC)
| ชุด | เนื้อหา | ตอบคำถาม |
|---|---|---|
| E-PCA (a) | PCA ของ E ล้วน (ตามแผน: corr · EM · `nfactors.combine_k` · dedup_keep ตอนสร้าง) | factor ทางสถิติของ E เมื่อไม่มี F / O ปน |
| **E-X0** | แกน: MKT (+ FX ถ้าบังคับ) | เส้นฐานที่ลงทุนได้ (ใกล้ ③a ที่ไม่มีทอง / บอนด์) |
| **E-X1** | E-X0 + factor ร่วมจาก stepwise (pool ≤ 12 · K ≤ 6 · กติกาข้อ 4) | factor ภายนอกชุดใหม่ (b) |
| **E-X2** | E-X1 + factor เฉพาะกลุ่ม ≤ 1 ตัวต่อกองจากชื่อกอง (ประเทศ E2 / ธีม E3 / SMB ภูมิภาค E9) residualize บน E-X1 | ชั้นกลุ่มที่ไม่ต้องอาศัย primary จากช่วง test (ต่างจาก B-prim ของ L3) |
| E-H (c) | E-X1 + residual PC (`lib/hybrid.py` · k_res ด้วยกฎเดิม เพดาน 3) | factor ภายนอกขาดอะไรไป |
| ตัวเทียบ (d) | ①a / ①c · ③a · ①a + P4 (M1) | เทียบชุดเดิม |
| ภาคผนวก | E-X1 ที่ใช้ style ETF แทน KF · E-X1 แทน HML / RMW ด้วย AQR HML-Devil / QMJ · ชื่อกองเทียบกับ L2 primary | ความทนทาน |

### 6.2 ชุดที่แข่งของ O (U_O ~12 · รายงานรายกอง + กลุ่มย่อยเป็นหลัก)
| ชุด | กองทอง | กอง REIT |
|---|---|---|
| **O-X** (หลัก · ตายตัว) | GOLD_XS + FX | MKT + REIT_e + FX + TERM |
| O-X′ (ตัวเทียบอย่างง่าย) | Gold_THB − RF | REET_THB − RF |
| O-X + ภูมิภาค (ภาคผนวก) | — | + (VNQ / 1343.T / CLR.SI) − REET ตามชื่อกอง |
| O-PCA (ภาคผนวก · ป้าย N น้อย) | PCA ของ O ล้วน | |
| ตัวเทียบ | ①a · ①c · ③a | ①a · ①c · ③a |

- กลุ่มย่อยที่รายงาน: ทอง-hedge · ทอง-ไม่ hedge · REIT-US · REIT-global · REIT-Asia / Japan / Singapore
- ตรวจคู่ twin (KT-GOLD / KT-GOLDUH-A · UOBSG-H / UOBSG-N): loading FX และ α
- GRS / ความเสถียรของ O ติดป้าย "N น้อย" (ตามแผนข้อ 5) · กองทองที่ corr > 0.99 จะยุบรวมเฉพาะตอนทำ PCA

### 6.3 การรายงานราย factor (หัวใจของงาน · ทุก factor ในชุดที่แข่ง)
1. **ใส่เดี่ยว:** factor นั้นตัวเดียว (lag 0 + 1) + α และแบบ "แกน + factor นั้น" → adj R² ใน train และ R²_oos
2. **drop-one:** R² ที่หายไปเมื่อถอดตัวนั้นจากชุดเต็ม ทั้ง train (adj R²) และ test (R²_oos)
3. **Shapley R²:**
   - แบ่ง R² ของ train ด้วยค่าเฉลี่ยของส่วนเพิ่มตามทุกลำดับการใส่
   - **ให้ lag 0 กับ lag 1 ของ factor เดียวกันนับเป็น "ผู้เล่น" คนเดียว** (แบบ Owen value สำหรับตัวแปรที่จัดกลุ่มล่วงหน้า · Huettner–Sunder 2012 · Electronic J. Statistics)
   - ผลรวมของทุกตัวต้องเท่ากับ R² เต็ม (ใช้เป็น test ของโค้ด)
   - ต้นทุน: 2^K regression ต่อกอง (K ≤ 8 → 256 × ~209 กอง ซึ่งรันได้สบาย)
   - **ภาคผนวก:** Shapley ของ R²_oos (ใช้ loading จาก train · อาจได้ค่าติดลบ · ป้าย "ช่วง test ใช้ซ้ำ")
4. จำนวนกอง (และ**กลุ่มกองอิสระ**) ที่ β แบบ Dimson (b0 + b1) มีนัย · HAC · BH ภายใน factor
5. VIF รวม lag ของ Dimson · corr กับ factor อื่นทั้งช่วง train และ test (ความตั้งฉากหลัง residualize)
6. ความเสถียร: r ดิบของ β ครึ่งแรก / ครึ่งหลัง (ข้อ 18) · rolling 104 สัปดาห์ หน้าต่างแรกเทียบหน้าต่างสุดท้าย
7. ชื่อ factor: corr ≥ 0.7 = "≈" (กติกาเดิม) · กลุ่มกองที่ loading สูงสุด
8. เทียบกับชุดเดิม: canonical corr กับ ①a · ΔBIC · spanning (ทั้งสองทิศ)
9. **diagnostic lead 1 ครั้งเดียว** สำหรับ factor ใหม่ที่รวมจากรายวัน (KF / JKP / GLD / VNQ) เพื่อตรวจว่าการจัดสัปดาห์คลาดไหม (F-R001)

### 6.4 ร่างความคาดหมายล่วงหน้า (designer ปรับและล็อก · ระยะ 1 คาดผิดบ่อย จึงให้ช่วงกว้าง)
- E-X1 เลือกได้ 3–5 ตัว · ตัวแรก ๆ คือ e_CHINA และ TERM · style KF ผ่าน ≤ 2 ตัว
- E-X1 / E-X2 ยังต่ำกว่า E-PCA ใน R²_oos (เหมือนที่ C-prim 0.580 ต่ำกว่า ①a 0.618) แต่ช่องว่างแคบลง
- O-X ของกองทอง: R²_oos ≥ 0.9 · α ของกองทองไม่ต่างจาก −TER
- O-X ของกอง REIT ดีกว่า ①a อย่างชัดเจน

---

## 7. ข้อจำกัด
- **ช่วง test 2024–2025 ถูกใช้ซ้ำ** ตั้งแต่ระยะ 1 · factor ใหม่ไม่ได้ทำให้ช่วงนั้นเป็นหลักฐานอิสระ · ไม่มี holdout (NAV 2026 มีรู)
- **จำนวนกองตามธีมนับจากชื่อ (regex) บน panel เดิม** — U_E / U_O จริงจะน้อยกว่า · ชื่อกองอาจไม่ตรงกับสิ่งที่ถือ (Sensoy 2009) · FundProfile เป็น snapshot และช่อง benchmark ว่างเกือบทั้งหมด (E 4 / 357 · O 0 / 27)
- **corr ทุกตัวในรายงานนี้เป็นการคาดการณ์** · ไม่ได้เปิดดูข้อมูลผลตอบแทน
- **JKP จบ ธ.ค. 2025** — พอดีกับช่วงหลัก แต่ดูปี 2026 ประกอบไม่ได้ · ชื่อ 13 theme ยังไม่ยืนยัน · ใช้แบบ capped VW (ค่าเริ่มต้นของเว็บ) · สัญญาอนุญาต CC BY-NC
- **Ken French:** Developed ไม่มี EM · EM มีแค่รายเดือน · วิธีแปลง USD รายวันของพอร์ตหลายประเทศ (เวลาปิดต่างกัน) ยังไม่ยืนยัน · การทบต้นรายวันของ factor long–short เป็นค่าประมาณของพอร์ตที่ปรับสมดุลรายวัน
- **กลไกทอง / FX ตั้งบนสมมติฐาน CIP** ซึ่งในทางปฏิบัติมีส่วนเบี่ยง (basis) ของบาทที่ยังไม่ทราบขนาด · สัดส่วน hedge จริงของแต่ละกองยังไม่ได้ตรวจกับหนังสือชี้ชวน
- REIT: หลักฐานเรื่องความไวต่อดอกเบี้ยขัดกัน · REIT รายภูมิภาค 1–2 กองต่อภูมิภาค → รายกองเท่านั้น
- ทุก ETF / ดัชนีที่ปิดเวลา NY ต้องใช้ Dimson lag · ETF มีค่าธรรมเนียม (α ของกองเทียบกับ ETF ที่หักค่าธรรมเนียมแล้ว)
- หลักฐานวรรณกรรมเกือบทั้งหมดมาจากตลาดสหรัฐฯ / ตลาดพัฒนาแล้ว และหุ้นรายตัว ไม่ใช่กอง FIF ไทย (ค้นภาษาไทยแล้วไม่พบงาน factor model ของกอง FIF)

---

## 8. ต้องให้ผู้ใช้ตัดสินใจ
1. **อนุมัติรายการดาวน์โหลด:** จำเป็น 4 ไฟล์ (ข้อ 5.1) · ถ้ามีก็ดี 6 รายการ (ข้อ 5.2) — แนะนำ: จำเป็นทั้งหมด + ข้อ 5 (KF รายเดือน · เล็กมาก) + ข้อ 6 (KF ภูมิภาค) · ข้อ 7–10 เลือกได้
2. **JKP (CC BY-NC · ข้อมูลถึง ธ.ค. 2025)** ใช้เป็นแหล่ง style ของ EM หรือไม่ — ถ้าไม่ใช้ กอง EM / เอเชียจะไม่มี style factor รายสัปดาห์เลย (ทางเลือก: ตรวจรายเดือนด้วย KF Emerging เท่านั้น)
3. **ชุด style หลัก:** KF (แนะนำ) / style ETF 4 ตัวเดิม / ทั้งสองแยกกันเป็นชุดภาคผนวก (ห้ามรวมใน pool เดียว)
4. **factor เฉพาะกลุ่มกำหนดจากชื่อกอง (แนะนำ)** หรือจาก primary ของ L2 (ใช้ข้อมูลช่วง test เลือกมาแล้ว → ป้าย look-ahead) · และผู้ใช้อยากตรวจตารางชื่อกอง → factor ก่อนล็อกหรือไม่
5. **กอง O มีแค่ทอง + REIT** (ไม่มีกองผสมภายใต้ 9 เกณฑ์) — ยืนยันว่าไม่ต้องหากองผสมเพิ่ม (ถ้าต้องการต้องเปลี่ยน universe = งานใหม่)
6. **FX ในกอง E:** บังคับในแกน (สอดคล้อง L4 · ΔBIC +5.5) หรือให้เข้าแข่งใน pool (แนะนำ: อยู่ใน pool · O บังคับเสมอ)
7. **เพดาน:** pool E ≤ 12 · K_ร่วม ≤ 6 · กลุ่มต้องมี ≥ 5 กอง · O ≤ 4 ตัวต่อกอง · ค่าตัด ΔBIC −2 — ยืนยันหรือเปลี่ยน (ต้องล็อกก่อนรัน)
8. **REIT ปิดเวลาเอเชีย (1343.T / CLR.SI)** ต้องใช้ค่าเงิน JPY / SGD เพิ่ม และ Yahoo อาจมีข้อมูลไม่ครบ — ใส่หรือไม่
9. **AQR** (ต้องอ่าน Terms of Use · ขนาดไม่ทราบ) ใช้เป็น robustness หรือข้าม (แนะนำ: ข้ามรอบนี้)
10. **Shapley ของ R²_oos** รายงานเป็นภาคผนวกหรือไม่ (แนะนำ: รายงาน พร้อมป้าย)
- **ข้อมูลเสียเงิน:** ไม่มีรายการใดที่ต้องจ่าย · ดัชนีทางการ (MSCI factor / MSCI REIT · FTSE EPRA Nareit · BCOM · SET) ใช้ ETF แทนได้

---

## บรรณานุกรม
ป้าย:
- **[อ่านเอง-abs]** = เปิดหน้าบทคัดย่อ / หน้าข้อมูลเอง
- **[หน้าข้อมูล]** = เปิดหน้าแหล่งข้อมูลเอง
- **[ผลค้น]** = ยืนยันจากผลค้นที่ยกเนื้อหามา (ไม่ได้เปิดหน้า)
- **[ยังไม่ยืนยันแหล่ง]** = จากความจำ
- **[F-R00x]** = อ้างต่อจากรายงานเดิม

**แหล่งข้อมูล**
- Ken French Data Library (หน้าหลัก · รายชื่อไฟล์ · ข้อมูลถึง ส.ค. 2026) https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html [หน้าข้อมูล] · หน้า Developed 5 factors (USD · ประเทศ · วิธีสร้าง · รายวัน 1990-07-01 → 2026-08-31) https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/Data_Library/f-f_5developed.html [หน้าข้อมูล] · รูปแบบ URL `/ftp/<file>_CSV.zip` [ยังไม่ยืนยันแหล่ง]
- AQR Datasets (QMJ / BAB / HML-Devil รายวัน · ลงวันที่ 31 ก.ค. 2026) https://www.aqr.com/Insights/Datasets [หน้าข้อมูล] · QMJ Daily https://www.aqr.com/Insights/Datasets/Quality-Minus-Junk-Factors-Daily [หน้าข้อมูล]
- JKP Global Factor Data https://jkpfactors.com/ (อัปเดตถึง ธ.ค. 2025 · CC BY-NC 4.0) [หน้าข้อมูล] · https://jkpfactors.com/data (รายวัน / รายเดือน · capped VW / VW / EW · 93 ประเทศ + 4 region) [หน้าข้อมูล] · tidyfinance `download_data_jkp` (region usa / world / developed / emerging) https://rdrr.io/cran/tidyfinance/man/download_data_jkp.html [หน้าข้อมูล] · ชื่อ 13 theme [ยังไม่ยืนยันแหล่ง]
- FRED DTWEXEMEGS (รายวัน · ถึง 2026-10-16) https://fred.stlouisfed.org/series/DTWEXEMEGS [หน้าข้อมูล] · DTWEXBGS · DFII10 [ยังไม่ยืนยันแหล่ง]
- Invesco DB G10 Currency Harvest (DBV) เลิกซื้อขาย 3 มี.ค. 2023 · ชำระบัญชี 10 มี.ค. 2023 — SEC filing https://www.sec.gov/Archives/edgar/data/1354730/000119312523077468/d477628dposam.htm [ผลค้น]
- SPDR Gold Trust: NAV อิง LBMA Gold Price PM https://www.spdrgoldshares.com/media/GLD/file/GLD-FAQs-January-2025.pdf [ผลค้น]
- K-GOLD ลงทุนใน SPDR Gold Trust · hedge ทั้งหมด / เกือบทั้งหมด https://www.finnomena.com/fund/K-GOLD-A(A) [ผลค้น]
- NEXT FUNDS TSE REIT (1343) เริ่ม ก.ย. 2008 https://www.trackinsight.com/en/fund/1343 [ผลค้น] · Lion-Phillip S-REIT ETF (CLR) เริ่ม 2017-10-30 https://www.tradingview.com/symbols/SGX-CLR [ผลค้น]
- ปีเริ่มของ GLD / VNQ / VNQI / ETF ธีมย่อย [ยังไม่ยืนยันแหล่ง — ให้ data-engineer ตรวจแถวแรก]

**วรรณกรรม**
- Hollstein, F. (2022) Local, Regional, or Global Asset Pricing? JFQA 57(1), 291–320. https://ideas.repec.org/a/cup/jfinqa/v57y2022i1p291-320_9.html [อ่านเอง-abs]
- Jensen, T.I., Kelly, B. & Pedersen, L.H. (2023) Is There a Replication Crisis in Finance? JF 78(5), 2465–2518. https://ideas.repec.org/a/bla/jfinan/v78y2023i5p2465-2518.html [อ่านเอง-abs]
- Busse, J., Goyal, A. & Wahal, S. (2014) Investing in a Global World. Review of Finance 18(2), 561–590. https://ideas.repec.org/a/oup/revfin/v18y2014i2p561-590..html · CFA digest https://rpc.cfainstitute.org/research/cfa-digest/2014/09/investing-in-a-global-world-digest-summary [ผลค้น]
- Fama, E. & French, K. (2017) International tests of a five-factor asset pricing model. JFE 123, 441–463. https://academicnewsletter.sufe.edu.cn/info/356243 [ผลค้น] · FF (2012) [F-R001]
- Hou, K., Karolyi, G.A. & Kho, B.-C. (2011) What Factors Drive Global Stock Returns? RFS 24(8), 2527–2574. https://ideas.repec.org/a/oup/rfinst/v24y2011i8p2527-2574.html [ผลค้น]
- Asness, Moskowitz & Pedersen (2013) · Sharpe (1992) · Cremers, Petajisto & Zitzewitz (2013) · Lustig, Roussanov & Verdelhan (2011) · Goetzmann, Ivković & Rouwenhorst (2001) · Elton, Gruber & Blake (1995) [F-R001]
- Heston & Rouwenhorst (1994) · Brooks & Del Negro · Bekaert, Hodrick & Zhang (2009) · Greger & Scholz (SSRN 4565638) [F-R004]
- Verdelhan, A. (2018) The Share of Systematic Variation in Bilateral Exchange Rates. JF 73(1), 375–418. https://dspace.mit.edu/handle/1721.1/122354 [ผลค้น]
- Erb, C. & Harvey, C. (2013) The Golden Dilemma. FAJ 69(4), 10–42. https://www.nber.org/papers/w18706 [ผลค้น] · ตัวเลข corr ทอง–ดอกเบี้ยแท้จริงจากแหล่งรอง [ยังไม่ยืนยันแหล่ง] · บทวิเคราะห์ตลาดเรื่องความสัมพันธ์ทอง–TIPS แตกหลังปี 2022 https://www.goldmoney.com/research/have-central-banks-lost-control-over-the-gold-price [ผลค้น · ไม่ใช่งานวิชาการ]
- Clayton, J. & MacKinnon, G. (2003) The Relative Importance of Stock, Bond and Real Estate Factors in Explaining REIT Returns. JREFE 27(1), 39–60. https://ideas.repec.org/a/kap/jrefec/v27y2003i1p39-60.html [ผลค้น] · งานแย้ง (Lee) https://www.prres.org/uploads/829/1451/Lee_Real_Estate_Risk_Exposure.pdf [ผลค้น] · REIT มาเลเซีย https://www.prres.org/uploads/661/2110/Wong_Malaysia_REIT.pdf [ผลค้น] · Chen–Tzang (1988) / Liang et al. (1995) ผ่านแหล่งรอง [ผลค้น]
- Ben-David, I., Franzoni, F., Kim, B. & Moussawi, R. (2023) Competition for Attention in the ETF Space. RFS 36(3), 987–1042. https://www.nber.org/system/files/working_papers/w28369/revisions/w28369.rev2.pdf [ผลค้น]
- Sensoy, B. (2009) Performance evaluation and self-designated benchmark indexes in the mutual fund industry. JFE 92(1), 25–39. https://ideas.repec.org/a/eee/jfinec/v92y2009i1p25-39.html [ผลค้น]
- Harvey, C. & Liu, Y. (2021) Lucky factors. JFE 141(2), 413–435. https://ideas.repec.org/a/eee/jfinec/v141y2021i2p413-435.html [ผลค้น]
- Huettner, F. & Sunder, M. (2012) Axiomatic arguments for decomposing goodness of fit according to Shapley and Owen values. Electronic J. Statistics 6. https://projecteuclid.org/journals/electronic-journal-of-statistics/volume-6/issue-none/Axiomatic-arguments-for-decomposing-goodness-of-fit-according-to-Shapley/10.1214/12-EJS710.short [ผลค้น]
- Fama–French (1993) TERM / DEF · Dechow, Sloan & Soliman (2004) equity duration · Kass & Raftery (1995) Bayes factors · Frazzini & Pedersen (2014) BAB · Asness, Frazzini & Pedersen QMJ · Griffin (2002) · Grömping (2006) relaimpo [ยังไม่ยืนยันแหล่ง]
- บริบทไทย: ค้น "กองทุน FIF + factor model" ภาษาไทย → ไม่พบงานกับกอง FIF โดยตรง (พบเฉพาะงานหุ้นไทย / ETF) https://nuir.lib.nu.ac.th/dspace/bitstream/123456789/7329/1/JirapornNitipoom.pdf [ผลค้น]

## สิ่งที่ยังค้าง
- ยังไม่ได้อ่านฉบับเต็ม: Hollstein 2022 (รายชื่อตลาด / ช่วงปี) · BGW 2014 (สมการ factor) · FF 2017 (ตาราง local vs global) · Harvey–Liu 2021 (ขั้นตอน bootstrap) · Clayton–MacKinnon 2003
- ยังไม่ยืนยัน: ชื่อ theme และรูปแบบไฟล์ของ JKP · ขนาดไฟล์ AQR และ Terms of Use · Yahoo มี 1343.T / CLR.SI ครบหรือไม่ · สัดส่วน hedge จริงของกองทอง / REIT แต่ละกอง · ขนาดส่วนเบี่ยง CIP ของบาท
