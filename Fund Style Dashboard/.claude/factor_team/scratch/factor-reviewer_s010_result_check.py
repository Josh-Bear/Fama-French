"""reviewer — ตรวจผล S010/S011 (อ่านอย่างเดียว · ไม่เขียนใน runs/ · ไม่แตะ trials.csv)
ใช้: PYTHONPATH=. ./.venv/bin/python .claude/factor_team/scratch/factor-reviewer_s010_result_check.py
"""
import csv, json, math, sys, hashlib
from pathlib import Path
import numpy as np, pandas as pd
from scipy import stats

ROOT = Path(".").resolve()
TEAM = ROOT / ".claude/factor_team"
RUN = TEAM / "runs/S010"
sys.path.insert(0, str(TEAM / "lib"))
OUT = {}

# ── A. trials.csv ──
rows = list(csv.reader(open(TEAM / "trials.csv", newline="", encoding="utf-8")))
H, D = rows[0], rows[1:]
df = pd.DataFrame(D, columns=H)
A = {}
A["n_rows"] = len(df)
A["row_kind"] = df.row_kind.value_counts().to_dict()
A["has_inference"] = df.has_inference.value_counts().to_dict()
A["sumA"] = int(df.counts_mode_A.astype(int).sum()); A["sumB"] = int(df.counts_mode_B.astype(int).sum())
A["cumA_ok"] = bool((df.counts_mode_A.astype(int).cumsum() == df.n_trials_cumulative.astype(int)).all())
A["cumB_ok"] = bool((df.counts_mode_B.astype(int).cumsum() == df.n_trials_cumulative_B.astype(int)).all())
A["ncomb_ok"] = bool(((df.n_trials_cumulative.astype(int) + 102) == df.n_combined.astype(int)).all() and ((df.n_trials_cumulative_B.astype(int) + 102) == df.n_combined_B.astype(int)).all())
A["last_ncomb"] = (df.n_combined.iloc[-1], df.n_combined_B.iloc[-1])
A["dup_trial_id"] = df.trial_id[df.trial_id.duplicated()].tolist()
A["run_at"] = sorted(df.run_at.unique().tolist())
A["spec_file"] = df.spec_file.unique().tolist()
A["status"] = df.status.value_counts().to_dict()
A["run_dir"] = df.run_dir.unique().tolist()
A["lib_sha_unique"] = df.lib_sha256.nunique(); A["data_sha_unique"] = df.data_sha256.nunique()
A["main_ids"] = df.loc[df.row_kind == "main", "trial_id"].tolist()
A["rob_by_parent"] = df.loc[df.row_kind == "robustness"].groupby("parent_id").size().to_dict()
A["rob_noinf"] = df.loc[(df.row_kind == "robustness") & (df.has_inference != "1"), "trial_id"].tolist()
A["blank_p_with_inf"] = df.loc[(df.has_inference == "1") & (df.p_two == ""), "trial_id"].tolist()
# lib_sha256 in trials vs run_meta
meta = json.load(open(RUN / "run_meta.json"))
A["lib_sha_matches_meta"] = df.lib_sha256.iloc[0] == hashlib.sha256(json.dumps(meta["lib_sha256"], sort_keys=True).encode()).hexdigest()
A["data_sha_matches_meta"] = df.data_sha256.iloc[0] == hashlib.sha256(json.dumps(meta["data_sha256"], sort_keys=True).encode()).hexdigest()
OUT["A_trials"] = A

# ── B. backups: prefix chain ──
bk = sorted((RUN / "trials_backup").glob("trials.backup_*.csv"), key=lambda p: p.stat().st_mtime_ns)
final = (TEAM / "trials.csv").read_bytes()
chain, prev = [], b""
for p in sorted(bk, key=lambda p: len(p.read_bytes())):
    b = p.read_bytes()
    chain.append(dict(f=p.name, lines=b.count(b"\n"), prefix_of_final=final.startswith(b), extends_prev=b.startswith(prev)))
    prev = b
OUT["B_backups"] = dict(n=len(bk), chain=chain)

# ── C. BH ทั้ง family m=97 / 17 ด้วย p จริง ──
import p2, tests_stat as tsx, l2
runpy = (RUN / "run.py").read_text()
pmap = {r.trial_id: (float(r.p_two) if r.p_two not in ("", "nan") else 1.0) for r in df.itertuples()}
main = ["P2-B0", "P2-A2", "P2-C1", "P2-A1", "P2-A3", "P2-C2", "P2-D1", "P2-C3", "P2-D3", "P2-B2", "P2-B1", "P2-J1"]
cond = ["P2-M1", "P2-M2", "P2-W1", "P2-W2", "P2-W3"]
rob = [t for t in df.trial_id if t not in main]
cond_rob = [f"{c}.R{i}" for c in cond for i in range(1, 6)]
order97 = main + cond + rob + cond_rob
C = dict(len97=len(order97), n_rob=len(rob))
J1N = {"P2-J1"} | {f"P2-J1.S{i}" for i in range(1, 5)}
pv = np.array([1.0 if (s in J1N) else pmap.get(s, 1.0) for s in order97])
rej, adj = tsx.bh(pv, 0.10)
C["bh97_rejected"] = [(order97[i], pv[i]) for i in np.where(rej)[0]]
C["bh97_thr_rank1"] = 0.10 / 97
pv_real = np.array([pmap.get(s, 1.0) for s in order97])
rej2, _ = tsx.bh(pv_real, 0.10)
C["bh97_rejected_realJ1"] = [order97[i] for i in np.where(rej2)[0]]
by, _ = l2.by(pv, 0.10)
C["by97_rejected"] = [order97[i] for i in np.where(by)[0]]
pv17 = np.array([1.0 if s == "P2-J1" else pmap.get(s, 1.0) for s in main + cond])
C["bh17_rejected"] = [(main + cond)[i] for i in np.where(tsx.bh(pv17, 0.10)[0])[0]]
C["smallest_p"] = sorted(((pmap[s], s) for s in pmap))[:6]
# B-full without R5
pv_noR5 = np.array([1.0 if (s in J1N or s.endswith(".R5")) else pmap.get(s, 1.0) for s in order97])
C["bh97_rejected_if_R5_p1"] = [order97[i] for i in np.where(tsx.bh(pv_noR5, 0.10)[0])[0]]
OUT["C_family"] = C

# ── D. t_dec ซ้ำจาก ic_series (โค้ดของ reviewer เอง) ──
ics = pd.read_csv(RUN / "ic_series.csv")
ts_ = pd.read_csv(RUN / "trial_summary.csv").set_index("trial")
def my_tdec(x):
    x = np.asarray(x, float); x = x[np.isfinite(x)]; Q = len(x); m = x.mean(); s = x.std(ddof=1)
    L = int(math.floor(4 * (Q / 100) ** (2 / 9))); d = x - m
    g = lambda l: (d[l:] @ d[:Q - l]) / Q
    om = (g(0) + 2 * sum((1 - l / (L + 1)) * g(l) for l in range(1, L + 1))) * Q / (Q - 1)
    se_i, se_n = s / math.sqrt(Q), math.sqrt(om / Q)
    t = m / max(se_i, se_n)
    return dict(Q=Q, mean=m, s=s, se_iid=se_i, se_nw=se_n, L=L, t=t, p=2 * stats.t.sf(abs(t), Q - 1), h1=x[:7].mean(), h2=x[7:].mean())
Dd = {}
for tr in ("P2-C1", "P2-A1", "P2-B0", "P2-D3"):
    x = ics[(ics.trial == tr) & (ics.col == "IC")].sort_values("t")["value"].to_numpy()
    me = my_tdec(x)
    Dd[tr] = dict(mine={k: round(v, 6) for k, v in me.items()}, file_t=round(ts_.loc[tr, "t_dec"], 6), file_p=round(ts_.loc[tr, "p"], 6),
                  diff_t=abs(me["t"] - ts_.loc[tr, "t_dec"]), diff_mean=abs(me["mean"] - ts_.loc[tr, "mean"]))
# B1 payoff
x = ics[(ics.trial == "P2-B1") & (ics.col == "mean_payoff")].sort_values("t")["value"].to_numpy()
me = my_tdec(x); Dd["P2-B1"] = dict(t=me["t"], file_t=ts_.loc["P2-B1", "t_dec"] if "P2-B1" in ts_.index else None, mean=me["mean"])
OUT["D_tdec"] = Dd

# ── E. Hotelling J1 จาก j1_slopes ──
J = pd.read_csv(RUN / "j1_slopes.csv")
L_ = J[[c for c in J.columns if c.startswith("slope")]].to_numpy(float)
L_ = L_[np.isfinite(L_).all(axis=1)]
Q, p = L_.shape
lb = L_.mean(0); S = np.cov(L_, rowvar=False, ddof=1)
T2 = Q * lb @ np.linalg.inv(S) @ lb; F = (Q - p) / (p * (Q - 1)) * T2
OUT["E_hotelling"] = dict(Q=Q, p=p, F=F, pval=stats.f.sf(F, p, Q - p), slope_t=[my_tdec(L_[:, j])["t"] for j in range(p)])

# ── F. IC_min80 realized multiplier ──
OUT["F_mde"] = dict(mult_sim_ratio={tr: ts_.loc[tr, "ic_min80_realized_sim"] / ts_.loc[tr, "s_sigmaIC"] for tr in ("P2-B0", "P2-A1", "P2-C1")},
                    nct=p2.mde_mult_nct(15, 3.0, 0.8))

# ── G. คำนวณซ้ำจากข้อมูลจริง: B0 (สัญญาณ + target เขียนเอง) · A1/C1 (OLS+target เขียนเอง) ที่ 3 ไตรมาส + future-scramble ที่ t เพิ่ม ──
import io_l1, l4
exec_ns = {}
src = runpy.split("if SIM:")[0]
# ดึงเฉพาะ load_real (ไม่รันส่วนอื่นของ run.py)
start = src.index("def load_real():")
code = src[start:]
hdr = "import numpy as np, pandas as pd\nimport io_l1, l4, p2\nfrom pathlib import Path\nROOT = Path('.').resolve()\n"
exec(hdr + code, exec_ns)
INP, IDX = exec_ns["load_real"]()
R = INP.R
DQ = p2.decision_dates(R.index, "Q")
G = {}
qs = [0, 7, 14]
prev = None; states = {}
for j, r in enumerate(DQ.itertuples()):
    prev = p2.state_at(INP, r.t_pos, prev, None)
    if j in qs:
        states[j] = prev
for j in qs:
    r = DQ.iloc[j]; st = states[j]; U = st["U"]
    R_le = R.iloc[: r.t_pos + 1]
    Rw = R.iloc[r.t_pos + 1: r.e_pos + 1][U]
    nobs = Rw.notna().sum()
    Ut = [c for c in U if nobs[c] >= math.ceil(r.n_q / 2)]
    # B0 เอง
    L52 = R_le[Ut].iloc[-52:]
    b0 = (52 * L52.mean()).where(L52.notna().sum() >= 47)
    tt = r.n_q / nobs[Ut] * Rw[Ut].sum()
    ok = b0.notna() & tt.notna()
    ic_b0 = stats.spearmanr(b0[ok], tt[ok]).statistic
    f_ic = ics[(ics.trial == "P2-B0") & (ics.col == "IC") & (ics.t == str(r.t.date()))]
    # A1 / C1 เอง: OLS Dimson บน [f, FX] + lag, HAC Bartlett L=4 (ไม่มี df correction)
    f_le = st["f_le"]; FX = INP.F3["FX"].to_numpy(float)[: r.t_pos + 1]
    Xc = np.column_stack([f_le, FX]); Xl = np.vstack([np.full((1, Xc.shape[1]), np.nan), Xc[:-1]])
    Dm = np.column_stack([Xc, Xl])
    tg = p2.target_at(INP, st, int(r.e_pos), int(r.n_q))
    Fp = tg["Fp"]; Dw = np.hstack([Fp[1:], Fp[:-1]])
    a1, c1, tpca = {}, {}, {}
    for c in Ut:
        y = R_le[c].to_numpy(float)
        for win, store in ((None, a1), (104, c1)):
            m = np.isfinite(y) & np.isfinite(Dm).all(1)
            if win is not None and len(y) > win:
                m[: len(y) - win] = False
            n = m.sum()
            if n < 52:
                continue
            X = np.column_stack([np.ones(n), Dm[m]]); yy = y[m]
            b, *_ = np.linalg.lstsq(X, yy, rcond=None); e = yy - X @ b
            k = X.shape[1]
            if win is None:
                XtXi = np.linalg.inv(X.T @ X); Sg = (X * e[:, None]).T @ (X * e[:, None])
                for l in range(1, 5):
                    w = 1 - l / 5; G_ = (X[l:] * e[l:, None]).T @ (X[:-l] * e[:-l, None]); Sg += w * (G_ + G_.T)
                V = XtXi @ Sg @ XtXi
                store[c] = b[0] / math.sqrt(V[0, 0])
                rw = Rw[c].to_numpy(float); pred = Dw @ b[1:]; res = rw - pred
                okr = np.isfinite(res)
                tpca[c] = r.n_q / okr.sum() * res[okr].sum() if okr.sum() else np.nan
            else:
                r2 = 1 - (e @ e) / (((yy - yy.mean()) ** 2).sum()); store[c] = 1 - (1 - (1 - r2) * (n - 1) / (n - k))
    a1s, c1s, tps = pd.Series(a1), pd.Series(c1), pd.Series(tpca)
    def icx(s):
        o = s.notna() & tps.reindex(s.index).notna()
        return stats.spearmanr(s[o], tps.reindex(s.index)[o]).statistic, int(o.sum())
    fa = ics[(ics.trial == "P2-A1") & (ics.col == "IC") & (ics.t == str(r.t.date()))]
    fc = ics[(ics.trial == "P2-C1") & (ics.col == "IC") & (ics.t == str(r.t.date()))]
    # เทียบสัญญาณ/target กับของ lib
    sig = st["sig"]; dft = tg["df"]
    G[str(r.t.date())] = dict(
        nU=len(U), nUt=len(Ut),
        B0_mine=round(ic_b0, 6), B0_file=round(float(f_ic.value.iloc[0]), 6), N_b0=int(ok.sum()), N_file=float(f_ic.N.iloc[0]),
        A1_mine=icx(a1s), A1_file=round(float(fa.value.iloc[0]), 6),
        C1_mine=icx(c1s), C1_file=round(float(fc.value.iloc[0]), 6),
        maxdiff_Tpca=float(np.nanmax(np.abs(tps - dft["T_PCA"].reindex(tps.index)))),
        corr_tA1=float(np.corrcoef(a1s, sig["A1"].reindex(a1s.index))[0, 1]),
        maxdiff_C1=float(np.nanmax(np.abs(c1s - sig["C1"].reindex(c1s.index)))))
OUT["G_recompute"] = G

# future-scramble เพิ่มที่ 2022-06-24 (j=1) และ 2025-06-27 (j=13): แทนแถว > t ด้วยค่าสุ่ม
rng = np.random.default_rng(7)
fs = {}
for j in (1, 13):
    r = DQ.iloc[j]; t = r.t
    def scr(X):
        X = X.copy(); m = X.index > t
        V = rng.standard_normal((int(m.sum()), X.shape[1])) * 0.03
        V[rng.random(V.shape) < 0.2] = np.nan
        X.loc[m] = V
        return X
    Zs = INP.Z.copy(); Zs.loc[Zs.index > t] = (rng.random(Zs.loc[Zs.index > t].shape) < 0.5).astype(float)
    INP2 = p2.Inputs(scr(INP.R), Zs, scr(INP.F3), scr(INP.AUM).abs() * 1e9, INP.meta)
    pv1 = pv2 = None
    for jj in range(j + 1):
        rr = DQ.iloc[jj]
        pv1 = p2.state_at(INP, rr.t_pos, pv1, None); pv2 = p2.state_at(INP2, rr.t_pos, pv2, None)
    eq = dict(U=pv1["U"] == pv2["U"], S=pv1["S"] == pv2["S"],
              sig=bool(np.array_equal(pv1["sig"].to_numpy(float), pv2["sig"].to_numpy(float), equal_nan=True)),
              Lam=bool(np.array_equal(pv1["Lam_al"], pv2["Lam_al"])), Q=bool(np.array_equal(pv1["Q"], pv2["Q"])))
    fs[str(t.date())] = eq
OUT["H_future_scramble_extra"] = fs

# regression phase 1 summary
rg = json.load(open(RUN / "regression_phase1.json"))
OUT["I_regress"] = {k: ({kk: (vv if not isinstance(vv, (dict, list)) else (len(vv))) for kk, vv in v.items()} if isinstance(v, dict) else v) for k, v in rg.items()}

json.dump(OUT, open(TEAM / "scratch/factor-reviewer_s010_result_check.json", "w"), ensure_ascii=False, indent=1, default=str)
print(json.dumps(OUT, ensure_ascii=False, indent=1, default=str))
