"""exposure.py — fit exposure ของกองต่อ MSCI (ElasticNet) แบบ expanding window [2021-01-01, t] · cache ต่อ (t, scope)
ใต้ .claude/quant_team/backtest/cache/ (parquet) เพื่อใช้ซ้ำข้าม run/รุ่นโมเดล (M002+).

ใช้ analysis.matching ตรงๆ (read-only import) — ห้ามเรียก data_access.build_* / portfolio_risk_model
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd
from joblib import Parallel, delayed

import common
import config
from analysis import matching


def _fit_one(fund_code: str, fund_nav_t: pd.Series, levels_t: pd.DataFrame, t: pd.Timestamp) -> dict:
    # sanity: ไม่มีข้อมูลหลัง t รั่วเข้ามา
    if len(fund_nav_t):
        assert fund_nav_t.index.max() <= t, f"look-ahead NAV: {fund_code} {fund_nav_t.index.max()} > {t}"
    assert levels_t.index.max() <= t, f"look-ahead index level ณ {t}"
    if len(fund_nav_t) < 2:
        return {"FundCode": fund_code, "n": 0, "r2": np.nan, "primary": None, "secondary": None,
                "primary_coef": np.nan, "secondary_coef": np.nan}
    aligned = matching.build_fund_returns(fund_nav_t, levels_t)
    if len(aligned) < config.MIN_REGRESSION_OBS:
        return {"FundCode": fund_code, "n": len(aligned), "r2": np.nan, "primary": None, "secondary": None,
                "primary_coef": np.nan, "secondary_coef": np.nan}
    res = matching.match_exposure(aligned, alternatives=False)
    return {"FundCode": fund_code, "n": res["n"], "r2": res["r2"], "primary": res["primary"],
            "secondary": res["secondary"], "primary_coef": res["primary_coef"],
            "secondary_coef": res["secondary_coef"]}


def fit_scope(fund_codes: list[str], nav_by_fund: dict[str, pd.Series], levels_full: pd.DataFrame,
              cols: list[str], t: pd.Timestamp, scope_name: str, n_jobs: int = 8,
              use_cache: bool = True) -> pd.DataFrame:
    """fit ElasticNet ของทุกกองใน fund_codes ต่อ index[cols] ด้วยข้อมูล <= t (expanding window)."""
    key = f"exposure_{scope_name}_{len(cols)}c_{t.date()}"
    cache_path = os.path.join(common.CACHE_DIR, key + ".parquet")
    if use_cache and os.path.exists(cache_path):
        cached = pd.read_parquet(cache_path)
        if set(cached["FundCode"]) >= set(fund_codes):
            return cached[cached["FundCode"].isin(fund_codes)].reset_index(drop=True)
    levels_t = levels_full.loc[:t, cols]
    assert levels_t.index.max() <= t

    def _job(fc):
        nav_t = nav_by_fund[fc].loc[:t]
        return _fit_one(fc, nav_t, levels_t, t)

    results = Parallel(n_jobs=n_jobs, prefer="threads")(delayed(_job)(fc) for fc in fund_codes)
    df = pd.DataFrame(results)
    if use_cache:
        df.to_parquet(cache_path)
    return df


def build_matches(country_df: pd.DataFrame, sector_df: pd.DataFrame) -> pd.DataFrame:
    """รวม country/sector exposure -> matches_t (เฉพาะกองที่ผ่าน guard ทั้ง 2 scope — ตามกฎ §4.1.3)."""
    c = country_df.rename(columns={"r2": "country_r2", "primary": "country_primary",
                                    "secondary": "country_secondary",
                                    "primary_coef": "country_primary_coef",
                                    "secondary_coef": "country_secondary_coef"})
    s = sector_df.rename(columns={"r2": "sector_r2", "primary": "sector_primary",
                                   "secondary": "sector_secondary",
                                   "primary_coef": "sector_primary_coef",
                                   "secondary_coef": "sector_secondary_coef"})
    m = c.merge(s, on="FundCode", how="inner")
    m = m.dropna(subset=["country_r2", "sector_r2"])
    cols = ["FundCode", "country_primary", "country_secondary", "country_r2",
            "country_primary_coef", "country_secondary_coef",
            "sector_primary", "sector_secondary", "sector_r2",
            "sector_primary_coef", "sector_secondary_coef"]
    return m[cols].reset_index(drop=True)
