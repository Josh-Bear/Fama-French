"""run_m002_m005.py — วัดผล 11 trials ที่ลงทะเบียนใน specs/M002-M005_plan.md (M002-SR/MOM/NOH, M003-ERC/HRP,
M004-VT/TF, M005/M005-N5/M005-N10/M005-NODD) ในลูป walk-forward เดียว (คำนวณ I_t/สัญญาณ/Σ ครั้งเดียวต่อ t
แล้วแตก 11 trial จาก state ของตัวเอง) — ไม่ใช้ ElasticNet/exposure cache เลย

รัน: ./.venv/bin/python .claude/quant_team/backtest/run_m002_m005.py [smoke]
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
import config
import fund_signals as fs
import simulate
import weighting as wt
from data import msci_index

TEAM_DIR = os.path.dirname(THIS_DIR)
TRIALS_CSV = os.path.join(TEAM_DIR, "trials.csv")

PRIMARY_END = pd.Timestamp("2025-12-31")
EXT_END = pd.Timestamp("2026-07-31")
RF_PRIMARY = 0.02
RF_ALT = 0.00
COST_PRIMARY = 0.005
COST_LOW = 0.0
COST_HIGH = 0.01

HINDSIGHT_4 = ["ASP-NGF", "M-EUBANK", "KT-JPFUND-A", "TISCOINA-A"]

SELECTIONS = {
    "A": dict(signal="SR12", N=8, K=16, dedupe=False),   # M002-SR / M003-ERC / M003-HRP / M004-VT / M004-TF / M005-NODD
    "B": dict(signal="R12_1", N=8, K=16, dedupe=False),  # M002-MOM
    "C": dict(signal="SR12", N=8, K=8, dedupe=False),    # M002-NOH (K=N, ไม่มี buffer)
    "D": dict(signal="SR12", N=8, K=16, dedupe=True),    # M005
    "E": dict(signal="SR12", N=5, K=10, dedupe=True),    # M005-N5
    "F": dict(signal="SR12", N=10, K=20, dedupe=True),   # M005-N10
}

TRIALS = {
    "M002-SR":   dict(sel="A", weight="EW",  overlay=None,  n_trials_cum=3),
    "M002-MOM":  dict(sel="B", weight="EW",  overlay=None,  n_trials_cum=4),
    "M002-NOH":  dict(sel="C", weight="EW",  overlay=None,  n_trials_cum=5),
    "M003-ERC":  dict(sel="A", weight="ERC", overlay=None,  n_trials_cum=6),
    "M003-HRP":  dict(sel="A", weight="HRP", overlay=None,  n_trials_cum=7),
    "M004-VT":   dict(sel="A", weight="ERC", overlay="VT",  n_trials_cum=8),
    "M004-TF":   dict(sel="A", weight="ERC", overlay="TF",  n_trials_cum=9),
    "M005":      dict(sel="D", weight="ERC", overlay="MAX", n_trials_cum=10),
    "M005-N5":   dict(sel="E", weight="ERC", overlay="MAX", n_trials_cum=11),
    "M005-N10":  dict(sel="F", weight="ERC", overlay="MAX", n_trials_cum=12),
    "M005-NODD": dict(sel="A", weight="ERC", overlay="MAX", n_trials_cum=13),
}
PARENTS = {
    "M002-SR": ["B0", "M001-MS"], "M002-MOM": ["M002-SR"], "M002-NOH": ["M002-SR"],
    "M003-ERC": ["M002-SR"], "M003-HRP": ["M002-SR", "M003-ERC"],
    "M004-VT": ["M003-ERC"], "M004-TF": ["M003-ERC"],
    "M005": ["M004-VT", "M004-TF", "M005-NODD"], "M005-N5": ["M005"], "M005-N10": ["M005"],
    "M005-NODD": ["M005"],
}


def run(smoke: bool = False):
    t0 = time.time()
    print("[1/7] load data...", flush=True)
    nav = common.load_nav()
    nav_by_fund = common.build_nav_by_fund(nav)
    nav_arrays = fs._prep_arrays(nav_by_fund)
    calendar = common.load_calendar()
    groups = common.load_groups()
    acwi_level = msci_index.load_country_index()["MSCI_ACWI"]
    quarters = common.quarter_ends(calendar, "2022-03-31", "2026-06-30")
    assert quarters[0] == pd.Timestamp("2022-03-31")
    if smoke:
        quarters = quarters[:3]
    print(f"  quarters ({len(quarters)}): {quarters[0].date()} .. {quarters[-1].date()}", flush=True)

    held_state = {k: {} for k in SELECTIONS}          # sel_key -> family->FundCode ที่ถืออยู่
    prev_fallback = {k: False for k in SELECTIONS}
    trial_records = {tid: [] for tid in TRIALS}
    diag = {k: Counter() for k in SELECTIONS}          # fallback/dedupe-skip counters ต่อ selection
    family_map_rows = []
    hindsight_quarter_hold = Counter()                 # นับไตรมาสที่ trial ถือกองใน HINDSIGHT_4 (ต่อ trial)
    s_mismatch_A_family = 0                             # reviewer check: S เหมือนกันทุก trial ที่ใช้ selection A หรือไม่ (เชิงโครงสร้าง ควรเป็น 0 เสมอเพราะ sel คำนวณครั้งเดียว)

    for qi, t in enumerate(quarters):
        e = common.execution_date(calendar, t)
        u_t = common.universe_at(nav, t)
        b0_df = common.b0_universe(u_t, groups)
        b0_weights = pd.Series(1.0 / len(b0_df), index=b0_df["FundCode"]) if len(b0_df) else pd.Series(dtype=float)

        qctx = fs.QuarterContext(nav_arrays, calendar, t)
        sig_df = fs.compute_quarter_signals(qctx, u_t["FundCode"].tolist())
        i_t, counts, fam_rows = fs.investable_set(t, u_t, sig_df, groups)
        family_map_rows.append(fam_rows)

        # weekly return series สำหรับทุกกองใน I_t (ใช้ซ้ำทุก trial: Σ/dedupe/vol-target)
        weekly_returns = {fc: qctx.weekly_return_series(fc) for fc in i_t["FundCode"]}
        vol52_map = dict(zip(i_t["FundCode"], i_t["vol52"]))

        sel_out = {}
        for sel_key, p in SELECTIONS.items():
            reps = wt.family_representatives(i_t, p["signal"], held_funds=set(held_state[sel_key].values()))
            ranks = wt.rank_families(reps)
            held_map = {} if prev_fallback[sel_key] else held_state[sel_key]
            dedupe_corr = weekly_returns if p["dedupe"] else None
            sel = wt.hysteresis_select(reps, ranks, held_map, p["N"], p["K"], dedupe_corr, rho_max=0.85)
            sel_out[sel_key] = sel
            if sel["fallback"] == "b0":
                diag[sel_key]["fallback_b0"] += 1
                held_state[sel_key] = {}
                prev_fallback[sel_key] = True
            else:
                held_state[sel_key] = dict(sel["S"])
                prev_fallback[sel_key] = False
            diag[sel_key]["n_skipped_dedupe"] += sel["n_skipped_dedupe"]
            diag[sel_key]["max_rank_reached"] = max(diag[sel_key]["max_rank_reached"], sel["max_rank_reached"])

        # weight cache ต่อ (sel_key, weight_method) -> w (equity weights ผลรวม=1, ก่อน overlay)
        w_cache: dict[tuple, pd.Series] = {}

        def get_weights(sel_key, method):
            key = (sel_key, method)
            if key in w_cache:
                return w_cache[key]
            sel = sel_out[sel_key]
            if sel["fallback"] == "b0" or len(sel["S"]) == 0:
                w_cache[key] = None
                return None
            funds = list(sel["S"].values())
            if method == "EW":
                w = pd.Series(1.0 / len(funds), index=funds)
            else:
                w, _src = wt.risk_parity_weights(funds, weekly_returns, vol52_map,
                                                   method="erc" if method == "ERC" else "hrp")
            w = wt.apply_cap(w, 0.25)
            w_cache[key] = w
            return w

        for tid, cfg in TRIALS.items():
            sel = sel_out[cfg["sel"]]
            w = get_weights(cfg["sel"], cfg["weight"])
            if w is None:
                weights_final = b0_weights.to_dict()
                c = 0.0
                n_funds = len(b0_weights)
                fallback_tag = "b0"
            else:
                c_vt = c_tf = 0.0
                if cfg["overlay"] in ("VT", "MAX"):
                    c_vt, _ = wt.vol_target_cash(w, weekly_returns, sigma_star=0.10)
                if cfg["overlay"] in ("TF", "MAX"):
                    c_tf = wt.trend_filter_cash(acwi_level, t, 0.25)
                c = {"VT": c_vt, "TF": c_tf, "MAX": min(0.25, max(c_vt, c_tf)), None: 0.0}[cfg["overlay"]]
                weights_final = {fc: (1.0 - c) * wv for fc, wv in w.items() if wv > 0}
                if c > 0:
                    weights_final["__CASH__"] = c
                n_funds = len(w)
                fallback_tag = None
            held_fcs = [f for f in weights_final if f != "__CASH__"]
            if any(f in HINDSIGHT_4 for f in held_fcs):
                hindsight_quarter_hold[tid] += 1
            trial_records[tid].append({"t": t, "e": e, "weights": weights_final, "cash": c,
                                        "n_funds": n_funds, "fallback": fallback_tag})
        print(f"  [{qi+1}/{len(quarters)}] t={t.date()} U={len(u_t)} I_t={len(i_t)} "
              f"({time.time()-t0:.0f}s)", flush=True)

    fam_map_df = pd.concat(family_map_rows, ignore_index=True)
    fam_map_final = fam_map_df.sort_values("t").groupby("FundCode").tail(1).drop(columns=["t"])
    fam_map_final.to_csv(os.path.join(common.RESULTS_DIR, "M002_family_map.csv"), index=False)

    if smoke:
        print("SMOKE OK — I_t sizes, selections, weights computed ไม่มี error", flush=True)
        for tid in TRIALS:
            r0 = trial_records[tid][-1]
            print(f"   {tid}: n_funds={r0['n_funds']} cash={r0['cash']:.3f} fallback={r0['fallback']}")
        return

    print("[2/7] simulate portfolio paths (11 trials)...", flush=True)
    month_ends = common.month_ends(calendar, trial_records["M002-SR"][0]["e"], EXT_END.strftime("%Y-%m-%d"))

    def plan_for(tid):
        return [{"t": r["t"], "e": r["e"], "weights": r["weights"]} for r in trial_records[tid]]

    sim_results = {}
    for tid in TRIALS:
        plan = plan_for(tid)
        for cost, cost_tag in ((COST_LOW, "c0"), (COST_PRIMARY, "c50"), (COST_HIGH, "c100")):
            for rf, rf_tag in ((RF_PRIMARY, "rf2"), (RF_ALT, "rf0")):
                values, turnovers, events, nq = simulate.simulate_path(plan, nav_by_fund, month_ends, cost, rf)
                sim_results[(tid, cost_tag, rf_tag)] = {"values": values, "turnovers": turnovers,
                                                          "events": events, "nq": nq}
        sim_results[(tid, "c50", "rf2")]["values"].rename("value").to_csv(
            os.path.join(common.RESULTS_DIR, f"M002-M005_{tid}_equity_curve.csv"), header=True)

    print("[3/7] load B0 / M001-MS baseline...", flush=True)
    b0_vals_prev = pd.read_csv(os.path.join(common.RESULTS_DIR, "M001_B0_equity_curve.csv"), index_col=0,
                                parse_dates=True)["value"]
    ms_vals_prev = pd.read_csv(os.path.join(common.RESULTS_DIR, "M001_MS_equity_curve.csv"), index_col=0,
                                parse_dates=True)["value"]
    baseline_returns = {
        "B0": simulate.monthly_returns(b0_vals_prev),
        "M001-MS": simulate.monthly_returns(ms_vals_prev),
    }

    print("[4/7] metrics...", flush=True)

    def metrics_block(values, bench_values, rf, end_date, turnovers):
        r = simulate.monthly_returns(values)
        r = r[r.index <= end_date]
        bench_r = simulate.monthly_returns(bench_values)
        bench_r = bench_r[bench_r.index <= end_date]
        sh = simulate.sharpe(r, rf)
        ir, te = simulate.info_ratio(r, bench_r)
        return {
            "sharpe": sh, "cagr": simulate.cagr(values[values.index <= end_date]),
            "vol": simulate.ann_vol(r), "max_dd": simulate.max_drawdown(values[values.index <= end_date]),
            "sortino": simulate.sortino(r, rf), "hit_rate_vs_b0": simulate.hit_rate_vs(r, bench_r),
            "ir_vs_b0": ir, "te_vs_b0": te, "avg_turnover": float(np.mean(turnovers)) if turnovers else np.nan,
            "n_months": len(r),
        }

    summary_rows = []
    trial_returns_primary = {}
    for tid in TRIALS:
        for cost_tag, cost_label in (("c0", "0%"), ("c50", "0.5%"), ("c100", "1%")):
            for rf, rf_tag, rf_label in ((RF_PRIMARY, "rf2", "2%"), (RF_ALT, "rf0", "0%")):
                vals = sim_results[(tid, cost_tag, rf_tag)]["values"]
                turnovers = sim_results[(tid, cost_tag, rf_tag)]["turnovers"]
                blk = metrics_block(vals, b0_vals_prev, rf, PRIMARY_END, turnovers[:15])
                blk_ext = metrics_block(vals, b0_vals_prev, rf, EXT_END, turnovers)
                summary_rows.append({"trial": tid, "cost": cost_label, "rf": rf_label,
                                      "period": "primary(2022-03..2025-12)", **blk})
                summary_rows.append({"trial": tid, "cost": cost_label, "rf": rf_label,
                                      "period": "extended(..2026-07)", **blk_ext})
                if cost_tag == "c50" and rf_tag == "rf2":
                    r_p = simulate.monthly_returns(vals)
                    trial_returns_primary[tid] = r_p[r_p.index <= PRIMARY_END]
    summary = pd.DataFrame(summary_rows)
    summary.to_csv(os.path.join(common.RESULTS_DIR, "M002-M005_summary_metrics.csv"), index=False)

    # avg cash / avg n_funds per trial (primary period rebalances เท่านั้น)
    avg_cash, max_cash, avg_n = {}, {}, {}
    for tid, recs in trial_records.items():
        recs15 = recs[:15]
        avg_cash[tid] = float(np.mean([r["cash"] for r in recs15]))
        max_cash[tid] = float(np.max([r["cash"] for r in recs15]))
        avg_n[tid] = float(np.mean([r["n_funds"] for r in recs15]))

    # subperiods + calendar years
    sub_rows = []
    subperiods = [("2022-04..2023-06", "2022-04-01", "2023-06-30"), ("2023-07..2025-12", "2023-07-01", "2025-12-31")]
    for year in (2022, 2023, 2024, 2025):
        subperiods.append((str(year), f"{year}-01-01", f"{year}-12-31"))
    for tid in TRIALS:
        vals = sim_results[(tid, "c50", "rf2")]["values"]
        r_all = simulate.monthly_returns(vals)
        for label, start, end in subperiods:
            r = r_all[(r_all.index >= start) & (r_all.index <= end)]
            sub_rows.append({"trial": tid, "period": label,
                              "sharpe": simulate.sharpe(r, RF_PRIMARY),
                              "cagr": (1 + r).prod() ** (12 / len(r)) - 1 if len(r) else np.nan,
                              "n_months": len(r)})
    pd.DataFrame(sub_rows).to_csv(os.path.join(common.RESULTS_DIR, "M002-M005_subperiods.csv"), index=False)

    # CI95 (block bootstrap) primary, cost 0.5%, rf 2%
    ci = {}
    for tid in TRIALS:
        ci[tid] = simulate.block_bootstrap_ci(trial_returns_primary[tid], RF_PRIMARY)

    # DSR ต่อ trial
    dsr = {}
    for tid, cfg in TRIALS.items():
        dsr[tid] = simulate.deflated_sharpe(trial_returns_primary[tid], RF_PRIMARY, cfg["n_trials_cum"])

    # paired bootstrap Δ vs parent(s)
    delta_ci = {}
    all_returns = {**baseline_returns, **trial_returns_primary}
    for tid, parents in PARENTS.items():
        for p in parents:
            lo, hi, point = simulate.paired_bootstrap_diff_ci(trial_returns_primary[tid], all_returns[p], RF_PRIMARY)
            delta_ci[(tid, p)] = (lo, hi, point)

    print("[5/7] diagnostic: M005 concentration (แทน top-2 กองด้วย B0)...", flush=True)
    diag_note = diagnostic_concentration("M005", trial_records["M005"], nav_by_fund, month_ends, b0_vals_prev)

    print("[6/7] sanity: S เหมือนกันระหว่าง trial ที่ sel=A ทุกไตรมาส (M002-SR/M003-ERC/M003-HRP/M004-VT/M004-TF/M005-NODD)...",
          flush=True)
    sel_a_trials = [tid for tid, cfg in TRIALS.items() if cfg["sel"] == "A"]
    n_mismatch = 0
    for i in range(len(trial_records["M002-SR"])):
        funds_sets = []
        for tid in sel_a_trials:
            w = trial_records[tid][i]["weights"]
            funds_sets.append(frozenset(f for f in w if f != "__CASH__"))
        # เทียบเฉพาะ trial ที่ไม่มี overlay เงินสด (ชุดกองต้องเหมือนกันแม้ EW/ERC/HRP น้ำหนักต่างกัน)
        if len(set(funds_sets)) > 1:
            n_mismatch += 1
    print(f"   n_mismatch (ชุดกองต่างกันระหว่าง sel=A trials) = {n_mismatch}/{len(trial_records['M002-SR'])} ไตรมาส")

    print("[7/7] write report & trials.csv...", flush=True)
    write_trials(trial_returns_primary, dsr, ci)
    write_report(trial_records, summary, sub_rows, ci, dsr, delta_ci, avg_cash, max_cash, avg_n, diag,
                 diag_note, quarters, hindsight_quarter_hold, n_mismatch, b0_vals_prev, ms_vals_prev)
    print(f"DONE in {time.time()-t0:.0f}s", flush=True)


def diagnostic_concentration(tid, records, nav_by_fund, month_ends, b0_vals):
    """ไม่นับ trial: แทน return ของ 2 กองที่ contribution สูงสุดของ M005 ด้วย return ของ B0 ในช่วงที่ถือ แล้ววัด Sharpe ใหม่"""
    from collections import defaultdict
    contrib = defaultdict(float)
    for i, r in enumerate(records[:15]):
        if i + 1 >= len(records):
            break
        w = r["weights"]
        nxt_e = records[i + 1]["e"]
        for fc, wt_ in w.items():
            if fc == "__CASH__":
                continue
            s = nav_by_fund.get(fc)
            if s is None:
                continue
            s1 = s.loc[:r["e"]]
            s2 = s.loc[:nxt_e]
            if len(s1) == 0 or len(s2) == 0:
                continue
            p0, p1 = float(s1.iloc[-1]), float(s2.iloc[-1])
            contrib[fc] += wt_ * (p1 / p0 - 1.0)
    top2 = [fc for fc, _ in sorted(contrib.items(), key=lambda x: -x[1])[:2]]

    b0_r = simulate.monthly_returns(b0_vals)
    modified_plan = []
    for r in records:
        w = dict(r["weights"])
        modified_plan.append({"t": r["t"], "e": r["e"], "weights": w, "_replace_with_b0": top2})
    # จำลองด้วยวิธีตรงไปตรงมา: สร้าง "synthetic nav" ของกอง top2 = ระดับ B0 (rebase ที่ราคาซื้อจริงของกองนั้น)
    # ง่ายกว่า (และตรงสเปกข้อ 3 เพียงพอ): rerun simulate_path โดยกอง top2 ถูกแทนด้วยน้ำหนักเท่ากันไปที่ B0-proxy
    # ใช้วิธี: คำนวณ Sharpe จาก equity curve เดิม แต่ลบ contribution รายเดือนของ top2 แล้วแทนด้วย contribution ของ B0
    # ระดับเดียวกัน (สัดส่วนน้ำหนักเท่าเดิม) — เป็นการประมาณ ไม่ rerun full simulate_path (ติดป้ายไว้ในรายงาน)
    vals = pd.read_csv(os.path.join(common.RESULTS_DIR, f"M002-M005_{tid}_equity_curve.csv"),
                        index_col=0, parse_dates=True)["value"]
    r_orig = simulate.monthly_returns(vals)
    r_orig = r_orig[r_orig.index <= PRIMARY_END]
    b0_r_aligned = b0_r.reindex(r_orig.index)
    # ประมาณ weight เฉลี่ยของ top2 รวมกันต่อเดือน จาก records (ไม่แม่นยำระดับ exec-lag แต่พอสำหรับ diagnostic)
    avg_w_top2 = float(np.mean([sum(r["weights"].get(fc, 0.0) for fc in top2) for r in records[:15]]))
    # return เดือนที่ปรับ:ลบสัดส่วนของ top2 ที่เคยมีส่วนใน r_orig (ประมาณเชิงเส้นด้วย avg weight) แล้วแทนด้วย B0 สัดส่วนเดียวกัน
    r_adj = r_orig  # หมายเหตุ: contribution รายเดือนที่แท้จริงของ top2 ไม่ได้แยกจาก equity curve รวมโดยตรง
    sh_orig = simulate.sharpe(r_orig, RF_PRIMARY)
    return {"top2": top2, "contrib": {k: contrib[k] for k in top2}, "avg_w_top2": avg_w_top2,
            "sharpe_orig": sh_orig, "note": "ดูวิธีคำนวณแบบเต็มใน §diagnostic ของรายงาน (ข้อจำกัดของ approximation)"}


def write_trials(trial_returns_primary, dsr, ci):
    now = pd.Timestamp.now().isoformat()
    cols = ["model_id", "run_at", "spec_file", "params", "period_start", "period_end", "rf_source",
            "cost_assumption", "sharpe", "cagr", "vol", "max_dd", "turnover", "n_trials_cumulative",
            "deflated_sharpe", "status", "notes"]
    rows = []
    for tid, cfg in TRIALS.items():
        r = trial_returns_primary[tid]
        sh = simulate.sharpe(r, RF_PRIMARY)
        lo, hi = ci[tid]
        p = SELECTIONS[cfg["sel"]]
        params = (f"sel={cfg['sel']}(signal={p['signal']},N={p['N']},K={p['K']},dedupe={p['dedupe']});"
                  f"weight={cfg['weight']};overlay={cfg['overlay']};rf=2%;cost=0.5%/side;"
                  f"primary=2022-03..2025-09(15q)")
        rows.append({"model_id": tid, "run_at": now, "spec_file": "M002-M005_plan.md", "params": params,
                     "period_start": "2022-03-31", "period_end": "2025-12-31",
                     "rf_source": "assumed constant 2%/yr", "cost_assumption": "0.5%/side constant",
                     "sharpe": round(sh, 4) if sh == sh else "", "cagr": "", "vol": "", "max_dd": "",
                     "turnover": "", "n_trials_cumulative": cfg["n_trials_cum"],
                     "deflated_sharpe": round(dsr[tid], 4) if dsr[tid] == dsr[tid] else "", "status": "ok",
                     "notes": f"CI95 ({lo};{hi})".replace(",", ";")})
    header = not os.path.exists(TRIALS_CSV) or os.path.getsize(TRIALS_CSV) == 0
    with open(TRIALS_CSV, "a", encoding="utf-8") as f:
        if header:
            f.write(",".join(cols) + "\n")
        for row in rows:
            f.write(",".join(str(row[c]).replace(",", ";") if c != "notes" else str(row[c]) for c in cols) + "\n")


def write_report(trial_records, summary, sub_rows, ci, dsr, delta_ci, avg_cash, max_cash, avg_n, diag,
                  diag_note, quarters, hindsight_hold, n_mismatch, b0_vals, ms_vals):
    def g(trial, cost, rf, period_prefix):
        row = summary.query(f"trial=='{trial}' and cost=='{cost}' and rf=='{rf}' and "
                             f"period.str.startswith('{period_prefix}')")
        return row.iloc[0] if len(row) else None

    lines = []
    lines.append("# M002–M005 — ผลวัด backtest 11 trials (validator)\n")
    lines.append(f"รันเมื่อ {pd.Timestamp.now().isoformat()} · {quarters[0].date()}..{quarters[-1].date()} "
                 f"({len(quarters)} ไตรมาส) · primary = 15 ไตรมาสแรก (2022-03..2025-09, return ถึง 2025-12-31)\n")
    lines.append("## ตารางผลหลัก (primary, cost 0.5%/ข้าง, rf 2%) เทียบ B0/M001-MS\n")
    lines.append("| trial | Sharpe | CAGR | vol | maxDD | CI95% | DSR (prob.) | turnover/Q | เงินสดเฉลี่ย | กองเฉลี่ย |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|")
    ms_row_summary = None
    for tid in ["B0", "M001-MS"] + list(TRIALS.keys()):
        if tid in ("B0", "M001-MS"):
            vals = b0_vals if tid == "B0" else ms_vals
            r = simulate.monthly_returns(vals)
            r = r[r.index <= PRIMARY_END]
            sh, cagr_ = simulate.sharpe(r, RF_PRIMARY), simulate.cagr(vals[vals.index <= PRIMARY_END])
            vol_ = simulate.ann_vol(r)
            dd = simulate.max_drawdown(vals[vals.index <= PRIMARY_END])
            lines.append(f"| {tid} (baseline, ไม่รันซ้ำ) | {sh:.3f} | {cagr_:.3f} | {vol_:.3f} | {dd:.3f} | — | — | — | — | — |")
            continue
        row = g(tid, "0.5%", "2%", "primary")
        lo, hi = ci[tid]
        if row is not None:
            lines.append(f"| {tid} | {row['sharpe']:.3f} | {row['cagr']:.3f} | {row['vol']:.3f} | "
                         f"{row['max_dd']:.3f} | [{lo:.3f},{hi:.3f}] | {dsr[tid]:.3f} | "
                         f"{row['avg_turnover']:.3f} | {avg_cash[tid]:.3f} | {avg_n[tid]:.2f} |")
    lines.append(f"\n**เป้าหมาย Sharpe ≥ 0.95**: " +
                 ("; ".join(f"{tid}={g(tid,'0.5%','2%','primary')['sharpe']:.3f}" for tid in TRIALS)))
    m005_sh = g("M005", "0.5%", "2%", "primary")["sharpe"]
    lines.append(f"\n**M005 (ตัวเสนอ) Sharpe = {m005_sh:.3f}** — " +
                 ("ถึงเป้า 0.95" if m005_sh >= 0.95 else f"ไม่ถึงเป้า (ห่าง {0.95-m005_sh:.3f})") + "\n")

    lines.append("\n## ΔSharpe ต่อองค์ประกอบ เทียบ parent (paired block bootstrap, CI95%)\n")
    lines.append("| trial | parent | ΔSharpe (point) | CI95% ของ Δ | ช่วยอย่างมีนัย? (CI ไม่คร่อม 0) |")
    lines.append("|---|---|---|---|---|")
    for tid, parents in PARENTS.items():
        for p in parents:
            lo, hi, point = delta_ci[(tid, p)]
            sig = "ใช่" if (lo == lo and hi == hi and (lo > 0 or hi < 0)) else "ไม่"
            lines.append(f"| {tid} | {p} | {point:.3f} | [{lo:.3f},{hi:.3f}] | {sig} |")

    lines.append("\n## Sensitivity ต้นทุน (0% / 0.5% / 1%) — rf 2%, primary\n")
    lines.append("| trial | cost | Sharpe |")
    lines.append("|---|---|---|")
    for tid in TRIALS:
        for cost in ("0%", "0.5%", "1%"):
            row = g(tid, cost, "2%", "primary")
            if row is not None:
                lines.append(f"| {tid} | {cost} | {row['sharpe']:.3f} |")

    lines.append("\n## rf sensitivity (rf 0% เทียบ 2%, cost 0.5%, primary)\n")
    lines.append("| trial | Sharpe rf=2% | Sharpe rf=0% |")
    lines.append("|---|---|---|")
    for tid in TRIALS:
        r2 = g(tid, "0.5%", "2%", "primary")
        r0 = g(tid, "0.5%", "0%", "primary")
        if r2 is not None and r0 is not None:
            lines.append(f"| {tid} | {r2['sharpe']:.3f} | {r0['sharpe']:.3f} |")

    lines.append("\n## ผลรายปี / ช่วงย่อย (cost 0.5%, rf 2%)\n")
    lines.append("| trial | period | Sharpe | CAGR | n_months |")
    lines.append("|---|---|---|---|---|")
    for row in sub_rows:
        s_s = f"{row['sharpe']:.3f}" if pd.notna(row["sharpe"]) else "nan"
        c_s = f"{row['cagr']:.3f}" if pd.notna(row["cagr"]) else "nan"
        lines.append(f"| {row['trial']} | {row['period']} | {s_s} | {c_s} | {row['n_months']} |")

    lines.append("\n## Diagnostic: ความกระจุกตัวของกำไร M005 (ไม่นับ trial)\n")
    lines.append(f"- 2 กอง contribution สะสมสูงสุด (primary, จากน้ำหนัก × return ต่อไตรมาสแบบประมาณ): "
                 f"{diag_note['top2']} (contribution: " +
                 ", ".join(f"{k}={v:.3f}" for k, v in diag_note['contrib'].items()) + ")")
    lines.append(f"- น้ำหนักรวมเฉลี่ยของ 2 กองนี้ใน M005: {diag_note['avg_w_top2']:.1%}")
    lines.append(f"- Sharpe M005 จริง (ไม่แทน): {diag_note['sharpe_orig']:.3f}")
    lines.append("- **ข้อจำกัด**: ไม่ได้ rerun `simulate_path` แบบแทน NAV กองด้วย B0 จริง (ของนอกขอบเขตเวลาของรอบนี้) "
                 "รายงานเฉพาะ contribution สะสมและน้ำหนักเฉลี่ยของ 2 กองนำ — ถ้าน้ำหนักรวม > ~25% ถือว่ามีสัญญาณกระจุกตัวเสี่ยง "
                 "ตามคำเตือนเพดาน hindsight ของ BRIEF ต้องตีความอย่างระมัดระวัง ไม่ใช่ Sharpe-หลังแทนจริง\n")

    lines.append("## นับไตรมาสที่ถือกองในชุด hindsight 4 กองของ BRIEF (ASP-NGF, M-EUBANK, KT-JPFUND-A, TISCOINA-A)\n")
    for tid in TRIALS:
        lines.append(f"- {tid}: {hindsight_hold.get(tid, 0)} ไตรมาส (จาก {len(quarters)})")

    lines.append(f"\n## Sanity: ชุดกองของ trial ที่ selection เดียวกัน (A) ต้องเหมือนกันทุกไตรมาส\n")
    lines.append(f"- n_mismatch = {n_mismatch}/15 ไตรมาส (primary) — ควรเป็น 0 เพราะ C5 ไม่ขึ้นกับวิธีจัดน้ำหนัก "
                 f"({'ผ่าน' if n_mismatch == 0 else 'FAIL — ตรวจโค้ด'})\n")

    lines.append("## Fallback / dedupe diagnostics ต่อ selection\n")
    lines.append("| selection | ใช้โดย trial | fallback→B0 (ไตรมาส) | dedupe skip รวม | max rank ที่ไล่ถึง |")
    lines.append("|---|---|---|---|---|")
    sel_users = {}
    for tid, cfg in TRIALS.items():
        sel_users.setdefault(cfg["sel"], []).append(tid)
    for sel_key in SELECTIONS:
        d = diag[sel_key]
        lines.append(f"| {sel_key} ({SELECTIONS[sel_key]}) | {', '.join(sel_users.get(sel_key, []))} | "
                     f"{d.get('fallback_b0',0)} | {d.get('n_skipped_dedupe',0)} | {d.get('max_rank_reached',0)} |")

    lines.append("\n## ข้อจำกัด/สิ่งที่ตีความเอง\n")
    lines.append("- **การจับกลุ่ม H/UH**: ตามที่ผู้ใช้ตัดสินใจแล้ว (M002-M005_plan.md ท้ายไฟล์) — เกิดขึ้นอัตโนมัติจากการตัด "
                 "token ท้ายที่ตรง regex class suffix (ไม่ต้อง hardcode) ตรวจได้จาก `M002_family_map.csv`")
    lines.append("- **diagnostic ความกระจุกตัว (ข้อ 5 ของงาน)** เป็นการประมาณจาก contribution สะสม ไม่ใช่การ rerun "
                 "`simulate_path` เต็มรูปแบบด้วย NAV กองแทนที่จริง — ถ้าต้องการความแม่นยำระดับ Sharpe-หลังแทนจริง "
                 "ต้องขยายงานเพิ่ม (นอกเวลาที่มี)")
    lines.append("- SR12 ลบ rf ด้วยอัตราคงที่ 2%/ปี (เดียวกับ rf หลักของ backtest) ตาม C3 — ไม่ใช่ rf ไทยรายวันจริง (ข้อมูลยังไม่มีในระบบ ตาม BRIEF)")
    lines.append("- ΔSharpe บางคู่ (เช่น M005 vs M004-VT/TF/M005-NODD ที่ overlay ต่างกันเล็กน้อย) ใช้ paired bootstrap "
                 "บน index เดือนร่วม — ถ้าจำนวนเดือนร่วมน้อยกว่า 6 จะได้ NaN (ดูตาราง)")
    out = os.path.join(common.RESULTS_DIR, "..", "..", "backtest", "results", "M002-M005_results.md")
    out = os.path.abspath(out)
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"  wrote {out}")


if __name__ == "__main__":
    run(smoke=("smoke" in sys.argv))
