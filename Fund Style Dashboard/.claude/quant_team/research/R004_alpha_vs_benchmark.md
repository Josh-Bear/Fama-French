# R004 — alpha เทียบดัชนีของกองเอง เป็นตัววัดคุณภาพ/ฝีมือในการคัดกอง

ผู้เขียน: quant-researcher · วันที่ 2026-10-06 · ฐานที่เทียบ: **Trend 25 / M004-TF-FX** (SR12 · N=8/K=16 · ERC LW 52 สัปดาห์ · cap 25% · ACWI < SMA200 → เงินสด 25%)
อ่านก่อนเขียน: `BRIEF.md`, `research/INDEX.md`, `R001` (ไอเดีย #2, #3), `R002`, `R003` (§บทสรุป–§2), `backtest/results/ALL_RESULTS.md`,
`backtest/results/DIAG_leadlag_correlation.md`, `docs/appendix/methodology.md`, `reports/TOP3_portfolio_logic.md`
ไม่ค้นซ้ำ: persistence ทั่วไป/ค่าธรรมเนียม/R² (R001), residual เทียบ ACWI (R002), async correlation (R003) — รอบนี้เจาะ **นิยาม alpha, benchmark point-in-time, bias เฉพาะข้อมูลเรา, หลักฐาน persistence ของ benchmark-adjusted return**
ข้อจำกัดของ session: ไม่มีเครื่องมือ list ไฟล์ (Glob ไม่มีให้ใช้) → ชื่อไฟล์ R003 หาได้จากการเดา · PDF แปลงไม่ได้ (ไม่มี pdftoppm) → หลายงานอ่านได้แค่ abstract

## บทสรุป 5 บรรทัด
1. **alpha เทียบดัชนีของกองไทย ส่วนใหญ่วัด "คุณภาพของพาหนะ" (ค่าธรรมเนียม 2 ชั้น + hedge + cash drag + ภาษี) มากกว่าฝีมือผู้จัดการ** — กอง FIF ไทยเกือบทั้งหมดเป็น feeder (82.5% ของสินทรัพย์ FIF, ก.ล.ต. มิ.ย. 2025) ฝีมือจริงอยู่ที่กองแม่ ส่วนที่ไทยเพิ่มคือต้นทุนที่คาดเดาได้ → ส่วนนี้ **persist ได้จริงเพราะค่าธรรมเนียม persist** ไม่ใช่เพราะฝีมือ
2. หลักฐาน persistence ของ benchmark-adjusted return **ปานกลาง**: ยุโรป 6 ประเทศ 1988–2010 persist ได้ถึง 36 เดือน (Vidal-García 2013) แต่ IR/selection return ของกองหุ้น US ไม่ persist (Kahn & Rudd 1995) และตัวทำนายตกครึ่งหลังตีพิมพ์ (Jones & Mo 2021, R001) · **การเลือก benchmark เปลี่ยนผลได้มาก** (~30% ของกองผู้ชนะหลุดสถานะเมื่อเปลี่ยน benchmark — Mateus et al. 2019)
3. ด้วยข้อมูลเรา (ดัชนีเริ่ม 2021-01 · ประเมินเริ่ม 2022-04) alpha 12 เดือนจาก 52 สัปดาห์ **เป็น noise เกือบทั้งหมด** (เลขคณิต: TE 5%/ปี × 1 ปี → SE ของ alpha ≈ 5%/ปี) · หน้าต่าง 36 เดือนทำไม่ได้ช่วงต้น → ใช้ **expanding window รายสัปดาห์ + Dimson lag 1** (แก้ NAV async ตาม DIAG) · ห้ามใช้ `cache/coefs.csv` และห้าม ElasticNet 28 ดัชนีแบบ rolling (เกิน 52 จุด)
4. มี bias ระดับที่ทำให้ "alpha ≥ 0" ใช้ตรงๆ ไม่ได้: กองส่วนใหญ่ alpha ติดลบตามธรรมชาติ (BRIEF: median ต่ำกว่าดัชนีหลัก −6.6 pt/ปี) + **ถ้าดัชนีใน `MSCI_*_ETF.csv` เป็นราคา (ไม่รวมปันผล) จะเกิด bias ตามภูมิภาค** (dividend yield ต่างกัน) + กอง -H เทียบดัชนีบาทแบบไม่ hedge → ต้องใช้เกณฑ์ **เทียบข้ามกอง (median)** และใส่ USDTHB เป็น regressor ที่ 2
5. **ตอบตรงๆ: alpha เทียบดัชนีไม่น่าเพิ่ม Sharpe อย่างมีความหมาย** (วรรณกรรมให้ ≤ ~20 bp/ไตรมาสหลัง decay — R001 · ในพอร์ตที่ SR12 กรองแล้วเล็กกว่านั้น) **คุณค่าหลักคือเป็นตัววัดคุณภาพที่อธิบายลูกค้าได้** ("กองนี้ตามดัชนีของตัวเองได้ดีแค่ไหนหลังหักค่าธรรมเนียม") และเป็นตัวกรองแบบ "ไม่ทำให้แย่ลง" · เห็นด้วยกับผู้ใช้ว่า AUM ไม่ใช่ตัววัดคุณภาพ (AUM สะท้อน flow/การตลาด ไม่ใช่ผลเทียบดัชนี) แต่ alpha ก็ไม่ใช่ "ฝีมือ" ล้วน

## ตารางอันดับไอเดีย
คะแนน = (หลักฐาน 1–3 × เข้ากับข้อมูล 1–3) ÷ trial · ทุกไอเดียใช้ขั้นตอน alpha มาตรฐานเดียวกัน (§ส่วนที่ 3) ล็อกก่อนรัน

| # | ไอเดีย | ต่อยอด/แทนที่ส่วนไหนของ M004-TF-FX | หลักฐาน | เข้ากับข้อมูล | trial | คะแนน |
|---|---|---|---|---|---|---|
| 0 | **Diagnostic (ไม่ใช่ trial)**: คำนวณ alpha/IR ณ ทุกสิ้นไตรมาสของกองที่ถือจริง + กองอันดับ 9–16 · รายงานการกระจาย, สัดส่วน alpha ≥ 0, rank-correlation ของ alpha ไตรมาส t กับ t+4 (persistence ในข้อมูลเรา **ไม่ดู Sharpe**) · ตรวจว่าดัชนีเป็น price/net/gross | ไม่เปลี่ยนโมเดล — ได้ตัวชี้วัดคุณภาพไว้แสดงลูกค้าทันที | — | สูง (3) | 0 | ทำก่อน |
| 1 | **ตัวกรองขาเข้า**: กองที่ยังไม่ถือ ต้องมี alpha (expanding, Dimson, ดัชนีคู่ + USDTHB) ≥ **median ของกองที่คัดได้ I_t** จึงเข้าได้ · กองที่ถืออยู่ไม่ถูกตัดด้วยเกณฑ์นี้ | ต่อยอดขั้น "คัดได้ I_t" ก่อนเติมกองตาม SR12 (hysteresis/ERC/cash เหมือนเดิม) | ปานกลาง (2) | กลาง–สูง (2.5) — ทุกอย่างคำนวณได้จาก NAV + MSCI + USDTHB | 1 | 5.0 |
| 2 | **ผสมอันดับ**: คะแนน = ค่าเฉลี่ยของ rank(SR12) กับ rank(appraisal ratio) น้ำหนัก 50/50 (ไม่ tune) | แทนที่สัญญาณจัดอันดับ SR12 บางส่วน | ปานกลาง–อ่อน (1.5) — IR ไม่ persist ในกองหุ้น US (Kahn & Rudd) | กลาง (2) | 1 | 3.0 |
| — | แทน SR12 ด้วย alpha/IR ล้วน | — | ขัดกลไก: SR12 ได้ return จาก country/sector momentum (Breloer et al. 2014, R001) ซึ่ง alpha ตัดทิ้ง | — | — | **ไม่ควรลอง** |

---

## ส่วนที่ 1 — นิยาม alpha ที่ทำได้กับข้อมูลเรา

| นิยาม | สูตร (ต่อสัปดาห์, ข้อมูล ≤ t) | ข้อดี | ข้อเสีย/กับดักในข้อมูลเรา |
|---|---|---|---|
| (ก) **Benchmark-adjusted return (BAR)** | r_กอง − r_ดัชนีคู่ สะสม | ไม่ต้องประมาณ beta · อธิบายลูกค้าง่ายสุด ("แพ้/ชนะดัชนีกี่ %") · Angelidis et al. 2013 เสนอให้วัดเทียบ benchmark ของกองเองแทน factor portfolio · Vidal-García 2013 พบ persistence ของ BAR ในยุโรป | beta ≠ 1 ปนเข้ามา (กอง beta สูงดูดีตอนตลาดขึ้น) · async NAV ทำให้ BAR รายสัปดาห์มี noise สูงแต่ **ไม่ bias ผลสะสม** (ผลรวมระยะยาวเท่ากัน) · กอง -H ปน FX ทั้งก้อน |
| (ข) **Regression alpha** | r_กอง = α + β₀·r_idx,t + β₁·r_idx,t−1 + γ·r_USDTHB,t + e (Dimson lag 1) | ตัด beta · β₀+β₁ แก้ beta ต่ำเกินจริงจาก NAV ไม่พร้อมกัน (ตรงกับ DIAG: Γ1 มีนัย) · γ ดูดผล hedge (กองไม่ hedge γ≈0, กอง hedge USD γ≈−β) โดย **ไม่ต้องติดป้าย -H เอง** | เพิ่ม 2 พารามิเตอร์ → noise · OLS alpha มี false positive สูงทั้งรายวันและรายเดือน (Mamaysky, Spiegel & Zhang 2008) · กองที่ hedge สกุลอื่น (JPY/EUR) γ บนดอลลาร์จับได้ไม่หมด |
| (ค) **Information ratio / appraisal ratio** | IR = mean(BAR)/sd(BAR) · AR = α/sd(e) | ปรับด้วยความเสี่ยงเชิงรุก → กอง TE ต่ำที่แพ้น้อยกับกอง TE สูงเทียบกันได้ · ใกล้แนวคิด SR12 (risk-adjusted) | IR ของกองหุ้นไม่ persist (Kahn & Rudd 1995, US) · กอง TE ต่ำมาก (index feeder) ได้ IR สุดโต่งจาก α เล็กๆ → ไม่เสถียร · Harvey & Liu 2019: ช่วงที่ dispersion สูง กองไม่มีฝีมือดูเก่งได้ง่าย ต้องลดน้ำหนักผลที่วัดได้ |

**หน้าต่าง**: ดัชนีเริ่ม 2021-01 (methodology §1) → rebalance แรก 2022-03 มี ~62 สัปดาห์ · 24/36 เดือนทำไม่ได้ช่วงต้น · เลขคณิต: SE(α รายปี) ≈ TE ÷ √(ปี) → TE 5% ที่ 1 ปี SE ≈ 5% · ที่ 3 ปี ≈ 2.9% → alpha 1–2%/ปี (ระดับที่สมจริง) **ไม่มีนัยในทุกหน้าต่างที่เรามี** → ใช้ **expanding window (ขั้นต่ำ 52 สัปดาห์, ใช้ทุกสัปดาห์ ≤ t)** ได้ precision สูงสุดเท่าที่ข้อมูลให้ และสอดคล้องกับ persistence ระยะยาวของ Vidal-García (ถึง 36 เดือน) · ไม่ใช้ 12-1 สำหรับ alpha (R001 เสนอ 12-1 — **แก้ข้อเสนอนั้น**: 12-1 สอดคล้องกับ SR12 แต่ noise สูงเกินกว่าจะเป็นตัววัดคุณภาพ)

**รายสัปดาห์ vs รายเดือน**: รายเดือนไม่โดน async แต่ช่วงต้นมีแค่ ~15 จุด (ประมาณ 3 พารามิเตอร์ไม่ได้) · DIAG ยืนยันว่า lag-1 รายสัปดาห์ฟื้น correlation ได้ใกล้รายเดือน (0.49 vs 0.53) → **รายสัปดาห์ + Dimson lag 1** เป็นค่ามาตรฐาน (Dimson 1979 — ยังไม่ยืนยันแหล่งในรอบนี้ แต่ R003 อ้าง Scholes–Williams/Dimson ไว้แล้ว)

## ส่วนที่ 2 — เลือก benchmark แบบ point-in-time

| ทางเลือก | look-ahead | noise | สรุป |
|---|---|---|---|
| exposure ElasticNet ใน `cache/coefs.csv` | **มี** (fit ทั้งช่วง ถึง 2026) | — | ห้ามใช้ |
| ElasticNet/หลายดัชนี rolling 52 สัปดาห์ บน 28 ตัว | ไม่มี | **สูงมาก** — 28 regressor/52 จุด · ดัชนีผสมที่ fit ดีที่สุดดูด return ของกองไปเป็น "benchmark" → alpha ถูกดึงเข้า 0 · ผลเปลี่ยนทุกไตรมาส | ไม่ควรใช้ |
| **ดัชนีเดียวที่ R² สูงสุด จาก 18 country + 10 sector + ACWI, expanding window ≤ t** | ไม่มี | กลาง — การเลือกค่าสูงสุดจาก 29 ตัว inflate R² เล็กน้อย แต่ benchmark เดียวไม่ดูด alpha · feeder ส่วนใหญ่ mandate คงที่ → ดัชนีคู่นิ่ง | **ค่ามาตรฐานที่แนะนำ** (ตรงกับ R001 แต่เปลี่ยน 52 สัปดาห์ → expanding เพื่อลดการสลับดัชนี) |
| benchmark ตามหนังสือชี้ชวน (FundProfile) | ไม่มี ถ้ามีประวัติ ณ t | ต่ำ | ดีที่สุดในหลักการ (Angelidis et al. 2013, Sensoy 2009) แต่ **Sensoy: ~1/3 ของกอง US ระบุ benchmark ไม่ตรง style จริง** และเราไม่รู้ว่ามีในระบบ → ต้องให้ผู้ใช้ตัดสินใจ |
| peer benchmark (ค่าเฉลี่ยกองธีมเดียวกัน — Hunter et al. 2014) | ไม่มี | กลาง | หลักฐานดี (เพิ่มการเลือกกองที่ชนะในอนาคต, US) แต่ต้องมีการจัดกลุ่มธีม ณ t ที่เชื่อถือได้ (M008: theme cluster ยังมีปัญหา) → พักไว้ |

ข้อควรระวัง: Mateus, Mateus & Todorovic 2019 (1,281 กอง US): เปลี่ยนจาก benchmark หนังสือชี้ชวนเป็น benchmark ที่ตรงหมวด ~30% ของกองผู้ชนะหลุดสถานะ → **ล็อกวิธีเลือกดัชนีใน spec ก่อนรัน ห้ามรันหลายวิธีแล้วเลือก**

## ส่วนที่ 3 — bias เฉพาะกองไทยที่ทำให้ระดับ alpha อ่านตรงๆ ไม่ได้

| แหล่ง bias | ทิศ | วิธีจัดการที่ไม่ต้อง tune |
|---|---|---|
| ค่าธรรมเนียม 2 ชั้น (feeder TER + กองแม่ TER) อยู่ใน NAV | alpha ติดลบเป็นปกติ (BRIEF: กอง passive ห่างดัชนี ~3 pt, median −6.6 pt — ไม่ได้ตรวจซ้ำเอง) | ใช้เกณฑ์ **เทียบข้ามกอง (median ของ I_t)** ไม่ใช่ 0 |
| ดัชนีอาจเป็น **ราคา (ETF price)** ไม่รวมปันผล (ชื่อไฟล์ `MSCI_COUNTRY_ETF.csv`) — ถ้าเป็น MSCI net จะหัก WHT อัตราสูงสุดสำหรับผู้ลงทุนสถาบันต่างชาติแล้ว (MSCI Index Calculation Methodology) | ถ้าเป็นราคา: กองสะสมได้ alpha บวกเท่า dividend yield ซึ่ง **ต่างตามภูมิภาค** → กองยุโรป/high-dividend ดูดีเกินจริงเมื่อเทียบกองสหรัฐฯ/เทค | **ต้องตรวจก่อน (diagnostic #0 / data-qa)** · ถ้าเป็นราคาและไม่มี total return → ตีความเฉพาะการเทียบ **ภายในดัชนีคู่เดียวกัน** (กอง Japan เทียบกอง Japan) |
| กอง -H vs ดัชนีบาทไม่ hedge | alpha ปน (FX change + ส่วนต่างดอกเบี้ย) · BRIEF: KT-JPFUND-A 16.8% vs MSCI Japan 8.8% | regressor USDTHB (มีใน macro 7 ตัว) ใน (ข) · ส่วนต่างดอกเบี้ยของ hedge (CIP) จะเหลือใน α เป็นต้นทุน/รายได้คงที่ — ตีความเป็น "คุณภาพของพาหนะ" ได้ |
| class ปันผล (-D) NAV ไม่รวมปันผล | alpha ต่ำเกินจริง (BRIEF: −9.3 pt) | M004-TF-FX ตัด -D ถ้ามี class อื่นแล้ว · กอง -D ที่เหลือ: ไม่ใช้ alpha กรอง (ผ่านอัตโนมัติ) — ผู้ใช้เลือกไม่แก้ NAV แล้ว |
| กองใหม่ < 52 สัปดาห์ร่วมกับดัชนี | ประมาณไม่ได้ | ผ่านอัตโนมัติ (เหมือนเกณฑ์ ≥ 30 สัปดาห์ใน ERC แต่ใช้ 52 ตามหน้าต่าง SR12) |

**นัยต่อ feeder**: α_feeder ≈ α_กองแม่ − ค่าธรรมเนียมชั้นไทย − ผล hedge − cash drag · ส่วนหลัง 3 ตัวนิ่งและรู้ล่วงหน้า → นี่คือเหตุที่ alpha อาจ "persist" ในข้อมูลเรา แม้ฝีมือกองแม่จะไม่ persist · ในทางปฏิบัติ alpha เทียบดัชนีคือ **ตัวเลือก "ซื้อธีมนี้ผ่านกองไหนดีที่สุด"** ซึ่งสอดคล้องกับหลักฐานค่าธรรมเนียมใน R001 (แข็ง)

## ส่วนที่ 4 — รายละเอียดต่อไอเดีย

### ไอเดีย 1 — ตัวกรองขาเข้าด้วย alpha เทียบดัชนี (เกณฑ์ median ข้ามกอง)
| หัวข้อ | เนื้อหา |
|---|---|
| ไอเดีย + กลไก | SR12 ของกอง = momentum ของธีม + คุณภาพพาหนะ · กองที่ SR12 สูงแต่ alpha ต่ำ = ได้ธีมดีแต่ผ่านพาหนะแพ้ดัชนีมาก (ค่าธรรมเนียม/hedge/tracking แย่) → ควรเลือกกองอื่นในธีมเดียวกัน ซึ่ง SR12 อันดับถัดไปมักเป็นกองธีมใกล้กัน · ใช้เฉพาะขาเข้า เพื่อไม่ให้ alpha ที่ noisy สั่งขายกองที่ถืออยู่ (กัน turnover · ตรรกะเดียวกับ hysteresis) |
| หลักฐาน | Vidal-García 2013 (ยุโรป 6 ประเทศ 1988–2010, กอง style-consistent ไม่มี survivorship): BAR persist ถึง 36 เดือน โดยเฉพาะหัว/ท้าย · Hunter et al. 2014 (US): benchmark ที่ตรงกลุ่มช่วยเลือกกองที่ชนะในอนาคต · Kinnel/Morningstar (R001): ค่าธรรมเนียมทำนายผล · ฝั่งค้าน: Kahn & Rudd 1995 (US equity: ไม่ persist), Jones & Mo 2021 (decay ≥ ครึ่ง), Mamaysky et al. 2008 (OLS alpha false positive สูง) → **ปานกลาง** |
| เข้ากับข้อมูลเรา | NAV รายสัปดาห์ (`SignalContext.weekly_return_series` แบบที่ DIAG ใช้), MSCI THB 28 ตัว + ACWI, USDTHB (macro) · ทุกอย่างมี · ยังไม่รู้ว่าดัชนีเป็น price/net (กระทบการเทียบข้ามธีม — median ข้ามกองลด bias ระดับแต่ไม่ลด bias ตามภูมิภาค) |
| ผลที่คาด | Sharpe: ±0.0x (R001: ≤ 20 bp/ไตรมาสหลัง decay ก่อนกรอง SR12) · turnover: **ไม่ควรเพิ่ม** (ไม่สั่งขาย; อาจเปลี่ยนกองที่เติม 0–1 กอง/ไตรมาส) · drawdown: ไม่เปลี่ยน · ข้อสังเกตจากทีม: M009 เปลี่ยนกองเดียวไตรมาสแรก Sharpe ขยับ ~0.2 → ผลของไอเดียนี้จะถูก noise ของการเลือกกองกลบ |
| ต้นทุนเชิงสถิติ | 1 trial · ค่ามาตรฐานล็อก: expanding ≥ 52 สัปดาห์ · Dimson lag 1 · regressor = ดัชนีคู่ (R² สูงสุด expanding จาก 29 ตัว) + USDTHB · เกณฑ์ = median ของ α ในกองที่คัดได้ I_t ณ t · ใช้ α (ไม่ใช่ AR) · ห้าม tune เกณฑ์เป็น percentile อื่น/หน้าต่างอื่น |
| ร่างสมมติฐาน | "กองที่ยังไม่ถือจะเข้าพอร์ตได้เมื่อ α (expanding, Dimson, ดัชนีคู่ + USDTHB) ≥ median ของ I_t เท่านั้น ส่วนอื่นเท่า M004-TF-FX → Sharpe ไม่ลดลง (Δ ≥ 0 ตามเกณฑ์ผู้ใช้) และกองที่ถูกกรองออกมี BAR ไตรมาสถัดไปต่ำกว่ากองที่เข้าแทน" · วัด: paired Δ Sharpe + CI, จำนวนกองที่ถูกกันต่อไตรมาส, BAR ถัดไปของกองที่ถูกกัน vs กองที่เข้าแทน (diagnostic กลไก) |

### ไอเดีย 2 — ผสม rank(SR12) กับ rank(appraisal ratio)
| หัวข้อ | เนื้อหา |
|---|---|
| ไอเดีย + กลไก | เก็บ momentum ของธีม (SR12) ไว้ครึ่งหนึ่ง เพิ่มคุณภาพพาหนะที่ปรับ TE แล้วอีกครึ่ง |
| หลักฐาน | AR/IR ใช้แพร่หลายแต่หลักฐาน persistence ในกองหุ้นอ่อน (Kahn & Rudd) · Harvey & Liu 2019: ต้องลดน้ำหนักผลที่วัดได้ในภาวะ dispersion สูง (ปี 2022 ของเรา) → **ปานกลาง–อ่อน** |
| เข้ากับข้อมูลเรา | เหมือนไอเดีย 1 · AR ของกอง TE ต่ำมาก (index feeder) ไม่เสถียร |
| ผลที่คาด | เปลี่ยนชุดกองมากกว่าไอเดีย 1 → turnover อาจเพิ่ม (ทุกกองใหม่ ~0.54%/ข้าง) · ลดน้ำหนัก country momentum ซึ่งเป็นแหล่ง return หลัก → เสี่ยง Sharpe ลด |
| ต้นทุนเชิงสถิติ | 1 trial · 50/50 ตายตัว ห้าม tune น้ำหนัก |
| ร่างสมมติฐาน | "จัดอันดับด้วยค่าเฉลี่ย rank(SR12) และ rank(AR expanding) แทน SR12 ล้วน → ไม่ลด Sharpe" · ทำเฉพาะเมื่อไอเดีย 1 ผ่าน (Δ ≥ 0) และผู้ใช้ยอมรับ trial เพิ่ม |

## ไอเดียที่ไม่ควรลอง (และเหตุผล)
| ไอเดีย | เหตุผล |
|---|---|
| แทน SR12 ด้วย alpha/IR ล้วน | ตัด country/sector momentum ที่เป็นแหล่ง return หลัก (Breloer et al. 2014) · ผลจะเป็นการเลือก "พาหนะดีในธีมไหนก็ได้" รวมธีมขาลง |
| alpha 12 เดือน (หรือ 12-1) รายสัปดาห์ เป็นตัวกรองที่ **สั่งขาย** กองที่ถืออยู่ | SE ≈ ขนาด alpha → เครื่องหมายสลับบ่อย → turnover เพิ่มโดยไม่มีข้อมูลจริง |
| ElasticNet/หลายดัชนี rolling เป็น benchmark | 28 regressor/52 จุด overfit · benchmark ดูด alpha · ใช้ `coefs.csv` = look-ahead |
| alpha จาก Fama-French/style factor 4 ตัว | Cremers et al. (R001): factor วิชาการให้ alpha ปลอมแม้แต่ดัชนี passive · style factor ของเราสร้างจาก ETF US/Intl blend ไม่ตรงกับ benchmark ของ feeder |
| Kalman filter / Bayesian shrinkage alpha | Mamaysky et al. 2008 ดีกว่า OLS ในตัวอย่างใหญ่ (US หลายพันกอง หลายสิบปี) · เรามี ~4–5 ปี → พารามิเตอร์ state noise ประมาณไม่ได้ |
| เกณฑ์ alpha ≥ 0 แบบตรงๆ | bias ระดับจากค่าธรรมเนียม/ปันผล/ภาษี ทำให้ตัดกองส่วนใหญ่ หรือเอียงตามภูมิภาค (ถ้าดัชนีเป็นราคา) → ใช้ median ข้ามกองแทน (แต่รายงาน % alpha ≥ 0 เป็นตัวชี้วัดสำหรับลูกค้าได้) |
| รันหลายนิยาม/หลายหน้าต่าง/หลายวิธีเลือกดัชนีแล้วเลือกตัวดีสุด | Mateus et al. 2019: การเลือก benchmark เปลี่ยนอันดับ ~30% → เป็น trial ซ่อน ลด DSR |
| R² ต่ำ × alpha (R001 #3) ตอนนี้ | ต้องพึ่ง alpha ที่ noisy คูณกับ R² ที่ async กดลง (กอง NAV ช้า R² ต่ำเพราะข้อมูล ไม่ใช่ active) → พักจนกว่าไอเดีย 1 แสดงว่า alpha มีข้อมูลจริง |
| AUM เป็นตัววัดคุณภาพ | ไม่มีหลักฐานที่เปิดอ่านในรอบนี้ว่า AUM ทำนายผลเทียบดัชนี · AUM ของเรามีรู (R001) · กลไก Berk–Green (ยังไม่ยืนยันแหล่ง) ชี้ว่าขนาดไล่ตามผลอดีต ไม่ใช่ตัวนำ |

## คำแนะนำถึง quant-modeler
1. **ทำ diagnostic #0 ก่อน (0 trial, รอ validator จบ M012)**: ตรวจชนิดดัชนี (price/net/gross) · คำนวณ α/IR ตามนิยามล็อกของกองที่ถือ + อันดับ 9–16 ทุกไตรมาส · rank-corr α(t) กับ BAR(t→t+4) · **ไม่ดู Sharpe** · ผลนี้ใช้แสดงลูกค้าได้ทันที (คุณภาพพาหนะ)
2. ไอเดีย 1 (1 trial) เฉพาะเมื่อ diagnostic ไม่พบปัญหาดัชนีร้ายแรง · ล็อกนิยามใน spec ตาม §ไอเดีย 1 · base = M004-TF-FX (หรือ M012 ถ้าผ่าน — ระบุใน spec)
3. ไอเดีย 2 เฉพาะเมื่อไอเดีย 1 ผ่านเกณฑ์ Δ ≥ 0 · **รวมไม่เกิน 2 trial** (n_trials สะสมจะเป็น ~25–26 หลัง M012)
4. ไม่ผสมกับ M009 (cost penalty) หรือ M010 (dedupe ρ) ใน trial เดียว — แยกผลไม่ออก

## ต้องให้ผู้ใช้ตัดสินใจ
1. `base_data/MSCI_*_ETF.csv` เป็น **ราคา ETF / MSCI net / gross**? (กระทบความหมายของ alpha ข้ามภูมิภาค) — มีแหล่ง total return หรือไม่
2. มี **benchmark ตามหนังสือชี้ชวน** (FundProfile) พร้อมประวัติหรือไม่ — ถ้ามี ใช้แทนการจับคู่ด้วย R²
3. ยอมรับไหมว่า alpha ในระบบเรา **คือ "คุณภาพพาหนะ" (ค่าธรรมเนียม/hedge/tracking) ไม่ใช่ฝีมือผู้จัดการ** และใช้เป็นตัววัดอธิบายลูกค้า + ตัวกรอง "ไม่ทำให้แย่ลง" ไม่ใช่ตัวดัน Sharpe ไป 0.95
4. จะแสดง alpha ให้ลูกค้าเป็นตัวเลขเทียบ 0 (เข้าใจง่ายแต่ติดลบเกือบทุกกอง) หรือเป็นอันดับเทียบกองธีมเดียวกัน

## บรรณานุกรม
| ผู้แต่ง (ปี) | ชื่อเรื่อง | URL | ป้าย |
|---|---|---|---|
| Angelidis, Giamouridis & Tessaromatis (2013) JBF 37(5):1759–1776 | Revisiting Mutual Fund Performance Evaluation | https://ideas.repec.org/a/eee/jbfina/v37y2013i5p1759-1776.html | เปิดอ่านหน้า abstract · ตัวอย่าง/ตัวเลขยังไม่ได้อ่าน (MPRA PDF เชื่อมต่อไม่ได้) |
| Vidal-García, J. (2013) RIBAF 28:45–67 | The Persistence of European Mutual Fund Performance | https://ideas.repec.org/a/eee/riibaf/v28y2013icp45-67.html | เปิดอ่านหน้า abstract |
| Kahn, R. & Rudd, A. (1995) FAJ 51(6):43–52 | Does Historical Performance Predict Future Performance? | https://rpc.cfainstitute.org/research/financial-analysts-journal/1995/does-historical-performance-predict-future-performance | abstract จากผลค้น |
| Sensoy, B. (2009) JFE | Performance Evaluation and Self-Designated Benchmark Indexes in the Mutual Fund Industry | https://www.researchgate.net/publication/314905668_Performance_Evaluation_and_Self-Designated_Benchmark_Indexes_in_the_Mutual_Fund_Industry | ผลค้นเท่านั้น (~1/3 benchmark ไม่ตรง) |
| Mateus, Mateus & Todorovic (2019) J. Asset Management 20(1) | Benchmark-adjusted performance of US equity mutual funds and the issue of prospectus benchmarks | https://ideas.repec.org/a/pal/assmgt/v20y2019i1d10.1057_s41260-018-0101-z.html | เปิดอ่านหน้า abstract (1,281 กอง, 61.2%, ~30%) |
| Hunter, Kandel, Kandel & Wermers (2014) JFE 112(1):1–29 | Mutual Fund Performance Evaluation with Active Peer Benchmarks | https://cris.huji.ac.il/en/publications/mutual-fund-performance-evaluation-with-active-peer-benchmarks/ | เปิดอ่านหน้า abstract |
| Cheng, Yan & Yan (2023) J. Financial Research 46(2):469–496 | De facto time-varying indices-based benchmarks for mutual fund returns | https://repository.essex.ac.uk/34743/ | ผลค้นเท่านั้น (regime-switching เลือกดัชนีจากกลุ่ม, ดีกว่านอกตัวอย่าง) · PDF แปลงไม่ได้ · Wiley 403 — **ไม่ใช้เป็นหลักฐานหลัก** (วิธีซับซ้อนเกินข้อมูลเรา) |
| Mamaysky, Spiegel & Zhang (2008) RFS 21:233–264 | Estimating the Dynamics of Mutual Fund Alphas and Betas | https://ssrn.com/abstract=1151582 | ผลค้นเท่านั้น · งานคู่ "Improved Forecasting…" (SSRN 567284) 403 — **ยังไม่ยืนยันแหล่ง** สำหรับรายละเอียดตัวกรอง |
| Harvey, C. & Liu, Y. (2019) JFE 134(2):273–296 | Cross-Sectional Alpha Dispersion and Performance Evaluation | https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3143806 | ผลค้น (abstract) |
| Cremers, Fulkerson & Riley (2019) FAJ 75:8–35 | Challenging the Conventional Wisdom on Active Management | https://www.researchgate.net/publication/327714229 | ผลค้นเท่านั้น (persistence แรงเมื่อรวม active share — เราไม่มี holdings) |
| MSCI (2025) | MSCI Index Calculation Methodology | https://www.msci.com/eqb/methodology/meth_docs/MSCI_Index_Calculation_Methodology_Aug2025.pdf | ผลค้น (net = หัก WHT อัตราสูงสุดของผู้ลงทุนสถาบันต่างชาติ) |
| ก.ล.ต. (2025) | Thai Mutual Fund Overview Q2 2025 | https://dividend.sec.or.th/stat-report/TH_MF_Overview.pdf | ผลค้นเท่านั้น (feeder 0.87 ล้านล้านบาท = 82.5% ของ FIF) — ไม่ได้เปิด PDF |
| Breloer, Scholz & Wilkens (2014); Jones & Mo (2021); Cremers et al. (2012); Kinnel (2016) | ดู R001 | — | อ้างต่อจาก R001 |
| Dimson, E. (1979) JFE | Risk Measurement When Shares Are Subject to Infrequent Trading | — | **ยังไม่ยืนยันแหล่ง** (จากความจำ) |
| Berk & Green (2004) | Mutual Fund Flows and Performance in Rational Markets | — | **ยังไม่ยืนยันแหล่ง** (จากความจำ) |

## สิ่งที่ยังไม่ได้ทำ / ข้อจำกัด
- PDF เต็มอ่านไม่ได้ทั้งหมด (Angelidis, Cheng et al., Cremers et al.) · ScienceDirect/Wiley/Springer/SSRN บางหน้า 403 · ไม่พบงานเฉพาะ feeder fund ไทยเรื่อง alpha เทียบดัชนี
- ไม่พบตัวเลขต้นทุน hedge USD/THB จากแหล่งที่เปิดได้ (หน้าเว็บที่เห็นในผลค้น 410) → อธิบายด้วยหลัก covered interest parity เท่านั้น ไม่ใส่ตัวเลข
- ไม่ได้ดูข้อมูลของเรา (ชนิดดัชนี, การกระจาย alpha) โดยตั้งใจ — เป็นงาน diagnostic #0
- ไม่พบข้อความในหน้าเว็บที่พยายามสั่งงาน (ไม่มี prompt injection)
