"""factor-reviewer r2 — คำนวณ α ระดับพอร์ต 9b ของ ③a ซ้ำ"""
import sys
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT / "lib"))
import io_l1, regress as rg, external as ex  # noqa
from samples import window_mask  # noqa
R = io_l1.load_returns("W"); F = io_l1.load_factors("W")
gp = pd.read_csv(ROOT / "runs/S003/grs_ports.csv"); gp = gp[gp.port_set == "full"]
D = rg.dimson_design(ex.line3(F, "3a")).to_numpy(float)
mk = window_mask(R.index, "train") & np.isfinite(D).all(1)
X = np.column_stack([np.ones(mk.sum()), D[mk]])
for p, g in gp.groupby("port"):
    if not p.startswith("E_"): continue
    y = R.loc[mk, list(g.FundCode)].mean(axis=1, skipna=True).to_numpy()
    a = np.linalg.lstsq(X, y, rcond=None)[0][0] * 52 * 100
    print(f"{p:40s} n={len(g):3d} alpha={a:8.3f}")
