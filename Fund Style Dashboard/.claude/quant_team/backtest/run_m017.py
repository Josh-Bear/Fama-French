"""run_m017.py — M017-IDX (trial #34): คัดดัชนี MSCI 28 ตัวด้วย SR12_idx ก่อน แล้วเลือกกองที่ตามดัชนีที่ชนะ · specs/M017_index_first.md
universe เต็ม · rf จริง · FeeData(legacy=False) · reuse robust_offsets.setup_env_off / run_m012 (Quality, stream, to_plan) / run_m011 / run_m010.rho_adj_pair
(A) regression: r12.stream("S") -> Sharpe full M012-QF-S 0.659648 + Trend25 0.719313 + leak asserts + spot refit exposure = cache -> ไม่ผ่าน = หยุด
(B) M017-IDX offset 0 (full/nofront/flat/c0) + offset 1/2 (ช่วงร่วม 42 เดือน) + log trials.csv (สำรองก่อน)
รัน: PYTHONPATH=. ./.venv/bin/python .claude/quant_team/backtest/run_m017.py [--prep]   (--prep = fit/cache exposure ของ offset 1/2 เท่านั้น ไม่คำนวณ return)
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
import config
import exposure
import fund_signals as fs
import weighting as wt
import run_m010 as r10
import run_m011 as r11
import run_m012 as r12
import remeasure_real_rf as rr
import robust_offsets as ro
from data import msci_index

TEAM_DIR = os.path.dirname(THIS_DIR)
SCRATCH = os.path.join(TEAM_DIR, "scratch")
RES = common.RESULTS_DIR
TRIALS_CSV = os.path.join(TEAM_DIR, "trials.csv")
NAME, N_TRIAL = "M017-IDX", 34
N_SEL, K_IDX, CAP, R2_MIN, RHO_MAX = 5, 10, 0.25, 0.50, 0.85
TARGET_CAGR, DD_FLOOR = 0.0909, -0.20
CTX = {0: os.path.join(SCRATCH, "validator_m012_ctxs.pkl"),
       1: os.path.join(SCRATCH, "validator_full_ctxs_off1.pkl"),
       2: os.path.join(SCRATCH, "validator_full_ctxs_off2.pkl")}
KINDS = ["full", "nofront", "flat", "c0"]
COUNTRY_ALL = list(config.MSCI_COUNTRY_COLS)
SECTOR_ALL = list(config.MSCI_SECTOR_COLS)
IDX_ALL = COUNTRY_ALL + SECTOR_ALL                       # 28
SCOPE = {**{c: "country" for c in COUNTRY_ALL}, **{s: "sector" for s in SECTOR_ALL}}
FITTABLE = set(config.SCORE_COUNTRY_CLEAN) | set(SECTOR_ALL)   # 21 ดัชนีที่เป็น primary ได้
PHASE_B = False
assert len(IDX_ALL) == 28 and len(set(IDX_ALL)) == 28


# ---------------- index levels / SR12_idx ----------------
class IndexSignals:
    def __init__(self, calendar):
        c = msci_index.load_country_index()
        s = msci_index.load_sector_index()
        self.lv = pd.concat([c, s], axis=1)[IDX_ALL].sort_index()
        self.lc, self.ls = c, s
        self.calendar = calendar

    def at(self, t, h):
        lv_t = self.lv.loc[:t]
        assert lv_t.index.max() <= t, "look-ahead index level"
        arrs = fs._prep_arrays({col: lv_t[col].dropna() for col in IDX_ALL})
        q = fs.QuarterContext(arrs, self.calendar, t)
        rows = []
        for col in IDX_ALL:
            sg = q.fund_signal(col)
            sr = (sg["R12_1"] - h) / sg["vol52"] if (sg["vol52"] == sg["vol52"] and sg["vol52"] > 0) else np.nan
            rows.append({"idx": col, "scope": SCOPE[col], "R12_1": sg["R12_1"], "vol52": sg["vol52"], "SR12_idx": sr})
        d = pd.DataFrame(rows)
        d["_k"] = d["SR12_idx"].fillna(-np.inf)
        d = d.sort_values(["_k", "idx"], ascending=[False, True]).drop(columns="_k").reset_index(drop=True)
        d["rank"] = np.arange(1, len(d) + 1)
        return d


# ---------------- exposure ณ t ----------------
def exposure_at(nav, nav_by_fund, lc, ls, t, need_codes):
    u = common.universe_at(nav, t)
    codes = u["FundCode"].tolist()
    assert set(need_codes) <= set(codes)
    for scope, n in (("country", len(config.SCORE_COUNTRY_CLEAN)), ("sector", len(SECTOR_ALL))):
        key = f"exposure_{scope}_{n}c_{t.date()}"                   # key ของ cache = t (PIT)
        assert key.endswith(str(t.date()))
    cdf = exposure.fit_scope(codes, nav_by_fund, lc, config.SCORE_COUNTRY_CLEAN, t, "country")
    sdf = exposure.fit_scope(codes, nav_by_fund, ls, SECTOR_ALL, t, "sector")
    ex = {}
    cc, sc = cdf.set_index("FundCode"), sdf.set_index("FundCode")
    for fc in codes:
        tr = set()
        cp = cc.loc[fc] if fc in cc.index else None
        sp = sc.loc[fc] if fc in sc.index else None
        if cp is not None and cp["primary"] is not None and cp["r2"] == cp["r2"] and cp["r2"] >= R2_MIN and cp["primary_coef"] > 0:
            tr.add(cp["primary"])
        if sp is not None and sp["primary"] is not None and sp["r2"] == sp["r2"] and sp["r2"] >= R2_MIN and sp["primary_coef"] > 0:
            tr.add(sp["primary"])
        ex[fc] = {"tracks": tr, "country_primary": None if cp is None else cp["primary"], "country_r2": np.nan if cp is None else cp["r2"],
                  "sector_primary": None if sp is None else sp["primary"], "sector_r2": np.nan if sp is None else sp["r2"]}
    return ex, cdf, sdf


# ---------------- selection stream ----------------
def country_of(ex, fc):
    cp = ex.get(fc, {}).get("country_primary")
    return cp if isinstance(cp, str) and cp else f"NA:{fc}"


def select_idx(ctx, it, held, prev_fb, ex, idx_tab, rc, country_rule=False):
    """held: family -> (FundCode, X). คืน dict."""
    H = {} if prev_fb else held
    reps = wt.family_representatives(it, "SR12", held_funds={v[0] for v in H.values()})
    rank_of = dict(zip(idx_tab["idx"], idx_tab["rank"]))
    chosen = {}                                   # fam -> (fc, X, kept)
    occupied = set()
    for fam, (fc, X) in H.items():
        if fam in reps and reps[fam]["FundCode"] == fc and rank_of[X] <= K_IDX and X in ex.get(fc, {}).get("tracks", set()):
            chosen[fam] = (fc, X, True)
            occupied |= ex[fc]["tracks"]
    n_kept = len(chosen)
    # candidates per index
    cand = {X: [] for X in IDX_ALL}
    for fam, r in reps.items():
        for X in ex.get(r["FundCode"], {}).get("tracks", set()):
            cand[X].append((fam, r))
    log = {"structural": [], "no_eligible": [], "occupied": [], "blocked": [], "rej_a": 0, "rej_b": 0, "rej_c": 0, "rej_country": 0, "rej_c_list": [], "walked": 0}
    for X in idx_tab["idx"]:
        if len(chosen) >= N_SEL:
            break
        log["walked"] += 1
        if X in occupied:
            log["occupied"].append(X)
            continue
        cs = sorted(cand[X], key=lambda kv: (-kv[1]["signal"], kv[1]["vol52"], kv[1]["FundCode"]))
        if not cs:
            log["structural" if X not in FITTABLE else "no_eligible"].append(X)
            continue
        picked = None
        for fam, r in cs:
            fc = r["FundCode"]
            if fam in chosen:
                log["rej_a"] += 1
                continue
            if ex[fc]["tracks"] & occupied:
                log["rej_b"] += 1
                continue
            if country_rule:
                cc = country_of(ex, fc)
                if sum(1 for s_fc, _, _ in chosen.values() if country_of(ex, s_fc) == cc) >= 2:
                    log["rej_country"] += 1
                    continue
            hit = None
            for s_fc, _, _ in chosen.values():
                ra, r0 = rc.get(ctx["qi"], ctx["wk"], fc, s_fc)
                if not np.isnan(ra) and ra > RHO_MAX:
                    hit = (s_fc, ra)
                    break
            if hit is not None:
                log["rej_c"] += 1
                log["rej_c_list"].append(f"{fc}~{hit[0]}:{hit[1]:.2f}")
                continue
            picked = (fam, fc)
            break
        if picked is None:
            log["blocked"].append(X)
            continue
        chosen[picked[0]] = (picked[1], X, False)
        occupied |= ex[picked[1]]["tracks"]
    fb = len(chosen) < 4
    # invariant (กฎ b): ทุกดัชนีถูก track โดยกองที่เลือกใหม่ไม่เกิน 1 กอง (นับรวมกองถือต่อ ยกเว้นคู่ที่เป็นกองถือต่อทั้งคู่)
    if not fb:
        seen = {}
        for fam, (fc, X, kept) in chosen.items():
            for y in ex[fc]["tracks"]:
                if y in seen:
                    assert kept and chosen[seen[y]][2], f"rule b violated {y}"
                seen[y] = fam
    return {"chosen": chosen, "fallback": fb, "n_kept": n_kept, "reps": reps, "log": log}


def erc_cap25(funds, ctx, ex):
    w, _ = wt.risk_parity_weights(funds, ctx["wk"], ctx["vol_map"], method="erc")
    return wt.apply_cap(w, CAP)


def stream_idx(ctxs, quals, exs, idx_tabs, rc, country_rule=False, weigher=erc_cap25):
    held, prev_fb = {}, False
    sleeves, recs = {}, []
    for ctx in ctxs:
        qi = ctx["qi"]
        q = quals[qi]
        fam_ok = set(q.index[q["pass_q1"] & q["pass_q2"]])
        it = ctx["i_t"][ctx["i_t"]["family"].isin(fam_ok)]
        rec = select_idx(ctx, it, held, prev_fb, exs[qi], idx_tabs[qi], rc, country_rule)
        rec.update({"qi": qi, "t": ctx["t"], "prev_fb": prev_fb})
        recs.append(rec)
        if rec["fallback"]:
            held, prev_fb = {}, True
            sleeves[qi] = ctx["b0_w"]
            continue
        funds = [v[0] for v in rec["chosen"].values()]
        sleeves[qi] = weigher(funds, ctx, exs[qi])
        held = {fam: (v[0], v[1]) for fam, v in rec["chosen"].items()}
        prev_fb = False
    return {"sleeves": sleeves, "recs": recs}


# ---------------- env per offset ----------------
def build_env(k):
    E = ro.setup_env_off(k, set(), CTX[k])
    E["ctx15"] = [c for c in E["ctx_h"] if c["qi"] < 15]
    for c in E["ctx15"]:
        for fc, s in c["wk"].items():
            assert len(s) == 0 or s.index.max() <= c["t"], "look-ahead weekly"
    IS = IndexSignals(E["calendar"])
    E["IS"] = IS
    E["idx_tabs"], E["exs"], E["raw_ex"] = {}, {}, {}
    for c in E["ctx15"]:
        E["idx_tabs"][c["qi"]] = IS.at(c["t"], E["h_by_q"][c["qi"]])
        ex, cdf, sdf = exposure_at(E["nav"], E["nav_by_fund"], IS.lc, IS.ls, c["t"], c["i_t"]["FundCode"].tolist())
        E["exs"][c["qi"]] = ex
        E["raw_ex"][c["qi"]] = (cdf, sdf)
    return E


def prep_only():
    t0 = time.time()
    for k in (1, 2):
        E = ro.setup_env_off(k, set(), CTX[k])
        IS = IndexSignals(E["calendar"])
        for c in [c for c in E["ctx_h"] if c["qi"] < 15]:
            exposure_at(E["nav"], E["nav_by_fund"], IS.lc, IS.ls, c["t"], c["i_t"]["FundCode"].tolist())
            print(f"[prep off{k}] {c['t'].date()} ({time.time()-t0:.0f}s)", flush=True)
    return 0


def sim(plan, E, kinds):
    return ro.sims_for("B", plan, E, None, kinds)


def yearly(r):
    return ((1 + r).groupby(r.index.year).prod() - 1).to_dict()


def plan_diag(plan, st, E):
    rows = []
    for p, rec in zip(plan, st["recs"]):
        qi = rec["qi"]
        ex = E["exs"][qi]
        tab = E["idx_tabs"][qi]
        w = {f: v for f, v in p["weights"].items() if f != "__CASH__" and v > 1e-12}
        cash = float(p["weights"].get("__CASH__", 0.0))
        eqw = 1.0 - cash
        cw = {}
        for f, v in w.items():
            cp = ex.get(f, {}).get("country_primary") or "NA"
            cw[cp] = cw.get(cp, 0.0) + v
        topc = max(cw, key=cw.get) if cw else ""
        lg = rec["log"]
        top5 = ";".join(f"{r.idx}:{r.SR12_idx:.2f}" for r in tab.head(5).itertuples())
        picks = "" if rec["fallback"] else ";".join(f"{fc}->{X}{'(keep)' if kept else ''}" for fc, X, kept in rec["chosen"].values())
        rows.append({"t": p["t"].date(), "fallback_B0": rec["fallback"], "n_funds": len(w), "n_kept": rec["n_kept"], "cash": cash,
                     "top5_idx": top5, "picks": picks, "n_idx_walked": lg["walked"],
                     "skip_structural": len(lg["structural"]), "skip_no_eligible": len(lg["no_eligible"]), "skip_occupied": len(lg["occupied"]),
                     "skip_blocked": len(lg["blocked"]), "rej_a_family": lg["rej_a"], "rej_b_index": lg["rej_b"], "rej_c_corr": lg["rej_c"],
                     "rej_c_pairs": ";".join(lg["rej_c_list"]),
                     "skipped_idx": ";".join(lg["structural"] + lg["no_eligible"] + lg["occupied"] + lg["blocked"]),
                     "n_countries": len(cw), "max_country": topc, "max_country_w_total": cw.get(topc, np.nan),
                     "max_country_w_equity": cw.get(topc, np.nan) / eqw if eqw > 0 and cw else np.nan,
                     "max_w_fund": max(w.values()) if w else np.nan,
                     "holdings": ";".join(f"{f}:{v:.3f}" for f, v in sorted(w.items(), key=lambda kv: -kv[1]))})
    return pd.DataFrame(rows)


# ---------------- main ----------------
def main():
    global PHASE_B
    t0 = time.time()
    envs, P, S, ST = {}, {}, {}, {}
    for k in ro.OFFSETS:
        E = build_env(k)
        envs[k] = E
        rc = r10.RhoCache()
        st_idx = stream_idx(E["ctx15"], E["quals"], E["exs"], E["idx_tabs"], rc)
        st_s = r12.stream(E["ctx15"], E["quals"], "S", {})
        ST[k] = {NAME: st_idx, "M012-QF-S": st_s}
        P[k] = {NAME: r12.to_plan(st_idx, E["q15"], E["calendar"], E["acwi"]),
                "M012-QF-S": r12.to_plan(st_s, E["q15"], E["calendar"], E["acwi"]),
                "Trend25": r11.build_plan(E["ctx_old"], E["q15"], E["calendar"], E["acwi"], E["fd_dec"], {})[0]}
        kinds = KINDS if k == 0 else ["full", "c0"]
        S[k] = {m: sim(P[k][m], E, kinds) for m in P[k]}
        print(f"[off{k}] done ({time.time()-t0:.0f}s) t0={E['q15'][0].date()}", flush=True)
    E0, real = envs[0], envs[0]["real"]

    # ---------- (A) regression + leak checks ----------
    ref12 = float(pd.read_csv(os.path.join(RES, "M012_results.csv")).set_index(["trial", "cost"]).loc[("M012-QF-S", "full"), "sharpe_real"])
    ref_t = float(pd.read_csv(os.path.join(RES, "REAL_RF_summary.csv")).set_index("trial").loc["M004-TF-FX", "sharpe_full_real"])
    got12 = rr.metrics(S[0]["M012-QF-S"]["full"]["values"], real)["sharpe"]
    gott = rr.metrics(S[0]["Trend25"]["full"]["values"], real)["sharpe"]
    # spot refit: ไม่ใช้ cache สำหรับ 12 กองแรกของ I_t ที่ 3 ไตรมาส -> primary/R² ต้องตรง cache
    spot_ok, spot_n = True, 0
    for qi in (0, 7, 14):
        c = E0["ctx15"][qi]
        codes = sorted(c["i_t"]["FundCode"])[:12]
        cdf, sdf = E0["raw_ex"][qi]
        for scope, cols, lvl, ref in (("country", config.SCORE_COUNTRY_CLEAN, E0["IS"].lc, cdf), ("sector", SECTOR_ALL, E0["IS"].ls, sdf)):
            fr = exposure.fit_scope(codes, E0["nav_by_fund"], lvl, cols, c["t"], scope, use_cache=False).set_index("FundCode")
            rf_ = ref.set_index("FundCode").loc[codes]
            same = (fr["primary"].fillna("") == rf_["primary"].fillna("")).all() and np.allclose(fr["r2"].fillna(-9), rf_["r2"].fillna(-9), atol=1e-6)
            spot_ok &= bool(same)
            spot_n += len(codes)
    # leak: index table built from levels <= t (assert in IndexSignals.at), weekly <= t (assert build_env), Quality <= t (assert r12.Quality.table)
    reg = {"M012S_full": got12, "M012S_ref": ref12, "Trend25_full": gott, "Trend25_ref": ref_t, "spot_refit_ok": spot_ok, "spot_refit_n": spot_n,
           "leak_asserts": "index levels<=t, weekly<=t, exposure fit<=t (cache key=t + refit), quality<=t"}
    reg["ok"] = bool(abs(got12 - ref12) < 5e-7 and abs(gott - ref_t) < 5e-7 and spot_ok)
    print("REGRESSION:", json.dumps(reg, default=str), flush=True)
    json.dump(reg, open(os.path.join(SCRATCH, "validator_m017_regression.json"), "w"), default=str)
    if not reg["ok"]:
        print("REGRESSION FAIL — หยุด (ไม่นับ trial)", flush=True)
        return 2
    PHASE_B = True

    # ---------- (B) offset 0 fee cases ----------
    names = [NAME, "Trend25", "M012-QF-S"]
    rows, MR = [], {}
    for m in names:
        for kind in KINDS:
            x = rr.metrics(S[0][m][kind]["values"], real)
            MR[(m, kind)] = x
            lo, hi = rr.boot_ci(x["r"], x["rfm"])
            yr = yearly(x["r"])
            rows.append({"model": m, "fee": kind, "sharpe": x["sharpe"], "cagr": x["cagr"], "vol": x["vol"], "max_dd": x["max_dd"],
                         "cost_pct_yr": S[0][m][kind]["cost_bp_yr"] / 100.0, "turn_yr": S[0][m][kind]["turn_yr"],
                         "dsr34": rr.dsr_s(x["r"], x["rfm"], N_TRIAL), "ci_lo": lo, "ci_hi": hi,
                         "sharpe_2022": x["sharpe_2022"], "sharpe_2307_2512": x["sharpe_2307_2512"], "n_months": x["n_months"],
                         **{f"ret_{y}": yr.get(y, np.nan) for y in (2022, 2023, 2024, 2025)}})
    R = pd.DataFrame(rows)
    R.to_csv(os.path.join(RES, "M017_results.csv"), index=False)
    pr = []
    for other in ("Trend25", "M012-QF-S"):
        for kind in ("full", "nofront", "flat"):
            lo, hi, pt = r11.paired_real(MR[(NAME, kind)]["r"], MR[(other, kind)]["r"], MR[(NAME, kind)]["rfm"], "r")
            pr.append({"vs": other, "fee": kind, "d_sharpe": pt, "ci_lo": lo, "ci_hi": hi, "d_cagr": MR[(NAME, kind)]["cagr"] - MR[(other, kind)]["cagr"]})
    PR = pd.DataFrame(pr)
    PR.to_csv(os.path.join(RES, "M017_paired.csv"), index=False)

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
    OF.to_csv(os.path.join(RES, "M017_offsets.csv"), index=False)
    fu = pd.read_csv(os.path.join(RES, "FULLUNIV_offsets.csv"))
    fu = fu[(fu["model"] == "B") & (fu["offset"].isin(["0", "1", "2"]))].set_index("offset")
    off_reg = max(abs(float(fu.loc[str(k), "sharpe"]) - float(OF[(OF.model == "Trend25") & (OF.offset == k)]["sharpe"].iloc[0])) for k in ro.OFFSETS)
    print(f"offset regression Trend25 vs FULLUNIV max|d| {off_reg:.2e}", flush=True)
    assert off_reg < 5e-7

    DG = plan_diag(P[0][NAME], ST[0][NAME], E0)
    DG.to_csv(os.path.join(RES, "M017_quarter_diag.csv"), index=False)
    dg_off = {k: plan_diag(P[k][NAME], ST[k][NAME], envs[k]) for k in ro.OFFSETS}
    pd.concat([d.assign(offset=k) for k, d in dg_off.items()]).to_csv(os.path.join(RES, "M017_quarter_diag_offsets.csv"), index=False)
    pd.concat([E0["idx_tabs"][q].assign(t=E0["ctx15"][q]["t"].date()) for q in range(15)]).to_csv(os.path.join(RES, "M017_index_scores.csv"), index=False)
    wr = []
    for k in ro.OFFSETS:
        for en in S[k][NAME]["full"]["entries"]:
            for f, w in en["target"].items():
                if w > 1e-12:
                    wr.append({"offset": k, "t": en["t"].date(), "e": en["e"].date(), "FundCode": f, "weight": w})
    pd.DataFrame(wr).to_csv(os.path.join(RES, "M017_weights.csv"), index=False)
    pd.DataFrame({f"{m}_{kind}": S[0][m][kind]["values"] for m in names for kind in ("full", "c0")}).to_csv(os.path.join(RES, "M017_equity_curve.csv"))

    m17 = MR[(NAME, "full")]
    verdict = "ผ่าน" if (m17["max_dd"] >= DD_FLOOR and m17["cagr"] > TARGET_CAGR) else "ไม่ผ่าน"
    out = {"R": R, "PR": PR, "OF": OF, "DG": DG, "dg_off": dg_off, "verdict": verdict, "reg": reg, "off_reg": off_reg}
    write_md(out)
    append_trial(out)
    pd.set_option("display.width", 250)
    print(R.round(4).to_string())
    print(PR.round(4).to_string())
    print(OF.round(4).to_string())
    print(DG.drop(columns=["holdings", "rej_c_pairs", "skipped_idx"]).to_string())
    print("verdict", verdict)
    print(f"DONE {time.time()-t0:.0f}s", flush=True)
    return 0


def pc(x, d=2):
    return "—" if x != x else f"{x*100:.{d}f}%"


def write_md(o):
    R, PR, OF, DG = o["R"], o["PR"], o["OF"], o["DG"]
    g = lambda m, k: R[(R.model == m) & (R.fee == k)].iloc[0]
    L = []
    A = L.append
    A("# M017-IDX — คัดดัชนี MSCI ก่อน แล้วเลือกกองที่ตามดัชนี (index-first) บน M012-QF-S — ผลวัด\n")
    A(f"รันเมื่อ {pd.Timestamp.now().isoformat()} · spec `specs/M017_index_first.md` (ลงทะเบียนก่อนรัน) · **trial #34** · universe เต็ม · rf จริง · "
      "FeeData(legacy=False) Actual · เม.ย. 2022–ธ.ค. 2025 (45 เดือน) · Sharpe = mean(r−rf)×12/(sd(r)×√12) · โค้ด `backtest/run_m017.py`\n")
    rg = o["reg"]
    A(f"**Regression (ผ่าน)**: M012-QF-S full {rg['M012S_full']:.6f} (ref {rg['M012S_ref']:.6f}) · Trend 25 {rg['Trend25_full']:.6f} (ref {rg['Trend25_ref']:.6f}) · "
      f"Trend 25 offset 0/1/2 = `FULLUNIV_offsets.csv` (max|Δ| {o['off_reg']:.1e}) · refit exposure ไม่ใช้ cache {rg['spot_refit_n']} กอง-scope = cache ({rg['spot_refit_ok']}) · "
      f"assert ไม่มีข้อมูลหลัง t: {rg['leak_asserts']}\n")
    m = g(NAME, "full")
    A(f"## 1. ผลตามเกณฑ์ที่ล็อก (fee full): **{o['verdict']}**\n")
    A(f"- CAGR {pc(m.cagr)} (เกณฑ์ > 9.09%: {'✓' if m.cagr > TARGET_CAGR else '✗'}) · maxDD {pc(m.max_dd)} (เกณฑ์ ≥ −20%: {'✓' if m.max_dd >= DD_FLOOR else '✗'}) · Sharpe {m.sharpe:.3f}\n")
    A("## 2. ตารางหลัก (offset 0, 45 เดือน, rf จริง)\n")
    A("| โมเดล | fee | Sharpe | CAGR | vol | maxDD | ต้นทุน %/ปี | turnover/ปี | DSR@34 | CI95% Sharpe | 2022 (เม.ย.–) | 2023 | 2024 | 2025 |")
    A("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    lab = {"full": "full (จริง)", "nofront": "nofront", "flat": "flat 0.5%/ข้าง", "c0": "0%"}
    for mm in (NAME, "Trend25", "M012-QF-S"):
        for k in KINDS:
            x = g(mm, k)
            A(f"| {'**'+mm+'**' if mm == NAME else mm} | {lab[k]} | {x.sharpe:.3f} | {pc(x.cagr)} | {pc(x.vol)} | {pc(x.max_dd)} | {x.cost_pct_yr:.2f} | {x.turn_yr:.2f} | "
              f"{x.dsr34:.3f} | [{x.ci_lo:.2f}, {x.ci_hi:.2f}] | {pc(x.ret_2022,1)} | {pc(x.ret_2023,1)} | {pc(x.ret_2024,1)} | {pc(x.ret_2025,1)} |")
    A("\n(DSR@34 ของ Trend 25 / M012-QF-S คำนวณที่ n = 34 เพื่อเทียบเท่านั้น · M016-CW อ้างอิงจาก `M016_results.csv`: 0.541 / 7.85% / −19.73% — ไม่ได้รันซ้ำ)\n")
    A("## 3. Paired Δ (M017-IDX − อ้างอิง, block bootstrap 3, 2000, seed 0)\n")
    A("| เทียบ | fee | Δ Sharpe | CI95% | Δ CAGR |\n|---|---|---|---|---|")
    for r in PR.itertuples():
        A(f"| {r.vs} | {r.fee} | {r.d_sharpe:+.3f} | [{r.ci_lo:+.2f}, {r.ci_hi:+.2f}] | {r.d_cagr*100:+.2f} pt |")
    A("\n## 4. เลื่อนเดือน rebalance (fee full · ช่วงร่วม ก.ค. 2022–ธ.ค. 2025 = 42 เดือน)\n")
    A("| โมเดล | offset | Sharpe | CAGR | vol | maxDD | ต้นทุน %/ปี | turnover/ปี | Sharpe/CAGR/maxDD ช่วงเต็มของ offset |")
    A("|---|---|---|---|---|---|---|---|---|")
    for r in OF.itertuples():
        A(f"| {r.model} | {r.offset} | {r.sharpe:.3f} | {pc(r.cagr)} | {pc(r.vol)} | {pc(r.max_dd)} | {r.cost_pct_yr:.2f} | {r.turn_yr:.2f} | "
          f"{r.sharpe_origwin:.3f} / {pc(r.cagr_origwin)} / {pc(r.maxdd_origwin)} ({r.n_months_origwin}m) |")
    A("\n| โมเดล | Sharpe เฉลี่ย 3 offset (min–max) | CAGR เฉลี่ย (min–max) | maxDD แย่สุด |\n|---|---|---|---|")
    for mm in (NAME, "Trend25", "M012-QF-S"):
        d = OF[OF.model == mm]
        A(f"| {mm} | {d.sharpe.mean():.3f} ({d.sharpe.min():.3f}–{d.sharpe.max():.3f}) | {pc(d.cagr.mean())} ({pc(d.cagr.min())}–{pc(d.cagr.max())}) | {pc(d.max_dd.min())} |")
    A("\n## 5. กลไกต่อไตรมาส (offset 0)\n")
    A(f"- fallback B0: **{int(DG.fallback_B0.sum())}/15** ไตรมาส · กองเฉลี่ย {DG.n_funds.mean():.2f} · ถือต่อเฉลี่ย {DG.n_kept.mean():.2f} · "
      f"ปัดเพราะ corr รวม {int(DG.rej_c_corr.sum())} · ปัดเพราะกฎ 1 ดัชนี→1 กอง {int(DG.rej_b_index.sum())} · family ซ้ำ {int(DG.rej_a_family.sum())}")
    A(f"- ดัชนีที่ถูกข้าม (รวม 15 ไตรมาส): เชิงโครงสร้าง (ดัชนีรวม ไม่มีใน exposure) {int(DG.skip_structural.sum())} · ไม่มีกองมีสิทธิ์ {int(DG.skip_no_eligible.sum())} · "
      f"ช่องถูกครอง {int(DG.skip_occupied.sum())} · มีกองแต่ถูกปัดหมด {int(DG.skip_blocked.sum())}")
    A(f"- จำนวนประเทศ (country_primary) เฉลี่ย {DG.n_countries.mean():.2f} (min {DG.n_countries.min()}) · น้ำหนักรวมใน 1 ประเทศสูงสุด {pc(DG.max_country_w_total.max(),1)} ของพอร์ตรวม / "
      f"{pc(DG.max_country_w_equity.max(),1)} ของส่วนหุ้น · กองเดียวสูงสุด {pc(DG.max_w_fund.max(),1)}")
    for k, d in o["dg_off"].items():
        A(f"- offset {k}: B0 {int(d.fallback_B0.sum())} · กองเฉลี่ย {d.n_funds.mean():.2f} · ปัด corr {int(d.rej_c_corr.sum())} · ประเทศเฉลี่ย {d.n_countries.mean():.2f} · ประเทศสูงสุด {pc(d.max_country_w_total.max(),1)}")
    A("\n| t | top-5 ดัชนี (SR12_idx) | กองที่เลือก → ดัชนี | ข้าม (โครงสร้าง/ไม่มีกอง/ครอง/ปัดหมด) | ปัด b / corr | B0 | ประเทศ | ประเทศสูงสุด (พอร์ตรวม) |")
    A("|---|---|---|---|---|---|---|---|")
    for r in DG.itertuples():
        A(f"| {r.t} | {r.top5_idx.replace('MSCI_', '')} | {r.picks.replace('MSCI_', '') or '—'} | {r.skip_structural}/{r.skip_no_eligible}/{r.skip_occupied}/{r.skip_blocked} | "
          f"{r.rej_b_index} / {r.rej_c_corr} | {'B0' if r.fallback_B0 else '-'} | {r.n_countries} | {str(r.max_country).replace('MSCI_', '')} {pc(r.max_country_w_total,1)} |")
    A("\n## 6. ไฟล์\n`M017_results.csv`, `M017_paired.csv`, `M017_offsets.csv`, `M017_quarter_diag.csv`, `M017_quarter_diag_offsets.csv`, `M017_index_scores.csv`, "
      "`M017_weights.csv`, `M017_equity_curve.csv`, `scratch/validator_m017_regression.json`")
    open(os.path.join(RES, "M017_summary.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")


def backup_trials():
    dst = os.path.join(TEAM_DIR, f"trials.backup_{pd.Timestamp.now().strftime('%Y%m%dT%H%M%S')}.csv")
    shutil.copy2(TRIALS_CSV, dst)
    return dst


def append_line(vals):
    txt = open(TRIALS_CSV, encoding="utf-8", newline="").read()
    assert not any(l.startswith(f"{NAME},") and ",ok," in l for l in txt.splitlines()), "M017-IDX (ok) มีใน trials.csv แล้ว"
    line = ",".join(str(v).replace(",", ";") for v in vals)
    with open(TRIALS_CSV, "a", encoding="utf-8", newline="") as f:
        if not txt.endswith("\n"):
            f.write("\r\n")
        f.write(line + "\r\n")


def append_trial(o):
    R, PR, DG = o["R"], o["PR"], o["DG"]
    m = R[(R.model == NAME) & (R.fee == "full")].iloc[0]
    sh = {k: R[(R.model == NAME) & (R.fee == k)].iloc[0].sharpe for k in KINDS}
    pt = PR[(PR.vs == "Trend25") & (PR.fee == "full")].iloc[0]
    ps = PR[(PR.vs == "M012-QF-S") & (PR.fee == "full")].iloc[0]
    of = o["OF"][o["OF"].model == NAME]
    crashed_before = any(l.startswith(f"{NAME},") for l in open(TRIALS_CSV, encoding="utf-8").read().splitlines())
    params = (f"{NAME}: rank 28 MSCI (18 country+10 sector THB levels) by SR12_idx=(R12_1-h_t)/vol52 real BOT hurdle; eligible fund = rep class in M012-QF-S I_t' "
              f"with idx = ElasticNet PIT primary in scope & R2>=0.50 & coef>0; fill rank1->28 best SR12' per idx; 1 idx->1 fund (tracks overlap); rho_adj(M010)>0.85 reject min30w; "
              f"N=5; hold if idx rank<=10 & quality & still primary; ERC LW cap25%; B0 fallback <4; trend cash25%; fee=FEEUH Actual legacy=False")
    note = (f"pass rule CAGR>9.09% & maxDD>=-20% -> {o['verdict']}; Sharpe(real rf; sd(r)) 0%={sh['c0']:.3f} flat={sh['flat']:.3f} full={sh['full']:.3f} nofront={sh['nofront']:.3f}; "
            f"CAGR full {m.cagr:.4f}; CI95 ({m.ci_lo:.3f};{m.ci_hi:.3f}); paired dSharpe vs Trend25 {pt.d_sharpe:+.3f} CI ({pt.ci_lo:.3f};{pt.ci_hi:.3f}); "
            f"vs M012-QF-S {ps.d_sharpe:+.3f} CI ({ps.ci_lo:.3f};{ps.ci_hi:.3f}); offsets 0/1/2 common-42m Sharpe {'/'.join(f'{x:.3f}' for x in of.sharpe)} "
            f"CAGR {'/'.join(f'{x:.4f}' for x in of.cagr)}; B0 quarters {int(DG.fallback_B0.sum())}/15; corr rejects {int(DG.rej_c_corr.sum())}; "
            f"avg countries {DG.n_countries.mean():.2f}; 7 aggregate idx structurally no funds (country exposure 11 VIF-clean); n_months=45"
            + ("; rerun after crashed row (same locked spec; same trial #34)" if crashed_before else ""))
    vals = [NAME, pd.Timestamp.now().isoformat(), "M017_index_first.md", params, "2022-03-31", "2025-12-31",
            "BOT policy rate daily (TH_POLICY_RATE.csv)", "real fees SecFundFee FEEUH (full; FeeData legacy=False)",
            round(m.sharpe, 4), round(m.cagr, 4), round(m.vol, 4), round(m.max_dd, 4), round(m.turn_yr, 4), N_TRIAL, round(m.dsr34, 4), "ok", note]
    b = backup_trials()
    print(f"trials backup -> {b}", flush=True)
    append_line(vals)


if __name__ == "__main__":
    if "--prep" in sys.argv:
        sys.exit(prep_only())
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
                append_line([NAME, pd.Timestamp.now().isoformat(), "M017_index_first.md", f"{NAME} run crashed", "2022-03-31", "2025-12-31",
                             "BOT policy rate daily (TH_POLICY_RATE.csv)", "real fees SecFundFee FEEUH (full)", "", "", "", "", "", N_TRIAL, "", "crashed", last])
        except Exception:
            pass
        rc = 1
    sys.exit(rc)
