"""reviewer S009: ตรวจตัวเลขจาก CSV ใน runs/S009 (อ่านอย่างเดียว · ไม่ fit model ผลตอบแทนใหม่ · ไม่เขียนใน runs/)
ใช้: PYTHONPATH=. ./.venv/bin/python .claude/factor_team/scratch/factor-reviewer_s009_check.py"""
import json
import numpy as np, pandas as pd
from scipy import stats

R = ".claude/factor_team/runs/S009/"
OUT = ".claude/factor_team/scratch/factor-reviewer_s009_check.json"
af = pd.read_csv(R + "alpha_fund.csv")
ch = pd.read_csv(R + "chars.csv", index_col=0)
q2 = pd.read_csv(R + "alpha_q2.csv", index_col=0)
cl = pd.read_csv(".claude/factor_team/runs/S005/fund_clusters.csv").set_index("FundCode")["group_id"]
res = {}


def bh(p, q=0.10, by=False):
    p = np.asarray(p, float); m = len(p); o = np.argsort(p)
    c = np.sum(1.0 / np.arange(1, m + 1)) if by else 1.0
    thr = q * np.arange(1, m + 1) / (m * c)
    ok = np.where(p[o] <= thr)[0]
    return 0 if len(ok) == 0 else int(ok.max() + 1)


# 1) BH / BY ซ้ำ + เหตุที่ BY ต่าง
for row in ["M1", "M2", "M3", "M4", "ref_3a"]:
    d = af[(af.row == row) & (af.window == "full") & (af.FundCode != "MGAPVD")].dropna(subset=["t"])
    p = 2 * stats.norm.sf(np.abs(d.t.to_numpy()))
    at = np.sort(np.abs(d.t.to_numpy()))[::-1]
    m = len(p); cm = np.sum(1.0 / np.arange(1, m + 1))
    res[f"bh_{row}"] = dict(n=m, BH=bh(p), BY=bh(p, by=True), BH_csv=int(d.bh.sum()), BY_csv=int(d.by.sum()),
                            top_abs_t=[round(x, 3) for x in at[:20]],
                            n_abs_t_gt_3_23=int((at > 3.23).sum()), n_abs_t_gt_3_94=int((at > 3.94).sum()),
                            BY_t_needed_k1=round(float(stats.norm.isf(0.10 / (m * cm) / 2)), 3),
                            BY_t_needed_k15=round(float(stats.norm.isf(15 * 0.10 / (m * cm) / 2)), 3))

# 2) Q2 + กลุ่มอิสระ + ทอง + ref-③a
v = q2.q2_verdict.value_counts().to_dict(); res["q2_counts"] = v
ev = q2[q2.q2_verdict == "มีหลักฐาน α"].copy()
ev["cluster"] = [cl.get(c, np.nan) for c in ev.index]
r3 = af[(af.row == "ref_3a") & (af.window == "full")].set_index("FundCode")
ev["a_ref3a"] = r3.alpha_pct.reindex(ev.index); ev["t_ref3a"] = r3.t.reindex(ev.index); ev["bh_ref3a"] = r3.bh.reindex(ev.index)
res["q2_evidence"] = ev[["policy", "group", "div", "alpha_full_1", "t_full_1", "alpha_full_2", "t_full_2", "cluster", "a_ref3a", "t_ref3a", "bh_ref3a"]].round(3).reset_index().to_dict("records")
res["q2_evidence_n_clusters"] = int(ev.cluster.nunique())
res["q2_evidence_GO"] = int((ev.group == "G-O").sum()); res["q2_evidence_GO_clusters"] = int(ev[ev.group == "G-O"].cluster.nunique())
res["q2_evidence_pos"] = int((ev.alpha_full_1 > 0).sum())

# 3) X2 ซ้ำ (WLS 1/se² · CR1 · t(G−1)) + OLS + ความไว
def xsec(y, se, X, g, w=True):
    N, K = X.shape; W = 1 / se ** 2 if w else np.ones(N)
    A = np.linalg.inv(X.T @ (X * W[:, None])); b = A @ (X.T @ (W * y)); e = y - X @ b
    G = len(np.unique(g)); meat = np.zeros((K, K))
    for gg in np.unique(g):
        s = (X[g == gg] * (W[g == gg] * e[g == gg])[:, None]).sum(0); meat += np.outer(s, s)
    V = G / (G - 1) * (N - 1) / (N - K) * A @ meat @ A; sd = np.sqrt(np.diag(V)); tc = stats.t.ppf(0.975, G - 1)
    return b, sd, tc, G, (W.sum() ** 2 / (W ** 2).sum())


cols = ["ter", "FXb", "omr", "DIV", "d_v2026", "G_MSCI_ACWI_CD", "G_MSCI_ACWI_IT", "G_MSCI_ASIA_EX_JAPAN", "G_MSCI_CHINA_ALL_SHARES"]
for row in ["M1", "M2"]:
    d = af[(af.row == row) & (af.window == "full")].set_index("FundCode")
    E = ch[(ch.policy == "E") & (ch.index != "FCSCBSETE") & (ch.index != "MGAPVD")].copy()
    E["omr"] = E[f"omr_{row}"]
    E = E.join(d[["alpha_pct", "se_pct"]], how="inner").dropna(subset=cols + ["alpha_pct", "se_pct"])
    X = np.column_stack([np.ones(len(E)), E[cols].to_numpy(float)]); y = E.alpha_pct.to_numpy(); se = E.se_pct.to_numpy()
    g = np.array([cl.get(c, -1) for c in E.index])
    out = {}
    for nm, w in [("wls", True), ("ols", False)]:
        b, sd, tc, G, kish = xsec(y, se, X, g, w)
        out[nm] = dict(N=len(E), G=G, kish=round(kish, 1), ter=round(b[1], 3), ter_ci=[round(b[1] - tc * sd[1], 3), round(b[1] + tc * sd[1], 3)],
                       DIV=round(b[4], 3), DIV_ci=[round(b[4] - tc * sd[4], 3), round(b[4] + tc * sd[4], 3)])
    # ความไว: ตัด 10 กองน้ำหนักสูงสุด / ตัดกอง se ต่ำ (index-like) · LOCO ของ slope TER
    W = 1 / se ** 2; top = np.argsort(W)[::-1][:10]; keep = np.setdiff1d(np.arange(len(E)), top)
    b, sd, tc, G, _ = xsec(y[keep], se[keep], X[keep], g[keep], True)
    out["wls_drop_top10w"] = dict(ter=round(b[1], 3), ter_ci=[round(b[1] - tc * sd[1], 3), round(b[1] + tc * sd[1], 3)],
                                  top10=list(E.index[top]), top10_ter=E.ter.iloc[top].round(2).tolist(), top10_alpha=E.alpha_pct.iloc[top].round(2).tolist())
    loco = []
    for gg in np.unique(g):
        k = g != gg
        bb = np.linalg.lstsq(X[k] * np.sqrt(W[k])[:, None], y[k] * np.sqrt(W[k]), rcond=None)[0]; loco.append(bb[1])
    out["wls_loco_ter_minmax"] = [round(min(loco), 3), round(max(loco), 3)]
    out["ter_desc"] = E.ter.describe().round(3).to_dict(); out["alpha_desc"] = E.alpha_pct.describe().round(3).to_dict()
    out["corr_ter_se"] = round(float(np.corrcoef(E.ter, se)[0, 1]), 3)
    out["ter_by_se_tercile"] = E.assign(q=pd.qcut(se, 3, labels=["lo_se", "mid", "hi_se"])).groupby("q", observed=True).agg(ter=("ter", "median"), alpha=("alpha_pct", "median"), n=("ter", "size")).round(3).to_dict("index")
    res[f"X2_{row}"] = out

# 4) FX gap / ff bootstrap / spot-check
fx = pd.read_csv(R + "fx_gap.csv"); res["fx_median_ratio"] = fx.groupby("base").ratio.median().round(3).to_dict()
for row in ["M1", "M2"]:
    fb = pd.read_csv(R + f"ff_boot_{row}.csv")
    act = {"M1": 16, "M2": 20}[row]
    res[f"ff_{row}"] = dict(B=len(fb), null_mean_nbh=round(fb.n_bh.mean(), 3), null_p95=float(np.percentile(fb.n_bh, 95)),
                            p_boot=round((1 + (fb.n_bh >= act).sum()) / (1 + len(fb)), 4), max_null=int(fb.n_bh.max()))
sc = af[(af.window == "full") & af.FundCode.isin(["ASP-NGF", "K-GOLD-A(A)", "TUSEQ-UH"]) & af.row.isin(["M1", "M2"])]
res["spot"] = sc[["row", "FundCode", "alpha_pct", "t", "bh", "by"]].round(3).to_dict("records")
json.dump(res, open(OUT, "w"), ensure_ascii=False, indent=1, default=str)
print(json.dumps(res, ensure_ascii=False, default=str)[:9000])
