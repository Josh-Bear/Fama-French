"""test_smoke.py — Phase 0 checkpoint: โครงสร้าง + config + import ครบ ไม่ error."""

import os

import config


def test_base_data_files_exist():
    """path ทุกไฟล์ดิบใน config ต้องชี้ไปที่ base_data/ ที่มีอยู่จริง (ไม่มี path ค้าง Downloads/MSCI)."""
    for path in [
        config.FUND_PROFILE_CSV,
        config.NAV_HISTORY_CSV,
        config.MSCI_COUNTRY_CSV,
        config.MSCI_SECTOR_CSV,
        config.SEC_FUND_FEE_CSV,
        config.TOP_HOLDING_CSV,
    ]:
        assert os.path.exists(path), f"ไม่พบไฟล์: {path}"
        assert "base_data" in path


def test_msci_column_counts():
    """country = 18, sector = 10 ตามไฟล์จริง."""
    assert len(config.MSCI_COUNTRY_COLS) == 18
    assert len(config.MSCI_SECTOR_COLS) == 10


def test_modules_import():
    """ทุก module import ได้ ไม่ error."""
    import analysis.matching  # noqa: F401
    import analysis.metrics  # noqa: F401
    import data.fund_profile  # noqa: F401
    import data.msci_index  # noqa: F401
    import data.nav_loader  # noqa: F401
    import data_access  # noqa: F401
    import viz  # noqa: F401
