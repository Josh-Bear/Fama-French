"""factor-reviewer · Shapley share ของ O-X (ทอง / REIT) และ E-PCA-a1: ไฟล์ (lag 0) เทียบคู่ Dimson — อ่านอย่างเดียว"""
import itertools, json, sys
from math import factorial
from pathlib import Path
import numpy as np, pandas as pd
T = Path(".claude/factor_team"); sys.path.insert(0, str(T / "lib"))
import io_l1, l1eo  # noqa
from samples import window_mask
RUN = T / "runs" / "S012"
g = l1eo.load_group_map(); gu = g.drop_duplicates("unit").set_index("unit")
F = io_l1.load_factors("W"); Feo, Fext = l1eo.load_eo("W"), l1eo.load_ext("W")
R, _ = l1eo.splice_units(io_l1.load_returns("W")[list(g["FundCode"])])
idx = R.index; rows = window_mask(idx, "train") & (np.arange(len(idx)) >= 1)
OF = l1eo.o_factors(F, Fext, Feo, window_mask(idx, "train"))
sets = pd.read_csv(RUN / "sets.csv").set_index("unit")
EVO = sorted(sets.index[(sets.policy == "O") & sets["eval"]])
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
    return phi / vv[tuple(range(K))]
out = {}
for grp, df in (("ทอง", OF["gold"]), ("REIT", OF["reit"])):
    us = [u for u in EVO if gu.loc[u, "o_group"] == grp]
    s0 = np.array([shap(R[u].to_numpy(float), [df[c].to_numpy(float).reshape(-1, 1) for c in df.columns]) for u in us])
    sD = np.array([shap(R[u].to_numpy(float), [lp(df[c]) for c in df.columns]) for u in us])
    out[grp] = {c: dict(lag0_med=float(np.median(s0[:, j])), dimson_med=float(np.median(sD[:, j]))) for j, c in enumerate(df.columns)}
fr = pd.read_csv(RUN / "factor_report_O.csv")
out["file_O"] = fr[["row", "factor", "shap_share_med"]].to_dict(orient="records")
json.dump(out, open(T / "scratch" / "factor-reviewer_s012_shapley_o.json", "w"), indent=1, ensure_ascii=False)
print(json.dumps(out, indent=1, ensure_ascii=False))
