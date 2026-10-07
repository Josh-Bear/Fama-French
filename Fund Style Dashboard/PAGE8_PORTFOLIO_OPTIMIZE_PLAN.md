# PAGE8_PORTFOLIO_OPTIMIZE_PLAN.md — หน้า 8: Portfolio Optimize

> สถานะ (อัปเดต 2026-09-29): **หน้า 8 ส่วนที่ 1-3 implement แล้ว** — สเปกปัจจุบัน = §14 + การแก้ใน §19-§21 · §3-§11 เป็นแผนเดิมก่อนเปลี่ยนมาใช้ grid enumeration (เก็บไว้เป็นประวัติ)
> ที่มา: ต่อยอดจาก "Future Plan" ที่กันที่ไว้ใน `docs/archive/PAGE6_STYLE_FACTOR_PLAN.md` §7 ("Σ = B·F·Bᵗ + D") — ตอนนี้เขียนละเอียดจริงจัง 2026-09-22
> Objective และวิธีรวม scope — 2 จุดที่คุณให้ผมเสนอในแผนนี้ (ยังไม่ confirm) — ทุกตัวเลขด้านล่าง **รันจริงกับข้อมูลจริงในเครื่องคุณแล้ว** ไม่ใช่ค่าประมาณ
> **อัปเดต 2026-09-22**: มีแนวทางเสริมแบบ score-based screening (ไม่พึ่ง risk model) กำลังสำรวจคู่กันอยู่ — ดู §12

---

## 0. สรุปสั้น

สร้างหน้าใหม่ที่ให้ผู้ใช้เลือกกองทุน (จากกอง E 313 กอง) มาประกอบเป็นพอร์ต แล้วคำนวณน้ำหนักที่ "ดี" ตาม risk model แบบ Barra-style (Σ = B·F·Bᵗ + D) ที่สร้างจาก **factor exposure ที่ fit ใหม่ร่วมกันทั้ง 28 ดัชนี (country+sector รวมเป็นโมเดลเดียว)** ไม่ใช่เอา coefficient จาก 4 scope เดิม (country/sector/style/macro) มาต่อกันตรงๆ — เหตุผลอยู่ใน §3

**จุดที่ต่างจากหน้า 1-7 ทุกหน้าเดิม**: หน้า 1-7 เป็นเครื่องมือ "อ่าน/จำแนก" กองทุนที่มีอยู่ ไม่แตะน้ำหนักพอร์ต ส่วนหน้า 8 เป็นเครื่องมือ "ตัดสินใจ" (ให้ตัวเลขน้ำหนักออกมา) — ความเสี่ยงต่อความผิดพลาดสูงกว่าหน้าอื่นมาก เพราะผลลัพธ์ผิดที่นี่มีโอกาสถูกเอาไปใช้จัดพอร์ตจริง ทุกจุดในแผนนี้จึงต้อง validate ด้วยข้อมูลจริงก่อนเขียนโค้ด (ไม่ใช่แค่ "ดูสมเหตุสมผล" เฉยๆ)

---

## 1. เป้าหมาย / ทำไมต้องมีหน้านี้

หน้า 1-7 บอกได้ว่ากองไหน "ไวต่ออะไร" แต่ไม่เคยตอบว่า **"ถ้าเอากองพวกนี้มารวมกันเป็นพอร์ต ควรใส่น้ำหนักเท่าไหร่ถึงจะกระจายความเสี่ยงได้ดี"** — หน้า 8 ปิดช่องว่างนี้โดยใช้ factor exposure ที่มีอยู่แล้ว (ไม่ต้องประเมิน correlation ระหว่างกองทุนตรงๆ จาก NAV ซึ่งข้อมูลกองส่วนใหญ่สั้น/ไม่สม่ำเสมอ — ใช้ factor model แทนซึ่ง robust กว่า) มาคำนวณ covariance matrix ของพอร์ตแล้ว optimize น้ำหนัก

---

## 2. Scope — เฉพาะกอง E 313 กอง (confirmed)

เหตุผลเดิมเหมือนหน้า 6/7: F/O ไม่มี style/macro ให้ใช้ประกอบ และ "การจัดพอร์ต" ในบริบทนี้หมายถึงพอร์ตหุ้นเป็นหลัก — กอง F/O (บอนด์/อื่นๆ) มีลักษณะความเสี่ยงต่างกันมาก เอามาปนใน risk model เดียวกับกองหุ้นโดยไม่มี fixed-income factor ที่เหมาะสม (duration, credit spread ฯลฯ) จะทำให้ D (idiosyncratic) ของกองพวกนั้นสูงผิดปกติ (เพราะ 28 factor ที่มีเป็นดัชนีหุ้นล้วน อธิบายกองบอนด์ไม่ได้ — ตรงกับที่หน้า 1/2 เจอแล้ว R²เฉลี่ยกอง F แค่ 0.15)

---

## 3. Risk model — หัวใจของแผนนี้

### 3.1 ทำไมรวม 4 scope (country+sector+style+macro) ตรงๆ ไม่ได้

ปัญหานี้เจอซ้ำมาแล้ว 2 รอบในโปรเจกต์นี้:
- หน้า 6: ต้องคุมตลาด 2 โลก (MSCI_ACWI + ACWI_ETF) ไม่งั้น LowVol_rel (ที่มี beta −0.49 ต่อตลาด) จะอุดส่วนต่างจนกองส่วนใหญ่ได้ป้าย High-Beta ปลอม
- หน้า 7: ต้องเฉลี่ย country-scope กับ sector-scope (ไม่ใช่รวม) เพราะทั้งสองเป็นคนละ regression ที่ต่างก็อ้างว่าอธิบาย 100% ของ return กองได้อยู่แล้ว รวมตรงๆ จะนับตลาดซ้ำ ~1.6 เท่า

ถ้าเอา `coefs.csv` (country 18 + sector 10, จาก **2 regression อิสระ**) + `style_coefs.csv` (4 ตัว, ยังมี market beta ตกค้าง −0.49) + `macro_loadings.csv` (implied ที่ **derive มาจาก country/sector coefficient อยู่แล้ว** ไม่ใช่ factor อิสระ) มาต่อกันเป็นเวกเตอร์เดียวยาว 18+10+4+7=39 ตัวสำหรับ B แล้วคำนวณ Σ=BFBᵗ จะนับ "การเคลื่อนไหวของตลาดโลก" ซ้ำ **อย่างน้อย 3 รอบ** (จาก country, จาก sector ที่แชร์ market factor เดียวกัน, และจาก macro ที่เป็น derived quantity) — Σ ที่ได้จะประเมิน portfolio variance สูงเกินจริงมาก โดยเฉพาะความเสี่ยง "ตลาดร่วง" ที่จะถูกนับซ้ำหนักที่สุด

### 3.2 วิธีที่เสนอ (แก้ปัญหา §3.1): **refit ร่วมกันเป็นโมเดลเดียว 28 factor**

แทนที่จะ reuse `coefs.csv`, ให้ fit ใหม่ต่อกองด้วย `match_exposure()` (ฟังก์ชันเดิมที่มีอยู่แล้ว ไม่ต้องเขียนใหม่) แต่ส่ง **28 คอลัมน์พร้อมกัน** (`pd.concat([country_18, sector_10], axis=1)`) เป็น aligned table เดียว แทนที่จะแยก fit country กับ sector คนละรอบ — นี่คือ true joint exposure ที่ ElasticNet เลือก sparse combination ที่ดีที่สุดจาก 28 ตัวเลย ไม่มีการนับซ้ำเพราะเป็น**การ fit ครั้งเดียว**

**ทดสอบจริงแล้ว (5 กองที่รู้ผลอยู่แล้วจากหน้า 1-3)**, เทียบ joint-28 R² กับ country_r2/sector_r2 เดิม:

| กอง | joint28 R² | country R² (เดิม) | sector R² (เดิม) | top-3 factor ที่ได้ |
|---|---|---|---|---|
| K-INDIA | **0.785** | 0.744 | 0.216 | MSCI_INDIA, MSCI_USA, MSCI_ACWI_MT |
| ABJO | **0.732** | 0.733 | 0.193 | MSCI_JAPAN, MSCI_TAIWAN, MSCI_ACWI_IN |
| ABEG | **0.516** | 0.488 | 0.317 | MSCI_WORLD_EX_US, MSCI_EUROPE, MSCI_INDIA |
| BCARE | **0.752** | 0.450 | 0.700 | MSCI_ACWI_HC, MSCI_ACWI_CS, MSCI_ACWI_CD |
| K-USA-A(A) | **0.464** | 0.322 | 0.372 | MSCI_USA, MSCI_ACWI_IT, MSCI_WORLD_EX_US |

**สรุปจากผลทดสอบ**: joint R² สูงกว่าหรือใกล้เคียงกับ max(country_r2, sector_r2) เสมอ (สมเหตุสมผล เพราะมี information มากกว่า) primary factor ที่ได้ยังตรงกับที่รู้จากหน้า 1-3 (K-INDIA→INDIA, ABJO→JAPAN, BCARE→Health Care) **ElasticNet ไม่พังแม้ดัชนีจะ collinear สูง** (ดู §3.3) — ยืนยันว่าวิธีนี้ใช้งานได้จริง ไม่ใช่แค่ทฤษฎี

**ผลกระทบที่ต้องรู้**: B ที่ได้จากวิธีนี้จะ**ไม่เท่ากับ** `country_primary`/`sector_primary`/`coefs.csv` ที่หน้า 1-3 ใช้ (เพราะเป็นคนละ fit) — หน้า 8 ต้องมี cache ของตัวเองแยกต่างหาก ไม่ reuse `coefs.csv` ตรงๆ (เหมือนที่หน้า 6/7 ก็แยก cache ของตัวเองอยู่แล้ว)

**style/macro จะใช้ยังไงในหน้านี้**: ไม่รวมเข้า Σ (กันนับซ้ำ) แต่ยังโชว์เป็น**ข้อมูลประกอบการตัดสินใจ** ได้ (เช่น หลังคำนวณน้ำหนักพอร์ตแล้ว แสดง weighted-average style tilt / weighted-average macro impact ของพอร์ตนั้น โดยดึงจาก `style_loadings`/`macro_loadings` cache ที่มีอยู่แล้ว — เป็น descriptive readout ไม่ใช่ input ของ optimizer) วิธีนี้ได้ประโยชน์จาก 4 scope ครบโดยไม่เสี่ยงนับซ้ำ

### 3.3 Factor covariance matrix (F) — ต้อง shrink ไม่ใช้ raw sample covariance

**ปัญหา**: 28 ดัชนี MSCI collinear กันรุนแรงมาก (ACWI/WORLD/EM ซ้อนกัน ตามที่ README บันทึกไว้แล้วเรื่อง condition number ของ correlation matrix) **ทดสอบจริงกับ daily return 28 ดัชนี (2021-01-04 → 2026-07-31, n=1,455 วัน):**

| covariance ที่ใช้ | condition number |
|---|---|
| raw sample covariance (annualized) | **665,809** |
| Ledoit-Wolf shrinkage (shrinkage intensity = **1.06%**) | **1,037** |

Shrinkage แค่ 1% ลด condition number ลง **~640 เท่า** — raw sample covariance เกือบ singular (eigenvalue เล็กสุด ≈ 5.7e-7 เทียบใหญ่สุด 0.38) ถ้าเอาไปเข้า optimizer ตรงๆ จะเกิด "error maximization problem" ที่รู้จักกันดีในวงการ (optimizer หาทางใช้ประโยชน์จาก near-linear-dependence ระหว่าง factor ทำให้ได้น้ำหนักพอร์ตที่ extreme/ไม่สมเหตุสมผล แม้ underlying กองทุนจะเป็น long-only ธรรมดา)

**ตัดสินใจ**: ใช้ `sklearn.covariance.LedoitWolf` (มีอยู่แล้วใน dependency เพราะ scikit-learn เป็น dependency หลักของโปรเจกต์นี้อยู่แล้ว ไม่ต้องเพิ่ม dependency ใหม่) fit บน 28-factor daily return แล้ว annualize (×252) เป็น F

### 3.4 Idiosyncratic risk (D)

D = diagonal matrix ของ residual variance ต่อกอง = `total_ann_var × (1 − joint28_R²)` — **ทดสอบจริงแล้ว**:

| กอง | total ann vol | joint28 R² | idiosyncratic vol |
|---|---|---|---|
| K-INDIA | 16.8% | 0.785 | 7.8% |
| BCARE | 14.9% | 0.752 | 7.4% |

ตัวเลขสมเหตุสมผล (idiosyncratic vol เหลืออยู่พอสมควรแต่ไม่เกิน total vol) — ยืนยันว่าคำนวณได้ตรงไปตรงมาจาก R² ที่มีอยู่แล้ว ไม่ต้องมีขั้นตอนซับซ้อนเพิ่ม

### 3.5 สูตรรวม

```
Σ_portfolio (N fund × N fund) = B · F · Bᵗ + D
  B = exposure matrix (N fund × 28 factor)     — joint refit ต่อกอง (§3.2)
  F = factor covariance (28 × 28)               — Ledoit-Wolf shrunk (§3.3)
  D = idiosyncratic variance (N fund diagonal)  — (1−R²)×total_var ต่อกอง (§3.4)

portfolio variance = wᵀ Σ_portfolio w   (w = น้ำหนักที่จะ optimize)
```

---

## 4. Objective function — เสนอ 3 ระดับ (คุณให้ผมเสนอ)

เหตุผลที่เสนอแบบ **phased** แทนที่จะฟันธงตัวเดียว: mean-variance ต้องพึ่ง expected return ซึ่งระบบนี้มีแค่ `ann_return` ที่ตัว README เองก็ document ไว้แล้วว่ามี bias จากสูตร 252/n_obs (คลาดเคลื่อนได้ถึงเท่าตัวสำหรับกองที่รายงาน NAV ห่าง) — เอาไปเข้า optimizer ตรงๆ จะได้น้ำหนักที่เอียงตามความคลาดเคลื่อนของสูตร ไม่ใช่ตามพื้นฐานกองจริง

**Phase 1 (แนะนำเป็นค่าเริ่มต้นของหน้า — ไม่ต้องพึ่ง expected return เลย):**
- **Minimum-variance**: `min wᵀΣw` s.t. `Σw=1, w≥0` (long-only, full-invested) — ปลอดภัยสุด ใช้ได้ทันทีเพราะพึ่งแค่ Σ ที่ validate แล้วใน §3
- **Risk parity** (toggle เลือกได้): แต่ละกอง contribute ความเสี่ยงเท่ากัน (`w_i × (Σw)_i` เท่ากันทุก i) — เหมาะกับคนที่อยากกระจายความเสี่ยงมากกว่าจะ minimize ความเสี่ยงรวม

**Phase 2 (ถ้าต้องการ — ต้องมี disclaimer ชัดเจนในหน้าเว็บ):**
- **Mean-variance**: เพิ่ม expected return เข้ามา (`max μᵀw − λ·wᵀΣw`) — ใช้ `ann_return` จาก results.csv ได้ แต่ต้องโชว์คำเตือนเรื่อง annualization bias (ข้อ 5 ใน Known Limitations ของ README) ชัดเจนข้างๆ ตัวเลข ไม่ปล่อยให้ผู้ใช้เข้าใจว่าเป็นค่าพยากรณ์แม่นยำ

ข้อเสนอ: **เริ่มจาก Phase 1 ก่อน** (min-variance เป็น default, risk-parity เป็นตัวเลือก) แล้วค่อยพิจารณา mean-variance เป็นงานถัดไปถ้าต้องการจริง — ตรงกับหลัก "ไม่ทำให้ซับซ้อนขึ้นโดยไม่จำเป็น" ของโปรเจกต์นี้ และไม่ต้องแก้ปัญหาความแม่นยำของ expected return ให้เสร็จก่อนถึงจะเริ่มหน้านี้ได้

---

## 5. Optimizer — ใช้ `scipy.optimize` (ไม่ต้องเพิ่ม dependency ใหม่)

**ทดสอบแล้ว**: `scipy` (1.15.3) มีอยู่ในเครื่องคุณแล้ว (เป็น dependency ของ scikit-learn ที่ใช้อยู่ทั้งระบบ) — ลอง `cvxpy` แล้วพบว่า**ยังไม่ได้ติดตั้ง** เสนอ**ไม่เพิ่ม** cvxpy เป็น dependency ใหม่ เพราะ `scipy.optimize.minimize(method="SLSQP")` แก้ quadratic program ขนาดนี้ได้สบาย (N ≤ 313 ตัวแปร, constraint เชิงเส้นล้วน) — ยึดหลัก "ไม่เพิ่ม dependency โดยไม่จำเป็น" เหมือนที่หน้า 7 ตัดสินใจ reuse `nested_r2` แทนเขียน module ใหม่

Constraint ที่เสนอเป็นค่าเริ่มต้น (ปรับได้ผ่าน UI):
- `Σw = 1` (full-invested)
- `w ≥ 0` (long-only — เหมาะกับบริบทกองทุนไทยที่ short ไม่ได้อยู่แล้ว)
- `w_i ≤ max_weight` (เพดานน้ำหนักต่อกอง กันกระจุกตัวกองเดียว — เสนอ default 20%, ปรับได้)

---

## 6. โครงสร้างโค้ดที่ต้องเพิ่ม

- **`data_access.py`** — เพิ่ม:
  - `build_portfolio_risk_model()`: refit joint-28 ต่อกอง E ทั้ง 313 กอง (reuse `matching.build_fund_returns`/`match_exposure` — ไม่แก้ฟังก์ชันเดิม) → เขียน `cache/portfolio_exposure.csv` (B) + `cache/portfolio_factor_cov.csv` (F, Ledoit-Wolf) + คอลัมน์ idiosyncratic variance ใน `cache/portfolio_exposure.csv` เดียวกัน (D)
  - `optimize_portfolio(fund_codes, objective, constraints)`: ฟังก์ชัน UI-layer เรียก scipy ตอนกดปุ่ม (ไม่ต้อง cache ผล เพราะขึ้นกับกองที่ผู้ใช้เลือกสดๆ)
- **`analysis/portfolio.py`** (ใหม่ — งานนี้เป็น logic ใหม่จริง ไม่ reuse ของเดิมได้เหมือนหน้า 6/7 เพราะเป็นคณิตศาสตร์คนละแบบ): `portfolio_variance(w, Sigma)`, `min_variance_weights(Sigma, constraints)`, `risk_parity_weights(Sigma, constraints)`, `risk_contribution(w, Sigma)` (แยกความเสี่ยงต่อกองสำหรับกราฟ breakdown)
- **`pages/8_💼_Portfolio_Optimize.py`** (ใหม่)
- **`config.py`** — เพิ่ม `PORTFOLIO_POLICY="E"`, `PORTFOLIO_MAX_WEIGHT=0.20`, ฯลฯ

---

## 7. Cache design

| ไฟล์ | schema | ขนาดโดยประมาณ |
|---|---|---|
| `cache/portfolio_exposure.csv` | `FundCode, index, beta` (long-form, 28 factor × 313 กอง) + `FundCode, idio_var, r2, n` (อีกไฟล์หรือ merge) | ~8,764 แถว |
| `cache/portfolio_factor_cov.csv` | 28×28 matrix (wide-form, index=factor, columns=factor) | 28×28 |

แยกจาก `coefs.csv`/`style_coefs.csv`/`macro_loadings.csv` เดิมทั้งหมด (ตาม pattern ของหน้า 6/7 ที่แยก cache scope ใหม่เสมอ ไม่ยัดเข้าไฟล์เดิม)

---

## 8. UI หน้า 8 (โครงคร่าวๆ)

1. **เลือกกองทุน** — multiselect จากกอง E 313 กอง (ค้นหาได้) หรือเลือก preset (เช่น "primary = INDIA ทุกกอง" ต่อยอดจากหน้า 1)
2. **ตั้งค่า** — objective (min-variance / risk-parity), max weight ต่อกอง, long-only (fix ไว้ก่อน ไม่ให้ short)
3. **ผลลัพธ์**:
   - ตารางน้ำหนักที่ optimize ได้ต่อกอง
   - Metric: portfolio expected vol (จาก Σ), diversification ratio
   - Bar chart risk contribution ต่อกอง (ใครมีส่วนความเสี่ยงมากสุดในพอร์ต)
   - (descriptive, ไม่ใช่ input) weighted-average country/sector/style/macro exposure ของพอร์ตที่ได้ — ดึงจาก cache เดิมหน้า 1/2/6/7
   - เทียบกับ equal-weight พอร์ตเดียวกัน (baseline ให้เห็นว่า optimize ช่วยลด vol ได้กี่ %)
4. **Caption เตือน**: Σ มาจาก factor model ไม่ใช่ observed fund covariance ตรงๆ (fund ที่ idiosyncratic risk สูงจะถูก under-diversify ใน model นี้ถ้าไม่ correlate กันจริงในทางที่ model จับไม่ได้) · ถ้าเปิด mean-variance (Phase 2) ต้องมี caption เรื่อง expected return bias

---

## 9. Checklist ก่อน implement จริง

- [ ] Confirm objective เริ่มต้น (min-variance) และว่าจะทำ risk-parity คู่กันเลยหรือทำทีหลัง
- [ ] Confirm ว่า mean-variance (Phase 2) จะทำในรอบนี้เลยหรือแยกเป็นงานถัดไป
- [ ] Confirm max_weight default (20%) และจะให้ปรับได้ผ่าน UI ไหม
- [ ] รัน `build_portfolio_risk_model()` กับกอง E ทั้ง 313 กองจริง (ไม่ใช่แค่ 5 กองตัวอย่างที่ validate ในแผนนี้) เช็คเวลารัน + ไม่มีกองไหน R²/idio_var ผิดปกติ (เช่น idio_var ติดลบจาก floating point, ต้อง clip ที่ 0)
- [ ] เช็คว่า optimizer scipy convergence ผ่านทุกกรณี (เผื่อ user เลือกกองน้อยมาก เช่น 2 กอง หรือกองที่ idio_var=0 พอดี)
- [ ] รัน `pytest -q` ยืนยันไม่กระทบหน้า 1-7 เดิม

---

## 10. Decision log

1. Scope เฉพาะกอง E 313 กอง (confirmed โดยคุณ) — เหตุผล: F/O ไม่มี fixed-income factor ให้ใช้ อธิบายไม่ได้
2. **ไม่รวม 4 scope ตรงๆ** — เสี่ยงนับตลาดซ้ำ ≥3 รอบ (validate เชิงเหตุผลจากบทเรียนหน้า 6/7)
3. **Risk model ใช้ joint-28-factor refit** (fit ใหม่ร่วมกัน ไม่ reuse coefs.csv เดิม) — validate แล้วด้วยข้อมูลจริง 5 กอง ได้ R² สมเหตุสมผล + primary ตรงกับที่รู้จากหน้า 1-3
4. **Factor covariance ต้อง shrink ด้วย Ledoit-Wolf** — validate แล้ว raw condition number 665,809 → shrunk 1,037 (ลด ~640 เท่า)
5. style/macro **ไม่รวมเข้า Σ** แต่โชว์เป็น descriptive readout ของพอร์ตที่ optimize ได้
6. Objective **เสนอ phased**: Phase 1 = min-variance + risk-parity (ไม่พึ่ง expected return) · Phase 2 = mean-variance (ถ้าต้องการ ต้องมี disclaimer) — **ยังไม่ confirm รอคุณเลือก**
7. Optimizer ใช้ `scipy.optimize` ไม่เพิ่ม dependency ใหม่ (cvxpy ยังไม่ติดตั้ง เช็คแล้ว)
8. Cache แยกไฟล์ใหม่ทั้งหมด (`portfolio_exposure.csv`, `portfolio_factor_cov.csv`) ไม่แตะ cache เดิม

---

## 11. Open items / ความเสี่ยงที่ต้องรู้ไว้ก่อนเริ่ม

1. **Σ จาก factor model ไม่ใช่ observed fund correlation จริง** — ถ้ากองสองกองมี correlation จริงที่ไม่ได้มาจาก factor ร่วมกัน (เช่น กองเดียวกันบริหารโดยทีมเดียวกัน ถือหุ้นคล้ายกันโดยบังเอิญ) model นี้จะไม่จับได้ — เป็นข้อจำกัดมาตรฐานของ factor-based risk model ทุกตัว ไม่ใช่บั๊ก แต่ต้องบอกผู้ใช้ตรงๆ
2. **313 กอง มี R² กระจายกว้าง** (ตั้งแต่ ~0.05 บางกองถ้ามี ถึง ~0.8+) — กองที่ R² ต่ำมากจะมี D (idiosyncratic) ใหญ่มาก ซึ่งถูกต้องตามทฤษฎี แต่ optimizer อาจ under-weight กองพวกนี้หนักเพราะมองว่า "เสี่ยงเกินจะอธิบายได้" ทั้งที่จริงอาจแค่ fit ไม่เข้ากับ 28-factor set (เช่นกองที่เอียง sector เฉพาะทางมากๆ) — ควรโชว์ R² ควบคู่กับผลลัพธ์เสมอ (เหมือนที่หน้า 1-7 ทำมาตลอด)
3. **ยังไม่ทำ**: mean-variance เต็มรูปแบบ, short-selling/leverage, sector/country exposure cap ระดับพอร์ต (เช่น "ห้ามพอร์ตมี China exposure รวมเกิน 30%"), backtest ของน้ำหนักที่ optimize ได้ย้อนหลัง — ทั้งหมดนี้เป็นงานต่อยอดที่ทำได้หลัง Phase 1 เสร็จ

---

## 12. แนวทางเสริม: Score-based screening (country+sector) — สำรวจ 2026-09-22

> สถานะ: **สำรวจ/validate ด้วยข้อมูลจริงแล้ว ยังไม่ confirm ว่าจะใช้แทนหรือใช้คู่กับ §3-§8** — คุณบอกไว้ว่าอยากลอง 3 แบบ: country+sector (ส่วนนี้) · style · macro (2 อันหลังยังไม่ได้เริ่มออกแบบ)
> แนวคิดต้นตอ: มองจาก zone (quadrant) ของ index บนหน้า 5 (Filtered Scatter) แทนที่จะเริ่มจาก risk model — เป็นมุมมองแบบ "top-down screen" คนละมุมกับ §3 ที่เป็น "bottom-up risk minimize"

### 12.1 สูตร (confirmed ร่วมกันแล้ว)

> ⚠️ **ล้าสมัยแล้ว (อัปเดต 2026-09-22)** — สูตรนี้ใช้ `return_21d` และยังไม่มี R² product / secondary-fallback selection ตามที่ confirm ภายหลัง สูตร+notation ปัจจุบันจริงอยู่ที่ **§12.8** (formula/notation) และ **§12.9-§12.10** (fund score + diversified selection algorithm) — เก็บส่วนนี้ไว้เป็นประวัติการพัฒนาเท่านั้น อย่า implement ตามนี้ตรงๆ

```
zone_score(index)  = percentile(return_21d) × [1 − percentile(vol_forecast)]      ← percentile คำนวณแยกภายใน scope ตัวเอง (18 country / 10 sector)
                      (คูณ ไม่บวก — ต้องการ AND logic: ต้องดีทั้ง return และ vol พร้อมกัน ถึงจะเป็น "โซนฟ้า" จริง)

scope_score(กอง)   = zone_score(primary_index) × R²_scope
                    + [|secondary_coef| / |primary_coef|] × zone_score(secondary_index) × R²_scope
                      (ใช้ |coef| เพราะ country/sector ไม่สนเครื่องหมาย ต่างจาก style — ดู docs/pages/6-style-match.md)

fund_score         = country_scope_score + sector_scope_score
```

ข้อมูลที่ใช้: `data_access.get_index_snapshot()` (return_21d + GARCH vol_forecast ต่อ index, เหมือนหน้า 5), `data_access.get_results()` (primary/primary_coef/R² ต่อกอง), `data_access.get_coefs()` (secondary_coef — results.csv ไม่มีคอลัมน์นี้ ต้องดึงจาก coefs.csv ที่ `is_secondary == True`)

### 12.2 ข้อมูล historical vs predicted (สำคัญ — ต้องรู้ไว้)

| ตัวแปร | แหล่ง | ชนิด |
|---|---|---|
| `return_21d` | ราคาดิบของ index เทียบ 21 observation ที่แล้ว | **Historical/Realized** (มองย้อนหลัง) |
| `vol_forecast` | GARCH(1,1) Student-t จากหน้า 4 | **Predicted** (มองไปข้างหน้า 21 วัน) |

สองตัวคนละทิศเวลากัน — ระบบไม่มี expected-return model ให้ใช้ (เหตุผลเดียวกับที่ §4 เลี่ยง mean-variance ใน Phase 1) เพราะงั้น `return_21d` ที่ใช้จริงๆ คือสมมติฐาน **momentum ระยะสั้น** (index ที่เพิ่งวิ่งดี 21 วันจะวิ่งต่อ) ไม่ใช่การพยากรณ์ที่ validate แล้วแบบฝั่ง vol

### 12.3 Validate zone_score กับตัวอย่างจริงที่คุณยกมา

รันจริงกับ `get_index_snapshot()` ปัจจุบัน (2026-09-22) — **ASEAN ได้ zone_score สูงสุดในกลุ่ม country (0.892/18 ตัว)** และ **FN (Financials) ได้สูงสุดในกลุ่ม sector (0.720/10 ตัว)** ตรงกับตัวอย่างที่คุณยกมาเป๊ะ ยืนยันว่าสูตรจับสัญญาณที่ต้องการได้ถูกต้อง

| country top 3 | zone_score | sector top 3 | zone_score |
|---|---|---|---|
| MSCI_ASEAN | 0.892 | MSCI_ACWI_FN | 0.720 |
| MSCI_WORLD_EX_US | 0.602 | MSCI_ACWI_CS | 0.490 |
| MSCI_WORLD | 0.494 | MSCI_ACWI_EN | 0.300 |

### 12.4 Top 5 กอง E (313 กอง) ตามสูตรนี้

> ⚠️ **ล้าสมัยแล้ว (อัปเดต 2026-09-22)** — ตัวเลขนี้คำนวณจากสูตร §12.1 เดิม (return_21d, ไม่มี VIF-cleaning, ไม่มี diversification filter) ตัวเลข top-5 ปัจจุบันจริงอยู่ที่ **§12.10** (diversified selection ด้วย cleaned country index)

| FundCode | score | country primary/secondary | sector primary/secondary |
|---|---|---|---|
| LHUSFIN-D | 1.108 | Europe / World-ex-US | **FN** / CD |
| TUSFIN-A | 1.093 | World-ex-US / Europe | **FN** / CS |
| LHUSFIN-A | 1.013 | ACWI-ex-US / Europe | **FN** / CS |
| K-EUX | 0.847 | Europe / World-ex-US | MT / **FN** |
| TISCOEU-A | 0.812 | Europe / World-ex-US | MT / **FN** |

Distribution คะแนนกอง E ทั้งหมด: mean 0.367 · median 0.340 · min 0.027 · max 1.108

### 12.5 ⚠️ ปัญหาที่เจอ — pure score ranking ไม่กระจายความเสี่ยงจริง (ต้องแก้ก่อนใช้จริง)

Correlation ของ daily return จริง (NAV จริง ไม่ใช่ประมาณ) ระหว่าง top-5 ข้างต้น:

|  | K-EUX | LHUSFIN-A | LHUSFIN-D | TISCOEU-A | TUSFIN-A |
|---|---|---|---|---|---|
| K-EUX | 1.00 | 0.49 | 0.49 | **0.98** | 0.52 |
| LHUSFIN-A | 0.49 | 1.00 | **0.97** | 0.49 | 0.95 |
| LHUSFIN-D | 0.49 | 0.97 | 1.00 | 0.49 | 0.95 |
| TISCOEU-A | 0.98 | 0.49 | 0.49 | 1.00 | 0.52 |
| TUSFIN-A | 0.52 | 0.95 | 0.95 | 0.52 | 1.00 |

- **LHUSFIN-A / LHUSFIN-D correlation 0.97** — คนละ share class ของกองเดียวกัน (LH US Financial Fund) พอร์ตข้างในเหมือนกัน นับเป็น 2 ตำแหน่งคือหลอกตัวเองว่ากระจายความเสี่ยง
- **K-EUX / TISCOEU-A correlation 0.98** — กอง Europe index tracker ทั้งคู่ แทบเป็น proxy กัน
- รวมแล้ว top-5 นี้จริงๆ คือ **2 bet หลัก** (US Financials ~0.95 correlated ×3 กอง + Europe equity ~0.98 correlated ×2 กอง) ไม่ใช่ 5 ตำแหน่งที่กระจายตัว — เพราะ score ให้คะแนนกองแยกกันทีละกอง ไม่รู้ว่ากองไหนซ้ำกัน (ไม่เห็น correlation ระหว่างกัน)

**ทางแก้ที่เสนอไว้ (ยังไม่ confirm):**
- (A) ใส่ diversification filter ก่อนเลือก top-N เช่น จำกัด correlation หรือ 1 กอง/1 benchmark หลัก — เร็ว เข้าใจง่าย แต่ต้องเดา threshold เอง
- (B) เอา top-N (เช่น 15-20 จาก score) ส่งต่อให้ optimizer ใน §3-§8 (Σ=BFBᵗ+D) จัดน้ำหนัก — แก้ที่ root cause เพราะ optimizer เห็น correlation จริงอยู่แล้วในตัว ไม่ต้องตั้งกฎมือ **← แนวทางที่เอนเอียงไปทางนี้มากกว่า เพราะงานสร้าง optimizer ทำ+validate เสร็จแล้วใน §3 รอใช้อยู่**

### 12.6 สถานะและงานที่เหลือ

- [x] สูตร zone_score / scope_score / fund_score — confirm ร่วมกันแล้ว
- [x] Validate ด้วยข้อมูลจริง 313 กอง — เจอ ASEAN/FN ตรงกับตัวอย่าง, เจอปัญหา concentration ชัดเจน
- [ ] **ยังไม่ confirm**: จะแก้ปัญหา concentration ด้วย (A) diversification filter หรือ (B) ส่งต่อ optimizer §3
- [ ] **ยังไม่เริ่ม**: version สำหรับ style scope และ macro scope (คุณบอกไว้ว่าอยากลองทั้ง 3 แบบ)
- [ ] **ยังไม่เริ่ม**: rebalance ทุก 3 เดือน — คุยแนวคิดคร่าวๆ แล้ว (reuse สถาปัตยกรรม walk-forward expanding-window เดียวกับ `analysis/vol_forecast.py::walk_forward_backtest()` ที่มีอยู่แล้วสำหรับหน้า 4) แต่ยังไม่ได้ตัดสินใจว่าจะทำโหมด (A) ใช้งานจริง/เอกสารขั้นตอน หรือโหมด (B) backtest ย้อนหลังจริงจัง (ข้อมูลพอทำได้ ~18-20 รอบไตรมาสหลังหัก warm-up 1 ปี แต่ยังถือว่า sample size ไม่เยอะ) — รอ confirm ก่อนเริ่มออกแบบ/เขียนโค้ด
- ยังไม่มีโค้ดจริงถูกเขียนสำหรับส่วนนี้เลย (แค่ script สำรวจชั่วคราวที่รันแล้วทิ้ง) — รอ confirm แนวทาง §12.5 ก่อนค่อยลง `analysis/portfolio.py`/`pages/8_...py` จริง
  ⚠️ ล้าสมัย — implement แล้ว (§14, §18-§22)

### 12.7 อัปเดต 2026-09-22 (ต่อ): confirm return window = 12m (252d), target = 63d

หลัง test autocorrelation หลายหน้าต่าง (§12.5 เดิม + เพิ่ม 252d ดิบ และ 12m-1m แบบ skip เดือนล่าสุดของ Jegadeesh-Titman) คุณ confirm เลือก:

- **Target ที่สนใจ = future return 63 วัน** (~1 ไตรมาส ตรงกับแผน rebalance ทุก 3 เดือน)
- **Return signal ที่ใช้ = 252d (12m) แบบดิบ** (ไม่ skip เดือนล่าสุด) — เลือก 12m แทนที่จะไล่ตาม 126d ที่ backtest ได้ t-stat สูงสุด (3.90) เพราะ 12m เป็นหน้าต่างมาตรฐานที่ใช้กันทั่วไปในวรรณกรรม (Carhart/Fama-French momentum) ลดความเสี่ยง overfit กับ sample เดียวที่มีอยู่ — ที่ t-stat ของ 12m ก็ยังมีนัยสำคัญดี (+2.63 สำหรับ target 63d)
- **vol_forecast ยังคงเดิม** (GARCH 21 วันข้างหน้า ไม่แตะ — ตามทางเลือก (A) ที่เสนอไว้ ไม่ขยาย horizon ของ GARCH ตอนนี้)

```
zone_score(index) = percentile(return_252d) × [1 − percentile(vol_forecast_21d)]   ← เปลี่ยนจาก return_21d เดิม
                    ⚠️ อัปเดต 2026-09-29 (§12.13): return_252d เปลี่ยนเป็นแบบ **ข้าม 21 วันล่าสุด** (t−252 → t−21)
```

**ผลที่เปลี่ยนไป:**
- Country zone_score นำโดย MSCI_ACWI_EX_US (0.481) และ MSCI_WORLD_EX_US (0.463) แทน ASEAN (ASEAN ตกไปอยู่กลางตาราง 0.210 เพราะ 12m return แค่ 15.2% เทียบกับกลุ่มนำที่ ~20-28%)
- Sector zone_score ยังนำโดย FN (Financials, 0.56) เหมือนเดิม — สัญญาณ FN แข็งแรงข้ามหน้าต่างเวลา
- **Top 10 กอง E เปลี่ยนไป**: LHGREEN-D (LH Green Technology, 0.902) · PRINCIPAL GEF-A (Principal Global Equity, 0.873) · DAOL-AQUA (DAOL Global Water, 0.866) · LHUSFIN-A (0.828) · LHUSFIN-D (0.814) · EHD (Euro High Dividend, 0.807) · TUSFIN-A (0.807) · KKP GIMPACT-H (0.798) · K-EUX (0.784) · LHGREEN-A (0.770)

**⚠️ ปัญหา concentration ยังไม่หายไป — ยังต้องแก้ตาม §12.5**

เช็ค correlation จริงของ top-5 ใหม่ (LHGREEN-D, PRINCIPAL GEF-A, DAOL-AQUA, LHUSFIN-A, LHUSFIN-D):

|  | DAOL-AQUA | LHGREEN-D | LHUSFIN-A | LHUSFIN-D | PRINCIPAL GEF-A |
|---|---|---|---|---|---|
| DAOL-AQUA | 1.00 | 0.88 | 0.73 | 0.73 | 0.82 |
| LHGREEN-D | 0.88 | 1.00 | 0.72 | 0.72 | 0.83 |
| LHUSFIN-A | 0.73 | 0.72 | **1.00** | **1.00** | 0.75 |
| LHUSFIN-D | 0.73 | 0.72 | **1.00** | **1.00** | 0.75 |
| PRINCIPAL GEF-A | 0.82 | 0.83 | 0.75 | 0.75 | 1.00 |

- **LHUSFIN-A / LHUSFIN-D correlation = 1.00 พอดี** (เดิมทดสอบกับ return_21d ได้ 0.97 — ตอนนี้ confirm ชัดว่าคนละ share class ของกองเดียวกันจริงๆ ปัญหานี้**ไม่เกี่ยวกับว่าจะใช้ window ไหน** เป็นปัญหาระดับ fund taxonomy ต้อง dedup แยกต่างหาก ไม่ว่าจะเลือก return window แบบไหนก็เจอปัญหานี้เหมือนเดิม)
- ที่เหลือ correlation กันเอง 0.72-0.88 (สูงกว่ารอบก่อนที่เจอ 0.49-0.52 ระหว่าง 2 cluster) เพราะ top-10 ใหม่ทุกกองมี country primary อยู่ในตระกูล global/world-ex-US คล้ายกันหมด (ตรงข้ามกับรอบก่อนที่มี Europe cluster กับ US Financial cluster แยกกันชัดเจน) — market beta ร่วมกันสูงกว่า

สรุป: เปลี่ยน window ช่วยให้ theme หลากหลายขึ้นเล็กน้อย (Green Tech, Global Equity, Global Water แทนที่จะเป็น US Financial ล้วน) แต่**ไม่ได้แก้ปัญหา concentration/duplicate ที่ root cause** — ยังต้องตัดสินใจ (A) diversification filter หรือ (B) ส่งต่อ Σ optimizer ตามที่คุยไว้ใน §12.5 อยู่ดี

### 12.8 อัปเดต 2026-09-22 (ต่อ): แก้ notation กำกวม + percentile rescale (1,99) + sector legend

**แก้ notation ที่กำกวม**: สูตรเดิมเขียน `fore_vol(0,1)` โดยไม่บอกว่ากลับด้านแล้วหรือยัง — ถ้าอ่านเป็น percentile ดิบของ vol_forecast ใกล้ 1 จะหมายถึง vol สูง = **แย่** ซึ่งสวนทางกับ `return_pct(0,1)` ที่ใกล้ 1 = ดี ของจริงในโค้ดกลับด้านแล้วเสมอ (`1 − percentile(vol_forecast)`) แค่ชื่อเขียนไม่ชัด — เปลี่ยนชื่อเป็น `vol_pct_good` ทุกจุดตั้งแต่นี้ไปกันงง:

```
return_pct(0,1)   = percentile(return_252d **ข้าม 21 วันล่าสุด**) ต่อ scope (18 country / 10 sector แยกกัน) → ใกล้ 1 = ดี  [§12.13]
vol_pct_good(0,1) = 1 − percentile(vol_forecast_21d) ต่อ scope                          → ใกล้ 1 = นิ่ง/ดี (**ไม่ใช่** raw percentile ของ vol!)
```

**Percentile rescale (0,1) → (1,99)**: ปัญหาเดิม percentile rank ที่ extreme (index อันดับสุดท้าย/แรกสุดของ scope) ชนขอบ 0/1 พอดี ทำให้ทั้งแถว/คอลัมน์ในตาราง matrix กลายเป็น 0.00 หมด (เจอกับ KOREA และ IT) แก้ด้วย linear rescale (monotonic, ไม่กระทบ ranking):

```
to_1_99(raw_pct) = 0.01 + 0.98 × raw_pct
```

**สูตรสุดท้าย (ใช้ตั้งแต่นี้เป็นต้นไป)**:

```
country_score(i) = return_pct(i) × vol_pct_good(i)          ← ภายใน scope country (18 หรือ 11 ตัว แล้วแต่ config §12.10)
sector_score(j)  = return_pct(j) × vol_pct_good(j)           ← ภายใน scope sector (10 ตัวเสมอ)
country_sector_score(i,j) = country_score(i) × sector_score(j) × 100     ∈ (0, ~96.06] ในทางทฤษฎี (แต่ละ percentile ∈ [0.01,0.99] ไม่ใช่ [0,1] เพราะ rescale — คูณ 4 ตัวรวมกันแล้วเพดานจริงต่ำกว่า 100) ในทางปฏิบัติสังเกตได้ต่ำกว่านี้มาก (สูงสุดที่เจอจริงในข้อมูล ~26, ดู §12.8 ตารางตัวอย่าง)
```

**Sector abbreviation legend** (จาก `docs/pages/2-sector-match.md`, GICS 10/11 sector มาตรฐาน — ไม่มี Real Estate ในชุด MSCI ACWI sector index ที่ใช้):

| ย่อ | ชื่อเต็ม |
|---|---|
| CD | Consumer Discretionary |
| CS | Consumer Staples |
| EN | Energy |
| FN | Financials |
| HC | Health Care |
| IN | Industrials |
| IT | Information Technology |
| MT | Materials |
| TC | Communication Services (โค้ดเก่าก่อน GICS เปลี่ยนชื่อจาก "Telecommunication Services" ปี 2018) |
| UT | Utilities |

---

### 12.9 Greedy diversified fund selection (confirmed 2026-09-22)

เป้าหมาย: เลือก top-N กองที่ไม่ซ้ำ country/sector กัน (คนละ "การเดิมพัน" กัน) แทนที่จะ rank คะแนนดิบอย่างเดียว (ซึ่งเจอปัญหา concentration ตาม §12.5/§12.7)

**Fund score**:

```
R²(กอง) = country_r2 × sector_r2                                          ← คูณกันทั้งสอง scope (country_sector_score เป็น cross term ของทั้งคู่)
score(กอง) = R²(กอง) × country_sector_score(country_primary, sector_primary)   ← ใช้ primary pair คำนวณ "คะแนนหลัก" เสมอ
```

**Greedy selection algorithm** (ไล่จากคะแนนสูงสุด, ทำจนครบ N):

```
used_countries = {}, used_sectors = {}
สำหรับแต่ละกอง (เรียงคะแนนมาก→น้อย):
  ถ้า country_primary ∉ used_countries และ sector_primary ∉ used_sectors:
      เลือกกองนี้ → mark country_primary, sector_primary เป็น used  (ใช้ "primary" pair)
  ไม่งั้น ถ้า country_secondary ∉ used_countries และ sector_secondary ∉ used_sectors:
      เลือกกองนี้ → mark country_secondary, sector_secondary เป็น used  (ใช้ "secondary" pair — ช่องสำรอง)
  ไม่งั้น: ข้าม (ตัดสิทธิ์ — ต้องใหม่ทั้ง country และ sector พร้อมกันถึงจะเลือกได้)
```

**⚠️ ข้อสังเกตสำคัญที่เจอ**: กองที่ถูกเลือกผ่านทาง "secondary" (เพราะ primary ชนกับกองที่เลือกไปแล้ว) บางกอง score_secondary จริงอ่อนกว่า score_primary ที่ใช้จัดอันดับมาก (เช่น KT-MFE-A ตัวอย่างเดิมก่อน VIF-clean: score_primary=8.73 → score_secondary=0.02) เพราะกองถูกจัดอันดับด้วยคะแนนของ pair ที่ใช้จริงไม่ได้ ไม่ใช่คะแนนของ pair ที่เอามาใช้จริง

**เช็คซ้ำ (2026-09-22) หลัง VIF-cleaning (§12.10) — ปัญหานี้ยังอยู่ ไม่หายไปกับการแก้ sign bug** (คนละสาเหตุกัน): กองที่ถูกเลือกผ่าน secondary ในชุด top-5 ใหม่ (§12.10) บางกอง ratio score_secondary/score_primary ต่ำมาก —

| FundCode | score_primary | score_secondary | ratio |
|---|---|---|---|
| TUSFIN-A | 5.24 | 1.53 | 0.29 |
| TISCOEU-A | 4.05 | 3.57 | 0.88 |
| ONE-EUROEQ | 3.93 | 0.13 | 0.03 |
| ONE-APACESG | 2.44 | 0.01 | 0.00 |

**Resolution (confirmed 2026-09-22, ขอบเขตแคบ — ไม่เปลี่ยน ranking/selection order)**: ยังใช้ score_primary จัดอันดับ/คัดเลือกเหมือนเดิม (ไม่เปลี่ยน algorithm §12.9 ด้านบน) แต่ **หน้า UI (§12.11 ส่วนที่ 2) ต้องโชว์คอลัมน์ score_secondary ควบคู่กับ score เสมอ** เพื่อความโปร่งใส ให้ผู้ใช้เห็นและกรองเองได้ว่ากองไหน secondary อ่อนเกินไปจนไม่ควรเอาเข้าพอร์ตจริง — ยังไม่ทำ auto-filter ด้วย threshold (เก็บเป็น future work ถ้าต้องการ)
> ⚠️ **ถูกแทนที่โดย §12.12 (band filter) + §20 (score ≥ 0.7 ของคู่ที่ใช้จริง)** — ตอนนี้กรองอัตโนมัติแล้ว ไม่ต้องให้ผู้ใช้กรองเอง

---

### 12.10 ⚠️ พบบั๊ก: primary/secondary ไม่สนเครื่องหมาย coef → แก้ด้วย VIF-cleaning (confirmed 2026-09-22)

**บั๊กที่พบ**: `analysis/matching.py::match_exposure()` นิยาม primary/secondary จาก **|coefficient| อย่างเดียว ไม่สนเครื่องหมายบวกลบ** (ตั้งใจไว้ตั้งแต่แรกสำหรับ display ทั่วไป) แต่สูตร `country_sector_score` ใน §12.9 สมมติว่ากองเคลื่อนไหว**ทิศเดียวกับ** index ที่จับคู่ไว้เสมอ (coef บวก) — ถ้า secondary coef ติดลบจริง การเอา country_sector_score (ตีความว่า "โซนดี") ไปคูณเป็นคะแนนบวกให้กองจะผิดทิศทาง (โซนดีควรทำนายว่ากองแย่ลง ไม่ใช่ดีขึ้น)

**ความรุนแรง (313 กอง E)**:

| | coef บวก | coef ลบ |
|---|---|---|
| primary (country/sector) | 309/309 | 4/4 (~1%) |
| **secondary (country)** | 236 | **77 (~25%)** |
| **secondary (sector)** | 257 | **56 (~18%)** |

primary แทบไม่มีปัญหา แต่ secondary (ที่ใช้เป็น "ช่องสำรอง" ใน §12.9 พอดี) ติดลบถึง ~1 ใน 4 ของกองทั้งหมด

**Root cause**: multicollinearity ระหว่าง 18 country index (เช่น WORLD_EX_US กับ EUROPE correlate กันเอง 0.93) ทำให้ ElasticNet "แบ่ง" น้ำหนักเป็นบวกแรง/ลบแรงทั้งที่จริงทั้งคู่เคลื่อนไปทางเดียวกัน (simple correlation ของกองกับ EUROPE ตรงๆ ยังเป็นบวกเสมอในเคสที่เช็ค) — **เรื่องนี้รู้และรับไว้แล้วตั้งแต่ต้นทาง** ดู `docs/archive/MSCI_DASHBOARD_PLAN.md` บรรทัด 42 (2026-09-01): ทดสอบ prune 18→11 ตัว ได้ condition number 726→6 แต่**ตัดสินใจเก็บครบ 18** เพื่อความละเอียดระดับประเทศ พร้อมยอมรับไว้ตรงๆ ว่า "primary อาจเป็น coefficient ค่าลบได้" — ตอนนั้นโฟกัสแค่ primary display ยังไม่ได้คิดถึงผลกระทบตอนเอาไปทำ scoring แบบนี้

**ทางแก้ที่ confirmed (ขอบเขตแคบ — ใช้แค่ตอนคำนวณ country_sector_score/eligibility เท่านั้น ไม่แตะ `analysis/matching.py`/results.csv/coefs.csv เดิมที่หน้าอื่นในระบบยังใช้อยู่)**:

1. Backward elimination ด้วย VIF (`statsmodels.stats.outliers_influence.variance_inflation_factor`) — ตัด index ที่ VIF สูงสุดออกทีละตัวจนทุกตัวเหลือ VIF < 5
2. **Country: 18 → 11 ตัว** — ตัดออก: WORLD, ACWI_EX_US, ACWI, ASIA_EX_JAPAN, WORLD_EX_US, EM, CHINA_ALL_SHARES (ล้วนเป็น aggregate/regional composite) เหลือ: BRAZIL, CHINA_A_SHARES, CHINA_H_SHARES, EUROPE, INDIA, JAPAN, KOREA, ASEAN, TAIWAN, USA, VIETNAM — condition number 492.3 → 3.5

**⚠️ Percentile re-rank policy (confirmed 2026-09-22)** — ตอนสลับ toggle เป็น "cleaned 11" ค่า `return_pct`/`vol_pct_good` ของ country_score (§12.8) ต้อง **re-rank percentile ภายในกลุ่ม 11 ตัวที่เหลือเท่านั้น** ไม่ใช่ใช้ percentile เดิมที่คำนวณจาก 18 ตัวเต็มแล้วกรองแสดงผลแค่ 11 — เช็คแล้วสองแบบให้ตัวเลขต่างกันจริง ไม่ใช่เรื่องเล็ก (USA: percentile ใน 18 ตัว = 0.333 vs ใน 11 ตัว = 0.455, ต่างกัน 12 percentile point; EUROPE ต่างกัน 10 point) เหตุผล: ความหมายของ "percentile" ควรสะท้อน universe ที่ผู้ใช้เลือกใช้จริง ไม่ใช่ universe ที่ถูกตัดทิ้งไปแล้วบางส่วน

**None-handling** — กองที่ regress กับ cleaned index set แล้ว coefficient เป็น 0 หมดทุกตัว (`primary=None` ตามที่ `analysis/matching.py` guard ไว้อยู่แล้ว — พบได้ถ้า R² ต่ำมากหรือ regularization ตัดทิ้งหมด) ให้ตัดออกจาก matrix ส่วนที่ 1 และ top-20 ส่วนที่ 2 ไปเลย ไม่นับเป็น 0 หรือ error
3. **Sector: เก็บครบ 10 ตัวเดิม** (ตัดสินใจ 2026-09-22: ไม่ clean sector — risk เบาอยู่แล้วตามที่คาดไว้ใน plan เดิม, ตัดแค่ IN ตัวเดียวถ้า clean ก็ยังจะ VIF=5.9 ใกล้เกณฑ์ ไม่คุ้มความซับซ้อนที่เพิ่ม)
4. Refit ElasticNetCV (`analysis/matching.py::match_exposure()` เดิมทุกอย่าง แค่ป้อน index set ที่ clean แล้ว) ต่อกองทั้ง 313 กอง → ได้ `clean_country_primary/secondary/r2` ใหม่ ใช้แทน `country_primary/secondary/r2` เดิมเฉพาะตอนคำนวณ score

**ผลยืนยัน (ตัวอย่าง TUSFIN-A)**: country primary เปลี่ยนจาก WORLD_EX_US (ของเดิม) → **USA**, secondary เปลี่ยนจาก EUROPE ติดลบ (−0.0060) → **EUROPE บวก (+0.0025)** — สัญญาณกลับมาเชื่อถือได้จริงหลัง clean

**Top-5 diversified ใหม่ (country=cleaned 11, sector=original 10, §12.9 algorithm)**:

| FundCode | score | ใช้ pair | country/sector ที่ใช้ | primary (c/s) | secondary (c/s) | R²(c/s) |
|---|---|---|---|---|---|---|
| KT-MFE-A | 5.25 | primary | USA / MT | USA / MT | EUROPE / IT | 0.71 / 0.77 |
| TUSFIN-A | 5.24 | secondary | EUROPE / CS | USA / FN | EUROPE / CS | 0.56 / 0.70 |
| TISCOEU-A | 4.05 | secondary | CHINA_A_SHARES / FN | EUROPE / MT | CHINA_A_SHARES / FN | 0.76 / 0.50 |
| ONE-EUROEQ | 3.93 | secondary | KOREA / IN | EUROPE / MT | KOREA / IN | 0.71 / 0.52 |
| ONE-APACESG | 2.44 | secondary | TAIWAN / IT | EUROPE / MT | TAIWAN / IT | 0.55 / 0.41 |

กระจายครบ 5 ประเทศ + 5 sector ไม่ซ้ำกันเลย และปัญหา LHUSFIN-A/D (share class ซ้ำ, correlation 1.00 จาก §12.7) หลุดจาก top-5 ไปเองเพราะ USA ถูกใช้ไปแล้ว — ไม่ต้องเขียนกติกา dedup เพิ่มเติม

**สถานะ**: exploratory เท่านั้น (`/tmp/clean_matches_v2.csv`) ยังไม่ได้เก็บเป็น cache ถาวรในโปรเจกต์ — รอ implement จริงตาม §12.11

---

### 12.11 หน้า 8 UI spec: Score-based screening page (confirmed 2026-09-22)

> ⚠️ **ถูกแทนที่แล้ว (2026-09-29)** — สเปกส่วนที่ 2/3 ของหน้า 8 เปลี่ยนไปแล้ว (Top 5 สำหรับ efficient frontier แทน Top 20) ดูสเปกล่าสุดที่ **§14** เก็บส่วนนี้ไว้เป็นประวัติ (ส่วนที่ 1 คะแนนโซน + 3 toggle ยังใช้เหมือนเดิม)

**Controls (บนสุดของหน้า)**:

| Control | ตัวเลือก | ผลกระทบ |
|---|---|---|
| Country index universe | All (18 ตัว) / VIF-cleaned (11 ตัว) — ดู §12.10 | เปลี่ยนขนาด matrix ส่วนที่ 1 (18×10 หรือ 11×10) และ primary/secondary ที่ใช้คำนวณ score กอง — **sector ไม่มีตัวเลือก ใช้ครบ 10 เสมอ** |
| Matching mode | Primary + Secondary (fallback) / Primary only | Primary only = ปิด secondary fallback ใน §12.9 ไปเลย กองที่ primary ชนกับที่เลือกไปแล้วตกรอบทันที ไม่เช็ค secondary ต่อ |
| Diversification strictness | ต้องใหม่ทั้ง country และ sector (AND, ค่าเริ่มต้น) / ใหม่แค่ตัวใดตัวหนึ่งพอ (OR) | OR = ผ่อนเกณฑ์ eligibility ใน §12.9 จาก "ทั้งคู่ต้องใหม่" เหลือ "ตัวใดตัวหนึ่งใหม่พอ" — **แต่ mark ว่า used ยังมาร์คทั้ง country และ sector เหมือนเดิมเสมอ** (ไม่ว่าโหมดไหน) กันกองถัดไปมาซ้ำซ้อนโดยไม่รู้ตัว |

> **ขอบเขตของแต่ละ control**: "Country index universe" มีผลกับ**ทั้งส่วนที่ 1 และ 2** (เปลี่ยนขนาด matrix + primary/secondary ที่ใช้คำนวณ) ส่วน "Matching mode" และ "Diversification strictness" มีผลกับ**ส่วนที่ 2 เท่านั้น** (ส่วนที่ 1 เป็น index-level score ล้วนๆ ไม่เกี่ยวกับกองทุน/การคัดเลือก)

**ส่วนที่ 1 — Country × Sector score matrix**: ตาราง `country_sector_score(i,j)` (§12.8 สูตร) ขนาด 18×10 หรือ 11×10 ตาม config ด้านบน (เหมือนตารางที่ทำไว้ก่อนหน้านี้ — heatmap หรือตาราง ใส่ full sector name แทนตัวย่อกันงงตาม legend §12.8)

**ส่วนที่ 2 — Top 20 กองทุน**: รัน greedy algorithm (§12.9) ตาม 3 control ด้านบน ไปจนกว่าจะครบ **20 กอง** (ขยายจาก top-5 ที่ทดสอบไว้) แสดง: FundCode, score (=score_primary), **score_secondary** (โชว์เสมอเพื่อความโปร่งใส — ดู §12.9 resolution), ใช้ pair ไหน (primary/secondary), country/sector ที่ใช้จริง, primary/secondary pair เต็ม, R² — กองที่ `primary=None` (ดู §12.10 None-handling) ไม่นับรวมในลิสต์นี้

**สถานะและงานที่เหลือ**:
- [x] สูตร + notation confirm แล้ว (§12.8)
- [x] Greedy diversified algorithm confirm แล้ว (§12.9) — รวม known limitation เรื่อง score_secondary อ่อน
- [x] VIF-cleaning fix สำหรับ sign bug confirm แล้ว (§12.10) — ขอบเขตแคบ ไม่แตะระบบเดิม
- [x] UI spec หน้า 8 confirm แล้ว (ส่วนนี้)
- [ ] **ยังไม่เริ่ม implement จริง** — ต้องสร้าง:
  - `cache/country_matches_all18.csv` และ `cache/country_matches_clean11.csv` (**precompute ล่วงหน้าทั้ง 2 ชุด ห้าม refit สดตอน toggle** — วัดเวลาจริงแล้ว refit 313 กอง ใช้ ~40 วินาที ต่อชุด ช้าเกินไปสำหรับ UI toggle)
  - ฟังก์ชันใน `data_access.py` สำหรับอ่าน cache ที่ถูกต้องตาม toggle 3 ตัว (รวม re-rank percentile ตาม §12.10 policy)
  - หน้า `pages/8_...py`
- [x] เรื่อง score_secondary display ตัดสินใจแล้ว (§12.9 resolution) — โชว์เป็นคอลัมน์ ไม่ auto-filter
      **อัปเดต 2026-09-29 (§12.12)**: เปลี่ยนเป็น auto-filter แบบ band (signed) แล้ว — ดู §12.12
- [x] Percentile re-rank policy ตัดสินใจแล้ว (§12.10) — re-rank ภายใน universe ที่เลือกจริง
- [x] None-handling ตัดสินใจแล้ว (§12.10) — ตัดออกจากทั้ง 2 ส่วน
- [ ] Style scope / macro scope (แผนเดิมบอกอยากลอง 3 แบบ: country+sector / style / macro) — ยังไม่เริ่ม
- [ ] Rebalance ทุก 3 เดือน — คุยแนวคิดคร่าวๆ แล้ว (§12 เดิม) ยังไม่ implement

### 12.12 แก้ secondary ไม่มีเกณฑ์ขั้นต่ำ → เพิ่ม band filter แบบมีทิศทาง (confirmed 2026-09-29)

**ที่มา**: อธิบายคอลัมน์หน้า 8 ให้ผู้ใช้ฟัง แล้วถูกถามว่า "คู่สำรองต้องอยู่ในเกณฑ์คัด secondary ใช่ไหม" —
พบว่า `country_secondary`/`sector_secondary` ที่ใช้ในหน้า 8 (จาก `match_exposure()`) แค่เป็น
"อันดับ 2 ของ |coefficient| ที่ไม่ใช่ 0" **ไม่มีเกณฑ์ขั้นต่ำเลย** ต่างจาก `classify_exposure()` (หน้า 5/6)
ที่มีเกณฑ์ band (`SECONDARY_BAND_PCT=0.30`, |coef| >= 70% ของ primary) แต่ก็ยังใช้ |coef| ไม่สนเครื่องหมายเหมือนกัน
(ยังมีปมสวนทางแบบเดียวกับที่เจอใน §12.10 ได้อยู่)

**Fix (ตัดสินใจร่วมกัน 2026-09-29)**:
- ขอบเขต: **เฉพาะหน้า 8** (`analysis/screening.py` + `data_access.py`) ไม่แตะ `analysis/matching.py`
  (หน้า 5/6 ที่ใช้ `classify_exposure()`/band แบบเดิมไม่กระทบ — สอดคล้องแนวทาง VIF-clean ใน §12.10)
- สูตร: secondary ต้องอยู่ในช่วง **`[primary_coef × (1 − pct), primary_coef]`** — คือทิศทางเดียวกับ primary
  (ไม่ใช่ |coef|) และแรงอย่างน้อย (1 − pct) ของ primary · ทำทั้ง country และ sector แยกกัน ต้องผ่านทั้งคู่
- threshold: ตัวแปรแยกเฉพาะหน้า 8 — `config.SCORE_SECONDARY_BAND_PCT = 0.30` (ไม่ reuse `SECONDARY_BAND_PCT`
  ของหน้า 5/6 กันกระทบกัน ถึงแม้ค่าจะเท่ากันตอนนี้)
- ไม่ผ่าน band → `score_secondary` เป็น `NaN` → หน้าเว็บโชว์ `"-"` ในคอลัมน์ `score (คู่สำรอง)` และ
  ⚠️ ภายหลังหน้า 8 แสดงเฉพาะกองที่ผ่านเกณฑ์ — คอลัมน์ `score (คู่สำรอง)` ไม่มีแล้ว (แทนด้วย `score คู่ที่ใช้` §22)
  `greedy_select()` จะไม่ลองคู่นี้เป็น fallback เลย (เช็คแค่ `pd.isna(score_secondary)` ก่อนลอง — reuse ของเดิม)

**โค้ดที่แก้**: `config.py` (constant ใหม่) · `data_access.py` (`build_score_matches()` เก็บ `*_coef` เพิ่ม,
`score_matches()` เติม `*_primary_coef`/`*_secondary_coef` ให้ครบ 4 คอลัมน์, ฟังก์ชันใหม่ `_secondary_coef()`
ดึงจาก `cache/coefs.csv`) · `analysis/screening.py` (ฟังก์ชันใหม่ `_passes_band()`, `fund_scores()` เซ็ต NaN,
`greedy_select()` เช็ค NaN ก่อนลอง secondary) · `pages/8_...py` (คอลัมน์ display ใหม่ + ข้อความอธิบาย) ·
`tests/test_screening.py` (เพิ่ม test `_passes_band`, band-fail nulls score_secondary, greedy skips NaN fallback)

---

### 12.13 เปลี่ยน momentum เป็นแบบข้ามเดือนล่าสุด (12-1) — confirmed + implement แล้ว 2026-09-29

> ⚠️ **ข้อ 1–2 ในหัวข้อ "ข้อค้นพบอื่น" ด้านล่าง (ขา vol ของคะแนนโซน) ถูกต่อยอด/แทนที่โดย §12.14 (แผนแก้ 2026-09-30 — ยังไม่ implement)** · ส่วน momentum 12-1 ของ §12.13 ยังใช้ตามเดิม

**ที่มา**: ตรวจความเหมาะสมของคะแนนโซนด้วย backtest จาก walk-forward GARCH ที่หน้า 4 เก็บไว้แล้ว
(55 รอบ × 28 ดัชนี · 2021-12 → 2026-06) — IC = Spearman รายรอบแล้วเฉลี่ยข้ามรอบ:

| สัญญาณ | IC ต่อ return 63 วัน | IC ต่อ Sharpe 63 วัน | IC ต่อ vol 63 วัน |
|---|---|---|---|
| momentum 252d ล้วน | **+0.099** (t 2.53 · ปรับ overlap 1.46) | +0.077 | — |
| vol_pct_good ล้วน | **−0.067** | +0.011 | **−0.80** |
| คะแนนโซน (สูตรเดิม) | +0.016 | +0.064 | — |
| คะแนนโซน (ข้ามเดือนล่าสุด) | **+0.036** | — | — |

**ตัดสินใจ**: สัญญาณ return เปลี่ยนเป็น **t−252 → t−21 (11 เดือน)** ตาม Jegadeesh-Titman 12-1
**implement แล้ว**: `config.SCORE_RETURN_SKIP=21` + `SCORE_RETURN_COL` · `metrics.recent_return(skip=...)` ·
`data_access._load_index_snapshot` · `analysis/screening.zone_scores` · หน้า 8 · docs · test (74 ผ่าน)
ผลที่เปลี่ยน: sector นำโดย IN/MT/FN (เดิม FN เดี่ยว) · กองที่ผ่านเกณฑ์ 6 กอง · Top 5 = KT-MFE-A, PRINCIPAL GEF-X,
K-SEMQ, KT-JPFUND-A, K-AEC (ตรงกับตาราง §13.0)

**ข้อค้นพบอื่นจากการทดสอบเดียวกัน — ยังไม่เปลี่ยนอะไร บันทึกไว้ตัดสินใจภายหลัง**:
1. ขา vol ทำนาย **vol** ได้ดีมาก (IC −0.80 กับ vol จริง) แต่ทำนาย **return** ได้ติดลบ (−0.067) การคูณสองขาจึงทำให้
   สัญญาณ return จางลงจาก 0.099 เหลือ 0.036 · แยก scope แล้วขา vol ช่วยฝั่ง country (Sharpe 0.112 vs 0.082)
   แต่ทำให้ฝั่ง sector แย่ลง (0.016 vs 0.072) — ทางเลือกคือตัดขา vol ออก หรือใช้เฉพาะฝั่ง country
2. GARCH 21 วันจัดอันดับ vol ใกล้เคียง vol จริงย้อนหลัง 3 ปีมาก (rank corr 0.96 country · 0.94 sector) →
   horizon ไม่ใช่ปัญหา **แต่** แปลว่า vol ถูกนับซ้ำกับ Σ ของ frontier (ตัวคัดเลือกกอง vol ต่ำ แล้ว optimizer ลงโทษ vol อีกรอบ)
3. **Π = γΣW ไม่มีสัญญาณจากคะแนนโซนอยู่เลย** — เหตุผลที่กองถูกเลือกหายไปหมดในขั้นจัดน้ำหนัก ถ้าต้องการให้สัญญาณ
   ไหลต่อถึง frontier ต้องใส่คะแนนโซนเป็น **BL views (P/Q/Ω)** ทับบน Π (ตอนนี้ใช้ BL แค่ครึ่งเดียวคือ reverse optimization)
4. ความนิ่งของอันดับโซนข้ามไตรมาส: rank corr 0.76 (country) / 0.67 (sector) · top-3 เปลี่ยนราวครึ่งหนึ่งทุกไตรมาส
   → สมาชิก Top 5 จะหมุนบ่อยกว่าที่ Σ 3 ปีจะขยับ

### 12.14 แก้ส่วนที่ 1 (คะแนนโซน): เปลี่ยนเป็น return 12-1 ÷ realized vol — **confirmed + implement แล้ว 2026-09-30 (ผลดูท้ายหัวข้อ)**

> สถานะ: ผู้ใช้ยืนยันสูตรและให้เขียนแผนแล้ว · **ยังไม่มีโค้ดถูกแก้** · เอกสารนี้แทนที่ (supersede) ส่วนที่บอกว่าขา vol = GARCH ใน §12.13 ข้อ 1–2,
> §14.2 และ `docs/pages/8-score-screen.md` (ไม่ลบของเดิม — ติดธงแล้วที่ §12.13 และ §14.2 · ส่วน `docs/pages/8-score-screen.md` จะอัปเดต/ติดธงตอน implement ขั้นที่ 6)

**ที่มา**: dry run 2026-09-30 (read-only, สคริปต์อยู่ใน /tmp ของเครื่อง ไม่ได้อยู่ในโปรเจกต์) ทดสอบ 54 รอบ ทุก 21 วัน
(2021-12-21 → 2026-03-27 · ตัดที่ข้อมูลถึง 2026-06-30 ให้มี 63 วันข้างหน้าครบ) universe = country VIF-cleaned 11 + sector 10 **แยก scope**
IC = Spearman รายรอบต่อผลตอบแทน 63 วันข้างหน้า แล้วเฉลี่ย · t = Newey-West lag 3 · ผลตอบแทนเซลล์ (110 เซลล์) เป็น proxy = เฉลี่ย country+sector
(ไม่มีอนุกรมเซลล์จริง) · ข้อมูลดัชนีใช้ตามเดิม **ไม่ clean วันหยุด** (ผู้ใช้ตัดสินใจ)

| สูตรคะแนนโซน | IC country 11 | IC sector 10 | IC เซลล์ 110 (proxy) | เอียง vol ต่ำ (c/s) | นิ่ง 63 วัน (c/s) |
|---|---|---|---|---|---|
| A1 return 12-1 ล้วน | 0.074 | 0.088 | 0.077 | 0.07 / −0.22 | 0.61 / 0.72 |
| **A3 return 12-1 ÷ realized vol 12-1 (สูตรใหม่)** | **0.087** | **0.097** | **0.085 (t 1.55)** | 0.15 / −0.06 | 0.63 / 0.69 |
| A2 return ÷ GARCH 63 วัน | 0.080 | 0.088 | 0.079 | 0.14 / −0.07 | 0.63 / 0.69 |
| A5 สูตรเดิม (อันดับ return × อันดับ GARCH 21 วัน) | −0.031 | 0.030 | −0.014 | 0.71 / 0.56 | 0.71 / 0.69 |
| A4 สูตรเดิมแต่ GARCH 63 วัน | 0.002 | 0.030 | −0.005 | 0.71 / 0.57 | 0.73 / 0.67 |
| B1 ตัวกรอง (ตัด vol สูงสุด 25% แล้วเรียง return) | −0.012 | 0.029 | −0.029 | 0.62 / 0.41 | 0.67 / 0.52 |
| C1 z(return) − 0.25·z(vol63) | 0.050 | 0.059 | 0.047 | 0.26 / −0.03 | 0.61 / 0.70 |

ข้อสรุปจาก dry run: (1) ใส่ vol ยิ่งมาก IC ยิ่งลด — ตัวกรองและสูตรแบบบวกแย่กว่า return ล้วน (2) สูตรเดิมเอียงไปหาตลาด vol ต่ำ (สหสัมพันธ์ 0.71/0.56)
จน IC ของ country ติดลบ (3) A3 ดีที่สุดใน 3 ระดับ ตัดอคติ vol ต่ำเหลือ 0.15/−0.06 และไม่ต้องพึ่ง GARCH (4) **ข้อจำกัด**: ไม่มีสูตรไหนผ่าน t = 2
(A3 สูงสุด t = 1.26 country · 1.40 sector · 1.55 เซลล์) · ความต่างจาก return ล้วนไม่มีนัยสำคัญ (ΔIC +0.007, t 0.61) · ตัวอย่างรอบ overlap กัน
· ควรอ่านเป็นแนวโน้ม ไม่ใช่การพิสูจน์ · Top 5 ของเซลล์คงเดิมหลัง 63 วันเพียง ~31% (สูตรเดิม 37%) — หมุนบ่อยขึ้นเล็กน้อย

**สูตรที่ยืนยัน (ต่อดัชนี ณ วัน t = วันล่าสุดของข้อมูล)**

```
mom   = ราคา(t−21) ÷ ราคา(t−252) − 1                                   # เดิม (SCORE_RETURN_COL) ไม่เปลี่ยน
vol   = std(ผลตอบแทนรายวัน 231 ตัว ช่วงเดียวกับ mom, ddof=1) × √252       # ใช้ metrics.annualized_volatility ที่มีอยู่แล้ว
ratio = mom ÷ vol                                                        # vol <= 0 หรือ NaN -> ratio = NaN
score = pct_rescaled(ratio)  (percentile ภายใน scope ที่เลือก -> (0.01, 0.99))
cell  = country_score × sector_score × SCORE_MATRIX_SCALE                # เหมือนเดิม
```

- ตัวหาร **ไม่ใช่ GARCH และไม่ใช่การพยากรณ์** — ใช้ realized vol ของช่วง 12-1 เอง (231 ผลตอบแทน) ตัดสินใจ 2026-09-30 แทนไอเดีย "GARCH 63 วัน" ที่เคยเสนอ
  (ผล IC ของ realized สูงกว่า GARCH เล็กน้อยทุกระดับ) → **ไม่ต้องเปลี่ยน `VOL_FORECAST_HORIZON`** (ยัง 21 สำหรับหน้า 4/5)
- ×√252 คือการแปลงเป็นรายปีตามธรรมเนียมของระบบ (`config.TRADING_DAYS`) ไม่ใช่ความยาวหน้าต่าง · ตัวคูณต่างจาก √231 เป็นค่าคงที่ ไม่กระทบอันดับ
- ใช้กับทั้ง country และ sector (ผล sector 10 ก็ดีที่สุด) · percentile ยัง re-rank **ภายใน universe ที่เลือก** ตาม §12.10 (11 หรือ 18 country)
- ข้อมูลวันหยุดตลาดใช้ตามเดิม (ไม่ clean) → realized vol ต่ำกว่าจริงเล็กน้อย (~5–8% ของวันต่อดัชนีเป็นวันหยุด) กระทบทุกดัชนีใกล้เคียงกัน

**ที่ต้องแก้ (ทั้งหมดเล็ก · ไม่แตะ `analysis/matching.py` · `analysis/macro_chain.py` · `analysis/metrics.py` · `analysis/vol_forecast.py`)**

| ไฟล์ | สิ่งที่ทำ | เหตุผล |
|---|---|---|
| `config.py` (~บรรทัด 214–228) | เพิ่ม `SCORE_VOL_COL` (ชื่อคอลัมน์ vol ของ snapshot) + `SCORE_ZONE_METHOD` (`"ret_over_realized_vol"` = ใหม่ / `"rank_x_rank_garch"` = เดิม) + ปรับ comment | ประกาศที่เดียวเหมือน `SCORE_RETURN_COL` · ค่าสวิตช์ทำให้ย้อนกลับและ A/B ได้ (ดูข้อ "ยังไม่ตัดสินใจ") |
| `analysis/screening.py` | เพิ่มฟังก์ชันบริสุทธิ์ `realized_vol_window(series, window, skip)` (ใช้ `metrics.annualized_volatility`) + แตกกิ่งใน `zone_scores()` ตาม `SCORE_ZONE_METHOD` · กิ่งใหม่คืนคอลัมน์ `[return_12m1, vol_realized, ratio, score]` · กิ่งเดิมคงไว้ทั้งหมด | จุดเดียวที่คำนวณคะแนน · `score` ยังชื่อเดิม `score_matrix` / `fund_scores` ใช้ต่อได้ |
| `data_access.py` `_load_index_snapshot()` (~บรรทัด 178) | เพิ่มคอลัมน์ `SCORE_VOL_COL` ต่อดัชนี **คง `vol_forecast` และ `garch_fallback` ไว้** | หน้า 5 (`viz.py` ~บรรทัด 268) ใช้ `vol_forecast` ต่อ · snapshot คำนวณสดทุกครั้ง จึง **ไม่ต้อง rebuild cache** |
| `pages/8_🧭_Score_Screen.py` (caption ~บรรทัด 18–19 และ ~72–74, expander คะแนนรายดัชนี) | แก้ข้อความสูตร + ชื่อคอลัมน์ในตาราง | ข้อความเดิมบอก "vol ที่ทำนายไว้ต่ำ" และ "[1 − percentile(vol forecast)]" |
| `tests/test_screening.py` (fixture `_snapshot()` + เคสบรรทัด ~38–63, ~97, ~115) | เพิ่ม fixture คอลัมน์ `SCORE_VOL_COL` · เพิ่มเคสใหม่ · เคสเดิมที่ผูกกับสูตรเดิมให้รันภายใต้ `SCORE_ZONE_METHOD="rank_x_rank_garch"` (monkeypatch) | ไม่ลบ test เดิม |
| `docs/pages/8-score-screen.md` (~บรรทัด 26 และหัวข้อข้อจำกัด ~220–226) | อัปเดตสูตร + ข้อจำกัด (เดิมเขียน "return เป็นอดีตแต่ vol เป็นอนาคต / horizon ไม่เท่ากัน" — ใช้ไม่ได้แล้ว: ทั้งสองขาเป็นอดีตช่วงเดียวกัน) | ตามกติกา flag/supersede |

**ขั้นตอน implement (ทำเรียงลำดับ · ทุกขั้นเช็ค 3 เรื่อง: โค้ดที่เพิ่งเขียนถูกไหม / ของเดิมยังรันได้ไหม / โครงสร้างไม่ซับซ้อนเกินจำเป็น)**

0. **Baseline ก่อนแก้**: รัน `pytest -q` (บันทึกจำนวนที่ผ่าน) + บันทึก Top 20 / Top 5 ของหน้า 8 ในทั้ง 8 toggle (universe 11/18 × mode × AND/OR) เก็บเป็นไฟล์เทียบก่อน–หลัง
1. เพิ่มค่าคงที่ใน `config.py` โดยพฤติกรรมยังเหมือนเดิม (สวิตช์ตั้ง `"rank_x_rank_garch"` ชั่วคราว) → รัน test ต้องผ่านเท่าเดิม
2. เขียน `realized_vol_window()` + test หน่วยของมัน (ข้อ 4) ก่อนเชื่อมกับ snapshot
3. เพิ่มคอลัมน์ใน `_load_index_snapshot()` → เช็คว่าหน้า 5 และแคชหน้า 4 ไม่เปลี่ยน (เทียบค่า `vol_forecast` ก่อน–หลังต้องเท่ากันทุกตัว)
4. เพิ่มกิ่งใหม่ใน `zone_scores()` + เคสทดสอบ (ดูด้านล่าง) → สลับสวิตช์เป็นสูตรใหม่
5. **Recalibrate `SCORE_MIN_ELIGIBLE`** (ดูหัวข้อถัดไป — ต้องตัดสินใจก่อนขั้นนี้)
6. แก้ข้อความหน้า 8 + docs + ติดธงในเอกสารแผน
7. **ตรวจยืนยัน**: (ก) เทียบ `zone_scores` กับตัวเลขจากสคริปต์ dry run ณ วันเดียวกัน (ตัดข้อมูลถึง 2026-03-27) อันดับต้องตรงทุกดัชนี (ข) ตาราง Top 5 ก่อน–หลังต่อ toggle · จำนวนกองที่ผ่านเกณฑ์ต้อง ≥ `PORTFOLIO_MIN_FUNDS` (3) ทุก toggle และควร ≥ 5 ในค่าเริ่มต้น (ค) `pytest -q` ทั้งชุดต้องผ่านไม่น้อยกว่า baseline (ง) เปิดหน้า 8 ผ่าน smoke test / เปิดจริงหนึ่งครั้ง

**เคสทดสอบใหม่ (fixture รู้คำตอบ)**: ratio เรียงถูกทิศ (mom สูง vol ต่ำ = ดีสุด) · momentum ติดลบไม่ทำให้ error และได้อันดับท้าย · vol = 0 หรือ NaN → ratio NaN
ไม่ crash และ NaN ไม่ไหลเป็น score ที่ผ่านเกณฑ์ · window ถูก 231 ผลตอบแทน (t−251..t−21) เทียบกับคำนวณมือ · `skip = 0` ไม่ได้ slice ว่าง (`iloc[-w:-0]` ว่าง! ต้องกันกรณีนี้) ·
percentile re-rank ภายใน universe ที่ส่งเข้า (ชุด 11 vs 18 ตาม §12.10) · `score` อยู่ใน [0.01, 0.99] · vol เท่ากันทุกตัว → อันดับ = อันดับของ mom · ข้อมูลสั้นกว่า window → NaN

**⚠️ สเกลคะแนนเปลี่ยน — `SCORE_MIN_ELIGIBLE = 0.7` ใช้ต่อไม่ได้ (ต้องตัดสินใจ)**

เดิม cell = (rank_ret × rank_vol)_country × (rank_ret × rank_vol)_sector × 100 (สูงสุด ~17.9 ในโหมด 11) ส่วนใหม่ cell = country_score × sector_score × 100 โดยแต่ละตัวอยู่ใน (0.01, 0.99)
→ สูงสุด ~98 ค่ากลาง ~25 และ fund score = R²_country × R²_sector × cell (R² ทำให้เล็กลงอีก) เกณฑ์ 0.7 บนสเกลใหม่จะ **ผ่านเกือบทุกกอง**
(ตกเฉพาะเมื่อ R²_country × R²_sector × cell < 0.7 เช่น R² ต่ำมาก หรือโซนท้ายสุดทั้งสองฝั่ง) กองจะแทบไม่ถูกกรองโดยคะแนนโซนอีก ทางเลือก:
- (ก) **จับคู่เปอร์เซ็นไทล์**: หาค่าที่ทำให้สัดส่วนกองที่ผ่านเกณฑ์ใน snapshot ล่าสุดเท่าปัจจุบัน แล้วตรวจความเสถียรข้าม 54 รอบ — แนะนำเป็นจุดเริ่ม
- (ข) **เกณฑ์ตีความง่าย**: ทั้ง country และ sector อยู่เหนือค่ากลางของ universe (คู่ ≥ 0.25 → cell ≥ 25 ก่อนคูณ R²)
- (ค) ตั้งจากจำนวนกองที่ต้องการ: ให้ได้กองที่ผ่านเกณฑ์ ≥ 5 ในค่าเริ่มต้นและ ≥ 3 ทุก toggle
ต้องรัน dry run กระจายของ `score` ใหม่ก่อนเลือก — **ยังไม่ตัดสินใจ**

**ความเสี่ยง / ข้อควรระวัง**
- หลักฐานอ่อน (t < 2 ทุกสูตร, 54 รอบ overlap, 11 และ 10 ดัชนีต่อรอบ) — ทางเลือกที่เรียบง่ายกว่าคือ A1 (return ล้วน) ซึ่งผลใกล้เคียง (ΔIC A3−A1 = +0.007 ไม่มีนัยสำคัญ) เลือก A3 เพราะตัดอคติ vol ต่ำและมีความหมาย "return ต่อความเสี่ยง" อธิบายง่าย
- **ตัวหาร vol เป็นข้อมูลอดีต**: ตัด GARCH ออกจากคะแนนโซนแล้ว vol ไม่ใช่สัญญาณล่วงหน้าอีก (แต่ dry run ก่อนหน้าชี้ว่า GARCH ไม่ได้เพิ่ม IC ต่อ return อยู่ดี)
- **การเลือกสูตรมาจาก dry run เดียวกัน** (มี selection bias เล็กน้อย) — ควรติดตาม IC ต่อเมื่อมีข้อมูลรอบใหม่
- **Top 5 ของเซลล์หมุนบ่อยขึ้นเล็กน้อย** (คงเดิม ~31% เทียบ ~37%) ผลต่อ turnover ของพอร์ต — ตัดสินใจร่วมกับกติกา rebalance รายไตรมาส
- ตัวเลข IC ที่ระดับเซลล์เป็น proxy ไม่ใช่ผลตอบแทนเซลล์จริง · การทดสอบกับผลตอบแทนกองจริง (NAV เบาบาง ~60% ของวัน) ยังไม่ทำ
- ปัญหาข้อมูลที่ยังเปิดอยู่ (ไม่ได้แก้ในแผนนี้): เกาหลี (มีวัน |ret| > 10% ถึง 7 วัน) · วันหยุดตลาด (ตัดสินใจไม่ clean) · NAV กองที่หยุดอัปเดต

**ตัดสินใจแล้ว (2026-09-30)**: return = 12-1 (ไม่เปลี่ยน) · ตัวหาร = realized vol ช่วง 12-1 (ไม่ใช่ GARCH) · รวมด้วยการหาร ไม่ใช่คูณอันดับ · ใช้ข้อมูลดัชนีตามเดิม ไม่ clean วันหยุด ·
ชุดทดสอบ = country VIF-cleaned 11 + sector 10 · ใช้สูตรใหม่กับทั้ง country และ sector

**ยังไม่ตัดสินใจ**: (1) วิธี recalibrate `SCORE_MIN_ELIGIBLE` (2) เก็บสวิตช์ `SCORE_ZONE_METHOD` ไว้ถาวรหรือถอดหลังรอบแรก (แนะนำเก็บไว้หนึ่งรอบเพื่อ A/B แล้วถอด)
(3) จะ clean เกาหลี/วันหยุดภายหลังหรือไม่ (4) ทดสอบกับผลตอบแทนกองจริงก่อน implement หรือไม่

**ตัดสินใจครบ + implement แล้ว (2026-09-30)**
- (1) **คง `SCORE_MIN_ELIGIBLE = 0.7`** — dry run 55 รอบกับ return กองจริง: พอร์ต Top 5 (โหมดเริ่มต้น) ชนะค่าเฉลี่ยกอง +2.42%/63 วัน (t 5.6)
  เทียบเกณฑ์ (ก) 2.75 ที่ +1.89% (t 3.9) และสูตรเดิม +1.13% (t 2.8) · (ก) ไม่นิ่ง (สัดส่วนผ่าน 50–78% ข้ามรอบ) และให้แค่ 4 กอง
- (2) สวิตช์ `SCORE_ZONE_METHOD` เก็บ 1 รอบแล้วถอด (ค่าปัจจุบัน `"ret_over_realized_vol"`)
- (3) **เกาหลีไม่ต้อง clean** — 7 วันที่ขยับ > 10% ขยับทิศเดียวกับ Taiwan/EM/Asia ex Japan ทุกครั้ง (2–3 เท่า = beta สูง ไม่ใช่ spike)
  · ปี 2025 +84% · ตัดวันเหล่านั้นแล้วยังอันดับ 2 (mom +149% · vol 50%) · วันหยุด: ตามเดิม ไม่ clean
- (4) ทดสอบกับ return กองจริงแล้ว (NAV clean 209 กอง · 55 รอบ): IC คะแนนกอง สูตรใหม่ 0.132 (t 4.05) · เดิม 0.104 (t 2.87) ·
  return ล้วน 0.132 · ใหม่ − เดิม +0.027 (t 1.32 ไม่มีนัยสำคัญ) · ⚠️ exposure จากข้อมูลทั้งช่วง + เฉพาะกองที่ยังอยู่ (look-ahead/survivorship)

**ผลหลัง implement** (test 108 ผ่าน · snapshot คอลัมน์เดิมเท่าเดิมทุกตัว → หน้า 5 ไม่กระทบ · ratio ตรงกับ dry run)
- อันดับ country: TAIWAN · KOREA · CHINA_A · USA · EUROPE · … · INDIA (ติดลบ) · sector: IT · IN · HC · MT · FN · … · CD
- ผ่านเกณฑ์ 8 โหมด (P+S·AND / P+S·OR / P·AND / P·OR): clean 11 = 5 / 14 / 4 / 15 · ชุด 18 = 6 / 20 / 6 / 20 (ทุกโหมด ≥ 3)
- โหมดเริ่มต้น 5 กอง: TLUSNDQ-H-A (USA/IT) · KT-EMEQ-A (KOREA/MT) · MATECH-A (ทางคู่สำรอง TAIWAN/CD · คู่ 2.57) · M-EUBANK
  (EUROPE/FN) · KT-JPFUND-A (JAPAN/IN) · frontier 885,801 ชุด → 1,084 จุด · max Sharpe 0.32 (risk 14.0% · 28/27/9/16/20) ·
  equal weight 0.31 · min-variance risk 13.5%

---

## 13. Efficient Frontier จาก Top 5 (หน้า 8 Score Screen) — kickoff ต่อจาก §3-§11 (เริ่มคุย 2026-09-29)

> ⚠️ **ถูกแทนที่แล้ว (2026-09-29 เช่นกัน — คุยต่อในวันเดียวกัน)** — คุณบอกว่าส่วนนี้ "ผสมเยอะไปหน่อย" ให้เขียนสเปกหน้า 8 รวมใหม่ทั้งหน้า ดู **§14** สำหรับสเปกล่าสุด (3 ส่วนชัดเจน: เงื่อนไข/ส่วน 1 เดิม + ส่วน 2 = Top 5 เท่านั้น + ส่วน 3 = plot frontier) เก็บ §13 นี้ไว้เป็นประวัติการคิด (ตัวเลขตัวอย่าง Top 5 ในนี้ยังใช้อ้างอิงได้)

> สถานะ: **แผน — ยังไม่ execute code** (รอ confirm ตาม checklist §13.1 ก่อน)
> บริบท: §3-§11 คือแผน risk-model optimizer เดิม (Σ=BFBᵗ+D, joint 28-factor, Ledoit-Wolf) ที่ validate ไว้แล้วด้วยข้อมูลจริงแต่ **ยังไม่เคย implement เป็นโค้ดจริงสักบรรทัด** (เช็คแล้ว — checklist §9 ทุกข้อยังไม่ติ๊ก) ตอนนี้ผู้ใช้อยากเริ่มจริงจัง แต่เปลี่ยนจุดเริ่มต้นจาก "เลือกกองทุนเองทั้ง 313 กองแบบ multiselect" (§8 เดิม) เป็น **"เอา Top 5 จากหน้า 8 Score Screen มาทำ efficient frontier"** — risk model core (§3-§7) ยังใช้แนวทางเดิมได้ ไม่ต้องคิดใหม่

### 13.0 สิ่งที่ยืนยันร่วมกันแล้ว (2026-09-29)

1. **Objective = Phase 2 เต็มรูป (mean-variance)** ไม่ใช่ Phase 1 (min-variance/risk-parity เฉยๆ) — เพราะ "efficient frontier" ตามนิยามที่ยืนยันกันคือ **กราฟเส้นแสดงพอร์ตที่ risk ต่ำสุดในแต่ละระดับ return ที่ต้องการ** (สลับ target return/λ หลายจุดแล้ว minimize variance ที่ target นั้น) ซึ่งต้องมี expected return เป็น input เสมอ — ใช้ `ann_return` จาก `results.csv` (มี annualization bias ตามที่ README บันทึกไว้ — **ต้องโชว์คำเตือนกลางหน้า ไม่ใช่แค่ footnote**)
   - หมายเหตุ: จุดซ้ายสุดของ frontier (return ต่ำสุดที่ไล่ถึง) ก็คือ **min-variance portfolio เดิมของ Phase 1** อยู่ในตัวอยู่แล้ว — ไม่เสียของที่ validate ไว้ใน §3
2. **กองทุนตั้งต้น = Top 5 ที่ "ผ่านเกณฑ์" (eligible=True) จากตาราง Top 20 หน้า 8** หลัง 3 toggle (country universe, matching mode, diversification) ที่ผู้ใช้ตั้งไว้ ณ ขณะนั้นบนหน้า 8 — ไม่ใช่ Top 5 ก่อนกรอง diversification (เช่นเดียวกับที่หน้า 8 ranking โดยรวมใช้อยู่)

**ตัวอย่างจริงที่ทดสอบแล้ว** (default toggles ของหน้า 8: VIF-cleaned 11, Primary+Secondary, AND):

| # | FundCode | FundName | score | used_country | used_sector | ann_return | ann_vol |
|---|---|---|---|---|---|---|---|
| 1 | KT-MFE-A | KTAM Multi Manager Flexible Equity Fund - Class A | 10.66 | USA | Materials | 8.1% | 14.4% |
| 2 | PRINCIPAL GEF-X | Principal Global Equity Fund | 9.46 | EUROPE | Information Technology | 11.4% | 14.1% |
| 3 | K-SEMQ | K Selective Emerging Markets Equity Fund | 4.65 | CHINA_H_SHARES | Consumer Discretionary | 3.5% | 19.1% |
| 4 | KT-JPFUND-A | KTAM Japan Equity Passive Fund - Class A | 3.45 | JAPAN | Industrials | 19.8% | 20.3% |
| 5 | K-AEC | K ASEAN Economic Community Equity Fund | 1.35 | ASEAN | Financials | 6.1% | 9.6% |

หมายเหตุสำคัญ: `n_eligible` รวม ณ toggle นี้ = **6 กอง** — พอสำหรับ Top 5 พอดี (เหลือเผื่อ 1) แต่ก่อนหน้านี้เคยเจอ toggle ที่ eligible เหลือแค่ 6-9/20 เท่านั้น (โหมด AND) ถ้าผู้ใช้ปรับ toggle จนเหลือ eligible **น้อยกว่า 5** ต้องมี fallback UI (ดู 13.1.2)

### 13.1 ปัญหาที่ต้องคุยก่อนเขียนโค้ด (ยังไม่ตัดสินใจ — ต้อง confirm ก่อนเริ่ม)

**1. Max weight cap ไม่ทำงานกับ N=5 กอง (สำคัญที่สุด — ตัวเลขจากแผนเดิมใช้ต่อไม่ได้ตรงๆ)**

แผนเดิม (§5) เสนอ `max_weight=20%` ต่อกอง (กันกระจุกตัวกองเดียว) — แต่ถ้ามีแค่ **5 กอง** เพดาน `20% × 5 = 100%` พอดี ผลคือ constraint `Σw=1, w≥0, w≤20%` มีทางแก้เดียวคือ **ทุกกองต้องได้ 20% เท่ากันเป๊ะ** (equal-weight บังคับ) — optimizer จะไม่มีทางเลือกให้ปรับตาม return/risk เลย ทุกจุดบน "เส้น" frontier จะกลายเป็นจุดเดียวจุดเดียวกันหมด (ไม่ใช่เส้นจริง) ต้องเลือกทางแก้ทางใดทางหนึ่ง:
- **(a) ไม่ใส่ cap เลยสำหรับหน้านี้** (constraint แค่ long-only + full-invested) — ง่ายสุด แต่เสี่ยง concentration ถ้ากองใดกองหนึ่ง dominate (เช่น idio risk ต่ำมากจนได้น้ำหนักเกือบ 100%)
- **(b) ปรับ cap ตามจำนวนกองอัตโนมัติ** เช่น `cap = max(20%, ceil(100%/N) + buffer)` หรือง่ายกว่านั้น `cap = 100%/N × 2` (สำหรับ N=5 → cap=40%) — ให้พอมี room ขยับแต่ไม่กระจุกเดียวเกินไป
- **(c) ให้ผู้ใช้ปรับ cap ผ่าน UI slider ได้เอง** แต่ระบบต้องเช็ค `N × cap ≥ 100%` ก่อนรัน optimizer ไม่งั้นเตือน/บล็อกไว้ก่อน (กันเจอ error จาก scipy convergence ที่มาจาก constraint พังโดยไม่รู้ตัว)

**ข้อเสนอ**: (b) หรือ (c) — ยัง**ไม่ตัดสินใจแทน** เพราะกระทบรูปหน้าตาของกราฟ frontier ตรงๆ ต้องให้คุณเลือก

**2. Eligible fund น้อยกว่า 5**

ถ้าผู้ใช้ปรับ toggle บนหน้า 8 จนเหลือ eligible < 5 กอง หน้า Portfolio Optimize (หน้าใหม่) ควรทำยังไง — ตัวเลือก: (a) ทำ frontier ด้วยกองที่มีเท่าที่มี (< 5 ก็ได้ ขั้นต่ำ 2 กอง) พร้อมข้อความเตือน หรือ (b) บล็อกไว้ไม่ให้กดคำนวณ พร้อมบอกให้กลับไปปรับ toggle หน้า 8 ก่อน

**3. วิธี sweep กราฟ frontier**

เสนอ **sweep ตาม target return** (Markowitz แบบดั้งเดิม): `min wᵀΣw` s.t. `μᵀw = target, Σw=1, w≥0 [, w≤cap]` ไล่ `target` จาก return ของ min-variance portfolio ไปถึง `max(ann_return)` ของ 5 กองที่เลือก แบ่งเป็น K จุด (เสนอ **K=20** จุดให้เส้นเรียบพอเห็นทรง) — อีกทางคือ sweep ค่า λ ใน `max(μᵀw − λ·wᵀΣw)` แต่จุดที่ได้จะไม่กระจายทั่วช่วง return สวยเท่า sweep target-return ตรงๆ (บางช่วง λ จุดจะกระจุกกัน) **แนะนำ sweep target-return**

**4. หน้าใหม่นี้คือหน้า 9** — page 8 ถูก Score Screen เอาไปแล้ว (`8_🧭_Score_Screen.py`) เสนอ `pages/9_💼_Portfolio_Optimize.py` (ไม่ชนกับที่มีอยู่ — เช็คแล้วมีแค่หน้า 1-8)

> ✅ **Resolved (2026-09-29, ดู §14)** — ไม่ทำหน้า 9 แล้ว คุณสั่งให้เขียนแผนหน้า 8 ทั้งหน้าใหม่ (§14) ทุกส่วน (เงื่อนไข + ส่วนที่ 1/2/3) อยู่ในไฟล์ `pages/8_🧭_Score_Screen.py` เดิมทั้งหมด ไม่มีไฟล์หน้า 9

**5. Risk model build scope — 313 กองครบ หรือแค่ 5 กองที่เลือก**

แผนเดิม (§6, checklist §9) ตั้งใจ build `build_portfolio_risk_model()` ครบกอง E ทั้ง 313 กอง (เก็บ cache ไว้ reuse) แต่ตอนนี้ต้องการแค่ 5 กองจากหน้า 8 ต่อครั้ง — ถ้า build ครบ 313 กองไว้ล่วงหน้า (เหมือน `build_score_matches` ที่ใช้ ~28-40 วิ) จะ reuse ได้ทุกครั้งที่ผู้ใช้เปลี่ยน toggle หน้า 8 แล้วมาดูหน้า 9 ใหม่ (ไม่ต้อง refit สดทุกครั้ง ตรงกับหลักการ cache ที่ยึดมาตลอดทั้งโปรเจกต์) แต่กินเวลา build ครั้งแรกนานกว่าถ้า build แค่ 5 กอง (fit สดตอนกดปุ่ม ~0.1-0.2 วิ/กอง = เร็วมาก แต่ refit ใหม่ทุกครั้งที่ Top 5 เปลี่ยน) — **แนะนำ build ครบ 313 กองไว้ล่วงหน้าเหมือนแผนเดิม** (เข้ากับ pattern ของทั้งระบบ) แต่ต้องให้คุณ confirm เพราะมีผลกับเวลารอตอน build cache ครั้งแรก

**6. ข้อมูลย้อนหลังสำหรับ factor covariance (F) ต้อง refresh**

ตัวเลข condition number ที่ validate ไว้ใน §3.3 (665,809 → 1,037 หลัง Ledoit-Wolf) มาจากข้อมูล ณ 2026-09-22 (ช่วง 2021-01-04 → 2026-07-31) — ต้องรันซ้ำกับข้อมูลล่าสุดตอน build จริง (ควรยังใกล้เคียงเดิม เพราะ collinearity ของ MSCI index เป็นโครงสร้าง ไม่ใช่เรื่องช่วงเวลา แต่ควรเช็คซ้ำไม่ใช่เชื่อเลขเก่า)

**7. R² ต่ำของกองใน 5 กองที่เลือกได้ (idiosyncratic risk สูง) — ต้องโชว์คู่กับกราฟเสมอ**

ตามหลักที่ตกลงไว้ใน §11.2 — กองที่ joint28 R² ต่ำ (fit เข้ากับ 28-factor ไม่ดี เช่นกองที่เอียง sector เฉพาะทางมาก) จะมี D (idiosyncratic) ใหญ่ ทำให้ optimizer มองว่า "เสี่ยงเกินจะอธิบายได้" และอาจ underweight ทั้งที่จริงอาจแค่ fit ไม่เข้ากับ factor set — ต้องโชว์ R² ของ 5 กองที่เลือกควบคู่กับกราฟ/ตารางน้ำหนักเสมอ ไม่ปล่อยให้ตัวเลขน้ำหนักดูเหมือนคำแนะนำที่แน่นอน

### 13.2 UI ที่เสนอ (หน้า 9 ใหม่ — ปรับจาก §8 เดิมให้ตรงกับ "มาจากหน้า 8" แทน multiselect เอง)

1. **แหล่งกองทุน**: ไม่มี multiselect เอง — ดึง Top 5 eligible จากหน้า 8 อัตโนมัติ (ต้องส่ง state ข้ามหน้า หรือให้ผู้ใช้ตั้ง toggle ซ้ำบนหน้า 9 เอง — เป็นรายละเอียด implementation ที่ยังไม่ตัดสินใจ ดู 13.1)
2. **คำเตือนกลางหน้า (ไม่ใช่ footnote)**: ann_return มี annualization bias, Σ มาจาก factor model ไม่ใช่ observed correlation ตรงๆ, ผลลัพธ์ไม่ใช่คำแนะนำการลงทุน
3. **กราฟ efficient frontier**: แกน x = ann vol ของพอร์ต, แกน y = ann return ของพอร์ต, เส้น = K จุดจาก sweep (13.1.3) + จุด equal-weight เป็น baseline เทียบ + จุดกองเดี่ยวทั้ง 5 กอง (scatter) ให้เห็นว่า diversification ช่วยลด risk ได้แค่ไหน
4. **เลือกจุดบนเส้น → โชว์ตารางน้ำหนักของจุดนั้น** + risk contribution ต่อกอง (bar chart ตาม §8 เดิม) + R² ของแต่ละกอง (ข้อ 13.1.7)

### 13.3 Checklist ก่อนเขียนโค้ดจริง (แทนที่ checklist เดิมของ §9 สำหรับรอบนี้)

- [ ] **Max weight cap สำหรับ N=5** (13.1.1) — เลือก (a)/(b)/(c)
- [ ] **Eligible < 5 กอง** จะทำยังไง (13.1.2)
- [ ] **Sweep แบบ target-return** (13.1.3) confirm K=20 จุด
- [x] **หน้า 9** (13.1.4) — **resolved: ไม่ทำหน้า 9 อยู่หน้า 8 เดิมตาม §14** (ดูหมายเหตุ resolved ที่ 13.1.4 ด้านบน)
- [ ] **Risk model build scope 313 กองครบ vs 5 กองสด** (13.1.5) confirm
- [ ] Build `build_portfolio_risk_model()` จริงกับกอง E ทั้ง 313 กอง (ถ้าเลือกข้อ 13.1.5 = ครบ) เช็คเวลารัน + ไม่มีกองไหน R²/idio_var ผิดปกติ
- [ ] เช็ค optimizer scipy convergence ทุกจุดบน sweep (K จุด) รวมกรณี N<5
- [ ] รัน `pytest -q` ยืนยันไม่กระทบหน้า 1-8 เดิม
- [ ] วิธีส่ง Top 5 + toggle จากหน้า 8 ไปหน้า 9 (session state / query param / ให้ผู้ใช้ตั้งซ้ำ) — รายละเอียด implementation

---

## 14. หน้า 8 — สเปกรวมล่าสุด (3 ส่วน, แทนที่ §12.11 + §13, เขียนใหม่ทั้งหน้า 2026-09-29)

> ✅ **implement แล้ว 2026-09-29** — ส่วนที่ 2 (Top 5 ที่ผ่านเกณฑ์) และส่วนที่ 3 (efficient frontier) อยู่ใน
> `pages/8_🧭_Score_Screen.py` · คณิตอยู่ที่ `analysis/portfolio.py` · risk model ที่ `data_access.portfolio_risk_model`
> · กราฟที่ `viz.frontier_chart` · test ที่ `tests/test_portfolio.py` (85 ผ่าน) · เอกสาร `docs/pages/8-score-screen.md`
> (จำนวน test ตอนนั้น — ปัจจุบันดู §22)
> ผลรันจริง (toggle ค่าเริ่มต้น): 5 กอง fit 2.6 วิ · enumerate 213,876 ชุด + Pareto 0.07 วิ -> frontier 1,178 จุด
> · ช่วงความเสี่ยง 8.6%-12.5% · จุด min-variance 30/30/5/5/30 (risk 8.6% · Π 2.2%) เทียบ equal weight (10.3% · 3.1%)
> การตัดสินใจที่ต่างจากสเปกเดิมในหัวข้อนี้: γ คงที่ 2.5 (§15 + ยืนยัน 2026-09-29) · หน้าต่าง 3 ปีทั้ง B/Σ/vol ·
> เตือนแทนการคำนวณเมื่อกองผ่านเกณฑ์ < 4 (**ภายหลัง §20: < 3 · เพดาน 40%**) · ตาราง Part 2 โชว์ทั้ง ann_return/ann_vol และ Π/vol 3 ปี
> ตัวเลขผลรันในกล่องนี้เป็นของชุด 5 กองก่อน §19/§20 — ผลล่าสุดดู §21
> โครง: **เงื่อนไข (3 toggle) + ส่วนที่ 1 (คะแนนโซน) ไม่เปลี่ยนจากเดิม** — เปลี่ยนแค่ **ส่วนที่ 2** (Top 20 → Top 5 เท่านั้น) และเพิ่ม **ส่วนที่ 3 ใหม่** (efficient frontier)
> **อัปเดต (คุยต่อในวันเดียวกัน)**: เปลี่ยนวิธีสร้าง frontier จาก "sweep target-return ผ่าน scipy.optimize" เป็น **grid enumeration** (ผู้ใช้เสนอ: min weight 5%, max weight 30%, ขยับทีละ 1%, ลองทุก combination ที่ผ่านเงื่อนไข) — validate แล้วด้วยข้อมูลจริง ดีกว่าวิธีเดิม เพราะไม่ต้องพึ่ง solver เลย (ตัดปัญหา scipy convergence ที่เคยกังวลไว้ทิ้งไปทั้งหมด) และ constraint 5%-30% กับ 5 กองไม่ชนปัญหา degenerate แบบที่ cap 20% เคยชนมาก่อน

### 14.1 เงื่อนไข / ตัวควบคุม (ไม่เปลี่ยนจาก §12.11)

| Control | ตัวเลือก | ผลกระทบ |
|---|---|---|
| Country index universe | All (18 ตัว) / VIF-cleaned (11 ตัว) | เปลี่ยนขนาด matrix ส่วนที่ 1 และ primary/secondary ที่ใช้คำนวณ score กอง (มีผลถึงส่วนที่ 2 และ 3 ด้วย เพราะ Top 5 มาจาก score นี้) |
| Matching mode | Primary + Secondary / Primary only | ปิด/เปิด secondary fallback ตอนกรองความซ้ำ — มีผลว่ากองไหน "ผ่านเกณฑ์" ได้บ้าง |
| Diversification | AND (ใหม่ทั้ง country และ sector) / OR (ใหม่อย่างใดอย่างหนึ่ง) | เกณฑ์ eligibility ตอนกรองความซ้ำ |

sector ใช้ครบ 10 ตัวเสมอ ไม่มีตัวเลือก (เหมือนเดิม)

### 14.2 ส่วนที่ 1 — คะแนนโซน country × sector (ไม่เปลี่ยนจากเดิม)

> ⚠️ **สูตรคะแนนโซนถูกแทนที่โดย §12.14 (แผนแก้ 2026-09-30 — ยังไม่ implement): return 12-1 ÷ realized vol แทน อันดับ return × อันดับ GARCH** · โครงสร้างหน้า/heatmap ยังเหมือนเดิม

Heatmap `score_matrix(country, sector)` ขนาด 18×10 หรือ 11×10 ตาม toggle + expander ตารางคะแนนรายดัชนี (return/vol แยกกัน) — โค้ดเดิม `viz.score_heatmap()` ใช้ต่อได้ ไม่ต้องแก้

### 14.3 ส่วนที่ 2 — Top 5 สำหรับ Efficient Frontier (เปลี่ยนจาก Top 20 → Top 5 **ที่ผ่านเกณฑ์เท่านั้น**)

รัน pipeline เดิมทั้งหมด (`fund_scores` → `greedy_select`) แต่**ตัดให้เหลือแค่ 5 แถวแรกที่ `eligible=True`** (ไม่เอาแถว `fill` มาโชว์เลย) เพราะกองที่ไม่ผ่านเกณฑ์กระจายความเสี่ยงไม่ควรถูกเอาไปทำ efficient frontier ด้วย

**คอลัมน์ที่โชว์**: `#, FundCode, FundName, score, ใช้คู่ (primary/secondary), used_country, used_sector, country_r2, sector_r2, ann_return, ann_vol`

**กรณี eligible < 5**: โชว์เท่าที่มี พร้อมข้อความเตือน เช่น "ผ่านเกณฑ์แค่ N กอง (< 5) — Efficient frontier ส่วนที่ 3 จะใช้ N กองนี้" — ไม่เติม fill แทน

**กรณี eligible < 2** (⚠️ implement จริงใช้ `PORTFOLIO_MIN_FUNDS` = 4 แล้วลดเป็น 3 ใน §20 — ไม่ใช่ 2): ทำ frontier ไม่ได้ (ต้องมีอย่างน้อย 2 กองถึงจะมีอะไรให้กระจายระหว่างกัน) → ซ่อนส่วนที่ 3 ไปเลย พร้อมบอกให้ปรับ toggle

### 14.4 ส่วนที่ 3 — Efficient Frontier แบบ Grid Enumeration (วิธีใหม่ — validate แล้ว)

#### 14.4.1 หลักการทำงาน

แทนที่จะแก้ optimization ต่อเนื่องด้วย solver (scipy) — **ลองทุกพอร์ตที่เป็นไปได้จริงตามกฎการซื้อ** แล้วดูว่าอันไหนดีที่สุด:

1. แต่ละกองในหมื่น 5 กอง (หรือ N กองถ้า eligible < 5) ต้องถือน้ำหนักเป็นจำนวนเต็ม % ระหว่าง **min_weight (เสนอ 5%)** ถึง **max_weight (เสนอ 30%)** ขยับทีละ **step (เสนอ 1%)** (ภายหลัง 40% — §20)
2. Enumerate ทุก combination ของน้ำหนัก (w1,...,wN) ที่ผ่านเงื่อนไขข้อ 1 **และ** รวมกันได้ 100% เป๊ะ
3. คำนวณ `risk = √(wᵀΣw)` และ `return = μᵀw` ของทุก combination (Σ, μ จาก risk model §3 — เหมือนเดิมไม่เปลี่ยน)
4. หา **Pareto frontier**: เรียง combination ตาม risk จากน้อยไปมาก แล้วไล่หาจุดที่ return เป็น "running max" ใหม่ทุกครั้ง (จุดที่ risk สูงกว่าแต่ return ไม่มากกว่าจุดก่อนหน้า = ไม่ efficient ตัดออก) — จุดที่เหลือคือ efficient frontier ตัวจริง

**ทำไมดีกว่าวิธี sweep+solver เดิม**:
- ไม่ต้องเพิ่ม dependency/ความซับซ้อนของ `scipy.optimize` เลยสำหรับ feature นี้ (ตัด §5/§6 เดิมส่วน optimizer ทิ้งไปได้ทั้งหมด สำหรับ use case นี้) — ไม่มีปัญหา convergence ให้กังวล เพราะเป็นการนับตรงๆไม่ใช่ solve
- น้ำหนักที่ได้เป็นจำนวนเต็ม % เสมอ (5%, 6%, ..., 30%) ตรงกับที่คนจะซื้อขายจริง ไม่ใช่ทศนิยมแปลกๆแบบที่ solver ให้
- constraint 5%-30% กับ 5 กอง **ไม่ชนปัญหา degenerate** แบบที่ cap 20% เดิมเคยชน (20%×5=100% พอดี บีบเป็น equal-weight บังคับ) — เพราะ min×N=25% ≤ 100% ≤ max×N=150% มี slack ให้ปรับจริง

**ทดสอบจริงแล้ว (N=5, min=5%, max=30%, step=1%, ใช้ Σ/μ สมมติทดสอบความเร็ว — ยังไม่ใช่ Σ จริงจาก risk model)**:

| | ผลทดสอบ |
|---|---|
| จำนวน combination ที่ผ่านเงื่อนไขทั้งหมด | **213,876** |
| เวลา enumerate (Python loop ตรงๆ) | 1.12 วินาที |
| เวลาคำนวณ risk/return ของทุก combo (numpy vectorized) | **0.01 วินาที** |
| จำนวนจุดที่อยู่บน Pareto frontier จริง | **92 จุด** |

สรุป: เร็วมาก ไม่ต้องห่วงเรื่อง performance เลย ทำสดตอนกดปุ่มได้โดยไม่ต้อง cache ผลลัพธ์ของ combination (แค่ต้อง cache risk model B/F/D ไว้ล่วงหน้าตาม §3 เดิม ไม่เกี่ยวกับส่วนนี้)

#### 14.4.2 Input / Output / การตีความ (คำอธิบายเดิมยังใช้ได้ แค่เปลี่ยนวิธี "หา" จุดบนเส้น)

**Input**: μ (`ann_return` ต่อกอง, มี bias ต้องเตือน) · Σ (จาก B·F·Bᵗ+D §3, ไม่ใช่ correlation จาก NAV ตรงๆ) · เงื่อนไขน้ำหนัก (min/max/step)

> ⚠️ **ส่วน μ ด้านบนถูกแทนที่แล้ว — ดู §15** (μ เปลี่ยนจาก `ann_return` เป็น Black-Litterman Implied Return, Σ/vol เปลี่ยน window เป็น 1 ปี) ข้อความ Input นี้เป็นของเดิมก่อน §15 เก็บไว้เป็นประวัติเท่านั้น อย่า implement ตามนี้ตรงๆ

**Output**:
- **จุด scatter สีจางทั้ง 213,876 จุด** (หรือเท่าที่ enumerate ได้ตาม N จริง) — ใช้ `go.Scattergl` (WebGL) ให้ plot จุดจำนวนมากได้ลื่น — โชว์ "พื้นที่ความเป็นไปได้ทั้งหมด" ให้เห็นภาพรวม
- **เส้น/จุดสีเข้มทับไว้ = 92 จุดบน Pareto frontier** (efficient frontier ตัวจริง)
- จุด scatter ของกองเดี่ยวทั้ง N กอง (ที่ ann_vol, ann_return จริง) ทับไว้เทียบ
- จุด equal-weight portfolio (baseline) ทับไว้ด้วย
- คลิก/เลือกจุดบน frontier → โชว์ตารางน้ำหนัก (จำนวนเต็ม %) ของจุดนั้น + risk contribution ต่อกอง + R² ต่อกอง

**การตีความ**: เหมือนที่อธิบายไปก่อนหน้า — จุดในกลุ่มเมฆ (cloud) ที่ไม่อยู่บนเส้นคือพอร์ตที่ "ทำได้" แต่ "ไม่ efficient" (มีทางเลือกที่ดีกว่าเสมอที่ risk เท่ากันหรือต่ำกว่า) ระยะห่างระหว่างขอบซ้ายของกลุ่มเมฆกับเส้นตรงที่ลากระหว่างจุดกองเดี่ยว บอกว่า diversification ช่วยได้แค่ไหน จุดซ้ายสุดของ frontier = พอร์ต min-variance ภายใต้ constraint น้ำหนักที่ตั้งไว้ ไม่มีจุดไหนบนเส้น frontier "ดีที่สุดสัมบูรณ์" ขึ้นกับ risk appetite ผู้ใช้เลือกเอง

#### 14.4.3 UI ที่เสนอ

1. **ตัวเลือกเงื่อนไขน้ำหนัก** (ปรับได้ผ่าน UI): min weight (default 5%), max weight (default 30%), step (default 1%) — ต้องเช็ค feasibility ก่อนรัน (`min×N ≤ 100 ≤ max×N` ไม่งั้น enumerate ได้ 0 combination — เตือนผู้ใช้ทันทีถ้าตั้งค่าที่เป็นไปไม่ได้) (ภายหลัง 40% — §20)
2. คำเตือนกลางหน้า (ก่อนกราฟ): ann_return bias, Σ มาจาก factor model, ไม่ใช่คำแนะนำการลงทุน
3. กราฟ scatter cloud + frontier ตาม 14.4.2
4. เลือกจุดบนเส้น (dropdown/คลิก) → ตารางน้ำหนัก + risk contribution + R² ต่อกอง

#### 14.4.4 ประเด็นที่ยังไม่ตัดสินใจ (เหลือน้อยลงมากจากวิธีเดิม — grid enumeration ตัดปัญหา cap/K/solver ทิ้งไปแล้ว)

1. **min/max/step ควรเป็นค่าคงที่ (5%/30%/1%) หรือปรับผ่าน UI ได้** — เสนอปรับได้ (ผู้ใช้อาจอยากลองเงื่อนไขอื่น) แต่ default ตามที่เสนอวันนี้
2. **Risk model build scope** — build `build_portfolio_risk_model()` (joint 28-factor + Ledoit-Wolf + idio) ครบกอง E 313 กองไว้ล่วงหน้าเป็น cache (reuse ได้ทุกครั้งที่ toggle เปลี่ยนแล้ว Top 5 เปลี่ยน) หรือ refit สดแค่ N กองที่เลือกทุกครั้ง — **แนะนำ build ครบ 313 กอง** ตาม pattern cache ทั้งระบบที่ผ่านมา (เสียเวลา build ครั้งแรกครั้งเดียว)
3. ต้องรัน Ledoit-Wolf shrinkage ซ้ำกับข้อมูลล่าสุด (ตัวเลข condition number 665,809→1,037 ใน §3.3 มาจากข้อมูล ณ 2026-09-22 ต้อง refresh ก่อนเชื่อเลขเดิม)
4. จะ plot cloud ทั้ง 213,876 จุดจริง หรือ downsample เพื่อความเร็ว/ความสวยของกราฟ (เสนอ plot ครบ เพราะทดสอบแล้วเร็วพอ — `go.Scattergl` รับจุดระดับแสนได้สบาย)

### 14.5 Checklist ก่อนเขียนโค้ดจริง

- [x] min/max/step น้ำหนัก — **ปรับผ่าน UI ได้** (ค่าเริ่มต้น 5%/30%/1%) พร้อมเช็ค feasibility ก่อนรัน (ภายหลัง: เพดาน 40% §20 · step ต้องหาร 100 ลงตัว §22)
- [x] Risk model build scope — **fit สดเฉพาะกองที่เลือก** (ไม่ build 313 กอง) เพราะ Σ ผูกกับหน้าต่าง rolling
      cache ลงดิสก์จะเก่าทันทีที่ข้อมูลขยับ · ใช้ `@st.cache_data` กันคำนวณซ้ำระหว่าง rerun
- [x] Build จริง + Ledoit-Wolf กับข้อมูลหน้าต่าง 3 ปี — √diag(Σ) ใกล้ ann vol จริง (เช่น 0.241 vs 0.243) ⚠️ **ยกเฉพาะกองที่บังเอิญใกล้** — กองอื่นต่าง 0.4–2.2 pp (§22)
- [x] ทดสอบ grid enumeration กับ Σ/μ จริง — 213,876 ชุด · 0.07 วิ · frontier 1,178 จุด
- [x] รัน `pytest -q` — 85 ผ่าน (เพิ่ม `tests/test_portfolio.py` 11 ตัว) ไม่กระทบหน้า 1-7 (ภายหลัง: 86 → 92 → 93 → 96 ตาม §18-§22)

### 14.6 ช่วงข้อมูล (lookback window) สำหรับ μ/Σ — ตัดสินใจแล้ว (2026-09-29)

> ⚠️ **ถูกแทนที่แล้ว (2026-09-29 เช่นกัน)** — เปลี่ยนใจจาก expanding window เป็น fixed rolling 3 ปีแล้ว (ดูเหตุผล/ตัดสินใจล่าสุดที่ **§14.7**) เก็บหัวข้อนี้ไว้เป็น record ว่าทำไมตอนแรกเลือก expanding และทำไมเปลี่ยนใจทีหลัง

**คำถาม**: rebalance ทุก 3 เดือน ควรใช้ข้อมูลย้อนหลังกี่ปีมาคำนวณ expected return (μ) และ covariance matrix (Σ) ที่ใช้ใน efficient frontier?

**ข้อสรุปสำคัญก่อนตัดสินใจ**: ความถี่ rebalance (3 เดือน) กับช่วงข้อมูลที่ใช้คำนวณ (lookback window) เป็นคนละเรื่องกัน — ไม่ควรใช้ข้อมูลแค่ 3 เดือนล่าสุดมาประมาณ μ/Σ (63 วันทำการ น้อยเกินไป ค่าเฉลี่ย/correlation จะสุ่ม/เพี้ยนสูงมาก) 3 เดือนคือแค่ "ความถี่ที่รันคำนวณใหม่" ไม่ใช่ "ปริมาณข้อมูลที่ป้อนให้แต่ละครั้ง"

**ตรวจ convention เดิมของระบบก่อนตัดสินใจ** (grep จริงจาก config.py/data_access.py):
- `DATA_START = "2021-01-01"` — ข้อมูล MSCI มีถึงตอนนี้ ~5.5 ปี
- `ann_return`/`ann_vol` ที่แสดงทั่วทั้ง dashboard (data_access.py:122-123) และ regression หา B (country/sector exposure, ผ่าน `matching.build_fund_returns`) **ไม่มีการตัด window เลย** — ใช้ข้อมูลทุกจุดที่มีตั้งแต่ 2021-01-01 ถึงล่าสุดเสมอ (expanding, ไม่ใช่ rolling)

**ตัดสินใจ**: ใช้ **expanding window จาก 2021-01-01** สำหรับ μ/Σ ของ efficient frontier ด้วย — สอดคล้องกับ convention เดิมทั้งระบบ (ไม่สร้างมาตรฐานที่สองขึ้นมาแยกกัน) และเหมาะกับสถานะข้อมูลตอนนี้ที่มีรวมแค่ ~5.5 ปี (ตัดเป็น rolling window สั้นกว่านี้จะเสียข้อมูลที่มีจำกัดอยู่แล้วไปเยอะ) ทุกไตรมาสที่ rebalance ใหม่ ช่วงข้อมูลจะยาวขึ้นเรื่อยๆตามเวลาที่ผ่านไป ไม่ตัดข้อมูลเก่าทิ้ง

**ทบทวนใหม่ในอนาคต**: ถ้าข้อมูลสะสมยาวขึ้นมาก (เช่น 8-10 ปีขึ้นไป) หรือเจอ regime change ชัดเจน (เช่นวิกฤตตลาดรอบใหม่) ควรกลับมาพิจารณา fixed rolling window อีกครั้ง เพื่อไม่ให้ข้อมูลเก่ามากๆ (เช่นช่วง COVID recovery ปี 2021) มีน้ำหนักเท่าข้อมูลปัจจุบันตลอดไป — ไม่ใช่การตัดสินใจตายตัวถาวร

**เพิ่มเติม (ย้ำจาก §14.4.2)**: ไม่ว่าจะเลือก window แบบไหน historical mean return ก็ยังมี bias เป็น estimator ของ "expected return ในอนาคต" อยู่ดี (window ช่วยเรื่อง noise/ความนิ่งของค่า แต่ไม่แก้ปัญหานี้) — ต้องมีคำเตือนบนหน้าจอตามที่วางแผนไว้แล้ว

### 14.7 ช่วงข้อมูลสำหรับ μ/Σ — เปลี่ยนเป็น Fixed Rolling 3 ปี (ตัดสินใจล่าสุด 2026-09-29, แทนที่ §14.6)

**เปลี่ยนใจจาก §14.6**: จาก expanding window (2021-01-01 → ล่าสุด, ยาวขึ้นเรื่อยๆ) เป็น **fixed rolling window 3 ปีล่าสุดเสมอ**
ทุกไตรมาสที่ rebalance/predict ใหม่ ให้ตัดข้อมูลที่เก่ากว่า 3 ปีก่อนหน้า "ณ วันที่คำนวณ" ทิ้ง ใช้แค่ ~756 วันทำการล่าสุด (252×3)

**เหตุผลที่เปลี่ยน**: ต้องการให้ μ/Σ สะท้อน regime ตลาดปัจจุบันมากกว่า ไม่อยากให้ข้อมูลปี 2021 (ช่วง COVID recovery)
มีน้ำหนักเท่าข้อมูลตอนนี้ตลอดไปแบบที่ expanding window จะเป็น (ตามที่เกริ่นไว้เป็นข้อเสียของ expanding ใน §14.6 เดิม)

**ขอบเขตการเปลี่ยน (สำคัญ — ตัดสินใจแล้ว)**: ใช้ fixed rolling 3 ปี **เฉพาะกับ μ/Σ ของ portfolio risk model ส่วนใหม่เท่านั้น**
(สำหรับ efficient frontier ใน §14.4) — **ไม่แก้** `ann_return`/`ann_vol`/regression B ที่มีอยู่แล้วทั่ว dashboard (ตารางอื่นๆ,
ส่วนเงื่อนไข/score matrix ของหน้า 8 เอง) สิ่งเหล่านั้นยังเป็น expanding window ตาม convention เดิมของระบบต่อไป
ไม่เปลี่ยนแปลง — เหมือน pattern การขอบเขตของการแก้ secondary band (§12.12) ที่ผ่านมา คือแก้เฉพาะจุดที่ตกลงกัน
ไม่กระทบส่วนอื่นที่ไม่ได้ถูกขอให้แก้

**ผลกับ implementation** (เมื่อถึงตอนเขียนโค้ดจริง):
- `build_portfolio_risk_model()` (ฟังก์ชันใหม่ที่ยังไม่เขียน) ต้องรับ "as-of date" และตัด return series ของแต่ละกอง/factor
  ให้เหลือแค่ 3 ปีล่าสุดนับจากวันนั้น ก่อนส่งเข้า joint 28-factor regression + Ledoit-Wolf shrinkage + idiosyncratic variance
- กองที่มีประวัติสั้นกว่า 3 ปี (กองเปิดใหม่) ใช้เท่าที่มี (เหมือน guard `MIN_REGRESSION_OBS` ที่มีอยู่แล้วในระบบ) ไม่ error
- ต้องมี config constant ใหม่แยกจาก `DATA_START` เดิม เช่น `PORTFOLIO_RISK_LOOKBACK_YEARS = 3` (ชื่อจริงค่อยตั้งตอนเขียนโค้ด)
- Ledoit-Wolf condition number ที่เคยทดสอบ (665,809 → 1,037) วัดจากข้อมูล ~5.5 ปี ต้อง**รันใหม่กับ 3 ปีล่าสุด**เท่านั้น
  ถึงจะเชื่อได้ (ข้อมูลน้อยลง covariance อาจ ill-conditioned กว่าเดิม ยังไม่รู้ตัวเลขจริงจนกว่าจะลองกับข้อมูล 3 ปี)

**Checklist §14.5 ที่ต้องปรับ**: รายการ "Ledoit-Wolf/condition number ยังโอเคกับข้อมูลล่าสุด" ต้องทดสอบด้วยข้อมูล
**trailing 3 ปี** โดยเฉพาะ (ไม่ใช่ทั้งหมด 5.5 ปีแบบที่ทดสอบไปก่อนหน้า)

## 15. μ methodology — เปลี่ยนเป็น Black-Litterman Implied Return + สรุป window สุดท้าย (2026-09-29)

> ⚠️ **ถูกแทนที่แล้ว** — ส่วน μ ของ §14.4.2 (ที่เคยบอกว่า μ = ann_return จาก historical mean, มี bias) และ window ของ
> §14.6 (expanding) / §14.7 (fixed rolling 3 ปี) ถูกแทนที่ทั้งคู่ ด้วยการตัดสินใจสุดท้ายด้านล่างนี้ (คุยต่อวันเดียวกัน 2026-09-29)

### 15.1 สรุปสุดท้าย: μ, Σ, volatility
> ⚠️ หัวข้อนี้ชื่อ "สรุปสุดท้าย" แต่ถูกแก้ต่ออีกหลายรอบ — ค่าที่ใช้จริง: หน้าต่าง 756 วัน · γ = 2.5 คงที่ · Π = γΣ_sys·(1/N) (§15.3, §18.1, §19)

- **Σ, volatility**: fixed rolling window **1 ปีล่าสุดเสมอ** (เปลี่ยนจาก 3 ปีใน §14.7 อีกครั้ง) — ทุกไตรมาสที่ rebalance
  ⚠️ **ถูกแทนที่ (§15.3/§18.1)** — หน้าต่างสุดท้ายคือ 756 วัน (~3 ปี) ไม่ใช่ 1 ปี
  ตัดข้อมูลเก่ากว่า 1 ปีก่อนหน้า "ณ วันคำนวณ" ทิ้ง ใช้ ~252 วันทำการล่าสุดเท่านั้น
- **μ**: เลิกใช้ historical ann_return แล้ว — เปลี่ยนเป็น **Black-Litterman Implied Return (Reverse Optimization)**:
  - สูตร: Π = γ × Σ × W_market
  - ⚠️ **ถูกแทนที่โดย §19** — W_market จาก AUM เปลี่ยนเป็น w_ref = 1/N และ Π ใช้ Σ_sys (ไม่รวม D) แทน Σ เต็ม
  - **W_market** = AUM ของกองนั้น ÷ AUM รวมของ Top 5 ที่เลือกมา (ข้อมูลมีอยู่แล้ว — ใช้ `aum` field เดิมที่มีอยู่ใน
    data_access.py ไม่ต้องหาข้อมูลใหม่)
  - **γ (risk aversion)** = (ผลตอบแทนตลาด − r_f) ÷ variance ของตลาด — "ตลาด" ใช้ **MSCI_ACWI** (มีอยู่แล้วในระบบ,
    ⚠️ **ถูกแทนที่ (§15.3/§17.5)** — γ ใช้ค่าคงที่ 2.5 ไม่ถอดจาก ACWI/r_f ไทย
    เป็น THB สอดคล้องกับ NAV) ส่วน **r_f ใช้ Thai risk-free rate** (ตัดสินใจแล้ว — ไม่ใช่ US ตามที่เสนอมาทีแรก
    เพราะทั้งระบบคำนวณเป็น THB หมด ต้องใช้ r_f สกุลเดียวกันเพื่อไม่ให้ γ บิดเบือนจาก currency mismatch)
  - ⚠️ **ข้อนี้ถูกยกเลิกโดยตั้งใจใน §19** — Π ใช้ Σ_sys ส่วน frontier ใช้ Σ เต็ม (ผลที่ตามมาดู §21.2)
  - **Σ ในสูตรนี้ต้องเป็น Σ ใบเดียวกัน** กับที่ใช้ตอน grid enumeration หา efficient frontier (ยืนยันแล้ว) — ตาม
    หลัก Black-Litterman: W_market ต้อง "optimal" ภายใต้ Σ ตัวเดียวกันที่ใช้ถอด Π กลับมา ถ้าใช้ Σ คนละใบตรรกะจะพัง

### 15.2 ข้อสำคัญที่เพิ่งถูกเตือน — จำนวน factor ของ B/F/D ต้องตามเงื่อนไข toggle ของหน้า 8 (ไม่ fix 28 เสมอ)

เดิมเรียก risk model ว่า "joint 28-factor regression" (18 country + 10 sector) แบบตายตัว — แต่หน้า 8 มี toggle
"country universe" อยู่แล้วตาม §14.1 (full 18 ดิบ vs VIF-cleaned 11) เพราะฉะนั้น B/F/D ของ portfolio risk model
**ต้องใช้จำนวน factor ตามที่ toggle เลือกไว้จริง ณ ตอนนั้น ไม่ตายตัวที่ 28**:

- ถ้า user เลือก VIF-cleaned (11 country) → total factor = 11 + 10 sector = **21 factor**
- ถ้า user เลือก full (18 country) → total factor = 18 + 10 sector = **28 factor**

`build_portfolio_risk_model()` (ยังไม่เขียนโค้ด) ต้องรับ country-universe ปัจจุบันของหน้าเป็น parameter เพื่อเลือกชุด
factor ให้ตรงกับที่ใช้คัด Top 5 มา — ไม่ให้ Top 5 มาจาก matching แบบหนึ่ง (เช่น VIF-cleaned) แต่ risk model ไปคำนวณ
ด้วย factor set อีกแบบ (full 18) ซึ่งจะไม่สอดคล้องกัน

### 15.3 Checklist เพิ่มจาก §14.5

- [x] Thai risk-free rate proxy — **ตัดสินใจแล้ว: BOT policy rate** (ดอกเบี้ยนโยบายธนาคารแห่งประเทศไทย)
      ยังต้องหา/นำเข้าข้อมูล historical series จริงก่อนเขียนโค้ด (BOT ประกาศเป็นขั้นบันได เปลี่ยนเฉพาะวันที่มีมติ กนง.
      ไม่ใช่ daily series ต่อเนื่องแบบ MSCI index — ต้อง forward-fill ระหว่างวันประชุมตอนใช้จริง)
- [x] `portfolio_risk_model()` รับ country-universe เป็น parameter แล้ว (21 หรือ 28 factor ตาม toggle)
- [x] หน้าต่างสรุปสุดท้าย = **3 ปี** (ไม่ใช่ 1 ปีตาม §15.1 เดิม — ยืนยัน 2026-09-29 ให้ B/Σ/vol ใช้หน้าต่างเดียวกัน)
- [x] คำเตือนบนหน้าจอเปลี่ยนเป็นเรื่องสมมติฐาน "ตลาดอยู่ในดุลยภาพ" ของ Black-Litterman แล้ว (ไม่ใช่ bias ของ historical mean)
- [x] γ — ใช้ค่าคงที่ 2.5 จึง **ไม่ต้องใช้ r_f ไทย/BOT policy rate** อีกต่อไป (ตัดงานหาข้อมูลชุดนั้นทิ้ง)

## 16. Plan review (2026-09-29) — 4 จุดที่พบระหว่างทวนแผนทั้งไฟล์ทวนกับโค้ดจริง

> ที่มา: คุณขอ "ช่วยทำ plan review หน่อย และตอนนี้หน้า 8 ที่ทำมาถึงขั้นไหนแล้ว" — ทวนเอกสารทั้งไฟล์ (750+ บรรทัด)
> เทียบกับโค้ดจริงของ `pages/8_🧭_Score_Screen.py` และ `config.py` ทีละจุด

### 16.1 (แก้แล้ว) §14.4.2 ไม่มี flag ชี้ไป §15

เพิ่ม inline flag ไว้ที่ §14.4.2 แล้ว (ดูด้านบนหัวข้อนั้น) — เตือนว่าส่วน μ ในนั้นถูกแทนที่โดย §15

### 16.2 (แก้แล้ว) หน้า 8 vs หน้า 9 ไม่เคย resolve ไว้ตรงๆเป็นข้อความ

เพิ่ม resolution note ที่ §13.1 ข้อ 4 และติ๊ก checklist §13.3 ที่เกี่ยวข้องแล้ว — สรุปคือ **อยู่หน้า 8 เดิม ไม่ทำหน้า 9**

### 16.3 (✅ resolved ใน §17.5/§18.2 — รันของจริงทั้ง 21/28 factor แล้ว) Default toggle ของหน้าจริง (VIF-cleaned 11) ไม่ตรงกับตัวเลขที่ validate ไว้ใน §3 (28 factor)

เช็คโค้ด `pages/8_🧭_Score_Screen.py` บรรทัด radio "Country universe" — ตัวเลือกแรก (= default ของ Streamlit radio)
คือ **"VIF-cleaned (11)"** ไม่ใช่ "ทั้งหมด (18)" แต่ตัวเลขทั้งหมดที่ validate ไว้ใน §3.2 (joint R² ของ 5 กองตัวอย่าง:
K-INDIA 0.785, ABJO 0.732, ABEG 0.516, BCARE 0.752, K-USA-A(A) 0.464) และ §3.3 (Ledoit-Wolf condition number
665,809 → 1,037) **รันด้วย full 28 factor (18 country + 10 sector) ทั้งหมด** — ไม่ใช่ 21 factor (11 country + 10
sector) ที่เป็นค่า default จริงของหน้าตามที่ §15.2 เตือนไว้ว่าต้องเปลี่ยนตาม toggle

**ต้องทำก่อนเขียนโค้ดจริง**: re-run §3.2 (joint R² 5 กองตัวอย่างเดิม) และ §3.3 (Ledoit-Wolf condition number) ด้วย
ชุด **21 factor** แยกเป็นอีกชุดตัวเลข เก็บไว้คู่กับชุด 28 factor เดิม (ไม่ใช่แทนที่ — เพราะผู้ใช้ปรับ toggle ได้ทั้ง 2
แบบ ต้องมีเลขอ้างอิงครบทั้งคู่ก่อนเชื่อว่า risk model ใช้ได้กับทั้ง 2 สถานะของ toggle)

### 16.4 (✅ resolved ใน §14 กล่องสรุป — โชว์ทั้งสองชุด — เป็นคำถาม UI ที่ยังไม่ตัดสินใจ) §14.3 ตารางส่วนที่ 2 ควรโชว์ Π/1yr-vol ใหม่ด้วยไหม

§14.3 กำหนดคอลัมน์ตาราง Top 5 ไว้รวม `ann_return, ann_vol` (ค่า expanding-window เดิม ที่ตกลงไว้ใน §14.7 ว่า
**ไม่แตะ** ยังใช้แสดงทั่วไปในหน้าอื่นต่อไป) — แต่หลัง §15 เปลี่ยนวิธีคำนวณ μ/Σ ที่ Part 3 จะใช้จริง (Black-Litterman
Π + Σ/vol แบบ 1 ปี) เป็นตัวเลขคนละชุดกับ ann_return/ann_vol เดิมไปแล้ว ยังไม่มีการตัดสินใจว่า:

- **(a)** ตาราง Part 2 โชว์แค่ ann_return/ann_vol เดิม (บริบททั่วไป) เท่านั้น — ตัวเลข Π/1yr-vol ที่ Part 3 ใช้จริง
  ไม่ต้องโชว์ในตาราง Part 2 เลย (คำนวณ/ใช้แค่ภายใน Part 3)
- **(b)** เพิ่มคอลัมน์ใหม่ในตาราง Part 2 โชว์ Π (implied return) และ 1yr vol ที่จะเอาไปใช้จริงตอนกด Part 3 ด้วย
  ให้ผู้ใช้เห็นตัวเลขที่ optimizer จะใช้จริงก่อนกดคำนวณ frontier — ตารางจะมี 4 คอลัมน์ตัวเลขผลตอบแทน/ความเสี่ยง
  (ann_return, ann_vol, Π, 1yr-vol) ซึ่งอาจดูรกและสับสนว่าอันไหนคืออันไหน ต้องมี label ที่ชัดมาก

### 16.5 Checklist เพิ่มจากการ review

- [ ] Re-run §3.2/§3.3 ด้วย 21-factor set (VIF-cleaned 11 country) แยกจากตัวเลข 28-factor เดิม (16.3)
- [x] ↑ resolved ด้วยการรัน `portfolio_risk_model` จริงแทน script (§17.5 / §18.1)
- [ ] ตัดสินใจ §14.3 ตาราง Part 2 โชว์ Π/1yr-vol เพิ่มไหม หรือคงแค่ ann_return/ann_vol เดิม (16.4)
- [x] ↑ resolved: ตาราง Part 2 โชว์ทั้ง ann_return/ann_vol และ Π/vol 3 ปี (§14 กล่องสรุป)

## 17. Counter-review จากคุณ (2026-09-29) — 4 จุดที่แก้ plan §16 เพิ่ม

> ที่มา: คุณ peer-review §16 ต่อด้วยตัวเอง เจอ 4 จุดที่ผมมองข้าม/ยังคิดไม่ครบ — บันทึกทั้ง 4 พร้อมผลที่มีต่อแผน

### 17.1 (รับ + ขอปรับคำอธิบายกลไกเล็กน้อย) หน้าต่าง 1 ปีชนกับ B ที่มี 21-28 factor
> ⚠️ **ถูกแทนที่โดย §18.1** — สุดท้ายใช้หน้าต่างเดียว 756 วันทั้ง B/F/vol (ไม่แยก B ยาว / F 1 ปี)

**ข้อสังเกตของคุณ**: 252 obs ต่อ 21-28 parameter ≈ observation/parameter ราว 9-12 เท่า บางเกินไป → R² ดูดีเกินจริง
→ `D=(1−R²)×var` ต่ำเกินจริง → ความเสี่ยงพอร์ตถูกประเมินต่ำกว่าจริง (ทิศทางอันตรายที่สุดสำหรับหน้าที่ให้ตัวเลขน้ำหนัก)

**ขอปรับกลไกอธิบายให้ตรงขึ้นนิดหนึ่ง** (ผลสรุป/ทิศทางอันตรายที่คุณสรุปไว้ถูกต้องทั้งหมด ไม่เปลี่ยน): ตัว shrinkage ของ
ElasticNet เองมีแนวโน้ม**ลด** ค่า coefficient ไม่ใช่ทำให้ R² สูงเกินจริงโดยตรง — ตัวการจริงคือ **in-sample R² มี bias
เป็นบวกเสมอเมื่อ observation/parameter ต่ำ** (โมเดลจับ noise ของ sample นั้นไปด้วยโดยไม่รู้ตัว แม้จะ regularize แล้ว)
ยิ่ง ratio ต่ำ bias นี้ยิ่งแรง — และ cross-validation เองก็ไม่นิ่งเมื่อแต่ละ fold มีข้อมูลน้อย (252/5 fold ≈ 50 obs/fold)
อาจเลือกความแรง regularization ที่ไม่เหมาะสมได้ — **ผลลัพธ์สุดท้ายเหมือนกับที่คุณสรุปไว้**: R² สูงเกินจริง, D ต่ำเกินจริง

**รับข้อเสนอ**: แยก window ตามหน้าที่ของแต่ละส่วน —
- **B (exposure matrix)**: ใช้ window ยาว (obs/param กลับไปสูงเหมือนเดิม เช่น 3 ปี ≈ 756 obs → ratio ~27-36:1)
- **F (factor covariance) + total variance สำหรับ D**: ใช้ 1 ปีตามที่ตัดสินใจไว้ใน §15 (ต้องการให้สะท้อน regime ปัจจุบัน)
- ผลคือ `D = total_var(1yr) × (1 − R²(long-window))` — ใช้ "สัดส่วนที่อธิบายไม่ได้" แบบนิ่ง (จาก window ยาว) คูณกับ
  "ระดับความผันผวนปัจจุบัน" (จาก window สั้น) — เป็นการผสมที่สมเหตุสมผล ไม่ใช่ inconsistency

**⚠️ เปิดคำถามใหม่ที่ยังไม่ตัดสินใจ**: "window ยาว" สำหรับ B ควรเป็น **expanding (§14.6 เดิม)** หรือ **fixed rolling 3 ปี
(§14.7 เดิม)** — ทั้งสองหัวข้อนี้ถูก flag ว่า "ถูกแทนที่แล้ว" ไปตอนที่ §15 รวม window ทั้งหมดเป็น 1 ปี ตอนนี้ B แยกออกมา
ใช้ window ยาวแล้ว ต้องหยิบกลับมาเลือกใหม่ระหว่าง 2 ทางเดิมนั้น (ดูคำถามท้าย section นี้)

### 17.2 (รับเต็มที่) ไม่ build cache risk model ครบ 313 กอง — live-fit เฉพาะ 5 กองที่เลือก, cache แค่ F
> ⚠️ **ถูกแทนที่โดย §17.5/§18.1** — สุดท้ายไม่ cache แม้แต่ F (fit สดทั้ง B/F/D ผ่าน `@st.cache_data`)

**ข้อสังเกตของคุณ**: μ/Σ ผูกกับ as-of date (rolling) และผูกกับ toggle 2 แบบ (21/28 factor) พร้อมกัน — cache ต่อกองครบ
313 กองจะกลายเป็นข้อมูลเก่าทันทีที่วันที่ขยับ (ปัญหาเดียวกับที่เจอใน code review หน้า 7: cache ไม่มี provenance/staleness
tracking) ในขณะที่ fit สดแค่ 5 กองเร็วมากอยู่แล้ว (~0.1-0.2 วิ/กอง ตาม §13.1.5 เดิม)

**รับเต็มที่ — สถาปัตยกรรมที่ได้หลังรับข้อเสนอนี้ (สะอาดกว่าที่คิดไว้เดิมด้วย)**:
- **B, D (ต่อกอง)**: fit สดทุกครั้งเฉพาะกองที่เลือกจริง (5 กอง หรือ N กอง) — ไม่ cache เลย ไม่มีปัญหา staleness เพราะ
  fit ใหม่ตลอด สอดคล้องกับ as-of date ปัจจุบันเสมอ
- **F (factor covariance)**: cache ได้จริง เพราะ**ไม่ขึ้นกับกองที่เลือก** ขึ้นกับ (window, toggle) เท่านั้น — และเพราะ
  window ของ F ตัดสินใจตายตัวไว้แล้วที่ 1 ปี (§15) เหลือแค่ตัวแปรเดียวคือ toggle → **cache แค่ 2 ชุด** (F แบบ 21-factor,
  F แบบ 28-factor) รีเฟรชทุกครั้งที่ข้อมูลใหม่เข้ามา (เช่น รายวัน/รายสัปดาห์ ไม่ต้องรอไตรมาส เพราะเบามาก)
- **ผลคือตัดปัญหา cache staleness/provenance ของกองทั้ง 313 กองทิ้งไปทั้งหมด** เหลือแค่ 2 cache entry ที่เบาและ track
  ง่ายกว่าเดิมมาก — **แทนที่ข้อเสนอเดิมใน §14.4.4.2/§13.1.5 ("build ครบ 313 กอง") ไปเลย**

### 17.3 (รับ — เปิดคำถามคู่กัน) r_f ของไทยเป็นข้อมูลใหม่ทั้งหมด ต้องทำ base_data + forward-fill — คุ้มไหม

**ข้อสังเกตของคุณ**: BOT policy rate ไม่มี API พร้อมใช้แบบ FRED ต้องทำเป็น snapshot ไฟล์ใหม่ใน `base_data/` (ตาม pattern
เดียวกับ style/macro) พร้อม forward-fill ระหว่างวันที่มีมติ กนง. (ไม่ใช่ daily series ต่อเนื่อง) — เป็นงานที่ต้องเผื่อไว้จริง
ใช้แค่จุดเดียวคือสูตร γ ทำให้ต้องกลับไปถามว่าคุ้มกับความซับซ้อนที่เพิ่มไหม

**รับว่าเป็นต้นทุนจริง** — เสนอทางเลือกลดต้นทุนไว้ให้พิจารณา (ยังคงโครงสร้าง Black-Litterman ไว้ ไม่ต้องทิ้งของที่ตัดสินใจ
ไปแล้วทั้งหมด):

- **(a) หา r_f จริงตามเดิม** — ต้นทุนสูงกว่า แต่ γ สะท้อนสภาพตลาด/ดอกเบี้ยจริง ณ เวลานั้น
- **(b) ใช้ γ เป็นค่าคงที่สมมติ** (เช่น γ=2.5, ค่าที่มักอ้างอิงกันในวรรณกรรม Black-Litterman ทั่วไป) — ตัด dependency
  เรื่อง r_f/BOT ทิ้งไปทั้งหมด ไม่ต้องทำ base_data ใหม่ ไม่ต้อง forward-fill — ยังคงสูตร Π=γΣW_market ไว้ทั้งหมด
  (W_market, Σ ไม่กระทบ) แค่ γ ไม่ได้ derive จากตลาดจริงแต่เป็นสมมติฐานคงที่ที่ต้องระบุไว้ตรงๆบนหน้าจอ

### 17.4 (รับ + คำนวณใหม่ให้ตรง) §16.3 ต้อง re-validate 4 ชุดจริง ไม่ใช่แค่เพิ่ม 21-factor เข้าไปอีกชุด

**ข้อสังเกตของคุณ**: หลังรับ 17.1 (แยก window B vs F) ตัวเลข validate ที่ต้องรันใหม่ไม่ใช่แค่ "28-factor เดิม + 21-factor
ใหม่" แต่ต้องคูณกับ window ที่แยกกันด้วย

**ยืนยันคณิตศาสตร์ตรงกับที่คุณว่า — ต้องรันจริง 4 ชุด**:
1. §3.2 (joint R² 5 กองตัวอย่าง) ด้วย **28 factor × window ยาว** (เดิมมีอยู่แล้ว แต่ window ยาวที่ใช้ต้องยืนยันว่าคือ
   แบบไหนตาม 17.1 ก่อน — ถ้าเปลี่ยนจาก "expanding ทั้งประวัติ" เป็น "fixed 3 ปี" ตัวเลขจะไม่เท่าของเดิมด้วย)
2. §3.2 ด้วย **21 factor × window ยาว** (ชุดใหม่ทั้งหมด)
3. §3.3 (Ledoit-Wolf condition number) ด้วย **28 factor × 1 ปี** (ชุดใหม่ — เดิมทดสอบด้วย 5.5 ปีเท่านั้น)
4. §3.3 ด้วย **21 factor × 1 ปี** (ชุดใหม่ทั้งหมด)

### 17.5 Checklist อัปเดต (แทนที่รายการเดิมใน §16.5)

- [x] **เลือก window ยาวสำหรับ B**: ✅ resolved → **ไม่ใช้ทั้ง expanding (§14.6) หรือ fixed-3ปี-เฉพาะ-B (§14.7/17.1)**
      implement จริงใช้ **window เดียว (fixed rolling 756 วัน = 3 ปี) ทั้ง B, F และ vol พร้อมกัน** — ดู §18
- [x] Re-run §3.2/§3.3 แบบ script แยก — ✅ **ไม่ทำแบบเดิม** เพราะไม่จำเป็นแล้ว (เหตุผลดู §18.3) แทนที่ด้วยการรัน
      `data_access.portfolio_risk_model()` จริงกับข้อมูลจริงตรงๆ (สิ่งที่ code จะรันจริงตอนใช้งาน ไม่ใช่ script แยกที่อาจเพี้ยนจากโค้ดจริง)
- [x] **เลือกวิธี γ**: ✅ resolved → **ใช้ค่าคงที่ γ = 2.5** (`config.PORTFOLIO_GAMMA`) — ไม่ต้องหา Thai r_f (17.3 ตัวเลือก b)
- [x] Cache design ใหม่: ✅ resolved → **ไม่ cache ลงดิสก์เลยแม้แต่ F** — fit สด B+F+D ทุกครั้งด้วย `@st.cache_data`
      (memoize ระดับ process ตาม (fund_codes, country_cols) เคลียร์พร้อม cache อื่นทุกตัวตอนกด 🔄 Rebuild — เบากว่าที่ 17.2 เสนอไว้อีก
      เพราะกองที่เลือกมีแค่ ≤5 กอง fit สดทั้ง B และ F ก็ยังเร็วพอ ไม่ต้องแยก cache F ออกมา)

**สถานะ: implement เสร็จแล้วทั้งหมด (2026-09-29) — โค้ดจริงอยู่ที่ `analysis/portfolio.py` +
`data_access.portfolio_risk_model()` + หน้า 8 ส่วนที่ 3 · รายละเอียดสูตร/ผลตรวจจริง → `docs/pages/8-score-screen.md`
(หัวข้อ "ส่วนที่ 3 — Efficient frontier") · ดู §18 สำหรับสรุป code review**

## 18. Implement เสร็จแล้ว + Code review (2026-09-29)

โค้ดจริง (`config.py`, `analysis/portfolio.py`, `tests/test_portfolio.py`, `data_access.py`,
`pages/8_🧭_Score_Screen.py`, `viz.frontier_chart`, `docs/pages/8-score-screen.md`) implement ครบตามที่คุยกันใน
§13-§17 — ผมอ่านโค้ดจริงทั้งหมด (ไม่ใช่เดาจากแผน) แล้วรันจริงกับข้อมูลจริงอีกรอบเพื่อ verify ก่อนสรุปหัวข้อนี้

### 18.1 การตัดสินใจสุดท้าย (ต่างจาก checklist §17.5 บางจุด — เขียนอธิบายว่าทำไม)

| เรื่อง | แผนเดิมคุยไว้ | โค้ดจริงทำ | ทำไมต่างแต่ยังถูก |
|---|---|---|---|
| window ของ B vs F/vol | แยกกัน (§17.1): B ยาว, F/vol 1 ปี | **window เดียว 756 วัน (3 ปี) ทั้ง B, F, vol** | ปัญหาที่ split-window แก้คือ obs:param ต่ำที่ 1 ปี (252/21-28 ≈ 9-12:1) — ใช้ 3 ปีทั้งคู่แก้ปัญหาเดียวกันได้ตรงกว่า (obs:param จริงที่วัดได้ ≈ 16-22:1 ดูข้อ 18.2) **โดยไม่ต้องมี 2 window ให้จัดการ** — ง่ายกว่า ไม่ได้เสียอะไร |
| γ | เปิดคำถาม: derive จาก Thai r_f หรือคงที่ (§17.3) | **คงที่ 2.5** | ตัดปัญหา "ต้องหาข้อมูล r_f ไทยที่ไม่มีในระบบ" ทิ้งทั้งหมด ตรงกับตัวเลือก (b) ที่เสนอไว้ |
| cache | cache แค่ F (2 ชุดตาม toggle), live-fit B/D (§17.2) | **ไม่ cache ลงดิสก์อะไรเลย** — fit สด B+F+D ทุกครั้ง ผ่าน `@st.cache_data` (memoize ใน process เท่านั้น) | กองที่เข้า frontier ≤5 กองเสมอ (`PORTFOLIO_TOP_N`) — fit ทั้ง B และ F สดใช้เวลา ~2.6 วิ (วัดจริง) เร็วพอไม่ต้องแยก cache F ออกมาให้ซับซ้อนขึ้น |
| re-validate §3.2/§3.3 (4 ชุด) | รัน script offline 4 ชุด (§17.4) | **รันฟังก์ชันที่ใช้งานจริง (`data_access.portfolio_risk_model`) กับข้อมูลจริงตรงๆ** (ดู 18.2) | script offline แยกอาจเพี้ยนจากโค้ดจริง (parameter/ขั้นตอนไม่ตรง 100%) — รันของจริงให้ผลที่เชื่อได้มากกว่าและตรงกับที่ผู้ใช้จะเจอเป๊ะ |

### 18.2 ตรวจกับข้อมูลจริง (รันสดวันนี้ ไม่ใช่ตัวเลขจากแผนเดิมที่ใช้ dummy Σ/μ)

ทดสอบ 5 กองแรกใน `cache/results.csv` (ABAGS, ABAPAC, ABEG, ABGEM, ABGS-A) ผ่าน `data_access.portfolio_risk_model()` จริง:

- **obs:parameter ดีขึ้นจริง**: n_obs ≈ 456-461 (ไม่ถึง 756 เพราะ NAV ไม่ได้มีทุกวันทำการ) ต่อ 21-28 parameter
  = ratio **~16-22:1** (เทียบกับ 1 ปีที่จะได้ ~9-12:1) → ตาม §17.1 ที่กังวลไว้ ปัญหาลดลงมากแม้ไม่ถึง 27:1 ตามทฤษฎีเป๊ะ
- **R² อยู่ในช่วงสมเหตุสมผล**: 0.30-0.78 (ไม่มีตัวไหนใกล้ 1 แบบ overfit ผิดปกติ) ทั้ง 21-factor และ 28-factor ให้ค่าใกล้กันมาก
  (เช่น ABAPAC 0.758 vs 0.785) — สอดคล้องกับที่ตัด collinear index ออกไม่ควรกระทบ R² มาก
- **Σ เป็น positive semi-definite จริง** (eigenvalue ต่ำสุด > 0 ทั้ง 21F/28F) ไม่มีปัญหา numerical
- **fit time ~2.6-2.7 วิ / 5 กอง** (ส่วนใหญ่คือโหลด NAV) ตรงกับที่ `docs/pages/8-score-screen.md` บันทึกไว้ (~2.6 วิ)
- **grid+Pareto เร็วตามที่ validate ไว้เดิม**: 213,876 combination, compute 0.01 วิ, ได้ frontier ~495 จุด (ตัวเลขต่างจาก
  ตัวอย่าง dummy เดิมใน §14.4 เพราะ Σ/μ เปลี่ยนเป็นของจริงแล้ว — เป็นเรื่องปกติ)
- **market_weights/Π เป็นตัวเลขที่สมเหตุสมผล**: w_market ตาม AUM จริง (ไม่มีกองไหนเกิน cap 50%), Π ที่ได้เป็นบวกทั้งหมด
  ⚠️ **ถูกแทนที่โดย §19** — w_ref เป็น 1/N และ Π ใช้ Σ_sys แล้ว ตัวเลข Π 2-5% ในข้อนี้เป็นของสูตรเดิม
  ในช่วง 2-5% ต่อปี ไม่มีค่าผิดปกติ (เช่นติดลบทั้งกระดานซึ่งเป็นเหตุผลที่เลือก γ คงที่ตาม §17.3)

### 18.3 ตรวจโค้ด 3 เรื่องตามธรรมเนียมโปรเจกต์

**(1) โค้ดใหม่ถูกต้องหรือไม่**
- `macro_chain.unstandardize` = coef_std / σ_x ถูกต้อง (StandardScaler ใน pipeline scale เฉพาะ X ไม่ใช่ y ตรงกับสูตรนี้)
- window เดียวกัน (`levels.iloc[-756:]`) ถูกส่งเข้าทั้ง `factor_covariance` และ `build_fund_returns` ต่อกอง → B/F/D
  สอดคล้องกันแน่นอน ไม่มี window mismatch
  ⚠️ **ไม่จริงทั้งหมด (review §22)**: กองที่ NAV จบก่อน (PRINCIPAL GEF-X / K-AEC ถึง 2026-01) fit B/D จากช่วงสั้นกว่า F ที่ใช้ถึง 2026-07-31
- factor set ตาม toggle จริง — ตรวจโค้ดแล้วรันจริงแล้วว่า K=21 (VIF-cleaned) กับ K=28 (ทั้งหมด) ให้ betas/Σ คนละชุดจริง
- D = (1−R²)×total_var, clip ≥ 0 — ตรงสูตร

**(2) ระบบเดิมไม่พัง**
- `pytest -q` → **86/86 ผ่านทั้งหมด** (เดิม 74 ก่อนฟีเจอร์นี้ + เพิ่ม 12 test ใหม่ใน `tests/test_portfolio.py`)
- `matching.py` / `macro_chain.py` **ไม่ถูกแก้** ในงาน frontier — โค้ดใหม่แค่เรียกใช้ (`metrics.py` ถูกแก้ก่อนหน้านั้นใน §12.13
  เพิ่ม `recent_return(skip=...)` สำหรับ momentum 12-1 — ค่าเริ่มต้น skip=0 จึงไม่กระทบหน้าอื่น)
- `config.py` มีแต่ "เพิ่ม" ค่าคงที่ `PORTFOLIO_*` ต่อท้าย ไม่มีการแก้ค่าเดิมที่มีอยู่

**(3) โครงสร้างโดยรวมยังสมเหตุสมผล ไม่ซับซ้อนเกินจำเป็น**
- การรวม window เป็นตัวเดียว (18.1) ทำให้ระบบ **ง่ายกว่า** แผน split-window เดิมโดยไม่เสียความถูกต้อง — เป็นการลดความซับซ้อนที่ดี
- ไม่มี cache ลงดิสก์ใหม่ → ไม่เพิ่มความเสี่ยง "cache ไม่มี provenance" แบบที่เจอในหน้า 7

### 18.4 ข้อสังเกตเล็กๆ (ไม่ใช่บั๊ก — ไม่บล็อกการใช้งาน)

1. **R² ที่ใช้หา D เป็น in-sample** (ElasticNetCV เลือก hyperparameter ด้วย CV แต่ตัวเลข R² ที่รายงานมาจาก refit เต็มแล้ว
   score บนชุดเดียวกัน) ที่ ratio ~16-22:1 ยัง optimistic bias เหลืออยู่นิดหน่อยแต่เบากว่าที่ 1 ปีมาก (9-12:1) มาก —
   ไม่ต้องแก้ตอนนี้ แค่บันทึกไว้เป็นข้อจำกัดที่รู้ (ถ้าจะรัดกุมกว่านี้ในอนาคต ใช้ out-of-fold R² จาก CV ของ ElasticNetCV แทนได้)
2. `front_w` (น้ำหนักของแต่ละจุดบน frontier) เรียงด้วย `numpy.argsort` ส่วน `frontier` (risk/return) เรียงด้วย
   → ✅ ปิดแล้วที่ §21.3 (เกิดจริงไม่ได้ · review §22 ทดสอบ brute force ซ้ำแล้วลำดับตรงกัน)
   `pandas.sort_values` — ปกติให้ผลตรงกันเพราะ risk เป็น float ต่อเนื่องไม่ค่อยชนกันเป๊ะ แต่ถ้าอยากตัดความเสี่ยงนี้ทิ้งสนิท
   เปลี่ยนให้ทั้งสองฝั่งใช้ `argsort` ตัวเดียวกันได้ (nitpick ระดับความสะอาดของโค้ด ไม่ใช่บั๊กที่เจอจริง)

### 18.5 สรุป

**ฟีเจอร์นี้ implement เสร็จสมบูรณ์ ตรวจแล้วถูกต้อง ไม่มีอะไรพังจากของเดิม (86/86 test ผ่าน) และโครงสร้างเรียบง่ายกว่า
แผนที่คุยกันไว้ตอนแรกโดยไม่เสียความถูกต้อง — พร้อมใช้งาน** สิ่งที่ยังไม่ทำ (ตามที่ `docs/pages/8-score-screen.md` ข้อ 9
บันทึกไว้แล้ว): BL views จากคะแนนโซน, versioning ของ style/macro scope, rebalance ทุก 3 เดือน, backtest น้ำหนักย้อนหลัง
— ไม่ใช่ scope ของงานรอบนี้


## 19. แก้ Π: ตัด D + น้ำหนักอ้างอิงเท่ากัน (2026-09-29, แทนที่ §15.1 ส่วน w_market จาก AUM และ Π จาก Σ เต็ม)

**ที่มา**: จากผลจริงบนหน้า 8 กอง TCHTECH-A (score อันดับ 292/310 แค่เติมโซนที่ 5) AUM 73.5% ของ 5 กอง → w_market ชน cap 50%, vol 36% → Π 17.65% (93.5% มาจากเทอมตัวเอง γΣ_iiw_i) → optimizer ดันชนเพดาน 30% แบกความเสี่ยง 68%

**ผู้ใช้วินิจฉัยต้นเหตุ 2 ข้อ (รับเต็มที่)**: (1) BL เป็นทฤษฎีของ "พอร์ตตลาด" ของหุ้น — AUM ของกองที่คัดมาเองไม่ใช่ตลาด (2) D เป็นความเสี่ยงเฉพาะตัวที่ตลาดไม่จ่าย ไม่ควรเข้าสูตร Π

**ที่ทำ**: `portfolio.systematic_covariance` (Σ − diag D), `portfolio.reference_weights` (config `PORTFOLIO_REF_WEIGHT`="equal", สลับเป็น "aum" ได้), หน้า 8 คำนวณ Π จาก Σ_sys · w_ref แต่ความเสี่ยงพอร์ตยังใช้ Σ เต็ม · test เพิ่ม 3 ตัว (89/89 ผ่าน)

**ผลจำลอง/รันจริง**: Π TCHTECH-A 17.65% → 4.68% · น้ำหนัก max Sharpe 30% → 11% · risk contribution 68% → 18%

**ไม่ทำ (ตัดสินใจร่วมกัน)**: เพดาน risk contribution ต่อกอง (แนวทาง 4) · เกณฑ์กันกองอ่อนที่ส่วนที่ 2 (จะให้เหลือ <4 กอง) — ทบทวนใหม่ถ้าเจอเคสที่ Π ยังเพี้ยนหลังแก้นี้

**ข้อจำกัดที่ยังอยู่**: Π ยังไม่มีสัญญาณจากคะแนนโซน/คุณภาพกอง (ต้องใส่เป็น BL views) · กอง vol ตาม factor สูงยังได้ Π สูงตามโครงสร้าง

## 20. เกณฑ์ score ขั้นต่ำ 0.7 + ลดขั้นต่ำเหลือ 3 กอง + เพดานน้ำหนัก 40% (2026-09-29)

**ที่ทำ**: `config.SCORE_MIN_ELIGIBLE = 0.7` · `greedy_select(min_score=...)` เทียบกับ score ของ**คู่ที่ใช้จริง** (primary→score, secondary→score คู่สำรอง)
· กองที่คู่ยังใหม่แต่ต่ำกว่าเกณฑ์ = ไม่ผ่าน (ไม่ mark used ไม่ลองคู่สำรอง) · `PORTFOLIO_MIN_FUNDS` 4→3 · `PORTFOLIO_MAX_W` 30%→40% (3×40%=120%≥100%)
· แก้ข้อความ error ที่ hard-code "× 3 กอง" ให้คำนวณจาก MIN_FUNDS · ผู้ใช้ตัดสินใจเองหลังเห็นว่า Primary only + AND เหลือ 3 กอง

**ตรวจ 8 โหมด (universe × P+S/P × AND/OR) กับข้อมูลจริง**: ทุกโหมดมีกองผ่านเกณฑ์ ≥3 (ต่ำสุด 3 = clean/P only/AND; โหมดเริ่มต้นได้ 4) → frontier คำนวณได้ทุกโหมด
· test ใหม่ 3 ตัว + ปรับ test grid ให้ระบุ max_w เอง (92/92 ผ่าน)

**ข้อสังเกต**: score เป็น percentile ภายใน universe → 0.7 เป็นเกณฑ์สัมบูรณ์ในสเกลนั้น (สลับ toggle แล้วความหมายขยับ) · โหมดเริ่มต้นเหลือ 4 กอง (ตัดกองคะแนนต่ำที่เคยเติมเป็นกองที่ 5)

## 21. Plan review รอบ §18-§20 + แก้กติกา min_score (2026-09-29)

ทวน §18-§20 เทียบโค้ดจริง: ทุกข้อที่เขียนว่า "ที่ทำ" มีอยู่ในโค้ดจริง · test 92/92 ผ่าน · 8 โหมดมีกองผ่านเกณฑ์ ≥ 3 ตามที่ §20 ว่า

### 21.1 แก้: primary ว่างแต่อ่อน -> ลองคู่สำรองต่อ (ตัดสินใจร่วมกัน)
เดิม (§20) คู่ primary ที่ยังว่างแต่ score < 0.7 = ข้ามกองทันที ไม่ลองคู่สำรอง แต่ถ้า primary **ชน** กลับลองคู่สำรอง →
กองที่ primary ว่างเสียเปรียบกองที่ primary ถูกใช้ไปแล้ว (ขัดกันเอง) · มีกองแบบนี้จริง: ชุด 11 = TCHTECH-A (0.10 / สำรอง 1.56),
ASIA-E, GC · ชุด 18 = 7 กอง เช่น KKP G-THEME-H (0.08 / **6.94**)
**แก้**: `greedy_select` เงื่อนไขเดียว `_is_new(...) and value >= min_score` ไม่ผ่าน -> ลองคู่ถัดไป · test ใหม่ 1 ตัว (93/93 ผ่าน)
**ผล**: Top 5 และจำนวนกองผ่านเกณฑ์ **ไม่เปลี่ยนทั้ง 8 โหมด** (กองพวกนี้อยู่อันดับท้าย) — แก้ความถูกต้องเชิงตรรกะไว้ก่อนจะเจอเคสจริง
  ⚠️ **review §22**: ที่ไม่เปลี่ยนเพราะ greedy ไล่ตาม score ของ primary — กองพวกนี้ถึงคิวหลังโซนถูกใช้หมด การแก้นี้มีผลจริงน้อยมาก (ยืนยันคงลำดับเดิม)

### 21.2 ผลของ §19 ที่ควรรู้: max Sharpe ≈ equal weight โดยโครงสร้าง
Π = γ·Σ_sys·(1/N) -> tangency ภายใต้ Σ_sys คือ Σ_sys⁻¹Π ∝ 1/N พอดี · frontier ใช้ Σ เต็ม ส่วนต่างจาก 1/N จึงมาจาก D อย่างเดียว
(กอง D สูงโดนนับความเสี่ยงแต่ไม่ได้ Π ชดเชย -> ถูกลดน้ำหนัก) · ตั้งใจแบบนี้ได้ แต่แปลว่า frontier ยังไม่ได้บอกว่า "กองไหนดีกว่า"
จนกว่าจะใส่ BL views (§12.13 ข้อ 3)

**ผลรันจริง (clean 11 · P+S · AND · 4 กอง KT-MFE-A / PRINCIPAL GEF-X / KT-JPFUND-A / K-AEC)**:

| กอง | Π | vol โมเดล √diag(Σ) (ไม่ใช่ vol จริง — §22) | R² |
|---|---|---|---|
| KT-MFE-A | 1.8% | 11.3% | 0.76 |
| PRINCIPAL GEF-X | 1.8% | 12.1% | 0.74 |
| KT-JPFUND-A | 4.2% | 24.1% | 0.79 |
| K-AEC | 0.9% | 9.5% | 0.48 |

fit 2.4 วิ · 28,011 ชุด · frontier 1,631 จุด · 0.01 วิ · max Sharpe 0.21 (risk 10.5% · 28/28/26/18) · equal weight 0.21 (10.2%)
· min-variance 0.19 (8.2% · 31/24/5/40) · 5 กองที่เพดาน 40% = 885,801 ชุด ~0.3 วิ (ยังเร็วพอ)

### 21.3 ข้อสังเกต §18.4.2 (argsort vs sort_values) — เกิดจริงไม่ได้
`pareto_mask` เก็บเฉพาะ `ret > best` แบบเข้มงวด -> 2 จุดที่ risk เท่ากันเป๊ะถูกเก็บได้อย่างมากจุดเดียว ไม่มีค่าเสมอให้เรียงต่างกัน · ไม่แก้

### 21.4 เอกสารที่ปรับให้ตรงกับ §19-§21
`docs/pages/8-score-screen.md` (ขั้นตอน greedy · จำนวน combination ที่ 40% · ขั้นต่ำ 3 · ผลจริง 4 กอง · หมายเหตุ max Sharpe ≈ 1/N ·
กติกา min_score ใหม่) · `docs/appendix/methodology.md` §8/§9 + ตารางพารามิเตอร์ · `README.md` + `docs/README.md` (Π = γΣ_sys·w_ref)
· แผนนี้: หัวไฟล์ · กล่องสรุป §14 · §14.3 · §15.1 (ทำเครื่องหมายถูกแทนที่) · §18.3 (แก้ 2 จุดที่คลาดเคลื่อน)


## 22. Review หน้า 8 ด้วย sub-agent 3 มุม (คณิต / โค้ด / เอกสาร) — 2026-09-29

ทุกข้อที่มีตัวเลขตรวจซ้ำด้วยสคริปต์แยกแล้ว · ผู้ใช้เลือกแก้ **บั๊กโค้ด + เอกสาร** · ข้อเชิงวิธีการ (A) บันทึกไว้ ยังไม่แก้ · greedy คงลำดับตาม score ของ primary

### 22.1 แก้แล้ว (โค้ด)
| เรื่อง | เดิม | แก้ |
|---|---|---|
| slider เลือกจุดบน frontier | label ปัด 1 ตำแหน่ง -> 1,631 จุดเหลือ label ไม่ซ้ำ 58 ตัว (Streamlit ซ้ำ = ได้ตัวท้าย) slider กระโดด | label `#i · risk x.xx% · return x.xx%` ไม่ซ้ำ · frontier จุดเดียว = ไม่สร้าง slider |
| `weight_grid` step | step 3% -> หน่วย 3.03% · 7% หลุด min/max · 2% กับ min 5% -> 4% | step ต้องหาร 100 (ไม่งั้น ValueError) · min ปัดขึ้น/max ปัดลง · UI เลือก step จาก `PORTFOLIO_STEP_CHOICES` |
| กราฟ 5 กอง | 885,801 จุด ≈ figure 24MB ส่งใหม่ทุกครั้งที่ขยับ slider | สุ่มแสดงกลุ่มเมฆไม่เกิน `PORTFOLIO_CLOUD_MAX_POINTS` = 50,000 (seed คงที่) · frontier วาดครบ |
| fit risk model ล้ม | `st.stop()` ก่อนตารางส่วนที่ 2 -> ตารางหายด้วย | แจ้ง error แล้วยังโชว์ตาราง หยุดก่อนส่วนที่ 3 |
| คอลัมน์ vol | help ส่วนที่ 2 ว่า "ตัวที่เข้า Σ จริง" (ไม่จริง) | ส่วนที่ 2 = vol จริง · ส่วนที่ 3 = "vol (โมเดล)" √diag(Σ) พร้อม help |
| หัวตาราง "score ≥ 0.7" | ตารางโชว์แค่ score ของ primary (GEF-X 7.61 แต่ผ่านด้วยคู่สำรอง 1.92) | เพิ่มคอลัมน์ `score คู่ที่ใช้` |
| `app.py` | "313/715 (44%)" + "กอง F รวมใน regression" | ตัวหาร `EXPECTED_FILTERED_FUNDS_E` = 600 · ข้อความเฉพาะกอง E |
test ใหม่ 3 ตัว (step ไม่ลงตัว · ปัด min/max เข้าใน · กราฟสุ่มลดแต่ frontier ครบ) -> **96/96 ผ่าน** · เปิดหน้า 8 จริง: slider ขยับทีละจุด (#865 -> #866) · step 5% ได้ 315 ชุด · ไม่มี error

### 22.2 ยังไม่แก้ — ข้อจำกัดเชิงวิธีการ (ต้องคุยสเปกก่อน)
1. **กองที่ NAV เก่ายังถูกคัด** — โหมดเริ่มต้น PRINCIPAL GEF-X / K-AEC NAV ถึง 2026-01-07/08 แต่ factor ถึง 2026-07-31 · อีก 8 กอง NAV จบก่อนปี 2025
   ยังผ่าน screening · ONE-CHINA (NAV จบ 2023) ถ้าถูกเลือกจะทำให้ fit ล้ม -> เสนอเกณฑ์ "NAV ล่าสุดเก่าไม่เกิน N วัน" ก่อน greedy
2. **F รายวันจับ correlation ข้ามเขตเวลาต่ำเกินจริง** — USA–JAPAN 0.08 (รายวัน) vs 0.38 (รายสัปดาห์) · USA–EUROPE 0.32 vs 0.53 ·
   corr ตามโมเดลของ 4 กอง 0.20–0.31 vs realized รายสัปดาห์ 0.41–0.61 -> diversification ดูดีเกินจริง
3. **√diag(Σ) ≠ vol จริง** — KT-MFE-A 11.3% vs 13.5% · D = (1−R²) × var จาก return ที่ winsorize × 252 (NAV มีแค่ 58–78% ของวันทำการ) คนละฐานกับ BFBᵀ
   -> ทางแก้ที่เสนอ: D = max(var จริง − (BFBᵀ)_ii, floor)
4. **กองเอเชีย NAV ช้ากว่า factor บางส่วน** — R² K-AEC 0.50 -> 0.63 เมื่อใส่ lag 1 วัน (UGD 0.42 -> 0.50) กระทบ score และ D
   -> ข้อ 2–4 แก้พร้อมกันได้ด้วย B/F/D **รายสัปดาห์** (ทดลอง: vol KT-JPFUND 24.1% -> 19.6% ใกล้ realized รายสัปดาห์ 19.3%)
5. เล็ก: 756 แถว = 2.9 ปีปฏิทิน · ×252 กับดัชนีที่มี ~261 แถว/ปี ทำให้ var ของ F ต่ำ ~3% · ไม่เช็คเครื่องหมาย primary (ชุด 18 มี 4 กอง) ·
   โหมด OR เลือก share class คนละตัวของกองเดียวกันได้ · `nav_loader` เขียนทับ `cache/nav_spike_fixes.csv` ทุกครั้งที่โหลด NAV ชุดย่อยที่มี spike
   (ตอน review สคริปต์โหลด 313 กองจึงเขียนทับไป 1 ครั้ง ได้ 5 แถวจากกองชุดเดียวกับ pipeline — กด Rebuild เพื่อยืนยันว่าเป็นของ pipeline)

### 22.3 ตรวจแล้วถูกต้อง
unstandardize แม่นยำ (error 3e-17) · Σ, Σ_sys PSD · สูตร BL และ "tangency ภายใต้ Σ_sys ∝ 1/N" · Pareto (brute force) · argsort = sort_values ·
จำนวนกริด 231 / 28,011 / 885,801 · momentum 12-1 ไม่ off-by-one · pct_rescaled สมมาตร · เกณฑ์ 0.7 ผ่านใกล้กันทั้งสอง universe (68.7% / 66.5%) ·
`_passes_band` กับ coef ติดลบ · cache/fallback ของ streamlit · หน้า 1–7 ไม่กระทบ

### 22.4 เอกสารที่ปรับ
`docs/pages/8-score-screen.md` (จำนวนกองไม่ตายตัว 5 · เพดาน OR = country + sector − 1 · ตารางแสดงเฉพาะกองผ่านเกณฑ์ · ลำดับ greedy ·
share class ไม่รับประกัน · vol โมเดล vs จริง · step/cloud/slider · cache 313 × 6 · ข้อควรระวัง 5 และ 9 ใหม่) · `methodology.md` §8/§9 + พารามิเตอร์
(band, PCT_LO/HI, MATRIX_SCALE, STEP_CHOICES, CLOUD_MAX_POINTS) · README ×2 · `docs/archive/README.md` (8 หน้า) · `data-sources.md`
(ชุด 11 ของหน้า 8) · docstring `data_access.py`/`screening.py`/หน้า 8 · แผนนี้: ใส่เครื่องหมายถูกแทนที่ใน §12.6, §12.9, §12.12, §14, §15.1, §16, §17.1-2, §18, §21

## 23. Clean ข้อมูล NAV ต่อกอง ทั้งแอป (2026-09-30)

ผู้ใช้เลือกเริ่มจากการ clean ข้อมูลกองก่อน (ดัชนี 28 ตัวโอเคแล้ว) · ตัดสินใจร่วมกันหลัง dry run 2 รอบ:
1. **ขอบเขต = ทั้งแอป** (แก้ที่ต้นทาง) · 2. **ตัดกองที่ NAV ล่าสุดช้ากว่าดัชนี > 90 วัน + กองเลิกแล้ว** (313 → 209)
3. **ทิ้ง return ที่คร่อมรู > 10 วันทำการ** (159 กอง · 340 จุด) · 4. **share class: เก็บทุก class · หน้า 8 เลือกได้ ≤ 1 ต่อกลุ่ม**
(`base_data/share_class_groups.csv` 32 กลุ่ม) · 5. class ปันผล: ไม่ทำอะไร · 6. อ่าน UpdateTime ครบ 3 รูปแบบ (ผลไม่เปลี่ยน)
· เก็บ NAV ที่ clean แล้วเป็น `cache/nav_clean.parquet`

**ผลหน้า 8 โหมดเริ่มต้น**: KT-MFE-A · PRINCIPAL GEF-A (ทางคู่สำรอง — profile เหมือน KT-MFE-A ทุกอย่าง = ปัญหา V1 ของ code review
ที่ยังไม่แก้) · KT-JPFUND-A · max Sharpe 0.26 · รายละเอียดใน `docs/pages/8-score-screen.md` หัวข้อ "หลัง clean NAV ต่อกอง"

