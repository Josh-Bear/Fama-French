"""S009 (addendum ของ S008) — ตรวจโครงข้อมูลเท่านั้น: SecFundFee (TER) + ป้ายกลุ่ม · ไม่อ่านผลตอบแทน · ไม่ fit model
กติกา TER (BRIEF 80): Actual ≤ 2025 → Actual 2026 → Rate ≤ 2025 → Rate 2026 (as-of เร็วสุดในแต่ละขั้น)
"""
import hashlib, json, re, sys
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parents[3]; T = ROOT / ".claude" / "factor_team"; o = {}
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
o["sha256"] = {k: sha(T / k) for k in ["specs/S007_L4_group_factors_fund_alpha.md", "specs/S008_L4_addendum_to_S007.md",
                                        "reviews/S008_spec_review.md"]}
o["sha256"]["base_data/SecFundFee.csv"] = sha(ROOT / "base_data/SecFundFee.csv")

fl = pd.read_csv(T / "runs/S003/fund_level.csv", usecols=["form", "FundCode", "policy", "in_EVAL", "in_E67"])
ev = fl[(fl.form == "1a") & (fl.in_EVAL)].drop_duplicates("FundCode")[["FundCode", "policy", "in_E67"]]
pi = pd.read_csv(T / "runs/S005/primary_index.csv", usecols=["form", "FundCode", "index"])
fc = pd.read_csv(T / "runs/S005/fund_clusters.csv", usecols=["FundCode", "group_id"])
fee = pd.read_csv(ROOT / "base_data/SecFundFee.csv", dtype=str, encoding="utf-8-sig")
def num(s):
    if pd.isna(s): return np.nan
    s = str(s).strip()
    if any(w in s for w in ["ไม่มี", "ยกเว้น", "ไม่เรียกเก็บ"]): return 0.0
    m = re.fullmatch(r"([0-9]*\.?[0-9]+)\s*%?", s); return float(m.group(1)) if m else np.nan
mf = fee[(fee["Complex Type Code"] == "FEEMF") & fee["Fund Code"].isin(set(ev.FundCode))].copy()
mf["d"] = pd.to_datetime(mf["As of Date"], format="%Y%m%d"); mf["a"] = mf["Actual Value"].map(num); mf["r"] = mf["Rate"].map(num)
tt = mf[mf.Code == "TT"]; of = mf[mf.Code == "OF"][["Fund Code", "d", "a"]].rename(columns={"a": "of_a"})
order = [("actual", "le2025", "a"), ("actual", "y2026", "a"), ("rate", "le2025", "r"), ("rate", "y2026", "r")]
rows = []
for f, g in tt.groupby("Fund Code"):
    g = g.sort_values("d"); g = g.assign(v=np.where(g["d"] <= "2025-12-31", "le2025", "y2026")); pick = None
    for src, v, col in order:
        h = g[(g.v == v) & g[col].notna()]
        if len(h): pick = dict(FundCode=f, src=src, vint=v, asof=h.iloc[0]["d"], ter=h.iloc[0][col],
                                rate_same=h.iloc[0]["r"]); break
    le_r = g[(g.v == "le2025") & g["r"].notna()]
    pick = pick or dict(FundCode=f, src=None, vint=None, asof=pd.NaT, ter=np.nan, rate_same=np.nan)
    pick["rate_le_first"] = le_r.iloc[0]["r"] if len(le_r) else np.nan
    rows.append(pick)
S = pd.DataFrame(rows).merge(ev, on="FundCode", how="right")
o["cell_counts_EVAL207"] = {f"{a}|{b}": int(n) for (a, b), n in S.groupby(["src", "vint"]).size().items()}
o["cell_by_policy"] = {f"{p}|{a}|{b}": int(n) for (p, a, b), n in S.groupby(["policy", "src", "vint"]).size().items()}
o["n_nan"] = int(S.src.isna().sum())
fam = S[S.FundCode != "MGAPVD"]
o["family206_cells"] = {f"{a}|{b}": int(n) for (a, b), n in fam.groupby(["src", "vint"]).size().items()}
o["family206_cells_by_pol"] = {f"{p}|{a}|{b}": int(n) for (p, a, b), n in fam.groupby(["policy", "src", "vint"]).size().items()}
# Rate − Actual (ก) แถวเดียวกัน (as-of ที่เลือก) (ข) Rate ≤ 2025 เร็วสุด − Actual ที่เลือก (กอง actual)
A = S[S.src == "actual"]
d1 = (A.rate_same - A.ter).dropna(); d2 = (A.rate_le_first - A.ter).dropna()
q = lambda x: dict(n=int(len(x)), median=float(x.median()), q25=float(x.quantile(.25)), q75=float(x.quantile(.75)),
                   frac_rate_ge_actual=float((x >= -1e-12).mean())) if len(x) else None
o["rate_minus_actual_same_row"] = q(d1); o["rate_le2025_minus_actual_chosen"] = q(d2)
# QA TT ≥ OF บน as-of ที่เลือก
qa = A.merge(of, left_on=["FundCode", "asof"], right_on=["Fund Code", "d"], how="left").dropna(subset=["of_a"])
o["QA_TT_ge_OF"] = dict(n=int(len(qa)), frac=float((qa.ter >= qa.of_a - 1e-12).mean()))
# ชุดย่อย XV (Actual ≤ 2025) · E67 · dummy กลุ่ม
p = pi[pi.form == "1a@4"][["FundCode", "index"]].merge(fam, on="FundCode").merge(fc, on="FundCode", how="left")
dg = ["MSCI_ACWI_CD", "MSCI_ACWI_IT", "MSCI_ASIA_EX_JAPAN", "MSCI_CHINA_ALL_SHARES"]
for name, m in {"XV1_ALL_actual_le2025": (p.src == "actual") & (p.vint == "le2025"),
                "XV2_E_actual_le2025": (p.src == "actual") & (p.vint == "le2025") & (p.policy == "E"),
                "X2_E_all": p.policy == "E", "XE67": p.in_E67}.items():
    d = p[m]
    o[name] = dict(n=int(len(d)), n_indep=int(d.group_id.nunique()), by_pol=d.policy.value_counts().to_dict(),
                   d_v2026=int((d.vint == "y2026").sum()), d_rate=int((d.src == "rate").sum()),
                   dummy_groups={g: int((d["index"] == g).sum()) for g in dg})
o["rate_funds"] = S[S.src == "rate"][["FundCode", "policy", "vint"]].to_dict("records")
json.dump(o, sys.stdout, ensure_ascii=False, default=str, indent=0); print()
