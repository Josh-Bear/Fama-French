"""run_m016.py — M016-CW (trial #33): M012-QF-S + N=5/K=10 + น้ำหนัก ∝ max(SR12',0) + เพดาน 35% · specs/M016_concentrated_scoreweight.md
universe เต็ม · rf จริง · FeeData(legacy=False) · reuse robust_offsets.setup_env_off / run_m012 (Quality, to_plan) / run_m011 / run_m015.sim_cases_x
(A) regression: stream_cw(N=8,K=16,ERC,cap25%) == r12.stream("S") ทุก sleeve + Sharpe full M012-QF-S 0.659648 + Trend25 0.719313 -> ไม่ผ่าน = หยุด
(B) M016-CW offset 0 (full/nofront/flat/c0) + offset 1/2 (ช่วงร่วม 42 เดือน, วิธี ROBUST_offsets) + log trials.csv (สำรองก่อน)
รัน: PYTHONPATH=. ./.venv/bin/python .claude/quant_team/backtest/run_m016.py
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import time
import traceback

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if THIS_DIR not in sys.path:
    sys.path.insert(0, THIS_DIR)

import numpy as np
import pandas as pd

import common
import weighting as wt
import run_m011 as r11
import run_m012 as r12
import remeasure_real_rf as rr
import robust_offsets as ro

TEAM_DIR = os.path.dirname(THIS_DIR)
SCRATCH = os.path.join(TEAM_DIR, "scratch")
RES = common.RESULTS_DIR
TRIALS_CSV = os.path.join(TEAM_DIR, "trials.csv")
NAME, N_TRIAL = "M016-CW", 33
N_SEL, K_SEL, CAP = 5, 10, 0.35
TARGET_CAGR, DD_FLOOR = 0.0909, -0.20
CTX = {0: os.path.join(SCRATCH, "validator_m012_ctxs.pkl"),
       1: os.path.join(SCRATCH, "validator_full_ctxs_off1.pkl"),
       2: os.path.join(SCRATCH, "validator_full_ctxs_off2.pkl")}
KINDS = ["full", "nofront", "flat", "c0"]
PHASE_B = False


# ---------------- weighting ----------------
def score_weights(funds, reps, S, ctx, cap=CAP):
    """w ∝ max(SR12',0) ของกองที่เลือก · ทุกตัว ≤ 0 (หรือ NaN) -> equal · แล้ว wt.apply_cap(cap). คืน (w, used_equal)."""
    fam_of = {fc: f for f, fc in S.items()}
    s = pd.Series([reps[fam_of[fc]]["signal"] for fc in funds], index=funds, dtype=float).fillna(0.0).clip(lower=0.0)
    eq = bool(s.sum() <= 0)
    w = pd.Series(1.0 / len(funds), index=funds) if eq else s / s.sum()
    return wt.apply_cap(w, cap), eq


def erc_weights_cap25(funds, reps, S, ctx):
    w, _ = wt.risk_parity_weights(funds, ctx["wk"], ctx["vol_map"], method="erc")
    return wt.apply_cap(w, 0.25), False


# ---------------- selection stream (M012-QF-S path, N/K/weigher เป็นพารามิเตอร์) ----------------
def stream_cw(ctxs, quals, n_sel, k_sel, weigher, held_positive_only):
    held, prev_fb = {}, False
    sleeves, recs = {}, []
    for ctx in ctxs:
        qi, i_t = ctx["qi"], ctx["i_t"]
        q = quals[qi]
        fam_ok = set(q.index[q["pass_q1"] & q["pass_q2"]])
        it = i_t[i_t["family"].isin(fam_ok)]
        H_map = {} if prev_fb else held
        reps = wt.family_representatives(it, "SR12", held_funds=set(held.values()))
        ranks = wt.rank_families(reps)
        sel = wt.hysteresis_select(reps, ranks, H_map, n_sel, k_sel, None, rho_max=0.85)
        fb = sel["fallback"] == "b0" or len(sel["S"]) == 0
        rec = {"qi": qi, "t": ctx["t"], "fallback": fb, "S": dict(sel["S"]), "n_kept": sel["n_kept"], "eq_fallback": False}
        if fb:
            held, prev_fb = {}, True
            sleeves[qi] = ctx["b0_w"]
            recs.append(rec)
            continue
        funds = list(sel["S"].values())
        w, eq = weigher(funds, reps, sel["S"], ctx)
        rec["eq_fallback"] = eq
        rec["scores"] = {fc: float(reps[f]["signal"]) for f, fc in sel["S"].items()}
        sleeves[qi] = w
        if held_positive_only:
            held = {f: fc for f, fc in sel["S"].items() if w.get(fc, 0.0) > 1e-12}
        else:
            held = dict(sel["S"])
        prev_fb = False
        recs.append(rec)
    return {"sleeves": sleeves, "recs": recs}


def plan_from(st, E):
    return r12.to_plan(st, E["q15"], E["calendar"], E["acwi"])


def sim(plan, E, kinds):
    return ro.sims_for("B", plan, E, None, kinds)       # = r15.sim_cases_x กับ FeeData ของ E (กองหุ้นล้วน)


def yearly(r):
    return ((1 + r).groupby(r.index.year).prod() - 1).to_dict()


def plan_diag(plan, st):
    rows = []
    for p, rec in zip(plan, st["recs"]):
        w = {f: v for f, v in p["weights"].items() if f != "__CASH__" and v > 1e-12}
        cash = float(p["weights"].get("__CASH__", 0.0))
        eqw = (1.0 - cash)
        top = max(w, key=w.get)
        rows.append({"t": p["t"].date(), "fallback_B0": rec["fallback"], "eq_fallback": rec.get("eq_fallback", False), "n_funds_held": len(w), "cash": cash,
                     "max_w_total": w[top], "max_w_equity_sleeve": w[top] / eqw if eqw > 0 else np.nan, "top_fund": top,
                     "n_selected": 0 if rec["fallback"] else len(rec["S"]),
                     "n_selected_score_le0": 0 if rec["fallback"] else int(sum(1 for v in rec.get("scores", {}).values() if not (v > 0))),
                     "holdings": ";".join(f"{f}:{v:.3f}" for f, v in sorted(w.items(), key=lambda kv: -kv[1]))})
    return pd.DataFrame(rows)


def quarter_returns(r, plan):
    es = np.array([p["e"] for p in plan], dtype="datetime64[ns]")
    qm = [max(0, int(np.searchsorted(es, np.datetime64(m), side="left")) - 1) for m in r.index]
    return (1 + r).groupby(qm).prod() - 1


# ---------------- main ----------------
def main():
    global PHASE_B
    t0 = time.time()
    envs, P, S, ST = {}, {}, {}, {}
    for k in ro.OFFSETS:
        E = ro.setup_env_off(k, set(), CTX[k])
        envs[k] = E
        ctx15 = [c for c in E["ctx_h"] if c["qi"] < 15]
        st_cw = stream_cw(ctx15, E["quals"], N_SEL, K_SEL, score_weights, True)
        st_s = r12.stream(ctx15, E["quals"], "S", {})
        ST[k] = {"M016-CW": st_cw, "M012-QF-S": st_s}
        P[k] = {"M016-CW": plan_from(st_cw, E), "M012-QF-S": r12.to_plan(st_s, E["q15"], E["calendar"], E["acwi"]),
                "Trend25": r11.build_plan(E["ctx_old"], E["q15"], E["calendar"], E["acwi"], E["fd_dec"], {})[0]}
        if k == 0:
            st_reg = stream_cw(ctx15, E["quals"], 8, 16, erc_weights_cap25, False)
            ST[0]["REG"] = st_reg
        kinds = KINDS if k == 0 else ["full", "c0"]
        S[k] = {m: sim(P[k][m], E, kinds) for m in P[k]}
        print(f"[off{k}] done ({time.time()-t0:.0f}s) t0={E['q15'][0].date()}", flush=True)
    E0, real = envs[0], envs[0]["real"]

    # ---------- (A) regression ----------
    a, b = ST[0]["REG"]["sleeves"], ST[0]["M012-QF-S"]["sleeves"]
    sl_ok = all(set(a[q].index) == set(b[q].index) and np.allclose(a[q].sort_index().to_numpy(), b[q].sort_index().to_numpy(), atol=1e-12)
                for q in range(15))
    ref12 = float(pd.read_csv(os.path.join(RES, "M012_results.csv")).set_index(["trial", "cost"]).loc[("M012-QF-S", "full"), "sharpe_real"])
    ref_t = float(pd.read_csv(os.path.join(RES, "REAL_RF_summary.csv")).set_index("trial").loc["M004-TF-FX", "sharpe_full_real"])
    got12 = rr.metrics(S[0]["M012-QF-S"]["full"]["values"], real)["sharpe"]
    gott = rr.metrics(S[0]["Trend25"]["full"]["values"], real)["sharpe"]
    reg = {"sleeves_N8K16ERC_eq_M012S": bool(sl_ok), "M012S_full": got12, "M012S_ref": ref12, "Trend25_full": gott, "Trend25_ref": ref_t}
    reg["ok"] = bool(sl_ok and abs(got12 - ref12) < 5e-7 and abs(gott - ref_t) < 5e-7)
    print("REGRESSION:", json.dumps(reg), flush=True)
    json.dump(reg, open(os.path.join(SCRATCH, "validator_m016_regression.json"), "w"))
    if not reg["ok"]:
        print("REGRESSION FAIL — หยุด (ไม่นับ trial)", flush=True)
        return 2
    PHASE_B = True

    # ---------- (B) offset 0 fee cases ----------
    names = ["M016-CW", "M012-QF-S", "Trend25"]
    rows, MR = [], {}
    for m in names:
        for kind in KINDS:
            x = rr.metrics(S[0][m][kind]["values"], real)
            MR[(m, kind)] = x
            lo, hi = rr.boot_ci(x["r"], x["rfm"])
            yr = yearly(x["r"])
            rows.append({"model": m, "fee": kind, "sharpe": x["sharpe"], "cagr": x["cagr"], "vol": x["vol"], "max_dd": x["max_dd"],
                         "cost_pct_yr": S[0][m][kind]["cost_bp_yr"] / 100.0, "turn_yr": S[0][m][kind]["turn_yr"],
                         "dsr33": rr.dsr_s(x["r"], x["rfm"], N_TRIAL), "ci_lo": lo, "ci_hi": hi,
                         "sharpe_2022": x["sharpe_2022"], "sharpe_2307_2512": x["sharpe_2307_2512"], "n_months": x["n_months"],
                         **{f"ret_{y}": yr.get(y, np.nan) for y in (2022, 2023, 2024, 2025)}})
    R = pd.DataFrame(rows)
    R.to_csv(os.path.join(RES, "M016_results.csv"), index=False)
    pr = []
    for other in ("Trend25", "M012-QF-S"):
        for kind in ("full", "nofront", "flat"):
            lo, hi, pt = r11.paired_real(MR[("M016-CW", kind)]["r"], MR[(other, kind)]["r"], MR[("M016-CW", kind)]["rfm"], "r")
            pr.append({"vs": other, "fee": kind, "d_sharpe": pt, "ci_lo": lo, "ci_hi": hi,
                       "d_cagr": MR[("M016-CW", kind)]["cagr"] - MR[(other, kind)]["cagr"]})
    PR = pd.DataFrame(pr)
    PR.to_csv(os.path.join(RES, "M016_paired.csv"), index=False)

    # ---------- offsets ----------
    orow = []
    for m in names:
        for k in ro.OFFSETS:
            w = ro.win_metrics(S[k][m]["full"]["values"], real)
            wc = ro.win_metrics(S[k][m]["c0"]["values"], real)
            o = rr.metrics(S[k][m]["full"]["values"], real)
            orow.append({"model": m, "offset": k, "sharpe": w["sharpe"], "cagr": w["cagr"], "vol": w["vol"], "max_dd": w["max_dd"], "n_months": w["n_months"],
                         "sharpe_c0": wc["sharpe"], "cost_pct_yr": S[k][m]["full"]["cost_bp_yr"] / 100.0, "turn_yr": S[k][m]["full"]["turn_yr"],
                         "sharpe_origwin": o["sharpe"], "cagr_origwin": o["cagr"], "maxdd_origwin": o["max_dd"], "n_months_origwin": o["n_months"]})
    OF = pd.DataFrame(orow)
    OF.to_csv(os.path.join(RES, "M016_offsets.csv"), index=False)
    # Trend25 offsets ต้องตรงกับ FULLUNIV_offsets.csv (B)
    fu = pd.read_csv(os.path.join(RES, "FULLUNIV_offsets.csv"))
    fu = fu[(fu["model"] == "B") & (fu["offset"].isin(["0", "1", "2"]))].set_index("offset")
    off_reg = max(abs(float(fu.loc[str(k), "sharpe"]) - float(OF[(OF.model == "Trend25") & (OF.offset == k)]["sharpe"].iloc[0])) for k in ro.OFFSETS)
    print(f"offset regression Trend25 vs FULLUNIV max|d| {off_reg:.2e}", flush=True)
    assert off_reg < 5e-7

    # ---------- diagnostics ----------
    DG = plan_diag(P[0]["M016-CW"], ST[0]["M016-CW"])
    DG.to_csv(os.path.join(RES, "M016_quarter_diag.csv"), index=False)
    DG12 = plan_diag(P[0]["M012-QF-S"], ST[0]["M012-QF-S"])
    dg_off = {k: plan_diag(P[k]["M016-CW"], ST[k]["M016-CW"]) for k in ro.OFFSETS}
    wr = []
    for k in ro.OFFSETS:
        for en in S[k]["M016-CW"]["full"]["entries"]:
            for f, w in en["target"].items():
                if w > 1e-12:
                    wr.append({"offset": k, "t": en["t"].date(), "e": en["e"].date(), "FundCode": f, "weight": w})
    pd.DataFrame(wr).to_csv(os.path.join(RES, "M016_weights.csv"), index=False)
    pd.DataFrame({f"{m}_{kind}": S[0][m][kind]["values"] for m in names for kind in ("full", "c0")}).to_csv(os.path.join(RES, "M016_equity_curve.csv"))
    qr = pd.DataFrame({m: quarter_returns(MR[(m, "full")]["r"], P[0][m]) for m in names})
    qr.index = [P[0]["M016-CW"][q]["t"].date() for q in qr.index]
    qr.to_csv(os.path.join(RES, "M016_quarter_returns.csv"))
    # ไตรมาสดีที่สุดของ M016 ออก -> CAGR/ Sharpe (ความไวต่อไตรมาสเดียว)
    r16, rf16 = MR[("M016-CW", "full")]["r"], MR[("M016-CW", "full")]["rfm"]
    es = np.array([p["e"] for p in P[0]["M016-CW"]], dtype="datetime64[ns]")
    qm = pd.Series([max(0, int(np.searchsorted(es, np.datetime64(m), side="left")) - 1) for m in r16.index], index=r16.index)
    best_q = int(qr.reset_index(drop=True)["M016-CW"].idxmax())
    keep = qm != best_q
    drop_best = {"q": str(P[0]["M016-CW"][best_q]["t"].date()), "sharpe": rr.sharpe_s(r16[keep], rf16[keep]),
                 "cagr_ann": float((1 + r16[keep]).prod() ** (12 / keep.sum()) - 1)}

    m16 = MR[("M016-CW", "full")]
    verdict = "ผ่าน" if (m16["max_dd"] >= DD_FLOOR and m16["cagr"] > TARGET_CAGR) else "ไม่ผ่าน"
    out = {"R": R, "PR": PR, "OF": OF, "DG": DG, "DG12": DG12, "dg_off": dg_off, "qr": qr, "drop_best": drop_best, "verdict": verdict, "reg": reg,
           "off_reg": off_reg, "S0": S[0]}
    write_md(out)
    append_trial(out)
    pd.set_option("display.width", 250)
    print(R.round(4).to_string())
    print(PR.round(4).to_string())
    print(OF.round(4).to_string())
    print(DG.drop(columns=["holdings"]).round(3).to_string())
    print(qr.round(4).to_string())
    print("drop_best", drop_best, "verdict", verdict)
    print(f"DONE {time.time()-t0:.0f}s", flush=True)
    return 0


def pc(x, d=2):
    return f"{x*100:.{d}f}%"


def write_md(o):
    R, PR, OF, DG, DG12 = o["R"], o["PR"], o["OF"], o["DG"], o["DG12"]
    g = lambda m, k: R[(R.model == m) & (R.fee == k)].iloc[0]
    L = []
    A = L.append
    A("# M016-CW — 5 กอง + น้ำหนักตามคะแนน SR12' + เพดาน 35% (บน M012-QF-S) — ผลวัด\n")
    A(f"รันเมื่อ {pd.Timestamp.now().isoformat()} · spec `specs/M016_concentrated_scoreweight.md` (ลงทะเบียนก่อนรัน) · **trial #33** · universe เต็ม · rf จริง · "
      "FeeData(legacy=False) Actual · เม.ย. 2022–ธ.ค. 2025 (45 เดือน) · Sharpe = mean(r−rf)×12/(sd(r)×√12) · โค้ด `backtest/run_m016.py`\n")
    rg = o["reg"]
    A(f"**Regression (ผ่าน)**: stream ใหม่ที่ N=8/K=16/ERC/cap25% = sleeves ของ `r12.stream('S')` ทุกไตรมาส ({rg['sleeves_N8K16ERC_eq_M012S']}) · "
      f"M012-QF-S full {rg['M012S_full']:.6f} (ref {rg['M012S_ref']:.6f}) · Trend 25 {rg['Trend25_full']:.6f} (ref {rg['Trend25_ref']:.6f}) · "
      f"Trend 25 offset 0/1/2 = `FULLUNIV_offsets.csv` (max|Δ| {o['off_reg']:.1e})\n")
    m = g("M016-CW", "full")
    A(f"## 1. ผลตามเกณฑ์ที่ล็อก (fee full): **{o['verdict']}**\n")
    A(f"- maxDD {pc(m.max_dd)} (เกณฑ์ ≥ −20%: {'✓' if m.max_dd >= DD_FLOOR else '✗'}) · CAGR {pc(m.cagr)} (เกณฑ์ > 9.09%: {'✓' if m.cagr > TARGET_CAGR else '✗'})\n")
    A("## 2. ตารางหลัก (offset 0, 45 เดือน, rf จริง)\n")
    A("| โมเดล | fee | Sharpe | CAGR | vol | maxDD | ต้นทุน %/ปี | turnover/ปี | DSR@33 | CI95% Sharpe | 2022 (เม.ย.–) | 2023 | 2024 | 2025 |")
    A("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    lab = {"full": "full (จริง)", "nofront": "nofront", "flat": "flat 0.5%/ข้าง", "c0": "0%"}
    for mm in ("M016-CW", "Trend25", "M012-QF-S"):
        for k in ("full", "nofront", "flat", "c0"):
            x = g(mm, k)
            A(f"| {'**'+mm+'**' if mm == 'M016-CW' else mm} | {lab[k]} | {x.sharpe:.3f} | {pc(x.cagr)} | {pc(x.vol)} | {pc(x.max_dd)} | {x.cost_pct_yr:.2f} | {x.turn_yr:.2f} | "
              f"{x.dsr33:.3f} | [{x.ci_lo:.2f}, {x.ci_hi:.2f}] | {pc(x.ret_2022,1)} | {pc(x.ret_2023,1)} | {pc(x.ret_2024,1)} | {pc(x.ret_2025,1)} |")
    A("\n(DSR@33 ของ Trend 25 / M012-QF-S คำนวณที่ n = 33 เพื่อเทียบเท่านั้น)\n")
    A("## 3. Paired Δ (M016-CW − อ้างอิง, block bootstrap 3, 2000, seed 0)\n")
    A("| เทียบ | fee | Δ Sharpe | CI95% | Δ CAGR |\n|---|---|---|---|---|")
    for r in PR.itertuples():
        A(f"| {r.vs} | {r.fee} | {r.d_sharpe:+.3f} | [{r.ci_lo:+.2f}, {r.ci_hi:+.2f}] | {r.d_cagr*100:+.2f} pt |")
    A("\n## 4. เลื่อนเดือน rebalance (fee full · ช่วงร่วม ก.ค. 2022–ธ.ค. 2025 = 42 เดือน · วิธีเดียวกับ ROBUST/FULLUNIV_offsets)\n")
    A("| โมเดล | offset | Sharpe | CAGR | vol | maxDD | ต้นทุน %/ปี | turnover/ปี | Sharpe/CAGR/maxDD ช่วงเต็มของ offset |")
    A("|---|---|---|---|---|---|---|---|---|")
    olab = {0: "0 (มี.ค./มิ.ย./ก.ย./ธ.ค.)", 1: "1 (เม.ย./ก.ค./ต.ค./ม.ค.)", 2: "2 (พ.ค./ส.ค./พ.ย./ก.พ.)"}
    for r in OF.itertuples():
        A(f"| {r.model} | {olab[r.offset]} | {r.sharpe:.3f} | {pc(r.cagr)} | {pc(r.vol)} | {pc(r.max_dd)} | {r.cost_pct_yr:.2f} | {r.turn_yr:.2f} | "
          f"{r.sharpe_origwin:.3f} / {pc(r.cagr_origwin)} / {pc(r.maxdd_origwin)} ({r.n_months_origwin}m) |")
    A("\n| โมเดล | Sharpe เฉลี่ย 3 offset (min–max) | CAGR เฉลี่ย (min–max) | maxDD แย่สุด |\n|---|---|---|---|")
    for mm in ("M016-CW", "Trend25", "M012-QF-S"):
        d = OF[OF.model == mm]
        A(f"| {mm} | {d.sharpe.mean():.3f} ({d.sharpe.min():.3f}–{d.sharpe.max():.3f}) | {pc(d.cagr.mean())} ({pc(d.cagr.min())}–{pc(d.cagr.max())}) | {pc(d.max_dd.min())} |")
    A("\n## 5. Concentration (offset 0)\n")
    A(f"- จำนวนกองที่ถือจริง (น้ำหนัก > 0) เฉลี่ย **{DG.n_funds_held.mean():.2f}** กอง/ไตรมาส (min {DG.n_funds_held.min()}, max {DG.n_funds_held.max()}) · M012-QF-S {DG12.n_funds_held.mean():.2f}")
    A(f"- น้ำหนักกองเดียวสูงสุด (target): **{pc(DG.max_w_total.max(),1)} ของพอร์ตรวม** · {pc(DG.max_w_equity_sleeve.max(),1)} ของส่วนหุ้น · เฉลี่ยต่อไตรมาส {pc(DG.max_w_total.mean(),1)} "
      f"(M012-QF-S สูงสุด {pc(DG12.max_w_total.max(),1)}) · น้ำหนักระหว่างไตรมาส drift ได้เกินค่านี้")
    A(f"- ไตรมาส fallback B0: {int(DG.fallback_B0.sum())}/15 · ไตรมาสที่คะแนนทุกตัว ≤ 0 → equal weight: {int(DG.eq_fallback.sum())}/15 · "
      f"กองที่ถูกเลือกแต่คะแนน ≤ 0 รวม {int(DG.n_selected_score_le0.sum())} ครั้ง")
    for k, d in o["dg_off"].items():
        A(f"- offset {k}: กองเฉลี่ย {d.n_funds_held.mean():.2f} · น้ำหนักสูงสุด {pc(d.max_w_total.max(),1)} · B0 {int(d.fallback_B0.sum())} · EW {int(d.eq_fallback.sum())}")
    db = o["drop_best"]
    A(f"- ตัดไตรมาสที่ดีที่สุดของ M016 ({db['q']}) ออก → Sharpe {db['sharpe']:.3f} · CAGR (ต่อปี จากเดือนที่เหลือ) {pc(db['cagr_ann'])}\n")
    A("| t | กอง | เงินสด | กองใหญ่สุด | น้ำหนักสูงสุด | fallback | holdings (น้ำหนักพอร์ตรวม) |\n|---|---|---|---|---|---|---|")
    for r in DG.itertuples():
        fb = "B0" if r.fallback_B0 else ("EW" if r.eq_fallback else "-")
        A(f"| {r.t} | {r.n_funds_held} | {pc(r.cash,0)} | {r.top_fund} | {pc(r.max_w_total,1)} | {fb} | {r.holdings} |")
    A("\n## 6. ผลตอบแทนรายไตรมาส (fee full)\n")
    qr = o["qr"]
    A("| ไตรมาส (t) | M016-CW | Trend25 | M012-QF-S |\n|---|---|---|---|")
    for t, r in qr.iterrows():
        A(f"| {t} | {pc(r['M016-CW'],1)} | {pc(r['Trend25'],1)} | {pc(r['M012-QF-S'],1)} |")
    A("\n## 7. ไฟล์\n`M016_results.csv`, `M016_paired.csv`, `M016_offsets.csv`, `M016_quarter_diag.csv`, `M016_weights.csv`, `M016_equity_curve.csv`, `M016_quarter_returns.csv`, "
      "`scratch/validator_m016_regression.json`")
    open(os.path.join(RES, "M016_summary.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")


def backup_trials():
    dst = os.path.join(TEAM_DIR, f"trials.backup_{pd.Timestamp.now().strftime('%Y%m%dT%H%M%S')}.csv")
    shutil.copy2(TRIALS_CSV, dst)
    return dst


def append_line(vals):
    txt = open(TRIALS_CSV, encoding="utf-8", newline="").read()
    assert not any(l.startswith(f"{NAME},") and ",ok," in l for l in txt.splitlines()), "M016-CW (ok) มีใน trials.csv แล้ว"
    line = ",".join(str(v).replace(",", ";") for v in vals)
    with open(TRIALS_CSV, "a", encoding="utf-8", newline="") as f:
        if not txt.endswith("\n"):
            f.write("\r\n")
        f.write(line + "\r\n")


def append_trial(o):
    R, PR = o["R"], o["PR"]
    m = R[(R.model == NAME) & (R.fee == "full")].iloc[0]
    sh = {k: R[(R.model == NAME) & (R.fee == k)].iloc[0].sharpe for k in ("c0", "flat", "full", "nofront")}
    pt = PR[(PR.vs == "Trend25") & (PR.fee == "full")].iloc[0]
    ps = PR[(PR.vs == "M012-QF-S") & (PR.fee == "full")].iloc[0]
    of = o["OF"][o["OF"].model == NAME]
    params = (f"{NAME}: M012-QF-S base (full universe; quality AUM_fam>=100M & age B; held cut) + N=5;K=10; weights prop max(SR12';0) (all<=0 -> EW); "
              f"cap35% apply_cap redistribute; held=weight>0; B0 fallback <4; trend cash25% ACWI<SMA200; measure=real policy rf; fee=FEEUH Actual legacy=False")
    note = (f"pre-registered objective max CAGR s.t. maxDD>=-20%; pass rule maxDD>=-20% & CAGR>9.09% -> {o['verdict']}; Sharpe(real rf; sd(r)) 0%={sh['c0']:.3f} "
            f"flat={sh['flat']:.3f} full={sh['full']:.3f} nofront={sh['nofront']:.3f}; CAGR full {m.cagr:.4f}; CI95 ({m.ci_lo:.3f};{m.ci_hi:.3f}); "
            f"paired dSharpe vs Trend25 {pt.d_sharpe:+.3f} CI ({pt.ci_lo:.3f};{pt.ci_hi:.3f}); vs M012-QF-S {ps.d_sharpe:+.3f} CI ({ps.ci_lo:.3f};{ps.ci_hi:.3f}); "
            f"offsets 0/1/2 common-42m Sharpe {'/'.join(f'{x:.3f}' for x in of.sharpe)} CAGR {'/'.join(f'{x:.4f}' for x in of.cagr)}; "
            f"rerun after crashed row (diagnostic KeyError in plan_diag; same locked spec; same trial #33); avg funds held {o['DG'].n_funds_held.mean():.2f}; max single weight {o['DG'].max_w_total.max():.3f}; n_months=45")
    vals = [NAME, pd.Timestamp.now().isoformat(), "M016_concentrated_scoreweight.md", params, "2022-03-31", "2025-12-31",
            "BOT policy rate daily (TH_POLICY_RATE.csv)", "real fees SecFundFee FEEUH (full; FeeData legacy=False)",
            round(m.sharpe, 4), round(m.cagr, 4), round(m.vol, 4), round(m.max_dd, 4), round(m.turn_yr, 4), N_TRIAL, round(m.dsr33, 4), "ok", note]
    b = backup_trials()
    print(f"trials backup -> {b}", flush=True)
    append_line(vals)


if __name__ == "__main__":
    try:
        rc = main()
    except Exception:
        tb = traceback.format_exc()
        print(tb, flush=True)
        try:
            txt = open(TRIALS_CSV, encoding="utf-8", newline="").read()
            if PHASE_B and not any(l.startswith(f"{NAME},") for l in txt.splitlines()):
                backup_trials()
                last = tb.strip().splitlines()[-1].replace(",", ";")[:200]
                append_line([NAME, pd.Timestamp.now().isoformat(), "M016_concentrated_scoreweight.md", f"{NAME} run crashed", "2022-03-31", "2025-12-31",
                             "BOT policy rate daily (TH_POLICY_RATE.csv)", "real fees SecFundFee FEEUH (full)", "", "", "", "", "", N_TRIAL, "", "crashed", last])
        except Exception:
            pass
        rc = 1
    sys.exit(rc)
