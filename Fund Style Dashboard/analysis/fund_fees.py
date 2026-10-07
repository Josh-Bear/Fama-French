"""fund_fees.py — ค่าธรรมเนียมซื้อขายจริงต่อกอง (SecFundFee · FEEUH · Actual Value) สำหรับ backtest หน้า 9.

พอร์ตจากโค้ด backtest ของทีม quant (specs/COST_real_fees.md) โดยไม่เปลี่ยนตรรกะ
- FF = front-end (จ่ายตอนซื้อ) · BF = back-end (ตอนขาย) · SI/SO = สับเปลี่ยนเข้า/ออก
- สลับกองภายใน บลจ. เดียวกัน: ยอดที่จับคู่ได้ใช้ช่องทางที่ถูกกว่าระหว่างสับเปลี่ยน (SO+SI) กับขาย-ซื้อ (BF+FF)
- point-in-time: ณ วันซื้อขาย e ใช้แถวล่าสุดที่ As of Date ≤ e · ก่อน snapshot แรกใช้ snapshot เก่าสุด
- ค่าว่าง/ติดลบ/> TF_FEE_MAX_PCT (เป็นบาทคงที่ ไม่ใช่ %) -> median ของกองทั้งหมด
- โหมด: "full" จ่ายเต็ม · "nofront" FF=SI=0 · "flat" ทุกขาเท่ากันและปิดช่องทางสับเปลี่ยน (= ต้นทุนคงที่ต่อข้าง)
"""
from __future__ import annotations

from collections import defaultdict

import numpy as np
import pandas as pd

import config

CODES = ("FF", "BF", "SI", "SO")
NO_FEE_TEXT = ("ไม่มี", "ยกเว้น", "ไม่เรียกเก็บ")      # ข้อความใน Actual Value ที่แปลว่าไม่เก็บค่าธรรมเนียม = 0%


def parse_fee_value(raw: pd.Series) -> pd.Series:
    """Actual Value (ข้อความ) → % ต่อปีเป็นตัวเลข · "ไม่มี/ยกเว้น/ไม่เรียกเก็บ" → 0 · "0.535%" → 0.535 · อื่นที่อ่านไม่ได้ → NaN."""
    s = raw.fillna("").astype(str).str.strip()
    v = pd.to_numeric(s.str.rstrip("%").str.strip(), errors="coerce")
    v[v.isna() & s.str.contains("|".join(NO_FEE_TEXT))] = 0.0
    return v


class FeeData:
    """อัตราค่าธรรมเนียมรายกองตามเวลา + บลจ. ของแต่ละกอง."""

    def __init__(self, fund_codes, fee_csv: str | None = None, profile_csv: str | None = None):
        d = pd.read_csv(fee_csv or config.SEC_FUND_FEE_CSV, dtype=str, encoding="utf-8-sig")
        d = d[(d["Complex Type Code"] == "FEEUH") & d["Code"].isin(CODES) & d["Fund Code"].isin(set(fund_codes))].copy()
        d["date"] = pd.to_datetime(d["As of Date"], format="%Y%m%d")
        d["v"] = parse_fee_value(d["Actual Value"])
        d.loc[(d["v"] < 0) | (d["v"] > config.TF_FEE_MAX_PCT), "v"] = np.nan
        # แถวซ้ำ (กอง, รหัส, วันที่) ค่าขัดกัน → เรียง v น้อย→มาก แบบ stable · lookup เลือกแถวสุดท้าย = ค่าสูงกว่า (ระวังไว้ก่อน)
        d = d.sort_values(["date", "v"], kind="mergesort", na_position="first")
        self.series = {}
        for (fc, code), g in d.groupby(["Fund Code", "Code"]):
            self.series[(fc, code)] = (g["date"].to_numpy(), g["v"].to_numpy())
        last = d.groupby(["Fund Code", "Code"]).tail(1)
        self.median = {c: float(last[last["Code"] == c]["v"].median()) for c in CODES}
        # ไม่มีค่าที่ใช้ได้เลยสำหรับรหัสใด (median = NaN) -> ใช้ต้นทุนคงที่ TF_COST_FLAT แทน และบันทึกไว้ (ไม่ให้ NaN ไหลเข้า backtest)
        self.median_fallback = [c for c, v in self.median.items() if not np.isfinite(v)]
        for c in self.median_fallback:
            self.median[c] = config.TF_COST_FLAT * 100
        prof = pd.read_csv(profile_csv or config.FUND_PROFILE_CSV, dtype=str)
        self.amc = dict(zip(prof["Fund Code"], prof["AMC_CODE"]))
        self.n_fallback = defaultdict(int)

    def rate(self, fc: str, code: str, e: pd.Timestamp) -> float:
        """อัตรา (%) ณ วัน e · ไม่มีข้อมูล -> median."""
        s = self.series.get((fc, code))
        if s is None:
            self.n_fallback[code] += 1
            return self.median[code]
        dates, vals = s
        i = np.searchsorted(dates, np.datetime64(e), side="right") - 1
        v = vals[max(i, 0)]
        if not np.isfinite(v):
            self.n_fallback[code] += 1
            return self.median[code]
        return float(v)


class FeeModel:
    """ต้นทุนต่อการปรับพอร์ตหนึ่งครั้ง (สัดส่วนของมูลค่าพอร์ต) — คิดเฉพาะขากอง ไม่รวมเงินสด."""

    def __init__(self, data: FeeData | None, mode: str = "full", flat_rate: float | None = None):
        assert mode in ("full", "nofront", "flat")
        self.data, self.mode = data, mode
        self.flat = config.TF_COST_FLAT if flat_rate is None else flat_rate
        self.tot = defaultdict(float)

    def _r(self, fc, code, e):
        if self.mode == "flat":
            return self.flat
        if self.mode == "nofront" and code in ("FF", "SI"):
            return 0.0
        return self.data.rate(fc, code, e) / 100.0

    def entry_cost(self, e, drift_w: dict, target_w: dict) -> tuple[float, dict]:
        sells, buys = {}, {}
        for f in set(drift_w) | set(target_w):
            dlt = target_w.get(f, 0.0) - drift_w.get(f, 0.0)
            if dlt < -1e-15:
                sells[f] = -dlt
            elif dlt > 1e-15:
                buys[f] = dlt
        cost, switch_vol = 0.0, 0.0
        by_amc_s, by_amc_b = defaultdict(list), defaultdict(list)
        for f in sells:
            by_amc_s[self.data.amc.get(f, f) if self.mode != "flat" else f].append(f)
        for f in buys:
            by_amc_b[self.data.amc.get(f, f) if self.mode != "flat" else f].append(f)
        for amc in set(by_amc_s) | set(by_amc_b):
            sf, bf = by_amc_s.get(amc, []), by_amc_b.get(amc, [])
            s_tot, b_tot = sum(sells[f] for f in sf), sum(buys[f] for f in bf)
            m = min(s_tot, b_tot) if (self.mode != "flat" and sf and bf) else 0.0
            sell_left = 1.0 - (m / s_tot if s_tot > 0 else 0.0)
            buy_left = 1.0 - (m / b_tot if b_tot > 0 else 0.0)
            if m > 0:
                so_w = sum(sells[f] * self._r(f, "SO", e) for f in sf) / s_tot
                si_w = sum(buys[f] * self._r(f, "SI", e) for f in bf) / b_tot
                bf_w = sum(sells[f] * self._r(f, "BF", e) for f in sf) / s_tot
                ff_w = sum(buys[f] * self._r(f, "FF", e) for f in bf) / b_tot
                if so_w + si_w < bf_w + ff_w:        # สับเปลี่ยนถูกกว่า (เท่ากัน -> ขาย-ซื้อ)
                    cost += m * (so_w + si_w)
                    switch_vol += m
                else:
                    cost += m * (bf_w + ff_w)
            cost += sum(sells[f] * sell_left * self._r(f, "BF", e) for f in sf)
            cost += sum(buys[f] * buy_left * self._r(f, "FF", e) for f in bf)
        sv, bv = sum(sells.values()), sum(buys.values())
        self.tot["sell_vol"] += sv
        self.tot["buy_vol"] += bv
        self.tot["switch_vol"] += switch_vol
        self.tot["cost"] += cost
        return cost, {"sell_vol": sv, "buy_vol": bv, "switch_vol": switch_vol}
