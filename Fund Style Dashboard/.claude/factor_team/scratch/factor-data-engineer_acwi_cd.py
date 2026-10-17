"""สร้าง data/QA_ACWI_CD_group.md — อ่านอย่างเดียว: FundProfile.csv · TopHolding.csv · runs/S005/primary_index.csv · data/universe.csv"""
import os, pandas as pd
ROOT = "/Users/doyinratnavardhana/Fama French/Fund Style Dashboard"
FT = os.path.join(ROOT, ".claude/factor_team")
p = pd.read_csv(os.path.join(ROOT, "base_data/FundProfile.csv"), encoding="utf-8-sig", dtype=str)
p.columns = [c.strip() for c in p.columns]
p["Fund Code"] = p["Fund Code"].str.strip()
t = pd.read_csv(os.path.join(ROOT, "base_data/TopHolding.csv"), encoding="utf-8-sig", dtype={"Fund Code": str})
t.columns = [c.strip() for c in t.columns]
t["Fund Code"] = t["Fund Code"].str.strip()
d = pd.read_csv(os.path.join(FT, "runs/S005/primary_index.csv"))
u = pd.read_csv(os.path.join(FT, "data/universe.csv")).set_index("FundCode")
main = d[(d.form == "1a@4") & (d["index"] == "MSCI_ACWI_CD")]
codes = main.FundCode.tolist()
r2 = main.set_index("FundCode")["r2"]
forms = d[d["index"] == "MSCI_ACWI_CD"].groupby("FundCode").form.apply(lambda s: ",".join(sorted(s)))
extra = sorted(set(d[d["index"] == "MSCI_ACWI_CD"].FundCode) - set(codes))

# กลุ่มธีม — ใช้ "ชื่อ" เป็นหลักฐานหลัก เพราะ FundProfile ไม่มีคำบรรยายนโยบาย/ธีม (Fund Compare Perfermance Description มีค่าแค่ 2 กอง) ;
# เสริมด้วย TopHolding เมื่อมี (6 กอง) — ดู evidence
THEME = {
 "เทคโนโลยี / นวัตกรรม / ดิจิทัล": ["ASP-DISRUPT", "KT-WTAI-A", "LHINNO-A", "MFTECH", "MGTECH", "PRINCIPAL GCLOUD-A", "PRINCIPAL GINNO-A", "TNEXTGEN-A", "UNI"],
 "Healthcare / Biotech": ["ASP-IHEALTH", "LHHEALTH-A", "PRINCIPAL GHEALTH-A", "TBIOTECH", "TGENOME", "TGHDIGI"],
 "EV / Mobility / พลังงานใหม่": ["LHMOBILITY-A", "UEV", "TNEWENGY"],
 "Consumer / Lifestyle / E-commerce / Entertainment": ["LHESPORT-A", "LHGLIFEE-A", "ONE-GECOM", "MCANN"],
 "Global / US equity ทั่วไป (growth · small cap · ไม่ใช่ธีมชัด)": ["ABAGS", "ABGS-A", "B-USALPHA", "K-USA-A(A)", "LHGEQ-A", "MGAG", "MGAPVD", "ONE-DISC-RA", "ONE-UGG-RA", "PRINCIPAL GOPP-A", "ASP-X"],
 "Sustainable / ESG / Impact": ["ABWOOF", "B-SIP", "K-CHANGE-A(A)"],
 "หลายธีม / security / ไม่ชัด": ["UGSE", "KKP G-THEME-H", "B-FUTURE"],
 "ผิดกลุ่ม (ตราสารหนี้ · policy F)": ["M-SUKUK"],
}
code2theme = {c: g for g, cs in THEME.items() for c in cs}
assert set(code2theme) == set(codes), (set(codes) ^ set(code2theme))

x = p[p["Fund Code"].isin(codes)].set_index("Fund Code").loc[codes]
def th(c):
    s = t[t["Fund Code"] == c].sort_values("Securities Seq")
    s = s[s["Securities Invest Size"] >= 5].head(3)
    return "; ".join(f"{r['Securities Name'].strip()[:38]} ({r['Securities Invest Size']:.0f}%)" for _, r in s.iterrows())
rows = []
for c in codes:
    r = x.loc[c]
    tp = th(c)
    rows.append(dict(
        code=c, grp=code2theme[c], amc=r["AMC_CODE"], pol=r["Fund Policy"], en=r["Fund Name EN"].strip(), th=r["Fund Name TH"].strip(),
        reg=r["Registration_date"], div=r["Dividend_Flag"], fx=r["FX Risk Flag"], risk=r["Fund Risk Level"], fam=u.loc[c, "family"], nw=int(u.loc[c, "n_weeks"]),
        last=u.loc[c, "last"], r2=r2[c], hold=tp, ev="ชื่อ + TopHolding" if tp else "ชื่อ"))
R = pd.DataFrame(rows)

def tab(df, cols, heads):
    out = "| " + " | ".join(heads) + " |\n|" + "|".join(["---"] * len(heads)) + "|\n"
    for _, r in df.iterrows():
        out += "| " + " | ".join(str(r[c]) for c in cols) + " |\n"
    return out

L = []
P = L.append
P("# QA_ACWI_CD_group — กองที่ primary = MSCI_ACWI_CD (ค่าชั่วคราวข้อ 48 · ตรวจก่อน L4)\n")
P("แหล่งข้อมูล (อ่านอย่างเดียว): `base_data/FundProfile.csv` (ชื่อ · policy · บลจ. · flag) · `base_data/TopHolding.csv` (ข้อมูล ณ 2026-05 · เสริมเฉพาะ 6 กอง) · "
  "`runs/S005/primary_index.csv` (รายชื่อกลุ่ม · ฟอร์ม `1a@4`) · `data/universe.csv` (family · n_weeks · สัปดาห์ล่าสุด)\n")
P("## สรุป\n")
P(f"- กลุ่ม primary = MSCI_ACWI_CD ที่ฟอร์มหลัก `1a@4` = **{len(codes)} กอง** (E {int((R.pol=='E').sum())} · F {int((R.pol=='F').sum())} · O {int((R.pol=='O').sum())}) · บลจ. {R.amc.nunique()} แห่ง · ทุกกองพบใน FundProfile (0 หาย)")
P(f"- ฟอร์ม `1a@3/@5 · 1b@4 · 1c@3/@4/@5 · none` ได้ชุดเดียวกัน 40 กอง · ฟอร์ม `3b@4 / 4a@4` ได้ 45 กอง (เพิ่ม {', '.join(extra)}) → กลุ่มไม่เสถียรเล็กน้อยตามฟอร์ม; ใช้ 40 กองของฟอร์มหลัก")
P("- **FundProfile ไม่มีคำบรรยายนโยบาย/ธีมที่ใช้ได้**: คอลัมน์ `Fund Compare Perfermance Description` มีค่าเพียง 2 กอง (MGAG, MGAPVD = \"Global Equity\") · ไม่มีคอลัมน์ benchmark / investment policy / master fund → "
  "การจัดกลุ่มธีมด้านล่างอิง **ชื่อกอง (EN/TH)** เป็นหลักฐานหลัก และเสริมด้วย `TopHolding.csv` ได้เพียง 6 กอง (ASP-IHEALTH · ABAGS · LHESPORT-A · LHMOBILITY-A · MFTECH · UEV) · อีก 34 กองไม่มีข้อมูลดีกว่าชื่อ → ถือเป็นการจัดกลุ่มคร่าวๆ ตามที่สั่ง ไม่ใช่ข้อเท็จจริงเชิงนโยบาย")
P("- ไม่พบกองจีนในกลุ่มนี้ (ไม่มีชื่อ China / Greater China / ASEAN / Asia) → ธีม \"จีน\" = 0 กอง · ถ้า L4 ต้องการ factor จีนต้องมองกลุ่ม CHINA_ALL (21 กอง) แยก")
P("- Policy ทุกกองเป็น E ยกเว้น **M-SUKUK = F (ศุกูก/ตราสารหนี้)** — ไม่ควรอยู่ในกลุ่มธีมหุ้น (r² ต่อ ACWI_CD = 0.126 ต่ำสุดของกลุ่ม · มัธยฐานกลุ่ม 0.53) → เสนอให้ L4 ตัดออกจากกลุ่มหรือแยก")
P("- **MGAG กับ MGAPVD เป็นกองเดียวกัน** (MFC Global Alpha · จดทะเบียน 2005-11-16 · ชนิดทั่วไปกับชนิดกองทุนสำรองเลี้ยงชีพ) · diff ผลตอบแทนรายสัปดาห์ค่ามัธยฐาน ~1e-6 แต่ corr = 0.988 < เกณฑ์ซ้ำ 0.99 เพราะ 2 สัปดาห์ที่ต่างกัน ~4% (2021-01-15, 2021-06-25) + 1 สัปดาห์ 0.25% (2026-07-03) → `dup_pairs.csv` ไม่จับ · family ใน L0 แยกเป็น 2 → ในกลุ่มมี **39 กองที่ไม่ซ้ำจริง** (เสนอรวมเป็น 1 ก่อน L4: ใช้ MGAG หรือตัดสินใจเรื่อง class ปันผล · ทั้งคู่ Dividend_Flag = Y)")
P("- ธง Dividend_Flag = Y 4 กอง (B-FUTURE · B-USALPHA · MGAG · MGAPVD) → NAV ไม่รวมปันผล (ข้อ 52 α ต้องมีธง) · FX Risk Flag = N 4 กอง (KKP G-THEME-H · PRINCIPAL GCLOUD-A · GHEALTH-A · GINNO-A) — น่าจะเป็นกองที่ป้องกันความเสี่ยง FX เต็มจำนวน/เกือบเต็ม (KKP ชื่อลงท้าย HEDGED ยืนยันได้ 1 กอง · อีก 3 กองยังไม่ยืนยัน เพราะอ่าน schema PDF ในเครื่องนี้ไม่ได้) → ผลจาก USDTHB ไม่ควรเหมือนกองที่ไม่ hedge")
P("- ข้อมูลสดต่างกัน: สัปดาห์ล่าสุดที่มีผลตอบแทน (จาก universe.csv) ของ 9 กอง (B-FUTURE · B-SIP · B-USALPHA · K-USA-A(A) · TBIOTECH · TGENOME · TGHDIGI · TNEWENGY · TNEXTGEN-A) สิ้นสุด 2026-01-16 · K-CHANGE-A(A) 2026-03-20 · PRINCIPAL GHEALTH-A 2026-04-10 → ช่วงทดสอบนอกตัวอย่างปี 2026 ไม่ครบทุกกอง (ค่าจาก universe.csv · อาจเป็นกองที่ NAV หยุดอัปเดต/เลิก — ยังไม่ได้ตรวจสถานะ)")
P("- n_weeks ในช่วงหลัก 2021–2025: 215–260 (ต่ำสุด TNEXTGEN-A 215 · LHHEALTH-A 221 · B-USALPHA 226) — เปิดกองหลังปี 2021 หลายกอง (Registration 2021: ABGS-A · B-SIP · B-USALPHA · LHHEALTH-A · LHINNO-A · LHMOBILITY-A · MCANN · MFTECH · PRINCIPAL GHEALTH-A · TGENOME · TNEWENGY · UEV · KKP G-THEME-H)\n")

P("## จัดกลุ่มธีมคร่าวๆ\n")
P("| กลุ่มธีม | จำนวน | กอง |\n|---|---|---|")
for g, cs in THEME.items():
    P(f"| {g} | {len(cs)} | {', '.join(cs)} |")
P("\nหลักการจัด: ชื่อ EN/TH ที่บอกธีมชัด (Cloud · AI · Fintech · Healthcare · Genomic · Battery/EV · e-Sport · Cannabis ฯลฯ) → ธีมนั้น · ชื่อทั่วไป (Global Equity · Growth · US Alpha · Discovery · Small Cap) → ทั่วไป · "
  "TopHolding ที่ยืนยันได้: ASP-IHEALTH (ARKG → healthcare/genomics) · LHESPORT-A (VanEck Video Gaming & eSports ETF 99.7%) · LHMOBILITY-A (Global X Lithium & Battery · KraneShares EV) · MFTECH (ARK Fintech Innovation 59%) · "
  "UEV (Robeco + Neuberger Berman — master fund ไม่ระบุธีมในไฟล์ จัดตามชื่อ) · ABAGS (abrdn Investments Luxembourg 99.6% = master fund ของ American Growth Smaller Co — ไม่ใช่ธีม) · "
  "กลุ่ม \"หลายธีม / security / ไม่ชัด\" = เดาจากชื่อไม่ได้ (UGSE = Global Security · B-FUTURE = หุ้นเพื่อคนรุ่นใหม่)\n")

P("## ตารางกอง (40)\n")
P("เรียงตามกลุ่มธีม · r² = R² ของ primary index (ฟอร์ม 1a@4) · n_wk = จำนวนสัปดาห์ผลตอบแทนใน 2021–2025 · last = สัปดาห์ล่าสุดที่มีผลตอบแทน (≤ 2026-07-31) · ev = หลักฐานที่ใช้จัดกลุ่ม\n")
R["r2"] = R["r2"].round(3)
R["grp"] = pd.Categorical(R["grp"], list(THEME.keys()), ordered=True)
R = R.sort_values(["grp", "code"], kind="stable")
P("| กลุ่ม | FundCode | ชื่อเต็ม (EN) | ชื่อ (TH) | policy | บลจ. | family | จดทะเบียน | div | FX | risk | n_wk | last | r² | ev | TopHolding (≥5%) |")
P("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
for _, r in R.iterrows():
    P(f"| {r.grp.split(' (')[0].split(' /')[0]} | {r.code} | {r.en} | {r.th} | {r.pol} | {r.amc} | {r.fam} | {r.reg} | {r['div']} | {r.fx} | {r.risk} | {r.nw} | {str(r['last'])[:10]} | {r.r2} | {r.ev} | {r.hold or '-'} |")
P("")
P("## จำนวนต่อ บลจ.\n")
vc = R.groupby("amc").code.apply(lambda s: ", ".join(s)).reset_index()
vc["n"] = vc["code"].str.count(",") + 1
vc = vc.sort_values(["n", "amc"], ascending=[False, True])
P("| บลจ. | จำนวน | กอง |\n|---|---|---|")
for _, r in vc.iterrows():
    P(f"| {r.amc} | {r.n} | {r.code} |")
P("\n## กองที่เข้ากลุ่มเฉพาะบางฟอร์ม (3b@4 / 4a@4)\n")
e = p[p["Fund Code"].isin(extra)].set_index("Fund Code")
P("| FundCode | ชื่อ EN | policy | บลจ. | ฟอร์มที่เข้ากลุ่มนี้ |\n|---|---|---|---|---|")
for c in extra:
    P(f"| {c} | {e.loc[c, 'Fund Name EN'].strip()} | {e.loc[c, 'Fund Policy']} | {e.loc[c, 'AMC_CODE']} | {forms[c]} |")
P("\n## ต้องให้ผู้ใช้ตัดสินใจ / สิ่งที่กระทบ L4\n")
P("1. ธีมของ 34 กองจัดจากชื่อเท่านั้น (ไม่มีข้อมูลนโยบายในไฟล์) — ถ้าต้องการหลักฐานที่ดีกว่า ต้องหาจากหนังสือชี้ชวน/factsheet (นอกขอบเขตไฟล์ที่มี · ต้องให้ผู้ใช้อนุญาต/จัดหา)")
P("2. MGAG/MGAPVD ซ้ำกัน → รวมเป็น 1 ก่อน L4 หรือไม่ (กระทบขนาดกลุ่ม 40 → 39)")
P("3. M-SUKUK (policy F) ควรออกจากกลุ่มธีมหุ้นหรือไม่")
P("4. กลุ่มย่อยที่ใหญ่พอสำหรับ PCA (≥ 10): เทคโนโลยี/นวัตกรรม 9 (ใกล้) · Global/US ทั่วไป 11 (แต่ไม่ใช่ธีม) · ที่เหลือ < 10 → ใช้ LOO-mean residual (F-R004) ตามเดิม")
open(os.path.join(FT, "data/QA_ACWI_CD_group.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")
print("written", len(codes))
