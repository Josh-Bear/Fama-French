"""test_screening.py — คณิตหน้า 8: percentile rescale, โซน, ตาราง, คะแนนกอง, greedy selection."""

import numpy as np
import pandas as pd
import pytest

import config
from analysis import screening

RET = config.SCORE_RETURN_COL
VOL = config.SCORE_VOL_COL


def _snapshot():
    """4 country + 3 sector — C1 ดีสุด (return สูงสุด vol ต่ำสุด), C4 แย่สุด · realized vol = vol_forecast (อันดับตรงกันทั้งสองสูตร)."""
    rows = [
        {"scope": "country", "index": "C1", RET: 0.40, "vol_forecast": 0.10},
        {"scope": "country", "index": "C2", RET: 0.30, "vol_forecast": 0.20},
        {"scope": "country", "index": "C3", RET: 0.20, "vol_forecast": 0.30},
        {"scope": "country", "index": "C4", RET: 0.10, "vol_forecast": 0.40},
        {"scope": "sector", "index": "S1", RET: 0.50, "vol_forecast": 0.10},
        {"scope": "sector", "index": "S2", RET: 0.30, "vol_forecast": 0.20},
        {"scope": "sector", "index": "S3", RET: 0.10, "vol_forecast": 0.30},
    ]
    snap = pd.DataFrame(rows)
    snap[VOL] = snap["vol_forecast"]
    return snap


@pytest.fixture
def old_zone_method(monkeypatch):
    """สูตรเดิม (อันดับ return × อันดับ GARCH) — เก็บไว้ A/B 1 รอบตาม §12.14."""
    monkeypatch.setattr(config, "SCORE_ZONE_METHOD", "rank_x_rank_garch")


def test_pct_rescaled_stays_inside_band_and_keeps_order():
    s = pd.Series([1.0, 2.0, 3.0, 4.0], index=list("abcd"))
    p = screening.pct_rescaled(s)
    assert p.min() >= config.SCORE_PCT_LO and p.max() <= config.SCORE_PCT_HI
    assert p.is_monotonic_increasing and p.iloc[-1] == pytest.approx(config.SCORE_PCT_HI)
    inv = screening.pct_rescaled(s, invert=True)            # กลับด้านแล้วต้องสมมาตรกัน: ตัวน้อยสุดได้เต็ม
    assert inv.is_monotonic_decreasing and inv.iloc[0] == pytest.approx(config.SCORE_PCT_HI)
    assert inv.min() == pytest.approx(p.min()) and inv.max() == pytest.approx(p.max())


def test_zone_score_wants_high_return_and_low_vol(old_zone_method):
    z = screening.zone_scores(_snapshot(), "country")
    assert list(z.index) == ["C1", "C2", "C3", "C4"]          # เรียงคะแนนมาก->น้อย
    assert z.loc["C1", "score"] == pytest.approx(config.SCORE_PCT_HI ** 2)
    # ดีด้านเดียวไม่พอ: return สูงสุดแต่ vol สูงสุด ต้องแพ้ตัวที่ดีปานกลางทั้งคู่
    swapped = _snapshot()
    swapped.loc[0, "vol_forecast"] = 0.99
    z2 = screening.zone_scores(swapped, "country")
    assert z2.loc["C2", "score"] > z2.loc["C1", "score"]


def test_zone_score_reranks_within_selected_universe(old_zone_method):
    """§12.10 policy — จำกัด universe แล้ว percentile ต้องคิดใหม่ในกลุ่มที่เหลือ ไม่ใช่กรองจากของเดิม."""
    full = screening.zone_scores(_snapshot(), "country")
    sub = screening.zone_scores(_snapshot(), "country", ["C2", "C3", "C4"])
    assert sub.loc["C2", "return_pct"] > full.loc["C2", "return_pct"]
    assert sub.loc["C2", "return_pct"] == pytest.approx(config.SCORE_PCT_HI)
    with pytest.raises(KeyError):
        screening.zone_scores(_snapshot(), "country", ["C1", "NOPE"])


def test_score_matrix_is_outer_product_scaled():
    snap = _snapshot()
    c, s = screening.zone_scores(snap, "country"), screening.zone_scores(snap, "sector")
    m = screening.score_matrix(c, s)
    assert m.shape == (4, 3)
    assert m.at["C1", "S1"] == pytest.approx(c.at["C1", "score"] * s.at["S1", "score"] * config.SCORE_MATRIX_SCALE)


def _matches():
    return pd.DataFrame([
        # กองปกติ (secondary ผ่าน band) · กองที่ secondary ว่าง · กองที่ primary เป็น None (ElasticNet ตัดหมด)
        {"FundCode": "A", "country_primary": "C1", "country_secondary": "C2", "country_r2": 0.8,
         "sector_primary": "S1", "sector_secondary": "S2", "sector_r2": 0.5,
         "country_primary_coef": 0.10, "country_secondary_coef": 0.08,
         "sector_primary_coef": 0.05, "sector_secondary_coef": 0.04},
        {"FundCode": "B", "country_primary": "C2", "country_secondary": None, "country_r2": 0.6,
         "sector_primary": "S2", "sector_secondary": None, "sector_r2": 0.5,
         "country_primary_coef": 0.06, "country_secondary_coef": np.nan,
         "sector_primary_coef": 0.05, "sector_secondary_coef": np.nan},
        {"FundCode": "C", "country_primary": None, "country_secondary": "C3", "country_r2": 0.1,
         "sector_primary": "S3", "sector_secondary": "S3", "sector_r2": 0.2,
         "country_primary_coef": np.nan, "country_secondary_coef": 0.02,
         "sector_primary_coef": np.nan, "sector_secondary_coef": 0.02},
    ])


def test_passes_band_checks_direction_and_strength():
    """2026-09-29 — secondary ต้องอยู่ในช่วง [primary×(1-pct), primary]: ทิศทางตรงกัน + แรง >= 70% ของ primary."""
    assert screening._passes_band(0.10, 0.08)          # แรง 80% ของ primary ทิศเดียวกัน -> ผ่าน (เกณฑ์ 70%)
    assert not screening._passes_band(0.10, 0.05)      # แรงแค่ 50% -> ไม่ผ่าน
    assert not screening._passes_band(0.10, -0.09)     # สวนทาง primary -> ไม่ผ่านเสมอ ไม่ว่าจะแรงแค่ไหน
    assert screening._passes_band(-0.10, -0.08)        # ทิศลบทั้งคู่ แรงพอ -> ผ่าน
    assert not screening._passes_band(np.nan, 0.08)
    assert not screening._passes_band(0.10, np.nan)


def test_fund_scores_nulls_score_secondary_when_band_fails():
    """secondary ที่สวนทาง หรือแรงไม่ถึง 70% ของ primary -> score_secondary ต้องเป็น NaN (ตัดสินใจ 2026-09-29)."""
    snap = _snapshot()
    m = screening.score_matrix(screening.zone_scores(snap, "country"), screening.zone_scores(snap, "sector"))
    matches = pd.DataFrame([
        {"FundCode": "D", "country_primary": "C1", "country_secondary": "C2", "country_r2": 0.8,
         "sector_primary": "S1", "sector_secondary": "S2", "sector_r2": 0.5,
         "country_primary_coef": 0.10, "country_secondary_coef": -0.09,   # country secondary สวนทาง primary
         "sector_primary_coef": 0.05, "sector_secondary_coef": 0.04},
        {"FundCode": "E", "country_primary": "C1", "country_secondary": "C2", "country_r2": 0.8,
         "sector_primary": "S1", "sector_secondary": "S2", "sector_r2": 0.5,
         "country_primary_coef": 0.10, "country_secondary_coef": 0.08,
         "sector_primary_coef": 0.05, "sector_secondary_coef": 0.02},    # sector secondary แรงไม่ถึง 70%
    ])
    out = screening.fund_scores(matches, m).set_index("FundCode")
    assert np.isnan(out.at["D", "score_secondary"])
    assert np.isnan(out.at["E", "score_secondary"])


def test_fund_scores_uses_r2_product_and_drops_unusable_primary():
    snap = _snapshot()
    m = screening.score_matrix(screening.zone_scores(snap, "country"), screening.zone_scores(snap, "sector"))
    out = screening.fund_scores(_matches(), m).set_index("FundCode")
    assert list(out.index) == ["A", "B"]                     # กอง C (primary=None) ถูกตัด
    assert out.at["A", "score"] == pytest.approx(0.8 * 0.5 * m.at["C1", "S1"])
    assert out.at["A", "score_secondary"] == pytest.approx(0.8 * 0.5 * m.at["C2", "S2"])
    assert np.isnan(out.at["B", "score_secondary"])          # ไม่มีคู่สำรอง -> NaN ไม่ใช่ 0


def _scored(n: int):
    """n กอง คะแนนไล่ลง — กอง i เกาะ C{i%2} / S{i%2} (ซ้ำกันเยอะ) และมีคู่สำรองที่ไม่ซ้ำ."""
    return pd.DataFrame([
        {"FundCode": f"F{i}", "score": 100 - i, "score_secondary": 50 - i,
         "country_primary": f"C{i % 2}", "sector_primary": f"S{i % 2}",
         "country_secondary": f"CX{i}", "sector_secondary": f"SX{i}"}
        for i in range(n)
    ])


def test_greedy_marks_both_dimensions_and_falls_back_to_secondary():
    sel = screening.greedy_select(_scored(6), n=6)
    assert sel.loc[0, "pair"] == "primary" and sel.loc[0, "eligible"]
    assert sel.loc[1, "pair"] == "primary"                   # F1 ใช้ C1/S1 ยังว่าง
    assert sel.loc[2, "pair"] == "secondary"                 # F2 ชน C0/S0 -> ใช้คู่สำรอง
    assert sel["used_country"].dropna().is_unique and sel["used_sector"].dropna().is_unique


def test_greedy_skips_secondary_fallback_when_score_secondary_is_nan():
    """score_secondary = NaN (ไม่ผ่าน band ตาม fund_scores) -> ห้ามลองเป็น fallback เลย ต่อให้เปิด use_secondary."""
    scored = pd.DataFrame([
        {"FundCode": "F0", "score": 100, "score_secondary": 50,
         "country_primary": "C0", "sector_primary": "S0",
         "country_secondary": "CX0", "sector_secondary": "SX0"},
        {"FundCode": "F1", "score": 90, "score_secondary": np.nan,   # ไม่ผ่าน band -> NaN
         "country_primary": "C0", "sector_primary": "S0",           # ชน F0 (primary ซ้ำ)
         "country_secondary": "CX1", "sector_secondary": "SX1"},
    ])
    sel = screening.greedy_select(scored, n=2, use_secondary=True)
    f1 = sel[sel["FundCode"] == "F1"].iloc[0]
    assert f1["pair"] == "fill" and not f1["eligible"]


def test_greedy_primary_only_mode_skips_the_fallback():
    sel = screening.greedy_select(_scored(6), n=6, use_secondary=False)
    assert int(sel["eligible"].sum()) == 2                   # เหลือแค่ 2 คู่ primary ที่ไม่ซ้ำ
    assert set(sel.loc[sel["eligible"], "pair"]) == {"primary"}


def test_greedy_fills_up_to_n_and_flags_the_filler_rows():
    sel = screening.greedy_select(_scored(6), n=6, use_secondary=False)
    assert len(sel) == 6
    fill = sel[~sel["eligible"]]
    assert set(fill["pair"]) == {"fill"} and fill["used_country"].isna().all()
    assert sel["FundCode"].is_unique                          # กองที่เลือกแล้วต้องไม่ถูกเติมซ้ำ


def test_greedy_or_mode_is_looser_than_and_mode():
    # country ซ้ำกันทุก 2 กอง แต่ sector ไม่ซ้ำเลย -> AND ตกตั้งแต่กองที่ 3 ส่วน OR ยังผ่าน (sector ใหม่)
    scored = pd.DataFrame([
        {"FundCode": f"F{i}", "score": 100 - i, "score_secondary": np.nan,
         "country_primary": f"C{i % 2}", "sector_primary": f"S{i}",
         "country_secondary": None, "sector_secondary": None}
        for i in range(6)
    ])
    n_and = int(screening.greedy_select(scored, n=6, use_secondary=False, strict_and=True)["eligible"].sum())
    n_or = int(screening.greedy_select(scored, n=6, use_secondary=False, strict_and=False)["eligible"].sum())
    assert n_or > n_and


def test_clean_country_set_is_valid_and_still_low_vif():
    """ชุด 11 ตัวถูก hardcode ไว้ (ไม่รัน VIF ตอน build) — test คอยจับถ้าข้อมูลเปลี่ยนจน collinear อีก."""
    from data import msci_index
    assert len(config.SCORE_COUNTRY_CLEAN) == 11
    assert set(config.SCORE_COUNTRY_CLEAN) <= set(config.MSCI_COUNTRY_COLS)
    x = msci_index.load_country_index()[config.SCORE_COUNTRY_CLEAN].pct_change().dropna().to_numpy()
    vif = []
    for j in range(x.shape[1]):
        y, z = x[:, j], np.column_stack([np.ones(len(x)), np.delete(x, j, axis=1)])
        resid = y - z @ np.linalg.lstsq(z, y, rcond=None)[0]
        vif.append(1.0 / (1.0 - (1.0 - resid.var() / y.var())))
    assert max(vif) < config.SCORE_VIF_MAX, f"VIF สูงสุด {max(vif):.1f}"


def test_greedy_min_score_rejects_a_new_pair_with_low_score():
    """คู่ใหม่แต่คะแนนต่ำกว่าเกณฑ์ -> ไม่ผ่าน (ไม่ mark used) ส่วนกองคะแนนสูงกว่ายังผ่านตามปกติ."""
    scored = pd.DataFrame([
        {"FundCode": "HI", "score": 5.0, "score_secondary": np.nan,
         "country_primary": "C0", "sector_primary": "S0", "country_secondary": None, "sector_secondary": None},
        {"FundCode": "LO", "score": 0.1, "score_secondary": np.nan,
         "country_primary": "C1", "sector_primary": "S1", "country_secondary": None, "sector_secondary": None},
    ])
    sel = screening.greedy_select(scored, n=2, min_score=0.7).set_index("FundCode")
    assert sel.at["HI", "eligible"] and not sel.at["LO", "eligible"] and sel.at["LO", "pair"] == "fill"
    assert screening.greedy_select(scored, n=2).set_index("FundCode").at["LO", "eligible"]   # ค่าเริ่มต้น 0 = ไม่กรอง


def test_greedy_min_score_uses_the_score_of_the_pair_actually_used():
    """primary ชน -> ใช้ secondary: ต้องเทียบ score_secondary กับเกณฑ์ (ไม่ใช่ score ของ primary ที่สูงกว่า)."""
    scored = pd.DataFrame([
        {"FundCode": "A", "score": 9.0, "score_secondary": 3.0,
         "country_primary": "C0", "sector_primary": "S0", "country_secondary": "CX0", "sector_secondary": "SX0"},
        {"FundCode": "B", "score": 8.0, "score_secondary": 0.2,     # primary ชน A แต่คู่สำรองคะแนนต่ำ
         "country_primary": "C0", "sector_primary": "S0", "country_secondary": "CX1", "sector_secondary": "SX1"},
    ])
    sel = screening.greedy_select(scored, n=2, min_score=0.7).set_index("FundCode")
    assert sel.at["A", "eligible"] and sel.at["A", "pair"] == "primary"
    assert not sel.at["B", "eligible"]


def test_greedy_min_score_tries_secondary_when_a_free_primary_is_too_weak():
    """primary ยังว่างแต่คะแนนต่ำ -> ต้องลองคู่สำรองต่อ (ไม่งั้นกองที่ primary ว่างเสียเปรียบกองที่ primary ชน)."""
    scored = pd.DataFrame([
        {"FundCode": "W", "score": 0.1, "score_secondary": 2.0,
         "country_primary": "C0", "sector_primary": "S0", "country_secondary": "C1", "sector_secondary": "S1"},
    ])
    w = screening.greedy_select(scored, n=1, min_score=0.7).iloc[0]
    assert w["eligible"] and w["pair"] == "secondary" and w["used_country"] == "C1"
    w = screening.greedy_select(scored, n=1, min_score=0.7, use_secondary=False).iloc[0]
    assert not w["eligible"]                                  # Primary only -> ไม่มีทางสำรอง


# --- §12.14 สูตรใหม่: return 12-1 ÷ realized vol ช่วงเดียวกัน ---

def _levels(n=300, seed=3):
    d = pd.bdate_range("2023-01-02", periods=n)
    return pd.Series(100 * np.cumprod(1 + np.random.default_rng(seed).normal(0, 0.01, n)), index=d)


def test_realized_vol_window_uses_the_231_returns_of_the_momentum_window():
    s = _levels()
    w, k = config.SCORE_RETURN_WINDOW, config.SCORE_RETURN_SKIP
    r = s.pct_change()
    hand = r.iloc[len(s) - w:len(s) - k].std(ddof=1) * np.sqrt(config.TRADING_DAYS)   # return t−251 .. t−21
    assert len(r.iloc[len(s) - w:len(s) - k]) == w - k == 231
    assert screening.realized_vol_window(s) == pytest.approx(hand)
    shuffled = s.sample(frac=1, random_state=0)                                         # sort_index ภายใน
    assert screening.realized_vol_window(shuffled) == pytest.approx(hand)


def test_realized_vol_window_handles_skip_zero_and_short_series():
    s = _levels()
    r = s.pct_change()
    assert screening.realized_vol_window(s, window=50, skip=0) == pytest.approx(
        r.iloc[-50:].std(ddof=1) * np.sqrt(config.TRADING_DAYS))                       # iloc[a:-0] ว่าง — ต้องไม่เกิด
    assert np.isnan(screening.realized_vol_window(s.iloc[:100]))                      # สั้นกว่า window -> NaN


def test_zone_score_new_method_ranks_return_per_unit_of_risk():
    snap = _snapshot()
    snap.loc[snap["index"] == "C1", [RET, VOL]] = [0.40, 0.40]     # return สูงสุดแต่ vol สูง -> ratio 1.0
    snap.loc[snap["index"] == "C2", [RET, VOL]] = [0.30, 0.10]     # ratio 3.0 -> ดีสุด
    snap.loc[snap["index"] == "C4", [RET, VOL]] = [-0.20, 0.20]    # momentum ติดลบ -> ท้ายสุด ไม่ error
    z = screening.zone_scores(snap, "country")
    assert list(z.columns) == ["return_12m1", "vol_realized", "ratio", "score"]
    assert z.index[0] == "C2" and z.index[-1] == "C4"
    assert z["score"].between(config.SCORE_PCT_LO, config.SCORE_PCT_HI).all()
    assert z.loc["C2", "ratio"] == pytest.approx(3.0)


def test_zone_score_new_method_bad_vol_gives_nan_that_never_passes():
    snap = _snapshot()
    snap.loc[snap["index"] == "C1", VOL] = 0.0
    snap.loc[snap["index"] == "C2", VOL] = np.nan
    z = screening.zone_scores(snap, "country")
    assert z.loc[["C1", "C2"], "score"].isna().all() and z.loc[["C3", "C4"], "score"].notna().all()
    m = screening.score_matrix(z, screening.zone_scores(snap, "sector"))
    assert m.loc[["C1", "C2"]].isna().all().all()                 # -> fund_scores ตัดกองที่เกาะโซนนี้ทิ้ง ไม่ผ่านเกณฑ์


def test_zone_score_new_method_equal_vol_reduces_to_momentum_rank_and_reranks_universe():
    snap = _snapshot()
    snap[VOL] = 0.2
    z = screening.zone_scores(snap, "country")
    assert list(z.index) == ["C1", "C2", "C3", "C4"]
    sub = screening.zone_scores(snap, "country", ["C2", "C3", "C4"])   # §12.10 re-rank ภายในชุดที่เลือก
    assert sub.loc["C2", "score"] == pytest.approx(config.SCORE_PCT_HI)
    assert sub.loc["C2", "score"] > z.loc["C2", "score"]


def test_zone_score_rejects_unknown_method(monkeypatch):
    monkeypatch.setattr(config, "SCORE_ZONE_METHOD", "nope")
    with pytest.raises(ValueError, match="SCORE_ZONE_METHOD"):
        screening.zone_scores(_snapshot(), "country")


def test_greedy_and_mode_blocks_a_reused_sector_even_with_a_new_country():
    """F1 country ใหม่แต่ sector ซ้ำ F0 -> AND ต้องตก (จับ mutant ที่ลืม mark sector — fixture เดิมผูก C กับ S ไว้ด้วยกัน)."""
    scored = pd.DataFrame([
        {"FundCode": "F0", "score": 9.0, "score_secondary": np.nan,
         "country_primary": "C0", "sector_primary": "S0", "country_secondary": None, "sector_secondary": None},
        {"FundCode": "F1", "score": 8.0, "score_secondary": np.nan,
         "country_primary": "C1", "sector_primary": "S0", "country_secondary": None, "sector_secondary": None},
        {"FundCode": "F2", "score": 7.0, "score_secondary": np.nan,
         "country_primary": "C0", "sector_primary": "S1", "country_secondary": None, "sector_secondary": None},
    ])
    sel = screening.greedy_select(scored, n=3, use_secondary=False, strict_and=True).set_index("FundCode")
    assert sel.at["F0", "eligible"] and not sel.at["F1", "eligible"] and not sel.at["F2", "eligible"]


def test_greedy_marks_the_unused_secondary_pair_so_a_twin_cannot_slip_in():
    """V1: A เข้าด้วย primary (C0,S0) มี secondary (C1,S1) ผ่าน band · B profile เหมือน A ทุกอย่าง -> ต้องไม่ผ่าน."""
    twin = {"score_secondary": 5.0, "country_primary": "C0", "sector_primary": "S0",
            "country_secondary": "C1", "sector_secondary": "S1"}
    scored = pd.DataFrame([{"FundCode": "A", "score": 9.0, **twin}, {"FundCode": "B", "score": 8.0, **twin}])
    sel = screening.greedy_select(scored, n=2).set_index("FundCode")
    assert sel.at["A", "eligible"] and not sel.at["B", "eligible"]


def test_greedy_returns_a_boolean_eligible_column_when_nothing_is_scored():
    """ไม่มีกองเลย -> eligible ต้องเป็น bool ให้ df[df.eligible] ใช้ได้ (เดิม object dtype -> หน้า 8 KeyError)."""
    empty = pd.DataFrame(columns=["FundCode", "score", "score_secondary", "country_primary", "sector_primary",
                                  "country_secondary", "sector_secondary"])
    sel = screening.greedy_select(empty, n=5)
    assert sel["eligible"].dtype == bool and sel[sel["eligible"]].empty
