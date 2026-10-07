"""run_m010.py — M010-LLD (Trend 25 + dedupe ρ_adj lead-lag, n_trials 22) ตาม specs/M010_leadlag_dedupe.md (+ การตัดสินใจผู้ใช้ 2026-10-06)

รัน: PYTHONPATH=. ./.venv/bin/python .claude/quant_team/backtest/run_m010.py
(A) regression: threshold 1.01 -> น้ำหนักเท่า M004-TF-FX_weights.csv, Sharpe 0.706119/0.720494/0.893296, skip = 0, sanity ρ_adj vs DIAG_leadlag_pairs 2025-12-31
(B) ถ้าผ่านเท่านั้น -> รัน M010-LLD (threshold 0.85) · ไม่แก้ไฟล์เดิม · reuse run_m009.prepare/sim_cases/regression ฯลฯ
เกณฑ์ (ผู้ใช้ 2026-10-06): ผ่าน = กลไกทำงาน และ Δ Sharpe full >= 0 เท่านั้น; Δ < 0 = ไม่ผ่าน; ไม่มี skip = ไม่มีผล
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
import fees
import fund_signals as fs
import simulate
import weighting as wt
import run_m006_m007 as r67
import run_m009 as r9
from run_m008 import drop_best_q
from data import msci_index

TEAM_DIR = os.path.dirname(THIS_DIR)
SCRATCH = os.path.join(TEAM_DIR, "scratch")
RES = common.RESULTS_DIR
TRIALS_CSV = os.path.join(TEAM_DIR, "trials.csv")
RF = 0.02
N_TRIALS = 22
SEL_N, SEL_K = 8, 16
MIN_W = 30
THR = 0.85
PHASE_B = False


# ---------------- ρ_adj (spec §2) ----------------

def rho_adj_pair(sa: pd.Series, sb: pd.Series, with_lag0=False):
    """sa, sb: weekly return Series บนกริดสัปดาห์เดียวกัน (อาจมี NaN). คืน ρ_adj (NaN ถ้า n<30 / S<=0) [, ρ lag-0 Pearson บน C]."""
    a = sa.reindex(sb.index.union(sa.index)).to_numpy() if not sa.index.equals(sb.index) else sa.to_numpy()
    b = sb.reindex(sb.index.union(sa.index)).to_numpy() if not sa.index.equals(sb.index) else sb.to_numpy()
    C = ~(np.isnan(a) | np.isnan(b))
    n = int(C.sum())
    if n < MIN_W:
        return (np.nan, np.nan) if with_lag0 else np.nan
    mua, mub = a[C].mean(), b[C].mean()
    x = np.where(C, a - mua, 0.0)
    y = np.where(C, b - mub, 0.0)
    # L: w และ w-1 (ตำแหน่งก่อนหน้าบนกริด) อยู่ใน C ทั้งคู่
    Lm = C[1:] & C[:-1]
    xw, xp = x[1:][Lm], x[:-1][Lm]
    yw, yp = y[1:][Lm], y[:-1][Lm]
    d = n - 1.0
    g0xy, g0xx, g0yy = (x * y).sum() / d, (x * x).sum() / d, (y * y).sum() / d
    g1xy = (xw * yp).sum() / d      # cov(x_t, y_{t-1})
    g1yx = (yw * xp).sum() / d      # cov(y_t, x_{t-1})
    g1xx, g1yy = (xw * xp).sum() / d, (yw * yp).sum() / d
    sab = g0xy + g1xy + g1yx
    saa, sbb = g0xx + 2 * g1xx, g0yy + 2 * g1yy
    if saa <= 0 or sbb <= 0:
        rho = np.nan
    else:
        rho = float(np.clip(sab / np.sqrt(saa * sbb), -1, 1))
    if with_lag0:
        r0 = g0xy / np.sqrt(g0xx * g0yy) if g0xx > 0 and g0yy > 0 else np.nan
        return rho, float(r0)
    return rho


class RhoCache:
    def __init__(self):
        self.c = {}
        self.n_nan = 0

    def get(self, qi, wk, f1, f2):
        k = (qi, *sorted((f1, f2)))
        if k not in self.c:
            s1, s2 = wk.get(f1), wk.get(f2)
            if s1 is None or s2 is None or len(s1) == 0 or len(s2) == 0:
                self.c[k] = (np.nan, np.nan)
            else:
                self.c[k] = rho_adj_pair(s1, s2, with_lag0=True)
            if np.isnan(self.c[k][0]):
                self.n_nan += 1
        return self.c[k]


# ---------------- selection (แทนขั้น 6 ของ select_at) ----------------

def select_lld(reps, ranks, held_map, thr, qi, wk, rc, skips, t):
    S = {}
    for fam, fc in held_map.items():
        if fam in reps and ranks.get(fam, 10**9) <= SEL_K and reps[fam]["FundCode"] == fc:
            S[fam] = fc
    n_kept = len(S)
    order = sorted(reps.keys(), key=lambda f: ranks.get(f, 10**9))
    k_fill = min(SEL_K, len(order))
    max_rank = 0
    for fam in order[:k_fill]:
        if len(S) >= SEL_N:
            break
        if fam in S:
            continue
        j = reps[fam]["FundCode"]
        max_rank = max(max_rank, ranks[fam])
        hit = None
        for s in list(S.values()):
            ra, r0 = rc.get(qi, wk, j, s)
            if not np.isnan(ra) and ra > thr:
                hit = (s, ra, r0)
                break
        if hit is not None:
            skips.append({"qi": qi, "t": t.date(), "family": fam, "FundCode": j, "rank": ranks[fam], "conflict_fund": hit[0],
                          "rho_adj": hit[1], "rho_lag0": hit[2], "lag0_le_085": bool(hit[2] <= 0.85)})
            continue
        S[fam] = j
    return {"S": S, "n_kept": n_kept, "n_added": len(S) - n_kept, "max_rank": max_rank,
            "fallback": "b0" if len(S) < 4 else None}


def select_stream(ctxs, thr, rc):
    held, prev_fb = {}, False
    sleeves, diag, skips, sets = {}, [], [], {}
    erc_cache = {}
    for ctx in ctxs:
        qi, t, i_t = ctx["qi"], ctx["t"], ctx["i_t"]
        reps = wt.family_representatives(i_t, "SR12", held_funds=set(held.values()))
        H_map = {} if prev_fb else held
        ranks = wt.rank_families(reps)
        n0 = len(skips)
        sel = select_lld(reps, ranks, H_map, thr, qi, ctx["wk"], rc, skips, t)
        fallback = sel["fallback"] == "b0" or len(sel["S"]) == 0
        diag.append({"qi": qi, "t": t.date(), "n_I": len(i_t), "prev_fb": prev_fb, "fallback": fallback, "n_S": len(sel["S"]),
                     "n_kept": sel["n_kept"], "n_added": sel["n_added"], "n_skips": len(skips) - n0, "max_rank_reached": sel["max_rank"]})
        sets[qi] = dict(sel["S"])
        if fallback:
            held, prev_fb = {}, True
            sleeves[qi] = ctx["b0_w"]
            continue
        held, prev_fb = dict(sel["S"]), False
        funds = list(sel["S"].values())
        w, _src = wt.risk_parity_weights(funds, ctx["wk"], ctx["vol_map"], method="erc")
        sleeves[qi] = wt.apply_cap(w, 0.25)
    return {"sleeves": sleeves, "diag": pd.DataFrame(diag), "skips": pd.DataFrame(skips), "sets": sets}


# ---------------- กลไก: G_t, DR², ENB (ใต้ Σ_adj 8x8) ----------------

def psd_clip(S, eps=1e-10):
    S = (S + S.T) / 2
    w, V = np.linalg.eigh(S)
    return (V * np.clip(w, eps * max(w.max(), 1e-12), None)) @ V.T


def cov_leadlag(X):  # เหมือน diag_leadlag.cov_leadlag(bart=1)
    Xc = X - X.mean(0)
    T = len(Xc)
    G0 = Xc.T @ Xc / (T - 1)
    G1 = Xc[1:].T @ Xc[:-1] / (T - 1)
    return psd_clip((G0 + G1 + G1.T) * 52.0)


def risk_stats(w, S):  # เหมือน diag_leadlag.risk_stats
    w = np.asarray(w)
    vol = np.sqrt(w @ S @ w)
    sig = np.sqrt(np.diag(S))
    dr = (w @ sig) / vol
    lam, V = np.linalg.eigh(S)
    e = V.T @ w
    p = (e ** 2) * lam
    p = p / p.sum()
    p = p[p > 1e-12]
    return vol, dr, float(np.exp(-(p * np.log(p)).sum()))


def mech_quarter(sleeve, wk, qi, rc):
    """sleeve = Series FundCode->weight (ERC ที่ cap แล้ว) · คืน G_t, n คู่ > 0.85, DR², ENB (None ถ้าไม่ครบข้อมูล)."""
    funds = [f for f in sleeve.index if sleeve[f] > 1e-12]
    if any(f not in wk for f in funds):
        return None  # B0 fallback sleeve (ไม่อยู่ใน I_t) — ไม่คำนวณ
    w = sleeve[funds] / sleeve[funds].sum()
    n = len(funds)
    adj = {i: [] for i in range(n)}
    npairs = 0
    for i in range(n):
        for j in range(i + 1, n):
            ra, _ = rc.get(qi, wk, funds[i], funds[j])
            if not np.isnan(ra) and ra > THR:
                adj[i].append(j)
                adj[j].append(i)
                npairs += 1
    seen, G, comps = set(), 0.0, []
    for i in range(n):
        if i in seen:
            continue
        st, comp = [i], []
        seen.add(i)
        while st:
            k = st.pop()
            comp.append(k)
            for m in adj[k]:
                if m not in seen:
                    seen.add(m)
                    st.append(m)
        if len(comp) >= 2:
            gw = float(w.iloc[comp].sum())
            comps.append((gw, [funds[k] for k in comp]))
            G = max(G, gw)
    mat = pd.DataFrame({f: wk[f] for f in funds}).dropna(how="any")
    dr = enb = np.nan
    if len(mat) >= MIN_W:
        S = cov_leadlag(mat.to_numpy())
        _, d, e = risk_stats(w.to_numpy(), S)
        dr, enb = d ** 2, e
    top = max(comps, key=lambda c: c[0])[1] if comps else []
    return {"G": G, "n_pairs_gt": npairs, "DR2": dr, "ENB": enb, "weeks": len(mat), "top_group": ";".join(top)}


# ---------------- sanity ρ_adj vs DIAG ----------------

def sanity_rho(nav_arrays, calendar):
    P = pd.read_csv(os.path.join(RES, "DIAG_leadlag_pairs.csv"), parse_dates=["t"])
    t = pd.Timestamp("2025-12-31")
    P = P[P["t"] == t]
    qctx = fs.QuarterContext(nav_arrays, calendar, t)
    funds = sorted(set(P.f1) | set(P.f2))
    wk = {f: qctx.weekly_return_series(f) for f in funds}
    rows = []
    for r in P.itertuples():
        ra, r0 = rho_adj_pair(wk[r.f1], wk[r.f2], with_lag0=True)
        rows.append({"f1": r.f1, "f2": r.f2, "mine": ra, "diag": r.rho_adj, "diff": ra - r.rho_adj, "mine_lag0": r0, "diag_rho0": r.rho0})
    D = pd.DataFrame(rows)
    gi = D[((D.f1 == "KKP GINFRAEQ-H") & (D.f2 == "ES-GINFRA-A")) | ((D.f2 == "KKP GINFRAEQ-H") & (D.f1 == "ES-GINFRA-A"))]
    return D, gi


# ---------------- main ----------------

def fmt_ci(ci):
    return f"[{ci[0]:+.3f}, {ci[1]:+.3f}]"


def main():
    t0 = time.time()
    print("[1/7] load...", flush=True)
    nav = common.load_nav()
    nav_by_fund = common.build_nav_by_fund(nav)
    calendar = common.load_calendar()
    groups = common.load_groups()
    acwi = msci_index.load_country_index()["MSCI_ACWI"]
    codes = sorted(nav["FundCode"].unique())
    quarters15 = common.quarter_ends(calendar, "2022-03-31", "2025-09-30")
    quarters16 = common.quarter_ends(calendar, "2022-03-31", "2025-12-31")
    assert len(quarters15) == 15 and len(quarters16) == 16, (len(quarters15), len(quarters16))
    bound_m = quarters15[-1] + pd.Timedelta(days=75)
    months = [m for m in common.month_ends(calendar, common.execution_date(calendar, quarters15[0]), "2026-03-31")
              if m <= bound_m + pd.Timedelta(days=31)]
    assert months[-1] == r9.PE, months[-1]
    fd_sim = fees.FeeData(codes)
    nav_arrays = fs._prep_arrays(nav_by_fund)

    print("[2/7] prepare contexts (16 quarters; 16th = 2025-12-31 แยกรายงาน)...", flush=True)
    ctxs = r9.prepare(nav, nav_by_fund, calendar, groups, quarters16)

    print("[3/7] (A) regression threshold 1.01...", flush=True)
    rc = RhoCache()
    base = select_stream(ctxs, 1.01, rc)  # threshold 1.01 => ไม่มีการตัด
    plan_base = r9.make_plan({q: s for q, s in base["sleeves"].items() if q < 15}, quarters15, calendar, acwi)
    sims_base = r9.sim_cases(plan_base, nav_by_fund, months, fd_sim)
    reg = r9.regression(plan_base, sims_base)
    reg["n_skip_threshold_1.01"] = int(len(base["skips"]))
    reg["n_rho_nan_pairs"] = int(rc.n_nan)
    D, gi = sanity_rho(nav_arrays, calendar)
    reg["sanity_n_pairs"] = int(len(D))
    reg["sanity_max_absdiff"] = float(D["diff"].abs().max())
    reg["sanity_median_absdiff"] = float(D["diff"].abs().median())
    reg["sanity_frac_within_0.05"] = float((D["diff"].abs() <= 0.05).mean())
    reg["sanity_infra_pair_mine"] = float(gi["mine"].iloc[0]) if len(gi) else None
    reg["sanity_infra_pair_diag"] = float(gi["diag"].iloc[0]) if len(gi) else None
    reg["sanity_infra_ok"] = bool(len(gi) and gi["mine"].iloc[0] >= 0.85)
    reg["ok_all"] = bool(reg["ok"] and reg["n_skip_threshold_1.01"] == 0 and reg["sanity_infra_ok"])
    print("  REGRESSION:", json.dumps(reg, default=float), flush=True)
    D.to_csv(os.path.join(SCRATCH, "validator_m010_sanity_rho.csv"), index=False)
    json.dump(reg, open(os.path.join(SCRATCH, "validator_m010_regression.json"), "w"), default=float)
    if not reg["ok_all"]:
        print("REGRESSION FAIL — หยุด ไม่รัน M010 (ไม่นับ trial)", flush=True)
        return 2

    print("[4/7] (B) รัน M010-LLD...", flush=True)
    global PHASE_B
    PHASE_B = True
    rc2 = rc  # cache ใช้ร่วมได้ (ค่า ρ ไม่ขึ้นกับ threshold)
    lld = select_stream(ctxs, THR, rc2)
    plan_lld = r9.make_plan({q: s for q, s in lld["sleeves"].items() if q < 15}, quarters15, calendar, acwi)
    sims_lld = r9.sim_cases(plan_lld, nav_by_fund, months, fd_sim)

    print("[5/7] diagnostics...", flush=True)
    ret = lambda s, tag: (lambda r: r[r.index <= r9.PE])(simulate.monthly_returns(s[tag]["values"]))
    r_l, r_b = ret(sims_lld, "full"), ret(sims_base, "full")
    dd = simulate.paired_bootstrap_diff_ci(r_l, r_b, RF)
    d_c50 = simulate.paired_bootstrap_diff_ci(ret(sims_lld, "c50"), ret(sims_base, "c50"), RF)
    late = lambda r: r[r.index >= "2023-07-01"]
    d_late = simulate.paired_bootstrap_diff_ci(late(r_l), late(r_b), RF)
    ci_l, ci_b = simulate.block_bootstrap_ci(r_l, RF), simulate.block_bootstrap_ci(r_b, RF)
    dsr_l = simulate.deflated_sharpe(r_l, RF, N_TRIALS)
    dsr_l50 = simulate.deflated_sharpe(ret(sims_lld, "c50"), RF, N_TRIALS)
    dbq_l, dbq_b = drop_best_q(r_l, RF), drop_best_q(r_b, RF)

    # กลไกต่อไตรมาส (15 ไตรมาส + 2025-12-31 แยก)
    mrows = []
    for tag, st in (("M010", lld), ("TF", base)):
        for qi in range(16):
            ctx = ctxs[qi]
            mq = mech_quarter(st["sleeves"][qi], ctx["wk"], qi, rc)
            mrows.append({"model": tag, "qi": qi, "t": ctx["t"].date(), "fallback": bool(st["diag"].loc[qi, "fallback"]), **(mq or {})})
    M = pd.DataFrame(mrows)
    M15 = M[M.qi < 15]
    mean = lambda tag, col: float(M15[M15.model == tag][col].mean())
    med = lambda tag, col: float(M15[M15.model == tag][col].median())
    mech = {c: {"M010": (mean("M010", c), med("M010", c)), "TF": (mean("TF", c), med("TF", c))} for c in ("G", "n_pairs_gt", "DR2", "ENB")}
    sk = lld["skips"]
    sk15 = sk[sk.qi < 15] if len(sk) else sk
    n_skip, n_skq = len(sk15), (sk15["qi"].nunique() if len(sk15) else 0)
    mech_ok = bool(n_skip >= 1 and mech["G"]["M010"][0] < mech["G"]["TF"][0] and mech["DR2"]["M010"][0] >= mech["DR2"]["TF"][0])
    # ไตรมาสที่ชุดกองต่างกัน
    hold_l, hold_b = r9.holdings(plan_lld), r9.holdings(plan_base)
    skq = set(sk15["qi"]) if len(sk15) else set()
    diffq = [qi for qi in range(15) if set(hold_l[qi]) != set(hold_b[qi])]
    direct = [qi for qi in diffq if qi in skq]
    inherit = [qi for qi in diffq if qi not in skq]
    skq_same = [qi for qi in skq if qi not in diffq]
    es_l = r9.entry_stats(hold_l, fees.FeeData(codes), quarters15)
    es_b = r9.entry_stats(hold_b, fees.FeeData(codes), quarters15)
    dg = lld["diag"]
    dgb = base["diag"]
    nS_lt8 = [str(ctxs[i]["t"].date()) for i in range(15) if (not dg.loc[i, "fallback"]) and dg.loc[i, "n_S"] < 8]
    n_fb_l, n_fb_b = int(dg[dg.qi < 15]["fallback"].sum()), int(dgb[dgb.qi < 15]["fallback"].sum())
    deepest = int(dg[dg.qi < 15]["max_rank_reached"].max())
    # 2025-12-31 พอร์ตแนะนำ
    p16 = {}
    for tag, st in (("M010", lld), ("TF", base)):
        sl = st["sleeves"][15]
        p16[tag] = {f: float(w) for f, w in sl.items() if w > 1e-12}
    sk16 = sk[sk.qi == 15] if len(sk) else sk

    verdict = ("ไม่มีผล (ไม่มี skip ตลอดช่วง → M010 ≡ Trend 25)" if n_skip == 0 else
               "ผ่าน" + (" (ดีกว่าอย่างมีนัย: CI ล่าง > 0)" if dd[0] > 0 else "") if (mech_ok and dd[2] >= 0) else
               "ไม่ผ่าน")
    if n_skip > 0 and not mech_ok:
        why = "กลไกไม่ทำงาน (G ไม่ลด หรือ DR² ลด)" + (" และ Δ < 0" if dd[2] < 0 else "")
    elif n_skip > 0 and dd[2] < 0:
        why = "Δ Sharpe full < 0 (เกณฑ์ผู้ใช้ 2026-10-06)"
    else:
        why = ""

    print("[6/7] write outputs...", flush=True)
    eq = pd.DataFrame({"M010-LLD_full": sims_lld["full"]["values"], "M010-LLD_c50": sims_lld["c50"]["values"], "M010-LLD_c0": sims_lld["c0"]["values"],
                       "M004-TF-FX_full": sims_base["full"]["values"], "M004-TF-FX_c50": sims_base["c50"]["values"], "M004-TF-FX_c0": sims_base["c0"]["values"]})
    eq.to_csv(os.path.join(RES, "M010_equity_curve.csv"))
    wrows = [{"trial": "M010-LLD", "offset": "Q", "t": en["t"].date() if hasattr(en["t"], "date") else en["t"], "e": en["e"].date(), "kind": en["mode"],
              "FundCode": f, "weight": w} for en in sims_lld["full"]["entries"] for f, w in en["target"].items() if w > 1e-12]
    pd.DataFrame(wrows).to_csv(os.path.join(RES, "M010-LLD_weights.csv"), index=False)
    sk.to_csv(os.path.join(RES, "M010_skip_log.csv"), index=False)
    M.to_csv(os.path.join(RES, "M010_mechanism_quarterly.csv"), index=False)
    dg2 = dg.copy()
    dg2["same_set_as_TF"] = [set(lld["sets"][i].values()) == set(base["sets"][i].values()) for i in range(16)]
    dg2.to_csv(os.path.join(RES, "M010_quarter_diag.csv"), index=False)
    cols = ["c0", "c50", "c100", "flat", "full", "nofront"]
    summ = []
    for name, sims in (("M010-LLD", sims_lld), ("M004-TF-FX", sims_base)):
        for c in cols:
            s = sims[c]
            summ.append({"trial": name, "cost": c, **s["metrics"], "cost_bp_yr": s["cost_bp_yr"], "turn_yr": s["turn_yr"],
                         "switch_share": s.get("switch_share", np.nan), "avg_fee_pct": s.get("avg_fee_pct", np.nan), "n_cannot_buy": s["n_cannot_buy"]})
    pd.DataFrame(summ).to_csv(os.path.join(RES, "M010_results.csv"), index=False)

    cs = pd.read_csv(os.path.join(RES, "COST_real_fees_summary.csv")).set_index("trial")
    g = lambda sims, c, k: sims[c]["metrics"][k]
    L, A = [], None
    A = L.append
    A("# M010-LLD — Trend 25 + ตัดกองซ้ำด้วย ρ_adj (lead-lag) (n_trials = 22) — ผลวัด (validator)\n")
    A(f"รันเมื่อ {pd.Timestamp.now().isoformat()} · spec `specs/M010_leadlag_dedupe.md` + การตัดสินใจผู้ใช้ 2026-10-06 (ผ่าน = กลไกทำงาน และ Δ Sharpe full ≥ 0 เท่านั้น) · "
      f"primary เม.ย. 2022 → 2025-12-31 (45 เดือน) · rf 2% · ไม่ปรับพารามิเตอร์ (ρ_adj > 0.85, lag 1 น้ำหนักเต็ม, 52 สัปดาห์, ขั้นต่ำ 30, K_fill 16) · ไม่มี holdout\n")
    A("## 1. Regression ก่อนรัน (threshold 1.01)\n")
    A(f"- น้ำหนักเทียบ `M004-TF-FX_weights.csv`: max|Δw| = {reg['max_dw']:.2e} · แถว {reg['n_rows_ref']} vs {reg['n_rows_mine']} · คีย์ฝั่งเดียว {reg['n_only_one_side']} → **{'PASS' if reg['ok_w'] else 'FAIL'}**")
    A(f"- Sharpe full/flat/nofront = {reg['sharpe']['full']:.6f} / {reg['sharpe']['flat']:.6f} / {reg['sharpe']['nofront']:.6f} (อ้างอิง 0.706119 / 0.720494 / 0.893296) → **{'PASS' if reg['ok_s'] else 'FAIL'}**")
    A(f"- จำนวน skip ที่ threshold 1.01 = {reg['n_skip_threshold_1.01']} (ต้อง 0) · คู่ ρ_adj เป็น NaN (n<30/S≤0) ระหว่างรัน = {reg['n_rho_nan_pairs']} · ไม่ crash")
    A(f"- sanity ρ_adj ณ 2025-12-31 vs `DIAG_leadlag_pairs.csv`: {reg['sanity_n_pairs']} คู่ · |ต่าง| median {reg['sanity_median_absdiff']:.3f} · max {reg['sanity_max_absdiff']:.3f} · "
      f"สัดส่วนคู่ที่ห่าง ≤ 0.05 = {reg['sanity_frac_within_0.05']:.1%} · KKP GINFRAEQ-H vs ES-GINFRA-A: ของเรา {reg['sanity_infra_pair_mine']:.3f} (DIAG {reg['sanity_infra_pair_diag']:.3f}) ≥ 0.85 → **{'PASS' if reg['sanity_infra_ok'] else 'FAIL'}**\n")
    A("## 2. ตารางผลหลัก (ค่าธรรมเนียมจริง FEEUH full, rf 2%)\n")
    A("| โมเดล | Sharpe | CAGR | vol | maxDD | cost bp/ปี | turnover/ปี | CI95% Sharpe |")
    A("|---|---|---|---|---|---|---|---|")
    for nm, sims, ci in (("**M010-LLD**", sims_lld, ci_l), ("M004-TF-FX (Trend 25)", sims_base, ci_b)):
        m = sims["full"]["metrics"]
        A(f"| {nm} | {m['sharpe']:.3f} | {m['cagr']:.4f} | {m['vol']:.4f} | {m['max_dd']:.4f} | {sims['full']['cost_bp_yr']:.1f} | {sims['full']['turn_yr']:.3f} | [{ci[0]:.2f}, {ci[1]:.2f}] |")
    for nm in ("M001-MS", "B0"):
        r = cs.loc[nm]
        A(f"| {nm} (อ้างอิง COST_real_fees) | {r['sharpe_full']:.3f} | {r['cagr_full']:.4f} | {r['vol_full']:.4f} | {r['maxdd_full']:.4f} | {r['cost_bp_yr_full']:.1f} | — | — |")
    A("")
    A("## 3. ตัวชี้วัดหลัก + เกณฑ์ (ผู้ใช้ 2026-10-06)\n")
    A(f"- Δ Sharpe_full (M010-LLD − M004-TF-FX) paired block bootstrap (block 3, 2000, seed 0) = **{dd[2]:+.4f}** CI95% **{fmt_ci(dd)}** ({'คร่อม 0' if dd[0] <= 0 <= dd[1] else 'ไม่คร่อม 0'})")
    A(f"- กลไก: skip {n_skip} ครั้ง ใน {n_skq} ไตรมาส · mean G_t M010 {mech['G']['M010'][0]:.3f} vs TF {mech['G']['TF'][0]:.3f} · mean DR² M010 {mech['DR2']['M010'][0]:.3f} vs TF {mech['DR2']['TF'][0]:.3f} → **กลไก{'ทำงาน' if mech_ok else 'ไม่ทำงาน'}**")
    A(f"- **ผลตามเกณฑ์: {verdict}**" + (f" — {why}" if why else "") + "\n")
    A(f"- Δ ที่ cost 0.5%/ข้าง คงที่ (ประกอบ): {d_c50[2]:+.4f} CI {fmt_ci(d_c50)} · Δ เฉพาะ 2023-07..2025-12 (full): {d_late[2]:+.4f} CI {fmt_ci(d_late)}\n")
    A("## 4. กลไก (15 ไตรมาส 2022-03…2025-09, ใช้นิยาม ρ_adj §2 เดียวกัน)\n")
    A("| ตัวชี้วัด | M010 mean (median) | Trend 25 mean (median) |")
    A("|---|---|---|")
    A(f"| G_t (น้ำหนักกลุ่มซ้ำสูงสุด, ส่วนหุ้น normalize) | {mech['G']['M010'][0]:.3f} ({mech['G']['M010'][1]:.3f}) | {mech['G']['TF'][0]:.3f} ({mech['G']['TF'][1]:.3f}) |")
    A(f"| จำนวนคู่ ρ_adj > 0.85 ในพอร์ต | {mech['n_pairs_gt']['M010'][0]:.2f} ({mech['n_pairs_gt']['M010'][1]:.1f}) | {mech['n_pairs_gt']['TF'][0]:.2f} ({mech['n_pairs_gt']['TF'][1]:.1f}) |")
    A(f"| DR² (Σ_adj 8×8, หลัก) | {mech['DR2']['M010'][0]:.3f} ({mech['DR2']['M010'][1]:.3f}) | {mech['DR2']['TF'][0]:.3f} ({mech['DR2']['TF'][1]:.3f}) |")
    A(f"| ENB (Meucci PCA — กลับหัวได้) | {mech['ENB']['M010'][0]:.3f} ({mech['ENB']['M010'][1]:.3f}) | {mech['ENB']['TF'][0]:.3f} ({mech['ENB']['TF'][1]:.3f}) |")
    A("")
    A("G_t รายไตรมาส (M010 / TF): " + " · ".join(f"{r.t}: {M15[(M15.model=='M010')&(M15.qi==r.qi)]['G'].iloc[0]:.2f}/{r.G:.2f}" for r in M15[M15.model == 'TF'].itertuples()))
    A(f"- จำนวน skip = {n_skip} · ไตรมาสที่มี skip = {n_skq}/15 ({', '.join(str(ctxs[q]['t'].date()) for q in sorted(skq))}) · อันดับลึกสุดที่ไล่ถึง {deepest} · ไตรมาส |S|<8 (ไม่ fallback): {nS_lt8 or 'ไม่มี'} · fallback B0 (15 ไตรมาส): M010 {n_fb_l} / TF {n_fb_b}")
    A(f"- skip ที่ ρ_lag0 ≤ 0.85 แต่ ρ_adj > 0.85 (ส่วนที่ M005 ทำไม่ได้): {int(sk15['lag0_le_085'].sum()) if len(sk15) else 0}/{n_skip}")
    A("")
    A("### ตาราง skip (ทั้ง 16 ไตรมาส รวม 2025-12-31 ที่ติดป้าย)\n")
    A("| t | family | กองที่ข้าม | rank | กองที่ชน | ρ_adj | ρ_lag0 |")
    A("|---|---|---|---|---|---|---|")
    for r in sk.itertuples():
        A(f"| {r.t}{' (นอกช่วงตัดสิน)' if r.qi == 15 else ''} | {r.family} | {r.FundCode} | {r.rank} | {r.conflict_fund} | {r.rho_adj:.3f} | {r.rho_lag0:.3f} |")
    A("")
    A("## 5. ไตรมาสที่ชุดกองต่างจาก Trend 25\n")
    A(f"- ต่างทั้งหมด {len(diffq)}/15: **ต่างเพราะ skip ตรงๆ (ไตรมาสนั้นมี skip) {len(direct)}** ({', '.join(str(ctxs[q]['t'].date()) for q in direct)}) · "
      f"**ต่างเพราะสืบทอดผ่าน hysteresis {len(inherit)}** ({', '.join(str(ctxs[q]['t'].date()) for q in inherit)}) · ไตรมาสที่มี skip แต่ชุดเท่ากัน: {len(skq_same)}\n")
    A("## 6. รายงานคู่ (ไม่ใช้ตัดสิน) — ต่อกรณีต้นทุน\n")
    A("| ต้นทุน | M010 Sharpe | CAGR | vol | maxDD | TF Sharpe | CAGR | vol | maxDD |")
    A("|---|---|---|---|---|---|---|---|---|")
    lab = {"c0": "0%", "c50": "0.5%/ข้าง", "c100": "1%/ข้าง", "flat": "flat 0.5% (fee model)", "full": "ค่าธรรมเนียมจริง full", "nofront": "nofront"}
    for c in cols:
        a, b = sims_lld[c]["metrics"], sims_base[c]["metrics"]
        A(f"| {lab[c]} | {a['sharpe']:.3f} | {a['cagr']:.4f} | {a['vol']:.4f} | {a['max_dd']:.4f} | {b['sharpe']:.3f} | {b['cagr']:.4f} | {b['vol']:.4f} | {b['max_dd']:.4f} |")
    A("")
    A("| ตัวชี้วัด | M010 | TF |")
    A("|---|---|---|")
    A(f"| turnover/ปี | {sims_lld['full']['turn_yr']:.3f} | {sims_base['full']['turn_yr']:.3f} |")
    A(f"| cost bp/ปี (full) | {sims_lld['full']['cost_bp_yr']:.1f} | {sims_base['full']['cost_bp_yr']:.1f} |")
    A(f"| กองใหม่ต่อไตรมาส (2–15) | {es_l['new_per_q_mean']:.2f} | {es_b['new_per_q_mean']:.2f} |")
    A(f"| ระยะถือเฉลี่ย (ไตรมาส; กองที่เข้าหลังไตรมาสแรก) | {es_l['hold_q_mean_entered']:.2f} | {es_b['hold_q_mean_entered']:.2f} |")
    A(f"| ระยะถือเฉลี่ยทุกช่วงถือ | {es_l['hold_q_mean_all']:.2f} | {es_b['hold_q_mean_all']:.2f} |")
    A("")
    A("## 7. ผลย่อยช่วงเวลา (Sharpe, full)\n")
    A("| ช่วง | M010 | TF |")
    A("|---|---|---|")
    for lbl, k in (("2022 (เม.ย.–ธ.ค.)", "sharpe_2022"), ("2023-07..2025-12", "sharpe_2307_2512"), ("2022-04..2023-06", "sharpe_2204_2306")):
        A(f"| {lbl} | {g(sims_lld,'full',k):.3f} | {g(sims_base,'full',k):.3f} |")
    A(f"| drop-best-quarter (ตัดไตรมาสปฏิทินที่ดีสุด) | {dbq_l[0]:.3f} (ตัด {dbq_l[1]}) | {dbq_b[0]:.3f} (ตัด {dbq_b[1]}) |")
    A("")
    A("## 8. DSR / ความเชื่อมั่น\n")
    A(f"- **DSR@22 (full) M010-LLD = {dsr_l:.4f}** (c50 = {dsr_l50:.4f}) · CI95% Sharpe M010 [{ci_l[0]:.3f}, {ci_l[1]:.3f}] · TF [{ci_b[0]:.3f}, {ci_b[1]:.3f}] · เป้า 0.95: ไม่ถึง ({g(sims_lld,'full','sharpe'):.3f})\n")
    A("## 9. พอร์ต ณ 2025-12-31 (พอร์ตแนะนำหน้า 9 — รายงานแยก ไม่ใช้ตัดสิน)\n")
    A("- M010 (ส่วนกอง, ก่อนเงินสด trend): " + "; ".join(f"{f} {w:.3f}" for f, w in sorted(p16["M010"].items(), key=lambda kv: -kv[1])))
    A("- Trend 25: " + "; ".join(f"{f} {w:.3f}" for f, w in sorted(p16["TF"].items(), key=lambda kv: -kv[1])))
    if len(sk16):
        A("- skip ที่ 2025-12-31: " + "; ".join(f"{r.FundCode} ชน {r.conflict_fund} (ρ_adj {r.rho_adj:.2f}, rank {r.rank})" for r in sk16.itertuples()))
    G16 = M[(M.qi == 15)].set_index("model")
    A(f"- G_t / DR² ที่ 2025-12-31: M010 {G16.loc['M010','G']:.3f} / {G16.loc['M010','DR2']:.3f} · TF {G16.loc['TF','G']:.3f} / {G16.loc['TF','DR2']:.3f}\n")
    A("## 10. สมมติฐาน / การตีความของ validator\n")
    for s in [
        "reuse `run_m009.prepare/sim_cases/regression/holdings/entry_stats` (import ไม่แก้ไฟล์เดิม) · selection เขียนใหม่ใน `select_lld` (ขั้น 6 เท่านั้น) · ขั้นอื่น (family_representatives, rank_families, ERC LW, cap 25%, trend cash, fallback B0, ต้นทุน) เรียกใช้ซ้ำจาก weighting/run_m006_m007",
        "ρ_adj คำนวณจาก `QuarterContext.weekly_return_series` (ชุดเดียวกับ ERC) ตาม §2 ทุกบรรทัด (S_aa=Γ0+2Γ1, ตัวหาร n−1, L ใช้ตำแหน่งสัปดาห์ก่อนหน้าบนกริด) · เทียบกับทุกกองใน S ขณะนั้น · กองถือต่อไม่ถูกตัด · n<30/S≤0 = ผ่าน",
        "ไล่เติมถึง min(16, จำนวน family) ตาม §3 · ใช้ rank จาก SR12 (ไม่มี pen)",
        "กลไก G_t/DR²/ENB คำนวณกับพอร์ตจริงของทั้งสองโมเดลที่ 15 ไตรมาส (น้ำหนัก ERC หลัง cap, normalize=1) ใต้ Σ_adj จากสัปดาห์ร่วม listwise ของกองในพอร์ต (cov_leadlag เหมือน diag_leadlag รวม PSD clip) · ไตรมาสที่ fallback B0 ข้ามการคำนวณ",
        "'กลไกทำงาน' = skip ≥ 1 และ mean G ลดลง และ mean DR²_adj ไม่ลดลง (เทียบ mean 15 ไตรมาส) ตาม §6 · 'ต่างเพราะ skip ตรงๆ' = ไตรมาสนั้นมี skip ≥ 1 และชุดต่าง; 'สืบทอด' = ชุดต่างแต่ไตรมาสนั้นไม่มี skip",
        "ไตรมาส 2025-12-31 (16th) ใช้ selection ต่อจากสายเดียวกัน (ไม่มีผลต่อไตรมาสก่อนหน้า) แต่ไม่อยู่ใน plan/Sharpe/กลไก 15 ไตรมาส",
        "Δ หลัก = full-fee 45 เดือน (เหมือน M009) · DSR = simulate.deflated_sharpe @22",
    ]:
        A(f"- {s}")
    A("\n## 11. ไฟล์\n`M010_results.csv`, `M010_equity_curve.csv`, `M010-LLD_weights.csv`, `M010_skip_log.csv`, `M010_mechanism_quarterly.csv`, `M010_quarter_diag.csv`, `scratch/validator_m010_regression.json`, `scratch/validator_m010_sanity_rho.csv`")
    open(os.path.join(RES, "M010_results.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")

    print("[7/7] trials.csv / ALL_RESULTS...", flush=True)
    res = {"verdict": verdict, "why": why, "dd": dd, "d_c50": d_c50, "d_late": d_late, "dsr": dsr_l, "dsr50": dsr_l50, "n_skip": n_skip, "n_skq": n_skq,
           "mech_ok": mech_ok, "mech": mech, "diffq": len(diffq), "direct": len(direct), "inherit": len(inherit), "ci_l": ci_l, "ci_b": ci_b,
           "dbq": [dbq_l, dbq_b], "nS_lt8": nS_lt8, "fb": [n_fb_l, n_fb_b], "deepest": deepest}
    append_logs(sims_lld, sims_base, res, ci_l)
    json.dump(res, open(os.path.join(SCRATCH, "validator_m010_summary.json"), "w"), default=float)
    print(f"DONE in {time.time()-t0:.0f}s · verdict: {verdict} {why}", flush=True)
    return 0


def append_logs(sims, sims_base, res, ci):
    now = pd.Timestamp.now().isoformat()
    m = sims["full"]["metrics"]
    dd = res["dd"]
    note = (f"M010-LLD dedupe rho_adj>0.85 (lead-lag lag1 full weight; 52w; min30w; K_fill16; held not cut) on M004-TF-FX; Sharpe: 0%={sims['c0']['metrics']['sharpe']:.3f} "
            f"0.5%={sims['c50']['metrics']['sharpe']:.3f} full={m['sharpe']:.3f} nofront={sims['nofront']['metrics']['sharpe']:.3f}; paired dSharpe full vs M004-TF-FX {dd[2]:.3f} CI ({dd[0]:.3f};{dd[1]:.3f}); "
            f"skips={res['n_skip']} in {res['n_skq']}q; mean G {res['mech']['G']['M010'][0]:.3f} vs {res['mech']['G']['TF'][0]:.3f}; mean DR2 {res['mech']['DR2']['M010'][0]:.3f} vs {res['mech']['DR2']['TF'][0]:.3f}; "
            f"mech_ok={res['mech_ok']}; cost bp/yr full {sims['full']['cost_bp_yr']:.1f} vs {sims_base['full']['cost_bp_yr']:.1f}; CI95 ({ci[0]:.3f};{ci[1]:.3f}); DSR@22(full)={res['dsr']:.4f}; "
            f"verdict={res['verdict']} {res['why']}; n_months=45; family map F/U fix; fees snapshot oldest before 2023-05")
    params = "M010-LLD: rho_adj>0.85 dedupe at fill step; weekly 52 lag1 full weight; min 30 weeks; K_fill=16; N=8; ERC LW lag0; cap25%; trend cash25%; rf=2%; fee=FEEUH full PIT; primary=2022-03..2025-12"
    vals = ["M010-LLD", now, "M010_leadlag_dedupe.md", params, "2022-03-31", "2025-12-31", "assumed constant 2%/yr", "real fees SecFundFee FEEUH (full)",
            round(m["sharpe"], 4), round(m["cagr"], 4), round(m["vol"], 4), round(m["max_dd"], 4), round(sims["full"]["turn_yr"], 4), N_TRIALS, round(res["dsr"], 4), "ok", note]
    line = ",".join(str(v).replace(",", ";") for v in vals)
    txt = open(TRIALS_CSV, encoding="utf-8", newline="").read()
    assert "M010-LLD," not in txt, "มีแถว M010-LLD แล้ว"
    with open(TRIALS_CSV, "a", encoding="utf-8", newline="") as f:
        f.write(line + "\r\n")
    g = lambda c, k: sims[c]["metrics"][k]
    allv = ["M010", "M010-LLD", "Trend 25 + dedupe rho_adj>0.85 (lead-lag) at fill step", "new", "no", f"{g('c0','sharpe'):.3f}", f"{g('c50','sharpe'):.3f}",
            f"{g('c100','sharpe'):.3f}", f"{g('c50','cagr'):.3f}", f"{g('c50','vol'):.3f}", f"{g('c50','max_dd'):.3f}", f"{res['dsr50']:.3f}",
            f"{g('full','sharpe'):.4f}", f"{g('nofront','sharpe'):.4f}", f"{g('full','cagr'):.4f}", f"{sims['full']['cost_bp_yr']:.1f}"]
    p = os.path.join(RES, "ALL_RESULTS.csv")
    txt = open(p, encoding="utf-8", newline="").read()
    assert "M010-LLD," not in txt
    with open(p, "a", encoding="utf-8", newline="") as f:
        if not txt.endswith("\n"):
            f.write("\n")
        f.write(",".join(allv) + "\n")
    md = os.path.join(RES, "ALL_RESULTS.md")
    with open(md, "a", encoding="utf-8") as f:
        f.write(f"\n## เพิ่ม 2026-10-06: M010-LLD\nแถว `M010-LLD` ใน `ALL_RESULTS.csv` (trial ที่ 22 · base M004-TF-FX · วัดใหม่ · รายละเอียด `M010_results.md`): ตัดกองซ้ำด้วย ρ_adj > 0.85 · "
                f"Sharpe full {m['sharpe']:.3f} (M004-TF-FX 0.706) · paired Δ {dd[2]:+.3f} CI95% [{dd[0]:+.3f}, {dd[1]:+.3f}] · skip {res['n_skip']} ครั้ง ใน {res['n_skq']} ไตรมาส · "
                f"กลไก{'ทำงาน' if res['mech_ok'] else 'ไม่ทำงาน'} · DSR@22 {res['dsr']:.3f} · **{res['verdict']}** {res['why']} (เกณฑ์ผู้ใช้ 2026-10-06: Δ ≥ 0 เท่านั้น) · "
                f"คอลัมน์ `dsr_n18` ของแถวนี้ = DSR@22 ที่ต้นทุน 0.5% คงที่\n")


if __name__ == "__main__":
    try:
        rc = main()
    except Exception:
        tb = traceback.format_exc()
        print(tb, flush=True)
        try:
            txt = open(TRIALS_CSV, encoding="utf-8", newline="").read()
            if PHASE_B and "M010-LLD," not in txt:
                last = tb.strip().splitlines()[-1].replace(",", ";")[:200]
                vals = ["M010-LLD", pd.Timestamp.now().isoformat(), "M010_leadlag_dedupe.md", "M010-LLD run crashed", "2022-03-31", "2025-12-31",
                        "assumed constant 2%/yr", "real fees SecFundFee FEEUH (full)", "", "", "", "", "", N_TRIALS, "", "crashed", last]
                with open(TRIALS_CSV, "a", encoding="utf-8", newline="") as f:
                    f.write(",".join(str(v) for v in vals) + "\r\n")
        except Exception:
            pass
        rc = 1
    sys.exit(rc)
