# Design — ทีมวิจัย Factor ของกองทุน (factor_team)

สถานะ: **ร่างรอผู้ใช้รีวิว** · 2026-10-15 · path ทั้งหมดสัมพันธ์กับ `Fund Style Dashboard/`
ยังไม่ commit (commit เมื่อผู้ใช้สั่งเท่านั้น) · ยังไม่สร้าง agent / โฟลเดอร์ใดๆ

---

## 1. เป้าหมาย

หา factor แบบ Fama-French ที่อธิบายผลตอบแทนกองทุนไทยในระบบนี้ โดยไล่จากบนลงล่าง:
factor ร่วมของกองทั้งหมด → factor × MSCI → ชุด MSCI ที่ตัด VIF แล้ว → ระดับกลุ่ม (ประเทศ / sector / ประเภทกอง) และรายกอง

| ระยะ | คำถาม | นับ trial? |
|---|---|---|
| **ระยะ 1 — อธิบาย** (L0–L4) | อะไรขับเคลื่อนผลตอบแทนกอง · กี่ factor · exposure / R² / alpha ที่เหลือ | **ไม่นับ** (ไม่ได้ใช้เลือกกอง) |
| **ระยะ 2 — ทำนาย** (เริ่มเมื่อผู้ใช้สั่งหลังจบ L4) | factor / loading / alpha ที่ประมาณด้วยข้อมูล ≤ t ทำนายผลตอบแทนข้างหน้าได้ไหม | **นับทุกการทดสอบ** · ลงทะเบียนล่วงหน้า |

**ผลผลิต:** รายงานวิจัยภาษาไทยต่อชั้น + ไฟล์ผล (CSV) ในโฟลเดอร์ทีม · **ไม่แก้แอป** ·
ถ้าได้ factor ที่ดีค่อยให้ผู้ใช้สั่งทำแผนหน้าแอปใหม่ภายหลัง

**เกณฑ์ความสำเร็จของระยะ 1:** ได้ชุด factor ที่ (1) อธิบายผลตอบแทนกองได้ดีทั้งในช่วงและนอกช่วง (ตารางคะแนน §5)
(2) เสถียรข้ามช่วงเวลา (3) ตีความทางเศรษฐศาสตร์ได้ — หรือได้ข้อสรุปตามจริงว่า "ไม่มีชุดที่ผ่าน" พร้อมเหตุผล

## 2. การตัดสินใจของผู้ใช้ (2026-10-15)

| เรื่อง | ตัดสินใจ |
|---|---|
| เป้าหมาย | ทั้งอธิบายและทำนาย แยกเป็น 2 ระยะ |
| แหล่ง factor | ลองได้ทุกสาย: pure stat · pure Fama-French · factor ภายนอก · สร้าง factor ใหม่ — เริ่มจาก deep research ของ sub agent |
| Universe | กอง **E, F, O** ที่ผ่าน **FundProfile 9 เกณฑ์ + NAV พอคำนวณ** (ไม่ตัด AUM / อายุกอง) |
| ความถี่ | **รายสัปดาห์เป็นหลัก** · ตรวจซ้ำรายเดือน |
| ทีม | **ทีมใหม่แยกโฟลเดอร์** · agent ใหม่ทั้งหมด ไม่ใช้ agent ของ `quant_team` ร่วม |
| แนวทาง | **A** — ไล่ทีละชั้น ทุกชั้นวนลูปเดียวกัน · ที่ L1 ทุกสายแข่งบนตารางคะแนนชุดเดียว |
| ผลผลิต | รายงาน + ไฟล์ผล · ไม่แตะแอป |

## 3. ทีม agent

นิยามที่ `.claude/agents/factor-*.md` (frontmatter แบบเดียวกับทีมเดิม) ·
agent types ของโปรเจกต์ไม่ถูก register เมื่อ cwd = `Fama French/` → เรียกผ่าน general-purpose agent และสั่งให้อ่านไฟล์ role ก่อน

| agent | model / effort | หน้าที่ | เครื่องมือ | เขียนได้เฉพาะ |
|---|---|---|---|---|
| `factor-researcher` | opus · high | deep research ทุกสาย (§4 L1) แล้วกลั่นเป็นไอเดียที่ทดสอบได้ภายใต้ข้อจำกัดข้อมูล · จัดอันดับ · ระบุพารามิเตอร์มาตรฐานจากวรรณกรรม · ไม่เขียน spec ไม่รันโค้ด | Read, Grep, Glob, Write, WebSearch, WebFetch | `research/` |
| `factor-data-engineer` | sonnet · medium | สร้าง L0 panel + factor inputs + `manifest.json` · checklist QA ในตัว · เทียบกับ cache F/O ของ quant_team (read-only) | Read, Grep, Glob, Bash, Write, Edit | `data/` |
| `factor-designer` | opus · high | แปลงไอเดียเป็น spec ล่วงหน้า (สมมติฐาน · วิธี · การทดสอบ · เกณฑ์ผ่าน) · เขียนสรุปชั้นให้ผู้ใช้ | Read, Grep, Glob, Bash, Write | `specs/`, `reports/` |
| `factor-analyst` | sonnet · medium | เขียนโค้ดกลางใน `lib/` + tests และรันตาม spec เท่านั้น (ห้ามเปลี่ยน spec · เจอปัญหา = หยุดแล้วรายงาน) | Read, Grep, Glob, Bash, Write, Edit | `lib/`, `runs/` |
| `factor-reviewer` | opus · high | รีวิว spec ก่อนรัน และรีวิวผลหลังรัน: look-ahead · NAV ไทยไม่พร้อมดัชนี · multiple testing · factor ที่สร้างจากกองชุดเดียวกับที่อธิบาย (circularity) · ตีความเกินหลักฐาน | Read, Grep, Glob, Bash, Write | `reviews/` |

**กติกาเหล็ก (ทุก agent · เขียนซ้ำใน BRIEF):**
- READ-ONLY ต่อโค้ดแอป (`pages/`, `analysis/`, `data/`, `data_access.py`, `config.py`, `viz.py`, `tests/`), `cache/`, `base_data/` และ `.claude/quant_team/`
- ห้ามเรียก `data.nav_loader.load_nav_history*`, `data_access.build_*`, `data_access.rebuild` (เขียนทับ cache) · ใช้ฟังก์ชันที่ไม่เขียนไฟล์ได้ (`nav_loader.clean_nav_spikes`, `_detect_and_fix_spikes`, `parse_update_time`, `fund_profile.filter_funds`)
- ระยะ 2 ห้ามใช้ `cache/coefs.csv` / `results.csv` ของแอป (fit ทั้งช่วง = look-ahead) · ระยะ 1 ใช้เทียบเชิงบรรยายได้
- ห้ามแตะ `quant_team/trials.csv` · ห้ามเปิด server / Streamlit · pytest ใช้ `-p no:cacheprovider`
- รันทีละ agent (ประหยัดโควตา) · ทำให้จบภายใน `maxTurns` — ใกล้หมดให้สรุปสิ่งที่ได้ + สิ่งที่เหลือ
- ภาษาไทย · ตัวเลขทุกตัวต้องมาจากการรันหรืออ่านไฟล์เอง
- เรื่องที่ต้องตัดสินใจ (นิยาม · ข้อมูลที่ขาด · trade-off) → หยุดและเขียนหัวข้อ **"ต้องให้ผู้ใช้ตัดสินใจ"**
- ดาวน์โหลดข้อมูลใหม่ต้องให้ผู้ใช้อนุมัติก่อน (ชื่อไฟล์ / แหล่ง / ขนาด) · ไม่ให้คำแนะนำการลงทุน

## 4. โฟลเดอร์ `.claude/factor_team/`

| path | เนื้อหา |
|---|---|
| `BRIEF.md` | เป้าหมาย · นิยาม universe · กติกาเหล็ก · ตารางคะแนนกลาง (lock ก่อน L1) · สถานะล่าสุด |
| `research/` | `F-R###_<หัวข้อ>.md` + `INDEX.md` |
| `specs/` | `S###_L#_<ชื่อ>.md` (เลขรันต่อเนื่องทุกชั้น) |
| `data/` | `panel_weekly.parquet` · `panel_monthly.parquet` · `universe.csv` (กอง · policy · family · class ที่ใช้ · เหตุผลที่ตัด) · `factors_weekly.parquet` / `factors_monthly.parquet` · `manifest.json` · `QA_L0.md` |
| `lib/` | โมดูล Python กลาง (`panel.py` โหลด/จัด panel · `regress.py` OLS + Dimson lag + HAC SE · `pca.py` · `tests_stat.py` GRS / Bai–Ng / BH-FDR · `scoreboard.py`) + `lib/tests/` |
| `runs/S###/` | ผล CSV + `run.log` (บันทึก hash ข้อมูลจาก manifest + hash ของไฟล์ใน lib — งานอาจยังไม่ commit จึงไม่อ้างเลข commit) |
| `reviews/` | `S###_spec_review.md` · `S###_result_review.md` |
| `reports/` | `L0_summary.md` … `L4_summary.md` · `PHASE1_SUMMARY.md` |
| `trials.csv` | **ระยะ 2 เท่านั้น** · backup timestamp ก่อน append · append แบบ text เท่านั้น · ห้ามลบ/แก้แถว |
| `scratch/` | สคริปต์ชั่วคราว (นำหน้าด้วยชื่อ agent) |

## 5. ระยะ 1 — ชั้นการวิเคราะห์

**ข้อมูลพื้นฐาน:** ช่วงหลัก 2021-01-01 → 2025-12-31 (NAV 2026 มีรูใหญ่ — ใช้ดูประกอบเท่านั้น) ·
ผลตอบแทนรายสัปดาห์ (จุดปิดสัปดาห์เดียวกันทุกชุด · NAV asof ≤ วันอ้างอิง) · ตรวจซ้ำรายเดือน ·
ทุก regression ใส่ lag 1 ช่วงของ factor (Dimson) เพราะ NAV ไทยออกไม่พร้อมดัชนีต่างประเทศ · SE แบบ HAC (Newey–West)

### L0 — ข้อมูล (`factor-data-engineer`)
1. FundProfile 9 เกณฑ์เดิม (`fund_profile.filter_funds` · 715 กอง: E 600 / F 77 / O 38)
2. NAV จาก `base_data/nav_history_db.csv` ด้วยตัวอ่าน chunked ของทีมเอง → dedupe (UpdateTime ล่าสุด) → `clean_nav_spikes`
3. "NAV พอคำนวณ": ≥ 52 ผลตอบแทนรายสัปดาห์ในช่วงหลัก · สัดส่วนสัปดาห์ที่ return = 0 ไม่เกินเกณฑ์ **แยกตาม policy** (กอง F ตลาดเงินขยับน้อยโดยธรรมชาติ — ค่าเกณฑ์กำหนดใน spec L0 พร้อมเหตุผล)
4. **1 class ต่อกอง** (family จาก `share_class_groups.csv` / suffix แบบเดียวกับทีมเดิม · เลือก class ไม่ปันผลที่ประวัติยาวสุด) — กัน class ที่ return เกือบเท่ากันดัน PCA
5. point-in-time: กองเลิก/stale อยู่ใน panel เฉพาะช่วงที่มี NAV (unbalanced panel) · ไม่ตัดกองตามสถานะวันนี้นอกเหนือจาก 9 เกณฑ์
6. factor inputs: MSCI 28 (THB) · style ETF 4 (de-market แบบ `data.style_factor`) · macro 7 · rf ดอกเบี้ยนโยบาย ธปท. · AGG / IEF (แปลงเป็นบาทด้วย USDTHB) · ทอง (USD และบาท)
7. QA: ความสด · รู · spike · จำนวนกองต่อสัปดาห์ · กองที่ซ้ำกัน (corr > 0.99) · เทียบกับ `quant_team/backtest/cache/m015_navF_clean.parquet` และ `r1_navO_all.parquet`

**ต้องให้ผู้ใช้ตัดสินใจตอน L0:** ใช้ดัชนี SET จาก cache ของโปรเจกต์ `Fama French SET50/` (read-only) เป็น factor สำหรับกองหุ้นไทยที่ติด FIF Flag ไหม

### L1 — factor ร่วมของกองทั้งหมด (แข่ง 4 สาย)
| สาย | ตัวอย่างวิธี (researcher ยืนยัน / เพิ่มเติมใน F-R001) |
|---|---|
| ① pure stat | PCA บน balanced sub-panel · จำนวน factor ด้วย Bai–Ng IC และ parallel analysis · PCA แบบรองรับข้อมูลขาด (EM/ALS) บน unbalanced panel · Connor–Korajczyk (N > T) |
| ② Fama-French ของกองทุน | long–short ระหว่างกลุ่มกองที่เรียงตามคุณลักษณะ ณ ต้นช่วง: ขนาด AUM · ค่าธรรมเนียม · โมเมนตัม · ระดับ hedge FX (beta ต่อ USDTHB จาก NAV) · active/passive (R² ต่อดัชนีหลัก) · ประเภท E/F/O |
| ③ factor ภายนอก | ตลาดโลก (ACWI บาท − rf) · ทอง · บอนด์ (AGG บาท) · USDTHB · ชุดเล็กเพิ่มเติม (เช่น EM − DM, US − ACWI) |
| ④ factor ใหม่ | ตามที่ researcher เสนอ (ต้องมีเหตุผลเชิงเศรษฐศาสตร์และวิธีสร้างที่ใช้ข้อมูลที่มี) |

### ตารางคะแนนกลาง (ใช้กับทุกสายที่ L1 · lock ใน BRIEF ก่อนรัน · L2–L4 ใช้ชุดเดียวกันเท่าที่ทำได้)
1. **R² รายกอง** — median และ IQR ของ adj R² แยก E / F / O
2. **R² นอกช่วง** — ประมาณ factor (เช่น น้ำหนัก PCA / การจัดกลุ่มของสาย ②) และ loading ด้วยช่วง 2021–2023 แล้ววัดช่วง 2024–2025 โดยไม่ fit ใหม่ (กัน circularity)
3. **pricing error** — |α| เฉลี่ย · GRS test บนพอร์ตกลุ่มของกอง (จำนวนกอง > จำนวนสัปดาห์ จึงทดสอบรายกองตรงไม่ได้)
4. **ความประหยัด** — จำนวน factor · BIC
5. **ความเสถียร** — correlation ของ loading ระหว่างครึ่งแรก / ครึ่งหลัง · rolling 104 สัปดาห์
6. **ตีความได้** — correlation กับ factor ภายนอก / ดัชนี · ชื่อที่ให้ได้

ตัวเลขจากตารางนี้ไม่มีเกณฑ์ผ่านอัตโนมัติ — designer เสนอ ผู้ใช้เลือกชุดที่ลงชั้นถัดไป

### L2 — factor × MSCI
- spanning regression: factor ของ L1 ~ MSCI 28 + style + macro → factor ทางสถิติตรงกับดัชนีอะไร
- incremental R² ของ MSCI ต่อกองหลังมี factor ของ L1 · ดัชนีไหนซ้ำซ้อน
### L3 — VIF-cleaned
- country 11 ตัวของ `config.SCORE_COUNTRY_CLEAN` + ตรวจ VIF ของ sector 10 ตัวและชุดรวม (factor + ดัชนี) ด้วยเกณฑ์ VIF < 5 เดิม
- ผลจาก L2 ยังอยู่ไหม · เทียบ primary country/sector กับที่แอปให้ (เชิงบรรยาย)
### L4 — กลุ่มและรายกอง
- กลุ่มตาม primary country / sector / policy E-F-O → PCA ของ residual ภายในกลุ่ม (มี factor เฉพาะกลุ่ม เช่น hedge FX ของกองอินเดีย?)
- α รายกองหลังหัก factor ชุดสุดท้าย · t แบบ HAC · แก้ multiple testing ด้วย Benjamini–Hochberg (FDR 10%)

## 6. ลำดับงาน

**ต่อชั้น:** researcher (เมื่อต้องการไอเดีย/หลักฐานใหม่) → designer เขียน spec → **reviewer รีวิว spec ก่อนรัน** →
analyst รัน → reviewer รีวิวผล → (ไม่ผ่าน → แก้ spec เป็นเลขใหม่ / รันใหม่) → designer เขียน `reports/L#_summary.md` → **ผู้ใช้อนุมัติ** ก่อนลงชั้นถัดไป

**kick-off (เมื่อผู้ใช้สั่ง · ทีละตัว):**
1. `factor-researcher` → `F-R001` สำรวจวรรณกรรม 4 สาย + ตารางไอเดียจัดอันดับ
2. `factor-data-engineer` → L0 panel + `QA_L0.md` + `reports/L0_summary.md`
3. `factor-designer` → `S001_L1_*` (การแข่ง L1) → reviewer → รอผู้ใช้สั่งรัน

ขั้น 1–3 ไม่เปิดดูผลตอบแทนเพื่อเลือก factor

## 7. ระยะ 2 — ทำนาย (เมื่อผู้ใช้สั่งหลังจบ L4)

- (ก) **cross-section:** loading / α รายกองที่ประมาณด้วยข้อมูล ≤ t (rolling / expanding) ทำนายผลตอบแทนกองไตรมาสถัดไปได้ไหม — Fama–MacBeth · IC
- (ข) **time-series:** ผลตอบแทน factor จับจังหวะได้ไหม (เช่น factor momentum)
- walk-forward รายไตรมาส · ช่วงเดียวกับ M052 (เม.ย. 2022 – ธ.ค. 2025) · rf ธปท. จริง
- **งบ trial กำหนดล่วงหน้า** (ค่าเริ่มต้นที่เสนอ ≤ 10 · ผู้ใช้ยืนยันตอนเริ่มระยะ 2) · ทุกการทดสอบลง `factor_team/trials.csv`
- สัญญาณที่ผ่านและจะใช้ทำพอร์ต → ส่งต่อทีม quant วัดด้วยเครื่องมือ backtest เดิม (ค่าธรรมเนียมจริง) · **DSR ใช้ n รวมสองทีม** (102 + trials ของ factor_team ณ ตอนนั้น)
- ไม่มี holdout (NAV 2026 ไม่ครบ) → จบที่ "ล็อกกติกา แล้ว forward test" แบบเดียวกับ M052

## 8. กติกากันพลาด

- ทุกฟังก์ชันใน `lib/` มี test ใน `lib/tests/` (เช่น OLS เทียบ statsmodels · PCA บนข้อมูลจำลองที่รู้จำนวน factor · GRS บนข้อมูลที่ α = 0)
- ทุก run บันทึก hash ข้อมูล (manifest) → รันซ้ำต้องได้ผลเดิมทุกบิต
- ระยะ 1 ห้ามสรุปว่า "ลงทุนได้" — long–short ระหว่างกองเป็นเชิงอธิบาย (กองทุนไทยขายชอร์ตไม่ได้)
- ทุกรายงานแยก "สิ่งที่พบ" กับ "ข้อจำกัด" (FundProfile เป็น snapshot ปัจจุบัน · NAV class ปันผลไม่รวมปันผล · NAV 2026 มีรู · ETF style ปิดเวลา NY)
- ไม่แตะแอป รายงานเดิม และ `quant_team/`

## 9. สิ่งที่จะสร้างเมื่ออนุมัติ (ขั้น implementation)

1. `.claude/agents/factor-{researcher,data-engineer,designer,analyst,reviewer}.md`
2. `.claude/factor_team/BRIEF.md` (รวม §2, §3 กติกาเหล็ก, §5 ตารางคะแนน) + โครงโฟลเดอร์ §4 + `research/INDEX.md` ว่าง
3. อัปเดต `handoff.md` ให้ชี้ถึงทีมใหม่ (เมื่อผู้ใช้สั่ง)

ไม่รันการวิเคราะห์ใดๆ จนกว่าผู้ใช้สั่ง kick-off
