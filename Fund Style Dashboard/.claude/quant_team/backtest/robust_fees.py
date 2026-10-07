"""robust_fees.py — ตรวจความทนทาน 2: สถานการณ์ค่าธรรมเนียม บน A (M015-FAUM) และ B (Trend 25) · อ้างอิง B0 (2026-10-06 · backtest-validator)
**ไม่ใช่ trial** (ไม่แตะ trials.csv / ALL_RESULTS) · ไม่แก้ fees.py / ไฟล์เดิม — เพิ่มโหมด 'Rate' ที่นี่ (FeeDataRate = fees.FeeData ที่อ่านคอลัมน์ Rate แทน Actual Value)

กรณี (ใช้ plan เดิมของแต่ละ offset ไม่เลือกกองใหม่; เปลี่ยนเฉพาะต้นทุนตอนซื้อขาย):
 (ก) Actual (หลัก) = FeeData(legacy=False) FEEUH 'Actual Value' ทั้งขากองหุ้นและขากอง F · FeeModel full
 (ข) Rate = เพดานหนังสือชี้ชวน (คอลัมน์ Rate; schema: Rate = เพดาน, Actual Value = อัตราเก็บจริง ตาม results/AUDIT_fees.md) · กฎ parse เดียวกับ Actual
     ('ไม่มี/ยกเว้น/ไม่เรียกเก็บ' = 0 · ค่าอ่านไม่ได้/ติดลบ/>10 -> median ของ Rate ต่อรหัส) · FeeModel full ทั้งขากองหุ้นและขา F
 (ค) ยกเว้น front-end = FF=SI=0 (FeeModel 'nofront' บน Actual)
 (ง) 0% = ไม่หักค่าธรรมเนียม (c0)
ผลหลักที่ offset 0 บนช่วงวัดผลเดิม (45 เดือน, include_start) · ถ้าเวลาพอ: (ข),(ค) ที่ offset 1-2 ด้วย (ช่วงวัดผลร่วม 42 เดือน เหมือน robust_offsets)
regression: (ก) offset 0 ต้อง = A 0.765 / B 0.6235 (ผ่าน robust_offsets pipeline) · (ข) Rate บน B universe เต็มเทียบ AUDIT 0.308 ไม่ทำ (universe ต่าง) — รายงานเป็นข้อสังเกต

รัน (หลัง robust_offsets.py): PYTHONPATH=. ./.venv/bin/python .claude/quant_team/backtest/robust_fees.py
"""
from __future__ import annotations

import json
import os
import pickle
import sys
import time
from collections import defaultdict

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
import run_m015 as r15
import rerun_retail_universe as rru
import robust_offsets as ro

RES = common.RESULTS_DIR
SCRATCH = ro.SCRATCH


class FeeDataRate(fees.FeeData):
    """เหมือน fees.FeeData(legacy=False) ทุกบรรทัด ยกเว้นอ่านคอลัมน์ 'Rate' (เพดาน) แทน 'Actual Value' (ไม่แก้ fees.py)."""
    def __init__(self, fund_codes, value_col: str = "Rate"):
        self.legacy = False
        self.value_col = value_col
        root = common.PROJECT_ROOT
        d = pd.read_csv(os.path.join(root, "base_data", "SecFundFee.csv"), dtype=str, encoding="utf-8-sig")
        d = d[(d["Complex Type Code"] == "FEEUH") & d["Code"].isin(fees.CODES) & d["Fund Code"].isin(set(fund_codes))].copy()
        d["date"] = pd.to_datetime(d["As of Date"], format="%Y%m%d")
        d["v"] = fees.parse_fee_value(d[value_col])
        d.loc[(d["v"] < 0) | (d["v"] > fees.MAX_PCT), "v"] = np.nan
        self.n_rows, self.n_invalid = len(d), int(d["v"].isna().sum())
        self.series = {}
        d = d.sort_values(["date", "v"], kind="mergesort", na_position="first")
        for (fc, code), g in d.groupby(["Fund Code", "Code"]):
            self.series[(fc, code)] = (g["date"].to_numpy(), g["v"].to_numpy())
        last = d.groupby(["Fund Code", "Code"]).tail(1)
        self.median = {c: float(last[(last["Code"] == c)]["v"].median()) for c in fees.CODES}
        for c in fees.CODES:
            if not np.isfinite(self.median[c]):
                self.median[c] = 0.5
        self.n_funds_fee = d["Fund Code"].nunique()
        prof = pd.read_csv(os.path.join(root, "base_data", "FundProfile.csv"), dtype=str)
        self.amc = dict(zip(prof["Fund Code"], prof["AMC_CODE"]))
        self.n_fallback = defaultdict(int)


CASES = [("ก_Actual", "full", "actual"), ("ข_Rate", "full", "rate"), ("ค_noFront", "nofront", "actual"), ("ง_0pct", "c0", "actual")]


def run_cases(E, FD, plan_by_model, fd_actual_e, fd_actual_f, fd_rate_e, fd_rate_f, cases=CASES, models=ro.MODELS):
    """-> {(case, model): sims_dict[kind]}"""
    out = {}
    for case, kind, src in cases:
        fe, ff = (fd_actual_e, fd_actual_f) if src == "actual" else (fd_rate_e, fd_rate_f)
        for m in models:
            s = ro.sims_for(m, plan_by_model[m], E, FD, [kind], fd_e=fe, fd_f=ff)
            out[(case, m)] = s[kind]
    return out


def rate_diag(fd_a, fd_r, held_pairs):
    """อัตรา FF/BF/SI/SO เฉลี่ย (Actual vs Rate) ของกองที่ถูกถือ ณ วันซื้อ — อธิบายว่าทำไมเพดานแพงกว่า."""
    rows = []
    for code in fees.CODES:
        a = [fd_a.rate(fc, code, e) for fc, e in held_pairs]
        r = [fd_r.rate(fc, code, e) for fc, e in held_pairs]
        rows.append({"code": code, "mean_actual_pct": float(np.mean(a)), "mean_rate_pct": float(np.mean(r)), "n_pairs": len(a)})
    return rows


def main():
    t0 = time.time()
    nav = common.load_nav()
    codes = sorted(nav["FundCode"].unique())
    groups = common.load_groups()
    tab = rru.retail_table(codes, groups)
    cut = set(tab.loc[tab["cut"], "FundCode"])
    saved = pickle.load(open(os.path.join(SCRATCH, "validator_robust_offsets_out.pkl"), "rb"))
    PL = saved["plans"]
    envs = {}
    FD = None
    f_codes = None
    rows, diag_rows, cov_rows = [], [], []
    ref_off = {}
    for k in ro.OFFSETS:
        pk = os.path.join(SCRATCH, "validator_retail_ctxs.pkl") if k == 0 else None
        E = ro.setup_env_off(k, cut, pk)
        if FD is None:
            FD = r15.FData(r15.load_profile(), E)
            f_codes = sorted(FD.profile.index[FD.profile["Fund Policy"] == "F"])
            fd_a_f = fees.FeeData(f_codes)
            fd_r_f = FeeDataRate(f_codes)
            fd_r_e = FeeDataRate(E["codes"])
        envs[k] = E
        fd_a_e = E["fd_sim"]
        plan_by_model = PL[k]
        # plan ต้องตรงกับ pickle ของ robust_offsets (วันที่เท่ากัน)
        assert [p["t"] for p in plan_by_model["B"]] == E["q15"]
        cases = CASES if k == 0 else [c for c in CASES if c[0] in ("ก_Actual", "ข_Rate", "ค_noFront")]
        res = run_cases(E, FD, plan_by_model, fd_a_e, fd_a_f, fd_r_e, fd_r_f, cases=cases)
        print(f"[off{k}] fee cases done ({time.time()-t0:.0f}s)", flush=True)
        for (case, m), s in res.items():
            mo = ro.orig_metrics(s["values"], E["real"])
            wm = ro.win_metrics(s["values"], E["real"])
            rows.append({"offset": k, "case": case, "model": m, "sharpe_origwin": mo["sharpe"], "cagr_origwin": mo["cagr"], "vol_origwin": mo["vol"], "maxdd_origwin": mo["max_dd"],
                         "n_months_origwin": mo["n_months"], "sharpe_win": wm["sharpe"], "cagr_win": wm["cagr"], "vol_win": wm["vol"], "maxdd_win": wm["max_dd"],
                         "n_months_win": wm["n_months"], "cost_pct_yr": s["cost_bp_yr"] / 100.0, "turn_yr": s["turn_yr"], "n_cannot_buy": s["n_cannot_buy"],
                         "r_win": None})
            res[(case, m)]["_wm"] = wm
        # A − B ต่อกรณี (ช่วงวัดผลร่วม paired CI + ช่วงเดิม)
        for case in {c[0] for c in cases}:
            ra, rb = res[(case, "A")]["_wm"]["r"], res[(case, "B")]["_wm"]["r"]
            lo, hi, pt = r11.paired_real(ra, rb, res[(case, "A")]["_wm"]["rfm"], "r")
            ma, mb = ro.orig_metrics(res[(case, "A")]["values"], E["real"]), ro.orig_metrics(res[(case, "B")]["values"], E["real"])
            diag_rows.append({"offset": k, "case": case, "A_minus_B_win": pt, "ci_lo": lo, "ci_hi": hi, "A_minus_B_origwin": ma["sharpe"] - mb["sharpe"],
                              "A_win": res[(case, "A")]["_wm"]["sharpe"], "B_win": res[(case, "B")]["_wm"]["sharpe"]})
        # regression offset 0 (ก)
        if k == 0:
            reg = json.load(open(os.path.join(SCRATCH, "validator_robust_regression.json")))
            for m in ro.MODELS:
                got = ro.orig_metrics(res[("ก_Actual", m)]["values"], E["real"])["sharpe"]
                ref_off[m] = {"got": got, "ref": reg[m]["ref"], "diff": abs(got - reg[m]["ref"])}
            print("REGRESSION (ก) offset 0:", json.dumps(ref_off), flush=True)
            assert all(v["diff"] < 5e-7 for v in ref_off.values()), "regression ไม่ผ่าน"
            # ความครอบคลุม/ข้อมูล: Rate vs Actual ของกองที่ถือ
            for m in ("A", "B"):
                ents = res[("ก_Actual", m)]["entries"]
                held = sorted({(f, en["e"]) for en in ents for f, w in en["target"].items() if w > 1e-12 and f != "__CASH__"})
                held_e = [(f, e) for f, e in held if f not in FD.codes]
                held_f = [(f, e) for f, e in held if f in FD.codes]
                for lab, fda, fdr, hp in (("หุ้น", fd_a_e, fd_r_e, held_e), ("F", fd_a_f, fd_r_f, held_f)):
                    if hp:
                        for r_ in rate_diag(fda, fdr, hp):
                            cov_rows.append({"model": m, "leg": lab, **r_})
            cov_rows.append({"model": "-", "leg": "FeeData หุ้น Actual", "code": "n_rows/n_invalid", "mean_actual_pct": fd_a_e.n_rows, "mean_rate_pct": fd_a_e.n_invalid, "n_pairs": 0})
            cov_rows.append({"model": "-", "leg": "FeeData หุ้น Rate", "code": "n_rows/n_invalid", "mean_actual_pct": fd_r_e.n_rows, "mean_rate_pct": fd_r_e.n_invalid, "n_pairs": 0})
            cov_rows.append({"model": "-", "leg": "FeeData F Actual", "code": "n_rows/n_invalid", "mean_actual_pct": fd_a_f.n_rows, "mean_rate_pct": fd_a_f.n_invalid, "n_pairs": 0})
            cov_rows.append({"model": "-", "leg": "FeeData F Rate", "code": "n_rows/n_invalid", "mean_actual_pct": fd_r_f.n_rows, "mean_rate_pct": fd_r_f.n_invalid, "n_pairs": 0})
            for c in fees.CODES:
                cov_rows.append({"model": "-", "leg": "median fallback", "code": c, "mean_actual_pct": fd_a_e.median[c], "mean_rate_pct": fd_r_e.median[c], "n_pairs": 0})
                cov_rows.append({"model": "-", "leg": "median fallback F", "code": c, "mean_actual_pct": fd_a_f.median[c], "mean_rate_pct": fd_r_f.median[c], "n_pairs": 0})
    S = pd.DataFrame(rows).drop(columns=["r_win"])
    S.to_csv(os.path.join(RES, "ROBUST_fees.csv"), index=False)
    D = pd.DataFrame(diag_rows)
    D.to_csv(os.path.join(RES, "ROBUST_fees_AminusB.csv"), index=False)
    pd.DataFrame(cov_rows).to_csv(os.path.join(RES, "ROBUST_fees_rate_vs_actual.csv"), index=False)
    pd.set_option("display.width", 250)
    print(S.round(4).to_string())
    print(D.round(4).to_string())
    print(pd.DataFrame(cov_rows).round(3).to_string())
    print(f"DONE {time.time()-t0:.0f}s", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
