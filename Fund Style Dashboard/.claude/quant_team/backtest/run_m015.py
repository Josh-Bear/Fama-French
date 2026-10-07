"""run_m015.py — M015: กองตราสารหนี้ policy F แทนเงินสด (`__CASH__`) ในขาที่ไม่ใช่หุ้นของ M013-GC75 (universe รายย่อย) · 3 trials: FSR3 (30), FSR1 (31), FAUM (32)
ตาม specs/M015_bond_fund_cash.md + "การตัดสินใจของผู้ใช้ 2026-10-06" · วัดด้วย rf จริง (remeasure_real_rf.py, ตัวหาร sd(r)) · fees = FeeData(legacy=False)
รัน: PYTHONPATH=. ./.venv/bin/python .claude/quant_team/backtest/run_m015.py [--phase-a-only]
(A) regression (ไม่ผ่าน = หยุด ไม่นับ trial): 1) selector=CASH ผ่านโค้ดใหม่ทั้งเส้นทาง = RETAIL_weights/RETAIL_results (M013-GC75) · 2) กองสังเคราะห์ __RF_FUND__ ·
    3) ส่วนหุ้น = baseline (max|dw|<1e-12), Σ=1, ไม่มีข้อมูล > t
(B) ถ้าผ่านเท่านั้น -> รัน 3 trials · ไม่แก้ไฟล์เดิม · reuse rerun_retail_universe/run_m011/run_m012/run_m013/remeasure_real_rf/fund_signals/fees/simulate

ข้อตีความของ validator (ต้องรายงาน):
 (i) fs.QuarterContext.fund_signal มีเพดานล่าง vol52 < 0.02 -> NaN (ตัวกันกองหุ้น NAV นิ่ง) · ถ้าใช้กับกอง F จะตัดกองตลาดเงินทุกกอง (vol จริง ~0.0001-0.001)
     ทำให้ F-AUM (ตลาดเงิน Risk Level 1-2) เลือกไม่ได้เลย ขัดกับ spec §2 -> ใช้สัญญาณ F แบบเดียวกันทุกสูตร แต่เปลี่ยนเพดานเป็น vol52 > 0 (ยังคง n_obs>=40 และ zero_frac<=0.20)
 (ii) FeeData ฝั่ง F = FeeData(ทุกกอง policy F ใน FundProfile) (median ของ "กอง F ทั้งหมด" ตาม spec §2)
 (iii) universe/Quality ของ F: Quality ใช้ NAV ของทุก class F (AUM_fam รวมทุก class เหมือนฝั่งหุ้น) · เกณฑ์ snapshot ตัด class ก่อนเลือก family ตัวแทน
"""
from __future__ import annotations

import json
import os
import pickle
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
import run_m006_m007 as r67
import run_m011 as r11
import run_m012 as r12
import run_m013 as r13
import remeasure_real_rf as rr
import rerun_retail_universe as rru

TEAM_DIR = os.path.dirname(THIS_DIR)
PROJECT = os.path.dirname(os.path.dirname(TEAM_DIR))
SCRATCH = os.path.join(TEAM_DIR, "scratch")
RES = common.RESULTS_DIR
CACHE = common.CACHE_DIR
TRIALS_CSV = os.path.join(TEAM_DIR, "trials.csv")
N_TRIALS_FINAL = 32
TRIAL_IDS = ["M015-FSR3", "M015-FSR1", "M015-FAUM"]
KINDS = ["c0", "c50", "flat", "full", "nofront"]
AUM_BIG = 1_000_000_000.0
NAVF_PARQUET = os.path.join(CACHE, "m015_navF_clean.parquet")
SPIKE_LOG = os.path.join(CACHE, "m015_navF_spike_log.csv")
RF_FUND = "__RF_FUND__"


# ====================== ข้อมูลกอง F ======================
def load_profile() -> pd.DataFrame:
    p = pd.read_csv(os.path.join(PROJECT, "base_data", "FundProfile.csv"), dtype=str, encoding="utf-8-sig")
    p.columns = [c.strip() for c in p.columns]
    return p.drop_duplicates("Fund Code").set_index("Fund Code")


def build_navF(profile: pd.DataFrame, force=False) -> pd.DataFrame:
    """NAV กอง F (policy F) จาก base_data/nav_history_db.csv (chunk · เลือกคอลัมน์) -> dedupe (FundCode,NAVDate) UpdateTime ล่าสุด -> clean §4.2 -> cache parquet ใน backtest/cache/."""
    if os.path.exists(NAVF_PARQUET) and not force:
        d = pd.read_parquet(NAVF_PARQUET)
        d["NAVDate"] = pd.to_datetime(d["NAVDate"])
        return d
    codes = set(profile.index[profile["Fund Policy"] == "F"])
    parts = []
    for ch in pd.read_csv(os.path.join(PROJECT, "base_data", "nav_history_db.csv"), usecols=["FundCode", "NAV", "NAVDate", "AUM", "UpdateTime"],
                          chunksize=500_000, dtype={"FundCode": str}):
        parts.append(ch[ch["FundCode"].isin(codes)])
    d = pd.concat(parts)
    d["NAVDate"] = pd.to_datetime(d["NAVDate"], errors="coerce")
    d = d.dropna(subset=["NAVDate", "NAV"])
    d = d[d["NAV"] > 0]
    d = d.sort_values(["FundCode", "NAVDate", "UpdateTime"]).drop_duplicates(["FundCode", "NAVDate"], keep="last")
    out, log = [], []
    for fc, g in d.groupby("FundCode"):
        g = g.sort_values("NAVDate").copy()
        v = g["NAV"].to_numpy(float)
        k = 0
        g["spike_fixed"] = False
        if len(v) >= 3:
            lr = np.diff(np.log(v))
            rin, rout = lr[:-1], lr[1:]
            m = (np.abs(rin) > 0.005) & (np.abs(rout) > 0.005) & (np.sign(rin) != np.sign(rout)) & (np.abs(rin + rout) < 0.001)
            idx = np.where(m)[0] + 1
            v2 = v.copy()
            v2[idx] = np.sqrt(v[idx - 1] * v[idx + 1])
            g["NAV"] = v2
            if len(idx):
                g.iloc[idx, g.columns.get_loc("spike_fixed")] = True
            k = len(idx)
        log.append((fc, k))
        out.append(g)
    D = pd.concat(out)
    D.to_parquet(NAVF_PARQUET)
    pd.DataFrame(log, columns=["FundCode", "n_fixed"]).to_csv(SPIKE_LOG, index=False)
    return D


def snapshot_codes(profile: pd.DataFrame) -> set:
    F = profile[profile["Fund Policy"] == "F"]
    ok = F[(F["Tax Type"].isna()) & (F["buy period flag"] == "N") & (F["Project Retail Type"] == "R")
           & (pd.to_numeric(F["fst_lowbuy_val"], errors="coerce") <= 100_000)]
    ok = ok[~ok["Fund Name EN"].fillna("").str.contains("Not for Retail|NOT FOR RETAIL|TEST", regex=True)]
    return set(ok.index)


def f_signal(qctx: fs.QuarterContext, fc: str) -> dict:
    """เหมือน fs.QuarterContext.fund_signal ทุกบรรทัด ยกเว้นเพดานล่าง vol52: (v < 0.02 -> NaN) เปลี่ยนเป็น (v <= 0 -> NaN) · hurdle ใส่ภายหลัง (SR12' = (R12_1 - h_t)/vol52)."""
    arrs = qctx.nav_arrays.get(fc)
    if arrs is None or len(qctx.months) < 13 or len(qctx.weeks) < 53:
        return {"R12_1": np.nan, "vol52": np.nan, "SR12": np.nan, "n_week_obs": 0}
    dates, values = arrs
    p_m1 = fs._asof(dates, values, qctx._months_np[-2])
    p_m12 = fs._asof(dates, values, qctx._months_np[0])
    r12_1 = (p_m1 / p_m12 - 1.0) if (p_m1 == p_m1 and p_m12 not in (0.0,) and p_m12 == p_m12) else np.nan
    wp = np.array([fs._asof(dates, values, wn) for wn in qctx._weeks_np], dtype=float)
    with np.errstate(invalid="ignore", divide="ignore"):
        wr = wp[1:] / wp[:-1] - 1.0
    valid = ~np.isnan(wr)
    n_obs = int(valid.sum())
    if n_obs < 40:
        vol52 = np.nan
    else:
        zero_frac = float((wr[valid] == 0.0).mean())
        v = float(np.std(wr[valid], ddof=1)) * np.sqrt(52.0)
        vol52 = np.nan if (zero_frac > 0.20 or not v > 0) else v
    return {"R12_1": r12_1, "vol52": vol52, "SR12": np.nan, "n_week_obs": n_obs}


class FData:
    """ข้อมูลกอง F ทั้งหมด: nav (ทุก class F ที่มี NAV), nav_by_fund, snapshot set, groups (Fund Class), Quality."""
    def __init__(self, profile, E):
        self.profile = profile
        self.nav = build_navF(profile)
        self.codes = sorted(self.nav["FundCode"].unique())
        self.nav_by_fund = {fc: g.sort_values("NAVDate").set_index("NAVDate")["NAV"] for fc, g in self.nav.groupby("FundCode")}
        self.snap = snapshot_codes(profile)
        self.groups = {fc: profile.loc[fc, "Fund Class"] for fc in self.codes if isinstance(profile.loc[fc, "Fund Class"], str)}
        self.arrays = fs._prep_arrays(self.nav_by_fund)
        self.calendar = E["calendar"]
        self.Q = r12.Quality(self.nav, self.groups)
        self.risk = profile["Fund Risk Level"]
        self.fif = profile["FIF Flag"]
        self.amc = profile["AMC_CODE"]
        self.spike = pd.read_csv(SPIKE_LOG).set_index("FundCode")["n_fixed"].to_dict()
        assert not (set(self.codes) & set(E["nav_by_fund"])), "FundCode ของ F ซ้ำกับกองหุ้นใน nav_clean"

    def it_at(self, t, nav_override=None):
        """I_t^F + ตาราง Quality ณ t (ใช้ NAV ≤ t เท่านั้น). nav_override ใช้ทดสอบ no-look-ahead (NAV ที่ตัด ≤ t ไว้แล้ว)."""
        nav = self.nav if nav_override is None else nav_override
        U = common.universe_at(nav, t)
        U = U[U["FundCode"].isin(self.snap)].reset_index(drop=True)
        arrays = self.arrays if nav_override is None else fs._prep_arrays({fc: g.set_index("NAVDate")["NAV"] for fc, g in nav.groupby("FundCode")})
        q = fs.QuarterContext(arrays, self.calendar, t)
        sig = pd.DataFrame([{"FundCode": fc, **f_signal(q, fc)} for fc in U["FundCode"]])
        if len(sig) == 0:
            return pd.DataFrame(), pd.DataFrame(), U
        it, _, _ = fs.investable_set(t, U, sig, self.groups, family_fix=True)
        Q = r12.Quality(nav, self.groups) if nav_override is not None else self.Q
        qual, _ = Q.table(t)
        return it, qual, U


def select_F(it, qual, h, mode):
    """คืน (v: {FundCode: v_j}, info dict). ไม่มี hysteresis."""
    info = {"n_I": 0, "n_fam": 0, "fallback_vol": False, "empty": False}
    if len(it) == 0:
        info["empty"] = True
        return {}, info, pd.DataFrame()
    ok = set(qual.index[qual["pass_q1"] & qual["pass_q2"]])
    it = it[it["family"].isin(ok)].copy()
    info["n_I"] = len(it)
    if len(it) == 0:
        info["empty"] = True
        return {}, info, pd.DataFrame()
    it["SR12p"] = (it["R12_1"] - h) / it["vol52"]
    it["aum_fam"] = it["family"].map(qual["aum_fam"])
    reps = it.sort_values(["SR12p", "FundCode"], ascending=[False, True]).groupby("family", sort=False).head(1).reset_index(drop=True)
    info["n_fam"] = len(reps)
    if mode == "FSR3":
        c = reps[reps["aum_fam"] >= AUM_BIG].head(3)
        if len(c) == 0:
            info["empty"] = True
            return {}, info, reps
        return {r.FundCode: 1.0 / len(c) for r in c.itertuples()}, info, c
    if mode == "FSR1":
        c = reps.head(1)
        return {c.iloc[0]["FundCode"]: 1.0}, info, c
    assert mode == "FAUM"
    reps["risk"] = reps["FundCode"].map(lambda f: None)       # เติมภายนอก (ต้องใช้ profile) — ดู select_F_aum
    raise RuntimeError("use select_F_aum")


def select_F_aum(it, qual, h, risk_map):
    info = {"n_I": 0, "n_fam": 0, "fallback_vol": False, "empty": False}
    if len(it) == 0:
        info["empty"] = True
        return {}, info, pd.DataFrame()
    ok = set(qual.index[qual["pass_q1"] & qual["pass_q2"]])
    it = it[it["family"].isin(ok)].copy()
    info["n_I"] = len(it)
    if len(it) == 0:
        info["empty"] = True
        return {}, info, pd.DataFrame()
    it["SR12p"] = (it["R12_1"] - h) / it["vol52"]
    it["aum_fam"] = it["family"].map(qual["aum_fam"])
    reps = it.sort_values(["SR12p", "FundCode"], ascending=[False, True]).groupby("family", sort=False).head(1).reset_index(drop=True)
    info["n_fam"] = len(reps)
    reps["risk"] = reps["FundCode"].map(risk_map)
    c = reps[reps["risk"].isin(["1", "2"])]
    if len(c) == 0:
        info["fallback_vol"] = True
        thr = float(it["vol52"].quantile(0.25))
        c = reps[reps["vol52"] <= thr]
    c = c.sort_values(["aum_fam", "FundCode"], ascending=[False, True]).head(1)
    return {c.iloc[0]["FundCode"]: 1.0}, info, c


def f_rows(FD: FData, E, h_by_q):
    """คำนวณ I_t^F/Quality ต่อไตรมาส (qi 0..14) ครั้งเดียว แล้วใช้ซ้ำทุกวิธีเลือก."""
    rows = []
    for qi, t in enumerate(E["q15"]):
        it, qual, U = FD.it_at(t)
        rows.append({"qi": qi, "t": t, "it": it, "qual": qual, "h": h_by_q[qi], "n_U": len(U)})
    return rows


def f_selections(FD, rows):
    """-> {mode: {qi: (v, info, table)}}"""
    out = {m: {} for m in ("FSR3", "FSR1", "FAUM")}
    risk_map = FD.risk.to_dict()
    for r in rows:
        out["FSR3"][r["qi"]] = select_F(r["it"], r["qual"], r["h"], "FSR3")
        out["FSR1"][r["qi"]] = select_F(r["it"], r["qual"], r["h"], "FSR1")
        out["FAUM"][r["qi"]] = select_F_aum(r["it"], r["qual"], r["h"], risk_map)
    return out


# ====================== fee wrapper (FeeData แยก E / F) ======================
class CombinedFee:
    """ห่อ FeeData ของกองหุ้น (FD_E) + FeeData ของกอง F (FD_F) · rate() เลือกตามสมาชิก · ไม่แก้ fees.py · amc = dict รวม (+ กองสังเคราะห์)."""
    def __init__(self, fd_e, fd_f, f_codes, extra_zero=None, extra_amc=None):
        self.fd_e, self.fd_f, self.f_codes = fd_e, fd_f, set(f_codes)
        self.extra_zero = set(extra_zero or [])
        self.amc = {**fd_e.amc, **fd_f.amc, **(extra_amc or {})}
        self.median = fd_e.median

    def rate(self, fc, code, e):
        if fc in self.extra_zero:
            return 0.0
        if fc in self.f_codes:
            return self.fd_f.rate(fc, code, e)
        return self.fd_e.rate(fc, code, e)

    @property
    def n_fallback_E(self):
        return dict(self.fd_e.n_fallback)

    @property
    def n_fallback_F(self):
        return dict(self.fd_f.n_fallback)


class LogFeeModel(fees.FeeModel):
    """FeeModel เดิม + แยกต้นทุนต่อ entry (ไม่เปลี่ยนค่าที่คืน): stock-only / F-only / F↔F rotation."""
    def __init__(self, data, mode, fset):
        super().__init__(data, mode)
        self.fset = set(fset)
        self.log = []

    def _sub(self, e, d, t):
        return fees.FeeModel(self.data, self.mode).entry_cost(e, d, t)[0] if (d or t) else 0.0

    def entry_cost(self, e, drift_w, target_w):
        cost, det = super().entry_cost(e, drift_w, target_w)
        dS = {f: w for f, w in drift_w.items() if f not in self.fset}
        tS = {f: w for f, w in target_w.items() if f not in self.fset}
        dF = {f: w for f, w in drift_w.items() if f in self.fset}
        tF = {f: w for f, w in target_w.items() if f in self.fset}
        c_stock = self._sub(e, dS, tS)
        sd, st = sum(dF.values()), sum(tF.values())
        c_rot = self._sub(e, dF, {f: w * sd / st for f, w in tF.items()}) if (sd > 1e-12 and st > 1e-12) else 0.0
        self.log.append({"e": e, "total": cost, "stock_only": c_stock, "f_related": cost - c_stock, "f_rot": c_rot,
                         "f_vs_stock": cost - c_stock - c_rot, "dF": sd, "tF": st})
        return cost, det


# ====================== simulate ======================
def sim_cases_x(plan, nav_by_fund, months, fd, curve, fset=(), kinds=KINDS, log_full=False):
    """เหมือน run_m009.sim_cases (rf จริงผ่าน cash_curve) แต่รับ fee-data ห่อ + (ถ้า log_full) แยกต้นทุน full ต่อ entry."""
    clean = [{k: v for k, v in p.items() if k in ("t", "e", "weights")} for p in plan]
    yrs = (rr.PE - clean[0]["e"]).days / 365.25
    out = {}
    for kind in kinds:
        if kind == "full":
            fm = LogFeeModel(fd, "full", fset) if log_full else fees.FeeModel(fd, "full")
        elif kind == "nofront":
            fm = fees.FeeModel(fd, "nofront")
        elif kind == "flat":
            fm = fees.FeeModel(None, "flat", 0.005)
        else:
            fm = None
        cs = {"c0": 0.0, "c50": 0.005}.get(kind, 0.0)
        info = {}
        with rr.cash_curve(curve):
            v, tu, ev, _ = simulate.simulate_path(clean, nav_by_fund, months, cs, 0.02, include_start=True, info=info, fee_model=fm)
        ent = [x for x in info["entries"] if x["e"] <= rr.PE]
        cost = sum(x["cost"] for x in ent)
        o = {"values": v, "cost_bp_yr": cost / yrs * 1e4, "turn_yr": sum(x["turnover"] for x in ent[1:]) / yrs, "entries": ent,
             "n_cannot_buy": sum(1 for e in ev if e["type"] == "cannot_buy"), "events": ev}
        if fm is not None and kind in ("full", "nofront"):
            tot = fm.tot
            o["switch_share"] = tot["switch_vol"] / tot["sell_vol"] if tot["sell_vol"] > 0 else np.nan
            if log_full and kind == "full":
                o["feelog"] = fm.log
        out[kind] = o
    out["yrs"] = yrs
    return out


def metrics_bundle(sims, real):
    return {k: rr.metrics(sims[k]["values"], real) for k in KINDS if k in sims}


# ====================== plan ======================
def x_of(plan_entry):
    return 1.0 - float(plan_entry["weights"].get("__CASH__", 0.0))


def make_plan_F(base_plan, sel, nav_by_fund_all=None, mode_cash=False):
    """แทน __CASH__ ใน plan ของ baseline ด้วยกอง F ตาม sel[qi]=(v,info,tab) · ไม่มีกอง F ที่ผ่าน -> คง __CASH__ (fallback)."""
    out, fb_q = [], []
    for qi, p in enumerate(base_plan):
        w = dict(p["weights"])
        c = float(w.pop("__CASH__", 0.0))
        if c > 1e-12:
            v = sel[qi][0] if sel is not None else {}
            if v:
                for f, vj in v.items():
                    assert f not in w
                    w[f] = c * vj
            else:
                w["__CASH__"] = c
                fb_q.append(qi)
        out.append({"t": p["t"], "e": p["e"], "weights": w})
    return out, fb_q


def plan_checks(plan, base_plan, fset, tol_stock=1e-12):
    """ส่วนหุ้นของทุก entry = baseline (max|Δw| < 1e-12) · Σ = 1."""
    mx = 0.0
    for p, b in zip(plan, base_plan):
        assert abs(sum(p["weights"].values()) - 1.0) < 1e-9, (p["t"], sum(p["weights"].values()))
        assert p["t"] == b["t"] and p["e"] == b["e"]
        sp = {f: w for f, w in p["weights"].items() if f not in fset and f != "__CASH__" and f != RF_FUND}
        sb = {f: w for f, w in b["weights"].items() if f != "__CASH__"}
        for f in set(sp) | set(sb):
            mx = max(mx, abs(sp.get(f, 0.0) - sb.get(f, 0.0)))
    assert mx < tol_stock, mx
    return mx


# ====================== regression ======================
def regression(E, base_plan, FD, fd_comb, nav_all, sims_ref):
    reg = {}
    wref = pd.read_csv(os.path.join(RES, "RETAIL_weights.csv"))
    wref = wref[wref["model"] == "M013-GC75"]
    wref = {(pd.Timestamp(r.t), r.FundCode): r.weight for r in wref.itertuples()}
    # 1) selector = CASH ผ่านโค้ดใหม่ทั้งเส้นทาง (make_plan_F ด้วย sel=None -> __CASH__ คงเดิม)
    plan_c, fb_q = make_plan_F(base_plan, None)
    mine = {(p["t"], f): w for p in plan_c for f, w in p["weights"].items() if w > 1e-12}
    keys = set(wref) | set(mine)
    d1 = max(abs(wref.get(k, 0.0) - mine.get(k, 0.0)) for k in keys)
    reg["r1_max_dw_vs_RETAIL_weights"] = float(d1)
    reg["r1_n_key_mismatch"] = len([k for k in keys if (k in wref) != (k in mine)])
    sims = sim_cases_x(plan_c, nav_all, E["months"], fd_comb, E["real"], kinds=KINDS)
    MR = metrics_bundle(sims, E["real"])
    ref = pd.read_csv(os.path.join(RES, "RETAIL_results.csv")).set_index("model").loc["M013-GC75"]
    reg["r1_sharpe"] = {"full": MR["full"]["sharpe"], "nofront": MR["nofront"]["sharpe"], "c0": MR["c0"]["sharpe"]}
    reg["r1_ref"] = {"full": float(ref["new_sharpe_full"]), "nofront": float(ref["new_sharpe_nofront"]), "c0": float(ref["new_sharpe_c0"])}
    reg["r1_max_dsharpe"] = max(abs(reg["r1_sharpe"][k] - reg["r1_ref"][k]) for k in reg["r1_sharpe"])
    reg["r1_ok"] = bool(d1 < 1e-9 and reg["r1_n_key_mismatch"] == 0 and reg["r1_max_dsharpe"] < 5e-7)
    # 2) กองสังเคราะห์ __RF_FUND__ = real.cum รายวัน, fee 0, AMC เฉพาะตัว
    cum = E["real"].cum
    nav_rf = cum.copy()
    nav_syn = {**nav_all, RF_FUND: nav_rf}
    fd_syn = CombinedFee(fd_comb.fd_e, fd_comb.fd_f, fd_comb.f_codes, extra_zero=[RF_FUND], extra_amc={RF_FUND: "__RF_AMC__"})
    plan_s = []
    for p in plan_c:
        w = dict(p["weights"])
        if "__CASH__" in w:
            w[RF_FUND] = w.pop("__CASH__")
        plan_s.append({"t": p["t"], "e": p["e"], "weights": w})
    sims_s = sim_cases_x(plan_s, nav_syn, E["months"], fd_syn, E["real"], kinds=["full", "nofront", "c0"])
    MRs = metrics_bundle(sims_s, E["real"])
    reg["r2_sharpe_full"] = MRs["full"]["sharpe"]
    reg["r2_d_full"] = abs(MRs["full"]["sharpe"] - MR["full"]["sharpe"])
    reg["r2_d_nofront"] = abs(MRs["nofront"]["sharpe"] - MR["nofront"]["sharpe"])
    reg["r2_d_c0"] = abs(MRs["c0"]["sharpe"] - MR["c0"]["sharpe"])
    reg["r2_ok"] = bool(reg["r2_d_full"] < 0.005)
    reg["_sims_base"] = sims
    reg["_MR_base"] = MR
    return reg


# ====================== รายงานเสริม ======================
def exec_price(nav_all, f, e):
    r = simulate._exec_nav(nav_all, f, e)
    return None if r is None else r[0]


def leg_series(plan, qlist, nav_all, months, real, funds_of, bound):
    """ผลตอบแทนรายเดือนของ "ขา" (ตะกร้า) — คืน DataFrame: month, r (ก่อนค่าธรรมเนียม), rf (เดือนเดียวกัน), days, q.
    ตะกร้า = กองใน funds_of(qi) (dict กอง->น้ำหนักสัมพัทธ์) ซื้อที่ NAV วัน e ถือจนสิ้นไตรมาส (drift จริง) · ซื้อไม่ได้ -> rf"""
    rows = []
    n = len(plan)
    for qi in qlist:
        e = plan[qi]["e"]
        ne = plan[qi + 1]["e"] if qi + 1 < n else (months[-1] + pd.Timedelta(days=1))
        wts = funds_of(qi)
        if not wts:
            continue
        tot = sum(wts.values())
        wts = {f: w / tot for f, w in wts.items()}
        px = {}
        for f in wts:
            pr = exec_price(nav_all, f, e)
            px[f] = pr
        ms = [m for m in months if e <= m < ne and m <= bound]
        prev_val, prev_d = 1.0, e
        for m in ms:
            val = 0.0
            for f, w in wts.items():
                if px[f] is None:
                    val += w * real.growth(e, m)
                else:
                    p_m, _ = simulate._nav_last(nav_all, f, m)
                    val += w * p_m / px[f]
            rows.append({"month": m, "qi": qi, "r": val / prev_val - 1.0, "rf": real.growth(prev_d, m) - 1.0, "days": (m - prev_d).days})
            prev_val, prev_d = val, m
    return pd.DataFrame(rows)


def ann_from(df, col):
    g = float(np.prod(1.0 + df[col].to_numpy()))
    days = int(df["days"].sum())
    return g ** (365.0 / days) - 1.0 if days > 0 else np.nan


def daily_index_2022(plan, sel_funds, nav_all, calendar, bound_start, bound_end, real):
    """ดัชนีตะกร้า F รายวัน (วันปฏิทินดัชนี) 2022-01-01..2022-12-31 ต่อไตรมาสที่ถือ F · ต่อเนื่องข้ามไตรมาส · คืน (series, maxDD, ret, rf_ret, first, last)."""
    n = len(plan)
    lvl, pieces, last_level = None, [], 1.0
    for qi in range(n):
        wts = sel_funds(qi)
        if not wts:
            continue
        e = plan[qi]["e"]
        ne = plan[qi + 1]["e"] if qi + 1 < n else pd.Timestamp("2026-12-31")
        days = calendar[(calendar >= e) & (calendar < ne) & (calendar >= bound_start) & (calendar <= bound_end)]
        if len(days) == 0:
            continue
        tot = sum(wts.values())
        px = {f: exec_price(nav_all, f, e) for f in wts}
        vals = []
        for d in days:
            v = 0.0
            for f, w in wts.items():
                if px[f] is None:
                    v += (w / tot) * real.growth(e, d)
                else:
                    p_d, _ = simulate._nav_last(nav_all, f, d)
                    v += (w / tot) * p_d / px[f]
            vals.append(v)
        s = pd.Series(vals, index=days) * last_level
        last_level = float(s.iloc[-1])
        pieces.append(s)
    if not pieces:
        return None
    s = pd.concat(pieces)
    s = s[~s.index.duplicated()]
    dd = float((s / s.cummax() - 1).min())
    first, last = s.index[0], s.index[-1]
    return {"series": s, "maxdd": dd, "ret": float(s.iloc[-1] / 1.0 - 1.0), "rf_ret": real.growth(first, last) - 1.0, "first": first.date(), "last": last.date()}


def daily_vol_and_maxabs(nav_all, f, a, b):
    s = nav_all[f].loc[a:b]
    r = np.log(s).diff().dropna()
    return (float(r.std(ddof=1) * np.sqrt(252)) if len(r) > 2 else np.nan), (float(r.abs().max()) if len(r) else np.nan)


# ====================== trials / ALL_RESULTS ======================
def log_trial15(name, n, params, MR, sims_r, ci, dsr, d, verdict, note_extra):
    now = pd.Timestamp.now().isoformat()
    txt = open(TRIALS_CSV, encoding="utf-8", newline="").read()
    assert f"\n{name}," not in "\n" + txt, f"{name} มีใน trials.csv แล้ว"
    mn, so = MR["full"], sims_r["full"]
    note = (f"{name}: universe RETAIL (cut fst_lowbuy>100000) + real rf + fees FeeData(legacy=False) แยก E/F; Sharpe (real rf; sd(r)): 0%={MR['c0']['sharpe']:.3f} 0.5%={MR['c50']['sharpe']:.3f} "
            f"full={mn['sharpe']:.3f} nofront={MR['nofront']['sharpe']:.3f}; paired dSharpe full vs M013-GC75 retail 0.779 {d[2]:+.4f} CI ({d[0]:.3f};{d[1]:.3f}); CI95 ({ci[0]:.3f};{ci[1]:.3f}); "
            f"DSR@{N_TRIALS_FINAL}={dsr:.4f}; verdict={verdict}; {note_extra}; n_months=45; WARN: F-fund Sharpe overstated (smooth NAV/credit-liquidity risk not realised 2022-25); "
            f"WARN: path luck quarter-level (SETTLEMENT_sensitivity); WARN: FundProfile snapshot not PIT + F survivorship; sharpe column = REAL rf; deflated_sharpe column = DSR@{N_TRIALS_FINAL}")
    vals = [name, now, "M015_bond_fund_cash.md", params, "2022-03-31", "2025-12-31", "BOT policy rate daily (TH_POLICY_RATE.csv)",
            "real fees SecFundFee FEEUH (full; FeeData legacy=False; E/F separate)", round(mn["sharpe"], 4), round(mn["cagr"], 4), round(mn["vol"], 4), round(mn["max_dd"], 4),
            round(so["turn_yr"], 4), n, round(dsr, 4), "ok", note]
    line = ",".join(str(v).replace(",", ";").replace("\n", " ") for v in vals)
    with open(TRIALS_CSV, "a", encoding="utf-8", newline="") as f:
        if not txt.endswith("\n"):
            f.write("\r\n")
        f.write(line + "\r\n")


def log_all_results15(name, idea, MR, sims_r, d):
    p = os.path.join(RES, "ALL_RESULTS.csv")
    atxt = open(p, encoding="utf-8", newline="").read()
    assert f",{name}," not in atxt, f"{name} มีใน ALL_RESULTS แล้ว"
    hdr = atxt.splitlines()[0].split(",")
    row = {h: "" for h in hdr}
    row.update({"round": "M015", "trial": name, "idea": idea.replace(",", ";"), "measurement": "new", "post_hoc": "no",
                "sharpe_fee_full_retail_realrf": f"{MR['full']['sharpe']:.4f}", "sharpe_fee_nofront_retail_realrf": f"{MR['nofront']['sharpe']:.4f}",
                "sharpe_cost0_retail_realrf": f"{MR['c0']['sharpe']:.4f}", "cagr_fee_full_retail_realrf": f"{MR['full']['cagr']:.4f}",
                "maxdd_fee_full_retail_realrf": f"{MR['full']['max_dd']:.4f}", "sharpe_2022_fee_full_retail_realrf": f"{MR['full']['sharpe_2022']:.4f}"})
    with open(p, "a", encoding="utf-8", newline="") as f:
        if not atxt.endswith("\n"):
            f.write("\n")
        f.write(",".join(row[h] for h in hdr) + "\n")


def fee_flags(fd_f, fc, e):
    """อัตรา FF/BF/SI/SO (%) ณ e ของกอง F + ใช้ median fallback หรือไม่ (ไม่แตะ n_fallback ของ FeeData)."""
    res, nfb = {}, 0
    for code in fees.CODES:
        sr = fd_f.series.get((fc, code))
        fb = True
        v = fd_f.median[code]
        if sr is not None:
            dates, vals = sr
            i = np.searchsorted(dates, np.datetime64(e), side="right") - 1
            vv = vals[max(i, 0)]
            if np.isfinite(vv):
                v, fb = float(vv), False
        res[code], nfb = v, nfb + int(fb)
    return {"FF": res["FF"], "BF": res["BF"], "SI": res["SI"], "SO": res["SO"], "fee_fallback_n": nfb}


def first_week_split(plan, qi, funds, nav_all, real, months_end):
    """ผลตอบแทนส่วนเกินเทียบ rf ของตะกร้า F: สัปดาห์แรกหลัง e (7 วันปฏิทิน) vs ส่วนที่เหลือของไตรมาส (สัดส่วนของขา F)."""
    e = plan[qi]["e"]
    ne = plan[qi + 1]["e"] if qi + 1 < len(plan) else months_end
    tot = sum(funds.values())
    px = {f: exec_price(nav_all, f, e) for f in funds}
    def val(d):
        v = 0.0
        for f, w in funds.items():
            if px[f] is None:
                v += w / tot * real.growth(e, d)
            else:
                p_d, _ = simulate._nav_last(nav_all, f, d)
                v += w / tot * p_d / px[f]
        return v
    d1 = e + pd.Timedelta(days=7)
    v1, v2 = val(d1), val(ne)
    r1 = v1 - 1.0 - (real.growth(e, d1) - 1.0)
    r2 = (v2 / v1 - 1.0) - (real.growth(d1, ne) - 1.0)
    return r1, r2


def random_diag(rows, FD, base_plan, ER, nav_all, fd_comb, fset_all, risk_map, n=40):
    """sanity (ไม่ใช่ trial): เลือก family F แบบสุ่ม (1 กอง) จาก I_t^F ที่ผ่านคุณภาพ · n seeds · และ "สัญญาณอนาคต +1 ไตรมาส" (ตั้งใจ look-ahead) ของ FSR1/FAUM."""
    out = {"rand_all": [], "rand_mmf": []}
    reps_by_q = []
    for r in rows:
        it, qual = r["it"], r["qual"]
        ok = set(qual.index[qual["pass_q1"] & qual["pass_q2"]])
        it = it[it["family"].isin(ok)]
        reps = it.sort_values(["R12_1", "FundCode"], ascending=[False, True]).groupby("family", sort=False).head(1)
        reps_by_q.append(reps)
    for kind in ("rand_all", "rand_mmf"):
        for seed in range(n):
            rng = np.random.default_rng(1000 + seed)
            sel = {}
            for qi, reps in enumerate(reps_by_q):
                pool = reps if kind == "rand_all" else reps[reps["FundCode"].map(risk_map).isin(["1", "2"])]
                sel[qi] = ({pool.iloc[int(rng.integers(len(pool)))]["FundCode"]: 1.0}, {}, pd.DataFrame()) if len(pool) else ({}, {}, pd.DataFrame())
            pl, _ = make_plan_F(base_plan, sel)
            sm = sim_cases_x(pl, nav_all, ER["months"], fd_comb, ER["real"], kinds=["full"])
            out[kind].append(rr.metrics(sm["full"]["values"], ER["real"])["sharpe"])
    return out


def pct(x, d=2):
    return "—" if x is None or (isinstance(x, float) and not np.isfinite(x)) else f"{x*100:.{d}f}%"


def write_md(out, MRb, ci_b, sims_b, base_plan, sels, FB, Sel, FW, LF, reg, DIAG, FD, fd_f, ER, PLAN, SIMS):
    L = []
    A = L.append
    mb = MRb["full"]
    dsr_b = rr.dsr_s(mb["r"], mb["rfm"], N_TRIALS_FINAL)
    A("# M015 — กองตราสารหนี้ policy F แทนเงินสดในขาที่ไม่ใช่หุ้นของ M013-GC75 (universe รายย่อย)")
    A("")
    A("trials 30 `M015-FSR3` · 31 `M015-FSR1` · 32 `M015-FAUM` (n_trials สะสม = 32 → DSR@32) · spec `specs/M015_bond_fund_cash.md` + 'การตัดสินใจของผู้ใช้ 2026-10-06' · รัน `backtest/run_m015.py`")
    A("วัดด้วย **rf จริง** (นโยบาย กนง. รายวัน, ตัวหาร sd(r)) · ค่าธรรมเนียม **SecFundFee FEEUH full, `FeeData(legacy=False)`** (ฝั่งหุ้น = `FeeData(codes หุ้น)` เดิม, ฝั่ง F = `FeeData(ทุก class policy F)` แยก) · "
      "universe รายย่อย (ตัด class ขั้นต่ำซื้อครั้งแรก > 100,000 บาท 8 class) · ช่วง primary 2022-03-31 → 2025-12-31 (45 เดือน) · baseline = **M013-GC75 บน universe รายย่อย**")
    A("")
    A("## 0. สรุปผู้บริหาร")
    A("")
    A("| trial | Sharpe full | Δ vs baseline | CI95% paired Δ | ผลตามเกณฑ์ (Δ ≥ 0) | Δ ที่ 0% | Δ nofront | DSR@32 |")
    A("|---|---|---|---|---|---|---|---|")
    A(f"| baseline M013-GC75 retail | **{mb['sharpe']:.3f}** | — | — | — | — | — | {dsr_b:.4f} |")
    for tid in TRIAL_IDS:
        o = out[tid]; d = o["d"]
        rule = "ผ่าน" if d[2] >= 0 else "ไม่ผ่าน"
        if d[0] > 0: rule += " (ดีกว่าอย่างมีนัย)"
        if d[1] < 0: rule += " (แย่กว่าอย่างมีนัย: CI ไม่คร่อม 0)"
        A(f"| **{tid}** | {o['m']['full']['sharpe']:.3f} | {d[2]:+.4f} | [{d[0]:+.3f}, {d[1]:+.3f}] | {rule} | {o['dn']['c0']:+.4f} | {o['dn']['nofront']:+.4f} | {o['dsr']:.4f} |")
    A("")
    fa = out["M015-FAUM"]["d"][2]
    A(f"- ตามที่ผู้ใช้ตัดสินใจก่อนเห็นผล: **ใช้ M015-FAUM เสมอ ยกเว้น Δ < −0.10** → Δ(FAUM) = {fa:+.4f} → {'ไม่เข้าเงื่อนไขคุยใหม่ (Δ ≥ −0.10)' if fa >= -0.10 else 'Δ < −0.10 ต้องคุยใหม่'}. FSR3/FSR1 รายงานตามเกณฑ์ปกติ (Δ ≥ 0) — ทั้งสามตัว **ไม่ถึงเกณฑ์ Δ ≥ 0** (ไม่มีตัวไหนสูงกว่า baseline); **ห้ามอ้างตัวใดเป็นผลงาน** · ไม่มีตัวไหนช่วยให้ถึง 0.95")
    A("- ทั้งสามตัว: ส่วนหุ้นเหมือน baseline ทุกบิต (max|Δw| = 0) → Δ มาจากขา F ล้วน")
    A("")
    A("## 1. Regression (ผ่านทั้งหมด ก่อนนับ trial)")
    A("")
    A("| ข้อ | ตรวจ | ผล | เกณฑ์ |")
    A("|---|---|---|---|")
    A(f"| 1 | selector = CASH (ขา F = `__CASH__`) ผ่านโค้ดใหม่ทั้งเส้นทาง (nav_by_fund_all + FeeData ห่อ): น้ำหนักเทียบ `RETAIL_weights.csv` (M013-GC75) | max|Δw| = {reg['r1_max_dw_vs_RETAIL_weights']:.1e}, key ไม่ตรง {reg['r1_n_key_mismatch']} | < 1e-9 |")
    A(f"| 1 | Sharpe full / nofront / c0 เทียบ `RETAIL_results.csv` new_* | {reg['r1_sharpe']['full']:.6f} / {reg['r1_sharpe']['nofront']:.6f} / {reg['r1_sharpe']['c0']:.6f} (อ้างอิง {reg['r1_ref']['full']:.6f} / {reg['r1_ref']['nofront']:.6f} / {reg['r1_ref']['c0']:.6f}) · max|ΔSharpe| = {reg['r1_max_dsharpe']:.1e} | < 5e-7 |")
    A(f"| 2 | กองสังเคราะห์ `__RF_FUND__` (NAV รายวัน = RFCurve.cum, ค่าธรรมเนียม 0, AMC เฉพาะตัว) | Sharpe full {reg['r2_sharpe_full']:.6f} · ต่างจาก baseline {reg['r2_d_full']:.1e} (nofront {reg['r2_d_nofront']:.1e}, c0 {reg['r2_d_c0']:.1e}) | < 0.005 |")
    A("| 3 | ส่วนหุ้นของทุก trial = baseline ทุก entry · Σ = 1 · กอง F ที่เลือกอยู่ใน I_t^F ของไตรมาสนั้น + ผ่านเกณฑ์ snapshot + ไม่ซ้ำกับกองหุ้นใน nav_clean | max|Δw| ส่วนหุ้น = 0.0 ทุก trial (assert < 1e-12) | < 1e-12 |")
    A("| 3 | ไม่มีข้อมูล > t: คำนวณ I_t^F + Quality ใหม่จาก NAV ที่ตัด ≤ t ทุกไตรมาส (15) เทียบกับตัวหลัก | max|Δ signal| = 0 · ชุดกองต่างกัน 0 ไตรมาส · AUM_fam/ผ่านเกณฑ์ตรงกัน | = 0 |")
    A("")
    A("## 2. สิ่งที่ validator ตีความเอง (ต้องตรวจ)")
    A("")
    A("1. **เพดานล่าง vol52 ของกองหุ้น (`< 0.02 → NaN`) ใช้กับกอง F ไม่ได้**: spec ระบุ 'สูตรเดียวกับหุ้น' แต่ `fs.QuarterContext.fund_signal` ตัดกองที่ vol52 < 2% ออกทั้งหมด → กองตลาดเงิน (vol จริง ~0.01–0.1%) หายหมด "
      "(ตัวเลขใน §2 ของ spec 'Risk Level 1–2 ผ่าน 19 → 28 class' นับก่อนขั้นสัญญาณ) → F-AUM จะเลือกกองตลาดเงินไม่ได้เลยและตก fallback vol52 เสมอ (ขัดเจตนา spec). "
      "ใช้สัญญาณ F **เหมือนเดิมทุกบรรทัด** (R12_1, vol52 รายสัปดาห์ 52, n_obs ≥ 40, zero_frac ≤ 0.20) ยกเว้นเพดาน → `vol52 > 0`. ตัวนับเปรียบเทียบ (`M015_floor_diagnostic.csv`):")
    A("")
    A("| ไตรมาส t | |I_t| ตามเพดานเดิม | |I_t| ที่ใช้ (vol52>0) | กองตลาดเงิน (Risk 1–2) ตามเพดานเดิม | กองตลาดเงินที่ใช้ |")
    A("|---|---|---|---|---|")
    for r in LF.itertuples():
        A(f"| {r.t} | {r.n_I_literal_floor} | {r.n_I_f_signal} | {r.n_mmf_literal} | {r.n_mmf_f_signal} |")
    A("")
    A("   → **ผู้ใช้/quant-modeler ควรยืนยัน** การตีความนี้ (ถ้าต้องการอ่านตรงตัวตามเพดานเดิม = F-AUM ตก fallback ทุกไตรมาสและเลือกกองที่ไม่ใช่ตลาดเงิน — จะเป็นเวอร์ชันใหม่ +trial)")
    A("2. `FeeData` ฝั่ง F = ทุก class policy F ใน FundProfile (662) → median FF/BF/SI/SO = 0.000% (ตรง spec §2). อัตราของกองที่ถูกเลือกดู §6 (คอลัมน์ `fee_fallback_n`)")
    A("3. Quality/AUM_fam ของ F ใช้ NAV ทุก class F (รวม class ที่ผ่านเกณฑ์ snapshot ไม่ได้) เหมือนฝั่งหุ้น; เกณฑ์ snapshot (Tax Type ว่าง, buy period = N, Retail Type = R, ขั้นต่ำ ≤ 100,000 — ค่าว่างถือว่าไม่ผ่าน, ชื่อไม่มี Not for Retail/TEST) ตัด class ก่อนเลือก class ตัวแทนของ family")
    A("4. `Fund Risk Level` ของ F-AUM ตรวจที่ class ตัวแทนของ family (SR12′ สูงสุดใน family) · เสมอกัน → FundCode ตัวอักษร · fallback vol52 (ไม่ถูกใช้เลย): quantile 0.25 ของ vol52 ระดับ class ใน I_t^F ผ่านคุณภาพ")
    A("5. spike rule §4.2 ใช้ครั้งเดียวต่อกอง จากค่าเดิม (ไม่ cascade): แก้ 438 จุด ใน 134 กอง (จาก 471 กอง/321,383 แถว) · ตัวแก้ spike ของกองหุ้นไม่ถูกเรียก")
    A("6. 'ขา F เทียบเงินสด' คำนวณจากตะกร้า F ที่ซื้อที่ NAV วัน e (drift ตามจริงภายในไตรมาส) เฉพาะเดือนที่ขา F > 0 (9 ไตรมาส = 27 เดือน); 'หลังค่าธรรมเนียม' = หักค่าธรรมเนียมส่วนที่เกิดจากขา F ของ entry นั้น (÷ น้ำหนักขา F) ออกจากเดือนแรกของไตรมาส")
    A("")
    A("## 3. ผลหลัก (full = ค่าธรรมเนียมจริง · rf จริง)")
    A("")
    A("| โมเดล | Sharpe | CAGR | vol | maxDD | maxDD ช่วง 2022 (รายเดือน) | Sharpe 2022 | Sharpe 2023-07..25 | CI95% Sharpe | DSR@32 | cost bp/ปี | turnover/ปี |")
    A("|---|---|---|---|---|---|---|---|---|---|---|---|")
    A(f"| baseline M013-GC75 retail | {mb['sharpe']:.3f} | {mb['cagr']:.4f} | {mb['vol']:.4f} | {mb['max_dd']:.4f} | {r13.mdd_2022(sims_b['full']['values']):.4f} | {mb['sharpe_2022']:.3f} | {mb['sharpe_2307_2512']:.3f} | [{ci_b[0]:.2f}, {ci_b[1]:.2f}] | {dsr_b:.4f} | {sims_b['full']['cost_bp_yr']:.1f} | {sims_b['full']['turn_yr']:.3f} |")
    for tid in TRIAL_IDS:
        o = out[tid]; m = o["m"]["full"]
        A(f"| **{tid}** | {m['sharpe']:.3f} | {m['cagr']:.4f} | {m['vol']:.4f} | {m['max_dd']:.4f} | {o['mdd22']:.4f} | {m['sharpe_2022']:.3f} | {m['sharpe_2307_2512']:.3f} | [{o['ci'][0]:.2f}, {o['ci'][1]:.2f}] | {o['dsr']:.4f} | {o['S']['full']['cost_bp_yr']:.1f} | {o['S']['full']['turn_yr']:.3f} |")
    A("")
    A("turnover รวมการสลับกอง F ด้วย (นิยามเดียวกับ baseline: ½Σ|Δw| ขากอง ไม่รวม `__CASH__`) → สูงกว่า baseline โดยโครงสร้าง")
    A("")
    A("### Sharpe/CAGR/vol/maxDD ตามกรณีต้นทุน (rf จริง)")
    A("")
    A("| โมเดล | กรณี | Sharpe | CAGR | vol | maxDD |")
    A("|---|---|---|---|---|---|")
    lab = {"c0": "0%", "c50": "0.5%/ข้าง", "flat": "flat 0.5% (fee model)", "full": "full", "nofront": "nofront"}
    rows_ = [("baseline", MRb)] + [(tid, out[tid]["m"]) for tid in TRIAL_IDS]
    for nm, M in rows_:
        for k in ("c0", "c50", "flat", "full", "nofront"):
            A(f"| {nm} | {lab[k]} | {M[k]['sharpe']:.3f} | {M[k]['cagr']:.4f} | {M[k]['vol']:.4f} | {M[k]['max_dd']:.4f} |")
    A("")
    A("## 4. ขา F เทียบเงินสด rf จริง (เฉพาะ 27 เดือนที่ขา F > 0)")
    A("")
    A("| trial | ผลตอบแทนทบต้น/ปี ก่อนค่าธรรมเนียม | หลังค่าธรรมเนียมขา F | rf จริงช่วงเดียวกัน | ส่วนต่าง (bp/ปี) ก่อน | หลัง | vol/ปี ขา F | corr กับขาหุ้น (รายเดือน) |")
    A("|---|---|---|---|---|---|---|---|")
    for tid in TRIAL_IDS:
        g = out[tid]["leg"]
        A(f"| {tid} | {pct(g['ann_F_before'])} | {pct(g['ann_F_after'])} | {pct(g['ann_rf'])} | {g['excess_bp_before']:+.0f} | {g['excess_bp_after']:+.0f} | {pct(g['vol_F'])} | {g['corr_stock']:+.2f} |")
    A("")
    A("(rf รายเดือนเอง vol ≈ 0.19%/ปี เพราะอัตรานโยบายเปลี่ยนเป็นขั้น) · ⚠️ ตัวอย่างสั้น 27 เดือน/9 ไตรมาส ส่วนต่าง ±bp ไม่มีนัยสถิติ")
    A("")
    A("## 5. ปี 2022 (ดอกเบี้ยขาขึ้น) — ขา F")
    A("")
    A("ช่วงที่จำลองมีขา F ในปี 2022 = ตั้งแต่ e แรก (2022-04-04) ถึง 2022-12-30 (ก่อนหน้านั้นไม่มีพอร์ตในการจำลอง) · ดัชนีตะกร้า F รายวันจาก NAV ต่อเนื่องข้ามไตรมาส (x_t 2022: 0.50/0.25/0.25 → ขา F 50/75/75%)")
    A("")
    A("| trial | maxDD ดัชนี F รายวัน | ผลตอบแทนช่วง (ไม่ทบเป็นปี) | rf จริงช่วงเดียวกัน | maxDD พอร์ตรวมช่วง 2022 (รายเดือน) | baseline | Sharpe 2022 พอร์ต | baseline |")
    A("|---|---|---|---|---|---|---|---|")
    for tid in TRIAL_IDS:
        o = out[tid]; di = o["di"]
        A(f"| {tid} | {pct(di['maxdd'])} | {pct(di['ret'])} | {pct(di['rf_ret'])} | {o['mdd22']:.4f} | {o['mdd22_b']:.4f} | {o['m']['full']['sharpe_2022']:.3f} | {mb['sharpe_2022']:.3f} |")
    A("")
    A("## 6. ต้นทุนเพิ่ม (full − baseline full)")
    A("")
    A("| trial | cost bp/ปี | Δ vs baseline | แยก: ขาหุ้น (เหมือนเดิม) | F↔F (หมุนชื่อ F ที่ขา F ขนาดคงที่) | หุ้น↔F (เปลี่ยนขนาดขา F/เข้า-ออก F รวมช่องทางสับเปลี่ยน) | สัดส่วนปริมาณขายที่ไปทางสับเปลี่ยน | เปลี่ยนตัว F ระหว่างไตรมาสที่ถือ F ต่อเนื่อง (ครั้ง) |")
    A("|---|---|---|---|---|---|---|---|")
    base_cost = float(sims_b["full"]["cost_bp_yr"])
    for tid in TRIAL_IDS:
        o = out[tid]; cs = o["cost_split"]
        A(f"| {tid} | {cs['total']:.1f} | {cs['total']-base_cost:+.2f} | {cs['stock_only']:.1f} | {cs['f_rot']:.2f} | {cs['f_vs_stock']:+.2f} | {o['switch_share']*100:.1f}% | {o['n_F_changes_consecutive']} |")
    A(f"| baseline | {base_cost:.1f} | — | — | — | — | {sims_b['full'].get('switch_share', float('nan'))*100:.1f}% | — |")
    A("")
    A("**ค่าธรรมเนียมจริงของกอง F ที่ถูกเลือก (คอลัมน์ `fee_fallback_n` = จำนวนรหัสจาก 4 ที่ต้องใช้ median fallback = 0% เพราะไม่มีข้อมูล)**")
    held = Sel[(Sel["held_in_plan"] == True)] if "held_in_plan" in Sel.columns else Sel
    ff = held.groupby("model").agg(n_rows=("FundCode", "size"), n_fee_fallback_rows=("fee_fallback_n", lambda x: int((x > 0).sum())), fee_fallback_codes=("fee_fallback_n", "sum"), max_FF=("FF", "max"), max_BF=("BF", "max"), max_SI=("SI", "max"), max_SO=("SO", "max")).reset_index()
    A("")
    A("| trial | แถว (กอง×ไตรมาสที่ถือ) | แถวที่มี fallback ≥ 1 รหัส | รหัส fallback รวม | max FF% | max BF% | max SI% | max SO% |")
    A("|---|---|---|---|---|---|---|---|")
    for r in ff.itertuples():
        A(f"| {r.model} | {r.n_rows} | {r.n_fee_fallback_rows} | {int(r.fee_fallback_codes)} | {r.max_FF:.3f} | {r.max_BF:.3f} | {r.max_SI:.3f} | {r.max_SO:.3f} |")
    A("")
    A("## 7. กอง F ที่ถูกเลือกต่อไตรมาส (เฉพาะไตรมาสที่ถือ F จริง = x_t < 1 · 9 ไตรมาส) · ตารางเต็มทุกไตรมาสใน `M015_selected_funds.csv`")
    A("")
    A("ตกเป็น `__CASH__` (ไม่มี F ผ่าน): FSR3 " + str(FB['M015-FSR3']) + " · FSR1 " + str(FB['M015-FSR1']) + " · FAUM " + str(FB['M015-FAUM']) + " ไตรมาส (รายการ qi ที่ตก; ว่าง = ไม่มี) · F-AUM ใช้ fallback vol52: " + str(int(Sel[(Sel['model'] == 'M015-FAUM')]['fallback_vol'].fillna(False).sum())) + " ไตรมาส")
    A("")
    A("| trial | t | x_t | FundCode | บลจ. | Risk | FIF | AUM_fam (พันล้านบาท) | SR12′_F | vol52 | น้ำหนักใน F | |I_t^F| | spike ที่แก้ (ทั้งประวัติ) | vol รายวัน/ปี ในไตรมาสที่ถือ | |r| รายวันสูงสุด |")
    A("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for r in held.itertuples():
        A(f"| {r.model} | {r.t} | {r.x_t:.2f} | {r.FundCode} | {r.amc} | {r.risk} | {r.fif} | {r.aum_fam/1e9:.1f} | {r.SR12p:.2f} | {r.vol52:.4f} | {r.v_j:.2f} | {r.n_I} | {int(r.fund_n_spike_fixed_all)} | {r.hold_q_daily_vol:.4f} | {r.hold_q_max_abs_dret:.4f} |")
    A("")
    A("**spike หลุดเข้าพอร์ตหรือไม่**: |r| รายวันสูงสุด > 1% ในกองที่ถือ = " + ", ".join(sorted({f"{r.model} {r.FundCode} {r.t} ({r.hold_q_max_abs_dret*100:.1f}%)" for r in held.itertuples() if r.hold_q_max_abs_dret > 0.01})) +
      " · กรณี PRINCIPAL DPLUS-X 2023-05-26 (−9.2% วันเดียว แล้วฟื้น +5.7% วันที่ 2023-06-12) **เป็นเหตุการณ์เครดิตจริง** (ไม่กลับตัวภายใน 1 จุด ตรวจกับ nav_history_db ดิบ: แถวเดียวกันทุก UpdateTime) ไม่ใช่ spike ข้อมูล → rule §4.2 ไม่แก้ (ถูกต้อง) · นี่คือความเสี่ยงเครดิตที่ป้ายเตือนระบุ — **เกิดจริง 1 ครั้งในตัวอย่างและเข้าพอร์ต FSR3 ไตรมาส 2023-03**")
    A("")
    A("## 8. Δ ต่อไตรมาส (Σ Δr รายเดือนของไตรมาสนั้น, พอร์ต − baseline) · drop-best-quarter · path luck")
    A("")
    A("| t | x_t | " + " | ".join(TRIAL_IDS) + " |")
    A("|---|---|---|---|---|")
    for qi in range(15):
        vals = []
        for tid in TRIAL_IDS:
            tab = out[tid]["qd"]["tab"]
            vals.append(f"{tab.loc[qi, 'sum_dret']*100:+.3f}%" if qi in tab.index else "—")
        A(f"| {ER['q15'][qi].date()} | {x_of(base_plan[qi]):.2f} | " + " | ".join(vals) + " |")
    A("")
    A("| trial | Σ Δr ไตรมาสดีสุด (t) | แย่สุด (t) | Sharpe(พอร์ต) / Sharpe(baseline) เมื่อตัดไตรมาสดีสุด | Δ หลังตัด | Δ เดิม |")
    A("|---|---|---|---|---|---|")
    for tid in TRIAL_IDS:
        o = out[tid]; q = o["qd"]
        A(f"| {tid} | {q['tab'].loc[q['best_q'], 'sum_dret']*100:+.3f}% ({ER['q15'][q['best_q']].date()}) | {q['tab'].loc[q['worst_q'], 'sum_dret']*100:+.3f}% ({ER['q15'][q['worst_q']].date()}) | "
          f"{q['drop'][0]:.3f} / {q['drop'][1]:.3f} | {q['drop'][0]-q['drop'][1]:+.4f} | {o['d'][2]:+.4f} |")
    A("")
    A("**path luck (สัปดาห์แรก 7 วันหลัง e เทียบส่วนที่เหลือ)** — ผลตอบแทนส่วนเกินเทียบ rf ของตะกร้า F × น้ำหนักขา F (ระดับพอร์ต) · ไตรมาสที่ |ส่วนต่างรวม| ≥ 0.10% ของพอร์ต:")
    A("")
    A("| trial | t (ไตรมาส) | 7 วันแรก | ส่วนที่เหลือ | รวม | สัดส่วน 7 วันแรก |")
    A("|---|---|---|---|---|---|")
    for r in FW.itertuples():
        tot = r.port_contrib_first7d + r.port_contrib_rest
        if abs(tot) >= 0.001:
            A(f"| {r.model} | {r.t} | {r.port_contrib_first7d*100:+.3f}% | {r.port_contrib_rest*100:+.3f}% | {tot*100:+.3f}% | {r.port_contrib_first7d/tot*100:.0f}% |" if tot != 0 else "")
    A("")
    A("(ไตรมาส 2025-03-31 = 'เม.ย. 2025' ตามที่ถาม — ดูแถว t = 2025-03-31)")
    A("")
    A("## 9. Sanity (ไม่ใช่ trial · ไม่นับใน n_trials)")
    A("")
    rall, rmm = np.array(DIAG["rand_all"]), np.array(DIAG["rand_mmf"])
    A(f"- เลือก F แบบสุ่ม 1 กองต่อไตรมาสจาก I_t^F (ผ่านคุณภาพ) 40 seeds: Sharpe full เฉลี่ย {rall.mean():.4f} (sd {rall.std(ddof=1):.4f}, ช่วง {rall.min():.3f}–{rall.max():.3f}) · baseline {mb['sharpe']:.4f}")
    A(f"- สุ่มเฉพาะกองตลาดเงิน (Risk 1–2) 40 seeds: เฉลี่ย {rmm.mean():.4f} (sd {rmm.std(ddof=1):.4f}, ช่วง {rmm.min():.3f}–{rmm.max():.3f}) · F-AUM = {out['M015-FAUM']['m']['full']['sharpe']:.4f}")
    A(f"- ใช้สัญญาณ **อนาคต +1 ไตรมาส** (ตั้งใจ look-ahead) กับ FSR3/FSR1/FAUM: Sharpe {DIAG['future_shift']['FSR3']:.4f} / {DIAG['future_shift']['FSR1']:.4f} / {DIAG['future_shift']['FAUM']:.4f} (ของจริง {out['M015-FSR3']['m']['full']['sharpe']:.4f} / {out['M015-FSR1']['m']['full']['sharpe']:.4f} / {out['M015-FAUM']['m']['full']['sharpe']:.4f}) — การเลื่อนสัญญาณไปอนาคตทำให้ FSR1/FSR3 ดีขึ้นชัด (สัญญาณจริง ณ t ไม่เห็นอนาคต → ไม่มี look-ahead แฝง) ส่วน F-AUM แทบไม่ต่าง (เลือกตาม AUM/ตลาดเงิน ไม่ขึ้นกับสัญญาณ)")
    A("")
    A("## 10. ป้ายบังคับ")
    A("")
    A("- ⚠️ **Sharpe ของกองตราสารหนี้สูงเกินจริง**: NAV เรียบ (ราคาประเมิน/accrual) + ความเสี่ยงเครดิต/สภาพคล่องที่ไม่เกิดในช่วง 2022–2025 → vol52 ต่ำเกินจริง → FSR1/FSR3 เลือกกองที่ 'ดูดี' จากความเรียบ (SR12′ ถึง 8 / vol52 0.03%) — ยกเว้น PRINCIPAL DPLUS-X ที่เกิดเหตุการณ์เครดิตจริงไตรมาส 2023-Q2")
    A("- ⚠️ **path luck**: Sharpe ระดับพอร์ตขยับ ±0.1 ได้จาก 3–5 วันแรกของไตรมาสเดียว (`SETTLEMENT_sensitivity.md`) · Δ เทียบ baseline เป็น paired (ส่วนหุ้นเหมือนทุกบิต) noise มาจากขา F ล้วน — ดูตาราง §8")
    A("- ⚠️ เกณฑ์ snapshot (Risk Level, buy period, retail type, ขั้นต่ำ) ไม่ point-in-time · survivorship ของกอง F ที่ไม่อยู่ใน FundProfile (FundCode 3,391 ตัวใน NAV ไม่มีใน FundProfile)")
    A("- ⚠️ ใช้ชุดข้อมูลเดิม ไม่มี holdout · 3 trials นี้เพิ่ม n_trials เป็น 32 · DSR คิดจากชุดเดียวกัน")
    A("")
    A("## 11. ต้องให้ผู้ใช้ตัดสินใจ / ข้อสงสัยต่อ spec")
    A("")
    A("1. **เพดาน vol52 < 0.02 ของสัญญาณกองหุ้น** (ดู §2 ข้อ 1) — spec ไม่ได้ระบุว่าให้ยกเลิกสำหรับกอง F แต่ถ้าไม่ยกเลิก F-AUM ทำไม่ได้ · validator ยกเลิกเอง (vol52 > 0) — ขอยืนยัน")
    A("2. กอง F ต่างประเทศ/Risk 5 ที่ถูก **ถือจริง**: เฉพาะ FSR3 (`K-APB-A(A)` FIF Risk 5 ไตรมาส 2024-09 และ 2024-12; vol52 4–5% ≈ 50 เท่าของกองตลาดเงิน) · FSR1/FAUM ไม่ถือกอง FIF เลย (FSR1 เลือก `KT-CSBOND-A` FIF ไตรมาส 2024-03 แต่ x_t = 1 จึงไม่ถือ) — ตามที่ผู้ใช้ยอมรับ (ข้อ 2 ของการตัดสินใจ)")
    A("3. F-AUM ไม่ผ่านเกณฑ์ Δ ≥ 0 และ **CI ไม่คร่อม 0** (แย่กว่า baseline อย่างมีนัยเล็กน้อย ~−0.014) · ผลตอบแทนขา F ต่ำกว่า rf นโยบายราว 39 bp/ปี → ยืนยันสมมติฐาน §1 ข้อ 2 (baseline มองเงินสดดีเกินจริง) · ตามคำตัดสินผู้ใช้ F-AUM คือขาเงินสดที่สมจริงกว่า — ถ้าจะเปลี่ยนวิธีวัด baseline เป็น F-AUM ต้องบันทึกเป็นการเปลี่ยนวิธีวัด (ไม่ใช่ trial ใหม่)")
    open(os.path.join(RES, "M015_results.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")


# ====================== main ======================
def main():
    t0 = time.time()
    phase_a_only = "--phase-a-only" in sys.argv
    nav = common.load_nav()
    codes = sorted(nav["FundCode"].unique())
    groups = common.load_groups()
    tab = rru.retail_table(codes, groups)
    cut = set(tab.loc[tab["cut"], "FundCode"])
    print(f"[setup] retail cut classes {len(cut)}", flush=True)
    ER = rru.setup_env(os.path.join(SCRATCH, "validator_retail_ctxs.pkl"), cut)
    leaked = {fc for c in ER["ctxs"] for fc in c["i_t"]["FundCode"]} & cut
    assert not leaked, leaked
    PR = rru.build_plans(ER)
    base_plan = PR["M013-GC75"]
    print(f"[setup] retail env + plans done ({time.time()-t0:.0f}s)", flush=True)

    profile = load_profile()
    FD = FData(profile, ER)
    f_all_codes = sorted(profile.index[profile["Fund Policy"] == "F"])
    fd_f = fees.FeeData(f_all_codes)                     # legacy=False (ค่าเริ่มต้น)
    fd_e = ER["fd_sim"]
    fd_comb = CombinedFee(fd_e, fd_f, f_all_codes)
    nav_all = {**ER["nav_by_fund"], **FD.nav_by_fund}
    assert len(nav_all) == len(ER["nav_by_fund"]) + len(FD.nav_by_fund)
    print(f"[setup] F classes with NAV {len(FD.codes)} · snapshot-eligible {len(FD.snap)} · fee median F {fd_f.median} · fee rows F {fd_f.n_rows} ({time.time()-t0:.0f}s)", flush=True)

    # ---------- (A) regression ----------
    reg = regression(ER, base_plan, FD, fd_comb, nav_all, None)
    sims_base_r, MR_base = reg.pop("_sims_base"), reg.pop("_MR_base")
    print("REGRESSION 1/2:", json.dumps({k: v for k, v in reg.items()}, default=float), f"({time.time()-t0:.0f}s)", flush=True)
    json.dump(reg, open(os.path.join(SCRATCH, "validator_m015_regression.json"), "w"), default=float)
    if not (reg["r1_ok"] and reg["r2_ok"]):
        print("REGRESSION FAIL — หยุด (ไม่นับ trial)", flush=True)
        return 2

    # ---------- F selection ----------
    rows = f_rows(FD, ER, ER["h_by_q"])
    sels = f_selections(FD, rows)
    # no-look-ahead check: คำนวณ I_t^F ใหม่จาก NAV ที่ตัด ≤ t แล้วต้องได้เหมือนเดิม (ทุกไตรมาส)
    mxd, nmis = 0.0, 0
    for r in rows:
        t = r["t"]
        navt = FD.nav[FD.nav["NAVDate"] <= t]
        assert navt["NAVDate"].max() <= t
        it2, q2, _ = FD.it_at(t, nav_override=navt)
        a = r["it"].set_index("FundCode")[["R12_1", "vol52"]].sort_index()
        b = it2.set_index("FundCode")[["R12_1", "vol52"]].sort_index()
        nmis += int(set(a.index) != set(b.index))
        if len(a) and set(a.index) == set(b.index):
            mxd = max(mxd, float((a - b).abs().max().max()))
        qa, qb = r["qual"][["aum_fam", "pass_q1", "pass_q2"]].sort_index(), q2[["aum_fam", "pass_q1", "pass_q2"]].sort_index()
        com = qa.index.intersection(qb.index)
        extra = qa.index.difference(qb.index)
        assert len(qb.index.difference(qa.index)) == 0 and (qa.loc[extra, "aum_fam"] <= 0).all() and not qa.loc[extra, "pass_q1"].any()
        assert (qa.loc[com, "aum_fam"] - qb.loc[com, "aum_fam"]).abs().max() < 1e-6 and (qa.loc[com, ["pass_q1", "pass_q2"]] == qb.loc[com, ["pass_q1", "pass_q2"]]).all().all()
    print(f"[no-lookahead] max|d signal| {mxd:.2e} · quarters with differing I_t^F set {nmis}", flush=True)
    assert mxd < 1e-12 and nmis == 0
    # เทียบกับเพดานเดิมของ fs (ตัวนับเชิงอธิบายเท่านั้น)
    litfloor = []
    for r in rows:
        q = fs.QuarterContext(FD.arrays, FD.calendar, r["t"])
        U = common.universe_at(FD.nav, r["t"])
        U = U[U["FundCode"].isin(FD.snap)]
        sg = fs.compute_quarter_signals(q, U["FundCode"].tolist())
        it_lit, _, _ = fs.investable_set(r["t"], U, sg, FD.groups, family_fix=True)
        litfloor.append({"qi": r["qi"], "t": r["t"].date(), "n_I_literal_floor": len(it_lit), "n_I_f_signal": len(r["it"]),
                         "n_mmf_literal": int(it_lit["FundCode"].map(FD.risk).isin(["1", "2"]).sum()),
                         "n_mmf_f_signal": int(r["it"]["FundCode"].map(FD.risk).isin(["1", "2"]).sum())})
    LF = pd.DataFrame(litfloor)
    LF.to_csv(os.path.join(RES, "M015_floor_diagnostic.csv"), index=False)
    print(LF.to_string(index=False), flush=True)

    # ---------- plans + sims ----------
    fset_all = set(FD.codes)
    PLAN, FB, SIMS, MRS = {}, {}, {}, {}
    for tid, mode in zip(TRIAL_IDS, ("FSR3", "FSR1", "FAUM")):
        pl, fb_q = make_plan_F(base_plan, sels[mode])
        mxs = plan_checks(pl, base_plan, fset_all)
        # ตรวจ: กอง F ที่เลือกต้องอยู่ใน I_t^F ของไตรมาสนั้น (ผ่านเกณฑ์) และไม่ใช่กองหุ้น
        for qi, p in enumerate(pl):
            for f in p["weights"]:
                if f in fset_all:
                    assert f in set(rows[qi]["it"]["FundCode"]) and f in FD.snap
                    assert f not in ER["nav_by_fund"]
        PLAN[tid], FB[tid] = pl, fb_q
        SIMS[tid] = sim_cases_x(pl, nav_all, ER["months"], fd_comb, ER["real"], fset=fset_all, log_full=True)
        MRS[tid] = metrics_bundle(SIMS[tid], ER["real"])
        print(f"[{tid}] max|dw| stock part {mxs:.1e} · fallback quarters {fb_q} · Sharpe full {MRS[tid]['full']['sharpe']:.4f} nofront {MRS[tid]['nofront']['sharpe']:.4f} "
              f"c0 {MRS[tid]['c0']['sharpe']:.4f} · cannot_buy {SIMS[tid]['full']['n_cannot_buy']} ({time.time()-t0:.0f}s)", flush=True)
    pickle.dump({"PLAN": PLAN, "FB": FB, "SIMS": {k: {kk: (vv if kk != "events" else None) for kk, vv in v["full"].items()} for k, v in SIMS.items()}},
                open(os.path.join(SCRATCH, "validator_m015_plans.pkl"), "wb"))
    if phase_a_only:
        return 0

    # ---------- สถิติ ----------
    real, months = ER["real"], ER["months"]
    q15, cal = ER["q15"], ER["calendar"]
    out = {}
    rb, rfm = MR_base["full"]["r"], MR_base["full"]["rfm"]
    ci_b = rr.boot_ci(rb, rfm)
    base_stock_funds = lambda qi: {f: w for f, w in base_plan[qi]["weights"].items() if f != "__CASH__"}
    summary_rows, qrows, selrows, legrows = [], [], [], []
    for tid, mode in zip(TRIAL_IDS, ("FSR3", "FSR1", "FAUM")):
        MR, S = MRS[tid], SIMS[tid]
        m = MR["full"]
        r_n, rfm_n = m["r"], m["rfm"]
        ci = rr.boot_ci(r_n, rfm_n)
        d = r11.paired_real(r_n, rb, rfm_n, "r")
        dsr = rr.dsr_s(r_n, rfm_n, N_TRIALS_FINAL)
        dn = {k: MR[k]["sharpe"] - MR_base[k]["sharpe"] for k in ("full", "nofront", "c0", "c50")}
        qd = r13.qdelta(r_n, rb, rfm_n, PLAN[tid], q15)
        # F-leg
        sel = sels[mode]
        fw = lambda qi, sel=sel: sel[qi][0] if (qi in sel and sel[qi][0] and (1.0 - x_of(base_plan[qi])) > 1e-12 and x_of(base_plan[qi]) < 1 - 1e-12) else {}
        qlist = [qi for qi in range(15) if fw(qi)]
        F_leg = leg_series(PLAN[tid], qlist, nav_all, months, real, fw, rr.PE)
        S_leg = leg_series(PLAN[tid], qlist, nav_all, months, real, base_stock_funds, rr.PE)
        feelog = pd.DataFrame(S["full"]["feelog"])
        feelog["qi"] = range(len(feelog))
        # ค่าธรรมเนียมที่เกิดจากขา F ต่อ entry เป็นสัดส่วนของขา F -> หักจากเดือนแรกของไตรมาส
        F_after = F_leg.copy()
        for qi in qlist:
            fr = float(feelog.loc[feelog["qi"] == qi, "f_related"].iloc[0])
            tF = float(feelog.loc[feelog["qi"] == qi, "tF"].iloc[0])
            idx = F_after.index[F_after["qi"] == qi]
            if len(idx) and tF > 1e-12:
                F_after.loc[idx[0], "r"] = (1.0 + F_after.loc[idx[0], "r"]) * (1.0 - fr / tF) - 1.0
        leg = {"months": len(F_leg), "ann_F_before": ann_from(F_leg, "r"), "ann_F_after": ann_from(F_after, "r"), "ann_rf": ann_from(F_leg, "rf"),
               "vol_F": float(F_leg["r"].std(ddof=1) * np.sqrt(12)), "vol_F_after": float(F_after["r"].std(ddof=1) * np.sqrt(12)),
               "corr_stock": float(np.corrcoef(F_leg["r"], S_leg["r"].reindex(F_leg.index))[0, 1]) if len(F_leg) > 3 and len(S_leg) == len(F_leg) else np.nan,
               "n_months_F_gt0": int(len(F_leg)),
               "rf_vol_not_zero": float(F_leg["rf"].std(ddof=1) * np.sqrt(12))}
        leg["excess_bp_before"] = (leg["ann_F_before"] - leg["ann_rf"]) * 1e4
        leg["excess_bp_after"] = (leg["ann_F_after"] - leg["ann_rf"]) * 1e4
        di = daily_index_2022(PLAN[tid], fw, nav_all, cal, pd.Timestamp("2022-01-01"), pd.Timestamp("2022-12-31"), real)
        # drawdown 2022 พอร์ตรวม
        mdd22 = r13.mdd_2022(S["full"]["values"])
        mdd22_b = r13.mdd_2022(sims_base_r["full"]["values"])
        # cost
        fl = feelog
        yrs = S["yrs"]
        cost_split = {k: float(fl[k].sum() / yrs * 1e4) for k in ("total", "stock_only", "f_related", "f_rot", "f_vs_stock")}
        cost_base = float(sims_base_r["full"]["cost_bp_yr"])
        nb = fd_comb.n_fallback_F
        o = {"tid": tid, "mode": mode, "m": MR, "S": S, "ci": ci, "d": d, "dsr": dsr, "dn": dn, "qd": qd, "leg": leg, "F_leg": F_leg, "di": di,
             "mdd22": mdd22, "mdd22_b": mdd22_b, "cost_split": cost_split, "cost_base": cost_base, "feelog": fl}
        out[tid] = o
        summary_rows.append({"model": tid, "sharpe_full": m["sharpe"], "d_full": d[2], "d_ci_lo": d[0], "d_ci_hi": d[1], "pass_rule": bool(d[2] >= 0),
                             "sig_better": bool(d[0] > 0), "sharpe_c0": MR["c0"]["sharpe"], "sharpe_c50": MR["c50"]["sharpe"], "sharpe_nofront": MR["nofront"]["sharpe"],
                             "d_c0": dn["c0"], "d_nofront": dn["nofront"], "cagr": m["cagr"], "vol": m["vol"], "maxdd": m["max_dd"], "maxdd_2022": mdd22,
                             "sharpe_2022": m["sharpe_2022"], "sharpe_2307_2512": m["sharpe_2307_2512"], "ci_lo": ci[0], "ci_hi": ci[1], "dsr32": dsr,
                             "cost_bp_yr_full": S["full"]["cost_bp_yr"], "turn_yr": S["full"]["turn_yr"], "n_cannot_buy": S["full"]["n_cannot_buy"],
                             "fallback_cash_quarters": len(FB[tid]), **{f"leg_{k}": v for k, v in leg.items()}})
        for qi in range(15):
            qrows.append({"model": tid, "qi": qi, "t": q15[qi].date(), "sum_dret": float(qd["tab"].loc[qi, "sum_dret"]) if qi in qd["tab"].index else np.nan})
        for qi in range(15):
            v, info, tb = sel[qi]
            x = x_of(base_plan[qi])
            for r in (tb.itertuples() if len(tb) else []):
                if r.FundCode in v:
                    dv, mxa = daily_vol_and_maxabs(nav_all, r.FundCode, q15[qi], q15[qi] + pd.Timedelta(days=95))
                    selrows.append({"model": tid, "qi": qi, "t": q15[qi].date(), "x_t": x, "FundCode": r.FundCode, "amc": FD.amc.get(r.FundCode), "risk": FD.risk.get(r.FundCode),
                                    "fif": FD.fif.get(r.FundCode), "aum_fam": r.aum_fam, "SR12p": r.SR12p, "vol52": r.vol52, "v_j": v[r.FundCode], "n_I": info["n_I"],
                                    "n_fam": info["n_fam"], "fallback_vol": info["fallback_vol"], "fund_n_spike_fixed_all": FD.spike.get(r.FundCode, 0),
                                    "hold_q_daily_vol": dv, "hold_q_max_abs_dret": mxa, "held_in_plan": bool(x < 1 - 1e-12), **fee_flags(fd_f, r.FundCode, base_plan[qi]["e"])})
            if x < 1 - 1e-12 and not v:
                selrows.append({"model": tid, "qi": qi, "t": q15[qi].date(), "x_t": x, "FundCode": "__CASH__ (fallback)", "n_I": info["n_I"], "n_fam": info["n_fam"]})
    S_df, Q_df, Sel_df = pd.DataFrame(summary_rows), pd.DataFrame(qrows), pd.DataFrame(selrows)
    S_df.to_csv(os.path.join(RES, "M015_results.csv"), index=False)
    Q_df.to_csv(os.path.join(RES, "M015_quarter_delta.csv"), index=False)
    Sel_df.to_csv(os.path.join(RES, "M015_selected_funds.csv"), index=False)
    wrows = []
    for tid in TRIAL_IDS:
        for en in SIMS[tid]["full"]["entries"]:
            for f, w in en["target"].items():
                if w > 1e-12:
                    wrows.append({"model": tid, "t": en["t"].date(), "e": en["e"].date(), "FundCode": f, "weight": w})
    pd.DataFrame(wrows).to_csv(os.path.join(RES, "M015_weights.csv"), index=False)
    eqc = pd.DataFrame({tid: SIMS[tid]["full"]["values"] for tid in TRIAL_IDS})
    eqc["BASELINE_M013-GC75_retail"] = sims_base_r["full"]["values"]
    eqc.to_csv(os.path.join(RES, "M015_equity_curve.csv"))

    # ---------- ตัวเสริม: first-week split · F-change · switch share · sanity diagnostics ----------
    fwrows = []
    for tid, mode in zip(TRIAL_IDS, ("FSR3", "FSR1", "FAUM")):
        sel = sels[mode]
        prev = None
        nchg = 0
        for qi in range(15):
            x = x_of(base_plan[qi])
            cur = frozenset(sel[qi][0]) if (x < 1 - 1e-12 and sel[qi][0]) else frozenset()
            if x < 1 - 1e-12 and sel[qi][0]:
                r1, r2 = first_week_split(PLAN[tid], qi, sel[qi][0], nav_all, real, months[-1] + pd.Timedelta(days=1))
                fwrows.append({"model": tid, "qi": qi, "t": q15[qi].date(), "leg_wt": 1.0 - x, "F_excess_first7d": r1, "F_excess_rest": r2,
                               "port_contrib_first7d": (1.0 - x) * r1, "port_contrib_rest": (1.0 - x) * r2})
            if prev is not None and cur and prev and cur != prev:
                nchg += 1
            prev = cur
        out[tid]["n_F_changes_consecutive"] = nchg
        out[tid]["n_quarters_with_F"] = sum(1 for qi in range(15) if x_of(base_plan[qi]) < 1 - 1e-12)
    FW = pd.DataFrame(fwrows)
    FW.to_csv(os.path.join(RES, "M015_first_week_split.csv"), index=False)
    # future-shift (ตั้งใจ look-ahead 1 ไตรมาส) · random F
    t_last = ER["q16"][15]
    it_l, qual_l, _ = FD.it_at(t_last)
    risk_map = FD.risk.to_dict()
    fut = {}
    for mode in ("FSR1", "FSR3", "FAUM"):
        sel_f = {}
        for qi in range(15):
            if qi < 14:
                r_n = rows[qi + 1]
                it_n, ql_n, h_n = r_n["it"], r_n["qual"], r_n["h"]
            else:
                it_n, ql_n, h_n = it_l, qual_l, ER["h_by_q"][15]
            sel_f[qi] = select_F_aum(it_n, ql_n, h_n, risk_map) if mode == "FAUM" else select_F(it_n, ql_n, h_n, mode)
        pl, _ = make_plan_F(base_plan, sel_f)
        sm = sim_cases_x(pl, nav_all, ER["months"], fd_comb, ER["real"], kinds=["full"])
        fut[mode] = rr.metrics(sm["full"]["values"], ER["real"])["sharpe"]
    RD = random_diag(rows, FD, base_plan, ER, nav_all, fd_comb, fset_all, risk_map, n=40)
    for tid in TRIAL_IDS:
        out[tid]["switch_share"] = SIMS[tid]["full"].get("switch_share", np.nan)
    DIAG = {"future_shift": fut, "rand_all": RD["rand_all"], "rand_mmf": RD["rand_mmf"]}
    print("[diag] future-shift Sharpe", {k: round(v, 4) for k, v in fut.items()}, "· rand_all mean/sd", round(float(np.mean(RD["rand_all"])), 4), round(float(np.std(RD["rand_all"], ddof=1)), 4),
          "· rand_mmf mean/sd", round(float(np.mean(RD["rand_mmf"])), 4), round(float(np.std(RD["rand_mmf"], ddof=1)), 4), flush=True)
    write_md(out, MR_base, ci_b, sims_base_r, base_plan, sels, FB, Sel_df, FW, LF, reg, DIAG, FD, fd_f, ER, PLAN, SIMS)
    pickle.dump({"out": {k: {kk: vv for kk, vv in v.items() if kk not in ("S",)} for k, v in out.items()}, "MR_base": {k: {kk: vv for kk, vv in m_.items()} for k, m_ in MR_base.items()},
                 "ci_b": ci_b, "reg": reg, "fb": FB, "LF": LF}, open(os.path.join(SCRATCH, "validator_m015_out.pkl"), "wb"))
    print(S_df[["model", "sharpe_full", "d_full", "d_ci_lo", "d_ci_hi", "sharpe_nofront", "sharpe_c0", "dsr32", "fallback_cash_quarters"]].round(4).to_string(), flush=True)

    # ---------- ลง log (เฉพาะเมื่อทุกอย่างผ่าน และสั่ง --log) ----------
    if "--log" not in sys.argv:
        print("DONE (no log) ", f"{time.time()-t0:.0f}s", flush=True)
        return 0
    for tid, mode in zip(TRIAL_IDS, ("FSR3", "FSR1", "FAUM")):
        o = out[tid]
        d = o["d"]
        verdict = "pass(d>=0)" if d[2] >= 0 else "fail(d<0)"
        if mode == "FAUM":
            verdict += "; user-rule: use FAUM always unless d<-0.10"
        params = {"FSR3": "M015-FSR3: M013-GC75 retail; non-stock leg (1-x_t) -> top3 policy-F families by SR12' (AUM_fam>=1bn) equal weight; no hysteresis; fallback __CASH__; F spike rule 0.5%/0.1%",
                  "FSR1": "M015-FSR1: M013-GC75 retail; non-stock leg -> top1 policy-F family by SR12' (basic criteria only); no hysteresis",
                  "FAUM": "M015-FAUM: M013-GC75 retail; non-stock leg -> largest AUM_fam family whose rep class has Risk Level 1-2 (fallback vol52 lowest quartile); no hysteresis"}[mode]
        extra = (f"dSharpe nofront {o['dn']['nofront']:+.4f} c0 {o['dn']['c0']:+.4f}; Sharpe2022 {o['m']['full']['sharpe_2022']:.3f}; fallback_cash_quarters={len(FB[tid])}; "
                 f"F-leg excess vs rf {o['leg']['excess_bp_before']:.0f}bp/yr (after fees {o['leg']['excess_bp_after']:.0f}); cost_bp_yr {o['S']['full']['cost_bp_yr']:.1f} vs base {o['cost_base']:.1f}; "
                 f"FAUM vol-floor interpretation: F signal uses vol52>0 not >=0.02")
        log_trial15(tid, 30 + TRIAL_IDS.index(tid), params, o["m"], o["S"], o["ci"], o["dsr"], d, verdict, extra)
        log_all_results15(tid, f"M013-GC75 retail + non-stock leg in policy-F bond fund ({mode}) (measured with real rf; retail universe; app fees)", o["m"], o["S"], d)
    print(f"DONE {time.time()-t0:.0f}s", flush=True)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        sys.exit(1)
