"""tf_model.py — ประกอบโมเดลหน้า 9 (M004-TF-FX): คัดกองรายไตรมาส · walk-forward · backtest · พอร์ตแนะนำ ณ วันที่เลือก.

ต่อไตรมาส t (ใช้ข้อมูล ≤ t):
  U_t (NAV สด + ประวัติพอ) -> I_t (ตัดกอง NAV เก่า/ภาษี/ปันผลซ้ำ/สัญญาณไม่ได้) -> ตัวแทน family ตาม SR12
  -> hysteresis เลือก N กอง -> ERC + เพดาน -> ถ้า ACWI < SMA200 ถือเงินสด TF_TREND_CASH
ซื้อขายที่ NAV วันทำการที่ TF_EXEC_LAG หลัง t แล้วถือจนรอบถัดไป
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

import config
from analysis import fund_backtest as fb
from analysis import fund_signals as fs
from analysis import fund_weighting as fw
from analysis.fund_backtest import CASH


@dataclass
class ModelInputs:
    """ข้อมูลที่โมเดลใช้ทั้งหมด (โหลดครั้งเดียวต่อการคำนวณ)."""
    nav: pd.DataFrame                    # long: FundCode, NAVDate, NAV, AUM
    calendar: pd.DatetimeIndex           # วันทำการของดัชนี MSCI
    trend_index: pd.Series               # ระดับ MSCI ACWI (บาท)
    groups: dict = field(default_factory=dict)
    nav_by_fund: dict = field(init=False)
    nav_arrays: dict = field(init=False)

    def __post_init__(self):
        self.nav_by_fund = {fc: g.set_index("NAVDate")["NAV"]
                            for fc, g in self.nav.sort_values("NAVDate").groupby("FundCode")}
        self.nav_arrays = fs.prep_arrays(self.nav_by_fund)


def select_at(inp: ModelInputs, t: pd.Timestamp, held: dict[str, str], prev_fallback: bool) -> dict:
    """ผลคัดกอง ณ t จากสถานะถือครองก่อนหน้า (held: family -> FundCode).

    คืน dict: t, counts, n_fresh, table (ตัวแทนทุก family + rank/สถานะ), sleeve (น้ำหนักส่วนหุ้น),
    weights (รวมเงินสด), trend, fallback, held (สถานะหลังรอบนี้), weight_source
    """
    u_t = fb.universe_at(inp.nav, t)
    fresh_mask = (t - u_t["last_nav_date"]).dt.days <= config.TF_FRESH_DAYS
    n_fresh = int(fresh_mask.sum())
    ctx = fs.SignalContext(inp.nav_arrays, inp.calendar, t)
    sig = fs.compute_signals(ctx, u_t["FundCode"].tolist())
    i_t, counts = fs.investable_set(t, u_t, sig, inp.groups)
    trend = fw.trend_state(inp.trend_index, t)

    reps = fw.family_representatives(i_t, held_funds=set(held.values()))
    ranks = fw.rank_families(reps)
    sel = fw.hysteresis_select(reps, ranks, {} if prev_fallback else held)
    table = pd.DataFrame([{"family": fam, "FundCode": r["FundCode"], "SR12": r["signal"], "vol52": r["vol52"],
                           "rank": ranks[fam]} for fam, r in reps.items()])
    if len(table):
        table = table.merge(i_t[["FundCode", "R12_1", "fam_source"]], on="FundCode", how="left")
        table = table.sort_values("rank").reset_index(drop=True)

    is_fallback = sel["fallback"] == "b0" or not sel["S"]
    dropped = drop_reasons(held, {} if is_fallback else sel["S"], set(u_t["FundCode"]),
                           set(u_t.loc[fresh_mask, "FundCode"]), set(i_t["FundCode"]), ranks, is_fallback)
    out = {"t": t, "counts": counts, "n_fresh": n_fresh, "trend": trend, "table": table,
           "kept": sel["kept"], "dropped": dropped}
    if is_fallback:
        b0 = fb.b0_universe(u_t, inp.groups)
        sleeve = pd.Series(1.0 / len(b0), index=b0["FundCode"]) if len(b0) else pd.Series(dtype=float)
        out.update(fallback=True, held={}, sleeve=sleeve, weight_source="b0", selected={})
    else:
        funds = list(sel["S"].values())
        wk = {fc: ctx.weekly_return_series(fc) for fc in funds}
        vol_map = dict(zip(i_t["FundCode"], i_t["vol52"]))
        w, src = fw.risk_parity_weights(funds, wk, vol_map)
        out.update(fallback=False, held=dict(sel["S"]), sleeve=fw.apply_cap(w), weight_source=src,
                   selected=dict(sel["S"]))
    c = trend["cash"]
    weights = {fc: (1.0 - c) * float(v) for fc, v in out["sleeve"].items() if v > 0}
    if c > 0:
        weights[CASH] = c
    out["weights"] = weights
    return out


def drop_reasons(held: dict[str, str], selected: dict[str, str], in_universe: set, fresh: set,
                 investable: set, ranks: dict[str, int], fallback: bool) -> list[dict]:
    """กองที่ถืออยู่แต่ไม่ได้ถือต่อ (รวมกรณีเปลี่ยนไปถือ class อื่นของกองเดียวกัน) พร้อมเหตุผล.

    แยก "ข้อมูลไม่พร้อม" (NAV เก่า/ไม่สด/สัญญาณคำนวณไม่ได้) ออกจาก "หลุดอันดับ" — ช่วง NAV ขาดปี 2026
    กองถูกตัดเพราะ NAV ไม่สดเป็นส่วนใหญ่ ไม่ใช่สัญญาณขาย
    """
    out = []
    for fam, fc in held.items():
        new_fc = selected.get(fam)
        if new_fc == fc:
            continue
        if fallback:
            reason = f"คัดได้น้อยกว่า {config.TF_MIN_FUNDS} กอง → ถือแบบ B0"
        elif fc not in in_universe:
            reason = f"NAV ล่าสุดเก่ากว่า {config.NAV_STALE_MAX_DAYS} วัน (ข้อมูลไม่พร้อม)"
        elif fc not in fresh:
            reason = f"NAV ไม่สด — ล่าสุดห่างเกิน {config.TF_FRESH_DAYS} วัน (ข้อมูลไม่พร้อม)"
        elif fc not in investable:
            reason = "สัญญาณคำนวณไม่ได้ / ไม่ผ่านเกณฑ์ class (ข้อมูลไม่พร้อม)"
        elif ranks.get(fam, 10**9) > config.TF_HYSTERESIS_K:
            reason = f"หลุดอันดับ ({ranks.get(fam, '—')} > {config.TF_HYSTERESIS_K})"
        else:
            reason = "ไม่ถูกเลือก"
        if new_fc:
            reason += f" · ถือ {new_fc} (class อื่นของกองเดียวกัน) แทน"
        out.append({"family": fam, "FundCode": fc, "reason": reason, "data_issue": "ข้อมูลไม่พร้อม" in reason})
    return out


def complete_quarters(calendar: pd.DatetimeIndex, start: str, end) -> list[pd.Timestamp]:
    """สิ้นไตรมาสที่จบแล้ว (เดือน 3/6/9/12).

    ไตรมาสล่าสุดนับเฉพาะเมื่อข้อมูลไปถึงสิ้นไตรมาสจริง: มีวันในปฏิทินหลัง t แล้ว หรือ t เป็นวันทำการสุดท้ายของเดือน
    (กันกรณีไฟล์ MSCI อัปเดตถึงกลางเดือน เช่น 15 ก.ย. แล้วถูกนับเป็น rebalance)
    """
    last = calendar.max()
    return [t for t in fb.quarter_ends(calendar, start, end)
            if t.month in (3, 6, 9, 12) and (t < last or t == t + pd.offsets.BMonthEnd(0))]


def walk_forward(inp: ModelInputs, quarters: list[pd.Timestamp], coverage_ref: int | None = None) -> list[dict]:
    """คัดกองต่อเนื่องทุกไตรมาส (สถานะ hysteresis ส่งต่อกันไป).

    coverage_ref: จำนวนกองสด ณ TF_COVERAGE_REF — ไตรมาสหลังวันนั้นที่กองสด < TF_COVERAGE_MIN × ค่านี้
    ถูกข้าม (คงสถานะเดิม ไม่ซื้อขาย) · None = ไม่ข้าม (backtest)
    """
    held, prev_fb = {}, False
    out = []
    for t in quarters:
        r = select_at(inp, t, held, prev_fb)
        r["coverage"] = coverage(r["n_fresh"], coverage_ref)
        r["skipped"] = bool(coverage_ref and t > pd.Timestamp(config.TF_COVERAGE_REF)
                            and r["coverage"] < config.TF_COVERAGE_MIN)
        if not r["skipped"]:
            held, prev_fb = r["held"], r["fallback"]
        r["held_after"] = dict(held)
        r["prev_fallback_after"] = prev_fb
        out.append(r)
    return out


def build_plan(results: list[dict], calendar: pd.DatetimeIndex, key: str = "weights") -> list[dict]:
    """แปลงผลคัดกองเป็นแผนซื้อขายของ simulate_path (ข้ามไตรมาสที่ถูกข้าม/ยังไม่มีวันซื้อขาย)."""
    plan = []
    for r in results:
        e = fb.execution_date(calendar, r["t"])
        if r.get("skipped") or e is None:
            continue
        plan.append({"t": r["t"], "e": e, "weights": r[key]})
    return plan


def b0_plan(inp: ModelInputs, quarters: list[pd.Timestamp]) -> list[dict]:
    """baseline B0: ถือทุกกองใน U_t เท่ากัน (1 class ต่อกลุ่ม) rebalance ทุกไตรมาส."""
    plan = []
    for t in quarters:
        b0 = fb.b0_universe(fb.universe_at(inp.nav, t), inp.groups)
        plan.append({"t": t, "e": fb.execution_date(inp.calendar, t),
                     "weights": {fc: 1.0 / len(b0) for fc in b0["FundCode"]}})
    return plan


def eval_months(inp: ModelInputs, plan: list[dict]) -> list[pd.Timestamp]:
    return fb.month_ends(inp.calendar, plan[0]["e"], config.TF_EVAL_END)


def run_cases(inp: ModelInputs, plan: list[dict], fee_data) -> dict[str, tuple[pd.Series, list]]:
    """มูลค่าพอร์ตสิ้นเดือน 3 กรณีต้นทุน: flat (0.5%/ข้าง), full (ค่าธรรมเนียมจริง), nofront (ยกเว้น front-end)."""
    from analysis.fund_fees import FeeModel
    months = eval_months(inp, plan)
    rf = config.TF_RF_SIM
    out = {"flat": fb.simulate_path(plan, inp.nav_by_fund, months, rf, cost_side=config.TF_COST_FLAT)}
    for mode in ("full", "nofront"):
        out[mode] = fb.simulate_path(plan, inp.nav_by_fund, months, rf, fee_model=FeeModel(fee_data, mode))
    return out


def holdings_frame(results: list[dict], calendar: pd.DatetimeIndex) -> pd.DataFrame:
    """ตารางน้ำหนักต่อไตรมาส (long) + family/สถานะ (คงไว้/เพิ่มใหม่) ของแต่ละกอง."""
    rows = []
    for r in results:
        fam_of = {fc: fam for fam, fc in r.get("selected", {}).items()}
        for fc, w in r["weights"].items():
            fam = fam_of.get(fc, "")
            status = "cash" if fc == CASH else ("kept" if fam in r["kept"] else ("b0" if r["fallback"] else "added"))
            rows.append({"t": r["t"], "e": fb.execution_date(calendar, r["t"]), "FundCode": fc, "family": fam,
                         "weight": w, "status": status, "skipped": r.get("skipped", False)})
    return pd.DataFrame(rows)


def quarter_log(results: list[dict]) -> pd.DataFrame:
    """สรุปต่อไตรมาส: ขนาด universe, กองสด, cash, fallback, ข้ามไหม."""
    return pd.DataFrame([{
        "t": r["t"], "n_universe": r["counts"]["n_universe"], "n_fresh": r["n_fresh"],
        "n_investable": r["counts"]["n_investable"], "n_families": len(r["table"]),
        "trend_below": r["trend"]["below"], "cash": r["trend"]["cash"], "fallback": r["fallback"],
        "weight_source": r["weight_source"], "skipped": r.get("skipped", False),
        "n_kept": len(r["kept"]), "n_selected": len(r.get("selected", {})),
        "coverage": r.get("coverage", np.nan)} for r in results])


def state_before(log_holdings: pd.DataFrame, log: pd.DataFrame, as_of: pd.Timestamp) -> tuple[dict, bool]:
    """สถานะถือครอง (family -> FundCode, prev_fallback) จากไตรมาส replay ล่าสุดที่ < as_of และไม่ถูกข้าม."""
    done = log[(log["t"] < as_of) & (~log["skipped"])]
    if done.empty:
        return {}, False
    last = done.iloc[-1]
    if bool(last["fallback"]):
        return {}, True
    h = log_holdings[(log_holdings["t"] == last["t"]) & (log_holdings["FundCode"] != CASH)
                     & (log_holdings["family"] != "")]
    return dict(zip(h["family"], h["FundCode"])), False


def year_returns(values: pd.Series) -> dict[int, float]:
    """ผลตอบแทนรายปีปฏิทิน (ปีแรกนับจากวันซื้อแรก)."""
    out = {}
    for y in sorted(set(values.index.year)):
        prev = values[values.index < pd.Timestamp(f"{y}-01-01")]
        start = prev.iloc[-1] if len(prev) else values.iloc[0]
        out[y] = float(values[values.index <= pd.Timestamp(f"{y}-12-31")].iloc[-1] / start - 1)
    return out


def coverage(n_fresh: int, coverage_ref: int | None) -> float:
    """สัดส่วนกองสดเทียบวันอ้างอิง (นิยามเดียวที่ใช้ทั้งกติกาข้ามไตรมาส ตาราง replay และพอร์ตแนะนำ)."""
    return float(n_fresh / coverage_ref) if coverage_ref else np.nan
