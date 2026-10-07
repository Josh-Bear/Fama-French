"""screening.py — คณิตของหน้า 8 Score Screening (pure functions — test ได้ตรงๆ).

แนวคิด (ดู docs/pages/8-score-screen.md · ที่มา PAGE8_PORTFOLIO_OPTIMIZE_PLAN.md §12 / §12.14):
  "โซนดี" ของ index = ผลตอบแทน 11 เดือน (ข้ามเดือนล่าสุด) **ต่อหนึ่งหน่วยความเสี่ยง** ของช่วงเดียวกัน
  (return 12-1 ÷ realized vol · config.SCORE_ZONE_METHOD — สูตรเดิมคูณอันดับ return กับอันดับ GARCH ยังเลือกได้ 1 รอบ)
  คะแนนกอง = ความแน่นของ match (R² country × R² sector) × คะแนนโซนของคู่ (country, sector) ที่กองนั้นเกาะอยู่
  แล้วเลือกกองแบบ greedy ให้แต่ละกอง "เดิมพัน" คนละ country/sector กัน (กันพอร์ตซ้ำ theme เดียว)

หน่วย/ทิศทาง (กันสับสน — บทเรียนจาก §12.8):
  return_pct    ใกล้ 1 = ผลตอบแทนดี
  vol_pct_good  ใกล้ 1 = **นิ่ง/ดี** (กลับด้านจาก percentile ของ vol ดิบแล้ว) — เฉพาะสูตรเดิม
  ทั้งคู่ rescale เป็นช่วง (0.01, 0.99) กันค่าอันดับท้าย/หัวชนขอบ 0 แล้วคูณกันได้ 0 ทั้งแถว
"""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np
import pandas as pd

import config
from analysis import metrics

PRIMARY, SECONDARY, FILL = "primary", "secondary", "fill"


def pct_rescaled(values: pd.Series, invert: bool = False) -> pd.Series:
    """percentile rank ภายในชุดที่ส่งมา -> (0.01, 0.99). invert=True สำหรับตัวที่ "ต่ำ = ดี" (vol)."""
    # invert ด้วย ascending=False (ไม่ใช่ 1 − rank) — ไม่งั้นจะไม่สมมาตร: rank(pct) ต่ำสุดคือ 1/n ไม่ใช่ 0
    # ตัวที่ vol ต่ำสุดจึงจะได้แค่ (n−1)/n ทั้งที่ควรได้เต็มเหมือนตัวที่ return สูงสุด
    rank = values.rank(pct=True, ascending=not invert)
    return config.SCORE_PCT_LO + (config.SCORE_PCT_HI - config.SCORE_PCT_LO) * rank


def realized_vol_window(series: pd.Series, window: int | None = None, skip: int | None = None) -> float:
    """annualized realized vol ของช่วงเดียวกับ momentum 12-1: return รายวันจากราคา t−window ถึง t−skip.

    = window − skip return (ค่าเริ่มต้น 231) · ×√TRADING_DAYS ผ่าน metrics.annualized_volatility (ตัวคูณคงที่ ไม่กระทบอันดับ)
    ข้อมูลไม่ถึง window + 1 จุด -> NaN · slice ด้วยตำแหน่งบวก เพราะ iloc[a:-0] ว่าง (กรณี skip = 0)
    """
    window = config.SCORE_RETURN_WINDOW if window is None else window
    skip = config.SCORE_RETURN_SKIP if skip is None else skip
    s = series.sort_index().dropna()
    n = len(s)
    if n < window + 1:
        return np.nan
    seg = s.iloc[n - 1 - window:n - skip]                 # ราคา t−window .. t−skip (window − skip + 1 จุด)
    return metrics.annualized_volatility(seg.pct_change())


def zone_scores(snapshot: pd.DataFrame, scope: str, indices: list[str] | None = None) -> pd.DataFrame:
    """คะแนนโซนต่อ index ภายใน scope เดียว -> DataFrame(index=ชื่อ index) เรียง score มาก->น้อย.

    config.SCORE_ZONE_METHOD:
      "ret_over_realized_vol" -> [return_12m1, vol_realized, ratio, score] · score = pct_rescaled(return ÷ vol)
                                 vol ≤ 0 / NaN -> ratio NaN -> score NaN (กองที่เกาะโซนนี้ไม่ได้คะแนน ไม่ผ่านเกณฑ์)
      "rank_x_rank_garch"     -> [return_pct, vol_pct_good, score] · score = อันดับ return × อันดับ GARCH กลับด้าน (สูตรเดิม)

    indices : จำกัด universe (เช่น country ชุด VIF-cleaned 11 ตัว) — percentile ถูก **re-rank ภายในชุดที่เหลือ**
              ไม่ใช่คำนวณจาก 18 ตัวแล้วกรองแสดง (policy §12.10 — ต่างกันจริง เช่น USA 0.333 vs 0.455)
    """
    sub = snapshot[snapshot["scope"] == scope].set_index("index")
    if indices is not None:
        missing = [ix for ix in indices if ix not in sub.index]
        if missing:
            raise KeyError(f"snapshot ไม่มี index: {missing}")
        sub = sub.loc[indices]
    method = config.SCORE_ZONE_METHOD
    if method == "ret_over_realized_vol":
        mom, vol = sub[config.SCORE_RETURN_COL], sub[config.SCORE_VOL_COL]
        ratio = mom / vol.where(vol > 0)
        out = pd.DataFrame({"return_12m1": mom, "vol_realized": vol, "ratio": ratio, "score": pct_rescaled(ratio)})
    elif method == "rank_x_rank_garch":
        out = pd.DataFrame({
            "return_pct": pct_rescaled(sub[config.SCORE_RETURN_COL]),
            "vol_pct_good": pct_rescaled(sub["vol_forecast"], invert=True),
        })
        out["score"] = out["return_pct"] * out["vol_pct_good"]
    else:
        raise ValueError(f"SCORE_ZONE_METHOD ไม่รู้จัก: {method!r}")
    return out.sort_values("score", ascending=False)


def score_matrix(country: pd.DataFrame, sector: pd.DataFrame) -> pd.DataFrame:
    """ตาราง country × sector = country_score × sector_score × SCORE_MATRIX_SCALE."""
    return pd.DataFrame(np.outer(country["score"], sector["score"]) * config.SCORE_MATRIX_SCALE,
                        index=country.index, columns=sector.index)


def _passes_band(primary_coef: float, secondary_coef: float, band_pct: float | None = None) -> bool:
    """secondary ผ่านเกณฑ์ band ไหม — ต้องอยู่ในช่วง [primary_coef × (1 − band_pct), primary_coef]

    คือทิศทางเดียวกับ primary (ไม่ใช่ |coef| แบบ SECONDARY_BAND_PCT หน้า 5/6) และแรงอย่างน้อย (1 − band_pct)
    ของ primary · NaN ฝั่งใดฝั่งหนึ่ง (ไม่มี primary/secondary) = ไม่ผ่านเสมอ (ตัดสินใจ 2026-09-29 — กันกรณี
    secondary สวนทาง primary ที่เจอใน TUSFIN-A และกองอื่นๆ)
    """
    if pd.isna(primary_coef) or pd.isna(secondary_coef):
        return False
    band_pct = config.SCORE_SECONDARY_BAND_PCT if band_pct is None else band_pct
    lo, hi = sorted([primary_coef, primary_coef * (1 - band_pct)])
    return lo <= secondary_coef <= hi


def _pair_score(matrix: pd.DataFrame, country, sector) -> float:
    """ค่าในตารางของคู่ (country, sector) — คู่ที่ไม่มีในตาราง (None/ถูกตัดออกจาก universe) = NaN."""
    if country in matrix.index and sector in matrix.columns:
        return float(matrix.at[country, sector])
    return np.nan


def fund_scores(matches: pd.DataFrame, matrix: pd.DataFrame) -> pd.DataFrame:
    """คะแนนต่อกอง จาก match ของกอง (primary/secondary + R² ทั้ง 2 scope) และตารางโซน.

    matches ต้องมีคอลัมน์: FundCode, country_primary, country_secondary, country_r2,
                          sector_primary, sector_secondary, sector_r2,
                          country_primary_coef, country_secondary_coef, sector_primary_coef, sector_secondary_coef
    score           = (country_r2 × sector_r2) × zone score ของคู่ primary   <- ใช้จัดอันดับเสมอ
    score_secondary = (country_r2 × sector_r2) × zone score ของคู่ secondary <- โชว์คู่กันเพื่อความโปร่งใส
    กองที่คู่ primary ใช้ไม่ได้ (primary=None หรือ index ไม่อยู่ใน universe) ถูกตัดออก (§12.10 None-handling)

    score_secondary ถูกเซ็ตเป็น NaN ถ้า country_secondary **หรือ** sector_secondary ไม่ผ่าน _passes_band
    เทียบกับ primary ของตัวเอง (ทิศทางต้องตรงกัน + แรงอย่างน้อย SCORE_SECONDARY_BAND_PCT ของ primary) —
    กัน secondary ที่จริงๆสวนทาง/อ่อนเกินไปไม่ให้ถูกใช้เป็น fallback ตอน greedy_select (ตัดสินใจ 2026-09-29)
    """
    df = matches.copy()
    df["match_r2"] = df["country_r2"] * df["sector_r2"]
    df["score"] = [df["match_r2"].iat[i] * _pair_score(matrix, c, s) for i, (c, s) in
                   enumerate(zip(df["country_primary"], df["sector_primary"]))]
    df["score_secondary"] = [df["match_r2"].iat[i] * _pair_score(matrix, c, s) for i, (c, s) in
                             enumerate(zip(df["country_secondary"], df["sector_secondary"]))]
    secondary_ok = [
        _passes_band(df["country_primary_coef"].iat[i], df["country_secondary_coef"].iat[i])
        and _passes_band(df["sector_primary_coef"].iat[i], df["sector_secondary_coef"].iat[i])
        for i in range(len(df))
    ]
    df.loc[~pd.Series(secondary_ok, index=df.index), "score_secondary"] = np.nan
    return df.dropna(subset=["score"]).sort_values("score", ascending=False).reset_index(drop=True)


def _is_new(country, sector, used_c: set, used_s: set, strict_and: bool) -> bool:
    """คู่นี้ยัง 'ใหม่' พอจะเลือกได้ไหม — AND = ต้องใหม่ทั้งคู่ · OR = ใหม่ตัวใดตัวหนึ่งพอ."""
    if pd.isna(country) or pd.isna(sector):
        return False
    new_c, new_s = country not in used_c, sector not in used_s
    return (new_c and new_s) if strict_and else (new_c or new_s)


def greedy_select(scored: pd.DataFrame, n: int | None = None, use_secondary: bool = True,
                  strict_and: bool = True, min_score: float = 0.0,
                  groups: Mapping[str, str] | None = None) -> pd.DataFrame:
    """เลือกกองแบบ greedy ไล่จากคะแนนสูงสุด ให้ไม่ซ้ำ country/sector กัน แล้วเติมให้ครบ n แถว.

    - ผ่านเกณฑ์ด้วยคู่ primary ก่อน · ถ้าใช้ไม่ได้ (ชนกับที่เลือกไปแล้ว **หรือ** คะแนนต่ำกว่า min_score)
      และ use_secondary จึงลองคู่ secondary
      (ถ้า score_secondary เป็น NaN — ไม่มี secondary หรือ secondary ไม่ผ่าน _passes_band — ไม่ลองเลย)
    - min_score : score ของ**คู่ที่ใช้จริง** (primary -> score · secondary -> score_secondary) ต้อง >= ค่านี้ถึงจะเลือก
      ลอง secondary ทั้งตอน primary ชนและตอน primary อ่อน — ไม่งั้นกองที่ primary "ว่าง" จะเสียเปรียบกองที่ primary
      ถูกใช้ไปแล้ว (เช่น KKP G-THEME-H primary 0.08 · คู่สำรอง 6.94 — ตัดสินใจ 2026-09-29)
    - เลือกแล้ว mark ทั้ง country และ sector ของคู่ที่ใช้จริงเป็น used เสมอ (ทุกโหมด)
      และเมื่อ use_secondary เปิด mark **ทั้งสองคู่ของกองนั้น** (primary + secondary ที่ผ่าน band) ด้วย — ไม่งั้นกองถัดไปที่
      profile เหมือนกันทั้ง primary/secondary จะเข้ามาทางคู่ที่ยังว่าง = 2 กองแต่เป็นเดิมพันเดียว (V1 · ตัดสินใจ 2026-10-02)
    - groups : {FundCode: กลุ่ม share class} — กลุ่มหนึ่งผ่านเกณฑ์ได้ไม่เกิน 1 class (class คะแนนสูงสุดที่ผ่านก่อนได้)
      share class ของกองเดียวกันถือพอร์ตเดียวกัน (corr รายวัน ~0.99) แต่ ElasticNet อาจให้คู่ต่างกัน จึงหลุดตัวกรอง
      country/sector ได้ (PRINCIPAL GEF-X USA/MT vs GEF-A USA/IT) · กองที่ไม่อยู่ใน groups = กลุ่มของตัวเอง
    - เพดานจริง: โหมด AND ได้ ≤ จำนวน sector (10) · โหมด OR ได้ ≤ country + sector − 1 (แต่ละกองต้องเพิ่มของใหม่ ≥ 1)
      ที่เหลือเติมด้วยกองคะแนนถัดไปที่ยังไม่ถูกเลือก (`pair = "fill"`, eligible=False) ให้ครบ n
    """
    n = config.SCORE_TOP_N if n is None else n
    used_c: set = set()
    used_s: set = set()
    picked: list[dict] = []
    taken: set = set()
    used_g: set = set()
    groups = groups or {}
    for row in scored.itertuples(index=False):
        if len(picked) >= n:
            break
        group = groups.get(row.FundCode, row.FundCode)
        if group in used_g:
            continue                    # share class อื่นของกองเดียวกันผ่านไปแล้ว -> ไปเป็น fill
        for pair, country, sector, value in (
            (PRIMARY, row.country_primary, row.sector_primary, row.score),
            (SECONDARY, row.country_secondary, row.sector_secondary, row.score_secondary),
        ):
            if pair == SECONDARY and (not use_secondary or pd.isna(value)):
                break   # ไม่มี secondary หรือไม่ผ่าน band (fund_scores เซ็ต NaN ไว้แล้ว) — ไม่ลองเลย
            # คู่ต้อง "ใหม่" และคะแนนถึงเกณฑ์ · ไม่ผ่านข้อใดข้อหนึ่ง -> ลองคู่ถัดไป (ไม่ผ่านทั้งคู่ = ไปเป็น fill)
            if _is_new(country, sector, used_c, used_s, strict_and) and value >= min_score:
                used_c.add(country)
                used_s.add(sector)
                if use_secondary:                       # V1: กันกอง profile ซ้ำเข้าทางคู่ที่ยังว่าง
                    for c, s, v in ((row.country_primary, row.sector_primary, row.score),
                                    (row.country_secondary, row.sector_secondary, row.score_secondary)):
                        if pd.notna(v):
                            used_c.add(c)
                            used_s.add(s)
                used_g.add(group)
                taken.add(row.FundCode)
                picked.append({"FundCode": row.FundCode, "pair": pair, "used_country": country,
                               "used_sector": sector, "pair_score": value, "eligible": True})
                break

    for row in scored.itertuples(index=False):        # เติมให้ครบ n — ไม่ mark used (ไม่ได้ผ่านเกณฑ์)
        if len(picked) >= n:
            break
        if row.FundCode not in taken:
            picked.append({"FundCode": row.FundCode, "pair": FILL, "used_country": None,
                           "used_sector": None, "pair_score": row.score, "eligible": False})
    out = pd.DataFrame(picked, columns=["FundCode", "pair", "used_country", "used_sector",
                                        "pair_score", "eligible"])
    out["eligible"] = out["eligible"].astype(bool)   # ว่าง -> object dtype ทำให้ df[mask] กลายเป็นเลือกคอลัมน์
    return out.merge(scored, on="FundCode", how="left")
