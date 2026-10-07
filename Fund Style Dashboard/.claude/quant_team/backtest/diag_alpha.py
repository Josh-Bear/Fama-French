"""diag_alpha.py — DIAGNOSTIC (ไม่ใช่ trial · ไม่แตะ trials.csv/ALL_RESULTS · ไม่รายงาน Sharpe ของพอร์ต)
R004 ไอเดีย #0: alpha เทียบดัชนีคู่ (Dimson lag1 + USDTHB) ของ family ที่คัดได้ ณ สิ้นไตรมาส · persistence 4Q ข้างหน้า · ดัชนีราคา vs รวมปันผล

นิยามล็อกก่อนรัน (R004 #1):
  * ณ t ทุกสิ้นไตรมาส 2022-03-31..2025-12-31 · ข้อมูล <= t เท่านั้น · expanding weekly (ขั้นต่ำ 52 สัปดาห์)
  * ดัชนีคู่ = ตัวที่ R² สูงสุดของ r_f ~ 1 + x_t + x_{t-1} (Dimson, ไม่ใส่ FX) จาก 28 ดัชนี (18 country + 10 sector, รวม ACWI)
  * alpha = intercept ของ r_f = a + b0 x_t + b1 x_{t-1} + g*dUSDTHB_t + e   (alpha_ann = 52*a) · TE = sd(e)*sqrt(52) · IR = alpha_ann/TE
  * alpha อนาคต (t, t+4Q]: ดัชนีคู่เดิม ณ t · (หลัก) ประมาณใหม่ในหน้าต่าง · (robust) beta/gamma ตรึงจาก t · (robust) BAR = mean(r_f - r_idx)*52
  * IC ต่อไตรมาสคำนวณเฉพาะ t ที่ t+4Q <= 2025-12-31 (NAV ปี 2026 มีรู) -> 12 ไตรมาส (2022-03 .. 2024-12)
READ-ONLY ต่อแอป/cache/base_data. เรียกเฉพาะ data_access.tf_live / _tf_inputs / load_tf_cache (อ่านอย่างเดียว)"""
from __future__ import annotations
import os, sys, re, warnings
import numpy as np, pandas as pd
from scipy import stats
warnings.filterwarnings("ignore")
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, ROOT); os.chdir(ROOT)
import data_access
from data import msci_index
OUT = os.path.join(ROOT, ".claude/quant_team/backtest/results")
MIN_W = 52          # สัปดาห์ขั้นต่ำสำหรับ alpha ณ t
MIN_W_FWD = 40      # สัปดาห์ขั้นต่ำในหน้าต่างอนาคต
MAX_WK_RET = 0.5    # |return รายสัปดาห์| > 50% = NAV ผิดปกติ -> NaN
EVAL_END = pd.Timestamp("2025-12-31")


# ---------- grid / asof ----------
def weekly_grid(cal: pd.DatetimeIndex, t: pd.Timestamp) -> list[pd.Timestamp]:
    """วันทำการสุดท้ายของแต่ละ ISO week ที่ <= t (จุดสุดท้าย = วันสุดท้ายของปฏิทิน <= t ในสัปดาห์นั้น) — เหมือน weekly_points ของทีม แต่ไม่จำกัดจำนวน."""
    c = cal[cal <= t]
    iso = c.isocalendar()
    df = pd.DataFrame({"d": c, "y": iso["year"].to_numpy(), "w": iso["week"].to_numpy()})
    return sorted(pd.Timestamp(v) for v in df.groupby(["y", "w"])["d"].max().to_numpy())


def asof_vec(dates: np.ndarray, vals: np.ndarray, days: np.ndarray, tol: int = 10) -> np.ndarray:
    idx = np.searchsorted(dates, days, side="right") - 1
    out = np.full(len(days), np.nan)
    ok = idx >= 0
    gap = np.where(ok, (days - dates[np.clip(idx, 0, None)]) / np.timedelta64(1, "D"), np.inf)
    ok &= gap <= tol
    out[ok] = vals[idx[ok]]
    return out


def lag(x: np.ndarray) -> np.ndarray:
    y = np.full_like(x, np.nan); y[1:] = x[:-1]; return y


# ---------- OLS ----------
def ols(y: np.ndarray, X: np.ndarray):
    """X ไม่รวม const · คืน (coef[const,...], resid, R2, n) หรือ None"""
    m = np.isfinite(y) & np.all(np.isfinite(X), axis=1)
    n = int(m.sum())
    if n < X.shape[1] + 5:
        return None
    A = np.column_stack([np.ones(n), X[m]]); yy = y[m]
    b, *_ = np.linalg.lstsq(A, yy, rcond=None)
    e = yy - A @ b; sst = ((yy - yy.mean()) ** 2).sum()
    r2 = 1 - (e ** 2).sum() / sst if sst > 0 else np.nan
    return b, e, r2, n


def wk_returns(p: np.ndarray) -> np.ndarray:
    r = np.full(len(p), np.nan)
    with np.errstate(invalid="ignore", divide="ignore"):
        r[1:] = p[1:] / p[:-1] - 1.0
    r[np.abs(r) > MAX_WK_RET] = np.nan
    return r


def hedge_class(fc: str) -> str:
    toks = [x for x in re.split(r"[-\s]+", fc.upper().strip()) if x]
    if any(x == "H" for x in toks): return "H"
    if any(x == "UH" or x.endswith("UH") or "(UH)" in x for x in toks) or "UH" in fc.upper().replace("-", ""): return "UH"
    return "other"


def hedge_key(fc: str) -> str:
    toks = [x for x in re.split(r"[-\s]+", fc.upper().strip()) if x]
    toks = ["*" if (x == "H" or x == "UH") else x for x in toks]
    return "-".join(toks)


def spearman(a, b):
    m = np.isfinite(a) & np.isfinite(b)
    if m.sum() < 8: return np.nan
    return stats.spearmanr(a[m], b[m]).correlation


def tstat(x: np.ndarray, nw: int = 0):
    x = x[np.isfinite(x)]
    n = len(x)
    if n < 3: return np.nan
    mu = x.mean(); d = x - mu
    v = (d @ d) / n
    for l in range(1, nw + 1):
        v += 2 * (1 - l / (nw + 1)) * (d[l:] @ d[:-l]) / n
    return mu / np.sqrt(v / n)


# ---------- main ----------
def main():
    inp = data_access._tf_inputs(); cal = inp.calendar; arrs = inp.nav_arrays
    cache = data_access.load_tf_cache(); hold = cache["holdings"]
    hold = hold[(hold["FundCode"] != "__CASH__") & (~hold["skipped"])]
    ts = sorted(t for t in cache["holdings"]["t"].unique() if pd.Timestamp("2022-03-31") <= t <= EVAL_END)
    assert len(ts) == 16, ts

    lv = pd.concat([msci_index.load_country_index(), msci_index.load_sector_index()], axis=1).sort_index()
    idx_names = list(lv.columns); assert len(idx_names) == 28
    I_dates = lv.index.values.astype("datetime64[D]"); I_vals = {c: lv[c].to_numpy(float) for c in idx_names}
    mf = pd.read_csv("base_data/MACRO_FACTOR.csv", parse_dates=["Date"]).set_index("Date").sort_index()
    has_fx = "USDTHB" in mf.columns
    fx_d = mf.index.values.astype("datetime64[D]"); fx_v = mf["USDTHB"].to_numpy(float)

    # ดัชนีบน grid: คืน dict name -> price array
    def grid_arrays(grid):
        days = np.array([np.datetime64(g.date()) for g in grid])
        P = {c: asof_vec(I_dates, I_vals[c], days) for c in idx_names}
        fxp = asof_vec(fx_d, fx_v, days)
        return days, P, fxp

    rows, fund_rows, sel_rows = [], [], []
    for qi, t in enumerate(ts):
        T2 = ts[qi + 4] if qi + 4 < len(ts) else None
        g_tr = weekly_grid(cal, t)
        g_fw = [t] + [p for p in weekly_grid(cal, T2) if p > t] if T2 is not None else [t]
        grid = g_tr + g_fw[1:]                       # จุดสุดท้ายของ train = t เสมอ? (ตรวจด้านล่าง)
        if g_tr[-1] != t:
            g_tr = g_tr + [t] if g_tr[-1] < t else g_tr
            grid = g_tr + g_fw[1:]
        n_tr = len(g_tr)                              # จำนวนจุด train; return ที่ตำแหน่ง k สิ้นสุดที่ grid[k]
        days, P, fxp = grid_arrays(grid)
        X_idx = {c: wk_returns(P[c]) for c in idx_names}
        fxr = wk_returns(fxp) if has_fx else None
        tr = slice(0, n_tr); fw = slice(n_tr, len(grid))     # fw: return ที่สิ้นสุดหลัง t

        r = data_access.tf_live(str(t.date()))
        tab = r["table"].copy()
        held = set(hold.loc[hold.t == t, "FundCode"])
        tab["held"] = tab["FundCode"].isin(held)
        tab["t"] = t

        # ทุกกองที่สด ณ t (สำหรับเทียบ H/UH ภายในคู่) — ใช้ universe_at ของโมเดล
        from analysis import fund_backtest as fb
        u_t = fb.universe_at(inp.nav, t)
        fresh = u_t.loc[(t - u_t["last_nav_date"]).dt.days <= 10, "FundCode"].tolist()
        fund_set = list(dict.fromkeys(list(tab["FundCode"]) + fresh))
        tab_codes = set(tab["FundCode"])

        for fc in fund_set:
            if fc not in arrs: continue
            d, v = arrs[fc]
            rf_all = wk_returns(asof_vec(d, v, days))
            y_tr = rf_all[tr]
            if np.isfinite(y_tr).sum() < MIN_W: continue
            # เลือกดัชนีคู่: R² สูงสุดของ Dimson (ข้อมูล <= t)
            best = None; r2s = {}
            for c in idx_names:
                x = X_idx[c][tr]
                res = ols(y_tr, np.column_stack([x, lag(x)]))
                if res is None or res[3] < MIN_W: continue
                r2s[c] = res[2]
                if best is None or res[2] > best[1]: best = (c, res[2])
            if best is None: continue
            c = best[0]
            r2_sorted = sorted(r2s.values(), reverse=True)
            x = X_idx[c]; xl = lag(x)
            Xf = np.column_stack([x[tr], xl[tr]] + ([fxr[tr]] if has_fx else []))
            res = ols(y_tr, Xf)
            if res is None or res[3] < MIN_W: continue
            b, e, r2f, n = res
            alpha_ann = 52 * b[0]; te = e.std(ddof=Xf.shape[1] + 1) * np.sqrt(52)
            # no-FX variant
            res0 = ols(y_tr, np.column_stack([x[tr], xl[tr]]))
            alpha0 = 52 * res0[0][0]
            m = np.isfinite(y_tr) & np.isfinite(x[tr])
            bar = 52 * np.mean(y_tr[m] - x[tr][m]); bar_te = np.std(y_tr[m] - x[tr][m], ddof=1) * np.sqrt(52)
            row = {"t": t, "FundCode": fc, "in_table": fc in tab_codes, "index": c, "r2_pick": best[1],
                   "r2_gap": (r2_sorted[0] - r2_sorted[1]) if len(r2_sorted) > 1 else np.nan, "n_wk": n,
                   "beta_sum": b[1] + b[2], "gamma_fx": b[3] if has_fx else np.nan, "alpha_ann": alpha_ann,
                   "alpha_ann_noFX": alpha0, "te_ann": te, "IR": alpha_ann / te if te > 0 else np.nan,
                   "bar_ann": bar, "bar_IR": bar / bar_te if bar_te > 0 else np.nan, "hedge": hedge_class(fc)}
            # อนาคต
            if T2 is not None:
                y_fw = rf_all[fw]
                Xw = np.column_stack([x[fw], xl[fw]] + ([fxr[fw]] if has_fx else []))
                rw = ols(y_fw, Xw)
                if rw is not None and rw[3] >= MIN_W_FWD:
                    row["alpha_fwd"] = 52 * rw[0][0]; row["n_wk_fwd"] = rw[3]
                # alpha ตรึง beta จาก t (ไม่มี intercept: a_hat = mean(y - Xb))
                mw = np.isfinite(y_fw) & np.all(np.isfinite(Xw), axis=1)
                if mw.sum() >= MIN_W_FWD:
                    row["alpha_fwd_fixed"] = 52 * np.mean(y_fw[mw] - Xw[mw] @ b[1:])
                pa = asof_vec(d, v, days[[n_tr - 1, -1]])
                if np.all(np.isfinite(pa)) and pa[0] > 0: row["ret_fwd"] = pa[1] / pa[0] - 1.0
                mb = np.isfinite(y_fw) & np.isfinite(x[fw])
                if mb.sum() >= MIN_W_FWD:
                    row["bar_fwd"] = 52 * np.mean(y_fw[mb] - x[fw][mb])
            fund_rows.append(row)
        print(f"t={t.date()} funds={sum(1 for r_ in fund_rows if r_['t']==t)} grid_tr={n_tr} grid_fw={len(grid)-n_tr}", flush=True)

        sel_rows.append(tab[["t", "family", "FundCode", "rank", "SR12", "held"]])

    F = pd.DataFrame(fund_rows)
    SEL = pd.concat(sel_rows, ignore_index=True)
    TAB = SEL.merge(F, on=["t", "FundCode"], how="left")      # family ที่คัดได้ + alpha
    F.to_csv(f"{OUT}/DIAG_alpha_funds.csv", index=False)
    TAB.to_csv(f"{OUT}/DIAG_alpha_table.csv", index=False)

    # ---------- IC ----------
    def ic_block(D: pd.DataFrame, preds: list[str], target: str, within: bool = False):
        out = []
        for t, g in D.groupby("t"):
            if target not in g or g[target].notna().sum() < 8: continue
            rec = {"t": t, "n": int(g[target].notna().sum())}
            for p in preds:
                a = g[p].to_numpy(float); y = g[target].to_numpy(float)
                if within:
                    gg = g[["index", p, target]].copy()
                    cnt = gg.groupby("index")[p].transform("count")
                    a = (gg[p] - gg.groupby("index")[p].transform("median")).where(cnt >= 3).to_numpy(float)
                    y = (gg[target] - gg.groupby("index")[target].transform("median")).where(cnt >= 3).to_numpy(float)
                rec[p] = spearman(a, y)
            out.append(rec)
        return pd.DataFrame(out)

    def summarize(ic: pd.DataFrame, preds):
        rows_ = []
        for p in preds:
            x = ic[p].to_numpy(float)
            rows_.append({"predictor": p, "n_q": int(np.isfinite(x).sum()), "mean_IC": np.nanmean(x), "sd": np.nanstd(x, ddof=1),
                          "t_naive": tstat(x), "t_NW3": tstat(x, 3), "pos_frac": np.nanmean(x > 0)})
        return pd.DataFrame(rows_)

    preds = ["alpha_ann", "IR", "bar_ann", "bar_IR", "SR12", "alpha_ann_noFX"]
    ev = TAB[TAB["in_table"].fillna(False) | TAB["rank"].notna()].copy()     # family ที่คัดได้เท่านั้น
    ev = ev[ev["alpha_ann"].notna()]
    ev16 = ev[ev["rank"] <= 16]
    res = {}
    for name, D in (("universe", ev), ("top16_SR12", ev16)):
        for tgt in ("alpha_fwd", "alpha_fwd_fixed", "bar_fwd", "ret_fwd"):
            ic = ic_block(D, preds, tgt); res[(name, tgt, "pooled")] = (ic, summarize(ic, preds))
        ic = ic_block(D, preds, "alpha_fwd", within=True); res[(name, "alpha_fwd", "within_index")] = (ic, summarize(ic, preds))
    ic_all = []
    for (nm, tg, kind), (ic, sm) in res.items():
        ic_all.append(ic.assign(universe=nm, target=tg, kind=kind))
    pd.concat(ic_all, ignore_index=True).to_csv(f"{OUT}/DIAG_alpha_ic_quarterly.csv", index=False)
    SUM = pd.concat([sm.assign(universe=nm, target=tg, kind=kind) for (nm, tg, kind), (ic, sm) in res.items()], ignore_index=True)
    SUM.to_csv(f"{OUT}/DIAG_alpha_ic_summary.csv", index=False)

    # ---------- descriptive ----------
    desc = []
    for t, g in ev.groupby("t"):
        desc.append({"t": t, "n": len(g), "median_alpha": g.alpha_ann.median(), "frac_neg": (g.alpha_ann < 0).mean(),
                     "median_alpha_noFX": g.alpha_ann_noFX.median(), "median_bar": g.bar_ann.median(), "median_IR": g.IR.median(),
                     "median_beta": g.beta_sum.median(), "median_te": g.te_ann.median(), "median_r2": g.r2_pick.median()})
    DESC = pd.DataFrame(desc); DESC.to_csv(f"{OUT}/DIAG_alpha_descriptive.csv", index=False)

    grp_rows = []
    for t, g in ev.groupby("t"):
        for nm, m in (("held", g.held), ("rank1-8", g["rank"] <= 8), ("rank9-16", (g["rank"] >= 9) & (g["rank"] <= 16)),
                      ("rank9-16_not_held", (g["rank"] >= 9) & (g["rank"] <= 16) & ~g.held), ("rank>16", g["rank"] > 16)):
            s = g[m.fillna(False)]
            if len(s): grp_rows.append({"t": t, "group": nm, "n": len(s), "mean_alpha": s.alpha_ann.mean(), "median_alpha": s.alpha_ann.median(),
                                        "mean_IR": s.IR.mean(), "median_bar": s.bar_ann.median(), "mean_alpha_fwd": s.alpha_fwd.mean() if "alpha_fwd" in s else np.nan})
    GRP = pd.DataFrame(grp_rows); GRP.to_csv(f"{OUT}/DIAG_alpha_groups.csv", index=False)

    # ความเสถียรของดัชนีคู่ (family ที่คัดได้ — ใช้ FundCode ตัวแทน; ถ้ารายนั้นเปลี่ยนตัวแทนใช้ family)
    pv = ev.pivot_table(index="family", columns="t", values="index", aggfunc="first")
    chg = []
    cols = list(pv.columns)
    for a, b in zip(cols[:-1], cols[1:]):
        m = pv[a].notna() & pv[b].notna()
        chg.append({"from": a, "to": b, "n_both": int(m.sum()), "frac_changed": float((pv.loc[m, a] != pv.loc[m, b]).mean())})
    CHG = pd.DataFrame(chg); CHG.to_csv(f"{OUT}/DIAG_alpha_index_stability.csv", index=False)
    # ดัชนีที่ถูกเลือกบ่อย + R² gap
    pick = ev.groupby("t")["index"].agg(lambda s: s.value_counts().head(3).to_dict())

    # H vs UH (ทั้งกองสดที่ประมาณได้, จับคู่ตาม key) + เทียบเฉพาะ table
    hu = []
    Fh = F[F.hedge.isin(["H", "UH"])].copy(); Fh["key"] = Fh.FundCode.map(hedge_key)
    for t, g in Fh.groupby("t"):
        h = g[g.hedge == "H"].groupby("key").alpha_ann.mean(); u = g[g.hedge == "UH"].groupby("key").alpha_ann.mean()
        j = pd.concat([h.rename("H"), u.rename("UH")], axis=1).dropna()
        hu.append({"t": t, "n_pairs": len(j), "mean_H_minus_UH": (j.H - j.UH).mean() if len(j) else np.nan,
                   "median_H_minus_UH": (j.H - j.UH).median() if len(j) else np.nan,
                   "median_alpha_H_all": g[g.hedge == "H"].alpha_ann.median(), "median_alpha_UH_all": g[g.hedge == "UH"].alpha_ann.median(),
                   "n_H": int((g.hedge == "H").sum()), "n_UH": int((g.hedge == "UH").sum())})
    HU = pd.DataFrame(hu); HU.to_csv(f"{OUT}/DIAG_alpha_hedge.csv", index=False)
    hed_tab = ev.groupby("hedge").agg(n=("alpha_ann", "size"), median_alpha=("alpha_ann", "median"), frac_neg=("alpha_ann", lambda s: (s < 0).mean()),
                                      median_gamma=("gamma_fx", "median"), median_beta=("beta_sum", "median"))

    ex = extras(ev, ev16, TAB, F)

    # ---------- ข้อ 5: price vs total return ----------
    div = dividend_test()

    # ---------- print ----------
    pd.set_option("display.width", 250); pd.set_option("display.max_columns", 40)
    print("\n=== DESCRIPTIVE (family ที่คัดได้ ณ t) ===\n", DESC.round(3).to_string())
    pooled = ev.alpha_ann
    print("pooled median alpha", pooled.median(), "frac<0", (pooled < 0).mean(), "n obs", len(ev))
    print("\n=== GROUPS ===\n", GRP.groupby("group")[["mean_alpha", "median_alpha", "mean_IR", "median_bar"]].agg(["mean"]).round(4).to_string())
    print("\n=== IC SUMMARY ===\n", SUM.round(3).to_string())
    print("\n=== INDEX STABILITY ===\n", CHG.round(3).to_string(), "\nmean frac changed", CHG.frac_changed.mean())
    print("\n=== HEDGE (ev) ===\n", hed_tab.round(3).to_string(), "\n", HU.round(3).to_string())
    print("\n=== DIVIDEND TEST ===\n", div.round(4).to_string())
    return dict(ex=ex, F=F, TAB=TAB, ev=ev, ev16=ev16, SUM=SUM, DESC=DESC, GRP=GRP, CHG=CHG, HU=HU, hed_tab=hed_tab, div=div, pick=pick, res=res)


def extras(ev, ev16, TAB, F):
    """รายละเอียดเสริม: IC รายไตรมาส · ชุดไม่ซ้อนทับ · group diff แบบ paired · Fama-MacBeth incremental · corr(alpha,SR12) · ดัชนีเปลี่ยนใน 4Q"""
    pd.set_option("display.width", 250); pd.set_option("display.max_columns", 40)
    qs = sorted(ev.t.unique()); out = {}
    # IC รายไตรมาส (alpha, SR12 -> alpha_fwd)
    rec = []
    for t in qs[:12]:
        g = ev[ev.t == t]; g16 = ev16[ev16.t == t]
        rec.append({"t": t.date(), "n": int(g.alpha_fwd.notna().sum()), "IC_alpha": spearman(g.alpha_ann.to_numpy(float), g.alpha_fwd.to_numpy(float)),
                    "IC_bar": spearman(g.bar_ann.to_numpy(float), g.alpha_fwd.to_numpy(float)), "IC_SR12": spearman(g.SR12.to_numpy(float), g.alpha_fwd.to_numpy(float)),
                    "IC16_alpha": spearman(g16.alpha_ann.to_numpy(float), g16.alpha_fwd.to_numpy(float)), "IC16_SR12": spearman(g16.SR12.to_numpy(float), g16.alpha_fwd.to_numpy(float)),
                    "corr_alpha_SR12": spearman(g.alpha_ann.to_numpy(float), g.SR12.to_numpy(float))})
    Q = pd.DataFrame(rec); out["Q"] = Q; Q.to_csv(f"{OUT}/DIAG_alpha_ic_perq_compact.csv", index=False)
    print("\n=== IC per quarter (-> alpha_fwd) ===\n", Q.round(3).to_string())
    for k in range(4):
        sub = Q.iloc[k::4]
        print(f"non-overlap set offset {k}: n={len(sub)} IC_alpha={sub.IC_alpha.mean():.3f} IC_SR12={sub.IC_SR12.mean():.3f} IC16_alpha={sub.IC16_alpha.mean():.3f}")
    print("mean corr(alpha,SR12) cross-sectional:", Q.corr_alpha_SR12.mean())
    # group differences (paired by quarter)
    e2 = ev.copy(); e2["g"] = np.where(e2.held, "held", np.where((e2["rank"] >= 9) & (e2["rank"] <= 16), "r9_16_nh", "other"))
    pv = e2.pivot_table(index="t", columns="g", values=["alpha_ann", "alpha_fwd", "ret_fwd", "bar_ann"], aggfunc="mean")
    for m in ("alpha_ann", "bar_ann", "alpha_fwd", "ret_fwd"):
        d = (pv[m]["held"] - pv[m]["r9_16_nh"]).dropna()
        print(f"held - rank9-16(not held) mean {m}: {d.mean():.4f} t={tstat(d.to_numpy()):.2f} n_q={len(d)} | held={pv[m]['held'].mean():.4f} r9-16={pv[m]['r9_16_nh'].mean():.4f} other={pv[m]['other'].mean():.4f}")
    # Fama-MacBeth: rank(alpha_fwd) ~ rank(alpha) + rank(SR12)
    fm = []
    for t in qs[:12]:
        g = ev[ev.t == t].dropna(subset=["alpha_fwd", "alpha_ann", "SR12"])
        if len(g) < 30: continue
        R = lambda c: (g[c].rank() - g[c].rank().mean()) / g[c].rank().std()
        A = np.column_stack([np.ones(len(g)), R("alpha_ann"), R("SR12")]); b, *_ = np.linalg.lstsq(A, R("alpha_fwd").to_numpy(), rcond=None)
        fm.append(b[1:])
    fm = np.array(fm); print("FM rank-regress alpha_fwd ~ alpha + SR12: coef alpha", fm[:, 0].mean(), "t", tstat(fm[:, 0]), "| SR12", fm[:, 1].mean(), "t", tstat(fm[:, 1]))
    out["fm"] = fm
    # ดัชนีคู่เปลี่ยนภายใน 4Q (กระทบ alpha อนาคตที่ใช้ดัชนีเดิม)
    pvx = ev.pivot_table(index="family", columns="t", values="index", aggfunc="first"); cols = list(pvx.columns); r4 = []
    for a, b_ in zip(cols[:-4], cols[4:]):
        m = pvx[a].notna() & pvx[b_].notna(); r4.append((pvx.loc[m, a] != pvx.loc[m, b_]).mean())
    print("index changed over 4Q (t vs t+4Q), mean frac:", np.mean(r4), "per start:", np.round(r4, 3))
    out["chg4"] = r4
    top = ev["index"].value_counts(normalize=True).head(8); print("index pick share (pooled):\n", top.round(3).to_string())
    print("r2_pick median", ev.r2_pick.median(), "r2_gap median", ev.r2_gap.median(), "share gap<0.02", (ev.r2_gap < 0.02).mean(), "n_wk median", ev.n_wk.median())
    print("gamma_fx quantiles", ev.gamma_fx.quantile([.1, .25, .5, .75, .9]).round(3).to_dict())
    print("alpha_fwd realized median", ev.alpha_fwd.median(), "frac neg", (ev.alpha_fwd.dropna() < 0).mean(), "| n alpha_fwd by q", ev.groupby("t").alpha_fwd.count().tolist())
    return out


def dividend_test() -> pd.DataFrame:
    """MSCI_ACWI (THB ระดับดัชนี) vs ACWI ETF รวมปันผล (USD, auto_adjust) x USDTHB — ผลตอบแทนรายปีปฏิทิน + USD-terms."""
    lv = msci_index.load_country_index()["MSCI_ACWI"]
    st = pd.read_csv("base_data/STYLE_FACTOR_ETF.csv", parse_dates=["Date"]).set_index("Date").sort_index()["ACWI"]
    fx = pd.read_csv("base_data/MACRO_FACTOR.csv", parse_dates=["Date"]).set_index("Date").sort_index()["USDTHB"]
    D = pd.concat([lv.rename("idx_thb"), st.rename("etf_usd"), fx.rename("fx")], axis=1).sort_index().ffill().dropna()
    D = D[D.index <= pd.Timestamp("2025-12-31")]
    D["etf_thb"] = D.etf_usd * D.fx; D["idx_usd"] = D.idx_thb / D.fx
    rows = []
    for y in range(2021, 2026):
        d0 = D.index[D.index <= pd.Timestamp(f"{y-1}-12-31")]; d1 = D.index[D.index <= pd.Timestamp(f"{y}-12-31")]
        a = D.loc[d0[-1]] if len(d0) and y > 2021 else D.iloc[0]; b = D.loc[d1[-1]]
        rr = lambda c: b[c] / a[c] - 1
        rows.append({"year": y, "start": (d0[-1] if len(d0) and y > 2021 else D.index[0]).date(), "idx_thb": rr("idx_thb"), "etf_tr_thb": rr("etf_thb"),
                     "diff_thb(etf-idx)": rr("etf_thb") - rr("idx_thb"), "idx_usd": rr("idx_usd"), "etf_tr_usd": rr("etf_usd"),
                     "diff_usd(etf-idx)": rr("etf_usd") - rr("idx_usd")})
    R = pd.DataFrame(rows)
    # รายวัน: correlation / tracking
    dr = np.log(D[["idx_thb", "etf_thb", "idx_usd", "etf_usd"]]).diff().dropna()
    R.attrs["daily_corr_thb"] = dr.idx_thb.corr(dr.etf_thb); R.attrs["daily_corr_usd"] = dr.idx_usd.corr(dr.etf_usd)
    R.attrs["cum_diff_ann_thb"] = (np.log(D.etf_thb.iloc[-1] / D.etf_thb.iloc[0]) - np.log(D.idx_thb.iloc[-1] / D.idx_thb.iloc[0])) / ((D.index[-1] - D.index[0]).days / 365.25)
    R.attrs["cum_diff_ann_usd"] = (np.log(D.etf_usd.iloc[-1] / D.etf_usd.iloc[0]) - np.log(D.idx_usd.iloc[-1] / D.idx_usd.iloc[0])) / ((D.index[-1] - D.index[0]).days / 365.25)
    R.attrs["range"] = (D.index[0].date(), D.index[-1].date()); R.attrs["n"] = len(D)
    print("mean annual diff (etf TR - idx) thb", R["diff_thb(etf-idx)"].mean(), "sd", R["diff_thb(etf-idx)"].std(), "usd", R["diff_usd(etf-idx)"].mean())
    R.to_csv(f"{OUT}/DIAG_alpha_dividend_test.csv", index=False)
    print("daily corr thb", R.attrs["daily_corr_thb"], "usd", R.attrs["daily_corr_usd"], "ann log diff thb", R.attrs["cum_diff_ann_thb"], "usd", R.attrs["cum_diff_ann_usd"], R.attrs["range"], R.attrs["n"])
    return R


if __name__ == "__main__":
    main()
