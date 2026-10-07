"""test_nav_cleaning.py — การ clean NAV ต่อกอง (ตกลงกับผู้ใช้ 2026-09-30).

ครอบคลุม: อ่าน UpdateTime หลายรูปแบบ · ตรวจกองเลิก · ความสดของ NAV · ข้าม return ที่คร่อมรูข้อมูล
· parquet ของ NAV ที่ clean แล้ว · หน้า 8 เลือกได้ไม่เกิน 1 share class ต่อกลุ่ม
ทุก test ใช้ข้อมูลสังเคราะห์และ tmp_path — ไม่แตะ base_data/ หรือ cache/ จริง
"""

import numpy as np
import pandas as pd

import config
import data_access
from analysis import matching, screening
from analysis.matching import FUND_COL
from data import nav_loader


def test_parse_update_time_reads_all_three_formats_as_thai_time():
    s = pd.Series(["2022-07-12 10:42:59.423", "2026-08-25 15:44:10", "2026-06-30T04:11:06Z", None])
    out = nav_loader.parse_update_time(s)
    assert out.iloc[:3].notna().all() and pd.isna(out.iloc[3])
    assert out.iloc[0] == pd.Timestamp("2022-07-12 10:42:59.423")
    assert out.iloc[2] == pd.Timestamp("2026-06-30 11:11:06")      # 04:11 UTC = 11:11 เวลาไทย


def _write_nav_csv(tmp_path, monkeypatch, rows):
    path = tmp_path / "nav.csv"
    pd.DataFrame(rows, columns=["FundCode", "NAV", "NAVDate", "UpdateTime", "AUM"]).to_csv(path, index=False)
    monkeypatch.setattr(config, "NAV_HISTORY_CSV", str(path))
    monkeypatch.setattr(config, "CACHE_DIR", str(tmp_path))          # spike log (ถ้ามี) ลง tmp ไม่ลง cache จริง


def test_dedupe_keeps_the_latest_revision_across_formats_and_flags_closed_funds(tmp_path, monkeypatch):
    _write_nav_csv(tmp_path, monkeypatch, [
        ["A", 10.0, "2026-01-05", "2026-01-05 18:00:00.000", 1e6],
        ["A", 11.0, "2026-01-05", "2026-01-06T02:00:00Z", 1e6],        # revision ใหม่กว่า (09:00 ไทย วันถัดไป) ต้องชนะ
        ["A", 10.5, "2026-01-06", "2026-01-06 18:00:00", 1e6],
        ["A", 0.0, "2026-05-08", "2026-06-30T04:11:06Z", 1e6],         # NAV = 0 ต่อท้าย = เลิกกอง
        ["B", 0.0, "2025-12-01", "2025-12-01 18:00:00.000", 1e6],      # NAV = 0 **ก่อน** เปิดกอง = ไม่ใช่เลิก
        ["B", 5.0, "2026-01-05", "2026-01-05 18:00:00.000", 1e6],
    ])
    nav, closed, _ = nav_loader.load_nav_history_full(["A", "B"])
    a = nav[nav["FundCode"] == "A"].set_index("NAVDate")["NAV"]
    assert a[pd.Timestamp("2026-01-05")] == 11.0
    assert (nav["NAV"] > 0).all()
    assert closed == {"A"}


def test_fund_nav_status_flags_stale_and_closed_funds():
    nav = pd.DataFrame({"FundCode": ["A", "B", "C"],
                        "NAVDate": pd.to_datetime(["2026-07-30", "2026-01-07", "2026-07-30"]),
                        "NAV": [1.0, 1.0, 1.0]})
    st = nav_loader.fund_nav_status(nav, "2026-07-31", closed={"C"}, max_days=90)
    assert st.loc["A", "status"] == "keep" and st.loc["A", "days_behind"] == 1
    assert st.loc["B", "status"] == "stale" and st.loc["B", "days_behind"] == 205
    assert st.loc["C", "status"] == "closed"                            # เลิกกองชนะความสด


def _levels(n=120):
    d = pd.bdate_range("2024-01-01", periods=n)
    rng = np.random.default_rng(1)
    return pd.DataFrame({"X": 100 * np.cumprod(1 + rng.normal(0, 0.01, n))}, index=d)


def test_build_fund_returns_drops_only_the_return_that_spans_a_long_gap():
    lv = _levels()
    nav = lv["X"] / 10
    hole = nav.index[40:55]                                             # หาย 15 วันทำการ -> เกินเกณฑ์ 10
    small = nav.index[80:83]                                            # หาย 3 วัน -> ยังใช้ (ทบต้นตามเดิม)
    nav = nav.drop(hole).drop(small)
    out = matching.build_fund_returns(nav, lv, winsorize=False, max_gap_bdays=10)
    assert nav.index[40] not in out.index                               # return 39 -> 55 (ข้ามรู) ถูกทิ้ง
    assert nav.index[nav.index.get_loc(nav.index[40]) + 1] in out.index  # จุดถัดจากรูกลับมาใช้ตามปกติ
    after_small = nav.index[nav.index.searchsorted(lv.index[83])]
    assert after_small in out.index                                     # รูเล็กยังใช้
    assert len(out) == len(nav) - 2                                     # ทิ้งแค่จุดแรกของ series + จุดข้ามรู
    loose = matching.build_fund_returns(nav, lv, winsorize=False, max_gap_bdays=100)
    assert len(loose) == len(nav) - 1                                   # ปิดเกณฑ์ -> พฤติกรรมเดิม


def test_nav_clean_parquet_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "NAV_CLEAN_PARQUET", str(tmp_path / "nav_clean.parquet"))
    nav = pd.DataFrame({"FundCode": ["A", "A", "B"],
                        "NAVDate": pd.to_datetime(["2026-01-05", "2026-01-06", "2026-01-05"]),
                        "NAV": [10.0, 10.5, 5.0], "AUM": [1e6, 1e6, 2e6]})
    status = pd.DataFrame({"status": ["keep", "stale"]}, index=["A", "B"])
    spikes = pd.DataFrame({"FundCode": ["A"], "NAVDate": pd.to_datetime(["2026-01-06"]),
                           "nav_before": [99.0], "nav_after": [10.5]})
    data_access._write_nav_clean(nav, status, spikes)
    saved = pd.read_parquet(config.NAV_CLEAN_PARQUET)
    assert saved["spike_fixed"].tolist() == [False, True, False]
    assert saved["status"].tolist() == ["keep", "keep", "stale"]
    got = data_access._load_clean_nav(["A"])
    assert list(got) == ["A"] and got["A"].tolist() == [10.0, 10.5]


def test_greedy_allows_at_most_one_share_class_per_group():
    """share class ของกองเดียวกันที่ ElasticNet ให้คู่ต่างกัน (หลุดตัวกรอง country/sector) ต้องผ่านได้แค่ตัวเดียว."""
    scored = pd.DataFrame([
        {"FundCode": "GEF-X", "score": 9.0, "score_secondary": np.nan, "country_primary": "USA",
         "sector_primary": "MT", "country_secondary": None, "sector_secondary": None},
        {"FundCode": "GEF-A", "score": 5.0, "score_secondary": np.nan, "country_primary": "USA",
         "sector_primary": "IT", "country_secondary": None, "sector_secondary": None},
        {"FundCode": "OTHER", "score": 4.0, "score_secondary": np.nan, "country_primary": "JAPAN",
         "sector_primary": "IN", "country_secondary": None, "sector_secondary": None},
    ])
    groups = {"GEF-X": "GEF", "GEF-A": "GEF"}
    sel = screening.greedy_select(scored, n=3, strict_and=False, groups=groups).set_index("FundCode")
    assert sel.at["GEF-X", "eligible"] and not sel.at["GEF-A", "eligible"] and sel.at["OTHER", "eligible"]
    loose = screening.greedy_select(scored, n=3, strict_and=False).set_index("FundCode")
    assert loose.at["GEF-A", "eligible"]                                # ไม่ส่ง groups = พฤติกรรมเดิม
