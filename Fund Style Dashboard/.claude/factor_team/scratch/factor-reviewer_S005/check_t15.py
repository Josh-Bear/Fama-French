import numpy as np, io_l1, l2, forms
from samples import window_mask
R=io_l1.load_returns("W"); U=io_l1.load_universe().set_index("FundCode")
S=l2.fund_sets(R,U,io_l1.load_dup_pairs())
L={k:forms.build_line1(R,S["bal"],S["base"],kstar=k,n_perm=20) for k in (3,4,5)}
a3,a4,a5=(L[k]["forms"]["1a"].plain.to_numpy() for k in (3,4,5))
full=R[S["bal"]].notna().all(axis=1).to_numpy()
mte=window_mask(R.index,"test"); mtr=window_mask(R.index,"train")
d=np.abs(a3-a4[:,:3]); nf=~full&np.isfinite(d).all(1)
print("nonfull rows",nf.sum(),"in test",(nf&mte).sum(),"in train",(nf&mtr).sum())
sd=np.nanstd(a4[:,:3],0)
print("max diff/sd in nonfull rows per col",np.nanmax(d[nf],0)/sd, "median",np.nanmedian(d[nf],0)/sd)
for j in range(3): print("corr k3 vs k4 col",j,np.corrcoef(a3[nf,j],a4[nf,j])[0,1])
d5=np.abs(a5[:,:4]-a4); print("k5 vs k4 max/sd",np.nanmax(d5[nf],0)/np.nanstd(a4,0))
print("missing per nonfull row median",np.median(R[S["bal"]].isna().sum(1).to_numpy()[nf]), "bal n",len(S["bal"]))
