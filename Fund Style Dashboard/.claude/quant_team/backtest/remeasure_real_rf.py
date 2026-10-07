"""remeasure_real_rf.py — เปลี่ยนวิธีวัดผล (ไม่ใช่ trial ใหม่): คำนวณทุก trial ใหม่ด้วย rf ไทยจริง แทน rf คงที่ 2%
เฉพาะ 2 จุด: (1) ดอกเบี้ยเงินสด (__CASH__ และเงินที่ซื้อกองไม่ได้) (2) rf ในสูตร Sharpe/DSR/CI · ไม่แตะการคัดกอง (ใช้ plan เดิม)
rf = อัตรานโยบาย กนง. (1-day repo, base_data/TH_POLICY_RATE.csv) แบบ step: อัตราใหม่มีผลตั้งแต่วันถัดจาก announce_date
 - อัตรา ณ วัน d (ช่วง [d, d+1)) = rate ของ announce_date ล่าสุดที่ < d · ปัจจัยสะสมรายวัน f_d=(1+r_d)^(1/365) (ACT/365 ทบต้น)
 - เงินสด: growth(d0,d1)=∏_{d0<=d<d1} f_d (ค่าคงที่ 2% -> (1.02)^(days/365) ตรงสูตรเดิมทุกประการ)
 - rf รายเดือนของ Sharpe: rf_k = growth(วันที่ index k-1, วันที่ index k) − 1 · excess_k = r_k − rf_k
   Sharpe = mean(excess)*12 / (std(r)*sqrt(12))  (สูตรเดิม แทน rf/12 ด้วย rf_k)
ไม่แก้ไฟล์เดิม: simulate.simulate_path ถูกใช้ตามเดิม โดยแทน simulate._grow_cash ชั่วคราว (context manager) ด้วยฟังก์ชันที่รับเส้น rf
เขียนผล: results/REAL_RF_summary.csv, results/REAL_RF_remeasure.md, เพิ่มคอลัมน์ใน ALL_RESULTS.csv/.md"""
import os, sys, pickle, json, time, contextlib
ROOT = "/Users/doyinratnavardhana/Fama French/Fund Style Dashboard"
BT = ROOT + "/.claude/quant_team/backtest"
SC = ROOT + "/.claude/quant_team/scratch"
sys.path.insert(0, ROOT); sys.path.insert(0, BT); os.chdir(ROOT)
import numpy as np, pandas as pd
from scipy import stats
import common, simulate, fees
import run_m006_m007 as r67

PE = r67.PRIMARY_END
RF_CONST = 0.02

# ---------------- rf curve ----------------
class RFCurve:
    def __init__(self, rate_by_day: pd.Series):
        """rate_by_day: Series รายวันปฏิทิน (% ต่อปี) index=วัน · cum[d]=∏_{u<d} f_u"""
        self.rate = rate_by_day
        f = (1.0 + rate_by_day.to_numpy() / 100.0) ** (1.0 / 365.0)
        self.cum = pd.Series(np.concatenate([[1.0], np.cumprod(f)]), index=rate_by_day.index.append(
            pd.DatetimeIndex([rate_by_day.index[-1] + pd.Timedelta(days=1)])))

    def growth(self, d0, d1):
        return float(self.cum.loc[pd.Timestamp(d0).normalize()] / self.cum.loc[pd.Timestamp(d1).normalize()] ** -1) if False else \
            float(self.cum.loc[pd.Timestamp(d1).normalize()] / self.cum.loc[pd.Timestamp(d0).normalize()])

    def avg_rate(self, d0, d1):
        days = (pd.Timestamp(d1) - pd.Timestamp(d0)).days
        return self.growth(d0, d1) ** (365.0 / days) - 1.0

    def rf_monthly(self, idx):
        idx = pd.DatetimeIndex(idx)
        return pd.Series([self.growth(idx[i - 1], idx[i]) - 1.0 for i in range(1, len(idx))], index=idx[1:])


def load_policy():
    p = pd.read_csv(ROOT + "/base_data/TH_POLICY_RATE.csv", comment="#", parse_dates=["announce_date"]).sort_values("announce_date")
    days = pd.date_range("2015-02-01", "2026-12-31", freq="D")
    eff = p["announce_date"] + pd.Timedelta(days=1)             # มีผลวันถัดจาก announce
    s = pd.Series(p["rate_pct"].to_numpy(), index=eff)
    s = s[~s.index.duplicated(keep="last")]
    rate = s.reindex(days.union(s.index)).ffill().reindex(days)
    assert rate.notna().all()
    return RFCurve(rate), p


def const_curve(pct=2.0):
    days = pd.date_range("2015-02-01", "2026-12-31", freq="D")
    return RFCurve(pd.Series(pct, index=days))


@contextlib.contextmanager
def cash_curve(curve: RFCurve):
    orig = simulate._grow_cash
    def g(amount, d0, d1, rf_annual):
        if amount <= 0 or d0 is None or d1 <= d0:
            return amount
        return amount * curve.growth(d0, d1)
    simulate._grow_cash = g
    try:
        yield
    finally:
        simulate._grow_cash = orig

# ---------------- metrics (series rf) ----------------
def sharpe_s(r: pd.Series, rfm):
    if len(r) < 2: return np.nan
    rfm = rfm if isinstance(rfm, pd.Series) else pd.Series(rfm, index=r.index)
    sd = r.std(ddof=1)
    if not sd or np.isnan(sd): return np.nan
    return float(((r - rfm.reindex(r.index)).mean() * 12) / (sd * np.sqrt(12)))

def metrics(values, rf_spec):
    """rf_spec: float (rf คงที่ รูปแบบเดิม rf/12) หรือ RFCurve"""
    v = values[values.index <= PE]
    r = simulate.monthly_returns(v)
    rfm = (pd.Series(rf_spec / 12.0, index=r.index) if not isinstance(rf_spec, RFCurve)
           else rf_spec.rf_monthly(v.index))
    def sh(a, b):
        m = (r.index >= a) & (r.index <= b)
        return sharpe_s(r[m], rfm.reindex(r.index)[m]) if m.sum() >= 3 else np.nan
    return {"sharpe": sharpe_s(r, rfm), "cagr": simulate.cagr(v), "vol": simulate.ann_vol(r), "max_dd": simulate.max_drawdown(v),
            "n_months": len(r), "sharpe_2022": sh("2022-04-01", "2022-12-31"),
            "sharpe_2307_2512": sh("2023-07-01", "2025-12-31"), "rf_ann_avg": float(rfm.mean() * 12), "r": r, "rfm": rfm}

def dsr_s(r, rfm, n_trials):
    """สูตรเดียวกับ simulate.deflated_sharpe (per-period รายเดือน) แต่ใช้ excess = r − rf_k"""
    r = r.dropna(); rfm = rfm.reindex(r.index)
    sd = r.std(ddof=1)
    sr_m = float((r - rfm).mean() / sd)
    n_eff = simulate.effective_n(r)
    skew = float(stats.skew(r.to_numpy(), bias=False)); kurt = float(stats.kurtosis(r.to_numpy(), fisher=False, bias=False))
    euler = 0.5772156649
    sr0 = 0.0 if n_trials <= 1 else ((1 - euler) * stats.norm.ppf(1 - 1.0 / n_trials) + euler * stats.norm.ppf(1 - 1.0 / (n_trials * np.e))) / np.sqrt(max(n_eff, 2.0))
    se = np.sqrt(max((1 - skew * sr_m + (kurt - 1) / 4.0 * sr_m ** 2) / max(n_eff - 1, 1e-6), 1e-12))
    return float(stats.norm.cdf((sr_m - sr0) / se))

def boot_ci(r, rfm, n_boot=2000, block=3, seed=0):
    rng = np.random.default_rng(seed)
    rv, fv = r.to_numpy(), rfm.reindex(r.index).to_numpy(); n = len(rv)
    nb = int(np.ceil(n / block)); out = []
    for _ in range(n_boot):
        idx = rng.integers(0, max(n - block, 0) + 1, size=nb)
        sel = np.concatenate([np.arange(i, i + block) for i in idx])[:n]
        a, f = rv[sel], fv[sel]; sd = a.std(ddof=1)
        if sd > 0: out.append((a - f).mean() * 12 / (sd * np.sqrt(12)))
    return float(np.percentile(out, 2.5)), float(np.percentile(out, 97.5))

# ---------------- plans ----------------
def load_plans():
    CLEAN = ("t", "e", "weights", "mode", "equity", "sleeve")
    PLANS = pickle.load(open(SC + "/validator_fee_plans.pkl", "rb"))
    calendar = common.load_calendar()
    for tid, w in (("M009-NC", "M009-NC_weights.csv"), ("M010-LLD", "M010-LLD_weights.csv")):
        d = pd.read_csv(common.RESULTS_DIR + "/" + w, parse_dates=["t", "e"])
        plan = []
        for (t, e), g in d.groupby(["t", "e"], sort=True):
            plan.append({"t": t, "e": e, "weights": dict(zip(g["FundCode"], g["weight"]))})
        PLANS[tid] = [plan]
    return PLANS, calendar

CASES = (("c0", 0.0, None), ("c50", 0.005, None), ("c100", 0.01, None), ("full", 0.0, "full"), ("nofront", 0.0, "nofront"))

def run_case(plan, nav_by_fund, months, kind, FD, curve, rf_ann_for_sim):
    cs, fmk = {"c0": (0.0, None), "c50": (0.005, None), "c100": (0.01, None), "full": (0.0, "full"), "nofront": (0.0, "nofront")}[kind]
    fm = fees.FeeModel(FD, fmk) if fmk else None
    info = {}
    if curve is None:
        v, tu, ev, _ = simulate.simulate_path(plan, nav_by_fund, months, cs, rf_ann_for_sim, include_start=True, info=info, fee_model=fm)
    else:
        with cash_curve(curve):
            v, tu, ev, _ = simulate.simulate_path(plan, nav_by_fund, months, cs, rf_ann_for_sim, include_start=True, info=info, fee_model=fm)
    return v, info["entries"]

def case_values(tid, kind, PLANS, nav_by_fund, months, FD, curve):
    vals, ents = [], []
    for plan in PLANS[tid]:
        v, en = run_case(plan, nav_by_fund, months, kind, FD, curve, RF_CONST)
        vals.append(v); ents.append(en)
    v = pd.concat(vals, axis=1).mean(axis=1) if len(vals) > 1 else vals[0]
    return v, ents

def cash_stats(ents, curve, real):
    """เงินสดเฉลี่ย (ถ่วงเวลาตาม target ของแต่ละ entry) และอัตราดอกเบี้ยที่เงินสดได้จริงถ่วงด้วยเงินสด"""
    num = den = 0.0; cw = []; tw_all = 0.0
    for en in ents:
        ends = [x["e"] for x in en[1:]] + [PE]
        for i, x in enumerate(en):
            d0, d1 = x["e"], min(ends[i], PE)
            if d1 <= d0: continue
            days = (d1 - d0).days
            c = x["target"].get("__CASH__", 0.0)
            ar = curve.avg_rate(d0, d1) if real else RF_CONST
            num += c * days * ar; den += c * days; cw.append((c * days, days))
    avg_cash = sum(a for a, _ in cw) / sum(b for _, b in cw)
    return avg_cash, (num / den if den > 0 else np.nan)

def main():
    t0 = time.time()
    nav = common.load_nav(); nav_by_fund = common.build_nav_by_fund(nav)
    PLANS, calendar = load_plans()
    quarters = common.quarter_ends(calendar, "2022-03-31", "2025-09-30")
    months = [m for m in common.month_ends(calendar, common.execution_date(calendar, quarters[0]), "2026-03-31")
              if m <= quarters[-1] + pd.Timedelta(days=75) + pd.Timedelta(days=31)]
    assert months[-1] == PE
    FD = fees.FeeData(sorted(nav["FundCode"].unique()))
    real, pol = load_policy(); const = const_curve(2.0)
    ORDER = ["B0", "M001-MS", "M001-EW", "M002-SR", "M002-MOM", "M002-NOH", "M003-ERC", "M003-HRP", "M004-VT", "M004-TF", "M005",
             "M005-N5", "M005-N10", "M005-NODD", "M004-TF-FX", "M006-TC", "M006-TCA", "M006-TCQ", "M007-6M", "M007-12M", "M008-GC",
             "M008-SQ", "M009-NC", "M010-LLD"]
    smoke = "smoke" in sys.argv
    if smoke: ORDER = ["M004-TF-FX", "M009-NC"]
    # ---- (A) regression: เส้นคงที่ 2% ผ่านเครื่องมือใหม่ ต้องตรงตัวเลขเดิมใน COST/M009/M010 summary ----
    cost = pd.read_csv(common.RESULTS_DIR + "/COST_real_fees_summary.csv").set_index("trial")
    m9 = pd.read_csv(common.RESULTS_DIR + "/M009_summary_metrics.csv"); m10 = pd.read_csv(common.RESULTS_DIR + "/M010_results.csv")
    ref = {}
    for tid in ORDER:
        for kind, col in (("c0", "c0"), ("c50", "c50"), ("full", "full"), ("nofront", "nofront")):
            if tid in cost.index:
                ref[(tid, kind)] = {k: cost.loc[tid, f"{k}_{col}"] for k in ("sharpe", "cagr", "vol")} if False else \
                    {"sharpe": cost.loc[tid, f"sharpe_{col}"], "cagr": cost.loc[tid, f"cagr_{col}"], "vol": cost.loc[tid, f"vol_{col}"], "max_dd": cost.loc[tid, f"maxdd_{col}"]}
            else:
                src = m9 if tid == "M009-NC" else m10
                row = src[(src["trial"] == tid) & (src["cost"] == col)].iloc[0]
                ref[(tid, kind)] = {"sharpe": row["sharpe"], "cagr": row["cagr"], "vol": row["vol"], "max_dd": row["max_dd"]}
    reg_rows, max_d = [], 0.0
    for tid in ORDER:
        for kind in ("c0", "c50", "full", "nofront"):
            v, _ = case_values(tid, kind, PLANS, nav_by_fund, months, FD, const)
            m = metrics(v, RF_CONST)
            d = {k: abs(m[k] - ref[(tid, kind)][k]) for k in ("sharpe", "cagr", "vol", "max_dd")}
            reg_rows.append({"trial": tid, "case": kind, "sharpe_new": m["sharpe"], "sharpe_ref": ref[(tid, kind)]["sharpe"], **{f"d_{k}": x for k, x in d.items()}})
            max_d = max(max_d, d["sharpe"])
    reg = pd.DataFrame(reg_rows)
    print(f"REGRESSION max|dSharpe| = {max_d:.3e} (n={len(reg)}) max|dCAGR|={reg['d_cagr'].max():.2e} max|dMaxDD|={reg['d_max_dd'].max():.2e} ({time.time()-t0:.0f}s)", flush=True)
    # regression 2: DSR/CI คงที่ 2% ผ่านฟังก์ชันชุดใหม่ = simulate เดิม
    v, _ = case_values("M004-TF-FX", "full", PLANS, nav_by_fund, months, FD, const); mm = metrics(v, RF_CONST)
    d_dsr = abs(dsr_s(mm["r"], mm["rfm"], 20) - simulate.deflated_sharpe(mm["r"], RF_CONST, 20))
    ci_old = simulate.block_bootstrap_ci(mm["r"], RF_CONST); ci_new = boot_ci(mm["r"], mm["rfm"])
    print(f"REG DSR d={d_dsr:.2e}  CI old {ci_old} new {ci_new}", flush=True)
    ok = max_d < 1e-6 and d_dsr < 1e-9 and max(abs(a - b) for a, b in zip(ci_old, ci_new)) < 1e-9
    reg.to_csv(SC + "/validator_realrf_regression.csv", index=False)
    if not ok:
        print("REGRESSION FAIL -> หยุด"); sys.exit(1)
    if smoke: return
    # ---- (B) รันจริง: rf 2% (ไม่แตะ ใช้ค่าอ้างอิงเดิมซ้ำจากเครื่องมือเดิม) vs rf จริง ----
    rows, extra = [], {}
    for tid in ORDER:
        o = {"trial": tid}
        for kind in ("c0", "c50", "c100", "full", "nofront"):
            v2, en2 = case_values(tid, kind, PLANS, nav_by_fund, months, FD, None)      # เครื่องมือเดิม ไม่แตะ
            vr, enr = case_values(tid, kind, PLANS, nav_by_fund, months, FD, real)
            m2, mr = metrics(v2, RF_CONST), metrics(vr, real)
            for tag, m in (("rf2", m2), ("real", mr)):
                for k in ("sharpe", "cagr", "vol", "max_dd", "sharpe_2022", "sharpe_2307_2512"):
                    o[f"{k}_{kind}_{tag}"] = m[k]
            if kind == "full":
                for nt in (22,):
                    o[f"dsr{nt}_rf2"] = dsr_s(m2["r"], m2["rfm"], nt); o[f"dsr{nt}_real"] = dsr_s(mr["r"], mr["rfm"], nt)
                o["ci_lo_rf2"], o["ci_hi_rf2"] = boot_ci(m2["r"], m2["rfm"]); o["ci_lo_real"], o["ci_hi_real"] = boot_ci(mr["r"], mr["rfm"])
                o["rf_avg_ann_real"] = mr["rf_ann_avg"]; o["n_months"] = mr["n_months"]
                a2, y2 = cash_stats(en2, real, False); ar, yr = cash_stats(enr, real, True)
                o["avg_cash_weight"], o["cash_yield_rf2"], o["cash_yield_real"] = ar, y2, yr
                e0 = enr[0][0]["e"]; o["policy_avg_rate_sim_period"] = real.avg_rate(e0, PE)
                o["cash_income_pp_yr_rf2"] = a2 * y2; o["cash_income_pp_yr_real"] = ar * yr
        rows.append(o)
        print(f"{tid:11s} full rf2={o['sharpe_full_rf2']:.3f} real={o['sharpe_full_real']:.3f}  nofront {o['sharpe_nofront_rf2']:.3f}->{o['sharpe_nofront_real']:.3f} "
              f"cash {o['avg_cash_weight']:.2f} y {o['cash_yield_rf2']*100:.2f}->{o['cash_yield_real']*100:.2f} ({time.time()-t0:.0f}s)", flush=True)
    S = pd.DataFrame(rows)
    S.to_csv(common.RESULTS_DIR + "/REAL_RF_summary.csv", index=False)
    reg.to_csv(SC + "/validator_realrf_regression.csv", index=False)
    json.dump({"max_dsharpe": max_d, "n_reg": len(reg), "d_dsr": d_dsr,
               "policy_avg_by_year": {str(y): float(real.rate[f"{y}-01-01":f"{y}-12-31"].mean()) for y in range(2022, 2026)}},
              open(SC + "/validator_realrf_meta.json", "w"))

if __name__ == "__main__":
    main()
