"""matching.py — return series construction (Phase 2) + multi-factor matching (Phase 3).

Phase 2 (build_fund_returns): ใช้ NAVDate เป็นวันอ้างอิงของกอง แล้วเทียบ return ของกอง
  (NAV.pct_change ระหว่าง NAVDate ติดกัน) กับ **compounded index return ในช่วงเดียวกัน**
  ทำง่ายๆ ด้วยอัตราส่วนของ index LEVEL ที่สอง NAVDate (reindex ffill) -> .pct_change()
  = ทบต้นผลตอบแทน index ตลอด gap อัตโนมัติ (แก้ทั้งปัญหา gap + NAV lag พร้อมกัน)
  จากนั้น winsorize ทุกคอลัมน์ที่ 1st–99th percentile แยกทีละ series (clip ไม่ drop)

Phase 3 (match_exposure): StandardScaler + ElasticNetCV เป็นหลัก (รัน Lasso/Ridge เก็บเทียบ)
  primary = |standardized coef| มากสุด, secondary = อันดับ 2, ที่เหลือ non-zero = "อื่นๆ"
  ถ้า coef เหลือ 0 ทุกตัว -> primary/secondary = None ("ไม่พบ exposure ชัดเจน")
"""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
from sklearn.linear_model import ElasticNetCV, LassoCV, RidgeCV
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

import config
from analysis import metrics

FUND_COL = "__fund__"      # ชื่อคอลัมน์ return ของกองใน aligned DataFrame
_ZERO = 1e-9               # coef ที่ |.| ต่ำกว่านี้ถือเป็นศูนย์ (ElasticNet ตัดทิ้ง)


def classify_exposure(fund_coefs: pd.Series, band_pct: float | None = None) -> tuple[str | None, list[str]]:
    """จัด primary / secondary (band-based) จาก coefficient ของกองหนึ่ง — **ฟังก์ชันกลาง**.

    fund_coefs : Series index=ชื่อ index, values=coefficient (โมเดลเดียว)
    คืน (primary, secondary_list) โดย
      primary   = index ที่ |coef| มากสุด (None ถ้า coefficient เป็นศูนย์หมด)
      secondary = ทุก index ที่เหลือที่ |coef| >= |primary| × (1 − band_pct) -> ได้ 0..N ตัว

    ใช้ร่วมกันระหว่างหน้า 3 (viz.match_strength_bar) และหน้า 5 (get_funds_matching_index)
    เพื่อไม่ให้ threshold logic กระจายอยู่หลายที่
    """
    band_pct = config.SECONDARY_BAND_PCT if band_pct is None else band_pct
    nz = fund_coefs[fund_coefs.abs() > _ZERO].abs().sort_values(ascending=False)
    if len(nz) == 0:
        return None, []
    band_lo = nz.iloc[0] * (1 - band_pct)
    return nz.index[0], [ix for ix, v in nz.iloc[1:].items() if v >= band_lo]


def get_index_matches(coefs: pd.DataFrame, index_name: str, scope: str,
                      model: str = "elastic", band_pct: float | None = None) -> pd.DataFrame:
    """กองที่ index_name เป็น exposure ของมัน พร้อม **บทบาท** (primary/secondary).

    coefs: cache/coefs.csv (คอลัมน์ FundCode, scope, index, elastic/lasso/ridge)
    band_pct: ส่งต่อให้ classify_exposure (None = SECONDARY_BAND_PCT · scope style ต้องส่ง STYLE_SECONDARY_BAND_PCT)
    คืน DataFrame [FundCode, role] — role บอกว่าเป็น "primary" หรือ "secondary" (band-based)
    เพื่อให้ผู้ใช้แยกได้ว่า match แน่น (primary) หรือแค่อยู่ใน band (secondary)
    """
    sub = coefs[coefs["scope"] == scope]
    rows = []
    for fund, g in sub.groupby("FundCode"):
        primary, secondary = classify_exposure(g.set_index("index")[model], band_pct=band_pct)
        if index_name == primary:
            rows.append({"FundCode": fund, "role": "primary"})
        elif index_name in secondary:
            rows.append({"FundCode": fund, "role": "secondary"})
    return pd.DataFrame(rows, columns=["FundCode", "role"])


def get_funds_matching_index(coefs: pd.DataFrame, index_name: str, scope: str,
                             model: str = "elastic", band_pct: float | None = None) -> list[str]:
    """รายชื่อ FundCode ที่ index_name เป็น primary **หรือ** secondary (band-based) ของกองนั้น."""
    return get_index_matches(coefs, index_name, scope, model, band_pct)["FundCode"].tolist()


def _winsorize(col: pd.Series) -> pd.Series:
    """clip ที่ 1st–99th percentile ของ series นั้นเอง (ไม่ pool รวม)."""
    lo = col.quantile(config.WINSOR_LOWER)
    hi = col.quantile(config.WINSOR_UPPER)
    return col.clip(lo, hi)


def _clip_to_index_window(fund_nav: pd.Series, index_levels: pd.DataFrame) -> pd.Series:
    """เรียง NAV ตามวันที่ แล้วตัดให้อยู่ในช่วงที่ index มีข้อมูล (ตัด NAVDate ก่อน 2021 และหลัง index วันสุดท้าย)."""
    fund_nav = fund_nav.sort_index()
    lo, hi = index_levels.index.min(), index_levels.index.max()
    return fund_nav[(fund_nav.index >= lo) & (fund_nav.index <= hi)]


def _within_gap_limit(fund_nav: pd.Series, index_levels: pd.DataFrame,
                      max_gap_bdays: int | None = None) -> pd.Series:
    """mask ต่อ NAVDate: True = return ที่สิ้นสุดวันนี้ไม่คร่อมรูเกิน max_gap_bdays วันทำการของ index."""
    max_gap_bdays = config.NAV_MAX_GAP_BDAYS if max_gap_bdays is None else max_gap_bdays
    pos = index_levels.index.searchsorted(fund_nav.index)
    missing = pd.Series(np.r_[0, np.diff(pos) - 1], index=fund_nav.index)
    return missing <= max_gap_bdays


def fund_return_stats(fund_nav: pd.Series, index_levels: pd.DataFrame,
                      max_gap_bdays: int | None = None) -> dict:
    """annualized return / vol ของกองจาก NAV ในช่วงเดียวกับ build_fund_returns (สำหรับแสดงผล + risk model).

    - ann_return = CAGR ของ NAV ต้น–ท้ายในช่วง index (รวมช่วงรูข้อมูล = ผลที่นักลงทุนได้จริง)
    - ann_vol = std(return ที่ไม่คร่อมรู · winsorize 1–99% แบบเดียวกับ regression) × √(จำนวนจุดต่อปีจริง)
      winsorize กัน NAV ผิดพลาดที่ตัวกรอง spike จับไม่ได้ (เช่น KKP SEMICON-H 15–17 มิ.ย. 2026: −56% แล้ว +152%
      ทำให้ vol ดิบ 0.84 แทน ~0.36) — CAGR ใช้ NAV ต้น–ท้าย ไม่โดน glitch กลางช่วง
    - periods_per_year = จำนวน return ที่ใช้ ÷ (วันปฏิทินที่ครอบคลุม ÷ 365.25) — ใช้ annualize variance อื่นของกองเดียวกัน
    ไม่ใช้ 252/n เพราะ NAV กองมีราว 74% ของวันทำการ MSCI (ทบต้น/คูณ √252 เกินจริง)
    """
    nav = _clip_to_index_window(fund_nav, index_levels).dropna()
    ret = nav.pct_change()
    days = pd.Series(nav.index, index=nav.index).diff().dt.days
    keep = _within_gap_limit(nav, index_levels, max_gap_bdays) & ret.notna()
    return {"ann_return": metrics.cagr(nav),
            "ann_vol": metrics.irregular_annualized_volatility(_winsorize(ret[keep]), days[keep]),
            "periods_per_year": metrics.periods_per_year(days[keep])}


def build_fund_returns(fund_nav: pd.Series, index_levels: pd.DataFrame,
                       winsorize: bool = True, max_gap_bdays: int | None = None) -> pd.DataFrame:
    """สร้าง aligned return table ของกองหนึ่ง เทียบกับ index ทั้งชุด.

    fund_nav: Series index=NAVDate(datetime), values=NAV
    index_levels: DataFrame index=Date(datetime), columns=index (level ราคา)
    max_gap_bdays: NAV 2 จุดติดกันที่มีวันทำการของ index หายไประหว่างกันเกินค่านี้ -> ไม่ใช้ return ช่วงนั้น
                   (ทั้งฝั่งกองและ index) · None = config.NAV_MAX_GAP_BDAYS
    คืน DataFrame: columns = [<index cols...>, FUND_COL], index=NAVDate (winsorize แล้ว, dropna)
    """
    fund_nav = _clip_to_index_window(fund_nav, index_levels)

    fret = fund_nav.pct_change()
    # index level ณ NAVDate ของกอง (ffill เผื่อ NAVDate ตรงวันหยุดตลาด) -> % change = ผลตอบแทนทบต้นช่วง gap
    idx_at = index_levels.reindex(fund_nav.index, method="ffill")
    iret = idx_at.pct_change()

    out = iret.copy()
    out[FUND_COL] = fret
    # รูข้อมูล: return ข้ามรูหลายเดือน (เช่น 7 ม.ค. -> 12 มิ.ย. 2026 = +18.5% ใน "จุดเดียว") ไม่ใช่ return ช่วงสั้นแบบจุดอื่น
    # -> ทิ้งทั้งแถว ไม่เติมค่า · ช่วงก่อน/หลังรูยังใช้ตามปกติ · ขาดทีละไม่กี่วันยังทบต้นเหมือนเดิม
    out = out[_within_gap_limit(fund_nav, index_levels, max_gap_bdays)]
    out = out.dropna()
    if winsorize and len(out):
        out = out.apply(_winsorize)
    return out


def _fit(model, X: np.ndarray, y: np.ndarray, cols: list[str]) -> tuple[pd.Series, float]:
    """fit pipeline(StandardScaler, model) -> (standardized coef Series, R²).

    StandardScaler อยู่ใน pipeline เดียวกับ CV ของ model -> scaler ถูก fit บน train fold เท่านั้น
    (กัน data leakage). coef ที่ได้อยู่บนสเกล standardized -> เทียบขนาดข้าม index ได้ตรงๆ.
    """
    pipe = make_pipeline(StandardScaler(), model)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        pipe.fit(X, y)
    coef = pipe.steps[-1][1].coef_
    return pd.Series(coef, index=cols), float(pipe.score(X, y))


def match_exposure(aligned: pd.DataFrame, alternatives: bool = True) -> dict:
    """multi-factor regression กอง vs index ทั้งชุด -> dict ผลลัพธ์.

    keys: coef (ElasticNet, Series), r2, primary, secondary, primary_coef, secondary_coef,
          lasso_coef, lasso_r2, ridge_coef, ridge_r2, n
    alternatives=False -> ข้าม Lasso/Ridge (lasso_coef/ridge_coef = None, r2 = NaN) สำหรับ caller ที่ใช้แค่ ElasticNet
    """
    cols = [c for c in aligned.columns if c != FUND_COL]
    X = aligned[cols].to_numpy()
    y = aligned[FUND_COL].to_numpy()
    n = len(aligned)

    en_coef, en_r2 = _fit(
        ElasticNetCV(l1_ratio=[0.1, 0.5, 0.9, 1.0], cv=5, random_state=0, max_iter=5000), X, y, cols)
    if alternatives:
        la_coef, la_r2 = _fit(LassoCV(cv=5, random_state=0, max_iter=5000), X, y, cols)
        ri_coef, ri_r2 = _fit(RidgeCV(alphas=np.logspace(-3, 3, 25)), X, y, cols)
    else:   # ~30% ของเวลา fit — ไม่ต้องจ่ายถ้าไม่มีใครอ่าน (หน้า 6)
        la_coef = ri_coef = None
        la_r2 = ri_r2 = np.nan

    # primary/secondary จาก |ElasticNet coef| (ตามแผน) — เฉพาะตัวที่ไม่เป็นศูนย์
    ranked = en_coef[en_coef.abs() > _ZERO].abs().sort_values(ascending=False)
    primary = ranked.index[0] if len(ranked) >= 1 else None
    secondary = ranked.index[1] if len(ranked) >= 2 else None

    return {
        "n": n,
        "coef": en_coef, "r2": en_r2,
        "primary": primary, "secondary": secondary,
        "primary_coef": float(en_coef[primary]) if primary else np.nan,
        "secondary_coef": float(en_coef[secondary]) if secondary else np.nan,
        "lasso_coef": la_coef, "lasso_r2": la_r2,
        "ridge_coef": ri_coef, "ridge_r2": ri_r2,
    }


def nested_r2(aligned: pd.DataFrame, base_cols: list[str],
              extra_cols: list[str]) -> tuple[float, float, pd.Series, pd.Series]:
    """OLS 2 โมเดลซ้อนกัน (base กับ base+extra) บน return ที่ align แล้ว
    -> (R² full, R² base, coef full, coef base).

    ใช้วัดว่า extra (เช่น style factor) อธิบาย return เพิ่มจาก base (เช่น ตลาด) ได้เท่าไหร่
    OLS ไม่มี penalty -> R² full ≥ R² base เสมอ (ElasticNet หดค่าจึงใช้วัดส่วนต่างนี้ไม่ได้)
    """
    y = aligned[FUND_COL].to_numpy()
    ss_tot = float(((y - y.mean()) ** 2).sum())

    def _ols(cols: list[str]) -> tuple[float, np.ndarray]:
        X = np.column_stack([np.ones(len(y)), aligned[cols].to_numpy()])
        beta, *_ = np.linalg.lstsq(X, y, rcond=None)
        ss_res = float(((y - X @ beta) ** 2).sum())
        return (1.0 - ss_res / ss_tot if ss_tot > 0 else np.nan), beta[1:]

    r2_base, beta_base = _ols(base_cols)
    r2_full, beta_full = _ols(base_cols + extra_cols)
    return (float(r2_full), float(r2_base),
            pd.Series(beta_full, index=base_cols + extra_cols), pd.Series(beta_base, index=base_cols))
