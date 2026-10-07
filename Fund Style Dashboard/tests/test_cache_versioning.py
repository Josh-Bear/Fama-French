"""test_cache_versioning.py — stamp ของ cache ผูกกับไฟล์โค้ด/ข้อมูล และแต่ละ getter มี cache แยกกัน."""

import os

import data_access


def test_stamp_tracks_code_files():
    names = {os.path.relpath(p, data_access._ROOT) for p in data_access._CODE_FILES}
    assert {"data_access.py", "config.py", os.path.join("analysis", "tf_model.py"),
            os.path.join("analysis", "matching.py")} <= names


def test_each_getter_gets_its_own_cache_key():
    def fake_cache_data(**kw):
        def deco(f):
            fake_cache_data.seen.append((f.__qualname__, kw.get("max_entries")))
            return f
        return deco
    fake_cache_data.seen = []
    data_access._versioned(data_access._load_results, fake_cache_data, data_access.RESULTS_CSV)
    data_access._versioned(data_access.tf_live, fake_cache_data)
    (q1, m1), (q2, m2) = fake_cache_data.seen
    assert q1 != q2 and m1 == m2 == data_access._CACHE_MAX_ENTRIES
