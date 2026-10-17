# factor-designer: ตรวจโครงข้อมูลเท่านั้น (จำนวนกอง/สัปดาห์) -- ไม่ดูค่าผลตอบแทน ไม่ fit model
import pandas as pd, numpy as np
B='.claude/factor_team/data/'
u=pd.read_csv(B+'universe.csv'); u=u[u.included==True]
fp=pd.read_csv('base_data/FundProfile.csv', encoding='utf-8-sig', usecols=['Fund Code','Fund Policy','Tax Type','FIF Flag','FX Risk Flag','ETF Flag','Fund Compare Perfermance Description'])
fp=fp.drop_duplicates('Fund Code').rename(columns={'Fund Code':'FundCode'})
m=u.merge(fp,on='FundCode',how='left')
print('n panel',len(m), m.policy.value_counts().to_dict())
for c in ['FIF Flag','FX Risk Flag','Tax Type','ETF Flag']:
    print(c); print(pd.crosstab(m.policy,m[c].fillna('NA')))
print(pd.crosstab([m.policy,m['FIF Flag'].fillna('NA')],m['FX Risk Flag'].fillna('NA')))
p=pd.read_parquet(B+'panel_weekly.parquet')
p=p[(p.date>='2021-01-01')&(p.date<='2025-12-31')]
obs=p.dropna(subset=['ret'])  # นับเฉพาะการมีค่า ไม่ดูค่า
tr=obs[obs.date<='2023-12-31'].groupby('FundCode').size(); te=obs[obs.date>='2024-01-01'].groupby('FundCode').size()
d=m[['FundCode','policy','FIF Flag']].set_index('FundCode'); d['tr']=tr; d['te']=te; d=d.fillna({'tr':0,'te':0})
print('train weeks',obs[obs.date<='2023-12-31'].date.nunique(),'test weeks',obs[obs.date>='2024-01-01'].date.nunique())
for a,b in [(156,104),(104,52),(78,52),(52,52),(52,26),(0,52)]:
    s=d[(d.tr>=a)&(d.te>=b)]; print(f'tr>={a} te>={b}', s.policy.value_counts().to_dict(), 'FIF', s.groupby(['policy','FIF Flag']).size().to_dict())
# first-week / test start counts
print('alive at 2021-01-08', obs[obs.date==obs.date.min()].FundCode.nunique())
# dup groups
dp=pd.read_csv(B+'dup_pairs.csv'); print(dp.columns.tolist())
# fee file structure
fee=pd.read_csv('base_data/SecFundFee.csv',encoding='utf-8-sig',nrows=5); print(fee.columns.tolist())
fee=pd.read_csv('base_data/SecFundFee.csv',encoding='utf-8-sig',usecols=['As of Date','Fund Code','Code'])
print('fee codes',fee.Code.value_counts().head(12).to_dict()); print('fee dates',fee['As of Date'].min(),fee['As of Date'].max(), fee['As of Date'].nunique())
print('fee coverage panel', d.index.isin(fee['Fund Code']).sum())
a=pd.read_parquet(B+'aum_weekly.parquet'); a=a[a.FundCode.isin(d.index)]
a0=a[(a.date<='2021-01-31')].dropna(subset=['aum']).FundCode.nunique(); a3=a[(a.date>='2023-12-01')&(a.date<='2023-12-31')].dropna(subset=['aum']).FundCode.nunique()
print('aum nonnull Jan2021',a0,'Dec2023',a3)
# --- dedup sets (connected components; keep longest n_weeks, tie -> alphabetical) ---
import itertools
par={}
def f(x):
    par.setdefault(x,x)
    while par[x]!=x: par[x]=par[par[x]]; x=par[x]
    return x
for a_,b_ in zip(dp.a,dp.b): par[f(a_)]=f(b_)
comp={}
for x in list(par): comp.setdefault(f(x),[]).append(x)
nw=u.set_index('FundCode').n_weeks
drop=set()
for g in comp.values():
    g=sorted(g,key=lambda c:(-nw.get(c,0),c)); drop|=set(g[1:])
print('dup groups',len(comp),'drop',len(drop),'drop in panel',len(drop&set(d.index)))
dd=d[~d.index.isin(drop)]
for name,s in [('EVAL tr>=104&te>=52',dd[(dd.tr>=104)&(dd.te>=52)]),('balanced train tr==156',dd[dd.tr>=156]),('tr>=52',dd[dd.tr>=52]),('te>=52',dd[dd.te>=52]),('tr>=52&te>=52',dd[(dd.tr>=52)&(dd.te>=52)])]:
    print('DEDUP',name,s.policy.value_counts().to_dict(),len(s))
print('FULL tr>=52',d[d.tr>=52].policy.value_counts().to_dict())
# weekly alive counts per policy in train/test (count only)
cnt=obs.merge(m[['FundCode','policy']],on='FundCode').groupby(['date','policy']).size().unstack()
print('min per week train',cnt[cnt.index<='2023-12-31'].min().to_dict(),'test',cnt[cnt.index>='2024-01-01'].min().to_dict())
try:
    import statsmodels, scipy; print('statsmodels',statsmodels.__version__,'scipy',scipy.__version__)
except Exception as e: print('import',e)
