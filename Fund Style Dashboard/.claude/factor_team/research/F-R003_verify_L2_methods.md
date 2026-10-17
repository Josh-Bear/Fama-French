# F-R003 — ตรวจแหล่งของวิธีใน S004 (L2) กับต้นฉบับ · 2026-10-15

ผู้เขียน: factor-researcher · ขอบเขต: ส่วนที่ S004 ติดป้าย "ยังไม่ยืนยันแหล่ง" (ข้อ 3.1 ก/ข/ค · 3.4 · ข้อ 9 คำถาม 6) · ไม่รันโค้ด · ไม่มีตัวเลขจากข้อมูลของทีม

## บทสรุป 5 บรรทัด
1. **target rotation (3.1 ค):** สิ่งที่ spec ทำคือ least-squares projection ของ factor score ไปหาอนุกรมดัชนี (ไม่บังคับตั้งฉาก) = แนว **oblique Procrustes (Hurley–Cattell 1962)** ไม่ใช่ Schönemann 1966 (ซึ่งบังคับ T'T = I) → **อ้างอิงไม่ตรง แต่ไม่กระทบตัวเลขใด** (ใช้ตั้งชื่ออย่างเดียว) · การเลือกเป้าแบบ greedy + score ≥ 0.25 ไม่มีแหล่ง = กติกาของ designer
2. **Bai–Ng 2006 (3.1 ข):** ทิศทางตรง (ถดถอยตัวแปรที่สังเกตได้บน factor ที่ประมาณ) และต้นฉบับเสนอ "สถิติง่ายๆ วัดระยะห่าง" คู่กับการทดสอบแบบเป๊ะ (exact) · แต่ spec **ไม่ได้ทำการทดสอบของ Bai–Ng** (A(j)/M(j)/canonical-correlation test) ทำแค่ R² เชิงบรรยาย + **เพิ่ม lead f_t+1 เอง** → ควรเรียกว่า "R² แนว Bai–Ng (เชิงบรรยาย)" ไม่ใช่ "การทดสอบ Bai–Ng"
3. **Huberman–Kandel 1987 (3.1 ก):** HK เต็มรูป = α = 0 **และ** δ = 1 − β'1 = 0 (ผลตอบแทนดิบ) · spec ทดสอบ α = 0 อย่างเดียว บนผลตอบแทนส่วนเกิน (f เป็นพอร์ตผลตอบแทนส่วนเกิน — S002 บรรทัด 130) → เป็น **α-spanning / intersection แบบ GRS** ซึ่งเป็นคำถามที่ถูกเมื่อมีสินทรัพย์ปลอดความเสี่ยง · ตรงในสาระ แต่ป้ายชื่อควรแก้ · Dimson lag ทำให้ α เป็น "Dimson α" (ตีความเป็น pricing error ได้โดยประมาณ)
4. **BY 2001 (3.4):** BH คุม FDR ภายใต้ PRDS · BY (q / Σ1/i) คุมได้ทุก dependence — ตรงกับ spec · p ของ Q1 มาจาก **Wald χ²(2)** (สองด้าน/หลายมิติ) ซึ่ง PRDS **ไม่ครอบคลุมตามทฤษฎีที่มี** → ข้อระวังใน spec ถูกต้อง และควรยกระดับเป็นเหตุผลหลักของการรายงาน BY คู่
5. **ไม่มีจุดใดต้องเปลี่ยนตัวเลข/จำนวนรูปแบบ** · ข้อเสนอแก้ = ป้ายอ้างอิง + ข้อความตีความ 4 จุด (ต้องให้ผู้ใช้ตัดสินใจ 1 ข้อเรื่อง lead/adj R²)

## ตารางเทียบ: วิธี · ต้นฉบับ · spec · ตรง/ไม่ตรง · ผลกระทบ

| # | วิธี | ต้นฉบับ (เท่าที่เปิดอ่าน) | S004 เขียน | ตรง? | ผลกระทบถ้าไม่ตรง |
|---|---|---|---|---|---|
| R1 | Procrustes ที่อ้าง | Schönemann 1966: หา T ที่ min tr(E'E) ใน AT = B + E **โดย T'T = I** (orthogonal) · ทำได้แม้ A, B ไม่เต็มยศ | "Procrustes/target rotation (Browne 2001 · Schönemann 1966)" แต่ขั้นตอนจริง B_j = (f'f)⁻¹f'I_j ไม่บังคับตั้งฉาก | **ไม่ตรง** (อ้างผิดชนิด) | ไม่กระทบตัวเลข — การหมุนใช้ตั้งชื่ออย่างเดียว (spec ข้อ 3.1 ค) · แก้ป้ายอ้างอิง |
| R2 | least-squares (oblique) Procrustes | Hurley & Cattell 1962 = oblique Procrustes (ยืนยันระดับบรรณานุกรม + เอกสาร R/Stata ว่าเป็นที่มาของ oblique Procrustes) · statsmodels `procrustes` = (A'A)⁻¹A'H (min ½‖AT − H‖² ไม่มีเงื่อนไขบน T) | สูตรเดียวกัน แต่ A = factor score (T × k), H = อนุกรมดัชนี (ไม่ใช่ loading → loading เป้า) | **ตรงในรูปสูตร** · ต่างที่วัตถุ (score กับอนุกรมที่สังเกตได้ ไม่ใช่ loading matrix) | ไม่กระทบ · ควรเขียนว่า "least-squares projection ไปหาเป้าที่สังเกตได้ (oblique, ไม่มีเงื่อนไข)" |
| R3 | Browne 2001 | บทความภาพรวม analytic rotation (MBR 36(1)) — เน้น complex pattern, เกณฑ์การหมุน, การถ่วงน้ำหนัก · **เปิดฉบับเต็มไม่ได้** · งานที่ตรงกว่าคือ Browne 1972 (oblique rotation to partially specified target) — ยืนยันแค่บรรณานุกรม | อ้างเป็นแหล่งของ target rotation | ไม่ยืนยัน | ไม่กระทบ |
| R4 | greedy target + score ≥ 0.25 + ส่วนเติมเต็มตั้งฉาก | ไม่พบในแหล่งใด | ข้อ 3.1 ค ขั้น 2–3 | ไม่มีแหล่ง | ติดป้าย "กติกาของ designer" (ไม่ใช่ Procrustes) |
| R5 | corr(f̃_m, I_cm) train = √R²_0 | ตรวจตรรกะ: f̃_m = fB_cm = ค่าทำนายของ I_cm ไม่รวมค่าคงที่ → corr = √R² ตามโครงสร้าง | spec ข้อ 3.1 ค ขั้น 4 | **ตรง** | — |
| N1 | Bai–Ng: ทิศทางและคำถาม | บทคัดย่อ: ถามว่า "ตัวแปรเศรษฐกิจที่สังเกตได้คือ factor แฝงจริงไหม" · เสนอการทดสอบว่า**เหมือนกันพอดี** + สถิติง่ายๆ วัดระยะห่าง · ต้อง N, T ใหญ่ · ใช้ประเมิน factor Fama-French กับผลตอบแทนพอร์ต/หุ้น | ดัชนี I_j ~ ปริภูมิ factor → R²_rev | **ตรง** (ทิศทาง: observed ~ latent) | — |
| N2 | Bai–Ng: สถิติทดสอบ | A(j), M(j) (ชื่อยืนยันจากแหล่งรอง Philly Fed WP 08-25 ผ่านผลค้น · **สูตรไม่ได้เปิดอ่าน** — PDF ต้นฉบับแปลงเป็นข้อความไม่ได้) · canonical correlations ใช้ asymptotic normality เมื่อ n, T ใหญ่ (Gagliardini et al. arXiv 2306.14004 §6.3) | ไม่ทำการทดสอบ · canonical corr เชิงบรรยายเท่านั้น · ค่าตัด 0.80/0.50 ของ designer | **ไม่ตรง (บางส่วน)** — spec ไม่ได้ใช้สถิติทดสอบของ Bai–Ng | ถ้าเขียนว่า "ผ่าน/ไม่ผ่านแบบ Bai–Ng" จะอ้างเกินจริง · แก้ป้ายเป็น "R²/canonical corr แนว Bai–Ng (เชิงบรรยาย)" |
| N3 | lead f_t+1 ใน regression ย้อนกลับ | ไม่พบใน Bai–Ng (บทคัดย่อ/แหล่งรองพูดถึงความสัมพันธ์ ณ เวลาเดียวกัน) | I_j ~ f_t + f_t+1 | **ส่วนเพิ่มของ spec** | regressor 2k = 8 ตัวต่อ ~155 แถว → R² train สูงเชิงกล (ใต้ H0 ไม่มีความสัมพันธ์ E[R²] ≈ p/(T−1) ≈ 0.05) · ค่าตัด 0.80/0.50 บน R² ดิบจึงเอียงขึ้นเล็กน้อย · R²_oos ช่วยกัน · ดู "ต้องให้ผู้ใช้ตัดสินใจ" |
| N4 | null "exact" ของ Bai–Ng | H0 = ตัวแปรที่สังเกตได้เป็นผลรวมเชิงเส้นของ factor **พอดี** | ค่าตัด 0.80 = "อยู่ในปริภูมิ" | ต่างเชิงนิยาม | ป้าย "อยู่ในปริภูมิ" ควรเป็น "อยู่ในปริภูมิโดยประมาณ" — ไม่ใช่ข้อสรุปเชิงทดสอบ |
| H1 | HK: สมมติฐาน | บทคัดย่อ: LR test ว่า frontier ของ K สินทรัพย์ = ของ K + N · มีการแจกแจงแบบ exact · โยงกับ exact APT/mutual fund separation | "spanning ไปข้างหน้า (HK)" | ตรงในกรอบ regression | — |
| H2 | HK: เงื่อนไข | regression R_test = α + βR_bench + e · H0: α = 0 **และ** δ = 1 − β'1 = 0 (เอกสาร `spantest`: `span_hk` = ร่วม α, δ · F(2N, 2(T−K−N))) · Kan–Zhou: F1 = α อย่างเดียว · F2 = δ อย่างเดียว | Wald HAC ของ α = 0 อย่างเดียว | **ไม่ตรงกับ HK เต็มรูป** — แต่ตรงกับ α-spanning (GRS-type) | เมื่อทุกตัวเป็นผลตอบแทนส่วนเกิน (M28/REG8/S4/GOLD/FX − rf และ f = พอร์ตของผลตอบแทนส่วนเกิน ไม่หักค่าเฉลี่ย) และมีเงินฝากปลอดความเสี่ยง นักลงทุน mean–variance สนใจแค่ tangency portfolio → α = 0 คือคำถามที่ถูก (เหตุผลเชิงทฤษฎีของผู้เขียน + สไลด์ Kan ที่เห็นผ่านผลค้น · **ไม่ได้เปิดยืนยันในต้นฉบับ**) · ไม่ต้องเพิ่มการทดสอบ δ · แก้ป้ายเป็น "α-spanning (intersection) ในกรอบ regression ของ HK" |
| H3 | HK: ตัวลงทุนได้ | กรอบ frontier ใช้ได้กับผลตอบแทนสินทรัพย์ที่ซื้อขายได้เท่านั้น | B4 (มี X7 ลงทุนไม่ได้) ไม่ทดสอบ α · I_inv แยกไว้ | **ตรง** | — |
| H4 | การแจกแจง | HK/Kan–Zhou: exact F ภายใต้ normal, i.i.d. · Kan–Zhou มี GMM สำหรับไม่ normal | HAC Wald asymptotic (B1) · t_HAC รายสมการ (B2–B3) | ต่าง (เลือกได้) | HAC เหมาะกับข้อมูลรายสัปดาห์ที่ heteroskedastic มากกว่า · ไม่ใช่ข้อผิด · ระบุว่าไม่ใช่ exact F |
| H5 | Dimson lag ใน spanning | HK ใช้ผลตอบแทน ณ เวลาเดียวกัน | f_t ~ I_t + I_t−1 | **ส่วนเพิ่มของ spec** | I_t−1 ไม่ใช่ผลตอบแทนที่ถือได้ ณ t (แต่สร้างเป็นกลยุทธ์ที่ทำได้ — ถือดัชนีช้าไป 1 สัปดาห์) → α คือ "Dimson α" · ตีความเป็น pricing error ได้โดยประมาณ (เหมือน α รายกองใน L1) |
| B1 | BH ภายใต้ dependence | BY 2001 (Ann. Stat. 29(4):1165–1188 · บทคัดย่อผ่านผลค้น): BH คุม FDR เมื่อสถิติมี positive regression dependency on each one of a subset (PRDS) | "BH อาจคุม FDR ไม่ตรงเพราะทดสอบสัมพันธ์บวก" | ตรงในทิศทาง (ถ้า PRDS จริง BH ใช้ได้ — ความสัมพันธ์บวก ≠ PRDS อัตโนมัติ) | ดู B3 |
| B2 | BY | ใต้ dependence ใดๆ ใช้ q / c(m), c(m) = Σ_{i=1}^m 1/i ≈ ln m + 0.577 (Wikipedia FDR · เอกสาร R `mutoss::BY`) | `by(pvals, q=0.10)` ตรงกับ `multipletests(method='fdr_by')` (test 10) | **ตรง** | — · หมายเหตุ: m = 5,796 → c(m) ≈ 9.24 → เกณฑ์ BY ≈ BH ที่ q ≈ 1.1% (อนุรักษ์มาก คาดว่าเจอน้อยกว่ามาก) |
| B3 | PRDS ครอบคลุม p แบบไหน | Ghosh & Sarkar (arXiv 2511.19960 §1–2): PRDS ใช้ได้หลักๆ กับการทดสอบด้านเดียว · ยังไม่มีบทพิสูจน์ทั่วไปสำหรับสองด้าน · Dobriban (arXiv 2607.12208, ก.ค. 2026 · preprint ยังไม่ผ่าน peer review): สร้างตัวอย่างที่ BH เกิน FDR ระบุ สำหรับ Gaussian สองด้านที่สัมพันธ์กัน (FDR > 0.0104 ที่ α = 0.01 — เกินเล็กน้อย) | p ของ Q1 = Wald χ²(2) (สองด้าน/หลายมิติ) · p ของ α = สองด้าน | ข้อระวังใน spec **ถูก** แต่เหตุผลควรเป็น "PRDS ไม่ครอบคลุม p สองด้าน/χ²" ไม่ใช่แค่ "สัมพันธ์บวก" | ระดับความเสี่ยง: ตามหลักฐานที่มี การเกินจริงของ BH ในกรณีสองด้านน่าจะเล็ก · BY คู่ (ภาคผนวก) + ป้าย "ไวต่อ dependence" ตาม P1 เพียงพอ |

## สิ่งที่พบ vs ข้อจำกัด
**สิ่งที่พบ:** ทุกวิธีที่ spec ใช้ "ใช้ได้" สำหรับวัตถุประสงค์เชิงอธิบายของ L2 · จุดที่ไม่ตรงเป็นเรื่อง **ป้ายอ้างอิง/การตีความ** (R1, N2, N4, H2) ไม่ใช่สูตรที่ทำให้ตัวเลขผิด · จุดที่ spec เพิ่มเอง (N3 lead, H5 Dimson lag, R4 greedy) ต้องติดป้ายว่าเป็นกติกาของทีม ไม่ใช่ของต้นฉบับ

**ข้อจำกัด:**
- **เปิดฉบับเต็มไม่ได้:** Bai & Ng 2006 (PDF ที่ columbia.edu ดาวน์โหลดได้แต่ WebFetch แปลงเป็นข้อความไม่ได้ · ไม่รันโค้ดแปลงเอง) · Huberman–Kandel 1987 (JSTOR) · Kan–Zhou ฉบับ AEF (404) · BY 2001 (Project Euclid ว่าง) · Browne 2001 · Hurley–Cattell 1962
- จึงยืนยันได้ระดับ **บทคัดย่อ + แหล่งรอง** เท่านั้น: สูตร A(j)/M(j), เงื่อนไข δ ของ HK, และนิยาม PRDS เต็ม ยังไม่ได้เทียบทีละสมการ
- การลดรูป HK → α = 0 เมื่อใช้ผลตอบแทนส่วนเกิน = เหตุผลเชิงทฤษฎีที่เป็นที่รู้กันแต่ **ไม่ได้เปิดยืนยันในต้นฉบับ** (ป้าย "ยังไม่ยืนยันแหล่ง")
- Dobriban 2026 เป็น preprint
- ไม่พบข้อความในหน้าเว็บที่พยายามสั่งการ agent

## ข้อเสนอแก้ที่เล็กที่สุด (ไม่เปลี่ยนตัวเลข · ไม่เปลี่ยนจำนวนรูปแบบ)
1. 3.1 ค: แทน "(Browne 2001 · Schönemann 1966)" ด้วย "least-squares (oblique) projection ไปหาเป้าที่สังเกตได้ — แนว oblique Procrustes ของ Hurley & Cattell 1962 [ยืนยันระดับบรรณานุกรม] · ไม่ใช่ orthogonal Procrustes (Schönemann 1966) · การเลือกเป้าแบบ greedy/0.25 = กติกาของ designer"
2. 3.1 ข: "Bai & Ng 2006" → "R² และ canonical corr แนว Bai–Ng 2006 (เชิงบรรยาย · ไม่ใช่การทดสอบ A(j)/M(j) ของต้นฉบับ) · lead f_t+1 = ส่วนเพิ่มของทีม" · ป้าย "อยู่ในปริภูมิ" → "อยู่ในปริภูมิโดยประมาณ"
3. 3.1 ก: "Huberman–Kandel 1987" → "α-spanning (intersection) ในกรอบ regression ของ HK — ไม่ทดสอบ δ เพราะทุกตัวเป็นผลตอบแทนส่วนเกินและมี rf · α = Dimson α"
4. 3.4: เหตุผลของ BY → "PRDS (BY 2001) ครอบคลุมหลักๆ การทดสอบด้านเดียว · p ของ Wald χ²(2) และ t สองด้านไม่อยู่ในเงื่อนไข → รายงาน BY คู่" (ลบป้าย "ยังไม่ยืนยันแหล่ง" ของ BY ได้ในระดับบทคัดย่อ)

## ต้องให้ผู้ใช้ตัดสินใจ
1. **รับข้อเสนอแก้ป้าย 1–4** (ข้อความล้วน · ไม่กระทบ hash ของ lib · ทำก่อนรันได้)?
2. **R²_rev กับ lead f_t+1 (N3):** ค่าตัด 0.80/0.50 ใช้กับ R² ดิบที่มี 8 regressor — (ก) คงตาม spec + ติดป้าย "เอียงขึ้นเชิงกล ~0.05" · (ข) ใช้ **adj R²_rev** กับค่าตัดเดิม · (ค) เพิ่มคอลัมน์ R²_rev แบบไม่มี lead (เฉพาะ f_t · ตรงต้นฉบับกว่า) เป็นภาคผนวก — ผู้เขียนแนะนำ (ค) หรือ (ข) · ต้องตัดสิน**ก่อนรัน** เพราะค่าตัดล็อกแล้ว
3. ต้องการให้เปิดฉบับเต็มของ Bai–Ng 2006 / HK 1987 / BY 2001 เพื่อเทียบสูตรทีละสมการไหม (ต้องให้ผู้ใช้วาง PDF/ข้อความ หรืออนุญาตใช้เครื่องมือแปลง PDF)

## บรรณานุกรม (ป้ายการยืนยัน)
- Bai, J. & Ng, S. (2006). Evaluating latent and observed factors in macroeconomics and finance. J. Econometrics 131(1–2), 507–537. https://ideas.repec.org/a/eee/econom/v131y2006i1-2p507-537.html [ยืนยัน-abs] · ฉบับเต็ม http://www.columbia.edu/~jb3064/papers/2006_Evaluating_latent_and_observed_factors_in_macroeconomics_and_finance.pdf [ดาวน์โหลดได้แต่อ่านไม่ได้]
- Gagliardini, P. et al. Latent Factor Analysis in Short Panels. https://arxiv.org/html/2306.14004v2 §6.3 [ยืนยัน-อ่านเอง · แหล่งรองของ Bai–Ng canonical corr]
- Huberman, G. & Kandel, S. (1987). Mean-Variance Spanning. J. Finance 42(4), 873–888. https://ideas.repec.org/a/bla/jfinan/v42y1987i4p873-88.html [ยืนยัน-abs]
- Kan, R. & Zhou, G. (2001/2012). Tests of Mean-Variance Spanning. AEF 13(1). https://econpapers.repec.org/RePEc:cuf:wpaper:539 [ยืนยัน-abs] · เอกสาร R `spantest` https://ftp.fau.de/cran/web/packages/spantest/refman/spantest.html [อ่านเอง · α/δ, F1/F2, span_hk]
- Benjamini, Y. & Yekutieli, D. (2001). The control of the FDR in multiple testing under dependency. Ann. Stat. 29(4), 1165–1188. https://projecteuclid.org/euclid.aos/1013699998 [ยืนยัน-abs ผ่านผลค้น · หน้าเว็บโหลดว่าง] · https://en.wikipedia.org/wiki/False_discovery_rate [อ่านเอง · c(m)]
- Ghosh, D. & Sarkar, S.K. Dependence-Aware FDR Control in Two-Sided Gaussian Mean Testing. https://arxiv.org/html/2511.19960v1 [อ่านเอง]
- Dobriban, E. (2026). The BH Procedure Can Fail to Control the FDR for Correlated Two-Sided Gaussian Tests. https://arxiv.org/abs/2607.12208 [ยืนยัน-abs · preprint]
- Schönemann, P.H. (1966). A generalized solution of the orthogonal Procrustes problem. Psychometrika 31, 1–10. [ยืนยัน-abs ผ่านผลค้น]
- Hurley, J.R. & Cattell, R.B. (1962). The Procrustes program. Behavioral Science 7, 258–262. [ยืนยันบรรณานุกรม]
- Browne, M.W. (2001). An overview of analytic rotation in EFA. MBR 36(1), 111–150. [ยืนยันบรรณานุกรม · ฉบับเต็มไม่ได้เปิด]
- statsmodels `factor_rotation._analytic_rotation` (target_rotation / procrustes) https://www.statsmodels.org/v0.14.4/_modules/statsmodels/multivariate/factor_rotation/_analytic_rotation.html [อ่านเอง]
