"""run_m009.py — M009-NC (SR12 สุทธิต้นทุน, n_trials 21) บน M004-TF-FX ตาม specs/M009_sr12_net_cost.md (+ การตัดสินใจของผู้ใช้ 2026-10-03)

รัน: PYTHONPATH=. ./.venv/bin/python .claude/quant_team/backtest/run_m009.py
ขั้นตอน: (A) บังคับ pen≡0 ผ่านโค้ด wrapper เดียวกัน -> ต้องตรง M004-TF-FX_weights.csv (max|Δw|<1e-9) และ Sharpe full/flat/nofront = 0.706119/0.720494/0.893296
         (B) ถ้าผ่านเท่านั้น -> รัน M009-NC (pen เปิด) · ไม่แก้ไฟล์เดิม · reuse common/fund_signals/weighting/fees/simulate/run_m006_m007
(ไม่เรียก nav_loader.load_nav_history / data_access.build_*; NAV จาก cache/nav_clean.parquet เท่านั้น)
"""
from __future__ import annotations

import json
import os
import sys
import time
import traceback
from collections import Counter, defaultdict

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if THIS_DIR not in sys.path:
    sys.path.insert(0, THIS_DIR)

import numpy as np
import pandas as pd

import common
import fees
import fund_signals as fs
import simulate
import weighting as wt
import run_m006_m007 as r67
from run_m008 import theme_shares, theme_of
from data import msci_index

TEAM_DIR = os.path.dirname(THIS_DIR)
SCRATCH = os.path.join(TEAM_DIR, "scratch")
RES = common.RESULTS_DIR
TRIALS_CSV = os.path.join(TEAM_DIR, "trials.csv")
PE, RF = r67.PRIMARY_END, 0.02
HOLD_YRS, WIN = 1.0, 11.0 / 12.0
N_TRIALS = 21
SEL_N, SEL_K = 8, 16
PHASE_B = False
REG_REF = {"full": 0.706119, "flat": 0.720494, "nofront": 0.893296}


# ---------------- ข้อมูลต่อไตรมาส (คำนวณครั้งเดียว ใช้ทั้ง regression และรันจริง) ----------------

def prepare(nav, nav_by_fund, calendar, groups, quarters):
    nav_arrays = fs._prep_arrays(nav_by_fund)
    ctxs = []
    t0 = time.time()
    for qi, t in enumerate(quarters):
        u_t = common.universe_at(nav, t)
        b0_df = common.b0_universe(u_t, groups)
        b0_w = pd.Series(1.0 / len(b0_df), index=b0_df["FundCode"])
        qctx = fs.QuarterContext(nav_arrays, calendar, t)
        sig = fs.compute_quarter_signals(qctx, u_t["FundCode"].tolist())
        i_t, _, _ = fs.investable_set(t, u_t, sig, groups, family_fix=True)
        wk = {fc: qctx.weekly_return_series(fc) for fc in i_t["FundCode"]}
        ctxs.append({"qi": qi, "t": t, "e": common.execution_date(calendar, t), "i_t": i_t, "wk": wk,
                     "vol_map": dict(zip(i_t["FundCode"], i_t["vol52"])), "b0_w": b0_w, "n_u": len(u_t)})
        print(f"  prep [{qi+1}/{len(quarters)}] t={t.date()} U={len(u_t)} I={len(i_t)} ({time.time()-t0:.0f}s)", flush=True)
    return ctxs


def rate_flag(fd, fc, code, t):
    """(อัตรา %, ใช้ median fallback หรือไม่) — ใช้ FeeData.rate เดิมทุกกติกา."""
    b = fd.n_fallback[code]
    v = fd.rate(fc, code, t)
    return v, fd.n_fallback[code] > b


def select_stream(ctxs, pen_on, fd_dec, acwi, erc_cache):
    """เดิน selection รายไตรมาส (เหมือน r67 NEWQ) · pen_on=False = pen≡0 ผ่านเส้นทางโค้ดเดียวกัน (regression)."""
    held, prev_fb = {}, False
    sleeves, rows, diag, plan_meta = {}, [], [], []
    pen_all, pen_top16, gaps = [], [], []
    for ctx in ctxs:
        qi, t, i_t = ctx["qi"], ctx["t"], ctx["i_t"]
        reps = wt.family_representatives(i_t, "SR12", held_funds=set(held.values()))
        H_map = {} if prev_fb else held
        reps_net, tab = {}, {}
        n_cls_changed = n_fb_pen = n_new_pen = 0
        for f, r in reps.items():
            j = r["FundCode"]
            if f in H_map and H_map[f] != j:
                n_cls_changed += 1
            if (not pen_on) or H_map.get(f) == j:
                pen, ff, bf = 0.0, np.nan, np.nan
            else:
                ff, fb1 = rate_flag(fd_dec, j, "FF", t)
                bf, fb2 = rate_flag(fd_dec, j, "BF", t)
                n_fb_pen += int(fb1) + int(fb2)
                n_new_pen += 1
                c_j = (ff + bf) / 100.0
                pen = c_j * WIN / HOLD_YRS / r["vol52"]
            reps_net[f] = {**r, "signal": r["signal"] - pen}
            tab[f] = {"FundCode": j, "SR12": r["signal"], "vol52": r["vol52"], "pen": pen, "FF": ff, "BF": bf,
                      "score": r["signal"] - pen, "held": H_map.get(f) == j}
        ranks_raw = wt.rank_families(reps)
        ranks_net = wt.rank_families(reps_net)
        sel = wt.hysteresis_select(reps_net, ranks_net, H_map, SEL_N, SEL_K, None, rho_max=0.85)
        fallback = sel["fallback"] == "b0" or len(sel["S"]) == 0
        # diagnostics: กองที่ถือต่อเพราะค่าปรับ
        kept_by_pen = [f for f, fc in H_map.items() if f in reps and reps[f]["FundCode"] == fc and f in sel["S"]
                       and ranks_raw[f] > SEL_K and ranks_net[f] <= SEL_K] if not fallback else []
        # gap SR12 อันดับดิบ 8 vs 9..16
        srt = sorted(reps.items(), key=lambda kv: ranks_raw[kv[0]])
        sr_by_rank = [kv[1]["signal"] for kv in srt]
        if len(sr_by_rank) >= 16:
            gaps.append({"t": t, "g8_9": sr_by_rank[7] - sr_by_rank[8], "g8_12": sr_by_rank[7] - sr_by_rank[11],
                         "g8_16": sr_by_rank[7] - sr_by_rank[15]})
        for f, d in tab.items():
            if pen_on and not d["held"]:
                pen_all.append(d["pen"])
                if ranks_raw[f] <= SEL_K:
                    pen_top16.append(d["pen"])
            if ranks_raw[f] <= 25 or ranks_net[f] <= 25 or d["held"] or (f in sel["S"]):
                rows.append({"t": t.date(), "family": f, **d, "rank_raw": ranks_raw[f], "rank_net": ranks_net[f],
                             "selected": f in sel["S"]})
        diag.append({"qi": qi, "t": t.date(), "n_I": len(i_t), "prev_fb": prev_fb, "fallback": fallback,
                     "n_class_changed_in_family": n_cls_changed, "n_pen_new": n_new_pen, "n_pen_median_fb": n_fb_pen,
                     "kept_by_pen": ";".join(kept_by_pen), "n_kept_by_pen": len(kept_by_pen),
                     "n_kept": sel.get("n_kept"), "n_added": sel.get("n_added"), "n_removed": sel.get("n_removed")})
        if fallback:
            held, prev_fb = {}, True
            sleeves[qi] = ctx["b0_w"]
            continue
        held, prev_fb = dict(sel["S"]), False
        funds = list(sel["S"].values())
        key = (qi, tuple(funds))
        if key not in erc_cache:
            w, _src = wt.risk_parity_weights(funds, ctx["wk"], ctx["vol_map"], method="erc")
            erc_cache[key] = wt.apply_cap(w, 0.25)
        sleeves[qi] = erc_cache[key]
    return {"sleeves": sleeves, "rows": pd.DataFrame(rows), "diag": pd.DataFrame(diag), "pen_all": np.array(pen_all),
            "pen_top16": np.array(pen_top16), "gaps": pd.DataFrame(gaps)}


def make_plan(sleeves, quarters, calendar, acwi):
    return r67.old_style_plan(sleeves, quarters, calendar, lambda t: wt.trend_filter_cash(acwi, t, 0.25))


# ---------------- simulate หลายกรณีต้นทุน ----------------

def sim_cases(plan, nav_by_fund, months, fd_sim):
    clean = [{k: v for k, v in p.items() if k in ("t", "e", "weights")} for p in plan]
    yrs = (PE - clean[0]["e"]).days / 365.25
    out = {}
    for tag, kind in (("c0", "c0"), ("c50", "c50"), ("c100", "c100"), ("flat", "flat"), ("full", "full"), ("nofront", "nofront")):
        fm = {"full": lambda: fees.FeeModel(fd_sim, "full"), "nofront": lambda: fees.FeeModel(fd_sim, "nofront"),
              "flat": lambda: fees.FeeModel(None, "flat", 0.005)}.get(kind, lambda: None)()
        cs = {"c0": 0.0, "c50": 0.005, "c100": 0.01}.get(kind, 0.0)
        info = {}
        v, tu, ev, _ = simulate.simulate_path(clean, nav_by_fund, months, cs, RF, include_start=True, info=info, fee_model=fm)
        ent = [x for x in info["entries"] if x["e"] <= PE]
        m = r67.per_metrics(v, RF)
        cost = sum(x["cost"] for x in ent)
        full_ent = ent[1:]
        o = {"values": v, "metrics": m, "cost_bp_yr": cost / yrs * 1e4, "turn_yr": sum(x["turnover"] for x in full_ent) / yrs,
             "entries": ent, "n_cannot_buy": sum(1 for e in ev if e["type"] == "cannot_buy")}
        if fm is not None:
            tot = fm.tot
            o["switch_share"] = tot["switch_vol"] / tot["sell_vol"] if tot["sell_vol"] > 0 else np.nan
            o["avg_fee_pct"] = cost / (tot["sell_vol"] + tot["buy_vol"]) * 100 if (tot["sell_vol"] + tot["buy_vol"]) > 0 else np.nan
            o["sell_vol_yr"], o["buy_vol_yr"] = tot["sell_vol"] / yrs, tot["buy_vol"] / yrs
        out[tag] = o
    out["yrs"] = yrs
    return out


# ---------------- regression ----------------

def regression(plan_base, sims_base):
    ref = pd.read_csv(os.path.join(RES, "M004-TF-FX_weights.csv"))
    refd = {(pd.Timestamp(r.t), r.FundCode): r.weight for r in ref.itertuples()}
    mine = {}
    for p in plan_base:
        for f, w in p["weights"].items():
            if w > 1e-12:
                mine[(p["t"], f)] = w
    keys = set(refd) | set(mine)
    dmax = max(abs(refd.get(k, 0.0) - mine.get(k, 0.0)) for k in keys)
    only = [k for k in keys if (k in refd) != (k in mine)]
    sh = {k: sims_base[k]["metrics"]["sharpe"] for k in ("full", "flat", "nofront")}
    ok_w = dmax < 1e-9 and not only
    ok_s = all(abs(round(sh[k], 6) - REG_REF[k]) < 1.5e-6 for k in REG_REF)
    return {"max_dw": float(dmax), "n_rows_ref": len(ref), "n_rows_mine": len(mine), "n_only_one_side": len(only),
            "sharpe": sh, "ok_w": bool(ok_w), "ok_s": bool(ok_s), "ok": bool(ok_w and ok_s)}


# ---------------- diagnostics ที่ใช้ plan (ชุดกอง/ระยะถือ/FF=0) ----------------

def holdings(plan):
    return [{f: w for f, w in p["weights"].items() if f != "__CASH__" and w > 1e-12} for p in plan]


def entry_stats(hold, fd_diag, quarters):
    new_counts, ff0_entry, ff0_entry_all, ff_med_fb = [], [], [], 0
    entered_funds = []
    all_entry_funds = []
    for q, h in enumerate(hold):
        prev = set(hold[q - 1]) if q > 0 else set()
        new = [f for f in h if f not in prev]
        if q > 0:
            new_counts.append(len(new))
            entered_funds += [(q, f) for f in new]
        all_entry_funds += [(q, f) for f in new]
    def ff0(lst):
        flags = []
        for q, f in lst:
            v, fb = rate_flag(fd_diag, f, "FF", quarters[q])
            flags.append((f, v == 0.0 and not fb, fb))
        return flags
    fl_after = ff0(entered_funds)
    fl_all = ff0(all_entry_funds)
    # fund-quarters + weight share
    fq, fq0, wsum, w0 = 0, 0, [], []
    ff0_funds = Counter()
    for q, h in enumerate(hold):
        tot = sum(h.values())
        w_ff0 = 0.0
        for f, w in h.items():
            v, fb = rate_flag(fd_diag, f, "FF", quarters[q])
            fq += 1
            if v == 0.0 and not fb:
                fq0 += 1
                w_ff0 += w
                ff0_funds[f] += 1
        w0.append(w_ff0 / tot if tot > 0 else 0.0)
    # episodes
    eps_after, eps_all = [], []
    funds_all = set().union(*[set(h) for h in hold])
    for f in funds_all:
        q = 0
        while q < len(hold):
            if f in hold[q]:
                s = q
                while q < len(hold) and f in hold[q]:
                    q += 1
                eps_all.append(q - s)
                if s > 0:
                    eps_after.append(q - s)
            else:
                q += 1
    return {"new_per_q_mean": float(np.mean(new_counts)), "new_per_q_list": new_counts,
            "n_entries_after_first": len(fl_after), "ff0_entries_after_first": sum(1 for x in fl_after if x[1]),
            "ff0_entry_frac_after_first": float(np.mean([x[1] for x in fl_after])) if fl_after else np.nan,
            "n_entries_all": len(fl_all), "ff0_entry_frac_all": float(np.mean([x[1] for x in fl_all])) if fl_all else np.nan,
            "ff_median_fb_entries": sum(1 for x in fl_all if x[2]),
            "fq": fq, "fq_ff0_frac": fq0 / fq if fq else np.nan, "w_ff0_mean": float(np.mean(w0)),
            "ff0_funds": dict(ff0_funds), "hold_q_mean_entered": float(np.mean(eps_after)) if eps_after else np.nan,
            "hold_q_mean_all": float(np.mean(eps_all)), "n_episodes": len(eps_all)}


def concentration(sleeves):
    rows = []
    for qi, sw in sleeves.items():
        tm, tn = theme_shares(sw)
        tm3, tn3 = theme_shares(sw, ("infra", "india", "tech"))
        rows.append({"qi": qi, "theme_max": tm, "theme_name": tn, "theme3_max": tm3, "theme3_name": tn3, "n": len(sw),
                     "max_w": float(sw.max())})
    return pd.DataFrame(rows)


# ---------------- main ----------------

def main():
    t0 = time.time()
    print("[1/7] load...", flush=True)
    nav = common.load_nav()
    nav_by_fund = common.build_nav_by_fund(nav)
    calendar = common.load_calendar()
    groups = common.load_groups()
    acwi = msci_index.load_country_index()["MSCI_ACWI"]
    codes = sorted(nav["FundCode"].unique())
    quarters = common.quarter_ends(calendar, "2022-03-31", "2025-09-30")
    t_first = quarters[0]
    bound_m = quarters[-1] + pd.Timedelta(days=75)
    months = [m for m in common.month_ends(calendar, common.execution_date(calendar, t_first), "2026-03-31")
              if m <= bound_m + pd.Timedelta(days=31)]
    assert months[-1] == PE, months[-1]
    fd_dec, fd_sim, fd_diag = fees.FeeData(codes), fees.FeeData(codes), fees.FeeData(codes)
    print(f"  quarters {len(quarters)} {quarters[0].date()}..{quarters[-1].date()} · fee medians {fd_dec.median} rows {fd_dec.n_rows}", flush=True)

    print("[2/7] prepare per-quarter contexts...", flush=True)
    ctxs = prepare(nav, nav_by_fund, calendar, groups, quarters)
    erc_cache = {}

    print("[3/7] (A) regression pen≡0...", flush=True)
    base = select_stream(ctxs, False, fd_dec, acwi, erc_cache)
    plan_base = make_plan(base["sleeves"], quarters, calendar, acwi)
    sims_base = sim_cases(plan_base, nav_by_fund, months, fd_sim)
    reg = regression(plan_base, sims_base)
    print("  REGRESSION:", json.dumps(reg, default=float), flush=True)
    json.dump(reg, open(os.path.join(SCRATCH, "validator_m009_regression.json"), "w"), default=float)
    if not reg["ok"]:
        print("REGRESSION FAIL — หยุด ไม่รัน M009", flush=True)
        return 2
    n_fb_before = dict(fd_dec.n_fallback)

    print("[4/7] (B) รัน M009-NC...", flush=True)
    global PHASE_B
    PHASE_B = True
    nc = select_stream(ctxs, True, fd_dec, acwi, erc_cache)
    plan_nc = make_plan(nc["sleeves"], quarters, calendar, acwi)
    sims_nc = sim_cases(plan_nc, nav_by_fund, months, fd_sim)
    pen_fb = {k: fd_dec.n_fallback[k] - n_fb_before.get(k, 0) for k in ("FF", "BF")}

    print("[5/7] diagnostics...", flush=True)
    ret = lambda s, tag: (lambda r: r[r.index <= PE])(simulate.monthly_returns(s[tag]["values"]))
    r_nc, r_b = ret(sims_nc, "full"), ret(sims_base, "full")
    d_full = simulate.paired_bootstrap_diff_ci(r_nc, r_b, RF)
    d_c50 = simulate.paired_bootstrap_diff_ci(ret(sims_nc, "c50"), ret(sims_base, "c50"), RF)
    late = lambda r: r[r.index >= "2023-07-01"]
    early = lambda r: r[r.index <= "2022-12-31"]
    d_late = simulate.paired_bootstrap_diff_ci(late(r_nc), late(r_b), RF)
    ci_nc = simulate.block_bootstrap_ci(r_nc, RF)
    ci_b = simulate.block_bootstrap_ci(r_b, RF)
    dsr_nc = simulate.deflated_sharpe(r_nc, RF, N_TRIALS)
    dsr_nc50 = simulate.deflated_sharpe(ret(sims_nc, "c50"), RF, N_TRIALS)
    dsr_b21 = simulate.deflated_sharpe(r_b, RF, N_TRIALS)
    hold_nc, hold_b = holdings(plan_nc), holdings(plan_base)
    es_nc = entry_stats(hold_nc, fd_diag, quarters)
    es_b = entry_stats(hold_b, fd_diag, quarters)
    n_diff_q = sum(1 for a, b in zip(hold_nc, hold_b) if set(a) != set(b))
    diff_q_list = [str(quarters[i].date()) for i, (a, b) in enumerate(zip(hold_nc, hold_b)) if set(a) != set(b)]
    conc_nc, conc_b = concentration(nc["sleeves"]), concentration(base["sleeves"])
    dg = nc["diag"]
    bdg = base["diag"]
    # เมตริกอ้างอิงจาก COST summary
    cs = pd.read_csv(os.path.join(RES, "COST_real_fees_summary.csv")).set_index("trial")

    # ---------- เขียนไฟล์ผล ----------
    print("[6/7] write outputs...", flush=True)
    eq = pd.DataFrame({"M009-NC_full": sims_nc["full"]["values"], "M009-NC_c50": sims_nc["c50"]["values"],
                       "M009-NC_c0": sims_nc["c0"]["values"], "M004-TF-FX_full": sims_base["full"]["values"],
                       "M004-TF-FX_c50": sims_base["c50"]["values"], "M004-TF-FX_c0": sims_base["c0"]["values"]})
    eq.to_csv(os.path.join(RES, "M009_equity_curve.csv"))
    wrows = [{"trial": "M009-NC", "offset": "Q", "t": en["t"].date() if hasattr(en["t"], "date") else en["t"],
              "e": en["e"].date(), "kind": en["mode"], "FundCode": f, "weight": w}
             for en in sims_nc["full"]["entries"] for f, w in en["target"].items() if w > 1e-12]
    pd.DataFrame(wrows).to_csv(os.path.join(RES, "M009-NC_weights.csv"), index=False)
    nc["rows"].to_csv(os.path.join(RES, "M009_selection_log.csv"), index=False)
    dg2 = dg.copy()
    dg2["same_set_as_M004"] = [set(a) == set(b) for a, b in zip(hold_nc, hold_b)]
    dg2.to_csv(os.path.join(RES, "M009_quarter_diag.csv"), index=False)
    cols = ["c0", "c50", "c100", "flat", "full", "nofront"]
    summ = []
    for name, sims in (("M009-NC", sims_nc), ("M004-TF-FX", sims_base)):
        for c in cols:
            s = sims[c]
            summ.append({"trial": name, "cost": c, **s["metrics"], "cost_bp_yr": s["cost_bp_yr"], "turn_yr": s["turn_yr"],
                         "switch_share": s.get("switch_share", np.nan), "avg_fee_pct": s.get("avg_fee_pct", np.nan),
                         "n_cannot_buy": s["n_cannot_buy"]})
    summ = pd.DataFrame(summ)
    summ.to_csv(os.path.join(RES, "M009_summary_metrics.csv"), index=False)

    g = lambda sims, c, k: sims[c]["metrics"][k]
    dd = d_full
    dcost = sims_nc["full"]["cost_bp_yr"] - sims_base["full"]["cost_bp_yr"]
    if dd[2] < 0:
        verdict = "ไม่ผ่าน"
    elif dd[0] > 0:
        verdict = "ผ่าน (ดีกว่า)"
    elif dcost < 0:
        verdict = "ผ่านแบบมีเงื่อนไข (เทียบเท่าแต่ถูกกว่า)"
    else:
        verdict = "ไม่เข้าเกณฑ์ผ่านใด (Δ ≥ 0 แต่ต้นทุนไม่ลด) — ไม่ผ่าน"
    gp = nc["gaps"]
    pen_a, pen_t = nc["pen_all"], nc["pen_top16"]
    res = {"verdict": verdict, "dd": dd, "d_c50": d_c50, "d_late": d_late, "dcost": dcost, "ci_nc": ci_nc, "ci_b": ci_b,
           "dsr_nc": dsr_nc, "dsr_nc50": dsr_nc50, "dsr_b21": dsr_b21, "n_diff_q": n_diff_q, "diff_q_list": diff_q_list}
    L = []
    A = L.append
    A("# M009-NC — SR12 สุทธิต้นทุน บน M004-TF-FX (n_trials = 21) — ผลวัด (validator)\n")
    A(f"รันเมื่อ {pd.Timestamp.now().isoformat()} · spec `specs/M009_sr12_net_cost.md` + การตัดสินใจผู้ใช้ 2026-10-03 · primary เม.ย. 2022 → 2025-12-31 "
      f"(45 เดือน, วิธีวัดใหม่นับเดือนแรก) · rf 2% คงที่ · ไม่ปรับพารามิเตอร์ใดๆ (HOLD_YRS=1, ×11/12, ตายตัวตาม spec) · ไม่มี holdout 2026\n")
    A("## 1. Regression ก่อนรัน (pen ≡ 0 ผ่าน wrapper เดียวกัน)\n")
    A(f"- น้ำหนักเทียบ `M004-TF-FX_weights.csv`: **max|Δw| = {reg['max_dw']:.2e}** · แถว csv {reg['n_rows_ref']} vs แถวที่คำนวณ {reg['n_rows_mine']} · "
      f"คีย์ที่มีฝั่งเดียว {reg['n_only_one_side']} → **{'PASS' if reg['ok_w'] else 'FAIL'}** (เกณฑ์ < 1e-9)")
    A(f"- Sharpe (ค่าธรรมเนียมจริง / flat 0.5% / nofront) = {reg['sharpe']['full']:.6f} / {reg['sharpe']['flat']:.6f} / {reg['sharpe']['nofront']:.6f} "
      f"vs อ้างอิง 0.706119 / 0.720494 / 0.893296 → **{'PASS' if reg['ok_s'] else 'FAIL'}**\n")
    A("## 2. ตารางผลหลัก (ค่าธรรมเนียมจริง FEEUH full, rf 2%)\n")
    A("| โมเดล | Sharpe | CAGR | vol | maxDD | cost bp/ปี | turnover/ปี | CI95% Sharpe |")
    A("|---|---|---|---|---|---|---|---|")
    for nm, sims, ci in (("**M009-NC**", sims_nc, ci_nc), ("M004-TF-FX", sims_base, ci_b)):
        m = sims["full"]["metrics"]
        A(f"| {nm} | {m['sharpe']:.3f} | {m['cagr']:.4f} | {m['vol']:.4f} | {m['max_dd']:.4f} | {sims['full']['cost_bp_yr']:.1f} | "
          f"{sims['full']['turn_yr']:.3f} | [{ci[0]:.2f}, {ci[1]:.2f}] |")
    for nm in ("M001-MS", "B0"):
        r = cs.loc[nm]
        A(f"| {nm} (อ้างอิง COST_real_fees) | {r['sharpe_full']:.3f} | {r['cagr_full']:.4f} | {r['vol_full']:.4f} | {r['maxdd_full']:.4f} | {r['cost_bp_yr_full']:.1f} | — | — |")
    A("")
    A("## 3. ตัวชี้วัดหลัก + เกณฑ์ตัดสิน (ล็อกล่วงหน้า)\n")
    A(f"- Δ Sharpe_full (M009-NC − M004-TF-FX), paired block bootstrap (block=3, 2000 รอบ, seed 0 — ค่าเริ่มต้นเดียวกับครั้งก่อน) = **{dd[2]:+.4f}** "
      f"CI95% **[{dd[0]:+.3f}, {dd[1]:+.3f}]** ({'คร่อม 0' if dd[0] <= 0 <= dd[1] else 'ไม่คร่อม 0'})")
    A(f"- cost bp/ปี (full): M009-NC {sims_nc['full']['cost_bp_yr']:.1f} vs M004-TF-FX {sims_base['full']['cost_bp_yr']:.1f} → ต่าง {dcost:+.1f} bp")
    A(f"- **ผลตามเกณฑ์: {verdict}**\n")
    A(f"- Δ ที่ cost 0.5%/ข้าง คงที่ (ตามที่ทีมเทียบครั้งก่อน, ข้อมูลประกอบ): {d_c50[2]:+.4f} CI [{d_c50[0]:+.3f}, {d_c50[1]:+.3f}]")
    A(f"- Δ เฉพาะ 2023-07..2025-12 (หลัง snapshot ค่าธรรมเนียมแรก, full): {d_late[2]:+.4f} CI [{d_late[0]:+.3f}, {d_late[1]:+.3f}] (n={len(late(r_nc))} เดือน)\n")
    A("## 4. รายงานคู่ — Sharpe/CAGR/vol/maxDD ต่อกรณีต้นทุน (ไม่ใช้ตัดสิน)\n")
    A("| ต้นทุน | M009 Sharpe | M009 CAGR | M009 vol | M009 maxDD | TF-FX Sharpe | TF-FX CAGR | TF-FX vol | TF-FX maxDD |")
    A("|---|---|---|---|---|---|---|---|---|")
    lab = {"c0": "0%", "c50": "0.5%/ข้าง (ไม่ผ่าน fee model)", "c100": "1%/ข้าง", "flat": "flat 0.5% (fee model)", "full": "ค่าธรรมเนียมจริง full",
           "nofront": "nofront (น้ำหนักชุดเดียวกัน; โมเดลตัดสินด้วย FF+BF เต็ม)"}
    for c in cols:
        a, b = sims_nc[c]["metrics"], sims_base[c]["metrics"]
        A(f"| {lab[c]} | {a['sharpe']:.3f} | {a['cagr']:.4f} | {a['vol']:.4f} | {a['max_dd']:.4f} | {b['sharpe']:.3f} | {b['cagr']:.4f} | {b['vol']:.4f} | {b['max_dd']:.4f} |")
    A("")
    A("## 5. ต้นทุน / การหมุนกอง\n")
    A("| ตัวชี้วัด | M009-NC | M004-TF-FX |")
    A("|---|---|---|")
    for nm, key, f in (("turnover ½Σ|Δw|/ปี (ไม่รวมซื้อเข้าครั้งแรก)", "turn_yr", "{:.3f}"), ("cost bp/ปี (full)", "cost_bp_yr", "{:.1f}")):
        A(f"| {nm} | " + f.format(sims_nc['full'][key]) + " | " + f.format(sims_base['full'][key]) + " |")
    A(f"| cost bp/ปี (0.5% คงที่) | {sims_nc['c50']['cost_bp_yr']:.1f} | {sims_base['c50']['cost_bp_yr']:.1f} |")
    A(f"| ยอดซื้อ+ขาย/ปี (fee model, สัดส่วนพอร์ต) | {sims_nc['full']['buy_vol_yr']+sims_nc['full']['sell_vol_yr']:.3f} | {sims_base['full']['buy_vol_yr']+sims_base['full']['sell_vol_yr']:.3f} |")
    A(f"| fee เฉลี่ย/ข้าง (%) full | {sims_nc['full']['avg_fee_pct']:.3f} | {sims_base['full']['avg_fee_pct']:.3f} |")
    A(f"| สัดส่วนช่องทางสับเปลี่ยน (ของยอดขาย) | {sims_nc['full']['switch_share']:.3f} | {sims_base['full']['switch_share']:.3f} |")
    A(f"| กองใหม่ต่อไตรมาส (ไตรมาส 2–15, ชุดกองในพอร์ต) | {es_nc['new_per_q_mean']:.2f} | {es_b['new_per_q_mean']:.2f} |")
    A(f"| ระยะถือเฉลี่ยของกองที่เข้าหลังไตรมาสแรก (ไตรมาส; ตัดปลาย = นับถึงไตรมาสสุดท้าย) | {es_nc['hold_q_mean_entered']:.2f} | {es_b['hold_q_mean_entered']:.2f} |")
    A(f"| ระยะถือเฉลี่ยทุกช่วงถือ (รวมชุดแรก) | {es_nc['hold_q_mean_all']:.2f} | {es_b['hold_q_mean_all']:.2f} |")
    A(f"| จำนวนช่วงถือ (episodes) | {es_nc['n_episodes']} | {es_b['n_episodes']} |")
    A(f"- จำนวนไตรมาสที่ชุดกองต่างจาก M004-TF-FX: **{n_diff_q}/{len(quarters)}** ({', '.join(diff_q_list)})\n")
    A("## 6. สัดส่วนกอง class ที่ FF = 0 ที่เข้าพอร์ต (การตัดสินใจผู้ใช้ ข้อ 1 — คงไว้ใน universe, รายงานเท่านั้น)\n")
    A("FF = 0 นิยาม = ค่า FEEUH Actual Value (PIT ณ วัน t) เป็น 0 จริง ไม่นับค่าที่ถูกแทนด้วย median\n")
    A("| ตัวชี้วัด | M009-NC | M004-TF-FX |")
    A("|---|---|---|")
    A(f"| กองที่เข้าหลังไตรมาสแรกซึ่ง FF=0 | {es_nc['ff0_entries_after_first']}/{es_nc['n_entries_after_first']} ({es_nc['ff0_entry_frac_after_first']:.1%}) | {es_b['ff0_entries_after_first']}/{es_b['n_entries_after_first']} ({es_b['ff0_entry_frac_after_first']:.1%}) |")
    A(f"| กองที่เข้าทั้งหมด (รวมชุดแรก) ซึ่ง FF=0 | {es_nc['ff0_entry_frac_all']:.1%} (n={es_nc['n_entries_all']}) | {es_b['ff0_entry_frac_all']:.1%} (n={es_b['n_entries_all']}) |")
    A(f"| สัดส่วน fund-quarter ที่ถือซึ่ง FF=0 | {es_nc['fq_ff0_frac']:.1%} | {es_b['fq_ff0_frac']:.1%} |")
    A(f"| น้ำหนักเฉลี่ย (ของส่วนกอง) ใน FF=0 | {es_nc['w_ff0_mean']:.1%} | {es_b['w_ff0_mean']:.1%} |")
    A(f"| กองที่เข้าซึ่ง FF ใช้ค่า median fallback | {es_nc['ff_median_fb_entries']} | {es_b['ff_median_fb_entries']} |")
    A(f"- กอง FF=0 ที่เคยถือ (จำนวนไตรมาส) — M009-NC: {es_nc['ff0_funds']}")
    A(f"- กอง FF=0 ที่เคยถือ (จำนวนไตรมาส) — M004-TF-FX: {es_b['ff0_funds']}\n")
    A("## 7. ผลย่อยช่วงเวลา (Sharpe)\n")
    A("| ช่วง | M009 full | TF-FX full | M009 c50 | TF-FX c50 |")
    A("|---|---|---|---|---|")
    for lbl, k in (("2022 (เม.ย.–ธ.ค.)", "sharpe_2022"), ("2023-07..2025-12", "sharpe_2307_2512"), ("2022-04..2023-06", "sharpe_2204_2306")):
        A(f"| {lbl} | {g(sims_nc,'full',k):.3f} | {g(sims_base,'full',k):.3f} | {g(sims_nc,'c50',k):.3f} | {g(sims_base,'c50',k):.3f} |")
    A(f"| maxDD ถึง 2022-12 | {g(sims_nc,'full','maxdd_2022'):.4f} | {g(sims_base,'full','maxdd_2022'):.4f} | {g(sims_nc,'c50','maxdd_2022'):.4f} | {g(sims_base,'c50','maxdd_2022'):.4f} |")
    A("")
    A("## 8. การกระจาย pen เทียบช่องว่าง SR12\n")
    A(f"- pen (กองที่ไม่ได้ถือ class นั้น, ทุก family × 15 ไตรมาส; n={len(pen_a)}): median {np.median(pen_a):.3f} · p90 {np.percentile(pen_a,90):.3f} · max {pen_a.max():.3f}")
    A(f"- pen เฉพาะ family ที่อันดับดิบ ≤ 16 (n={len(pen_t)}): median {np.median(pen_t):.3f} · p90 {np.percentile(pen_t,90):.3f}")
    A(f"- ช่องว่าง SR12 อันดับดิบ 8 vs 9 / 12 / 16 (median ข้ามไตรมาส): {gp['g8_9'].median():.3f} / {gp['g8_12'].median():.3f} / {gp['g8_16'].median():.3f} "
      f"(p90: {gp['g8_9'].quantile(.9):.3f} / {gp['g8_12'].quantile(.9):.3f} / {gp['g8_16'].quantile(.9):.3f})")
    A(f"- กองที่ถือต่อเพราะค่าปรับ (อันดับดิบ > 16 แต่อันดับสุทธิ ≤ 16 และถูกถือต่อ): รวม **{int(dg['n_kept_by_pen'].sum())} ครั้ง-กอง** ใน {int((dg['n_kept_by_pen']>0).sum())} ไตรมาส")
    A("- ข้อ reviewer (§8): (1) family เดิมแต่ class ถือ ≠ rep ปัจจุบัน (นับเป็นกองใหม่): " +
      f"{int(dg['n_class_changed_in_family'].sum())} ครั้ง · (3) ไตรมาสที่ prev_fallback (ทุกกองถูกปรับเป็นกองใหม่): {int(dg['prev_fb'].sum())} "
      f"· ไตรมาสที่ fallback เป็น B0: M009 {int(dg['fallback'].sum())}, TF-FX {int(bdg['fallback'].sum())} · (4) ค่า median fallback ใน pen: FF {pen_fb['FF']} / BF {pen_fb['BF']} "
      f"จากทั้งหมด {int(dg['n_pen_new'].sum())} ค่าของแต่ละ code\n")
    A("## 9. ความกระจุกตามธีม (สัดส่วนของส่วนกอง, regex ชื่อกองจาก run_m008)\n")
    A("| ตัวชี้วัด | M009-NC | M004-TF-FX |")
    A("|---|---|---|")
    A(f"| ธีมใหญ่สุด เฉลี่ยข้ามไตรมาส / สูงสุด | {conc_nc['theme_max'].mean():.3f} / {conc_nc['theme_max'].max():.3f} | {conc_b['theme_max'].mean():.3f} / {conc_b['theme_max'].max():.3f} |")
    A(f"| infra/india/tech ใหญ่สุด เฉลี่ย / สูงสุด | {conc_nc['theme3_max'].mean():.3f} / {conc_nc['theme3_max'].max():.3f} | {conc_b['theme3_max'].mean():.3f} / {conc_b['theme3_max'].max():.3f} |")
    A(f"| น้ำหนักกองเดี่ยวสูงสุด (เฉลี่ย / สูงสุด) | {conc_nc['max_w'].mean():.3f} / {conc_nc['max_w'].max():.3f} | {conc_b['max_w'].mean():.3f} / {conc_b['max_w'].max():.3f} |")
    A(f"| จำนวนไตรมาสที่ธีมใหญ่สุด > 40% | {(conc_nc['theme_max']>0.4).sum()} | {(conc_b['theme_max']>0.4).sum()} |\n")
    A("## 10. DSR / ความเชื่อมั่น\n")
    A(f"- **DSR@21 (full) M009-NC = {dsr_nc:.4f}** · (c50 = {dsr_nc50:.4f}) · M004-TF-FX @21 (full) = {dsr_b21:.4f}")
    A(f"- CI95% Sharpe (block bootstrap) M009-NC [{ci_nc[0]:.3f}, {ci_nc[1]:.3f}] · M004-TF-FX [{ci_b[0]:.3f}, {ci_b[1]:.3f}]")
    A(f"- เทียบเป้า 0.95: M009-NC Sharpe full {g(sims_nc,'full','sharpe'):.3f} (ไม่ถึง) \n")
    A("## 11. สมมติฐาน / การตีความของ validator\n")
    for s in [
        "รัน selection 2 ชุดผ่านฟังก์ชันเดียว (`select_stream`): pen_on=False (regression) และ True (M009-NC) · logic ขั้น 1–3, ERC, cap 25%, trend cash 25%, fallback B0, hysteresis N=8/K=16 เหมือน `run_m006_m007` NEWQ ทุกบรรทัด (import ใช้ซ้ำ ไม่แก้ไฟล์เดิม)",
        "`FeeData.rate(j, code, t)` ใช้ t = วันตัดสินใจ (สิ้นไตรมาส) ตาม spec · ใช้ FeeData คนละอินสแตนซ์สำหรับการตัดสินใจ / จำลอง / diagnostics เพื่อนับ median fallback แยก",
        "pen ใช้ vol52 ของกอง rep (จาก I_t) · กองที่ถือ class เดิมได้ pen = 0 โดยเทียบ `H_map.get(family) == FundCode` (H_map = {} หลัง fallback B0)",
        "Δ หลักคำนวณบน return รายเดือนของ full-fee (เม.ย. 2022–ธ.ค. 2025, 45 เดือน) ด้วย `simulate.paired_bootstrap_diff_ci` ค่าเริ่มต้น (block 3, 2000, seed 0) — ครั้งก่อน (M006/M008) ใช้ return ที่ cost 0.5% คงที่ จึงรายงาน Δ ที่ c50 เพิ่มเป็นข้อมูลประกอบ",
        "ผลตามเกณฑ์ใช้ Δ จุด + CI ล่าง + cost bp/ปี (full) ตรงตัวที่ spec ล็อก · กรณี Δ ≥ 0 แต่ต้นทุนไม่ลดและ CI คร่อม 0: spec ไม่ได้ระบุ → ตีความเป็นไม่ผ่านเกณฑ์ใด",
        "'กองที่เข้า' = FundCode ที่มีน้ำหนัก > 0 ในไตรมาส q แต่ไม่มีในไตรมาส q−1 (นับรวมกองใน B0 fallback ถ้ามี) · FF = 0 ตรวจที่ t (วันตัดสินใจ) · ระยะถือเฉลี่ยนับเป็นไตรมาสติดต่อกัน ตัดปลายที่ไตรมาสสุดท้าย (censored)",
        "turnover/ปี = Σ ½Σ|Δw| ของ entry ที่ 2..15 ÷ ปี (ไม่รวมซื้อเข้าครั้งแรก) · cost bp/ปี รวมต้นทุนซื้อเข้าครั้งแรก (เหมือน COST_real_fees)",
        "ก่อน 2023-05 ใช้ snapshot ค่าธรรมเนียมเก่าสุด ทั้งในค่าปรับและการคิดต้นทุน (ผู้ใช้ข้อ 2) — ป้ายสมมติฐาน (มี look-ahead เล็กน้อยใน 5 ไตรมาสแรก)",
        "nofront ใช้น้ำหนักชุดเดียวกับ full (โมเดลยังตัดสินด้วย FF+BF เต็ม) ตาม spec · TER (FEEMF) ไม่ใช้ (ผู้ใช้ข้อ 4) · class FF=0 คงอยู่ใน universe (ผู้ใช้ข้อ 1)",
        "DSR = `simulate.deflated_sharpe` (หน่วยรายเดือน แก้แล้ว) ที่ n_trials = 21",
    ]:
        A(f"- {s}")
    A("\n## 12. ไฟล์\n`M009_summary_metrics.csv`, `M009_equity_curve.csv`, `M009-NC_weights.csv`, `M009_selection_log.csv` (family อันดับดิบ/สุทธิ ≤ 25 + ที่ถือ/ที่เลือก), `M009_quarter_diag.csv`, "
      "`scratch/validator_m009_regression.json`")
    open(os.path.join(RES, "M009_results.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")

    print("[7/7] trials.csv / ALL_RESULTS...", flush=True)
    append_logs(sims_nc, sims_base, res, ci_nc)
    json.dump(res, open(os.path.join(SCRATCH, "validator_m009_summary.json"), "w"), default=float)
    print(f"DONE in {time.time()-t0:.0f}s · verdict: {verdict}", flush=True)
    return 0


def append_logs(sims_nc, sims_base, res, ci_nc):
    now = pd.Timestamp.now().isoformat()
    m = sims_nc["full"]["metrics"]
    dd = res["dd"]
    note = (f"M009-NC SR12 net of FF+BF penalty on M004-TF-FX; Sharpe: 0%={sims_nc['c0']['metrics']['sharpe']:.3f} 0.5%={sims_nc['c50']['metrics']['sharpe']:.3f} "
            f"full={m['sharpe']:.3f} nofront={sims_nc['nofront']['metrics']['sharpe']:.3f}; paired dSharpe full vs M004-TF-FX {dd[2]:.3f} CI ({dd[0]:.3f};{dd[1]:.3f}); "
            f"cost bp/yr full {sims_nc['full']['cost_bp_yr']:.1f} vs {sims_base['full']['cost_bp_yr']:.1f}; CI95 ({ci_nc[0]:.3f};{ci_nc[1]:.3f}); "
            f"DSR@21(full)={res['dsr_nc']:.4f}; verdict={res['verdict']}; n_months=45 new measurement; family map F/U fix; fees snapshot oldest before 2023-05")
    params = ("M009-NC: score=SR12-pen; pen=(FF+BF)/100*(11/12)/HOLD_YRS/vol52, 0 if held class; HOLD_YRS=1; N=8;K=16;ERC;cap25%;trend cash25%;rf=2%;"
              "fee=FEEUH Actual Value full PIT;primary=2022-03..2025-12")
    vals = ["M009-NC", now, "M009_sr12_net_cost.md", params, "2022-03-31", "2025-12-31", "assumed constant 2%/yr", "real fees SecFundFee FEEUH (full)",
            round(m["sharpe"], 4), round(m["cagr"], 4), round(m["vol"], 4), round(m["max_dd"], 4),
            round(sims_nc["full"]["turn_yr"], 4), N_TRIALS, round(res["dsr_nc"], 4), "ok", note]
    line = ",".join(str(v).replace(",", ";") for v in vals)
    txt = open(TRIALS_CSV, encoding="utf-8", newline="").read()
    assert "M009-NC," not in txt, "มีแถว M009-NC แล้ว"
    with open(TRIALS_CSV, "a", encoding="utf-8", newline="") as f:
        f.write(line + "\r\n")
    g = lambda c, k: sims_nc[c]["metrics"][k]
    allv = ["M009", "M009-NC", "SR12 net of FF+BF cost penalty on M004-TF-FX", "new", "no", f"{g('c0','sharpe'):.3f}", f"{g('c50','sharpe'):.3f}",
            f"{g('c100','sharpe'):.3f}", f"{g('c50','cagr'):.3f}", f"{g('c50','vol'):.3f}", f"{g('c50','max_dd'):.3f}", f"{res['dsr_nc50']:.3f}",
            f"{g('full','sharpe'):.4f}", f"{g('nofront','sharpe'):.4f}", f"{g('full','cagr'):.4f}", f"{sims_nc['full']['cost_bp_yr']:.1f}"]
    txt = open(os.path.join(RES, "ALL_RESULTS.csv"), encoding="utf-8", newline="").read()
    assert "M009-NC," not in txt
    with open(os.path.join(RES, "ALL_RESULTS.csv"), "a", encoding="utf-8", newline="") as f:
        if not txt.endswith("\n"):
            f.write("\n")
        f.write(",".join(allv) + "\n")


if __name__ == "__main__":
    try:
        rc = main()
    except Exception:
        tb = traceback.format_exc()
        print(tb, flush=True)
        # บันทึก crashed ลง trials.csv (ไม่ลบแถวเดิม)
        try:
            txt = open(TRIALS_CSV, encoding="utf-8", newline="").read()
            if PHASE_B and "M009-NC," not in txt:
                last = tb.strip().splitlines()[-1].replace(",", ";")[:200]
                vals = ["M009-NC", pd.Timestamp.now().isoformat(), "M009_sr12_net_cost.md", "M009-NC run crashed", "2022-03-31", "2025-12-31",
                        "assumed constant 2%/yr", "real fees SecFundFee FEEUH (full)", "", "", "", "", "", N_TRIALS, "", "crashed", last]
                with open(TRIALS_CSV, "a", encoding="utf-8", newline="") as f:
                    f.write(",".join(str(v) for v in vals) + "\r\n")
        except Exception:
            pass
        rc = 1
    sys.exit(rc)
