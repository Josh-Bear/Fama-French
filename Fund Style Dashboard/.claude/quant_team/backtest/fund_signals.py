"""fund_signals.py — สัญญาณระดับกอง (C3), family map (C2 ข้อ3), investable set I_t (C2) ตาม
.claude/quant_team/specs/M002-M005_plan.md · ไม่ใช้ ElasticNet/exposure cache เลย (สัญญาณจาก NAV กองเองล้วนๆ)

ทุกฟังก์ชันรับ t และตัดข้อมูล <= t เท่านั้น (point-in-time)
"""
from __future__ import annotations

import re

import numpy as np
import pandas as pd

RF_ANNUAL_SIGNAL = 0.02  # rf ที่ใช้ลบใน SR12 (สอดคล้อง rf หลักของโปรเจกต์ 2%/ปี — C3)

TAX_TOKEN_RE = re.compile(r'^(SSF|SSFX|SSFE|RMF|TESG|THAIESG|THAIESGX)$', re.IGNORECASE)
CLASS_SUFFIX_RE = re.compile(
    r'^(A|D|R|RA|RD|A\(A\)|A\(D\)|H|UH|E|P|I|IA|AC|AR|AE|C|X|SSF|SSFX|RMF|TESG|THAIESG|THAIESGX)$',
    re.IGNORECASE)
DIV_RE = re.compile(r'^(D|RD|A\(D\))$', re.IGNORECASE)
# M006 §2 + M007 §3 (family map fix): เพิ่ม token F และ U, ตัดท้ายได้สูงสุด 3 ครั้ง — ใช้เมื่อ fixed=True เท่านั้น
# (default fixed=False = พฤติกรรมเดิมของ M002–M005 ทุกประการ)
CLASS_SUFFIX_RE_FX = re.compile(
    r'^(A|D|R|RA|RD|A\(A\)|A\(D\)|H|UH|E|P|I|IA|AC|AR|AE|C|X|SSF|SSFX|RMF|TESG|THAIESG|THAIESGX|F|U)$',
    re.IGNORECASE)
FU_RE = re.compile(r'^(F|U)$', re.IGNORECASE)


def _tokens(fc: str) -> list[str]:
    return re.split(r'[-\s]+', fc.strip())


def is_tax_class(fc: str) -> bool:
    return any(TAX_TOKEN_RE.match(tok) for tok in _tokens(fc) if tok)


def is_dividend(fc: str, fixed: bool = False) -> bool:
    toks = [t for t in _tokens(fc) if t]
    if fixed:  # ข้าม token F/U ท้ายสุดก่อน (X-D-F = ปันผล)
        while len(toks) > 1 and FU_RE.match(toks[-1]):
            toks = toks[:-1]
    return bool(toks) and bool(DIV_RE.match(toks[-1]))


def family_of(fc: str, groups: dict[str, str], fixed: bool = False) -> tuple[str, str]:
    """(family, source) — source='csv' ถ้าอยู่ใน share_class_groups.csv ไม่งั้น 'suffix' (ตัด token ท้ายซ้ำได้ 2 ครั้ง)."""
    if fc in groups:
        return groups[fc], "csv"
    parts = re.split(r'([-\s]+)', fc.strip())  # alternating token/sep, เก็บ separator ไว้ประกอบกลับ
    stripped = 0
    max_strip, rx = (3, CLASS_SUFFIX_RE_FX) if fixed else (2, CLASS_SUFFIX_RE)
    while stripped < max_strip and len(parts) >= 3 and rx.match(parts[-1] or ""):
        candidate = parts[:-2]
        if not candidate or not any(p.strip() for p in candidate):
            break
        parts = candidate
        stripped += 1
    fam = "".join(parts).strip()
    return (fam if fam else fc), "suffix"


# ---------------- NAV point lookups (asof, tol=10 calendar days) ----------------

def _prep_arrays(nav_by_fund: dict[str, pd.Series]) -> dict[str, tuple]:
    out = {}
    for fc, s in nav_by_fund.items():
        if len(s) == 0:
            continue
        out[fc] = (s.index.values.astype("datetime64[D]"), s.to_numpy(dtype=float))
    return out


def _asof(dates: np.ndarray, values: np.ndarray, day: np.datetime64, tol_days: int = 10):
    idx = int(np.searchsorted(dates, day, side="right")) - 1
    if idx < 0:
        return np.nan
    d = dates[idx]
    gap = (day - d) / np.timedelta64(1, "D")
    if gap > tol_days:
        return np.nan
    return float(values[idx])


def weekly_points(calendar: pd.DatetimeIndex, t: pd.Timestamp, n: int = 53) -> list[pd.Timestamp]:
    """w_k = วันทำการสุดท้ายของปฏิทินดัชนีในแต่ละสัปดาห์ (ISO week) ที่ <= t · คืน n จุดล่าสุด."""
    cal = calendar[calendar <= t]
    if len(cal) == 0:
        return []
    iso = cal.isocalendar()
    df = pd.DataFrame({"date": cal, "y": iso["year"].to_numpy(), "w": iso["week"].to_numpy()})
    last_per_week = df.groupby(["y", "w"])["date"].max()
    ts = sorted(pd.Timestamp(v) for v in last_per_week.to_numpy())
    return ts[-n:] if len(ts) >= n else ts


def month_end_points(calendar: pd.DatetimeIndex, t: pd.Timestamp, n: int = 13) -> list[pd.Timestamp]:
    """M-12 .. M0 (M0 = เดือนของ t) · คืน n จุดล่าสุด (n=13 -> M-12..M0)."""
    cal = calendar[calendar <= t]
    if len(cal) == 0:
        return []
    grp = pd.Series(cal, index=cal).groupby([cal.year, cal.month]).max()
    ts = sorted(pd.Timestamp(v) for v in grp.to_numpy())
    return ts[-n:] if len(ts) >= n else ts


class QuarterContext:
    """แคช weekly/month-end anchor points + nav arrays สำหรับ t หนึ่งค่า (reuse ข้ามกองใน t เดียวกัน)."""

    def __init__(self, nav_arrays: dict[str, tuple], calendar: pd.DatetimeIndex, t: pd.Timestamp):
        self.nav_arrays = nav_arrays
        self.weeks = weekly_points(calendar, t, 53)
        self.months = month_end_points(calendar, t, 13)
        self._weeks_np = [np.datetime64(w.date()) for w in self.weeks]
        self._months_np = [np.datetime64(m.date()) for m in self.months]

    def fund_signal(self, fc: str) -> dict:
        arrs = self.nav_arrays.get(fc)
        if arrs is None or len(self.months) < 13 or len(self.weeks) < 53:
            return {"R12_1": np.nan, "vol52": np.nan, "SR12": np.nan, "n_week_obs": 0}
        dates, values = arrs
        # month-end prices: months[-1]=M0, months[-2]=M-1, months[0]=M-12
        p_m1 = _asof(dates, values, self._months_np[-2])
        p_m12 = _asof(dates, values, self._months_np[0])
        r12_1 = (p_m1 / p_m12 - 1.0) if (p_m1 == p_m1 and p_m12 not in (0.0,) and p_m12 == p_m12) else np.nan
        # weekly prices -> 52 returns
        wp = np.array([_asof(dates, values, wn) for wn in self._weeks_np], dtype=float)
        with np.errstate(invalid="ignore", divide="ignore"):
            wr = wp[1:] / wp[:-1] - 1.0
        valid = ~np.isnan(wr)
        n_obs = int(valid.sum())
        if n_obs < 40:
            vol52 = np.nan
        else:
            zero_frac = float((wr[valid] == 0.0).mean())
            v = float(np.std(wr[valid], ddof=1)) * np.sqrt(52.0)
            if zero_frac > 0.20 or v < 0.02:
                vol52 = np.nan
            else:
                vol52 = v
        sr12 = np.nan
        if r12_1 == r12_1 and vol52 == vol52 and vol52 > 0:
            sr12 = (r12_1 - RF_ANNUAL_SIGNAL * 11.0 / 12.0) / vol52
        return {"R12_1": r12_1, "vol52": vol52, "SR12": sr12, "n_week_obs": n_obs}

    def weekly_return_series(self, fc: str) -> pd.Series:
        """คืน weekly return series (index=week date, 52 ค่า, อาจมี NaN) สำหรับ Σ/dedupe/vol-target."""
        arrs = self.nav_arrays.get(fc)
        if arrs is None or len(self.weeks) < 2:
            return pd.Series(dtype=float)
        dates, values = arrs
        wp = np.array([_asof(dates, values, wn) for wn in self._weeks_np], dtype=float)
        with np.errstate(invalid="ignore", divide="ignore"):
            wr = wp[1:] / wp[:-1] - 1.0
        return pd.Series(wr, index=self.weeks[1:])


def compute_quarter_signals(qctx: QuarterContext, fund_codes: list[str]) -> pd.DataFrame:
    rows = []
    for fc in fund_codes:
        sig = qctx.fund_signal(fc)
        rows.append({"FundCode": fc, **sig})
    return pd.DataFrame(rows)


def investable_set(t: pd.Timestamp, u_t: pd.DataFrame, signals: pd.DataFrame, groups: dict[str, str],
                   family_fix: bool = False):
    """C2: U_t -> I_t. คืน (df I_t พร้อม family/is_dividend/signal, counts dict สำหรับรายงาน, family_map rows)."""
    df = u_t.merge(signals, on="FundCode", how="left")
    n_u = len(df)
    fresh = (t - df["last_nav_date"]).dt.days <= 10
    n_fresh_cut = int((~fresh).sum())
    df = df[fresh].copy()

    is_tax = df["FundCode"].apply(is_tax_class)
    n_tax_cut = int(is_tax.sum())
    df = df[~is_tax].copy()

    fam_info = df["FundCode"].apply(lambda f: family_of(f, groups, family_fix))
    df["family"] = fam_info.apply(lambda x: x[0])
    df["fam_source"] = fam_info.apply(lambda x: x[1])
    df["is_dividend"] = df["FundCode"].apply(lambda f: is_dividend(f, family_fix))
    family_map_rows = df[["FundCode", "family", "fam_source", "is_dividend"]].copy()
    family_map_rows.insert(0, "t", t)

    nondiv_families = set(df.loc[~df["is_dividend"], "family"])
    drop_div = df["is_dividend"] & df["family"].isin(nondiv_families)
    n_div_dropped = int(drop_div.sum())
    df = df[~drop_div].copy()

    n_before_signal = len(df)
    df = df.dropna(subset=["R12_1", "vol52"]).reset_index(drop=True)
    n_signal_cut = n_before_signal - len(df)

    counts = {"n_universe": n_u, "n_fresh_cut": n_fresh_cut, "n_tax_cut": n_tax_cut,
              "n_div_dropped": n_div_dropped, "n_signal_cut": n_signal_cut, "n_investable": len(df)}
    return df, counts, family_map_rows
