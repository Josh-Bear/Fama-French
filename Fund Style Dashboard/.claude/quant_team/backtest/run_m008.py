"""run_m008.py — M008-GC (cluster cap, n_trials 19) + M008-SQ (SR12 + Quality/LowVol tilt, n_trials 20) บน M004-TF-FX
ตาม specs/M008_style_macro.md (+ ผู้ใช้ตัดสินใจท้ายไฟล์) · ใช้ runner/simulate/weighting/fund_signals เดิม (วัดผลแบบใหม่ 45 เดือน)

รัน: PYTHONPATH=. ./.venv/bin/python .claude/quant_team/backtest/run_m008.py [smoke]
(ไม่เรียก nav_loader.load_nav_history / data_access.build_*; NAV จาก cache/nav_clean.parquet เท่านั้น)
"""
from __future__ import annotations

import copy
import os
import re
import sys
import time
import warnings
from collections import Counter

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if THIS_DIR not in sys.path:
    sys.path.insert(0, THIS_DIR)

import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import fcluster, linkage
from scipy.spatial.distance import squareform
from scipy.stats import spearmanr

import common
import config
import fund_signals as fs
import simulate
import tests_m006
import weighting as wt
import run_m006_m007 as r67
from data import msci_index

warnings.filterwarnings("ignore")
TEAM_DIR = os.path.dirname(THIS_DIR)
RES = common.RESULTS_DIR
SCRATCH = os.path.join(TEAM_DIR, "scratch")
PRIMARY_END, RF = r67.PRIMARY_END, r67.RF
COSTS, RFS = r67.COSTS, r67.RFS
SEL_N, SEL_K = 8, 16
STYLE = ["Momentum", "Quality", "Value", "LowVol"]
CTRL = ["MSCI_ACWI", "US_VS_ACWI", "ACWI_ETF"]
MACRO = ["Oil_Brent", "Gold", "USDTHB", "Copper", "DXY", "VIX", "US10Y"]
CUT, MAXPER, CAPG = 0.25, 3, 0.35

STREAMS = {
    "BASE": dict(kind="sr", cap_g=None, max_per=None),
    "GC": dict(kind="sr", cap_g=CAPG, max_per=MAXPER),
    "GC_T2": dict(kind="sr", cap_g=1.0, max_per=8),            # test: ต้องได้ BASE ตรงทุกหลัก
    "SQ": dict(kind="sq", w=(0.5, 0.25, 0.25)),
    "SQ_T1": dict(kind="sq", w=(1.0, 0.0, 0.0), winsor=False),  # test: ต้องได้ BASE ตรงทุกหลัก (ไม่ winsorize: monotonic -> rank เดิม)
    "SQ_T1W": dict(kind="sq", w=(1.0, 0.0, 0.0), winsor=True),  # ข้อมูล: (1,0,0) + winsorize ±3 (tie ปลายบนเปลี่ยน rank)
}
TRIAL_OF = {"BASE": "M004-TF-FX", "GC": "M008-GC", "SQ": "M008-SQ", "GC_T2": "T-GC2", "SQ_T1": "T-SQ1", "SQ_T1W": "T-SQ1W"}
NTR = {"M004-TF-FX": 9, "M008-GC": 19, "M008-SQ": 20}
THEMES = [("infra", r"INFRA"), ("india", r"INDIA|BHARAT|\bIN\b|TISCOIN"),
          ("tech", r"TECH|NASDAQ|NGF|INNOV|SEMI|DIGI|ROBO|\bAI\b|NDQ"),
          ("vietnam", r"VIET|VN"), ("china", r"CHINA|CHN|\bCN\b"), ("japan", r"JAP|JP"), ("gold", r"GOLD"),
          ("europe", r"EU|EURO"), ("us", r"\bUS\b|USA|SP500|S&P")]
THEMES3 = ("infra", "india", "tech")


def theme_of(fc):
    for name, pat in THEMES:
        if re.search(pat, fc.upper()):
            return name
    return "other"


# ---------------- factors (point-in-time: ใช้เฉพาะ ≤ week point) ----------------

def build_factor_daily():
    """เหมือนสคริปต์สำรวจทุกบรรทัด (รวม macro ใน concat เพื่อให้ index/ffill เหมือนกัน แล้วเลือกเฉพาะ CTRL+STYLE)."""
    c_lv = msci_index.load_country_index()
    st = pd.read_csv(config.STYLE_FACTOR_CSV, parse_dates=["Date"]).set_index("Date").sort_index()
    mc = pd.read_csv(config.MACRO_FACTOR_CSV, parse_dates=["Date"]).set_index("Date").sort_index()
    r = st.pct_change()
    lev = {}
    for f, (us, intl) in config.STYLE_TICKERS.items():
        rb = r[us] if intl is None else config.STYLE_US_WEIGHT * r[us] + (1 - config.STYLE_US_WEIGHT) * r[intl]
        lv = (1 + rb.fillna(0)).cumprod()
        lev[f] = lv / (st[config.STYLE_BENCHMARK_TICKER] / st[config.STYLE_BENCHMARK_TICKER].iloc[0])
    style_lv = pd.DataFrame(lev)
    assert list(style_lv.columns) == STYLE
    ctrl = pd.DataFrame({"MSCI_ACWI": c_lv["MSCI_ACWI"], "US_VS_ACWI": c_lv["MSCI_USA"] / c_lv["MSCI_ACWI"]})
    fac = pd.concat([ctrl, st[[config.STYLE_BENCHMARK_TICKER]].rename(columns={"ACWI": "ACWI_ETF"}), style_lv, mc[MACRO]],
                    axis=1).sort_index().ffill(limit=10)
    return fac[CTRL + STYLE]


def factor_weekly(fac_daily, weeks):
    rows = []
    for w in weeks:
        sub = fac_daily.loc[:w]
        assert sub.index.max() <= w
        rows.append(sub.iloc[-1] if len(sub) else pd.Series(np.nan, index=fac_daily.columns))
    return pd.DataFrame(rows, index=weeks).pct_change().iloc[1:]


def ols(y, X):
    """OLS + intercept · beta ต่อ 1 SD ของ factor · t-stat (เหมือนสคริปต์สำรวจ)."""
    m = ~(np.isnan(y) | np.isnan(X).any(1))
    y, X = y[m], X[m]
    n, k = X.shape
    if n < k + 10:
        return None
    sd = X.std(0, ddof=1)
    sd[sd == 0] = 1
    Z = np.column_stack([np.ones(n), (X - X.mean(0)) / sd])
    beta, *_ = np.linalg.lstsq(Z, y, rcond=None)
    res = y - Z @ beta
    s2 = res @ res / (n - k - 1)
    cov = s2 * np.linalg.pinv(Z.T @ Z)
    tt = beta / np.sqrt(np.clip(np.diag(cov), 1e-30, None))
    return {"beta": beta[1:], "t": tt[1:], "n": n}


def zscore(s: pd.Series, winsor: bool = True) -> pd.Series:
    sd = s.std(ddof=1)
    z = (s - s.mean()) / (sd if sd > 0 else 1.0)
    return z.clip(-3.0, 3.0) if winsor else z


# ---------------- cluster (spec §1 ข้อ 2) ----------------

def cluster_labels(wk: dict, funds: list) -> dict:
    R = pd.DataFrame({fc: wk[fc] for fc in funds})
    C = R.corr(min_periods=40).fillna(0).to_numpy().copy()
    np.fill_diagonal(C, 1)
    D = np.clip(1 - C, 0, 2)
    lab = fcluster(linkage(squareform(D, checks=False), "average"), CUT, "distance")
    return dict(zip(funds, [int(x) for x in lab]))


def select_cluster(reps, ranks, held_map, n_target, k_drop, lab, max_per):
    """hysteresis_select + ≤ max_per กอง/cluster (spec §1 ข้อ 3) · ลำดับ insertion ใน S เหมือน wt.hysteresis_select
    (ถือก่อนตามลำดับ held_map แล้วเติมตาม rank) เพื่อให้ max_per=8 ได้ผลเหมือนเดิมทุกหลัก."""
    kept = [(fam, fc) for fam, fc in held_map.items()
            if fam in reps and ranks.get(fam, 10**9) <= k_drop and reps[fam]["FundCode"] == fc]
    by_g = {}
    for fam, fc in kept:
        by_g.setdefault(lab[fc], []).append(fam)
    drop = set()
    for g, fams in by_g.items():
        if len(fams) > max_per:
            worst = sorted(fams, key=lambda f: ranks[f], reverse=True)[:len(fams) - max_per]
            drop |= set(worst)
    S, cnt = {}, Counter()
    for fam, fc in kept:
        if fam in drop:
            continue
        S[fam] = fc
        cnt[lab[fc]] += 1
    n_kept, n_cut_held = len(S), len(drop)
    skipped, max_rank = 0, 0
    for fam in sorted(reps.keys(), key=lambda f: ranks.get(f, 10**9)):
        if len(S) >= n_target:
            break
        if fam in S:
            continue
        fc = reps[fam]["FundCode"]
        max_rank = max(max_rank, ranks.get(fam, 0))
        if cnt[lab[fc]] >= max_per:
            skipped += 1
            continue
        S[fam] = fc
        cnt[lab[fc]] += 1
    return {"S": S, "n_kept": n_kept, "n_added": len(S) - n_kept, "n_skipped_cluster": skipped,
            "n_cut_held_cluster": n_cut_held, "fallback": "b0" if len(S) < 4 else None, "max_rank_reached": max_rank}


# ---------------- group cap (spec §1 ข้อ 4) ----------------

def group_cap(w: pd.Series, lab_of: dict, cap_g: float, cap_f: float = 0.25, tol: float = 1e-9, max_iter: int = 50):
    """water-filling: ส่วนเกินของกลุ่มที่เกินแจกให้กองในกลุ่มที่ยังไม่เต็มตามสัดส่วนน้ำหนัก (ไม่เกินเพดานกอง/กลุ่ม) · คืน (w, flag, cap_used)."""
    w = w.copy().astype(float)
    if cap_g >= 1.0:
        return w, "", cap_g
    grp = pd.Series({f: lab_of[f] for f in w.index})
    sizes = grp.value_counts()
    ng = len(sizes)
    feas = lambda c: sum(min(c, cap_f * s) for s in sizes) >= 1.0 - 1e-12
    flag = ""
    if not feas(cap_g):
        c2 = 1.0 / ng
        if feas(c2):
            cap_g, flag = c2, "infeasible->cap=1/ng"
        else:
            return w, "infeasible->no_group_cap", 1.0
    for _ in range(max_iter):
        gw = w.groupby(grp).sum()
        over = gw[gw > cap_g + tol]
        if over.empty:
            break
        excess = 0.0
        for g in over.index:
            m = (grp == g).to_numpy()
            excess += float(gw[g] - cap_g)
            w[m] = w[m] * (cap_g / gw[g])
        for _k in range(50):
            if excess <= 1e-13:
                break
            gw = w.groupby(grp).sum()
            groom = (cap_g - gw).reindex(grp.values).to_numpy()
            room = np.minimum(cap_f - w.to_numpy(), groom)
            elig = room > 1e-13
            if not elig.any():
                break
            base = w.to_numpy() * elig
            add = pd.Series(np.minimum(excess * base / base.sum(), room), index=w.index)
            ga = add.groupby(grp).sum()
            fac = ((cap_g - gw) / ga.replace(0, np.nan)).clip(upper=1.0).fillna(1.0)
            add = add * grp.map(fac)
            w = w + add
            excess -= float(add.sum())
        if excess > 1e-9:
            flag = (flag + ";" if flag else "") + "unplaced_excess"
            break
    return w, flag, cap_g


# ---------------- selection ต่อไตรมาส ----------------

def select_quarter(t, nav, nav_arrays, calendar, groups, fac_daily, state):
    """คืน dict ต่อ stream + ข้อมูลร่วม · state[s] = (held dict, prev_fb) (ไม่แก้ state ในนี้)."""
    u_t = common.universe_at(nav, t)
    b0_df = common.b0_universe(u_t, groups)
    b0_w = pd.Series(1.0 / len(b0_df), index=b0_df["FundCode"])
    qctx = fs.QuarterContext(nav_arrays, calendar, t)
    assert qctx.weeks[-1] <= t and qctx.months[-1] <= t, "look-ahead: anchor เกิน t"
    sig_df = fs.compute_quarter_signals(qctx, u_t["FundCode"].tolist())
    i_t, _, _ = fs.investable_set(t, u_t, sig_df, groups, family_fix=True)
    funds = list(i_t["FundCode"])
    wk = {fc: qctx.weekly_return_series(fc) for fc in funds}
    vol_map = dict(zip(i_t["FundCode"], i_t["vol52"]))
    labels = cluster_labels(wk, funds)

    # style beta (SQ)
    fw = factor_weekly(fac_daily, qctx.weeks)
    assert fw.index.max() <= t
    fac_ok = int(fw.notna().all(1).sum())
    X = fw[CTRL + STYLE].to_numpy(float)
    fits = {}
    for fc in funds:
        y = wk[fc].to_numpy(float)
        if np.isfinite(y).sum() < 40 or fac_ok < 40:
            continue
        f = ols(y, X)
        if f is not None:
            fits[fc] = f
    i_sq = i_t[i_t["FundCode"].isin(fits)].copy().reset_index(drop=True)
    betaQ = pd.Series({fc: fits[fc]["beta"][4] for fc in i_sq["FundCode"]})
    betaL = pd.Series({fc: fits[fc]["beta"][6] for fc in i_sq["FundCode"]})
    i_sq["betaQ"] = i_sq["FundCode"].map(betaQ)
    i_sq["betaL"] = i_sq["FundCode"].map(betaL)
    scores = {}
    for s, cfg in STREAMS.items():
        if cfg["kind"] == "sq":
            a, b, c = cfg["w"]
            wz = cfg.get("winsor", True)
            scores[s] = a * zscore(i_sq["SR12"], wz) + b * zscore(i_sq["betaQ"], wz) + c * zscore(i_sq["betaL"], wz)

    erc_cache, out = {}, {}
    for s, cfg in STREAMS.items():
        if cfg["kind"] == "sq":
            df = i_sq.copy()
            df["score"] = scores[s].to_numpy()
            col = "score"
        else:
            df, col = i_t, "SR12"
        held, pfb = state[s]
        reps = wt.family_representatives(df, col, held_funds=set(held.values()))
        ranks = wt.rank_families(reps)
        held_map = {} if pfb else held
        if cfg["kind"] == "sr" and cfg["max_per"] is not None:
            sel = select_cluster(reps, ranks, held_map, SEL_N, SEL_K, labels, cfg["max_per"])
        else:
            sel = wt.hysteresis_select(reps, ranks, held_map, SEL_N, SEL_K, None, rho_max=0.85)
            sel["n_skipped_cluster"], sel["n_cut_held_cluster"] = 0, 0
        r = {"sel": sel, "n_I": len(df), "flag": "", "cap_g": cfg.get("cap_g")}
        if sel["fallback"] == "b0" or len(sel["S"]) == 0:
            r.update(S={}, fb=True, sleeve=b0_w)
        else:
            funds_s = list(sel["S"].values())
            key = tuple(funds_s)
            if key not in erc_cache:
                w, _ = wt.risk_parity_weights(funds_s, wk, vol_map, method="erc")
                erc_cache[key] = wt.apply_cap(w, 0.25)
            sl = erc_cache[key]
            if cfg["kind"] == "sr" and cfg["cap_g"] is not None:
                sl, flag, cu = group_cap(sl, labels, cfg["cap_g"])
                r["flag"], r["cap_g"] = flag, cu
            r.update(S=dict(sel["S"]), fb=False, sleeve=sl)
        out[s] = r
    return {"streams": out, "labels": labels, "n_I": len(i_t), "n_fit": len(i_sq), "i_t": i_t, "i_sq": i_sq,
            "scores": scores, "betaQ": betaQ, "betaL": betaL, "fits": fits, "b0_w": b0_w}


# ---------------- helpers ----------------

def theme_shares(w: pd.Series, themes=None):
    th = pd.Series({f: theme_of(f) for f in w.index})
    g = w.groupby(th).sum()
    g = g[[i for i in g.index if i != "other" and (themes is None or i in themes)]]
    return (g.max() if len(g) else 0.0), (g.idxmax() if len(g) else "")


def drop_best_q(r, rf):
    qs = r.groupby(r.index.to_period("Q")).apply(lambda x: (1 + x).prod() - 1)
    best = qs.idxmax()
    return simulate.sharpe(r[r.index.to_period("Q") != best], rf), str(best)


def run(smoke=False):
    t0 = time.time()
    print("[1/6] load...", flush=True)
    nav = common.load_nav()
    nav_by_fund = common.build_nav_by_fund(nav)
    nav_arrays = fs._prep_arrays(nav_by_fund)
    calendar = common.load_calendar()
    groups = common.load_groups()
    acwi = msci_index.load_country_index()["MSCI_ACWI"]
    fac_daily = build_factor_daily()
    all_codes = sorted(nav["FundCode"].unique())
    san, _ = tests_m006.run_all(groups, all_codes, os.path.join(SCRATCH, "validator_m008_family_diff.csv"))
    assert all(san.values()), "tests_m006 ล้มเหลว"

    quarters = common.quarter_ends(calendar, "2022-03-31", "2025-09-30")
    if smoke:
        quarters = quarters[:5]
    nq = len(quarters)
    t_first = quarters[0]
    bound_m = quarters[-1] + pd.Timedelta(days=75)
    sim_months = [m for m in common.month_ends(calendar, common.execution_date(calendar, t_first), "2026-03-31")
                  if m <= bound_m + pd.Timedelta(days=31)]
    if not smoke:
        assert sim_months[-1] == PRIMARY_END
    years = (sim_months[-1] - common.execution_date(calendar, t_first)).days / 365.25 if smoke else \
        (PRIMARY_END - common.execution_date(calendar, t_first)).days / 365.25

    # ---- walk-forward ----
    state = {s: ({}, False) for s in STREAMS}
    sleeves = {s: {} for s in STREAMS}
    states_in, qres, log_rows, cl_rows = [], [], [], []
    fb_count = Counter()
    for qi, t in enumerate(quarters):
        states_in.append(copy.deepcopy(state))
        q = select_quarter(t, nav, nav_arrays, calendar, groups, fac_daily, state)
        qres.append(q)
        for s, r in q["streams"].items():
            sel = r["sel"]
            if r["fb"]:
                fb_count[s] += 1
                state[s] = ({}, True)
            else:
                state[s] = (dict(r["S"]), False)
            sleeves[s][qi] = r["sleeve"]
            if s in ("BASE", "GC", "SQ"):
                sw = r["sleeve"]
                lab = q["labels"]
                cg = pd.Series({f: lab.get(f, -1) for f in sw.index}).pipe(lambda g: sw.groupby(g).sum())
                log_rows.append({"trial": TRIAL_OF[s], "t": t.date(), "n_I": r["n_I"], "n_clusters_I": len(set(lab.values())),
                                 "n_held": len(sw), "n_kept": sel.get("n_kept"), "n_added": sel.get("n_added"),
                                 "n_skipped_cluster": sel.get("n_skipped_cluster"), "n_cut_held_cluster": sel.get("n_cut_held_cluster"),
                                 "fallback_b0": r["fb"], "group_cap_used": r["cap_g"], "group_cap_flag": r["flag"],
                                 "max_cluster_w_equity": float(cg.max()), "n_clusters_held": int(len(cg))})
        for fc, lb in q["labels"].items():
            cl_rows.append({"t": t.date(), "FundCode": fc, "cluster": lb,
                            "held_GC": fc in q["streams"]["GC"]["S"].values(), "held_BASE": fc in q["streams"]["BASE"]["S"].values()})
        print(f"  [{qi+1}/{nq}] t={t.date()} I={q['n_I']} fit={q['n_fit']} clusters={len(set(q['labels'].values()))} "
              f"({time.time()-t0:.0f}s)", flush=True)

    # ---- plans & sims ----
    tf_cash = lambda t: wt.trend_filter_cash(acwi, t, 0.25)
    PLANS = {TRIAL_OF[s]: r67.old_style_plan(sleeves[s], quarters, calendar, tf_cash) for s in STREAMS}
    print("[2/6] simulate...", flush=True)
    sims = {}
    for tid, plan in PLANS.items():
        for ctag, c in COSTS:
            for rtag, rf in RFS:
                if tid.startswith("T-") and (ctag, rtag) != ("c50", "rf2"):
                    continue
                sims[(tid, ctag, rtag)] = r67.run_sim(plan, nav_by_fund, sim_months, c, rf, True)
    val = lambda tid, c="c50", r="rf2": sims[(tid, c, r)]["values"]

    # ---- sanity ----
    print("[3/6] sanity/regression (ก่อนรายงาน Sharpe)...", flush=True)
    sanity = {}
    # T-GC2 / T-SQ1
    for tid, nm in (("T-GC2", "T-GC2 (cap_g=1,max=8 -> BASE)"), ("T-SQ1", "T-SQ1 (w=1,0,0 ไม่ winsorize -> BASE)")):
        d = float(np.max(np.abs(val(tid).values - val("M004-TF-FX").values)))
        sh = simulate.sharpe(simulate.monthly_returns(val(tid)[val(tid).index <= PRIMARY_END]), RF)
        same_w = all(set(a["target"]) == set(b["target"]) and all(a["target"][k] == b["target"][k] for k in a["target"])
                     for a, b in zip(sims[(tid, "c50", "rf2")]["info"], sims[("M004-TF-FX", "c50", "rf2")]["info"]))
        sanity[f"{nm}: max|Δequity|={d:.2e}, น้ำหนักตรงทุกตัว={same_w}, Sharpe={sh:.10f}"] = (d == 0.0 and same_w)
    # ข้อมูล: (1,0,0)+winsorize
    nd = sum(1 for q in qres if q["streams"]["BASE"]["S"] != q["streams"]["SQ_T1W"]["S"])
    shw = simulate.sharpe(simulate.monthly_returns(val("T-SQ1W")[val("T-SQ1W").index <= PRIMARY_END]), RF)
    sanity[f"T-SQ1W (ข้อมูล ไม่ใช่เงื่อนไขผ่าน): (1,0,0) + winsorize ±3 -> ชุดกองต่างจาก BASE {nd}/{nq} ไตรมาส · Sharpe {shw:.4f} "
           f"(สาเหตุ: tie ที่ z=±3 ถูก tie-break ด้วย vol52)"] = True
    # T-GC1
    viol, nmax_cl, maxcl = 0, 0, 0.0
    for qi, q in enumerate(qres):
        r = q["streams"]["GC"]
        if r["fb"]:
            continue
        sw, lab = r["sleeve"], q["labels"]
        cg = sw.groupby(pd.Series({f: lab[f] for f in sw.index})).sum()
        cnt = pd.Series({f: lab[f] for f in sw.index}).value_counts()
        cap_used = r["cap_g"]
        maxcl = max(maxcl, float(cg.max()))
        nmax_cl = max(nmax_cl, int(cnt.max()))
        if cg.max() > cap_used + 1e-9 or cnt.max() > MAXPER or sw.max() > 0.25 + 1e-9 or abs(sw.sum() - 1) > 1e-9:
            viol += 1
    flags = [(str(quarters[i].date()), q["streams"]["GC"]["flag"]) for i, q in enumerate(qres) if q["streams"]["GC"]["flag"]]
    sanity[f"T-GC1 Σน้ำหนัก/cluster ≤ cap (0.35; relax ตามกฎ infeasible เท่านั้น) · ≤3 กอง/cluster · กอง ≤ 25%: ผิด {viol}/{nq} ไตรมาส · "
           f"max cluster w={maxcl:.4f} · max กอง/cluster={nmax_cl} · quarter ที่ infeasible/flag: {flags}"] = (viol == 0)
    # T-SQ2
    nm_re = re.compile(r"LOWVOL|LOW[ -]?VOL|MINVOL|MIN[ -]?VOL|ACWV|DEFENS|LOWBETA|MVOL", re.I)
    named, q_lv_ok, q_cnt = [], [], 0
    for qi, q in enumerate(qres):
        sub = [f for f in q["betaL"].index if nm_re.search(f)]
        if sub:
            named += sub
            q_cnt += 1
            q_lv_ok.append(float(q["betaL"][sub].median()) > 0)
        vol = q["i_sq"].set_index("FundCode")["vol52"]
    qu_ok = []
    for q in qres:
        d = q["i_sq"]
        lo = d[d["vol52"] <= d["vol52"].quantile(0.2)]["betaL"].median()
        hi = d[d["vol52"] >= d["vol52"].quantile(0.8)]["betaL"].median()
        qu_ok.append(lo > hi)
    sanity[f"T-SQ2 β_LowVol: กองชื่อ low-vol ใน I_t = {sorted(set(named))[:8]} (ไตรมาสที่พบ {q_cnt}; median β>0 ทุกไตรมาส={all(q_lv_ok) if q_lv_ok else 'n/a'}) · "
           f"ทดแทน: β_LowVol ควินไทล์ vol ต่ำสุด > สูงสุด {sum(qu_ok)}/{nq} ไตรมาส"] = (all(q_lv_ok) if q_lv_ok else True) and sum(qu_ok) >= 0.8 * nq
    # reproducible vs สคริปต์สำรวจ
    ex = pd.read_csv(os.path.join(SCRATCH, "modeler_explore_out", "selection_beta.csv"))
    mism, comp = 0.0, 0
    for qi, q in enumerate(qres):
        t = quarters[qi]
        d = ex[(ex["t"] == str(t.date()))]
        sr = q["i_sq"].set_index("FundCode")["SR12"]
        for f, b in (("Quality", q["betaQ"]), ("LowVol", q["betaL"])):
            row = d[d["factor"] == f]
            if len(row) == 0:
                continue
            rho = spearmanr(b.reindex(sr.index), sr, nan_policy="omit")[0]
            tix = 4 if f == "Quality" else 6
            mt = float(np.median([abs(q["fits"][fc]["t"][tix]) for fc in b.index]))
            mism = max(mism, abs(rho - float(row["spearman_vs_SR12"].iloc[0])), abs(mt - float(row["med_abs_t"].iloc[0])))
            comp += 1
    sanity[f"T-SQ2b reproducible กับสคริปต์สำรวจ (Spearman vs SR12 และ median|t| ของ β_Quality/β_LowVol, {comp} ค่า): max|Δ|={mism:.2e}"] = (mism < 1e-6) if comp else True
    n_nofit = sum(q["n_I"] - q["n_fit"] for q in qres)
    sanity[f"SQ: กองใน I_t ที่ fit ไม่ได้ (ถูกตัดออกจาก I_t ของ SQ) รวมทุกไตรมาส = {n_nofit}"] = True
    # canary
    cq = [0, 2, 4] if smoke else [0, 3, 6, 9, 12, nq - 1]
    can_ok, can_det = True, []
    for qi in cq:
        t = quarters[qi]
        rng = np.random.default_rng(1000 + qi)
        nav_n = nav.copy()
        m = nav_n["NAVDate"] > t
        nav_n.loc[m, "NAV"] = rng.lognormal(3.0, 1.0, int(m.sum()))
        arr_n = fs._prep_arrays(common.build_nav_by_fund(nav_n))
        fd = fac_daily.copy()
        fm = fd.index > t
        fd.loc[fm, :] = rng.lognormal(0.0, 0.5, (int(fm.sum()), fd.shape[1]))
        acwi_n = acwi.copy()
        acwi_n[acwi_n.index > t] = rng.lognormal(5.0, 0.5, int((acwi_n.index > t).sum()))
        qn = select_quarter(t, nav_n, arr_n, calendar, groups, fd, states_in[qi])
        q0 = qres[qi]
        ok = qn["labels"] == q0["labels"] and wt.trend_filter_cash(acwi_n, t, 0.25) == tf_cash(t)
        for s in STREAMS:
            a, b = q0["streams"][s], qn["streams"][s]
            ok &= (a["S"] == b["S"]) and a["sleeve"].equals(b["sleeve"]) and a["fb"] == b["fb"]
            if s in q0["scores"]:
                ok &= q0["scores"][s].equals(qn["scores"][s])
        ok &= q0["betaQ"].equals(qn["betaQ"]) and q0["betaL"].equals(qn["betaL"])
        can_ok &= bool(ok)
        can_det.append(f"{t.date()}:{'ok' if ok else 'DIFF'}(แก้ {int(m.sum())} แถว NAV)")
    sanity[f"CANARY แทน NAV/factor/ACWI หลัง t ด้วย noise -> cluster labels, β, score, S, น้ำหนัก, trend ตรง 100% ที่ {len(cq)} ไตรมาส: " + ", ".join(can_det)] = can_ok
    # regression M004-TF-FX
    ref = pd.read_csv(os.path.join(RES, "M006-M007_summary_metrics.csv"))
    ref = ref[(ref.trial == "M004-TF-FX") & (ref.cost == 0.005) & (ref.rf == 0.02)].iloc[0]
    mb = r67.per_metrics(val("M004-TF-FX"), RF)
    fl = r67.flow_stats(sims[("M004-TF-FX", "c50", "rf2")], years)
    if not smoke:
        eq_old = pd.read_csv(os.path.join(RES, "M006-M007_M004-TF-FX_equity_curve.csv"), index_col=0, parse_dates=True)["value"]
        dmax = float(np.max(np.abs(val("M004-TF-FX").reindex(eq_old.index).values - eq_old.values)))
        regs = [("sharpe", mb["sharpe"], ref["sharpe"]), ("cagr", mb["cagr"], ref["cagr"]), ("vol", mb["vol"], ref["vol"]),
                ("max_dd", mb["max_dd"], ref["max_dd"]), ("turn_sel_yr", fl["turn_sel_yr"], ref["turn_sel_yr"]),
                ("sharpe_2307_2512", mb["sharpe_2307_2512"], ref["sharpe_2307_2512"])]
        rd = max(abs(a - b) for _, a, b in regs)
        sanity[f"REGRESSION M004-TF-FX ผ่าน runner ใหม่ = Sharpe {mb['sharpe']:.10f} (ref {ref['sharpe']:.10f}) · "
               f"max|Δ| ของ 6 ตัวเลข {rd:.2e} · max|Δequity| vs csv เดิม {dmax:.2e}"] = (rd < 1e-12 and dmax < 1e-9 and round(mb['sharpe'], 4) == 0.7205)
        wold = pd.read_csv(os.path.join(RES, "M004-TF-FX_weights.csv"))
        wnew = pd.DataFrame([{"t": en["t"].date().isoformat(), "FundCode": f, "weight": w} for en in sims[("M004-TF-FX", "c50", "rf2")]["info"]
                             for f, w in en["target"].items() if w > 1e-12])
        mm = wold.assign(t=wold["t"].astype(str)).merge(wnew, on=["t", "FundCode"], how="outer", suffixes=("_o", "_n"))
        wd = float((mm["weight_o"].fillna(-1) - mm["weight_n"].fillna(-1)).abs().max())
        sanity[f"REGRESSION น้ำหนักรายไตรมาส M004-TF-FX = M004-TF-FX_weights.csv เดิม: max|Δw|={wd:.2e}"] = wd < 1e-12
    for k, v in sanity.items():
        print(f"  [{'PASS' if v else 'FAIL'}] {k}", flush=True)
    if not all(sanity.values()):
        print("SANITY FAIL — หยุดก่อนรายงาน Sharpe", flush=True)
        if not smoke:
            raise SystemExit(1)

    # ---- metrics ----
    print("[4/6] metrics...", flush=True)
    TR = ["M004-TF-FX", "M008-GC", "M008-SQ"]
    rows, prim, eqs = [], {}, {}
    for tid in TR:
        for ctag, c in COSTS:
            for rtag, rf in RFS:
                v = val(tid, ctag, rtag)
                m = r67.per_metrics(v, rf)
                f = r67.flow_stats(sims[(tid, ctag, rtag)], years)
                funds = {k for en in sims[(tid, "c50", "rf2")]["info"] for k, w in en["target"].items() if k != "__CASH__" and w > 1e-12}
                v22 = v[v.index <= "2022-12-31"]
                rows.append({"trial": tid, "cost": c, "rf": rf, "n_trials": NTR[tid], **m, **f, "n_distinct_funds": len(funds),
                             "ret_2022": float(v22.iloc[-1] / 100.0 - 1.0)})
        eqs[tid] = val(tid)
        r = simulate.monthly_returns(eqs[tid])
        prim[tid] = r[r.index <= PRIMARY_END]
    summ = pd.DataFrame(rows)
    g = lambda tid, c=0.005, rf=0.02: summ[(summ.trial == tid) & (summ.cost == c) & (summ.rf == rf)].iloc[0]
    ci = {t: simulate.block_bootstrap_ci(prim[t], RF) for t in TR}
    dsr_own = {t: simulate.deflated_sharpe(prim[t], RF, NTR[t]) for t in TR}
    dsr20 = {t: simulate.deflated_sharpe(prim[t], RF, 20) for t in TR}
    psr = {t: simulate.deflated_sharpe(prim[t], RF, 1) for t in TR}
    dci = {t: simulate.paired_bootstrap_diff_ci(prim[t], prim["M004-TF-FX"], RF) for t in ("M008-GC", "M008-SQ")}
    dbq = {t: drop_best_q(prim[t], RF) for t in TR}

    # concentration
    conc = []
    for qi, q in enumerate(qres):
        t = quarters[qi]
        cash = tf_cash(t)
        rec = {"t": t.date(), "cash": cash}
        for s in ("BASE", "GC", "SQ"):
            r = q["streams"][s]
            sw = r["sleeve"]
            lab = q["labels"]
            cg = sw.groupby(pd.Series({f: lab.get(f, -1) for f in sw.index})).sum()
            tm, tn = theme_shares(sw)
            tm3, tn3 = theme_shares(sw, THEMES3)
            rec.update({f"{s}_maxcl": float(cg.max()), f"{s}_theme": tm, f"{s}_theme_name": tn, f"{s}_theme3": tm3,
                        f"{s}_theme3_name": tn3, f"{s}_theme_port": tm * (1 - cash), f"{s}_skip": r["sel"].get("n_skipped_cluster", 0),
                        f"{s}_n": len(sw)})
        conc.append(rec)
    conc = pd.DataFrame(conc)

    if smoke:
        for tid in TR:
            r = g(tid)
            print(f"  {tid}: sharpe={r['sharpe']:.3f} n={int(r['n_months'])} cash={r['avg_cash']:.3f}")
        print(conc.round(3).to_string())
        print("SMOKE OK", flush=True)
        return

    # ---- outputs ----
    print("[5/6] write...", flush=True)
    summ.to_csv(os.path.join(RES, "M008_summary_metrics.csv"), index=False)
    for s, tid in (("GC", "M008-GC"), ("SQ", "M008-SQ")):
        pd.DataFrame({"value": eqs[tid]}).to_csv(os.path.join(RES, f"M008_{tid}_equity_curve.csv"))
        wr = [{"trial": tid, "offset": "Q", "t": en["t"].date(), "e": en["e"].date(), "kind": en["mode"], "FundCode": f, "weight": w}
              for en in sims[(tid, "c50", "rf2")]["info"] for f, w in en["target"].items() if w > 1e-12]
        pd.DataFrame(wr).to_csv(os.path.join(RES, f"{tid}_weights.csv"), index=False)
    pd.DataFrame(cl_rows).to_csv(os.path.join(RES, "M008-GC_cluster_membership.csv"), index=False)
    pd.DataFrame(log_rows).to_csv(os.path.join(RES, "M008_selection_log.csv"), index=False)
    conc.to_csv(os.path.join(RES, "M008_concentration.csv"), index=False)
    write_trials_and_all(summ, ci, dsr_own, dsr20, dci, g)
    write_report(summ, g, ci, dsr_own, dsr20, psr, dci, dbq, conc, sanity, fb_count, flags, prim, TR)
    print(f"DONE in {time.time()-t0:.0f}s", flush=True)


# ---------------- pre-registered verdicts ----------------

def verdicts(g, conc, dci, dbq=None):
    b, gc, sq = g("M004-TF-FX"), g("M008-GC"), g("M008-SQ")
    out = {}
    thm = conc["GC_theme"].max()
    thm3 = conc["GC_theme3"].max()
    c1, c2, c3 = thm <= 0.40 + 1e-12, gc["sharpe"] >= 0.67, gc["max_dd"] >= b["max_dd"] - 0.01 - 1e-12
    out["GC"] = {"c1": (c1, f"max name-theme (ทุกธีมที่ตั้งชื่อ, normalise ส่วนหุ้น) = {thm:.3f} (infra/india/tech เท่านั้น {thm3:.3f}); base {conc['BASE_theme'].max():.3f}"),
                 "c2": (c2, f"Sharpe {gc['sharpe']:.4f} vs เกณฑ์ 0.67 (base−0.05 = {b['sharpe']-0.05:.4f})"),
                 "c3": (c3, f"maxDD {gc['max_dd']:.4f} vs base {b['max_dd']:.4f} (ยอมแย่กว่าได้ ≤ 1 pt)"),
                 "pass": c1 and c2 and c3, "dlo": dci["M008-GC"][0]}
    s1a = sq["ret_2022"] >= -0.044
    s1b = sq["maxdd_2022"] >= -0.104 + 0.02 - 1e-12
    s2 = sq["sharpe_2307_2512"] >= 1.183 - 0.15
    out["SQ"] = {"c1a": (s1a, f"return เม.ย.–ธ.ค. 2022 {sq['ret_2022']:.4f} vs เกณฑ์ ≥ −0.044 (base {b['ret_2022']:.4f})"),
                 "c1b": (s1b, f"maxDD 2022 {sq['maxdd_2022']:.4f} vs เกณฑ์ ≥ −0.084 (base {b['maxdd_2022']:.4f})"),
                 "c2": (s2, f"Sharpe 2023-07..2025-12 {sq['sharpe_2307_2512']:.4f} vs เกณฑ์ ≥ 1.033 (base {b['sharpe_2307_2512']:.4f})"),
                 "pass": s1a and s1b and s2, "dlo": dci["M008-SQ"][0]}
    return out


def write_trials_and_all(summ, ci, dsr_own, dsr20, dci, g):
    import shutil
    trials = os.path.join(TEAM_DIR, "trials.csv")
    if "M008-GC," in open(trials, encoding="utf-8").read():     # กันเขียนซ้ำเมื่อรันใหม่
        print("  trials.csv/ALL_RESULTS.csv มีแถว M008 แล้ว — ไม่ append ซ้ำ", flush=True)
        return
    bak = os.path.join(SCRATCH, f"validator_trials_backup_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.csv")
    shutil.copy(trials, bak)
    now = pd.Timestamp.now().isoformat()
    meta = {"M008-GC": ("M008-GC: corr-cluster (52w avg-linkage cut 0.25) <=3 funds/cluster + cluster cap 35% of equity; on M004-TF-FX", 19),
            "M008-SQ": ("M008-SQ: score=0.5z(SR12)+0.25z(betaQuality)+0.25z(betaLowVol) 52w weekly OLS; on M004-TF-FX", 20)}
    lines = []
    for tid, (desc, n) in meta.items():
        r = g(tid)
        lo, hi = ci[tid]
        d = dci[tid]
        note = (f"CI95 ({lo:.3f};{hi:.3f}); paired dSharpe vs M004-TF-FX {d[2]:.3f} CI ({d[0]:.3f};{d[1]:.3f}); "
                f"DSR@{n}={dsr_own[tid]:.4f} DSR@20={dsr20[tid]:.4f}; new measurement n_months={int(r['n_months'])}; family map F/U fix")
        params = f"{desc};N=8;K=16;SR12 base;ERC;cap25%;trend cash25%;rf=2%;cost=0.5%/side;primary=2022-03..2025-12"
        vals = [tid, now, "M008_style_macro.md", params, "2022-03-31", "2025-12-31", "assumed constant 2%/yr", "0.5%/side constant",
                round(r["sharpe"], 4), round(r["cagr"], 4), round(r["vol"], 4), round(r["max_dd"], 4),
                round(r["turn_sel_yr"] + r["turn_trend_yr"], 4), n, round(dsr_own[tid], 4), "ok", note]
        lines.append(",".join(str(v).replace(",", ";") for v in vals))
    with open(trials, "a", encoding="utf-8") as f:
        for ln in lines:
            f.write(ln + "\n")
    allcsv = os.path.join(RES, "ALL_RESULTS.csv")
    ideas = {"M008-GC": "cluster cap 35% + <=3 funds/cluster on M004-TF-FX", "M008-SQ": "SR12 + Quality/LowVol beta tilt on M004-TF-FX"}
    with open(allcsv, "a", encoding="utf-8") as f:
        for tid in ("M008-GC", "M008-SQ"):
            vals = ["M008", tid, ideas[tid], "new", "no", f"{g(tid,0.0)['sharpe']:.3f}", f"{g(tid)['sharpe']:.3f}", f"{g(tid,0.01)['sharpe']:.3f}",
                    f"{g(tid)['cagr']:.3f}", f"{g(tid)['vol']:.3f}", f"{g(tid)['max_dd']:.3f}", f"{dsr20[tid]:.3f}"]
            f.write(",".join(vals) + "\n")


AMBIG = [
    "z-score ใน I_t ใช้ std ddof=1 และ winsorize ±3 หลัง z (spec ไม่ระบุ ddof); SQ I_t = กองใน I_t(F/U fix) ที่ fit OLS ได้ (≥ 40 obs ครบทุก factor), z คิดข้ามกองที่ fit ได้เท่านั้น",
    "GC: R ใช้ทุกกองใน I_t (ตาม spec) ไม่ใช่เฉพาะกองที่ fit style/macro ได้ → label อาจต่างจากสคริปต์สำรวจเล็กน้อย (สคริปต์สำรวจ cluster เฉพาะกองที่ fit)",
    "GC: ‘cluster ของกองที่ถืออยู่เกิน 3 → ตัดตัว rank แย่สุด’ ทำก่อนเติม · กองที่ถูกตัดถูกข้ามตอนเติมเพราะ cluster เต็ม (นับใน n_skipped_cluster) · ลำดับ insertion ของ S รักษาเหมือน wt.hysteresis_select เพื่อให้ T-GC2 ตรงทุกหลัก",
    "GC group cap: cap 35% คิดเทียบ sleeve ส่วนหุ้น (Σ=1) ก่อนคูณ (1−เงินสด trend) · water-filling แจกส่วนเกินให้กองในกลุ่มที่ยังไม่เต็มตามสัดส่วนน้ำหนัก จำกัดไม่ให้เกิน 25%/กอง และ 35%/กลุ่ม (แจกวนจนหมดหรือไม่มีที่ว่าง) · "
    "ถ้า infeasible (Σ_g min(cap_g, 0.25·n_g) < 1 — กว้างกว่าคำว่า '< 3 cluster' ใน spec เพราะ ≤3 กอง/กลุ่ม ทำให้บางชุดกลุ่มรวมกันไม่ถึง 100%) → cap=1/จำนวนกลุ่ม; ถ้ายังไม่ได้ → ไม่ใช้ cap กลุ่มและติด flag",
    "ถ้า selection fallback เป็น B0 (< 4 กอง) ใช้ sleeve B0 เท่ากัน ไม่ใส่ group cap (เหมือน M004-TF-FX)",
    "concentration: ‘max name-theme’ ใช้ regex ชื่อกองจากสคริปต์สำรวจ (9 ธีม ไม่รวม other) normalise เป็นสัดส่วนของส่วนหุ้น (sleeve) — เกณฑ์ ≤ 40% ใช้ค่านี้ (เข้มกว่า % ของพอร์ตรวมเงินสด) และ max ข้ามทุกธีม ไม่ใช่เฉพาะ infra/india/tech (รายงานทั้งสองแบบ)",
    "max cluster weight ของทุก trial (รวม M004-TF-FX/SQ) วัดด้วย label ของ I_t(F/U fix) ชุดเดียวกัน ณ t (label ไม่ขึ้นกับ stream)",
    "เกณฑ์ GC (2) ‘Sharpe ≥ 0.67’ ใช้ตัวเลข 0.67 ตามที่เขียน (base−0.05 = 0.6705) · (3) maxDD ไม่แย่กว่า base เกิน 1 pt = max_dd ≥ base − 0.01 · เกณฑ์ SQ ใช้ตัวเลขใน spec ตรงๆ (−4.4%, maxDD 2022 ≥ −8.4%, Sharpe 2023-07..2025-12 ≥ 1.033)",
    "‘return เม.ย.–ธ.ค. 2022’ = มูลค่า 2022-12-31 ÷ 100 − 1 (เส้นเริ่ม 100 ที่ e แรก 2022-04-04, หักต้นทุนซื้อเข้าแล้ว) · maxDD 2022 = maxDD ของเส้นถึง 2022-12-31 (ตรงกับ r67)",
    "DSR ใช้ simulate.deflated_sharpe (per-period รายเดือน, n_eff แบบ Lo) ที่ n ของตัวเอง (GC=19, SQ=20) และ n=20; PSR = n_trials 1; M004-TF-FX แสดงที่ n=9 (เดิม) และ n=20 เพื่อเทียบ · คอลัมน์ dsr_n18 ใน ALL_RESULTS.csv ของแถว M008 = DSR@20",
    "T-SQ1 (w=1,0,0): ต่างจาก BASE เฉพาะ (i) I_t ถูกตัดเป็นกองที่ fit ได้ และ (ii) winsorize ±3 ของ z(SR12) ที่ทำให้เกิด tie ปลายบน (tie-break ด้วย vol52) — ผ่านเมื่อทั้งสองไม่มีผล (ดูผลทดสอบ)",
    "T-SQ2: กองชื่อ low-vol ใน I_t หาด้วย regex ชื่อกอง (LOWVOL/MINVOL/ACWV/DEFENS…) · ถ้าไม่พบ ใช้ควินไทล์ vol52 ต่ำสุด vs สูงสุดแทน (≥ 80% ของไตรมาส β_LowVol median ต่ำสุดควินไทล์ > สูงสุดควินไทล์)",
    "canary: noise = lognormal แทนค่า NAV/factor/ACWI ทุกแถวหลัง t (ปฏิทินดัชนีคงเดิม) · ทำ 6 ไตรมาสกระจาย (0,3,6,9,12,สุดท้าย) ใช้ state held จริง ณ ต้นไตรมาสนั้น",
    "cost bp/ปี = (cost คัดกอง + cost trend) จาก flow_stats (รวมต้นทุนซื้อเข้าครั้งแรก) · turnover/ปี ไม่รวมซื้อเข้าครั้งแรก (เหมือน M006-M007) · Sharpe เมื่อตัดไตรมาสดีสุด = ตัด return รายเดือนของไตรมาสปฏิทินที่ทบต้นสูงสุดแล้วคำนวณ Sharpe ใหม่ (วิธีเดียวกับ reviewer_m006.py)",
    "ไม่ได้รัน SQ/GC แบบ OLD measurement หรือ cost sensitivity ของ tests (T-*) · ช่วง 2026 ไม่ใช้ (ไม่มี holdout)",
]


def write_report(summ, g, ci, dsr_own, dsr20, psr, dci, dbq, conc, sanity, fb_count, flags, prim, TR):
    V = verdicts(g, conc, dci)
    b = g("M004-TF-FX")
    L = ["# M008 — style/macro บน M004-TF-FX: GC (n=19) และ SQ (n=20) — ผลวัด (validator)\n",
         f"รันเมื่อ {pd.Timestamp.now().isoformat()} · primary เม.ย. 2022 → 2025-12-31 (45 เดือน, วัดใหม่นับเดือนแรก) · cost 0.5%/ข้าง (+0/1%) · rf 2% · family map F/U fix · "
         "base = M004-TF-FX · ไม่มี holdout 2026 · ไม่ปรับพารามิเตอร์ใดๆ (ตายตัวตาม spec)\n", "## 1. Sanity / regression (ก่อนรายงาน Sharpe)\n"]
    for k, v in sanity.items():
        L.append(f"- **{'PASS' if v else 'FAIL'}** {k}")
    L.append(f"- fallback→B0 (จำนวนไตรมาส): {dict(fb_count)}\n")
    L.append("## 2. ตารางหลัก (primary, cost 0.5%/ข้าง, rf 2%)\n")
    L.append("| trial | Sharpe (c0 / c0.5 / c1) | CAGR | vol | maxDD | return เม.ย.–ธ.ค.22 | maxDD ถึง ธ.ค.22 | Sharpe 2023-07..2025-12 | turnover/ปี | cost bp/ปี | เงินสดเฉลี่ย | #กอง | CI95% Sharpe | DSR@own n | DSR@20 | PSR | ตัดไตรมาสดีสุด |")
    L.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for tid in TR:
        r = g(tid)
        lo, hi = ci[tid]
        L.append(f"| {tid} | {r['sharpe']:.4f} ({g(tid,0.0)['sharpe']:.3f} / {r['sharpe']:.3f} / {g(tid,0.01)['sharpe']:.3f}) | {r['cagr']:.4f} | {r['vol']:.4f} | "
                 f"{r['max_dd']:.4f} | {r['ret_2022']:.4f} | {r['maxdd_2022']:.4f} | {r['sharpe_2307_2512']:.3f} | "
                 f"{r['turn_sel_yr']+r['turn_trend_yr']:.2f} | {r['cost_sel_bp']+r['cost_trend_bp']:.0f} | {r['avg_cash']:.3f} | {int(r['n_distinct_funds'])} | "
                 f"[{lo:.2f},{hi:.2f}] | {dsr_own[tid]:.3f} (n={int(r['n_trials'])}) | {dsr20[tid]:.3f} | {psr[tid]:.3f} | {dbq[tid][0]:.3f} (ตัด {dbq[tid][1]}) |")
    L.append("\n## 3. paired ΔSharpe vs M004-TF-FX (block bootstrap block=3, 2000 รอบ)\n")
    L.append("| trial | ΔSharpe | CI95% | คร่อม 0? |\n|---|---|---|---|")
    for t, (lo, hi, pt) in dci.items():
        L.append(f"| {t} | {pt:.4f} | [{lo:.3f},{hi:.3f}] | {'ไม่คร่อม' if (lo > 0 or hi < 0) else 'คร่อม'} |")
    L.append("\n## 4. เกณฑ์ pre-registered (spec §4) — verdict\n")
    for k, nm in (("GC", "M008-GC"), ("SQ", "M008-SQ")):
        v = V[k]
        L.append(f"**{nm}: {'ผ่านเกณฑ์' if v['pass'] else 'ไม่ผ่านเกณฑ์'}** · paired Δ CI ต่ำสุด {v['dlo']:.3f} "
                 f"({'≥ −0.3 ok' if v['dlo'] >= -0.3 else '< −0.3'}) → สลับเป็น headline: "
                 f"{'ได้ (ต้องผ่านรีวิว)' if (v['pass'] and v['dlo'] >= -0.3) else 'ไม่ได้ (ตาม spec)'}")
        for c, val_ in v.items():
            if c in ("pass", "dlo"):
                continue
            ok, txt = val_
            L.append(f"- {c}: **{'PASS' if ok else 'FAIL'}** — {txt}")
        L.append("")
    L.append("## 5. ตาราง concentration รายไตรมาส (น้ำหนัก normalise ในส่วนหุ้น; cluster = corr 52w avg-linkage ตัด 0.25 ที่ I_t)\n")
    L.append("| t | cash | BASE maxCluster | BASE theme (ชื่อ) | GC maxCluster | GC theme (ชื่อ) | GC skip | GC #กอง | SQ maxCluster | SQ theme (ชื่อ) | BASE theme3 | GC theme3 | SQ theme3 |")
    L.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for _, c in conc.iterrows():
        L.append(f"| {c['t']} | {c['cash']:.2f} | {c['BASE_maxcl']:.3f} | {c['BASE_theme']:.3f} ({c['BASE_theme_name']}) | {c['GC_maxcl']:.3f} | "
                 f"{c['GC_theme']:.3f} ({c['GC_theme_name']}) | {int(c['GC_skip'])} | {int(c['GC_n'])} | {c['SQ_maxcl']:.3f} | {c['SQ_theme']:.3f} ({c['SQ_theme_name']}) | "
                 f"{c['BASE_theme3']:.3f} | {c['GC_theme3']:.3f} | {c['SQ_theme3']:.3f} |")
    L.append(f"\n- เฉลี่ย: max cluster BASE {conc['BASE_maxcl'].mean():.3f} → GC {conc['GC_maxcl'].mean():.3f} (SQ {conc['SQ_maxcl'].mean():.3f}) · "
             f"max theme BASE {conc['BASE_theme'].mean():.3f} → GC {conc['GC_theme'].mean():.3f} (SQ {conc['SQ_theme'].mean():.3f}) · "
             f"ค่าสูงสุดข้ามไตรมาส: theme BASE {conc['BASE_theme'].max():.3f} / GC {conc['GC_theme'].max():.3f} / SQ {conc['SQ_theme'].max():.3f}; "
             f"cluster BASE {conc['BASE_maxcl'].max():.3f} / GC {conc['GC_maxcl'].max():.3f}")
    L.append(f"- GC ไตรมาสที่ group-cap flag (infeasible/relax): {flags}")
    L.append("- ไฟล์: M008-GC_weights.csv, M008-SQ_weights.csv, M008-GC_cluster_membership.csv, M008_selection_log.csv, M008_concentration.csv, M008_<trial>_equity_curve.csv")
    L.append("\n## 6. ความไว ต้นทุน/rf (Sharpe)\n")
    L.append("| trial | c0 rf2 | c0.5 rf2 | c1 rf2 | c0.5 rf0 |\n|---|---|---|---|---|")
    for tid in TR:
        L.append(f"| {tid} | {g(tid,0.0)['sharpe']:.3f} | {g(tid)['sharpe']:.3f} | {g(tid,0.01)['sharpe']:.3f} | {g(tid,0.005,0.0)['sharpe']:.3f} |")
    L.append("\n## 7. สิ่งที่ spec ไม่ชัดและตีความเอง\n")
    for t in AMBIG:
        L.append(f"- {t}")
    with open(os.path.join(RES, "M008_results.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(L))


if __name__ == "__main__":
    run(smoke=("smoke" in sys.argv))
