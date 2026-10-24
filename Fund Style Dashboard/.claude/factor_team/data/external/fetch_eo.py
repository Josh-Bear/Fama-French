"""fetch_eo.py — ดาวน์โหลดข้อมูลภายนอกของงาน F5-EO (F-R006 §5 · ผู้ใช้อนุมัติทั้ง 10 รายการ 2026-10-20 · BRIEF 111 / 113).

เขียนเฉพาะในโฟลเดอร์นี้ (ไม่แตะ base_data/) · ไฟล์ต้นฉบับ (zip / xlsx) เก็บใน raw_eo/ ไม่แตกไฟล์ (data-engineer อ่าน/แปลงเอง)
· Yahoo / FRED บันทึกเป็น CSV ด้วย save() เดิมของ fetch_external.py · รันซ้ำ = ดึงใหม่ทับไฟล์เดิม (ต้องได้รับอนุมัติใหม่)
  1–2, 5–6  Ken French Data Library (zip)          → raw_eo/KF_*.zip
  3, 9      JKP all themes · daily · capped VW      → raw_eo/JKP_{EMERGING,DEVELOPED}_THEMES_DAILY.zip
  4         Yahoo GLD / VNQ / VNQI                  → EO_ALT_ETF.csv
  7         FRED DTWEXBGS / DTWEXEMEGS / DFII10     → US_DOLLAR_REALRATE_FRED.csv
  8         Yahoo 1343.T / CLR.SI / JPYTHB=X / SGDTHB=X → ASIA_REIT_LOCAL.csv
  10        AQR QMJ / BAB / HML-Devil daily (xlsx)  → raw_eo/AQR_*.xlsx
รัน: cd "/Users/doyinratnavardhana/Fama French/Fund Style Dashboard" && ./.venv/bin/python .claude/factor_team/data/external/fetch_eo.py [กลุ่ม ...]
"""
from __future__ import annotations

import hashlib
import os
import sys

import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fetch_external import OUT, fred, save, yahoo  # noqa: E402

RAW = os.path.join(OUT, "raw_eo")
KF = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/{}_CSV.zip"
JKP = "https://jkpfactors-data.s3.amazonaws.com/public/%5B{}%5D_%5Ball_themes%5D_%5Bdaily%5D_%5Bvw_cap%5D.zip"
AQR = "https://www.aqr.com/-/media/AQR/Documents/Insights/Data-Sets/{}.xlsx"
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}

KF_FILES = {
    "kf_daily": ["Developed_5_Factors_Daily", "Developed_Mom_Factor_Daily"],
    "kf_monthly": ["Developed_5_Factors", "Developed_Mom_Factor", "Emerging_5_Factors", "Emerging_MOM_Factor"],
    "kf_regional": ["North_America_5_Factors_Daily", "Europe_5_Factors_Daily", "Japan_5_Factors_Daily",
                    "North_America_Mom_Factor_Daily", "Europe_Mom_Factor_Daily", "Japan_Mom_Factor_Daily"],
}
AQR_FILES = ["Quality-Minus-Junk-Factors-Daily", "Betting-Against-Beta-Equity-Factors-Daily",
             "The-Devil-in-HMLs-Details-Factors-Daily"]


def fetch_raw(url: str, name: str) -> None:
    r = requests.get(url, headers=UA, timeout=300)
    r.raise_for_status()
    path = os.path.join(RAW, name)
    with open(path, "wb") as fh:
        fh.write(r.content)
    sha = hashlib.sha256(r.content).hexdigest()
    print(f"{name}: size={len(r.content):,}B sha256={sha[:12]} url={url}")


def kf(group: str) -> None:
    for f in KF_FILES[group]:
        fetch_raw(KF.format(f), f"KF_{f}_CSV.zip")


if __name__ == "__main__":
    os.makedirs(RAW, exist_ok=True)
    only = set(sys.argv[1:])
    jobs = {
        "kf_daily": lambda: kf("kf_daily"),
        "jkp_em": lambda: fetch_raw(JKP.format("emerging"), "JKP_EMERGING_THEMES_DAILY.zip"),
        "alt": lambda: save(yahoo(["GLD", "VNQ", "VNQI"], adjusted=True), "EO_ALT_ETF.csv"),
        "kf_monthly": lambda: kf("kf_monthly"),
        "kf_regional": lambda: kf("kf_regional"),
        "fred": lambda: save(fred(["DTWEXBGS", "DTWEXEMEGS", "DFII10"]), "US_DOLLAR_REALRATE_FRED.csv"),
        "asia_reit": lambda: save(yahoo(["1343.T", "CLR.SI", "JPYTHB=X", "SGDTHB=X"], adjusted=True), "ASIA_REIT_LOCAL.csv"),
        "jkp_dev": lambda: fetch_raw(JKP.format("developed"), "JKP_DEVELOPED_THEMES_DAILY.zip"),
        "aqr": lambda: [fetch_raw(AQR.format(f), f"AQR_{f}.xlsx") for f in AQR_FILES],
    }
    for k, fn in jobs.items():
        if not only or k in only:
            fn()
