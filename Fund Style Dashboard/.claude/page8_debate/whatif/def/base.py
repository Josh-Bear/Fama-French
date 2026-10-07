import sys, os, warnings
warnings.filterwarnings("ignore")
sys.path.insert(0, os.getcwd())
import numpy as np, pandas as pd
import config, data_access
from analysis import portfolio, screening

def selected_for(clean, use_sec, strict, min_score=config.SCORE_MIN_ELIGIBLE, snapshot=None):
    snap = data_access.get_index_snapshot() if snapshot is None else snapshot
    matches = data_access.get_score_matches(clean_country=clean)
    country = screening.zone_scores(snap, "country", config.SCORE_COUNTRY_CLEAN if clean else None)
    sector = screening.zone_scores(snap, "sector")
    matrix = screening.score_matrix(country, sector)
    scored = screening.fund_scores(matches, matrix)
    return screening.greedy_select(scored, n=config.SCORE_TOP_N, use_secondary=use_sec, strict_and=strict, min_score=min_score), scored, matrix
