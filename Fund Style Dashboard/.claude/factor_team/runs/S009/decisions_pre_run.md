# decisions_pre_run — S009 (เขียนก่อน fit ทุกแบบ · การตีความจุดกำกวม)

เวลา: 2026-10-17T04:08:52 · ลำดับ: regression → ter_qa.json → chars.csv → groups.csv → ไฟล์นี้ → fit

## ก. การตีความจุดกำกวม (เลือกแบบกระทบผลน้อยสุด)
1. **เลข test:** test_l3.py เดิมใช้เลขถึง 49 → test ใหม่ของ S007 เลข 48–68 ตั้งชื่อ `test_s9_<เลข>_…` ใน `lib/tests/test_l4.py` เพื่อไม่ให้เลขชน (เลขในชื่อ = เลขของ spec) · เพิ่ม test_s9_69 ตรวจ `MixedProvider` / `sub_fit`
2. **`ff_bootstrap`** รับ provider (`.design(code)`) แทน `design_fn` ตามที่ S007 8.2 ร่างไว้ — พฤติกรรมเท่ากัน · กองเข้ารอบเมื่อมี ≥ 104 แถวไม่ขาดจากแถวที่ resample ได้ (นับจากแถวที่สุ่มได้จริงในรอบนั้น)
3. **ชุดที่ fit:** fit ทุกแถวบน EVAL 207 แล้วตัด MGAPVD (ข้อ 54) ออกเป็น α-family 206 ก่อนทำ BH / BY / MDA / ตาราง Q2 / X · scorecard ใช้ EVAL 207 ตาม S003–S006 · min_obs = 52 (train / full / test) · bootstrap ≥ 104
4. **p ค่าสอง​ด้านของ α** = 2·SF(|t_HAC|) แบบ normal (แบบเดียวกับ S006) · se(α̂) = |α̂/t| (m4) · BH/BY q = 0.10 ต่อ (แถว × ช่วง) บน 206 กอง
5. **CI ของ xsec** ใช้ t(G−1) (G = จำนวนกลุ่มกองอิสระใน regression นั้น) · Wald ร่วมของ dummy กลุ่มใช้ χ²(q) ด้วย V แบบ CR1 · HC1 = N/(N−K) · WLS น้ำหนัก 1/se² (X4 = OLS)
6. **'ครบ train'** = ผลตอบแทนไม่ว่างทุกสัปดาห์ของ train (156) · u (residual) ใช้ 155 แถว (แถวแรกไม่มี lag) · PCA กลุ่มบน correlation ของ u ที่ตัวแทน cluster (FundCode น้อยสุดต่อกลุ่มอิสระที่ครบ train)
7. **k_g:** `group_k` ใช้ `onatski_ed(kmax=3)` + `parallel_analysis(n_perm=500, q=0.95, seed=20261015)` · ตัวแทน < 8 → `ed_small` และใช้ LOO-mean ทั้งกลุ่ม · ED ไม่ลู่เข้า → `ed_none` เช่นกัน
8. **null กลุ่มสุ่ม (b):** 200 draw · `default_rng(20261015)` ใหม่ต่อ (กลุ่ม × ฐาน) · กลุ่มเรียงตามชื่อ · pool = กอง E ใน α-family นอกกลุ่ม g และนอก cluster ของ i (PCA: ตัวแทน cluster ที่ครบ train) · ทำเฉพาะกลุ่ม G-E ที่มีวิธี PCA / LOO-mean · G-F / G-O ไม่ทำ null
9. **ธีม ACWI_CD (G-T) และ LOO-mean ธีม:** ไม่ได้ทำในรอบนี้ถ้าไม่มีหัวข้อ 'ธีม' ใน results.md (บันทึกใน 'ค้าง')
10. **FXβ** = b0+b1 ของ FX ใน y ~ [MKT, FX] train (min_obs 52) ทุก policy · 1−R² ของ M3/M4 ใช้ adj R² ของ model ตัวเอง (m10) · M1/M2 ของ model ตัวเอง
11. **log AUM:** สัปดาห์แรกที่มีค่าใน train · X5 ทำเมื่อครอบคลุม ≥ 80% ของ E · มิฉะนั้น N/A
12. **FX gap:** กองที่ FXβ = มัธยฐานกลุ่มพอดีถูกตัดจากทั้งสองข้าง · กลุ่มที่เข้า = G-E ที่มีสมาชิก E (α-family) ≥ 10
13. **ป้าย 'แยกจากโชคไม่ได้':** ใช้เมื่อ p_boot (หางบน) ของ **สัดส่วน** BH ของ M1 หรือ M2 > 0.10 (S008 F · m5)
14. **Q2 sign:** sign(α̂_train) = sign(α̂_test) = sign(α̂_full) แยกฐาน · α̂ = 0 / NaN นับว่าไม่ตรง
15. **ชื่อ factor กลุ่ม:** ผู้สมัคร = e ของ M28 (residualize บน f ด้วย `l3.residualize`) + ETF ส่วนขยาย 14 ตัว (`l3.ext_excess`) · factor กลุ่มฉบับรวม = factor ของตัวแทน cluster ทั้งกลุ่ม (PC1 สำหรับ PCA) หรือ mean ของสมาชิกทั้งกลุ่ม · ป้าย 'ชื่อ' |corr| ≥ 0.7 ทั้ง train และ test · 'คล้าย' 0.5–0.7
16. **ลดขอบเขต (ค้าง/ไม่ได้ทำในรอบนี้ ถ้ามีในหัวข้อ 'ค้าง' ของ results.md):** monthly · G-T ธีม · stability/rolling เฉพาะที่ระบุใน results.md

## ข. กติกา TER และ d_rate (S009 1.1, 1.4) — ผลที่ได้จากข้อมูล (ก่อน fit)
- เซลล์ vintage × src: [{"ter_vintage": "le2025", "ter_src": "actual", "policy": "E", "n": 34}, {"ter_vintage": "le2025", "ter_src": "actual", "policy": "F", "n": 4}, {"ter_vintage": "le2025", "ter_src": "actual", "policy": "O", "n": 5}, {"ter_vintage": "le2025", "ter_src": "rate", "policy": "E", "n": 1}, {"ter_vintage": "le2025", "ter_src": "rate", "policy": "F", "n": 1}, {"ter_vintage": "y2026", "ter_src": "actual", "policy": "E", "n": 139}, {"ter_vintage": "y2026", "ter_src": "actual", "policy": "F", "n": 13}, {"ter_vintage": "y2026", "ter_src": "actual", "policy": "O", "n": 9}]
- QA TT ≥ OF: {'n': 204, 'frac': 0.9803921568627451, 'thr': 0.9} · ter_dropped = False · กอง Rate: ['FCSCBSETE', 'KKP G-UBOND-H-U']
- Rate − Actual (ก): {'n': 204, 'median': 3.20981, 'q25': 2.455, 'q75': 3.7199999999999998, 'frac_pos_or_zero': 1.0} · (ข): {'n': 102, 'median': 3.40385, 'q25': 2.836275, 'q75': 4.176125, 'frac_pos_or_zero': 1.0}
- ความเสถียรข้ามรุ่น TER (Actual 2026 − Actual ≤ 2025): {'n': 39, 'median': 0.020000000000000018, 'q25': -0.010000000000000009, 'q75': 0.2983149999999999, 'frac_pos_or_zero': 0.717948717948718, 'corr': 0.91964996027229}

## ค. คอลัมน์และจำนวนกองที่ใช้จริงต่อ regression (ก่อน fit · ลำดับ S008 I.3)
- **X2_E**: n = 173 · กลุ่มอิสระ = 142 · คอลัมน์ = ['const', 'ter', 'FXb', 'omr', 'DIV', 'd_v2026', 'G_MSCI_ACWI_CD', 'G_MSCI_ACWI_IT', 'G_MSCI_ASIA_EX_JAPAN', 'G_MSCI_CHINA_ALL_SHARES'] · ตัดคอลัมน์ = ['d_rate'] · ตัดกอง (TER=NaN, d_rate) = ['FCSCBSETE']
- **X1_ALL**: n = 204 · กลุ่มอิสระ = 166 · คอลัมน์ = ['const', 'ter', 'FXb', 'omr', 'DIV', 'd_v2026', 'F', 'O', 'G_MSCI_ACWI_CD', 'G_MSCI_ACWI_IT', 'G_MSCI_ASIA_EX_JAPAN', 'G_MSCI_CHINA_ALL_SHARES'] · ตัดคอลัมน์ = ['d_rate'] · ตัดกอง (TER=NaN, d_rate) = ['FCSCBSETE', 'KKP G-UBOND-H-U']
- **XV1_ALL_actual_le2025**: n = 43 · กลุ่มอิสระ = 40 · คอลัมน์ = ['const', 'ter', 'FXb', 'omr', 'DIV', 'F', 'O', 'G_MSCI_ACWI_CD', 'G_MSCI_ACWI_IT', 'G_MSCI_CHINA_ALL_SHARES'] · ตัดคอลัมน์ = ['d_v2026', 'd_rate', 'G_MSCI_ASIA_EX_JAPAN'] · ตัดกอง (TER=NaN, d_rate) = []
- **XV2_E_actual_le2025**: n = 34 · กลุ่มอิสระ = 32 · คอลัมน์ = ['const', 'ter', 'FXb', 'omr', 'G_MSCI_ACWI_CD', 'G_MSCI_ACWI_IT', 'G_MSCI_CHINA_ALL_SHARES'] · ตัดคอลัมน์ = ['DIV', 'd_v2026', 'd_rate', 'G_MSCI_ASIA_EX_JAPAN'] · ตัดกอง (TER=NaN, d_rate) = []
- **XE67**: n = 66 · กลุ่มอิสระ = 60 · คอลัมน์ = ['const', 'ter', 'FXb', 'omr', 'DIV', 'd_v2026', 'G_MSCI_ACWI_CD', 'G_MSCI_ACWI_IT', 'G_MSCI_ASIA_EX_JAPAN', 'G_MSCI_CHINA_ALL_SHARES'] · ตัดคอลัมน์ = ['d_rate'] · ตัดกอง (TER=NaN, d_rate) = ['FCSCBSETE']
- X3 / X4 / X5 ใช้ชุดและคอลัมน์เดียวกับ X2 (X5 + log_aum ถ้าครอบคลุม ≥ 80%) · XV ตัด d_v2026 / d_rate โดยกฎ < 3 กอง (ค่าคงที่)
- seed 20261015 · B_ff 999 · n_null 200 · n_perm 500 · PY B 999 · bootstrap CI 2000
