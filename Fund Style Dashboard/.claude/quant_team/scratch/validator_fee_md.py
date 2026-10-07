import json, pandas as pd
R="/Users/doyinratnavardhana/Fama French/Fund Style Dashboard/.claude/quant_team/backtest/results"
s=pd.read_csv(R+"/COST_real_fees_summary.csv"); m=json.load(open("/Users/doyinratnavardhana/Fama French/Fund Style Dashboard/.claude/quant_team/scratch/validator_fee_meta.json"))
L=["# COST_real_fees — ผลคำนวณใหม่ด้วยค่าธรรมเนียมจริง (2026-10-02 · backtest-validator)","",
"สเปก: `specs/COST_real_fees.md` · สคริปต์: `scratch/validator_fee_recalc.py` · โมดูล: `backtest/fees.py` + `simulate_path(..., fee_model=)` (ค่าเริ่มต้น None = พฤติกรรมเดิม)","",
"## ข้อมูลและกติกา",
f"- FEEUH `Actual Value` FF/BF/SI/SO point-in-time (แถวล่าสุด As of Date ≤ วันซื้อขาย; ก่อน snapshot แรก ~2023-05 ใช้ snapshot เก่าสุด) · {m['rows']} แถวของกองใน universe (555 กองมีข้อมูล FEEUH จาก 570) · แถวใช้ไม่ได้ (ว่าง/ติดลบ/>10 = บาทคงที่) {m['invalid']} แถว",
f"- median fallback (กองใน universe, snapshot ล่าสุด): **FF {m['median']['FF']} · BF {m['median']['BF']} · SI {m['median']['SI']} · SO {m['median']['SO']} %** (ตรงที่ spec คาด) · จำนวนครั้งที่ต้องใช้ fallback ในการคิดต้นทุนทั้งหมด (นับรายครั้งเรียก ไม่ใช่รายกอง): {m['fallback']}",
"- ขา `__CASH__` ไม่มีต้นทุน · สับเปลี่ยนภายใน บลจ. เดียวกันใช้ช่องทางที่ถูกกว่า (SO+SI เทียบ BF+FF ถ่วงน้ำหนัก) · ยอดเหลือ = ขาย×BF / ซื้อ×FF ของกองนั้น · (ข) ยกเว้น front-end: FF=SI=0",
"- ความต่างจาก spec ที่ผู้อ่านควรรู้: ค่า `Actual Value` > 10 (70 แถวของ SO เช่น 200/300 = บาทคงที่ ไม่ใช่ %) ถือเป็นค่าไม่ถูกต้อง -> median (SO median = 0)",
"","## Regression (ต้องผ่านก่อนใช้ผล)",
f"- fee model โหมด flat (FF=BF=SI=SO=0.5, ปิดช่องทางสับเปลี่ยน) vs `cost_side=0.5%` เดิม ทั้ง 22 trial: max|Δมูลค่าพอร์ต| = {m['reg_max_dv']:.1e}, max|Δต้นทุนรวม| = {m['reg_max_dcost']:.1e} (ระดับ floating-point) -> ผ่าน",
f"- วิธีวัดเดิม (ไม่นับเดือนแรก, cost 0.5%) สร้าง M001 จาก `M001_quarterly_weights.csv` ซ้ำได้: B0 {m['old_regression']['B0']:.3f} · MS {m['old_regression']['M001-MS']:.3f} · EW {m['old_regression']['M001-EW']:.3f} (เท่าของเดิม 0.282/0.251/0.134) · ผลวัดใหม่ของ M004-TF-FX/M006/M007/M008 ที่ 0.5% ตรงตัวเลขเดิมใน ALL_RESULTS (0.720/0.671/0.429/0.551/0.283 ฯลฯ)",
f"- M004-TF (family map ใหม่ สร้างใหม่ใน validator) vs M004-TF-FX: max|Δw| = {m['tf_vs_fx']:.1e} (ตรงกัน) · ผลรวมน้ำหนัก M001 {m['w_sum_range'][0]:.12f}..{m['w_sum_range'][1]:.12f}",
"","## ผลต่อ trial (rf 2%, 2022-04..2025-12, วัดใหม่นับเดือนแรก; M002+ ใช้ family map ใหม่)",
"| trial | Sharpe 0% | 0.5% | จ่ายเต็ม | ยกเว้น front | CAGR (0.5%/เต็ม) | vol เต็ม | maxDD เต็ม | cost bp/yr (0.5%/เต็ม/ยกเว้น) | สัดส่วนช่องสับเปลี่ยน | fee เฉลี่ย/ข้าง เต็ม | DSR@20 เต็ม |","|---|---|---|---|---|---|---|---|---|---|---|---|"]
for _,r in s.iterrows():
    L.append(f"| {r.trial} | {r.sharpe_c0:.3f} | {r.sharpe_c50:.3f} | {r.sharpe_full:.3f} | {r.sharpe_nofront:.3f} | {r.cagr_c50*100:.1f}%/{r.cagr_full*100:.1f}% | {r.vol_full*100:.1f}% | {r.maxdd_full*100:.1f}% | {r.cost_bp_yr_c50:.0f}/{r.cost_bp_yr_full:.0f}/{r.cost_bp_yr_nofront:.0f} | {r.switch_share_full*100:.0f}% | {r.avg_fee_pct_full:.2f}% | {r.dsr20_full:.3f} |")
L+=["","## ตัวเลขที่เปลี่ยนจากของเดิมเพราะอะไร",
"- B0, M001-MS, M001-EW, M002-SR/MOM/NOH, M003-ERC/HRP, M004-VT/TF, M005 ทั้งชุด: Sharpe @0.5% ต่างจาก ALL_RESULTS เดิม (measurement=old) เพราะ (1) นับเดือนแรก (เม.ย. 2022 ≈ −2.6%) และ (2) family map ใหม่ -F/-U (M002+) — **ไม่ใช่เพราะค่าธรรมเนียม** · ใช้คอลัมน์ `sharpe_c50` ในไฟล์นี้เป็นฐานเทียบกับ `sharpe_full`",
"- M004-TF-FX, M006, M007, M008: วัดใหม่/family ใหม่อยู่แล้ว -> 0.5% ตรงของเดิม",
"- M001: ใช้ selection เดิมของหน้า 8 จาก `M001_quarterly_weights.csv` (ไม่ refit ElasticNet) · ไฟล์น้ำหนักนี้เป็น plan สุดท้าย (รวม fallback B0) จึงจำลองซ้ำได้ตรง",
"","## ตีความ",
"- ค่าธรรมเนียมจริงกับ 0.5%/ข้าง ให้ Sharpe ใกล้กันมาก (ต่างไม่เกิน ~0.03 เกือบทุก trial): ต้นทุนเต็มสูงกว่า 0.5% เล็กน้อยใน trial หมุนต่ำ (FF median 1.5% ตอนซื้อ) แต่ต่ำกว่าใน trial หมุนสูง (M001) เพราะขายส่วนใหญ่ BF=0 และสับเปลี่ยนใน บลจ. เดียวกันถูกกว่า",
"- ถ้าผู้จัดจำหน่ายยกเว้น front-end (SI=FF=0) ต้นทุนเหลือ ~0–14 bp/ปี Sharpe ≈ ตัวเลขที่ต้นทุน 0% -> **ผลลัพธ์ไวต่อสมมติฐาน front-end waiver มากที่สุด** (สูงสุด +0.17 Sharpe ในกลุ่ม M004-TF) ผู้ใช้ต้องยืนยันกับช่องทางซื้อจริงว่าจะได้ยกเว้นหรือไม่",
"","## ข้อจำกัด",
"- ค่าธรรมเนียมเป็น snapshot ตั้งแต่ ~2023-05 (ก่อนหน้า = ใช้ snapshot เก่าสุดแทน; 4/93 รายการของกองที่เคยถือเปลี่ยนค่า) — ปี 2022 ใช้ค่า 2023 ย้อนหลัง",
"- เงินสดของ M006/M007 (ปรับสัดส่วนหุ้นรายเดือน) คิดต้นทุนเฉพาะขากอง; ไม่คิดค่าธรรมเนียมรายการขั้นต่ำ/บาทคงที่ และไม่คิดภาษี/ส่วนต่าง bid-ask · ไม่คิดว่าสับเปลี่ยนข้าม บลจ. ต้องขายแล้วซื้อแยก (คิด BF+FF ตามสูตร) แต่ไม่คิดเวลาเงินค้าง T+n",
"- ช่องทางที่ถูกกว่าเลือกจากอัตราเฉลี่ยถ่วงต่อ บลจ. (ไม่ใช่ต่อคู่กอง) ตาม spec · fallback median ถูกใช้บ่อยสำหรับ BF/SO (กองที่ไม่มีแถว FEEUH) — median=0 อาจต่ำเกินจริงสำหรับกองเหล่านั้น",
"- DSR@20 เป็นของกรณีจ่ายเต็ม (n_trials = 20 สะสม, ไม่นับรอบนี้เป็น trial ใหม่) · ไม่แก้ CI bootstrap รอบนี้"]
open(R+"/COST_real_fees_results.md","w",encoding="utf-8").write("\n".join(L))
print(s[["trial","sharpe_c0","sharpe_c50","sharpe_full","sharpe_nofront","cost_bp_yr_c50","cost_bp_yr_full","cagr_full","dsr20_full","switch_share_full","avg_fee_pct_full","vol_full","maxdd_full"]].round(3).to_string())
