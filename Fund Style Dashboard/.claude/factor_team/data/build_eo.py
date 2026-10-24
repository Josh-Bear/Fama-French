"""build_eo.py — งาน F5-EO ชั้น L0: factor ภายนอกใหม่ (Ken French / JKP / AQR / GLD VNQ VNQI / REIT เอเชีย / FRED) + AUM_fam สำหรับ U_E / U_O

รัน:  cd "<root>" && PYTHONDONTWRITEBYTECODE=1 ./.venv/bin/python -I -B .claude/factor_team/data/build_eo.py [--out DIR]
- ไม่ดาวน์โหลด · ไม่แก้ไฟล์ L0 เดิม (ตรวจ sha256 เทียบ manifest.json / manifest_ext.json ทุกครั้ง) · ไม่แก้ไฟล์ต้นฉบับใน external/ (อ่านอย่างเดียว)
- ไฟล์ดาวน์โหลด = ข้อมูลภายนอก: อ่านด้วย zipfile + pandas + xml.etree เท่านั้น (ไม่ exec / import อะไรจากในไฟล์) · xlsx ของ AQR อ่านด้วยตัวอ่านเองแบบ stdlib (venv ไม่มี openpyxl)
- จุดวันเดียวกับ panel: ใช้ anchors เดียวกับ build_l0.py (W-FRI 2021-01-01 → 2026-07-31 · เดือน = สิ้นเดือน) และ asof_series ของ L0 (≤ วันอ้างอิง · ห่างไม่เกิน 10 วัน)
- factor long–short รายวัน (KF / JKP / AQR): ทบต้นเป็น cum index แล้ว asof ที่ anchor (= Π(1+r) ของวันใน (anchor ก่อน, anchor]) · สัปดาห์/เดือนที่ anchor เลยวันสุดท้ายของข้อมูล = NaN (ไม่ใช้สัปดาห์ที่ข้อมูลไม่ครบ)
  ไม่แปลงเป็นบาท · หน่วยเป็นสัดส่วน (0.01 = 1%) ไม่ใช่ %
- ราคา ETF (Yahoo adjusted close): ผลตอบแทน USD และบาท (× USDTHB ของ base_data/MACRO_FACTOR.csv แบบเดียวกับ build_l0_ext) · REIT เอเชีย: สกุลท้องถิ่นและบาท (× JPYTHB / SGDTHB)
- ตัดแถว Yahoo ที่ Date ≥ วันดาวน์โหลด (2026-10-20 · ข้อมูลยังไม่ปิดวัน)
- ผลลัพธ์: factors_eo_weekly.parquet · factors_eo_monthly.parquet · factor_groups_eo.csv · eo_row_flags.csv · aum_fam.parquet · QA_EO.md · manifest_eo.json
- ผลเหมือนเดิมทุกบิต (parquet / csv / QA ไม่มีวันที่สร้างในเนื้อหา · manifest มี created แยกฟิลด์เดียว)
"""
from __future__ import annotations

import io
import json
import os
import re
import sys
import zipfile
import xml.etree.ElementTree as ET
from datetime import date

sys.dont_write_bytecode = True

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import build_l0 as L0  # noqa: E402  (import เฉยๆ ไม่รัน main · asof_series / D / sha256 / info_file / family_of / constants)

config = L0.config
ROOT, EXT, BD = L0.ROOT, L0.EXT, L0.BD
RAW = os.path.join(EXT, "raw_eo")
OUT = HERE
for i, a in enumerate(sys.argv):
    if a == "--out":
        OUT = os.path.abspath(sys.argv[i + 1])

# ---------------------------------------------------------------- ค่าคงที่ (ใช้จริงใน build นี้)
DOWNLOAD_DATE = pd.Timestamp("2026-10-20")      # วันดาวน์โหลด (NOTES.md) — แถว Yahoo ที่ Date >= วันนี้ถูกตัด
CUM_START = pd.Timestamp("2020-10-01")          # เริ่ม cum index ของ factor รายวัน (ก่อน anchor แรก 2021-01-01)
AUM_ASOF = pd.Timestamp("2023-12-31")           # วันวัด AUM_fam (BRIEF 109)
AGE_ASOF = pd.Timestamp("2025-12-31")           # วันวัดอายุ family (BRIEF 109)
AUM_MIN = 100_000_000.0                         # บาท
AGE_MIN_DAYS = 730
AUM_STALE_DAYS = 90                             # ค่าบวกล่าสุดภายใน 90 วัน (M012 · = config.NAV_STALE_MAX_DAYS)
EXPECT_UE, EXPECT_UO = 209, 12                  # ค่าคาดจากแผน (~)
WEEK_ABN, MONTH_ABN = 0.20, 0.30
Z_ABN = 6.0
TRAIN_END = pd.Timestamp("2023-12-31")

KF_FILES = {   # (prefix, zip ของ 5F รายวัน, zip ของ Mom รายวัน)
    "KF_DEV": ("KF_Developed_5_Factors_Daily_CSV.zip", "KF_Developed_Mom_Factor_Daily_CSV.zip"),
    "KF_NA": ("KF_North_America_5_Factors_Daily_CSV.zip", "KF_North_America_Mom_Factor_Daily_CSV.zip"),
    "KF_EU": ("KF_Europe_5_Factors_Daily_CSV.zip", "KF_Europe_Mom_Factor_Daily_CSV.zip"),
    "KF_JP": ("KF_Japan_5_Factors_Daily_CSV.zip", "KF_Japan_Mom_Factor_Daily_CSV.zip"),
}
KF_MONTHLY = {   # ใช้ใน QA (Developed) และเป็นคอลัมน์รายเดือนอย่างเดียว (Emerging)
    "KF_DEV": ("KF_Developed_5_Factors_CSV.zip", "KF_Developed_Mom_Factor_CSV.zip"),
    "KF_EM": ("KF_Emerging_5_Factors_CSV.zip", "KF_Emerging_MOM_Factor_CSV.zip"),
}
KF_COLMAP = {"Mkt-RF": "MKTRF", "SMB": "SMB", "HML": "HML", "RMW": "RMW", "CMA": "CMA", "RF": "RF", "WML": "WML"}
JKP_FILES = {"JKP_EM": "JKP_EMERGING_THEMES_DAILY.zip", "JKP_DEV": "JKP_DEVELOPED_THEMES_DAILY.zip"}
AQR_FILES = {   # prefix → (xlsx, ชื่อ sheet แรก)
    "AQR_QMJ": ("AQR_Quality-Minus-Junk-Factors-Daily.xlsx", "QMJ Factors"),
    "AQR_BAB": ("AQR_Betting-Against-Beta-Equity-Factors-Daily.xlsx", "BAB Factors"),
    "AQR_HMLD": ("AQR_The-Devil-in-HMLs-Details-Factors-Daily.xlsx", "HML Devil"),
}
AQR_SERIES = {"USA": "USA", "Global": "GLOBAL", "Global Ex USA": "GLOBALXUS"}   # series ที่เลือก (ตรงคำสั่งงาน: US + Global / Global ex US)

# ---------------------------------------------------------------- utilities
def md_table(df: pd.DataFrame) -> str:
    h = "| " + " | ".join(str(c) for c in df.columns) + " |\n|" + "|".join(["---"] * len(df.columns)) + "|\n"
    return h + "\n".join("| " + " | ".join(str(x) for x in r) + " |" for r in df.itertuples(index=False))


def fmt(x, nd=3):
    return "" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{x:.{nd}f}"


def main_mask(idx: pd.DatetimeIndex) -> np.ndarray:
    return np.asarray((idx > L0.MAIN_START) & (idx <= L0.MAIN_END))


def read_zip_text(path: str, member: str | None = None) -> tuple[str, str]:
    """อ่านไฟล์เดียวใน zip เป็นข้อความ (ไม่แตกไฟล์ลงดิสก์ · ตรวจชื่อสมาชิกไม่มี path แปลก)."""
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        assert len(names) == 1 and ".." not in names[0] and not names[0].startswith("/"), (path, names)
        return names[0], z.read(names[0]).decode("latin-1")


def info_raw(path: str) -> dict:
    return {"file": os.path.relpath(path, ROOT), "sha256": L0.sha256(path), "bytes": os.path.getsize(path)}


# ---------------------------------------------------------------- 1. อ่านไฟล์ต้นฉบับ
def parse_kf(text: str, ndigits: int) -> pd.DataFrame:
    """Ken French CSV: บรรทัดข้อมูล = วันที่ (YYYYMMDD หรือ YYYYMM) + ค่า % · -99.99 = ขาด · บล็อกรายปี (4 หลัก) ถูกข้าม."""
    hdr, rows = None, []
    rx = re.compile(rf"^\s*(\d{{{ndigits}}})\s*,(.*)$")
    for ln in text.splitlines():
        m = rx.match(ln)
        if m:
            rows.append([m.group(1)] + [float(x) for x in m.group(2).split(",")])
        elif hdr is None and ln.startswith(","):
            hdr = [x.strip() for x in ln.split(",")[1:]]
    assert hdr is not None and rows, "KF: ไม่พบ header/ข้อมูล"
    df = pd.DataFrame(rows, columns=["date"] + hdr)
    df["date"] = pd.to_datetime(df["date"], format="%Y%m%d" if ndigits == 8 else "%Y%m")
    if ndigits == 6:
        df["date"] = df["date"] + pd.offsets.MonthEnd(0)
    df = df.set_index("date").sort_index()
    assert df.index.is_unique
    df = df.where(df > -99.0)              # -99.99 = missing
    return df / 100.0                       # % → สัดส่วน


def load_kf_daily() -> dict[str, pd.DataFrame]:
    out = {}
    for pre, (f5, fm) in KF_FILES.items():
        a = parse_kf(read_zip_text(os.path.join(RAW, f5))[1], 8)
        m = parse_kf(read_zip_text(os.path.join(RAW, fm))[1], 8)
        df = a.join(m, how="outer")
        out[pre] = df.rename(columns=KF_COLMAP)
    return out


def load_kf_monthly() -> dict[str, pd.DataFrame]:
    out = {}
    for pre, (f5, fm) in KF_MONTHLY.items():
        a = parse_kf(read_zip_text(os.path.join(RAW, f5))[1], 6)
        m = parse_kf(read_zip_text(os.path.join(RAW, fm))[1], 6)
        out[pre] = a.join(m, how="outer").rename(columns=KF_COLMAP)
    return out


def load_jkp() -> dict[str, pd.DataFrame]:
    out = {}
    for pre, f in JKP_FILES.items():
        name, txt = read_zip_text(os.path.join(RAW, f))
        df = pd.read_csv(io.StringIO(txt), usecols=["location", "name", "freq", "weighting", "date", "ret"])
        assert df["freq"].eq("daily").all() and df["weighting"].eq("vw_cap").all()
        df["date"] = pd.to_datetime(df["date"])
        assert not df.duplicated(["name", "date"]).any()
        out[pre] = df.pivot(index="date", columns="name", values="ret").sort_index()
    return out


# --- xlsx (stdlib) — AQR
_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
_RNS = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"


def _col_letters(ref: str) -> str:
    return re.match(r"[A-Z]+", ref).group()


def xlsx_first_sheet_path(z: zipfile.ZipFile, expect_name: str) -> str:
    wb = ET.fromstring(z.read("xl/workbook.xml"))
    sh = wb.find(_NS + "sheets")[0]
    assert sh.get("name") == expect_name, (sh.get("name"), expect_name)
    rid = sh.get(_RNS + "id")
    rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
    tgt = [r.get("Target") for r in rels if r.get("Id") == rid][0]
    return "xl/" + tgt.lstrip("/").replace("xl/", "", 1)


def xlsx_shared_strings(z: zipfile.ZipFile) -> list[str]:
    ss = []
    for _, el in ET.iterparse(z.open("xl/sharedStrings.xml")):
        if el.tag == _NS + "si":
            ss.append("".join(t.text or "" for t in el.iter(_NS + "t")))
            el.clear()
    return ss


def read_aqr(path: str, expect_sheet: str, series: dict[str, str]) -> tuple[pd.DataFrame, dict]:
    """อ่าน sheet แรกของ AQR daily factors: แถว header = แถวที่คอลัมน์ A = 'DATE' · วันที่ MM/DD/YYYY · เก็บเฉพาะ series ที่เลือก."""
    with zipfile.ZipFile(path) as z:
        sp = xlsx_first_sheet_path(z, expect_sheet)
        ss = xlsx_shared_strings(z)
        letters = None
        recs, n_rows = [], 0
        for _, el in ET.iterparse(z.open(sp)):
            if el.tag != _NS + "row":
                continue
            cells = {}
            for c in el.findall(_NS + "c"):
                v = c.find(_NS + "v")
                if v is None:
                    continue
                cells[_col_letters(c.get("r"))] = ss[int(v.text)] if c.get("t") == "s" else v.text
            el.clear()
            if letters is None:
                if cells.get("A") == "DATE":
                    letters = {k: v for k, v in cells.items()}
                    want = {name: [k for k, v in letters.items() if v == name] for name in series}
                    assert all(len(v) == 1 for v in want.values()), want
                    want = {name: v[0] for name, v in want.items()}
                continue
            if "A" not in cells or not re.match(r"^\d\d/\d\d/\d{4}$", cells["A"]):
                continue
            n_rows += 1
            recs.append([cells["A"]] + [cells.get(want[nm]) for nm in series])
    df = pd.DataFrame(recs, columns=["date"] + [series[nm] for nm in series])
    df["date"] = pd.to_datetime(df["date"], format="%m/%d/%Y")
    df = df.set_index("date").sort_index()
    assert df.index.is_unique
    df = df.apply(pd.to_numeric, errors="coerce")
    meta = {"sheet": expect_sheet, "header_row_series_letters": want, "data_rows": n_rows,
            "n_header_cols": len(letters) - 1, "all_series_in_file": [v for k, v in letters.items() if k != "A"]}
    return df, meta


def load_yahoo(f: str) -> tuple[pd.DataFrame, int]:
    df = pd.read_csv(os.path.join(EXT, f), parse_dates=["Date"]).set_index("Date").sort_index()
    n0 = len(df)
    df = df[df.index < DOWNLOAD_DATE]
    return df, n0 - len(df)


# ---------------------------------------------------------------- 2. แปลงเป็นรายสัปดาห์ / รายเดือน
def ret_from_daily(r: pd.Series, anchors: pd.DatetimeIndex) -> np.ndarray:
    """ทบต้นผลตอบแทนรายวัน (สัดส่วน) เป็นรายช่วง: cum index แล้ว asof ที่ anchor (≤ anchor ห่าง ≤ 10 วัน) · anchor เลยวันสุดท้ายของข้อมูล = NaN."""
    r = r.dropna().loc[CUM_START:]
    assert r.index.is_unique and r.index.is_monotonic_increasing
    cum = (1.0 + r).cumprod()
    A = L0.D(anchors)
    lvl = L0.asof_series(cum, A)
    lvl = np.where(np.asarray(anchors) <= cum.index.max(), lvl, np.nan)
    return lvl[1:] / lvl[:-1] - 1.0


def ret_from_price(lvl: np.ndarray) -> np.ndarray:
    return lvl[1:] / lvl[:-1] - 1.0


def rr(s: pd.Series) -> tuple[str, str, int]:
    """ช่วงข้อมูลดิบ (วันแรก / วันสุดท้าย / จำนวนแถวไม่ว่าง) ของแหล่งที่ใช้สร้างคอลัมน์."""
    s = s.dropna()
    return (f"{s.index.min():%Y-%m-%d}", f"{s.index.max():%Y-%m-%d}", int(len(s)))


def make_eo(anchors: pd.DatetimeIndex, src: dict, monthly: bool):
    """คืน (DataFrame index=anchors[1:], meta dict ต่อคอลัมน์)."""
    A = L0.D(anchors)
    cols, meta = {}, {}

    def add(name, arr, **m):
        cols[name] = arr
        meta[name] = m

    # --- Ken French รายวัน
    for pre, df in src["kf"].items():
        for c in ("MKTRF", "SMB", "HML", "RMW", "CMA", "WML") + (("RF",) if pre == "KF_DEV" else ()):
            nm = f"KF_{'RF' if c == 'RF' else pre[3:] + '_' + c}"
            add(nm, ret_from_daily(df[c], anchors), raw=rr(df[c]), source="Ken French Data Library", file=KF_FILES[pre][0] + (" + " + KF_FILES[pre][1] if c == "WML" else ""),
                region=pre[3:], factor=c, kind="daily_ls_compound", currency="USD (long–short · ไม่แปลงบาท)",
                investable="ไม่ได้ (long–short · ลงทุนไม่ได้)" if c not in ("MKTRF", "RF") else ("ไม่ได้ (ตลาด − rf)" if c == "MKTRF" else "ใช้เป็น rf อ้างอิง"),
                unit="สัดส่วนผลตอบแทนต่อช่วง", line="②", freq_native="daily")
    # --- KF รายเดือนทางการ (monthly-native · เฉพาะ parquet รายเดือน): Developed (ใช้เทียบ/ทางเลือก WML) และ Emerging (ไม่มีรายวัน)
    if monthly:
        me_idx = pd.DatetimeIndex(anchors[1:])
        for pre, reg_ in (("KFM_DEV", "DEV"), ("KFM_EM", "EM")):
            km = src["kf_m"]["KF_" + reg_]
            for c in ("MKTRF", "SMB", "HML", "RMW", "CMA", "WML"):
                s_ = km[c].reindex(me_idx)
                f5, fm = KF_MONTHLY["KF_" + reg_]
                add(f"{pre}_{c}", s_.to_numpy(float), raw=rr(km[c]), source="Ken French Data Library", file=f5 + (" + " + fm if c == "WML" else ""),
                    region=reg_, factor=c, kind="monthly_native", currency="USD (long–short · ไม่แปลงบาท)",
                    investable="ไม่ได้ (long–short · ลงทุนไม่ได้)" if c != "MKTRF" else "ไม่ได้ (ตลาด − rf)",
                    unit="สัดส่วนผลตอบแทนรายเดือน (ไฟล์รายเดือนทางการของ KF)", line="②", freq_native="monthly")
    # --- JKP
    for pre, df in src["jkp"].items():
        for th in df.columns:
            add(f"{pre}_{th}", ret_from_daily(df[th], anchors), raw=rr(df[th]), source="JKP Global Factor Data (CC BY-NC 4.0)",
                file=JKP_FILES[pre], region="emerging" if pre == "JKP_EM" else "developed", factor=th,
                kind="daily_ls_compound", currency="USD (long–short · ไม่แปลงบาท)", investable="ไม่ได้ (long–short · ลงทุนไม่ได้)",
                unit="สัดส่วนผลตอบแทนต่อช่วง (capped VW)", line="②", freq_native="daily")
    # --- AQR
    for pre, df in src["aqr"].items():
        for c in df.columns:
            add(f"{pre}_{c}", ret_from_daily(df[c], anchors), raw=rr(df[c]), source="AQR Data Library", file=AQR_FILES[pre][0],
                region=c, factor=pre[4:], kind="daily_ls_compound", currency="USD (long–short · ไม่แปลงบาท)",
                investable="ไม่ได้ (long–short · ลงทุนไม่ได้)", unit="สัดส่วนผลตอบแทนต่อช่วง (self-financing excess)",
                line="②", freq_native="daily")
    # --- ราคา ETF (USD → บาท ด้วย USDTHB ของทีม)
    fx = L0.asof_series(src["mac"]["USDTHB"], A)
    for c in ("GLD", "VNQ", "VNQI"):
        v = L0.asof_series(src["alt"][c], A)
        for nm, lvl, cur in ((f"{c}_USD", v, "USD"), (f"{c}_THB", v * fx, "THB (ราคา USD × USDTHB)")):
            add(nm, ret_from_price(lvl), raw=rr(src["alt"][c]), source="Yahoo Finance (adjusted close)", file="EO_ALT_ETF.csv", region={"GLD": "ทอง", "VNQ": "REIT สหรัฐฯ", "VNQI": "REIT ex-US"}[c],
                factor=c, kind="etf_price", currency=cur, investable="ได้ (ETF)", unit="สัดส่วนผลตอบแทนต่อช่วง (total return)", line="③", freq_native="daily")
    # --- REIT เอเชียท้องถิ่น + ค่าเงิน
    rl = src["reit"]
    fxj = L0.asof_series(rl["JPYTHB=X"], A)
    fxs = L0.asof_series(rl["SGDTHB=X"], A)
    for tk, nm, cur, fxv, region in (("1343.T", "REIT1343T", "JPY", fxj, "REIT ญี่ปุ่น (TSE · ปิดเวลาโตเกียว)"), ("CLR.SI", "REITCLRSI", "SGD", fxs, "REIT สิงคโปร์ (SGX · ปิดเวลาสิงคโปร์)")):
        v = L0.asof_series(rl[tk], A)
        add(f"{nm}_LOC", ret_from_price(v), raw=rr(rl[tk]), source="Yahoo Finance (adjusted close)", file="ASIA_REIT_LOCAL.csv", region=region, factor=tk, kind="etf_price",
            currency=f"{cur} (สกุลท้องถิ่น)", investable="ได้ (ETF ตลาดท้องถิ่น)", unit="สัดส่วนผลตอบแทนต่อช่วง (total return)", line="③", freq_native="daily")
        add(f"{nm}_THB", ret_from_price(v * fxv), raw=rr(rl[tk]), source="Yahoo Finance (adjusted close)", file="ASIA_REIT_LOCAL.csv", region=region, factor=tk, kind="etf_price",
            currency=f"THB (ราคา {cur} × {cur}THB)", investable="ได้ (ETF ตลาดท้องถิ่น)", unit="สัดส่วนผลตอบแทนต่อช่วง (total return)", line="③", freq_native="daily")
    for nm, fxv, pair in (("FX_JPYTHB", fxj, "JPYTHB"), ("FX_SGDTHB", fxs, "SGDTHB")):
        add(nm, ret_from_price(fxv), raw=rr(rl[pair + "=X"]), source="Yahoo Finance (adjusted close)", file="ASIA_REIT_LOCAL.csv", region=pair, factor=pair, kind="fx",
            currency=f"THB ต่อ 1 {pair[:3]}", investable="ไม่ได้ (ค่าเงิน)", unit="%Δ อัตราแลกเปลี่ยนต่อช่วง (สัดส่วน)", line="④", freq_native="daily")
    # --- FRED
    fr = src["fred"]
    for c, nm in (("DTWEXBGS", "DTWEXBGS_ret"), ("DTWEXEMEGS", "DTWEXEMEGS_ret")):
        add(nm, ret_from_price(L0.asof_series(fr[c], A)), raw=rr(fr[c]), source="FRED", file="US_DOLLAR_REALRATE_FRED.csv", region="ดัชนีดอลลาร์" + (" (กว้าง)" if c == "DTWEXBGS" else " (เทียบสกุล EM)"),
            factor=c, kind="index_ret", currency="USD index", investable="ไม่ได้ (ดัชนี)", unit="%Δ ดัชนีต่อช่วง (สัดส่วน)", line="④", freq_native="daily")
    lvl = L0.asof_series(fr["DFII10"], A)
    add("DFII10_lvl", lvl[1:], raw=rr(fr["DFII10"]), source="FRED", file="US_DOLLAR_REALRATE_FRED.csv", region="TIPS 10Y real yield", factor="DFII10", kind="level_end",
        currency="% ต่อปี", investable="ไม่ได้ (อัตราดอกเบี้ย)", unit="ระดับ (% ต่อปี) ณ ปลายช่วง", line="④", freq_native="daily")
    add("DFII10_d", lvl[1:] - lvl[:-1], raw=rr(fr["DFII10"]), source="FRED", file="US_DOLLAR_REALRATE_FRED.csv", region="TIPS 10Y real yield", factor="DFII10", kind="delta_pp",
        currency="% ต่อปี", investable="ไม่ได้ (อัตราดอกเบี้ย)", unit="Δ ระดับ (จุด %) ต่อช่วง", line="④", freq_native="daily")
    df = pd.DataFrame(cols, index=anchors[1:])
    df.index.name = "date"
    return df, meta


# ---------------------------------------------------------------- 3. ป้ายกลุ่มสาย / ใช้กับ E-O
USE = {   # คอลัมน์ → (ใช้กับ, รหัสไอเดียใน F-R006, หมายเหตุ)
}


def use_for(name: str) -> tuple[str, str, str]:
    if name == "KF_RF":
        return "ref", "-", "rf สหรัฐฯ (T-bill 1 เดือน) ของ KF · ใช้ตรวจเทียบ/ไม่ใช้เป็น factor"
    if name.endswith("_MKTRF"):
        return "ref", "E7", "ตลาด − rf ของ KF · ซ้ำกับ ACWI (F-R006: ไม่ใช้ใน pool) · ใช้ QA เทียบกับ ACWI/MSCI เท่านั้น"
    if name.startswith("KF_DEV_"):
        return "E", "E7", "pool E (SMB/HML/RMW/CMA/WML) · USD long–short ไม่แปลงบาท · Dimson lag 1"
    if name.startswith("KFM_EM_"):
        return ("ref" if name.endswith("_MKTRF") else "E"), "E7/E8", "รายเดือนอย่างเดียว (KF ไม่มี EM รายวัน) · ใช้ตรวจซ้ำรายเดือน / เทียบ JKP EM"
    if name.startswith("KFM_DEV_"):
        return ("ref" if name.endswith("_MKTRF") else "E"), "E7", "ไฟล์รายเดือนทางการของ KF (Developed) · ใช้ตรวจซ้ำรายเดือน (WML รายเดือนทางการต่างจากทบรายวัน · ดู QA ข้อ 5)"
    if name.startswith(("KF_NA_", "KF_EU_", "KF_JP_")):
        return "E", "E9", "factor เฉพาะกลุ่มภูมิภาค (SMB/HML/WML ฯลฯ) ตามชื่อกอง · ไม่ใช้ใน pool ร่วม"
    if name.startswith("JKP_EM_"):
        th = name[7:]
        return "E", "E8", ("theme ที่ F-R006 แนะนำล็อกล่วงหน้า (value/momentum) → pool E ≤ 2 ตัว" if th in ("value", "momentum") else "theme อื่นของ JKP EM · เก็บไว้ครบ แต่ pool ใช้เฉพาะที่ spec ล็อกล่วงหน้า")
    if name.startswith("JKP_DEV_"):
        return "E", "robustness", "JKP developed · ตรวจ KF กับ JKP สอดคล้องกัน (F-R006 ข้อ 9) · ไม่อยู่ใน pool"
    if name.startswith("AQR_"):
        return "E", "E10 robustness", "AQR · robustness เท่านั้น (BRIEF 113) · ไม่อยู่ใน pool"
    if name.startswith("GLD_"):
        return "O", "O1", "ทอง (GLD) ของกองทอง: GOLD_XS = GLD_USD − SHV_USD + FX"
    if name.startswith("VNQI_"):
        return "O", "O4", "REIT ex-US สำหรับกอง REIT global/Asia (ภาคผนวก)"
    if name.startswith("VNQ_"):
        return "O", "O2/O4", "REIT สหรัฐฯ (กอง US REIT 2 กอง) · ภาคผนวกเทียบ REET"
    if name.startswith(("REIT1343T", "REITCLRSI", "FX_JPYTHB", "FX_SGDTHB")):
        return "O", "O4", "REIT ญี่ปุ่น/สิงคโปร์ปิดเวลาเอเชีย · รายกอง (TJREIT / ONEPROP-SG) ภาคผนวก"
    if name.startswith("DTWEX"):
        return "E+O", "E12", "ดอลลาร์ (F-R006: ไม่อยู่ใน pool E · ตัวเทียบ FX) "
    if name.startswith("DFII10"):
        return "O", "O6", "ดอกเบี้ยแท้จริง 10Y (F-R006: ไม่แนะนำ · เก็บเป็นภาคผนวก)"
    return "?", "?", ""


# ---------------------------------------------------------------- 4. AUM_fam / อายุ family → U_E / U_O
_GOLD_RE = re.compile(r"gold(?!en)")          # ตรงกับ lib/p2.py is_gold (S011 ข้อ 1.1)
_REIT_RE = re.compile(r"reit|prop|real estate|estate", re.I)


def is_gold(name_en, name_th) -> bool:
    en = name_en.lower() if isinstance(name_en, str) else ""
    th = name_th if isinstance(name_th, str) else ""
    return bool(_GOLD_RE.search(en)) or ("ทองคำ" in th)


def is_reit(name_en, name_th) -> bool:
    en = name_en if isinstance(name_en, str) else ""
    th = name_th if isinstance(name_th, str) else ""
    return bool(_REIT_RE.search(en)) or ("อสังหา" in th) or ("รีท" in th)


def read_nav_aum_age(t_aum: pd.Timestamp):
    """อ่าน nav_history_db.csv ทั้งไฟล์แบบ chunk (อ่านอย่างเดียว · ทุก class) → (first_nav ต่อ class, แถวหน้าต่าง AUM ที่ dedupe แล้ว, stats).
    ใช้แถว NAV > 0 และ NAVDate/NAV ไม่ว่าง (เหมือน build_l0.load_nav) · หน้าต่าง AUM = NAVDate ∈ [t−90 วัน, t]."""
    c = config
    first, win, rows_total, rows_valid = {}, [], 0, 0
    lo = t_aum - pd.Timedelta(days=AUM_STALE_DAYS)
    for ch in pd.read_csv(c.NAV_HISTORY_CSV, usecols=c.NAV_USECOLS, dtype={c.NAV_FUND_CODE_COL: str}, chunksize=c.NAV_CHUNKSIZE):
        rows_total += len(ch)
        ch[c.NAV_FUND_CODE_COL] = ch[c.NAV_FUND_CODE_COL].str.strip()
        ch[c.NAV_DATE_COL] = pd.to_datetime(ch[c.NAV_DATE_COL], errors="coerce")
        ch[c.NAV_COL] = pd.to_numeric(ch[c.NAV_COL], errors="coerce")
        ch[c.NAV_AUM_COL] = pd.to_numeric(ch[c.NAV_AUM_COL], errors="coerce")
        ch = ch.dropna(subset=[c.NAV_DATE_COL, c.NAV_COL])
        ch = ch[ch[c.NAV_COL] > 0]
        rows_valid += len(ch)
        g = ch.groupby(c.NAV_FUND_CODE_COL)[c.NAV_DATE_COL].min()
        for k, v in g.items():
            if k not in first or v < first[k]:
                first[k] = v
        w = ch[(ch[c.NAV_DATE_COL] <= t_aum) & (ch[c.NAV_DATE_COL] >= lo)]
        if len(w):
            win.append(w)
    w = pd.concat(win, ignore_index=True)
    w["_upd"] = L0.nav_loader.parse_update_time(w[c.NAV_UPDATE_COL])
    w = w.sort_values("_upd", na_position="first", kind="stable")
    n_before = len(w)
    w = w.drop_duplicates(subset=[c.NAV_FUND_CODE_COL, c.NAV_DATE_COL], keep="last")
    w = w.sort_values([c.NAV_FUND_CODE_COL, c.NAV_DATE_COL]).reset_index(drop=True)
    return pd.Series(first).sort_index(), w, {"rows_total": rows_total, "rows_valid_nav": rows_valid, "window_rows_before_dedupe": n_before,
                                              "window_rows_after_dedupe": len(w)}


def build_aum_fam(prof: pd.DataFrame, uni: pd.DataFrame):
    c = config
    first_nav, win, nstats = read_nav_aum_age(AUM_ASOF)
    assert win[c.NAV_DATE_COL].max() <= AUM_ASOF, "AUM ใช้แถวหลัง 2023-12-31"
    grp = pd.read_csv(os.path.join(BD, "share_class_groups.csv"), encoding="utf-8-sig")
    groups = dict(zip(grp["FundCode"].str.strip(), grp["group"].str.strip()))
    prof = prof.copy()
    prof["code"] = prof[c.FUND_CODE_COL].astype(str).str.strip()
    prof["reg"] = pd.to_datetime(prof["Registration_date"].fillna("").astype(str).str.strip(), format="%Y%m%d", errors="coerce")
    reg = prof.drop_duplicates("code").set_index("code")["reg"]
    names = prof.drop_duplicates("code").set_index("code")[["Fund Name EN", "Fund Name TH"]]
    all_codes = sorted(set(first_nav.index) | set(prof["code"]))
    fam_of = {k: L0.family_of(k, groups, True) for k in all_codes}

    # AUM ต่อ class: แถวล่าสุดที่ AUM > 0 ภายใน 90 วัน (หลัง dedupe) → ผลรวมต่อ family
    wp = win[win[c.NAV_AUM_COL].notna() & (win[c.NAV_AUM_COL] > 0)]
    last = wp.sort_values([c.NAV_FUND_CODE_COL, c.NAV_DATE_COL]).drop_duplicates(c.NAV_FUND_CODE_COL, keep="last")
    aum_c = last.set_index(c.NAV_FUND_CODE_COL)[c.NAV_AUM_COL]
    aum_date = last.set_index(c.NAV_FUND_CODE_COL)[c.NAV_DATE_COL]
    cl = pd.DataFrame({"code": all_codes})
    cl["family"] = cl["code"].map(fam_of)
    cl["aum"] = cl["code"].map(aum_c).fillna(0.0)
    cl["aum_date"] = cl["code"].map(aum_date)
    cl["first_nav"] = cl["code"].map(first_nav)
    cl["reg"] = cl["code"].map(reg)
    cl["reg_used"] = cl["reg"].where(cl["reg"] <= AGE_ASOF)                    # Registration_date > t ไม่นับ (M012 §2)
    cl["first_nav_used"] = cl["first_nav"].where(cl["first_nav"] <= AGE_ASOF)
    cl["first_c"] = cl[["reg_used", "first_nav_used"]].min(axis=1)
    fam = cl.groupby("family").agg(n_classes=("code", "size"), n_classes_aum_pos=("aum", lambda s: int((s > 0).sum())),
                                    aum_fam_2023=("aum", "sum"), first_date_fam=("first_c", "min"),
                                    first_nav_fam=("first_nav_used", "min"), last_aum_date=("aum_date", "max"))
    fam["age_days_2025"] = (AGE_ASOF - fam["first_date_fam"]).dt.days
    fam["pass_aum"] = fam["aum_fam_2023"] >= AUM_MIN
    fam["pass_age"] = fam["age_days_2025"] >= AGE_MIN_DAYS                       # NaN วัน → False

    # ผูกกับ universe เดิม (ตัวแทน family ใน panel)
    u = uni.copy()
    u = u[["FundCode", "family", "policy", "included", "n_weeks", "first", "last", "nav_last"]]
    rep = u[u["included"]].set_index("family")
    out = fam.loc[fam.index.intersection(u["family"].unique())].copy()
    out["FundCode"] = [rep.loc[f, "FundCode"] if f in rep.index else None for f in out.index]
    first_code = u.sort_values("FundCode").drop_duplicates("family").set_index("family")["FundCode"]
    out["FundCode"] = out["FundCode"].fillna(first_code.reindex(out.index))
    out["included"] = [f in rep.index for f in out.index]
    out["policy"] = u.drop_duplicates("family").set_index("family")["policy"].reindex(out.index)
    out.loc[out["included"], "policy"] = rep["policy"].reindex(out.index[out["included"]])
    out["name_en"] = [names["Fund Name EN"].get(k) for k in out["FundCode"]]
    out["name_th"] = [names["Fund Name TH"].get(k) for k in out["FundCode"]]
    out["pass_both"] = out["pass_aum"] & out["pass_age"]
    out["in_U"] = out["included"] & out["pass_both"] & out["policy"].isin(["E", "O"])
    out["o_kind"] = ""
    for f in out.index[out["policy"] == "O"]:
        g, r = is_gold(out.at[f, "name_en"], out.at[f, "name_th"]), is_reit(out.at[f, "name_en"], out.at[f, "name_th"])
        out.at[f, "o_kind"] = "gold" if g else ("reit" if r else "other")
    out["nav_last"] = u[u["included"]].set_index("family")["nav_last"].reindex(out.index)
    out["last_valid_week"] = u[u["included"]].set_index("family")["last"].reindex(out.index)
    out = out.reset_index().rename(columns={"family": "family"})
    out = out[["family", "FundCode", "policy", "included", "n_classes", "n_classes_aum_pos", "aum_fam_2023", "last_aum_date",
               "first_date_fam", "first_nav_fam", "age_days_2025", "pass_aum", "pass_age", "pass_both", "in_U", "o_kind",
               "name_en", "nav_last", "last_valid_week"]].sort_values(["policy", "family"], kind="stable").reset_index(drop=True)
    return out, cl, nstats, fam_of


# ---------------------------------------------------------------- 5. ตรวจไฟล์ L0 เดิมไม่ถูกแก้
def check_untouched() -> list[dict]:
    res = []
    for mf in ("manifest.json", "manifest_ext.json"):
        man = json.load(open(os.path.join(HERE, mf), encoding="utf-8"))
        for o in man["outputs"]:
            if o["file"].endswith("QA_L0.md"):   # มีวันที่สร้างในเนื้อหา แต่ sha ใน manifest ยังตรงกับไฟล์ปัจจุบัน
                pass
            p = os.path.join(ROOT, o["file"])
            now = L0.sha256(p)
            res.append({"manifest": mf, "file": o["file"], "sha256_manifest": o["sha256"], "sha256_now": now, "match": now == o["sha256"]})
    return res


# ---------------------------------------------------------------- main
def main():
    os.makedirs(OUT, exist_ok=True)
    today = date.today().isoformat()

    # ---------- โหลดทุกแหล่ง
    kf = load_kf_daily()
    kf_m = load_kf_monthly()
    jkp = load_jkp()
    aqr, aqr_meta = {}, {}
    for pre, (f, sh) in AQR_FILES.items():
        aqr[pre], aqr_meta[pre] = read_aqr(os.path.join(RAW, f), sh, AQR_SERIES)
    alt, dropped_alt = load_yahoo("EO_ALT_ETF.csv")
    reit, dropped_reit = load_yahoo("ASIA_REIT_LOCAL.csv")
    fred = pd.read_csv(os.path.join(EXT, "US_DOLLAR_REALRATE_FRED.csv"), parse_dates=["Date"]).set_index("Date").sort_index()
    mac = pd.read_csv(config.MACRO_FACTOR_CSV, parse_dates=["Date"]).set_index("Date").sort_index()
    src = {"kf": kf, "kf_m": kf_m, "jkp": jkp, "aqr": aqr, "alt": alt, "reit": reit, "fred": fred, "mac": mac}

    wk = pd.date_range("2021-01-01", L0.PANEL_END, freq="W-FRI")
    me = pd.DatetimeIndex([pd.Timestamp("2020-12-31")] + list(pd.date_range("2021-01-31", L0.PANEL_END, freq="ME")))
    Fw, meta = make_eo(wk, src, monthly=False)
    Fm, meta_m = make_eo(me, src, monthly=True)
    assert list(Fw.columns) == [c for c in Fm.columns if not c.startswith("KFM_")]
    assert all(meta[c] == meta_m[c] for c in Fw.columns)
    meta.update(meta_m)

    # ---------- assert พื้นฐาน
    f0w = pd.read_parquet(os.path.join(HERE, "factors_weekly.parquet"))
    f0m = pd.read_parquet(os.path.join(HERE, "factors_monthly.parquet"))
    e0w = pd.read_parquet(os.path.join(HERE, "factors_ext_weekly.parquet"))
    e0m = pd.read_parquet(os.path.join(HERE, "factors_ext_monthly.parquet"))
    assert Fw.index.equals(f0w.index) and Fm.index.equals(f0m.index), "จุดวันที่ไม่ตรงกับ factors_weekly/monthly เดิม"
    dup_cols = sorted((set(Fw.columns) | set(Fm.columns)) & (set(f0w.columns) | set(e0w.columns)))
    assert not dup_cols, dup_cols
    assert not np.isinf(Fw.to_numpy(float)).any() and not np.isinf(Fm.to_numpy(float)).any()
    mw, mm = main_mask(Fw.index), main_mask(Fm.index)
    for pre in ("KF_", "JKP_", "AQR_", "GLD_", "VNQ_", "REIT", "FX_", "DTWEX", "DFII10"):
        cw = [c for c in Fw.columns if c.startswith(pre)]
        assert not Fw.loc[mw, cw].isna().any().any(), ("NaN ในช่วงหลัก (รายสัปดาห์)", pre)
    for c in Fm.columns:
        assert not Fm.loc[mm, c].isna().any(), ("NaN ในช่วงหลัก (รายเดือน)", c)
    # JKP: ต้องเป็น NaN ตั้งแต่ anchor ที่เลยข้อมูล (2025-12-31)
    jc = [c for c in Fw.columns if c.startswith("JKP_")]
    assert Fw.loc[Fw.index > pd.Timestamp("2025-12-31"), jc].isna().all().all() and Fm.loc[Fm.index > pd.Timestamp("2025-12-31"), jc].isna().all().all()

    Fw.to_parquet(os.path.join(OUT, "factors_eo_weekly.parquet"))
    Fm.to_parquet(os.path.join(OUT, "factors_eo_monthly.parquet"))

    # ---------- factor_groups_eo.csv
    rows = []
    for c in Fm.columns:
        m = meta[c]
        uf, idea, note = use_for(c)
        s = Fw[c] if c in Fw.columns else None
        lw = s.dropna().index.max() if s is not None else pd.NaT
        rows.append({"factor": c, "source": m["source"], "source_file": m["file"], "line": m["line"], "use_for": uf, "idea_F-R006": idea,
                     "investable": m["investable"], "currency": m["currency"], "unit": m["unit"], "kind": m["kind"], "freq_native": m["freq_native"],
                     "in_weekly": c in Fw.columns, "in_monthly": True, "last_valid_weekly": lw, "last_valid_monthly": Fm[c].dropna().index.max(),
                     "region": m["region"], "factor_name": m["factor"], "raw_first": m["raw"][0], "raw_last": m["raw"][1], "raw_rows": m["raw"][2],
                     "note": note})
    fg = pd.DataFrame(rows)
    fg.to_csv(os.path.join(OUT, "factor_groups_eo.csv"), index=False, date_format="%Y-%m-%d")

    # ---------- eo_row_flags.csv (แยกแถวที่ใช้ fit ได้ vs ดูประกอบหลัง 2025-12-31)
    fl = pd.concat([pd.DataFrame({"date": Fw.index, "freq": "weekly"}), pd.DataFrame({"date": Fm.index, "freq": "monthly"})], ignore_index=True)
    fl["main_period_fit_ok"] = (fl["date"] > L0.MAIN_START) & (fl["date"] <= L0.MAIN_END)
    fl["display_only_post_2025"] = fl["date"] > L0.MAIN_END
    fl.to_csv(os.path.join(OUT, "eo_row_flags.csv"), index=False, date_format="%Y-%m-%d")

    # ---------- AUM_fam
    prof_full = L0.fund_profile.load_fund_profile()     # FundProfile ทั้งตาราง (ทุก class · Registration_date)
    uni = pd.read_csv(os.path.join(HERE, "universe.csv"), parse_dates=["first", "last", "nav_first", "nav_last"])
    aum, cl, nstats, fam_of = build_aum_fam(prof_full, uni)
    aum.to_parquet(os.path.join(OUT, "aum_fam.parquet"), index=False)

    ctx = dict(today=today, Fw=Fw, Fm=Fm, meta=meta, fg=fg, src=src, f0w=f0w, f0m=f0m, e0w=e0w, e0m=e0m, aum=aum, cl=cl, nstats=nstats, uni=uni,
               dropped={"EO_ALT_ETF.csv": dropped_alt, "ASIA_REIT_LOCAL.csv": dropped_reit}, aqr_meta=aqr_meta, wk=wk, me=me, prof_full=prof_full)
    qa_md = make_qa(ctx)
    open(os.path.join(OUT, "QA_EO.md"), "w", encoding="utf-8").write(qa_md)

    # ---------- manifest_eo.json
    chk = check_untouched()
    bad = [c for c in chk if not c["match"]]
    assert not bad, bad
    raw_files = sorted(os.listdir(RAW))
    ins = [info_raw(os.path.join(RAW, f)) for f in raw_files] + \
          [L0.info_file(os.path.join(EXT, f), "Date") for f in ("EO_ALT_ETF.csv", "US_DOLLAR_REALRATE_FRED.csv", "ASIA_REIT_LOCAL.csv")] + \
          [L0.info_file(config.MACRO_FACTOR_CSV, "Date"), L0.info_file(config.FUND_PROFILE_CSV), L0.info_file(config.NAV_HISTORY_CSV, "NAVDate"),
           L0.info_file(os.path.join(BD, "share_class_groups.csv")), L0.info_file(os.path.join(HERE, "universe.csv")),
           L0.info_file(os.path.join(HERE, "build_l0.py")), L0.info_file(os.path.join(HERE, "build_eo.py"))]
    outs = []
    for f in ("factors_eo_weekly.parquet", "factors_eo_monthly.parquet", "aum_fam.parquet"):
        p = os.path.join(OUT, f)
        x = pd.read_parquet(p)
        d = L0.info_file(p)
        d["columns"] = int(x.shape[1])
        if f.startswith("factors_"):
            d.update({"date_min": f"{x.index.min():%Y-%m-%d}", "date_max": f"{x.index.max():%Y-%m-%d}"})
        outs.append(d)
    for f in ("factor_groups_eo.csv", "eo_row_flags.csv", "QA_EO.md"):
        outs.append({"file": os.path.relpath(os.path.join(OUT, f), ROOT), "sha256": L0.sha256(os.path.join(OUT, f))})
    man = {"created": today, "script": "build_eo.py", "pandas": pd.__version__, "numpy": np.__version__, "python": sys.version.split()[0],
           "criteria": {"anchors": "weekly W-FRI 2021-01-01→2026-07-31 · monthly month-end 2020-12-31→2026-07-31 (เหมือน build_l0.py)",
                        "asof_tolerance_calendar_days": L0.ASOF_TOL_DAYS, "daily_factor": "cum index (1+r) เริ่ม 2020-10-01 แล้ว asof ที่ anchor · anchor เลยข้อมูลวันสุดท้าย = NaN",
                        "kf_units": "% → สัดส่วน (÷100) · -99.99 = ขาด", "usd_to_thb": "ราคา × USDTHB (MACRO_FACTOR.csv) แล้วหาผลตอบแทน · REIT เอเชีย × JPYTHB/SGDTHB",
                        "yahoo_drop_date_ge": f"{DOWNLOAD_DATE:%Y-%m-%d}",
                        "aum": {"asof": f"{AUM_ASOF:%Y-%m-%d}", "min_baht": AUM_MIN, "stale_days": AUM_STALE_DAYS, "age_asof": f"{AGE_ASOF:%Y-%m-%d}", "age_min_days": AGE_MIN_DAYS,
                                "age_def": "min(Registration_date ≤ 2025-12-31, NAV แรก) ของทุก class ใน family", "family_map": "build_l0.family_of(fixed=True) + share_class_groups.csv"},
                        "aqr_series": AQR_SERIES, "flags": {"weekly_abs_ret": WEEK_ABN, "monthly_abs_ret": MONTH_ABN, "z_abn": Z_ABN},
                        "main_period": [f"{L0.MAIN_START:%Y-%m-%d}", f"{L0.MAIN_END:%Y-%m-%d}"]},
           "counts": {"weekly_cols": int(Fw.shape[1]), "monthly_cols": int(Fm.shape[1]),
                      "U_E": int(((aum["policy"] == "E") & aum["in_U"]).sum()), "U_O": int(((aum["policy"] == "O") & aum["in_U"]).sum())},
           "inputs": ins, "outputs": outs, "l0_untouched_check": chk}
    with open(os.path.join(OUT, "manifest_eo.json"), "w", encoding="utf-8") as f:
        json.dump(man, f, ensure_ascii=False, indent=1, default=str)
    print("done", Fw.shape, Fm.shape, "U_E/U_O", man["counts"]["U_E"], man["counts"]["U_O"], "l0_untouched:", not bad)


def cc(a: pd.Series, b: pd.Series, mask=None) -> tuple[float, int]:
    j = pd.concat([a, b], axis=1, keys=["a", "b"]).dropna()
    if mask is not None:
        j = j[main_mask(j.index)]
    if len(j) < 5:
        return (np.nan, len(j))
    return (float(j["a"].corr(j["b"])), len(j))


def make_qa(ctx: dict) -> str:
    Fw, Fm, meta, fg, src = ctx["Fw"], ctx["Fm"], ctx["meta"], ctx["fg"], ctx["src"]
    f0w, f0m, e0w, e0m = ctx["f0w"], ctx["f0m"], ctx["e0w"], ctx["e0m"]
    aum, cl, nstats, uni = ctx["aum"], ctx["cl"], ctx["nstats"], ctx["uni"]
    mw, mm = main_mask(Fw.index), main_mask(Fm.index)
    L: list[str] = []
    P = L.append
    old_w = pd.concat([f0w, e0w], axis=1)
    old_m = pd.concat([f0m, e0m], axis=1)
    ret_cols = [c for c in Fw.columns if not c.endswith("_lvl")]
    tr_mask = np.asarray((Fw.index > L0.MAIN_START) & (Fw.index <= TRAIN_END))
    te_mask = np.asarray((Fw.index > TRAIN_END) & (Fw.index <= L0.MAIN_END))

    P("# QA_EO — factor ภายนอกใหม่ (F5-EO) + AUM_fam / U_E / U_O\n")
    P("สร้างโดย `build_eo.py` (เนื้อหาไฟล์นี้ไม่มีวันที่สร้างเพื่อให้ผลเหมือนเดิมทุกบิต · วันที่สร้างอยู่ใน `manifest_eo.json`) · ไม่แก้ไฟล์ L0 เดิม · ไม่ดาวน์โหลดเพิ่ม · "
      "ตัวเลขทุกตัวในไฟล์นี้มาจากการรันของ `build_eo.py` รอบนี้\n")

    # ------------------------------------------------------------------ สรุป
    P("## สรุป\n")
    src_cnt = fg.groupby("source").agg(weekly=("in_weekly", "sum"), monthly=("in_monthly", "sum")).reset_index()
    P(f"- weekly: {Fw.shape[0]} สัปดาห์ × {Fw.shape[1]} คอลัมน์ ({Fw.index.min():%Y-%m-%d} → {Fw.index.max():%Y-%m-%d}) · "
      f"monthly: {Fm.shape[0]} เดือน × {Fm.shape[1]} คอลัมน์ ({Fm.index.min():%Y-%m-%d} → {Fm.index.max():%Y-%m-%d}) · คอลัมน์รายเดือนที่เกินรายสัปดาห์ = `KFM_*` 12 ตัว (ไฟล์รายเดือนทางการของ KF: Developed 6 + Emerging 6 · KF ไม่มี EM รายวัน)")
    P(f"- index วันที่ตรงกับ `factors_weekly.parquet` / `factors_monthly.parquet` เดิม = **ผ่าน** (assert) · ชื่อคอลัมน์ไม่ชนกับ L0 / ext เดิม = **ผ่าน** (assert)")
    P("- จำนวนคอลัมน์ต่อแหล่ง:\n")
    P(md_table(src_cnt.rename(columns={"source": "แหล่ง", "weekly": "คอลัมน์ weekly", "monthly": "คอลัมน์ monthly"})))
    grp = fg.groupby(["line", "use_for"]).size().reset_index(name="n")
    P("\n- แยกตามสาย (F-R006) × ใช้กับ E/O (ดู `factor_groups_eo.csv`):\n")
    P(md_table(grp.rename(columns={"line": "สาย", "use_for": "ใช้กับ"})))
    P("\n- หน่วย: factor long–short (KF / JKP / AQR) เป็น**สัดส่วนผลตอบแทน** (0.01 = 1%) USD **ไม่แปลงเป็นบาท** · ราคา ETF = USD และบาท (× USDTHB เดิมของทีม) · REIT เอเชีย = สกุลท้องถิ่น และบาท (× JPYTHB / SGDTHB) · "
      "FRED ดอลลาร์ = %Δ ดัชนี · DFII10 = ระดับ (`_lvl`) + Δ จุด % (`_d`)")
    P("- จุดปิดสัปดาห์ / สิ้นเดือน = anchors เดียวกับ `build_l0.py` (W-FRI 2021-01-01 → 2026-07-31) · factor รายวันทบต้นเป็น cum index แล้ว asof ที่ anchor (≤ วันอ้างอิง · ห่าง ≤ 10 วัน) "
      "· **สัปดาห์ที่ anchor เลยวันสุดท้ายของข้อมูลเป็น NaN** (JKP จบ 2025-12-31 → สัปดาห์สิ้นสุด 2026-01-02 เป็นต้นไปเป็น NaN เพราะวันที่ 2 ม.ค. ไม่มีข้อมูล · สัปดาห์สุดท้ายของช่วงหลักที่ใช้ได้คือ 2025-12-26 · รายเดือนใช้ได้ถึง 2025-12-31)")
    P("- **ช่วงหลักที่ใช้ fit** = (2021-01-01, 2025-12-31] → weekly 2021-01-08 … 2025-12-26 · แถวหลัง 2025-12-31 = ดูประกอบเท่านั้น (แยก flag ใน `eo_row_flags.csv` คอลัมน์ `display_only_post_2025`)")
    P(f"- weekly ในช่วงหลัก = {int(mw.sum())} สัปดาห์ (train 2021-01-08…2023-12-29 = {int(tr_mask.sum())} · test 2024-01-05…2025-12-26 = {int(te_mask.sum())}) · monthly ในช่วงหลัก = {int(mm.sum())} เดือน\n")

    # ------------------------------------------------------------------ 1 NaN
    P("## 1. NaN ในช่วงหลัก 2021-01 → 2025-12\n")
    nw = Fw.loc[mw].isna().sum()
    nm_ = Fm.loc[mm].isna().sum()
    tot = int(nw.sum() + nm_.sum())
    P(f"- NaN รวมทุกคอลัมน์ในช่วงหลัก weekly + monthly = **{tot}** ({'ผ่าน' if tot == 0 else 'เตือน'})")
    after_w = Fw.loc[~mw].isna().sum()
    P(f"- NaN นอกช่วงหลัก (2026): weekly {int(after_w.sum())} จุด ใน {int((after_w > 0).sum())} คอลัมน์ — **ทั้งหมดเป็น JKP 26 ตัว × {int(after_w.max())} สัปดาห์** (ข้อมูล JKP จบ 2025-12-31) · "
      "แหล่งอื่น (KF / AQR / ETF / FRED) ครบถึง 2026-07-31\n")
    if tot:
        P(md_table(pd.DataFrame({"col": nw.index, "nan_weekly": nw.values}).query("nan_weekly>0")))

    # ------------------------------------------------------------------ 2 ช่วงที่มีจริง
    P("## 2. ช่วงข้อมูลจริงต่อคอลัมน์\n")
    rows = []
    for c in Fm.columns:
        m = meta[c]
        sw = Fw[c] if c in Fw.columns else None
        sm = Fm[c]
        fvw = sw.first_valid_index() if sw is not None else None
        lvw = sw.last_valid_index() if sw is not None else None
        rows.append([c, m["raw"][0], m["raw"][1], m["raw"][2],
                     f"{fvw:%Y-%m-%d}" if fvw is not None else "-", f"{lvw:%Y-%m-%d}" if lvw is not None else "-",
                     int(sw.notna().sum()) if sw is not None else "-",
                     int(sw[tr_mask].notna().sum()) if sw is not None else "-", int(sw[te_mask].notna().sum()) if sw is not None else "-",
                     f"{sm.first_valid_index():%Y-%m-%d}", f"{sm.last_valid_index():%Y-%m-%d}", int(sm.notna().sum()), int(sm[mm].notna().sum())])
    P(md_table(pd.DataFrame(rows, columns=["col", "raw_first", "raw_last", "raw_rows", "weekly_first", "weekly_last", "n_weeks", "n_train", "n_test",
                                           "monthly_first", "monthly_last", "n_months", "n_months_main"])))
    P("\n- ทุกคอลัมน์ weekly ครบ train 156 สัปดาห์ และ test 104 สัปดาห์ (ไม่มี NaN) → จำนวนสัปดาห์ที่ใช้ได้ไม่เป็นข้อจำกัด · ข้อจำกัดอยู่ที่ **JKP ใช้ดูปี 2026 ไม่ได้** และ KF EM มีแค่รายเดือน (60 เดือนในช่วงหลัก)")
    P("- แหล่งดิบที่ราคาเริ่ม 2020-11-02 (ETF / FRED / REIT) → ครอบคลุมตั้งแต่สัปดาห์แรกของ panel · KF / JKP / AQR เริ่มก่อนปี 2000 (ตัดเริ่ม cum index ที่ 2020-10-01)\n")

    # ------------------------------------------------------------------ 3 ค่าสุดโต่ง
    P("## 3. ค่าสุดโต่ง\n")
    zr = []
    for c in ret_cols:
        x = Fw.loc[mw, c]
        z = (x - x.mean()) / x.std()
        big = z.index[z.abs() > Z_ABN]
        zr.append([c, f"{x.min():.4f}", f"{x.idxmin():%Y-%m-%d}", f"{x.max():.4f}", f"{x.idxmax():%Y-%m-%d}", f"{z.abs().max():.2f}", len(big),
                   f"{(x == 0).mean():.3f}", (int((x.abs() > WEEK_ABN).sum()) if not c.endswith("_d") else 0)])
    zdf = pd.DataFrame(zr, columns=["col", "w_min", "w_min_date", "w_max", "w_max_date", "max|z|", f"n|z|>{Z_ABN:g}", "w_zero_frac", f"w_|r|>{WEEK_ABN:.0%}"])
    nz = int((zdf[f"n|z|>{Z_ABN:g}"] > 0).sum())
    P(f"- z = (r − mean)/sd บนผลตอบแทนรายสัปดาห์ช่วงหลัก ({int(mw.sum())} สัปดาห์) · คอลัมน์ที่มี |z| > {Z_ABN:g}: **{nz}** จาก {len(ret_cols)} · สัปดาห์ที่ |r| > {WEEK_ABN:.0%} รวม {int(zdf[f'w_|r|>{WEEK_ABN:.0%}'].sum())} จุด (ไม่นับ `DFII10_d` ซึ่งเป็น Δ จุด % ไม่ใช่ผลตอบแทน)\n")
    P("เรียงตาม max|z| มากสุด 15 อันดับ:\n")
    P(md_table(zdf.sort_values("max|z|", ascending=False, key=lambda s: s.astype(float)).head(15)))
    flagged = zdf[zdf[f"n|z|>{Z_ABN:g}"] > 0]
    if len(flagged):
        P("\nคอลัมน์ที่เกินเกณฑ์ |z| > %g (วันที่ที่เกิน):\n" % Z_ABN)
        for c in flagged["col"]:
            x = Fw.loc[mw, c]
            z = (x - x.mean()) / x.std()
            P(f"- `{c}`: " + "; ".join(f"{d:%Y-%m-%d} {x[d]:+.4f} (z {z[d]:+.1f})" for d in z.index[z.abs() > Z_ABN]))
    P("\n- ค่าสุดโต่งที่พบเกิดซ้ำในสัปดาห์เดียวกันข้าม factor/แหล่ง (เช่น KF_EU_WML และ JKP_DEV_momentum ที่ 2022-11-11) → เป็นเหตุการณ์ตลาดร่วม ไม่ใช่ข้อผิดพลาดรายตัวของไฟล์ (ไม่ได้ตรวจสาเหตุกับข่าว) · ไม่แก้ค่าใดๆ\n")
    P("### ไฟล์ดิบรายวันของ ETF / FX (Yahoo)\n")
    dr = []
    for nmf, cols_ in (("EO_ALT_ETF.csv", ["GLD", "VNQ", "VNQI"]), ("ASIA_REIT_LOCAL.csv", ["1343.T", "CLR.SI", "JPYTHB=X", "SGDTHB=X"])):
        d = src["alt"] if nmf.startswith("EO_") else src["reit"]
        for c in cols_:
            s_ = d[c].dropna()
            r_ = s_.pct_change().dropna()
            dr.append([nmf, c, len(d), int(d[c].isna().sum()), int((s_ <= 0).sum()), int(d.index.duplicated().sum()), f"{r_.abs().max():.3f}", f"{r_.abs().idxmax():%Y-%m-%d}",
                       int((r_.abs() > 0.10).sum())])
    P(md_table(pd.DataFrame(dr, columns=["ไฟล์", "ticker", "แถว", "NaN", "price<=0", "วันซ้ำ", "max|daily|", "date", "n|daily|>10%"])))
    P(f"\n- แถว Yahoo ที่ Date ≥ {DOWNLOAD_DATE:%Y-%m-%d} (วันดาวน์โหลด · ข้อมูลยังไม่ปิดวัน) ถูกตัด: " + ", ".join(f"{k} {v} แถว" for k, v in ctx["dropped"].items()) +
      " · อยู่นอก panel (สิ้นสุด 2026-07-31) จึงไม่กระทบผลอยู่แล้ว")
    P(f"- NaN ในไฟล์ดิบ ASIA_REIT_LOCAL = วันหยุดตลาดท้องถิ่น (1343.T / CLR.SI) และวันที่ Yahoo ไม่มีค่าเงิน → asof ≤ วันอ้างอิง (≤ 10 วัน) ครอบคลุมทั้งหมด (ไม่มี NaN ใน weekly ช่วงหลัก)")
    zero_etf = [c for c in Fw.columns if c.endswith(("_USD", "_LOC")) and (Fw.loc[mw, c] == 0).any()]
    P("- สัปดาห์ผลตอบแทน = 0 (ราคาปิดซ้ำ): " + (", ".join(f"{c} {int((Fw.loc[mw, c] == 0).sum())}" for c in zero_etf) if zero_etf else "ไม่มีในกลุ่ม ETF USD / LOC") + "\n")

    # ------------------------------------------------------------------ 4 เทียบ KF / ACWI / ทอง / REIT
    P("## 4. corr จริงเทียบ factor เดิม (ช่วงหลัก · weekly เว้นแต่ระบุ) — เทียบกับ \"ค่าคาดการณ์\" ใน F-R006\n")
    cmp_rows = []

    def add_cmp(label, a, b, expect, freq="weekly"):
        if freq == "weekly":
            r_, n_ = cc(a, b, True)
        else:
            r_, n_ = cc(a, b, True)
        cmp_rows.append([label, freq, n_, fmt(r_, 4), expect, ""])

    kfm = Fw["KF_DEV_MKTRF"] + Fw["KF_RF"]
    add_cmp("KF_DEV_MKTRF + KF_RF (ตลาดพัฒนาแล้ว USD) vs ACWI_ETF_USD", kfm, f0w["ACWI_ETF_USD"], "> 0.95 (KF Mkt กับ ACWI USD)")
    add_cmp("KF_DEV_MKTRF vs MSCI_WORLD (THB)", Fw["KF_DEV_MKTRF"], f0w["MSCI_WORLD"], "— (ตลาด USD vs ดัชนี THB)")
    add_cmp("KF_DEV_MKTRF vs MSCI_ACWI (THB)", Fw["KF_DEV_MKTRF"], f0w["MSCI_ACWI"], "—")
    add_cmp("KF_NA_MKTRF vs MSCI_USA (THB)", Fw["KF_NA_MKTRF"], f0w["MSCI_USA"], "—")
    add_cmp("KF_EU_MKTRF vs MSCI_EUROPE (THB)", Fw["KF_EU_MKTRF"], f0w["MSCI_EUROPE"], "—")
    add_cmp("KF_JP_MKTRF vs MSCI_JAPAN (THB)", Fw["KF_JP_MKTRF"], f0w["MSCI_JAPAN"], "—")
    add_cmp("KF_DEV_HML vs Value (style ETF de-market)", Fw["KF_DEV_HML"], f0w["Value"], "~0.4–0.7")
    add_cmp("KF_DEV_WML vs Momentum (style ETF)", Fw["KF_DEV_WML"], f0w["Momentum"], "~0.4–0.7")
    add_cmp("KF_DEV_RMW vs Quality (style ETF)", Fw["KF_DEV_RMW"], f0w["Quality"], "~0.3–0.6")
    add_cmp("GLD_USD vs Gold (GC=F · USD)", Fw["GLD_USD"], f0w["Gold"], "> 0.98")
    add_cmp("GLD_THB vs Gold_THB (ทองบาทเดิม)", Fw["GLD_THB"], f0w["Gold_THB"], "> 0.98 (ใช้แทน ไม่ใช้คู่)")
    gx = (Fw["GLD_USD"] - f0w["SHV_USD"]) + (f0w["SHV_THB"] - f0w["RF_BOT"])
    add_cmp("GOLD_XS + FX = (GLD_USD − SHV_USD) + (SHV_THB − RF_BOT) vs Gold_THB − RF_BOT", gx, f0w["Gold_THB"] - f0w["RF_BOT"], "≈ เท่ากันเกือบพอดี")
    add_cmp("VNQ_USD vs REET_USD", Fw["VNQ_USD"], e0w["REET_USD"], "~0.85–0.95")
    add_cmp("VNQ_THB vs REET_THB", Fw["VNQ_THB"], e0w["REET_THB"], "~0.85–0.95")
    add_cmp("VNQI_USD vs REET_USD", Fw["VNQI_USD"], e0w["REET_USD"], "—")
    add_cmp("VNQ_USD vs MSCI_ACWI (THB) (REIT กับหุ้นโลก)", Fw["VNQ_USD"], f0w["MSCI_ACWI"], "REET กับ ACWI ~0.6–0.8")
    add_cmp("REIT1343T_THB vs MSCI_JAPAN (THB)", Fw["REIT1343T_THB"], f0w["MSCI_JAPAN"], "—")
    add_cmp("REIT1343T_THB vs REET_THB", Fw["REIT1343T_THB"], e0w["REET_THB"], "—")
    add_cmp("REITCLRSI_THB vs EWS_THB (MSCI Singapore)", Fw["REITCLRSI_THB"], e0w["EWS_THB"], "—")
    add_cmp("REITCLRSI_THB vs REET_THB", Fw["REITCLRSI_THB"], e0w["REET_THB"], "—")
    fxfac = f0w["SHV_THB"] - f0w["RF_BOT"]
    add_cmp("DTWEXBGS_ret (ดอลลาร์กว้าง) vs DXY (macro เดิม)", Fw["DTWEXBGS_ret"], f0w["DXY"], "—")
    add_cmp("DTWEXBGS_ret vs SHV_THB − RF_BOT (factor FX เดิม)", Fw["DTWEXBGS_ret"], fxfac, "—")
    add_cmp("DTWEXEMEGS_ret vs SHV_THB − RF_BOT", Fw["DTWEXEMEGS_ret"], fxfac, "—")
    add_cmp("DTWEXEMEGS_ret vs DTWEXBGS_ret", Fw["DTWEXEMEGS_ret"], Fw["DTWEXBGS_ret"], "—")
    add_cmp("DFII10_d vs US10Y_d (Δ ผลตอบแทนพันธบัตร 10Y)", Fw["DFII10_d"], f0w["US10Y_d"], "—")
    add_cmp("DFII10_d vs Gold (ทอง vs ดอกเบี้ยแท้จริง)", Fw["DFII10_d"], f0w["Gold"], "ทอง–ดอกเบี้ยแท้จริงแตกหลังปี 2022 (แหล่งรอง)")
    add_cmp("DFII10_d vs GLD_USD", Fw["DFII10_d"], Fw["GLD_USD"], "—")
    # KF vs JKP / AQR
    pairs = [("KF_DEV_HML", "JKP_DEV_value"), ("KF_DEV_WML", "JKP_DEV_momentum"), ("KF_DEV_SMB", "JKP_DEV_size"), ("KF_DEV_RMW", "JKP_DEV_profitability"), ("KF_DEV_CMA", "JKP_DEV_investment")]
    for a_, b_ in pairs:
        add_cmp(f"{a_} vs {b_} (KF vs JKP developed)", Fw[a_], Fw[b_], "สอดคล้อง (F-R006 ข้อ 9)")
    add_cmp("JKP_EM_value vs KF_DEV_HML", Fw["JKP_EM_value"], Fw["KF_DEV_HML"], "~0.2–0.4")
    add_cmp("JKP_EM_momentum vs KF_DEV_WML", Fw["JKP_EM_momentum"], Fw["KF_DEV_WML"], "—")
    add_cmp("JKP_EM_value vs JKP_DEV_value", Fw["JKP_EM_value"], Fw["JKP_DEV_value"], "—")
    add_cmp("JKP_EM_momentum vs JKP_DEV_momentum", Fw["JKP_EM_momentum"], Fw["JKP_DEV_momentum"], "—")
    add_cmp("AQR_HMLD_GLOBAL vs KF_DEV_HML", Fw["AQR_HMLD_GLOBAL"], Fw["KF_DEV_HML"], "ควรสูง (HML-Devil คือ HML แบบใช้ราคาปัจจุบัน)")
    add_cmp("AQR_QMJ_GLOBAL vs KF_DEV_RMW", Fw["AQR_QMJ_GLOBAL"], Fw["KF_DEV_RMW"], "—")
    add_cmp("AQR_QMJ_GLOBAL vs JKP_DEV_quality", Fw["AQR_QMJ_GLOBAL"], Fw["JKP_DEV_quality"], "—")
    add_cmp("AQR_BAB_GLOBAL vs JKP_DEV_low_risk", Fw["AQR_BAB_GLOBAL"], Fw["JKP_DEV_low_risk"], "—")
    add_cmp("KF_NA_HML vs KF_DEV_HML", Fw["KF_NA_HML"], Fw["KF_DEV_HML"], "—")
    add_cmp("KF_EU_HML vs KF_DEV_HML", Fw["KF_EU_HML"], Fw["KF_DEV_HML"], "—")
    add_cmp("KF_JP_HML vs KF_DEV_HML", Fw["KF_JP_HML"], Fw["KF_DEV_HML"], "—")
    P(md_table(pd.DataFrame(cmp_rows, columns=["คู่", "ความถี่", "n", "corr จริง", "ค่าคาด (F-R006)", ""]).iloc[:, :5]))
    P("\n- ค่าคาดใน F-R006 เป็น \"คาดการณ์\" ที่ยังไม่ได้ดูผลตอบแทน (ตามที่ระบุ) · ตารางนี้คือการวัดจริง · การเทียบ \"JKP EM market vs MSCI EM\" ทำไม่ได้ตามที่สั่ง: ไฟล์ JKP all-themes ไม่มีผลตอบแทนตลาด (มีแค่ 13 theme) → "
      "ใช้ KF Emerging Mkt-RF รายเดือนเทียบ MSCI_EM แทน (ข้อ 6)\n")

    # lead/lag
    P("### 4.1 diagnostic lead/lag 1 สัปดาห์ (F-R006 §6.3 ข้อ 9 · ตรวจว่าการจัดสัปดาห์คลาดไหม)\n")
    ll = []
    for lab, x, y in (("KF_DEV_MKTRF+RF → ACWI_ETF_USD", kfm, f0w["ACWI_ETF_USD"]), ("KF_JP_MKTRF → MSCI_JAPAN (THB)", Fw["KF_JP_MKTRF"], f0w["MSCI_JAPAN"]),
                      ("KF_EU_MKTRF → MSCI_EUROPE (THB)", Fw["KF_EU_MKTRF"], f0w["MSCI_EUROPE"]), ("REIT1343T_THB → EWJ_THB (ปิด NY)", Fw["REIT1343T_THB"], e0w["EWJ_THB"]),
                      ("REITCLRSI_THB → EWS_THB (ปิด NY)", Fw["REITCLRSI_THB"], e0w["EWS_THB"]), ("GLD_USD → Gold (GC=F)", Fw["GLD_USD"], f0w["Gold"])):
        row = [lab]
        for k in (-1, 0, 1):
            xs = x[mw]
            ys = y.shift(-k)[mw] if k else y[mw]
            row.append(fmt(float(pd.concat([xs, ys], axis=1).dropna().corr().iloc[0, 1])))
        ll.append(row)
    P(md_table(pd.DataFrame(ll, columns=["x → y", "corr(x_t, y_t−1)", "corr(x_t, y_t)", "corr(x_t, y_t+1)"])))
    P("\n- อ่าน: ถ้า corr ที่ y_t+1 ไม่ใกล้ศูนย์ แปลว่า x ปิดก่อน y (ตลาดเอเชีย/ยุโรปปิดก่อน NY) → ต้องใช้ Dimson lag ตาม BRIEF (ไม่แก้ข้อมูล · ใช้ lag ใน regression)\n")

    # ------------------------------------------------------------------ 5 KF รายวัน → รายเดือน เทียบไฟล์รายเดือน
    P("## 5. KF รายวัน → รายเดือน เทียบไฟล์ KF รายเดือนทางการ (Developed · 2021-01 → 2025-12)\n")
    kr, kr_ok, kr_warn = [], [], []
    for c in ("MKTRF", "SMB", "HML", "RMW", "CMA", "WML", "RF"):
        mine = Fm["KF_RF" if c == "RF" else f"KF_DEV_{c}"]
        off = Fm["KFM_DEV_" + c] if c != "RF" else src["kf_m"]["KF_DEV"]["RF"].reindex(Fm.index)
        j = pd.concat([mine, off], axis=1, keys=["m", "o"]).dropna()
        j = j[main_mask(j.index)]
        d = (j["m"] - j["o"])
        cr = float(j["m"].corr(j["o"]))
        if c == "RF":
            verdict = "ผ่าน (ดู RF ด้านล่าง)" if d.abs().max() <= 0.002 else "เตือน"
        elif cr >= 0.99:
            verdict = "ผ่าน"
            kr_ok.append(c)
        else:
            verdict = "เตือน"
            kr_warn.append(c)
        if c == "WML":
            wml_worst = ", ".join(f"{x:%Y-%m}" for x in d.abs().sort_values(ascending=False).index[:3])
        kr.append([c, len(j), f"{cr:.6f}", f"{d.abs().max():.5f}", f"{d.abs().mean():.5f}", f"{d.mean():+.5f}", verdict])
    P(md_table(pd.DataFrame(kr, columns=["factor", "n เดือน", "corr", "max|ต่าง|", "mean|ต่าง|", "mean ต่าง (ทบรายวัน − ทางการ)", "ผล (เกณฑ์ corr ≥ 0.99)"])))
    P("\n- ไฟล์ทางการปัดทศนิยม 2 ตำแหน่ง (% → ±0.00005 ต่อเดือนในหน่วยสัดส่วน) · RF รายวันของ KF ปัดที่ 0.01% ต่อวัน (ค่า RF เกือบคงที่ → corr ไม่เหมาะเป็นเกณฑ์ ใช้ผลต่างสัมบูรณ์แทน: สูงสุด ≤ 0.002 = 0.2%)")
    P(f"- **Mkt-RF / " + " / ".join(c for c in kr_ok if c != 'MKTRF') + f" ผ่าน** (corr ≥ 0.99) → การทบต้นรายวันเป็นรายเดือนใช้ได้ · **{'WML' if 'WML' in kr_warn else '-'} = เตือน**")
    wm_full = None
    dd = src["kf"]["KF_DEV"]["WML"].loc["2020-12-01":"2026-07-31"]
    mm_ = (1 + dd).groupby(dd.index.to_period("M")).prod() - 1
    mm_.index = mm_.index.to_timestamp("M")
    jj = pd.concat([mm_, src["kf_m"]["KF_DEV"]["WML"]], axis=1, keys=["a", "b"], sort=True).dropna()
    jj = jj.loc["2021-01-01":"2026-07-31"]
    wm_full = float(jj["a"].corr(jj["b"]))
    r_d, n_d = cc(Fm["KF_DEV_WML"], Fm["JKP_DEV_momentum"], True)
    r_o, n_o = cc(Fm["KFM_DEV_WML"], Fm["JKP_DEV_momentum"], True)
    P(f"- WML: corr ทบรายวัน vs ทางการ = {kr[5][2]} (ช่วงหลัก 60 เดือน) / {wm_full:.4f} (2021-01 → 2026-07 รวม {len(jj)} เดือน) · max|ต่าง| {kr[5][3]} (≈ {float(kr[5][3]) * 100:.1f} จุด %) ใหญ่สุดที่เดือน {wml_worst} · "
      "**สาเหตุไม่ทราบ — ไม่ใช่ข้อผิดพลาดของการแปลงเรา** เพราะ Mkt-RF / SMB / HML / RMW / CMA ใช้ขั้นตอนเดียวกันและตรงกัน ≥ 0.997 · เป็นความต่างระหว่างไฟล์ KF รายวันกับรายเดือนของ Mom เอง (ตั้งสมมติฐาน: การทบต้น long–short รายวัน ≠ พอร์ตที่ปรับสมดุลรายเดือน · ยังไม่ทดสอบ)")
    P(f"- ตัวชี้ทางว่าไฟล์ไหนใกล้ factor momentum อื่น: corr รายเดือนกับ JKP_DEV_momentum — WML ทบรายวัน **{fmt(r_d)}** · WML รายเดือนทางการ **{fmt(r_o)}** (n={n_d}) → "
      "ข้อเสนอ: ชั้นตรวจซ้ำรายเดือนใช้ `KFM_DEV_WML` (ไฟล์ทางการ · มีใน parquet รายเดือนเป็นคอลัมน์ monthly-native) เทียบกับ `KF_DEV_WML` ทบรายวัน · weekly ใช้ `KF_DEV_WML` เพราะ KF ไม่มี WML รายสัปดาห์")
    P("- ผลรวม: **ผ่านเฉพาะ 5 factor (Mkt-RF · SMB · HML · RMW · CMA) · WML เตือน** — ไม่ถือเป็น \"ไม่ผ่าน\" ที่ต้องหยุด แต่ต้องติดป้ายในทุกรายงานที่ใช้ WML รายเดือน\n")

    # ------------------------------------------------------------------ 6 JKP EM vs KF EM รายเดือน
    P("## 6. JKP EM vs KF Emerging (รายเดือน · 2021-01 → 2025-12) และตลาด EM\n")
    em = src["kf_m"]["KF_EM"]
    jr = []
    for kf_c, jk_c in (("HML", "value"), ("WML", "momentum"), ("SMB", "size"), ("RMW", "profitability"), ("CMA", "investment")):
        r_, n_ = cc(Fm[f"KFM_EM_{kf_c}"], Fm[f"JKP_EM_{jk_c}"], True)
        r2, n2 = cc(Fm[f"KF_DEV_{kf_c}"], Fm[f"JKP_EM_{jk_c}"], True)
        jr.append([f"KFM_EM_{kf_c} vs JKP_EM_{jk_c}", n_, fmt(r_), fmt(r2)])
    P(md_table(pd.DataFrame(jr, columns=["คู่ (รายเดือน)", "n", "corr กับ KF Emerging", "corr กับ KF Developed (เทียบ)"])))
    r_, n_ = cc(Fm["KFM_EM_MKTRF"], f0m["MSCI_EM"], True)
    r2, n2 = cc(Fm["KF_DEV_MKTRF"], f0m["MSCI_WORLD"], True)
    P(f"\n- KFM_EM_MKTRF (USD ตลาด − rf) vs MSCI_EM (THB · รายเดือน): corr **{fmt(r_)}** (n={n_}) · KF_DEV_MKTRF vs MSCI_WORLD รายเดือน: {fmt(r2)} (n={n2})")
    P("- ไฟล์ JKP all-themes (capped VW) มีเฉพาะ 13 theme ไม่มีผลตอบแทนตลาด → เทียบ \"JKP EM market vs MSCI EM\" ตรงๆ ไม่ได้ · ใช้ KF EM Mkt-RF แทน · JKP EM ใช้ได้เฉพาะ style long–short")
    P("- เครื่องหมาย factor (long–short) ของ JKP กับ KF ไม่ได้เทียบกันตรงตัว (JKP กำหนด theme ต่างจาก KF — เช่น JKP 'value' ผสมหลายตัวชี้วัด · 'investment' = low-minus-high) · corr ต่ำ/ติดลบไม่ใช่ข้อผิดพลาดของข้อมูลโดยตัวมันเอง\n")

    # ------------------------------------------------------------------ 7 factor ซ้ำกับของเดิม
    P("## 7. ความซ้ำซ้อนกับ factor เดิม (corr สูงสุดต่อคอลัมน์ · weekly ช่วงหลัก · ไม่นับ `_lvl`)\n")
    oldr = [c for c in old_w.columns if not c.endswith("_lvl")]
    rows = []
    for c in ret_cols:
        best, bn = 0.0, ""
        x = Fw.loc[mw, c]
        for o in oldr:
            y = old_w.loc[mw, o]
            r_ = x.corr(y)
            if not np.isnan(r_) and abs(r_) > abs(best):
                best, bn = r_, o
        rows.append([c, bn, f"{best:+.3f}", "ซ้ำ (|corr| ≥ 0.9)" if abs(best) >= 0.9 else ("สูง (≥ 0.7)" if abs(best) >= 0.7 else "")])
    tdf = pd.DataFrame(rows, columns=["factor ใหม่", "factor เดิมที่ corr สูงสุด", "corr", "หมายเหตุ"])
    P(f"- จาก {len(ret_cols)} คอลัมน์: |corr| ≥ 0.9 = **{int((tdf['หมายเหตุ'].str.startswith('ซ้ำ')).sum())}** · 0.7–0.9 = **{int((tdf['หมายเหตุ'].str.startswith('สูง')).sum())}** (ตารางแสดงเฉพาะแถวที่ ≥ 0.7 + factor สำคัญ)\n")
    keep = tdf[(tdf["หมายเหตุ"] != "") | tdf["factor ใหม่"].str.match(r"^(KF_DEV_(SMB|HML|RMW|CMA|WML)|JKP_EM_(value|momentum)|GLD_|VNQ_|VNQI_|DTWEX|DFII10_d|AQR_.*_GLOBAL)")]
    P(md_table(keep))
    P("\n- ข้อสังเกต: KF_*_MKTRF กับ ETF/ดัชนีตลาดซ้ำโดยธรรมชาติ (ไม่ใช้เป็น factor · F-R006) · GLD กับ Gold (GC=F) ซ้ำกัน (ใช้แทน ไม่ใช้คู่)\n")
    cn = Fw.loc[mw, ret_cols].corr()
    hp = []
    for i, a_ in enumerate(ret_cols):
        for b_ in ret_cols[i + 1:]:
            v = cn.at[a_, b_]
            if abs(v) >= 0.9:
                hp.append((a_, b_, v))
    P(f"### 7.1 คู่ในชุดใหม่ที่ |corr| ≥ 0.9 ({len(hp)} คู่)\n")
    if hp:
        P(md_table(pd.DataFrame([[a_, b_, f"{v:+.3f}"] for a_, b_, v in sorted(hp, key=lambda t: -abs(t[2]))[:60]], columns=["a", "b", "corr"])))
        if len(hp) > 60:
            P(f"\n(แสดง 60 คู่แรกจาก {len(hp)})")
    P("")

    # ------------------------------------------------------------------ 8 เกี่ยวกับแหล่ง
    P("## 8. รายละเอียดแหล่ง\n")
    P("### 8.1 Ken French\n")
    kfr = []
    for pre in KF_FILES:
        d = src["kf"][pre]
        w = d.loc[CUM_START:"2026-07-31"]
        kfr.append([pre, f"{d.index.min():%Y-%m-%d}", f"{d.index.max():%Y-%m-%d}", len(d), int(w.isna().sum().sum()),
                    len(pd.bdate_range(w.index.min(), w.index.max()).difference(w.index)), int(((w == 0).sum().sum()))])
    P(md_table(pd.DataFrame(kfr, columns=["ภูมิภาค", "raw_first", "raw_last", "แถว", "NaN (-99.99) 2020-10→2026-07", "วันทำการที่ขาด", "ค่า = 0 ทั้งหมดรวม"])))
    P("- ไฟล์ KF รายวันมีทุกวันจันทร์–ศุกร์ (วันหยุดเป็นผลตอบแทน 0 ของ factor ไม่ใช่แถวขาด) → ศุกร์ทุกวันมีแถว · ไม่มี -99.99 ในช่วงที่ใช้ · header ของไฟล์ระบุ \"202608 Bloomberg database\" (อ่านตามที่ไฟล์ระบุ ไม่ได้ตรวจกับต้นฉบับ)")
    P("- KF RF ของ 4 ภูมิภาคเท่ากันทุกแถว (ตรวจแล้ว) → เก็บ `KF_RF` ตัวเดียว · `KFM_DEV_*` / `KFM_EM_*` = ไฟล์รายเดือนทางการ 6 ตัวต่อภูมิภาค (Mkt-RF SMB HML RMW CMA WML) เฉพาะ parquet รายเดือน\n")
    P("### 8.2 JKP\n")
    jr2 = []
    for pre, d in src["jkp"].items():
        w = d.loc[CUM_START:]
        cal = w.index[w.notna().any(axis=1)]
        miss = {c: int(len(cal.difference(w[c].dropna().index))) for c in d.columns}
        jr2.append([pre, d.shape[1], f"{d.index.min():%Y-%m-%d}", f"{d.index.max():%Y-%m-%d}", len(cal), max(miss.values()),
                    ", ".join(d.columns)])
    P(md_table(pd.DataFrame(jr2, columns=["ชุด", "theme", "raw_first", "raw_last", "วัน (2020-10→)", "วันที่ขาดต่อ theme (สูงสุด)", "theme ทั้งหมด"])))
    P("- ใช้ capped value-weighted ตามที่ดาวน์โหลด · ผลตอบแทนเป็นสัดส่วน (ไม่ใช่ %) · ทุก theme ครบ 13 ตัว · ตั้งชื่อ `JKP_EM_<theme>` / `JKP_DEV_<theme>` · เก็บ**ทุก theme** (ตามคำสั่ง) — pool ที่ใช้ในการแข่งให้ spec ล็อกล่วงหน้า (F-R006: EM value / momentum)\n")
    P("### 8.3 AQR (robustness เท่านั้น · BRIEF 113)\n")
    am = ctx["aqr_meta"]
    P(md_table(pd.DataFrame([[k, v["sheet"], v["data_rows"], ", ".join(AQR_SERIES), v["n_header_cols"]] for k, v in am.items()],
                            columns=["ชุด", "sheet", "แถวข้อมูล", "series ที่เลือก", "จำนวน series ในไฟล์"])))
    P(f"- **เลือก 3 series ต่อ factor** = USA · Global · Global Ex USA (ตรงคำสั่งงาน: US + Global / Global ex US) → 9 คอลัมน์ (`AQR_QMJ_*` · `AQR_BAB_*` · `AQR_HMLD_*`) · F-R006 ไม่ระบุ series ระดับภูมิภาค (Europe / North America / Pacific / รายประเทศ) → **ไม่เลือก** (มีในไฟล์ดิบ: " + ", ".join(list(am.values())[0]["all_series_in_file"]) + ")")
    P("- sheet อื่นในไฟล์ (MKT / SMB / HML FF / UMD / RF) ไม่ได้นำมาใช้ · ไม่พบข้อความสั่งการในไฟล์ที่อ่าน (อ่านเฉพาะแถวข้อมูลที่รูปแบบวันที่ MM/DD/YYYY และ header) · Terms of Use: ไม่มีหน้ายอมรับเงื่อนไขตอนดาวน์โหลด (NOTES.md) — ใช้ภายในงานวิจัยเท่านั้น\n")

    # ------------------------------------------------------------------ 9 AUM_fam / U_E / U_O
    P("## 9. AUM_fam · อายุ family · U_E / U_O (BRIEF 109)\n")
    P("**นิยาม (ตาม M012-QF · วันตายตัว):** AUM_fam = ผลรวม AUM ของ**ทุก class** ใน family (family map เดิมของทีม `build_l0.family_of(fixed=True)` + `share_class_groups.csv`) "
      f"โดย AUM ต่อ class = ค่าบวกล่าสุดที่ NAVDate ≤ {AUM_ASOF:%Y-%m-%d} และไม่เก่ากว่า {AUM_STALE_DAYS} วัน (NAVDate ≥ 2023-10-02) · ไม่มี → 0 (= ไม่ผ่าน) · "
      f"ผ่าน AUM = AUM_fam ≥ {AUM_MIN:,.0f} บาท · อายุ family ณ {AGE_ASOF:%Y-%m-%d} = min(Registration_date ที่ ≤ วันนั้น, NAV แรก) ของทุก class · ผ่านอายุ = ≥ {AGE_MIN_DAYS} วัน · "
      "U = policy E / O · ตัด F · เป็นตัวแทน family ที่ `included` ใน universe เดิม (panel L0) · ผ่านทั้งสองเกณฑ์\n")
    P(f"- nav_history_db.csv: อ่านทั้งไฟล์แบบ chunk ({nstats['rows_total']:,} แถว · แถว NAV>0 ใช้ได้ {nstats['rows_valid_nav']:,}) · แถวในหน้าต่าง AUM (2023-10-02 → 2023-12-31) {nstats['window_rows_before_dedupe']:,} → หลัง dedupe (UpdateTime ล่าสุด) {nstats['window_rows_after_dedupe']:,} · **แถวที่ใช้ทั้งหมดมี NAVDate ≤ 2023-12-31** (assert · ค่าสูงสุดที่ใช้ {pd.Timestamp(cl['aum_date'].max()):%Y-%m-%d})")
    P(f"- class ในไฟล์ NAV + FundProfile = {len(cl):,} · family = {cl['family'].nunique():,} · class ที่มี AUM บวกในหน้าต่าง = {int((cl['aum'] > 0).sum()):,} · family ใน universe (filter9 = 715 class) = {len(aum)}")
    inc = aum[aum["included"]]
    t = []
    for pol in ("E", "F", "O"):
        x = inc[inc["policy"] == pol]
        t.append([pol, len(x), int(x["pass_aum"].sum()), int(x["pass_age"].sum()), int(x["pass_both"].sum()), int((x["aum_fam_2023"] == 0).sum())])
    P("\nจำนวน family ใน panel L0 (included) ต่อ policy:\n")
    P(md_table(pd.DataFrame(t, columns=["policy", "ใน panel L0", "ผ่าน AUM", "ผ่านอายุ", "ผ่านทั้งสอง", "AUM_fam = 0"])))
    ue = int(((aum["policy"] == "E") & aum["in_U"]).sum())
    uo = int(((aum["policy"] == "O") & aum["in_U"]).sum())
    ugold = int(((aum["policy"] == "O") & aum["in_U"] & (aum["o_kind"] == "gold")).sum())
    ureit = int(((aum["policy"] == "O") & aum["in_U"] & (aum["o_kind"] == "reit")).sum())
    uother = uo - ugold - ureit
    assert not (aum["in_U"] & (aum["policy"] == "F")).any(), "มีกอง F ใน U"
    P(f"\n### 9.1 ผลลัพธ์: **U_E = {ue} · U_O = {uo}** (คาดจากแผน ~{EXPECT_UE} / ~{EXPECT_UO})\n")
    P(f"- U_O แยกตามชื่อกอง (กฎ `is_gold` แบบ lib/p2.py: EN มี 'gold' ไม่รวม 'golden' หรือ TH มี 'ทองคำ' · ที่เหลือจัดเป็น REIT/อสังหา ถ้าชื่อมี REIT / PROP / REAL ESTATE / อสังหา): **ทอง {ugold} · REIT/อสังหา {ureit} · อื่น {uother}**")
    P("- ไม่มีกอง F ใน U (assert ผ่าน) · กอง F ใน panel 49 ถูกตัดออกทั้งหมด")
    P("- **ทำไมต่างจากค่าคาด** (วิเคราะห์เอง — ตัวเลขคำนวณรอบนี้):")
    # sensitivity
    iu = inc[inc["policy"].isin(["E", "O"])]
    aw = pd.read_parquet(os.path.join(HERE, "aum_weekly.parquet"))
    aw29 = aw[aw["date"] == pd.Timestamp("2023-12-29")].set_index("FundCode")["aum"]
    rep_aum = iu["FundCode"].map(aw29)
    sens = []
    for lab, aumv, age_th in (("นิยามรอบนี้ (AUM_fam รวมทุก class · อายุ 730 วัน)", iu["aum_fam_2023"], 730),
                              ("อายุ 1,095 วัน (3 ปี · ค่าเดิมก่อนผู้ใช้เปลี่ยน)", iu["aum_fam_2023"], 1095),
                              ("AUM เฉพาะ class ตัวแทน (aum_weekly.parquet · 2023-12-29 · อายุ 730)", rep_aum, 730),
                              ("AUM เฉพาะ class ตัวแทน · อายุ 1,095", rep_aum, 1095),
                              ("AUM_fam ≥ 50 ล้าน · อายุ 730", iu["aum_fam_2023"], 730), ("AUM_fam ≥ 200 ล้าน · อายุ 730", iu["aum_fam_2023"], 730)):
        thr = 50e6 if "50 ล้าน" in lab else (200e6 if "200 ล้าน" in lab else AUM_MIN)
        m = (aumv >= thr) & (iu["age_days_2025"] >= age_th)
        sens.append([lab, int(m[iu["policy"] == "E"].sum()), int(m[iu["policy"] == "O"].sum())])
    P("\n" + md_table(pd.DataFrame(sens, columns=["นิยาม", "U_E", "U_O"])))
    sd = {r[0]: (r[1], r[2]) for r in sens}
    k_all, k_3y, k_rep, k_rep3 = (sd[sens[0][0]], sd[sens[1][0]], sd[sens[2][0]], sd[sens[3][0]])
    P(f"\n- สรุป: ค่าคาด ~{EXPECT_UE} / ~{EXPECT_UO} อยู่ระหว่างการใช้ AUM เฉพาะ class ตัวแทน ({k_rep[0]} / {k_rep[1]}) กับการรวมทุก class ({k_all[0]} / {k_all[1]}) · "
      f"อายุ 3 ปี + รวมทุก class = {k_3y[0]} / {k_3y[1]} (ใกล้ค่าคาดที่สุดในสูตรที่รวมทุก class) — แผนระบุเป็นค่าประมาณ ไม่ใช่ผลจากสคริปต์ · "
      "ส่วนต่างหลักของรอบนี้มาจาก **การรวม AUM ทุก class ใน family** (กองที่ class ตัวแทนไม่มี AUM แต่ class อื่นมี เช่น ASP-INDIA · K-INDIA · LHEUROPE) ซึ่งเป็นนิยามที่ BRIEF 109 กำหนด\n")

    # O รายกอง
    P("### 9.2 กอง O ทั้ง 27 family ใน panel (ผ่าน/ไม่ผ่าน · ล้านบาท)\n")
    o = aum[(aum["policy"] == "O") & aum["included"]].copy()
    o["aum_M"] = (o["aum_fam_2023"] / 1e6).round(1)
    o["last_valid_week"] = pd.to_datetime(o["last_valid_week"]).dt.strftime("%Y-%m-%d")
    o["age_days_2025"] = o["age_days_2025"].astype(int)
    o["ผล"] = np.where(o["in_U"], "อยู่ใน U_O", np.where(~o["pass_aum"] & ~o["pass_age"], "ตก AUM+อายุ", np.where(~o["pass_aum"], "ตก AUM", "ตก อายุ")))
    P(md_table(o[["family", "FundCode", "o_kind", "n_classes", "aum_M", "age_days_2025", "ผล", "last_valid_week", "name_en"]].rename(
        columns={"o_kind": "ชนิด", "n_classes": "class", "aum_M": "AUM_fam (ล้านบาท)", "age_days_2025": "อายุ (วัน)", "last_valid_week": "สัปดาห์สุดท้ายใน panel"})))
    P("")
    twins = o[o["family"].isin(["KT-GOLD", "KT-GOLDUH", "UOBSG", "UOBSG-N"])][["family", "ผล"]]
    P("- **คู่ twin ของ F-R006 (hedge / unhedge)** — " + "; ".join(f"{r.family}: {r.ผล}" for r in twins.itertuples()) + " → ใน U_O เหลือเฉพาะ UOBSG-N กับ KT-GOLD (ฝั่ง unhedged ของ KT ไม่ผ่านอายุ · ฝั่ง hedged ของ UOBSG ไม่ผ่าน AUM) → ตรวจ twin test ในกลไก FX ของทองทำไม่ได้เต็มรูปแบบ")
    ig = o.set_index("family")
    P(f"- `I-GOLD` กับ `IGOLD-G` = **กองเดียวกันที่เปลี่ยนรหัส** (ชื่อ EN เดียวกัน · `Fund Class` ใน FundProfile = I-GOLD ทั้งคู่ · AUM_fam 138 / 141 ล้านบาท · "
      f"panel: I-GOLD จบ {ig.at['I-GOLD', 'last_valid_week']} · IGOLD-G เริ่ม 2023-12-08 → ต่อกันพอดี ไม่ซ้อนกัน) แต่ family map ของทีมแยกเป็น 2 family และ `Previous Fund Code` ว่าง → นับเป็น 2 ใน U_O ทั้งที่เป็นกองจริง 1 กอง "
      "(ทั้งคู่ไม่ครบ train/test ตามข้อ 9.4) · ไม่แก้ family map / panel ของทีม → ขอให้ตัดสินใจ (ข้อ 12.3)\n")

    # E: ไม่ผ่าน เพราะอะไร
    P("### 9.3 กอง E (357 family) — สาเหตุที่ไม่ผ่าน\n")
    e = aum[(aum["policy"] == "E") & aum["included"]].copy()
    cat = np.select([e["in_U"], (~e["pass_aum"]) & (~e["pass_age"]), ~e["pass_aum"], ~e["pass_age"]],
                    ["อยู่ใน U_E", "ตก AUM + อายุ", "ตก AUM อย่างเดียว", "ตก อายุอย่างเดียว"], "?")
    P(md_table(pd.Series(cat).value_counts().rename_axis("สถานะ").reset_index(name="family")))
    z0 = e[(e["aum_fam_2023"] == 0)]
    fn = z0["FundCode"].map(cl.set_index("code")["first_nav"])
    n_new = int((fn > AUM_ASOF).sum())
    P(f"\n- AUM_fam = 0 ทั้งหมด {len(z0)} family: NAV แรกหลัง 2023-12-31 (กองเปิดใหม่ / เปลี่ยนรหัส) **{n_new}** · NAV แรก ≤ 2023-12-31 แต่ไม่มี AUM บวกใน 90 วัน **{len(z0) - n_new}** "
      "(" + ", ".join(z0.loc[~(fn > AUM_ASOF), "family"].tolist()) + ")")
    # ES rename
    profx = ctx["prof_full"].copy()
    profx["code"] = profx[config.FUND_CODE_COL].astype(str).str.strip()
    prev = profx.drop_duplicates("code").set_index("code")["Previous Fund Code"].fillna("").astype(str).str.strip()
    cc_ = cl.set_index("code")
    rn = []
    for r in aum[aum["included"] & aum["policy"].isin(["E", "O"]) & (aum["aum_fam_2023"] == 0)].itertuples():
        pv = prev.get(r.FundCode, "")
        if pv and pv in cc_.index and pd.notna(cc_.at[pv, "first_nav"]) and cc_.at[pv, "aum"] > 0 and cc_.at[pv, "first_nav"] <= pd.Timestamp("2021-12-31") and pv != r.FundCode:
            rn.append((r.family, r.policy, pv, cc_.at[pv, "aum"] / 1e6))
    rne = [x for x in rn if x[1] == "E"]
    rno = [x for x in rn if x[1] == "O"]
    P(f"- **พบการเปลี่ยนรหัสกอง (Eastspring ES-* เดิม TMB… / T-…)**: {len(rn)} family (E {len(rne)} · O {len(rno)}) ที่ใน panel มี NAV เริ่ม 2024-06 (รหัสใหม่) แต่ `Previous Fund Code` ใน FundProfile ชี้ไปรหัสเดิมที่มี NAV + AUM ตั้งแต่ 2020-12 ในไฟล์ NAV "
      "(AUM รหัสเดิมรวม {:,.0f} ล้านบาท · O: {}) — รหัสเดิมไม่อยู่ใน 9 เกณฑ์ (ไม่อยู่ใน panel) ดังนั้น **ช่วง 2021 → 2024-06 ของกองเหล่านี้หายจาก panel L0** และ AUM_fam ณ 2023-12-31 ของรหัสใหม่ = 0 (ไม่ผ่านตามกติกา \"ไม่มี → 0\")".format(
          sum(x[3] for x in rn), ", ".join(x[0] for x in rno) or "-"))
    P("  - ผลต่อ U: ตามกติกาข้อ 109 ตรงตัว กองเหล่านี้**ไม่อยู่ใน U** · ในทางปฏิบัติก็ใช้ train 2021–2023 ไม่ได้อยู่แล้ว (panel เริ่ม 2024-06) · ถ้าผู้ใช้อยากสะสม AUM / อายุข้ามรหัส (chain `Previous Fund Code`) ต้องแก้ L0 (ต่อ NAV รหัสเดิม) → ดู \"ต้องให้ผู้ใช้ตัดสินใจ\" ข้อ 1")
    P(f"  - รายชื่อ E ({len(rne)}): " + ", ".join(f"{x[0]}←{x[2]}" for x in rne))
    P("  - กลับด้าน: รหัสเดิมบางตัวที่ **ยังอยู่ใน panel** (เช่น TMB-ES-GCG · TMB-ES-GINNO · TMBGINFRA ซึ่ง NAV จบ 2023-11-28) ผ่านเกณฑ์และอยู่ใน U_E แต่ panel จบ 2023-12-08 → ไม่มีข้อมูลช่วง test 2024–2025 (ดูข้อ 9.4)")
    # borderline
    P("\n### 9.4 ความไวของเกณฑ์ + ความใช้ได้จริงของ U ในการประเมิน\n")
    ee = aum[(aum["policy"].isin(["E", "O"])) & aum["included"]]
    bl = []
    for pol in ("E", "O"):
        x = ee[ee["policy"] == pol]
        bl.append([pol, int(((x["aum_fam_2023"] >= 80e6) & (x["aum_fam_2023"] < 100e6)).sum()), int(((x["aum_fam_2023"] >= 100e6) & (x["aum_fam_2023"] < 125e6)).sum()),
                   int(((x["age_days_2025"] >= 700) & (x["age_days_2025"] < 730)).sum()), int(((x["age_days_2025"] >= 730) & (x["age_days_2025"] < 760)).sum())])
    P(md_table(pd.DataFrame(bl, columns=["policy", "AUM 80–100M (ตกนิดเดียว)", "AUM 100–125M (ผ่านนิดเดียว)", "อายุ 700–729 วัน (ตกนิดเดียว)", "อายุ 730–759 วัน (ผ่านนิดเดียว)"])))
    pw = pd.read_parquet(os.path.join(HERE, "panel_weekly.parquet"))
    pwm = pw[(pw["date"] > L0.MAIN_START) & (pw["date"] <= L0.MAIN_END)].dropna(subset=["ret"])
    wtr = pwm[pwm["date"] <= TRAIN_END].groupby("FundCode").size()
    wte = pwm[pwm["date"] > TRAIN_END].groupby("FundCode").size()
    uu = aum[aum["in_U"]].copy()
    uu["n_train"] = uu["FundCode"].map(wtr).fillna(0).astype(int)
    uu["n_test"] = uu["FundCode"].map(wte).fillna(0).astype(int)
    ub = []
    for pol in ("E", "O"):
        x = uu[uu["policy"] == pol]
        ub.append([pol, len(x), int((x["n_train"] >= 104).sum()), int((x["n_test"] >= 52).sum()), int(((x["n_train"] >= 104) & (x["n_test"] >= 52)).sum()),
                   int((x["n_test"] == 0).sum()), int((x["n_train"] == 0).sum())])
    P("\nจำนวนกองใน U ที่มีผลตอบแทนใน panel L0 พอสำหรับการประเมิน (ตามข้อ 10: ≥ 104 สัปดาห์ใน train และ ≥ 52 ใน test — ใช้เป็นเกณฑ์ EVAL ของระยะ 1):\n")
    P(md_table(pd.DataFrame(ub, columns=["policy", "U", "train ≥ 104", "test ≥ 52", "ทั้งสอง (EVAL)", "ไม่มีข้อมูล test เลย", "ไม่มีข้อมูล train เลย"])))
    nt = uu[(uu["n_test"] == 0) | (uu["n_train"] == 0)][["family", "policy", "n_train", "n_test", "last_valid_week"]].copy()
    nt["last_valid_week"] = pd.to_datetime(nt["last_valid_week"]).dt.strftime("%Y-%m-%d")
    P("\nกองใน U ที่ไม่มีผลตอบแทนใน test เลย หรือใน train เลย (ติดป้าย · ไม่ตัดออกจาก `aum_fam.parquet`):\n")
    P(md_table(nt.rename(columns={"n_train": "สัปดาห์ train", "n_test": "สัปดาห์ test", "last_valid_week": "สัปดาห์สุดท้ายใน panel"})))
    # family ที่ Fund Class ร่วมกัน (กองเดียวกันหลายรหัส · ตัวอย่าง: I-GOLD / IGOLD-G · MGAG / MGAPVD)
    pf = ctx["prof_full"].copy()
    pf["code"] = pf[config.FUND_CODE_COL].astype(str).str.strip()
    fcm = pf.drop_duplicates("code").set_index("code")["Fund Class"].fillna("").astype(str).str.strip()
    uu2 = uu.copy()
    uu2["fund_class"] = uu2["FundCode"].map(fcm)
    gg = uu2[uu2["fund_class"] != ""].groupby("fund_class")["FundCode"].agg(list)
    gg = gg[gg.map(len) > 1]
    P(f"\n- family ใน U ที่ `Fund Class` (FundProfile) ซ้ำกัน = กองเดียวกันหลายรหัส (family map ของทีมแยกเป็นคนละ family): **{len(gg)} กลุ่ม** รวมเกิน {int(sum(len(v) - 1 for v in gg))} family — "
      + "; ".join(f"{k}: {', '.join(v)}" for k, v in gg.items()) + " · ใช้ `samples.dedup_keep` ตอนสร้าง PCA (ข้อ 109) · ตอนรายงาน O รายกอง ต้องระวังนับซ้ำ")
    P("\n- ติดป้าย **look-ahead**: เกณฑ์อายุวัดที่ 2025-12-31 (ใช้ข้อมูลหลังช่วง train) · **survivorship**: เกณฑ์อายุ + n_weeks ≥ 52 ใน panel L0 ตัดกองที่เลิก/ควบรวมก่อนถึงเกณฑ์ และ U ยังมีกองที่เลิกกลางช่วง (TMB-ES-* จบ 2023-12) ที่ไม่ได้ถูกตัด · "
      "PCA ใช้ `samples.dedup_keep` ตอนสร้าง factor เท่านั้น (ข้อ 109) · ไฟล์ `aum_fam.parquet` ไม่ได้ dedupe\n")

    # ------------------------------------------------------------------ 10 ไฟล์ L0 เดิม
    P("## 10. ไฟล์ L0 เดิมไม่ถูกแก้\n")
    chk = check_untouched()
    bad = [c for c in chk if not c["match"]]
    P(f"- เทียบ sha256 ของไฟล์ output ใน `manifest.json` + `manifest_ext.json` ({len(chk)} ไฟล์ รวม panel_weekly / panel_monthly / factors_* / universe) กับไฟล์จริง: **{'ตรงทุกไฟล์ (ผ่าน)' if not bad else 'ไม่ตรง ' + str([b['file'] for b in bad]) + ' (ไม่ผ่าน)'}**\n")

    # ------------------------------------------------------------------ 11 ข้อจำกัด + ตัดสินใจ
    P("## 11. ข้อจำกัด\n")
    for t_ in (
        "factor long–short (KF / JKP / AQR) เป็น USD และ**ลงทุนไม่ได้** · ไม่แปลงเป็นบาท (BRIEF 110) · การทบต้นรายวันเป็นสัปดาห์ = ค่าประมาณของพอร์ตที่ปรับสมดุลรายวัน · ต้องใช้ Dimson lag 1 (ตลาดปิดต่างเวลา · ดูข้อ 4.1)",
        "KF ไม่มี Emerging รายวัน → EM มี style รายสัปดาห์จาก JKP EM เท่านั้น (จบ 2025-12-31) · `KFM_*` (KF รายเดือนทางการ Developed + Emerging) อยู่ใน parquet รายเดือนเท่านั้น",
        "JKP จบ 2025-12-31: สัปดาห์สิ้นสุด 2026-01-02 เป็นต้นไป = NaN · ปี 2026 ดูประกอบด้วย JKP ไม่ได้ · ไม่มีผลตอบแทนตลาดในไฟล์ JKP · ชื่อ theme ยืนยันจากไฟล์ (13 ตัว) · CC BY-NC 4.0 (งานวิจัยภายใน)",
        "AQR: เลือกแค่ USA / Global / Global Ex USA · ไฟล์ดิบ 89 MB ไม่ commit (`.gitignore`) · ไม่พบหน้ายอมรับเงื่อนไขตอนดาวน์โหลด · หน้าข้อมูลลงวันที่ 2026-07-31",
        "ETF ทุกตัวเป็น adjusted close (รวมปันผล) · ETF มีค่าธรรมเนียม · 1343.T / CLR.SI ปิดเวลาเอเชีย (เร็วกว่า NY) · USDTHB asof ตามเดิม · Yahoo ตัดแถววันดาวน์โหลด",
        "FRED: DTWEXBGS / DTWEXEMEGS เป็นดัชนี (ไม่ใช่ราคาที่ลงทุนได้) · DFII10 เป็นระดับ % ต่อปี (ใช้ Δ เป็น factor)",
        "AUM_fam: ไฟล์ NAV มี AUM = 0 / ว่างบางแถว (ถือเป็น \"ไม่รายงาน\") · กติกา \"ไม่มี AUM ใน 90 วัน = 0 = ไม่ผ่าน\" อนุรักษ์นิยม · family map ของทีมไม่ได้เชื่อม `Previous Fund Code` (ดูข้อ 9.3)",
        "FundProfile เป็น snapshot ปัจจุบัน (ชื่อกอง / Registration_date) · เกณฑ์อายุ/AUM วัดที่วันตายตัวคนละวัน (look-ahead + survivorship)",
        "ตัวเลข corr ที่ F-R006 คาดเป็น \"คาดการณ์\" — ข้อ 4 คือการวัดจริง (ไม่ได้ปรับ factor ให้ตรงค่าคาด)",
    ):
        P(f"- {t_}")
    P("\n## 12. ต้องให้ผู้ใช้ตัดสินใจ\n")
    P("1. **การเปลี่ยนรหัสกอง Eastspring (ข้อ 9.3)** — ES-* ประมาณ {} family E + {} family O (รวมกองทอง {} · REIT {}) ใน panel มีข้อมูลเริ่ม 2024-06 เพราะรหัสเดิมหลุดจาก 9 เกณฑ์: "
      "(ก) **ตามกติกาตรงตัว (ค่าเริ่มต้น · ทำแล้ว)** ไม่เข้า U · (ข) ต่อ NAV รหัสเดิมเข้า panel + รวม AUM/อายุข้ามรหัส (ต้องสร้าง L0 รอบใหม่ = เปลี่ยน sha ของ panel · ไม่ได้ทำ) — แนะนำ (ก) เพราะ train 2021–2023 ใช้ไม่ได้ตามเงื่อนไขเดิมอยู่แล้ว แต่ผู้ใช้ควรรู้ว่า U_O เสีย ES-GOLD / ES-GOLDBULLION-H / ES-GOLDS / ES-GPROP".format(
          len(rne), len(rno), sum(1 for x in rno if "GOLD" in x[0]), sum(1 for x in rno if "PROP" in x[0])))
    P(f"2. **U_E = {ue} / U_O = {uo}** (ทอง {ugold} · REIT {ureit}) ต่างจากค่าคาด ~209 / ~12 (ข้อ 9.1) — ยอมรับตามนิยาม BRIEF 109 หรือให้ใช้ AUM เฉพาะ class ตัวแทน (~201 / 11)?")
    P(f"3. **I-GOLD → IGOLD-G** เป็นกองเดียวที่เปลี่ยนรหัส (ข้อ 9.2) แต่นับเป็น 2 family ใน U_O (ทั้งคู่ไม่ครบ train/test) — ปล่อยตาม family map เดิม (ค่าเริ่มต้น) หรือรวม/ตัดตอนรายงาน O รายกอง")
    P("4. **JKP ไม่มีผลตอบแทนตลาด** — ตลาด EM ใช้ MSCI_EM (THB · ของเดิม) / KF EM Mkt-RF รายเดือน (ตรวจซ้ำ) แทน · ถ้าต้องการตลาด EM รายสัปดาห์ในหน่วย USD factor แบบ JKP ต้องดาวน์โหลดเพิ่ม (ไม่ได้ทำ · ผู้ใช้ไม่ได้อนุมัติ)")
    P("5. **WML รายเดือน (ข้อ 5)** — KF_DEV_WML ทบรายวันกับไฟล์รายเดือนทางการต่างกัน (corr 0.94–0.96) ขณะที่ factor อื่นของ KF ตรงกัน ≥ 0.997: ที่ชั้นตรวจซ้ำรายเดือนใช้ `KFM_DEV_WML` (ทางการ · แนะนำ) หรือ `KF_DEV_WML` ทบรายวัน หรือรายงานคู่")
    P("6. AQR เลือกเฉพาะ USA / Global / Global Ex USA — ถ้า spec ต้องการระดับภูมิภาค (Europe / North America / Pacific) แจ้งเพื่อเพิ่ม (ไม่ต้องดาวน์โหลด · ไฟล์ดิบมีอยู่)")
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    main()
