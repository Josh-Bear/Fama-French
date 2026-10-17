"""S009 addendum (ตามรีวิวผล S009 · BRIEF ข้อ 83–86) — อ่านผลเดิมใน runs/S009 (ไม่แก้) แล้วเขียนไฟล์ใหม่ + results_addendum.md
ทุกอย่างในไฟล์นี้ **ทำหลังเห็นผล** (ป้าย "ทำหลังเห็นผล") · ใช้: PYTHONPATH=. python run_addendum.py [--out DIR]"""
import json
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

LIB = Path(__file__).resolve().parents[2] / "lib"
sys.path.insert(0, str(LIB))
import forms as fm_  # noqa: E402
import io_l1  # noqa: E402
import l2  # noqa: E402
import l3  # noqa: E402
import l4  # noqa: E402
import tests_stat as ts  # noqa: E402
from pca import factor_returns  # noqa: E402
from samples import window_mask  # noqa: E402

SEED = 20261015
SRC = Path(__file__).resolve().parent  # ผลเดิม (อ่านอย่างเดียว)
OUT = SRC
if "--out" in sys.argv:
    OUT = Path(sys.argv[sys.argv.index("--out") + 1])
OUT.mkdir(parents=True, exist_ok=True)
TEAM = io_l1.TEAM
S003, S005, S006 = TEAM / "runs" / "S003", TEAM / "runs" / "S005", TEAM / "runs" / "S006"
LOG = open(OUT / "run_addendum.log", "w")


def log(m):
    line = f"[{datetime.now().isoformat(timespec='seconds')}] {m}"
    LOG.write(line + "\n")
    LOG.flush()
    print(line, flush=True)


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


def sv(df, name):
    df.to_csv(OUT / name, index=False)
    return df


log("START addendum (ทำหลังเห็นผล)")
AL = pd.read_csv(SRC / "alpha_fund.csv")
Q = pd.read_csv(SRC / "alpha_q2.csv", index_col=0)
FC = pd.read_csv(S005 / "fund_clusters.csv").set_index("FundCode")
AF = list(Q.index)
polA = Q["policy"]
nonGO = [c for c in AF if polA[c] != "O"]
assert len(AF) == 206 and len(nonGO) == 192
a = lambda rid, w="full": AL[(AL.row == rid) & (AL.window == w)].set_index("FundCode")

# ───────── S1 (ก): ตารางแยก "มีหลักฐาน α" / "บางส่วน" ─────────
ev = Q[Q.q2_verdict != "ไม่พบ"].copy()
r3 = a("ref_3a")
t = pd.DataFrame(dict(FundCode=ev.index, policy=ev.policy.values, group=ev.group.values, cluster=FC.loc[ev.index, "group_id"].values, verdict=ev.q2_verdict.values,
                      div=ev["div"].values, div_note=ev.div_note.fillna("").values, alpha_M1=ev.alpha_full_1.values, t_M1=ev.t_full_1.values, bh_M1=ev.bh1.values,
                      alpha_M2=ev.alpha_full_2.values, t_M2=ev.t_full_2.values, bh_M2=ev.bh2.values,
                      alpha_ref3a=r3.loc[ev.index, "alpha_pct"].values, t_ref3a=r3.loc[ev.index, "t"].values, bh_ref3a=r3.loc[ev.index, "bh"].values))
t["is_G_O"] = t.policy.eq("O")
t["abs_t_ref3a_lt_2"] = t.t_ref3a.abs() < 2
t["note"] = np.where(t.is_G_O, "G-O (กองทอง/กองอื่นนอก factor ①a/①c) — ไม่นับเป็นหลักฐาน α ของผู้จัดการ · factor ทองไม่อยู่ใน ①a/①c", "")
t = t.sort_values(["verdict", "cluster", "FundCode"])
sv(t, "q2_evidence_funds.csv")
cs = t.groupby(["verdict", "cluster"]).agg(n_funds=("FundCode", "count"), policy=("policy", "first"), n_G_O=("is_G_O", "sum"), med_alpha_M1=("alpha_M1", "median"), med_alpha_ref3a=("alpha_ref3a", "median"),
                                           n_bh_ref3a=("bh_ref3a", "sum"), funds=("FundCode", lambda x: ";".join(x))).reset_index()
sv(cs, "q2_evidence_cluster_summary.csv")
sm_rows = []
for v, d in t.groupby("verdict"):
    sm_rows.append(dict(verdict=v, n_funds=len(d), n_indep_groups=d.cluster.nunique(), n_G_O=int(d.is_G_O.sum()), n_indep_groups_G_O=d[d.is_G_O].cluster.nunique(), n_not_G_O=int((~d.is_G_O).sum()),
                        n_indep_groups_not_G_O=d[~d.is_G_O].cluster.nunique(), n_with_div_flag=int(d["div"].sum()), n_bh_under_ref3a=int(d.bh_ref3a.sum()), n_abs_t_ref3a_lt_2=int(d.abs_t_ref3a_lt_2.sum())))
SM = sv(pd.DataFrame(sm_rows), "q2_evidence_summary.csv")

# ───────── S1 (ข): BH/BY เมื่อตัด G-O + FF bootstrap 192 กอง ─────────
rows = []
for rid in ("M1", "M2", "M3", "M4", "ref_FX_1a", "ref_FX_1c", "ref_3a", "ref_L3B_1a", "ref_L3B_1c"):
    d = a(rid)
    for nm, funds in (("206", AF), ("192_exclGO", nonGO)):
        p = d.loc[funds, "p"].to_numpy()
        rows.append(dict(row=rid, set=nm, n=len(funds), BH=int(ts.bh(p, 0.10)[0].sum()), BY=int(l2.by(p, 0.10)[0].sum()), max_abs_t=float(d.loc[funds, "t"].abs().max()),
                         n_t_gt_3_23=int((d.loc[funds, "t"].abs() > 3.23).sum()), n_t_gt_3_94=int((d.loc[funds, "t"].abs() > 3.94).sum())))
BHX = sv(pd.DataFrame(rows), "bh_by_exclGO.csv")
log("เขียน bh_by_exclGO.csv")

R = io_l1.load_returns("W")
F = io_l1.load_factors("W")
U = io_l1.load_universe().set_index("FundCode")
S = l2.fund_sets(R, U, io_l1.load_dup_pairs())
EVAL, STAB = S["EVAL"], S["STAB"]
idx = R.index
I, blocks = l2.index_set(F)
M28 = I[blocks["M28"]]
FXs = l4.fx_factor(F)
fac_path = S003 / "factors_S003_weekly.parquet"
BASES = {"1a": l2.load_l1_factors(fac_path, "1a"), "1c": l2.load_l1_factors(fac_path, "1c")}
PRIMDF = pd.read_csv(S005 / "primary_index.csv")
PRIM_L2 = {b: PRIMDF[PRIMDF.form == f"{b}@4"].set_index("FundCode")["index"] for b in BASES}
E_b = {b: l4.e_from_s006(M28, f, S006 / "resid_B_coef.csv", b) for b, f in BASES.items()}
mfull = window_mask(idx, "full")
B_FF = 999
rowsb = []
for rid, b in (("M1", "1a"), ("M2", "1c")):
    base = pd.concat([BASES[b], FXs.to_frame("FX")], axis=1)
    pf = l3.perfund_from_primary(E_b[b], PRIM_L2[b], EVAL)
    prov = l4.MixedProvider(base, pf)
    d = a(rid)
    for nm, funds in (("206", AF), ("192_exclGO", nonGO)):
        ah = d.loc[funds, "alpha_pct"].to_numpy() / 5200.0
        rd, act, sm = l4.ff_bootstrap(R, prov, funds, mfull, ah, B=B_FF, block=4, seed=SEED, min_rows=104, is_E=(polA[funds] == "E").to_numpy())
        sm.insert(0, "set", nm)
        sm.insert(0, "row", rid)
        sm["null_p99_of_n_bh"] = float(np.percentile(rd["n_bh"], 99))
        rowsb.append(sm)
        log(f"ff_bootstrap {rid} {nm}: n_bh จริง {act['n_bh']} · null p95 {np.percentile(rd['n_bh'], 95):.1f}")
FFX = sv(pd.concat(rowsb, ignore_index=True), "ff_boot_exclGO_summary.csv")

# ───────── S2: ตรวจซ้ำรายเดือน M1 / M2 ─────────
Rm = io_l1.load_returns("M")
Fm = io_l1.load_factors("M")
midx = Rm.index
bal, base_f = S["bal"], S["base"]
mm_tr = np.asarray(midx <= pd.Timestamp("2023-12-31"))
L1 = fm_.build_line1(R, bal, base_f, kstar=4, seed=SEED, n_perm=500)
parts = L1["parts"]
sd_bal, sd_base = Rm.loc[mm_tr, bal].std(ddof=0).to_numpy(), Rm.loc[mm_tr, base_f].std(ddof=0).to_numpy()
M28m = pd.DataFrame({c: Fm[c] - Fm["RF_BOT"] for c in blocks["M28"]})
FXm = (Fm["SHV_THB"] - Fm["RF_BOT"]).rename("FX")
AFm = [c for c in AF if c in Rm.columns]
mrows, mfund = [], []
allm = np.ones(len(midx), bool)
for rid, b in (("M1", "1a"), ("M2", "1c")):
    Lam, sdv, cols_ = {"1a": (parts["Lam_a"], sd_bal, bal), "1c": (parts["Lam_c"], sd_base, base_f)}[b]
    fmd = pd.DataFrame(factor_returns(Rm[cols_].to_numpy(float), Lam, sdv), index=midx, columns=[f"PC{i + 1}" for i in range(Lam.shape[1])])
    base = pd.concat([fmd, FXm.reindex(midx)], axis=1)
    pf = {c: M28m[PRIM_L2[b][c]] for c in AFm if PRIM_L2[b][c] in l3.P4}
    fit, _, _ = l3.fit_perfund(Rm, base, pf, allm, None, AFm, 36, 3)
    ok = np.where(fit.ok)[0]
    at = l4.alpha_table(l4.sub_fit(fit, ok), ann=12)
    w = a(rid).loc[at.index]
    both = w.alpha_pct.notna() & at.alpha_pct.notna()
    rho = stats.spearmanr(w.alpha_pct[both], at.alpha_pct[both])
    wk_same = ts.bh(w.loc[both, "p"].to_numpy(), 0.10)[0].sum()
    mrows.append(dict(row=rid, n_funds_monthly=len(at), BH_monthly=int(at.bh.sum()), BY_monthly=int(at.by.sum()), BH_weekly_206=int(a(rid).bh.sum()), BH_weekly_same_funds=int(wk_same),
                      spearman_alpha_weekly_vs_monthly=float(rho.statistic), spearman_p=float(rho.pvalue), sign_agree_frac=float((np.sign(w.alpha_pct[both]) == np.sign(at.alpha_pct[both])).mean()),
                      n_ev14_in_monthly=int(at.index.isin(Q.index[Q.q2_verdict == "มีหลักฐาน α"]).sum()), n_ev14_BH_monthly=int(at.loc[at.index.isin(Q.index[Q.q2_verdict == "มีหลักฐาน α"]), "bh"].sum()),
                      note="รายเดือน Dimson lag 1 เดือน · HAC L=3 · ดัชนีดิบแทน e (span เท่ากัน) · min_obs 36 · α ×12 · บรรยาย ไม่ใช่รูปแบบใหม่ · ทำหลังเห็นผล"))
    x = at.copy()
    x.insert(0, "row", rid)
    x.insert(1, "FundCode", x.index)
    x["alpha_weekly_pct"] = w.alpha_pct
    x["bh_weekly"] = w.bh
    x["q2_verdict_weekly"] = Q.loc[x.index, "q2_verdict"]
    mfund.append(x.reset_index(drop=True))
    log(f"รายเดือน {rid}: n={len(at)} BH={int(at.bh.sum())} Spearman={rho.statistic:.3f}")
MON = sv(pd.DataFrame(mrows), "monthly_check.csv")
MF = sv(pd.concat(mfund, ignore_index=True), "monthly_check_funds.csv")

# ───────── ข้อ 85: X2 vs X4 · คำตัดสิน Q3 ─────────
XS = pd.read_csv(SRC / "xsec.csv")
XM = pd.read_csv(SRC / "xsec_meta.csv").set_index("spec")
xr = []
for term in ("ter", "DIV", "FXb", "omr", "d_v2026", "d_rate"):
    row = dict(term=term)
    for sp in ("X2_M1", "X4_M1", "X2_M2", "X4_M2", "X3_M1", "X3_M2"):
        d = XS[(XS.spec == sp) & (XS.term == term)]
        row[sp] = (f"{d.coef.iloc[0]:.2f} [{d.ci_lo.iloc[0]:.2f}, {d.ci_hi.iloc[0]:.2f}]" if len(d) else "ตัดคอลัมน์")
    xr.append(row)
X24 = sv(pd.DataFrame(xr), "x2_vs_x4.csv")


def ci(sp, term):
    d = XS[(XS.spec == sp) & (XS.term == term)]
    return (d.ci_lo.iloc[0], d.ci_hi.iloc[0], d.coef.iloc[0]) if len(d) else None


q3 = []
for term in ("ter", "DIV", "FXb", "omr"):
    ex_ = [ci(f"X2_{r}", term) for r in ("M1", "M2")]
    n_ex = sum(1 for c in ex_ if c and (c[0] > 0 or c[1] < 0))
    v = "อธิบาย α (ทั้งสองฐาน CI ไม่คร่อม 0)" if n_ex == 2 else ("บางส่วน (ฐานเดียว)" if n_ex == 1 else "ไม่อธิบาย (CI คร่อม 0)")
    extra = ""
    if term == "ter":
        cover = sum(1 for c in ex_ if c[0] <= -1 <= c[1])
        extra = "สอดคล้อง 1:1" if cover == 2 else ("ครอบ −1 ฐานเดียว" if cover == 1 else "ไม่สอดคล้อง 1:1 (CI ไม่ครอบ −1 ทั้งสองฐาน)")
        x4 = [ci(f"X4_{r}", term) for r in ("M1", "M2")]
        extra += " · X4(OLS) ครอบ −1: " + str([bool(c[0] <= -1 <= c[1]) for c in x4]) + " ครอบ 0: " + str([bool(c[0] <= 0 <= c[1]) for c in x4])
    x3 = [ci(f"X3_{r}", term) for r in ("M1", "M2")]
    q3.append(dict(term=term, q3_verdict_X2=v, extra=extra, X3_coef=str([round(float(c[2]), 2) if c else None for c in x3]), X3_CI_straddle0=str([bool(c[0] <= 0 <= c[1]) if c else None for c in x3])))
wald = [float(XM.loc[f"X2_{r}", "wald_group_p"]) for r in ("M1", "M2")]
q3.append(dict(term="กลุ่ม (Wald ร่วม)", q3_verdict_X2="อธิบาย (p<0.05 ทั้งสองฐาน)" if all(p < 0.05 for p in wald) else "บางส่วน/ไม่", extra=f"p = {wald}", X3_coef="", X3_CI_straddle0=""))
Q3V = sv(pd.DataFrame(q3), "q3_verdict.csv")

# ───────── ข้อ 85/5: สรุปความคาดหมายที่ประเมินใหม่ ─────────
EXP = pd.read_csv(SRC / "expectations_vs_results.csv")
G0 = pd.read_csv(SRC / "g0_pca.csv")
x2w = XS[(XS.spec.isin(["X2_M1", "X2_M2"])) & (XS.term == "ter")]
xv2 = [(float(XS[(XS.spec == f"XV2_{r}") & (XS.term == "ter")].eval("ci_hi-ci_lo").iloc[0]) / float(XS[(XS.spec == f"X2_{r}") & (XS.term == "ter")].eval("ci_hi-ci_lo").iloc[0])) for r in ("M1", "M2")]
GRn = pd.read_csv(SRC / "group_names.csv")
top11 = GRn[GRn.group.isin(["MSCI_ACWI_CD", "MSCI_CHINA_ALL_SHARES"])].groupby(["base", "group"]).head(1)
re_eval = pd.DataFrame([
    dict(item=7, assessment="ไม่ตรง", basis=f"CI ของ TER ไม่ครอบทั้ง 0 และ −1 (X2 M1 {ci('X2_M1','ter')[:2]}, M2 {ci('X2_M2','ter')[:2]}) · Wald กลุ่ม p {wald} (ความคาดหมาย p>0.05)"),
    dict(item=9, assessment="ไม่ตรง", basis="ACWI_CD = บางส่วน (①a k_g=3 ผ่าน · ①c k_g=0) แทน 'มี' ทั้งสองฐาน · ACWI_IT 'มี' ทั้งที่คาดว่าไม่มี · กลุ่ม LOO 'มี' 3 กลุ่ม (EUROPE/INDIA/JAPAN) > 2 · G-F บางส่วน · (ดู group_factor.csv)"),
    dict(item=10, assessment="ไม่ตรง", basis="eigenvalue แรก/trace = " + ", ".join(f"{b}:{s:.3f}" for b, s in zip(G0.base, G0.eig1_share)) + " (ความคาดหมาย < 10%) · k_ED ≥ 1 ตรงบนตัวแทน (k_ED=1) แต่ k_ED=0 บนชุดครบ train"),
    dict(item=11, assessment="ไม่ตรง", basis="top-1 ของ ACWI_CD/CHINA_ALL ไม่ใช่ ARKK/QQQ/KWEB/CHINA_A และ |corr| ต่ำกว่า 0.5 ทั้ง train/test หรือป้าย 'ไม่ชัด' (group_names.csv): " + "; ".join(f"{r.base}/{r.group}:{r.candidate}({r.corr_train:.2f},{r.corr_test:.2f})" for r in top11.itertuples())),
    dict(item=16, assessment="บางส่วน", basis=f"CI ของ TER ใน XV2 กว้างกว่า X2 = {xv2[0]:.2f} / {xv2[1]:.2f} เท่า (ความคาดหมาย ≥ 2: M1 ไม่ถึง · M2 ถึง) · เครื่องหมายตรงกันทั้งสองฐาน · ASIA_EX_JAPAN ถูกรวมฐาน"),
    dict(item=13, assessment="ดูตาราง monthly_check.csv", basis=f"Spearman {MON.spearman_alpha_weekly_vs_monthly.round(3).tolist()} · BH รายเดือน {MON.BH_monthly.tolist()} vs รายสัปดาห์ (กองเดียวกัน) {MON.BH_weekly_same_funds.tolist()}"),
    dict(item=20, assessment="ไม่ตรง (เกณฑ์เดิมตามตัวอักษร) / ตรง (เกณฑ์ที่ปรับหลังรัน smoke · ป้าย 'ปรับหลังเห็นผล')", basis="เดิม: n=205/103 บน EVAL 207 → ได้ n=204/102 บน α-family 206 (ไม่รวม MGAPVD ที่มีทั้ง Rate และ Actual) · median/IQR/100% ตรงกัน · เป็น QA ของข้อมูลค่าธรรมเนียม ไม่ใช่ผลตอบแทน"),
])
sv(re_eval, "expectations_reassessed.csv")

# ───────── results_addendum.md ─────────
nGO_ev = int(t[t.verdict == "มีหลักฐาน α"].is_G_O.sum())
L = ["# results_addendum — S009 (ตามรีวิวผล S009 · BRIEF ข้อ 83–86) · **ทำหลังเห็นผล**\n",
     f"สร้าง {datetime.now().isoformat(timespec='seconds')} · ไม่แก้ไฟล์ผลเดิม (37 CSV sha256 เท่าเดิม) · เพิ่มเฉพาะไฟล์ใหม่ในโฟลเดอร์นี้ · ป้ายบังคับ (ก)–(ญ) ของ results.md ใช้กับทุกตารางในนี้ · ทุกตารางในนี้คือ **ทำหลังเห็นผล** (ไม่ใช่เกณฑ์ที่ล็อก) · คำตัดสิน Q2 / ป้าย / Q3 ที่ล็อกยังคิดบน 206 กอง / X2 ตามเดิม\n",
     "## A. S1 — รายการ 'มีหลักฐาน α' และ 'บางส่วน' แยกกลุ่มกองอิสระ / G-O / เทียบ ref-③a\n",
     "**ห้ามอ่านคำว่า 'กองมี α' โดยไม่ดูตารางนี้คู่กัน.** G-O (policy O) 14 กอง = กองทอง 6 + REIT/อสังหา 8 (ตามรีวิวรอบ 2 · ไม่ได้ตรวจชื่อเอง) — **กองทอง 6 กอง** (BGOLD / K-GOLD-A(A) / KT-GOLD / SCBGOLDHP / TGOLD / UOBSG-N) ถือ exposure ต่อทองที่ factor ①a/①c ไม่ครอบ จึงไม่ใช่หลักฐาน α ของผู้จัดการ · ห้ามอ่านว่ากอง G-O ทั้งหมดถือทอง · ตัวเลขเมื่อตัดเฉพาะกองทอง 6 กอง (200 กอง) **เป็นของ reviewer ไม่ได้คำนวณเอง**: BH M1 = 4 · M2 = 12\n",
     md(SM), md(cs.drop(columns=["funds"])), md(t.drop(columns=["note"])),
     f"## B. BH / BY เมื่อตัด G-O (192 กอง) — diagnostic ทำหลังเห็นผล\n- ใน 'มีหลักฐาน α' มี G-O {nGO_ev} จาก {int((t.verdict == 'มีหลักฐาน α').sum())} กอง\n- BY M1 = 0 เพราะ |t| สูงสุดของ M1 = {BHX[(BHX.row == 'M1') & (BHX.set == '206')].max_abs_t.iloc[0]:.2f} < 3.94 (ขั้นแรกของ BY ต้อง |t| ≥ 3.94 ที่ N = 206) ส่วน M2 มีกองที่ |t| > 3.94 และ 15 กองที่ |t| > 3.23 → BY ผ่าน 15 · BY ทำงานแบบหน้าผา (ผ่านทั้งหมดหรือไม่ผ่านเลย) ห้ามอ่านว่า M2 'แข็งกว่า' M1 มาก\n",
     md(BHX), "### B.1 FF 2010 block bootstrap บน 206 vs 192 (ไม่รวม G-O) — ป้าย: ทำหลังเห็นผล · seed/B เดิม (999) · ป้าย FF block เดิมใช้\n", md(FFX[FFX.stat.isin(["n_bh", "frac_bh", "p1_ALL", "p5_ALL", "p95_ALL", "p99_ALL"])]), "**อ่านผล:** เมื่อไม่รวม G-O หางขวาของ M1 ไม่เกิน null (p_boot ของ p95 = 0.292 · ตามรีวิวรอบ 2) และ n_BH = 4 มี p_boot 0.050 (M2 ยังเกิน null: n_BH 13 · p_boot 0.003)\n",
     "## C. S2 — ตรวจซ้ำรายเดือน M1 / M2 (ความคาดหมายข้อ 13 · ป้าย: ทำหลังเห็นผล · บรรยาย ไม่ใช่รูปแบบใหม่)\n", md(MON), "**ป้าย: ไม่มี null รองรับ — ใช้ดูความสอดคล้องเท่านั้น** (ห้ามอ่าน BH รายเดือนที่มากกว่าเป็นหลักฐานว่ามี α มากขึ้น) · อ่านได้สองทาง (reviewer): (ก) NAV ไทยไม่พร้อมดัชนีต่างประเทศ ข้อมูลรายเดือนลดปัญหานี้ได้มากกว่า Dimson lag 1 รายสัปดาห์ → t จริงอาจสูงขึ้น (ข) HAC (L=3) ที่ T เล็ก (~59 เดือน) ปฏิเสธเกินจริง (over-reject) → BH มากเกิน · แยกสองทางไม่ได้จากข้อมูลนี้\n", "รายกอง: `monthly_check_funds.csv`\n",
     "## D. ข้อ 85 — X2 (WLS · ตัดสิน) เทียบ X4 (OLS) อย่างเท่าเทียม · คำตัดสิน Q3 (ล็อกไว้ที่ X2 · ไม่เปลี่ยน)\n", md(X24), md(Q3V),
     "**ถ้อยคำ TER:** slope ของ TER (หน่วย %/ปี ต่อ %/ปี) เป็น **ความสัมพันธ์ข้ามกอง** ไม่ใช่เหตุและผล — กองที่ TER สูงกว่า 1 จุด % สัมพันธ์กับ α̂ ที่ต่ำกว่า ~2.4–2.7 จุด %/ปี (X2) · ค่าที่คาดจากกลไกหักค่าธรรมเนียมคือ −1 · X4 (OLS) ให้ ≈ −1.1 / −1.4 (CI ครอบทั้ง 0 และ −1) → ผลขึ้นกับวิธีถ่วงน้ำหนัก · "
     "คำอธิบายที่เป็นไปได้ทั้งหมด (ไม่มีข้อใดตัดออกได้): น้ำหนัก WLS · ต้นทุนนอก TER ที่สัมพันธ์กับ TER · **ช่องทางย้อนทาง** (TER = ค่าใช้จ่าย/NAV เฉลี่ย: ผลงานแย่ → AUM หด → TER สูงขึ้น; 161 กองใช้ snapshot ปี 2026; XV2 ใช้ as-of 2023 ซึ่งอยู่ในช่วง α จึงตัดข้อนี้ไม่ได้) · ลักษณะ active/ธีม · "
     "ห้ามเขียนว่า 'ค่าธรรมเนียม 1 บาททำให้ α ลด 2.4 บาท' · **DIV** = ผลของ NAV ที่ไม่รวมปันผล (ขนาดใกล้ dividend yield · ประมาณจากกอง E ที่ปันผลราว 12–13 กอง) **ไม่ใช่ α**\n",
     "## E. ความคาดหมายที่ประเมินใหม่ (ข้อ 7/9/10/11/13/16/20 · ตรวจกับประเมินของ reviewer และตัวเลขใน results.md/CSV)\n", md(re_eval),
     "รวมทุกข้อ (ประเมินร่วมกับ reviewer): ตรง 5 [14, 15, 18, 19, 20*] · ไม่ตรง 13 [1–12, 17] · บางส่วน 2 [13, 16] — ข้อ 13: Spearman ≥ 0.8 ตรง แต่ BH รายเดือนมากกว่ารายสัปดาห์ (ดู C) → บางส่วน · *ข้อ 20 ตรงเฉพาะเกณฑ์ที่ปรับหลังเห็นผล (เกณฑ์เดิม = ไม่ตรง) → สรุป: ความคาดหมายล่วงหน้าพลาดเกือบทั้งหมด\n",
     "## F. ป้ายและขอบเขต\n- **decisions_pre_run.md ข้อ 9 และ 16** เป็นการตัดขอบเขตแบบมีเงื่อนไข เขียนหลังรัน smoke บนข้อมูลจริงอย่างน้อย 1 ครั้ง — **นับเป็นการตัดสินใจล่วงหน้าไม่ได้**; ไฟล์ `decisions_pre_run.md` ถูกบันทึกก่อน fit ของรอบรายงานแต่หลังการรันข้อมูลจริง (smoke) ข้อเสนอชั้นถัดไป: เขียน decisions ก่อน smoke ครั้งแรก หรือรัน smoke บนข้อมูลจำลอง\n"
     "- **rolling 104 และ PY bootstrap ของ ref-③a เกินสเปก** (S008 D.2 สั่ง 'ไม่ทำ') → เชิงบรรยายเท่านั้น\n- **G-T (ธีมของ ACWI_CD)** ไม่ได้ทำ → ย้ายไปข้อจำกัด (ส่วนบรรยายตาม spec · ไม่กระทบ Q1 / Q2 / Q3)\n"
     "- ไฟล์ใหม่ทั้งหมดเป็น 'ทำหลังเห็นผล' · ไม่มีรูปแบบใหม่ที่ใช้ตัดสินแทนเกณฑ์ที่ล็อก\n"]
(OUT / "results_addendum.md").write_text("\n".join(L), encoding="utf-8")
log("เสร็จ addendum")
