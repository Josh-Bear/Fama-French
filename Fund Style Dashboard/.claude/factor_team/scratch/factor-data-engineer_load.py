import sys, pandas as pd, numpy as np
sys.dont_write_bytecode=True
import config
codes=['BGOLD','I-GOLD','IGOLD-G','K-GOLD-A(A)','KT-GOLD','PRINCIPAL iGOLD-A','TGOLD','UOBSG-N']
p=pd.read_csv('base_data/FundProfile.csv')
m=p[(p['Fund Policy']=='O')&(p['Fund Name EN'].str.contains('gold',case=False,na=False)|p['Fund Name TH'].str.contains('ทอง',na=False))]
ext=sorted(set(m['Fund Code'].astype(str).str.strip())|set(codes))
parts=[]
for ch in pd.read_csv(config.NAV_HISTORY_CSV,usecols=['AsOfDate','FundCode','NAV','NAVDate','UpdateTime','AUM'],dtype={'FundCode':str},chunksize=500000):
    ch['FundCode']=ch['FundCode'].str.strip()
    s=ch[ch.FundCode.isin(ext)]
    if len(s): parts.append(s)
d=pd.concat(parts,ignore_index=True)
d.to_parquet('.claude/factor_team/scratch/factor-data-engineer_goldraw.parquet')
print(len(d), d.FundCode.nunique())
print(d.groupby('FundCode').agg(n=('NAV','size'),first=('NAVDate','min'),last=('NAVDate','max')).to_string())
