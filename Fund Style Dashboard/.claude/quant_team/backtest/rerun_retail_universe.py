"""rerun_retail_universe.py — งาน 2 (2026-10-06): ตัด share class ที่รายย่อยซื้อไม่ได้ออกจาก universe แล้วรันโมเดลหลักซ้ำ
(แก้ความถูกต้อง/เปลี่ยนวิธีวัด — ไม่ใช่ trial ใหม่: ไม่แตะ trials.csv · ไม่แก้ไฟล์ run_m0xx เดิม)

เกณฑ์ตัด class: ขั้นต่ำซื้อครั้งแรก (FundProfile.fst_lowbuy_val) > 100,000 บาท · ข้อมูลขั้นต่ำมีครบทุก class (570/570) จึงไม่ต้องตัดสินด้วยชื่อ
(ชื่อ class ใช้เป็นตัวตรวจประกอบ/รายงานเท่านั้น). ข้อจำกัด: FundProfile เป็น snapshot ปัจจุบัน — ใช้ตัดทุกวัน (ไม่ point-in-time).
วิธีทำ: patch common.universe_at ชั่วคราว (กรอง U_t) -> run_m009.prepare / run_m011 / run_m012 / run_m013 ทำงานบน universe ใหม่ตามเดิม
(family representative เลือกจาก class ที่เหลือเอง; family ที่ไม่มี class รายย่อยหายไปเอง; B0 = 1 class/กลุ่มจาก class ที่เหลือ).
ค่าธรรมเนียม = fees.FeeData (ค่าเริ่มต้นใหม่ = ตรงกับแอป) · วัดด้วย rf จริง (policy rate) เหมือน M011–M013.

รัน: PYTHONPATH=. ./.venv/bin/python .claude/quant_team/backtest/rerun_retail_universe.py
ขั้นตอน: (A) regression — universe เต็ม + fees ใหม่ ต้องได้ตัวเลขเดิม (B0 = 0.059449 ที่ rf 2% · Trend 25 = 0.706119/0.720494/0.893296)
         (B) retail universe -> ผล + diff ไตรมาส -> results/RETAIL_*.csv + scratch/validator_retail_plans.pkl (ใช้ต่อใน sens_settlement)"""
from __future__ import annotations

import contextlib
import json
import os
import pickle
import re
import sys
import time

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
import run_m013 as r13
import remeasure_real_rf as rr
from data import msci_index

TEAM_DIR = os.path.dirname(THIS_DIR)
SCRATCH = os.path.join(TEAM_DIR, "scratch")
RES = common.RESULTS_DIR
MIN_BUY_CUT = 100_000.0
KINDS = ["c0", "c50", "flat", "full", "nofront"]
INST_RE = re.compile(r"^(I|IA|ID|IR|IP|IN|INS|INST|INSTI|IX|X|XA|XD|P|PP|C)$")      # ชื่อ class แนวสถาบัน/พิเศษ (ตรวจประกอบเท่านั้น)


# ---------------- ตาราง class รายย่อย ----------------
def retail_table(codes, groups) -> pd.DataFrame:
    p = pd.read_csv(os.path.join(common.PROJECT_ROOT, "base_data", "FundProfile.csv"), dtype=str, encoding="utf-8-sig")
    p.columns = [c.strip() for c in p.columns]
    p = p.drop_duplicates("Fund Code").set_index("Fund Code")
    rows = []
    for fc in codes:
        r = p.loc[fc] if fc in p.index else None
        fb = pd.to_numeric(r["fst_lowbuy_val"], errors="coerce") if r is not None else np.nan
        nb = pd.to_numeric(r["nxt_lowbuy_val"], errors="coerce") if r is not None else np.nan
        toks = [x for x in re.split(r"[-\s]+", fc) if x]
        suf = toks[-2] if (toks and toks[-1] == "F" and len(toks) > 1) else (toks[-1] if toks else "")
        name_inst = bool(INST_RE.match(suf))
        fam = fs.family_of(fc, groups, True)[0]
        if pd.notna(fb):
            cut, basis = bool(fb > MIN_BUY_CUT), "fst_lowbuy_val"
            reason = f"ขั้นต่ำซื้อครั้งแรก {fb:,.0f} บาท" + (" > 100,000" if cut else " <= 100,000")
        else:
            cut, basis = bool(name_inst and suf in ("I", "IA", "ID", "IR", "INST", "INSTI", "IN", "INS", "IP")), "ชื่อ class (ไม่มีข้อมูลขั้นต่ำ)"
            reason = f"ไม่มีข้อมูลขั้นต่ำ ใช้ชื่อ class '{suf}'"
        rows.append({"FundCode": fc, "family": fam, "amc": r["AMC_CODE"] if r is not None else "", "fst_lowbuy_val": fb, "nxt_lowbuy_val": nb,
                     "suffix": suf, "name_inst_like": name_inst, "cut": cut, "basis": basis, "reason": reason})
    d = pd.DataFrame(rows)
    fam_retail = d[~d["cut"]].groupby("family").size()
    d["family_n_retail_left"] = d["family"].map(fam_retail).fillna(0).astype(int)
    d["family_dropped"] = d["cut"] & (d["family_n_retail_left"] == 0)
    return d


@contextlib.contextmanager
def retail_universe(cut_set):
    orig = common.universe_at

    def patched(nav, t):
        u = orig(nav, t)
        return u[~u["FundCode"].isin(cut_set)].reset_index(drop=True)
    common.universe_at = patched
    try:
        yield
    finally:
        common.universe_at = orig


# ---------------- pipeline (ใช้ซ้ำสำหรับ universe เต็ม/รายย่อย) ----------------
def setup_env(ctx_pickle, cut_set):
    E = {}
    nav = common.load_nav()
    E["nav"], E["nav_by_fund"], E["calendar"] = nav, common.build_nav_by_fund(nav), common.load_calendar()
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
    E["fd_sim"] = fees.FeeData(E["codes"])          # ค่าเริ่มต้นใหม่ = แบบแอป
    E["fd_dec"] = fees.FeeData(E["codes"])
    real, _ = rr.load_policy()
    E["real"], E["rate"] = real, real.rate
    if os.path.exists(ctx_pickle):
        ctxs = pickle.load(open(ctx_pickle, "rb"))
    else:
        if cut_set:
            with retail_universe(cut_set):
                ctxs = r9.prepare(nav, E["nav_by_fund"], E["calendar"], E["groups"], q16)
        else:
            ctxs = r9.prepare(nav, E["nav_by_fund"], E["calendar"], E["groups"], q16)
        pickle.dump(ctxs, open(ctx_pickle, "wb"))
    E["ctxs"] = ctxs
    h_by_q = {}
    for ctx in ctxs:
        ms = fs.month_end_points(E["calendar"], ctx["t"], 13)
        h_by_q[ctx["qi"]] = r11.hurdle(E["rate"], ms[0], ms[-2])
    E["h_by_q"] = h_by_q
    E["ctx_h"] = r11.with_hurdle(ctxs, E["calendar"], h_by_q)
    E["ctx_old"] = r11.with_hurdle(ctxs, E["calendar"], {q: r11.H_OLD for q in h_by_q})
    Q = r12.Quality(nav, E["groups"])
    E["quals"] = [Q.table(c["t"])[0] for c in E["ctx_h"]]
    return E


def build_plans(E):
    q15, cal, acwi = E["q15"], E["calendar"], E["acwi"]
    P = {}
    b0 = {c["qi"]: c["b0_w"] for c in E["ctxs"] if c["qi"] < 15}
    P["B0"] = r67.old_style_plan(b0, q15, cal, lambda t: 0.0)
    P["Trend25"], _ = r11.build_plan(E["ctx_old"], q15, cal, acwi, E["fd_dec"], {})
    P["M011-RFH"], _ = r11.build_plan(E["ctx_h"], q15, cal, acwi, E["fd_dec"], {})
    st = r12.stream(E["ctx_h"], E["quals"], "S", {})
    P["M012-QF-S"] = r12.to_plan(st, q15, cal, acwi)
    sleeves15 = {q: v for q, v in st["sleeves"].items() if q < 15}
    sig = r13.gc_signals({**E})
    kmap = dict(zip(sig["t"], sig["k"]))
    P["M013-GC75"], xmap = r13.gc_plan(E, sleeves15, kmap, r13.TABLES["GC75"])
    E["sig"], E["st_m012"] = sig, st
    return P


def run_sims(E, plans):
    out = {}
    for name, plan in plans.items():
        sims_r = r11.sims_real(plan, E["nav_by_fund"], E["months"], E["fd_sim"], E["real"])
        sims_c = r9.sim_cases(plan, E["nav_by_fund"], E["months"], E["fd_sim"])
        MR = {k: rr.metrics(sims_r[k]["values"], E["real"]) for k in KINDS}
        MC = {k: rr.metrics(sims_c[k]["values"], 0.02) for k in KINDS}
        out[name] = {"sims_r": sims_r, "MR": MR, "MC": MC}
    return out


def fund_sets(plan):
    return [frozenset(f for f, w in p["weights"].items() if f != "__CASH__" and w > 1e-12) for p in plan]


def summarize(name, R, E):
    MR, MC = R["MR"], R["MC"]
    rn, rfm = MR["full"]["r"], MR["full"]["rfm"]
    lo, hi = rr.boot_ci(rn, rfm)
    return {"model": name, "sharpe_full": MR["full"]["sharpe"], "sharpe_nofront": MR["nofront"]["sharpe"], "sharpe_c0": MR["c0"]["sharpe"],
            "sharpe_c50": MR["c50"]["sharpe"], "cagr_full": MR["full"]["cagr"], "vol_full": MR["full"]["vol"], "maxdd_full": MR["full"]["max_dd"],
            "sharpe_2022_full": MR["full"]["sharpe_2022"], "sharpe_2307_2512_full": MR["full"]["sharpe_2307_2512"],
            "ci_lo": lo, "ci_hi": hi, "cost_bp_yr_full": R["sims_r"]["full"]["cost_bp_yr"], "turn_yr": R["sims_r"]["full"]["turn_yr"],
            "sharpe_full_rf2": MC["full"]["sharpe"], "sharpe_nofront_rf2": MC["nofront"]["sharpe"], "sharpe_flat_rf2": MC["flat"]["sharpe"]}


def main():
    t0 = time.time()
    nav = common.load_nav()
    codes = sorted(nav["FundCode"].unique())
    groups = common.load_groups()
    tab = retail_table(codes, groups)
    tab.to_csv(os.path.join(RES, "RETAIL_class_table.csv"), index=False)
    cut = set(tab.loc[tab["cut"], "FundCode"])
    print(f"cut classes: {len(cut)}  {sorted(cut)}", flush=True)

    # (A) universe เต็ม + fees ใหม่ = regression
    print("[A] full universe + app fees (regression)", flush=True)
    EF = setup_env(os.path.join(SCRATCH, "validator_m012_ctxs.pkl"), None)          # ctx เต็มจากรอบ M012 (อ่านอย่างเดียว)
    PF = build_plans(EF)
    RF = run_sims(EF, PF)
    SF = {n: summarize(n, RF[n], EF) for n in PF}
    ref_real = pd.read_csv(os.path.join(RES, "REAL_RF_summary.csv")).set_index("trial")
    ref13 = pd.read_csv(os.path.join(RES, "M013_results.csv")).set_index(["trial", "cost"])
    ref11 = pd.read_csv(os.path.join(RES, "M011_results.csv")).set_index(["trial", "cost"])
    ref12 = pd.read_csv(os.path.join(RES, "M012_results.csv")).set_index(["trial", "cost"])
    reg = {
        "B0_full_rf2_app": SF["B0"]["sharpe_full_rf2"], "B0_ref_rf2_app": 0.059449,
        "T25_rf2": {"full": SF["Trend25"]["sharpe_full_rf2"], "flat": SF["Trend25"]["sharpe_flat_rf2"], "nofront": SF["Trend25"]["sharpe_nofront_rf2"]},
        "T25_real_full": SF["Trend25"]["sharpe_full"], "T25_real_ref": float(ref_real.loc["M004-TF-FX", "sharpe_full_real"]),
        "B0_real_full": SF["B0"]["sharpe_full"], "B0_real_ref_legacyfee": float(ref_real.loc["B0", "sharpe_full_real"]),
        "M011_real_full": SF["M011-RFH"]["sharpe_full"], "M011_ref": float(ref11.loc[("M011-RFH", "full"), "sharpe_real"]),
        "M012S_real_full": SF["M012-QF-S"]["sharpe_full"], "M012S_ref": float(ref12.loc[("M012-QF-S", "full"), "sharpe_real"]),
        "M013_real_full": SF["M013-GC75"]["sharpe_full"], "M013_ref": float(ref13.loc[("M013-GC75", "full"), "sharpe_real"]),
    }
    reg["ok_B0"] = bool(abs(round(reg["B0_full_rf2_app"], 6) - 0.059449) < 1.5e-6)
    reg["ok_T25"] = bool(abs(round(reg["T25_rf2"]["full"], 6) - 0.706119) < 1.5e-6 and abs(round(reg["T25_rf2"]["flat"], 6) - 0.720494) < 1.5e-6
                         and abs(round(reg["T25_rf2"]["nofront"], 6) - 0.893296) < 1.5e-6)
    reg["ok_T25_real"] = bool(abs(reg["T25_real_full"] - reg["T25_real_ref"]) < 5e-7)
    reg["ok_models"] = bool(all(abs(reg[a] - reg[b]) < 5e-7 for a, b in (("M011_real_full", "M011_ref"), ("M012S_real_full", "M012S_ref"), ("M013_real_full", "M013_ref"))))
    reg["ok_all"] = bool(reg["ok_B0"] and reg["ok_T25"] and reg["ok_T25_real"] and reg["ok_models"])
    print("REGRESSION:", json.dumps(reg, default=float), flush=True)
    json.dump(reg, open(os.path.join(SCRATCH, "validator_retail_regression.json"), "w"), default=float)
    if not reg["ok_all"]:
        print("REGRESSION FAIL — หยุด", flush=True)
        return 2

    # (B) retail universe
    print("[B] retail universe", flush=True)
    ER = setup_env(os.path.join(SCRATCH, "validator_retail_ctxs.pkl"), cut)
    # ตรวจ: ไม่มี class ที่ถูกตัดหลุดเข้า i_t
    leaked = {fc for c in ER["ctxs"] for fc in c["i_t"]["FundCode"]} & cut
    assert not leaked, leaked
    PR = build_plans(ER)
    RR = run_sims(ER, PR)
    SR = {n: summarize(n, RR[n], ER) for n in PR}
    pickle.dump({"plans_retail": PR, "plans_full": PF, "cut": sorted(cut)}, open(os.path.join(SCRATCH, "validator_retail_plans.pkl"), "wb"))

    # ผลรวม
    rows = []
    for n in PR:
        o, nw = SF[n], SR[n]
        rows.append({"model": n, **{f"old_{k}": v for k, v in o.items() if k != "model"}, **{f"new_{k}": v for k, v in nw.items() if k != "model"}})
    S = pd.DataFrame(rows)
    S.to_csv(os.path.join(RES, "RETAIL_results.csv"), index=False)

    # diff ไตรมาส + class ที่ถูกตัดเคยอยู่ใน universe/พอร์ตเดิมไหม
    drows = []
    for n in PR:
        if n == "B0":
            continue
        a, b = fund_sets(PF[n]), fund_sets(PR[n])
        for qi, (x, y) in enumerate(zip(a, b)):
            drows.append({"model": n, "qi": qi, "t": PF[n][qi]["t"].date(), "changed": x != y, "n_old": len(x), "n_new": len(y),
                          "removed": ";".join(sorted(x - y)), "added": ";".join(sorted(y - x)),
                          "old_held_cut_class": ";".join(sorted(x & cut))})
    D = pd.DataFrame(drows)
    D.to_csv(os.path.join(RES, "RETAIL_quarter_diff.csv"), index=False)
    # B0 universe size ต่อไตรมาส
    urow = []
    for cf, cr in zip(EF["ctxs"], ER["ctxs"]):
        urow.append({"qi": cf["qi"], "t": cf["t"].date(), "U_full": cf["n_u"], "U_retail": cr["n_u"], "I_full": len(cf["i_t"]), "I_retail": len(cr["i_t"]),
                     "B0_n_full": len(cf["b0_w"]), "B0_n_retail": len(cr["b0_w"]),
                     "cut_in_U": ";".join(sorted(set(common.universe_at(nav, cf["t"])["FundCode"]) & cut))})
    pd.DataFrame(urow).to_csv(os.path.join(RES, "RETAIL_universe_by_quarter.csv"), index=False)
    # paired Δ (retail − full) ต่อโมเดล · rf จริง
    prow = []
    for n in PR:
        ra, rb = RR[n]["MR"]["full"]["r"], RF[n]["MR"]["full"]["r"]
        rfm = RR[n]["MR"]["full"]["rfm"]
        lo, hi, pt = r11.paired_real(ra, rb, rfm, "r")
        prow.append({"model": n, "d_sharpe_full": pt, "ci_lo": lo, "ci_hi": hi})
    pd.DataFrame(prow).to_csv(os.path.join(RES, "RETAIL_paired.csv"), index=False)
    # น้ำหนัก retail
    wr = []
    for n in PR:
        if n == "B0":
            continue
        for en in RR[n]["sims_r"]["full"]["entries"]:
            for f, w in en["target"].items():
                if w > 1e-12:
                    wr.append({"model": n, "t": en["t"].date(), "e": en["e"].date(), "FundCode": f, "weight": w})
    pd.DataFrame(wr).to_csv(os.path.join(RES, "RETAIL_weights.csv"), index=False)
    # สรุปให้อ่าน
    pd.set_option("display.width", 250)
    print(S[["model", "old_sharpe_full", "new_sharpe_full", "old_sharpe_nofront", "new_sharpe_nofront", "old_sharpe_c0", "new_sharpe_c0",
             "old_cagr_full", "new_cagr_full"]].round(4).to_string())
    print(D.groupby("model")["changed"].agg(["sum", "count"]))
    print(f"DONE {time.time()-t0:.0f}s", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
