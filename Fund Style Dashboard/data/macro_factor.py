"""macro_factor.py — 7 macro factor สำหรับหน้า 7 Macro Chain.

แหล่งข้อมูล: yfinance (Oil, Gold, USDTHB, Copper, DXY, VIX) + FRED DGS10 (US10Y)
-> snapshot base_data/MACRO_FACTOR.csv ครั้งเดียว (ต้องต่อเน็ต) แล้ว pipeline อ่าน offline เหมือน style ETF

การแปลงรายเดือน (to_factor_changes — รับ level ณ สิ้นเดือนที่ analysis.macro_chain.month_end_levels ทำให้แล้ว):
  ราคาสินทรัพย์ (MACRO_RETURN_COLS) -> % return
  VIX, US10Y (MACRO_DELTA_COLS)     -> ผลต่างระดับ Δ — ไม่ใช่ราคา: yield 4.78%->4.80% = +0.02pp ไม่ใช่ "return" +0.42%
"""

from __future__ import annotations

import os

import pandas as pd

import config
from data.style_factor import SnapshotMissingError   # ชนิดเดียวกับหน้า 6 — หน้าเว็บจับ error ตัวเดียว


def parse_fred_csv(src, series: str) -> pd.Series:
    """อ่าน CSV ของ FRED (path/URL/buffer) -> Series. FRED ใช้ "." แทนวันที่ไม่มีข้อมูล -> NaN.

    คอลัมน์แรกคือวันที่ (ชื่อเปลี่ยนไปมาระหว่าง DATE / observation_date) จึงอ้างด้วยตำแหน่ง
    """
    df = pd.read_csv(src)
    return pd.Series(pd.to_numeric(df[series], errors="coerce").to_numpy(),
                     index=pd.to_datetime(df.iloc[:, 0]), name=series)


def _yf_close(yf, tickers: list[str], start: str) -> pd.DataFrame:
    close = yf.download(tickers, start=start, auto_adjust=True, progress=False)["Close"]
    return close.to_frame(tickers[0]) if isinstance(close, pd.Series) else close


def download_snapshot(start: str | None = None) -> pd.DataFrame:
    """ดึง level ดิบ 7 factor (หน่วยดั้งเดิม ไม่แปลงสกุลเงิน) แล้วเขียน snapshot — ต้องต่อเน็ต."""
    import yfinance as yf   # lazy: ใช้เฉพาะตอนดาวน์โหลด

    start = start or config.MACRO_SNAPSHOT_START
    ticks = config.MACRO_YF_TICKERS
    raw = _yf_close(yf, list(ticks.values()), start)
    snap = pd.DataFrame({f: raw[t] for f, t in ticks.items() if t in raw.columns})
    if "DXY" not in snap or snap["DXY"].dropna().empty:
        alt = _yf_close(yf, [config.MACRO_DXY_FALLBACK], start).iloc[:, 0]
        print(f"⚠️ {ticks['DXY']} ไม่มีข้อมูล — ใช้ {config.MACRO_DXY_FALLBACK} (futures) แทน")
        snap["DXY"] = alt
    for f, sid in config.MACRO_FRED_SERIES.items():
        snap = snap.join(parse_fred_csv(config.MACRO_FRED_URL.format(series=sid, start=start), sid)
                         .rename(f).loc[start:], how="outer")

    missing = [f for f in config.MACRO_FACTOR_COLS if f not in snap or snap[f].dropna().empty]
    if missing:
        raise RuntimeError(f"ดึงข้อมูลไม่ได้: {missing} — ตรวจเน็ต/ticker แล้วลองใหม่")
    snap = snap[config.MACRO_FACTOR_COLS].dropna(how="all")
    snap.index.name = "Date"
    last = snap.apply(pd.Series.last_valid_index)
    lagging = {f: f"{d:%Y-%m-%d}" for f, d in last.items() if d < last.max()}
    if lagging:   # pipeline ตัดทุกอย่างที่วันร่วมล่าสุด + ทิ้งเดือนที่ยังไม่จบ (month_end_levels)
        print(f"ℹ️ factor ที่ข้อมูลหมดก่อน {lagging} — pipeline จะใช้ถึงวันร่วมล่าสุด")
    snap.to_csv(config.MACRO_FACTOR_CSV)
    return snap


def load_snapshot() -> pd.DataFrame:
    """อ่าน snapshot (offline). ไม่มีไฟล์ -> SnapshotMissingError พร้อมคำสั่งที่ต้องรัน."""
    if not os.path.exists(config.MACRO_FACTOR_CSV):
        raise SnapshotMissingError(
            f"ไม่พบ {os.path.basename(config.MACRO_FACTOR_CSV)} — รัน "
            "`./.venv/bin/python data_access.py macro-download` (ต้องต่อเน็ต) ก่อน")
    return pd.read_csv(config.MACRO_FACTOR_CSV, parse_dates=["Date"]).set_index("Date").sort_index()


def to_factor_changes(month_end: pd.DataFrame) -> pd.DataFrame:
    """level สิ้นเดือน -> factor รายเดือน: % return (ราคาสินทรัพย์) / Δ (VIX, US10Y). pure function."""
    out = pd.concat([month_end[config.MACRO_RETURN_COLS].pct_change(),
                     month_end[config.MACRO_DELTA_COLS].diff()], axis=1)
    return out[config.MACRO_FACTOR_COLS].iloc[1:]
