import pandas as pd, numpy as np, json
R="/Users/doyinratnavardhana/Fama French/Fund Style Dashboard/.claude/factor_team/runs/S005/"
pls=pd.read_csv(R+"placebo_summary.csv")
for k in (3,4,5):
    g=pls[pls.k==k]; print("k",k,"R0",g.frac_p05.max(),"R1",g.frac_padj05.max())
ss=pd.read_csv(R+"scan_single.csv")
fc=pd.read_csv(R+"fund_clusters.csv"); print("groups",fc.group_id.nunique(),"max",fc.group_size.max(), "n",len(fc))
s4=ss[ss.key.isin(["1a@4"])]
print("cols sig_chosen==BH_padj?", (s4.sig_chosen==s4.BH_padj).all())
for key in ["1a@4","1c@4"]:
    s=ss[ss.key==key]; anys=s.groupby("FundCode").sig_chosen.any()
    print(key,"frac_any_sig",anys.mean(),len(anys), "pairs sig frac",s.sig_chosen.mean(), "n pairs",len(s))
    h=s[s["index"]=="MSCI_ACWI_HC"]; sig=h[h.sig_chosen]
    print(" HC funds",len(sig),"groups",fc.set_index("FundCode").loc[sig.FundCode].group_id.nunique(),"medDr2oos_sig",sig.d_r2_oos.median(),"med all",h.d_r2_oos.median())
# placebo null: per fund any BH sig (p_adj) under placebo
ps=pd.read_csv(R+"placebo_scan.csv")
from statsmodels.stats.multitest import multipletests
for (key,sh),g in ps[ps.key.isin(["1a@4","1c@4"])].groupby(["key","shift"]):
    g=g[np.isfinite(g.p_adj)]
    rej=multipletests(g.p_adj,0.10,"fdr_bh")[0]
    print("placebo",key,sh,"funds any BH",g.FundCode[rej].nunique()/g.FundCode.nunique(), "raw any p_adj<.05", (g.assign(r=g.p_adj<0.05).groupby("FundCode").r.any()).mean())
sbi=pd.read_csv(R+"scan_by_index.csv")
r=sbi[(sbi.key=="1a@4")&(sbi["index"]=="MSCI_ACWI_HC")].iloc[0]; print(r[["n_funds_sig","n_groups_sig","n_BH_padj","med_d_r2_oos_all","med_d_r2_oos_primary"]].to_dict())
sc=pd.read_csv(R+"scorecard.csv"); print(sc[(sc.model=="L2-1")&(sc.set=="EVAL")][["policy","adjr2_med","med_d_r2_oos","med_d_bic"]])
py=pd.read_csv(R+"py.csv"); print(py[["model","window","J","p","p_boot","size05"]].head(4))
