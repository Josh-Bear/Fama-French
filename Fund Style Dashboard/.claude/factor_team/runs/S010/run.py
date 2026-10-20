"""S010 run (ระยะ 2 · spec S010 + S011 · ข้อ 102 = B-full · m=97) — เรียก lib เท่านั้น
ใช้: PYTHONPATH=. python run.py [--phase pre|full] [--out DIR] [--no-trials] [--sim]
pre  = ตรวจ sha · universe/S_t ต่อไตรมาส · future-scramble บนข้อมูลจริง 2 จุด (เทียบเท่าเดิม/ไม่เท่าเท่านั้น) · เขียน decisions_pre_run.md · **ไม่คำนวณ target / IC**
full = รัน trial หลัก 12 → ช่องเงื่อนไข (กลไก) → verdict · --no-trials = ไม่ append trials.csv (ใช้กับรันซ้ำลง scratch) · --sim = ข้อมูลจำลอง (debug)"""
import hashlib
import json
import math
import platform
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

LIB = Path(__file__).resolve().parents[2] / "lib"
sys.path.insert(0, str(LIB))
import io_l1  # noqa: E402
import l4  # noqa: E402
import p2  # noqa: E402
import regress as rg  # noqa: E402

ARGS = sys.argv[1:]
PHASE = ARGS[ARGS.index("--phase") + 1] if "--phase" in ARGS else "full"
SIM = "--sim" in ARGS
NO_TRIALS = "--no-trials" in ARGS
OUT = Path(ARGS[ARGS.index("--out") + 1]) if "--out" in ARGS else Path(__file__).resolve().parent
OUT.mkdir(parents=True, exist_ok=True)
T0 = time.time()
LOGF = open(OUT / ("run.log" if PHASE == "full" else "run_pre.log"), "w")
TEAM, ROOT = io_l1.TEAM, io_l1.ROOT
TRIALS = TEAM / "trials.csv" if not SIM else OUT / "trials_sim.csv"
BACKUP = Path(__file__).resolve().parent / "trials_backup" if not SIM else OUT / "trials_backup"
SPEC_FILE = "specs/S011_P2_addendum_to_S010.md"
M_B, M_A = 97, 17
Z95 = 1.06


def log(msg):
    line = f"[{datetime.now().isoformat(timespec='seconds')} +{time.time() - T0:7.1f}s] {msg}"
    LOGF.write(line + "\n")
    LOGF.flush()
    print(line, flush=True)


def md(df, nd=3, maxrows=400):
    if df is None or len(df) == 0:
        return "(ว่าง)\n"
    cols = list(df.columns)
    out = ["| " + " | ".join(str(c) for c in cols) + " |", "|" + "|".join("---" for _ in cols) + "|"]
    for _, r in df.head(maxrows).iterrows():
        cells = []
        for c in cols:
            v = r[c]
            if isinstance(v, (float, np.floating)):
                cells.append("–" if not np.isfinite(v) else (str(int(v)) if float(v).is_integer() and abs(v) < 1e6 else f"{v:.{nd}f}"))
            else:
                cells.append(str(v))
        out.append("| " + " | ".join(cells) + " |")
    return "\n".join(out) + "\n"


def save(df, name):
    df.to_csv(OUT / name, index=False)
    return df


# ───────────────────────── 0) sha · ข้อมูล ─────────────────────────
log(f"START run S010/S011 phase={PHASE} sim={SIM} no_trials={NO_TRIALS}")
PIN = {}
if not SIM:
    man = io_l1.verify_manifest()
    for rel, sha in {"specs/S010_P2_predictive_walkforward.md": "833ab5163cc432fa69a66585c9e304ffc2c2a7edf24e9f072c562d4d6467d8b3",
                     "specs/S011_P2_addendum_to_S010.md": None, "reviews/S010_spec_review.md": "8cf0cdd8e5a62875a190e81bea3ff4f9e9ade895cd72aaa935e1cba8293e43b4",
                     "reviews/S011_spec_review.md": None}.items():
        got = io_l1.sha256_file(TEAM / rel)
        assert sha is None or got == sha, f"sha256 ไม่ตรง: {rel}"
        PIN[rel] = got
    for rel, sha in {"base_data/SecFundFee.csv": "94f0b7716a7979303ef6ba063746061d7e454c8e966731b567aa29316f0134cd",
                     "base_data/FundProfile.csv": "9516281426fc854c8f3a0833f119cad0ce581adb39450732e579084cb4cedfaf"}.items():
        got = io_l1.sha256_file(ROOT / rel)
        assert got == sha, f"sha256 ไม่ตรง: {rel}"
        PIN[rel] = got
    DATA_SHA = dict(man)
else:
    DATA_SHA = {}
DATA_SHA_H = hashlib.sha256(json.dumps(DATA_SHA, sort_keys=True).encode()).hexdigest()
LIB_H = io_l1.lib_hash()
LIB_SHA_H = hashlib.sha256(json.dumps(LIB_H, sort_keys=True).encode()).hexdigest()
log(f"sha256 ข้อมูล {len(DATA_SHA)} ไฟล์ L0 + {len(PIN)} ไฟล์ pin ตรง · lib {len(LIB_H)} ไฟล์ (รวม p2.py)")


def load_real():
    R = io_l1.load_returns("W")
    F = io_l1.load_factors("W")
    F3 = l4.ref3a_factors(F).loc[R.index]
    raw = pd.read_parquet(io_l1.DATA / "panel_weekly.parquet").pivot(index="date", columns="FundCode", values="ret").sort_index().loc[R.index[0]:R.index[-1]].reindex(columns=R.columns)
    Z = p2.zero_flags(raw)
    AUM = p2.truncate(io_l1.load_aum(), R.index[-1]).reindex(columns=R.columns)
    U = io_l1.load_universe().set_index("FundCode").reindex(R.columns)
    fp = pd.read_csv(ROOT / "base_data" / "FundProfile.csv", usecols=["Fund Code", "Fund Name EN", "Fund Name TH"]).drop_duplicates("Fund Code").set_index("Fund Code").reindex(R.columns)
    gold = pd.Series([p2.is_gold(a, b) for a, b in zip(fp["Fund Name EN"], fp["Fund Name TH"])], index=R.columns)
    fee = pd.read_csv(ROOT / "base_data" / "SecFundFee.csv", dtype=str, encoding="utf-8-sig")
    ter = l4.ter_table(fee, list(R.columns), "actual_first").set_index("FundCode").reindex(R.columns)
    meta = pd.DataFrame(dict(policy=U["policy"], div_flag=U["div_flag"], gold=gold, ter=ter["ter"], ter_src=ter["ter_src"], ter_vintage=ter["ter_vintage"],
                             ter_asof=ter["ter_asof"]), index=R.columns)
    IDX = pd.DataFrame({"MSCI_CHINA_ALL_SHARES": F["MSCI_CHINA_ALL_SHARES"] - F["RF_BOT"], "MSCI_WORLD": F["MSCI_WORLD"] - F["RF_BOT"]}).loc[R.index]
    return p2.Inputs(R, Z, F3, AUM, meta), IDX


if SIM:
    sys.path.insert(0, str(LIB / "tests"))
    from test_p2 import make_inputs  # noqa: E402
    INP = make_inputs(N=120, T=260, seed=3)
    IDX = pd.DataFrame({"MSCI_CHINA_ALL_SHARES": INP.F3["MKT"], "MSCI_WORLD": INP.F3["BOND"]})
else:
    INP, IDX = load_real()
R, meta = INP.R, INP.meta
LAST = pd.Timestamp("2025-12-26")
for nm, obj in (("R", INP.R), ("Z", INP.Z), ("F3", INP.F3), ("AUM", INP.AUM), ("IDX", IDX)):
    assert obj.index.max() <= LAST, f"{nm} มีแถวหลัง 2025-12-26 (m3)"
DQ = p2.decision_dates(R.index, "Q")
assert len(DQ) == 15 and DQ["n_q"].tolist() == [13, 14] + [13] * 13
log(f"ข้อมูล: R {R.shape} · กองทอง {int(meta['gold'].sum())} · ปันผล {int((meta['div_flag'] == 'Y').sum())} · TER actual {int((meta['ter_src'] == 'actual').sum())} / rate {int((meta['ter_src'] == 'rate').sum())}")


def build_states(dates, variant=None):
    out, prev = [], None
    for r in dates.itertuples():
        prev = p2.state_at(INP, r.t_pos, prev, variant)
        out.append(prev)
    return out


def build_targets(states, dates):
    return [p2.target_at(INP, st, r.e_pos, r.n_q) for st, r in zip(states, dates.itertuples())]


# ───────────────────────── 1) phase pre ─────────────────────────
ST = build_states(DQ)
log("สร้าง state 15 จุด (PCA · fit · สัญญาณ) เสร็จ — ยังไม่คำนวณ target")
uq = []
for st, r in zip(ST, DQ.itertuples()):
    nxt = R.iloc[r.t_pos + 1: r.e_pos + 1][st["U"]].notna().sum(axis=0)
    need = math.ceil(r.n_q / 2)
    pol = meta["policy"].reindex(st["U"])
    c = st["counts"]
    gold_in_S = [x for x in st["S"] if bool(meta.loc[x, "gold"])]
    uq.append(dict(t=str(r.t.date()), n_q=r.n_q, S_t=len(st["S"]), U_pre=len(st["U"]), U_t=int((nxt >= need).sum()), dropped_target=int((nxt < need).sum()),
                   E=int((pol == "E").sum()), F=int((pol == "F").sum()), O=int((pol == "O").sum()), N_eff=int(st["clusters"].nunique()),
                   n_pass52=c["n_pass52"], gone_u0=c["n_gone_u0_among_52"], gold_cut=c["n_gold_cut"], div_cut=c["n_div_cut"], dup_cut=c["n_dup_cut"],
                   gold_in_S=len(gold_in_S), gold_in_S_list=";".join(gold_in_S),
                   gold_in_U=int(meta["gold"].reindex(st["U"]).sum()), div_in_U=int((meta["div_flag"].reindex(st["U"]) == "Y").sum()),
                   TER_cov=int(meta["ter_src"].reindex(st["U"]).eq("actual").sum()), AUM_cov=int(st["sig"]["D3"].notna().sum()), k=st["k"]))
UQ = pd.DataFrame(uq)
save(UQ, "universe_by_quarter.csv")
assert UQ["gold_in_U"].sum() == 0 and UQ["div_in_U"].sum() == 0, "มีกองทอง/ปันผลใน U_t"
log("universe_by_quarter: " + UQ[["t", "S_t", "U_pre", "U_t", "dropped_target", "gold_cut"]].to_string(index=False).replace("\n", " | "))

if PHASE == "pre":
    # future-scramble บนข้อมูลจริง 2 จุด · บันทึกแค่ เท่า/ไม่เท่า
    def _h(st):
        return hashlib.sha256(b"".join(np.ascontiguousarray(np.asarray(x, float)).tobytes() for x in (st["sig"].to_numpy(float), st["Lam"], st["Lam_al"], st["fit_e"].coef, st["fit_3a"].coef))).hexdigest() + "|" + ",".join(st["U"]) + "|" + ",".join(st["S"])
    scr = []
    for j in (4, 10):
        rng = np.random.default_rng(7 + j)
        tp = int(DQ["t_pos"].iloc[j])
        R2, Z2, F2, A2 = INP.R.copy(), INP.Z.copy(), INP.F3.copy(), INP.AUM.copy()
        n = len(R2) - tp - 1
        R2.iloc[tp + 1:] = rng.standard_normal((n, R2.shape[1])) * 0.05
        R2.iloc[tp + 1:] = R2.iloc[tp + 1:].where(rng.random((n, R2.shape[1])) > 0.2)
        Z2.iloc[tp + 1:] = (rng.random((n, R2.shape[1])) < 0.5).astype(float)
        F2.iloc[tp + 1:] = rng.standard_normal((n, F2.shape[1])) * 0.05
        A2.loc[A2.index > R2.index[tp]] = rng.random((int((A2.index > R2.index[tp]).sum()), A2.shape[1])) * 1e9
        sc = p2.Inputs(R2, Z2, F2, A2, meta)
        prev = None
        for jj in range(j + 1):
            prev = p2.state_at(sc, int(DQ["t_pos"].iloc[jj]), prev)
        scr.append((str(DQ["t"].iloc[j].date()), _h(prev) == _h(ST[j])))
    log(f"future-scramble บนข้อมูลจริง: {scr}")
    assert all(x[1] for x in scr), "future-scramble ไม่เท่าเดิม"
    json.dump(dict(scramble=scr, pinned=PIN, lib=LIB_H), open(OUT / "pre_run_numbers.json", "w"), indent=1, ensure_ascii=False)
    sm = UQ.copy()
    L = ["# decisions_pre_run — S010 + S011 (ข้อ 102 · B-full · m = 97) · เขียนก่อนคำนวณ target / IC ใดๆ บนข้อมูลจริง", "",
         f"สร้างโดย `run.py --phase pre` เมื่อ {datetime.now().isoformat(timespec='seconds')} · sha256 ข้อมูล 8 ไฟล์ L0 + {len(PIN)} ไฟล์ pin ตรง (สเปก S010 = 833ab516… ตรงที่ S011 pin) · phase นี้ไม่เรียก `target_at` และไม่คำนวณ IC",
         "", "## 1. ยืนยันโหมด", "- ข้อ 102: **B-full** · m ของ BH / BY = **97** (ตัดสินหลัก) · m = 17 รายงานคู่ (บรรยาย) · งบ trial ≤ 111 · n_combined_B ≤ 213 · ใช้ `spec_file = specs/S011_P2_addendum_to_S010.md`",
         "- **ที่เก็บผล:** S011 ข้อ 8 ระบุ `runs/S011/` แต่คำสั่งมอบหมายล็อกการเขียนที่ `runs/S010/` → ใช้ `runs/S010/` (รวม `trials_backup/`) · ไม่กระทบเนื้อหา (แจ้งใน results.md)",
         "- **n1 (รีวิว S011):** ป้าย what-if ฝั่ง \"ผ่าน\" = \"ทนต่อ … (ข้อมูลชุดเดียวกัน · ไม่ใช่หลักฐานอิสระ)\"", "",
         "## 2. การตีความจุดกำกวม (ตัดสินก่อนเห็นตัวเลข)",
         "1. `runs/S010` vs `runs/S011`: ดูข้อ 1",
         "2. (u2) นับแถว Dimson = แถว pos ≥ 1 ที่ rᵢ มีค่าและ factor ③a ครบทั้งแถวนั้นและแถวก่อนหน้า (≥ 52)",
         "3. (u3) ใช้ ret ดิบ == 0 (ไม่ใช่ส่วนเกิน RF) ตามนิยาม L0 (`zero_frac`) · สัดส่วน = #(ret=0)/#(ret มีค่า) บนแถว ≤ t ≤ 0.10",
         "4. (u5) corr คำนวณบนผลตอบแทนส่วนเกิน (excess) · strict `> 0.99` · overlap ≥ 52 · เก็บกองที่มีแถว ≤ t มากสุด (เสมอ → FundCode) · cluster R4 corr ≥ 0.95 บน U_t^pre",
         "5. S_t: balanced (ครบทุกแถว 2021-01-08 → t) + (u3) แล้วตัดซ้ำ ≤ t บนชุดนี้เอง (รวมกองทอง/ปันผล ตาม S011 ข้อ 1.2) · (u5) บน U ทำหลังตัดทอง/ปันผล",
         "6. PCA: `pca.pca_fit(kind=corr, k=4)` · factor แถวหลัง t: `factor_returns(min_frac 0.5)` น้ำหนักตรึง Λ_t · Procrustes บน S_t ∩ S_{t−1} กับ Λ̃_{t−1}; ไตรมาสแรก Λ̃ = Λ",
         "7. B2 ใช้ regression บน f̃ (จัดแนว) + FX (ตัวเลขเท่า non-aligned ตามพีชคณิต — test ยืนยัน)",
         "8. FM (R1) และ J1 ใช้ z = rank-normal Φ⁻¹((rank−0.5)/n) (ตัวเดียวกัน) · slope รายงานเป็น %/ไตรมาส ต่อ 1 หน่วย z · Q5−Q1 รายงานเป็น % (target ×100)",
         "9. Q5−Q1: ลำดับ (สัญญาณ, FundCode) แล้วแบ่งตำแหน่ง floor(5·pos/n) · winsorize ใช้ np.percentile 1/99 (linear)",
         "10. IC ไตรมาสที่ N < 30 → NaN; N_eff = จำนวน cluster (corr ≥ 0.95 ≤ t) ที่มีกองอยู่ในตัวอย่างนั้น · คอลัมน์บรรยาย IC แยก F / O / ใน-นอก S_t ใช้ N ขั้นต่ำ 8",
         "11. t_dec ใช้ SE ที่ใหญ่กว่า (iid vs NW L=⌊4(Q/100)^{2/9}⌋) · p ที่ df = Q_eff − 1 · Q_eff < 12 → status na-insufficient, p = 1",
         "12. perm (R5): `default_rng(20261015)` ต่อ trial · B = 999 · สถิติ = mean IC ข้ามไตรมาส",
         "13. R4 สำหรับ C3: ตัวแทนเลือกจาก U_t^pre แล้วตัดกับสมาชิก C3 ∩ U_t (S011 ข้อ 2.1)",
         "14. D3 ใช้ AUM ที่แถว t ตรง ๆ (ถ้า t ไม่มีแถว AUM → NaN) · D1 ใช้ `ter_src = actual` เท่านั้น",
         "15. ช่องเงื่อนไขเลือกด้วยผลหลักที่ m = 97 (ผ่านข้อ 6 ครบทุกข้อ) · robustness ของช่องเงื่อนไข: แม่ D1 → R1–R5 · แม่ C2 → R3 ไม่ทำ (p = 1) · แม่ B1 → R1-B1 + 4 ช่อง p = 1 (S011 m8)",
         "16. W3: k_t = max(1, ED) · ถ้า ED ล้มเหลว → k = 4 (`ed_fallback`) · ถ้า k เปลี่ยนจากไตรมาสก่อน → ไม่ทำ Procrustes ที่จุดนั้น (Λ̃ = Λ)",
         "17. ค่า p ของ J1 slopes (B-full) และ J1 = 1 ตอนตัดสิน trial เดี่ยว / เลือกช่องเงื่อนไข (S011 ข้อ 3) · `verdict.csv` มี `passed_if_J1_real_p`",
         "18. DSR: ตามข้อ 9 (V = 1/(Q−1)) · IC ต่ำสุดที่ตรวจได้ = 1.06 × s (จำลอง) คู่ nct 1.01 × s", "",
         "## 3. ตัวเลขโครงจริง (ใช้ข้อมูล ≤ t และ notna เท่านั้น)", md(sm.drop(columns=["gold_in_S_list"]), 0), "",
         f"- รายชื่อกองทองใน S_t (ตัวอย่าง t แรก / กลาง / ท้าย): {UQ['gold_in_S_list'].iloc[0]} | {UQ['gold_in_S_list'].iloc[7]} | {UQ['gold_in_S_list'].iloc[-1]}",
         f"- กองทองที่ตัดต่อไตรมาส: {int(UQ['gold_cut'].min())}–{int(UQ['gold_cut'].max())} · ไม่มีกองทอง/ปันผลใน U_t (assert) · `is_gold` ตรง 17 กอง (test)",
         f"- |U_t| {int(UQ['U_t'].min())}–{int(UQ['U_t'].max())} (มัธยฐาน {UQ['U_t'].median():.0f}) · |S_t| {int(UQ['S_t'].min())}–{int(UQ['S_t'].max())} · หลุดเพราะ target < ½: รวม {int(UQ['dropped_target'].sum())} กอง-ไตรมาส",
         f"- coverage TER (actual) ใน U_t^pre: {int(UQ['TER_cov'].min())}–{int(UQ['TER_cov'].max())} กอง · AUM ณ t: {int(UQ['AUM_cov'].min())}–{int(UQ['AUM_cov'].max())} กอง",
         f"- future-scramble บนข้อมูลจริงที่ t = {scr[0][0]} และ {scr[1][0]}: " + " · ".join(f"{a}: {'เท่าเดิมทุกบิต' if b else 'ไม่เท่า'}" for a, b in scr),
         "- โครงต่างจาก S011 ข้อ 2.2 เกิน ±15% หรือไม่: ดูตาราง (เทียบ U_t^pre ≈ 163 / 211 / 251 / 326 และ S_t ≈ 140 / 140 / 134 / 131) — เทียบด้วยตัวเลขด้านบน; ถ้าเกิน ±15% ให้หยุด (ผลการเทียบเขียนใน results.md)"]
    (OUT / "decisions_pre_run.md").write_text("\n".join(L), encoding="utf-8")
    log("เขียน decisions_pre_run.md เสร็จ — จบ phase pre")
    sys.exit(0)

# ───────────────────────── 2) phase full ─────────────────────────
XS = [  # id, sig, target, uni, sigma_assumed, line, params
    ("P2-B0", "B0", "tot", "U", 0.25, "② timing (anchor)", "52w mean ≥47 · ไม่เว้นเดือนล่าสุด"),
    ("P2-A2", "A2", "3a", "U", 0.15, "① α", "t_HAC(α) M_3a expanding · ≥52 · Dimson · HAC4"),
    ("P2-C1", "C1", "PCA", "U", 0.15, "③ exposure", "1-adjR2 M_PCA 104w"),
    ("P2-A1", "A1", "PCA", "U", 0.15, "① α", "t_HAC(α) M_PCA k=4+FX expanding"),
    ("P2-A3", "A1", "tot", "U", 0.25, "① α", "= A1"),
    ("P2-C2", "C2", "PCA", "E", 0.15, "③ exposure", "-sd 52w ddof1 ≥47 · กอง E"),
    ("P2-D1", "D1", "PCA", "U", 0.15, "④ คุณลักษณะ", "-TER actual (ข้อ 92)"),
    ("P2-C3", "C3", "PCA", "U", 0.18, "③ exposure", "A1 เฉพาะกอง C1 ≥ มัธยฐานบน U_t^pre"),
    ("P2-D3", "D3", "PCA", "U", 0.15, "④ คุณลักษณะ", "-ln AUM ที่แถว t"),
    ("P2-B2", "B2", "tot", "U", 0.25, "② timing", "52×Σβ̂ f̄̃ 52w (จัดแนว)"),
]
SPEC = {s[0]: s for s in XS}
PCA_TRIALS = {"P2-A1", "P2-A3", "P2-C1", "P2-C3", "P2-B2", "P2-B1"}
ROB_COLS = ["R1", "R2", "R3", "R4", "R5"]
SLOTS_MAIN = [s[0] for s in XS] + ["P2-B1", "P2-J1"]
COND = ["P2-M1", "P2-M2", "P2-W1", "P2-W2", "P2-W3"]
SLOTS_ROB = []
for s in XS:
    SLOTS_ROB += [f"{s[0]}.{c}" for c in ROB_COLS if not (s[0] == "P2-C2" and c == "R3")]
SLOTS_ROB += ["P2-D1.R6", "P2-B1.R1B"] + [f"P2-J1.S{i}" for i in range(1, 5)]
SLOTS_COND_ROB = [f"{c}.{r}" for c in COND for r in ROB_COLS]
ORDER97 = SLOTS_MAIN + COND + SLOTS_ROB + SLOTS_COND_ROB
ORDER17 = SLOTS_MAIN + COND
assert len(ORDER97) == M_B and len(ORDER17) == M_A, (len(ORDER97), len(ORDER17))
J1_NAMES97 = {"P2-J1"} | {f"P2-J1.S{i}" for i in range(1, 5)}
RES = {}  # slot -> dict(t, p, x, h1, h2, ...)
P_ALL, PREV_ROWS = {}, []
ALL_ROWS = []


def stat_dict(d):
    return {k: d.get(k, np.nan) for k in ("Q", "mean", "s", "se_iid", "se_nw", "L", "t", "df", "p", "x_h1", "x_h2", "lag1", "status")}


def mkrow(tid, kind, parent, line, signal, target, universe, params, freq, stat_name, d, ns, exante="", realized="", dsr=None, notes="", has_inf=1, p_over=None, est=None, status=None):
    dsr = dsr or {}
    ok_sign = (d["mean"] > 0) if np.isfinite(d.get("mean", np.nan)) else ""
    hv = (d["x_h1"] > 0 and d["x_h2"] > 0) if np.isfinite(d.get("x_h1", np.nan)) and np.isfinite(d.get("x_h2", np.nan)) else ""
    if stat_name == "hotelling_F":
        ok_sign = hv = ""
    r = {h: "" for h in p2.HEADER}
    r.update(trial_id=tid, row_kind=kind, parent_id=parent, run_at=datetime.now().isoformat(timespec="seconds"), spec_file=SPEC_FILE, line=line, signal=signal,
             target=target, universe=universe, params=params, freq=freq, period_start="2022-03-25", period_end="2025-12-26", rf_source="RF_BOT (TH_POLICY_RATE ธปท.)",
             n_periods=d.get("Q", ""), n_funds_median=float(np.median(ns)) if len(ns) else "", n_funds_min=int(np.min(ns)) if len(ns) else "", stat_name=stat_name,
             estimate=d["mean"] if est is None else est, sd_series=d.get("s", ""), se_iid=d.get("se_iid", ""), se_nw=d.get("se_nw", ""), nw_lag=d.get("L", ""),
             t_dec=d.get("t", ""), df=d.get("df", ""), p_two=d["p"] if p_over is None else p_over, has_inference=has_inf, expected_sign="+", sign_ok=ok_sign,
             est_h1=d.get("x_h1", ""), est_h2=d.get("x_h2", ""), halves_ok=hv, ic_min80_exante=exante, ic_min80_realized=realized, skew=dsr.get("skew", ""),
             kurt=dsr.get("kurt", ""), dsr_n20=dsr.get("n20", ""), dsr_n122=dsr.get("n122", ""), status=status or d.get("status", "valid"), data_sha256=DATA_SHA_H,
             lib_sha256=LIB_SHA_H, run_dir="runs/S010", notes=notes)
    return r


def record(rows):
    ALL_ROWS.extend(rows)
    if not NO_TRIALS:
        info = p2.append_trials(TRIALS, rows, BACKUP)
        log(f"append trials.csv {len(rows)} แถว · {rows[0]['trial_id']} · สะสม A={info['cumA']} B={info['cumB']}")


def dsr_pair(x):
    a, b = p2.dsr_ic(x, 20), p2.dsr_ic(x, 122)
    return dict(skew=a["skew"], kurt=a["kurt"], n20=a["dsr"], n122=b["dsr"])


def sample_q(spec, st, tg, nq):
    _, sg, kind, uni = spec[0], spec[1], spec[2], spec[3]
    df = tg["df"]
    sig = st["sig"][sg]
    tgt, tgt1 = df["T_" + kind], df["T_" + kind + "_d1"]
    pol = meta["policy"].reindex(st["U"])
    m = (df["n_tgt"] >= math.ceil(nq / 2)) & sig.notna() & tgt.notna()
    if uni == "E":
        m &= pol == "E"
    d = pd.DataFrame(dict(sig=sig[m], tgt=tgt[m], tgt_d1=tgt1[m], pol=pol[m]))
    d["inS"] = d.index.isin(st["S"])
    d["rep"] = d.index.isin(st["reps"])
    d["grp"] = st["clusters"].reindex(d.index).to_numpy()
    d["ter_le"] = ((meta["ter_vintage"].reindex(d.index) == "le2025") & (meta["ter_src"].reindex(d.index) == "actual")).to_numpy()
    return d


def ic_of(d, mn=30, col="tgt"):
    return p2.ic_q(d["sig"], d[col], mn)[0] if len(d) else np.nan


def xs_run(spec, states, tgts, dates, n1, with_perm=True):
    S = [sample_q(spec, st, tg, r.n_q) for st, tg, r in zip(states, tgts, dates.itertuples())]
    cols = {k: [] for k in ("ic", "fm", "q5", "icE", "icrep", "icS", "icout", "icF", "icO", "icd1", "icter", "n", "neff")}
    for d in S:
        cols["ic"].append(ic_of(d))
        cols["n"].append(len(d))
        cols["neff"].append(d["grp"].nunique() if len(d) else 0)
        cols["fm"].append(100 * p2.fm_slope(d["sig"], d["tgt"]) if len(d) else np.nan)
        cols["q5"].append(100 * p2.quintile_spread(d["sig"], d["tgt"], d.index) if len(d) else np.nan)
        cols["icE"].append(ic_of(d[d["pol"] == "E"]))
        cols["icrep"].append(ic_of(d[d["rep"]]))
        cols["icS"].append(ic_of(d[d["inS"]], 8))
        cols["icout"].append(ic_of(d[~d["inS"]], 8))
        cols["icF"].append(ic_of(d[d["pol"] == "F"], 8))
        cols["icO"].append(ic_of(d[d["pol"] == "O"], 5))
        cols["icd1"].append(ic_of(d, 30, "tgt_d1"))
        cols["icter"].append(ic_of(d[d["ter_le"]]) if spec[0].endswith("D1") else np.nan)
    cols = {k: np.array(v, float) for k, v in cols.items()}
    out = dict(S=S, cols=cols, main=p2.series_stats(cols["ic"], n1))
    out["R1"], out["R2"] = p2.series_stats(cols["fm"], n1), p2.series_stats(cols["q5"], n1)
    out["R3"], out["R4"] = p2.series_stats(cols["icE"], n1), p2.series_stats(cols["icrep"], n1)
    out["R6"] = p2.series_stats(cols["icter"], n1) if spec[0].endswith("D1") else None
    if with_perm:
        obs, pp = p2.perm_p([d["sig"].to_numpy() for d in S], [d["tgt"].to_numpy() for d in S], 999, p2.SEED)
        out["R5"] = dict(obs=obs, p=pp)
    return out


def xs_rows(tid, kind, parent, spec, o, freq, n1, label_tail=""):
    d = o["main"]
    ex = Z95 * spec[4] if kind in ("main",) else ""
    rows = [mkrow(tid, kind, parent, spec[5], spec[1], spec[2], spec[3], spec[6], freq, "mean_IC", d, o["cols"]["n"][np.isfinite(o["cols"]["ic"])], ex,
                  Z95 * d["s"] if np.isfinite(d["s"]) else "", dsr_pair(o["cols"]["ic"]), notes=label_tail)]
    nn = o["cols"]["n"][np.isfinite(o["cols"]["ic"])]
    for nm, key, sn in (("R1", "R1", "FM_slope"), ("R2", "R2", "Q5Q1"), ("R3", "R3", "mean_IC"), ("R4", "R4", "mean_IC")):
        if nm == "R3" and spec[0] == "P2-C2":
            continue
        rows.append(mkrow(f"{tid}.{nm}", "robustness", tid, spec[5], spec[1], spec[2], "E" if nm == "R3" else spec[3], f"robustness {nm}", freq, sn, o[key], nn, notes="หน่วย %" if nm in ("R1", "R2") else ""))
    r5 = o["R5"]
    rows.append(mkrow(f"{tid}.R5", "robustness", tid, spec[5], spec[1], spec[2], spec[3], "perm B=999 seed 20261015", freq, "perm_p", dict(mean=r5["obs"], p=r5["p"], Q=int(np.isfinite(o["cols"]["ic"]).sum()), status="valid"), nn, est=r5["obs"]))
    if o["R6"] is not None and kind == "main":
        rows.append(mkrow(f"{tid}.R6", "robustness", tid, spec[5], spec[1], spec[2], "TER=Actual ≤2025", "robustness R6", freq, "mean_IC", o["R6"], nn))
    return rows


def b1_run(states, tgts, n1):
    m_al = np.array([tg["B1_al"][1] for tg in tgts])
    m_raw = np.array([tg["B1_raw"][1] for tg in tgts])
    pi = np.array([tg["B1_al"][0] for tg in tgts])
    return dict(m=m_al, raw=m_raw, pi=pi, main=p2.series_stats(m_al, n1), R1B=p2.series_stats(m_raw, n1))


def reg(slot, d, parent_slot=None):
    RES[slot] = dict(t=d["t"], p=d["p"] if np.isfinite(d["p"]) else 1.0, x=d["mean"], h1=d["x_h1"], h2=d["x_h2"], s=d["s"], status=d.get("status", "valid"))
    P_ALL[slot] = RES[slot]["p"]


def family_tables():
    pmap = {k: v["p"] for k, v in RES.items()}
    tmap = {k: v["t"] for k, v in RES.items() if k in ORDER17}
    xm = {k: v["x"] for k, v in RES.items() if k in ORDER17}
    h1 = {k: v["h1"] for k, v in RES.items() if k in ORDER17}
    h2 = {k: v["h2"] for k, v in RES.items() if k in ORDER17}
    d97 = p2.decide_family(ORDER97, pmap, tmap, xm, h1, h2, J1_NAMES97)
    d17 = p2.decide_family(ORDER17, pmap, tmap, xm, h1, h2, {"P2-J1"})
    return d97, d17


# ── ตัวช่วยของ trial หลัก ──
TG = build_targets(ST, DQ)
log("สร้าง target 15 ไตรมาส (น้ำหนัก PCA ตรึง ณ t) เสร็จ")
XSR = {}
n1Q = 7
for spec in XS:
    t_ = time.time()
    o = xs_run(spec, ST, TG, DQ, n1Q)
    XSR[spec[0]] = o
    rows = xs_rows(spec[0], "main", "", spec, o, "Q", n1Q)
    record(rows)
    reg(spec[0], o["main"])
    for r_ in rows[1:]:
        k = r_["trial_id"].split(".")[1]
        slot = r_["trial_id"]
        dd = {"R1": o["R1"], "R2": o["R2"], "R3": o["R3"], "R4": o["R4"], "R5": dict(mean=o["R5"]["obs"], p=o["R5"]["p"], t=np.nan, x_h1=np.nan, x_h2=np.nan, s=np.nan, status="valid"), "R6": o["R6"]}[k]
        P_ALL[slot] = float(dd["p"]) if np.isfinite(dd["p"]) else 1.0
    log(f"{spec[0]}: mean IC {o['main']['mean']:+.4f} t_dec {o['main']['t']:+.2f} p {o['main']['p']:.4f} ({time.time() - t_:.1f}s)")
    if spec[0] == "P2-D1":
        pass
# B1 (ก่อน J1)
B1 = b1_run(ST, TG, n1Q)
b1d = B1["main"]
rows = [mkrow("P2-B1", "main", "", "② timing (time-series)", "sign(52w sum) × payoff PC aligned", "payoff ไตรมาสถัดไป", "PC 4 ตัว", "52w · Procrustes", "Q", "mean_payoff", b1d, np.array([4]), "", Z95 * b1d["s"], dsr_pair(B1["m"]), notes="MDE Sharpe/ปี ≈1.06"),
        mkrow("P2-B1.R1B", "robustness", "P2-B1", "② timing", "PC ดิบ ไม่จัดแนว", "payoff", "PC 4 ตัว", "R1-B1 raw", "Q", "mean_payoff", B1["R1B"], np.array([4]))]
record(rows)
reg("P2-B1", b1d)
P_ALL["P2-B1.R1B"] = float(B1["R1B"]["p"]) if np.isfinite(B1["R1B"]["p"]) else 1.0
log(f"P2-B1: mean payoff {b1d['mean']:+.4f} t_dec {b1d['t']:+.2f} p {b1d['p']:.4f}")
# J1 (ท้ายสุด)
lam, nJ = [], []
for st, tg, r in zip(ST, TG, DQ.itertuples()):
    X = st["sig"][["A1", "C1", "D1", "D3"]]
    m = tg["df"]["n_tgt"] >= math.ceil(r.n_q / 2)
    lam.append(p2.j1_slopes(X[m], tg["df"]["T_PCA"][m]))
    nJ.append(int((X[m].notna().all(axis=1) & tg["df"]["T_PCA"][m].notna()).sum()))
LAM = np.array(lam)
hot = p2.hotelling(LAM)
jd = dict(Q=hot["Q"], mean=hot["F"], s=np.nan, se_iid=np.nan, se_nw=np.nan, L=np.nan, t=np.nan, df=f"{hot['df1']},{hot['df2']}", p=hot["p"], x_h1=np.nan, x_h2=np.nan, status="valid" if hot["Q"] >= 12 else "na-insufficient")
rows = [mkrow("P2-J1", "main", "", "ส่วนเพิ่ม", "A1 · C1 · D1 · D3 (z)", "T_PCA", "ครบ 4 สัญญาณ", "FM ร่วม 4 ตัว", "Q", "hotelling_F", jd, np.array(nJ), notes="ไม่มีทิศ/ไม่ล็อก", est=hot["F"])]
J1S = [p2.series_stats(100 * LAM[:, i], n1Q) for i in range(4)]
for i, nm in enumerate(["A1", "C1", "D1", "D3"]):
    rows.append(mkrow(f"P2-J1.S{i + 1}", "robustness", "P2-J1", "ส่วนเพิ่ม", f"slope_{nm}", "T_PCA", "ครบ 4 สัญญาณ", "J1 slope (%/ไตรมาส ต่อ 1 z)", "Q", f"slope_{nm}", J1S[i], np.array(nJ)))
    P_ALL[f"P2-J1.S{i + 1}"] = float(J1S[i]["p"]) if np.isfinite(J1S[i]["p"]) else 1.0
record(rows)
P_ALL["P2-J1"] = float(hot["p"]) if np.isfinite(hot["p"]) else 1.0
RES["P2-J1"] = dict(t=np.nan, p=hot["p"], x=hot["F"], h1=np.nan, h2=np.nan, s=np.nan, status=jd["status"])
log(f"P2-J1: Hotelling F {hot['F']:.3f} p {hot['p']:.4f} Q={hot['Q']}")
# robustness p ทั้งหมดเข้า RES สำหรับ family
for k, v in P_ALL.items():
    if k not in RES:
        RES[k] = dict(t=np.nan, p=v, x=np.nan, h1=np.nan, h2=np.nan, s=np.nan, status="valid")

# ── BH รอบแรก → เลือกช่องเงื่อนไขแบบกลไก ──
d97, d17 = family_tables()
pass_r1 = d97.set_index("slot")["passed"].to_dict()
cands = [dict(slot=s, t=RES[s]["t"], passed=bool(pass_r1[s]), pca=(s in PCA_TRIALS)) for s in SLOTS_MAIN if s != "P2-J1"]
monthly_sel, anchor = p2.select_conditional(cands)
log(f"รอบแรก (m=97): ผ่าน {[c['slot'] for c in cands if c['passed']]} · รายเดือน={monthly_sel} · anchor what-if={anchor}")
COND_LOG = []
n1M = 21
DM = p2.decision_dates(R.index, "M")
assert len(DM) == 45
if monthly_sel:
    STM = build_states(DM)
    TGM = build_targets(STM, DM)
    for i, parent in enumerate(monthly_sel):
        slot = f"P2-M{i + 1}"
        if parent == "P2-B1":
            b = b1_run(STM, TGM, n1M)
            rows = [mkrow(slot, "monthly", parent, "② timing (time-series)", "B1 รายเดือน", "payoff", "PC 4 ตัว", "formation 52 สัปดาห์ ถือ 1 เดือน", "M", "mean_payoff", b["main"], np.array([4]), dsr=dsr_pair(b["m"])),
                    mkrow(f"{slot}.R1", "robustness", slot, "② timing", "PC ดิบ", "payoff", "PC 4 ตัว", "R1-B1 raw", "M", "mean_payoff", b["R1B"], np.array([4]))]
            record(rows)
            reg(slot, b["main"])
            P_ALL[f"{slot}.R1"] = float(b["R1B"]["p"]) if np.isfinite(b["R1B"]["p"]) else 1.0
            COND_LOG.append((slot, parent, b["main"], "ok"))
        else:
            o = xs_run(SPEC[parent], STM, TGM, DM, n1M)
            rows = xs_rows(slot, "monthly", parent, SPEC[parent], o, "M", n1M)
            for r_ in rows[1:]:
                r_["trial_id"] = r_["trial_id"].replace(slot + ".R", slot + ".R")
            record(rows)
            reg(slot, o["main"])
            for nm in ROB_COLS:
                dd = o["R5"] if nm == "R5" else o[nm]
                if dd is not None:
                    P_ALL[f"{slot}.{nm}"] = float(dd["p"]) if np.isfinite(dd["p"]) else 1.0
            COND_LOG.append((slot, parent, o["main"], "ok"))
        log(f"{slot} ({parent}) t_dec {COND_LOG[-1][2]['t']:+.2f}")
if anchor:
    for w, var in (("P2-W1", "W1"), ("P2-W2", "W2"), ("P2-W3", "W3")):
        if anchor == "P2-B1" and var in ("W2", "W3"):
            COND_LOG.append((w, anchor, None, "ไม่รัน (anchor = B1 · S011 m5 / S010 4.3) p = 1"))
            continue
        STW = build_states(DQ, var)
        TGW = build_targets(STW, DQ)
        if anchor == "P2-B1":
            b = b1_run(STW, TGW, n1Q)
            rows = [mkrow(w, "whatif", anchor, "② timing", f"B1 {var}", "payoff", "PC", var, "Q", "mean_payoff", b["main"], np.array([4]), dsr=dsr_pair(b["m"])),
                    mkrow(f"{w}.R1", "robustness", w, "② timing", "PC ดิบ", "payoff", "PC", "R1-B1 raw", "Q", "mean_payoff", b["R1B"], np.array([4]))]
            record(rows)
            reg(w, b["main"])
            P_ALL[f"{w}.R1"] = float(b["R1B"]["p"]) if np.isfinite(b["R1B"]["p"]) else 1.0
            COND_LOG.append((w, anchor, b["main"], "ok"))
        else:
            o = xs_run(SPEC[anchor], STW, TGW, DQ, n1Q)
            rows = xs_rows(w, "whatif", anchor, SPEC[anchor], o, "Q", n1Q, notes_ := f"variant {var}" + (" · ed_fallback" if any(s.get("ed_fallback") for s in STW) else ""))
            record(rows)
            reg(w, o["main"])
            for nm in ROB_COLS:
                dd = o["R5"] if nm == "R5" else o[nm]
                if dd is not None:
                    P_ALL[f"{w}.{nm}"] = float(dd["p"]) if np.isfinite(dd["p"]) else 1.0
            COND_LOG.append((w, anchor, o["main"], "ok"))
        log(f"{w} (anchor {anchor}) t_dec {COND_LOG[-1][2]['t']:+.2f}")
for k, v in P_ALL.items():
    if k not in RES:
        RES[k] = dict(t=np.nan, p=v, x=np.nan, h1=np.nan, h2=np.nan, s=np.nan, status="valid")
    else:
        RES[k]["p"] = v if k not in ORDER17 else RES[k]["p"]

# ── verdict ──
d97, d17 = family_tables()
V = pd.DataFrame({"slot": ORDER17})
for s in ORDER17:
    r = RES.get(s)
    V.loc[V.slot == s, "ran"] = bool(r is not None and s in P_ALL or s in RES and s in ORDER17 and RES[s]["status"] != "x")
V["ran"] = [(s in RES and s in P_ALL) for s in ORDER17]
for c in ("t_dec", "p_two", "mean", "est_h1", "est_h2"):
    key = {"t_dec": "t", "p_two": "p", "mean": "x", "est_h1": "h1", "est_h2": "h2"}[c]
    V[c] = [RES[s][key] if s in RES and s in P_ALL else np.nan for s in ORDER17]
for tag, d in (("m97", d97), ("m17", d17)):
    dd = d.set_index("slot")
    V[f"BH_reject_{tag}"] = [bool(dd.loc[s, "bh_reject"]) for s in ORDER17]
    V[f"BY_reject_{tag}"] = [bool(dd.loc[s, "by_reject"]) for s in ORDER17]
    V[f"pass_{tag}"] = [bool(dd.loc[s, "passed"]) for s in ORDER17]
    V[f"grade_{tag}"] = [dd.loc[s, "grade"] for s in ORDER17]
    V[f"pass_if_J1_real_p_{tag}"] = [bool(dd.loc[s, "passed_if_J1_real_p"]) for s in ORDER17]
V["p_J1_used_for_individual"] = 1
V["note"] = ["ไม่ได้รัน (p = 1 ใน BH)" if not r else "" for r in V["ran"]]
for slot, parent, d, why in COND_LOG:
    V.loc[V.slot == slot, "note"] = f"parent={parent} · {why}"
V["selection_reason"] = ""
V.loc[V.slot.isin(COND), "selection_reason"] = f"กลไก: รายเดือน={monthly_sel} · anchor={anchor} (รอบแรก m=97 · p_J1=1)"
save(V, "verdict.csv")
npass97 = int(V.loc[V.slot.isin(SLOTS_MAIN), "pass_m97"].sum())
npass17 = int(V.loc[V.slot.isin(SLOTS_MAIN), "pass_m17"].sum())
log(f"verdict: ผ่าน m97 = {npass97} · m17 (บรรยาย) = {npass17} · J1 ร่วมมีนัย m97 = {d97.set_index('slot').loc['P2-J1', 'bh_reject']}")

# ── ไฟล์ผล ──
icrows, sumrows, robrows = [], [], []
qdates = [str(x.date()) for x in DQ["t"]]
for spec in XS:
    o = XSR[spec[0]]
    for key, lab in (("ic", "IC"), ("fm", "FM_slope%"), ("q5", "Q5Q1%"), ("icE", "IC_E"), ("icrep", "IC_rep"), ("icS", "IC_inS"), ("icout", "IC_outS"), ("icF", "IC_F"), ("icO", "IC_O"), ("icd1", "IC_no_first_week"), ("icter", "IC_TER_le2025")):
        for q, v in enumerate(o["cols"][key]):
            icrows.append(dict(trial=spec[0], col=lab, t=qdates[q], value=v, N=o["cols"]["n"][q], N_eff=o["cols"]["neff"][q]))
    d = o["main"]
    sumrows.append(dict(trial=spec[0], signal=spec[1], target=spec[2], universe=spec[3], Q=d["Q"], mean=d["mean"], s_sigmaIC=d["s"], se_iid=d["se_iid"], se_nw=d["se_nw"], L=d["L"], t_dec=d["t"], p=d["p"],
                        h1=d["x_h1"], h2=d["x_h2"], lag1=d["lag1"], ic_min80_exante=Z95 * spec[4], ic_min80_realized_sim=Z95 * d["s"], ic_min80_realized_nct=1.01 * d["s"],
                        N_median=float(np.median(o["cols"]["n"])), N_min=int(np.min(o["cols"]["n"])), N_eff_median=float(np.median(o["cols"]["neff"])),
                        ic_inS_mean=np.nanmean(o["cols"]["icS"]) if np.isfinite(o["cols"]["icS"]).any() else np.nan, ic_outS_mean=np.nanmean(o["cols"]["icout"]) if np.isfinite(o["cols"]["icout"]).any() else np.nan,
                        ic_F_mean=np.nanmean(o["cols"]["icF"]) if np.isfinite(o["cols"]["icF"]).any() else np.nan, ic_O_mean=np.nanmean(o["cols"]["icO"]) if np.isfinite(o["cols"]["icO"]).any() else np.nan,
                        ic_no_first_week_mean=np.nanmean(o["cols"]["icd1"]) if np.isfinite(o["cols"]["icd1"]).any() else np.nan))
    for nm in ROB_COLS + ["R6"]:
        dd = o["R5"] if nm == "R5" else o.get(nm)
        if dd is None or (spec[0] == "P2-C2" and nm == "R3"):
            continue
        robrows.append(dict(trial=spec[0], col=nm, mean=dd.get("mean", dd.get("obs", np.nan)) if nm != "R5" else dd["obs"], t_dec=dd.get("t", np.nan), p=dd["p"], h1=dd.get("x_h1", np.nan), h2=dd.get("x_h2", np.nan)))
sumrows.append(dict(trial="P2-B1", signal="PC4 timing", target="payoff", universe="PC", Q=b1d["Q"], mean=b1d["mean"], s_sigmaIC=b1d["s"], se_iid=b1d["se_iid"], se_nw=b1d["se_nw"], L=b1d["L"], t_dec=b1d["t"], p=b1d["p"], h1=b1d["x_h1"], h2=b1d["x_h2"], lag1=b1d["lag1"]))
sumrows.append(dict(trial="P2-J1", signal="A1,C1,D1,D3", target="T_PCA", universe="ครบ 4", Q=hot["Q"], mean=hot["F"], p=hot["p"], N_median=float(np.median(nJ)), N_min=int(np.min(nJ))))
robrows.append(dict(trial="P2-B1", col="R1B", mean=B1["R1B"]["mean"], t_dec=B1["R1B"]["t"], p=B1["R1B"]["p"], h1=B1["R1B"]["x_h1"], h2=B1["R1B"]["x_h2"]))
for i, nm in enumerate(["A1", "C1", "D1", "D3"]):
    robrows.append(dict(trial="P2-J1", col=f"S{i + 1}_{nm}", mean=J1S[i]["mean"], t_dec=J1S[i]["t"], p=J1S[i]["p"], h1=J1S[i]["x_h1"], h2=J1S[i]["x_h2"]))
icrows += [dict(trial="P2-B1", col="mean_payoff", t=qdates[q], value=B1["m"][q], N=4, N_eff=4) for q in range(15)] + [dict(trial="P2-B1", col="mean_payoff_raw", t=qdates[q], value=B1["raw"][q], N=4, N_eff=4) for q in range(15)]
icrows += [dict(trial="P2-J1", col=f"slope%_{nm}", t=qdates[q], value=100 * LAM[q, i], N=nJ[q], N_eff=np.nan) for i, nm in enumerate(["A1", "C1", "D1", "D3"]) for q in range(15)]
save(pd.DataFrame(icrows), "ic_series.csv")
TS = save(pd.DataFrame(sumrows), "trial_summary.csv")
save(pd.DataFrame(robrows), "robustness.csv")
save(pd.DataFrame([dict(t=qdates[q], PC=k + 1, payoff=B1["pi"][q][k], m=B1["m"][q]) for q in range(15) for k in range(4)]), "b1_payoff.csv")
save(pd.DataFrame([dict(t=qdates[q], **{f"slope%_{n}": 100 * LAM[q, i] for i, n in enumerate(["A1", "C1", "D1", "D3"])}, N=nJ[q]) for q in range(15)]), "j1_slopes.csv")
pdg = []
for q, (st, r) in enumerate(zip(ST, DQ.itertuples())):
    ev = st["pf"]["eig"]
    pdg.append(dict(t=qdates[q], S_t=len(st["S"]), eig_share_PC1_4=float(ev[:4].sum() / ev.sum()), eig_PC1=float(ev[0] / ev.sum()), n_common=st["n_common"], **{f"tucker_PC{k + 1}": st["tucker"][k] for k in range(4)}))
save(pd.DataFrame(pdg), "pca_diag.csv")
# scorecard_wf
sc = []
for q, (st, tg, r) in enumerate(zip(ST, TG, DQ.itertuples())):
    fit = st["fit_e"]
    pol = meta["policy"].reindex(fit.codes).to_numpy()
    row = dict(t=qdates[q], k=st["k"], median_BIC=float(np.nanmedian(fit.bic)), mean_abs_alpha_annual=float(52 * np.nanmean(np.abs(fit.alpha))))
    Fp, Rw = tg["Fp"], tg["Rw"]
    D = np.hstack([Fp[1:], Fp[:-1]])
    r2o = np.full(len(fit.codes), np.nan)
    for j in range(len(fit.codes)):
        if fit.ok[j]:
            r2o[j] = rg.r2_oos(Rw[:, j], rg.predict_oos(fit.coef[j], D))
    for g in "EFO":
        m = pol == g
        row[f"median_R2_{g}"] = float(np.nanmedian(fit.r2[m])) if m.any() else np.nan
        row[f"median_R2oos_week_{g}"] = float(np.nanmedian(r2o[m])) if m.any() else np.nan
    if q > 0:
        pf_, f2 = ST[q - 1]["fit_al"], st["fit_al"]
        com = [c for c in f2.codes if c in set(pf_.codes)]
        ia = [f2.codes.index(c) for c in com]
        ib = [pf_.codes.index(c) for c in com]
        for k in range(5):
            a, b = f2.beta[ia, k], pf_.beta[ib, k]
            ok = np.isfinite(a) & np.isfinite(b)
            row[f"corr_beta_{'PC%d' % (k + 1) if k < 4 else 'FX'}"] = float(np.corrcoef(a[ok], b[ok])[0, 1]) if ok.sum() > 3 else np.nan
        for k in range(4):
            row[f"tucker_PC{k + 1}"] = float(st["tucker"][k])
    fa = pd.DataFrame(st["f_al"], index=R.index[: r.t_pos + 1])
    for nm in IDX.columns:
        for k in range(4):
            row[f"corr_f{k + 1}_{nm}"] = float(fa[k].corr(IDX[nm].iloc[: r.t_pos + 1]))
    sc.append(row)
save(pd.DataFrame(sc), "scorecard_wf.csv")
# mde
md_rows = []
for tc, lab in ((3.0, "t>3"), (3.2438, "BH m17 (t>=3.24)"), (4.125, "BH m97 (t>=4.12)")):
    nct = p2.mde_mult_nct(15, tc, 0.8)
    sim, size = p2.mde_mult_sim(15, tc, 0.8, 20000)
    md_rows.append(dict(rule=lab, mult_nct=nct, mult_sim_max_SE=sim, size_H0_sim=size, ic_at_sigma_015_sim=sim * 0.15, ic_at_sigma_025_sim=sim * 0.25))
sim_ar, _ = p2.mde_mult_sim(15, 3.0, 0.8, 20000, rho=0.3)
md_rows.append(dict(rule="t>3 · AR(1) 0.3", mult_nct=np.nan, mult_sim_max_SE=sim_ar, size_H0_sim=np.nan, ic_at_sigma_015_sim=sim_ar * 0.15, ic_at_sigma_025_sim=sim_ar * 0.25))
for spec in XS:
    d = XSR[spec[0]]["main"]
    md_rows.append(dict(rule=f"{spec[0]} realized", mult_nct=1.01 * d["s"], mult_sim_max_SE=Z95 * d["s"], size_H0_sim=np.nan, ic_at_sigma_015_sim=spec[4], ic_at_sigma_025_sim=abs(d["mean"])))
save(pd.DataFrame(md_rows), "mde.csv")
# dsr
cumA = cumB = None
if not NO_TRIALS:
    last = p2.read_trials(TRIALS)[-1]
    h = p2.HEADER
    cumA, cumB = int(last[h.index("n_combined")]), int(last[h.index("n_combined_B")])
else:
    cumA = p2.N_QUANT_PRIOR + sum(p2.row_counts(r)[0] for r in ALL_ROWS)
    cumB = p2.N_QUANT_PRIOR + sum(p2.row_counts(r)[1] for r in ALL_ROWS)
dsr_rows = []
series_map = {s[0]: XSR[s[0]]["cols"]["ic"] for s in XS}
series_map["P2-B1"] = B1["m"]
for k, x in series_map.items():
    a = {n: p2.dsr_ic(x, n) for n in (20, 122, cumA, cumB)}
    dsr_rows.append(dict(trial=k, SR_q=a[20]["sr"], skew=a[20]["skew"], kurt=a[20]["kurt"], SR0_n20=a[20]["sr0"], DSR_n20=a[20]["dsr"], SR0_n122=a[122]["sr0"], DSR_n122=a[122]["dsr"],
                         n_combined_A=cumA, DSR_nA=a[cumA]["dsr"], n_combined_B=cumB, DSR_nB=a[cumB]["dsr"], label="15 จุด · ไม่น่าเชื่อ · DSR สมมติ trial อิสระ"))
save(pd.DataFrame(dsr_rows), "dsr_appendix.csv")
# expectations
E = []
g = lambda k: RES[k]
trs = TS.set_index("trial")
def ex(n, txt, obs, ok):
    E.append(dict(n=n, expectation=txt, observed=obs, match=bool(ok)))
ex(1, "|U_t| 150–335 ทุกไตรมาส · |S_t| 120–150 · ทองตัด 10–16 · ไม่มีทองใน U_t", f"U_t {UQ.U_pre.min()}–{UQ.U_pre.max()} · S_t {UQ.S_t.min()}–{UQ.S_t.max()} · ทองตัด {UQ.gold_cut.min()}–{UQ.gold_cut.max()} · ทองใน U {UQ.gold_in_U.sum()}", UQ.U_pre.between(150, 335).all() and UQ.S_t.between(120, 150).all() and UQ.gold_cut.between(10, 16).all() and UQ.gold_in_U.sum() == 0)
pf = lambda k: not bool(V.set_index("slot").loc[k, "pass_m97"])
ex(2, "A1: 0≤x̄≤0.12 · ไม่ผ่าน", f"x̄={trs.loc['P2-A1', 'mean']:+.3f}", 0 <= trs.loc["P2-A1", "mean"] <= 0.12 and pf("P2-A1"))
ex(3, "A2: x̄ ≥ x̄ ของ A1 · ไม่ผ่าน", f"A2 {trs.loc['P2-A2', 'mean']:+.3f} vs A1 {trs.loc['P2-A1', 'mean']:+.3f}", trs.loc["P2-A2", "mean"] >= trs.loc["P2-A1", "mean"] and pf("P2-A2"))
ex(4, "A3: |x̄|<0.08 · x̄_H2<x̄_H1 · ไม่ผ่าน", f"x̄={trs.loc['P2-A3', 'mean']:+.3f} H1 {trs.loc['P2-A3', 'h1']:+.3f} H2 {trs.loc['P2-A3', 'h2']:+.3f}", abs(trs.loc["P2-A3", "mean"]) < 0.08 and trs.loc["P2-A3", "h2"] < trs.loc["P2-A3", "h1"] and pf("P2-A3"))
ex(5, "B0: 0.03≤x̄≤0.20 · σ≥0.20 · ไม่ผ่าน", f"x̄={trs.loc['P2-B0', 'mean']:+.3f} σ={trs.loc['P2-B0', 's_sigmaIC']:.3f}", 0.03 <= trs.loc["P2-B0", "mean"] <= 0.20 and trs.loc["P2-B0", "s_sigmaIC"] >= 0.20 and pf("P2-B0"))
ex(6, "B2: x̄>0 และ ≥ ½ x̄ ของ B0 · ไม่ผ่าน", f"B2 {trs.loc['P2-B2', 'mean']:+.3f} vs B0 {trs.loc['P2-B0', 'mean']:+.3f}", trs.loc["P2-B2", "mean"] > 0 and trs.loc["P2-B2", "mean"] >= 0.5 * trs.loc["P2-B0", "mean"] and pf("P2-B2"))
ex(7, "B1: x̄>0 แต่ t<3 · ไม่ผ่าน", f"x̄={b1d['mean']:+.3f} t={b1d['t']:+.2f}", b1d["mean"] > 0 and b1d["t"] < 3 and pf("P2-B1"))
ex(8, "C1 (1−adj R²): |x̄|<0.05 · ไม่ผ่าน", f"x̄={trs.loc['P2-C1', 'mean']:+.3f}", abs(trs.loc["P2-C1", "mean"]) < 0.05 and pf("P2-C1"))
ex(9, "C2: 0<x̄<0.10 · ไม่ผ่าน", f"x̄={trs.loc['P2-C2', 'mean']:+.3f}", 0 < trs.loc["P2-C2", "mean"] < 0.10 and pf("P2-C2"))
ex(10, "C3: x̄ ≥ x̄ ของ A1 · ไม่ผ่าน", f"C3 {trs.loc['P2-C3', 'mean']:+.3f} vs A1 {trs.loc['P2-A1', 'mean']:+.3f}", trs.loc["P2-C3", "mean"] >= trs.loc["P2-A1", "mean"] and pf("P2-C3"))
ex(11, "D1: 0≤x̄≤0.10 · บวกทั้งสองครึ่ง · ไม่ผ่าน", f"x̄={trs.loc['P2-D1', 'mean']:+.3f} H1 {trs.loc['P2-D1', 'h1']:+.3f} H2 {trs.loc['P2-D1', 'h2']:+.3f}", 0 <= trs.loc["P2-D1", "mean"] <= 0.10 and trs.loc["P2-D1", "h1"] > 0 and trs.loc["P2-D1", "h2"] > 0 and pf("P2-D1"))
ex(12, "D3: |x̄|<0.05 · ไม่ผ่าน", f"x̄={trs.loc['P2-D3', 'mean']:+.3f}", abs(trs.loc["P2-D3", "mean"]) < 0.05 and pf("P2-D3"))
ex(13, "J1: p_F>0.01 · ไม่มีนัยใน BH", f"p={hot['p']:.4f} · ร่วมมีนัย m97={bool(d97.set_index('slot').loc['P2-J1', 'bh_reject'])}", hot["p"] > 0.01 and not bool(d97.set_index("slot").loc["P2-J1", "bh_reject"]))
sg = lambda ks: float(np.median([trs.loc[k, "s_sigmaIC"] for k in ks]))
ex(14, "σ_IC จริง: T_PCA/T_3a มัธยฐาน 0.10–0.20 · T_tot 0.18–0.35", f"PCA/3a {sg(['P2-A2', 'P2-C1', 'P2-A1', 'P2-C2', 'P2-D1', 'P2-C3', 'P2-D3']):.3f} · tot {sg(['P2-B0', 'P2-A3', 'P2-B2']):.3f}", 0.10 <= sg(['P2-A2', 'P2-C1', 'P2-A1', 'P2-C2', 'P2-D1', 'P2-C3', 'P2-D3']) <= 0.20 and 0.18 <= sg(['P2-B0', 'P2-A3', 'P2-B2']) <= 0.35)
ex(15, "จำนวนที่ผ่าน: แบบ A 0–1 · B-full 0", f"m97 = {npass97} · m17 = {npass17}", npass97 == 0 and npass17 <= 1)
cnt16 = sum(1 for k in [s[0] for s in XS] if trs.loc[k, "ic_min80_realized_sim"] > abs(trs.loc[k, "mean"]))
ex(16, "IC_min80 จริง (1.06×s) > |x̄| อย่างน้อย 9 จาก 11 trial เดี่ยว", f"{cnt16} จาก 10 IC + B1", cnt16 + int(Z95 * b1d["s"] > abs(b1d["mean"])) >= 9)
try:
    pyl = (OUT / "pytest_all.log").read_text().strip().splitlines()[-1]
    rg_ok = json.load(open(OUT / "regression_phase1.json"))["all_pass"]
except Exception:
    pyl, rg_ok = "ไม่พบ pytest_all.log", False
ex(17, "test: future-scramble ทุกบิต · การหมุน ≤1e-10 · regression ระยะ 1 ตรงทุกบิต", f"{pyl} · regression_phase1.json all_pass={rg_ok}", ("passed" in pyl and "failed" not in pyl) and rg_ok)
dE = [abs(XSR[k]["main"]["mean"] - XSR[k]["R3"]["mean"]) for k in XSR if k not in ("P2-D1", "P2-C2") and XSR[k]["R3"]["Q"] >= 3]
ex(18, "IC-E ห่างจาก IC หลังไม่เกิน 0.05 ทุก trial ยกเว้น D1", f"max |Δ| = {max(dE):.3f}", max(dE) <= 0.05)
dR = [abs(XSR[k]["main"]["mean"] - XSR[k]["R4"]["mean"]) for k in XSR if XSR[k]["R4"]["Q"] >= 3]
ex(19, "IC-rep ห่างจาก IC หลังไม่เกิน 0.03", f"max |Δ| = {max(dR):.3f}", max(dR) <= 0.03)
if monthly_sel:
    oks = []
    for slot, parent, d, why in COND_LOG:
        if slot.startswith("P2-M") and d is not None:
            oks.append((np.sign(d["mean"]) == np.sign(RES[parent]["x"]), abs(d["t"]) < abs(RES[parent]["t"])))
    ex(20, "รายเดือน: เครื่องหมายตรง · t_dec ต่ำกว่า", str(oks), all(a and b for a, b in oks))
else:
    ex(20, "รายเดือน (ถ้ามี)", "ไม่มี trial ผ่าน → ไม่รัน", True)
same = bool((V.set_index("slot").loc[SLOTS_MAIN[:-1], "pass_m97"] == V.set_index("slot").loc[SLOTS_MAIN[:-1], "pass_if_J1_real_p_m97"]).all())
ex(21, "ช่องที่เลือกด้วย p_J1=1 ตรงกับด้วย p จริง", f"pass เท่ากันทุก trial หลัก = {same}", same)
EX = save(pd.DataFrame(E), "expectations_vs_" + "results" + ".csv")

# ── run_meta · results.md ──
meta_json = dict(created=datetime.now().isoformat(timespec="seconds"), runtime_sec=round(time.time() - T0, 1), seed=p2.SEED, python=platform.python_version(), versions=dict(numpy=np.__version__, pandas=pd.__version__),
                 data_sha256=DATA_SHA, pinned_sha256=PIN, lib_sha256=LIB_H, mode="B-full m=97", sim=SIM, no_trials=NO_TRIALS,
                 output_sha256={p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(OUT.glob("*.csv")) if not p.name.startswith("trials")})
json.dump(meta_json, open(OUT / "run_meta.json", "w"), indent=1, ensure_ascii=False)
Vm = V[V.slot.isin(ORDER17)][["slot", "ran", "t_dec", "p_two", "mean", "est_h1", "est_h2", "BH_reject_m97", "BY_reject_m97", "pass_m97", "grade_m97", "pass_m17", "pass_if_J1_real_p_m97", "note"]]
L = ["# results — S010 + S011 (ระยะ 2 · อำนาจทำนายแบบ walk-forward รายไตรมาส · B-full m = 97)", "",
     f"รันเมื่อ {meta_json['created']} · runtime {meta_json['runtime_sec']}s · ศึกษาอำนาจทำนายเท่านั้น (ไม่ใช่พอร์ต · ไม่ใช่คำแนะนำการลงทุน) · ที่เก็บผล `runs/S010/` (S011 ข้อ 8 ระบุ `runs/S011/` — ใช้ตามคำสั่งมอบหมาย) · `spec_file` ใน trials.csv = S011",
     f"**จำนวน trial ที่นับ:** แบบ A = {cumA - p2.N_QUANT_PRIOR} · แบบ B-full = {cumB - p2.N_QUANT_PRIOR} (≤ 111) · n_combined A = {cumA} · B = {cumB}",
     "", "## 1. ตารางคะแนน — trial หลัก (mean IC / payoff · t_dec = x̄/max(SE_iid, SE_NW))", md(TS[["trial", "signal", "target", "universe", "Q", "mean", "s_sigmaIC", "se_iid", "se_nw", "t_dec", "p", "h1", "h2", "lag1", "ic_min80_exante", "ic_min80_realized_sim", "ic_min80_realized_nct", "N_median", "N_min", "N_eff_median"]], 3),
     "", "## 2. คำตัดสิน (BH / BY · p_J1 = 1 ตอนตัดสิน trial เดี่ยว) — m = 97 หลัก · m = 17 บรรยาย", md(Vm, 4), f"ผ่าน m97 = **{npass97}** · m17 (บรรยาย) = {npass17} · เกณฑ์ BH ผ่านตัวเดียว m97: t ≥ 4.12 · m17: t ≥ 3.24",
     f"ช่องเงื่อนไขที่เลือกแบบกลไก: รายเดือน = {monthly_sel} · anchor what-if = {anchor}", "",
     "## 3. IC รายไตรมาส (trial หลัก)", md(pd.DataFrame(icrows).query("col=='IC' or col=='mean_payoff'").pivot(index="t", columns="trial", values="value").reset_index(), 3), "",
     "## 4. universe ต่อไตรมาส", md(UQ.drop(columns=["gold_in_S_list"]), 0), "",
     "## 5. robustness (ข้อมูล / target เดียวกัน · นับใน B-full)", md(pd.DataFrame(robrows), 3), "",
     "## 6. J1 (ร่วม 4 สัญญาณ)", f"Hotelling F({hot['df1']},{hot['df2']}) = {hot['F']:.3f} · p = {hot['p']:.4f} · Q = {hot['Q']} · ร่วมมีนัย m97: {bool(d97.set_index('slot').loc['P2-J1', 'bh_reject'])}", md(pd.DataFrame(robrows).query("trial=='P2-J1'"), 3), "",
     "## 7. B1 payoff ราย PC", md(pd.read_csv(OUT / "b1_payoff.csv").groupby("PC")["payoff"].agg(["mean", "std"]).reset_index(), 4), "",
     "## 8. IC ต่ำสุดที่ตรวจจับได้ (nct vs จำลองภายใต้กฎ max(SE))", md(pd.DataFrame(md_rows[:4]), 3), "",
     "## 9. ตารางคะแนนกลางแบบ walk-forward (บรรยาย · ไม่มี inference · ไม่นับ trial)", md(pd.read_csv(OUT / "scorecard_wf.csv")[["t", "median_R2_E", "median_R2_F", "median_R2_O", "median_R2oos_week_E", "median_R2oos_week_F", "mean_abs_alpha_annual", "median_BIC"]], 3),
     "(รายละเอียดข้อ 5–6 ของตารางกลาง: `scorecard_wf.csv` · `pca_diag.csv`)", "",
     "## 10. DSR (ภาคผนวก · n = 20 / 122 / n_combined)", md(pd.read_csv(OUT / "dsr_appendix.csv"), 3), "",
     "## 11. เทียบความคาดหมายล่วงหน้า (S010 ข้อ 15 + S011 ข้อ 8)", md(EX, 3), "",
     "## 12. ช่องเงื่อนไข (รายเดือน / what-if)", "\n".join(f"- {s} (parent {p}): " + (f"mean {d['mean']:+.4f} t_dec {d['t']:+.2f} p {d['p']:.4f}" if d is not None else "-") + f" · {w}" for s, p, d, w in COND_LOG) if COND_LOG else "ไม่มี trial หลักผ่านข้อ 6 (m = 97) → ไม่รันรายเดือน / what-if ทั้ง 5 ช่อง (p = 1 ใน BH · ไม่นับเป็น trial)", "",
     "ป้าย what-if: ผ่าน = \"ทนต่อ … (ข้อมูลชุดเดียวกัน · ไม่ใช่หลักฐานอิสระ)\" · ไม่ผ่าน = \"อาจขึ้นกับ … (หรือ power ไม่พอ)\" · ไม่ได้รัน = \"ไม่ได้ตรวจ\" · ไม่ veto การล็อก (S011 ข้อ 4)", "",
     "## 13. การตัดสินใจของ analyst", "- ดู `decisions_pre_run.md` (เขียนก่อนแตะ target) · ไม่มีการแก้โค้ดหลังเห็นผลจริง (ไม่ใช้ช่องแก้บั๊ก)",
     "- A1 ผ่านแต่ A2 ไม่ผ่านไม่ใช่หลักฐานว่าต่างกัน (m12) → รายงาน x̄ คู่กันเท่านั้น", "",
     "## 14. ป้าย", "(ก) โครง model เลือกจากช่วงที่ซ้อน (2024–2025 ใช้ในระยะ 1) · (ข) ข้อมูลชุดเดียวกับ quant DIAG · (ค) กองทอง 17 กองตามกฎชื่อกอง (ข้อ 98) + class ปันผล 27 กองถูกตัดจาก target; DAOL-GOLD เป็นกอง E ที่ถูกตัดตามกฎเดียวกัน; ยังอยู่ใน S_t (PCA) · (ง) TER snapshot ปี 2026 + ช่องทางย้อนทาง · (จ) FundProfile snapshot / การคัด 433 กอง · (ฉ) spike ของ L0 · (ช) self-inclusion (IC แยกใน/นอก S_t ใน trial_summary) · (ซ) \"ไม่ผ่าน\" = power ไม่พอ / ไม่มีหลักฐาน ไม่ใช่ไม่มีผล · (ฌ) ศึกษาอำนาจทำนายเท่านั้น · factor ลงทุนไม่ได้", "",
     "## ต้องให้ผู้ใช้ตัดสินใจ", "- (ไม่มีเรื่องที่ต้องหยุด) · ข้อสังเกต: S011 ระบุโฟลเดอร์ผล `runs/S011/` แต่รันที่ `runs/S010/` ตามคำสั่ง — ถ้าต้องการย้ายแจ้งได้"]
(OUT / "results.md").write_text("\n".join(L), encoding="utf-8")
log(f"เสร็จ · runtime {time.time() - T0:.1f}s")
