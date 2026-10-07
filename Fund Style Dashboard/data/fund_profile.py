"""fund_profile.py — โหลด + กรอง base_data/FundProfile.csv (Phase 1).

กรองตามเงื่อนไข 9 ข้อใน config (FILTER_EQ 6 / FILTER_NEQ 2 / FILTER_EMPTY 1) -> คาดเหลือ 715 กอง
(E=600, F=77, O=38) — verify กับข้อมูลจริงแล้ว 2026-09-01 (ดูแผน §0.1)
"""

from __future__ import annotations

import pandas as pd

import config


def _norm(s: pd.Series) -> pd.Series:
    """normalize ค่า string: NaN -> '' แล้ว strip ช่องว่าง (ค่าฟิลเตอร์ในไฟล์มี trailing space ได้)."""
    return s.fillna("").astype(str).str.strip()


def load_fund_profile() -> pd.DataFrame:
    """อ่าน FundProfile.csv (encoding utf-8-sig เพื่อตัด BOM). คืน DataFrame ดิบทั้งตาราง (ทุกคอลัมน์เป็น str)."""
    return pd.read_csv(config.FUND_PROFILE_CSV, encoding="utf-8-sig", dtype=str, low_memory=False)


def filter_funds(profile: pd.DataFrame) -> pd.DataFrame:
    """กรองตาม config.FILTER_EQ / FILTER_NEQ / FILTER_EMPTY -> คืนเฉพาะกองที่เข้าเกณฑ์ (คาด 715).

    - FILTER_EQ: คอลัมน์ต้อง == ค่าที่กำหนด (เทียบหลัง strip)
    - FILTER_NEQ: คอลัมน์ต้อง != ค่าที่กำหนด
    - FILTER_EMPTY: คอลัมน์ต้องเป็นค่าว่าง (Tax Type ว่าง = กองทั่วไป ไม่ใช่ RMF/SSF/LTF)
    """
    missing = [c for c in (*config.FILTER_EQ, *config.FILTER_NEQ, *config.FILTER_EMPTY)
               if c not in profile.columns]
    if missing:
        raise KeyError(f"FundProfile.csv ขาดคอลัมน์ที่ใช้กรอง: {missing}")

    mask = pd.Series(True, index=profile.index)
    for col, val in config.FILTER_EQ.items():
        mask &= _norm(profile[col]) == val
    for col, val in config.FILTER_NEQ.items():
        mask &= _norm(profile[col]) != val
    for col in config.FILTER_EMPTY:
        mask &= _norm(profile[col]) == ""
    return profile[mask].copy()


def fund_universe(filtered: pd.DataFrame) -> list[str]:
    """list ของ Fund Code (strip แล้ว) จากผลกรอง — ใช้ส่งต่อให้ nav_loader."""
    return sorted(_norm(filtered[config.FUND_CODE_COL]).unique())


def policy_map(filtered: pd.DataFrame) -> dict[str, str]:
    """map Fund Code -> Fund Policy (E/F/O) — ใช้ระบายสี/แยกกลุ่มใน dashboard ภายหลัง."""
    codes = _norm(filtered[config.FUND_CODE_COL])
    pol = _norm(filtered[config.FUND_POLICY_COL])
    return dict(zip(codes, pol))
