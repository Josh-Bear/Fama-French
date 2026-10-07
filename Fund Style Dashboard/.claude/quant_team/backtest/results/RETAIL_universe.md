# RETAIL_universe — ตัด class ที่รายย่อยซื้อไม่ได้ แล้วรันโมเดลหลักซ้ำ (2026-10-06 · backtest-validator)

**แก้ความถูกต้องของ universe / เปลี่ยนวิธีวัด — ไม่ใช่ trial ใหม่** (ไม่แตะ `trials.csv`, ไม่แก้ `run_m0xx` เดิม) · สคริปต์ `backtest/rerun_retail_universe.py` · ค่าธรรมเนียม = `fees.FeeData` ค่าเริ่มต้นใหม่ (ตรงกับแอป) · วัดด้วย rf จริง (policy rate) · 15 ไตรมาส 2022-03→2025-12

## 1. กติกาตัด class
- ตัด class ที่ **ขั้นต่ำซื้อครั้งแรก (`FundProfile.fst_lowbuy_val`) > 100,000 บาท** · ข้อมูลนี้มีครบทั้ง 570 class (ไม่ต้องตัดสินด้วยชื่อ class) · ชื่อ class ใช้ตรวจประกอบ: class ชื่อ -X/-P/-C (TL*, PRINCIPAL, KT-*-P, ASP-X) ขั้นต่ำ ≤ 1,000 บาท = รายย่อยซื้อได้ → ไม่ตัด · `KT-GEQ-I` ขั้นต่ำ 50,000 → ไม่ตัด (ตามกติกา ≤ 100,000)
- **ข้อจำกัด**: `FundProfile.csv` เป็น snapshot ปัจจุบัน ใช้ตัดทุกวันย้อนหลัง (ไม่ point-in-time) — ขั้นต่ำในอดีตอาจต่างจากวันนี้ · ไฟล์ schema PDF เปิดอ่านข้อความไม่ได้ในเครื่องนี้ (เป็นเวกเตอร์ ไม่มี text layer) จึงตีความ `fst_lowbuy_val` = ขั้นต่ำซื้อครั้งแรก (บาท) จากชื่อคอลัมน์ + ค่าตรงกับที่ผู้ใช้ระบุ (ONE-GLOBFIN-IA 5 ล้าน, ONE-INDIAOPP-IA 30 ล้าน) — ไม่ได้ยืนยันกับ schema
- `Project Retail Type` = R ทุก class ใช้แยกไม่ได้

## 2. class ที่ถูกตัด (8 จาก 570)
| class | family | ขั้นต่ำซื้อครั้งแรก (บาท) | class รายย่อยที่เหลือใน family | ผล |
|---|---|---|---|---|
| MATECH-IA | MATECH | 50,000,000 | MATECH-A, MATECH-D | ใช้ class รายย่อยแทน |
| MGAI | MGAI | 1,000,000 | — | ตัดทั้ง family (มีแต่สถาบัน) |
| ONE-GLOBFIN-IA | ONE-GLOBFIN | 5,000,000 | ONE-GLOBFIN-RA, ONE-GLOBFIN-RD | ใช้ class รายย่อยแทน |
| ONE-GLOBFIN-ID | ONE-GLOBFIN | 5,000,000 | ONE-GLOBFIN-RA, ONE-GLOBFIN-RD | ใช้ class รายย่อยแทน |
| ONE-INDIAOPP-IA | ONE-INDIAOPP | 30,000,000 | ONE-INDIAOPP-RA, ONE-INDIAOPP-RD | ใช้ class รายย่อยแทน |
| ONE-INDIAOPP-ID | ONE-INDIAOPP | 30,000,000 | ONE-INDIAOPP-RA, ONE-INDIAOPP-RD | ใช้ class รายย่อยแทน |
| ONE-UGG-IA | ONE-UGG | 25,000,000 | ONE-UGG-RA | ใช้ class รายย่อยแทน |
| PRINCIPAL VNEQ-I | PRINCIPAL VNEQ | 500,000 | PRINCIPAL VNEQ-A | ใช้ class รายย่อยแทน |

- family ที่ตัดทั้ง family: **MGAI** (class เดียว ขั้นต่ำ 1 ล้าน) · family อื่นที่เหลือ class รายย่อย: ตัวแทน family เปลี่ยนเป็น class รายย่อยที่ SR12 สูงสุดโดยอัตโนมัติ (เช่น ONE-GLOBFIN-RA แทน -IA; ONE-INDIAOPP-RA/RD ไม่ได้ถูกเลือกเพราะ SR12 ต่ำกว่า -IA หลังหัก fee ของ class)
- ขนาด universe: U_t เหลือน้อยลง 6–8 class ต่อไตรมาส (เช่น 2025-12: 396 → 390) · ตาราง `RETAIL_universe_by_quarter.csv`, รายชื่อทั้ง 570 class `RETAIL_class_table.csv`

## 3. Regression (ก่อนตัด class) — ผ่าน
- universe เต็ม + fees ใหม่: **B0 full rf 2% = 0.059449** · Trend 25 rf 2% = 0.706119 / 0.720494 / 0.893296 (ไม่เปลี่ยน) · rf จริง: Trend 25 0.7193, M011 0.6488, M012-QF-S 0.6596, M013-GC75 0.7646 (ตรงไฟล์เดิมทุกตัว < 5e-7) · B0 rf จริง 0.0760 → 0.0759

## 4. Sharpe เดิม vs ใหม่ (rf จริง · universe เต็ม fees ใหม่ → universe รายย่อย)
| โมเดล | full เดิม | full ใหม่ | Δ (CI95% paired) | nofront เดิม→ใหม่ | 0% เดิม→ใหม่ | CAGR full เดิม→ใหม่ | maxDD ใหม่ |
|---|---|---|---|---|---|---|---|
| B0 (ถือเท่ากันทุกกอง) | 0.076 | **0.077** | +0.001 [-0.000, +0.002] | 0.117→0.117 | 0.117→0.117 | 1.96%→1.97% | -21.4% |
| Trend 25 (M004-TF-FX) | 0.719 | **0.624** | -0.096 [-0.252, +0.003] | 0.906→0.807 | 0.907→0.808 | 9.09%→7.94% | -11.2% |
| M011-RFH | 0.649 | **0.643** | -0.006 [-0.058, +0.046] | 0.836→0.826 | 0.837→0.827 | 8.21%→8.17% | -11.2% |
| M012-QF-S | 0.660 | **0.687** | +0.028 [-0.058, +0.121] | 0.835→0.853 | 0.836→0.854 | 8.33%→8.70% | -10.2% |
| M013-GC75 | 0.765 | **0.779** | +0.014 [-0.084, +0.118] | 0.951→0.953 | 0.952→0.954 | 8.19%→8.44% | -8.0% |

- ลำดับโมเดล (full): เดิม M013 0.765 > **Trend 25 0.719** > M012 0.660 > M011 0.649 > B0 · ใหม่ M013 0.779 > M012 0.687 > M011 0.643 > **Trend 25 0.624** > B0 0.077 → **ลำดับเปลี่ยน**: Trend 25 ตกจากที่ 2 เป็นที่ 4 (ตัวที่โดนผลเต็มๆ คือ ONE-INDIAOPP-IA/ONE-GLOBFIN-IA ที่ถูกถือ 4 ไตรมาสติด) · M012/M013 ดีขึ้นเล็กน้อย (ได้กองอื่นแทน) · ทุก Δ มี CI คร่อม 0 (พอร์ต 8 กอง × 15 ไตรมาส → ชุดกองเปลี่ยนแค่ 2–6 ไตรมาสจึงเป็น path luck เป็นหลัก)
- Sharpe ช่วง 2023-07→2025-12 (full ใหม่): Trend 25 1.05 · M011 1.05 · M012 1.06 · M013 1.07 · ปี 2022 ไม่เปลี่ยน (−1.01/−1.01/−1.02/−1.49) เพราะ class ที่ตัดอยู่ในพอร์ตเฉพาะ 2024–25

## 5. ไตรมาสที่ชุดกองเปลี่ยน (จาก 15 ไตรมาส)
| โมเดล | จำนวนไตรมาสที่เปลี่ยน | ไตรมาส (t) : ออก → เข้า |
|---|---|---|
| Trend 25 (M004-TF-FX) | 5 | 2024-06-28: ONE-INDIAOPP-IA → TSTAR-UH<br>2024-09-30: ONE-INDIAOPP-IA → K-US500X-A(A)<br>2024-12-31: ONE-GLOBFIN-IA → K-US500X-A(A)<br>2025-03-31: ONE-GLOBFIN-IA → TISCOC19<br>2025-06-30: DAOL-GOLD → TISCOC19 |
| M011-RFH | 2 | 2024-06-28: ONE-INDIAOPP-IA → TSTAR-UH<br>2024-09-30: ONE-INDIAOPP-IA → ABIG |
| M012-QF-S | 6 | 2024-03-29: K-JPX-A(A) → K-USXNDQ-A(A)<br>2024-06-28: K-JPX-A(A);ONE-INDIAOPP-IA → TSTAR-UH;TUSEQ-UH<br>2024-09-30: ONE-INDIAOPP-IA → KT-WEQ-A<br>2024-12-31: LHESPORT-A → KT-WEQ-A<br>2025-03-31: ONE-GLOBFIN-IA → ONE-GLOBFIN-RA<br>2025-06-30: ES-GINFRA-A → ONE-GLOBFIN-RA |
| M013-GC75 | 6 | 2024-03-29: K-JPX-A(A) → K-USXNDQ-A(A)<br>2024-06-28: K-JPX-A(A);ONE-INDIAOPP-IA → TSTAR-UH;TUSEQ-UH<br>2024-09-30: ONE-INDIAOPP-IA → KT-WEQ-A<br>2024-12-31: LHESPORT-A → KT-WEQ-A<br>2025-03-31: ONE-GLOBFIN-IA → ONE-GLOBFIN-RA<br>2025-06-30: ES-GINFRA-A → ONE-GLOBFIN-RA |

- ชุดกองเปลี่ยนจาก **การถือ class ที่ถูกตัด** (ONE-INDIAOPP-IA ไตรมาส 2024-06/09 · ONE-GLOBFIN-IA 2024-12/2025-03) และจากผลต่อเนื่อง (hysteresis ทำให้กองอื่นต่างไปอีก 1–2 ไตรมาส เช่น K-JPX-A(A), LHESPORT-A, ES-GINFRA-A, DAOL-GOLD) · มีเพียง M012/M013 ที่ ONE-GLOBFIN-IA ถูกแทนด้วย class รายย่อยของ family เดียวกัน (ONE-GLOBFIN-RA, 2025-03) · ที่เหลือ family นั้นหลุดจาก 8 อันดับ
- B0: ตัดแล้วจำนวนกองลดลง 0–1 กอง/ไตรมาส (เพราะ B0 = 1 class/กลุ่มจาก AUM มากสุด) → Sharpe เปลี่ยนน้อยมาก (0.0759→0.0766)

## 6. ข้อสังเกต / ข้อสงสัย
- Δ ของ Trend 25 (−0.096) ใกล้ขอบ CI (−0.252, +0.003) และเกือบทั้งหมดมาจากการถือ 2 class นี้ 4 ไตรมาส (น้ำหนัก 9–13%) — ไม่ควรตีความว่า Trend 25 'แย่ลง' เชิงโครงสร้าง แต่ผล backtest เดิมของ Trend 25 **เกินจริง** ส่วนหนึ่งเพราะถือกองที่ซื้อไม่ได้
- กฎตัดใช้ snapshot ปัจจุบัน: ถ้าอยากเข้มกว่า (เช่นตัด -X/-P/KT-GEQ-I ด้วยชื่อ) ต้องให้ผู้ใช้ตัดสิน — ตอนนี้ไม่ตัด เพราะขั้นต่ำจริงต่ำ
- Quality filter ของ M012 (AUM family ≥ 100 ล้าน) ยังรวม AUM ของ class ที่ตัดในผลรวม family ตามเดิม (AUM เป็นของกอง ไม่ใช่ของ class) — ไม่เปลี่ยนนิยาม
- ไฟล์: `RETAIL_results.csv`, `RETAIL_paired.csv`, `RETAIL_quarter_diff.csv`, `RETAIL_universe_by_quarter.csv`, `RETAIL_weights.csv`, `RETAIL_class_table.csv`
