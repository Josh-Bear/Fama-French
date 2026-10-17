# factor-reviewer S003: โครงข้อมูลเท่านั้น (นับแถว/NaN/ชื่อ) -- ไม่ดูค่าผลตอบแทน ไม่ fit model
import pandas as pd, numpy as np
exec(open('.claude/factor_team/scratch/factor-reviewer_s002_structure.py').read())
B='.claude/factor_team/data/'
for f in ('factors_weekly','factors_monthly'):
    F=pd.read_parquet(B+f+'.parquet')
    idx=F.index if 'date' not in F.columns else F['date']
    print(f,'rows',len(F),'first',str(pd.Series(idx).iloc[0])[:10],'last',str(pd.Series(idx).iloc[-1])[:10])
    na=F.isna().sum(); na=na[na>0]; print(' cols with NaN:',na.to_dict())
    for c in ['SHV_THB','RF_BOT','SHV_USD','USDTHB','Gold_THB','TDEX_THB','MSCI_ACWI']: print('  has',c,c in F.columns)
    if na.size:
        r=F[F[na.index].isna().any(axis=1)]; print('  NaN rows at:',[str(x)[:10] for x in (r.index if 'date' not in F.columns else r['date'])])
pm=pd.read_parquet(B+'panel_monthly.parquet'); print('panel_monthly date min',str(pm.date.min())[:10])
kw2=['ASEAN','ASIA','VIET','INDO','EM']
print('E base names ASEAN/ASIA/VIET/INDO:',sorted([x for x in Eb if any(k in x.upper() for k in kw2[:4])]))
