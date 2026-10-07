import warnings; warnings.filterwarnings("ignore")
import sys; sys.path.insert(0,".")
import numpy as np, pandas as pd
import config, data_access
from data import msci_index, nav_loader
from analysis import matching, screening
snap = data_access._load_index_snapshot()
m = data_access.score_matches(True)
c = screening.zone_scores(snap,"country", config.SCORE_COUNTRY_CLEAN); s = screening.zone_scores(snap,"sector")
mat = screening.score_matrix(c,s); sc = screening.fund_scores(m, mat)
top = list(sc.head(40).FundCode)
nav = data_access._nav_by_fund(nav_loader.load_nav_history(top))
cty = msci_index.load_country_index()[config.SCORE_COUNTRY_CLEAN]; sec = msci_index.load_sector_index()
agree_s=agree_c=agree_pair=0; n=0; rows=[]
for f in top:
    out={}
    for scope,lv in (("country",cty),("sector",sec)):
        a = matching.build_fund_returns(nav[f], lv)
        h = len(a)//2
        if h<60: break
        r1 = matching.match_exposure(a.iloc[:h], alternatives=False); r2 = matching.match_exposure(a.iloc[h:], alternatives=False)
        out[scope]=(r1["primary"], r2["primary"], r1["r2"], r2["r2"])
    if len(out)<2: continue
    n+=1
    ac = out["country"][0]==out["country"][1]; as_ = out["sector"][0]==out["sector"][1]
    agree_c+=ac; agree_s+=as_; agree_pair+= (ac and as_)
    z = lambda cc,ss: mat.at[cc,ss] if cc in mat.index and ss in mat.columns else np.nan
    rows.append((f, out["country"][0], out["country"][1], out["sector"][0], out["sector"][1], z(out["country"][0],out["sector"][0]), z(out["country"][1],out["sector"][1]), sc.set_index("FundCode").score[f]))
d = pd.DataFrame(rows, columns=["f","c1","c2","s1","s2","z1","z2","fullscore"])
print("n",n,"country primary same across halves: %d/%d, sector: %d/%d, both: %d/%d"%(agree_c,n,agree_s,n,agree_pair,n))
print(d.round(2).head(15).to_string())
print("zone value of pair, half1 vs half2 spearman", d[["z1","z2"]].corr(method="spearman").iloc[0,1])
