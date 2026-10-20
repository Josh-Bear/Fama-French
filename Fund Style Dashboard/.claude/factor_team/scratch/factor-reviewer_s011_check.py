"""S011 short review — โครงเท่านั้น (notna · ชื่อกอง) · ไม่อ่านค่าผลตอบแทน"""
import json, re, numpy as np, pandas as pd
T = '.claude/factor_team/'
P = pd.read_parquet(T + 'data/panel_weekly.parquet', columns=['date', 'FundCode', 'ret'])
M = P.assign(ok=P['ret'].notna()).pivot(index='date', columns='FundCode', values='ok').fillna(False).astype(bool); del P
M = M.loc['2021-01-08':'2025-12-26']; idx = M.index; pos = np.arange(len(idx))
FP = pd.read_csv('base_data/FundProfile.csv', dtype=str, encoding='utf-8-sig')
FPp = FP[FP['Fund Code'].isin(M.columns)]
o = {'fp_rows_per_panel_fund_max': int(FPp.groupby('Fund Code').size().max()),
     'panel_funds_with_multiple_distinct_EN': int((FPp.groupby('Fund Code')['Fund Name EN'].nunique() > 1).sum())}
en = FPp.groupby('Fund Code')['Fund Name EN'].apply(lambda s: any(re.search('gold', str(x), re.I) for x in s))
th = FPp.groupby('Fund Code')['Fund Name TH'].apply(lambda s: any('ทองคำ' in str(x) for x in s))
gold = sorted(en.index[en | th]); o['n_gold_rule'] = len(gold); o['gold'] = gold
o['golden_hits'] = sorted(c for c in FPp['Fund Code'].unique() if re.search('golden', str(FPp.loc[FPp['Fund Code'] == c, 'Fund Name EN'].iloc[0]), re.I))
o['th_only'] = sorted(set(th.index[th]) - set(en.index[en]))
U = pd.read_csv(T + 'data/universe.csv').set_index('FundCode')
qe = pd.date_range('2022-03-31', '2025-12-31', freq='QE-DEC'); dec = [idx[idx <= q][-1] for q in qe]
rows = []
for a, b in zip(dec[:-1], dec[1:]):
    le = idx <= a
    dim = M.loc[le & (pos >= 1)].sum(0)
    e52 = set(dim[dim >= 52].index)
    at_t = set(M.columns[M.loc[a]])
    before = set(M.columns[M.loc[le].any()]); after = set(M.columns[M.loc[idx > a].any()])
    hole_t = sorted((e52 & before & after) - at_t)          # มีข้อมูลก่อนและหลัง t แต่ไม่มีที่แถว t
    bal = M.loc[le].all(0); bal = set(bal[bal].index)
    rows.append(dict(t=str(a.date()), elig52=len(e52), u0_removed=len(e52 - at_t), hole_at_t_alive=len(hole_t),
                     gold_cut=len((e52 & at_t) & set(gold)), gold_in_balanced=len(bal & set(gold)), gold_bal=sorted(bal & set(gold))))
o['by_q'] = rows
json.dump(o, open(T + 'scratch/factor-reviewer_s011_check.json', 'w'), ensure_ascii=False, indent=1)
print(json.dumps({k: v for k, v in o.items() if k != 'by_q'}, ensure_ascii=False))
for r in rows: print(r)
