"""frontier_export.py — ตัวช่วยร่วมของ export หน้า frontier ในแอป (หน้า 10 = M019 · หน้า 11 = M052) · ไม่ใช่ trial

- holdings_weekly(): กองที่ถือ + น้ำหนัก + SR12′ + weekly return 52 สัปดาห์ ≤ t ต่อไตรมาส (kind E หุ้น / G ทอง / F ตลาดเงิน)
- realized(): ผลที่เกิดขึ้นจริงของ MVP / max Sharpe / Model Portfolio ต่อไตรมาส
  · ต้นทุน = ค่าธรรมเนียมจริง (fees.FeeModel "full") ของการสลับจากพอร์ตจริงของโมเดลไตรมาสก่อน (drift ถึง e) → พอร์ตนั้น
    (กติกาเดียวกับ simulate.simulate_path: mark ด้วย NAV ล่าสุด ≤ e · ซื้อที่ NAV แรก ≥ e) · ไตรมาสแรก = ซื้อจากเงินสด
  · buy-and-hold: Q = e → e ไตรมาสถัดไป (ไตรมาสสุดท้าย → PE) · 1Y = e → e + 365 วัน (ตัดที่ PE)
  · ret/ปี = ช่วงถือ × 365/วัน · vol = มูลค่าพอร์ตรายวัน × √(จำนวนวัน ÷ ปี) · rf = ดอกเบี้ยนโยบายทบต้นรายวัน × 365/วัน
  · คืนผลคูณ (1 + ret Q) ของ Model Portfolio ทุกไตรมาส → ผู้เรียก assert = มูลค่าพอร์ตจาก simulate ของโมเดล
- write_reference(): เขียน CSV อ้างอิง (header # + ตาราง)
"""
from __future__ import annotations

import json
import os

import numpy as np
import pandas as pd

import fees
import fund_signals as fs
import run_m011 as r11
import simulate

PORTS = ("MVP", "max Sharpe", "ERC (กติกาโมเดล)")   # ชื่อคอลัมน์ของ analysis.gc75_frontier.frontier_case (แอปแสดงเป็น Model Portfolio)


def holdings_weekly(plan, E, fset, gset, FD, GD, info, extra=None):
    """plan = แผนจริงของโมเดล (t, e, weights) · info(qi, fc, kind) -> (family, sr12p, rank) · extra(qi) -> dict คอลัมน์เพิ่มต่อไตรมาส."""
    hold, wk_rows = [], []
    for qi, p in enumerate(plan):
        t, e, w = p["t"], p["e"], p["weights"]
        ctx = E["ctx_h"][qi]
        assert ctx["t"] == t and "__CASH__" not in w
        assert "K-GOLD-C(A)" not in w, "K-GOLD-C(A) มี NAV ผิดหลัง 2024-04-22 (ดู run_r5.clean_gold_v2)"
        rf_t = float(E["rate"].loc[t]) / 100.0
        add = extra(qi) if extra else {}
        for f, wt_ in w.items():
            if wt_ <= 0:
                continue
            if f in gset or f in fset:
                kind = "G" if f in gset else "F"
                arr = GD.arrays if kind == "G" else FD.arrays
                wk = fs.QuarterContext(arr, E["calendar"], t).weekly_return_series(f)
            else:
                kind = "E"
                wk = ctx["wk"][f]
            fam, sr, rank = info(qi, f, kind)
            assert wk.index.max() <= t and len(wk) == 52, (t, f, len(wk))
            hold.append({"t": t.date(), "e": e.date(), "FundCode": f, "kind": kind, "weight": wt_, "family": fam,
                         "sr12p": sr, "rank": rank, "rf": rf_t, **add})
            wk_rows += [{"t": t.date(), "FundCode": f, "week": d.date(), "ret": r} for d, r in wk.items()]
    H = pd.DataFrame(hold)
    assert (H.groupby("t")["weight"].sum() - 1).abs().max() < 1e-9
    assert (H.groupby("t")["kind"].apply(lambda s: (s != "E").sum()) <= 1).all(), "ขาตั้งรับมากกว่า 1 กองในไตรมาสเดียว"
    return H, pd.DataFrame(wk_rows)


def _exec_px(nav, f, e):
    r = simulate._exec_nav(nav, f, e)
    assert r is not None, ("ซื้อไม่ได้", f, e)
    return r[0]


def _drift(nav, w, e0, e1):
    val = {f: x / _exec_px(nav, f, e0) * simulate._nav_last(nav, f, e1)[0] for f, x in w.items() if x > 0}
    s = sum(val.values())
    return {f: v / s for f, v in val.items()}


def _hold(nav, w, e, end, start_value):
    units = {f: start_value * x / _exec_px(nav, f, e) for f, x in w.items() if x > 0}
    days = sorted({d for f in units for d in nav[f].loc[e:end].index})
    v = pd.Series({d: sum(u * simulate._nav_last(nav, f, d)[0] for f, u in units.items()) for d in days})
    return v, sum(u * simulate._nav_last(nav, f, end)[0] for f, u in units.items())


def realized(Hr, Wr, plan, nav, fee_data, rate, pe, frontier_case, use_held_weights):
    """Hr/Wr = ไฟล์อ้างอิงที่อ่านกลับแบบเดียวกับแอป · frontier_case = analysis.gc75_frontier.frontier_case
    use_held_weights = True → Model Portfolio = น้ำหนักที่ถือจริง (เช่น M052 ที่มี BAND5) · False → ERC ของแอป (ต้องเท่าที่ถือจริง)."""
    plan_e = [p["e"] for p in plan]
    rows, chain = [], 1.0
    for qi, t in enumerate(sorted(Hr["t"].unique())):
        t = pd.Timestamp(t)
        h_t, w_t = Hr[Hr["t"] == t], Wr[Wr["t"] == t]
        held = h_t.set_index("FundCode")["weight"]
        res = frontier_case(h_t, w_t, model_weights=held if use_held_weights else None)
        e = pd.Timestamp(h_t["e"].iloc[0])
        assert e == plan_e[qi] and plan[qi]["t"] == t
        model = res["weights"][PORTS[2]]
        pw = {f: x for f, x in plan[qi]["weights"].items() if x > 0}
        assert max(abs(model.get(f, 0) - pw.get(f, 0)) for f in set(model.index) | set(pw)) < 1e-12, t
        prior = _drift(nav, plan[qi - 1]["weights"], plan_e[qi - 1], e) if qi else {}
        end_q = min(plan_e[qi + 1], pe) if qi + 1 < len(plan_e) else pe
        end_y = min(e + pd.Timedelta(days=365), pe)
        for name in PORTS:
            w = {f: float(x) for f, x in res["weights"][name].items() if x > 1e-12}
            cost = fees.FeeModel(fee_data, "full").entry_cost(e, prior, w)[0]
            s = res["summary"].loc[name]
            for hz, end in (("Q", end_q), ("1Y", end_y)):
                v, v_end = _hold(nav, w, e, end, 1.0 - cost)
                days = (end - e).days
                r_d = v.pct_change().dropna()
                ret = v_end - 1.0
                rf_p = r11.hurdle(rate, e, end)
                vol = float(r_d.std(ddof=1) * np.sqrt(len(r_d) / (days / 365.0)))
                rows.append({"t": t.date(), "portfolio": name, "horizon": hz, "e": e.date(), "end": end.date(), "days": days,
                             "truncated": hz == "1Y" and end < e + pd.Timedelta(days=365), "cost": cost,
                             "ret": ret, "ret_gross": v_end / (1.0 - cost) - 1.0, "ret_ann": ret * 365.0 / days, "vol_ann": vol,
                             "rf_ann": rf_p * 365.0 / days, "sharpe": (ret - rf_p) * 365.0 / days / vol, "n_days": len(r_d),
                             "exp_ret": s["ret"], "exp_vol": s["risk"], "exp_sharpe": s["sharpe"],
                             "weights": json.dumps({f: round(x, 12) for f, x in w.items()}, sort_keys=True)})
                if name == PORTS[2] and hz == "Q":
                    chain *= 1.0 + ret
    return pd.DataFrame(rows), chain


def write_reference(path, header_lines, df):
    with open(path, "w", encoding="utf-8") as f:
        f.write("".join(f"# {h}\n" for h in header_lines))
        df.to_csv(f, index=False)
    print("เขียน", path, df.shape)
