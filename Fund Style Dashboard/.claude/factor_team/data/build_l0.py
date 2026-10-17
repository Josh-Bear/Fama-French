"""build_l0.py — ชั้น L0 ของทีมวิจัย factor: panel ผลตอบแทนกอง E/F/O + factor inputs + manifest + QA.

รัน:  cd "<root>" && PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. ./.venv/bin/python -B .claude/factor_team/data/build_l0.py [--out DIR]
ไม่ดาวน์โหลด · ไม่เขียนนอก DIR (ค่าเริ่มต้น = โฟลเดอร์ของสคริปต์) และ reports/L0_summary.md
ไม่เรียก load_nav_history* / data_access / download_snapshot — อ่าน nav_history_db.csv เองแบบ chunk
ผลเหมือนเดิมทุกบิตเมื่อ input ไม่เปลี่ยน (ตรวจด้วย sha256 ใน manifest) · env L0_NAV_CACHE (เฉพาะ dev) = parquet NAV สะอาดเพื่อข้ามขั้นอ่าน CSV
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from datetime import date

sys.dont_write_bytecode = True

import numpy as np
import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, ROOT)
import config  # noqa: E402
from data import fund_profile, msci_index, nav_loader, style_factor  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = HERE
for i, a in enumerate(sys.argv):
    if a == "--out":
        OUT = os.path.abspath(sys.argv[i + 1])
EXT = os.path.join(HERE, "external")
REPORT_DIR = os.path.join(ROOT, ".claude", "factor_team", "reports")
BD = config.BASE_DATA_DIR

# ---------------------------------------------------------------- เกณฑ์ (ค่าที่ใช้จริงใน build นี้)
MAIN_START, MAIN_END = pd.Timestamp("2021-01-01"), pd.Timestamp("2025-12-31")   # ช่วงหลัก
PANEL_END = pd.Timestamp("2026-07-31")          # ปลาย MSCI (ใช้ 2026 ดูประกอบ)
MIN_WEEKS = 52
ASOF_TOL_DAYS = 10                              # NAV/ราคา asof ห่างจากวันอ้างอิงไม่เกิน 10 วันปฏิทิน
HOLE_BDAYS = 10                                 # รู NAV > 10 วันทำการ = ไม่ทบต้นข้าม
# เกณฑ์สัดส่วนสัปดาห์ return = 0 ต่อ policy — ค่าชั่วคราว (เสนอใน QA_L0.md · รอผู้ใช้ยืนยัน)
ZERO_THRESH = {"E": 0.10, "F": 0.10, "O": 0.10}
CORR_DUP = 0.99
FAMILY_FIXED = True       # family_of(fixed=True): รวม token F/U (ดู quant_team M006/M007) — เทียบกับ fixed=False ใน QA
YIELD_TENORS = {"TH1Y": 1.0, "TH5Y": 5.0, "TH10Y": 10.0, "TH_TBILL3M": 0.25}   # อายุ (ปี) ใช้ในสูตร duration (ชั่วคราว)

# ---------------------------------------------------------------- family (คัดลอกตรรกะจาก quant_team/backtest/fund_signals.py · อ่านอย่างเดียว)
_CLS = r'A|D|R|RA|RD|A\(A\)|A\(D\)|H|UH|E|P|I|IA|AC|AR|AE|C|X|SSF|SSFX|RMF|TESG|THAIESG|THAIESGX'
CLASS_SUFFIX_RE = re.compile(rf'^({_CLS})$', re.IGNORECASE)
CLASS_SUFFIX_RE_FX = re.compile(rf'^({_CLS}|F|U)$', re.IGNORECASE)


def family_of(fc: str, groups: dict, fixed: bool) -> str:
    if fc in groups:
        return groups[fc]
    parts = re.split(r'([-\s]+)', fc.strip())
    stripped = 0
    max_strip, rx = (3, CLASS_SUFFIX_RE_FX) if fixed else (2, CLASS_SUFFIX_RE)
    while stripped < max_strip and len(parts) >= 3 and rx.match(parts[-1] or ""):
        cand = parts[:-2]
        if not cand or not any(p.strip() for p in cand):
            break
        parts = cand
        stripped += 1
    fam = "".join(parts).strip()
    return fam if fam else fc


# ---------------------------------------------------------------- utilities
def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def D(x) -> np.ndarray:
    return pd.DatetimeIndex(x).values.astype("datetime64[D]")


def asof_idx(dates: np.ndarray, anchors: np.ndarray, tol: int = ASOF_TOL_DAYS) -> np.ndarray:
    """index ของ obs ล่าสุด ≤ anchor และห่างไม่เกิน tol วัน · ไม่มี = -1."""
    idx = np.searchsorted(dates, anchors, side="right") - 1
    ok = idx >= 0
    lag = (anchors - dates[np.clip(idx, 0, None)]).astype(int)
    ok &= lag <= tol
    return np.where(ok, idx, -1)


def asof_series(s: pd.Series, anchors: np.ndarray, tol: int = ASOF_TOL_DAYS) -> np.ndarray:
    s = s.dropna().sort_index()
    if s.empty:
        return np.full(len(anchors), np.nan)
    idx = asof_idx(D(s.index), anchors, tol)
    v = s.to_numpy(float)
    return np.where(idx >= 0, v[np.clip(idx, 0, None)], np.nan)


def read_csv_c(path: str, **kw) -> pd.DataFrame:
    return pd.read_csv(path, comment="#", **kw)


def info_file(path: str, date_col: str | None = None, **kw) -> dict:
    d = {"file": os.path.relpath(path, ROOT), "sha256": sha256(path)}
    if path.endswith(".csv"):
        with open(path, "rb") as f:
            d["rows"] = sum(1 for _ in f) - 1
    if path.endswith(".parquet"):
        d["rows"] = int(len(pd.read_parquet(path)))
    d["date_min"] = d["date_max"] = None
    if date_col:
        try:
            df = pd.read_parquet(path) if path.endswith(".parquet") else pd.read_csv(path, comment="#", usecols=[date_col])
            dt = pd.to_datetime(df[date_col], errors="coerce")
            d["date_min"], d["date_max"] = f"{dt.min():%Y-%m-%d}", f"{dt.max():%Y-%m-%d}"
        except Exception:
            pass
    return d


# ---------------------------------------------------------------- 1. universe + NAV
def load_universe_profile():
    prof = fund_profile.load_fund_profile()
    f = fund_profile.filter_funds(prof)
    f = f.assign(FundCode=f[config.FUND_CODE_COL].astype(str).str.strip(),
                 policy=f[config.FUND_POLICY_COL].astype(str).str.strip(),
                 div_flag=f["Dividend_Flag"].fillna("N").astype(str).str.strip())
    return prof, f.sort_values("FundCode").reset_index(drop=True)


def load_nav(codes: list[str]):
    """อ่าน nav_history_db.csv แบบ chunk → drop NAV≤0/NaN → dedupe (UpdateTime ล่าสุด) → clean_nav_spikes (ในหน่วยความจำ)."""
    cache = os.environ.get("L0_NAV_CACHE")
    if cache and os.path.exists(cache):
        z = pd.read_parquet(cache)
        sp = pd.read_parquet(cache + ".spikes")
        return z, sp, {}
    want = set(codes)
    parts, raw_rows, raw_bad = [], 0, 0
    for ch in pd.read_csv(config.NAV_HISTORY_CSV, usecols=config.NAV_USECOLS, dtype={config.NAV_FUND_CODE_COL: str},
                          chunksize=config.NAV_CHUNKSIZE):
        ch[config.NAV_FUND_CODE_COL] = ch[config.NAV_FUND_CODE_COL].str.strip()
        sub = ch[ch[config.NAV_FUND_CODE_COL].isin(want)]
        if len(sub):
            parts.append(sub)
    nav = pd.concat(parts, ignore_index=True)
    raw_rows = len(nav)
    nav[config.NAV_DATE_COL] = pd.to_datetime(nav[config.NAV_DATE_COL], errors="coerce")
    nav[config.NAV_COL] = pd.to_numeric(nav[config.NAV_COL], errors="coerce")
    nav[config.NAV_AUM_COL] = pd.to_numeric(nav[config.NAV_AUM_COL], errors="coerce")
    nav = nav.dropna(subset=[config.NAV_DATE_COL, config.NAV_COL])
    nav = nav[nav[config.NAV_COL] > 0]
    after_bad = len(nav)
    nav["_upd"] = nav_loader.parse_update_time(nav[config.NAV_UPDATE_COL])
    nav = nav.sort_values("_upd", na_position="first", kind="stable")
    nav = nav.drop_duplicates(subset=[config.NAV_FUND_CODE_COL, config.NAV_DATE_COL], keep="last")
    out = nav[[config.NAV_FUND_CODE_COL, config.NAV_DATE_COL, config.NAV_COL, config.NAV_AUM_COL]]
    out = out.sort_values([config.NAV_FUND_CODE_COL, config.NAV_DATE_COL]).reset_index(drop=True)
    after_dedupe = len(out)
    fixed, log_df = nav_loader.clean_nav_spikes(out)
    fixed = fixed.sort_values([config.NAV_FUND_CODE_COL, config.NAV_DATE_COL]).reset_index(drop=True)
    stats = {"rows_filtered_raw": raw_rows, "rows_after_drop_bad_nav": after_bad, "rows_after_dedupe": after_dedupe,
             "spike_points": int(len(log_df))}
    if cache:
        fixed.to_parquet(cache)
        log_df.to_parquet(cache + ".spikes")
    return fixed, log_df, stats


def fund_returns(navdf: pd.DataFrame, codes: list[str], anchors: pd.DatetimeIndex):
    """ผลตอบแทนเลขคณิตต่อช่วง (anchor[k-1] → anchor[k]) ต่อกอง · คืน (ret DataFrame index=anchors[1:], aum DataFrame index=anchors, meta)."""
    A = D(anchors)
    ret = np.full((len(anchors) - 1, len(codes)), np.nan)
    aum = np.full((len(anchors), len(codes)), np.nan)
    first_nav, last_nav, n_obs, n_holes = {}, {}, {}, {}
    g = {k: v for k, v in navdf.groupby(config.NAV_FUND_CODE_COL, sort=False)}
    for j, c in enumerate(codes):
        if c not in g:
            continue
        gg = g[c]
        dts = D(gg[config.NAV_DATE_COL])
        nv = gg[config.NAV_COL].to_numpy(float)
        av = gg[config.NAV_AUM_COL].to_numpy(float)
        hole = np.busday_count(dts[:-1], dts[1:]) > HOLE_BDAYS if len(dts) > 1 else np.array([], bool)
        C = np.concatenate([[0], np.cumsum(hole)])
        idx = asof_idx(dts, A)
        i0, i1 = idx[:-1], idx[1:]
        ok = (i0 >= 0) & (i1 >= 0)
        i0c, i1c = np.clip(i0, 0, None), np.clip(i1, 0, None)
        ok &= (C[i1c] - C[i0c]) == 0
        r = nv[i1c] / nv[i0c] - 1.0
        ret[:, j] = np.where(ok, r, np.nan)
        aum[:, j] = np.where(idx >= 0, av[np.clip(idx, 0, None)], np.nan)
        first_nav[c], last_nav[c], n_obs[c], n_holes[c] = dts[0], dts[-1], len(dts), int(hole.sum())
    R = pd.DataFrame(ret, index=anchors[1:], columns=codes)
    AU = pd.DataFrame(aum, index=anchors, columns=codes)
    meta = pd.DataFrame({"nav_first": pd.Series(first_nav), "nav_last": pd.Series(last_nav),
                         "nav_obs": pd.Series(n_obs), "nav_holes": pd.Series(n_holes)})
    for c in ("nav_first", "nav_last"):
        meta[c] = pd.to_datetime(meta[c])
    return R, AU, meta.reindex(codes)


def spike_candidates_frule(navdf: pd.DataFrame, codes: list[str], pol: dict, anchors: pd.DatetimeIndex) -> pd.DataFrame:
    """ตรวจอย่างเดียว (ไม่แก้): กฎ spike ของ quant_team M015 §4.2 — |r_in|>0.5% & |r_out|>0.5% & เครื่องหมายตรงข้าม & |r_in+r_out|<0.1% (log-return รายจุด)."""
    A = D(anchors)
    rows = []
    sub = navdf[navdf[config.NAV_FUND_CODE_COL].isin(set(codes))]
    for c, g in sub.groupby(config.NAV_FUND_CODE_COL, sort=True):
        g = g.sort_values(config.NAV_DATE_COL)
        v = g[config.NAV_COL].to_numpy(float)
        dts = D(g[config.NAV_DATE_COL])
        if len(v) < 3:
            continue
        r = np.diff(np.log(v))
        rin, rout = r[:-1], r[1:]
        hit = (np.abs(rin) > 0.005) & (np.abs(rout) > 0.005) & (rin * rout < 0) & (np.abs(rin + rout) < 0.001)
        pos = np.where(hit)[0] + 1
        if len(pos) == 0:
            continue
        used = set(asof_idx(dts, A).tolist())
        for i in pos:
            rows.append({"FundCode": c, "policy": pol[c], "NAVDate": pd.Timestamp(dts[i]), "move": float(rin[i - 1]),
                         "used_as_weekly_asof": bool(i in used)})
    return pd.DataFrame(rows, columns=["FundCode", "policy", "NAVDate", "move", "used_as_weekly_asof"])


# ---------------------------------------------------------------- 2. factor inputs
def par_mod_duration(y_dec: np.ndarray, n_years: float) -> np.ndarray:
    """modified duration ของบอนด์ par coupon=y จ่ายรายครึ่งปี อายุ n ปี: (1 − (1+y/2)^(−2n)) / y."""
    y = np.where(np.abs(y_dec) < 1e-9, 1e-9, y_dec)
    return (1.0 - (1.0 + y / 2.0) ** (-2.0 * n_years)) / y


def build_factor_levels(anchors: pd.DatetimeIndex) -> dict:
    """คืน dict name → ค่าที่ anchor (asof ≤ anchor · ห่างไม่เกิน 10 วัน) แยกประเภท: levels(price) / diffs(Δ) / levels-only."""
    A = D(anchors)
    price: dict[str, np.ndarray] = {}      # -> pct change
    delta: dict[str, np.ndarray] = {}      # -> diff (level ที่ anchor)
    group: dict[str, str] = {}

    def add(store, name, arr, grp):
        store[name] = arr
        group[name] = grp

    # MSCI 28 (THB)
    cty, sec = msci_index.load_country_index(), msci_index.load_sector_index()
    for c in config.MSCI_COUNTRY_COLS:
        add(price, c, asof_series(cty[c], A), "MSCI_country")
    for c in config.MSCI_SECTOR_COLS:
        add(price, c, asof_series(sec[c], A), "MSCI_sector")
    # style ETF 4 relative (de-market) + ACWI ETF USD
    snap = style_factor.load_snapshot()
    rel = style_factor.build_style_levels(snap)
    for c in config.STYLE_FACTOR_COLS:
        add(price, c, asof_series(rel[c], A), "style_relative")
    add(price, "ACWI_ETF_USD", asof_series(snap["ACWI"], A), "market_ETF_USD")
    # macro 7
    mac = pd.read_csv(config.MACRO_FACTOR_CSV, parse_dates=["Date"]).set_index("Date").sort_index()
    for c in config.MACRO_RETURN_COLS:
        add(price, c, asof_series(mac[c], A), "macro")
    for c in config.MACRO_DELTA_COLS:
        add(delta, c + "_d", asof_series(mac[c], A), "macro_delta")
    fx = price["USDTHB"]
    add(price, "Gold_THB", price["Gold"] * fx, "gold")
    # ETF ที่ต้องแปลงเป็นบาท (USD + THB)
    usd = {}
    bond = read_csv_c(os.path.join(BD, "US_BOND_ETF.csv"), parse_dates=["Date"]).set_index("Date").sort_index()
    for c in ("AGG", "IEF"):
        usd[c] = asof_series(bond[c], A)
    rc = pd.read_csv(os.path.join(EXT, "US_RATES_CREDIT_ETF.csv"), parse_dates=["Date"]).set_index("Date").sort_index()
    for c in ("SHV", "LQD", "HYG", "EMB"):
        usd[c] = asof_series(rc[c], A)
    for c, v in usd.items():
        add(price, f"{c}_USD", v, "bond_ETF_USD")
        add(price, f"{c}_THB", v * fx, "bond_ETF_THB")
    tdex = pd.read_csv(os.path.join(EXT, "TH_EQUITY_PROXY.csv"), parse_dates=["Date"]).set_index("Date").sort_index()
    add(price, "TDEX_THB", asof_series(tdex["TDEX.BK"], A), "TH_equity_proxy")
    # ผลตอบแทน rf = ดอกเบี้ยนโยบาย ธปท. ทบต้นรายวัน (act/365) · ใช้อัตราที่ประกาศ มีผลวันประกาศ (สมมติ)
    pr = read_csv_c(os.path.join(BD, "TH_POLICY_RATE.csv"), parse_dates=["announce_date"]).sort_values("announce_date")
    days = pd.date_range("2020-01-01", PANEL_END + pd.Timedelta(days=5), freq="D")
    rate = pr.set_index("announce_date")["rate_pct"].reindex(days, method="ffill")
    cum = (1.0 + rate.to_numpy(float) / 100.0 / 365.0)
    cum = pd.Series(np.cumprod(cum), index=days)
    add(price, "RF_BOT", asof_series(cum, A, tol=3), "rf")
    # พันธบัตรไทย: level + Δ (pp) + ผลตอบแทนประมาณด้วย duration
    thy = pd.read_csv(os.path.join(EXT, "TH_GOV_YIELDS.csv"), parse_dates=["Date"]).set_index("Date").sort_index()
    ylev = {}
    for c in YIELD_TENORS:
        ylev[c] = asof_series(thy[c], A)
        add(delta, f"{c}_d", ylev[c], "TH_yield_delta_pp")
    # FRED
    fr = pd.read_csv(os.path.join(EXT, "US_SPREADS_FRED.csv"), parse_dates=["Date"]).set_index("Date").sort_index()
    add(delta, "DTB3_d", asof_series(fr["DTB3"], A), "US_tbill_delta_pp")
    add(delta, "IG_OAS_late_d", asof_series(fr["BAMLC0A0CM"], A), "FRED_spread_NOT_USABLE_MAIN")
    add(delta, "HY_OAS_late_d", asof_series(fr["BAMLH0A0HYM2"], A), "FRED_spread_NOT_USABLE_MAIN")
    levels_only = dict(ylev)
    levels_only["DTB3_lvl"] = delta["DTB3_d"]
    levels_only["IG_OAS_late_lvl"] = delta["IG_OAS_late_d"]
    levels_only["HY_OAS_late_lvl"] = delta["HY_OAS_late_d"]
    levels_only["VIX_lvl"] = delta["VIX_d"]
    levels_only["US10Y_lvl"] = delta["US10Y_d"]
    return {"price": price, "delta": delta, "ylev": ylev, "levels_only": levels_only, "group": group}


def make_factors(anchors: pd.DatetimeIndex):
    L = build_factor_levels(anchors)
    idx = anchors[1:]
    cols, group = {}, dict(L["group"])
    for k, v in L["price"].items():
        if k == "RF_BOT":
            cols[k] = v[1:] / v[:-1] - 1.0
        else:
            cols[k] = v[1:] / v[:-1] - 1.0
    for k, v in L["delta"].items():
        cols[k] = v[1:] - v[:-1]
    # ระดับ ณ ปลายช่วง
    for k, v in L["levels_only"].items():
        cols[k.replace("TH_TBILL3M", "TH_TBILL3M") + ("" if k.endswith("_lvl") else "_lvl")] = v[1:]
        group[k + ("" if k.endswith("_lvl") else "_lvl")] = "levels_end_of_period"
    # ประมาณผลตอบแทนบอนด์ไทยจาก yield (ชั่วคราว · ต้องให้ผู้ใช้ตัดสินใจ): carry y0·days/365 − D_mod(y0,n)·Δy
    days = (anchors[1:] - anchors[:-1]).days.to_numpy(float)
    for k, n in YIELD_TENORS.items():
        y = L["ylev"][k]
        y0, dy = y[:-1] / 100.0, (y[1:] - y[:-1]) / 100.0
        cols[f"{k}_est_ret"] = y0 * days / 365.0 - par_mod_duration(y0, n) * dy
        group[f"{k}_est_ret"] = "TH_bond_est_PROVISIONAL"
    df = pd.DataFrame(cols, index=idx)
    df.index.name = "date"
    order = [c for c in df.columns]
    return df[order], group


# ---------------------------------------------------------------- main
def pct(x):
    return f"{100 * x:.1f}%"


def main():
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(REPORT_DIR, exist_ok=True)
    today = date.today().isoformat()
    prof, uni = load_universe_profile()
    codes = uni["FundCode"].tolist()
    pol = dict(zip(uni["FundCode"], uni["policy"]))
    divf = dict(zip(uni["FundCode"], uni["div_flag"]))
    n0 = uni["policy"].value_counts().to_dict()

    nav, spikes, nav_stats = load_nav(codes)
    have = set(nav[config.NAV_FUND_CODE_COL].unique())

    # anchors
    wk = pd.date_range("2021-01-01", PANEL_END, freq="W-FRI")
    me = pd.DatetimeIndex([pd.Timestamp("2020-12-31")] + list(pd.date_range("2021-01-31", PANEL_END, freq="ME")))
    assert wk[0] == pd.Timestamp("2021-01-01") and wk[-1] == PANEL_END
    Rw, AUw, meta = fund_returns(nav, codes, wk)
    Rm, _, _ = fund_returns(nav, codes, me)

    # 3. NAV พอคำนวณ
    main_w = Rw.loc[(Rw.index > MAIN_START) & (Rw.index <= MAIN_END)]
    n_weeks = main_w.notna().sum()
    zero_frac = ((main_w == 0) & main_w.notna()).sum() / n_weeks.replace(0, np.nan)
    cls = pd.DataFrame({"FundCode": codes, "policy": [pol[c] for c in codes], "div_flag": [divf[c] for c in codes]})
    cls["has_nav"] = cls["FundCode"].isin(have)
    cls["n_weeks"] = n_weeks.reindex(codes).to_numpy()
    cls["zero_frac"] = zero_frac.reindex(codes).to_numpy()
    cls["thr"] = cls["policy"].map(ZERO_THRESH)
    cls = cls.join(meta, on="FundCode")
    grp = pd.read_csv(os.path.join(BD, "share_class_groups.csv"), encoding="utf-8-sig")
    groups = dict(zip(grp["FundCode"].str.strip(), grp["group"].str.strip()))
    fam_old = {c: family_of(c, groups, False) for c in codes}
    fam_new = {c: family_of(c, groups, True) for c in codes}
    fam = fam_new if FAMILY_FIXED else fam_old
    cls["family"] = cls["FundCode"].map(fam)
    cls["ok_n"] = cls["n_weeks"] >= MIN_WEEKS
    cls["ok_zero"] = cls["zero_frac"] <= cls["thr"]
    cls["eligible"] = cls["has_nav"] & cls["ok_n"] & cls["ok_zero"]

    # 4. 1 class ต่อกอง
    cls["_div"] = (cls["div_flag"] == "Y").astype(int)
    el = cls[cls["eligible"]].sort_values(["family", "_div", "n_weeks", "nav_first", "FundCode"],
                                          ascending=[True, True, False, True, True], kind="stable")
    rep = el.drop_duplicates("family", keep="first").set_index("family")["FundCode"].to_dict()
    cls["selected"] = cls["eligible"] & (cls["FundCode"] == cls["family"].map(rep))
    reasons = []
    for r in cls.itertuples():
        if not r.has_nav:
            reasons.append("ไม่มี NAV ใช้ได้")
        elif not r.ok_n:
            reasons.append(f"n_weeks={int(r.n_weeks)}<{MIN_WEEKS}")
        elif not r.ok_zero:
            reasons.append(f"zero_frac={r.zero_frac:.3f}>{r.thr:.2f}({r.policy})")
        elif not r.selected:
            reasons.append(f"class อื่นของ family เป็นตัวแทน: {rep[r.family]}")
        elif r.div_flag == "Y":
            reasons.append("ok · family มีแต่ class ปันผล (NAV ไม่รวมปันผล)")
        else:
            reasons.append("ok")
    cls["reason"] = reasons
    sel = cls[cls["selected"]].copy()

    # 4b. corr ซ้ำข้าม family
    sc = sel["FundCode"].tolist()
    cmat = main_w[sc].corr(min_periods=MIN_WEEKS)
    iu = np.triu_indices(len(sc), 1)
    pairs = pd.DataFrame({"a": np.array(sc)[iu[0]], "b": np.array(sc)[iu[1]], "corr": cmat.to_numpy()[iu]})
    dup = pairs[pairs["corr"] > CORR_DUP].sort_values(["corr", "a", "b"], ascending=[False, True, True]).reset_index(drop=True)
    dup["fam_a"] = dup["a"].map(fam)
    dup["fam_b"] = dup["b"].map(fam)
    dup["same_family"] = dup["fam_a"] == dup["fam_b"]

    spk_f = spike_candidates_frule(nav, [c for c in sc if pol[c] == "F"], pol, wk)   # F-rule ออกแบบสำหรับกอง F เท่านั้น (กับ E/O จับ noise ปกติ)
    spk_f.to_csv(os.path.join(OUT, "spike_candidates_Frule.csv"), index=False, date_format="%Y-%m-%d")
    dup.to_csv(os.path.join(OUT, "dup_pairs.csv"), index=False)

    # universe.csv
    valid_dates = {}
    Rall = Rw.notna()
    for c in codes:
        v = Rall.index[Rall[c].to_numpy()]
        valid_dates[c] = (v.min(), v.max()) if len(v) else (pd.NaT, pd.NaT)
    u = pd.DataFrame({
        "FundCode": cls["FundCode"], "family": cls["family"], "policy": cls["policy"],
        "n_weeks": cls["n_weeks"].fillna(0).astype(int),
        "first": [valid_dates[c][0] for c in cls["FundCode"]], "last": [valid_dates[c][1] for c in cls["FundCode"]],
        "included": cls["selected"], "reason": cls["reason"],
        "zero_frac": cls["zero_frac"].round(6), "div_flag": cls["div_flag"],
        "nav_first": cls["nav_first"], "nav_last": cls["nav_last"], "nav_obs": cls["nav_obs"], "nav_holes": cls["nav_holes"],
    }).sort_values("FundCode", kind="stable")
    u.to_csv(os.path.join(OUT, "universe.csv"), index=False, date_format="%Y-%m-%d")

    # panels (long · ครบทุกวัน × กองที่เลือก · NaN = ไม่มีข้อมูล)
    def to_long(R, cols):
        x = R[cols].copy()
        x.index.name = "date"
        l = x.reset_index().melt(id_vars="date", var_name="FundCode", value_name="ret")
        return l.sort_values(["FundCode", "date"], kind="stable").reset_index(drop=True)[["FundCode", "date", "ret"]]

    pw, pm = to_long(Rw, sc), to_long(Rm, sc)
    pw.to_parquet(os.path.join(OUT, "panel_weekly.parquet"), index=False)
    pm.to_parquet(os.path.join(OUT, "panel_monthly.parquet"), index=False)
    au = AUw[sc].copy()
    au.index.name = "date"
    aul = au.reset_index().melt(id_vars="date", var_name="FundCode", value_name="aum")
    aul = aul.sort_values(["FundCode", "date"], kind="stable").reset_index(drop=True)[["FundCode", "date", "aum"]]
    aul.to_parquet(os.path.join(OUT, "aum_weekly.parquet"), index=False)

    # factors
    Fw, fgroup = make_factors(wk)
    Fm, _ = make_factors(me)
    Fw.to_parquet(os.path.join(OUT, "factors_weekly.parquet"))
    Fm.to_parquet(os.path.join(OUT, "factors_monthly.parquet"))
    pd.Series(fgroup, name="group").rename_axis("factor").reset_index().to_csv(
        os.path.join(OUT, "factor_groups.csv"), index=False)

    # coverage ต่อสัปดาห์
    cov = pd.DataFrame({p: Rw[[c for c in sc if pol[c] == p]].notna().sum(axis=1) for p in ("E", "F", "O")})
    cov["ALL"] = cov.sum(axis=1)
    cov.index.name = "date"
    cov.to_csv(os.path.join(OUT, "coverage_weekly.csv"))
    spikes.to_csv(os.path.join(OUT, "spike_fixes.csv"), index=False, date_format="%Y-%m-%d")

    # ------------------------------------------------------------ QA
    import qa_l0  # noqa: E402  (ไฟล์เดียวกันในโฟลเดอร์ data/)
    ctx = dict(today=today, uni=u, cls=cls, sel=sel, n0=n0, nav=nav, nav_stats=nav_stats, spikes=spikes, Rw=Rw, Rm=Rm,
               main_w=main_w, Fw=Fw, Fm=Fm, fgroup=fgroup, cov=cov, dup=dup, pol=pol, fam_old=fam_old, fam_new=fam_new,
               ZERO_THRESH=ZERO_THRESH, MIN_WEEKS=MIN_WEEKS, MAIN_START=MAIN_START, MAIN_END=MAIN_END, PANEL_END=PANEL_END,
               sc=sc, codes=codes, AUw=AUw, FAMILY_FIXED=FAMILY_FIXED, YIELD_TENORS=YIELD_TENORS, OUT=OUT, ROOT=ROOT,
               REPORT_DIR=REPORT_DIR, pw=pw, pm=pm, spk_f=spk_f, wk=wk)
    qa_l0.run(ctx)

    # ------------------------------------------------------------ manifest
    files_in = [
        info_file(config.FUND_PROFILE_CSV), info_file(config.NAV_HISTORY_CSV, "NAVDate"),
        info_file(os.path.join(BD, "share_class_groups.csv")),
        info_file(config.MSCI_COUNTRY_CSV, "Date"), info_file(config.MSCI_SECTOR_CSV, "Date"),
        info_file(config.STYLE_FACTOR_CSV, "Date"), info_file(config.MACRO_FACTOR_CSV, "Date"),
        info_file(os.path.join(BD, "TH_POLICY_RATE.csv"), "announce_date"), info_file(os.path.join(BD, "US_BOND_ETF.csv"), "Date"),
    ] + [info_file(os.path.join(EXT, f), "Date") for f in
         ("TH_EQUITY_PROXY.csv", "US_RATES_CREDIT_ETF.csv", "TH_GOV_YIELDS.csv", "US_SPREADS_FRED.csv")]
    files_in.append(info_file(os.path.join(HERE, "build_l0.py")))
    files_in.append(info_file(os.path.join(HERE, "qa_l0.py")))
    outs = []
    for f, dc in (("panel_weekly.parquet", "date"), ("panel_monthly.parquet", "date"), ("aum_weekly.parquet", "date"),
                  ("factors_weekly.parquet", None), ("factors_monthly.parquet", None), ("universe.csv", None),
                  ("factor_groups.csv", None), ("coverage_weekly.csv", "date"), ("spike_fixes.csv", None),
                  ("spike_candidates_Frule.csv", None), ("dup_pairs.csv", None)):
        p = os.path.join(OUT, f)
        d = info_file(p, dc)
        if f.startswith("factors_"):
            fx = pd.read_parquet(p)
            d["date_min"], d["date_max"] = f"{fx.index.min():%Y-%m-%d}", f"{fx.index.max():%Y-%m-%d}"
        outs.append(d)
    for f in ("QA_L0.md",):
        outs.append({"file": os.path.relpath(os.path.join(OUT, f), ROOT), "sha256": sha256(os.path.join(OUT, f)),
                     "note": "มีวันที่สร้างในเนื้อหา"})
    man = {"created": today, "script": "build_l0.py", "pandas": pd.__version__, "numpy": np.__version__,
           "criteria": {"main_period": [f"{MAIN_START:%Y-%m-%d}", f"{MAIN_END:%Y-%m-%d}"], "panel_end": f"{PANEL_END:%Y-%m-%d}",
                        "min_weekly_returns": MIN_WEEKS, "zero_return_thresholds_PROVISIONAL": ZERO_THRESH,
                        "asof_tolerance_calendar_days": ASOF_TOL_DAYS, "nav_hole_business_days": HOLE_BDAYS,
                        "dup_corr": CORR_DUP, "family_fixed": FAMILY_FIXED,
                        "th_bond_est_durations": "par-bond modified duration ที่ y ต้นช่วง · อายุ(ปี)=" + json.dumps(YIELD_TENORS),
                        "fund_filter": "config.FILTER_EQ/NEQ/EMPTY (9 เกณฑ์)"},
           "inputs": files_in, "outputs": outs,
           "counts": {"filter9": n0, "selected": sel["policy"].value_counts().to_dict()}}
    with open(os.path.join(OUT, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(man, f, ensure_ascii=False, indent=1, sort_keys=False, default=str)
    print("done", sel["policy"].value_counts().to_dict())


if __name__ == "__main__":
    sys.path.insert(0, HERE)
    main()
