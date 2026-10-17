"""factor-reviewer — ④a ที่ k_res 1..5 (IC ชน kmax) · ความคาดหมาย 9b (α hedge vs ไม่ hedge ของ ③a)"""
import sys
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))
import io_l1, samples as sp, regress as rg, forms as fm_, external as ex  # noqa
from samples import window_mask  # noqa
R = io_l1.load_returns("W"); F = io_l1.load_factors("W")
U = io_l1.load_universe().set_index("FundCode"); pol = U["policy"]
keep = sp.dedup_keep(io_l1.load_dup_pairs(), U.loc[R.columns, "n_weeks"])
bal = sp.eligible(R, "balanced", keep); EVAL = sorted(sp.eligible(R, "EVAL", keep)); STAB = sp.eligible(R, "STAB", keep)
idx = R.index; POS = np.arange(len(idx)); mtr, mte = window_mask(idx, "train"), window_mask(idx, "test")
polE = (pol.loc[EVAL] == "E").to_numpy(); stE = [c for c in STAB if pol[c] == "E"]
F3a = ex.line3(F, "3a")
p3 = rg.CommonFactors(F3a); f3 = rg.fit_funds(R, p3, mtr, 52, funds=EVAL)
bic3 = np.asarray(f3.bic, float) if hasattr(f3, "bic") else None
for km in (1, 2, 3, 4, 5):
    l4 = fm_.build_line4(R, F3a, bal, kmax=km)
    prov = l4["form"].provider
    fit = rg.fit_funds(R, prov, mtr, 52, funds=EVAL)
    oo = np.asarray(rg.oos_r2_funds(R, prov, fit, mte), float); r2 = np.asarray(fit.r2, float)
    h1 = rg.fit_funds(R, prov, window_mask(idx, "H1") & (POS >= 1), 104, funds=stE)
    h2 = rg.fit_funds(R, prov, window_mask(idx, "H2"), 104, funds=stE)
    rr = [pd.Series(h1.beta[:, j]).corr(pd.Series(h2.beta[:, j])) for j in range(prov.K)]
    db = np.nanmedian((np.asarray(fit.bic, float) - bic3)[polE]) if bic3 is not None else np.nan
    print(f"kmax={km} k_res={l4['rp']['k_res']}: r2oos_E={np.nanmedian(oo[polE]):.3f} gap_E={np.nanmedian((r2 - oo)[polE]):.3f} "
          f"adj_E={np.nanmedian(np.asarray(fit.adj_r2)[polE]):.3f} r_raw_E={np.mean(rr):.3f} dBIC_vs_3a_E={db:.1f}")
# 9b
fl = pd.read_csv(ROOT / "runs/S003/fund_level.csv"); gp = pd.read_csv(ROOT / "runs/S003/grs_ports.csv")
a = fl[(fl.form == "3a") & (fl.in_EVAL == True)].merge(gp[gp.port_set == "full"], on="FundCode")
print(a.groupby("port").alpha.agg(lambda x: x.mean() * 52 * 100).round(2).to_string())
