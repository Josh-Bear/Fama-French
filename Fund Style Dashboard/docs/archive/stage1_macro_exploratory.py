"""Stage 1 validation (เบื้องต้น) — เช็คว่า macro factor อธิบาย 28 MSCI country+sector index ได้แค่ไหน
ก่อนตัดสินใจสร้างหน้า 7 เต็มรูปแบบ (chain + UI)

Exploratory เท่านั้น — ไม่ใช่ส่วนหนึ่งของ pipeline จริง (ไม่แตะ config.py / data_access.py)

ความถี่: รายเดือน (month-end)
v2: เพิ่ม Copper, DXY เป็น non-US world factor เสริม (รวม 7 ตัว)
- ราคาสินทรัพย์ (Oil, Gold, USDTHB, Copper, DXY): % return = (P_i - P_i-1) / P_i-1
- VIX, US10Y (index/yield, mean-revert): ผลต่างระดับ (delta), ไม่หารอะไร
"""
import numpy as np
import pandas as pd

country = pd.read_csv("base_data/MSCI_COUNTRY_ETF.csv", parse_dates=["Date"], index_col="Date")
sector = pd.read_csv("base_data/MSCI_SECTOR_ETF.csv", parse_dates=["Date"], index_col="Date")
idx_level = pd.concat([country, sector], axis=1)
assert idx_level.shape[1] == 28

macro_level = pd.read_csv("macro_factor_test.csv", index_col="Date", parse_dates=True)

RETURN_COLS = ["Oil_Brent", "Gold", "USDTHB", "Copper", "DXY"]
DELTA_COLS = ["VIX", "US10Y"]
macro_level = macro_level[RETURN_COLS + DELTA_COLS]

idx_m = idx_level.resample("ME").last()
macro_m = macro_level.resample("ME").last()

idx_ret = idx_m.pct_change()
macro_ret = pd.DataFrame(index=macro_m.index)
for c in RETURN_COLS:
    macro_ret[c] = macro_m[c].pct_change()
for c in DELTA_COLS:
    macro_ret[c] = macro_m[c].diff()

aligned = idx_ret.join(macro_ret, how="inner").dropna()
print(f"aligned shape: {aligned.shape}  ({aligned.index.min():%Y-%m} -> {aligned.index.max():%Y-%m})")
print()

factor_cols = RETURN_COLS + DELTA_COLS
X = np.column_stack([np.ones(len(aligned)), aligned[factor_cols].to_numpy()])

results = []
for col in idx_level.columns:
    y = aligned[col].to_numpy()
    coef, *_ = np.linalg.lstsq(X, y, rcond=None)
    y_hat = X @ coef
    ss_res = np.sum((y - y_hat) ** 2)
    ss_tot = np.sum((y - y.mean()) ** 2)
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else np.nan
    row = {"index": col, "r2_7f": r2, "n_obs": len(y)}
    row.update({f"coef_{c}": coef[i + 1] for i, c in enumerate(factor_cols)})
    results.append(row)

res = pd.DataFrame(results).sort_values("r2_7f", ascending=False)
pd.set_option("display.width", 160)
pd.set_option("display.max_rows", 30)
print(res[["index", "r2_7f", "n_obs"]].to_string(index=False))
print()
print("สรุป R² ทั้ง 28 index (7 factor):")
print(res["r2_7f"].describe())
print()
print("coefficient เฉลี่ย:")
print(res[[f"coef_{c}" for c in factor_cols]].mean())

# เทียบกับผล 5-factor เดิม (เฉพาะ Oil/Gold/USDTHB/VIX/US10Y) เพื่อดูว่า Copper/DXY ช่วยเพิ่ม R² จริงไหม
factor_cols5 = ["Oil_Brent", "Gold", "USDTHB", "VIX", "US10Y"]
X5 = np.column_stack([np.ones(len(aligned)), aligned[factor_cols5].to_numpy()])
r2_5 = []
for col in idx_level.columns:
    y = aligned[col].to_numpy()
    coef, *_ = np.linalg.lstsq(X5, y, rcond=None)
    y_hat = X5 @ coef
    ss_res = np.sum((y - y_hat) ** 2)
    ss_tot = np.sum((y - y.mean()) ** 2)
    r2_5.append(1 - ss_res / ss_tot if ss_tot > 0 else np.nan)
res["r2_5f"] = pd.Series(r2_5, index=idx_level.columns).reindex(res["index"]).to_numpy()
res["delta_r2"] = res["r2_7f"] - res["r2_5f"]
print()
print("เทียบ R² 5-factor เดิม vs 7-factor ใหม่ (เรียงตาม delta มากไปน้อย):")
print(res[["index", "r2_5f", "r2_7f", "delta_r2"]].sort_values("delta_r2", ascending=False).to_string(index=False))
