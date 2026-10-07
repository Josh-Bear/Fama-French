"""simulate.py — จำลองมูลค่าพอร์ต buy-and-hold รายไตรมาส + ต้นทุนสลับกอง + เมตริกผลตอบแทน (Sharpe/CAGR/...).
รับ quarter_plan (weights ต่อ t จากโมดูล selection) แล้วเดินพอร์ตจริงบน NAV — ใช้ซ้ำได้ทุกโมเดล (M001+)

แก้บั๊ก 2026-09-30 (พบโดย session หลัก): เดิมถ้าซื้อกองไม่ได้ (ไม่มี NAVDate >= e เลย) โค้ดเดิม `continue`
ทิ้งเงินส่วนนั้นไปเฉยๆ (ไม่ถือเป็นเงินสด) ทำให้มูลค่าพอร์ตหายจริง ไม่ใช่แค่ error ทางสถิติ (พบที่ t=2026-03-31
กอง TEMxCH/ASP-EUROPE QUALITY/K-SEMQ/LHUSFIN-D NAV ล่าสุด ~2026-01-06/07 → equity MS ลด 64.7% เดือน 2026-04)
แก้เป็น: น้ำหนักที่ซื้อไม่ได้ -> ถือเป็นเงินสดได้ rf_annual จนรอบถัดไป (ห้ามทิ้งเงิน) + exec lag เกิน
10 วันทำการหลัง e ถือว่าซื้อไม่ได้ (กันใช้ราคาที่รู้ในอนาคตไกลเกินจริง) + mark-to-market ห้ามเป็น 0 เพราะไม่มี
NAV ณ วันนั้น ต้องใช้ NAV ล่าสุดที่มีจริงเสมอ (กองที่ถือย่อมเคยมี NAV ตอนซื้อ)."""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

import config

STALE_MARK_DAYS = config.NAV_STALE_MAX_DAYS  # เกณฑ์เดียวกับ universe staleness — ใช้ flag event "mark ด้วย NAV เก่า"


def _nav_last(nav_by_fund, fc, day):
    """(price, is_stale) จาก NAV ล่าสุดที่ NAVDate <= day — (None, False) ถ้าไม่เคยมี NAV เลย."""
    s = nav_by_fund.get(fc)
    if s is None:
        return None, False
    s2 = s.loc[:day]
    if len(s2) == 0:
        return None, False
    last_date = s2.index[-1]
    is_stale = (day - last_date).days > STALE_MARK_DAYS
    return float(s2.iloc[-1]), is_stale


def _exec_nav(nav_by_fund, fc, e, max_gap_bdays=10):
    """ราคาซื้อ = NAV ของ NAVDate แรกที่ >= e ถ้าห่างไม่เกิน max_gap_bdays วันทำการ · เกินนั้น = ซื้อไม่ได้ (None)."""
    s = nav_by_fund.get(fc)
    if s is None:
        return None
    s2 = s.loc[e:]
    if len(s2) == 0:
        return None
    actual_date = s2.index[0]
    gap_bdays = int(np.busday_count(e.date(), actual_date.date()))
    if gap_bdays > max_gap_bdays:
        return None
    late = gap_bdays > 2   # ปกติ execution lag ~2 วัน (spec §3) — เกินนี้ถือว่า "ช้า" แต่ยังซื้อได้
    return float(s2.iloc[0]), actual_date, late


def _grow_cash(amount, d0, d1, rf_annual):
    if amount <= 0 or d0 is None or d1 <= d0:
        return amount
    days = (d1 - d0).days
    return amount * (1.0 + rf_annual) ** (days / 365.0)


def simulate_path(quarter_plan: list[dict], nav_by_fund: dict, month_ends: list, cost_side: float,
                   rf_annual: float, start_value: float = 100.0, max_exec_gap_bdays: int = 10,
                   include_start: bool = False, info: dict | None = None, fee_model=None):
    """quarter_plan item: {"t":.., "e":.., "weights": {fund: w}}.
    น้ำหนักที่ซื้อไม่ได้ -> เงินสดได้ rf_annual จนรอบถัดไป (ห้ามทิ้งเงิน)
    คืน (monthly_values: Series, turnover_per_quarter: list[float],
         events: list[{"date","type","fund","t"}] (cannot_buy/exec_late/mark_stale), n_quarters)
    """
    # M006 §4 / M007 §4 (เพิ่ม 2026-10-02): plan entry ที่มี "mode":"scale" = ปรับส่วนหุ้นตามสัดส่วน drift (ต้นทุนเฉพาะขากอง);
    # entry ไม่มี mode = full rebalance (พฤติกรรมเดิมทุกประการ) · include_start=True -> เพิ่มจุด (e แรก, start_value) ใน series
    # (วัดเดือนแรก) · info (dict, optional) ได้ info["entries"] = list[{t,e,mode,turnover,cost,target}]
    value = start_value
    units: dict[str, float] = {}
    cash = 0.0
    cash_since = None
    monthly_records = []
    turnovers = []
    events: list[dict] = []
    m_idx = 0
    n_months = len(month_ends)

    for qi, plan in enumerate(quarter_plan):
        e = plan["e"]
        target_w = plan.get("weights", {})

        cur_vals = {}
        if units or cash:
            for fc, u in units.items():
                px, is_stale = _nav_last(nav_by_fund, fc, e)
                cur_vals[fc] = u * (px if px is not None else 0.0)
                if is_stale:
                    events.append({"date": e, "type": "mark_stale", "fund": fc, "t": plan["t"]})
            cash_grown = _grow_cash(cash, cash_since, e, rf_annual)
            value = sum(cur_vals.values()) + cash_grown
            drift_w = {fc: v / value for fc, v in cur_vals.items()} if value > 0 else {}
        else:
            drift_w = {}

        # C7 (ขยาย 2026-09-30, session หลัก): key พิเศษ "__CASH__" = เงินสดเป้าหมายที่ผู้ใช้ตั้งใจถือ (ไม่ใช่
        # cannot_buy fallback) — ขานี้ไม่คิดต้นทุนและไม่นับ turnover (สลับ "กอง -> กอง" เท่านั้นที่เสียต้นทุน 1 ข้าง)
        is_scale = plan.get("mode", "full") == "scale"
        if is_scale:
            d_eq = sum(drift_w.values())
            e_tgt = plan["equity"] * sum(plan["sleeve"].values())
            if d_eq > 1e-12:
                target_w_funds = {f: dw / d_eq * e_tgt for f, dw in drift_w.items()}
            else:
                target_w_funds = {f: plan["equity"] * w for f, w in plan["sleeve"].items() if w > 0}
            target_cash_w = 1.0 - sum(target_w_funds.values())
            assert -1e-9 <= target_cash_w <= 1 + 1e-9, f"cash เป้าหมายนอกช่วง {target_cash_w}"
            target_w = {**target_w_funds, "__CASH__": target_cash_w}
        else:
            target_w_funds = {f: w for f, w in target_w.items() if f != "__CASH__"}
            target_cash_w = float(target_w.get("__CASH__", 0.0))

        all_funds = set(drift_w) | set(target_w_funds)
        turnover = sum(abs(target_w_funds.get(f, 0.0) - drift_w.get(f, 0.0)) for f in all_funds) / 2.0
        cost_detail = None
        if fee_model is None:      # พฤติกรรมเดิม: ต้นทุนคงที่ cost_side ต่อข้าง
            cost = sum(cost_side * abs(target_w_funds.get(f, 0.0) - drift_w.get(f, 0.0)) for f in all_funds)
        else:                      # COST_real_fees: ค่าธรรมเนียมจริงต่อกอง/บลจ. (fees.FeeModel) — ขากองเท่านั้น
            cost, cost_detail = fee_model.entry_cost(e, drift_w, target_w_funds)
        value_before_cost = value
        value = value * (1 - cost)
        assert abs(value - value_before_cost * (1 - cost)) < 1e-9 * max(1.0, abs(value_before_cost)), \
            "มูลค่าหลัง rebalance ต้อง = มูลค่าก่อน x (1-cost)"
        turnovers.append(turnover)
        if info is not None:
            info.setdefault("entries", []).append(
                {"t": plan["t"], "e": e, "mode": "scale" if is_scale else "full", "turnover": turnover,
                 "cost": cost, "target": {**target_w_funds, "__CASH__": target_cash_w}, "cost_detail": cost_detail})

        next_e = quarter_plan[qi + 1]["e"] if qi + 1 < len(quarter_plan) else \
            (month_ends[-1] + pd.Timedelta(days=1))

        new_units: dict[str, float] = {}
        bought_money = 0.0
        new_cash = value * target_cash_w            # เงินสดเป้าหมาย (C7) — ไม่ผ่าน _exec_nav, ไม่มี cannot_buy
        for fc, w in target_w_funds.items():
            if w <= 0:
                continue
            alloc = value * w
            if is_scale and fc in units and cur_vals.get(fc, 0.0) > 0:
                new_units[fc] = units[fc] * alloc / cur_vals[fc]   # ปรับที่ราคา mark ณ e (ไม่ซื้อใหม่ที่ _exec_nav)
                bought_money += alloc
                continue
            r = _exec_nav(nav_by_fund, fc, e, max_exec_gap_bdays)
            if r is None:
                new_cash += alloc                      # ซื้อไม่ได้ -> ถือเป็นเงินสด (ห้ามทิ้งเงิน)
                events.append({"date": e, "type": "cannot_buy", "fund": fc, "t": plan["t"]})
                continue
            px, actual_date, late = r
            if late:
                events.append({"date": e, "type": "exec_late", "fund": fc, "t": plan["t"]})
            new_units[fc] = alloc / px
            bought_money += alloc
        units = new_units
        cash = new_cash
        cash_since = e
        total_w = sum(target_w_funds.values()) + target_cash_w
        total_money = bought_money + new_cash
        if value > 1e-9:
            assert abs(total_money / value - total_w) < 1e-6, "ผลรวมน้ำหนัก(ซื้อ)+เงินสด ต้อง = ผลรวมน้ำหนักเป้าหมาย"
            if total_w > 0:
                assert abs(total_w - 1.0) < 1e-6, f"น้ำหนักรวมต้อง ~1 ไม่ใช่ {total_w}"

        while m_idx < n_months and month_ends[m_idx] < next_e:
            md = month_ends[m_idx]
            if md >= e:
                mv = 0.0
                for fc, u in units.items():
                    px, is_stale = _nav_last(nav_by_fund, fc, md)
                    mv += u * (px if px is not None else 0.0)
                    if is_stale:
                        events.append({"date": md, "type": "mark_stale", "fund": fc, "t": plan["t"]})
                mv += _grow_cash(cash, cash_since, md, rf_annual)
                monthly_records.append((md, mv))
            m_idx += 1

    values = pd.Series(dict(monthly_records)).sort_index()
    if include_start and quarter_plan:
        values = pd.concat([pd.Series({quarter_plan[0]["e"]: start_value}), values]).sort_index()
    return values, turnovers, events, len(quarter_plan)


# ---------------- perf metrics ----------------

def monthly_returns(values: pd.Series) -> pd.Series:
    return values.pct_change().dropna()


def sharpe(returns: pd.Series, rf_annual: float) -> float:
    if len(returns) < 2:
        return np.nan
    rf_m = rf_annual / 12.0
    excess_mean = (returns - rf_m).mean()
    sd = returns.std(ddof=1)
    if sd == 0 or np.isnan(sd):
        return np.nan
    return float((excess_mean * 12) / (sd * np.sqrt(12)))


def cagr(values: pd.Series) -> float:
    if len(values) < 2:
        return np.nan
    n_years = (values.index[-1] - values.index[0]).days / 365.25
    if n_years <= 0 or values.iloc[0] <= 0:
        return np.nan
    return float((values.iloc[-1] / values.iloc[0]) ** (1 / n_years) - 1)


def ann_vol(returns: pd.Series) -> float:
    return float(returns.std(ddof=1) * np.sqrt(12)) if len(returns) > 1 else np.nan


def max_drawdown(values: pd.Series) -> float:
    if len(values) < 2:
        return np.nan
    peak = values.cummax()
    return float((values / peak - 1).min())


def sortino(returns: pd.Series, rf_annual: float) -> float:
    rf_m = rf_annual / 12.0
    excess = returns - rf_m
    downside = excess[excess < 0]
    if len(downside) < 2:
        return np.nan
    dd_std = downside.std(ddof=1)
    if not dd_std:
        return np.nan
    return float((excess.mean() * 12) / (dd_std * np.sqrt(12)))


def hit_rate_vs(returns: pd.Series, bench: pd.Series) -> float:
    a, b = returns.align(bench, join="inner")
    return float((a > b).mean()) if len(a) else np.nan


def info_ratio(returns: pd.Series, bench: pd.Series):
    a, b = returns.align(bench, join="inner")
    diff = a - b
    te = diff.std(ddof=1) * np.sqrt(12) if len(diff) > 1 else np.nan
    if not te or np.isnan(te):
        return np.nan, te
    return float((diff.mean() * 12) / te), float(te)


def block_bootstrap_ci(returns: pd.Series, rf_annual: float, n_boot=2000, block=3, seed=0):
    rng = np.random.default_rng(seed)
    r = returns.dropna().to_numpy()
    n = len(r)
    if n < 6:
        return (np.nan, np.nan)
    n_blocks = int(np.ceil(n / block))
    sh_list = []
    for _ in range(n_boot):
        idx = rng.integers(0, max(n - block, 0) + 1, size=n_blocks)
        sample = np.concatenate([r[i:i + block] for i in idx])[:n]
        s = pd.Series(sample)
        v = sharpe(s, rf_annual)
        if not np.isnan(v):
            sh_list.append(v)
    if not sh_list:
        return (np.nan, np.nan)
    return (float(np.percentile(sh_list, 2.5)), float(np.percentile(sh_list, 97.5)))


def effective_n(returns: pd.Series, max_lag: int | None = None) -> float:
    """n_eff แบบ Lo (2002) — จำนวนสังเกตอิสระ "ที่เทียบเท่า" ของ return ที่มี autocorrelation
    n_eff = n / (1 + 2*sum_{k=1..K} (1 - k/n) * rho_k)   (Newey-West-style variance-of-mean inflation)
    เหตุผลที่ต้องมี: reviewer พบว่า M001 ใช้ n_obs=15 (จำนวนไตรมาส) ทั้งที่ Sharpe คำนวณจาก return รายเดือน 44 จุด
    ซึ่งไม่อิสระต่อกัน (พอร์ต buy-and-hold ไม่ rebalance กลางไตรมาส -> return ภายในไตรมาสเดียวกันสัมพันธ์กัน)
    แทนที่จะ hardcode 15 หรือใช้ 44 ตรงๆ (สมมติอิสระเต็ม ซึ่งไม่จริง) ให้ประมาณจำนวนอิสระจริงจาก autocorrelation
    ของ return เอง — ถ้า n เล็ก (<8) คืน n ตรงๆ (ไม่มีข้อมูลพอประมาณ autocorrelation อย่างน่าเชื่อถือ).
    max_lag default = Newey-West rule-of-thumb floor(4*(n/100)^(2/9)), poj ไม่เกิน n-2.
    """
    r = np.asarray(pd.Series(returns).dropna(), dtype=float)
    n = len(r)
    if n < 8:
        return float(n)
    if max_lag is None:
        max_lag = max(1, int(np.floor(4 * (n / 100.0) ** (2.0 / 9.0))))
    max_lag = int(min(max_lag, n - 2))
    r_c = r - r.mean()
    var0 = np.sum(r_c ** 2) / n
    denom = 1.0
    if var0 > 0:
        for k in range(1, max_lag + 1):
            cov_k = np.sum(r_c[k:] * r_c[:-k]) / n
            rho_k = cov_k / var0
            denom += 2.0 * (1.0 - k / n) * rho_k
    denom = max(denom, 1e-6)
    n_eff = n / denom
    return float(min(max(n_eff, 2.0), n))


def deflated_sharpe(returns: pd.Series, rf_annual: float, n_trials: int) -> float:
    """Deflated Sharpe Ratio (Bailey & Lopez de Prado 2014) — คืนค่า **ความน่าจะเป็น** (probability, 0..1)
    ว่า Sharpe ที่แท้จริง (หลังหักผลของการค้นหา n_trials ครั้ง) มากกว่า 0

    **หน่วย (สำคัญ — แก้บั๊ก 2026-09-30, พบโดย model-reviewer `reviews/M002-M005_review.md` ข้อ 1):**
    สูตร PSR/DSR ของ Bailey & Lopez de Prado (SE และ SR0 ด้านล่าง) ถูกคิดมาสำหรับ Sharpe **ต่อช่วงสังเกต
    (per-period)** เดียวกับที่ใช้คำนวณ n_eff/skew/kurtosis เสมอ — ที่นี่คือ **รายเดือน** (returns คือ return
    รายเดือน) ห้ามใส่ Sharpe แบบ **annualized** (ที่คูณ √12 แล้ว จากฟังก์ชัน `sharpe()`) เข้าไปตรงๆ เพราะ SE/SR0
    ไม่ได้ปรับหน่วยให้ จะทำให้ z เฟ้อขึ้น ~√12 เท่า (DSR เข้าใกล้ 1 เกือบทุกกรณีทั้งที่ CI95 ของ ΔSharpe ยังคร่อม 0)
    ที่นี่จึงคำนวณ **sr_m = per-period Sharpe** เองจาก excess mean / sd ของ return รายเดือนตรงๆ
    (เทียบเท่า sr_annualized / √12) แล้วใช้ sr_m ทั้งใน SE และเทียบกับ SR0 เสมอ — ไม่เรียก `sharpe()` ตรงนี้

    1. **n_eff** = effective_n(returns) — ปรับ autocorrelation แบบ Lo (2002) แทนการเดา n_obs คงที่
       (ดัก underestimate variance ของ Sharpe ที่มาจาก return ภายในไตรมาสเดียวกันไม่อิสระต่อกัน)
    2. **skew/kurtosis** คำนวณจาก returns จริง (ไม่ใช่ normal สมมติ skew=0,kurt=3 เหมือนเดิม) ตามสูตร PSR ของ
       Bailey & Lopez de Prado (2012) "The Sharpe Ratio Efficient Frontier"
    3. SR0 (expected max Sharpe จาก n_trials อิสระภายใต้ H0 Sharpe=0) ใช้ n_eff เดียวกันในการ scale (สอดคล้องกับ SE)
       — SR0 เป็น per-period อยู่แล้ว (มี 1/√n_eff ในสูตร) จึงต้องเทียบกับ sr_m ที่เป็น per-period เช่นกัน

    สูตร (ทุกพจน์เป็น per-period/รายเดือน):
          sr_m = per-period excess mean / per-period sd   (≈ sr_annualized / √12)
          SR0  = [(1-γ)Φ⁻¹(1-1/N) + γΦ⁻¹(1-1/(N·e))] / √n_eff   (γ = Euler-Mascheroni)
          SE   = sqrt[(1 - skew·sr_m + (kurt-1)/4·sr_m²) / (n_eff - 1)]
          DSR  = Φ[(sr_m - SR0) / SE]
    """
    r = pd.Series(returns).dropna()
    if len(r) < 3:
        return float("nan")
    rf_m = rf_annual / 12.0
    sd = r.std(ddof=1)
    if sd == 0 or np.isnan(sd):
        return float("nan")
    sr_m = float((r - rf_m).mean() / sd)  # per-period (รายเดือน) Sharpe -- ห้ามใส่ค่า annualized ตรงนี้
    n_eff = effective_n(r)
    skew = float(stats.skew(r.to_numpy(), bias=False)) if len(r) > 2 else 0.0
    kurt = float(stats.kurtosis(r.to_numpy(), fisher=False, bias=False)) if len(r) > 3 else 3.0
    if n_trials <= 1:
        sr0 = 0.0
    else:
        euler = 0.5772156649
        sr0 = ((1 - euler) * stats.norm.ppf(1 - 1.0 / n_trials) +
               euler * stats.norm.ppf(1 - 1.0 / (n_trials * np.e))) / np.sqrt(max(n_eff, 2.0))
    se = np.sqrt(max((1 - skew * sr_m + (kurt - 1) / 4.0 * sr_m ** 2) / max(n_eff - 1, 1e-6), 1e-12))
    z = (sr_m - sr0) / se
    return float(stats.norm.cdf(z))


def paired_bootstrap_diff_ci(r_a: pd.Series, r_b: pd.Series, rf_annual: float, block: int = 3,
                              n_boot: int = 2000, seed: int = 0):
    """CI95% ของ ΔSharpe = Sharpe(a) - Sharpe(b) ด้วย paired block bootstrap: สุ่ม index บล็อกชุดเดียวกัน
    ใช้กับทั้งสองซีรีส์ (คงคู่วันที่/ความสัมพันธ์ระหว่างพอร์ต) แล้วคำนวณ Sharpe ต่างกันในแต่ละรอบ
    คืน (ci_lo, ci_hi, point_diff)."""
    a, b = r_a.align(r_b, join="inner")
    mask = a.notna() & b.notna()
    a, b = a[mask], b[mask]
    n = len(a)
    point = sharpe(a, rf_annual) - sharpe(b, rf_annual) if n >= 2 else float("nan")
    if n < 6:
        return (float("nan"), float("nan"), point)
    rng = np.random.default_rng(seed)
    av, bv = a.to_numpy(), b.to_numpy()
    n_blocks = int(np.ceil(n / block))
    diffs = []
    for _ in range(n_boot):
        idx = rng.integers(0, max(n - block, 0) + 1, size=n_blocks)
        sa = np.concatenate([av[i:i + block] for i in idx])[:n]
        sb = np.concatenate([bv[i:i + block] for i in idx])[:n]
        sh_a = sharpe(pd.Series(sa), rf_annual)
        sh_b = sharpe(pd.Series(sb), rf_annual)
        if not (np.isnan(sh_a) or np.isnan(sh_b)):
            diffs.append(sh_a - sh_b)
    if not diffs:
        return (float("nan"), float("nan"), point)
    return (float(np.percentile(diffs, 2.5)), float(np.percentile(diffs, 97.5)), point)
