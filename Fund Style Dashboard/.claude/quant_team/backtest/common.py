"""common.py — path setup, point-in-time NAV/calendar/universe/B0. โมดูลกลางใช้ซ้ำได้กับ M002+.

อ่าน NAV จาก cache/nav_clean.parquet เท่านั้น (ห้ามเรียก nav_loader.load_nav_history / data_access.build_* ฯลฯ)
"""
from __future__ import annotations

import os
import sys

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(THIS_DIR, "..", "..", ".."))
CACHE_DIR = os.path.join(THIS_DIR, "cache")
RESULTS_DIR = os.path.join(THIS_DIR, "results")
os.makedirs(CACHE_DIR, exist_ok=True)
os.makedirs(RESULTS_DIR, exist_ok=True)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import numpy as np
import pandas as pd

import config
import data_access
from data import msci_index

NAV_PARQUET = os.path.join(PROJECT_ROOT, "cache", "nav_clean.parquet")


def load_nav() -> pd.DataFrame:
    df = pd.read_parquet(NAV_PARQUET)
    df["NAVDate"] = pd.to_datetime(df["NAVDate"])
    return df


def build_nav_by_fund(nav: pd.DataFrame) -> dict[str, pd.Series]:
    """FundCode -> Series(index=NAVDate เรียงแล้ว, values=NAV) ประวัติเต็ม (ตัด ≤ t ทีหลังด้วย .loc[:t])."""
    out = {}
    for fc, g in nav.sort_values("NAVDate").groupby("FundCode"):
        out[fc] = g.set_index("NAVDate")["NAV"]
    return out


def load_calendar() -> pd.DatetimeIndex:
    c = msci_index.load_country_index().index
    s = msci_index.load_sector_index().index
    return c.union(s).sort_values()


def load_levels():
    """คืน (levels_country_full, levels_sector_full, levels_21_full) — level ราคา, ยังไม่ตัดตาม t."""
    c = msci_index.load_country_index()
    s = msci_index.load_sector_index()
    combined = pd.concat([c[config.SCORE_COUNTRY_CLEAN], s[config.MSCI_SECTOR_COLS]], axis=1).dropna()
    return c, s, combined


def quarter_ends(calendar: pd.DatetimeIndex, start: str, end: str) -> list[pd.Timestamp]:
    """วันสุดท้ายของไตรมาสที่มีในปฏิทินดัชนี ระหว่าง [start, end]."""
    cal = pd.Series(calendar, index=calendar).sort_index()
    grp = cal.groupby([cal.index.year, cal.index.quarter]).max()
    ts = sorted(pd.Timestamp(v) for v in grp.values)
    return [t for t in ts if pd.Timestamp(start) <= t <= pd.Timestamp(end)]


def month_ends(calendar: pd.DatetimeIndex, start: pd.Timestamp, end: str) -> list[pd.Timestamp]:
    cal = pd.Series(calendar, index=calendar).sort_index()
    grp = cal.groupby([cal.index.year, cal.index.month]).max()
    ts = sorted(pd.Timestamp(v) for v in grp.values)
    return [t for t in ts if start <= t <= pd.Timestamp(end)]


def execution_date(calendar: pd.DatetimeIndex, t: pd.Timestamp) -> pd.Timestamp:
    """e = วันทำการที่ 2 ของปฏิทินดัชนีหลัง t."""
    after = calendar[calendar > t]
    assert len(after) >= 2, f"ปฏิทินดัชนีไม่พอหลัง t={t}"
    e = after[1]
    assert e > t
    return e


def universe_at(nav: pd.DataFrame, t: pd.Timestamp) -> pd.DataFrame:
    """U_t: กองที่ NAV สด (<=90 วันปฏิทินจาก t) และมีประวัติ >=252 NAVDate ไม่ซ้ำใน [2021-01-01, t].

    ไม่กรองด้วยคอลัมน์ status (look-ahead) — point-in-time ล้วนๆ จาก NAVDate <= t เท่านั้น
    """
    sub = nav[nav["NAVDate"] <= t]
    assert sub["NAVDate"].max() <= t  # sanity: no look-ahead in slice
    g = sub.groupby("FundCode")
    last_date = g["NAVDate"].max()
    hist = sub[sub["NAVDate"] >= pd.Timestamp("2021-01-01")].groupby("FundCode")["NAVDate"].nunique()
    stale_ok = (t - last_date).dt.days <= config.NAV_STALE_MAX_DAYS
    hist_ok = hist.reindex(last_date.index).fillna(0) >= 252
    keep = last_date.index[stale_ok & hist_ok]
    last_rows = sub[sub["FundCode"].isin(keep)].sort_values("NAVDate").groupby("FundCode").tail(1)
    out = last_rows.set_index("FundCode").loc[list(keep), ["NAVDate", "NAV", "AUM"]].reset_index()
    out.columns = ["FundCode", "last_nav_date", "last_nav", "last_aum"]
    return out.reset_index(drop=True)


def b0_universe(u_t: pd.DataFrame, groups: dict) -> pd.DataFrame:
    """B0 = 1 share class ต่อกลุ่ม (ตัวที่ AUM ล่าสุดมากสุดในกลุ่ม, จาก U_t ที่ผ่าน staleness+history แล้ว)."""
    df = u_t.copy()
    df["group"] = df["FundCode"].map(lambda f: groups.get(f, f))
    df["last_aum"] = df["last_aum"].fillna(0.0)
    picked = df.sort_values("last_aum", ascending=False).groupby("group", as_index=False).head(1)
    return picked.reset_index(drop=True)


def load_groups() -> dict[str, str]:
    return data_access.share_class_groups()
