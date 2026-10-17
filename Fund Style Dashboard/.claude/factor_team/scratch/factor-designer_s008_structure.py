"""S008 (addendum ของ S007) — ตรวจโครงข้อมูลเท่านั้น
ไม่อ่านค่าผลตอบแทน (ใช้แค่ ret.notna()) · ไม่ fit model · ไม่อ่านคอลัมน์ผล (alpha / t / r2 / bic) ของ runs/*
ตรวจ: (1) sha256 ของ S007 + ไฟล์อ้างอิงใหม่ (2) TER ตามกติกาใหม่ (รุ่น ≤ 2025 ก่อน → Actual ก่อน Rate → as-of เร็วสุด)
(3) ธง in_PCA_sample / in_E67 ใน EVAL (4) การนับกลุ่ม E: n · n_indep_all · n_tr · n_indep_tr → วิธีตามกฎใหม่
(5) ขนาด pool ของ null แบบ (b) (6) จำนวนกองต่อกลุ่มในชุดย่อย E67 / TER ≤ 2025 (ความเป็นไปได้ของ dummy)
"""
import hashlib, json, re, sys
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parents[3]; T = ROOT / ".claude" / "factor_team"; o = {}
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
o["sha256"] = {k: sha(T / k) for k in [
    "specs/S007_L4_group_factors_fund_alpha.md", "reviews/S007_spec_review.md",
    "data/QA_ACWI_CD_group.md", "runs/S003/fund_level.csv", "runs/S005/fund_clusters.csv",
    "runs/S005/primary_index.csv", "data/panel_weekly.parquet", "data/factors_weekly.parquet"]}
o["sha256"]["base_data/SecFundFee.csv"] = sha(ROOT / "base_data/SecFundFee.csv")

fl = pd.read_csv(T / "runs/S003/fund_level.csv", usecols=["form", "FundCode", "policy", "in_EVAL", "in_E67", "in_PCA_sample"])
ev = fl[(fl.form == "1a") & (fl.in_EVAL)].drop_duplicates("FundCode")[["FundCode", "policy", "in_E67", "in_PCA_sample"]]
o["EVAL_n"] = int(len(ev))
o["in_PCA_sample_by_pol"] = ev[ev.in_PCA_sample].policy.value_counts().to_dict()
o["in_E67_by_pol"] = ev[ev.in_E67].policy.value_counts().to_dict()
o["E67_and_PCA_overlap"] = int((ev.in_E67 & ev.in_PCA_sample).sum())
o["E_not_PCA_not_E67"] = int(((ev.policy == "E") & ~ev.in_PCA_sample & ~ev.in_E67).sum())

fc = pd.read_csv(T / "runs/S005/fund_clusters.csv", usecols=["FundCode", "group_id"])
pi = pd.read_csv(T / "runs/S005/primary_index.csv", usecols=["form", "FundCode", "index"])
p = pi[pi.form == "1a@4"][["FundCode", "index"]].merge(ev, on="FundCode").merge(fc, on="FundCode", how="left")
p = p[p.FundCode != "MGAPVD"].copy()

# ครบทุกแถว train — นับ notna เท่านั้น (ไม่ใช้ค่า)
R = pd.read_parquet(T / "data/panel_weekly.parquet", columns=["FundCode", "date", "ret"])
R = R[R.FundCode.isin(ev.FundCode)]; R["date"] = pd.to_datetime(R["date"])
tr = R[(R.date >= "2021-01-08") & (R.date <= "2023-12-29")]
ntr = tr.assign(ok=tr["ret"].notna()).groupby("FundCode").ok.sum(); del R, tr
o["train_rows_max"] = int(ntr.max())
p["full_tr"] = p.FundCode.map(ntr).fillna(0).astype(int) >= int(ntr.max())

def method(nind_all, nind_tr):
    if nind_tr >= 10: return "PCA"
    if nind_all >= 5: return "LOO-mean"
    return "none"

E = p[p.policy == "E"]; rows = []
for g, d in E.groupby("index"):
    dt = d[d.full_tr]
    nia, nit = d.group_id.nunique(), dt.group_id.nunique()
    # PCA: peer ครบ train ของแต่ละกอง i หลังตัด cluster ของ i (ต่ำสุด)
    min_peer_tr = min(int((dt.group_id != gid).sum()) for gid in d.group_id) if len(dt) else 0
    min_peer_all = min(int((d.group_id != gid).sum()) for gid in d.group_id)
    pool_all = int(((p.policy == "E") & (p["index"] != g)).sum())
    pool_tr = int(((p.policy == "E") & (p["index"] != g) & p.full_tr).sum())
    rows.append(dict(group=g, n=len(d), n_indep_all=nia, n_tr=len(dt), n_indep_tr=nit, method=method(nia, nit),
                     dummy=nia >= 10, min_peer_tr=min_peer_tr, min_peer_all=min_peer_all, pool_E_all=pool_all, pool_E_tr=pool_tr))
G = pd.DataFrame(rows).sort_values("n", ascending=False)
o["E_groups"] = G.to_dict("records")
for pol in ["F", "O"]:
    d = p[p.policy == pol]; dt = d[d.full_tr]
    o[f"G_{pol}"] = dict(n=len(d), n_indep_all=int(d.group_id.nunique()), n_tr=int(len(dt)), n_indep_tr=int(dt.group_id.nunique()),
                         method=method(d.group_id.nunique(), dt.group_id.nunique()))
o["G0_E"] = dict(n=int(len(E)), n_tr=int(E.full_tr.sum()), n_indep_tr=int(E[E.full_tr].group_id.nunique()))

# TER ตามกติกาใหม่
fee = pd.read_csv(ROOT / "base_data/SecFundFee.csv", dtype=str, encoding="utf-8-sig")
codes = set(ev.FundCode)
mf = fee[(fee["Complex Type Code"] == "FEEMF") & fee["Fund Code"].isin(codes)].copy()
mf["asof"] = pd.to_datetime(mf["As of Date"], format="%Y%m%d")
def parse(s):
    if s is None or (isinstance(s, float) and np.isnan(s)): return np.nan
    s = str(s).strip()
    if any(w in s for w in ["ไม่มี", "ยกเว้น", "ไม่เรียกเก็บ"]): return 0.0
    m = re.fullmatch(r"([0-9]*\.?[0-9]+)\s*%?", s)
    return float(m.group(1)) if m else np.nan
mf["act"] = mf["Actual Value"].map(parse); mf["rate"] = mf["Rate"].map(parse)
tt = mf[mf.Code == "TT"].copy(); of = mf[mf.Code == "OF"][["Fund Code", "asof", "act"]].rename(columns={"act": "of_act"})
tt["vint"] = np.where(tt["asof"] <= "2025-12-31", "le2025", "y2026")
sel = []
for f, d in tt.groupby("Fund Code"):
    d = d.sort_values("asof"); pick = None
    for v in ["le2025", "y2026"]:
        dv = d[d.vint == v]
        a = dv[dv.act.notna()]
        if len(a): pick = (a.iloc[0], "actual"); break
        r = dv[dv.rate.notna()]
        if len(r): pick = (r.iloc[0], "rate"); break
    if pick is None: sel.append(dict(FundCode=f, vint=None, src=None, asof=None)); continue
    row, src = pick
    sel.append(dict(FundCode=f, vint=row["vint"], src=src, asof=row["asof"], ter=row.act if src == "actual" else row.rate))
S = pd.DataFrame(sel).merge(ev[["FundCode", "policy", "in_E67"]], on="FundCode", how="right")
o["TER_missing"] = int(S.vint.isna().sum())
o["TER_vint_x_src"] = {str(k): int(v) for k, v in S.groupby(["vint", "src"]).size().items()}
o["TER_vint_x_src_x_pol"] = {str(k): int(v) for k, v in S.groupby(["policy", "vint", "src"]).size().items()}
o["TER_old_rule_rate_n"] = 69  # รีวิว S007
o["TER_le2025_n_by_pol"] = S[S.vint == "le2025"].policy.value_counts().to_dict()
o["TER_asof_top"] = {str(pd.Timestamp(k).date()): int(v) for k, v in S["asof"].value_counts().head(6).items()}
# QA TT ≥ OF บน as-of ที่เลือก (Actual ทั้งคู่)
q = S.dropna(subset=["asof"]).merge(of, left_on=["FundCode", "asof"], right_on=["Fund Code", "asof"], how="left")
qa = q[(q.src == "actual") & q.of_act.notna()]
o["QA_TT_ge_OF"] = dict(n=int(len(qa)), frac=float((qa.ter >= qa.of_act - 1e-12).mean()) if len(qa) else None)
# ชุดย่อย: กลุ่ม dummy (n_indep_all ≥ 10) ใน E ∩ (E67 / TER ≤ 2025)
dg = set(G[G.dummy].group)
Pm = p.merge(S[["FundCode", "vint"]], on="FundCode", how="left")
for name, mask in {"E67": Pm.in_E67 & (Pm.policy == "E"), "E_le2025": (Pm.vint == "le2025") & (Pm.policy == "E"),
                   "ALL_le2025": Pm.vint == "le2025"}.items():
    d = Pm[mask]
    o[f"subset_{name}"] = dict(n=int(len(d)), n_indep=int(d.group_id.nunique()), by_pol=d.policy.value_counts().to_dict(),
                               dummy_groups={g: int((d["index"] == g).sum()) for g in sorted(dg)})
o["dummy_groups"] = sorted(dg)
json.dump(o, sys.stdout, ensure_ascii=False, default=str, indent=0); print()
