# quant-modeler: hurdle SR12 จาก rf ไทยจริง (ไม่มี return/Sharpe) — เทียบ 0.02*11/12
import pandas as pd, numpy as np
r = pd.read_csv("base_data/TH_POLICY_RATE.csv", comment="#", parse_dates=["announce_date"]).sort_values("announce_date")
def rate_on(d):  # มีผลวันถัดจากวันประกาศ: ใช้ประกาศล่าสุดที่ announce_date < d
    s = r[r.announce_date < d]
    return s.rate_pct.iloc[-1] / 100.0
def hurdle(a, b):  # ทบรายวัน ACT/365 วัน d ∈ (a, b]
    days = pd.date_range(a + pd.Timedelta(days=1), b, freq="D")
    return float(np.prod([1 + rate_on(d) / 365 for d in days]) - 1)
qs = pd.date_range("2022-03-31", "2025-12-31", freq="QE")
rows = []
for t in qs:
    m1 = (t - pd.offsets.MonthEnd(1)); m12 = (t - pd.offsets.MonthEnd(12))
    rows.append((t.date(), m12.date(), m1.date(), hurdle(m12, m1), 0.02 * 11 / 12, hurdle(m12, m1) - 0.02*11/12))
df = pd.DataFrame(rows, columns=["t", "M-12", "M-1", "h_real", "h_const", "diff"])
print(df.round(5).to_string(index=False))
print("const 2% compounded over 334-ish days:", hurdle(pd.Timestamp("2021-03-31"), pd.Timestamp("2022-02-28")))
for v in (0.08, 0.12, 0.18, 0.25):
    print("vol", v, "SR shift per -1pt hurdle:", round(0.01 / v, 4))
