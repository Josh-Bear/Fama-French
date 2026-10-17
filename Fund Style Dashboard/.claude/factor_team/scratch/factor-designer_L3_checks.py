"""factor-designer: ตรวจตัวเลขสำหรับแก้ L2_summary (ค่าชั่วคราว 62) และเขียน L3_summary
อ่าน CSV ใน runs/ อย่างเดียว · ไม่ fit model · ไม่ดูผลตอบแทนดิบ
"""
import hashlib, json, pathlib
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[1]
S5 = ROOT / "runs" / "S005"
S6 = ROOT / "runs" / "S006"
out = {}

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

files = [S5 / "rolling_104.csv", S6 / "rolling_104.csv", S6 / "fund_level.csv", S6 / "primary_C.csv",
         S5 / "primary_index.csv", S6 / "vif_elim_A.csv", S6 / "q1_verdict.csv"]
out["sha256"] = {str(p.relative_to(ROOT)): sha(p) for p in files}

# 1) S006 rolling: แถวอ้างอิง (= โมเดลเดียวกับ S005) หน้าต่างแรก vs สุดท้าย
r6 = pd.read_csv(S6 / "rolling_104.csv")
ref = r6[r6["row"].isin(["ref_base_1a", "ref_base_1c", "ref_L2_1a", "ref_L2_1c"])]
out["s006_ref_first_last"] = {
    f"{r.row}|{r.policy}|{r.factor}": [round(r.roll_median, 3), round(r.roll_min, 3), round(r.corr_first_last, 3)]
    for r in ref.itertuples()}
# B-all e ของ P4: หน้าต่างแรก vs สุดท้าย (E)
ball = r6[r6["row"].isin(["R2", "R7"]) & (r6["policy"] == "E")]
out["s006_Ball_first_last_E"] = {f"{r.row}|{r.factor}": round(r.corr_first_last, 3) for r in ball.itertuples()}

# 2) S005 rolling: ค่าเฉลี่ยรวม / ไม่รวม PRIM และตรวจว่าแถวอ้างอิงของ S006 ตรง S005
r5 = pd.read_csv(S5 / "rolling_104.csv")
k4 = r5[r5["key"].str.endswith("@4") | ~r5["key"].str.contains("@")] if "key" in r5 else r5
agg = {}
for (m, pol), g in r5.groupby(["model", "policy"]):
    ex = g[g["factor"] != "PRIM"]
    agg[f"{m}|{pol}"] = {"n_factor": int(len(g)), "has_PRIM": bool((g["factor"] == "PRIM").any()),
                         "mean_med_exPRIM": round(ex["roll_median"].mean(), 3),
                         "mean_med_inclPRIM": round(g["roll_median"].mean(), 3),
                         "min_min_exPRIM": round(ex["roll_min"].min(), 3),
                         "min_min_inclPRIM": round(g["roll_min"].min(), 3),
                         "keys": sorted(g["key"].unique().tolist())}
out["s005_rolling_agg"] = agg
m5 = r5[(r5["model"] == "ฐาน 1a") & (r5["policy"] == "E")].set_index("factor")["roll_median"]
m6 = r6[(r6["row"] == "ref_base_1a") & (r6["policy"] == "E")].set_index("factor")["roll_median"]
out["ref_base_1a_S005_vs_S006_maxabs"] = float((m5 - m6.reindex(m5.index)).abs().max())
m5b = r5[(r5["model"] == "L2-1") & (r5["policy"] == "E")].set_index("factor")["roll_median"]
m6b = r6[(r6["row"] == "ref_L2_1a") & (r6["policy"] == "E")].set_index("factor")["roll_median"]
out["L2_1_S005_vs_S006_maxabs"] = float((m5b - m6b.reindex(m5b.index)).abs().max())

# 3) vif_elim_A (มี Dimson ต่อคอลัมน์ไหม)
ve = pd.read_csv(S6 / "vif_elim_A.csv")
out["vif_elim_A_cols"] = ve.columns.tolist()
out["vif_elim_A"] = ve.astype(str).values.tolist()

# 4) m4: A-prim / L2 / B-prim บน 38 กอง E เดียวกัน (L2 primary ∈ P4)
P4 = ["MSCI_ACWI_HC", "MSCI_ACWI_UT", "MSCI_EUROPE", "MSCI_INDIA", "MSCI_JAPAN", "MSCI_VIETNAM"]
pi = pd.read_csv(S5 / "primary_index.csv")
fl = pd.read_csv(S6 / "fund_level.csv")
EVAL = set(fl.loc[fl["row"] == "R12", "FundCode"])
res = {}
for base, form, rows in [("1a", "1a@4", ["R1", "ref_L2_1a", "R3"]), ("1c", "1c@4", ["R6", "ref_L2_1c", "R8"])]:
    p = pi[(pi["form"] == form) & pi["FundCode"].isin(EVAL)]
    sub = set(p.loc[p["index"].isin(P4), "FundCode"])
    for r in rows:
        g = fl[(fl["row"] == r) & (fl["policy"] == "E") & fl["FundCode"].isin(sub)]
        res[f"{base}|{r}"] = {"n": int(len(g)), "med_d_r2_oos": round(g["d_r2_oos"].median(), 4),
                              "med_d_bic": round(g["d_bic"].median(), 2)}
    pn = pi[(pi["form"] == "none") & pi["FundCode"].isin(EVAL)]
    res[f"{base}|same_set_as_none"] = sub == set(pn.loc[pn["index"].isin(P4), "FundCode"])
out["m4_same_38"] = res

# 5) ETF ธีมในกลุ่ม ACWI_CD (L2 primary form none) → ตัวเลือก C-prim
pc = pd.read_csv(S6 / "primary_C.csv")
pn = pi[(pi["form"] == "none") & pi["FundCode"].isin(EVAL)]
cd = pn.loc[pn["index"] == "MSCI_ACWI_CD", "FundCode"]
pol = fl[fl["row"] == "R12"].set_index("FundCode")["policy"]
j = pc[pc["FundCode"].isin(cd)].copy()
j["policy"] = j["FundCode"].map(pol)
out["acwi_cd_n"] = int(len(cd))
out["acwi_cd_cprim_counts"] = j["index"].value_counts().to_dict()
out["acwi_cd_cprim_by_policy"] = j.groupby(["policy", "index"]).size().to_dict().__repr__()
# R²_oos ของ C-prim vs ①a ในกลุ่ม ACWI_CD (E) — อ่านจาก fund_level
for r in ["R12", "ref_base_1a", "ref_3a", "R11"]:
    g = fl[(fl["row"] == r) & fl["FundCode"].isin(cd) & (fl["policy"] == "E")]
    out[f"acwi_cd_E_{r}_r2oos_med"] = [int(len(g)), round(g["r2_oos"].median(), 3)]

print(json.dumps(out, ensure_ascii=False, indent=1, default=str))
