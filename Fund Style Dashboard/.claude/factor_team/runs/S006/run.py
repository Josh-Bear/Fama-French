"""S006 run (L3 VIF-cleaned) — เรียก lib เท่านั้น · ใช้: python run.py [--out DIR]"""
import ast
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
import forms as fm_  # noqa: E402
import io_l1  # noqa: E402
import l2  # noqa: E402
import l3  # noqa: E402
import regress as rg  # noqa: E402
import scorecard as sc  # noqa: E402
import tests_stat as ts  # noqa: E402
from pca import factor_returns  # noqa: E402
from samples import window_mask  # noqa: E402

SEED = 20261015
OUT = Path(__file__).resolve().parent
if "--out" in sys.argv:
    OUT = Path(sys.argv[sys.argv.index("--out") + 1])
OUT.mkdir(parents=True, exist_ok=True)
T0 = time.time()
LOGF = open(OUT / "run.log", "w")
TEAM = io_l1.TEAM
S003, S005 = TEAM / "runs" / "S003", TEAM / "runs" / "S005"
CI_LABEL = "CI สุ่มกองแบบอิสระภายใน policy — กองสัมพันธ์กัน → CI แคบกว่าจริง"


def log(msg):
    line = f"[{datetime.now().isoformat(timespec='seconds')} +{time.time() - T0:6.1f}s] {msg}"
    LOGF.write(line + "\n")
    LOGF.flush()
    print(line, flush=True)


def save(df, name, index=False):
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
            else:
                cells.append(str(v))
        out.append("| " + " | ".join(cells) + " |")
    return "\n".join(out) + "\n"


def gmed(x, sub, pol_arr, g):
    m = sub & (pol_arr == g if g != "ALL" else True)
    x = np.asarray(x, float)[m]
    x = x[np.isfinite(x)]
    return float(np.median(x)) if len(x) else np.nan


# ───────────────────────── 0) ตรวจ sha256 ─────────────────────────
log("START run S006")
man = io_l1.verify_manifest()
D_ = TEAM / "data"
PIN = {
    "data/factors_ext_weekly.parquet": (D_ / "factors_ext_weekly.parquet", "3105b6e7fe32ffd3648e8feac8dbd03a8db22b7e8eb245c5faf462b14da5e296"),
    "runs/S003/factors_S003_weekly.parquet": (S003 / "factors_S003_weekly.parquet", l2.S003_FAC_SHA),
    "runs/S003/fund_level.csv": (S003 / "fund_level.csv", "36b41161d6a13c1184a4052d9e799f660f431c2694dc57fafd747f8e695bf8cf"),
    "runs/S003/grs_ports.csv": (S003 / "grs_ports.csv", "d55011094898acdf6e0419c90a3b2713479451380cacc0bf950559c43b98ba19"),
    "runs/S003/regions.csv": (S003 / "regions.csv", "2fa3ce691c9dd66ef523e1baca228a635369d2971857797a05c105c1306e6866"),
    "runs/S005/primary_index.csv": (S005 / "primary_index.csv", "5a94ab9b498bb107600938d37f665c7263d9f0a5973460159c09ae83a799275c"),
    "runs/S005/fund_clusters.csv": (S005 / "fund_clusters.csv", "072cd97ade7e01a32edb9aaf5b949381d1500dcb1ed909558bee3a373e2fc0cb"),
    "runs/S005/criteria_P4.json": (S005 / "criteria_P4.json", "0db21831202f8ff2378923740074d2517be1a37563d5f09a64e103d8651cbfb2"),
    "runs/S005/fund_level.csv": (S005 / "fund_level.csv", "1be9d49e70f385cd9a6e09d586f16ec3677622ee87b598826a34bebd69a89cf5"),
    "runs/S005/placebo_rule.json": (S005 / "placebo_rule.json", "0460b5b2ff9721c3be97c134fd15c19d28c6596c0a5f6ad5dd08d842ec3f78dc"),
    "specs/S005_L2_addendum_to_S004.md": (TEAM / "specs" / "S005_L2_addendum_to_S004.md", "c71ad963b64347d463c8d8a30fe55240b851be85d364f35a6ab121a7112f8468"),
    "config.py": (io_l1.ROOT / "config.py", "711d5738ecf25fc0064e10134ae4cf5d8cfb0cee22d8dd5fbf0174fe925a7d66"),
    "cache/results.csv": (io_l1.ROOT / "cache" / "results.csv", "7c0ce137c4a8692e0136cefe1c4ddbad4cea42cca5e0af8aaa8bb36a05239cfc"),
}
pin_sha = {}
for k, (p, want) in PIN.items():
    got = io_l1.sha256_file(p)
    assert got == want, f"sha256 ไม่ตรง: {k}"
    pin_sha[k] = got
lib_hashes = io_l1.lib_hash()
s5lib = json.load(open(S005 / "run_meta.json"))["lib_sha256"]
assert all(lib_hashes.get(k) == v for k, v in s5lib.items()), "lib เดิมต่างจาก S005 run_meta"
assert set(lib_hashes) - set(s5lib) == {"l3.py"}, set(lib_hashes) - set(s5lib)
REGR = json.load(open(OUT / "regression_S003_S005.json")) if (OUT / "regression_S003_S005.json").exists() else json.load(open(TEAM / "runs" / "S006" / "regression_S003_S005.json"))
assert REGR["all_pass"], "regression S003/S005 ไม่ผ่าน"
log(f"sha256 ข้อมูล 8 ไฟล์ + {len(PIN)} ไฟล์ pin ตรง · lib 12 ไฟล์เดิมตรง S005 + l3.py · regression S003/S005 ผ่าน (ทุกบิต)")

# ───────────────────────── 1) ข้อมูล ─────────────────────────
R = io_l1.load_returns("W")
F = io_l1.load_factors("W")
Rm = io_l1.load_returns("M")
Fm = io_l1.load_factors("M")
Fext = pd.read_parquet(D_ / "factors_ext_weekly.parquet")
U = io_l1.load_universe().set_index("FundCode")
pol = U["policy"]
idx = R.index
POS = np.arange(len(idx))
S = l2.fund_sets(R, U, io_l1.load_dup_pairs())
base_f, bal, EVAL, STAB, PYTE, PYTR, E67 = (S[k] for k in ("base", "bal", "EVAL", "STAB", "PYTE", "PYTR", "E67"))
got = dict(base=len(base_f), bal=len(bal), EVAL=len(EVAL), STAB=len(STAB), PYTR=len(PYTR), PYTE=len(PYTE), E67=len(E67))
assert got == dict(base=277, bal=134, EVAL=207, STAB=191, PYTR=148, PYTE=206, E67=67), got
mtr, mte = window_mask(idx, "train"), window_mask(idx, "test")
polE = pol[EVAL].to_numpy()
divE = (U.loc[EVAL, "div_flag"] == "Y").to_numpy()
inE67 = np.isin(EVAL, E67)
I, blocks = l2.index_set(F)
M28 = I[blocks["M28"]]
C0 = ex.line3(F, "3a")
EXT = l3.ext_excess(Fext, F)
assert (EXT.index == F.index).all() and EXT.notna().all().all() and F.index.max() < pd.Timestamp("2026-01-01")
TDEX = (F["TDEX_THB"] - F["RF_BOT"]).rename("TDEX")
I_all = pd.concat([M28, EXT, C0[["MKT"]]], axis=1)
assert set(l3.C11 + l3.S10 + l3.P4) <= set(M28.columns) and set(l3.HIER_CHILDREN) <= set(I_all.columns)
FG = pd.read_csv(D_ / "factor_groups.csv")["factor"].tolist()
ORDER = FG
fac_path = S003 / "factors_S003_weekly.parquet"
BASES = {"1a": l2.load_l1_factors(fac_path, "1a"), "1c": l2.load_l1_factors(fac_path, "1c")}
FL5 = pd.read_csv(S005 / "fund_level.csv")
FL3 = pd.read_csv(S003 / "fund_level.csv")
PRIMDF = pd.read_csv(S005 / "primary_index.csv")
PRIM_L2 = {b: PRIMDF[PRIMDF.form == f"{b}@4"].set_index("FundCode")["index"] for b in BASES}
PRIM_NONE = PRIMDF[PRIMDF.form == "none"].set_index("FundCode")["index"]
FC = pd.read_csv(S005 / "fund_clusters.csv")
GMAP = FC.set_index("FundCode").group_id.to_dict()
RULE = json.load(open(S005 / "placebo_rule.json"))
STEP = RULE["step"]
base_rows = {"train": mtr & (POS >= 1), "test": mte & (POS >= 1)}
log(f"ชุดกอง ตรง spec: {got} · M28 {M28.shape} · EXT {EXT.shape} · placebo_rule ขั้น {STEP}")
vcols = lambda X, m=mtr: ts.vif(X.to_numpy(float)[m & np.isfinite(X.to_numpy(float)).all(1)])


def dimson_vif(X, m=mtr):
    D = rg.lag_stack(X.to_numpy(float))
    ok = m & np.isfinite(D).all(1)
    return ts.vif(D[ok])


# ───────────────────────── 2) A0 / A1 / primary_A ─────────────────────────
fullm = window_mask(idx, "full")
a0 = []
for b, f in BASES.items():
    for wn, wm in (("train", mtr), ("full_2021_2025", fullm)):
        for sn, X in (("C11", I[l3.C11]), ("S10", I[l3.S10]), ("C11+S10", I[l3.C11 + l3.S10]), ("f+C11+S10", pd.concat([f, I[l3.C11 + l3.S10]], axis=1))):
            t, kap = l3.vif_table(X, wm)
            t.insert(0, "kappa", kap)
            t.insert(0, "n_cols", X.shape[1])
            t.insert(0, "set", sn)
            t.insert(0, "window", wn)
            t.insert(0, "base", b)
            a0.append(t)
A0 = save(pd.concat(a0, ignore_index=True), "vif_A0.csv")
log("เขียน vif_A0.csv")
S_A, S_A_b, a1log, PRIM_A = {}, {}, [], {}
for b, f in BASES.items():
    X = pd.concat([f, I[l3.C11 + l3.S10]], axis=1)
    kept, lg = l3.vif_backward(X, mtr, protect=list(f.columns), order=list(f.columns) + ORDER, thr=5.0, continue_all=True)
    lg.insert(0, "base", b)
    a1log.append(lg)
    S_A[b] = [c for c in kept if c not in f.columns]
    dropped_b = list(lg[(lg.phase == "descriptive_all") & (lg.dropped != "")].dropped)
    S_A_b[b] = [c for c in S_A[b] if c not in dropped_b]
VA = save(pd.concat(a1log, ignore_index=True), "vif_elim_A.csv")
log("เขียน vif_elim_A.csv · S_A " + json.dumps({b: len(v) for b, v in S_A.items()}) + " · (ข) " + json.dumps({b: len(v) for b, v in S_A_b.items()}))
for b, f in BASES.items():
    d = l2.primary_index(R, I[S_A[b]], mtr, EVAL)
    d.insert(0, "base", b)
    PRIM_A[b] = d.set_index("FundCode")["index"]
    d["in_P4"] = d["index"].isin(l3.P4)
    PRIM_A[b + "_df"] = d
save(pd.concat([PRIM_A[b + "_df"] for b in BASES], ignore_index=True), "primary_A.csv")
log("เขียน primary_A.csv (ก่อน fit)")

# ───────────────────────── 3) B: residualize ─────────────────────────
E_B, BCO, BVIF, B_USED = {}, [], [], {}
for b, f in BASES.items():
    E, co = l3.residualize(I[l3.P4], f, mtr)
    E_B[b] = E
    co.insert(0, "base", b)
    # corr test / corr ระหว่าง e
    Xte = pd.concat([f, E], axis=1)
    cte = Xte[mte].corr().abs()
    co["max_abs_corr_test_e_f"] = [float(cte.loc[j, list(f.columns)].max()) for j in E.columns]
    co["max_abs_corr_train_e_e"] = [float(E[mtr].corr().abs().loc[j].drop(j).max()) for j in E.columns]
    co["max_abs_corr_test_e_e"] = [float(E[mte].corr().abs().loc[j].drop(j).max()) for j in E.columns]
    BCO.append(co)
    t, kap = l3.vif_table(pd.concat([f, E], axis=1), mtr)
    td = dimson_vif(pd.concat([f, E], axis=1))
    t["vif_dimson_max_all"] = float(td.max())
    BVIF.append(t.assign(base=b, kappa=kap))
    mx = float(t[t["col"].isin(l3.P4)].vif.max())
    if t.vif.max() >= 5:
        kept, lg = l3.vif_backward(pd.concat([f, E], axis=1), mtr, list(f.columns), list(f.columns) + l3.P4, 5.0)
        B_USED[b] = [c for c in kept if c in l3.P4]
        lg.to_csv(OUT / f"vif_elim_B_{b}.csv", index=False)
    else:
        B_USED[b] = list(l3.P4)
save(pd.concat(BCO, ignore_index=True), "resid_B_coef.csv")
BVIF = pd.concat(BVIF, ignore_index=True)
log(f"เขียน resid_B_coef.csv · VIF max [f,e(P4)] = {BVIF.groupby('base').vif.max().to_dict()} · fallback: { {b: (len(v) < 6) for b, v in B_USED.items()} }")

# ───────────────────────── 4) C: ลำดับชั้น · placebo · selection · primary_C ─────────────────────────
E_C, HCO = l3.hier_residuals(I_all, mtr)
assert E_C.shape[1] == 37
save(HCO, "hier_coef.csv")
log("เขียน hier_coef.csv")
PL = l3.placebo_forward(R, C0, E_C, mtr, EVAL, shifts=(26, 52), kmax=8)
json.dump(dict(timestamp=datetime.now().isoformat(timespec="seconds"), **PL), open(OUT / "placebo_C.json", "w"), ensure_ascii=False, indent=1, default=float)
TAU = PL["tau"]
log(f"เขียน placebo_C.json (ก่อน selection จริง) · τ = {TAU:.4f} · เลือก " + json.dumps({s: v["n_selected"] for s, v in PL["shifts"].items()}))
SEL, SLOG = l3.forward_select(R, C0, E_C, mtr, EVAL, tau=TAU, kmax=8)
save(SLOG, "select_C.csv")
CBLK = pd.concat([C0, E_C[SEL]], axis=1)
log(f"เขียน select_C.csv · บล็อก C ({len(SEL)}): {SEL}")
PC_ = l3.prim_from_pool(R, CBLK, E_C.drop(columns=SEL), mtr, EVAL)
PRIM_C = PC_.set_index("FundCode")["index"]
save(PC_, "primary_C.csv")
log("เขียน primary_C.csv (ก่อน fit)")

# ───────────────────────── 5) แถว R1–R12 + อ้างอิง ─────────────────────────
ROWS = {}


def add_row(rid, label, kind, base_df, ref, extra=None, per_fund=None, group="main", added=None):
    ROWS[rid] = dict(id=rid, label=label, kind=kind, base_df=base_df, ref=ref, extra=extra, per_fund=per_fund, group=group, added=added or [])


for b, f in BASES.items():
    add_row(f"ref_base_{b}", f"ฐาน ①{b[1]}", "base", f, None, group="ref")
    pfL2 = {c: M28[PRIM_L2[b][c]] for c in EVAL}
    add_row(f"ref_L2_{b}", "L2-1" if b == "1a" else "L2-3", "perfund", f, f"ref_base_{b}", per_fund=pfL2, group="ref", added=["PRIM(M28)"])
add_row("ref_3a", "③a (= C0)", "base", C0, None, group="ref")
ids = {"1a": ["R1", "R2", "R3", "R4", "R5"], "1c": ["R6", "R7", "R8", "R9", "R10"]}
for b, f in BASES.items():
    r1, r2, r3, r4, r5 = ids[b]
    rb = f"ref_base_{b}"
    pfA = {c: I[PRIM_A[b][c]] for c in EVAL if isinstance(PRIM_A[b][c], str)}
    add_row(r1, f"A-prim@{b}", "perfund", f, rb, per_fund=pfA, added=["PRIM(S_A)"])
    lab2 = "B-all′" if len(B_USED[b]) < 6 else "B-all"
    add_row(r2, f"{lab2}@{b}", "common", f, rb, extra=E_B[b][B_USED[b]], added=[f"e({c})" for c in B_USED[b]])
    add_row(r3, f"B-prim@{b}", "perfund", f, rb, per_fund=l3.perfund_from_primary(E_B[b], PRIM_L2[b], EVAL), added=["e_p(i)"])
    add_row(r4, f"B-all5@{b} ⚠️", "common", f, rb, extra=E_B[b][l3.P4_STRICT], added=[f"e({c})" for c in l3.P4_STRICT], group="strict")
    add_row(r5, f"B-prim5@{b} ⚠️", "perfund", f, rb, per_fund=l3.perfund_from_primary(E_B[b], PRIM_L2[b], EVAL, exclude=("MSCI_VIETNAM",)), added=["e_p(i)"], group="strict")
add_row("R11", "C-blk", "common", CBLK, "ref_3a", added=[f"e({c})" for c in SEL])
add_row("R12", "C-prim", "perfund", CBLK, "R11", per_fund={c: E_C[PRIM_C[c]] for c in EVAL if isinstance(PRIM_C[c], str)}, added=["e_j(i)"])
MAIN = ["R1", "R2", "R3", "R4", "R5", "R6", "R7", "R8", "R9", "R10", "R11", "R12"]
for r in ROWS.values():
    r["K"] = r["base_df"].shape[1] + (0 if r["extra"] is None else r["extra"].shape[1]) + (1 if r["per_fund"] is not None else 0)
    r["names"] = list(r["base_df"].columns) + (list(r["extra"].columns) if r["extra"] is not None else []) + (["PRIM"] if r["per_fund"] is not None else [])
    r["mixed"] = r["per_fund"] is not None and len(r["per_fund"]) < len(EVAL)


def fitr(r, mask_tr_, mask_te_, funds, min_obs=52, mon=None):
    """→ (fit, r2oos, provider|None)"""
    if r["kind"] == "perfund":
        fit, ro, pa = l3.fit_perfund(R, r["base_df"], r["per_fund"], mask_tr_, mask_te_, funds, min_obs)
        return fit, ro, (None if r["mixed"] else pa)
    prov = rg.CommonFactors(r["base_df"]) if r["extra"] is None else l2.AugmentedFactors(r["base_df"], extra=r["extra"])
    fit = rg.fit_funds(R, prov, mask_tr_, min_obs, funds=funds)
    ro = rg.oos_r2_funds(R, prov, fit, mask_te_) if mask_te_ is not None else np.full(len(funds), np.nan)
    return fit, ro, prov


# ───────────────────────── 6) span test (ก่อน fit แถวที่ให้คะแนน) ─────────────────────────
span = []


def cmp_rows(a, b_, keys=("alpha", "adj_r2", "r2", "bic", "t_alpha_hac")):
    return {k: float(np.nanmax(np.abs(getattr(a, k) - getattr(b_, k)))) for k in keys}


for b, f in BASES.items():
    # (i) B-all e(P4) vs ดัชนีดิบ P4
    pr, pe = l2.AugmentedFactors(f, extra=I[l3.P4]), l2.AugmentedFactors(f, extra=E_B[b])
    fr_, fe_ = rg.fit_funds(R, pr, mtr, 52, funds=EVAL), rg.fit_funds(R, pe, mtr, 52, funds=EVAL)
    d = cmp_rows(fr_, fe_)
    d["r2_oos"] = float(np.nanmax(np.abs(rg.oos_r2_funds(R, pr, fr_, mte) - rg.oos_r2_funds(R, pe, fe_, mte))))
    for k, v in d.items():
        tl = 1e-8 if k == "t_alpha_hac" else 1e-10
        span.append(dict(test="i_Ball_vs_raw", base=b, stat=k, max_abs_diff=v, tol=tl, passed=v <= tl))
    # (ii) B-prim vs L2-1/L2-3 (กองหลัก P4) และ = ฐาน (กองอื่น) จาก S005 fund_level
    r3 = ROWS[ids[b][2]]
    fit3, ro3, _ = fitr(r3, mtr, mte, EVAL)
    L2name = "L2-1" if b == "1a" else "L2-3"
    baseName = f"ฐาน {b}"
    isP = np.array([c in r3["per_fund"] for c in EVAL])
    for stat, arr in (("alpha", fit3.alpha), ("adj_r2", fit3.adj_r2), ("bic", fit3.bic), ("r2_oos", ro3)):
        col = {"alpha": "alpha", "adj_r2": "adj_r2", "bic": "bic", "r2_oos": "r2_oos"}[stat]
        ref = np.where(isP, FL5[FL5.model == L2name].set_index("FundCode").loc[EVAL, col].to_numpy(),
                       FL5[FL5.model == baseName].set_index("FundCode").loc[EVAL, col].to_numpy())
        v = float(np.nanmax(np.abs(arr - ref)))
        span.append(dict(test="ii_Bprim_vs_L2", base=b, stat=stat, max_abs_diff=v, tol=1e-10, passed=v <= 1e-10))
    # อ้างอิง: ฐาน / L2-1 ตรง S005 (test 30)
    for rid, nm in ((f"ref_base_{b}", baseName), (f"ref_L2_{b}", L2name)):
        fx, rx, _ = fitr(ROWS[rid], mtr, mte, EVAL)
        for stat, arr in (("alpha", fx.alpha), ("adj_r2", fx.adj_r2), ("bic", fx.bic), ("r2_oos", rx)):
            ref = FL5[FL5.model == nm].set_index("FundCode").loc[EVAL, stat].to_numpy()
            v = float(np.nanmax(np.abs(arr - ref)))
            span.append(dict(test="ref_vs_S005", base=b, stat=f"{nm}:{stat}", max_abs_diff=v, tol=1e-10, passed=v <= 1e-10))
# ③a ตรง S003
fx, rx, _ = fitr(ROWS["ref_3a"], mtr, mte, EVAL)
f3 = FL3[(FL3.form == "3a")].set_index("FundCode").loc[EVAL]
for stat, arr in (("alpha", fx.alpha), ("adj_r2", fx.adj_r2), ("bic", fx.bic), ("r2_oos", rx)):
    v = float(np.nanmax(np.abs(arr - f3[stat].to_numpy())))
    span.append(dict(test="ref_vs_S003", base="3a", stat=stat, max_abs_diff=v, tol=1e-10, passed=v <= 1e-10))
# (iii) C closure
pc_, pr_ = l2.AugmentedFactors(C0, extra=E_C), l2.AugmentedFactors(C0, extra=I_all[l3.HIER_CHILDREN])
fc_, fr2_ = rg.fit_funds(R, pc_, mtr, 52, funds=EVAL), rg.fit_funds(R, pr_, mtr, 52, funds=EVAL)
d = cmp_rows(fc_, fr2_)
d["r2_oos"] = float(np.nanmax(np.abs(rg.oos_r2_funds(R, pc_, fc_, mte) - rg.oos_r2_funds(R, pr_, fr2_, mte))))
for k, v in d.items():
    span.append(dict(test="iii_Cclosure", base="C0", stat=k, max_abs_diff=v, tol=1e-8, passed=v <= 1e-8))
SPAN = save(pd.DataFrame(span), "span_test.csv")
hard = SPAN[SPAN.test != "iii_Cclosure"]
assert hard.passed.all(), "span test (i)(ii)/อ้างอิง ไม่ผ่าน: \n" + hard[~hard.passed].to_string()
log(f"span test: (i)(ii)+อ้างอิง ผ่านทั้งหมด (max {hard.max_abs_diff.max():.2e}) · (iii) max {SPAN[SPAN.test == 'iii_Cclosure'].max_abs_diff.max():.2e}")
log("เริ่ม fit แถวที่ให้คะแนน (หลัง vif_A0 · vif_elim_A · primary_A · resid_B_coef · hier_coef · placebo_C · select_C · primary_C · span test)")

# ───────────────────────── 7) fit ทุกแถว + scorecard ─────────────────────────
FITS, RO, PROV = {}, {}, {}
for rid, r in ROWS.items():
    FITS[rid], RO[rid], PROV[rid] = fitr(r, mtr, mte, EVAL)
log(f"fit รายกอง {len(ROWS)} แถว")
SUBS = {"EVAL": np.ones(len(EVAL), bool), "E67": inE67}
srows, flrows = [], []
for rid, r in ROWS.items():
    fit, ro = FITS[rid], RO[rid]
    ref = r["ref"]
    dl = l2.deltas(fit, ro, FITS[ref], RO[ref]) if ref else None
    t = fit.t_alpha_hac
    okk = fit.ok & np.isfinite(t)
    rej = np.zeros(len(EVAL), bool)
    rej[okk] = ts.bh(2 * stats.norm.sf(np.abs(t[okk])), 0.10)[0]
    for sname, sub in SUBS.items():
        d = sc.score_model(fit, ro, polE, subset=sub, div_flag=divE)
        d.insert(0, "set", sname)
        d.insert(0, "label", r["label"])
        d.insert(0, "row", rid)
        d["p_regressors_max"] = 2 * fit.K + 1
        for c_ in ("d_adj_r2", "d_r2_oos", "d_bic", "d_abs_alpha_pct"):
            d["med_" + c_] = [np.nan if dl is None else gmed(dl[c_], sub & fit.ok & FITS[ref].ok, polE, g) for g in d.policy]
        d["bh_reject"] = [int((rej & sub & (polE == g if g != "ALL" else True)).sum()) for g in d.policy]
        srows.append(d)
    x = pd.DataFrame(dict(row=rid, label=r["label"], FundCode=EVAL, policy=polE, in_E67=inE67, alpha=fit.alpha, t_alpha_hac=fit.t_alpha_hac,
                          adj_r2=fit.adj_r2, r2=fit.r2, bic=fit.bic, n_rows=fit.n, r2_oos=ro, bh_reject=rej))
    if dl is not None:
        x["d_adj_r2"], x["d_r2_oos"], x["d_bic"], x["d_abs_alpha_pct"] = dl["d_adj_r2"], dl["d_r2_oos"], dl["d_bic"], dl["d_abs_alpha_pct"]
    flrows.append(x)
SCORE = save(pd.concat(srows, ignore_index=True), "scorecard.csv")
FL = save(pd.concat(flrows, ignore_index=True), "fund_level.csv")
log("เขียน scorecard.csv + fund_level.csv")

# bias argmax (m6)
bias = []
for rid in ("ref_L2_1a", "ref_L2_1c", "R1", "R6", "R12"):
    x = FL[(FL.row == rid) & (FL.policy == "E")]
    bias.append(dict(row=rid, label=ROWS[rid]["label"], med_d_adj_r2_train=float(np.nanmedian(x.d_adj_r2)), med_d_r2_oos=float(np.nanmedian(x.d_r2_oos)),
                     med_bias=float(np.nanmedian(x.d_adj_r2 - x.d_r2_oos))))
BIAS = save(pd.DataFrame(bias), "bias_argmax.csv")

# bootstrap
nb = [rid for rid in ROWS if ROWS[rid]["ref"]]
cols, mat = [], []
for rid in nb:
    x = FL[FL.row == rid]
    for c_ in ("d_adj_r2", "d_r2_oos", "d_bic"):
        cols.append((rid, c_))
        mat.append(x[c_].to_numpy())
Sb = np.column_stack(mat)
bs = ts.bootstrap_median(Sb, polE, pairs=(), n_boot=2000, seed=SEED)
brow = []
for g in ("E", "F", "O", "ALL"):
    ci = bs[g][0]
    mg = (polE == g) if g != "ALL" else np.ones(len(EVAL), bool)
    for j, (rid, c_) in enumerate(cols):
        brow.append(dict(group=g, row=rid, label=ROWS[rid]["label"], stat="median_" + c_, median=float(np.nanmedian(Sb[mg, j])), lo=ci[0, j], hi=ci[1, j], note=CI_LABEL))
BOOT = save(pd.DataFrame(brow), "bootstrap.csv")
log("เขียน bootstrap.csv")

# ───────────────────────── 8) GRS · PY ─────────────────────────
GRS_PORTS = pd.read_csv(S003 / "grs_ports.csv")
GRS_PORTS = GRS_PORTS[GRS_PORTS.port_set == "full"].set_index("FundCode")["port"]
pcols = sorted(GRS_PORTS.unique())
PX = np.full((len(idx), len(pcols)), np.nan)
PC = np.zeros((len(idx), len(pcols)), int)
for j, p in enumerate(pcols):
    V = R[list(GRS_PORTS.index[GRS_PORTS == p])].to_numpy(float)
    PC[:, j] = np.isfinite(V).sum(axis=1)
    with np.errstate(invalid="ignore"):
        PX[:, j] = np.where(PC[:, j] > 0, np.nansum(V, axis=1) / np.maximum(PC[:, j], 1), np.nan)
PDROP = {w: (PC < 3).any(axis=1) & m for w, m in base_rows.items()}
gr = []
for rid, r in ROWS.items():
    if r["kind"] == "perfund":
        continue
    Xd = rg.lag_stack(pd.concat([r["base_df"]] + ([r["extra"]] if r["extra"] is not None else []), axis=1).to_numpy(float))
    for w, m in base_rows.items():
        use = m & ~PDROP[w] & np.isfinite(Xd).all(1) & np.isfinite(PX).all(1)
        g = ts.grs(PX[use], Xd[use])
        gr.append(dict(row=rid, label=r["label"], window=w, N_ports=len(pcols), T_used=int(use.sum()), L=g["L"], dof2=g["dof2"], F=g["F"], p=g["p"],
                       mean_abs_alpha_pct=float(np.mean(np.abs(g["alpha"])) * 5200)))
GRS = save(pd.DataFrame(gr), "grs.csv")
pyr = []
for rid, r in ROWS.items():
    prov = PROV[rid]
    for w, funds in (("test", PYTE), ("train", PYTR)):
        if prov is None:
            pyr.append(dict(row=rid, label=r["label"], window=w, role="หลัก" if w == "test" else "ภาคผนวก", J=np.nan, p=np.nan, p_boot=np.nan,
                            note="N/A — แถวต่อกองที่ K = 4 หรือ 5 (py_null_bootstrap ต้องการ K คงที่ · ห้ามแก้ lib เดิม · decisions_pre_run ข้อ 1)"))
            continue
        mk = base_rows[w] & np.isfinite(prov.design(funds[0])).all(axis=1)
        x = ts.py_null_bootstrap(R, prov, funds, mk, B=999, block=4, seed=SEED)
        x.update(row=rid, label=r["label"], window=w, role="หลัก" if w == "test" else "ภาคผนวก", m_regressors=2 * prov.K, v=x["T"] - 2 * prov.K - 1,
                 note=("(N−1)ρ̄²>1 " if x["Nrho2"] > 1 else "") + ("regressor ต่างกันรายกอง — นอกกรอบทฤษฎี (บรรยาย)" if r["kind"] == "perfund" else ""))
        pyr.append(x)
PYD = save(pd.DataFrame(pyr), "py.csv")
log("เขียน grs.csv + py.csv")

# ───────────────────────── 9) ความเสถียร · rolling ─────────────────────────
sp_stab = pol[STAB].to_numpy()
st_rows, rl_rows = [], []
fullp = fullm & (POS >= 1)
for rid, r in ROWS.items():
    h1m, h2m = window_mask(idx, "H1") & (POS >= 1), window_mask(idx, "H2")
    fh1 = fitr(r, h1m, None, STAB, 104)[0]
    fh2 = fitr(r, h2m, None, STAB, 104)[0]
    for g in ("E", "F", "O", "ALL"):
        sel = (sp_stab == g) if g != "ALL" else np.ones(len(STAB), bool)
        rr = sc.stability_halves(fh1.beta[sel], fh2.beta[sel])
        for kk, fn in enumerate(r["names"]):
            st_rows.append(dict(row=rid, label=r["label"], policy=g, factor=fn, n_funds=int(sel.sum()), r_raw=rr[kk]))
    if r["kind"] == "perfund":
        pn = {"R1": PRIM_A["1a"], "R6": PRIM_A["1c"], "R12": PRIM_C, "ref_L2_1a": PRIM_L2["1a"], "ref_L2_1c": PRIM_L2["1c"], "R3": PRIM_L2["1a"], "R8": PRIM_L2["1c"],
              "R5": PRIM_L2["1a"], "R10": PRIM_L2["1c"]}[rid]
        pj = np.array([pn[c] if c in r["per_fund"] else "" for c in STAB])
        kk = r["names"].index("PRIM")
        for j in sorted(set(pj) - {""}):
            s_ = pj == j
            if s_.sum() >= 10:
                st_rows.append(dict(row=rid, label=r["label"], policy="by_index", factor="PRIM:" + j, n_funds=int(s_.sum()),
                                    r_raw=sc.stability_halves(fh1.beta[s_][:, [kk]], fh2.beta[s_][:, [kk]])[0]))
    if r["kind"] == "perfund":
        bw, bfull, starts = l3.rolling_perfund(R, r["base_df"], r["per_fund"], STAB, fullp)
    else:
        bw, bfull, starts = l2.rolling_betas(R, PROV[rid], STAB, fullp)
    for g in ("E", "F", "O", "ALL"):
        sel = (sp_stab == g) if g != "ALL" else np.ones(len(STAB), bool)
        med, mn = sc.stability_rolling(bw[:, sel, :], bfull[sel])
        for kk, fn in enumerate(r["names"]):
            rl_rows.append(dict(row=rid, label=r["label"], policy=g, factor=fn, n_funds=int(sel.sum()), n_windows=len(starts), roll_median=med[kk], roll_min=mn[kk],
                                corr_first_last=sc._corr(bw[0][sel, kk], bw[-1][sel, kk]),
                                note=("PRIM/e ต่อกอง: ข้ามกองต่างดัชนี · " if fn == "PRIM" else "") + ("ปนความต่างของ β ระหว่าง policy — สูงเชิงกล" if g == "ALL" else "")))
STB = save(pd.DataFrame(st_rows), "stability.csv")
RLD = save(pd.DataFrame(rl_rows), "rolling_104.csv")
log("เขียน stability.csv + rolling_104.csv")

# ───────────────────────── 10) รายเดือน ─────────────────────────
midx = Rm.index
mm_tr, mm_te = np.asarray(midx <= pd.Timestamp("2023-12-31")), np.asarray(midx >= pd.Timestamp("2024-01-31"))
ntr, nte = Rm.loc[mm_tr].notna().sum(), Rm.loc[mm_te].notna().sum()
EVAL_m = [c for c in EVAL if ntr[c] >= 24 and nte[c] >= 12]
polm = pol[EVAL_m].to_numpy()
M28m = pd.DataFrame({c: Fm[c] - Fm["RF_BOT"] for c in blocks["M28"]})
L1 = fm_.build_line1(R, bal, base_f, kstar=4, seed=SEED, n_perm=500)
parts = L1["parts"]
sd_bal, sd_base = Rm.loc[mm_tr, bal].std(ddof=0).to_numpy(), Rm.loc[mm_tr, base_f].std(ddof=0).to_numpy()
mrows = []
for b in BASES:
    Lam, sdv, cols_ = {"1a": (parts["Lam_a"], sd_bal, bal), "1c": (parts["Lam_c"], sd_base, base_f)}[b]
    fmd = pd.DataFrame(factor_returns(Rm[cols_].to_numpy(float), Lam, sdv), index=midx, columns=[f"PC{i + 1}" for i in range(Lam.shape[1])])
    variants = {"base": {},
                "A-prim": {c: M28m[PRIM_A[b][c]] for c in EVAL_m if isinstance(PRIM_A[b][c], str) and PRIM_A[b][c] in M28m.columns},
                "B-prim": {c: M28m[PRIM_L2[b][c]] for c in EVAL_m if PRIM_L2[b][c] in l3.P4},
                "B-prim5": {c: M28m[PRIM_L2[b][c]] for c in EVAL_m if PRIM_L2[b][c] in l3.P4_STRICT}}
    res_m = {}
    for vn, pf in variants.items():
        if vn == "base":
            ft = rg.fit_funds(Rm, rg.CommonFactors(fmd), mm_tr, 24, L=3, funds=EVAL_m)
            ro = rg.oos_r2_funds(Rm, rg.CommonFactors(fmd), ft, mm_te)
        else:
            ft, ro, _ = l3.fit_perfund(Rm, fmd, pf, mm_tr, mm_te, EVAL_m, 24, 3)
        res_m[vn] = (ft, ro)
    for vn, (ft, ro) in res_m.items():
        okm = ft.ok & res_m["base"][0].ok
        for g in ("E", "F", "O", "ALL"):
            mrows.append(dict(base=b, variant=vn, policy=g, n=int((ft.ok & ((polm == g) if g != "ALL" else np.ones(len(polm), bool))).sum()),
                              adjr2_med=gmed(ft.adj_r2, ft.ok, polm, g), r2_oos_med=gmed(ro, ft.ok, polm, g),
                              d_r2_oos_med=(gmed(ro - res_m["base"][1], okm, polm, g) if vn != "base" else np.nan),
                              d_adj_r2_med=(gmed(ft.adj_r2 - res_m["base"][0].adj_r2, okm, polm, g) if vn != "base" else np.nan)))
MON = pd.DataFrame(mrows)
MON["note"] = "รายเดือน Dimson lag 1 เดือน · HAC L=3 · ดัชนีดิบ (span เท่ากับ e) · A-prim = ดัชนี S_A · B-prim = primary ของ L2 ใน P4 · แถวอื่น N/A (p>13)"
save(MON, "monthly.csv")
log("เขียน monthly.csv")

# ───────────────────────── 11) drop-one · Q1 · Wald · VIF ─────────────────────────
ptr = mtr & (idx <= pd.Timestamp("2022-06-24"))
pte = mtr & (idx >= pd.Timestamp("2022-07-01"))
dd_all, vif_e = [], {}
for b, f in BASES.items():
    d1 = l3.drop_one(R, f, E_B[b], mtr, mte, EVAL)
    d1.insert(0, "window", "main_train_test")
    d2 = l3.drop_one(R, f, E_B[b], ptr, pte, EVAL)
    d2.insert(0, "window", "pseudo_oos_inside_train")
    for d in (d1, d2):
        d.insert(0, "base", b)
        dd_all.append(d)
    t, _ = l3.vif_table(pd.concat([f, E_B[b]], axis=1), mtr)
    vif_e[b] = t.set_index("col").vif
DD = pd.concat(dd_all, ignore_index=True)
DD["policy"] = DD.FundCode.map(pol)
save(DD, "drop_one_B.csv")
q1 = []
for j in l3.P4:
    row = dict(index=j)
    flags = {}
    for b, f in BASES.items():
        d = DD[(DD.base == b) & (DD["index"] == j)]
        dm = d[d.window == "main_train_test"].set_index("FundCode")
        dp = d[d.window == "pseudo_oos_inside_train"].set_index("FundCode")
        prim = [c for c in EVAL if PRIM_L2[b][c] == j]
        r_ = float(np.nanmedian(dm.loc[prim, "d_r2_oos"]))
        bic_ = float(np.nanmedian(dm.loc[prim, "d_bic"]))
        vj = float(vif_e[b][j])
        Xd = pd.concat([f, E_B[b]], axis=1)
        dv = dimson_vif(Xd)
        ii = list(Xd.columns).index(j)
        vdim = float(max(dv[ii], dv[Xd.shape[1] + ii]))
        ok_ = bool(r_ >= 0.02 and bic_ <= 0 and vj < 5)
        flags[b] = ok_
        grp_n = l2.count_groups([c for c in EVAL if np.isfinite(dm.loc[c, "d_r2_oos"]) and dm.loc[c, "d_r2_oos"] >= 0.02], GMAP)
        row.update({f"n_primary_{b}": len(prim), f"med_dR2oos_primary_{b}": r_, f"med_dBIC_primary_{b}": bic_, f"vif_e_{b}": vj,
                    f"pass_{b}": ok_, f"med_dR2oos_allEVAL_{b}": float(np.nanmedian(dm.d_r2_oos)), f"n_groups_dR2oos_ge_002_{b}": grp_n,
                    f"pseudo_med_dR2oos_primary_{b}": float(np.nanmedian(dp.loc[[c for c in prim if c in dp.index], "d_r2_oos"])),
                    f"pseudo_med_dBIC_primary_{b}": float(np.nanmedian(dp.loc[[c for c in prim if c in dp.index], "d_bic"])),
                    f"vif_dimson_ge5_lag0_lt5_{b}": bool(np.isfinite(vdim) and vdim >= 5 and vj < 5)})
    row["Q1a"] = "ยังอยู่" if all(flags.values()) else ("ยังอยู่บางส่วน" if any(flags.values()) else "ไม่ผ่าน")
    row["Q1a_A_survives_both"] = bool(j in S_A["1a"] and j in S_A["1c"])
    row["in_S_A_1a"], row["in_S_A_1c"] = j in S_A["1a"], j in S_A["1c"]
    row["in_S_A_b_1a"], row["in_S_A_b_1c"] = j in S_A_b["1a"], j in S_A_b["1c"]
    row["evidence_independent"] = False
    row["note"] = "Q1a ไม่ใช่หลักฐานนอกช่วงใหม่ · pseudo-OOS = diagnostic"
    q1.append(row)
Q1 = save(pd.DataFrame(q1), "q1_verdict.csv")
log("เขียน drop_one_B.csv + q1_verdict.csv")
# Wald B + placebo ราคาถูก
wl, wsum = [], []
for b, f in BASES.items():
    w = l3.wald_B(R, f, E_B[b], mtr, EVAL)
    rej = ts.bh(w.p_adj.to_numpy(), 0.10)[0] if STEP in (1, 2) else l2.by(w.p_adj.to_numpy(), 0.10)[0]
    w["sig"] = rej
    w.insert(0, "base", b)
    wl.append(w)
    plc = {}
    for s in (26, 52):
        ws = l3.wald_B(R, f, l2.circular_shift(E_B[b], mtr, s), mtr, EVAL)
        plc[s] = ws.groupby("index").p_adj.apply(lambda x: float((x < 0.05).mean()))
    for j in l3.P4:
        g = w[w["index"] == j]
        sf = list(g.FundCode[g.sig])
        wsum.append(dict(base=b, index=j, n_funds_sig=len(sf), n_groups_sig=l2.count_groups(sf, GMAP), frac_padj05=float((g.p_adj < 0.05).mean()),
                         placebo26_frac_padj05=plc[26][j], placebo52_frac_padj05=plc[52][j],
                         note="บรรยาย · คาลิเบรตจาก single-index ของ L2 (ขั้น 2) + placebo ราคาถูก (m5)"))
save(pd.concat(wl, ignore_index=True), "wald_B.csv")
WSUM = save(pd.DataFrame(wsum), "wald_B_summary.csv")

# VIF ทุกแถว
vr = []
for rid, r in ROWS.items():
    if r["kind"] == "perfund":
        v0, v1 = [], []
        for c in EVAL:
            if c not in r["per_fund"]:
                continue
            X = pd.concat([r["base_df"], r["per_fund"][c].rename("PRIM")], axis=1)
            v0.append(vcols(X)[-1])
            v1.append(dimson_vif(X)[[X.shape[1] - 1, 2 * X.shape[1] - 1]].max())
        vr.append(dict(row=rid, label=r["label"], kind="ต่อกอง (VIF ของ PRIM กับฐาน)", n_funds=len(v0), vif_max_lag0=float(np.max(v0)), vif_median_lag0=float(np.median(v0)),
                       vif_max_dimson=float(np.max(v1)), vif_median_dimson=float(np.median(v1)), kappa=np.nan))
    else:
        X = pd.concat([r["base_df"]] + ([r["extra"]] if r["extra"] is not None else []), axis=1)
        v0 = vcols(X)
        v1 = dimson_vif(X)
        vr.append(dict(row=rid, label=r["label"], kind="factor ร่วม", n_funds=len(EVAL), vif_max_lag0=float(np.max(v0)), vif_median_lag0=float(np.median(v0)),
                       vif_max_dimson=float(np.max(v1)), vif_median_dimson=float(np.median(v1)), kappa=l3.cond_number(X, mtr)))
for b in BASES:
    X = pd.concat([BASES[b], I[S_A[b]]], axis=1)
    v0, v1 = vcols(X), dimson_vif(X)
    vr.append(dict(row=f"A1_S_A@{b}", label=f"[f, S_A] ({len(S_A[b])} ดัชนี)", kind="ชุดคัดแบบแอป (ไม่ใช่แถวคะแนน)", n_funds=np.nan, vif_max_lag0=float(np.max(v0)),
                   vif_median_lag0=float(np.median(v0)), vif_max_dimson=float(np.max(v1)), vif_median_dimson=float(np.median(v1)), kappa=l3.cond_number(X, mtr)))
VR = save(pd.DataFrame(vr), "vif_rows.csv")
log("เขียน wald_B + vif_rows.csv")

# ───────────────────────── 12) elastic net ─────────────────────────
Z = pd.concat([M28, EXT, TDEX], axis=1)
EN, ENI = [], []
for b, f in BASES.items():
    en = l3.enet_stability(R, f, Z, mtr, EVAL, n_sub=100, seed=SEED)
    en.insert(0, "base", b)
    EN.append(en)
    for j in Z.columns:
        g = en[en["index"] == j]
        prim = [c for c in EVAL if PRIM_L2[b][c] == j]
        row = dict(base=b, index=j, in_P4=j in l3.P4, in_S_A=j in S_A[b], in_blockC=j in SEL,
                   med_pi_primary=float(g.set_index("FundCode").loc[[c for c in prim if c in set(g.FundCode)], "pi"].median()) if prim else np.nan, n_primary_L2=len(prim))
        for th in (0.6, 0.8):
            sf = list(g.FundCode[g.pi >= th])
            row[f"n_funds_pi_ge_{th}"] = len(sf)
            row[f"n_groups_pi_ge_{th}"] = l2.count_groups(sf, GMAP)
        ENI.append(row)
save(pd.concat(EN, ignore_index=True), "enet_stability.csv")
ENI = save(pd.DataFrame(ENI), "enet_by_index.csv")
log("เขียน enet_stability.csv + enet_by_index.csv")

# ───────────────────────── 13) Q2 flags · Q1b ─────────────────────────
q2 = []
for rid in MAIN:
    r = ROWS[rid]
    sE = SCORE[(SCORE.row == rid) & (SCORE.set == "EVAL") & (SCORE.policy == "E")].iloc[0]
    v = VR[VR.row == rid].iloc[0]
    st = STB[(STB.row == rid) & (STB.policy == "E") & (STB.factor != "PRIM")]
    stall = STB[(STB.row == rid) & (STB.policy == "E")]
    rmed, rmin = float(st.r_raw.median()), float(st.r_raw.min())
    ref_r2 = float(SCORE[(SCORE.row == "ref_base_1a") & (SCORE.set == "EVAL") & (SCORE.policy == "E")].r2oos_med.iloc[0])
    q2.append(dict(row=rid, label=r["label"], vif_max_lag0=v.vif_max_lag0, f1_vif_lt5=bool(v.vif_max_lag0 < 5), vif_dimson_max=v.vif_max_dimson,
                   flag_dimson_ge5_lag0_lt5=bool(v.vif_max_dimson >= 5 and v.vif_max_lag0 < 5),
                   med_dR2oos_E=sE.med_d_r2_oos, f2_dR2oos_ge0=bool(sE.med_d_r2_oos >= 0), med_dBIC_E=sE.med_d_bic, f3_dBIC_le0=bool(sE.med_d_bic <= 0),
                   r_raw_median_E=rmed, r_raw_min_E=rmin, f4_r_ge06=bool(rmed >= 0.6), gap_E=sE.r2gap_med, f5_gap_le015=bool(sE.r2gap_med <= 0.15),
                   f6_named=True, r2oos_E=sE.r2oos_med, r2oos_E_below_1a=(ref_r2 - sE.r2oos_med) if rid in ("R11", "R12") else np.nan,
                   note="ไม่มีการเลือกอัตโนมัติ · PRIM/e ต่อกองนับเป็นมีชื่อ (ดัชนี)"))
Q2 = save(pd.DataFrame(q2), "q2_flags.csv")
q1b = []
for b in BASES:
    rid = ids[b][1]
    sE = SCORE[(SCORE.row == rid) & (SCORE.set == "EVAL") & (SCORE.policy == "E")].iloc[0]
    q1b.append(dict(base=b, row=rid, med_dR2oos_E=sE.med_d_r2_oos, med_dBIC_E=sE.med_d_bic, Q1b_pass=bool(sE.med_d_r2_oos >= 0.02 and sE.med_d_bic <= 0)))
Q1B = save(pd.DataFrame(q1b), "q1b_verdict.csv")

# ───────────────────────── 14) Q3 ─────────────────────────
APP = pd.read_csv(io_l1.ROOT / "cache" / "results.csv").set_index("FundCode")[["country_primary", "sector_primary"]]
q3, ct = [], []
AGG = {"MSCI_ACWI", "MSCI_WORLD", "MSCI_WORLD_EX_US", "MSCI_ACWI_EX_US", "MSCI_EM", "MSCI_ASIA_EX_JAPAN"}
srcs = {"L2(none,M28)": PRIM_NONE.reindex(EVAL), "A-prim@1a": PRIM_A["1a"], "A-prim@1c": PRIM_A["1c"], "C-prim(ETF=ไม่ตรง)": PRIM_C}
for nm, ours in srcs.items():
    ours = ours.dropna()
    ag = l3.primary_agreement(ours, APP, pol, n_perm=1000, seed=SEED)
    ag.insert(0, "grouping", "policy")
    ag.insert(0, "source", nm)
    q3.append(ag)
    isagg = pd.Series({c: ("ดัชนีรวมใน L2" if PRIM_NONE.get(c) in AGG else "ไม่ใช่ดัชนีรวม") for c in EVAL})
    ag2 = l3.primary_agreement(ours, APP, isagg, n_perm=1000, seed=SEED)
    ag2.insert(0, "grouping", "L2_primary_is_aggregate")
    ag2.insert(0, "source", nm)
    q3.append(ag2)
    m = l3.primary_match(ours, APP)
    m = m[~m.match_either]
    x = m.groupby(["ours", "app_country"]).size().reset_index(name="n").sort_values(["n", "ours"], ascending=[False, True], kind="stable").head(15)
    x.insert(0, "source", nm)
    ct.append(x)
    if nm.startswith("C-prim"):
        etf = ours.isin(l3.EXT14).mean()
        q3.append(pd.DataFrame([dict(source=nm, grouping="สัดส่วนที่ primary เป็น ETF ส่วนขยาย", group="ALL", n=len(ours), rate_either=float(etf))]))
Q3 = save(pd.concat(q3, ignore_index=True), "q3_primary_vs_app.csv")
save(pd.concat(ct, ignore_index=True), "q3_crosstab.csv")
cpm = pd.DataFrame(dict(FundCode=EVAL, l2_primary=[PRIM_L2["1a"][c] for c in EVAL], C_prim=[PRIM_C[c] for c in EVAL], policy=polE, l2_group=[PRIM_NONE.get(c) for c in EVAL]))
log("เขียน q3_primary_vs_app.csv + q3_crosstab.csv")

# ───────────────────────── 15) expectations_vs_results ─────────────────────────
exp = []


def add(i, text, fn):
    try:
        obs, met = fn()
    except Exception as e:  # noqa: BLE001
        obs, met = f"คำนวณไม่ได้: {type(e).__name__}: {e}", None
    exp.append(dict(item=i, expectation=text, observed=obs, met=met))


def sE(rid, col):
    return float(SCORE[(SCORE.row == rid) & (SCORE.set == "EVAL") & (SCORE.policy == "E")][col].iloc[0])


def e1():
    a = A0[(A0.set == "C11") & (A0.base == "1a")].groupby("window").vif.max().to_dict()
    s = A0[(A0.set == "S10") & (A0.base == "1a")].groupby("window").vif.max().to_dict()
    fv = A0[(A0.set == "f+C11+S10") & (A0.base == "1a") & (A0.window == "train")]
    n5 = int((fv.vif >= 5).sum())
    return f"C11 max VIF {a} · S10 max VIF {s} · f+C11+S10 (train, ①a) VIF≥5 = {n5} ตัว", bool(max(a.values()) < 5 and max(s.values()) >= 5 and n5 >= 5)


add("1 (A0)", "C11 ลำพัง max VIF<5 ทั้ง train และ 2021–2025 · S10 ลำพังมี ≥1 ตัว VIF≥5 · f+C11+S10 มี ≥5 ตัว VIF≥5", e1)


def e2():
    dropped = {b: VA[(VA.base == b) & (VA.phase == "main") & (VA.dropped != "")].dropped.tolist() for b in BASES}
    n = {b: len(v) for b, v in dropped.items()}
    sect = {b: [c for c in v if c in l3.S10] for b, v in dropped.items()}
    p4in = {b: sum(j in S_A[b] for j in l3.P4) for b in BASES}
    usa = all("MSCI_USA" in dropped[b] for b in BASES)
    return f"ตัด {n} · USA ถูกตัดทั้งสองฐาน={usa} · sector ที่ถูกตัด {{b: len}}={ {b: len(v) for b, v in sect.items()} } · P4 อยู่ใน S_A {p4in} · ตัด={dropped}", bool(all(4 <= v <= 10 for v in n.values()) and usa and all(len(v) >= 3 for v in sect.values()) and all(v >= 4 for v in p4in.values()))


add("2 (A1)", "ตัด 4–10 ดัชนี · USA ถูกตัดทั้งสองฐาน · sector ที่ถูกตัด ≥3 · P4 อยู่ใน S_A ≥4 ใน 6 ทั้งสองฐาน", e2)
add("3 (A-prim)", "median ΔR²_oos (E) ของ A-prim เทียบฐาน 0.010–0.030 (①a) และ ≤ L2-1 · ต่ำกว่า L2-1/L2-3 ไม่เกิน 0.01",
    lambda: (f"A-prim ①a={sE('R1', 'med_d_r2_oos'):.4f} (L2-1={sE('ref_L2_1a', 'med_d_r2_oos'):.4f}) · ①c={sE('R6', 'med_d_r2_oos'):.4f} (L2-3={sE('ref_L2_1c', 'med_d_r2_oos'):.4f})",
             bool(0.010 <= sE('R1', 'med_d_r2_oos') <= 0.030 and sE('R1', 'med_d_r2_oos') <= sE('ref_L2_1a', 'med_d_r2_oos') and sE('ref_L2_1a', 'med_d_r2_oos') - sE('R1', 'med_d_r2_oos') <= 0.01
                  and sE('ref_L2_1c', 'med_d_r2_oos') - sE('R6', 'med_d_r2_oos') <= 0.01)))
add("4 (B VIF)", "max VIF [f,e(P4)]<5 ทั้งสองฐาน (ไม่ใช้ fallback) · |corr(e_j,e_k)| train ≤0.6 · corr(e,f) test ≤0.3",
    lambda: (f"VIF max={BVIF.groupby('base').vif.max().round(3).to_dict()} · max|corr e,e| train={pd.concat(BCO).max_abs_corr_train_e_e.max():.3f} · max|corr(e,f)| test={pd.concat(BCO).max_abs_corr_test_e_f.max():.3f} · fallback={ {b: len(v) < 6 for b, v in B_USED.items()} }",
             bool(BVIF.vif.max() < 5 and pd.concat(BCO).max_abs_corr_train_e_e.max() <= 0.6 and pd.concat(BCO).max_abs_corr_test_e_f.max() <= 0.3)))
add("5 (B-all)", "B-all: median ΔR²_oos (E) −0.01…+0.02 · ΔBIC>0 → Q1b ไม่ผ่านทั้งสองฐาน · GRS/PY ไม่ปฏิเสธที่ 5% ช่วง test",
    lambda: (f"①a ΔR²_oos={sE('R2', 'med_d_r2_oos'):.4f} ΔBIC={sE('R2', 'med_d_bic'):.2f} · ①c ΔR²_oos={sE('R7', 'med_d_r2_oos'):.4f} ΔBIC={sE('R7', 'med_d_bic'):.2f} · GRS p(test) ①a={GRS[(GRS.row == 'R2') & (GRS.window == 'test')].p.iloc[0]:.3f} ①c={GRS[(GRS.row == 'R7') & (GRS.window == 'test')].p.iloc[0]:.3f} · PY p_boot ①a={PYD[(PYD.row == 'R2') & (PYD.window == 'test')].p_boot.iloc[0]:.3f} ①c={PYD[(PYD.row == 'R7') & (PYD.window == 'test')].p_boot.iloc[0]:.3f}",
             bool((~Q1B.Q1b_pass).all() and -0.01 <= sE('R2', 'med_d_r2_oos') <= 0.02 and -0.01 <= sE('R7', 'med_d_r2_oos') <= 0.02 and sE('R2', 'med_d_bic') > 0 and sE('R7', 'med_d_bic') > 0
                  and GRS[(GRS.row.isin(['R2', 'R7'])) & (GRS.window == 'test')].p.min() >= 0.05 and PYD[(PYD.row.isin(['R2', 'R7'])) & (PYD.window == 'test')].p_boot.min() >= 0.05)))
add("6 (B-prim)", "B-prim: median ΔR²_oos (E) 0.005–0.020 · ΔBIC ≤ 0",
    lambda: (f"①a ΔR²_oos={sE('R3', 'med_d_r2_oos'):.4f} ΔBIC={sE('R3', 'med_d_bic'):.3f} · ①c ΔR²_oos={sE('R8', 'med_d_r2_oos'):.4f} ΔBIC={sE('R8', 'med_d_bic'):.3f}",
             bool(all(0.005 <= sE(r_, 'med_d_r2_oos') <= 0.020 and sE(r_, 'med_d_bic') <= 0 for r_ in ('R3', 'R8')))))


def e7():
    out = {}
    ok = True
    n_pass = {}
    for b in BASES:
        crit = pd.read_csv(S005 / "criteria_P1.csv")
        for j in l3.P4:
            L2v = crit[(crit.key == f"{b}@4") & (crit["index"] == j)].med_dR2oos_used
            v = float(Q1[Q1["index"] == j][f"med_dR2oos_primary_{b}"].iloc[0])
            out[f"{b}:{j}"] = round(v - float(L2v.iloc[0]), 4) if len(L2v) else None
            ok &= bool(len(L2v) and abs(v - float(L2v.iloc[0])) <= 0.03)
        n_pass[b] = int(Q1[f"pass_{b}"].sum())
    return f"Δ(drop-one − single-index L2) = {out} · ผ่าน Q1a ต่อฐาน {n_pass} · Q1a รายดัชนี {dict(zip(Q1['index'], Q1.Q1a))}", bool(ok and all(v >= 5 for v in n_pass.values()))


add("7 (drop-one)", "median Δ_j R²_oos ในกองหลัก ภายใน ±0.03 ของ single-index L2 ทุกดัชนี · ผ่าน Q1a ทั้งสองฐาน ≥5 ใน 6", e7)
add("8 (span)", "span test (i)(ii) ≤1e-12 จริง (เกณฑ์ 1e-10) · (iii) ≤1e-9",
    lambda: (f"(i)(ii)+อ้างอิง max={hard.max_abs_diff.max():.2e} · (iii) max={SPAN[SPAN.test == 'iii_Cclosure'].max_abs_diff.max():.2e}",
             bool(hard.max_abs_diff.max() <= 1e-12 and SPAN[SPAN.test == 'iii_Cclosure'].max_abs_diff.max() <= 1e-9)))
add("9 (C placebo)", "placebo เลือก 0 ตัวทั้ง shift 26/52 → τ=0",
    lambda: (f"เลือก { {s: v['n_selected'] for s, v in PL['shifts'].items()} } · best_score_step1 { {s: round(v['best_score_step1'], 3) for s, v in PL['shifts'].items()} } · τ={TAU:.3f}", bool(TAU == 0.0 and not PL['any_selected'])))


def e10():
    r = sE("R11", "r2oos_med")
    return (f"บล็อก ({len(SEL)}): {SEL} · R²_oos E C-blk={r:.3f} (③a={sE('ref_3a', 'r2oos_med'):.3f} · ①a={sE('ref_base_1a', 'r2oos_med'):.3f}) · ΔBIC(E) เทียบ ③a={sE('R11', 'med_d_bic'):.1f}",
            bool(2 <= len(SEL) <= 5 and SEL[0] in ("MSCI_CHINA_ALL_SHARES", "MSCI_ASIA_EX_JAPAN", "MSCI_USA", "MSCI_ACWI_IT") and 0.40 <= r <= 0.55 and sE("R11", "med_d_bic") < -20))


add("10 (C-blk)", "m=2–5 · ตัวแรก ∈ {CHINA_ALL, ASIA_EX_JAPAN, USA, IT} · R²_oos E 0.40–0.55 (>③a 0.326, <①a 0.618) · ΔBIC(E) เทียบ ③a < −20", e10)


def e11():
    cd = pd.DataFrame(dict(FundCode=EVAL, j=[PRIM_C[c] for c in EVAL], g=[PRIM_NONE.get(c) for c in EVAL]))
    acwi_cd = [c for c in EVAL if PRIM_L2["1a"][c] == "MSCI_ACWI_CD"]
    theme = [c for c in acwi_cd if PRIM_C[c] in ("ARKK", "QQQ", "SOXX", "IBB", "ICLN")]
    asean = [c for c in EVAL if PRIM_L2["1a"][c] == "MSCI_ASEAN" and PRIM_C[c] == "THD"]
    return (f"ΔR²_oos C-prim เทียบ C-blk={sE('R12', 'med_d_r2_oos'):.4f} · R²_oos E={sE('R12', 'r2oos_med'):.3f} (①a {sE('ref_base_1a', 'r2oos_med'):.3f}) · กลุ่ม ACWI_CD ใน EVAL={len(acwi_cd)} กอง ที่ C-prim เป็น ETF ธีม={len(theme)} · L2 primary=ASEAN แล้ว C-prim=THD {len(asean)} กอง",
            bool(0.02 <= sE("R12", "med_d_r2_oos") <= 0.06 and sE("R12", "r2oos_med") < sE("ref_base_1a", "r2oos_med") and len(theme) >= 15 and len(asean) >= 1))


add("11 (C-prim)", "C-prim: ΔR²_oos จาก C-blk 0.02–0.06 · ต่ำกว่า ①a · ACWI_CD ที่ ETF ธีมเป็นตัวเลือก ≥15 กอง · THD เป็นตัวเลือกกอง L2 primary=ASEAN ≥1", e11)


def e12():
    g = ENI[(ENI.base == "1a") & (ENI.index.isin(ENI.index))]
    cnt = int(g[(g["index"].isin(l3.P4)) & (g["n_groups_pi_ge_0.6"] >= 7)].shape[0])
    eu = g[g["index"] == "MSCI_EUROPE"].med_pi_primary.iloc[0]
    oth = g[g["index"].isin(["MSCI_INDIA", "MSCI_VIETNAM", "MSCI_ACWI_HC"])].med_pi_primary
    etf = g[(g["index"].isin(l3.EXT14)) & (g["n_groups_pi_ge_0.6"] >= 1)]["index"].tolist()
    return f"①a: P4 ที่ π≥0.6 ใน ≥7 กลุ่ม = {cnt}/6 · med π primary Europe={eu:.3f} vs India/Vietnam/HC={oth.round(3).tolist()} · ETF ที่ถึงเกณฑ์ (≥1 กลุ่ม)={etf}", bool(cnt >= 4 and eu < oth.min() and len(etf) >= 1)


add("12 (elastic net)", "①a: ดัชนี π≥0.6 ใน ≥7 กลุ่ม ครอบ P4 ≥4 · Europe π ต่ำกว่า India/Vietnam/HC · ETF ธีม ≥1 ตัวถึงเกณฑ์", e12)


def e13():
    a = Q3[(Q3.source == "L2(none,M28)") & (Q3.grouping == "policy") & (Q3.group == "ALL")].iloc[0]
    g = Q3[(Q3.source == "L2(none,M28)") & (Q3.grouping == "L2_primary_is_aggregate")].set_index("group")
    return f"L2 ตรงแอป (country หรือ sector) {a.rate_either:.3f} (n={int(a.n)}) · baseline {a.base_either_mean:.3f} · ดัชนีรวม={g.loc['ดัชนีรวมใน L2', 'rate_either']:.3f} vs อื่น={g.loc['ไม่ใช่ดัชนีรวม', 'rate_either']:.3f}", bool(0.50 <= a.rate_either <= 0.75 and g.loc['ดัชนีรวมใน L2', 'rate_either'] > g.loc['ไม่ใช่ดัชนีรวม', 'rate_either'])


add("13 (Q3)", "ตรงแอป 50–75% · กลุ่มที่ L2 primary เป็นดัชนีรวมตรงสูงกว่ากลุ่มอื่น", e13)


def e14():
    out = {}
    for b in BASES:
        rid = ids[b][1]
        sE_ = STB[(STB.row == rid) & (STB.policy == "E")]
        out[b] = (round(float(sE_.r_raw.median()), 3), round(float(STB[(STB.row == f"ref_base_{b}") & (STB.policy == "E")].r_raw.median()), 3))
    return f"r ดิบ (E) median ข้าม factor: B-all vs ฐาน {out}", bool(all(v[0] >= 0.6 and v[0] < v[1] for v in out.values()))


add("14 (เสถียร)", "r ดิบ (E) ของ B-all ≥0.6 แต่ต่ำกว่าฐาน (0.804)", e14)


def e15():
    m = MON[(MON.policy == "E") & (MON.variant.isin(["A-prim", "B-prim"]))]
    w = {r_: sE(r_, "med_d_r2_oos") for r_ in ("R1", "R3", "R6", "R8")}
    mp = {("1a", "A-prim"): "R1", ("1a", "B-prim"): "R3", ("1c", "A-prim"): "R6", ("1c", "B-prim"): "R8"}
    cmpv = {f"{b}:{v}": (round(float(x), 4), round(w[mp[(b, v)]], 4)) for b, v, x in zip(m.base, m.variant, m.d_r2_oos_med)}
    return f"รายเดือน vs รายสัปดาห์ ΔR²_oos(E) {cmpv}", bool(all(a > c for a, c in cmpv.values()))


add("15 (รายเดือน)", "ΔR²_oos รายเดือนของ A-prim/B-prim สูงกว่ารายสัปดาห์", e15)
EXP = save(pd.DataFrame(exp), "expectations_vs_results.csv")
log("เขียน expectations_vs_results.csv")

# ───────────────────────── 16) results.md ─────────────────────────
pyview = PYD[PYD.window == "test"][["row", "label", "J", "p", "p_boot", "note"]]
sec = []
sec.append("# S006 (L3 VIF-cleaned) — ผลรัน\n\nรายงานตัวเลขอย่างเดียว · ไม่ตีความเกินตัวเลข · ระยะ 1 ไม่นับ trial\n")
sec.append("**ป้ายบังคับ:** (ก) ED ตรงกับแหล่งรอง ยังไม่เปิดต้นฉบับ Onatski 2010 [22, 47] · (ก2) PY ตรงต้นฉบับ JFEc 2024 [24] แต่คงป้าย (N−1)ρ̄²>1 + p_boot · "
           "(ข) ช่วง test 2024–2025 ถูกใช้เลือกรูปแบบตั้งแต่ L1 และตัดสิน P1(ข) ของ L2 — **ไม่ใช่หลักฐานนอกช่วงที่อิสระ** · (ค) ผลขึ้นกับค่าที่ยืนยัน 1–21 และค่าชั่วคราว 22–63 · "
           "(ง) เกณฑ์ L3 ออกแบบหลังเห็นผล L2 · (จ) แถว ⚠️ (ไม่มี Vietnam) = เกณฑ์เปลี่ยนหลังเห็นผล\n")
sec.append(f"**Q1a ไม่ใช่หลักฐานนอกช่วงใหม่:** drop-one ΔR²_oos วัดในช่วง test เดียวกับที่ P4 ถูกเลือก (`evidence_independent = False`) · pseudo-OOS ภายในช่วง train เป็น diagnostic (b̂ ของ e ประมาณจาก train เต็ม)\n")
sec.append("## 0. เงื่อนไขทางเทคนิค\n" + f"- sha256 ข้อมูล + ไฟล์ pin ตรง · lib เดิม 12 ไฟล์ตรง S005 · regression S003/S005 ทุกไฟล์ตรงทุกบิต (`regression_S003_S005.json`) · ตัวเลข n กอง: {got}\n"
           f"- span test (i)(ii)+อ้างอิง: max |Δ| = {hard.max_abs_diff.max():.2e} (เกณฑ์ 1e-10) · (iii) C closure max |Δ| = {SPAN[SPAN.test == 'iii_Cclosure'].max_abs_diff.max():.2e} (เกณฑ์ 1e-8 บรรยาย)\n")
sec.append("```\n" + SPAN.groupby(["test", "base"]).max_abs_diff.max().to_string() + "\n```\n")
sec.append("## 1. A0 — VIF / κ (บรรยาย)\n")
a0s = A0.groupby(["base", "window", "set"]).agg(n_cols=("n_cols", "first"), kappa=("kappa", "first"), vif_max=("vif", "max"), n_ge5=("vif", lambda x: int((x >= 5).sum()))).reset_index()
sec.append(md(a0s))
sec.append("## 2. A1 — ตัดแบบแอป (เกณฑ์หลัก: ดัชนีทุกตัว VIF < 5 · ชุด (ข) = เดิน log ต่อจนทุกคอลัมน์รวม f < 5)\n")
for b in BASES:
    sec.append(f"**①{b[1]}:** S_A ({len(S_A[b])}) = {S_A[b]}\n\nชุด (ข) ({len(S_A_b[b])}) = {S_A_b[b]}\n\nตัดตามลำดับ (main): " +
               ", ".join(f"{r.dropped}({r.vif_max_idx:.1f})" for r in VA[(VA.base == b) & (VA.phase == "main") & (VA.dropped != "")].itertuples()) + "\n\nหมายเหตุ STOP: " +
               "; ".join(VA[(VA.base == b) & (VA.note != "")].note.tolist()) + "\n")
sec.append("**A-mem (P4 อยู่ใน S_A):**\n\n" + md(Q1[["index", "in_S_A_1a", "in_S_A_1c", "in_S_A_b_1a", "in_S_A_b_1c", "Q1a_A_survives_both"]]) +
           f"P4′ (ไม่มี Vietnam) ใน S_A: " + str({b: sum(j in S_A[b] for j in l3.P4_STRICT) for b in BASES}) + "\n")
sec.append("## 3. B — residualize\n" + md(BVIF[["base", "col", "vif", "kappa"]]) + "\n" + md(pd.concat(BCO)[["base", "index", "r2_train", "max_abs_corr_test_e_f", "max_abs_corr_train_e_e", "max_abs_corr_test_e_e"]]) +
           "\nfallback B-all′ ใช้: " + str({b: len(v) < 6 for b, v in B_USED.items()}) + "\n")
sec.append(f"## 4. C — ลำดับชั้น\nplacebo: {json.dumps({s: v['n_selected'] for s, v in PL['shifts'].items()})} · best score รอบแรก {json.dumps({s: round(v['best_score_step1'], 3) for s, v in PL['shifts'].items()})} · τ={TAU:.4f} ({PL['rule']})\n\n"
           f"บล็อกที่เลือก: {SEL}\n\n" + md(SLOG))
sec.append("## 5. ตารางคะแนน (EVAL 207 · E / ALL) — ทุกแถว R1–R12 + อ้างอิง\n")
view = SCORE[(SCORE.set == "EVAL") & SCORE.policy.isin(["E", "F", "O", "ALL"])][["row", "label", "policy", "n", "p_regressors_max", "adjr2_med", "adjr2_iqr", "r2oos_med", "r2oos_iqr", "r2gap_med",
                                                                                "mean_abs_alpha_pct", "bic_med", "med_d_adj_r2", "med_d_r2_oos", "med_d_bic", "bh_reject"]]
order = list(ROWS)
view = view.assign(o=view.row.map({r: i for i, r in enumerate(order)})).sort_values(["o", "policy"]).drop(columns="o")
sec.append(md(view))
sec.append("### 5.1 bootstrap CI ของ median Δ (E · " + CI_LABEL + ")\n" + md(BOOT[(BOOT.group == "E")][["row", "label", "stat", "median", "lo", "hi"]]))
sec.append("### 5.2 ภาคผนวก E67 (E เท่านั้น)\n" + md(SCORE[(SCORE.set == "E67") & (SCORE.policy == "E")][["row", "label", "n", "adjr2_med", "r2oos_med", "med_d_r2_oos", "med_d_bic"]]))
sec.append("### 5.3 GRS (17 พอร์ต · แถว factor ร่วม; แถวต่อกอง = N/A)\n" + md(GRS))
sec.append("### 5.4 PY + null bootstrap (ช่วง test หลัก) \n" + md(pyview))
sec.append("### 5.5 ความเสถียร r ดิบ H1/H2 (STAB 191 · E)\n" + md(STB[STB.policy.isin(["E", "by_index"])][["row", "label", "policy", "factor", "n_funds", "r_raw"]]))
rl = RLD[RLD.policy == "E"]
sec.append("### 5.6 rolling 104 (E · เฉลี่ยข้าม factor แยกรวม/ไม่รวม PRIM · corr หน้าต่างแรกกับสุดท้ายไม่ซ้อนกัน)\n")
rls = rl.groupby(["row", "label"]).apply(lambda d: pd.Series(dict(mean_roll_median_exPRIM=d[d.factor != "PRIM"].roll_median.mean(), mean_roll_median_inclPRIM=d.roll_median.mean(),
                                                                 min_roll_min=d.roll_min.min(), mean_first_last_exPRIM=d[d.factor != "PRIM"].corr_first_last.mean(), min_first_last=d.corr_first_last.min())), include_groups=False).reset_index()
sec.append(md(rls) + "\nแถว ALL ใน `rolling_104.csv` ปนความต่างของ β ระหว่าง policy — สูงเชิงกล · PRIM/e ต่อกองข้ามกองต่างดัชนี\n")
sec.append("### 5.7 รายเดือน (E / ALL)\n" + md(MON[MON.policy.isin(["E", "ALL"])]))
sec.append("### 5.8 ความเอียงจาก argmax (m6) — median(Δadj R² train − ΔR²_oos) (E)\n" + md(BIAS))
# B-prim: ผลเฉพาะกอง P4-primary (median ของทั้ง EVAL = 0 เชิงโครงสร้างเพราะกองอื่น = ฐาน)
bp = []
for rid in ("R3", "R5", "R8", "R10", "R1", "R6"):
    x = FL[(FL.row == rid)]
    hasp = x.FundCode.isin(list(ROWS[rid]["per_fund"]))
    sub_ = x[hasp & (x.policy == "E")] if rid in ("R3", "R5", "R8", "R10") else x[x.policy == "E"]
    bp.append(dict(row=rid, label=ROWS[rid]["label"], n_funds_with_extra_E=len(sub_), med_d_adj_r2=float(np.nanmedian(sub_.d_adj_r2)), med_d_r2_oos=float(np.nanmedian(sub_.d_r2_oos)), med_d_bic=float(np.nanmedian(sub_.d_bic))))
BPS = save(pd.DataFrame(bp), "bprim_subset.csv")
sec.append("### 5.9 B-prim / B-prim5: ผลเฉพาะกอง E ที่ได้ตัวเพิ่ม (median ทั้งชุด EVAL = 0 เชิงโครงสร้าง) เทียบ A-prim (ทุกกอง E)\n" + md(BPS))
cpg = pd.DataFrame(dict(group=[PRIM_NONE.get(c) for c in EVAL], is_etf=[PRIM_C[c] in l3.EXT14 for c in EVAL], j=[PRIM_C[c] for c in EVAL]))
cpg_s = cpg.groupby("group").agg(n=("is_etf", "size"), share_etf=("is_etf", "mean"), top_choice=("j", lambda x: x.value_counts().index[0])).reset_index().sort_values("n", ascending=False).head(15)
save(cpg_s, "primary_C_by_group.csv")
sec.append("### 5.10 C-prim: สัดส่วนที่ตัวเลือกเป็น ETF ส่วนขยาย แยกตามกลุ่ม primary ของ L2 (none · M28)\n" + md(cpg_s) + f"\nสัดส่วน ETF ทั้งหมด = {cpg.is_etf.mean():.3f}\n")
en_all = pd.concat(EN)
enq = en_all.groupby(["base", "FundCode"]).apply(lambda d: int((d.pi >= 0.6).sum()), include_groups=False).groupby("base").agg(["mean", "median", "max"]).reset_index()
sec.append("### 5.11 elastic net: จำนวนดัชนี (จาก 43) ที่ π ≥ 0.6 ต่อกอง และ median π ทุกคู่\n" + md(enq) + "\nmedian π ทุกคู่ (กอง × ดัชนี): " + str(en_all.groupby("base").pi.median().round(3).to_dict()) + "\n")
sec.append("## 6. VIF / κ ทุกแถว\n" + md(VR))
sec.append("## 7. Q1 — ผล L2 ยังอยู่ไหม (Q1a ของ B คู่ Q1a-A เสมอ · **ไม่ใช่หลักฐานนอกช่วงใหม่**)\n" + md(Q1) + "\n**Q1b (ทั้งบล็อก B-all):**\n\n" + md(Q1B))
sec.append("### 7.1 Wald (b0_j, b1_j)=0 ใน B-all (บรรยาย) + placebo ราคาถูก\n" + md(WSUM))
sec.append("## 8. Q2 — ธงของชุดที่เป็นไปได้ (ไม่มีการเลือกอัตโนมัติ)\n" + md(Q2))
sec.append("## 9. Q3 — primary เทียบแอป (บรรยาย)\n" + md(Q3) + "\n" + md(pd.read_csv(OUT / "q3_crosstab.csv")))
sec.append("### 9.1 elastic net stability (บรรยาย · ไม่ใช้เลือกอะไร)\n" + md(ENI[(ENI.in_P4) | (ENI.in_blockC) | (ENI["n_groups_pi_ge_0.6"] >= 5)]))
sec.append("## 10. เทียบความคาดหมายล่วงหน้า (ข้อ 9 ของ spec)\n" + md(EXP))
sec.append("## 11. การตัดสินใจของ analyst (ดู `decisions_pre_run.md`)\n- PY/p_boot ของ R3, R5, R8, R10 = N/A (K ต่างรายกอง) · test 39 ใช้เกณฑ์ π ตัวอื่น ≤ 0.6 แทน 0.3 · Q2 ธง (4) ใช้ median ข้าม factor · เกณฑ์หยุด A1 = (ก) + (ข) เชิงบรรยาย\n"
           "## 12. ต้องให้ผู้ใช้ตัดสินใจ\nไม่มีข้อที่ analyst ต้องหยุด (ผลเลือกชุดสุดท้ายเป็นของผู้ใช้ที่ gate L3)\n")
(OUT / "results.md").write_text("\n".join(sec))
meta = dict(created=datetime.now().isoformat(timespec="seconds"), seed=SEED, data_sha256=man, pinned_sha256=pin_sha, lib_sha256=lib_hashes, regression=dict(all_pass=REGR["all_pass"]),
            versions=dict(python=platform.python_version(), numpy=np.__version__, pandas=pd.__version__, scipy=__import__("scipy").__version__,
                          sklearn=__import__("sklearn").__version__), runtime_sec=round(time.time() - T0, 1),
            S_A=S_A, S_A_b=S_A_b, B_used=B_USED, C_selected=SEL, tau=TAU, placebo_rule_step=STEP)
(OUT / "run_meta.json").write_text(json.dumps(meta, indent=1, default=str))
log(f"เสร็จ · runtime {time.time() - T0:.1f}s")
