"""S009 run (L4 = S007 + S008 + S009) — เรียก lib เท่านั้น · ใช้: python run.py [--out DIR] [--smoke]
--smoke = รอบ debug ลดจำนวนรอบสุ่ม (ไม่ใช่ผลรายงาน) · ต้องรันจาก root ด้วย PYTHONPATH=."""
import hashlib
import json
import platform
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

LIB = Path(__file__).resolve().parents[2] / "lib"
sys.path.insert(0, str(LIB))
import external as ex  # noqa: E402
import io_l1  # noqa: E402
import l2  # noqa: E402
import l3  # noqa: E402
import l4  # noqa: E402
import nfactors as nf  # noqa: E402
import regress as rg  # noqa: E402
import scorecard as sc  # noqa: E402
import tests_stat as ts  # noqa: E402
from samples import window_mask  # noqa: E402

SEED = 20261015
SMOKE = "--smoke" in sys.argv
B_FF, N_NULL, N_PERM, B_PY, N_BOOT = (8, 4, 50, 19, 50) if SMOKE else (999, 200, 500, 999, 2000)
OUT = Path(__file__).resolve().parent
if "--out" in sys.argv:
    OUT = Path(sys.argv[sys.argv.index("--out") + 1])
OUT.mkdir(parents=True, exist_ok=True)
T0 = time.time()
LOGF = open(OUT / "run.log", "w")
TEAM = io_l1.TEAM
ROOT = io_l1.ROOT
S003, S005, S006 = TEAM / "runs" / "S003", TEAM / "runs" / "S005", TEAM / "runs" / "S006"
D_ = TEAM / "data"
CI_LABEL = "CI สุ่มกองอิสระภายใน policy — กองสัมพันธ์กัน → CI แคบกว่าจริง"


def log(msg):
    line = f"[{datetime.now().isoformat(timespec='seconds')} +{time.time() - T0:7.1f}s] {msg}"
    LOGF.write(line + "\n")
    LOGF.flush()
    print(line, flush=True)


def save(df, name, index=False):
    df.to_csv(OUT / name, index=index)
    return df


def md(df, nd=3, maxrows=300):
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


def gmed(x, m):
    x = np.asarray(x, float)[m]
    x = x[np.isfinite(x)]
    return float(np.median(x)) if len(x) else np.nan


# ───────────────────────── 0) sha256 · regression · lib ─────────────────────────
log(f"START run S009 {'(SMOKE — ไม่ใช่ผลรายงาน)' if SMOKE else ''}")
man = io_l1.verify_manifest()
PIN = {}
for rel, sha in {
    "data/factors_ext_weekly.parquet": "3105b6e7fe32ffd3648e8feac8dbd03a8db22b7e8eb245c5faf462b14da5e296",
    "runs/S003/factors_S003_weekly.parquet": l2.S003_FAC_SHA,
    "runs/S003/fund_level.csv": "36b41161d6a13c1184a4052d9e799f660f431c2694dc57fafd747f8e695bf8cf",
    "runs/S003/grs_ports.csv": "d55011094898acdf6e0419c90a3b2713479451380cacc0bf950559c43b98ba19",
    "runs/S005/primary_index.csv": "5a94ab9b498bb107600938d37f665c7263d9f0a5973460159c09ae83a799275c",
    "runs/S005/fund_clusters.csv": "072cd97ade7e01a32edb9aaf5b949381d1500dcb1ed909558bee3a373e2fc0cb",
    "runs/S005/criteria_P4.json": "0db21831202f8ff2378923740074d2517be1a37563d5f09a64e103d8651cbfb2",
    "runs/S006/fund_level.csv": "2fc1d735f52669d1034707c5d9c0194b087e91aff5dbfb91b2fd59ac4f85f5d2",
    "runs/S006/resid_B_coef.csv": "71af654fc789a24d79999d96d7149e05e75007ac6e8f83d33bd0355d292eef0b",
    "runs/S006/run_meta.json": "3abb04b19c97223ed72d062a21216d3befc0e67805e3f60298a22e02603ec5ef",
    "specs/S007_L4_group_factors_fund_alpha.md": "5dfddfc42f381679f423bdfb9ec7401222272450f3e5c1644ac46ab0a2ab2996",
    "specs/S008_L4_addendum_to_S007.md": "6483b4aaabe8bb3f48c6e6c95a97b28c6f6e78fd68f565d9ad48e3dbad0b3f66",
    "specs/S009_L4_addendum_to_S008.md": "f000ba21432da7eeb67fb5f9055650be8df98939237f072991a63f318e8621b2",
    "reviews/S009_spec_review.md": "77880b6b0f905264be3a3970f2094673df8ccfefde5e402ea920fdfc2c84405f",
    "data/QA_ACWI_CD_group.md": None,
}.items():
    got = io_l1.sha256_file(TEAM / rel)
    assert sha is None or got == sha, f"sha256 ไม่ตรง: {rel}"
    PIN[rel] = got
for rel, sha in {"base_data/SecFundFee.csv": "94f0b7716a7979303ef6ba063746061d7e454c8e966731b567aa29316f0134cd",
                 "base_data/FundProfile.csv": "9516281426fc854c8f3a0833f119cad0ce581adb39450732e579084cb4cedfaf"}.items():
    got = io_l1.sha256_file(ROOT / rel)
    assert got == sha, f"sha256 ไม่ตรง: {rel}"
    PIN[rel] = got
lib_hashes = io_l1.lib_hash()
s6lib = json.load(open(S006 / "run_meta.json"))["lib_sha256"]
assert {k: v for k, v in lib_hashes.items() if k != "l4.py"} == s6lib and set(lib_hashes) - set(s6lib) == {"l4.py"}, "lib เดิมต่างจาก S006 run_meta"
REG = json.load(open(TEAM / "runs" / "S009" / "regression_S003_S005_S006.json"))
assert REG["all_pass"], "regression S003/S005/S006 ไม่ผ่าน"
log(f"sha256 ข้อมูล 8 ไฟล์ L0 + {len(PIN)} ไฟล์ pin ตรง · lib 13 ไฟล์เดิมตรง S006 + l4.py · regression S003/S005/S006 ผ่านทุกบิต (regression_S003_S005_S006.json)")

# ───────────────────────── 1) ข้อมูล ─────────────────────────
R = io_l1.load_returns("W")
F = io_l1.load_factors("W")
Rm = io_l1.load_returns("M")
Fm = io_l1.load_factors("M")
U = io_l1.load_universe().set_index("FundCode")
pol = U["policy"]
idx = R.index
POS = np.arange(len(idx))
S = l2.fund_sets(R, U, io_l1.load_dup_pairs())
EVAL, STAB, E67 = S["EVAL"], S["STAB"], S["E67"]
assert (len(EVAL), len(STAB), len(E67)) == (207, 191, 67), (len(EVAL), len(STAB), len(E67))
mtr, mte, mfull = window_mask(idx, "train"), window_mask(idx, "test"), window_mask(idx, "full")
AF = [c for c in EVAL if c != "MGAPVD"]
AFidx = np.array([EVAL.index(c) for c in AF])
polE = pol[EVAL].to_numpy()
polA = pol[AF]
assert len(AF) == 206
I, blocks = l2.index_set(F)
M28 = I[blocks["M28"]]
FXs = l4.fx_factor(F)
SC_ = l4.spot_carry(F)
C0 = l4.ref3a_factors(F)
assert (FXs.index == F.index).all() and F.index.max() < pd.Timestamp("2026-01-01")
fac_path = S003 / "factors_S003_weekly.parquet"
BASES = {"1a": l2.load_l1_factors(fac_path, "1a"), "1c": l2.load_l1_factors(fac_path, "1c")}
FL3 = pd.read_csv(S003 / "fund_level.csv")
FL6 = pd.read_csv(S006 / "fund_level.csv")
PRIMDF = pd.read_csv(S005 / "primary_index.csv")
PRIM_L2 = {b: PRIMDF[PRIMDF.form == f"{b}@4"].set_index("FundCode")["index"] for b in BASES}
assert (PRIM_L2["1a"].reindex(AF) == PRIM_L2["1c"].reindex(AF)).all()  # ป้ายกลุ่มเดียวกัน
FC = pd.read_csv(S005 / "fund_clusters.csv").set_index("FundCode")
CLU = FC["group_id"]
in_pca = FL3[(FL3.form == "1a")].set_index("FundCode")["in_PCA_sample"].reindex(EVAL)
inE67 = pd.Series([c in set(E67) for c in EVAL], index=EVAL)
div_flag = (U.loc[EVAL, "div_flag"] == "Y")
fp = pd.read_csv(ROOT / "base_data" / "FundProfile.csv", usecols=["Fund Code", "FX Risk Flag"]).drop_duplicates("Fund Code").set_index("Fund Code")
fxflagN = pd.Series([fp["FX Risk Flag"].get(c) == "N" for c in EVAL], index=EVAL)
E_b = {b: l4.e_from_s006(M28, f, S006 / "resid_B_coef.csv", b) for b, f in BASES.items()}
for b in BASES:
    chk, _ = l3.residualize(M28[l3.P4], BASES[b], mtr)
    assert np.nanmax(np.abs(chk.to_numpy() - E_b[b].to_numpy())) <= 1e-12
log(f"ชุดกอง EVAL {len(EVAL)} · α-family {len(AF)} (ตัด MGAPVD) · E {int((polA == 'E').sum())} / F {int((polA == 'F').sum())} / O {int((polA == 'O').sum())} · div ใน EVAL {int(div_flag.sum())} · E67 {len(E67)} · in_PCA_sample {int(in_pca.sum())}")

# ───────────────────────── 2) ter_qa.json ─────────────────────────
fee = pd.read_csv(ROOT / "base_data" / "SecFundFee.csv", dtype=str, encoding="utf-8-sig")
TER = l4.ter_table(fee, AF).set_index("FundCode")
QA = l4.ter_qa(fee, TER.reset_index(), pol=pol)
QA["timestamp"] = datetime.now().isoformat(timespec="seconds")
json.dump(QA, open(OUT / "ter_qa.json", "w"), ensure_ascii=False, indent=1, default=str)
log(f"เขียน ter_qa.json (ก่อน fit) · TT≥OF {QA['tt_ge_of']} · ter_dropped={QA['ter_dropped']} · NaN {QA['n_nan']} · กอง Rate {QA['rate_funds']} · ข้ามรุ่น {QA['cross_vintage_stability']}")

# ───────────────────────── 3) chars.csv (ก่อน fit model α) ─────────────────────────
FXb = l4.fx_beta(R, F, mtr, AF)
CH = pd.DataFrame(index=AF)
CH["policy"] = polA
CH["ter"] = TER["ter"]
for c in ("ter_asof", "ter_vintage", "ter_src", "d_v2026", "d_rate"):
    CH[c] = TER[c]
CH["DIV"] = div_flag.reindex(AF).astype(int)
CH["FXb"] = FXb
CH["FXflag_N"] = fxflagN.reindex(AF).astype(int)
CH["F"] = (polA == "F").astype(int)
CH["O"] = (polA == "O").astype(int)
CH["in_PCA_sample"] = in_pca.reindex(AF).astype(int)
CH["in_E67"] = inE67.reindex(AF).astype(int)
AUM = io_l1.load_aum().reindex(idx)
laum = {}
for c in AF:
    s_ = AUM[c].loc[mtr].dropna() if c in AUM.columns else pd.Series(dtype=float)
    laum[c] = float(np.log(s_.iloc[0])) if len(s_) and s_.iloc[0] > 0 else np.nan
CH["log_aum"] = pd.Series(laum)
save(CH.drop(columns=["ter_asof"]).assign(ter_asof=CH["ter_asof"].astype(str)), "chars.csv", index=True)
log("เขียน chars.csv (TER · d_v2026 · d_rate · DIV · FXβ · log AUM) ก่อน fit model α")

# ───────────────────────── 4) groups.csv ─────────────────────────
full_train = R.loc[mtr, AF].notna().all()
LAB = l4.group_labels(PRIM_L2["1a"], pol, AF)
GT = l4.group_table(LAB, CLU, full_train)
GT["theme_label"] = np.where(GT.group == "MSCI_ACWI_CD", "ธีมจากชื่อกอง (ฉ)", "")
save(GT, "groups.csv")
GOF = LAB.set_index("FundCode")["group"]
DUMMY_G = list(GT[GT.dummy].group)
for g in DUMMY_G:
    CH["G_" + g] = (GOF.reindex(AF) == g).astype(int)
log("เขียน groups.csv · dummy กลุ่ม " + json.dumps(DUMMY_G) + " · วิธี " + json.dumps(dict(zip(GT.group, GT.method)), ensure_ascii=False))

# ───────────────────────── 5) แผน X + decisions_pre_run.md (ก่อน fit) ─────────────────────────
GCOLS = ["G_" + g for g in DUMMY_G]
CONT = ["ter", "FXb", "omr"]
BIN = ["DIV", "d_v2026", "d_rate"]
CH["omr"] = 0.5  # placeholder (เติม 1−R² หลัง fit M1/M2 — ไม่มีผลต่อกติกาตัดคอลัมน์ dummy)
CH["ter"] = CH["ter"]
Eaf = CH[CH.policy == "E"]
plan = {}


def plan_x(name, d, extra_bin=(), drop_cont=(), drop_bin=()):
    cont = [c for c in CONT if c not in drop_cont]
    bn = [c for c in BIN + list(extra_bin) if c not in drop_bin]
    dd = d[d.ter.notna()]
    X, d2, dr = l4.build_x(dd, cont, bn, GCOLS)
    plan[name] = dict(n=int(len(X)), cols=list(X.columns), dropped=dr, n_indep=int(CLU[list(X.index)].nunique()))
    return dr


plan_x("X2_E", Eaf)
plan_x("X1_ALL", CH, extra_bin=("F", "O"))
plan_x("XV1_ALL_actual_le2025", CH[(CH.ter_src == "actual") & (CH.ter_vintage == "le2025")], extra_bin=("F", "O"))
plan_x("XV2_E_actual_le2025", Eaf[(Eaf.ter_src == "actual") & (Eaf.ter_vintage == "le2025")])
plan_x("XE67", Eaf[Eaf.in_E67 == 1])
PRE = ["# decisions_pre_run — S009 (เขียนก่อน fit ทุกแบบ · การตีความจุดกำกวม)\n",
       f"เวลา: {datetime.now().isoformat(timespec='seconds')} · ลำดับ: regression → ter_qa.json → chars.csv → groups.csv → ไฟล์นี้ → fit\n",
       "## ก. การตีความจุดกำกวม (เลือกแบบกระทบผลน้อยสุด)",
       "1. **เลข test:** test_l3.py เดิมใช้เลขถึง 49 → test ใหม่ของ S007 เลข 48–68 ตั้งชื่อ `test_s9_<เลข>_…` ใน `lib/tests/test_l4.py` เพื่อไม่ให้เลขชน (เลขในชื่อ = เลขของ spec) · เพิ่ม test_s9_69 ตรวจ `MixedProvider` / `sub_fit`",
       "2. **`ff_bootstrap`** รับ provider (`.design(code)`) แทน `design_fn` ตามที่ S007 8.2 ร่างไว้ — พฤติกรรมเท่ากัน · กองเข้ารอบเมื่อมี ≥ 104 แถวไม่ขาดจากแถวที่ resample ได้ (นับจากแถวที่สุ่มได้จริงในรอบนั้น)",
       "3. **ชุดที่ fit:** fit ทุกแถวบน EVAL 207 แล้วตัด MGAPVD (ข้อ 54) ออกเป็น α-family 206 ก่อนทำ BH / BY / MDA / ตาราง Q2 / X · scorecard ใช้ EVAL 207 ตาม S003–S006 · min_obs = 52 (train / full / test) · bootstrap ≥ 104",
       "4. **p ค่าสอง​ด้านของ α** = 2·SF(|t_HAC|) แบบ normal (แบบเดียวกับ S006) · se(α̂) = |α̂/t| (m4) · BH/BY q = 0.10 ต่อ (แถว × ช่วง) บน 206 กอง",
       "5. **CI ของ xsec** ใช้ t(G−1) (G = จำนวนกลุ่มกองอิสระใน regression นั้น) · Wald ร่วมของ dummy กลุ่มใช้ χ²(q) ด้วย V แบบ CR1 · HC1 = N/(N−K) · WLS น้ำหนัก 1/se² (X4 = OLS)",
       "6. **'ครบ train'** = ผลตอบแทนไม่ว่างทุกสัปดาห์ของ train (156) · u (residual) ใช้ 155 แถว (แถวแรกไม่มี lag) · PCA กลุ่มบน correlation ของ u ที่ตัวแทน cluster (FundCode น้อยสุดต่อกลุ่มอิสระที่ครบ train)",
       "7. **k_g:** `group_k` ใช้ `onatski_ed(kmax=3)` + `parallel_analysis(n_perm=500, q=0.95, seed=20261015)` · ตัวแทน < 8 → `ed_small` และใช้ LOO-mean ทั้งกลุ่ม · ED ไม่ลู่เข้า → `ed_none` เช่นกัน",
       "8. **null กลุ่มสุ่ม (b):** 200 draw · `default_rng(20261015)` ใหม่ต่อ (กลุ่ม × ฐาน) · กลุ่มเรียงตามชื่อ · pool = กอง E ใน α-family นอกกลุ่ม g และนอก cluster ของ i (PCA: ตัวแทน cluster ที่ครบ train) · ทำเฉพาะกลุ่ม G-E ที่มีวิธี PCA / LOO-mean · G-F / G-O ไม่ทำ null",
       "9. **ธีม ACWI_CD (G-T) และ LOO-mean ธีม:** ไม่ได้ทำในรอบนี้ถ้าไม่มีหัวข้อ 'ธีม' ใน results.md (บันทึกใน 'ค้าง')",
       "10. **FXβ** = b0+b1 ของ FX ใน y ~ [MKT, FX] train (min_obs 52) ทุก policy · 1−R² ของ M3/M4 ใช้ adj R² ของ model ตัวเอง (m10) · M1/M2 ของ model ตัวเอง",
       "11. **log AUM:** สัปดาห์แรกที่มีค่าใน train · X5 ทำเมื่อครอบคลุม ≥ 80% ของ E · มิฉะนั้น N/A",
       "12. **FX gap:** กองที่ FXβ = มัธยฐานกลุ่มพอดีถูกตัดจากทั้งสองข้าง · กลุ่มที่เข้า = G-E ที่มีสมาชิก E (α-family) ≥ 10",
       "13. **ป้าย 'แยกจากโชคไม่ได้':** ใช้เมื่อ p_boot (หางบน) ของ **สัดส่วน** BH ของ M1 หรือ M2 > 0.10 (S008 F · m5)",
       "14. **Q2 sign:** sign(α̂_train) = sign(α̂_test) = sign(α̂_full) แยกฐาน · α̂ = 0 / NaN นับว่าไม่ตรง",
       "15. **ชื่อ factor กลุ่ม:** ผู้สมัคร = e ของ M28 (residualize บน f ด้วย `l3.residualize`) + ETF ส่วนขยาย 14 ตัว (`l3.ext_excess`) · factor กลุ่มฉบับรวม = factor ของตัวแทน cluster ทั้งกลุ่ม (PC1 สำหรับ PCA) หรือ mean ของสมาชิกทั้งกลุ่ม · ป้าย 'ชื่อ' |corr| ≥ 0.7 ทั้ง train และ test · 'คล้าย' 0.5–0.7",
       "16. **ลดขอบเขต (ค้าง/ไม่ได้ทำในรอบนี้ ถ้ามีในหัวข้อ 'ค้าง' ของ results.md):** monthly · G-T ธีม · stability/rolling เฉพาะที่ระบุใน results.md",
       "",
       "## ข. กติกา TER และ d_rate (S009 1.1, 1.4) — ผลที่ได้จากข้อมูล (ก่อน fit)",
       f"- เซลล์ vintage × src: {json.dumps(QA['cells'], ensure_ascii=False)}",
       f"- QA TT ≥ OF: {QA['tt_ge_of']} · ter_dropped = {QA['ter_dropped']} · กอง Rate: {QA['rate_funds']}",
       f"- Rate − Actual (ก): {QA['rate_minus_actual_same_row']} · (ข): {QA['rate_le2025_minus_actual_chosen']}",
       f"- ความเสถียรข้ามรุ่น TER (Actual 2026 − Actual ≤ 2025): {QA['cross_vintage_stability']}",
       "",
       "## ค. คอลัมน์และจำนวนกองที่ใช้จริงต่อ regression (ก่อน fit · ลำดับ S008 I.3)"]
for k, v in plan.items():
    PRE.append(f"- **{k}**: n = {v['n']} · กลุ่มอิสระ = {v['n_indep']} · คอลัมน์ = {v['cols']} · ตัดคอลัมน์ = {v['dropped']['cols']} · ตัดกอง (TER=NaN, d_rate) = {v['dropped']['funds']}")
PRE.append("- X3 / X4 / X5 ใช้ชุดและคอลัมน์เดียวกับ X2 (X5 + log_aum ถ้าครอบคลุม ≥ 80%) · XV ตัด d_v2026 / d_rate โดยกฎ < 3 กอง (ค่าคงที่)")
PRE.append(f"- seed {SEED} · B_ff {B_FF} · n_null {N_NULL} · n_perm {N_PERM} · PY B {B_PY} · bootstrap CI {N_BOOT}")
(OUT / "decisions_pre_run.md").write_text("\n".join(PRE) + "\n", encoding="utf-8")
log("เขียน decisions_pre_run.md (ก่อน fit)")
assert not QA["ter_dropped"], "TER ไม่ผ่าน QA — spec ให้ถอด TER แล้วรันต่อ (ไม่คาดว่าเกิด)"

# ───────────────────────── 6) แถว + fit ─────────────────────────
ROWS = {}


def add_row(rid, label, base_df, pf=None, kind="main", ref=None):
    ROWS[rid] = dict(id=rid, label=label, base_df=base_df, pf=pf, kind=kind, ref=ref, names=list(base_df.columns) + (["PRIM"] if pf is not None else []))


FXf = FXs.to_frame("FX")
pf_ = {b: l3.perfund_from_primary(E_b[b], PRIM_L2[b], EVAL) for b in BASES}
pf5 = {b: l3.perfund_from_primary(E_b[b], PRIM_L2[b], EVAL, exclude=("MSCI_VIETNAM",)) for b in BASES}
for b, f in BASES.items():
    add_row(f"ref_L3B_{b}", f"ref-L3B@{b}", f, pf_[b], "ref")
    add_row(f"ref_L3B5_{b}", f"ref-L3B5@{b}", f, pf5[b], "ref")
    add_row(f"ref_FX_{b}", f"ref-FX@{b}", pd.concat([f, FXf], axis=1), None, "ref")
add_row("ref_3a", "ref-③a", C0, None, "ref")
for rid, b, strict in (("M1", "1a", False), ("M2", "1c", False), ("M3", "1a", True), ("M4", "1c", True)):
    add_row(rid, f"{rid}@{b}" + (" ⚠️" if strict else ""), pd.concat([BASES[b], FXf], axis=1), pf5[b] if strict else pf_[b], "main" if not strict else "strict", ref=f"ref_L3B{'5' if strict else ''}_{b}")
for rid, b in (("H1", "1a"), ("H2", "1c")):
    add_row(rid, f"{rid}@{b}", pd.concat([BASES[b], SC_], axis=1), pf_[b], "appx", ref=f"ref_L3B_{b}")
for r in ROWS.values():
    r["prov"] = l4.MixedProvider(r["base_df"], r["pf"])


def fitr(r, mk, mk_te, funds=EVAL, min_obs=52):
    if r["pf"] is not None:
        fit, ro, _ = l3.fit_perfund(R, r["base_df"], r["pf"], mk, mk_te, funds, min_obs)
        return fit, ro
    prov = rg.CommonFactors(r["base_df"])
    fit = rg.fit_funds(R, prov, mk, min_obs, funds=funds)
    ro = rg.oos_r2_funds(R, prov, fit, mk_te) if mk_te is not None else np.full(len(funds), np.nan)
    return fit, ro


log("เริ่ม fit ref-L3B + ตรวจ test 50 (ก่อน fit แถวอื่น)")
FIT = {}
for rid in ("ref_L3B_1a", "ref_L3B_1c", "ref_L3B5_1a", "ref_L3B5_1c"):
    FIT[(rid, "train")] = fitr(ROWS[rid], mtr, mte)
t50 = []
for rid, srow in (("ref_L3B_1a", "R3"), ("ref_L3B_1c", "R8"), ("ref_L3B5_1a", "R5"), ("ref_L3B5_1c", "R10")):
    fit, ro = FIT[(rid, "train")]
    ref = FL6[FL6.row == srow].set_index("FundCode").loc[EVAL]
    for nm, arr in (("alpha", fit.alpha), ("t_alpha_hac", fit.t_alpha_hac), ("adj_r2", fit.adj_r2), ("bic", fit.bic), ("r2_oos", ro)):
        v = float(np.nanmax(np.abs(arr - ref[nm].to_numpy())))
        t50.append(dict(row=rid, S006_row=srow, stat=nm, max_abs_diff=v, tol=1e-10, passed=v <= 1e-10))
T50 = save(pd.DataFrame(t50), "test50_ref_L3B_vs_S006.csv")
assert T50.passed.all(), "test 50: ref-L3B ไม่ตรง S006 ภายใน 1e-10\n" + T50[~T50.passed].to_string()
log(f"test 50 ผ่าน: ref-L3B ตรง S006 R3/R8/R5/R10 (max {T50.max_abs_diff.max():.2e})")
assert float(np.abs(SC_["SPOT"] + SC_["CARRY"] - FXs).max()) <= 1e-15
for rid, r in ROWS.items():
    for w, mk, mk_te in (("train", mtr, mte), ("full", mfull, None)):
        if (rid, w) not in FIT:
            FIT[(rid, w)] = fitr(r, mk, mk_te)
    if rid in ("M1", "M2", "M3", "M4"):
        FIT[(rid, "test")] = fitr(r, mte, None)
log(f"fit {len(FIT)} (แถว × ช่วง) เสร็จ")

# ───────────────────────── 7) scorecard · fund_level · α ─────────────────────────
srows, flrows, alrows = [], [], []
for rid, r in ROWS.items():
    fit, ro = FIT[(rid, "train")]
    ref = r["ref"]
    dl = l2.deltas(fit, ro, *FIT[(ref, "train")]) if ref else None
    ff, _ = FIT[(rid, "full")]
    d = sc.score_model(fit, ro, polE, div_flag=div_flag.to_numpy())
    d.insert(0, "label", r["label"])
    d.insert(0, "row", rid)
    d["p_regressors_max"] = 2 * fit.K + 1
    for c_ in ("d_adj_r2", "d_r2_oos", "d_bic", "d_abs_alpha_pct"):
        d["med_" + c_] = [np.nan if dl is None else gmed(dl[c_], (polE == g if g != "ALL" else True) & fit.ok & FIT[(ref, "train")][0].ok) for g in d.policy]
    ft = fit.t_alpha_hac
    rejt = np.zeros(len(EVAL), bool)
    ok_ = fit.ok & np.isfinite(ft)
    rejt[ok_] = ts.bh(2 * stats.norm.sf(np.abs(ft[ok_])), 0.10)[0]
    tf = ff.t_alpha_hac
    rejf = np.zeros(len(EVAL), bool)
    ok_ = ff.ok & np.isfinite(tf)
    rejf[ok_] = ts.bh(2 * stats.norm.sf(np.abs(tf[ok_])), 0.10)[0]
    d["bh_reject_train(EVAL207)"] = [int((rejt & (polE == g if g != "ALL" else True)).sum()) for g in d.policy]
    d["bh_reject_full(EVAL207)"] = [int((rejf & (polE == g if g != "ALL" else True)).sum()) for g in d.policy]
    d["mean_abs_alpha_full_pct"] = [float(np.nanmean(np.abs(ff.alpha[ff.ok & (polE == g if g != "ALL" else True)])) * 5200) for g in d.policy]
    srows.append(d)
    x = pd.DataFrame(dict(row=rid, FundCode=EVAL, policy=polE, in_E67=inE67.to_numpy(), in_PCA_sample=in_pca.to_numpy(), alpha_train=fit.alpha, t_train=fit.t_alpha_hac,
                          adj_r2=fit.adj_r2, bic=fit.bic, r2_oos=ro, alpha_full=ff.alpha, t_full=ff.t_alpha_hac))
    if dl is not None:
        x["d_adj_r2"], x["d_r2_oos"], x["d_bic"] = dl["d_adj_r2"], dl["d_r2_oos"], dl["d_bic"]
    flrows.append(x)
    for w in ("train", "full", "test"):
        if (rid, w) not in FIT:
            continue
        fw = FIT[(rid, w)][0]
        sf = l4.sub_fit(fw, AFidx)
        at = l4.alpha_table(sf)
        at.insert(0, "FundCode", sf.codes)
        at.insert(0, "window", w)
        at.insert(0, "row", rid)
        alrows.append(at)
SCORE = save(pd.concat(srows, ignore_index=True), "scorecard.csv")
FL = save(pd.concat(flrows, ignore_index=True), "fund_level.csv")
AL = pd.concat(alrows, ignore_index=True)
AL["policy"] = AL.FundCode.map(pol)
AL["group"] = AL.FundCode.map(GOF)
AL["div_flag"] = AL.FundCode.map(div_flag).astype(int)
AL["fx_flag_N"] = AL.FundCode.map(fxflagN).astype(int)
AL["in_PCA_sample"] = AL.FundCode.map(in_pca).astype(int)
AL["in_E67"] = AL.FundCode.map(inE67).astype(int)
AL["label_peer"] = "α เทียบพอร์ตกองเพื่อน (ฌ)"
save(AL, "alpha_fund.csv")
log("เขียน scorecard.csv · fund_level.csv · alpha_fund.csv")


def A(rid, w):
    return AL[(AL.row == rid) & (AL.window == w)].set_index("FundCode")


# ───────────────────────── 8) Q2 · BH list · class ปันผล · self-inclusion · ref-③a ─────────────────────────
Q = pd.DataFrame(index=AF)
Q["policy"], Q["group"], Q["div"] = polA, GOF.reindex(AF), div_flag.reindex(AF).astype(bool)
Q["in_PCA_sample"], Q["in_E67"] = in_pca.reindex(AF), inE67.reindex(AF)
for k, rid in (("1", "M1"), ("2", "M2")):
    for w in ("full", "train", "test"):
        a = A(rid, w)
        Q[f"alpha_{w}_{k}"], Q[f"t_{w}_{k}"] = a["alpha_pct"], a["t"]
    Q[f"bh{k}"], Q[f"by{k}"], Q[f"mda{k}"] = A(rid, "full")["bh"], A(rid, "full")["by"], A(rid, "full")["mda"]
    Q[f"sg{k}"] = (np.sign(Q[f"alpha_train_{k}"]) == np.sign(Q[f"alpha_test_{k}"])) & (np.sign(Q[f"alpha_test_{k}"]) == np.sign(Q[f"alpha_full_{k}"])) & (Q[f"alpha_full_{k}"] != 0)
Q["alpha1"] = Q["alpha_full_1"]
Q["bh_ref3a"] = A("ref_3a", "full")["bh"]
Q["bh_refFX_1a"], Q["bh_refFX_1c"] = A("ref_FX_1a", "full")["bh"], A("ref_FX_1c", "full")["bh"]
Q["bh3"], Q["bh4"] = A("M3", "full")["bh"], A("M4", "full")["bh"]
log(f"BH (full · 206): M1 {int(Q.bh1.sum())} · M2 {int(Q.bh2.sum())} · M3 {int(Q.bh3.sum())} · M4 {int(Q.bh4.sum())} · ref-③a {int(Q.bh_ref3a.sum())}")

# ───────────────────────── 9) FF 2010 bootstrap (M1, M2 · full) ─────────────────────────
FFB = {}
FFS = []
for rid in ("M1", "M2"):
    r = ROWS[rid]
    ff = FIT[(rid, "full")][0]
    ah = ff.alpha[AFidx]
    log(f"เริ่ม ff_bootstrap {rid} B={B_FF}")
    rd, act, sm = l4.ff_bootstrap(R, r["prov"], AF, mfull, ah, B=B_FF, block=4, seed=SEED, min_rows=104, is_E=(polA == "E").to_numpy())
    sm.insert(0, "row", rid)
    FFS.append(sm)
    FFB[rid] = (act, sm)
    rd.insert(0, "row", rid)
    rd.to_csv(OUT / f"ff_boot_{rid}.csv", index=False)
SFF = save(pd.concat(FFS, ignore_index=True), "ff_boot_summary.csv")
Q2 = {}
pb = {rid: float(SFF[(SFF.row == rid) & (SFF.stat == "frac_bh")].p_boot_upper.iloc[0]) for rid in ("M1", "M2")}
LUCK = any(v > 0.10 for v in pb.values())
V = l4.q2_verdict(Q, p_boot_gt=LUCK)
Q["q2_verdict"], Q["div_note"], Q["q2_label"] = V.verdict, V.div_note, V.label
Q["ref3a_bh"] = Q["bh_ref3a"]
save(Q, "alpha_q2.csv", index=True)
cross = Q.groupby(["q2_verdict"]).apply(lambda d: pd.Series(dict(n=len(d), ref3a_bh=int(d.ref3a_bh.sum()), refFX_1a_bh=int(d.bh_refFX_1a.sum()), refFX_1c_bh=int(d.bh_refFX_1c.sum())))).reset_index()
save(cross, "q2_vs_ref3a.csv")
save(Q[(Q.bh1 | Q.bh2 | Q.bh3 | Q.bh4)].assign(cluster=CLU.reindex(Q[(Q.bh1 | Q.bh2 | Q.bh3 | Q.bh4)].index).to_numpy()), "alpha_bh_list.csv", index=True)
dv = Q[Q["div"]].copy()
dv["mda_1"] = Q.loc[dv.index, "mda1"]
dnd = lambda g: Q[(~Q["div"]) & (Q.policy == g)]
dv_rows = [dict(policy=g, n_div=int(((Q["div"]) & (Q.policy == g)).sum()), med_alpha_div_M1=float(Q[(Q["div"]) & (Q.policy == g)].alpha_full_1.median()) if ((Q["div"]) & (Q.policy == g)).any() else np.nan,
                med_alpha_nodiv_M1=float(dnd(g).alpha_full_1.median()), n_nodiv=len(dnd(g))) for g in ("E", "F", "O")]
save(pd.DataFrame(dv_rows).assign(diff=lambda d: d.med_alpha_div_M1 - d.med_alpha_nodiv_M1), "alpha_div_summary.csv")
mg = A("M1", "full").loc[["MGAG"]] if "MGAG" in A("M1", "full").index else None
mp_fit = FIT[("M1", "full")][0]
j_pvd = EVAL.index("MGAPVD")
dv.to_csv(OUT / "alpha_div.csv", index=True)
pd.DataFrame([dict(FundCode="MGAPVD", alpha_full_M1_pct=mp_fit.alpha[j_pvd] * 5200, t_full_M1=mp_fit.t_alpha_hac[j_pvd], note="MGAPVD = ชนิดกองทุนสำรองเลี้ยงชีพของ MGAG (ข้อ 54) · ไม่นับใน family 206")]).to_csv(OUT / "alpha_mgapvd.csv", index=False)
# แยก in_PCA_sample / E67 (E) และ mean|α|, signed
sel = []
for rid in ("M1", "M2", "M3", "M4", "ref_FX_1a", "ref_FX_1c", "ref_3a", "ref_L3B_1a", "ref_L3B_1c"):
    a = A(rid, "full")
    for nm, m in (("E_in_PCA_sample", (a.policy == "E") & (a.in_PCA_sample == 1)), ("E_E67", (a.policy == "E") & (a.in_E67 == 1)), ("E_all", a.policy == "E"), ("F", a.policy == "F"), ("O", a.policy == "O"), ("ALL", a.policy.notna())):
        x = a[m]
        sel.append(dict(row=rid, set=nm, n=len(x), mean_abs_alpha_pct=float(x.alpha_pct.abs().mean()), median_alpha_pct=float(x.alpha_pct.median()), n_BH=int(x.bh.sum()), n_BY=int(x.by.sum()),
                        median_mda=float(x.mda.median()), median_mda_mt=float(x.mda_mt.median())))
SELF = save(pd.DataFrame(sel), "alpha_by_set.csv")
agr = []
for rid in ("M1", "M2", "M3", "M4", "ref_FX_1a", "ref_FX_1c", "ref_3a"):
    a = A(rid, "full")
    for g, d in a.groupby("group"):
        agr.append(dict(row=rid, group=g, n=len(d), median_alpha_pct=float(d.alpha_pct.median()), mean_abs_alpha_pct=float(d.alpha_pct.abs().mean()), n_BH=int(d.bh.sum()),
                        median_mda=float(d.mda.median()), median_mda_mt=float(d.mda_mt.median())))
save(pd.DataFrame(agr), "alpha_by_group.csv")
mda = []
for rid in ("M1", "M2", "M3", "M4"):
    a = A(rid, "full")
    for g in ("E", "F", "O", "ALL"):
        x = a[(a.policy == g) if g != "ALL" else a.policy.notna()]
        for nm in ("mda", "mda_mt"):
            q = np.percentile(x[nm], [25, 50, 75])
            mda.append(dict(row=rid, policy=g, stat=nm, n=len(x), q25=q[0], median=q[1], q75=q[2]))
save(pd.DataFrame(mda), "mda.csv")
p4 = []
for c in AF:
    pm = PRIM_L2["1a"][c]
    if pm in l3.P4:
        p4.append(dict(FundCode=c, primary=pm, group=GOF[c], alpha_M1=Q.loc[c, "alpha_full_1"], t_M1=Q.loc[c, "t_full_1"], bh_M1=bool(Q.loc[c, "bh1"]), alpha_M2=Q.loc[c, "alpha_full_2"], t_M2=Q.loc[c, "t_full_2"], bh_M2=bool(Q.loc[c, "bh2"]),
                       alpha_refFX_1a=A("ref_FX_1a", "full").loc[c, "alpha_pct"], bh_refFX_1a=bool(A("ref_FX_1a", "full").loc[c, "bh"]), alpha_refFX_1c=A("ref_FX_1c", "full").loc[c, "alpha_pct"], bh_refFX_1c=bool(A("ref_FX_1c", "full").loc[c, "bh"])))
save(pd.DataFrame(p4), "alpha_p4.csv")
log(f"เขียน alpha_q2 · alpha_bh_list · alpha_div · alpha_by_set · alpha_by_group · mda · alpha_p4 · ff_boot_summary · p_boot frac_BH {pb} → ป้าย 'แยกจากโชคไม่ได้' = {LUCK}")

# ───────────────────────── 10) factor เฉพาะกลุ่ม ─────────────────────────
CAND = pd.concat([l3.residualize(M28, BASES["1a"], mtr)[0], l3.ext_excess(pd.read_parquet(D_ / "factors_ext_weekly.parquet"), F)], axis=1)
GFR, GFF, GNAMES, GNULL, G0R = [], [], [], [], []
E_AF = [c for c in AF if polA[c] == "E"]
E_ctr = [c for c in E_AF if full_train[c]]
E_reps = list(l4.cluster_reps(E_ctr, CLU).values())
for b in BASES:
    r = ROWS["M1" if b == "1a" else "M2"]
    fit_tr = l4.sub_fit(FIT[(r["id"], "train")][0], AFidx)
    fit_tr.coef = FIT[(r["id"], "train")][0].coef[AFidx]
    U_ = l4.resid_panel(R, r["prov"], fit_tr, AF)
    # G0
    g0 = l4.group_k(U_, [c for c in E_reps], mtr, n_perm=N_PERM)
    Zr = U_[E_ctr].to_numpy(float)[mtr]
    Zr = Zr[np.isfinite(Zr).all(1)]
    Zr = (Zr - Zr.mean(0)) / Zr.std(0)
    eg = nf.corr_eig(Zr)
    G0R.append(dict(base=b, n_rep=len(E_reps), k_ED=g0["k_ed"], k_PA=g0["k_pa"], k_g=g0["k_g"], flag=g0["flag"], eig1_share=g0["eig5"][0] / len(E_reps) if g0["eig5"] else np.nan,
                    eig1_5=g0["eig5"], n_all_ctr=len(E_ctr), k_ED_all=nf.onatski_ed(eg, 3), k_PA_all=int(nf.parallel_analysis(Zr, N_PERM, 0.95, SEED)), eig1_share_all=float(eg[0] / len(E_ctr))))
    for g in sorted(GT.group):
        gr = GT[GT.group == g].iloc[0]
        mem = gr.members.split(";")
        reps = [c for c in gr.reps.split(";") if c]
        method = gr.method
        row = dict(base=b, group=g, policy=gr.policy, n=gr.n, n_indep_all=gr.n_indep_all, n_indep_tr=gr.n_indep_tr, n_rep=gr.n_rep, method=method)
        if method == "small":
            row.update(verdict_i="N/A", note="กลุ่มเล็กเกิน")
            GFR.append(row)
            continue
        kg, meth = 1, "mean"
        if method == "PCA":
            kk = l4.group_k(U_, reps, mtr, n_perm=N_PERM)
            row.update(k_ED=kk["k_ed"], k_PA=kk["k_pa"], k_g=kk["k_g"], flag=kk["flag"], eig1_5=kk["eig5"])
            if kk["flag"] or kk["k_g"] is None:
                meth, kg = "mean", 1
                row["method"] = "LOO-mean (fallback " + kk["flag"] + ")"
            elif kk["k_g"] == 0:
                row.update(verdict_i="ไม่มี (k_g = 0)", note="PCA k_g = 0 = ไม่มี โดยตรง")
                GFR.append(row)
                continue
            else:
                meth, kg = "pca", kk["k_g"]
        gl = l4.group_factor_loo(U_, mem, CLU, meth, kg, mtr, reps=reps)
        res = {}
        for i in mem:
            jf = AF.index(i)
            d = l4.fit_with_factor(R[i].to_numpy(float), r["prov"].design(i), gl[i]["g"], mtr, mte)
            res[i] = d
            bc = l4.max_abs_corr(U_, i, gl[i]["peers"], mtr)
            GFF.append(dict(base=b, group=g, FundCode=i, method_i=gl[i]["method"], flag=gl[i]["flag"], n_peer=len(gl[i]["peers"]), d_r2_oos=d["d_r2_oos"], d_bic=d["d_bic"], d_adj_r2=d["d_adj_r2"],
                            alpha_new_pct=d["alpha_new"] * 5200 if d["ok"] else np.nan, max_abs_corr=bc[0], max_corr_peer=bc[1], near_copy=bool(bc[0] >= 0.90) if np.isfinite(bc[0]) else False))
        okm = [i for i in mem if res[i]["ok"]]
        med_r = float(np.nanmedian([res[i]["d_r2_oos"] for i in okm])) if okm else np.nan
        med_b = float(np.nanmedian([res[i]["d_bic"] for i in okm])) if okm else np.nan
        # mean|corr| ก่อน/หลัง (train)
        Ub = U_[okm].loc[mtr]
        cb = Ub.corr().abs().to_numpy()
        before = float(np.nanmean(cb[np.triu_indices(len(okm), 1)])) if len(okm) > 1 else np.nan
        Ra = pd.DataFrame({i: res[i]["resid_new"] for i in okm}, index=idx).loc[mtr]
        ca = Ra.corr().abs().to_numpy()
        after = float(np.nanmean(ca[np.triu_indices(len(okm), 1)])) if len(okm) > 1 else np.nan
        row.update(n_fit=len(okm), med_d_r2_oos=med_r, med_d_bic=med_b, mean_abs_corr_before=before, mean_abs_corr_after=after, method_used=meth, k_used=kg)
        # null
        if gr.policy == "E" and g.startswith("MSCI_"):
            memset = set(mem)

            def delta_fn(i, gg, r=r):
                return l4.fit_with_factor(R[i].to_numpy(float), r["prov"].design(i), gg, mtr, mte)["d_r2_oos"]

            if meth == "pca":
                pool_fn = lambda i, memset=memset: [c for c in E_reps if c not in memset and CLU[c] != CLU[i]]
            else:
                pool_fn = lambda i, memset=memset: [c for c in E_AF if c not in memset and CLU[c] != CLU[i]]
            n_peer = {i: len(gl[i]["peers"]) for i in okm}
            nseed = np.random.default_rng(SEED).integers(0, 2**31)  # seed ใหม่ต่อ (กลุ่ม×ฐาน) ผ่าน default_rng(SEED) · กลุ่มเรียงชื่อ
            dr = l4.random_group_null(delta_fn, okm, pool_fn, n_peer, meth, kg, U_, mtr, n_draw=N_NULL, seed=SEED)
            ns = l4.null_summary(med_r, dr)
            row.update(null_p95=ns["null_p95"], null_median=ns["null_median"], p_null=ns["p_null"], null_type="b")
            for dd_, v in enumerate(dr):
                GNULL.append(dict(base=b, group=g, draw=dd_, median_d_r2_oos=v))
            ok1 = bool(np.isfinite(med_r) and med_r >= 0.02 and med_b <= 0 and med_r > ns["null_p95"])
        else:
            row.update(null_type="N/A (ไม่มี null — เชิงบรรยาย)")
            ok1 = bool(np.isfinite(med_r) and med_r >= 0.02 and med_b <= 0)
        row.update(q1_pass_base=ok1)
        # ตั้งชื่อ: factor ฉบับรวมทั้งกลุ่ม
        allp = reps if meth == "pca" else mem
        gfull = l4.peer_factor(U_, allp, meth, kg, mtr)[:, 0]
        nm_rows = []
        for cn in CAND.columns:
            cv = CAND[cn].to_numpy(float)
            ctr_ = np.isfinite(gfull) & np.isfinite(cv) & mtr
            cte_ = np.isfinite(gfull) & np.isfinite(cv) & mte
            nm_rows.append((cn, float(np.corrcoef(gfull[ctr_], cv[ctr_])[0, 1]) if ctr_.sum() > 30 else np.nan, float(np.corrcoef(gfull[cte_], cv[cte_])[0, 1]) if cte_.sum() > 30 else np.nan))
        nm_rows.sort(key=lambda x: -min(abs(x[1]), abs(x[2])) if np.isfinite(x[1]) and np.isfinite(x[2]) else 0)
        for cn, ctr, cte in nm_rows[:3]:
            lab = "ชื่อ" if min(abs(ctr), abs(cte)) >= 0.7 else ("คล้าย" if min(abs(ctr), abs(cte)) >= 0.5 else "ไม่ชัด")
            GNAMES.append(dict(base=b, group=g, candidate=cn, corr_train=ctr, corr_test=cte, label=lab))
        GFR.append(row)
        log(f"factor กลุ่ม {b} {g} [{row['method']}] n_fit={len(okm)} med ΔR²oos={med_r:.4f} med ΔBIC={med_b:.2f}")
GR = pd.DataFrame(GFR)
GRb = []
for g, d in GR.groupby("group"):
    q = d.set_index("base")
    if "q1_pass_base" in d.columns and d.q1_pass_base.notna().any():
        passes = [bool(q.q1_pass_base.get(b)) if pd.notna(q.q1_pass_base.get(b)) else False for b in BASES]
        GRb.append(dict(group=g, q1_overall="มี" if all(passes) else ("บางส่วน" if any(passes) else "ไม่มี")))
    else:
        GRb.append(dict(group=g, q1_overall=("N/A (กลุ่มเล็กเกิน)" if (d.method == "small").all() else "ไม่มี (k_g = 0)")))
GR = GR.merge(pd.DataFrame(GRb), on="group", how="left")
# q_BH (บรรยาย) ของ p_null ข้ามกลุ่ม G-E ต่อฐาน
GR["q_BH_p_null"] = np.nan
for b in BASES:
    m = (GR.base == b) & GR.p_null.notna() if "p_null" in GR.columns else None
    if m is not None and m.sum():
        GR.loc[m, "q_BH_p_null"] = ts.bh(GR.loc[m, "p_null"].to_numpy(), 0.10)[1]
save(GR, "group_factor.csv")
save(pd.DataFrame(GFF), "group_factor_fund.csv")
save(pd.DataFrame(GNAMES), "group_names.csv")
save(pd.DataFrame(GNULL), "group_null.csv")
save(pd.DataFrame(G0R), "g0_pca.csv")
log("เขียน group_factor · group_factor_fund · group_names · group_null · g0_pca")

# ───────────────────────── 11) xsec ─────────────────────────
XS, XM = [], []
R2 = {}
for rid in ("M1", "M2", "M3", "M4"):
    R2[rid] = pd.Series(1 - FIT[(rid, "train")][0].adj_r2[AFidx], index=AF)
logaum_cov = float(CH.loc[CH.policy == "E", "log_aum"].notna().mean())
Cl = CLU
for rid in ("M1", "M2", "M3", "M4"):
    CH[f"omr_{rid}"] = R2[rid]
specs = []
for rid in ("M1", "M2", "M3", "M4"):
    specs.append((f"X2_{rid}", rid, "full", "E", "inv_var", ()))
for rid in ("M1", "M2"):
    specs += [(f"X1_{rid}", rid, "full", "ALL", "inv_var", ("F", "O")), (f"X3_{rid}", rid, "test", "E", "inv_var", ()), (f"X4_{rid}", rid, "full", "E", "ols", ()),
              (f"X5_{rid}", rid, "full", "E", "inv_var", ("log_aum",)), (f"XV1_{rid}", rid, "full", "ALL_le", "inv_var", ("F", "O")), (f"XV2_{rid}", rid, "full", "E_le", "inv_var", ()),
              (f"XE67_{rid}", rid, "full", "E67", "inv_var", ())]
for name, rid, w, subset, wt, extra in specs:
    d = CH.copy()
    d["omr"] = d[f"omr_{rid}"]
    if subset == "E":
        d = d[d.policy == "E"]
    elif subset == "ALL_le":
        d = d[(d.ter_src == "actual") & (d.ter_vintage == "le2025")]
    elif subset == "E_le":
        d = d[(d.policy == "E") & (d.ter_src == "actual") & (d.ter_vintage == "le2025")]
    elif subset == "E67":
        d = d[(d.policy == "E") & (d.in_E67 == 1)]
    cont = list(CONT)
    if "log_aum" in extra:
        if logaum_cov < 0.80:
            XM.append(dict(spec=name, row=rid, N=np.nan, note=f"N/A — log AUM ครอบคลุม E {logaum_cov:.2f} < 0.80"))
            continue
        cont.append("log_aum")
    d = d[d.ter.notna() & d.omr.notna() & d.FXb.notna()]
    if "log_aum" in extra:
        d = d[d.log_aum.notna()]
    bn = [c for c in BIN + [e for e in extra if e in ("F", "O")]]
    X, d2, dr = l4.build_x(d, cont, bn, GCOLS)
    a = A(rid, w)
    y, se = a.loc[X.index, "alpha_pct"].to_numpy(), a.loc[X.index, "se_pct"].to_numpy()
    okk = np.isfinite(y) & np.isfinite(se) & (se > 0)
    X, y, se = X[okk], y[okk], se[okk]
    gc = [c for c in X.columns if c.startswith("G_")]
    res = l4.xsec_wls(y, se, X, Cl[list(X.index)].to_numpy(), weights=wt, wald_cols=gc if gc else None, policy=d2.loc[X.index, "policy"].to_numpy())
    tab = res["coef"].reset_index().rename(columns={"index": "term"})
    tab.insert(0, "spec", name)
    tab.insert(1, "row", rid)
    XS.append(tab)
    XM.append(dict(spec=name, row=rid, window=w, subset=subset, weights=wt, N=res["N"], G=res["G"], K=res["K"], kish_n=res["kish_n"], kish_over_N=res["kish_n"] / res["N"], top10_share=res["top10_share"],
                   wald_group_p=res.get("wald", {}).get("p", np.nan), wald_q=res.get("wald", {}).get("q", np.nan), share_E=res["policy_share"].get("E", 0.0), share_F=res["policy_share"].get("F", 0.0),
                   share_O=res["policy_share"].get("O", 0.0), dropped_cols=";".join(dr["cols"]), dropped_funds=";".join(dr["funds"]), cols=";".join(X.columns)))
XSD = pd.concat(XS, ignore_index=True)
save(XSD, "xsec.csv")
save(pd.DataFrame(XM), "xsec_meta.csv")
save(CH.drop(columns=["ter_asof"]).assign(ter_asof=CH["ter_asof"].astype(str)), "chars.csv", index=True)
log("เขียน xsec.csv · xsec_meta.csv · chars.csv (เติม 1−R² ของ M1–M4 หลัง fit — คอลัมน์เดียวที่เขียนทีหลัง)")

# ───────────────────────── 12) FX gap · carry · bootstrap · GRS · PY · stability · rolling ─────────────────────────
fg_rows, fg_sum = [], []
GE = pd.Series({c: GOF[c] for c in E_AF})
cnt = GE.value_counts()
GE = GE[GE.isin(cnt[cnt >= 10].index) & GE.str.startswith("MSCI_")]
for b, (m, refm) in {"1a": ("M1", "ref_L3B_1a"), "1c": ("M2", "ref_L3B_1c")}.items():
    tab, sm = l4.fx_gap(A(refm, "full")["alpha_pct"], A(m, "full")["alpha_pct"], CH["FXb"], GE, min_n=10)
    tab.insert(0, "base", b)
    fg_rows.append(tab)
    sm["base"] = b
    fg_sum.append(sm)
save(pd.concat(fg_rows, ignore_index=True), "fx_gap.csv")
FGS = pd.DataFrame(fg_sum)
save(FGS, "fx_gap_summary.csv")
cd = l4.carry_diag(F)
save(pd.DataFrame([cd]), "carry_diag.csv")
# Δα = α(no FX) − α(FX) เทียบ β̂_FX × mean(FX)
dd_ = []
for b, (m, refm) in {"1a": ("M1", "ref_L3B_1a"), "1c": ("M2", "ref_L3B_1c")}.items():
    fm_ = FIT[(m, "full")][0]
    kfx = ROWS[m]["names"].index("FX")
    bfx = pd.Series(fm_.beta[AFidx, kfx], index=AF)
    da = A(refm, "full")["alpha_pct"] - A(m, "full")["alpha_pct"]
    alg = bfx * float(FXs[mfull].mean()) * 5200
    ok = da.notna() & alg.notna()
    dd_.append(dict(base=b, n=int(ok.sum()), corr_dalpha_vs_bfx_meanFX=float(np.corrcoef(da[ok], alg[ok])[0, 1]), median_dalpha_pct=float(da[ok].median()), median_bfx_meanFX_pct=float(alg[ok].median())))
save(pd.DataFrame(dd_), "dalpha_vs_bfx.csv")
# bootstrap CI median Δ
nb = [rid for rid in ROWS if ROWS[rid]["ref"]]
FLd = FL.set_index(["row", "FundCode"])
cols, mat = [], []
for rid in nb:
    x = FL[FL.row == rid]
    for c_ in ("d_adj_r2", "d_r2_oos", "d_bic"):
        cols.append((rid, c_))
        mat.append(x[c_].to_numpy())
Sb = np.column_stack(mat)
bs = ts.bootstrap_median(Sb, polE, pairs=(), n_boot=N_BOOT, seed=SEED)
brow = []
for g in ("E", "F", "O", "ALL"):
    ci = bs[g][0]
    mg_ = (polE == g) if g != "ALL" else np.ones(len(EVAL), bool)
    for j, (rid, c_) in enumerate(cols):
        brow.append(dict(group=g, row=rid, label=ROWS[rid]["label"], stat="median_" + c_, median=float(np.nanmedian(Sb[mg_, j])), lo=ci[0, j], hi=ci[1, j], note=CI_LABEL))
save(pd.DataFrame(brow), "bootstrap.csv")
# GRS · PY (ref-FX · ref-③a)
GRS_PORTS = pd.read_csv(S003 / "grs_ports.csv")
GRS_PORTS = GRS_PORTS[GRS_PORTS.port_set == "full"].set_index("FundCode")["port"]
pcols = sorted(GRS_PORTS.unique())
PX = np.full((len(idx), len(pcols)), np.nan)
PC_ = np.zeros((len(idx), len(pcols)), int)
for j, p in enumerate(pcols):
    Vv = R[list(GRS_PORTS.index[GRS_PORTS == p])].to_numpy(float)
    PC_[:, j] = np.isfinite(Vv).sum(axis=1)
    with np.errstate(invalid="ignore"):
        PX[:, j] = np.where(PC_[:, j] > 0, np.nansum(Vv, axis=1) / np.maximum(PC_[:, j], 1), np.nan)
base_rows = {"train": mtr & (POS >= 1), "test": mte & (POS >= 1)}
PDROP = {w: (PC_ < 3).any(axis=1) & m for w, m in base_rows.items()}
gr, pyr = [], []
for rid in ("ref_FX_1a", "ref_FX_1c", "ref_3a"):
    r = ROWS[rid]
    Xd = rg.lag_stack(r["base_df"].to_numpy(float))
    for w, m in base_rows.items():
        use = m & ~PDROP[w] & np.isfinite(Xd).all(1) & np.isfinite(PX).all(1)
        g = ts.grs(PX[use], Xd[use])
        gr.append(dict(row=rid, window=w, N_ports=len(pcols), T_used=int(use.sum()), L=g["L"], dof2=g["dof2"], F=g["F"], p=g["p"], mean_abs_alpha_pct=float(np.mean(np.abs(g["alpha"])) * 5200)))
    prov = rg.CommonFactors(r["base_df"])
    for w, funds in (("test", S["PYTE"]), ("train", S["PYTR"])):
        mk = base_rows[w] & np.isfinite(prov.design(funds[0])).all(axis=1)
        x = ts.py_null_bootstrap(R, prov, funds, mk, B=B_PY, block=4, seed=SEED)
        x.update(row=rid, window=w, role="หลัก" if w == "test" else "ภาคผนวก", m_regressors=2 * prov.K, note=("(N−1)ρ̄²>1 " if x["Nrho2"] > 1 else ""))
        pyr.append(x)
save(pd.DataFrame(gr), "grs.csv")
save(pd.DataFrame(pyr), "py.csv")
log("เขียน fx_gap · carry_diag · bootstrap · grs · py")
# stability H1/H2 · rolling (ref-FX)
sp_stab = pol[STAB].to_numpy()
st_rows, rl_rows = [], []
h1m, h2m = window_mask(idx, "H1") & (POS >= 1), window_mask(idx, "H2")
fullp = mfull & (POS >= 1)
for rid in ("M1", "M2", "M3", "M4", "H1", "H2", "ref_L3B_1a", "ref_L3B_1c", "ref_FX_1a", "ref_FX_1c", "ref_3a"):
    r = ROWS[rid]
    f1, f2 = fitr(r, h1m, None, STAB, 104)[0], fitr(r, h2m, None, STAB, 104)[0]
    for g in ("E", "F", "O", "ALL"):
        sel_ = (sp_stab == g) if g != "ALL" else np.ones(len(STAB), bool)
        rr = sc.stability_halves(f1.beta[sel_], f2.beta[sel_])
        for kk, fn in enumerate(r["names"]):
            st_rows.append(dict(row=rid, label=r["label"], policy=g, factor=fn, n_funds=int(sel_.sum()), r_raw=rr[kk]))
    if rid.startswith("ref_FX") or rid == "ref_3a":
        bw, bfull, starts = l2.rolling_betas(R, rg.CommonFactors(r["base_df"]), STAB, fullp)
        for g in ("E", "F", "O", "ALL"):
            sel_ = (sp_stab == g) if g != "ALL" else np.ones(len(STAB), bool)
            med, mn = sc.stability_rolling(bw[:, sel_, :], bfull[sel_])
            for kk, fn in enumerate(r["names"]):
                rl_rows.append(dict(row=rid, policy=g, factor=fn, n_funds=int(sel_.sum()), n_windows=len(starts), roll_median=med[kk], roll_min=mn[kk], corr_first_last=sc._corr(bw[0][sel_, kk], bw[-1][sel_, kk]),
                                    note="ปนความต่างของ β ระหว่าง policy — สูงเชิงกล" if g == "ALL" else ""))
save(pd.DataFrame(st_rows), "stability.csv")
save(pd.DataFrame(rl_rows), "rolling_104.csv")
log("เขียน stability · rolling_104")

# ───────────────────────── 13) เกณฑ์ที่ล็อก · ความคาดหมาย · results.md ─────────────────────────
X2 = {k: XSD[XSD.spec == k].set_index("term") for k in XSD.spec.unique()}
XMd = pd.DataFrame(XM).set_index("spec")
q3 = []
for term in ("ter", "DIV", "FXb", "omr"):
    row = dict(term=term)
    for rid in ("M1", "M2", "M3", "M4"):
        t = X2[f"X2_{rid}"]
        if term not in t.index:
            row[rid] = "ตัดคอลัมน์"
            continue
        lo, hi = t.loc[term, "ci_lo"], t.loc[term, "ci_hi"]
        row[rid] = f"{t.loc[term, 'coef']:.2f} [{lo:.2f}, {hi:.2f}]" + (" ไม่คร่อม0" if (lo > 0 or hi < 0) else " คร่อม0") + (" ∋−1" if term == "ter" and lo <= -1 <= hi else "")
    q3.append(row)
Q3 = save(pd.DataFrame(q3), "criteria_Q3.csv")
for rid in ("M1", "M2"):
    pass
json.dump(dict(M1_wald_p=float(XMd.loc["X2_M1", "wald_group_p"]), M2_wald_p=float(XMd.loc["X2_M2", "wald_group_p"])), open(OUT / "criteria_Q3_wald.json", "w"))
n_ev = int((Q.q2_verdict == "มีหลักฐาน α").sum())
crit = dict(Q2_n_with_evidence=n_ev, Q2_counts=Q.q2_verdict.value_counts().to_dict(), Q2_label=("แยกจากโชคไม่ได้" if LUCK else ""), p_boot_frac_bh=pb,
            FX_gap=FGS.to_dict("records"), Q1=dict(zip(GRb and [x["group"] for x in GRb], [x["q1_overall"] for x in GRb])))
json.dump(crit, open(OUT / "criteria_values.json", "w"), ensure_ascii=False, indent=1, default=str)

SC_E = SCORE[(SCORE.policy == "E") & SCORE.row.isin(["M1", "M2", "M3", "M4", "H1", "H2", "ref_L3B_1a", "ref_L3B_1c", "ref_FX_1a", "ref_FX_1c", "ref_3a"])]
exp = []


def ex_add(i, text, obs, ok):
    exp.append(dict(item=i, expectation=text, observed=obs, match=("ตรง" if ok else ("ไม่ตรง" if ok is False else "ไม่ได้ประเมิน"))))


sE = lambda rid, col: float(SCORE[(SCORE.row == rid) & (SCORE.policy == "E")][col].iloc[0])
ex_add(1, "FX ใน model: median adj R² (E) ของ M1/M2 สูงกว่า ref-L3B ≤ 0.01 · ΔBIC (E) ±3 · mean|α̂| train เปลี่ยน ≤ ±1 %/ปี",
       f"Δadj R² M1 {sE('M1', 'med_d_adj_r2'):.4f} M2 {sE('M2', 'med_d_adj_r2'):.4f} · ΔBIC M1 {sE('M1', 'med_d_bic'):.2f} M2 {sE('M2', 'med_d_bic'):.2f} · Δ|α| M1 {sE('M1', 'med_d_abs_alpha_pct'):.2f}",
       bool(sE("M1", "med_d_adj_r2") <= 0.01 and sE("M2", "med_d_adj_r2") <= 0.01 and abs(sE("M1", "med_d_bic")) <= 3 and abs(sE("M2", "med_d_bic")) <= 3))
ex_add(2, "BH (full) M1/M2 ผ่าน 0–8 กอง · BY ≤ BH · 'มีหลักฐาน α' ≤ 5 · ส่วนใหญ่ α<0 · M3/M4 ต่าง M1/M2 ≤ 1 กอง · ≥70% ของที่ผ่าน (i) ผ่าน (ii)",
       f"BH M1 {int(Q.bh1.sum())} M2 {int(Q.bh2.sum())} · BY M1 {int(Q.by1.sum())} M2 {int(Q.by2.sum())} · มีหลักฐาน {n_ev} · M3 {int(Q.bh3.sum())} M4 {int(Q.bh4.sum())}",
       bool(Q.bh1.sum() <= 8 and Q.bh2.sum() <= 8 and Q.by1.sum() <= Q.bh1.sum() and Q.by2.sum() <= Q.bh2.sum() and n_ev <= 5 and abs(Q.bh3.sum() - Q.bh1.sum()) <= 1 and abs(Q.bh4.sum() - Q.bh2.sum()) <= 1))
ex_add(3, "p_boot ของสัดส่วน BH > 0.10 · p1/p5 ของ t จริงต่ำกว่า null (p_boot<0.05) · p95/p99 ไม่เกิน null (p_boot>0.10)",
       f"p_boot frac_BH {pb} · p1 {[float(SFF[(SFF.row == r_) & (SFF.stat == 'p1_ALL')].p_boot_lower.iloc[0]) for r_ in ('M1', 'M2')]} p5 {[float(SFF[(SFF.row == r_) & (SFF.stat == 'p5_ALL')].p_boot_lower.iloc[0]) for r_ in ('M1', 'M2')]} p95 {[float(SFF[(SFF.row == r_) & (SFF.stat == 'p95_ALL')].p_boot_upper.iloc[0]) for r_ in ('M1', 'M2')]} p99 {[float(SFF[(SFF.row == r_) & (SFF.stat == 'p99_ALL')].p_boot_upper.iloc[0]) for r_ in ('M1', 'M2')]}",
       bool(all(v > 0.10 for v in pb.values()) and all(float(SFF[(SFF.row == r_) & (SFF.stat.isin(['p1_ALL', 'p5_ALL']))].p_boot_lower.max()) < 0.05 for r_ in ('M1', 'M2')) and all(float(SFF[(SFF.row == r_) & (SFF.stat.isin(['p95_ALL', 'p99_ALL']))].p_boot_upper.min()) > 0.10 for r_ in ('M1', 'M2'))))
_MDA = pd.DataFrame(mda)
mdE = lambda rid, nm, col: float(_MDA[(_MDA.row == rid) & (_MDA.policy == nm.split(':')[0]) & (_MDA.stat == nm.split(':')[1])][col].iloc[0])
ex_add(4, "median MDA (E · single) > 5 %/ปี · MDA_mt > 9 · กอง F median < 2", f"M1 E mda {mdE('M1', 'E:mda', 'median'):.2f} mda_mt {mdE('M1', 'E:mda_mt', 'median'):.2f} · F mda {mdE('M1', 'F:mda', 'median'):.2f} · M2 E {mdE('M2', 'E:mda', 'median'):.2f}",
       bool(mdE('M1', 'E:mda', 'median') > 5 and mdE('M1', 'E:mda_mt', 'median') > 9 and mdE('M1', 'F:mda', 'median') < 2))
ex_add(5, "signed α (full · E) median −1 ถึง −4 %/ปี", f"M1 {float(Q[Q.policy == 'E'].alpha_full_1.median()):.2f} · M2 {float(Q[Q.policy == 'E'].alpha_full_2.median()):.2f}",
       bool(-4 <= Q[Q.policy == 'E'].alpha_full_1.median() <= -1 and -4 <= Q[Q.policy == 'E'].alpha_full_2.median() <= -1))
dvs = pd.read_csv(OUT / "alpha_div_summary.csv")
ex_add(6, "class ปันผล: median α̂ ต่ำกว่ากองไม่ปันผลใน policy เดียวกัน ≥ 1 %/ปี", "diff (div − nodiv, M1): " + json.dumps({r_.policy: round(float(r_["diff"]), 2) for _, r_ in dvs.iterrows()}), bool((dvs["diff"].dropna() <= -1).all()) if dvs["diff"].notna().any() else None)
x2 = {rid: X2[f"X2_{rid}"] for rid in ("M1", "M2")}
t7 = {t: {rid: (float(x2[rid].loc[t, 'ci_lo']) <= 0 <= float(x2[rid].loc[t, 'ci_hi'])) if t in x2[rid].index else None for rid in x2} for t in ("ter", "DIV", "FXb", "omr", "d_v2026", "d_rate")}
ex_add(7, "X2: slope TER<0 · CI TER ครอบ 0 และ −1 อย่างน้อยฐานเดียว · DIV<0 CI ไม่คร่อม0 อย่างน้อยฐานเดียว · FXβ/1−R²/d_v2026 คร่อม0 · Wald กลุ่ม p>0.05 · X1: น้ำหนัก F>50% · Kish X1<0.25N · Kish X2≥0.5N_E",
       f"slope TER {[round(float(x2[r_].loc['ter', 'coef']), 2) for r_ in x2]} CI [{[ (round(float(x2[r_].loc['ter','ci_lo']),2), round(float(x2[r_].loc['ter','ci_hi']),2)) for r_ in x2]}] · DIV {[round(float(x2[r_].loc['DIV','coef']), 2) for r_ in x2]} · คร่อม0 {t7} · Wald p {[round(float(XMd.loc[f'X2_{r_}','wald_group_p']),3) for r_ in x2]} · X1 share_F {[round(float(XMd.loc[f'X1_{r_}','share_F']),2) for r_ in ('M1','M2')]} Kish/N X1 {[round(float(XMd.loc[f'X1_{r_}','kish_over_N']),2) for r_ in ('M1','M2')]} X2 {[round(float(XMd.loc[f'X2_{r_}','kish_over_N']),2) for r_ in ('M1','M2')]}",
       None)
ex_add(8, "FX gap: median ratio (กลุ่มที่คำนวณได้) ≤ 0.5", json.dumps(FGS[["base", "n_groups", "n_computable", "median_ratio", "na"]].to_dict("records"), default=float), bool(all((not r_.na) and r_.median_ratio <= 0.5 for r_ in FGS.itertuples())) if not FGS.na.all() else None)
ex_add(9, "ACWI_CD (PCA) k_g=1 'มี' ทั้งสองฐาน · CHINA_ALL (LOO) 'มี' ≥ฐานเดียว · ไม่มีใน ACWI/ACWI_EX_US/ASIA_EX_JAPAN/ACWI_IT · LOO อื่นผ่าน ≤ 2 · G-F ผ่าน (i)+(ii) · G-O ไม่ผ่าน", json.dumps({x["group"]: x["q1_overall"] for x in GRb}, ensure_ascii=False), None)
ex_add(10, "G0 บนตัวแทน: k_ED ≥ 1 · eigenvalue แรก < 10% ของ trace", json.dumps([{k_: v_ for k_, v_ in x.items() if k_ in ("base", "n_rep", "k_ED", "k_PA", "eig1_share", "k_ED_all", "eig1_share_all")} for x in G0R], default=float), None)
nm_ = pd.DataFrame(GNAMES)
ex_add(11, "ชื่อ factor กลุ่ม: ACWI_CD ใกล้ ARKK/QQQ (≥0.5) · CHINA_ALL ใกล้ KWEB/e ของ CHINA_A", "top-1 ต่อกลุ่ม ดู group_names.csv: " + json.dumps(nm_.groupby(["base", "group"]).head(1).query("group in ['MSCI_ACWI_CD','MSCI_CHINA_ALL_SHARES']")[["base", "group", "candidate", "corr_train", "corr_test", "label"]].round(2).to_dict("records"), ensure_ascii=False, default=float), None)
ex_add(12, "carry: R² trend ≥ 0.8 · uncentered share ≥ 0.5 · lag corr ≥ 0.8", json.dumps(cd, default=float), bool(cd["r2_trend"] >= 0.8 and cd["uncentered_share"] >= 0.5 and cd["lag1_corr"] >= 0.8))
ex_add(13, "รายเดือน: Spearman α̂ สัปดาห์ vs เดือน ≥ 0.8 · BH รายเดือน ≤ รายสัปดาห์", "ไม่ได้รันรายเดือนในรอบนี้ (ดู 'ค้าง')", None)
a14 = lambda rid, col: float(SCORE[(SCORE.row == rid) & (SCORE.policy == "E")][col].iloc[0])
ex_add(14, "ref-③a: median adj R² (E · train) ต่ำกว่า M1 ≥ 0.10 · BH(full) ≥ M1 · mean|α̂| (full · E) สูงกว่า M1", f"adjR2 ③a {a14('ref_3a', 'adjr2_med'):.3f} vs M1 {a14('M1', 'adjr2_med'):.3f} · BH ③a {int(Q.bh_ref3a.sum())} vs M1 {int(Q.bh1.sum())} · mean|α| full E ③a {a14('ref_3a', 'mean_abs_alpha_full_pct'):.2f} vs M1 {a14('M1', 'mean_abs_alpha_full_pct'):.2f}",
       bool(a14('M1', 'adjr2_med') - a14('ref_3a', 'adjr2_med') >= 0.10 and Q.bh_ref3a.sum() >= Q.bh1.sum() and a14('ref_3a', 'mean_abs_alpha_full_pct') > a14('M1', 'mean_abs_alpha_full_pct')))
sl = SELF.set_index(["row", "set"])
ex_add(15, "self-inclusion: mean|α̂| (full) E67 > in_PCA_sample (E) ภายใต้ M1 · ความต่างภายใต้ M2 น้อยกว่า M1", f"M1 E67 {sl.loc[('M1', 'E_E67'), 'mean_abs_alpha_pct']:.2f} vs in_PCA {sl.loc[('M1', 'E_in_PCA_sample'), 'mean_abs_alpha_pct']:.2f} · M2 E67 {sl.loc[('M2', 'E_E67'), 'mean_abs_alpha_pct']:.2f} vs {sl.loc[('M2', 'E_in_PCA_sample'), 'mean_abs_alpha_pct']:.2f}",
       bool(sl.loc[('M1', 'E_E67'), 'mean_abs_alpha_pct'] > sl.loc[('M1', 'E_in_PCA_sample'), 'mean_abs_alpha_pct'] and (sl.loc[('M2', 'E_E67'), 'mean_abs_alpha_pct'] - sl.loc[('M2', 'E_in_PCA_sample'), 'mean_abs_alpha_pct']) < (sl.loc[('M1', 'E_E67'), 'mean_abs_alpha_pct'] - sl.loc[('M1', 'E_in_PCA_sample'), 'mean_abs_alpha_pct'])))
ex_add(16, "XV2 (n=34): CI ของ slope TER กว้างกว่า X2 ≥ 2 เท่า · เครื่องหมาย slope ตรง X2 อย่างน้อยฐานเดียว · ASIA_EX_JAPAN รวมฐาน",
       json.dumps({r_: dict(w_ratio=round(float((X2[f'XV2_{r_}'].loc['ter', 'ci_hi'] - X2[f'XV2_{r_}'].loc['ter', 'ci_lo']) / (X2[f'X2_{r_}'].loc['ter', 'ci_hi'] - X2[f'X2_{r_}'].loc['ter', 'ci_lo'])), 2), sign_same=bool(np.sign(X2[f'XV2_{r_}'].loc['ter', 'coef']) == np.sign(X2[f'X2_{r_}'].loc['ter', 'coef'])), N=int(XMd.loc[f'XV2_{r_}', 'N']), dropped=XMd.loc[f'XV2_{r_}', 'dropped_cols']) for r_ in ('M1', 'M2')}, default=str), None)
GRi = GR.set_index(["base", "group"])
if "MSCI_ACWI_CD" in GR.group.values and "p_null" in GR.columns:
    pn = [float(GRi.loc[(b, "MSCI_ACWI_CD"), "p_null"]) for b in BASES]
    nmed = [float(GRi.loc[(b, "MSCI_ACWI_CD"), "null_median"]) for b in BASES]
    ex_add(17, "Q1 null (b): ACWI_CD p_null<0.05 ทั้งสองฐาน · median null ใน [−0.01, 0.01]", f"p_null {pn} · null median {nmed}", bool(all(p < 0.05 for p in pn) and all(-0.01 <= v <= 0.01 for v in nmed)))
else:
    ex_add(17, "Q1 null (b) ACWI_CD", "ไม่มีผล", None)
ex_add(18, "TER QA ผ่าน (ter_dropped=false) · ตรวจโครง 98.0% บน 205 กอง · กอง Rate = 2 · d_rate ถูกตัดใน X1/X2/XE67", f"ter_dropped={QA['ter_dropped']} · TT≥OF {QA['tt_ge_of']} · กอง Rate {len(QA['rate_funds'])} · d_rate ตัดแล้วใน X1/X2/XE67: {[ 'd_rate' in str(XMd.loc[k, 'dropped_cols']) for k in ('X1_M1', 'X2_M1', 'XE67_M1')]} · หลุดกอง {[str(XMd.loc[k, 'dropped_funds']) for k in ('X1_M1', 'X2_M1', 'XE67_M1')]}",
       bool((not QA['ter_dropped']) and len(QA['rate_funds']) == 2 and abs(QA['tt_ge_of']['frac'] - 0.980) < 0.005))
ex_add(19, "ไม่มีกลุ่มใดเข้า fallback (ed_small/ed_none/peer_small = 0)", f"flags group: {GR['flag'].fillna('').value_counts().to_dict() if 'flag' in GR.columns else {}} · peer_small ต่อกอง {int((pd.DataFrame(GFF).flag == 'peer_small').sum())}", bool(('flag' not in GR.columns or (GR['flag'].fillna('') == '').all()) and (pd.DataFrame(GFF).flag != 'peer_small').all()))
r20 = QA["rate_minus_actual_same_row"]
ex_add(20, "ตาราง Rate − Actual ตรงโครง: (ก) n 205 median +3.21 IQR 2.46–3.72 100% · (ข) n 103 median +3.39 100%", f"(ก) {r20} · (ข) {QA['rate_le2025_minus_actual_chosen']} · หมายเหตุ: n ใน α-family 206 (ไม่รวม MGAPVD) ต่างจาก designer ที่นับ EVAL 207 (205/103) ตัดสิน 'ตรง' จาก median/IQR/100% เท่านั้น", bool(abs(r20['median'] - 3.21) < 0.03 and r20['frac_pos_or_zero'] == 1.0 and r20['n'] in (204, 205)))
EXP = save(pd.DataFrame(exp), "expectations_vs_results.csv")
log("เขียน expectations_vs_results.csv · criteria_*")

# results.md
L = []
L.append("# results — S009 (L4 = S007 + S008 + S009) · ระยะ 1 (อธิบาย · ไม่นับ trial)\n")
L.append(f"สร้าง {datetime.now().isoformat(timespec='seconds')} · {'**SMOKE (รอบ debug — ไม่ใช่ผลรายงาน)**' if SMOKE else 'รอบรายงาน'} · seed {SEED}\n")
L.append("**ป้ายบังคับ:** (ก) ED ตรงกับแหล่งรอง ยังไม่เปิดต้นฉบับ Onatski 2010 · (ก2) PY ตรงต้นฉบับ แต่ (N−1)ρ̄²>1 → อ่าน p_boot · (ข) ช่วง test 2024–2025 ถูกใช้เลือกรูปแบบตั้งแต่ L1 → ไม่ใช่หลักฐานนอกช่วงที่อิสระ · (ค) ผลขึ้นกับค่าที่ยืนยัน 1–21 และค่าชั่วคราว 22–82 · (ง) เกณฑ์ L4 ออกแบบหลังเห็นผล L3 · (จ) แถว ⚠️ (ชุดเข้ม 5 ดัชนี) = เกณฑ์เปลี่ยนหลังเห็นผล · (ฉ) ธีม ACWI_CD = ธีมจากชื่อกอง · (ช) FundProfile/SecFundFee = snapshot · "
         "(ซ) TER ของ 161 กองเป็น Actual snapshot ปี 2026 (หลังช่วงศึกษา · ขัดข้อ 6 แต่เป็นคุณลักษณะกอง) อาจสะท้อนผลงานช่วงเดียวกับ α̂ (ย้อนทาง) → อ่านคู่ d_v2026 และ XV (n เล็ก) · 43 กองใช้ Actual รุ่น ≤ 2025 (as-of 2023 เกือบทั้งหมด) · 2 กองมีแค่ Rate และหลุดจาก regression ที่มี TER · ความหมายรหัส TT ยังไม่ยืนยันกับเอกสาร ก.ล.ต. · "
         "(ฌ) **α เทียบพอร์ตกองเพื่อน** — factor ①a/①c สร้างจาก NAV สุทธิค่าธรรมเนียมของกองชุดเดียวกัน ไม่ใช่ α เทียบ benchmark ที่ลงทุนได้ · (ญ) รายการ 'มีหลักฐาน α' = **เชิงบรรยาย ไม่ใช่หลักฐานนอกช่วงที่อิสระ — ยืนยันได้ด้วย forward test ระยะ 2 เท่านั้น** · ระยะ 1 ห้ามใช้เลือกกองหรือสรุปว่าลงทุนได้\n")
L.append("## 0. ความถูกต้องทางเทคนิค\n" + f"- sha256 ข้อมูล/spec/รีวิว ตรงทุกไฟล์ ({len(PIN)} pin + manifest L0) · lib 13 ไฟล์เดิมตรง S006 + l4.py · regression S003/S005/S006 ตรงทุกบิต (`regression_S003_S005_S006.json`: all_pass={REG['all_pass']})\n- test 50 (ref-L3B เทียบ S006 R3/R8/R5/R10) max diff = {T50.max_abs_diff.max():.2e} (เกณฑ์ 1e-10) · SPOT+CARRY=FX ≤ 1e-15\n- TER QA: TT≥OF {QA['tt_ge_of']} · ter_dropped={QA['ter_dropped']}\n")
L.append("### 0.1 ตาราง Rate − Actual / ความเสถียรข้ามรุ่น (ก่อน fit · p1 ของรีวิว S009)\n" + f"- (ก) แถวเดียวกัน: {QA['rate_minus_actual_same_row']}\n- (ข) Rate ≤ 2025 เร็วสุด − Actual ที่เลือก: {QA['rate_le2025_minus_actual_chosen']}\n- ข้ามรุ่น (Actual 2026 − Actual ≤ 2025): {QA['cross_vintage_stability']}\n- เซลล์ vintage×src×policy: {QA['cells']}\n")
L.append("## 1. ตารางคะแนน (train) — E / F / O / ALL\n" + md(SCORE[SCORE.row.isin(["M1", "M2", "M3", "M4", "H1", "H2", "ref_L3B_1a", "ref_L3B_1c", "ref_FX_1a", "ref_FX_1c", "ref_3a"])][["row", "policy", "n", "K", "adjr2_med", "adjr2_iqr", "r2oos_med", "r2oos_iqr", "r2gap_med", "mean_abs_alpha_pct", "mean_abs_alpha_full_pct", "signed_mean_alpha_pct", "bic_med", "med_d_adj_r2", "med_d_r2_oos", "med_d_bic", "bh_reject_train(EVAL207)", "bh_reject_full(EVAL207)"]]))
L.append("### 1.1 bootstrap CI ของ median Δ (" + CI_LABEL + ")\n" + md(pd.DataFrame(brow).query("group=='E'").round(4)))
L.append("### 1.2 GRS / PY (ref-FX, ref-③a · 17 พอร์ต)\n" + md(pd.DataFrame(gr)) + md(pd.DataFrame(pyr)[["row", "window", "role", "N", "T", "J", "p", "p_boot", "Nrho2", "note"]]))
L.append("### 1.3 ความเสถียร (r ดิบ H1/H2 · STAB 191) และ rolling 104 (ref-FX)\n" + md(pd.DataFrame(st_rows).query("policy=='E'")) + md(pd.DataFrame(rl_rows).query("policy=='E'")))
L.append("## 2. α รายกอง (α-family 206 · ป้าย ฌ ญ)\n### 2.1 BH / BY / MDA ต่อแถว (full)\n" + md(pd.DataFrame([dict(row=rid, window=w, n=int(len(d)), BH=int(d.bh.sum()), BY=int(d.by.sum()), median_alpha_E=float(d[d.policy == 'E'].alpha_pct.median()), median_mda_E=float(d[d.policy == 'E'].mda.median())) for (rid, w), d in AL.groupby(["row", "window"])])))
L.append("### 2.2 Q2 (S008 F) — จำนวนต่อคำตัดสิน\n" + md(Q.q2_verdict.value_counts().rename_axis("verdict").reset_index(name="n")) + f"\nป้าย: p_boot ของสัดส่วน BH = {pb} → {'**แยกจากโชคไม่ได้**' if LUCK else 'ไม่เข้าเงื่อนไขป้าย'}\n")
L.append("### 2.3 กองที่ผ่าน BH ในแถวใดแถวหนึ่ง (alpha_bh_list.csv)\n" + md(pd.read_csv(OUT / "alpha_bh_list.csv")[["Unnamed: 0", "policy", "group", "div", "alpha_full_1", "t_full_1", "bh1", "alpha_full_2", "bh2", "q2_verdict", "div_note", "q2_label", "cluster"]].rename(columns={"Unnamed: 0": "FundCode"})))
L.append("### 2.4 FF 2010 block bootstrap (ป้าย: ดัดแปลงจาก FF 2010 · moving block 4 สัปดาห์ ใช้ร่วมทุกกอง · undersampling ตาม Harvey–Liu 2022)\n" + md(SFF))
L.append("### 2.5 MDA (%/ปี · ป้าย MDA_mt = ขอบบนแบบ Bonferroni ของการปฏิเสธตัวแรกของ BH · การประมาณของ designer)\n" + md(pd.read_csv(OUT / "mda.csv")))
L.append("### 2.6 class ปันผล (alpha_div.csv · α<0 = 'อาจเป็นผลของ NAV ไม่รวมปันผล')\n" + md(pd.read_csv(OUT / "alpha_div_summary.csv")) + md(pd.read_csv(OUT / "alpha_div.csv")[["Unnamed: 0", "policy", "alpha_full_1", "t_full_1", "alpha_full_2", "bh1", "bh2", "mda1"]].rename(columns={"Unnamed: 0": "FundCode"})) + md(pd.read_csv(OUT / "alpha_mgapvd.csv")))
L.append("### 2.7 in_PCA_sample vs E67 (E) และชุดอื่น\n" + md(SELF))
L.append("### 2.8 ref-③a (ป้าย: α เทียบ factor ตลาดที่ลงทุนได้ · 4 factor ไม่มีประเทศ/sector → α รวม tilt) — ตารางไขว้ q2_vs_ref3a\n" + md(cross))
L.append("### 2.9 α ของกองหลัก P4 (alpha_p4.csv · 'ref-FX' คู่)\n" + md(pd.read_csv(OUT / "alpha_p4.csv").round(3)))
L.append("## 3. factor เฉพาะกลุ่ม (Q1)\n" + md(GR[[c for c in ["base", "group", "n", "n_indep_all", "n_indep_tr", "n_rep", "method", "k_ED", "k_PA", "k_g", "flag", "n_fit", "med_d_r2_oos", "med_d_bic", "mean_abs_corr_before", "mean_abs_corr_after", "null_p95", "null_median", "p_null", "q_BH_p_null", "null_type", "q1_pass_base", "q1_overall"] if c in GR.columns]]) + "\nป้าย: k_g ใช้ข้อมูลกอง i ในการนับจำนวนเท่านั้น (m8) · percentile 95 จาก 200 draw คลาดเคลื่อน MC ราว ±1.5 จุด percentile → อ่าน p_null คู่ · Q1 ข้ามกลุ่มไม่แก้ FDR (q_BH บรรยาย) · G-F/G-O ไม่มี null — เชิงบรรยาย\n")
L.append("### 3.1 G0 (diagnostic)\n" + md(pd.DataFrame(G0R).drop(columns=["eig1_5"])) + "eigenvalue 1–5: " + json.dumps([x["eig1_5"] for x in G0R]) + "\n")
L.append("### 3.2 ชื่อ factor กลุ่ม (top 3 · บรรยาย)\n" + md(pd.DataFrame(GNAMES).round(3)))
L.append("## 4. α ข้ามกอง ~ คุณลักษณะ (Q3 · ตัดสินด้วย X2 — ครอบเฉพาะกอง E)\n### 4.1 X2: coef [CI 95% CR1] ของ M1–M4\n" + md(Q3) + f"\nWald กลุ่ม (X2) p: {json.load(open(OUT / 'criteria_Q3_wald.json'))}\n")
L.append("### 4.2 ทุก regression (18) — meta\n" + md(pd.DataFrame(XM)))
L.append("### 4.3 สัมประสิทธิ์ (slope TER, DIV, FXβ, 1−R², d_v2026, d_rate) ทุก regression\n" + md(XSD[XSD.term.isin(["ter", "DIV", "FXb", "omr", "d_v2026", "d_rate"])][["spec", "term", "coef", "ci_lo", "ci_hi", "ci_lo_hc1", "ci_hi_hc1", "p_cr1"]]) + "\nป้าย: FXβ / 1−R² = regressor ที่ประมาณเอง (SE ไม่รวมความคลาดเคลื่อนขั้นแรก · EIV ทำให้ slope ลดเข้าหา 0) · รายงานทิศของ X3 คู่ · X1: slope ถูกกอง F ครอบงำเมื่อน้ำหนัก F > 50% (ดู share_F) · ข้อสรุป Q3 ครอบเฉพาะ E\n")
L.append("## 5. FX (H4.3) และ carry\n" + md(pd.read_csv(OUT / "fx_gap.csv")) + md(FGS) + md(pd.read_csv(OUT / "dalpha_vs_bfx.csv")) + md(pd.DataFrame([cd])) + "ป้าย H1/H2: α แยกจากผลของ CARRY ไม่ได้เมื่อ uncentered share สูง · คู่ lag ของ Dimson เกือบ collinear → อ่านได้เฉพาะ b0+b1 ของ CARRY\n")
L.append("## 6. เกณฑ์ที่ล็อก (ข้อ 7 ของ S007 · S008 C.3/E.4/F)\n" + f"- Q2: จำนวน 'มีหลักฐาน α' = {n_ev} · {Q.q2_verdict.value_counts().to_dict()} · ป้ายภาพรวม: {'แยกจากโชคไม่ได้' if LUCK else '(ไม่เข้าเงื่อนไขป้าย)'}\n- Q1 (ต่อกลุ่ม): {json.dumps({x['group']: x['q1_overall'] for x in GRb}, ensure_ascii=False)}\n- Q3: ดู 4.1 (CI ไม่คร่อม 0 / TER ∋ −1 / Wald p) — ผ่านฐานเดียว = 'บางส่วน'\n- FX: ดู 5 (median ratio ≤ 0.5 ทั้งสองฐาน)\n")
L.append("## 7. เทียบความคาดหมายล่วงหน้า (ตรง / ไม่ตรง ตามตัวเลข — ไม่อ้างสาเหตุ · รีวิว S009 p2: ห้ามอ้างว่า CI แคบลงเป็นผลของ N1)\n" + md(EXP))
L.append("## 8. การตัดสินใจของ analyst\nดู `decisions_pre_run.md` (เขียนก่อน fit) · ป้าย 'ค่าชั่วคราว 22–82' ใช้กับทุกตาราง\n")
L.append("## 9. ข้อจำกัด\n- ช่วง test ถูกใช้เลือกรูปแบบแล้ว (ข) · ทิศความเอียงของ α กองหลัก P4 ไม่ทราบ (P4 เลือกด้วย ΔR²_oos) · α ของ P4 = α เทียบ [f, ดัชนีดิบ]\n- TER: 161 กอง snapshot ปี 2026 · trade-off: ลดการปนแหล่ง (Rate 61→2) แต่เพิ่มรุ่น 2026 จาก 102 เป็น 161 → ความเสี่ยงย้อนทางเพิ่ม · ตัวตรวจคือ XV (power ต่ำ) · ความเสถียรข้ามรุ่น ดู 0.1\n- T สั้น power ต่ำ · ไม่พบ ≠ ไม่มี · กลุ่ม 5–9 กอง (LOO-mean) median แกว่งง่าย · CR1 กับ cluster ที่สร้างจากข้อมูล · NAV class ปันผลไม่รวมปันผล · twin test ทำไม่ได้ · SPOT/CARRY จาก ETF SHV\n- F (18) / O (14) n เล็ก · spike F 119 จุดยังไม่แก้ · ไม่ใช้ปี 2026 · ETF/MSCI ปิดเวลา NY\n")
L.append("## 10. ค้าง / ไม่ได้ทำในรอบนี้\n- รายเดือน (ความคาดหมายข้อ 13) · G-T ธีมของ ACWI_CD (LOO-mean) · rolling เฉพาะ ref-FX/③a · PY bootstrap เฉพาะ ref-FX / ref-③a (แถว M ต่อกอง = N/A เพราะ K ต่างกัน) · ดูหัวข้อ 'การรัน debug' (ถ้ามี)\n")
L.append("## 11. การรัน debug บนข้อมูลจริง (เปิดเผย · บทเรียน L3 m8)\n"
         "ก่อนรอบสุดท้าย รัน `run.py --smoke` (B_ff 8 · null 4 draw · n_perm 50 · PY B 19 · bootstrap 50 — ไม่ใช่ผลรายงาน) บนข้อมูลจริง 3 ครั้ง ผลเก็บที่ `scratch/factor-analyst_s009_smoke/` แก้โค้ดหลังจากนั้น 5 จุด (ไม่แก้ spec / ไม่เปลี่ยนสูตร):\n"
         "1. `run.py`: `AUM = io_l1.load_aum().reindex(idx)` (เดิม IndexError ความยาว mask 260 ≠ 292 แถว AUM) \n"
         "2. `lib/l4.py` `resid_panel`: coef ของ fit ผสม (`l3.merge_fits`) เติม NaN ที่คอลัมน์ PRIM สำหรับกองฐานล้วน → เลือกเฉพาะ coef จำกัด (ValueError matmul เดิม) + เพิ่ม test_s9_69b\n"
         "3. `run.py`: ตัวช่วย `mdE` เปลี่ยนจาก `DataFrame.query` เป็น boolean filter (กัน query ใช้ method call ใน @-expression) \n"
         "4. `run.py`: ข้อความ/เกณฑ์ตัดสินความคาดหมายข้อ 20 — ตัดสินจาก median / 100% และ n ∈ {204, 205} เพราะ α-family ตัด MGAPVD (designer นับ 205 รวม MGAPVD) \n"
         "5. `run.py`: ฟังก์ชันสรุป Q1 ต่อกลุ่ม — `bool(NaN)` ถูกนับเป็น True เมื่อ k_g = 0 (ไม่มี fit) → แก้เป็น False (พบจากการตรวจผล smoke · ทำให้ ACWI_CD ฐาน ①c k_g=0 ไม่ถูกนับว่า 'ผ่าน')\n"
         "ผล smoke ใช้ไม่ได้รายงาน · รอบรายงานรันหลังแก้ทั้งหมด (2 รอบ · repro_check.json)\n")
(OUT / "results.md").write_text("\n".join(L), encoding="utf-8")
meta = dict(created=datetime.now().isoformat(timespec="seconds"), runtime_sec=round(time.time() - T0, 1), seed=SEED, smoke=SMOKE, python=platform.python_version(),
            versions=dict(numpy=np.__version__, pandas=pd.__version__), data_sha256=man, pinned_sha256=PIN, lib_sha256=lib_hashes, B_ff=B_FF, n_null=N_NULL, n_perm=N_PERM, B_py=B_PY, n_boot=N_BOOT,
            output_sha256={p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(OUT.glob("*.csv"))})
json.dump(meta, open(OUT / "run_meta.json", "w"), ensure_ascii=False, indent=1, default=str)
log(f"เสร็จ · runtime {time.time() - T0:.1f}s")
