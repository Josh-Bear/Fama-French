"""run_m001.py — วัดผล M001 (baseline หน้า 8 point-in-time รายไตรมาส) ตาม .claude/quant_team/specs/M001_baseline_page8.md
รัน: ./.venv/bin/python .claude/quant_team/backtest/run_m001.py [smoke]
  smoke = จำกัด 2 ไตรมาสแรกเพื่อทดสอบ pipeline ก่อนรันเต็ม (~15 นาที)
"""
from __future__ import annotations

import os
import sys
import time

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if THIS_DIR not in sys.path:
    sys.path.insert(0, THIS_DIR)

import numpy as np
import pandas as pd

import common
import config
import exposure
import selection
import simulate

TEAM_DIR = os.path.abspath(os.path.join(THIS_DIR, "..", ".."))
TRIALS_CSV = os.path.join(TEAM_DIR, "quant_team", "trials.csv") if False else \
    os.path.join(os.path.dirname(THIS_DIR), "trials.csv")

PRIMARY_END = pd.Timestamp("2025-12-31")
EXT_END = pd.Timestamp("2026-07-31")
RF_PRIMARY = 0.02
RF_ALT = 0.00
COST_PRIMARY = 0.005
COST_LOW = 0.0
COST_HIGH = 0.01
PAGE8_TODAY = ["KT-EMEQ-A", "KT-JPFUND-A", "M-EUBANK", "MATECH-A", "TLUSNDQ-H-A"]


def run(smoke: bool = False):
    t0 = time.time()
    print("[1/6] load data...", flush=True)
    nav = common.load_nav()
    nav_by_fund = common.build_nav_by_fund(nav)
    calendar = common.load_calendar()
    levels_country, levels_sector, levels21 = common.load_levels()
    groups = common.load_groups()
    quarters = common.quarter_ends(calendar, "2022-03-31", "2026-06-30")
    assert quarters[0] == pd.Timestamp("2022-03-31")
    print(f"  quarters ({len(quarters)}): {quarters[0].date()} .. {quarters[-1].date()}", flush=True)
    if smoke:
        quarters = quarters[:2]

    records = []
    print("[2/6] walk-forward loop...", flush=True)
    for qi, t in enumerate(quarters):
        e = common.execution_date(calendar, t)
        u_t = common.universe_at(nav, t)
        b0_df = common.b0_universe(u_t, groups)
        b0_weights = pd.Series(1.0 / len(b0_df), index=b0_df["FundCode"]) if len(b0_df) else pd.Series(dtype=float)

        country_df = exposure.fit_scope(u_t["FundCode"].tolist(), nav_by_fund, levels_country,
                                         config.SCORE_COUNTRY_CLEAN, t, "country")
        sector_df = exposure.fit_scope(u_t["FundCode"].tolist(), nav_by_fund, levels_sector,
                                        config.MSCI_SECTOR_COLS, t, "sector")
        matches_t = exposure.build_matches(country_df, sector_df)

        _, _, matrix = selection.zone_scores(levels_country, levels_sector, t)
        picked_df = selection.pick_funds(matches_t, matrix, groups)
        risk_res = selection.risk_model_at(picked_df["FundCode"].tolist(), nav_by_fund, levels21, t)
        decision = selection.decide_weights(risk_res, b0_weights)

        rec = {
            "t": t, "e": e, "n_universe": len(u_t), "n_b0": len(b0_df), "n_picked": len(picked_df),
            "n_ok": decision["n_ok"], "fallback": decision["fallback"],
            "ms_weights": decision["ms"].to_dict(), "ew_weights": decision["ew"].to_dict(),
            "b0_weights": b0_weights.to_dict(),
            "picked_meta": picked_df[["FundCode", "used_country", "used_sector"]].to_dict("records")
            if len(picked_df) else [],
        }
        records.append(rec)
        print(f"  [{qi+1}/{len(quarters)}] t={t.date()} U={len(u_t)} B0={len(b0_df)} picked={len(picked_df)} "
              f"n_ok={decision['n_ok']} fallback={decision['fallback']} ({time.time()-t0:.0f}s)", flush=True)

    if smoke:
        print("SMOKE OK", flush=True)
        return

    print("[3/6] simulate portfolio paths...", flush=True)
    month_ends = common.month_ends(calendar, records[0]["e"], EXT_END.strftime("%Y-%m-%d"))

    def plan_for(key):
        return [{"t": r["t"], "e": r["e"], "weights": r[key]} for r in records]

    plans = {"MS": plan_for("ms_weights"), "EW": plan_for("ew_weights"), "B0": plan_for("b0_weights")}
    sim_results = {}
    for variant, plan in plans.items():
        for cost, cost_tag in ((COST_LOW, "c0"), (COST_PRIMARY, "c50"), (COST_HIGH, "c100")):
            for rf, rf_tag in ((RF_PRIMARY, "rf2"), (RF_ALT, "rf0")):
                values, turnovers, events, nq = simulate.simulate_path(plan, nav_by_fund, month_ends, cost, rf)
                sim_results[(variant, cost_tag, rf_tag)] = {"values": values, "turnovers": turnovers,
                                                              "events": events, "nq": nq}
        eq_path = os.path.join(common.RESULTS_DIR, f"M001_{variant}_equity_curve.csv")
        sim_results[(variant, "c50", "rf2")]["values"].rename("value").to_csv(eq_path, header=True)

    print("[4/6] metrics...", flush=True)

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
    for variant in ("MS", "EW", "B0"):
        for cost_tag, cost_label in (("c0", "0%"), ("c50", "0.5%"), ("c100", "1%")):
            for rf, rf_tag, rf_label in ((RF_PRIMARY, "rf2", "2%"), (RF_ALT, "rf0", "0%")):
                vals = sim_results[(variant, cost_tag, rf_tag)]["values"]
                b0_vals = sim_results[("B0", cost_tag, rf_tag)]["values"]
                turnovers = sim_results[(variant, cost_tag, rf_tag)]["turnovers"]
                blk = metrics_block(vals, b0_vals, rf, PRIMARY_END, turnovers[:15])
                blk_ext = metrics_block(vals, b0_vals, rf, EXT_END, turnovers)
                summary_rows.append({"variant": variant, "cost": cost_label, "rf": rf_label,
                                      "period": "primary(2022-03..2025-12)", **blk})
                summary_rows.append({"variant": variant, "cost": cost_label, "rf": rf_label,
                                      "period": "extended(..2026-07)", **blk_ext})
    summary = pd.DataFrame(summary_rows)
    summary.to_csv(os.path.join(common.RESULTS_DIR, "M001_summary_metrics.csv"), index=False)

    # subperiods & calendar years (cost 0.5%, rf 2% and 0% — value path แยกจริงเพราะเงินสดโตด้วย rf คนละอัตรา)
    sub_rows = []
    subperiods = [("2022-04..2023-06", "2022-04-01", "2023-06-30"), ("2023-07..2025-12", "2023-07-01", "2025-12-31")]
    for year in (2022, 2023, 2024, 2025):
        subperiods.append((str(year), f"{year}-01-01", f"{year}-12-31"))
    for variant in ("MS", "EW", "B0"):
        for rf, rf_tag, rf_label in ((RF_PRIMARY, "rf2", "2%"), (RF_ALT, "rf0", "0%")):
            vals = sim_results[(variant, "c50", rf_tag)]["values"]
            r_all = simulate.monthly_returns(vals)
            for label, start, end in subperiods:
                r = r_all[(r_all.index >= start) & (r_all.index <= end)]
                sub_rows.append({"variant": variant, "period": label, "rf": rf_label,
                                  "sharpe": simulate.sharpe(r, rf), "cagr": (1 + r).prod() ** (12 / len(r)) - 1
                                  if len(r) else np.nan, "n_months": len(r)})
    pd.DataFrame(sub_rows).to_csv(os.path.join(common.RESULTS_DIR, "M001_subperiods.csv"), index=False)

    # CI (bootstrap) primary, cost 0.5%, rf 2%
    ci = {}
    for variant in ("MS", "EW", "B0"):
        r = simulate.monthly_returns(sim_results[(variant, "c50", "rf2")]["values"])
        r = r[r.index <= PRIMARY_END]
        ci[variant] = simulate.block_bootstrap_ci(r, RF_PRIMARY)

    # เหตุการณ์ผิดปกติ (cannot_buy / exec_late / mark_stale) จาก run หลัก (cost 0.5%, rf 2%) — เหมือนกันทุก cost/rf
    # เพราะ target weights เดียวกัน ต่างแค่การเติบโตของเงินสด/ต้นทุน
    from collections import Counter
    event_summary = {}
    for variant in ("MS", "EW", "B0"):
        ev = sim_results[(variant, "c50", "rf2")]["events"]
        ev_primary = [x for x in ev if x["date"] <= PRIMARY_END]
        ev_ext = [x for x in ev if x["date"] > PRIMARY_END]
        event_summary[variant] = {"primary": Counter(x["type"] for x in ev_primary),
                                   "extended": Counter(x["type"] for x in ev_ext),
                                   "primary_list": ev_primary, "extended_list": ev_ext}

    # fallback counts & composition
    n_fallback_small = sum(1 for r in records if r["fallback"] == "small_n")
    n_fallback_b0 = sum(1 for r in records if r["fallback"] == "b0")
    country_counts, sector_counts = {}, {}
    for r in records:
        for m in r["picked_meta"]:
            country_counts[m["used_country"]] = country_counts.get(m["used_country"], 0) + 1
            sector_counts[m["used_sector"]] = sector_counts.get(m["used_sector"], 0) + 1

    # quarterly weights csv
    wrows = []
    for r in records:
        for variant_key, wname in (("ms_weights", "MS"), ("ew_weights", "EW"), ("b0_weights", "B0")):
            for fc, w in r[variant_key].items():
                wrows.append({"t": r["t"], "variant": wname, "FundCode": fc, "weight": w,
                              "fallback": r["fallback"]})
    pd.DataFrame(wrows).to_csv(os.path.join(common.RESULTS_DIR, "M001_quarterly_weights.csv"), index=False)

    # picked at 2026-06-30 vs page 8 today
    last_rec = records[-1]
    last_picked = [m["FundCode"] for m in last_rec["picked_meta"]]
    overlap = sorted(set(last_picked) & set(PAGE8_TODAY))

    print("[5/6] sanity checks...", flush=True)
    sanity_notes = []
    ms_sh = summary.query("variant=='MS' and cost=='0.5%' and rf=='2%' and period.str.startswith('primary')")[
        "sharpe"].iloc[0]
    ew_sh = summary.query("variant=='EW' and cost=='0.5%' and rf=='2%' and period.str.startswith('primary')")[
        "sharpe"].iloc[0]
    try:
        assert abs(ms_sh - ew_sh) < 1.0, f"MS vs EW Sharpe ต่างกันเกินคาด: MS={ms_sh:.2f} EW={ew_sh:.2f}"
        sanity_notes.append(f"OK: MS Sharpe ({ms_sh:.2f}) ใกล้เคียง EW Sharpe ({ew_sh:.2f}) ตามคาด (Π ไม่มีสัญญาณจากคะแนน)")
    except AssertionError as ex:
        sanity_notes.append(f"WARN: {ex}")

    rng = np.random.default_rng(42)
    rand_plan = []
    for r in records:
        w = dict(r["ms_weights"])
        if w:
            keys = list(w.keys())
            vals = list(w.values())
            rng.shuffle(vals)
            w = dict(zip(keys, vals))
        rand_plan.append({"t": r["t"], "e": r["e"], "weights": w})
    rand_vals, _, _, _ = simulate.simulate_path(rand_plan, nav_by_fund, month_ends, COST_PRIMARY, RF_PRIMARY)
    rand_r = simulate.monthly_returns(rand_vals)
    rand_r = rand_r[rand_r.index <= PRIMARY_END]
    rand_sh = simulate.sharpe(rand_r, RF_PRIMARY)
    b0_sh_primary = summary.query("variant=='B0' and cost=='0.5%' and rf=='2%' and period.str.startswith('primary')")[
        "sharpe"].iloc[0]
    try:
        assert rand_sh < ms_sh + 1.0, "น้ำหนักสุ่มได้ Sharpe สูงกว่า MS มากผิดปกติ — สงสัย look-ahead/bug"
        sanity_notes.append(f"OK: สุ่มน้ำหนัก (fund ชุดเดียวกับ MS) Sharpe={rand_sh:.2f} ไม่สูงผิดปกติเทียบ MS={ms_sh:.2f}, B0={b0_sh_primary:.2f}")
    except AssertionError as ex:
        sanity_notes.append(f"WARN: {ex}")
    sanity_notes.append("OK: assert ในโค้ด (common.py/exposure.py/selection.py) ยืนยันทุก slice ของ NAV/ดัชนีที่ใช้คำนวณ ≤ t "
                         "ตลอด loop (universe_at, fit_scope, zone_snapshot, risk_model_at) — รันจบไม่มี AssertionError")

    print("[6/6] write report & trials.csv...", flush=True)
    ms_r_primary = simulate.monthly_returns(sim_results[("MS", "c50", "rf2")]["values"])
    ms_r_primary = ms_r_primary[ms_r_primary.index <= PRIMARY_END]
    ew_r_primary = simulate.monthly_returns(sim_results[("EW", "c50", "rf2")]["values"])
    ew_r_primary = ew_r_primary[ew_r_primary.index <= PRIMARY_END]
    write_trials(ms_sh, ew_sh, records, ci, ms_r_primary, ew_r_primary)
    write_report(records, summary, sub_rows, ci, n_fallback_small, n_fallback_b0, country_counts, sector_counts,
                 last_rec, overlap, sanity_notes, sim_results, quarters, event_summary)
    print(f"DONE in {time.time()-t0:.0f}s", flush=True)


def _cum_trials():
    if not os.path.exists(TRIALS_CSV):
        return 0
    try:
        df = pd.read_csv(TRIALS_CSV)
        return len(df)
    except Exception:
        return 0


def write_trials(ms_sh, ew_sh, records, ci, ms_r_primary=None, ew_r_primary=None):
    """แก้บั๊ก 2026-09-30: mark แถวเดิม (status=ok, run ก่อนแก้บั๊ก) เป็น invalid-bug (ไม่ลบ) แล้วเติมแถว
    bugfix-rerun ที่ใช้ n_trials_cumulative **เดิม** (ไม่นับเป็น trial ใหม่ — เป็นการแก้ไข ไม่ใช่การลองพารามิเตอร์ใหม่)."""
    now = pd.Timestamp.now().isoformat()
    bug_note = "bug: _exec_nav คืน None แล้ว continue ทิ้งเงินไปเฉยๆ (ไม่ถือเป็นเงินสด) -> ดู M001_baseline.md §แก้บั๊ก"
    trial_no = {"M001-MS": None, "M001-EW": None}
    if os.path.exists(TRIALS_CSV) and os.path.getsize(TRIALS_CSV) > 0:
        df = pd.read_csv(TRIALS_CSV, dtype=str).fillna("")
        for mid in trial_no:
            # trial number ของ model_id นี้ = ค่า n_trials_cumulative ที่เคยบันทึกไว้ครั้งแรก (สถานะใดก็ได้ที่มี
            # n_trials_cumulative จริง) — กันเลขเพี้ยนถ้ารันซ้ำหลายรอบระหว่างแก้บั๊ก (ไม่นับเป็น trial ใหม่ทุกครั้ง)
            has_num = df["model_id"] == mid
            has_num = has_num & df["n_trials_cumulative"].astype(str).str.strip().ne("")
            if has_num.any():
                trial_no[mid] = int(float(df.loc[has_num, "n_trials_cumulative"].iloc[0]))
            mask_ok = (df["model_id"] == mid) & (df["status"] == "ok")
            if mask_ok.any():
                df.loc[mask_ok, "status"] = "invalid-bug"
                df.loc[mask_ok, "notes"] = df.loc[mask_ok, "notes"].astype(str) + " | " + bug_note
        df.to_csv(TRIALS_CSV, index=False)
    n0 = _cum_trials() if trial_no["M001-MS"] is None else None  # fallback ถ้าไม่เคยมีแถวเดิม (ไม่ควรเกิด)
    ms_trial = trial_no["M001-MS"] if trial_no["M001-MS"] is not None else (n0 or 0) + 1
    ew_trial = trial_no["M001-EW"] if trial_no["M001-EW"] is not None else (n0 or 0) + 2
    rows = [
        {"model_id": "M001-MS", "run_at": now, "spec_file": "M001_baseline_page8.md",
         "params": "rf=2%,cost=0.5%/side,hist>=252,B0=1classpergroup,primary=2022-03..2025-09(15q),bugfix=cash-on-exec-fail",
         "period_start": "2022-03-31", "period_end": "2025-12-31", "rf_source": "assumed constant 2%/yr",
         "cost_assumption": "0.5%/side constant", "sharpe": round(ms_sh, 4), "cagr": "", "vol": "", "max_dd": "",
         "turnover": "", "n_trials_cumulative": ms_trial,
         "deflated_sharpe": round(simulate.deflated_sharpe(ms_r_primary, RF_PRIMARY, ms_trial), 4)
         if ms_r_primary is not None else "", "status": "bugfix-rerun",
         "notes": f"CI95 {ci.get('MS')} | แก้บั๊กจาก trial เดิม (ไม่นับ trial ใหม่)"},
        {"model_id": "M001-EW", "run_at": now, "spec_file": "M001_baseline_page8.md",
         "params": "rf=2%,cost=0.5%/side,hist>=252,B0=1classpergroup,primary=2022-03..2025-09(15q),bugfix=cash-on-exec-fail",
         "period_start": "2022-03-31", "period_end": "2025-12-31", "rf_source": "assumed constant 2%/yr",
         "cost_assumption": "0.5%/side constant", "sharpe": round(ew_sh, 4), "cagr": "", "vol": "", "max_dd": "",
         "turnover": "", "n_trials_cumulative": ew_trial,
         "deflated_sharpe": round(simulate.deflated_sharpe(ew_r_primary, RF_PRIMARY, ew_trial), 4)
         if ew_r_primary is not None else "", "status": "bugfix-rerun",
         "notes": f"CI95 {ci.get('EW')} | แก้บั๊กจาก trial เดิม (ไม่นับ trial ใหม่)"},
    ]
    header = not os.path.exists(TRIALS_CSV) or os.path.getsize(TRIALS_CSV) == 0
    with open(TRIALS_CSV, "a", encoding="utf-8") as f:
        cols = list(rows[0].keys())
        if header:
            f.write(",".join(cols) + "\n")
        for row in rows:
            f.write(",".join(str(row[c]).replace(",", ";") for c in cols) + "\n")


def write_report(records, summary, sub_rows, ci, n_fb_small, n_fb_b0, country_counts, sector_counts, last_rec,
                  overlap, sanity_notes, sim_results, quarters, event_summary):
    def g(variant, cost, rf, period_prefix):
        row = summary.query(f"variant=='{variant}' and cost=='{cost}' and rf=='{rf}' and period.str.startswith('{period_prefix}')")
        return row.iloc[0] if len(row) else None

    lines = []
    lines.append("# M001 baseline — ผลวัด backtest (validator)\n")
    lines.append(f"รันเมื่อ {pd.Timestamp.now().isoformat()} · ไตรมาส {quarters[0].date()}..{quarters[-1].date()} "
                  f"({len(quarters)} ไตรมาส) · rf หลัก = 2%/ปี คงที่ (สมมติฐาน) · ต้นทุนหลัก = 0.5%/ข้าง\n")
    lines.append("## แก้บั๊ก (2026-09-30, พบโดย session หลัก)\n")
    lines.append(
        "รันครั้งแรกมีบั๊กใน `simulate.py`: เมื่อ `_exec_nav` หาราคาซื้อไม่ได้ (ไม่มี NAVDate >= execution date เลย) "
        "โค้ดเดิม `continue` ข้ามไปโดยไม่เก็บเงินส่วนนั้นไว้ที่ไหน — เงินหายไปจากพอร์ตจริง (ไม่ใช่แค่ error ทางสถิติ) "
        "พบที่ t=2026-03-31 ซึ่งกอง TEMxCH/ASP-EUROPE QUALITY/K-SEMQ/LHUSFIN-D (รวม ~89% น้ำหนัก) มี NAV ล่าสุด "
        "~2026-01-06/07 (ผ่านเกณฑ์ universe staleness 90 วัน ณ t แต่ไม่มี NAVDate ใหม่หลัง execution date เลย) "
        "ทำให้ equity ของ M001-MS ลด 64.7% ในเดือน 2026-04 อย่างผิดปกติ\n\n"
        "**แก้**: (1) น้ำหนักที่ซื้อไม่ได้ -> ถือเป็นเงินสดที่ได้ rf (2%/ปีในรันหลัก, 0 ในรัน rf=0) จนรอบ rebalance ถัดไป "
        "(2) exec lag เกิน 10 วันทำการหลัง e -> ถือว่าซื้อไม่ได้ (กันใช้ราคาที่รู้ในอนาคตไกลเกินจริง) "
        "(3) mark-to-market ใช้ NAV ล่าสุดที่มีจริงเสมอ ห้ามเป็น 0 (4) เพิ่ม assert money-conservation "
        "(มูลค่าหลัง rebalance = มูลค่าก่อน×(1-cost) และ ผลรวมน้ำหนักซื้อ+เงินสด = ผลรวมน้ำหนักเป้าหมาย) "
        "— รันจบไม่มี AssertionError ทั้ง 18 ไตรมาส × 3 variant × 3 cost × 2 rf\n\n"
        "trials.csv: แถวรันแรก (status เดิม=ok) ถูกแก้เป็น `invalid-bug` **ไม่ลบ** และเพิ่มแถวใหม่ status=`bugfix-rerun` "
        "ที่ใช้ n_trials_cumulative **เดิม** (ไม่นับเป็น trial ใหม่ เพราะเป็นการแก้ไขโค้ด ไม่ใช่การลองพารามิเตอร์ใหม่)\n")
    lines.append("## ตารางผลหลัก (primary period 2022-03-31..2025-12-31, cost 0.5%/ข้าง)\n")
    lines.append("| variant | rf | Sharpe | CAGR | vol | maxDD | Sortino | hit-rate vs B0 | IR vs B0 | TE vs B0 | turnover เฉลี่ย/ไตรมาส |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|---|")
    for variant in ("MS", "EW", "B0"):
        for rf in ("2%", "0%"):
            row = g(variant, "0.5%", rf, "primary")
            if row is not None:
                lines.append(f"| {variant} | {rf} | {row['sharpe']:.3f} | {row['cagr']:.3f} | {row['vol']:.3f} | "
                              f"{row['max_dd']:.3f} | {row['sortino']:.3f} | {row['hit_rate_vs_b0']:.2f} | "
                              f"{row['ir_vs_b0']:.3f} | {row['te_vs_b0']:.3f} | {row['avg_turnover']:.3f} |")
    lines.append("\n## Sensitivity ต้นทุน (0% / 0.5% / 1%) — rf 2%, primary period\n")
    lines.append("| variant | cost | Sharpe | CAGR |")
    lines.append("|---|---|---|---|")
    for variant in ("MS", "EW", "B0"):
        for cost in ("0%", "0.5%", "1%"):
            row = g(variant, cost, "2%", "primary")
            if row is not None:
                lines.append(f"| {variant} | {cost} | {row['sharpe']:.3f} | {row['cagr']:.3f} |")
    lines.append("\n## Extended period (..2026-07-31, ข้อมูลมีรู)\n")
    lines.append("| variant | rf | Sharpe | CAGR | maxDD |")
    lines.append("|---|---|---|---|---|")
    for variant in ("MS", "EW", "B0"):
        for rf in ("2%", "0%"):
            row = g(variant, "0.5%", rf, "extended")
            if row is not None:
                lines.append(f"| {variant} | {rf} | {row['sharpe']:.3f} | {row['cagr']:.3f} | {row['max_dd']:.3f} |")
    lines.append("\n## ช่วงย่อย / รายปี (cost 0.5%, MS/EW/B0)\n")
    lines.append("| variant | period | rf | Sharpe | CAGR | n_months |")
    lines.append("|---|---|---|---|---|---|")
    for row in sub_rows:
        c = row["cagr"]
        c_s = f"{c:.3f}" if pd.notna(c) else "nan"
        s_s = f"{row['sharpe']:.3f}" if pd.notna(row["sharpe"]) else "nan"
        lines.append(f"| {row['variant']} | {row['period']} | {row['rf']} | {s_s} | {c_s} | {row['n_months']} |")
    lines.append("\n## CI 95% ของ Sharpe (block bootstrap, block=3 เดือน, primary, rf 2%, cost 0.5%)\n")
    for variant in ("MS", "EW", "B0"):
        lo, hi = ci.get(variant, (np.nan, np.nan))
        lines.append(f"- {variant}: [{lo:.3f}, {hi:.3f}]")
    lines.append(f"\n## Fallback\n- small_n (n_ok<3): {n_fb_small} ไตรมาส · b0 (n_ok=0): {n_fb_b0} ไตรมาส จาก {len(records)} ไตรมาสทั้งหมด\n")
    lines.append("## เหตุการณ์ NAV ผิดปกติระหว่างจำลองพอร์ต (cannot_buy / exec_late / mark_stale)\n")
    lines.append("นับจาก run คอสต์ 0.5%/rf 2% (target weights เดียวกันทุก cost/rf จึงเหตุการณ์เท่ากัน) "
                  "mark_stale ใช้เกณฑ์เดียวกับ universe staleness (>90 วันปฏิทินจาก NAV ล่าสุด)\n")
    lines.append("| variant | ช่วงหลัก (2022-03..2025-12) | ช่วงขยาย (2026-01..2026-07) |")
    lines.append("|---|---|---|")
    for variant in ("MS", "EW", "B0"):
        p = event_summary[variant]["primary"]
        e = event_summary[variant]["extended"]
        p_s = ", ".join(f"{k}={v}" for k, v in p.items()) or "ไม่มี"
        e_s = ", ".join(f"{k}={v}" for k, v in e.items()) or "ไม่มี"
        lines.append(f"| {variant} | {p_s} | {e_s} |")
    lines.append("\nสรุป: ช่วงหลัก (ตัวเลขที่ใช้เทียบเป้า 0.95) แทบไม่กระทบ (cannot_buy/exec_late ในช่วงนี้ ถ้ามี "
                  "ก็เกิดใกล้ปลายปี 2025 ซึ่งข้อมูลเริ่มบางลงบ้างแล้ว — ดูตัวเลขในตารางข้างบนเทียบก่อน/หลังแก้บั๊กเพื่อยืนยัน) "
                  "ผลกระทบหลักอยู่ที่ **ช่วงขยาย 2026** ซึ่งมีรู NAV มากตามที่ spec เตือนไว้แล้ว (ก.พ. 2026 มีแค่ 107 กองรายงาน) "
                  "— ตัวเลขช่วงขยายยังไม่ควรใช้อ้างอิงไม่ว่าจะแก้บั๊กหรือไม่\n")
    lines.append("## สัดส่วน country/sector ที่ถือ (นับความถี่ตลอด backtest)\n")
    tot_c = sum(country_counts.values()) or 1
    tot_s = sum(sector_counts.values()) or 1
    lines.append("Country: " + ", ".join(f"{k}={v/tot_c:.0%}" for k, v in sorted(country_counts.items(), key=lambda x: -x[1])))
    lines.append("\n\nSector: " + ", ".join(f"{k}={v/tot_s:.0%}" for k, v in sorted(sector_counts.items(), key=lambda x: -x[1])))
    lines.append(f"\n\n## กองที่คัด ณ {last_rec['t'].date()} เทียบหน้า 8 วันนี้\n")
    lines.append(f"- picked (M001): {[m['FundCode'] for m in last_rec['picked_meta']]}")
    lines.append(f"- หน้า 8 วันนี้: {PAGE8_TODAY}")
    lines.append(f"- ตรงกัน: {overlap if overlap else 'ไม่มี'}")
    lines.append("\n## Sanity checks\n")
    for n in sanity_notes:
        lines.append(f"- {n}")
    lines.append("\n## ข้อจำกัด/สิ่งที่ตีความเอง (นอกเหนือจาก spec §7,§10 เดิม)\n")
    lines.append("- **Deflated Sharpe ratio (DSR) ที่รายงานใน trials.csv เป็นค่า \"ความน่าจะเป็น\" (probability, 0..1) "
                  "ที่ Sharpe ที่แท้จริงมากกว่า 0 หลังปรับ selection bias จากจำนวน trial — ไม่ใช่ค่า Sharpe ratio** "
                  "(อย่าอ่านเป็นหน่วยเดียวกับ Sharpe 0.17/0.95) ใช้สูตรประมาณของ Bailey & López de Prado โดยสมมติ "
                  "trial-Sharpe variance หน่วยเดียวกัน (ไม่มี distribution ของ Sharpe จากหลาย trial จริงเพราะเพิ่งเริ่ม M001) "
                  "— ตัวเลขเป็นเพียง order-of-magnitude ของความมั่นใจ ไม่ใช่ตัวเลขแม่นยำ")
    lines.append("- ไม่ได้ลอง map base_data/SecFundFee.csv (ผู้ใช้อนุมัติใช้ 0.5% คงที่ตรงๆ ใน §11.2 แล้ว) — ถ้าต้องการ map จริงต้องรันเพิ่ม")
    lines.append("- frozen_fund นับจากกองที่ไม่มี NAVDate ใหม่ระหว่าง [e, e ถัดไป] ขณะถือ (รวม approx ที่ e เอง)")
    lines.append("- IR/TE เทียบ B0 คำนวณจาก B0 cost 0.5% เดียวกัน (ไม่ใช่ B0 gross)")
    out = os.path.join(common.RESULTS_DIR, "M001_baseline.md")
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"  wrote {out}")


if __name__ == "__main__":
    run(smoke=("smoke" in sys.argv))
