"""style_factor.py — style factor (Momentum / Quality / Value / LowVol) สำหรับหน้า 6 Style Match.

แหล่งข้อมูล: iShares MSCI factor ETF จาก yfinance (USD) -> snapshot ลง base_data/STYLE_FACTOR_ETF.csv
ครั้งเดียว (ต้องต่อเน็ต) แล้ว pipeline อ่าน offline เหมือนไฟล์อื่นใน base_data

วิธีสร้าง (ยืนยันแล้ว 2026-09-15 — ดู docs/pages/6-style-match.md):
  ETF พวกนี้เป็น long-only -> corr กับตลาด 0.80-0.95 -> ต้อง de-market ก่อน regress
  1) blend US+Intl ใน **return** space : r = w·r_US + (1−w)·r_Intl      (w = STYLE_US_WEIGHT)
  2) level = cumprod(1 + r)
  3) relative = level ÷ ACWI_ETF                                         (USD÷USD -> ค่าเงินหักล้างพอดี)
  LowVol ใช้ ACWV (global) ÷ ACWI เดี่ยว ไม่ต้อง blend
  ต้องคืนเป็น **level** เพราะ matching.build_fund_returns ทบต้นช่วง NAVDate gap ด้วยอัตราส่วน level

ตัวแปรควบคุม (control — ไม่นับเป็น style):
  MSCI_ACWI  = ตลาดโลก "โลก MSCI" (THB, base_data — ตรงกับ NAV กอง)
  US_VS_ACWI = MSCI_USA ÷ MSCI_ACWI (THB÷THB) -> ดูด "US ชนะโลก" ออก
  ACWI_ETF   = ตลาดโลก "โลก ETF" (USD, snapshot — ตรงกับ style factor)
  ต้องคุมตลาดทั้งสองโลก: ถ้ามีแค่ฝั่ง MSCI, LowVol (corr −0.79 กับตลาดฝั่ง ETF) จะอุดช่องว่างระหว่างสองโลก
  จน coef ติดลบปลอม -> กองเกือบทั้งหมดได้ป้าย "High-Beta" (พบตอน sanity check 2026-09-15)
"""

from __future__ import annotations

import os

import pandas as pd

import config
from data import msci_index


class SnapshotMissingError(FileNotFoundError):
    """ยังไม่มี snapshot ETF — แยกชนิดจาก FileNotFoundError อื่น ให้หน้า 6 บอกวิธีแก้ได้ตรงสาเหตุ."""


def _all_tickers() -> list[str]:
    """ticker ทั้งหมดที่ต้องดึง = ETF ของทุก factor + benchmark."""
    ticks = {config.STYLE_BENCHMARK_TICKER}
    for us, intl in config.STYLE_TICKERS.values():
        ticks.add(us)
        if intl:
            ticks.add(intl)
    return sorted(ticks)


def download_snapshot(start: str | None = None) -> pd.DataFrame:
    """ดึงราคา ETF (auto_adjust = รวมปันผลแล้ว) จาก yfinance แล้วเขียน snapshot — ต้องต่อเน็ต."""
    import yfinance as yf   # lazy: ใช้เฉพาะตอนดาวน์โหลด ส่วนอื่นของแอปไม่ต้องมีเน็ต

    tickers = _all_tickers()
    raw = yf.download(tickers, start=start or config.STYLE_SNAPSHOT_START,
                      auto_adjust=True, progress=False)["Close"]
    missing = [t for t in tickers if t not in raw.columns or raw[t].dropna().empty]
    if missing:
        raise RuntimeError(f"yfinance ไม่คืนข้อมูลของ {missing} — ตรวจเน็ต/ticker แล้วลองใหม่")
    snap = raw[tickers].dropna(how="all")
    snap.index.name = "Date"
    last = snap.apply(pd.Series.last_valid_index)
    lagging = {t: f"{d:%Y-%m-%d}" for t, d in last.items() if d < last.max()}
    if lagging:   # build_style_levels จะตัดปลายทุก factor ตามตัวที่หมดก่อน (ไม่ ffill ต่อเป็น return 0 ปลอม)
        print(f"⚠️ ticker ข้อมูลหมดก่อนตัวอื่น {lagging} — ช่วงที่ใช้ได้จะถูกตัดตาม")
    snap.to_csv(config.STYLE_FACTOR_CSV)
    return snap


def load_snapshot() -> pd.DataFrame:
    """อ่าน snapshot (offline). ไม่มีไฟล์ -> SnapshotMissingError พร้อมคำสั่งที่ต้องรัน."""
    if not os.path.exists(config.STYLE_FACTOR_CSV):
        raise SnapshotMissingError(
            f"ไม่พบ {os.path.basename(config.STYLE_FACTOR_CSV)} — รัน "
            "`./.venv/bin/python data_access.py style-download` (ต้องต่อเน็ต) ก่อน")
    return pd.read_csv(config.STYLE_FACTOR_CSV, parse_dates=["Date"]).set_index("Date").sort_index()


def build_style_levels(etf: pd.DataFrame, us_weight: float | None = None) -> pd.DataFrame:
    """ราคา ETF (USD) -> relative level ต่อ style factor (de-market แล้ว, เริ่มที่ 1).

    pure function (ไม่อ่านไฟล์) -> test ได้ตรงๆ
    ตัดหัว/ท้ายให้เหลือช่วงที่**ทุก ticker**มีข้อมูลจริง (ticker เริ่มช้า/หมดก่อน) กัน level แบนปลอมขณะ benchmark ขยับ
    ช่องว่างกลางช่วง (ticker ขาดบางวัน) -> ใช้ราคาล่าสุด (return 0 วันนั้น)
    """
    w = config.STYLE_US_WEIGHT if us_weight is None else us_weight
    # 1 ticker = 1 ชุด -> combine_levels ทำ ffill + ตัดช่วงให้ (เดิม ffill ก่อน dropna ทำให้ปลายที่หมดก่อนถูกเติมแบน)
    etf = combine_levels(*(etf[[c]] for c in etf.columns))
    bench = etf[config.STYLE_BENCHMARK_TICKER]
    r = etf.pct_change()
    out = {}
    for factor, (us, intl) in config.STYLE_TICKERS.items():
        if intl is None:
            level = etf[us]
        else:
            blended = (w * r[us] + (1 - w) * r[intl]).fillna(0.0)   # แถวแรกไม่มี return -> 0
            level = (1.0 + blended).cumprod()
        out[factor] = level / bench
    rel = pd.DataFrame(out)
    return (rel / rel.iloc[0])[config.STYLE_FACTOR_COLS]    # normalize ไม่กระทบ return


def build_controls() -> pd.DataFrame:
    """control ฝั่ง MSCI จาก base_data (THB): ตลาดโลก + US ชนะโลก (ACWI_ETF มาจาก snapshot — ดู assemble_regressors)."""
    cty = msci_index.load_country_index()
    return pd.DataFrame({
        "MSCI_ACWI": cty["MSCI_ACWI"],
        "US_VS_ACWI": cty["MSCI_USA"] / cty["MSCI_ACWI"],
    })


def combine_levels(*frames: pd.DataFrame) -> pd.DataFrame:
    """รวม level หลายชุดที่ปฏิทินต่างกัน (MSCI = ทุก weekday, ETF = ปฏิทิน NYSE).

    - ใช้วันรวม (union) แล้ว ffill -> วันที่ตลาดหนึ่งปิด ใช้ราคาล่าสุด (return 0) ไม่เป็น NaN
      ต้องไม่มี NaN เพราะ build_fund_returns ใช้ reindex(ffill) ซึ่งไม่ข้าม NaN -> แถวจะหาย
    - ตัดเฉพาะช่วงที่**ทุกชุด**มีข้อมูล -> กัน ffill ต่อหลังชุดใดหมด (จะได้ return 0 ปลอม)
    """
    lo = max(f.dropna().index.min() for f in frames)
    hi = min(f.dropna().index.max() for f in frames)
    merged = pd.concat(frames, axis=1).sort_index().ffill()
    return merged.loc[lo:hi]


def assemble_regressors(msci_controls: pd.DataFrame, snap: pd.DataFrame) -> pd.DataFrame:
    """control ฝั่ง MSCI ⊕ ตลาดฝั่ง ETF (ACWI_ETF) ⊕ style relative -> เรียงคอลัมน์ตาม config (pure function)."""
    bench = config.STYLE_BENCHMARK_TICKER
    etf_market = snap[[bench]].rename(columns={bench: "ACWI_ETF"})
    merged = combine_levels(msci_controls, etf_market, build_style_levels(snap))
    return merged[config.STYLE_CONTROL_COLS + config.STYLE_FACTOR_COLS]


def load_style_regressors() -> pd.DataFrame:
    """regressor ครบทั้ง control ×3 + style ×4 — พร้อมส่งให้ matching.build_fund_returns()."""
    return assemble_regressors(build_controls(), load_snapshot())


def style_label(factor: str | None, coef: float) -> str | None:
    """ชื่อ style ตามเครื่องหมาย coef — Value+ = "Value", Value− = "Growth" (ดู config.STYLE_LABELS).

    ต่างจาก country/sector ที่ใช้ |coef| อย่างเดียว: style ติดลบมีความหมายตรงข้ามจริง
    """
    if factor is None or pd.isna(coef):
        return None
    pos, neg = config.STYLE_LABELS[factor]
    return pos if coef >= 0 else neg
