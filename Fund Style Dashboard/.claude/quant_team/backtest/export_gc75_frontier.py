"""export_gc75_frontier.py — input ของ efficient frontier หน้า 10 = **M019-LC3-GCGOLD** (universe เต็ม · offset 0) · ไม่ใช่ trial
(เดิม 2026-10-07 เป็น M015-FAUM · ผู้ใช้สั่งเปลี่ยนเป็น M019 2026-10-13)
ต่อไตรมาส t (15 ไตรมาส 2022-03-31 … 2025-09-30): กองหุ้น 3 กองที่ M019 ถือจริง (อันดับ 1 + เติม max ρ_adj ต่ำสุด · ERC เพดาน 40%)
+ ขาตั้งรับ (กองทอง AUM ใหญ่สุด = kind G · ไม่มี → กองตลาดเงิน = kind F) · น้ำหนักจริง · SR12′ ณ t · weekly return 52 สัปดาห์ ≤ t
· rf = ดอกเบี้ยนโยบาย ธปท. ที่มีผล ณ t · regression: น้ำหนัก = results/M019_weights.csv ทุกบิต
รัน: PYTHONPATH=. ./.venv/bin/python .claude/quant_team/backtest/export_gc75_frontier.py
"""
import os, sys
THIS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, THIS)
import numpy as np, pandas as pd
import common
import fund_signals as fs
import fulluniv_run as fu
import run_m015 as r15
import run_m018 as m18
import run_m019 as m19

RES = common.RESULTS_DIR
REF = os.path.join(common.PROJECT_ROOT, "base_data", "reference")
HEADER = ("# input efficient frontier หน้า 10 — M019-LC3-GCGOLD (หุ้น 3 กอง + ขาทอง/ตลาดเงิน) · ไฟล์อ้างอิงคงที่ (ห้ามแก้มือ)\n"
          "# ที่มา: .claude/quant_team/backtest/export_gc75_frontier.py · universe เต็ม · offset 0 · rebalance สิ้นไตรมาส 2022-03-31 … 2025-09-30\n")

holder = {}
E, P, X = fu.build_env_and_plans(0, holder)
FD = holder["FD"]
profile = r15.load_profile()
f_codes = sorted(FD.profile.index[FD.profile["Fund Policy"] == "F"])
GD = m18.GData(profile, E, f_codes)
GS = m18.gold_sels(GD, E)
sleeves, recs = m19.stream_lc(E["ctx_h"], E["quals"], m19.POOL, ordered=False)
plan = m19.gc_gold_plan(E, X, GS, sleeves)
fset, gset = set(FD.codes), set(GD.codes)

hold_rows, wk_rows = [], []
for qi, p in enumerate(plan):
    t, e, w = p["t"], p["e"], p["weights"]
    rec, ctx = recs[qi], E["ctx_h"][qi]
    assert not rec["fallback"] and ctx["t"] == t
    fam_of = {fc: fam for fam, fc in rec["S"].items()}
    eq = [f for f in w if f not in fset and f not in gset]
    assert set(eq) == set(rec["S"].values()) and len(eq) == 3, (t, eq)
    assert "K-GOLD-C(A)" not in w, "K-GOLD-C(A) มี NAV ผิดหลัง 2024-04-22 (ดู run_r5.clean_gold_v2)"
    rf_t = float(E["rate"].loc[t]) / 100.0
    for f, wt_ in w.items():
        if f in gset:
            kind, tab, arr = "G", GS[qi][2], GD.arrays
        elif f in fset:
            kind, tab, arr = "F", X["sels"]["FAUM"][qi][2], FD.arrays
        else:
            kind = "E"
        if kind == "E":
            sr, rank, wk = float(rec["reps"][fam_of[f]]["signal"]), rec["ranks"][fam_of[f]], ctx["wk"][f]
        else:
            sr, rank = float(tab.set_index("FundCode").loc[f, "SR12p"]), np.nan
            wk = fs.QuarterContext(arr, E["calendar"], t).weekly_return_series(f)
        assert wk.index.max() <= t and len(wk) == 52, (t, f, len(wk))
        hold_rows.append({"t": t.date(), "e": e.date(), "FundCode": f, "kind": kind, "weight": wt_,
                          "family": fam_of.get(f, ""), "sr12p": sr, "rank": rank, "rf": rf_t})
        wk_rows += [{"t": t.date(), "FundCode": f, "week": d.date(), "ret": r} for d, r in wk.items()]

H = pd.DataFrame(hold_rows)
W = pd.DataFrame(wk_rows)

ref = pd.read_csv(os.path.join(RES, "M019_weights.csv")).assign(t=lambda d: pd.to_datetime(d["t"]).dt.date)
m = ref.merge(H, on=["t", "FundCode"], how="outer", suffixes=("_ref", "_new"))
assert m["weight_ref"].notna().all() and m["weight_new"].notna().all(), "ชุดกองไม่ตรง M019_weights"
dw = float((m["weight_ref"] - m["weight_new"]).abs().max())
assert dw < 1e-12, dw
assert (H.groupby("t")["weight"].sum() - 1).abs().max() < 1e-9
assert (H.groupby("t")["kind"].apply(lambda s: (s != "E").sum()) <= 1).all(), "ขาตั้งรับมากกว่า 1 กองในไตรมาสเดียว"
print(f"REGRESSION OK · {H['t'].nunique()} ไตรมาส · max|Δw| {dw:.1e} · ทอง {int((H.kind == 'G').sum())} · ตลาดเงิน {int((H.kind == 'F').sum())} ไตรมาส"
      f" · NaN weekly {int(W.ret.isna().sum())}")

for name, df in (("holdings", H), ("weekly", W)):
    path = os.path.join(REF, f"gc75_frontier_{name}.csv")
    with open(path, "w", encoding="utf-8") as f:
        f.write(HEADER)
        df.to_csv(f, index=False)
    print("เขียน", os.path.relpath(path, common.PROJECT_ROOT), df.shape)
print(H.pivot_table(index="t", columns="kind", values="weight", aggfunc="sum").round(3).to_string())
nan = W[W.ret.isna()].groupby(["t", "FundCode"]).size()
if len(nan):
    print("weekly NaN:\n" + nan.to_string())


# ================= ผลที่เกิดขึ้นจริง (ผู้ใช้สั่ง 2026-10-14) =================
# ต่อไตรมาส × พอร์ต {MVP, max Sharpe, ERC} (น้ำหนักจาก analysis.gc75_frontier.frontier_case ของแอป · input = ไฟล์ที่เพิ่งเขียน):
# - ต้นทุน = ค่าธรรมเนียมจริง (fees.FeeModel "full" · Fee3 E/F/O) ของการสลับจากพอร์ตที่ M019 ถือจริงไตรมาสก่อน (drift ถึง e) → พอร์ตนั้น
#   (ไตรมาสแรก = ซื้อจากเงินสด) · กติกาเดียวกับ simulate.simulate_path (mark ด้วย NAV ล่าสุด ≤ e · ซื้อที่ NAV แรก ≥ e)
# - ถือแบบไม่ rebalance: Q = e → e ไตรมาสถัดไป (ไตรมาสสุดท้าย → 2025-12-31) · 1Y = e → e + 365 วัน (ตัดที่ 2025-12-31)
# - ผลตอบแทนช่วงถือ (หลังต้นทุน) · ต่อปีแบบไม่ทบต้น (× 365/วัน = นิยามเดียวกับค่าคาดหวัง mean×52)
# - vol จริง = มูลค่าพอร์ตรายวัน (วันที่มี NAV ของกองใดกองหนึ่ง · กองอื่นใช้ NAV ล่าสุด) · × √(จำนวนวัน ÷ ปี)
# - rf จริง = ดอกเบี้ยนโยบายทบต้นรายวันตลอดช่วง (r11.hurdle) ต่อปีแบบ × 365/วัน · Sharpe = (ret/ปี − rf/ปี) ÷ vol/ปี
# regression: ต่อผล Q ของ ERC ทุกไตรมาส = มูลค่าพอร์ต M019 จาก r15.sim_cases_x ณ 2025-12-31 (กติกาต้นทุนเดียวกัน)
import json
import fees
import remeasure_real_rf as rr
import run_m011 as r11
import simulate
from analysis import gc75_frontier as gf
import data_access

ref_data = data_access.load_gc75_frontier()
Hr, Wr = ref_data["holdings"], ref_data["weekly"]
fee3 = m18.Fee3(E["fd_sim"], fees.FeeData(f_codes), f_codes, fees.FeeData(GD.codes), GD.codes)
nav3 = {**E["nav_by_fund"], **FD.nav_by_fund, **GD.nav_by_fund}
PE = rr.PE
PORTS = ("MVP", "max Sharpe", "ERC (กติกาโมเดล)")


def exec_px(f, e):
    r = simulate._exec_nav(nav3, f, e)
    assert r is not None, ("ซื้อไม่ได้", f, e)
    return r[0]


def drift_of(w, e0, e1):
    """น้ำหนักของพอร์ตที่ซื้อ ณ e0 (ราคา NAV แรก ≥ e0) เมื่อ mark ที่ e1 (NAV ล่าสุด ≤ e1)."""
    val = {f: x / exec_px(f, e0) * simulate._nav_last(nav3, f, e1)[0] for f, x in w.items() if x > 0}
    s = sum(val.values())
    return {f: v / s for f, v in val.items()}


def hold(w, e, end, start_value):
    """buy-and-hold ตั้งแต่ e ถึง end · คืน (มูลค่ารายวัน Series, มูลค่า ณ end)."""
    units = {f: start_value * x / exec_px(f, e) for f, x in w.items() if x > 0}
    days = sorted({d for f in units for d in nav3[f].loc[e:end].index})
    v = pd.Series({d: sum(u * simulate._nav_last(nav3, f, d)[0] for f, u in units.items()) for d in days})
    v_end = sum(u * simulate._nav_last(nav3, f, end)[0] for f, u in units.items())
    return v, v_end


plan_e = [p["e"] for p in plan]
rows, chain = [], 1.0
for qi, t in enumerate(sorted(Hr["t"].unique())):
    t = pd.Timestamp(t)
    h_t, w_t = Hr[Hr["t"] == t], Wr[Wr["t"] == t]
    res = gf.frontier_case(h_t, w_t)
    e = pd.Timestamp(h_t["e"].iloc[0])
    assert e == plan_e[qi] and plan[qi]["t"] == t
    erc = res["weights"]["ERC (กติกาโมเดล)"]
    assert max(abs(erc.get(f, 0) - plan[qi]["weights"].get(f, 0)) for f in set(erc.index) | set(plan[qi]["weights"])) < 1e-12
    prior = drift_of(plan[qi - 1]["weights"], plan_e[qi - 1], e) if qi else {}
    end_q = min(plan_e[qi + 1], PE) if qi + 1 < len(plan_e) else PE
    end_y = min(e + pd.Timedelta(days=365), PE)
    for name in PORTS:
        w = {f: float(x) for f, x in res["weights"][name].items() if x > 1e-12}
        cost = fees.FeeModel(fee3, "full").entry_cost(e, prior, w)[0]
        s = res["summary"].loc[name]
        for hz, end in (("Q", end_q), ("1Y", end_y)):
            v, v_end = hold(w, e, end, 1.0 - cost)
            days = (end - e).days
            r_d = v.pct_change().dropna()
            ret = v_end - 1.0
            rf_p = r11.hurdle(E["rate"], e, end)
            vol = float(r_d.std(ddof=1) * np.sqrt(len(r_d) / (days / 365.0)))
            rows.append({"t": t.date(), "portfolio": name, "horizon": hz, "e": e.date(), "end": end.date(), "days": days,
                         "truncated": hz == "1Y" and end < e + pd.Timedelta(days=365), "cost": cost,
                         "ret": ret, "ret_gross": v_end / (1.0 - cost) - 1.0, "ret_ann": ret * 365.0 / days, "vol_ann": vol,
                         "rf_ann": rf_p * 365.0 / days, "sharpe": (ret * 365.0 / days - rf_p * 365.0 / days) / vol, "n_days": len(r_d),
                         "exp_ret": s["ret"], "exp_vol": s["risk"], "exp_sharpe": s["sharpe"],
                         "weights": json.dumps({f: round(x, 12) for f, x in w.items()}, sort_keys=True)})
            if name == "ERC (กติกาโมเดล)" and hz == "Q":
                chain *= 1.0 + ret

sim19 = r15.sim_cases_x(plan, nav3, E["months"], fee3, E["real"], fset=fset | gset, kinds=["full"])["full"]["values"]
ref_growth = float(sim19.loc[PE] / sim19.iloc[0])
print(f"REGRESSION ผลจริง: ต่อ ERC ทุกไตรมาส {chain:.10f} · M019 sim {ref_growth:.10f}")
assert abs(chain / ref_growth - 1) < 1e-9
R = pd.DataFrame(rows)
path = os.path.join(REF, "gc75_frontier_realized.csv")
with open(path, "w", encoding="utf-8") as f:
    f.write("# ผลที่เกิดขึ้นจริงของ MVP / max Sharpe / ERC หน้า 10 (M019) — ไฟล์อ้างอิงคงที่ (ห้ามแก้มือ)\n"
            "# ที่มา: .claude/quant_team/backtest/export_gc75_frontier.py · ต้นทุน = ค่าธรรมเนียมจริงจากพอร์ต M019 ไตรมาสก่อน · buy-and-hold · "
            "Q = ถึงวันซื้อขายรอบถัดไป · 1Y = 365 วัน (ตัดที่ 2025-12-31) · ret_ann/rf_ann = × 365/วัน · vol = รายวัน\n")
    R.to_csv(f, index=False)
print("เขียน", os.path.relpath(path, common.PROJECT_ROOT), R.shape)
pd.set_option("display.width", 250)
print(R[R.horizon == "Q"].pivot_table(index="t", columns="portfolio", values="ret").round(4).to_string())
print(R.groupby(["horizon", "portfolio"])[["ret", "sharpe", "exp_sharpe", "cost"]].mean().round(4).to_string())
