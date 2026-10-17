"""S003 run — เรียก lib เท่านั้น (S003 = S002 + addendum · รีวิว M1–M4) · ใช้: python run.py [--out DIR]"""
import hashlib
import json
import platform
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

LIB = Path(__file__).resolve().parents[2] / "lib"
sys.path.insert(0, str(LIB))
import external as ex  # noqa: E402
import forms as fm_  # noqa: E402
import fundff as ff  # noqa: E402
import hybrid  # noqa: E402
import io_l1  # noqa: E402
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
LOG_MD = []


def log(msg):
    line = f"[{datetime.now().isoformat(timespec='seconds')} +{time.time() - T0:6.1f}s] {msg}"
    LOGF.write(line + "\n")
    LOGF.flush()
    print(line, flush=True)


def save(df, name, **kw):
    df.to_csv(OUT / name, index=kw.pop("index", False))
    return df


FORMS = fm_.FORM_NAMES
PROV = {  # ค่าชั่วคราวที่ผลขึ้นต่อ (BRIEF · ข้อ)
    "1a": "1,3,4,5,7,10,15", "1b": "1,3,4,5,7,10,15", "1c": "1,3,4,5,7,10,15",
    "2a": "1,3,4,5,7,10,13,14,15", "2b": "1,3,4,5,7,10,13,14,15,17,21",
    "2c": "1,3,4,5,7,8,10,13,14,15,16,17,21 (ไม่เทียบตรง)",
    "3a": "1,3,4,5,7,10,15,20", "3b": "1,3,4,5,7,10,11,15,20", "3c": "1,3,4,5,7,10,11,15,20", "4a": "1,3,4,5,7,10,15,20",
}
COMMON = {"1": "PC1", "2": "APB_E", "3": "MKT", "4": "MKT"}
decisions = []


def decide(topic, choice, impact):
    decisions.append((topic, choice, impact))


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
                cells.append("–" if not np.isfinite(v) else (str(int(v)) if (c in ("k", "T", "v", "N", "n", "N_ports", "T_used", "L", "dof2", "m") and float(v).is_integer()) else f"{v:.{nd}f}"))
            else:
                cells.append(str(v))
        out.append("| " + " | ".join(cells) + " |")
    return "\n".join(out) + "\n"


# ───────────────────────── 1) ข้อมูล + ชุดกอง ─────────────────────────
log("START run S003")
man = io_l1.verify_manifest()
log("sha256 ข้อมูลตรง manifest + spec: " + json.dumps({k.split('/')[-1]: v for k, v in man.items()}))
lib_hashes = io_l1.lib_hash()
log("sha256 lib: " + json.dumps(lib_hashes))
R = io_l1.load_returns("W")
F = io_l1.load_factors("W")
Rm = io_l1.load_returns("M")
Fm = io_l1.load_factors("M")
AUM = io_l1.load_aum()
U = io_l1.load_universe().set_index("FundCode")
pol = U["policy"]
idx = R.index
POS = np.arange(len(idx))
keep = sp.dedup_keep(io_l1.load_dup_pairs(), U.loc[R.columns, "n_weeks"])
base = sp.eligible(R, "unbalanced", keep)
bal = sp.eligible(R, "balanced", keep)
EVAL = sp.eligible(R, "EVAL", keep)
EVAL52 = sp.eligible(R, "EVAL52", keep)
FULL = sp.eligible(R, "FULL")
STAB = sp.eligible(R, "STAB", keep)
PYTR = sp.eligible(R, "PY_train", keep)
PYTE = sp.eligible(R, "PY_test", keep)
PYTC = sp.eligible(R, "PY_train_c", keep)
balset = set(bal)
E67 = [c for c in EVAL if c not in balset and pol[c] == "E"]
EVAL_in = [c for c in EVAL if c in balset]
EVAL_out = [c for c in EVAL if c not in balset]
expect = dict(base=277, bal=134, EVAL=207, STAB=191, PYTR=148, PYTE=206, PYTC=200, E67=67, EVALin=132)
got = dict(base=len(base), bal=len(bal), EVAL=len(EVAL), STAB=len(STAB), PYTR=len(PYTR), PYTE=len(PYTE), PYTC=len(PYTC),
           E67=len(E67), EVALin=len(EVAL_in))
assert got == expect, (got, expect)
cnt_tbl = pd.DataFrame([
    dict(set=n, n=len(l), E=int((pol[l] == "E").sum()), F=int((pol[l] == "F").sum()), O=int((pol[l] == "O").sum()))
    for n, l in [("base(unbalanced ตัดซ้ำ)", base), ("balanced", bal), ("EVAL", EVAL), ("EVAL52", EVAL52), ("FULL(ไม่ตัดซ้ำ)", FULL),
                 ("STAB", STAB), ("PY_train", PYTR), ("PY_test", PYTE), ("PY_train_c", PYTC), ("EVAL ใน sample PCA", EVAL_in),
                 ("EVAL นอก sample PCA", EVAL_out), ("E67", E67)]])
log("ขนาดชุดกอง ตรง spec: " + json.dumps(got))
mtr, mte = window_mask(idx, "train"), window_mask(idx, "test")
mtrc = window_mask(idx, "train_c")
halves = sp.split_halves(base, pol)
HA = sorted(halves.FundCode[halves.half == "A"])
HB = sorted(halves.FundCode[halves.half == "B"])

# ── ลำดับบังคับ: regions.csv → grs_ports.csv → halves.csv → (เริ่ม fit) ──
tab = fm_.train_characteristics(R, F, AUM, pol, base)
reg = tab["reg"]
rr = pd.DataFrame({"FundCode": tab["EO"]})
for c in ex.REGION_IDX:
    rr["r2_" + c] = tab["r2"].loc[tab["EO"], c].to_numpy()
rr["r2_gold"] = tab["r2"].loc[tab["EO"], "GOLDX"].to_numpy()
rr["r2_tdex"] = tab["r2"].loc[tab["EO"], "TDEXX"].to_numpy()
rr["policy"] = pol[tab["EO"]].to_numpy()
rr["max_r2"] = reg.loc[tab["EO"], "max_r2"].to_numpy()
rr["label_pre"] = reg.loc[tab["EO"], "label_pre"].to_numpy()
rr["label_post"] = reg.loc[tab["EO"], "label_post"].to_numpy()
rr["nonFX_eq"] = tab["flags"].loc[tab["EO"], "flag"].to_numpy()
rr["flag_reason"] = tab["flags"].loc[tab["EO"], "reason"].to_numpy()
rr["fx_beta_usdthb"] = tab["fx"].loc[tab["EO"]].to_numpy()
rr["act_1mR2"] = tab["act"].loc[tab["EO"]].to_numpy()
rr["median_log_aum_train"] = tab["aumlog"].reindex(tab["EO"]).to_numpy()
save(rr, "regions.csv")
log("เขียน regions.csv (ก่อน fit)")
ports = {"full": fm_.make_ports(base, pol, tab), "A": fm_.make_ports(HA, pol, tab), "B": fm_.make_ports(HB, pol, tab)}
gp = pd.concat([pd.DataFrame({"port_set": k, "FundCode": v.index, "port": v.to_numpy()}) for k, v in ports.items()], ignore_index=True)
save(gp, "grs_ports.csv")
log("เขียน grs_ports.csv (ก่อน fit) · จำนวนพอร์ต " + json.dumps({k: int(v.nunique()) for k, v in ports.items()}))
save(halves, "halves.csv")
log("เขียน halves.csv (ก่อน fit)")

# ───────────────────────── 2) สร้างรูปแบบ ─────────────────────────
log("เริ่ม fit/สร้าง factor รูปแบบ ① ② ③ ④")
l1 = fm_.build_line1(R, bal, base, n_perm=500, seed=SEED)
forms = {}
forms.update(l1["forms"])
chars_full = fm_.make_chars(R, base, pol, tab)
forms.update(fm_.build_line2_forms(R, chars_full, loo=True, min_n=5))
l3 = fm_.build_line3(F)
forms.update(l3)
l4 = fm_.build_line4(R, l3["3a"].plain, bal)
forms["4a"] = l4["form"]
forms = {k: forms[k] for k in FORMS}
nf = l1["nf"]
log(f"k ของ ①a: {nf} · k*={l1['k']} (auto {l1['k_auto']}) · EM iter={l1['parts']['em_iter']} converged={l1['parts']['em_conv']} · k_res ④a={l4['rp']['k_res']}")
nfrows = [dict(kind="criterion", name=k, value=v) for k, v in nf.items()]
nfrows += [dict(kind="criterion", name="k_star", value=l1["k"]), dict(kind="criterion", name="k_res_4a_IC_p2", value=l4["rp"]["k_res"]),
           dict(kind="criterion", name="EM_iterations_1c", value=l1["parts"]["em_iter"])]
for i, v in enumerate(l1["eig"][:15]):
    nfrows.append(dict(kind="eigenvalue_corr_1a", name=i + 1, value=float(v)))
for i, v in enumerate(l4["rp"]["eig"][:8]):
    nfrows.append(dict(kind="eigenvalue_resid_4a", name=i + 1, value=float(v)))
save(pd.DataFrame(nfrows), "nfactors.csv")
if nf["ED"] is None:
    log("ED ไม่ลู่เข้า — ไม่นับในมัธยฐาน")
facs = pd.concat({k: v.plain for k, v in forms.items()}, axis=1)
facs.columns = [f"{a}__{b}" for a, b in facs.columns]
facs.to_parquet(OUT / "factors_S003_weekly.parquet")

# half providers (② split-half: factor จากครึ่งหนึ่ง ไม่ LOO · min_n=3)
halfprov = {}
for h, mem in (("A", HA), ("B", HB)):
    ch = fm_.make_chars(R, mem, pol, tab)
    halfprov[h] = {"2" + v: ff.build_line2(R, ch, v, loo=False, min_n=3) for v in ("a", "b", "c")}

# ───────────────────────── 3) regression รายกอง ─────────────────────────
POOL = sorted(set(EVAL52) | set(FULL))
polP = pol.loc[POOL].to_numpy()
inset = {n: np.isin(POOL, l) for n, l in [("EVAL", EVAL), ("EVAL52", EVAL52), ("FULL", FULL), ("E67", E67), ("EVAL_in", EVAL_in), ("EVAL_out", EVAL_out)]}
divP = (U.loc[POOL, "div_flag"] == "Y").to_numpy()
fits, r2oos = {}, {}
for nm, f in forms.items():
    mk = window_mask(idx, f.window)
    mo = 78 if f.window == "train_c" else 52
    fits[nm] = rg.fit_funds(R, f.provider, mk, mo, funds=POOL)
    r2oos[nm] = rg.oos_r2_funds(R, f.provider, fits[nm], mte)
log("fit รายกองครบ 10 รูปแบบ")
# ตัวเทียบจับคู่ของ ②c (ภาคผนวก · ข้อ 19): ②b และ ③a บน train_c ชุดกองเดียวกัน
matched = {}
for nm in ("2b", "3a"):
    k = nm + "@train_c"
    matched[k] = rg.fit_funds(R, forms[nm].provider, mtrc, 78, funds=POOL)
    r2oos[k] = rg.oos_r2_funds(R, forms[nm].provider, matched[k], mte)
fits.update(matched)
miss_c = [c for c in EVAL if not fits["2c"].ok[POOL.index(c)]]
log(f"EVAL ที่ fit ②c ไม่ได้ (n<78 ใน train_c): {len(miss_c)}")

rows = []
for nm in list(forms) + list(matched):
    base_nm = nm.split("@")[0]
    for sname in ("EVAL", "EVAL52", "FULL", "E67", "EVAL_in", "EVAL_out"):
        d = sc.score_model(fits[nm], r2oos[nm], polP, subset=inset[sname], k=None, div_flag=divP)
        d.insert(0, "set", sname)
        d.insert(0, "form", nm)
        d["K"] = fits[nm].K
        d["p"] = 2 * fits[nm].K + 1
        d["provisional"] = PROV[base_nm] + (" · ตัวเทียบจับคู่ train_c (ข้อ 19)" if "@" in nm else "")
        rows.append(d)
SCORE = pd.concat(rows, ignore_index=True)
# ΔBIC median เทียบ ③a (EVAL · กองเดียวกัน) และรูปแบบที่เล็กกว่าในสายเดียวกัน
def dbic(a, b, setname="EVAL"):
    m = inset[setname] & fits[a].ok & fits[b].ok
    return {g: float(np.nanmedian((fits[a].bic - fits[b].bic)[m & ((polP == g) if g != "ALL" else True)])) if (m & ((polP == g) if g != "ALL" else True)).sum() else np.nan for g in ("E", "F", "O", "ALL")}
dref = {"2c": "3a@train_c"}
for i, r in SCORE.iterrows():
    if r["set"] != "EVAL":
        continue
    refname = "3a@train_c" if r["form"] in ("2c", "2b@train_c", "3a@train_c") and r["form"] != "3a@train_c" else "3a"
    if r["form"] == "3a@train_c":
        refname = "3a@train_c"
    SCORE.loc[i, "dBIC_med_vs_3a"] = dbic(r["form"], refname)[r["policy"]]
smaller = {"2b": "2a", "2c": "2b@train_c", "3b": "3a", "3c": "3b", "4a": "3a"}
for i, r in SCORE.iterrows():
    if r["set"] == "EVAL" and r["form"] in smaller:
        SCORE.loc[i, "dBIC_med_vs_smaller_in_line"] = dbic("2c" if False else r["form"], smaller[r["form"]])[r["policy"]]
save(SCORE, "scorecard.csv")

# fund_level.csv
fl_rows = []
for nm in list(forms) + list(matched):
    ft = fits[nm]
    d = pd.DataFrame(dict(form=nm, FundCode=POOL, policy=polP, in_EVAL=inset["EVAL"], in_E67=inset["E67"], in_PCA_sample=np.isin(POOL, bal),
                          alpha=ft.alpha, t_alpha_hac=ft.t_alpha_hac, t_alpha_ols=ft.t_alpha_ols, adj_r2=ft.adj_r2, r2=ft.r2,
                          bic=ft.bic, n_rows=ft.n, r2_oos=r2oos[nm]))
    fl_rows.append(d[d.in_EVAL | inset["EVAL52"] | inset["FULL"]])
save(pd.concat(fl_rows, ignore_index=True), "fund_level.csv")
log("เขียน scorecard.csv, fund_level.csv")

# BH (FDR 10%) บน t_HAC ของ α (train · EVAL) → p สองข้าง (normal)
from scipy import stats as _st  # noqa: E402
bhr = []
for nm in forms:
    m = inset["EVAL"] & fits[nm].ok
    t = fits[nm].t_alpha_hac[m]
    rej, adj = ts.bh(2 * _st.norm.sf(np.abs(t)), 0.10)
    pg = polP[m]
    d = dict(form=nm, n_EVAL=int(m.sum()), n_reject_ALL=int(rej.sum()))
    for g in "EFO":
        d["n_reject_" + g] = int(rej[pg == g].sum())
        d["n_" + g] = int((pg == g).sum())
    bhr.append(d)
BH = pd.DataFrame(bhr)

# bootstrap CI (EVAL)
ev_idx = np.where(inset["EVAL"])[0]
cols = [("adjr2_train", nm) for nm in forms] + [("r2_oos", nm) for nm in forms] + [("gap_train_minus_oos", nm) for nm in forms]
Smat = np.column_stack([fits[nm].adj_r2[ev_idx] for nm in forms] + [r2oos[nm][ev_idx] for nm in forms] +
                       [fits[nm].r2[ev_idx] - r2oos[nm][ev_idx] for nm in forms])
ix3a = len(forms) + FORMS.index("3a")
pairs = [(len(forms) + i, ix3a) for i in range(len(forms))]
bs = ts.bootstrap_median(Smat, polP[ev_idx], pairs=pairs, n_boot=2000, seed=SEED)
brow = []
for g in ("E", "F", "O", "ALL"):
    ci, dci = bs[g]
    mg = (polP[ev_idx] == g) if g != "ALL" else np.ones(len(ev_idx), bool)
    for j, (stat, nm) in enumerate(cols):
        brow.append(dict(group=g, form=nm, stat=stat, median=float(np.nanmedian(Smat[mg, j])), lo=ci[0, j], hi=ci[1, j]))
    for pi, (a, b) in enumerate(pairs):
        nm = FORMS[a - len(forms)]
        brow.append(dict(group=g, form=nm, stat="d_r2oos_vs_3a(paired)", median=float(np.nanmedian(Smat[mg, a]) - np.nanmedian(Smat[mg, b])),
                         lo=dci[0, pi], hi=dci[1, pi]))
BOOT = pd.DataFrame(brow)
BOOT["note"] = np.where(BOOT.form == "2c", "ไม่เทียบตรง (ข้อ 8)", "")
save(BOOT, "bootstrap.csv")
log("bootstrap 2000 รอบ เสร็จ")

# ───────────────────────── 4) GRS ─────────────────────────
def port_returns(members_ports):
    cols = sorted(members_ports.unique())
    X = np.full((len(idx), len(cols)), np.nan)
    C = np.zeros((len(idx), len(cols)), int)
    for j, p in enumerate(cols):
        mem = list(members_ports.index[members_ports == p])
        V = R[mem].to_numpy(float)
        C[:, j] = np.isfinite(V).sum(axis=1)
        with np.errstate(invalid="ignore"):
            X[:, j] = np.where(C[:, j] > 0, np.nansum(V, axis=1) / np.maximum(C[:, j], 1), np.nan)
    return cols, X, C


PR = {k: port_returns(v) for k, v in ports.items()}
base_rows = {"train": mtr & (POS >= 1), "train_c": mtrc & (POS >= 1), "test": mte & (POS >= 1)}
dropped, grs_rows, split_rows = [], [], []
dropset = {}
for k, (cols_, X, C) in PR.items():
    for w, m in base_rows.items():
        bad = (C < 3).any(axis=1) & m
        dropset[(k, w)] = bad
        for t in np.where(bad)[0]:
            dropped.append(dict(port_set=k, window=w, date=str(idx[t].date()), ports_lt3=";".join(c for c, v in zip(cols_, C[t]) if v < 3),
                                min_count=int(C[t].min())))
DROP = pd.DataFrame(dropped, columns=["port_set", "window", "date", "ports_lt3", "min_count"])
save(DROP, "grs_dropped_weeks.csv")


def run_grs(Xdes, port_set, window, label):
    cols_, X, C = PR[port_set]
    m = base_rows[window]
    bad = dropset[(port_set, window)]
    fin_f = np.isfinite(Xdes).all(axis=1)
    use = m & ~bad & fin_f & np.isfinite(X).all(axis=1)
    n_drop_ports = int((m & bad).sum())
    n_drop_factor = int((m & ~bad & ~fin_f).sum())
    d = dict(label=label, port_set=port_set, window=window, N_ports=len(cols_), T_used=int(use.sum()), n_drop_ports=n_drop_ports,
             n_drop_factor_nan=n_drop_factor)
    if use.sum() - len(cols_) - Xdes.shape[1] <= 10:
        d.update(F=np.nan, p=np.nan, L=Xdes.shape[1], dof2=int(use.sum() - len(cols_) - Xdes.shape[1]), mean_abs_alpha_pct=np.nan,
                 note="N/A (T ไม่พอ)")
        return d
    g = ts.grs(X[use], Xdes[use])
    d.update(F=g["F"], p=g["p"], L=g["L"], dof2=g["dof2"], mean_abs_alpha_pct=float(np.mean(np.abs(g["alpha"])) * 5200), note="")
    return d


for nm, f in forms.items():
    if nm[0] == "2":
        continue
    Xd = rg.lag_stack(f.plain.to_numpy(float))
    for ps in ("full", "A", "B"):
        for w in ("train_c" if f.window == "train_c" else "train", "test"):
            r = run_grs(Xd, ps, w, nm)
            r["window"] = "train" if w == "train_c" else w
            r["tag"] = "พอร์ตทดสอบซ้อนกับ sample PCA" if nm[0] in "14" and ps == "full" else ""
            r["role"] = "main" if ps == "full" else "appendix(half-port)"
            r["provisional"] = PROV[nm]
            grs_rows.append(r)
for direction, (src, dst) in {"A->B": ("A", "B"), "B->A": ("B", "A")}.items():
    for v in ("2a", "2b", "2c"):
        Xd = rg.lag_stack(halfprov[src][v].plain().to_numpy(float))
        for w in ("train_c" if v == "2c" else "train", "test"):
            r = run_grs(Xd, dst, w, v)
            r["window"] = "train" if w == "train_c" else w
            r.update(direction=direction, tag="peer-relative (split-half) — benchmark เป็นกองกลุ่มเดียวกันอีกครึ่ง · พอร์ต EW กว้างมี α≈0 เชิงกล",
                     provisional=PROV[v] + " · 13")
            split_rows.append(r)
GRS = pd.DataFrame(grs_rows)
GS = pd.DataFrame(split_rows)
concl = []
for (v, w), d in GS.groupby(["label", "window"]):
    rj = (d.p < 0.05).tolist()
    concl.append(dict(label=v, window=w, conclusion="ปฏิเสธ" if all(rj) else ("ไม่ปฏิเสธ" if not any(rj) else "ไม่สรุป"),
                      p_A2B=float(d[d.direction == "A->B"].p.iloc[0]), p_B2A=float(d[d.direction == "B->A"].p.iloc[0])))
GSC = pd.DataFrame(concl)
GS = GS.merge(GSC[["label", "window", "conclusion"]], on=["label", "window"], how="left")
save(GRS, "grs.csv")
save(GS, "grs_split.csv")
# ── 9b (N1.3): α ระดับพอร์ต ฝั่ง FX-beta ต่ำ vs สูง ภายในภูมิภาคเดียวกัน · train · ③a และ ④a (เพิ่มหลังรีวิวผล) ──
hrows = []
cols_f, Xf, Cf = PR["full"]
for nm in ("3a", "4a"):
    Xd = rg.lag_stack(forms[nm].plain.to_numpy(float))
    use = base_rows["train"] & np.isfinite(Xd).all(axis=1) & np.isfinite(Xf).all(axis=1)
    al = sc.port_alpha(Xf[use], Xd[use]) * 5200
    am = dict(zip(cols_f, al))
    regs = sorted({c[:-len("_hedged")] for c in cols_f if c.endswith("_hedged")})
    for r_ in regs:
        lo, hi = am[r_ + "_hedged"], am[r_ + "_unhedged"]
        hrows.append(dict(form=nm, region_port=r_, alpha_pct_yr_low_FXbeta=lo, alpha_pct_yr_high_FXbeta=hi, diff=lo - hi, abs_diff=abs(lo - hi),
                          diff_lt_1pct=bool(abs(lo - hi) < 1.0), T_rows=int(use.sum()), expectation_9b="ต่างกัน < 1%/ปี"))
N1H = pd.DataFrame(hrows)
save(N1H, "n1_hedge_alpha.csv")
log("GRS เสร็จ")

# ───────────────────────── 5) Pesaran–Yamagata ─────────────────────────
def py_for(nm, window, funds, hac=False):
    f = forms[nm]
    mk0 = base_rows[window]
    mk = mk0 & np.isfinite(f.provider.design(funds[0])).all(axis=1)  # แถวที่ factor มีค่า (④a: g แถวแรก NaN → lag แถวที่ 2 ตก)
    fit = rg.fit_funds(R, f.provider, mk, 50, funds=funds)
    full = fit.n == mk.sum()
    keepi = np.where(fit.ok & full)[0]
    out = []
    if len(keepi) == 0:
        return out
    codes = [fit.codes[i] for i in keepi]
    resid = fit.resid[mk][:, keepi]
    t = (fit.t_alpha_hac if hac else fit.t_alpha_ols)[keepi]
    pg = pol[codes].to_numpy()
    m = 2 * f.K
    for sub in ("ALL", "E", "F", "O"):
        s = np.ones(len(codes), bool) if sub == "ALL" else (pg == sub)
        if s.sum() < 6:
            continue
        r = ts.pesaran_yamagata(t[s], resid[:, s], int(mk.sum()), m)
        note = ""
        if np.isfinite(r["Nrho2"]) and r["Nrho2"] > 1:
            note = "(N−1)ρ̄²>1: เงื่อนไข cross-correlation อ่อนน่าจะไม่เป็นจริง — ตีความ PY ระวัง"
        if sub in ("F", "O"):
            note = (note + " · n เล็ก/power ต่ำ").strip(" ·")
        out.append(dict(form=nm, window="train" if window == "train_c" else window, subset=sub, J=r["J"], p=r["p"], N=r["N"], T=r["T"], v=r["v"],
                        rho2=r["rho2"], Nrho2=r["Nrho2"], m=m, t_type="HAC (sensitivity)" if hac else "OLS (หลัก)", kind="PY", note=note,
                        provisional=PROV[nm]))
    return out


pyrows = []
for nm in FORMS:
    wtr = "train_c" if nm == "2c" else "train"
    ftr = PYTC if nm == "2c" else PYTR
    for hac in (False, True):
        pyrows += py_for(nm, wtr, ftr, hac)
        pyrows += py_for(nm, "test", PYTE, hac)
    # ฉบับขยาย v_i (ภาคผนวก)
    for w, fl_ in ((wtr, EVAL), ("test", EVAL)):
        mk = base_rows[w]
        fit = rg.fit_funds(R, forms[nm].provider, mk, 50, funds=fl_)
        ok = fit.ok
        e = fit.resid[mk][:, ok]
        r = ts.py_extended(fit.t_alpha_ols[ok], fit.n[ok], e, 2 * forms[nm].K)
        pyrows.append(dict(form=nm, window="train" if w == "train_c" else w, subset="ALL(EVAL)", J=r["J"], p=r["p"], N=r["N"], T=r["T"], v=np.nan,
                           rho2=r["rho2"], Nrho2=r["Nrho2"], m=2 * forms[nm].K, t_type="OLS", kind="PY_extended(ภาคผนวก · ไม่มีทฤษฎีรองรับ)",
                           note="", provisional=PROV[nm]))
PY = pd.DataFrame(pyrows)
save(PY, "py.csv")
log("PY เสร็จ")

# ───────────────────────── 6) ความเสถียร (STAB 191) ─────────────────────────
stab_pol = pol[STAB].to_numpy()
rng_b = np.random.default_rng(SEED)
srows = []
rb = 2000


def fit_stab(nm, mask, min_obs):
    return rg.fit_funds(R, forms[nm].provider, mask, min_obs, funds=STAB)


for nm in FORMS:
    f = forms[nm]
    c = nm.endswith("c") and nm[0] == "2"
    h1n, h2n = ("H1_c", "H2") if c else ("H1", "H2")
    fh1 = fit_stab(nm, window_mask(idx, h1n) & (POS >= 1), 60 if c else 104)
    fh2 = fit_stab(nm, window_mask(idx, h2n), 104)
    fo = fit_stab(nm, window_mask(idx, "odd_c" if c else "odd") & (POS >= 1), 60)
    fe = fit_stab(nm, window_mask(idx, "even_c" if c else "even") & (POS >= 1), 60)
    ffull = fit_stab(nm, window_mask(idx, "full_c" if c else "full") & (POS >= 1), 100)
    starts = [s for s in range(0, 157, 4) if (not c) or idx[s] >= pd.Timestamp("2022-01-14")]
    rolls = []
    for s in starts:
        mk = np.zeros(len(idx), bool)
        mk[s:s + 104] = True
        mk &= window_mask(idx, "full_c" if c else "full") & (POS >= 1)
        rolls.append(fit_stab(nm, mk, 78).beta)
    rolls = np.array(rolls)
    common_name = COMMON[nm[0]]
    for g in ("E", "F", "O", "ALL"):
        sel = (stab_pol == g) if g != "ALL" else np.ones(len(STAB), bool)
        b1, b2, s1, s2 = fh1.beta[sel], fh2.beta[sel], fh1.se_beta[sel], fh2.se_beta[sel]
        dd = sc.stability_disattenuated(b1, s1, b2, s2)
        ceil = sc.stability_ceiling(fo.beta[sel], fe.beta[sel])
        rmed, rmin = sc.stability_rolling(rolls[:, sel, :], ffull.beta[sel])
        for k, fn in enumerate(f.names):
            lo = hi = naf = np.nan
            if g == "E":
                ok = np.isfinite(b1[:, k]) & np.isfinite(b2[:, k]) & np.isfinite(s1[:, k]) & np.isfinite(s2[:, k])
                n = int(ok.sum())
                ii = rng_b.integers(0, n, size=(rb, n))
                B1, B2, S1, S2 = b1[ok, k][ii], b2[ok, k][ii], s1[ok, k][ii], s2[ok, k][ii]
                B1c, B2c = B1 - B1.mean(1, keepdims=True), B2 - B2.mean(1, keepdims=True)
                with np.errstate(invalid="ignore", divide="ignore"):
                    rr_ = (B1c * B2c).sum(1) / np.sqrt((B1c ** 2).sum(1) * (B2c ** 2).sum(1))
                    v1, v2 = B1.var(1, ddof=1), B2.var(1, ddof=1)
                    rel1 = (v1 - (S1 ** 2).mean(1)) / v1
                    rel2 = (v2 - (S2 ** 2).mean(1)) / v2
                    rs = rr_ / np.sqrt(rel1 * rel2)
                na = ~((rel1 >= 0.10) & (rel2 >= 0.10))
                naf = float(na.mean())
                if np.isfinite(dd["r_star"][k]):
                    if naf > 0.10:
                        lo = hi = "N/A (noise ครอบงำ)"
                    else:
                        lo, hi = np.percentile(rs[~na], [2.5, 97.5])
            srows.append(dict(form=nm, policy=g, factor=fn, is_common=(fn == common_name), n_funds=int(sel.sum()),
                              r_raw=dd["r"][k], rel_H1=dd["rel1"][k], rel_H2=dd["rel2"][k], r_star=dd["r_star"][k],
                              r_star_lo=lo, r_star_hi=hi, r_star_na_frac=naf, r_ceil=ceil[k],
                              r_over_ceil=dd["r"][k] / ceil[k] if np.isfinite(ceil[k]) and ceil[k] != 0 else np.nan,
                              roll_median=rmed[k], roll_min=rmin[k], n_rolling_windows=len(starts),
                              note=("ปนความต่างของ β ระหว่าง policy — สูงเชิงกล" if g == "ALL" else ("n เล็ก" if g in "FO" else "")) +
                                   (" · ci เงื่อนไขบน rel≥0.10" if (g == "E" and 0 < naf <= 0.10) else ""),
                              provisional=PROV[nm]))
        # MEAN
        sub = [r for r in srows if r["form"] == nm and r["policy"] == g]
        rv = np.array([r["r_raw"] for r in sub], float)
        rs_ = np.array([r["r_star"] for r in sub], float)
        srows.append(dict(form=nm, policy=g, factor="MEAN(all factors)", is_common=False, n_funds=int(sel.sum()), r_raw=np.nanmean(rv),
                          r_star=np.nanmean(rs_) if np.isfinite(rs_).any() else np.nan, r_ceil=np.nan,
                          roll_median=np.nanmean([r["roll_median"] for r in sub]), n_rolling_windows=len(starts),
                          note=f"factors ที่ใช้ได้ {int(np.isfinite(rv).sum())}/{len(rv)} (r_raw) · {int(np.isfinite(rs_).sum())}/{len(rs_)} (r*)",
                          provisional=PROV[nm]))
    log(f"stability {nm}")
STABDF = pd.DataFrame(srows)
save(STABDF, "stability.csv")

# ───────────────────────── 7) การตีความ ─────────────────────────
ref = ex.reference_set(F)
F3b = forms["3b"].plain
irows = []
for nm, f in forms.items():
    it = sc.interpret(f.plain, ref)
    it.insert(0, "form", nm)
    r2on = {}
    for c in f.plain.columns:
        d = pd.concat([f.plain[c], F3b], axis=1).dropna()
        y, X = d.iloc[:, 0].to_numpy(), np.column_stack([np.ones(len(d)), d.iloc[:, 1:].to_numpy()])
        b = np.linalg.lstsq(X, y, rcond=None)[0]
        e = y - X @ b
        r2on[c] = 1 - e @ e / ((y - y.mean()) ** 2).sum()
    it["r2_on_3b"] = it["factor"].map(r2on)
    it["direct_definition"] = nm[0] in "23"
    irows.append(it)
INTERP = pd.concat(irows, ignore_index=True)
save(INTERP, "interpret.csv")

# ───────────────────────── 8) Spanning · lead · b1 · resid corr · VIF · H①b · k-curve ─────────────────────────
spn = []
sp_forms = ["1a", "2a", "3a", "4a"]
for a in sp_forms:
    for b in sp_forms:
        if a == b:
            continue
        r = ts.spanning(forms[a].plain, forms[b].plain, mte)
        spn.append(dict(A=a, B=b, n=r["n"], wald=r["wald"], p=r["p"], df=r["df"], alpha_mean=float(np.mean(r["alpha"])), r2_mean=float(np.mean(r["r2"])),
                        note="2a ใช้ APB แบบไม่ LOO (factor ชุดเดียว)" if "2a" in (a, b) else "", provisional="20"))
SPAN = pd.DataFrame(spn)
save(SPAN, "spanning.csv")
# lead diagnostic ③a
F3a = forms["3a"].plain
K3 = F3a.shape[1]
Dl = rg.lag_stack(F3a.to_numpy(float))
lead = np.vstack([F3a.to_numpy(float)[1:], np.full((1, K3), np.nan)])
Xall = np.hstack([Dl, lead])
leadt = []
Rv = R[EVAL].to_numpy(float)
for j, c in enumerate(EVAL):
    ok = mtr & np.isfinite(Rv[:, j]) & np.isfinite(Xall).all(axis=1)
    X = np.column_stack([np.ones(ok.sum()), Xall[ok]])
    r = rg.ols_hac(Rv[ok, j], X, 4)
    leadt.append(r["t"][1 + 2 * K3:])
leadt = np.array(leadt)
ext = [dict(item="lead_diag_3a", key=F3a.columns[k], value=float((np.abs(leadt[:, k]) > 2).mean())) for k in range(K3)]
ext.append(dict(item="lead_diag_3a", key="any_factor", value=float((np.abs(leadt) > 2).any(axis=1).mean())))
# Dimson b1 share
for nm in forms:
    ft = fits[nm]
    m = inset["EVAL"] & ft.ok
    for k, fn in enumerate(forms[nm].names):
        ext.append(dict(item="dimson_b1_share_abs_t_gt2", key=f"{nm}:{fn}", value=float((np.abs(ft.t_b1[m, k]) > 2).mean())))
# residual correlation ภายใน policy (train)
for nm in forms:
    f = forms[nm]
    mk = window_mask(idx, f.window) & (POS >= 1)
    ev = [c for c in EVAL if fits[nm].ok[POOL.index(c)]]
    res = pd.DataFrame(fits[nm].resid[mk][:, [POOL.index(c) for c in ev]], columns=ev)
    C = res.corr(min_periods=52).to_numpy()
    pg = pol[ev].to_numpy()
    for g in "EFO":
        s = np.where(pg == g)[0]
        sub = C[np.ix_(s, s)]
        iu = np.triu_indices(len(s), 1)
        ext.append(dict(item="mean_abs_resid_corr_within_policy", key=f"{nm}:{g}", value=float(np.nanmean(np.abs(sub[iu])))))
# H①b
cc = sc.canonical_corr(forms["1c"].plain.loc[mtr & (POS >= 0)].to_numpy(), forms["1a"].plain.loc[mtr].to_numpy())
for i, v in enumerate(cc):
    ext.append(dict(item="H1b_canonical_corr_1c_vs_1a_train", key=str(i + 1), value=float(v)))
# FX-flag diagnostics (M3)
fr = rr[rr.nonFX_eq == True]  # noqa: E712
ext.append(dict(item="nonFX_flag_count", key="total_E_flagged", value=int(len(fr))))
for rs in ("a", "b", "a+b"):
    ext.append(dict(item="nonFX_flag_count", key=f"reason={rs}", value=int((fr.flag_reason == rs).sum())))
named12 = ["ASP-EUPROP", "B-GLOB-INFRA", "DAOL-GOLD", "FCSCBSETE", "K-GINFRA-A(D)", "K-GPROP-A(A)", "KKP GINFRAEQ-H", "KT-PROPERTY-A", "MINFRA", "TGHIDIV", "TMBGINFRA", "UINFRA-N"]
for c in named12:
    st = "ไม่อยู่ในฐาน 277" if c not in set(base) else ("ติดธง " + str(rr.loc[rr.FundCode == c, "flag_reason"].iloc[0]) if bool(rr.loc[rr.FundCode == c, "nonFX_eq"].iloc[0]) else "ไม่ติดธง")
    ext.append(dict(item="named12_flag_status", key=c, value=st))
# ความสัมพันธ์ภายในชุด factor ของแต่ละรูปแบบ (ช่วงหลัก · ไม่ LOO)
for nm, f in forms.items():
    Cm = f.plain.corr().to_numpy()
    iu = np.triu_indices(f.K, 1)
    if len(iu[0]):
        j = int(np.nanargmax(np.abs(Cm[iu])))
        ext.append(dict(item="max_abs_corr_within_form", key=nm, value=f"{abs(Cm[iu][j]):.3f} ({f.names[iu[0][j]]} vs {f.names[iu[1][j]]})"))
if True:
    P2 = forms["2b"].plain
    for a_ in ("FXH",):
        ext.append(dict(item="corr_FXH_vs", key="APB_E", value=f"{P2[a_].corr(P2['APB_E']):.3f}"))
        ext.append(dict(item="corr_FXH_vs", key="USDTHB(weekly)", value=f"{P2[a_].corr(F['USDTHB']):.3f}"))
# กองที่ติดธง nonFX_eq (รายชื่อ + เหตุ + R²)
for _, r_ in rr[rr.nonFX_eq == True].iterrows():  # noqa: E712
    ext.append(dict(item="flagged_fund", key=r_.FundCode, value=f"reason={r_.flag_reason}; maxR2_8idx={r_.max_r2:.3f}; r2_gold={r_.r2_gold:.3f}; r2_tdex={r_.r2_tdex:.3f}"))
# VIF
for nm in ("3b", "3c"):
    P = forms[nm].plain
    X0 = P.loc[mtr].to_numpy()
    Xd = rg.dimson_design(P).loc[mtr & (POS >= 1)].to_numpy()
    v0, v1 = ts.vif(X0), ts.vif(Xd)
    cn = list(P.columns)
    vrows = [dict(form=nm, design="lag0", column=c, vif=float(v)) for c, v in zip(cn, v0)]
    vrows += [dict(form=nm, design="dimson_full", column=c, vif=float(v)) for c, v in zip(list(rg.dimson_design(P).columns), v1)]
    globals().setdefault("VIFROWS", []).extend(vrows)
VIF = pd.DataFrame(VIFROWS)
save(VIF, "vif.csv")
# k-curve (บรรยาย)
kc = fm_.build_line1_k(R, bal, range(1, 9))
krows = []
for k, dfk in kc.items():
    fit = rg.fit_funds(R, dfk, mtr, 52, funds=EVAL)
    o = rg.oos_r2_funds(R, dfk, fit, mte)
    for g in ("E", "F", "O", "ALL"):
        s = (pol[EVAL].to_numpy() == g) if g != "ALL" else np.ones(len(EVAL), bool)
        krows.append(dict(k=k, policy=g, n=int(s.sum()), adjr2_train_med=float(np.nanmedian(fit.adj_r2[s])), r2_oos_med=float(np.nanmedian(o[s]))))
KC = pd.DataFrame(krows)
save(KC, "k_curve.csv")
log("ส่วนเสริมเสร็จ")

# ───────────────────────── 9) รายเดือน (ตรวจซ้ำ · p ≤ 17) ─────────────────────────
midx = Rm.index
mm_tr = np.asarray(midx <= pd.Timestamp("2023-12-31"))
mm_te = np.asarray(midx >= pd.Timestamp("2024-01-31"))
ntr = Rm.loc[mm_tr].notna().sum()
nte = Rm.loc[mm_te].notna().sum()
EVAL_m = [c for c in EVAL if ntr[c] >= 24 and nte[c] >= 12]
Fm3a = ex.line3(Fm, "3a")
mf = {}
sd_bal = Rm.loc[mm_tr, bal].std(ddof=0).to_numpy()
sd_base = Rm.loc[mm_tr, base].std(ddof=0).to_numpy()
parts = l1["parts"]
for nm, Lam, sdv, cols_ in (("1a", parts["Lam_a"], sd_bal, bal), ("1b", parts["Lam_b"], None, bal), ("1c", parts["Lam_c"], sd_base, base)):
    f = factor_returns(Rm[cols_].to_numpy(float), Lam, sdv)
    df = pd.DataFrame(f, index=midx, columns=[f"PC{i + 1}" for i in range(Lam.shape[1])])
    mf[nm] = rg.CommonFactors(df)
for v in ("a", "b"):
    pv = ff.build_line2(Rm, chars_full, v, loo=True, min_n=5)
    mf["2" + v] = pv
mf["3a"] = rg.CommonFactors(Fm3a)
fitm = rg.fit_funds(Rm, Fm3a, mm_tr, 20, L=3, funds=bal)
Dm = rg.lag_stack(Fm3a.to_numpy(float))
Um = np.full((len(midx), len(bal)), np.nan)
Xb = Rm[bal].to_numpy(float)
for j in range(len(bal)):
    Um[:, j] = Xb[:, j] - Dm @ fitm.coef[j, 1:]
s_m = np.nanstd(np.where(mm_tr[:, None], fitm.resid, np.nan), axis=0, ddof=1)
gm = factor_returns(Um, l4["rp"]["W"], s_m)
if gm.shape[1] > 0:
    mf["4a"] = rg.CommonFactors(pd.concat([Fm3a, pd.DataFrame(gm, index=midx, columns=l4["g"].columns)], axis=1))
mrows = []
for nm, pv in mf.items():
    ft = rg.fit_funds(Rm, pv, mm_tr, 24, L=3, funds=EVAL_m)
    o = rg.oos_r2_funds(Rm, pv, ft, mm_te)
    pg = pol[EVAL_m].to_numpy()
    for g in ("E", "F", "O", "ALL"):
        s = (pg == g) if g != "ALL" else np.ones(len(EVAL_m), bool)
        s = s & ft.ok
        mrows.append(dict(form=nm, policy=g, n=int(s.sum()), K=pv.K, p=2 * pv.K + 1, train_rows_median=float(np.median(ft.n[s])) if s.any() else np.nan,
                          adjr2_med=float(np.nanmedian(ft.adj_r2[s])) if s.any() else np.nan, r2_oos_med=float(np.nanmedian(o[s])) if s.any() else np.nan))
MON = pd.DataFrame(mrows)
MON["note"] = "รายเดือน Dimson lag 1 เดือน · HAC L=3 · Λ จาก train รายสัปดาห์ · ②c และ ③b/③c = N/A (p>17)"
save(MON, "monthly.csv")
log("รายเดือนเสร็จ")

# ───────────────────────── 10) บันทึกเมตา + results.md ─────────────────────────
import scipy, statsmodels, sklearn  # noqa: E402
meta = dict(created=datetime.now().isoformat(timespec="seconds"), seed=SEED, data_sha256=man, lib_sha256=lib_hashes,
            versions=dict(python=platform.python_version(), numpy=np.__version__, pandas=pd.__version__, scipy=scipy.__version__,
                          statsmodels=statsmodels.__version__, sklearn=sklearn.__version__),
            runtime_sec=round(time.time() - T0, 1), spec="S002 rev1 + S003 addendum (รีวิว S003 PASS · M1–M4)")
EXT = pd.DataFrame(ext)
save(EXT, "extras.csv")

decide("ภูมิภาค/ACT: ใช้ R² (ไม่ปรับ) ของ Dimson ดัชนีเดียว", "plain R² · argmax ตามลำดับในวงเล็บ", "ถ้าใช้ adj R² ธรณี 0.30 ขยับเล็กน้อย (p เท่ากันทุกดัชนี อันดับไม่เปลี่ยน)")
decide("ดัชนีถดถอยของกอง 'อื่น'/ที่ถูกรวม", "ใช้ป้าย label_post (OTHER→ACWI) ของฐานเต็มสำหรับ FX beta/ACT; ครึ่ง A/B ใช้ค่ารายกองเดิม (ตาม M3)", "กอง Vietnam/Japan/USA ที่ถูกรวมเข้า 'อื่น' ใช้ ACWI เป็นดัชนี")
decide("ขนาดขา 30/40/30", "n_leg = floor(0.3n) (n=10→3) · เสมอ→FundCode", "ขาต่างกัน ≤1 กองต่อกลุ่ม")
decide("GRS สูตร Σ̂", "ใช้ Σ̂ MLE (หาร T) ซึ่งเทียบเท่ารูปที่ใช้ Σ dof T−L−1 คูณ T/(T−L−1) — ตรวจด้วย simulation size 5% (test 9)", "ถ้า spec หมายถึง Σ unbiased ตรงๆ F จะเล็กลงเล็กน้อย (T/(T−L−1))")
decide("GRS ฐานเต็ม 277 ของสาย ②", "ไม่คำนวณ (circular: พอร์ต EW เดียวกับ APB) — ② ใช้ split-half + PY ตาม S002 4.2(ข)", "ไม่มีตัวเลข GRS ฐานเต็มของ ② ในตาราง")
decide("EVAL52 / ชุดเต็ม", "EVAL52 = ตัดซ้ำ ≥52 แถว Dimson train และ ≥52 test · FULL = ไม่ตัดซ้ำ ใช้เกณฑ์ EVAL (≥104/≥52)", "ภาคผนวกเท่านั้น")
decide("odd/even (ข2)", "odd = สัปดาห์ลำดับ 1,3,5.. ของช่วงหลัก (pos 0,2,4..) · even = pos 1,3,.. ; ②c ตัดให้อยู่ใน full_c · แถว pos 0 ตก (ไม่มี lag)", "r^ceil เปลี่ยนเล็กน้อยถ้านิยามสลับ")
decide("EM-PCA เกณฑ์หยุด", "‖Δ‖_F/‖Z_filled‖_F < 1e-6 (spec ระบุ X_miss — ใช้ตัวส่วนเป็นเมทริกซ์ที่เติมแล้ว)", "จำนวนรอบอาจต่าง; Λ ต่างเล็กน้อยมาก")
decide("IC / ER / GR", "IC ค้นหา k=0..10 (V(k)=Σ_{j>k}λ_j/N) · ER/GR ค้นหา k=1..10 · PA 500 permutation ด้วย rng.permuted(axis=0)", "—")
decide("Onatski ED", "implement ตามขั้นตอนใน spec (จากความจำของ designer); analyst **ไม่ได้เปิดบทความ** เทียบสมการ calibration — ยังไม่ยืนยันแหล่ง", "ถ้า calibration ต่าง k_ED อาจต่าง; k* = floor(median) ได้รับผลถ้า ED เปลี่ยนค่ากลาง")
decide("PY ฉบับขยาย (ภาคผนวก)", "v_i=T_i−m−1 · ρ̂_ij จากคู่ทับกัน ≥52 · เกณฑ์ √(n_ij−m−1)|ρ|>c_p · J หารด้วย √(Var_i)ต่อกอง", "สูตรไม่มีทฤษฎีรองรับ (ตาม spec)")
decide("BH", "p สองข้างจาก N(0,1) ของ t_HAC (train, EVAL) ต่อรูปแบบ", "ถ้าใช้ t-distribution จำนวนที่ปฏิเสธอาจลดเล็กน้อย")
decide("Bootstrap CI", "สุ่มกอง EVAL ใส่คืนภายใน policy · ใช้ index ชุดเดียวกันทุกรูปแบบ · nanmedian · percentile 2.5/97.5 · gap=R²_train(ไม่ปรับ)−R²_oos", "—")
decide("Lead diagnostic", "ถดถอย ③a + lead 1 สัปดาห์ (train) · รายงานสัดส่วน |t_HAC(lead)|>2 ต่อ factor และ 'any factor'", "ตัวเลข any-factor สูงกว่ารายตัวโดยโครงสร้าง")
decide("รายเดือน", "Λ และ W จากสัปดาห์ train ใช้กับผลตอบแทนรายเดือน (σ_m รายเดือนของ train) · ②a/②b ใช้ป้ายขา/กลุ่มเดิม · ④a: β̂ รายเดือนของ ③a → u → g=W'(u/s_m)", "ตรวจซ้ำเท่านั้น")
decide("④a แถวที่ใช้", "g แถวแรก (2021-01-08) เป็น NaN เพราะไม่มี lag ของ ③a → lag ของ g ที่ 2021-01-15 ไม่มี → train ของ ④a เหลือ 154 แถว (รูปแบบอื่น 155) · PY ของ ④a ใช้ T=154 และกองที่ครบทุกแถวนั้น", "N/T ของ ④a ต่างจากรูปแบบอื่น 1 แถว")
decide("GRS ตัดสัปดาห์ (N3)", "สัปดาห์ 2021-01-08 (pos 0 · O ครึ่ง A เหลือ 4 กอง) ไม่ใช่แถวถดถอยของ Dimson (ไม่มี lag) จึงไม่ถูกนับเป็นสัปดาห์ที่ตัด → grs_dropped_weeks.csv ว่าง (ไม่มีสัปดาห์ใดในแถวที่ใช้มีพอร์ต <3 กอง)", "ถ้านับ pos 0 เป็นสัปดาห์ที่ตัด ผลไม่เปลี่ยน (แถวนั้นตกอยู่แล้ว)")
decide("หลังรีวิวผล", "เพิ่ม n1_hedge_alpha.csv, expectations_vs_results.csv และหัวข้อ 8.5/9b/หมายเหตุ ใน results.md — ไม่เปลี่ยนโมเดล/ตัวเลขเดิม (CSV เดิม sha256 เท่าเดิม)", "—")
decide("MOM", "ทบต้นจาก excess return (ไม่ใช่ gross) บนกอง E ในฐาน 277 ทั้งหมด (รวมกองมีธง nonFX_eq) · ถือ τ+1..τถัดไป", "กองมีธงอยู่ในขา MOM ตาม N4")
decide("HAC กับแถวที่ขาด", "แถวที่ผลตอบแทนกองขาดถูกตัด แล้วคำนวณ HAC เหมือนแถวติดกัน", "—")
decide("min_obs ต่อกอง", "fit: ≥52 แถว (②c ≥78) + ≥2K+3 · PY ต้องครบทุกแถวของหน้าต่าง · STAB H1/H2 ≥104 (H1_c ≥60) · rolling ≥78 · odd/even ≥60", "ตาม spec")
decide("ΔBIC เทียบ 'รูปแบบที่เล็กกว่า'", "②b vs ②a · ②c vs ②b@train_c · ③b vs ③a · ③c vs ③b · ④a vs ③a · ① ไม่มีคู่ (K เท่ากัน)", "ข้อเสนอเกณฑ์ผู้เข้ารอบข้อ 4")
decide("M2 (CI ของ r*)", "ตามข้อเสนอรีวิว: r* จุด N/A → ไม่คำนวณ CI · na_frac>0.10 → 'N/A (noise ครอบงำ)' · 0<na_frac≤0.10 → CI พร้อมป้ายเงื่อนไข", "ภาคผนวก")
decide("M1 (รายเดือน)", "รายงานจำนวนแถว train รายเดือน (median) ต่อรูปแบบใน monthly.csv (MSCI ขาดที่ 2021-01-31 ทำให้ ③a/④a เสียแถว 2021-02)", "—")
decide("M3", "FX beta/1−R² ของกองที่ถูกย้ายไปกลุ่มเรียง ACWI คำนวณด้วยดัชนีตามป้ายใน regions.csv · ในครึ่ง A/B เกณฑ์ <10 นับภายในครึ่ง · รายชื่อกองมีธง/12 กองที่ชื่อส่อ อยู่ใน extras.csv", "—")
decide("PA/ED/IC ใช้ Z ของ ①a เท่านั้น", "k* ของ ①b และ ①c = k* ของ ①a ตาม spec", "—")

# ผู้เข้ารอบ (ข้อ 7 · ตัวเลขตามข้อเสนอของ designer)
crit = []
ev = SCORE[(SCORE.set == "EVAL") & (SCORE.policy == "E") & (~SCORE.form.str.contains("@"))].set_index("form")
mx = ev.r2oos_med.drop("2c").max()
for nm in FORMS:
    r = ev.loc[nm]
    sr = STABDF[(STABDF.form == nm) & (STABDF.policy == "E") & (STABDF.factor == "MEAN(all factors)")].r_raw.iloc[0]
    dsm = r.get("dBIC_med_vs_smaller_in_line", np.nan)
    ref_ = mx if nm != "2c" else r.r2oos_med
    named = INTERP[(INTERP.form == nm) & (INTERP["rank"] == 1)]
    nm_ok = bool(forms[nm].names and (nm[0] in "23" or (named["corr"].abs() >= 0.5).all()))
    crit.append(dict(form=nm, c1_r2oos_E=r.r2oos_med, c1_threshold=0.9 * ref_, c1_pass=bool(r.r2oos_med >= 0.9 * ref_),
                     c2_gap_E=r.r2gap_med, c2_pass=bool(r.r2gap_med <= 0.15), c3_mean_r_E=sr, c3_pass=bool(sr >= 0.6),
                     c4_dBIC_vs_smaller=dsm, c4_pass=("n/a" if not np.isfinite(dsm) else bool(dsm <= 0)), c5_named_or_direct=nm_ok))
CRIT = pd.DataFrame(crit)
save(CRIT, "criteria_values.csv")

sec = []
sec.append(f"# results — S003 (S002 rev1 + addendum · รีวิว S003 PASS)\n\nรัน: {meta['created']} · seed {SEED} · runtime {meta['runtime_sec']} s · ตัวเลขทุกตัวมาจากการรันนี้ (รายงานตัวเลขอย่างเดียว ไม่ตีความ)\n"
           "ป้าย `ค่าชั่วคราว` = หมายเลขข้อใน BRIEF ที่ผลขึ้นกับ (คอลัมน์ provisional)\n")
sec.append("## 0. ตรวจก่อนรัน\n- sha256 ข้อมูล 8 ไฟล์ตรง manifest และตรง spec · sha256 ของ lib/*.py + พารามิเตอร์ อยู่ใน `run.log`/`run_meta.json`\n"
           "- test 19 ข้อ (lib/tests) ผ่านก่อนรัน (บันทึกผลใน `run.log` จากการรัน pytest แยก)\n- ขนาดชุดกองตรงตัวเลขใน spec ทุกชุด:\n\n" + md(cnt_tbl))
nfk = pd.DataFrame([nf]).T.reset_index()
nfk.columns = ["เกณฑ์", "k"]
sec.append("## 1. จำนวน factor ของสาย ① (บน Z ของ ①a · balanced 134×156)  [ค่าชั่วคราว 1,3,4,5,7]\n" + md(nfk) +
           f"\nk* = floor(median{{IC_p2, ER, ED, PA}}) = **{l1['k']}** (คำนวณอัตโนมัติ {l1['k_auto']}) · IC_p1/GR/eig รายงานใน nfactors.csv · k_res ของ ④a (IC_p2, kmax 5) = {l4['rp']['k_res']} · EM-PCA ①c: {l1['parts']['em_iter']} รอบ ลู่เข้า={l1['parts']['em_conv']}\n"
           "\nเส้น R² เทียบ k=1…8 ของ ①a (EVAL, บรรยาย):\n\n" + md(KC.pivot(index="k", columns="policy", values=["adjr2_train_med", "r2_oos_med"]).reset_index().pipe(lambda d: d.set_axis([("_".join(map(str, c)) if isinstance(c, tuple) else c).strip("_") for c in d.columns], axis=1))))
sc1 = SCORE[(SCORE.set == "EVAL") & (~SCORE.form.str.contains("@"))]
sec.append("## 2. ข้อ 1–2: R² รายกอง และ R² นอกช่วง (EVAL 207 · adj R² train; R²_oos = test 2024–2025, ไม่ fit ใหม่)\n"
           "②c = train_c 103 แถว **ไม่เทียบตรง (ค่าชั่วคราว 8, 16)** · ① ในตาราง = ใน+นอก sample PCA ปนกัน (แยกในหัวข้อ 2.2)\n\n"
           + md(sc1[["form", "policy", "n", "K", "adjr2_med", "adjr2_q25", "adjr2_q75", "r2oos_med", "r2oos_q25", "r2oos_q75", "r2gap_med", "provisional"]]))
bsE = BOOT[(BOOT.group.isin(["E", "ALL"])) & (BOOT.stat.isin(["adjr2_train", "r2_oos", "gap_train_minus_oos", "d_r2oos_vs_3a(paired)"]))]
sec.append("### 2.1 bootstrap 95% CI (2,000 รอบ · seed 20261015 · สุ่มกองใหม่ภายใน policy)\n" + md(bsE[["group", "form", "stat", "median", "lo", "hi", "note"]]))
e67 = SCORE[(SCORE.set == "E67") & (SCORE.policy == "E") & (~SCORE.form.str.contains("@"))]
sec.append("### 2.2 E67 (ตัวเทียบหลักของ ① — กอง E นอก sample PCA) · และ ① แยกใน/นอก sample\n" +
           md(e67[["form", "n", "adjr2_med", "r2oos_med", "r2gap_med"]]) + "\n① แยกใน/นอก sample (EVAL):\n\n" +
           md(SCORE[SCORE.form.isin(["1a", "1b"]) & SCORE.set.isin(["EVAL_in", "EVAL_out"])][["form", "set", "policy", "n", "adjr2_med", "r2oos_med"]]) +
           "\nF/O นอก sample: n = " + f"F {int((pol[EVAL_out] == 'F').sum())}, O {int((pol[EVAL_out] == 'O').sum())} (n ไม่พอ) · ①c: EVAL ⊂ ฐาน 277 ไม่มีกลุ่มนอก sample\n")
sc3 = SCORE[(SCORE.set == "EVAL") & (~SCORE.form.str.contains("@"))]
sec.append("## 3. ข้อ 3: pricing error\n### 3.1 |α̂| เฉลี่ย (%/ปี · train) · ② ติดป้าย **peer-relative — เทียบกับสายอื่นตรงๆ ไม่ได้ (ค่าชั่วคราว 13)** · ③c ติดป้าย **มี factor ลงทุนไม่ได้ (VIX_d, US10Y_d, TH5Y_d)**\n\n"
           + md(sc3[["form", "policy", "n", "mean_abs_alpha_pct", "signed_mean_alpha_pct", "mean_abs_alpha_nodiv_pct"]]))
gt = GRS[(GRS.port_set == "full")][["label", "window", "N_ports", "T_used", "L", "dof2", "F", "p", "mean_abs_alpha_pct", "n_drop_ports", "n_drop_factor_nan", "tag", "provisional"]]
sec.append("### 3.2 GRS บนพอร์ตฐานเต็ม 277 (≤20 พอร์ต · fit α, β ใหม่ในแต่ละช่วงบนอนุกรม factor น้ำหนัก train) — ①③④ (② ไม่คำนวณ: circular — ดูการตัดสินใจ) \n" + md(gt))
sec.append("### 3.3 GRS split-half ของ ② (ค่าชั่วคราว 13) — ป้าย peer-relative (split-half) · กติกา: ทั้งสองทิศปฏิเสธ→ปฏิเสธ · ทั้งสองไม่ปฏิเสธ→ไม่ปฏิเสธ · ทิศเดียว→ไม่สรุป\n" +
           md(GS[["label", "direction", "window", "N_ports", "T_used", "L", "dof2", "F", "p", "mean_abs_alpha_pct", "n_drop_ports", "n_drop_factor_nan", "conclusion"]]))
pyM = PY[(PY.kind == "PY") & (PY.t_type == "OLS (หลัก)")]
sec.append("### 3.4 Pesaran–Yamagata (ฉบับหลัก · ต้นฉบับ · f(N)=N · p=0.10 · ค่าชั่วคราว 14) — หลักของ ②\n" +
           md(pyM[["form", "window", "subset", "N", "T", "v", "J", "p", "rho2", "Nrho2", "note"]]))
sec.append("### 3.5 PY sensitivity (t แบบ HAC) และฉบับขยาย v_i (ภาคผนวก)\n" + md(PY[(PY.t_type == "HAC (sensitivity)") & (PY.subset == "ALL")][["form", "window", "N", "J", "p", "Nrho2"]]) + "\n" +
           md(PY[PY.kind.str.startswith("PY_extended")][["form", "window", "N", "T", "J", "p", "rho2", "Nrho2", "kind"]]))
sec.append("### 3.6 BH (FDR 10%) บน α รายกอง (train · t_HAC)\n" + md(BH))
sc4 = SCORE[(SCORE.set == "EVAL") & (SCORE.policy.isin(["E", "ALL"]))]
sec.append("## 4. ข้อ 4: ความประหยัด (BIC_i = n ln(SSR/n)+p ln n · ②c เทียบ ③a บน train_c)\n" +
           md(sc4[["form", "policy", "K", "p", "bic_med", "dBIC_med_vs_3a", "dBIC_med_vs_smaller_in_line"]]))
mt = SCORE[(SCORE.set == "EVAL") & (SCORE.form.str.contains("@")) | ((SCORE.set == "EVAL") & (SCORE.form == "2c"))]
sec.append("### 4.1 ตัวเทียบจับคู่ของ ②c (ภาคผนวก · ข้อ 19 · fit ที่ train_c 103 แถว ชุดกองเดียวกัน)\n" + md(mt[mt.policy.isin(["E", "ALL"])][["form", "policy", "n", "K", "adjr2_med", "r2oos_med", "bic_med", "dBIC_med_vs_3a"]]))
st = STABDF[(STABDF.policy.isin(["E", "F", "O"])) & (STABDF.factor == "MEAN(all factors)")]
sec.append("## 5. ข้อ 5: ความเสถียร (STAB 191 ทุกรูปแบบ · ค่าชั่วคราว 15; ②c H1_c ค่าชั่วคราว 16) — r ดิบ แยก policy (เกณฑ์) \n" +
           md(st[["form", "policy", "n_funds", "r_raw", "r_star", "roll_median", "note"]]) +
           "\n### 5.1 รายละเอียดต่อ factor (E)\n" + md(STABDF[(STABDF.policy == "E") & (STABDF.factor != "MEAN(all factors)")][["form", "factor", "is_common", "r_raw", "rel_H1", "rel_H2", "r_star", "r_star_lo", "r_star_hi", "r_star_na_frac", "r_ceil", "r_over_ceil", "roll_median", "roll_min", "n_rolling_windows"]], 3) +
           "\n(ALL, F, O ต่อ factor อยู่ใน stability.csv · ALL ปนความต่างของ β ระหว่าง policy — สูงเชิงกล)\n")
top1 = INTERP[INTERP["rank"] == 1]
sec.append("## 6. ข้อ 6: ตีความได้ (top-1 |corr| กับชุดอ้างอิง I · ≥0.7 '≈' · 0.5–0.7 'คล้าย' · <0.5 'ไม่มีชื่อ') — ดู top-3 ใน interpret.csv\n" +
           md(top1[["form", "factor", "ref", "corr", "label", "r2_on_3b"]], 2))
sec.append("## 7. ภาคผนวกเพิ่มเติม\n### 7.1 EVAL52 / FULL (E, ALL)\n" +
           md(SCORE[SCORE.set.isin(["EVAL52", "FULL"]) & SCORE.policy.isin(["E", "ALL"]) & (~SCORE.form.str.contains("@"))][["form", "set", "policy", "n", "adjr2_med", "r2oos_med", "mean_abs_alpha_pct"]]) +
           "\n### 7.2 GRS ของ ①③④ บนพอร์ตครึ่ง A/B (ภาคผนวก)\n" + md(GRS[GRS.port_set != "full"][["label", "port_set", "window", "N_ports", "T_used", "F", "p", "tag"]]) +
           "\n### 7.3 Spanning (test · HAC · Wald joint α=0)\n" + md(SPAN) +
           "\n### 7.4 ตัวเสริม (lead · Dimson b1 · resid corr · H①b · ธง)\n" + md(EXT[EXT.item.isin(["lead_diag_3a", "H1b_canonical_corr_1c_vs_1a_train", "nonFX_flag_count"])]) +
           "\n(ที่เหลือใน extras.csv)\n### 7.5 VIF (ป้อน L3 · เชิงบรรยาย)\n" + md(VIF.groupby(["form", "design"]).vif.agg(["min", "median", "max"]).reset_index()) +
           "\n### 7.6 ตรวจซ้ำรายเดือน (p ≤ 17 · M1: train_rows_median)\n" + md(MON[MON.policy.isin(["E", "ALL"])].drop(columns=["note"])) + "\n" + MON.note.iloc[0] + "\n"
           f"\n### 7.7 GRS: สัปดาห์ที่ถูกตัด\n{len(DROP)} แถวใน grs_dropped_weeks.csv · สรุป: \n\n" +
           md(DROP.groupby(["port_set", "window"]).size().rename("n_weeks").reset_index()))
reg_sum = rr.groupby(["policy", "label_post"]).size().rename("n").reset_index()
sec.append("### 7.8 ภูมิภาค/ธง (ก่อน fit) \n" + md(reg_sum) + "\n" + md(EXT[EXT.item == "nonFX_flag_count"]))
sec.append("## 8. ค่าตัวเลขของเกณฑ์ผู้เข้ารอบ (ข้อเสนอ designer · S002 ข้อ 7 + S003 N2 · **ผู้ใช้เลือกที่ gate L1**; แสดงค่าที่คำนวณ ไม่ใช่การตัดสิน)\n" + md(CRIT))

def _g(f_, pol_="E", set_="EVAL", col="adjr2_med"):
    return float(SCORE[(SCORE.form == f_) & (SCORE.policy == pol_) & (SCORE.set == set_)][col].iloc[0])


exp = []
def ex_(n, claim, verdict, num):
    exp.append(dict(ข้อ=n, ความคาดหมาย=claim, ผล=verdict, ตัวเลข=num))


ref_ = ex.reference_set(F)
pc1c = float(forms["1a"].plain["PC1"].corr(ref_["MSCI_ACWI"]))
ex_("8.1", "k* ของ ①a = 3–5 · ER มักให้ 1 · PA ให้มากสุด · PC1 |corr|>0.8 กับ ACWI−rf", "ตรงบางส่วน",
    f"k*={l1['k']} (ตรง) · ER={nf['ER']} (ตรง) · PA={nf['PA']} แต่ IC_p2={nf['IC_p2']} (ชน kmax) มากกว่า PA (ไม่ตรง) · corr(PC1, ACWI−rf)={pc1c:.2f} ({'ตรง' if abs(pc1c) > 0.8 else 'ไม่ตรง'})")
ex_("8.2", "adj R² train (E): ①≈0.70–0.85 > ③b≈0.65–0.80 > ③a≈0.55–0.75 · ②a≈③a · ส่วนต่าง ①−③ ใน R²_oos แคบกว่า train", "ตรงบางส่วน",
    f"①a {_g('1a'):.3f} (ตรง) · ③b {_g('3b'):.3f} (ต่ำกว่าช่วง) · ③a {_g('3a'):.3f} (ต่ำกว่าช่วง) · ②a {_g('2a'):.3f} vs ③a {_g('3a'):.3f} (ไม่ใกล้) · ลำดับ ①>③b>③a ตรง · ①a−③a: train {_g('1a')-_g('3a'):.3f}, oos {_g('1a',col='r2oos_med')-_g('3a',col='r2oos_med'):.3f} (ไม่แคบลง)")
ex_("8.3", "กอง F: median R² 0.2–0.5 ทุกรูปแบบ · ③b ดีขึ้นจาก ③a ชัดสุด · APB_F ช่วย F มากกว่า ③a", "ไม่ตรง (ช่วง) / ตรง (ลำดับ)",
    f"F adj R²: ①a {_g('1a','F'):.3f} ②a {_g('2a','F'):.3f} ③a {_g('3a','F'):.3f} ③b {_g('3b','F'):.3f} ④a {_g('4a','F'):.3f} (สูงกว่า 0.5 ในรูปแบบส่วนใหญ่) · ③b−③a = {_g('3b','F')-_g('3a','F'):.3f} · ②a F {_g('2a','F'):.3f} > ③a {_g('3a','F'):.3f}")
btw = [nm for nm in FORMS if min(_g(nm, 'E'), _g(nm, 'F')) <= _g(nm, 'O') <= max(_g(nm, 'E'), _g(nm, 'F'))]
ex_("8.4", "กอง O อยู่ระหว่าง E กับ F", "ไม่ตรงเป็นส่วนใหญ่", f"รูปแบบที่ O อยู่ระหว่าง E–F (adj R² train): {btw if btw else 'ไม่มี'} จาก 10 · ①a: E {_g('1a'):.3f} F {_g('1a','F'):.3f} O {_g('1a','O'):.3f}")
ex_("8.5", "③c train R² สูงสุดในสาย ③ · BIC แย่กว่า ③b · R²_oos ไม่ดีกว่า ③b", "ตรง",
    f"adj R² ③c {_g('3c'):.3f} > ③b {_g('3b'):.3f} · ΔBIC ③c−③b (E) {float(SCORE[(SCORE.form=='3c')&(SCORE.policy=='E')&(SCORE.set=='EVAL')].dBIC_med_vs_smaller_in_line.iloc[0]):.1f} (>0 = แย่กว่า) · R²_oos ③c {_g('3c',col='r2oos_med'):.3f} < ③b {_g('3b',col='r2oos_med'):.3f}")
fxc = float(forms["2b"].plain["FXH"].corr(F["USDTHB"]))
dinc = _g("2c") - _g("2b@train_c")
ex_("8.6", "FXH corr ติดลบชัดกับ USDTHB · ②c เทียบ ②b บน train_c: MOM+SIZE+ACT เพิ่ม adj R² (E) < 0.01", "ตรง (FXH) / ไม่ตรง (ส่วนเพิ่ม)",
    f"corr(FXH, USDTHB)={fxc:.3f} (ตรง แต่ใกล้เส้น −0.5; corr กับ APB_E = 0.80) · ②c {_g('2c'):.3f} − ②b@train_c {_g('2b@train_c'):.3f} = +{dinc:.3f} (ไม่ตรง)")
cc_ = [float(x) for x in cc]
ins, oo = _g("1a", "E", "EVAL_in"), _g("1a", "E", "E67")
ex_("8.7", "①c≈①a (canonical corr ทุกคู่ > 0.9) · ①a: ใน sample สูงกว่า E67 ≈ 0.02–0.05", "ไม่ตรงบางส่วน",
    f"canonical corr = {[round(x, 3) for x in cc_]} (คู่ที่ 4 = {cc_[3]:.3f} < 0.9) · adj R² ①a ใน sample (E) {ins:.3f} vs E67 {oo:.3f} ต่าง {ins-oo:+.3f}")
g_ = l4["g"]["RPC1"]
cands = {"ΔUSDTHB": float(g_.corr(F["USDTHB"])), "FXH": float(g_.corr(forms["2b"].plain["FXH"])), "MSCI_ASIA_EX_JAPAN": float(g_.corr(ref_["MSCI_ASIA_EX_JAPAN"])),
         "MSCI_CHINA_ALL_SHARES": float(g_.corr(ref_["MSCI_CHINA_ALL_SHARES"]))}
ex_("8.8", "④a: k_res = 1–3 · residual PC1 สัมพันธ์ (|corr|≥0.5) กับ ΔUSDTHB / FXH / MSCI เอเชีย-จีน", "ไม่ตรง (k_res) / " + ("ตรง" if max(abs(v) for v in cands.values()) >= 0.5 else "ไม่ตรง") + " (PC1)",
    f"**k_res = {l4['rp']['k_res']} = kmax 5 (ชนเพดาน — IC_p2 ไม่หยุดเอง)** · corr ของ residual PC1: " + ", ".join(f"{k}={v:.2f}" for k, v in cands.items()))
gt_ = GRS[(GRS.port_set == "full") & (GRS.window == "test")]
pt_ = PY[(PY.kind == "PY") & (PY.t_type == "OLS (หลัก)") & (PY.window == "test") & (PY.subset == "ALL")]
nrej = int((gt_.p < 0.05).sum())
ex_("8.9", "GRS (test) ปฏิเสธ α=0 ที่ 5% เกือบทุกรูปแบบ รวม ④a และ ② split-half · PY ปฏิเสธเช่นกัน · (N−1)ρ̄²>1 ใน ③a, ②a", "**ไม่ตรง**",
    f"GRS test ฐาน 277: ปฏิเสธ {nrej}/{len(gt_)} รูปแบบ (p ต่ำสุด {gt_.p.min():.3f}) · ② split-half: ไม่ปฏิเสธ/ไม่สรุป — ดูตาราง 3.3 · PY test (ALL): ปฏิเสธที่ 5% {int((pt_.p < 0.05).sum())}/{len(pt_)} ({', '.join(pt_[pt_.p < 0.05].form)}) · (N−1)ρ̄²: ③a {float(pt_[pt_.form=='3a'].Nrho2.iloc[0]):.1f}, ②a {float(pt_[pt_.form=='2a'].Nrho2.iloc[0]):.1f} (ตรง)")
n9 = N1H[N1H.form == "3a"]
ex_("9b", "③a: signed α̂ ของพอร์ตฝั่ง FX-beta ต่ำ กับ สูง (ภูมิภาคเดียวกัน · train) ต่างกัน < 1%/ปี", "**ไม่ตรง**",
    f"ต่างกัน < 1%/ปี: {int(n9.diff_lt_1pct.sum())}/{len(n9)} ภูมิภาค · |ส่วนต่าง| ช่วง {n9.abs_diff.min():.1f}–{n9.abs_diff.max():.1f} %/ปี (ตาราง 9b ด้านล่าง)")
ccom = {nm: STABDF[(STABDF.form == nm) & (STABDF.policy == "E") & (STABDF.is_common)].r_raw.iloc[0] for nm in FORMS}
ls_ = STABDF[(STABDF.policy == "E") & STABDF.factor.isin(["FXH", "MOM", "SIZE", "ACT"])][["form", "factor", "r_raw"]]
pf = STABDF[(STABDF.policy == "E") & (~STABDF.factor.str.startswith("MEAN"))]
frac = float(((pf.r_star > pf.r_raw) & pf.r_star.notna()).sum() / pf.r_star.notna().sum())
ex_("8.10", "factor ร่วม r ดิบ (E) > 0.8 · long–short r ดิบ < 0.5 · r* > r ดิบ ทุก factor", "ตรงบางส่วน",
    "factor ร่วม: " + ", ".join(f"{k} {v:.2f}" for k, v in ccom.items()) + f" (>0.8: {[k for k, v in ccom.items() if v > 0.8]}) · long–short: " + ", ".join(f"{r.form}:{r.factor} {r.r_raw:.2f}" for r in ls_.itertuples()) + f" · r*>r ในสัดส่วน {frac:.2f} ของ factor ที่ r* ไม่ N/A (ทุก factor ไม่ได้)")
lead_any = float(EXT[(EXT.item == "lead_diag_3a") & (EXT.key == "any_factor")].value.iloc[0])
lead_max = float(EXT[(EXT.item == "lead_diag_3a") & (EXT.key != "any_factor")].value.max())
ex_("8.11", "lead diagnostic < 10% ของกองมี |t_lead|>2", "ตรง (รายตัว)", f"รายตัวสูงสุด {lead_max:.3f} · any-factor {lead_any:.3f}")
EXPDF = pd.DataFrame(exp)
save(EXPDF, "expectations_vs_results.csv")
sec.append("## 8.5 เทียบผลกับความคาดหมายล่วงหน้า (S002 ข้อ 8 + S003 ข้อ 9b) — ตัวเลขจากการรันนี้\n" + md(EXPDF) +
           "\n**ข้อที่ไม่ตรง:** 8.2 (R² ของ ③a/③b ต่ำกว่าช่วงที่คาด) · 8.3 (R² กอง F สูงกว่าช่วง) · 8.4 (O ไม่อยู่ระหว่าง E–F) · 8.6 (ส่วนเพิ่มของ MOM+SIZE+ACT) · 8.7 (canonical corr คู่ที่ 4) · **8.8 (k_res = 5 ชน kmax)** · **8.9 (GRS ไม่ปฏิเสธ)** · **9b**\n")
sec.append("### 9b: α ระดับพอร์ต GRS (ฐาน 277 · train · %/ปี) ฝั่ง FX-beta ต่ำ (hedge มากกว่า) vs สูง ภายในภูมิภาคเดียวกัน\n"
           "คำนวณจาก α̂ ของ OLS บน [1, Dimson ของ ③a หรือ ④a] ต่อพอร์ตใน grs_ports.csv (ชุด full) · **ไม่ตรงความคาดหมาย 9b** · ใช้ติดเป็นข้อจำกัดของ ③/④a: α ข้อ 3 ของ ③a/④a ยังปนผลของการ hedge/FX beta (N1 ไม่ได้ทำให้ α ของกอง hedge ≈ 0) · "
           "ป้ายค่าชั่วคราว 17, 20, 21\n\n" + md(N1H))
sec.append("### หมายเหตุหลังรีวิวผล (ตัวเลขของ reviewer = ไม่ได้ตรวจซ้ำเอง)\n"
           "- **k_res ของ ④a = 5 = kmax และ IC_p2 ของ ①a = 10 = kmax:** IC ไม่หยุดเอง · k* = floor(median{IC_p2, ER, ED, PA}) จึงขึ้นกับ ED/PA · ED ยังไม่ได้เทียบกับบทความ Onatski (2010) และสมการ (42)–(46) ของ PY ยังไม่ได้เทียบกับบทความ (ไม่ได้เปิดบทความ)\n"
           "- reviewer รายงาน (ไม่ได้ตรวจซ้ำเอง): ED=2 ทุก kmax 4–20; block bootstrap ให้ k* ∈ {3: 27%, 4: 59%, 5: 12%}; บังคับ k_res=1…5 แล้ว ④a ไม่ผ่านครบ 5 ข้อที่ k_res ใดเลย (R²_oos E 0.455/0.591/0.613/0.638/0.654)\n"
           "- **PY ปฏิเสธเกินจริง (ตัวเลขของ reviewer ไม่ได้ตรวจซ้ำเอง):** null bootstrap (สุ่มแถวเวลา คง cross-correlation · α=0 · 300 รอบ) อัตราปฏิเสธที่ระดับ 5%: ③b 7.3% · ③a 8.0% · ①a 11.7% (ช่วง 7–12%) · p แบบ bootstrap ของ ③b ≈ 0.043 เทียบกับ p ของ PY 0.014 → ผล PY ของ ③b (test) **ก้ำกึ่ง** ไวต่อ cross-correlation (bootstrap ไม่คง autocorrelation)\n"
           "- **ชื่อ FXH:** คือ 'FX-beta spread' (EW ขา FX beta ต่ำ − EW ขาสูง) ไม่ใช่ factor hedge · corr กับ APB_E = 0.80, กับ ΔUSDTHB = −0.50 · collinearity นี้ทำให้ r ดิบของ APB_E ใน ②b/②c ต่ำกว่า ②a (0.344 vs 0.769)\n"
           "- **ธง nonFX_eq:** คือ 'ดัชนีภูมิภาค 8 ตัวอธิบายกองไม่ได้' ไม่ใช่ 'ไม่ใช่หุ้นต่างประเทศ' — ติดกองหุ้นต่างประเทศเชิงธีม/รายประเทศด้วย (เช่น K-USA-A(A), KT-ASEAN-A, ES-INDONESIA, TBIOTECH, K-GHEALTH, ASP-DIGIBLOC) เพราะไม่มีดัชนี ASEAN/sector ในชุดเทียบ · กฎลงทะเบียนล่วงหน้า ไม่แก้\n"
           "- ชื่อ factor ที่ |corr| 0.5–0.7 คือ 'คล้าย' เท่านั้น (เช่น ①a PC3 'คล้าย US10Y_d' 0.69 · PC4 'คล้าย MSCI_INDIA' 0.59 · ①c PC3 'คล้าย MSCI_VIETNAM' 0.51)\n"
           "- ตารางเกณฑ์ (หัวข้อ 8): c1 ของ ②c **ผ่านโดยนิยาม** (เกณฑ์ = 0.9×ค่าของตัวเอง) ไม่เทียบตรง · ป้ายค่าชั่วคราว: เกณฑ์ผู้เข้ารอบ 12, 18 · GRS (ตาราง 3.2/3.3/7.2) 17 (พอร์ตสร้างจากภูมิภาค) · PY (py.csv/ตาราง 3.4–3.5) 14\n")
sec.append("## 9. การตัดสินใจของ analyst (จุดที่ spec ไม่ได้กำหนด)\n| จุดที่กำกวม | ที่เลือก | ผลกระทบถ้าผิด |\n|---|---|---|\n" +
           "\n".join(f"| {a} | {b} | {c} |" for a, b, c in decisions) + "\n")
sec.append("## 10. ต้องให้ผู้ใช้ตัดสินใจ\nไม่มีเรื่องที่ต้องหยุดรอ — ดูรายการหัวข้อ 9 และส่วน 'ปัญหาที่พบ' ในรายงานตอบกลับ\n")
(OUT / "results.md").write_text("\n".join(sec))

# checksum ของผล
chk = {}
for p in sorted(OUT.iterdir()):
    if p.suffix in (".csv", ".parquet"):
        chk[p.name] = io_l1.sha256_file(p)
meta["output_sha256"] = chk
(OUT / "run_meta.json").write_text(json.dumps(meta, indent=1, default=str))
log("เสร็จ · runtime %.1fs" % (time.time() - T0))
LOGF.close()
