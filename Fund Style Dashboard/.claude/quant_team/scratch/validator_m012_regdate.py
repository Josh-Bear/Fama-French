import pandas as pd, numpy as np
fp = pd.read_csv('base_data/FundProfile.csv', dtype=str, encoding='utf-8-sig')
fp.columns=[c.strip() for c in fp.columns]
nav = pd.read_parquet('cache/nav_clean.parquet')
codes = sorted(nav.FundCode.unique())
print('FundProfile rows', len(fp), 'unique codes', fp['Fund Code'].nunique(), 'dup', fp['Fund Code'].duplicated().sum())
rd = fp[['Fund Code','Registration_date']].drop_duplicates('Fund Code').set_index('Fund Code')['Registration_date']
print('nav classes', len(codes), 'in profile', sum(c in rd.index for c in codes))
r = rd.reindex(codes)
print('missing/blank reg', r.isna().sum(), (r.fillna('').str.strip()=='').sum())
print(r.dropna().str.len().value_counts().to_dict())
p = pd.to_datetime(r, format='%Y%m%d', errors='coerce')
print('parse fail among nonblank', (p.isna() & r.notna()).sum(), 'range', p.min(), p.max())
first = nav.groupby('FundCode').NAVDate.min().reindex(codes)
d = (p - first).dt.days
print('Reg > firstNAV:', (d>0).sum(), 'median gap', d[d>0].median(), 'max', d.max(), ' Reg<=firstNAV', (d<=0).sum())
print('Reg>firstNAV by >365d', (d>365).sum(), ' >730', (d>730).sum())
print('Reg before 2000:', (p<'2000-01-01').sum(), 'Reg in future(>2026-10-06):', (p>'2026-10-06').sum())
# classes where age B differs from A at 2022-03-31 (first<=t-730 ...)
t = pd.Timestamp('2022-03-31')
mn = pd.concat([p.where(p<=t), first.where(first<=t)],axis=1).min(axis=1)
print('classes with first_c <= t-730 at 2022-03-31 (B):', (mn<=t-pd.Timedelta(days=730)).sum(), ' A:', (first<=t-pd.Timedelta(days=730)).sum())
s = pd.DataFrame({'reg':p,'first':first,'gap':d}).dropna()
rng = np.random.default_rng(0)
print(s.sample(5, random_state=1))
# sample: those where reg>first, and where reg<first
print(s[s.gap>0].sample(3, random_state=2)); print(s[s.gap<-365].sample(3,random_state=3))
print('NAV earliest overall', first.min())
