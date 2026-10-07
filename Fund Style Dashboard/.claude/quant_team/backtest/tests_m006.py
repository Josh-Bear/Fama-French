"""tests_m006.py — sanity tests M006 §2/§5 + M007 §3 (family map F/U, scale entry, cash-only path). รันตรง: python tests_m006.py"""
from __future__ import annotations

import os
import sys

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if THIS_DIR not in sys.path:
    sys.path.insert(0, THIS_DIR)

import numpy as np
import pandas as pd

import fund_signals as fs
import simulate


def t_family(groups: dict) -> dict:
    fo = lambda f: fs.family_of(f, groups, True)[0]
    res = {}
    res["F1.1 KKP GINFRAEQ -H/-H-F/-UH/-H-U"] = (
        fo("KKP GINFRAEQ-H-F") == fo("KKP GINFRAEQ-H") == fo("KKP GINFRAEQ-UH") == fo("KKP GINFRAEQ-H-U") == "KKP GINFRAEQ"
        if not any(k in groups for k in ["KKP GINFRAEQ-H-F", "KKP GINFRAEQ-H", "KKP GINFRAEQ-UH", "KKP GINFRAEQ-H-U"])
        else fo("KKP GINFRAEQ-H-F") == fo("KKP GINFRAEQ-H") == fo("KKP GINFRAEQ-H-U"))
    res["F1.2 ES-NDQPIN-UH-A / KKP TECH-H"] = (fo("ES-NDQPIN-UH-A") == "ES-NDQPIN" and fo("KKP TECH-H") == "KKP TECH")
    res["F1.2b TECH -H-U/-H-F same"] = fo("KKP TECH-H-U") == fo("KKP TECH-H-F") == fo("KKP TECH-H")
    res["F1.is_dividend X-D-F=True, X-F=False"] = fs.is_dividend("AB-D-F", True) and not fs.is_dividend("AB-F", True) \
        and not fs.is_dividend("AB-D-F", False)
    return res


def t_family_diff(all_codes: list[str], groups: dict, out_csv: str) -> dict:
    rows = []
    for fc in sorted(all_codes):
        o = fs.family_of(fc, groups, False)[0]
        n = fs.family_of(fc, groups, True)[0]
        rows.append((fc, o, n))
    df = pd.DataFrame(rows, columns=["FundCode", "family_old", "family_new"])
    diff = df[df.family_old != df.family_new]
    diff.to_csv(out_csv, index=False)
    toks = lambda f: [t for t in fs._tokens(f) if t]
    has_fu = diff.FundCode.apply(lambda f: any(fs.FU_RE.match(t) for t in toks(f)))
    nofu = df[~df.FundCode.apply(lambda f: any(fs.FU_RE.match(t) for t in toks(f)))]
    return {"n_codes": len(df), "n_diff": len(diff), "n_diff_without_FU_token": int((~has_fu).sum()),
            "n_noFU_codes": len(nofu), "n_noFU_changed": int((nofu.family_old != nofu.family_new).sum())}


def _synth_nav(n=300, seed=1):
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2022-01-03", periods=n)
    return {f: pd.Series(100 * np.cumprod(1 + rng.normal(0.0004, 0.01, n)), index=idx) for f in ("A", "B", "C")}


def t_sim() -> dict:
    nav = _synth_nav()
    idx = nav["A"].index
    me = [pd.Timestamp(d) for d in pd.Series(idx, index=idx).groupby([idx.year, idx.month]).max().values]
    me = [m for m in me if m >= idx[5]]
    e0, e1, e2 = idx[3], idx[100], idx[200]
    sl = {"A": 0.5, "B": 0.5}
    base = [{"t": idx[1], "e": e0, "weights": dict(sl)}]
    res = {}
    # test 4: scale entry x เท่าเดิม (=1) -> turnover 0, cost 0, path เท่ากัน
    info = {}
    v0, _, _, _ = simulate.simulate_path(base, nav, me, 0.005, 0.02)
    v1, t1, _, _ = simulate.simulate_path(base + [{"t": idx[99], "e": e1, "mode": "scale", "equity": 1.0, "sleeve": sl}],
                                          nav, me, 0.005, 0.02, info=info)
    res["T4 scale x เท่าเดิม: turnover=0, cost=0, path เท่าเดิม"] = (
        abs(t1[-1]) < 1e-12 and info["entries"][-1]["cost"] < 1e-12 and np.allclose(v0.values, v1.values, rtol=1e-9, atol=1e-9))
    # scale 1 -> 0.7 : cost = 0.5% * 0.3 (ขากองเท่านั้น), เงินสด 30%
    info2 = {}
    v2, t2, _, _ = simulate.simulate_path(base + [{"t": idx[99], "e": e1, "mode": "scale", "equity": 0.7, "sleeve": sl}],
                                          nav, me, 0.005, 0.02, info=info2)
    res["T4b scale 1->0.7: cost = 0.5% x 0.3 = 0.15%"] = abs(info2["entries"][-1]["cost"] - 0.005 * 0.3) < 1e-9 \
        and abs(info2["entries"][-1]["target"]["__CASH__"] - 0.3) < 1e-9
    # scale 0.7 -> 0 -> 0.7 (D=0 ใช้ sleeve): money conservation ผ่าน assert ภายใน
    p3 = base + [{"t": idx[99], "e": e1, "mode": "scale", "equity": 0.0, "sleeve": sl},
                 {"t": idx[199], "e": e2, "mode": "scale", "equity": 1.0, "sleeve": sl}]
    info3 = {}
    v3, _, _, _ = simulate.simulate_path(p3, nav, me, 0.005, 0.02, info=info3)
    res["T4c 100%->0%->100%: cost 0.5% + 0.5%, funds ว่างช่วง cash"] = (
        abs(info3["entries"][1]["cost"] - 0.005) < 1e-9 and abs(info3["entries"][2]["cost"] - 0.005) < 1e-9
        and abs(info3["entries"][1]["target"]["__CASH__"] - 1.0) < 1e-9)
    # test 5: x≡0 -> cash เติบโตด้วย rf ตาม _grow_cash · turnover รอบแรก 0
    pc = [{"t": idx[1], "e": e0, "weights": {"__CASH__": 1.0}}]
    vc, tc, _, _ = simulate.simulate_path(pc, nav, me, 0.005, 0.02, include_start=True)
    exp = 1.02 ** (((vc.index - vc.index[0]).days) / 365.0) * 100
    res["T5 cash 100%: มูลค่า = 100*(1.02)^(days/365) (±1e-9) · turnover รอบแรก = 0"] = (
        np.allclose(vc.values, exp, rtol=0, atol=1e-9) and tc[0] == 0.0)
    return res


def run_all(groups, all_codes, out_csv):
    out = {}
    out.update(t_family(groups))
    out.update(t_sim())
    diff_stats = t_family_diff(all_codes, groups, out_csv)
    out["F1.3 กองไม่มี token F/U: family เท่าเดิม 100% (diff=0)"] = diff_stats["n_noFU_changed"] == 0
    out["F1.4 diff csv เฉพาะกองที่มี token F/U"] = diff_stats["n_diff_without_FU_token"] == 0
    return out, diff_stats
