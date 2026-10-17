# factor-reviewer S002: โครงข้อมูลเท่านั้น (นับกอง/สัปดาห์ · ชื่อกอง) -- ไม่ดูค่าผลตอบแทน ไม่ fit model
import pandas as pd, numpy as np, hashlib, json
B='.claude/factor_team/data/'
man=json.load(open(B+'manifest.json'))
def sha(p): return hashlib.sha256(open(p,'rb').read()).hexdigest()
spec={'panel_weekly.parquet':'95c16ee651d3a936788b7cb3c6372bbf5f1e84cb39daf5680343771dca24270b','panel_monthly.parquet':'e8e8cb5d5f04fba9bb35558ef7c3d8195c656334119e56f82775cc1ae21ccaed','factors_weekly.parquet':'115b87139d2bec0fd57a77a1593c46d36bb23f3f35f83236cdb07be642af47a8','factors_monthly.parquet':'f7c4248b4fa889853024449e72ae8909cf1f8d3226a54eebc37448a2a485bb72','aum_weekly.parquet':'48c34c73ae22ebffc6112f93e03f729223a496297bb65c324b693b817a723d26','universe.csv':'fdfb7830df78ce032465ac9d8cddc2c98f9aa86cfa0f3925fdb83026aa3f7252','dup_pairs.csv':'b1f0f0c745947fa70803a4f40526c0a1967c72925be985a2bedc1057d8b8aef3','factor_groups.csv':'42bf1cfb270721ae6112799ab795ebc4c91212e7584d5cdfee23b9b70b1b1731'}
print('sha all match spec:',all(sha(B+k)==v for k,v in spec.items()))
print('manifest mentions all:',all(v in json.dumps(man) for v in spec.values()))
u=pd.read_csv(B+'universe.csv'); u=u[u.included==True]
p=pd.read_parquet(B+'panel_weekly.parquet'); p=p[(p.date>='2021-01-01')&(p.date<='2025-12-31')]
obs=p.dropna(subset=['ret'])[['FundCode','date']]
dates=np.sort(obs.date.unique())
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
d=pd.DataFrame({'tr':cnt('2021-01-08','2023-12-29'),'te':cnt('2024-01-05','2025-12-26')}).fillna(0); d['pol']=pol
trD=cnt('2021-01-15','2023-12-29').reindex(d.index).fillna(0)
EVAL=d[(trD>=104)&(d.te>=52)].index; base=d[d.tr>=52].index
print('EVAL',len(EVAL),'base',len(base))
# m5: base funds with >=104 train rows but <52 test rows
lost=d[(trD>=104)&(d.te<52)]; print('m5 lost from EVAL (>=104 train,<52 test):',len(lost),lost.pol.value_counts().to_dict(),'te=0:',(lost.te==0).sum())
# split halves
rng=np.random.default_rng(20261015); half={}
for g in ['E','F','O']:
    m=sorted([x for x in base if d.loc[x,'pol']==g]); perm=rng.permutation(len(m)); k=len(m)//2
    for i,j in enumerate(perm): half[m[j]]='A' if i<k else 'B'
hs=pd.Series(half)
o2=obs[obs.FundCode.isin(base)].copy(); o2['h']=o2.FundCode.map(hs); o2['pol']=o2.FundCode.map(pol)
for per,(a,b) in {'train':('2021-01-08','2023-12-29'),'test':('2024-01-05','2025-12-26')}.items():
    q=o2[(o2.date>=a)&(o2.date<=b)].groupby(['date','h','pol']).size().unstack(['h','pol']).fillna(0)
    for h in 'AB':
        for g in 'FO':
            s=q[(h,g)]; print(per,h,g,'members',int((hs==h).sum() if False else ((hs==h)&(hs.index.map(pol)==g)).sum()),'weeks avail<=5 (2-port split guaranteed <3):',int((s<=5).sum()),'of',len(s),' <=3:',int((s<=3).sum()))
# names in E base that look non-equity / Thai
Eb=[x for x in base if pol[x]=='E']
kw=['GOLD','REIT','PROP','INFRA','SET','TH ','THAI','OIL','SILVER','DIV']
hits=[x for x in Eb if any(k in x.upper() for k in kw)]
print('E base n',len(Eb),'name hits',len(hits),sorted(hits))
print('policy of gold-named included funds:',u[u.FundCode.str.upper().str.contains('GOLD')].groupby('policy').size().to_dict())
