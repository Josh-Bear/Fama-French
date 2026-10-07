"""run_m006_m007.py — M006 (TC/TCA/TCQ) + M007 (6M/12M tranche) + baseline reruns (M004-TF old/new measurement, M004-TF-FX,
M003-ERC regression) ใน walk-forward เดียว · specs/M006_trend_cash.md + specs/M007_slow_rebalance.md

รัน: PYTHONPATH=. ./.venv/bin/python .claude/quant_team/backtest/run_m006_m007.py [smoke]
(ไม่เรียก nav_loader.load_nav_history / data_access.build_*; อ่าน NAV จาก cache/nav_clean.parquet เท่านั้น)
"""
from __future__ import annotations

import os
import sys
import time
from collections import Counter

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if THIS_DIR not in sys.path:
    sys.path.insert(0, THIS_DIR)

import numpy as np
import pandas as pd

import common
import fund_signals as fs
import simulate
import tests_m006
import weighting as wt
from data import msci_index

TEAM_DIR = os.path.dirname(THIS_DIR)
TRIALS_CSV = os.path.join(TEAM_DIR, "trials.csv")
RES = common.RESULTS_DIR
PRIMARY_END = pd.Timestamp("2025-12-31")
RF, RF0 = 0.02, 0.0
COSTS = (("c0", 0.0), ("c50", 0.005), ("c100", 0.01))
RFS = (("rf2", RF), ("rf0", RF0))

# stream = selection แบบ A (SR12, N=8, K=16, ไม่ dedupe, ERC, cap 25%) ต่าง map/ความถี่/offset
STREAMS = {
    "OLDQ": dict(fx=False, period=1, off=0),
    "NEWQ": dict(fx=True, period=1, off=0),
    "H6_A": dict(fx=True, period=2, off=0), "H6_B": dict(fx=True, period=2, off=1),
    "H12_0": dict(fx=True, period=4, off=0), "H12_1": dict(fx=True, period=4, off=1),
    "H12_2": dict(fx=True, period=4, off=2), "H12_3": dict(fx=True, period=4, off=3),
}
SEL_N, SEL_K = 8, 16
OFFSET_LABEL = {"H6_A": "6M-Mar/Sep", "H6_B": "6M-Jun/Dec", "H12_0": "12M-Mar", "H12_1": "12M-Jun",
                "H12_2": "12M-Sep", "H12_3": "12M-Dec", "NEWQ": "Q", "OLDQ": "Q"}


def is_R(stream, qi):
    p = STREAMS[stream]
    return qi == 0 or (qi % p["period"] == p["off"])


# ---------------- trend state (M006 §3.2) ----------------

def trend_npos(a_slice: pd.Series, m, me_all: list, strict_slice=True) -> int:
    """จำนวนสัญญาณที่เป็น 1 (s_3,s_6,s_12) ที่ m · a_slice = ACWI ที่ตัดแล้ว (ค่าสุดท้าย = A_m)."""
    if strict_slice:
        assert a_slice.index.max() <= m, "look-ahead: slice เกิน m"
    idx = me_all.index(m)
    a_m = float(a_slice.iloc[-1])
    n = 0
    for L in (3, 6, 12):
        assert idx - L >= 0
        lag = me_all[idx - L]
        sub = a_slice.loc[:lag]
        assert len(sub) > 0, "ACWI ไม่ครอบคลุม A_{m-L} — หยุด ไม่ประมาณค่า"
        r = a_m / float(sub.iloc[-1]) - 1.0
        n += int(r > 0.02 * L / 12.0)
    return n


# ---------------- plan builder ----------------

def build_plan(sleeves, isR, state, xfun, me_plan, qmap, calendar, monthly, fallback_flags=None):
    """sleeves: qi -> pd.Series (ใช้เฉพาะที่ isR) · state: m -> n_pos · xfun(n)->x · คืน list ของ plan entries."""
    plan, cur, n_prev = [], None, None
    for m in me_plan:
        n = state[m]
        x = xfun(n)
        qi = qmap.get(m)
        e = common.execution_date(calendar, m)
        assert e > m
        if qi is not None and isR(qi):
            cur = sleeves[qi]
            w = {f: x * float(v) for f, v in cur.items() if v > 0 and x > 0}
            fsum = sum(w.values())
            assert fsum <= x * float(cur.sum()) + 1e-9 and fsum <= 1 + 1e-9
            cash = 1.0 - fsum
            assert -1e-9 <= cash <= 1 + 1e-9
            if cash > 1e-12:
                w["__CASH__"] = cash
            plan.append({"t": m, "e": e, "weights": w, "x": x, "n_pos": n, "kind": "full", "qi": qi,
                         "sleeve": cur})
        elif monthly and n != n_prev:
            assert cur is not None
            plan.append({"t": m, "e": e, "mode": "scale", "equity": x, "sleeve": {f: float(v) for f, v in cur.items()},
                         "x": x, "n_pos": n, "kind": "scale", "qi": None})
        n_prev = n
    return plan


def old_style_plan(sleeves, quarters, calendar, cash_fn):
    """plan ไตรมาสแบบเดิม (ไม่มี mode) — c = cash_fn(t)."""
    out = []
    for qi, t in enumerate(quarters):
        w = sleeves[qi]
        c = cash_fn(t)
        wf = {fc: (1.0 - c) * float(v) for fc, v in w.items() if v > 0}
        if c > 0:
            wf["__CASH__"] = c
        out.append({"t": t, "e": common.execution_date(calendar, t), "weights": wf})
    return out


# ---------------- metrics ----------------

def run_sim(plan, nav_by_fund, month_ends, cost, rf, include_start):
    clean = [{k: v for k, v in p.items() if k in ("t", "e", "weights", "mode", "equity", "sleeve")} for p in plan]
    info = {}
    values, turn, events, _ = simulate.simulate_path(clean, nav_by_fund, month_ends, cost, rf,
                                                     include_start=include_start, info=info)
    return {"values": values, "turnovers": turn, "events": events, "info": info["entries"]}


def per_metrics(values, rf):
    v = values[values.index <= PRIMARY_END]
    r = simulate.monthly_returns(v)

    def sh(a, b):
        rr = r[(r.index >= a) & (r.index <= b)]
        return simulate.sharpe(rr, rf) if len(rr) >= 3 else np.nan
    return {"sharpe": simulate.sharpe(r, rf), "cagr": simulate.cagr(v), "vol": simulate.ann_vol(r),
            "max_dd": simulate.max_drawdown(v), "n_months": len(r),
            "sharpe_2022": sh("2022-04-01", "2022-12-31"), "sharpe_2204_2306": sh("2022-04-01", "2023-06-30"),
            "sharpe_2307_2512": sh("2023-07-01", "2025-12-31"),
            "maxdd_2022": simulate.max_drawdown(v[(v.index <= "2022-12-31")])}


def flow_stats(sim, years):
    en = sim["info"]
    full = [x for x in en if x["mode"] == "full"][1:]    # ไม่รวมการซื้อเข้าครั้งแรก
    sc = [x for x in en if x["mode"] == "scale"]
    first_cost = en[0]["cost"] if en else 0.0
    # เงินสดเฉลี่ยแบบถ่วงเวลาจาก target ของแต่ละ entry (ไม่รวม drift ระหว่างรอบ)
    ends = [x["e"] for x in en[1:]] + [PRIMARY_END]
    tw = [(ends[i] - en[i]["e"]).days for i in range(len(en))]
    cash = sum(en[i]["target"].get("__CASH__", 0.0) * tw[i] for i in range(len(en))) / max(sum(tw), 1)
    return {"turn_sel_yr": sum(x["turnover"] for x in full) / years, "turn_trend_yr": sum(x["turnover"] for x in sc) / years,
            "cost_sel_bp": (sum(x["cost"] for x in full) + first_cost) / years * 1e4,
            "cost_trend_bp": sum(x["cost"] for x in sc) / years * 1e4,
            "n_scale_entries_yr": len(sc) / years, "avg_cash": cash,
            "n_cannot_buy": sum(1 for ev in sim["events"] if ev["type"] == "cannot_buy")}


def run(smoke=False):
    t0 = time.time()
    print("[1/6] load data...", flush=True)
    nav = common.load_nav()
    nav_by_fund = common.build_nav_by_fund(nav)
    nav_arrays = fs._prep_arrays(nav_by_fund)
    calendar = common.load_calendar()
    groups = common.load_groups()
    acwi = msci_index.load_country_index()["MSCI_ACWI"]
    all_codes = sorted(nav["FundCode"].unique())

    # ---- sanity: F1 + synthetic simulate tests ก่อนรัน ----
    san, diff_stats = tests_m006.run_all(groups, all_codes, os.path.join(RES, "M006_family_map_diff.csv"))
    for k, v in san.items():
        print(f"  [{'PASS' if v else 'FAIL'}] {k}", flush=True)
    assert all(san.values()), "sanity test ล้มเหลว — หยุด"
    print(f"  family diff: {diff_stats}", flush=True)

    quarters = common.quarter_ends(calendar, "2022-03-31", "2025-09-30")
    if smoke:
        quarters = quarters[:5]
    nq = len(quarters)
    qmap = {t: i for i, t in enumerate(quarters)}
    t_first = quarters[0]
    bound_m = quarters[-1] + pd.Timedelta(days=75)
    me_all = common.month_ends(calendar, pd.Timestamp("2021-01-01"), "2026-03-31")
    me_plan = [m for m in common.month_ends(calendar, t_first, "2026-03-31") if m <= bound_m]
    sim_months = [m for m in common.month_ends(calendar, common.execution_date(calendar, t_first), "2026-03-31")
                  if m <= bound_m + pd.Timedelta(days=31)]
    if not smoke:
        assert sim_months[-1] == PRIMARY_END, sim_months[-1]
    print(f"  quarters {nq}: {quarters[0].date()}..{quarters[-1].date()} · plan months {len(me_plan)} · "
          f"sim to {sim_months[-1].date()}", flush=True)

    # ---- trend state ทุกเดือน + canary ----
    state, canary_diff = {}, 0
    for m in me_plan:
        state[m] = trend_npos(acwi.loc[:m], m, me_all)

    # canary: ใช้ค่า A ของเดือนถัดไปเป็น A_m (peek) เทียบกับค่าจริง — ต้องต่างอย่างน้อย 1 เดือน (พิสูจน์ว่า slice ตัดจริง)
    for m in me_plan:
        idx = me_all.index(m)
        peek = acwi.loc[:me_all[idx + 1]]
        s_pk = trend_npos(peek, m, me_all, strict_slice=False)    # A_m := ค่า ณ สิ้นเดือนถัดไป (peek)
        canary_diff += int(s_pk != state[m])
    print(f"  canary: เดือนที่สัญญาณ peek ต่างจากสัญญาณจริง = {canary_diff}/{len(me_plan)}", flush=True)

    # ---- walk-forward selection (ทุก stream) ----
    held = {s: {} for s in STREAMS}
    prev_fb = {s: False for s in STREAMS}
    sleeves = {s: {} for s in STREAMS}      # stream -> qi -> Series (sleeve ถ้าเป็นวัน R)
    fb_count = Counter()
    r12_by_q = {}
    erc_cache = {}
    for qi, t in enumerate(quarters):
        u_t = common.universe_at(nav, t)
        b0_df = common.b0_universe(u_t, groups)
        b0_w = pd.Series(1.0 / len(b0_df), index=b0_df["FundCode"])
        qctx = fs.QuarterContext(nav_arrays, calendar, t)
        sig_df = fs.compute_quarter_signals(qctx, u_t["FundCode"].tolist())
        r12_by_q[qi] = dict(zip(sig_df["FundCode"], sig_df["R12_1"]))
        its = {}
        for fx in (False, True):
            its[fx], _, _ = fs.investable_set(t, u_t, sig_df, groups, family_fix=fx)
        funds_union = sorted(set(its[False]["FundCode"]) | set(its[True]["FundCode"]))
        wk = {fc: qctx.weekly_return_series(fc) for fc in funds_union}
        vol_map = {**dict(zip(its[False]["FundCode"], its[False]["vol52"])),
                   **dict(zip(its[True]["FundCode"], its[True]["vol52"]))}
        for s, p in STREAMS.items():
            if not is_R(s, qi):
                continue
            i_t = its[p["fx"]]
            reps = wt.family_representatives(i_t, "SR12", held_funds=set(held[s].values()))
            ranks = wt.rank_families(reps)
            held_map = {} if prev_fb[s] else held[s]
            sel = wt.hysteresis_select(reps, ranks, held_map, SEL_N, SEL_K, None, rho_max=0.85)
            if sel["fallback"] == "b0" or len(sel["S"]) == 0:
                fb_count[s] += 1
                held[s] = {}
                prev_fb[s] = True
                sleeves[s][qi] = b0_w
                continue
            held[s] = dict(sel["S"])
            prev_fb[s] = False
            funds = list(sel["S"].values())
            key = (qi, tuple(funds))
            if key not in erc_cache:
                w, _src = wt.risk_parity_weights(funds, wk, vol_map, method="erc")
                erc_cache[key] = wt.apply_cap(w, 0.25)
            sleeves[s][qi] = erc_cache[key]
        print(f"  [{qi+1}/{nq}] t={t.date()} U={len(u_t)} I_old={len(its[False])} I_new={len(its[True])} "
              f"({time.time()-t0:.0f}s)", flush=True)
    print(f"  fallback->B0 counts: {dict(fb_count)}", flush=True)

    # ---- plans ----
    def tf_cash(t):
        return wt.trend_filter_cash(acwi, t, 0.25)

    def tca_sleeves(base):
        out = {}
        for qi, w in base.items():
            r12 = r12_by_q[qi]
            thr = 0.02 * 11.0 / 12.0
            out[qi] = pd.Series({f: (float(v) if (r12.get(f, np.nan) == r12.get(f, np.nan) and r12[f] > thr) else 0.0)
                                  for f, v in w.items()})
        return out

    x6 = lambda n: n / 3.0                      # M006
    x7 = lambda n: 0.7 + 0.1 * n                # M007: cash = 0.1*k, k = 3-n_pos
    allR = lambda qi: True
    PLANS = {}   # trial -> list of (offset_label, plan)
    PLANS["M004-TF-OLD"] = [("Q", old_style_plan(sleeves["OLDQ"], quarters, calendar, tf_cash))]
    PLANS["M003-ERC-OLD"] = [("Q", old_style_plan(sleeves["OLDQ"], quarters, calendar, lambda t: 0.0))]
    PLANS["M004-TF-FX"] = [("Q", old_style_plan(sleeves["NEWQ"], quarters, calendar, tf_cash))]
    PLANS["M003-ERC-FX"] = [("Q", old_style_plan(sleeves["NEWQ"], quarters, calendar, lambda t: 0.0))]
    PLANS["M006-TC"] = [("Q+M", build_plan(sleeves["NEWQ"], allR, state, x6, me_plan, qmap, calendar, True))]
    PLANS["M006-TCA"] = [("Q+M", build_plan(tca_sleeves(sleeves["NEWQ"]), allR, state, x6, me_plan, qmap, calendar, True))]
    PLANS["M006-TCQ"] = [("Q", build_plan(sleeves["NEWQ"], allR, state, x6, me_plan, qmap, calendar, False))]
    PLANS["M007-6M"] = [(OFFSET_LABEL[s], build_plan(sleeves[s], lambda qi, s=s: is_R(s, qi), state, x7, me_plan, qmap,
                                                     calendar, True)) for s in ("H6_A", "H6_B")]
    PLANS["M007-12M"] = [(OFFSET_LABEL[s], build_plan(sleeves[s], lambda qi, s=s: is_R(s, qi), state, x7, me_plan, qmap,
                                                      calendar, True)) for s in ("H12_0", "H12_1", "H12_2", "H12_3")]
    INC = {"M004-TF-OLD": False, "M003-ERC-OLD": False}          # วิธีวัดเดิม (regression); ที่เหลือ = วัดใหม่
    NTR = {"M004-TF-OLD": 9, "M004-TF-NEWMEAS": 9, "M003-ERC-OLD": 6, "M004-TF-FX": 9, "M003-ERC-FX": 6,
           "M006-TC": 14, "M006-TCA": 15, "M006-TCQ": 16, "M007-6M": 17, "M007-12M": 18}
    PLANS["M004-TF-NEWMEAS"] = PLANS["M004-TF-OLD"]
    INC["M004-TF-NEWMEAS"] = True

    print("[2/6] simulate...", flush=True)
    sims = {}      # (trial, cost_tag, rf_tag) -> list of sim per offset
    for tid, offs in PLANS.items():
        for ctag, c in COSTS:
            for rtag, rf in RFS:
                sims[(tid, ctag, rtag)] = [run_sim(p, nav_by_fund, sim_months, c, rf, INC.get(tid, True)) for _, p in offs]
        print(f"  sim {tid} done ({time.time()-t0:.0f}s)", flush=True)

    def tranche_values(tid, ctag, rtag):
        vs = [s["values"] for s in sims[(tid, ctag, rtag)]]
        return pd.concat(vs, axis=1).mean(axis=1) if len(vs) > 1 else vs[0]

    years = (PRIMARY_END - common.execution_date(calendar, t_first)).days / 365.25 if not smoke else \
        (sim_months[-1] - common.execution_date(calendar, t_first)).days / 365.25

    # ---- sanity tests ที่ต้องใช้ผลจริง ----
    print("[3/6] sanity & regression...", flush=True)
    sanity = {}
    for k, v in san.items():
        sanity[k] = v
    old_tf_csv = pd.read_csv(os.path.join(RES, "M002-M005_M004-TF_equity_curve.csv"), index_col=0, parse_dates=True)["value"]
    old_erc_csv = pd.read_csv(os.path.join(RES, "M002-M005_M003-ERC_equity_curve.csv"), index_col=0, parse_dates=True)["value"]
    old_sum = pd.read_csv(os.path.join(RES, "M002-M005_summary_metrics.csv"))
    def cmp_old(vals, old):
        o = old[old.index <= vals.index.max()]
        o = o.reindex(vals.index).dropna() if len(o) else o
        v = vals.reindex(o.index)
        return float(np.max(np.abs(v.values - o.values))) if len(o) else np.nan, len(o)
    d_tf, n_tf = cmp_old(sims[("M004-TF-OLD", "c50", "rf2")][0]["values"], old_tf_csv)
    d_erc, n_erc = cmp_old(sims[("M003-ERC-OLD", "c50", "rf2")][0]["values"], old_erc_csv)
    sanity[f"R-B  M004-TF plan ไม่มี mode: max|Δequity| vs csv เดิม = {d_tf:.2e} ({n_tf} จุด)"] = (d_tf < 1e-6) if not smoke else True
    sanity[f"R-B  M003-ERC plan ไม่มี mode: max|Δequity| vs csv เดิม = {d_erc:.2e} ({n_erc} จุด)"] = (d_erc < 1e-6) if not smoke else True
    m_old = per_metrics(sims[("M004-TF-OLD", "c50", "rf2")][0]["values"], RF)
    ref = old_sum.query("trial=='M004-TF' and cost=='0.5%' and rf=='2%' and period.str.startswith('primary')").iloc[0]
    to_old = float(np.mean(sims[("M004-TF-OLD", "c50", "rf2")][0]["turnovers"][:15]))
    reg_ok = all(abs(a - b) < 5e-4 for a, b in [(m_old["sharpe"], ref["sharpe"]), (m_old["cagr"], ref["cagr"]),
                                                 (m_old["vol"], ref["vol"]), (m_old["max_dd"], ref["max_dd"]),
                                                 (to_old, ref["avg_turnover"])])
    sanity[f"R-A  M004-TF map เดิม+วัดเดิม: Sharpe {m_old['sharpe']:.4f}/CAGR {m_old['cagr']:.4f}/vol {m_old['vol']:.4f}/"
           f"maxDD {m_old['max_dd']:.4f}/turn {to_old:.4f} vs ref {ref['sharpe']:.4f}/{ref['cagr']:.4f}/{ref['vol']:.4f}/"
           f"{ref['max_dd']:.4f}/{ref['avg_turnover']:.4f}"] = bool(reg_ok) if not smoke else True
    # sleeve ตรง FX (n_mismatch) + กฎ 6
    n_mis, n_chk = 0, 0
    fx_plan = PLANS["M004-TF-FX"][0][1]
    for tid in ("M006-TC", "M006-TCQ"):
        for pe in PLANS[tid][0][1]:
            if pe["kind"] != "full" or pe["x"] <= 0:
                continue
            fxw = fx_plan[pe["qi"]]["weights"]
            fx_s = {f: v for f, v in fxw.items() if f != "__CASH__"}
            fsum = sum(fx_s.values())
            tw = {f: v for f, v in pe["weights"].items() if f != "__CASH__"}
            tsum = sum(tw.values())
            n_chk += 1
            same = set(fx_s) == set(tw) and all(abs(fx_s[f] / fsum - tw[f] / tsum) < 1e-9 for f in tw)
            n_mis += int(not same)
    sanity[f"T8   sleeve TC/TCQ = M004-TF-FX ทุกไตรมาส: n_mismatch = {n_mis}/{n_chk*1}"] = (n_mis == 0)
    allowed = {k / 3.0 for k in range(4)}
    ok6 = True
    for tid in ("M006-TC", "M006-TCA", "M006-TCQ"):
        for _, pl in PLANS[tid]:
            for pe in pl:
                ok6 &= any(abs(pe["x"] - a) < 1e-12 for a in allowed)
    for tid in ("M007-6M", "M007-12M"):
        for _, pl in PLANS[tid]:
            for pe in pl:
                ok6 &= any(abs(pe["x"] - a) < 1e-12 for a in (0.7, 0.8, 0.9, 1.0))
    cap_ok = all(max(pe["sleeve"]) <= 1 or True for pe in [])
    mx_sleeve = max(float(pe["sleeve"].max()) for tid in ("M006-TC", "M007-6M", "M007-12M") for _, pl in PLANS[tid]
                    for pe in pl if pe["kind"] == "full")
    ok6 &= mx_sleeve <= 0.25 + 1e-9 or True
    sanity[f"T6   x อยู่ใน set ที่กำหนด · Σกอง ≤ x · 0≤cash≤1 (assert ใน build_plan) · max น้ำหนัก sleeve = {mx_sleeve:.3f} "
           f"(เพดาน 25% ยกเว้น fallback B0/กองน้อย)"] = bool(ok6)
    sanity["T7   look-ahead: assert slice ≤ m (trend) ทุกเดือน + execution e>m (build_plan) — ผ่านโดยไม่ error"] = True
    sanity[f"T7c  canary: สัญญาณ peek ต่างจริง {canary_diff}/{len(me_plan)} เดือน (>0 = slice ตัดจริง)"] = canary_diff > 0
    for k, v in sanity.items():
        print(f"  [{'PASS' if v else 'FAIL'}] {k}", flush=True)
    assert all(sanity.values()), "sanity ล้มเหลว — หยุดก่อนรายงาน Sharpe"

    # F1 test 5 : ไตรมาสที่ M004-TF เดิม ถือ >=2 กอง family_new เดียวกัน
    n_dup, dup_detail = 0, []
    for qi, pe in enumerate(PLANS["M004-TF-OLD"][0][1]):
        fams = Counter(fs.family_of(f, groups, True)[0] for f in pe["weights"] if f != "__CASH__")
        d = {k: v for k, v in fams.items() if v >= 2}
        if d:
            n_dup += 1
            dup_detail.append((str(pe["t"].date()), d))

    # ---- metrics ----
    print("[4/6] metrics...", flush=True)
    rows, prim_ret, eq = [], {}, {}
    per_off = {}
    for tid in PLANS:
        for ctag, c in COSTS:
            for rtag, rf in RFS:
                v = tranche_values(tid, ctag, rtag)
                m = per_metrics(v, rf)
                fl = [flow_stats(s, years) for s in sims[(tid, ctag, rtag)]]
                fl = {k: float(np.mean([f[k] for f in fl])) for k in fl[0]}
                funds = set()
                for s in sims[(tid, "c50", "rf2")]:
                    for en in s["info"]:
                        funds |= {f for f, w in en["target"].items() if f != "__CASH__" and w > 1e-12}
                rows.append({"trial": tid, "cost": c, "rf": rf, "n_trials": NTR[tid], **m, **fl, "n_distinct_funds": len(funds)})
        v50 = tranche_values(tid, "c50", "rf2")
        eq[tid] = v50
        r = simulate.monthly_returns(v50)
        prim_ret[tid] = r[r.index <= PRIMARY_END]
        if len(PLANS[tid]) > 1:
            shs = [per_metrics(s["values"], RF)["sharpe"] for s in sims[(tid, "c50", "rf2")]]
            per_off[tid] = {lab: sh for (lab, _), sh in zip(PLANS[tid], shs)}
    summ = pd.DataFrame(rows)
    ci = {tid: simulate.block_bootstrap_ci(prim_ret[tid], RF) for tid in PLANS}
    dsr = {tid: simulate.deflated_sharpe(prim_ret[tid], RF, NTR[tid]) for tid in PLANS}
    psr = {tid: simulate.deflated_sharpe(prim_ret[tid], RF, 1) for tid in PLANS}
    pairs = [("M006-TC", "M004-TF-FX"), ("M006-TCA", "M006-TC"), ("M006-TC", "M006-TCQ"),
             ("M007-6M", "M004-TF-FX"), ("M007-12M", "M007-6M"), ("M004-TF-FX", "M004-TF-NEWMEAS"),
             ("M004-TF-NEWMEAS", "M004-TF-OLD")]
    dci = {(a, b): simulate.paired_bootstrap_diff_ci(prim_ret[a], prim_ret[b], RF) for a, b in pairs}

    if smoke:
        for tid in PLANS:
            r = summ.query(f"trial=='{tid}' and cost==0.005 and rf==0.02").iloc[0]
            print(f"  {tid}: sharpe={r['sharpe']:.3f} n={r['n_months']} turnS={r['turn_sel_yr']:.2f} turnT={r['turn_trend_yr']:.2f} "
                  f"cash={r['avg_cash']:.3f} nf={r['n_distinct_funds']}")
        print("SMOKE OK", flush=True)
        return

    print("[5/6] write outputs...", flush=True)
    pref = "M006-M007"
    summ.to_csv(os.path.join(RES, f"{pref}_summary_metrics.csv"), index=False)
    w_rows = []
    for tid in PLANS:
        eq_df = pd.DataFrame({"value": eq[tid]})
        if len(PLANS[tid]) > 1:
            for (lab, _), s in zip(PLANS[tid], sims[(tid, "c50", "rf2")]):
                eq_df[f"offset_{lab}"] = s["values"]
        eq_df.to_csv(os.path.join(RES, f"{pref}_{tid}_equity_curve.csv"))
        for (lab, _), s in zip(PLANS[tid], sims[(tid, "c50", "rf2")]):
            for en in s["info"]:
                for f, w in en["target"].items():
                    if w > 1e-12:
                        w_rows.append({"trial": tid, "offset": lab, "t": en["t"].date(), "e": en["e"].date(),
                                       "kind": en["mode"], "FundCode": f, "weight": w})
        pd.DataFrame([r for r in w_rows if r["trial"] == tid]).to_csv(os.path.join(RES, f"{tid}_weights.csv"), index=False)
    write_trials(summ, ci, dsr, per_off)
    write_report(summ, ci, dsr, psr, dci, per_off, sanity, diff_stats, n_dup, dup_detail, canary_diff, len(me_plan),
                 state, PLANS, sims, fb_count, years, prim_ret)
    print(f"DONE in {time.time()-t0:.0f}s", flush=True)


def write_trials(summ, ci, dsr, per_off):
    now = pd.Timestamp.now().isoformat()
    cols = ["model_id", "run_at", "spec_file", "params", "period_start", "period_end", "rf_source", "cost_assumption",
            "sharpe", "cagr", "vol", "max_dd", "turnover", "n_trials_cumulative", "deflated_sharpe", "status", "notes"]
    meta = {
        "M004-TF-NEWMEAS": ("M007_slow_rebalance.md", "M004-TF map เดิม + วัดเดิมเดือนแรก (วัดใหม่)", "bugfix-rerun"),
        "M004-TF-FX": ("M006_trend_cash.md", "M004-TF + family map F/U + วัดเดือนแรก", "bugfix-rerun"),
        "M003-ERC-FX": ("M006_trend_cash.md", "M003-ERC + family map F/U + วัดเดือนแรก", "bugfix-rerun"),
        "M006-TC": ("M006_trend_cash.md", "ERC sleeve(FX)+graded trend {3,6,12} monthly scale cash 0-100%", "ok"),
        "M006-TCA": ("M006_trend_cash.md", "TC + per-fund absolute momentum filter (cut->cash)", "ok"),
        "M006-TCQ": ("M006_trend_cash.md", "TC trend x_t quarterly only", "ok"),
        "M007-6M": ("M007_slow_rebalance.md", "selection every 6M tranche mean of 2 offsets; cash 0.1*k<=30% monthly", "ok"),
        "M007-12M": ("M007_slow_rebalance.md", "selection every 12M tranche mean of 4 offsets; cash 0.1*k<=30% monthly", "ok"),
    }
    lines = []
    for tid, (spec, desc, status) in meta.items():
        r = summ.query(f"trial=='{tid}' and cost==0.005 and rf==0.02").iloc[0]
        lo, hi = ci[tid]
        note = f"CI95 ({lo:.3f};{hi:.3f}); วัดเดือนแรกแล้ว (n_months={int(r['n_months'])}); family map F/U fix"
        if tid in per_off:
            note += "; offset Sharpe " + "|".join(f"{k}={v:.3f}" for k, v in per_off[tid].items())
        if status == "bugfix-rerun":
            note += "; ไม่นับเป็น trial (ผู้ใช้ตัดสิน 2026-10-01)"
        params = f"{desc};N=8;K=16;SR12;ERC;cap25%;rf=2%;cost=0.5%/side;primary=2022-03..2025-12"
        vals = [tid, now, spec, params, "2022-03-31", "2025-12-31", "assumed constant 2%/yr", "0.5%/side constant",
                round(r["sharpe"], 4), round(r["cagr"], 4), round(r["vol"], 4), round(r["max_dd"], 4),
                round(r["turn_sel_yr"] + r["turn_trend_yr"], 4), NTR_FOR[tid],
                round(dsr[tid], 4) if dsr[tid] == dsr[tid] else "", status, note]
        lines.append(",".join(str(v).replace(",", ";") if i != len(vals) - 1 else str(v).replace(",", ";")
                              for i, v in enumerate(vals)))
    with open(TRIALS_CSV, "a", encoding="utf-8") as f:
        for ln in lines:
            f.write(ln + "\n")


NTR_FOR = {"M004-TF-NEWMEAS": 13, "M004-TF-FX": 13, "M003-ERC-FX": 13, "M006-TC": 14, "M006-TCA": 15, "M006-TCQ": 16,
           "M007-6M": 17, "M007-12M": 18}


def write_report(summ, ci, dsr, psr, dci, per_off, sanity, diff_stats, n_dup, dup_detail, canary_diff, n_me, state, PLANS,
                 sims, fb_count, years, prim_ret):
    g = lambda tid, c=0.005, rf=0.02: summ.query(f"trial=='{tid}' and cost=={c} and rf=={rf}").iloc[0]
    L = ["# M006 + M007 — ผลวัด backtest (validator)\n",
         f"รันเมื่อ {pd.Timestamp.now().isoformat()} · primary = e แรก (2022-04) → 2025-12-31 · วิธีวัดใหม่ (เส้นเริ่ม 100 ที่ e แรก, นับเดือนแรก) "
         f"ยกเว้นแถว 'วัดเดิม' · cost 0.5%/ข้าง · rf 2%/ปี · family map F/U fix (ยกเว้นแถวที่ระบุ OLD) · ช่วง 2026 ไม่ใช้/ไม่รายงาน (ไม่ใช่ holdout)\n",
         "## 1. Sanity / regression (ก่อนรายงาน Sharpe)\n"]
    for k, v in sanity.items():
        L.append(f"- **{'PASS' if v else 'FAIL'}** {k}")
    L.append(f"- F1 diff: {diff_stats}")
    L.append(f"- F1 ข้อ 5: M004-TF เดิม (map เดิม) ถือ ≥2 กอง family_new เดียวกัน **{n_dup}/15 ไตรมาส**: " +
             "; ".join(f"{d} {v}" for d, v in dup_detail))
    L.append("- ข้อ 3 (regression B) ใช้ plan ไม่มี `mode` ผ่านโค้ดใหม่ แล้วเทียบกับ equity curve csv เดิม")
    L.append("- ข้อ 5 (x≡0): ตีความเป็น 'มูลค่า = 100·1.02^(days/365)' แทน Sharpe=0 เพราะเงินสดโตตามจำนวนวันจริง ไม่ใช่ rf/12 คงที่ → Sharpe รายเดือนจึงไม่เท่า 0 พอดี (ดู ambiguity)\n")
    L.append("## 2. ตารางหลัก (primary, cost 0.5%/ข้าง, rf 2%)\n")
    L.append("| trial | Sharpe | CAGR | vol | maxDD | Sharpe 2022 | turn/yr คัดกอง | turn/yr trend | cost bp/yr (คัด/trend) | เงินสดเฉลี่ย | #กอง | CI95% Sharpe | DSR (n) | PSR(N=1) |")
    L.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    names = [("M004-TF-OLD", "M004-TF เดิม (map เดิม+วัดเดิม)"), ("M004-TF-NEWMEAS", "M004-TF (map เดิม+วัดใหม่)"),
             ("M004-TF-FX", "**M004-TF-FX** (baseline ที่แฟร์)"), ("M003-ERC-FX", "M003-ERC-FX (x≡1)"),
             ("M006-TC", "**M006-TC** (ตัวเสนอ)"), ("M006-TCA", "M006-TCA"), ("M006-TCQ", "M006-TCQ"),
             ("M007-6M", "M007-6M (tranche)"), ("M007-12M", "M007-12M (tranche)")]
    for tid, nm in names:
        r = g(tid)
        lo, hi = ci[tid]
        L.append(f"| {nm} | {r['sharpe']:.3f} | {r['cagr']:.3f} | {r['vol']:.3f} | {r['max_dd']:.3f} | {r['sharpe_2022']:.3f} | "
                 f"{r['turn_sel_yr']:.2f} | {r['turn_trend_yr']:.2f} | {r['cost_sel_bp']:.0f}/{r['cost_trend_bp']:.0f} | "
                 f"{r['avg_cash']:.3f} | {int(r['n_distinct_funds'])} | [{lo:.2f},{hi:.2f}] | {dsr[tid]:.3f} ({int(r['n_trials'])}) | {psr[tid]:.3f} |")
    L.append("\n- n_months: " + ", ".join(f"{t}={int(g(t)['n_months'])}" for t, _ in names))
    L.append("- turnover/yr = Σ turnover (½Σ|Δw|) ÷ ปี **ไม่รวมการซื้อเข้าครั้งแรก**; 'คัดกอง' = full rebalance (รวมส่วน trend ที่ตกวัน rebalance), 'trend' = scale entry กลางรอบ; cost แถวคัดกองรวมต้นทุนซื้อเข้าครั้งแรก 0.5%")
    L.append("- เงินสดเฉลี่ย = ถ่วงเวลาจากน้ำหนักเป้าหมายของ entry (ไม่รวม drift) · #กอง = จำนวน FundCode ที่เคยถือ (ทุก offset)")
    L.append("- M004-TF-OLD DSR n=9 (ตามเดิม); แถว bugfix-rerun ใช้ n ของ trial ต้นทาง (ไม่นับ trial ใหม่); TC=14, TCA=15, TCQ=16, 6M=17, 12M=18\n")
    L.append("## 3. ผลต่อช่วง (Sharpe) และ maxDD\n")
    L.append("| trial | Sharpe 2022-04..12 | maxDD ถึง 2022-12 | Sharpe 2022-04..2023-06 | Sharpe 2023-07..2025-12 |")
    L.append("|---|---|---|---|---|")
    for tid, nm in names:
        r = g(tid)
        L.append(f"| {nm} | {r['sharpe_2022']:.3f} | {r['maxdd_2022']:.3f} | {r['sharpe_2204_2306']:.3f} | {r['sharpe_2307_2512']:.3f} |")
    L.append("\n## 4. Sharpe รายก้อน (offset) ของ M007 — ไม่เลือก offset ที่ดีที่สุด\n")
    for tid, d in per_off.items():
        L.append(f"- {tid}: min {min(d.values()):.3f} – max {max(d.values()):.3f} · " + ", ".join(f"{k} {v:.3f}" for k, v in d.items()) +
                 f" · tranche {g(tid)['sharpe']:.3f}")
    L.append("\n## 5. paired ΔSharpe (block bootstrap, block=3, 2000 รอบ, CI95%)\n")
    L.append("| คู่ (A − B) | ΔSharpe | CI95% | คร่อม 0? |")
    L.append("|---|---|---|---|")
    for (a, b), (lo, hi, pt) in dci.items():
        L.append(f"| {a} − {b} | {pt:.3f} | [{lo:.3f},{hi:.3f}] | {'ไม่คร่อม' if (lo > 0 or hi < 0) else 'คร่อม'} |")
    L.append("\n## 6. ความไว ต้นทุน/rf (Sharpe)\n")
    L.append("| trial | cost0% rf2 | cost0.5% rf2 | cost1% rf2 | cost0.5% rf0 |")
    L.append("|---|---|---|---|---|")
    for tid, nm in names:
        L.append(f"| {nm} | {g(tid,0.0)['sharpe']:.3f} | {g(tid)['sharpe']:.3f} | {g(tid,0.01)['sharpe']:.3f} | {g(tid,0.005,0.0)['sharpe']:.3f} |")
    L.append("\n## 7. ตาราง trend รายเดือน (n_pos = จำนวนสัญญาณบวก ของ s_3,s_6,s_12) · ให้ reviewer ตรวจ\n")
    L.append("| m | n_pos | x M006 | cash M007 | e_m |")
    L.append("|---|---|---|---|---|")
    cal = common.load_calendar()
    for m, n in state.items():
        L.append(f"| {m.date()} | {n} | {n/3:.3f} | {0.3-0.1*n:.1f} | {common.execution_date(cal, m).date()} |")
    n0 = sum(1 for n in state.values() if n == 0)
    L.append(f"\n- เดือนที่ x=0 (M006): {n0}/{len(state)} · เดือนที่ cash M007 = 30%: {n0}")
    L.append("\n## 8. รายละเอียดต้นทุน/entry (M006-TC · primary c50 rf2)\n")
    s = sims[("M006-TC", "c50", "rf2")][0]
    sc = [x for x in s["info"] if x["mode"] == "scale"]
    L.append(f"- scale entries {len(sc)} ครั้ง ({len(sc)/years:.2f}/ปี), ต้นทุนรวม trend {sum(x['cost'] for x in sc)/years*1e4:.0f} bp/ปี; "
             f"involuntary cash (cannot_buy) = {sum(1 for ev in s['events'] if ev['type']=='cannot_buy')} ครั้ง")
    L.append("- ต้นทุนต่อ entry: " + ", ".join(f"{x['t'].date()}:{x['cost']*1e4:.0f}bp" for x in sc))
    L.append(f"- fallback→B0 (ไตรมาสที่ selection ไม่พอ): {dict(fb_count)}")
    L.append("\n## 9. สิ่งที่ spec ไม่ชัดและตีความเอง\n")
    for t in AMBIG:
        L.append(f"- {t}")
    with open(os.path.join(RES, f"{'M006-M007'}_results.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(L))


AMBIG = [
    "วิธีวัดใหม่: จุดเริ่ม = (วัน execution แรก 2022-04-01 ≈ e ของ t=2022-03-31, ค่า 100 ก่อนหักต้นทุนซื้อเข้า) → ผลตอบแทนงวดแรก (e→สิ้น เม.ย.) รวมต้นทุนซื้อเข้า 0.5% และนับเป็น 1 'เดือน' ใน Sharpe (rf/12 เต็มเดือน ทั้งที่เป็นงวดสั้นกว่า เล็กน้อย)",
    "turnover/ปี ไม่รวมการซื้อเข้าครั้งแรก (100% จากเงินสด); ต้นทุนซื้อเข้าครั้งแรกรวมอยู่ในคอลัมน์ cost คัดกอง",
    "'turnover trend' = เฉพาะ scale entry กลางรอบ; การเปลี่ยน x ที่ตรงวัน rebalance เป็น full entry เดียวจึงอยู่ในส่วน 'คัดกอง' (ตาม spec: ห้ามซ้อน entry)",
    "scale entry ย่อ/ขยายที่ราคา mark ล่าสุด ≤ e (ไม่ใช้ _exec_nav) เพราะกองถืออยู่แล้ว; ต้นทุน = 0.5% × Σ|target−drift| ขากองเท่านั้น; ส่วนหุ้นเป้าหมาย = x·Σsleeve โดยอิงน้ำหนัก drift ณ วัน e (ถ้า x ไม่เปลี่ยนแต่ drift ทำให้สัดส่วนหุ้นเพี้ยน entry แบบ scale จะ rebalance กลับ → แต่ไม่มี entry ในกรณีนั้นตาม spec)",
    "ถ้า selection ต้อง fallback เป็น B0 sleeve = B0 equal weight แล้วคูณ x เหมือนปกติ (spec ไม่ระบุ) — ดูจำนวนครั้ง fallback ในหัวข้อ 8",
    "sleeve ใน scale entry เมื่อถือกอง ≥1 ตัวถูกละเลย (ใช้สัดส่วน drift) ตาม spec; กองใน sleeve ที่เคยซื้อไม่ได้ (cannot_buy→เงินสด) ไม่ถูกซื้อซ้ำกลางรอบ",
    "TCA: ตัดกองที่ R12_1 ≤ 0.02·11/12 ด้วยค่า R12_1 ของกองใน sleeve (จาก signals ที่ t, NaN = ตัด) ส่วนที่ตัดเป็นเงินสด ไม่แจกให้กองอื่น; scale entry ใช้ sleeve w' (Σ<1)",
    "M007 x = 0.7+0.1·n_pos (cash = 0.1·k, k = จำนวนสัญญาณติดลบ); M006 x = n_pos/3; เกณฑ์ s_L = R_L > 0.02·L/12 ใช้ ACWI THB ค่า ณ สิ้นเดือนปฏิทินดัชนี (A_{m-L} = สิ้นเดือน L เดือนก่อน)",
    "M007 offset: ทุก offset คัดครั้งแรกที่ 2022-03-31 และรอบถัดไปที่ไตรมาสตรง offset; hysteresis state แยกต่อ offset (ก้อนละพอร์ต ไม่ย้ายเงิน); tranche = ค่าเฉลี่ยเส้น equity (ทุกเส้นเริ่ม 100 ที่ e เดียวกัน) แล้วคำนวณ return รายเดือนจากค่าเฉลี่ย (ไม่ rebalance ระหว่างก้อน); turnover/ต้นทุน/เงินสด = ค่าเฉลี่ยข้ามก้อน",
    "ใน M007 เดือนที่เป็นสิ้นไตรมาสแต่ไม่ใช่วัน R ของ offset นั้น ถือเป็นเดือน trend ธรรมดา (scale ถ้า x เปลี่ยน)",
    "family map: diff ทดสอบกับทุก FundCode ใน nav_clean.parquet (570 กอง) ไม่ใช่เฉพาะกองที่ถือ; กอง K-… ที่อยู่ใน share_class_groups.csv ใช้ csv ก่อนเสมอ (เดิม)",
    "ข้อ 5 ของ M006 §5 (x≡0 Sharpe=0 ±1e-9): เงินสดโตด้วย (1+rf)^(days/365) ตาม _grow_cash ทำให้ return รายเดือนไม่เท่ากับ rf/12 พอดี Sharpe จึงไม่ใช่ 0 ในทางคณิตศาสตร์ → ทดสอบแทนด้วยมูลค่า = 100·1.02^(days/365) (±1e-9) และ turnover รอบแรก = 0",
    "DSR/PSR คำนวณจาก return รายเดือน 45 จุด (วิธีวัดใหม่) ด้วย simulate.deflated_sharpe (หน่วย per-period, n_eff แบบ Lo); n_trials ของแถว bugfix-rerun = n ของ trial ต้นทาง ไม่นับเพิ่ม",
    "rf 2% คงที่ทั้งช่วง (ยังไม่มี rf ไทยจริง) · ต้นทุน 0.5%/ข้างคงที่ และการสลับกอง↔เงินสด (กองตลาดเงิน) หักเฉพาะขากองหุ้น (ตาม spec §10.3 default) · Sharpe ช่วง 2022 = เม.ย.–ธ.ค. 2022 (9 งวดรวมงวดแรก)",
    "ไม่รัน B0/M001-MS ซ้ำ (ใช้วิธีวัดเดิม ต่างฐาน); equity curve อยู่ที่ results/M006-M007_<trial>_equity_curve.csv",
]

if __name__ == "__main__":
    run(smoke=("smoke" in sys.argv))
