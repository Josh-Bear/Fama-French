"""nav_loader.py — โหลด base_data/nav_history_db.csv (Phase 1) + pivot (Phase 2).

ไฟล์ ~336MB -> อ่านแบบ chunked (config.NAV_CHUNKSIZE) + usecols (config.NAV_USECOLS)
filter เฉพาะ FundCode ที่สนใจตั้งแต่ตอนอ่าน chunk เพื่อลด memory (จาก ~3.0M แถว เหลือ ~0.45M)
ใช้ NAVDate เป็นวันที่หลัก (แก้ปัญหา NAV lag — ดูแผน Phase 2) และ dedupe (FundCode, NAVDate)
โดยเก็บแถวที่ UpdateTime ล่าสุด (confirmed 2026-09-01)

Data cleaning (เพิ่ม 2026-09-09): แก้ NAV ที่กระโดดผิดปกติวันเดียวแล้วเด้งกลับ (single-tick data error,
เช่น KKP SEMICON-H 2026-06-16) **ที่ต้นทาง** ใน load_nav_history() — มีผลกับทั้งระบบที่ต่อจากนี้
(return_21d, ann_return/vol หน้า 1/2, regression R²/primary หน้า 3) ตามที่ตกลงกับผู้ใช้ไว้
รายละเอียดอัลกอริทึม + เหตุผล ดู comment ที่ config.NAV_SPIKE_K

เพิ่ม 2026-09-30: อ่าน UpdateTime ทุกรูปแบบ (parse_update_time) · ตรวจกองเลิก (closed_funds) · ความสดของ NAV
(fund_nav_status) — build_pipeline ใช้ตัดกองแล้วเขียน cache/nav_clean.parquet ให้ขั้นอื่นอ่านแทนไฟล์ดิบ
ส่วนการทิ้ง return ที่คร่อมรูข้อมูลอยู่ที่ analysis/matching.build_fund_returns (ขึ้นกับปฏิทินของดัชนีที่ใช้เทียบ)
"""

from __future__ import annotations

import os

import numpy as np
import pandas as pd

import config


# UpdateTime ในไฟล์มี 3 รูปแบบปนกัน: "YYYY-MM-DD HH:MM:SS.fff" (~97%) · "YYYY-MM-DD HH:MM:SS" · "YYYY-MM-DDTHH:MM:SSZ"
# แบบไม่มี Z เป็นเวลาท้องถิ่น (ชั่วโมงอยู่ในเวลาทำการไทย) · แบบ Z เป็น UTC -> แปลงเป็นเวลาไทยก่อนเทียบกัน
_LOCAL_TZ = "Asia/Bangkok"


def parse_update_time(s: pd.Series) -> pd.Series:
    """UpdateTime (string หลายรูปแบบ) -> datetime เวลาไทยแบบ naive · parse ไม่ได้ = NaT.

    เดิมใช้ pd.to_datetime(errors="coerce") ตรงๆ ซึ่งเดารูปแบบจากแถวแรกแล้วแถวรูปแบบอื่นกลายเป็น NaT เงียบๆ
    (~3% ของแถว) — NaT แพ้ตอน dedupe จึงอาจเลือก revision เก่าผิดตัวได้ (ตรวจแล้วตอนนี้ยังไม่มีคู่ไหนเลือกต่างกัน)
    """
    s = s.astype("string").str.strip()
    is_utc = s.str.endswith("Z", na=False)
    out = pd.to_datetime(s.where(~is_utc), format="ISO8601", errors="coerce")
    if is_utc.any():
        utc = pd.to_datetime(s.where(is_utc), format="ISO8601", errors="coerce", utc=True)
        out = out.where(~is_utc, utc.dt.tz_convert(_LOCAL_TZ).dt.tz_localize(None))
    return out


def load_nav_history(fund_codes: list[str]) -> pd.DataFrame:
    """อ่าน nav_history_db.csv แบบ chunked, เก็บเฉพาะ fund_codes -> NAV ที่ clean แล้ว (ดู load_nav_history_full)."""
    return load_nav_history_full(fund_codes)[0]


def load_nav_history_full(fund_codes: list[str]) -> tuple[pd.DataFrame, set[str], pd.DataFrame]:
    """อ่าน nav_history_db.csv แบบ chunked, เก็บเฉพาะ fund_codes -> (NAV clean แล้ว, กองที่เลิกแล้ว, log ของ spike ที่แก้).

    dedupe (FundCode, NAVDate) -> เก็บแถว UpdateTime ล่าสุด.
    แก้ NAV spike (single-tick data error) ที่ต้นทางก่อนคืนค่า (ดู clean_nav_spikes).
    คืน long-form sort แล้ว: columns = [FundCode, NAVDate(datetime), NAV(float), AUM(float)]
    กองที่เลิกแล้ว = มีแถว NAV ≤ 0 / ว่าง **หลัง** วันสุดท้ายที่ NAV ใช้ได้ (เช่น PRINCIPAL GEF-X: NAV = 0 ทุกแถวหลัง ม.ค. 2026)
    """
    want = set(fund_codes)
    parts: list[pd.DataFrame] = []
    reader = pd.read_csv(
        config.NAV_HISTORY_CSV,
        usecols=config.NAV_USECOLS,
        dtype={config.NAV_FUND_CODE_COL: str},
        chunksize=config.NAV_CHUNKSIZE,
    )
    for chunk in reader:
        chunk[config.NAV_FUND_CODE_COL] = chunk[config.NAV_FUND_CODE_COL].str.strip()
        sub = chunk[chunk[config.NAV_FUND_CODE_COL].isin(want)]
        if len(sub):
            parts.append(sub)

    if not parts:
        return pd.DataFrame(columns=[config.NAV_FUND_CODE_COL, config.NAV_DATE_COL,
                                     config.NAV_COL, config.NAV_AUM_COL]), set(), pd.DataFrame()

    nav = pd.concat(parts, ignore_index=True)
    nav[config.NAV_DATE_COL] = pd.to_datetime(nav[config.NAV_DATE_COL], errors="coerce")
    nav[config.NAV_COL] = pd.to_numeric(nav[config.NAV_COL], errors="coerce")
    nav[config.NAV_AUM_COL] = pd.to_numeric(nav[config.NAV_AUM_COL], errors="coerce")
    closed = closed_funds(nav)

    # ตัดแถว NAV เสีย/ว่าง (NAV<=0 = กองยังไม่เปิด/ระงับ, ทำ pct_change เป็น inf/−100% ปลอม) **ก่อน** dedupe
    # -> ถ้าแถว UpdateTime ล่าสุดบังเอิญ NAV เสีย จะไม่ทิ้ง NAVDate นั้นทั้งจุด แต่ให้แถวเก่ากว่าที่ NAV ใช้ได้ชนะแทน
    nav = nav.dropna(subset=[config.NAV_DATE_COL, config.NAV_COL])
    nav = nav[nav[config.NAV_COL] > 0]

    # dedupe: เก็บแถว UpdateTime ล่าสุด ต่อ (FundCode, NAVDate)
    # na_position="first" -> UpdateTime ที่ parse ไม่ได้ (NaT) เรียงหน้า, keep="last" จึงเลือกแถวที่มี timestamp จริงล่าสุด
    # kind="stable" -> ผล tie-break คงที่ทุกครั้งที่รัน (reproducible) เมื่อ UpdateTime เท่ากันเป๊ะ/NaT ทั้งคู่
    nav["_upd"] = parse_update_time(nav[config.NAV_UPDATE_COL])
    nav = nav.sort_values("_upd", na_position="first", kind="stable")
    nav = nav.drop_duplicates(subset=[config.NAV_FUND_CODE_COL, config.NAV_DATE_COL], keep="last")

    out = nav[[config.NAV_FUND_CODE_COL, config.NAV_DATE_COL, config.NAV_COL, config.NAV_AUM_COL]]
    out = out.sort_values([config.NAV_FUND_CODE_COL, config.NAV_DATE_COL]).reset_index(drop=True)

    out, log_df = clean_nav_spikes(out)
    if len(log_df):
        os.makedirs(config.CACHE_DIR, exist_ok=True)
        log_path = os.path.join(config.CACHE_DIR, "nav_spike_fixes.csv")
        log_df.to_csv(log_path, index=False)
        print(f"[nav_loader] แก้ NAV spike (single-tick data error) {len(log_df)} จุด "
              f"({log_df[config.NAV_FUND_CODE_COL].nunique()} กอง) — log ที่ {log_path}")

    return out.sort_values([config.NAV_FUND_CODE_COL, config.NAV_DATE_COL]).reset_index(drop=True), closed, log_df


def closed_funds(raw: pd.DataFrame) -> set[str]:
    """กองที่เลิกแล้ว: มีแถว NAV ≤ 0 / ว่าง ลงวันที่ **หลัง** วันสุดท้ายที่ NAV ใช้ได้ (ต้องส่งแถวดิบก่อนตัด NAV เสีย).

    NAV = 0 ต่อท้ายคือสัญญาณเลิกกอง/ชำระบัญชี — ต่างจากกองที่แค่ข้อมูลขาดช่วง (ไม่มีแถวเลย) ซึ่งตัดสินด้วยเกณฑ์ความสด
    """
    fund, date, nav_col = config.NAV_FUND_CODE_COL, config.NAV_DATE_COL, config.NAV_COL
    raw = raw.dropna(subset=[date])
    valid = raw[nav_col] > 0
    last_ok = raw[valid].groupby(fund)[date].max()
    bad = raw[~valid]
    after = bad[date] > bad[fund].map(last_ok)          # กองที่ไม่มี NAV ใช้ได้เลย -> NaN -> False (ไม่นับว่าเลิก)
    return set(bad.loc[after, fund])


def fund_nav_status(nav_long: pd.DataFrame, as_of, closed: set[str] | None = None,
                    max_days: int | None = None) -> pd.DataFrame:
    """ความสดของ NAV ต่อกอง -> DataFrame(index=FundCode)[last_nav, days_behind, status].

    as_of    : วันล่าสุดของดัชนีที่ใช้เทียบ (MSCI) · days_behind = as_of − NAVDate ล่าสุด (วันปฏิทิน · ติดลบ = ใหม่กว่า)
    status   : "closed" (อยู่ใน closed) > "stale" (days_behind > max_days) > "keep"
    """
    max_days = config.NAV_STALE_MAX_DAYS if max_days is None else max_days
    last = nav_long.groupby(config.NAV_FUND_CODE_COL)[config.NAV_DATE_COL].max()
    out = pd.DataFrame({"last_nav": last, "days_behind": (pd.Timestamp(as_of) - last).dt.days})
    out["status"] = np.where(out.index.isin(list(closed or ())), "closed",
                             np.where(out["days_behind"] > max_days, "stale", "keep"))
    return out


def _detect_and_fix_spikes(nav_values: np.ndarray, k_spike: float | None = None,
                            k_roundtrip: float | None = None, window: int | None = None
                            ) -> tuple[np.ndarray, list[int]]:
    """ตรวจ+แก้ NAV กระโดดวันเดียวแล้วเด้งกลับ (single-tick data error) ของกองเดียว (sorted ตามวันแล้ว).

    Hampel-filter-style: ที่แต่ละจุด i (interior) ให้ r_in = log-return ขาเข้า (i-1->i),
    r_out = log-return ขาออก (i->i+1) ใช้ median/MAD ของ log-return ใกล้เคียง (window จุด, ไม่รวม
    r_in/r_out เอง) เป็น baseline ปกติเฉพาะที่ -> ตัดว่าเป็น data error ถ้าเข้าเงื่อนไขครบ 3 อย่าง:
      1) ทั้ง r_in และ r_out เบี่ยงจาก median เกิน k_spike เท่าของ mad (สุดโต่งทั้ง 2 ขา)
      2) r_in กับ r_out สัญญาณตรงข้ามกัน (ไป-กลับ ไม่ใช่ trend จริง)
      3) ผลรวม r_in+r_out เบี่ยงจาก 2×median ไม่เกิน k_roundtrip เท่าของ mad (กลับสู่ปกติจริง ไม่ทิ้ง shift ค้าง)
    แก้ด้วย geometric interpolation: nav[i] = sqrt(nav[i-1] × nav[i+1])

    คืน (fixed_values, flagged_positions) — flagged_positions เป็น index (0-based) ใน nav_values ที่ถูกแก้
    ไม่มีการ recompute log-return หลังแก้แต่ละจุด (จุดที่ถูกแก้เป็น single-tick แยกกัน ไม่ติดกัน
    ตามที่ validate กับข้อมูลจริงแล้ว — ถ้าเจอ 2 จุดติดกันในทางทฤษฎี จะข้ามจุดที่ 2 ไปเช็คในรอบถัดไปแทน)
    """
    k_spike = config.NAV_SPIKE_K if k_spike is None else k_spike
    k_roundtrip = config.NAV_SPIKE_ROUNDTRIP_K if k_roundtrip is None else k_roundtrip
    window = config.NAV_SPIKE_WINDOW if window is None else window

    v = nav_values.astype(float)
    n = len(v)
    if n < 5:
        return v, []

    log_r = np.diff(np.log(v))  # length n-1; log_r[j] = log(v[j+1]/v[j])
    flagged: list[int] = []

    for i in range(1, n - 1):
        r_in, r_out = log_r[i - 1], log_r[i]

        lo, hi = max(0, i - 1 - window), min(n - 1, i + window)
        neighbor_idx = [j for j in range(lo, hi) if j not in (i - 1, i)]
        if len(neighbor_idx) < 5:
            continue
        local = log_r[neighbor_idx]
        med = float(np.median(local))
        mad = float(np.median(np.abs(local - med))) * 1.4826
        if mad <= 1e-12:
            continue  # ช่วงนี้แทบไม่ขยับเลย (mad~0) -> เกณฑ์ inflate ผิดปกติ ข้ามไปกันกันตัดสินพลาด

        both_extreme = abs(r_in - med) > k_spike * mad and abs(r_out - med) > k_spike * mad
        opposite_sign = r_in * r_out < 0
        reverts = abs((r_in + r_out) - 2 * med) < k_roundtrip * mad
        if both_extreme and opposite_sign and reverts:
            flagged.append(i)

    if not flagged:
        return v, []

    fixed = v.copy()
    for i in flagged:
        fixed[i] = np.sqrt(v[i - 1] * v[i + 1])
    return fixed, flagged


def clean_nav_spikes(nav_long: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """แก้ NAV spike (single-tick data error) ทีละกอง ทั้ง long-form dataframe (ดู _detect_and_fix_spikes).

    คืน (fixed_df, log_df) — fixed_df = nav_long เดิมแต่แก้คอลัมน์ NAV ตรงจุดที่ตรวจพบ
    log_df = รายการจุดที่แก้ [FundCode, NAVDate, nav_before, nav_after] (ว่างถ้าไม่พบเลย)
    """
    fund_col, date_col, nav_col = config.NAV_FUND_CODE_COL, config.NAV_DATE_COL, config.NAV_COL
    fixed_parts: list[pd.DataFrame] = []
    log_rows: list[dict] = []

    for fund_code, g in nav_long.groupby(fund_col, sort=False):
        g = g.sort_values(date_col)
        fixed_vals, flagged = _detect_and_fix_spikes(g[nav_col].to_numpy())
        if flagged:
            dates = g[date_col].to_numpy()
            orig_vals = g[nav_col].to_numpy()
            for i in flagged:
                log_rows.append({
                    fund_col: fund_code,
                    date_col: dates[i],
                    "nav_before": float(orig_vals[i]),
                    "nav_after": float(fixed_vals[i]),
                })
            g = g.copy()
            g[nav_col] = fixed_vals
        fixed_parts.append(g)

    fixed_df = pd.concat(fixed_parts, ignore_index=True) if fixed_parts else nav_long.copy()
    log_df = pd.DataFrame(log_rows, columns=[fund_col, date_col, "nav_before", "nav_after"])
    return fixed_df, log_df


def nav_point_counts(nav_long: pd.DataFrame) -> pd.Series:
    """จำนวนจุดข้อมูล (distinct NAVDate) ต่อกอง — ใช้คัดกองที่ผ่าน threshold (> config.MIN_DATA_POINTS)."""
    return nav_long.groupby(config.NAV_FUND_CODE_COL)[config.NAV_DATE_COL].nunique()


def funds_passing_threshold(nav_long: pd.DataFrame) -> list[str]:
    """list กองที่มีจุดข้อมูล NAVDate มากกว่า config.MIN_DATA_POINTS (คาด 368 จาก 680).

    หมายเหตุ: นับ NAVDate ทั้ง history — ยังไม่รับประกันจำนวนจุด "ในช่วง MSCI" (2021+)
    ดังนั้น build_pipeline มี guard MIN_REGRESSION_OBS + try/except ต่อกองอีกชั้น (ดู data_access)
    """
    cnt = nav_point_counts(nav_long)
    return sorted(cnt[cnt > config.MIN_DATA_POINTS].index)
