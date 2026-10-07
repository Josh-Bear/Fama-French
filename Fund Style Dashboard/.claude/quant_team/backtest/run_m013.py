"""run_m013.py — M013 สัดส่วนหุ้นไล่ระดับรายไตรมาส (ACWI 3/6/12 เดือน > rf จริง) แทน Trend 25 · บน M012-QF-S · 2 trials: GC75 (26), GC80 (27)
ตาม specs/M013_graded_cash_q.md + "การตัดสินใจของผู้ใช้ 2026-10-06" · วัดด้วย rf จริง (remeasure_real_rf.py, ตัวหาร sd(r)) แบบเดียวกับ M011/M012
รัน: PYTHONPATH=. ./.venv/bin/python .claude/quant_team/backtest/run_m013.py
(A) regression: cash_fn = trend_filter_cash(0.25) ผ่านโค้ดใหม่ -> น้ำหนัก = M012_weights.csv (M012-QF-S, full) · Sharpe ตรง M012_results.csv · k_t ตรงตาราง spec §2 · ถ้าไม่ผ่านหยุด (ไม่นับ trial)
(B) ถ้าผ่าน -> GC75 / GC80 · ไม่แก้ไฟล์เดิม · reuse run_m012/run_m011/run_m009/run_m006_m007/remeasure_real_rf
ไฟล์นี้ยังมี helper กลาง (setup, baseline, log) ที่ run_m014.py import ใช้ซ้ำ
"""
from __future__ import annotations

import json
import os
import pickle
import sys
import time
import traceback

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
import run_m009 as r9
import run_m011 as r11
import run_m012 as r12
import remeasure_real_rf as rr
from data import msci_index

TEAM_DIR = os.path.dirname(THIS_DIR)
PROJECT = os.path.dirname(os.path.dirname(TEAM_DIR))
SCRATCH = os.path.join(TEAM_DIR, "scratch")
RES = common.RESULTS_DIR
TRIALS_CSV = os.path.join(TEAM_DIR, "trials.csv")
N_TRIALS_FINAL = 29
KINDS = ["c0", "c50", "flat", "full", "nofront"]
KIND_LAB = {"c0": "0%", "c50": "0.5%/ข้าง", "flat": "flat 0.5% (fee model)", "full": "ค่าธรรมเนียมจริง full", "nofront": "nofront"}
EXPECT_K = [1, 0, 0, 1, 2, 3, 2, 3, 3, 3, 1, 2, 1, 3, 3, 2]       # spec §2
TABLES = {"GC75": {3: 1.00, 2: 0.75, 1: 0.50, 0: 0.25}, "GC80": {3: 1.00, 2: 0.80, 1: 0.60, 0: 0.40}}
PHASE_B = False


# ====================== helper กลาง (ใช้ซ้ำใน run_m014) ======================
def setup():
    E = {}
    nav = common.load_nav()
    E["nav"] = nav
    E["nav_by_fund"] = common.build_nav_by_fund(nav)
    E["calendar"] = common.load_calendar()
    E["groups"] = common.load_groups()
    E["acwi"] = msci_index.load_country_index()["MSCI_ACWI"]
    E["codes"] = sorted(nav["FundCode"].unique())
    q16 = common.quarter_ends(E["calendar"], "2022-03-31", "2025-12-31")
    assert len(q16) == 16
    E["q16"], E["q15"] = q16, q16[:15]
    bound_m = E["q15"][-1] + pd.Timedelta(days=75)
    months = [m for m in common.month_ends(E["calendar"], common.execution_date(E["calendar"], E["q15"][0]), "2026-03-31")
              if m <= bound_m + pd.Timedelta(days=31)]
    assert months[-1] == r11.PE
    E["months"] = months
    E["fd_sim"] = fees.FeeData(E["codes"])
    real, _ = rr.load_policy()
    E["real"], E["rate"] = real, real.rate
    pk = os.path.join(SCRATCH, "validator_m012_ctxs.pkl")           # cache ที่ M012 สร้าง (ctx point-in-time 16 ไตรมาส)
    if os.path.exists(pk):
        ctxs = pickle.load(open(pk, "rb"))
    else:
        ctxs = r9.prepare(E["nav"], E["nav_by_fund"], E["calendar"], E["groups"], q16)
        pickle.dump(ctxs, open(pk, "wb"))
    h_by_q = {}
    for ctx in ctxs:
        ms = fs.month_end_points(E["calendar"], ctx["t"], 13)
        h_by_q[ctx["qi"]] = r11.hurdle(E["rate"], ms[0], ms[-2])
    E["ctx_h"] = r11.with_hurdle(ctxs, E["calendar"], h_by_q)
    Q = r12.Quality(nav, E["groups"])
    E["Q"] = Q
    E["quals"] = [Q.table(c["t"])[0] for c in E["ctx_h"]]
    return E


def baseline(E):
    """M012-QF-S ผ่านโค้ด r12 เดิม (stream mode S) -> sleeves, plan (Trend 25), sims."""
    erc_cache = {}
    st = r12.stream(E["ctx_h"], E["quals"], "S", erc_cache)
    plan = r12.to_plan(st, E["q15"], E["calendar"], E["acwi"])
    sims_r = r11.sims_real(plan, E["nav_by_fund"], E["months"], E["fd_sim"], E["real"])
    sims_c = r9.sim_cases(plan, E["nav_by_fund"], E["months"], E["fd_sim"])
    return {"st": st, "plan": plan, "sims_r": sims_r, "sims_c": sims_c, "erc_cache": erc_cache}


def ref_weights():
    ref = pd.read_csv(os.path.join(RES, "M012_weights.csv"))
    ref = ref[(ref["trial"] == "M012-QF-S") & (ref["kind"] == "full")]
    return {(pd.Timestamp(r.t), r.FundCode): r.weight for r in ref.itertuples()}


def reg_vs_m012s(plan):
    refd = ref_weights()
    mine = r11.weights_map(plan)
    keys = set(refd) | set(mine)
    dmax = max(abs(refd.get(k, 0.0) - mine.get(k, 0.0)) for k in keys)
    only = [k for k in keys if (k in refd) != (k in mine)]
    rs = pd.read_csv(os.path.join(RES, "M012_results.csv")).set_index(["trial", "cost"])
    return float(dmax), len(only), len(refd), len(mine), rs


def sharpes_vs_ref(sims_r, real, rs):
    sh = {k: rr.metrics(sims_r[k]["values"], real)["sharpe"] for k in KINDS}
    ref = {k: float(rs.loc[("M012-QF-S", k), "sharpe_real"]) for k in KINDS}
    return sh, ref, all(abs(sh[k] - ref[k]) < 5e-7 for k in KINDS)


def plan_sum_check(plan, tol=1e-9):
    for p in plan:
        s = sum(p["weights"].values())
        assert abs(s - 1.0) < tol, (p["t"], s)
        assert all(v >= -1e-15 for v in p["weights"].values())


def mdd_2022(values):
    v = values[values.index <= pd.Timestamp("2022-12-31")]
    return float(simulate.max_drawdown(v))


def bundle(sims_r, sims_c, real):
    MR = {k: rr.metrics(sims_r[k]["values"], real) for k in KINDS}
    MC = {k: rr.metrics(sims_c[k]["values"], 0.02) for k in KINDS}
    return MR, MC


def qdelta(rn, rb, rfm, plan, quarters15):
    """Σ Δr ต่อไตรมาส + drop-best-quarter (นิยามเดียวกับ r12)."""
    es = np.array([p["e"] for p in plan], dtype="datetime64[ns]")
    qm = pd.Series([max(0, int(np.searchsorted(es, np.datetime64(m), side="left")) - 1) for m in rn.index], index=rn.index)
    dret = rn - rb
    per_q = dret.groupby(qm).sum()
    best_q = int(per_q.idxmax())
    worst_q = int(per_q.idxmin())
    keep = qm != best_q
    sh_n = rr.sharpe_s(rn[keep], rfm.reindex(rn.index)[keep])
    sh_b = rr.sharpe_s(rb[keep], rfm.reindex(rb.index)[keep])
    tab = pd.DataFrame({"t": [quarters15[q].date() for q in per_q.index], "sum_dret": per_q.to_numpy(), "n_months": qm.groupby(qm).size().to_numpy()}, index=per_q.index)
    return {"tab": tab, "best_q": best_q, "worst_q": worst_q, "drop": (float(sh_n), float(sh_b)), "qm": qm}


def entry_stats(sims_r_full, quarters15):
    """ต่อ entry: เงินสดเป้าหมาย, ต้นทุน, turnover (full fee model)."""
    rows = []
    for i, en in enumerate(sims_r_full["entries"]):
        cash = float(en["target"].get("__CASH__", 0.0))
        nf = sum(1 for f, w in en["target"].items() if f != "__CASH__" and w > 1e-12)
        rows.append({"qi": i, "t": quarters15[i].date(), "cash": cash, "stock": 1.0 - cash, "n_funds": nf, "cost": float(en["cost"]), "turnover": float(en["turnover"])})
    return pd.DataFrame(rows)


def main_row(name, m, so, ci, dsr):
    return (f"| **{name}** | {m['sharpe']:.3f} | {m['cagr']:.4f} | {m['vol']:.4f} | {m['max_dd']:.4f} | {mdd_2022(so['values']):.4f} | {m['sharpe_2022']:.3f} | "
            f"{m['sharpe_2307_2512']:.3f} | {so['cost_bp_yr']:.1f} | {so['turn_yr']:.3f} | [{ci[0]:.2f}, {ci[1]:.2f}] | {dsr:.4f} |")


MAIN_HDR = ["| โมเดล | Sharpe | CAGR | vol | maxDD | maxDD ช่วง 2022 | Sharpe 2022 | Sharpe 2023-07..25 | cost bp/ปี | turnover/ปี | CI95% Sharpe | DSR@29 |",
            "|---|---|---|---|---|---|---|---|---|---|---|---|"]


def b0_row(L):
    r = pd.read_csv(os.path.join(RES, "REAL_RF_summary.csv")).set_index("trial").loc["B0"]
    L.append(f"| B0 (rf จริง, `REAL_RF_summary.csv`, ไม่ได้ตรวจซ้ำเอง) | {r['sharpe_full_real']:.3f} | {r['cagr_full_real']:.4f} | {r['vol_full_real']:.4f} | {r['max_dd_full_real']:.4f} | — | "
             f"{r['sharpe_2022_full_real']:.3f} | {r['sharpe_2307_2512_full_real']:.3f} | — | — | [{r['ci_lo_real']:.2f}, {r['ci_hi_real']:.2f}] | — |")


def context_rows(L, names):
    st = pd.read_csv(os.path.join(RES, "REAL_RF_summary.csv")).set_index("trial")
    for n in names:
        r = st.loc[n]
        L.append(f"| {n} (บริบท, วัดต่างกัน: ไฟล์ผลเดิม rf จริง ไม่ได้ตรวจซ้ำเอง) | {r['sharpe_full_real']:.3f} | {r['cagr_full_real']:.4f} | {r['vol_full_real']:.4f} | {r['max_dd_full_real']:.4f} | — | "
                 f"{r['sharpe_2022_full_real']:.3f} | {r['sharpe_2307_2512_full_real']:.3f} | — | — | [{r['ci_lo_real']:.2f}, {r['ci_hi_real']:.2f}] | — |")


def log_trial(name, n, spec_file, params, MR, MC, sims_r, sims_c, ci, dsr, d, verdict, idea, note_extra):
    """เพิ่ม 1 แถวใน trials.csv + ALL_RESULTS.csv (ไม่ลบ/ไม่แก้แถวเดิม · สำรองไฟล์ไว้แล้วก่อนรัน)."""
    now = pd.Timestamp.now().isoformat()
    txt = open(TRIALS_CSV, encoding="utf-8", newline="").read()
    assert f"\n{name}," not in "\n" + txt, f"{name} มีใน trials.csv แล้ว"
    mn = MR["full"]
    so = sims_r["full"]
    note = (f"{name} POST-HOC LABEL: see spec; Sharpe (real rf; sd(r)): 0%={MR['c0']['sharpe']:.3f} 0.5%={MR['c50']['sharpe']:.3f} full={mn['sharpe']:.3f} nofront={MR['nofront']['sharpe']:.3f}; "
            f"rf2 full={MC['full']['sharpe']:.4f}; paired dSharpe full vs M012-QF-S {d[2]:+.4f} CI ({d[0]:.3f};{d[1]:.3f}); CI95 ({ci[0]:.3f};{ci[1]:.3f}); "
            f"DSR@{N_TRIALS_FINAL}={dsr:.4f}; verdict={verdict}; {note_extra}; n_months=45; sharpe column = REAL rf not 2%; deflated_sharpe column = DSR@{N_TRIALS_FINAL}")
    vals = [name, now, spec_file, params, "2022-03-31", "2025-12-31", "BOT policy rate daily (TH_POLICY_RATE.csv)",
            "real fees SecFundFee FEEUH (full)", round(mn["sharpe"], 4), round(mn["cagr"], 4), round(mn["vol"], 4), round(mn["max_dd"], 4),
            round(so["turn_yr"], 4), n, round(dsr, 4), "ok", note]
    line = ",".join(str(v).replace(",", ";").replace("\n", " ") for v in vals)
    with open(TRIALS_CSV, "a", encoding="utf-8", newline="") as f:
        if not txt.endswith("\n"):
            f.write("\r\n")
        f.write(line + "\r\n")
    p = os.path.join(RES, "ALL_RESULTS.csv")
    atxt = open(p, encoding="utf-8", newline="").read()
    assert f",{name}," not in atxt
    ncol = len(atxt.splitlines()[0].split(","))
    g = lambda c, k: MC[c][k]
    rnd = name.split("-")[0]
    allv = [rnd, name, idea.replace(",", ";"), "new", "yes", f"{MC['c0']['sharpe']:.3f}", f"{MC['c50']['sharpe']:.3f}", "", f"{g('c50','cagr'):.3f}", f"{g('c50','vol'):.3f}",
            f"{g('c50','max_dd'):.3f}", "", f"{MC['full']['sharpe']:.4f}", f"{MC['nofront']['sharpe']:.4f}", f"{g('full','cagr'):.4f}", f"{sims_c['full']['cost_bp_yr']:.1f}",
            f"{MR['full']['sharpe']:.4f}", f"{MR['nofront']['sharpe']:.4f}", f"{MR['flat']['sharpe']:.4f}", f"{MR['c0']['sharpe']:.4f}",
            f"{MR['full']['cagr']:.4f}", f"{MR['full']['max_dd']:.4f}", f"{MR['full']['sharpe_2022']:.4f}", f"{dsr:.4f}"]
    assert len(allv) == ncol, (len(allv), ncol)
    with open(p, "a", encoding="utf-8", newline="") as f:
        if not atxt.endswith("\n"):
            f.write("\n")
        f.write(",".join(allv) + "\n")


def log_crash(names_n, spec_file, msg):
    for name, n in names_n:
        txt = open(TRIALS_CSV, encoding="utf-8", newline="").read()
        if f"\n{name}," in "\n" + txt:
            continue
        vals = [name, pd.Timestamp.now().isoformat(), spec_file, f"{name} run crashed", "2022-03-31", "2025-12-31", "BOT policy rate daily (TH_POLICY_RATE.csv)",
                "real fees SecFundFee FEEUH (full)", "", "", "", "", "", n, "", "crashed", msg]
        with open(TRIALS_CSV, "a", encoding="utf-8", newline="") as f:
            if not txt.endswith("\n"):
                f.write("\r\n")
            f.write(",".join(str(v).replace(",", ";") for v in vals) + "\r\n")


# ====================== M013 เฉพาะ ======================
def acwi_level(acwi, d):
    s = acwi.loc[:d]
    assert s.index.max() <= d
    return float(s.iloc[-1])


def gc_signals(E):
    rows = []
    for qi, t in enumerate(E["q16"]):
        ms = fs.month_end_points(E["calendar"], t, 13)
        assert ms[-1] == t, (t, ms[-1])
        a_t = acwi_level(E["acwi"], t)
        r = {"qi": qi, "t": t}
        k = 0
        for L in (3, 6, 12):
            lag = ms[-1 - L]
            assert lag < t
            R = a_t / acwi_level(E["acwi"], lag) - 1.0
            h = r11.hurdle(E["rate"], lag, t)
            s = int(R > h)
            r[f"R{L}"], r[f"rf{L}"], r[f"s{L}"] = R, h, s
            k += s
        r["k"] = k
        r["sma200_below"] = bool(wt.trend_filter_cash(E["acwi"], t, 0.25) > 0)
        rows.append(r)
    return pd.DataFrame(rows)


def gc_plan(E, sleeves, kmap, table):
    xmap = {t: table[kmap[t]] for t in E["q16"]}
    plan = r67.old_style_plan(sleeves, E["q15"], E["calendar"], lambda t: 1.0 - xmap[t])
    plan_sum_check(plan)
    return plan, xmap


def main():
    t0 = time.time()
    print("[1/7] setup...", flush=True)
    E = setup()
    print("[2/7] baseline M012-QF-S + regression...", flush=True)
    B = baseline(E)
    sleeves15 = {q: v for q, v in B["st"]["sleeves"].items() if q < 15}
    assert len(sleeves15) == 15
    n_fb = sum(1 for r in B["st"]["recs"][:15] if r["fallback"])
    # regression 1: cash_fn = trend_filter_cash ผ่าน old_style_plan โดยตรง (ไม่ผ่าน r9.make_plan)
    plan_rg = r67.old_style_plan(sleeves15, E["q15"], E["calendar"], lambda t: wt.trend_filter_cash(E["acwi"], t, 0.25))
    plan_sum_check(plan_rg)
    sims_rg = r11.sims_real(plan_rg, E["nav_by_fund"], E["months"], E["fd_sim"], E["real"])
    dmax, nonly, nref, nmine, rs = reg_vs_m012s(plan_rg)
    sh, shref, ok_s = sharpes_vs_ref(sims_rg, E["real"], rs)
    sig = gc_signals(E)
    ok_k = list(sig["k"]) == EXPECT_K
    reg = {"max_dw": dmax, "n_only": nonly, "n_ref": nref, "n_mine": nmine, "sharpe": sh, "sharpe_ref": shref, "ok_w": bool(dmax < 1e-9 and nonly == 0), "ok_s": bool(ok_s),
           "k_t": list(map(int, sig["k"])), "ok_k": bool(ok_k), "n_fb_base": n_fb,
           "sleeves_ok": bool(all(abs(sleeves15[q].sum() - 1.0) < 1e-9 for q in sleeves15))}
    reg["ok_all"] = bool(reg["ok_w"] and reg["ok_s"] and reg["ok_k"] and reg["sleeves_ok"])
    print("  REGRESSION:", json.dumps(reg, default=float), flush=True)
    json.dump(reg, open(os.path.join(SCRATCH, "validator_m013_regression.json"), "w"), default=float)
    if not reg["ok_all"]:
        print("REGRESSION FAIL — หยุด (ไม่นับ trial)", flush=True)
        return 2

    print("[3/7] รัน GC75 / GC80...", flush=True)
    real = E["real"]
    MRb, MCb = bundle(B["sims_r"], B["sims_c"], real)
    rb, rfm = MRb["full"]["r"], MRb["full"]["rfm"]
    ci_b = rr.boot_ci(rb, rfm)
    dsr_b = rr.dsr_s(rb, rfm, N_TRIALS_FINAL)
    kmap = dict(zip(sig["t"], sig["k"]))
    ARM = {}
    for tag, table in TABLES.items():
        plan, xmap = gc_plan(E, sleeves15, kmap, table)
        sims_r = r11.sims_real(plan, E["nav_by_fund"], E["months"], E["fd_sim"], real)
        sims_c = r9.sim_cases(plan, E["nav_by_fund"], E["months"], E["fd_sim"])
        MR, MC = bundle(sims_r, sims_c, real)
        rn = MR["full"]["r"]
        d = r11.paired_real(rn, rb, rfm, "r")
        ci = rr.boot_ci(rn, rfm)
        dsr = rr.dsr_s(rn, rfm, N_TRIALS_FINAL)
        qd = qdelta(rn, rb, rfm, plan, E["q15"])
        es = entry_stats(sims_r["full"], E["q15"])
        ARM[tag] = {"plan": plan, "xmap": xmap, "sims_r": sims_r, "sims_c": sims_c, "MR": MR, "MC": MC, "d": d, "ci": ci, "dsr": dsr, "qd": qd, "es": es,
                    "verdict": "ผ่าน (ดีกว่าอย่างมีนัย)" if (d[2] >= 0 and d[0] > 0) else ("ผ่าน" if d[2] >= 0 else "ไม่ผ่าน")}
        print(f"  {tag}: Δ {d[2]:+.4f} [{d[0]:+.3f},{d[1]:+.3f}] full={MR['full']['sharpe']:.4f} avg stock {es['stock'].mean():.3f}", flush=True)
    d_gc = r11.paired_real(ARM["GC80"]["MR"]["full"]["r"], ARM["GC75"]["MR"]["full"]["r"], rfm, "r")
    base_es = entry_stats(B["sims_r"]["full"], E["q15"])

    print("[4/7] write outputs...", flush=True)
    eqd = {"M012-QF-S_full_real": B["sims_r"]["full"]["values"], "M012-QF-S_c0_real": B["sims_r"]["c0"]["values"]}
    for tag in ARM:
        eqd[f"M013-{tag}_full_real"] = ARM[tag]["sims_r"]["full"]["values"]
        eqd[f"M013-{tag}_c0_real"] = ARM[tag]["sims_r"]["c0"]["values"]
    pd.DataFrame(eqd).to_csv(os.path.join(RES, "M013_equity_curve.csv"))
    wrows = []
    for tag in ARM:
        for en in ARM[tag]["sims_r"]["full"]["entries"]:
            for f, w in en["target"].items():
                if w > 1e-12:
                    wrows.append({"trial": f"M013-{tag}", "t": en["t"].date(), "e": en["e"].date(), "kind": en["mode"], "FundCode": f, "weight": w})
    pd.DataFrame(wrows).to_csv(os.path.join(RES, "M013_weights.csv"), index=False)
    sig_out = sig.copy()
    sig_out["x_GC75"] = [TABLES["GC75"][k] for k in sig["k"]]
    sig_out["x_GC80"] = [TABLES["GC80"][k] for k in sig["k"]]
    sig_out.to_csv(os.path.join(RES, "M013_signals.csv"), index=False)
    summ = []
    for name, MRx, sr, MCx, sc in (("M012-QF-S", MRb, B["sims_r"], MCb, B["sims_c"]),
                                   ("M013-GC75", ARM["GC75"]["MR"], ARM["GC75"]["sims_r"], ARM["GC75"]["MC"], ARM["GC75"]["sims_c"]),
                                   ("M013-GC80", ARM["GC80"]["MR"], ARM["GC80"]["sims_r"], ARM["GC80"]["MC"], ARM["GC80"]["sims_c"])):
        for k in KINDS:
            summ.append({"trial": name, "cost": k, "sharpe_real": MRx[k]["sharpe"], "cagr_real": MRx[k]["cagr"], "vol_real": MRx[k]["vol"], "maxdd_real": MRx[k]["max_dd"],
                         "maxdd_2022_real": mdd_2022(sr[k]["values"]), "sharpe_2022_real": MRx[k]["sharpe_2022"], "sharpe_2307_2512_real": MRx[k]["sharpe_2307_2512"],
                         "sharpe_rf2": MCx[k]["sharpe"], "cost_bp_yr_real": sr[k]["cost_bp_yr"], "turn_yr": sr[k]["turn_yr"]})
    pd.DataFrame(summ).to_csv(os.path.join(RES, "M013_results.csv"), index=False)
    write_md(E, reg, sig, B, MRb, ci_b, dsr_b, ARM, d_gc, base_es)

    print("[5/7] trials.csv / ALL_RESULTS...", flush=True)
    global PHASE_B
    PHASE_B = True
    for tag, n in (("GC75", 26), ("GC80", 27)):
        x = ARM[tag]
        tb = "x_t=" + "/".join(f"{k}:{v:.2f}" for k, v in sorted(TABLES[tag].items(), reverse=True))
        params = (f"M013-{tag}: M012-QF-S sleeves; stock share x_t by k_t=#(ACWI R_L>rf_L real, L=3/6/12m) {tb}; cash=1-x_t quarterly only; N=8;K=16;ERC LW;cap25%;"
                  f"measure=real policy rf; fee=FEEUH full PIT;primary=2022-03..2025-12; POST-HOC partly (quarterly freq chosen after TCQ>TC; relative of TCQ)")
        log_trial(f"M013-{tag}", n, "M013_graded_cash_q.md", params, x["MR"], x["MC"], x["sims_r"], x["sims_c"], x["ci"], x["dsr"], x["d"], x["verdict"],
                  f"M012-QF-S + graded stock share by ACWI 3/6/12m>rf ({tag}) quarterly (POST-HOC partly) (measured with real rf)",
                  f"avg stock {x['es']['stock'].mean():.3f}; POST-HOC partly label")
    with open(os.path.join(RES, "ALL_RESULTS.md"), "a", encoding="utf-8") as f:
        a, b = ARM["GC75"], ARM["GC80"]
        f.write(f"\n## M013-GC75 / M013-GC80 (เพิ่ม {pd.Timestamp.now().date()}, trial ที่ 26 และ 27 · ⚠️ post-hoc บางส่วน: ความถี่รายไตรมาสเลือกหลังเห็น TCQ > TC)\n"
                f"- M012-QF-S + สัดส่วนหุ้นไล่ระดับ x_t (ACWI 3/6/12 เดือน > rf จริง): GC75 = 100/75/50/25%, GC80 = 100/80/60/40% · **วัดด้วย rf จริง** "
                f"(คอลัมน์ `*_realrf`, `dsr_n22_fee_full_realrf` ของแถวนี้ = DSR@29)\n"
                f"- Sharpe full (rf จริง): M012-QF-S {MRb['full']['sharpe']:.3f} · GC75 {a['MR']['full']['sharpe']:.3f} (Δ {a['d'][2]:+.4f} CI [{a['d'][0]:+.3f}, {a['d'][1]:+.3f}] · {a['verdict']}) · "
                f"GC80 {b['MR']['full']['sharpe']:.3f} (Δ {b['d'][2]:+.4f} CI [{b['d'][0]:+.3f}, {b['d'][1]:+.3f}] · {b['verdict']}) · รายละเอียด `M013_results.md`\n")
    print(f"DONE in {time.time()-t0:.0f}s", flush=True)
    return 0


def write_md(E, reg, sig, B, MRb, ci_b, dsr_b, ARM, d_gc, base_es):
    L = []
    A = L.append
    mb = MRb["full"]
    A("# M013 — สัดส่วนหุ้นไล่ระดับรายไตรมาส (ACWI 3/6/12 เดือน > rf จริง) บน M012-QF-S — ผลวัด (validator)\n")
    A(f"รันเมื่อ {pd.Timestamp.now().isoformat()} · spec `specs/M013_graded_cash_q.md` + การตัดสินใจผู้ใช้ 2026-10-06 (GC75 = trial 26, GC80 = trial 27 · ถ้าผ่านทั้งคู่ผู้ใช้เลือก GC75 ล่วงหน้า) · "
      "primary เม.ย. 2022–2025-12-31 (45 เดือน) · วัดด้วย **rf จริง** (นโยบาย ธปท., `remeasure_real_rf.py`, ตัวหาร sd(r)) ทุกแขน · baseline = M012-QF-S (วัดซ้ำในรันนี้ ตรง `M012_results.csv`) · ไม่มี holdout\n")
    A("> ⚠️ **POST-HOC บางส่วน**: ความถี่รายไตรมาสถูกเลือกหลังเห็น M006-TCQ (0.905) > M006-TC รายเดือน (0.645) และ GC75/GC80 เป็นญาติใกล้ของ TCQ → หลักฐานอ่อน แม้ผ่านเกณฑ์ · DSR ใช้ n = 29 (รวม M013×2, M014×2)\n")
    A("## 1. Regression (ก่อนรันจริง)\n")
    A(f"- cash_fn = `trend_filter_cash(ACWI, t, 0.25)` ผ่าน `r67.old_style_plan` (sleeves จาก `r12.stream` mode S) เทียบ `M012_weights.csv` (M012-QF-S, full): max|Δw| = {reg['max_dw']:.2e} "
      f"(แถว {reg['n_ref']} vs {reg['n_mine']}, คีย์ฝั่งเดียว {reg['n_only']}) → **{'PASS' if reg['ok_w'] else 'FAIL'}**")
    A(f"- Sharpe c0/c50/flat/full/nofront ตรง `M012_results.csv` (< 5e-7) → **{'PASS' if reg['ok_s'] else 'FAIL'}** (full {reg['sharpe']['full']:.6f} vs {reg['sharpe_ref']['full']:.6f})")
    A(f"- k_t ทั้ง 16 ไตรมาสตรงตาราง spec §2 → **{'PASS' if reg['ok_k'] else 'FAIL'}** · sleeves Σ = 1 ทุกไตรมาส {'✓' if reg['sleeves_ok'] else '✗'} · ไตรมาสตก fallback B0 ของ M012-QF-S (ใน 15) = {reg['n_fb_base']} · ทุก entry Σกอง + __CASH__ = 1 (assert) · A(d)/rf_L ใช้ข้อมูล ≤ d (assert)\n")
    A("## 2. ตารางหลัก (ค่าธรรมเนียมจริง full, rf จริง, ตัวหาร sd(r))\n")
    L.extend(MAIN_HDR)
    for tag in ARM:
        A(main_row(f"M013-{tag}", ARM[tag]["MR"]["full"], ARM[tag]["sims_r"]["full"], ARM[tag]["ci"], ARM[tag]["dsr"]))
    A(main_row("M012-QF-S (baseline)", mb, B["sims_r"]["full"], ci_b, dsr_b))
    b0_row(L)
    context_rows(L, ["M006-TCQ", "M001-MS"])
    A("\nmaxDD ช่วง 2022 = max drawdown ของ equity curve ตั้งแต่ 2022-04-04 ถึง 2022-12-31 (full fee, rf จริง)\n")
    A("## 3. ตัวชี้วัดหลัก + เกณฑ์ (ล็อก: ผ่าน = Δ Sharpe full ≥ 0 · ไม่ผ่าน = คง M012-QF-S · รายงานทั้งคู่ ไม่เลือกตัวที่ดีกว่า)\n")
    for tag in ARM:
        d = ARM[tag]["d"]
        A(f"- **{tag}: Δ Sharpe_full (M013-{tag} − M012-QF-S) = {d[2]:+.4f}** · CI95% paired block bootstrap (block 3, 2000, seed 0) [{d[0]:+.3f}, {d[1]:+.3f}] "
          f"({'คร่อม 0' if d[0] <= 0 <= d[1] else 'ไม่คร่อม 0'}) · **ผลตามเกณฑ์: {ARM[tag]['verdict']}**")
    A(f"- Δ (GC80 − GC75) paired = {d_gc[2]:+.4f} CI [{d_gc[0]:+.3f}, {d_gc[1]:+.3f}] (ต่างกันแค่ระดับ · ไม่ใช้เลือกตัวชนะ)")
    both = all(ARM[t]["d"][2] >= 0 for t in ARM)
    A(f"- กฎผู้ใช้ล่วงหน้า: ถ้าผ่านทั้งคู่ → ใช้ GC75 · ผลจริง: {'ผ่านทั้งคู่' if both else 'ไม่ผ่านทั้งคู่/ผ่านบางตัว (กฎไม่ถูกเรียกใช้เต็ม)'}\n")
    A("## 4. ตารางต้นทุน (rf จริง)\n")
    A("| ต้นทุน | GC75 Sharpe | CAGR | vol | maxDD | GC80 Sharpe | CAGR | vol | maxDD | M012-QF-S Sharpe | CAGR | vol | maxDD |")
    A("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for k in KINDS:
        a, b, c = ARM["GC75"]["MR"][k], ARM["GC80"]["MR"][k], MRb[k]
        A(f"| {KIND_LAB[k]} | {a['sharpe']:.3f} | {a['cagr']:.4f} | {a['vol']:.4f} | {a['max_dd']:.4f} | {b['sharpe']:.3f} | {b['cagr']:.4f} | {b['vol']:.4f} | {b['max_dd']:.4f} | "
          f"{c['sharpe']:.3f} | {c['cagr']:.4f} | {c['vol']:.4f} | {c['max_dd']:.4f} |")
    A("")
    A("## 5. สัดส่วนหุ้น/เงินสดต่อไตรมาส + ต้นทุนต่อ entry (full fee)\n")
    A("| t | R3 (rf3) | R6 (rf6) | R12 (rf12) | k | x GC75 | x GC80 | เงินสด GC75 | ต้นทุน GC75 | ต้นทุน GC80 | ต้นทุน M012-QF-S | ACWI<SMA200 (trend เดิม) |")
    A("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for r in sig.itertuples():
        i = r.qi
        inplan = i < 15
        c75 = ARM["GC75"]["es"]["cost"].iloc[i] * 100 if inplan else np.nan
        c80 = ARM["GC80"]["es"]["cost"].iloc[i] * 100 if inplan else np.nan
        cb = base_es["cost"].iloc[i] * 100 if inplan else np.nan
        f = lambda v: "—" if v != v else f"{v:.2f}%"
        A(f"| {r.t.date()}{'' if inplan else ' (หน้า 9)'} | {r.R3:+.3f} ({r.rf3:.4f}){'✓' if r.s3 else ''} | {r.R6:+.3f} ({r.rf6:.4f}){'✓' if r.s6 else ''} | {r.R12:+.3f} ({r.rf12:.4f}){'✓' if r.s12 else ''} | "
          f"{r.k} | {TABLES['GC75'][r.k]:.2f} | {TABLES['GC80'][r.k]:.2f} | {1-TABLES['GC75'][r.k]:.2f} | {f(c75)} | {f(c80)} | {f(cb)} | {'✓' if r.sma200_below else ''} |")
    A("")
    for tag in ARM:
        es = ARM[tag]["es"]
        xs = [ARM[tag]["xmap"][t] for t in E["q15"]]
        ups = [i for i in range(1, 15) if xs[i] > xs[i - 1] + 1e-12]
        dns = [i for i in range(1, 15) if xs[i] < xs[i - 1] - 1e-12]
        yrs = ARM[tag]["sims_r"]["full"]["cost_bp_yr"] / max(ARM[tag]["sims_r"]["full"]["cost_bp_yr"], 1e-12)
        so = ARM[tag]["sims_r"]["full"]
        yrs = (r11.PE - ARM[tag]["plan"][0]["e"]).days / 365.25
        cost_up = es["cost"].iloc[ups].sum() / yrs * 1e4 if ups else 0.0
        cost_nonup = (es["cost"].sum() - es["cost"].iloc[ups].sum()) / yrs * 1e4
        A(f"- **{tag}**: หุ้นเฉลี่ย (เป้าหมาย 15 entry) {es['stock'].mean():.3f} · ต่ำสุด {es['stock'].min():.2f} · เงินสดเฉลี่ย {es['cash'].mean():.3f} · M012-QF-S หุ้นเฉลี่ย {base_es['stock'].mean():.3f} · "
          f"x เพิ่ม {len(ups)} ครั้ง / ลด {len(dns)} ครั้ง · ต้นทุนรวม {so['cost_bp_yr']:.1f} bp/ปี (M012-QF-S {B['sims_r']['full']['cost_bp_yr']:.1f}; ส่วนต่าง {so['cost_bp_yr']-B['sims_r']['full']['cost_bp_yr']:+.1f}) "
          f"· ต้นทุนใน entry ที่ x เพิ่ม (≈ ค่าธรรมเนียมขาเข้าจากการเพิ่มหุ้น + สลับกอง) {cost_up:.1f} bp/ปี · entry อื่น {cost_nonup:.1f} bp/ปี · turnover/ปี {so['turn_yr']:.3f} (M012-QF-S {B['sims_r']['full']['turn_yr']:.3f})")
    A("")
    A("## 6. Δ ต่อไตรมาส (Σ Δr รายเดือนในไตรมาส, GC − M012-QF-S) + drop-best-quarter\n")
    A("| ไตรมาส t | k | Σ Δr GC75 | Σ Δr GC80 |")
    A("|---|---|---|---|")
    t75, t80 = ARM["GC75"]["qd"]["tab"], ARM["GC80"]["qd"]["tab"]
    for q in t75.index:
        A(f"| {t75.loc[q,'t']} | {int(sig['k'].iloc[q])} | {t75.loc[q,'sum_dret']:+.4f} | {t80.loc[q,'sum_dret']:+.4f} |")
    A("")
    for tag in ARM:
        qd = ARM[tag]["qd"]
        A(f"- **{tag}**: ตัดไตรมาสที่ผลต่างบวกสุด ({E['q15'][qd['best_q']].date()}) → Sharpe GC {qd['drop'][0]:.3f} vs M012-QF-S {qd['drop'][1]:.3f} Δ {qd['drop'][0]-qd['drop'][1]:+.3f} · ไตรมาสลบสุด {E['q15'][qd['worst_q']].date()}")
    A("")
    A("## 7. สมมติฐาน / ที่ validator ตีความเอง\n")
    for s in [
        "sleeve ทุกไตรมาส = M012-QF-S (เรียก `r12.stream(..., 'S')` ตัวเดียวกัน) → Δ = overlay เงินสดล้วน ไม่มี path luck ของการคัดกอง · GC ไม่มี entry mode scale (ไม่ปรับกลางไตรมาส)",
        "k_t: A(d) = ค่า MSCI_ACWI (THB) ล่าสุด ≤ d (assert) · ms = `fs.month_end_points(calendar, t, 13)` (ms[-1] = t) · R_L = A(t)/A(ms[-1-L]) − 1 · rf_L = `r11.hurdle(rate, ms[-1-L], t)` · s_L = R_L > rf_L แบบเข้มงวด ใช้ float ตรงๆ ไม่ปัด",
        "plan: `r67.old_style_plan` กับ cash_fn = 1 − x_t (สูตร (1−c)·w + __CASH__ = c) · ตกลงตาม spec ว่าไตรมาส fallback B0 (ไม่มีใน 15 ไตรมาสนี้) จะใช้ x_t กับ B0 เหมือนกัน",
        "ต้นทุน: ขาเงินสดไม่มีต้นทุน · การเพิ่มหุ้นในกองที่ถืออยู่ใช้ค่าธรรมเนียมขาเข้าตาม FeeModel (full) · 'ต้นทุนใน entry ที่ x เพิ่ม' เป็นการประมาณการแยกต้นทุน (ไม่ใช่ counterfactual เต็ม เพราะ entry เดียวกันมีทั้งการสลับกอง)",
        "Δ paired CI: `r11.paired_real` (block 3, 2000, seed 0, rf จริงรายเดือน, ตัวหาร sd(r)) · DSR = `rr.dsr_s` n = 29 · maxDD 2022 คำนวณจาก equity ถึง 2022-12-31",
        "เงินสด = ดอกเบี้ยนโยบายแบบ step ไม่หักค่าธรรมเนียมกองตลาดเงิน (~0.2–0.4%) → เงินสดดูดีเกินจริงเล็กน้อย กระทบ M013 มากกว่า baseline · n ขาลง = 1 (2022) → ใช้พิสูจน์ไม่ได้",
        "พอร์ต 2025-12-31 (ไตรมาสที่ 16) ไม่อยู่ใน 45 เดือนที่วัด (แสดง k/x ในตารางเพื่ออ้างอิงหน้า 9)",
    ]:
        A(f"- {s}")
    A("\n## 8. ไฟล์\n`M013_results.csv`, `M013_equity_curve.csv`, `M013_weights.csv`, `M013_signals.csv`, `scratch/validator_m013_regression.json`, `scratch/validator_m013_run.log`")
    open(os.path.join(RES, "M013_results.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")


if __name__ == "__main__":
    try:
        rc = main()
    except Exception:
        tb = traceback.format_exc()
        print(tb, flush=True)
        try:
            if PHASE_B:
                log_crash((("M013-GC75", 26), ("M013-GC80", 27)), "M013_graded_cash_q.md", tb.strip().splitlines()[-1].replace(",", ";")[:200])
        except Exception:
            pass
        rc = 1
    sys.exit(rc)
