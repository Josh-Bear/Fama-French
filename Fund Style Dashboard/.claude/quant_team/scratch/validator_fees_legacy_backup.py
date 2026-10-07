"""fees.py — โมเดลค่าธรรมเนียมจริง (SecFundFee FEEUH 'Actual Value' FF/BF/SI/SO) ต่อ entry ของ simulate_path
(specs/COST_real_fees.md). ใช้ผ่าน simulate_path(..., fee_model=FeeModel(...)); fee_model=None = พฤติกรรมเดิม (cost_side คงที่).

โหมด: "full" = จ่ายเต็ม · "nofront" = FF=0 และ SI=0 · "flat" = FF=BF=SI=SO=flat_rate ทุกกอง + ปิดช่องทางสับเปลี่ยน (ต้อง = cost_side เดิม)
point-in-time: ณ วันซื้อขาย e ใช้แถวล่าสุดที่ As of Date <= e; ถ้าไม่มี (ก่อน snapshot แรก) ใช้ snapshot เก่าสุดที่มี.
ค่าว่าง/ไม่ใช่ตัวเลข/ติดลบ/> 10 (ไม่ใช่ % — เป็นบาทคงที่ เช่น SO 200/300) -> median ของ Code (กองใน NAV universe, snapshot ล่าสุดต่อกอง).
"""
from __future__ import annotations

import os
from collections import defaultdict

import numpy as np
import pandas as pd

import common

CODES = ("FF", "BF", "SI", "SO")
MAX_PCT = 10.0


class FeeData:
    def __init__(self, fund_codes):
        root = common.PROJECT_ROOT
        d = pd.read_csv(os.path.join(root, "base_data", "SecFundFee.csv"), dtype=str, encoding="utf-8-sig")
        d = d[(d["Complex Type Code"] == "FEEUH") & d["Code"].isin(CODES) & d["Fund Code"].isin(set(fund_codes))].copy()
        d["date"] = pd.to_datetime(d["As of Date"], format="%Y%m%d")
        d["v"] = pd.to_numeric(d["Actual Value"], errors="coerce")
        d.loc[(d["v"] < 0) | (d["v"] > MAX_PCT), "v"] = np.nan
        self.n_rows, self.n_invalid = len(d), int(d["v"].isna().sum())
        self.series = {}      # (fund, code) -> (dates ndarray, values ndarray)
        for (fc, code), g in d.sort_values("date").groupby(["Fund Code", "Code"]):
            self.series[(fc, code)] = (g["date"].to_numpy(), g["v"].to_numpy())
        last = d.sort_values("date").groupby(["Fund Code", "Code"]).tail(1)
        self.median = {c: float(last[(last["Code"] == c)]["v"].median()) for c in CODES}   # NaN ถูกข้ามโดย median
        self.n_funds_fee = d["Fund Code"].nunique()
        prof = pd.read_csv(os.path.join(root, "base_data", "FundProfile.csv"), dtype=str)
        self.amc = dict(zip(prof["Fund Code"], prof["AMC_CODE"]))
        self.n_fallback = defaultdict(int)

    def rate(self, fc, code, e):
        """อัตรา % ณ วัน e (point-in-time) · fallback median."""
        s = self.series.get((fc, code))
        if s is None:
            self.n_fallback[code] += 1
            return self.median[code]
        dates, vals = s
        i = np.searchsorted(dates, np.datetime64(e), side="right") - 1
        v = vals[max(i, 0)]                       # i<0 (ก่อน snapshot แรก) -> snapshot เก่าสุด
        if not np.isfinite(v):
            self.n_fallback[code] += 1
            return self.median[code]
        return float(v)


class FeeModel:
    def __init__(self, data: FeeData | None, mode="full", flat_rate=0.005):
        assert mode in ("full", "nofront", "flat")
        self.data, self.mode, self.flat = data, mode, flat_rate
        self.tot = defaultdict(float)     # สะสม: sell_vol, buy_vol, switch_vol, cost

    def _r(self, fc, code, e):
        if self.mode == "flat":
            return self.flat
        if self.mode == "nofront" and code in ("FF", "SI"):
            return 0.0
        return self.data.rate(fc, code, e) / 100.0

    def entry_cost(self, e, drift_w: dict, target_w: dict):
        """คืน (cost เป็นสัดส่วนของมูลค่าพอร์ต, detail dict) — เฉพาะขากอง (ผู้เรียกไม่ส่ง __CASH__)."""
        sells, buys = {}, {}
        for f in set(drift_w) | set(target_w):
            dlt = target_w.get(f, 0.0) - drift_w.get(f, 0.0)
            if dlt < -1e-15:
                sells[f] = -dlt
            elif dlt > 1e-15:
                buys[f] = dlt
        cost, switch_vol = 0.0, 0.0
        by_amc_s, by_amc_b = defaultdict(list), defaultdict(list)
        for f, s in sells.items():
            by_amc_s[self.data.amc.get(f, f) if self.mode != "flat" else f].append(f)
        for f, b in buys.items():
            by_amc_b[self.data.amc.get(f, f) if self.mode != "flat" else f].append(f)
        for amc in set(by_amc_s) | set(by_amc_b):
            sf, bf = by_amc_s.get(amc, []), by_amc_b.get(amc, [])
            S, B = sum(sells[f] for f in sf), sum(buys[f] for f in bf)
            m = min(S, B) if (self.mode != "flat" and sf and bf) else 0.0
            sell_frac_left = 1.0 - (m / S if S > 0 else 0.0)
            buy_frac_left = 1.0 - (m / B if B > 0 else 0.0)
            if m > 0:
                so_w = sum(sells[f] * self._r(f, "SO", e) for f in sf) / S
                si_w = sum(buys[f] * self._r(f, "SI", e) for f in bf) / B
                bf_w = sum(sells[f] * self._r(f, "BF", e) for f in sf) / S
                ff_w = sum(buys[f] * self._r(f, "FF", e) for f in bf) / B
                if so_w + si_w < bf_w + ff_w:           # ช่องทางสับเปลี่ยนถูกกว่า (เท่ากัน -> ขาย-ซื้อ)
                    cost += m * (so_w + si_w)
                    switch_vol += m
                else:
                    cost += m * (bf_w + ff_w)
            cost += sum(sells[f] * sell_frac_left * self._r(f, "BF", e) for f in sf)
            cost += sum(buys[f] * buy_frac_left * self._r(f, "FF", e) for f in bf)
        sv, bv = sum(sells.values()), sum(buys.values())
        self.tot["sell_vol"] += sv
        self.tot["buy_vol"] += bv
        self.tot["switch_vol"] += switch_vol
        return cost, {"sell_vol": sv, "buy_vol": bv, "switch_vol": switch_vol}
