import pandas as pd, numpy as np
cnt_as={}; cnt_nd={}
parts=[]
for ch in pd.read_csv('base_data/nav_history_db.csv',usecols=['AsOfDate','NAVDate','FundCode'],dtype={'FundCode':str},chunksize=500000):
    ch['AsOfDate']=pd.to_datetime(ch['AsOfDate'],errors='coerce'); ch['NAVDate']=pd.to_datetime(ch['NAVDate'],errors='coerce')
    a=ch.dropna(subset=['AsOfDate']); n=ch.dropna(subset=['NAVDate'])
    parts.append((a.groupby([a.AsOfDate.dt.year,a.AsOfDate.dt.dayofweek]).size(), n.groupby([n.NAVDate.dt.year,n.NAVDate.dt.dayofweek]).size()))
A=pd.concat([p[0] for p in parts]).groupby(level=[0,1]).sum(); N=pd.concat([p[1] for p in parts]).groupby(level=[0,1]).sum()
pd.set_option('display.width',200)
print('AsOfDate rows by year x weekday'); print(A.unstack(fill_value=0))
print('NAVDate rows'); print(N.unstack(fill_value=0))
