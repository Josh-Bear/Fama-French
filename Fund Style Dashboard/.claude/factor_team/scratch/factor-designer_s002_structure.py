# factor-designer S002: ตรวจโครงข้อมูลเท่านั้น (นับกอง/สัปดาห์) -- ไม่ดูค่าผลตอบแทน ไม่ fit model
import pandas as pd, numpy as np
B='.claude/factor_team/data/'
u=pd.read_csv(B+'universe.csv'); u=u[u.included==True]
p=pd.read_parquet(B+'panel_weekly.parquet')
p=p[(p.date>='2021-01-01')&(p.date<='2025-12-31')]
obs=p.dropna(subset=['ret'])[['FundCode','date']]   # ใช้เฉพาะการมีค่า
dates=np.sort(obs.date.unique()); print('weeks',len(dates),dates[0],dates[-1])
dp=pd.read_csv(B+'dup_pairs.csv'); par={}
def f(x):
    par.setdefault(x,x)
    while par[x]!=x: par[x]=par[par[x]]; x=par[x]
    return x
for a_,b_ in zip(dp.a,dp.b): par[f(a_)]=f(b_)
comp={}
for x in list(par): comp.setdefault(f(x),[]).append(x)
nw=u.set_index('FundCode').n_weeks; drop=set()
for g in comp.values(): g=sorted(g,key=lambda c:(-nw.get(c,0),c)); drop|=set(g[1:])
pol=u.set_index('FundCode').policy
obs=obs[~obs.FundCode.isin(drop)]
def cnt(a,b): return obs[(obs.date>=a)&(obs.date<=b)].groupby('FundCode').size()
tr=cnt('2021-01-08','2023-12-29'); te=cnt('2024-01-05','2025-12-26')
d=pd.DataFrame({'tr':tr,'te':te}).fillna(0); d['pol']=pol
# Dimson train rows = rows excluding first week 2021-01-08
trD=cnt('2021-01-15','2023-12-29').reindex(d.index).fillna(0)
EVAL=d[(trD>=104)&(d.te>=52)].index; print('EVAL',len(EVAL),d.loc[EVAL,'pol'].value_counts().to_dict())
base=d[d.tr>=52].index; print('base unbalanced',len(base),d.loc[base,'pol'].value_counts().to_dict())
c2=cnt('2022-01-14','2023-12-29').reindex(EVAL).fillna(0)
print('2c train rows among EVAL: min',c2.min(),'>=78',(c2>=78).sum(),'complete103',(c2>=103).sum(), d.loc[c2[c2>=103].index,'pol'].value_counts().to_dict())
h1=cnt('2021-01-15','2023-06-30').reindex(EVAL).fillna(0); h2=cnt('2023-07-07','2025-12-26').reindex(EVAL).fillna(0)
S191=EVAL[(h1>=104)&(h2>=104)]; print('STAB set',len(S191),d.loc[S191,'pol'].value_counts().to_dict())
h1c=cnt('2022-01-14','2023-06-30').reindex(S191).fillna(0)
print('2c H1 rows among STAB: max',h1c.max(),'min',h1c.min(),'>=52',(h1c>=52).sum(),'>=60',(h1c>=60).sum())
# rolling windows
st=list(range(0,260-104+1,4)); print('n windows',len(st))
ok=[s for s in st if pd.Timestamp(dates[s])>=pd.Timestamp('2022-01-14')]; print('2c windows',len(ok),dates[ok[0]] if ok else None)
cov=[]
for s in st:
    a,b=dates[s],dates[s+103]; c=cnt(a,b).reindex(S191).fillna(0); cov.append((c>=78).sum())
print('STAB funds with>=78 per window: min',min(cov),'max',max(cov))
# PY complete rows
print('PY train complete(155)',(trD.reindex(EVAL)>=155).sum(),'test complete(104)',(d.loc[EVAL,'te']>=104).sum())
# split-half stratified by policy
rng=np.random.default_rng(20261015); half={}
for g in ['E','F','O']:
    m=sorted([x for x in base if d.loc[x,'pol']==g]); perm=rng.permutation(len(m)); k=len(m)//2
    for i,j in enumerate(perm): half[m[j]]='A' if i<k else 'B'
hs=pd.Series(half); print('halves',pd.crosstab(hs,d.loc[hs.index,'pol']).to_dict())
o2=obs[obs.FundCode.isin(base)].copy(); o2['h']=o2.FundCode.map(hs); o2['pol']=o2.FundCode.map(pol)
for per,(a,b) in {'train':('2021-01-08','2023-12-29'),'test':('2024-01-05','2025-12-26')}.items():
    q=o2[(o2.date>=a)&(o2.date<=b)].groupby(['date','h','pol']).size().unstack(['h','pol'])
    print(per,'min per week by half/policy',q.min().to_dict())
