"""factor-reviewer — ตรวจผล S003 (อ่านอย่างเดียว · ไม่เขียนใน runs/)
1) ED/IC/ER sensitivity ต่อ kmax และ jackknife กอง  2) ①a ที่ k อื่น: เกณฑ์ c1/c2/c3 (E)
3) PY null bootstrap (③b test, ①a test, ③a test)  4) spot check ตัวเลข"""
import sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))
import io_l1, samples as sp, regress as rg, tests_stat as ts, forms as fm_  # noqa
from nfactors import corr_eig, bai_ng_ic, ahn_horenstein, onatski_ed, combine_k  # noqa
from samples import window_mask  # noqa

R = io_l1.load_returns("W"); F = io_l1.load_factors("W")
U = io_l1.load_universe().set_index("FundCode"); pol = U["policy"]
keep = sp.dedup_keep(io_l1.load_dup_pairs(), U.loc[R.columns, "n_weeks"])
base = sp.eligible(R, "unbalanced", keep); bal = sp.eligible(R, "balanced", keep)
EVAL = sp.eligible(R, "EVAL", keep); STAB = sp.eligible(R, "STAB", keep); PYTE = sp.eligible(R, "PY_test", keep)
idx = R.index; POS = np.arange(len(idx))
mtr, mte = window_mask(idx, "train"), window_mask(idx, "test")

# ---------- 1) ED sensitivity ----------
Xb = R.loc[mtr, bal].to_numpy(float); T, N = Xb.shape
Z = (Xb - Xb.mean(0)) / Xb.std(0, ddof=0)
eig = corr_eig(Z)
print("N,T", N, T, "eig1..12", np.round(eig[:12], 3))
print("gaps", np.round(-np.diff(eig[:12]), 3))
for km in (4, 5, 6, 8, 10, 12, 15, 20):
    print(f"kmax={km}: IC_p2={bai_ng_ic(eig, N, T, km, 'p2')} ER/GR={ahn_horenstein(eig, km)} ED={onatski_ed(eig, km)}")
PA = 6
for ed in range(0, 11):
    print("ถ้า ED =", ed, "→ k* =", combine_k([10, 1, ed, PA]))
rng = np.random.default_rng(1)
jk = []
for i in range(N):
    Zi = np.delete(Z, i, axis=1); e = corr_eig(Zi)
    jk.append((bai_ng_ic(e, N - 1, T, 10, "p2"), ahn_horenstein(e, 10)[0], onatski_ed(e, 10)))
jk = pd.DataFrame(jk, columns=["IC", "ER", "ED"])
print("jackknife กอง (ลบทีละกอง):", {c: jk[c].value_counts().to_dict() for c in jk})
# bootstrap สัปดาห์ (block 4) → ED
eds = []
for b in range(300):
    st = rng.integers(0, T - 4, size=T // 4 + 1)
    rows = np.concatenate([np.arange(s, s + 4) for s in st])[:T]
    Zb = Z[rows]; Zb = (Zb - Zb.mean(0)) / Zb.std(0)
    e = corr_eig(Zb); eds.append((onatski_ed(e, 10), combine_k([bai_ng_ic(e, N, T, 10, 'p2'), ahn_horenstein(e, 10)[0], onatski_ed(e, 10), PA])))
eds = pd.DataFrame(eds, columns=["ED", "kstar_PA6"])
print("block-bootstrap สัปดาห์ ED:", eds.ED.value_counts().sort_index().to_dict(), "k*(PA=6 คงที่):", eds.kstar_PA6.value_counts().sort_index().to_dict())

# ---------- 2) ①a ที่ k อื่น ----------
POOL = sorted(EVAL)
polE = (pol.loc[POOL] == "E").to_numpy()
stE = [c for c in STAB if pol[c] == "E"]
fk = fm_.build_line1_k(R, bal, [2, 3, 4, 5, 6])
for k, df in fk.items():
    prov = rg.CommonFactors(df)
    fit = rg.fit_funds(R, prov, mtr, 52, funds=POOL)
    oo = np.asarray(rg.oos_r2_funds(R, prov, fit, mte), float)
    r2tr = np.asarray(fit.r2, float)
    adj = np.asarray(fit.adj_r2, float)
    h1 = rg.fit_funds(R, prov, window_mask(idx, "H1") & (POS >= 1), 104, funds=stE)
    h2 = rg.fit_funds(R, prov, window_mask(idx, "H2"), 104, funds=stE)
    rr = [pd.Series(h1.beta[:, j]).corr(pd.Series(h2.beta[:, j])) for j in range(k)]
    print(f"k={k}: adjR2_E={np.nanmedian(adj[polE]):.3f} r2oos_E={np.nanmedian(oo[polE]):.3f} "
          f"gap_E={np.nanmedian((r2tr - oo)[polE]):.3f} r_raw_E mean={np.mean(rr):.3f} per={np.round(rr, 3)}")

# ---------- 3) PY null bootstrap ----------
import external as ex  # noqa


def py_null(df, funds, mask, B=300, seed=7):
    prov = rg.CommonFactors(df)
    D = np.asarray(prov.design(funds[0]), float)
    mk = mask & np.isfinite(D).all(1)
    Y = R.loc[mk, funds].to_numpy(float)
    okc = np.isfinite(Y).all(0); Y = Y[:, okc]
    X = np.column_stack([np.ones(mk.sum()), D[mk]])
    Tn, p = X.shape; m = p - 1
    XtXi = np.linalg.inv(X.T @ X)

    def J_of(Yy):
        Bh = XtXi @ X.T @ Yy; E = Yy - X @ Bh
        s2 = (E ** 2).sum(0) / (Tn - p)
        t = Bh[0] / np.sqrt(s2 * XtXi[0, 0])
        return ts.pesaran_yamagata(t, E, Tn, m)
    r0 = J_of(Y)
    Bh = XtXi @ X.T @ Y; E = Y - X @ Bh; fitted0 = X[:, 1:] @ Bh[1:]
    g = np.random.default_rng(seed); Js = []
    for _ in range(B):
        rows = g.integers(0, Tn, Tn)
        Ec = E[rows]  # ไม่ center ต่อรอบ (center ทำให้ var(α̂*) หด)
        Js.append(J_of(fitted0 + Ec)["J"])
    Js = np.array(Js)
    return r0, Js


for nm in ("3b", "3a"):
    df = ex.line3(F, nm)
    r0, Js = py_null(df, PYTE, mte)
    print(f"PY {nm} test: J={r0['J']:.3f} p_N01={r0['p']:.3f} N={r0['N']} v={r0['v']} | null bootstrap: rej5%={np.mean(Js > 1.645):.3f} "
          f"q95={np.quantile(Js, .95):.3f} mean={Js.mean():.3f} sd={Js.std():.3f} p_boot={np.mean(Js >= r0['J']):.3f}")
fa = fk[4]
r0, Js = py_null(fa, PYTE, mte)
print(f"PY 1a(k4) test: J={r0['J']:.3f} p={r0['p']:.3f} | null rej5%={np.mean(Js > 1.645):.3f} q95={np.quantile(Js, .95):.3f}")

# ---------- 4) spot checks ----------
fl = pd.read_csv(ROOT / "runs/S003/fund_level.csv")
print("fund_level cols:", list(fl.columns)[:25])
rg_ = pd.read_csv(ROOT / "runs/S003/regions.csv")
uni = pd.read_csv(ROOT / "data/universe.csv")
namecol = [c for c in uni.columns if "name" in c.lower() or "abbr" in c.lower()]
fl_ = rg_[rg_.nonFX_eq == True].merge(uni[["FundCode"] + namecol[:2]], on="FundCode", how="left")
print(fl_[["FundCode"] + namecol[:2] + ["max_r2", "label_post", "r2_gold", "r2_tdex", "flag_reason", "r2_MSCI_ASIA_EX_JAPAN", "r2_MSCI_ACWI"]].to_string())
