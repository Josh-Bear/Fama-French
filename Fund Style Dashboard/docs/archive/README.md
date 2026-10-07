# 📦 Archive — เอกสารเชิงประวัติ

ไฟล์ในโฟลเดอร์นี้คือ **บันทึกการวางแผนและการตัดสินใจระหว่างพัฒนา** ไม่ใช่คู่มือระบบ
เนื้อหาที่ยังใช้งานจริงถูกสรุปเข้า [`docs/`](../README.md) แล้ว

เก็บไว้เพื่อ: ย้อนดูว่า *ทำไม*ถึงตัดสินใจแบบนั้น · ตัวเลขที่เคย verify ไว้ · ปมที่เคยแก้

> ⚠️ ไฟล์เหล่านี้อาจมีข้อมูลที่ล้าสมัยหรือขัดแย้งกับระบบปัจจุบัน — **ถ้าขัดกัน ให้ยึด `docs/` เป็นหลัก**

| ไฟล์ | ขนาด | เนื้อหา |
|---|---|---|
| `MSCI_DASHBOARD_PLAN.md` | 57 KB | แผนหลักทั้งโปรเจกต์ Phase 0–6 · การตัดสินใจเรื่อง NAVDate/collinearity/threshold · §0.1 คือผลรีวิวเทียบข้อมูลจริง |
| `MSCI_DASHBOARD_CODE_REVIEW.md` | 41 KB | code review หลายรอบ + สถานะการแก้แต่ละจุด |
| `VOL_FORECAST_PLAN.md` | 20 KB | สเปกหน้า 4 (EWMA/GARCH) · §0.1 คือข้อสรุปเรื่องนิยามหน่วย forecast |
| `MATCH_STRENGTH_SECONDARY_PLAN.md` | 13 KB | แผนเปลี่ยนนิยาม secondary เป็น band-based (implement แล้ว 2026-09-09) — รุ่นล่าสุดหลัง recheck คู่กับแผนหน้า 5 (ย้าย `classify_exposure()` ไปเป็นฟังก์ชันกลางใน `matching.py`) |
| `PAGE5_VOL_RETURN_PLAN.md` | 26 KB | แผนหน้า 5 (Vol-Return Scatter + fund drill-down) · อ้างอิง band-based secondary จาก `MATCH_STRENGTH_SECONDARY_PLAN.md` |
| `PAGE6_STYLE_FACTOR_PLAN.md` · `PAGE6_STYLE_FACTOR_PLAN_REVIEW.md` | 14 KB · 15 KB | แผน + review หน้า 6 (Style Match) — review เป็นจุดที่แก้ methodology จริง (excess return de-market ก่อน regress) |
| `PAGE7_MACRO_CHAIN_PLAN.md` · `PAGE7_MACRO_CHAIN_PLAN_REVIEW.md` | 25 KB · 12 KB | แผน + review หน้า 7 (Macro Chain) — review พบ 3 บั๊กสำคัญที่ implementation จริงแก้ไปแล้ว (standardized coef, double-counting, unit normalization — ดู [methodology §7](../appendix/methodology.md)) |
| `fetch_macro_exploratory.py` · `stage1_macro_exploratory.py` · `macro_factor_test.csv` | 4 KB · 4 KB · 177 KB | สคริปต์/ข้อมูล exploratory ตอนวางแผนหน้า 7 (fetch + Stage 1 validation) — ระบบจริงใช้ `data/macro_factor.py` + `analysis/macro_chain.py` แทน · path ในสคริปต์อ้าง root โปรเจกต์เดิม |

## หมายเหตุจุดที่ archive ขัดกับระบบปัจจุบัน
- `MATCH_STRENGTH_SECONDARY_PLAN.md` **§6.1 ระบุว่า ABAGS ควรได้ secondary 3 ตัว** (รวม EUROPE)
  → ของจริงได้ **2 ตัว** เพราะ EUROPE อยู่ที่ 66% ของ primary ไม่ถึงเกณฑ์ 70%
  โค้ดถูกต้องตามนิยาม 30% band (ยืนยันด้วยตาราง §2 ของแผนเองที่ตรงกับผลจริงทุกช่อง)
- แผนเก่าบางไฟล์ยังอ้างถึง **หน้า 5 (Return Forecast)** ซึ่ง**ถูกลบออกจากระบบแล้ว** (2026-09-09) — หน้า 5 ปัจจุบันคือ Vol-Return Scatter · ระบบปัจจุบันมี 8 หน้า
- `PAGE6_STYLE_FACTOR_PLAN.md` §3 เสนอ blend 60/40 (US/Intl) แบบ generic และ regress ETF ดิบตรงๆ — `PAGE6_STYLE_FACTOR_PLAN_REVIEW.md` ข้อ 1 ชี้ว่าต้อง de-market ก่อน (ETF เป็น long-only ไม่ใช่ long-short) ระบบจริงใช้วิธี relative level (`level ÷ ACWI_ETF`) ตามที่ review เสนอ ไม่ใช่ raw excess return แบบที่ review เขียนไว้เป๊ะๆ — รายละเอียดวิธีจริงดู [docs/pages/6-style-match.md](../pages/6-style-match.md)
- `PAGE7_MACRO_CHAIN_PLAN.md` เสนอ scope "ทุกกอง" และ schema/module ที่ต่างจากที่ implement จริง (ดู `PAGE7_MACRO_CHAIN_PLAN_REVIEW.md` + [methodology §7](../appendix/methodology.md) สำหรับของจริง) — implementation จริงยังแก้บั๊กเพิ่มอีก 3 จุดที่ทั้งแผนและ review ไม่เคยพบ (standardized-vs-raw coefficient, country/sector double-counting, unit normalization)
