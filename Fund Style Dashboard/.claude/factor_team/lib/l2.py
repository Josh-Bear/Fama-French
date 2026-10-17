"""l2 — เครื่องมือ L2 (factor × MSCI) ตาม S004 + addendum S005 · ไม่แก้ฟังก์ชันของ L1"""
import numpy as np
import pandas as pd
from scipy import stats
from scipy.cluster.hierarchy import linkage, fcluster
from scipy.linalg import null_space
from scipy.spatial.distance import squareform

import io_l1
import regress as rg
import tests_stat as ts
from external import REGION_IDX
from fundff import single_index_r2
from pca import sign_fix
from samples import _components

S003_FAC_SHA = "be3ceb2e34b0df1f1a3db27d59e1a103cf5f5a5ca38f2e87f7c812c1c53944ac"
S4 = ["Momentum", "Quality", "Value", "LowVol"]
X7 = ["Oil_Brent", "Copper", "DXY", "GOLD", "FX", "VIX_d", "US10Y_d"]
INVESTABLE_X = ["GOLD", "FX"]


# ───────────── ดัชนี ─────────────
def index_set(F):
    """factors raw → (I_L2 DataFrame 39 ตัว, blocks dict ของรายชื่อคอลัมน์) ตามข้อ 2.2"""
    g = pd.read_csv(io_l1.DATA / "factor_groups.csv")
    m28 = [c for c, grp in zip(g["factor"], g["group"]) if grp in ("MSCI_country", "MSCI_sector")]
    rf = F["RF_BOT"]
    I = pd.DataFrame(index=F.index)
    for c in m28:
        I[c] = F[c] - rf
    for c in S4:
        I[c] = F[c]
    I["Oil_Brent"] = F["Oil_Brent"]
    I["Copper"] = F["Copper"]
    I["DXY"] = F["DXY"]
    I["GOLD"] = F["Gold_THB"] - rf
    I["FX"] = F["SHV_THB"] - rf
    I["VIX_d"] = F["VIX_d"]
    I["US10Y_d"] = F["US10Y_d"]
    blocks = dict(M28=list(m28), S4=list(S4), X7=list(X7), REG8=list(REGION_IDX), I_inv=list(m28) + S4 + INVESTABLE_X)
    return I, blocks


def load_l1_factors(path, form, expect_sha=S003_FAC_SHA):
    """อ่าน factors_S003_weekly.parquet (ตรวจ sha256 ก่อน) → คอลัมน์ของ form (ตัดคำนำหน้า)"""
    sha = io_l1.sha256_file(path)
    if expect_sha and sha != expect_sha:
        raise ValueError("sha256 factors_S003_weekly ไม่ตรง spec")
    df = pd.read_parquet(path)
    cols = [c for c in df.columns if c.startswith(form + "__")]
    out = df[cols].copy()
    out.columns = [c.split("__", 1)[1] for c in cols]
    return out


def fund_sets(R, U, dup):
    """ชุดกองเหมือน S003 → dict"""
    import samples as sp
    keep = sp.dedup_keep(dup, U.loc[R.columns, "n_weeks"])
    pol = U["policy"]
    base = sp.eligible(R, "unbalanced", keep)
    bal = sp.eligible(R, "balanced", keep)
    EVAL = sp.eligible(R, "EVAL", keep)
    balset = set(bal)
    return dict(keep=keep, base=base, bal=bal, EVAL=EVAL, STAB=sp.eligible(R, "STAB", keep),
                PYTE=sp.eligible(R, "PY_test", keep), PYTR=sp.eligible(R, "PY_train", keep),
                E67=[c for c in EVAL if c not in balset and pol[c] == "E"])


# ───────────── span / design ─────────────
def _dim(df):
    return rg.dimson_design(df if isinstance(df, pd.DataFrame) else df.to_frame())


def _resid_frac(Xb, Y):
    """ส่วนที่เหลือสัมพัทธ์ (‖e‖/‖Y−Ȳ‖) ของคอลัมน์ Y หลัง project บน Xb (มีค่าคงที่)"""
    b = np.linalg.lstsq(Xb, Y, rcond=None)[0]
    e = Y - Xb @ b
    nrm = np.linalg.norm(Y - Y.mean(0), axis=0)
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.linalg.norm(e, axis=0) / nrm


def _base_rows(Fbase, col):
    Db = _dim(Fbase).to_numpy()
    Dc = _dim(col).to_numpy()
    ok = np.isfinite(Db).all(1) & np.isfinite(Dc).all(1)
    return Db[ok], Dc[ok]


def in_span(Fbase, col, tol=1e-10):
    """rank ของ [1, D_base, D_col] ไม่เพิ่ม (ทั้ง I_t และ I_t−1 อยู่ใน span ของ [1, D_base])"""
    Db, Dc = _base_rows(Fbase, col)
    Xb = np.column_stack([np.ones(len(Db)), Db])
    return bool(np.all(_resid_frac(Xb, Dc) <= tol))


def near_dup_r2(Fbase, col, mask_tr):
    """min ของ R² ของ I_t และ I_t−1 บน [1, D_base] (train)"""
    Db = _dim(Fbase).to_numpy()
    Dc = _dim(col).to_numpy()
    ok = np.asarray(mask_tr, bool) & np.isfinite(Db).all(1) & np.isfinite(Dc).all(1)
    Xb = np.column_stack([np.ones(ok.sum()), Db[ok]])
    fr = _resid_frac(Xb, Dc[ok])
    return float(np.min(1.0 - fr ** 2))


class AugmentedFactors:
    """provider สำหรับ fit_funds: base (+ extra ร่วม) (+ per_fund dict กอง→Series) · layout [cur…|lag…]"""

    def __init__(self, base, extra=None, per_fund=None):
        self.common = base if extra is None else pd.concat([base, extra], axis=1)
        self.per_fund = per_fund
        self.index = self.common.index
        self.names = list(self.common.columns) + (["PRIM"] if per_fund is not None else [])
        self.K = len(self.names)
        self._cur = self.common.to_numpy(float)
        self._D = rg.lag_stack(self._cur)
        self._T = len(self.index)

    def design(self, code=None):
        if self.per_fund is None:
            return self._D
        s = self.per_fund.get(code)
        if s is None:
            return np.full((self._T, 2 * self.K), np.nan)
        x = np.asarray(s, float).reshape(-1, 1)
        cur = np.hstack([self._cur, x])
        return np.hstack([cur, rg.lag_stack(cur)[:, cur.shape[1]:]])


def primary_index(R, IDX, mask, funds, base=None):
    """argmax R² (Dimson ตัวเดียว · train) ต่อกอง · เสมอ → ลำดับคอลัมน์ · ถ้า in_span กับ base → อันดับถัดไป"""
    cols = list(IDX.columns)
    r2 = single_index_r2(R, IDX, mask, funds)
    cache = {}
    rows = []
    for code in funds:
        v = r2.loc[code].to_numpy(float)
        order = np.argsort(-np.where(np.isfinite(v), v, -np.inf), kind="stable")
        rank, skipped, chosen = 0, [], None
        for j in order:
            if not np.isfinite(v[j]):
                break
            rank += 1
            if base is not None:
                if cols[j] not in cache:
                    cache[cols[j]] = in_span(base, IDX[cols[j]])
                if cache[cols[j]]:
                    skipped.append(cols[j])
                    continue
            chosen = j
            break
        rows.append(dict(FundCode=code, index=cols[chosen] if chosen is not None else None,
                         r2=float(v[chosen]) if chosen is not None else np.nan, rank_used=rank if chosen is not None else 0,
                         skipped_reason=";".join(skipped)))
    return pd.DataFrame(rows)


def common_primary(prim_long):
    """prim_long: DataFrame (form, FundCode, rank_used) → Series bool ต่อกอง: rank_used = 1 ในทุกฐาน"""
    return prim_long.groupby("FundCode")["rank_used"].apply(lambda s: bool((s == 1).all()))


def wald_subset(coef, V, idx):
    idx = np.asarray(idx, int)
    b = np.asarray(coef, float)[idx]
    Vs = np.asarray(V, float)[np.ix_(idx, idx)]
    W = float(b @ np.linalg.solve(Vs, b))
    return W, len(idx), float(stats.chi2.sf(W, len(idx)))


def wald_p_dfadj(W, q, n, p):
    """F_adj = (W/q)(n−p)/n · p_adj = F.sf(F_adj, q, n−p)"""
    Fa = (np.asarray(W, float) / q) * (n - p) / n
    return stats.f.sf(Fa, q, n - p)


def _r2_oos_rows(y, yh):
    return rg.r2_oos(y, yh)


def _scan_core(R, base, IDX, mask_tr, mask_te, funds, L, skip, min_rows=52):
    Dbase = rg.lag_stack(base.to_numpy(float))
    Kb = base.shape[1]
    p0 = 1 + 2 * Kb
    mask_tr = np.asarray(mask_tr, bool)
    mask_te = None if mask_te is None else np.asarray(mask_te, bool)
    Rv = R[list(funds)].to_numpy(float)
    cols = list(IDX.columns)
    Dcol = {c: rg.lag_stack(IDX[[c]].to_numpy(float)) for c in cols}
    fb_ok = np.isfinite(Dbase).all(1)
    out = []
    for i, code in enumerate(funds):
        y = Rv[:, i]
        ok0 = mask_tr & np.isfinite(y) & fb_ok
        n0 = int(ok0.sum())
        rb0 = None
        if n0 >= max(min_rows, p0 + 5):
            rb0 = rg.ols_hac(y[ok0], np.column_stack([np.ones(n0), Dbase[ok0]]), L)
        for c in cols:
            row = dict(FundCode=code, index=c, n=np.nan, p_cols=p0 + 2, W=np.nan, p=np.nan, p_adj=np.nan, d_adj_r2=np.nan,
                       d_r2_oos=np.nan, d_bic=np.nan, adj_r2_base=np.nan, adj_r2_aug=np.nan, r2_oos_base=np.nan,
                       r2_oos_aug=np.nan, defn_dup=bool(skip.get(c, False)))
            if row["defn_dup"] or rb0 is None:
                out.append(row)
                continue
            ok = ok0 & np.isfinite(Dcol[c]).all(1)
            n = int(ok.sum())
            if n < max(min_rows, p0 + 5):
                out.append(row)
                continue
            Xb = np.column_stack([np.ones(n), Dbase[ok]])
            rb = rb0 if n == n0 else rg.ols_hac(y[ok], Xb, L)
            Xa = np.column_stack([Xb, Dcol[c][ok]])
            ra = rg.ols_hac(y[ok], Xa, L)
            W, _, p = wald_subset(ra["coef"], ra["V"], [p0, p0 + 1])
            bic = lambda r: n * np.log(r["ssr"] / n) + r["p"] * np.log(n)
            row.update(n=n, p_cols=Xa.shape[1], W=W, p=p, p_adj=float(wald_p_dfadj(W, 2, n, Xa.shape[1])),
                       d_adj_r2=ra["adj_r2"] - rb["adj_r2"], d_bic=bic(ra) - bic(rb), adj_r2_base=rb["adj_r2"],
                       adj_r2_aug=ra["adj_r2"])
            if mask_te is not None:
                te = mask_te & np.isfinite(y) & fb_ok & np.isfinite(Dcol[c]).all(1)
                if te.sum() >= 2:
                    ob = rg.r2_oos(y[te], rg.predict_oos(rb["coef"], Dbase[te]))
                    oa = rg.r2_oos(y[te], rg.predict_oos(ra["coef"], np.hstack([Dbase[te], Dcol[c][te]])))
                    row.update(r2_oos_base=ob, r2_oos_aug=oa, d_r2_oos=oa - ob)
            out.append(row)
    return pd.DataFrame(out)


def span_flags(base, IDX):
    return {c: in_span(base, IDX[c]) for c in IDX.columns}


def incremental_scan(R, base, IDX, mask_tr, mask_te, funds, L=4, min_rows=52):
    """ต่อกอง × ดัชนี: base vs base + I_j (Dimson) บนแถวเดียวกัน → ΔadjR², ΔR²_oos, ΔBIC, Wald(b0_j,b1_j), p_adj"""
    return _scan_core(R, base, IDX, mask_tr, mask_te, funds, L, span_flags(base, IDX), min_rows)


def circular_shift(I, mask_tr, s):
    """เลื่อนวนภายในบล็อก train (นอก train = NaN)"""
    pos = np.where(np.asarray(mask_tr, bool))[0]
    n = len(pos)
    arr = np.full(I.shape, np.nan)
    vals = I.to_numpy(float)[pos]
    arr[pos] = vals[(np.arange(n) + s) % n]
    return pd.DataFrame(arr, index=I.index, columns=I.columns)


def placebo_scan(R, base, IDX, mask_tr, funds, shifts=(26, 52), L=4, skip=None, min_rows=52):
    skip = span_flags(base, IDX) if skip is None else skip
    parts = []
    for s in shifts:
        d = _scan_core(R, base, circular_shift(IDX, mask_tr, s), mask_tr, None, funds, L, skip, min_rows)
        d.insert(0, "shift", s)
        parts.append(d)
    return pd.concat(parts, ignore_index=True)


def placebo_rule(summary, thr=0.08):
    """summary: DataFrame คอลัมน์ frac_p05, frac_padj05 (ทุก (S,s)) → dict(R0, R1, step)"""
    R0 = float(np.max(summary["frac_p05"]))
    R1 = float(np.max(summary["frac_padj05"]))
    step = 1 if R0 <= thr else (2 if R1 <= thr else 3)
    return dict(R0=R0, R1=R1, step=step)


def fund_clusters(R, mask_tr, funds, thr=0.95, min_overlap=52):
    funds = list(funds)
    X = R.loc[np.asarray(mask_tr, bool), funds]
    A = X.corr(min_periods=min_overlap).to_numpy()
    ia, ib = np.triu_indices(len(funds), 1)
    sel = np.isfinite(A[ia, ib]) & (A[ia, ib] >= thr)
    pairs = [(funds[a], funds[b]) for a, b in zip(ia[sel], ib[sel])]
    comps = _components(pairs, sorted(funds))
    comps = sorted([sorted(c) for c in comps], key=lambda c: c[0])
    rows = []
    for gid, c in enumerate(comps, 1):
        for code in c:
            rows.append(dict(FundCode=code, group_id=gid, group_size=len(c)))
    return pd.DataFrame(rows).sort_values("FundCode", kind="stable").reset_index(drop=True)


def canon_oos(f, I, mask_tr, mask_te):
    """canonical corr ระหว่าง f กับ I (train · lag 0) + น้ำหนักตรึงใช้ใน test"""
    fv, Iv = f.to_numpy(float), I.to_numpy(float)
    mtr = np.asarray(mask_tr, bool) & np.isfinite(fv).all(1) & np.isfinite(Iv).all(1)
    mte = np.asarray(mask_te, bool) & np.isfinite(fv).all(1) & np.isfinite(Iv).all(1)
    A, Bm = fv[mtr], Iv[mtr]
    ma, mb = A.mean(0), Bm.mean(0)
    qa, ra = np.linalg.qr(A - ma)
    qb, rb = np.linalg.qr(Bm - mb)
    U, S, Vt = np.linalg.svd(qa.T @ qb, full_matrices=False)
    c = A.shape[1]
    wa = np.linalg.solve(ra, U[:, :c])
    wb = np.linalg.solve(rb, Vt.T[:, :c])
    ua, vb = (fv[mte] - ma) @ wa, (Iv[mte] - mb) @ wb
    rho_oos = [float(np.corrcoef(ua[:, j], vb[:, j])[0, 1]) for j in range(c)]
    return pd.DataFrame(dict(c=np.arange(1, c + 1), rho_train=S[:c], rho_oos=rho_oos))


def reverse_span(I, f, mask_tr, mask_te, lead=1):
    """I_j,t ~ f_t (+ f_t+1) · lead=1: ตัดแถว train ที่ f_t+1 อยู่นอก train · test ตกแถวที่ไม่มี f_t+1"""
    Fv = f.to_numpy(float)
    mask_tr, mask_te = np.asarray(mask_tr, bool), np.asarray(mask_te, bool)
    if lead:
        X = np.hstack([Fv, np.vstack([Fv[1:], np.full((1, Fv.shape[1]), np.nan)])])
        mtr = mask_tr & np.r_[mask_tr[1:], False]
        mte = mask_te
    else:
        X, mtr, mte = Fv, mask_tr, mask_te
    fin = np.isfinite(X).all(1)
    rows = []
    for c in I.columns:
        y = I[c].to_numpy(float)
        ok = mtr & fin & np.isfinite(y)
        ot = mte & fin & np.isfinite(y)
        Xt = np.column_stack([np.ones(ok.sum()), X[ok]])
        b = np.linalg.lstsq(Xt, y[ok], rcond=None)[0]
        e = y[ok] - Xt @ b
        n, p = Xt.shape
        r2 = 1 - e @ e / ((y[ok] - y[ok].mean()) ** 2).sum()
        adj = 1 - (1 - r2) * (n - 1) / (n - p)
        yh = b[0] + X[ot] @ b[1:]
        rows.append(dict(index=c, r2=r2, adj_r2=adj, r2_oos=rg.r2_oos(y[ot], yh), n_tr=int(n), n_te=int(ot.sum()), p=p))
    return pd.DataFrame(rows).set_index("index")


def forward_span(f, blocks, mask_tr, mask_te, L=4, tol=1e-10):
    """factor ~ บล็อกดัชนี (Dimson) → R², adj R², R²_oos, α, t_α(HAC) · bh_family เฉพาะ B1 ที่ไม่เชิงนิยาม"""
    mask_tr, mask_te = np.asarray(mask_tr, bool), np.asarray(mask_te, bool)
    rows = []
    for bn, B in blocks.items():
        D = rg.lag_stack(B.to_numpy(float))
        fin = np.isfinite(D).all(1)
        for fk in f.columns:
            y = f[fk].to_numpy(float)
            ok = mask_tr & fin & np.isfinite(y)
            r = rg.ols_hac(y[ok], np.column_stack([np.ones(ok.sum()), D[ok]]), L)
            te = mask_te & fin & np.isfinite(y)
            r2o = rg.r2_oos(y[te], rg.predict_oos(r["coef"], D[te]))
            defn = bool(np.sqrt(max(1 - r["r2"], 0)) <= tol)
            rows.append(dict(factor=fk, block=bn, n=r["n"], p=r["p"], r2=r["r2"], adj_r2=r["adj_r2"], r2_oos=r2o,
                             alpha_pct_yr=r["coef"][0] * 5200, t_alpha=r["t"][0], defn=defn,
                             bh_family=bool(bn == "B1" and not defn)))
    return pd.DataFrame(rows)


def index_clusters(I, mask_tr, cut=0.10):
    X = I.to_numpy(float)[np.asarray(mask_tr, bool)]
    X = X[np.isfinite(X).all(1)]
    C = np.corrcoef(X, rowvar=False)
    vif = np.diag(np.linalg.inv(C))
    D = 1.0 - np.abs(C)
    np.fill_diagonal(D, 0.0)
    D = (D + D.T) / 2
    Z = linkage(squareform(D, checks=False), method="complete")
    cl = fcluster(Z, t=cut, criterion="distance")
    return pd.DataFrame(dict(index=list(I.columns), r2_on_others=1 - 1 / vif, vif=vif, cluster=cl))


def by(pvals, q=0.10):
    """Benjamini–Yekutieli · คืน (reject, adj p)"""
    p = np.asarray(pvals, float)
    c = float(np.sum(1.0 / np.arange(1, len(p) + 1)))
    _, adj = ts.bh(p, q)
    adj = np.minimum(adj * c, 1.0)
    return adj <= q, adj


def holm(p):
    p = np.asarray(p, float)
    n = len(p)
    o = np.argsort(p, kind="stable")
    adj = np.maximum.accumulate(np.minimum(np.sort(p) * (n - np.arange(n)), 1.0))
    out = np.empty(n)
    out[o] = adj
    return out


def target_rotation(f, I, mask_tr, k, min_score=0.25, order=None):
    """oblique target rotation (least-squares projection) ตามข้อ 3.1 ค — ใช้ตั้งชื่อเท่านั้น"""
    cols = list(I.columns) if order is None else list(order)
    fv, Iv = f.to_numpy(float), I[cols].to_numpy(float)
    ok = np.asarray(mask_tr, bool) & np.isfinite(fv).all(1) & np.isfinite(Iv).all(1)
    fc = fv[ok] - fv[ok].mean(0)
    Ic = Iv[ok] - Iv[ok].mean(0)
    Ball = np.linalg.lstsq(fc, Ic, rcond=None)[0]
    G = fc @ Ball
    r20 = 1 - ((Ic - G) ** 2).sum(0) / (Ic ** 2).sum(0)
    C, scores = [], []
    for _ in range(k):
        best, bs = None, -np.inf
        for j in range(len(cols)):
            if j in C:
                continue
            if C:
                Gc = G[:, C]
                b = np.linalg.lstsq(Gc, G[:, j], rcond=None)[0]
                e = G[:, j] - Gc @ b
                r2c = 1 - (e @ e) / (G[:, j] @ G[:, j]) if G[:, j] @ G[:, j] > 0 else 1.0
            else:
                r2c = 0.0
            s = r20[j] * (1 - r2c)
            if s > bs:
                best, bs = j, s
        if best is None or bs < min_score:
            break
        C.append(best)
        scores.append(float(bs))
    m = len(C)
    Bc = Ball[:, C] if m else np.zeros((k, 0))
    names = [cols[j] for j in C]
    if m < k:
        Sig = fc.T @ fc / len(fc)
        N = np.eye(k) if m == 0 else null_space(Bc.T @ Sig)
        w, U = np.linalg.eigh(N.T @ Sig @ N)
        o = np.argsort(w)[::-1]
        V = sign_fix(N @ U[:, o])[:, : k - m]
        B = np.hstack([Bc, V])
        names += [f"R-ไม่มีเป้า{i + 1}" for i in range(k - m)]
    else:
        B = Bc
    f_rot = pd.DataFrame(fv @ B, index=f.index, columns=names)
    return dict(targets=[cols[j] for j in C], scores=scores, r2_0=[float(r20[j]) for j in C], B=B, f_rot=f_rot, names=names)


def count_groups(sig_funds, gmap):
    """จำนวน group_id ไม่ซ้ำของกองที่ significant · gmap: dict/Series FundCode→group_id"""
    return len({gmap[c] for c in sig_funds})


def deltas(fit_a, ro_a, fit_b, ro_b):
    """Δ = aug − base รายกอง (ต้องเป็นกองลำดับเดียวกัน · k เดียวกัน) → dict array"""
    assert list(fit_a.codes) == list(fit_b.codes)
    return dict(d_adj_r2=fit_a.adj_r2 - fit_b.adj_r2, d_r2_oos=np.asarray(ro_a) - np.asarray(ro_b), d_bic=fit_a.bic - fit_b.bic,
                d_abs_alpha_pct=(np.abs(fit_a.alpha) - np.abs(fit_b.alpha)) * 5200)


def rolling_betas(R, provider, funds, base_mask, window=104, step=4, min_obs=78, full_min=100, last_start=156):
    """β̂ (b0+b1) รายกองในหน้าต่างเลื่อน `window` สัปดาห์ (เริ่ม 0,step,…,last_start ภายใน base_mask) + β เต็มช่วง
    → (W x N x K, N x K, starts) · ใช้กับ scorecard.stability_rolling"""
    base_mask = np.asarray(base_mask, bool)
    T = len(base_mask)
    starts = list(range(0, last_start + 1, step))
    bw = []
    for s in starts:
        mk = np.zeros(T, bool)
        mk[s:s + window] = True
        bw.append(rg.fit_funds(R, provider, mk & base_mask, min_obs, funds=funds).beta)
    full = rg.fit_funds(R, provider, base_mask, full_min, funds=funds).beta
    return np.array(bw), full, starts
