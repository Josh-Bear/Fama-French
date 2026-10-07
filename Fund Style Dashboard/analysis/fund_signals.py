"""fund_signals.py — สัญญาณระดับกองของโมเดลหน้า 9 (M004-TF-FX) จาก NAV ของกองเองล้วนๆ.

พอร์ตจากโค้ด backtest ของทีม quant (ตรวจแล้วโดย validator/reviewer) โดยไม่เปลี่ยนตรรกะ — ตัวเลขต้องตรงกับ backtest
ทุกฟังก์ชันรับวันอ้างอิง t และใช้ข้อมูล ≤ t เท่านั้น (point-in-time)

- family ของ share class: ตัด token ท้ายชื่อ (A/H/UH/D/F/U/…) ได้สูงสุด 3 ครั้ง หรือใช้ `share_class_groups.csv` ถ้ามี
- SR12 = (R12-1 − rf × 11/12) ÷ vol52
  R12-1 = NAV สิ้นเดือนที่แล้ว ÷ NAV สิ้นเดือน 12 เดือนก่อน − 1 · vol52 = SD(return รายสัปดาห์ 52 สัปดาห์) × √52
"""
from __future__ import annotations

import re

import numpy as np
import pandas as pd

import config

TAX_TOKEN_RE = re.compile(r'^(SSF|SSFX|SSFE|RMF|TESG|THAIESG|THAIESGX)$', re.IGNORECASE)
CLASS_SUFFIX_RE = re.compile(
    r'^(A|D|R|RA|RD|A\(A\)|A\(D\)|H|UH|E|P|I|IA|AC|AR|AE|C|X|SSF|SSFX|RMF|TESG|THAIESG|THAIESGX|F|U)$',
    re.IGNORECASE)
DIV_RE = re.compile(r'^(D|RD|A\(D\))$', re.IGNORECASE)
FU_RE = re.compile(r'^(F|U)$', re.IGNORECASE)
MAX_SUFFIX_STRIP = 3


def _tokens(fc: str) -> list[str]:
    return re.split(r'[-\s]+', fc.strip())


def is_tax_class(fc: str) -> bool:
    """class ห่อภาษี (SSF/RMF/ThaiESG) — ไม่อยู่ใน universe ของโมเดล."""
    return any(TAX_TOKEN_RE.match(tok) for tok in _tokens(fc) if tok)


def is_dividend(fc: str) -> bool:
    """class ปันผล (token ท้าย D/RD/A(D)) · ข้าม token F/U ท้ายสุดก่อน (X-D-F = ปันผล)."""
    toks = [t for t in _tokens(fc) if t]
    while len(toks) > 1 and FU_RE.match(toks[-1]):
        toks = toks[:-1]
    return bool(toks) and bool(DIV_RE.match(toks[-1]))


def family_of(fc: str, groups: dict[str, str]) -> tuple[str, str]:
    """(family, source) — 'csv' ถ้าอยู่ใน share_class_groups.csv ไม่งั้น 'suffix' (ตัด token ท้ายได้สูงสุด 3 ครั้ง)."""
    if fc in groups:
        return groups[fc], "csv"
    parts = re.split(r'([-\s]+)', fc.strip())  # สลับ token/ตัวคั่น เก็บตัวคั่นไว้ประกอบกลับ
    stripped = 0
    while stripped < MAX_SUFFIX_STRIP and len(parts) >= 3 and CLASS_SUFFIX_RE.match(parts[-1] or ""):
        candidate = parts[:-2]
        if not candidate or not any(p.strip() for p in candidate):
            break
        parts = candidate
        stripped += 1
    fam = "".join(parts).strip()
    return (fam if fam else fc), "suffix"


# ---------------- จุดราคา ณ วันอ้างอิง (asof) ----------------

def prep_arrays(nav_by_fund: dict[str, pd.Series]) -> dict[str, tuple]:
    """FundCode -> (dates datetime64[D], values) สำหรับ asof แบบเร็ว."""
    out = {}
    for fc, s in nav_by_fund.items():
        if len(s) == 0:
            continue
        out[fc] = (s.index.values.astype("datetime64[D]"), s.to_numpy(dtype=float))
    return out


def _asof(dates: np.ndarray, values: np.ndarray, day: np.datetime64, tol_days: int | None = None):
    """NAV ล่าสุดที่ ≤ day ถ้าห่างไม่เกิน tol_days · ไม่งั้น NaN."""
    tol_days = config.TF_ASOF_TOL_DAYS if tol_days is None else tol_days
    idx = int(np.searchsorted(dates, day, side="right")) - 1
    if idx < 0:
        return np.nan
    gap = (day - dates[idx]) / np.timedelta64(1, "D")
    if gap > tol_days:
        return np.nan
    return float(values[idx])


def weekly_points(calendar: pd.DatetimeIndex, t: pd.Timestamp, n: int) -> list[pd.Timestamp]:
    """วันทำการสุดท้ายของปฏิทินดัชนีในแต่ละสัปดาห์ (ISO week) ที่ ≤ t · คืน n จุดล่าสุด."""
    cal = calendar[calendar <= t]
    if len(cal) == 0:
        return []
    iso = cal.isocalendar()
    df = pd.DataFrame({"date": cal, "y": iso["year"].to_numpy(), "w": iso["week"].to_numpy()})
    last_per_week = df.groupby(["y", "w"])["date"].max()
    ts = sorted(pd.Timestamp(v) for v in last_per_week.to_numpy())
    return ts[-n:] if len(ts) >= n else ts


def month_end_points(calendar: pd.DatetimeIndex, t: pd.Timestamp, n: int = 13) -> list[pd.Timestamp]:
    """สิ้นเดือน M-12 .. M0 (M0 = เดือนของ t) · คืน n จุดล่าสุด."""
    cal = calendar[calendar <= t]
    if len(cal) == 0:
        return []
    grp = pd.Series(cal, index=cal).groupby([cal.year, cal.month]).max()
    ts = sorted(pd.Timestamp(v) for v in grp.to_numpy())
    return ts[-n:] if len(ts) >= n else ts


class SignalContext:
    """จุดอ้างอิงรายสัปดาห์/สิ้นเดือน ณ วัน t หนึ่งค่า (ใช้ซ้ำทุกกองใน t เดียวกัน)."""

    def __init__(self, nav_arrays: dict[str, tuple], calendar: pd.DatetimeIndex, t: pd.Timestamp):
        self.nav_arrays = nav_arrays
        self.weeks = weekly_points(calendar, t, config.TF_SIGNAL_WEEKS)
        self.months = month_end_points(calendar, t, 13)
        self._weeks_np = [np.datetime64(w.date()) for w in self.weeks]
        self._months_np = [np.datetime64(m.date()) for m in self.months]

    def _weekly_returns(self, dates, values) -> np.ndarray:
        wp = np.array([_asof(dates, values, wn) for wn in self._weeks_np], dtype=float)
        with np.errstate(invalid="ignore", divide="ignore"):
            return wp[1:] / wp[:-1] - 1.0

    def fund_signal(self, fc: str) -> dict:
        arrs = self.nav_arrays.get(fc)
        if arrs is None or len(self.months) < 13 or len(self.weeks) < config.TF_SIGNAL_WEEKS:
            return {"R12_1": np.nan, "vol52": np.nan, "SR12": np.nan, "n_week_obs": 0}
        dates, values = arrs
        p_m1 = _asof(dates, values, self._months_np[-2])      # สิ้นเดือนที่แล้ว (ข้ามเดือนล่าสุด)
        p_m12 = _asof(dates, values, self._months_np[0])      # สิ้นเดือน 12 เดือนก่อน
        r12_1 = (p_m1 / p_m12 - 1.0) if (p_m1 == p_m1 and p_m12 not in (0.0,) and p_m12 == p_m12) else np.nan
        wr = self._weekly_returns(dates, values)
        valid = ~np.isnan(wr)
        n_obs = int(valid.sum())
        vol52 = np.nan
        if n_obs >= config.TF_SIGNAL_MIN_WEEKS:
            zero_frac = float((wr[valid] == 0.0).mean())
            v = float(np.std(wr[valid], ddof=1)) * np.sqrt(52.0)
            if zero_frac <= config.TF_MAX_ZERO_FRAC and v >= config.TF_MIN_VOL:
                vol52 = v
        sr12 = np.nan
        if r12_1 == r12_1 and vol52 == vol52 and vol52 > 0:
            sr12 = (r12_1 - config.TF_RF_SIGNAL * 11.0 / 12.0) / vol52
        return {"R12_1": r12_1, "vol52": vol52, "SR12": sr12, "n_week_obs": n_obs}

    def weekly_return_series(self, fc: str) -> pd.Series:
        """return รายสัปดาห์ 52 ค่า (อาจมี NaN) สำหรับ covariance ของ ERC."""
        arrs = self.nav_arrays.get(fc)
        if arrs is None or len(self.weeks) < 2:
            return pd.Series(dtype=float)
        return pd.Series(self._weekly_returns(*arrs), index=self.weeks[1:])


def compute_signals(ctx: SignalContext, fund_codes: list[str]) -> pd.DataFrame:
    return pd.DataFrame([{"FundCode": fc, **ctx.fund_signal(fc)} for fc in fund_codes])


def investable_set(t: pd.Timestamp, u_t: pd.DataFrame, signals: pd.DataFrame,
                   groups: dict[str, str]) -> tuple[pd.DataFrame, dict]:
    """U_t -> I_t: ตัดกอง NAV ไม่สด · class ภาษี · class ปันผลถ้า family มี class ไม่ปันผล · สัญญาณคำนวณไม่ได้.

    คืน (I_t พร้อม family/is_dividend/สัญญาณ, จำนวนที่ตัดในแต่ละขั้น)
    """
    df = u_t.merge(signals, on="FundCode", how="left")
    n_u = len(df)
    fresh = (t - df["last_nav_date"]).dt.days <= config.TF_FRESH_DAYS
    n_fresh_cut = int((~fresh).sum())
    df = df[fresh].copy()

    is_tax = df["FundCode"].apply(is_tax_class)
    n_tax_cut = int(is_tax.sum())
    df = df[~is_tax].copy()

    fam_info = df["FundCode"].apply(lambda f: family_of(f, groups))
    df["family"] = fam_info.apply(lambda x: x[0])
    df["fam_source"] = fam_info.apply(lambda x: x[1])
    df["is_dividend"] = df["FundCode"].apply(is_dividend)

    nondiv_families = set(df.loc[~df["is_dividend"], "family"])
    drop_div = df["is_dividend"] & df["family"].isin(nondiv_families)
    n_div_dropped = int(drop_div.sum())
    df = df[~drop_div].copy()

    n_before_signal = len(df)
    df = df.dropna(subset=["R12_1", "vol52"]).reset_index(drop=True)
    counts = {"n_universe": n_u, "n_fresh_cut": n_fresh_cut, "n_tax_cut": n_tax_cut,
              "n_div_dropped": n_div_dropped, "n_signal_cut": n_before_signal - len(df), "n_investable": len(df)}
    return df, counts
