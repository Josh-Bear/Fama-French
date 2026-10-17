"""factor-reviewer: ตรวจผล S006 (อ่านอย่างเดียว · ไม่เขียน runs/) — คำนวณซ้ำส่วนเล็กจาก CSV + hash"""
import hashlib, json
from pathlib import Path
import numpy as np
import pandas as pd

T = Path(".claude/factor_team")
S6 = T / "runs/S006"
P4 = ["MSCI_ACWI_HC", "MSCI_ACWI_UT", "MSCI_EUROPE", "MSCI_INDIA", "MSCI_JAPAN", "MSCI_VIETNAM"]
THEME = {"ARKK", "QQQ", "SOXX", "IBB", "ICLN"}
out = {}

fl = pd.read_csv(S6 / "fund_level.csv")
sc = pd.read_csv(S6 / "scorecard.csv")
# A) median จาก fund_level เทียบ scorecard (E · EVAL)
chk = []
for row in ["ref_base_1a", "ref_L2_1a", "R1", "R2", "R6", "R7", "R11", "R12", "R3", "R8"]:
    d = fl[(fl.row == row) & (fl.policy == "E")]
    s = sc[(sc.row == row) & (sc.policy == "E")]
    if "set" in sc.columns:
        s = s[s.set == "EVAL"]
    s = s.iloc[0]
    for a, b in [("adj_r2", "adjr2_med"), ("r2_oos", "r2oos_med"), ("d_r2_oos", "med_d_r2_oos"), ("d_bic", "med_d_bic")]:
        if b in s and not pd.isna(s[b]) and d[a].notna().any():
            chk.append(dict(row=row, stat=b, n=len(d), mine=float(d[a].median()), csv=float(s[b])))
A = pd.DataFrame(chk)
A["absdiff"] = (A.mine - A.csv).abs()
out["A_max_absdiff_scorecard"] = float(A.absdiff.max())
print(A.to_string())

# B) bprim_subset + เทียบบนกองเดียวกัน
pi = pd.read_csv(T / "runs/S005/primary_index.csv")
res = []
for b, rB, rB5, rA, rL in [("1a", "R3", "R5", "R1", "ref_L2_1a"), ("1c", "R8", "R10", "R6", "ref_L2_1c")]:
    p = pi[pi.form == f"{b}@4"].set_index("FundCode")["index"]
    E = fl[(fl.row == rB) & (fl.policy == "E")].FundCode
    ext = [c for c in E if p.get(c) in P4]
    ext5 = [c for c in ext if p.get(c) != "MSCI_VIETNAM"]
    def med(row, funds, col="d_r2_oos"):
        d = fl[(fl.row == row) & fl.FundCode.isin(funds)]
        return float(d[col].median()), len(d)
    res.append(dict(base=b, n_ext=len(ext), Bprim=med(rB, ext), Bprim5=med(rB5, ext5), Aprim_same=med(rA, ext), L2_same=med(rL, ext),
                    Bprim_bic=med(rB, ext, "d_bic")))
print(pd.DataFrame(res).to_string())
out["B"] = res

# C) Q3: L2(none) vs แอป + baseline สลับภายใน policy
app = pd.read_csv("cache/results.csv").set_index("FundCode")[["country_primary", "sector_primary"]]
EV = fl[fl.row == "ref_base_1a"][["FundCode", "policy"]].set_index("FundCode").policy
none = pi[pi.form == "none"].set_index("FundCode")["index"].reindex(EV.index).dropna()
cm = [c for c in none.index if c in app.index]
o = none[cm].to_numpy(); ac = app.loc[cm, "country_primary"].to_numpy(); as_ = app.loc[cm, "sector_primary"].to_numpy()
pol = EV[cm].to_numpy()
rate = float(((o == ac) | (o == as_)).mean())
rng = np.random.default_rng(12345)
rates = []
for _ in range(2000):
    pm = np.arange(len(cm))
    for g in set(pol):
        w = np.where(pol == g)[0]; pm[w] = rng.permutation(w)
    rates.append(((o == ac[pm]) | (o == as_[pm])).mean())
out["C_q3"] = dict(n=len(cm), policies=sorted(set(pol)), rate=rate, base_mean=float(np.mean(rates)), base_q=[float(np.percentile(rates, 2.5)), float(np.percentile(rates, 97.5))])
print(out["C_q3"])

# D) C-prim ในกลุ่ม ACWI_CD
pc = pd.read_csv(S6 / "primary_C.csv").set_index("FundCode")["index"]
cd = [c for c in none.index if none[c] == "MSCI_ACWI_CD"]
vc = pc.reindex(cd).value_counts()
out["D_acwicd"] = dict(n=len(cd), theme=int(pc.reindex(cd).isin(THEME).sum()), counts=vc.to_dict())
print(out["D_acwicd"])

# E) Q1a: drop-one median ในกองหลัก (HC, Vietnam)
do = pd.read_csv(S6 / "drop_one_B.csv")
print(do.columns.tolist(), do.shape)
q = []
for b in ["1a", "1c"]:
    p = pi[pi.form == f"{b}@4"].set_index("FundCode")["index"]
    for j in P4:
        prim = [c for c in p.index if p[c] == j]
        cols = {c: c for c in do.columns}
        d = do[(do["base"] == b) & (do["index"] == j) & (do["FundCode"].isin(prim))]
        if "window" in do.columns:
            d = d[d.window == "main"] if "main" in set(do.window) else d
        q.append(dict(base=b, j=j, n=len(d), med_r2oos=float(d.d_r2_oos.median()), med_bic=float(d.d_bic.median())))
print(pd.DataFrame(q).to_string())
out["E_q1a"] = q

# F) hash: runs/S006 vs run2 · S003/S005 vs regress3
def h(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()
EXC = {"results.md", "run.log", "run_meta.json", "run.py", "repro_check.json", "repro_check.py", "pytest_all.log", "regression_S003_S005.json", "decisions_pre_run.md", "placebo_C.json"}
r2 = T / "scratch/factor-analyst_s006_run2"
F = {}
for f in sorted(S6.iterdir()):
    if f.name in EXC or f.is_dir():
        continue
    g = r2 / f.name
    F[f.name] = (g.exists() and h(f) == h(g))
out["F_run2_n"] = len(F); out["F_run2_all"] = all(F.values()); out["F_run2_bad"] = [k for k, v in F.items() if not v]
pj = json.loads((S6 / "placebo_C.json").read_text()); pj2 = json.loads((r2 / "placebo_C.json").read_text())
pj.pop("timestamp"); pj2.pop("timestamp"); out["F_placebo_eq"] = pj == pj2
for run, rg in [("S003", "factor-analyst_s003_regress3"), ("S005", "factor-analyst_s005_regress3")]:
    base = T / "runs" / run; alt = T / "scratch" / rg
    exc = {"results.md", "run.log", "run_meta.json", "repro_check.json", "repro_check.py", "placebo_rule.json"}
    res_ = {}
    for f in sorted(base.rglob("*")):
        if f.is_dir() or f.name in exc or f.suffix == ".py" or "__pycache__" in str(f):
            continue
        g = alt / f.relative_to(base)
        res_[str(f.relative_to(base))] = g.exists() and h(f) == h(g)
    out[f"F_{run}_n"] = len(res_); out[f"F_{run}_bad"] = [k for k, v in res_.items() if not v]
print({k: v for k, v in out.items() if k.startswith("F")})
Path(T / "scratch/factor-reviewer_S006/result_check.json").write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str))
