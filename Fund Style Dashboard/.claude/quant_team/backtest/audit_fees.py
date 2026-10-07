"""audit_fees.py — ตรวจค่าธรรมเนียมซื้อขาย/สับเปลี่ยนใน backtest ของ M004-TF-FX (Trend 25, หน้า 9) และ M013-GC75 (โมเดลหลัก)
เป็นการตรวจ (audit) ไม่ใช่ trial: ไม่แตะ trials.csv / ALL_RESULTS · READ-ONLY ต่อแอป/cache/base_data · ไม่แก้โค้ดเดิม
รัน: ./.venv/bin/python .claude/quant_team/backtest/audit_fees.py   (จาก root โปรเจกต์)
เขียนเฉพาะ: backtest/results/AUDIT_fees*.csv|md

ขั้นตอน
 1) FeeData ของผม (AFD) อ่านจาก SecFundFee.csv ดิบ — ต้องให้ค่าตรง fees.FeeData เดิมทุกกอง/รหัส/วัน (assert)
 2) สร้าง plan จาก results/*_weights.csv แล้วรัน simulate_path เดิม (เส้นทางเงินสด rf จริง) ผ่าน FeeModel ที่ "ดักจับ" drift/target ต่อ entry
    -> regression: Sharpe/ต้นทุน bp/ปี ต้องตรงไฟล์ผลเดิม
 3) คำนวณต้นทุนต่อ entry ซ้ำแบบอิสระ (my_entry) เทียบ simulate ทุก entry + แยก FF/BF/SI/SO + ต่อกอง + ช่องทางสับเปลี่ยน
 4) ตรวจ edge case / ตารางค่าธรรมเนียม / sensitivity ต่อ Sharpe (alt FeeData รันซ้ำ read-only)
"""
from __future__ import annotations

import json
import os
import sys
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

ROOT = common.PROJECT_ROOT
RES = common.RESULTS_DIR
PE = pd.Timestamp("2025-12-31")
CODES = ("FF", "BF", "SI", "SO")
ZERO_TEXT = {"ไม่มี", "ยกเว้น", "ปัจจุบันไม่เรียกเก็บ"}      # ข้อความที่แปลว่า "ไม่เก็บ" (= 0) — โค้ดเดิมถือเป็น NaN -> median
MAX_PCT = 10.0

_RAW = None


def raw_fee():
    global _RAW
    if _RAW is None:
        d = pd.read_csv(os.path.join(ROOT, "base_data", "SecFundFee.csv"), dtype=str, encoding="utf-8-sig")
        d = d[d["Complex Type Code"] == "FEEUH"].copy()
        d["file_row"] = d.index
        d["date"] = pd.to_datetime(d["As of Date"], format="%Y%m%d")
        _RAW = d
    return _RAW


# ============================================================ FeeData อิสระ (AFD)
class AFD:
    """อ่านค่าธรรมเนียมจาก CSV ดิบด้วยตรรกะของผมเอง · พารามิเตอร์ใช้ทำ sensitivity:
    value_col 'Actual Value' | 'Rate' (เพดาน) · text_zero: 'ไม่มี/ยกเว้น/ไม่เรียกเก็บ' = 0 · dup: 'last'|'first'|'min'|'max' (แถวซ้ำ fund+code+date)
    no_switch: ปิดช่องทางสับเปลี่ยน (ใช้ใน sensitivity) — ให้ผู้เรียกอ่านจากแอตทริบิวต์"""

    def __init__(self, fund_codes, value_col="Actual Value", text_zero=False, dup="last", override=None, fill_missing=None, fill_funds=()):
        d = raw_fee()
        d = d[d["Code"].isin(CODES) & d["Fund Code"].isin(set(fund_codes))].copy()
        raw = d[value_col]
        v = pd.to_numeric(raw, errors="coerce")
        d["text_zero"] = raw.isin(ZERO_TEXT)
        if text_zero:
            v[d["text_zero"]] = 0.0
        d["bad"] = v.isna() | (v < 0) | (v > MAX_PCT)
        v[(v < 0) | (v > MAX_PCT)] = np.nan
        d["v"] = v
        if override:
            for (fc, code), val in override.items():
                m = (d["Fund Code"] == fc) & (d["Code"] == code)
                d.loc[m, "v"] = val
                d.loc[m, "bad"] = False
        d = d.sort_values(["Fund Code", "Code", "date", "file_row"], kind="mergesort")
        self.rows = d
        self.series = {}
        self.dup_groups = []
        for (fc, code), g in d.groupby(["Fund Code", "Code"], sort=False):
            gg = g.groupby("date", sort=True)
            dates, vals, bads = [], [], []
            for dt, x in gg:
                if len(x) > 1 and x["v"].nunique(dropna=False) > 1:
                    self.dup_groups.append((fc, code, dt, list(x["v"]), list(x["Actual Value"])))
                if dup == "last":
                    r = x.iloc[-1]
                elif dup == "first":
                    r = x.iloc[0]
                elif dup == "min":
                    r = x.loc[x["v"].idxmin()] if x["v"].notna().any() else x.iloc[-1]
                else:
                    r = x.loc[x["v"].idxmax()] if x["v"].notna().any() else x.iloc[-1]
                dates.append(dt)
                vals.append(r["v"])
                bads.append(bool(r["bad"]))
            self.series[(fc, code)] = (np.array(dates, dtype="datetime64[ns]"), np.array(vals, dtype=float), np.array(bads))
        for f in fill_funds:                 # กอง/รหัสที่ไม่มีแถว FEEUH -> ค่าคงที่ (ใช้ใน sensitivity เท่านั้น)
            for c, val in (fill_missing or {}).items():
                if (f, c) not in self.series:
                    self.series[(f, c)] = (np.array(["1900-01-01"], dtype="datetime64[ns]"), np.array([val], dtype=float), np.array([False]))
        last = {k: s[1][-1] for k, s in self.series.items() if (k[0], k[1]) not in self._filled(fill_funds, fill_missing)}
        self.median = {c: float(np.nanmedian([v for (f, cc), v in last.items() if cc == c])) for c in CODES}
        prof = pd.read_csv(os.path.join(ROOT, "base_data", "FundProfile.csv"), dtype=str)
        self.amc = dict(zip(prof["Fund Code"], prof["AMC_CODE"]))
        self.n_fallback = defaultdict(int)

    @staticmethod
    def _filled(fill_funds, fill_missing):
        return set()

    def lookup(self, fc, code, e):
        """-> (ค่า %, แหล่งที่มา, วันที่ snapshot ที่ใช้)"""
        s = self.series.get((fc, code))
        if s is None:
            return self.median[code], "median: ไม่มีแถว FEEUH ของกอง/รหัสนี้", None
        dates, vals, bads = s
        i = int(np.searchsorted(dates, np.datetime64(e), side="right")) - 1
        pre = i < 0
        i = max(i, 0)
        if not np.isfinite(vals[i]):
            return self.median[code], "median: ค่าใช้ไม่ได้ (ว่าง/ข้อความ/ติดลบ/>10)", pd.Timestamp(dates[i])
        src = "snapshot เก่าสุด (ก่อน snapshot แรก)" if pre else "ค่าจริง (snapshot ≤ วันซื้อขาย)"
        return float(vals[i]), src, pd.Timestamp(dates[i])

    def rate(self, fc, code, e):
        v, src, _ = self.lookup(fc, code, e)
        if src.startswith("median"):
            self.n_fallback[code] += 1
        return v


# ============================================================ model ที่ดักจับ drift/target
class RecFeeModel(fees.FeeModel):
    def __init__(self, data, mode="full", switch=True):
        super().__init__(data, mode)
        self.rec = []
        self.switch = switch

    def entry_cost(self, e, drift_w, target_w):
        if self.switch:
            c, det = super().entry_cost(e, drift_w, target_w)
        else:                      # ปิดช่องทางสับเปลี่ยน: ขาย×BF + ซื้อ×FF (ไม่ใช้ min(S,B))
            c = 0.0
            for f in set(drift_w) | set(target_w):
                dl = target_w.get(f, 0.0) - drift_w.get(f, 0.0)
                if dl < -1e-15:
                    c += -dl * self._r(f, "BF", e)
                elif dl > 1e-15:
                    c += dl * self._r(f, "FF", e)
            det = {"sell_vol": 0, "buy_vol": 0, "switch_vol": 0}
        self.rec.append({"e": e, "drift": dict(drift_w), "target": dict(target_w), "cost": c})
        return c, det


def load_plan(path, trial):
    w = pd.read_csv(path)
    w = w[w["trial"] == trial]
    plan = []
    for (t, e), g in w.groupby(["t", "e"], sort=True):
        plan.append({"t": pd.Timestamp(t), "e": pd.Timestamp(e), "weights": dict(zip(g["FundCode"], g["weight"]))})
    plan.sort(key=lambda p: p["t"])
    return plan


def make_months(calendar, q15):
    bound_m = q15[-1] + pd.Timedelta(days=75)
    months = [m for m in common.month_ends(calendar, common.execution_date(calendar, q15[0]), "2026-03-31") if m <= bound_m + pd.Timedelta(days=31)]
    return months


def run_sim(plan, nav_by_fund, months, fee_model, curve):
    clean = [{k: v for k, v in p.items() if k in ("t", "e", "weights")} for p in plan]
    info = {}
    with rr.cash_curve(curve):
        v, tu, ev, _ = simulate.simulate_path(clean, nav_by_fund, months, 0.0, 0.02, include_start=True, info=info, fee_model=fee_model)
    ent = [x for x in info["entries"] if x["e"] <= PE]
    yrs = (PE - clean[0]["e"]).days / 365.25
    cost = sum(x["cost"] for x in ent)
    m = rr.metrics(v, curve)
    return {"values": v, "entries": ent, "events": ev, "metrics": m, "cost_bp_yr": cost / yrs * 1e4, "yrs": yrs,
            "turn_yr": sum(x["turnover"] for x in ent[1:]) / yrs}


# ============================================================ ต้นทุนต่อ entry แบบอิสระ (ตามสูตร spec ทีละขั้น)
def my_entry(e, drift, target, afd: AFD, switch=True):
    """คืน dict: cost รวม, แยกรหัส (FF/BF/SI/SO), ต่อกอง, ต่อ บลจ. (m, อัตราถ่วง, ช่องทาง)"""
    dlt = {f: target.get(f, 0.0) - drift.get(f, 0.0) for f in set(drift) | set(target)}
    sells = {f: -x for f, x in dlt.items() if x < -1e-15}
    buys = {f: x for f, x in dlt.items() if x > 1e-15}
    comp = {c: 0.0 for c in CODES}
    per_fund = defaultdict(lambda: {c: 0.0 for c in CODES})
    amcs = {}
    r = lambda f, c: afd.lookup(f, c, e)[0] / 100.0
    by = defaultdict(lambda: ([], []))
    for f in sells:
        by[afd.amc.get(f, f)][0].append(f)
    for f in buys:
        by[afd.amc.get(f, f)][1].append(f)
    for amc, (sf, bf) in by.items():
        S, B = sum(sells[f] for f in sf), sum(buys[f] for f in bf)
        m = min(S, B) if (switch and sf and bf) else 0.0
        info = {"amc": amc, "S": S, "B": B, "m": m, "channel": "-"}
        s_left = S - m
        b_left = B - m
        if m > 0:
            so_w = sum(sells[f] * r(f, "SO") for f in sf) / S
            si_w = sum(buys[f] * r(f, "SI") for f in bf) / B
            bf_w = sum(sells[f] * r(f, "BF") for f in sf) / S
            ff_w = sum(buys[f] * r(f, "FF") for f in bf) / B
            info.update({"so_w": so_w, "si_w": si_w, "bf_w": bf_w, "ff_w": ff_w})
            if so_w + si_w < bf_w + ff_w:
                info["channel"] = "สับเปลี่ยน"
                comp["SO"] += m * so_w
                comp["SI"] += m * si_w
                info["saving"] = m * ((bf_w + ff_w) - (so_w + si_w))
                for f in sf:
                    per_fund[f]["SO"] += sells[f] / S * m * r(f, "SO")
                for f in bf:
                    per_fund[f]["SI"] += buys[f] / B * m * r(f, "SI")
            else:
                info["channel"] = "ขาย-ซื้อ"
                info["saving"] = 0.0
                comp["BF"] += m * bf_w
                comp["FF"] += m * ff_w
                for f in sf:
                    per_fund[f]["BF"] += sells[f] / S * m * r(f, "BF")
                for f in bf:
                    per_fund[f]["FF"] += buys[f] / B * m * r(f, "FF")
        for f in sf:
            x = sells[f] * (s_left / S) * r(f, "BF")
            comp["BF"] += x
            per_fund[f]["BF"] += x
        for f in bf:
            x = buys[f] * (b_left / B) * r(f, "FF")
            comp["FF"] += x
            per_fund[f]["FF"] += x
        amcs[amc] = info
    return {"cost": sum(comp.values()), "comp": comp, "per_fund": dict(per_fund), "amcs": amcs, "sells": sells, "buys": buys}


def src_of(afd, f, c, e):
    return afd.lookup(f, c, e)


def main(write=True):
    out = {}
    nav = common.load_nav()
    nav_by_fund = common.build_nav_by_fund(nav)
    calendar = common.load_calendar()
    codes = sorted(nav["FundCode"].unique())
    q16 = common.quarter_ends(calendar, "2022-03-31", "2025-12-31")
    q15 = q16[:15]
    months = make_months(calendar, q15)
    real, _ = rr.load_policy()

    plans = {"M004-TF-FX": load_plan(os.path.join(RES, "M004-TF-FX_weights.csv"), "M004-TF-FX"),
             "M013-GC75": load_plan(os.path.join(RES, "M013_weights.csv"), "M013-GC75")}
    ref = pd.read_csv(os.path.join(RES, "REAL_RF_summary.csv")).set_index("trial")
    ref13 = pd.read_csv(os.path.join(RES, "M013_results.csv")).set_index(["trial", "cost"])
    reference = {"M004-TF-FX": {"sharpe": float(ref.loc["M004-TF-FX", "sharpe_full_real"]), "src": "REAL_RF_summary.csv sharpe_full_real"},
                 "M013-GC75": {"sharpe": float(ref13.loc[("M013-GC75", "full"), "sharpe_real"]), "cost_bp": float(ref13.loc[("M013-GC75", "full"), "cost_bp_yr_real"]),
                               "src": "M013_results.csv full"}}

    # ---- 1) AFD เทียบ FeeData เดิม ทุก (กอง, รหัส, วัน e)
    held = sorted({f for p in plans.values() for q in p for f in q["weights"] if f != "__CASH__"})
    orig = fees.FeeData(codes)
    afd = AFD(codes)
    es = sorted({q["e"] for p in plans.values() for q in p})
    mism = []
    for f in held:
        for c in CODES:
            for e in es:
                a, b = orig.rate(f, c, e), afd.rate(f, c, e)
                if not (abs(a - b) < 1e-12):
                    mism.append((f, c, str(e.date()), a, b))
    out["afd_vs_orig_mismatch"] = mism
    out["median"] = afd.median
    out["median_orig"] = orig.median
    out["dup_groups_held"] = [x for x in afd.dup_groups if x[0] in set(held)]
    out["dup_groups_all"] = len(afd.dup_groups)
    out["held"] = held
    out["entry_dates"] = es

    # ---- 2) simulate (เดิม) พร้อมดักจับ
    sims = {}
    for name, plan in plans.items():
        fm = RecFeeModel(fees.FeeData(codes), "full")
        s = run_sim(plan, nav_by_fund, months, fm, real)
        s["rec"] = fm.rec
        sims[name] = s
    out["sims_meta"] = {n: {"sharpe_real": s["metrics"]["sharpe"], "cost_bp_yr": s["cost_bp_yr"], "turn_yr": s["turn_yr"], "cagr": s["metrics"]["cagr"],
                            "n_entries": len(s["entries"]), "cannot_buy": sum(1 for e in s["events"] if e["type"] == "cannot_buy")} for n, s in sims.items()}
    out["reference"] = reference

    # ---- 3) ต้นทุนอิสระ ทุก entry
    rows, fund_rows, amc_rows = [], [], []
    for name, s in sims.items():
        for k, (en, rec) in enumerate(zip(s["entries"], s["rec"])):
            assert en["e"] == rec["e"]
            mine = my_entry(rec["e"], rec["drift"], rec["target"], afd)
            tgt = en["target"]
            cash_t = tgt.get("__CASH__", 0.0)
            drift_eq = sum(rec["drift"].values())
            row = {"model": name, "k": k, "t": en["t"].date(), "e": rec["e"].date(), "equity_before": drift_eq, "equity_after": 1 - cash_t,
                   "n_sell": len(mine["sells"]), "n_buy": len(mine["buys"]), "sell_vol": sum(mine["sells"].values()), "buy_vol": sum(mine["buys"].values()),
                   "turnover": en["turnover"], "cost_sim": rec["cost"], "cost_mine": mine["cost"], "diff": rec["cost"] - mine["cost"],
                   "cost_FF": mine["comp"]["FF"], "cost_BF": mine["comp"]["BF"], "cost_SI": mine["comp"]["SI"], "cost_SO": mine["comp"]["SO"],
                   "switch_vol": sum(a["m"] for a in mine["amcs"].values() if a["channel"] == "สับเปลี่ยน"),
                   "matched_vol": sum(a["m"] for a in mine["amcs"].values()),
                   "saving_switch": sum(a.get("saving", 0.0) for a in mine["amcs"].values())}
            cs = my_entry(rec["e"], rec["drift"], rec["target"], afd, switch=False)
            row["cost_noswitch"] = cs["cost"]
            # fallback ที่มีผลจริง (กอง×รหัสที่ถูกใช้ใน entry นี้)
            used_fb = defaultdict(int)
            for f in mine["sells"]:
                for c in ("BF", "SO"):
                    if afd.lookup(f, c, rec["e"])[1].startswith("median"):
                        used_fb[c] += 1
            for f in mine["buys"]:
                for c in ("FF", "SI"):
                    if afd.lookup(f, c, rec["e"])[1].startswith("median"):
                        used_fb[c] += 1
            for c in CODES:
                row[f"fallback_{c}"] = used_fb[c]
            rows.append(row)
            for f, comp in mine["per_fund"].items():
                fund_rows.append({"model": name, "k": k, "e": rec["e"].date(), "fund": f, "amc": afd.amc.get(f), **{f"cost_{c}": comp[c] for c in CODES},
                                  "cost": sum(comp.values()), "sell": mine["sells"].get(f, 0.0), "buy": mine["buys"].get(f, 0.0)})
            for amc, a in mine["amcs"].items():
                amc_rows.append({"model": name, "k": k, "e": rec["e"].date(), **a})
    E = pd.DataFrame(rows)
    F = pd.DataFrame(fund_rows)
    A = pd.DataFrame(amc_rows)
    out["max_abs_diff_entry"] = float(E["diff"].abs().max())

    # ---- 4) ตารางค่าธรรมเนียมต่อกอง × รหัส × วัน
    ftab = []
    for name, s in sims.items():
        for k, (en, rec) in enumerate(zip(s["entries"], s["rec"])):
            mine = my_entry(rec["e"], rec["drift"], rec["target"], afd)
            for f in sorted(set(mine["sells"]) | set(mine["buys"])):
                for c in CODES:
                    side_ok = (f in mine["sells"] and c in ("BF", "SO")) or (f in mine["buys"] and c in ("FF", "SI"))
                    v, src, sd = afd.lookup(f, c, rec["e"])
                    ftab.append({"model": name, "k": k, "e": rec["e"].date(), "fund": f, "amc": afd.amc.get(f), "code": c, "used_in_entry": side_ok,
                                 "side": "sell" if f in mine["sells"] else "buy", "value_pct": v, "source": src, "snapshot": sd.date() if sd is not None else None})
    FT = pd.DataFrame(ftab)

    # ---- 5) snapshot ทุกค่าของกองที่เคยถือ
    snap = raw_fee()
    snap = snap[snap["Fund Code"].isin(held) & snap["Code"].isin(CODES)][["Fund Code", "Code", "As of Date", "Rate", "Actual Value", "file_row"]]
    snap = snap.sort_values(["Fund Code", "Code", "As of Date", "file_row"])
    out["n_snapshot_rows_held"] = len(snap)

    # ---- 6) sensitivity: alt fee data รัน simulate ใหม่ (read-only)
    def sens(label, afd_alt, switch=True, name_list=("M004-TF-FX", "M013-GC75")):
        res = {}
        for name in name_list:
            fm = RecFeeModel(afd_alt, "full", switch=switch)
            s = run_sim(plans[name], nav_by_fund, months, fm, real)
            res[name] = {"sharpe": s["metrics"]["sharpe"], "cagr": s["metrics"]["cagr"], "cost_bp_yr": s["cost_bp_yr"]}
        return label, res

    S = []
    S.append(sens("baseline (AFD ของผม = โค้ดเดิม)", afd))
    S.append(sens("'ไม่มี/ยกเว้น/ไม่เรียกเก็บ' = 0 (แทน median)", AFD(codes, text_zero=True)))
    for d_ in ("first", "min", "max"):
        S.append(sens(f"แถวซ้ำ fund+code+date เลือก {d_}", AFD(codes, dup=d_)))
    S.append(sens("ใช้ Rate (เพดานหนังสือชี้ชวน) แทน Actual Value", AFD(codes, value_col="Rate", text_zero=True)))
    S.append(sens("ไม่มีช่องทางสับเปลี่ยน (ขาย×BF + ซื้อ×FF ล้วน)", afd, switch=False))
    nof = {(f, c): 0.0 for f in held for c in ("FF", "SI")}
    S.append(sens("ยกเว้น front-end (FF=SI=0) — ผ่าน AFD", AFD(codes, override=nof, fill_missing={"FF": 0.0, "SI": 0.0}, fill_funds=held)))
    zero_all = {(f, c): 0.0 for f in held for c in CODES}
    S.append(sens("ต้นทุน 0 ทุกกอง (เพดาน Sharpe ก่อนค่าธรรมเนียม)", AFD(codes, override=zero_all, fill_missing={c: 0.0 for c in CODES}, fill_funds=held)))
    # กอง/รหัสที่ไม่มีแถว FEEUH ใช้ 0 หรือ 2x median แทน median (ช่วงของผลจาก fallback)
    S.append(sens("กอง/รหัสที่ไม่มีแถว FEEUH = 0 (แทน median)", AFD(codes, fill_missing={c: 0.0 for c in CODES}, fill_funds=held)))
    S.append(sens("กอง/รหัสที่ไม่มีแถว FEEUH = FF/SI เพดาน-สมมติ 3.0/3.0, BF/SO 2.0 (ขอบบน)", AFD(codes, fill_missing={"FF": 3.0, "SI": 3.0, "BF": 2.0, "SO": 2.0}, fill_funds=held)))
    # กองที่ FF Actual = 0 (class เฉพาะช่องทาง/ยกเว้น) — ถ้าต้องจ่าย FF=SI=1.5 แทน
    rawf = raw_fee()
    rawf = rawf[rawf["Fund Code"].isin(held) & (rawf["Code"] == "FF")]
    ff0_funds = sorted(rawf[pd.to_numeric(rawf["Actual Value"], errors="coerce") == 0]["Fund Code"].unique())
    ov = {(f, c): 1.5 for f in ff0_funds for c in ("FF", "SI")}
    S.append(sens("กองที่ FF Actual=0 (" + str(len(ff0_funds)) + " กอง) ต้องจ่าย FF=SI=1.5", AFD(codes, override=ov)))
    out["ff0_funds"] = ff0_funds
    out["sens"] = S
    out["missing_series"] = sorted([f"{f}:{c}" for f in held for c in CODES if (f, c) not in afd.series])

    # ---- 7) edge cases
    ec = {}
    prof = pd.read_csv(os.path.join(ROOT, "base_data", "FundProfile.csv"), dtype=str).set_index("Fund Code")
    flags = prof.loc[[f for f in held if f in prof.index], ["AMC_CODE", "switch_out flag", "switch_in flag", "Fund Class", "buy period flag", "sell period flag", "switch in periold flag", "switch out periold flag", "Dividend_Flag", "fst_lowbuy_val", "Project Retail Type", "Fund Name EN"]]
    ec["flags"] = flags
    sw = A[A["channel"] == "สับเปลี่ยน"]
    ec["n_switch_amc_entries"] = int(len(sw))
    ec["stale_marks"] = {}
    ec["cannot_buy"] = {n: [(str(e["date"].date()), e["fund"]) for e in s["events"] if e["type"] == "cannot_buy"] for n, s in sims.items()}
    ec["exec_late"] = {n: [(str(e["date"].date()), e["fund"]) for e in s["events"] if e["type"] == "exec_late"] for n, s in sims.items()}
    out["ec"] = ec
    # แถวดิบตัวอย่าง
    out["snap"] = snap

    # family (cross-class) switch ตัวอย่าง
    groups = common.load_groups()
    xs = []
    for name, s in sims.items():
        for k, rec in enumerate(s["rec"]):
            mine = my_entry(rec["e"], rec["drift"], rec["target"], afd)
            for amc, a in mine["amcs"].items():
                if a["m"] > 0:
                    sf = [f for f in mine["sells"] if afd.amc.get(f, f) == amc]
                    bf = [f for f in mine["buys"] if afd.amc.get(f, f) == amc]
                    for x in sf:
                        for y in bf:
                            xs.append({"model": name, "e": str(rec["e"].date()), "sell": x, "buy": y, "amc": amc, "same_family": groups.get(x) is not None and groups.get(x) == groups.get(y),
                                       "sell_vol": mine["sells"][x], "buy_vol": mine["buys"][y], "channel": a["channel"]})
    out["pairs"] = pd.DataFrame(xs)

    out["E"], out["F"], out["A"], out["FT"] = E, F, A, FT
    out["yrs"] = {n: s["yrs"] for n, s in sims.items()}
    out["sims"] = sims
    out["afd"] = afd
    out["nav_by_fund"] = nav_by_fund
    return out


if __name__ == "__main__":
    import audit_fees_report
    audit_fees_report.main()
