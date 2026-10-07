import warnings; warnings.filterwarnings("ignore")
import sys; sys.path.insert(0,".")
import numpy as np, pandas as pd
import config, data_access
from analysis import portfolio, screening
snap = data_access._load_index_snapshot()
for clean in (True, False):
    m = data_access.score_matches(clean)
    ids = config.SCORE_COUNTRY_CLEAN if clean else config.MSCI_COUNTRY_COLS
    c = screening.zone_scores(snap,"country", config.SCORE_COUNTRY_CLEAN if clean else None)
    s = screening.zone_scores(snap,"sector")
    mat = screening.score_matrix(c,s)
    sc = screening.fund_scores(m, mat)
    print(clean, len(m), len(sc))
    for strict in (True, False):
      for sec in (True, False):
        sel = screening.greedy_select(sc, n=20, use_secondary=sec, strict_and=strict, min_score=0.7)
        print("  and" if strict else "  or", "sec" if sec else "pri", "eligible:", int(sel.eligible.sum()), list(sel[sel.eligible].FundCode.head(5)))
    if clean:
        print(mat.round(1).to_string()); print(c.round(3)); print(s.round(3))
        print(sc.head(12)[["FundCode","country_primary","sector_primary","country_r2","sector_r2","score"]])
        print(sc.score.describe())
