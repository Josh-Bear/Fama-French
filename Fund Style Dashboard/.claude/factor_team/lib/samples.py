"""samples — ชุดกอง / ช่วงเวลา / split-half (S002 ข้อ 2.3, 0, 4.2 ข)"""
import numpy as np
import pandas as pd

WINDOWS = {
    "train": ("2021-01-08", "2023-12-29"),
    "test": ("2024-01-05", "2025-12-26"),
    "H1": ("2021-01-08", "2023-06-30"),
    "H2": ("2023-07-07", "2025-12-26"),
    "train_c": ("2022-01-14", "2023-12-29"),
    "H1_c": ("2022-01-14", "2023-06-30"),
    "full": ("2021-01-08", "2025-12-26"),
    "full_c": ("2022-01-14", "2025-12-26"),
}
SEED = 20261015


def window_mask(index, name):
    """boolean array ตาม index (วันที่) — แถวที่ใช้เป็นตัวแปรตาม
    odd = สัปดาห์ลำดับที่ 1,3,5,... ของ index (pos 0,2,4..) · even = pos 1,3,5.. · odd_c/even_c ตัดให้อยู่ใน full_c"""
    idx = pd.DatetimeIndex(index)
    pos = np.arange(len(idx))
    if name in WINDOWS:
        s, e = WINDOWS[name]
        return np.asarray((idx >= pd.Timestamp(s)) & (idx <= pd.Timestamp(e)))
    if name in ("odd", "even", "odd_c", "even_c"):
        base = window_mask(idx, "full_c" if name.endswith("_c") else "full")
        par = (pos % 2 == 0) if name.startswith("odd") else (pos % 2 == 1)
        return base & par
    raise KeyError(name)


def _components(pairs, nodes):
    parent = {n: n for n in nodes}

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    for a, b in pairs:
        if a in parent and b in parent:
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[max(ra, rb)] = min(ra, rb)
    comp = {}
    for n in nodes:
        comp.setdefault(find(n), []).append(n)
    return list(comp.values())


def dedup_keep(dup_pairs, n_weeks):
    """1 กองต่อ connected component ของ dup_pairs (n_weeks มากสุด · เสมอ → FundCode ตามตัวอักษร)
    dup_pairs: DataFrame a,b · n_weeks: Series (index FundCode) · คืน list ที่เรียงตามตัวอักษร"""
    nodes = sorted(n_weeks.index)
    pairs = list(zip(dup_pairs["a"], dup_pairs["b"]))
    keep = []
    for comp in _components(pairs, nodes):
        best = sorted(comp, key=lambda c: (-int(n_weeks[c]), c))[0]
        keep.append(best)
    return sorted(keep)


def _rows(R, win):
    """จำนวนแถว Dimson ต่อกอง: ผลตอบแทนไม่ว่างใน window ตั้งแต่ pos>=1 (pos 0 ไม่มี lag)"""
    idx = R.index
    m = window_mask(idx, win).copy()
    m[0] = False
    return R.loc[m].notna().sum(axis=0), m


def eligible(R, rule, keep=None):
    """รายชื่อกองตามกติกา (R = excess return weekly ช่วงหลัก · keep = ชุดตัดซ้ำ)
    rules: unbalanced · balanced · EVAL · EVAL52 · FULL · STAB · PY_train · PY_test · PY_train_c · E67 ใช้ฟังก์ชันอื่น"""
    codes = list(R.columns) if keep is None else [c for c in R.columns if c in set(keep)]
    R = R[codes]
    if rule == "unbalanced":
        n = R.loc[window_mask(R.index, "train")].notna().sum(axis=0)
        return sorted(n.index[n >= 52])
    if rule == "balanced":
        n = R.loc[window_mask(R.index, "train")].notna().sum(axis=0)
        return sorted(n.index[n == window_mask(R.index, "train").sum()])
    n_tr, _ = _rows(R, "train")
    n_te, _ = _rows(R, "test")
    if rule in ("EVAL", "FULL"):
        return sorted(R.columns[(n_tr >= 104) & (n_te >= 52)])
    if rule == "EVAL52":
        return sorted(R.columns[(n_tr >= 52) & (n_te >= 52)])
    if rule == "STAB":
        n1, _ = _rows(R, "H1")
        n2, _ = _rows(R, "H2")
        return sorted(R.columns[(n_tr >= 104) & (n_te >= 52) & (n1 >= 104) & (n2 >= 104)])
    if rule == "PY_train":
        n, m = _rows(R, "train")
        return sorted(R.columns[(n_tr >= 104) & (n_te >= 52) & (n == m.sum())])
    if rule == "PY_test":
        n, m = _rows(R, "test")
        return sorted(R.columns[(n_tr >= 104) & (n_te >= 52) & (n == m.sum())])
    if rule == "PY_train_c":
        n, m = _rows(R, "train_c")
        return sorted(R.columns[(n_tr >= 104) & (n_te >= 52) & (n == m.sum())])
    raise KeyError(rule)


def split_halves(base, policy, seed=SEED):
    """base: list รหัสกอง · policy: Series(FundCode→E/F/O) · คืน DataFrame(FundCode, policy, half A/B)
    แต่ละ policy ตามลำดับ E,F,O: เรียง FundCode → permutation (generator เดียวต่อเนื่อง) → floor(n/2) ตัวแรก = A"""
    rng = np.random.default_rng(seed)
    rows = []
    for g in ("E", "F", "O"):
        codes = sorted(c for c in base if policy[c] == g)
        n = len(codes)
        perm = rng.permutation(n)
        na = n // 2
        for r, i in enumerate(perm):
            rows.append((codes[i], g, "A" if r < na else "B"))
    out = pd.DataFrame(rows, columns=["FundCode", "policy", "half"]).sort_values("FundCode", kind="stable")
    return out.reset_index(drop=True)
