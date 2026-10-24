# ข้อมูลภายนอก (ผู้ใช้อนุมัติดาวน์โหลด 2026-10-15) · สร้างด้วย `fetch_external.py`

| ไฟล์ | แหล่ง | ช่วงที่มีข้อมูลจริง | หมายเหตุ |
|---|---|---|---|
| `US_RATES_CREDIT_ETF.csv` | Yahoo Finance SHV / LQD / HYG / EMB (adjusted close · USD) | 2020-11-02 → 2026-10-14 · 1,494 แถว · ไม่มี NaN | แปลงเป็นบาทด้วย USDTHB ก่อนใช้ (งาน data-engineer) |
| `US_SPREADS_FRED.csv` | FRED DTB3 / BAMLC0A0CM / BAMLH0A0HYM2 (% · ระดับ) | DTB3 ครบตั้งแต่ 2020-11-02 · **IG/HY spread เริ่ม 2023-10-16 เท่านั้น** (ICE จำกัดประวัติบน FRED) | spread ใช้ในช่วงหลัก 2021–2025 ไม่ได้ → ใช้ LQD / HYG แทน · DTB3 ใช้ได้ |
| `TH_GOV_YIELDS.csv` | ThaiBMA public JSON — interpolated 1Y / 5Y / 10Y + T-BILL3M (% ต่อปี) | 2020-11-02 → 2026-10-14 · 1,440 แถว · ไม่มี NaN | เป็น yield ไม่ใช่ราคา → ประมาณผลตอบแทนด้วย duration (งาน data-engineer) |
| ~~`SET_INDEX.csv`~~ | Yahoo Finance `^SET.BK` | **ไม่ได้** — Yahoo คืนแค่วันล่าสุด 1 แถวทุก period (ทดสอบ start / 5y / max) | ลบไฟล์ 1 แถวทิ้งแล้ว · รอผู้ใช้เลือกแหล่งแทน |
| `TH_EQUITY_PROXY.csv` | Yahoo Finance **TDEX.BK** (ETF SET50 · บาท · adjusted close) — ผู้ใช้อนุมัติ "TDEX ก่อน ไม่ได้ค่อย THD" | 2020-11-02 → 2026-10-15 · 1,439 แถว · ไม่มี NaN | ตรวจกับ SET รายเดือนของ `Fama French SET50/` (Mkt-RF + Rf) 2021–2025: corr 0.963 (60 เดือน) · TDEX สูงกว่า ~0.52%/เดือน เพราะ adjusted close รวมปันผล (SET เป็นดัชนีราคา) · **วันที่ราคาไม่ขยับ 11.8%** (ETF สภาพคล่องต่ำ) → ใช้รายสัปดาห์ / ใส่ใน QA L0 · เป็น SET50 ไม่ใช่ SET ทั้งตลาด |
| `THEMATIC_ETF.csv` | Yahoo QQQ / SOXX / ARKK / ICLN / IBB / KWEB (adjusted close · USD) | 2020-11-02 → 2026-10-16 · 1,496 แถว · ไม่มี NaN · 122,996 B · sha256 `e400b26634635fc3…` | กองธีม (F-R004 · L4) · ดาวน์โหลด 2026-10-16 ตามที่ผู้ใช้อนุญาตระหว่าง auto run |
| `ASEAN_COUNTRY_ETF.csv` | Yahoo THD / EIDO / EPHE / EWM / EWS (adjusted close · USD) | 2020-11-02 → 2026-10-16 · 1,496 แถว · ไม่มี NaN · 105,280 B · sha256 `4d15460d34161b53…` | THD = MSCI Thailand แทน SET ฉบับทางการ · แยกประเทศอาเซียน · ดาวน์โหลด 2026-10-16 ตามที่ผู้ใช้อนุญาตระหว่าง auto run |
| `REAL_ASSETS_ETF.csv` | Yahoo REET / IGF / DBC / GSG (adjusted close · USD) | 2020-11-02 → 2026-10-16 · 1,496 แถว · ไม่มี NaN · 87,236 B · sha256 `7905fcf4f5ac6c02…` | กอง O / REIT / infra / commodities · ดาวน์โหลด 2026-10-16 ตามที่ผู้ใช้อนุญาตระหว่าง auto run |
| `HEDGED_EQUITY_ETF.csv` | Yahoo HEWJ + EWJ / HEFA + EFA (adjusted close · USD) | 2020-11-02 → 2026-10-16 · 1,496 แถว · ไม่มี NaN · 87,607 B · sha256 `8c1124a57c0f7a58…` | ผลของการ hedge (ลำดับรอง) · ดาวน์โหลด 2026-10-16 ตามที่ผู้ใช้อนุญาตระหว่าง auto run |

**ไม่ซื้อ** ข้อมูล SET ฉบับทางการ (USD 80 · F-R004) — การซื้อต้องให้ผู้ใช้ตัดสินเอง · ใช้ THD / TDEX แทน

## งาน F5-EO (F-R006 §5 · ผู้ใช้อนุมัติทั้ง 10 รายการ 2026-10-20 · BRIEF 111 / 113) · สร้างด้วย `fetch_eo.py` · ดาวน์โหลด 2026-10-20

| ไฟล์ | แหล่ง | ขนาด (B) | sha256 | หมายเหตุ |
|---|---|---|---|---|
| `raw_eo/AQR_Betting-Against-Beta-Equity-Factors-Daily.xlsx` | AQR Data Library (daily · หน้าลงวันที่ 2026-07-31 · ไม่มีหน้ายอมรับเงื่อนไข · ใช้เป็น robustness เท่านั้น) | 31458570 | `c34f1ac4130f69dd73440dd62a53caf22df47bc7cc50f5cf544f8e522c28a8c6` | ยังไม่แตก zip / แปลง (งาน data-engineer) |
| `raw_eo/AQR_Quality-Minus-Junk-Factors-Daily.xlsx` | AQR Data Library (daily · หน้าลงวันที่ 2026-07-31 · ไม่มีหน้ายอมรับเงื่อนไข · ใช้เป็น robustness เท่านั้น) | 31884896 | `6e0d68577fcd87e182c51902cd35d4dd7252d211d0f62327a87a1c7d9456de7e` | ยังไม่แตก zip / แปลง (งาน data-engineer) |
| `raw_eo/AQR_The-Devil-in-HMLs-Details-Factors-Daily.xlsx` | AQR Data Library (daily · หน้าลงวันที่ 2026-07-31 · ไม่มีหน้ายอมรับเงื่อนไข · ใช้เป็น robustness เท่านั้น) | 26114387 | `14d274a113a3ac0802fc501f4fe06798127d1eaef1d0e1a7aae9d515d5ccd760` | ยังไม่แตก zip / แปลง (งาน data-engineer) |
| `raw_eo/JKP_DEVELOPED_THEMES_DAILY.zip` | jkpfactors.com S3 (all themes · daily · capped VW · CC BY-NC 4.0) | 1904284 | `8db62c48399c55779758c0e66205f1a1129bcd67c374a08fbc5285fb8244e75a` | ยังไม่แตก zip / แปลง (งาน data-engineer) |
| `raw_eo/JKP_EMERGING_THEMES_DAILY.zip` | jkpfactors.com S3 (all themes · daily · capped VW · CC BY-NC 4.0) | 1963057 | `032fb61b7e01cb4abcd03ac642ea445f3934b3d41866bde29bd3bbea92fa2a30` | ยังไม่แตก zip / แปลง (งาน data-engineer) |
| `raw_eo/KF_Developed_5_Factors_CSV.zip` | Ken French Data Library | 6802 | `11c299a69b299ada4bd2e68d4c6393347a70e3bf474c967fe96bff469baa5e2e` | ยังไม่แตก zip / แปลง (งาน data-engineer) |
| `raw_eo/KF_Developed_5_Factors_Daily_CSV.zip` | Ken French Data Library | 86809 | `d380a0e73a680f31cbbad1760ed64cfa762a2efd27869756ed6c4688cccb87f9` | ยังไม่แตก zip / แปลง (งาน data-engineer) |
| `raw_eo/KF_Developed_Mom_Factor_CSV.zip` | Ken French Data Library | 2264 | `f2217d81ca76d749d1ee84dd8de80ec70db341c583b7c94a1960e3b807fa7931` | ยังไม่แตก zip / แปลง (งาน data-engineer) |
| `raw_eo/KF_Developed_Mom_Factor_Daily_CSV.zip` | Ken French Data Library | 30597 | `5a9ed87d648e4730fd9bbecaf83662fd333f5ea800091043b8cf5b7266b44373` | ยังไม่แตก zip / แปลง (งาน data-engineer) |
| `raw_eo/KF_Emerging_5_Factors_CSV.zip` | Ken French Data Library | 6978 | `303b5afb42232683f48f80178206a5cb99b1b755e4dc0493f9ec9b26dd74d103` | ยังไม่แตก zip / แปลง (งาน data-engineer) |
| `raw_eo/KF_Emerging_MOM_Factor_CSV.zip` | Ken French Data Library | 2272 | `5316f98a394947be155ba97f860366a14b214140d37b75c7eb93ad08bda92735` | ยังไม่แตก zip / แปลง (งาน data-engineer) |
| `raw_eo/KF_Europe_5_Factors_Daily_CSV.zip` | Ken French Data Library | 88773 | `d8c7d685917923160c2cc42609296775e3abdc3ba892bd0ca0d0c0c594ac7482` | ยังไม่แตก zip / แปลง (งาน data-engineer) |
| `raw_eo/KF_Europe_Mom_Factor_Daily_CSV.zip` | Ken French Data Library | 30815 | `735c247ecf004135cd53ded618ddb3174bc786ad82c2a999a340455f4a38daeb` | ยังไม่แตก zip / แปลง (งาน data-engineer) |
| `raw_eo/KF_Japan_5_Factors_Daily_CSV.zip` | Ken French Data Library | 91298 | `350b1eec802d2a24a861fa901f9cc0793ac55bca47ea7ef816514f7dc3140c0d` | ยังไม่แตก zip / แปลง (งาน data-engineer) |
| `raw_eo/KF_Japan_Mom_Factor_Daily_CSV.zip` | Ken French Data Library | 30965 | `841a361f662cb2bd0604a3bb79f6d5e626f2993cae3f205c2e357a417c1acaf9` | ยังไม่แตก zip / แปลง (งาน data-engineer) |
| `raw_eo/KF_North_America_5_Factors_Daily_CSV.zip` | Ken French Data Library | 90618 | `4bf4609f291754a77d9b65266263557e25faef721a736acbf86adcafa61da70b` | ยังไม่แตก zip / แปลง (งาน data-engineer) |
| `raw_eo/KF_North_America_Mom_Factor_Daily_CSV.zip` | Ken French Data Library | 31245 | `c5e28759a38079c3d1f17158cafd771e37c61c1622fbab728f5e8e4d075bebe0` | ยังไม่แตก zip / แปลง (งาน data-engineer) |
| `EO_ALT_ETF.csv` | Yahoo GLD / VNQ / VNQI adjusted close USD | 69580 | `6e7f1c1eb9676af52380ac5a03c34d75b933874043e84e8aaaf771342ef2ee31` | ยังไม่แตก zip / แปลง (งาน data-engineer) |
| `US_DOLLAR_REALRATE_FRED.csv` | FRED DTWEXBGS / DTWEXEMEGS / DFII10 | 51385 | `eab7e93599705fb4b211e2bb500836b9ea73a1f1aa554d6e4d5fe7855f99471d` | ยังไม่แตก zip / แปลง (งาน data-engineer) |
| `ASIA_REIT_LOCAL.csv` | Yahoo 1343.T / CLR.SI / JPYTHB=X / SGDTHB=X adjusted close (สกุลท้องถิ่น) | 92093 | `225debe3f940382c32685fe402405a30258bc62a07465f5cc2b5dae196339ed0` | ยังไม่แตก zip / แปลง (งาน data-engineer) |

- Yahoo ตัดแถววันดาวน์โหลด (ข้อมูลยังไม่ปิดวัน) ตอนสร้าง panel ตามบทเรียน EIDO · ASIA_REIT_LOCAL มี NaN ตามวันหยุดตลาดท้องถิ่น (1343.T 99 · CLR.SI 56) · FRED มี NaN วันหยุดสหรัฐฯ
- AQR xlsx 3 ไฟล์รวม ~89 MB → ไม่ commit (`.gitignore`) · สร้างใหม่ได้ด้วย `fetch_eo.py aqr`
