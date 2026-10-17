"""factor-designer · L2_summary หัวข้อ 4 — ชุดเกณฑ์ที่เข้มกว่า (เกณฑ์เปลี่ยนหลังเห็นผล · ค่าชั่วคราวข้อ 44)

คำนวณจาก CSV ที่มีอยู่ใน runs/S005 เท่านั้น — ไม่ fit model ใหม่ ไม่อ่านผลตอบแทน
นิยาม P1(ก)′ (เข้มกว่า): นับเฉพาะกองที่ significant ตามขั้น C.2 (sig_chosen = p_adj + BH)
**และ** ΔR²_oos ของกองนั้น ≥ 0.02 → ต้องได้ ≥ 7 กลุ่มกองอิสระ และ ≥ 7 กอง
(ค่า 7 และ 0.02 = ค่าที่ล็อกใน S005 C.4 / S004 P1(ข) · ไม่มีพารามิเตอร์ใหม่)
P1(ข) ไม่เปลี่ยน (ใช้คอลัมน์ P1b ใน criteria_P1.csv ตามเดิม) · P4′ = ผ่าน P1′ ทั้ง ①a และ ①c ที่ k เดียวกัน

รัน: cd "<root>" && ./.venv/bin/python .claude/factor_team/scratch/factor-designer_L2_strict.py
"""
from pathlib import Path
import hashlib
import json

import numpy as np
import pandas as pd

ROOT = Path(".claude/factor_team")
RUN = ROOT / "runs" / "S005"
OUT = ROOT / "scratch" / "factor-designer_L2_strict_P1.csv"
OUT_SUM = ROOT / "scratch" / "factor-designer_L2_strict_summary.json"
THR_N, THR_D = 7, 0.02


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


cl = pd.read_csv(RUN / "fund_clusters.csv")[["FundCode", "group_id"]]
inputs = {str(RUN / "fund_clusters.csv"): sha(RUN / "fund_clusters.csv")}
rows, base_rates = [], {}

for sub in ["", "appendix_k3", "appendix_k5"]:
    d = RUN / sub if sub else RUN
    for f in ("scan_single.csv", "criteria_P1.csv", "scan_by_index.csv"):
        inputs[str(d / f)] = sha(d / f)
    sc = pd.read_csv(d / "scan_single.csv").merge(cl, on="FundCode", how="left")
    assert sc.group_id.notna().all(), "กองไม่มี group_id"
    sc["sig_chosen"] = sc.sig_chosen.astype(bool)
    p1 = pd.read_csv(d / "criteria_P1.csv").set_index(["key", "index"])
    sbi = pd.read_csv(d / "scan_by_index.csv").set_index(["key", "index"])

    for key, gk in sc.groupby("key"):
        fit = gk[~gk.defn_dup.astype(bool) & gk.d_r2_oos.notna()]
        ge = fit.d_r2_oos >= THR_D
        base_rates[key] = dict(
            n_pairs=int(len(fit)),
            n_sig=int(fit.sig_chosen.sum()),
            frac_ge002_all=float(ge.mean()),
            frac_ge002_sig=float(ge[fit.sig_chosen].mean()),
            frac_ge002_nonsig=float(ge[~fit.sig_chosen].mean()),
        )

    for (key, idx), g in sc.groupby(["key", "index"]):
        if (key, idx) not in p1.index:
            continue  # ซ้ำเชิงนิยาม (ไม่ fit)
        sig = g[g.sig_chosen]
        n_f, n_g = len(sig), sig.group_id.nunique()
        st = sig[sig.d_r2_oos >= THR_D]
        n_fs, n_gs = len(st), st.group_id.nunique()
        r = p1.loc[(key, idx)]
        if pd.isna(r.n_funds_sig):
            continue  # ซ้ำเชิงนิยาม (③b/④a + ACWI/USA) — ไม่ fit
        # ตรวจว่าตัวนับเดิมสร้างซ้ำได้ตรง criteria_P1.csv
        assert int(r.n_funds_sig) == n_f and int(r.n_groups_sig) == n_g, (key, idx)
        b = sbi.loc[(key, idx)]
        p1a_by = bool(b.n_groups_sig_BYsame >= THR_N and b.n_funds_sig_BYsame >= THR_N)
        p1a_s = bool(n_gs >= THR_N and n_fs >= THR_N)
        rows.append(dict(
            key=key, k=int(key.split("@")[1]), index=idx,
            n_funds_sig=n_f, n_groups_sig=n_g,
            P1a=bool(r.P1a), P1b=bool(r.P1b), P1=bool(r.P1),
            med_dR2oos_used=float(r.med_dR2oos_used), label=r.label if isinstance(r.label, str) else "",
            n_funds_sig_oos002=n_fs, n_groups_sig_oos002=n_gs,
            P1a_strict=p1a_s, P1_strict=bool(p1a_s and bool(r.P1b)),
            P1a_BYpadj=p1a_by,
        ))

res = pd.DataFrame(rows).sort_values(["k", "key", "index"], kind="stable")
res.to_csv(OUT, index=False)

summary = {"inputs_sha256": inputs, "thr_n": THR_N, "thr_d": THR_D, "base_rates": base_rates, "per_key": {}, "P4": {}}
for key, g in res.groupby("key"):
    summary["per_key"][key] = dict(
        n_index=int(len(g)),
        P1a_locked=int(g.P1a.sum()), P1a_strict=int(g.P1a_strict.sum()), P1a_BYpadj=int(g.P1a_BYpadj.sum()),
        P1_locked=sorted(g[g.P1]["index"]), P1_strict=sorted(g[g.P1_strict]["index"]),
        dropped=sorted(g[g.P1 & ~g.P1_strict]["index"]),
    )
for k in (3, 4, 5):
    a, c = res[res.key == f"1a@{k}"], res[res.key == f"1c@{k}"]
    lock = sorted(set(a[a.P1]["index"]) & set(c[c.P1]["index"]))
    strict = sorted(set(a[a.P1_strict]["index"]) & set(c[c.P1_strict]["index"]))
    summary["P4"][k] = dict(locked=lock, strict=strict)
# ตรวจ P4 locked สร้างซ้ำตรง criteria_P4.json
for k, sub in ((4, ""), (3, "appendix_k3"), (5, "appendix_k5")):
    j = json.loads(((RUN / sub) if sub else RUN).joinpath("criteria_P4.json").read_text())
    assert sorted(j["pass_both"]) == summary["P4"][k]["locked"], k
OUT_SUM.write_text(json.dumps(summary, ensure_ascii=False, indent=1))
print(json.dumps({k: v for k, v in summary.items() if k != "inputs_sha256"}, ensure_ascii=False, indent=1))
cols = ["key", "index", "n_groups_sig", "n_funds_sig", "n_groups_sig_oos002", "n_funds_sig_oos002",
        "P1a", "P1b", "P1", "P1a_strict", "P1_strict", "P1a_BYpadj", "med_dR2oos_used"]
print(res[res.key.isin(["1a@4", "1c@4"]) & (res.P1 | res.P1_strict)][cols].to_string(index=False))
