"""factor-reviewer · CI แบบสุ่มกลุ่มกองอิสระ (คำนวณเอง) ของ Q-E1 / Q-E2 ทั้งแบบผลต่างของ median และ median ของผลต่างรายกอง
ใช้ R²_oos รายกองจาก fund_level_E.csv (ยืนยันแล้วว่าตรงกับการ fit ของ reviewer ≤ 4e-14) · กลุ่มอิสระสร้างเอง (corr ≥ 0.95 · train · overlap ≥ 52 · connected components)"""
import json
from pathlib import Path
import numpy as np, pandas as pd
T = Path(".claude/factor_team"); RUN = T / "runs" / "S012"
fl = pd.read_csv(RUN / "fund_level_E.csv")
ev = fl[(fl.row == "E-X2") & fl.in_EVAL]["unit"].tolist()
r = {row: fl[fl.row == row].set_index("unit").loc[ev, "r2_oos"] for row in ("E-X2", "E-PCA-a1", "E-X1", "③a")}
# ผลตอบแทนหน่วย (ต่อรหัสแบบ S013 §2)
F = pd.read_parquet(T / "data" / "factors_weekly.parquet").loc["2021-01-08":"2025-12-26"]
P = pd.read_parquet(T / "data" / "panel_weekly.parquet")
W = P.pivot(index="date", columns="FundCode", values="ret").sort_index().loc["2021-01-08":"2025-12-26"]
g = pd.read_csv(T / "specs" / "S012_group_map.csv"); g["unit"] = g["splice_id"].where(g["splice_id"].notna(), g["FundCode"])
SPL = {"I-GOLD*": ("I-GOLD", "IGOLD-G"), "ES-GCG*": ("TMB-ES-GCG", "ES-GCG-A"), "ES-GINNO*": ("TMB-ES-GINNO", "ES-GINNO-A"), "ES-GINFRA*": ("TMBGINFRA", "ES-GINFRA-A")}
wk = pd.Timestamp("2023-12-08"); idx = W.index
R = {}
for u in ev:
    if u in SPL:
        o, n = SPL[u]; R[u] = W[o].where(idx < wk).combine_first(W[n].where(idx >= wk))
    else:
        R[u] = W[g.loc[g.unit == u, "FundCode"].iloc[0]]
R = pd.DataFrame(R).loc["2021-01-08":"2023-12-29"]
C = R.corr(min_periods=52).fillna(0).to_numpy()
A = C >= 0.95
n = len(ev); lab = -np.ones(n, int); k = 0
for i in range(n):
    if lab[i] >= 0: continue
    st = [i]; lab[i] = k
    while st:
        j = st.pop()
        for m in np.where(A[j] & (lab < 0))[0]:
            lab[m] = k; st.append(m)
    k += 1
out = {"n_clusters": int(k)}
rng = np.random.default_rng(12345)
mem = {c: np.where(lab == c)[0] for c in range(k)}
pairs = {"Q-E1": ("E-X2", "E-PCA-a1"), "Q-E2": ("E-X1", "③a")}
dr = {q: [] for q in pairs}; dp = {q: [] for q in pairs}
for _ in range(2000):
    d = rng.choice(k, size=k, replace=True)
    ii = np.concatenate([mem[c] for c in d])
    for q, (a, b) in pairs.items():
        x, y = r[a].to_numpy()[ii], r[b].to_numpy()[ii]
        dr[q].append(np.median(x) - np.median(y)); dp[q].append(np.median(x - y))
for q, (a, b) in pairs.items():
    out[q] = dict(diff_of_medians=float(r[a].median() - r[b].median()), ci_diff_of_medians=[float(np.percentile(dr[q], 2.5)), float(np.percentile(dr[q], 97.5))],
                  median_paired=float((r[a] - r[b]).median()), ci_median_paired=[float(np.percentile(dp[q], 2.5)), float(np.percentile(dp[q], 97.5))],
                  share_pos=float(((r[a] - r[b]) > 0).mean()))
json.dump(out, open(T / "scratch" / "factor-reviewer_s012_boot.json", "w"), indent=1, ensure_ascii=False)
print(json.dumps(out, indent=1, ensure_ascii=False))
