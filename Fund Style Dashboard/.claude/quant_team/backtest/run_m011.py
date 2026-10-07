"""run_m011.py — M011-RFH: Trend 25 (M004-TF-FX) + ดอกเบี้ยนโยบายจริงใน hurdle ของ SR12 (n_trials = 23)
ตาม specs/M011_real_rf_hurdle.md · วิธีวัด = นิยาม/โค้ดของ remeasure_real_rf.py (rf จริง, ตัวหาร sd(r)) ทั้งสองแขน
รัน: PYTHONPATH=. ./.venv/bin/python .claude/quant_team/backtest/run_m011.py
(A) regression: h_t := 0.02*11/12 -> น้ำหนักเท่า M004-TF-FX_weights.csv (max|dw|<1e-9) + Sharpe 0.706119 (rf คงที่) + ตรวจ h_t/r(d)
(B) ถ้าผ่านเท่านั้น -> รัน M011 · ไม่แก้ไฟล์เดิม · reuse run_m009/remeasure_real_rf/fund_signals/weighting/fees/simulate
"""
from __future__ import annotations

import json
import os
import sys
import time
import traceback

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if THIS_DIR not in sys.path:
    sys.path.insert(0, THIS_DIR)

import numpy as np
import pandas as pd
from scipy import stats

import common
import fees
import fund_signals as fs
import simulate
import weighting as wt
import run_m009 as r9
import remeasure_real_rf as rr
from data import msci_index

TEAM_DIR = os.path.dirname(THIS_DIR)
SCRATCH = os.path.join(TEAM_DIR, "scratch")
RES = common.RESULTS_DIR
TRIALS_CSV = os.path.join(TEAM_DIR, "trials.csv")
PE = r9.PE
N_TRIALS = 23
H_OLD = fs.RF_ANNUAL_SIGNAL * 11.0 / 12.0   # 0.0183333...
PHASE_B = False
SEL_N, SEL_K = 8, 16


# ---------------- h_t ----------------
def hurdle(rate_pct: pd.Series, a: pd.Timestamp, b: pd.Timestamp) -> float:
    """h_t = Π_{d=a+1..b ทุกวันปฏิทิน}(1 + r(d)/365) − 1 · r(d) = ดอกเบี้ยนโยบายที่ announce_date < d (rate_pct = % ต่อปีรายวัน)"""
    days = pd.date_range(pd.Timestamp(a).normalize() + pd.Timedelta(days=1), pd.Timestamp(b).normalize(), freq="D")
    r = rate_pct.reindex(days).to_numpy() / 100.0
    assert not np.isnan(r).any()
    return float(np.prod(1.0 + r / 365.0) - 1.0)


def with_hurdle(ctxs, calendar, h_by_q):
    """คืนสำเนา ctxs ที่ i_t["SR12"] = (R12_1 − h_t)/vol52 (สูตรเดียวกับโค้ดเดิม · h เดียวทุกกอง)."""
    out = []
    for ctx in ctxs:
        c = dict(ctx)
        it = ctx["i_t"].copy()
        h = h_by_q[ctx["qi"]]
        it["SR12"] = (it["R12_1"] - h) / it["vol52"]
        c["i_t"] = it
        out.append(c)
    return out


# ---------------- select_at (เส้นทางเดียวกับ r9.select_stream pen=0) ----------------
def select_at(i_t, held, prev_fb):
    reps = wt.family_representatives(i_t, "SR12", held_funds=set(held.values()))
    H_map = {} if prev_fb else held
    ranks = wt.rank_families(reps)
    sel = wt.hysteresis_select(reps, ranks, H_map, SEL_N, SEL_K, None, rho_max=0.85)
    fb = sel["fallback"] == "b0" or len(sel["S"]) == 0
    return {"S": dict(sel["S"]), "fallback": fb, "reps": reps, "ranks": ranks}


def sig_of(rec):
    return "B0" if rec["fallback"] else tuple(sorted(rec["S"].values()))


def walk(ctxs):
    held, prev_fb, out = {}, False, []
    for ctx in ctxs:
        rec = select_at(ctx["i_t"], held, prev_fb)
        out.append({"held_before": dict(held), "prev_fb": prev_fb, **rec})
        held, prev_fb = ({}, True) if rec["fallback"] else (dict(rec["S"]), False)
    return out


# ---------------- plan + simulate (rf คงที่ หรือ rf จริง) ----------------
def build_plan(ctxs_mod, quarters15, calendar, acwi, fd_dec, erc_cache):
    st = r9.select_stream([c for c in ctxs_mod if c["qi"] < 15], False, fd_dec, acwi, erc_cache)
    return r9.make_plan(st["sleeves"], quarters15, calendar, acwi), st


def sims_real(plan, nav_by_fund, months, fd_sim, curve):
    with rr.cash_curve(curve):
        return r9.sim_cases(plan, nav_by_fund, months, fd_sim)


def weights_map(plan):
    return {(p["t"], f): w for p in plan for f, w in p["weights"].items() if w > 1e-12}


def max_dw(pa, pb):
    a, b = weights_map(pa), weights_map(pb)
    return max(abs(a.get(k, 0.0) - b.get(k, 0.0)) for k in set(a) | set(b)), len(set(a) ^ set(b))


# ---------------- paired bootstrap (rf จริง) — กระบวนการสุ่มเหมือน simulate.paired_bootstrap_diff_ci ----------------
def paired_real(ra, rb, rfm, denom="r", block=3, n_boot=2000, seed=0):
    a, b = ra.align(rb, join="inner")
    f = rfm.reindex(a.index).to_numpy()
    av, bv = a.to_numpy(), b.to_numpy()
    n = len(a)

    def sh(x, ff):
        sd = (x - ff).std(ddof=1) if denom == "x" else x.std(ddof=1)
        return (x - ff).mean() * 12 / (sd * np.sqrt(12)) if sd > 0 else np.nan
    point = sh(av, f) - sh(bv, f)
    rng = np.random.default_rng(seed)
    nb = int(np.ceil(n / block))
    d = []
    for _ in range(n_boot):
        idx = rng.integers(0, max(n - block, 0) + 1, size=nb)
        sel = np.concatenate([np.arange(i, i + block) for i in idx])[:n]
        x = sh(av[sel], f[sel]) - sh(bv[sel], f[sel])
        if not np.isnan(x):
            d.append(x)
    return float(np.percentile(d, 2.5)), float(np.percentile(d, 97.5)), float(point)


def sharpe_x(r, rfm):
    x = r - rfm.reindex(r.index)
    return float(x.mean() * 12 / (x.std(ddof=1) * np.sqrt(12)))


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
    quarters16 = common.quarter_ends(calendar, "2022-03-31", "2025-12-31")
    quarters15 = quarters16[:15]
    assert len(quarters16) == 16
    bound_m = quarters15[-1] + pd.Timedelta(days=75)
    months = [m for m in common.month_ends(calendar, common.execution_date(calendar, quarters15[0]), "2026-03-31")
              if m <= bound_m + pd.Timedelta(days=31)]
    assert months[-1] == PE
    fd_dec, fd_sim = fees.FeeData(codes), fees.FeeData(codes)
    real, pol = rr.load_policy()
    rate = real.rate  # % ต่อปี รายวันปฏิทิน (announce_date < d)

    print("[2/7] prepare 16 quarters...", flush=True)
    ctxs = r9.prepare(nav, nav_by_fund, calendar, groups, quarters16)

    # ---------- h_t ----------
    h_rows = []
    for ctx in ctxs:
        ms = fs.month_end_points(calendar, ctx["t"], 13)
        a, b = ms[0], ms[-2]
        h_rows.append({"qi": ctx["qi"], "t": ctx["t"], "a_M12": a, "b_M1": b, "h_t": hurdle(rate, a, b)})
    H = pd.DataFrame(h_rows)
    H["dh_pt"] = (H["h_t"] - H_OLD) * 100
    h_by_q = {r.qi: r.h_t for r in H.itertuples()}
    h_old_by_q = {q: H_OLD for q in h_by_q}
    # ค่าตรวจ §2 (สิ้นเดือนปฏิทิน) + ตัวอย่าง r(d)
    cal_chk = {}
    for dt, ref in (("2022-03-31", 0.00459), ("2024-09-30", 0.02328), ("2025-12-31", 0.01662)):
        d = pd.Timestamp(dt)
        a = (d - pd.offsets.MonthEnd(12)); b = (d - pd.offsets.MonthEnd(1))
        cal_chk[dt] = {"mine": hurdle(rate, a, b), "ref": ref}
    spot = {"2022-08-10": float(rate.loc["2022-08-10"]), "2022-08-11": float(rate.loc["2022-08-11"]), "2024-10-17": float(rate.loc["2024-10-17"])}
    spot_ok = abs(spot["2022-08-10"] - 0.50) < 1e-9 and abs(spot["2022-08-11"] - 0.75) < 1e-9 and abs(spot["2024-10-17"] - 2.25) < 1e-9
    chk_ok = all(abs(v["mine"] - v["ref"]) <= 2e-4 for v in cal_chk.values())
    print("  h_t:", [round(x, 5) for x in H["h_t"]], "· cal check", cal_chk, "· spot", spot, flush=True)

    print("[3/7] (A) regression h_t := 0.02*11/12 ...", flush=True)
    erc_cache = {}
    ctx_old = with_hurdle(ctxs, calendar, h_old_by_q)
    sig_diff_old = max(float(np.nanmax(np.abs(a["i_t"]["SR12"].to_numpy() - b["i_t"]["SR12"].to_numpy()))) for a, b in zip(ctxs, ctx_old))
    plan_base, st_base = build_plan(ctx_old, quarters15, calendar, acwi, fd_dec, erc_cache)
    sims_base_c = r9.sim_cases(plan_base, nav_by_fund, months, fd_sim)          # วัดแบบเดิม rf คงที่
    reg = r9.regression(plan_base, sims_base_c)
    # รันโค้ด wrapper เดียวกันโดยไม่แทน SR12 เลย (ctxs เดิม) = ต้องเหมือน
    plan_raw, _ = build_plan(ctxs, quarters15, calendar, acwi, fd_dec, erc_cache)
    reg["max_dw_vs_unmodified_ctx"] = max_dw(plan_raw, plan_base)[0]
    reg["max_abs_dSR12_recomputed"] = sig_diff_old
    # โค้ดวัดใหม่โหมด rf คงที่ (rr.metrics float) ต้อง 0.706119
    m_const = rr.metrics(sims_base_c["full"]["values"], 0.02)
    reg["sharpe_full_rr_const_mode"] = m_const["sharpe"]
    reg["ok_rr_const"] = bool(abs(round(m_const["sharpe"], 6) - 0.706119) < 1.5e-6)
    # โหมด rf จริงไม่ crash
    sims_base_r = sims_real(plan_base, nav_by_fund, months, fd_sim, real)
    m_real_chk = rr.metrics(sims_base_r["full"]["values"], real)
    reg["sharpe_full_realrf_baseline"] = m_real_chk["sharpe"]
    ref_real = float(pd.read_csv(os.path.join(RES, "REAL_RF_summary.csv")).set_index("trial").loc["M004-TF-FX", "sharpe_full_real"])
    reg["sharpe_full_real_ref_summary"] = ref_real
    reg["ok_real_match"] = bool(abs(m_real_chk["sharpe"] - ref_real) < 5e-7)
    reg["h_check"] = cal_chk; reg["spot_r_d"] = spot; reg["ok_h_spot"] = bool(spot_ok and chk_ok)
    reg["ok_all"] = bool(reg["ok"] and reg["ok_rr_const"] and reg["ok_real_match"] and reg["ok_h_spot"] and reg["max_dw_vs_unmodified_ctx"] < 1e-12)
    print("  REGRESSION:", json.dumps(reg, default=float), flush=True)
    json.dump(reg, open(os.path.join(SCRATCH, "validator_m011_regression.json"), "w"), default=float)
    if not reg["ok_all"]:
        print("REGRESSION FAIL — หยุด ไม่รัน M011 (ไม่นับ trial)", flush=True)
        return 2

    print("[4/7] (B) รัน M011-RFH ...", flush=True)
    global PHASE_B
    PHASE_B = True
    ctx_new = with_hurdle(ctxs, calendar, h_by_q)
    plan_new, st_new = build_plan(ctx_new, quarters15, calendar, acwi, fd_dec, erc_cache)
    sims_new_c = r9.sim_cases(plan_new, nav_by_fund, months, fd_sim)
    sims_new_r = sims_real(plan_new, nav_by_fund, months, fd_sim, real)

    print("[5/7] metrics + diagnostics...", flush=True)
    kinds = ["c0", "c50", "flat", "full", "nofront"]
    MR = {k: {"new": rr.metrics(sims_new_r[k]["values"], real), "base": rr.metrics(sims_base_r[k]["values"], real)} for k in kinds}
    MC = {k: {"new": rr.metrics(sims_new_c[k]["values"], 0.02), "base": rr.metrics(sims_base_c[k]["values"], 0.02)} for k in kinds}
    rn, rb, rfm = MR["full"]["new"]["r"], MR["full"]["base"]["r"], MR["full"]["new"]["rfm"]
    d_lo, d_hi, d_pt = paired_real(rn, rb, rfm, "r")
    dx_lo, dx_hi, dx_pt = paired_real(rn, rb, rfm, "x")
    # paired ด้วยฟังก์ชันกลาง: ส่ง x_k, rf=0 (วิธี spec §3 = ตัวหาร sd(x))
    xn, xb = rn - rfm, rb - rfm
    sx_lo, sx_hi, sx_pt = simulate.paired_bootstrap_diff_ci(xn, xb, 0.0)
    ci_n, ci_b = rr.boot_ci(rn, rfm), rr.boot_ci(rb, rfm)
    dsr_n = rr.dsr_s(rn, rfm, N_TRIALS)
    dsr_b = rr.dsr_s(rb, rfm, N_TRIALS)
    # 2 ช่วงย่อย
    def sub(r, a, b):
        m = (r.index >= a) & (r.index <= b)
        return r[m]
    d_2022 = paired_real(sub(rn, "2022-04-01", "2022-12-31"), sub(rb, "2022-04-01", "2022-12-31"), rfm, "r", n_boot=500) if False else None
    sharpe_x_new, sharpe_x_base = sharpe_x(rn, rfm), sharpe_x(rb, rfm)
    meas_only = MR["full"]["base"]["sharpe"] - 0.706119

    # --- เลือก/สัญญาณ ---
    W = walk(ctx_new)            # เส้นทาง M011 (16 ไตรมาส)
    Wb = walk(ctx_old)           # เส้นทาง Trend 25
    Wraw = walk(ctxs)
    assert all(sig_of(a) == sig_of(b) for a, b in zip(Wb, Wraw)), "walk(ctx_old) != walk(ctxs)"
    # ตรงกับ plan (15 ไตรมาสแรก)
    def plan_sets(plan):
        return [frozenset(f for f, w in p["weights"].items() if f != "__CASH__" and w > 1e-12) for p in plan]
    ps_n, ps_b = plan_sets(plan_new), plan_sets(plan_base)
    for q in range(15):
        for Wx, ps in ((W, ps_n), (Wb, ps_b)):
            if not Wx[q]["fallback"]:
                assert frozenset(Wx[q]["S"].values()) == ps[q], (q,)
    rows, n_direct, n_diff = [], 0, 0
    direct_q, inherit_q, diff_q = [], [], []
    for q in range(16):
        ctxo, ctxn = ctx_old[q], ctx_new[q]
        # ตรงๆ: SR12' + สถานะถือ/prev_fb ของ Trend 25
        dirrec = select_at(ctxn["i_t"], Wb[q]["held_before"], Wb[q]["prev_fb"])
        s_dir, s_b, s_n = sig_of(dirrec), sig_of(Wb[q]), sig_of(W[q])
        is_dir, is_diff = s_dir != s_b, s_n != s_b
        it0, it1 = ctxo["i_t"], ctxn["i_t"]
        rho = stats.spearmanr(it0["SR12"], it1["SR12"])[0] if len(it0) > 2 else np.nan
        # อันดับข้ามขอบ 8/16 (family reps ภายใต้สถานะถือของ Trend 25)
        rk0 = Wb[q]["ranks"]
        reps1 = wt.family_representatives(it1, "SR12", held_funds=set(Wb[q]["held_before"].values()))
        rk1 = wt.rank_families(reps1)
        c8 = sum(1 for f in rk0 if (rk0[f] <= 8) != (rk1[f] <= 8)) if set(rk0) == set(rk1) else np.nan
        c16 = sum(1 for f in rk0 if (rk0[f] <= 16) != (rk1[f] <= 16)) if set(rk0) == set(rk1) else np.nan
        n_cls = sum(1 for f in rk0 if f in reps1 and Wb[q]["reps"][f]["FundCode"] != reps1[f]["FundCode"])
        a_, b_ = Wb[q]["S"], dirrec["S"]
        rows.append({"qi": q, "t": ctxo["t"].date(), "in_plan15": q < 15, "h_t": h_by_q[q], "dh_pt": (h_by_q[q] - H_OLD) * 100,
                     "n_I": len(it0), "spearman_SR12": rho, "n_cross_rank8": c8, "n_cross_rank16": c16, "n_rep_class_changed": n_cls,
                     "diff_direct": is_dir, "diff_final": is_diff, "set_base": ";".join(sorted(s_b)) if s_b != "B0" else "B0",
                     "set_m011": ";".join(sorted(s_n)) if s_n != "B0" else "B0",
                     "direct_added": ";".join(sorted(set(b_.values()) - set(a_.values()))) if not (dirrec["fallback"] or Wb[q]["fallback"]) else "",
                     "direct_removed": ";".join(sorted(set(a_.values()) - set(b_.values()))) if not (dirrec["fallback"] or Wb[q]["fallback"]) else ""})
        if q < 15:
            if is_diff: diff_q.append(q)
            if is_dir: direct_q.append(q)
            if is_diff and not is_dir: inherit_q.append(q)
    QD = pd.DataFrame(rows)
    # น้ำหนักต่างไหม (ไตรมาสที่ชุดกองเหมือน)
    wa, wb_ = [p["weights"] for p in plan_new], [p["weights"] for p in plan_base]
    n_w_diff = sum(1 for a, b in zip(wa, wb_) if max(abs(a.get(k, 0) - b.get(k, 0)) for k in set(a) | set(b)) > 1e-9)
    dw_all, _ = max_dw(plan_new, plan_base)
    n_cls_chg_q = [int(r.n_rep_class_changed) for r in QD.itertuples() if r.qi < 15]

    # --- path luck: Δ ตามไตรมาส (เดือนในไตรมาสที่ชุดเหมือน vs ต่าง) ---
    es = [p["e"] for p in plan_new]
    def q_of(m):
        return max(0, int(np.searchsorted(np.array(es, dtype="datetime64[ns]"), np.datetime64(m), side="left")) - 1)
    qm = pd.Series([q_of(m) for m in rn.index], index=rn.index)
    dret = rn - rb                                # ผลต่างผลตอบแทนรายเดือน (net fee, rf จริง)
    same_mask = qm.map(lambda q: q not in diff_q)
    dsum_same, dsum_diff = float(dret[same_mask].sum()), float(dret[~same_mask].sum())
    n_m_same, n_m_diff = int(same_mask.sum()), int((~same_mask).sum())
    per_q = dret.groupby(qm).sum()
    per_q_tbl = pd.DataFrame({"sum_dret": per_q, "n_months": qm.groupby(qm).size()})
    per_q_tbl["diff_set"] = [q in diff_q for q in per_q_tbl.index]
    per_q_tbl["t"] = [quarters15[q].date() for q in per_q_tbl.index]
    best_q = int(per_q.idxmax()) if len(per_q) else None
    if diff_q:
        keep = qm != best_q
        sh_drop_n = rr.sharpe_s(rn[keep], rfm.reindex(rn.index)[keep]); sh_drop_b = rr.sharpe_s(rb[keep], rfm.reindex(rb.index)[keep])
    else:
        sh_drop_n = sh_drop_b = np.nan
    # --- พอร์ต 2025-12-31 ---
    p16_same = sig_of(W[15]) == sig_of(Wb[15])

    # --- turnover / cost ---
    def cost_row(sims, k):
        return sims[k]["cost_bp_yr"], sims[k]["turn_yr"]

    base_stats = pd.read_csv(os.path.join(RES, "REAL_RF_summary.csv")).set_index("trial")

    # ---------- เขียนไฟล์ ----------
    print("[6/7] write outputs...", flush=True)
    eq = pd.DataFrame({"M011-RFH_full_real": sims_new_r["full"]["values"], "M011-RFH_c50_real": sims_new_r["c50"]["values"],
                       "M011-RFH_c0_real": sims_new_r["c0"]["values"], "M004-TF-FX_full_real": sims_base_r["full"]["values"],
                       "M004-TF-FX_c50_real": sims_base_r["c50"]["values"], "M004-TF-FX_c0_real": sims_base_r["c0"]["values"],
                       "M011-RFH_full_rf2": sims_new_c["full"]["values"], "M004-TF-FX_full_rf2": sims_base_c["full"]["values"]})
    eq.to_csv(os.path.join(RES, "M011_equity_curve.csv"))
    wrows = [{"trial": "M011-RFH", "t": en["t"].date() if hasattr(en["t"], "date") else en["t"], "e": en["e"].date(), "kind": en["mode"],
              "FundCode": f, "weight": w} for en in sims_new_r["full"]["entries"] for f, w in en["target"].items() if w > 1e-12]
    pd.DataFrame(wrows).to_csv(os.path.join(RES, "M011-RFH_weights.csv"), index=False)
    QD.to_csv(os.path.join(RES, "M011_quarter_diag.csv"), index=False)
    per_q_tbl.to_csv(os.path.join(RES, "M011_path_luck_by_quarter.csv"))
    summ = []
    for name, sr, sc in (("M011-RFH", sims_new_r, sims_new_c), ("M004-TF-FX(rf จริง)", sims_base_r, sims_base_c)):
        for k in kinds:
            mr_, mc_ = rr.metrics(sr[k]["values"], real), rr.metrics(sc[k]["values"], 0.02)
            summ.append({"trial": name, "cost": k, "sharpe_real": mr_["sharpe"], "cagr_real": mr_["cagr"], "vol_real": mr_["vol"],
                         "maxdd_real": mr_["max_dd"], "sharpe_2022_real": mr_["sharpe_2022"], "sharpe_2307_2512_real": mr_["sharpe_2307_2512"],
                         "sharpe_rf2": mc_["sharpe"], "cagr_rf2": mc_["cagr"], "vol_rf2": mc_["vol"], "maxdd_rf2": mc_["max_dd"],
                         "cost_bp_yr_real": sr[k]["cost_bp_yr"], "turn_yr": sr[k]["turn_yr"]})
    pd.DataFrame(summ).to_csv(os.path.join(RES, "M011_results.csv"), index=False)

    f3 = lambda x: f"{x:.3f}"
    verdict = "ผ่าน (ดีกว่าอย่างมีนัย)" if (d_pt >= 0 and d_lo > 0) else ("ผ่าน" if d_pt >= 0 else "ไม่ผ่าน")
    no_effect = (len(diff_q) == 0 and n_w_diff == 0)
    if no_effect:
        verdict = "ไม่มีผล (ชุดกอง+น้ำหนักเท่า Trend 25 ทุกไตรมาส)"
    L, A = [], None
    A = L.append
    mn, mb = MR["full"]["new"], MR["full"]["base"]
    A("# M011-RFH — Trend 25 + ดอกเบี้ยนโยบายจริงใน hurdle ของ SR12 (n_trials = 23) — ผลวัด (validator)\n")
    A(f"รันเมื่อ {pd.Timestamp.now().isoformat()} · spec `specs/M011_real_rf_hurdle.md` + การตัดสินใจผู้ใช้ 2026-10-06 · primary เม.ย. 2022–2025-12-31 (45 เดือน) · "
      "วิธีวัดหลัก = rf จริง (นโยบาย ธปท.) ตามนิยาม `remeasure_real_rf.py` (ตัวหาร sd(r)) ทั้งสองแขน · ไม่มี holdout\n")
    A("## 1. Regression ก่อนรัน\n")
    A(f"- h_t := 0.02·11/12 ผ่านโค้ดเดียวกัน → น้ำหนักเทียบ `M004-TF-FX_weights.csv`: max|Δw| = {reg['max_dw']:.2e} (แถว {reg['n_rows_ref']} vs {reg['n_rows_mine']}, คีย์ฝั่งเดียว {reg['n_only_one_side']}) → **{'PASS' if reg['ok_w'] else 'FAIL'}** · "
      f"เทียบ ctx ที่ไม่แทน SR12: {reg['max_dw_vs_unmodified_ctx']:.1e} · max|ΔSR12 recomputed| = {sig_diff_old:.1e}")
    A(f"- Sharpe full/flat/nofront (rf คงที่) = {reg['sharpe']['full']:.6f}/{reg['sharpe']['flat']:.6f}/{reg['sharpe']['nofront']:.6f} (อ้างอิง 0.706119/0.720494/0.893296) → **{'PASS' if reg['ok_s'] else 'FAIL'}** · "
      f"โค้ดวัดใหม่โหมด rf คงที่ (`rr.metrics`) = {reg['sharpe_full_rr_const_mode']:.6f} → **{'PASS' if reg['ok_rr_const'] else 'FAIL'}**")
    A(f"- โหมด rf จริงไม่ crash · Trend 25 (rf จริง) Sharpe full = {reg['sharpe_full_realrf_baseline']:.6f} vs `REAL_RF_summary.csv` {ref_real:.6f} → **{'PASS' if reg['ok_real_match'] else 'FAIL'}** (ตรง 6 หลัก)")
    A(f"- r(d): 2022-08-10 = {spot['2022-08-10']:.2f}%, 2022-08-11 = {spot['2022-08-11']:.2f}%, 2024-10-17 = {spot['2024-10-17']:.2f}% · "
      "ค่าตรวจ h (สิ้นเดือนปฏิทิน): " + " · ".join(f"{k} {v['mine']:.5f} (spec ≈{v['ref']})" for k, v in cal_chk.items()) + f" → **{'PASS' if reg['ok_h_spot'] else 'FAIL'}**\n")
    A("## 2. h_t ทั้ง 16 ไตรมาส (ปฏิทินดัชนี: a=M-12, b=M-1)\n")
    A("| t | h_t | Δh (pt) | Spearman SR12~SR12′ | จำนวนกองข้ามขอบ 8 / 16 | class ตัวแทนเปลี่ยน | ชุดกองต่างตรงๆ | ชุดกองต่างจริง |")
    A("|---|---|---|---|---|---|---|---|")
    for r in QD.itertuples():
        A(f"| {r.t}{'' if r.in_plan15 else ' (หน้า 9)'} | {r.h_t:.5f} | {r.dh_pt:+.2f} | {r.spearman_SR12:.4f} | {r.n_cross_rank8} / {r.n_cross_rank16} | {r.n_rep_class_changed} | "
          f"{'ต่าง' if r.diff_direct else '-'} | {'ต่าง' if r.diff_final else '-'} |")
    A("")
    A("## 3. ตารางหลัก (ค่าธรรมเนียมจริง full, **rf จริง**, ตัวหาร sd(r))\n")
    A("| โมเดล | Sharpe | CAGR | vol | maxDD | Sharpe 2022 | Sharpe 2023-07..25 | cost bp/ปี | turnover/ปี | CI95% Sharpe | DSR@23 |")
    A("|---|---|---|---|---|---|---|---|---|---|---|")
    A(f"| **M011-RFH** | {mn['sharpe']:.3f} | {mn['cagr']:.4f} | {mn['vol']:.4f} | {mn['max_dd']:.4f} | {mn['sharpe_2022']:.3f} | {mn['sharpe_2307_2512']:.3f} | "
      f"{sims_new_r['full']['cost_bp_yr']:.1f} | {sims_new_r['full']['turn_yr']:.3f} | [{ci_n[0]:.2f}, {ci_n[1]:.2f}] | {dsr_n:.4f} |")
    A(f"| Trend 25 (rf จริง) | {mb['sharpe']:.3f} | {mb['cagr']:.4f} | {mb['vol']:.4f} | {mb['max_dd']:.4f} | {mb['sharpe_2022']:.3f} | {mb['sharpe_2307_2512']:.3f} | "
      f"{sims_base_r['full']['cost_bp_yr']:.1f} | {sims_base_r['full']['turn_yr']:.3f} | [{ci_b[0]:.2f}, {ci_b[1]:.2f}] | {dsr_b:.4f} |")
    for nm in ("M001-MS", "B0"):
        r = base_stats.loc[nm]
        A(f"| {nm} (rf จริง, `REAL_RF_summary.csv`) | {r['sharpe_full_real']:.3f} | {r['cagr_full_real']:.4f} | {r['vol_full_real']:.4f} | {r['max_dd_full_real']:.4f} | "
          f"{r['sharpe_2022_full_real']:.3f} | {r['sharpe_2307_2512_full_real']:.3f} | — | — | [{r['ci_lo_real']:.2f}, {r['ci_hi_real']:.2f}] | {r['dsr22_real']:.4f} (@22) |")
    A(f"\n(ค่าอ้างอิงเดิมที่ rf 2%: B0 0.060 · M001-MS 0.105 · Trend 25 0.706119)\n")
    A("## 4. ตัวชี้วัดหลัก + เกณฑ์ (ล็อกล่วงหน้า)\n")
    A(f"- **Δ Sharpe_full (M011 − Trend 25, rf จริง) = {d_pt:+.4f}** · CI95% paired block bootstrap (block 3, 2000, seed 0) **[{d_lo:+.3f}, {d_hi:+.3f}]** "
      f"({'คร่อม 0' if d_lo <= 0 <= d_hi else 'ไม่คร่อม 0'}) · ตัวหาร sd(r) ตามนิยาม remeasure")
    A(f"- ตัวหาร sd(x) (spec §3 ข้อความ, รายงานคู่): Sharpe M011 {sharpe_x_new:.4f} vs Trend 25 {sharpe_x_base:.4f} → Δ {sx_pt:+.4f} CI [{sx_lo:+.3f}, {sx_hi:+.3f}] (ผ่าน `simulate.paired_bootstrap_diff_ci` ส่ง x, rf=0)")
    A(f"- **ผลตามเกณฑ์: {verdict}** (ไม่ตัดสินแทนผู้ใช้ — ผู้ใช้ตัดสินล่วงหน้าแล้วว่า Δ<0 เล็กน้อยก็ใช้ rf จริงต่อด้วยเหตุผลเชิงนิยาม)")
    A(f"- ผลของวิธีวัดอย่างเดียว (ไม่ใช่ trial): Trend 25 rf จริง {mb['sharpe']:.6f} − 0.706119 = {meas_only:+.4f}\n")
    A("## 5. ชุดกองต่างจาก Trend 25 (15 ไตรมาสในแผน)\n")
    A(f"- ต่างจริง **{len(diff_q)}/15**: {', '.join(str(quarters15[q].date()) for q in diff_q) or '-'}")
    A(f"- ต่างตรงๆ (select ด้วย SR12′ + สถานะถือของ Trend 25) **{len(direct_q)}/15**: {', '.join(str(quarters15[q].date()) for q in direct_q) or '-'}")
    A(f"- สืบทอดผ่าน hysteresis **{len(inherit_q)}/15**: {', '.join(str(quarters15[q].date()) for q in inherit_q) or '-'}")
    A(f"- ไตรมาสที่น้ำหนัก (ทั้ง plan รวมเงินสด) ต่างจาก Trend 25 > 1e-9: {n_w_diff}/15 · max|Δw| ทั้งช่วง {dw_all:.3f}")
    A(f"- พอร์ต 2025-12-31 (หน้า 9, ไตรมาสที่ 16): ชุดกอง {'เหมือน' if p16_same else 'ต่าง'} Trend 25 · ต่างตรงๆ: {'ต่าง' if QD.iloc[15]['diff_direct'] else 'เหมือน'}")
    if diff_q:
        for q in diff_q:
            r = QD.iloc[q]
            A(f"  - {r['t']}: Trend25={r['set_base']} | M011={r['set_m011']} | เพิ่มตรงๆ [{r['direct_added']}] ตัดตรงๆ [{r['direct_removed']}]")
    A("")
    A("## 6. Δ path luck\n")
    A(f"- ผลต่างผลตอบแทนรายเดือนสะสม (Σ(r_M011 − r_T25), net fee): เดือนในไตรมาสที่ชุดกอง**เหมือน** {dsum_same:+.4f} ({n_m_same} เดือน) · **ต่าง** {dsum_diff:+.4f} ({n_m_diff} เดือน)")
    if diff_q:
        A(f"- ไตรมาสที่ผลต่างบวกมากสุด: {quarters15[best_q].date()} → ตัดไตรมาสนี้ออก (drop-best-quarter): Sharpe M011 {sh_drop_n:.3f} vs T25 {sh_drop_b:.3f} Δ {sh_drop_n - sh_drop_b:+.3f}")
        A("\n| ไตรมาส t | Σ Δr เดือนในไตรมาส | ชุดกองต่าง |\n|---|---|---|")
        for r in per_q_tbl.itertuples():
            A(f"| {r.t} | {r.sum_dret:+.4f} | {'ต่าง' if r.diff_set else 'เหมือน'} |")
    A("")
    A("## 7. ตารางต้นทุน (rf จริง; M011 / Trend 25)\n")
    A("| ต้นทุน | M011 Sharpe | M011 CAGR | M011 vol | M011 maxDD | T25 Sharpe | T25 CAGR | T25 vol | T25 maxDD |")
    A("|---|---|---|---|---|---|---|---|---|")
    lab = {"c0": "0%", "c50": "0.5%/ข้าง", "flat": "flat 0.5% (fee model)", "full": "ค่าธรรมเนียมจริง full", "nofront": "nofront"}
    for k in kinds:
        a, b = MR[k]["new"], MR[k]["base"]
        A(f"| {lab[k]} | {a['sharpe']:.3f} | {a['cagr']:.4f} | {a['vol']:.4f} | {a['max_dd']:.4f} | {b['sharpe']:.3f} | {b['cagr']:.4f} | {b['vol']:.4f} | {b['max_dd']:.4f} |")
    A(f"\n- รายงานคู่ M011 ที่วัดด้วย rf คงที่ 2% แบบเดิม: full {MC['full']['new']['sharpe']:.4f} (T25 0.706119) · c0 {MC['c0']['new']['sharpe']:.3f} · c50 {MC['c50']['new']['sharpe']:.3f} · nofront {MC['nofront']['new']['sharpe']:.3f}")
    A(f"- rf จริงเฉลี่ย (ทบรายเดือน×12) = {mn['rf_ann_avg']*100:.3f}%/ปี · cost bp/ปี c50: M011 {sims_new_r['c50']['cost_bp_yr']:.1f} vs T25 {sims_base_r['c50']['cost_bp_yr']:.1f}\n")
    A("## 8. สมมติฐาน / ที่ validator ตีความเอง\n")
    for s in [
        "วิธีวัด: ใช้ `remeasure_real_rf.py` ทั้งหมด (RFCurve/`cash_curve`/`metrics`/`dsr_s`/`boot_ci`) — **ตัวหาร Sharpe = sd(r)** (ไม่ใช่ sd(x) ตามข้อความ spec §3; ผู้ใช้สั่งใช้นิยาม remeasure และ baseline 0.719) · เพิ่มรายงานคู่ sd(x) · "
        "ปัจจัยรายวันของเงินสด/rf = (1+r)^(1/365) ตาม remeasure (spec §3 เขียน 1+r/365 — ต่างระดับ r²/730 ต่อวัน ≈ 1e-6/ปี ไม่มีนัย)",
        "h_t ใช้สูตร spec §2 ตรงตัว: ทบ (1 + r(d)/365) รายวันปฏิทิน d = a+1..b โดย r(d) = นโยบายที่ announce_date < d (ใช้ `rr.load_policy().rate` ซึ่งมีผลวันถัดจากประกาศ) · a=ctx.months[0], b=ctx.months[-2] จาก `fs.month_end_points` (ปฏิทิน NAV)",
        "แทน SR12 ใน `i_t` ด้วย (R12_1 − h_t)/vol52 ก่อนส่งเข้า `r9.select_stream` (pen=0) · SR12 ถูกอ่านใน repo เฉพาะ `family_representatives` (เลือก class ตัวแทน) และ `rank_families` (ผ่าน reps) → ใช้ SR12′ ทั้งคู่ · class ตัวแทนอาจเปลี่ยนได้ (นับเป็น 'class ตัวแทนเปลี่ยน')",
        "'ต่างตรงๆ' = `select_at` ด้วย SR12′ แต่ใช้ held/prev_fb ของ Trend 25 ณ t เทียบชุดกองของ Trend 25 ณ t · 'ต่างจริง' = ชุดกองใน plan เทียบ plan Trend 25 · สืบทอด = ต่างจริงแต่ไม่ต่างตรงๆ · เทียบเฉพาะชุด FundCode (เงินสด trend เหมือนกัน)",
        "พอร์ต 2025-12-31 (ไตรมาสที่ 16) ไม่อยู่ใน 45 เดือนที่วัดและไม่นับใน 15 ไตรมาส",
        "Δ paired CI: เขียนซ้ำกระบวนการสุ่มของ `simulate.paired_bootstrap_diff_ci` (rng seed 0, block 3, 2000) แต่ใช้ sd(r) และ rf รายเดือนจริงที่ resample ตาม index เดียวกัน (ฟังก์ชันกลางรับ rf เดี่ยว) · รายงานคู่ผ่านฟังก์ชันกลางด้วย x, rf=0 (sd(x))",
        "DSR@23 = `rr.dsr_s` (สูตรเดียวกับ `simulate.deflated_sharpe` แบบ excess=r−rf_k) ที่ n_trials=23 · ค่าในแถว trials.csv/ALL_RESULTS ของ M011 บันทึก Sharpe full ที่ **rf จริง** (ระบุใน rf_source) ต่างจากแถวก่อนหน้าที่เป็น rf 2% — โปรดระวังเทียบข้ามแถว",
        "ต้นทุน/ค่าธรรมเนียม/trend filter/ERC/เพดาน/ตารางเวลาเหมือน M009/M010 ทุกบรรทัด (import `run_m009`)",
    ]:
        A(f"- {s}")
    A("\n## 9. ไฟล์\n`M011_results.csv`, `M011_equity_curve.csv`, `M011-RFH_weights.csv`, `M011_quarter_diag.csv`, `M011_path_luck_by_quarter.csv`, `scratch/validator_m011_regression.json`")
    open(os.path.join(RES, "M011_results.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")

    res = {"verdict": verdict, "d": (d_lo, d_hi, d_pt), "dx": (sx_lo, sx_hi, sx_pt), "n_diff": len(diff_q), "n_direct": len(direct_q),
           "n_inherit": len(inherit_q), "dsr": dsr_n, "ci_n": ci_n, "ci_b": ci_b, "meas_only": meas_only,
           "sharpe": {k: MR[k]["new"]["sharpe"] for k in kinds}, "sharpe_base": {k: MR[k]["base"]["sharpe"] for k in kinds},
           "sharpe_rf2": {k: MC[k]["new"]["sharpe"] for k in kinds}, "p16_same": p16_same, "no_effect": no_effect,
           "dsum_same": dsum_same, "dsum_diff": dsum_diff, "drop_best": (sh_drop_n, sh_drop_b)}
    json.dump(res, open(os.path.join(SCRATCH, "validator_m011_summary.json"), "w"), default=float)

    print("[7/7] trials.csv / ALL_RESULTS...", flush=True)
    append_logs(sims_new_r, sims_new_c, sims_base_r, MR, MC, res, mn, ci_n)
    print(f"DONE in {time.time()-t0:.0f}s · verdict: {verdict} · dSharpe {d_pt:+.4f} [{d_lo:+.3f},{d_hi:+.3f}] · diff quarters {len(diff_q)}", flush=True)
    return 0


def append_logs(sims_new_r, sims_new_c, sims_base_r, MR, MC, res, mn, ci_n):
    now = pd.Timestamp.now().isoformat()
    d = res["d"]
    note = (f"M011-RFH Trend 25 + real policy-rate hurdle in SR12; Sharpe (real rf, sd(r)): 0%={MR['c0']['new']['sharpe']:.3f} 0.5%={MR['c50']['new']['sharpe']:.3f} "
            f"full={mn['sharpe']:.3f} nofront={MR['nofront']['new']['sharpe']:.3f}; rf2 full={MC['full']['new']['sharpe']:.4f}; "
            f"paired dSharpe full vs Trend25(real rf {MR['full']['base']['sharpe']:.4f}) {d[2]:.4f} CI ({d[0]:.3f};{d[1]:.3f}); "
            f"quarters set differs {res['n_diff']}/15 (direct {res['n_direct']} inherited {res['n_inherit']}); CI95 ({ci_n[0]:.3f};{ci_n[1]:.3f}); "
            f"DSR@23={res['dsr']:.4f}; verdict={res['verdict']}; n_months=45; sharpe column = REAL rf not 2%")
    params = ("M011-RFH: SR12'=(R12_1-h_t)/vol52; h_t=prod(1+r(d)/365)-1 over (M-12,M-1] r=BOT policy announce<d; N=8;K=16;ERC LW;cap25%;trend cash25%;"
              "measure=real policy rf (cash+Sharpe); fee=FEEUH full PIT;primary=2022-03..2025-12")
    m = mn
    vals = ["M011-RFH", now, "M011_real_rf_hurdle.md", params, "2022-03-31", "2025-12-31", "BOT policy rate daily (TH_POLICY_RATE.csv)",
            "real fees SecFundFee FEEUH (full)", round(m["sharpe"], 4), round(m["cagr"], 4), round(m["vol"], 4), round(m["max_dd"], 4),
            round(sims_new_r["full"]["turn_yr"], 4), N_TRIALS, round(res["dsr"], 4), "ok", note]
    line = ",".join(str(v).replace(",", ";") for v in vals)
    txt = open(TRIALS_CSV, encoding="utf-8", newline="").read()
    assert "M011-RFH," not in txt, "มีแถว M011-RFH แล้ว"
    with open(TRIALS_CSV, "a", encoding="utf-8", newline="") as f:
        if not txt.endswith("\n"):
            f.write("\r\n")
        f.write(line + "\r\n")
    g = lambda c, k: MC[c]["new"][k]
    allv = ["M011", "M011-RFH", "Trend 25 + real policy-rate hurdle in SR12 (measured with real rf)", "new", "no",
            f"{MC['c0']['new']['sharpe']:.3f}", f"{MC['c50']['new']['sharpe']:.3f}", "", f"{g('c50','cagr'):.3f}", f"{g('c50','vol'):.3f}", f"{g('c50','max_dd'):.3f}", "",
            f"{MC['full']['new']['sharpe']:.4f}", f"{MC['nofront']['new']['sharpe']:.4f}", f"{g('full','cagr'):.4f}", f"{sims_new_c['full']['cost_bp_yr']:.1f}",
            f"{MR['full']['new']['sharpe']:.4f}", f"{MR['nofront']['new']['sharpe']:.4f}", f"{MR['flat']['new']['sharpe']:.4f}", f"{MR['c0']['new']['sharpe']:.4f}",
            f"{MR['full']['new']['cagr']:.4f}", f"{MR['full']['new']['max_dd']:.4f}", f"{MR['full']['new']['sharpe_2022']:.4f}", f"{res['dsr']:.4f}"]
    p = os.path.join(RES, "ALL_RESULTS.csv")
    txt = open(p, encoding="utf-8", newline="").read()
    assert "M011-RFH," not in txt
    ncol = len(txt.splitlines()[0].split(","))
    assert len(allv) == ncol, (len(allv), ncol)
    with open(p, "a", encoding="utf-8", newline="") as f:
        if not txt.endswith("\n"):
            f.write("\n")
        f.write(",".join(allv) + "\n")
    # ALL_RESULTS.md: เพิ่มบรรทัดสรุป (ไม่แก้ส่วนเดิม)
    mdp = os.path.join(RES, "ALL_RESULTS.md")
    with open(mdp, "a", encoding="utf-8") as f:
        f.write(f"\n## M011-RFH (เพิ่ม {pd.Timestamp.now().date()}, trial ที่ 23)\n"
                f"- Trend 25 + hurdle ใน SR12 = ดอกเบี้ยนโยบายจริง · วัดด้วย rf จริง (คอลัมน์ `*_realrf`) · แถวใน `ALL_RESULTS.csv`: คอลัมน์ rf 2% = วัดแบบเดิม (rf คงที่), คอลัมน์ `realrf` = วัดด้วย rf จริง, "
                f"`dsr_n22_fee_full_realrf` ของแถวนี้ = DSR@23\n"
                f"- Sharpe full (rf จริง) M011 {MR['full']['new']['sharpe']:.3f} vs Trend 25 {MR['full']['base']['sharpe']:.3f} · Δ {d[2]:+.4f} CI [{d[0]:+.3f}, {d[1]:+.3f}] · "
                f"ชุดกองต่าง {res['n_diff']}/15 ไตรมาส · ผล: {res['verdict']} · รายละเอียด `M011_results.md`\n")


if __name__ == "__main__":
    try:
        rc = main()
    except Exception:
        tb = traceback.format_exc()
        print(tb, flush=True)
        try:
            txt = open(TRIALS_CSV, encoding="utf-8", newline="").read()
            if PHASE_B and "M011-RFH," not in txt:
                last = tb.strip().splitlines()[-1].replace(",", ";")[:200]
                vals = ["M011-RFH", pd.Timestamp.now().isoformat(), "M011_real_rf_hurdle.md", "M011-RFH run crashed", "2022-03-31", "2025-12-31",
                        "BOT policy rate daily (TH_POLICY_RATE.csv)", "real fees SecFundFee FEEUH (full)", "", "", "", "", "", N_TRIALS, "", "crashed", last]
                with open(TRIALS_CSV, "a", encoding="utf-8", newline="") as f:
                    f.write(",".join(str(v) for v in vals) + "\r\n")
        except Exception:
            pass
        rc = 1
    sys.exit(rc)
