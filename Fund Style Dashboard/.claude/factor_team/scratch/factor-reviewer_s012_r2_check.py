"""factor-reviewer · รีวิวผล S012 รอบ 2: Shapley คู่ Dimson (คำนวณเองด้วย numpy) เทียบ shapley_E/O.csv ฉบับแก้ · paired_lens_E.csv เทียบค่าของ reviewer · อ่านอย่างเดียว"""
import itertools, json, sys
from math import factorial
from pathlib import Path
import numpy as np, pandas as pd
T = Path(".claude/factor_team"); RUN = T / "runs" / "S012"
F = pd.read_parquet(T / "data" / "factors_weekly.parquet").loc["2021-01-08":"2025-12-26"]
Feo = pd.read_parquet(T / "data" / "factors_eo_weekly.parquet").loc["2021-01-08":"2025-12-26"]
Fext = pd.read_parquet(T / "data" / "factors_ext_weekly.parquet").loc["2021-01-08":"2025-12-26"]
P = pd.read_parquet(T / "data" / "panel_weekly.parquet")
W = P.pivot(index="date", columns="FundCode", values="ret").sort_index().loc["2021-01-08":"2025-12-26"]
rf = F["RF_BOT"]; Rx = W.sub(rf, axis=0); idx = F.index
g = pd.read_csv(T / "specs" / "S012_group_map.csv"); g["unit"] = g["splice_id"].where(g["splice_id"].notna(), g["FundCode"])
SPL = {"I-GOLD*": ("I-GOLD", "IGOLD-G"), "ES-GCG*": ("TMB-ES-GCG", "ES-GCG-A"), "ES-GINNO*": ("TMB-ES-GINNO", "ES-GINNO-A"), "ES-GINFRA*": ("TMBGINFRA", "ES-GINFRA-A")}
wk = pd.Timestamp("2023-12-08")
R = pd.DataFrame({u: (Rx[SPL[u][0]].where(idx < wk).combine_first(Rx[SPL[u][1]].where(idx >= wk)) if u in SPL else Rx[d["FundCode"].iloc[0]]) for u, d in g.groupby("unit")})
gu = g.drop_duplicates("unit").set_index("unit")
tr = (idx >= "2021-01-08") & (idx <= "2023-12-29"); rows = tr & (np.arange(len(idx)) >= 1)
sets = pd.read_csv(RUN / "sets.csv").set_index("unit")
EV = sorted(sets.index[(sets.policy == "E") & sets["eval"]]); EVO = sorted(sets.index[(sets.policy == "O") & sets["eval"]])
MKT = F["MSCI_ACWI"] - rf; FX = F["SHV_THB"] - rf; CMA = Feo["KF_DEV_CMA"]
X1 = pd.concat([MKT.rename("MKT"), FX.rename("FX"), CMA.rename("CMA")], axis=1)
def resid(I, Pdf):
    y = I.to_numpy(float); Pv = Pdf.to_numpy(float); ok = tr & np.isfinite(y) & np.isfinite(Pv).all(1)
    b = np.linalg.lstsq(np.column_stack([np.ones(ok.sum()), Pv[ok]]), y[ok], rcond=None)[0]; return pd.Series(y - Pv @ b[1:], index=I.index)
I = {"e_CHINA(grp)": ("e_CHINAg", F["MSCI_CHINA_ALL_SHARES"] - rf), "e_ASIA": ("e_ASIA", F["MSCI_ASIA_EX_JAPAN"] - rf), "e_EUROPE": ("e_EUROPE", F["MSCI_EUROPE"] - rf),
     "e_USA": ("e_USA", F["MSCI_USA"] - rf), "e_JAPAN": ("e_JAPAN", F["MSCI_JAPAN"] - rf), "e_INDIA": ("e_INDIA", F["MSCI_INDIA"] - rf), "e_HC": ("e_HC", F["MSCI_ACWI_HC"] - rf),
     "e_IT": ("e_IT", F["MSCI_ACWI_IT"] - rf), "e_VIETNAM": ("e_VIETNAM", F["MSCI_VIETNAM"] - rf), "e_ARKK": ("e_ARKK", Fext["ARKK_THB"] - rf), "e_IGF": ("e_IGF", Fext["IGF_THB"] - rf)}
EG = {k: (nm, resid(s, X1)) for k, (nm, s) in I.items()}
def lp(s):
    a = np.asarray(s, float); l = np.full_like(a, np.nan); l[1:] = a[:-1]; return np.column_stack([a, l])
def shap(y, bl):
    X = np.hstack(bl); ok = rows & np.isfinite(y) & np.isfinite(X).all(1); K = len(bl)
    def v(S):
        if not S: return 0.0
        A = np.column_stack([np.ones(ok.sum())] + [bl[k][ok] for k in S]); b = np.linalg.lstsq(A, y[ok], rcond=None)[0]; e = y[ok] - A @ b
        return 1 - e @ e / ((y[ok] - y[ok].mean()) ** 2).sum()
    vv = {S: v(list(S)) for r in range(K + 1) for S in itertools.combinations(range(K), r)}
    phi = np.zeros(K)
    for k in range(K):
        for S, val in vv.items():
            if k in S: continue
            phi[k] += factorial(len(S)) * factorial(K - len(S) - 1) / factorial(K) * (vv[tuple(sorted(S + (k,)))] - val)
    return phi, vv[tuple(range(K))]
sh = pd.read_csv(RUN / "shapley_E.csv"); fl = pd.read_csv(RUN / "fund_level_E.csv")
out = {}
mx1 = mx2 = mxr = 0.0
for u in EV:
    y = R[u].to_numpy(float)
    p1, r1 = shap(y, [lp(MKT), lp(FX), lp(CMA)])
    f1 = sh[(sh.unit == u) & (sh.row == "E-X1")].set_index("factor")
    mx1 = max(mx1, max(abs(p1[k] - f1.loc[n, "phi"]) for k, n in enumerate(["MKT", "FX", "CMA"])))
    r2_fit = fl[(fl.row == "E-X1") & (fl.unit == u)]["r2"].iloc[0]
    mxr = max(mxr, abs(r1 - r2_fit))
    gf = gu.loc[u, "group_factor"]
    if gf != "ไม่มี":
        nm, e = EG[gf]
        p2, r2 = shap(y, [lp(MKT), lp(FX), lp(CMA), lp(e)])
        f2 = sh[(sh.unit == u) & (sh.row == "E-X2")].set_index("factor")
        mx2 = max(mx2, max(abs(p2[k] - f2.loc[n, "phi"]) for k, n in enumerate(["MKT", "FX", "CMA", nm])))
out["E-X1_max_abs_dphi_vs_new_file"] = mx1
out["E-X2_groupfunds_max_abs_dphi_vs_new_file"] = mx2
out["E-X1_sum_phi_vs_fund_level_r2_max_abs"] = mxr
# O
sho = pd.read_csv(RUN / "shapley_O.csv")
gold = pd.DataFrame({"GOLD_XS": Feo["GLD_USD"] - F["SHV_USD"], "FX": FX})
reit = pd.DataFrame({"MKT": MKT, "REIT_e": resid(Fext["REET_USD"] - F["SHV_USD"], MKT.to_frame()), "FX": FX, "TERM": F["IEF_USD"] - F["SHV_USD"]})
mo = 0.0
print(sho.columns.tolist(), sho["row"].unique() if "row" in sho.columns else "")
for u in EVO:
    df = gold if gu.loc[u, "o_group"] == "ทอง" else reit
    p, _ = shap(R[u].to_numpy(float), [lp(df[c]) for c in df.columns])
    f = sho[(sho.unit == u) & (sho["row"].str.startswith("O-X")) & ~sho["row"].str.startswith("O-X′")].set_index("factor") if "row" in sho.columns else sho[sho.unit == u].set_index("factor")
    mo = max(mo, max(abs(p[k] - f.loc[c, "phi"]) for k, c in enumerate(df.columns)))
out["O-X_max_abs_dphi_vs_new_file"] = mo
pl = pd.read_csv(RUN / "paired_lens_E.csv"); out["paired_lens"] = pl[["question", "subset", "n", "diff_of_medians_locked", "median_of_fund_diffs", "ci_lo", "ci_hi", "frac_worse", "frac_improved"]].round(4).to_dict(orient="records")
json.dump(out, open(T / "scratch" / "factor-reviewer_s012_r2_check.json", "w"), indent=1, ensure_ascii=False, default=float)
print(json.dumps(out, indent=1, ensure_ascii=False, default=float))
