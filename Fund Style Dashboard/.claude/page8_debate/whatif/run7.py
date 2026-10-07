import warnings; warnings.filterwarnings("ignore")
import sys; sys.path.insert(0,".")
import numpy as np, pandas as pd
pd.set_option("display.width",250); pd.set_option("display.max_columns",30)
import config, data_access
from analysis import screening, metrics
from data import msci_index
snap = data_access._load_index_snapshot()
print(snap[snap.scope=="sector"][["index",config.SCORE_RETURN_COL,"vol_forecast","garch_fallback"]].round(4).to_string())
print(snap[snap.scope=="country"][["index",config.SCORE_RETURN_COL,"vol_forecast","garch_fallback"]].round(4).to_string())
# (f) fragility of zone under window/skip changes
cty = msci_index.load_country_index(); sec = msci_index.load_sector_index()
lv = pd.concat([cty, sec],axis=1)
def snap_w(win, skip):
    s = snap.copy()
    s[config.SCORE_RETURN_COL] = [metrics.recent_return(lv[ix], window=win, max_gap_days=None, skip=skip) for ix in s["index"]]
    return s
m = data_access.score_matches(True)
base_c = screening.zone_scores(snap,"country", config.SCORE_COUNTRY_CLEAN); base_s = screening.zone_scores(snap,"sector")
bsc = screening.fund_scores(m, screening.score_matrix(base_c, base_s))
bsel = screening.greedy_select(bsc, n=20, min_score=0.7)
bset = list(bsel[bsel.eligible].head(5).FundCode)
print("BASE", bset)
for win, skip in [(252,21),(231,21),(273,21),(252,0),(252,42),(189,21),(126,21),(315,21)]:
    s = snap_w(win, skip)
    c = screening.zone_scores(s,"country", config.SCORE_COUNTRY_CLEAN); se = screening.zone_scores(s,"sector")
    sc = screening.fund_scores(m, screening.score_matrix(c, se))
    sel = screening.greedy_select(sc, n=20, min_score=0.7)
    st_ = list(sel[sel.eligible].head(5).FundCode)
    print(win, skip, "n_elig",int(sel.eligible.sum()), st_, "overlap w/ base", len(set(st_)&set(bset)))
# threshold sensitivity
for th in (0.5,0.6,0.7,0.8,0.9,1.0,1.5):
    sel = screening.greedy_select(bsc, n=20, min_score=th)
    print("min_score",th,"eligible",int(sel.eligible.sum()), list(sel[sel.eligible].head(5).FundCode))
# (g) label quality
coefs = data_access._load_coefs()
for scope in ("sector","country"):
    sub = coefs[coefs.scope==scope]
    rows=[]
    for f,g in sub.groupby("FundCode"):
        a = g["elastic"].abs().sort_values(ascending=False)
        if len(a)<2 or a.iloc[0]<=0: continue
        rows.append((f, a.iloc[1]/a.iloc[0], a.iloc[0]/a.sum(), (a>1e-9).sum()))
    d = pd.DataFrame(rows, columns=["f","sec_over_pri","pri_share","nnz"]).set_index("f")
    print(scope, "n",len(d), "sec/pri>0.9: %.0f%%"%(100*(d.sec_over_pri>0.9).mean()), ">0.7: %.0f%%"%(100*(d.sec_over_pri>0.7).mean()), "pri_share median %.2f"%d.pri_share.median(), "nnz median", d.nnz.median())
    print(d.loc[[x for x in ["KT-MFE-A","PRINCIPAL GEF-X","KT-JPFUND-A","K-AEC","LHGREEN-D","TUSFIN-A"] if x in d.index]].round(2))
r = data_access._load_results().set_index("FundCode")
print(r.loc[["KT-MFE-A","PRINCIPAL GEF-X","KT-JPFUND-A","K-AEC"],["FundName","country_r2","sector_r2","sector_primary","sector_secondary","sector_primary_coef"]])
print(m.set_index("FundCode").loc[["KT-MFE-A","PRINCIPAL GEF-X","KT-JPFUND-A","K-AEC"]].T)
