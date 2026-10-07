import warnings; warnings.filterwarnings("ignore")
import sys; sys.path.insert(0,".")
import numpy as np, pandas as pd
import config, data_access
from data import nav_loader
funds=["KT-MFE-A","PRINCIPAL GEF-X","KT-JPFUND-A","K-AEC"]
nav = data_access._nav_by_fund(nav_loader.load_nav_history(funds)); lo=pd.Timestamp("2023-09-08")
for a,b in [("KT-MFE-A","PRINCIPAL GEF-X"),("KT-MFE-A","KT-JPFUND-A"),("KT-MFE-A","K-AEC"),("PRINCIPAL GEF-X","KT-JPFUND-A")]:
    x=nav[a][nav[a].index>=lo]; y=nav[b][nav[b].index>=lo]; idx=x.index.intersection(y.index)
    for step in (1,5,10):
        s=idx[::step]
        d=pd.concat([x.loc[s].pct_change(),y.loc[s].pct_change()],axis=1).dropna()
        print(a,b,"step",step,"n",len(d),"corr raw %.2f"%d.corr().iloc[0,1])
