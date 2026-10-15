"""export_gc75_frontier.py — input ของ efficient frontier หน้า 10 = **M019-LC3-GCGOLD** (universe เต็ม · offset 0) · ไม่ใช่ trial
(เดิม 2026-10-07 เป็น M015-FAUM · ผู้ใช้สั่งเปลี่ยนเป็น M019 2026-10-13 · ผลจริง 2026-10-14 · ตัวช่วยร่วม frontier_export.py 2026-10-14)
ต่อไตรมาส t (15 ไตรมาส 2022-03-31 … 2025-09-30): กองหุ้น 3 กองที่ M019 ถือจริง (อันดับ 1 + เติม max ρ_adj ต่ำสุด · ERC เพดาน 40%)
+ ขาตั้งรับ (กองทอง AUM ใหญ่สุด = kind G · ไม่มี → กองตลาดเงิน = kind F) · น้ำหนักจริง · SR12′ ณ t · weekly return 52 สัปดาห์ ≤ t
· rf = ดอกเบี้ยนโยบาย ธปท. ที่มีผล ณ t · ผลที่เกิดขึ้นจริงของ MVP / max Sharpe / Model (= ERC ของแอป)
regression: น้ำหนัก = results/M019_weights.csv ทุกบิต · ต่อผล Q ของ Model ทุกไตรมาส = มูลค่าพอร์ต M019 จาก r15.sim_cases_x
รัน: PYTHONPATH=. ./.venv/bin/python .claude/quant_team/backtest/export_gc75_frontier.py
"""
import os, sys
THIS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, THIS)
import numpy as np, pandas as pd
import common
import fees
import fulluniv_run as fu
import remeasure_real_rf as rr
import run_m015 as r15
import run_m018 as m18
import run_m019 as m19
import frontier_export as fx
import data_access
from analysis import gc75_frontier as gf

RES = common.RESULTS_DIR
REF = os.path.join(common.PROJECT_ROOT, "base_data", "reference")
SRC = ("ที่มา: .claude/quant_team/backtest/export_gc75_frontier.py · universe เต็ม · offset 0 · "
       "rebalance สิ้นไตรมาส 2022-03-31 … 2025-09-30")

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
for qi, p in enumerate(plan):
    eq = [f for f in p["weights"] if f not in fset and f not in gset]
    assert not recs[qi]["fallback"] and set(eq) == set(recs[qi]["S"].values()) and len(eq) == 3, (p["t"], eq)


def info(qi, f, kind):
    if kind == "E":
        fam = {fc: fm for fm, fc in recs[qi]["S"].items()}[f]
        return fam, float(recs[qi]["reps"][fam]["signal"]), recs[qi]["ranks"][fam]
    tab = GS[qi][2] if kind == "G" else X["sels"]["FAUM"][qi][2]
    return "", float(tab.set_index("FundCode").loc[f, "SR12p"]), np.nan


H, W = fx.holdings_weekly(plan, E, fset, gset, FD, GD, info)
ref = pd.read_csv(os.path.join(RES, "M019_weights.csv")).assign(t=lambda d: pd.to_datetime(d["t"]).dt.date)
m = ref.merge(H, on=["t", "FundCode"], how="outer", suffixes=("_ref", "_new"))
assert m["weight_ref"].notna().all() and m["weight_new"].notna().all(), "ชุดกองไม่ตรง M019_weights"
dw = float((m["weight_ref"] - m["weight_new"]).abs().max())
assert dw < 1e-12, dw
print(f"REGRESSION OK · {H['t'].nunique()} ไตรมาส · max|Δw| {dw:.1e} · ทอง {int((H.kind == 'G').sum())} · ตลาดเงิน {int((H.kind == 'F').sum())} ไตรมาส"
      f" · NaN weekly {int(W.ret.isna().sum())}")
TITLE = "input efficient frontier หน้า 10 — M019-LC3-GCGOLD (หุ้น 3 กอง + ขาทอง/ตลาดเงิน) · ไฟล์อ้างอิงคงที่ (ห้ามแก้มือ)"
fx.write_reference(os.path.join(REF, "gc75_frontier_holdings.csv"), [TITLE, SRC], H)
fx.write_reference(os.path.join(REF, "gc75_frontier_weekly.csv"), [TITLE, SRC], W)

# ---------------- ผลที่เกิดขึ้นจริง (frontier_export.realized) ----------------
fee3 = m18.Fee3(E["fd_sim"], fees.FeeData(f_codes), f_codes, fees.FeeData(GD.codes), GD.codes)
nav3 = {**E["nav_by_fund"], **FD.nav_by_fund, **GD.nav_by_fund}
d = data_access.load_gc75_frontier()
R, chain = fx.realized(d["holdings"], d["weekly"], plan, nav3, fee3, E["rate"], rr.PE, gf.frontier_case, use_held_weights=False)
sim = r15.sim_cases_x(plan, nav3, E["months"], fee3, E["real"], fset=fset | gset, kinds=["full"])["full"]["values"]
growth = float(sim.loc[rr.PE] / sim.iloc[0])
print(f"REGRESSION ผลจริง: ต่อ Model ทุกไตรมาส {chain:.10f} · M019 sim {growth:.10f}")
assert abs(chain / growth - 1) < 1e-9
fx.write_reference(os.path.join(REF, "gc75_frontier_realized.csv"),
                   ["ผลที่เกิดขึ้นจริงของ MVP / max Sharpe / Model Portfolio หน้า 10 (M019) — ไฟล์อ้างอิงคงที่ (ห้ามแก้มือ)",
                    SRC + " · ต้นทุน = ค่าธรรมเนียมจริงจากพอร์ตโมเดลไตรมาสก่อน · buy-and-hold · Q = ถึงวันซื้อขายรอบถัดไป · "
                          "1Y = 365 วัน (ตัดที่ 2025-12-31) · ret_ann/rf_ann = × 365/วัน · vol = รายวัน"], R)
