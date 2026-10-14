"""export_top3.py — export curves/metrics 5 series x 3 cases (full/nofront/flat) บน universe เต็ม offset 0 · ไม่ใช่ trial · reuse fulluniv_run
+ M019-LC3-GCGOLD (ผู้ใช้สั่งเพิ่มในหน้า 9 2026-10-14 · เส้นทางโค้ด run_m019 · regression = M019_results.csv)
เขียน results/EXPORT_top3_*.csv และไฟล์อ้างอิงของแอป base_data/reference/tf_top3_{curves,metrics}.csv
รัน: PYTHONPATH=. ./.venv/bin/python .claude/quant_team/backtest/export_top3.py"""
import os, sys
THIS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, THIS)
import numpy as np, pandas as pd
import common, simulate
import remeasure_real_rf as rr
import robust_offsets as ro
import fulluniv_run as fu
import fees
import run_m015 as r15
import run_m018 as m18
import run_m019 as m19

RES = common.RESULTS_DIR
SER = {"GC75_MMF": "M015-FAUM", "TREND25": "Trend25", "M012_QFS": "M012-QF-S", "B0": "B0"}
REFNAME = {"GC75_MMF": "M015-FAUM", "TREND25": "Trend25", "M012_QFS": "M012-QF-S", "B0": "B0"}
CASES = ["full", "nofront", "flat"]
# n_trials ของ DSR = n_trials_cumulative สูงสุดใน trials.csv ณ ตอน export (อ่านจาก ledger · ไม่ hard-code)
# แอปแสดงค่านี้จาก config.TF_TOP3_N_TRIALS → ต้องอัปเดตให้ตรง (test_tf_top3_reference ตรวจกับ ledger)
N_TRIALS = int(pd.read_csv(os.path.join(os.path.dirname(THIS), "trials.csv"))["n_trials_cumulative"].max())
REF_DIR = os.path.join(common.PROJECT_ROOT, "base_data", "reference")
holder = {}
E, P, X = fu.build_env_and_plans(0, holder)
FD, real = holder["FD"], E["real"]
ref = pd.read_csv(os.path.join(RES, "FULLUNIV_models.csv")).set_index("model")
curves, mets, rfm_out, reg = [], [], None, []
# M019: เส้นทางเดียวกับ run_m019.main (ขาทอง + ค่าธรรมเนียม E/F/O แยก)
profile = r15.load_profile()
f_codes = sorted(FD.profile.index[FD.profile["Fund Policy"] == "F"])
GD = m18.GData(profile, E, f_codes)
GS = m18.gold_sels(GD, E)
fee3 = m18.Fee3(E["fd_sim"], fees.FeeData(f_codes), f_codes, fees.FeeData(GD.codes), GD.codes)
nav3 = {**E["nav_by_fund"], **FD.nav_by_fund, **GD.nav_by_fund}
sl19, _ = m19.stream_lc(E["ctx_h"], E["quals"], m19.POOL, ordered=False)
plan19 = m19.gc_gold_plan(E, X, GS, sl19)
assert all("K-GOLD-C(A)" not in p["weights"] for p in plan19)       # NAV class นี้ผิดหลัง 2024-04-22 (run_r5.clean_gold_v2)


def sims_of(s, m):
    if s == "M019":
        return r15.sim_cases_x(plan19, nav3, E["months"], fee3, real, fset=set(FD.codes) | set(GD.codes), kinds=CASES)
    return fu.sim_model(m, P[m], E, FD, CASES)


SER["M019"] = REFNAME["M019"] = "M019-LC3-GCGOLD"
ref19 = pd.read_csv(os.path.join(RES, "M019_results.csv")).set_index("model_id").loc["M019-LC3-GCGOLD"]
for s, m in SER.items():
    sims = sims_of(s, m)
    for c in CASES:
        v = sims[c]["values"]
        v = v[v.index <= rr.PE]
        m_ = rr.metrics(v, real)
        r, rfm = m_["r"], m_["rfm"]
        lo, hi = rr.boot_ci(r, rfm)
        base = v / v.iloc[0]
        # recompute check: curve -> monthly returns -> excess - rf
        r2 = base.pct_change().dropna()
        sh2 = float(((r2 - rfm.reindex(r2.index)).mean() * 12) / (r2.std(ddof=1) * np.sqrt(12)))
        assert abs(sh2 - m_["sharpe"]) < 1e-10, (s, c, sh2, m_["sharpe"])
        for d, x in base.items():
            curves.append((s, c, d.date().isoformat(), float(x)))
        mets.append({"series": s, "case": c, "sharpe": m_["sharpe"], "cagr": m_["cagr"], "vol": m_["vol"], "max_dd": m_["max_dd"],
                     "dsr": rr.dsr_s(r, rfm, N_TRIALS), "ci_lo": lo, "ci_hi": hi, "cost_pct_yr": sims[c]["cost_bp_yr"] / 100.0,
                     "turnover_yr": sims[c]["turn_yr"], "n_months": m_["n_months"], "sharpe_recomputed": sh2})
        if rfm_out is None:
            rfm_out = rfm
        else:
            assert rfm_out.reindex(rfm.index).equals(rfm) or rfm.index.equals(rfm_out.index)
        if c in ("full", "nofront"):
            col = "sharpe_" + c
            rsrc = ref19 if s == "M019" else ref.loc[REFNAME[s]]
            reg.append((s, c, m_["sharpe"], float(rsrc[col]), m_["cagr"], float(rsrc["cagr_" + c])))
print("REGRESSION")
ok = True
for s, c, g, rf_, cg, cr in reg:
    good = abs(g - rf_) < 5e-7 and abs(cg - cr) < 5e-7
    ok &= good
    print(f"  {s:9s} {c:8s} got {g:.6f} ref {rf_:.6f} cagr {cg:.5f}/{cr:.5f} {'OK' if good else 'FAIL'}")
if not ok:
    print("REGRESSION FAIL"); sys.exit(2)
cdf = pd.DataFrame(curves, columns=["series", "case", "date", "value"])
cdf.to_csv(os.path.join(RES, "EXPORT_top3_curves.csv"), index=False)
M = pd.DataFrame(mets)
M.drop(columns=["sharpe_recomputed"]).to_csv(os.path.join(RES, "EXPORT_top3_metrics.csv"), index=False)
rfm_out.rename("rf").rename_axis("date").to_csv(os.path.join(RES, "EXPORT_top3_rf_month.csv"))
HDR = ("# ผล backtest walk-forward TOP3 + M019 + B0 สำหรับแอปหน้า 9 ส่วนที่ 2 — ไฟล์อ้างอิงคงที่ (ห้ามแก้มือ)\n"
       "# ที่มา: .claude/quant_team/backtest/export_top3.py · universe เต็ม · rf = ดอกเบี้ยนโยบาย ธปท. จริง · FeeData(legacy=False)\n"
       "# rebalance ตัดสินใจสิ้น มี.ค./มิ.ย./ก.ย./ธ.ค. ซื้อขายวันทำการที่ 2 · 2022-04-04 → 2025-12-31 (45 เดือน) · case: full / nofront / flat (0.5%/ข้าง)\n"
       f"# export {pd.Timestamp.now():%Y-%m-%d} · dsr ที่ n_trials = {N_TRIALS} (trials.csv) · M019 = หุ้น 3 กอง LC + ERC 40% + GC75 + ขาทอง\n")
# แอปแสดงมูลค่าพอร์ตเริ่ม 100 (รูปแบบไฟล์อ้างอิงเดิม) · results/EXPORT_* คงฐาน 1.0
for name, df in (("curves", cdf.assign(value=cdf["value"] * 100.0)), ("metrics", M.drop(columns=["sharpe_recomputed"]))):
    with open(os.path.join(REF_DIR, f"tf_top3_{name}.csv"), "w", encoding="utf-8") as f:
        f.write(HDR)
        df.to_csv(f, index=False)
print(f"เขียน base_data/reference/tf_top3_*.csv · N_TRIALS = {N_TRIALS}")
pd.set_option("display.width", 200)
print(M.pivot(index="series", columns="case", values="sharpe").round(3))
print(M.round(4).to_string())
print(cdf.groupby(["series", "case"]).agg(n=("value", "size"), d0=("date", "min"), d1=("date", "max"), v0=("value", "first")).to_string())
