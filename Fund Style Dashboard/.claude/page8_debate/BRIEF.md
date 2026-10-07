# BRIEF (ใช้ร่วมกันทุก agent) — หน้า 8 "Score Screen"

บริบท: Streamlit Fund Style Dashboard หน้า 8 (`pages/8_🧭_Score_Screen.py`) คัด Top 5 กองทุนจากคะแนน แล้วสร้าง Efficient Frontier.

## ไฟล์ที่ต้องอ่าน (path สัมพัทธ์จาก root โปรเจกต์)
- `pages/8_🧭_Score_Screen.py`, `analysis/portfolio.py`, `analysis/screening.py`
- `data_access.py` (ฟังก์ชัน `portfolio_risk_model`), `config.py` (ค่าคงที่ `SCORE_*`, `PORTFOLIO_*`)
- `docs/pages/8-score-screen.md`, `PAGE8_PORTFOLIO_OPTIMIZE_PLAN.md` (§12–§20; §19–§20 คือการแก้ล่าสุด)
- `tests/test_portfolio.py`, `tests/test_screening.py`

## กฎเหล็ก READ-ONLY
- ห้ามแก้/สร้าง/ลบไฟล์ใดๆ ในโปรเจกต์ (ห้าม `sed -i`, ห้าม redirect ลงโฟลเดอร์โปรเจกต์)
- ทำ what-if ได้โดยรัน `python3` (heredoc หรือ `-c`) ที่ import โมดูลโปรเจกต์แล้ว print ผลออกหน้าจอเท่านั้น; ไฟล์ชั่วคราวเขียนได้เฉพาะ `/tmp` (ตัวอย่างสคริปต์: `.claude/page8_debate/whatif/`)
- ใช้ `PYTHONDONTWRITEBYTECODE=1` และ `pytest -p no:cacheprovider`
- ห้ามแก้ `analysis/matching.py`, `analysis/macro_chain.py`, `analysis/metrics.py` (import ใช้อย่างเดียว)
- ข้อสังเกต: การ `import data_access` เรียก `nav_loader` ซึ่งเขียนทับ `cache/nav_spike_fixes.csv` (Critic พบใน session แรก) — ตรวจว่าเนื้อหาไม่เปลี่ยนหลังรัน
- ตอบเป็นภาษาไทย อ้างหลักฐาน (ไฟล์:บรรทัด หรือผลรัน) ทุกข้อ ห้ามเดา

## ระบบปัจจุบัน (ตัดสินใจไว้แล้ว)
1. **Risk model** Σ = B·F·Bᵀ + D. B = ElasticNetCV joint betas (ประเทศ 11 หรือ 18 ตาม toggle + 10 sector = 21/28 factors, unstandardized), F = Ledoit-Wolf annualized factor cov, D = idiosyncratic variance = (1−R²)×total var (diagonal). window เดียว `PORTFOLIO_LOOKBACK_DAYS=756` (3 ปี) สำหรับ B, F, vol (obs:param ≈16–22:1). R² เป็น in-sample.
2. **Π (Black-Litterman implied return)** = γ·Σ_sys·w_ref; Σ_sys = Σ − diag(D) (idiosyncratic ไม่ถูกตีราคา), w_ref = 1/N (`PORTFOLIO_REF_WEIGHT="equal"`; ตัวเลือก `"aum"` cap 50%), γ=2.5 คงที่. ความเสี่ยงพอร์ตใช้ Σ เต็ม. เหตุที่แก้: TCHTECH-A (AUM 73.5% ของ 5 กอง, vol 36%, R² 0.46) เคยได้ Π 17.65% → weight 30% → risk contribution 68%; หลังแก้ Π 4.7%, weight 11%, RC 18%. ข้อจำกัดที่รู้: Π ไม่มีสัญญาณ zone-score (ไม่มี BL views).
3. **Score**: Part 1 zone score = return_pct (12m−1m cumulative, window 252 skip 21) × vol_pct_good (GARCH 21d forecast กลับด้าน), rescale (0.01,0.99) แล้ว re-rank percentile ภายใน universe ที่เลือก. Part 2 fund score = country_r2 × sector_r2 × zone matrix ของคู่หลัก (คู่รองใช้ `score_secondary` + band `SCORE_SECONDARY_BAND_PCT=0.30`). `greedy_select` เลือก country/sector ไม่ซ้ำ (AND/OR) เติมที่เหลือ; ต้อง pair score ≥ `SCORE_MIN_ELIGIBLE=0.7` (คะแนนของคู่ที่ใช้จริง). country_r2/sector_r2 มาจาก regression แยก scope ใช้ history เต็ม (ไม่ใช่ R² ของ risk model 3y). `ann_return` ในตาราง = geometric annualized history เต็ม.
4. **Frontier**: grid enumeration น้ำหนักจำนวนเต็ม %, min 5%, max 40%, step 1%, `PORTFOLIO_MIN_FUNDS=3`, `PORTFOLIO_TOP_N=5`, Pareto mask, max-Sharpe rf=0. nitpick ที่ยังไม่แก้: `front_w`/`frontier` argsort pairing. ไม่มี RC cap, ไม่มี R²-floor gate ที่ Part 2. `pytest -q` → 92 passed.

## หัวข้อที่โต้แย้ง (ใช้ชื่อเต็ม ไม่ใช้ตัวอักษร เพราะรอบแรกแต่ละ agent จัด A–D ไม่ตรงกัน)
- Π / Black-Litterman
- Score + Greedy select (รวม threshold 0.7)
- Risk model Σ=BFBᵀ+D
- Frontier + ข้อจำกัด (min 5% / max 40% / min 3 กอง / max-Sharpe rf=0)
