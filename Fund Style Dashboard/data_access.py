"""data_access.py — cached data layer สำหรับ UI (Phase 5) + orchestration ของ pipeline.

รัน pipeline ครั้งเดียว (filter -> nav -> return series -> match -> metrics) แล้ว cache ลงดิสก์
(cache/results.csv, cache/coefs.csv) เพราะการโหลด nav 336MB + ElasticNet 368×2×3 ใช้เวลาหลายนาที
UI อ่านจาก cache ผ่าน @st.cache_data (ถ้าไม่มี cache จะ build อัตโนมัติ)

Build ใหม่ (CLI):
  ./.venv/bin/python data_access.py          -> fund pipeline (nav_clean.parquet + results.csv + coefs.csv, ~75 วิ)
  ./.venv/bin/python data_access.py vol      -> vol forecast cache (หน้า 4, ~10 วิ)
  ./.venv/bin/python data_access.py style-download -> snapshot ETF style (ต้องต่อเน็ต, ครั้งแรก/อัปเดต)
  ./.venv/bin/python data_access.py style    -> style cache (หน้า 6, ต้องมี snapshot + results.csv)
  ./.venv/bin/python data_access.py macro-download -> snapshot macro 7 ตัว (ต้องต่อเน็ต, ครั้งแรก/อัปเดต)
  ./.venv/bin/python data_access.py macro    -> macro cache (หน้า 7, ต้องมี snapshot + results.csv/coefs.csv)
  ./.venv/bin/python data_access.py score    -> match กับ country ชุด VIF-cleaned (หน้า 8, ~35-40 วิ)
  ./.venv/bin/python data_access.py tf       -> backtest + replay โมเดล M004-TF-FX (หน้า 9, ~15 วิ · ต้องมี nav_clean.parquet)
ปุ่ม 🔄 Rebuild ในแอป = build ทุก cache รวดเดียว (fund + vol + style/macro ถ้ามี snapshot แล้ว + score หน้า 8 + tf หน้า 9)
"""

from __future__ import annotations

import os

import numpy as np
import pandas as pd

import config
from analysis import fund_backtest, macro_chain, matching, metrics, portfolio, screening, tf_model
from data import fund_profile, macro_factor, msci_index, nav_loader, style_factor

RESULTS_CSV = os.path.join(config.CACHE_DIR, "results.csv")
COEFS_CSV = os.path.join(config.CACHE_DIR, "coefs.csv")
VOL_BACKTEST_CSV = os.path.join(config.CACHE_DIR, "vol_forecast_backtest.csv")
VOL_LATEST_CSV = os.path.join(config.CACHE_DIR, "vol_forecast_latest.csv")
STYLE_RESULTS_CSV = os.path.join(config.CACHE_DIR, "style_results.csv")
STYLE_COEFS_CSV = os.path.join(config.CACHE_DIR, "style_coefs.csv")
MACRO_LOADINGS_CSV = os.path.join(config.CACHE_DIR, "macro_loadings.csv")
MACRO_INDEX_BETAS_CSV = os.path.join(config.CACHE_DIR, "macro_index_betas.csv")
SCORE_MATCHES_CLEAN_CSV = os.path.join(config.CACHE_DIR, "country_matches_clean11.csv")

FUND = config.NAV_FUND_CODE_COL
NAVDATE = config.NAV_DATE_COL
_FUND_NAME_COL = "Fund Name EN"


def _nav_by_fund(nav: pd.DataFrame) -> dict[str, pd.Series]:
    """nav long-form -> {FundCode: NAV (index=NAVDate)} — group ครั้งเดียว (linear) แทนการ mask nav ทั้งก้อนต่อกอง."""
    return {f: g.set_index(NAVDATE)[config.NAV_COL] for f, g in nav.groupby(FUND)}


def _atomic_write(path: str, write) -> None:
    """เขียนไฟล์ cache แบบ atomic: write(tmp) ในโฟลเดอร์เดียวกัน แล้ว os.replace — คนอ่านพร้อมกันไม่เห็นไฟล์ครึ่งๆ กลางๆ."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = f"{path}.tmp-{os.getpid()}"
    try:
        write(tmp)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def _atomic_csv(df: pd.DataFrame, path: str) -> None:
    _atomic_write(path, lambda tmp: df.to_csv(tmp, index=False))


def _write_nav_clean(nav: pd.DataFrame, status: pd.DataFrame, spike_log: pd.DataFrame) -> None:
    """NAV ที่ clean แล้ว + สถานะต่อกอง -> config.NAV_CLEAN_PARQUET (ขั้นหลังอ่านจากที่นี่ ไม่สแกนไฟล์ดิบซ้ำ).

    คอลัมน์: FundCode, NAVDate, NAV, AUM, spike_fixed (แถวที่ถูกแก้ NAV spike), status (keep/stale/closed/few_points)
    """
    if nav.empty:
        raise RuntimeError(f"ไม่มี NAV เลย — ไม่เขียนทับ {os.path.basename(config.NAV_CLEAN_PARQUET)}")
    out = nav.copy()
    fixed = set()
    if len(spike_log):
        fixed = set(zip(spike_log[FUND], pd.to_datetime(spike_log[NAVDATE])))
    out["spike_fixed"] = [(f, d) in fixed for f, d in zip(out[FUND], out[NAVDATE])]
    out["status"] = out[FUND].map(status["status"])
    os.makedirs(config.CACHE_DIR, exist_ok=True)
    _atomic_write(config.NAV_CLEAN_PARQUET, lambda tmp: out.to_parquet(tmp, index=False))


def _load_clean_nav(fund_codes: list[str]) -> dict[str, pd.Series]:
    """{FundCode: NAV (index=NAVDate)} จาก NAV_CLEAN_PARQUET — ~0.1 วิ แทนการสแกน nav_history_db.csv 336MB (~2 วิ).

    ไม่มีไฟล์ (ยังไม่เคยรัน build_pipeline หลังเพิ่มขั้นนี้) -> โหลดจากไฟล์ดิบแบบเดิม (ช้าแต่ผลเท่ากัน)
    """
    codes = list(fund_codes)
    if not os.path.exists(config.NAV_CLEAN_PARQUET):
        return _nav_by_fund(nav_loader.load_nav_history(codes))
    nav = pd.read_parquet(config.NAV_CLEAN_PARQUET, columns=[FUND, NAVDATE, config.NAV_COL],
                          filters=[(FUND, "in", codes)])
    return _nav_by_fund(nav)


def _write_cache(results: pd.DataFrame, coefs: pd.DataFrame, results_path: str, coefs_path: str,
                 skipped: list | None = None) -> None:
    """เขียน cache คู่ results + coefs — ผลว่าง (ทุกกองพลาด) = raise ไม่เขียนทับ.

    CSV เปล่า pd.read_csv อ่านไม่ได้ (EmptyDataError) และ loader จะไม่ build ใหม่เพราะไฟล์มีอยู่แล้ว -> ค้างถาวร
    """
    if results.empty:
        raise RuntimeError(f"ไม่มีกองไหนผ่านเลย — ไม่เขียนทับ {os.path.basename(results_path)} "
                           f"(ตัวอย่างที่พลาด: {(skipped or [])[:3]})")
    os.makedirs(config.CACHE_DIR, exist_ok=True)
    _atomic_csv(results, results_path)
    _atomic_csv(coefs, coefs_path)


def build_pipeline(verbose: bool = True) -> tuple[pd.DataFrame, pd.DataFrame]:
    """รัน pipeline เต็ม -> (results, coefs) แล้วเขียน cache. one row per fund.

    เฉพาะกอง config.APP_POLICY (E) — กรองตั้งแต่ universe ก่อนโหลด nav ทั้งแอปจึงเห็นแต่กองหุ้น
    (คอลัมน์ policy ยังเก็บไว้ใน results.csv เพื่อ provenance แม้จะมีค่าเดียว)
    """
    filt = fund_profile.filter_funds(fund_profile.load_fund_profile())
    pol = fund_profile.policy_map(filt)
    codes = fund_profile._norm(filt[config.FUND_CODE_COL])
    name_map = dict(zip(codes, fund_profile._norm(filt[_FUND_NAME_COL]))) if _FUND_NAME_COL in filt else {}
    universe = [f for f in fund_profile.fund_universe(filt) if pol.get(f) == config.APP_POLICY]

    if verbose:
        print(f"universe={len(universe)} (policy {config.APP_POLICY})  loading nav (336MB, chunked)...")
    nav, closed, spike_log = nav_loader.load_nav_history_full(universe)
    cty = msci_index.load_country_index()
    sec = msci_index.load_sector_index()

    # ความสดของ NAV เทียบวันล่าสุดของดัชนี: กองเลิกแล้ว / NAV เก่าเกิน NAV_STALE_MAX_DAYS -> ตัดออกทั้งแอป
    status = nav_loader.fund_nav_status(nav, cty.index.max(), closed)
    enough = set(nav_loader.funds_passing_threshold(nav))
    status.loc[~status.index.isin(list(enough)) & (status["status"] == "keep"), "status"] = "few_points"
    passed = sorted(status.index[status["status"] == "keep"])
    _write_nav_clean(nav, status, spike_log)
    if verbose:
        n = status["status"].value_counts().to_dict()
        print(f"nav rows={len(nav):,}  funds passing threshold={len(enough)}  -> keep {len(passed)} "
              f"(stale {n.get('stale', 0)} · closed {n.get('closed', 0)} · few_points {n.get('few_points', 0)})")

    aum_latest = (nav.dropna(subset=[config.NAV_AUM_COL])
                     .sort_values(NAVDATE).groupby(FUND)[config.NAV_AUM_COL].last())

    nav_by_fund = _nav_by_fund(nav)

    rows, coef_rows, skipped = [], [], []
    scopes = [("country", cty, config.MSCI_COUNTRY_COLS), ("sector", sec, config.MSCI_SECTOR_COLS)]
    for i, f in enumerate(passed):
        fn = nav_by_fund[f]
        try:
            res_by_scope, fund_coef_rows = {}, []
            for scope, levels, cols in scopes:
                aligned = matching.build_fund_returns(fn, levels)
                # guard: กองที่มี return ในช่วง MSCI น้อยเกิน -> ข้ามทั้งกอง (กัน ElasticNetCV crash/ผลมั่ว)
                if len(aligned) < config.MIN_REGRESSION_OBS:
                    raise ValueError(f"{scope}: in-window obs {len(aligned)} < {config.MIN_REGRESSION_OBS}")
                res = matching.match_exposure(aligned)
                res_by_scope[scope] = (res, aligned)
                for idx in cols:
                    fund_coef_rows.append({
                        "FundCode": f, "scope": scope, "index": idx,
                        "elastic": float(res["coef"][idx]),
                        "lasso": float(res["lasso_coef"][idx]),
                        "ridge": float(res["ridge_coef"][idx]),
                        "is_primary": idx == res["primary"],
                        "is_secondary": idx == res["secondary"],
                    })
        except Exception as e:  # noqa: BLE001 — กองเดียวพลาด ไม่ให้ล้ม build ทั้งชุด
            skipped.append((f, str(e)))
            continue

        coef_rows.extend(fund_coef_rows)
        rc, ac = res_by_scope["country"]
        rs, _ = res_by_scope["sector"]
        stats = matching.fund_return_stats(fn, cty)   # CAGR + vol ตามจำนวนจุดต่อปีจริง (ไม่ใช่ 252/n)
        rows.append({
            "FundCode": f, "FundName": name_map.get(f, ""), "policy": pol.get(f, ""),
            "aum": float(aum_latest.get(f, 0.0) or 0.0),
            "ann_return": stats["ann_return"],
            "ann_vol": stats["ann_vol"],
            "return_21d": metrics.recent_return(fn),   # หน้า 5 — ใช้ fn ที่โหลดอยู่แล้ว ไม่อ่าน nav ใหม่
            "n_obs": rc["n"],
            "country_primary": rc["primary"], "country_secondary": rc["secondary"],
            "country_primary_coef": rc["primary_coef"], "country_r2": rc["r2"],
            "sector_primary": rs["primary"], "sector_secondary": rs["secondary"],
            "sector_primary_coef": rs["primary_coef"], "sector_r2": rs["r2"],
        })
        if verbose and (i + 1) % 50 == 0:
            print(f"  ...{i + 1}/{len(passed)} funds")

    if verbose and skipped:
        print(f"skipped {len(skipped)} funds (in-window obs น้อยเกิน/error): {[s[0] for s in skipped][:10]}")
    results = pd.DataFrame(rows)
    coefs = pd.DataFrame(coef_rows)
    _write_cache(results, coefs, RESULTS_CSV, COEFS_CSV, skipped)
    if verbose:
        print(f"saved {len(results)} funds -> {RESULTS_CSV}")
    return results, coefs


# --- Vol Forecast (หน้า 4) — index-level EWMA/GARCH walk-forward (ดู VOL_FORECAST_PLAN.md) ---
def build_vol_forecast_cache(verbose: bool = True) -> tuple[pd.DataFrame, pd.DataFrame]:
    """รัน walk-forward ทุก MSCI index (28 ตัว) -> เขียน backtest + forecast ล่าสุด ลง cache."""
    from analysis import vol_forecast as vf   # lazy: arch ถูก import เฉพาะตอน build จริง

    scopes = [("country", msci_index.load_country_index(), config.MSCI_COUNTRY_COLS),
              ("sector", msci_index.load_sector_index(), config.MSCI_SECTOR_COLS)]
    bt_frames, latest_rows = [], []
    for scope, levels, cols in scopes:
        ret = msci_index.to_daily_return(levels)
        for ix in cols:
            s = ret[ix].dropna()
            df = vf.walk_forward_backtest(s, ix)
            df["scope"] = scope
            bt_frames.append(df)
            garch_l, fb = vf.garch_forecast(s)     # forecast ล่าสุด (ใช้ข้อมูลทั้งหมด)
            latest_rows.append({
                "scope": scope, "index": ix, "asof": s.index[-1],
                "last_realized": vf.realized_vol(s.iloc[-config.VOL_FORECAST_HORIZON:]),
                "ewma_forecast": vf.ewma_forecast(s), "garch_forecast": garch_l, "garch_fallback": fb,
            })
            if verbose:
                print(f"  {scope}/{ix}: {len(df)} windows fb={int(df['garch_fallback'].sum())}")

    backtest = pd.concat(bt_frames, ignore_index=True)
    latest = pd.DataFrame(latest_rows)
    os.makedirs(config.CACHE_DIR, exist_ok=True)
    _atomic_csv(backtest, VOL_BACKTEST_CSV)
    _atomic_csv(latest, VOL_LATEST_CSV)
    if verbose:
        print(f"saved vol cache: backtest={backtest.shape} latest={latest.shape}")
    return backtest, latest


# --- Filtered Scatter (หน้า 5) — snapshot ระดับ index ---
def _load_index_snapshot() -> pd.DataFrame:
    """return 21 วันล่าสุด (ราคาดิบ) + forecast vol ล่าสุด ต่อ index ทั้ง 28 ตัว.

    คำนวณสด ไม่ cache ลง disk — ไฟล์ MSCI เล็ก (1456×28) โหลด <1 วิ
    vol ใช้คอลัมน์ garch_forecast จาก cache หน้า 4 (GARCH(1,1) Student-t)
    """
    cty = msci_index.load_country_index()
    sec = msci_index.load_sector_index()
    scope_map = {c: "country" for c in cty.columns}
    scope_map.update({c: "sector" for c in sec.columns})
    levels = pd.concat([cty, sec], axis=1)

    vol_latest = _load_vol_latest().set_index(["scope", "index"])
    rows = []
    for ix in levels.columns:
        scope = scope_map[ix]
        rows.append({
            "scope": scope, "index": ix,
            "return_21d": metrics.recent_return(levels[ix]),
            # หน้า 8 ใช้ momentum แบบข้ามเดือนล่าสุด (t−252 ถึง t−21) — index มีข้อมูลครบทุกวันทำการ
            # จึงปิด gap guard (ช่วง 252 วันทำการกินเวลาจริง ~1 ปีปฏิทิน เกินเกณฑ์ 60 วันเสมอ)
            config.SCORE_RETURN_COL: metrics.recent_return(
                levels[ix], window=config.SCORE_RETURN_WINDOW, max_gap_days=None,
                skip=config.SCORE_RETURN_SKIP),
            # ตัวหารคะแนนโซนหน้า 8 (§12.14): realized vol ช่วงเดียวกับ momentum · vol_forecast คงไว้ให้หน้า 5
            config.SCORE_VOL_COL: screening.realized_vol_window(levels[ix]),
            "vol_forecast": float(vol_latest.loc[(scope, ix), "garch_forecast"]),
            # ติดธงไว้: ถ้า GARCH fit ไม่ผ่าน ค่าที่ได้จริงคือ EWMA fallback ไม่ใช่ GARCH
            "garch_fallback": bool(vol_latest.loc[(scope, ix), "garch_fallback"]),
            # หน้า 5 เช็คว่า vol forecast เป็นรุ่นเดียวกับ MSCI ไหม (cache หน้า 4 ไม่ rebuild ตามไฟล์ MSCI อัตโนมัติ)
            "vol_asof": vol_latest.loc[(scope, ix), "asof"],
            "msci_last": levels[ix].last_valid_index(),
        })
    return pd.DataFrame(rows)


# --- Style Factor Match (หน้า 6) — scope "style" เฉพาะกอง E (ดู docs/pages/6-style-match.md) ---
def policy_universe(results: pd.DataFrame, policy: str) -> list[str]:
    """กองที่ผ่าน pipeline หลักแล้วและเป็น policy นี้ (ตั้งแต่ 2026-09-29 pipeline กรอง APP_POLICY ให้แล้ว)."""
    return sorted(results.loc[results["policy"] == policy, "FundCode"])


def style_universe(results: pd.DataFrame) -> list[str]:
    """กองที่เข้า scope style = policy E ที่ผ่าน pipeline หลักแล้ว (F/O ไม่มีความหมายกับ style factor)."""
    return policy_universe(results, config.STYLE_POLICY)


def style_match_one(fund_nav: pd.Series, regressors: pd.DataFrame) -> tuple[dict, dict]:
    """regress กองหนึ่งกับ [control ×3 + style ×4] -> (แถวผล style, ผล match_exposure ดิบ).

    - ใช้ build_fund_returns / match_exposure ของเดิม (ElasticNet + standardize ใน pipeline)
    - primary/secondary จัดจาก **4 style เท่านั้น** — control 3 ตัว (ตลาดโลก MSCI + ETF, US ชนะโลก) ไม่ถูกนับ
    - ป้ายตามเครื่องหมาย coef (style_factor.style_label) เช่น Value ติดลบ = Growth
    - style_r2 = **incremental R²** จาก OLS nested: R²(control+style) − R²(control) -> ≥ 0 เสมอ
    - mkt_beta = beta ตลาดรวม (MSCI_ACWI + ACWI_ETF) จากโมเดล OLS ที่มีแค่ control
    """
    ctrl, style = config.STYLE_CONTROL_COLS, config.STYLE_FACTOR_COLS
    aligned = matching.build_fund_returns(fund_nav, regressors[ctrl + style])
    if len(aligned) < config.MIN_REGRESSION_OBS:
        raise ValueError(f"in-window obs {len(aligned)} < {config.MIN_REGRESSION_OBS}")
    res = matching.match_exposure(aligned, alternatives=False)   # ใช้แค่ ElasticNet — Lasso/Ridge ไม่มีใครอ่าน
    coef = res["coef"][style]
    primary, secondary = matching.classify_exposure(coef, band_pct=config.STYLE_SECONDARY_BAND_PCT)
    r2_full, r2_ctrl, _, ols_ctrl = matching.nested_r2(aligned, ctrl, style)
    row = {
        "n_obs_style": len(aligned),
        "style_primary": style_factor.style_label(primary, coef[primary]) if primary else None,
        "style_primary_factor": primary,
        "style_primary_coef": float(coef[primary]) if primary else np.nan,
        "style_secondary": ", ".join(style_factor.style_label(s, coef[s]) for s in secondary) or None,
        # nan_to_num: R² ไม่นิยาม (return คงที่) -> 0 ไม่ใช่ NaN (max(nan, 0) = nan -> กองหายจาก filter หน้า 6)
        "style_r2": max(float(np.nan_to_num(r2_full - r2_ctrl)), 0.0),
        "style_r2_full": r2_full,
        # beta ตลาดรวมจากโมเดล **control อย่างเดียว** — ในโมเดลเต็ม style relative มีขาตลาดในตัว
        # (LowVol_rel beta −0.49 ต่อ ACWI_ETF) coef ตลาดตรงนั้นจึงเป็น partial beta ไม่ใช่ความไวจริงของกอง
        "mkt_beta": float(sum(ols_ctrl[c] for c in config.STYLE_MARKET_COLS)),
    }
    return row, res


def build_style_pipeline(verbose: bool = True) -> tuple[pd.DataFrame, pd.DataFrame]:
    """หน้า 6: กอง E × [control + style] -> cache/style_results.csv + cache/style_coefs.csv.

    แยกไฟล์จาก results/coefs เดิมโดยตั้งใจ (additive ล้วน ไม่เปลี่ยน schema ที่หน้า 1-5 ใช้)
    ต้องมี base_data/STYLE_FACTOR_ETF.csv ก่อน — ไม่มี -> style_factor.SnapshotMissingError พร้อมคำสั่ง (ไม่ดึงเน็ตเอง)
    """
    regs = style_factor.load_style_regressors()
    funds = style_universe(_load_results())
    if verbose:
        print(f"style: {len(funds)} กอง {config.STYLE_POLICY} · regressors={list(regs.columns)} · loading nav...")
    nav_by_fund = _load_clean_nav(funds)               # NAV clean ชุดเดียวกับ build_pipeline (parquet)

    rows, coef_rows, skipped = [], [], []
    for i, f in enumerate(funds):
        try:
            row, res = style_match_one(nav_by_fund[f], regs)
        except Exception as e:  # noqa: BLE001 — กองเดียวพลาด ไม่ให้ล้มทั้งชุด
            skipped.append((f, str(e)))
            continue
        rows.append({"FundCode": f, **row})
        for ix in config.STYLE_CONTROL_COLS + config.STYLE_FACTOR_COLS:
            coef_rows.append({
                "FundCode": f, "index": ix,
                # scope แยก "style" กับ "style_control" -> get_index_matches(coefs, ix, "style",
                #   band_pct=config.STYLE_SECONDARY_BAND_PCT) ไม่หยิบ control มาจัดอันดับ (ชื่อยังไม่ติดเครื่องหมาย -> style_label)
                "scope": "style_control" if ix in config.STYLE_CONTROL_COLS else "style",
                "elastic": float(res["coef"][ix]),
            })
        if verbose and (i + 1) % 50 == 0:
            print(f"  ...{i + 1}/{len(funds)} funds")

    if verbose and skipped:
        print(f"skipped {len(skipped)} funds: {skipped[:5]}")
    results = pd.DataFrame(rows)
    coefs = pd.DataFrame(coef_rows)
    _write_cache(results, coefs, STYLE_RESULTS_CSV, STYLE_COEFS_CSV, skipped)
    if verbose:
        print(f"saved style: results={results.shape} coefs={coefs.shape}")
    return results, coefs


# --- Macro Chain (หน้า 7) — implied (chain ผ่าน country/sector) คู่ direct (regress NAV ตรง) เฉพาะกอง E ---
def macro_match_one(fund_nav: pd.Series, coef_std: dict[str, pd.Series], levels_by_scope: dict[str, pd.DataFrame],
                    B: pd.DataFrame, macro_m: pd.DataFrame, start, end) -> list[dict]:
    """กองหนึ่ง -> แถว loading 7 factor × 2 วิธี (implied / direct).

    coef_std        : {scope: standardized ElasticNet coef (index -> coef)} จาก coefs.csv
    levels_by_scope : {scope: MSCI level} ชุดเดียวกับที่ build_pipeline ใช้ fit coef นั้น -> σ ตรงกับตอน fit
    implied = unstandardize ทีละ scope -> chain กับ Stage 1 -> เฉลี่ย 2 scope (ดู analysis/macro_chain.py)
    direct  = OLS return รายเดือนของกอง ~ macro (< MACRO_MIN_MONTHS เดือน -> NaN)
    r2      : implied = corr² ของค่าที่ chain ทำนายกับ return จริง (ไม่ fit กับกอง) · direct = R² ของ OLS
    """
    raw = {}
    for scope, lv in levels_by_scope.items():
        if set(coef_std[scope].index) != set(lv.columns):     # chain ตาม label -> ชุด index ต้องครบตรงกัน
            raise ValueError(f"{scope}: coef มี {len(coef_std[scope])} index ไม่ตรงกับ MSCI {lv.shape[1]} ตัว")
        aligned = matching.build_fund_returns(fund_nav, lv)
        if len(aligned) < config.MIN_REGRESSION_OBS:   # guard เดียวกับ build_pipeline/style_match_one
            raise ValueError(f"{scope}: in-window obs {len(aligned)} < {config.MIN_REGRESSION_OBS}")
        raw[scope] = macro_chain.unstandardize(coef_std[scope], aligned)
    implied = macro_chain.implied_loadings(raw, B)
    fund_m = macro_chain.month_end_levels(fund_nav.sort_index(), start, end).pct_change()
    direct, r2_direct, n = macro_chain.ols_loadings(fund_m, macro_m, config.MACRO_MIN_MONTHS)
    r2_implied, _ = macro_chain.implied_fit_r2(fund_m, macro_m, implied, config.MACRO_MIN_MONTHS)
    sd = macro_m.std()
    return [{"method": method, "factor": fac, "loading": float(load[fac]),
             "impact_1sd": float(load[fac] * sd[fac]), "r2": r2, "n_months": n}
            for method, load, r2 in [("implied", implied, r2_implied), ("direct", direct, r2_direct)]
            for fac in config.MACRO_FACTOR_COLS]


def build_macro_pipeline(verbose: bool = True) -> tuple[pd.DataFrame, pd.DataFrame]:
    """หน้า 7: Stage 1 (28 index ~ macro) + loading กอง E -> cache/macro_loadings.csv + macro_index_betas.csv.

    เฉพาะกอง config.MACRO_POLICY (E) เหมือนหน้า 6 — implied มองผ่าน index หุ้น จึงมองไม่เห็นบอนด์/ทองของกอง F/O
    ต้องมี base_data/MACRO_FACTOR.csv (ไม่มี -> SnapshotMissingError) และ results/coefs.csv (อ่าน coef ของกอง)
    ช่วงเวลา = ช่วงร่วมของ MSCI กับ snapshot · เดือนสุดท้ายที่ยังไม่จบถูกทิ้ง (month_end_levels)
    """
    snap = macro_factor.load_snapshot()
    levels_by_scope = {"country": msci_index.load_country_index(), "sector": msci_index.load_sector_index()}
    start = max(lv.index.min() for lv in levels_by_scope.values())
    end = min([lv.index.max() for lv in levels_by_scope.values()] + [snap.apply(pd.Series.last_valid_index).min()])
    macro_m = macro_factor.to_factor_changes(macro_chain.month_end_levels(snap, start, end))
    idx_m = macro_chain.month_end_levels(pd.concat(levels_by_scope.values(), axis=1), start, end).pct_change().iloc[1:]
    B, r2_idx, n_idx = macro_chain.stage1_betas(idx_m, macro_m)
    sd = macro_m.std()
    scope_of = {ix: s for s, lv in levels_by_scope.items() for ix in lv.columns}
    betas = pd.DataFrame([{"index": ix, "scope": scope_of[ix], "factor": fac, "beta": B.loc[ix, fac],
                           "impact_1sd": B.loc[ix, fac] * sd[fac], "factor_sd": sd[fac],
                           "r2": r2_idx[ix], "n_obs": n_idx[ix]} for ix in B.index for fac in B.columns])
    if verbose:
        print(f"macro: {len(macro_m)} เดือน ({macro_m.index.min():%Y-%m} -> {macro_m.index.max():%Y-%m}) · "
              f"Stage 1 R² เฉลี่ย {r2_idx.mean():.3f} · loading nav...")

    funds = policy_universe(_load_results(), config.MACRO_POLICY)
    coef_by = _load_coefs().set_index(["FundCode", "scope", "index"])["elastic"].sort_index()
    nav_by_fund = _load_clean_nav(funds)

    rows, skipped = [], []
    for f in funds:
        try:
            coef_std = {s: coef_by.loc[(f, s)] for s in levels_by_scope}
            rows += [{"FundCode": f, **r} for r in
                     macro_match_one(nav_by_fund[f], coef_std, levels_by_scope, B, macro_m, start, end)]
        except Exception as e:  # noqa: BLE001 — กองเดียวพลาด ไม่ให้ล้มทั้งชุด
            skipped.append((f, str(e)))

    if verbose and skipped:
        print(f"skipped {len(skipped)} funds: {skipped[:5]}")
    loadings = pd.DataFrame(rows)
    _write_cache(loadings, betas, MACRO_LOADINGS_CSV, MACRO_INDEX_BETAS_CSV, skipped)
    if verbose:
        print(f"saved macro: loadings={loadings.shape} index_betas={betas.shape}")
    return loadings, betas


# --- Score Screening (หน้า 8) — match กับ country ชุด VIF-cleaned (ดู docs/pages/8-score-screen.md) ---
def build_score_matches(verbose: bool = True) -> pd.DataFrame:
    """refit กอง E กับ country ชุด VIF-cleaned 11 ตัว -> cache/country_matches_clean11.csv.

    ทำไมต้อง refit: primary/secondary ใน results.csv มาจากชุด 18 ตัวที่ collinear กันเอง (WORLD_EX_US ~ EUROPE 0.93)
    ElasticNet จึงแบ่งน้ำหนักเป็นบวกแรง/ลบแรง -> secondary ติดลบ ~25% ของกอง ซึ่งทำให้ score ของหน้า 8 ผิดทิศ
    (คะแนน "โซนดี" ไปคูณกับกองที่จริงๆ เคลื่อนสวน index นั้น) — ชุด cleaned แก้ที่ต้นเหตุ โดยไม่แตะ results/coefs เดิม
    sector ไม่ต้อง clean (ตัด IN ตัวเดียวก็ยัง VIF 5.9 ไม่คุ้ม) จึงใช้ผลเดิมจาก results.csv เสมอ
    """
    funds = policy_universe(_load_results(), config.SCORE_POLICY)
    cty = msci_index.load_country_index()[config.SCORE_COUNTRY_CLEAN]
    if verbose:
        print(f"score: refit {len(funds)} กอง {config.SCORE_POLICY} × country {cty.shape[1]} ตัว (VIF-cleaned) · loading nav...")
    nav_by_fund = _load_clean_nav(funds)

    rows, skipped = [], []
    for f in funds:
        try:
            aligned = matching.build_fund_returns(nav_by_fund[f], cty)
            if len(aligned) < config.MIN_REGRESSION_OBS:
                raise ValueError(f"in-window obs {len(aligned)} < {config.MIN_REGRESSION_OBS}")
            res = matching.match_exposure(aligned, alternatives=False)
        except Exception as e:  # noqa: BLE001 — กองเดียวพลาด ไม่ให้ล้มทั้งชุด
            skipped.append((f, str(e)))
            continue
        rows.append({"FundCode": f, "country_primary": res["primary"],
                     "country_secondary": res["secondary"], "country_r2": res["r2"],
                     "country_primary_coef": res["primary_coef"], "country_secondary_coef": res["secondary_coef"]})

    matches = pd.DataFrame(rows)
    if matches.empty:
        raise RuntimeError(f"ไม่มีกองไหนผ่านเลย — ไม่เขียนทับ {os.path.basename(SCORE_MATCHES_CLEAN_CSV)} "
                           f"(ตัวอย่างที่พลาด: {skipped[:3]})")
    os.makedirs(config.CACHE_DIR, exist_ok=True)
    _atomic_csv(matches, SCORE_MATCHES_CLEAN_CSV)
    if verbose:
        print(f"saved score matches: {matches.shape} (skipped {len(skipped)})")
    return matches


def _secondary_coef(scope: str) -> pd.DataFrame:
    """coef (มีเครื่องหมาย) ของ secondary ต่อกอง จาก cache/coefs.csv (long format).

    ใช้ตรวจ band ของหน้า 8 (screening.py::_passes_band) — ต้องมีเครื่องหมายจริง ไม่ใช่ |coef|
    คืน DataFrame [FundCode, <scope>_secondary_coef] · กองที่ไม่มี secondary จะไม่มีแถว -> merge left ได้ NaN
    """
    coefs = _load_coefs()
    sub = coefs[(coefs["scope"] == scope) & (coefs["is_secondary"] == True)]  # noqa: E712
    return sub[["FundCode", "elastic"]].rename(columns={"elastic": f"{scope}_secondary_coef"})


def score_matches(clean_country: bool) -> pd.DataFrame:
    """match ต่อกอง E สำหรับหน้า 8 — sector ใช้ผลเดิมเสมอ · country เลือกชุด 18 เดิม หรือ 11 ตัวที่ clean แล้ว.

    รวม *_primary_coef / *_secondary_coef (มีเครื่องหมาย) ด้วย — screening.py::fund_scores ใช้เช็คว่า secondary
    อยู่ในทิศทาง/แรงพอที่จะใช้เป็น fallback ได้ไหม (SCORE_SECONDARY_BAND_PCT, ตัดสินใจ 2026-09-29)
    """
    res = _load_results()
    res = res[res["policy"] == config.SCORE_POLICY]
    cols = ["FundCode", "FundName", "sector_primary", "sector_secondary", "sector_primary_coef", "sector_r2"]
    if not clean_country:
        out = res[cols + ["country_primary", "country_secondary", "country_primary_coef", "country_r2"]].copy()
        out = out.merge(_secondary_coef("country"), on="FundCode", how="left")
    else:
        out = res[cols].merge(_load_score_matches_clean(), on="FundCode", how="inner")
    out = out.merge(_secondary_coef("sector"), on="FundCode", how="left")
    return out.reset_index(drop=True)


# --- Portfolio / Efficient Frontier (หน้า 8 ส่วนที่ 3) — fit สดเฉพาะกองที่เลือก ไม่เก็บ cache ลงดิสก์ ---
def portfolio_risk_model(fund_codes: tuple[str, ...], country_cols: tuple[str, ...] | None = None
                         ) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Σ = B·F·Bᵀ + D ของกองที่เลือก (หน้าต่าง rolling ล่าสุดตาม PORTFOLIO_LOOKBACK_DAYS) -> (Σ, ตารางข้อมูลต่อกอง).

    - factor set ตาม toggle ของหน้า 8: country ที่ส่งมา (11 หรือ 18) + sector 10 ตัวเสมอ
      -> ต้องเป็นชุดเดียวกับที่ใช้คัด Top 5 ไม่งั้น exposure กับเหตุผลที่เลือกกองไม่สอดคล้องกัน
    - fit สดต่อครั้ง (กองน้อย เร็วพอ) แทนการ build cache 313 กอง เพราะ Σ ผูกกับ "หน้าต่างล่าสุด ณ วันคำนวณ"
      cache ลงดิสก์จะเก่าทันทีที่ข้อมูลขยับ (บทเรียนจาก code review หน้า 7)
    - B ได้จาก match_exposure เดิม แล้ว unstandardize (coefs เป็น standardized) ด้วย macro_chain.unstandardize
    """
    cty = msci_index.load_country_index()
    if country_cols:
        cty = cty[list(country_cols)]
    levels = pd.concat([cty, msci_index.load_sector_index()], axis=1).iloc[-config.PORTFOLIO_LOOKBACK_DAYS:]
    factor_cov = portfolio.factor_covariance(levels.pct_change())

    nav_by_fund = _load_clean_nav(list(fund_codes))
    betas, idio, info = {}, {}, {}
    for f in fund_codes:
        aligned = matching.build_fund_returns(nav_by_fund[f], levels)
        if len(aligned) < config.MIN_REGRESSION_OBS:
            raise ValueError(f"{f}: in-window obs {len(aligned)} < {config.MIN_REGRESSION_OBS}")
        res = matching.match_exposure(aligned, alternatives=False)
        fund_ret = aligned[matching.FUND_COL]
        # variance ต่อจุด NAV × จำนวนจุดต่อปีจริง (ไม่ใช่ ×252) · ใช้ return winsorize ชุดเดียวกับที่ได้ R² -> D สอดคล้องกับ fit
        stats = matching.fund_return_stats(nav_by_fund[f], levels)
        total_var = float(fund_ret.var(ddof=1) * stats["periods_per_year"])
        betas[f] = macro_chain.unstandardize(res["coef"], aligned)
        idio[f] = max(total_var * (1.0 - res["r2"]), 0.0)     # clip: R² > 1 ไม่เกิด แต่กัน floating error
        info[f] = {"r2": res["r2"], "ann_vol_win": total_var ** 0.5,
                   "ann_return_win": stats["ann_return"],
                   "idio_vol": idio[f] ** 0.5, "n_obs": len(aligned)}

    b = pd.DataFrame(betas).T[levels.columns]
    sigma = portfolio.fund_covariance(b, factor_cov, pd.Series(idio))
    return sigma, pd.DataFrame(info).T


# --- TF Portfolio (หน้า 9) — โมเดล M004-TF-FX (ดู docs/pages/9-tf-portfolio.md) ---
TF_CURVES_CSV = os.path.join(config.CACHE_DIR, f"{config.TF_CACHE_PREFIX}_curves.csv")
TF_METRICS_CSV = os.path.join(config.CACHE_DIR, f"{config.TF_CACHE_PREFIX}_metrics.csv")
TF_HOLDINGS_CSV = os.path.join(config.CACHE_DIR, f"{config.TF_CACHE_PREFIX}_holdings.csv")
TF_QUARTERS_CSV = os.path.join(config.CACHE_DIR, f"{config.TF_CACHE_PREFIX}_quarters.csv")
TF_META_JSON = os.path.join(config.CACHE_DIR, f"{config.TF_CACHE_PREFIX}_meta.json")
TF_CACHE_FILES = (TF_CURVES_CSV, TF_METRICS_CSV, TF_HOLDINGS_CSV, TF_QUARTERS_CSV, TF_META_JSON)
# ไฟล์ข้อมูลทุกไฟล์ที่ผล TF ขึ้นอยู่ด้วย — เก็บ sha1 ของเนื้อหาไว้ใน meta (ตรวจความเก่า) · mtime ใช้เป็น stamp ของ st.cache_data
TF_INPUT_FILES = (config.NAV_CLEAN_PARQUET, config.MSCI_COUNTRY_CSV, config.MSCI_SECTOR_CSV, config.SHARE_CLASS_CSV,
                  config.SEC_FUND_FEE_CSV, config.FUND_PROFILE_CSV, config.TF_M001_REFERENCE_CSV)
TF_MODEL_CONFIG_EXTRA = ("NAV_STALE_MAX_DAYS",)   # ค่า config นอกบล็อก TF_* ที่โมเดลใช้ (universe_at)
# ค่า TF_* ที่ใช้แสดงผลส่วนที่ 2 (ไฟล์อ้างอิงคงที่) ไม่ได้ไหลเข้า cache — แก้แล้วต้องไม่ทำให้ cache ดูเก่า
TF_DISPLAY_CONFIG_PREFIX = "TF_TOP3_"


def _tf_config_fingerprint() -> str:
    """hash ของค่า config ที่โมเดลหน้า 9 ใช้ (TF_* + TF_MODEL_CONFIG_EXTRA) — ไม่รวมค่าที่เป็น path และค่าแสดงผล TF_TOP3_*
    (ย้าย/clone โฟลเดอร์โปรเจกต์ต้องไม่ทำให้ cache ดูเก่า · เนื้อหาไฟล์ตรวจด้วย sha1 ของ TF_INPUT_FILES แทน)."""
    import hashlib
    keys = [k for k in dir(config) if k.startswith("TF_") and not k.endswith("_CSV")
            and not k.startswith(TF_DISPLAY_CONFIG_PREFIX)] + list(TF_MODEL_CONFIG_EXTRA)
    items = sorted((k, repr(getattr(config, k))) for k in keys)
    return hashlib.sha1(repr(items).encode()).hexdigest()[:12]


def _tf_input_hashes() -> dict[str, str | None]:
    """sha1 ของเนื้อหาไฟล์ข้อมูลแต่ละไฟล์ (ไม่มีไฟล์ = None) — ไม่ใช้ mtime เพราะ git checkout/clone/copy เปลี่ยน mtime
    ทั้งที่เนื้อหาเท่าเดิม (เคยทำให้หน้า 9 เตือนว่า cache เก่าทุกไฟล์ 2026-10-07)."""
    import hashlib
    out = {}
    for p in TF_INPUT_FILES:
        if not os.path.exists(p):
            out[os.path.basename(p)] = None
            continue
        h = hashlib.sha1()
        with open(p, "rb") as f:
            for block in iter(lambda: f.read(1 << 20), b""):
                h.update(block)
        out[os.path.basename(p)] = h.hexdigest()
    return out


def _tf_inputs() -> tf_model.ModelInputs:
    """NAV ทุกกองจาก nav_clean.parquet (รวมกองที่เลิก/หยุดรายงาน — universe ตามเวลาคัดเอง) + ปฏิทิน/ACWI."""
    nav = pd.read_parquet(config.NAV_CLEAN_PARQUET, columns=[FUND, NAVDATE, config.NAV_COL, config.NAV_AUM_COL])
    nav = nav.rename(columns={FUND: "FundCode", NAVDATE: "NAVDate", config.NAV_COL: "NAV", config.NAV_AUM_COL: "AUM"})
    nav["NAVDate"] = pd.to_datetime(nav["NAVDate"])
    cty = msci_index.load_country_index()
    calendar = cty.index.union(msci_index.load_sector_index().index).sort_values()
    return tf_model.ModelInputs(nav=nav, calendar=calendar, trend_index=cty[config.TF_TREND_INDEX],
                                groups=share_class_groups())


def _tf_metric_rows(series: str, cases: dict) -> list[dict]:
    rows = []
    for case, (values, entries) in cases.items():
        years = (values.index[-1] - values.index[0]).days / config.DAYS_PER_YEAR
        rows.append({"series": series, "case": case, **fund_backtest.summarize(values, config.TF_RF_SIM),
                     "cost_pct_yr": sum(x["cost"] for x in entries) / years if years > 0 else np.nan,
                     "turnover_yr": sum(x["turnover"] for x in entries[1:]) / years if years > 0 else np.nan})
    return rows


def build_tf_cache(verbose: bool = True) -> dict:
    """walk-forward backtest + replay สถานะถือครองของโมเดลหน้า 9 -> cache/tf_portfolio_*.

    - backtest: rebalance ทุกสิ้นไตรมาสตั้งแต่ TF_START_Q ที่วันซื้อขาย ≤ TF_EVAL_END (ไม่ข้ามไตรมาสใด — ตรงกับผลของทีม quant)
    - replay: ทุกสิ้นไตรมาสถึงข้อมูลล่าสุด · หลัง TF_COVERAGE_REF ไตรมาสที่กองสด < TF_COVERAGE_MIN × กองสด ณ วันอ้างอิง
      ถูกข้าม (คงสถานะเดิม) เพราะ NAV ปี 2026 ขาดหลายร้อยกอง
    - ค่าธรรมเนียม 3 กรณี: flat 0.5%/ข้าง · full ค่าธรรมเนียมจริง · nofront ยกเว้น front-end
    """
    import json
    from analysis.fund_fees import FeeData

    inp = _tf_inputs()
    cal = inp.calendar
    eval_end = pd.Timestamp(config.TF_EVAL_END)
    all_q = tf_model.complete_quarters(cal, config.TF_START_Q, cal.max())
    bt_q = [t for t in all_q if (fund_backtest.execution_date(cal, t) or eval_end + pd.Timedelta(days=1)) <= eval_end]
    if verbose:
        print(f"tf: backtest {len(bt_q)} ไตรมาส {bt_q[0].date()}..{bt_q[-1].date()} · replay ถึง {all_q[-1].date()}")

    ref_t = pd.Timestamp(config.TF_COVERAGE_REF)
    u_ref = fund_backtest.universe_at(inp.nav, ref_t)
    coverage_ref = int(((ref_t - u_ref["last_nav_date"]).dt.days <= config.TF_FRESH_DAYS).sum())
    replay = tf_model.walk_forward(inp, all_q, coverage_ref=coverage_ref)
    backtest = replay[:len(bt_q)]            # ก่อน TF_COVERAGE_REF ไม่มีการข้าม -> เหมือน walk_forward(bt_q)
    assert not any(r["skipped"] for r in backtest), "ไตรมาสใน backtest ห้ามถูกข้าม"

    fee_data = FeeData(sorted(inp.nav["FundCode"].unique()))
    model_cases = tf_model.run_cases(inp, tf_model.build_plan(backtest, cal), fee_data)
    b0_cases = tf_model.run_cases(inp, tf_model.b0_plan(inp, bt_q), fee_data)

    curves = []
    for series, cases in ((config.TF_MODEL_ID, model_cases), ("B0", b0_cases)):
        for case, (values, _) in cases.items():
            curves.append(pd.DataFrame({"date": values.index, "series": series, "case": case, "value": values.values}))
    m001 = pd.read_csv(config.TF_M001_REFERENCE_CSV, comment="#", parse_dates=["date"])
    curves.append(m001.assign(series="M001"))
    curves = pd.concat(curves, ignore_index=True)

    metrics_rows = _tf_metric_rows(config.TF_MODEL_ID, model_cases) + _tf_metric_rows("B0", b0_cases)
    for case, g in m001.groupby("case"):
        v = g.set_index("date")["value"]
        metrics_rows.append({"series": "M001", "case": case, **fund_backtest.summarize(v, config.TF_RF_SIM)})
    metrics_df = pd.DataFrame(metrics_rows)

    holdings = tf_model.holdings_frame(replay, cal)
    quarters = tf_model.quarter_log(replay)
    quarters["in_backtest"] = quarters["t"].isin(bt_q)
    if holdings.empty or metrics_df.empty:
        raise RuntimeError("ผล TF ว่าง — ไม่เขียนทับ cache")

    os.makedirs(config.CACHE_DIR, exist_ok=True)
    for df, path in ((curves, TF_CURVES_CSV), (metrics_df, TF_METRICS_CSV), (holdings, TF_HOLDINGS_CSV),
                     (quarters, TF_QUARTERS_CSV)):
        _atomic_csv(df, path)
    meta = {"built_at": pd.Timestamp.now().isoformat(timespec="seconds"),
            "nav_max_date": str(inp.nav["NAVDate"].max().date()), "msci_last": str(cal.max().date()),
            "input_sha1": _tf_input_hashes(), "coverage_ref": coverage_ref,
            "config": _tf_config_fingerprint(), "fee_median": fee_data.median,
            "fee_median_fallback": fee_data.median_fallback,
            # เหตุการณ์ระหว่างจำลอง (ค่าธรรมเนียมจริง): กองที่ซื้อไม่ได้ (ส่วนนั้นถือเงินสด) / ถือกองที่ NAV ค้างนาน
            "sim_events": [{"t": str(x["t"].date()), "cannot_buy": x["cannot_buy"], "stale_marks": x["stale_marks"]}
                           for x in model_cases["full"][1] if x["cannot_buy"] or x["stale_marks"]]}
    def _dump(tmp):
        with open(tmp, "w") as f:
            json.dump(meta, f, ensure_ascii=False, indent=1)
    _atomic_write(TF_META_JSON, _dump)            # meta เขียนท้ายสุด = ตัวบอกว่า build ครบ
    if verbose:
        m = metrics_df.set_index(["series", "case"])["sharpe"]
        print(f"tf: Sharpe {config.TF_MODEL_ID} flat {m[(config.TF_MODEL_ID, 'flat')]:.4f} · "
              f"full {m[(config.TF_MODEL_ID, 'full')]:.4f} · nofront {m[(config.TF_MODEL_ID, 'nofront')]:.4f}")
    return meta


def load_tf_cache() -> dict:
    """{curves, metrics, holdings, quarters, meta, stale} — ไม่มี cache = build ก่อน."""
    import json
    if not all(os.path.exists(p) for p in TF_CACHE_FILES):
        build_tf_cache(verbose=False)
    with open(TF_META_JSON) as f:
        meta = json.load(f)
    stale = []
    if meta.get("config") != _tf_config_fingerprint():
        stale.append("ค่า config ของโมเดล (TF_* / NAV_STALE_MAX_DAYS) เปลี่ยนหลังสร้าง cache")
    recorded = meta.get("input_sha1")
    if recorded is None:   # ไม่มีเลย หรือรุ่นที่บันทึกแค่ mtime ("inputs")
        stale.append("cache รุ่นเก่าที่ไม่ได้บันทึกที่มาของข้อมูล")
    else:
        changed = [name for name, h in _tf_input_hashes().items() if h != recorded.get(name)]
        if changed:
            stale.append("ไฟล์ข้อมูลเปลี่ยนหลังสร้าง cache: " + ", ".join(changed))
    return {"curves": pd.read_csv(TF_CURVES_CSV, parse_dates=["date"]),
            "metrics": pd.read_csv(TF_METRICS_CSV),
            "holdings": pd.read_csv(TF_HOLDINGS_CSV, parse_dates=["t", "e"], keep_default_na=False,
                                    na_values={"weight": [""]}).astype({"skipped": bool}),
            "quarters": pd.read_csv(TF_QUARTERS_CSV, parse_dates=["t"]),
            "meta": meta, "stale": stale}


TF_TOP3_FILES = (config.TF_TOP3_CURVES_CSV, config.TF_TOP3_METRICS_CSV)


def load_tf_top3() -> dict:
    """ผล backtest TOP3 + B0 สำหรับหน้า 9 ส่วนที่ 2 — ไฟล์อ้างอิงคงที่ (ไม่คำนวณในแอป เพราะ GC75/M012 อยู่ในเครื่องมือของทีม quant).

    curves: series, case, date, value (มูลค่าพอร์ตสิ้นเดือน) · metrics: series, case, sharpe, cagr, vol, max_dd, dsr, ci_lo, ci_hi, ...
    """
    curves = pd.read_csv(config.TF_TOP3_CURVES_CSV, comment="#", parse_dates=["date"])
    metrics = pd.read_csv(config.TF_TOP3_METRICS_CSV, comment="#")
    order = {s: i for i, s in enumerate(config.TF_TOP3_SERIES)}
    curves = curves[curves["series"].isin(order)].assign(_o=lambda d: d["series"].map(order))
    curves = curves.sort_values(["_o", "case", "date"]).drop(columns="_o").reset_index(drop=True)
    return {"curves": curves, "metrics": metrics[metrics["series"].isin(order)].reset_index(drop=True)}


GC75_FRONTIER_FILES = (config.GC75_FRONTIER_HOLDINGS_CSV, config.GC75_FRONTIER_WEEKLY_CSV, config.GC75_FRONTIER_REALIZED_CSV)


def load_gc75_frontier() -> dict:
    """พอร์ต M019-LC3-GCGOLD ทุกไตรมาส (หน้า 10 frontier + หน้า 9 ส่วนที่ 1) — ไฟล์อ้างอิงคงที่จากทีม quant (ไม่ได้คำนวณในแอป).

    holdings: t, e, FundCode, kind (E = หุ้น · G = ทอง · F = ตลาดเงิน), weight, family, sr12p, rank, rf
    · weekly: t, FundCode, week, ret (52 สัปดาห์ ≤ t · กองทองบางไตรมาสมี NaN)
    · realized (ไม่มีไฟล์ = None): t, portfolio, horizon (Q/1Y), cost, ret, ret_ann, vol_ann, sharpe, exp_*, weights (JSON) ...
    """
    holdings = pd.read_csv(config.GC75_FRONTIER_HOLDINGS_CSV, comment="#", parse_dates=["t", "e"])
    weekly = pd.read_csv(config.GC75_FRONTIER_WEEKLY_CSV, comment="#", parse_dates=["t", "week"])
    realized = (pd.read_csv(config.GC75_FRONTIER_REALIZED_CSV, comment="#", parse_dates=["t", "e", "end"])
                if os.path.exists(config.GC75_FRONTIER_REALIZED_CSV) else None)
    return {"holdings": holdings, "weekly": weekly, "realized": realized}


def tf_cache_ready() -> bool:
    """มี cache หน้า 9 ครบทุกไฟล์ไหม (ให้หน้าอื่นอ่านตัวเลขได้โดยไม่ต้อง build ใน request)."""
    return all(os.path.exists(p) for p in TF_CACHE_FILES)


def tf_asof_options(cache: dict) -> list[pd.Timestamp]:
    """วันที่ให้เลือกคำนวณพอร์ตแนะนำ: สิ้นไตรมาสตั้งแต่ TF_COVERAGE_REF + วันข้อมูล MSCI ล่าสุด (ถ้าไม่ใช่สิ้นไตรมาส)."""
    q = cache["quarters"]
    opts = list(q.loc[q["t"] >= pd.Timestamp(config.TF_COVERAGE_REF), "t"])
    last = pd.Timestamp(cache["meta"]["msci_last"])
    if last not in opts:
        opts.append(last)
    return sorted(opts)


def tf_live(as_of: str) -> dict:
    """พอร์ตแนะนำ ณ as_of จากสถานะถือครองของไตรมาส replay ล่าสุดก่อนหน้า (ข้อมูล ≤ as_of)."""
    cache = load_tf_cache()
    t = pd.Timestamp(as_of)
    held, prev_fb = tf_model.state_before(cache["holdings"], cache["quarters"], t)
    r = tf_model.select_at(_tf_inputs(), t, held, prev_fb)
    r["coverage"] = tf_model.coverage(r["n_fresh"], cache["meta"]["coverage_ref"])
    r["held_before"] = held
    return r


# --- UI layer (cached) ---
def _load_results() -> pd.DataFrame:
    if not os.path.exists(RESULTS_CSV):
        build_pipeline(verbose=False)
    return pd.read_csv(RESULTS_CSV)


def _load_coefs() -> pd.DataFrame:
    if not os.path.exists(COEFS_CSV):
        build_pipeline(verbose=False)
    return pd.read_csv(COEFS_CSV)


def _load_style_results() -> pd.DataFrame:
    if not os.path.exists(STYLE_RESULTS_CSV):
        build_style_pipeline(verbose=False)       # ไม่มี snapshot -> SnapshotMissingError พร้อมคำสั่ง
    return pd.read_csv(STYLE_RESULTS_CSV)


def _load_macro_loadings() -> pd.DataFrame:
    if not os.path.exists(MACRO_LOADINGS_CSV):
        build_macro_pipeline(verbose=False)       # ไม่มี snapshot -> SnapshotMissingError พร้อมคำสั่ง
    return pd.read_csv(MACRO_LOADINGS_CSV)


def _load_macro_index_betas() -> pd.DataFrame:
    if not os.path.exists(MACRO_INDEX_BETAS_CSV):
        build_macro_pipeline(verbose=False)
    return pd.read_csv(MACRO_INDEX_BETAS_CSV)


def share_class_groups() -> dict[str, str]:
    """{FundCode: กลุ่ม share class} จาก base_data/share_class_groups.csv (แก้ด้วยมือได้) · ไม่มีไฟล์ = {} (ไม่จัดกลุ่ม)."""
    if not os.path.exists(config.SHARE_CLASS_CSV):
        return {}
    g = pd.read_csv(config.SHARE_CLASS_CSV, encoding="utf-8-sig", dtype=str)
    return dict(zip(g["FundCode"].str.strip(), g["group"].str.strip()))


def _score_matches_clean_is_stale(clean: pd.DataFrame) -> bool:
    """cache ชุด 11 ต่างรุ่นกับ results.csv หรือ config ไหม — ต้อง refit ถ้า:
    results.csv ถูกเขียนหลัง clean11 (CLI รันแค่ build_pipeline / rebuild ล้มกลางทาง) · มีกองที่ไม่อยู่ใน universe ปัจจุบัน ·
    country ที่ match ได้หลุดจาก config.SCORE_COUNTRY_CLEAN (แก้ชุด 11 ใน config)."""
    if os.path.getmtime(SCORE_MATCHES_CLEAN_CSV) < os.path.getmtime(RESULTS_CSV):
        return True
    if not set(clean["FundCode"]) <= set(policy_universe(_load_results(), config.SCORE_POLICY)):
        return True
    used = set(clean["country_primary"].dropna()) | set(clean["country_secondary"].dropna())
    return not used <= set(config.SCORE_COUNTRY_CLEAN)


def _load_score_matches_clean() -> pd.DataFrame:
    if os.path.exists(SCORE_MATCHES_CLEAN_CSV) and os.path.exists(RESULTS_CSV):
        clean = pd.read_csv(SCORE_MATCHES_CLEAN_CSV)
        if not _score_matches_clean_is_stale(clean):
            return clean
    return build_score_matches(verbose=False)


def _load_vol_backtest() -> pd.DataFrame:
    if not os.path.exists(VOL_BACKTEST_CSV):
        build_vol_forecast_cache(verbose=False)
    return pd.read_csv(VOL_BACKTEST_CSV, parse_dates=["window_start", "window_end"])


def _load_vol_latest() -> pd.DataFrame:
    if not os.path.exists(VOL_LATEST_CSV):
        build_vol_forecast_cache(verbose=False)
    return pd.read_csv(VOL_LATEST_CSV, parse_dates=["asof"])


def _cache_stamp(paths: tuple[str, ...]) -> tuple:
    """ตัวระบุรุ่นของข้อมูล: mtime ของไฟล์ที่ฟังก์ชันอ่าน + ค่า config ทั้งหมด (ตัวพิมพ์ใหญ่).

    st.cache_data ใช้แค่ source ของฟังก์ชัน + argument เป็น key -> ไฟล์ cache ที่ CLI เขียนใหม่ หรือค่า config ที่แก้ระหว่าง
    server รันอยู่ จะไม่ทำให้ cache หมดอายุ (review หน้า 8: results/score_matches คนละรุ่น -> KeyError) · ส่ง stamp เป็น argument แทน
    """
    files = tuple(os.path.getmtime(p) if os.path.exists(p) else None for p in (*paths, *_CODE_FILES))
    settings = tuple((k, repr(getattr(config, k))) for k in sorted(dir(config)) if k.isupper())
    return files, hash(settings)


# โค้ดที่ getter ทุกตัวพึ่ง — mtime อยู่ใน stamp ด้วย: แก้ analysis/*.py ระหว่าง server รันแล้ว cache หมดอายุเอง
# (key ของ st.cache_data ผูกกับ source ของฟังก์ชันที่ห่อเท่านั้น ซึ่งเป็น `cached` ตัวกลางด้านล่าง ไม่ใช่โค้ดจริง)
_ROOT = os.path.dirname(os.path.abspath(__file__))
_CODE_FILES = tuple(sorted(
    os.path.join(d, f) for d in (_ROOT, os.path.join(_ROOT, "analysis"), os.path.join(_ROOT, "data"))
    for f in os.listdir(d) if f.endswith(".py")))
_CACHE_MAX_ENTRIES = 16   # ต่อ getter — entry ของ stamp เก่าถูกไล่ออกเอง (ไม่สะสมจน restart)


def _versioned(fn, cache_data, *paths: str):
    """ห่อ fn ด้วย st.cache_data ที่หมดอายุเองเมื่อไฟล์ใน paths, ไฟล์โค้ด หรือ config เปลี่ยน.

    ตั้ง __qualname__ ของตัวห่อให้ต่างกันต่อ getter ก่อน decorate — Streamlit สร้าง key ของ cache จาก module + qualname
    + source ถ้าเหมือนกันทุก getter จะใช้ store เดียวกัน (max_entries/clear ใช้ร่วมกัน · streamlit issue #11157)
    """
    def cached(name: str, stamp: tuple, *args, **kwargs):
        return fn(*args, **kwargs)

    cached.__qualname__ = f"_versioned.{fn.__name__}"
    cached = cache_data(show_spinner=f"กำลังโหลด {fn.__name__}…", max_entries=_CACHE_MAX_ENTRIES)(cached)

    def get(*args, **kwargs):
        return cached(fn.__name__, _cache_stamp(paths), *args, **kwargs)

    get.__name__ = get.__qualname__ = fn.__name__
    get.__doc__ = fn.__doc__
    return get


_MSCI_FILES = (config.MSCI_COUNTRY_CSV, config.MSCI_SECTOR_CSV)

try:
    import streamlit as st

    get_results = _versioned(_load_results, st.cache_data, RESULTS_CSV)
    get_coefs = _versioned(_load_coefs, st.cache_data, COEFS_CSV)
    get_vol_forecast_backtest = _versioned(_load_vol_backtest, st.cache_data, VOL_BACKTEST_CSV)
    get_vol_forecast_latest = _versioned(_load_vol_latest, st.cache_data, VOL_LATEST_CSV)
    get_index_snapshot = _versioned(_load_index_snapshot, st.cache_data, VOL_LATEST_CSV, *_MSCI_FILES)
    get_style_results = _versioned(_load_style_results, st.cache_data, STYLE_RESULTS_CSV)
    get_macro_loadings = _versioned(_load_macro_loadings, st.cache_data, MACRO_LOADINGS_CSV)
    get_macro_index_betas = _versioned(_load_macro_index_betas, st.cache_data, MACRO_INDEX_BETAS_CSV)
    get_score_matches = _versioned(score_matches, st.cache_data, RESULTS_CSV, COEFS_CSV, SCORE_MATCHES_CLEAN_CSV)
    get_portfolio_risk_model = _versioned(portfolio_risk_model, st.cache_data, config.NAV_CLEAN_PARQUET, *_MSCI_FILES)
    get_share_class_groups = _versioned(share_class_groups, st.cache_data, config.SHARE_CLASS_CSV)
    get_tf_cache = _versioned(load_tf_cache, st.cache_data, *TF_CACHE_FILES, *TF_INPUT_FILES)
    get_tf_live = _versioned(tf_live, st.cache_data, *TF_CACHE_FILES, *TF_INPUT_FILES)
    get_tf_top3 = _versioned(load_tf_top3, st.cache_data, *TF_TOP3_FILES)
    get_gc75_frontier = _versioned(load_gc75_frontier, st.cache_data, *GC75_FRONTIER_FILES)

    def rebuild() -> None:
        try:
            build_pipeline(verbose=False)
            build_vol_forecast_cache(verbose=False)      # รวมทุก cache ให้ปุ่มเดียว rebuild ครบ (เร็ว ~ไม่กี่วิ)
            if os.path.exists(config.STYLE_FACTOR_CSV):   # style ต้องมี snapshot ก่อน (ดาวน์โหลดแยก ไม่ดึงเน็ตในแอป)
                build_style_pipeline(verbose=False)       # ต้องหลัง build_pipeline เพราะอ่านรายชื่อกอง E จาก results
            if os.path.exists(config.MACRO_FACTOR_CSV):   # macro เหมือนกัน — ต้องหลัง build_pipeline (อ่าน coefs.csv)
                build_macro_pipeline(verbose=False)
            build_score_matches(verbose=False)            # หน้า 8 — refit country ชุด cleaned (ต้องหลัง build_pipeline)
            build_tf_cache(verbose=False)                 # หน้า 9 — backtest + replay (ต้องหลัง build_pipeline: อ่าน nav_clean.parquet)
        finally:
            # ขั้นหลังพังได้หลังขั้นก่อนเขียนทับไฟล์ไปแล้ว -> ล้าง in-memory เสมอ ให้ UI ตรงกับดิสก์
            st.cache_data.clear()
except ModuleNotFoundError:  # รันนอก streamlit (เช่น pytest/CLI)
    get_results = _load_results
    get_coefs = _load_coefs
    get_vol_forecast_backtest = _load_vol_backtest
    get_vol_forecast_latest = _load_vol_latest
    get_index_snapshot = _load_index_snapshot
    get_style_results = _load_style_results
    get_macro_loadings = _load_macro_loadings
    get_macro_index_betas = _load_macro_index_betas
    get_score_matches = score_matches
    get_portfolio_risk_model = portfolio_risk_model
    get_share_class_groups = share_class_groups
    get_tf_cache = load_tf_cache
    get_tf_live = tf_live
    get_tf_top3 = load_tf_top3
    get_gc75_frontier = load_gc75_frontier


if __name__ == "__main__":
    import sys
    import time
    t0 = time.time()
    if len(sys.argv) > 1 and sys.argv[1] == "macro-download":
        snap = macro_factor.download_snapshot()
        print(f"snapshot {snap.shape} {snap.index.min():%Y-%m-%d} -> {snap.index.max():%Y-%m-%d} "
              f"-> {config.MACRO_FACTOR_CSV}")
    elif len(sys.argv) > 1 and sys.argv[1] == "score":
        m = build_score_matches(verbose=True)
        print(f"\nscore matches done in {time.time() - t0:.0f}s  {m.shape}")
        print(m["country_primary"].value_counts().head(8).to_string())
    elif len(sys.argv) > 1 and sys.argv[1] == "macro":
        ld, bt = build_macro_pipeline(verbose=True)
        print(f"\nmacro done in {time.time() - t0:.0f}s  loadings={ld.shape} index_betas={bt.shape}")
        print(ld.groupby("method")["r2"].median().rename("median R² ต่อกอง").to_string())
    elif len(sys.argv) > 1 and sys.argv[1] == "style-download":
        snap = style_factor.download_snapshot()
        print(f"snapshot {snap.shape} {snap.index.min():%Y-%m-%d} -> {snap.index.max():%Y-%m-%d} "
              f"-> {config.STYLE_FACTOR_CSV}")
    elif len(sys.argv) > 1 and sys.argv[1] == "style":
        r, c = build_style_pipeline(verbose=True)
        print(f"\nstyle done in {time.time() - t0:.0f}s  results={r.shape} coefs={c.shape}")
        print(r["style_primary"].value_counts(dropna=False).to_string())
    elif len(sys.argv) > 1 and sys.argv[1] == "tf":
        meta = build_tf_cache(verbose=True)
        print(f"\ntf cache done in {time.time() - t0:.0f}s  NAV ถึง {meta['nav_max_date']} · MSCI ถึง {meta['msci_last']}")
    elif len(sys.argv) > 1 and sys.argv[1] == "vol":
        b, l = build_vol_forecast_cache(verbose=True)
        print(f"\nvol cache done in {time.time() - t0:.0f}s  backtest={b.shape} latest={l.shape}")
        print(l.groupby("scope")["garch_fallback"].sum().to_string())
    else:
        r, c = build_pipeline(verbose=True)
        print(f"\ndone in {time.time() - t0:.0f}s  results={r.shape} coefs={c.shape}")
        print("country primary distribution (top 8):")
        print(r["country_primary"].value_counts().head(8).to_string())
        print(f"\nR² country: mean={r['country_r2'].mean():.2f} median={r['country_r2'].median():.2f}")
        print(f"R² by policy (country):\n{r.groupby('policy')['country_r2'].mean().to_string()}")
