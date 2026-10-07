import json, pandas as pd, numpy as np
from scipy import stats
R="/Users/doyinratnavardhana/Fama French/Fund Style Dashboard/.claude/quant_team"; res=R+"/backtest/results"
S=pd.read_csv(res+"/REAL_RF_summary.csv"); meta=json.load(open(R+"/scratch/validator_realrf_meta.json")); reg=pd.read_csv(R+"/scratch/validator_realrf_regression.csv")
lab={"M004-TF-FX":"Trend 25","M006-TC":"Graded Cash","M006-TCA":"Graded Cash + Fund Filter"}
S["rk2"]=S["sharpe_full_rf2"].rank(ascending=False,method="min").astype(int); S["rkr"]=S["sharpe_full_real"].rank(ascending=False,method="min").astype(int)
rho=stats.spearmanr(S["sharpe_full_rf2"],S["sharpe_full_real"])[0]
nm=lambda t: t+(f" ({lab[t]})" if t in lab else "")
f=lambda x,d=3: "" if pd.isna(x) else f"{x:.{d}f}"
p=lambda x: "" if pd.isna(x) else f"{x*100:.1f}%"
L=["# REAL_RF_remeasure — คำนวณทุก trial ใหม่ด้วย rf ไทยจริง (2026-10-06 · backtest-validator)","",
"**นี่คือการเปลี่ยนวิธีวัดผล ไม่ใช่ trial ใหม่** (ไม่เพิ่มแถวใน trials.csv · ไม่แตะการคัดกอง/SR12 — ใช้ plan/น้ำหนักเดิมของแต่ละ trial ทุกไตรมาส → กองที่เลือกเหมือนเดิม) · สคริปต์ `backtest/remeasure_real_rf.py` · ตาราง `REAL_RF_summary.csv`","",
"## วิธีและสมมติฐาน",
"- ข้อมูล `base_data/TH_POLICY_RATE.csv` (อัตรานโยบาย กนง. 1-day repo, % ต่อปี) → อัตรารายวันแบบ step: **อัตราใหม่มีผลตั้งแต่วันถัดจาก announce_date** (วัน d ใช้ rate ของมติล่าสุดที่ announce_date < d)",
"- เงินสด (`__CASH__` และเงินที่ซื้อกองไม่ได้): โตทบต้นรายวัน ปัจจัยวัน d = (1+r_d)^(1/365) (ACT/365) · growth(d0,d1)=∏ ปัจจัยวัน · rf คงที่ 2% ให้ (1.02)^(days/365) ตรงสูตรเดิมทุกประการ",
"- **rf ของ Sharpe รายเดือน**: rf_k = growth(วันที่ index k−1 → k) − 1 (ดอกเบี้ยทบของเดือนนั้นจากเส้นอัตรารายวันเดียวกัน) · excess_k = r_k − rf_k · Sharpe = mean(excess)·12 ÷ (std(r)·√12) · DSR (n_trials=22) และ CI95% block bootstrap (block 3, 2000 รอบ) ใช้ excess แบบเดียวกัน",
"- นัยของสมมติฐาน: อัตรานโยบายใช้แทนผลตอบแทนเงินสด (กองตลาดเงินจริงต่ำกว่านโยบายเล็กน้อยหลังค่าใช้จ่าย) · ฐาน rf 2% = ค่าอ้างอิงเดิม (rf/12 รายเดือน, ทบ ACT/365 สำหรับเงินสด) · วัดใหม่ (นับเดือนแรก) family map ใหม่ ตาม COST_real_fees ทุก trial · ช่วง 2022-04..2025-12 (45 เดือน)",
"- เงินสดที่ได้จริงเฉลี่ย ≈ ผลตอบแทนเฉลี่ยของอัตรานโยบายช่วง e₀..2025-12 = "+f(S['policy_avg_rate_sim_period'].iloc[0]*100,2)+"% ต่อปี (ไม่ใช่ 2%) · เฉลี่ยรายปีปฏิทิน (กนง.): "+" · ".join(f"{y} {v:.2f}%" for y,v in meta["policy_avg_by_year"].items()),
"","## Regression (ผ่านก่อนใช้ผล)",
f"- ป้อนเส้นคงที่ 2% ผ่านเครื่องมือใหม่ (กลไกเดียวกับรันจริง) ทั้ง 24 trial × 4 กรณี (cost 0% / flat 0.5% / full / nofront) = {meta['n_reg']} ชุด เทียบ `COST_real_fees_summary.csv` / `M009_summary_metrics.csv` / `M010_results.csv`: **max|ΔSharpe| = {meta['max_dsharpe']:.1e}** (เกณฑ์ <1e-6) · max|ΔCAGR|={reg['d_cagr'].max():.1e} · max|ΔmaxDD|={reg['d_max_dd'].max():.1e} → ผ่าน (ละเอียด `scratch/validator_realrf_regression.csv`)",
f"- DSR/CI ฟังก์ชันชุดใหม่ที่เส้นคงที่ = `simulate.deflated_sharpe` / `block_bootstrap_ci` เดิมเป๊ะ (Δ={meta['d_dsr']:.0e}) · `simulate.py` ไม่ถูกแก้ (แทน `_grow_cash` ชั่วคราวผ่าน context manager ในสคริปต์ใหม่)",
"- M009-NC / M010-LLD สร้าง plan ซ้ำจาก `*_weights.csv` (target รวม `__CASH__`) → regression ตรงตัวเลขเดิม","",
"## ตารางหลัก — กรณีจ่ายค่าธรรมเนียมเต็ม (full) · rf 2% vs rf จริง",
"| trial | Sharpe rf2% | Sharpe rf จริง | Δ | อันดับ 2%→จริง | CAGR 2%→จริง | vol | maxDD 2%→จริง | DSR@22 2%→จริง | CI95% (rf จริง) |","|---|---|---|---|---|---|---|---|---|---|"]
for _,r in S.iterrows():
    L.append(f"| {nm(r.trial)} | {f(r.sharpe_full_rf2)} | {f(r.sharpe_full_real)} | {r.sharpe_full_real-r.sharpe_full_rf2:+.3f} | {r.rk2}→{r.rkr} | {p(r.cagr_full_rf2)}→{p(r.cagr_full_real)} | {p(r.vol_full_real)} | {p(r.max_dd_full_rf2)}→{p(r.max_dd_full_real)} | {f(r.dsr22_rf2)}→{f(r.dsr22_real)} | [{r.ci_lo_real:.2f}, {r.ci_hi_real:.2f}] |")
L+=["","## Sharpe ทุกกรณีค่าธรรมเนียม (rf 2% → rf จริง)","| trial | cost 0% | flat 0.5% | cost 1% | full | nofront |","|---|---|---|---|---|---|"]
for _,r in S.iterrows():
    L.append(f"| {nm(r.trial)} | "+" | ".join(f"{f(r[f'sharpe_{k}_rf2'])}→{f(r[f'sharpe_{k}_real'])}" for k in ("c0","c50","c100","full","nofront"))+" |")
L+=["","## ลำดับเปลี่ยนไหม (กรณี full)",f"- Spearman ระหว่างอันดับ Sharpe rf 2% กับ rf จริง = **{rho:.3f}**",
"- Δ Sharpe ต่อ trial: ต่ำเป็น rf จริงต่ำกว่า 2% ราว 0.7 pt/ปี (เฉลี่ย ~1.3%) → Sharpe สูงขึ้น ~+0.01–0.02 เกือบทุก trial · ยกเว้นกลุ่มถือเงินสดมาก (M006-TC/TCA/TCQ เฉลี่ยเงินสด ~38–40%) ที่ Sharpe **ลดเล็กน้อย** (−0.003 ถึง −0.004) เพราะรายได้เงินสดลดลงมากกว่าที่ rf ลดลงช่วยในตัวหาร"]
ch=S[S.rk2!=S.rkr]
L.append("- trial ที่อันดับเปลี่ยน: "+("; ".join(f"{t} {a}→{b}" for t,a,b in zip(ch.trial,ch.rk2,ch.rkr)) if len(ch) else "ไม่มี"))
L+=["","## ปี 2022 แยก (Sharpe เม.ย.–ธ.ค. 2022, 9 เดือน, full) — rf จริงปี 2022 ~0.68% ต่ำกว่า 2% มาก","| trial | Sharpe 2022 rf2% | rf จริง | Sharpe 2023-07..2025-12 rf2% | rf จริง |","|---|---|---|---|---|"]
for _,r in S.iterrows():
    L.append(f"| {nm(r.trial)} | {f(r.sharpe_2022_full_rf2)} | {f(r.sharpe_2022_full_real)} | {f(r.sharpe_2307_2512_full_rf2)} | {f(r.sharpe_2307_2512_full_real)} |")
L+=["","## ผลตอบแทนของเงินสดที่ได้จริง (full; ถัวเฉลี่ยตามเวลาของ target เงินสดแต่ละ entry)","| trial | สัดส่วนเงินสดเฉลี่ย | อัตราที่เงินสดได้ rf2% | rf จริง (ต่อปี) | รายได้เงินสด pt/ปี รวมพอร์ต 2%→จริง |","|---|---|---|---|---|"]
for _,r in S[S.avg_cash_weight>0.005].iterrows():
    L.append(f"| {nm(r.trial)} | {p(r.avg_cash_weight)} | {r.cash_yield_rf2*100:.2f}% | {r.cash_yield_real*100:.2f}% | {r.cash_income_pp_yr_rf2*100:.2f}→{r.cash_income_pp_yr_real*100:.2f} |")
L+=["","(trial ที่ไม่ได้ถือเงินสดตามเป้า — B0, M001, M002, M003 — ได้รับผลเฉพาะตัวหาร rf ใน Sharpe และเงินที่ซื้อกองไม่ได้ซึ่งแทบไม่มี)","",
"## ข้อสังเกต / ข้อจำกัด",
"- rf จริงช่วงนี้ **ต่ำกว่า 2%** (เฉลี่ย ~1.30%; 2022 ~0.68%, 2023 ~1.99%, 2024 ~2.45%, 2025 ~1.77%) → Sharpe สูงขึ้นเล็กน้อยทั่วกระดาน แต่เงินสดได้น้อยลง → trial ที่ถือเงินสดมาก (Graded Cash) ไม่ได้ประโยชน์สุทธิ · ผลต่างต่อลำดับน้อยมาก ไม่เปลี่ยนข้อสรุปเชิงเปรียบเทียบ",
"- ไม่ได้เปลี่ยนการคัดกอง/SR12 จึงไม่ใช่ trial; SR12 + rf จริงเป็น trial แยก (modeler เขียน spec) · DSR ใช้ n_trials=22 ทุกแถว (ไม่ใช่จำนวนสะสมเดิมของแต่ละแถว) เพื่อเทียบกันได้",
"- อัตรานโยบายเป็นขั้นบันได ไม่ใช่ผลตอบแทนกองตลาดเงิน/ตั๋ว ธปท. จริง (ซึ่งมักต่ำกว่านโยบาย 0.1–0.3 pt หลังค่าใช้จ่าย) → ค่ารายได้เงินสดเป็นขอบบน · ไม่รวมภาษีดอกเบี้ย",
"- M004-TF-NEWMEAS (ตัวแปรการวัดของ M004-TF เดิม) ไม่คำนวณใหม่ (ไม่มีคอลัมน์ fee ใน ALL_RESULTS เดิม) · แถว M007 เฉลี่ยมูลค่าหลาย tranche ก่อนวัดผลตาม COST_real_fees"]
open(res+"/REAL_RF_remeasure.md","w",encoding="utf-8").write("\n".join(L))
# ALL_RESULTS.csv/.md
a=pd.read_csv(res+"/ALL_RESULTS.csv"); m=S.set_index("trial")
for new,src,d in (("sharpe_fee_full_realrf","sharpe_full_real",4),("sharpe_fee_nofront_realrf","sharpe_nofront_real",4),("sharpe_flat05_realrf","sharpe_c50_real",4),
                  ("sharpe_cost0_realrf","sharpe_c0_real",4),("cagr_fee_full_realrf","cagr_full_real",4),("maxdd_fee_full_realrf","max_dd_full_real",4),
                  ("sharpe_2022_fee_full_realrf","sharpe_2022_full_real",4),("dsr_n22_fee_full_realrf","dsr22_real",4)):
    if new in a.columns: a=a.drop(columns=[new])
    a[new]=a["trial"].map(m[src]).round(d)
a.to_csv(res+"/ALL_RESULTS.csv",index=False)
with open(res+"/ALL_RESULTS.md","a",encoding="utf-8") as fh:
    fh.write("\n\n## เพิ่ม 2026-10-06: rf ไทยจริง (REAL_RF_remeasure — เปลี่ยนวิธีวัด ไม่ใช่ trial)\nคอลัมน์ใหม่ใน `ALL_RESULTS.csv` (ท้ายตาราง, ลงท้าย `_realrf`): `sharpe_fee_full_realrf`, `sharpe_fee_nofront_realrf`, `sharpe_flat05_realrf`, `sharpe_cost0_realrf`, `cagr_fee_full_realrf`, `maxdd_fee_full_realrf`, `sharpe_2022_fee_full_realrf`, `dsr_n22_fee_full_realrf` — "
            "ใช้ rf = อัตรานโยบาย กนง. รายวัน (step, มีผลวันถัดจากประกาศ) ทั้งดอกเบี้ยเงินสดและ rf ใน Sharpe/DSR · plan/กองที่คัดเหมือนเดิม · เทียบกับคอลัมน์ `sharpe_fee_full` (rf 2%, วัดใหม่) · แถว M004-TF-NEWMEAS เว้นว่าง · รายละเอียด `REAL_RF_remeasure.md`\n")
print(S[["trial","rk2","rkr"]].T.to_string()); print("rho",rho)
print(S[["trial","sharpe_full_rf2","sharpe_full_real","sharpe_2022_full_rf2","sharpe_2022_full_real","dsr22_rf2","dsr22_real","ci_lo_real","ci_hi_real","max_dd_full_real","cagr_full_real"]].round(3).to_string())
