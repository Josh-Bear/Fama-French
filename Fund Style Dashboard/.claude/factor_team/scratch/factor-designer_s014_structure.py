"""factor-designer · S014 · โครงข้อมูลของ holding M052 (notna เท่านั้น · ไม่อ่านค่าผลตอบแทน · ไม่ fit)"""
import json, hashlib
from pathlib import Path
import pandas as pd, numpy as np
APP = Path(__file__).resolve().parents[3]
FT = APP / ".claude" / "factor_team"
H = pd.read_csv(APP / "base_data/reference/m052_frontier_holdings.csv", comment="#")
u = pd.read_csv(FT / "data/universe.csv")
inc = u[u.included]; rep = dict(zip(inc.family, inc.FundCode)); fam = dict(zip(u.FundCode, u.family))
MAP = {}
for c, hf in H[["FundCode", "family"]].drop_duplicates().itertuples(index=False):
    if c in set(inc.FundCode):
        MAP[c] = (c, "same")
    else:
        f = fam.get(c) or hf
        MAP[c] = (rep.get(f), "family_rep")
P = pd.read_parquet(FT / "data/panel_weekly.parquet", columns=["FundCode", "date", "ret"])
units = sorted({v[0] for v in MAP.values() if v[0]})
P = P[P.FundCode.isin(units)]
NN = P.assign(v=P.ret.notna()).pivot(index="date", columns="FundCode", values="v").fillna(False).astype(bool)
del P
idx = NN.index
ts = sorted(pd.to_datetime(H.t.unique()))
rows = []
for i, t in enumerate(ts):
    t_next = ts[i + 1] if i + 1 < len(ts) else pd.Timestamp("2025-12-26")
    for _, h in H[pd.to_datetime(H.t) == t].iterrows():
        unit, how = MAP[h.FundCode]
        win = (idx <= t) & (idx > t - pd.Timedelta(weeks=156))
        hold = (idx > t) & (idx <= t_next)
        n_win = int(NN.loc[win, unit].sum()) if unit in NN else 0
        n_all = int(NN.loc[idx <= t, unit].sum()) if unit in NN else 0
        n_hold = int(NN.loc[hold, unit].sum()) if unit in NN else 0
        rows.append(dict(t=t.date(), FundCode=h.FundCode, kind=h.kind, weight=round(h.weight, 4), unit=unit, map=how,
                         n_rows_win156=n_win, n_rows_le_t=n_all, n_hold_weeks=n_hold, n_hold_anchor=int(hold.sum())))
D = pd.DataFrame(rows)
out = FT / "scratch/factor-designer_s014_structure.csv"
D.to_csv(out, index=False)
print(D.to_string())
print("quarters", len(ts), "first", ts[0].date(), "last", ts[-1].date())
