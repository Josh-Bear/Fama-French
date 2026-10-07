# 🌍 หน้า 1 — Country Match

**ไฟล์:** `pages/1_🌍_Country_Match.py` → เรียก `page_common.scatter_page("country", ...)`

## หน้านี้ทำอะไร
แสดงกองหุ้นทั้ง 209 กอง (policy E — ดู `config.APP_POLICY`) เป็น scatter ทีเดียว เพื่อตอบว่า **"กองไหนให้ผลตอบแทน/ความเสี่ยงเท่าไหร่ และเกาะดัชนีประเทศไหน"**

| องค์ประกอบ | ค่าที่ใช้ |
|---|---|
| แกน X | annualized return |
| แกน Y | annualized volatility |
| สีจุด | 4 quadrant (ดูตารางล่าง) |
| ขนาดจุด | คงที่ — AUM ดูได้ใน hover (เดิมเคยผูกขนาดกับ AUM แต่จุดใหญ่บังกันจนอ่านยาก) |
| hover | FundCode, ชื่อกอง, primary country, R², AUM, return, vol, **n_obs** |

## ข้อมูลที่ใช้
`cache/results.csv` (209 แถว) ผ่าน `data_access.get_results()` — ไม่แตะไฟล์ดิบตอน render
คอลัมน์หลัก: `ann_return`, `ann_vol`, `country_primary`, `country_secondary`, `country_r2`, `aum`, `n_obs`
(ไฟล์ยังมีคอลัมน์ `policy` ไว้เป็น provenance แต่มีค่าเดียวแล้ว จึงไม่แสดงในหน้าเว็บ)

## การแบ่ง 4 quadrant
เส้นแบ่ง: **แนวตั้งที่ return = 0** · **แนวนอนที่ median volatility ของกองที่แสดงอยู่ในกราฟ ณ ตอนนั้น**

| Quadrant | เงื่อนไข | สี |
|---|---|---|
| Q1 บนขวา | return > 0, vol > median | 🟢 เขียว |
| Q2 บนซ้าย | return < 0, vol > median | 🟡 เหลือง |
| Q3 ล่างซ้าย | return < 0, vol < median | 🔴 แดง |
| Q4 ล่างขวา | return > 0, vol < median | 🔵 น้ำเงิน |

> ⚠️ median คำนวณจาก**กองที่แสดงอยู่หลัง filter** ไม่ใช่ทั้ง 313 กองเสมอ → เปลี่ยน filter แล้วสีของกองเดิมอาจเปลี่ยนได้ (ตั้งใจตามสเปก "median ของกองในกราฟ")

## Filter ที่มี
1. **primary country** — เลือกเฉพาะบางประเทศ (ว่าง = ทั้งหมด)
2. **R² ขั้นต่ำ** — slider ซ่อนกองที่ match ไม่มั่นใจ

> ตัวกรอง **Fund Policy** ถูกเอาออก (2026-09-29) เพราะ pipeline กรองเหลือ policy E อย่างเดียวแล้ว

## รายละเอียดการแสดงผล
- **แกนตัดที่ percentile 1–99** ของกองที่แสดงอยู่ (+ขอบ 8%) เพื่อกันกอง outlier ผันผวนสูงดันสเกลจนกองส่วนใหญ่กระจุกกัน — จุด outlier ยังอยู่ในข้อมูลครบ ซูมออกเองได้
- กองที่ ElasticNet ตัด coefficient เหลือ 0 หมด → ช่อง primary แสดง **"ไม่พบ exposure ชัดเจน"** (ฝั่ง country ปัจจุบันไม่มีกองแบบนี้)
- ตารางข้อมูลใน expander ด้านล่าง มีคอลัมน์ `n_obs` ให้ประเมินความน่าเชื่อถือของ return/vol

## วิธีอ่าน / ข้อควรระวัง
1. **ดู R² ก่อนเชื่อ primary เสมอ** — กองหุ้นมี R² เฉลี่ย ~0.57 (country) แต่กระจายกว้าง · กองที่ R² ต่ำมากแปลว่าดัชนีชุดนี้อธิบายกองนั้นได้น้อย
   (กอง F/O ที่ R² เฉลี่ยแค่ 0.15-0.17 คือเหตุผลที่ถูกตัดออกจากระบบตั้งแต่ pipeline)
2. **ดัชนีรวมแย่ง primary** — กองหุ้นสหรัฐฯ อาจขึ้น primary เป็น ACWI/WORLD แทน USA เพราะดัชนีซ้อนทับกัน (ดู [data-sources §collinearity](../appendix/data-sources.md))
3. **n_obs ต่ำ = ตัวเลข return/vol พองได้** (ดู [methodology §3](../appendix/methodology.md))

## ผลที่ verify แล้ว
- R² เฉลี่ยฝั่ง country = **0.51** · แยกตามประเภท: **E=0.57 · F=0.15 · O=0.17** (ตรงตามทฤษฎี)
- ตัวอย่างที่ตรวจด้วยมือ: K-INDIA → INDIA (R²=0.74) · ABJO → JAPAN (0.73) · ABEG → EUROPE (0.49)
