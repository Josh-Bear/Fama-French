"""reviewer: ตรวจ rolling_104 ของ S005 (ส่วนเล็ก) · อ่านอย่างเดียว ไม่เขียน runs/"""
import sys, json
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path("/Users/doyinratnavardhana/Fama French/Fund Style Dashboard/.claude/factor_team")
sys.path.insert(0, str(ROOT / "lib"))
import io_l1, l2, regress as rg, scorecard as sc
from samples import window_mask
R = io_l1.load_returns("W"); F = io_l1.load_factors("W")
U = io_l1.load_universe().set_index("FundCode"); pol = U["policy"]
idx = R.index; POS = np.arange(len(idx))
print("R rows", len(idx), idx[0].date(), idx[-1].date())
S = l2.fund_sets(R, U, io_l1.load_dup_pairs())
EVAL, STAB = S["EVAL"], S["STAB"]
print("STAB", len(STAB), "STAB not in EVAL", [c for c in STAB if c not in set(EVAL)])
fullm = window_mask(idx, "full") & (POS >= 1)
print("full rows", fullm.sum(), "first True pos", np.argmax(fullm), "last pos", np.where(fullm)[0][-1])
FR = l2.load_l1_factors(ROOT / "runs/S003/factors_S003_weekly.parquet", "1a")
I, blocks = l2.index_set(F); M28 = I[blocks["M28"]]
pi = pd.read_csv(ROOT / "runs/S005/primary_index.csv"); pi = pi[pi.form == "1a@4"].set_index("FundCode")["index"]
sp_stab = pol[STAB].to_numpy()
CSV = pd.read_csv(ROOT / "runs/S005/rolling_104.csv")
out = {}
for name, prov in (("ฐาน 1a", rg.CommonFactors(FR)), ("L2-1", l2.AugmentedFactors(FR, per_fund={c: M28[pi[c]] for c in EVAL}))):
    bw, bfull, starts = l2.rolling_betas(R, prov, STAB, fullm)
    print(name, "windows", len(starts), "window rows (first,last)", [int((np.r_[np.zeros(s,bool), np.ones(104,bool), np.zeros(max(0,len(idx)-s-104),bool)][:len(idx)] & fullm).sum()) for s in (starts[0], starts[-1])])
    nfin = np.isfinite(bw[:, :, 0]).sum(1)
    print(" funds with β per window min/max", nfin.min(), nfin.max(), "full finite", int(np.isfinite(bfull[:, 0]).sum()))
    for g in ("E", "ALL"):
        sel = (sp_stab == g) if g != "ALL" else np.ones(len(STAB), bool)
        med, mn = sc.stability_rolling(bw[:, sel, :], bfull[sel])
        ref = CSV[(CSV.model == name) & (CSV.key == "1a@4") & (CSV.policy == g)].set_index("factor")
        d = max(abs(med[k] - ref.loc[f, "roll_median"]) + abs(mn[k] - ref.loc[f, "roll_min"]) for k, f in enumerate(prov.names))
        print(" ", g, "max|diff| vs CSV", d)
        # window-specific: corr in window 0 (train only) vs last (test-heavy)
        cs = np.array([[sc._corr(bw[w, sel, k], bfull[sel, k]) for k in range(len(prov.names))] for w in range(len(starts))])
        print("   corr first window", np.round(cs[0], 3), "last window", np.round(cs[-1], 3))
    # ความถ่วงจากการทับซ้อน: เทียบ window แรก vs window สุดท้าย (ไม่ทับกัน: s=0 vs s=156)
    sel = sp_stab == "E"
    cnon = [sc._corr(bw[0, sel, k], bw[-1, sel, k]) for k in range(len(prov.names))]
    print("  E: corr β window[0] vs window[-1] (ไม่ทับกัน)", np.round(cnon, 3))
