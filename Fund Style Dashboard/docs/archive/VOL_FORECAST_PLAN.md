# แผนฟีเจอร์: 🔮 Vol Forecast (หน้าที่ 4)

> สถานะ: ✅ **เสร็จแล้ว 2026-09-07** — implement ครบตาม spec (รวม §0.1) · pytest 18/18 · vol cache 28 index (GARCH fallback 0) · หน้า 4 รันได้
> ต่อยอดจาก 3 หน้าเดิม (Country Match / Sector Match / Match Strength) แบบ **ไม่แตะโค้ดเดิมเลย** — เพิ่มไฟล์ใหม่ทั้งหมด
> ผล sanity: USA realized 15.8%/GARCH 16.5%, TAIWAN GARCH ชนะ EWMA · GARCH ชนะเล็กน้อยภาพรวม (RMSE 0.069 vs 0.073)

---

## 0. เป้าหมาย + ขอบเขตที่ confirm แล้ว

| หัวข้อ | Decision |
|---|---|
| Forecast อะไร | annualized volatility ของ **MSCI country/sector index** (28 ตัว: 18 country + 10 sector) — ยังไม่ทำระดับกองทุน |
| Horizon | 21 trading days ข้างหน้า (~1 เดือน) |
| โมเดล | **EWMA** (baseline) + **GARCH(1,1)** (ตัวหลัก) — เทียบกันสองตัว |
| Validation | **Walk-forward, expanding window** (ไม่ใช่ split ครั้งเดียว) |
| ตำแหน่งในแอป | หน้าใหม่แยกต่างหาก **หน้าที่ 4** — ไม่ยุ่งกับ 3 หน้าเดิม |
| นิยาม forecast target | **Annualized avg-daily-vol ตลอด horizon** — `√(mean daily variance ที่ทำนาย 21 วัน × 252)` ให้หน่วยตรงกับ `ann_vol` ที่ใช้อยู่ทั้งแอป (ไม่ใช่ cumulative 21-day vol) — ดูสูตรแม่นยำต่อฟังก์ชันใน §2 |

**เหตุผลที่เริ่มจาก index-level ก่อนกองทุน** (ตามที่คุยกันไปแล้ว): ข้อมูล index สะอาดกว่า (daily ครบ ไม่มี NAV gap) จำนวน series น้อยกว่ามาก (28 vs 368) และผลลัพธ์ต่อยอดกับ pipeline เดิมได้ในอนาคต — เอา ElasticNet coefficient ที่มีอยู่แล้วมาถ่วงน้ำหนัก forecasted index vol เพื่อประมาณ forecasted fund vol ได้ (phase ถัดไป ยังไม่ทำตอนนี้)

**ข้อจำกัดที่ต้องรู้ไว้ตั้งแต่ต้น**: ข้อมูลมีแค่ 2021-01-01 → 2026-07 (~5.6 ปี) เป็น daily close ไม่มี intraday, refit ทุก 21 วัน (=horizon) แบบไม่ overlap กัน ได้ test window เต็มที่ราวๆ **~55 หน้าต่าง** ต่อ index (`(1406−252)//21≈54`) — เป็นตัวอย่างที่ไม่เยอะทางสถิติ และไม่ครอบคลุม regime วิกฤตรุนแรง (เช่น 2008/2020) ต้องอ่านผล backtest แบบ "ทิศทาง" ไม่ใช่ "สรุปแน่นอน"

---

## 0.1 ข้อสรุปเพิ่มเติมหลังคุย spec (confirmed 2026-09-07)

4 จุดที่เคลียร์ก่อนลงมือ — ถือเป็น ground truth ทับข้อความเดิมถ้าขัดกัน:

1. **นิยาม forecast target (สำคัญสุด)** — ทำนาย **annualized average-daily-vol ตลอด horizon** ให้เทียบกับ realized ตรงหน่วย:
   - forecast = `√(mean ของ daily variance ที่ทำนาย h=1..21) × √252`
   - realized  = `std(daily return ใน window 21 วัน, ddof=1) × √252` (สูตรเดียวกับ `metrics.annualized_volatility`)
   - EWMA ไม่มี mean-reversion → h-step แบน = σ²_t ทุกวัน → forecast = `√(σ²_t)×√252`
   - GARCH ใช้ `.forecast(horizon=21).variance` แล้ว **เฉลี่ย** variance h=1..21 (ไม่ใช่บวกสะสม) ก่อน √×√252

2. **หน่วย + การ fit GARCH** — `arch_model(returns*100, mean="Zero", vol="Garch", p=1, q=1)`:
   - คูณ 100 ให้ %-scale (กัน convergence warning) → variance ที่ได้เป็น `%²` **ต้องหารกลับ 100²** ก่อนแปลงเป็น vol (จุดพลาดง่าย)
   - ใช้ `mean="Zero"` (daily index return mean≈0 ลดพารามิเตอร์)

3. **QLIKE คำนวณบน variance ไม่ใช่ vol** (Patton 2011, robust ต่อ noise ของ realized proxy):
   - `QLIKE = realized²/forecast² + log(forecast²)` (ต่อ window แล้วเฉลี่ย) — realized²/forecast² = variance ratio
   - ยัง report RMSE/MAE บน **vol** (หน่วยอ่านง่าย) ควบคู่กัน

4. **`step` ปรับได้ผ่าน config** — default `21` (non-overlap, ~55 window, independent แต่น้อย + target noisy).
   ตั้ง `VOL_FORECAST_STEP` เล็กลง (เช่น 5 → ~230 window, overlap) เพื่อดูกราฟละเอียด/eval จุดเยอะขึ้นได้
   แต่ต้องตีความ metric แบบ autocorrelated (ไม่ใช้อ้าง significance). guard: window สุดท้ายที่ไม่มี 21 วันอนาคตครบ → ข้าม

---

## 1. ไฟล์ที่จะเพิ่ม (ใหม่ทั้งหมด ไม่แก้ไฟล์เดิม)

```
analysis/
  vol_forecast.py        ← โมดูลใหม่: EWMA, GARCH, walk-forward harness, evaluation metrics
data_access.py            ← เพิ่มฟังก์ชันใหม่ (ไม่แก้ของเดิม): build_vol_forecast_cache(), get_vol_forecast()
pages/
  4_🔮_Vol_Forecast.py    ← หน้าใหม่
config.py                 ← เพิ่มค่าคงที่ใหม่ (ไม่แก้ค่าเดิม)
cache/
  vol_forecast_backtest.csv  ← ผล walk-forward ทุก window ทุก index (regenerate ได้)
  vol_forecast_latest.csv    ← forecast ปัจจุบัน (ใช้ข้อมูลทั้งหมดที่มี) ต่อ index
tests/
  test_vol_forecast.py    ← unit test ของโมดูลใหม่
requirements.txt          ← เพิ่ม dependency `arch` (GARCH library)
```

---

## 2. `analysis/vol_forecast.py` — ฟังก์ชันหลัก

> **หน่วยที่ใช้ตลอดทั้ง 3 ฟังก์ชันข้างล่าง (สำคัญ — เป็นจุดที่เคยกำกวมในดราฟต์แรก แก้ให้ชัดแล้ว):**
> ทุกฟังก์ชันคืนค่าเป็น **annualized average-daily volatility** หน่วยเดียวกับ `ann_vol` ที่ใช้ทั้งแอป ไม่ใช่ cumulative-21-day dispersion
> - EWMA: `forecast = √(σ̂²_t × 252)` — variance ประมาณล่าสุดคงที่ตลอด horizon (สมมติฐานของ EWMA)
> - GARCH: ได้ variance forecast รายวัน 21 ค่าจาก `.forecast(horizon=21)` (ไม่เท่ากันเพราะมี mean-reversion) → เอา **ค่าเฉลี่ย** ของ 21 ค่า (ไม่ใช่ผลรวม) แล้ว annualize: `forecast = √(mean(σ̂²_{t+1..t+21}) × 252)`
> - Realized (ground truth): `√252 × std(daily return ในช่วง window, ddof=1)` — สูตรเดียวกับ `analysis/metrics.py::annualized_volatility()` เป๊ะๆ

### `ewma_forecast(returns, lam=0.94, horizon=21) -> float`
ประมาณ daily variance ล่าสุดแบบ exponentially weighted (`σ²_t = λ·σ²_{t-1} + (1-λ)·r²_{t-1}`, λ=0.94 ตาม RiskMetrics convention) แล้วแปลงเป็น annualized vol ตามสูตรด้านบน (สมมติ variance คงที่ตลอด horizon — ข้อจำกัดของ EWMA ตามที่อธิบายไปก่อนหน้านี้)

### `garch_forecast(returns, horizon=21) -> float`
fit GARCH(1,1) ด้วย library `arch` (`arch_model(returns*100, vol="Garch", p=1, q=1)`) แล้วใช้ `.forecast(horizon=21)` ได้ variance รายวัน 21 ค่า เฉลี่ยแล้ว annualize ตามสูตรด้านบน (**เฉลี่ย ไม่ใช่ผลรวม** — จุดที่แก้จากดราฟต์แรก) มี fallback: ถ้า fit ไม่ converge (MLE ล้มเหลว, พบได้กับ series ผันผวนน้อย/ไม่ต่อเนื่องอย่าง Vietnam) ให้ตกกลับไปใช้ EWMA แทนสำหรับ window นั้น พร้อม flag บอกว่า fallback (ไม่ปล่อยให้ crash ทั้ง pipeline เหมือน pattern `MIN_REGRESSION_OBS` guard ที่ทำไว้ในฝั่ง matching)

### `realized_vol(returns, window=21) -> float`
ground truth ของ backtest — annualized std ของ return จริงที่เกิดขึ้นใน window นั้นๆ ตามสูตรด้านบน (สูตรเดียวกับ `analysis/metrics.py::annualized_volatility` เพื่อให้เทียบกันตรงหน่วยกับทั้ง EWMA และ GARCH forecast)

### `walk_forward_backtest(returns, index_name, min_train=252, step=21, horizon=21) -> pd.DataFrame`
Harness หลัก — เริ่มจาก `min_train` วันแรก (~1 ปี ขั้นต่ำที่พอให้ GARCH fit ได้เสถียร) เป็น training window แรก (expanding ไม่ใช่ rolling คือไม่ตัดข้อมูลเก่าทิ้ง):

1. fit EWMA + GARCH ด้วยข้อมูลถึงวันที่ `t`
2. forecast vol ของ 21 วันถัดไป (`t+1` ถึง `t+21`) ด้วยทั้งสองโมเดล
3. รอจน 21 วันนั้นผ่านไปจริง คำนวณ `realized_vol` ของช่วงนั้น
4. บันทึกแถว: `{index, window_start, window_end, ewma_forecast, garch_forecast, realized_vol}`
5. เลื่อน `t += step` (step=21=horizon → window ถัดไปไม่ overlap กับ window ก่อน ได้ sample ที่ independent มากขึ้น) ทำซ้ำจนหมดข้อมูล

คืน DataFrame ยาว (ทุก window ทุก index) → เก็บเป็น `cache/vol_forecast_backtest.csv`

### `evaluation_metrics(df) -> pd.DataFrame`
สรุป error ต่อโมเดลต่อ index (และรวมทุก index): **RMSE**, **MAE**, และ **QLIKE** (loss function มาตรฐานสำหรับ vol forecasting โดยเฉพาะ — ลงโทษการ under-predict vol แรงกว่า over-predict ซึ่งเหมาะกับ risk management)

---

## 3. `data_access.py` — ส่วนที่เพิ่ม (ไม่แก้ของเดิม)

- `build_vol_forecast_cache()` — orchestration เดินตาม `data/msci_index.py::load_country_index()/load_sector_index()` (ใช้ของเดิมได้เลย ไม่ต้องเขียนใหม่) → daily return → รัน `walk_forward_backtest()` ทีละ index (28 รอบ) → เขียน `cache/vol_forecast_backtest.csv` + คำนวณ forecast ล่าสุด (ใช้ข้อมูลทั้งหมด) เขียน `cache/vol_forecast_latest.csv`
- `get_vol_forecast_backtest()` / `get_vol_forecast_latest()` — โหลด cache แบบ `@st.cache_data` ตาม pattern เดิมของ `get_results()`

**หมายเหตุเรื่องเวลารัน**: GARCH fit 28 index × ~60 window/index = ราว 1,600+ ครั้ง ต้องลอง benchmark เวลาจริงตอน implement (คาดว่าไม่กี่นาที เพราะแต่ละ fit เร็ว) ถ้าช้าเกินจะแคช per-index ระหว่างพัฒนาแทนรันรวดเดียวทั้งหมด

---

## 4. `pages/4_🔮_Vol_Forecast.py` — โครงหน้า

**บนสุด**: เลือก scope (country/sector) + เลือก index ตัวเดียว (selectbox 28 ตัว)

**Section A — Forecast ล่าสุด**: metric card 3 อัน — Realized vol ล่าสุด (ของ 21 วันที่ผ่านมา) vs EWMA forecast (21 วันข้างหน้า) vs GARCH forecast (21 วันข้างหน้า)

**Section B — Walk-forward backtest chart**: line chart ตามเวลา 3 เส้น (realized vol เส้นทึบ, EWMA forecast, GARCH forecast เส้นประ) ของ index ที่เลือก — เห็นภาพว่าแต่ละโมเดลตามความจริงได้แม่นแค่ไหนตลอด 5.6 ปี

**Section C — Model comparison table**: ตาราง RMSE/MAE/QLIKE ของ EWMA vs GARCH ทั้งรวมทุก index และเฉพาะ index ที่เลือก — บอกตรงๆ ว่าโมเดลไหนชนะ (อาจจะไม่เท่ากันทุก index)

**Caption เตือนข้อจำกัด**: ระบุชัดว่า ~60 window/index, ไม่ครอบคลุม regime วิกฤตหนักๆ, เป็น index-level ไม่ใช่ fund-level

---

## 5. `config.py` — ค่าคงที่ใหม่

```python
VOL_FORECAST_HORIZON = 21       # trading days ข้างหน้า
VOL_FORECAST_MIN_TRAIN = 252    # ~1 ปี ขั้นต่ำก่อนเริ่ม forecast แรก (GARCH ต้องการข้อมูลพอสมควร)
VOL_FORECAST_STEP = 21          # เลื่อน window ทีละเท่าไหร่ (=horizon -> ไม่ overlap)
EWMA_LAMBDA = 0.94              # RiskMetrics convention
```

---

## 6. Testing (`tests/test_vol_forecast.py`)

ตาม convention เดิมของโปรเจกต์ (มี unit test ทุกโมดูลใหม่):
- `ewma_forecast` บน synthetic constant-vol series → ค่าที่ได้ควรใกล้เคียง true vol ที่ตั้งไว้
- `garch_forecast` ไม่ crash และคืนค่า vol เป็นบวกเสมอ (รวม fallback path เวลา fit ไม่ converge)
- `walk_forward_backtest` คืนจำนวน window ตรงตามสูตร `(len(returns) - min_train) // step`
- `evaluation_metrics` คำนวณ RMSE/MAE/QLIKE ถูกต้องบน toy data ที่รู้คำตอบล่วงหน้า
- **หน่วยตรงกัน**: บน synthetic constant-variance series ให้เช็คว่า `ewma_forecast`, `garch_forecast`, `realized_vol` (คำนวณจาก series เดียวกัน) ได้ตัวเลขใกล้เคียงกัน (ไม่ใช่ผิดกันเป็น √21 เท่าตัวจากการลืม annualize/annualize ซ้ำ) — กัน regression ของจุดที่เคยกำกวมเรื่อง unit

---

## 7. Dependency ใหม่

เพิ่ม `arch` ใน `requirements.txt` (GARCH library) — ต้อง `./.venv/bin/pip install arch` ในเครื่องก่อน implement/test จริง (แนะนำรัน `python -c "import arch"` เช็คก่อนเริ่มโค้ดจริงเพื่อกันเสียเวลา)

---

## 8. Risk / Open items

1. **Sample size เล็ก** — ~60 window/index ไม่ใช่ตัวอย่างที่เยอะทางสถิติ ผล RMSE/QLIKE ควรตีความแบบระวัง ไม่ใช่ข้อสรุปนัยสำคัญทางสถิติเต็มรูปแบบ
2. **GARCH convergence** — บาง index (โดยเฉพาะที่ผันผวนน้อย/ข้อมูลไม่ smooth เช่น Vietnam, ASEAN) อาจ fit ไม่ผ่านบางช่วง ต้องมี fallback ที่ทดสอบจริง ไม่ใช่แค่ทฤษฎี
3. **ไม่ครอบคลุม tail regime รุนแรง** — ข้อมูลแค่ 2021-2026 ไม่มี 2008-style crisis ในช่วงนี้ ผลลัพธ์บอกได้แค่ performance ใน regime ปกติ-ผันผวนปานกลาง
4. **runtime การ build cache** — ต้อง benchmark จริงตอน implement (1,600+ GARCH fits)
5. **ไม่ winsorize raw index return (decision — confirmed จาก code-review 2026-09-07)**: ต่างจาก fund pipeline (Phase 2 winsorize 1–99%) โดย**ตั้งใจ** — vol forecasting มาตรฐานต้องการให้ EWMA/GARCH react ต่อ tail event จริง (เช่น regime MSCI_KOREA ผันผวนสูง มิ.ย. 2026, return วันเดียว +22% ที่โมเดลจับได้ถูกต้อง ไม่ใช่ data error) การ winsorize จะกลบสัญญาณที่อยากทำนายพอดี · ข้อแลกเปลี่ยน: ถ้ามี data error จริงจะไม่มีตัวกัน — รับความเสี่ยงนี้ไว้
6. **Phase ถัดไป (ยังไม่ทำตอนนี้)**: fund-level forecast ผ่าน coefficient-weighted combination, เพิ่ม HAR-RV/ML regression ถ้า baseline ยังไม่พอ, ขยาย horizon ให้เลือกได้ (1w/1m/3m)

---

## 9. ลำดับการ implement (เมื่อ confirm แผนนี้แล้ว)

1. เพิ่ม `arch` ใน requirements.txt + verify install
2. เขียน `analysis/vol_forecast.py` (EWMA → GARCH → walk-forward → metrics) พร้อม unit test คู่กันทีละฟังก์ชัน
3. รัน `walk_forward_backtest` กับ 1-2 index จริงก่อน (เช่น USA, TAIWAN) เช็คตัวเลขสมเหตุสมผลด้วยตา ก่อนรันเต็ม 28 index
4. เพิ่ม `build_vol_forecast_cache()` ใน `data_access.py` + รัน build cache จริง
5. เขียนหน้า `pages/4_🔮_Vol_Forecast.py`
6. เช็ค 3 เรื่องตาม convention โปรเจกต์: โค้ดใหม่ถูกต้อง / 3 หน้าเดิมยังทำงานปกติไม่มีอะไรพัง / โครงสร้างรวมยังสมเหตุสมผลไม่ซับซ้อนเกินจำเป็น
