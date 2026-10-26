"""factor-reviewer · diagnostic: exposure / Euler share ของไตรมาส 2025 แบบ P-A (DAOL-GOLD + GOLD_XS) เทียบชุดหลัก · ใช้ฟังก์ชันของ lib · อ่านอย่างเดียว"""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
T = Path(".claude/factor_team"); sys.path.insert(0, str(T / "lib"))
import io_l1, l1eo, port  # noqa
F = io_l1.load_factors("W"); Fext = l1eo.load_ext("W"); Feo = port.load_eo_noaqr("W")
R = io_l1.load_returns("W"); FR = port.factor_frames(F, Fext, Feo)
H = port.load_m052(); MPI = pd.read_csv(T / "runs/S014/mapping_codes.csv").set_index("FundCode")
out = {}
for t in ("2025-03-31", "2025-06-30", "2025-09-30", "2022-06-30", "2022-09-30", "2022-12-30"):
    t = pd.Timestamp(t); r = {}
    for v in ("main", "PA"):
        qf = port.quarter_fit(R, FR, t, H[H["t"] == t].reset_index(drop=True), MPI, v)
        Sig, _ = port.sigma_f(qf); B, _, w, s2 = port.exposure(qf); d = port.var_decomp(B, Sig, w, s2)
        r[v] = {"B": {c: round(float(B[k]), 3) for k, c in enumerate(qf["names"])}, "share": {c: round(float(d["share"][k]), 3) for k, c in enumerate(qf["names"])},
                "share_eps": round(d["share_eps"], 3), "top": qf["names"][int(np.argmax(np.abs(d["share"])))]}
    out[str(t.date())] = r
json.dump(out, open(T / "scratch/factor-reviewer_s014_pa_conc.json", "w"), indent=1, ensure_ascii=False)
for t, r in out.items():
    print(t, "| main top", r["main"]["top"], "B_FX", r["main"]["B"].get("FX"), "sFX", r["main"]["share"].get("FX"), "sGOLD", r["main"]["share"].get("GOLD_XS"), "| PA top", r["PA"]["top"], "B_FX", r["PA"]["B"].get("FX"), "sFX", r["PA"]["share"].get("FX"), "sGOLD", r["PA"]["share"].get("GOLD_XS"), "B_GOLD", r["PA"]["B"].get("GOLD_XS"), "sTDEX", r["PA"]["share"].get("TDEXX"), "B_CMA", r["PA"]["B"].get("CMA"))
