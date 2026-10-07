"""test_fund_fees.py — อ่านค่าธรรมเนียมจาก SecFundFee: ข้อความ "ไม่มี" = 0 และแถวซ้ำเลือกค่าแบบคงที่."""

import pandas as pd
import pytest

from analysis.fund_fees import FeeData, parse_fee_value


def test_parse_fee_value_handles_text_and_percent_sign():
    raw = pd.Series(["1.5", "ไม่มี", "ยกเว้น", "ปัจจุบันไม่เรียกเก็บ", "0.535%", "", None, "n/a"])
    out = parse_fee_value(raw).tolist()
    assert out[:5] == [1.5, 0.0, 0.0, 0.0, 0.535]
    assert all(pd.isna(x) for x in out[5:])


def _fee_files(tmp_path, rows):
    fee = pd.DataFrame(rows, columns=["Fund Code", "Complex Type Code", "Code", "As of Date", "Actual Value"])
    fee_csv, prof_csv = tmp_path / "fee.csv", tmp_path / "prof.csv"
    fee.to_csv(fee_csv, index=False)
    pd.DataFrame({"Fund Code": ["A", "B"], "AMC_CODE": ["X", "Y"]}).to_csv(prof_csv, index=False)
    return str(fee_csv), str(prof_csv)


def test_no_fee_text_is_zero_not_median(tmp_path):
    fee_csv, prof_csv = _fee_files(tmp_path, [("A", "FEEUH", "FF", "20240101", "ไม่มี"),
                                             ("B", "FEEUH", "FF", "20240101", "1.5")])
    data = FeeData(["A", "B"], fee_csv=fee_csv, profile_csv=prof_csv)
    assert data.rate("A", "FF", pd.Timestamp("2024-06-01")) == 0.0
    assert data.n_fallback["FF"] == 0


@pytest.mark.parametrize("order", [("0", "1.5"), ("1.5", "0")])
def test_duplicate_rows_pick_the_higher_rate_regardless_of_file_order(tmp_path, order):
    fee_csv, prof_csv = _fee_files(tmp_path, [("A", "FEEUH", "FF", "20240101", order[0]),
                                             ("A", "FEEUH", "FF", "20240101", order[1]),
                                             ("B", "FEEUH", "FF", "20240101", "1.0")])
    data = FeeData(["A", "B"], fee_csv=fee_csv, profile_csv=prof_csv)
    assert data.rate("A", "FF", pd.Timestamp("2024-06-01")) == 1.5
