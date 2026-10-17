"""fundff — สาย ② Fama-French ของกองทุน: ภูมิภาค · FX beta · ธง nonFX_eq (N4) · long-short · LOO · MOM · พอร์ต GRS"""
import numpy as np
import pandas as pd

from external import REGION_IDX
from regress import fit_funds, lag_stack

OTHER = "OTHER"
ACWI = "MSCI_ACWI"


def single_index_r2(R, idxdf, mask, funds, cols=None, min_obs=30):
    """R² ของ Dimson regression ตัวเดียวต่อดัชนี (train) → DataFrame funds x ดัชนี"""
    cols = list(idxdf.columns) if cols is None else list(cols)
    out = {}
    for c in cols:
        out[c] = fit_funds(R, idxdf[[c]], mask, min_obs, funds=funds).r2
    return pd.DataFrame(out, index=list(funds))


def assign_region(r2tab, count_mask, r2_min=0.30, min_group=10, order=REGION_IDX):
    """ภูมิภาค = ดัชนี R² สูงสุด (เสมอ → ลำดับ) · max R² < r2_min → OTHER ·
    กฎรวมกลุ่มเดียว: ภูมิภาคที่มีกอง (count_mask) < min_group → OTHER · OTHER < min_group → MSCI_ACWI
    คืน DataFrame(max_r2, label_pre, label_post)"""
    T = r2tab[order]
    mx = T.max(axis=1)
    arg = np.nanargmax(T.to_numpy(float), axis=1)
    pre = pd.Series(np.array(order, dtype=object)[arg], index=T.index, dtype=object)
    pre[mx < r2_min] = OTHER
    post = pre.copy()
    cm = pd.Series(count_mask, index=T.index).astype(bool)
    cnt = pre[cm].value_counts()
    for g in [x for x in pre.unique() if x != OTHER]:
        if cnt.get(g, 0) < min_group:
            post[pre == g] = OTHER
    if int((post[cm] == OTHER).sum()) < min_group:
        post[post == OTHER] = ACWI
    return pd.DataFrame({"max_r2": mx, "label_pre": pre, "label_post": post})


def label_index(label):
    return ACWI if label == OTHER else label


def regional_stats(R, IDX, labels_post, r2tab, mask, funds, min_obs=30):
    """FX beta (Dimson x ~ [ดัชนีภูมิภาค, USDTHB] → b0+b1 ของ USDTHB) และ ACT = 1 − R² (ดัชนีภูมิภาคตัวเดียว)
    ดัชนีที่ใช้ = label_post (OTHER → ACWI)"""
    lab = labels_post.loc[list(funds)].map(label_index)
    fx = pd.Series(np.nan, index=list(funds))
    act = pd.Series(np.nan, index=list(funds))
    for g in sorted(lab.unique()):
        codes = list(lab.index[lab == g])
        fit = fit_funds(R, IDX[[g, "USDTHB"]], mask, min_obs, funds=codes)
        fx[codes] = fit.beta[:, 1]
        act[codes] = 1.0 - r2tab.loc[codes, g].to_numpy(float)
    return fx, act


def nonfx_flags(r2tab, r2_gold, r2_tdex, r2_min=0.30, order=REGION_IDX):
    """N4: (ก) max R² < 0.30 หรือ (ข) R² ทอง/TDEX > max R² ของ 8 ดัชนี → DataFrame(flag, reason)"""
    mx = r2tab[order].max(axis=1)
    a = mx < r2_min
    b = np.maximum(r2_gold, r2_tdex) > mx
    flag = a | b
    reason = pd.Series(np.where(a & b, "a+b", np.where(a, "a", np.where(b, "b", ""))), index=mx.index)
    return pd.DataFrame({"flag": flag, "reason": reason})


def sort_groups(label_post, flagged, members, min_group=10):
    """กลุ่มเรียงของ FXH/ACT (N4): เฉพาะกองไม่มีธง · กลุ่ม < min_group → ACWI · ACWI (ถ้ามีกอง) < min_group → กลุ่มเดียว"""
    nf = [c for c in members if not bool(flagged[c])]
    lab = label_post.loc[nf].copy()
    grp = lab.copy()
    cnt = lab.value_counts()
    for g in cnt.index:
        if g != ACWI and cnt[g] < min_group:
            grp[lab == g] = ACWI
    n_acwi = int((grp == ACWI).sum())
    if 0 < n_acwi < min_group:
        grp[:] = "ALL"
    return grp


def sort_legs(char, groups, pos="low", q=(0.3, 0.7)):
    """เรียงภายในกลุ่ม: ต่ำ 30% / สูง 30% (stable, เสมอ → FundCode) · คืน Series +1 = ขา pos · −1 = ขาตรงข้าม · 0 = กลาง
    groups: Series (index = กองที่ถูกเรียง) · char NaN ถูกข้าม"""
    lab = pd.Series(0, index=groups.index, dtype=int)
    for g in sorted(groups.unique()):
        codes = list(groups.index[groups == g])
        df = pd.DataFrame({"v": char.reindex(codes), "c": codes}).dropna(subset=["v"]).sort_values(["v", "c"], kind="stable")
        n = len(df)
        nl = int(np.floor(q[0] * n + 1e-9))
        nh = int(np.floor((1 - q[1]) * n + 1e-9))
        low = list(df["c"].iloc[:nl])
        high = list(df["c"].iloc[n - nh:]) if nh > 0 else []
        p, m = (low, high) if pos == "low" else (high, low)
        lab[p] = 1
        lab[m] = -1
    return lab


def momentum(R, form=52, skip=4, min_obs=40, rebalance="Q", q=(0.3, 0.7)):
    """MOM (52-4) รายไตรมาส: τ = สัปดาห์สุดท้ายใน index ของ มี.ค./มิ.ย./ก.ย./ธ.ค. · กองที่มี ≥ min_obs สัปดาห์ใน (τ−form, τ−skip] ·
    ผลตอบแทนทบต้น → 30/40/30 → ถือ τ+1..τ ถัดไป · ใช้ข้อมูล ≤ τ−skip เท่านั้น · คืน DataFrame T x N ค่า +1 (ผู้ชนะ) −1 (ผู้แพ้) 0"""
    idx = pd.DatetimeIndex(R.index)
    T = len(idx)
    ym = pd.Series(np.arange(T), index=idx).groupby([idx.year, idx.month]).max()
    taus = sorted(int(v) for (y, m), v in ym.items() if m in (3, 6, 9, 12))
    X = R.to_numpy(float)
    codes = list(R.columns)
    lab = np.zeros(X.shape, dtype=np.int8)
    for a, tau in enumerate(taus):
        lo = max(0, tau - form + 1)
        hi = tau - skip + 1
        if hi <= lo:
            continue
        W = X[lo:hi]
        cnt = np.isfinite(W).sum(axis=0)
        el = np.where(cnt >= min_obs)[0]
        if len(el) < 3:
            continue
        cum = np.array([np.prod(1.0 + W[np.isfinite(W[:, j]), j]) - 1.0 for j in el])
        order = sorted(range(len(el)), key=lambda i: (cum[i], codes[el[i]]))
        n = len(el)
        nl = int(np.floor(q[0] * n + 1e-9))
        nh = int(np.floor((1 - q[1]) * n + 1e-9))
        losers = [el[order[i]] for i in range(nl)]
        winners = [el[order[n - 1 - i]] for i in range(nh)]
        end = taus[a + 1] if a + 1 < len(taus) else T - 1
        for j in winners:
            lab[tau + 1:end + 1, j] = 1
        for j in losers:
            lab[tau + 1:end + 1, j] = -1
    return pd.DataFrame(lab, index=R.index, columns=codes)


class LegPair:
    """EW(ขา pos) − EW(ขา neg) พร้อม LOO · neg=None → EW ของ pos อย่างเดียว (APB) · pos/neg boolean (T x N) ·
    สมาชิก < min_n ในสัปดาห์ → NaN"""

    def __init__(self, Rm, pos, neg, min_n):
        ok = np.isfinite(Rm)
        self.v = np.where(ok, Rm, 0.0)
        self.pos = pos & ok
        self.neg = (neg & ok) if neg is not None else None
        self.min_n = min_n
        self.Sp = (self.v * self.pos).sum(1)
        self.Cp = self.pos.sum(1).astype(float)
        if self.neg is not None:
            self.Sn = (self.v * self.neg).sum(1)
            self.Cn = self.neg.sum(1).astype(float)

    def series(self, j=None):
        Sp, Cp = self.Sp, self.Cp
        if j is not None:
            Sp = Sp - self.v[:, j] * self.pos[:, j]
            Cp = Cp - self.pos[:, j]
        with np.errstate(divide="ignore", invalid="ignore"):
            mp = np.where(Cp >= self.min_n, Sp / Cp, np.nan)
        if self.neg is None:
            return mp
        Sn, Cn = self.Sn, self.Cn
        if j is not None:
            Sn = Sn - self.v[:, j] * self.neg[:, j]
            Cn = Cn - self.neg[:, j]
        with np.errstate(divide="ignore", invalid="ignore"):
            mn = np.where(Cn >= self.min_n, Sn / Cn, np.nan)
        return mp - mn


class Line2Provider:
    """factor ของสาย ② รายกอง (LOO ถ้า loo=True): .design(code) → (T x 2K) · .plain() → DataFrame (ไม่ LOO)"""

    def __init__(self, index, names, legs, col, loo=True):
        self.index = index
        self.names = list(names)
        self.K = len(names)
        self.legs = legs
        self.col = col
        self.loo = loo
        self._cache = {}

    def series(self, code=None):
        j = self.col.get(code) if (self.loo and code is not None) else None
        return np.column_stack([lp.series(j) for lp in self.legs])

    def design(self, code=None):
        key = code if (self.loo and code in self.col) else None
        if key not in self._cache:
            self._cache[key] = lag_stack(self.series(key))
        return self._cache[key]

    def plain(self):
        return pd.DataFrame(self.series(None), index=self.index, columns=self.names)


def line2_characteristics(R, members, pol, r2tab, fx, act, flag, aumlog, min_group=10):
    """ป้ายขา FXH/ACT/SIZE + MOM ของชุดสมาชิก `members` (นับเกณฑ์กลุ่ม < min_group ภายใน members) ·
    r2tab/fx/act/flag/aumlog = ค่ารายกองเดิม (คำนวณจาก train ของฐานเต็ม — ไม่คำนวณใหม่ในครึ่ง)"""
    members = list(members)
    E = [c for c in members if pol[c] == "E"]
    EO = [c for c in members if pol[c] in ("E", "O")]
    cm = pd.Series([pol[c] == "E" for c in EO], index=EO)
    reg = assign_region(r2tab.loc[EO], cm, min_group=min_group)
    grp = sort_groups(reg["label_post"], flag, E, min_group=min_group)
    nf = list(grp.index)
    fx_lab = sort_legs(fx.reindex(nf), grp, "low")
    act_lab = sort_legs(act.reindex(nf), grp, "high")
    size_lab = sort_legs(aumlog.reindex(E).dropna(), pd.Series("ALL", index=list(aumlog.reindex(E).dropna().index)), "low")
    mom = momentum(R[E])
    return dict(members=members, pol=pol, E=E, region=reg, sort_group=grp, fx=fx_lab, act=act_lab, size=size_lab, mom=mom)


def build_line2(R, chars, variant, loo=True, min_n=5):
    """variant: 'a' (APB_E,F,O) · 'b' (+FXH) · 'c' (+MOM,SIZE,ACT)"""
    members = chars["members"]
    pol = chars["pol"]
    Rm = R[members].to_numpy(float)
    T, N = Rm.shape
    col = {c: i for i, c in enumerate(members)}
    names, legs = [], []
    for g in ("E", "F", "O"):
        names.append(f"APB_{g}")
        pos = np.tile(np.array([pol[c] == g for c in members])[None, :], (T, 1))
        legs.append(LegPair(Rm, pos, None, min_n))

    def static(lab):
        p = np.array([lab.get(c, 0) == 1 for c in members])
        n = np.array([lab.get(c, 0) == -1 for c in members])
        return np.tile(p[None, :], (T, 1)), np.tile(n[None, :], (T, 1))

    if variant in ("b", "c"):
        p, n = static(chars["fx"])
        names.append("FXH")
        legs.append(LegPair(Rm, p, n, min_n))
    if variant == "c":
        m = chars["mom"].reindex(columns=members).fillna(0).to_numpy()
        names.append("MOM")
        legs.append(LegPair(Rm, m == 1, m == -1, min_n))
        p, n = static(chars["size"])
        names.append("SIZE")
        legs.append(LegPair(Rm, p, n, min_n))
        p, n = static(chars["act"])
        names.append("ACT")
        legs.append(LegPair(Rm, p, n, min_n))
    return Line2Provider(R.index, names, legs, col, loo=loo)


def ew_factor(R, members, exclude=None, min_n=5):
    """EW ของ members (ไม่รวม exclude) ต่อสัปดาห์ · สมาชิก < min_n → NaN"""
    m = [c for c in members if c != exclude]
    X = R[m].to_numpy(float)
    cnt = np.isfinite(X).sum(axis=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        mean = np.nanmean(np.where(np.isfinite(X), X, np.nan), axis=1) if X.size else np.full(len(R), np.nan)
    return pd.Series(np.where(cnt >= min_n, mean, np.nan), index=R.index)


def apb(R, policy, loo, members, min_n=5):
    """APB_g ของทุก policy (DataFrame T x 3) ถ้า loo=False · ถ้า loo=True คืน Line2Provider (APB เท่านั้น)"""
    pol = pd.Series(policy)
    chars = dict(members=list(members), pol=pol)
    prov = build_line2(R, chars, "a", loo=loo, min_n=min_n)
    return prov if loo else prov.plain()


def grs_portfolios(members, pol, reg_post, fx, sigma, max_ports=20, split_min=20):
    """พอร์ต GRS (≤ 20): E = กลุ่มภูมิภาคหลังรวม (reg_post: Series label_post ของสมาชิก) · กลุ่ม ≥ split_min กอง แบ่งครึ่งตามมัธยฐาน FX beta ·
    เกิน max_ports → ยกเลิกการแบ่งของกลุ่มที่เล็กสุดทีละกลุ่ม · F, O: 2 พอร์ตตามมัธยฐาน σ → Series code→ชื่อพอร์ต"""
    ports = {}
    E = [c for c in members if pol[c] == "E"]
    groups = {}
    for c in E:
        groups.setdefault(reg_post[c], []).append(c)
    splittable = sorted([g for g, v in groups.items() if len(v) >= split_min], key=lambda g: (len(groups[g]), g))
    do_split = list(splittable)
    while len(groups) + len(do_split) > max_ports and do_split:
        do_split.pop(0)
    for g, codes in groups.items():
        if g in do_split:
            med = float(np.median([fx[c] for c in codes]))
            for c in codes:
                ports[c] = f"E_{g}_{'hedged' if fx[c] <= med else 'unhedged'}"
        else:
            for c in codes:
                ports[c] = f"E_{g}"
    for pg in ("F", "O"):
        cs = [c for c in members if pol[c] == pg]
        if not cs:
            continue
        med = float(np.median([sigma[c] for c in cs]))
        for c in cs:
            ports[c] = f"{pg}_{'lo' if sigma[c] <= med else 'hi'}sigma"
    return pd.Series(ports)
