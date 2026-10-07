import json, csv, datetime
import pandas as pd
R="/Users/doyinratnavardhana/Fama French/Fund Style Dashboard/.claude/quant_team"
res=R+"/backtest/results"
s=pd.read_csv(res+"/COST_real_fees_summary.csv"); meta=json.load(open(R+"/scratch/validator_fee_meta.json"))
# ALL_RESULTS.csv: เพิ่มคอลัมน์
a=pd.read_csv(res+"/ALL_RESULTS.csv")
m=s.set_index("trial")
for new,src in (("sharpe_fee_full","sharpe_full"),("sharpe_fee_nofront","sharpe_nofront"),("cagr_fee_full","cagr_full"),("cost_bp_yr_fee_full","cost_bp_yr_full")):
    a[new]=a["trial"].map(m[src]).round(4 if "bp" not in new else 1)
a.to_csv(res+"/ALL_RESULTS.csv",index=False)
# trials.csv: append
now=datetime.datetime.now().isoformat()
with open(R+"/trials.csv","a",newline="",encoding="utf-8") as f:
    w=csv.writer(f)
    for _,r in s.iterrows():
        notes=(f"fee-recalc (ไม่ใช่ trial ใหม่) วัดใหม่ n_months={int(r.n_months)} family map F/U fix (M002+) · Sharpe: 0%={r.sharpe_c0:.3f} 0.5%={r.sharpe_c50:.3f} "
               f"full={r.sharpe_full:.3f} nofront={r.sharpe_nofront:.3f} · cost bp/yr 0.5%={r.cost_bp_yr_c50:.0f} full={r.cost_bp_yr_full:.0f} nofront={r.cost_bp_yr_nofront:.0f} · DSR@20(full)={r.dsr20_full:.3f}")
        w.writerow([r.trial,now,"COST_real_fees.md","fee=FEEUH Actual Value FF/BF/SI/SO point-in-time; full (SI/SO channel cheaper-of; cash leg free; median fallback)",
                    "2022-03-31","2025-12-31","assumed constant 2%/yr","real fees SecFundFee FEEUH (full)",round(r.sharpe_full,4),round(r.cagr_full,4),round(r.vol_full,4),round(r.maxdd_full,4),"",
                    int(r.n_trials_cum),round(r.dsr20_full,4),"fee-recalc",notes])
# md note ใน ALL_RESULTS.md
with open(res+"/ALL_RESULTS.md","a",encoding="utf-8") as f:
    f.write("\n\n## เพิ่ม 2026-10-02: ค่าธรรมเนียมจริง (COST_real_fees)\nคอลัมน์ใหม่ใน `ALL_RESULTS.csv`: `sharpe_fee_full`, `sharpe_fee_nofront`, `cagr_fee_full`, `cost_bp_yr_fee_full` — คำนวณใหม่ทุกแถวด้วย **วิธีวัดใหม่ (นับเดือนแรก) + family map ใหม่ (M002+)** "
            "จึงต่างจากคอลัมน์ `sharpe_cost05` เดิมของแถว `measurement=old` ด้วย (เดิม: ไม่นับเดือนแรก/บั๊ก share class) · เทียบกับ 0.5%/ข้างแบบวัดใหม่ให้ดู `COST_real_fees_summary.csv` (`sharpe_c50`) · "
            "รายละเอียด/ข้อจำกัด: `COST_real_fees_results.md` · M001 ใช้น้ำหนักจาก `M001_quarterly_weights.csv` (ไม่ refit)\n")
print(a.tail(3).T)
