"""M012 ex-ante counts (read-only, no returns): families in approx I_t passing AUM / age (A: first NAVDate, B: Registration_date)
and effect on M011-RFH holdings. Run: ./.venv/bin/python .claude/quant_team/scratch/quant_m012_counts.py
"""
import sys
sys.path.insert(0, ".")
import pandas as pd
import data_access
from analysis import fund_signals as fs

nav = pd.read_parquet("cache/nav_clean.parquet", columns=["FundCode", "NAVDate", "AUM"])
nav["NAVDate"] = pd.to_datetime(nav["NAVDate"])
groups = data_access.share_class_groups()
fam = {fc: fs.family_of(fc, groups)[0] for fc in nav["FundCode"].unique()}
nav["family"] = nav["FundCode"].map(fam)
prof = pd.read_csv("base_data/FundProfile.csv", usecols=["Fund Code", "Registration_date"], dtype=str)
reg = pd.to_datetime(prof.set_index("Fund Code")["Registration_date"], format="%Y%m%d", errors="coerce")
first = nav.groupby("FundCode")["NAVDate"].min()
w = pd.read_csv(".claude/quant_team/backtest/results/M011-RFH_weights.csv", parse_dates=["t"])
w = w[(w["kind"] == "full") & (w["FundCode"] != "CASH")]

rows, port = [], []
for t in sorted(w["t"].unique()):
    t = pd.Timestamp(t)
    sub = nav[nav["NAVDate"] <= t]
    lastd = sub.groupby("FundCode")["NAVDate"].max()
    hist = sub[sub["NAVDate"] >= "2021-01-01"].groupby("FundCode")["NAVDate"].nunique()
    cand = [f for f in lastd.index if (t - lastd[f]).days <= 10 and hist.get(f, 0) >= 252 and not fs.is_tax_class(f)]
    # family AUM = sum over ALL classes of last positive AUM within 90 days
    p = sub[sub["AUM"] > 0].sort_values("NAVDate").groupby("FundCode").tail(1)
    p = p[(t - p["NAVDate"]).dt.days <= 90]
    fam_aum = p.groupby("family")["AUM"].sum()
    fam_first = sub.groupby("family")["NAVDate"].min()
    regs = pd.Series({f: reg.get(f, pd.NaT) for f in sub["FundCode"].unique()})
    regs = regs.where(regs.notna(), first.reindex(regs.index))
    fam_reg = regs.groupby(regs.index.map(fam)).min()
    fams = sorted({fam[f] for f in cand})
    cut = t - pd.Timedelta(days=730)
    a = pd.Series({f: fam_aum.get(f, 0) >= 1e8 for f in fams})
    gA = pd.Series({f: fam_first[f] <= cut for f in fams})
    gB = pd.Series({f: fam_reg.get(f, fam_first[f]) <= cut for f in fams})
    rows.append(dict(t=t.date(), fam=len(fams), aum_ok=a.sum(), ageA_ok=gA.sum(), bothA=(a & gA).sum(),
                     ageB_ok=gB.sum(), bothB=(a & gB).sum()))
    h = w[w["t"] == t]
    hf = h["FundCode"].map(fam)
    ha = hf.map(fam_aum).fillna(0)
    port.append(dict(t=t.date(), n_held=len(h), min_aum_mb=round(ha.min() / 1e6, 1),
                     fail_aum=",".join(h.loc[ha.values < 1e8, "FundCode"]),
                     fail_ageA=int((hf.map(fam_first) > cut).sum()),
                     fail_ageB=",".join(h.loc[(hf.map(fam_reg) > cut).values, "FundCode"])))
print(pd.DataFrame(rows).to_string(index=False))
print(pd.DataFrame(port).to_string(index=False))
