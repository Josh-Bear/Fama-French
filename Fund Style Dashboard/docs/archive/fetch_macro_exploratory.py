"""ลอง fetch macro factor มาดู (exploratory เท่านั้น - ยังไม่ใช่ส่วนหนึ่งของ pipeline จริง)

รันบนเครื่องที่ต่อเน็ตได้ปกติ (ไม่ใช่ sandbox):
    pip install yfinance --quiet
    python3 fetch_macro_test.py

เขียนไฟล์ macro_factor_test.csv ไว้ที่โฟลเดอร์เดียวกับสคริปต์นี้
ทุก series เก็บเป็น "ราคา/ระดับดิบ" หน่วยดั้งเดิม (ไม่แปลงสกุลเงิน - เหตุผลดูในแชท)

v3: เพิ่ม 2 world factor ที่ไม่เอียงไปทาง USA มากเท่าเดิม
    - Copper (HG=F): "Dr. Copper" - ตัวชี้วัด global industrial demand / China growth
    - DXY (DX-Y.NYB): US Dollar Index เทียบตะกร้า 6 สกุลหลัก (กว้างกว่า USDTHB ที่เป็นคู่เดียว)
    รวมเป็น 7 factor: Oil, Gold, USDTHB, VIX, US10Y, Copper, DXY

v2: เปลี่ยนวิธีดึง US10Y เป็น CSV ตรงจาก FRED แทน pandas_datareader
    (pandas_datareader รุ่นเก่าชนกับ pandas รุ่นใหม่ - deprecate_kwarg() error)
"""
import pandas as pd
import yfinance as yf

START = "2020-11-01"   # เผื่อก่อนช่วง MSCI (2021-01) ให้มี return วันแรก เหมือน style ETF

TICKERS = {
    "Oil_Brent": "BZ=F",     # USD/barrel
    "VIX": "^VIX",           # index level (ไม่มีหน่วยเงิน)
    "Gold": "GC=F",          # USD/oz
    "USDTHB": "THB=X",       # อัตราแลกเปลี่ยน USD->THB
    "Copper": "HG=F",        # USD/lb - global industrial demand / China proxy
    "DXY": "DX-Y.NYB",       # US Dollar Index เทียบตะกร้า 6 สกุลหลัก
}

print("fetching yfinance tickers:", list(TICKERS.values()))
raw = yf.download(list(TICKERS.values()), start=START, auto_adjust=True, progress=False)["Close"]
raw = raw.rename(columns={v: k for k, v in TICKERS.items()})

missing = [k for k in TICKERS if k not in raw.columns or raw[k].dropna().empty]
if missing:
    print(f"⚠️ ticker ดึงไม่ได้: {missing}")
    if "DXY" in missing:
        print("   -> DXY ลองไม่ได้บ่อยบน yfinance บางช่วง ถ้าพลาดจะลอง fallback ticker 'DX=F' ให้อัตโนมัติด้านล่าง")

# fallback DXY เผื่อ DX-Y.NYB ดึงไม่ได้ (บางครั้ง Yahoo ไม่มีข้อมูลย้อนหลังพอ)
if "DXY" in missing:
    try:
        alt = yf.download("DX=F", start=START, auto_adjust=True, progress=False)["Close"]
        if not alt.dropna().empty:
            raw["DXY"] = alt
            print(f"   -> ใช้ fallback DX=F แทนสำเร็จ: {raw['DXY'].notna().sum()} จุด")
    except Exception as e:
        print(f"   -> fallback DX=F ก็ดึงไม่ได้เหมือนกัน: {type(e).__name__}: {e}")

# US10Y จาก FRED (DGS10) - ดึง CSV ตรง ไม่ผ่าน pandas_datareader (กัน version conflict)
try:
    us10y = pd.read_csv(
        f"https://fred.stlouisfed.org/graph/fredgraph.csv?id=DGS10&cosd={START}",
        parse_dates=["observation_date"], index_col="observation_date",
    )["DGS10"]
    us10y = pd.to_numeric(us10y, errors="coerce")   # FRED ใช้ "." แทนวันที่ไม่มีข้อมูล (วันหยุด) -> NaN
    raw["US10Y"] = us10y
    print(f"US10Y: {raw['US10Y'].notna().sum()} จุด, ล่าสุด {raw['US10Y'].dropna().index.max():%Y-%m-%d}")
except Exception as e:
    print(f"⚠️ FRED DGS10 ดึงไม่ได้: {type(e).__name__}: {e}")

raw.index.name = "Date"
out_path = "macro_factor_test.csv"
raw.to_csv(out_path)
print(f"\nsaved {raw.shape} -> {out_path}")
print(raw.tail())
print("\nnull count per column:")
print(raw.isna().sum())
