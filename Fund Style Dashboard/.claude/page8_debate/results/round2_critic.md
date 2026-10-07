# รอบ 2 — Critic ตอบข้อแก้ต่างของ Defender

> รัน what-if เพิ่ม 1 ชุด: `whatif/run11.py` (subsample ทุก 1/5/10 NAVDate ร่วมเพื่อเช็ก correlation).

## (ก) ยอมถอย / ยังยืนหยัด
**ยอมถอย**
- น้ำหนักไม่ไวต่อ lookback และต่อ D (28/28/26/18 vs 31/26/26/17 vs 28/29/26/17) — ไม่ใช่ข้อโจมตี
- γ ไม่กระทบน้ำหนัก (ข้อโจมตีคือความหมายของ Sharpe/Π ไม่ใช่น้ำหนัก)
- equal ref แก้ปัญหา AUM ได้จริง (RC ของ KT-JPFUND-A 68% → 48%)
- สูตรคูณ AND, R² เป็นตัวถ่วงที่มีผล, threshold 0.7 อยู่บนที่ราบ (min_score 0.5–0.9 ได้ 4 กองเหมือนกัน)
- ไม่ชนเพดาน 40% / floor 5%; R² in-sample พองไม่มาก (placebo 0.03 vs 0.75)

**ยังยืนหยัดได้**
1. **กองเก่าและข้อมูลสั้น** — Defender ไม่ได้ตอบในรอบ 1; 130/213 NAV เก่ากว่า 2026-06-30; TMBGINFRA 53 obs/21 factor; lookback 504 → `ValueError` ทั้งหน้าพัง
2. **Correlation ต่ำเกินจริง** — แข็งขึ้นหลังทดสอบเพิ่ม (subsample ทุก 1, 5, 10 NAVDate ร่วมผลคงที่):

| คู่กอง | corr โมเดล | corr จริง (step 1 / 5 / 10) |
|---|---|---|
| KT-MFE-A / PRINCIPAL GEF-X | 0.66 | 0.95, 0.96, 0.96 |
| KT-MFE-A / KT-JPFUND-A | 0.31 | 0.60, 0.76, 0.77 |
| KT-MFE-A / K-AEC | 0.24 | 0.64, 0.72, 0.50 |
| PRINCIPAL GEF-X / KT-JPFUND-A | 0.25 | 0.43, 0.76, 0.74 |

   ตัวเลข "corr จริงของกองกระจาย 0.66–0.74" ที่ Defender ยอมรับต่ำกว่าที่วัดได้จริง; RC ของ KT-JPFUND-A 48% (โมเดล) vs 31% (ข้อมูลตรง) เป็นผลข้างเคียงของข้อนี้ ไม่ใช่ข้อยืนยันว่าโมเดลดี
3. **Label primary/secondary ไม่เสถียร** — split-half 23/40 (58%), Spearman 0.30 (Defender ไม่ได้ตอบในรอบ 1)
4. **ความไวต่อ window ของ momentum** — window 189 ทับ 1/5, window 126 ทับ 2/5

## (ข) จุดที่ Defender ยอมรับเองซ้อนกับของ Critic
- ไม่มี R² floor และไม่มี RC cap
- Π ไม่มี zone signal; Sharpe/Π ไม่มีความหมายเชิงระดับ
- สเกล 0.7 ถูกอธิบายผิดว่าเป็น percentile (ค่าจริง 0.007–8.57) — Critic รับเพิ่มเป็นข้อบกพร่องด้านเอกสาร
- Diversification ผลักกองอันดับสูงออก (K-AEC อันดับ 184 เข้า) + corr จริงที่ยังสูง

## (ค) อันดับความรุนแรงใหม่ + ทางแก้ + ขนาดงาน
1. ตัดกองเก่า/obs ไม่พอ: NAV ล่าสุดเก่ากว่าปลาย index ~10 วัน; obs ≥ 5–8× จำนวน factor; fit ต่อกองแบบ try/except — **เล็ก–กลาง**
2. Correlation ต่ำเกิน: blend residual correlation จากกองคู่ที่มี NAV ร่วม (shrink); ตัดกองที่ corr จริง > 0.85 ตอน greedy — **กลาง**
3. ไม่มี R² floor และ RC cap: floor 0.3 ก่อน (แต่เหลือ 3 กอง; 0.4 เหลือ 2 < MIN_FUNDS ต้องมีกลไกเติมกองทดแทน); RC cap เป็นเงื่อนไขกรองในกริด — **กลาง**
4. Label ไม่เสถียร: zone score เฉลี่ยถ่วง |coef| แทน argmax หรือ gate ที่ primary_share/margin — **กลาง–ใหญ่**
5. Sharpe/Π ไม่มีความหมายเชิงระดับ: ซ่อนหรือติดป้าย — **เล็ก**
6. Momentum window fragile: แสดง sensitivity 6/9/12 เดือน — **กลาง**
7. Annualize กับ NAV มีช่องว่าง: annualize ต่อ obs — **เล็ก**
8. เอกสารสเกล score: แก้ `config.py` และ `docs/pages/8-score-screen.md:223` — **เล็ก**

## (ง) คะแนนความมั่นใจต่อดีไซน์ (0–10)
| หัวข้อ | คะแนน | เหตุผลสั้น |
|---|---|---|
| Risk model | 4.0 | น้ำหนักนิ่งแต่ correlation ต่ำเกินชัด และไม่กัน stale/short |
| Π | 6.5 | หลักการถูก ตัด D เอนเอียงที่รับได้ แต่สะท้อนแค่ risk structure |
| Score | 4.5 | สูตร/threshold ทนทาน แต่ label ไม่เสถียร ไม่มี R² floor ไวต่อ window |
| Frontier | 6.5 | กริดปลอดภัย แต่ไม่มี RC cap และ tangency ≈ equal-weight |
