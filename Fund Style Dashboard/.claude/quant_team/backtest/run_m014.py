"""run_m014.py — M014 เกณฑ์ขาเข้า SR12' > 0.50 + ช่องว่าง = เงินสด (ไม่มี fallback B0) · น้ำหนักแบบช่อง n/8 · บน M012-QF-S · 2 trials: M014-SR05-T (28, คง trend), M014-SR05-N (29, ไม่มี trend)
ตาม specs/M014_sr12_hurdle1.md + "การยืนยันของผู้ใช้ 2026-10-06 รอบ 2" (threshold = 0.50 แทน 1.0/0.75; อันดับยังมากไปน้อยตาม SR12; slot n/8 + trend ซ้อนคูณ) · rf จริง ทุกแขน
รัน: PYTHONPATH=. ./.venv/bin/python .claude/quant_team/backtest/run_m014.py
(A) regression: (1) sr_min=-inf + fallback B0 + trend -> น้ำหนัก = M012_weights.csv & Sharpe ตรง · (2) sr_min=-inf + ไม่มี fallback -> เท่าข้อ 1 · (3) unit n=0/1/3 · ไม่ผ่าน = หยุด (ไม่นับ trial)
(B) ถ้าผ่าน -> T / N · reuse helper จาก run_m013 (setup/baseline/log) และ r12/r11/r9/rr · ไม่แก้ไฟล์เดิม
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

import common
import simulate
import weighting as wt
import run_m009 as r9
import run_m011 as r11
import run_m012 as r12
import run_m013 as r13
import remeasure_real_rf as rr

RES = common.RESULTS_DIR
SCRATCH = r13.SCRATCH
SR_MIN = 0.50
SLOTS = 8
PHASE_B = False


# ====================== การคัด / น้ำหนัก / plan ======================
def select_sr(reps, ranks, held_map, sr_min, use_fallback, n_target=8, k_drop=16):
    """keep = hysteresis เดิม (ไม่ดูเกณฑ์) · fill เรียงตามอันดับ ข้ามถ้า signal NaN หรือ ไม่ > sr_min (เฉพาะเมื่อ sr_min > -inf) · ไม่มี fallback เมื่อ use_fallback=False."""
    S, n_kept, n_kept_below = {}, 0, 0
    for fam, fc in held_map.items():
        if fam in reps and ranks.get(fam, 10**9) <= k_drop and reps[fam]["FundCode"] == fc:
            S[fam] = fc
            n_kept += 1
            sg = reps[fam]["signal"]
            if not (sg == sg and sg > sr_min):
                n_kept_below += 1
    use_gate = sr_min > -np.inf
    n_gate_skip = 0
    for fam in sorted(reps.keys(), key=lambda f: ranks.get(f, 10**9)):
        if len(S) >= n_target:
            break
        if fam in S:
            continue
        if use_gate:
            sg = reps[fam]["signal"]
            if not (sg == sg and sg > sr_min):
                n_gate_skip += 1
                continue
        S[fam] = reps[fam]["FundCode"]
    return {"S": S, "n_kept": n_kept, "n_kept_below": n_kept_below,
            "fallback": ("b0" if (use_fallback and len(S) < 4) else None)}


def stream_sr(ctxs, quals, sr_min, use_fallback):
    held, prev_fb, recs = {}, False, []
    for ctx in ctxs:
        g = quals[ctx["qi"]]
        fam_ok = set(g.index[g["pass_q1"] & g["pass_q2"]])
        it = ctx["i_t"][ctx["i_t"]["family"].isin(fam_ok)]                       # เกณฑ์คุณภาพแบบ S (เหมือน run_m012)
        reps = wt.family_representatives(it, "SR12", held_funds=set(held.values()))
        ranks = wt.rank_families(reps)                                           # อันดับจากทุก family ใน I_t' (ไม่กรอง sr_min ก่อน rank)
        H_map = {} if (use_fallback and prev_fb) else held
        sel = select_sr(reps, ranks, H_map, sr_min, use_fallback)
        fb = bool(use_fallback and (sel["fallback"] == "b0" or len(sel["S"]) == 0))
        n_sr_pass = sum(1 for r in reps.values() if (r["signal"] == r["signal"] and r["signal"] > sr_min))
        recs.append({"qi": ctx["qi"], "held_before": dict(held), "prev_fb": prev_fb, "S": dict(sel["S"]), "fallback": fb, "n_kept": sel["n_kept"],
                     "n_kept_below": sel["n_kept_below"], "n_fam": len(reps), "n_sr_pass": n_sr_pass, "reps": reps, "ranks": ranks})
        if fb:
            held, prev_fb = {}, True
        else:
            held, prev_fb = dict(sel["S"]), False
    return recs


def slot_weights(funds, wk, vol_map, erc_raw=None, key=None):
    """n=|funds| (>=1): ERC เต็ม 1 -> cap_n = min(1, 0.25*8/n) -> w_i = (n/8)*u_i (Σ = n/8)."""
    n = len(funds)
    assert 1 <= n <= SLOTS
    if erc_raw is not None and key in erc_raw:
        v = erc_raw[key]
    else:
        v, _ = wt.risk_parity_weights(funds, wk, vol_map, method="erc")
        if erc_raw is not None:
            erc_raw[key] = v
    cap_n = min(1.0, 0.25 * SLOTS / n)
    u = wt.apply_cap(v, cap_n)
    return (n / SLOTS) * u


def build_plan(recs, ctxs, quarters15, calendar, acwi, use_trend, erc_raw):
    plan = []
    for qi, t in enumerate(quarters15):
        ctx, rec = ctxs[qi], recs[qi]
        assert ctx["t"] == t and rec["qi"] == qi
        c_tr = wt.trend_filter_cash(acwi, t, 0.25) if use_trend else 0.0
        if rec["fallback"]:
            sleeve = ctx["b0_w"]                                                  # fallback B0 (เฉพาะแขน regression)
            w = {fc: float(v) for fc, v in sleeve.items() if v > 0}               # Σ = 1 (ไม่ผ่าน slot)
        else:
            funds = list(rec["S"].values())
            if len(funds) == 0:
                w = {}
            else:
                key = (qi, tuple(funds))
                ws = slot_weights(funds, ctx["wk"], ctx["vol_map"], erc_raw, key)
                w = {f: float(x) for f, x in ws.items() if x > 0}
        wf = {fc: (1.0 - c_tr) * v for fc, v in w.items()}
        cash = 1.0 - sum(wf.values())                                             # __CASH__ = 1 − Σ กอง
        if cash > 1e-15:
            wf["__CASH__"] = cash
        plan.append({"t": t, "e": common.execution_date(calendar, t), "weights": wf})
    r13.plan_sum_check(plan)
    return plan


def sets_of(recs):
    return [("B0" if r["fallback"] else tuple(sorted(r["S"].values()))) for r in recs]


# ====================== unit tests ======================
def unit_tests(E, recs_ref):
    out = {}
    q = 10
    ctx = E["ctx_h"][q]
    funds8 = list(recs_ref[q]["S"].values())
    assert len(funds8) == 8
    erc = {}
    # n = 0 -> เงินสด 100%
    r0 = {"qi": q, "S": {}, "fallback": False}
    p = build_plan([{**r0, "qi": i} if i == q else {"qi": i, "S": recs_ref[i]["S"], "fallback": False} for i in range(15)], E["ctx_h"], E["q15"], E["calendar"], E["acwi"], False, erc)
    out["n0_cash_only"] = bool(set(p[q]["weights"].keys()) == {"__CASH__"} and abs(p[q]["weights"]["__CASH__"] - 1.0) < 1e-12)
    # n = 1 (T/N): 1/8 * (1 - c_tr)
    for use_trend in (False, True):
        c_tr = wt.trend_filter_cash(E["acwi"], E["q15"][q], 0.25) if use_trend else 0.0
        r1 = {"qi": q, "S": {"X": funds8[0]}, "fallback": False}
        pl = build_plan([r1 if i == q else {"qi": i, "S": recs_ref[i]["S"], "fallback": False} for i in range(15)], E["ctx_h"], E["q15"], E["calendar"], E["acwi"], use_trend, erc)
        w = pl[q]["weights"]
        out[f"n1_trend{int(use_trend)}"] = bool(abs(w[funds8[0]] - (1 - c_tr) / 8.0) < 1e-12)
    # n = 3: Σ = 3/8 และไม่มีกอง > 0.25
    r3 = {"qi": q, "S": {f"X{i}": f for i, f in enumerate(funds8[:3])}, "fallback": False}
    pl = build_plan([r3 if i == q else {"qi": i, "S": recs_ref[i]["S"], "fallback": False} for i in range(15)], E["ctx_h"], E["q15"], E["calendar"], E["acwi"], False, erc)
    w = {k: v for k, v in pl[q]["weights"].items() if k != "__CASH__"}
    out["n3_sum_3over8"] = bool(abs(sum(w.values()) - 3 / 8) < 1e-12)
    out["n3_max_le_025"] = bool(max(w.values()) <= 0.25 + 1e-12)
    # ทุก n 1..8: Σ = n/8, max ≤ 0.25
    ok_all_n = True
    for n in range(1, 9):
        ws = slot_weights(funds8[:n], ctx["wk"], ctx["vol_map"])
        ok_all_n &= bool(abs(ws.sum() - n / 8) < 1e-12 and ws.max() <= 0.25 + 1e-12)
    out["all_n_sum_and_cap"] = ok_all_n
    out["ok"] = bool(all(v for v in out.values()))
    return out


# ====================== main ======================
def main():
    t0 = time.time()
    print("[1/7] setup...", flush=True)
    E = r13.setup()
    real = E["real"]
    print("[2/7] baseline M012-QF-S...", flush=True)
    B = r13.baseline(E)
    ctx15 = [c for c in E["ctx_h"] if c["qi"] < 15]
    st_ref_sets = [("B0" if r["fallback"] else tuple(sorted(r["S"].values()))) for r in B["st"]["recs"]]

    print("[3/7] regression...", flush=True)
    rs = pd.read_csv(os.path.join(RES, "M012_results.csv")).set_index(["trial", "cost"])
    reg = {}
    for name, use_fb in (("R1_fallback_on", True), ("R2_fallback_off", False)):
        recs = stream_sr(E["ctx_h"], E["quals"], -np.inf, use_fb)
        same_sets = bool(sets_of(recs) == st_ref_sets)
        same_flag = bool([r["fallback"] for r in recs] == [r["fallback"] for r in B["st"]["recs"]])
        n_lt8 = [i for i, r in enumerate(recs[:15]) if (not r["fallback"]) and len(r["S"]) < 8]
        erc_raw = {}
        plan = build_plan(recs, E["ctx_h"], E["q15"], E["calendar"], E["acwi"], True, erc_raw)
        sims = r11.sims_real(plan, E["nav_by_fund"], E["months"], E["fd_sim"], real)
        dmax, nonly, nref, nmine, _ = r13.reg_vs_m012s(plan)
        sh, shref, ok_s = r13.sharpes_vs_ref(sims, real, rs)
        reg[name] = {"max_dw": dmax, "n_only": nonly, "n_ref": nref, "n_mine": nmine, "ok_w": bool(dmax < 1e-9 and nonly == 0), "ok_s": bool(ok_s),
                     "sharpe_full": sh["full"], "sharpe_ref_full": shref["full"], "same_sets_as_r12": same_sets, "same_fb_flags": same_flag, "quarters_n_lt_8": n_lt8}
    reg["unit"] = unit_tests(E, B["st"]["recs"])
    reg["ok_all"] = bool(all(reg[k]["ok_w"] and reg[k]["ok_s"] and reg[k]["same_sets_as_r12"] and reg[k]["same_fb_flags"] for k in ("R1_fallback_on", "R2_fallback_off"))
                         and not reg["R2_fallback_off"]["quarters_n_lt_8"] and reg["unit"]["ok"])
    print("  REGRESSION:", json.dumps(reg, default=float), flush=True)
    json.dump(reg, open(os.path.join(SCRATCH, "validator_m014_regression.json"), "w"), default=float)
    if not reg["ok_all"]:
        print("REGRESSION FAIL — หยุด (ไม่นับ trial)", flush=True)
        return 2

    print("[4/7] รัน T / N...", flush=True)
    MRb, MCb = r13.bundle(B["sims_r"], B["sims_c"], real)
    rb, rfm = MRb["full"]["r"], MRb["full"]["rfm"]
    ci_b = rr.boot_ci(rb, rfm)
    dsr_b = rr.dsr_s(rb, rfm, r13.N_TRIALS_FINAL)
    recs = stream_sr(E["ctx_h"], E["quals"], SR_MIN, False)
    assert not any(r["fallback"] for r in recs)
    base_recs = B["st"]["recs"]
    base_sets = sets_of(base_recs)
    erc_raw = {}
    ARM = {}
    for tag, use_trend in (("T", True), ("N", False)):
        plan = build_plan(recs, E["ctx_h"], E["q15"], E["calendar"], E["acwi"], use_trend, erc_raw)
        sims_r = r11.sims_real(plan, E["nav_by_fund"], E["months"], E["fd_sim"], real)
        sims_c = r9.sim_cases(plan, E["nav_by_fund"], E["months"], E["fd_sim"])
        MR, MC = r13.bundle(sims_r, sims_c, real)
        rn = MR["full"]["r"]
        d = r11.paired_real(rn, rb, rfm, "r")
        ci = rr.boot_ci(rn, rfm)
        dsr = rr.dsr_s(rn, rfm, r13.N_TRIALS_FINAL)
        qd = r13.qdelta(rn, rb, rfm, plan, E["q15"])
        es = r13.entry_stats(sims_r["full"], E["q15"])
        ARM[tag] = {"plan": plan, "sims_r": sims_r, "sims_c": sims_c, "MR": MR, "MC": MC, "d": d, "ci": ci, "dsr": dsr, "qd": qd, "es": es,
                    "verdict": "ผ่าน (ดีกว่าอย่างมีนัย)" if (d[2] >= 0 and d[0] > 0) else ("ผ่าน" if d[2] >= 0 else "ไม่ผ่าน")}
        print(f"  {tag}: Δ {d[2]:+.4f} [{d[0]:+.3f},{d[1]:+.3f}] full={MR['full']['sharpe']:.4f} avg stock {es['stock'].mean():.3f}", flush=True)
    d_nt = r11.paired_real(ARM["N"]["MR"]["full"]["r"], ARM["T"]["MR"]["full"]["r"], rfm, "r")
    base_es = r13.entry_stats(B["sims_r"]["full"], E["q15"])

    # ---- ต่อไตรมาส: จำนวนกอง ชุดต่างจาก M012-QF-S (ตรง/สืบทอด) path luck ----
    rows = []
    diff_q = []
    for q in range(16):
        rec = recs[q]
        brec = base_recs[q]
        # "ตรง": คัดด้วยเกณฑ์ + สถานะถือ (held) ของ M012-QF-S ณ t
        g = E["quals"][q]
        fam_ok = set(g.index[g["pass_q1"] & g["pass_q2"]])
        it = E["ctx_h"][q]["i_t"]
        it = it[it["family"].isin(fam_ok)]
        reps_d = wt.family_representatives(it, "SR12", held_funds=set(brec["held_before"].values()))
        rk_d = wt.rank_families(reps_d)
        sel_d = select_sr(reps_d, rk_d, {} if brec["prev_fb"] else brec["held_before"], SR_MIN, False)
        s_dir = tuple(sorted(sel_d["S"].values()))
        s_b, s_n = base_sets[q], tuple(sorted(rec["S"].values()))
        is_dir, is_diff = s_dir != s_b, s_n != s_b
        if q < 15 and is_diff:
            diff_q.append(q)
        n = len(rec["S"])
        c_tr_T = float(wt.trend_filter_cash(E["acwi"], E["q15"][q] if q < 15 else E["q16"][q], 0.25))
        stock_T = (1 - c_tr_T) * n / 8.0
        sel_f = list(rec["S"].keys())
        min_aum = float(min(g.loc[f, "aum_fam"] for f in sel_f)) / 1e6 if sel_f else np.nan
        rows.append({"qi": q, "t": E["q16"][q].date(), "in_plan15": q < 15, "n_family_I_prime": rec["n_fam"], "n_sr_gt_min": rec["n_sr_pass"], "n_kept": rec["n_kept"],
                     "n_added": n - rec["n_kept"], "n": n, "cash_gap": (8 - n) / 8.0, "cash_trend_T": c_tr_T * n / 8.0, "cash_total_T": 1 - stock_T,
                     "cash_total_N": 1 - n / 8.0, "n_kept_sr_le_min": rec["n_kept_below"], "n_lt4": n < 4, "n_0": n == 0, "min_aum_fam_MBaht": min_aum,
                     "diff_direct": is_dir, "diff_final": is_diff, "set_base": ";".join(sorted(s_b)), "set_m014": ";".join(sorted(s_n))})
    QD = pd.DataFrame(rows)
    # path luck T และ N (ชุดเหมือน/ต่าง)
    pl = {}
    for tag in ARM:
        qm = ARM[tag]["qd"]["qm"]
        dret = ARM[tag]["MR"]["full"]["r"] - rb
        same_mask = qm.map(lambda q: q not in diff_q)
        pl[tag] = {"same": float(dret[same_mask].sum()), "diff": float(dret[~same_mask].sum()), "n_same": int(same_mask.sum()), "n_diff": int((~same_mask).sum())}

    print("[5/7] write outputs...", flush=True)
    eqd = {"M012-QF-S_full_real": B["sims_r"]["full"]["values"], "M012-QF-S_c0_real": B["sims_r"]["c0"]["values"]}
    for tag in ARM:
        eqd[f"M014-SR05-{tag}_full_real"] = ARM[tag]["sims_r"]["full"]["values"]
        eqd[f"M014-SR05-{tag}_c0_real"] = ARM[tag]["sims_r"]["c0"]["values"]
    pd.DataFrame(eqd).to_csv(os.path.join(RES, "M014_equity_curve.csv"))
    wrows = []
    for tag in ARM:
        for en in ARM[tag]["sims_r"]["full"]["entries"]:
            for f, w in en["target"].items():
                if w > 1e-12:
                    wrows.append({"trial": f"M014-SR05-{tag}", "t": en["t"].date(), "e": en["e"].date(), "kind": en["mode"], "FundCode": f, "weight": w})
    pd.DataFrame(wrows).to_csv(os.path.join(RES, "M014_weights.csv"), index=False)
    QD.to_csv(os.path.join(RES, "M014_quarter_diag.csv"), index=False)
    summ = []
    for name, MRx, sr, MCx in (("M012-QF-S", MRb, B["sims_r"], MCb), ("M014-SR05-T", ARM["T"]["MR"], ARM["T"]["sims_r"], ARM["T"]["MC"]),
                               ("M014-SR05-N", ARM["N"]["MR"], ARM["N"]["sims_r"], ARM["N"]["MC"])):
        for k in r13.KINDS:
            summ.append({"trial": name, "cost": k, "sharpe_real": MRx[k]["sharpe"], "cagr_real": MRx[k]["cagr"], "vol_real": MRx[k]["vol"], "maxdd_real": MRx[k]["max_dd"],
                         "maxdd_2022_real": r13.mdd_2022(sr[k]["values"]), "sharpe_2022_real": MRx[k]["sharpe_2022"], "sharpe_2307_2512_real": MRx[k]["sharpe_2307_2512"],
                         "sharpe_rf2": MCx[k]["sharpe"], "cost_bp_yr_real": sr[k]["cost_bp_yr"], "turn_yr": sr[k]["turn_yr"]})
    pd.DataFrame(summ).to_csv(os.path.join(RES, "M014_results.csv"), index=False)
    write_md(E, reg, B, MRb, ci_b, dsr_b, ARM, d_nt, base_es, QD, pl, recs, base_recs)

    print("[6/7] trials.csv / ALL_RESULTS...", flush=True)
    global PHASE_B
    PHASE_B = True
    for tag, n in (("T", 28), ("N", 29)):
        x = ARM[tag]
        nn = QD[QD["in_plan15"]]["n"]
        params = (f"M014-SR05-{tag}: M012-QF-S + entry gate SR12'>0.50 (fill only; held not cut; rank over all I_t'); no B0 fallback; gap=cash; slot weights w=(n/8)*ERC cap_n=min(1;0.25*8/n); "
                  f"trend={'SMA200 25% multiplicative' if tag == 'T' else 'none'}; N=8;K=16;ERC LW;measure=real policy rf; fee=FEEUH full PIT;primary=2022-03..2025-12; "
                  f"POST-HOC (threshold 1.0->0.75->0.50 after seeing count table)")
        log_trial_m014(x, tag, n, params, d_nt, nn)
    with open(os.path.join(RES, "ALL_RESULTS.md"), "a", encoding="utf-8") as f:
        a, b = ARM["T"], ARM["N"]
        f.write(f"\n## M014-SR05-T / M014-SR05-N (เพิ่ม {pd.Timestamp.now().date()}, trial ที่ 28 และ 29 · ⚠️ post-hoc: threshold เปลี่ยน 1.0 → 0.75 → 0.50 หลังเห็นตารางจำนวนกอง)\n"
                f"- M012-QF-S + เกณฑ์ขาเข้า SR12′ > 0.50 (fill เท่านั้น กองถือต่อไม่ถูกตัด) · ไม่มี fallback B0 · ช่องว่าง = เงินสด · น้ำหนักแบบช่อง n/8 · T = คง trend (คูณ), N = ไม่มี trend · **วัดด้วย rf จริง** "
                f"(คอลัมน์ `*_realrf`, `dsr_n22_fee_full_realrf` ของ 2 แถวนี้ = DSR@29)\n"
                f"- Sharpe full (rf จริง): M012-QF-S {MRb['full']['sharpe']:.3f} · T {a['MR']['full']['sharpe']:.3f} (Δ {a['d'][2]:+.4f} CI [{a['d'][0]:+.3f}, {a['d'][1]:+.3f}] · {a['verdict']}) · "
                f"N {b['MR']['full']['sharpe']:.3f} (Δ {b['d'][2]:+.4f} CI [{b['d'][0]:+.3f}, {b['d'][1]:+.3f}] · {b['verdict']}) · Δ(N−T) {d_nt[2]:+.4f} · รายละเอียด `M014_results.md`\n")
    print(f"DONE in {time.time()-t0:.0f}s", flush=True)
    return 0


def log_trial_m014(x, tag, n, params, d_nt, nn):
    note_extra = (f"POST-HOC label (threshold changed 1.0->0.75->0.50 after seeing count table); n funds/quarter min {int(nn.min())} mean {nn.mean():.2f}; "
                  f"{'dSharpe(N-T)=' + format(d_nt[2], '+.4f') + ' CI (' + format(d_nt[0], '.3f') + ';' + format(d_nt[1], '.3f') + ')' if tag == 'N' else 'trend kept'}")
    r13.log_trial(f"M014-SR05-{tag}", n, "M014_sr12_hurdle1.md", params, x["MR"], x["MC"], x["sims_r"], x["sims_c"], x["ci"], x["dsr"], x["d"], x["verdict"],
                  f"M012-QF-S + entry gate SR12'>0.50 no fallback gap=cash slot n/8 {'trend kept' if tag == 'T' else 'no trend'} (POST-HOC threshold) (measured with real rf)", note_extra)


def write_md(E, reg, B, MRb, ci_b, dsr_b, ARM, d_nt, base_es, QD, pl, recs, base_recs):
    L = []
    A = L.append
    mb = MRb["full"]
    A("# M014 — เกณฑ์ขาเข้า SR12′ > 0.50 + ช่องว่าง = เงินสด (ไม่มี fallback B0) บน M012-QF-S — ผลวัด (validator)\n")
    A(f"รันเมื่อ {pd.Timestamp.now().isoformat()} · spec `specs/M014_sr12_hurdle1.md` + การยืนยันของผู้ใช้ 2026-10-06 รอบ 2 (threshold = 0.50 · slot n/8 · trend ซ้อนคูณ) · "
      "M014-SR05-T (trial 28, คง trend) · M014-SR05-N (trial 29, ไม่มี trend) · primary เม.ย. 2022–2025-12-31 (45 เดือน) · วัดด้วย **rf จริง** (ตัวหาร sd(r)) ทุกแขน · baseline = M012-QF-S (วัดซ้ำในรันนี้) · ไม่มี holdout\n")
    A("> ⚠️ **POST-HOC**: ผู้ใช้เปลี่ยน threshold 1.0 → 0.75 → 0.50 หลังเห็นตารางจำนวน family ที่ผ่าน SR12 > 1 ต่อไตรมาส → ค่า 0.50 ไม่ใช่ค่า ex-ante · ใช้ค่าเดียว ไม่ได้รันค่าอื่น · DSR ใช้ n = 29\n")
    A("## 1. Regression (ก่อนรันจริง)\n")
    for k, lab in (("R1_fallback_on", "sr_min = −∞ + fallback B0 + trend (select_sr + slot + builder ใหม่)"), ("R2_fallback_off", "sr_min = −∞ + **ไม่มี** fallback + trend")):
        r = reg[k]
        A(f"- {lab}: เทียบ `M012_weights.csv` max|Δw| = {r['max_dw']:.2e} (แถว {r['n_ref']} vs {r['n_mine']}, คีย์ฝั่งเดียว {r['n_only']}) → **{'PASS' if r['ok_w'] else 'FAIL'}** · "
          f"Sharpe c0/c50/flat/full/nofront ตรง `M012_results.csv` (<5e-7) → **{'PASS' if r['ok_s'] else 'FAIL'}** (full {r['sharpe_full']:.6f}) · ชุดกอง/flag fallback ตรง `r12.stream` mode S ทุกไตรมาส: "
          f"{'PASS' if (r['same_sets_as_r12'] and r['same_fb_flags']) else 'FAIL'} · ไตรมาส n < 8 (ใน 15): {r['quarters_n_lt_8'] if r['quarters_n_lt_8'] else 'ไม่มี'}")
    u = reg["unit"]
    A(f"- unit: n=0 → entry = {{__CASH__: 1}} {'✓' if u['n0_cash_only'] else '✗'} · n=1 → 1/8×(1−c_tr) (N: {'✓' if u['n1_trend0'] else '✗'}, T: {'✓' if u['n1_trend1'] else '✗'}) · n=3 → Σ = 3/8 {'✓' if u['n3_sum_3over8'] else '✗'} และไม่มีกอง > 0.25 {'✓' if u['n3_max_le_025'] else '✗'} · "
      f"ทุก n = 1..8: Σ = n/8 และ max ≤ 0.25 {'✓' if u['all_n_sum_and_cap'] else '✗'} · ทุก entry Σ = 1 (assert) · ข้อมูล ≤ t (Quality/ctx เดิม + assert ใน `r12.Quality.table`)\n")
    A("## 2. ตารางหลัก (ค่าธรรมเนียมจริง full, rf จริง, ตัวหาร sd(r))\n")
    L.extend(r13.MAIN_HDR)
    for tag in ARM:
        A(r13.main_row(f"M014-SR05-{tag}", ARM[tag]["MR"]["full"], ARM[tag]["sims_r"]["full"], ARM[tag]["ci"], ARM[tag]["dsr"]))
    A(r13.main_row("M012-QF-S (baseline)", mb, B["sims_r"]["full"], ci_b, dsr_b))
    r13.b0_row(L)
    r13.context_rows(L, ["M006-TCA"])
    A("\nM006-TCA วัดด้วย rf จริงในไฟล์เดิม (ต่างกลไก: ตัดน้ำหนักกองที่ R12 < 2%) · maxDD ช่วง 2022 = ถึง 2022-12-31 (full fee, rf จริง)\n")
    A("## 3. ตัวชี้วัดหลัก + เกณฑ์ (ล็อก: ผ่าน = Δ Sharpe full ≥ 0 · ไม่ผ่าน = คง M012-QF-S · รายงานทั้ง T และ N ไม่เลือกตัวที่ดีกว่า)\n")
    for tag in ARM:
        d = ARM[tag]["d"]
        A(f"- **{tag}: Δ Sharpe_full (M014-SR05-{tag} − M012-QF-S) = {d[2]:+.4f}** · CI95% paired block bootstrap (block 3, 2000, seed 0) [{d[0]:+.3f}, {d[1]:+.3f}] "
          f"({'คร่อม 0' if d[0] <= 0 <= d[1] else 'ไม่คร่อม 0'}) · **ผลตามเกณฑ์: {ARM[tag]['verdict']}**")
    A(f"- **Δ paired (N − T) = {d_nt[2]:+.4f}** CI [{d_nt[0]:+.3f}, {d_nt[1]:+.3f}] = ผลของการเอา trend ออกภายใต้เกณฑ์ 0.50 (ไม่ใช่ trial เพิ่ม)\n")
    A("## 4. ตารางต้นทุน (rf จริง)\n")
    A("| ต้นทุน | T Sharpe | CAGR | vol | maxDD | N Sharpe | CAGR | vol | maxDD | M012-QF-S Sharpe | CAGR | vol | maxDD |")
    A("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for k in r13.KINDS:
        a, b, c = ARM["T"]["MR"][k], ARM["N"]["MR"][k], MRb[k]
        A(f"| {r13.KIND_LAB[k]} | {a['sharpe']:.3f} | {a['cagr']:.4f} | {a['vol']:.4f} | {a['max_dd']:.4f} | {b['sharpe']:.3f} | {b['cagr']:.4f} | {b['vol']:.4f} | {b['max_dd']:.4f} | "
          f"{c['sharpe']:.3f} | {c['cagr']:.4f} | {c['vol']:.4f} | {c['max_dd']:.4f} |")
    A(f"\n- turnover/ปี (full): T {ARM['T']['sims_r']['full']['turn_yr']:.3f} · N {ARM['N']['sims_r']['full']['turn_yr']:.3f} · M012-QF-S {B['sims_r']['full']['turn_yr']:.3f} · "
      f"cost bp/ปี (full): T {ARM['T']['sims_r']['full']['cost_bp_yr']:.1f} · N {ARM['N']['sims_r']['full']['cost_bp_yr']:.1f} · M012-QF-S {B['sims_r']['full']['cost_bp_yr']:.1f}\n")
    A("## 5. ต่อไตรมาส: จำนวนกอง / เงินสด / family ที่ผ่านเกณฑ์\n")
    A("| t | family ใน I_t′ | SR12′ > 0.50 | n_kept | n_added | **n = กองที่ถือ** | กองถือต่อที่ SR12′ ≤ 0.50 | เงินสดช่องว่าง | เงินสดรวม T | เงินสดรวม N | AUM_fam ต่ำสุด (ล้านบาท) | ชุดต่างจาก M012-QF-S |")
    A("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for r in QD.itertuples():
        dd = ("ต่าง-ตรง" if r.diff_direct else "ต่าง-สืบทอด") if r.diff_final else "-"
        A(f"| {r.t}{'' if r.in_plan15 else ' (หน้า 9)'} | {r.n_family_I_prime} | {r.n_sr_gt_min} | {r.n_kept} | {r.n_added} | **{r.n}** | {r.n_kept_sr_le_min} | {r.cash_gap:.3f} | {r.cash_total_T:.3f} | {r.cash_total_N:.3f} | "
          f"{'—' if r.min_aum_fam_MBaht != r.min_aum_fam_MBaht else format(r.min_aum_fam_MBaht, ',.0f')} | {dd} |")
    q15 = QD[QD["in_plan15"]]
    A("")
    for tag in ARM:
        es = ARM[tag]["es"]
        be = base_es
        A(f"- **{tag}**: หุ้นเฉลี่ย (เป้าหมาย 15 entry) {es['stock'].mean():.3f} · เงินสดเฉลี่ย {es['cash'].mean():.3f} · M012-QF-S หุ้นเฉลี่ย {be['stock'].mean():.3f} · หุ้นต่ำสุด {es['stock'].min():.3f}")
    A(f"- จำนวนกองต่อไตรมาส (15 ไตรมาสใน plan): ต่ำสุด {int(q15['n'].min())} · เฉลี่ย {q15['n'].mean():.2f} · สูงสุด {int(q15['n'].max())} · **ไตรมาสที่ n < 4: {int((q15['n']<4).sum())}** "
      f"({', '.join(str(t) for t in q15.loc[q15['n']<4,'t'])}) · **n = 0: {int((q15['n']==0).sum())}** (ขัดกรอบ 4–10 กองของ BRIEF — ผู้ใช้ยอมรับแล้ว) · n = 8 เต็ม: {int((q15['n']==8).sum())}/15")
    A(f"- ชุดกองต่างจาก M012-QF-S {int(q15['diff_final'].sum())}/15 ไตรมาส (ตรงๆ {int(q15['diff_direct'].sum())}, สืบทอดผ่าน hysteresis {int((q15['diff_final'] & ~q15['diff_direct']).sum())}) · "
      f"พอร์ต 2025-12-31 (หน้า 9): M014 n = {int(QD.iloc[15]['n'])} [{QD.iloc[15]['set_m014']}] · M012-QF-S [{QD.iloc[15]['set_base']}]\n")
    A("## 6. Path luck + drop-best-quarter + Δ ต่อไตรมาส\n")
    for tag in ARM:
        qd = ARM[tag]["qd"]
        A(f"- **{tag}**: Σ(r_M014 − r_M012-QF-S) เดือนในไตรมาสชุดกอง**เหมือน** {pl[tag]['same']:+.4f} ({pl[tag]['n_same']} เดือน) · **ต่าง** {pl[tag]['diff']:+.4f} ({pl[tag]['n_diff']} เดือน) · "
          f"ตัดไตรมาสที่ผลต่างบวกสุด ({E['q15'][qd['best_q']].date()}) → Sharpe {qd['drop'][0]:.3f} vs M012-QF-S {qd['drop'][1]:.3f} Δ {qd['drop'][0]-qd['drop'][1]:+.3f} · ไตรมาสลบสุด {E['q15'][qd['worst_q']].date()}")
    A("\n| ไตรมาส t | n | Σ Δr T | Σ Δr N |\n|---|---|---|---|")
    tt, tn = ARM["T"]["qd"]["tab"], ARM["N"]["qd"]["tab"]
    for q in tt.index:
        A(f"| {tt.loc[q,'t']} | {int(QD.iloc[q]['n'])} | {tt.loc[q,'sum_dret']:+.4f} | {tn.loc[q,'sum_dret']:+.4f} |")
    A("")
    A("## 7. สมมติฐาน / ที่ validator ตีความเอง\n")
    for s in [
        "I_t′ = แถวของ I_t (SR12 ด้วย hurdle rf จริงของ M011) ที่ family ผ่าน Q1 (AUM_fam ≥ 100 ล้าน) และ Q2 (อายุแบบ B ≥ 730 วัน) = mode S ของ `run_m012` · `family_representatives(.., 'SR12', held_funds)` + `rank_families` คำนวณจากทุก family ใน I_t′ (ไม่กรอง 0.50 ก่อน rank) · เกณฑ์ใช้เฉพาะขั้น fill (signal > 0.50 เข้มงวด; NaN = ไม่ผ่าน)",
        "keep = hysteresis เดิม (class เดิม, อันดับ ≤ 16) ไม่ดู 0.50 · ไม่มี fallback B0 ในแขนจริง (ถ้า |S| < 4 ยังถือต่อ, ว่าง = เงินสด) · held ไตรมาสถัดไป = S แม้ว่าง · อันดับของกองถือต่อคิดด้วย class ที่ถือ (กติกา `family_representatives` เดิม)",
        "slot: n = |S| → ERC เต็ม 1 ในกองที่มี (`wt.risk_parity_weights` LW lag-0, inverse-vol ถ้า < 30 สัปดาห์) → `apply_cap(v, min(1, 0.25·8/n))` → w_i = (n/8)·u_i · trend (T): w_i × (1 − c_tr) · `__CASH__` = 1 − Σกอง · ไม่ใช้ `old_style_plan` (ตาม spec §2.3)",
        "คอลัมน์ 'SR12′ > 0.50' นับจาก reps ของแขน M014 (ใช้ class ที่ถืออยู่เป็นตัวแทนของ family ที่ถือ) จึงอาจต่างจากตาราง ex-ante ของ quant-modeler (นับ class สัญญาณสูงสุดโดยไม่มีสถานะถือ) เล็กน้อย",
        "'ชุดต่างตรงๆ' = select ด้วย 0.50 + สถานะถือของ M012-QF-S ณ t · 'สืบทอด' = ต่างจริงแต่ไม่ต่างตรงๆ · Δ paired CI: `r11.paired_real` (block 3, 2000, seed 0, rf จริง, ตัวหาร sd(r)) · DSR = `rr.dsr_s` n = 29",
        "เงินสด = ดอกเบี้ยนโยบายแบบ step ไม่หักค่าธรรมเนียมกองตลาดเงิน (~0.2–0.4%) → เงินสดดูดีเกินจริงเล็กน้อย · n ขาลง = 1 (2022) · พอร์ต 2025-12-31 ไม่อยู่ใน 45 เดือนที่วัด",
    ]:
        A(f"- {s}")
    A("\n## 8. ไฟล์\n`M014_results.csv`, `M014_equity_curve.csv`, `M014_weights.csv`, `M014_quarter_diag.csv`, `scratch/validator_m014_regression.json`, `scratch/validator_m014_run.log`")
    open(os.path.join(RES, "M014_results.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")


if __name__ == "__main__":
    try:
        rc = main()
    except Exception:
        tb = traceback.format_exc()
        print(tb, flush=True)
        try:
            if PHASE_B:
                r13.log_crash((("M014-SR05-T", 28), ("M014-SR05-N", 29)), "M014_sr12_hurdle1.md", tb.strip().splitlines()[-1].replace(",", ";")[:200])
        except Exception:
            pass
        rc = 1
    sys.exit(rc)
