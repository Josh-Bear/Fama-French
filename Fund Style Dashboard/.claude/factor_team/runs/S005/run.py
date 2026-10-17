"""S005 run (L2: factor x MSCI · S004 + addendum S005) — เรียก lib เท่านั้น · ใช้: python run.py [--out DIR]"""
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
import regress as rg  # noqa: E402
import samples as sp  # noqa: E402
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
S003 = io_l1.TEAM / "runs" / "S003"
CI_LABEL = "CI สุ่มกองแบบอิสระภายใน policy — กองสัมพันธ์กัน → CI แคบกว่าจริง (เหมือน L1)"
THR_N = 7


def log(msg):
    line = f"[{datetime.now().isoformat(timespec='seconds')} +{time.time() - T0:6.1f}s] {msg}"
    LOGF.write(line + "\n")
    LOGF.flush()
    print(line, flush=True)


def save(df, name, d=None, index=False):
    p = (d or OUT)
    p.mkdir(parents=True, exist_ok=True)
    df.to_csv(p / name, index=index)
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


def gmed(x, sub, pol_arr, g):
    m = sub & (pol_arr == g if g != "ALL" else True)
    x = np.asarray(x, float)[m]
    x = x[np.isfinite(x)]
    return float(np.median(x)) if len(x) else np.nan


# ───────────────────────── 0) ตรวจ sha256 ─────────────────────────
log("START run S005")
man = io_l1.verify_manifest()
PIN = {
    "runs/S003/fund_level.csv": (S003 / "fund_level.csv", "36b41161d6a13c1184a4052d9e799f660f431c2694dc57fafd747f8e695bf8cf"),
    "runs/S003/grs_ports.csv": (S003 / "grs_ports.csv", "d55011094898acdf6e0419c90a3b2713479451380cacc0bf950559c43b98ba19"),
    "runs/S003/regions.csv": (S003 / "regions.csv", "2fa3ce691c9dd66ef523e1baca228a635369d2971857797a05c105c1306e6866"),
    "runs/S003/factors_S003_weekly.parquet": (S003 / "factors_S003_weekly.parquet", l2.S003_FAC_SHA),
    "specs/S004": (io_l1.TEAM / "specs" / "S004_L2_factor_x_msci.md", "25b929d866f714246d02d7a1fa6fbea6bc341a13c63e3c660438174b5d49d20e"),
}
pin_sha = {}
for k, (p, want) in PIN.items():
    got = io_l1.sha256_file(p)
    assert got == want, f"sha256 ไม่ตรง: {k}"
    pin_sha[k] = got
lib_hashes = io_l1.lib_hash()
log("sha256 ข้อมูล 8 ไฟล์ + 5 ไฟล์ pin ตรง · lib: " + json.dumps(lib_hashes))

# ───────────────────────── 1) ข้อมูล · ชุดกอง · ดัชนี · ฐาน ─────────────────────────
R = io_l1.load_returns("W")
F = io_l1.load_factors("W")
Rm = io_l1.load_returns("M")
Fm = io_l1.load_factors("M")
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
REG8 = I[blocks["REG8"]]
IINV = I[blocks["I_inv"]]
M28S4 = I[blocks["M28"] + blocks["S4"]]
INVEST = set(blocks["I_inv"])
BLK = {"B1": REG8, "B2": M28, "B3": M28S4, "B4": I}
log(f"ชุดกอง ตรง spec: {got} · I_L2 {I.shape}")

fac_path = S003 / "factors_S003_weekly.parquet"
FR = {nm: l2.load_l1_factors(fac_path, nm) for nm in ("1a", "1b", "1c", "3b", "4a")}
L1 = {}
for k in (3, 4, 5):
    L1[k] = fm_.build_line1(R, bal, base_f, kstar=k, seed=SEED, n_perm=500)
    assert L1[k]["parts"]["em_conv"], f"EM ไม่ converge k={k}"
    log(f"build_line1 k={k}: EM iter={L1[k]['parts']['em_iter']} converged={L1[k]['parts']['em_conv']}")
for nm in ("1a", "1b", "1c"):
    assert np.nanmax(np.abs(L1[4]["forms"][nm].plain.to_numpy() - FR[nm].to_numpy())) <= 1e-12
BASES = {}
for nm in ("1a", "1b", "1c", "3b", "4a"):
    BASES[f"{nm}@4"] = FR[nm]
for k in (3, 5):
    for nm in ("1a", "1c"):
        BASES[f"{nm}@{k}"] = L1[k]["forms"][nm].plain
KOF = {key: int(key.split("@")[1]) for key in BASES}
FORM = {key: key.split("@")[0] for key in BASES}

# ───────────────────────── 2) ลำดับบังคับ: primary → fund_clusters → rotation_targets → redundancy → placebo ─────────────────────────
prim_rows, PRIM_IDX = [], {}
d0 = l2.primary_index(R, M28, mtr, EVAL, base=None)
d0.insert(0, "form", "none")
prim_rows.append(d0)
for key, fr in BASES.items():
    d = l2.primary_index(R, M28, mtr, EVAL, base=fr)
    d.insert(0, "form", key)
    prim_rows.append(d)
PRIMDF = pd.concat(prim_rows, ignore_index=True)
cp = l2.common_primary(PRIMDF[PRIMDF.form.isin([f"{n}@4" for n in ("1a", "1c", "3b", "4a", "1b")])])
PRIMDF["common_primary"] = PRIMDF.FundCode.map(cp)
save(PRIMDF, "primary_index.csv")
for key in BASES:
    d = PRIMDF[PRIMDF.form == key].set_index("FundCode")
    PRIM_IDX[key] = d["index"]
COMMON = np.array([bool(cp[c]) for c in EVAL])
log(f"เขียน primary_index.csv (ก่อน fit) · common_primary n={int(COMMON.sum())} (E/F/O = {[int((COMMON & (polE == g)).sum()) for g in 'EFO']})")

FC = l2.fund_clusters(R, mtr, EVAL, thr=0.95, min_overlap=52)
FC["policy"] = pol[FC.FundCode].to_numpy()
save(FC, "fund_clusters.csv")
GMAP = FC.set_index("FundCode").group_id.to_dict()
n_groups_total = FC.group_id.nunique()
log(f"เขียน fund_clusters.csv (ก่อน fit) · กลุ่ม {n_groups_total} จาก {len(FC)} กอง · กลุ่มใหญ่สุด {FC.group_size.max()}")

rot_t_rows, ROT = [], {}
for key, fr in BASES.items():
    if FORM[key] not in ("1a", "1b", "1c"):
        continue
    r = l2.target_rotation(fr, I, mtr, fr.shape[1], 0.25, order=list(I.columns))
    ROT[key] = r
    for m, nm in enumerate(r["names"]):
        has = m < len(r["targets"])
        rot_t_rows.append(dict(key=key, k=KOF[key], pos=m + 1, name=nm, target=r["targets"][m] if has else "",
                               score=r["scores"][m] if has else np.nan, r2_0=r["r2_0"][m] if has else np.nan,
                               investable=(r["targets"][m] in INVEST) if has else np.nan))
save(pd.DataFrame(rot_t_rows), "rotation_targets.csv")
log("เขียน rotation_targets.csv (train เท่านั้น · ก่อน fit)")

RD = []
for nm_, df_ in (("M28", M28), ("I_L2", I)):
    c = l2.index_clusters(df_, mtr, 0.10)
    c.insert(0, "set", nm_)
    c["cluster_size"] = c.groupby("cluster")["index"].transform("size")
    RD.append(c)
REDUN = pd.concat(RD, ignore_index=True)
save(REDUN, "redundancy.csv")
log("เขียน redundancy.csv (คลัสเตอร์ · train · ก่อน fit)")

# placebo
PK = ["1a@4", "1c@4", "1a@3", "1c@3", "1a@5", "1c@5"]
pl_parts, pl_sum, pl_idx = [], [], []
for key in PK:
    d = l2.placebo_scan(R, BASES[key], M28, mtr, EVAL, shifts=(26, 52))
    d.insert(0, "key", key)
    pl_parts.append(d)
    for s_, g in d.groupby("shift"):
        g = g[np.isfinite(g.p)]
        bh_p = ts.bh(g.p.to_numpy(), 0.10)[0]
        bh_a = ts.bh(g.p_adj.to_numpy(), 0.10)[0]
        pl_sum.append(dict(key=key, k=KOF[key], form=FORM[key], shift=s_, n_pairs=len(g), frac_p05=float((g.p < 0.05).mean()),
                           frac_padj05=float((g.p_adj < 0.05).mean()), n_BH_sig_p=int(bh_p.sum()), n_BH_sig_padj=int(bh_a.sum()),
                           n_funds_BHp=int(g.FundCode[bh_p].nunique()), n_funds_BHpadj=int(g.FundCode[bh_a].nunique())))
        gg = g.assign(sp=bh_p, sa=bh_a).groupby("index").agg(frac_p05=("p", lambda x: float((x < 0.05).mean())),
                                                             frac_padj05=("p_adj", lambda x: float((x < 0.05).mean())),
                                                             n_BHp=("sp", "sum"), n_BHpadj=("sa", "sum")).reset_index()
        gg.insert(0, "shift", s_)
        gg.insert(0, "key", key)
        pl_idx.append(gg)
PLS = pd.DataFrame(pl_sum)
save(pd.concat(pl_parts, ignore_index=True), "placebo_scan.csv")
save(PLS, "placebo_summary.csv")
save(pd.concat(pl_idx, ignore_index=True), "placebo_by_index.csv")
RULE = {}
for k in (3, 4, 5):
    RULE[k] = l2.placebo_rule(PLS[PLS.k == k], 0.08)
rule_json = dict(timestamp=datetime.now().isoformat(timespec="seconds"), main_k=4, **RULE[4],
                 per_k={str(k): RULE[k] for k in (3, 4, 5)}, thr=0.08,
                 step_meaning={"1": "p(chi2)+BH", "2": "p_adj+BH", "3": "p_adj+BY"})
json.dump(rule_json, open(OUT / "placebo_rule.json", "w"), ensure_ascii=False, indent=1)
STEP4 = RULE[4]["step"]
log(f"เขียน placebo_scan/summary + placebo_rule.json (ก่อนสแกนจริง): k=4 R0={RULE[4]['R0']:.4f} R1={RULE[4]['R1']:.4f} → ขั้น {STEP4} · "
    f"k=3 ขั้น {RULE[3]['step']} · k=5 ขั้น {RULE[5]['step']}")

# ───────────────────────── 3) ตัวช่วยกลุ่ม (k) ─────────────────────────
POOL_BASE = {c: i for i, c in enumerate(EVAL)}
base_rows = {"train": mtr & (POS >= 1), "test": mte & (POS >= 1)}
GRS_PORTS = pd.read_csv(S003 / "grs_ports.csv")
GRS_PORTS = GRS_PORTS[GRS_PORTS.port_set == "full"].set_index("FundCode")["port"]


def port_returns(ports):
    cols = sorted(ports.unique())
    X = np.full((len(idx), len(cols)), np.nan)
    C = np.zeros((len(idx), len(cols)), int)
    for j, p in enumerate(cols):
        mem = list(ports.index[ports == p])
        V = R[mem].to_numpy(float)
        C[:, j] = np.isfinite(V).sum(axis=1)
        with np.errstate(invalid="ignore"):
            X[:, j] = np.where(C[:, j] > 0, np.nansum(V, axis=1) / np.maximum(C[:, j], 1), np.nan)
    return cols, X, C


PCOLS, PX, PC = port_returns(GRS_PORTS)
PDROP = {w: (PC < 3).any(axis=1) & m for w, m in base_rows.items()}


def run_grs(Xdes, window):
    m = base_rows[window]
    bad = PDROP[window]
    use = m & ~bad & np.isfinite(Xdes).all(1) & np.isfinite(PX).all(1)
    g = ts.grs(PX[use], Xdes[use])
    return dict(window=window, N_ports=len(PCOLS), T_used=int(use.sum()), L=g["L"], dof2=g["dof2"], F=g["F"], p=g["p"],
                mean_abs_alpha_pct=float(np.mean(np.abs(g["alpha"])) * 5200))


def sig_flags(scan, step):
    """significant ตามขั้น · scan: ตาราง long ของ key เดียว (p finite)"""
    ok = np.isfinite(scan.p.to_numpy())
    out = np.zeros(len(scan), bool)
    pv = scan.p.to_numpy()[ok] if step == 1 else scan.p_adj.to_numpy()[ok]
    rej = (ts.bh(pv, 0.10)[0] if step in (1, 2) else l2.by(pv, 0.10)[0])
    out[ok] = rej
    return out


def lab_space(v):
    return "อยู่ในปริภูมิโดยประมาณ" if v >= 0.80 else ("บางส่วน" if v >= 0.50 else "นอกปริภูมิ")


def lab_corr(v):
    return "≈" if v >= 0.7 else ("คล้าย" if v >= 0.5 else "ไม่มีชื่อ")


ALL_OUT = {}


def process_group(k, keys, outdir, comparators):
    """รันทุกอย่างของชุดฐาน keys (ที่ k) → เขียนไฟล์ใน outdir · คืน dict ตารางสำคัญ"""
    t_g = time.time()
    res = {}
    FITS, RO, MOD = {}, {}, {}  # name → fit · r2oos · meta
    # --- โมเดล ---
    for key in keys:
        fr = BASES[key]
        f = FORM[key]
        MOD[f"base[{key}]"] = dict(key=key, kind="base", provider=rg.CommonFactors(fr), L2=f"ฐาน {f}")
        pf = {c: M28[PRIM_IDX[key][c]] for c in EVAL}
        MOD[f"prim[{key}]"] = dict(key=key, kind="prim", provider=l2.AugmentedFactors(fr, per_fund=pf))
        if f in ("1a", "1c"):
            MOD[f"reg8[{key}]"] = dict(key=key, kind="reg8", provider=l2.AugmentedFactors(fr, extra=REG8))
    code_of = {}
    suffix = "" if k == 4 else f"k{k}"
    for key in keys:
        f = FORM[key]
        n_prim = {"1a": "L2-1", "1c": "L2-3", "3b": "L2-5", "4a": "L2-6", "1b": "L2-7"}[f]
        MOD[f"prim[{key}]"]["L2"] = n_prim + suffix
        if f in ("1a", "1c"):
            MOD[f"reg8[{key}]"]["L2"] = {"1a": "L2-2", "1c": "L2-4"}[f] + suffix
    for nm, m in MOD.items():
        FITS[nm] = rg.fit_funds(R, m["provider"], mtr, 52, funds=EVAL)
        RO[nm] = rg.oos_r2_funds(R, m["provider"], FITS[nm], mte)
    base_of = {nm: f"base[{m['key']}]" for nm, m in MOD.items()}
    log(f"[k={k}] fit รายกอง {len(MOD)} โมเดล")
    # --- scorecard + fund_level ---
    SUBS = {"EVAL": np.ones(len(EVAL), bool), "E67": inE67, "COMMON_PRIM": COMMON}
    srows, flrows, bhrows = [], [], []
    for nm, m in MOD.items():
        fit, ro = FITS[nm], RO[nm]
        bnm = base_of[nm]
        dl = l2.deltas(fit, ro, FITS[bnm], RO[bnm])
        t = fit.t_alpha_hac
        okk = fit.ok & np.isfinite(t)
        rej = np.zeros(len(EVAL), bool)
        rej[okk] = ts.bh(2 * stats.norm.sf(np.abs(t[okk])), 0.10)[0]
        for sname, sub in SUBS.items():
            d = sc.score_model(fit, ro, polE, subset=sub, div_flag=divE)
            d.insert(0, "set", sname)
            d.insert(0, "model", m["L2"])
            d.insert(0, "kind", m["kind"])
            d.insert(0, "key", m["key"])
            d["k"] = KOF[m["key"]]
            d["p_regressors"] = 2 * fit.K + 1
            for c_ in ("d_adj_r2", "d_r2_oos", "d_bic", "d_abs_alpha_pct"):
                d["med_" + c_] = [np.nan if m["kind"] == "base" else gmed(dl[c_], sub & fit.ok & FITS[bnm].ok, polE, g) for g in d.policy]
            d["bh_reject"] = [int((rej & sub & (polE == g if g != "ALL" else True)).sum()) for g in d.policy]
            srows.append(d)
        flrows.append(pd.DataFrame(dict(
            model=m["L2"], key=m["key"], k=KOF[m["key"]], kind=m["kind"], FundCode=EVAL, policy=polE, in_E67=inE67, common_primary=COMMON,
            primary_index=PRIM_IDX[m["key"]][EVAL].to_numpy(), alpha=fit.alpha, t_alpha_hac=fit.t_alpha_hac, adj_r2=fit.adj_r2, r2=fit.r2,
            bic=fit.bic, n_rows=fit.n, r2_oos=ro, d_adj_r2=dl["d_adj_r2"], d_r2_oos=dl["d_r2_oos"], d_bic=dl["d_bic"],
            d_abs_alpha_pct=dl["d_abs_alpha_pct"], bh_reject=rej)))
    SCORE = pd.concat(srows, ignore_index=True)
    FL = pd.concat(flrows, ignore_index=True)
    # test 16 ภายในการรัน: Δ = aug − base ที่ k เดียวกัน
    chk = FL[FL.kind != "base"].merge(FL[FL.kind == "base"][["key", "FundCode", "adj_r2", "r2_oos"]], on=["key", "FundCode"], suffixes=("", "_b"))
    assert np.allclose(chk.d_adj_r2.fillna(0), (chk.adj_r2 - chk.adj_r2_b).fillna(0), atol=1e-12)
    assert np.allclose(chk.d_r2_oos.fillna(0), (chk.r2_oos - chk.r2_oos_b).fillna(0), atol=1e-12)
    save(SCORE, "scorecard.csv", outdir)
    save(FL, "fund_level.csv", outdir)
    res["score"], res["fl"] = SCORE, FL
    # --- bootstrap CI ---
    nb_models = [nm for nm, m in MOD.items() if m["kind"] != "base"]
    cols = []
    mat = []
    for nm in nb_models:
        sub_fl = FL[FL.model == MOD[nm]["L2"]]
        for c_ in ("d_adj_r2", "d_r2_oos", "d_bic"):
            cols.append((MOD[nm]["L2"], c_))
            mat.append(sub_fl[c_].to_numpy())
    S_ = np.column_stack(mat)
    bs = ts.bootstrap_median(S_, polE, pairs=(), n_boot=2000, seed=SEED)
    brow = []
    for g in ("E", "F", "O", "ALL"):
        ci = bs[g][0]
        mg = (polE == g) if g != "ALL" else np.ones(len(EVAL), bool)
        for j, (mn, c_) in enumerate(cols):
            brow.append(dict(group=g, model=mn, stat="median_" + c_, median=float(np.nanmedian(S_[mg, j])), lo=ci[0, j], hi=ci[1, j], note=CI_LABEL))
    BOOT = pd.DataFrame(brow)
    save(BOOT, "bootstrap.csv", outdir)
    res["boot"] = BOOT
    # --- สแกนดัชนีเดี่ยว ---
    scans, byrows = [], []
    for key in keys:
        fr = BASES[key]
        sc_ = l2.incremental_scan(R, fr, M28, mtr, mte, EVAL)
        sc_.insert(0, "key", key)
        sc_.insert(1, "k", KOF[key])
        nd = {c: l2.near_dup_r2(fr, M28[c], mtr) for c in M28.columns}
        sc_["near_dup_r2"] = sc_["index"].map(nd)
        sc_["near_dup"] = sc_["near_dup_r2"] >= 0.99
        ok = np.isfinite(sc_.p.to_numpy())
        for nm_, col, fn in (("BH_p", "p", ts.bh), ("BH_padj", "p_adj", ts.bh), ("BY_p", "p", l2.by), ("BY_padj", "p_adj", l2.by)):
            v = np.zeros(len(sc_), bool)
            v[ok] = fn(sc_[col].to_numpy()[ok], 0.10)[0]
            sc_[nm_] = v
        for nm_, col in (("BH_p_perindex", "p"), ("BH_padj_perindex", "p_adj")):
            v = np.zeros(len(sc_), bool)
            for _, gi in sc_[ok].groupby("index").groups.items():
                pos = sc_.index.get_indexer(gi)
                v[pos] = ts.bh(sc_[col].to_numpy()[pos], 0.10)[0]
            sc_[nm_] = v
        step_k = RULE[k]["step"]
        sc_["sig_chosen"] = sig_flags(sc_, STEP4)
        sc_["sig_stepk"] = sig_flags(sc_, step_k)
        sc_["sig_BYsame_p"] = sc_["BY_p"] if STEP4 == 1 else sc_["BY_padj"]
        sc_["common_primary"] = sc_.FundCode.map(cp)
        scans.append(sc_)
        # scan_by_index
        prim_map = PRIM_IDX[key]
        for j, g in sc_.groupby("index"):
            fund_prim = [c for c in EVAL if prim_map[c] == j]
            row = dict(key=key, k=KOF[key], index=j, defn_dup=bool(g.defn_dup.iloc[0]), near_dup_r2=g.near_dup_r2.iloc[0], near_dup=bool(g.near_dup.iloc[0]))
            for tag, col in (("", "sig_chosen"), ("_stepk", "sig_stepk"), ("_BYsame", "sig_BYsame_p")):
                sf = g.FundCode[g[col]]
                row["n_funds_sig" + tag] = len(sf)
                row["n_groups_sig" + tag] = l2.count_groups(sf, GMAP)
                if tag == "":
                    for pg in "EFO":
                        row["n_funds_sig_" + pg] = int((pol[sf] == pg).sum())
            for c_ in ("BH_p", "BH_padj", "BY_p", "BY_padj", "BH_p_perindex", "BH_padj_perindex"):
                row["n_" + c_] = int(g[c_].sum())
            row["n_primary"] = len(fund_prim)
            row["n_groups_exposed"] = l2.count_groups(fund_prim, GMAP) if fund_prim else 0
            gi_ = g.set_index("FundCode")
            row["med_d_r2_oos_all"] = float(np.nanmedian(g.d_r2_oos)) if np.isfinite(g.d_r2_oos).any() else np.nan
            row["med_d_r2_oos_primary"] = float(np.nanmedian(gi_.loc[fund_prim, "d_r2_oos"])) if fund_prim else np.nan
            sfl = list(g.FundCode[g.sig_chosen])
            row["med_d_r2_oos_sigfunds"] = float(np.nanmedian(gi_.loc[sfl, "d_r2_oos"])) if sfl else np.nan
            byrows.append(row)
    SCAN = pd.concat(scans, ignore_index=True)
    BYI = pd.DataFrame(byrows)
    save(SCAN, "scan_single.csv", outdir)
    save(BYI, "scan_by_index.csv", outdir)
    res["scan"], res["byi"] = SCAN, BYI
    # P1
    p1 = []
    for _, r in BYI.iterrows():
        if r.defn_dup:
            p1.append(dict(key=r.key, index=r["index"], P1a=False, P1b=False, P1=False, label="ซ้ำเชิงนิยาม"))
            continue
        a = bool(r.n_groups_sig >= THR_N and r.n_funds_sig >= THR_N)
        small = r.n_primary < 5
        medv = r.med_d_r2_oos_sigfunds if small else r.med_d_r2_oos_primary
        b = bool(np.isfinite(medv) and medv >= 0.02)
        lab = []
        if r.n_funds_sig >= THR_N and r.n_groups_sig < THR_N:
            lab.append("กระจุกในกลุ่มกองเกือบซ้ำ")
        if small:
            lab.append("n เล็ก")
        if STEP4 in (1, 2) and a and not (r.n_groups_sig_BYsame >= THR_N and r.n_funds_sig_BYsame >= THR_N):
            lab.append("ไวต่อ dependence")
        if r.near_dup:
            lab.append("เกือบซ้ำเชิงนิยาม")
        p1.append(dict(key=r.key, index=r["index"], P1a=a, P1b=b, P1=a and b, n_groups_sig=r.n_groups_sig, n_funds_sig=r.n_funds_sig,
                       n_primary=r.n_primary, med_dR2oos_used=medv, label=";".join(lab)))
    P1 = pd.DataFrame(p1)
    res["P1"] = P1
    log(f"[k={k}] สแกนดัชนีเดี่ยว + P1 เสร็จ · ผ่าน P1: " + json.dumps({key: list(P1[(P1.key == key) & P1.P1]["index"]) for key in keys}, ensure_ascii=False))
    # --- spanning ไปข้างหน้า ---
    sf_rows, sw_rows = [], []
    for key in keys:
        fr = BASES[key]
        t = l2.forward_span(fr, BLK, mtr, mte)
        t.loc[t.block == "B4", ["alpha_pct_yr", "t_alpha"]] = np.nan
        t.insert(0, "key", key)
        t["alpha_role"] = t.block.map({"B1": "ทดสอบ(BH)", "B2": "บรรยาย", "B3": "บรรยาย", "B4": "ไม่รายงาน"})
        sf_rows.append(t)
        d1 = t[(t.block == "B1") & ~t.defn]["factor"].tolist()
        if d1:
            w = ts.spanning(fr[d1], REG8, mtr)
            sw_rows.append(dict(key=key, n_factors=len(d1), factors=",".join(d1), n=w["n"], wald=w["wald"], p=w["p"], df=w["df"],
                                note="HAC Wald asymptotic ไม่ใช่ exact F" + (" · ตัด factor เชิงนิยาม" if len(d1) < fr.shape[1] else "")))
    SFW = pd.concat(sf_rows, ignore_index=True)
    fam = SFW.bh_family.to_numpy()
    SFW["p_alpha"] = 2 * stats.norm.sf(np.abs(SFW.t_alpha.fillna(0)))
    SFW["bh_reject"] = False
    SFW["bh_adj"] = np.nan
    if fam.sum():
        rj, adj = ts.bh(SFW.loc[fam, "p_alpha"].to_numpy(), 0.10)
        SFW.loc[fam, "bh_reject"] = rj
        SFW.loc[fam, "bh_adj"] = adj
    SWD = pd.DataFrame(sw_rows)
    if len(SWD):
        SWD["p_holm"] = l2.holm(SWD.p.to_numpy())
    save(SFW, "span_forward.csv", outdir)
    save(SWD, "span_forward_wald.csv", outdir)
    res["sf"], res["sw"] = SFW, SWD
    # --- spanning ย้อนกลับ + canonical ---
    rv_rows, cn_rows = [], []
    for key in keys:
        fr = BASES[key]
        a1 = l2.reverse_span(I, fr, mtr, mte, lead=1)
        a0 = l2.reverse_span(I, fr, mtr, mte, lead=0)
        d = pd.DataFrame(dict(key=key, k=KOF[key], index=a1.index, r2_rev=a1.r2.to_numpy(), adj_r2_rev=a1.adj_r2.to_numpy(),
                              r2_rev_oos=a1.r2_oos.to_numpy(), n_tr=a1.n_tr.to_numpy(), n_te=a1.n_te.to_numpy(),
                              r2_rev_nolead=a0.r2.to_numpy(), adj_r2_rev_nolead=a0.adj_r2.to_numpy(), r2_rev_nolead_oos=a0.r2_oos.to_numpy()))
        d["label"] = [lab_space(v) for v in d.adj_r2_rev]
        d["investable"] = d["index"].isin(INVEST)
        rv_rows.append(d)
        for tn, tdf in (("M28", M28), ("I_inv", IINV)):
            c = l2.canon_oos(fr, tdf, mtr, mte)
            c.insert(0, "target", tn)
            c.insert(0, "key", key)
            c["label_oos"] = ["จับ" if v >= 0.8 else ("จับบางส่วน" if v >= 0.5 else "ไม่จับ") for v in c.rho_oos]
            c["note"] = "ρ_oos หดเชิงกล (p/n = 28/155 หรือ 34/155) · ป้าย (ข)"
            cn_rows.append(c)
    RV = pd.concat(rv_rows, ignore_index=True)
    CN = pd.concat(cn_rows, ignore_index=True)
    save(RV, "span_reverse.csv", outdir)
    save(CN, "canon.csv", outdir)
    res["rv"], res["cn"] = RV, CN
    # --- การหมุน ---
    rot_rows = []
    for key in keys:
        if key not in ROT:
            continue
        r = ROT[key]
        fr = r["f_rot"]
        for m, nm in enumerate(r["names"]):
            has = m < len(r["targets"])
            ctr = cte = np.nan
            if has:
                tg = r["targets"][m]
                ctr = float(pd.concat([fr.iloc[:, m], I[tg]], axis=1)[mtr].corr().iloc[0, 1])
                cte = float(pd.concat([fr.iloc[:, m], I[tg]], axis=1)[mte].corr().iloc[0, 1])
            rot_rows.append(dict(key=key, k=KOF[key], pos=m + 1, name=nm, target=r["targets"][m] if has else "", score=r["scores"][m] if has else np.nan,
                                 corr_train=ctr, corr_test=cte, label_train=lab_corr(ctr) if has else "R-ไม่มีเป้า",
                                 label_test=lab_corr(cte) if has else "R-ไม่มีเป้า", investable=(r["targets"][m] in INVEST) if has else np.nan,
                                 note_uninvestable=("เป้าลงทุนไม่ได้ — ชื่อเชิงบรรยาย" if has and r["targets"][m] not in INVEST else ""),
                                 P2=bool(has and ctr >= 0.7 and cte >= 0.6)))
            if key in ROT:
                pass
    ROTD = pd.DataFrame(rot_rows)
    save(ROTD, "rotation.csv", outdir)
    Bm = [pd.DataFrame(ROT[key]["B"], columns=ROT[key]["names"]).assign(key=key) for key in keys if key in ROT]
    save(pd.concat(Bm, ignore_index=True), "rotation_B.csv", outdir)
    res["rot"] = ROTD
    # --- GRS (L2-2/4) ---
    gr = []
    for nm, m in MOD.items():
        if m["kind"] != "reg8":
            continue
        Xd = rg.lag_stack(np.column_stack([BASES[m["key"]].to_numpy(float), REG8.to_numpy(float)]))
        for w in ("train", "test"):
            r = run_grs(Xd, w)
            r.update(model=m["L2"], key=m["key"], k=KOF[m["key"]])
            gr.append(r)
    GRS = pd.DataFrame(gr)
    save(GRS, "grs.csv", outdir)
    res["grs"] = GRS
    # --- PY + null bootstrap ---
    pyr = []
    for nm, m in MOD.items():
        for w, funds in (("test", PYTE), ("train", PYTR)):
            prov = m["provider"]
            mk = base_rows[w] & np.isfinite(prov.design(funds[0])).all(axis=1)
            r = ts.py_null_bootstrap(R, prov, funds, mk, B=999, block=4, seed=SEED)
            r.update(model=m["L2"], key=m["key"], k=KOF[m["key"]], window=w, kind=m["kind"], m_regressors=2 * prov.K, v=r["T"] - 2 * prov.K - 1,
                     role="หลัก" if w == "test" else "ภาคผนวก",
                     note=("(N−1)ρ̄²>1 " if r["Nrho2"] > 1 else "") + ("regressor ต่างกันรายกอง — นอกกรอบทฤษฎี (บรรยาย)" if m["kind"] == "prim" else ""))
            pyr.append(r)
    PYD = pd.DataFrame(pyr)
    save(PYD, "py.csv", outdir)
    res["py"] = PYD
    log(f"[k={k}] GRS + PY null bootstrap เสร็จ")
    # --- ความเสถียร (STAB) ---
    st_rows = []
    sp_stab = pol[STAB].to_numpy()
    for nm, m in MOD.items():
        prov = m["provider"]
        fh1 = rg.fit_funds(R, prov, window_mask(idx, "H1") & (POS >= 1), 104, funds=STAB)
        fh2 = rg.fit_funds(R, prov, window_mask(idx, "H2"), 104, funds=STAB)
        Kc = prov.K
        for g in ("E", "F", "O", "ALL"):
            sel = (sp_stab == g) if g != "ALL" else np.ones(len(STAB), bool)
            r = sc.stability_halves(fh1.beta[sel], fh2.beta[sel])
            for kk, fn in enumerate(prov.names):
                if fn == "PRIM":
                    continue
                st_rows.append(dict(model=m["L2"], key=m["key"], kind=m["kind"], policy=g, factor=fn, n_funds=int(sel.sum()), r_raw=r[kk]))
        if m["kind"] == "prim":
            kk = prov.names.index("PRIM")
            pj = PRIM_IDX[m["key"]][STAB].to_numpy()
            for j in sorted(set(pj)):
                s_ = pj == j
                if s_.sum() >= 10:
                    r = sc.stability_halves(fh1.beta[s_][:, [kk]], fh2.beta[s_][:, [kk]])[0]
                    st_rows.append(dict(model=m["L2"], key=m["key"], kind="prim", policy="by_index", factor="PRIM:" + j, n_funds=int(s_.sum()), r_raw=r))
    STB = pd.DataFrame(st_rows)
    save(STB, "stability.csv", outdir)
    res["stab"] = STB
    # --- rolling 104 สัปดาห์ (ภาคผนวกข้อ 5 · STAB · เหมือนวิธี S003: เริ่มทุก 4 สัปดาห์ · เทียบ β เต็มช่วง) ---
    fullm = window_mask(idx, "full") & (POS >= 1)
    rl_rows = []
    for nm, m in MOD.items():
        bw, bfull, starts = l2.rolling_betas(R, m["provider"], STAB, fullm)
        for g in ("E", "F", "O", "ALL"):
            sel = (sp_stab == g) if g != "ALL" else np.ones(len(STAB), bool)
            med, mn = sc.stability_rolling(bw[:, sel, :], bfull[sel])
            for kk, fn in enumerate(m["provider"].names):
                rl_rows.append(dict(model=m["L2"], key=m["key"], kind=m["kind"], policy=g, factor=fn, n_funds=int(sel.sum()), n_windows=len(starts),
                                    roll_median=med[kk], roll_min=mn[kk],
                                    note="PRIM: ข้ามกองต่างดัชนี (ปนความต่างของดัชนี)" if fn == "PRIM" else ""))
    RLD = pd.DataFrame(rl_rows)
    save(RLD, "rolling_104.csv", outdir)
    res["roll"] = RLD
    # --- รายเดือน ---
    midx = Rm.index
    mm_tr = np.asarray(midx <= pd.Timestamp("2023-12-31"))
    mm_te = np.asarray(midx >= pd.Timestamp("2024-01-31"))
    ntr, nte = Rm.loc[mm_tr].notna().sum(), Rm.loc[mm_te].notna().sum()
    EVAL_m = [c for c in EVAL if ntr[c] >= 24 and nte[c] >= 12]
    polm = pol[EVAL_m].to_numpy()
    M28m = pd.DataFrame({c: Fm[c] - Fm["RF_BOT"] for c in blocks["M28"]})
    parts = L1[k]["parts"]
    sd_bal = Rm.loc[mm_tr, bal].std(ddof=0).to_numpy()
    sd_base = Rm.loc[mm_tr, base_f].std(ddof=0).to_numpy()
    mrows = []
    scan_m = None
    for key in keys:
        f = FORM[key]
        if f not in ("1a", "1b", "1c"):
            continue
        Lam, sdv, cols_ = {"1a": (parts["Lam_a"], sd_bal, bal), "1b": (parts["Lam_b"], None, bal), "1c": (parts["Lam_c"], sd_base, base_f)}[f]
        fm_df = pd.DataFrame(factor_returns(Rm[cols_].to_numpy(float), Lam, sdv), index=midx, columns=[f"PC{i + 1}" for i in range(Lam.shape[1])])
        pfm = {c: M28m[PRIM_IDX[key][c]] for c in EVAL_m}
        provs = {"base": rg.CommonFactors(fm_df), "prim": l2.AugmentedFactors(fm_df, per_fund=pfm)}
        fits_m = {}
        for kind, pv in provs.items():
            ft = rg.fit_funds(Rm, pv, mm_tr, 24, L=3, funds=EVAL_m)
            fits_m[kind] = (ft, rg.oos_r2_funds(Rm, pv, ft, mm_te))
        okm = fits_m["base"][0].ok & fits_m["prim"][0].ok
        for g in ("E", "F", "O", "ALL"):
            s_ = (polm == g) if g != "ALL" else np.ones(len(EVAL_m), bool)
            for kind, (ft, ro) in fits_m.items():
                mrows.append(dict(key=key, k=KOF[key], kind=kind, row="fit", policy=g, n=int((s_ & ft.ok).sum()), p=2 * ((fm_df.shape[1]) + (kind == "prim")) + 1,
                                  adjr2_med=gmed(ft.adj_r2, ft.ok, polm, g), r2_oos_med=gmed(ro, ft.ok, polm, g),
                                  d_r2_oos_med=(gmed(ro - fits_m["base"][1], okm, polm, g) if kind == "prim" else np.nan),
                                  d_adj_r2_med=(gmed(ft.adj_r2 - fits_m["base"][0].adj_r2, okm, polm, g) if kind == "prim" else np.nan)))
        if f == "1a":
            sm = l2.incremental_scan(Rm, fm_df, M28m, mm_tr, mm_te, EVAL_m, L=3, min_rows=24)
            okp = np.isfinite(sm.p.to_numpy())
            rj = np.zeros(len(sm), bool)
            rj[okp] = ts.bh(sm.p.to_numpy()[okp], 0.10)[0]
            mrows.append(dict(key=key, k=KOF[key], kind="scan_single_BH_p", row="scan", policy="ALL", n=int(okp.sum()), p=np.nan,
                              adjr2_med=np.nan, r2_oos_med=np.nan, d_r2_oos_med=float(np.nanmedian(sm.d_r2_oos)), d_adj_r2_med=float(np.nanmedian(sm.d_adj_r2)),
                              n_BH_sig=int(rj.sum()), frac_BH_sig=float(rj.mean())))
    MON = pd.DataFrame(mrows)
    MON["note"] = "รายเดือน Dimson lag 1 เดือน · HAC L=3 · primary index ตามป้ายรายสัปดาห์ · L2-2/4/5/6 = N/A (p>17 กับ ~35 แถว)"
    save(MON, "monthly.csv", outdir)
    res["mon"] = MON
    # --- P2 / P3 / P4 ---
    rv = RV
    P3 = []
    cl = REDUN[REDUN.set == "M28"].set_index("index")
    ra = RV[RV.key == f"1a@{k}"].set_index("index")
    rep = {}
    for c_, g in REDUN[REDUN.set == "M28"].groupby("cluster"):
        rep[c_] = ra.loc[g["index"], "adj_r2_rev"].idxmax()
    for key in [kk for kk in keys if FORM[kk] in ("1a", "1c")]:
        pk = P1[P1.key == key].set_index("index")
        rk = RV[RV.key == key].set_index("index")
        for j in I.columns:
            adj, oos = rk.loc[j, "adj_r2_rev"], rk.loc[j, "r2_rev_oos"]
            p1ok = bool(pk.loc[j, "P1"]) if j in pk.index else False
            lab = []
            if adj >= 0.80 and oos >= 0.70 and not p1ok:
                lab.append("ซ้ำกับ factor")
            if j in cl.index:
                r2o, vf, cc = cl.loc[j, "r2_on_others"], cl.loc[j, "vif"], cl.loc[j, "cluster"]
                if r2o >= 0.90 or vf >= 10 or (cl[cl.cluster == cc].shape[0] > 1 and rep[cc] != j):
                    lab.append("ซ้ำกับดัชนีอื่น")
            if adj < 0.50 and not p1ok:
                lab.append("ไม่เกี่ยว")
            P3.append(dict(key=key, index=j, adj_r2_rev=adj, r2_rev_oos=oos, P1=p1ok, P3=";".join(lab)))
    P3 = pd.DataFrame(P3)
    save(P3, "criteria_P3.csv", outdir)
    save(P1, "criteria_P1.csv", outdir)
    pa, pc = f"1a@{k}", f"1c@{k}"
    both = sorted(set(P1[(P1.key == pa) & P1.P1]["index"]) & set(P1[(P1.key == pc) & P1.P1]["index"]))
    reg8 = {}
    for key in (pa, pc):
        sub_ = SCORE[(SCORE.key == key) & (SCORE.kind == "reg8") & (SCORE.set == "EVAL") & (SCORE.policy == "E")]
        reg8[key] = dict(dR2oos_E=float(sub_.med_d_r2_oos.iloc[0]), dBIC_E=float(sub_.med_d_bic.iloc[0]),
                         worth=bool(sub_.med_d_r2_oos.iloc[0] >= 0.02 and sub_.med_d_bic.iloc[0] <= 0))
    P4 = dict(k=k, pass_both=both, REG8=reg8, near_dup_labels={j: bool(SCAN[(SCAN.key == pa) & (SCAN["index"] == j)].near_dup.iloc[0]) for j in both},
              verdict=("MSCI ไม่เพิ่มคำอธิบายเหนือ factor ของ L1 อย่างมีนัย" if not both else "ส่งต่อ L3: " + ",".join(both)))
    json.dump(P4, open(Path(outdir) / "criteria_P4.json", "w"), ensure_ascii=False, indent=1)
    res["P3"], res["P4"] = P3, P4
    log(f"[k={k}] เสร็จกลุ่ม ({time.time() - t_g:.0f}s) · P4 {both}")
    return res


# ───────────────────────── 4) รันกลุ่ม k=4 (+ตัวเทียบ) และภาคผนวก k=3,5 ─────────────────────────
log("เริ่ม fit รูปแบบจริง / สแกนจริง (หลัง placebo_rule.json)")
G = {}
G[4] = process_group(4, ["1a@4", "1c@4", "3b@4", "4a@4", "1b@4"], OUT, True)
for k in (3, 5):
    G[k] = process_group(k, [f"1a@{k}", f"1c@{k}"], OUT / f"appendix_k{k}", False)

# ───────────────────────── 5) ตารางเปรียบเทียบ + expectations ─────────────────────────
tab = []
for k in (3, 4, 5):
    S_ = G[k]["score"]
    for key in (f"1a@{k}", f"1c@{k}"):
        for kind in ("prim", "reg8"):
            d = S_[(S_.key == key) & (S_.kind == kind) & (S_.set == "EVAL")]
            for _, r in d.iterrows():
                tab.append(dict(model=r.model, key=key, k=k, policy=r.policy, n=r.n, med_d_adj_r2=r.med_d_adj_r2, med_d_r2_oos=r.med_d_r2_oos, med_d_bic=r.med_d_bic))
KSIDE = pd.DataFrame(tab)
save(KSIDE, "k_side_by_side.csv")

S4_ = G[4]["score"]
rv4, rot4, byi4 = G[4]["rv"], G[4]["rot"], G[4]["byi"]
exp = []


def add(i, text, obs, met):
    exp.append(dict(item=i, expectation=text, observed=obs, met=met))


ra = rv4[rv4.key == "1a@4"].set_index("index")
rc = rv4[rv4.key == "1c@4"].set_index("index")
hi = ["MSCI_ACWI", "MSCI_ACWI_EX_US", "MSCI_WORLD", "MSCI_WORLD_EX_US", "MSCI_EM", "MSCI_ASIA_EX_JAPAN", "MSCI_CHINA_ALL_SHARES"]
lo = ["MSCI_VIETNAM", "MSCI_INDIA", "MSCI_BRAZIL", "MSCI_ASEAN"]
sectors = [c for c in M28.columns if "_ACWI_" in c and c not in ("MSCI_ACWI_EX_US",)]
nlo = sum(ra.loc[s, "adj_r2_rev"] < 0.6 for s in sectors)
add("8.1/H2.1", "①a adj R²_rev ≥0.80: " + ",".join(hi) + " · <0.60: Vietnam/India/Brazil/ASEAN และ sector ≥6/10",
    "hi=" + json.dumps({s: round(float(ra.loc[s, 'adj_r2_rev']), 3) for s in hi}) + " lo=" + json.dumps({s: round(float(ra.loc[s, 'adj_r2_rev']), 3) for s in lo}) +
    f" sector<0.6 = {nlo}/10 · ①c Vietnam={rc.loc['MSCI_VIETNAM', 'adj_r2_rev']:.3f} vs ①a={ra.loc['MSCI_VIETNAM', 'adj_r2_rev']:.3f}",
    bool(all(ra.loc[s, 'adj_r2_rev'] >= 0.8 for s in hi) and all(ra.loc[s, 'adj_r2_rev'] < 0.6 for s in lo) and nlo >= 6))
r1a, r1c = rot4[rot4.key == "1a@4"], rot4[rot4.key == "1c@4"]
t1a, t1c = r1a.target.tolist(), r1c.target.tolist()
add("8.2", "①a เป้า1=ACWI ex US/ACWI (corr test ≥0.85) · เป้า2=China All (≥0.8) · เป้า3–4 ≤คล้าย · ≥1 เป้าลงทุนไม่ได้ · ①a/①c เป้า1–2 เดียวกัน · 3–4 ต่างอย่างน้อย 1",
    f"①a targets={t1a} corr_test={[round(x,3) for x in r1a.corr_test]} ลงทุนไม่ได้={[t for t in t1a if t and t not in INVEST]} · ①c targets={t1c}",
    bool(len(t1a) >= 2 and t1a[0] in ("MSCI_ACWI_EX_US", "MSCI_ACWI") and r1a.corr_test.iloc[0] >= 0.85 and t1a[1] == "MSCI_CHINA_ALL_SHARES" and r1a.corr_test.iloc[1] >= 0.8
         and t1a[:2] == t1c[:2] and t1a[2:] != t1c[2:]))
sf4 = G[4]["sf"]
sfa = sf4[sf4.key == "1a@4"]
cn4 = G[4]["cn"]
c_a = cn4[(cn4.key == "1a@4")]
n_low_M = int((c_a[c_a.target == "M28"].rho_oos < 0.5).sum())
n_low_I = int((c_a[c_a.target == "I_inv"].rho_oos < 0.5).sum())
b2 = sfa[sfa.block == "B2"].set_index("factor")
b4 = sfa[sfa.block == "B4"].set_index("factor")
ov = sum(b4.loc[f_, "r2_oos"] < b2.loc[f_, "r2_oos"] for f_ in b2.index)
add("8.3 (D.4)", "①a: PC1–2 adj R²(B2)≥0.80 · PC3–4 adj R²(B4)≤0.70 · R²_oos B4<B2 ≥3/4 · canon M28 ρ_oos c1,c2 ≥0.80 · ≥1 มิติ ρ_oos<0.50 · I_inv จำนวนมิติ<0.5 ไม่มากกว่า M28",
    f"adjR2 B2={[round(float(b2.loc[f_,'adj_r2']),3) for f_ in b2.index]} · adjR2 B4={[round(float(b4.loc[f_,'adj_r2']),3) for f_ in b4.index]} · B4<B2 oos: {ov}/4 · "
    f"ρ_oos M28={[round(float(x),3) for x in c_a[c_a.target=='M28'].rho_oos]} I_inv={[round(float(x),3) for x in c_a[c_a.target=='I_inv'].rho_oos]}",
    bool(b2.adj_r2.iloc[:2].min() >= 0.8 and b4.adj_r2.iloc[2:].max() <= 0.7 and ov >= 3 and c_a[c_a.target == "M28"].rho_oos.iloc[:2].min() >= 0.8 and n_low_M >= 1 and n_low_I <= n_low_M))
fl4 = G[4]["fl"]
def med_d(model, g, col="d_r2_oos", sub=None):
    d = fl4[(fl4.model == model)]
    if sub is not None:
        d = d[sub(d)]
    d = d[d.policy == g] if g != "ALL" else d
    return float(np.nanmedian(d[col]))
sc1 = S4_[(S4_.model == "L2-1") & (S4_.set == "EVAL")].set_index("policy")
e_med, o_med, f_med = sc1.loc["E", "med_d_r2_oos"], sc1.loc["O", "med_d_r2_oos"], sc1.loc["F", "med_d_r2_oos"]
sca = G[4]["scan"]
sa = sca[(sca.key == "1a@4")]
frac_any = float(sa.groupby("FundCode").sig_chosen.any().mean())
add("8.4", "L2-1: median ΔR²_oos E 0.01–0.06 · O≥E · F≤0.01 · ΔBIC median E ≤0 · กอง EVAL มีดัชนีเดี่ยว significant ≥1 ตัว 30–60% (ขั้น C.2)",
    f"E={e_med:.4f} O={o_med:.4f} F={f_med:.4f} · ΔBIC_E={sc1.loc['E','med_d_bic']:.3f} · frac_any_sig={frac_any:.3f} (ขั้น {STEP4})",
    bool(0.01 <= e_med <= 0.06 and o_med >= e_med and f_med <= 0.01 and sc1.loc['E', 'med_d_bic'] <= 0 and 0.30 <= frac_any <= 0.60))
P1a = G[4]["P1"]
passa = list(P1a[(P1a.key == "1a@4") & P1a.P1]["index"])
cand = {"MSCI_VIETNAM", "MSCI_INDIA", "MSCI_JAPAN", "MSCI_KOREA", "MSCI_TAIWAN"}
sectors_ = {c for c in M28.columns if "_ACWI_" in c and c != "MSCI_ACWI_EX_US"}
add("8.5", "ผ่าน P1 บน ①a: ≥1 ใน Vietnam/India/Japan/Korea/Taiwan · sector ≥1 (หรือไม่มีเลยถ้าขั้น 3) · ACWI/World/EM ไม่ผ่าน", f"ผ่าน P1 = {passa} (ขั้น {STEP4})",
    bool((len(set(passa) & cand) >= 1 and len(set(passa) & sectors_) >= 1 or (STEP4 == 3 and not passa)) and not (set(passa) & {"MSCI_ACWI", "MSCI_WORLD", "MSCI_EM"})))
r2m = S4_[(S4_.model == "L2-2") & (S4_.set == "EVAL")].set_index("policy")
add("8.6", "REG8 (L2-2/4): ΔadjR² train > ΔR²_oos · median ΔR²_oos(E) −0.02…+0.04 · ΔBIC>0",
    f"L2-2 E: ΔadjR²={r2m.loc['E','med_d_adj_r2']:.4f} ΔR²_oos={r2m.loc['E','med_d_r2_oos']:.4f} ΔBIC={r2m.loc['E','med_d_bic']:.2f} · L2-4 E: " +
    (lambda x: f"ΔadjR²={x.loc['E','med_d_adj_r2']:.4f} ΔR²_oos={x.loc['E','med_d_r2_oos']:.4f} ΔBIC={x.loc['E','med_d_bic']:.2f}")(S4_[(S4_.model == 'L2-4') & (S4_.set == 'EVAL')].set_index('policy')),
    bool(r2m.loc['E', 'med_d_adj_r2'] > r2m.loc['E', 'med_d_r2_oos'] and -0.02 <= r2m.loc['E', 'med_d_r2_oos'] <= 0.04 and r2m.loc['E', 'med_d_bic'] > 0))
cm = S4_[(S4_.set == "COMMON_PRIM") & (S4_.policy == "ALL") & (S4_.kind == "prim")].set_index("model")
cmE = S4_[(S4_.set == "COMMON_PRIM") & (S4_.policy == "E") & (S4_.kind == "prim")].set_index("model")
v = {m_: float(cm.loc[m_, "med_d_r2_oos"]) for m_ in ("L2-5", "L2-1", "L2-7", "L2-6")}
add("8.7 (E.3)", "บนกอง primary ร่วม: ΔR²_oos ③b(L2-5) 0.08–0.20 > ①a≈①b > ④a(L2-6) · |①b−①a|≤0.02",
    f"n={int(cm.loc['L2-1','n'])} ALL: " + json.dumps({k_: round(x, 4) for k_, x in v.items()}) + " · E: " + json.dumps({m_: round(float(cmE.loc[m_, 'med_d_r2_oos']), 4) for m_ in v}),
    bool(0.08 <= v["L2-5"] <= 0.20 and v["L2-5"] > v["L2-1"] > v["L2-6"] and abs(v["L2-7"] - v["L2-1"]) <= 0.02))
rd = REDUN[REDUN.set == "M28"]
n90 = int((rd.r2_on_others >= 0.90).sum())
big = rd.groupby("cluster")["index"].apply(list)
bigc = max(big.tolist(), key=len)
add("8.8 (Q3)", "≥8/28 ดัชนี R² บนดัชนีอื่น ≥0.90 · คลัสเตอร์ใหญ่สุดมี ACWI/World/ACWI ex US/World ex US",
    f"n(R²≥0.90)={n90} · คลัสเตอร์ใหญ่สุด={bigc}", bool(n90 >= 8 and {"MSCI_ACWI", "MSCI_WORLD", "MSCI_ACWI_EX_US", "MSCI_WORLD_EX_US"} <= set(bigc)))
ps = {k: {key: set(G[k]["P1"][(G[k]["P1"].key == key) & G[k]["P1"].P1]["index"]) for key in (f"1a@{k}", f"1c@{k}")} for k in (3, 4, 5)}
diffs = {k: {f: len(ps[k][f"{f}@{k}"] ^ ps[4][f"{f}@4"]) for f in ("1a", "1c")} for k in (3, 5)}
medk = {k: {m_: float(G[k]["score"][(G[k]["score"].model == m_) & (G[k]["score"].set == "EVAL") & (G[k]["score"].policy == "E")].med_d_r2_oos.iloc[0])
            for m_ in (["L2-1", "L2-3", "L2-2", "L2-4"] if k == 4 else [f"L2-{i}k{k}" for i in (1, 3, 2, 4)])} for k in (3, 4, 5)}
mono = all(medk[3][a] >= medk[4][b] >= medk[5][c] for a, b, c in (("L2-1k3", "L2-1", "L2-1k5"), ("L2-3k3", "L2-3", "L2-3k5")))
p4 = {k: set(G[k]["P4"]["pass_both"]) for k in (3, 4, 5)}
add("8.9 (แก้)", "ชุดดัชนีผ่าน P1 ที่ k=3/5 ต่างจาก k=4 ≤2 ดัชนี (แต่ละ ①a/①c) · median ΔR²_oos(E) L2-1k/L2-3k เรียง k3≥k4≥k5 · REG8 ทิศเดียวกัน · P4 ต่าง ≤1",
    f"ผ่าน P1: {json.dumps({k: {f: sorted(x) for f, x in zip(('1a','1c'), (ps[k][f'1a@{k}'], ps[k][f'1c@{k}']))} for k in (3,4,5)})} · |Δชุด| vs k=4: {json.dumps(diffs)} · medΔR²_oos(E): {json.dumps(medk)} · P4 ต่าง k3={len(p4[3]^p4[4])} k5={len(p4[5]^p4[4])}",
    bool(max(max(d.values()) for d in diffs.values()) <= 2 and mono and len(p4[3] ^ p4[4]) <= 1 and len(p4[5] ^ p4[4]) <= 1))
py4 = G[4]["py"]
pt = py4[py4.window == "test"]
add("8.10", "PY bootstrap: size จริง 6–15% · p_boot ≥ p asymptotic ทุกแถว · ไม่มีแถว p_boot<0.05 (test)",
    f"size05 ช่วง {pt.size05.min():.3f}–{pt.size05.max():.3f} (median {pt.size05.median():.3f}) · แถวที่ p_boot<p: {int((pt.p_boot < pt.p).sum())}/{len(pt)} · แถวที่ p_boot<0.05: {int((pt.p_boot < 0.05).sum())}",
    bool(pt.size05.min() >= 0.06 and pt.size05.max() <= 0.15 and (pt.p_boot >= pt.p).all() and not (pt.p_boot < 0.05).any()))
mo = G[4]["mon"]
mw = {}
for key in ("1a@4", "1c@4", "1b@4"):
    m_ = mo[(mo.key == key) & (mo.kind == "prim") & (mo.policy == "E")]
    mw[key] = (float(m_.d_r2_oos_med.iloc[0]), float(S4_[(S4_.key == key) & (S4_.kind == "prim") & (S4_.set == "EVAL") & (S4_.policy == "E")].med_d_r2_oos.iloc[0]))
add("8.11", "รายเดือน: ΔR²_oos ของ primary index สูงกว่ารายสัปดาห์", "E (รายเดือน, รายสัปดาห์): " + json.dumps({k_: [round(a, 4), round(b, 4)] for k_, (a, b) in mw.items()}),
    bool(all(a > b for a, b in mw.values())))
pls = PLS.copy()
r0 = RULE[4]["R0"]
add("8.12 (ใหม่)", "placebo: R₀ 6–12% · R₁ ≤8% · สัดส่วน shift 26 vs 52 ต่างกัน ≤2 จุด %",
    f"R0={r0:.4f} R1={RULE[4]['R1']:.4f} ขั้น={STEP4} · ตาราง: " + json.dumps(pls[pls.k == 4][['key', 'shift', 'frac_p05', 'frac_padj05']].round(4).to_dict('records')),
    bool(0.06 <= r0 <= 0.12 and RULE[4]["R1"] <= 0.08 and all(abs(pls[(pls.key == k_) & (pls['shift'] == 26)].frac_p05.iloc[0] - pls[(pls.key == k_) & (pls['shift'] == 52)].frac_p05.iloc[0]) <= 0.02 for k_ in ("1a@4", "1c@4"))))
passidx = byi4[(byi4.key == "1a@4") & byi4["index"].isin(passa)]
ratio = float((passidx.n_groups_sig / passidx.n_funds_sig).median()) if len(passidx) else np.nan
add("8.13 (ใหม่)", "จำนวนกลุ่มกองอิสระใน EVAL 150–195 · ต่อดัชนีผ่าน P1(ก): n_groups_sig/n_funds_sig median ≥0.6",
    f"กลุ่ม={n_groups_total} (ใหญ่สุด {FC.group_size.max()} กอง) · median ratio={ratio if np.isfinite(ratio) else 'N/A (ไม่มีดัชนีผ่าน)'}",
    bool(150 <= n_groups_total <= 195 and (np.isnan(ratio) or ratio >= 0.6)))
EXPD = pd.DataFrame(exp)
save(EXPD, "expectations_vs_results.csv")


# ── map_factor_index.csv: แผนที่ factor ↔ ดัชนี ──
mrows_ = []
for key in ("1a@4", "1c@4", "1b@4", "3b@4", "4a@4"):
    fr = BASES[key]
    sfk_ = G[4]["sf"][G[4]["sf"].key == key]
    for fk in fr.columns:
        d_ = pd.concat([fr[fk].rename("f"), I], axis=1)[mtr].dropna()
        cc = d_.drop(columns="f").corrwith(d_["f"])
        top3 = cc.reindex(cc.abs().sort_values(ascending=False, kind="stable").index)[:3]
        row = dict(kind="factor", key=key, name=fk, top1=top3.index[0], corr1=top3.iloc[0], top2=top3.index[1], corr2=top3.iloc[1], top3=top3.index[2], corr3=top3.iloc[2])
        for b in ("B1", "B2", "B3", "B4"):
            q = sfk_[(sfk_.factor == fk) & (sfk_.block == b)]
            row["adjR2_" + b] = float(q.adj_r2.iloc[0])
        if key in ROT:
            row["rotation_targets"] = ";".join(ROT[key]["targets"])
        mrows_.append(row)
P1_ = {k_: G[4]["P1"][(G[4]["P1"].key == k_)].set_index("index") for k_ in ("1a@4", "1c@4")}
P3_ = {k_: G[4]["P3"][(G[4]["P3"].key == k_)].set_index("index") for k_ in ("1a@4", "1c@4")}
cl_ = REDUN[REDUN.set == "M28"].set_index("index")
ra_ = G[4]["rv"][G[4]["rv"].key == "1a@4"].set_index("index")
repm = {c_: ra_.loc[g["index"], "adj_r2_rev"].idxmax() for c_, g in REDUN[REDUN.set == "M28"].groupby("cluster")}
for j in I.columns:
    row = dict(kind="index", name=j, investable=j in INVEST)
    for k_ in ("1a@4", "1c@4"):
        row["P1_" + k_] = bool(P1_[k_].loc[j, "P1"]) if j in P1_[k_].index else np.nan
        row["P1label_" + k_] = P1_[k_].loc[j, "label"] if j in P1_[k_].index else ""
        row["P3_" + k_] = P3_[k_].loc[j, "P3"]
        row["adj_r2_rev_" + k_] = P3_[k_].loc[j, "adj_r2_rev"]
    if j in cl_.index:
        row.update(cluster=int(cl_.loc[j, "cluster"]), cluster_rep=repm[int(cl_.loc[j, "cluster"])], r2_on_others=cl_.loc[j, "r2_on_others"], vif=cl_.loc[j, "vif"])
    mrows_.append(row)
MAPDF = pd.DataFrame(mrows_)
save(MAPDF, "map_factor_index.csv")
nm1a, nm1c = ROT["1a@4"]["targets"], ROT["1c@4"]["targets"]
log("เขียน map_factor_index.csv")

# ④-1 (BRIEF ข้อ 41)
n41 = []
for k in (3, 4, 5):
    for f in ("1a", "1c"):
        key = f"{f}@{k}"
        c_ = G[k]["cn"][(G[k]["cn"].key == key) & (G[k]["cn"].target == "M28")]
        sf_ = G[k]["sf"]
        lowb2 = bool(((sf_.key == key) & (sf_.block == "B2") & (sf_.adj_r2 < 0.5)).any())
        nlow = int((c_.rho_oos < 0.5).sum())
        n41.append(dict(key=key, n_dims_rho_oos_lt_0_5=nlow, any_factor_adjR2_B2_lt_0_5=lowb2,
                        verdict=("ดัชนีไม่จับ %d มิติ" % nlow) if nlow > 0 and lowb2 else ("ไม่มีมิติที่ดัชนีไม่จับ" if nlow == 0 and not lowb2 else "ไม่สรุป (สองตัวชี้ขัดกัน)")))
N41 = pd.DataFrame(n41)
save(N41, "q4_1_verdict.csv")

# ───────────────────────── 6) meta + results.md ─────────────────────────
import scipy  # noqa: E402
import statsmodels  # noqa: E402

meta = dict(created=datetime.now().isoformat(timespec="seconds"), seed=SEED, data_sha256=man, pinned_sha256=pin_sha, lib_sha256=lib_hashes,
            versions=dict(python=platform.python_version(), numpy=np.__version__, pandas=pd.__version__, scipy=scipy.__version__, statsmodels=statsmodels.__version__),
            runtime_sec=round(time.time() - T0, 1), placebo_rule=rule_json, spec="S004 + S005 addendum (รีวิว S005 PASS)")
json.dump(meta, open(OUT / "run_meta.json", "w"), ensure_ascii=False, indent=1)

L = []
L.append("# results — S005 (L2 factor × MSCI · S004 + addendum S005 · รีวิว S005 PASS)\n")
L.append(f"รัน: {meta['created']} · seed {SEED} · runtime {meta['runtime_sec']} s · รายงานตัวเลขอย่างเดียว ไม่ตีความเกินตัวเลข\n")
L.append("**ป้ายบังคับ:** (ก) ED ตรงกับแหล่งรอง (R `cate::EigenDiff`) · ยังไม่เปิดต้นฉบับ Onatski 2010 [ค่าชั่วคราว 22] · (ก2) PY ตรงต้นฉบับ JFEc 2024 [24] แต่คงป้าย (N−1)ρ̄²>1 + p_boot · "
         "(ข) ช่วง test 2024–2025 ถูกใช้เลือกรูปแบบใน L1 แล้ว — ไม่ใช่หลักฐานนอกช่วงที่อิสระ · (ค) ค่าที่ยืนยัน 1–21 · ชั่วคราว 22–42 (ผลขึ้นกับ 22,24,31–42) · "
         "CI: " + CI_LABEL + " · วิธีหมุน/Bai–Ng/HK: ใช้ป้าย F-R003 (least-squares oblique ตามแนว Hurley–Cattell; R² และ canonical corr **แนว** Bai–Ng ไม่ใช่การทดสอบ A(j)/M(j); α-spanning แนว HK ด้วย Dimson α; HAC Wald asymptotic) · "
         "BY: PRDS ไม่ครอบคลุม Wald χ²(2)/t สองด้าน → รายงาน BY คู่ (m=5,796 → c(m)≈9.24) · ยังไม่เทียบฉบับเต็มทีละสมการ [35]\n")
L.append("## 0. ตรวจก่อนรัน\n- sha256 ข้อมูล 8 ไฟล์ตรง manifest+spec; ไฟล์ pin 5 ไฟล์ (factors_S003_weekly, fund_level, grs_ports, regions, S004) ตรง · ขนาดชุดกองตรง spec (EVAL 207 E175/F18/O14 · E67 67 · STAB 191 · PY_test 206 · PY_train 148 · ฐาน 277 · bal 134)\n"
         f"- ①a/①b/①c ที่ k=4 สร้างซ้ำตรง parquet (≤1e-12) · EM-PCA ①c: k=3 iter {L1[3]['parts']['em_iter']}, k=4 {L1[4]['parts']['em_iter']}, k=5 {L1[5]['parts']['em_iter']} ทุกอัน converged\n"
         f"- ลำดับเขียนก่อน fit: primary_index.csv → fund_clusters.csv → rotation_targets.csv → redundancy.csv → placebo_* → placebo_rule.json (ดู run.log)\n")
L.append(f"## 1. placebo + กฎ C.2\n{md(PLS.round(4))}\n- k=4: R₀={RULE[4]['R0']:.4f} R₁={RULE[4]['R1']:.4f} → **ขั้น {STEP4}** · k=3: ขั้น {RULE[3]['step']} (R₀={RULE[3]['R0']:.4f}, R₁={RULE[3]['R1']:.4f}) · k=5: ขั้น {RULE[5]['step']} (R₀={RULE[5]['R0']:.4f}, R₁={RULE[5]['R1']:.4f})\n"
         "- ป้าย n1: placebo เลื่อนวนทำให้ดัชนีเกือบไม่สัมพันธ์กับ S แต่สแกนจริงใช้ดัชนีสัมพันธ์กับ S → size ของ HAC อาจต่างกัน · n5: กฎคาลิเบรตจาก ①a/①c ใช้กับ ③b/④a/①b ด้วย (p ของตัวเทียบสูงกว่า)\n"
         f"- กลุ่มกองอิสระ (corr≥0.95 · connected components): {n_groups_total} กลุ่มจาก 207 กอง · กลุ่มใหญ่สุด {int(FC.group_size.max())} กอง\n")


def sc_view(S_, setname="EVAL", models=None):
    d = S_[(S_.set == setname)]
    if models:
        d = d[d.model.isin(models)]
    return d[["model", "kind", "policy", "n", "K", "adjr2_med", "adjr2_iqr", "med_d_adj_r2", "r2oos_med", "r2oos_iqr", "med_d_r2_oos", "r2gap_med", "mean_abs_alpha_pct",
              "signed_mean_alpha_pct", "bh_reject", "bic_med", "med_d_bic", "med_d_abs_alpha_pct"]]


L.append("## 2. ตารางคะแนน 6 ข้อ — EVAL 207 (ข้อ 1–4) · k=4 · Δเทียบฐานชุดเดียวกัน (ป้าย ข)\n" + md(sc_view(S4_).round(4)))
bt = G[4]["boot"]
L.append("### 2.1 bootstrap CI ของ median Δ (2,000 รอบ · seed 20261015)\n" + f"_{CI_LABEL}_\n\n" + md(bt[bt.group.isin(['E', 'ALL']) & bt.stat.isin(['median_d_r2_oos', 'median_d_adj_r2', 'median_d_bic'])].round(4)))
L.append("### 2.2 กองในชุด E67 (นอก sample PCA)\n" + md(sc_view(S4_, 'E67').query("policy == 'E'").round(4)))
L.append("### 2.3 กอง primary ร่วม (E.3) ทุกฐาน\n" + md(sc_view(S4_, 'COMMON_PRIM').round(4)))
L.append("## 3. GRS (17 พอร์ต · L2-2/L2-4)\n" + md(G[4]["grs"].round(4)))
L.append("## 4. PY + null bootstrap (B=999 · บล็อก 4 · fixed-design · ป้าย (N−1)ρ̄²>1)\n" + md(G[4]["py"][["model", "key", "window", "kind", "N", "T", "m_regressors", "J", "p", "p_boot", "size05", "sd_J", "rho2", "Nrho2", "mean_alpha_star", "role", "note"]].round(4)))
L.append("## 5. ความเสถียร (r ดิบ H1/H2 · STAB 191) — ค่าเฉลี่ยข้าม factor ต่อโมเดล\n" + md(G[4]["stab"][G[4]["stab"].policy.isin(["E", "ALL"])].groupby(["model", "policy"]).r_raw.agg(["mean", "min", "count"]).reset_index().round(3)))
L.append("### 5.1 β ของดัชนีที่เพิ่ม (primary) แยกตามดัชนี (≥10 กอง)\n" + md(G[4]["stab"][G[4]["stab"].policy == "by_index"].round(3)))
L.append("## 6. ตัวชี้วัดเฉพาะ L2\n### 6.1 การหมุน (k=4 และ ภาคผนวก k ใน appendix_k*/rotation.csv)\n" + md(rot4.round(3)))
for k in (3, 5):
    L.append(f"#### rotation k={k}\n" + md(G[k]["rot"].round(3)))
sfk = G[4]["sf"]
L.append("### 6.2 spanning ไปข้างหน้า (adj R² = ตัวอ่านหลัก · R²_oos = diagnostic overfit) k=4\n" + md(sfk[["key", "factor", "block", "n", "p", "r2", "adj_r2", "r2_oos", "alpha_pct_yr", "t_alpha", "defn", "bh_family", "bh_reject", "alpha_role"]].round(3)))
L.append("Wald ร่วม B1 (HAC asymptotic · Holm 5)\n" + md(G[4]["sw"].round(4)))
L.append("### 6.3 canonical correlation (ρ_oos น้ำหนักตรึงจาก train · ป้าย ข)\n" + md(G[4]["cn"].round(3)))
L.append("### 6.4 ④-1 (BRIEF ข้อ 41: ρ_oos<0.50 และ adj R²(B2)<0.50 ทั้งคู่)\n" + md(N41))
L.append("### 6.5 spanning ย้อนกลับ ①a/①c adj R²_rev (ตัวหลัก) — ทั้ง 39 ดัชนีใน span_reverse.csv\n" + md(
    rv4[rv4.key.isin(["1a@4", "1c@4"])].pivot(index="index", columns="key", values="adj_r2_rev").round(3).reset_index()))
L.append("### 6.6 สแกนดัชนีเดี่ยว: ดัชนีผ่าน P1 / สรุปต่อชุดฐาน (ขั้น C.2 = %d)\n" % STEP4 + md(G[4]["P1"][G[4]["P1"].P1].round(4)))
top = byi4[byi4.key.isin(["1a@4", "1c@4"])].sort_values("n_groups_sig", ascending=False).groupby("key").head(8)
L.append("ดัชนีที่ n_groups_sig สูงสุด 8 อันดับแรกต่อชุดฐาน\n" + md(top[["key", "index", "n_funds_sig", "n_groups_sig", "n_funds_sig_E", "n_funds_sig_F", "n_funds_sig_O", "n_primary", "n_groups_exposed", "med_d_r2_oos_all", "med_d_r2_oos_primary", "near_dup", "n_BH_p", "n_BY_p", "n_BH_padj", "n_BY_padj"]].round(4)))
L.append("### 6.7 Q3 redundancy (M28) + P3\n" + md(REDUN[REDUN.set == "M28"].round(3)))
L.append("### 6.8 P4\n```\n" + json.dumps(G[4]["P4"], ensure_ascii=False, indent=1) + "\n```\n")
L.append("### 6.9 รายเดือน (L2-1/L2-3/L2-7 + สแกน ①a)\n" + md(mo.round(4)))
L.append("## 7. ภาคผนวก k = 3 / 5 (ครบ B.2 ใน appendix_k3/ appendix_k5/) — Δ ที่ k เดียวกัน\n" + md(KSIDE[KSIDE.policy.isin(["E", "ALL"])].round(4)))
for k in (3, 5):
    L.append(f"#### P4 k={k}\n```\n" + json.dumps(G[k]["P4"], ensure_ascii=False) + "\n```\n")
L.append("## 8. เทียบผลกับความคาดหมายล่วงหน้า (ทุกข้อ · met = ตรงตามเกณฑ์ตัวเลขของ spec ทุกประโยค)\n" + md(EXPD))
ptx = G[4]["py"]
ptx = ptx[(ptx.window == "test")]
main_py = ptx[ptx.model.isin(["ฐาน 1a", "L2-1", "L2-2", "ฐาน 1c", "L2-3", "L2-4"])]
cmp_py = ptx[ptx.model.isin(["ฐาน 3b", "L2-5"])]
L.append("### 4.1 PY: p (asymptotic) คู่ p_boot ทุกแถว (test · k=4 · ตรวจจาก py.csv)\n" + md(ptx[["model", "key", "J", "p", "p_boot", "size05"]].round(4)) +
         f"- แถวหลัก ①a/①c (6 แถว): p_boot ต่ำสุด {main_py.p_boot.min():.4f} · p_boot>0.05 ทุกแถว = {bool((main_py.p_boot > 0.05).all())} · แถวที่ p_boot<0.10: {int((main_py.p_boot < 0.10).sum())} ({', '.join(f'{r.model}={r.p_boot:.3f}' for r in main_py[main_py.p_boot < 0.10].itertuples())}) · p asymptotic ต่ำสุด {main_py.p.min():.4f}\n"
         f"- ตัวเทียบ ③b/L2-5: p_boot = {', '.join(f'{r.model}={r.p_boot:.3f}' for r in cmp_py.itertuples())}\n"
         f"- size05 ภายใต้ null ของข้อมูลเรา {ptx.size05.min():.3f}–{ptx.size05.max():.3f} (ทิศตรงข้ามความคาดหมาย 8.10 ที่คาด 6–15%) · p_boot<p ใน {int((ptx.p_boot < ptx.p).sum())}/{len(ptx)} แถว\n")
rl4 = G[4]["roll"]
L.append("### 5.2 rolling 104 สัปดาห์ (ภาคผนวกข้อ 5 · STAB 191 · เริ่มทุก 4 สัปดาห์ 40 หน้าต่าง · corr ข้ามกองของ β หน้าต่าง vs β เต็มช่วง) — เฉลี่ยข้าม factor\n" +
         md(rl4[rl4.policy.isin(["E", "ALL"]) & (rl4.factor != "PRIM")].groupby(["model", "policy"]).agg(roll_median_mean=("roll_median", "mean"), roll_min_min=("roll_min", "min")).reset_index().round(3)) +
         "ไฟล์เต็ม: rolling_104.csv (และ appendix_k3/, appendix_k5/)\n")
cdp = PRIMDF[(PRIMDF.form == "none") & (PRIMDF["index"] == "MSCI_ACWI_CD")]
L.append("## 8.1 ข้อสังเกตตามรีวิวผล (m2 m4 m5 m6 · ไม่เปลี่ยนตัวเลข)\n"
         "- m2: P1(ก) ที่ล็อกไว้ (n_groups_sig≥7 และ n_funds_sig≥7) ไม่คัดดัชนีใดออก — ผ่านทั้ง 28 ดัชนีบน ①a และ ①c; P1 ถูกตัดสินโดย P1(ข) (median ΔR²_oos ≥ 0.02) เป็นหลัก · ห้ามอ่านว่า 'ดัชนี X เพิ่มคำอธิบายให้ N กอง' จากจำนวนกอง significant (train) — ให้อ่านจาก ΔR²_oos ในกอง primary และ median ΔR²_oos ทุกกอง (ตาราง scan_by_index)\n"
         "- m4: 8.4 (96.6%) ไม่ได้มาจาก size ที่ไม่คุม (placebo ด้วยนิยามเดียวกันให้ 0–1.4% ตาม placebo_scan) แต่เป็น power ของ T=155 × 28 ดัชนี · 8.9: ความต่างของชุด P1 ข้าม k มาจากดัชนีที่ median ΔR²_oos ชิดเกณฑ์ 0.02 · แกน P4 (ACWI_HC, ACWI_UT, EUROPE, INDIA, JAPAN, VIETNAM) ตรวจได้จาก criteria_P4.json ของ k=3/4/5\n"
         "- m6: primary index = MSCI_ACWI_CD ในกอง " + str(len(cdp)) + " กอง (E/F/O = " + "/".join(str(int((pol[cdp.FundCode] == g).sum())) for g in "EFO") + ") — ต้องตรวจองค์ประกอบกองกลุ่มนี้ (ไฟล์ primary_index.csv, form=none) ก่อนตีความ · รายชื่อ: " + ", ".join(sorted(cdp.FundCode)) + "\n")
L.append("## 8.2 deviation ของ test 15 (m5)\n"
         "- เกณฑ์ใน spec S005 test 15: ①a(k=3)=3 คอลัมน์แรกของ k=4 และ k=5 4 คอลัมน์แรก=k=4 ทั้งตาราง (max|diff|≤1e-12) · ที่ทำจริง: ตรวจ ≤1e-12 เฉพาะแถวที่กองใน Λ ครบทุกตัว (train ทุกแถวครบ) · เหตุผล: 80 แถวช่วง test ที่กองใน Λ ขาดข้อมูล factor_returns ทำ LS บนเซตย่อยของ Λ ซึ่งไม่ orthonormal จึงต่างกัน (ไม่ใช่เรื่องเครื่องหมาย)\n"
         "- ผลที่ reviewer ตรวจซ้ำ: 80 แถวทั้งหมดอยู่ใน test (train 0 แถว) · ต่าง ≤1.5% ของ sd (k3 vs k4) · corr ≥0.99998 · ไม่กระทบภาคผนวก k=3/5 เพราะสร้างด้วย build_line1(kstar=k) โดยตรง · analyst เปลี่ยนเกณฑ์ test เองโดยไม่ส่งกลับ designer — บันทึกเป็น deviation\n")
L.append("## 9. การตัดสินใจของ analyst / จุดกำกวม\n"
         "- test 15 (ซ้อนคอลัมน์): ①a ที่ k=3/5 ตรงกับ k=4 ≤1e-12 **เฉพาะแถวที่กองใน Λ ครบทุกตัว**; 80 แถวช่วง test (กองใน Λ ขาดข้อมูล) ต่างกันเพราะ least-squares บนเซตย่อยของ Λ ไม่ orthonormal — ไม่ใช่เรื่องเครื่องหมาย; ไม่กระทบการรัน (k=3/5 สร้างตรงด้วย build_line1(kstar=k) ตาม B.1)\n"
         "- py_null_bootstrap: fitted ของ y* ไม่รวมค่าคงที่ (บังคับ α=0) · ฟังก์ชันและ test 14 ยืนยัน |mean α̂*|<1e-4\n"
         "- rolling 104 (ภาคผนวกข้อ 5) เพิ่มภายหลังรีวิวผล: rolling_104.csv · ไฟล์ผลเดิมไม่เปลี่ยน hash\n- ไฟล์ผลรันชื่อ run.py (ตามคำสั่ง) แทน run_s005.py · รันเฉพาะ ALL ของ PY bootstrap · bootstrap CI ของ Δ เป็น median ของ Δ รายกอง (ส่วนต่างจับคู่) ไม่ใช่ผลต่างของ median\n"
         "- primary index ใช้ rank ถัดไปเมื่อ in_span กับฐาน (③b: ACWI/USA ฯลฯ; ④a: ACWI…) บันทึกใน primary_index.csv (rank_used, skipped_reason) · ธง common_primary = rank_used=1 ครบ 5 ฐาน k=4\n"
         "- n_groups_exposed (BRIEF ข้อ 42) เพิ่มใน scan_by_index.csv · ขนาดกลุ่มกองใหญ่สุดรายงานข้างบน (n4)\n"
         "- ภาคผนวก k: placebo ประเมินกฎที่ k นั้นแยก (sig_stepk, *_stepk) แต่ P1 หลักใช้ขั้นของ k=4 (STEP4) ตามข้อ C.2\n"
         "- รายเดือน: ใช้ Λ train รายสัปดาห์ · M28 รายเดือน = ผลตอบแทน MSCI ส่วนเกิน rf รายเดือน · scan รายเดือนเฉพาะ ①a · L2-5/6 ไม่ทำ (p>17)\n"
         "- GRS: สัปดาห์ที่พอร์ตมี <3 กองถูกตัดเหมือน S003 (ว่างเปล่าใน S003)\n")
L.append("## 10. ต้องให้ผู้ใช้ตัดสินใจ\n- เลือกชุดผลจากเกณฑ์ P1–P4 ที่ล็อก (ข้อ 31) · ตัดสินใจ k* (ถ้าเปลี่ยน ใช้ภาคผนวกที่ลงทะเบียน) · ไม่มีรายการที่ analyst ต้องหยุดรอ\n")
(OUT / "results.md").write_text("\n".join(L))
log(f"เสร็จ · runtime {time.time() - T0:.0f}s")
