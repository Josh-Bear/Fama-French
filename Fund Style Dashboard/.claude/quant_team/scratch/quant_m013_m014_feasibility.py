"""quant_m013_m014_feasibility.py — read-only (quant-modeler) · ไม่คำนวณ return/Sharpe ของโมเดล
(1) M013: จำนวนสัญญาณ ACWI ผ่าน (3/6/12 เดือน > rf จริงช่วงเดียวกัน) ณ ทุกสิ้นไตรมาส + เทียบ SMA200 (trend เดิม)
(2) M014: จำนวน family ใน I_t' (หลังเกณฑ์คุณภาพ M012) ที่ SR12' (hurdle rf จริง) > 1.0 ต่อไตรมาส
รัน: PYTHONPATH=. ./.venv/bin/python .claude/quant_team/scratch/quant_m013_m014_feasibility.py
"""
import os, sys, pickle
HERE = os.path.dirname(os.path.abspath(__file__))
BT = os.path.join(os.path.dirname(HERE), "backtest")
sys.path.insert(0, BT); sys.path.insert(0, ".")
import pandas as pd
import common, fund_signals as fs, weighting as wt
import run_m011 as r11, run_m012 as r12, remeasure_real_rf as rr
from data import msci_index

cal = common.load_calendar()
acwi = msci_index.load_country_index()["MSCI_ACWI"]
real, _ = rr.load_policy(); rate = real.rate
q16 = common.quarter_ends(cal, "2022-03-31", "2025-12-31")
print("t | R3 rf3 s | R6 rf6 s | R12 rf12 s | k | SMA200 below")
for t in q16:
    ms = fs.month_end_points(cal, t, 13)
    assert ms[-1] == t, (t, ms[-1])
    a = acwi.loc[:t]; a_t = float(a.iloc[-1]); k = 0; parts = []
    for L in (3, 6, 12):
        lag = ms[-1 - L]
        R = a_t / float(acwi.loc[:lag].iloc[-1]) - 1
        h = r11.hurdle(rate, lag, t)
        s = int(R > h); k += s
        parts.append(f"{R:+.3f} {h:.4f} {s}")
    print(t.date(), "|", " | ".join(parts), "|", k, "|", wt.trend_filter_cash(acwi, t, 0.25) > 0)

ctxs = pickle.load(open(os.path.join(HERE, "validator_m012_ctxs.pkl"), "rb"))
h_by_q = {}
for c in ctxs:
    ms = fs.month_end_points(cal, c["t"], 13)
    h_by_q[c["qi"]] = r11.hurdle(rate, ms[0], ms[-2])
ctx_h = r11.with_hurdle(ctxs, cal, h_by_q)
nav = common.load_nav(); groups = common.load_groups()
Q = r12.Quality(nav, groups)
print("t | fam I_t' | fam SR12'>1 (rep) | fam SR12'>0")
for c in ctx_h:
    g, _ = Q.table(c["t"])
    ok = set(g.index[g["pass_q1"] & g["pass_q2"]])
    it = c["i_t"][c["i_t"]["family"].isin(ok)]
    reps = wt.family_representatives(it, "SR12", held_funds=set())
    sr = pd.Series({f: r["signal"] for f, r in reps.items()})
    print(c["t"].date(), "|", len(reps), "|", int((sr > 1.0).sum()), "|", int((sr > 0).sum()))
