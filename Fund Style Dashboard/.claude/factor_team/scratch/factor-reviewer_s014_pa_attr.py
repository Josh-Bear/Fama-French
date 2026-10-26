"""factor-reviewer · คำนวณ L1 ทั้งช่วงแบบ P-A ด้วยโค้ดของ reviewer (numpy · ไม่ใช้ lib port) — เทียบ attribution_summary แถว L1_PA · อ่านอย่างเดียว"""
import json
from pathlib import Path
import numpy as np, pandas as pd
T = Path(".claude/factor_team"); RUN = T / "runs/S014"; D = T / "data"
F = pd.read_parquet(D / "factors_weekly.parquet").loc["2021-01-08":"2025-12-26"]; Fext = pd.read_parquet(D / "factors_ext_weekly.parquet").loc["2021-01-08":"2025-12-26"]
Feo = pd.read_parquet(D / "factors_eo_noaqr_weekly.parquet").loc["2021-01-08":"2025-12-26"]; idx = F.index; rf = F["RF_BOT"]
P = pd.read_parquet(D / "panel_weekly.parquet"); Rx = P.pivot(index="date", columns="FundCode", values="ret").sort_index().reindex(idx).sub(rf, axis=0)
H = pd.read_csv("base_data/reference/m052_frontier_holdings.csv", comment="#", parse_dates=["t", "e"]); MP = pd.read_csv(RUN / "mapping_codes.csv").set_index("FundCode")
QT = pd.read_csv(RUN / "quarters.csv", parse_dates=["t", "first_anchor", "last_anchor"])
base = pd.DataFrame({"MKT": F["MSCI_ACWI"] - rf, "FX": F["SHV_THB"] - rf, "CMA": Feo["KF_DEV_CMA"], "GOLD_XS": Feo["GLD_USD"] - F["SHV_USD"], "TDEXX": F["TDEX_THB"] - rf})
Ig = {"e_CHINAg": F["MSCI_CHINA_ALL_SHARES"] - rf, "e_ASIA": F["MSCI_ASIA_EX_JAPAN"] - rf, "e_EUROPE": F["MSCI_EUROPE"] - rf, "e_USA": F["MSCI_USA"] - rf, "e_JAPAN": F["MSCI_JAPAN"] - rf,
      "e_INDIA": F["MSCI_INDIA"] - rf, "e_HC": F["MSCI_ACWI_HC"] - rf, "e_IT": F["MSCI_ACWI_IT"] - rf, "e_VIETNAM": F["MSCI_VIETNAM"] - rf, "e_ARKK": Fext["ARKK_THB"] - rf, "e_IGF": Fext["IGF_THB"] - rf}
def resid(I, X, m):
    y = I.to_numpy(float); Xv = X.to_numpy(float); ok = m & np.isfinite(y) & np.isfinite(Xv).all(1)
    b = np.linalg.lstsq(np.column_stack([np.ones(ok.sum()), Xv[ok]]), y[ok], rcond=None)[0]; return pd.Series(y - Xv @ b[1:], index=I.index)
tot = {}
for t in sorted(H["t"].unique()):
    m = np.asarray((idx <= t) & (idx > t - pd.Timedelta(weeks=156))); X1 = base[["MKT", "FX", "CMA"]]
    row = QT[QT["t"] == t].iloc[0]; anc = idx[(idx >= row["first_anchor"]) & (idx <= row["last_anchor"])]; pos = np.array([idx.get_loc(a) for a in anc])
    fits = []
    for h in H[H["t"] == t].itertuples(index=False):
        mp = MP.loc[h.FundCode]
        if h.kind == "G": Dm = base[["GOLD_XS", "FX"]]
        else:
            Dm = X1.copy()
            if h.FundCode == "DAOL-GOLD": Dm["GOLD_XS"] = base["GOLD_XS"]
            if h.FundCode == "FCSCBSETE": Dm["TDEXX"] = base["TDEXX"]
            if mp["group_factor"] != "ไม่มี":
                nm = {"e_CHINA(grp)": "e_CHINAg"}.get(mp["group_factor"], mp["group_factor"]); Dm[nm] = resid(Ig[nm], X1, m)
        A = Dm.to_numpy(float); L = np.full_like(A, np.nan); L[1:] = A[:-1]; X = np.hstack([A, L]); y = Rx[mp["unit"]].to_numpy(float)
        ok = m & np.isfinite(y) & np.isfinite(X).all(1); b = np.linalg.lstsq(np.column_stack([np.ones(ok.sum()), X[ok]]), y[ok], rcond=None)[0]
        fits.append((h.weight, mp["unit"], list(Dm.columns), A, b))
    w = np.array([f[0] for f in fits])
    for s, p in enumerate(pos):
        r = np.array([Rx[f[1]].to_numpy(float)[p] for f in fits])
        for i, (w0, u, names, A, b) in enumerate(fits):
            K = len(names); cur, lag = A[p], A[p - 1]
            for j, c in enumerate(names):
                tot[c] = tot.get(c, 0) + w[i] * (b[1 + j] * cur[j] + b[1 + K + j] * lag[j])
            tot["A"] = tot.get("A", 0) + w[i] * b[0]; tot["E"] = tot.get("E", 0) + w[i] * (r[i] - b[0] - cur @ b[1:1 + K] - lag @ b[1 + K:])
        g = w * (1 + r + rf.to_numpy(float)[p]); w = g / g.sum()
S = pd.read_csv(RUN / "attribution_summary.csv"); fpa = S[(S.lens == "L1_PA") & S.period.str.startswith("ทั้ง")].set_index("component")["value"]
out = {k: round(v * 100, 3) for k, v in sorted(tot.items(), key=lambda kv: -abs(kv[1]))}
out["max_abs_diff_vs_file"] = float(max(abs(tot[k] - fpa[k]) for k in tot if k in fpa.index))
json.dump(out, open(T / "scratch/factor-reviewer_s014_pa_attr.json", "w"), indent=1, ensure_ascii=False); print(out)
