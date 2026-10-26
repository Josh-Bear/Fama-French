"""addendum S1 (รีวิวผล S014 · BRIEF 124): คำนวณซ้ำตาราง diagnostic การกระจุกแบบ P-A และตารางเทียบชุดหลัก/P-A ของ A · A+E · ลำดับ factor
โดยโหลดข้อมูลเองแล้วเรียก port.quarter_fit(..., 'main' / 'PA') + sigma_f / exposure / var_decomp → addendum_s1.csv · เทียบกับ concentration_PA.csv และ attribution_summary.csv ที่ run.py เขียน
→ addendum_s1_check.json (บันทึก sha256 ของ run.py · สคริปต์นี้ · port.py)   ใช้ (จาก root): PYTHONPATH=. ./.venv/bin/python .claude/factor_team/runs/S014/addendum_s1.py [--out DIR]"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
TEAM = HERE.parents[1]
sys.path.insert(0, str(TEAM / "lib"))
import io_l1  # noqa: E402
import l1eo  # noqa: E402
import port  # noqa: E402

OUT = Path(sys.argv[sys.argv.index("--out") + 1]) if "--out" in sys.argv else HERE
port.check_pins()
H = port.load_m052()
universe = pd.read_csv(TEAM / "data" / "universe.csv").set_index("FundCode")
gmap = l1eo.load_group_map()
profile = pd.read_csv(io_l1.ROOT / "base_data" / "FundProfile.csv", encoding="utf-8-sig", low_memory=False,
                      usecols=["Fund Code", "Fund Name EN", "FX Risk Flag"]).drop_duplicates("Fund Code").set_index("Fund Code")
MPI = port.map_holdings(H, universe, gmap, profile).set_index("FundCode")
F = io_l1.load_factors("W")
FR = port.factor_frames(F, l1eo.load_ext("W"), port.load_eo_noaqr("W"))
R = io_l1.load_returns("W")
rows = []
for t in sorted(H["t"].unique()):
    hold = H[H["t"] == t].reset_index(drop=True)
    r = dict(t=t.date())
    for lab, v in (("main_", "main"), ("PA_", "PA")):
        qf = port.quarter_fit(R, FR, t, hold, MPI, v)
        B, seB, wv, s2 = port.exposure(qf)
        Sig, nS = port.sigma_f(qf)
        d = port.var_decomp(B, Sig, wv, s2)
        nm = qf["names"]
        sh = dict(zip(nm, d["share"]))
        top = nm[int(np.argmax(np.abs(d["share"])))]
        r.update({lab + "top": top, lab + "top_share": float(sh[top]), lab + "B_MKT": float(B[nm.index("MKT")]) if "MKT" in nm else 0.0, lab + "B_FX": float(B[nm.index("FX")]),
                  lab + "B_GOLD_XS": float(B[nm.index("GOLD_XS")]) if "GOLD_XS" in nm else 0.0, lab + "share_MKT": float(sh.get("MKT", 0.0)), lab + "share_FX": float(sh["FX"]),
                  lab + "share_GOLD_XS": float(sh.get("GOLD_XS", 0.0)), lab + "share_eps": float(d["share_eps"])})
    rows.append(r)
A = pd.DataFrame(rows)
A.to_csv(OUT / "addendum_s1.csv", index=False)
C = pd.read_csv(OUT / "concentration_PA.csv")
num = [c for c in A.columns if c not in ("t", "main_top", "PA_top")]
mx = float(np.nanmax(np.abs(A[num].to_numpy(float) - C[num].to_numpy(float))))
tops_same = bool((A["main_top"] == C["main_top"]).all() and (A["PA_top"] == C["PA_top"]).all())
S = pd.read_csv(OUT / "attribution_summary.csv")
sm = S[(S.period == "ทั้งช่วง (2022-04 → 2025-12)") & S.lens.isin(["L1", "L1_PA"]) & S.component.isin(["A", "E"])].pivot(index="component", columns="lens", values="value")
chk = dict(max_abs_diff_vs_concentration_PA=mx, top_labels_equal=tops_same, identical=bool(mx <= 1e-12 and tops_same),
           AE_all_period_pp=dict(main=float((sm.loc["A", "L1"] + sm.loc["E", "L1"]) * 100), PA=float((sm.loc["A", "L1_PA"] + sm.loc["E", "L1_PA"]) * 100)),
           run_py_sha256=io_l1.sha256_file(HERE / "run.py"), addendum_script_sha256=io_l1.sha256_file(Path(__file__)), port_py_sha256=io_l1.sha256_file(TEAM / "lib" / "port.py"))
(OUT / "addendum_s1_check.json").write_text(json.dumps(chk, indent=1, ensure_ascii=False))
print(chk)
