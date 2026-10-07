"""test_filters.py — fund filter + MSCI load (Phase 1). เร็ว (ไม่แตะ nav 336MB — อยู่ใน checkpoint1)."""

import config
from data import fund_profile, msci_index


def test_filter_criteria_present():
    """เงื่อนไขกรอง 9 ข้อ (eq 6 + neq 2 + empty 1) ต้องอยู่ครบใน config."""
    assert len(config.FILTER_EQ) == 6
    assert len(config.FILTER_NEQ) == 2
    assert len(config.FILTER_EMPTY) == 1


def test_filter_produces_715():
    """กรอง FundProfile จริง -> 715 กอง (E600/F77/O38), ไม่มี Fund Code ซ้ำ."""
    filt = fund_profile.filter_funds(fund_profile.load_fund_profile())
    assert len(filt) == config.EXPECTED_FILTERED_FUNDS
    pol = fund_profile._norm(filt[config.FUND_POLICY_COL]).value_counts().to_dict()
    assert (pol.get("E"), pol.get("F"), pol.get("O")) == (600, 77, 38)
    assert filt[config.FUND_CODE_COL].duplicated().sum() == 0
    assert len(fund_profile.fund_universe(filt)) == 715


def test_msci_load():
    """MSCI country 18 / sector 10 คอลัมน์, ไม่มี NaN, daily return น้อยกว่า level 1 แถว."""
    cty = msci_index.load_country_index()
    sec = msci_index.load_sector_index()
    assert list(cty.columns) == config.MSCI_COUNTRY_COLS
    assert list(sec.columns) == config.MSCI_SECTOR_COLS
    assert cty.isna().sum().sum() == 0 and sec.isna().sum().sum() == 0
    assert len(msci_index.to_daily_return(cty)) == len(cty) - 1
