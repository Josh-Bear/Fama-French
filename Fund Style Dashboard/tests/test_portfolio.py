"""test_portfolio.py — คณิตของ efficient frontier หน้า 8 ส่วนที่ 3 (น้ำหนักตลาด, Σ, กริด, pareto)."""

import numpy as np
import pandas as pd
import pytest

import config
from analysis import portfolio


def test_market_weights_caps_then_spreads_the_excess():
    w = portfolio.market_weights(pd.Series({"A": 900.0, "B": 50.0, "C": 50.0}))
    assert w["A"] == pytest.approx(0.5) and w["B"] == pytest.approx(0.25) and w["C"] == pytest.approx(0.25)
    assert w.sum() == pytest.approx(1.0)


def test_market_weights_repeats_until_every_weight_is_under_cap():
    """เกลี่ยรอบเดียวไม่พอ — กองที่ 2 ทะลุ cap จากส่วนเกินที่เพิ่งได้มา ต้องวนซ้ำ (ใช้ cap 30% ให้เห็นเคสชัด)."""
    w = portfolio.market_weights(pd.Series({"A": 60.0, "B": 30.0, "C": 5.0, "D": 5.0}), cap=0.30)
    assert (w <= 0.30 + 1e-9).all() and w.sum() == pytest.approx(1.0)
    assert w["A"] == pytest.approx(0.30) and w["B"] == pytest.approx(0.30)
    assert w["C"] == pytest.approx(0.20) and w["D"] == pytest.approx(0.20)


def test_market_weights_falls_back_to_equal_when_no_aum():
    w = portfolio.market_weights(pd.Series({"A": 0.0, "B": 0.0}))
    assert w.tolist() == pytest.approx([0.5, 0.5])


def test_weight_grid_matches_hand_count_and_respects_bounds():
    g = portfolio.weight_grid(5, max_w=0.30)          # 5%-30% ทีละ 1% รวม 100% (ระบุ max_w เพราะค่าเริ่มต้นเปลี่ยนเป็น 40% แล้ว)
    assert len(g) == 213_876                          # นับด้วย inclusion-exclusion: C(79,4)−5·C(53,4)+10·C(27,4)
    assert np.allclose(g.sum(axis=1), 1.0)
    assert g.min() >= config.PORTFOLIO_MIN_W - 1e-9 and g.max() <= 0.30 + 1e-9


def test_weight_grid_is_empty_when_bounds_cannot_reach_100pct():
    assert len(portfolio.weight_grid(3, max_w=0.30)) == 0   # 30% × 3 = 90% < 100%
    assert len(portfolio.weight_grid(25)) == 0        # 5% × 25 = 125% > 100%
    assert len(portfolio.weight_grid(4, max_w=0.30)) == 1_771
    assert len(portfolio.weight_grid(2)) == 0         # ค่าเริ่มต้น 40% × 2 = 80% < 100% (จึงต้อง >= PORTFOLIO_MIN_FUNDS = 3)


def test_default_bounds_allow_the_minimum_fund_count():
    g = portfolio.weight_grid(config.PORTFOLIO_MIN_FUNDS)         # 3 กอง × เพดาน 40% = 120% ต้องมีพอร์ตที่เป็นไปได้
    assert len(g) == 231 and np.allclose(g.sum(axis=1), 1.0)
    assert len(portfolio.weight_grid(config.PORTFOLIO_MIN_FUNDS - 1)) == 0


def test_weight_grid_rejects_a_step_that_does_not_divide_100pct():
    for step in (0.03, 0.07, 0.15):                   # เดิมปัดเป็นหน่วย 3.03% / 7.14% / 14.29% โดยไม่บอก
        with pytest.raises(ValueError, match="หาร 100%"):
            portfolio.weight_grid(4, step=step)


def test_weight_grid_rounds_off_step_bounds_inward():
    g = portfolio.weight_grid(4, min_w=0.05, max_w=0.41, step=0.02)   # min 5% -> 6% · max 41% -> 40% (ไม่หลุดเงื่อนไข)
    assert len(g) and g.min() >= 0.06 - 1e-9 and g.max() <= 0.40 + 1e-9
    assert np.allclose(np.round(g * 100) % 2, 0)                      # ทุกน้ำหนักเป็นพหุคูณของ step


def test_weight_grid_guards_against_explosive_settings():
    with pytest.raises(ValueError, match="กริดใหญ่เกินไป"):
        portfolio.weight_grid(6, min_w=0.0, max_w=1.0, step=0.001)


def _model():
    b = pd.DataFrame({"f1": [1.0, 0.5], "f2": [0.0, 0.5]}, index=["A", "B"])
    f = pd.DataFrame(np.diag([0.04, 0.09]), index=["f1", "f2"], columns=["f1", "f2"])
    d = pd.Series({"A": 0.01, "B": 0.02})
    return b, f, d


def test_fund_covariance_is_bfbt_plus_d():
    b, f, d = _model()
    sigma = portfolio.fund_covariance(b, f, d)
    assert sigma.at["A", "A"] == pytest.approx(1.0 * 0.04 + 0.01)
    assert sigma.at["B", "B"] == pytest.approx(0.25 * 0.04 + 0.25 * 0.09 + 0.02)
    assert sigma.at["A", "B"] == pytest.approx(0.5 * 0.04) == sigma.at["B", "A"]


def test_implied_returns_is_gamma_sigma_w():
    b, f, d = _model()
    sigma = portfolio.fund_covariance(b, f, d)
    w = pd.Series({"A": 0.6, "B": 0.4})
    mu = portfolio.implied_returns(sigma, w, gamma=2.5)
    assert np.allclose(mu.to_numpy(), 2.5 * sigma.to_numpy() @ w.to_numpy())


def test_portfolio_points_and_pareto_keep_only_undominated():
    b, f, d = _model()
    sigma = portfolio.fund_covariance(b, f, d)
    mu = pd.Series({"A": 0.05, "B": 0.10})
    w = np.array([[1.0, 0.0], [0.0, 1.0], [0.5, 0.5]])
    pts = portfolio.portfolio_points(w, mu, sigma)
    assert pts.loc[0, "risk"] == pytest.approx(np.sqrt(sigma.at["A", "A"]))
    assert pts.loc[2, "ret"] == pytest.approx(0.075)
    keep = portfolio.pareto_mask(pts["risk"].to_numpy(), pts["ret"].to_numpy())
    # พอร์ตผสม 50/50 เสี่ยงต่ำกว่า **และ** return สูงกว่าการถือ A เดี่ยว -> A ตกจากเส้น (นี่คือประโยชน์ของ diversification)
    assert keep[2] and keep[1] and not keep[0]
    assert portfolio.pareto_mask(np.array([0.1, 0.2]), np.array([0.05, 0.04])).tolist() == [True, False]


def test_risk_contribution_sums_to_one():
    b, f, d = _model()
    sigma = portfolio.fund_covariance(b, f, d)
    rc = portfolio.risk_contribution(pd.Series({"A": 0.7, "B": 0.3}), sigma)
    assert rc.sum() == pytest.approx(1.0) and (rc > 0).all()


def _brute_force_cc_delta(x):
    """δ ของ Ledoit-Wolf constant correlation แบบวนลูปตามสูตรในเปเปอร์ตรงๆ — ใช้ตรวจเวอร์ชัน vectorized."""
    x = x - x.mean(0)
    t, n = x.shape
    s = x.T @ x / t
    sd = np.sqrt(np.diag(s))
    r = s / np.outer(sd, sd)
    rbar = (r.sum() - n) / (n * (n - 1))
    f = rbar * np.outer(sd, sd)
    np.fill_diagonal(f, np.diag(s))
    pi = sum(((x[:, i] * x[:, j] - s[i, j]) ** 2).mean() for i in range(n) for j in range(n))
    rho = sum(((x[:, i] ** 2 - s[i, i]) ** 2).mean() for i in range(n))
    for i in range(n):
        for j in range(n):
            if i != j:
                th_ii = ((x[:, i] ** 2 - s[i, i]) * (x[:, i] * x[:, j] - s[i, j])).mean()
                th_jj = ((x[:, j] ** 2 - s[j, j]) * (x[:, i] * x[:, j] - s[i, j])).mean()
                rho += rbar / 2 * (np.sqrt(s[j, j] / s[i, i]) * th_ii + np.sqrt(s[i, i] / s[j, j]) * th_jj)
    return max(0.0, min(1.0, (pi - rho) / ((f - s) ** 2).sum() / t))


def test_constant_correlation_shrinkage_matches_the_paper_formula():
    rng = np.random.default_rng(1)
    x = rng.normal(size=(200, 5)) @ rng.normal(size=(5, 5))
    cov, delta = portfolio.shrink_constant_correlation(x)
    assert delta == pytest.approx(_brute_force_cc_delta(x), rel=1e-9) and 0 < delta < 1
    s = np.cov(x, rowvar=False, bias=True)
    assert np.allclose(np.diag(cov), np.diag(s))                       # variance ไม่ถูก shrink
    assert not np.allclose(cov, s)                                     # off-diagonal ถูก shrink จริง


def test_factor_covariance_is_annualized_and_tames_a_near_singular_matrix():
    """ดัชนีรวม = ค่าเฉลี่ยของ 2 ตลาด + noise นิดเดียว (แบบ ACWI ⊃ USA) -> cond ต้องลดลงหลายเท่า (mutant ไม่ shrink ตก)."""
    rng = np.random.default_rng(0)
    a, b = rng.normal(0, 0.01, (2, 500))
    r = pd.DataFrame({"a": a, "b": b, "agg": (a + b) / 2 + rng.normal(0, 1e-4, 500)})
    cov = portfolio.factor_covariance(r)
    raw = np.cov(r.to_numpy(), rowvar=False, bias=True) * config.TRADING_DAYS
    assert np.allclose(np.diag(cov), np.diag(raw))                     # annualize ×252 ถูก
    assert np.linalg.cond(cov.to_numpy()) < np.linalg.cond(raw) / 10


def test_max_sharpe_index_picks_the_best_return_per_risk():
    pts = pd.DataFrame({"risk": [0.10, 0.20, 0.05], "ret": [0.05, 0.12, 0.01]})
    assert portfolio.max_sharpe_index(pts) == 1          # 0.60 > 0.50 > 0.20
    flip = pd.DataFrame({"risk": [0.10, 0.20], "ret": [0.06, 0.11]})
    assert portfolio.max_sharpe_index(flip) == 0                   # rf=0: 0.60 vs 0.55
    assert portfolio.max_sharpe_index(flip, risk_free=0.02) == 1   # หัก rf แล้วพลิก: 0.40 vs 0.45
    assert portfolio.max_sharpe_index(pd.DataFrame({"risk": [0.0, 0.1], "ret": [0.5, 0.05]})) == 1  # risk 0 ไม่ถูกเลือก


def test_systematic_covariance_drops_only_the_idiosyncratic_diagonal():
    b, f, d = _model()
    sigma = portfolio.fund_covariance(b, f, d)
    sys = portfolio.systematic_covariance(sigma, d)
    assert np.allclose(sys.to_numpy(), b.to_numpy() @ f.to_numpy() @ b.to_numpy().T)   # = B F Bᵀ
    assert sys.at["A", "B"] == pytest.approx(sigma.at["A", "B"])                        # off-diagonal ไม่เปลี่ยน


def test_implied_return_no_longer_rewards_idiosyncratic_variance():
    """กอง A/B factor เหมือนกันเป๊ะ ต่างกันแค่ D — Π จาก Σ_sys ต้องเท่ากัน (Σ เต็มจะให้กอง D สูงได้ Π สูงกว่า)."""
    b = pd.DataFrame({"f1": [1.0, 1.0]}, index=["A", "B"])
    f = pd.DataFrame([[0.04]], index=["f1"], columns=["f1"])
    d = pd.Series({"A": 0.01, "B": 0.20})
    sigma = portfolio.fund_covariance(b, f, d)
    w = pd.Series({"A": 0.5, "B": 0.5})
    full = portfolio.implied_returns(sigma, w, gamma=2.5)
    sys = portfolio.implied_returns(portfolio.systematic_covariance(sigma, d), w, gamma=2.5)
    assert full["B"] > full["A"]                                  # ของเดิม: vol เฉพาะตัวสูง -> Π สูง (ปัญหา)
    assert sys["A"] == pytest.approx(sys["B"])                    # แก้แล้ว


def test_reference_weights_equal_ignores_aum_and_aum_mode_uses_it():
    aum = pd.Series({"A": 900.0, "B": 50.0, "C": 50.0})
    assert portfolio.reference_weights(aum, mode="equal").tolist() == pytest.approx([1 / 3] * 3)
    assert portfolio.reference_weights(aum, mode="aum")["A"] == pytest.approx(0.5)   # cap 50%
    with pytest.raises(ValueError):
        portfolio.reference_weights(aum, mode="nope")


def test_constant_correlation_shrinkage_stays_finite_for_a_flat_factor_or_tiny_sample():
    rng = np.random.default_rng(2)
    x = rng.normal(size=(60, 3))
    x[:, 2] = 0.0                                                     # factor ที่ค่าไม่ขยับ
    cov, _ = portfolio.shrink_constant_correlation(x)
    assert np.isfinite(cov).all()
    assert np.isfinite(portfolio.shrink_constant_correlation(rng.normal(size=(2, 3)))[0]).all()
