"""export_top3.py — export curves/metrics 4 series x 3 cases (full/nofront/flat) บน universe เต็ม offset 0 · ไม่ใช่ trial · reuse fulluniv_run
รัน: PYTHONPATH=. ./.venv/bin/python .claude/quant_team/backtest/export_top3.py"""
import os, sys
THIS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, THIS)
import numpy as np, pandas as pd
import common, simulate
import remeasure_real_rf as rr
import robust_offsets as ro
import fulluniv_run as fu

RES = common.RESULTS_DIR
SER = {"GC75_MMF": "M015-FAUM", "TREND25": "Trend25", "M012_QFS": "M012-QF-S", "B0": "B0"}
REFNAME = {"GC75_MMF": "M015-FAUM", "TREND25": "Trend25", "M012_QFS": "M012-QF-S", "B0": "B0"}
CASES = ["full", "nofront", "flat"]
holder = {}
E, P, X = fu.build_env_and_plans(0, holder)
FD, real = holder["FD"], E["real"]
ref = pd.read_csv(os.path.join(RES, "FULLUNIV_models.csv")).set_index("model")
curves, mets, rfm_out, reg = [], [], None, []
for s, m in SER.items():
    sims = fu.sim_model(m, P[m], E, FD, CASES)
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
                     "dsr": rr.dsr_s(r, rfm, 32), "ci_lo": lo, "ci_hi": hi, "cost_pct_yr": sims[c]["cost_bp_yr"] / 100.0,
                     "turnover_yr": sims[c]["turn_yr"], "n_months": m_["n_months"], "sharpe_recomputed": sh2})
        if rfm_out is None:
            rfm_out = rfm
        else:
            assert rfm_out.reindex(rfm.index).equals(rfm) or rfm.index.equals(rfm_out.index)
        if c in ("full", "nofront"):
            col = "sharpe_" + c
            reg.append((s, c, m_["sharpe"], float(ref.loc[REFNAME[s], col]), m_["cagr"], float(ref.loc[REFNAME[s], "cagr_" + c])))
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
pd.set_option("display.width", 200)
print(M.pivot(index="series", columns="case", values="sharpe").round(3))
print(M.round(4).to_string())
print(cdf.groupby(["series", "case"]).agg(n=("value", "size"), d0=("date", "min"), d1=("date", "max"), v0=("value", "first")).to_string())
