"""test_viz.py — band-based secondary ของ Match Strength (หน้า 3) + macro bar (หน้า 7).

secondary = ทุก index นอกจาก primary ที่ |coef| >= |primary| × (1 − config.SECONDARY_BAND_PCT)
"""

import numpy as np
import pandas as pd

import config
import viz


def _coefs(values, fund="F1", scope="country"):
    """สร้าง coefs DataFrame ตาม schema จริง (FundCode, scope, index, elastic/lasso/ridge)."""
    return pd.DataFrame([
        {"FundCode": fund, "scope": scope, "index": f"MSCI_{i}",
         "elastic": v, "lasso": v, "ridge": v,
         "is_primary": False, "is_secondary": False}
        for i, v in enumerate(values)
    ])


def _colors(values, **kw):
    fig = viz.match_strength_bar(_coefs(values, **kw), "F1", "country", "elastic")
    return list(fig.data[0].marker.color)


def test_band_includes_only_within_threshold():
    """band=30% -> ตัวที่ >=70% ของ primary เป็น secondary, ต่ำกว่านั้นเป็นอื่นๆ."""
    assert config.SECONDARY_BAND_PCT == 0.30
    # 1.0 (primary) / 0.80 = 80% ผ่าน / 0.60 = 60% ไม่ผ่าน
    assert _colors([1.0, 0.80, 0.60]) == [viz.PRIMARY_C, viz.SECONDARY_C, viz.OTHER_C]


def test_band_allows_multiple_secondaries():
    """exposure ใกล้เคียงกันหลายตัว -> secondary ได้หลายตัว (จุดประสงค์หลักของการแก้)."""
    colors = _colors([1.0, 0.95, 0.75, 0.50])
    assert colors == [viz.PRIMARY_C, viz.SECONDARY_C, viz.SECONDARY_C, viz.OTHER_C]


def test_band_uses_absolute_value_so_opposite_sign_counts():
    """เทียบด้วย |coef| -> exposure เครื่องหมายตรงข้าม primary ก็เป็น secondary ได้ (เคส ABAGS)."""
    assert _colors([0.0189, -0.0160]) == [viz.PRIMARY_C, viz.SECONDARY_C]
    # 0.0125/0.0189 = 66% -> ต่ำกว่า 70% ถึงแม้เครื่องหมายลบเหมือนกัน
    assert _colors([0.0189, -0.0125])[1] == viz.OTHER_C


def test_single_and_empty_exposure():
    """กองมี exposure เดียว -> primary อย่างเดียว ไม่ error; ไม่มีเลย -> None."""
    assert _colors([0.05]) == [viz.PRIMARY_C]
    assert viz.match_strength_bar(_coefs([0.0, 0.0]), "F1", "country", "elastic") is None


def _macro_loadings():
    """schema จริงของ cache/macro_loadings.csv — implied บวก / direct ลบ ให้แยกกันออก."""
    return pd.DataFrame([
        {"FundCode": "F1", "method": m, "factor": f, "loading": 0.1 * i,
         "impact_1sd": 0.01 * i * (1 if m == "implied" else -1), "r2": 0.3, "n_months": 60}
        for m in ["implied", "direct"] for i, f in enumerate(config.MACRO_FACTOR_COLS)
    ])


def test_macro_bar_fixed_order_two_methods_and_median():
    """factor เรียงตาม config เสมอ (ไม่เรียงตามขนาด) · 2 วิธีคนละ group · ◆ median ขึ้น legend ครั้งเดียว."""
    ld = _macro_loadings().sample(frac=1, random_state=0)          # ลำดับแถวสุ่ม
    sd = pd.Series(0.05, index=config.MACRO_FACTOR_COLS)
    peer = ld.pivot_table(index="factor", columns="method", values="impact_1sd", aggfunc="median")
    fig = viz.macro_bar(ld, "F1", sd, peer)
    bars = [t for t in fig.data if t.type == "bar"]
    marks = [t for t in fig.data if t.type == "scatter"]
    assert [t.offsetgroup for t in bars] == ["implied", "direct"]
    assert np.allclose(bars[0].y, [0.01 * i for i in range(7)])
    assert np.allclose(bars[1].y, [-0.01 * i for i in range(7)])
    assert [x.split("<br>")[0] for x in bars[0].x] == config.MACRO_FACTOR_COLS
    assert len(marks) == 2 and [bool(t.showlegend) for t in marks] == [True, False]


def test_macro_factor_tick_units():
    """1 SD ของ factor แบบ return เป็น % · แบบ Δ ใช้หน่วยของมันเอง."""
    assert "11.7%" in viz.macro_factor_tick("Oil_Brent", 0.1166)
    assert "4.73 จุด" in viz.macro_factor_tick("VIX", 4.7287)
    assert "0.27 pp" in viz.macro_factor_tick("US10Y", 0.2714)


def test_frontier_chart_downsamples_the_cloud_but_keeps_every_frontier_point():
    """กลุ่มเมฆ > PORTFOLIO_CLOUD_MAX_POINTS ถูกสุ่มลด (figure ไม่บวม) · frontier/จุดอ้างอิงครบ · ทุก trace เป็น WebGL."""
    rng = np.random.default_rng(0)
    n = config.PORTFOLIO_CLOUD_MAX_POINTS + 1_000
    cloud = pd.DataFrame({"risk": rng.uniform(0.05, 0.2, n), "ret": rng.uniform(0.0, 0.05, n)})
    frontier = cloud.nsmallest(300, "risk")
    singles = pd.DataFrame({"risk": [0.1, 0.2], "ret": [0.02, 0.04]}, index=["A", "B"])
    ref = pd.Series({"risk": 0.12, "ret": 0.03})
    fig = viz.frontier_chart(cloud, frontier, singles, ref, ref)
    assert len(fig.data[0].x) == config.PORTFOLIO_CLOUD_MAX_POINTS and f"{n:,}" in fig.data[0].name
    assert len(fig.data[1].x) == 300
    assert all(tr.type == "scattergl" for tr in fig.data)
