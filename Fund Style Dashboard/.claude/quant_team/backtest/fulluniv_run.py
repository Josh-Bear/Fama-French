"""fulluniv_run.py — วัดผลโมเดลหลักบน universe เต็ม (ลูกค้าซื้อได้ทุก class) · 2026-10-07 · backtest-validator
**ไม่ใช่ trial** (ไม่แตะ trials.csv) · ไม่แก้ไฟล์เดิมใน backtest/ · reuse rerun_retail_universe / robust_offsets / robust_fees / run_m015 / remeasure_real_rf ผ่าน wrapper

universe เต็ม = ไม่ตัด class ตามขั้นต่ำซื้อ ทั้งฝั่งหุ้น (cut_set = ว่าง) และฝั่งกอง F ของ M015 (snapshot F ตัดเงื่อนไข fst_lowbuy_val <= 100,000 ออก;
เงื่อนไขอื่น = Tax Type ว่าง / buy period N / Retail Type R / ชื่อไม่ใช่ Not for Retail|TEST คงเดิม) · rf จริง (policy rate) · FeeData(legacy=False)
ขั้นตอน: (1) regression (ต้องตรงค่าเดิม) -> (2) ตารางโมเดล offset 0 ช่วงเดิม 45 เดือน -> (3) offset 0/1/2 + tranche (A, B, B0) ช่วงร่วม ก.ค.2022-ธ.ค.2025
 -> (4) ค่าธรรมเนียม 4 กรณี A/B offset 0 -> (5) CAGR ก่อน/หลังค่าธรรมเนียม + ปีปฏิทินของ tranche -> บันทึก results/FULLUNIV_*.csv + scratch/validator_full_out.pkl
รัน: PYTHONPATH=. ./.venv/bin/python .claude/quant_team/backtest/fulluniv_run.py
"""
from __future__ import annotations

import json
import os
import pickle
import sys
import time

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if THIS_DIR not in sys.path:
    sys.path.insert(0, THIS_DIR)

import numpy as np
import pandas as pd

import common
import fees
import simulate
import remeasure_real_rf as rr
import run_m011 as r11
import run_m013 as r13
import run_m015 as r15
import rerun_retail_universe as rru
import robust_offsets as ro
import robust_fees as rf

TEAM_DIR = os.path.dirname(THIS_DIR)
SCRATCH = os.path.join(TEAM_DIR, "scratch")
RES = common.RESULTS_DIR
N_TRIALS = 32
CTX = {0: os.path.join(SCRATCH, "validator_m012_ctxs.pkl"),            # ctx เต็ม offset 0 (อ่านอย่างเดียว — มีอยู่แล้วจากรอบ M012)
       1: os.path.join(SCRATCH, "validator_full_ctxs_off1.pkl"),
       2: os.path.join(SCRATCH, "validator_full_ctxs_off2.pkl")}
MODELS6 = ["B0", "Trend25", "M011-RFH", "M012-QF-S", "M013-GC75", "M015-FAUM"]


def snapshot_full(profile: pd.DataFrame) -> set:
    """snapshot กอง F สำหรับ universe เต็ม = snapshot_codes เดิม ตัดเงื่อนไขขั้นต่ำซื้อ (fst_lowbuy_val <= 100000) ออก."""
    F = profile[profile["Fund Policy"] == "F"]
    ok = F[(F["Tax Type"].isna()) & (F["buy period flag"] == "N") & (F["Project Retail Type"] == "R")]
    ok = ok[~ok["Fund Name EN"].fillna("").str.contains("Not for Retail|NOT FOR RETAIL|TEST", regex=True)]
    return set(ok.index)


class FullFData(r15.FData):
    def __init__(self, profile, E):
        super().__init__(profile, E)
        self.snap_retail = self.snap
        self.snap = snapshot_full(profile)


def build_env_and_plans(k, FD_holder):
    E = ro.setup_env_off(k, set(), CTX[k])                      # cut_set ว่าง = universe เต็ม
    if FD_holder.get("FD") is None:
        FD_holder["FD"] = FullFData(r15.load_profile(), E)
    FD = FD_holder["FD"]
    P = rru.build_plans(E)                                      # B0, Trend25, M011-RFH, M012-QF-S, M013-GC75 (โค้ดเดิม)
    base = P["M013-GC75"]
    rows = r15.f_rows(FD, E, E["h_by_q"])
    sels = r15.f_selections(FD, rows)
    fset_all = set(FD.codes)
    plan_a, fb_q = r15.make_plan_F(base, sels["FAUM"])
    mx = r15.plan_checks(plan_a, base, fset_all)
    for qi, p in enumerate(plan_a):
        for f in p["weights"]:
            if f in fset_all:
                assert f in set(rows[qi]["it"]["FundCode"]) and f in FD.snap and f not in E["nav_by_fund"]
    P["M015-FAUM"] = plan_a
    return E, P, {"fb_q": fb_q, "mx": mx, "rows": rows, "sels": sels, "base": base}


def sim_model(name, plan, E, FD, kinds, fd_e=None, fd_f=None):
    return ro.sims_for("A" if name == "M015-FAUM" else "B", plan, E, FD, kinds, fd_e=fd_e, fd_f=fd_f)


def bundle(sims, real, kinds=("full", "nofront", "c0")):
    return {k: rr.metrics(sims[k]["values"], real) for k in kinds}


def nolookahead_F(FD, rows):
    """คำนวณ I_t^F ใหม่จาก NAV ที่ตัด ≤ t ต้องได้เหมือนเดิม (กัน look-ahead ของขา F บน snapshot ใหม่)."""
    mxd, nmis = 0.0, 0
    for r in rows:
        navt = FD.nav[FD.nav["NAVDate"] <= r["t"]]
        it2, q2, _ = FD.it_at(r["t"], nav_override=navt)
        a = r["it"].set_index("FundCode")[["R12_1", "vol52"]].sort_index()
        b = it2.set_index("FundCode")[["R12_1", "vol52"]].sort_index()
        nmis += int(set(a.index) != set(b.index))
        if len(a) and set(a.index) == set(b.index):
            mxd = max(mxd, float((a - b).abs().max().max()))
    return mxd, nmis


def main():
    t0 = time.time()
    holder = {}
    envs, plans, extra, sims = {}, {}, {}, {}
    for k in ro.OFFSETS:
        E, P, X = build_env_and_plans(k, holder)
        FD = holder["FD"]
        envs[k], plans[k], extra[k] = E, P, X
        print(f"[off{k}] env+plans ({time.time()-t0:.0f}s) · t0={E['q15'][0].date()} · FAUM fallback quarters {X['fb_q']} · max|dw| stock {X['mx']:.1e}", flush=True)
        names = MODELS6 if k == 0 else ["M015-FAUM", "Trend25", "B0"]
        sims[k] = {m: sim_model(m, P[m], E, FD, ["full", "nofront", "c0"]) for m in names}
        print(f"[off{k}] sims done ({time.time()-t0:.0f}s)", flush=True)
    FD, E0, real = holder["FD"], envs[0], envs[0]["real"]
    mxd, nmis = nolookahead_F(FD, extra[0]["rows"])
    print(f"[no-lookahead F] max|d signal| {mxd:.2e} · differing I_t^F quarters {nmis}", flush=True)
    assert mxd < 1e-12 and nmis == 0

    # ---------- (1) regression ----------
    refreal = pd.read_csv(os.path.join(RES, "REAL_RF_summary.csv")).set_index("trial")
    ref11 = pd.read_csv(os.path.join(RES, "M011_results.csv")).set_index(["trial", "cost"])
    ref12 = pd.read_csv(os.path.join(RES, "M012_results.csv")).set_index(["trial", "cost"])
    ref13 = pd.read_csv(os.path.join(RES, "M013_results.csv")).set_index(["trial", "cost"])
    MB = {m: bundle(sims[0][m], real) for m in MODELS6}
    # FAUM ขา F = เงินสด: plan baseline GC75 ผ่านเส้นทางโค้ด A (r15.sim_cases_x + CombinedFee + nav_all)
    base_cash = sims_cash = ro.sims_for("A", extra[0]["base"], E0, FD, ["full"])
    sh_cash = rr.metrics(base_cash["full"]["values"], real)["sharpe"]
    reg = {"B0": {"got": MB["B0"]["full"]["sharpe"], "ref": 0.0759, "tol": 5e-5},
           "Trend25": {"got": MB["Trend25"]["full"]["sharpe"], "ref": float(refreal.loc["M004-TF-FX", "sharpe_full_real"]), "tol": 5e-7},
           "M011-RFH": {"got": MB["M011-RFH"]["full"]["sharpe"], "ref": float(ref11.loc[("M011-RFH", "full"), "sharpe_real"]), "tol": 5e-7},
           "M012-QF-S": {"got": MB["M012-QF-S"]["full"]["sharpe"], "ref": float(ref12.loc[("M012-QF-S", "full"), "sharpe_real"]), "tol": 5e-7},
           "M013-GC75": {"got": MB["M013-GC75"]["full"]["sharpe"], "ref": float(ref13.loc[("M013-GC75", "full"), "sharpe_real"]), "tol": 5e-7},
           "FAUM_F_is_cash": {"got": sh_cash, "ref": float(ref13.loc[("M013-GC75", "full"), "sharpe_real"]), "tol": 5e-7}}
    for v in reg.values():
        v["ok"] = bool(abs(v["got"] - v["ref"]) < v["tol"])
    reg["ok_all"] = bool(all(v["ok"] for v in reg.values()))
    print("REGRESSION:", json.dumps(reg, default=float), flush=True)
    json.dump(reg, open(os.path.join(SCRATCH, "validator_full_regression.json"), "w"), default=float)
    if not reg["ok_all"]:
        print("REGRESSION FAIL — หยุด", flush=True)
        return 2

    # ---------- (2) ตารางโมเดล ----------
    rows = []
    for m in MODELS6:
        M = MB[m]
        rn, rfm = M["full"]["r"], M["full"]["rfm"]
        lo, hi = rr.boot_ci(rn, rfm)
        s = sims[0][m]["full"]
        rows.append({"model": m, "sharpe_full": M["full"]["sharpe"], "sharpe_nofront": M["nofront"]["sharpe"], "sharpe_c0": M["c0"]["sharpe"],
                     "cagr_full": M["full"]["cagr"], "vol_full": M["full"]["vol"], "maxdd_full": M["full"]["max_dd"],
                     "cagr_nofront": M["nofront"]["cagr"], "cagr_c0": M["c0"]["cagr"],
                     "sharpe_2022_full": M["full"]["sharpe_2022"], "sharpe_2307_2512_full": M["full"]["sharpe_2307_2512"],
                     "ci_lo": lo, "ci_hi": hi, "dsr32": rr.dsr_s(rn, rfm, N_TRIALS), "cost_pct_yr_full": s["cost_bp_yr"] / 100.0, "turn_yr": s["turn_yr"],
                     "n_cannot_buy": s["n_cannot_buy"], "n_months": M["full"]["n_months"]})
    T = pd.DataFrame(rows)
    T.to_csv(os.path.join(RES, "FULLUNIV_models.csv"), index=False)
    # paired: M015-FAUM − M013-GC75 และ vs Trend25
    pr = []
    for a, b in (("M015-FAUM", "M013-GC75"), ("M015-FAUM", "Trend25"), ("M013-GC75", "Trend25")):
        lo, hi, pt = r11.paired_real(MB[a]["full"]["r"], MB[b]["full"]["r"], MB[a]["full"]["rfm"], "r")
        pr.append({"a": a, "b": b, "d_sharpe_full": pt, "ci_lo": lo, "ci_hi": hi})
    pd.DataFrame(pr).to_csv(os.path.join(RES, "FULLUNIV_paired.csv"), index=False)

    # ---------- (3) offset + tranche (ช่วงร่วม) ----------
    MODS3 = ("A", "B", "B0")
    key = {"A": "M015-FAUM", "B": "Trend25", "B0": "B0"}
    WM, orig = {}, {}
    for m in MODS3:
        for kind in ("full", "nofront", "c0"):
            vs = [sims[k][key[m]][kind]["values"] for k in ro.OFFSETS]
            for k, v in zip(ro.OFFSETS, vs):
                WM[(m, k, kind)] = ro.win_metrics(v, real)
                orig[(m, k, kind)] = rr.metrics(v, real)
            WM[(m, "tr", kind)] = ro.win_metrics(ro.tranche_values(vs), real)
    orow, rets = [], {}
    for m in MODS3:
        for k in (*ro.OFFSETS, "tr"):
            w = WM[(m, k, "full")]
            o = {"model": m, "offset": k, "sharpe": w["sharpe"], "cagr": w["cagr"], "vol": w["vol"], "max_dd": w["max_dd"], "n_months": w["n_months"],
                 "sharpe_nofront": WM[(m, k, "nofront")]["sharpe"], "sharpe_c0": WM[(m, k, "c0")]["sharpe"],
                 "cagr_c0": WM[(m, k, "c0")]["cagr"], "cagr_nofront": WM[(m, k, "nofront")]["cagr"],
                 "sharpe_2022h2": w["sharpe_2022h2"], "sharpe_2307_2512": w["sharpe_2307_2512"]}
            lo, hi = rr.boot_ci(w["r"], w["rfm"])
            o.update({"ci_lo": lo, "ci_hi": hi})
            if k != "tr":
                s = sims[k][key[m]]["full"]
                om = orig[(m, k, "full")]
                oc = orig[(m, k, "c0")]
                o.update({"cost_pct_yr": s["cost_bp_yr"] / 100.0, "turn_yr": s["turn_yr"], "sharpe_origwin": om["sharpe"], "cagr_origwin": om["cagr"],
                          "cagr_c0_origwin": oc["cagr"], "n_months_origwin": om["n_months"], "maxdd_origwin": om["max_dd"]})
            orow.append(o)
            rets[(m, k)] = w["r"]
    OF = pd.DataFrame(orow)
    OF.to_csv(os.path.join(RES, "FULLUNIV_offsets.csv"), index=False)
    agg = []
    for m in MODS3:
        d = OF[(OF["model"] == m) & (OF["offset"] != "tr")]
        tr = OF[(OF["model"] == m) & (OF["offset"] == "tr")].iloc[0]
        agg.append({"model": m, "sharpe_mean": d["sharpe"].mean(), "sharpe_min": d["sharpe"].min(), "sharpe_max": d["sharpe"].max(), "sharpe_tranche": tr["sharpe"],
                    "cagr_mean": d["cagr"].mean(), "cagr_min": d["cagr"].min(), "cagr_max": d["cagr"].max(), "cagr_tranche": tr["cagr"], "maxdd_worst": d["max_dd"].min(),
                    "maxdd_tranche": tr["max_dd"], "vol_tranche": tr["vol"]})
    pd.DataFrame(agg).to_csv(os.path.join(RES, "FULLUNIV_offsets_summary.csv"), index=False)
    ab = []
    for k in (*ro.OFFSETS, "tr"):
        for other in ("B", "B0"):
            lo, hi, pt = r11.paired_real(rets[("A", k)], rets[(other, k)], WM[("A", k, "full")]["rfm"], "r")
            ab.append({"offset": k, "vs": other, "A": WM[("A", k, "full")]["sharpe"], "other": WM[(other, k, "full")]["sharpe"], "d_sharpe": pt, "ci_lo": lo, "ci_hi": hi,
                       "d_cagr": WM[("A", k, "full")]["cagr"] - WM[(other, k, "full")]["cagr"]})
    # ค่าเฉลี่ย 3 offset ของ A − B (ไม่ใช่ paired CI)
    pd.DataFrame(ab).to_csv(os.path.join(RES, "FULLUNIV_offsets_AminusB.csv"), index=False)
    mo = pd.DataFrame({f"{m}_off{k}": rets[(m, k)] for m in MODS3 for k in (*ro.OFFSETS, "tr")})
    mo["rf_month"] = WM[("A", 0, "full")]["rfm"]
    mo.to_csv(os.path.join(RES, "FULLUNIV_offsets_monthly_returns.csv"))

    # ---------- (5) CAGR ก่อน/หลังค่าธรรมเนียม + ปีปฏิทิน tranche ของ A (และ B เทียบ) ----------
    cg = []
    for m in ("A", "B"):
        for k in (*ro.OFFSETS, "tr"):
            f_, c_ = WM[(m, k, "full")], WM[(m, k, "c0")]
            cg.append({"model": m, "offset": k, "window": "common 2022-07..2025-12 (42m)", "cagr_before_fee": c_["cagr"], "cagr_after_fee": f_["cagr"],
                       "fee_drag_pt": (c_["cagr"] - f_["cagr"]) * 100.0, "sharpe_before": c_["sharpe"], "sharpe_after": f_["sharpe"]})
            if k != "tr":
                oc, of = orig[(m, k, "c0")], orig[(m, k, "full")]
                cg.append({"model": m, "offset": k, "window": f"own full range ({of['n_months']}m from entry)", "cagr_before_fee": oc["cagr"], "cagr_after_fee": of["cagr"],
                           "fee_drag_pt": (oc["cagr"] - of["cagr"]) * 100.0, "sharpe_before": oc["sharpe"], "sharpe_after": of["sharpe"]})
    CG = pd.DataFrame(cg)
    CG.to_csv(os.path.join(RES, "FULLUNIV_cagr_before_after.csv"), index=False)
    yr = {}
    for m in ("A", "B"):
        for lab, kind in (("after", "full"), ("before", "c0")):
            for k in (*ro.OFFSETS, "tr"):
                r = WM[(m, k, kind)]["r"]
                yr[f"{m}_off{k}_{lab}"] = (1 + r).groupby(r.index.year).prod() - 1
    YR = pd.DataFrame(yr)
    YR.to_csv(os.path.join(RES, "FULLUNIV_calendar_year.csv"))

    # ---------- (4) ค่าธรรมเนียม 4 กรณี A/B offset 0 ----------
    f_codes = sorted(FD.profile.index[FD.profile["Fund Policy"] == "F"])
    fd_a_f, fd_r_f = fees.FeeData(f_codes), rf.FeeDataRate(f_codes)
    fd_r_e = rf.FeeDataRate(E0["codes"])
    pm = {"A": plans[0]["M015-FAUM"], "B": plans[0]["Trend25"]}
    res = rf.run_cases(E0, FD, pm, E0["fd_sim"], fd_a_f, fd_r_e, fd_r_f, models=("A", "B"))
    frows = []
    for (case, m), s in res.items():
        mo_ = rr.metrics(s["values"], real)
        rn, rfm = mo_["r"], mo_["rfm"]
        frows.append({"case": case, "model": m, "sharpe": mo_["sharpe"], "cagr": mo_["cagr"], "vol": mo_["vol"], "max_dd": mo_["max_dd"],
                      "cost_pct_yr": s["cost_bp_yr"] / 100.0, "turn_yr": s["turn_yr"], "n_cannot_buy": s["n_cannot_buy"], "n_months": mo_["n_months"]})
        res[(case, m)]["_r"] = (rn, rfm)
    FE = pd.DataFrame(frows)
    FE.to_csv(os.path.join(RES, "FULLUNIV_fees.csv"), index=False)
    fab = []
    for case in [c[0] for c in rf.CASES]:
        lo, hi, pt = r11.paired_real(res[(case, "A")]["_r"][0], res[(case, "B")]["_r"][0], res[(case, "A")]["_r"][1], "r")
        fab.append({"case": case, "A_minus_B": pt, "ci_lo": lo, "ci_hi": hi})
    pd.DataFrame(fab).to_csv(os.path.join(RES, "FULLUNIV_fees_AminusB.csv"), index=False)
    # Actual ต้องตรงกับ (2)
    assert abs(FE[(FE["case"] == "ก_Actual") & (FE["model"] == "A")]["sharpe"].iloc[0] - MB["M015-FAUM"]["full"]["sharpe"]) < 1e-12
    assert abs(FE[(FE["case"] == "ก_Actual") & (FE["model"] == "B")]["sharpe"].iloc[0] - MB["Trend25"]["full"]["sharpe"]) < 1e-12

    # ---------- น้ำหนัก/กองที่เลือก + diagnostics ----------
    wr, sel = [], []
    for k in ro.OFFSETS:
        for m in MODS3:
            for en in sims[k][key[m]]["full"]["entries"]:
                for f, w in en["target"].items():
                    if w > 1e-12:
                        wr.append({"model": m, "offset": k, "t": en["t"].date(), "e": en["e"].date(), "FundCode": f, "weight": w})
    pd.DataFrame(wr).to_csv(os.path.join(RES, "FULLUNIV_weights.csv"), index=False)
    # A offset 0: กอง F ที่ถูกเลือกต่อไตรมาส + class ใหม่ที่หลุดเข้ามาเพราะไม่ตัดขั้นต่ำ + เทียบ snapshot รายย่อยเดิม
    new_f = set(FD.snap) - set(FD.snap_retail)
    for k in ro.OFFSETS:
        for qi, p in enumerate(plans[k]["M015-FAUM"]):
            for f, w in p["weights"].items():
                if f in set(FD.codes) or f == "__CASH__":
                    sel.append({"offset": k, "qi": qi, "t": p["t"].date(), "FundCode": f, "weight": w, "risk": FD.risk.get(f), "amc": FD.amc.get(f),
                                "fst_lowbuy_val": FD.profile["fst_lowbuy_val"].get(f), "is_new_vs_retail_snap": f in new_f})
    pd.DataFrame(sel).to_csv(os.path.join(RES, "FULLUNIV_A_F_funds.csv"), index=False)
    # เทียบแผน: full vs retail (offset 0) — กองหุ้นต่างกันกี่ไตรมาส
    pk = pickle.load(open(os.path.join(SCRATCH, "validator_retail_plans.pkl"), "rb"))
    drows = []
    for n in ("Trend25", "M011-RFH", "M012-QF-S", "M013-GC75"):
        a, b = rru.fund_sets(pk["plans_full"][n]), rru.fund_sets(plans[0][n])
        assert a == b, f"plan เต็ม {n} ไม่ตรงกับ plan เต็มรอบ retail"
        drows.append({"model": n, "n_q_full_plan_equals_prior_full_plan": len(a)})
    print("plan full == prior full plan:", drows, flush=True)
    diag = {"fallback_cash_quarters_off": {k: extra[k]["fb_q"] for k in ro.OFFSETS}, "new_F_classes_vs_retail_snapshot": sorted(new_f),
            "n_F_snap_full": len(FD.snap), "n_F_snap_retail": len(FD.snap_retail), "no_lookahead_F": {"max_d": mxd, "n_mis": nmis}}
    json.dump(diag, open(os.path.join(SCRATCH, "validator_full_diag.json"), "w"), default=str)
    pickle.dump({"plans": {k: plans[k] for k in ro.OFFSETS},
                 "values": {(k, m, kind): sims[k][m][kind]["values"] for k in ro.OFFSETS for m in sims[k] for kind in ("full", "nofront", "c0")}},
                open(os.path.join(SCRATCH, "validator_full_out.pkl"), "wb"))
    pd.set_option("display.width", 250)
    print(T.round(4).to_string())
    print(pd.DataFrame(pr).round(4).to_string())
    print(OF.round(4).to_string())
    print(pd.DataFrame(agg).round(4).to_string())
    print(pd.DataFrame(ab).round(4).to_string())
    print(FE.round(4).to_string())
    print(pd.DataFrame(fab).round(4).to_string())
    print(CG.round(4).to_string())
    print(YR.round(4).to_string())
    print(pd.DataFrame(sel).to_string())
    print(f"DONE {time.time()-t0:.0f}s", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
