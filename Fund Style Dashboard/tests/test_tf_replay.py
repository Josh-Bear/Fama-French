"""test_tf_replay.py — กติกาไตรมาส/เหตุผลการขายออก/ตัวเช็ค cache เก่าของหน้า 9 (ไม่ต้องใช้ข้อมูลจริง)."""

import os

import pandas as pd

import config
import data_access
from analysis import tf_model as tm


def test_partial_last_quarter_is_not_a_quarter_end():
    cal = pd.bdate_range("2025-07-01", "2025-12-15")              # MSCI อัปเดตถึงกลาง ธ.ค.
    assert tm.complete_quarters(cal, "2025-07-01", "2025-12-31") == [pd.Timestamp("2025-09-30")]


def test_last_quarter_counts_once_data_reaches_its_last_business_day_or_beyond():
    full = pd.bdate_range("2025-07-01", "2025-12-31")
    assert tm.complete_quarters(full, "2025-07-01", "2025-12-31")[-1] == pd.Timestamp("2025-12-31")
    holiday = pd.bdate_range("2025-07-01", "2026-01-15").drop(pd.Timestamp("2025-12-31"))
    assert pd.Timestamp("2025-12-30") in tm.complete_quarters(holiday, "2025-07-01", "2026-01-15")


def test_drop_reasons_separate_data_gaps_from_rank():
    held = {"A": "A-A", "B": "B-A", "C": "C-A", "D": "D-A", "E": "E-A"}
    reasons = tm.drop_reasons(held, selected={"E": "E-H"},
                              in_universe={"B-A", "C-A", "D-A", "E-A"}, fresh={"C-A", "D-A", "E-A"},
                              investable={"D-A"}, ranks={"D": config.TF_HYSTERESIS_K + 1}, fallback=False)
    r = {x["family"]: x for x in reasons}
    assert set(r) == {"A", "B", "C", "D", "E"}
    assert r["A"]["data_issue"] and r["B"]["data_issue"] and r["C"]["data_issue"]     # เก่า 90 วัน / ไม่สด / สัญญาณ
    assert not r["D"]["data_issue"] and "หลุดอันดับ" in r["D"]["reason"]
    assert "E-H" in r["E"]["reason"]                                                   # เปลี่ยน class ก็นับว่าไม่ถือต่อ
    assert tm.drop_reasons({"X": "X-A"}, {"X": "X-A"}, {"X-A"}, {"X-A"}, {"X-A"}, {"X": 1}, False) == []


def test_tf_fingerprint_ignores_paths_but_tracks_model_config(monkeypatch):
    base = data_access._tf_config_fingerprint()
    monkeypatch.setattr(config, "TF_M001_REFERENCE_CSV", "/somewhere/else/m001.csv")
    assert data_access._tf_config_fingerprint() == base                                # ย้ายโฟลเดอร์ไม่ทำให้ดูเก่า
    monkeypatch.setattr(config, "TF_TOP3_N_TRIALS", config.TF_TOP3_N_TRIALS + 1)
    assert data_access._tf_config_fingerprint() == base                                # ค่าแสดงผลส่วนที่ 2 ไม่เกี่ยวกับ cache
    monkeypatch.setattr(config, "NAV_STALE_MAX_DAYS", config.NAV_STALE_MAX_DAYS + 1)
    assert data_access._tf_config_fingerprint() != base


def test_tf_input_hashes_follow_content_not_mtime(tmp_path, monkeypatch):
    f = tmp_path / "a.csv"
    f.write_text("x\n1\n")
    monkeypatch.setattr(data_access, "TF_INPUT_FILES", (str(f), str(tmp_path / "missing.csv")))
    base = data_access._tf_input_hashes()
    assert base["missing.csv"] is None
    os.utime(f, (1, 1))                                                                # checkout/clone เปลี่ยนแค่ mtime
    assert data_access._tf_input_hashes() == base
    f.write_text("x\n2\n")
    assert data_access._tf_input_hashes()["a.csv"] != base["a.csv"]


def test_tf_inputs_cover_every_file_the_model_reads():
    names = {p for p in data_access.TF_INPUT_FILES}
    for p in (config.NAV_CLEAN_PARQUET, config.MSCI_COUNTRY_CSV, config.MSCI_SECTOR_CSV, config.SHARE_CLASS_CSV,
              config.SEC_FUND_FEE_CSV, config.FUND_PROFILE_CSV, config.TF_M001_REFERENCE_CSV):
        assert p in names
