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
