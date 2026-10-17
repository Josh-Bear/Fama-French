"""factor-designer · ตัวเลขประกอบ L2_summary (อ่าน CSV ใน runs/S005 เท่านั้น · ไม่ fit)"""
import pandas as pd
R = ".claude/factor_team/runs/S005/"
sbi = pd.read_csv(R + "scan_by_index.csv")
for key in ("1a@4", "1c@4"):
    g = sbi[sbi.key == key]
    print(key, "max med_d_r2_oos_all =", round(g.med_d_r2_oos_all.max(), 4), g.loc[g.med_d_r2_oos_all.idxmax(), "index"],
          "| #index med_all>=0.02:", int((g.med_d_r2_oos_all >= 0.02).sum()),
          "| #index med_sigfunds>=0.02:", int((g.med_d_r2_oos_sigfunds >= 0.02).sum()))
pi = pd.read_csv(R + "primary_index.csv"); pi = pi[pi.form == "none"]
fl = pd.read_csv(R + "fund_level.csv")
ev = fl[(fl.model == "ฐาน 1a")][["FundCode", "policy", "adj_r2", "r2_oos"]]
cd = set(pi[pi["index"] == "MSCI_ACWI_CD"].FundCode) & set(ev.FundCode)
print("ACWI_CD primary in EVAL:", len(cd), ev[ev.FundCode.isin(cd)].policy.value_counts().to_dict())
e = ev[ev.policy == "E"]
print("base 1a E all: med adj", round(e.adj_r2.median(), 3), "med oos", round(e.r2_oos.median(), 3))
x = ev[ev.FundCode.isin(cd) & (ev.policy == "E")]
print("base 1a E ACWI_CD-primary: n", len(x), "med adj", round(x.adj_r2.median(), 3), "med oos", round(x.r2_oos.median(), 3))
l21 = fl[(fl.model == "L2-1") & fl.FundCode.isin(cd)]
print("L2-1 d_r2_oos in ACWI_CD-primary: med", round(l21.d_r2_oos.median(), 4), "n", len(l21))
print(pi["index"].value_counts().head(8).to_dict(), "n_EVAL_rows", len(set(pi.FundCode) & set(ev.FundCode)))
