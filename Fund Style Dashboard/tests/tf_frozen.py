"""tf_frozen.py — ชุดข้อมูลแช่แข็งของโมเดลหน้า 9 (input ที่ทีม quant ใช้ตรวจผล) สำหรับ regression test.

ทำไมต้องแช่แข็ง: ถ้าคำนวณจาก cache/nav_clean.parquet ตัวจริง พอ rebuild แล้ว NAV ย้อนหลังเปลี่ยน test จะแดงทั้งที่โค้ดไม่ผิด
- `load()` -> (ModelInputs, FeeData) จาก tests/fixtures/tf_frozen/ — ไม่ขึ้นกับ cache/base_data
- `slice_live()` -> ข้อมูลจริงตัดแบบเดียวกัน ใช้ตรวจว่าข้อมูลจริงยังตรงกับชุดแช่แข็งไหม (ไม่ตรง = ข้อมูลเปลี่ยน ไม่ใช่โค้ดพัง)
- NAV/ปฏิทิน/ACWI ตัดถึง TF_EVAL_END (backtest ใช้ข้อมูล ≤ วันนั้นเท่านั้น) · ค่าธรรมเนียมเก็บทุกวันที่ของกองที่ใช้
  (median fallback ใช้ snapshot ล่าสุดของแต่ละกอง)

สร้างใหม่ (เฉพาะเมื่อตั้งใจเปลี่ยน reference และตรวจผลกับทีม quant แล้ว):
    PYTHONPATH=. ./.venv/bin/python -m tests.tf_frozen
"""
from __future__ import annotations

import json
import os

import pandas as pd

import config
from analysis import tf_model
from analysis.fund_fees import CODES, FeeData

DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "tf_frozen")
FEE_COLS = ["Fund Code", "Complex Type Code", "Code", "As of Date", "Actual Value"]


def slice_live() -> dict:
    """ข้อมูลจริงปัจจุบัน ตัดตามกติกาของชุดแช่แข็ง."""
    import data_access
    from data import msci_index

    cut = pd.Timestamp(config.TF_EVAL_END)
    nav = data_access._tf_inputs().nav
    cty = msci_index.load_country_index()
    calendar = cty.index.union(msci_index.load_sector_index().index).sort_values()
    funds = set(nav["FundCode"])
    fee = pd.read_csv(config.SEC_FUND_FEE_CSV, dtype=str, encoding="utf-8-sig")
    fee = fee[(fee["Complex Type Code"] == "FEEUH") & fee["Code"].isin(CODES) & fee["Fund Code"].isin(funds)][FEE_COLS]
    prof = pd.read_csv(config.FUND_PROFILE_CSV, dtype=str)
    prof = prof[prof["Fund Code"].isin(funds)][["Fund Code", "AMC_CODE"]]
    acwi = cty[config.TF_TREND_INDEX]
    return {
        "nav": nav[nav["NAVDate"] <= cut].sort_values(["FundCode", "NAVDate"]).reset_index(drop=True),
        "calendar": pd.DataFrame({"date": calendar[calendar <= cut]}),
        "acwi": acwi[acwi.index <= cut].rename_axis("date").reset_index(name="level"),
        "fees": fee.sort_values(FEE_COLS).reset_index(drop=True),
        "profile": prof.sort_values("Fund Code").reset_index(drop=True),
        "groups": dict(sorted(data_access.share_class_groups().items())),
    }


def _paths() -> dict:
    return {k: os.path.join(DIR, f) for k, f in (("nav", "nav.parquet"), ("calendar", "calendar.parquet"),
                                                   ("acwi", "acwi.parquet"), ("fees", "fees.csv.gz"),
                                                   ("profile", "profile.csv"), ("groups", "groups.json"))}


def read_raw() -> dict:
    p = _paths()
    return {
        "nav": pd.read_parquet(p["nav"]),
        "calendar": pd.read_parquet(p["calendar"]),
        "acwi": pd.read_parquet(p["acwi"]),
        "fees": pd.read_csv(p["fees"], dtype=str, keep_default_na=False, na_values=[""]),
        "profile": pd.read_csv(p["profile"], dtype=str),
        "groups": json.load(open(p["groups"], encoding="utf-8")),
    }


def available() -> bool:
    return all(os.path.exists(p) for p in _paths().values())


def load() -> tuple[tf_model.ModelInputs, FeeData]:
    raw = read_raw()
    p = _paths()
    inp = tf_model.ModelInputs(nav=raw["nav"], calendar=pd.DatetimeIndex(raw["calendar"]["date"]),
                               trend_index=raw["acwi"].set_index("date")["level"].rename(config.TF_TREND_INDEX),
                               groups=raw["groups"])
    fee = FeeData(sorted(raw["fees"]["Fund Code"].unique()), fee_csv=p["fees"], profile_csv=p["profile"])
    return inp, fee


def write(data: dict) -> None:
    os.makedirs(DIR, exist_ok=True)
    p = _paths()
    for k in ("nav", "calendar", "acwi"):
        data[k].to_parquet(p[k], index=False, compression="zstd")
    data["fees"].to_csv(p["fees"], index=False, compression="gzip")
    data["profile"].to_csv(p["profile"], index=False)
    with open(p["groups"], "w", encoding="utf-8") as f:
        json.dump(data["groups"], f, ensure_ascii=False, indent=0)


if __name__ == "__main__":
    write(slice_live())
    print("เขียน", DIR, {k: os.path.getsize(v) for k, v in _paths().items()})
