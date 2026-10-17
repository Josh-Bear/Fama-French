# QA_ACWI_CD_group — กองที่ primary = MSCI_ACWI_CD (ค่าชั่วคราวข้อ 48 · ตรวจก่อน L4)

แหล่งข้อมูล (อ่านอย่างเดียว): `base_data/FundProfile.csv` (ชื่อ · policy · บลจ. · flag) · `base_data/TopHolding.csv` (ข้อมูล ณ 2026-05 · เสริมเฉพาะ 6 กอง) · `runs/S005/primary_index.csv` (รายชื่อกลุ่ม · ฟอร์ม `1a@4`) · `data/universe.csv` (family · n_weeks · สัปดาห์ล่าสุด)

## สรุป

- กลุ่ม primary = MSCI_ACWI_CD ที่ฟอร์มหลัก `1a@4` = **40 กอง** (E 39 · F 1 · O 0) · บลจ. 12 แห่ง · ทุกกองพบใน FundProfile (0 หาย)
- ฟอร์ม `1a@3/@5 · 1b@4 · 1c@3/@4/@5 · none` ได้ชุดเดียวกัน 40 กอง · ฟอร์ม `3b@4 / 4a@4` ได้ 45 กอง (เพิ่ม B-GTO, PRINCIPAL GEF-A, PWIN, TSTARP, TUSMS) → กลุ่มไม่เสถียรเล็กน้อยตามฟอร์ม; ใช้ 40 กองของฟอร์มหลัก
- **FundProfile ไม่มีคำบรรยายนโยบาย/ธีมที่ใช้ได้**: คอลัมน์ `Fund Compare Perfermance Description` มีค่าเพียง 2 กอง (MGAG, MGAPVD = "Global Equity") · ไม่มีคอลัมน์ benchmark / investment policy / master fund → การจัดกลุ่มธีมด้านล่างอิง **ชื่อกอง (EN/TH)** เป็นหลักฐานหลัก และเสริมด้วย `TopHolding.csv` ได้เพียง 6 กอง (ASP-IHEALTH · ABAGS · LHESPORT-A · LHMOBILITY-A · MFTECH · UEV) · อีก 34 กองไม่มีข้อมูลดีกว่าชื่อ → ถือเป็นการจัดกลุ่มคร่าวๆ ตามที่สั่ง ไม่ใช่ข้อเท็จจริงเชิงนโยบาย
- ไม่พบกองจีนในกลุ่มนี้ (ไม่มีชื่อ China / Greater China / ASEAN / Asia) → ธีม "จีน" = 0 กอง · ถ้า L4 ต้องการ factor จีนต้องมองกลุ่ม CHINA_ALL (21 กอง) แยก
- Policy ทุกกองเป็น E ยกเว้น **M-SUKUK = F (ศุกูก/ตราสารหนี้)** — ไม่ควรอยู่ในกลุ่มธีมหุ้น (r² ต่อ ACWI_CD = 0.126 ต่ำสุดของกลุ่ม · มัธยฐานกลุ่ม 0.53) → เสนอให้ L4 ตัดออกจากกลุ่มหรือแยก
- **MGAG กับ MGAPVD เป็นกองเดียวกัน** (MFC Global Alpha · จดทะเบียน 2005-11-16 · ชนิดทั่วไปกับชนิดกองทุนสำรองเลี้ยงชีพ) · diff ผลตอบแทนรายสัปดาห์ค่ามัธยฐาน ~1e-6 แต่ corr = 0.988 < เกณฑ์ซ้ำ 0.99 เพราะ 2 สัปดาห์ที่ต่างกัน ~4% (2021-01-15, 2021-06-25) + 1 สัปดาห์ 0.25% (2026-07-03) → `dup_pairs.csv` ไม่จับ · family ใน L0 แยกเป็น 2 → ในกลุ่มมี **39 กองที่ไม่ซ้ำจริง** (เสนอรวมเป็น 1 ก่อน L4: ใช้ MGAG หรือตัดสินใจเรื่อง class ปันผล · ทั้งคู่ Dividend_Flag = Y)
- ธง Dividend_Flag = Y 4 กอง (B-FUTURE · B-USALPHA · MGAG · MGAPVD) → NAV ไม่รวมปันผล (ข้อ 52 α ต้องมีธง) · FX Risk Flag = N 4 กอง (KKP G-THEME-H · PRINCIPAL GCLOUD-A · GHEALTH-A · GINNO-A) — น่าจะเป็นกองที่ป้องกันความเสี่ยง FX เต็มจำนวน/เกือบเต็ม (KKP ชื่อลงท้าย HEDGED ยืนยันได้ 1 กอง · อีก 3 กองยังไม่ยืนยัน เพราะอ่าน schema PDF ในเครื่องนี้ไม่ได้) → ผลจาก USDTHB ไม่ควรเหมือนกองที่ไม่ hedge
- ข้อมูลสดต่างกัน: สัปดาห์ล่าสุดที่มีผลตอบแทน (จาก universe.csv) ของ 9 กอง (B-FUTURE · B-SIP · B-USALPHA · K-USA-A(A) · TBIOTECH · TGENOME · TGHDIGI · TNEWENGY · TNEXTGEN-A) สิ้นสุด 2026-01-16 · K-CHANGE-A(A) 2026-03-20 · PRINCIPAL GHEALTH-A 2026-04-10 → ช่วงทดสอบนอกตัวอย่างปี 2026 ไม่ครบทุกกอง (ค่าจาก universe.csv · อาจเป็นกองที่ NAV หยุดอัปเดต/เลิก — ยังไม่ได้ตรวจสถานะ)
- n_weeks ในช่วงหลัก 2021–2025: 215–260 (ต่ำสุด TNEXTGEN-A 215 · LHHEALTH-A 221 · B-USALPHA 226) — เปิดกองหลังปี 2021 หลายกอง (Registration 2021: ABGS-A · B-SIP · B-USALPHA · LHHEALTH-A · LHINNO-A · LHMOBILITY-A · MCANN · MFTECH · PRINCIPAL GHEALTH-A · TGENOME · TNEWENGY · UEV · KKP G-THEME-H)

## จัดกลุ่มธีมคร่าวๆ

| กลุ่มธีม | จำนวน | กอง |
|---|---|---|
| เทคโนโลยี / นวัตกรรม / ดิจิทัล | 9 | ASP-DISRUPT, KT-WTAI-A, LHINNO-A, MFTECH, MGTECH, PRINCIPAL GCLOUD-A, PRINCIPAL GINNO-A, TNEXTGEN-A, UNI |
| Healthcare / Biotech | 6 | ASP-IHEALTH, LHHEALTH-A, PRINCIPAL GHEALTH-A, TBIOTECH, TGENOME, TGHDIGI |
| EV / Mobility / พลังงานใหม่ | 3 | LHMOBILITY-A, UEV, TNEWENGY |
| Consumer / Lifestyle / E-commerce / Entertainment | 4 | LHESPORT-A, LHGLIFEE-A, ONE-GECOM, MCANN |
| Global / US equity ทั่วไป (growth · small cap · ไม่ใช่ธีมชัด) | 11 | ABAGS, ABGS-A, B-USALPHA, K-USA-A(A), LHGEQ-A, MGAG, MGAPVD, ONE-DISC-RA, ONE-UGG-RA, PRINCIPAL GOPP-A, ASP-X |
| Sustainable / ESG / Impact | 3 | ABWOOF, B-SIP, K-CHANGE-A(A) |
| หลายธีม / security / ไม่ชัด | 3 | UGSE, KKP G-THEME-H, B-FUTURE |
| ผิดกลุ่ม (ตราสารหนี้ · policy F) | 1 | M-SUKUK |

หลักการจัด: ชื่อ EN/TH ที่บอกธีมชัด (Cloud · AI · Fintech · Healthcare · Genomic · Battery/EV · e-Sport · Cannabis ฯลฯ) → ธีมนั้น · ชื่อทั่วไป (Global Equity · Growth · US Alpha · Discovery · Small Cap) → ทั่วไป · TopHolding ที่ยืนยันได้: ASP-IHEALTH (ARKG → healthcare/genomics) · LHESPORT-A (VanEck Video Gaming & eSports ETF 99.7%) · LHMOBILITY-A (Global X Lithium & Battery · KraneShares EV) · MFTECH (ARK Fintech Innovation 59%) · UEV (Robeco + Neuberger Berman — master fund ไม่ระบุธีมในไฟล์ จัดตามชื่อ) · ABAGS (abrdn Investments Luxembourg 99.6% = master fund ของ American Growth Smaller Co — ไม่ใช่ธีม) · กลุ่ม "หลายธีม / security / ไม่ชัด" = เดาจากชื่อไม่ได้ (UGSE = Global Security · B-FUTURE = หุ้นเพื่อคนรุ่นใหม่)

## ตารางกอง (40)

เรียงตามกลุ่มธีม · r² = R² ของ primary index (ฟอร์ม 1a@4) · n_wk = จำนวนสัปดาห์ผลตอบแทนใน 2021–2025 · last = สัปดาห์ล่าสุดที่มีผลตอบแทน (≤ 2026-07-31) · ev = หลักฐานที่ใช้จัดกลุ่ม

| กลุ่ม | FundCode | ชื่อเต็ม (EN) | ชื่อ (TH) | policy | บลจ. | family | จดทะเบียน | div | FX | risk | n_wk | last | r² | ev | TopHolding (≥5%) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| เทคโนโลยี | ASP-DISRUPT | Asset Plus Disruptive Opportunities Fund | กองทุนเปิด แอสเซทพลัส ดิสรัปทีฟ ออพพอร์ทูนิตี้ส์ | E | ASSETFUND | ASP-DISRUPT | 20180402 | N | Y | 6 | 260 | 2026-05-29 | 0.61 | ชื่อ | - |
| เทคโนโลยี | KT-WTAI-A | KTAM World Technology Artificial Intelligence Equity Fund - Class A | กองทุนเปิดเคแทม เวิลด์ เทคโนโลยี อาร์ทีฟิเชียล อินเทลลิเจนซ์ อิควิตี้ ฟันด์ - Class A | E | KTAM | KT-WTAI | 20180531 | N | Y | 6 | 260 | 2026-07-31 | 0.389 | ชื่อ | - |
| เทคโนโลยี | LHINNO-A | LH INNOVATION FUND | กองทุนเปิด แอล เอช อินโนเวชั่น ชนิดสะสมมูลค่า | E | LHFUND | LHINNO | 20210121 | N | Y | 6 | 257 | 2026-06-19 | 0.592 | ชื่อ | - |
| เทคโนโลยี | MFTECH | MFC Fintech Innovation Fund | กองทุนเปิดเอ็มเอฟซี ฟินเทค อินโนเวชั่น | E | MFC | MFTECH | 20210225 | N | Y | 6 | 252 | 2026-07-10 | 0.613 | ชื่อ + TopHolding | ARK Fintech Innovation ETF (59%); BGF FINTECH-D2 USD (22%); ETFMG PRIME MOBILE PAYMENTS - IPAYUS (17%) |
| เทคโนโลยี | MGTECH | MFC Next Generation Technology Fund | กองทุนเปิดเอ็มเอฟซี เน็กซ์ เจนเนอเรชั่น เทคโนโลยี | E | MFC | MGTECH | 20201030 | N | Y | 7 | 260 | 2026-07-10 | 0.52 | ชื่อ | - |
| เทคโนโลยี | PRINCIPAL GCLOUD-A | Principal Global Cloud Computing Fund | กองทุนเปิดพรินซิเพิล โกลบอล คลาวด์ คอมพิวติ้ง ชนิดสะสมมูลค่า | E | PRINCIPAL | PRINCIPAL GCLOUD | 20201012 | N | N | 7 | 260 | 2026-07-31 | 0.492 | ชื่อ | - |
| เทคโนโลยี | PRINCIPAL GINNO-A | Principal Global Innovation Fund | กองทุนเปิดพรินซิเพิล โกลบอล อินโนเวชั่น ชนิดสะสมมูลค่า | E | PRINCIPAL | PRINCIPAL GINNO | 20190220 | N | N | 6 | 260 | 2026-07-10 | 0.709 | ชื่อ | - |
| เทคโนโลยี | TNEXTGEN-A | TISCO Next Generation Internet Fund | กองทุนเปิด ทิสโก้ Next Generation Internet ชนิดผู้ลงทุนทั่วไป | E | TISCOASSET | TNEXTGEN | 20201112 | N | Y | 6 | 215 | 2026-01-16 | 0.646 | ชื่อ | - |
| เทคโนโลยี | UNI | United Global Innovation Fund | กองทุนเปิด ยูไนเต็ด โกลบอล อินโนเวชั่น ฟันด์ หน่วยลงทุนชนิดเพื่อผู้ลงทุนทั่วไป | E | UOBAM | UNI | 20181030 | N | Y | 6 | 260 | 2026-07-31 | 0.677 | ชื่อ | - |
| Healthcare | ASP-IHEALTH | Asset Plus Innovative Healthcare Fund | กองทุนเปิด แอสเซทพลัส อินโนเวทีฟ เฮลธ์แคร์ | E | ASSETFUND | ASP-IHEALTH | 20190329 | N | Y | 7 | 260 | 2026-05-29 | 0.392 | ชื่อ + TopHolding | JANUS HENDERSON HORIZON FUND (77%); ARK Investment Management LLC (22%) |
| Healthcare | LHHEALTH-A | LH HEALTH INNOVATION FUND | กองทุนเปิด แอล เอช เฮลธ์  อินโนเวชั่น ชนิดสะสมมูลค่า | E | LHFUND | LHHEALTH | 20210929 | N | Y | 7 | 221 | 2026-06-19 | 0.396 | ชื่อ | - |
| Healthcare | PRINCIPAL GHEALTH-A | Principal Global Health Innovation Fund | กองทุนเปิดพรินซิเพิล โกลบอล เฮลธ์ อินโนเวชั่น ชนิดสะสมมูลค่า | E | PRINCIPAL | PRINCIPAL GHEALTH | 20210205 | N | N | 7 | 256 | 2026-04-10 | 0.346 | ชื่อ | - |
| Healthcare | TBIOTECH | TISCO Biotechnology Healthcare Fund | กองทุนเปิด ทิสโก้ ไบโอเทคโนโลยี เฮลธ์แคร์ | E | TISCOASSET | TBIOTECH | 20200312 | N | Y | 7 | 260 | 2026-01-16 | 0.298 | ชื่อ | - |
| Healthcare | TGENOME | TISCO Genomic Revolution Fund | กองทุนเปิด ทิสโก้ Genomic Revolution | E | TISCOASSET | TGENOME | 20210113 | N | Y | 7 | 258 | 2026-01-16 | 0.455 | ชื่อ | - |
| Healthcare | TGHDIGI | TISCO Global Digital Health Equity Fund | กองทุนเปิด ทิสโก้ โกลบอล ดิจิตอล เฮลธ์ อิควิตี้ | E | TISCOASSET | TGHDIGI | 20190301 | N | Y | 7 | 260 | 2026-01-16 | 0.467 | ชื่อ | - |
| EV | LHMOBILITY-A | LH SMART MOBILITY FUND | กองทุนเปิด แอล เอช สมาร์ท โมบิลิตี้ ชนิดสะสมมูลค่า | E | LHFUND | LHMOBILITY | 20210518 | N | Y | 6 | 240 | 2026-06-19 | 0.597 | ชื่อ + TopHolding | Global X Lithium & Battery Tec (51%); Robeco Institutional Asset Management (35%); KraneShares Electric Vehicles and Futu (14%) |
| EV | TNEWENGY | TISCO New Energy Fund | กองทุนเปิด ทิสโก้ New Energy | E | TISCOASSET | TNEWENGY | 20210317 | N | Y | 6 | 249 | 2026-01-16 | 0.388 | ชื่อ | - |
| EV | UEV | United Battery and EV Technology Fund | กองทุนเปิด ยูไนเต็ด แบตเตอรี่ แอนด์ อีวี เทคโนโลยี ฟันด์ หน่วยลงทุนชนิดเพื่อผู้ลงทุนทั่วไป | E | UOBAM | UEV | 20210316 | N | Y | 6 | 251 | 2026-07-31 | 0.563 | ชื่อ + TopHolding | Robeco (51%); Neuberger Berman Group LLC (48%) |
| Consumer | LHESPORT-A | LH ESPORTS FUND | กองทุนเปิด แอล เอช อีสปอร์ต ชนิดสะสมมูลค่า | E | LHFUND | LHESPORT | 20201029 | N | Y | 6 | 260 | 2026-06-19 | 0.48 | ชื่อ + TopHolding | VanEck Video Gaming and eSports ETF (100%) |
| Consumer | LHGLIFEE-A | LH Global Lifestyle Equity Fund | กองทุนเปิด แอล เอช โกลบอล ไลฟ์สไตล์ อิควิตี้ ชนิดสะสมมูลค่า | E | LHFUND | LHGLIFEE | 20170830 | N | Y | 6 | 260 | 2026-06-19 | 0.537 | ชื่อ | - |
| Consumer | MCANN | MFC Global Cannabis Fund | กองทุนเปิดเอ็มเอฟซี โกลบอล แคนนาบิส | E | MFC | MCANN | 20210429 | N | Y | 6 | 243 | 2026-07-10 | 0.269 | ชื่อ | - |
| Consumer | ONE-GECOM | ONE GLOBAL E-COMMERCE FUND | กองทุนเปิด วรรณ โกลบอล อีคอมเมิร์ซ | E | ONEAM | ONE-GECOM | 20190327 | N | Y | 6 | 260 | 2026-07-31 | 0.637 | ชื่อ | - |
| Global | ABAGS | abrdn American Growth - Smaller Companies Fund | กองทุนเปิด อเบอร์ดีน อเมริกัน โกรท - สมอลเลอร์ คอมพานี ฟันด์ ชนิดสะสมมูลค่า | E | ABERDEEN | ABAGS | 20151103 | N | Y | 6 | 260 | 2026-06-19 | 0.407 | ชื่อ + TopHolding | abrdn Investments Luxembourg S.A. (100%) |
| Global | ABGS-A | abrdn Global Small Cap Fund | กองทุนเปิด อเบอร์ดีน โกลบอล สมอลแค็พ ฟันด์ ชนิดสะสมมูลค่า | E | ABERDEEN | ABGS | 20210407 | N | Y | 6 | 246 | 2026-06-19 | 0.493 | ชื่อ | - |
| Global | ASP-X | Asset Plus Extra Growth Fund | กองทุนเปิด แอสเซทพลัส เอ็กซ์ตร้า โกรท | E | ASSETFUND | ASP | 20200629 | N | Y | 6 | 260 | 2026-05-29 | 0.57 | ชื่อ | - |
| Global | B-USALPHA | Bualuang US Alpha Fund | กองทุนเปิดบัวหลวงยูเอสอัลฟ่า | E | BBLAM | B-USALPHA | 20210826 | Y | Y | 6 | 226 | 2026-01-16 | 0.685 | ชื่อ | - |
| Global | K-USA-A(A) | K USA Equity Fund | กองทุนเปิดเค ยูเอสเอ หุ้นทุน ชนิดสะสมมูลค่า | E | KASSET | K-USA | 20120907 | N | Y | 6 | 250 | 2026-01-16 | 0.394 | ชื่อ | - |
| Global | LHGEQ-A | LH GLOBAL EQUITY FUND | กองทุนเปิด แอล เอช โกลบอล อิควิตี้ ชนิดสะสมมูลค่า | E | LHFUND | LHGEQ | 20180725 | N | Y | 6 | 260 | 2026-06-19 | 0.599 | ชื่อ | - |
| Global | MGAG | MFC Global Alpha Fund | กองทุนเปิดเอ็มเอฟซี โกลบอล อัลฟ่า ฟันด์ ชนิดผู้ลงทุนทั่วไป | E | MFC | MGAG | 20051116 | Y | Y | 6 | 260 | 2026-07-10 | 0.549 | ชื่อ | - |
| Global | MGAPVD | MFC Global Alpha Fund | กองทุนเปิดเอ็มเอฟซี โกลบอล อัลฟ่า ฟันด์ ชนิดกองทุนสำรองเลี้ยงชีพ | E | MFC | MGAPVD | 20051116 | Y | Y | 6 | 260 | 2026-07-10 | 0.535 | ชื่อ | - |
| Global | ONE-DISC-RA | ONE DISCOVERY FUND | กองทุนเปิด วรรณ ดิสคัฟเวอรี่ หน่วยลงทุนชนิดไม่จ่ายปันผล สำหรับผู้ลงทุนทั่วไป (RA) | E | ONEAM | ONE-DISC | 20191120 | N | Y | 6 | 260 | 2026-07-31 | 0.357 | ชื่อ | - |
| Global | ONE-UGG-RA | ONE Ultimate Global Growth Fund | กองทุนเปิดวรรณ อัลติเมท โกลบอล โกรว์ธ หน่วยลงทุนชนิดไม่จ่ายปันผล สำหรับผู้ลงทุนทั่วไป (RA) | E | ONEAM | ONE-UGG | 20160204 | N | Y | 6 | 260 | 2026-07-31 | 0.468 | ชื่อ | - |
| Global | PRINCIPAL GOPP-A | Principal Global Opportunity Fund | กองทุนเปิดพรินซิเพิล โกลบอล ออพพอร์ทูนิตี้ ชนิดสะสมมูลค่า | E | PRINCIPAL | PRINCIPAL GOPP | 20170523 | N | Y | 6 | 260 | 2026-07-31 | 0.552 | ชื่อ | - |
| Sustainable | ABWOOF | abrdn Global Sustainable Equity Fund | กองทุนเปิด อเบอร์ดีน โกลบอล ซัสเทนเนเบิล เอคควิตี้ ฟันด์ | E | ABERDEEN | ABWOOF | 20060329 | N | Y | 6 | 260 | 2026-06-19 | 0.536 | ชื่อ | - |
| Sustainable | B-SIP | Bualuang Sustainable Investing Portfolio | กองทุนเปิดบัวหลวงยั่งยืน | E | BBLAM | B-SIP | 20210310 | N | Y | 6 | 250 | 2026-01-16 | 0.547 | ชื่อ | - |
| Sustainable | K-CHANGE-A(A) | K Positive Change Equity Fund | กองทุนเปิดเค พอสซิทีฟ เชนจ์ หุ้นทุน ชนิดสะสมมูลค่า | E | KASSET | K-CHANGE | 20190516 | N | Y | 6 | 250 | 2026-03-20 | 0.361 | ชื่อ | - |
| หลายธีม | B-FUTURE | Bualuang Future Generation Equity Fund | กองทุนเปิดบัวหลวงหุ้นเพื่อคนรุ่นใหม่ | E | BBLAM | B-FUTURE | 20180726 | Y | Y | 6 | 260 | 2026-01-16 | 0.558 | ชื่อ | - |
| หลายธีม | KKP G-THEME-H | KKP GLOBAL THEMATIC OPPORTUNITIES FUND - HEDGED | กองทุนเปิดเคเคพี GLOBAL THEMATIC OPPORTUNITIES - HEDGED ชนิดทั่วไป | E | KKPAM | KKP G-THEME | 20210210 | N | N | 6 | 254 | 2026-06-19 | 0.497 | ชื่อ | - |
| หลายธีม | UGSE | United Global Security Equities Fund | กองทุนเปิด ยูไนเต็ด โกลบอล ซีเคียวริตี้ อิควิตี้ ฟันด์ | E | UOBAM | UGSE | 20151201 | N | Y | 6 | 260 | 2026-07-31 | 0.531 | ชื่อ | - |
| ผิดกลุ่ม | M-SUKUK | MFC Global Sukuk Fund | กองทุนเปิดเอ็มเอฟซี โกลบอล ศุกูก | F | MFC | M-SUKUK | 20180802 | N | Y | 5 | 260 | 2026-07-10 | 0.126 | ชื่อ | - |

## จำนวนต่อ บลจ.

| บลจ. | จำนวน | กอง |
|---|---|---|
| LHFUND | 6 | LHINNO-A, LHHEALTH-A, LHMOBILITY-A, LHESPORT-A, LHGLIFEE-A, LHGEQ-A |
| MFC | 6 | MFTECH, MGTECH, MCANN, MGAG, MGAPVD, M-SUKUK |
| TISCOASSET | 5 | TNEXTGEN-A, TBIOTECH, TGENOME, TGHDIGI, TNEWENGY |
| PRINCIPAL | 4 | PRINCIPAL GCLOUD-A, PRINCIPAL GINNO-A, PRINCIPAL GHEALTH-A, PRINCIPAL GOPP-A |
| ABERDEEN | 3 | ABAGS, ABGS-A, ABWOOF |
| ASSETFUND | 3 | ASP-DISRUPT, ASP-IHEALTH, ASP-X |
| BBLAM | 3 | B-USALPHA, B-SIP, B-FUTURE |
| ONEAM | 3 | ONE-GECOM, ONE-DISC-RA, ONE-UGG-RA |
| UOBAM | 3 | UNI, UEV, UGSE |
| KASSET | 2 | K-USA-A(A), K-CHANGE-A(A) |
| KKPAM | 1 | KKP G-THEME-H |
| KTAM | 1 | KT-WTAI-A |

## กองที่เข้ากลุ่มเฉพาะบางฟอร์ม (3b@4 / 4a@4)

| FundCode | ชื่อ EN | policy | บลจ. | ฟอร์มที่เข้ากลุ่มนี้ |
|---|---|---|---|---|
| B-GTO | Bualuang Global Thematic Opportunities Fund | E | BBLAM | 3b@4,4a@4 |
| PRINCIPAL GEF-A | Principal Global Equity Fund | E | PRINCIPAL | 3b@4,4a@4 |
| PWIN | PHILLIP WORLD INNOVATION FUND | E | PAMC | 3b@4,4a@4 |
| TSTARP | TISCO Global Stars Plus Fund | E | TISCOASSET | 3b@4,4a@4 |
| TUSMS | TISCO US Mid/Small Cap Equity Fund | E | TISCOASSET | 3b@4,4a@4 |

## ต้องให้ผู้ใช้ตัดสินใจ / สิ่งที่กระทบ L4

1. ธีมของ 34 กองจัดจากชื่อเท่านั้น (ไม่มีข้อมูลนโยบายในไฟล์) — ถ้าต้องการหลักฐานที่ดีกว่า ต้องหาจากหนังสือชี้ชวน/factsheet (นอกขอบเขตไฟล์ที่มี · ต้องให้ผู้ใช้อนุญาต/จัดหา)
2. MGAG/MGAPVD ซ้ำกัน → รวมเป็น 1 ก่อน L4 หรือไม่ (กระทบขนาดกลุ่ม 40 → 39)
3. M-SUKUK (policy F) ควรออกจากกลุ่มธีมหุ้นหรือไม่
4. กลุ่มย่อยที่ใหญ่พอสำหรับ PCA (≥ 10): เทคโนโลยี/นวัตกรรม 9 (ใกล้) · Global/US ทั่วไป 11 (แต่ไม่ใช่ธีม) · ที่เหลือ < 10 → ใช้ LOO-mean residual (F-R004) ตามเดิม
