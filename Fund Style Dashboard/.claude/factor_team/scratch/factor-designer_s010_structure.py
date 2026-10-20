"""S010 (ระยะ 2) — ตรวจโครงข้อมูลเท่านั้น (designer) · ไม่อ่านค่าผลตอบแทน (ใช้เฉพาะ notna) · ไม่ fit model · ไม่คำนวณ IC
นับ: วันตัดสินใจรายไตรมาส/รายเดือน · สัปดาห์ต่อไตรมาสเป้าหมาย · จำนวนกองที่เข้าเกณฑ์ ณ t · balanced ณ t (ขนาด PCA) ·
กองทอง / class ปันผล · AUM ณ t · TER (กติกา BRIEF 80/92) · สัดส่วน cluster (จากไฟล์ S005 เดิม) + เลขคณิต power / BH / BY
"""
import hashlib, json, sys
from pathlib import Path
import numpy as np, pandas as pd
from scipy import stats, optimize

ROOT = Path(__file__).resolve().parents[3]; T = ROOT / ".claude" / "factor_team"
sys.path.insert(0, str(T / "lib"))
import l4  # noqa: E402  (ter_table เท่านั้น)
import samples as sm  # noqa: E402

sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
o = {"sha256": {k: sha(T / k) for k in ["research/F-R005_predictive_phase2.md", "BRIEF.md", "data/manifest.json",
                                         "data/manifest_ext.json"]}}
o["sha256"]["base_data/SecFundFee.csv"] = sha(ROOT / "base_data/SecFundFee.csv")
o["lib_sha256"] = {p.name: sha(p) for p in sorted((T / "lib").glob("*.py"))}

U = pd.read_csv(T / "data/universe.csv")
P = pd.read_parquet(T / "data/panel_weekly.parquet", columns=["date", "FundCode", "ret"])
M = P.assign(ok=P["ret"].notna()).pivot(index="date", columns="FundCode", values="ok").fillna(False).astype(bool)
del P  # ไม่เก็บค่าผลตอบแทน
M = M.loc["2021-01-08":"2025-12-26"]
idx = M.index
pol = U.set_index("FundCode")["policy"]; div = U.set_index("FundCode")["div_flag"]
GOLD = ["BGOLD", "K-GOLD-A(A)", "KT-GOLD", "SCBGOLDHP", "TGOLD", "UOBSG-N"]
o["panel"] = {"n_funds": int(M.shape[1]), "n_weeks_main": int(len(idx)), "first": str(idx[0].date()), "last": str(idx[-1].date()),
              "gold_in_panel": [g for g in GOLD if g in M.columns],
              "div_Y_in_panel": int(sum(div.get(c, "N") == "Y" for c in M.columns)),
              "policy": {k: int(v) for k, v in pol.reindex(M.columns).value_counts().items()}}

# วันตัดสินใจ = แถว weekly สุดท้าย ≤ สิ้นไตรมาส (มี.ค./มิ.ย./ก.ย./ธ.ค.)
qe = pd.date_range("2022-03-31", "2025-12-31", freq="QE-DEC")
dec = [idx[idx <= q][-1] for q in qe]
o["decision_dates_Q"] = [str(d.date()) for d in dec[:-1]]
o["target_end_last"] = str(dec[-1].date())
o["weeks_per_target_Q"] = [int(((idx > a) & (idx <= b)).sum()) for a, b in zip(dec[:-1], dec[1:])]
me = pd.date_range("2022-03-31", "2025-12-31", freq="ME")
decm = [idx[idx <= q][-1] for q in me]
o["n_decision_M"] = len(decm) - 1
o["weeks_per_target_M"] = sorted(set(int(((idx > a) & (idx <= b)).sum()) for a, b in zip(decm[:-1], decm[1:])))

dup = pd.read_csv(T / "data/dup_pairs.csv")
KEEP = set(sm.dedup_keep(dup, U.set_index("FundCode")["n_weeks"].reindex(M.columns).fillna(0)))
cl = pd.read_csv(T / "runs/S005/fund_clusters.csv")
fee = pd.read_csv(ROOT / "base_data/SecFundFee.csv", dtype=str, encoding="utf-8-sig")
A = pd.read_parquet(T / "data/aum_weekly.parquet", columns=["date", "FundCode", "aum"])
Aok = A.assign(ok=A["aum"].notna()).pivot(index="date", columns="FundCode", values="ok").fillna(False).astype(bool)
del A
o["aum_funds"] = int(Aok.shape[1])

rows, allU = [], set()
pos = np.arange(len(idx))
for a, b in zip(dec[:-1], dec[1:]):
    le = idx <= a
    dim = M.loc[le & (pos >= 1)].sum(0)             # แถว Dimson ≤ t (แถวแรกไม่มี lag)
    elig = dim[dim >= 52].index
    tgt = M.loc[(idx > a) & (idx <= b)].sum(0)
    nq = int(((idx > a) & (idx <= b)).sum())
    u = [c for c in elig if tgt[c] >= int(np.ceil(nq / 2))]
    u_full = [c for c in elig if tgt[c] == nq]
    tu = [c for c in u if c not in GOLD and div.get(c, "N") != "Y"]
    allU |= set(tu)
    bal = M.loc[le].all(0); bal = bal[bal].index
    aum_t = Aok.loc[Aok.index <= a].iloc[-1] if (Aok.index <= a).any() else None
    n_aum = int(sum(bool(aum_t.get(c, False)) for c in tu)) if aum_t is not None else 0
    gmap = cl.set_index("FundCode")["group_id"]
    n_cl = int(gmap.reindex(tu).dropna().nunique()); n_in_cl = int(gmap.reindex(tu).notna().sum())
    rows.append(dict(t=str(a.date()), T_weeks_le_t=int(le.sum()), elig52=len(elig), target_ok=len(u), target_full=len(u_full),
                     U_target=len(tu), U_E=int(sum(pol[c] == "E" for c in tu)), U_F=int(sum(pol[c] == "F" for c in tu)),
                     U_O=int(sum(pol[c] == "O" for c in tu)), dropped_lt_half=len(elig) - len(u),
                     balanced=len(bal), balanced_dedupL0=int(sum(c in KEEP for c in bal)), U_target_dedupL0=int(sum(c in KEEP for c in tu)),
                     aum_at_t=n_aum, S005_clusters=n_cl, S005_cl_funds=n_in_cl))
Q = pd.DataFrame(rows)
o["per_quarter"] = Q.to_dict("records")
ter = l4.ter_table(fee, sorted(allU))
tsel = ter.set_index("FundCode")
o["ter_union"] = {"n_union": len(allU), **{f"{s}|{v}": int(n) for (s, v), n in ter.groupby(["ter_src", "ter_vintage"]).size().items()},
                  "nan": int(ter["ter"].isna().sum())}
o["cluster_ratio_S005_on_union"] = float(cl.set_index("FundCode")["group_id"].reindex(sorted(allU)).dropna().nunique() /
                                         cl.set_index("FundCode")["group_id"].reindex(sorted(allU)).notna().sum())

# ── เลขคณิต power / BH / BY (ไม่ใช้ข้อมูล) ──
Tq, df = 15, 14
tq = lambda p: float(stats.t.ppf(1 - p / 2, df))
cm = lambda m: sum(1 / i for i in range(1, m + 1))
o["thresholds"] = {f"m{m}": {"BH_rank1_p": 0.1 / m, "BH_rank1_t": tq(0.1 / m), "BY_rank1_p": 0.1 / (m * cm(m)),
                             "BY_rank1_t": tq(0.1 / (m * cm(m))), "BH_all_p(rank=m)": 0.1} for m in (17, 20, 97)}
o["p_two_t3_df14"] = float(2 * stats.t.sf(3, df))


def delta_nct(tc, power=0.8):
    return optimize.brentq(lambda d: stats.nct.sf(tc, df, d) - power, 0.1, 20)


mde = {}
for name, tc in [("t3", 3.0), ("BH_m17_single", tq(0.1 / 17)), ("BH_m97_single", tq(0.1 / 97))]:
    for pw in (0.5, 0.8):
        d_n = tc + stats.norm.ppf(pw); d_t = delta_nct(tc, pw)
        mde[f"{name}_pw{int(pw*100)}"] = {"tc": tc, "mult_normal": d_n / np.sqrt(Tq), "mult_nct": d_t / np.sqrt(Tq)}
o["mde_multiplier_of_sigmaIC"] = mde
o["sigma_floor_by_Neff"] = {str(n): float(1 / np.sqrt(n - 1)) for n in (30, 40, 50, 75, 100, 150)}
out = T / "scratch/factor-designer_s010_structure.json"
json.dump(o, open(out, "w"), ensure_ascii=False, indent=1, default=str)
print(json.dumps({k: o[k] for k in o if k not in ("per_quarter", "lib_sha256", "sha256")}, ensure_ascii=False, indent=1, default=str))
print(Q.to_string())
