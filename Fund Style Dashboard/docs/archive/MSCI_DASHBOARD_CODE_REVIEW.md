# Code Review: MSCI Fund Country/Sector Classification Dashboard

รีวิวโค้ดจริงใน `Fund Style Dashboard/` เทียบกับ `MSCI_DASHBOARD_PLAN.md` (อ่านทุกไฟล์ครบแล้ว: app.py, config.py, data_access.py, viz.py, page_common.py, checkpoint1.py, conftest.py, requirements.txt, analysis/*, data/*, pages/*, tests/*)

วันที่รีวิว: 2026-09-02 (รอบ 1) · อัปเดต 2026-09-02 (รอบ 2 — รีวิวซ้ำตามคำขอ) · เพิ่ม 2026-09-07 (หน้า 4 Vol Forecast — ฟีเจอร์ใหม่)

---

## รีวิว หน้า 4 — 🔮 Vol Forecast (2026-09-07)

รีวิวเทียบกับ `VOL_FORECAST_PLAN.md` (สเปกที่ confirm กันไว้ก่อนเขียนโค้ด รวมจุดที่แก้ ambiguity เรื่อง unit ไปแล้ว) อ่านไฟล์ที่เพิ่ม/แก้ครบ: `analysis/vol_forecast.py`, `data_access.py` (ส่วนที่เพิ่ม), `pages/4_🔮_Vol_Forecast.py`, `config.py` (ส่วนที่เพิ่ม), `tests/test_vol_forecast.py`, `requirements.txt`, `README.md` — และรัน sanity check กับข้อมูลจริงใน `cache/vol_forecast_backtest.csv`/`vol_forecast_latest.csv` ที่ build มาแล้วจริง (ไม่ใช่แค่อ่านโค้ดเฉยๆ)

### ✅ ถูกต้องตามแผน (ยืนยันแล้ว)

- **หน่วยตรงกันครบทั้ง 3 จุด** (จุดที่เคย flag เรื่อง ambiguity ไว้) — `ewma_forecast` ใช้ variance คงที่ตลอด horizon, `garch_forecast` เอา**ค่าเฉลี่ย**ของ variance forecast รายวัน 21 ค่า (ไม่ใช่ผลรวม, เช็คโค้ดแล้วตรง `np.mean(var_path)` จริง) ก่อนหารกลับจากสเกล ×100, `realized_vol` ใช้สูตรเดียวกับ `metrics.annualized_volatility` เป๊ะ — ทั้ง 3 ทางสอบผ่านหน่วยเดียวกัน (annualized avg-daily-vol) ตามที่ confirm ไว้
- **Walk-forward ไม่มี leakage**: `train = r.iloc[:t]`, `future = r.iloc[t:t+horizon]` แยกกันชัดเจน, ไล่เช็คจำนวน window ด้วยมือ (n=1455, min_train=252, step=horizon=21 → ได้ 57 window/index ตรงกับที่ cache จริงโชว์: `bt.groupby(['scope','index']).size()` = 57 ทุก index ไม่มีตัวไหนขาด) ตรงกับสูตรที่ทดสอบใน `test_walk_forward_window_count`
- **GARCH fallback safety net ทำงานจริง**: เช็ค `convergence_flag`, ค่า variance ที่ไม่ finite/≤0, และ `try/except` ครอบทั้งบล็อก — ตก fallback ไปที่ `ewma_forecast(r)` ด้วย `r` ตัวเดิม (unscaled) ไม่ใช่ตัวที่ ×100 ไปแล้ว เลยไม่มี unit bug ซ่อนอยู่ในเส้นทาง fallback (จุดที่เสี่ยงพลาดซ้ำเรื่อง unit มากที่สุด เช็คแล้วไม่พลาด)
- **`evaluation_metrics`**: RMSE/MAE คำนวณบน vol, QLIKE คำนวณบน variance (`av/fv + log(fv)`) ตรงกับ Patton QLIKE ที่ระบุในแผน และตรงกับ `test_evaluation_metrics_toy` ที่คำนวณมือเทียบ
- **ไม่กระทบระบบเดิมเลย**: เช็ค mtime ของ `viz.py`, `page_common.py`, `pages/1-3`, `tests/test_filters.py`/`test_matching.py`/`test_metrics.py`/`test_smoke.py`, และ `data_access.build_pipeline()` — ทุกไฟล์ mtime เดิมเป๊ะ ไม่มีการแก้ (ตรงตามที่แผนตั้งใจ "เพิ่มไฟล์ใหม่ทั้งหมด ไม่แก้ของเดิม")
- **Lazy import `arch`** เฉพาะตอน `garch_forecast`/`build_vol_forecast_cache` เรียกจริง — ไม่กระทบ startup ของหน้าอื่นที่ไม่ใช้ vol forecast

### 🟡 จุดที่ควรรู้ (ไม่ถึงกับ bug แต่ควรตัดสินใจ)

**1. ไม่มี winsorize/outlier guard บน raw index return — ต่างจาก fund-matching pipeline ที่มี**

ลองสุ่มเช็คตัวเลขจริงใน `cache/vol_forecast_latest.csv` เจอ **MSCI_KOREA** โชว์ EWMA/GARCH forecast ล่าสุด ~121%/135% ต่อปี (สูงกว่าตัวอื่นทั้ง 27 index มาก ซึ่งอยู่ช่วง 8-53%) ตรวจ raw price level ของ `MSCI_KOREA` ช่วง 2026-07-20→07-31 พบว่าราคาเหวี่ยงจริง (79,539→88,148→68,450→83,673 ภายใน ~8 วันทำการ, return วันเดียวสูงสุด +22.2%) ไม่ใช่ tick เพี้ยนโดดเดี่ยว (level เดินสมเหตุสมผลต่อเนื่องกัน ไม่ใช่กระโดดแล้วสะท้อนกลับจุดเดิมทันทีแบบ data error ทั่วไป) — ดูจาก backtest window ก่อนหน้าด้วย realized vol ของ Korea ไต่จาก ~30% เฉลี่ยทั้ง series ขึ้นไป 55-96% ต่อเนื่อง 5-6 window ก่อนจุดนี้ ก็สอดคล้องกับ regime ผันผวนสูงที่ต่อเนื่องมาสักระยะ ไม่ใช่ noise ของวันเดียว **สรุปคือโค้ดคำนวณถูกต้องตามข้อมูลที่ให้มาจริง ไม่ใช่บั๊ก** — GARCH/EWMA ตอบสนอง regime นี้ตามที่ควรจะเป็น (เป็นตัวอย่างที่ดีด้วยซ้ำว่าโมเดล react ทัน)

แต่จุดที่ต่างจาก fund-matching pipeline ชัดเจนคือ: ฝั่ง `analysis/matching.py` (Phase 2) มี `WINSOR_LOWER/UPPER` (1st/99th percentile) ตัด outlier ของ return ทุก series ก่อนเข้า regression ตามที่แผนเดิมตัดสินใจไว้ ส่วน `vol_forecast.py` ใช้ raw daily return จาก `msci_index.to_daily_return()` ตรงๆ ไม่มีการ winsorize เลย — ถ้าวันหนึ่งมี data error จริงๆ (ไม่ใช่ regime ผันผวนจริงแบบ Korea เคสนี้) ตัวเลข forecast จะพังทันทีโดยไม่มีตัวป้องกัน ควรตัดสินใจให้ชัดว่าจะ (ก) เพิ่ม winsorize แบบเดียวกับฝั่งกองทุนเพื่อความสอดคล้อง หรือ (ข) เก็บ raw ไว้ตั้งใจ (เพราะ vol forecasting มาตรฐานมักไม่ winsorize เพราะ tail event คือสิ่งที่อยากให้โมเดล react ต่อพอดี) แต่ต้องเขียน decision นี้ลง `VOL_FORECAST_PLAN.md`/README ให้ชัดเหมือนจุดอื่นๆ ที่ทำมา

**2. README.md มี documentation drift เหมือนจุดที่เคย flag ไว้ในรอบ 1 (ข้อ 1 hardcode "368/715")**

ส่วน `## หน้าเว็บ (3 หน้า)` header ยังเขียน "3 หน้า" ทั้งที่ตารางด้านล่างมี 4 แถวแล้ว (เพิ่ม Vol Forecast ไปแล้ว) ส่วน `## โครงสร้าง` (tree diagram) ก็ยังไม่มี `pages/4_🔮_Vol_Forecast.py`, `analysis/vol_forecast.py`, `tests/test_vol_forecast.py` ในรายการ และ diagram "Pipeline (6 Phase)"ท้ายๆ ยังปิดด้วย "Streamlit 3 หน้า" — จุดเดียวที่อัปเดตครบคือ Quickstart (เพิ่มคำสั่ง `data_access.py vol` แล้ว) ควรไล่แก้ 3 จุดที่เหลือให้ตรงกันด้วย

**3. Rebuild button (`app.py`) ไม่รวม vol forecast cache**

ปุ่ม "🔄 Rebuild" หน้าแรกเรียก `build_pipeline()` อย่างเดียว ไม่รวม `build_vol_forecast_cache()` — ต้อง rebuild ผ่าน CLI (`python data_access.py vol`) แยกต่างหากเท่านั้น ตรงกับ scope ที่แผนตั้งใจไว้ (หน้า 4 independent จาก pipeline เดิม) แค่อยากให้รู้ตัวไว้ เผื่ออนาคตอยากรวมปุ่มให้กด rebuild ทีเดียวทั้งคู่

**4. ไม่มี `st.spinner` ระหว่าง auto-build cache ครั้งแรกที่หน้า 4**

ถ้าเปิดหน้า 4 ก่อนรัน `data_access.py vol` เอง จะ auto-build ~10 วิ (28 index × GARCH fit) แบบ UI ไม่มี spinner/ข้อความบอก (ต่างจาก `app.py`/`page_common.py` ที่มี `st.spinner` ล้อมตอน build pipeline หลัก) เสี่ยงดูเหมือนหน้าค้าง — severity ต่ำเพราะเร็วกว่า pipeline หลักมาก (~10 วิ vs 2-3 นาที) แต่ปรับให้ UX สอดคล้องกันได้

**5. (nice-to-have) "ALL" ใน model comparison รวม country+sector ปนกัน**

`evaluation_metrics(bt)` กลุ่ม `"ALL"` เอาทั้ง 18 country + 10 sector มาเฉลี่ยรวมกันแถวเดียว ทั้งที่ลักษณะความผันผวนของ 2 กลุ่มต่างกันพอสมควร (aggregate index อย่าง ACWI/WORLD มักผันผวนต่ำกว่า sector เฉพาะทาง) อาจมีประโยชน์กว่าถ้าแยก "ALL country" กับ "ALL sector" — ไม่กระทบความถูกต้อง แค่เสนอเป็นตัวเลือกอ่านง่ายขึ้น

---

## อัปเดตรอบ 2 (รีวิวซ้ำ)

เช็คไฟล์ทุกไฟล์อีกรอบก่อน (เทียบ mtime/ขนาดไฟล์กับตอนรอบ 1) — **โค้ดไม่มีไฟล์ไหนเปลี่ยนเลย** เปลี่ยนแค่ `README.md` (เพิ่มผล verify จริง: R² by policy E=0.57/F=0.15/O=0.17, ตัวอย่างกองที่ validate แล้ว, condition number ของชุด country index = 726, และรับทราบ 2 ใน 6 จุดที่รีวิวรอบ 1 แจ้งไว้ — ดูสถานะแต่ละจุดด้านล่าง) เพราะงั้นรอบนี้คือ (ก) เช็คว่า 6 จุดจากรอบ 1 ยังอยู่ไหม (ข) ไล่โค้ดซ้ำแบบละเอียดขึ้นเพื่อหาจุดที่รอบแรกอาจมองข้าม

### สถานะ 6 จุดจากรอบ 1

| # | เรื่อง | สถานะ |
|---|---|---|
| 1 | "368/715" hardcode ใน app.py | ❌ ยังไม่แก้ (app.py ไฟล์เดิมเป๊ะ) |
| 2 | Chart 1-2 โชว์ "—" แทน "ไม่พบ exposure ชัดเจน" | ❌ ยังไม่แก้ (viz.py ไฟล์เดิมเป๊ะ) |
| 3 | Chart 3 model selector ทำให้ primary ไม่ตรง Chart 1-2 เวลาเลือก lasso/ridge | ❌ ยังไม่แก้ (pages/3, viz.py ไฟล์เดิมเป๊ะ) |
| 4 | NAVDate tie-break ใช้ UpdateTime (ไม่ตรงกับที่แผนเสนอ AsOfDate) | 🟡 **รับทราบแล้วใน README** ("dedup เก็บแถว UpdateTime ล่าสุดจริง") แต่ `MSCI_DASHBOARD_PLAN.md` เองยังไม่ได้แก้ item 7 ที่ยังเขียนว่า "ยังไม่ confirm" — แผนกับ README เล่าคนละเรื่องกันอยู่ ควรอัปเดตแผนให้ตรง |
| 5 | `sort_values` ตอน dedupe ไม่ stable | ❌ ยังไม่แก้ (nav_loader.py ไฟล์เดิมเป๊ะ) |
| 6 | `MIN_REGRESSION_OBS=30` ไม่มีในแผน | 🟡 **รับทราบแล้วใน README** ("guard MIN_REGRESSION_OBS+try/except ต่อกอง กัน build ล้มทั้งชุด") แต่แผนเองก็ยังไม่ได้แก้เช่นกัน |

### จุดใหม่ที่เจอตอนไล่ซ้ำรอบนี้ (สำคัญกว่ารอบแรก)

**7. สูตร annualize (Phase 4) ใช้ "จำนวนจุดข้อมูล" แทน "ระยะเวลาที่ผ่านไปจริง" — บิดเบือนตัวเลขได้เยอะสำหรับกองที่รายงานไม่สม่ำเสมอ**

`analysis/metrics.py`:
```python
def annualized_return(returns):
    growth = float((1.0 + r).prod())
    return growth ** (config.TRADING_DAYS / len(r)) - 1.0
```
สูตรนี้ใช้ `len(r)` (**จำนวน observation** ที่เหลือหลัง align+winsorize) เป็นตัวหาร ซึ่งถูกต้อง **เฉพาะกรณีที่กองรายงานทุกวันทำการติดกันไม่มีช่องว่าง** (ตอนนั้น n = จำนวนวันทำการที่ผ่านไปจริงพอดี) — แต่ pipeline นี้ตั้งใจไม่ fill ช่องว่างที่กองไม่รายงาน (Phase 2 ใช้ NAVDate ของกองจริงๆ เท่านั้น) ดังนั้นกองที่รายงานห่างๆ (median 1 วันแต่ 25% ของช่วงห่าง ≥ 3 วัน, มี outlier ถึง 54 วัน — ตามที่เจอตอนวิเคราะห์ K-USA-A(A) ในแผนเอง) จะมี **n น้อยกว่าจำนวนวันทำการที่ข้อมูลครอบคลุมจริงมาก**

ตัวอย่างตัวเลขจริง: กองที่เพิ่งผ่าน threshold พอดี (n≈601 จุด) แต่ข้อมูลกระจายอยู่ตลอดช่วง 2021-2026 (~1,300 วันทำการ) ถ้ากองนั้นโต 50% ตลอดทั้งช่วง (~5.16 ปี):
- **สูตรปัจจุบัน** (`n=601`): `1.5^(252/601) - 1 ≈ 18.5%/ปี`
- **ถ้า annualize ด้วยระยะเวลาที่ผ่านไปจริง** (~1,300 วันทำการ ≈ 5.16 ปี): `1.5^(1/5.16) - 1 ≈ 8.2%/ปี`

ต่างกันกว่า 2 เท่า — และ `annualized_volatility` (`std(r) × √252`) มีปัญหาแบบเดียวกัน (ยิ่งกองรายงานห่างเท่าไหร่ แต่ละ observation ยิ่งเป็น return สะสมหลายวันที่มี variance สูงกว่าเดิมอยู่แล้ว การคูณด้วย √252 ซ้ำ (สมมติว่าเป็น daily obs) จะยิ่งดัน volatility ให้สูงเกินจริงไปอีก) — สองอย่างนี้รวมกันหมายความว่า **กองที่รายงาน NAV ไม่บ่อย มีแนวโน้มโชว์ทั้ง return และ volatility สูงเกินจริงอย่างเป็นระบบ (ไม่ใช่เพราะความเสี่ยงจริง)** ซึ่งกระทบ Chart 1-2 ตรงๆ เพราะ quadrant แบ่งด้วย return>0 และ vol เทียบ median — กองกลุ่มนี้เสี่ยงถูกจัดเข้ากลุ่ม "ผันผวนสูง" ผิดๆ จากข้อจำกัดของสูตร ไม่ใช่จากพฤติกรรมกองจริง

จุดนี้ README เขียนไว้แล้วในข้อ 5 ของ Known Limitations ว่า *"annualized return ใช้ 252/n_obs (กองที่รายงานห่างจะ annualize ไม่ตรงเป๊ะ — descriptive)"* — ก็คือรู้อยู่แล้วว่ามีปัญหานี้ แต่คำว่า "ไม่ตรงเป๊ะ" อาจทำให้เข้าใจว่าคลาดเคลื่อนเล็กน้อย ทั้งที่ตัวอย่างข้างบนแสดงว่าคลาดเคลื่อนได้ถึงเท่าตัว และไม่มีการพูดถึงเรื่องนี้ในแผนเลย (`MSCI_DASHBOARD_PLAN.md` Phase 4 ไม่มีคำเตือนนี้) — สองทางเลือกที่ทำได้:
1. **ยอมรับเป็น known limitation แบบมี disclaimer ชัดเจนกว่านี้** (บอกตัวเลขความคลาดเคลื่อนที่เป็นไปได้ + โชว์ `n_obs` หรือช่วงวันที่ครอบคลุมในหน้าเว็บให้ผู้ใช้ประเมินความน่าเชื่อถือเอง — ตอนนี้ `n_obs` มีอยู่แล้วใน `results.csv`/`rc["n"]` แต่**ไม่ถูกโชว์ที่ไหนในหน้าเว็บเลย** ทั้ง hover, ตาราง, หรือ metric card)
2. **แก้สูตรให้ annualize ด้วยระยะเวลาที่ผ่านไปจริง** เช่น `growth ** (config.TRADING_DAYS / trading_days_elapsed) - 1` โดย `trading_days_elapsed` นับจากช่วง NAVDate แรก-สุดท้ายของกองนั้น (business days) แทนจำนวน observation — ให้ผลตรงกับความเป็นจริงมากกว่า โดยเฉพาะกองกลุ่ม 601-1,100 จุด (~172 จาก 368 กอง ตามตารางกระจายจุดข้อมูลในแผน) ที่มีช่องว่างการรายงานเยอะกว่ากลุ่ม 1,100+ จุด

**จุดเล็กเสริม**: ลำดับการ dedupe ใน `nav_loader.py` ทำ tie-break ด้วย UpdateTime **ก่อน** กรอง NAV≤0/NaN ออก — เคสหายาก (แถวซ้ำ NAVDate ที่แถว UpdateTime ล่าสุดดันมี NAV เสีย/ว่าง ขณะที่แถวเก่ากว่ามี NAV ใช้ได้) จะทำให้ NAVDate จุดนั้นหายไปทั้งจุด ทั้งที่มีค่าที่ใช้ได้อยู่ในข้อมูลดิบ — severity ต่ำ (edge case, ตัดสินใจแบบไหนก็มีเหตุผลรองรับได้) แต่บันทึกไว้เผื่อเจอกองที่ n_obs ต่ำกว่าคาดผิดปกติ

---

## สรุปภาพรวม

โค้ดตรงกับแผนในระดับสูงมาก — filter 9 เงื่อนไข, การ join ด้วย NAVDate + cumulative-window compounding, winsorize แยกทีละ series, multi-factor ElasticNetCV/LassoCV/RidgeCV พร้อม StandardScaler ใน pipeline เดียว (กัน data leakage ถูกต้อง), นิยาม primary/secondary จาก |standardized coefficient|, quadrant coloring, threshold ตัวเลข 715/680/368 — ทั้งหมดนี้เขียนตรงตามที่ยืนยันไว้ในแผนแบบตรงไปตรงมา และมี `checkpoint1.py` + `tests/` ครอบคลุม Phase 1-4 ตาม unit test ที่แผนกำหนดไว้จริง

แต่พบ **จุดที่โค้ดไปไกลกว่าแผนโดยไม่ได้กลับมาอัปเดตแผน หรือเบี่ยงจากสิ่งที่ confirm ไว้แล้ว 4 จุด** (รายละเอียดด้านล่าง) และ **1 จุดที่ตัวเลขจะขัดแย้งกันเองในหน้าแรกได้ถ้ามีกองถูกข้าม** — ไม่มีจุดไหนทำให้แอป crash แต่มีผลต่อความถูกต้อง/ความสอดคล้องของข้อมูลที่แสดง ควรแก้ก่อนใช้งานจริง

หมายเหตุ: ระหว่างที่กำลังรีวิวรอบนี้ พบว่าไฟล์ `pages/1_🌍_Country_Match.py`, `pages/2_🏭_Sector_Match.py`, `pages/3_📊_Match_Strength.py` และ `page_common.py` (ใหม่) ถูกแก้ไขสดๆ อยู่ (น่าจะกำลัง refactor แยก logic ซ้ำออกมาเป็น `page_common.py`) — รีวิวนี้อ้างอิงจากไฟล์เวอร์ชันล่าสุดที่ดึงมาหลังนิ่งแล้ว (mtime คงที่ครั้งสุดท้าย) ไม่ใช่เวอร์ชันแรกที่เห็น

---

## ตรงตามแผน (ยืนยันแล้วว่าถูกต้อง)

- **Filter เงื่อนไข 9 ข้อ** (`config.FILTER_EQ/NEQ/EMPTY`) ตรงกับ Section 0 v2 ของแผนครบทุกข้อ คาด 715 กอง (E=600/F=77/O=38) — มี `checkpoint1.py` + `test_filters.py` assert ตัวเลขนี้ตรงๆ
- **Phase 2 (return series)**: `matching.build_fund_returns` ใช้ NAVDate join + reindex(ffill) ของ index level แล้ว pct_change — เท่ากับ compound ผลตอบแทน index ตลอดช่วงที่กองไม่รายงานอัตโนมัติ ตรงกับวิธีที่ยืนยันไว้ใน Phase 2 เป๊ะ (แก้ปัญหา gap + NAV lag พร้อมกันด้วยวิธีเดียว)
- **Winsorize**: clip 1st/99th percentile แยกทีละคอลัมน์ (`_winsorize` ใช้ `.apply()` ต่อคอลัมน์) ครอบคลุมทั้งกองทุนและ index ตรงตามแผน
- **Phase 3 (regression)**: `StandardScaler` อยู่ใน `Pipeline` เดียวกับ `ElasticNetCV/LassoCV/RidgeCV` — scaler ถูก fit ใหม่ทุก CV fold ตอนหา alpha (ไม่ leak), coefficient ที่ได้อยู่บนสเกล standardized เทียบข้าม index ได้ตรงตามที่ตั้งใจ
- **primary/secondary**: จัดอันดับจาก `|en_coef|` เฉพาะตัวที่ไม่เป็นศูนย์ ตรงตามนิยามที่เพิ่มในแผน Phase 3
- **Threshold ตัวเลข**: `EXPECTED_FILTERED_FUNDS=715`, `EXPECTED_WITH_NAV=680`, `EXPECTED_PASS_THRESHOLD=368`, `MIN_DATA_POINTS=600`, `TRADING_DAYS=252` ตรงกับแผนทุกตัว
- **Quadrant**: ตำแหน่ง/สี Q1(บนขวา,เขียว)/Q2(บนซ้าย,เหลือง)/Q3(ล่างซ้าย,แดง)/Q4(ล่างขวา,น้ำเงิน) ใน `viz.add_quadrant` ตรงกับสมมติฐาน Cartesian ที่ระบุไว้ในแผนเป๊ะ — แต่ยังเป็นสมมติฐานที่ผู้ใช้ยังไม่เคย confirm ชัดๆ (ดู "จุดที่ยังไม่ confirm" ด้านล่าง)
- **Chart 3 placeholder**: กองที่ ElasticNet ตัด coefficient เหลือ 0 หมด → `pages/3` โชว์ข้อความ "กองนี้ไม่พบ exposure ชัดเจน..." ตรงตามที่ confirm ไว้
- **โครงสร้างแยกโปรเจกต์**: ไม่มี import/อ้างอิงไฟล์ฝั่ง Fama French SET50 เลย, ทุก path อิงจาก `config.BASE_DIR` (ย้ายโฟลเดอร์ได้โดยไม่พัง) — Phase 6 recheck ข้อ "ไม่กระทบระบบเดิม" ผ่าน
- **Optional controls ใน Phase 5** (R² slider, Fund Policy multiselect, primary multiselect) ที่แผนระบุว่า "ไม่บังคับ" ก็ทำครบจริง

---

## จุดที่ควรแก้ (เรียงตามผลกระทบ)

### 1. ตัวเลข "368/715" ใน `app.py` เป็นค่า hardcode — จะขัดแย้งกับตัวเลขจริงถ้ามีกองถูกข้าม

`app.py` บรรทัด expander เขียนว่า `"ครอบคลุม 368/715 กอง (~51%)"` เป็น literal string ตรงๆ แต่ metric การ์ดด้านบนใช้ `len(results)` จริง (`c1.metric("กองที่วิเคราะห์", f"{len(results)}")`)

ปัญหาคือ `data_access.build_pipeline` มี guard เพิ่มที่ไม่มีในแผน (`MIN_REGRESSION_OBS = 30`, ดูข้อ 6 ด้านล่าง) และ `try/except` ที่ข้ามกองไปเงียบๆ ถ้า error — แปลว่าจำนวนกองที่ผ่านเข้า `results` จริงอาจ **น้อยกว่า 368** ได้ ถ้าเกิดเช่นนั้น หน้าแรกจะโชว์ตัวเลขสองค่าที่ขัดแย้งกันเองบนหน้าเดียวกัน (การ์ดบอกเช่น 350 กอง แต่ expander บอก 368/715)

**แนะนำ**: เปลี่ยนเป็น `f"ครอบคลุม {len(results)}/715 กอง ({len(results)/715:.0%})"` ให้อิงจากข้อมูลจริงเสมอ

### 2. Hover tooltip / ตารางใน Chart 1-2 โชว์ "—" แทนที่จะเป็น "ไม่พบ exposure ชัดเจน" ตามที่ confirm ไว้

แผน Phase 5 ระบุไว้ชัดว่า: *"hover tooltip ช่อง 'ประเทศที่ match' จะขึ้นข้อความ **'ไม่พบ exposure ชัดเจน'** แทนชื่อประเทศ"* (จุดนี้ confirm แล้วในแผน ไม่ใช่ข้อเสนอ)

แต่ `viz.short()` ที่ใช้สร้างคอลัมน์ `match` ในทั้ง `viz.scatter()` (hover) และตารางใน `page_common.scatter_page` เขียนว่า:
```python
if pd.isna(name):
    return "—"
```
กองที่ไม่มี primary/secondary จะโชว์ "—" ไม่ใช่ข้อความที่ confirm ไว้ — ตรงนี้ต่างจาก Chart 3 ที่ใช้ข้อความเต็มถูกต้อง (`viz.match_strength_bar` คืน `None` แล้ว `pages/3` โชว์ placeholder เต็มประโยค)

**แนะนำ**: แก้ `short()` ให้รับ fallback text เป็นพารามิเตอร์ หรือแก้ตรงจุดสร้างคอลัมน์ `match` ให้ map ค่า NaN เป็น `"ไม่พบ exposure ชัดเจน"` แทน `viz.short()`

### 3. Chart 3 มี model selector (elastic/lasso/ridge) ที่ทำให้ primary/secondary ไม่ตรงกับ Chart 1-2/ตาราง — เป็นการขยายขอบเขตเกินกว่าที่ confirm ไว้

แผน Phase 5 (ตอบคำถามล่าสุดของคุณ, confirm แล้ว) ระบุว่าแกน y ของ Chart 3 ใช้ **|standardized coefficient| จากโมเดล ElasticNet โดยเฉพาะ** เหตุผลตรงๆ คือให้ primary/secondary/แกน y เป็นตัวชี้วัดเดียวกันกับที่ใช้จัดอันดับใน Phase 3 (ซึ่งนิยามจาก ElasticNet เท่านั้น)

โค้ดจริงเพิ่ม radio "โมเดล: elastic/lasso/ridge" ใน `pages/3` แล้ว `viz.match_strength_bar()` **คำนวณ primary/secondary ใหม่จาก coefficient ของโมเดลที่เลือกเอง** (docstring ของ `match_strength_bar` บอกตรงๆ ว่า "ไม่ยึด ElasticNet") ผลคือ:
- ถ้าเลือกดู "ridge" ใน Chart 3 แท่งสีน้ำเงิน (primary) ที่โชว์ อาจเป็นคนละ index กับ `country_primary`/`sector_primary` ที่โชว์ใน Chart 1-2 และตารางผลลัพธ์ (ซึ่งอิงจาก ElasticNet เสมอ ไม่เปลี่ยนตามโมเดล)
- ไม่มีข้อความอธิบายในหน้าเว็บว่า primary/secondary ใน mode นี้คำนวณแยกจาก ElasticNet ผู้ใช้อาจสับสนว่าทำไม primary ไม่ตรงกันระหว่าง 2 หน้า

การรัน Lasso/Ridge เก็บไว้เปรียบเทียบตรงกับแผน (แผนบอกให้ "รันคู่ไว้เทียบ") แต่การให้ผู้ใช้สลับดูแล้ว **redefine primary/secondary ใหม่ตามโมเดลที่เลือก** เป็นการตัดสินใจที่ไม่มีในแผน และขัดกับเหตุผล "ใช้ตัวชี้วัดเดียวกันทั้งการจัดอันดับและความสูงแท่ง" ที่เพิ่ง confirm — ควรกลับไปคุยกับคุณก่อนว่าจะเก็บ behavior นี้ไว้ (แล้วเพิ่มคำอธิบายในหน้าเว็บว่า primary/secondary ของแต่ละโมเดลอาจต่างกัน) หรือจะให้สีอิงกับ `is_primary`/`is_secondary` ที่คำนวณจาก ElasticNet เพียงอย่างเดียว (คอลัมน์นี้มีอยู่แล้วใน `coefs.csv` จาก `data_access.py` แต่ `viz.py` เลือกไม่ใช้)

### 4. NAVDate tie-break ใช้ `UpdateTime` แทน `AsOfDate` — แก้ item 7 ในแผนไปแล้วโดยไม่ได้อัปเดตแผน/ถามยืนยัน

แผนข้อ "จุดที่ยังต้อง confirm" ข้อ 7 ยังเขียนว่า **"ยังไม่ confirm"** และเสนอ default เป็น "เก็บแถวที่ AsOfDate ล่าสุดไว้"

โค้ดจริง (`config.py`, `nav_loader.py`) ใช้ **`UpdateTime`** เป็น tie-break key แทน (`NAV_DEDUP_KEEP = "UpdateTime"`, และไม่ได้อ่านคอลัมน์ `AsOfDate` เข้ามาด้วยซ้ำ — `NAV_USECOLS` ไม่มี AsOfDate) พร้อม comment "confirmed 2026-09-01" ทั้งที่ในแผนยังไม่มีการ confirm นี้บันทึกไว้

ตรงนี้ไม่กระทบตัวเลข "368" (จำนวน NAVDate ที่ไม่ซ้ำต่อกองไม่เปลี่ยนตาม tie-break rule) แต่กระทบ **ค่า NAV ที่ถูกเลือกใช้จริง** เวลามีแถวชนกันที่ (FundCode, NAVDate) เดียวกัน ซึ่งอาจได้ผล regression ต่างจากถ้าใช้ AsOfDate ตามที่แผนเสนอไว้เดิม — ควรตัดสินใจให้ชัดว่าจะยึด UpdateTime (สมเหตุสมผลกว่า AsOfDate จริงๆ เพราะเป็น timestamp ละเอียดกว่า) แล้วอัปเดตแผนให้ตรงกับโค้ด หรือจะเปลี่ยนกลับ — อย่างไรก็ได้ แต่ตอนนี้แผนกับโค้ดไม่ตรงกัน

### 5. Dedup ด้วย `sort_values("_upd", ...)` ไม่ระบุ `kind="stable"` — เสี่ยง non-deterministic เวลามีแถว tie ที่ UpdateTime เท่ากันเป๊ะ (หรือ NaT ทั้งคู่)

`nav_loader.load_nav_history`:
```python
nav = nav.assign(_upd=upd).sort_values("_upd", na_position="first")
nav = nav.drop_duplicates(subset=[FUND, NAVDATE], keep="last")
```
`sort_values` ค่า default คือ `quicksort` ซึ่ง**ไม่ stable** ถ้ามีสองแถวขึ้นไปที่ (FundCode, NAVDate) ซ้ำกัน **และ** UpdateTime เท่ากันเป๊ะ (หรือ parse ไม่ได้เป็น NaT ทั้งคู่) ลำดับก่อน-หลังของแถวที่ tie กันไม่การันตีว่าเหมือนเดิมทุกครั้งที่รัน → ค่า NAV ที่ถูกเลือกเก็บไว้ (`keep="last"`) อาจสลับไปมาระหว่างการ build cache แต่ละรอบ ทำให้ผล regression ของกองที่เจอ tie แบบนี้ไม่ reproducible 100%

ไม่กระทบจำนวนกอง/จำนวนจุดข้อมูล (นับ NAVDate ไม่ซ้ำเท่าเดิม) แต่กระทบความสม่ำเสมอของตัวเลขระหว่างรัน — แก้ง่ายๆ ด้วยการเพิ่ม `kind="stable"` (หรือ `mergesort`) ใน `sort_values`

### 6. `MIN_REGRESSION_OBS = 30` เป็น guard ใหม่ที่ไม่มีในแผน (ของดี แต่ควรบันทึกไว้)

`data_access.build_pipeline` เพิ่มการเช็คว่า "in-window obs" (จำนวนจุดหลัง align กับช่วงที่ MSCI มีข้อมูลจริง) ต้อง ≥ 30 ไม่งั้นข้ามกองทั้งกอง (กัน `ElasticNetCV` ล้มหรือได้ผลไม่น่าเชื่อถือตอน cv=5 fold กับข้อมูลน้อยเกิน) — เป็นการตัดสินใจทางวิศวกรรมที่สมเหตุสมผลมาก และมี comment อธิบายเหตุผลชัดเจน แต่แผนไม่เคยพูดถึง guard ตัวนี้เลย ควรเพิ่มลงในแผน Phase 3 เพื่อให้แผนกับโค้ด sync กัน (และ record ไว้ว่าตัวเลขกองที่ผ่านเข้า dashboard จริงๆ อาจต่ำกว่า 368 เพราะ guard ตัวนี้ — เชื่อมกับปัญหาข้อ 1)

---

## จุดที่ยังไม่ confirm จากแผน (ยังค้างอยู่ ไม่ใช่บั๊ก แต่ควรตัดสินใจ)

- **Quadrant orientation (แผนข้อ 2)**: โค้ดใช้สมมติฐาน Q1=บนขวา ตามที่ระบุในแผน แต่คุณยังไม่เคย confirm ชัดๆ ว่าตรงกับที่นึกภาพไว้ — ถ้าใช่ตามนี้แล้วก็ปิดรายการนี้ได้เลย
- **NAVDate tie-break (แผนข้อ 7)**: ตามข้อ 4 ด้านบน — โค้ดเลือก UpdateTime ไปแล้วโดยไม่รอ confirm

---

## Recheck ตาม 3 ข้อบังคับของโปรเจกต์

1. **โค้ดที่เพิ่งเขียนถูกต้องหรือไม่**: ตรวจ logic ทีละไฟล์แล้ว (Phase 1-5 ทั้งหมด) ถูกต้องตามสเปกเป็นส่วนใหญ่ ยกเว้น 6 จุดที่ระบุไว้ข้างบน — ไม่มีจุดไหนทำให้แอป error/crash แต่มีผลต่อความถูกต้อง/ความสอดคล้องของตัวเลขที่แสดง
2. **ระบบเดิม (Fama French SET50) ไม่กระทบ**: ยืนยันแล้ว — ไม่มี import หรือแก้ไฟล์ฝั่งนั้นเลย โฟลเดอร์แยกกันสมบูรณ์
3. **โครงสร้างโดยรวมยังสมเหตุสมผล**: ใช่ — แยก data/analysis/pages/config ชัดเจนตาม pattern เดิม, มี `page_common.py` ลด duplication ระหว่างหน้า scatter (ดีขึ้นจากที่เคยเป็น), มี `checkpoint1.py` + `tests/` ครบตามที่แผนกำหนด ไม่ซับซ้อนเกินจำเป็น

**หมายเหตุเรื่องการรัน pytest จริง**: พยายามรัน `./.venv/bin/pytest` ผ่าน remote shell แต่ venv ของโปรเจกต์อ้างอิง path ของ Anaconda บนเครื่อง Mac จริง (`/opt/anaconda3/bin/python3.12`) ซึ่ง remote shell (sandboxed VM) มองไม่เห็น เลยรันให้ไม่ได้จากฝั่งนี้ — รีวิวนี้จึงอิงจากการอ่าน logic ตรงๆ (เทียบสูตร/edge case ด้วยมือ) ไม่ใช่ผลรัน test จริง แนะนำให้รัน `./.venv/bin/python -m pytest -q` และ `./.venv/bin/python checkpoint1.py` เองอีกรอบเพื่อ confirm ว่า assert ทั้งหมดผ่านจริงบนเครื่อง
