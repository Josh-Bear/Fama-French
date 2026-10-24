"""factor-reviewer · รีวิวผล S012/S013 · คำนวณซ้ำตัวเลขหลักด้วยโค้ดของ reviewer เอง (numpy ล้วน · ไม่เรียก lib ของทีมในการ fit)
อ่านอย่างเดียว · เขียนเฉพาะ scratch/factor-reviewer_s012_result_check.json
รันจาก root:  PYTHONPATH=. ./.venv/bin/python .claude/factor_team/scratch/factor-reviewer_s012_result_check.py
"""
import itertools
import json
from pathlib import Path

import numpy as np
import pandas as pd

T = Path(".claude/factor_team")
D = T / "data"
RUN = T / "runs" / "S012"
OUT = T / "scratch" / "factor-reviewer_s012_result_check.json"

# ---------- ข้อมูล (อ่าน parquet ตรง) ----------
F = pd.read_parquet(D / "factors_weekly.parquet").loc["2021-01-08":"2025-12-26"]
Feo = pd.read_parquet(D / "factors_eo_weekly.parquet").loc["2021-01-08":"2025-12-26"]
Fext = pd.read_parquet(D / "factors_ext_weekly.parquet").loc["2021-01-08":"2025-12-26"]
P = pd.read_parquet(D / "panel_weekly.parquet")
W = P.pivot(index="date", columns="FundCode", values="ret").sort_index().loc["2021-01-08":"2025-12-26"]
assert (W.index == F.index).all() and (F.index == Feo.index).all() and (F.index == Fext.index).all()
rf = F["RF_BOT"]
Rx = W.sub(rf, axis=0)
idx = F.index
res = {"max_index": str(idx.max()), "n_rows": int(len(idx))}

g = pd.read_csv(T / "specs" / "S012_group_map.csv")
g["unit"] = g["splice_id"].where(g["splice_id"].notna(), g["FundCode"])
SPL = {"I-GOLD*": ("I-GOLD", "IGOLD-G"), "ES-GCG*": ("TMB-ES-GCG", "ES-GCG-A"), "ES-GINNO*": ("TMB-ES-GINNO", "ES-GINNO-A"),
       "ES-GINFRA*": ("TMBGINFRA", "ES-GINFRA-A")}
wk = pd.Timestamp("2023-12-08")
cols = {}
for u, d in g.groupby("unit"):
    if u in SPL:
        o, n = SPL[u]
        s = Rx[o].where(idx < wk).combine_first(Rx[n].where(idx >= wk))
    else:
        assert len(d) == 1, u
        s = Rx[d["FundCode"].iloc[0]]
    cols[u] = s
R = pd.DataFrame(cols)
gu = g.drop_duplicates("unit").set_index("unit")
res["n_units"] = {"E": int((gu.policy == "E").sum()), "O": int((gu.policy == "O").sum())}

tr = (idx >= "2021-01-08") & (idx <= "2023-12-29")
te = (idx >= "2024-01-05") & (idx <= "2025-12-26")
pos1 = np.arange(len(idx)) >= 1
ntr = R.loc[tr & pos1].notna().sum()
nte = R.loc[te].notna().sum()
E_units = [u for u in gu.index if gu.loc[u, "policy"] == "E"]
O_units = [u for u in gu.index if gu.loc[u, "policy"] == "O"]
EVAL_E = sorted([u for u in E_units if ntr[u] >= 104 and nte[u] >= 52])
EVAL_O = sorted([u for u in O_units if ntr[u] >= 104 and nte[u] >= 52])
sets = pd.read_csv(RUN / "sets.csv").set_index("unit")
res["EVAL_E_n"] = len(EVAL_E)
res["EVAL_E_equal_sets_csv"] = sorted(sets.index[(sets.policy == "E") & sets["eval"]]) == EVAL_E
res["EVAL_O_n"] = len(EVAL_O)


# ---------- regression ของ reviewer ----------
def dimson(Fdf):
    A = Fdf.to_numpy(float)
    L = np.full_like(A, np.nan)
    L[1:] = A[:-1]
    return np.hstack([A, L])


def fit(y, Dm, m_tr, m_te, min_tr=52, min_te=52):
    ok = m_tr & np.isfinite(y) & np.isfinite(Dm).all(1)
    n = int(ok.sum())
    if n < min_tr:
        return None
    X = np.column_stack([np.ones(n), Dm[ok]])
    b, *_ = np.linalg.lstsq(X, y[ok], rcond=None)
    e = y[ok] - X @ b
    ssr = float(e @ e)
    sst = float(((y[ok] - y[ok].mean()) ** 2).sum())
    p = X.shape[1]
    r2 = 1 - ssr / sst
    adj = 1 - (1 - r2) * (n - 1) / (n - p)
    bic = n * np.log(ssr / n) + p * np.log(n)
    okt = m_te & np.isfinite(y) & np.isfinite(Dm).all(1)
    r2o = np.nan
    if okt.sum() >= min_te:
        yh = b[0] + Dm[okt] @ b[1:]
        yt = y[okt]
        r2o = 1 - ((yt - yh) ** 2).sum() / ((yt - yt.mean()) ** 2).sum()
    return dict(adj=adj, r2=r2, bic=bic, r2o=r2o, b=b, n=n)


def resid_on(I, Pdf, m_tr):
    """e = I − b'P (train · เก็บค่าคงที่)"""
    y = I.to_numpy(float)
    Pv = Pdf.to_numpy(float)
    ok = m_tr & np.isfinite(y) & np.isfinite(Pv).all(1)
    X = np.column_stack([np.ones(ok.sum()), Pv[ok]])
    b = np.linalg.lstsq(X, y[ok], rcond=None)[0]
    return pd.Series(y - Pv @ b[1:], index=I.index), b


MKT = (F["MSCI_ACWI"] - rf).rename("MKT")
FX = (F["SHV_THB"] - rf).rename("FX")
CMA = Feo["KF_DEV_CMA"].rename("CMA")
X0 = MKT.to_frame()
X1 = pd.concat([MKT, FX, CMA], axis=1)
F3A = pd.DataFrame({"MKT": MKT, "BOND": F["AGG_THB"] - rf, "GOLD": F["Gold_THB"] - rf, "FX": FX})


def table(units, model_of):
    out = {}
    for u in units:
        r = fit(R[u].to_numpy(float), dimson(model_of(u)), tr, te)
        out[u] = r
    return out


fl = pd.read_csv(RUN / "fund_level_E.csv")


def cmp_row(name, tab):
    a = fl[(fl.row == name) & fl.in_EVAL].set_index("unit")
    mine = pd.Series({u: tab[u]["r2o"] for u in EVAL_E})
    mine_adj = pd.Series({u: tab[u]["adj"] for u in EVAL_E})
    return dict(med_r2oos_mine=float(mine.median()), med_adj_mine=float(mine_adj.median()),
                med_r2oos_file=float(a.loc[EVAL_E, "r2_oos"].median()),
                max_abs_diff_r2oos=float((mine - a.loc[EVAL_E, "r2_oos"]).abs().max()),
                max_abs_diff_adj=float((mine_adj - a.loc[EVAL_E, "adj_r2"]).abs().max())), mine


res["E-X0"], r_x0 = cmp_row("E-X0", table(EVAL_E, lambda u: X0))
res["E-X1"], r_x1 = cmp_row("E-X1", table(EVAL_E, lambda u: X1))
res["3a"], r_3a = cmp_row("③a", table(EVAL_E, lambda u: F3A))

# ---------- E-X2: factor กลุ่ม residualize บน X1 (train) ----------
I = {"e_CHINA(grp)": F["MSCI_CHINA_ALL_SHARES"] - rf, "e_ASIA": F["MSCI_ASIA_EX_JAPAN"] - rf, "e_EUROPE": F["MSCI_EUROPE"] - rf,
     "e_USA": F["MSCI_USA"] - rf, "e_JAPAN": F["MSCI_JAPAN"] - rf, "e_INDIA": F["MSCI_INDIA"] - rf, "e_HC": F["MSCI_ACWI_HC"] - rf,
     "e_IT": F["MSCI_ACWI_IT"] - rf, "e_VIETNAM": F["MSCI_VIETNAM"] - rf, "e_ARKK": Fext["ARKK_THB"] - rf, "e_IGF": Fext["IGF_THB"] - rf}
EG = {k: resid_on(v, X1, tr)[0].rename(k) for k, v in I.items()}
gf = gu["group_factor"]


def x2_model(u):
    k = gf[u]
    return X1 if k == "ไม่มี" else pd.concat([X1, EG[k]], axis=1)


res["E-X2"], r_x2 = cmp_row("E-X2", table(EVAL_E, x2_model))
# drop-one ของ factor กลุ่ม (E-X2 − E-X1 บนสมาชิก EVAL) · median ΔR²_oos / ΔBIC
t1 = table(EVAL_E, lambda u: X1)
t2 = table(EVAL_E, x2_model)
dd = {}
for k in I:
    mem = [u for u in EVAL_E if gf[u] == k]
    dr = [t2[u]["r2o"] - t1[u]["r2o"] for u in mem]
    db = [t2[u]["bic"] - t1[u]["bic"] for u in mem]
    dd[k] = dict(n=len(mem), med_d_r2oos=float(np.median(dr)), med_d_bic=float(np.median(db)))
res["group_drop_one"] = dd

# ---------- E-PCA-a1: PCA corr บน balanced 97 (train) ----------
BAL = sorted(sets.index[sets["pca_balanced"] & (sets.policy == "E")])
Xb = R.loc[tr, BAL].to_numpy(float)
assert np.isfinite(Xb).all() and Xb.shape == (156, 97)
mu, sd = Xb.mean(0), Xb.std(0)
Z = (Xb - mu) / sd
w, V = np.linalg.eigh(Z.T @ Z / Z.shape[0])
o = np.argsort(w)[::-1]
Lam = V[:, o[:3]]
Xall = R[BAL].to_numpy(float) / sd
fpc = np.full((len(idx), 3), np.nan)
for t in range(len(idx)):
    a = np.isfinite(Xall[t])
    if a.sum() >= 0.5 * len(BAL):
        fpc[t] = np.linalg.lstsq(Lam[a], Xall[t, a], rcond=None)[0]
PCdf = pd.DataFrame(fpc, index=idx, columns=["PC1", "PC2", "PC3"])
res["E-PCA-a1"], r_pc = cmp_row("E-PCA-a1", table(EVAL_E, lambda u: PCdf))
res["eig_top5"] = [float(x) for x in w[o[:5]]]

# Q-E1 / Q-E2 / Q-E3 แบบผลต่างของ median และ median ของผลต่างรายกอง
A1 = pd.read_parquet(T / "runs" / "S003" / "factors_S003_weekly.parquet")
A1a = A1[[f"1a__PC{i}" for i in range(1, 5)]].reindex(idx)
r_1a = pd.Series({u: fit(R[u].to_numpy(float), dimson(A1a), tr, te)["r2o"] for u in EVAL_E})
q = {}
for nm, a_, b_ in (("Q-E1 E-X2 − E-PCA-a1", r_x2, r_pc), ("Q-E2 E-X1 − 3a", r_x1, r_3a), ("Q-E3 E-PCA-a1 − 1a", r_pc, r_1a)):
    q[nm] = dict(diff_of_medians=float(a_.median() - b_.median()), median_of_paired_diff=float((a_ - b_).median()),
                 share_funds_pos=float(((a_ - b_) > 0).mean()))
res["QE"] = q
inpca = [u for u in EVAL_E if u in BAL]
outpca = [u for u in EVAL_E if u not in BAL]
res["QE1_in_out_pca"] = dict(n_in=len(inpca), n_out=len(outpca), in_diff=float(r_x2[inpca].median() - r_pc[inpca].median()),
                             out_diff=float(r_x2[outpca].median() - r_pc[outpca].median()))
# QE1 บนกองที่ไม่มี factor กลุ่ม (E-X2 = E-X1)
nog = [u for u in EVAL_E if gf[u] == "ไม่มี"]
wg = [u for u in EVAL_E if gf[u] != "ไม่มี"]
res["QE1_by_groupfactor"] = dict(n_with=len(wg), n_without=len(nog),
                                 with_diff=float(r_x2[wg].median() - r_pc[wg].median()),
                                 without_diff=float(r_x2[nog].median() - r_pc[nog].median()),
                                 without_EX2_med=float(r_x2[nog].median()), without_PCA_med=float(r_pc[nog].median()))

# ---------- stepwise: ΔBIC median ข้ามตัวแทน ----------
reps = list(pd.read_csv(RUN / "sel_reps.csv").query("is_rep")["FundCode"])
res["n_reps"] = len(reps)
eCH, bch = resid_on(F["MSCI_CHINA_ALL_SHARES"] - rf, X0, tr)
pool = pd.DataFrame({"e_CHINA": eCH, "EMDM": F["MSCI_EM"] - F["MSCI_WORLD"], "TERM": F["IEF_USD"] - F["SHV_USD"],
                     "SMB": Feo["KF_DEV_SMB"], "HML": Feo["KF_DEV_HML"], "RMW": Feo["KF_DEV_RMW"], "CMA": Feo["KF_DEV_CMA"],
                     "WML": Feo["KF_DEV_WML"], "JKP_EM_value": Feo["JKP_EM_value"], "JKP_EM_momentum": Feo["JKP_EM_momentum"], "FX": FX})


def bic_on(y, Dm, ok):
    n = int(ok.sum())
    X = np.column_stack([np.ones(n), Dm[ok]])
    b = np.linalg.lstsq(X, y[ok], rcond=None)[0]
    e = y[ok] - X @ b
    return n * np.log((e @ e) / n) + X.shape[1] * np.log(n)


def score(core_df, cand):
    DM = dimson(core_df)
    DJ = dimson(pool[[cand]])
    out = []
    for u in reps:
        y = R[u].to_numpy(float)
        ok = tr & np.isfinite(y) & np.isfinite(DM).all(1) & np.isfinite(DJ).all(1)
        if ok.sum() < 52:
            continue
        out.append(bic_on(y, np.hstack([DM, DJ]), ok) - bic_on(y, DM, ok))
    return float(np.median(out)), len(out)


sw = {}
sw["round1"] = {c: score(X0, c)[0] for c in pool.columns}
sw["round2_given_FX"] = {c: score(pd.concat([MKT, FX], axis=1), c)[0] for c in pool.columns if c != "FX"}
sw["round3_given_FX_CMA"] = {c: score(X1, c)[0] for c in pool.columns if c not in ("FX", "CMA")}
allc = pd.read_csv(RUN / "stepwise_E_all_candidates.csv").query("tag == 'real'")
mx = 0.0
for r_, key in ((1, "round1"), (2, "round2_given_FX"), (3, "round3_given_FX_CMA")):
    for c, v in sw[key].items():
        f = float(allc[(allc["round"] == r_) & (allc.candidate == c)]["score_median_dBIC"].iloc[0])
        mx = max(mx, abs(f - v))
sw["max_abs_diff_vs_file"] = mx
res["stepwise"] = sw

# ---------- O: ทอง / REIT ----------
flo = pd.read_csv(RUN / "fund_level_O.csv")
GOLD = [u for u in EVAL_O if gu.loc[u, "o_group"] == "ทอง"]
REIT = [u for u in EVAL_O if gu.loc[u, "o_group"] == "REIT"]
OXg = pd.DataFrame({"GOLD_XS": Feo["GLD_USD"] - F["SHV_USD"], "FX": FX})
reit_e, brt = resid_on(Fext["REET_USD"] - F["SHV_USD"], X0, tr)
OXr = pd.DataFrame({"MKT": MKT, "REIT_e": reit_e, "FX": FX, "TERM": F["IEF_USD"] - F["SHV_USD"]})
A1c = A1[[f"1c__PC{i}" for i in range(1, 5)]].reindex(idx)


def ofit(units, Xdf):
    return {u: fit(R[u].to_numpy(float), dimson(Xdf), tr, te) for u in units}


og = {}
for grp, units, OX in (("ทอง", GOLD, OXg), ("REIT", REIT, OXr)):
    a = ofit(units, OX)
    comps = {"1a": ofit(units, A1a), "1c": ofit(units, A1c), "3a": ofit(units, F3A)}
    meds = {k: float(np.median([v[u]["r2o"] for u in units])) for k, v in comps.items()}
    best = max(meds, key=meds.get)
    d = [a[u]["r2o"] - comps[best][u]["r2o"] for u in units]
    d3 = [a[u]["r2o"] - comps["3a"][u]["r2o"] for u in units]
    db3 = [a[u]["bic"] - comps["3a"][u]["bic"] for u in units]
    og[grp] = dict(n=len(units), OX_med_r2oos=float(np.median([a[u]["r2o"] for u in units])), comp_meds=meds, best=best,
                   med_paired_d_vs_best=float(np.median(d)), frac_pos=float(np.mean(np.array(d) > 0)),
                   med_d_vs_3a=float(np.median(d3)), med_dbic_vs_3a=float(np.median(db3)),
                   per_fund_OX_r2oos={u: float(a[u]["r2o"]) for u in units},
                   per_fund_beta_sum={u: [float(x) for x in (a[u]["b"][1:1 + OX.shape[1]] + a[u]["b"][1 + OX.shape[1]:])] for u in units})
    fo = flo[(flo["row"] == "O-X")].set_index("unit") if "row" in flo.columns else None
    if fo is not None:
        og[grp]["max_abs_diff_r2oos_vs_file"] = float(max(abs(a[u]["r2o"] - fo.loc[u, "r2_oos"]) for u in units))
res["O"] = og

# ---------- กองทอง: lag 2 (ตรวจว่า Dimson lag 1 พอไหม · diagnostic ของ reviewer) ----------
def dimson2(Fdf):
    A = Fdf.to_numpy(float)
    L1 = np.full_like(A, np.nan); L1[1:] = A[:-1]
    L2 = np.full_like(A, np.nan); L2[2:] = A[:-2]
    Ld = np.full_like(A, np.nan); Ld[:-1] = A[1:]
    return np.hstack([A, L1, L2]), np.hstack([Ld, A, L1])


lag2 = {}
for u in GOLD + REIT:
    OX = OXg if u in GOLD else OXr
    d2, dl = dimson2(OX)
    y = R[u].to_numpy(float)
    base = fit(y, dimson(OX), tr, te)
    r2l2 = fit(y, d2, tr, te)
    r2ld = fit(y, dl, tr, te)
    lag2[u] = dict(r2oos_lag01=float(base["r2o"]), r2oos_lag012=float(r2l2["r2o"]), r2oos_lead_lag01=float(r2ld["r2o"]),
                   adj_lag01=float(base["adj"]), adj_lag012=float(r2l2["adj"]))
res["O_lag2_diag"] = lag2

# ---------- Shapley (exact) ของ ABAGS ใน E-X1 และ E-X2 ----------
def shapley(y, blocks):
    names = list(blocks)
    Dm = {k: dimson(v.to_frame() if isinstance(v, pd.Series) else v) for k, v in blocks.items()}
    allD = np.hstack([Dm[k] for k in names])
    ok = tr & np.isfinite(y) & np.isfinite(allD).all(1)

    def v(S):
        if not S:
            return 0.0
        X = np.column_stack([np.ones(ok.sum())] + [Dm[k][ok] for k in S])
        b = np.linalg.lstsq(X, y[ok], rcond=None)[0]
        e = y[ok] - X @ b
        return 1 - (e @ e) / ((y[ok] - y[ok].mean()) ** 2).sum()
    K = len(names)
    phi = {}
    from math import factorial
    for k in names:
        others = [x for x in names if x != k]
        s = 0.0
        for r_ in range(K):
            for S in itertools.combinations(others, r_):
                wgt = factorial(len(S)) * factorial(K - len(S) - 1) / factorial(K)
                s += wgt * (v(list(S) + [k]) - v(list(S)))
        phi[k] = s
    return phi, v(names)


sh = pd.read_csv(RUN / "shapley_E.csv")
shp = {}
for u in ("ABAGS", "ABAPAC"):
    y = R[u].to_numpy(float)
    phi1, full1 = shapley(y, {"MKT": MKT, "FX": FX, "CMA": CMA})
    k = gf[u]
    phi2, full2 = shapley(y, {"MKT": MKT, "FX": FX, "CMA": CMA, EG[k].name: EG[k]})
    f1 = sh[(sh.unit == u) & (sh.row == "E-X1")].set_index("factor")["phi"]
    f2 = sh[(sh.unit == u) & (sh.row == "E-X2")].set_index("factor")
    nm2 = {"e_CHINA(grp)": "e_CHINAg"}.get(k, k)
    shp[u] = dict(EX1_mine=phi1, EX1_sum=full1, EX1_file=f1.to_dict(),
                  EX1_maxdiff=float(max(abs(phi1[x] - f1[x]) for x in phi1)),
                  EX2_mine={("e_g:" + nm2 if x == k else x): v for x, v in phi2.items()},
                  EX2_file=f2["phi"].to_dict())
res["shapley"] = shp

json.dump(res, open(OUT, "w"), indent=1, ensure_ascii=False, default=lambda o: float(o) if isinstance(o, (np.floating,)) else str(o))
print(json.dumps({k: v for k, v in res.items() if k not in ("O_lag2_diag", "shapley", "O")}, indent=1, ensure_ascii=False, default=str))
print(json.dumps({k: {kk: vv for kk, vv in v.items() if not kk.startswith("per_fund")} for k, v in res["O"].items()}, indent=1, ensure_ascii=False))
