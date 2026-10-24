"""factor-reviewer · S012 · นับชุดกองระดับ "หน่วย" (หลังต่อรหัส) จากโครงข้อมูลเท่านั้น (notna) · ไม่อ่านค่าผลตอบแทน · ไม่ fit"""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[1]
D = ROOT / "data"
sys.path.insert(0, str(ROOT.parents[1]))
from importlib import util
spec = util.spec_from_file_location("samples", ROOT / "lib" / "samples.py")
samples = util.module_from_spec(spec); spec.loader.exec_module(samples)

A = pd.read_parquet(D / "aum_fam.parquet"); U = A[A.in_U].set_index("FundCode")
uni = pd.read_csv(D / "universe.csv").set_index("FundCode")
dup = pd.read_csv(D / "dup_pairs.csv")
P = pd.read_parquet(D / "panel_weekly.parquet", columns=["FundCode", "date", "ret"])
P = P[P.FundCode.isin(U.index)]
NN = P.assign(v=P["ret"].notna()).pivot(index="date", columns="FundCode", values="v").fillna(False).astype(bool)
del P
idx = NN.index
def wm(s, e): return (idx >= pd.Timestamp(s)) & (idx <= pd.Timestamp(e))
m_tr_raw = wm("2021-01-08", "2023-12-29"); m_tr = m_tr_raw.copy(); m_tr[0] = False
m_te = wm("2024-01-05", "2025-12-26")
m_h1 = wm("2021-01-08", "2023-06-30").copy(); m_h1[0] = False
m_h2 = wm("2023-07-07", "2025-12-26")
m_main = wm("2021-01-08", "2025-12-26")
m_ptr = wm("2021-01-08", "2022-06-24").copy(); m_ptr[0] = False
m_pte = wm("2022-07-01", "2023-12-29")
SPL = {"I-GOLD": ("I-GOLD", "IGOLD-G", "I-GOLD*"), "TMBGINFRA": ("TMBGINFRA", "ES-GINFRA-A", "ES-GINFRA*"),
       "TMB-ES-GCG": ("TMB-ES-GCG", "ES-GCG-A", "ES-GCG*"), "TMB-ES-GINNO": ("TMB-ES-GINNO", "ES-GINNO-A", "ES-GINNO*")}
c2u = {c: c for c in U.index}
UN = {}
for old, new, sid in SPL.values():
    c2u[old] = sid; c2u[new] = sid
    last_old = idx[NN[old]].max()
    UN[sid] = NN[old] | (NN[new] & (idx > last_old))
for c in U.index:
    if c2u[c] == c:
        UN[c] = NN[c]
UN = pd.DataFrame(UN)
pol = {c2u[c]: U.policy[c] for c in U.index}
units = sorted(UN.columns)
cnt = pd.DataFrame({"n_tr": UN[m_tr].sum(), "n_te": UN[m_te].sum(), "n_h1": UN[m_h1].sum(), "n_h2": UN[m_h2].sum(),
                    "n_tr_raw": UN[m_tr_raw].sum(), "n_main": UN[m_main].sum(), "n_ptr": UN[m_ptr].sum(), "n_pte": UN[m_pte].sum()})
cnt["policy"] = [pol[u] for u in cnt.index]
cnt["SEL"] = cnt.n_tr >= 104
cnt["EVAL"] = cnt.SEL & (cnt.n_te >= 52)
cnt["EVAL52"] = (cnt.n_tr >= 52) & (cnt.n_te >= 52)
cnt["STAB"] = cnt.EVAL & (cnt.n_h1 >= 104) & (cnt.n_h2 >= 104)
cnt["bal"] = cnt.n_tr_raw == int(m_tr_raw.sum())
cnt["unb"] = cnt.n_tr_raw >= 52
# n_weeks ต่อหน่วย: แบบ universe (นับทั้ง panel) — ใช้ 2 แบบ: (i) ผลรวม n_weeks ของ universe สำหรับหน่วยต่อ (ii) นับ notna ทั้ง panel
nw_code = uni["n_weeks"]
nw_unit = {}
for u in units:
    if u in SPL.get(u, ()):  # never
        pass
for c in U.index:
    u = c2u[c]
    if u == c:
        nw_unit[u] = int(nw_code.get(c, UN[u].sum()))
for old, new, sid in SPL.values():
    nw_unit[sid] = int(UN[sid].sum())
nw_unit = pd.Series(nw_unit)
# ตรวจ: n_weeks ของ universe = notna ทั้ง panel ไหม
chk = {c: (int(nw_code.get(c, -1)), int(NN[c].sum())) for c in U.index}
mismatch_nw = {c: v for c, v in chk.items() if v[0] != v[1]}
dupU = dup.copy(); dupU["a"] = dupU.a.map(lambda x: c2u.get(x, x)); dupU["b"] = dupU.b.map(lambda x: c2u.get(x, x))
out = {}
for p in ("E", "O"):
    us = [u for u in units if pol[u] == p]
    sub = cnt.loc[us]
    keep = samples.dedup_keep(dupU[dupU.a.isin(us) & dupU.b.isin(us)], nw_unit.loc[us])
    keep_code = samples.dedup_keep(dup[dup.a.isin(U.index[U.policy == p]) & dup.b.isin(U.index[U.policy == p])], nw_code.loc[[c for c in U.index[U.policy == p]]])
    out[p] = dict(units=len(us), SEL=int(sub.SEL.sum()), EVAL=int(sub.EVAL.sum()), EVAL52=int(sub.EVAL52.sum()), STAB=int(sub.STAB.sum()),
                  dedup_keep=len(keep), dropped=sorted(set(us) - set(keep)),
                  pca_bal=int(sub.loc[keep].bal.sum()), pca_unb=int(sub.loc[keep].unb.sum()),
                  pca_bal_list_spliced=[u for u in keep if u.endswith("*") and cnt.bal[u]],
                  no_train=int((sub.n_tr == 0).sum()), no_test=int((sub.n_te == 0).sum()),
                  SEL_pseudo_ok=int((sub.SEL & (sub.n_ptr >= 52) & (sub.n_pte >= 26)).sum()),
                  SEL_pseudo_fail=sorted(sub.index[sub.SEL & ~((sub.n_ptr >= 52) & (sub.n_pte >= 26))]))
out["nw_mismatch_universe_vs_panel"] = mismatch_nw
out["spliced"] = {sid: cnt.loc[sid, ["n_tr", "n_te", "n_h1", "n_h2", "n_tr_raw"]].astype(int).to_dict() for _, _, sid in SPL.values()}
out["dup_with_spliced"] = dupU[dupU.a.str.endswith("*") | dupU.b.str.endswith("*")][["a", "b", "corr"]].values.tolist()
out["nw_spliced"] = {sid: int(nw_unit[sid]) for _, _, sid in SPL.values()}
out["nw_KKP_GINFRAEQ"] = int(nw_unit.get("KKP GINFRAEQ-H", -1))
# รายการต่อชุด (ใช้เทียบกับ CSV)
cnt.to_csv(ROOT / "scratch" / "factor-reviewer_s012_units_counts.csv")
(ROOT / "scratch" / "factor-reviewer_s012_units.json").write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str))
print(json.dumps(out, ensure_ascii=False, indent=1, default=str))
