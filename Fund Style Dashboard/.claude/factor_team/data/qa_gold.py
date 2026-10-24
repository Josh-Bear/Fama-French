"""qa_gold.py — งาน GOLD-QA (BRIEF 120): ตรวจเชิงบรรยายว่าทำไมกองทองใน U_O (7 หน่วย) อธิบายด้วย GOLD_XS + FX ได้ R²_oos ~0.48 รายสัปดาห์แต่ ~0.84 รายเดือน

รัน:  cd "<root>" && PYTHONDONTWRITEBYTECODE=1 ./.venv/bin/python -I -B .claude/factor_team/data/qa_gold.py [--out DIR]
- ไม่ใช่ spec เต็ม · ไม่นับ trial · ไม่ fit ชุด factor ใหม่เพื่อแข่ง · ทุกตัวเลขเป็น "การสำรวจหลังเห็นผล S012 (บรรยาย)" ไม่ใช่ผลตัดสิน
- อ่านอย่างเดียว: base_data/nav_history_db.csv (chunk · ผ่าน build_l0.load_nav ของทีมสำหรับ NAV · + รอบอ่านเพิ่มเฉพาะ AsOfDate/UpdateTime) · panel / factors L0 · factors_eo_noaqr_* (ไม่ใช้ไฟล์ที่มี AQR)
  · external/EO_ALT_ETF.csv (GLD รายวัน) · base_data/MACRO_FACTOR.csv (GC=F · USDTHB รายวัน) · runs/S012/fund_level_O.csv + monthly.csv (เทียบฐาน)
- ใช้ lib ของทีมแบบอ่านอย่างเดียว (regress.ols_hac / r2_oos / l1eo.splice_*) · ไม่เขียนไฟล์นอก --out (ค่าเริ่มต้น = โฟลเดอร์ data/)
- ผลเหมือนเดิมทุกบิต (CSV ไม่มีวันที่สร้าง · qa_gold_check.json มี sha256 ของทุกผลลัพธ์ + สคริปต์ · ฟิลด์ created ฟิลด์เดียวเปลี่ยนตามเวลา)
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import date

sys.dont_write_bytecode = True

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
TEAM = os.path.join(ROOT, ".claude", "factor_team")
for p in (ROOT, HERE, os.path.join(TEAM, "lib")):
    sys.path.insert(0, p)

OUT = HERE
if "--out" in sys.argv:
    OUT = os.path.abspath(sys.argv[sys.argv.index("--out") + 1])
    os.makedirs(OUT, exist_ok=True)

import config  # noqa: E402
import build_l0 as L0  # noqa: E402   (import เฉยๆ ไม่รัน main)
import io_l1  # noqa: E402
import l1eo  # noqa: E402
import regress as rg  # noqa: E402
from samples import window_mask  # noqa: E402

CHECK = {}
OUTFILES = []
TRAIN_END, TEST_START = pd.Timestamp("2023-12-31"), pd.Timestamp("2024-01-01")
MAIN_LO, MAIN_HI = pd.Timestamp("2021-01-01"), pd.Timestamp("2025-12-31")


def save_csv(df: pd.DataFrame, name: str, **kw):
    p = os.path.join(OUT, name)
    df.to_csv(p, index=False, float_format="%.10g", **kw)
    OUTFILES.append(name)
    return p


def sha(path):
    return L0.sha256(path)


# ═════════════════════════════════════════════════════ 0) ข้อมูลและฐานเทียบ S012
g = l1eo.load_group_map()
gold_rows = g[(g["policy"] == "O") & (g["o_group"] == "ทอง")]
GOLD_CODES = list(gold_rows["FundCode"])                      # 8 รหัส (I-GOLD + IGOLD-G = หน่วย I-GOLD*)
GOLD_U = sorted(gold_rows["unit"].unique())                    # 7 หน่วย
FXFLAG = gold_rows.drop_duplicates("unit").set_index("unit")["fx_risk_flag"].to_dict()
assert len(GOLD_CODES) == 8 and len(GOLD_U) == 7

F = io_l1.load_factors("W")
Fm = io_l1.load_factors("M")
Feo = pd.read_parquet(os.path.join(HERE, "factors_eo_noaqr_weekly.parquet")).loc[io_l1.MAIN_START:io_l1.MAIN_END].copy()
Feom = pd.read_parquet(os.path.join(HERE, "factors_eo_noaqr_monthly.parquet")).loc[io_l1.MONTH_START:io_l1.MONTH_END].copy()
assert not any("AQR" in c.upper() for c in Feo.columns)
assert (F.index == Feo.index).all() and (Fm.index == Feom.index).all()

ALLC = list(g["FundCode"])
Rc = io_l1.load_returns("W")[ALLC]
Rmc = io_l1.load_returns("M")[ALLC]
R, SPL = l1eo.splice_units(Rc)
Rm = l1eo.splice_monthly(Rmc)
IDX = R.index
mtr = window_mask(IDX, "train")
mte = window_mask(IDX, "test")
midx = Rm.index
MM_TR = np.asarray(midx <= pd.Timestamp("2023-12-31"))
MM_TE = np.asarray(midx >= pd.Timestamp("2024-01-31"))

GOLD_W = pd.DataFrame({"GOLD_XS": Feo["GLD_USD"] - F["SHV_USD"], "FX": F["SHV_THB"] - F["RF_BOT"]})
GOLD_M = pd.DataFrame({"GOLD_XS": Feom["GLD_USD"] - Fm["SHV_USD"], "FX": Fm["SHV_THB"] - Fm["RF_BOT"]})


def lagged(df: pd.DataFrame, lags) -> pd.DataFrame:
    """คอลัมน์ [f_l{l} ...] ตามลำดับ lags · l>0 = ค่าที่ t−l (Dimson) · l<0 = ค่าที่ t+|l| (lead) · l=0 ชื่อเดิม"""
    parts = []
    for l in lags:
        d = df.shift(l)
        d.columns = [c if l == 0 else f"{c}_l{l}" for c in df.columns]
        parts.append(d)
    return pd.concat(parts, axis=1)


def fit_eval(y: pd.Series, X: pd.DataFrame, tr: np.ndarray, te: np.ndarray, min_obs=52, L=4):
    """OLS (HAC ไม่ใช้กับ R²) บน train → R²_oos บน test โดยไม่ fit ใหม่ · คืน dict(n_train, n_test, adj_r2_train, r2_train, r2_oos, coef, names)"""
    yv = y.to_numpy(float)
    Xv = X.to_numpy(float)
    ok = np.isfinite(yv) & np.isfinite(Xv).all(axis=1)
    mk = tr & ok
    n = int(mk.sum())
    if n < max(min_obs, Xv.shape[1] + 3):
        return None
    r = rg.ols_hac(yv[mk], np.column_stack([np.ones(n), Xv[mk]]), L)
    mt = te & ok
    yh = rg.predict_oos(r["coef"], Xv[mt]) if mt.sum() else np.array([])
    return dict(n_train=n, n_test=int(mt.sum()), adj_r2_train=r["adj_r2"], r2_train=r["r2"],
                r2_oos=rg.r2_oos(yv[mt], yh) if mt.sum() >= 2 else np.nan, coef=r["coef"], names=list(X.columns))


def med(x):
    x = np.asarray([v for v in x if v is not None and np.isfinite(v)], float)
    return float(np.median(x)) if len(x) else np.nan


# ── ตรวจฐาน: ทำซ้ำ O-X ทอง (GOLD_XS + FX · Dimson lag 0+1) ให้ตรง runs/S012/fund_level_O.csv และ monthly.csv
FL = pd.read_csv(os.path.join(TEAM, "runs", "S012", "fund_level_O.csv"))
FLG = FL[(FL["row"] == "O-X") & (FL["group"] == "ทอง")].set_index("unit")
base_w = {}
for u in GOLD_U:
    base_w[u] = fit_eval(R[u], lagged(GOLD_W, [0, 1]), mtr, mte)
d_oos = max(abs(base_w[u]["r2_oos"] - FLG.loc[u, "r2_oos"]) for u in GOLD_U)
d_adj = max(abs(base_w[u]["adj_r2_train"] - FLG.loc[u, "adj_r2"]) for u in GOLD_U)
assert d_oos < 1e-9 and d_adj < 1e-9, (d_oos, d_adj)
base_m = {u: fit_eval(Rm[u], lagged(GOLD_M, [0, 1]), MM_TR, MM_TE, min_obs=24, L=3) for u in GOLD_U}
MON = pd.read_csv(os.path.join(TEAM, "runs", "S012", "monthly.csv")).set_index("row").loc["O-X(ทอง)"]
mm = med([base_m[u]["r2_oos"] for u in GOLD_U if base_m[u]])
assert abs(mm - MON["r2oos_med_monthly"]) < 1e-9, (mm, MON["r2oos_med_monthly"])
CHECK["baseline"] = dict(weekly_max_abs_diff_r2_oos=d_oos, weekly_max_abs_diff_adj_r2=d_adj, weekly_median_r2_oos=med([base_w[u]["r2_oos"] for u in GOLD_U]),
                         monthly_median_r2_oos=mm, monthly_median_s012=float(MON["r2oos_med_monthly"]), note="ทำซ้ำ S012 O-X(ทอง) ได้ตรง (< 1e-9)")

# ═════════════════════════════════════════════════════ 1) NAV จริงของกองทอง (อ่านอย่างเดียว)
EXT_CODES = ["KT-GOLDUH-A", "UOBSG - H", "UOBSG-D", "KF-GOLD", "KF-HGOLD", "SCBGOLD", "SCBGOLDH", "ES-GOLDBULLION-H", "ES-GOLDBULLION-UH", "ES-GOLD",
             "ES-GOLDS", "LHGOLD-A", "GOLD-RMF-A", "PGOLD", "ASP-GOLD", "I-GOLDRMF"]
ALL_NAV_CODES = GOLD_CODES + EXT_CODES
nav, spk, nst = L0.load_nav(ALL_NAV_CODES)     # ตัวอ่าน chunk ของทีม: drop NAV≤0/NaN → dedupe (code, NAVDate) UpdateTime ล่าสุด → clean_nav_spikes
CHECK["nav_load"] = dict(**{k: int(v) for k, v in nst.items()}, spike_points_gold_codes=int(spk[spk[config.NAV_FUND_CODE_COL].isin(GOLD_CODES)].shape[0]) if len(spk) else 0)

# รอบอ่านเพิ่ม: เฉพาะ AsOfDate / UpdateTime ของรหัสทองใน U_O (อ่านอย่างเดียว)
parts = []
for ch in pd.read_csv(config.NAV_HISTORY_CSV, usecols=["AsOfDate", "FundCode", "NAV", "NAVDate", "UpdateTime"], dtype={"FundCode": str}, chunksize=config.NAV_CHUNKSIZE):
    ch["FundCode"] = ch["FundCode"].str.strip()
    s = ch[ch["FundCode"].isin(set(GOLD_CODES))]
    if len(s):
        parts.append(s)
RAW = pd.concat(parts, ignore_index=True)
RAW["AsOfDate"] = pd.to_datetime(RAW["AsOfDate"], errors="coerce")
RAW["NAVDate"] = pd.to_datetime(RAW["NAVDate"], errors="coerce")
RAW["upd"] = L0.nav_loader.parse_update_time(RAW["UpdateTime"])
RAW["NAV"] = pd.to_numeric(RAW["NAV"], errors="coerce")
RAW = RAW.dropna(subset=["AsOfDate", "NAVDate"])
RAW = RAW[(RAW["NAVDate"] >= MAIN_LO) & (RAW["NAVDate"] <= MAIN_HI)]


def bd(a, b):
    """จำนวนวันทำการ (จันทร์–ศุกร์) จาก a ถึง b (b − a)"""
    return np.busday_count(a.values.astype("datetime64[D]"), b.values.astype("datetime64[D]"))


navm = nav[(nav[config.NAV_DATE_COL] >= MAIN_LO) & (nav[config.NAV_DATE_COL] <= MAIN_HI)]
ND = {c: pd.DatetimeIndex(sorted(navm.loc[navm[config.NAV_FUND_CODE_COL] == c, config.NAV_DATE_COL].unique())) for c in ALL_NAV_CODES}
WD = pd.bdate_range("2021-01-04", MAIN_HI)                                                   # วันจันทร์–ศุกร์ทั้งหมดในช่วงหลัก
REF = ["BGOLD", "TGOLD", "PRINCIPAL iGOLD-A", "K-GOLD-A(A)", "KT-GOLD"]
cnt = pd.Series(0, index=WD)
for c in REF:
    cnt = cnt.add(pd.Series(1, index=ND[c]).reindex(WD).fillna(0), fill_value=0)
GAP_LO, GAP_HI = pd.Timestamp("2023-12-11"), pd.Timestamp("2025-12-31")   # ช่วงที่ nav_history_db ไม่มี snapshot AsOfDate วันศุกร์ (ดู qa_gold_db_weekday.csv)
THAI_DAYS = WD[(cnt >= 3).to_numpy()]
# ในช่วงที่ไม่มี snapshot วันศุกร์ กอง NAVDate=AsOfDate (5 กองอ้างอิง) ไม่มี NAV วันศุกร์ → นับวันศุกร์เป็นวันทำการไทยถ้า UOBSG-N (NAVDate = AsOfDate − 1 วันทำการ) มี NAVDate วันนั้น
extra = [d for d in WD if GAP_LO <= d <= GAP_HI and d.dayofweek == 4 and d in set(ND["UOBSG-N"])]
THAI_DAYS = THAI_DAYS.union(pd.DatetimeIndex(extra))
THAI_HOL = WD.difference(THAI_DAYS)

alt = pd.read_csv(os.path.join(HERE, "external", "EO_ALT_ETF.csv"), parse_dates=["Date"]).set_index("Date").sort_index()
GLD_LV = alt["GLD"].dropna()
NY_DAYS = pd.DatetimeIndex([d for d in WD if d in GLD_LV.index])
NY_HOL = WD.difference(NY_DAYS)
mac = pd.read_csv(config.MACRO_FACTOR_CSV, parse_dates=["Date"]).set_index("Date").sort_index()
GC_LV = mac["Gold"].dropna()
FXD_LV = mac["USDTHB"].dropna()

cal = []
for y in range(2021, 2026):
    w = WD[WD.year == y]
    th = THAI_HOL[THAI_HOL.year == y]
    ny = NY_HOL[NY_HOL.year == y]
    cal.append(dict(year=y, weekdays=len(w), thai_nonnav_days=len(th), ny_closed_days=len(ny), thai_only=len(th.difference(ny)), ny_only=len(ny.difference(th)), both=len(th.intersection(ny)),
                    thai_only_dates=";".join(f"{d:%m-%d}" for d in th.difference(ny)), ny_only_dates=";".join(f"{d:%m-%d}" for d in ny.difference(th))))
CAL = pd.DataFrame(cal)
save_csv(CAL, "qa_gold_calendar.csv")
CHECK["calendar"] = dict(ref_funds=REF, rule="วัน Thai = วันจันทร์–ศุกร์ที่ ≥ 3 ใน 5 กองอ้างอิงมี NAVDate (+ วันศุกร์ 2023-12-11→2025-12-31 ที่ UOBSG-N มี NAVDate) · วัน NY = วันที่ GLD มีราคา (Yahoo)",
                         n_thai_days=len(THAI_DAYS), n_thai_holidays_est=len(THAI_HOL), n_ny_closed=len(NY_HOL))

# ตารางต่อรหัส: ความถี่ NAV · NAVDate vs AsOfDate vs UpdateTime · NAV ค้าง
rows = []
for c in GOLD_CODES:
    nd = ND[c]
    first, last = (nd.min(), nd.max()) if len(nd) else (pd.NaT, pd.NaT)
    thai_in = THAI_DAYS[(THAI_DAYS >= first) & (THAI_DAYS <= last)]
    has = pd.Series(thai_in.isin(nd), index=thai_in)
    ny_in = NY_DAYS[(NY_DAYS >= first) & (NY_DAYS <= last)]
    rw = RAW[RAW["FundCode"] == c]
    gap_as = bd(rw["NAVDate"], rw["AsOfDate"])
    gap_up = bd(rw["NAVDate"], rw["upd"].dt.normalize().fillna(rw["AsOfDate"]))
    dup = rw.duplicated(["NAVDate"], keep=False)
    # NAV ค้าง = แถวที่ NAVDate ซ้ำกับแถวก่อนหน้า (ข้อมูลวันใหม่แต่ NAVDate เดิม)
    stale_rows = int(rw.duplicated(["NAVDate"], keep="first").sum())
    nv = navm[navm[config.NAV_FUND_CODE_COL] == c].sort_values(config.NAV_DATE_COL)
    r_ = nv[config.NAV_COL].pct_change().iloc[1:]
    rows.append(dict(code=c, unit=l1eo.code_to_unit().get(c, c), fx_risk_flag=FXFLAG[l1eo.code_to_unit().get(c, c)], nav_first=f"{first:%Y-%m-%d}", nav_last=f"{last:%Y-%m-%d}",
                     n_navdates=len(nd), n_thai_days_in_span=len(thai_in), thai_day_coverage=float(has.mean()) if len(has) else np.nan,
                     n_missing_thai_days=int((~has).sum()),
                     miss_ny_closed=int(sum(1 for d in has.index[~has.to_numpy()] if d in set(NY_HOL))),
                     miss_gapwindow_friday=int(sum(1 for d in has.index[~has.to_numpy()] if d.dayofweek == 4 and GAP_LO <= d <= GAP_HI and d not in set(NY_HOL))),
                     miss_gapwindow_thursday=int(sum(1 for d in has.index[~has.to_numpy()] if d.dayofweek == 3 and GAP_LO <= d <= GAP_HI and d not in set(NY_HOL))),
                     miss_other=int(sum(1 for d in has.index[~has.to_numpy()] if d not in set(NY_HOL) and not (GAP_LO <= d <= GAP_HI and d.dayofweek in (3, 4)))), n_navdate_on_thai_holiday=int(nd.isin(THAI_HOL).sum()), n_navdate_on_ny_closed=int(nd.isin(NY_HOL).sum()),
                     n_ny_days_in_span=len(ny_in), n_ny_days_without_nav=int((~ny_in.isin(nd)).sum()),
                     raw_rows=len(rw), raw_rows_repeated_navdate=stale_rows, frac_rows_repeated_navdate=stale_rows / max(len(rw), 1),
                     asof_minus_navdate_bd0=float(np.mean(gap_as == 0)), asof_minus_navdate_bd1=float(np.mean(gap_as == 1)), asof_minus_navdate_bd2plus=float(np.mean(gap_as >= 2)),
                     asof_minus_navdate_bd0_pre=float(np.mean(gap_as[(rw["NAVDate"] <= GAP_LO).to_numpy()] == 0)) if (rw["NAVDate"] <= GAP_LO).any() else np.nan,
                     asof_minus_navdate_bd0_gap=float(np.mean(gap_as[(rw["NAVDate"] >= GAP_LO).to_numpy()] == 0)) if (rw["NAVDate"] >= GAP_LO).any() else np.nan,
                     friday_navdates_pre=int(((nd.dayofweek == 4) & (nd <= GAP_LO)).sum()), friday_navdates_gap=int(((nd.dayofweek == 4) & (nd >= GAP_LO)).sum()),
                     thursday_navdates_gap=int(((nd.dayofweek == 3) & (nd >= GAP_LO)).sum()),
                     n_thai_fridays_in_gap_window=int(((THAI_DAYS.dayofweek == 4) & (THAI_DAYS >= max(GAP_LO, first)) & (THAI_DAYS <= GAP_HI)).sum()),
                     update_minus_navdate_bd_median=float(np.median(gap_up)), update_minus_navdate_bd1=float(np.mean(gap_up == 1)), update_minus_navdate_bd2plus=float(np.mean(gap_up >= 2)),
                     daily_zero_ret_frac=float((r_.abs() < 1e-12).mean()) if len(r_) else np.nan, daily_n_ret=len(r_)))
NAVT = pd.DataFrame(rows)
save_csv(NAVT, "qa_gold_nav_days.csv")

# ความครอบคลุมต่อปี (สัดส่วนวัน Thai ที่มี NAVDate)
rows = []
for c in GOLD_CODES:
    nd = ND[c]
    for y in range(2021, 2026):
        t = THAI_DAYS[THAI_DAYS.year == y]
        t = t[(t >= nd.min()) & (t <= nd.max())] if len(nd) else t
        rows.append(dict(code=c, year=y, thai_days=len(t), with_nav=int(t.isin(nd).sum()), coverage=float(t.isin(nd).mean()) if len(t) else np.nan))
save_csv(pd.DataFrame(rows), "qa_gold_nav_year.csv")

# ═════════════════════════════════════════════════════ 1b) จุดสิ้นสัปดาห์: NAVDate ที่ asof · NAV ค้าง · วันหยุด
ANCH = pd.date_range("2021-01-01", io_l1.MAIN_END, freq="W-FRI")      # เหมือน L0 (anchor แรก 2021-01-01)
A64 = L0.D(ANCH)
PW = pd.read_parquet(os.path.join(HERE, "panel_weekly.parquet")).pivot(index="date", columns="FundCode", values="ret").sort_index().loc[io_l1.MAIN_START:io_l1.MAIN_END]
gld_w_ret = Feo["GLD_USD"]
hol_fri_th = ANCH[ANCH.isin(THAI_HOL)]
hol_fri_ny = ANCH[ANCH.isin(NY_HOL)]
rows = []
for c in GOLD_CODES:
    nd = D_ = L0.D(ND[c]) if len(ND[c]) else None
    idx = L0.asof_idx(nd, A64)
    ok = idx >= 0
    asof_d = pd.DatetimeIndex(np.where(ok, nd[np.clip(idx, 0, None)], np.datetime64("NaT")))
    gap = (ANCH - asof_d).days
    wk_ret = PW[c].reindex(ANCH[1:]) if c in PW.columns else pd.Series(np.nan, index=ANCH[1:])
    valid = wk_ret.notna()
    # สัปดาห์ NAV ไม่ขยับ (asof NAVDate เหมือนสัปดาห์ก่อน) และ ret = 0
    same_asof = pd.Series(asof_d[1:] == asof_d[:-1], index=ANCH[1:])
    zero = (wk_ret == 0)
    big = gld_w_ret.reindex(ANCH[1:]).abs() > 0.01
    rows.append(dict(code=c, n_anchors=int(ok.sum()), asof_is_friday=float(np.mean(gap[ok] == 0)), asof_thu=float(np.mean(gap[ok] == 1)), asof_wed=float(np.mean(gap[ok] == 2)),
                     asof_older=float(np.mean(gap[ok] >= 3)), n_weekly_ret=int(valid.sum()), n_zero_ret_weeks=int(zero.sum()), frac_zero_ret=float(zero.sum() / max(valid.sum(), 1)),
                     n_same_asof_navdate=int((same_asof & valid.reindex(same_asof.index, fill_value=False)).sum()),
                     n_zero_while_gld_moved_gt1pct=int((zero & big.reindex(zero.index, fill_value=False)).sum()),
                     fridays_thai_holiday=int(sum(1 for a in ANCH[1:] if a in set(hol_fri_th))), fridays_ny_closed=int(sum(1 for a in ANCH[1:] if a in set(hol_fri_ny)))))
save_csv(pd.DataFrame(rows), "qa_gold_weekly_asof.csv")

# ═════════════════════════════════════════════════════ 2) lag รายวัน (NAVDate vs GLD / GC=F / USDTHB)


def prev_wd(d: pd.DatetimeIndex, k=1):
    return pd.DatetimeIndex(np.busday_offset(d.values.astype("datetime64[D]"), -k, roll="forward"))


def daily_ret(level: pd.Series) -> pd.Series:
    """ผลตอบแทนระหว่างวันทำการที่ติดกันเท่านั้น (ทั้งวันนี้ และวันทำการก่อนหน้ามีค่า) · index = วันที่ของค่าปลาย"""
    level = level.dropna()
    d = level.index
    p = prev_wd(d)
    prev = pd.Series(level.reindex(p).to_numpy(), index=d)
    return (level / prev - 1.0).dropna()


GLD_R = daily_ret(GLD_LV)
GC_R = daily_ret(GC_LV)
FXD_R = daily_ret(FXD_LV)


def at_shift(r: pd.Series, idx: pd.DatetimeIndex, k: int) -> pd.Series:
    """ค่า r ของวันทำการที่ก่อน idx k วันทำการ (k>0 = ย้อนหลัง · k<0 = ล่วงหน้า)"""
    s = pd.DatetimeIndex(np.busday_offset(idx.values.astype("datetime64[D]"), -k, roll="forward"))
    return pd.Series(r.reindex(s).to_numpy(), index=idx)


FUND_DR = {}
for c in GOLD_CODES:
    lv = navm.loc[navm[config.NAV_FUND_CODE_COL] == c].set_index(config.NAV_DATE_COL)[config.NAV_COL].sort_index()
    FUND_DR[c] = daily_ret(lv)


def corr_pair(a: pd.Series, b: pd.Series, lo=None, hi=None):
    d = pd.concat([a, b], axis=1).dropna()
    if lo is not None:
        d = d[(d.index >= lo)]
    if hi is not None:
        d = d[(d.index <= hi)]
    return (float(d.iloc[:, 0].corr(d.iloc[:, 1])) if len(d) > 20 else np.nan), len(d)


PER = {"all": (MAIN_LO, MAIN_HI), "2021-2023": (MAIN_LO, TRAIN_END), "2024-2025": (TEST_START, MAIN_HI)}
rows = []
for c in GOLD_CODES:
    r = FUND_DR[c]
    for fac_name, fac in (("GLD_USD", GLD_R), ("GC_F_USD", GC_R), ("USDTHB", FXD_R)):
        for k in (-2, -1, 0, 1, 2):
            f = at_shift(fac, r.index, k)
            for pn, (lo, hi) in PER.items():
                cc, n = corr_pair(r, f, lo, hi)
                rows.append(dict(code=c, factor=fac_name, lag_days=k, period=pn, corr=cc, n=n))
DLAG = pd.DataFrame(rows)
save_csv(DLAG, "qa_gold_lagcorr_daily.csv")
# สรุป lag ที่ corr สูงสุด (GLD) ต่อรหัส/ช่วง
best = DLAG[DLAG["factor"] == "GLD_USD"].sort_values("corr", ascending=False).groupby(["code", "period"], sort=False).head(1)[["code", "period", "lag_days", "corr", "n"]]
save_csv(best.sort_values(["code", "period"]), "qa_gold_daily_bestlag.csv")

# ถดถอยรายวัน (train 2021–2023 → test 2024–2025) · GLD lag 0..2 + USDTHB lag 0..2 · วันที่ครบทุกตัวแปร
rows = []
GLDX = {k: None for k in (0, 1, 2)}
for c in GOLD_CODES:
    r = FUND_DR[c]
    dfx = pd.DataFrame({"y": r})
    for k in (-1, 0, 1, 2):
        dfx[f"g{k}"] = at_shift(GLD_R, r.index, k)
        dfx[f"x{k}"] = at_shift(FXD_R, r.index, k)
    dfx = dfx.dropna()
    trm = (dfx.index <= TRAIN_END)
    tem = (dfx.index >= TEST_START)
    for name, gl in (("d_lag0", [0]), ("d_lag1", [1]), ("d_lag0+1", [0, 1]), ("d_lag0+1+2", [0, 1, 2]), ("d_lead-1+0+1", [-1, 0, 1])):
        X = dfx[[f"g{k}" for k in gl] + [f"x{k}" for k in gl]]
        res = fit_eval(dfx["y"], X, trm, tem, min_obs=100)
        if res is None:
            continue
        cf = dict(zip(res["names"], res["coef"][1:]))
        rows.append(dict(code=c, spec=name, n_train=res["n_train"], n_test=res["n_test"], adj_r2_train=res["adj_r2_train"], r2_oos=res["r2_oos"],
                         **{f"b_gld_lag{k}": cf.get(f"g{k}", np.nan) for k in (-1, 0, 1, 2)}, **{f"b_fx_lag{k}": cf.get(f"x{k}", np.nan) for k in (-1, 0, 1, 2)}))
DDIM = pd.DataFrame(rows)
save_csv(DDIM, "qa_gold_daily_dimson.csv")

# ═════════════════════════════════════════════════════ 2b) lag รายสัปดาห์ (−1, 0, +1, +2) กับ GOLD_XS / ทองบาท (เดิม) / GLD บาท
FAC_W = {"GOLD_XS": GOLD_W["GOLD_XS"], "Gold_THB_orig_minus_RF": F["Gold_THB"] - F["RF_BOT"], "GLD_THB_minus_RF": Feo["GLD_THB"] - F["RF_BOT"], "FX": GOLD_W["FX"]}
rows = []
for u in GOLD_U:
    for fn, fs in FAC_W.items():
        for k in (-1, 0, 1, 2):
            f = fs.shift(k)
            for pn, m_ in (("all", np.ones(len(IDX), bool)), ("2021-2023", mtr), ("2024-2025", mte)):
                d = pd.concat([R[u], f], axis=1)[m_].dropna()
                rows.append(dict(unit=u, fx_risk_flag=FXFLAG[u], factor=fn, lag_weeks=k, period=pn, corr=float(d.iloc[:, 0].corr(d.iloc[:, 1])) if len(d) > 20 else np.nan, n=len(d)))
WLAG = pd.DataFrame(rows)
save_csv(WLAG, "qa_gold_lagcorr_weekly.csv")

# ═════════════════════════════════════════════════════ 2c) เลื่อนจุดอ้างอิงสัปดาห์ของ factor ทีละวันทำการ (s) — ตรวจว่าความต่าง 1 วัน NY อธิบายได้เท่าไร
A_D = ANCH.values.astype("datetime64[D]")


def weekly_ret_shift(lv: pd.Series, s: int) -> pd.Series:
    """ผลตอบแทนรายสัปดาห์ของ level รายวัน ที่จุด (anchor − s วันทำการ) · asof ≤ จุดนั้น ห่างไม่เกิน 10 วัน (เหมือน L0) · index = anchors[1:]"""
    pts = pd.DatetimeIndex(np.busday_offset(A_D, -s, roll="forward"))
    v = L0.asof_series(lv, L0.D(pts))
    return pd.Series(v[1:] / v[:-1] - 1.0, index=ANCH[1:])


def factors_shift(s: int) -> pd.DataFrame:
    gl = weekly_ret_shift(GLD_LV, s)
    fxr = weekly_ret_shift(FXD_LV, s)
    gx = gl - F["SHV_USD"].reindex(gl.index)
    fx = (1 + F["SHV_USD"].reindex(gl.index)) * (1 + fxr) - 1 - F["RF_BOT"].reindex(gl.index)
    return pd.DataFrame({"GOLD_XS": gx, "FX": fx}).reindex(IDX)


chk0 = factors_shift(0)
d_g = float(np.nanmax(np.abs(chk0["GOLD_XS"].to_numpy() - GOLD_W["GOLD_XS"].to_numpy())))
d_f = float(np.nanmax(np.abs(chk0["FX"].to_numpy() - GOLD_W["FX"].to_numpy())))
assert d_g < 1e-9 and d_f < 1e-9, (d_g, d_f)
CHECK["shift0_reproduces_baseline_factors"] = dict(max_abs_diff_GOLD_XS=d_g, max_abs_diff_FX=d_f)
SHIFT = {s: factors_shift(s) for s in (-2, -1, 0, 1, 2)}
rows = []
for u in GOLD_U:
    for s, fdf in SHIFT.items():
        for nm, lg in (("lag0", [0]), ("lag0+1", [0, 1])):
            res = fit_eval(R[u], lagged(fdf, lg), mtr, mte)
            rows.append(dict(unit=u, shift_weekdays=s, spec=nm, adj_r2_train=res["adj_r2_train"], r2_oos=res["r2_oos"]))
SG = pd.DataFrame(rows)
save_csv(SG, "qa_gold_shift_grid.csv")

# ═════════════════════════════════════════════════════ 3) R² ตาม lag spec (weekly · 2 สัปดาห์ · monthly) — การสำรวจหลังเห็นผล
rows = []


def add_spec(freq, spec, u, res, note=""):
    rows.append(dict(freq=freq, spec=spec, unit=u, fx_risk_flag=FXFLAG[u], n_train=res["n_train"] if res else np.nan, n_test=res["n_test"] if res else np.nan,
                     adj_r2_train=res["adj_r2_train"] if res else np.nan, r2_oos=res["r2_oos"] if res else np.nan, note=note))


WSPECS = {"W_lag0": [0], "W_lag0+1 (S012)": [0, 1], "W_lag0+1+2": [0, 1, 2], "W_lead-1+0+1": [-1, 0, 1], "W_lead-1..+2": [-1, 0, 1, 2]}
for nm, lg in WSPECS.items():
    for u in GOLD_U:
        add_spec("weekly", nm, u, fit_eval(R[u], lagged(GOLD_W, lg), mtr, mte))
for u in GOLD_U:   # GOLD_XS ตัวเดียว (ไม่มี FX)
    add_spec("weekly", "W_GOLD_XS only lag0+1+2", u, fit_eval(R[u], lagged(GOLD_W[["GOLD_XS"]], [0, 1, 2]), mtr, mte))
for nm, s in (("W_thuAnchor_lag0", 1), ("W_wedAnchor_lag0", 2)):
    for u in GOLD_U:
        add_spec("weekly", nm, u, fit_eval(R[u], lagged(SHIFT[s], [0]), mtr, mte), note=f"factor เลื่อนจุดอ้างอิง {s} วันทำการ (กองเหมือนเดิม)")
for u in GOLD_U:
    add_spec("weekly", "W_thuAnchor_lag0+1", u, fit_eval(R[u], lagged(SHIFT[1], [0, 1]), mtr, mte), note="factor เลื่อนจุดอ้างอิง 1 วันทำการ")

# 2 สัปดาห์แบบไม่ซ้อน (ผลรวมผลตอบแทนส่วนเกินรายสัปดาห์ — ประมาณแบบบวก) · จัดคู่ 2 แบบ (A เริ่มสัปดาห์ที่ 1 · B เริ่มสัปดาห์ที่ 2) · รายงานทั้งคู่และค่าเฉลี่ย
for tag, off in (("A", 0), ("B", 1)):
    pos = np.arange(off, len(IDX) - 1, 2)          # คู่สัปดาห์ (pos, pos+1)
    ei = IDX[pos + 1]
    R2 = pd.DataFrame({u: R[u].to_numpy()[pos] + R[u].to_numpy()[pos + 1] for u in GOLD_U}, index=ei)
    G2 = pd.DataFrame({c: GOLD_W[c].to_numpy()[pos] + GOLD_W[c].to_numpy()[pos + 1] for c in GOLD_W.columns}, index=ei)
    tr2 = np.asarray(ei <= pd.Timestamp("2023-12-29"))
    te2 = np.asarray(ei >= pd.Timestamp("2024-01-12"))
    for nm, lg in (("2W_lag0", [0]), ("2W_lag0+1", [0, 1])):
        for u in GOLD_U:
            add_spec("2week_nonoverlap", f"{nm}_{tag}", u, fit_eval(R2[u], lagged(G2, lg), tr2, te2, min_obs=30, L=2), note="ผลรวมสัปดาห์ละ 2 สัปดาห์แบบไม่ซ้อน · lag = 2 สัปดาห์")
# รายเดือน
for nm, lg in (("M_lag0", [0]), ("M_lag0+1 (S012)", [0, 1]), ("M_lag0+1+2", [0, 1, 2])):
    for u in GOLD_U:
        add_spec("monthly", nm, u, fit_eval(Rm[u], lagged(GOLD_M, lg), MM_TR, MM_TE, min_obs=24, L=3))
SPEC = pd.DataFrame(rows)
save_csv(SPEC, "qa_gold_r2_specs.csv")
summ = []
for (fq, sp), d in SPEC.groupby(["freq", "spec"], sort=False):
    ex = d[d["unit"] != "UOBSG-N"]
    summ.append(dict(freq=fq, spec=sp, n_units=int(d["r2_oos"].notna().sum()), median_r2_oos_all7=med(d["r2_oos"]), median_r2_oos_ex_UOBSG=med(ex["r2_oos"]),
                     median_adj_r2_train_all7=med(d["adj_r2_train"]), min_r2_oos=float(np.nanmin(d["r2_oos"])) if d["r2_oos"].notna().any() else np.nan,
                     max_r2_oos=float(np.nanmax(d["r2_oos"])) if d["r2_oos"].notna().any() else np.nan))
SUMM = pd.DataFrame(summ)
SUMM.insert(0, "n_specs_tried_total", len(SUMM))
save_csv(SUMM, "qa_gold_r2_specs_summary.csv")

# ═════════════════════════════════════════════════════ 3b) กองสังเคราะห์: NAV = GLD ที่ล่าช้า d วันทำการ (ไม่มี FX · ไม่มีสัญญาณรบกวนอื่น) → เพดาน R² ของ Dimson 1 ช่วง
SYN = []
gl_lv = GLD_LV.copy()
wd_lv = gl_lv.reindex(pd.bdate_range("2020-12-01", "2026-01-31")).ffill()      # ffill วันหยุด NY (ราคาค้าง)
for d_lag in (0, 1, 2):
    sy = wd_lv.shift(d_lag)                                                    # NAV ณ วัน t = ราคา GLD ของ t − d วันทำการ
    # รายสัปดาห์ (Fri→Fri จุดเดียวกับ panel)
    f_w = pd.Series(L0.asof_series(sy, A64), index=ANCH)
    y_w = (f_w / f_w.shift(1) - 1).iloc[1:]
    x_w = Feo["GLD_USD"].reindex(y_w.index).to_frame("GLD")
    for nm, lg in (("lag0", [0]), ("lag0+1", [0, 1]), ("lag0+1+2", [0, 1, 2])):
        res = fit_eval(y_w.reindex(IDX), lagged(x_w.reindex(IDX), lg), mtr, mte)
        SYN.append(dict(freq="weekly", delay_weekdays=d_lag, spec=nm, adj_r2_train=res["adj_r2_train"], r2_oos=res["r2_oos"]))
    # รายสัปดาห์ 2 แบบไม่ซ้อน
    MEs = pd.DatetimeIndex([pd.Timestamp("2020-12-31")] + list(pd.date_range("2021-01-31", io_l1.MONTH_END, freq="ME")))
    f_m = pd.Series(L0.asof_series(sy, L0.D(MEs)), index=MEs)
    y_m = (f_m / f_m.shift(1) - 1).iloc[1:]
    x_m = Feom["GLD_USD"].reindex(y_m.index).to_frame("GLD")
    for nm, lg in (("lag0", [0]), ("lag0+1", [0, 1])):
        res = fit_eval(y_m.reindex(midx), lagged(x_m.reindex(midx), lg), MM_TR, MM_TE, min_obs=24, L=3)
        SYN.append(dict(freq="monthly", delay_weekdays=d_lag, spec=nm, adj_r2_train=res["adj_r2_train"], r2_oos=res["r2_oos"]))
SYNT = pd.DataFrame(SYN)
save_csv(SYNT, "qa_gold_synthetic.csv")

# ═════════════════════════════════════════════════════ 4) hedge / unhedge และคู่กอง (รวมกองนอก U_O · เชิงบรรยาย · ไม่ใช้เลือก)
fp = pd.read_csv(config.FUND_PROFILE_CSV) if hasattr(config, "FUND_PROFILE_CSV") else pd.read_csv(os.path.join(ROOT, "base_data", "FundProfile.csv"))
fpx = fp.set_index(fp["Fund Code"].astype(str).str.strip())
ANCH_ALL = pd.date_range("2021-01-01", io_l1.MAIN_END, freq="W-FRI")
codes_ext = [c for c in EXT_CODES]
Rx, _, metax = L0.fund_returns(nav, codes_ext + GOLD_CODES, ANCH_ALL)
rf_w = F["RF_BOT"]
Rx = Rx.sub(rf_w.reindex(Rx.index), axis=0)
rows = []
for c in [u for u in GOLD_U] + codes_ext:
    y = R[c] if c in GOLD_U else Rx[c].reindex(IDX)
    code0 = c if c in fpx.index else {"I-GOLD*": "I-GOLD"}.get(c, c)
    full = np.ones(len(IDX), bool)
    r0 = fit_eval(y, lagged(GOLD_W, [0, 1]), full, full, min_obs=40)
    r1 = fit_eval(y, lagged(SHIFT[1], [0]), full, full, min_obs=40)
    r2 = fit_eval(y, lagged(SHIFT[1], [0, 1]), full, full, min_obs=40)
    if r0 is None:
        continue
    cf = dict(zip(r0["names"], r0["coef"][1:]))
    cf1 = dict(zip(r1["names"], r1["coef"][1:])) if r1 else {}
    rows.append(dict(code=c, in_U_O=c in GOLD_U, fx_risk_flag=str(fpx.loc[code0, "FX Risk Flag"]) if code0 in fpx.index else "", name_en=str(fpx.loc[code0, "Fund Name EN"]) if code0 in fpx.index else "",
                     lag_allocation_day=fpx.loc[code0, "lag_allocation_day"] if code0 in fpx.index else np.nan,
                     buy_cutoff=fpx.loc[code0, "buy_cut_off_time"] if code0 in fpx.index else np.nan,
                     n_weeks=r0["n_train"], first_week=f"{y.dropna().index.min():%Y-%m-%d}",
                     beta_gold_sum_lag01=cf["GOLD_XS"] + cf["GOLD_XS_l1"], beta_fx_sum_lag01=cf["FX"] + cf["FX_l1"], b_gold_lag0=cf["GOLD_XS"], b_gold_lag1=cf["GOLD_XS_l1"],
                     adj_r2_insample_S012spec=r0["adj_r2_train"], adj_r2_insample_thu_lag0=r1["adj_r2_train"] if r1 else np.nan, adj_r2_insample_thu_lag01=r2["adj_r2_train"] if r2 else np.nan,
                     beta_gold_thu_lag0=cf1.get("GOLD_XS", np.nan), beta_fx_thu_lag0=cf1.get("FX", np.nan)))
HEDGE = pd.DataFrame(rows)
save_csv(HEDGE, "qa_gold_hedge.csv")

# ═════════════════════════════════════════════════════ 5) ผลของสัปดาห์ที่มีวันหยุด (Thai / NY) ต่อ residual ของ S012 O-X
rows = []
wk_end = IDX
wk_start = ANCH[:-1]
hol_flag = []
for a0, a1 in zip(wk_start, wk_end):
    wdw = pd.bdate_range(a0 + pd.Timedelta(days=1), a1)
    th_fri = a1 in THAI_HOL                                   # วันศุกร์ของสัปดาห์เป็นวันหยุดไทย (จุดสิ้นสัปดาห์ต้องถอยไปวันพฤหัส)
    th_mid = any((d in THAI_HOL) and d != a1 for d in wdw)    # หยุดไทยวันอื่นในสัปดาห์
    ny = any(d in NY_HOL for d in wdw)
    hol_flag.append("friday_thai_holiday" if th_fri else ("thai_holiday_other_day" if th_mid else ("ny_closed_only" if ny else "none")))
HF = pd.Series(hol_flag, index=IDX)
for u in GOLD_U:
    res = base_w[u]
    yv = R[u]
    X = lagged(GOLD_W, [0, 1])
    pred = pd.Series(res["coef"][0] + np.nan_to_num(X.to_numpy(float), nan=np.nan) @ res["coef"][1:], index=IDX)
    for pn, m_ in (("2021-2023", mtr), ("2024-2025", mte)):
        for grp in ("none", "friday_thai_holiday", "thai_holiday_other_day", "ny_closed_only"):
            sel = m_ & (HF.to_numpy() == grp) & yv.notna().to_numpy() & pred.notna().to_numpy()
            if sel.sum() < 3:
                continue
            e = (yv[sel] - pred[sel])
            rows.append(dict(unit=u, period=pn, week_type=grp, n=int(sel.sum()), rmse=float(np.sqrt((e ** 2).mean())), mean_abs_err=float(e.abs().mean()),
                             corr_y_pred=float(np.corrcoef(yv[sel], pred[sel])[0, 1]) if sel.sum() > 5 else np.nan))
HOLE = pd.DataFrame(rows)
save_csv(HOLE, "qa_gold_holiday_effect.csv")
CHECK["week_types"] = {k: int(v) for k, v in HF.value_counts().items()}

# ═════════════════════════════════════════════════════ 6) การเลื่อนจุดอ้างอิงแยกช่วง (in-sample ภายในช่วง · GOLD_XS + FX lag 0) — ช่วงที่มี NAV วันศุกร์ vs ช่วงที่ไม่มี
PRE_M = np.asarray(IDX <= pd.Timestamp("2023-12-08"))
GAP_M = np.asarray(IDX >= pd.Timestamp("2023-12-15"))
rows = []
for u in GOLD_U:
    for s_, fdf in SHIFT.items():
        for pn, m_ in (("pre_gap (2021-01 → 2023-12-08)", PRE_M), ("gap (2023-12-15 → 2025-12-26)", GAP_M)):
            res = fit_eval(R[u], lagged(fdf, [0]), m_, m_, min_obs=40)
            rows.append(dict(unit=u, shift_weekdays=s_, period=pn, n=res["n_train"], adj_r2_insample=res["adj_r2_train"]))
SBP = pd.DataFrame(rows)
save_csv(SBP, "qa_gold_shift_by_period.csv")
# spec S012 (lag 0+1 · s=0) ในช่วงย่อย
rows = []
for u in GOLD_U:
    for pn, m_ in (("pre_gap (2021-01 → 2023-12-08)", PRE_M), ("gap (2023-12-15 → 2025-12-26)", GAP_M)):
        res = fit_eval(R[u], lagged(GOLD_W, [0, 1]), m_, m_, min_obs=40)
        rows.append(dict(unit=u, period=pn, n=res["n_train"], adj_r2_insample_S012spec=res["adj_r2_train"]))
save_csv(pd.DataFrame(rows), "qa_gold_s012spec_by_period.csv")

# ═════════════════════════════════════════════════════ 7) ระดับฐานข้อมูล: snapshot AsOfDate / NAVDate แยกวันในสัปดาห์ (ทุกกอง · อ่านอย่างเดียว)
a_parts, n_parts, d_parts, u_parts = [], [], [], []
for ch in pd.read_csv(config.NAV_HISTORY_CSV, usecols=["AsOfDate", "NAVDate", "UpdateTime"], chunksize=config.NAV_CHUNKSIZE):
    u = L0.nav_loader.parse_update_time(ch["UpdateTime"]).dropna()
    u_parts.append(u.groupby([u.dt.year, u.dt.dayofweek]).size())
    a = pd.to_datetime(ch["AsOfDate"], errors="coerce").dropna()
    n = pd.to_datetime(ch["NAVDate"], errors="coerce").dropna()
    a_parts.append(a.groupby([a.dt.year, a.dt.dayofweek]).size())
    n_parts.append(n.groupby([n.dt.year, n.dt.dayofweek]).size())
    d_parts.append(a.groupby(a).size())
A_ = pd.concat(a_parts).groupby(level=[0, 1]).sum()
N_ = pd.concat(n_parts).groupby(level=[0, 1]).sum()
U_ = pd.concat(u_parts).groupby(level=[0, 1]).sum()
DB = pd.DataFrame({"asof_rows": A_, "navdate_rows": N_, "updatetime_rows": U_}).fillna(0).astype(int).reset_index()
DB.columns = ["year", "weekday_0mon", "asof_rows", "navdate_rows", "updatetime_rows"]
DB = DB[(DB["year"] >= 2021) & (DB["weekday_0mon"] <= 4)]
save_csv(DB, "qa_gold_db_weekday.csv")
dd = pd.concat(d_parts).groupby(level=0).sum()
fri = dd[(dd.index.dayofweek == 4) & (dd.index >= "2021-01-01") & (dd.index <= "2025-12-31")]
full_fri = fri[fri >= 1000]
late_fri = fri[(fri.index > pd.Timestamp("2023-12-08"))]
CHECK["db_friday_snapshot"] = dict(last_full_friday_asof_le_2023_12_31=f"{full_fri[full_fri.index <= pd.Timestamp('2023-12-31')].index.max():%Y-%m-%d}",
                                   n_full_fridays_2021_to_20231208=int((full_fri.index <= pd.Timestamp("2023-12-08")).sum()),
                                   fridays_after_20231208_with_rows={f"{d:%Y-%m-%d}": int(v) for d, v in late_fri[late_fri > 0].items()},
                                   friday_asof_rows_2024=int(fri[fri.index.year == 2024].sum()), friday_asof_rows_2025=int(fri[fri.index.year == 2025].sum()),
                                   n_fridays_after_20231208_in_2021_2025=int(len(late_fri)), note="จำนวนแถวต่อวัน AsOfDate (ทุกกองในไฟล์) · วันศุกร์ที่ ≥ 1000 แถว = มี snapshot เต็ม · วันศุกร์ที่ไม่มีแถวเลยไม่ปรากฏใน dict")

# ═════════════════════════════════════════════════════ 8) ขอบเขตระดับ L0: สัดส่วนจุดสิ้นสัปดาห์ที่ NAV asof เป็นวันศุกร์ (ทั้ง 715 กองใน universe · panel ตามจริง)
UNI = pd.read_csv(os.path.join(HERE, "universe.csv"))
U_inc = UNI[UNI["included"].astype(str).str.lower().isin(["true", "1", "y", "yes"])]
ucodes = list(U_inc["FundCode"])
nav_u, _, _ = L0.load_nav(ucodes)
nav_u = nav_u[(nav_u[config.NAV_DATE_COL] >= pd.Timestamp("2020-10-01")) & (nav_u[config.NAV_DATE_COL] <= MAIN_HI + pd.Timedelta(days=10))]
grp = {k: v for k, v in nav_u.groupby(config.NAV_FUND_CODE_COL, sort=False)}
gap_mat = np.full((len(ANCH), len(ucodes)), np.nan)
for j, c in enumerate(ucodes):
    if c not in grp:
        continue
    nd_ = L0.D(grp[c][config.NAV_DATE_COL])
    idx_ = L0.asof_idx(nd_, A64)
    ok_ = idx_ >= 0
    gap_mat[ok_, j] = (A64[ok_] - nd_[idx_[ok_]]).astype("timedelta64[D]").astype(int)
pol_u = U_inc.set_index("FundCode")["policy"].reindex(ucodes).to_numpy()
rows = []
for pn, am in (("pre_gap (2021-01-08 → 2023-12-08)", (ANCH >= "2021-01-08") & (ANCH <= "2023-12-08")), ("gap (2023-12-15 → 2025-12-26)", (ANCH >= "2023-12-15") & (ANCH <= "2025-12-26"))):
    for pol_ in ("E", "F", "O", "ALL"):
        cm = np.ones(len(ucodes), bool) if pol_ == "ALL" else (pol_u == pol_)
        gm = gap_mat[np.asarray(am)][:, cm]
        valid = np.isfinite(gm)
        tot = valid.sum()
        with np.errstate(all='ignore'):
            fri_share_by_fund = np.nanmean(np.where(valid, gm == 0, np.nan), axis=0)
        rows.append(dict(period=pn, policy=pol_, n_funds=int(cm.sum()), n_fund_weeks=int(tot), asof_is_friday=float((gm == 0).sum() / tot), asof_thu=float((gm == 1).sum() / tot),
                         asof_2to3d=float(((gm >= 2) & (gm <= 3)).sum() / tot), asof_4plus=float((gm >= 4).sum() / tot),
                         share_funds_friday_ge50pct=float(np.nanmean(fri_share_by_fund >= 0.5)), share_funds_friday_lt10pct=float(np.nanmean(fri_share_by_fund < 0.10))))
save_csv(pd.DataFrame(rows), "qa_gold_l0_friday.csv")

# ═════════════════════════════════════════════════════ 9) สรุปตัวเลขหลัก (อ้างใน QA_GOLD.md)
NVT = NAVT.set_index("code")
fr_share = {}
for c in GOLD_CODES:
    fr_share[l1eo.code_to_unit().get(c, c)] = max(fr_share.get(l1eo.code_to_unit().get(c, c), 0.0), NVT.loc[c, "friday_navdates_gap"] / max(NVT.loc[c, "n_thai_fridays_in_gap_window"], 1))
GRP_AB = {u: ("A_noFriNAV_in_gap" if fr_share[u] < 0.25 else "B_hasFriNAV_in_gap") for u in GOLD_U}
CHECK["unit_groups"] = dict(rule="A = NAV วันศุกร์ในช่วง 2023-12-11→2025-12-31 < 25% ของวันศุกร์ทำการไทย · B = ≥ 25%", groups=GRP_AB, friday_share_in_gap={k: round(v, 3) for k, v in fr_share.items()})
rows = []


def grp_med(vals: dict, members):
    return med([vals[u] for u in members])


A_ = [u for u in GOLD_U if GRP_AB[u].startswith("A")]
B_ = [u for u in GOLD_U if GRP_AB[u].startswith("B")]
s012_w = {u: base_w[u]["r2_oos"] for u in GOLD_U}
s012_m = {u: base_m[u]["r2_oos"] for u in GOLD_U}
ins_pre = SBP[(SBP.period.str.startswith("pre")) & (SBP.shift_weekdays == 0)]
ins_s012 = pd.read_csv(os.path.join(OUT, "qa_gold_s012spec_by_period.csv"))
for nm, mem in (("ทั้ง 7", GOLD_U), ("กลุ่ม A (5 หน่วย ไม่มี NAV ศุกร์)", A_), ("กลุ่ม B (I-GOLD*, UOBSG-N)", B_), ("UOBSG-N", ["UOBSG-N"])):
    r = dict(group=nm, n=len(mem), S012_weekly_r2_oos=grp_med(s012_w, mem), S012_monthly_r2_oos=grp_med(s012_m, mem))
    for pn, key in (("pre", "pre_gap"), ("gap", "gap (")):
        sub = ins_s012[ins_s012.period.str.startswith(key[:3]) & ins_s012.unit.isin(mem)]
        r[f"insample_adjr2_S012spec_{pn}"] = med(sub["adj_r2_insample_S012spec"])
        sb_ = SBP[SBP.period.str.startswith(key[:3]) & SBP.unit.isin(mem)]
        for s_ in (0, 1, 2):
            r[f"insample_adjr2_lag0_s{s_}_{pn}"] = med(sb_[sb_.shift_weekdays == s_]["adj_r2_insample"])
        bestv = sb_.groupby("unit")["adj_r2_insample"].max()
        r[f"insample_adjr2_lag0_bestshift_{pn}"] = med(bestv.to_numpy())
    for nm2 in ("W_lag0+1+2", "W_thuAnchor_lag0", "W_wedAnchor_lag0"):
        sp_ = SPEC[(SPEC.spec == nm2) & SPEC.unit.isin(mem)]
        r[f"r2_oos_{nm2}"] = med(sp_["r2_oos"])
    rows.append(r)
SUMKEY = pd.DataFrame(rows)
save_csv(SUMKEY, "qa_gold_summary.csv")

# ═════════════════════════════════════════════════════ check / manifest
man = dict(created=str(date.today()), script="qa_gold.py", script_sha256=sha(os.path.join(HERE, "qa_gold.py")), pandas=pd.__version__, numpy=np.__version__, python=sys.version.split()[0],
           inputs=[dict(file=os.path.relpath(p, ROOT), sha256=sha(p)) for p in (config.NAV_HISTORY_CSV, config.MACRO_FACTOR_CSV, os.path.join(HERE, "external", "EO_ALT_ETF.csv"),
                                                                             os.path.join(HERE, "factors_eo_noaqr_weekly.parquet"), os.path.join(HERE, "factors_eo_noaqr_monthly.parquet"),
                                                                             os.path.join(HERE, "panel_weekly.parquet"), os.path.join(HERE, "panel_monthly.parquet"),
                                                                             os.path.join(HERE, "factors_weekly.parquet"), os.path.join(HERE, "factors_monthly.parquet"),
                                                                             os.path.join(TEAM, "runs", "S012", "fund_level_O.csv"), os.path.join(TEAM, "runs", "S012", "monthly.csv"))],
           outputs=[dict(file=f".claude/factor_team/data/{n}", sha256=sha(os.path.join(OUT, n))) for n in sorted(OUTFILES)], checks=CHECK)
with open(os.path.join(OUT, "qa_gold_check.json"), "w", encoding="utf-8") as f:
    json.dump(man, f, ensure_ascii=False, indent=1, default=str)
    f.write("\n")
print("ok", len(OUTFILES), "files")
print(SUMM.to_string())
