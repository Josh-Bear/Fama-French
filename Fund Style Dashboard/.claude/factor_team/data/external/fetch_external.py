"""fetch_external.py — ดาวน์โหลดข้อมูลภายนอก 4 ไฟล์สำหรับทีมวิจัย factor (ผู้ใช้อนุมัติ 2026-10-15).

เขียนเฉพาะในโฟลเดอร์นี้ (ไม่แตะ base_data/) · รันซ้ำ = ดึงใหม่ทับไฟล์เดิม (ต้องได้รับอนุมัติใหม่ทุกครั้ง)
  1 TH_EQUITY_PROXY.csv     แทน ^SET.BK (Yahoo ไม่ให้ประวัติแล้ว · 2026-10-15): TDEX.BK (ETF SET50 · บาท) ถ้าครอบคลุมช่วงหลัก
                            ไม่งั้น THD (iShares MSCI Thailand · USD) — adjusted close · ผู้ใช้อนุมัติลำดับนี้
  2 US_RATES_CREDIT_ETF.csv Yahoo Finance SHV / LQD / HYG / EMB (adjusted close)
  3 US_SPREADS_FRED.csv     FRED DTB3 / BAMLC0A0CM / BAMLH0A0HYM2 (% · ระดับ ไม่ใช่ผลตอบแทน)
  4 TH_GOV_YIELDS.csv       ThaiBMA interpolated 1Y / 5Y / 10Y + T-BILL3M (% ต่อปี)
ThaiBMA endpoint เดียวกับ Fama French SET50/data/thaibma_api.py (คัดลอกส่วนที่ใช้ เพราะ import ข้ามโปรเจกต์ชนชื่อ package `data`)
รัน: cd "/Users/doyinratnavardhana/Fama French/Fund Style Dashboard" && ./.venv/bin/python .claude/factor_team/data/external/fetch_external.py
"""
from __future__ import annotations

import hashlib
import io
import os

import pandas as pd
import requests
import yfinance as yf

OUT = os.path.dirname(os.path.abspath(__file__))
START = "2020-11-01"
ETFS = ["SHV", "LQD", "HYG", "EMB"]
FRED = ["DTB3", "BAMLC0A0CM", "BAMLH0A0HYM2"]
TH_TENORS = ["1Y", "5Y", "10Y"]
THBMA = "https://www.thaibma.or.th"
THBMA_HDR = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Referer": "https://www.thaibma.or.th/EN/Market/YieldCurve/Government.aspx",
    "X-Requested-With": "XMLHttpRequest",
    "Accept": "application/json, text/javascript, */*",
}


def yahoo(tickers: list[str], adjusted: bool) -> pd.DataFrame:
    df = yf.download(tickers, start=START, auto_adjust=adjusted, progress=False, threads=False)["Close"]
    df = df.to_frame(tickers[0]) if isinstance(df, pd.Series) else df[tickers]
    df.index = pd.to_datetime(df.index).tz_localize(None)
    return df.dropna(how="all")


def fred(ids: list[str]) -> pd.DataFrame:
    cols = []
    for i in ids:
        r = requests.get("https://fred.stlouisfed.org/graph/fredgraph.csv", params={"id": i, "cosd": START}, timeout=60)
        r.raise_for_status()
        s = pd.read_csv(io.StringIO(r.text), index_col=0, parse_dates=True, na_values=".").iloc[:, 0].rename(i)
        cols.append(s)
    return pd.concat(cols, axis=1, sort=True)


def thaibma() -> pd.DataFrame:
    get = lambda p: requests.get(THBMA + p, headers=THBMA_HDR, timeout=30).json()  # noqa: E731
    years = [int(y) for y in get("/yieldcurve/availyear") if int(y) >= pd.Timestamp(START).year]
    rows = []
    for y in years:
        intp = {r["asof"]: r for r in get(f"/yieldcurve/getintpttm?year={y}")}
        bill = {r["asof"]: r for r in get(f"/yieldcurve/getbyyear?year={y}")}
        for d in sorted(set(intp) | set(bill)):
            row = {"Date": pd.Timestamp(d)}
            row.update({f"TH{t}": intp.get(d, {}).get(t) for t in TH_TENORS})
            row["TH_TBILL3M"] = bill.get(d, {}).get("T-BILL3M")
            rows.append(row)
    df = pd.DataFrame(rows).set_index("Date").sort_index().astype(float)
    df = df[~df.index.duplicated(keep="last")]
    return df[df.index >= pd.Timestamp(START)].dropna(how="all")


def th_equity_proxy() -> pd.DataFrame:
    """TDEX.BK ก่อน · ใช้ได้เมื่อเริ่มไม่เกิน 2021-01-08 และ ≥ 1,000 วัน · ไม่งั้น THD."""
    for tk in ("TDEX.BK", "THD"):
        df = yahoo([tk], adjusted=True)
        ok = len(df) >= 1000 and df.index.min() <= pd.Timestamp("2021-01-08")
        print(f"{tk}: rows={len(df)} first={df.index.min() if len(df) else None} -> {'ใช้' if ok else 'ไม่ผ่าน'}")
        if ok:
            return df
    raise RuntimeError("ไม่มีแหล่งหุ้นไทยที่ครอบคลุมช่วงหลัก")


def save(df: pd.DataFrame, name: str) -> None:
    df.index.name = "Date"
    path = os.path.join(OUT, name)
    df.to_csv(path, float_format="%.10g")
    sha = hashlib.sha256(open(path, "rb").read()).hexdigest()
    print(f"{name}: rows={len(df)} {df.index.min():%Y-%m-%d}..{df.index.max():%Y-%m-%d} "
          f"size={os.path.getsize(path):,}B sha256={sha[:12]} nan={df.isna().sum().to_dict()}")


if __name__ == "__main__":
    import sys
    only = set(sys.argv[1:])            # ว่าง = ทุกไฟล์ · หรือระบุ: th_equity etf fred thaibma
    jobs = {"th_equity": (th_equity_proxy, "TH_EQUITY_PROXY.csv"),
            "etf": (lambda: yahoo(ETFS, adjusted=True), "US_RATES_CREDIT_ETF.csv"),
            "fred": (lambda: fred(FRED), "US_SPREADS_FRED.csv"),
            "thaibma": (thaibma, "TH_GOV_YIELDS.csv"),
            # F-R004 (2026-10-16 · ผู้ใช้อนุญาตดาวน์โหลดระหว่าง auto run) · adjusted close · USD
            "thematic": (lambda: yahoo(["QQQ", "SOXX", "ARKK", "ICLN", "IBB", "KWEB"], adjusted=True), "THEMATIC_ETF.csv"),
            "asean": (lambda: yahoo(["THD", "EIDO", "EPHE", "EWM", "EWS"], adjusted=True), "ASEAN_COUNTRY_ETF.csv"),
            "real": (lambda: yahoo(["REET", "IGF", "DBC", "GSG"], adjusted=True), "REAL_ASSETS_ETF.csv"),
            "hedged": (lambda: yahoo(["HEWJ", "EWJ", "HEFA", "EFA"], adjusted=True), "HEDGED_EQUITY_ETF.csv")}
    for k, (fn, name) in jobs.items():
        if not only or k in only:
            save(fn(), name)
