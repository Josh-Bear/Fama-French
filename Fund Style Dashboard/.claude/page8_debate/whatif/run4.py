import warnings; warnings.filterwarnings("ignore")
import sys; sys.path.insert(0,".")
import numpy as np, pandas as pd
import config, data_access
from data import msci_index, nav_loader
from analysis import screening
res = data_access._load_results()
funds = data_access.policy_universe(res, config.SCORE_POLICY)
nav = data_access._nav_by_fund(nav_loader.load_nav_history(funds))
last = pd.Series({f: nav[f].index.max() for f in funds}); first = pd.Series({f: nav[f].index.min() for f in funds})
print(last.describe()); 
stale = last[last < pd.Timestamp("2026-06-30")]
print("stale (<2026-06-30):", len(stale)); print(stale.sort_values().head(15))
print("results cols", [c for c in res.columns][:40])
snap = data_access._load_index_snapshot()
for clean in (True, False):
    m = data_access.score_matches(clean)
    ids = config.SCORE_COUNTRY_CLEAN if clean else config.MSCI_COUNTRY_COLS
    c = screening.zone_scores(snap,"country", config.SCORE_COUNTRY_CLEAN if clean else None)
    s = screening.zone_scores(snap,"sector")
    sc = screening.fund_scores(m, screening.score_matrix(c,s))
    sc["last"]=sc.FundCode.map(last)
    for strict in (True, False):
      for sec in (True, False):
        sel = screening.greedy_select(sc, n=20, use_secondary=sec, strict_and=strict, min_score=0.7)
        p = sel[sel.eligible].head(5)
        print(clean, strict, sec, [(r.FundCode, str(nav[r.FundCode].index.max().date())) for r in p.itertuples()])
    print("eligible-scoring stale funds in scored (score>=0.7):", ((sc.score>=0.7)&(sc["last"]<pd.Timestamp("2026-06-30"))).sum(), "of", (sc.score>=0.7).sum())
