"""S011 (addendum ของ S010) — ตรวจโครงข้อมูลเท่านั้น · notna ของ ret · ชื่อกองใน FundProfile · as-of ของ TER ·
ไม่คำนวณค่าใดจากผลตอบแทน · ไม่ fit model · ไม่คำนวณ IC · การจำลอง power ใช้ข้อมูลสุ่มล้วน
"""
import hashlib, json, re, sys
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parents[3]; T = ROOT / ".claude" / "factor_team"
sys.path.insert(0, str(T / "lib"))
import l4  # noqa: E402
import samples as sm  # noqa: E402

sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
o = {"sha256": {k: sha(T / k) for k in ["specs/S010_P2_predictive_walkforward.md", "reviews/S010_spec_review.md", "BRIEF.md"]}}
o["sha256"]["base_data/FundProfile.csv"] = sha(ROOT / "base_data/FundProfile.csv")
o["sha256"]["base_data/SecFundFee.csv"] = sha(ROOT / "base_data/SecFundFee.csv")

U = pd.read_csv(T / "data/universe.csv")
P = pd.read_parquet(T / "data/panel_weekly.parquet", columns=["date", "FundCode", "ret"])
M = P.assign(ok=P["ret"].notna()).pivot(index="date", columns="FundCode", values="ok").fillna(False).astype(bool)
del P
M = M.loc["2021-01-08":"2025-12-26"]; idx = M.index; pos = np.arange(len(idx))
codes = list(M.columns)
pol = U.set_index("FundCode")["policy"]; div = U.set_index("FundCode")["div_flag"]

# ── กฎชื่อกองทอง (point-in-time: ชื่อกำหนดตอนจดทะเบียน · FundProfile snapshot) ──
FP = pd.read_csv(ROOT / "base_data/FundProfile.csv", dtype=str, encoding="utf-8-sig")
FP = FP.rename(columns={FP.columns[0]: "Fund Code"}).drop_duplicates("Fund Code").set_index("Fund Code")
en = FP["Fund Name EN"].reindex(codes).fillna(""); th = FP["Fund Name TH"].reindex(codes).fillna("")
r_en = en.str.contains(r"gold", case=False, regex=True)
r_th = th.str.contains("ทองคำ", regex=False)
r_code = pd.Series([("GOLD" in c.upper()) for c in codes], index=codes)
gold = sorted(c for c in codes if r_en[c] or r_th[c])
o["gold_rule"] = {"n_EN_or_TH": len(gold), "n_EN": int(r_en.sum()), "n_TH": int(r_th.sum()), "n_code_GOLD": int(r_code.sum()),
                  "only_code_not_name": sorted(c for c in codes if r_code[c] and c not in gold),
                  "name_not_code": sorted(c for c in gold if not r_code[c]),
                  "en_word_golden": sorted(c for c in codes if re.search(r"golden", en[c], re.I))}
o["gold_list"] = [dict(FundCode=c, policy=pol.get(c), div=div.get(c), en=en[c], th=th[c], en_hit=bool(r_en[c]), th_hit=bool(r_th[c]),
                       first=str(idx[M[c].values][0].date()) if M[c].any() else None,
                       last=str(idx[M[c].values][-1].date()) if M[c].any() else None) for c in gold]
GOLD6 = ["BGOLD", "K-GOLD-A(A)", "KT-GOLD", "SCBGOLDHP", "TGOLD", "UOBSG-N"]
o["gold6_subset"] = all(g in gold for g in GOLD6)

KEEP = set(sm.dedup_keep(pd.read_csv(T / "data/dup_pairs.csv"), U.set_index("FundCode")["n_weeks"].reindex(codes).fillna(0)))
qe = pd.date_range("2022-03-31", "2025-12-31", freq="QE-DEC"); dec = [idx[idx <= q][-1] for q in qe]
rows, union = [], set()
for a, b in zip(dec[:-1], dec[1:]):
    le = idx <= a; ia = int(np.where(idx == a)[0][0])
    dim = M.loc[le & (pos >= 1)].sum(axis=0)
    alive = M.iloc[ia]                                   # (u0) มีผลตอบแทนที่แถว t
    tgt = M.loc[(idx > a) & (idx <= b)].sum(axis=0); nq = int(((idx > a) & (idx <= b)).sum())
    e52 = [c for c in codes if dim[c] >= 52]
    u0 = [c for c in e52 if alive[c]]
    excl_g = [c for c in u0 if c in gold]; excl_d = [c for c in u0 if div.get(c, "N") == "Y" and c not in gold]
    pre = [c for c in u0 if c not in gold and div.get(c, "N") != "Y"]
    pre_d = [c for c in pre if c in KEEP]
    ut = [c for c in pre_d if tgt[c] >= int(np.ceil(nq / 2))]
    union |= set(pre)
    bal = [c for c in codes if M.loc[le, c].all()]
    rows.append(dict(t=str(a.date()), e52=len(e52), dead_at_t=len(e52) - len(u0), U_pre=len(pre), U_pre_dedupL0=len(pre_d),
                     U_t_dedupL0=len(ut), lost_by_future=len(pre_d) - len(ut), gold_excl=len(excl_g), div_excl=len(excl_d),
                     E=sum(pol[c] == "E" for c in pre_d), F=sum(pol[c] == "F" for c in pre_d), O=sum(pol[c] == "O" for c in pre_d),
                     S_t_balanced=len(bal), S_t_dedupL0=sum(c in KEEP for c in bal), gold_in_S_t_dedupL0=sum((c in KEEP) and (c in gold) for c in bal),
                     C3_half_approx=int(np.ceil(len(pre_d) / 2))))
Q = pd.DataFrame(rows); o["per_quarter"] = Q.to_dict("records")

fee = pd.read_csv(ROOT / "base_data/SecFundFee.csv", dtype=str, encoding="utf-8-sig")
ter = l4.ter_table(fee, sorted(union)); act = ter[ter["ter_src"] == "actual"]
o["ter_union"] = {"n_union": len(union), **{f"{s}|{v}": int(n) for (s, v), n in ter.groupby(["ter_src", "ter_vintage"]).size().items()},
                  "actual_asof_max": str(pd.to_datetime(act["ter_asof"]).max().date()),
                  "actual_asof_by_year": {str(k): int(v) for k, v in pd.to_datetime(act["ter_asof"]).dt.year.value_counts().sort_index().items()}}

# ── จำลอง power ภายใต้กฎจริง max(SE_iid, SE_NW L2) · Q 15 · ข้อมูลสุ่มล้วน ──
rng = np.random.default_rng(20261018); Qn, L, R = 15, 2, 40000


def tdec(x):
    m = x.mean(1); d = x - m[:, None]; s = x.std(1, ddof=1); se_i = s / np.sqrt(Qn)
    g0 = (d * d).sum(1) / Qn; om = g0.copy()
    for l in range(1, L + 1):
        om += 2 * (1 - l / (L + 1)) * (d[:, l:] * d[:, :-l]).sum(1) / Qn
    se_n = np.sqrt(np.maximum(om * Qn / (Qn - 1), 0) / Qn)
    return m / np.maximum(se_i, se_n)


def ar1(rho):
    e = rng.standard_normal((R, Qn)); x = np.empty_like(e); x[:, 0] = e[:, 0]
    for j in range(1, Qn):
        x[:, j] = rho * x[:, j - 1] + np.sqrt(1 - rho ** 2) * e[:, j]
    return x


pw = {}
for rho in (0.0, 0.3):
    Z = ar1(rho)
    for tc, nm in ((3.0, "t3"), (3.244, "BH17"), (4.125, "BH97")):
        grid = np.round(np.arange(0.70, 1.80, 0.01), 2)
        p = [float((tdec(Z + c) > tc).mean()) for c in grid]
        c80 = next((float(c) for c, v in zip(grid, p) if v >= 0.80), None)
        c50 = next((float(c) for c, v in zip(grid, p) if v >= 0.50), None)
        pw[f"rho{rho}_{nm}"] = {"mult50": c50, "mult80": c80, "size": float((tdec(Z) > tc).mean())}
o["power_maxrule_sim"] = pw
out = T / "scratch/factor-designer_s011_structure.json"
json.dump(o, open(out, "w"), ensure_ascii=False, indent=1, default=str)
print(json.dumps({k: o[k] for k in o if k not in ("per_quarter",)}, ensure_ascii=False, indent=1, default=str))
print(Q.to_string())
