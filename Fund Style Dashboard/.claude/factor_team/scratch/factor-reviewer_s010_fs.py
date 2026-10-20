"""reviewer — future-scramble เพิ่มบนข้อมูลจริง (แก้บั๊กของ reviewer เอง: สุ่มเฉพาะแถว > t ทุกตัวแปร รวม AUM)"""
import sys, json, math
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, ".claude/factor_team/lib")
import p2
src = Path(".claude/factor_team/runs/S010/run.py").read_text().split("if SIM:")[0]
ns = {}
exec("import numpy as np, pandas as pd\nimport io_l1, l4, p2\nfrom pathlib import Path\nROOT = Path('.').resolve()\n" + src[src.index("def load_real():"):], ns)
INP, _ = ns["load_real"]()
DQ = p2.decision_dates(INP.R.index, "Q")
rng = np.random.default_rng(7)
out = {}
for j in (1, 13):
    t = DQ.iloc[j].t
    def scr(X, pos=False):
        X = X.copy(); m = X.index > t
        V = rng.standard_normal((int(m.sum()), X.shape[1])) * 0.03
        if pos: V = np.abs(V) * 1e9
        V[rng.random(V.shape) < 0.2] = np.nan
        X.loc[m] = V
        return X
    Zs = INP.Z.copy(); Zs.loc[Zs.index > t] = (rng.random(Zs.loc[Zs.index > t].shape) < 0.5).astype(float)
    INP2 = p2.Inputs(scr(INP.R), Zs, scr(INP.F3), scr(INP.AUM, True), INP.meta)
    a = b = None
    for jj in range(j + 1):
        tp = int(DQ.iloc[jj].t_pos)
        a = p2.state_at(INP, tp, a, None); b = p2.state_at(INP2, tp, b, None)
    cols = {c: bool(np.array_equal(a["sig"][c].to_numpy(float), b["sig"][c].to_numpy(float), equal_nan=True)) for c in a["sig"].columns}
    out[str(t.date())] = dict(U=a["U"] == b["U"], S=a["S"] == b["S"], sig_cols=cols, Lam_al=bool(np.array_equal(a["Lam_al"], b["Lam_al"])),
                             f_le=bool(np.array_equal(a["f_le"], b["f_le"], equal_nan=True)), B1=bool(np.array_equal(np.r_[a["B1_al"][0], a["B1_al"][1]], np.r_[b["B1_al"][0], b["B1_al"][1]])),
                             reps=a["reps"] == b["reps"], coef=bool(np.array_equal(a["fit_e"].coef, b["fit_e"].coef, equal_nan=True)))
    # target ต้องเปลี่ยนเมื่อแถวในไตรมาสเป้าหมายเปลี่ยน (sanity) และไม่เปลี่ยนเมื่อสุ่มเฉพาะแถว > e
    r = DQ.iloc[j]
    tA = p2.target_at(INP, a, int(r.e_pos), int(r.n_q))["df"]["T_PCA"].to_numpy()
    e = INP.R.index[int(r.e_pos)]
    R3 = INP.R.copy(); m = R3.index > e; R3.loc[m] = rng.standard_normal((int(m.sum()), R3.shape[1]))
    F33 = INP.F3.copy(); F33.loc[F33.index > e] = rng.standard_normal((int((F33.index > e).sum()), F33.shape[1]))
    tB = p2.target_at(p2.Inputs(R3, INP.Z, F33, INP.AUM, INP.meta), a, int(r.e_pos), int(r.n_q))["df"]["T_PCA"].to_numpy()
    out[str(t.date())]["target_unchanged_after_e"] = bool(np.array_equal(tA, tB, equal_nan=True))
print(json.dumps(out, indent=1, ensure_ascii=False))
json.dump(out, open(".claude/factor_team/scratch/factor-reviewer_s010_fs.json", "w"), indent=1, ensure_ascii=False)
