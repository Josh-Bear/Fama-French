"""S010 spec review (reviewer) — โครงข้อมูล (notna เท่านั้น · ไม่อ่านค่าผลตอบแทน) + ข้อมูลจำลอง (power / size / BH / DSR)
ไม่ fit model บนข้อมูลจริง · ไม่คำนวณ target / IC / ผลตอบแทน
"""
import hashlib, json, sys
from pathlib import Path
import numpy as np, pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parents[3]; T = ROOT / ".claude" / "factor_team"
sys.path.insert(0, str(T / "lib"))
import l4  # noqa: E402
import tests_stat as ts  # noqa: E402
import l2  # noqa: E402

sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
o = {}
man = json.load(open(T / "data/manifest.json"))
mm = {d["file"]: d["sha256"] for d in man["inputs"] + man["outputs"]}
files = {"data/panel_weekly.parquet": T / "data/panel_weekly.parquet", "data/factors_weekly.parquet": T / "data/factors_weekly.parquet",
         "data/aum_weekly.parquet": T / "data/aum_weekly.parquet", "data/universe.csv": T / "data/universe.csv",
         "data/dup_pairs.csv": T / "data/dup_pairs.csv", "base_data/SecFundFee.csv": ROOT / "base_data/SecFundFee.csv",
         "base_data/FundProfile.csv": ROOT / "base_data/FundProfile.csv"}
o["sha"] = {}
for k, p in files.items():
    key = k if k.startswith("base_data") else ".claude/factor_team/" + k
    o["sha"][k] = dict(actual=sha(p), manifest=mm.get(key), match=(mm.get(key) == sha(p)) if mm.get(key) else None)

# ── โครง: กองที่หลุดเพราะ target < ½ = เลิก (ไม่มีข้อมูลหลังจากนั้นถึง 2025-12-26) หรือ รู (กลับมามีข้อมูล) ──
P = pd.read_parquet(T / "data/panel_weekly.parquet", columns=["date", "FundCode", "ret"])
M = P.assign(ok=P["ret"].notna()).pivot(index="date", columns="FundCode", values="ok").fillna(False).astype(bool)
del P
o["panel_max_date_incl_2026"] = str(M.index.max().date())
o["n_rows_2026"] = int((M.index > "2025-12-31").sum())
M = M.loc["2021-01-08":"2025-12-26"]
idx = M.index; pos = np.arange(len(idx))
last_ok = M.apply(lambda c: c[c].index.max() if c.any() else pd.NaT)
o["funds_last_row_before_2025-12-26"] = int((last_ok < idx[-1]).sum())
U = pd.read_csv(T / "data/universe.csv").set_index("FundCode")
GOLD = ["BGOLD", "K-GOLD-A(A)", "KT-GOLD", "SCBGOLDHP", "TGOLD", "UOBSG-N"]
qe = pd.date_range("2022-03-31", "2025-12-31", freq="QE-DEC")
dec = [idx[idx <= q][-1] for q in qe]
rows = []
for a, b in zip(dec[:-1], dec[1:]):
    dim = M.loc[(idx <= a) & (pos >= 1)].sum(0)
    elig = [c for c in dim[dim >= 52].index if c not in GOLD and U["div_flag"].get(c, "N") != "Y"]
    w = (idx > a) & (idx <= b); nq = int(w.sum())
    tgt = M.loc[w].sum(0)
    drop = [c for c in elig if tgt[c] < int(np.ceil(nq / 2))]
    partial = [c for c in elig if int(np.ceil(nq / 2)) <= tgt[c] < nq]
    dead = [c for c in drop if not M.loc[idx > b, c].any()]
    rows.append(dict(t=str(a.date()), U_pre_approx=len(elig), drop_lt_half=len(drop), drop_dead=len(dead),
                     drop_hole=len(drop) - len(dead), drop_zero_weeks=int(sum(tgt[c] == 0 for c in drop)), partial_kept=len(partial)))
o["dropped_by_quarter"] = rows

# ── TER: วัน as-of ของค่าที่เลือก (ไม่ใช่ผลตอบแทน) ──
fee = pd.read_csv(ROOT / "base_data/SecFundFee.csv", dtype=str, encoding="utf-8-sig")
union = sorted(set(c for c in M.columns if c not in GOLD and U["div_flag"].get(c, "N") != "Y"))
ter = l4.ter_table(fee, union)
ter = ter[ter["ter"].notna()]
a = ter["ter_asof"]
o["ter_asof"] = dict(n=int(len(ter)), min=str(a.min().date()), max=str(a.max().date()),
                     by_year={str(k): int(v) for k, v in a.dt.year.value_counts().sort_index().items()},
                     n_asof_2026_ge_Jan=int((a >= "2026-01-01").sum()), by_month_2026={str(k): int(v) for k, v in
                     a[a.dt.year == 2026].dt.month.value_counts().sort_index().items()},
                     src={f"{s}|{v}": int(n) for (s, v), n in ter.groupby(["ter_src", "ter_vintage"]).size().items()})

# ── จำลอง: size / power ของ t_dec = x̄ / max(SE_iid, SE_NW(L=2)) · Q = 15 ──
def se_nw(x, L):
    Q = len(x); d = x - x.mean()
    g = [d @ d / Q] + [d[l:] @ d[:-l] / Q for l in range(1, L + 1)]
    om = Q / (Q - 1) * (g[0] + 2 * sum((1 - l / (L + 1)) * g[l] for l in range(1, L + 1)))
    return np.sqrt(max(om, 0) / Q)


def sim(mu, rho=0.0, Q=15, n=20000, seed=1):
    rng = np.random.default_rng(seed)
    out = dict(iid=0, nw=0, dec=0, nw_gt_iid=0)
    L = int(np.floor(4 * (Q / 100) ** (2 / 9)))
    for _ in range(n):
        e = rng.standard_normal(Q)
        x = np.empty(Q); x[0] = e[0]
        for i in range(1, Q):
            x[i] = rho * x[i - 1] + np.sqrt(1 - rho ** 2) * e[i]
        x = x + mu
        s_iid = x.std(ddof=1) / np.sqrt(Q); s_nw = se_nw(x, L)
        tc = 3.0
        out["iid"] += x.mean() / s_iid > tc
        out["nw"] += x.mean() / s_nw > tc
        out["dec"] += x.mean() / max(s_iid, s_nw) > tc
        out["nw_gt_iid"] += s_nw > s_iid
    return {k: v / n for k, v in out.items()} | dict(L=L)


o["sim"] = {}
for mu in (0.0, 0.76, 1.01, 1.10, 1.20, 1.30):
    for rho in (0.0, 0.3, -0.3):
        o["sim"][f"mu{mu}_rho{rho}"] = sim(mu, rho)
# μ (หน่วย σ) ที่ให้ power 80% ภายใต้กฎ max
grid = np.arange(1.00, 1.41, 0.02)
pw = [sim(m, 0.0, n=8000, seed=7)["dec"] for m in grid]
o["mde80_maxrule_iid"] = float(grid[np.argmax(np.array(pw) >= 0.80)]) if max(pw) >= 0.80 else None
o["power_grid_maxrule"] = {f"{g:.2f}": round(p, 3) for g, p in zip(grid, pw)}

# ── BH: J1 ช่วยกู้ trial ที่ t ∈ (3, 3.24) ได้ไหม (ตัวอย่างมือ) ──
tq = lambda t: float(2 * stats.t.sf(t, 14))
p = np.ones(17); p[0] = tq(3.1); p[11] = 1e-4  # trial เดียว t = 3.1 + J1 p เล็ก
r_with, _ = ts.bh(p, 0.10)
p2 = p.copy(); p2[11] = 1.0
r_wo, _ = ts.bh(p2, 0.10)
o["bh_J1_rescue"] = dict(p_trial=tq(3.1), reject_with_J1=bool(r_with[0]), reject_without_J1=bool(r_wo[0]))

# ── DSR SR0 ──
g = 0.5772156649
sr0 = lambda n, Q=15: np.sqrt(1 / (Q - 1)) * ((1 - g) * stats.norm.ppf(1 - 1 / n) + g * stats.norm.ppf(1 - 1 / (n * np.e)))
o["dsr_sr0"] = {n: float(sr0(n)) for n in (17, 19, 20, 121, 122, 213)}
o["dsr_sr0_t_equiv"] = {n: float(sr0(n) * np.sqrt(15)) for n in (20, 122)}
# B-full m: โครงนับสูงสุดเมื่อแม่ของช่องรายเดือนเป็น D1 (R1–R5 + R6)
o["mB_count"] = dict(base=17 + (10 * 5 - 1) + 1 + 1 + 4, cond_5x5=25, cond_if_D1_monthly_with_R6=2 * 6 + 3 * 5)

out = T / "scratch/factor-reviewer_s010_check.json"
json.dump(o, open(out, "w"), ensure_ascii=False, indent=1, default=str)
print(json.dumps(o, ensure_ascii=False, indent=1, default=str))
