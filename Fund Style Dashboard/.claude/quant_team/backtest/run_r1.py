"""run_r1.py — debate รอบ 1: M023-TR3 · M024-FEE0 · M025-HOLD18 · M026-DEFX · M027-MH · M028-STACK (spec: debate/R1_modeler.md §3)
base = M019-LC3-GCGOLD (run_m019.py) · ทุกแบบรายงานเดี่ยว + TR3 · regression ไม่ผ่าน = หยุดแบบนั้น ไม่บันทึก
รัน: PYTHONPATH=. ./.venv/bin/python .claude/quant_team/backtest/run_r1.py
"""
from __future__ import annotations

import csv
import io
import os
import shutil
import sys
import time
from dataclasses import dataclass, replace

THIS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, THIS)

import numpy as np
import pandas as pd

import common
import fees
import fund_signals as fs
import remeasure_real_rf as rr
import robust_offsets as ro
import run_m010 as r10
import run_m011 as r11
import run_m012 as r12
import run_m015 as r15
import run_m018 as m18
import run_m019 as m19
import weighting as wt
import fulluniv_run as fu

TEAM = os.path.dirname(THIS)
RES = common.RESULTS_DIR
TRIALS = os.path.join(TEAM, "trials.csv")
DEBATE = os.path.join(TEAM, "debate")
O_ALL_PARQUET = os.path.join(common.CACHE_DIR, "r1_navO_all.parquet")
N, POOL, CAP, NMIN = 3, 9, 0.40, 2
EPS, DELTA, HOLD_WIDE, RHO_ACWI = 0.05, 0.10, 18, 0.5
WIN_A, WIN_B, WIN_MID = pd.Timestamp("2022-06-30"), rr.PE, pd.Timestamp("2023-12-31")


@dataclass(frozen=True)
class Cfg:
    fee0: bool = False
    hold: int = POOL
    defx: bool = False
    mh: bool = False


# ---------------- การคัดกอง (= run_m019.select_lc + สวิตช์ FEE0 / HOLD) ----------------
def select_gen(ctx, held, prev_fb, qual, cfg: Cfg, fee):
    t = ctx["t"]
    i_t = ctx["i_t"]
    H_map = {} if prev_fb else held
    fam_ok = set(qual.index[qual["pass_q1"] & qual["pass_q2"]])
    it = i_t[i_t["family"].isin(fam_ok)]
    reps = wt.family_representatives(it, "SR12", held_funds=set(held.values()))
    ranks = wt.rank_families(reps)
    if cfg.fee0:                                                   # class ที่ FF ต่ำสุดในแถบ SR12′ ≥ rep − ε (family ที่ไม่ได้ถือ)
        for fam, rep in list(reps.items()):
            if fam in held:
                continue
            g = it[(it["family"] == fam) & (it["SR12"] >= rep["signal"] - EPS)]
            best = sorted(g.itertuples(), key=lambda r: (fee.rate(r.FundCode, "FF", t), -r.SR12, r.FundCode))[0].FundCode
            reps[fam] = {**rep, "FundCode": best}
    pool = [f for f in sorted(reps, key=lambda f: ranks[f]) if ranks[f] <= POOL]
    S = {fam: fc for fam, fc in H_map.items() if fam in reps and ranks[fam] <= cfg.hold and reps[fam]["FundCode"] == fc}
    if not S and pool:
        S[pool[0]] = reps[pool[0]]["FundCode"]
    while len(S) < N:
        cands = [f for f in pool if f not in S]
        if not cands:
            break
        sc = {}
        for f in cands:
            rh = [r10.rho_adj_pair(ctx["wk"][reps[f]["FundCode"]], ctx["wk"][fc]) for fc in S.values()]
            sc[f] = max(1.0 if np.isnan(x) else x for x in rh)
        if cfg.fee0:
            s_star = min(sc.values())
            C = [f for f in cands if sc[f] <= s_star + DELTA]
            best = min(C, key=lambda f: (fee.rate(reps[f]["FundCode"], "FF", t), sc[f], ranks[f]))
        else:
            best = min(cands, key=lambda f: (sc[f], ranks[f]))
        S[best] = reps[best]["FundCode"]
    return {"S": S, "fallback": len(S) < NMIN, "ranks": ranks, "reps": reps}


def stream_gen(ctxs, quals, cfg, fee):
    held, prev_fb = {}, False
    sleeves, recs = {}, []
    for ctx in ctxs:
        qi = ctx["qi"]
        rec = select_gen(ctx, held, prev_fb, quals[qi], cfg, fee)
        recs.append(rec)
        if rec["fallback"]:
            held, prev_fb = {}, True
            sleeves[qi] = ctx["b0_w"]
            continue
        held, prev_fb = dict(rec["S"]), False
        funds = list(rec["S"].values())
        w, _ = wt.risk_parity_weights(funds, ctx["wk"], ctx["vol_map"], method="erc")
        sleeves[qi] = wt.apply_cap(w, CAP)
    return sleeves, recs


# ---------------- MH: คะแนน 3/6/12 เดือน annualize ----------------
def mh_ctxs(E, arrays, weights=(1, 1, 1)):
    out = []
    for ctx in E["ctx_h"]:
        t = ctx["t"]
        ms = fs.month_end_points(E["calendar"], t, 13)
        it = ctx["i_t"].copy()
        comp = {12: it["SR12"].to_numpy(float)}
        for L in (3, 6):
            a, b = np.datetime64(ms[-1 - L].date()), np.datetime64(ms[-1].date())
            assert ms[-1] <= t and ms[-1 - L] < t
            h = r11.hurdle(E["rate"], ms[-1 - L], ms[-1])
            R = np.array([(fs._asof(*arrays[f], b) / fs._asof(*arrays[f], a) - 1.0) if f in arrays else np.nan for f in it["FundCode"]])
            comp[L] = (R - h) * (12.0 / L) / it["vol52"].to_numpy(float)
        stack = np.vstack([comp[3] * weights[0], comp[6] * weights[1], comp[12] * weights[2]])
        valid = np.vstack([~np.isnan(comp[3]), ~np.isnan(comp[6]), ~np.isnan(comp[12])]) & (np.array(weights)[:, None] > 0)
        it["SR12"] = np.where(valid, np.nan_to_num(stack), 0).sum(0) / np.maximum((valid * np.array(weights)[:, None]).sum(0), 1e-12)
        c = dict(ctx)
        c["i_t"] = it
        out.append(c)
    return out


# ---------------- DEFX: กอง O ทั้งหมด + F · excess return 12 เดือนสูงสุด · ρ_adj กับ ACWI ≤ 0.5 ----------------
class OAll(m18.GData):
    def __init__(self, profile, E, f_codes):
        o = profile[profile["Fund Policy"].str.strip() == "O"]
        codes = set(o.index)
        if os.path.exists(O_ALL_PARQUET):
            nav = pd.read_parquet(O_ALL_PARQUET)
            nav["NAVDate"] = pd.to_datetime(nav["NAVDate"])
        else:
            gp = m18.GOLD_PARQUET
            m18.GOLD_PARQUET = O_ALL_PARQUET                           # ใช้ตัวโหลดเดิม แต่เขียน cache ไฟล์ใหม่ (ไม่ทับของ M018)
            try:
                nav = m18.build_nav_gold(codes, force=True)
            finally:
                m18.GOLD_PARQUET = gp
        self.profile = profile
        self.nav = nav
        self.codes = sorted(nav["FundCode"].unique())
        self.nav_by_fund = {fc: g.sort_values("NAVDate").set_index("NAVDate")["NAV"] for fc, g in nav.groupby("FundCode")}
        ok = o[o["Tax Type"].isna() & (o["buy period flag"] == "N") & (o["Project Retail Type"] == "R")]
        self.snap = set(ok[~ok["Fund Name EN"].fillna("").str.contains("Not for Retail|NOT FOR RETAIL|TEST", regex=True)].index)
        self.groups = {fc: profile.loc[fc, "Fund Class"] for fc in self.codes if isinstance(profile.loc[fc, "Fund Class"], str)}
        self.arrays = fs._prep_arrays(self.nav_by_fund)
        self.calendar = E["calendar"]
        self.Q = r12.Quality(self.nav, self.groups)
        self.risk, self.fif, self.amc = profile["Fund Risk Level"], profile["FIF Flag"], profile["AMC_CODE"]
        assert not (set(self.codes) & set(E["nav_by_fund"])) and not (set(self.codes) & set(f_codes))


def defx_sels(OD, FD, E, acwi_arrays, mode="defx"):
    """mode 'defx' = spec · 'gold' = regression (กองทอง + ไม่กรอง ρ + AUM สูงสุด → ต้องเท่า gold_sels)."""
    out = {}
    for qi, t in enumerate(E["q15"]):
        h = E["h_by_q"][qi]
        rows = []
        srcs = [(OD, "O")] if mode == "gold" else [(OD, "O"), (FD, "F")]
        for D, pol in srcs:
            it, qual, _ = D.it_at(t)
            if len(it) == 0:
                continue
            if mode == "gold":
                it = it[it["FundCode"].isin(m18.gold_snapshot(D.profile) & set(it["FundCode"]))]
            ok = set(qual.index[qual["pass_q1"] & qual["pass_q2"]])
            it = it[it["family"].isin(ok)].copy()
            if len(it) == 0:
                continue
            it["SR12p"] = (it["R12_1"] - h) / it["vol52"]
            it["aum_fam"] = it["family"].map(qual["aum_fam"])
            it["ex"] = it["R12_1"] - h
            it["pol"] = pol
            reps = it.sort_values(["SR12p", "FundCode"], ascending=[False, True]).groupby("family", sort=False).head(1)
            if mode == "defx":
                q = fs.QuarterContext(D.arrays, E["calendar"], t)
                qa = fs.QuarterContext(acwi_arrays, E["calendar"], t)
                aw = qa.weekly_return_series("ACWI")
                rho = [r10.rho_adj_pair(q.weekly_return_series(f), aw) for f in reps["FundCode"]]
                reps = reps.assign(rho_acwi=rho)
                reps = reps[reps["rho_acwi"].notna() & (reps["rho_acwi"] <= RHO_ACWI)]
            rows.append(reps)
        tab = pd.concat(rows) if rows else pd.DataFrame()
        if len(tab) == 0:
            out[qi] = ({}, {"empty": True}, tab)
            continue
        if mode == "gold":
            c = tab.sort_values(["aum_fam", "FundCode"], ascending=[False, True]).head(1)
        else:
            c = tab.sort_values(["ex", "aum_fam", "FundCode"], ascending=[False, False, True]).head(1)
            if float(c["ex"].iloc[0]) <= 0:
                out[qi] = ({}, {"empty": True}, tab)
                continue
        out[qi] = ({c.iloc[0]["FundCode"]: 1.0}, {"empty": False}, c)
    return out


# ---------------- TR3 ----------------
def tr3_plans(plans, s=0):
    """ทั้ง 3 ก้อนเริ่มด้วย plans[s][0] แล้วก้อน j เดิน stream (s + j) mod 3."""
    p0 = plans[s][0]
    return [[p0] + [p for p in plans[(s + j) % 3] if p["t"] > p0["t"]] for j in range(3)]


def fund_counts(tr):
    """จำนวนกองหุ้น (ไม่นับขากัน F/O) distinct ที่ถือพร้อมกันทั้ง 3 ก้อน ณ แต่ละวันตัดสินใจ."""
    ts = sorted({p["t"] for pl in tr for p in pl})
    n = []
    for d in ts:
        cur = set()
        for pl in tr:
            last = [p for p in pl if p["t"] <= d][-1]
            cur |= {f for f, w in last["weights"].items() if w > 0 and f in EQ_CODES}
        n.append(len(cur))
    return {"n_eq_max": max(n), "n_eq_mean": float(np.mean(n))}


EQ_CODES: set = set()


def win(values, real, a=WIN_A, b=WIN_B):
    v = values[(values.index >= a) & (values.index <= b)]
    r = v.pct_change().dropna()
    rfm = real.rf_monthly(v.index)
    return rr.sharpe_s(r, rfm.reindex(r.index)) if len(r) >= 3 else np.nan


def main():
    t0 = time.time()
    holder, envs = {}, {}
    for k in (0, 1, 2):
        envs[k] = fu.build_env_and_plans(k, holder)
    E, P, X = envs[0]
    FD = holder["FD"]
    profile = r15.load_profile()
    f_codes = sorted(FD.profile.index[FD.profile["Fund Policy"] == "F"])
    GD = m18.GData(profile, E, f_codes)
    OD = OAll(profile, E, f_codes)
    real = E["real"]
    EQ_CODES.update(E["nav_by_fund"])
    fee_gold = m18.Fee3(E["fd_sim"], fees.FeeData(f_codes), f_codes, fees.FeeData(GD.codes), GD.codes)
    fee_all = m18.Fee3(E["fd_sim"], fees.FeeData(f_codes), f_codes, fees.FeeData(OD.codes), OD.codes)
    nav_all = {**E["nav_by_fund"], **FD.nav_by_fund, **OD.nav_by_fund}
    fset = set(FD.codes) | set(OD.codes)
    acwi_arr = fs._prep_arrays({"ACWI": E["acwi"]})
    e_arr = fs._prep_arrays(E["nav_by_fund"])
    GS = {k: m18.gold_sels(GD, envs[k][0]) for k in envs}
    DS = {}
    MHC = {}

    def sim(plan, kinds, fee, Ex=E):
        return r15.sim_cases_x(plan, nav_all, Ex["months"], fee, real, fset=fset, kinds=kinds, log_full="full" in kinds)

    def plans_of(cfg: Cfg):
        out = {}
        for k, (Ek, Pk, Xk) in envs.items():
            ctxs = MHC[k] if cfg.mh else Ek["ctx_h"]
            sl, recs = stream_gen(ctxs, Ek["quals"], cfg, fee_all if cfg.defx else fee_gold)
            legs = DS[k] if cfg.defx else GS[k]
            out[k] = (m19.gc_gold_plan(Ek, Xk, legs, sl), recs)
        return out

    def evaluate(tag, cfg):
        fee = fee_all if cfg.defx else fee_gold
        pk = plans_of(cfg)
        plans = {k: pk[k][0] for k in pk}
        s = sim(plans[0], ["c0", "flat", "full", "nofront"], fee)
        M = {k: rr.metrics(s[k]["values"], real) for k in ("c0", "flat", "full", "nofront")}
        offs = [ro.win_metrics(sim(plans[k], ["full"], fee, envs[k][0])["full"]["values"], real)["sharpe"] for k in (0, 1, 2)]
        single = {"model_id": tag, "sharpe": M["full"]["sharpe"], "cagr": M["full"]["cagr"], "vol": M["full"]["vol"], "max_dd": M["full"]["max_dd"],
                  "sharpe_nofront": M["nofront"]["sharpe"], "sharpe_c0": M["c0"]["sharpe"], "sharpe_flat": M["flat"]["sharpe"],
                  **m18.year_returns(s["full"]["values"]), "cost_bp_yr": s["full"]["cost_bp_yr"], "turn_yr": s["full"]["turn_yr"],
                  "off0": offs[0], "off1": offs[1], "off2": offs[2], "off_mean": float(np.mean(offs)), "r": M["full"]["r"], "rfm": M["full"]["rfm"]}
        # TR3
        tr = tr3_plans(plans, 0)
        V = {kind: sum(sim(p, [kind], fee)[kind]["values"] for p in tr) / 3 for kind in ("full", "nofront", "c0")}
        Mt = {kind: rr.metrics(V[kind], real) for kind in V}
        Vj = [sim(p, ["full"], fee)["full"]["values"] for p in tr]
        shifts = [win(sum(sim(p, ["full"], fee, envs[sh][0])["full"]["values"] for p in tr3_plans(plans, sh)) / 3, real) for sh in (0, 1, 2)]
        drops = [win((Vj[a] + Vj[b]) / 2, real) for a, b in ((0, 1), (0, 2), (1, 2))]
        trr = {"model_id": f"{tag}-TR3", "sharpe": Mt["full"]["sharpe"], "cagr": Mt["full"]["cagr"], "vol": Mt["full"]["vol"], "max_dd": Mt["full"]["max_dd"],
               "sharpe_nofront": Mt["nofront"]["sharpe"], "sharpe_c0": Mt["c0"]["sharpe"], **m18.year_returns(V["full"]),
               "shift0": shifts[0], "shift1": shifts[1], "shift2": shifts[2], "shift_mean": float(np.mean(shifts)), "drop_min": float(min(drops)),
               "half1": win(V["full"], real, WIN_A, WIN_MID), "half2": win(V["full"], real, WIN_MID, WIN_B),
               **fund_counts(tr), "turn_yr": float(np.mean([sim(p, ["full"], fee)["full"]["turn_yr"] for p in tr])),
               "r": Mt["full"]["r"], "rfm": Mt["full"]["rfm"]}
        return single, trr, pk

    # ---------------- regression: เส้นทางใหม่ (ปิดทุกสวิตช์) = M019 ----------------
    print("[reg] base = M019", flush=True)
    ref_w = pd.read_csv(os.path.join(RES, "M019_weights.csv"), parse_dates=["t"])
    base_pk = plans_of(Cfg())
    m = ref_w.merge(m18.weights_frame(base_pk[0][0], "x"), on=["t", "FundCode"], how="outer", suffixes=("_ref", "_new"))
    dw = float((m["weight_ref"] - m["weight_new"]).abs().max()) if m[["weight_ref", "weight_new"]].notna().all().all() else np.inf
    sh0 = rr.metrics(sim(base_pk[0][0], ["full"], fee_gold)["full"]["values"], real)["sharpe"]
    offs_ref = pd.read_csv(os.path.join(RES, "M019_offsets.csv")).query("model_id == 'M019-LC3-GCGOLD'").set_index("offset")["sharpe"]
    offs_new = [ro.win_metrics(sim(base_pk[k][0], ["full"], fee_gold, envs[k][0])["full"]["values"], real)["sharpe"] for k in (0, 1, 2)]
    tr_same = sum(sim(base_pk[0][0], ["full"], fee_gold)["full"]["values"] for _ in range(3)) / 3
    print(f"  max|Δw| {dw:.2e} · Sharpe {sh0:.6f} · offsets {np.round(offs_new, 4)} vs {np.round(offs_ref.values, 4)} · TR3(plan0×3) {rr.metrics(tr_same, real)['sharpe']:.6f}", flush=True)
    assert dw < 1e-12 and abs(sh0 - 1.098098) < 5e-7 and np.allclose(offs_new, offs_ref.values, atol=5e-7)
    assert abs(rr.metrics(tr_same, real)["sharpe"] - sh0) < 1e-9
    # MH regression (0,0,1) + DEFX regression (gold/AUM/no ρ) = GS
    for k, (Ek, _, _) in envs.items():
        MHC[k] = mh_ctxs(Ek, e_arr, (0, 0, 1))
        assert all(np.allclose(a["i_t"]["SR12"], b["i_t"]["SR12"]) for a, b in zip(MHC[k], Ek["ctx_h"]))
        g = defx_sels(OD, FD, Ek, acwi_arr, mode="gold")
        assert all(g[q][0] == GS[k][q][0] for q in range(15)), (k, [(g[q][0], GS[k][q][0]) for q in range(15) if g[q][0] != GS[k][q][0]])
        MHC[k] = mh_ctxs(Ek, e_arr)
        DS[k] = defx_sels(OD, FD, Ek, acwi_arr)
    print("  regression ผ่าน (base · offsets · TR3 · MH(0,0,1) · DEFX(gold)=GS)", flush=True)

    rows, logs = [], {}
    specs = [("M023", None), ("M024-FEE0", Cfg(fee0=True)), ("M025-HOLD18", Cfg(hold=HOLD_WIDE)),
             ("M026-DEFX", Cfg(defx=True)), ("M027-MH", Cfg(mh=True))]
    results = {}
    for tag, cfg in specs:
        print(f"[run] {tag}", flush=True)
        single, trr, pk = evaluate("M019" if cfg is None else tag, cfg or Cfg())
        if cfg is None:
            trr["model_id"] = "M023-TR3"
            results["M023"] = (None, trr)
        else:
            results[tag] = (single, trr)
        logs[tag] = pk
        for x in (single, trr):
            print(f"   {x['model_id']}: Sharpe {x['sharpe']:.3f} · CAGR {x['cagr']:.2%} · DD {x['max_dd']:.2%}"
                  + (f" · off mean {x['off_mean']:.3f}" if "off_mean" in x else f" · shift mean {x['shift_mean']:.3f} · drop min {x['drop_min']:.3f}"), flush=True)
    base_tr = results["M023"][1]["sharpe"]
    comps = [c for c in ("M024-FEE0", "M025-HOLD18", "M026-DEFX", "M027-MH") if results[c][1]["sharpe"] >= base_tr]
    print(f"[M028] ส่วนประกอบที่ผ่านกติกา (X-TR3 ≥ M023-TR3 {base_tr:.3f}): {comps}", flush=True)
    if comps:
        cfg = Cfg(fee0="M024-FEE0" in comps, hold=HOLD_WIDE if "M025-HOLD18" in comps else POOL,
                  defx="M026-DEFX" in comps, mh="M027-MH" in comps)
        single, trr = evaluate("M028-STACK", cfg)[:2]
        results["M028-STACK"] = (single, trr)
        print(f"   M028-STACK-TR3: Sharpe {trr['sharpe']:.3f} · CAGR {trr['cagr']:.2%} · shift mean {trr['shift_mean']:.3f} · drop min {trr['drop_min']:.3f}", flush=True)

    # ---------------- บันทึก ----------------
    order = ["M023"] + [k for k in results if k != "M023"]
    flat = []
    for k in order:
        for x in results[k]:
            if x is not None:
                flat.append(x)
    R = pd.DataFrame([{c: v for c, v in x.items() if c not in ("r", "rfm")} for x in flat]).set_index("model_id")
    R.to_csv(os.path.join(RES, "R1_results.csv"))
    # diagnostic: quarter returns offset 0 vs 1 ของ M019 (ไม่นับ trial)
    v0 = sim(base_pk[0][0], ["full"], fee_gold)["full"]["values"]
    v1 = sim(base_pk[1][0], ["full"], fee_gold, envs[1][0])["full"]["values"]
    qd = pd.DataFrame({"off0": v0.resample("QE").last().pct_change(), "off1": v1.resample("QE").last().pct_change()}).dropna()
    qd["gap"] = qd["off0"] - qd["off1"]
    qd.to_csv(os.path.join(RES, "R1_diag_offset_gap.csv"))
    shutil.copy(TRIALS, os.path.join(TEAM, f"trials.backup_{pd.Timestamp.now():%Y%m%dT%H%M%S}.csv"))
    cols = next(csv.reader(open(TRIALS, encoding="utf-8", newline="")))
    raw = open(TRIALS, "rb").read()
    n = max(int(float(x["n_trials_cumulative"])) for x in csv.DictReader(open(TRIALS, encoding="utf-8", newline="")) if x["n_trials_cumulative"])
    new = []
    for x in flat:
        n += 1
        new.append({"model_id": x["model_id"], "run_at": pd.Timestamp.now().isoformat(), "spec_file": "debate/R1_modeler.md",
                    "params": "R1 debate · base M019 · " + x["model_id"], "period_start": "2022-03-31", "period_end": "2025-12-31",
                    "rf_source": "BOT policy rate daily (TH_POLICY_RATE.csv)", "cost_assumption": "real fees SecFundFee FEEUH (full; FeeData legacy=False; E/F/O separate)",
                    "sharpe": round(x["sharpe"], 4), "cagr": round(x["cagr"], 4), "vol": round(x["vol"], 4), "max_dd": round(x["max_dd"], 4),
                    "turnover": round(x.get("turn_yr", np.nan), 4), "n_trials_cumulative": n, "deflated_sharpe": round(rr.dsr_s(x["r"], x["rfm"], n), 4),
                    "status": "ok", "notes": "; ".join(f"{c}={x[c]:.3f}" for c in ("off_mean", "shift_mean", "drop_min", "sharpe_nofront") if c in x)})
    eol = "\r\n" if raw.count(b"\r\n") > raw.count(b"\n") / 2 else "\n"
    buf = io.StringIO()
    csv.writer(buf, lineterminator=eol).writerows([[str(r[c]) for c in cols] for r in new])
    with open(TRIALS, "ab") as f:
        f.write((b"" if raw.endswith(b"\n") else eol.encode()) + buf.getvalue().encode("utf-8"))
    pd.set_option("display.width", 250)
    print(R.round(4).to_string())
    print(qd.round(4).to_string())
    print(f"trials ถึง n = {n} · done {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
