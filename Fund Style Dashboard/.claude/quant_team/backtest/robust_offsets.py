"""robust_offsets.py — ตรวจความทนทาน 1: เลื่อนเดือน rebalance (offset 0/1/2) ของโมเดลที่ล็อก (2026-10-06 · backtest-validator)
**ไม่ใช่ trial** (ไม่แตะ trials.csv / ALL_RESULTS) · ไม่แก้ไฟล์เดิมใน backtest/ · reuse rerun_retail_universe / run_m009/11/12/13/15 / remeasure_real_rf / fees / simulate

A = M015-FAUM (M013-GC75 + เงินสดเป็นกองตลาดเงิน AUM ใหญ่สุด) บน universe รายย่อย · B = Trend 25 (M004-TF-FX) บน universe รายย่อย · อ้างอิง B0
offset k = เลื่อนเดือนตัดสินใจจาก (มี.ค./มิ.ย./ก.ย./ธ.ค.) ไปอีก k เดือน (ไตรมาสเท่าเดิม) -> t = วันทำการสุดท้ายของเดือนนั้นในปฏิทินดัชนี
สัญญาณ/risk model/เกณฑ์ทั้งหมด คำนวณใหม่ ณ t ใหม่ด้วยโค้ดเดิม (r9.prepare / r11 / r12 / r13 / r15 ไม่ถูกแก้) · ใช้ NAV <= t เท่านั้น (โค้ดเดิม)
ช่วงวัดผลร่วม: ฐาน = ค่าพอร์ตสิ้นเดือน 2022-06-30 (ทุก offset ลงทุนแล้ว) -> ผลตอบแทนรายเดือน ก.ค. 2022 .. ธ.ค. 2025 (42 เดือน) เท่ากันทุก offset
regression: offset 0 บนช่วงวัดผลเดิม (include_start, 45 เดือน) ต้องได้ A 0.765 (= M015_results.csv FAUM) และ B 0.6235 (= RETAIL_results.csv) ก่อนรันอื่น

รัน: PYTHONPATH=. ./.venv/bin/python .claude/quant_team/backtest/robust_offsets.py
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
import fund_signals as fs
import simulate
import run_m009 as r9
import run_m011 as r11
import run_m012 as r12
import run_m015 as r15
import remeasure_real_rf as rr
import rerun_retail_universe as rru
from data import msci_index

TEAM_DIR = os.path.dirname(THIS_DIR)
SCRATCH = os.path.join(TEAM_DIR, "scratch")
RES = common.RESULTS_DIR
WIN_START = pd.Timestamp("2022-06-30")           # ฐานของช่วงวัดผลร่วม
OFFSETS = (0, 1, 2)
MODELS = ("A", "B", "B0")                         # A = M015-FAUM · B = Trend25 (M004-TF-FX) · B0 = ถือเท่ากันทุกกอง
LABEL = {"A": "A  M015-FAUM", "B": "B  Trend 25", "B0": "B0 ถือเท่ากัน"}


# ---------------- ปฏิทินเดือนตัดสินใจ ----------------
def month_end_map(cal: pd.DatetimeIndex) -> dict:
    s = pd.Series(cal, index=cal)
    g = s.groupby([cal.year, cal.month]).max()
    return {(int(y), int(m)): pd.Timestamp(v) for (y, m), v in g.items()}


def shifted_q16(cal: pd.DatetimeIndex, offset: int) -> list:
    base = common.quarter_ends(cal, "2022-03-31", "2025-12-31")
    mm = month_end_map(cal)
    out = []
    for t in base:
        k = t.year * 12 + (t.month - 1) + offset
        out.append(mm[(k // 12, k % 12 + 1)])
    if offset == 0:
        assert out == base
    return out


# ---------------- env (สำเนาของ rru.setup_env ที่เลื่อน q16 ได้) ----------------
def setup_env_off(offset: int, cut_set, ctx_pickle: str | None = None):
    E = {"offset": offset}
    nav = common.load_nav()
    E["nav"], E["nav_by_fund"], E["calendar"] = nav, common.build_nav_by_fund(nav), common.load_calendar()
    E["groups"] = common.load_groups()
    E["acwi"] = msci_index.load_country_index()["MSCI_ACWI"]
    E["codes"] = sorted(nav["FundCode"].unique())
    q16 = shifted_q16(E["calendar"], offset)
    assert len(q16) == 16 and all(b > a for a, b in zip(q16, q16[1:]))
    E["q16"], E["q15"] = q16, q16[:15]
    months = [m for m in common.month_ends(E["calendar"], common.execution_date(E["calendar"], E["q15"][0]), "2026-03-31") if m <= rr.PE]
    assert months[-1] == rr.PE, months[-1]
    E["months"] = months
    E["fd_sim"] = fees.FeeData(E["codes"])
    E["fd_dec"] = fees.FeeData(E["codes"])
    real, _ = rr.load_policy()
    E["real"], E["rate"] = real, real.rate
    ctx_pickle = ctx_pickle or os.path.join(SCRATCH, f"validator_robust_ctxs_off{offset}.pkl")
    if os.path.exists(ctx_pickle):
        ctxs = pickle.load(open(ctx_pickle, "rb"))
        assert [c["t"] for c in ctxs] == q16, "ctx pickle ไม่ตรงวันตัดสินใจ"
    else:
        with rru.retail_universe(cut_set):
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


# ---------------- plans ----------------
def build_all_plans(E, FD):
    """-> {'A','B','B0'} plan + ข้อมูลประกอบ (ไม่ผ่านการ sim)"""
    P = rru.build_plans(E)                           # B0, Trend25, M011, M012, M013-GC75 (โค้ดเดิม)
    base = P["M013-GC75"]
    rows = r15.f_rows(FD, E, E["h_by_q"])
    sels = r15.f_selections(FD, rows)
    fset_all = set(FD.codes)
    plan_a, fb_q = r15.make_plan_F(base, sels["FAUM"])
    mx = r15.plan_checks(plan_a, base, fset_all)
    for qi, p in enumerate(plan_a):                  # กอง F ที่เลือกอยู่ใน I_t^F ผ่านเกณฑ์ และไม่ใช่กองหุ้น
        for f in p["weights"]:
            if f in fset_all:
                assert f in set(rows[qi]["it"]["FundCode"]) and f in FD.snap and f not in E["nav_by_fund"]
    return {"A": plan_a, "B": P["Trend25"], "B0": P["B0"], "base_GC75": base}, {"fb_q": fb_q, "max_dw_stock": mx, "sels": sels}


def make_fee_ctx(E, FD, fd_e=None, fd_f=None):
    """(nav_all, fd_comb, fset_all) — ค่าเริ่มต้น = FeeData Actual ทั้งสองฝั่ง (เหมือน M015)."""
    f_codes = sorted(FD.profile.index[FD.profile["Fund Policy"] == "F"])
    fd_f = fd_f or fees.FeeData(f_codes)
    fd_e = fd_e or E["fd_sim"]
    nav_all = {**E["nav_by_fund"], **FD.nav_by_fund}
    return nav_all, r15.CombinedFee(fd_e, fd_f, f_codes), set(FD.codes)


def sims_for(model, plan, E, FD, kinds, fd_e=None, fd_f=None, log_full=False):
    """simulate ผ่าน r15.sim_cases_x (rf จริงผ่าน cash_curve) · A ใช้กอง F + CombinedFee, B/B0 ใช้ FeeData ปกติ."""
    if model == "A":
        nav_all, fd_comb, fset = make_fee_ctx(E, FD, fd_e, fd_f)
        return r15.sim_cases_x(plan, nav_all, E["months"], fd_comb, E["real"], fset=fset, kinds=kinds, log_full=log_full)
    return r15.sim_cases_x(plan, E["nav_by_fund"], E["months"], fd_e or E["fd_sim"], E["real"], fset=(), kinds=kinds, log_full=log_full)


# ---------------- metrics ----------------
def win_metrics(values: pd.Series, real, start=WIN_START) -> dict:
    """metrics บนช่วงร่วม: ฐาน = ค่าพอร์ต ณ start (ต้องมีใน index) -> ผลตอบแทนรายเดือนถัดไปถึง PE · rf รายเดือนจริงตามช่วง."""
    v = values[(values.index >= start) & (values.index <= rr.PE)]
    assert v.index[0] == start, (v.index[0], start)
    r = simulate.monthly_returns(v)
    rfm = real.rf_monthly(v.index)

    def sub(a, b):
        m = (r.index >= a) & (r.index <= b)
        return rr.sharpe_s(r[m], rfm.reindex(r.index)[m]) if m.sum() >= 3 else np.nan
    return {"sharpe": rr.sharpe_s(r, rfm), "cagr": simulate.cagr(v), "vol": simulate.ann_vol(r), "max_dd": simulate.max_drawdown(v),
            "n_months": len(r), "sharpe_2022h2": sub("2022-07-01", "2022-12-31"), "sharpe_2307_2512": sub("2023-07-01", "2025-12-31"),
            "r": r, "rfm": rfm, "v": v}


def tranche_values(vals: list, start=WIN_START) -> pd.Series:
    """ถือ 1/3 ต่อ offset (buy&hold จากฐาน start): ค่าเฉลี่ยของค่าพอร์ตที่ปรับฐาน = 100 ณ start."""
    norm = []
    for v in vals:
        s = v[(v.index >= start) & (v.index <= rr.PE)]
        assert s.index[0] == start
        norm.append(s / s.iloc[0] * 100.0)
    df = pd.concat(norm, axis=1)
    assert df.notna().all().all()
    return df.mean(axis=1)


def orig_metrics(values, real):
    return rr.metrics(values, real)


# ---------------- main ----------------
def main():
    t0 = time.time()
    nav = common.load_nav()
    codes = sorted(nav["FundCode"].unique())
    groups = common.load_groups()
    tab = rru.retail_table(codes, groups)
    cut = set(tab.loc[tab["cut"], "FundCode"])
    print(f"[setup] retail cut {len(cut)} classes", flush=True)
    os.makedirs(SCRATCH, exist_ok=True)

    envs, plans, extra, sims = {}, {}, {}, {}
    FD = None
    for k in OFFSETS:
        pk = os.path.join(SCRATCH, "validator_retail_ctxs.pkl") if k == 0 else None      # offset 0 = ctx รอบ retail เดิม (เทียบกับ regression)
        E = setup_env_off(k, cut, pk)
        if FD is None:
            FD = r15.FData(r15.load_profile(), E)
        envs[k] = E
        leaked = {fc for c in E["ctxs"] for fc in c["i_t"]["FundCode"]} & cut
        assert not leaked
        print(f"[off{k}] env ready · t0={E['q15'][0].date()} .. t14={E['q15'][-1].date()} · e0={E['ctxs'][0]['e'].date()} ({time.time()-t0:.0f}s)", flush=True)
        plans[k], extra[k] = build_all_plans(E, FD)
        print(f"[off{k}] plans ready · A fallback quarters {extra[k]['fb_q']} · max|dw| stock part {extra[k]['max_dw_stock']:.1e} ({time.time()-t0:.0f}s)", flush=True)
        sims[k] = {}
        for m in MODELS:
            sims[k][m] = sims_for(m, plans[k][m], E, FD, ["full", "nofront", "c0"])
        print(f"[off{k}] sims done ({time.time()-t0:.0f}s)", flush=True)

    real = envs[0]["real"]
    # ---------- (A) regression: offset 0 บนช่วงเดิม ----------
    ref_a = float(pd.read_csv(os.path.join(RES, "M015_results.csv")).set_index("model").loc["M015-FAUM", "sharpe_full"])
    ref_r = pd.read_csv(os.path.join(RES, "RETAIL_results.csv")).set_index("model")
    ref = {"A": ref_a, "B": float(ref_r.loc["Trend25", "new_sharpe_full"]), "B0": float(ref_r.loc["B0", "new_sharpe_full"])}
    reg = {}
    for m in MODELS:
        got = orig_metrics(sims[0][m]["full"]["values"], real)
        reg[m] = {"sharpe_off0_orig_window": got["sharpe"], "ref": ref[m], "abs_diff": abs(got["sharpe"] - ref[m]), "n_months": got["n_months"],
                  "cagr": got["cagr"], "max_dd": got["max_dd"]}
    reg["ok"] = bool(all(reg[m]["abs_diff"] < 5e-7 for m in MODELS) and abs(round(reg["A"]["sharpe_off0_orig_window"], 3) - 0.765) < 1e-9
                     and abs(round(reg["B"]["sharpe_off0_orig_window"], 3) - 0.624) < 1e-9)
    print("REGRESSION:", json.dumps(reg, default=float), flush=True)
    json.dump(reg, open(os.path.join(SCRATCH, "validator_robust_regression.json"), "w"), default=float)
    if not reg["ok"]:
        print("REGRESSION FAIL — หยุด", flush=True)
        return 2

    # ---------- (B) ผลช่วงร่วม ----------
    rows, rets = [], {}
    WM = {}                                   # (model, offset|'tr', kind) -> metrics
    for m in MODELS:
        for kind in ("full", "nofront", "c0"):
            vs = [sims[k][m][kind]["values"] for k in OFFSETS]
            for k, v in zip(OFFSETS, vs):
                WM[(m, k, kind)] = win_metrics(v, real)
            WM[(m, "tr", kind)] = win_metrics(tranche_values(vs), real)
    for m in MODELS:
        for k in (*OFFSETS, "tr"):
            w = WM[(m, k, "full")]
            o = {"model": m, "offset": k, "sharpe": w["sharpe"], "cagr": w["cagr"], "vol": w["vol"], "max_dd": w["max_dd"], "n_months": w["n_months"],
                 "sharpe_2022h2": w["sharpe_2022h2"], "sharpe_2307_2512": w["sharpe_2307_2512"],
                 "sharpe_nofront": WM[(m, k, "nofront")]["sharpe"], "sharpe_c0": WM[(m, k, "c0")]["sharpe"]}
            if k != "tr":
                s = sims[k][m]["full"]
                o.update({"cost_bp_yr": s["cost_bp_yr"], "turn_yr": s["turn_yr"], "n_cannot_buy": s["n_cannot_buy"]})
                o0 = orig_metrics(s["values"], real)
                o.update({"sharpe_origwin": o0["sharpe"], "cagr_origwin": o0["cagr"], "maxdd_origwin": o0["max_dd"], "n_months_origwin": o0["n_months"]})
            rows.append(o)
            rets[(m, k)] = w["r"]
    S = pd.DataFrame(rows)
    S.to_csv(os.path.join(RES, "ROBUST_offsets.csv"), index=False)

    # สถิติข้าม offset ต่อโมเดล
    agg = []
    for m in MODELS:
        d = S[(S["model"] == m) & (S["offset"] != "tr")]
        tr = S[(S["model"] == m) & (S["offset"] == "tr")].iloc[0]
        agg.append({"model": m, "sharpe_mean": d["sharpe"].mean(), "sharpe_min": d["sharpe"].min(), "sharpe_max": d["sharpe"].max(),
                    "sharpe_range": d["sharpe"].max() - d["sharpe"].min(), "sharpe_tranche": tr["sharpe"],
                    "cagr_mean": d["cagr"].mean(), "cagr_min": d["cagr"].min(), "cagr_max": d["cagr"].max(),
                    "maxdd_mean": d["max_dd"].mean(), "maxdd_worst": d["max_dd"].min(), "tranche_cagr": tr["cagr"], "tranche_maxdd": tr["max_dd"], "tranche_vol": tr["vol"]})
    AG = pd.DataFrame(agg)
    AG.to_csv(os.path.join(RES, "ROBUST_offsets_summary.csv"), index=False)

    # A − B ต่อ offset (paired bootstrap ช่วงร่วม · block 3 · seed 0 · rf จริง · ตัวหาร sd(r))
    ab = []
    for k in (*OFFSETS, "tr"):
        for other in ("B", "B0"):
            ra, rb = rets[("A", k)], rets[(other, k)]
            rfm = WM[("A", k, "full")]["rfm"]
            lo, hi, pt = r11.paired_real(ra, rb, rfm, "r")
            ab.append({"offset": k, "vs": other, "A": WM[("A", k, "full")]["sharpe"], "other": WM[(other, k, "full")]["sharpe"], "d_sharpe": pt, "ci_lo": lo, "ci_hi": hi,
                       "d_sharpe_c0": WM[("A", k, "c0")]["sharpe"] - WM[(other, k, "c0")]["sharpe"],
                       "d_sharpe_nofront": WM[("A", k, "nofront")]["sharpe"] - WM[(other, k, "nofront")]["sharpe"]})
    AB = pd.DataFrame(ab)
    AB.to_csv(os.path.join(RES, "ROBUST_offsets_AminusB.csv"), index=False)

    # รายเดือน + น้ำหนัก
    mo = pd.DataFrame({f"{m}_off{k}": rets[(m, k)] for m in MODELS for k in (*OFFSETS, "tr")})
    mo["rf_month"] = WM[("A", 0, "full")]["rfm"]
    mo.to_csv(os.path.join(RES, "ROBUST_offsets_monthly_returns.csv"))
    wr = []
    for k in OFFSETS:
        for m in MODELS:
            for en in sims[k][m]["full"]["entries"]:
                for f, w in en["target"].items():
                    if w > 1e-12:
                        wr.append({"model": m, "offset": k, "t": en["t"].date(), "e": en["e"].date(), "FundCode": f, "weight": w})
    pd.DataFrame(wr).to_csv(os.path.join(RES, "ROBUST_offsets_weights.csv"), index=False)

    # diagnostics: ความต่างของชุดกอง/เงินสดข้ามเดือน (A) + ผลต่อปีแบบ calendar
    diag = []
    for k in OFFSETS:
        pl = plans[k]["A"]
        xs = [r15.x_of(p) for p in plans[k]["base_GC75"]]       # สัดส่วนขาหุ้น (1 - เงินสด/F) ของ M013-GC75 ก่อนแทนด้วยกอง F
        n_st = [len([f for f in p["weights"] if f not in FD.codes and f != "__CASH__"]) for p in pl]
        n_f = [len([f for f in p["weights"] if f in FD.codes]) for p in pl]
        diag.append({"offset": k, "mean_stock_x": float(np.mean(xs)), "mean_n_stock_funds": float(np.mean(n_st)), "quarters_with_F_leg": int(sum(1 for n in n_f if n > 0)),
                     "A_fallback_cash_quarters": len(extra[k]["fb_q"]), "A_turn_yr": sims[k]["A"]["full"]["turn_yr"], "A_cost_bp_yr": sims[k]["A"]["full"]["cost_bp_yr"],
                     "B_turn_yr": sims[k]["B"]["full"]["turn_yr"], "B_cost_bp_yr": sims[k]["B"]["full"]["cost_bp_yr"]})
    DG = pd.DataFrame(diag)
    DG.to_csv(os.path.join(RES, "ROBUST_offsets_diag.csv"), index=False)
    # ปีปฏิทินของ tranche A/B (ผลตอบแทนรายปี)
    yr = {}
    for m in ("A", "B"):
        for k in (*OFFSETS, "tr"):
            r = rets[(m, k)]
            yr[f"{m}_off{k}"] = (1 + r).groupby(r.index.year).prod() - 1
    YR = pd.DataFrame(yr)
    YR.to_csv(os.path.join(RES, "ROBUST_offsets_calendar_year.csv"))

    pickle.dump({"sims_values": {(k, m, kind): sims[k][m][kind]["values"] for k in OFFSETS for m in MODELS for kind in ("full", "nofront", "c0")},
                 "plans": {k: {m: plans[k][m] for m in MODELS} for k in OFFSETS}}, open(os.path.join(SCRATCH, "validator_robust_offsets_out.pkl"), "wb"))
    pd.set_option("display.width", 250)
    print(S.round(4).to_string())
    print(AG.round(4).to_string())
    print(AB.round(4).to_string())
    print(DG.round(3).to_string())
    print(YR.round(4).to_string())
    print(f"DONE {time.time()-t0:.0f}s", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
