"""run_m012.py — M012-QF (เกณฑ์คุณภาพ AUM_fam >= 100 ล้านบาท + อายุแบบ B >= 730 วัน) บน M011-RFH · 2 ทางเลือก = 2 trials (24, 25)
  M012-QF-S: กองที่ถือต่อแล้วหลุดเกณฑ์ -> ขาย      M012-QF-K: เกณฑ์ใช้เฉพาะเติมกองใหม่ (กองถือต่อไม่ถูกตัดด้วยเกณฑ์)
ตาม specs/M012_quality_filter.md + "การตัดสินใจของผู้ใช้ 2026-10-06" · วัดด้วย rf จริง (remeasure_real_rf.py, ตัวหาร sd(r)) แบบเดียวกับ M011
รัน: PYTHONPATH=. ./.venv/bin/python .claude/quant_team/backtest/run_m012.py
(A) regression: ปิดเกณฑ์ -> น้ำหนักเท่า M011-RFH_weights.csv (|dw|<1e-9) + Sharpe เท่า M011_results.csv (ทั้ง S และ K) · ถ้าไม่ผ่าน = หยุด (ไม่นับ trial)
(B) ถ้าผ่านเท่านั้น -> รัน S และ K · ไม่แก้ไฟล์เดิม · reuse run_m011/run_m009/remeasure_real_rf/weighting/fund_signals/fees/simulate
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
import run_m009 as r9
import run_m011 as r11
import remeasure_real_rf as rr
from data import msci_index

TEAM_DIR = os.path.dirname(THIS_DIR)
PROJECT = os.path.dirname(os.path.dirname(TEAM_DIR))
SCRATCH = os.path.join(TEAM_DIR, "scratch")
RES = common.RESULTS_DIR
TRIALS_CSV = os.path.join(TEAM_DIR, "trials.csv")
N_TRIALS_FINAL = 25
AUM_MIN = 100_000_000.0
AGE_DAYS = 730
AUM_STALE_DAYS = 90
SEL_N, SEL_K = 8, 16
PHASE_B = False


# ---------------- Q1/Q2 ต่อ family ณ t ----------------
def load_reg_dates():
    fp = pd.read_csv(os.path.join(PROJECT, "base_data", "FundProfile.csv"), dtype=str, encoding="utf-8-sig")
    fp.columns = [c.strip() for c in fp.columns]
    s = fp.drop_duplicates("Fund Code").set_index("Fund Code")["Registration_date"]
    return pd.to_datetime(s, format="%Y%m%d", errors="coerce")


class Quality:
    def __init__(self, nav, groups):
        self.nav = nav.sort_values("NAVDate")
        self.codes = sorted(nav["FundCode"].unique())
        self.fam = {fc: fs.family_of(fc, groups, True)[0] for fc in self.codes}
        self.first_nav = nav.groupby("FundCode")["NAVDate"].min()
        reg = load_reg_dates()
        self.reg = reg.reindex(self.codes)

    def table(self, t):
        """DataFrame index=family: aum_fam, first_fam, pass_q1, pass_q2, aum_empty (ไม่มี AUM บวกใน 90 วัน)."""
        sub = self.nav[(self.nav["NAVDate"] <= t)]
        assert sub["NAVDate"].max() <= t
        pos = sub[(sub["AUM"] > 0) & (sub["NAVDate"] >= t - pd.Timedelta(days=AUM_STALE_DAYS))]
        aum_c = pos.groupby("FundCode")["AUM"].last()          # แถวล่าสุด (เรียง NAVDate แล้ว) ที่ AUM>0
        rows = []
        for fc in self.codes:
            cand = []
            fn = self.first_nav[fc]
            if fn <= t:
                cand.append(fn)
            rg = self.reg[fc]
            if pd.notna(rg) and rg <= t:
                cand.append(rg)
            rows.append((fc, self.fam[fc], float(aum_c.get(fc, 0.0)), min(cand) if cand else pd.NaT))
        d = pd.DataFrame(rows, columns=["FundCode", "family", "aum_c", "first_c"])
        g = d.groupby("family").agg(aum_fam=("aum_c", "sum"), first_fam=("first_c", "min"))
        g["pass_q1"] = g["aum_fam"] >= AUM_MIN
        g["pass_q2"] = g["first_fam"].notna() & (g["first_fam"] <= t - pd.Timedelta(days=AGE_DAYS))
        g["aum_empty"] = g["aum_fam"] <= 0
        return g, d


# ---------------- selection ----------------
def select_K(reps, ranks, held_map, skip_fams, n_target=SEL_N, k_drop=SEL_K):
    """เหมือน wt.hysteresis_select (dedupe=None) แต่ขั้น fill ข้าม family ใน skip_fams (กองที่หลุดเกณฑ์ ไม่ใช่กองใหม่)."""
    S, n_kept = {}, 0
    for fam, fc in held_map.items():
        if fam in reps and ranks.get(fam, 10**9) <= k_drop and reps[fam]["FundCode"] == fc:
            S[fam] = fc
            n_kept += 1
    for fam in sorted(reps.keys(), key=lambda f: ranks.get(f, 10**9)):
        if len(S) >= n_target:
            break
        if fam in S or fam in skip_fams:
            continue
        S[fam] = reps[fam]["FundCode"]
    return {"S": S, "n_kept": n_kept, "fallback": "b0" if len(S) < 4 else None}


def select_variant(ctx, held, prev_fb, qual, mode):
    """mode: 'off' (ไม่กรอง = M011) | 'S' | 'K' (+ 'offK' = ใช้เส้นทางโค้ด K โดยเกณฑ์ผ่านหมด สำหรับ regression)"""
    i_t = ctx["i_t"]
    H_map = {} if prev_fb else held
    held_funds = set(held.values())
    fam_ok = None
    if mode in ("S", "K"):
        fam_ok = set(qual.index[qual["pass_q1"] & qual["pass_q2"]])
    elif mode == "offK":
        fam_ok = set(i_t["family"])
    skip = set()
    if mode == "off":
        it = i_t
    elif mode == "S":
        it = i_t[i_t["family"].isin(fam_ok)]
    else:   # K / offK: ผ่านเกณฑ์ หรือเป็นกองถือต่อ (เฉพาะ class ที่ถือ)
        keep_rows = i_t["family"].isin(fam_ok) | (i_t["FundCode"].isin(set(H_map.values())))
        it = i_t[keep_rows]
    reps = wt.family_representatives(it, "SR12", held_funds=held_funds)
    ranks = wt.rank_families(reps)
    if mode in ("K", "offK"):
        skip = {f for f in reps if f not in fam_ok}
        sel = select_K(reps, ranks, H_map, skip)
        # ตรวจ: ถ้าไม่มี family นอกเกณฑ์ใน reps ต้องเหมือน wt.hysteresis_select ทุกประการ
        if not skip:
            ref = wt.hysteresis_select(reps, ranks, H_map, SEL_N, SEL_K, None, rho_max=0.85)
            assert ref["S"] == sel["S"], "select_K != hysteresis_select"
    else:
        sel = wt.hysteresis_select(reps, ranks, H_map, SEL_N, SEL_K, None, rho_max=0.85)
    fb = sel["fallback"] == "b0" or len(sel["S"]) == 0
    return {"S": dict(sel["S"]), "fallback": fb, "reps": reps, "ranks": ranks, "skip": skip}


def sig_of(rec):
    return "B0" if rec["fallback"] else tuple(sorted(rec["S"].values()))


def stream(ctxs, quals, mode, erc_cache):
    held, prev_fb = {}, False
    sleeves, recs = {}, []
    for ctx in ctxs:
        qi = ctx["qi"]
        rec = select_variant(ctx, held, prev_fb, quals[qi], mode)
        recs.append({"held_before": dict(held), "prev_fb": prev_fb, **rec})
        if rec["fallback"]:
            held, prev_fb = {}, True
            sleeves[qi] = ctx["b0_w"]
            continue
        held, prev_fb = dict(rec["S"]), False
        funds = list(rec["S"].values())
        key = (qi, tuple(funds))
        if key not in erc_cache:
            w, _ = wt.risk_parity_weights(funds, ctx["wk"], ctx["vol_map"], method="erc")
            erc_cache[key] = wt.apply_cap(w, 0.25)
        sleeves[qi] = erc_cache[key]
    return {"sleeves": sleeves, "recs": recs}


def to_plan(st, quarters15, calendar, acwi):
    return r9.make_plan({k: v for k, v in st["sleeves"].items() if k < 15}, quarters15, calendar, acwi)


def reg_vs_m011(plan):
    ref = pd.read_csv(os.path.join(RES, "M011-RFH_weights.csv"))
    ref = ref[ref["kind"] == "full"]
    refd = {(pd.Timestamp(r.t), r.FundCode): r.weight for r in ref.itertuples()}
    mine = r11.weights_map(plan)
    keys = set(refd) | set(mine)
    dmax = max(abs(refd.get(k, 0.0) - mine.get(k, 0.0)) for k in keys)
    only = [k for k in keys if (k in refd) != (k in mine)]
    return float(dmax), len(only), len(refd), len(mine)


def main():
    t0 = time.time()
    print("[1/8] load...", flush=True)
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
    assert months[-1] == r11.PE
    fd_sim = fees.FeeData(codes)
    real, _pol = rr.load_policy()
    rate = real.rate

    print("[2/8] prepare 16 quarters (cache pickle)...", flush=True)
    pk = os.path.join(SCRATCH, "validator_m012_ctxs.pkl")
    if os.path.exists(pk):
        ctxs = pickle.load(open(pk, "rb"))
    else:
        ctxs = r9.prepare(nav, nav_by_fund, calendar, groups, quarters16)
        pickle.dump(ctxs, open(pk, "wb"))
    h_by_q = {}
    for ctx in ctxs:
        ms = fs.month_end_points(calendar, ctx["t"], 13)
        h_by_q[ctx["qi"]] = r11.hurdle(rate, ms[0], ms[-2])
    ctx_h = r11.with_hurdle(ctxs, calendar, h_by_q)           # = ctx_new ของ M011

    print("[3/8] quality tables...", flush=True)
    Q = Quality(nav, groups)
    quals, qraw = [], []
    for ctx in ctx_h:
        g, d = Q.table(ctx["t"])
        quals.append(g)
        qraw.append(d)

    # ---------- spot check Q1/Q2 ----------
    spot = {}
    t16 = quarters16[15]
    g16 = quals[15]
    d16 = qraw[15]
    spot["t16"] = str(t16.date())
    spot["ES-GQG_aum_fam"] = float(g16.loc["ES-GQG", "aum_fam"]) if "ES-GQG" in g16.index else None
    cls = d16[d16["family"] == "ES-GQG"][["FundCode", "aum_c"]]
    spot["ES-GQG_classes"] = {r.FundCode: r.aum_c for r in cls.itertuples()}
    spot["ES-GQG_sum_ok"] = bool(abs(cls["aum_c"].sum() - spot["ES-GQG_aum_fam"]) < 1e-6) if spot["ES-GQG_aum_fam"] else False
    spot["DAOL-KOREAEQ_first_fam"] = str(g16.loc["DAOL-KOREAEQ", "first_fam"].date()) if "DAOL-KOREAEQ" in g16.index else None
    spot["DAOL-KOREAEQ_pass_q2"] = bool(g16.loc["DAOL-KOREAEQ", "pass_q2"]) if "DAOL-KOREAEQ" in g16.index else None
    spot["max_nav_date_used_le_t"] = True   # assert ใน Quality.table
    print("  spot:", json.dumps(spot, default=str), flush=True)

    # ---------- (A) regression ----------
    print("[4/8] (A) regression (เกณฑ์ปิด) ...", flush=True)
    erc_cache = {}
    ref_res = pd.read_csv(os.path.join(RES, "M011_results.csv")).set_index(["trial", "cost"])
    reg = {}
    sims_off = {}
    for tag, mode in (("S", "off"), ("K", "offK")):
        st = stream([c for c in ctx_h if c["qi"] < 15], quals, mode, erc_cache)
        plan = to_plan(st, quarters15, calendar, acwi)
        dmax, nonly, nref, nmine = reg_vs_m011(plan)
        sims_r = r11.sims_real(plan, nav_by_fund, months, fd_sim, real)
        sh = {k: rr.metrics(sims_r[k]["values"], real)["sharpe"] for k in ("c0", "c50", "flat", "full", "nofront")}
        refsh = {k: float(ref_res.loc[("M011-RFH", k), "sharpe_real"]) for k in sh}
        ok_s = all(abs(sh[k] - refsh[k]) < 5e-7 for k in sh)
        reg[tag] = {"mode": mode, "max_dw": dmax, "n_only_one_side": nonly, "n_rows_ref": nref, "n_rows_mine": nmine,
                    "sharpe": sh, "sharpe_ref": refsh, "ok_w": bool(dmax < 1e-9 and nonly == 0), "ok_s": bool(ok_s)}
        sims_off[tag] = (st, plan, sims_r)
    # ตรวจ stream เดิมของ r9 บน ctx เดียวกัน (เกณฑ์ปิด) = sleeves ของเรา
    st_ref = r9.select_stream([c for c in ctx_h if c["qi"] < 15], False, fees.FeeData(codes), acwi, {})
    reg["sleeves_equal_r9"] = bool(all(set(st_ref["sleeves"][q].index) == set(sims_off["S"][0]["sleeves"][q].index) and
                                       np.allclose(st_ref["sleeves"][q].sort_index().to_numpy(),
                                                   sims_off["S"][0]["sleeves"][q].sort_index().to_numpy(), atol=1e-12) for q in range(15)))
    reg["ok_all"] = bool(reg["S"]["ok_w"] and reg["S"]["ok_s"] and reg["K"]["ok_w"] and reg["K"]["ok_s"] and reg["sleeves_equal_r9"])
    reg["spot"] = spot
    print("  REGRESSION:", json.dumps(reg, default=float), flush=True)
    json.dump(reg, open(os.path.join(SCRATCH, "validator_m012_regression.json"), "w"), default=float)
    if not reg["ok_all"]:
        print("REGRESSION FAIL — หยุด (ไม่นับ trial)", flush=True)
        return 2

    print("[5/8] (B) รัน S / K ...", flush=True)
    base_st, base_plan, base_sims_r = sims_off["S"]
    # full 16-quarter walk ของ baseline และตัวแปร
    st_base16 = stream(ctx_h, quals, "off", erc_cache)
    out = {}
    for tag, mode in (("S", "S"), ("K", "K")):
        st16 = stream(ctx_h, quals, mode, erc_cache)
        plan = to_plan(st16, quarters15, calendar, acwi)
        sims_r = r11.sims_real(plan, nav_by_fund, months, fd_sim, real)
        sims_c = r9.sim_cases(plan, nav_by_fund, months, fd_sim)
        out[tag] = {"st": st16, "plan": plan, "sims_r": sims_r, "sims_c": sims_c}
    sims_base_c = r9.sim_cases(base_plan, nav_by_fund, months, fd_sim)

    print("[6/8] metrics + diagnostics...", flush=True)
    kinds = ["c0", "c50", "flat", "full", "nofront"]
    MRb = {k: rr.metrics(base_sims_r[k]["values"], real) for k in kinds}
    rb, rfm = MRb["full"]["r"], MRb["full"]["rfm"]
    ci_b = rr.boot_ci(rb, rfm)
    dsr_b = rr.dsr_s(rb, rfm, N_TRIALS_FINAL)
    base_sets = [sig_of(r) for r in st_base16["recs"]]
    res = {}
    qd_all, pl_all = {}, {}
    for tag in ("S", "K"):
        o = out[tag]
        MR = {k: rr.metrics(o["sims_r"][k]["values"], real) for k in kinds}
        MC = {k: rr.metrics(o["sims_c"][k]["values"], 0.02) for k in kinds}
        rn = MR["full"]["r"]
        d_lo, d_hi, d_pt = r11.paired_real(rn, rb, rfm, "r")
        ci_n = rr.boot_ci(rn, rfm)
        dsr25 = rr.dsr_s(rn, rfm, N_TRIALS_FINAL)
        dsr_own = rr.dsr_s(rn, rfm, 24 if tag == "S" else 25)
        recs = o["st"]["recs"]
        rows, diff_q, direct_q, inherit_q = [], [], [], []
        for q in range(16):
            ctx = ctx_h[q]
            g = quals[q]
            it = ctx["i_t"]
            fams = sorted(set(it["family"]))
            gi = g.reindex(fams)
            n_I = len(fams)
            n_pass = int((gi["pass_q1"] & gi["pass_q2"]).sum())
            n_cut_q1 = int((~gi["pass_q1"] & gi["pass_q2"]).sum())
            n_cut_q2 = int((gi["pass_q1"] & ~gi["pass_q2"]).sum())
            n_cut_both = int((~gi["pass_q1"] & ~gi["pass_q2"]).sum())
            n_aum_empty = int((gi["aum_empty"]).sum())
            rec = recs[q]
            sel_f = list(rec["S"].keys()) if not rec["fallback"] else []
            min_aum = float(min(g.loc[f, "aum_fam"] for f in sel_f)) if sel_f else np.nan
            min_aum_f = min(sel_f, key=lambda f: g.loc[f, "aum_fam"]) if sel_f else ""
            brec = st_base16["recs"][q]
            bsel = list(brec["S"].keys()) if not brec["fallback"] else []
            b_min_aum = float(min(g.loc[f, "aum_fam"] for f in bsel)) if bsel else np.nan
            # ตรงๆ: select ด้วยเกณฑ์ + สถานะถือของ M011 ณ t
            dirrec = select_variant(ctx, brec["held_before"], brec["prev_fb"], g, tag)
            s_dir, s_b, s_n = sig_of(dirrec), base_sets[q], sig_of(rec)
            is_dir, is_diff = s_dir != s_b, s_n != s_b
            if q < 15:
                if is_diff:
                    diff_q.append(q)
                if is_dir:
                    direct_q.append(q)
                if is_diff and not is_dir:
                    inherit_q.append(q)
            # กองที่ถูกขาย/กันไว้เพราะเกณฑ์ (ต่อจากสถานะถือของ variant เอง)
            held = rec["held_before"] if not rec["prev_fb"] else {}
            reps0 = wt.family_representatives(it, "SR12", held_funds=set(rec["held_before"].values()))
            ranks0 = wt.rank_families(reps0)
            fails = lambda f: (f in g.index) and not (g.loc[f, "pass_q1"] and g.loc[f, "pass_q2"])
            crit_held = [f"{fc}" for f, fc in held.items() if f in reps0 and reps0[f]["FundCode"] == fc and ranks0[f] <= SEL_K and fails(f)]
            if tag == "S":
                sold = crit_held   # S: กองถือที่ยังควรถือต่อตามอันดับ แต่หลุดเกณฑ์ -> ขาย
                kept_fail = []
            else:
                sold = []
                kept_fail = [fc for f, fc in rec["S"].items() if fails(f)] if not rec["fallback"] else []
            rows.append({"qi": q, "t": ctx["t"].date(), "in_plan15": q < 15, "n_family_I": n_I, "n_pass": n_pass,
                         "n_cut_Q1_only": n_cut_q1, "n_cut_Q2_only": n_cut_q2, "n_cut_both": n_cut_both, "n_aum_empty90": n_aum_empty,
                         "fallback_B0": bool(rec["fallback"]), "min_aum_fam_port_MBaht": min_aum / 1e6 if min_aum == min_aum else np.nan,
                         "min_aum_family": min_aum_f, "min_aum_fam_M011_port_MBaht": b_min_aum / 1e6 if b_min_aum == b_min_aum else np.nan,
                         "sold_due_to_criteria": ";".join(sold), "kept_failing_K": ";".join(kept_fail),
                         "diff_direct": is_dir, "diff_final": is_diff,
                         "set_m011": ";".join(sorted(s_b)) if s_b != "B0" else "B0",
                         "set_m012": ";".join(sorted(s_n)) if s_n != "B0" else "B0"})
        QD = pd.DataFrame(rows)
        qd_all[tag] = QD
        # path luck
        es = [p["e"] for p in o["plan"]]
        qm = pd.Series([max(0, int(np.searchsorted(np.array(es, dtype="datetime64[ns]"), np.datetime64(m), side="left")) - 1) for m in rn.index], index=rn.index)
        dret = rn - rb
        same_mask = qm.map(lambda q: q not in diff_q)
        per_q = dret.groupby(qm).sum()
        ptab = pd.DataFrame({"sum_dret": per_q, "n_months": qm.groupby(qm).size()})
        ptab["diff_set"] = [q in diff_q for q in ptab.index]
        ptab["t"] = [quarters15[q].date() for q in ptab.index]
        pl_all[tag] = ptab
        best_q = int(per_q.idxmax()) if len(per_q) else None
        worst_q = int(per_q.idxmin()) if len(per_q) else None
        keep = qm != best_q
        sh_drop_n = rr.sharpe_s(rn[keep], rfm.reindex(rn.index)[keep]); sh_drop_b = rr.sharpe_s(rb[keep], rfm.reindex(rb.index)[keep])
        res[tag] = {"MR": MR, "MC": MC, "d": (d_lo, d_hi, d_pt), "ci": ci_n, "dsr25": dsr25, "dsr_own": dsr_own,
                    "n_diff": len(diff_q), "n_direct": len(direct_q), "n_inherit": len(inherit_q), "diff_q": diff_q,
                    "dsum_same": float(dret[same_mask].sum()), "dsum_diff": float(dret[~same_mask].sum()),
                    "n_m_same": int(same_mask.sum()), "n_m_diff": int((~same_mask).sum()),
                    "best_q": best_q, "worst_q": worst_q, "drop_best": (float(sh_drop_n), float(sh_drop_b)),
                    "n_fb": int(sum(1 for r in recs[:15] if r["fallback"])),
                    "verdict": "ผ่าน (ดีกว่าอย่างมีนัย)" if (d_pt >= 0 and d_lo > 0) else ("ผ่าน" if d_pt >= 0 else "ไม่ผ่าน"),
                    "p16": ";".join(sorted(sig_of(recs[15]))) if not recs[15]["fallback"] else "B0",
                    "p16_m011": ";".join(sorted(base_sets[15])) if base_sets[15] != "B0" else "B0"}
        if res[tag]["n_diff"] == 0:
            res[tag]["verdict"] = "ไม่มีผล (ชุดกอง = M011 ทุกไตรมาส) · " + res[tag]["verdict"]
        print(f"  {tag}: dSharpe {d_pt:+.4f} [{d_lo:+.3f},{d_hi:+.3f}] full={MR['full']['sharpe']:.4f} diff {len(diff_q)}/15", flush=True)

    # ---------- เขียนไฟล์ ----------
    print("[7/8] write outputs...", flush=True)
    eq = pd.DataFrame({"M011-RFH_full_real": base_sims_r["full"]["values"],
                       "M012-QF-S_full_real": out["S"]["sims_r"]["full"]["values"], "M012-QF-K_full_real": out["K"]["sims_r"]["full"]["values"],
                       "M011-RFH_c0_real": base_sims_r["c0"]["values"], "M012-QF-S_c0_real": out["S"]["sims_r"]["c0"]["values"],
                       "M012-QF-K_c0_real": out["K"]["sims_r"]["c0"]["values"]})
    eq.to_csv(os.path.join(RES, "M012_equity_curve.csv"))
    wrows = []
    for tag in ("S", "K"):
        for en in out[tag]["sims_r"]["full"]["entries"]:
            for f, w in en["target"].items():
                if w > 1e-12:
                    wrows.append({"trial": f"M012-QF-{tag}", "t": en["t"].date() if hasattr(en["t"], "date") else en["t"],
                                  "e": en["e"].date(), "kind": en["mode"], "FundCode": f, "weight": w})
    pd.DataFrame(wrows).to_csv(os.path.join(RES, "M012_weights.csv"), index=False)
    pd.concat([qd_all["S"].assign(variant="S"), qd_all["K"].assign(variant="K")]).to_csv(os.path.join(RES, "M012_quarter_diag.csv"), index=False)
    pd.concat([pl_all["S"].assign(variant="S"), pl_all["K"].assign(variant="K")]).to_csv(os.path.join(RES, "M012_path_luck_by_quarter.csv"))
    summ = []
    for name, MRx, sr, MCx, sc in (("M011-RFH", None, base_sims_r, None, sims_base_c),
                                   ("M012-QF-S", res["S"]["MR"], out["S"]["sims_r"], res["S"]["MC"], out["S"]["sims_c"]),
                                   ("M012-QF-K", res["K"]["MR"], out["K"]["sims_r"], res["K"]["MC"], out["K"]["sims_c"])):
        for k in kinds:
            mr_ = MRb[k] if MRx is None else MRx[k]
            mc_ = rr.metrics(sc[k]["values"], 0.02)
            summ.append({"trial": name, "cost": k, "sharpe_real": mr_["sharpe"], "cagr_real": mr_["cagr"], "vol_real": mr_["vol"],
                         "maxdd_real": mr_["max_dd"], "sharpe_2022_real": mr_["sharpe_2022"], "sharpe_2307_2512_real": mr_["sharpe_2307_2512"],
                         "sharpe_rf2": mc_["sharpe"], "cost_bp_yr_real": sr[k]["cost_bp_yr"], "turn_yr": sr[k]["turn_yr"]})
    pd.DataFrame(summ).to_csv(os.path.join(RES, "M012_results.csv"), index=False)

    write_md(res, MRb, ci_b, dsr_b, base_sims_r, out, qd_all, pl_all, quarters15, reg, spot, kinds, MRb)
    json.dump({t: {"d": res[t]["d"], "n_diff": res[t]["n_diff"], "dsr25": res[t]["dsr25"], "ci": res[t]["ci"], "verdict": res[t]["verdict"],
                   "sharpe": {k: res[t]["MR"][k]["sharpe"] for k in kinds}} for t in ("S", "K")},
              open(os.path.join(SCRATCH, "validator_m012_summary.json"), "w"), default=float)
    print("[8/8] trials.csv / ALL_RESULTS...", flush=True)
    global PHASE_B
    PHASE_B = True
    append_logs(res, out, MRb, dsr_b)
    print(f"DONE in {time.time()-t0:.0f}s", flush=True)
    return 0


def write_md(res, MRb, ci_b, dsr_b, base_sims_r, out, qd_all, pl_all, quarters15, reg, spot, kinds, MR_b):
    L = []
    A = L.append
    f3 = lambda x: f"{x:.3f}"
    base_stats = pd.read_csv(os.path.join(RES, "REAL_RF_summary.csv")).set_index("trial")
    mb = MRb["full"]
    A("# M012-QF — เกณฑ์คุณภาพ (AUM_fam ≥ 100 ล้านบาท + อายุแบบ B ≥ 730 วัน) บน M011-RFH — ผลวัด (validator)\n")
    A(f"รันเมื่อ {pd.Timestamp.now().isoformat()} · spec `specs/M012_quality_filter.md` + การตัดสินใจผู้ใช้ 2026-10-06 (อายุแบบ B · 2 ทางเลือก = trial 24 (S) และ 25 (K)) · "
      "primary เม.ย. 2022–2025-12-31 (45 เดือน) · วัดด้วย **rf จริง** (นโยบาย ธปท.) ตาม `remeasure_real_rf.py` (ตัวหาร sd(r)) ทุกแขน · baseline = M011-RFH · ไม่มี holdout\n")
    A("- **S** = กองที่ถือต่อและหลุดเกณฑ์ → ขาย · **K** = เกณฑ์ใช้เฉพาะเติมกองใหม่ (กองถือต่อไม่ถูกตัดด้วยเกณฑ์ ยังหลุดได้ตามกติกาเดิม: NAV ไม่สด/อันดับ > K) · รายงานทั้งคู่ ไม่เลือกตัวที่ดีกว่า\n")
    A("## 1. Spot check Registration_date + regression\n")
    A("- Spot check `FundProfile.csv` (570/570 class ใน NAV มีแถว, ไม่ซ้ำ, ไม่ว่าง, รูปแบบ YYYYMMDD ทั้งหมด parse ได้) · Registration_date > NAV แรก 131 class แต่ **ห่างสูงสุด 18 วัน (median 2 วัน)** "
      "— ไม่ใช่ median 145 วันตามที่ spec ระบุ (ไม่กระทบเพราะใช้ min กับ NAV แรก) · Reg < NAV แรก 439 class (class เก่าที่ไฟล์ NAV เริ่ม ธ.ค. 2020 หรือ NAV มาทีหลัง) · `scratch/validator_m012_regdate.py`")
    A(f"- AUM หน่วยบาท: ES-GQG family AUM_fam ณ {spot['t16']} = {spot['ES-GQG_aum_fam']:.4e} (= ผลรวม class {'✓' if spot['ES-GQG_sum_ok'] else '✗'}) · "
      f"DAOL-KOREAEQ first_fam = {spot['DAOL-KOREAEQ_first_fam']} ผ่านอายุ = {spot['DAOL-KOREAEQ_pass_q2']} · Q1/Q2 ใช้แถว NAVDate ≤ t เท่านั้น (assert ในโค้ด)")
    for tag in ("S", "K"):
        r = reg[tag]
        A(f"- Regression ({tag}, เกณฑ์ปิด, เส้นทางโค้ด {'wt.hysteresis_select' if tag == 'S' else 'select_K'}): น้ำหนักเทียบ `M011-RFH_weights.csv` max|Δw| = {r['max_dw']:.2e} "
          f"(แถว {r['n_rows_ref']} vs {r['n_rows_mine']}, คีย์ฝั่งเดียว {r['n_only_one_side']}) → **{'PASS' if r['ok_w'] else 'FAIL'}** · Sharpe c0/c50/flat/full/nofront ตรง `M011_results.csv` (<5e-7) → **{'PASS' if r['ok_s'] else 'FAIL'}** (full {r['sharpe']['full']:.6f})")
    A(f"- sleeves จาก stream ใหม่ (เกณฑ์ปิด) = `r9.select_stream` เดิม: {'PASS' if reg['sleeves_equal_r9'] else 'FAIL'}\n")
    A("## 2. ตารางหลัก (ค่าธรรมเนียมจริง full, rf จริง, ตัวหาร sd(r))\n")
    A("| โมเดล | Sharpe | CAGR | vol | maxDD | Sharpe 2022 | Sharpe 2023-07..25 | cost bp/ปี | turnover/ปี | CI95% Sharpe | DSR@25 |")
    A("|---|---|---|---|---|---|---|---|---|---|---|")
    for tag in ("S", "K"):
        m = res[tag]["MR"]["full"]; so = out[tag]["sims_r"]["full"]
        A(f"| **M012-QF-{tag}** | {m['sharpe']:.3f} | {m['cagr']:.4f} | {m['vol']:.4f} | {m['max_dd']:.4f} | {m['sharpe_2022']:.3f} | {m['sharpe_2307_2512']:.3f} | "
          f"{so['cost_bp_yr']:.1f} | {so['turn_yr']:.3f} | [{res[tag]['ci'][0]:.2f}, {res[tag]['ci'][1]:.2f}] | {res[tag]['dsr25']:.4f} |")
    A(f"| M011-RFH | {mb['sharpe']:.3f} | {mb['cagr']:.4f} | {mb['vol']:.4f} | {mb['max_dd']:.4f} | {mb['sharpe_2022']:.3f} | {mb['sharpe_2307_2512']:.3f} | "
      f"{base_sims_r['full']['cost_bp_yr']:.1f} | {base_sims_r['full']['turn_yr']:.3f} | [{ci_b[0]:.2f}, {ci_b[1]:.2f}] | {dsr_b:.4f} |")
    r = base_stats.loc["B0"]
    A(f"| B0 (rf จริง, `REAL_RF_summary.csv`, ไม่ได้ตรวจซ้ำเอง) | {r['sharpe_full_real']:.3f} | {r['cagr_full_real']:.4f} | {r['vol_full_real']:.4f} | {r['max_dd_full_real']:.4f} | "
      f"{r['sharpe_2022_full_real']:.3f} | {r['sharpe_2307_2512_full_real']:.3f} | — | — | [{r['ci_lo_real']:.2f}, {r['ci_hi_real']:.2f}] | {r['dsr22_real']:.4f} (@22) |")
    A("\n(DSR@25 = นับ 2 trials ของ M012 · DSR@24 ของ S = " + f"{res['S']['dsr_own']:.4f}" + ")\n")
    A("## 3. ตัวชี้วัดหลัก + เกณฑ์ (ล็อก: ผ่าน = Δ Sharpe full ≥ 0 · ไม่ผ่าน = ไม่ใช้เกณฑ์คุณภาพ)\n")
    for tag in ("S", "K"):
        d = res[tag]["d"]
        A(f"- **{tag}: Δ Sharpe_full (M012-QF-{tag} − M011-RFH) = {d[2]:+.4f}** · CI95% paired block bootstrap (block 3, 2000, seed 0) [{d[0]:+.3f}, {d[1]:+.3f}] "
          f"({'คร่อม 0' if d[0] <= 0 <= d[1] else 'ไม่คร่อม 0'}) · **ผลตามเกณฑ์: {res[tag]['verdict']}**")
    A("")
    A("## 4. ตารางต้นทุน (rf จริง)\n")
    A("| ต้นทุน | S Sharpe | S CAGR | S vol | S maxDD | K Sharpe | K CAGR | K vol | K maxDD | M011 Sharpe | M011 CAGR | M011 vol | M011 maxDD |")
    A("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    lab = {"c0": "0%", "c50": "0.5%/ข้าง", "flat": "flat 0.5% (fee model)", "full": "ค่าธรรมเนียมจริง full", "nofront": "nofront"}
    for k in kinds:
        a, b, c = res["S"]["MR"][k], res["K"]["MR"][k], MRb[k]
        A(f"| {lab[k]} | {a['sharpe']:.3f} | {a['cagr']:.4f} | {a['vol']:.4f} | {a['max_dd']:.4f} | {b['sharpe']:.3f} | {b['cagr']:.4f} | {b['vol']:.4f} | {b['max_dd']:.4f} | "
          f"{c['sharpe']:.3f} | {c['cagr']:.4f} | {c['vol']:.4f} | {c['max_dd']:.4f} |")
    A(f"\n- cost bp/ปี c50: S {out['S']['sims_r']['c50']['cost_bp_yr']:.1f} · K {out['K']['sims_r']['c50']['cost_bp_yr']:.1f} · M011 {base_sims_r['c50']['cost_bp_yr']:.1f} · "
      f"turnover/ปี (full): S {out['S']['sims_r']['full']['turn_yr']:.3f} · K {out['K']['sims_r']['full']['turn_yr']:.3f} · M011 {base_sims_r['full']['turn_yr']:.3f}\n")
    A("## 5. จำนวน family ต่อไตรมาส (ใน I_t ของ M011; ตัดด้วยเกณฑ์) + AUM ต่ำสุดในพอร์ต\n")
    QDs = qd_all["S"]
    A("| t | family ใน I_t | ผ่านทั้งคู่ | ตัดเพราะ AUM เท่านั้น | ตัดเพราะอายุเท่านั้น | ตัดทั้งคู่ | AUM_fam=0 (>90 วัน) |")
    A("|---|---|---|---|---|---|---|")
    for r in QDs.itertuples():
        A(f"| {r.t}{'' if r.in_plan15 else ' (หน้า 9)'} | {r.n_family_I} | {r.n_pass} | {r.n_cut_Q1_only} | {r.n_cut_Q2_only} | {r.n_cut_both} | {r.n_aum_empty90} |")
    A("")
    A("AUM_fam ต่ำสุดในพอร์ต (ล้านบาท) และชุดกองต่างจาก M011:\n")
    A("| t | M011 | S (ต่ำสุด · family) | K (ต่ำสุด · family) | S B0? | K B0? | S ชุดต่าง (ตรง/สืบทอด) | K ชุดต่าง (ตรง/สืบทอด) |")
    A("|---|---|---|---|---|---|---|---|")
    QDk = qd_all["K"]
    for rs, rk in zip(QDs.itertuples(), QDk.itertuples()):
        def dd(r):
            return ("ต่าง-ตรง" if r.diff_direct else "ต่าง-สืบทอด") if r.diff_final else "-"
        A(f"| {rs.t} | {rs.min_aum_fam_M011_port_MBaht:,.0f} | {rs.min_aum_fam_port_MBaht:,.0f} · {rs.min_aum_family} | {rk.min_aum_fam_port_MBaht:,.0f} · {rk.min_aum_family} | "
          f"{'B0' if rs.fallback_B0 else '-'} | {'B0' if rk.fallback_B0 else '-'} | {dd(rs)} | {dd(rk)} |")
    A("")
    for tag in ("S", "K"):
        x = res[tag]
        A(f"- **{tag}**: ชุดกองต่างจาก M011 {x['n_diff']}/15 ไตรมาส (ตรงๆ {x['n_direct']}, สืบทอดผ่าน hysteresis {x['n_inherit']}) · ไตรมาสที่ตก fallback B0 (ใน 15): {x['n_fb']} · "
          f"พอร์ต 2025-12-31 (หน้า 9) M012 = [{x['p16']}] · M011 = [{x['p16_m011']}]")
    A("")
    A("## 6. กลไก — กองที่ถูกตัด (ต่อไตรมาส)\n")
    A("**S: กองที่ถือต่อ (ยังอยู่ในอันดับ ≤ K) แต่หลุดเกณฑ์ → ถูกขาย** · **K: กองที่ยังถืออยู่ทั้งที่หลุดเกณฑ์**\n")
    A("| t | S: ขายเพราะหลุดเกณฑ์ | K: ถือต่อทั้งที่หลุดเกณฑ์ | S ชุดกอง | K ชุดกอง | M011 ชุดกอง |")
    A("|---|---|---|---|---|---|")
    for rs, rk in zip(QDs.itertuples(), QDk.itertuples()):
        if rs.diff_final or rk.diff_final or rs.sold_due_to_criteria or rk.kept_failing_K:
            A(f"| {rs.t} | {rs.sold_due_to_criteria or '-'} | {rk.kept_failing_K or '-'} | {rs.set_m012} | {rk.set_m012} | {rs.set_m011} |")
    A("")
    A("## 7. Path luck\n")
    for tag in ("S", "K"):
        x = res[tag]
        A(f"- **{tag}**: Σ(r_M012 − r_M011) เดือนในไตรมาสชุดกอง**เหมือน** {x['dsum_same']:+.4f} ({x['n_m_same']} เดือน) · **ต่าง** {x['dsum_diff']:+.4f} ({x['n_m_diff']} เดือน) · "
          f"ตัดไตรมาสที่ผลต่างบวกสุด ({quarters15[x['best_q']].date()}) → Sharpe M012 {x['drop_best'][0]:.3f} vs M011 {x['drop_best'][1]:.3f} Δ {x['drop_best'][0]-x['drop_best'][1]:+.3f} "
          f"· ไตรมาสลบสุด {quarters15[x['worst_q']].date()}")
        pt = pl_all[tag]
        A("\n| ไตรมาส t | Σ Δr | ชุดกองต่าง |\n|---|---|---|")
        for r in pt.itertuples():
            A(f"| {r.t} | {r.sum_dret:+.4f} | {'ต่าง' if r.diff_set else 'เหมือน'} |")
        A("")
    A("## 8. สมมติฐาน / ที่ validator ตีความเอง\n")
    for s in [
        "family = `fs.family_of(fc, groups, fixed=True)` (map เดียวกับ I_t) · AUM_fam = Σ AUM ล่าสุด>0 ภายใน 90 วันของ **ทุก class ของ family ในไฟล์ NAV (570 class)** รวม class ภาษี/ปันผล/ไม่สด · AUM ในหน่วยบาท",
        "อายุแบบ B: first_c = min(Registration_date ถ้า ≤ t, NAVDate แรก ถ้า ≤ t) · first_fam = min ข้าม class · ผ่านถ้า ≤ t − 730 วัน · class ที่ไม่มีค่าใดๆ ≤ t ไม่นับ (NAVDate แรก = ทั้งไฟล์ ไม่กรอง 2021)",
        "I_t' = แถวของ I_t (หลังใส่ SR12′ ของ M011 และตัดสด/ภาษี/-D/สัญญาณ) ที่ family ผ่าน Q1 และ Q2 · S: กรองก่อน `family_representatives` และ rank · fallback B0 ใช้ `b0_w` เดิมไม่กรอง",
        "K: reps = family ที่ผ่านเกณฑ์ + class ที่ถืออยู่ (แม้หลุดเกณฑ์) · อันดับคำนวณรวมกองถือต่อที่หลุดเกณฑ์ · กองถือต่อที่หลุดเกณฑ์ยังหลุดได้ด้วยอันดับ > K / ไม่สด · ขั้น fill ข้าม family ที่หลุดเกณฑ์ (ไม่เติมกองหลุดเกณฑ์ซ้ำแม้เคยถือ) · ถ้า S < 4 → B0 เหมือนเดิม · ตรวจ select_K = `wt.hysteresis_select` เมื่อไม่มี family หลุดเกณฑ์ (assert)",
        "'ต่างตรงๆ' = select ด้วยเกณฑ์ + สถานะถือ/prev_fb ของ M011 ณ t เทียบชุดกองของ M011 ณ t · 'ต่างจริง' = ชุดกองใน plan เทียบ M011 · สืบทอด = ต่างจริงแต่ไม่ต่างตรงๆ (เทียบชุด FundCode)",
        "'ขายเพราะหลุดเกณฑ์' (S) = family ที่ถือก่อน t, class ตัวแทนยังเป็น class ที่ถือ, อันดับ (ไม่กรอง ภายใต้สถานะถือของ S) ≤ K แต่หลุด Q1/Q2 · เป็นการประมาณเหตุผลเพื่ออธิบาย ไม่ใช่ counterfactual เต็ม",
        "Δ paired CI: `r11.paired_real` (block 3, 2000, seed 0, rf จริงรายเดือน, ตัวหาร sd(r)) · DSR = `rr.dsr_s` ที่ n_trials = 25 (นับ 2 trials ของ M012) · ต้นทุน/ERC/เพดาน/trend filter/ตารางเวลา/FeeModel เหมือน M011 (import run_m009/run_m011)",
        "พอร์ต 2025-12-31 (ไตรมาสที่ 16) ไม่อยู่ใน 45 เดือนที่วัด",
    ]:
        A(f"- {s}")
    A("\n## 9. ไฟล์\n`M012_results.csv`, `M012_equity_curve.csv`, `M012_weights.csv`, `M012_quarter_diag.csv`, `M012_path_luck_by_quarter.csv`, `scratch/validator_m012_regression.json`, `scratch/validator_m012_regdate.py`")
    open(os.path.join(RES, "M012_results.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")


def append_logs(res, out, MRb, dsr_b):
    now = pd.Timestamp.now().isoformat()
    txt = open(TRIALS_CSV, encoding="utf-8", newline="").read()
    assert "M012-QF-S," not in txt and "M012-QF-K," not in txt
    p = os.path.join(RES, "ALL_RESULTS.csv")
    atxt = open(p, encoding="utf-8", newline="").read()
    assert "M012-QF-S," not in atxt
    ncol = len(atxt.splitlines()[0].split(","))
    for tag, n in (("S", 24), ("K", 25)):
        MR, MC, x = res[tag]["MR"], res[tag]["MC"], res[tag]
        d = x["d"]
        mn = MR["full"]
        so = out[tag]["sims_r"]["full"]
        name = f"M012-QF-{tag}"
        desc = "ขาย: กองถือต่อที่หลุดเกณฑ์ถูกขาย" if tag == "S" else "ไม่ขาย: เกณฑ์ใช้เฉพาะเติมกองใหม่"
        params = (f"{name}: M011-RFH + quality filter AUM_fam>=100M THB (sum all classes; last positive AUM within 90d) + age B (min(Registration_date;first NAV)>=730d); "
                  f"{desc}; N=8;K=16;ERC LW;cap25%;trend cash25%;measure=real policy rf;fee=FEEUH full PIT;primary=2022-03..2025-12")
        note = (f"{name} {desc}; Sharpe (real rf; sd(r)): 0%={MR['c0']['sharpe']:.3f} 0.5%={MR['c50']['sharpe']:.3f} full={mn['sharpe']:.3f} nofront={MR['nofront']['sharpe']:.3f}; "
                f"rf2 full={MC['full']['sharpe']:.4f}; paired dSharpe full vs M011-RFH({MRb['full']['sharpe']:.4f}) {d[2]:+.4f} CI ({d[0]:.3f};{d[1]:.3f}); "
                f"quarters set differs {x['n_diff']}/15 (direct {x['n_direct']} inherited {x['n_inherit']}); CI95 ({x['ci'][0]:.3f};{x['ci'][1]:.3f}); "
                f"DSR@25={x['dsr25']:.4f} (DSR@{n}={x['dsr_own']:.4f}); verdict={x['verdict']}; n_months=45; sharpe column = REAL rf not 2%; deflated_sharpe column = DSR@25 (2 M012 trials counted)")
        vals = [name, now, "M012_quality_filter.md", params, "2022-03-31", "2025-12-31", "BOT policy rate daily (TH_POLICY_RATE.csv)",
                "real fees SecFundFee FEEUH (full)", round(mn["sharpe"], 4), round(mn["cagr"], 4), round(mn["vol"], 4), round(mn["max_dd"], 4),
                round(so["turn_yr"], 4), n, round(x["dsr25"], 4), "ok", note]
        line = ",".join(str(v).replace(",", ";") for v in vals)
        txt = open(TRIALS_CSV, encoding="utf-8", newline="").read()
        with open(TRIALS_CSV, "a", encoding="utf-8", newline="") as f:
            if not txt.endswith("\n"):
                f.write("\r\n")
            f.write(line + "\r\n")
        g = lambda c, k: MC[c][k]
        sc = out[tag]["sims_c"]
        allv = ["M012", name, f"M011-RFH + quality filter AUM>=100M & age B ({desc}) (measured with real rf)", "new", "no",
                f"{MC['c0']['sharpe']:.3f}", f"{MC['c50']['sharpe']:.3f}", "", f"{g('c50','cagr'):.3f}", f"{g('c50','vol'):.3f}", f"{g('c50','max_dd'):.3f}", "",
                f"{MC['full']['sharpe']:.4f}", f"{MC['nofront']['sharpe']:.4f}", f"{g('full','cagr'):.4f}", f"{sc['full']['cost_bp_yr']:.1f}",
                f"{MR['full']['sharpe']:.4f}", f"{MR['nofront']['sharpe']:.4f}", f"{MR['flat']['sharpe']:.4f}", f"{MR['c0']['sharpe']:.4f}",
                f"{MR['full']['cagr']:.4f}", f"{MR['full']['max_dd']:.4f}", f"{MR['full']['sharpe_2022']:.4f}", f"{x['dsr25']:.4f}"]
        assert len(allv) == ncol, (len(allv), ncol)
        atxt = open(p, encoding="utf-8", newline="").read()
        with open(p, "a", encoding="utf-8", newline="") as f:
            if not atxt.endswith("\n"):
                f.write("\n")
            f.write(",".join(allv) + "\n")
    mdp = os.path.join(RES, "ALL_RESULTS.md")
    with open(mdp, "a", encoding="utf-8") as f:
        f.write(f"\n## M012-QF-S / M012-QF-K (เพิ่ม {pd.Timestamp.now().date()}, trial ที่ 24 และ 25)\n"
                f"- M011-RFH + เกณฑ์คุณภาพ AUM_fam ≥ 100 ล้านบาท + อายุแบบ B ≥ 730 วัน · S = ขายกองถือที่หลุดเกณฑ์, K = เกณฑ์ใช้เฉพาะเติมกองใหม่ · **วัดด้วย rf จริง** "
                f"(คอลัมน์ rf 2% = วัดแบบเดิม, คอลัมน์ `realrf` = rf จริง, `dsr_n22_fee_full_realrf` ของ 2 แถวนี้ = DSR@25)\n"
                f"- Sharpe full (rf จริง): M011 {MRb['full']['sharpe']:.3f} · S {res['S']['MR']['full']['sharpe']:.3f} (Δ {res['S']['d'][2]:+.4f} CI [{res['S']['d'][0]:+.3f}, {res['S']['d'][1]:+.3f}] · {res['S']['verdict']}) · "
                f"K {res['K']['MR']['full']['sharpe']:.3f} (Δ {res['K']['d'][2]:+.4f} CI [{res['K']['d'][0]:+.3f}, {res['K']['d'][1]:+.3f}] · {res['K']['verdict']}) · รายละเอียด `M012_results.md`\n")


if __name__ == "__main__":
    try:
        rc = main()
    except Exception:
        tb = traceback.format_exc()
        print(tb, flush=True)
        try:
            txt = open(TRIALS_CSV, encoding="utf-8", newline="").read()
            if PHASE_B and "M012-QF-S," not in txt:
                last = tb.strip().splitlines()[-1].replace(",", ";")[:200]
                for name, n in (("M012-QF-S", 24), ("M012-QF-K", 25)):
                    vals = [name, pd.Timestamp.now().isoformat(), "M012_quality_filter.md", f"{name} run crashed", "2022-03-31", "2025-12-31",
                            "BOT policy rate daily (TH_POLICY_RATE.csv)", "real fees SecFundFee FEEUH (full)", "", "", "", "", "", n, "", "crashed", last]
                    with open(TRIALS_CSV, "a", encoding="utf-8", newline="") as f:
                        f.write(",".join(str(v) for v in vals) + "\r\n")
        except Exception:
            pass
        rc = 1
    sys.exit(rc)
