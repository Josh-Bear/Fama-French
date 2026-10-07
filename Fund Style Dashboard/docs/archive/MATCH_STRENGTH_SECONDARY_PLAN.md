# แผนแก้ไข: นิยาม "secondary" ใหม่ — หน้า 3 (Match Strength)

สถานะ: **ตกลง scope + threshold แล้ว รอ implement** — แก้ทีละหน้า เริ่มที่หน้า 3 ก่อน (หน้า 5 แยกแผนทีหลัง)

## 1. ปัญหาของนิยามเดิม

`viz.match_strength_bar()` (ที่หน้า 3 เรียกใช้) นิยาม primary/secondary แบบ **rank-based ตายตัว**:

```python
sub = sub.reindex(sub[model].abs().sort_values(ascending=False).index)
color = ([PRIMARY_C, SECONDARY_C] + [OTHER_C] * len(sub))[:len(sub)]
# แถวแรก (rank 1) = primary เสมอ, แถวสอง (rank 2) = secondary เสมอ, ที่เหลือ = อื่นๆ
```

ปัญหา: กองที่มี exposure หลัก **หลายตัวใกล้เคียงกัน** (เช่น ABAGS ที่ MSCI_WORLD_EX_US / MSCI_ACWI / MSCI_WORLD / MSCI_EUROPE มี |coefficient| ใกล้กันมาก) จะเห็นแค่ตัวที่ 2 เป็นสีเขียว (secondary) ส่วนตัวที่ 3-4 ที่ค่าใกล้เคียงกันมากกลับถูกจัดเป็น "อื่นๆ" (สีเทา) ทั้งที่ exposure จริงแรงพอกัน — ตัวเลขอันดับ (rank) เพียวๆไม่ได้สื่อว่า "ใกล้ primary แค่ไหน"

## 2. นิยามใหม่ — band-based (ยืนยันกับ Josh แล้ว)

**Secondary = ทุก index (นอกจาก primary) ที่ `|coefficient| ≥ |primary coefficient| × (1 − 30%)`**

- Primary ยังคงเป็น index ที่ `|coefficient|` มากที่สุดเสมอ (ไม่เปลี่ยน)
- Secondary เปลี่ยนจาก "ได้แค่ 1 ตัวตายตัว" → **ได้ 0, 1, 2, หรือมากกว่าตัวก็ได้** ขึ้นกับข้อมูลจริงของกองนั้น
- เทียบด้วย `|coefficient|` (absolute value) เหมือนเดิม → **นับรวมทั้งเครื่องหมายบวกและลบ** โดยอัตโนมัติ (ยืนยันด้วยข้อมูลจริงแล้ว — ดู §5)
- ที่เหลือ (นอกจาก primary + secondary) = "อื่นๆ" (สีเทา) เหมือนเดิม

**X = 30%** เลือกจากการเช็คกระจายตัวจริงของ `cache/coefs.csv` (368 กอง × 2 scope):

| X% band | avg secondary/กอง | %กองไม่มี extra | %กองมี ≥2 secondary | %กองมี ≥4 secondary |
|---|---|---|---|---|
| 10% | 0.11 | 90.0% | 0.7% | 0.0% |
| 20% | 0.26 | 77.9% | 3.6% | 0.0% |
| **30%** | **0.48** | **63.6%** | **9.0%** | **0.1%** |
| 50% | 1.13 | 40.9% | 34.0% | 4.2% |
| 70% | 2.36 | 17.3% | 63.4% | 25.0% |

30% ให้ผลลัพธ์ที่มีความหมาย (9% ของกองได้ secondary เพิ่มจริง ส่วนใหญ่ 2-3 ตัว) โดยไม่ระเบิดจนกลายเป็น "แทบทุก index non-zero กลายเป็น secondary" (แบบที่เกิดตอน X=70%)

## 3. โค้ดที่ต้องแก้ — `matching.py` (ฟังก์ชันกลางใหม่) + `viz.py` (เรียกใช้)

**อัปเดต (2026-09-09, หลัง recheck คู่กับแผนหน้า 5)**: ย้าย logic การจัด primary/secondary ออกมาเป็น**ฟังก์ชันกลาง**ใน `matching.py` แทนที่จะเขียน inline ใน `viz.py` เพราะหน้า 5 (`PAGE5_VOL_RETURN_PLAN.md` §4.2) ต้องใช้ logic เดียวกันนี้ในการกรองกองทุนตอนคลิก index — ถ้าเขียน inline ไว้ที่ `viz.py` อย่างเดียว หน้า 5 จะต้อง copy logic ซ้ำ แล้วพอแก้ threshold ทีหลังต้องแก้ 2 ที่

เพิ่มใน `analysis/matching.py`:
```python
def classify_exposure(fund_coefs: pd.Series, band_pct: float | None = None) -> tuple[str | None, list[str]]:
    """fund_coefs: Series index=ชื่อ index, values=coefficient (ของโมเดลเดียว, ไม่ได้กรอง zero มาก่อนก็ได้)
    คืน (primary, secondary_list) — secondary_list มีได้ 0..N ตัว ตาม band_pct (ไม่ใช่ rank-based top-2 แบบเดิม)
    """
    band_pct = config.SECONDARY_BAND_PCT if band_pct is None else band_pct
    nz = fund_coefs[fund_coefs.abs() > 1e-9].abs().sort_values(ascending=False)
    if len(nz) == 0:
        return None, []
    primary = nz.index[0]
    band_lo = nz.iloc[0] * (1 - band_pct)
    secondary = [ix for ix, v in nz.iloc[1:].items() if v >= band_lo]
    return primary, secondary
```

แก้ `viz.match_strength_bar()` ให้เรียกใช้ฟังก์ชันนี้แทน inline logic เดิม:
```python
def match_strength_bar(coefs: pd.DataFrame, fundcode: str, scope: str, model: str) -> go.Figure | None:
    sub = coefs[(coefs["FundCode"] == fundcode) & (coefs["scope"] == scope)].copy()
    sub = sub[sub[model].abs() > 1e-9]
    if sub.empty:
        return None
    sub = sub.reindex(sub[model].abs().sort_values(ascending=False).index)

    fc = sub.set_index("index")[model]
    primary, secondary = matching.classify_exposure(fc)   # << เรียกฟังก์ชันกลาง ไม่คำนวณ threshold ซ้ำที่นี่
    # เทียบด้วยชื่อ index (ไม่ใช่ position) กันเคส tie/ลำดับคลาดเคลื่อน
    color = [PRIMARY_C if i == primary else SECONDARY_C if i in secondary else OTHER_C for i in sub["index"]]

    fig = go.Figure(go.Bar(
        x=[short(i, scope) for i in sub["index"]], y=sub[model], marker_color=color,
        hovertemplate="%{x}: %{y:.3f}<extra></extra>"))
    fig.update_layout(yaxis_title=f"{model} standardized coefficient", xaxis_title="",
                      title=f"{fundcode} — {scope} exposure (🔵 primary · 🟢 secondary (±30%) · ⚪ อื่นๆ)")
    return fig
```

เพิ่ม constant ใน `config.py` (ตาม convention เดิมของโปรเจกต์ที่รวมค่าคงที่ไว้ที่เดียว):

```python
# --- Match Strength (หน้า 3) — secondary แบบ band-based ---
SECONDARY_BAND_PCT = 0.30   # secondary = |coef| >= primary * (1 - 30%) — ยืนยันจาก coefs.csv จริง (2026-09-09)
```

**ไม่ต้องแก้ที่อื่นเพิ่ม**: ไม่แก้ `data_access.py`, ไม่ต้อง rebuild `cache/coefs.csv`/`cache/results.csv` — `match_strength_bar()`/`classify_exposure()` อ่าน `coefs` (raw coefficient ทุก index ที่ไม่ใช่ศูนย์) มาคำนวณ primary/secondary **สดๆ เองอยู่แล้ว** ไม่ได้พึ่ง field `is_secondary` ที่ pipeline คำนวณไว้ล่วงหน้าแต่อย่างใด (แก้ `matching.py` แค่เพิ่มฟังก์ชันใหม่ ไม่แก้ฟังก์ชันเดิม `match_exposure()` ที่ pipeline ใช้อยู่ — ไม่กระทบ cache)

## 4. ผลกระทบต่อหน้าอื่น — **ไม่มีเลย** (verify จากโค้ดจริงแล้ว)

| หน้า | ใช้ secondary จากไหน | กระทบไหม |
|---|---|---|
| หน้า 1 (Country Match) | `results["country_secondary"]` (จาก `matching.py`, แสดงในตาราง expander เท่านั้น ไม่ใช้ filter/สี) | **ไม่กระทบ** — คนละ field, คนละฟังก์ชัน |
| หน้า 2 (Sector Match) | เหมือนหน้า 1 (`sector_secondary`) | **ไม่กระทบ** |
| หน้า 3 (Match Strength) | `viz.match_strength_bar()` คำนวณสดจาก `coefs` | **นี่คือจุดที่แก้** |
| หน้า 4 (Vol Forecast) | ไม่เกี่ยวกับ primary/secondary เลย | ไม่กระทบ |
| `cache/results.csv`, `cache/coefs.csv` | ไม่แก้ schema/pipeline | **ไม่ต้อง rebuild cache** |

## 5. Edge case ที่เช็คแล้ว

- **เครื่องหมายบวก/ลบ**: ใช้ `|coefficient|` เทียบ band → นับรวมทั้งสองฝั่งอัตโนมัติ (verify จริงแล้ว: เจอ 72 กรณีจาก 368×2 ที่ secondary มีเครื่องหมายตรงข้าม primary แต่ขนาดใกล้เคียงกัน เช่น ABAGS: primary=MSCI_WORLD_EX_US **+0.0189**, secondary=MSCI_ACWI **−0.0160** — 0.0160/0.0189≈85% เกิน 70% ผ่านเกณฑ์)
- **กองที่มี exposure เดียว** (`len(nz)==1`): `nz.iloc[1:]` เป็น Series ว่าง → `secondary = []` → ไม่ error, มีแค่ primary สีเดียว (เหมือนพฤติกรรมเดิม)
- **กองที่ไม่มี exposure เลย** (`sub.empty` ก่อนเข้า `classify_exposure`): คืน `None` เหมือนเดิม (ไม่เปลี่ยน — เช็คที่ `match_strength_bar()` เหมือนเดิม ไม่ได้ย้ายไปเช็คใน `classify_exposure`)
- **ตัวเลือกโมเดล lasso/ridge**: `classify_exposure(fc)` รับ `fc` จาก column `model` ที่เลือกเอง (ไม่ hardcode elastic) → สอดคล้องกันทั้ง 3 โมเดลเหมือนเดิม
- **เทียบด้วยชื่อ (`i == primary`, `i in secondary`) ไม่ใช่ position**: กันเคสที่ลำดับการ sort ของ `sub` (ใน `viz.py`) กับลำดับภายใน `classify_exposure()` อาจไม่ตรงกันเป๊ะเวลามี tie (ค่า |coef| เท่ากันพอดี) — ใช้ชื่อ index จับคู่แทนตำแหน่ง ปลอดภัยกว่า

## 6. Recheck ตามธรรมเนียมโปรเจกต์ (3 เรื่อง) — แผนตรวจสอบก่อนถือว่าเสร็จ

1. **โค้ดใหม่ถูกต้อง**: ทดสอบกับกองที่รู้ผลอยู่แล้วจาก §2 (เช่น ABAGS ที่ scope=country ควรได้ secondary 3 ตัว: MSCI_ACWI, MSCI_WORLD, MSCI_EUROPE) เทียบกับสีที่ขึ้นจริงบนกราฟ
2. **ระบบเดิมไม่พัง**: เปิดหน้า 1, 2 เช็คว่าตาราง/filter/กราฟเหมือนเดิมทุกอย่าง (ควรจะเหมือนเป๊ะ เพราะไม่ได้แก้โค้ดที่เกี่ยวข้อง) + เปิดหน้า 3 กับกองที่ secondary เดิมมีแค่ 1 ตัว (เช่นกอง fixed income ทั่วไป) ควรได้ผลเหมือนก่อนแก้
3. **โครงสร้างรวมยังสมเหตุสมผล**: การแก้ครั้งนี้เพิ่ม constant 1 ตัวใน config.py + แก้ logic ในฟังก์ชันเดียวใน viz.py — ไม่เพิ่มความซับซ้อนเชิงโครงสร้าง (ไม่เพิ่ม cache ใหม่ ไม่เพิ่ม dependency ใหม่ ไม่แก้ pipeline)

## 7. ขั้นต่อไป (แยกเป็นงานถัดไป — ยังไม่ทำตอนนี้)

หน้า 5 (Country/Sector Vol-Return scatter + fund filter ด้วย band-based secondary เดียวกันนี้) — วางแผนแยกทีหลัง ตามที่ Josh บอกว่า "แก้ทีละหน้า"
