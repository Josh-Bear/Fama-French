"""addendum S1 (รีวิวผล S012 · BRIEF 118(1)): ตารางมุมจับคู่รายกองของ Q-E1 / Q-E2 — คำนวณซ้ำจาก fund_level_E.csv + eval_clusters.csv
(median ของผลต่างรายกอง · สัดส่วนกองที่แย่ลง/ดีขึ้น · แยกกองมี/ไม่มี factor กลุ่ม · ในชุด/นอกชุด PCA(97) · CI สุ่มกลุ่มกองอิสระ 2,000 รอบ seed 20261015)
แล้วเทียบกับ paired_lens_E.csv ที่ run.py เขียน → addendum_s1.csv + addendum_s1_check.json (บันทึก sha256 ของ run.py และของสคริปต์นี้ · BRIEF 106)
ใช้ (จาก root): PYTHONPATH=. ./.venv/bin/python .claude/factor_team/runs/S012/addendum_s1.py [--out DIR] [--smoke]"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "lib"))
import io_l1  # noqa: E402
import l1eo  # noqa: E402

OUT = Path(sys.argv[sys.argv.index("--out") + 1]) if "--out" in sys.argv else HERE
N = 50 if "--smoke" in sys.argv else 2000
FL = pd.read_csv(OUT / "fund_level_E.csv")
CL = pd.read_csv(OUT / "eval_clusters.csv").set_index("unit")["group_id"]
ev = FL[FL["in_EVAL"]]
r2 = ev.pivot(index="unit", columns="row", values="r2_oos")
meta = ev[ev["row"] == "E-X1"].set_index("unit")[["has_group_factor", "in_PCA97"]]
SUBS = {"EVAL ทั้งหมด": meta.index, "มี factor กลุ่ม": meta.index[meta["has_group_factor"]], "ไม่มี factor กลุ่ม": meta.index[~meta["has_group_factor"]],
        "ในชุด PCA(97)": meta.index[meta["in_PCA97"]], "นอกชุด PCA(97)": meta.index[~meta["in_PCA97"]]}
rows = []
for q, a, b in (("Q-E1 E-X2 − E-PCA-a1", "E-X2", "E-PCA-a1"), ("Q-E2 E-X1 − ③a", "E-X1", "③a")):
    for name, units in SUBS.items():
        xa, xb = r2.loc[list(units), a].to_numpy(float), r2.loc[list(units), b].to_numpy(float)
        ok = np.isfinite(xa) & np.isfinite(xb)
        un = np.array(list(units))[ok]
        xa, xb = xa[ok], xb[ok]
        d = xa - xb
        cl = np.array([CL[u] for u in un])
        bs = l1eo.cluster_bootstrap(lambda i: np.array([np.median(d[i]), np.median(xa[i]) - np.median(xb[i])]), cl, n=N, seed=20261015)
        rows.append(dict(question=q, subset=name, n=int(len(d)), diff_of_medians_locked=float(np.median(xa) - np.median(xb)), ci_lo_dm=bs["lo"][1], ci_hi_dm=bs["hi"][1],
                         median_of_fund_diffs=float(np.median(d)), ci_lo=bs["lo"][0], ci_hi=bs["hi"][0], frac_improved=float(np.mean(d > 0)), frac_worse=float(np.mean(d < 0)),
                         n_improved=int(np.sum(d > 0))))
A = pd.DataFrame(rows)
A.to_csv(OUT / "addendum_s1.csv", index=False)
P = pd.read_csv(OUT / "paired_lens_E.csv")
cols = [c for c in A.columns if c not in ("question", "subset")]
mx = float(np.nanmax(np.abs(A[cols].to_numpy(float) - P[cols].to_numpy(float))))
chk = dict(max_abs_diff_vs_paired_lens_E=mx, identical_to_run_py_table=bool(mx <= 1e-12), n_bootstrap=N,
           run_py_sha256=io_l1.sha256_file(HERE / "run.py"), addendum_script_sha256=io_l1.sha256_file(Path(__file__)), lib_l1eo_sha256=io_l1.sha256_file(HERE.parents[1] / "lib" / "l1eo.py"),
           fund_level_E_sha256=io_l1.sha256_file(OUT / "fund_level_E.csv"))
(OUT / "addendum_s1_check.json").write_text(json.dumps(chk, indent=1, ensure_ascii=False))
print(chk)
