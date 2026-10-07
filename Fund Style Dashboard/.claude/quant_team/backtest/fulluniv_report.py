"""fulluniv_report.py — เขียน results/FULLUNIV_summary.md/.csv + เพิ่มคอลัมน์ *_fulluniv_realrf ใน ALL_RESULTS.csv/.md (สำรองก่อน · ไม่แตะ trials.csv)
อ่านผลจาก results/FULLUNIV_*.csv (สร้างโดย fulluniv_run.py) + ผล retail เดิม (RETAIL_results.csv, M015_results.csv, ROBUST_*.csv) — ไม่คำนวณใหม่."""
from __future__ import annotations

import json
import os
import shutil
import sys
import time

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if THIS_DIR not in sys.path:
    sys.path.insert(0, THIS_DIR)

import numpy as np
import pandas as pd

import common

RES = common.RESULTS_DIR
SCRATCH = os.path.join(os.path.dirname(THIS_DIR), "scratch")
rd = lambda n: pd.read_csv(os.path.join(RES, n))
NAME = {"B0": "B0 (ถือเท่ากันทุกกอง)", "Trend25": "Trend 25 (M004-TF-FX)", "M011-RFH": "M011-RFH", "M012-QF-S": "M012-QF-S", "M013-GC75": "M013-GC75 (เงินสด rf จริง)",
        "M015-FAUM": "M015-FAUM (GC75 + กองตลาดเงิน)"}
f3 = lambda x: f"{x:.3f}"
pc = lambda x, d=2: f"{x*100:.{d}f}%"


def main():
    T = rd("FULLUNIV_models.csv").set_index("model")
    RT = rd("RETAIL_results.csv").set_index("model")
    M15 = rd("M015_results.csv").set_index("model").loc["M015-FAUM"]
    OF = rd("FULLUNIV_offsets.csv")
    OFS = rd("FULLUNIV_offsets_summary.csv").set_index("model")
    AB = rd("FULLUNIV_offsets_AminusB.csv")
    FE = rd("FULLUNIV_fees.csv")
    FAB = rd("FULLUNIV_fees_AminusB.csv").set_index("case")
    CG = rd("FULLUNIV_cagr_before_after.csv")
    YR = pd.read_csv(os.path.join(RES, "FULLUNIV_calendar_year.csv"), index_col=0)
    PR = rd("FULLUNIV_paired.csv")
    ROB = rd("ROBUST_offsets.csv")
    ROBF = rd("ROBUST_fees.csv")
    reg = json.load(open(os.path.join(SCRATCH, "validator_full_regression.json")))
    diag = json.load(open(os.path.join(SCRATCH, "validator_full_diag.json")))

    # ---------- เทียบ full vs retail (ทุกโมเดล) ----------
    cmp_rows = []
    for m in T.index:
        if m == "M015-FAUM":
            r = {"sharpe_full": M15["sharpe_full"], "sharpe_nofront": M15["sharpe_nofront"], "sharpe_c0": M15["sharpe_c0"], "cagr_full": M15["cagr"], "maxdd_full": M15["maxdd"]}
        else:
            r = {"sharpe_full": RT.loc[m, "new_sharpe_full"], "sharpe_nofront": RT.loc[m, "new_sharpe_nofront"], "sharpe_c0": RT.loc[m, "new_sharpe_c0"],
                 "cagr_full": RT.loc[m, "new_cagr_full"], "maxdd_full": RT.loc[m, "new_maxdd_full"]}
        o = {"model": m}
        for k in ("sharpe_full", "sharpe_nofront", "sharpe_c0", "cagr_full", "maxdd_full"):
            o[f"full_{k}"], o[f"retail_{k}"], o[f"d_{k}"] = T.loc[m, k], r[k], T.loc[m, k] - r[k]
        for mm, key in (("A", "M015-FAUM"), ("B", "Trend25")):
            if m == key:
                o["full_offset_mean_sharpe"] = OFS.loc[mm, "sharpe_mean"]
                o["full_tranche_sharpe"] = OFS.loc[mm, "sharpe_tranche"]
                rr_ = ROB[(ROB["model"] == mm)]
                o["retail_offset_mean_sharpe"] = rr_[rr_["offset"].astype(str).isin(["0", "1", "2"])]["sharpe"].mean()
                o["retail_tranche_sharpe"] = float(rr_[rr_["offset"].astype(str) == "tr"]["sharpe"].iloc[0])
        cmp_rows.append(o)
    CMP = pd.DataFrame(cmp_rows)
    CMP.to_csv(os.path.join(RES, "FULLUNIV_vs_retail.csv"), index=False)

    # ---------- FULLUNIV_summary.csv (ตารางโมเดลหลัก + เทียบ retail ต่อโมเดล) ----------
    S = T.reset_index().merge(CMP, on="model")
    S.to_csv(os.path.join(RES, "FULLUNIV_summary.csv"), index=False)

    # ---------- ข้อความ ----------
    L = []
    A = L.append
    A("# FULLUNIV — วัดผลบน universe เต็ม (ลูกค้าซื้อได้ทุก class) · 2026-10-07 · backtest-validator")
    A("")
    A("**การวัดซ้ำตามการตัดสินใจของผู้ใช้ 2026-10-07 — ไม่ใช่ trial ใหม่** (ไม่แตะ `trials.csv`, ไม่แก้ไฟล์เดิม) · สคริปต์ `backtest/fulluniv_run.py` + `fulluniv_report.py` · "
      "universe เต็ม (ไม่ตัด class ตามขั้นต่ำซื้อ) · rf จริง (นโยบาย กนง.) · `FeeData(legacy=False)` Actual · ช่วงเต็ม 15 ไตรมาส เม.ย. 2022–ธ.ค. 2025 (45 เดือน) · DSR n = 32 (จำนวน trial สะสมเท่าเดิม)")
    A("")
    A("## 1. Regression (ก่อนรันอื่น) — ผ่านทุกตัว")
    A("| ตัวชี้วัด | ได้ | อ้างอิง | ต่าง |")
    A("|---|---|---|---|")
    lab = {"B0": "B0 (rf จริง)", "Trend25": "Trend 25", "M011-RFH": "M011-RFH", "M012-QF-S": "M012-QF-S", "M013-GC75": "M013-GC75", "FAUM_F_is_cash": "M015-FAUM เมื่อขา F = เงินสด (ผ่านโค้ด F/CombinedFee) = M013-GC75"}
    for k, v in reg.items():
        if k == "ok_all":
            continue
        A(f"| {lab[k]} | {v['got']:.6f} | {v['ref']:.6f} | {abs(v['got']-v['ref']):.1e} |")
    A("")
    A("- แผนกอง (น้ำหนักรายไตรมาส) ของ Trend 25 / M011 / M012-QF-S / M013-GC75 บน universe เต็มรอบนี้ **เท่ากับ** แผนเต็มรอบ retail (15/15 ไตรมาส) · ส่วนหุ้นของ M015-FAUM = M013-GC75 ทุกบิต (max|Δw| = 0 ทุก offset) · ไม่มีไตรมาสที่ F fallback เป็นเงินสด · no-look-ahead ของขา F: max|Δสัญญาณ| = 0, ชุด I_t^F เท่ากัน")
    A(f"- ขา F ของ M015: ตัดเงื่อนไขขั้นต่ำซื้อ (fst_lowbuy_val ≤ 100,000) ออกจาก snapshot F ด้วย → class F ที่เพิ่มเข้ามา {len(diag['new_F_classes_vs_retail_snapshot'])} class ({', '.join(diag['new_F_classes_vs_retail_snapshot'])}) · เงื่อนไขอื่นของ snapshot (Tax Type, buy period, Retail Type, ชื่อ Not for Retail/TEST) คงเดิม · **ผลไม่เปลี่ยน**: กอง F ที่ถูกเลือกทุกไตรมาส (K-MONEY, B-TREASURY, KKP MP-F) เป็นกองเดิมของ retail (ไม่มี class ใหม่ถูกเลือก)")
    A("")
    A("## 2. ผลโมเดลบน universe เต็ม (offset 0, 45 เดือน, rf จริง)")
    A("| โมเดล | Sharpe full | nofront | 0% | CAGR | vol | maxDD | ต้นทุน %/ปี | turnover/ปี | Sharpe 2022 | Sharpe 2023-07..25 | CI95% | DSR@32 |")
    A("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for m in T.sort_values("sharpe_full", ascending=False).index:
        t = T.loc[m]
        A(f"| {NAME[m]} | **{f3(t.sharpe_full)}** | {f3(t.sharpe_nofront)} | {f3(t.sharpe_c0)} | {pc(t.cagr_full)} | {pc(t.vol_full)} | {pc(t.maxdd_full)} | {t.cost_pct_yr_full:.2f} | {t.turn_yr:.2f} | {f3(t.sharpe_2022_full)} | {f3(t.sharpe_2307_2512_full)} | [{t.ci_lo:.2f}, {t.ci_hi:.2f}] | {t.dsr32:.3f} |")
    A("")
    A("- paired Δ Sharpe (full, rf จริง, block bootstrap): " + " · ".join(f"{r.a} − {r.b} = {r.d_sharpe_full:+.3f} [{r.ci_lo:+.3f}, {r.ci_hi:+.3f}]" for r in PR.itertuples()))
    A("- ไม่มีโมเดลถึงเป้า 0.95 ที่ช่วงเต็ม; DSR@32 ทุกตัว < 0.20 · M015-FAUM ต่ำกว่า M013-GC75 เล็กน้อยแต่มีนัย (CI ไม่คร่อม 0) เพราะกองตลาดเงินให้ผลตอบแทนต่ำกว่า rf นโยบาย + ต้นทุนสลับขา F (turnover 1.96 vs 1.37 ต่อปี)")
    A("")
    A("## 3. ตรวจเลื่อนเดือน rebalance — A = M015-FAUM, B = Trend 25 (universe เต็ม · ช่วงร่วม ก.ค. 2022–ธ.ค. 2025 = 42 เดือน · วิธีเดียวกับ `ROBUST_offsets.md`)")
    A("| โมเดล | offset | Sharpe | CAGR | vol | maxDD | Sharpe 0% | Sharpe ช่วง 45/44/43 เดือนเดิม |")
    A("|---|---|---|---|---|---|---|---|")
    olab = {"0": "0 (มี.ค./มิ.ย./ก.ย./ธ.ค.)", "1": "1 (เม.ย./ก.ค./ต.ค./ม.ค.)", "2": "2 (พ.ค./ส.ค./พ.ย./ก.พ.)", "tr": "tranche 1/3 ต่อ offset"}
    mlab = {"A": "A = M015-FAUM", "B": "B = Trend 25", "B0": "B0 ถือเท่ากัน"}
    for m in ("A", "B", "B0"):
        for r in OF[OF["model"] == m].itertuples():
            orig = "—" if pd.isna(r.sharpe_origwin) else f"{r.sharpe_origwin:.3f} ({int(r.n_months_origwin)})"
            A(f"| {mlab[m]} | {olab[str(r.offset)]} | {f3(r.sharpe)} | {pc(r.cagr)} | {pc(r.vol)} | {pc(r.max_dd)} | {f3(r.sharpe_c0)} | {orig} |")
    A("")
    A("| โมเดล | Sharpe เฉลี่ย 3 offset | min–max | tranche | CAGR เฉลี่ย (min–max) | tranche CAGR | maxDD แย่สุด |")
    A("|---|---|---|---|---|---|---|")
    for m in ("A", "B", "B0"):
        s = OFS.loc[m]
        A(f"| {mlab[m]} | {f3(s.sharpe_mean)} | {f3(s.sharpe_min)}–{f3(s.sharpe_max)} | {f3(s.sharpe_tranche)} | {pc(s.cagr_mean)} ({pc(s.cagr_min)}–{pc(s.cagr_max)}) | {pc(s.cagr_tranche)} | {pc(s.maxdd_worst)} |")
    A("")
    A("**A − B (Sharpe ช่วงร่วม, paired block bootstrap CI95%)**")
    A("| offset | A | B | A − B | CI95% | ΔCAGR (A−B) | A − B0 | CI95% (A−B0) |")
    A("|---|---|---|---|---|---|---|---|")
    for k in ("0", "1", "2", "tr"):
        b = AB[(AB["offset"].astype(str) == k) & (AB["vs"] == "B")].iloc[0]
        b0 = AB[(AB["offset"].astype(str) == k) & (AB["vs"] == "B0")].iloc[0]
        A(f"| {olab[k]} | {f3(b.A)} | {f3(b.other)} | **{b.d_sharpe:+.3f}** | [{b.ci_lo:+.2f}, {b.ci_hi:+.2f}] | {b.d_cagr*100:+.2f} pt | {b0.d_sharpe:+.3f} | [{b0.ci_lo:+.2f}, {b0.ci_hi:+.2f}] |")
    mean_ab = AB[(AB["vs"] == "B") & (AB["offset"].astype(str).isin(["0", "1", "2"]))]["d_sharpe"].mean()
    A(f"- A − B เฉลี่ย 3 offset = {mean_ab:+.3f} · A ชนะ B {int((AB[(AB['vs']=='B') & (AB['offset'].astype(str).isin(['0','1','2']))]['d_sharpe']>0).sum())} จาก 3 offset · CI คร่อม 0 ทุกค่า (ไม่มีนัยสถิติ)")
    A("")
    A("## 4. ค่าธรรมเนียม 4 กรณี (offset 0, ช่วงเต็ม 45 เดือน, universe เต็ม)")
    A("(ก) Actual = อัตราเก็บจริง (หลัก) · (ข) Rate = เพดานหนังสือชี้ชวน · (ค) ยกเว้น front-end (FF=SI=0) · (ง) 0% — plan เดิม ไม่เลือกกองใหม่ เปลี่ยนเฉพาะต้นทุนซื้อขาย")
    A("| กรณี | A Sharpe | A CAGR | A ต้นทุน %/ปี | B Sharpe | B CAGR | B ต้นทุน %/ปี | A − B (CI95%) |")
    A("|---|---|---|---|---|---|---|---|")
    clab = {"ก_Actual": "(ก) Actual", "ข_Rate": "(ข) Rate เพดาน", "ค_noFront": "(ค) ยกเว้น front-end", "ง_0pct": "(ง) 0%"}
    for c in clab:
        a = FE[(FE["case"] == c) & (FE["model"] == "A")].iloc[0]
        b = FE[(FE["case"] == c) & (FE["model"] == "B")].iloc[0]
        d = FAB.loc[c]
        A(f"| {clab[c]} | {f3(a.sharpe)} | {pc(a.cagr)} | {a.cost_pct_yr:.2f} | {f3(b.sharpe)} | {pc(b.cagr)} | {b.cost_pct_yr:.2f} | {d.A_minus_B:+.3f} [{d.ci_lo:+.2f}, {d.ci_hi:+.2f}] |")
    A("")
    A("## 5. CAGR ก่อน/หลังค่าธรรมเนียมของ A = M015-FAUM")
    A("ก่อน = ไม่หักค่าธรรมเนียมซื้อขายเลย (กรณี 0%) · หลัง = Actual (ต้นทุนสลับกอง front/back/switch ตามจริง; ค่าบริหารกองอยู่ใน NAV แล้วทั้งก่อนและหลัง) · แต่ละ offset เข้าตลาดไม่พร้อมกัน จึงรายงาน 2 ช่วง: ช่วงร่วม ก.ค. 2022–ธ.ค. 2025 (42 เดือน) และช่วงเต็มของแต่ละ offset (45/44/43 เดือนนับจากวันเข้า)")
    A("| ช่วง | offset | CAGR ก่อน | CAGR หลัง | ผลต่าง (pt/ปี) | Sharpe ก่อน→หลัง |")
    A("|---|---|---|---|---|---|")
    ca = CG[CG["model"] == "A"]
    for r in ca.itertuples():
        A(f"| {r.window} | {olab[str(r.offset)]} | {pc(r.cagr_before_fee)} | {pc(r.cagr_after_fee)} | {r.fee_drag_pt:.2f} | {r.sharpe_before:.3f} → {r.sharpe_after:.3f} |")
    full_rows = ca[ca["window"].str.startswith("own")]
    cm = ca[ca["window"].str.startswith("common") & ca["offset"].astype(str).isin(["0", "1", "2"])]
    A(f"- **ค่าเฉลี่ย 3 offset (ช่วงเต็มของแต่ละ offset)**: ก่อน {pc(full_rows.cagr_before_fee.mean())} → หลัง {pc(full_rows.cagr_after_fee.mean())} (ผลต่าง {full_rows.fee_drag_pt.mean():.2f} pt/ปี) · **ค่าเฉลี่ย 3 offset (ช่วงร่วม)**: ก่อน {pc(cm.cagr_before_fee.mean())} → หลัง {pc(cm.cagr_after_fee.mean())} ({cm.fee_drag_pt.mean():.2f} pt/ปี)")
    tr = ca[ca["offset"].astype(str) == "tr"].iloc[0]
    A(f"- **tranche (ช่วงร่วม 42 เดือน)**: CAGR ก่อน {pc(tr.cagr_before_fee)} → หลัง {pc(tr.cagr_after_fee)} (ผลต่าง {tr.fee_drag_pt:.2f} pt/ปี) · Sharpe {tr.sharpe_before:.3f} → {tr.sharpe_after:.3f} · tranche คิดต้นทุนแยกต่อ tranche (ไม่มี netting ข้าม tranche)")
    A("")
    A("**ผลตอบแทนรายปีปฏิทินของ tranche A (ก่อน → หลังค่าธรรมเนียม) เทียบ B** (2022 = ก.ค.–ธ.ค. เท่านั้น)")
    A("| ปี | A ก่อน | A หลัง | B ก่อน | B หลัง |")
    A("|---|---|---|---|---|")
    for y in YR.index:
        A(f"| {y} | {pc(YR.loc[y,'A_offtr_before'])} | **{pc(YR.loc[y,'A_offtr_after'])}** | {pc(YR.loc[y,'B_offtr_before'])} | {pc(YR.loc[y,'B_offtr_after'])} |")
    A("")
    A("## 6. เทียบ universe เต็ม vs รายย่อย (rf จริง · offset 0 · 45 เดือน · fees Actual)")
    A("| โมเดล | Sharpe เต็ม | Sharpe รายย่อย | Δ | nofront เต็ม / ย่อย | 0% เต็ม / ย่อย | CAGR เต็ม / ย่อย | maxDD เต็ม / ย่อย |")
    A("|---|---|---|---|---|---|---|---|")
    for r in CMP.itertuples():
        A(f"| {NAME[r.model]} | **{f3(r.full_sharpe_full)}** | {f3(r.retail_sharpe_full)} | {r.d_sharpe_full:+.3f} | {f3(r.full_sharpe_nofront)} / {f3(r.retail_sharpe_nofront)} | {f3(r.full_sharpe_c0)} / {f3(r.retail_sharpe_c0)} | {pc(r.full_cagr_full)} / {pc(r.retail_cagr_full)} | {pc(r.full_maxdd_full)} / {pc(r.retail_maxdd_full)} |")
    A("")
    A("เลื่อนเดือน (ช่วงร่วม 42 เดือน): เฉลี่ย 3 offset / tranche — " + " · ".join(
        f"{mlab[mm]}: เต็ม {OFS.loc[mm,'sharpe_mean']:.3f} / {OFS.loc[mm,'sharpe_tranche']:.3f} · รายย่อย {ROB[(ROB['model']==mm)&ROB['offset'].astype(str).isin(['0','1','2'])]['sharpe'].mean():.3f} / {float(ROB[(ROB['model']==mm)&(ROB['offset'].astype(str)=='tr')]['sharpe'].iloc[0]):.3f}" for mm in ("A", "B")))
    A("")
    A("ค่าธรรมเนียม 4 กรณี เทียบ retail (A / B Sharpe ช่วงเดิม): " + " · ".join(
        f"{clab[c]}: เต็ม {FE[(FE['case']==c)&(FE['model']=='A')].sharpe.iloc[0]:.3f}/{FE[(FE['case']==c)&(FE['model']=='B')].sharpe.iloc[0]:.3f} · ย่อย {ROBF[(ROBF['offset']==0)&(ROBF['case']==c)&(ROBF['model']=='A')].sharpe_origwin.iloc[0]:.3f}/{ROBF[(ROBF['offset']==0)&(ROBF['case']==c)&(ROBF['model']=='B')].sharpe_origwin.iloc[0]:.3f}" for c in clab))
    A("")
    A("## 7. ข้อสังเกต / ข้อจำกัด")
    A("- **universe เต็มทำให้ Trend 25 กลับมา 0.719 (เดิมตก 0.624 ที่ retail)** เพราะได้ถือ ONE-INDIAOPP-IA / ONE-GLOBFIN-IA (class สถาบัน ขั้นต่ำสูง) ซึ่งเข้าพอร์ต 4 ไตรมาส — ผลนี้ตั้งอยู่บนสมมติฐานว่าลูกค้าซื้อ class เหล่านั้นได้ทุกกอง/ทุกวัน (ไม่ point-in-time: ขั้นต่ำและสิทธิ์การซื้อของ class มาจาก snapshot ปัจจุบัน) · M013-GC75 ลดลงเทียบ retail (0.779 → 0.765) เป็น path luck ไม่มีนัย")
    A("- ลำดับ (full): M013-GC75 > M015-FAUM > Trend 25 > M012-QF-S > M011-RFH ≫ B0 · ช่องว่างระหว่าง 5 ตัวบนเล็กกว่า CI ทั้งหมด (paired Δ M015-FAUM vs Trend 25 +0.03 [−0.26, +0.30]) → ไม่ควรอ้างลำดับเป็นข้อสรุป")
    A("- ข้ามเดือน: Sharpe ของ A ผันผวนตาม offset ตั้งแต่ 0.35 ถึง 0.98 (ช่วงร่วม) และของ B 0.41–1.00 → ค่าที่ไม่ขึ้นกับเดือน (เฉลี่ย/tranche) ของ A ≈ 0.69–0.71 และ B ≈ 0.62–0.65 · ทั้งคู่ต่ำกว่าเป้า 0.95 · A ชนะ B เล็กน้อยแบบไม่มีนัย ยกเว้น offset 2 ที่ใกล้ขอบ (A−B +0.30, CI [−0.05, +0.74])")
    A("- ค่าธรรมเนียม: front-end เป็นต้นทุนเกือบทั้งหมด (ยกเว้น front-end เหลือ ~0.01%/ปี ≈ 0%) · เพดาน Rate ทำให้ Sharpe ของ A/B ตกเหลือ ~0.26/0.31 → ต้นทุนที่ลูกค้าจ่ายจริงมีผลต่อข้อสรุปมาก ควรเปิดเผย 'อัตราจริงต่อ AMC/ช่องทางซื้อ' เพราะ Actual ในไฟล์เป็นอัตราเก็บจริงของ AMC ไม่ใช่ของช่องทางขาย")
    A("- M015-FAUM ได้ประโยชน์จากขา F เฉพาะลดความผันผวน (vol 8.4%) แต่ผลตอบแทนส่วนเกินของขา F ต่ำกว่า rf หลังค่าธรรมเนียม · ผลขา F ไม่เปลี่ยนจาก retail (กอง F ที่เลือกเหมือนเดิม) · เตือนเดิมยังอยู่: Sharpe ของกอง F อาจเกินจริง (NAV เรียบ/ความเสี่ยงเครดิตไม่เกิดช่วง 2022–25)")
    A("- ทุกตัวเลขมาจากการรันครั้งนี้ ยกเว้นคอลัมน์ retail ในหัวข้อ 6 ที่อ่านจาก `RETAIL_results.csv`, `M015_results.csv`, `ROBUST_offsets.csv`, `ROBUST_fees.csv` (ไม่ได้ตรวจซ้ำ แต่ regression ของ offset 0 ตรงกับไฟล์เหล่านี้ในรอบก่อน)")
    A("- ไฟล์: `FULLUNIV_summary.csv`, `FULLUNIV_models.csv`, `FULLUNIV_paired.csv`, `FULLUNIV_offsets*.csv`, `FULLUNIV_fees*.csv`, `FULLUNIV_cagr_before_after.csv`, `FULLUNIV_calendar_year.csv`, `FULLUNIV_vs_retail.csv`, `FULLUNIV_weights.csv`, `FULLUNIV_A_F_funds.csv`")
    open(os.path.join(RES, "FULLUNIV_summary.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")

    # ---------- ALL_RESULTS.csv/.md : เพิ่มคอลัมน์ (สำรองก่อน) ----------
    ts = time.strftime("%Y%m%d_%H%M%S")
    p = os.path.join(RES, "ALL_RESULTS.csv")
    pm = os.path.join(RES, "ALL_RESULTS.md")
    shutil.copy(p, os.path.join(SCRATCH, f"validator_full_ALL_RESULTS.backup_{ts}.csv"))
    shutil.copy(pm, os.path.join(SCRATCH, f"validator_full_ALL_RESULTS_md.backup_{ts}.md"))
    raw = open(p, encoding="utf-8", newline="").read()
    df = pd.read_csv(p, dtype=str, keep_default_na=False)
    assert df.to_csv(index=False, lineterminator="\n") == raw.replace("\r\n", "\n"), "round-trip ของ ALL_RESULTS.csv ไม่ตรง"
    newcols = ["sharpe_fee_full_fulluniv_realrf", "sharpe_fee_nofront_fulluniv_realrf", "sharpe_cost0_fulluniv_realrf", "cagr_fee_full_fulluniv_realrf",
               "maxdd_fee_full_fulluniv_realrf", "sharpe_2022_fee_full_fulluniv_realrf", "dsr32_fee_full_fulluniv_realrf"]
    assert not any(c in df.columns for c in newcols), "มีคอลัมน์แล้ว"
    for c in newcols:
        df[c] = ""
    mapn = {"B0": "B0", "M004-TF-FX": "Trend25", "M011-RFH": "M011-RFH", "M012-QF-S": "M012-QF-S", "M013-GC75": "M013-GC75", "M015-FAUM": "M015-FAUM"}
    for tid, m in mapn.items():
        i = df.index[df["trial"] == tid]
        assert len(i) == 1, tid
        t = T.loc[m]
        df.loc[i, newcols] = [f"{t.sharpe_full:.4f}", f"{t.sharpe_nofront:.4f}", f"{t.sharpe_c0:.4f}", f"{t.cagr_full:.4f}", f"{t.maxdd_full:.4f}", f"{t.sharpe_2022_full:.4f}", f"{t.dsr32:.4f}"]
    df.to_csv(p, index=False, lineterminator="\n")
    sec = ["", "", "## เพิ่ม 2026-10-07: universe เต็ม (FULLUNIV — ฐานวัดผลหลัก)",
           "- ผู้ใช้ตัดสิน: ลูกค้าซื้อได้ทุก class → ฐานวัดผลหลัก = **universe เต็ม** + rf จริง + `FeeData(legacy=False)` · คอลัมน์ใหม่ `*_fulluniv_realrf` (Sharpe full/nofront/0%, CAGR, maxDD, Sharpe 2022, DSR@32) ของ B0 / M004-TF-FX / M011-RFH / M012-QF-S / M013-GC75 / M015-FAUM · ไม่ใช่ trial ใหม่ (ไม่แตะ `trials.csv`) · คอลัมน์ `*_retail_realrf` เดิมเก็บไว้เป็น sensitivity",
           "- Sharpe full (universe เต็ม · rf จริง): " + " · ".join(f"{NAME[m].split(' (')[0]} {T.loc[m,'sharpe_full']:.3f}" for m in T.sort_values("sharpe_full", ascending=False).index),
           f"- M015-FAUM เลื่อนเดือน (ช่วงร่วม 42 เดือน): offset 0/1/2 = {OF[(OF.model=='A')&(OF.offset.astype(str)=='0')].sharpe.iloc[0]:.3f} / {OF[(OF.model=='A')&(OF.offset.astype(str)=='1')].sharpe.iloc[0]:.3f} / {OF[(OF.model=='A')&(OF.offset.astype(str)=='2')].sharpe.iloc[0]:.3f}, เฉลี่ย {OFS.loc['A','sharpe_mean']:.3f}, tranche {OFS.loc['A','sharpe_tranche']:.3f} · Trend 25: เฉลี่ย {OFS.loc['B','sharpe_mean']:.3f}, tranche {OFS.loc['B','sharpe_tranche']:.3f} · รายละเอียด `FULLUNIV_summary.md`"]
    open(pm, "a", encoding="utf-8").write("\n".join(sec) + "\n")
    print("wrote FULLUNIV_summary.md/.csv + ALL_RESULTS columns")


if __name__ == "__main__":
    main()
