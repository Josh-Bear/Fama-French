# R5 — modeler: โต้แย้ง R5_researcher + แบบที่จะรัน (ฐาน M042-ENSDEF / M046-STACK5 · เป้า 4 ข้อ · ข้อมูลทอง clean_gold_v2)

ผู้เขียน: quant-modeler · 2026-10-12 · อ่านครบ: `agents/quant-modeler.md`, `DEBATE_BRIEF.md` (ส่วนท้าย + D0 GOLDFIX), `R4_modeler.md`, `R4_results.md`,
`R5_researcher.md`, `backtest/run_r5.py` (ทั้งไฟล์), `results/R5_d0_rebaseline.csv`, `R2.band_plan`, `r15.make_plan_F`/`sim_cases_x`, `r13.gc_signals`, `simulate_path`
· ตรวจเองแบบอ่านอย่างเดียว: `scratchpad/mod_r5chk.py` (จำลองเงื่อนไข ALLCLEAR จาก k, b, x, σ ใน `R4_overlay_log.csv` ทุก offset · **ไม่ได้ sim ผลตอบแทน**)
· ⚠ ไม่ blind: เห็นผลตอบแทนรายไตรมาส/ราย offset ของรอบ 4 และ D0 แล้ว · ตัวเลขฐานรอบนี้ = D0 (clean_gold_v2) เท่านั้น

## 0. ตรวจข้ออ้างของ researcher
| ข้อ | สิ่งที่อ้าง | ผลตรวจ |
|---|---|---|
| R5-1 | ALLCLEAR ที่ offset 0 ไม่ทำงานเลย (M042/M046) | **ยืนยัน** · 30 เดือนกลางไตรมาสที่ offset 0: เงื่อนไข k = 3 ∧ b = 0 จริง 6 เดือน (2024-05/07, 2025-07/08/10/11) แต่ทุกครั้ง x_held ≥ x_new (M042 = 1.0 · M046 = 0.937/0.798 = เพดาน VSL เดิม) → ขั้นไม่ถึง +0.25 · M036/M041 ก็ 0 ครั้ง |
| R5-1 | M042: offset 1 ทำงาน 3 ครั้ง (2023-12-29 0.25→1 · 2024-05-31 0.5→1 · 2025-06-30 0.25→1) · offset 2 3 ครั้ง (2023-12, 2024-03, 2025-06) | **ยืนยันทุกวัน/ทุกค่า** |
| R5-1 | ใช้กับ M046 ได้แบบเดียวกัน | **ไม่ตรง** · VSL ทำให้ x_new = m_VSL_q < 1: offset 1 ยัง 3 ครั้งแต่เป็น 0.25→**0.898**, 0.5→1.0, 0.25→**0.817** · offset 2 เหลือ **1 ครั้ง** (2025-06-30 0.25→1.0; 2023-12/2024-03 ขั้น 0.75→0.861/0.94 < 0.25) → ผลบวกของ M046 เล็กกว่า proxy ของ researcher (ซึ่งคิดจาก x_new = 1) ราว 20–30% |
| §0.4/D0 | ซ่อม K-GOLD-C(A) แล้ว ราคาไม่ค้าง | **ยังค้างบางส่วน**: `clean_gold_v2` ต่อราคาแค่ถึง 2024-05-16 (วันสุดท้ายของ C) ไม่ใช่ "ถึงวันสุดท้ายที่ A มีข้อมูล" ตามข้อเสนอเดิม → offset 1 (ถือ C จาก 2024-05-03) ยัง mark ราคา 05-16 ถึง ส.ค. 24 · K-GOLD-A(A) 2024-05-31→07-31 = **+2.9%** · กระทบ (ก) ฐาน M046 off1 ต่ำเกินจริงเล็กน้อย (~+0.01–0.02) (ข) **ALLCLEAR 2024-05-31 ที่ offset 1 ขายทองราคาค้าง → ส่วนได้ของครั้งนั้นพองได้ถึง ~1.4 pt (~0.03 Sharpe)** ซึ่งเทียบกับระยะขาด 0.043 ได้ → ต้องรายงานแยก (§3) · ไม่แก้เอง (เกินขอบเขตที่ผู้ใช้อนุมัติ) |

## 1. โต้แย้งทีละไอเดีย
- **D0 GOLDFIX — ทำแล้ว** (ผู้ใช้อนุมัติ) · **R5-4 GOLDCLS — ตัด** (ผู้ใช้เลือก splice) · ข้อค้างเรื่องราคาค้างหลัง 05-16 ส่งเป็นคำถามผู้ใช้ (§5)
- **R5-1 ALLCLEAR — รัน (หลัก)**: กลไกไม่แตะ offset 0 โดยข้อมูล (ตรวจแล้ว) → ข้อ 1–2 คงที่ทุกบิตเมื่อ offset 0 ทำงาน 0 ครั้ง · ไม่มีพารามิเตอร์ใหม่ (k = 3 ∧ b = 0 = สถานะบนสุดของสัญญาณเดิม · ขั้น 0.25 = ขั้นตาราง GC75)
  · ข้อแย้ง: (1) ออกแบบหลังเห็นว่า offset 1 เสียหลังจุดต่ำ = เหตุการณ์ 3 ครั้ง/offset → ส่วนได้คือ noise ระดับเดียวกับระยะขาด (2) ความไม่สมมาตร (ขึ้นได้กลางไตรมาส ลงไม่ได้) ไม่มีหลักฐานตรง
  (3) ซื้อกองหุ้นกลางไตรมาส = ค่าธรรมเนียมซื้อเพิ่ม (~0.3–0.9 pt/ครั้ง) · (4) กับ M046 ได้น้อยกว่าตามตาราง §0 · **คาด M049 off1 0.88–0.95 (≈ เหรียญหัวก้อย) · M048 off1 0.80–0.88 (ไม่น่าผ่าน)**
- **R5-2 SR3M — รัน 1 ตัวบน M046 (ผู้สมัคร)**: ตัวเดียวที่แก้ต้นเหตุ (การคัด 3 กองซ้ำกันข้ามเดือนแค่ ~50%) และพารามิเตอร์ = โครงสร้าง (3 เดือน = 3 offset)
  · ข้อแย้ง: เปลี่ยนการคัดของ offset 0 → ข้อ 2 ของ M046 มี headroom แค่ +0.044 · บทเรียน R1/R2: แตะการคัดกอง = ผล ±0.1–0.2 แบบสุ่ม · **คาด off0 ลด, ข้อ 2 หลุด ~60%**
  · ปรับจาก researcher 1 จุด: SR12′ ที่เดือน m อ่านจาก **FundCode ตัวแทนเดียวกับ ณ t** (ไม่ให้ class เปลี่ยนข้ามเดือน → ไม่ผสม class ต่างค่าธรรมเนียม)
- **R5-3 STACK7 (M046 + ALLCLEAR) — รัน · เห็นด้วยว่าเป็นทางหลัก** (ประเมินโอกาสผ่าน 4 ข้อของผม **≈ 45–55%** ต่ำกว่า researcher เพราะ §0 แถว 3–4)
- **R5-5 SR3M-GATED — รันแบบมีเงื่อนไข** (§3 M051) · ไม่รันถ้าไม่มีทางผ่าน
- **ไม่รัน M041 + ALLCLEAR**: M041 ตกแค่ข้อ 2 (1.2924) ซึ่งเป็นเส้นทาง offset 0 ล้วน · ALLCLEAR ไม่แตะ offset 0 → sh_c2 เท่าเดิมทุกบิต = ผ่านไม่ได้โดยกลไก
- "ไม่ควรลอง" ของ researcher: เห็นด้วยทั้งหมด (TR3, SMOOTH, MCHK, HOLD18, สัญญาณสิ้นไตรมาสปฏิทิน, N = 5, กฎเฉพาะ offset 1)

## 2. โค้ด (ต่อใน `run_r5.py` · ส่วน full หลังบล็อก `if STAGE == "d0": ... return` · ไม่แก้ฟังก์ชันเดิม · ใช้ `clean_gold_v2` ตามที่เป็นอยู่)
**Cfg** เพิ่มท้าย: `aclr: bool = False` · `sr3m: int = 1` (1 = ปิด) · assert `not (cfg.sigs and cfg.sr3m > 1)` · assert `cfg.aclr ⇒ cfg.canary and not (cfg.vote or cfg.smooth > 1 or cfg.rb2 or cfg.defmmf)`
**make_xfun**: เก็บ `xf.mv[qi] = m` (ตัวคูณ VSL · 1.0 ถ้าปิด) และ `xf.xq[qi] = x` (ค่า x ที่คืน) — ไม่เปลี่ยนการคำนวณใดๆ

### 2.1 ALLCLEAR (`add_allclear(plan, Ek, Xk, GSk, sl, xf, cfg, k)` · เรียกใน `plans3` หลัง `gc_gold_plan_x` **ก่อน** `R2.band_plan`)
```
cal = Ek["calendar"]; q = Ek["q15"]; MEND = fs.month_end_points(cal, cal[-1], 10**4)        # สิ้นเดือนทุกเดือน (trading day)
ksig(m) = int(r13.gc_signals({**Ek, "q16": [m]})["k"].iloc[0])                              # GC75 k เดิม ณ m (ข้อมูล ≤ m)
bsig(m) = canary_ens(m) if cfg.ens else canary_b(m)
out = []
for qi, p in enumerate(plan):                       # plan = ผลของ gc_gold_plan_x (หลัง make_plan_F 2 ชั้น · ยังไม่ band) · assert p["t"] == q[qi]
    out.append(p); xh = xf.xq[qi]
    t_nx = q[qi+1] if qi+1 < len(q) else None
    mids = [m for m in MEND if m > q[qi] and (t_nx is None or m < t_nx)][:2]
    mids = [m for m in mids if common.execution_date(cal, m) <= Ek["months"][-1]]       # ไม่สร้าง entry หลังจุดวัดสุดท้าย
    for m in mids:
        if ksig(m) == 3 and bsig(m) == 0:
            xn = max(0.25, GC75[3] * xf.mv[qi])                                             # = สูตร xf ที่ k=3, b=0 ด้วย VSL ของไตรมาส
            if xn >= xh + 0.25 - 1e-12:
                w = sl[qi]; wf = {fc: xn*float(v) for fc, v in w.items() if v > 0}           # ชุดกอง/น้ำหนักในขาหุ้นของไตรมาสเดิม (ไม่คัดใหม่)
                left = xn*(1-float(w.sum())) if 1-float(w.sum()) > 1e-9 else 0.0
                if (1-xn) + left > 0: wf["__CASH__"] = (1-xn) + left
                e0 = {"t": m, "e": common.execution_date(cal, m), "weights": wf}
                g1, _ = r15.make_plan_F([e0], {0: GSk[qi]})                                  # ทอง = ชุด/สัดส่วนทองของไตรมาส qi (กติกา AUM เดิม · ไม่เลือกใหม่)
                pe = r15.make_plan_F(g1, {0: Xk["sels"]["FAUM"][qi]})[0][0]
                assert abs(sum(pe["weights"].values()) - 1) < 1e-9 and "__CASH__" not in pe["weights"]
                pe["aclr"] = True; out.append(pe); xh = xn
                aclr_log.append({"model": tag, "offset": k, "qi": qi, "m": m, "k_m": 3, "b_m": 0.0, "x_held": xf.xq[qi], "x_new": xn})
return out                                          # ต่อด้วย R2.band_plan(out, nav_all, arrays, BAND) ตามเดิม (entry กลางไตรมาสโดน BAND5 แบบเดียวกัน)
```
- หลังยิงหนึ่งครั้ง เดือนที่สองยิงซ้ำไม่ได้ (xn เท่าเดิม) · ไม่มีการลด x กลางไตรมาส · entry ถัดไป (ไตรมาส qi+1) ไม่เปลี่ยน target แต่ BAND5 วัด drift จาก entry กลางไตรมาส (พฤติกรรมถูกต้อง)
- `sim_cases_x`/`simulate_path` รับ entry ใดๆ ที่เรียงตาม e (ตรวจโค้ดแล้ว: วนตาม plan · mark สิ้นเดือน < next_e) · assert `e` เรียงเพิ่มขึ้นเคร่งครัดและ e ของ entry กลางไตรมาส < e ของไตรมาสถัดไป
- `R2.eq_sets` ของ plan ที่มี entry ใหม่: เปรียบเทียบเฉพาะ entry ที่ไม่มี `aclr` (ชุดของ entry aclr = ชุดของไตรมาสนั้น — assert ด้วย)

### 2.2 SR3M (ใน `select_sig` หลังบรรทัด `ranks = wt.rank_families(reps)` · `aux["ctx_by_t"] = {c["t"]: c for k in envs for c in envs[k][0]["ctx_h"]}` · assert คีย์ไม่ซ้ำ)
```
if cfg.sr3m > 1:
    ms = fs.month_end_points(cal, t, cfg.sr3m); assert ms[-1] == t
    P = []
    for m in ms:                                   # m ≤ t → point-in-time
        cm = ctx if m == t else aux["ctx_by_t"].get(m)
        if cm is None: continue                    # ช่วงต้น (ก่อน ctx แรกของ offset นั้น) → ใช้เดือนที่มี
        s = cm["i_t"].set_index("FundCode")["SR12"]; assert s.index.is_unique
        P.append(pctrank({f: s.get(reps[f]["FundCode"], np.nan) for f in reps}))
    P = [x.where(x.notna(), P[-1]) for x in P]     # P[-1] = เดือน t (มีครบทุก family)
    ranks = wt.rank_families({f: {**reps[f], "signal": float(sum(P)[f] / len(P))} for f in reps})
```
- ต่อจากนี้ (pool ≤ 9, S_keep, ρ_adj filler, ERC, cap) เหมือนเดิมทุกบรรทัด · ช่องทางเดียวกับ `cfg.sigs` (ซึ่ง regression แล้วว่า `sigs=("SR",)` == ฐานทุกบิต)

## 3. regression (ไม่ผ่าน = หยุด ไม่บันทึก trial) · ทุกตัวใต้ `clean_gold_v2`
1. บล็อก d0 เดิมผ่าน (M033 · M036 · M041 · M042 1.5471 · M046 1.5874) · เพิ่ม assert ค่าฐานใหม่: M042 off **1.921938 / 0.746583 / 1.230990** · M046 **1.986320 / 0.856620 / 1.321172** (atol 5e-5)
   · sh_c2 M042 **1.312888** · M046 **1.343706** · Sharpe M042 **1.5470606** · M046 **1.5873870** (|Δ| < 5e-7)
2. ปิดสวิตช์: `Cfg(canary, ens, aclr=False, sr3m=1)` == p42 ทุกบิต · `Cfg(vsl, canary, ens, aclr=False, sr3m=1)` == p46 ทุกบิต · `sr3m=1` ผ่าน `select_sig` แล้ว ranks == เดิม
3. ข้อมูลสัญญาณ: สำหรับทุก env j และทุก t ใน `q15` ของ j: `ksig_k(t) == envs[j].sig.k(t)` สำหรับทุก k (k ข้าม offset ตรงกัน) และ `bsig(t)` == b ใน olog ของ M042
4. ALLCLEAR เปิด: **offset 0: จำนวนครั้ง = 0 และ plan[0] == p42[0] / p46[0] ทุกบิต** → Sharpe, sh_c2, off0 เท่าฐานถึง 1e-12
   · รายการวันที่ยิง (atol x 1e-3) ต้องตรงกับที่ผมตรวจ: **M048** off1 {2023-12-29 0.25→1, 2024-05-31 0.5→1, 2025-06-30 0.25→1} · off2 {2023-12-29 0.75→1, 2024-03-29 0.75→1, 2025-06-30 0.25→1}
     **M049** off1 {2023-12-29 0.25→0.898, 2024-05-31 0.5→1.0, 2025-06-30 0.25→0.817} · off2 {2025-06-30 0.25→1.0} · ไม่ตรง = หยุดและรายงาน (ไม่แก้ให้ตรง)
5. SR3M: ไม่ assert eq_sets (ตั้งใจเปลี่ยน) · assert ทุก entry Σ = 1 และ fallback เท่าเดิมหรือรายงาน

**รายงานเพิ่มต่อแบบ**: off0/1/2 แบบ full **และ c0** · `off_min` · `pass4 = off_min ≥ 0.9` · ต้นทุน bp/ปี ต่อ offset · จำนวนครั้งที่ ALLCLEAR ยิงต่อ offset + `aclr_log` → `results/R5_aclr_log.csv`
· ⚠ **แยกผลครั้ง 2024-05-31 offset 1**: น้ำหนัก K-GOLD-C(A) ที่ถูกขาย × ผลตอบแทน K-GOLD-A(A) จาก e ของ entry นั้นถึง e ไตรมาสถัดไป (= ส่วนที่พองจากราคาค้าง) · และ off1 แบบ "ไม่นับครั้งนั้น" (รันซ้ำโดยตัด entry นั้นออก · ไม่นับ trial)
· SR3M: ชุดกองซ้ำกับฐานต่อ offset และ "ความซ้ำของชุดกองเดือนติดกันข้าม offset" (เทียบ 51% ของ researcher) · Δ รายไตรมาส vs ฐาน offset 0/1/2 → `results/R5_qdelta.csv`
· trials: backup แล้ว append แบบ R4 · **assert n == 85 ก่อน** · spec_file = `debate/R5_modeler.md` · notes ใส่ sh_c2/off_mean/off_min/pass1–4 · ผล → `results/R5_results.csv`

## 4. แบบที่จะรัน (≤ 5 · ค่าเดียวทุกตัว · ห้ามลองค่าอื่นหลังเห็นผล · trial #86–#89)
| id | Cfg | ส่วนประกอบ | ฐาน (ปิดสวิตช์ = ทุกบิต) | คาด ข้อ1 / ข้อ2 / ข้อ3 / off1 |
|---|---|---|---|---|
| **M048-ACLR42** | `Cfg(canary=True, ens=True, aclr=True)` | 3 | M042 | 1.547 (=) / 1.313 (=) / 1.33–1.37 / 0.80–0.88 ✗ข้อ4 |
| **M049-STACK7** | `Cfg(vsl=True, canary=True, ens=True, aclr=True)` | 4 | M046 | 1.587 (=) / 1.344 (=) / 1.41–1.45 / **0.88–0.95** |
| **M050-SR3M46** | `Cfg(vsl=True, canary=True, ens=True, sr3m=3)` | 4 | M046 | 1.35–1.60 / 1.15–1.35 (เสี่ยง) / ± / 0.8–1.1 |
| **M051-STACK8** (มีเงื่อนไข) | `Cfg(vsl=True, canary=True, ens=True, aclr=True, sr3m=3)` | 5 | M050 | — |

**กติกา M051 (ลงทะเบียน)**: รันเฉพาะเมื่อ M050 ผ่าน pass1 ∧ pass2 **และ** ไม่ผ่าน pass4 (ถ้า M050 ตกข้อ 1/2 → ALLCLEAR ไม่ช่วยเพราะไม่แตะ offset 0 · ถ้า M050 ผ่านครบแล้ว → ไม่ต้องรัน)
· regression M051: `aclr=False` == M050 ทุกบิต · offset 0 ต้องยิง 0 ครั้ง (VSL ของชุดกองใหม่อาจต่าง — ถ้ายิงที่ offset 0 ให้รันต่อแต่รายงานชัด ไม่ใช่หยุด เพราะไม่มีค่าที่ผมตรวจไว้ล่วงหน้า)
**ลำดับรัน**: d0-regression → ข้อ 2–3 → M048 → M049 → M050 → (M051) · คาด ~1–2 นาที/แบบ (+ ksig/canary ราย 30 เดือน/offset · cache ด้วย dict ตาม m)

**กติกาผู้ชนะรอบ 5 (ลงทะเบียน)**: ผู้สมัคร = {M048, M049, M050, M051} · ผ่าน = pass1 (> 1.4) ∧ pass2 (≥ 1.3) ∧ pass3 (≥ 1.2) ∧ pass4 (off0, off1, off2 ≥ 0.9 ทุกตัว) · ค่าเต็ม ไม่ปัด
1. **ส่วนประกอบน้อยกว่า** (CANARY = 1 · ENS, VSL, ACLR, SR3M = +1 ต่อตัว) → 2. **sh_c2 สูงกว่า** → 3. **off_min สูงกว่า**
4. ไม่มีตัวผ่าน → รายงานตัวที่ off_min สูงสุดในบรรดา pass1 ∧ pass2 ∧ pass3 (รวม M046 ฐาน) พร้อมระยะขาด · **ไม่สร้างแบบใหม่ในรอบนี้**
· ถ้าผู้ชนะผ่านข้อ 4 ด้วยระยะ < ส่วนที่พองจากราคาค้าง (§3) → ติดธง "ผ่านแบบมีเงื่อนไขข้อมูล" และส่งผู้ใช้ตัดสิน

## 5. ประเมินตรงๆ + ต้องให้ผู้ใช้ตัดสินใจ
- โอกาสมีตัวผ่านทั้ง 4 ข้อ ≈ **45–55%** เกือบทั้งหมดผ่าน M049 · ถ้าผ่าน = ผ่านด้วย 3 เหตุการณ์ที่ offset 1 (ปลาย 2023, พ.ค. 24, มิ.ย. 25) ระยะห่างอยู่ใน noise · M050 คือการวัด "ราคาของการคัดกองที่ไม่ขึ้นกับเดือน"
- trials จะถึง 88–89 บน 45 เดือนเดียวกัน · DSR ต่ำ · หลักฐานจริงต้องรอ holdout NAV 2026
1. **K-GOLD-C(A) ยังใช้ราคาค้าง 2024-05-16 → ส.ค. 24 ที่ offset 1** (`clean_gold_v2` ต่อถึงวันสุดท้ายของ C เท่านั้น) · จะให้ต่อด้วย K-GOLD-A(A) ถึงสิ้นช่วงถือ (เหมือนข้อเสนอ D0 เดิม · คาดยก M046 off1 ~+0.01–0.02 และลดส่วนได้ของ ALLCLEAR) หรือคงไว้
2. ถ้า M049 ผ่านข้อ 4 ด้วยระยะ < 0.03: ยอมรับเป็นผู้ชนะ หรือถือว่า "ยังไม่ผ่าน" จนกว่าข้อ 1 ได้คำตอบ
