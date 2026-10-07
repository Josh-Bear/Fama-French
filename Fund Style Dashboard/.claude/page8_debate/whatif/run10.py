import warnings; warnings.filterwarnings("ignore")
import sys; sys.path.insert(0,".")
import numpy as np, pandas as pd
import config, data_access
from data import nav_loader
funds=["KT-MFE-A","PRINCIPAL GEF-X","LHGREEN-D","TUSFIN-A"]
sigma, info = data_access.portfolio_risk_model(tuple(funds), tuple(config.SCORE_COUNTRY_CLEAN))
nav = data_access._nav_by_fund(nav_loader.load_nav_history(funds)); lo=pd.Timestamp("2023-09-08")
C = np.eye(4)
for i,a in enumerate(funds):
    for j,b in enumerate(funds):
        if j<=i: continue
        x=nav[a][nav[a].index>=lo]; y=nav[b][nav[b].index>=lo]; idx=x.index.intersection(y.index)
        d=pd.concat([x.loc[idx].pct_change(),y.loc[idx].pct_change()],axis=1).dropna(); d=d.clip(d.quantile(.01),d.quantile(.99),axis=1)
        C[i,j]=C[j,i]=d.corr().iloc[0,1]
v=np.sqrt(np.diag(sigma)); S2=np.outer(v,v)*C
w=np.array([0.23,0.27,0.23,0.27])
print("model risk %.4f  realized-corr risk %.4f  (+%.0f%%)"%(np.sqrt(w@sigma.to_numpy()@w), np.sqrt(w@S2@w), 100*(np.sqrt(w@S2@w)/np.sqrt(w@sigma.to_numpy()@w)-1)))
print("min eig realized C", np.linalg.eigvalsh(C).min().round(3))
# risk contribution shift
mrc=S2@w; print("RC realized", (w*mrc/(w@mrc)).round(2), "RC model", (w*(sigma.to_numpy()@w)/(w@sigma.to_numpy()@w)).round(2))
