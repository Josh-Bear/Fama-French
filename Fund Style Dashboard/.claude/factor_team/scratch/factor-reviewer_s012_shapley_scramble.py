"""factor-reviewer · รีวิวผล S012 (ส่วน 2)
(A) Shapley: เทียบ shapley_E.csv กับ Shapley ที่คำนวณเอง 2 แบบ — lag 0 อย่างเดียว / คู่ Dimson (lag 0 + lag 1) เป็นผู้เล่นเดียว (ตาม S012 ข้อ 6.4)
(B) future-scramble บนข้อมูลจริง: สุ่มแทนผลตอบแทนกองและ factor ทุกแถว ≥ 2024-01-05 แล้วรันขั้นคัดเลือก (sel_reps · placebo · stepwise · group coef · E-PCA · hybrid · REIT_e)
    ด้วยฟังก์ชันของ lib → ต้องเท่าเดิมทุกบิต
อ่านอย่างเดียว · เขียนเฉพาะ scratch/factor-reviewer_s012_shapley_scramble.json
"""
import hashlib
import itertools
import json
import sys
from math import factorial
from pathlib import Path

import numpy as np
import pandas as pd

T = Path(".claude/factor_team")
sys.path.insert(0, str(T / "lib"))
import io_l1  # noqa: E402
import l1eo  # noqa: E402
from samples import window_mask  # noqa: E402

RUN = T / "runs" / "S012"
OUT = T / "scratch" / "factor-reviewer_s012_shapley_scramble.json"
res = {}

# ---------- โหลดแบบ run.py (ใช้ loader ของ lib) ----------
g = l1eo.load_group_map()
CODES = list(g["FundCode"])
gu = g.drop_duplicates("unit").set_index("unit").sort_index()
F = io_l1.load_factors("W")
Feo, Fext = l1eo.load_eo("W"), l1eo.load_ext("W")
Rc = io_l1.load_returns("W")[CODES]
R, SPL = l1eo.splice_units(Rc)
idx = R.index
mtr = window_mask(idx, "train")
mte = window_mask(idx, "test")
pos1 = np.arange(len(idx)) >= 1
sets = pd.read_csv(RUN / "sets.csv").set_index("unit")
EVAL_E = sorted(sets.index[(sets.policy == "E") & sets["eval"]])

# ---------- (A) Shapley ----------
MKT = (F["MSCI_ACWI"] - F["RF_BOT"]).rename("MKT")
FX = (F["SHV_THB"] - F["RF_BOT"]).rename("FX")
CMA = Feo["KF_DEV_CMA"].rename("CMA")
X1 = pd.concat([MKT, FX, CMA], axis=1)
E_G, PF, PFN, GCOEF, _ = l1eo.group_factors(gu[gu.policy == "E"].reset_index()[["unit", "group_factor"]], F, Fext, X1, mtr)


def lagpair(s):
    a = np.asarray(s, float)
    l = np.full_like(a, np.nan)
    l[1:] = a[:-1]
    return np.column_stack([a, l])


def shap(y, blocks, rows):
    Xall = np.hstack(blocks)
    ok = rows & np.isfinite(y) & np.isfinite(Xall).all(1)
    K = len(blocks)

    def v(S):
        if not S:
            return 0.0
        X = np.column_stack([np.ones(ok.sum())] + [blocks[k][ok] for k in S])
        b = np.linalg.lstsq(X, y[ok], rcond=None)[0]
        e = y[ok] - X @ b
        return 1 - (e @ e) / ((y[ok] - y[ok].mean()) ** 2).sum()
    vv = {}
    for r_ in range(K + 1):
        for S in itertools.combinations(range(K), r_):
            vv[S] = v(list(S))
    phi = np.zeros(K)
    for k in range(K):
        for S, val in vv.items():
            if k in S:
                continue
            S2 = tuple(sorted(S + (k,)))
            phi[k] += factorial(len(S)) * factorial(K - len(S) - 1) / factorial(K) * (vv[S2] - val)
    return phi, vv[tuple(range(K))]


sh = pd.read_csv(RUN / "shapley_E.csv")
rows_tr = mtr & pos1
out = []
for u in EVAL_E:
    y = R[u].to_numpy(float)
    names = ["MKT", "FX", "CMA"] + ([PFN[u]] if u in PF else [])
    ser = [MKT, FX, CMA] + ([PF[u]] if u in PF else [])
    p0, r0 = shap(y, [np.asarray(s, float).reshape(-1, 1) for s in ser], rows_tr)
    pD, rD = shap(y, [lagpair(s) for s in ser], rows_tr)
    for k, nm in enumerate(names):
        out.append(dict(unit=u, factor=nm, phi_lag0=p0[k], r2_lag0=r0, share_lag0=p0[k] / r0, phi_dimson=pD[k], r2_dimson=rD, share_dimson=pD[k] / rD))
mine = pd.DataFrame(out)
f2 = sh[sh.row == "E-X2"][["unit", "factor", "phi", "share"]]
m = mine.merge(f2, on=["unit", "factor"], how="left")
res["shapley_EX2_max_abs_diff_file_vs_lag0"] = float((m["phi"] - m["phi_lag0"]).abs().max())
res["shapley_EX2_max_abs_diff_file_vs_dimson"] = float((m["phi"] - m["phi_dimson"]).abs().max())
summ = {}
for nm, d in m.groupby("factor"):
    summ[nm] = dict(n=int(len(d)), share_med_file=float(d["share"].median()), share_med_lag0=float(d["share_lag0"].median()),
                    share_med_dimson=float(d["share_dimson"].median()), max_abs_share_diff=float((d["share"] - d["share_dimson"]).abs().max()))
res["shapley_EX2_share_medians"] = summ
# E-X1 (3 ผู้เล่น)
out1 = []
for u in EVAL_E:
    y = R[u].to_numpy(float)
    p0, r0 = shap(y, [np.asarray(s, float).reshape(-1, 1) for s in (MKT, FX, CMA)], rows_tr)
    pD, rD = shap(y, [lagpair(s) for s in (MKT, FX, CMA)], rows_tr)
    for k, nm in enumerate(("MKT", "FX", "CMA")):
        out1.append(dict(unit=u, factor=nm, phi_lag0=p0[k], share_lag0=p0[k] / r0, phi_dimson=pD[k], share_dimson=pD[k] / rD))
m1 = pd.DataFrame(out1).merge(sh[sh.row == "E-X1"][["unit", "factor", "phi", "share"]], on=["unit", "factor"])
res["shapley_EX1_max_abs_diff_file_vs_lag0"] = float((m1["phi"] - m1["phi_lag0"]).abs().max())
res["shapley_EX1_share_medians"] = {nm: dict(file=float(d["share"].median()), lag0=float(d["share_lag0"].median()), dimson=float(d["share_dimson"].median()))
                                    for nm, d in m1.groupby("factor")}

# ---------- (B) future-scramble บนข้อมูลจริง ----------
def selection(R_, F_, Feo_, Fext_):
    sets_ = pd.read_csv(RUN / "sets.csv")
    SEL_E = sorted(sets_.loc[(sets_.policy == "E") & sets_["sel"], "unit"])
    BAL = sorted(sets_.loc[(sets_.policy == "E") & sets_["pca_balanced"], "unit"])
    UNB = sorted(sets_.loc[(sets_.policy == "E") & sets_["pca_unbal52"], "unit"])
    ptr = mtr & (idx <= pd.Timestamp("2022-06-24"))
    pte = mtr & (idx >= pd.Timestamp("2022-07-01"))
    reps, cl = l1eo.sel_reps(R_, SEL_E, mtr)
    core, pool, ecoef = l1eo.pool_E(F_, Fext_, Feo_, mtr)
    pl = l1eo.placebo_eo(R_, core, pool, mtr, list(reps["rep"]), pseudo=(ptr, pte))
    sel, lg, ac = l1eo.stepwise_eo(R_, core, pool, mtr, list(reps["rep"]), tau=pl["tau"], pseudo=(ptr, pte), resid_spec=l1eo.resid_spec_E(F_))
    X1_ = pd.concat([core, pool[sel]], axis=1)
    Eg, _, _, gco, _ = l1eo.group_factors(gu[gu.policy == "E"].reset_index()[["unit", "group_factor"]], F_, Fext_, X1_, mtr)
    ep = l1eo.epca_build(R_, BAL, UNB, mtr, n_perm=50, seed=20261015)
    hy = l1eo.hybrid_eo(R_, X1_, mtr, BAL)
    of = l1eo.o_factors(F_, Fext_, Feo_, mtr)
    h = lambda a: hashlib.sha256(np.ascontiguousarray(np.asarray(a, float)).tobytes()).hexdigest()
    return dict(reps=h(reps["rep"].map(hash)), reps_list=list(reps["rep"]), placebo=json.dumps(pl["shifts"], sort_keys=True), tau=pl["tau"], selected=sel,
                steplog=lg.to_csv(index=False), allc=ac.to_csv(index=False), ecoef=ecoef.to_csv(index=False), gcoef=gco.to_csv(index=False),
                kstar=ep["kstar"], ks=json.dumps(ep["ks"], sort_keys=True, default=str), Lam_a=h(ep["Lam_a"]), sd_a=h(ep["sd_a"]), Lam_c=h(ep["Lam_c"]),
                a1_train=h(ep["a1"].loc[mtr].to_numpy()), k_res=hy["k_res"], W=h(hy["W"]), s=h(hy["s"]), coef=h(np.asarray(hy["coef"])),
                reit_coef=of["reit_coef"].to_csv(index=False))


base = selection(R, F, Feo, Fext)
rng = np.random.default_rng(777)
late = idx >= pd.Timestamp("2024-01-05")


def scr(df):
    d = df.copy()
    num = d.select_dtypes("number").columns
    v = d.loc[late, num].to_numpy(float)
    noise = rng.normal(0, 0.05, size=v.shape)
    d.loc[late, num] = np.where(np.isfinite(v), noise, np.nan)  # คงรูปแบบ NaN (ชุดกองไม่เปลี่ยนตามนิยาม)
    return d


Rs = scr(R)
Fs = scr(F)
Feos = scr(Feo)
Fexts = scr(Fext)
assert not np.allclose(Rs.loc[late].fillna(0).to_numpy(), R.loc[late].fillna(0).to_numpy())
sc_ = selection(Rs, Fs, Feos, Fexts)
res["scramble_equal"] = {k: (base[k] == sc_[k]) for k in base}
res["scramble_all_equal"] = all(res["scramble_equal"].values())
res["selected_base"] = base["selected"]
res["kstar_base"] = base["kstar"]
res["k_res_base"] = base["k_res"]
json.dump(res, open(OUT, "w"), indent=1, ensure_ascii=False, default=str)
print(json.dumps(res, indent=1, ensure_ascii=False, default=str))
