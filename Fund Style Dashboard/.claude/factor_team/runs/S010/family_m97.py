"""S010 · family m = 97 (BH / BY) แสดงครบ 97 ช่อง — งานแก้ตามรีวิวผล S010 ข้อ S1
ใช้: ./.venv/bin/python .claude/factor_team/runs/S010/family_m97.py [--out DIR]

- ไม่รันการศึกษา · ไม่เขียน trials.csv (อ่านอย่างเดียว) · ไม่มีเวลา/สุ่มใน csv → รันซ้ำได้ทุกบิต
- ลำดับ family = ORDER97 ของ run.py: run.py ทำงานทันทีตอน import (ไม่มี main guard) จึง import ตรงๆ ไม่ได้ →
  สคริปต์นี้ดึง **ข้อความ** ช่วงนิยาม XS … ORDER17 ออกจาก run.py แล้ว exec (ไม่คัดลอกนิยาม)
- BH / BY = `p2.bh_families` (→ `tests_stat.bh` / `l2.by`) ตัวเดียวกับ run.py · p ของช่องที่ไม่ได้รัน = 1 (spec)
- สองกรณี: (ก) p_J1 = 1 (ตอนตัดสิน trial เดี่ยว · S011 ข้อ 3) · (ข) p_J1 จริง (J1 และ J1.S1–S4 ใช้ p จริง)
"""
import hashlib
import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
TEAM = HERE.parents[1]
sys.path.insert(0, str(TEAM / "lib"))
import p2  # noqa: E402

ARGS = sys.argv[1:]
OUT = Path(ARGS[ARGS.index("--out") + 1]) if "--out" in ARGS else HERE
OUT.mkdir(parents=True, exist_ok=True)
Q = 0.10
RUN_DIR = "runs/S010"

# ── ลำดับ family จาก run.py (ข้อความช่วง XS … ORDER17) ──
src = (HERE / "run.py").read_text(encoding="utf-8")
a = src.index("XS = [")
b = src.index("ORDER17 = SLOTS_MAIN + COND")
b = src.index("\n", b)
NS = {"M_B": 97, "M_A": 17}
exec(src[a:b] + "\n", NS)  # noqa: S102  (ไฟล์ของทีมเอง)
ORDER97, ORDER17 = NS["ORDER97"], NS["ORDER17"]
SLOTS_MAIN, COND, SLOTS_ROB, SLOTS_COND_ROB = NS["SLOTS_MAIN"], NS["COND"], NS["SLOTS_ROB"], NS["SLOTS_COND_ROB"]
assert len(ORDER97) == 97 and len(set(ORDER97)) == 97 and len(ORDER17) == 17
J1_NAMES97 = {"P2-J1"} | {f"P2-J1.S{i}" for i in range(1, 5)}

# ── p จาก trials.csv (เฉพาะ run_dir = runs/S010) ──
tr = pd.read_csv(TEAM / "trials.csv")
tr = tr[tr["run_dir"] == RUN_DIR]
assert tr["trial_id"].is_unique and len(tr) == 67
PMAP = {r.trial_id: (float(r.p_two) if np.isfinite(r.p_two) else 1.0) for r in tr.itertuples()}
assert set(PMAP) <= set(ORDER97)
RAN = {s: (s in PMAP) for s in ORDER97}
P_REAL = np.array([PMAP.get(s, 1.0) for s in ORDER97], float)  # ช่องไม่ได้รัน = 1
P_J1EQ1 = np.array([1.0 if s in J1_NAMES97 else p for s, p in zip(ORDER97, P_REAL)], float)


def role(s):
    if s in SLOTS_MAIN:
        return "main"
    if s in COND or s in SLOTS_COND_ROB:
        return "conditional"
    assert s in SLOTS_ROB
    return "robustness"


def label(s):
    # คอลัมน์ robustness (รวม robustness ของช่องเงื่อนไข) = ไม่ใช้ตัดสิน (S010 ข้อ 4.5)
    return "robustness · ไม่ใช้ตัดสิน" if (s in SLOTS_ROB or s in SLOTS_COND_ROB) else ""


def scenario(p, tag):
    p = np.asarray(p, float)
    m = len(p)
    order = np.argsort(p, kind="stable")
    rank = np.empty(m, int)
    rank[order] = np.arange(1, m + 1)
    bh, adj = p2.bh_families(p, "bh", Q)
    by, _ = p2.bh_families(p, "by", Q)
    return pd.DataFrame({f"p_{tag}": p, f"rank_{tag}": rank, f"BH_threshold_{tag}": rank * Q / m, f"BH_adj_p_{tag}": adj,
                         f"BH_reject_m97_{tag}": bh, f"BY_reject_m97_{tag}": by})


A = scenario(P_J1EQ1, "J1eq1")
B = scenario(P_REAL, "J1real")
base = pd.DataFrame({"slot": ORDER97, "trial_id": ORDER97, "role": [role(s) for s in ORDER97], "ran": [RAN[s] for s in ORDER97],
                     "label": [label(s) for s in ORDER97]})
df = pd.concat([base, A, B], axis=1)
# เกณฑ์ BH รวมลำดับเดียวกับ rank → threshold_J1eq1 / threshold_J1real อยู่ในคอลัมน์ BH_threshold_*
df.to_csv(OUT / "family_m97.csv", index=False, float_format="%.12g", lineterminator="\n")

# ── ตรวจเทียบกับรีวิว (assert → ล้มทันทีถ้าไม่ตรง) ──
ps = np.sort(P_REAL)
rej_names = {tag: sorted(df.loc[df[f"BH_reject_m97_{tag}"], "slot"]) for tag in ("J1eq1", "J1real")}
by_names = {tag: sorted(df.loc[df[f"BY_reject_m97_{tag}"], "slot"]) for tag in ("J1eq1", "J1real")}
r17 = np.array([PMAP.get(s, 1.0) for s in ORDER17], float)
r17_j1eq1 = np.array([1.0 if s in {"P2-J1"} else p for s, p in zip(ORDER17, r17)], float)
bh17, _ = p2.bh_families(r17, "bh", Q)
bh17b, _ = p2.bh_families(r17_j1eq1, "bh", Q)
by17, _ = p2.bh_families(r17, "by", Q)
# กรณีที่ R5 ทุกตัว p = 1
P_R5_1 = np.array([1.0 if s.endswith(".R5") else p for s, p in zip(ORDER97, P_J1EQ1)], float)
bh_r5, _ = p2.bh_families(P_R5_1, "bh", Q)
by_r5, _ = p2.bh_families(P_R5_1, "by", Q)
c1 = df[df["slot"] == "P2-C1.R5"].iloc[0]
checks = dict(
    n_slots=len(df), n_ran=int(df["ran"].sum()), n_main=int((df["role"] == "main").sum()), n_conditional=int((df["role"] == "conditional").sum()),
    n_robustness=int((df["role"] == "robustness").sum()),
    smallest_p=[(s, float(p)) for s, p in sorted(PMAP.items(), key=lambda kv: kv[1])[:4]],
    C1R5_p=float(c1["p_J1eq1"]), C1R5_rank=int(c1["rank_J1eq1"]), C1R5_BH_threshold=float(c1["BH_threshold_J1eq1"]),
    BH_reject_m97_J1eq1=rej_names["J1eq1"], BH_reject_m97_J1real=rej_names["J1real"],
    BY_reject_m97_J1eq1=by_names["J1eq1"], BY_reject_m97_J1real=by_names["J1real"],
    BH_reject_m17_J1real=[s for s, r in zip(ORDER17, bh17) if r], BH_reject_m17_J1eq1=[s for s, r in zip(ORDER17, bh17b) if r],
    BY_reject_m17=[s for s, r in zip(ORDER17, by17) if r],
    all_R5_p1_BH_reject=[s for s, r in zip(ORDER97, bh_r5) if r], all_R5_p1_BY_reject=[s for s, r in zip(ORDER97, by_r5) if r],
)
(OUT / "family_m97_check.json").write_text(json.dumps(checks, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
assert checks["C1R5_p"] == 0.001 and checks["C1R5_rank"] == 1 and abs(checks["C1R5_BH_threshold"] - 0.10 / 97) < 1e-15
assert rej_names["J1eq1"] == ["P2-C1.R5"] and rej_names["J1real"] == ["P2-C1.R5"], rej_names
assert not by_names["J1eq1"] and not by_names["J1real"], by_names
assert not checks["BH_reject_m17_J1real"] and not checks["BH_reject_m17_J1eq1"] and not checks["BY_reject_m17"]
assert not checks["all_R5_p1_BH_reject"] and not checks["all_R5_p1_BY_reject"]
# เทียบกับ verdict.csv (ผลจาก run.py เดิม · อ่านอย่างเดียว) บน 17 ช่องหลัก
vd = pd.read_csv(HERE / "verdict.csv").set_index("slot")
for s in ORDER17:
    if s in vd.index and bool(vd.loc[s, "ran"]):
        i = ORDER97.index(s)
        assert bool(vd.loc[s, "BH_reject_m97"]) == bool(df.loc[i, "BH_reject_m97_J1eq1"]), s
        assert bool(vd.loc[s, "BY_reject_m97"]) == bool(df.loc[i, "BY_reject_m97_J1eq1"]), s
print("OK · BH m=97 ปฏิเสธ:", rej_names, "· BY:", by_names)
print("sha256(family_m97.csv) =", hashlib.sha256((OUT / "family_m97.csv").read_bytes()).hexdigest())
