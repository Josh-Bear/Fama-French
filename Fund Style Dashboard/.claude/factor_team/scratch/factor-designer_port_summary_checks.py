"""factor-designer · ตัวเลขประกอบ reports/PORT_M052_summary.md
อ่านเฉพาะไฟล์ผลของ runs/S014 · runs/S012/fund_level_E.csv · holdings (น้ำหนัก/วันที่) · ไม่ fit · ไม่อ่าน NAV
ผล: scratch/factor-designer_port_summary_checks.json"""
import json
from pathlib import Path
import numpy as np
import pandas as pd

APP = Path(__file__).resolve().parents[3]
FT = APP / ".claude" / "factor_team"
R = FT / "runs/S014"
out = {}

# ---- holdings: โครงพอร์ต ----
H = pd.read_csv(APP / "base_data/reference/m052_frontier_holdings.csv", comment="#", parse_dates=["t", "e"])
H = H[["t", "FundCode", "kind", "weight", "x_model", "gc_k", "x_gc", "canary_b", "vsl_mult"]]
q = H.groupby("t").agg(x_model=("x_model", "first"), gc_k=("gc_k", "first"), x_gc=("x_gc", "first"), canary_b=("canary_b", "first"),
                       vsl=("vsl_mult", "first"), n_E=("kind", lambda s: int((s == "E").sum())))
q["x_hold"] = H[H.kind == "E"].groupby("t").weight.sum().reindex(q.index).fillna(0)
q["w_gold"] = H[H.kind == "G"].groupby("t").weight.sum().reindex(q.index).fillna(0)
q["gold_fund"] = H[H.kind == "G"].groupby("t").FundCode.first().reindex(q.index)
ts = list(q.index)
prevE, new_cnt = set(), []
for t in ts:
    cur = set(H[(H.t == t) & (H.kind == "E")].FundCode)
    new_cnt.append(len(cur - prevE) if prevE else len(cur))
    prevE = cur
q["new_E"] = new_cnt
# x ถูกกำหนดโดยตัวใด (ตัวที่ binding)
def binder(r):
    tm = r.x_gc * r.vsl
    xc = 1 - r.canary_b / 2
    x = max(0.25, min(tm, xc))
    if abs(x - 0.25) < 1e-9 and min(tm, xc) < 0.25:
        return "floor0.25"
    return "canary" if xc < tm - 1e-12 else ("vsl" if r.vsl < 1 - 1e-12 else "gc")
q["binding"] = q.apply(binder, axis=1)
out["quarters"] = q.reset_index().assign(t=lambda d: d.t.dt.date.astype(str)).round(4).to_dict("records")
out["x_summary"] = dict(mean_x_model=float(q.x_model.mean()), min=float(q.x_model.min()), max=float(q.x_model.max()),
                        n_gold_ge_05=int((q.w_gold >= 0.5 - 1e-9).sum()), n_x1=int((q.x_hold > 1 - 1e-9).sum()),
                        n_codes=int(H.FundCode.nunique()), new_E_after_first=int(sum(new_cnt[1:])), new_E_per_q_mean=float(np.mean(new_cnt[1:])),
                        gold_funds=H[H.kind == "G"].FundCode.value_counts().to_dict(), binding=q.binding.value_counts().to_dict())

# ---- กลุ่มซ้ำ: กองใหม่หรือถือต่อ ----
G = pd.read_csv(FT / "runs/S014/mapping.csv")
grp = dict(zip(G.FundCode, G.group))
pairs = []
prev = set()
for t in ts:
    e = H[(H.t == t) & (H.kind == "E")].FundCode.tolist()
    gg = pd.Series({f: grp.get(f) for f in e})
    for g_, s in gg.groupby(gg):
        if g_ not in (None, "ไม่มี") and len(s) > 1:
            pairs.append(dict(t=str(t.date()), group=g_, funds=list(s.index), new=[f for f in s.index if f not in prev]))
    prev = set(e)
out["same_group_pairs"] = pairs

# ---- exposure ----
X = pd.read_csv(R / "exposure.csv")
X["sleeve_beta_MKT"] = X.B_MKT / X.x_hold
out["sleeve_beta_MKT"] = dict(min=float(X.sleeve_beta_MKT.min()), max=float(X.sleeve_beta_MKT.max()),
                              n_gt1=int((X.sleeve_beta_MKT > 1).sum()), by_t=dict(zip(X.t, X.sleeve_beta_MKT.round(3))))
out["corr_BMKT_x"] = float(np.corrcoef(X.B_MKT, X.x_model)[0, 1])
gcols = [c for c in X.columns if c.startswith("B_e_")]
X["max_B_group"] = X[gcols].abs().max(axis=1)
out["max_B_group"] = dict(zip(X.t, X.max_B_group.round(3)))
out["se_B"] = {c: dict(min=float(X[c].min()), max=float(X[c].max())) for c in ("se_B_MKT", "se_B_FX", "se_B_GOLD_XS", "se_B_CMA")}
out["B_ranges"] = {c: dict(min=float(X[c].min()), max=float(X[c].max())) for c in ("B_MKT", "B_FX", "B_CMA", "B_GOLD_XS")}
gx = X[X.x_hold < 1 - 1e-9]
out["BGOLD_over_1mx"] = dict(min=float((gx.B_GOLD_XS / (1 - gx.x_hold)).min()), max=float((gx.B_GOLD_XS / (1 - gx.x_hold)).max()))

# ---- concentration ----
C = pd.read_csv(R / "concentration.csv").merge(X[["t", "x_hold"]], on="t")
scols = [c for c in C.columns if c.startswith("share_e_")]
C["share_groups"] = C[scols].sum(axis=1)
hi = C[C.x_hold >= 0.75 - 1e-9]
out["concentration"] = dict(share_eps=dict(min=float(C.share_eps.min()), max=float(C.share_eps.max())),
                            share_groups_all=dict(min=float(C.share_groups.min()), max=float(C.share_groups.max())),
                            share_groups_x_ge_075=dict(n=int(len(hi)), min=float(hi.share_groups.min()), max=float(hi.share_groups.max()),
                                                       ts=hi.t.tolist()),
                            share_MKT_x_ge_075=dict(min=float(hi.share_MKT.min()), max=float(hi.share_MKT.max())),
                            top_main=C.top_factor.value_counts().to_dict(),
                            vol=dict(min=float(C.vol_ann_expected.min()), max=float(C.vol_ann_expected.max())),
                            share_groups_by_t=dict(zip(C.t, C.share_groups.round(3))))
CP = pd.read_csv(R / "concentration_PA.csv")
out["top_PA"] = CP.PA_top.value_counts().to_dict()
out["top_main_check"] = CP.main_top.value_counts().to_dict()

# ---- betas: adj R² รายกอง + SE ----
B = pd.read_csv(R / "betas.csv")
out["adj_r2_holdings"] = dict(min=float(B.adj_r2.min()), median=float(B.adj_r2.median()),
                              lt_050=B[B.adj_r2 < 0.5][["t", "FundCode", "adj_r2", "n"]].round(3).to_dict("records"))
sec = [c for c in B.columns if c.startswith("se_beta_e_")]
B["se_group"] = B[sec].min(axis=1, skipna=True)
out["se_beta_2022"] = B[B.t <= "2022-12-30"][["t", "FundCode", "n", "se_beta_MKT", "se_group"]].round(3).to_dict("records")
out["se_beta_MKT_all"] = dict(min=float(B.se_beta_MKT.min()), median=float(B.se_beta_MKT.median()), max=float(B.se_beta_MKT.max()))
dg = B[B.FundCode == "DAOL-GOLD"][["t", "beta_FX", "se_beta_FX", "beta_CMA", "se_beta_CMA", "adj_r2"]].round(3)
out["daol_main"] = dg.to_dict("records")

# ---- attribution summary ----
S = pd.read_csv(R / "attribution_summary.csv")
out["lens_values"] = S.lens.unique().tolist()
out["periods"] = S.period.unique().tolist()
def pick(period, lens):
    d = S[(S.period == period) & (S.lens == lens)]
    return {r.component: round(float(r.value) * (100 if abs(float(r.value)) < 5 else 1), 3) for r in d.itertuples()}
for p in S.period.unique():
    for l in S.lens.unique():
        v = pick(p, l)
        if v:
            out.setdefault("attr", {})[f"{p} | {l}"] = v

# ---- P-C ----
PC = pd.read_csv(R / "appendix_PC.csv")
out["PC_summary"] = PC[PC.kind == "summary"].drop(columns=[c for c in PC.columns if PC[PC.kind == "summary"][c].isna().all()]).round(4).to_dict("records") if "kind" in PC else None

# ---- S012: การกระจาย adj R² ของ E-X2 (train · EVAL) ----
F = pd.read_csv(FT / "runs/S012/fund_level_E.csv")
f2 = F[(F.row == "E-X2") & (F.in_EVAL == True)]
out["S012_EX2_adj_r2_EVAL"] = dict(n=int(len(f2)), p05=float(f2.adj_r2.quantile(0.05)), p10=float(f2.adj_r2.quantile(0.10)),
                                    p25=float(f2.adj_r2.quantile(0.25)), median=float(f2.adj_r2.median()))
fa = F[(F.row == "E-X2")]
out["S012_EX2_adj_r2_all196"] = dict(n=int(len(fa)), p05=float(fa.adj_r2.quantile(0.05)), p10=float(fa.adj_r2.quantile(0.10)),
                                      median=float(fa.adj_r2.median()))
out["S012_EX2_named"] = fa[fa.unit.isin(["DAOL-GOLD", "KT-MINING", "FCSCBSETE", "K-GPROP-A(A)", "KT-PROPERTY-A"])][["unit", "group", "adj_r2", "in_EVAL"]].round(3).to_dict("records")

(FT / "scratch/factor-designer_port_summary_checks.json").write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str))
print(json.dumps(out, ensure_ascii=False, indent=1, default=str)[:20000])
