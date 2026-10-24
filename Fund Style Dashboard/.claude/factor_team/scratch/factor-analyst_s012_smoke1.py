import sys, time
sys.path.insert(0, ".claude/factor_team/lib")
import numpy as np, pandas as pd
import io_l1, l1eo, l2, regress as rg
from samples import window_mask
t0=time.time()
F0 = io_l1.load_factors("W"); Feo0 = l1eo.load_eo("W"); Fext0 = l1eo.load_ext("W")
F = l1eo.sim_factors(F0, 1); Feo = l1eo.sim_factors(Feo0, 2); Fext = l1eo.sim_factors(Fext0, 3)
units = [f"E{i:02d}" for i in range(60)] + [f"O{i}" for i in range(6)]
pol = pd.Series({u: ("O" if u.startswith("O") else "E") for u in units})
R = l1eo.sim_returns(units, pol, F, Feo, Fext)
idx = R.index
masks = {n: window_mask(idx, n) for n in ("train","test","H1","H2","full")}; masks["pos1"] = np.arange(len(idx))>=1
mtr, mte = masks["train"], masks["test"]
E = [u for u in units if pol[u]=="E"]
reps, cl = l1eo.sel_reps(R, E, mtr)
print("reps", len(reps), len(cl))
core, pool, coef = l1eo.pool_E(F, Fext, Feo, mtr)
print(pool.shape, list(pool.columns))
ptr = mtr & (idx <= pd.Timestamp("2022-06-24")); pte = mtr & (idx >= pd.Timestamp("2022-07-01"))
rs = l1eo.resid_spec_E(F)
pl = l1eo.placebo_eo(R, core, pool, mtr, list(reps.rep), pseudo=(ptr, pte))
print("placebo", pl["tau"], {k:(v["selected"], v["best_score_round1"]) for k,v in pl["shifts"].items()}, time.time()-t0)
sel, lg, ac = l1eo.stepwise_eo(R, core, pool, mtr, list(reps.rep), tau=pl["tau"], pseudo=(ptr, pte), resid_spec=rs)
print(sel); print(lg.to_string())
X1 = pd.concat([core, pool[sel]], axis=1)
print(time.time()-t0)
