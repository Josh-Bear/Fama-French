import sys, os
sys.path.insert(0, "."); sys.path.insert(0, ".claude/quant_team/backtest")
import numpy as np, pandas as pd
CACHE = ".claude/quant_team/backtest/cache/m015_navF_clean.parquet"
p = pd.read_csv("base_data/FundProfile.csv", dtype=str, encoding="utf-8-sig"); p.columns = [c.strip() for c in p.columns]
p = p.drop_duplicates("Fund Code").set_index("Fund Code")
codes = set(p.index[p["Fund Policy"] == "F"])
parts = []
for ch in pd.read_csv("base_data/nav_history_db.csv", usecols=["FundCode", "NAV", "NAVDate", "AUM", "UpdateTime"], chunksize=500_000, dtype={"FundCode": str}):
    parts.append(ch[ch["FundCode"].isin(codes)])
d = pd.concat(parts)
d["NAVDate"] = pd.to_datetime(d["NAVDate"], errors="coerce")
d = d.dropna(subset=["NAVDate", "NAV"]); d = d[d["NAV"] > 0]
d = d.sort_values(["FundCode", "NAVDate", "UpdateTime"]).drop_duplicates(["FundCode", "NAVDate"], keep="last")
# §4.2 single-tick spike rule (log-return)
out, log = [], []
for fc, g in d.groupby("FundCode"):
    g = g.sort_values("NAVDate").copy()
    v = g["NAV"].to_numpy(float); n = len(v); k = 0
    if n >= 3:
        lr = np.diff(np.log(v)); rin, rout = lr[:-1], lr[1:]
        m = (np.abs(rin) > 0.005) & (np.abs(rout) > 0.005) & (np.sign(rin) != np.sign(rout)) & (np.abs(rin + rout) < 0.001)
        idx = np.where(m)[0] + 1
        # ไม่แก้จุดติดกัน (กัน cascade): ใช้ค่าดั้งเดิมของเพื่อนบ้านเสมอ (vectorized จากค่าเดิม)
        v2 = v.copy(); v2[idx] = np.sqrt(v[idx - 1] * v[idx + 1]); k = len(idx)
        g["NAV"] = v2
    g["spike_fixed"] = False
    if k: g.iloc[idx, g.columns.get_loc("spike_fixed")] = True
    log.append((fc, k)); out.append(g)
D = pd.concat(out)
D.to_parquet(CACHE)
L = pd.DataFrame(log, columns=["FundCode", "n_fixed"])
L.to_csv(".claude/quant_team/backtest/cache/m015_navF_spike_log.csv", index=False)
print("rows", len(D), "funds", D.FundCode.nunique(), "fixed pts", int(L.n_fixed.sum()), "funds w/ fix", int((L.n_fixed > 0).sum()))
print(L.sort_values("n_fixed", ascending=False).head(10).to_string(index=False))
