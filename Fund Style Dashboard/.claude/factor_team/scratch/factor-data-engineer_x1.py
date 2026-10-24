import pandas as pd, numpy as np
d=pd.read_parquet('.claude/factor_team/scratch/factor-data-engineer_goldraw.parquet')
for c in ['AsOfDate','NAVDate']: d[c]=pd.to_datetime(d[c])
d['upd']=pd.to_datetime(d['UpdateTime'],errors='coerce')
print(d.dtypes)
g=d[d.FundCode.isin(['BGOLD','UOBSG-N','KT-GOLD','TGOLD'])]
for c in ['BGOLD','UOBSG-N','KT-GOLD','TGOLD']:
    x=g[g.FundCode==c].sort_values('AsOfDate')
    x=x[(x.NAVDate>='2023-01-01')&(x.NAVDate<='2023-02-28')]
    print(c); print(x[['AsOfDate','NAVDate','NAV','UpdateTime']].head(16).to_string())
    print((x.AsOfDate-x.NAVDate).dt.days.value_counts().head())
