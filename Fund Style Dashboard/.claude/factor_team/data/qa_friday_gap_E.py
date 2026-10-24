"""qa_friday_gap_E.py — งาน BRIEF 121(3): กอง E ที่ไม่มี NAV วันศุกร์ (ธ.ค. 2023 → 2025) กระทบผล S012 / ระยะ 1 แค่ไหน · บรรยาย · ไม่รันการศึกษาใหม่ · ไม่ fit ชุด factor แข่งใหม่

รัน:  cd "<root>" && PYTHONDONTWRITEBYTECODE=1 ./.venv/bin/python -I -B .claude/factor_team/data/qa_friday_gap_E.py [--out DIR]
- ทุกตัวเลขในส่วน "ถ้าตัดกองกลุ่มนี้" คำนวณจากไฟล์ผลที่มี (runs/S012/fund_level_E.csv · eval_clusters.csv · criteria_8_1.csv · qe_verdicts.csv · runs/S003 · runs/S009) —
  ทำซ้ำคะแนนเดิมของ S012 ก่อน (assert ตรง) แล้วจึงตัดกอง · ไม่ refit PCA / factor (ชุด PCA 97 และ k_res ใช้ตามเดิม — ข้อจำกัด)
- R² in-sample ก่อน/หลัง ธ.ค. 2023: ใช้ factor ที่ S012 / S003 สร้างไว้แล้ว (E-PCA-a1 · E-X1 · ①a) · fit ภายในช่วง (Dimson lag 0+1) เหมือนที่ทำกับทอง (qa_gold.py)
- ป้ายบังคับ: ทุกตัวเลขเป็น "การสำรวจหลังเห็นผล (บรรยาย)" ไม่ใช่ผลตัดสิน · ไม่เปลี่ยนคำตัดสินที่ล็อกของ S012
- ผลเหมือนเดิมทุกบิต (CSV ไม่มีวันที่สร้าง · qa_friday_gap_check.json มี sha256 + ฟิลด์ created ฟิลด์เดียว)
"""
from __future__ import annotations

import json
import os
import sys
from datetime import date

sys.dont_write_bytecode = True

import numpy as np
import pandas as pd
from scipy import stats

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
TEAM = os.path.join(ROOT, ".claude", "factor_team")
for p in (ROOT, HERE, os.path.join(TEAM, "lib")):
    sys.path.insert(0, p)
OUT = HERE
if "--out" in sys.argv:
    OUT = os.path.abspath(sys.argv[sys.argv.index("--out") + 1])
    os.makedirs(OUT, exist_ok=True)

import config  # noqa: E402
import build_l0 as L0  # noqa: E402
import io_l1  # noqa: E402
import l1eo  # noqa: E402
import regress as rg  # noqa: E402
from samples import window_mask  # noqa: E402

S012 = os.path.join(TEAM, "runs", "S012")
OUTFILES, CHECK = [], {}
THR = 0.25            # กลุ่ม A = สัดส่วนจุดสิ้นสัปดาห์ที่ NAV asof = วันศุกร์ในช่วงช่องว่าง < 25% (กฎเดียวกับ qa_gold.py)
THR_STRICT = 0.10


def save_csv(df, name):
    df.to_csv(os.path.join(OUT, name), index=False, float_format="%.10g")
    OUTFILES.append(name)


def med(x):
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    return float(np.median(x)) if len(x) else np.nan


# ═════════════════════════════════ 1) สัดส่วน NAV ศุกร์ในช่วงช่องว่าง ต่อรหัส (ทุกกองใน panel L0)
g = l1eo.load_group_map()
UNI = pd.read_csv(os.path.join(HERE, "universe.csv"))
inc = UNI[UNI["included"].astype(str).str.lower().isin(["true", "1", "y", "yes"])]
codes = sorted(set(inc["FundCode"]) | set(g["FundCode"]))
nav, _, _ = L0.load_nav(codes)
nav = nav[(nav[config.NAV_DATE_COL] <= pd.Timestamp("2025-12-31") + pd.Timedelta(days=10))]
ANCH = pd.date_range("2021-01-01", io_l1.MAIN_END, freq="W-FRI")
A64 = L0.D(ANCH)
GAPM = np.asarray((ANCH >= "2023-12-15") & (ANCH <= "2025-12-26"))
PREM = np.asarray((ANCH >= "2021-01-08") & (ANCH <= "2023-12-08"))
grp = {k: v for k, v in nav.groupby(config.NAV_FUND_CODE_COL, sort=False)}
fri_gap, fri_pre = {}, {}
for c in codes:
    if c not in grp:
        continue
    nd = L0.D(grp[c][config.NAV_DATE_COL])
    idx = L0.asof_idx(nd, A64)
    ok = idx >= 0
    gap = np.full(len(ANCH), np.nan)
    gap[ok] = (A64[ok] - nd[idx[ok]]).astype("timedelta64[D]").astype(int)
    for dct, m in ((fri_gap, GAPM), (fri_pre, PREM)):
        v = gap[m]
        v = v[np.isfinite(v)]
        dct[c] = float((v == 0).mean()) if len(v) >= 20 else np.nan
code2unit = l1eo.code_to_unit()
SPL_NEW = {u: n for u, (o, n) in l1eo.SPLICE_TABLE.items()}


def unit_share(u, dct):
    c = SPL_NEW.get(u, u)
    return dct.get(c, np.nan)


# ═════════════════════════════════ 2) รายชื่อกอง E · สมาชิกชุดของ S012
SETS = pd.read_csv(os.path.join(TEAM, "specs", "S013_pca_sets.csv"))
SE = SETS[SETS["policy"] == "E"].copy()
SE["fri_share_gap"] = [unit_share(u, fri_gap) for u in SE["unit"]]
SE["fri_share_pre"] = [unit_share(u, fri_pre) for u in SE["unit"]]
SE["grp_A"] = SE["fri_share_gap"] < THR
SE["grp_A_strict"] = SE["fri_share_gap"] < THR_STRICT
SE["mid_025_075"] = (SE["fri_share_gap"] >= THR) & (SE["fri_share_gap"] < 0.75)
gm_u = g.drop_duplicates("unit").set_index("unit")
SE["group_name"] = [gm_u.loc[u, "group"] if u in gm_u.index else "" for u in SE["unit"]]
SE["name_en"] = [gm_u.loc[u, "name_en"] if u in gm_u.index else "" for u in SE["unit"]]
SE["fund_class"] = [gm_u.loc[u, "fund_class"] if u in gm_u.index else "" for u in SE["unit"]]
assert SE["fri_share_gap"].notna().sum() >= 0.9 * len(SE)
save_csv(SE.sort_values(["grp_A", "fri_share_gap"], ascending=[False, True]), "qa_friday_gap_E_units.csv")
A_UNITS = set(SE.loc[SE["grp_A"], "unit"])
A_STRICT = set(SE.loc[SE["grp_A_strict"], "unit"])
hist = pd.cut(SE["fri_share_gap"], [-0.001, 0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 1.001]).value_counts().sort_index()
CHECK["fri_share_hist_U_E"] = {str(k): int(v) for k, v in hist.items()}
mem = []
for nm, col in (("U_E (หน่วย E ทั้งหมด)", None), ("SEL", "sel"), ("EVAL (160)", "eval"), ("EVAL52", "eval52"), ("STAB", "stab"), ("dedup_keep", "dedup_keep"), ("PCA balanced (97)", "pca_balanced"), ("PCA unbalanced52", "pca_unbal52")):
    d = SE if col is None else SE[SE[col]]
    mem.append(dict(set=nm, n=len(d), n_A=int(d["grp_A"].sum()), frac_A=float(d["grp_A"].mean()), n_A_strict=int(d["grp_A_strict"].sum()), n_mid=int(d["mid_025_075"].sum())))
MEM = pd.DataFrame(mem)
save_csv(MEM, "qa_friday_gap_E_membership.csv")
CHECK["n_A_in_U_E"] = int(SE["grp_A"].sum())

# ═════════════════════════════════ 3) เทียบ R² รายกองต่อแถวหลัก (OOS จาก fund_level_E.csv)
FL = pd.read_csv(os.path.join(S012, "fund_level_E.csv"))
FLE = FL[FL["in_EVAL"]].copy()
ROWS = ["E-PCA-a1", "E-PCA-a2", "E-X0", "E-X1", "E-X2", "E-H", "①a", "①c", "③a", "M1"]
r2o = FLE.pivot(index="unit", columns="row", values="r2_oos")
r2i = FLE.pivot(index="unit", columns="row", values="adj_r2")
r2r = FLE.pivot(index="unit", columns="row", values="r2")
bic = FLE.pivot(index="unit", columns="row", values="bic")
EV = list(r2o.index)
assert len(EV) == 160 and set(EV) == set(SE.loc[SE["eval"], "unit"])
isA = pd.Series([u in A_UNITS for u in EV], index=EV)
rows = []
for r in ROWS:
    for nm, m in (("ทั้งหมด", np.ones(len(EV), bool)), ("กลุ่ม A (ไม่มี NAV ศุกร์)", isA.to_numpy()), ("กองอื่น", ~isA.to_numpy())):
        x, a, rr = r2o[r].to_numpy(float)[m], r2i[r].to_numpy(float)[m], r2r[r].to_numpy(float)[m]
        rows.append(dict(row=r, subset=nm, n=int(np.isfinite(x).sum()), median_r2_oos=med(x), median_adj_r2_train=med(a), median_gap_r2_minus_oos=med(rr - x)))
ROWT = pd.DataFrame(rows)
# ทดสอบเชิงบรรยาย: rank-sum ของ R²_oos กลุ่ม A vs อื่น
rs = []
for r in ROWS:
    xa, xo = r2o.loc[isA, r].dropna().to_numpy(), r2o.loc[~isA, r].dropna().to_numpy()
    u = stats.mannwhitneyu(xa, xo, alternative="two-sided")
    rs.append(dict(row=r, n_A=len(xa), n_other=len(xo), median_A=float(np.median(xa)), median_other=float(np.median(xo)), diff=float(np.median(xa) - np.median(xo)), mannwhitney_p=float(u.pvalue)))
RSUM = pd.DataFrame(rs)
RSUM["note"] = "เชิงบรรยาย · ไม่นับเป็นการทดสอบสมมติฐาน · กองไม่อิสระกัน (กลุ่มกองซ้ำ) → p ไม่ใช้ตัดสิน"
save_csv(ROWT, "qa_friday_gap_E_rows.csv")
save_csv(RSUM, "qa_friday_gap_E_rows_ranksum.csv")

# ═════════════════════════════════ 4) R² in-sample ก่อน/หลัง ธ.ค. 2023 (factor เดิมของ S012 / S003 · fit ภายในช่วง · Dimson lag 0+1)
ALLC = list(g["FundCode"])
Rc = io_l1.load_returns("W")[ALLC]
R, _ = l1eo.splice_units(Rc)
IDX = R.index
mtr, mte = window_mask(IDX, "train"), window_mask(IDX, "test")
PRE_M = np.asarray(IDX <= pd.Timestamp("2023-12-08"))
GAP_M = np.asarray(IDX >= pd.Timestamp("2023-12-15"))
F12 = pd.read_parquet(os.path.join(S012, "factors_S012_weekly.parquet"))
F03 = pd.read_parquet(os.path.join(TEAM, "runs", "S003", "factors_S003_weekly.parquet"))
FSETS = {"E-PCA-a1": F12[["E-PCA-a1__PC1", "E-PCA-a1__PC2", "E-PCA-a1__PC3"]], "E-X1": F12[["core__MKT", "pool__FX", "pool__CMA"]],
         "①a": F03[["1a__PC1", "1a__PC2", "1a__PC3", "1a__PC4"]]}
assert all((v.index == IDX).all() for v in FSETS.values())


def lagged(df, lags=(0, 1)):
    parts = []
    for l in lags:
        d = df.shift(l)
        d.columns = [c if l == 0 else f"{c}_l{l}" for c in df.columns]
        parts.append(d)
    return pd.concat(parts, axis=1)


def fit_eval(y, X, tr, te, min_obs=52, L=4):
    yv, Xv = y.to_numpy(float), X.to_numpy(float)
    ok = np.isfinite(yv) & np.isfinite(Xv).all(axis=1)
    mk = tr & ok
    n = int(mk.sum())
    if n < max(min_obs, Xv.shape[1] + 3):
        return None
    r = rg.ols_hac(yv[mk], np.column_stack([np.ones(n), Xv[mk]]), L)
    mt = te & ok
    yh = rg.predict_oos(r["coef"], Xv[mt]) if mt.sum() else np.array([])
    return dict(n=n, adj=r["adj_r2"], r2_oos=rg.r2_oos(yv[mt], yh) if mt.sum() >= 2 else np.nan)


# ตรวจฐาน: ทำซ้ำ r2_oos / adj_r2 ของ S012 ให้ตรง
for rname, fdf in FSETS.items():
    X = lagged(fdf)
    dmax = 0.0
    for u in EV[:60]:
        res = fit_eval(R[u], X, mtr, mte)
        dmax = max(dmax, abs(res["r2_oos"] - r2o.loc[u, rname]), abs(res["adj"] - r2i.loc[u, rname]))
    assert dmax < 1e-8, (rname, dmax)
    CHECK[f"baseline_repro_{rname}_first60_max_abs_diff"] = dmax
PERU = {}
rows = []
for rname, fdf in FSETS.items():
    X = lagged(fdf)
    per = {}
    for u in EV:
        a = fit_eval(R[u], X, PRE_M, PRE_M, min_obs=40)
        b = fit_eval(R[u], X, GAP_M, GAP_M, min_obs=40)
        per[u] = (a["adj"] if a else np.nan, b["adj"] if b else np.nan)
    pre = pd.Series({u: v[0] for u, v in per.items()})
    gap = pd.Series({u: v[1] for u, v in per.items()})
    PERU[rname] = (pre, gap)
    for nm, m in (("ทั้งหมด", isA.index), ("กลุ่ม A", isA.index[isA]), ("กองอื่น", isA.index[~isA])):
        d = (gap - pre).loc[m]
        rows.append(dict(row=rname, subset=nm, n=int(d.notna().sum()), median_adjr2_pre=med(pre.loc[m]), median_adjr2_gap=med(gap.loc[m]), median_change=med(d), mean_change=float(np.nanmean(d))))
INS = pd.DataFrame(rows)
save_csv(INS, "qa_friday_gap_E_insample.csv")

# จับคู่ในกลุ่มชื่อเดียวกัน (ควบคุมประเภทตลาด): กลุ่มที่มีทั้งกอง A และกองอื่นใน EVAL
gname = pd.Series({u: gm_u.loc[u, "group"] for u in EV})
rows = []
for gn in sorted(set(gname[isA.index[isA]])):
    ua = [u for u in EV if gname[u] == gn and u in A_UNITS]
    uo = [u for u in EV if gname[u] == gn and u not in A_UNITS]
    if not uo:
        continue
    for rname in FSETS:
        pre, gap = PERU[rname]
        rows.append(dict(group=gn, row=rname, n_A=len(ua), n_other=len(uo), r2_oos_A=med(r2o.loc[ua, rname]), r2_oos_other=med(r2o.loc[uo, rname]),
                         adjr2_pre_A=med(pre.loc[ua]), adjr2_pre_other=med(pre.loc[uo]), adjr2_gap_A=med(gap.loc[ua]), adjr2_gap_other=med(gap.loc[uo]),
                         change_A=med((gap - pre).loc[ua]), change_other=med((gap - pre).loc[uo])))
MATCH = pd.DataFrame(rows)
MATCH["did_change_A_minus_other"] = MATCH["change_A"] - MATCH["change_other"]
save_csv(MATCH, "qa_friday_gap_E_matched_group.csv")

# ═════════════════════════════════ 5) ถ้าตัดกองกลุ่ม A ออกจาก EVAL: คะแนน · เกณฑ์ 8.1 · Q-E1..Q-E4
CL = pd.read_csv(os.path.join(S012, "eval_clusters.csv")).set_index("unit")["group_id"]
HASG = FLE[FLE["row"] == "E-X1"].set_index("unit")["has_group_factor"]
CRI = pd.read_csv(os.path.join(S012, "criteria_8_1.csv")).set_index("row")
QEV = pd.read_csv(os.path.join(S012, "qe_verdicts.csv"))
HY = json.load(open(os.path.join(S012, "hybrid_E.json")))
COMPETE = ["E-PCA-a1", "E-PCA-a2", "E-X0", "E-X1", "E-X2", "E-H"]
SMALLER = {"E-X1": ("E-X0", None), "E-H": ("E-X1", None), "E-X2": ("E-X1", "grp")}


def scorecard(units):
    units = list(units)
    med_o = {r: med(r2o.loc[units, r]) for r in ROWS}
    mx = max(med_o.values())
    out = []
    for r in ROWS:
        gap = med((r2r.loc[units, r] - r2o.loc[units, r]).to_numpy())
        rec = dict(row=r, n=len(units), r2oos_med=med_o[r], max_all_rows=mx, C1=bool(med_o[r] >= 0.9 * mx), gap_med=gap, C2=bool(gap <= 0.15), C3_mean_r_h1h2_unchanged=CRI.loc[r, "mean_r_h1h2"],
                   C3=bool(CRI.loc[r, "mean_r_h1h2"] >= 0.6))
        if r in SMALLER:
            ref, flt = SMALLER[r]
            uu = [u for u in units if (flt is None or bool(HASG[u]))]
            d = (bic.loc[uu, r] - bic.loc[uu, ref]).to_numpy()
            rec.update(C4_vs=ref, C4_dBIC_med=med(d), C4=bool(med(d) <= 0))
        else:
            rec.update(C4_vs="", C4_dBIC_med=np.nan, C4=None)
        c5 = CRI.loc[r, "C5_named"]
        rec["C5_unchanged"] = c5
        allp = rec["C1"] and rec["C2"] and rec["C3"] and (rec["C4"] is None or rec["C4"]) and (str(c5) == "True")
        rec["passed_8_1"] = allp if r in COMPETE or r in ("①a", "①c", "③a") else "N/A"
        out.append(rec)
    return pd.DataFrame(out)


SC_ALL = scorecard(EV)
# ตรวจ: คะแนนทั้งหมดตรง criteria_8_1.csv เดิม
for _, rw in SC_ALL.iterrows():
    o = CRI.loc[rw["row"]]
    assert abs(rw["r2oos_med"] - o["r2oos_med"]) < 1e-9 and abs(rw["gap_med"] - o["gap_med"]) < 1e-9, rw["row"]
    if rw["row"] in SMALLER:
        assert abs(rw["C4_dBIC_med"] - o["C4_dBIC_med"]) < 1e-9, rw["row"]
    if rw["row"] in COMPETE + ["①a", "①c", "③a"]:
        assert str(rw["passed_8_1"]) == str(o["passed_8_1"]), (rw["row"], rw["passed_8_1"], o["passed_8_1"])
CHECK["scorecard_all_matches_criteria_8_1"] = True
EV_NOA = [u for u in EV if u not in A_UNITS]
EV_NOA_STRICT = [u for u in EV if u not in A_STRICT]
SC_NOA = scorecard(EV_NOA)
SC_NOA_S = scorecard(EV_NOA_STRICT)
out = []
for tag, d in (("ทั้งหมด (160)", SC_ALL), (f"ตัดกลุ่ม A (< {THR:.0%}) → {len(EV_NOA)}", SC_NOA), (f"ตัดกลุ่ม A เข้ม (< {THR_STRICT:.0%}) → {len(EV_NOA_STRICT)}", SC_NOA_S)):
    x = d.copy()
    x.insert(0, "set", tag)
    out.append(x)
SCT = pd.concat(out, ignore_index=True)
save_csv(SCT, "qa_friday_gap_E_scorecard.csv")


def qe(units, n_boot=2000):
    units = list(units)
    cl = np.array([CL[u] for u in units])
    res = []
    for q, a, b in (("Q-E1 E-X2 − E-PCA-a1", "E-X2", "E-PCA-a1"), ("Q-E2 E-X1 − ③a", "E-X1", "③a"), ("Q-E3 E-PCA-a1 − ①a", "E-PCA-a1", "①a"), ("Q-E4 E-H − E-X1", "E-H", "E-X1")):
        xa, xb = r2o.loc[units, a].to_numpy(float), r2o.loc[units, b].to_numpy(float)
        bs = l1eo.cluster_bootstrap(lambda i: np.array([np.median(xa[i]) - np.median(xb[i])]), cl, n=n_boot, seed=20261015)
        v, lo, hi = float(np.median(xa) - np.median(xb)), float(bs["lo"][0]), float(bs["hi"][0])
        res.append(dict(question=q, n=len(units), diff=v, ci_lo=lo, ci_hi=hi))
    sc = scorecard(units).set_index("row")
    p81 = lambda r: str(sc.loc[r, "passed_8_1"]) == "True"
    d4 = sc.loc["E-H", "C4_dBIC_med"]
    v1, v2, v3, v4 = res[0]["diff"], res[1], res[2], res[3]
    res[0]["verdict"] = ("แทนได้" if (v1 >= -0.03 and p81("E-X2")) else ("ใกล้ (≥ −0.03 แต่ E-X2 ไม่เข้ารอบ 8.1)" if v1 >= -0.03 else ("ใกล้" if v1 >= -0.06 else "แทนไม่ได้")))
    res[1]["verdict"] = "ดีกว่า" if (v2["diff"] >= 0.05 and v2["ci_lo"] > 0) else "ไม่ดีกว่า (ตามเกณฑ์)"
    res[2]["verdict"] = "ดีขึ้น" if v3["ci_lo"] > 0 else "ไม่ต่าง (บรรยาย)"
    res[3]["verdict"] = "มี" if (HY["k_res"] >= 1 and v4["diff"] >= 0.02 and d4 <= 0) else "ไม่มี"
    res[3]["note"] = f"k_res = {HY['k_res']} (ไม่คำนวณใหม่ · ใช้ตาม S012) · ΔBIC median (E-H − E-X1) = {d4:.2f}"
    res[0]["note"] = f"E-X2 เข้ารอบ 8.1 = {p81('E-X2')}"
    return pd.DataFrame(res)


QE_ALL = qe(EV)
for k in range(4):   # ตรวจ: ทำซ้ำ qe_verdicts.csv เดิม
    assert abs(QE_ALL.loc[k, "diff"] - QEV.loc[k, "diff"]) < 1e-9 and abs(QE_ALL.loc[k, "ci_lo"] - QEV.loc[k, "ci_lo"]) < 1e-9 and abs(QE_ALL.loc[k, "ci_hi"] - QEV.loc[k, "ci_hi"]) < 1e-9, k
    assert QE_ALL.loc[k, "verdict"] == QEV.loc[k, "verdict"], (QE_ALL.loc[k, "verdict"], QEV.loc[k, "verdict"])
CHECK["qe_all_matches_qe_verdicts"] = True
QE_NOA = qe(EV_NOA)
QE_NOA_S = qe(EV_NOA_STRICT)
parts = []
for tag, d in (("ทั้งหมด (160)", QE_ALL), (f"ตัดกลุ่ม A (< {THR:.0%})", QE_NOA), (f"ตัดกลุ่ม A เข้ม (< {THR_STRICT:.0%})", QE_NOA_S)):
    x = d.copy()
    x.insert(0, "set", tag)
    parts.append(x)
save_csv(pd.concat(parts, ignore_index=True), "qa_friday_gap_E_qe.csv")

# ═════════════════════════════════ 6) ผลต่อระยะ 1 (S003 · S009) โดยสังเขป — จากไฟล์ผลที่มี
isA_code = {c: (fri_gap.get(c, np.nan) < THR) for c in codes}
S3 = pd.read_csv(os.path.join(TEAM, "runs", "S003", "fund_level.csv"))
S3 = S3[(S3["policy"] == "E") & (S3["in_EVAL"])].copy()
S3["grpA"] = S3["FundCode"].map(isA_code)
rows = []
for f, d in S3.groupby("form", sort=False):
    a, o = d[d["grpA"] == True], d[d["grpA"] == False]
    rows.append(dict(source="S003 fund_level (E · EVAL)", form_or_row=f, n_A=len(a), n_other=len(o), median_r2_oos_A=med(a["r2_oos"]), median_r2_oos_other=med(o["r2_oos"]),
                     median_adj_r2_A=med(a["adj_r2"]), median_adj_r2_other=med(o["adj_r2"]), median_gap_A=med(a["r2"] - a["r2_oos"]), median_gap_other=med(o["r2"] - o["r2_oos"]),
                     median_r2_oos_all=med(d["r2_oos"]), median_r2_oos_excl_A=med(o["r2_oos"])))
S9 = pd.read_csv(os.path.join(TEAM, "runs", "S009", "fund_level.csv"))
S9 = S9[(S9["policy"] == "E")].copy()
S9["grpA"] = S9["FundCode"].map(isA_code)
for f, d in S9.groupby("row", sort=False):
    a, o = d[d["grpA"] == True], d[d["grpA"] == False]
    rows.append(dict(source="S009 fund_level (E · ทุกกองใน row)", form_or_row=f, n_A=len(a), n_other=len(o), median_r2_oos_A=med(a["r2_oos"]), median_r2_oos_other=med(o["r2_oos"]),
                     median_adj_r2_A=med(a["adj_r2"]), median_adj_r2_other=med(o["adj_r2"]), median_r2_oos_all=med(d["r2_oos"]), median_r2_oos_excl_A=med(o["r2_oos"])))
P1 = pd.DataFrame(rows)
save_csv(P1, "qa_friday_gap_E_phase1.csv")
bh = pd.read_csv(os.path.join(TEAM, "runs", "S009", "alpha_bh_list.csv")).rename(columns={"Unnamed: 0": "FundCode"})
bh["grpA"] = bh["FundCode"].map(isA_code)
bh_rows = bh[["FundCode", "policy", "group", "bh1", "bh2", "grpA"]].copy()
bh_rows["fri_share_gap"] = bh_rows["FundCode"].map(fri_gap)
save_csv(bh_rows, "qa_friday_gap_E_s009_alpha_list.csv")
n_E_codes_A = int(sum(1 for c in set(inc.loc[inc["policy"] == "E", "FundCode"]) if isA_code.get(c, False)))
CHECK["phase1"] = dict(n_E_panel_codes=int((inc["policy"] == "E").sum()), n_E_panel_codes_A=n_E_codes_A, n_S009_alpha_list=int(len(bh)), n_S009_alpha_list_E=int((bh["policy"] == "E").sum()),
                       n_S009_alpha_list_E_A=int(((bh["policy"] == "E") & (bh["grpA"] == True)).sum()))

# ═════════════════════════════════ check
def sha(p):
    return L0.sha256(p)


man = dict(created=str(date.today()), script="qa_friday_gap_E.py", script_sha256=sha(os.path.join(HERE, "qa_friday_gap_E.py")), pandas=pd.__version__, numpy=np.__version__, python=sys.version.split()[0],
           threshold_group_A=THR, threshold_strict=THR_STRICT,
           inputs=[dict(file=os.path.relpath(p, ROOT), sha256=sha(p)) for p in (config.NAV_HISTORY_CSV, os.path.join(HERE, "universe.csv"), os.path.join(HERE, "panel_weekly.parquet"), os.path.join(HERE, "factors_weekly.parquet"),
                                                                             os.path.join(TEAM, "specs", "S013_pca_sets.csv"), os.path.join(TEAM, "specs", "S012_group_map.csv"),
                                                                             os.path.join(S012, "fund_level_E.csv"), os.path.join(S012, "eval_clusters.csv"), os.path.join(S012, "criteria_8_1.csv"),
                                                                             os.path.join(S012, "qe_verdicts.csv"), os.path.join(S012, "hybrid_E.json"), os.path.join(S012, "factors_S012_weekly.parquet"),
                                                                             os.path.join(TEAM, "runs", "S003", "factors_S003_weekly.parquet"), os.path.join(TEAM, "runs", "S003", "fund_level.csv"),
                                                                             os.path.join(TEAM, "runs", "S009", "fund_level.csv"), os.path.join(TEAM, "runs", "S009", "alpha_bh_list.csv"))],
           outputs=[dict(file=f".claude/factor_team/data/{n}", sha256=sha(os.path.join(OUT, n))) for n in sorted(OUTFILES)], checks=CHECK)
with open(os.path.join(OUT, "qa_friday_gap_check.json"), "w", encoding="utf-8") as f:
    json.dump(man, f, ensure_ascii=False, indent=1, default=str)
    f.write("\n")
print("ok", len(OUTFILES))
print(MEM.to_string())
print(SCT[["set", "row", "r2oos_med", "gap_med", "passed_8_1", "C4_dBIC_med"]].to_string())
print(pd.concat(parts).to_string())
