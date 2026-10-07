"""weighting.py — จัดอันดับ family (C4), คัดแบบ hysteresis + dedupe (C5, M005), เพดานน้ำหนัก (C6),
Σ + ERC/HRP (C8), vol targeting (C9), trend filter (C10). ตาม .claude/quant_team/specs/M002-M005_plan.md"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import linkage, leaves_list
from scipy.spatial.distance import squareform
from scipy.optimize import minimize
from sklearn.covariance import LedoitWolf


# ---------------- C4: family representatives + rank ----------------

def family_representatives(df_it: pd.DataFrame, signal_col: str, held_funds: set[str]) -> dict[str, dict]:
    """ตัวแทน family = class สัญญาณสูงสุด เว้นแต่ family นั้นมี class ที่ถืออยู่ -> ใช้ class ที่ถือ (ไม่สลับ class)."""
    reps = {}
    for fam, g in df_it.groupby("family"):
        held_rows = g[g["FundCode"].isin(held_funds)]
        if len(held_rows):
            row = held_rows.iloc[0]
        else:
            gs = g.sort_values([signal_col, "vol52", "FundCode"], ascending=[False, True, True])
            row = gs.iloc[0]
        reps[fam] = {"FundCode": row["FundCode"], "signal": row[signal_col], "vol52": row["vol52"]}
    return reps


def rank_families(reps: dict[str, dict]) -> dict[str, int]:
    items = sorted(reps.items(), key=lambda kv: (-kv[1]["signal"] if kv[1]["signal"] == kv[1]["signal"] else np.inf,
                                                   kv[1]["vol52"] if kv[1]["vol52"] == kv[1]["vol52"] else np.inf,
                                                   kv[1]["FundCode"]))
    return {fam: i + 1 for i, (fam, _) in enumerate(items)}


# ---------------- C5: hysteresis select (+ optional correlation dedupe, M005) ----------------

def hysteresis_select(reps: dict[str, dict], ranks: dict[str, int], held_map: dict[str, str],
                       n_target: int, k_drop: int, dedupe_corr: dict[str, pd.Series] | None = None,
                       rho_max: float = 0.85) -> dict:
    """held_map: family -> FundCode ที่ถืออยู่ก่อนหน้า (เฉพาะ family ที่ยังไม่ถูกขาย)
    dedupe_corr: FundCode -> weekly return Series (52w <= t) ถ้าไม่ None จะกรองด้วย correlation (M005)
    คืน dict: S (family->FundCode), n_kept, n_added, n_removed, n_skipped_dedupe, max_rank_reached, fallback
    """
    S: dict[str, str] = {}
    n_kept = 0
    for fam, fc in held_map.items():
        if fam in reps and ranks.get(fam, 10**9) <= k_drop and reps[fam]["FundCode"] == fc:
            S[fam] = fc
            n_kept += 1

    order = sorted(reps.keys(), key=lambda f: ranks.get(f, 10**9))
    n_skipped_dedupe = 0
    max_rank_reached = 0
    for fam in order:
        if len(S) >= n_target:
            break
        if fam in S:
            continue
        cand_fc = reps[fam]["FundCode"]
        max_rank_reached = max(max_rank_reached, ranks.get(fam, 0))
        if dedupe_corr is not None and len(S) > 0:
            cand_r = dedupe_corr.get(cand_fc)
            ok = True
            if cand_r is not None:
                for held_fc in S.values():
                    held_r = dedupe_corr.get(held_fc)
                    if held_r is None:
                        continue
                    a, b = cand_r.align(held_r, join="inner")
                    m = a.notna() & b.notna()
                    if m.sum() < 30:
                        continue  # ไม่ถึง 30 สัปดาห์ร่วม -> ถือว่าผ่าน
                    rho = float(np.corrcoef(a[m], b[m])[0, 1])
                    if rho > rho_max:
                        ok = False
                        break
            if not ok:
                n_skipped_dedupe += 1
                continue
        S[fam] = cand_fc

    n_added = len(S) - n_kept
    fallback = None
    if len(S) < 4:
        fallback = "b0"
    return {"S": S, "n_kept": n_kept, "n_added": n_added, "n_target_short": max(0, n_target - len(S)),
            "n_skipped_dedupe": n_skipped_dedupe, "max_rank_reached": max_rank_reached, "fallback": fallback}


# ---------------- C6: cap ----------------

def apply_cap(w: pd.Series, cap: float = 0.25, max_iter: int = 50, tol: float = 1e-12) -> pd.Series:
    w = w.copy().astype(float)
    total = w.sum()
    if total <= 0:
        return w
    w = w / total
    for _ in range(max_iter):
        over = w[w > cap + tol]
        if len(over) == 0:
            break
        excess = float((over - cap).sum())
        w[over.index] = cap
        under_mask = w < cap - tol
        under_sum = float(w[under_mask].sum())
        if under_sum <= 0:
            # ทุกตัวติดเพดานพอดี (N เล็ก, cap*N ~ 1) กระจายเท่ากันเท่าที่ทำได้
            w[under_mask] = w[under_mask] + excess / max(under_mask.sum(), 1)
            break
        w[under_mask] = w[under_mask] + excess * (w[under_mask] / under_sum)
    return w * total


# ---------------- C8: Σ + ERC / HRP ----------------

def build_weekly_matrix(funds: list[str], weekly_returns: dict[str, pd.Series]) -> pd.DataFrame:
    cols = {fc: weekly_returns.get(fc, pd.Series(dtype=float)) for fc in funds}
    return pd.DataFrame(cols)


def covariance_or_fallback(funds: list[str], weekly_returns: dict[str, pd.Series],
                            vol52: dict[str, float]) -> tuple[np.ndarray | None, str]:
    mat = build_weekly_matrix(funds, weekly_returns).dropna(how="any")
    if len(mat) >= 30 and mat.shape[1] == len(funds):
        lw = LedoitWolf().fit(mat.to_numpy())
        Sigma = lw.covariance_ * 52.0
        return Sigma, "ledoit_wolf"
    return None, "ivol"


def erc_weights(Sigma: np.ndarray, funds: list[str]) -> pd.Series:
    n = len(funds)
    vol = np.sqrt(np.clip(np.diag(Sigma), 1e-12, None))
    x0 = 1.0 / vol

    def obj(y):
        y = np.clip(y, 1e-10, None)
        return 0.5 * y @ Sigma @ y - np.sum(np.log(y)) / n

    def grad(y):
        y = np.clip(y, 1e-10, None)
        return Sigma @ y - (1.0 / n) / y

    res = minimize(obj, x0, jac=grad, method="L-BFGS-B", bounds=[(1e-10, None)] * n)
    y = np.clip(res.x, 1e-10, None)
    w = y / y.sum()
    return pd.Series(w, index=funds)


def hrp_weights(Sigma: np.ndarray, funds: list[str]) -> pd.Series:
    n = len(funds)
    if n == 1:
        return pd.Series([1.0], index=funds)
    d = np.sqrt(np.diag(Sigma))
    corr = Sigma / np.outer(d, d)
    corr = np.clip(corr, -1.0, 1.0)
    dist = np.sqrt(np.clip(0.5 * (1.0 - corr), 0.0, None))
    np.fill_diagonal(dist, 0.0)
    dtilde = squareform((np.sqrt(((dist[:, None, :] - dist[None, :, :]) ** 2).sum(axis=2))), checks=False)
    link = linkage(dtilde, method="single")
    order = leaves_list(link).tolist()

    def cluster_var(idx):
        sub = Sigma[np.ix_(idx, idx)]
        ivp = 1.0 / np.clip(np.diag(sub), 1e-12, None)
        ivp = ivp / ivp.sum()
        return float(ivp @ sub @ ivp)

    weights = pd.Series(1.0, index=order)

    def recurse(idx):
        if len(idx) <= 1:
            return
        mid = len(idx) // 2
        left, right = idx[:mid], idx[mid:]
        var_l, var_r = cluster_var(left), cluster_var(right)
        alpha = 1.0 - var_l / (var_l + var_r) if (var_l + var_r) > 0 else 0.5
        weights[left] = weights[left] * alpha
        weights[right] = weights[right] * (1.0 - alpha)
        recurse(left)
        recurse(right)

    recurse(order)
    w = pd.Series(weights.to_numpy(), index=[funds[i] for i in order])
    w = w.reindex(funds)
    return w / w.sum()


def risk_parity_weights(funds: list[str], weekly_returns: dict[str, pd.Series], vol52: dict[str, float],
                         method: str = "erc") -> tuple[pd.Series, str]:
    if len(funds) == 1:
        return pd.Series([1.0], index=funds), "single"
    Sigma, src = covariance_or_fallback(funds, weekly_returns, vol52)
    if Sigma is None:
        inv = np.array([1.0 / max(vol52.get(f, np.nan), 1e-6) if vol52.get(f, np.nan) == vol52.get(f, np.nan)
                         else 0.0 for f in funds])
        if inv.sum() <= 0:
            inv = np.ones(len(funds))
        w = pd.Series(inv / inv.sum(), index=funds)
        return w, "ivol"
    if method == "erc":
        return erc_weights(Sigma, funds), src
    return hrp_weights(Sigma, funds), src


# ---------------- C9: vol targeting ----------------

def vol_target_cash(weights: pd.Series, weekly_returns: dict[str, pd.Series], sigma_star: float = 0.10) -> tuple[float, int]:
    funds = list(weights.index)
    mat = build_weekly_matrix(funds, weekly_returns)
    for n_weeks in (13, 26):
        sub = mat.tail(n_weeks).dropna(how="any")
        if len(sub) >= 10:
            port_r = sub.to_numpy() @ weights.reindex(funds).to_numpy()
            sigma_hat = float(np.std(port_r, ddof=1)) * np.sqrt(52.0)
            if sigma_hat <= 0:
                return 0.0, n_weeks
            c = float(np.clip(1.0 - sigma_star / sigma_hat, 0.0, 0.25))
            return c, n_weeks
    return 0.0, 0


# ---------------- C10: trend filter ----------------

def trend_filter_cash(acwi_level: pd.Series, t: pd.Timestamp, cash_amount: float = 0.25) -> float:
    s = acwi_level.loc[:t]
    if len(s) < 200:
        return 0.0
    sma200 = float(s.iloc[-200:].mean())
    a_t = float(s.iloc[-1])
    return cash_amount if a_t < sma200 else 0.0
