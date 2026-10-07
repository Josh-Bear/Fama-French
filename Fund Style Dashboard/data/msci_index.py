"""msci_index.py — โหลด base_data/MSCI_*_ETF.csv + คำนวณ daily return (Phase 1).

MSCI_COUNTRY (18 col) / MSCI_SECTOR (10 col) — แปลงเป็น THB ไว้แล้ว (verify ด้วย corr 0.72–0.77, ดูแผน §0.1)
ช่วงข้อมูล 2021-01-01 → 2026-07-31, ไม่มี NaN กลางช่วง
"""

from __future__ import annotations

import pandas as pd

import config


def _load_levels(path: str, cols: list[str]) -> pd.DataFrame:
    """อ่าน MSCI csv, parse Date เป็น index, คืน level ราคาเรียงคอลัมน์ตาม config."""
    df = pd.read_csv(path, parse_dates=[config.MSCI_DATE_COL]).set_index(config.MSCI_DATE_COL)
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise KeyError(f"{path} ขาดคอลัมน์: {missing}")
    return df[cols].sort_index()


def load_country_index() -> pd.DataFrame:
    """level ราคา MSCI country 18 คอลัมน์ (index=Date)."""
    return _load_levels(config.MSCI_COUNTRY_CSV, config.MSCI_COUNTRY_COLS)


def load_sector_index() -> pd.DataFrame:
    """level ราคา MSCI sector 10 คอลัมน์ (index=Date)."""
    return _load_levels(config.MSCI_SECTOR_CSV, config.MSCI_SECTOR_COLS)


def to_daily_return(levels: pd.DataFrame) -> pd.DataFrame:
    """level -> daily return (pct_change) ต่อ index; ตัดแถวแรกที่เป็น NaN ทั้งหมดออก."""
    return levels.pct_change().iloc[1:]
