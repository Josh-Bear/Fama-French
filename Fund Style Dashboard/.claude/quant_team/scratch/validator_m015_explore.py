import sys; sys.path.insert(0, "."); sys.path.insert(0, ".claude/quant_team/backtest")
import numpy as np, pandas as pd
import common, fund_signals as fs
D = pd.read_parquet(".claude/quant_team/backtest/cache/m015_navF_clean.parquet")
p = pd.read_csv("base_data/FundProfile.csv", dtype=str, encoding="utf-8-sig"); p.columns=[c.strip() for c in p.columns]; p=p.drop_duplicates("Fund Code").set_index("Fund Code")
F = p[p["Fund Policy"]=="F"]
base = F[(F["Tax Type"].isna())&(F["buy period flag"]=="N")&(F["Project Retail Type"]=="R")&(pd.to_numeric(F["fst_lowbuy_val"],errors="coerce")<=1e5)]
base = base[~base["Fund Name EN"].fillna("").str.contains("Not for Retail|NOT FOR RETAIL|TEST")]
print(len(base), base["Fund Class"].isna().sum())
D = D[D.FundCode.isin(base.index)]
cal = common.load_calendar()
nba = {fc: g.set_index("NAVDate")["NAV"] for fc, g in D.groupby("FundCode")}
arr = fs._prep_arrays(nba)
for t in [pd.Timestamp("2022-03-31"), pd.Timestamp("2023-12-29"), pd.Timestamp("2025-12-31")]:
    U = common.universe_at(D, t)
    q = fs.QuarterContext(arr, cal, t)
    sig = fs.compute_quarter_signals(q, U.FundCode.tolist())
    # raw vol (ไม่มี floor)
    raws=[]
    for fc in U.FundCode:
        w = q.weekly_return_series(fc).dropna()
        raws.append((fc, len(w), float(w.std(ddof=1)*np.sqrt(52)) if len(w)>2 else np.nan, float((w==0).mean()) if len(w) else np.nan))
    R = pd.DataFrame(raws, columns=["FundCode","n","vol_raw","zero"]).set_index("FundCode")
    s = sig.set_index("FundCode").join(R)
    s["risk"] = p["Fund Risk Level"].reindex(s.index)
    mm = s[s.risk.isin(["1","2"])]
    print(t.date(), "U", len(U), "| sig vol52 notna", int(s.vol52.notna().sum()), "| MMF in U", len(mm), "MMF vol52 notna", int(mm.vol52.notna().sum()),
          "| MMF raw vol median", mm.vol_raw.median(), "zero-frac>0.2:", int((mm.zero>0.2).sum()), " raw vol<0.02 any:", int((s.vol_raw<0.02).sum()))
