"""run_m018.py — M018: จำนวนกอง 3/5/8 × ขาที่ไม่ใช่หุ้น {ไม่มี (EQ100), กองตลาดเงิน (GCMMF), กองทอง (GCGOLD)} บนแกน GC75
spec: specs/M018_size_cash_gold.md (ผู้ใช้อนุมัติ 2026-10-12) · trial #36–#44 · DSR@44
reuse: fulluniv_run.build_env_and_plans (universe เต็ม · rf จริง · FeeData legacy=False) · run_m012 (เกณฑ์คุณภาพ) · run_m013 (GC75) · run_m015 (กอง F)
ลำดับ: regression (ไม่ผ่าน = หยุด ไม่บันทึก trial) -> 9 แบบ offset 0 -> offset 1/2 (รายงาน) -> results/M018_* + trials.csv (backup ก่อน)
รัน: PYTHONPATH=. ./.venv/bin/python .claude/quant_team/backtest/run_m018.py
"""
from __future__ import annotations

import math
import os
import shutil
import sys
import time

THIS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, THIS)

import numpy as np
import pandas as pd

import common
import fees
import fund_signals as fs
import remeasure_real_rf as rr
import robust_offsets as ro
import run_m006_m007 as r67
import run_m011 as r11
import run_m012 as r12
import run_m013 as r13
import run_m015 as r15
import weighting as wt
import fulluniv_run as fu

sys.path.insert(0, common.PROJECT_ROOT)
from data.nav_loader import _detect_and_fix_spikes   # pure function (ไม่เขียนไฟล์) — กติกาแก้ spike ของกองหุ้น

TEAM = os.path.dirname(THIS)
RES = common.RESULTS_DIR
TRIALS = os.path.join(TEAM, "trials.csv")
GOLD_PARQUET = os.path.join(common.CACHE_DIR, "m018_navO_gold.parquet")
N_TRIALS = 44
SIZES = {3: 6, 5: 10, 8: 16}                 # N -> K (= 2N)
CAP = 0.40
LEGS = ("EQ100", "GCMMF", "GCGOLD")
KINDS = ["c0", "flat", "full", "nofront"]


def nmin_of(n):
    return max(2, math.ceil(n / 2))           # fallback B0 เมื่อคัดได้ < ค่านี้ (N=8 -> 4 = เกณฑ์เดิม)


# ---------------- การคัดกองหุ้น (= run_m012.select_variant mode "S" + N/K/nmin เป็นพารามิเตอร์) ----------------
def select(ctx, held, prev_fb, qual, n, k, nmin):
    i_t = ctx["i_t"]
    H_map = {} if prev_fb else held
    fam_ok = set(qual.index[qual["pass_q1"] & qual["pass_q2"]])
    it = i_t[i_t["family"].isin(fam_ok)]
    reps = wt.family_representatives(it, "SR12", held_funds=set(held.values()))
    ranks = wt.rank_families(reps)
    sel = wt.hysteresis_select(reps, ranks, H_map, n, k, None, rho_max=0.85)
    fb = len(sel["S"]) < nmin or len(sel["S"]) == 0
    return {"S": dict(sel["S"]), "fallback": fb, "reps": reps, "ranks": ranks}


def stream(ctxs, quals, n, k, cap, nmin):
    held, prev_fb = {}, False
    sleeves, recs = {}, []
    for ctx in ctxs:
        qi = ctx["qi"]
        rec = select(ctx, held, prev_fb, quals[qi], n, k, nmin)
        recs.append(rec)
        if rec["fallback"]:
            held, prev_fb = {}, True
            sleeves[qi] = ctx["b0_w"]
            continue
        held, prev_fb = dict(rec["S"]), False
        funds = list(rec["S"].values())
        w, _ = wt.risk_parity_weights(funds, ctx["wk"], ctx["vol_map"], method="erc")
        sleeves[qi] = wt.apply_cap(w, cap)
    return sleeves, recs


# ---------------- กองทอง (spec §4.4 — ขนานกับกอง F ของ M015) ----------------
def gold_profile(profile):
    p = profile[(profile["Fund Policy"].str.strip() == "O") & profile["Fund Name EN"].fillna("").str.upper().str.contains("GOLD")]
    return p


def gold_snapshot(profile) -> set:
    g = gold_profile(profile)
    ok = g[g["Tax Type"].isna() & (g["buy period flag"] == "N") & (g["Project Retail Type"] == "R")]
    ok = ok[~ok["Fund Name EN"].fillna("").str.contains("Not for Retail|NOT FOR RETAIL|TEST", regex=True)]
    return set(ok.index)


def build_nav_gold(codes, force=False) -> pd.DataFrame:
    """NAV กองทองจาก nav_history_db.csv — dedupe แบบ M015 (UpdateTime ล่าสุด) · แก้ spike ด้วยกติกากองหุ้น · cache ใน backtest/cache/."""
    if os.path.exists(GOLD_PARQUET) and not force:
        d = pd.read_parquet(GOLD_PARQUET)
        d["NAVDate"] = pd.to_datetime(d["NAVDate"])
        return d
    parts = []
    for ch in pd.read_csv(os.path.join(common.PROJECT_ROOT, "base_data", "nav_history_db.csv"),
                          usecols=["FundCode", "NAV", "NAVDate", "AUM", "UpdateTime"], chunksize=500_000, dtype={"FundCode": str}):
        ch["FundCode"] = ch["FundCode"].str.strip()
        parts.append(ch[ch["FundCode"].isin(codes)])
    d = pd.concat(parts)
    d["NAVDate"] = pd.to_datetime(d["NAVDate"], errors="coerce")
    d["NAV"] = pd.to_numeric(d["NAV"], errors="coerce")
    d["AUM"] = pd.to_numeric(d["AUM"], errors="coerce")
    d = d.dropna(subset=["NAVDate", "NAV"])
    d = d[d["NAV"] > 0]
    d = d.sort_values(["FundCode", "NAVDate", "UpdateTime"]).drop_duplicates(["FundCode", "NAVDate"], keep="last")
    out = []
    for fc, g in d.groupby("FundCode"):
        g = g.sort_values("NAVDate").copy()
        fixed, idx = _detect_and_fix_spikes(g["NAV"].to_numpy(float))
        g["NAV"] = fixed
        g["spike_fixed"] = False
        if idx:
            g.iloc[idx, g.columns.get_loc("spike_fixed")] = True
        out.append(g[["FundCode", "NAVDate", "NAV", "AUM", "spike_fixed"]])
    D = pd.concat(out, ignore_index=True)
    D.to_parquet(GOLD_PARQUET)
    return D


class GData(r15.FData):
    """เหมือน FData (กอง F) แต่เป็นกองทอง policy O — ใช้ it_at / Quality / f_signal ของเดิม."""
    def __init__(self, profile, E, f_codes):
        self.profile = profile
        self.nav = build_nav_gold(set(gold_profile(profile).index))
        self.codes = sorted(self.nav["FundCode"].unique())
        self.nav_by_fund = {fc: g.sort_values("NAVDate").set_index("NAVDate")["NAV"] for fc, g in self.nav.groupby("FundCode")}
        self.snap = gold_snapshot(profile)
        self.groups = {fc: profile.loc[fc, "Fund Class"] for fc in self.codes if isinstance(profile.loc[fc, "Fund Class"], str)}
        self.arrays = fs._prep_arrays(self.nav_by_fund)
        self.calendar = E["calendar"]
        self.Q = r12.Quality(self.nav, self.groups)
        self.risk, self.fif, self.amc = profile["Fund Risk Level"], profile["FIF Flag"], profile["AMC_CODE"]
        self.spike = self.nav.groupby("FundCode")["spike_fixed"].sum().to_dict()
        assert not (set(self.codes) & set(E["nav_by_fund"])), "กองทองซ้ำกับกองหุ้น"
        assert not (set(self.codes) & set(f_codes)), "กองทองซ้ำกับกอง F"


def select_gold(it, qual, h):
    """family ที่ AUM_fam ใหญ่สุด (ผ่านคุณภาพ) -> class ตัวแทน SR12′ สูงสุด · ไม่มี -> {} (ใช้กองตลาดเงินแทน)."""
    info = {"empty": False}
    if len(it) == 0:
        info["empty"] = True
        return {}, info, pd.DataFrame()
    ok = set(qual.index[qual["pass_q1"] & qual["pass_q2"]])
    it = it[it["family"].isin(ok)].copy()
    if len(it) == 0:
        info["empty"] = True
        return {}, info, pd.DataFrame()
    it["SR12p"] = (it["R12_1"] - h) / it["vol52"]
    it["aum_fam"] = it["family"].map(qual["aum_fam"])
    reps = it.sort_values(["SR12p", "FundCode"], ascending=[False, True]).groupby("family", sort=False).head(1)
    c = reps.sort_values(["aum_fam", "FundCode"], ascending=[False, True]).head(1)
    return {c.iloc[0]["FundCode"]: 1.0}, info, reps


def gold_sels(GD, E):
    out = {}
    for qi, t in enumerate(E["q15"]):
        it, qual, _ = GD.it_at(t)
        out[qi] = select_gold(it, qual, E["h_by_q"][qi])
        for f in out[qi][0]:
            assert f in set(it["FundCode"]) and f in GD.snap
    return out


# ---------------- ค่าธรรมเนียม E / F / O แยกกัน ----------------
class Fee3(r15.CombinedFee):
    def __init__(self, fd_e, fd_f, f_codes, fd_o, o_codes):
        super().__init__(fd_e, fd_f, f_codes)
        self.fd_o, self.o_codes = fd_o, set(o_codes)
        self.amc = {**self.amc, **fd_o.amc}

    def rate(self, fc, code, e):
        if fc in self.o_codes:
            return self.fd_o.rate(fc, code, e)
        return super().rate(fc, code, e)


# ---------------- plans ----------------
def plans_for(E, X, GS, n, cap, nmin):
    sleeves, recs = stream(E["ctx_h"], E["quals"], n, SIZES[n], cap, nmin)
    s15 = {q: v for q, v in sleeves.items() if q < 15}
    kmap = dict(zip(E["sig"]["t"], E["sig"]["k"]))
    base_gc, xmap = r13.gc_plan(E, s15, kmap, r13.TABLES["GC75"])
    out = {"EQ100": r67.old_style_plan(s15, E["q15"], E["calendar"], lambda t: 0.0),
           "GCMMF": r15.make_plan_F(base_gc, X["sels"]["FAUM"])[0]}
    g1, fb_gold = r15.make_plan_F(base_gc, GS)                    # ไม่มีกองทอง -> คง __CASH__ ...
    out["GCGOLD"] = r15.make_plan_F(g1, X["sels"]["FAUM"])[0]      # ... แล้วเติมด้วยกองตลาดเงิน (spec §4.4)
    for name, plan in out.items():
        for p in plan:
            assert abs(sum(p["weights"].values()) - 1) < 1e-9, (name, p["t"])
            assert "__CASH__" not in p["weights"] or name != "EQ100"
    return out, recs, fb_gold, xmap


def weights_frame(plan, tag):
    return pd.DataFrame([{"model": tag, "t": p["t"], "e": p["e"], "FundCode": f, "weight": w}
                         for p in plan for f, w in p["weights"].items()])


def year_returns(v):
    v = v[v.index <= rr.PE]
    out = {}
    for y in (2022, 2023, 2024, 2025):
        prev = v[v.index < pd.Timestamp(f"{y}-01-01")]
        out[f"y{y}"] = float(v[v.index <= pd.Timestamp(f"{y}-12-31")].iloc[-1] / (prev.iloc[-1] if len(prev) else v.iloc[0]) - 1)
    return out


def main():
    t0 = time.time()
    holder = {}
    print("[1/5] env offset 0 + กองทอง", flush=True)
    E, P, X = fu.build_env_and_plans(0, holder)
    FD = holder["FD"]
    profile = r15.load_profile()
    f_codes = sorted(FD.profile.index[FD.profile["Fund Policy"] == "F"])
    GD = GData(profile, E, f_codes)
    GS = gold_sels(GD, E)
    fee = Fee3(E["fd_sim"], fees.FeeData(f_codes), f_codes, fees.FeeData(GD.codes), GD.codes)
    nav_all = {**E["nav_by_fund"], **FD.nav_by_fund, **GD.nav_by_fund}
    fset = set(FD.codes) | set(GD.codes)
    real = E["real"]

    def sim(plan, kinds=KINDS, Ex=E):
        return r15.sim_cases_x(plan, nav_all, Ex["months"], fee, real, fset=fset, kinds=kinds, log_full="full" in kinds)

    print("[2/5] regression", flush=True)
    reg_plans, _, _, _ = plans_for(E, X, GS, 8, 0.25, 4)
    ref = pd.read_csv(os.path.join(RES, "FULLUNIV_weights.csv"))
    ref = ref[(ref["model"] == "A") & (ref["offset"] == 0)].assign(t=lambda d: pd.to_datetime(d["t"]))
    mine = weights_frame(reg_plans["GCMMF"], "x")
    m = ref.merge(mine, on=["t", "FundCode"], how="outer", suffixes=("_ref", "_new"))
    dw = float((m["weight_ref"] - m["weight_new"]).abs().max()) if m["weight_ref"].notna().all() and m["weight_new"].notna().all() else np.inf
    sh_reg = rr.metrics(sim(reg_plans["GCMMF"], ["full"])["full"]["values"], real)["sharpe"]
    sh_ref = float(pd.read_csv(os.path.join(common.PROJECT_ROOT, "base_data", "reference", "tf_top3_metrics.csv"), comment="#")
                   .query("series == 'GC75_MMF' and case == 'full'")["sharpe"].iloc[0])
    sh_A = rr.metrics(ro.sims_for("A", reg_plans["GCMMF"], E, FD, ["full"])["full"]["values"], real)["sharpe"]   # fee path เดิม
    print(f"  max|Δw| {dw:.2e} · Sharpe {sh_reg:.6f} (ref {sh_ref:.6f} · fee path เดิม {sh_A:.6f})", flush=True)
    if not (dw < 1e-12 and abs(sh_reg - sh_ref) < 5e-7 and abs(sh_reg - sh_A) < 1e-12):
        print("REGRESSION FAIL — หยุด ไม่บันทึก trial"); sys.exit(2)

    print("[3/5] 9 แบบ offset 0", flush=True)
    rows, wts, gold_rows, rets = [], [], [], {}
    for n in SIZES:
        plans, recs, fb_gold, xmap = plans_for(E, X, GS, n, CAP, nmin_of(n))
        n_fb = sum(1 for r in recs[:15] if r["fallback"])
        for leg in LEGS:
            tag = f"M018-N{n}-{leg}"
            s = sim(plans[leg])
            M = {k: rr.metrics(s[k]["values"], real) for k in KINDS}
            r, rfm = M["full"]["r"], M["full"]["rfm"]
            lo, hi = rr.boot_ci(r, rfm)
            log = pd.DataFrame(s["full"]["feelog"])
            yrs = s["yrs"]
            eq_w = [max((w for f, w in p["weights"].items() if f not in fset and f != "__CASH__"), default=0) /
                    max(sum(w for f, w in p["weights"].items() if f not in fset and f != "__CASH__"), 1e-12) for p in plans[leg]]
            rows.append({"model_id": tag, "N": n, "K": SIZES[n], "leg": leg, **{f"sharpe_{k}": M[k]["sharpe"] for k in KINDS},
                         "cagr_full": M["full"]["cagr"], "cagr_nofront": M["nofront"]["cagr"], "vol": M["full"]["vol"],
                         "max_dd": M["full"]["max_dd"], "ci_lo": lo, "ci_hi": hi, "dsr44": rr.dsr_s(r, rfm, N_TRIALS),
                         "sharpe_2022": M["full"]["sharpe_2022"], "sharpe_2307_2512": M["full"]["sharpe_2307_2512"],
                         **year_returns(s["full"]["values"]), "cost_bp_yr": s["full"]["cost_bp_yr"],
                         "cost_stock_bp_yr": log[log["e"] <= rr.PE]["stock_only"].sum() / yrs * 1e4,
                         "cost_leg_bp_yr": log[log["e"] <= rr.PE]["f_related"].sum() / yrs * 1e4,
                         "switch_share": s["full"].get("switch_share"), "turn_yr": s["full"]["turn_yr"],
                         "max_sleeve_w": float(max(eq_w)), "n_fallback_b0": n_fb,
                         "n_gold_to_mmf": len(fb_gold) if leg == "GCGOLD" else np.nan, "n_cannot_buy": s["full"]["n_cannot_buy"]})
            rets[tag] = (r, rfm)
            wts.append(weights_frame(plans[leg], tag))
            if leg == "GCGOLD" and n == 8:
                for qi, p in enumerate(plans[leg]):
                    leg_f = [f for f in p["weights"] if f in fset]
                    gold_rows += [{"t": p["t"], "x_t": xmap[p["t"]], "fund": f, "kind": "O" if f in set(GD.codes) else "F",
                                   "weight": p["weights"][f], "class_H": "-H" in f or "HEDGED" in str(profile.loc[f, "Fund Name EN"]).upper(),
                                   "AMC": profile.loc[f, "AMC_CODE"]} for f in leg_f]
            print(f"  {tag}: Sharpe full {M['full']['sharpe']:.3f} · CAGR {M['full']['cagr']:.2%} · DD {M['full']['max_dd']:.2%}", flush=True)
    R = pd.DataFrame(rows).set_index("model_id")
    for n in SIZES:                                          # paired Δ Sharpe (full · rf จริง)
        for a, b in (("GCMMF", "EQ100"), ("GCGOLD", "GCMMF")):
            ra, rfm = rets[f"M018-N{n}-{a}"]
            rb, _ = rets[f"M018-N{n}-{b}"]
            lo, hi, pt = r11.paired_real(ra, rb, rfm)
            R.loc[f"M018-N{n}-{a}", f"d_vs_{b}"] = pt
            R.loc[f"M018-N{n}-{a}", f"d_vs_{b}_ci"] = f"[{lo:.3f}, {hi:.3f}]"

    print("[4/5] offset 1/2 (รายงานเท่านั้น)", flush=True)
    off_rows = []
    for k in (0, 1, 2):
        Ek, Pk, Xk = (E, P, X) if k == 0 else fu.build_env_and_plans(k, holder)
        GSk = GS if k == 0 else gold_sels(GD, Ek)
        for n in SIZES:
            plans, _, _, _ = plans_for(Ek, Xk, GSk, n, CAP, nmin_of(n))
            for leg in LEGS:
                v = sim(plans[leg], ["full"], Ek)["full"]["values"]
                w = ro.win_metrics(v, real)
                off_rows.append({"model_id": f"M018-N{n}-{leg}", "offset": k, "sharpe": w["sharpe"], "cagr": w["cagr"], "max_dd": w["max_dd"]})
    OFF = pd.DataFrame(off_rows)
    rng = OFF.groupby("model_id")["sharpe"].agg(["min", "max"])
    R["offset_sharpe_min"], R["offset_sharpe_max"] = rng["min"], rng["max"]

    print("[5/5] บันทึก", flush=True)
    R.to_csv(os.path.join(RES, "M018_results.csv"))
    pd.concat(wts).to_csv(os.path.join(RES, "M018_weights.csv"), index=False)
    OFF.to_csv(os.path.join(RES, "M018_offsets.csv"), index=False)
    pd.DataFrame(gold_rows).to_csv(os.path.join(RES, "M018_gold_leg.csv"), index=False)
    stamp = pd.Timestamp.now().strftime("%Y%m%dT%H%M%S")
    shutil.copy(TRIALS, os.path.join(TEAM, f"trials.backup_{stamp}.csv"))
    tr = pd.read_csv(TRIALS)
    assert int(tr["n_trials_cumulative"].max()) == 35, "trials.csv ไม่ได้อยู่ที่ n = 35 ตามที่ spec ลงทะเบียน"
    run_at = pd.Timestamp.now().isoformat()
    new = []
    for i, (mid, x) in enumerate(R.iterrows()):
        new.append({"model_id": mid, "run_at": run_at, "spec_file": "M018_size_cash_gold.md",
                    "params": f"M018: N={int(x.N)};K={int(x.K)};cap=40%;fallback<{nmin_of(int(x.N))};leg={x.leg};GC75 k->x;SR12' real rf;quality S;full universe",
                    "period_start": "2022-03-31", "period_end": "2025-12-31", "rf_source": "BOT policy rate daily (TH_POLICY_RATE.csv)",
                    "cost_assumption": "real fees SecFundFee FEEUH (full; FeeData legacy=False; E/F/O separate)",
                    "sharpe": round(x.sharpe_full, 4), "cagr": round(x.cagr_full, 4), "vol": round(x.vol, 4), "max_dd": round(x.max_dd, 4),
                    "turnover": round(x.turn_yr, 4), "n_trials_cumulative": 36 + i, "deflated_sharpe": round(x.dsr44, 4), "status": "ok",
                    "notes": (f"DSR@44 (ทั้งชุดลงทะเบียนพร้อมกัน); Sharpe 0%={x.sharpe_c0:.3f} flat={x.sharpe_flat:.3f} nofront={x.sharpe_nofront:.3f}; "
                              f"CI95 ({x.ci_lo:.3f};{x.ci_hi:.3f}); offset {x.offset_sharpe_min:.3f}-{x.offset_sharpe_max:.3f}"
                              + ("; POST-HOC LABEL: ผู้ใช้เห็นผลตอบแทนกองทองก่อนเสนอ" if x.leg == "GCGOLD" else ""))})
    # append เป็นข้อความต่อท้าย — ห้ามอ่าน/เขียนทั้งไฟล์ด้วย pandas (เคยเปลี่ยนรูปแบบแถวเดิม 1 -> 1.0 · 2026-10-12)
    import csv, io
    raw = open(TRIALS, "rb").read()
    eol = "\r\n" if raw.count(b"\r\n") > raw.count(b"\n") / 2 else "\n"
    buf = io.StringIO()
    csv.writer(buf, lineterminator=eol).writerows([[str(r[c]) for c in tr.columns] for r in new])
    with open(TRIALS, "ab") as f:
        f.write((b"" if raw.endswith(b"\n") else eol.encode()) + buf.getvalue().encode("utf-8"))
    pd.set_option("display.width", 250)
    cols = ["sharpe_full", "sharpe_nofront", "cagr_full", "vol", "max_dd", "dsr44", "ci_lo", "ci_hi", "offset_sharpe_min", "offset_sharpe_max",
            "y2022", "y2023", "y2024", "y2025", "cost_bp_yr", "cost_stock_bp_yr", "cost_leg_bp_yr", "max_sleeve_w", "n_fallback_b0", "n_gold_to_mmf"]
    print(R[cols].round(4).to_string())
    print(R[[c for c in R.columns if c.startswith("d_vs")]].to_string())
    print(pd.DataFrame(gold_rows).to_string())
    print(f"done {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
