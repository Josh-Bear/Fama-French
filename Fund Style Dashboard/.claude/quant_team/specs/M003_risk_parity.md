# M003 — M002-SR + risk parity (ERC) / HRP

- ผู้เขียน: quant-modeler · 2026-09-30 · สถานะ: **pre-registered** · องค์ประกอบกลาง `M002-M005_plan.md`
- trials: **2** (M003-ERC, M003-HRP) · n_trials_cumulative 6–7 · parent = **M002-SR** (การคัดกองเหมือนกันทุกประการ → Δ มาจากน้ำหนักล้วน)

## 1. สมมติฐาน + หลักฐาน
1. ในกองที่คัดแล้ว ความผันผวนต่างกันมาก (เช่น กองจีน/เวียดนาม/เทค vol 25–35% vs กองโลก/ญี่ปุ่น hedge ~12–15%)
   → EW ให้ risk budget ส่วนใหญ่ไปกองผันผวนสูง · ERC ให้ทุกกองเสี่ยงเท่ากัน → vol พอร์ตลดมากกว่า return ที่ลด
   (Maillard–Roncalli–Teiletche 2010; low-volatility anomaly: Frazzini & Pedersen 2014 — สินทรัพย์ vol ต่ำให้ Sharpe สูงกว่าต่อหน่วยความเสี่ยง)
2. HRP (López de Prado 2016) ไม่ต้อง invert Σ และจัดการกลุ่มกองที่ correlation สูงได้ดี → out-of-sample variance ต่ำกว่า inverse-variance/min-var ในงานต้นฉบับ
3. ไม่ใช้ expected return ในการจัดน้ำหนัก (หลักฐาน M001: Π ไม่มีข้อมูล → max Sharpe ≈ EW) — สัญญาณ return อยู่ที่ขั้นคัดกองเท่านั้น

## 2. อัลกอริทึม ณ วัน t
1. ขั้น 1–4 เหมือน M002-SR ทุกประการ (SR12, N=8, K=16) → S · **state hysteresis ของ M003 แยกของตัวเอง** (แต่ S จะเหมือน M002-SR เพราะ C5 ไม่ขึ้นกับน้ำหนัก — validator ควร assert ว่า S ตรงกับ M002-SR ทุกไตรมาส)
2. Σ ตาม C8 (weekly 52w, listwise ≥ 30 สัปดาห์, Ledoit-Wolf, ×52) · ไม่ครบ → inverse-vol fallback
3. **M003-ERC**: ERC ตาม C8 → cap 25% (C6) · **M003-HRP**: HRP ตาม C8 → cap 25%
4. เงินสด = 0 · rebalance ครบทุกไตรมาส

## 3. พารามิเตอร์
| พารามิเตอร์ | ค่า | หมายเหตุ |
|---|---|---|
| หน้าต่าง Σ | 52 สัปดาห์ (≥ 30 ครบ) | สอดคล้องกับ vol52 ใน C3 · ไม่มี sensitivity (ประหยัด trial) |
| shrinkage | Ledoit-Wolf (constant-correlation ไม่ใช้ — ใช้ sklearn default = scaled identity target) | |
| linkage HRP | single (ตามต้นฉบับ) | |
| เพดาน | 25% | |

## 4. สิ่งที่คาด
- vol พอร์ตลดจาก EW ~1–3 pt · CAGR ลดเล็กน้อย · Sharpe +0.0–0.1 · turnover สูงกว่า M002-SR เล็กน้อย (น้ำหนักขยับตาม Σ) ~+3–8 pt
- HRP ≈ ERC (N=8) · HRP อาจกระจุกกว่าเมื่อมีคลัสเตอร์เดียวใหญ่

## 5. ความเสี่ยง
- ERC ให้น้ำหนักกองผันผวนต่ำ ซึ่งอาจเป็นกองที่ NAV ปรับช้า/ค้าง (vol ต่ำหลอก) → stale guard C3 ช่วยบางส่วน · reviewer ตรวจกองที่ได้น้ำหนักสูงสุดทุกไตรมาส
- Σ จาก 52 สัปดาห์ไม่จับการเปลี่ยน regime เร็ว (2022) — ไม่ tune หน้าต่าง
- 2022-03-31: หน้าต่างครอบคลุมเฉพาะ 2021-04→2022-03 (ประวัติ NAV ส่วนใหญ่เริ่ม 2020–2021)

## 6. baseline
- parent M002-SR (paired Δ) · B0 · M001-MS · ระหว่างกัน ERC vs HRP

## 7. reviewer ตรวจ
1. RC ของ ERC เท่ากัน (ก่อน cap) ทุกไตรมาส · HRP น้ำหนักรวม = 1, ไม่มีค่าลบ
2. Σ ใช้ข้อมูล ≤ t · จำนวน fallback ivol · จำนวนไตรมาสที่ติดเพดาน
3. S เหมือน M002-SR ทุกไตรมาส (ถ้าไม่ = bug)
