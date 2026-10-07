# รอบ 1 — Critic (page8-critic)

> บันทึกจาก session 2026-09-29. สคริปต์ what-if: `whatif/run1.py`–`run10.py` (run11 ใช้รอบ 2).
> ข้อควรรู้: การ import `data_access` เรียก `nav_loader` ซึ่งเขียนทับ `cache/nav_spike_fixes.csv` ตอนโหลด (mtime เปลี่ยน) — agent ไม่ได้เขียนเอง ไม่ได้ตรวจว่าเนื้อหาเปลี่ยนไหม (side effect ระดับต่ำของเส้นทางอ่าน).

## ข้อโจมตี (เรียงตามความรุนแรง)

### 1. [สูง] กองเก่า/ข้อมูลสั้นหลุดเข้าทั้งการคัดและ risk model แล้วมีจุดพังทั้งหน้า
- ไม่มี gate เรื่องความสดของ NAV หรือจำนวน obs ต่อ factor
- index จบ 2026-07-31 แต่ 184/313 กองมี NAV ล่าสุดก่อน 2026-06-30; ในกองที่ผ่าน score ≥ 0.7 จำนวน 213 กอง มี 130 (61%) ที่ NAV เก่ากว่านั้น
- ค่าเริ่มต้น (VIF-11, AND, P+S) ได้ 4 กอง โดย PRINCIPAL GEF-X (NAV จบ 2026-01-07) และ K-AEC (2026-01-08) หยุดไป ~7 เดือน
- โหมด OR เลือก TMBGINFRA (NAV จบ 2023-11-28) มี 53 obs ใน window 756 vs 21 factor = 2.5:1 (ไม่ใช่ 16–22:1)
- lookback=504 → `portfolio_risk_model` โยน `ValueError: TMBGINFRA: in-window obs 0 < 30` → หน้าตกเข้า `st.error` + `st.stop()` (`pages/8_🧭_Score_Screen.py:93-95`) ทิ้งทั้งชุด
- ที่ 756 วัน obs ของ TMBGINFRA ตกต่ำกว่า `MIN_REGRESSION_OBS=30` ภายใน ~23 วันทำการ
- **ทางแก้:** ตัดกองที่ `last_nav < index_end − ~10 วัน` ก่อน `fund_scores`; ต้องมี obs ≥ ~5–8 เท่าของจำนวน factor; fit ต่อกองแบบ try/except ตัดกองที่พังพร้อมเตือน

### 2. [สูง] Σ ประเมิน correlation ต่ำกว่าจริง → ประเมิน diversification เกิน
D เป็น diagonal แต่ residual ของ ElasticNet (ที่ shrink beta) ไม่ orthogonal ข้ามกอง. เทียบ corr บน NAVDate ร่วม (winsorize 1–99%):

| คู่กอง | corr จริง | corr โมเดล |
|---|---|---|
| KT-MFE-A / PRINCIPAL GEF-X | 0.93 | 0.66 |
| KT-MFE-A / LHGREEN-D | 0.79 | 0.60 |
| KT-MFE-A / TUSFIN-A | 0.61 | 0.41 |
| GEF-X / LHGREEN-D | 0.77 | 0.64 |
| GEF-X / TUSFIN-A | 0.62 | 0.48 |
| LHGREEN-D / TUSFIN-A | 0.67 | 0.53 |

ทุกคู่ต่ำเกิน 0.13–0.27; พอร์ต tangency (23/27/23/27%) ความเสี่ยงจริงสูงกว่าโมเดล 9% (12.4% vs 11.4%); "ไม่ซ้ำ country/sector" ไม่กันกองแฝด (MFE-A กับ GEF-X label ต่างกันหลังบังคับ AND แต่ corr 0.93).
**ทางแก้:** blend residual correlation จริงจากกองคู่ที่มี NAV ร่วม (shrink), ตัดกองที่ corr จริง > ~0.85 ตอน greedy, หรือรายงาน "risk ตามโมเดล" คู่กับ "risk แบบ sample cov".

### 3. [สูง] Frontier ที่จุด tangency แทบเป็น equal-weight; return/Sharpe ไม่มีความหมายสัมบูรณ์
- Π = γ(Σ − D)·w_ref → tangency ∝ w_ref − Σ⁻¹D·w_ref = 1/N ปรับด้วย D เท่านั้น
- ชุด LHGREEN/TUSFIN: Sharpe equal 0.257 vs max 0.258 (23/27/23/27 vs 25% เท่ากัน) จากกริด 28,011 พอร์ต
- ชุด 4 กองเริ่มต้น: 28/28/26/18; lookback 504 → 31/26/26/17; 1008 → 28/29/26/17
- Sharpe เป็นเส้นตรงกับ γ: 2.5 → 10 ทำให้ SR 0.21 → 0.86, return 2.3% → 9.0% โดยน้ำหนักไม่ขยับ
- ตารางในหน้าเดียวกันโชว์ ann_return จริงของกอง 24–36% ข้าง Π 1.8–4.2%
- **ทางแก้:** เลิกโชว์ Sharpe/return เป็นค่าสัมบูรณ์ หรือ calibrate γ; ใส่ zone score เป็น BL view; หรือเรียกตรงๆ ว่า "equal-weight ปรับตาม idiosyncratic risk"

### 4. [กลาง–สูง] Label primary/secondary ไม่เสถียร แต่คะแนนคูณจากมัน
- primary = argmax|coef| ของ ElasticNet บน sector index ที่ collinear
- สัดส่วน |coef| ของ primary มัธยฐาน 0.36 (sector) / 0.31 (country); 35% ของกอง secondary ≥ 70% ของ primary; MFE-A secondary/primary = 0.84; GEF-X = 0.97
- split-half top-40: country+sector primary ตรงกันทั้งสองครึ่ง 23/40 (58%); Spearman ของ zone value ของคู่ระหว่างครึ่ง = 0.30; GEF-X เปลี่ยนจาก (Europe, Materials) 17.6 เป็น (USA, IT) 3.5
- R² ที่คูณวัดพลัง market beta ไม่ใช่ความเฉพาะเจาะจงของ match (Global Equity Fund ได้ "USA×Materials")
- **ทางแก้:** zone score เฉลี่ยถ่วง |coef| แทน argmax; gate ที่ primary_share และ margin เหนือ secondary; subsample stability เป็นเงื่อนไข

### 5. [กลาง] Momentum window ไวมาก แต่ threshold 0.7 ไม่ทำงานจริง
- window 252 → 189: ชุด eligible จาก [MFE-A, GEF-X, JPFUND-A, K-AEC] เป็น [TISCOEU-A, TUSFIN-A, JPFUND-A] (ซ้อนกัน 1 จาก 5); window 126 overlap 2; skip 42 เหลือ 3 กอง; window 231/273 เสถียร
- min_score 0.5–0.9 ให้ผล 4 กองเหมือนกันหมด (K-AEC 0.97) แต่ 1.0 → 3 กอง
- rank-based ทำให้ Korea (+171%, vol forecast 119%) ห่างจาก Taiwan (+97%, 51%) แค่ 0.09 ใน return_pct
- **ทางแก้:** รายงาน sensitivity ของ window (6/9/12 เดือน); ใช้ z-score/winsorized ค่าจริงแทนอันดับ

### 6. [กลาง–ต่ำ] Annualize ผิดในกองที่ NAV ไม่ครบวัน
`total_var = annualized_volatility(fund_ret)²` ใช้ ×252 กับผลตอบแทนต่อ NAVDate ที่มีช่องว่าง (ครอบคลุมเฉลี่ย 60% ของวัน; ช่องว่างเฉลี่ย 1.08–1.75 วันทำการ) → variance เกินจริง 1.09–1.68 เท่า (MFE-A vol 13.5% vs gap-adjusted 10.4%); D บวม; แก้แล้ว weight ขยับ ~2–3pt (MFE-A 28% → 31%). **ทางแก้:** annualize ต่อ obs หรือ resample รายสัปดาห์.

## ผลที่ทดสอบแล้วไม่จริง
- **R² in-sample เพี้ยน**: placebo (circular shift ของ factor) ให้ null R² เฉลี่ย 0.03 (max 0.12) ที่ n=53 และ 0.006 (max 0.03) ที่ n=431 vs จริง 0.75/0.76
- **NAV lag**: ไม่มี (R² สูงสุดที่ lag 0: MFE-A 0.763 vs 0.305/0.322 ที่ lag ±1)
- **ชนเพดาน 40% / floor 5%**: ไม่เกิดในทุกชุดที่ทดสอบ

## ข้อที่ร้ายแรงที่สุด 3 ข้อ
1. กองเก่า/ข้อมูลสั้นหลุดเข้า + จุดพังทั้งหน้า
2. Σ ประเมิน corr ต่ำกว่าจริง 0.13–0.27 → risk ต่ำกว่าจริง ~9%
3. tangency ≈ equal-weight และ Sharpe/return เป็นเส้นตรงกับ γ
