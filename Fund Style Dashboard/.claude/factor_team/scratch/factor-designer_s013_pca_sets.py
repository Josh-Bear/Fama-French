"""factor-designer · S013 · รายชื่อชุด PCA ของ E ระดับหน่วย (notna เท่านั้น · ไม่อ่านค่าผลตอบแทน)
n_weeks ของหน่วย = จำนวนแถวที่มีผลตอบแทนในช่วงหลัก 2021-01-08 → 2025-12-26 ของอนุกรมต่อ (สัปดาห์ซ้อนนับครั้งเดียว)
คู่ซ้ำใน dup_pairs.csv แปลงรหัสเป็นหน่วยก่อน dedup_keep · เขียน specs/S013_pca_sets.csv"""
import sys, json, hashlib
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))
import samples
g = pd.read_csv(ROOT / "specs" / "S012_group_map.csv")
g["unit"] = np.where(g.splice_id.fillna("") != "", g.splice_id, g.FundCode)
P = pd.read_parquet(ROOT / "data" / "panel_weekly.parquet", columns=["FundCode", "date", "ret"])
P = P[P.FundCode.isin(set(g.FundCode))]
NN = P.assign(v=P.ret.notna()).pivot(index="date", columns="FundCode", values="v").fillna(False).astype(bool)
del P
idx = NN.index
main = (idx >= pd.Timestamp("2021-01-08")) & (idx <= pd.Timestamp("2025-12-26"))
tr = (idx >= pd.Timestamp("2021-01-08")) & (idx <= pd.Timestamp("2023-12-29"))
trd = tr.copy(); trd[0] = False   # Dimson: แถวแรกไม่มี lag
te = (idx >= pd.Timestamp("2024-01-05")) & (idx <= pd.Timestamp("2025-12-26"))
h1 = (idx >= pd.Timestamp("2021-01-08")) & (idx <= pd.Timestamp("2023-06-30")); h1[0] = False
h2 = (idx >= pd.Timestamp("2023-07-07")) & (idx <= pd.Timestamp("2025-12-26"))
spl = g[g.splice_id.fillna("") != ""].groupby("splice_id").FundCode.apply(list).to_dict()
Uu = NN.copy()
for sid, cs in spl.items():
    Uu[sid] = NN[cs].any(axis=1)
    Uu = Uu.drop(columns=cs)
pol = g.drop_duplicates("unit").set_index("unit").policy
dup = pd.read_csv(ROOT / "data" / "dup_pairs.csv")
m = {c: sid for sid, cs in spl.items() for c in cs}
dupu = pd.DataFrame({"a": dup.a.map(lambda z: m.get(z, z)), "b": dup.b.map(lambda z: m.get(z, z))})
rows = []
for p in ("E", "O"):
    units = [u for u in Uu.columns if pol.get(u) == p]
    nw = Uu.loc[main, units].sum()
    d = dupu[dupu.a.isin(units) & dupu.b.isin(units)]
    keep = samples.dedup_keep(d, nw)
    raw = Uu.loc[tr, units].sum()
    ntr, nte = Uu.loc[trd, units].sum(), Uu.loc[te, units].sum()
    n1, n2 = Uu.loc[h1, units].sum(), Uu.loc[h2, units].sum()
    for u in sorted(units):
        ev = bool(ntr[u] >= 104 and nte[u] >= 52)
        rows.append(dict(unit=u, policy=p, n_weeks_main=int(nw[u]), n_train_raw=int(raw[u]), n_train_dimson=int(ntr[u]), n_test=int(nte[u]),
                         sel=bool(ntr[u] >= 104), eval=ev, eval52=bool(ntr[u] >= 52 and nte[u] >= 52),
                         stab=bool(ev and n1[u] >= 104 and n2[u] >= 104), dedup_keep=u in keep,
                         pca_balanced=bool(u in keep and raw[u] == int(tr.sum())), pca_unbal52=bool(u in keep and raw[u] >= 52)))
out = pd.DataFrame(rows)
fp = ROOT / "specs" / "S013_pca_sets.csv"
out.to_csv(fp, index=False)
print(out.groupby("policy")[["sel", "eval", "eval52", "stab", "dedup_keep", "pca_balanced", "pca_unbal52"]].sum().to_dict())
print("dropped E", sorted(out[(out.policy == "E") & ~out.dedup_keep].unit))
print("sha", hashlib.sha256(fp.read_bytes()).hexdigest())
