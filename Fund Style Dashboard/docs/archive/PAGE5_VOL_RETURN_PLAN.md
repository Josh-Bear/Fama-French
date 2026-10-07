# แผนหน้า 5 — 📉 Vol-Return Scatter (Country/Sector) + Fund Drill-down

สถานะ: **แผนละเอียด รอ review ก่อน implement** — ต่อจาก `VOL_FORECAST_PLAN.md` (หน้า 4) และ `MATCH_STRENGTH_SECONDARY_PLAN.md` (หน้า 3)

## 0. สรุปสิ่งที่ตกลงกันแล้ว (จากบทสนทนา)

| ส่วน | ข้อสรุป |
|---|---|
| Layout | 2 กราฟข้างกัน — **ซ้าย = country (18 index)**, **ขวา = sector (10 index)** |
| แกน x | **return 21 trading days ล่าสุด** ของ index (ราคาดิบ ไม่ annualize) = `P(t)/P(t−21)−1` |
| แกน y | **forecast vol จาก GARCH(1,1), dist=Student-t เท่านั้น** (ไม่มี EWMA, ไม่มี toggle) — ไม่ winsorize/clean ข้อมูลเพิ่ม |
| Quadrant | 4 สีเหมือนหน้า 1,2 — เส้นแบ่ง **x=0 (แนวตั้ง)** + **y=median forecast vol แยกคำนวณต่อกราฟ** (median ของ 18 ตัว กับ median ของ 10 ตัว แยกกัน) |
| Interaction | คลิกจุด (index) บนกราฟ → filter กองทุนที่ match กับ index นั้นในช่องด้านล่าง |
| Fund filter scope | **primary + secondary รวมกัน** โดย secondary = **band-based (X=30%)** เหมือนหน้า 3 (ดู §4) |
| Fund ranking | **rank by return 21 วันล่าสุด อย่างเดียว** (สูง→ต่ำ) ไม่มี metric อื่นปน |

**Dependency สำคัญ — ต้องทำก่อน**:
1. หน้า 4: เปลี่ยน `garch_forecast()` ใน `vol_forecast.py` เป็น `dist="t"` แล้ว rebuild cache (`cache/vol_forecast_*.csv`) — งานนี้ยังไม่ได้ทำ (คุยกันแค่ระดับ execute ทดสอบ ยังไม่แก้ไฟล์จริง)
2. หน้า 3: ทำ band-based secondary (`SECONDARY_BAND_PCT`) ให้เสร็จก่อน แล้ว**แยกเป็นฟังก์ชันกลาง**ให้หน้า 5 เรียกใช้ซ้ำได้ (ไม่ copy logic) — ดู §4.2

ถ้ายังไม่ทำ 2 อย่างนี้ หน้า 5 จะ "วางแผนเสร็จ แต่ implement ไม่ได้จริง" เพราะขาด input data (forecast vol ยังเป็น Normal-dist, secondary ยังเป็น rank-based)

---

## 1. โครงสร้างข้อมูลที่ต้องมี (เทียบกับที่มีอยู่แล้ว)

| ข้อมูลที่ต้องใช้ | มีอยู่แล้วไหม | ต้องทำอะไรเพิ่ม |
|---|---|---|
| forecast vol ต่อ index (28 ตัว) | มีแล้ว (`cache/vol_forecast_latest.csv` คอลัมน์ `garch_forecast`) | **ต้องเปลี่ยนเป็น t-dist** (dependency #1) — คอลัมน์เดิม ไม่ต้องเพิ่ม schema |
| return 21 วันล่าสุดของ **index** | ไม่มี — ต้องคำนวณใหม่ | คำนวณสดจาก MSCI price level ตอนโหลดหน้า (เบา ไม่ต้อง cache ลง disk ก็ได้ — ดู §2.1) |
| return 21 วันล่าสุดของ **กองทุน** (368 กอง) | ไม่มี — ต้องคำนวณใหม่ | **ต้องเพิ่มคอลัมน์ใหม่ใน `results.csv`** (คำนวณใน `build_pipeline()` เลย ใช้ nav ที่โหลดอยู่แล้ว ไม่อ่าน nav ใหม่ — ดู §2.2) |
| primary/secondary (band-based) ต่อกอง-ต่อ index | มีแบบ rank-based เดิม | ใช้ฟังก์ชันกลางที่แยกออกมาจากงานหน้า 3 (§4.2) — ไม่คำนวณซ้ำ |

### 1.1 ทำไม return 21 วันของ "index" ไม่ต้อง cache แต่ของ "กองทุน" ต้อง cache

- Index: อ่านจาก `msci_index.load_country_index()`/`load_sector_index()` ซึ่งเป็นไฟล์เล็ก (1456 แถว × 28 คอลัมน์) โหลดเร็วมาก (<1 วิ) — คำนวณสดตอนเปิดหน้าได้สบาย ไม่จำเป็นต้องมี cache แยก (แค่ wrap `@st.cache_data` กันคำนวณซ้ำเวลา rerun)
- กองทุน: ต้องมาจาก `nav_history_db.csv` (336MB) ซึ่ง**ช้ามาก**ถ้าอ่านสดทุกครั้งที่เปิดหน้า/คลิกจุด — **ต้องคำนวณครั้งเดียวตอน `build_pipeline()`** (ซึ่งอ่าน nav อยู่แล้ว) แล้วเก็บลง `results.csv` เหมือน `ann_return`/`ann_vol`

## 2. Implementation — ไฟล์ที่ต้องแก้/เพิ่ม

### 2.1 `analysis/metrics.py` — เพิ่มฟังก์ชันคำนวณ return ช่วงสั้น

```python
def recent_return(series, window: int | None = None) -> float:
    """cumulative return ดิบ (ไม่ annualize) ของ window ค่าล่าสุด — ใช้กับทั้ง price level และ NAV.

    series: pd.Series ของราคา/NAV (ไม่ใช่ return) — index เป็นวันที่ (ไม่ต้องเรียงมาก่อนเรียก ฟังก์ชัน sort เอง)
    ต้องมีอย่างน้อย window+1 จุด ไม่งั้นคืน NaN (กันกองใหม่/ข้อมูลสั้นเกิน)
    """
    window = config.RECENT_RETURN_WINDOW if window is None else window
    s = series.sort_index().dropna()   # << sort_index() เสมอ — กัน series ดิบที่ไม่เรียงตามวันที่ (ดู §2.2)
    if len(s) < window + 1:
        return np.nan
    return float(s.iloc[-1] / s.iloc[-(window + 1)] - 1.0)
```

**แก้จาก recheck (2026-09-09)**: ตอนแรกเขียนแค่ `series.dropna()` ไม่ sort — เจอบั๊กจริงตอน recheck: `fn` ที่ `build_pipeline()` ส่งมา (`nav_by_fund[f]`) มาจาก `nav.groupby(FUND)` ซึ่ง**ไม่การันตีเรียงตามวันที่** (หลักฐาน: `matching.build_fund_returns()` ที่ใช้ `fn` ตัวเดียวกันมีบรรทัดแรกเป็น `fund_nav.sort_index()` โดยเจตนา — แปลว่า `fn` ดิบไม่เรียงมาก่อน) ถ้าไม่ sort ใน `recent_return()` เอง `iloc[-1]`/`iloc[-22]` จะไม่ใช่ "ล่าสุด"/"22 จุดก่อนล่าสุด" จริง ได้ค่าผิดแบบสุ่ม — แก้โดยให้ฟังก์ชัน sort defensively เอง (ปลอดภัยกว่าหวังให้ทุกจุดที่เรียกจำ sort ก่อน)

เพิ่ม `RECENT_RETURN_WINDOW = 21` ใน `config.py` (sync กับ `VOL_FORECAST_HORIZON` โดยตั้งใจ — คนละชื่อเพราะความหมายคนละอัน: อันนี้คือ "ผ่านมาแล้ว" ไม่ใช่ "อนาคต")

**หมายเหตุสำคัญ (ต้องบอกไว้ตรงๆ)**: สำหรับกองทุน `series.iloc[-(window+1)]` คือ **นับจาก NAV observation ที่ 22 จากท้าย** ไม่ใช่ "21 วันทำการตามปฏิทินจริง" ถ้ากองมี NAVDate ไม่ครบทุกวันทำการ (บางกองรายงานไม่ทุกวัน) ตัวเลขนี้จะคลาดเคลื่อนจาก "21 วันตลาดจริง" ไปบ้าง — **เป็นข้อจำกัดเดียวกับที่ document ไว้แล้วใน README ข้อ 5** (n_obs ไม่ใช่วันทำการที่ผ่านจริง) ไม่ใช่ปัญหาใหม่ แค่สืบทอดข้อจำกัดเดิมมาใช้กับ metric ใหม่นี้ด้วย — ส่วน index (MSCI) ไม่มีปัญหานี้เพราะข้อมูลครบทุกวันทำการอยู่แล้ว (verify แล้วตอน Phase 1 recheck: ไม่มี NaN ใน MSCI levels)

### 2.2 `data_access.py` — เพิ่มคอลัมน์ `return_21d` ใน `build_pipeline()`

ในลูปต่อกอง (จุดที่คำนวณ `ann_return`/`ann_vol` อยู่แล้ว) เพิ่ม:

```python
"return_21d": metrics.recent_return(fn),   # fn = nav_by_fund[f] ที่โหลดอยู่แล้ว ไม่อ่าน nav ใหม่
```

**ผลกระทบ**: เพิ่ม column ใหม่ใน `results.csv` เท่านั้น (ไม่แก้/ลบ column เดิม) → **หน้า 1,2,3,4 ไม่กระทบ** (อ่าน column ที่มีอยู่เหมือนเดิม ไม่สน column ใหม่ที่เพิ่มมา) แต่ **ต้อง rebuild cache หนึ่งครั้ง** (`./.venv/bin/python data_access.py` หรือปุ่ม Rebuild) ก่อนหน้า 5 จะใช้งานได้ (คอลัมน์นี้ไม่มีใน `results.csv` เก่า)

### 2.3 `analysis/vol_forecast.py` หรือไฟล์ใหม่เล็กๆ — helper คำนวณ return 21 วันของ index

ไม่ต้องเพิ่มไฟล์ใหม่ทั้งไฟล์ — เพิ่มฟังก์ชันเล็กๆใน `data_access.py` (เพราะเป็น UI-layer helper เฉพาะหน้า 5 ไม่ใช่ core pipeline):

```python
def _load_index_snapshot() -> pd.DataFrame:
    """หน้า 5: return 21d (ราคาดิบ) + forecast vol ล่าสุด ต่อ index — คำนวณสด (เบา ไม่ cache ลง disk)."""
    cty = msci_index.load_country_index()
    sec = msci_index.load_sector_index()
    scope_map = {c: "country" for c in cty.columns}
    scope_map.update({c: "sector" for c in sec.columns})
    levels = pd.concat([cty, sec], axis=1)

    vol_latest = _load_vol_latest().set_index(["scope", "index"])  # ใช้ cache เดิม (garch_forecast, t-dist)
    rows = []
    for ix in levels.columns:
        rows.append({
            "scope": scope_map[ix], "index": ix,
            "return_21d": metrics.recent_return(levels[ix]),
            "vol_forecast": vol_latest.loc[(scope_map[ix], ix), "garch_forecast"],
        })
    return pd.DataFrame(rows)


get_index_snapshot = st.cache_data(_load_index_snapshot)   # อยู่ในบล็อก try/except streamlit เดิม
```

**ทำไมไม่ใช้ `ewma_forecast`/fallback**: ตามที่ยืนยันแล้ว หน้า 5 ใช้ **GARCH(t) เท่านั้น** ไม่สนใจ EWMA — แต่ต้องรู้ตัว: ถ้า dependency #1 (เปลี่ยน dist เป็น t) ยังไม่เสร็จ คอลัมน์ `garch_forecast` ใน cache จะยังเป็นค่า Normal-dist เดิมอยู่ (โค้ดหน้า 5 จะรันได้ แต่ตัวเลขจะไม่ตรงตามที่ตั้งใจ — ต้อง rebuild cache หลัง dependency #1 เสร็จก่อนใช้งานจริง)

## 3. หน้าเว็บ — `pages/5_📉_Vol_Return_Scatter.py` (ชื่อไฟล์เดา ปรับได้)

### 3.1 โครงหน้า

```
[Title + caption อธิบาย axis]

┌─────────────────────────┐  ┌─────────────────────────┐
│  🌍 Country (18 index)   │  │  🏭 Sector (10 index)     │
│  scatter: x=return21d    │  │  scatter: x=return21d    │
│  y=vol forecast (GARCH-t)│  │  y=vol forecast (GARCH-t)│
│  4-quadrant สี            │  │  4-quadrant สี            │
└─────────────────────────┘  └─────────────────────────┘

[ถ้าคลิกจุดฝั่ง country]        [ถ้าคลิกจุดฝั่ง sector]
📋 กองทุนที่ match กับ <index>   📋 กองทุนที่ match กับ <index>
(ตาราง: FundCode, FundName, primary/secondary, return_21d)
เรียง return_21d มาก→น้อย
```

**ตัดสินใจ (ขอเสนอ ไม่ใช่ที่ตกลงไปแล้ว — ต้อง confirm)**: แต่ละกราฟมีช่อง fund-list **ของตัวเอง** อยู่ใต้กราฟตัวเอง (ไม่ผสมกัน) — เพราะถ้าคลิกทั้งฝั่ง country และ sector พร้อมกัน จะสับสนว่าช่องข้างล่าง (ที่คุณอยากได้แค่ 1 ช่อง) ควรโชว์อันไหน ถ้าอยากได้ช่องเดียวรวมทั้งสองฝั่ง (เช่น คลิกกราฟไหนล่าสุด โชว์อันนั้น) บอกได้ จะปรับแผนให้

### 3.2 กราฟ (`viz.py` — ฟังก์ชันใหม่ `vol_return_scatter`)

```python
def vol_return_scatter(df: pd.DataFrame, scope: str) -> go.Figure:
    """scatter: x=return_21d, y=vol_forecast, สี=4 quadrant (x=0, y=median ของ df นี้), คลิกได้."""
    vol_med = df["vol_forecast"].median()
    colors = [_quadrant_color(r, v, 0.0, vol_med) for r, v in zip(df["return_21d"], df["vol_forecast"])]
    fig = go.Figure(go.Scatter(
        x=df["return_21d"], y=df["vol_forecast"], mode="markers",
        marker=dict(color=colors, size=12),
        customdata=df["index"],                       # << ใช้ระบุว่าคลิกจุดไหน
        text=[short(i, scope) for i in df["index"]],
        hovertemplate="%{text}<br>return 21d: %{x:.1%}<br>forecast vol: %{y:.1%}<extra></extra>",
    ))
    fig.add_vline(x=0, line_dash="dash", line_color="gray")
    fig.add_hline(y=vol_med, line_dash="dash", line_color="gray")
    fig.update_layout(xaxis_title="return 21 วันล่าสุด", yaxis_title="forecast vol (GARCH, t-dist)")
    return fig
```

(ใช้ `_quadrant_color` helper เดียวกับที่ `viz.scatter()` ของหน้า 1,2 มีอยู่แล้ว — ถ้ายังไม่มีเป็นฟังก์ชันแยก ต้อง refactor ดึงออกมาก่อน เพื่อไม่ copy logic สี 4 quadrant ซ้ำ)

### 3.3 การคลิกจุด — ใช้ Streamlit native selection (ยืนยันแล้วว่ารองรับ)

เช็คแล้วว่า **Streamlit ที่ลงในเครื่องคือ v1.62.0** (`.venv/lib/python3.12/site-packages/streamlit-1.62.0.dist-info`) — รองรับ `st.plotly_chart(..., on_select="rerun")` แบบ native (เพิ่มมาตั้งแต่ 1.35) **ไม่ต้องลง package เสริม** (`streamlit-plotly-events`) เพิ่ม

```python
event = st.plotly_chart(fig, key=f"scatter_{scope}", on_select="rerun",
                        selection_mode="points", use_container_width=True)
clicked = None
if event and event["selection"]["points"]:
    clicked = event["selection"]["points"][0]["customdata"]   # ชื่อ index ที่คลิก เช่น "MSCI_JAPAN"
```

**แก้จาก recheck (2026-09-09)**: ยืนยันแล้วแค่ว่า Streamlit เวอร์ชันนี้**รองรับ feature `on_select`** — ยังไม่ได้ verify **รูปแบบ object ที่คืนมาจริงเป๊ะๆ** (dict-access `event["selection"]["points"]` แบบข้างบน หรือ attribute-access `event.selection.points` — เอกสาร Streamlit บางเวอร์ชันให้ทั้งสองแบบ) **ต้องเช็คจริงตอน implement** (print(event) ดูโครงสร้างก่อนเขียน logic ต่อ) ไม่ใช่ยึดตามโค้ดนี้ 100%

### 3.4 Fund filter panel (ใต้กราฟที่ถูกคลิก)

```python
if clicked:
    scope_coefs = coefs[(coefs["scope"] == scope) & (coefs["index"] == clicked)]
    # primary: fund ที่ index นี้ = primary ของกอง
    # secondary (band-based): ใช้ฟังก์ชันกลางจากหน้า 3 (§4.2) ไม่คำนวณ threshold ซ้ำที่นี่
    matched_funds = get_funds_matching_index(coefs, clicked, scope)   # << ฟังก์ชันกลาง
    show = results[results["FundCode"].isin(matched_funds)][
        ["FundCode", "FundName", "policy", "return_21d"]
    ].sort_values("return_21d", ascending=False)
    st.subheader(f"📋 กองทุนที่ match กับ {clicked} (primary + secondary)")
    st.dataframe(show, use_container_width=True, hide_index=True)
```

## 4. Fund filter logic — เชื่อมกับงานหน้า 3 (สำคัญ ต้องอ่านคู่กับ `MATCH_STRENGTH_SECONDARY_PLAN.md`)

### 4.1 ทำไมต้องรอหน้า 3 เสร็จก่อน

หน้า 3 กำลังจะเปลี่ยนนิยาม "secondary" จาก rank-based (top-2 ตายตัว) เป็น band-based (≥70% ของ primary) — ตกลงกันไว้แล้วว่าหน้า 5 จะใช้นิยามเดียวกัน (เพื่อความ consistent ระหว่างสองหน้าที่พูดถึง exposure เดียวกัน) **ถ้าหน้า 5 implement ก่อนหน้า 3 จะต้องเขียน logic threshold ซ้ำ 2 ที่ (`viz.match_strength_bar()` และหน้า 5) แล้วพอหน้า 3 เสร็จ ต้องย้อนมาแก้หน้า 5 อีกที** — เสียเวลาซ้ำซ้อน จึงเสนอให้ **หน้า 3 เสร็จก่อน แล้วดึง logic ออกมาเป็นฟังก์ชันกลาง** ให้หน้า 5 เรียกใช้ทีเดียว

### 4.2 ฟังก์ชันกลางที่ต้องแยกออกมา (ระหว่างทำหน้า 3 ให้ทำจุดนี้ไปด้วย)

เสนอเพิ่มใน `analysis/matching.py` (อยู่กับ logic exposure อื่นๆอยู่แล้ว):

```python
def classify_exposure(fund_coefs: pd.Series, band_pct: float | None = None) -> tuple[str | None, list[str]]:
    """fund_coefs: Series index=index name, values=coefficient (ของ model เดียว, ทุก index ที่ไม่ใช่ 0)
    คืน (primary, secondary_list) — secondary_list มีได้ 0..N ตัว ตาม band_pct
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

- **หน้า 3** (`viz.match_strength_bar()`) เรียกใช้แทน logic ที่เขียนไว้ใน `MATCH_STRENGTH_SECONDARY_PLAN.md` §3 (ปรับ plan นั้นเล็กน้อยให้ดึงมาเป็นฟังก์ชันกลางนี้ แทนที่จะเขียน inline ใน `viz.py`)
- **หน้า 5** เรียกใช้แบบนี้ต่อ index ที่คลิก (`get_funds_matching_index`):

```python
def get_funds_matching_index(coefs: pd.DataFrame, index_name: str, scope: str) -> list[str]:
    """คืนรายชื่อ FundCode ที่ index_name เป็น primary หรือ secondary (band-based) ของกองนั้น."""
    matched = []
    sub = coefs[coefs["scope"] == scope]
    for fund, g in sub.groupby("FundCode"):
        fc = g.set_index("index")["elastic"]
        primary, secondary = matching.classify_exposure(fc)
        if index_name == primary or index_name in secondary:
            matched.append(fund)
    return matched
```

**ข้อควรระวังเรื่อง performance**: loop กองทุนทั้ง 368 กอง (group by) ทุกครั้งที่คลิกจุด — เบากว่าการอ่าน nav แน่นอน (ข้อมูลอยู่ใน `coefs.csv` ที่โหลด cache ไว้แล้ว ~368×28×2 แถว) แต่ถ้ารู้สึกช้าตอน implement จริง ค่อย wrap ด้วย `@st.cache_data` หรือ precompute เป็น dict `{(scope, index): [fund_list]}` ครั้งเดียวตอนโหลด cache ก็ได้ — ไม่ใช่ปัญหาต้องแก้ตอนวางแผน แค่ flag ไว้เผื่อ

## 5. Recheck ตามธรรมเนียมโปรเจกต์ (3 เรื่อง)

1. **โค้ดใหม่ถูกต้อง**: ทดสอบคลิก index ที่รู้ผลจาก `coefs.csv` อยู่แล้ว (เช่น ABAGS ควรโผล่มาเมื่อคลิก MSCI_WORLD_EX_US, MSCI_ACWI, MSCI_WORLD หรือ MSCI_EUROPE เพราะทั้ง 4 ตัวอยู่ใน band ของกองนี้ตามที่เช็คไว้ใน §2 ของ `MATCH_STRENGTH_SECONDARY_PLAN.md`) + เช็ค return_21d คำนวณตรงกับคำนวณมือ (เช่นเทียบกับราคา MSCI ดิบ)
2. **ระบบเดิมไม่พัง**: เปิดหน้า 1,2,3,4 หลัง rebuild cache (ที่เพิ่ม column `return_21d` และเปลี่ยน `garch_forecast` เป็น t-dist) เช็คว่าตัวเลข/กราฟ/filter ยังทำงานถูกต้อง (ควรเหมือนเดิมเกือบหมด ยกเว้นค่า forecast vol ในหน้า 4 ที่จะเปลี่ยนเล็กน้อยตามที่ execute เทียบให้ดูไปแล้ว — เฉลี่ย ~2% เปลี่ยน, Korea เปลี่ยนมากสุด ~12%)
3. **โครงสร้างรวมยังสมเหตุสมผล**: เพิ่ม 1 คอลัมน์ใน `results.csv`, เพิ่ม 1 ฟังก์ชันกลางที่ 2 หน้าใช้ร่วมกัน (ลด duplication ไม่เพิ่ม), ไม่เพิ่ม cache file ใหม่ (คำนวณสดสำหรับ index snapshot) — โครงสร้างไม่ซับซ้อนขึ้นเกินจำเป็น

## 6. ลำดับงานที่เสนอ (ทำทีละหน้าตามที่บอกไว้)

1. **หน้า 3**: `SECONDARY_BAND_PCT` + แยก `classify_exposure()` เป็นฟังก์ชันกลางใน `matching.py` (ปรับจาก plan เดิมเล็กน้อย) → แก้ `viz.match_strength_bar()` ให้เรียกใช้
2. **หน้า 4**: เปลี่ยน `garch_forecast()` เป็น `dist="t"` → rebuild `cache/vol_forecast_*.csv`
3. **หน้า 5**: เพิ่ม `return_21d` ใน `build_pipeline()` (`metrics.py` + `data_access.py`) → rebuild `results.csv` → เขียนหน้าใหม่ (`viz.vol_return_scatter()` + `pages/5_...py`) โดยเรียกใช้ `classify_exposure()`/`get_funds_matching_index()` ที่มีจากขั้นตอน 1

ต้องการให้เริ่ม **ขั้นตอนที่ 1 (หน้า 3)** ตามที่คุยไว้ก่อนหน้านี้เลยไหมครับ หรือมีจุดในแผนหน้า 5 นี้ที่อยากปรับก่อน (เช่น เรื่อง fund-list แยกช่องซ้าย-ขวา ใน §3.1)?
