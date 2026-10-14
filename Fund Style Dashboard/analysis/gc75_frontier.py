"""gc75_frontier.py — efficient frontier ของกองที่ **M019-LC3-GCGOLD** ถือจริง ณ ไตรมาสหนึ่ง (หน้า 10 · pure functions).

M019 = หุ้น 3 กอง (อันดับ 1 + เติม max ρ_adj ต่ำสุด · ERC เพดาน 40%) × สัดส่วนหุ้นตาม GC75 + ขาตั้งรับ (กองทอง AUM ใหญ่สุด · ไม่มี → กองตลาดเงิน)
(เดิม 2026-10-07 = GC75 + กองตลาดเงิน / M015-FAUM · ผู้ใช้เปลี่ยนเป็น M019 2026-10-13 · ชื่อโมดูล/ค่าคงที่ GC75_FRONTIER_* คงไว้)
input = ไฟล์อ้างอิงจากทีม quant (data_access.load_gc75_frontier): กองที่ถือ + น้ำหนักจริง + SR12′ + weekly return 52 สัปดาห์ ≤ t
· kind: E = กองหุ้น · G = กองทอง · F = กองตลาดเงิน (G/F = ขาตั้งรับ ≤ 1 กองต่อไตรมาส)
- μ = ค่าเฉลี่ย weekly return × 52 (ข้อมูล ≤ t → ค่าที่ "เห็นได้ ณ t" ไม่ใช่ผลหลังซื้อ) · กองหุ้นใช้สัปดาห์ที่กองหุ้นทุกกองมีข้อมูล
  (ชุดเดียวกับ ERC) · ขาตั้งรับใช้สัปดาห์ที่ตัวเองมี (ดู weekly_mu_sigma)
- Σ × 52 แบบ block: กองหุ้น = Ledoit-Wolf เป้า constant correlation **เฉพาะกองหุ้น** (portfolio.shrink_constant_correlation)
  · แถว/คอลัมน์ของขาตั้งรับ = sample variance/covariance (หาร T เหมือน S ในสูตร shrink)
  เหตุผล (review 2026-10-07): sklearn LedoitWolf แบบที่ ERC ใช้ (เป้า μI) ดึง vol กองตลาดเงิน ~0.01% ขึ้นเป็น ~5% ·
  ใส่ขาตั้งรับในเป้า constant correlation ก็ดึง r̄ ลง (corr กับหุ้นต่ำ) → correlation ระหว่างกองหุ้นต่ำเกินจริง
  ตรวจ PSD ทุกครั้ง · กองหุ้นที่ variance ≈ 0 → ValueError (ไม่ปล่อยให้ตกไป fallback μI เงียบๆ)
- กริด = **เฉพาะส่วนหุ้น**: กองหุ้นแต่ละกอง 0–GC75_FRONTIER_MAX_W ของส่วนหุ้น ทีละ GC75_FRONTIER_STEP (portfolio.composition_grid)
  · ขาตั้งรับล็อกที่น้ำหนักจริงของไตรมาส (GC75) → ทุกพอร์ตมีสัดส่วนหุ้น/ขาตั้งรับเท่ากับที่โมเดลถือ
  · frontier = pareto_mask · MVP = จุดความเสี่ยงต่ำสุดของกริด
- max Sharpe = (μ − rf) ÷ σ สูงสุดบน frontier · rf = ดอกเบี้ยนโยบาย ธปท. ณ t
- ERC = กติกาของโมเดล: ERC ส่วนหุ้น (fund_weighting.risk_parity_weights + apply_cap เพดาน GC75_FRONTIER_MODEL_CAP = 40% ของ M019)
  × สัดส่วนหุ้นจริง ณ t + ขาตั้งรับตามน้ำหนักจริง · = น้ำหนักที่ M019 ถือจริงทุกไตรมาส (test)
"""
from __future__ import annotations

import numpy as np
import pandas as pd

import config
from analysis import fund_weighting as fw
from analysis import portfolio


def pick_quarters(quarters, n: int | None = None, seed: int | None = None) -> list[pd.Timestamp]:
    """สุ่มไตรมาสแบบคงที่ (seed ตายตัว → ได้ชุดเดิมทุกครั้ง) · เรียงตามเวลา."""
    n = config.GC75_FRONTIER_N_QUARTERS if n is None else n
    seed = config.GC75_FRONTIER_SEED if seed is None else seed
    qs = sorted(pd.Timestamp(q) for q in set(quarters))
    idx = np.random.default_rng(seed).choice(len(qs), size=n, replace=False)
    return sorted(qs[i] for i in idx)


KIND_LABEL = {"E": "หุ้น", "G": "ทอง", "F": "ตลาดเงิน"}


def fund_set(holdings_t: pd.DataFrame) -> pd.DataFrame:
    """กองหุ้นที่ถือ ณ t (เรียงตาม SR12′) + ขาตั้งรับ (ทอง/ตลาดเงิน ถ้าไตรมาสนั้นถือ) ท้าย."""
    eq = holdings_t[holdings_t["kind"] == "E"].sort_values(["sr12p", "FundCode"], ascending=[False, True])
    if len(eq) == 0:
        raise ValueError("ไม่มีกองหุ้นที่ถือ")
    return pd.concat([eq, holdings_t[holdings_t["kind"] != "E"]], ignore_index=True)


def weekly_mu_sigma(weekly_t: pd.DataFrame, equity: list[str], defensive: list[str]) -> tuple[pd.Series, pd.DataFrame, int]:
    """(μ รายปี, Σ รายปี, จำนวนสัปดาห์ของกองหุ้น) ของ equity + defensive (ลำดับนี้) จาก weekly return long [FundCode, week, ret] ของไตรมาสเดียว.

    block กองหุ้น ใช้สัปดาห์ที่กองหุ้นทุกกองมีข้อมูล (= ชุดเดียวกับที่ ERC ของโมเดลใช้) — สัปดาห์ที่ขาตั้งรับไม่มี NAV
    (กองทองบางไตรมาสขาด 3 สัปดาห์) จึงไม่ตัดข้อมูลกองหุ้นทิ้ง · ขาตั้งรับ: μ/variance จากสัปดาห์ที่ตัวเองมี ·
    covariance กับกองหุ้น = คู่ต่อคู่บนสัปดาห์ร่วม · ถ้าประกอบแล้วไม่ PSD → ใช้สัปดาห์ที่ทุกกองมีข้อมูลทั้ง matrix (แบบเดิม)
    """
    funds = list(equity) + list(defensive)
    wide = weekly_t.pivot(index="week", columns="FundCode", values="ret").reindex(columns=funds)
    eq = wide[list(equity)].dropna(how="any")
    if len(eq) < config.TF_COV_MIN_WEEKS:                    # เกณฑ์เดียวกับ ERC
        raise ValueError(f"สัปดาห์ที่กองหุ้นทุกกองมีข้อมูล {len(eq)} < {config.TF_COV_MIN_WEEKS}")
    flat = [f for f, sd in zip(equity, eq.to_numpy().std(axis=0)) if sd < 1e-12]
    if flat:                                                  # shrink_constant_correlation จะตกไป μI เงียบๆ
        raise ValueError(f"กองหุ้นที่ weekly return ไม่ขยับ: {flat}")

    def assemble(src: pd.DataFrame) -> tuple[pd.Series, np.ndarray, int]:
        """src = wide (กองหุ้นสัปดาห์ร่วม + ขาตั้งรับคู่ต่อคู่) หรือ wide ที่ตัดสัปดาห์ NaN ทุกกองแล้ว (fallback)."""
        n_e = len(equity)
        eq_rows = src[list(equity)].dropna(how="any")
        x = eq_rows.to_numpy()
        cov = np.zeros((len(funds), len(funds)))
        cov[:n_e, :n_e] = (portfolio.shrink_constant_correlation(x)[0] if n_e >= 2
                           else np.cov(x, rowvar=False, ddof=0).reshape(1, 1))   # หาร T เหมือน S ใน shrink
        mu = eq_rows.mean().reindex(funds)
        for j, d in enumerate(defensive, start=n_e):
            col = src[d]
            if col.notna().sum() < config.TF_COV_MIN_WEEKS:
                raise ValueError(f"{d}: สัปดาห์ที่มีข้อมูล {int(col.notna().sum())} < {config.TF_COV_MIN_WEEKS}")
            mu[d] = col.mean()
            cov[j, j] = col.var(ddof=0)
            for i, other in enumerate(funds[:j]):
                pair = src[[other, d]].dropna()
                cov[i, j] = cov[j, i] = np.cov(pair.to_numpy(), rowvar=False, ddof=0)[0, 1]
        return mu, cov, len(eq_rows)

    mu, cov, n_weeks = assemble(wide)
    if np.linalg.eigvalsh(cov).min() < -1e-14:               # pairwise ไม่การันตี PSD → สัปดาห์ร่วมทั้ง matrix
        common = wide.dropna(how="any")
        if len(common) < config.TF_COV_MIN_WEEKS:
            raise ValueError(f"สัปดาห์ที่ทุกกองมีข้อมูล {len(common)} < {config.TF_COV_MIN_WEEKS}")
        mu, cov, n_weeks = assemble(common)
        if np.linalg.eigvalsh(cov).min() < -1e-14:
            raise ValueError("covariance ไม่เป็น PSD หลังประกอบ block")
    return mu * 52.0, pd.DataFrame(cov * 52.0, index=funds, columns=funds), n_weeks


def model_erc(funds_df: pd.DataFrame, weekly_t: pd.DataFrame) -> pd.Series:
    """น้ำหนักตามกติกาโมเดลของกองชุดนี้ (รวม 100%): ERC ส่วนหุ้น × สัดส่วนหุ้นจริง ณ t + ขาตั้งรับตามน้ำหนักจริง.

    ERC = fund_weighting.risk_parity_weights (sklearn Ledoit-Wolf weekly 52 สัปดาห์ · inverse-vol ถ้าสัปดาห์ร่วม < 30)
    + apply_cap เพดาน GC75_FRONTIER_MODEL_CAP (40% ของ M019 · แยกจากเพดานกริด) · สัดส่วนหุ้น = 1 − น้ำหนักขาตั้งรับ (GC75 100/75/50/25%)
    """
    eq = list(funds_df.loc[funds_df["kind"] == "E", "FundCode"])
    dfn = funds_df[funds_df["kind"] != "E"].set_index("FundCode")["weight"]
    wide = weekly_t.pivot(index="week", columns="FundCode", values="ret")
    vol = {f: float(wide[f].std(ddof=1) * np.sqrt(52.0)) for f in eq}
    w_eq, _ = fw.risk_parity_weights(eq, {f: wide[f] for f in eq}, vol)
    w_eq = fw.apply_cap(w_eq, config.GC75_FRONTIER_MODEL_CAP)
    return pd.concat([w_eq * (1.0 - dfn.sum()), dfn])[list(funds_df["FundCode"])]


def frontier_case(holdings_t: pd.DataFrame, weekly_t: pd.DataFrame, step: float | None = None,
                  max_w: float | None = None) -> dict:
    """frontier ของกองชุดหนึ่ง ณ ไตรมาสหนึ่ง -> dict ของกริด / frontier / จุดอ้างอิง (MVP, max Sharpe, ERC) + น้ำหนักทั้งพอร์ต."""
    step = config.GC75_FRONTIER_STEP if step is None else step
    max_w = config.GC75_FRONTIER_MAX_W if max_w is None else max_w
    funds_df = fund_set(holdings_t)
    funds = list(funds_df["FundCode"])
    is_eq = (funds_df["kind"] == "E").to_numpy()
    mu, sigma, n_weeks = weekly_mu_sigma(weekly_t, [f for f, e in zip(funds, is_eq) if e],
                                         [f for f, e in zip(funds, is_eq) if not e])
    rf = float(holdings_t["rf"].iloc[0])

    w_def = funds_df.loc[~is_eq, "weight"].to_numpy()                       # ขาตั้งรับล็อกตามน้ำหนักจริง
    eq_share = 1.0 - float(w_def.sum())
    sleeve = portfolio.composition_grid(int(is_eq.sum()), step, max_w)
    if len(sleeve) == 0:
        raise ValueError(f"เพดาน {max_w:.0%} × {int(is_eq.sum())} กอง ไม่ถึง 100% ของส่วนหุ้น")
    grid = np.column_stack([sleeve * eq_share, np.tile(w_def, (len(sleeve), 1))])
    points = portfolio.portfolio_points(grid, mu, sigma)
    mask = portfolio.pareto_mask(points["risk"].to_numpy(), points["ret"].to_numpy())
    order = points[mask]["risk"].to_numpy().argsort()
    frontier = points[mask].iloc[order].reset_index(drop=True)
    front_w = grid[mask][order]
    i_ms = portfolio.max_sharpe_index(frontier, risk_free=rf)

    erc_w = model_erc(funds_df, weekly_t)
    erc = portfolio.portfolio_points(erc_w.to_numpy()[None, :], mu, sigma).iloc[0]

    weights = pd.DataFrame({"MVP": front_w[0], "max Sharpe": front_w[i_ms], "ERC (กติกาโมเดล)": erc_w.to_numpy()},
                           index=funds)
    summary = pd.DataFrame({name: {"risk": float(np.sqrt(w @ sigma.to_numpy() @ w)), "ret": float(w @ mu.to_numpy())}
                            for name, w in weights.items()}).T
    summary["sharpe"] = (summary["ret"] - rf) / summary["risk"]
    eq_w = weights[is_eq]                                                   # น้ำหนักกองหุ้นในพอร์ตรวม
    summary["n_equity"] = (eq_w > 1e-9).sum().astype(int)                   # จำนวนกองหุ้นที่ถือจริง (น้ำหนัก > 0)
    summary["max_sleeve_w"] = eq_w.max() / eq_share if eq_share > 0 else np.nan   # น้ำหนักสูงสุด (% ของส่วนหุ้น)
    return {"funds": funds_df, "mu": mu, "sigma": sigma, "n_weeks": n_weeks, "rf": rf,
            "points": points, "frontier": frontier, "weights": weights, "summary": summary,
            "mvp": frontier.iloc[0], "max_sharpe": frontier.iloc[i_ms], "erc": erc,
            "singles": pd.DataFrame({"risk": np.sqrt(np.diag(sigma)), "ret": mu.to_numpy()}, index=funds)}
