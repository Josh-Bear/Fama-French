"""fund_backtest.py — universe ตามเวลา, จำลองพอร์ตรายไตรมาส และตัวชี้วัดรายเดือนของโมเดลหน้า 9.

พอร์ตจากโค้ด backtest ของทีม quant โดยไม่เปลี่ยนตรรกะ (ตัวเลขต้องตรง backtest)
ตัวชี้วัดคิดจากมูลค่าพอร์ตสิ้นเดือน: Sharpe = mean(r − rf/12) × 12 ÷ (SD(r) × √12) · CAGR ตามวันจริง
(คนละนิยามกับ analysis/metrics.py ที่ใช้กับ NAV/ดัชนีรายวัน — ชื่อฟังก์ชันจึงขึ้นต้นด้วย monthly_ / portfolio_)
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

import config
from analysis import metrics

CASH = "__CASH__"


# ---------------- ปฏิทินและ universe ตามเวลา ----------------

def quarter_ends(calendar: pd.DatetimeIndex, start: str, end) -> list[pd.Timestamp]:
    """วันสุดท้ายของแต่ละไตรมาสที่มีในปฏิทินดัชนี ในช่วง [start, end]."""
    cal = pd.Series(calendar, index=calendar).sort_index()
    ts = sorted(pd.Timestamp(v) for v in cal.groupby([cal.index.year, cal.index.quarter]).max().values)
    return [t for t in ts if pd.Timestamp(start) <= t <= pd.Timestamp(end)]


def month_ends(calendar: pd.DatetimeIndex, start, end) -> list[pd.Timestamp]:
    cal = pd.Series(calendar, index=calendar).sort_index()
    ts = sorted(pd.Timestamp(v) for v in cal.groupby([cal.index.year, cal.index.month]).max().values)
    return [t for t in ts if pd.Timestamp(start) <= t <= pd.Timestamp(end)]


def execution_date(calendar: pd.DatetimeIndex, t: pd.Timestamp) -> pd.Timestamp | None:
    """วันซื้อขาย = วันทำการที่ TF_EXEC_LAG ของปฏิทินดัชนีหลัง t (None ถ้าปฏิทินยังไม่ถึง)."""
    after = calendar[calendar > t]
    return after[config.TF_EXEC_LAG - 1] if len(after) >= config.TF_EXEC_LAG else None


def universe_at(nav: pd.DataFrame, t: pd.Timestamp) -> pd.DataFrame:
    """U_t: กองที่ NAV ล่าสุด ≤ NAV_STALE_MAX_DAYS วันจาก t และมี NAVDate ≥ TF_MIN_HISTORY วันตั้งแต่ TF_HISTORY_START.

    ใช้แค่ NAVDate ≤ t (ไม่ดูคอลัมน์ status ของวันนี้ — กัน look-ahead/survivorship)
    คืน [FundCode, last_nav_date, last_nav, last_aum]
    """
    sub = nav[nav["NAVDate"] <= t]
    g = sub.groupby("FundCode")
    last_date = g["NAVDate"].max()
    hist = sub[sub["NAVDate"] >= pd.Timestamp(config.TF_HISTORY_START)].groupby("FundCode")["NAVDate"].nunique()
    stale_ok = (t - last_date).dt.days <= config.NAV_STALE_MAX_DAYS
    hist_ok = hist.reindex(last_date.index).fillna(0) >= config.TF_MIN_HISTORY
    keep = last_date.index[stale_ok & hist_ok]
    last_rows = sub[sub["FundCode"].isin(keep)].sort_values("NAVDate").groupby("FundCode").tail(1)
    out = last_rows.set_index("FundCode").loc[list(keep), ["NAVDate", "NAV", "AUM"]].reset_index()
    out.columns = ["FundCode", "last_nav_date", "last_nav", "last_aum"]
    return out.reset_index(drop=True)


def b0_universe(u_t: pd.DataFrame, groups: dict) -> pd.DataFrame:
    """B0 = 1 share class ต่อกลุ่ม (AUM ล่าสุดมากสุดในกลุ่ม) — baseline ถือทุกกองเท่ากัน."""
    df = u_t.copy()
    df["group"] = df["FundCode"].map(lambda f: groups.get(f, f))
    df["last_aum"] = df["last_aum"].fillna(0.0)
    return df.sort_values("last_aum", ascending=False).groupby("group", as_index=False).head(1).reset_index(drop=True)


# ---------------- จำลองพอร์ต ----------------

def _nav_last(nav_by_fund, fc, day):
    """(NAV ล่าสุดที่ NAVDate ≤ day, NAVDate นั้น) สำหรับ mark-to-market · (None, None) ถ้าไม่เคยมี."""
    s = nav_by_fund.get(fc)
    if s is None:
        return None, None
    s2 = s.loc[:day]
    return (float(s2.iloc[-1]), s2.index[-1]) if len(s2) else (None, None)


def _exec_nav(nav_by_fund, fc, e, max_gap_bdays):
    """ราคาซื้อ = NAV ของ NAVDate แรกที่ ≥ e ถ้าห่างไม่เกิน max_gap_bdays วันทำการ · เกินนั้น = ซื้อไม่ได้ (None)."""
    s = nav_by_fund.get(fc)
    if s is None:
        return None
    s2 = s.loc[e:]
    if len(s2) == 0:
        return None
    if int(np.busday_count(e.date(), s2.index[0].date())) > max_gap_bdays:
        return None
    return float(s2.iloc[0])


def _grow_cash(amount, d0, d1, rf_annual):
    if amount <= 0 or d0 is None or d1 <= d0:
        return amount
    return amount * (1.0 + rf_annual) ** ((d1 - d0).days / 365.0)


def simulate_path(plan: list[dict], nav_by_fund: dict, months: list, rf_annual: float,
                  cost_side: float = 0.0, fee_model=None, start_value: float = 100.0,
                  max_exec_gap_bdays: int | None = None) -> tuple[pd.Series, list[dict]]:
    """เดินพอร์ตซื้อแล้วถือรายไตรมาสบน NAV จริง.

    plan item: {"t", "e", "weights": {FundCode: w, "__CASH__": c}} — rebalance เต็มที่ NAV แรก ≥ e
    - ต้นทุน: fee_model.entry_cost (ค่าธรรมเนียมจริง) หรือ cost_side × Σ|Δw| (ต่อข้าง) · ขาเงินสดไม่มีต้นทุน
    - กองที่ซื้อไม่ได้ -> ถือเป็นเงินสด (ได้ rf) จนรอบถัดไป · เงินสดโตด้วย rf ตามวันจริง
    คืน (มูลค่าพอร์ตสิ้นเดือน เริ่มที่ start_value ณ e แรก,
         รายการต่อรอบ [{t, e, turnover, cost, cannot_buy: [กอง], stale_marks: [กองที่ถูก mark ด้วย NAV เก่าเกิน
         NAV_STALE_MAX_DAYS ระหว่างถือ]}])
    ตรวจเงินไม่หาย: น้ำหนักรวม (กอง + เงินสด) ต้อง ≈ 1 · ต้นทุนต้องเป็นตัวเลขจริงใน [0, 1) — ผิดเงื่อนไข = raise ทันที
    """
    max_exec_gap_bdays = config.TF_EXEC_MAX_GAP_BDAYS if max_exec_gap_bdays is None else max_exec_gap_bdays
    value = start_value
    units: dict[str, float] = {}
    cash, cash_since = 0.0, None
    records, entries = [], []
    m_idx = 0
    for qi, p in enumerate(plan):
        e = p["e"]
        cur_vals = {}
        if units or cash:
            for fc, u in units.items():
                px, _ = _nav_last(nav_by_fund, fc, e)
                cur_vals[fc] = u * (px if px is not None else 0.0)
            value = sum(cur_vals.values()) + _grow_cash(cash, cash_since, e, rf_annual)
            drift_w = {fc: v / value for fc, v in cur_vals.items()} if value > 0 else {}
        else:
            drift_w = {}
        target_funds = {f: w for f, w in p["weights"].items() if f != CASH}
        target_cash = float(p["weights"].get(CASH, 0.0))
        total_w = sum(target_funds.values()) + target_cash
        if abs(total_w - 1.0) > 1e-6:
            raise ValueError(f"น้ำหนักรวม ณ {p['t']:%Y-%m-%d} = {total_w:.6f} ไม่ใช่ 1 (เงินส่วนที่ขาดจะหายไปเงียบๆ)")
        all_funds = set(drift_w) | set(target_funds)
        turnover = sum(abs(target_funds.get(f, 0.0) - drift_w.get(f, 0.0)) for f in all_funds) / 2.0
        if fee_model is None:
            cost = sum(cost_side * abs(target_funds.get(f, 0.0) - drift_w.get(f, 0.0)) for f in all_funds)
        else:
            cost, _ = fee_model.entry_cost(e, drift_w, target_funds)
        if not (np.isfinite(cost) and 0.0 <= cost < 1.0):
            raise ValueError(f"ต้นทุน ณ {e:%Y-%m-%d} = {cost} ผิดปกติ (ค่าธรรมเนียมเป็น NaN/ติดลบ?)")
        value = value * (1 - cost)
        entry = {"t": p["t"], "e": e, "turnover": turnover, "cost": cost, "cannot_buy": [], "stale_marks": set()}
        entries.append(entry)

        next_e = plan[qi + 1]["e"] if qi + 1 < len(plan) else months[-1] + pd.Timedelta(days=1)
        new_units, new_cash = {}, value * target_cash
        for fc, w in target_funds.items():
            if w <= 0:
                continue
            alloc = value * w
            px = _exec_nav(nav_by_fund, fc, e, max_exec_gap_bdays)
            if px is None:
                new_cash += alloc                 # ซื้อไม่ได้ -> เงินสด (ห้ามทิ้งเงิน)
                entry["cannot_buy"].append(fc)
                continue
            new_units[fc] = alloc / px
        units, cash, cash_since = new_units, new_cash, e

        while m_idx < len(months) and months[m_idx] < next_e:
            md = months[m_idx]
            if md >= e:
                mv = 0.0
                for fc, u in units.items():
                    px, last = _nav_last(nav_by_fund, fc, md)
                    mv += u * (px if px is not None else 0.0)
                    if last is not None and (md - last).days > config.NAV_STALE_MAX_DAYS:
                        entry["stale_marks"].add(fc)    # ถือกองที่ NAV ค้างนาน — มูลค่าเป็นราคาเก่า
                records.append((md, mv + _grow_cash(cash, cash_since, md, rf_annual)))
            m_idx += 1

    values = pd.Series(dict(records)).sort_index()
    if plan:
        values = pd.concat([pd.Series({plan[0]["e"]: start_value}), values]).sort_index()
    for x in entries:
        x["stale_marks"] = sorted(x["stale_marks"])
    return values, entries


# ---------------- ตัวชี้วัดรายเดือน ----------------

def monthly_returns(values: pd.Series) -> pd.Series:
    return values.pct_change().dropna()


def portfolio_sharpe(returns: pd.Series, rf_annual: float) -> float:
    if len(returns) < 2:
        return np.nan
    sd = returns.std(ddof=1)
    if sd == 0 or np.isnan(sd):
        return np.nan
    return float(((returns - rf_annual / 12.0).mean() * 12) / (sd * np.sqrt(12)))


def portfolio_cagr(values: pd.Series) -> float:
    """CAGR ของมูลค่าพอร์ตตามวันปฏิทินจริง (สูตรเดียวกับ analysis.metrics.cagr)."""
    return metrics.cagr(values)


def monthly_vol(returns: pd.Series) -> float:
    return float(returns.std(ddof=1) * np.sqrt(12)) if len(returns) > 1 else np.nan


def max_drawdown(values: pd.Series) -> float:
    if len(values) < 2:
        return np.nan
    return float((values / values.cummax() - 1).min())


def block_bootstrap_ci(returns: pd.Series, rf_annual: float, n_boot: int = 2000, block: int = 3, seed: int = 0):
    """CI95% ของ Sharpe ด้วย block bootstrap (บล็อก 3 เดือน)."""
    rng = np.random.default_rng(seed)
    r = returns.dropna().to_numpy()
    n = len(r)
    if n < 6:
        return (np.nan, np.nan)
    n_blocks = int(np.ceil(n / block))
    sh = []
    for _ in range(n_boot):
        idx = rng.integers(0, max(n - block, 0) + 1, size=n_blocks)
        v = portfolio_sharpe(pd.Series(np.concatenate([r[i:i + block] for i in idx])[:n]), rf_annual)
        if not np.isnan(v):
            sh.append(v)
    return (float(np.percentile(sh, 2.5)), float(np.percentile(sh, 97.5))) if sh else (np.nan, np.nan)


def effective_n(returns: pd.Series) -> float:
    """จำนวนสังเกตอิสระที่เทียบเท่า (Lo 2002) — ปรับ autocorrelation ของ return รายเดือน."""
    r = np.asarray(pd.Series(returns).dropna(), dtype=float)
    n = len(r)
    if n < 8:
        return float(n)
    max_lag = int(min(max(1, int(np.floor(4 * (n / 100.0) ** (2.0 / 9.0)))), n - 2))
    r_c = r - r.mean()
    var0 = np.sum(r_c ** 2) / n
    denom = 1.0
    if var0 > 0:
        for k in range(1, max_lag + 1):
            denom += 2.0 * (1.0 - k / n) * (np.sum(r_c[k:] * r_c[:-k]) / n) / var0
    return float(min(max(n / max(denom, 1e-6), 2.0), n))


def deflated_sharpe(returns: pd.Series, rf_annual: float, n_trials: int) -> float:
    """Deflated Sharpe (Bailey & López de Prado 2014) — ความน่าจะเป็นที่ Sharpe จริง > 0 หลังหักการลอง n_trials ครั้ง.

    ทุกพจน์เป็นหน่วยรายเดือน (sr_m = excess mean / SD รายเดือน — ห้ามใส่ Sharpe รายปี)
    """
    r = pd.Series(returns).dropna()
    if len(r) < 3:
        return float("nan")
    sd = r.std(ddof=1)
    if sd == 0 or np.isnan(sd):
        return float("nan")
    sr_m = float((r - rf_annual / 12.0).mean() / sd)
    n_eff = effective_n(r)
    skew = float(stats.skew(r.to_numpy(), bias=False))
    kurt = float(stats.kurtosis(r.to_numpy(), fisher=False, bias=False)) if len(r) > 3 else 3.0
    sr0 = 0.0
    if n_trials > 1:
        euler = 0.5772156649
        sr0 = ((1 - euler) * stats.norm.ppf(1 - 1.0 / n_trials) +
               euler * stats.norm.ppf(1 - 1.0 / (n_trials * np.e))) / np.sqrt(max(n_eff, 2.0))
    se = np.sqrt(max((1 - skew * sr_m + (kurt - 1) / 4.0 * sr_m ** 2) / max(n_eff - 1, 1e-6), 1e-12))
    return float(stats.norm.cdf((sr_m - sr0) / se))


def summarize(values: pd.Series, rf_annual: float, n_trials: int | None = None) -> dict:
    """ตัวชี้วัดของมูลค่าพอร์ตสิ้นเดือน (ตัดถึง TF_EVAL_END แล้ว)."""
    r = monthly_returns(values)
    n_trials = config.TF_N_TRIALS if n_trials is None else n_trials
    lo, hi = block_bootstrap_ci(r, rf_annual)
    return {"sharpe": portfolio_sharpe(r, rf_annual), "cagr": portfolio_cagr(values), "vol": monthly_vol(r),
            "max_dd": max_drawdown(values), "dsr": deflated_sharpe(r, rf_annual, n_trials),
            "ci_lo": lo, "ci_hi": hi, "n_months": len(r)}
