"""S012 run (F5-EO = S012 + S013) — เรียก lib เท่านั้น · ใช้ (ต้องรันจาก root ด้วย PYTHONPATH=.):
  python run.py --phase pre   [--out DIR]   # ไฟล์คัดเลือก (ก่อน fit แถวคะแนน)
  python run.py --phase full  [--out DIR]   # fit ทุกแถว + ผลทั้งหมด (คำนวณ phase pre ซ้ำแล้วตรวจว่าไฟล์ตรงทุกบิต)
  --sim  ข้อมูลจำลอง (smoke ไม่ใช่ผลรายงาน · ต้องใส่ --out)   --smoke  ลดจำนวนรอบสุ่ม (ไม่ใช่ผลรายงาน)
งาน F5-EO เชิงอธิบาย · ไม่นับ trial · ไม่แตะ trials.csv"""
import hashlib
import json
import platform
import shutil
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
import l1eo  # noqa: E402
import l2  # noqa: E402
import l3  # noqa: E402
import l4  # noqa: E402
import pca as pc  # noqa: E402
import regress as rg  # noqa: E402
import samples as sp  # noqa: E402
import scorecard as sc  # noqa: E402
import tests_stat as ts  # noqa: E402
from samples import window_mask  # noqa: E402

SEED = 20261015
ARGV = sys.argv
PHASE = ARGV[ARGV.index("--phase") + 1] if "--phase" in ARGV else "pre"
SIM = "--sim" in ARGV
SMOKE = "--smoke" in ARGV
assert PHASE in ("pre", "full")
N_PERM, B_PY, N_BOOT = (20, 19, 50) if SMOKE else (500, 999, 2000)
DEFAULT_OUT = Path(__file__).resolve().parent
OUT = Path(ARGV[ARGV.index("--out") + 1]) if "--out" in ARGV else DEFAULT_OUT
if SIM and OUT.resolve() == DEFAULT_OUT.resolve():
    sys.exit("--sim ต้องใส่ --out ที่ไม่ใช่ runs/S012")
OUT.mkdir(parents=True, exist_ok=True)
T0 = time.time()
RUN_SHA = io_l1.sha256_file(Path(__file__))
LOGF = open(OUT / ("run_pre.log" if PHASE == "pre" else "run.log"), "w")
TEAM, ROOT = io_l1.TEAM, io_l1.ROOT
SPEC_FILES = ["specs/S012_L1EO_split_factors.md", "specs/S013_L1EO_addendum_to_S012.md"]


def log(msg):
    line = f"[{datetime.now().isoformat(timespec='seconds')} +{time.time() - T0:7.1f}s] {msg}"
    LOGF.write(line + "\n")
    LOGF.flush()
    print(line, flush=True)


def _b(x):
    return x if isinstance(x, bytes) else x.encode("utf-8")


def pre_write(name, content):
    """ไฟล์ของ phase pre: phase pre เขียน · phase full คำนวณซ้ำแล้วต้องตรงทุกบิตกับไฟล์ที่เขียนไว้"""
    p = OUT / name
    b = _b(content)
    if PHASE == "pre":
        p.write_bytes(b)
    else:
        assert p.exists(), f"phase pre ยังไม่ได้เขียน {name}"
        assert p.read_bytes() == b, f"{name}: ผลคำนวณซ้ำใน phase full ต่างจากที่เขียนใน phase pre"


def pre_csv(df, name, index=False):
    pre_write(name, df.to_csv(index=index))


def pre_json(obj, name):
    pre_write(name, json.dumps(obj, indent=1, sort_keys=True, ensure_ascii=False, default=_jdef))


def _jdef(o):
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, (np.bool_,)):
        return bool(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, (pd.Timestamp,)):
        return str(o)
    raise TypeError(type(o))


def save(df, name, index=False):
    assert PHASE == "full"
    df.to_csv(OUT / name, index=index)
    return df


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
            elif isinstance(v, (bool, np.bool_)):
                cells.append("✓" if v else "✗")
            else:
                cells.append(str(v).replace("|", "/"))
        out.append("| " + " | ".join(cells) + " |")
    return "\n".join(out) + "\n"


def med(x, m=None):
    x = np.asarray(x, float)
    if m is not None:
        x = x[np.asarray(m, bool)]
    x = x[np.isfinite(x)]
    return float(np.median(x)) if len(x) else np.nan


# ───────────────────────── 0) ตรวจก่อนแตะข้อมูล ─────────────────────────
log(f"run.py sha256={RUN_SHA} phase={PHASE} sim={SIM} smoke={SMOKE}")
if PHASE == "pre" and not SIM:
    shutil.copyfile(Path(__file__), OUT / "run_pre.py")  # สำเนา run.py ตอนเริ่ม phase pre (BRIEF 106)
    log("เก็บสำเนา run.py → run_pre.py")
PIN = {}
if not SIM:
    PIN = l1eo.check_pins()
    log(f"sha256 เต็ม {len(PIN)} ไฟล์ตาม S013 §4 ตรง")
    s10lib = json.load(open(TEAM / "runs" / "S010" / "run_meta.json"))["lib_sha256"]
    LIBH = io_l1.lib_hash()
    assert {k: v for k, v in LIBH.items() if k != "l1eo.py"} == s10lib and set(LIBH) - set(s10lib) == {"l1eo.py"}, "lib เดิม 15 ไฟล์ต่างจาก runs/S010/run_meta.json"
    REG = json.load(open(TEAM / "runs" / "S012" / "regression_S003_S006.json"))
    assert REG["all_pass"], "regression S003 / S006 ไม่ผ่าน"
    DEC = TEAM / "runs" / "S012" / "decisions_pre_run.md"
    assert DEC.exists(), "ต้องเขียน decisions_pre_run.md ก่อนคำนวณผล"
    DEC_SHA = io_l1.sha256_file(DEC)
    log(f"lib เดิม 15 ไฟล์ตรง runs/S010 + l1eo.py · regression S003/S006 ผ่านทุกบิต · decisions_pre_run.md sha {DEC_SHA[:12]}…")
else:
    LIBH, DEC_SHA = io_l1.lib_hash(), "sim"

# ───────────────────────── 1) ข้อมูล · หน่วย · ชุดกอง ─────────────────────────
g = l1eo.load_group_map()
CODES = list(g["FundCode"])
gu = g.drop_duplicates("unit").set_index("unit").sort_index()
pol = gu["policy"]
UNITS = list(gu.index)
F0 = io_l1.load_factors("W")
if SIM:
    F = l1eo.sim_factors(F0, SEED + 1)
    Feo = l1eo.sim_factors(l1eo.load_eo("W", verify=False), SEED + 2)
    Fext = l1eo.sim_factors(l1eo.load_ext("W"), SEED + 3)
    nrows = (g.set_index("FundCode")[["n_train_rows", "n_test_rows"]].sum(axis=1) + 1).clip(upper=260)
    Rc = l1eo.sim_returns(CODES, g.set_index("FundCode")["policy"], F, Feo, Fext, seed=SEED + 4, n_weeks=nrows)
    wk = pd.Timestamp(l1eo.SPLICE_WEEK)
    for u, (o, n) in l1eo.SPLICE_TABLE.items():
        Rc.loc[Rc.index > wk, o] = np.nan
        Rc.loc[Rc.index < wk, n] = np.nan
        Rc.loc[wk, o] = 0.0
    Fm = l1eo.sim_factors(io_l1.load_factors("M"), SEED + 5)
    Feom = l1eo.sim_factors(l1eo.load_eo("M", verify=False), SEED + 6)
    Fextm = l1eo.sim_factors(l1eo.load_ext("M"), SEED + 7)
    Rmc = l1eo.sim_returns(CODES, g.set_index("FundCode")["policy"], Fm, Feom, Fextm, seed=SEED + 8)
else:
    F = F0
    Feo, Fext = l1eo.load_eo("W"), l1eo.load_ext("W")
    Fm, Feom, Fextm = io_l1.load_factors("M"), l1eo.load_eo("M"), l1eo.load_ext("M")
    Rc = io_l1.load_returns("W")[CODES]
    Rmc = io_l1.load_returns("M")[CODES]
assert (F.index == Feo.index).all() and (F.index == Fext.index).all() and F.index.max() <= pd.Timestamp(io_l1.MAIN_END)
R, SPL = l1eo.splice_units(Rc)
Rm = l1eo.splice_monthly(Rmc)
assert list(R.columns) == UNITS and list(Rm.columns) == UNITS
idx = R.index
POS = np.arange(len(idx))
MASKS = {n: window_mask(idx, n) for n in ("train", "test", "H1", "H2", "full")}
MASKS["pos1"] = POS >= 1
MASKS["ptr"] = MASKS["train"] & (idx <= pd.Timestamp("2022-06-24"))
MASKS["pte"] = MASKS["train"] & (idx >= pd.Timestamp("2022-07-01"))
mtr, mte = MASKS["train"], MASKS["test"]
UNI = pd.read_csv(TEAM / "data" / "universe.csv").set_index("FundCode")
dup = io_l1.load_dup_pairs()
SETS = l1eo.eo_sets(R, pol, dup)
if not SIM:
    DIFF = l1eo.compare_sets(SETS, pd.read_csv(TEAM / "specs" / "S013_pca_sets.csv"))
    assert DIFF == {}, f"รายชื่อชุดกองไม่ตรง S013_pca_sets.csv: {DIFF}"
    cnt = SETS.groupby("policy")[l1eo.SET_COLS].sum()
    assert cnt.loc["E"].tolist() == [163, 160, 196, 141, 199, 97, 185] and cnt.loc["O"].tolist() == [12, 12, 13, 12, 13, 7, 13], cnt
    log("รายชื่อหน่วยทุกชุด (SEL·EVAL·EVAL52·STAB·ตัดซ้ำ·PCA balanced 97·unbalanced 185) ตรง S013_pca_sets.csv ทุกหน่วย")
else:
    DIFF = {}


def LS(p, c):
    return sorted(SETS.loc[(SETS["policy"] == p) & SETS[c], "unit"])


SEL_E, EVAL_E, EVAL52_E, STAB_E, DED_E, BAL_E, UNB_E = (LS("E", c) for c in ("sel", "eval", "eval52", "stab", "dedup_keep", "pca_balanced", "pca_unbal52"))
SEL_O, EVAL_O, EVAL52_O, STAB_O = (LS("O", c) for c in ("sel", "eval", "eval52", "stab"))
O_UNITS = [u for u in UNITS if pol[u] == "O"]
E_UNITS = [u for u in UNITS if pol[u] == "E"]
log(f"ชุดกอง E: SEL {len(SEL_E)} EVAL {len(EVAL_E)} EVAL52 {len(EVAL52_E)} STAB {len(STAB_E)} ตัดซ้ำ {len(DED_E)} PCA {len(BAL_E)}/{len(UNB_E)} · O: SEL {len(SEL_O)} EVAL {len(EVAL_O)} EVAL52 {len(EVAL52_O)} STAB {len(STAB_O)}")
GOLD_U = [u for u in O_UNITS if gu.loc[u, "o_group"] == "ทอง"]
REIT_U = [u for u in O_UNITS if gu.loc[u, "o_group"] == "REIT"]
assert len(GOLD_U) == 7 and len(REIT_U) == 6
O_SUB_REIT = {"DAOL-USREIT": "REIT-US", "TUSREIT": "REIT-US", "IREITG": "REIT-Global", "LHPROPG-A": "REIT-Global", "PRINCIPAL GREITs": "REIT-Global",
              "ONEPROP-SG": "REIT-Singapore"}
OSUB = {u: (O_SUB_REIT[u] if u in REIT_U else f"ทอง-Flag {gu.loc[u, 'fx_risk_flag']}") for u in O_UNITS}
assert set(O_SUB_REIT) == set(REIT_U)
GRP = gu["group"].copy()  # กลุ่มชื่อต่อหน่วย (E) · O = ทอง / REIT
DIV = pd.Series({u: bool((UNI.loc[[c for c in g.loc[g.unit == u, "FundCode"]], "div_flag"] == "Y").any()) for u in UNITS})

# ───────────────────────── 2) ไฟล์ phase pre ─────────────────────────
pre_csv(SPL.assign(n_train_dimson=[int(R[u].loc[mtr & MASKS["pos1"]].notna().sum()) for u in SPL["unit"]],
                   n_test=[int(R[u].loc[mte].notna().sum()) for u in SPL["unit"]],
                   label="ต่อรหัสโดยกติกาของ designer (ญ) · ต่อใน run ไม่แก้ panel L0 · S013 §2 สัปดาห์ซ้อนใช้รหัสใหม่"), "units_splice.csv")
SETS_OUT = SETS.merge(gu[["group", "group_factor", "fx_risk_flag"]].reset_index(), on="unit", how="left")
pre_csv(SETS_OUT, "sets.csv")
E_BG = l1eo.build_groups(g[["FundCode", "name_en", "fund_class", "splice_id", "policy"]]).set_index("FundCode")
gm_chk = g.set_index("FundCode").loc[E_BG.index]
GM_OK = dict(name_group=bool((E_BG["name_group"] == gm_chk["name_group"].fillna("NONE")).all()), group=bool((E_BG["group"] == gm_chk["group"]).all()),
             group_factor=bool((E_BG["group_factor"] == gm_chk["group_factor"]).all()), alt=bool((E_BG["alt_factor_no_synonym"] == gm_chk["alt_factor_no_synonym"]).all()))
assert all(GM_OK.values()), GM_OK
GCNT = pd.DataFrame({"n_U_units": gu[gu.policy == "E"].groupby("group").size(),
                     "n_fit_SEL": gu[gu.policy == "E"].groupby("group").apply(lambda d: int(d.index.isin(SEL_E).sum()), include_groups=False),
                     "n_EVAL": gu[gu.policy == "E"].groupby("group").apply(lambda d: int(d.index.isin(EVAL_E).sum()), include_groups=False),
                     "n_STAB": gu[gu.policy == "E"].groupby("group").apply(lambda d: int(d.index.isin(STAB_E).sum()), include_groups=False)})
GF_COUNT = gu[gu.policy == "E"].groupby("group_factor").agg(n_U=("group", "size")).join(
    pd.DataFrame({"n_EVAL": gu[gu.policy == "E"].groupby("group_factor").apply(lambda d: int(d.index.isin(EVAL_E).sum()), include_groups=False)}))
pre_json(dict(group_map_sha256=io_l1.sha256_file(TEAM / "specs" / "S012_group_map.csv"), n_codes=len(g), n_units=len(UNITS), recomputed_equals_csv=GM_OK,
              n_units_E=len(E_UNITS), n_units_O=len(O_UNITS), n_group_factor_E_units=int((gu[gu.policy == "E"].group_factor != "ไม่มี").sum()),
              n_eval_with_factor=int(((gu.group_factor != "ไม่มี") & gu.index.isin(EVAL_E)).sum()), group_counts=GCNT.to_dict(orient="index"),
              group_factor_counts=GF_COUNT.to_dict(orient="index")), "group_map_check.json")
log("เขียน units_splice.csv · sets.csv · group_map_check.json")

REPS, CL_SEL = l1eo.sel_reps(R, SEL_E, mtr)
pre_csv(CL_SEL.merge(REPS[["group_id", "rep"]], on="group_id").assign(is_rep=lambda d: d["FundCode"] == d["rep"]), "sel_reps.csv")
log(f"เขียน sel_reps.csv · ตัวแทนกลุ่มกองอิสระ {len(REPS)} (จาก SEL_E {len(SEL_E)})")
CORE, POOL, ECOEF = l1eo.pool_E(F, Fext, Feo, mtr)
PSEUDO = (MASKS["ptr"], MASKS["pte"])
RSPEC = l1eo.resid_spec_E(F)
PL = l1eo.placebo_eo(R, CORE, POOL, mtr, list(REPS["rep"]), pseudo=PSEUDO)
pre_json(dict(shifts=PL["shifts"], tau=PL["tau"], tau0=PL["tau0"], any_selected=PL["any_selected"], rule=PL["rule"],
              n_candidates_evaluated=PL["n_candidates_evaluated"], logs=PL["logs"].to_dict(orient="records"),
              note="ตามกฎ S012 ข้อ 4.3 + m8 (e_CHINA เลื่อนหลัง residualize · G3 ไม่ residualize ซ้ำ)"), "placebo_E.json")
log(f"เขียน placebo_E.json (ก่อน selection จริง) · τ = {PL['tau']} · placebo เลือก {[v['n_selected'] for v in PL['shifts'].values()]}")
SELECTED, STEP_LOG, STEP_ALL = l1eo.stepwise_eo(R, CORE, POOL, mtr, list(REPS["rep"]), tau=PL["tau"], pseudo=PSEUDO, resid_spec=RSPEC)
pre_csv(STEP_LOG, "stepwise_E.csv")
pre_csv(STEP_ALL, "stepwise_E_all_candidates.csv")
X1 = pd.concat([CORE, POOL[SELECTED]], axis=1) if SELECTED else CORE.copy()
log(f"เขียน stepwise_E.csv · E-X1 = {list(X1.columns)}")
# A1: style ETF แทน KF (pool 10 · ไม่มี factor กลุ่ม)
CORE_A1, POOL_A1, _ = l1eo.pool_E(F, Fext, Feo, mtr, variant="A1")
PL_A1 = l1eo.placebo_eo(R, CORE_A1, POOL_A1, mtr, list(REPS["rep"]), pseudo=PSEUDO)
SEL_A1, LOG_A1, ALL_A1 = l1eo.stepwise_eo(R, CORE_A1, POOL_A1, mtr, list(REPS["rep"]), tau=PL_A1["tau"], pseudo=PSEUDO, resid_spec=RSPEC, tag="A1")
pre_csv(pd.concat([LOG_A1, ALL_A1], ignore_index=True), "stepwise_A1.csv")
pre_json(dict(tau=PL_A1["tau"], shifts=PL_A1["shifts"], selected=SEL_A1, n_candidates_evaluated=PL_A1["n_candidates_evaluated"]), "placebo_A1.json")
X1_A1 = pd.concat([CORE_A1, POOL_A1[SEL_A1]], axis=1) if SEL_A1 else CORE_A1.copy()
GM_E = gu[gu.policy == "E"].reset_index()[["unit", "group_factor"]]
E_G, PF, PFN, GCOEF, GSPAN = l1eo.group_factors(GM_E, F, Fext, X1, mtr)
pre_csv(GCOEF, "group_factor_coef.csv")
pre_csv(GSPAN, "group_factor_span.csv")
EP = l1eo.epca_build(R, BAL_E, UNB_E, mtr, n_perm=N_PERM, seed=SEED)
pre_json(dict(ks=EP["ks"], k_star=EP["kstar"], k_used=EP["k"], T=EP["T"], N=EP["N"], eig_corr_first15=EP["eig"][:15], em_iter=EP["em_iter"], em_converged=EP["em_conv"],
              ed_converged=EP["ks"]["ED"] is not None, n_balanced=len(BAL_E), n_unbalanced=len(UNB_E),
              Lam_a_sha256=hashlib.sha256(np.ascontiguousarray(EP["Lam_a"]).tobytes()).hexdigest(), sd_a_sha256=hashlib.sha256(np.ascontiguousarray(EP["sd_a"]).tobytes()).hexdigest()),
         "pca_E.json")
HY = l1eo.hybrid_eo(R, X1, mtr, BAL_E)
pre_json(dict(k_res=HY["k_res"], eig_resid_first8=HY["eig"][:8], T=HY["T"], n_funds=len(BAL_E), n_factors_EH=int(HY["EH"].shape[1]),
              n_params_EH=int(2 * HY["EH"].shape[1] + 1)), "hybrid_E.json")
OF = l1eo.o_factors(F, Fext, Feo, mtr)
pre_csv(OF["reit_coef"], "o_factor_coef.csv")
log(f"เขียน group_factor_coef.csv · pca_E.json (k* = {EP['kstar']}) · hybrid_E.json (k_res = {HY['k_res']}) · o_factor_coef.csv · stepwise_A1.csv (A1 = {SEL_A1})")
GRP_E = GRP[EVAL_E]
PORTS = l1eo.grs_ports(GRP_E)
pre_csv(PORTS.rename("port").reset_index().rename(columns={"index": "unit"}), "grs_ports.csv")
if not SIM:
    assert sorted(PORTS.unique()) == sorted(["CHINA", "HEALTH", "ASIA", "TECH", "EUROPE", "INNOV", "USA", "JAPAN", "VIETNAM", "GLOBAL", "NONE", "OTHER"]), sorted(PORTS.unique())

if PHASE == "pre":
    meta_pre = dict(created=datetime.now().isoformat(timespec="seconds"), phase="pre", run_py_sha256=RUN_SHA, seed=SEED, sim=SIM, smoke=SMOKE,
                    spec_files=SPEC_FILES, lib_sha256=LIBH, decisions_sha256=DEC_SHA, tau=PL["tau"], selected=SELECTED, k_star=EP["kstar"], k_res=HY["k_res"],
                    A1_selected=SEL_A1, runtime_sec=round(time.time() - T0, 1))
    (OUT / "run_meta_pre.json").write_text(json.dumps(meta_pre, indent=1, ensure_ascii=False, default=_jdef))
    log("phase pre เสร็จ · ไม่ได้ fit แถวคะแนนใดๆ")
    sys.exit(0)

# ═════════════════════════ phase full ═════════════════════════
log("เริ่ม phase full: คำนวณไฟล์ phase pre ซ้ำและตรวจว่าตรงทุกบิตแล้ว → fit แถวคะแนน")
META_PRE = json.load(open(OUT / "run_meta_pre.json"))
RUN_SHA_PRE = META_PRE["run_py_sha256"]
RUN_CHANGED = RUN_SHA_PRE != RUN_SHA
if RUN_CHANGED:
    log(f"คำเตือน: sha256 ของ run.py ต่างจาก phase pre ({RUN_SHA_PRE[:12]}… → {RUN_SHA[:12]}…) — ต้องมี diff ใน results.md (BRIEF 106)")

# ───────────── 3) แถวแข่ง · ตัวเทียบ ─────────────
FUNDS_E = EVAL52_E                       # ⊇ EVAL_E (fit pool)
IDX_E = {u: i for i, u in enumerate(FUNDS_E)}
POL_E = np.array(["E"] * len(FUNDS_E))
DIV_E = DIV[FUNDS_E].to_numpy()
S003_FAC = TEAM / "runs" / "S003" / "factors_S003_weekly.parquet"
if SIM:
    _ep4 = l1eo.epca_build(R, BAL_E, UNB_E, mtr, n_perm=N_PERM, k_override=4)
    B1A, B1C = _ep4["a1"], _ep4["a2"]
else:
    B1A, B1C = l2.load_l1_factors(S003_FAC, "1a"), l2.load_l1_factors(S003_FAC, "1c")
assert (B1A.index == idx).all() and (B1C.index == idx).all()
F3A = ex.line3(F, "3a")
M1_BASE, M1_PF = l1eo.build_M1(F, B1A, TEAM / "runs" / "S005" / "primary_index.csv", TEAM / "runs" / "S006" / "resid_B_coef.csv", FUNDS_E,
                                splice_units_set=set(l1eo.SPLICE_TABLE))
MODELS = {
    "E-PCA-a1": l1eo.Model("E-PCA-a1", EP["a1"], kind="pca", eig=(EP["eig"], EP["N"])),
    "E-PCA-a2": l1eo.Model("E-PCA-a2", EP["a2"], kind="pca"),
    "E-X0": l1eo.Model("E-X0", CORE, kind="x"),
    "E-X1": l1eo.Model("E-X1", X1, kind="x"),
    "E-X2": l1eo.Model("E-X2", X1, per_fund=PF, pf_name=PFN, kind="x2"),
    "E-H": l1eo.Model("E-H", HY["EH"], kind="h"),
    "①a": l1eo.Model("①a", B1A, kind="cmp"),
    "①c": l1eo.Model("①c", B1C, kind="cmp"),
    "③a": l1eo.Model("③a", F3A, kind="cmp"),
    "M1": l1eo.Model("M1", M1_BASE, per_fund=M1_PF, pf_name={u: "e_p(P4)" for u in M1_PF}, kind="cmp"),
}
ROWS_E = list(MODELS)
COMPETE = ["E-PCA-a1", "E-PCA-a2", "E-X0", "E-X1", "E-X2", "E-H"]
CMP = ["①a", "①c", "③a", "M1"]
COMMON = ["E-PCA-a1", "E-PCA-a2", "E-X0", "E-X1", "E-H", "①a", "①c", "③a"]       # แถวที่ factor ร่วมทุกกอง (GRS · PY)
FIT = {}
for nm, mdl in MODELS.items():
    FIT[nm] = l1eo.fit_model(R, mdl, mtr, mte, FUNDS_E, 52)
log("fit รายกองครบ " + str(len(FIT)) + " แถว (ชุด EVAL52 · min_obs 52)")
CL_EVAL_DF = l2.fund_clusters(R, mtr, EVAL_E)
CLU = CL_EVAL_DF.set_index("FundCode")["group_id"]
REPS_EVAL, _ = l1eo.sel_reps(R, EVAL_E, mtr)
REPSET_EVAL = set(REPS_EVAL["rep"])
SUBS = {"EVAL": EVAL_E, "EVAL52": EVAL52_E, "EVAL∩ตัดซ้ำ": [u for u in EVAL_E if u in set(DED_E)], "EVAL∩ตัวแทนกลุ่มอิสระ": [u for u in EVAL_E if u in REPSET_EVAL],
        "EVAL∩ใน PCA(97)": [u for u in EVAL_E if u in set(BAL_E)], "EVAL−นอก PCA(97)": [u for u in EVAL_E if u not in set(BAL_E)]}


def smask(lst):
    s = set(lst)
    return np.array([u in s for u in FUNDS_E])


def dbic(a, b, lst):
    fa, fb = FIT[a][0], FIT[b][0]
    m = smask(lst) & fa.ok & fb.ok
    return med(fa.bic - fb.bic, m)


# ───────────── 4) ตารางคะแนน E (6 ข้อ · ข้อ 1–4) ─────────────
srows = []
for nm in ROWS_E:
    fit, ro = FIT[nm]
    for sname, lst in SUBS.items():
        d = sc.score_model(fit, ro, POL_E, subset=smask(lst), div_flag=DIV_E)
        d = d[d["policy"] == "E"].iloc[0].to_dict()
        d.update(row=nm, set=sname, K=fit.K, p_max=2 * fit.K + 1, role="แข่ง" if nm in COMPETE else "ตัวเทียบ")
        d["dBIC_med_vs_E-X0"] = dbic(nm, "E-X0", lst)
        d["dBIC_med_vs_1a"] = dbic(nm, "①a", lst)
        srows.append(d)
SCORE_E = pd.DataFrame(srows)
cols_first = ["row", "role", "set", "n", "K", "p_max"]
SCORE_E = SCORE_E[cols_first + [c for c in SCORE_E.columns if c not in cols_first and c != "policy"]]

# bootstrap CI (สุ่มกลุ่มกองอิสระ) บน EVAL
ev_pos = np.array([IDX_E[u] for u in EVAL_E])
S_adj = np.column_stack([FIT[n][0].adj_r2[ev_pos] for n in ROWS_E])
S_oos = np.column_stack([FIT[n][1][ev_pos] for n in ROWS_E])
S_gap = np.column_stack([FIT[n][0].r2[ev_pos] - FIT[n][1][ev_pos] for n in ROWS_E])
nR = len(ROWS_E)
REFS = ["E-PCA-a1", "③a", "①a", "E-X1"]
clusters_arr = np.array([CLU[u] for u in EVAL_E])


def _bstat(i):
    m_adj, m_oos, m_gap = l1eo._nanmed(S_adj[i]), l1eo._nanmed(S_oos[i]), l1eo._nanmed(S_gap[i])
    d = [m_oos[j] - m_oos[ROWS_E.index(rf)] for rf in REFS for j in range(nR)]
    return np.r_[m_adj, m_oos, m_gap, d]


BS = l1eo.cluster_bootstrap(_bstat, clusters_arr, n=N_BOOT, seed=SEED)
mA, mO, mG = l1eo._nanmed(S_adj), l1eo._nanmed(S_oos), l1eo._nanmed(S_gap)
brow = []
for j, nm in enumerate(ROWS_E):
    brow += [dict(row=nm, stat="adjr2_med_train", value=mA[j], lo=BS["lo"][j], hi=BS["hi"][j]),
             dict(row=nm, stat="r2oos_med", value=mO[j], lo=BS["lo"][nR + j], hi=BS["hi"][nR + j]),
             dict(row=nm, stat="gap_med (R²train−R²oos)", value=mG[j], lo=BS["lo"][2 * nR + j], hi=BS["hi"][2 * nR + j])]
for ri, rf in enumerate(REFS):
    for j, nm in enumerate(ROWS_E):
        c = 3 * nR + ri * nR + j
        brow.append(dict(row=nm, stat=f"d_r2oos_med_vs_{rf} (จับคู่)", value=mO[j] - mO[ROWS_E.index(rf)], lo=BS["lo"][c], hi=BS["hi"][c]))
BOOT = pd.DataFrame(brow)
BOOT["note"] = f"CI สุ่ม**กลุ่มกองอิสระ**ทั้งก้อน {N_BOOT} รอบ · กลุ่ม {len(np.unique(clusters_arr))} (corr train ≥ 0.95 · single linkage) · CI แคบกว่าจริงถ้ากองข้ามกลุ่มยังสัมพันธ์กัน"
log(f"bootstrap {N_BOOT} รอบ (กลุ่มอิสระ {len(np.unique(clusters_arr))})")


def dmed(a, b, lst):
    fa, fb = FIT[a], FIT[b]
    m = smask(lst) & fa[0].ok & fb[0].ok
    return med(fa[1], m) - med(fb[1], m)


def BS_get(stat, row):
    r = BOOT[(BOOT["stat"] == stat) & (BOOT["row"] == row)].iloc[0]
    return r["value"], r["lo"], r["hi"]


# BH ของ α (EVAL · train)
bh_rows = []
for nm in ROWS_E:
    fit = FIT[nm][0]
    m = smask(EVAL_E) & fit.ok & np.isfinite(fit.t_alpha_hac)
    rej, adj = ts.bh(2 * stats.norm.sf(np.abs(fit.t_alpha_hac[m])), 0.10)
    bh_rows.append(dict(row=nm, n_EVAL=int(m.sum()), n_reject_bh10=int(rej.sum())))
BH_E = pd.DataFrame(bh_rows)

# ───────────── 5) GRS บนพอร์ตกลุ่ม · PY p_boot ─────────────
PC_, PX_, PCN_ = l1eo.port_returns(R, PORTS)
grs_rows = []
for nm in COMMON:
    Xd = rg.lag_stack(MODELS[nm].base.to_numpy(float))
    for w, mk in (("test", mte & MASKS["pos1"]), ("train", mtr & MASKS["pos1"])):
        d = l1eo.run_grs(PC_, PX_, PCN_, Xd, mk)
        d.update(row=nm, window=w, role="หลัก" if w == "test" else "รอง", ports=len(PC_))
        grs_rows.append(d)
GRS_E = pd.DataFrame(grs_rows)
GRS_E["note"] = "GRS บน 12 พอร์ต EW ตามคอลัมน์ group ที่มี ≥ 5 หน่วย EVAL (ที่เหลือ OTHER) · สมาชิก ≥ 3 ต่อสัปดาห์ · ช่วง test เป็นตัวหลัก (S012 ข้อ 7)"
log("GRS เสร็จ")
py_rows = []
for nm in COMMON:
    mdl = MODELS[nm]
    prov = rg.CommonFactors(mdl.base)
    finD = np.isfinite(prov.design()).all(axis=1)
    for w, mk0 in (("train", mtr & MASKS["pos1"]), ("test", mte)):
        mk = mk0 & finD
        fit0 = rg.fit_funds(R, prov, mk, 50, funds=EVAL_E)
        full = [u for u, n_, ok_ in zip(EVAL_E, fit0.n, fit0.ok) if ok_ and n_ == mk.sum()]
        if len(full) < 6:
            py_rows.append(dict(row=nm, window=w, N=len(full), note="N/A (กองครบทุกแถว < 6)"))
            continue
        r = ts.py_null_bootstrap(R, prov, full, mk, B=B_PY, block=4, seed=SEED)
        r.update(row=nm, window=w, m=2 * mdl.K, note="PY แบบต้นฉบับ (เฉพาะกองครบทุกแถวในหน้าต่าง) + null bootstrap ตามข้อ 29" + (" · (N−1)ρ̄²>1" if r["Nrho2"] > 1 else ""))
        py_rows.append(r)
PY_E = pd.DataFrame(py_rows)
log("PY null bootstrap เสร็จ")

# ───────────── 6) ความเสถียร (STAB_E) ─────────────
stab_parts = []
for nm in ROWS_E:
    d = l1eo.model_stability(R, MODELS[nm], STAB_E, MASKS)
    d.insert(0, "row", nm)
    stab_parts.append(d)
STAB_ALL = pd.concat(stab_parts, ignore_index=True)
STAB_MEAN = STAB_ALL[STAB_ALL["r_h1h2"].notna()].groupby("row")["r_h1h2"].mean().rename("mean_r_h1h2")
ROLL_MEAN = STAB_ALL[STAB_ALL["roll_first_last"].notna()].groupby("row")["roll_first_last"].mean().rename("mean_roll_first_last")
log("ความเสถียร + rolling 104 เสร็จ")

# ───────────── 7) รายงานราย factor (E) ─────────────
REF_BASE = pd.concat([ex.reference_set(F), l3.ext_excess(Fext, F),
                      Feo[[c for c in Feo.columns if c.startswith(("KF_", "JKP_", "GLD_", "VNQ", "DTWEX"))]]], axis=1)    # ไม่ใช้คอลัมน์ AQR (BRIEF 117 · n2)
assert not any(c.startswith("AQR") for c in REF_BASE.columns)
REF_BASE = REF_BASE.loc[:, ~REF_BASE.columns.duplicated()]


def ref_for(nm):
    parts = [REF_BASE]
    if nm != "①a":
        parts.append(B1A.add_prefix("①a_"))
    if nm != "①c":
        parts.append(B1C.add_prefix("①c_"))
    return pd.concat(parts, axis=1)


REPORT_ROWS = ["E-PCA-a1", "E-PCA-a2", "E-X1", "E-X2", "E-H", "①a", "①c", "③a"]
INTERP = {"E-PCA-a1": list(EP["a1"].columns), "E-PCA-a2": list(EP["a2"].columns), "E-H": list(HY["rpc"].columns), "①a": list(B1A.columns), "①c": list(B1C.columns)}
SHAP, FR_parts = {}, []
for nm in REPORT_ROWS:
    fit, ro = FIT[nm]
    ev = [u for u in EVAL_E if fit.ok[IDX_E[u]]]
    SHAP[nm] = l1eo.shapley_table(R, MODELS[nm], ev, MASKS, with_oos=True)
    ctx = dict(masks=MASKS, stab=STAB_E, clusters=CLU.to_dict(), group=GRP, ref=ref_for(nm), a1=B1A, axis="MKT", axis_series=CORE["MKT"])
    fr = l1eo.factor_report(R, MODELS[nm], fit, ro, EVAL_E, ctx, interpret_names=INTERP.get(nm, ()), shap=SHAP[nm], detail_common=(nm != "E-X2"))
    fr["role"] = "แข่ง" if nm in COMPETE else "ตัวเทียบ (บรรยาย)"
    FR_parts.append(fr)
    log(f"factor_report {nm}: {len(fr)} factor")
FR_E = pd.concat(FR_parts, ignore_index=True)
SHAP_E = pd.concat([d.assign(row=n) for n, d in SHAP.items()], ignore_index=True)

# สถานะ "n เล็ก" ของ factor กลุ่ม (ล็อก S012 ข้อ 8.3)
def small_flag(n):
    return "n เล็ก — คำตัดสินอ่านไม่ได้ (EVAL < 5)" if n < 5 else ("แกว่งง่าย (EVAL 5–7)" if n <= 7 else "")


# เลนส์ pseudo-OOS ของ factor กลุ่ม (diagnostic)
USE_AH = "e_CHINA" in X1.columns
X1p = X1.copy()
for c in X1p.columns:
    if c in RSPEC:
        X1p[c] = RSPEC[c](MASKS["ptr"])
GI = l1eo.group_I(F, Fext, USE_AH)
Rv_all = R.to_numpy(float)
PSEUDO_G = {}
for gname in MODELS["E-X2"].group_factor_names():
    ep_ = l3.residualize(GI[[gname]], X1p, MASKS["ptr"])[0][gname]
    mem = [u for u in MODELS["E-X2"].members(gname) if u in set(EVAL_E)]
    DM, Dj = rg.lag_stack(X1p.to_numpy(float)), rg.lag_stack(ep_.to_numpy(float).reshape(-1, 1))
    dl = np.array([l1eo._pseudo_delta(R[u].to_numpy(float), DM, Dj, MASKS["ptr"], MASKS["pte"]) for u in mem])
    PSEUDO_G[gname] = dict(pseudo_d_r2_med=med(dl), pseudo_n=int(np.isfinite(dl).sum()))

# ───────────── 8) set-level เทียบ ①a: canonical · spanning ─────────────
cs_rows = []
for nm in COMMON:
    if nm == "①a":
        continue
    f = MODELS[nm].base
    a_, b_ = (f, B1A) if f.shape[1] <= B1A.shape[1] else (B1A, f)
    cc = l2.canon_oos(a_, b_, mtr, mte)
    for _, r in cc.iterrows():
        cs_rows.append(dict(row=nm, kind="canonical", c=int(r["c"]), rho_train=r["rho_train"], rho_oos=r["rho_oos"]))
    s1 = ts.spanning(f, B1A, mte)
    s2 = ts.spanning(B1A, f, mte)
    cs_rows.append(dict(row=nm, kind="spanning แถว~①a (ช่วง test)", wald=s1["wald"], p=s1["p"], df=s1["df"], n=s1["n"], min_r2=float(np.min(s1["r2"])), median_r2=float(np.median(s1["r2"]))))
    cs_rows.append(dict(row=nm, kind="spanning ①a~แถว (ช่วง test)", wald=s2["wald"], p=s2["p"], df=s2["df"], n=s2["n"], min_r2=float(np.min(s2["r2"])), median_r2=float(np.median(s2["r2"]))))
    cs_rows.append(dict(row=nm, kind="median ΔBIC เทียบ ①a (EVAL)", value=dbic(nm, "①a", EVAL_E)))
CANON = pd.DataFrame(cs_rows)

# ───────────── 9) lead diagnostic · รายเดือน · A4 ─────────────
LEAD_COLS_E = [c for c in X1.columns if c in l1eo.LONG_SHORT_DAILY]
LEAD_E = l1eo.lead_diag(R, X1, LEAD_COLS_E, EVAL_E, mtr)
midx = Rm.index
MM_TR = np.asarray(midx <= pd.Timestamp("2023-12-31"))
MM_TE = np.asarray(midx >= pd.Timestamp("2024-01-31"))
ntr_m, nte_m = Rm.loc[MM_TR].notna().sum(), Rm.loc[MM_TE].notna().sum()
EVAL_M = [u for u in EVAL_E if ntr_m[u] >= 24 and nte_m[u] >= 12]
CORE_M, POOL_M, _ = l1eo.pool_E(Fm, Fextm, Feom, MM_TR, kf_prefix="KFM_DEV_")
MONTHLY_FAC = {}
sd_m = Rm.loc[MM_TR, BAL_E].std(ddof=0).to_numpy()
MONTHLY_FAC["E-PCA-a1"] = pd.DataFrame(pc.factor_returns(Rm[BAL_E].to_numpy(float), EP["Lam_a"], sd_m), index=midx, columns=EP["a1"].columns)
sd_mc = Rm.loc[MM_TR, UNB_E].std(ddof=0).to_numpy()
MONTHLY_FAC["E-PCA-a2"] = pd.DataFrame(pc.factor_returns(Rm[UNB_E].to_numpy(float), EP["Lam_c"], sd_mc), index=midx, columns=EP["a2"].columns)
MONTHLY_FAC["E-X0"] = CORE_M
MONTHLY_FAC["E-X1"] = pd.concat([CORE_M, POOL_M[SELECTED]], axis=1) if SELECTED else CORE_M.copy()
MONTHLY_FAC["③a"] = ex.line3(Fm, "3a")
mrows = []
for nm in ["E-PCA-a1", "E-PCA-a2", "E-X0", "E-X1", "E-X2", "E-H", "①a", "①c", "③a"]:
    if nm not in MONTHLY_FAC:
        why = "N/A (Λ ของ ①a/①c ไม่อยู่ใน factors_S003_weekly · ไม่สร้างซ้ำ · S013 m3)" if nm in ("①a", "①c") else ("N/A (ไม่อยู่ในรายการแถวที่ p ≤ 13 ตามข้อ 6.12)")
        mrows.append(dict(row=nm, note=why))
        continue
    df = MONTHLY_FAC[nm]
    p_ = 2 * df.shape[1] + 1
    if p_ > 13:
        mrows.append(dict(row=nm, K=df.shape[1], p=p_, note="N/A (p > 13)"))
        continue
    prov = rg.CommonFactors(df)
    ft = rg.fit_funds(Rm, prov, MM_TR, 24, L=3, funds=EVAL_M)
    o = rg.oos_r2_funds(Rm, prov, ft, MM_TE)
    wk_ = FIT[nm] if nm in FIT else None
    mrows.append(dict(row=nm, n=int(ft.ok.sum()), K=df.shape[1], p=p_, train_rows_median=med(ft.n, ft.ok), adjr2_med_monthly=med(ft.adj_r2, ft.ok), r2oos_med_monthly=med(o, ft.ok),
                      r2oos_med_weekly_same_funds=med(FIT[nm][1][[IDX_E[u] for u in EVAL_M]]) if nm in FIT else np.nan,
                      note="รายเดือน Dimson lag 1 เดือน · HAC L=3 · KF = KFM_DEV_* (ทางการ) · ไม่มี null รองรับ — ดูความสอดคล้องเท่านั้น · ป้าย (ช)"))
MONTHLY = pd.DataFrame(mrows)

# A4: ชื่อกลุ่มเทียบ primary ของ L2 (form none · บรรยายแบบ Sensoy)
PRIMN = pd.read_csv(TEAM / "runs" / "S005" / "primary_index.csv")
PRIMN = PRIMN[PRIMN["form"] == "none"].set_index("FundCode")["index"]
ACC = {"CHINA": {"MSCI_CHINA_ALL_SHARES", "MSCI_CHINA_A_SHARES", "MSCI_CHINA_H_SHARES"}, "ASIA": {"MSCI_ASIA_EX_JAPAN"}, "USA": {"MSCI_USA"},
       "EUROPE": {"MSCI_EUROPE"}, "JAPAN": {"MSCI_JAPAN"}, "INDIA": {"MSCI_INDIA"}, "VIETNAM": {"MSCI_VIETNAM"}, "HEALTH": {"MSCI_ACWI_HC"},
       "TECH": {"MSCI_ACWI_IT"}}
a4 = []
for gname in sorted(set(GRP[EVAL_E])):
    mem = [u for u in EVAL_E if GRP[u] == gname and u in PRIMN.index]
    if gname in ACC:
        mt = [u for u in mem if PRIMN[u] in ACC[gname]]
        a4.append(dict(group=gname, n_with_primary=len(mem), n_primary_equals_Ig=len(mt), rate=(len(mt) / len(mem)) if mem else np.nan,
                       acceptable=";".join(sorted(ACC[gname])), top_primary=pd.Series([PRIMN[u] for u in mem]).value_counts().head(3).to_dict() if mem else {}))
    else:
        a4.append(dict(group=gname, n_with_primary=len(mem), n_primary_equals_Ig=np.nan, rate=np.nan, acceptable="(ไม่มีดัชนี MSCI ตรงกับ I_g)",
                       top_primary=pd.Series([PRIMN[u] for u in mem]).value_counts().head(3).to_dict() if mem else {}))
A4 = pd.DataFrame(a4)
A4["note"] = "บรรยายแบบ Sensoy (2009): สัดส่วนกองที่ดัชนีหลัก L2 (form none) ตรงกับ I_g ของกลุ่มชื่อ · ไม่ใช้ตัดสิน · หน่วยต่อรหัสไม่มี primary"
log("canonical/spanning · lead · รายเดือน · A4 เสร็จ")

# ───────────── 10) เกณฑ์ 8.1 · คำตอบ 8.2 · คำตัดสินราย factor 8.3 (ค่าที่ล็อกตาม BRIEF 115(4)) ─────────────
def sget(row, col, setname="EVAL"):
    return float(SCORE_E[(SCORE_E["row"] == row) & (SCORE_E["set"] == setname)][col].iloc[0])


MAXOOS = max(sget(n, "r2oos_med") for n in ROWS_E)
GRPFAC_EVAL = [u for u in EVAL_E if u in PF]
SMALLER = {"E-X1": ("E-X0", EVAL_E), "E-H": ("E-X1", EVAL_E), "E-X2": ("E-X1", GRPFAC_EVAL)}
crit = []
for nm in ROWS_E:
    r2o, gap = sget(nm, "r2oos_med"), sget(nm, "r2gap_med")
    rr = float(STAB_MEAN.get(nm, np.nan))
    c1 = bool(r2o >= 0.9 * MAXOOS)
    c2 = bool(gap <= 0.15)
    c3 = bool(rr >= 0.6)
    if nm in SMALLER:
        ref_, lst_ = SMALLER[nm]
        c4v = dbic(nm, ref_, lst_)
        c4 = bool(c4v <= 0)
    else:
        ref_, c4v, c4 = "", np.nan, None
    sub = FR_E[FR_E["row"] == nm]
    c5 = bool((sub["name_label"] != "ไม่มีชื่อ").all()) if len(sub) else (True if nm == "E-X0" else None)   # E-X0 = MKT (นิยามตรง) · M1 ไม่มี factor report
    allp = c1 and c2 and c3 and (c4 is None or c4) and bool(c5)
    crit.append(dict(row=nm, role="แข่ง" if nm in COMPETE else "ตัวเทียบ (บรรยาย)", C1_r2oos_ge_0p9max=c1, r2oos_med=r2o, max_all_rows=MAXOOS,
                     C2_gap_le_0p15=c2, gap_med=gap, C3_mean_r_ge_0p6=c3, mean_r_h1h2=rr, C4_dBIC_le_0=c4, C4_vs=ref_, C4_dBIC_med=c4v,
                     C5_named=c5, passed_8_1=allp))
CRIT = pd.DataFrame(crit)
PASS81 = dict(zip(CRIT["row"], CRIT["passed_8_1"]))

# Q-E1..Q-E4 (ล็อก S012 ข้อ 8.2) + m6 (ในชุด / นอกชุด PCA)
qe = []
v1, lo1, hi1 = BS_get("d_r2oos_med_vs_E-PCA-a1 (จับคู่)", "E-X2")
q1 = "แทนได้" if (v1 >= -0.03 and PASS81["E-X2"]) else ("ใกล้" if v1 >= -0.06 else "แทนไม่ได้")
if v1 >= -0.03 and not PASS81["E-X2"]:
    q1 = "ใกล้ (ผลต่าง ≥ −0.03 แต่ E-X2 ไม่เข้ารอบ 8.1)"
qe.append(dict(question="Q-E1 ภายนอก (E-X2) แทน E-PCA-a1 ได้ไหม", diff=v1, ci_lo=lo1, ci_hi=hi1, verdict=q1, extra=f"E-X2 เข้ารอบ 8.1 = {PASS81['E-X2']} · ผลต่างจับคู่ในชุด PCA(97) {dmed('E-X2', 'E-PCA-a1', SUBS['EVAL∩ใน PCA(97)']):.3f} · นอกชุด {dmed('E-X2', 'E-PCA-a1', SUBS['EVAL−นอก PCA(97)']):.3f} (ป้าย self-inclusion · ไม่เปลี่ยนคำตัดสิน)"))
v2, lo2, hi2 = BS_get("d_r2oos_med_vs_③a (จับคู่)", "E-X1")
qe.append(dict(question="Q-E2 ภายนอกชุดใหม่ (E-X1) ดีกว่า ③a", diff=v2, ci_lo=lo2, ci_hi=hi2, verdict="ดีกว่า" if (v2 >= 0.05 and lo2 > 0) else "ไม่ดีกว่า (ตามเกณฑ์)", extra=""))
v3, lo3, hi3 = BS_get("d_r2oos_med_vs_①a (จับคู่)", "E-PCA-a1")
qe.append(dict(question="Q-E3 E-PCA-a1 ดีกว่า ①a", diff=v3, ci_lo=lo3, ci_hi=hi3, verdict="ดีขึ้น" if lo3 > 0 else "ไม่ต่าง (บรรยาย)", extra=""))
v4 = dmed("E-H", "E-X1", EVAL_E)
dB4 = dbic("E-H", "E-X1", EVAL_E)
vh, loh, hih = BS_get("d_r2oos_med_vs_E-X1 (จับคู่)", "E-H")
qe.append(dict(question="Q-E4 hybrid มีส่วนที่ภายนอกขาด", diff=vh, ci_lo=loh, ci_hi=hih,
               verdict="มี" if (HY["k_res"] >= 1 and vh >= 0.02 and dB4 <= 0) else "ไม่มี",
               extra=f"k_res = {HY['k_res']} · ΔBIC median (E-H − E-X1) = {dB4:.2f} · จำนวน factor ใน E-H = {HY['EH'].shape[1]} (19 พารามิเตอร์ใน 155 แถวเมื่อ K = 9 · m14(ง))"))
QE = pd.DataFrame(qe)

# 8.3 คำตัดสินราย factor
vrows = []
for _, r in FR_E[FR_E["row"] == "E-X1"].iterrows():
    out = r["drop_d_r2oos_med"] > 0 and r["vif_dimson"] < 5
    pl_ok = max(r["placebo26"], r["placebo52"]) <= 0.08
    imp = bool(out and r["drop_d_r2oos_med"] >= 0.005 and r["n_beta_sig_groups"] >= 7 and r["n_beta_sig_bh"] >= 7 and pl_ok)
    vrows.append(dict(row="E-X1", factor=r["factor"], kind="factor ร่วม", n_ref=int(r["n_ref"]), drop_d_r2oos_med=r["drop_d_r2oos_med"], vif_dimson=r["vif_dimson"],
                      n_beta_sig=r["n_beta_sig_bh"], n_beta_sig_groups=r["n_beta_sig_groups"], placebo_max=max(r["placebo26"], r["placebo52"]),
                      verdict="สำคัญ" if imp else ("ยืนยันนอกช่วง" if out else "ไม่ยืนยันนอกช่วง"), flag="", pseudo_oos_lens=np.nan))
for _, r in FR_E[(FR_E["row"] == "E-X2") & (FR_E["kind"] == "group")].iterrows():
    a = bool(r["drop_d_r2oos_med"] >= 0.02)
    b = bool(r["drop_d_bic_med"] <= 0)
    vif_ok = bool(r["vif_fund_max"] < 5)
    v = "มี" if (a and b and vif_ok) else ("บางส่วน" if (a or b) else "ไม่มี")
    ps = PSEUDO_G.get(r["factor"], {})
    vrows.append(dict(row="E-X2", factor=r["factor"], kind="factor กลุ่ม", n_ref=int(r["n_ref"]), drop_d_r2oos_med=r["drop_d_r2oos_med"], drop_d_bic_med=r["drop_d_bic_med"],
                      vif_dimson=r["vif_fund_max"], n_beta_sig=r["n_beta_sig_bh"], n_beta_sig_groups=r["n_beta_sig_groups"], placebo_max=max(r["placebo26"], r["placebo52"]),
                      verdict=v, flag=small_flag(int(r["n_ref"])), pseudo_oos_lens=ps.get("pseudo_d_r2_med", np.nan), pseudo_n=ps.get("pseudo_n", np.nan),
                      cond_a_dR2oos_ge_0p02=a, cond_b_dBIC_le_0=b, cond_vif_lt_5=vif_ok))
VERDICT_F = pd.DataFrame(vrows)
log("เกณฑ์ 8.1 · คำตอบ 8.2 · คำตัดสิน 8.3 (E) เสร็จ")

# ═════════════════════════ กอง O ═════════════════════════
FUNDS_O = EVAL52_O                         # 13 หน่วย (ตารางรายกอง) · คะแนนหลักใช้ EVAL_O (12)
FG, FR_ = OF["gold"], OF["reit"]
OROWS = ["O-X", "O-X′", "①a", "①c", "③a"]
O_FIT = {}                                 # (row, หน่วย) → dict(fit index) · เก็บรายกอง
O_FITS = {}


def o_fit(df, units):
    return l1eo.fit_df(R, df, mtr, units, mte, 52)


gold13 = [u for u in FUNDS_O if u in GOLD_U]
reit13 = [u for u in FUNDS_O if u in REIT_U]
O_FITS["O-X"] = {"ทอง": o_fit(FG, gold13), "REIT": o_fit(FR_, reit13)}
O_FITS["O-X′"] = {"ทอง": o_fit(OF["gold_simple"], gold13), "REIT": o_fit(OF["reit_simple"], reit13)}
for nm, df in (("①a", B1A), ("①c", B1C), ("③a", F3A)):
    O_FITS[nm] = {"ทอง": o_fit(df, gold13), "REIT": o_fit(df, reit13)}
# ภาคผนวก: O-PCA (em_pca k = 2 บน 13 หน่วย) · O-tilt รายกอง
_Xo = R.loc[mtr, O_UNITS].to_numpy(float)
_Lo, _mo, _so, _it, _cv = pc.em_pca(_Xo, 2)
OPCA = pd.DataFrame(pc.factor_returns(R[O_UNITS].to_numpy(float), _Lo, _so), index=idx, columns=["OPC1", "OPC2"])
O_FITS["O-PCA (ภาคผนวก)"] = {"ทอง": o_fit(OPCA, gold13), "REIT": o_fit(OPCA, reit13)}
tilt_rows = []
for u in reit13:
    if OSUB[u] == "REIT-US":
        df = pd.concat([FR_, OF["tilt_us"].rename("tilt_VNQ_m_REET")], axis=1)
    elif OSUB[u] == "REIT-Singapore":
        df = pd.concat([FR_, OF["tilt_sg"].rename("tilt_CLRSI_m_REET")], axis=1)
    else:
        continue
    f_, r_ = o_fit(df, [u])
    f0, r0 = O_FITS["O-X"]["REIT"]
    j0 = f0.codes.index(u)
    tilt_rows.append(dict(unit=u, subgroup=OSUB[u], K=f_.K, adj_r2_tilt=f_.adj_r2[0], adj_r2_OX=f0.adj_r2[j0], r2oos_tilt=r_[0], r2oos_OX=r0[j0],
                          d_r2oos=r_[0] - r0[j0], beta_tilt=f_.beta[0, -1], t_tilt_approx=f_.beta[0, -1] / f_.se_beta[0, -1] if f_.se_beta[0, -1] > 0 else np.nan,
                          label="O-tilt (ภาคผนวก · รายกอง · N = 1 ต่อกลุ่ม ไม่ใช้ตัดสิน)"))
O_TILT = pd.DataFrame(tilt_rows)

fl_rows = []
for nm, d in O_FITS.items():
    for gname, (fit, ro) in d.items():
        for i, u in enumerate(fit.codes):
            row = dict(row=nm, unit=u, group=gname, subgroup=OSUB[u], fx_risk_flag=gu.loc[u, "fx_risk_flag"], in_EVAL_O=u in set(EVAL_O), n_train_rows=int(fit.n[i]),
                       K=fit.K, alpha_pct_yr=fit.alpha[i] * 5200, t_alpha_hac=fit.t_alpha_hac[i], adj_r2=fit.adj_r2[i], r2=fit.r2[i], bic=fit.bic[i], r2_oos=ro[i],
                       label=("ต่อรหัส (ญ)" if u in l1eo.SPLICE_TABLE else "") + (" · DAOL-USREIT train 67 แถว (ธง)" if u == "DAOL-USREIT" else ""))
            names = list(fit.names)
            for k_, c_ in enumerate(names):
                row["beta_" + c_] = fit.beta[i, k_]
            fl_rows.append(row)
FLO = pd.DataFrame(fl_rows)
FLO["alpha_note"] = "α เทียบ factor ภายนอก (บางตัวลงทุนไม่ได้) · แถว PCA เทียบพอร์ตกองเพื่อน (ฌ)"


def o_get(row, unit, col):
    d = FLO[(FLO["row"] == row) & (FLO["unit"] == unit)]
    return float(d[col].iloc[0]) if len(d) else np.nan


def o_med(row, units, col, only_eval=True):
    us = [u for u in units if (u in set(EVAL_O) or not only_eval)]
    return med([o_get(row, u, col) for u in us])


O_GROUPS = {"ทอง (ทั้งหมด)": GOLD_U, "ทอง-Flag N": [u for u in GOLD_U if OSUB[u] == "ทอง-Flag N"], "ทอง-Flag Y": [u for u in GOLD_U if OSUB[u] == "ทอง-Flag Y"],
            "REIT (ทั้งหมด)": REIT_U, "REIT-US": [u for u in REIT_U if OSUB[u] == "REIT-US"], "REIT-Global": [u for u in REIT_U if OSUB[u] == "REIT-Global"],
            "REIT-Singapore": [u for u in REIT_U if OSUB[u] == "REIT-Singapore"]}
srows = []
for nm in list(O_FITS):
    for gname, units in O_GROUPS.items():
        for sname, only in (("EVAL_O (12)", True), ("EVAL52_O (13)", False)):
            us = [u for u in units if (u in set(EVAL_O) or not only)]
            if not us:
                continue
            ar = [o_get(nm, u, "alpha_pct_yr") for u in us]
            srows.append(dict(row=nm, group=gname, set=sname, n=len(us), K=O_FITS[nm]["ทอง" if gname.startswith("ทอง") else "REIT"][0].K,
                              adjr2_med=med([o_get(nm, u, "adj_r2") for u in us]), r2oos_med=med([o_get(nm, u, "r2_oos") for u in us]),
                              r2gap_med=med([o_get(nm, u, "r2") - o_get(nm, u, "r2_oos") for u in us]), mean_abs_alpha_pct=float(np.nanmean(np.abs(ar))),
                              signed_mean_alpha_pct=float(np.nanmean(ar)), bic_med=med([o_get(nm, u, "bic") for u in us]), note="N น้อย · รายงานรายกอง/กลุ่มย่อยเป็นหลัก (BRIEF 110)"))
SCORE_O = pd.DataFrame(srows)

# α · BH 10% ภายใน O (12 และ 13 การทดสอบ)
bh_o = []
for nm in OROWS:
    for sname, units in (("EVAL_O (12)", EVAL_O), ("EVAL52_O (13)", FUNDS_O)):
        t = np.array([o_get(nm, u, "t_alpha_hac") for u in units])
        ok = np.isfinite(t)
        rej, adj = ts.bh(2 * stats.norm.sf(np.abs(t[ok])), 0.10)
        bh_o.append(dict(row=nm, set=sname, n_tests=int(ok.sum()), n_reject_bh10=int(rej.sum()), units_rejected=";".join(np.array(units)[ok][rej])))
BH_O = pd.DataFrame(bh_o)

# GRS 2 พอร์ต EW (ทอง · REIT) ช่วง test (บรรยาย · N = 1 ต่อพอร์ต · ชุด factor ของแถวนั้น)
go_rows = []
for pname, units in (("ทอง", GOLD_U), ("REIT", REIT_U)):
    V = R[units].to_numpy(float)
    cnt_ = np.isfinite(V).sum(axis=1)
    yv = np.where(cnt_ > 0, np.nansum(V, axis=1) / np.maximum(cnt_, 1), np.nan)
    for nm in OROWS:
        df = {"O-X": FG if pname == "ทอง" else FR_, "O-X′": OF["gold_simple"] if pname == "ทอง" else OF["reit_simple"], "①a": B1A, "①c": B1C, "③a": F3A}[nm]
        d = l1eo.run_grs([pname], yv.reshape(-1, 1), cnt_.reshape(-1, 1), rg.lag_stack(df.to_numpy(float)), mte & MASKS["pos1"])
        rr_ = rg.ols_hac(yv[mte & MASKS["pos1"] & np.isfinite(rg.lag_stack(df.to_numpy(float))).all(1)],
                         np.column_stack([np.ones(int((mte & MASKS["pos1"] & np.isfinite(rg.lag_stack(df.to_numpy(float))).all(1)).sum())),
                                          rg.lag_stack(df.to_numpy(float))[mte & MASKS["pos1"] & np.isfinite(rg.lag_stack(df.to_numpy(float))).all(1)]]), 4)
        d.update(row=nm, portfolio=pname, window="test", alpha_pct_yr=rr_["coef"][0] * 5200, t_alpha_hac=rr_["t"][0],
                 note="GRS N = 1 พอร์ต (F-test ของ α) · บรรยาย · N น้อย · PY = N/A (S012 ข้อ 5)")
        go_rows.append(d)
GRS_O = pd.DataFrame(go_rows)

# ตารางทอง/REIT ลงทะเบียนล่วงหน้า (S013 §3 · BRIEF 116)
def per_fund_delta(a, b, units):
    return pd.DataFrame({"unit": units, "d_r2oos": [o_get(a, u, "r2_oos") - o_get(b, u, "r2_oos") for u in units], "d_bic": [o_get(a, u, "bic") - o_get(b, u, "bic") for u in units],
                         "d_adjr2": [o_get(a, u, "adj_r2") - o_get(b, u, "adj_r2") for u in units]})


def best_cmp(units, cands):
    mm = {c: med([o_get(c, u, "r2_oos") for u in units if u in set(EVAL_O)]) for c in cands}
    return max(mm, key=lambda c: mm[c]), mm


OT = []
VER_O = []
for gname, base_units in (("ทอง", GOLD_U), ("REIT", REIT_U)):
    ev_units = [u for u in base_units if u in set(EVAL_O)]
    best, mm = best_cmp(base_units, ["①a", "①c", "③a"])
    best_eq = best_cmp(base_units, ["①a", "①c"])[0]
    for table, ref in (("T1 O-X vs ③a (คำตัดสิน 'เทียบเท่า ③a' · ทองเท่านั้น)", "③a"), ("T2 O-X vs ตัวที่ดีที่สุดของ (①a,①c) (factor หุ้นพอไหม)", best_eq),
                       ("T3 O-X vs O-X′ (คุณค่าของการแยก FX)", "O-X′"), ("T0 O-X vs ตัวที่ดีที่สุดของ (①a,①c,③a) (เกณฑ์ที่ล็อก 8.3)", best)):
        for sub_name, units in ([(gname + " (ทั้งหมด)", base_units)] + [(k, v) for k, v in O_GROUPS.items() if k.startswith(gname + "-")]):
            dd = per_fund_delta("O-X", ref, units)
            dd_e = dd[dd["unit"].isin(EVAL_O)]
            OT.append(dict(table=table, group=sub_name, vs=ref, n=len(dd_e), n_all=len(dd), med_d_r2oos=float(np.nanmedian(dd_e["d_r2oos"])) if len(dd_e) else np.nan,
                           med_d_bic=float(np.nanmedian(dd_e["d_bic"])) if len(dd_e) else np.nan, frac_pos=float(np.mean(dd_e["d_r2oos"] > 0)) if len(dd_e) else np.nan,
                           per_fund=";".join(f"{u}:{v:+.3f}" for u, v in zip(dd["unit"], dd["d_r2oos"]))))
    dd0 = per_fund_delta("O-X", best, ev_units)
    md0, fp0 = float(np.nanmedian(dd0["d_r2oos"])), float(np.mean(dd0["d_r2oos"] > 0))
    better = bool(md0 >= 0.05 and fp0 >= 2 / 3)
    v = dict(group=gname, n_EVAL_O=len(ev_units), best_comparator=best, comparator_median_r2oos=mm[best], OX_median_r2oos=med([o_get("O-X", u, "r2_oos") for u in ev_units]),
             med_d_r2oos=md0, frac_pos=fp0, rule_8_3="ดีกว่าตัวเทียบ" if better else "ไม่ดีกว่าตัวเทียบ (ตามเกณฑ์ที่ล็อก)")
    if gname == "ทอง":
        d3 = per_fund_delta("O-X", "③a", ev_units)
        m3r, m3b = float(np.nanmedian(d3["d_r2oos"])), float(np.nanmedian(d3["d_bic"]))
        v.update(desc_med_d_r2oos_vs_3a=m3r, desc_med_d_bic_vs_3a=m3b, descriptive="เทียบเท่า ③a" if (abs(m3r) < 0.02 and m3b <= 0) else "ไม่เข้าเกณฑ์ 'เทียบเท่า ③a'",
                 note_ban="ห้ามสรุปว่า 'ชุดกลไกใช้ไม่ได้กับทอง' จากผล 'ไม่ดีกว่า ③a' (BRIEF 116) · ③a มี Gold_THB − RF + FX อยู่แล้ว")
        d2 = per_fund_delta("O-X", best_eq, ev_units)
        v.update(vs_stock_factors_best=best_eq, med_d_r2oos_vs_stock=float(np.nanmedian(d2["d_r2oos"])), frac_pos_vs_stock=float(np.mean(d2["d_r2oos"] > 0)),
                 beats_stock_factors=bool(np.nanmedian(d2["d_r2oos"]) >= 0.05 and np.mean(d2["d_r2oos"] > 0) >= 2 / 3))
    VER_O.append(v)
O_TABLES = pd.DataFrame(OT)
VERDICT_O = pd.DataFrame(VER_O)

# factor report O-X (ทอง · REIT)
ORP = []
MOD_OG = l1eo.Model("O-X(ทอง)", FG)
MOD_OR = l1eo.Model("O-X(REIT)", FR_)
CLU_O = l2.fund_clusters(R, mtr, EVAL_O).set_index("FundCode")["group_id"].to_dict()
SHAP_O = []
for mdl, units, axis, axser in ((MOD_OG, GOLD_U, "GOLD_XS", FG["GOLD_XS"]), (MOD_OR, REIT_U, "MKT", FR_["MKT"])):
    key = "ทอง" if mdl is MOD_OG else "REIT"
    fit, ro = O_FITS["O-X"][key]
    evu = [u for u in units if u in set(EVAL_O)]
    stab_u = [u for u in units if u in set(STAB_O)]
    sh = l1eo.shapley_table(R, mdl, [u for u in evu if fit.ok[fit.codes.index(u)]], MASKS, with_oos=True)
    ctx = dict(masks=MASKS, stab=stab_u, clusters=CLU_O, group=pd.Series(OSUB), ref=REF_BASE, a1=B1A, axis=axis, axis_series=axser, min_n_group=2)
    fr = l1eo.factor_report(R, mdl, fit, ro, evu, ctx, interpret_names=(), shap=sh, detail_common=True)
    fr["role"] = "O-X"
    ORP.append(fr)
    SHAP_O.append(sh.assign(row=mdl.name))
FR_O = pd.concat(ORP, ignore_index=True)
SHAP_OD = pd.concat(SHAP_O, ignore_index=True)
LEAD_O = {**l1eo.lead_diag(R, FG, ["GOLD_XS"], [u for u in GOLD_U if u in set(EVAL_O)], mtr), **l1eo.lead_diag(R, FR_, ["REIT_e"], [u for u in REIT_U if u in set(EVAL_O)], mtr)}

# O รายเดือน (O-X เท่านั้น · ①a/①c N/A)
OFM = l1eo.o_factors(Fm, Fextm, Feom, MM_TR)
mo_rows = []
for key, df, units in (("ทอง", OFM["gold"], GOLD_U), ("REIT", OFM["reit"], REIT_U)):
    us = [u for u in units if u in set(EVAL_O) and ntr_m[u] >= 24 and nte_m[u] >= 12]
    prov = rg.CommonFactors(df)
    ft = rg.fit_funds(Rm, prov, MM_TR, 24, L=3, funds=us)
    o = rg.oos_r2_funds(Rm, prov, ft, MM_TE)
    mo_rows.append(dict(row=f"O-X({key})", n=int(ft.ok.sum()), K=df.shape[1], p=2 * df.shape[1] + 1, adjr2_med_monthly=med(ft.adj_r2, ft.ok), r2oos_med_monthly=med(o, ft.ok),
                        r2oos_med_weekly_same_funds=med([o_get("O-X", u, "r2_oos") for u in us]),
                        note="รายเดือน · ไม่มี null รองรับ — ดูความสอดคล้องเท่านั้น"))
MONTHLY = pd.concat([MONTHLY, pd.DataFrame(mo_rows)], ignore_index=True)

# ความเสถียรของ O-X (บรรยาย · N น้อย)
STAB_O_ROWS = []
for mdl, units in ((MOD_OG, GOLD_U), (MOD_OR, REIT_U)):
    st = l1eo.model_stability(R, mdl, [u for u in units if u in set(STAB_O)], MASKS)
    st.insert(0, "row", mdl.name)
    STAB_O_ROWS.append(st)
STAB_OX = pd.concat(STAB_O_ROWS, ignore_index=True)
STAB_OX["note"] = STAB_OX["note"].astype(str) + " · N น้อย (บรรยาย)"
log("กอง O เสร็จ")

# ═════════════════════════ ภาคผนวก A1 · A2 · n_tried · ผลลัพธ์ ═════════════════════════
MOD_A1 = l1eo.Model("E-X1(A1: style ETF)", X1_A1)
FIT["E-X1(A1)"] = l1eo.fit_model(R, MOD_A1, mtr, mte, FUNDS_E, 52)
d_ = sc.score_model(FIT["E-X1(A1)"][0], FIT["E-X1(A1)"][1], POL_E, subset=smask(EVAL_E), div_flag=DIV_E)
d_ = d_[d_["policy"] == "E"].iloc[0].to_dict()
A1 = pd.DataFrame([dict(row="E-X1(A1)", selected=";".join(SEL_A1), K=X1_A1.shape[1], tau=PL_A1["tau"], n=d_["n"], adjr2_med=d_["adjr2_med"], r2oos_med=d_["r2oos_med"],
                        r2gap_med=d_["r2gap_med"], bic_med=d_["bic_med"], d_r2oos_vs_EX1_main=d_["r2oos_med"] - sget("E-X1", "r2oos_med"),
                        label="ภาคผนวก A1 · pool style ETF 4 ตัวแทน KF 5 ตัว (pool 10 · ไม่มี factor กลุ่ม) · ไม่ใช้ตัดสิน · 'ข้อมูลชุดเดียวกัน ไม่ใช่หลักฐานอิสระ' (ข้อ 103 n1)")])
A2 = pd.DataFrame([dict(appendix="A2", status="N/A", reason="AQR Terms of Use (BRIEF 117 · n2): ห้าม reproduce/copy/distribute โดยไม่ได้รับอนุญาตเป็นลายลักษณ์อักษร → เงื่อนไข BRIEF 113 ไม่ครบ · "
                                "คอลัมน์ AQR ใน factors_eo_*.parquet ไม่ถูกใช้ในการรัน (ไม่อยู่ใน pool · ไม่อยู่ในชุดอ้างอิงชื่อ) · ไม่กระทบแถวหลัก")])

n_tried = []


def nt(side, kind, item, n):
    n_tried.append(dict(side=side, kind=kind, item=item, n=int(n)))


nt("E", "factor ร่วม (pool)", "stepwise จริง: Σ candidate ที่ประเมินทุกรอบ", len(STEP_ALL))
nt("E", "factor ร่วม (pool)", "placebo 26/52: Σ candidate ที่ประเมินทุกรอบ", PL["n_candidates_evaluated"])
nt("E", "ภาคผนวก A1", "stepwise pool style ETF (จริง)", len(ALL_A1))
nt("E", "ภาคผนวก A1", "placebo A1 26/52", PL_A1["n_candidates_evaluated"])
nt("E", "ภาคผนวก A2", "AQR 2 factor (N/A ไม่ได้รัน)", 0)
nt("E", "factor กลุ่ม", "factor กลุ่มที่ fit (11 + e_AH ถ้าใช้ · นับ e_CHINAg/e_AH ที่ระบบสร้าง)", len(MODELS["E-X2"].group_factor_names()) + int(USE_AH))
nt("E", "residual PC", "k_res ที่เลือก (kmax 3)", HY["k_res"])
nt("E", "PC ของ E-PCA", "k* × 2 (a1 · a2)", 2 * EP["k"])
nt("E", "ตัวเทียบ M1", "ดัชนี P4 ของ M1", 6)
nt("E", "แถวแข่ง", "E-PCA-a1 · E-PCA-a2 · E-X0 · E-X1 · E-X2 · E-H", 6)
nt("E", "ตัวเทียบ", "①a · ①c · ③a · M1", 4)
nt("O", "factor ชุด O", "MKT · GOLD_XS · REIT_e · FX · TERM", 5)
nt("O", "O-X′", "GLD_THB · REET_THB", 2)
nt("O", "O-tilt", "VNQ−REET · CLRSI−REET", 2)
nt("O", "O-PCA", "OPC1 · OPC2", 2)
NTRIED = pd.DataFrame(n_tried)
NTRIED_TOTAL = int(NTRIED["n"].sum())

# fund_level E
fle = []
for nm in ROWS_E + ["E-X1(A1)"]:
    fit, ro = FIT[nm]
    fle.append(pd.DataFrame(dict(row=nm, unit=FUNDS_E, group=[GRP[u] for u in FUNDS_E], in_EVAL=[u in set(EVAL_E) for u in FUNDS_E], in_STAB=[u in set(STAB_E) for u in FUNDS_E],
                                 in_PCA97=[u in set(BAL_E) for u in FUNDS_E], has_group_factor=[u in PF for u in FUNDS_E], n_train_rows=fit.n, K=fit.K,
                                 alpha_pct_yr=fit.alpha * 5200, t_alpha_hac=fit.t_alpha_hac, adj_r2=fit.adj_r2, r2=fit.r2, bic=fit.bic, r2_oos=ro,
                                 splice_flag=["ต่อรหัส (ญ)" if u in l1eo.SPLICE_TABLE else "" for u in FUNDS_E],
                                 flag_struct=["ค่าผิดปกติเชิงโครงสร้าง (SCB SET Index · FIF=Y · ไม่มี TDEX)" if u == "FCSCBSETE" else "" for u in FUNDS_E],
                                 div_class=DIV[FUNDS_E].to_numpy())))
FLE = pd.concat(fle, ignore_index=True)

# ไฟล์ผล
save(SCORE_E, "scorecard_E.csv")
save(SCORE_O, "scorecard_O.csv")
save(FLE, "fund_level_E.csv")
save(FLO, "fund_level_O.csv")
save(FR_E, "factor_report_E.csv")
save(FR_O, "factor_report_O.csv")
save(SHAP_E, "shapley_E.csv")
save(SHAP_OD, "shapley_O.csv")
_sig_cols = ["row", "factor", "kind", "n_ref", "n_beta_tested", "n_beta_sig_bh", "n_beta_sig_groups", "n_beta_pos", "n_beta_neg", "frac_p05", "frac_abs_t_b1_gt2", "placebo26", "placebo52", "placebo_flag", "beta_med"]
save(pd.concat([FR_E.reindex(columns=_sig_cols), FR_O.reindex(columns=_sig_cols)], ignore_index=True), "sig_counts.csv")
_vif_cols = ["row", "factor", "kind", "vif_lag0", "vif_dimson", "vif_fund_max", "vif_fund_med", "maxcorr_other_train", "maxcorr_other_test"]
save(pd.concat([FR_E.reindex(columns=_vif_cols), FR_O.reindex(columns=_vif_cols)], ignore_index=True), "vif.csv")
save(pd.concat([STAB_ALL, STAB_OX], ignore_index=True), "stability.csv")
save(pd.concat([STAB_ALL, STAB_OX], ignore_index=True)[["row", "factor", "n", "roll_first_last", "roll_median_vs_full"]], "rolling_104.csv")
_int_cols = ["row", "factor", "name_label", "name_ref1", "name_corr1", "name_ref2", "name_corr2", "name_ref3", "name_corr3", "name_test_corr1", "max_corr_1a_pc", "max_corr_1a_which"]
save(FR_E.reindex(columns=_int_cols), "interpret.csv")
save(CANON, "canon_spanning.csv")
save(pd.concat([GRS_E.assign(group="E"), GRS_O.assign(group="O")], ignore_index=True), "grs.csv")
save(PY_E, "py.csv")
save(BOOT, "bootstrap.csv")
save(MONTHLY, "monthly.csv")
save(A1, "appendix_A1.csv")
save(A2, "appendix_A2.csv")
save(A4, "appendix_A4.csv")
save(CRIT, "criteria_8_1.csv")
save(QE, "qe_verdicts.csv")
save(VERDICT_F, "factor_verdicts.csv")
save(VERDICT_O, "o_verdicts.csv")
save(O_TABLES, "o_gold_tables.csv")
save(O_TILT, "o_tilt.csv")
save(BH_E, "bh_alpha_E.csv")
save(BH_O, "bh_alpha_O.csv")
save(NTRIED, "n_tried.csv")
save(pd.DataFrame([dict(factor=k, **{"frac_|t_lead|>2": v}) for k, v in {**LEAD_E, **LEAD_O}.items()]) if (LEAD_E or LEAD_O) else
     pd.DataFrame([dict(note="N/A")]), "lead_diag.csv")
FAC = {}
for nm in ("E-PCA-a1", "E-PCA-a2"):
    for c in MODELS[nm].base.columns:
        FAC[f"{nm}__{c}"] = MODELS[nm].base[c]
for c in POOL.columns:
    FAC[f"pool__{c}"] = POOL[c]
FAC["core__MKT"] = CORE["MKT"]
for c in E_G.columns:
    FAC[f"E-X2__{c}"] = E_G[c]
for c in HY["rpc"].columns:
    FAC[f"E-H__{c}"] = HY["rpc"][c]
for c in FG.columns:
    FAC[f"O-gold__{c}"] = FG[c]
for c in FR_.columns:
    FAC[f"O-reit__{c}"] = FR_[c]
FAC["O-PCA__OPC1"], FAC["O-PCA__OPC2"] = OPCA["OPC1"], OPCA["OPC2"]
pd.DataFrame(FAC).to_parquet(OUT / "factors_S012_weekly.parquet")
log("เขียนไฟล์ผล CSV/parquet ครบ")

# ═════════════════════════ ความคาดหมายล่วงหน้า (S012 ข้อ 9 + S013 §3) vs ผล ═════════════════════════
EXP = []


def ex_add(i, expect, result, status):
    EXP.append(dict(id=i, expectation=expect, result=result, status=status))


def st3(flags):
    flags = [bool(f) for f in flags]
    return "ตรง" if all(flags) else ("ไม่ตรง" if not any(flags) else "บางส่วน")


def frv(row, factor, col):
    d = FR_E[(FR_E["row"] == row) & (FR_E["factor"] == factor)]
    return float(d[col].iloc[0]) if len(d) and col in d.columns else np.nan


def corr_tr(a, b):
    ok = mtr & np.isfinite(a.to_numpy(float)) & np.isfinite(b.to_numpy(float))
    return float(np.corrcoef(a.to_numpy(float)[ok], b.to_numpy(float)[ok])[0, 1])


rfx = F["RF_BOT"]
pc1, pc2 = EP["a1"]["PC1"], (EP["a1"]["PC2"] if EP["k"] >= 2 else None)
c_pc1 = max(abs(corr_tr(pc1, F["MSCI_ACWI"] - rfx)), abs(corr_tr(pc1, F["MSCI_WORLD"] - rfx)))
c_pc2 = abs(corr_tr(pc2, F["MSCI_CHINA_ALL_SHARES"] - rfx)) if pc2 is not None else np.nan
ex_add(1, "k* ของ E-PCA = 3–6 · PC1 ≈ ACWI/World (|corr| ≥ 0.8) · PC2 ≈ จีน (≥ 0.7)", f"k* = {EP['k']} (IC_p2 {EP['ks']['IC_p2']} · ER {EP['ks']['ER']} · ED {EP['ks']['ED']} · PA {EP['ks']['PA']}) · |corr| PC1–ACWI/World = {c_pc1:.3f} · PC2–China All = {c_pc2:.3f}",
       st3([3 <= EP["k"] <= 6, c_pc1 >= 0.8, np.isfinite(c_pc2) and c_pc2 >= 0.7]))
ex_add(2, "placebo เลือก 0 ตัวทั้งสอง shift → τ = −2", f"placebo เลือก {[v['n_selected'] for v in PL['shifts'].values()]} · τ = {PL['tau']}", st3([not PL["any_selected"]]))
last_action = STEP_LOG["action"].iloc[-1]
KFsel = [c for c in SELECTED if c in l1eo.KF5]
JKsel = [c for c in SELECTED if c.startswith("JKP")]
ex_add(3, "E-X1 เพิ่ม 2–5 ตัว · หนึ่งในสองตัวแรก = e_CHINA หรือ TERM · KF ผ่าน ≤ 2 · JKP-EM ≤ 1 · FX ไม่ถูกเลือก · ด่าน G3/τ หยุดก่อนเพดาน 6",
       f"เลือก {SELECTED} ({len(SELECTED)} ตัว) · KF {KFsel} · JKP {JKsel} · FX {'ถูกเลือก' if 'FX' in SELECTED else 'ไม่ถูกเลือก'} · เหตุหยุด = {last_action}",
       st3([2 <= len(SELECTED) <= 5, any(c in ("e_CHINA", "TERM") for c in SELECTED[:2]), len(KFsel) <= 2, len(JKsel) <= 1, "FX" not in SELECTED, last_action in ("stop_tau", "stop_g3_pseudo_oos")]))
o_ = {n: sget(n, "r2oos_med") for n in ROWS_E}
ex_add(4, "median R²_oos (EVAL_E): a1 0.58–0.72 · a2 ต่างจาก a1 ≤ ±0.03 · E-X1 0.40–0.58 · E-X2 0.48–0.65 · E-H ≥ a1 − 0.03 · ③a 0.28–0.40 · ①a ใกล้ a1 (±0.03)",
       " · ".join(f"{n} {o_[n]:.3f}" for n in ["E-PCA-a1", "E-PCA-a2", "E-X1", "E-X2", "E-H", "③a", "①a"]),
       st3([0.58 <= o_["E-PCA-a1"] <= 0.72, abs(o_["E-PCA-a2"] - o_["E-PCA-a1"]) <= 0.03, 0.40 <= o_["E-X1"] <= 0.58, 0.48 <= o_["E-X2"] <= 0.65,
            o_["E-H"] >= o_["E-PCA-a1"] - 0.03, 0.28 <= o_["③a"] <= 0.40, abs(o_["①a"] - o_["E-PCA-a1"]) <= 0.03]))
ex_add(5, "Q-E1 = ใกล้/แทนไม่ได้ (E-X2 ต่ำกว่า a1 0.02–0.10) · Q-E2 = ดีกว่า · Q-E3 = ไม่ต่าง · Q-E4 = มี (k_res อาจชนเพดาน 3)",
       " · ".join(f"{r['question'][:4]} {r['verdict']} (Δ {r['diff']:+.3f})" for _, r in QE.iterrows()) + f" · k_res = {HY['k_res']}",
       st3([QE.loc[0, "verdict"].startswith(("ใกล้", "แทนไม่ได้")) and -0.10 <= QE.loc[0, "diff"] <= -0.02, QE.loc[1, "verdict"] == "ดีกว่า", QE.loc[2, "verdict"].startswith("ไม่ต่าง"), QE.loc[3, "verdict"] == "มี"]))
VG = VERDICT_F[VERDICT_F["kind"] == "factor กลุ่ม"].set_index("factor")
n_have = int((VG["verdict"] == "มี").sum())
ex_add(6, "factor กลุ่ม 'มี' ≥ 4 ใน 11 (คาด JAPAN · EUROPE · VIETNAM · HEALTH) · ASIA และ USA 'ไม่มี'/'บางส่วน' · INDIA/INFRA แกว่งมาก · e_AH ใช้เมื่อ e_CHINA ∈ E-X1",
       f"'มี' {n_have} จาก {len(VG)}: " + ", ".join(f"{k} {v}" for k, v in VG["verdict"].items()) + f" · e_AH {'ใช้' if USE_AH else 'ไม่ได้ใช้ (e_CHINA ไม่อยู่ใน E-X1)'}",
       st3([n_have >= 4, all(VG["verdict"].get(k, "ไม่มี") in ("ไม่มี", "บางส่วน") for k in ("e_ASIA", "e_USA")), True]))
mk_share = frv("E-X1", "MKT", "shap_share_med")
grp_sh = {k: frv("E-X2", k, "shap_share_med") for k in VG.index}
kf_sh = {c: frv("E-X1", c, "shap_share_med") for c in KFsel}
ex_add(7, "Shapley: MKT ≥ 40% ของ R² ในกองมัธยฐาน · factor กลุ่ม 5–20% ในกลุ่มตัวเอง · style KF < 5%",
       f"MKT {mk_share:.3f} · factor กลุ่ม " + ", ".join(f"{k} {v:.3f}" for k, v in grp_sh.items()) + (" · KF " + ", ".join(f"{k} {v:.3f}" for k, v in kf_sh.items()) if kf_sh else " · ไม่มี KF ใน E-X1"),
       st3([mk_share >= 0.40, all(0.05 <= v <= 0.20 for v in grp_sh.values() if np.isfinite(v)), all(v < 0.05 for v in kf_sh.values())]))
x1v = FR_E[FR_E["row"] == "E-X1"]
xg = FR_E[(FR_E["row"] == "E-X2") & (FR_E["kind"] == "group")]
ex_add(8, "VIF Dimson ของ E-X1 < 5 ทุกตัว · ต่อกองใน E-X2 < 5 · corr(e_g, factor ร่วม) ช่วง test สูงสุด ≤ 0.55",
       f"VIF Dimson max E-X1 {x1v['vif_dimson'].max():.2f} · E-X2 max {xg['vif_fund_max'].max():.2f} · max corr test (กลุ่ม) {xg['maxcorr_other_test'].max():.3f}",
       st3([x1v["vif_dimson"].max() < 5, xg["vif_fund_max"].max() < 5, xg["maxcorr_other_test"].max() <= 0.55]))
rr = lambda row, f: frv(row, f, "r_h1h2")
grp_r = [v for v in xg["r_h1h2"] if np.isfinite(v)]
ex_add(9, "ความเสถียร r ดิบ: MKT และ e_CHINA > 0.8 · style KF < 0.5 · factor กลุ่มที่คำนวณได้ 0.4–0.8 · E-PCA-a1 เฉลี่ย ≥ 0.75",
       f"MKT {rr('E-X1', 'MKT'):.3f} · e_CHINA {rr('E-X1', 'e_CHINA'):.3f} (ถ้าถูกเลือก) · KF {[round(rr('E-X1', c), 3) for c in KFsel]} · กลุ่ม {[round(v, 3) for v in grp_r]} · E-PCA-a1 mean {STAB_MEAN.get('E-PCA-a1', np.nan):.3f}",
       st3([rr("E-X1", "MKT") > 0.8, (rr("E-X1", "e_CHINA") > 0.8) if "e_CHINA" in SELECTED else False, all(rr("E-X1", c) < 0.5 for c in KFsel), all(0.4 <= v <= 0.8 for v in grp_r) if grp_r else False,
            STAB_MEAN.get("E-PCA-a1", 0) >= 0.75]))
mk_frac = frv("E-X1", "MKT", "n_beta_sig_bh") / max(frv("E-X1", "MKT", "n_beta_tested"), 1)
hml = FR_E[(FR_E["row"] == "E-X1") & (FR_E["factor"] == "HML")]
pl_ext = FR_E[(FR_E["row"] == "E-X1") & (FR_E["kind"] == "common") & (FR_E["factor"] != "MKT")]
ex_add(10, "กองที่ β มีนัย: MKT เกือบทุกกอง · HML ≥ 7 กลุ่มอิสระ (ติดลบในกลุ่ม TECH/INNOV เกินครึ่ง) · placebo ของ factor ภายนอก ≤ 8%",
       f"MKT มีนัย {mk_frac:.2f} ของกอง · HML {'ไม่ได้อยู่ใน E-X1 (ไม่ได้ถูกเลือก) — ไม่ได้ตรวจ' if len(hml) == 0 else str(int(hml['n_beta_sig_groups'].iloc[0])) + ' กลุ่มอิสระ'} · placebo สูงสุด (E-X1) {pl_ext[['placebo26', 'placebo52']].max().max() if len(pl_ext) else float('nan'):.3f}",
       st3([mk_frac >= 0.9, len(hml) > 0 and hml["n_beta_sig_groups"].iloc[0] >= 7, (pl_ext[["placebo26", "placebo52"]].max().max() <= 0.08) if len(pl_ext) else True]))
cc1 = CANON[(CANON["row"] == "E-X1") & (CANON["kind"] == "canonical")].sort_values("c")
ex_add(11, "canonical corr E-X1 กับ ①a: คู่แรก ≥ 0.85 · คู่สุดท้าย < 0.6", f"คู่แรก {cc1['rho_train'].iloc[0]:.3f} · คู่สุดท้าย {cc1['rho_train'].iloc[-1]:.3f} (train · {len(cc1)} คู่)",
       st3([cc1["rho_train"].iloc[0] >= 0.85, cc1["rho_train"].iloc[-1] < 0.6]))
og = lambda row, unit, col: o_get(row, unit, col)
gold_ev = [u for u in GOLD_U if u in set(EVAL_O)]
b_g = [og("O-X", u, "beta_GOLD_XS") for u in GOLD_U]
bfx_N = med([og("O-X", u, "beta_FX") for u in GOLD_U if OSUB[u] == "ทอง-Flag N"])
bfx_Y = med([og("O-X", u, "beta_FX") for u in GOLD_U if OSUB[u] == "ทอง-Flag Y"])
vg = VERDICT_O.set_index("group").loc["ทอง"]
dN = med([og("O-X", u, "r2_oos") - og("O-X′", u, "r2_oos") for u in GOLD_U if OSUB[u] == "ทอง-Flag N" and u in set(EVAL_O)])
dY = med([og("O-X", u, "r2_oos") - og("O-X′", u, "r2_oos") for u in GOLD_U if OSUB[u] == "ทอง-Flag Y" and u in set(EVAL_O)])
ga = [abs(og("O-X", u, "alpha_pct_yr")) for u in GOLD_U]
ex_add(12, "ทอง (แก้โดย S013 §3): ตามเกณฑ์ที่ล็อก O-X 'ไม่ดีกว่าตัวเทียบ' (ตัวเทียบดีสุด ③a) · คำตัดสินบรรยาย = 'เทียบเท่า ③a' · O-X ดีกว่าตัวดีสุดของ (①a,①c) ≥ +0.20 · O-X − O-X′ ≈ 0 (Flag Y) และ > 0 (Flag N) · β(GOLD_XS) 0.85–1.05 ทุกกอง · β(FX) Flag N 0–0.3 / Y 0.6–1.1 · R²_oos ≥ 0.85 · |α| ≤ 3%/ปี",
       f"เกณฑ์ล็อก: {vg['rule_8_3']} (ตัวเทียบดีสุด {vg['best_comparator']}) · บรรยาย: {vg['descriptive']} (ΔR²_oos {vg['desc_med_d_r2oos_vs_3a']:+.3f} · ΔBIC {vg['desc_med_d_bic_vs_3a']:+.2f}) · vs stock {vg['med_d_r2oos_vs_stock']:+.3f} · O-X−O-X′ Flag Y {dY:+.3f} / N {dN:+.3f} · β(GOLD_XS) {min(b_g):.2f}–{max(b_g):.2f} · β(FX) N {bfx_N:.2f} / Y {bfx_Y:.2f} · median R²_oos {vg['OX_median_r2oos']:.3f} · max|α| {max(ga):.2f}%/ปี",
       st3([vg["rule_8_3"].startswith("ไม่ดีกว่า") and vg["best_comparator"] == "③a", vg["descriptive"] == "เทียบเท่า ③a", vg["med_d_r2oos_vs_stock"] >= 0.20, abs(dY) <= 0.02 and dN > 0,
            0.85 <= min(b_g) and max(b_g) <= 1.05, 0 <= bfx_N <= 0.3 and 0.6 <= bfx_Y <= 1.1, vg["OX_median_r2oos"] >= 0.85, max(ga) <= 3]))
vr = VERDICT_O.set_index("group").loc["REIT"]
tb = [og("O-X", u, "beta_TERM") for u in REIT_U]
rb = [og("O-X", u, "beta_REIT_e") for u in REIT_U]
ex_add(13, "REIT: median R²_oos ของ O-X 0.55–0.80 และ ≥ ตัวเทียบดีสุด + 0.05 · TERM β > 0 ≥ 4/6 กอง · REIT_e β > 0 ทุกกอง",
       f"median R²_oos O-X {vr['OX_median_r2oos']:.3f} · ตัวเทียบดีสุด {vr['best_comparator']} {vr['comparator_median_r2oos']:.3f} · Δ {vr['med_d_r2oos']:+.3f} · TERM β>0 {int(np.sum(np.array(tb) > 0))}/6 · REIT_e β>0 {int(np.sum(np.array(rb) > 0))}/6",
       st3([0.55 <= vr["OX_median_r2oos"] <= 0.80 and vr["med_d_r2oos"] >= 0.05, np.sum(np.array(tb) > 0) >= 4, np.sum(np.array(rb) > 0) == 6]))
ex_add(14, "(แก้โดย S013 §3) REIT: O-X 'ดีกว่าตัวเทียบ' (③a ไม่มี REIT · คาดตัวเทียบดีสุดคือ ①c)", f"{vr['rule_8_3']} · ตัวเทียบดีสุด {vr['best_comparator']}",
       st3([vr["rule_8_3"] == "ดีกว่าตัวเทียบ", vr["best_comparator"] == "①c"]))
mm_ = MONTHLY.dropna(subset=["r2oos_med_monthly"])
lw = [(r["row"], r["r2oos_med_monthly"], r["r2oos_med_weekly_same_funds"]) for _, r in mm_.iterrows()]
ex_add(15, "รายเดือน R²_oos ต่ำกว่ารายสัปดาห์ทุกแถว", " · ".join(f"{a} {b:.3f} vs {c:.3f}" for a, b, c in lw), st3([b < c for a, b, c in lw]))
ld_all = {**LEAD_E, **LEAD_O}
ex_add(16, "lead diagnostic < 10% ของกอง", (" · ".join(f"{k} {v:.3f}" for k, v in ld_all.items()) if ld_all else "N/A (E-X1 ไม่มี factor ที่ทบจากรายวัน) · O: ไม่มีข้อมูล"),
       st3([all(v < 0.10 for v in ld_all.values())]) if ld_all else "N/A")
ex_add(17, "Q-E2: E-X1 − ③a ≥ 0.05 แม้ E-X1 ไม่มี factor ทอง/บอนด์", f"Δ {QE.loc[1, 'diff']:+.3f} (CI {QE.loc[1, 'ci_lo']:+.3f}…{QE.loc[1, 'ci_hi']:+.3f})", st3([QE.loc[1, "diff"] >= 0.05]))
EXPDF = pd.DataFrame(EXP)
EXPDF["note"] = "ความคาดหมายเขียนก่อนรัน · ระยะ 1 คาดผิดบ่อย · ข้อ 12/14 ใช้ฉบับแก้ของ S013 §3 · 'ตรง' ต้องครบทุกส่วนย่อย"
save(EXPDF, "expectations_vs_results.csv")
EXP_TALLY = EXPDF["status"].value_counts().to_dict()
log(f"ความคาดหมาย: {EXP_TALLY}")

# ═════════════════════════ results.md ═════════════════════════
def tbl(df, cols, ren=None, nd=3):
    d = df[cols].copy()
    if ren:
        d = d.rename(columns=ren)
    return md(d, nd)


sc_e = SCORE_E[SCORE_E["set"] == "EVAL"].set_index("row")
bt = BOOT.set_index(["row", "stat"])
main_rows = []
for nm in ROWS_E:
    g_ = GRS_E[(GRS_E["row"] == nm) & (GRS_E["window"] == "test")]
    p_ = PY_E[(PY_E.get("row") == nm) & (PY_E.get("window") == "test")] if "row" in PY_E.columns else pd.DataFrame()
    main_rows.append(dict(แถว=nm, บทบาท=sc_e.loc[nm, "role"], K=int(sc_e.loc[nm, "K"]), n=int(sc_e.loc[nm, "n"]),
                          adjR2_med=sc_e.loc[nm, "adjr2_med"], adjR2_IQR=sc_e.loc[nm, "adjr2_iqr"],
                          R2oos_med=sc_e.loc[nm, "r2oos_med"], R2oos_CI=f"{bt.loc[(nm, 'r2oos_med'), 'lo']:.3f}…{bt.loc[(nm, 'r2oos_med'), 'hi']:.3f}",
                          R2oos_IQR=sc_e.loc[nm, "r2oos_iqr"], gap=sc_e.loc[nm, "r2gap_med"], mean_abs_alpha_pct=sc_e.loc[nm, "mean_abs_alpha_pct"],
                          BH_alpha=int(BH_E.set_index("row").loc[nm, "n_reject_bh10"]), GRS_p_test=float(g_["p"].iloc[0]) if len(g_) else np.nan,
                          PY_pboot_test=float(p_["p_boot"].iloc[0]) if len(p_) and "p_boot" in p_.columns else np.nan,
                          bic_med=sc_e.loc[nm, "bic_med"], dBIC_vs_EX0=sc_e.loc[nm, "dBIC_med_vs_E-X0"], dBIC_vs_1a=sc_e.loc[nm, "dBIC_med_vs_1a"],
                          r_H1H2_mean=float(STAB_MEAN.get(nm, np.nan)), roll_first_last_mean=float(ROLL_MEAN.get(nm, np.nan))))
MAIN_E = pd.DataFrame(main_rows)
MAIN_E.to_csv(OUT / "scorecard_E_main.csv", index=False)
LABELS = ("**ป้ายบังคับ:** (ก) k* ของ E-PCA ใช้ `combine_k` ที่รวม ED ซึ่งตรงเฉพาะแหล่งรอง [ข้อ 22, 47] · (ข) ช่วง test 2024–2025 ถูกใช้ซ้ำตั้งแต่ระยะ 1 → R²_oos **ไม่ใช่หลักฐานนอกช่วงที่อิสระ** · "
          "(ค) การออกแบบ (pool · กลุ่ม · เกณฑ์) ทำหลังเห็นผลระยะ 1 · (ง) U_E/U_O มี look-ahead (อายุ ณ 2025-12-31) + survivorship · ชุด PCA ใช้ dup_pairs ที่ corr คำนวณทั้งช่วงหลัก (รวม test) (m9) · "
          "(จ) กอง O มีน้อย (13 หน่วย · EVAL 12) → รายกอง/กลุ่มย่อยเป็นหลัก · (ฉ) factor long–short (KF · JKP · TERM · REIT_e · e_* · PC · RPC) **ลงทุนไม่ได้** · KF/JKP/TERM เป็น USD ไม่แปลงบาท · "
          "(ช) KF WML ทบรายวันต่างจากไฟล์รายเดือนทางการ (corr 0.94) · (ซ) factor กลุ่มกำหนดจาก**ชื่อกอง** · (ฌ) α ของแถว PCA = α เทียบพอร์ตกองเพื่อน · α ของแถว X = เทียบ factor ภายนอก · "
          "(ญ) อนุกรม 'ต่อรหัส' 4 หน่วยสร้างโดยกติกาของ designer (สัปดาห์ 2023-12-01 ของรหัสเก่าเป็น 'สัปดาห์ไม่เต็ม') · (ฎ) ETF/MSCI ปิดเวลา NY → Dimson lag 1 · (ฏ) JKP จบ 2025-12-31")
md_ = []
A = md_.append
A("# S012_L1EO results — factor แยกกอง E / O (S012 + S013) · เชิงอธิบาย · ไม่นับ trial\n")
A(f"รันโดย `factor-analyst` · phase pre + full · run.py sha256 `{RUN_SHA}` · ข้อมูลทุก sha256 ตรง S013 §4 · lib เดิม 15 ไฟล์ตรง `runs/S010/run_meta.json` + `l1eo.py` · regression S003/S006 ผ่านทุกบิต (`regression_S003_S006.json`) · "
  f"{'**ข้อมูลจำลอง (--sim) — ไม่ใช่ผลรายงาน**' if SIM else 'ข้อมูลจริง'} · seed {SEED} · ไม่แตะ `trials.csv` · ตัวเลขทุกตัวมาจากการรันนี้ (ไม่ได้ตรวจซ้ำเองสำหรับตัวเลข corr ของ factor ภายนอกที่ยกจาก QA_EO)\n")
A(LABELS + "\n")
A("> **ถ้อยคำสำคัญ (S013 / BRIEF 116 / รีวิว):** ห้ามเขียนว่า 'ชุดกลไกใช้ไม่ได้กับทอง' จากผล 'ไม่ดีกว่า ③a' · 'ไม่ถูกเลือกเป็น factor ร่วม ≠ ไม่สำคัญกับกลุ่มย่อย' (median = กฎเสียงข้างมาก) · β(FX) ของกอง REIT รวมส่วนที่ถูกย้ายเข้า REIT_e → ห้ามอ่านเป็นสัดส่วน hedge · "
  "ระยะ 1 ห้ามสรุปว่า 'ลงทุนได้' · α ไม่ใช่หลักฐานฝีมือ · ผลภาคผนวก/what-if ฝั่ง 'ผ่าน' = 'ข้อมูลชุดเดียวกัน ไม่ใช่หลักฐานอิสระ'\n")
A("## 0. ข้อมูล ชุดกอง และการตรวจก่อนรัน\n")
A(f"- ตรวจรายชื่อหน่วยทุกชุดกับ `S013_pca_sets.csv` ทุกหน่วย (ไม่ใช่แค่จำนวน): **{'ตรง' if not DIFF else DIFF}** · E: SEL {len(SEL_E)} · EVAL {len(EVAL_E)} · EVAL52 {len(EVAL52_E)} · STAB {len(STAB_E)} · ตัดซ้ำ {len(DED_E)} · PCA balanced {len(BAL_E)} · unbalanced {len(UNB_E)} · O: SEL {len(SEL_O)} · EVAL {len(EVAL_O)} · EVAL52 {len(EVAL52_O)} · STAB {len(STAB_O)}")
A("- **n1 (รีวิว S013) แก้ถ้อยคำ:** `universe.csv` `n_weeks` นับในช่วงหลัก 2021-01-08 → 2025-12-26 (ไม่ได้นับถึง 2026-07-31 ตามที่ S013 §1 เขียน) · นิยามใหม่ n_weeks_main จึงต่างจากระยะ 1 เฉพาะหน่วยต่อรหัส 4 หน่วย · ชุดกองไม่เปลี่ยน")
A("- **n2:** AQR ภาคผนวก A2 = N/A (BRIEF 117) · ไม่ใช้คอลัมน์ AQR\n")
A("ตารางต่อรหัส (S013 §2):\n")
A(md(SPL[["unit", "old", "new", "week", "n_old_rows", "n_new_rows", "n_overlap_rows", "old_ret_at_week", "new_ret_at_week", "old_rows_after_week", "new_rows_before_week"]], 5))
A(f"- {len(g)} รหัส → {len(UNITS)} หน่วย (E {len(E_UNITS)} · O {len(O_UNITS)}) · factor กลุ่มจากชื่อกอง: {int((gu[gu.policy == 'E'].group_factor != 'ไม่มี').sum())} หน่วยได้ factor · EVAL ที่ได้ factor {int(((gu.group_factor != 'ไม่มี') & gu.index.isin(EVAL_E)).sum())} จาก {len(EVAL_E)}\n")
A("## 1. ผลหลัก E — ตารางคะแนน (EVAL_E)\n")
A(md(MAIN_E[["แถว", "บทบาท", "K", "n", "adjR2_med", "adjR2_IQR", "R2oos_med", "R2oos_CI", "R2oos_IQR", "gap", "mean_abs_alpha_pct", "BH_alpha"]], 3))
A(md(MAIN_E[["แถว", "GRS_p_test", "PY_pboot_test", "bic_med", "dBIC_vs_EX0", "dBIC_vs_1a", "r_H1H2_mean", "roll_first_last_mean"]], 3))
A(f"CI = สุ่ม**กลุ่มกองอิสระ**ทั้งก้อน {N_BOOT} รอบ ({len(np.unique(clusters_arr))} กลุ่ม) · GRS = 12 พอร์ตกลุ่ม ช่วง test (เฉพาะแถว factor ร่วม · E-X2/M1 = N/A) · PY p_boot ช่วง test (เฉพาะกองครบทุกแถว) · "
  "mean|α| หน่วย %/ปี · α ของแถว PCA เทียบพอร์ตกองเพื่อน (ฌ) · self-inclusion: R²_oos ของ E-PCA-a1/①a/①c มีกองตัวเองอยู่ใน PC\n")
A("ชุดย่อย (A5 + m6):\n")
A(md(SCORE_E[SCORE_E["row"].isin(["E-PCA-a1", "E-X1", "E-X2", "E-H", "③a"])][["row", "set", "n", "adjr2_med", "r2oos_med", "r2gap_med", "mean_abs_alpha_pct"]], 3))
A("### เกณฑ์เข้ารอบ 8.1 (ล็อก · BRIEF 115(4))\n")
A(md(CRIT[["row", "role", "C1_r2oos_ge_0p9max", "r2oos_med", "C2_gap_le_0p15", "gap_med", "C3_mean_r_ge_0p6", "mean_r_h1h2", "C4_dBIC_le_0", "C4_vs", "C4_dBIC_med", "C5_named", "passed_8_1"]], 3))
A("C4 = None → ไม่มีแถวที่เล็กกว่าในสายเดียวกัน (ไม่ใช้) · C3 ของ E-X2 = เฉลี่ย r ของ factor ร่วม + factor กลุ่มที่มี ≥ 10 สมาชิก STAB (m5) · E-H รวม RPC · E-PCA ทุก PC · E-H อาจมี factor ถึง 9 ตัว (19 พารามิเตอร์ใน 155 แถว) — gap ของ C2 สะท้อนข้อนี้ (m14 ง)\n")
A("### คำตอบการแข่ง 8.2\n")
A(md(QE, 3))
A("## 2. stepwise ของ factor ร่วม (train เท่านั้น)\n")
A(f"- placebo: เลือก {[v['n_selected'] for v in PL['shifts'].values()]} ตัว (shift 26/52) · τ = **{PL['tau']}** · {PL['rule']} · score ดีที่สุดรอบแรกของ placebo {[round(v['best_score_round1'], 2) for v in PL['shifts'].values()]}")
A(f"- E-X1 = **{list(X1.columns)}** · เหตุหยุด `{last_action}` · จำนวน candidate ที่ประเมินทั้งหมด (จริง) {len(STEP_ALL)} + placebo {PL['n_candidates_evaluated']} · **'ไม่ถูกเลือกเป็น factor ร่วม ≠ ไม่สำคัญกับกลุ่มย่อย'** (median ข้ามตัวแทน = กฎเสียงข้างมาก · m7)\n")
A(md(STEP_LOG.drop(columns=["tag"]), 3))
A("อันดับ 1–3 ของแต่ละรอบ (พร้อมสัดส่วนตัวแทนที่ ΔBIC ≤ −2):\n")
A(md(STEP_ALL[STEP_ALL["rank"] <= 3].drop(columns=["tag"]), 3))
A("## 3. ผลหลัก E — E-X2 factor กลุ่ม (คำตัดสิน 8.3 · กติกา Q1a ของ L3)\n")
A(md(VERDICT_F[VERDICT_F["kind"] == "factor กลุ่ม"][["factor", "n_ref", "drop_d_r2oos_med", "drop_d_bic_med", "vif_dimson", "n_beta_sig", "n_beta_sig_groups", "placebo_max", "verdict", "flag", "pseudo_oos_lens"]], 4))
A("pseudo-OOS (diagnostic · ข้อ 60) = median ΔR² ใน pseudo-test เมื่อ β ของ e_g และ e_CHINA ประมาณจาก pseudo-train — **ไม่ใช่หลักฐานนอกช่วงใหม่**\n")
A("คำตัดสิน factor ร่วมใน E-X1:\n")
A(md(VERDICT_F[VERDICT_F["kind"] == "factor ร่วม"][["factor", "n_ref", "drop_d_r2oos_med", "vif_dimson", "n_beta_sig", "n_beta_sig_groups", "placebo_max", "verdict"]], 4))
A("## 4. รายงานราย factor (E) — ตัวชี้ 6.1–6.10\n")
_c = ["row", "factor", "n_ref", "shap_share_med", "single_adjr2_med", "single_r2oos_med", "d_pair_axis_r2oos_med", "drop_d_adjr2_med", "drop_d_r2oos_med", "drop_d_bic_med",
      "n_beta_sig_bh", "n_beta_sig_groups", "placebo26", "placebo52", "vif_dimson", "r_h1h2", "roll_first_last", "name_label", "max_corr_1a_pc"]
A(md(FR_E[FR_E["role"] == "แข่ง"].reindex(columns=_c), 3))
A("ตัวเทียบ (บรรยาย):\n")
A(md(FR_E[FR_E["role"] != "แข่ง"].reindex(columns=_c), 3))
A("กลุ่มกองที่ loading สูงสุด (6.9) และชื่อ 3 อันดับของ PC/RPC อยู่ใน `factor_report_E.csv` · `interpret.csv` · Shapley รายกอง `shapley_E.csv`\n")
A("### set-level เทียบ ①a (canonical · spanning · ΔBIC)\n")
A(md(CANON, 3))
A(f"### lead diagnostic (6.11): E-X1 {LEAD_E if LEAD_E else 'N/A — ไม่มี factor ที่ทบจากรายวันใน E-X1'} · O {LEAD_O}\n")
A("## 5. ผลหลัก O — ทอง / REIT (ชุดตายตัว · ไม่มีการคัดเลือก)\n")
A(md(SCORE_O[SCORE_O["set"] == "EVAL_O (12)"][["row", "group", "n", "K", "adjr2_med", "r2oos_med", "r2gap_med", "mean_abs_alpha_pct", "signed_mean_alpha_pct", "bic_med"]], 3))
A("### คำตัดสิน O (เกณฑ์ที่ล็อก 8.3 + คำตัดสินบรรยายทอง S013 §3)\n")
A(md(VERDICT_O, 3))
A("### ตารางทอง 3 ตาราง (+ T0 เกณฑ์ที่ล็อก) และ REIT (ลงทะเบียนล่วงหน้า · `o_gold_tables.csv`)\n")
A(md(O_TABLES.drop(columns=["per_fund"]), 3))
A("รายกอง O (EVAL52_O 13 หน่วย) อยู่ใน `fund_level_O.csv` · DAOL-USREIT train 67 แถว (ธง) · I-GOLD* ต่อรหัส (ญ)\n")
A(md(FLO[FLO["row"] == "O-X"][["unit", "group", "subgroup", "fx_risk_flag", "in_EVAL_O", "n_train_rows", "alpha_pct_yr", "t_alpha_hac", "adj_r2", "r2_oos"] + [c for c in FLO.columns if c.startswith("beta_")]], 3))
A("**ห้ามอ่าน β(FX) ของกอง REIT เป็นสัดส่วน hedge** (รวมส่วน −b·FX ที่ถูกย้ายเข้า REIT_e · m14 ข)\n")
A("GRS 2 พอร์ต (N = 1 · ช่วง test · บรรยาย) และ α · BH ใน O:\n")
A(md(GRS_O[["row", "portfolio", "window", "T_used", "F", "p", "alpha_pct_yr", "t_alpha_hac"]], 3))
A(md(BH_O, 3))
A("O-tilt (ภาคผนวก · รายกอง):\n")
A(md(O_TILT, 3))
A("factor report O-X:\n")
A(md(FR_O.reindex(columns=["row", "factor", "n_ref", "shap_share_med", "single_adjr2_med", "single_r2oos_med", "drop_d_r2oos_med", "n_beta_sig_bh", "beta_med", "vif_dimson", "r_h1h2", "top_groups"]), 3))
A("## 6. ภาคผนวก\n")
A("- **A1** (style ETF แทน KF · ไม่ใช้ตัดสิน · 'ข้อมูลชุดเดียวกัน ไม่ใช่หลักฐานอิสระ'):\n")
A(md(A1, 3))
A("- **A2 (AQR)**: N/A ตาม BRIEF 117 (ไม่กระทบแถวหลัก)\n")
A("- **A3 รายเดือน** (ไม่มี null รองรับ — ดูความสอดคล้องเท่านั้น · ป้าย ช):\n")
A(md(MONTHLY, 3))
A("- **A4** ชื่อกลุ่มเทียบ primary ของ L2:\n")
A(md(A4.drop(columns=["note"]), 3))
A("## 7. จำนวน factor/แถวที่ลองทั้งหมด (`n_tried.csv` · BRIEF 110)\n")
A(md(NTRIED, 0))
A(f"รวมนับเชิงรายการ = {NTRIED_TOTAL} (ไม่ใช่จำนวน trial — งานนี้ไม่นับ trial) · การคัด factor ร่วมยังเป็นการค้นบนข้อมูลชุดเดียวกับระยะ 1 แม้ล็อกกติกาแล้ว\n")
A("## 8. ความคาดหมายเทียบผล\n")
A(md(EXPDF[["id", "expectation", "result", "status"]], 3))
A(f"**ยอดรวม:** ตรง {EXP_TALLY.get('ตรง', 0)} · บางส่วน {EXP_TALLY.get('บางส่วน', 0)} · ไม่ตรง {EXP_TALLY.get('ไม่ตรง', 0)} · N/A {EXP_TALLY.get('N/A', 0)} จาก {len(EXPDF)} ข้อ ('ตรง' ต้องครบทุกส่วนย่อยของข้อนั้น)\n")
A("## 9. สิ่งที่พบ\n")
fnd = []
fnd.append(f"E-PCA-a1 (k* = {EP['k']}): median R²_oos {o_['E-PCA-a1']:.3f} · E-X1 {o_['E-X1']:.3f} · E-X2 {o_['E-X2']:.3f} · E-H {o_['E-H']:.3f} · ①a {o_['①a']:.3f} · ①c {o_['①c']:.3f} · ③a {o_['③a']:.3f} · M1 {o_['M1']:.3f} (ช่วง test ใช้ซ้ำ — ป้าย ข)")
fnd.append("แถวที่ผ่านเกณฑ์ 8.1 ของ E (แถวแข่ง): " + (", ".join(r for r in COMPETE if PASS81[r]) if any(PASS81[r] for r in COMPETE) else "ไม่มีแถวผ่าน"))
fnd.append("คำตอบ: " + " · ".join(f"{r['question'][:4]} = {r['verdict']}" for _, r in QE.iterrows()))
fnd.append(f"factor ร่วมที่ stepwise เลือก (นอกจาก MKT): {SELECTED if SELECTED else 'ไม่มี'} (τ = {PL['tau']} · เหตุหยุด {last_action})")
fnd.append("factor กลุ่ม: " + ", ".join(f"{k}={v}" for k, v in VG["verdict"].items()))
fnd.append(f"O ทอง: เกณฑ์ที่ล็อก = {vg['rule_8_3']} (ตัวเทียบดีสุด {vg['best_comparator']}) · คำตัดสินบรรยาย = {vg['descriptive']} · O-X ดีกว่าตัวดีสุดของ (①a,①c) {vg['med_d_r2oos_vs_stock']:+.3f} (ส่วนต่าง median R²_oos) · REIT: {vr['rule_8_3']} (ตัวเทียบดีสุด {vr['best_comparator']} · Δ {vr['med_d_r2oos']:+.3f})")
for f_ in fnd:
    A("- " + f_)
A("\n## 10. ข้อจำกัด\n")
for t_ in ["ป้าย (ก)–(ฏ) ข้างต้น · ไม่มี holdout (NAV 2026 มีรู) · R²_oos ใช้ช่วง test ซ้ำกับระยะ 1 (ป้าย ข)",
           "การคัด factor ร่วมเป็นการค้นบนข้อมูลชุดเดียวกับระยะ 1: pool 11 × ≤ 6 รอบ (+ placebo 2 ชุด) · ค่าตัด −2 (Kass–Raftery) ยังไม่ยืนยันแหล่ง · เพดาน 6 / pool 12 เป็นค่าตั้ง",
           "กลุ่มจากชื่อกอง: ชื่ออาจไม่ตรง holding (Sensoy 2009) · ลำดับความสำคัญและคำของ designer เป็นกติกาที่ตั้งเอง · INDIA (EVAL 4) / INFRA (EVAL 3) มี factor แต่คำตัดสินอ่านไม่ได้ · VIETNAM/JAPAN แกว่งง่าย · ASIA เป็นกลุ่มผสม (รวม ASEAN 2 กอง)",
           "EVAL_E 160 จาก 215 หน่วย: class ตัวแทนของ L0 หลาย family เริ่ม 2022–2023 · U_O เสียกอง Eastspring 4 กอง · twin test ทำไม่ได้ (ใช้ FX Risk Flag snapshot)",
           "residualize ตรึง β จาก train → ตั้งฉากเฉพาะ train · KF รายวันทบเป็นสัปดาห์ (ประมาณ) · JKP ใช้ capped VW · CC BY-NC",
           "①a/①c สร้างจาก E/F/O ปน — ไม่ใช่ 'PCA ของ E' · M1 ใช้ primary ที่เลือกด้วยช่วง test ของระยะ 1 · หน่วยต่อรหัสไม่มี primary (M1 = ①a + FX)",
           "factor_report ของ E-X2: factor ร่วมรายงานเฉพาะ Shapley/β มีนัย (ตัวชี้อื่นของ factor ร่วมดูที่แถว E-X1) · M1 ไม่มี factor report (factor รายกองต่างกัน)",
           "ระยะ 1 ห้ามสรุปว่า 'ลงทุนได้' · α ไม่ใช่หลักฐานฝีมือ · long–short เป็นเชิงอธิบาย"]:
    A("- " + t_)
A("\n## 11. ต้องให้ผู้ใช้ตัดสินใจ\n")
A("- ยืนยันเกณฑ์ข้อ 8 ตอนสรุป (BRIEF 115(4)) · เรื่องลบ/ไม่ commit ไฟล์ AQR ใน `factors_eo_*.parquet` (BRIEF 117) ให้ผู้ใช้ตัดสิน\n")
A("## 12. การรันและความสอดคล้อง (BRIEF 106)\n")
A(f"- run.py sha256 phase pre `{RUN_SHA_PRE}` · phase full `{RUN_SHA}` · {'**ต่างกัน — ต้องมี diff ด้านล่าง**' if RUN_CHANGED else 'เท่ากัน (ไม่มีการแก้ run.py ระหว่าง phase)'} · สำเนา `run_pre.py` เก็บไว้ตอนเริ่ม phase pre")
if RUN_CHANGED and (OUT / "run_pre.py").exists():
    import difflib
    dl = list(difflib.unified_diff((OUT / "run_pre.py").read_text().splitlines(), Path(__file__).read_text().splitlines(), "run_pre.py", "run.py", lineterm="", n=0))
    A("```diff\n" + "\n".join(dl[:400]) + "\n```")
A("- ไฟล์ phase pre (selection) ถูกคำนวณซ้ำใน phase full และตรงทุกบิต · ผลซ้ำ: `repro_check.json` · pytest: `pytest_all.log`\n")
(OUT / "results.md").write_text("\n".join(md_) + "\n", encoding="utf-8")

# ───────────── run_meta.json ─────────────
import scipy  # noqa: E402
import statsmodels  # noqa: E402
OUTS = {p.name: io_l1.sha256_file(p) for p in sorted(OUT.iterdir()) if p.is_file() and p.name not in ("run.log", "run_pre.log", "run_meta.json", "run_meta_pre.json", "results.md",
                                                                                             "repro_check.json", "pytest_all.log", "run_pre.py", "run.py", "decisions_pre_run.md",
                                                                                             "regression_S003_S006.json", "repro_check.py") and not p.name.startswith("regression")}
meta = dict(created=datetime.now().isoformat(timespec="seconds"), phase="full", seed=SEED, sim=SIM, smoke=SMOKE, runtime_sec=round(time.time() - T0, 1),
            python=platform.python_version(), versions=dict(numpy=np.__version__, pandas=pd.__version__, scipy=scipy.__version__, statsmodels=statsmodels.__version__),
            spec_files=SPEC_FILES, spec_sha256={f: io_l1.sha256_file(TEAM / f) for f in SPEC_FILES}, run_py_sha256=RUN_SHA, run_py_sha256_pre=RUN_SHA_PRE, run_py_changed_between_phases=RUN_CHANGED,
            data_pins_sha256={k: v for k, v in PIN.items()}, lib_sha256=LIBH, decisions_sha256=DEC_SHA, tau=PL["tau"], selected=SELECTED, A1_selected=SEL_A1, k_star=EP["kstar"], k_used=EP["k"],
            k_res=HY["k_res"], expectations=EXP_TALLY, n_tried_total=NTRIED_TOTAL, output_sha256=OUTS)
(OUT / "run_meta.json").write_text(json.dumps(meta, indent=1, ensure_ascii=False, default=_jdef))
log(f"เสร็จ · runtime {time.time() - T0:.1f}s")
