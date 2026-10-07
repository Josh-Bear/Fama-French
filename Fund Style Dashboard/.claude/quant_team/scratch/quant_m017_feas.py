import sys, time, os
sys.path.insert(0, "."); sys.path.insert(0, ".claude/quant_team/backtest")
import pandas as pd, pickle
import common, exposure, config
nav = common.load_nav(); nbf = common.build_nav_by_fund(nav); cal = common.load_calendar()
lc, ls, _ = common.load_levels()
q = common.quarter_ends(cal, "2022-03-31", "2025-12-31")
t = q[0]; u = common.universe_at(nav, t)
cp = os.path.join(common.CACHE_DIR, f"exposure_country_11c_{t.date()}.parquet")
c = pd.read_parquet(cp); print("u", len(u), "cache", len(c), "subset", set(u.FundCode) <= set(c.FundCode))
ctx = pickle.load(open(".claude/quant_team/scratch/validator_m012_ctxs.pkl","rb"))
print("I_t", len(ctx[0]["i_t"]), set(ctx[0]["i_t"].FundCode) <= set(c.FundCode))
for qi,t in enumerate(q):
    c = pd.read_parquet(os.path.join(common.CACHE_DIR, f"exposure_country_11c_{t.date()}.parquet"))
    s = pd.read_parquet(os.path.join(common.CACHE_DIR, f"exposure_sector_10c_{t.date()}.parquet"))
    it = set(ctx[qi]["i_t"].FundCode)
    print(t.date(), len(c), len(s), "Isub", it <= set(c.FundCode), it <= set(s.FundCode), "negcoef c", int((c.primary_coef<0).sum()), "s", int((s.primary_coef<0).sum()))
t1 = time.time()
x = exposure.fit_scope(list(u.FundCode[:16]), nbf, lc, config.SCORE_COUNTRY_CLEAN, pd.Timestamp("2022-04-29"), "country", use_cache=False)
print("16 funds fit", time.time()-t1)
