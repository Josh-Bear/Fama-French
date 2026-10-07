"""diag_leadlag.py — DIAGNOSTIC (ไม่ใช่ trial, ไม่รายงาน Sharpe): ตรวจ correlation ต่ำเกินจริงจาก NAV ไม่พร้อมกัน
ต่อ Trend 25 (M004-TF-FX). reuse analysis.fund_signals / fund_weighting แบบ read-only. ไม่เขียน trials.csv"""
from __future__ import annotations
import os, sys, warnings
import numpy as np, pandas as pd
warnings.filterwarnings("ignore")
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, ROOT); os.chdir(ROOT)
import data_access
from analysis import fund_signals as fs, fund_weighting as fw
from data import msci_index
from sklearn.covariance import LedoitWolf
OUT = os.path.join(ROOT, ".claude/quant_team/backtest/results")

def psd_clip(S, eps=1e-10):
    S = (S + S.T) / 2; w, V = np.linalg.eigh(S); mn = w.min()
    return (V * np.clip(w, eps * max(w.max(), 1e-12), None)) @ V.T, mn

def cov_leadlag(X, bart=1.0):
    """X: T×n (ไม่มี NaN). Σ = Γ0 + bart·(Γ1+Γ1ᵀ) · ×52 · คืน (Σ_psd, min eig ก่อน clip)."""
    Xc = X - X.mean(0); T = len(Xc)
    G0 = Xc.T @ Xc / (T - 1); G1 = Xc[1:].T @ Xc[:-1] / (T - 1)   # G1[i,j]=cov(r_i,t ; r_j,t-1)
    S = (G0 + bart * (G1 + G1.T)) * 52.0
    return psd_clip(S)

def corr(S):
    d = np.sqrt(np.clip(np.diag(S), 1e-14, None)); return S / np.outer(d, d)

def offdiag(C):
    return C[np.triu_indices_from(C, 1)]

def risk_stats(w, S):
    w = np.asarray(w); v = w @ S @ w; vol = np.sqrt(v); sig = np.sqrt(np.diag(S))
    dr = (w @ sig) / vol
    # ENB (Meucci) จาก PCA ของ Σ
    lam, V = np.linalg.eigh(S); e = V.T @ w; p = (e ** 2) * lam; p = p / p.sum(); p = p[p > 1e-12]
    return vol, dr, np.exp(-(p * np.log(p)).sum())

def main():
    inp = data_access._tf_inputs(); cal = inp.calendar
    nav = inp.nav; hold = data_access.load_tf_cache()["holdings"]
    hold = hold[(hold["FundCode"] != "__CASH__") & (~hold["skipped"])]
    ts = sorted(t for t in hold["t"].unique() if pd.Timestamp("2022-03-31") <= t <= pd.Timestamp("2025-12-31"))
    funds_all = sorted(hold["FundCode"].unique())
    nbf = {fc: g.sort_values("NAVDate").set_index("NAVDate")["NAV"] for fc, g in nav[nav.FundCode.isin(funds_all)].groupby("FundCode")}
    arr = fs.prep_arrays(nbf)
    asia_kw = ("VIET", "UVO", "K-VIETNAM", "CHINA", "ASIA", "JAPAN", "JPFUND", "INDIA", "ASEAN", "KOREA", "TAIWAN", "VNEQ", "ASP-V")
    rows, pairs, wrows = [], [], []
    ctx_next = {}
    for i, t in enumerate(ts):
        h = hold[hold.t == t]; funds = h["FundCode"].tolist(); wa = h.set_index("FundCode")["weight"].astype(float)
        wa = wa / wa.sum(); ctx = fs.SignalContext(arr, cal, t)
        wr = {fc: ctx.weekly_return_series(fc) for fc in funds}
        mat = pd.DataFrame(wr).dropna(how="any"); X = mat.to_numpy(); n = len(funds)
        if len(mat) < 30: rows.append({"t": t.date(), "n": n, "weeks": len(mat), "note": "skip<30w"}); continue
        S0 = LedoitWolf().fit(X).covariance_ * 52.0
        Sa, mn_a = cov_leadlag(X, 1.0); Sb, mn_b = cov_leadlag(X, 0.5)
        # monthly 36m
        mp = fs.month_end_points(cal, t, 37)
        P = pd.DataFrame({fc: [fs._asof(*arr[fc], np.datetime64(m.date()), 40) for m in mp] for fc in funds}, index=mp)
        Rm = (P / P.shift(1) - 1).iloc[1:]; Rm = Rm.replace([np.inf, -np.inf], np.nan)
        Cm = Rm.corr(min_periods=24).to_numpy(); nm = int(Rm.dropna(how="any").shape[0])
        Xm = Rm.dropna(how="any")
        Sm = LedoitWolf().fit(Xm.to_numpy()).covariance_ * 12.0 if len(Xm) >= 24 else None
        C0, Ca, Cb = corr(S0), corr(Sa), corr(Sb)
        r = {"t": t.date(), "n": n, "weeks": len(mat), "months_all_funds": nm,
             "minEig_adj_raw": mn_a, "psd_clipped": mn_a < 0}
        for nm_, C in (("lag0_LW", C0), ("adj_full", Ca), ("adj_NW05", Cb), ("monthly", Cm)):
            o = offdiag(C); o = o[~np.isnan(o)]; r[f"{nm_}_npairs"] = len(o)
            r[f"{nm_}_med"], r[f"{nm_}_q25"], r[f"{nm_}_q75"] = (np.median(o), *np.percentile(o, [25, 75])) if len(o) else (np.nan,) * 3
        # raw (ไม่ shrink) lag0 สำหรับเทียบ
        r["lag0_raw_med"] = np.median(offdiag(np.corrcoef(X.T)))
        # ERC
        w0 = fw.erc_weights(S0, funds).to_numpy(); w1 = fw.erc_weights(Sa, funds).to_numpy(); w2 = fw.erc_weights(Sb, funds).to_numpy()
        wact = wa.reindex(funds).to_numpy()
        r["maxdw_adj_vs_erc0"] = np.abs(w1 - w0).max(); r["tv_adj_vs_erc0"] = np.abs(w1 - w0).sum() / 2
        r["maxdw_adj_vs_actual"] = np.abs(w1 - wact).max(); r["tv_adj_vs_actual"] = np.abs(w1 - wact).sum() / 2
        r["tv_erc0_vs_actual"] = np.abs(w0 - wact).sum() / 2; r["tv_NW05_vs_erc0"] = np.abs(w2 - w0).sum() / 2
        # risk ของพอร์ตจริง (equity sleeve normalized) และ ERC ใหม่
        for tag, S in (("lag0", S0), ("adj", Sa), ("adjNW05", Sb)):
            vol, dr, enb = risk_stats(wact, S); r[f"vol_{tag}"] = vol; r[f"DR2_{tag}"] = dr ** 2; r[f"ENB_{tag}"] = enb
        r["vol_ratio_adj_over_lag0"] = r["vol_adj"] / r["vol_lag0"]
        # realized ไตรมาสถัดไป (13 สัปดาห์ หลัง t) ด้วยน้ำหนักจริงคงที่รายสัปดาห์
        if i + 1 < len(ts):
            tn = ts[i + 1]; cn = fs.SignalContext(arr, cal, tn)
            Rn = pd.DataFrame({fc: cn.weekly_return_series(fc) for fc in funds}); Rn = Rn[Rn.index > t].dropna(how="any")
            if len(Rn) >= 8:
                pr = Rn.to_numpy() @ wact
                r["realized_vol"] = pr.std(ddof=1) * np.sqrt(52); r["realized_ms"] = (pr ** 2).mean() * 52; r["real_weeks"] = len(Rn)
                r["ms_pred_lag0"] = r["vol_lag0"] ** 2; r["ms_pred_adj"] = r["vol_adj"] ** 2
        rows.append(r)
        # คู่
        for a in range(n):
            for b in range(a + 1, n):
                pairs.append({"t": t.date(), "f1": funds[a], "f2": funds[b], "rho0": C0[a, b], "rho_adj": Ca[a, b], "rho_NW05": Cb[a, b],
                              "rho_monthly": Cm[a, b], "d": Ca[a, b] - C0[a, b]})
        for fc, a, b, c in zip(funds, wact, w0, w1): wrows.append({"t": t.date(), "FundCode": fc, "w_actual_eqnorm": a, "w_erc_lag0": b, "w_erc_adj": c})
    R = pd.DataFrame(rows); P = pd.DataFrame(pairs); W = pd.DataFrame(wrows)
    R.to_csv(f"{OUT}/DIAG_leadlag_quarterly.csv", index=False); P.to_csv(f"{OUT}/DIAG_leadlag_pairs.csv", index=False); W.to_csv(f"{OUT}/DIAG_leadlag_weights.csv", index=False)
    pd.set_option("display.width", 250); pd.set_option("display.max_columns", 50)
    print(R[["t", "n", "weeks", "months_all_funds", "lag0_LW_med", "adj_full_med", "adj_NW05_med", "monthly_med", "lag0_raw_med", "minEig_adj_raw"]].round(3).to_string())
    print(R[["t", "tv_erc0_vs_actual", "maxdw_adj_vs_erc0", "tv_adj_vs_erc0", "tv_adj_vs_actual", "tv_NW05_vs_erc0", "vol_lag0", "vol_adj", "vol_ratio_adj_over_lag0", "DR2_lag0", "DR2_adj", "ENB_lag0", "ENB_adj", "realized_vol"]].round(3).to_string())
    print("MEDIANS of quarterly:\n", R.drop(columns=["t"]).median(numeric_only=True).round(3).to_string())
    # pooled realized
    Q = R.dropna(subset=["realized_ms"])
    print("n realized q:", len(Q), "pooled RMS ratio lag0:", np.sqrt(Q.realized_ms.mean() / Q.ms_pred_lag0.mean()), "adj:", np.sqrt(Q.realized_ms.mean() / Q.ms_pred_adj.mean()))
    print("mean|log ratio| lag0", np.abs(np.log(np.sqrt(Q.realized_ms / Q.ms_pred_lag0))).mean(), "adj", np.abs(np.log(np.sqrt(Q.realized_ms / Q.ms_pred_adj))).mean())
    print("pooled pair stats: mean d", P.d.mean(), "median d", P.d.median(), "frac d>0", (P.d > 0).mean(), "median rho0", P.rho0.median(), "adj", P.rho_adj.median(), "monthly", P.rho_monthly.median())
    last = P[P.t == pd.Timestamp("2025-12-31").date()].sort_values("d", ascending=False); print(last.round(3).head(8).to_string())
    top = P.sort_values("d", ascending=False).head(12); print(top.round(3).to_string())
    # asia vs west
    def isasia(f): return any(k in f.upper() for k in asia_kw)
    P["grp"] = [("AA" if isasia(a) and isasia(b) else "WW" if (not isasia(a)) and (not isasia(b)) else "AW") for a, b in zip(P.f1, P.f2)]
    print(P.groupby("grp")[["rho0", "rho_adj", "rho_monthly", "d"]].agg(["median", "count"]).round(3).to_string())
    # sanity MSCI
    c = msci_index.load_country_index()
    pairs_s = [("MSCI_JAPAN", "MSCI_USA"), ("MSCI_KOREA", "MSCI_USA"), ("MSCI_TAIWAN", "MSCI_USA"), ("MSCI_ASIA_EX_JAPAN", "MSCI_USA"), ("MSCI_INDIA", "MSCI_USA"), ("MSCI_JAPAN", "MSCI_EUROPE"), ("MSCI_EUROPE", "MSCI_USA")]
    srows = []
    for freq in ("daily", "weekly"):
        L = np.log(c); R_ = L.diff().dropna() if freq == "daily" else L.resample("W-FRI").last().diff().dropna()
        for a, b in pairs_s:
            X = R_[[a, b]].to_numpy(); Xc = X - X.mean(0); T = len(X)
            G0 = Xc.T @ Xc / (T - 1); G1 = Xc[1:].T @ Xc[:-1] / (T - 1)
            S = G0 + G1 + G1.T; Sn = G0 + 0.5 * (G1 + G1.T)
            srows.append({"freq": freq, "pair": f"{a[5:]}-{b[5:]}", "T": T, "rho_lag0": G0[0, 1] / np.sqrt(G0[0, 0] * G0[1, 1]),
                          "rho_adj": S[0, 1] / np.sqrt(S[0, 0] * S[1, 1]), "rho_NW05": Sn[0, 1] / np.sqrt(Sn[0, 0] * Sn[1, 1]),
                          "cross_lag(a_t,b_t-1)": G1[0, 1] / np.sqrt(G0[0, 0] * G0[1, 1]), "cross_lag(b_t,a_t-1)": G1[1, 0] / np.sqrt(G0[0, 0] * G0[1, 1])})
    SR = pd.DataFrame(srows); SR.to_csv(f"{OUT}/DIAG_leadlag_msci_sanity.csv", index=False); print(SR.round(3).to_string())
    P.to_csv(f"{OUT}/DIAG_leadlag_pairs.csv", index=False)

if __name__ == "__main__": main()
