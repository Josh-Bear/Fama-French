import sys
sys.path.insert(0,".claude/factor_team/lib"); sys.path.insert(0,".claude/factor_team/lib/tests")
import p2, math, numpy as np
from test_p2 import make_inputs
inp = make_inputs(N=120, T=260, seed=3)
D = p2.decision_dates(inp.R.index, "Q")
for var in ("W1","W2","W3"):
    prev=None; sts=[]
    for r in D.itertuples():
        prev = p2.state_at(inp, r.t_pos, prev, var); sts.append(prev)
    tgs=[p2.target_at(inp, st, r.e_pos, r.n_q) for st,r in zip(sts,D.itertuples())]
    print(var, [s["k"] for s in sts][:4], np.nanmean([tg["B1_al"][1] for tg in tgs]), tgs[3]["df"].shape)
