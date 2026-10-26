"""factor-reviewer · รีวิวผล S014 + S015 · คำนวณซ้ำด้วยโค้ดของ reviewer (numpy ล้วน · อ่าน parquet / holdings ตรง) + future-scramble บนข้อมูลจริง
อ่านอย่างเดียว · เขียนเฉพาะ scratch/factor-reviewer_s014_result_check.json
รันจาก root: PYTHONPATH=. ./.venv/bin/python .claude/factor_team/scratch/factor-reviewer_s014_result_check.py"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

T = Path(".claude/factor_team")
RUN = T / "runs" / "S014"
REF = Path("base_data/reference")
D = T / "data"
res = {}

F = pd.read_parquet(D / "factors_weekly.parquet").loc["2021-01-08":"2025-12-26"]
Fext = pd.read_parquet(D / "factors_ext_weekly.parquet").loc["2021-01-08":"2025-12-26"]
Feo = pd.read_parquet(D / "factors_eo_noaqr_weekly.parquet").loc["2021-01-08":"2025-12-26"]
assert not any(c.upper().startswith("AQR") for c in Feo.columns)
idx = F.index
rf = F["RF_BOT"]
P = pd.read_parquet(D / "panel_weekly.parquet")
W = P.pivot(index="date", columns="FundCode", values="ret").sort_index().loc["2021-01-08":"2025-12-26"]
Rraw = W.reindex(idx)
Rx = Rraw.sub(rf, axis=0)
res["max_index"] = str(idx.max())

H = pd.read_csv(REF / "m052_frontier_holdings.csv", comment="#", parse_dates=["t", "e"])
MP = pd.read_csv(RUN / "mapping_codes.csv").set_index("FundCode")
QT = pd.read_csv(RUN / "quarters.csv", parse_dates=["t", "e", "first_anchor", "last_anchor"])

base = pd.DataFrame({"MKT": F["MSCI_ACWI"] - rf, "FX": F["SHV_THB"] - rf, "CMA": Feo["KF_DEV_CMA"], "GOLD_XS": Feo["GLD_USD"] - F["SHV_USD"]})
Ig = {"e_CHINAg": F["MSCI_CHINA_ALL_SHARES"] - rf, "e_ASIA": F["MSCI_ASIA_EX_JAPAN"] - rf, "e_EUROPE": F["MSCI_EUROPE"] - rf, "e_USA": F["MSCI_USA"] - rf,
      "e_JAPAN": F["MSCI_JAPAN"] - rf, "e_INDIA": F["MSCI_INDIA"] - rf, "e_HC": F["MSCI_ACWI_HC"] - rf, "e_IT": F["MSCI_ACWI_IT"] - rf,
      "e_VIETNAM": F["MSCI_VIETNAM"] - rf, "e_ARKK": Fext["ARKK_THB"] - rf, "e_IGF": Fext["IGF_THB"] - rf}
GN = {"e_CHINA(grp)": "e_CHINAg"}


def win(t):
    return np.asarray((idx <= t) & (idx > t - pd.Timedelta(weeks=156)))


def resid(I, X, m):
    y = I.to_numpy(float); Xv = X.to_numpy(float)
    ok = m & np.isfinite(y) & np.isfinite(Xv).all(1)
    b = np.linalg.lstsq(np.column_stack([np.ones(ok.sum()), Xv[ok]]), y[ok], rcond=None)[0]
    return pd.Series(y - Xv @ b[1:], index=I.index)


def lagged(A):
    L = np.full_like(A, np.nan); L[1:] = A[:-1]; return L


def fit(y, Dm, m):
    """Dimson OLS ในหน้าต่าง · → b (1 + 2K), ssr, n"""
    A = Dm.to_numpy(float)
    X = np.hstack([A, lagged(A)])
    ok = m & np.isfinite(y) & np.isfinite(X).all(1)
    n = int(ok.sum()); assert n >= 52
    Z = np.column_stack([np.ones(n), X[ok]])
    b = np.linalg.lstsq(Z, y[ok], rcond=None)[0]
    e = y[ok] - Z @ b
    return b, float(e @ e), n, A


def quarter(t):
    m = win(t)
    hq = H[H["t"] == t]
    X1 = base[["MKT", "FX", "CMA"]]
    out = []
    for h in hq.itertuples(index=False):
        mp = MP.loc[h.FundCode]
        if h.kind == "G":
            Dm = base[["GOLD_XS", "FX"]]
        else:
            Dm = X1.copy()
            if mp["group_factor"] != "ไม่มี":
                nm = GN.get(mp["group_factor"], mp["group_factor"])
                Dm[nm] = resid(Ig[nm], X1, m)
        y = Rx[mp["unit"]].to_numpy(float)
        b, ssr, n, A = fit(y, Dm, m)
        K = Dm.shape[1]
        out.append(dict(code=h.FundCode, unit=mp["unit"], w=float(h.weight), kind=h.kind, names=list(Dm.columns), b=b, K=K,
                        beta=b[1:1 + K] + b[1 + K:], s2=ssr / (n - (1 + 2 * K)), D=Dm, n=n))
    names = []
    for o in out:
        for c in o["names"]:
            if c not in names:
                names.append(c)
    B = np.zeros(len(names))
    for o in out:
        for j, c in enumerate(o["names"]):
            B[names.index(c)] += o["w"] * o["beta"][j]
    FU = pd.concat([o["D"] for o in out], axis=1)
    FU = FU.loc[:, ~FU.columns.duplicated()][names]
    Xf = FU.to_numpy(float)
    ok = m & np.isfinite(Xf).all(1)
    Sig = np.cov(Xf[ok], rowvar=False, ddof=1)
    w = np.array([o["w"] for o in out]); s2 = np.array([o["s2"] for o in out])
    SB = Sig @ B
    V = float(B @ SB + np.sum(w ** 2 * s2))
    return dict(out=out, names=names, B=B, share=B * SB / V, share_eps=float(np.sum(w ** 2 * s2)) / V, V=V)


EX = pd.read_csv(RUN / "exposure.csv", parse_dates=["t"]).set_index("t")
CO = pd.read_csv(RUN / "concentration.csv", parse_dates=["t"]).set_index("t")
TS = sorted(H["t"].unique())
QS = {t: quarter(t) for t in TS}
mxB = mxS = 0.0
for t, q in QS.items():
    for j, c in enumerate(q["names"]):
        mxB = max(mxB, abs(q["B"][j] - EX.loc[t, "B_" + c]))
        mxS = max(mxS, abs(q["share"][j] - CO.loc[t, "share_" + c]))
    mxS = max(mxS, abs(q["share_eps"] - CO.loc[t, "share_eps"]))
res["exposure_max_abs_diff_all15q"] = mxB
res["share_max_abs_diff_all15q"] = mxS
res["exposure_sample"] = {str(t.date()): {c: round(float(QS[t]["B"][j]), 4) for j, c in enumerate(QS[t]["names"])} for t in (TS[0], TS[5], TS[13])}

# ---------- attribution L1 (reviewer) ----------
comp_tot, comp_22, comp_by_hold = {}, {}, {}
xs_all, rp_all, rf_all, t_all = [], [], [], []
y22 = [pd.Timestamp(x) for x in ("2022-03-31", "2022-06-30", "2022-09-30")]
for t in TS:
    q = QS[t]
    row = QT[QT["t"] == t].iloc[0]
    anc = idx[(idx >= row["first_anchor"]) & (idx <= row["last_anchor"])]
    assert len(anc) == 13
    pos = np.array([idx.get_loc(a) for a in anc])
    rfs = rf.to_numpy(float)[pos]
    Rex = np.column_stack([Rx[o["unit"]].to_numpy(float)[pos] for o in q["out"]])
    Rr = Rex + rfs[:, None]
    w = np.array([o["w"] for o in q["out"]])
    for s in range(len(pos)):
        rp = float(w @ Rr[s]); x = float(w @ Rex[s])
        tot = 0.0
        for i, o in enumerate(q["out"]):
            A = o["D"].to_numpy(float)
            cur, lag = A[pos[s]], A[pos[s] - 1]
            K = o["K"]
            fitted = o["b"][0] + cur @ o["b"][1:1 + K] + lag @ o["b"][1 + K:]
            for j, c in enumerate(o["names"]):
                v = w[i] * (o["b"][1 + j] * cur[j] + o["b"][1 + K + j] * lag[j])
                comp_tot[c] = comp_tot.get(c, 0) + v
                if t in y22:
                    comp_22[c] = comp_22.get(c, 0) + v
                tot += v
            a_ = w[i] * o["b"][0]; e_ = w[i] * (Rex[s, i] - fitted)
            for k_, v_ in (("A", a_), ("E", e_)):
                comp_tot[k_] = comp_tot.get(k_, 0) + v_
                if t in y22:
                    comp_22[k_] = comp_22.get(k_, 0) + v_
                comp_by_hold.setdefault(o["code"], {"A": 0.0, "E": 0.0})[k_] += v_
            tot += a_ + e_
        assert abs(tot - x) < 1e-12
        xs_all.append(x); rp_all.append(rp); rf_all.append(rfs[s]); t_all.append(t)
        g = w * (1 + Rr[s]); w = g / g.sum()
xs_all, rp_all, rf_all, t_all = map(np.array, (xs_all, rp_all, rf_all, t_all))


def cex(mask):
    return float(np.prod(1 + rp_all[mask]) - np.prod(1 + rf_all[mask])), float(xs_all[mask].sum())


allm = np.ones(len(xs_all), bool); m22 = np.isin(t_all, y22)
c_all, s_all = cex(allm); c22, s22 = cex(m22)
grp = lambda d: sum(v for k, v in d.items() if k.startswith("e_"))
res["L1_total_pp"] = {k: round(v * 100, 3) for k, v in sorted(comp_tot.items())} | {"groups_sum": round(grp(comp_tot) * 100, 3), "SUM": round(s_all * 100, 3),
                                                                                  "CEX": round(c_all * 100, 3), "K": round((c_all - s_all) * 100, 3), "cum_rp": round((np.prod(1 + rp_all) - 1) * 100, 3)}
res["L1_2022_pp"] = {k: round(v * 100, 3) for k, v in sorted(comp_22.items())} | {"groups_sum": round(grp(comp_22) * 100, 3), "SUM": round(s22 * 100, 3),
                                                                                 "CEX": round(c22 * 100, 3), "K": round((c22 - s22) * 100, 3)}
S = pd.read_csv(RUN / "attribution_summary.csv")
f_all = S[(S.lens == "L1") & S.period.str.startswith("ทั้ง")].set_index("component")["value"]
f_22 = S[(S.lens == "L1") & S.period.str.startswith("ปี 2022")].set_index("component")["value"]
res["L1_total_max_abs_diff_vs_file"] = float(max(abs(comp_tot[k] - f_all[k]) for k in comp_tot))
res["L1_2022_max_abs_diff_vs_file"] = float(max(abs(comp_22[k] - f_22[k]) for k in comp_22))
res["CEX_diff_vs_file"] = float(c_all - f_all["CEX = Π(1+r_p) − Π(1+rf)"])
ae = {k: round((v["A"] + v["E"]) * 100, 2) for k, v in comp_by_hold.items()}
res["A_plus_E_by_holding_pp"] = dict(sorted(ae.items(), key=lambda kv: -abs(kv[1])))
res["A_by_holding_pp"] = {k: round(v["A"] * 100, 2) for k, v in sorted(comp_by_hold.items(), key=lambda kv: -abs(kv[1]["A"]))}

# ---------- P-C ปี 2022 ----------
pc = []
for t in y22:
    q = QS[t]
    row = QT[QT["t"] == t].iloc[0]
    anc = idx[(idx >= row["first_anchor"]) & (idx <= row["last_anchor"])]
    cum = {o["code"]: float(np.prod(1 + Rraw[o["unit"]].loc[anc].to_numpy(float)) - 1) for o in q["out"]}
    wE = {o["code"]: o["w"] for o in q["out"] if o["kind"] == "E"}; wG = {o["code"]: o["w"] for o in q["out"] if o["kind"] == "G"}
    x = sum(wE.values())
    RE = sum(wE[k] / x * cum[k] for k in wE); RG = sum(wG[k] / sum(wG.values()) * cum[k] for k in wG)
    pc.append(dict(t=str(t.date()), x=x, R_E=RE, R_G=RG, AE=(x - 0.57) * (RE - RG)))
res["PC_2022"] = pc
res["PC_2022_sumAE_pp"] = round(sum(p["AE"] for p in pc) * 100, 3)

# ---------- future-scramble บนข้อมูลจริง (ฟังก์ชันของ lib) ----------
sys.path.insert(0, str(T / "lib"))
import io_l1  # noqa: E402
import l1eo  # noqa: E402
import port  # noqa: E402
R0 = io_l1.load_returns("W")
FR0 = port.factor_frames(F, Fext, Feo)
MPI = pd.read_csv(RUN / "mapping_codes.csv").set_index("FundCode")
rng = np.random.default_rng(4242)


def snap(R_, FR_, t):
    qf = port.quarter_fit(R_, FR_, t, H[H["t"] == t].reset_index(drop=True), MPI, "main")
    Sig, n = port.sigma_f(qf)
    B, seB, w, s2 = port.exposure(qf)
    d = port.var_decomp(B, Sig, w, s2)
    blob = [np.r_[f["alpha"], f["b0"], f["b1"], f["se_beta"], f["s2"]] for f in qf["fits"]]
    return dict(fits=np.concatenate(blob), coef=qf["coef"].to_csv(index=False) if len(qf["coef"]) else "", Sig=Sig, B=B, seB=seB, share=d["share"], eps=d["share_eps"], n=n)


scr = {}
for t in (TS[0], TS[4], TS[7], TS[12]):
    late = R0.index > t
    Rs = R0.copy(); Rs.loc[late] = np.where(Rs.loc[late].notna(), rng.normal(0, 0.05, size=Rs.loc[late].shape), np.nan)
    FRs = {"base": FR0["base"].copy(), "I": FR0["I"].copy(), "rf": FR0["rf"], "gld_thb": FR0["gld_thb"]}
    for k in ("base", "I"):
        FRs[k].loc[late] = rng.normal(0, 0.05, size=FRs[k].loc[late].shape)
    a, b = snap(R0, FR0, t), snap(Rs, FRs, t)
    scr[str(t.date())] = {k: bool(np.array_equal(a[k], b[k]) if not isinstance(a[k], str) else a[k] == b[k]) for k in a}
res["future_scramble"] = scr
res["future_scramble_all_equal"] = all(all(v.values()) for v in scr.values())

json.dump(res, open(T / "scratch" / "factor-reviewer_s014_result_check.json", "w"), indent=1, ensure_ascii=False, default=float)
print(json.dumps(res, indent=1, ensure_ascii=False, default=float))
