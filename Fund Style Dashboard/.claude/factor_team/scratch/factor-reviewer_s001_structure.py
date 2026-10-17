# factor-reviewer: ตรวจโครงข้อมูลเท่านั้น (จำนวนกอง/สัปดาห์/คอลัมน์) -- ไม่ดูค่าผลตอบแทน ไม่ fit model
import pandas as pd, numpy as np
B='.claude/factor_team/data/'
u=pd.read_csv(B+'universe.csv'); print('universe cols',u.columns.tolist())
ui=u[u.included==True]
print('n_weeks desc', ui.n_weeks.describe().to_dict())
fw=pd.read_parquet(B+'factors_weekly.parquet'); print('factors shape',fw.shape); print(fw.columns.tolist())
need=['MSCI_ACWI','AGG_THB','Gold_THB','USDTHB','MSCI_EM','MSCI_WORLD','MSCI_USA','TDEX_THB','IEF_THB','SHV_THB','LQD_THB','HYG_THB','EMB_THB','Momentum','Quality','Value','LowVol','VIX_d','US10Y_d','Oil_Brent','TH5Y_d','DTB3_d','RF_BOT','MSCI_EUROPE','MSCI_JAPAN','MSCI_CHINA_ALL_SHARES','MSCI_ASIA_EX_JAPAN','MSCI_INDIA','MSCI_VIETNAM']
print('missing needed cols',[c for c in need if c not in fw.columns])
fg=pd.read_csv(B+'factor_groups.csv'); print(fg.head(80).to_string())
p=pd.read_parquet(B+'panel_weekly.parquet'); print('panel cols',p.columns.tolist())
p=p[(p.date>='2021-01-01')&(p.date<='2025-12-31')].dropna(subset=['ret'])
pol=ui.set_index('FundCode').policy
dp=pd.read_csv(B+'dup_pairs.csv')
par={}
def f(x):
    par.setdefault(x,x)
    while par[x]!=x: par[x]=par[par[x]]; x=par[x]
    return x
for a,b in zip(dp.a,dp.b): par[f(a)]=f(b)
comp={}
for x in list(par): comp.setdefault(f(x),[]).append(x)
nw=ui.set_index('FundCode').n_weeks; drop=set()
for g in comp.values():
    g=sorted(g,key=lambda c:(-nw.get(c,0),c)); drop|=set(g[1:])
p=p[~p.FundCode.isin(drop)]
first=p.date.min()
def cnt(lo,hi,dropfirst=True):
    s=p[(p.date>=lo)&(p.date<=hi)]
    if dropfirst: s=s[s.date!=first]
    return s.groupby('FundCode').size()
tr=cnt('2021-01-01','2023-12-31'); te=cnt('2024-01-01','2025-12-31',False)
trraw=p[p.date<='2023-12-31'].groupby('FundCode').size()
h1=cnt('2021-01-01','2023-06-30'); h2=cnt('2023-07-01','2025-12-31',False)
t22=cnt('2022-01-01','2023-12-31',False)
d=pd.DataFrame({'tr':tr,'trraw':trraw,'te':te,'h1':h1,'h2':h2,'t22':t22}).fillna(0); d['pol']=pol
ev=d[(d.trraw>=104)&(d.te>=52)]
print('EVAL (raw-week rule)',ev.pol.value_counts().to_dict(),len(ev))
ev2=d[(d.tr>=104)&(d.te>=52)]; print('EVAL (Dimson-row rule)',ev2.pol.value_counts().to_dict(),len(ev2))
bal=d[d.trraw>=156]; print('balanced',bal.pol.value_counts().to_dict())
print('EVAL ∩ balanced',ev.index.isin(bal.index).sum(),'EVAL not in balanced',(~ev.index.isin(bal.index)).sum(), ev[~ev.index.isin(bal.index)].pol.value_counts().to_dict())
print('balanced not in EVAL', (~bal.index.isin(ev.index)).sum())
for k in [52,78,104]:
    s=ev[(ev.h1>=k)&(ev.h2>=k)]; print(f'EVAL with >= {k} rows both halves',s.pol.value_counts().to_dict(),len(s))
print('weeks: H1',p[(p.date<='2023-06-30')].date.nunique(),'H2',p[(p.date>='2023-07-01')].date.nunique(),'2022-23',p[(p.date>='2022-01-01')&(p.date<='2023-12-31')].date.nunique())
for k in [104,103,78,52]:
    s=ev[ev.t22>=k]; print(f'EVAL with >= {k} rows in 2022-23',s.pol.value_counts().to_dict(),len(s))
# unbalanced base 277 and E region candidates count
ub=d[d.trraw>=52]; print('unbalanced base',ub.pol.value_counts().to_dict())
# rolling windows count
dates=sorted(p.date.unique()); print('n weeks main',len(dates)); nwin=len(range(0,len(dates)-104+1,4)); print('rolling windows step4',nwin)
# quarter-end tau for MOM: first tau with >=40 weeks in (tau-52w, tau-4w]
ds=pd.Series(pd.to_datetime(dates))
for tau in ['2021-09-24','2021-12-31','2022-03-25']:
    t=pd.Timestamp(tau); w=ds[(ds>t-pd.Timedelta(weeks=52))&(ds<=t-pd.Timedelta(weeks=4))]; print('tau',tau,'weeks in formation window',len(w))
# balanced-within-window subsets of EVAL (for PY paper-form)
print('EVAL complete train 155 rows',ev[ev.tr>=155].pol.value_counts().to_dict(),'complete test 104',ev[ev.te>=104].pol.value_counts().to_dict())
