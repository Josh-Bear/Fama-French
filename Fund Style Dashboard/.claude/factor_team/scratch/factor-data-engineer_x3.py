import pandas as pd, numpy as np
parts=[]
for ch in pd.read_csv('base_data/nav_history_db.csv',usecols=['AsOfDate','FundCode'],dtype={'FundCode':str},chunksize=500000):
    ch['AsOfDate']=pd.to_datetime(ch['AsOfDate'],errors='coerce')
    parts.append(ch.dropna(subset=['AsOfDate']).groupby('AsOfDate').size())
s=pd.concat(parts).groupby(level=0).sum()
s=s[s.index>='2023-06-01']
fri=s[s.index.dayofweek==4]
print(fri.loc['2023-09-01':'2024-03-31'].to_string())
print(fri.loc['2025-09-01':'2026-03-31'].to_string())
# all weekday rows per day near gap, median per weekday
print(s.loc['2023-12-18':'2024-01-20'].to_string())
