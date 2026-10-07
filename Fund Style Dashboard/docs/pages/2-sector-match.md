# 🏭 หน้า 2 — Sector Match

**ไฟล์:** `pages/2_🏭_Sector_Match.py` → เรียก `page_common.scatter_page("sector", ...)`

## หน้านี้ทำอะไร
เหมือน [หน้า 1](1-country-match.md) ทุกอย่าง — scatter, 4 quadrant, filter, ตาราง — **ต่างแค่จับคู่กับดัชนี sector 10 ตัวแทนประเทศ 18 ตัว**

ทั้งสองหน้าใช้ฟังก์ชันเดียวกัน (`page_common.scatter_page`) ต่างกันแค่พารามิเตอร์ `scope` → แก้ที่เดียวมีผลทั้งคู่

## ข้อมูลที่ใช้
`cache/results.csv` คอลัมน์ฝั่ง sector: `sector_primary`, `sector_secondary`, `sector_primary_coef`, `sector_r2`
(แกน X/Y คือ `ann_return` / `ann_vol` ชุดเดียวกับหน้า 1 — เป็นคุณสมบัติของกอง ไม่ขึ้นกับ scope)

## ดัชนี sector 10 ตัว (ฐาน ACWI ทั้งหมด)
| ย่อ | เต็ม | ย่อ | เต็ม |
|---|---|---|---|
| CD | Consumer Discretionary | IN | Industrials |
| CS | Consumer Staples | IT | Information Technology |
| EN | Energy | MT | Materials |
| FN | Financials | TC | Communication Services |
| HC | Health Care | UT | Utilities |

> ในหน้าเว็บตัด prefix `MSCI_ACWI_` ออกให้เหลือแค่ตัวย่อ — ทำที่ `viz.short(name, scope="sector")` จุดเดียว ใช้ร่วมกันทั้ง hover / filter / ตาราง / กราฟหน้า 3

## ต่างจากหน้า 1 ตรงไหน
| | หน้า 1 (country) | หน้า 2 (sector) |
|---|---|---|
| จำนวนดัชนี | 18 | 10 |
| R² เฉลี่ย | 0.51 | **0.38** |
| กองที่ไม่พบ exposure | 0 | **3 กอง** (ASP-VIET, DAOL-VIETGROWTH, KT-VIETNAM-SSF) |
| collinearity | รุนแรง (ACWI/WORLD ซ้อน) | เบากว่า แต่ทุกตัวแชร์ market factor ของ ACWI ร่วมกัน |

## วิธีอ่าน / ข้อควรระวัง
1. **R² ต่ำกว่าฝั่ง country เป็นเรื่องปกติ** — กองส่วนใหญ่กระจายหลาย sector ไม่ได้เจาะ sector เดียว ดัชนี sector เดี่ยวจึงอธิบายได้น้อยกว่า
2. **กองเวียดนาม 3 กองไม่พบ exposure** — ElasticNet ตัด coefficient เหลือ 0 ทุกตัว เพราะไม่มีดัชนี sector ตัวไหนอธิบายได้ → แสดง "ไม่พบ exposure ชัดเจน" (ถูกต้อง ไม่ใช่บั๊ก)
3. กองที่เจาะ sector จริงจะเห็นชัด เช่น **BCARE → Health Care (R²=0.70)**
