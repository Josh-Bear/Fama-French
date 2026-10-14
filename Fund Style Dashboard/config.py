"""config.py — MSCI Fund Country/Sector Classification Dashboard.

ค่าคงที่ทั้งหมดของโปรเจกต์รวมไว้ที่เดียว (single source ฝั่งโค้ด)
สเปก/เหตุผลเชิงลึก: ดู MSCI_DASHBOARD_PLAN.md

โปรเจกต์นี้แยกจาก Fama French SET50 โดยสมบูรณ์ (คนละโฟลเดอร์ คนละแอป)
data/ module ทุกตัวอ่านไฟล์ดิบจาก base_data/ (ไม่ hardcode path เดิมของ Downloads/MSCI ที่ถูกลบไปแล้ว)
"""

from __future__ import annotations

import os

# --- Paths ---
# ทุก path อ้างอิงจากตำแหน่งไฟล์ config.py นี้ -> ย้ายทั้งโฟลเดอร์ได้โดยไม่พัง
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DATA_DIR = os.path.join(BASE_DIR, "base_data")
CACHE_DIR = os.path.join(BASE_DIR, "cache")  # derived cache (return series, match result) — regenerate ได้

FUND_PROFILE_CSV = os.path.join(BASE_DATA_DIR, "FundProfile.csv")
NAV_HISTORY_CSV = os.path.join(BASE_DATA_DIR, "nav_history_db.csv")   # ~321MB -> อ่านแบบ chunked/usecols เสมอ
MSCI_COUNTRY_CSV = os.path.join(BASE_DATA_DIR, "MSCI_COUNTRY_ETF.csv")  # 18 index, THB terms แล้ว
MSCI_SECTOR_CSV = os.path.join(BASE_DATA_DIR, "MSCI_SECTOR_ETF.csv")    # 10 index, THB terms แล้ว
SEC_FUND_FEE_CSV = os.path.join(BASE_DATA_DIR, "SecFundFee.csv")
TOP_HOLDING_CSV = os.path.join(BASE_DATA_DIR, "TopHolding.csv")

# --- Fund filter criteria (Section 0 v2 -> คาดว่าเหลือ 715 กอง: E=600, F=77, O=38) ---
# key = ชื่อคอลัมน์เป๊ะใน FundProfile.csv (อ่านด้วย encoding='utf-8-sig' เพื่อตัด BOM)
FILTER_EQ = {                     # ต้องเท่ากับค่านี้
    "Project Retail Type": "R",
    "buy period flag": "N",
    "sell period flag": "N",
    "switch_in flag": "Y",
    "switch_out flag": "Y",
    "FIF Flag": "Y",
}
FILTER_NEQ = {                    # ต้องไม่เท่ากับค่านี้
    "Fund Policy": "M",           # ไม่เอา money market
    "Plain / Complex Fund": "C",  # ไม่เอา complex fund
}
FILTER_EMPTY = ["Tax Type"]       # ต้องเป็นค่าว่าง

FUND_CODE_COL = "Fund Code"
FUND_POLICY_COL = "Fund Policy"   # E=equity, F=fixed income, O=other
# ทั้งแอปใช้เฉพาะกองหุ้น (ผู้ใช้ตัดสินใจ 2026-09-29) — กรองตั้งแต่ build_pipeline
# กอง F/O ไม่มี fixed-income factor ให้ใช้ (R² country เฉลี่ย 0.15/0.17) และไม่มีความหมายกับ style/macro/score
APP_POLICY = "E"

EXPECTED_FILTERED_FUNDS = 715     # sanity check Phase 1 (E=600, F=77, O=38)
EXPECTED_WITH_NAV = 680           # หลัง join กับ nav_history_db
EXPECTED_PASS_THRESHOLD = 368     # หลังตัด threshold จำนวนจุดข้อมูล (นับด้วย NAVDate) — ทุก policy
EXPECTED_PASS_THRESHOLD_E = 313   # เฉพาะ APP_POLICY ที่ผ่าน threshold จุดข้อมูล (ก่อนตัดกอง NAV เก่า/เลิกกอง -> 209 ใน pipeline)
EXPECTED_FILTERED_FUNDS_E = 600   # กองผ่านเกณฑ์ fund_profile เฉพาะ APP_POLICY (ตัวหารของ "ครอบคลุม" ในหน้าแรก)

# --- NAV history (nav_history_db.csv) ---
NAV_COL = "NAV"
NAV_FUND_CODE_COL = "FundCode"    # ในไฟล์ nav ใช้ "FundCode" (ไม่มีเว้นวรรค) ต่างจาก FundProfile ("Fund Code")
NAV_DATE_COL = "NAVDate"          # วันที่หลักในการ join (สะท้อนราคาจริง — แก้ปัญหา NAV lag, ดูแผน Phase 2)
NAV_ASOF_COL = "AsOfDate"         # วันที่ระบบบันทึก/เผยแพร่
NAV_UPDATE_COL = "UpdateTime"     # timestamp อัปเดตจริง — ใช้ tie-break เมื่อ NAVDate ซ้ำ
NAV_AUM_COL = "AUM"               # ใช้เป็นขนาดจุดบน scatter
# เมื่อ (FundCode, NAVDate) ซ้ำกัน -> เก็บแถวที่ UpdateTime ล่าสุด (confirmed 2026-09-01)
NAV_DEDUP_KEEP = "UpdateTime"
# AsOfDate ไม่อยู่ใน usecols (ไม่ได้ใช้ — dedup tie-break ใช้ UpdateTime) เพื่อลด parse ไฟล์ 336MB
NAV_USECOLS = [NAV_FUND_CODE_COL, NAV_COL, NAV_DATE_COL, NAV_UPDATE_COL, NAV_AUM_COL]
NAV_CHUNKSIZE = 500_000           # อ่านทีละ chunk แล้ว filter เฉพาะ fund ที่สนใจ ลด memory

# --- Data cleaning: ความสดของ NAV + รูข้อมูล (ตกลงกับผู้ใช้ 2026-09-30 · ดู docs/appendix/data-sources.md) ---
# ไฟล์ NAV มีรูใหญ่ที่เกิดพร้อมกันหลายร้อยกอง (7 ม.ค. -> พ.ค./มิ.ย. 2026 และ 27 ม.ค. -> 22 มี.ค. 2021) + กองที่หยุดรายงาน
# NAV ล่าสุดช้ากว่าวันล่าสุดของดัชนี MSCI เกินกี่วัน (ปฏิทิน) ถึงตัดกองออกจากทั้งแอป · กองเลิกแล้ว (มีแถว NAV ≤ 0
# ต่อท้าย เช่น PRINCIPAL GEF-X) ตัดเสมอ — dry run 2026-09-30: 313 -> 209 กอง (NAV เก่า 102 · เลิกกอง 2)
NAV_STALE_MAX_DAYS = 90
# return ที่คร่อมรูข้อมูล: NAV 2 จุดติดกันห่างกันเกินกี่ "วันทำการของดัชนีที่หายไป" ถึงไม่ใช้ return ช่วงนั้น
# (ทั้งฝั่งกองและดัชนี) — ปกติขาดทีละ 1-7 วัน · รูสั้นสุดที่เจอจริง 12 วัน -> 10 แยกสองกลุ่มได้สะอาด (159 กอง · 340 จุด)
NAV_MAX_GAP_BDAYS = 10
# NAV ที่ clean แล้วของกอง APP_POLICY (เขียนโดย build_pipeline) — ขั้นอื่น (style/macro/score/risk model) อ่านจากที่นี่
# แทนการสแกนไฟล์ดิบ 336MB ซ้ำ · มีคอลัมน์ status (keep / closed / stale / few_points) และ spike_fixed ให้ตรวจย้อนได้
NAV_CLEAN_PARQUET = os.path.join(CACHE_DIR, "nav_clean.parquet")
# กลุ่ม share class ของกองเดียวกัน (-A/-D/-H/-SSF …) — แก้ด้วยมือได้ · หน้า 8 เลือกได้ไม่เกิน 1 class ต่อกลุ่ม
SHARE_CLASS_CSV = os.path.join(BASE_DATA_DIR, "share_class_groups.csv")

# --- MSCI index columns ---
MSCI_DATE_COL = "Date"
MSCI_COUNTRY_COLS = [
    "MSCI_ASIA_EX_JAPAN", "MSCI_BRAZIL", "MSCI_CHINA_A_SHARES", "MSCI_CHINA_H_SHARES",
    "MSCI_CHINA_ALL_SHARES", "MSCI_EM", "MSCI_EUROPE", "MSCI_INDIA", "MSCI_JAPAN",
    "MSCI_KOREA", "MSCI_ASEAN", "MSCI_TAIWAN", "MSCI_USA", "MSCI_VIETNAM",
    "MSCI_ACWI", "MSCI_WORLD", "MSCI_WORLD_EX_US", "MSCI_ACWI_EX_US",
]  # 18 — หมายเหตุ: ไม่มี index ประเทศไทยตรงๆ (ใกล้สุด = ASEAN)
MSCI_SECTOR_COLS = [
    "MSCI_ACWI_CD", "MSCI_ACWI_CS", "MSCI_ACWI_EN", "MSCI_ACWI_FN", "MSCI_ACWI_HC",
    "MSCI_ACWI_IN", "MSCI_ACWI_IT", "MSCI_ACWI_MT", "MSCI_ACWI_TC", "MSCI_ACWI_UT",
]  # 10 (CD=consumer disc, CS=consumer staples, EN=energy, FN=financials, HC=health care,
   #     IN=industrials, IT=info tech, MT=materials, TC=comm services, UT=utilities)

# --- Return series construction (Phase 2) ---
DATA_START = "2021-01-01"          # ช่วงข้อมูล MSCI (ถึง ~2026-07 ตามไฟล์)
MIN_DATA_POINTS = 600              # ตัดกองที่มีจุดข้อมูล NAV (นับด้วย NAVDate หลัง dedupe) ไม่เกินเกณฑ์นี้ (> 600)
MIN_REGRESSION_OBS = 30            # กองที่มี return "ในช่วง MSCI" น้อยกว่านี้ -> ข้าม (กัน ElasticNetCV crash/ผลมั่ว)
WINSOR_LOWER = 0.01                # winsorize return แยกทีละ series ที่ 1st–99th percentile
WINSOR_UPPER = 0.99

# --- Metrics (Phase 4) ---
TRADING_DAYS = 252                 # annualize ด้วย 252 วันทำการ (convention เดียวกับ Fama French SET50)
DAYS_PER_YEAR = 365.25             # annualize NAV กอง (รายงานไม่ครบทุกวัน) ด้วยวันปฏิทินจริง แทน 252/n

# --- Regression / matching (Phase 3) ---
# multi-factor: regress return กอง กับ MSCI index ทั้งชุด (18 หรือ 10) พร้อมกัน + StandardScaler
# primary = |standardized coef| มากสุด, secondary = อันดับ 2, ที่เหลือ non-zero = "อื่นๆ"
MATCH_PRIMARY_MODEL = "ElasticNetCV"   # หลัก; รัน Lasso/Ridge เก็บเทียบด้วย

# --- Dashboard (Phase 5) ---
# Chart 1-2 scatter: x=annualized return, y=annualized volatility, size=AUM, สี=4 quadrant
# เส้นแบ่ง: return=0 (แนวตั้ง), volatility=median ของกองทั้งหมดในกราฟ (แนวนอน)
QUADRANT_VOL_SPLIT = "median"
# Chart 3 (แยกหน้า pages/3): bar chart ต่อกอง, แกน y = standardized coefficient (ElasticNet),
#   primary=น้ำเงิน / secondary=เขียว / อื่นๆ=เทา (confirmed 2026-09-01)
CHART3_Y_METRIC = "standardized_coefficient"

# --- Match Strength (หน้า 3) — secondary แบบ band-based (แทน rank-based เดิม) ---
# secondary = ทุก index (นอกจาก primary) ที่ |coef| >= |primary coef| × (1 − SECONDARY_BAND_PCT)
# -> กองที่มี exposure หลายตัวใกล้เคียงกันจะได้ secondary หลายตัว ไม่ใช่ตายตัวแค่ 1
# X=0.30 เลือกจากการกระจายตัวจริงใน cache/coefs.csv (368 กอง × 2 scope, 2026-09-09):
#   10%->0.11 sec/กอง, 20%->0.26, [30%->0.48, 9.0% ของกองได้ >=2], 50%->1.13, 70%->2.36 (ระเบิดเกินไป)
SECONDARY_BAND_PCT = 0.30

# --- Vol Forecast (หน้า 4) — EWMA + GARCH(1,1), walk-forward (ดู VOL_FORECAST_PLAN.md §0.1) ---
VOL_FORECAST_HORIZON = 21       # trading days ข้างหน้า (~1 เดือน) ที่ทำนาย
VOL_FORECAST_MIN_TRAIN = 252    # ~1 ปี ขั้นต่ำก่อนเริ่ม forecast แรก (GARCH ต้องการข้อมูลพอ)
VOL_FORECAST_STEP = 21          # เลื่อน window ทีละเท่าไหร่ (=horizon -> non-overlap ~55 window; ลดเป็น 5 = overlap)
EWMA_LAMBDA = 0.94              # RiskMetrics convention
GARCH_DIST = "t"                # distribution ของ GARCH — Student-t (fat tail) แทน Normal (2026-09-09)

# --- Filtered Scatter (หน้า 5) ---
# หน้าต่างของ "return ที่ผ่านมาแล้ว" — ตั้งเท่า VOL_FORECAST_HORIZON โดยตั้งใจ (แกน x = อดีต, แกน y = อนาคต)
# แยกชื่อกันเพราะความหมายคนละอัน
RECENT_RETURN_WINDOW = 21

# --- Data cleaning: NAV spike detection (data/nav_loader.py) ---
# ปัญหา: บางกอง NAV กระโดดขึ้น/ลงผิดปกติวันเดียวแล้ว "เด้งกลับ" เกือบจุดเดิมในวันถัดไป (เช่น KKP SEMICON-H
# 2026-06-16) — ยืนยันแล้วว่าเป็น data error ไม่ใช่ bubble จริง (กองกระจายความเสี่ยงขนาดนี้ขยับวันเดียว
# หลักสิบ-ร้อย% ไม่ได้จริง + ไม่มีกองอื่น/index อ้างอิงขยับพร้อมกัน + snap-back กลับเทรนด์เดิมสนิท)
# วิธีตรวจ (Hampel-filter-style): ที่จุด i ใดๆ ให้ r_in = log-return ขาเข้า (i-1->i), r_out = ขาออก (i->i+1)
# ใช้ median/MAD (median absolute deviation ×1.4826 = robust std) จาก log-return ใกล้เคียง (NAV_SPIKE_WINDOW
# จุด) เป็น baseline ปกติของกองนั้น ๆ ช่วงนั้น ๆ -> ตัด (fix) เฉพาะจุดที่เข้าเงื่อนไขครบทั้ง 3:
#   1) |r_in - median| > NAV_SPIKE_K × mad  และ  |r_out - median| > NAV_SPIKE_K × mad  (ทั้ง 2 ขาสุดโต่งมาก)
#   2) r_in × r_out < 0  (สัญญาณตรงข้ามกัน = ไป-กลับ ไม่ใช่ trend จริง)
#   3) |(r_in + r_out) - 2×median| < NAV_SPIKE_ROUNDTRIP_K × mad  (รวม 2 ขาแล้วกลับสู่ปกติ ไม่ทิ้ง shift ค้าง)
# แก้ด้วย geometric interpolation: nav[i] = sqrt(nav[i-1] × nav[i+1]) (log-linear ระหว่าง 2 จุดข้างเคียง)
NAV_SPIKE_K = 8.0                  # จำนวนเท่าของ mad ที่ทั้ง 2 ขาต้องเกินเพื่อถือว่า "สุดโต่งผิดปกติ"
NAV_SPIKE_ROUNDTRIP_K = 3.0        # จำนวนเท่าของ mad ที่ผลรวม 2 ขายอมให้เบี่ยงจาก median ได้ (คุมว่า "กลับสู่ปกติจริง")
NAV_SPIKE_WINDOW = 20              # จำนวนจุด log-return ใกล้เคียงที่ใช้คำนวณ median/mad (baseline เฉพาะที่)

# --- Metrics: return_21d gap threshold (analysis/metrics.py::recent_return) ---
# กองที่รายงาน NAV ไม่ครบทุกวันทำการ อาจได้ 22 observation ล่าสุดที่กระจายข้ามช่วงเวลายาวเกินจริง
# (เช่น ES-INDONESIA กระจาย 152 วัน) ทำให้ "return 21 วันทำการ" ที่โชว์จริง ๆ ครอบคลุมหลายเดือน คลาดเคลื่อนสูง
# ตรวจสอบ empirical กับข้อมูลจริง (368 กอง) พบ distribution ของ gap วันปฏิทินของ 22 จุดล่าสุด แบบ bimodal ชัดเจน:
#   cluster ปกติ 30-45 วัน (~55% ของกอง) · เกือบว่าง 45-150 วัน (~3%) · cluster ห่างจริง 150-398 วัน (~41%)
#   และมี spike คมชัดที่ "พอดี 42 วัน" (~76-80 กอง) ตรงกับ pattern "รายงาน NAV ทุกวันทำการเว้นวัน" (ปกติ ไม่ใช่ error)
# เกณฑ์เดิม 42 วัน ตรง cluster นี้ — ปรับเป็น 60 วัน ตามที่ผู้ใช้ขอ (2026-09-09) ยังอยู่ในช่วง valley
# เกือบว่าง (45-150 วัน) เดียวกัน ผลกระทบ (~% กองที่ถูกตัดเป็น NaN) ใกล้เคียงกับ 42 วันมาก (ตรวจไว้ก่อนหน้าแล้ว)
RECENT_RETURN_MAX_GAP_DAYS = 60

# --- Style Factor Match (หน้า 6) — ดู docs/pages/6-style-match.md ---
# ที่มา: iShares MSCI factor ETF (yfinance, USD) snapshot ลง base_data ครั้งเดียว แล้ว pipeline อ่าน offline
STYLE_FACTOR_CSV = os.path.join(BASE_DATA_DIR, "STYLE_FACTOR_ETF.csv")   # สร้างด้วย `data_access.py style-download`
STYLE_SNAPSHOT_START = "2020-11-01"                  # เผื่อก่อน 2021 ให้มี return วันแรกของช่วง MSCI
STYLE_TICKERS = {                                    # factor -> (ETF US, ETF Intl) · None = ETF global เดี่ยว ไม่ต้อง blend
    "Momentum": ("MTUM", "IMTM"),
    "Quality": ("QUAL", "IQLT"),
    "Value": ("VLUE", "IVLU"),
    "LowVol": ("ACWV", None),
}
STYLE_FACTOR_COLS = list(STYLE_TICKERS)          # ลำดับเดียวกับ STYLE_TICKERS (single source — ไม่ต้องแก้สองที่)
STYLE_BENCHMARK_TICKER = "ACWI"     # de-market ด้วย ACWI ETF (USD) -> USD÷USD ค่าเงินหักล้างพอดี
# สัดส่วน US ใน blend — ต้อง ≈ สัดส่วน US ใน ACWI ไม่งั้นทุก factor มี (US−Intl) ปนเท่ากัน
# gate 2026-09-15: sweep 0.40-0.80 แล้ว corr กับ MSCI_USA÷MSCI_ACWI ต่ำสุดที่ 0.60 (|corr| เฉลี่ย 0.106)
STYLE_US_WEIGHT = 0.60
# ตัวแปรควบคุม (ไม่นับเป็น style) — ดูดผลที่ไม่ใช่ style ออกจาก 4 factor:
#   MSCI_ACWI  ตลาดโลกใน "โลก MSCI" (THB, ราคาปิดท้องถิ่น — ตรงกับ NAV กอง)
#   US_VS_ACWI "US ชนะโลก" (MSCI_USA÷MSCI_ACWI, THB÷THB)
#   ACWI_ETF   ตลาดโลกใน "โลก ETF" (USD, ปิดที่ NY — ตรงกับ style factor)
# ที่มา (gate/sanity 2026-09-15):
#   ไม่มี US_VS_ACWI -> Value/LowVol relative สัมพันธ์กับ US ชนะโลก −0.26/−0.43
#   ไม่มี ACWI_ETF   -> สองโลก corr กันแค่ 0.78 แล้ว LowVol (corr −0.79 กับตลาดฝั่ง ETF) เข้าไปอุดช่องว่าง
#                      -> "High-Beta" 236/313 กอง, partial market beta (โมเดลเต็ม) 0.57 · ใส่แล้ว -> 92/313, 0.88, defensive->Low-Vol 26/32
STYLE_CONTROL_COLS = ["MSCI_ACWI", "US_VS_ACWI", "ACWI_ETF"]
# mkt_beta ของกอง = ผลรวม coef ตลาดทั้งสองโลก **จากโมเดลที่มีแค่ control** (ไม่ใช่โมเดลเต็ม — style relative มีขาตลาดในตัว)
STYLE_MARKET_COLS = ["MSCI_ACWI", "ACWI_ETF"]     # ต้องเป็น subset ของ STYLE_CONTROL_COLS (มี test คุม)
STYLE_POLICY = APP_POLICY           # style factor มีความหมายเฉพาะกองหุ้น (= ทั้งแอปแล้ว)
# calibrate 2026-09-15 (313 กอง, 4 factor): band 20% -> ไม่มี sec 75.4% / มี>=2 1.0% · **30% -> 63.6% / 7.3%**
#   · 40% -> 52.1% / 13.4% · 50% -> 38.7% / 23.0% — 30% ให้พฤติกรรมใกล้ country (64.1% / 9.8%) และ sector (63.3% / 9.0%) จึงใช้ค่าเดิม
STYLE_SECONDARY_BAND_PCT = 0.30
STYLE_LABELS = {                    # factor -> (ชื่อเมื่อ coef บวก, ชื่อเมื่อ coef ลบ) — style ต้องดูเครื่องหมายด้วย
    "Momentum": ("Momentum", "Contrarian"),
    "Quality": ("Quality", "Junk"),
    "Value": ("Value", "Growth"),         # Value ติดลบ = กอง growth (ถ้าใช้ |coef| จะถูกเรียก Value ผิดๆ)
    "LowVol": ("Low-Vol", "High-Beta"),
}

# --- Macro Chain (หน้า 7) — ดู docs/pages/7-macro-chain.md ---
# ที่มา: yfinance 6 ตัว + FRED DGS10 -> snapshot ลง base_data ครั้งเดียว แล้ว pipeline อ่าน offline (เหมือน style)
MACRO_FACTOR_CSV = os.path.join(BASE_DATA_DIR, "MACRO_FACTOR.csv")   # สร้างด้วย `data_access.py macro-download`
MACRO_SNAPSHOT_START = "2020-11-01"                  # เผื่อก่อนช่วง MSCI (2021-01)
MACRO_YF_TICKERS = {                                 # factor -> ticker yfinance
    "Oil_Brent": "BZ=F",       # USD/barrel (futures ต่อเนื่อง — มี roll gap)
    "Gold": "GC=F",            # USD/oz
    "USDTHB": "THB=X",         # บาทต่อ USD (ขึ้น = บาทอ่อน)
    "Copper": "HG=F",          # USD/lb — global industrial demand / China proxy
    "DXY": "DX-Y.NYB",         # Dollar Index เทียบตะกร้า 6 สกุล
    "VIX": "^VIX",
}
MACRO_DXY_FALLBACK = "DX=F"                          # DX-Y.NYB บางช่วง yfinance ไม่คืนข้อมูล
MACRO_FRED_SERIES = {"US10Y": "DGS10"}               # % yield — ดึง CSV ตรง (pandas_datareader ชนกับ pandas ใหม่)
MACRO_FRED_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={series}&cosd={start}"
# การแปลงรายเดือน (month-end): ราคาสินทรัพย์ -> % return · index/yield ที่ mean-revert -> ผลต่างระดับ (Δ)
MACRO_RETURN_COLS = ["Oil_Brent", "Gold", "USDTHB", "Copper", "DXY"]
MACRO_DELTA_UNITS = {"VIX": "จุด", "US10Y": "pp"}    # หน่วยของ Δ (ใช้บอกขนาด 1 SD บนกราฟ)
MACRO_DELTA_COLS = list(MACRO_DELTA_UNITS)
MACRO_FACTOR_COLS = MACRO_RETURN_COLS + MACRO_DELTA_COLS
# direct regression ต่อกอง (7 factor + intercept) ต้องมีอย่างน้อยเท่านี้เดือน — กอง E ผ่าน 309/313 (2026-09-15)
MACRO_MIN_MONTHS = 36
# หน้า 7 ใช้เฉพาะกองหุ้น (ผู้ใช้ตัดสินใจ 2026-09-15 — กรองตั้งแต่ pipeline เหมือนหน้า 6)
# implied มองผ่าน index หุ้น จึงมองไม่เห็นความไวของบอนด์/ทองในกอง F/O · ◆ บนกราฟ = median ของกองกลุ่มนี้
MACRO_POLICY = APP_POLICY

# --- Score Screening (หน้า 8) — ดู docs/pages/8-score-screen.md ---
SCORE_POLICY = APP_POLICY           # เฉพาะกองหุ้น (= ทั้งแอปแล้ว)
SCORE_RETURN_WINDOW = 252           # ความยาวสัญญาณ momentum (12 เดือน — มาตรฐาน Carhart)
# ข้ามเดือนล่าสุด (Jegadeesh-Titman 12-1) -> สัญญาณจริงคือ t−252 ถึง t−21 = 11 เดือน
# backtest 55 รอบ × 28 ดัชนี (2026-09-29): IC ของคะแนนโซนต่อ return 63 วันข้างหน้า 0.016 -> 0.036 เมื่อ skip
# (short-term reversal: เดือนล่าสุดมักกลับทิศ) · หน้า 5 ยังใช้ return 21 วันของมันเองไม่กระทบ
SCORE_RETURN_SKIP = 21
# ชื่อคอลัมน์ใน index snapshot — ประกาศที่เดียว ใช้ทั้ง data_access และ analysis/screening
SCORE_RETURN_COL = f"return_{SCORE_RETURN_WINDOW}d_skip{SCORE_RETURN_SKIP}"
# realized vol ช่วงเดียวกับ momentum (231 return รายวัน t−252..t−21, ×√252) — ตัวหารของคะแนนโซนสูตรใหม่ (§12.14)
SCORE_VOL_COL = f"vol_{SCORE_RETURN_WINDOW}d_skip{SCORE_RETURN_SKIP}"
# วิธีคิดคะแนนโซน (§12.14 · ตัดสินใจ 2026-09-30):
#   "ret_over_realized_vol" = percentile(return 12-1 ÷ realized vol ช่วงเดียวกัน)   <- ใช้จริง
#   "rank_x_rank_garch"     = percentile(return 12-1) × percentile กลับด้าน(GARCH 21 วัน)   <- สูตรเดิม เก็บไว้ A/B 1 รอบแล้วถอด
# dry run 55 รอบ: IC ต่อ return กองจริง 63 วัน 0.104 -> 0.132 · สูตรเดิมเอียงไปหาตลาด vol ต่ำจน IC country ติดลบ
SCORE_ZONE_METHOD = "ret_over_realized_vol"
# percentile ของ scope ถูก rescale เป็นช่วง (0.01, 0.99) — กันค่าอันดับสุดท้าย/แรกสุดชนขอบ 0 แล้วคูณกันได้ 0 ทั้งแถว
SCORE_PCT_LO = 0.01
SCORE_PCT_HI = 0.99
SCORE_MATRIX_SCALE = 100            # country_score × sector_score × 100 ให้อ่านง่าย
SCORE_TOP_N = 20                    # จำนวนแถวในตารางหน้า 8 (กองที่ผ่านเกณฑ์ขึ้นก่อน แล้วเติมด้วยคะแนนถัดไป)
# เกณฑ์ขั้นต่ำของ score (ของคู่ที่ใช้จริง) ถึงจะนับว่า "ผ่านเกณฑ์" เข้า Top ของส่วนที่ 2/3 (กำหนด 2026-09-29)
# score = percentile ภายใน universe ที่เลือก -> เป็นเกณฑ์สัมบูรณ์ในสเกลนั้น · กองต่ำกว่านี้ไม่ถูกเลือก แม้โซนของมันยังไม่ถูกใครใช้
# §12.14 สเกลใหม่ใหญ่ขึ้น (cell สูงสุด ~98 เทียบเดิม ~18) -> 0.7 กรองน้อยลง (~74-93% ผ่าน) แต่ผู้ใช้เลือกคงไว้ (2026-09-30):
# dry run พอร์ต Top 5 ชนะค่าเฉลี่ยกอง +2.4%/63 วัน (เทียบ 2.75 ที่จับคู่สัดส่วนเดิม +1.9%) และโหมดเริ่มต้นได้ 5 กอง
SCORE_MIN_ELIGIBLE = 0.7
# country ชุด VIF-cleaned (backward elimination จนทุกตัว VIF < 5 · condition number 492 -> 3.5, 2026-09-22)
# ตัดออก 7 ตัวที่เป็น aggregate/regional composite: WORLD, ACWI_EX_US, ACWI, ASIA_EX_JAPAN, WORLD_EX_US, EM, CHINA_ALL_SHARES
# hardcode ไว้ (ไม่รัน VIF ตอน build) -> ผลคงที่ reproduce ได้ · มี test ยืนยันว่าชุดนี้ยัง VIF < 5 กับข้อมูลปัจจุบัน
SCORE_COUNTRY_CLEAN = [
    "MSCI_BRAZIL", "MSCI_CHINA_A_SHARES", "MSCI_CHINA_H_SHARES", "MSCI_EUROPE", "MSCI_INDIA",
    "MSCI_JAPAN", "MSCI_KOREA", "MSCI_ASEAN", "MSCI_TAIWAN", "MSCI_USA", "MSCI_VIETNAM",
]
SCORE_VIF_MAX = 5.0                 # เกณฑ์ที่ใช้ตอนเลือกชุดข้างบน (ใช้ใน test)
# secondary (country/sector) ต้องอยู่ในช่วง [primary_coef × (1 − pct), primary_coef] จึงจะใช้เป็น fallback
# ตอนกระจายความเสี่ยงได้ (ทิศทางเดียวกับ primary + แรงอย่างน้อย 70% ของ primary) — เช็คแบบมีเครื่องหมาย (signed)
# ไม่ใช่ |coef| แบบ SECONDARY_BAND_PCT ของหน้า 5/6 (ซึ่งไม่สนทิศทาง) · แยกตัวแปรเฉพาะหน้า 8 ตามที่ตกลง (2026-09-29)
SCORE_SECONDARY_BAND_PCT = 0.30
# ชื่อเต็มของ sector (GICS — ไม่มี Real Estate ในชุด MSCI ACWI ที่ใช้) สำหรับ label หน้า 8
SECTOR_FULL_NAMES = {
    "MSCI_ACWI_CD": "Consumer Discretionary", "MSCI_ACWI_CS": "Consumer Staples",
    "MSCI_ACWI_EN": "Energy", "MSCI_ACWI_FN": "Financials", "MSCI_ACWI_HC": "Health Care",
    "MSCI_ACWI_IN": "Industrials", "MSCI_ACWI_IT": "Information Technology",
    "MSCI_ACWI_MT": "Materials", "MSCI_ACWI_TC": "Communication Services",
    "MSCI_ACWI_UT": "Utilities",
}

# --- Portfolio / Efficient Frontier (หน้า 8 ส่วนที่ 3) — ดู docs/pages/8-score-screen.md ---
PORTFOLIO_TOP_N = 5                 # จำนวนกองที่ส่งเข้า frontier (เอาเฉพาะกองที่ผ่านเกณฑ์กระจายความเสี่ยง)
PORTFOLIO_MIN_FUNDS = 3             # น้อยกว่านี้ไม่คำนวณ (max_w × 2 = 80% < 100% -> ไม่มี combination ที่เป็นไปได้)
PORTFOLIO_LOOKBACK_DAYS = 756       # rolling 3 ปี (252×3) สำหรับ B/Σ/vol — สะท้อน regime ปัจจุบัน (ตัดสินใจ 2026-09-29)
# γ คงที่ตามมาตรฐานสากล (constant relative risk aversion) — ไม่คำนวณจากตลาด/r_f
# เพราะ γ ที่ถอดจาก realized market return ช่วงสั้นพลิกเครื่องหมายได้ (ปีที่ตลาดติดลบ -> Π ติดลบทั้งกระดาน)
PORTFOLIO_GAMMA = 2.5
# น้ำหนักตลาดของ Black-Litterman = สัดส่วน AUM ของกองที่คัดมา · cap ไม่ให้กองเดียวเกินครึ่ง แล้วเกลี่ยส่วนเกิน
# ให้กองที่เหลือเท่าๆ กัน วนซ้ำจนทุกกอง ≤ cap
PORTFOLIO_MARKET_CAP_W = 0.50
# น้ำหนักอ้างอิงของ Π: "equal" = 1/N (ค่าเริ่มต้น) | "aum" = สัดส่วน AUM (cap ด้วย PORTFOLIO_MARKET_CAP_W)
# เหตุที่ไม่ใช้ AUM: BL สมมติว่าน้ำหนักอ้างอิง = พอร์ตตลาดที่ทุกคนถือ (ใช้ได้กับหุ้น/market cap) แต่ 5 กองนี้ถูกคัดมาเอง
# AUM จึงสะท้อนอายุ/การขาย ไม่ใช่ฉันทามติเรื่องความเสี่ยง-ผลตอบแทน — เคส TCHTECH-A AUM 73% ทำให้ Π 93% มาจากตัวมันเอง (2026-09-29)
PORTFOLIO_REF_WEIGHT = "equal"
# กริดน้ำหนักพอร์ต (จำนวนเต็ม % ตรงกับที่ซื้อขายจริง) — enumerate ทุก combination ที่รวมได้ 100%
PORTFOLIO_MIN_W = 0.05
PORTFOLIO_MAX_W = 0.40
PORTFOLIO_STEP_W = 0.01
PORTFOLIO_MAX_COMBOS = 5_000_000    # กันผู้ใช้ตั้งค่าจนกริดระเบิด (เตือนแทนการรันค้าง)
PORTFOLIO_STEP_CHOICES = [1, 2, 4, 5, 10, 20, 25]   # step (%) ที่หาร 100 ลงตัว — ตัวเลือกใน UI
# กลุ่มเมฆบนกราฟสุ่มแสดงไม่เกินเท่านี้ (5 กอง = 885,801 จุด ≈ figure 24MB ส่งใหม่ทุกครั้งที่ขยับ slider)
# ใช้แค่วาด — frontier/max Sharpe คำนวณจากทุกชุดเสมอ
PORTFOLIO_CLOUD_MAX_POINTS = 50_000

# --- TF Portfolio (หน้า 9) — โมเดล M004-TF-FX ที่ผ่าน walk-forward backtest ของทีม quant (ดู docs/pages/9-tf-portfolio.md) ---
# ค่าทั้งหมดมาจากสเปกที่ลงทะเบียนไว้ (M002–M005 C2–C10 · M006 §2 · M007 §4 · COST_real_fees) — ห้ามปรับเพื่อให้ผลดีขึ้น
TF_MODEL_ID = "M004-TF-FX"
TF_N_FUNDS = 8                      # จำนวนกองที่ถือ
TF_HYSTERESIS_K = 16                # กองที่ถืออยู่ถือต่อได้ถ้ายังติดอันดับ ≤ K
TF_MIN_FUNDS = 4                    # คัดได้น้อยกว่านี้ -> ถือแบบ B0 (ทุกกองเท่ากัน 1 class/กลุ่ม)
TF_WEIGHT_CAP = 0.25                # เพดานน้ำหนักต่อกอง (หลัง ERC)
TF_RF_SIGNAL = 0.02                 # rf ที่หักใน SR12 = (R12-1 − rf×11/12) ÷ vol52
TF_FRESH_DAYS = 10                  # NAV ล่าสุดต้องห่างจาก t ไม่เกินนี้ (วันปฏิทิน) ถึงจะคัดได้
TF_MIN_HISTORY = 252                # ต้องมี NAVDate ≥ เท่านี้ตั้งแต่ 2021-01-01
TF_HISTORY_START = "2021-01-01"
TF_SIGNAL_WEEKS = 53                # จุดราคารายสัปดาห์ (= 52 return) สำหรับ vol52 / covariance
TF_SIGNAL_MIN_WEEKS = 40            # vol52 ต้องมี return ≥ เท่านี้
TF_MAX_ZERO_FRAC = 0.20             # สัดส่วน return 0 เกินนี้ = NAV ค้าง -> ไม่ใช้กอง
TF_MIN_VOL = 0.02                   # vol52 ต่ำกว่านี้ = NAV ค้าง/ผิดปกติ
TF_ASOF_TOL_DAYS = 10               # จุดราคา ณ วันอ้างอิงใช้ NAV ล่าสุดที่ห่างไม่เกินนี้
TF_COV_MIN_WEEKS = 30               # ERC ใช้ Ledoit-Wolf ถ้ามีสัปดาห์ร่วม ≥ เท่านี้ ไม่งั้น inverse-vol
TF_TREND_SMA = 200                  # trend filter: MSCI ACWI < ค่าเฉลี่ย 200 วันทำการ -> ถือเงินสด
TF_TREND_CASH = 0.25
TF_TREND_INDEX = "MSCI_ACWI"
TF_START_Q = "2022-03-31"           # rebalance แรกของ backtest (ไตรมาสแรกที่มีประวัติพอ)
TF_EVAL_END = "2025-12-31"          # วัดผลถึงวันนี้เท่านั้น (NAV ม.ค.–มี.ค. 2026 ขาดหลายร้อยกอง — ไม่มี holdout)
TF_EXEC_LAG = 2                     # ซื้อขายที่ NAV วันทำการที่ 2 หลัง t
TF_EXEC_MAX_GAP_BDAYS = 10          # ไม่มี NAV ภายในนี้หลังวันซื้อขาย = ซื้อไม่ได้ -> เงินสด
TF_RF_SIM = 0.02                    # ดอกเบี้ยเงินสด + rf ของ Sharpe (คงที่ — ยังไม่มีอัตราไทยจริงในระบบ)
TF_COST_FLAT = 0.005                # ต้นทุนคงที่ต่อข้าง (กรณีเทียบกับรายงานเดิม)
TF_FEE_MAX_PCT = 10.0               # ค่าธรรมเนียม > 10 ใน SecFundFee = จำนวนบาทคงที่ ไม่ใช่ % -> ใช้ median
TF_N_TRIALS = 20                    # จำนวน trial ที่ลองบนข้อมูลชุดนี้ (ตรึง 2026-10-02) — ใช้คำนวณ deflated Sharpe
# replay สถานะการถือกอง: ไตรมาสที่กองสด < สัดส่วนนี้ของจำนวน U_t ณ TF_COVERAGE_REF ถูกข้าม (คงสถานะเดิม)
TF_COVERAGE_MIN = 0.50
TF_COVERAGE_REF = "2025-12-31"
TF_CACHE_PREFIX = "tf_portfolio"    # cache/tf_portfolio_*.csv
TF_M001_REFERENCE_CSV = os.path.join(BASE_DATA_DIR, "reference", "m001_backtest_curves.csv")
# หน้า 9 ส่วนที่ 2: ผล backtest TOP3 + B0 (ไฟล์อ้างอิงคงที่จาก backtest-validator · universe เต็ม · rf จริง ธปท. · ค่าธรรมเนียมจริงแก้แล้ว)
TF_TOP3_CURVES_CSV = os.path.join(BASE_DATA_DIR, "reference", "tf_top3_curves.csv")
TF_TOP3_METRICS_CSV = os.path.join(BASE_DATA_DIR, "reference", "tf_top3_metrics.csv")
TF_TOP3_SERIES = ("M019", "GC75_MMF", "TREND25", "M012_QFS", "B0")   # ลำดับแสดงผล (M019 เพิ่ม 2026-10-14)
TF_TOP3_N_TRIALS = 88              # จำนวนแบบที่ทีมลองแล้ว ณ ตอน export (DSR ของไฟล์อ้างอิง · = n_trials_cumulative สูงสุดใน trials.csv ตอน export)

# --- GC75 Frontier (หน้า 10) — efficient frontier ของกองที่ M019-LC3-GCGOLD ถือจริง (ดู docs/pages/10-gc75-frontier.md) ---
# (เดิม = GC75 + กองตลาดเงิน / M015-FAUM · ผู้ใช้เปลี่ยนเป็น M019 2026-10-13 · ชื่อ GC75_FRONTIER_* คงไว้ เพราะ M019 ใช้ GC75 กำหนดสัดส่วนหุ้น)
# prefix GC75_ (ไม่ใช่ TF_) โดยตั้งใจ — ค่าเหล่านี้ไม่เกี่ยวกับ cache หน้า 9 จึงต้องไม่อยู่ใน _tf_config_fingerprint
# input = ไฟล์อ้างอิงคงที่จาก .claude/quant_team/backtest/export_gc75_frontier.py (กองที่ถือ/น้ำหนัก/SR12′/rf + weekly return 52 สัปดาห์ ≤ t)
GC75_FRONTIER_HOLDINGS_CSV = os.path.join(BASE_DATA_DIR, "reference", "gc75_frontier_holdings.csv")
GC75_FRONTIER_WEEKLY_CSV = os.path.join(BASE_DATA_DIR, "reference", "gc75_frontier_weekly.csv")
# ผลที่เกิดขึ้นจริงของ MVP / max Sharpe / ERC (ค่าธรรมเนียมจริง · buy-and-hold · ไตรมาสที่ถือ และ 1 ปี) — export สคริปต์เดียวกัน
GC75_FRONTIER_REALIZED_CSV = os.path.join(BASE_DATA_DIR, "reference", "gc75_frontier_realized.csv")
# กริดเฉพาะส่วนหุ้น: ขาตั้งรับ (ทอง/ตลาดเงิน) ล็อกตามน้ำหนักจริงของไตรมาส · หุ้น 3 กอง กองละ 0–40% ของส่วนหุ้น
# ทีละ 1% → 231 ชุด (ผู้ใช้กำหนด 2026-10-13 เพดาน 40% · 2026-10-14 เปลี่ยนจาก 5% เป็น 1%)
GC75_FRONTIER_STEP = 0.01
GC75_FRONTIER_MAX_W = 0.40           # เพดานของกริด (สำรวจ) — แก้ได้โดยไม่กระทบจุด ERC
GC75_FRONTIER_MODEL_CAP = 0.40       # เพดาน ERC ของโมเดล M019 (run_m019.CAP) — จุด ERC ต้องตรงพอร์ตที่ถือจริง ห้ามเปลี่ยนตามกริด
GC75_FRONTIER_N_QUARTERS = 4         # สุ่มไตรมาสแบบคงที่ เปลี่ยนในหน้าเว็บไม่ได้ (ผู้ใช้กำหนด)
GC75_FRONTIER_SEED = 20261007
