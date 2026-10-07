"""sens_settlement.py — งาน 3 (2026-10-06): sensitivity เงินค้าง T+k (R005 ข้อ A7) · ไม่ใช่ trial · ไม่แตะ trials.csv/simulate.py/ไฟล์เดิม

กติกา (ผู้ใช้ตัดสิน): ขาขายใช้ NAV ที่ e เดิม · ขาซื้อกองใหม่ใช้ NAV ของวันทำการที่ e+k (NAVDate แรก >= e+k, ช่องว่างเกิน 10 วันทำการ = ซื้อไม่ได้ -> เงินสดได้ rf)
 k = k_switch (3) ถ้าเงินมาจากการขายกองใน บลจ. เดียวกัน (สับเปลี่ยน) · k = k_cross (5) ถ้ามาจากการขายกองข้าม บลจ. · k = 0 ถ้ามาจากเงินสด -> กอง
ระหว่างรอ เงินอยู่เป็นเงินสด "ไม่มีดอกเบี้ย" (ทั้ง k_switch/k_cross) · ส่วนที่ถือต่อเนื่อง (ไม่ได้ขาย) ไม่มีผล · วันทำการ = จันทร์-ศุกร์ (np.busday_offset, ไม่มีปฏิทินวันหยุดไทย)
การจัดสรรเงินซื้อแต่ละกอง: (1) ส่วนที่จับคู่กับยอดขายใน บลจ. เดียวกัน min(ขาย,ซื้อ) ของ บลจ. นั้น = สับเปลี่ยน (ตรงกับที่ fees.FeeModel จับคู่) ·
 (2) ที่เหลือ: ส่วนที่ถูกจ่ายจากการลดเงินสด (cash release R = เงินสดก่อน − เงินสดเป้าหมาย; รอบแรกถือว่าเงินทุนเริ่มต้นเป็นเงินสด) = k 0 · ส่วนที่เหลือจากการขายข้าม บลจ. = k_cross
 (สัดส่วนเท่ากันทุกกองที่ซื้อ) · ยอดขายที่ไปเป็นเงินสดเป้าหมายถือว่าได้ดอกเบี้ยตั้งแต่ e เหมือนเดิม (ไม่เปลี่ยน)
regression: k=(0,0) ต้องได้อนุกรมมูลค่าเดียวกับ simulate.simulate_path ทุกจุด (max|Δ| < 1e-9) ทั้ง full/nofront/c0
รัน: PYTHONPATH=. ./.venv/bin/python .claude/quant_team/backtest/sens_settlement.py   (ต้องรัน rerun_retail_universe.py ก่อน เพื่อให้มี scratch/validator_retail_plans.pkl)"""
from __future__ import annotations

import os
import pickle
import sys
import time
from collections import defaultdict

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if THIS_DIR not in sys.path:
    sys.path.insert(0, THIS_DIR)

import numpy as np
import pandas as pd

import common
import fees
import simulate
import run_m011 as r11
import remeasure_real_rf as rr
from data import msci_index

TEAM_DIR = os.path.dirname(THIS_DIR)
SCRATCH = os.path.join(TEAM_DIR, "scratch")
RES = common.RESULTS_DIR
PE = r11.PE
MAX_GAP = 10
GRID = [("T+0 (เดิม)", 0, 0), ("T+3/T+5 (หลัก)", 3, 5), ("เบา T+2/T+3", 2, 3), ("หนัก T+5/T+7", 5, 7)]
KINDS3 = ("full", "nofront", "c0")


def _busday(e: pd.Timestamp, k: int) -> pd.Timestamp:
    return pd.Timestamp(np.busday_offset(e.date(), k, roll="forward"))


def _nav_last(nbf, fc, day):
    px, _ = simulate._nav_last(nbf, fc, day)
    return px


def _exec_at(nbf, fc, d0, max_gap=MAX_GAP):
    """NAV ของ NAVDate แรก >= d0 (ช่องว่างจาก d0 <= max_gap วันทำการ) -> (px, date) หรือ None."""
    s = nbf.get(fc)
    if s is None:
        return None
    s2 = s.loc[d0:]
    if len(s2) == 0:
        return None
    d = s2.index[0]
    if int(np.busday_count(d0.date(), d.date())) > max_gap:
        return None
    return float(s2.iloc[0]), d


def settle_path(plan, nbf, months, fee_model, amc, k_switch, k_cross, start_value=100.0):
    """คืน (values: Series (รวมจุดเริ่ม), entries: list, stats: dict) · fee_model=None -> ต้นทุน 0."""
    unit_lots = []        # {fund, units, amount, start}   (ก่อน start นับเป็นเงินสดไม่มีดอกเบี้ย = amount)
    cash_lots = []        # (amount, since)             (ได้ rf ตั้งแต่ since)
    records, entries = [], []
    idle_dollar_days = 0.0
    total_dollar_days = 0.0
    buy_split = defaultdict(float)
    n_months = len(months)
    m_idx = 0

    def total_value(d):
        v = 0.0
        for lot in unit_lots:
            if d >= lot["start"]:
                px = _nav_last(nbf, lot["fund"], d)
                v += lot["units"] * (px if px is not None else 0.0)
            else:
                v += lot["amount"]
        for a, s in cash_lots:
            v += simulate._grow_cash(a, s, d, 0.02)
        return v

    for qi, p in enumerate(plan):
        e, tw = p["e"], p["weights"]
        t_funds = {f: w for f, w in tw.items() if f != "__CASH__"}
        tgt_cash_w = float(tw.get("__CASH__", 0.0))
        assert p.get("mode", "full") == "full"
        first = qi == 0
        cur = defaultdict(float)
        for lot in unit_lots:
            assert lot["start"] <= e, "ล็อตซื้อยังไม่เสร็จก่อนรอบถัดไป"
            px = _nav_last(nbf, lot["fund"], e)
            cur[lot["fund"]] += lot["units"] * (px if px is not None else 0.0)
        cash_e = sum(simulate._grow_cash(a, s, e, 0.02) for a, s in cash_lots)
        if first:
            value, cash_e = start_value, start_value      # เงินทุนเริ่มต้น = เงินสด
        else:
            value = sum(cur.values()) + cash_e
        drift_w = {f: v / value for f, v in cur.items()} if value > 0 else {}
        all_f = set(drift_w) | set(t_funds)
        turnover = sum(abs(t_funds.get(f, 0.0) - drift_w.get(f, 0.0)) for f in all_f) / 2.0
        cost = 0.0 if fee_model is None else fee_model.entry_cost(e, drift_w, t_funds)[0]
        value_new = value * (1 - cost)
        entries.append({"t": p["t"], "e": e, "mode": "full", "turnover": turnover, "cost": cost,
                        "target": {**t_funds, "__CASH__": tgt_cash_w}})
        alloc = {f: value_new * w for f, w in t_funds.items() if w > 0}
        keep = {f: min(cur.get(f, 0.0), a) for f, a in alloc.items()}
        buy = {f: a - keep[f] for f, a in alloc.items() if a - keep[f] > 1e-12}
        sell = {f: cur[f] - keep.get(f, 0.0) for f in cur if cur[f] - keep.get(f, 0.0) > 1e-12}
        # --- จัดสรรแหล่งเงินซื้อ ---
        S_amc, B_amc = defaultdict(float), defaultdict(float)
        for f, x in sell.items():
            S_amc[amc.get(f, f)] += x
        for f, x in buy.items():
            B_amc[amc.get(f, f)] += x
        m_amc = {a: min(S_amc[a], B_amc[a]) for a in B_amc if a in S_amc}
        B_rem = sum(buy.values()) - sum(m_amc.values())
        R = cash_e - value_new * tgt_cash_w
        cash_part = min(max(R, 0.0), B_rem) if B_rem > 0 else 0.0
        cash_frac = cash_part / B_rem if B_rem > 1e-12 else 0.0
        # --- สร้างล็อต ---
        new_units, new_cash = [], []
        for f, k_amt in keep.items():
            if k_amt <= 0:
                continue
            r = _exec_at(nbf, f, e)       # เหมือน simulate._exec_nav (ส่วนที่ถือต่อ ซื้อใหม่ที่ราคา e ตามเดิม)
            if r is None:
                new_cash.append((k_amt, e))
            else:
                new_units.append({"fund": f, "units": k_amt / r[0], "amount": k_amt, "start": e})
        for f, b in buy.items():
            a = amc.get(f, f)
            s_part = b * (m_amc.get(a, 0.0) / B_amc[a]) if B_amc[a] > 0 else 0.0
            r_part = b - s_part
            parts = [(k_switch, s_part, "switch"), (0, r_part * cash_frac, "cash"), (k_cross, r_part * (1 - cash_frac), "cross")]
            for k, amt, tag in parts:
                if amt <= 1e-12:
                    continue
                buy_split[tag] += amt / value_new
                d0 = e if k == 0 else _busday(e, k)
                r = _exec_at(nbf, f, d0)
                if r is None:
                    new_cash.append((amt, d0))
                    idle_dollar_days += amt * max((d0 - e).days, 0)
                else:
                    px, dx = r
                    new_units.append({"fund": f, "units": amt / px, "amount": amt, "start": e if k == 0 else dx})
                    idle_dollar_days += amt * max((dx - e).days, 0) if k > 0 else 0.0
        tgt_cash_amt = value_new * tgt_cash_w
        if tgt_cash_amt > 1e-12:
            new_cash.append((tgt_cash_amt, e))
        unit_lots, cash_lots = new_units, new_cash
        next_e = plan[qi + 1]["e"] if qi + 1 < len(plan) else (months[-1] + pd.Timedelta(days=1))
        total_dollar_days += value_new * max((min(next_e, PE) - e).days, 0)
        while m_idx < n_months and months[m_idx] < next_e:
            md = months[m_idx]
            if md >= e:
                records.append((md, total_value(md)))
            m_idx += 1
    values = pd.Series(dict(records)).sort_index()
    values = pd.concat([pd.Series({plan[0]["e"]: start_value}), values]).sort_index()
    stats = {"idle_share_dollar_days": idle_dollar_days / total_dollar_days if total_dollar_days else np.nan, "buy_split": dict(buy_split)}
    return values, entries, stats


def run_case(plan, nbf, months, fd, real, kind, ks, kc):
    fm = fees.FeeModel(fd, kind) if kind in ("full", "nofront") else None
    with rr.cash_curve(real):
        v, en, st = settle_path(plan, nbf, months, fm, fd.amc, ks, kc)
    return v, en, st


def baseline_values(plan, nbf, months, fd, real, kind):
    clean = [{k: v for k, v in p.items() if k in ("t", "e", "weights")} for p in plan]
    fm = fees.FeeModel(fd, kind) if kind in ("full", "nofront") else None
    with rr.cash_curve(real):
        v, _, _, _ = simulate.simulate_path(clean, nbf, months, 0.0, 0.02, include_start=True, info={}, fee_model=fm)
    return v


def main():
    t0 = time.time()
    nav = common.load_nav()
    nbf = common.build_nav_by_fund(nav)
    cal = common.load_calendar()
    codes = sorted(nav["FundCode"].unique())
    fd = fees.FeeData(codes)
    real, _ = rr.load_policy()
    q16 = common.quarter_ends(cal, "2022-03-31", "2025-12-31")
    q15 = q16[:15]
    months = [m for m in common.month_ends(cal, common.execution_date(cal, q15[0]), "2026-03-31") if m <= q15[-1] + pd.Timedelta(days=75) + pd.Timedelta(days=31)]
    assert months[-1] == PE
    PK = pickle.load(open(os.path.join(SCRATCH, "validator_retail_plans.pkl"), "rb"))
    MODELS = [("Trend25", "Trend 25 (M004-TF-FX)"), ("M013-GC75", "M013-GC75")]
    UNIV = [("retail", PK["plans_retail"]), ("full", PK["plans_full"])]
    # regression: k=(0,0) = simulate_path
    maxd = 0.0
    for uname, plans in UNIV:
        for m, _ in MODELS:
            for kind in KINDS3:
                v0, _, _ = run_case(plans[m], nbf, months, fd, real, kind, 0, 0)
                vb = baseline_values(plans[m], nbf, months, fd, real, kind)
                d = float((v0 - vb.reindex(v0.index)).abs().max())
                maxd = max(maxd, d)
    print(f"REGRESSION max|Δvalue| (k=0,0 vs simulate_path) = {maxd:.2e}", flush=True)
    assert maxd < 1e-9, "regression fail"
    rows = []
    for uname, plans in UNIV:
        for m, label in MODELS:
            base = {}
            for gname, ks, kc in GRID:
                o = {"universe": uname, "model": label, "scenario": gname, "k_switch": ks, "k_cross": kc}
                for kind in KINDS3:
                    v, en, st = run_case(plans[m], nbf, months, fd, real, kind, ks, kc)
                    mt = rr.metrics(v, real)
                    o[f"sharpe_{kind}"], o[f"cagr_{kind}"] = mt["sharpe"], mt["cagr"]
                    if kind == "full":
                        o["vol"], o["maxdd"], o["sharpe_2022"] = mt["vol"], mt["max_dd"], mt["sharpe_2022"]
                        o["idle_share"] = st["idle_share_dollar_days"]
                        o["buy_share_switch"], o["buy_share_cash"], o["buy_share_cross"] = (st["buy_split"].get(x, 0.0) for x in ("switch", "cash", "cross"))
                        r_ = mt["r"]
                        o["_r"], o["_rfm"] = r_, mt["rfm"]
                        es = np.array([x["e"] for x in plans[m]], dtype="datetime64[ns]")
                        qm = pd.Series([max(0, int(np.searchsorted(es, np.datetime64(x), side="left")) - 1) for x in r_.index], index=r_.index)
                        o["_qm"] = qm
                        keep_m = qm != 12          # ตัดไตรมาส t=2025-03-31 (ช็อกภาษีศุลกากร เม.ย. 2025)
                        o["sharpe_full_ex_2025Q1"] = rr.sharpe_s(r_[keep_m], o["_rfm"].reindex(r_.index)[keep_m])
                        if gname.startswith("T+0"):
                            base["r"] = r_
                            base["shex"] = o["sharpe_full_ex_2025Q1"]
                rows.append(o)
            # paired Δ เทียบ T+0
            for o in rows:
                if o["universe"] == uname and o["model"] == label and "d_sharpe_full" not in o:
                    if o["scenario"].startswith("T+0"):
                        o["d_sharpe_full"], o["d_ci_lo"], o["d_ci_hi"] = 0.0, 0.0, 0.0
                    else:
                        lo, hi, pt = r11.paired_real(o["_r"], base["r"], o["_rfm"], "r")
                        o["d_sharpe_full"], o["d_ci_lo"], o["d_ci_hi"] = pt, lo, hi
                    o["d_sharpe_ex_2025Q1"] = o["sharpe_full_ex_2025Q1"] - base["shex"]
                    if o["scenario"].startswith("T+3"):
                        dq = (o["_r"] - base["r"]).groupby(o["_qm"]).sum()
                        pd.DataFrame({"qi": dq.index, "t": [q15[i].date() for i in dq.index], "sum_dret_T35_minus_T0": dq.values}).to_csv(
                            os.path.join(RES, f"SETTLEMENT_perq_{uname}_{m}.csv"), index=False)
    out = pd.DataFrame([{k: v for k, v in o.items() if not k.startswith("_")} for o in rows])
    out.to_csv(os.path.join(RES, "SETTLEMENT_sensitivity.csv"), index=False)
    pd.set_option("display.width", 250)
    print(out.round(4).to_string())
    print(f"DONE {time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()
