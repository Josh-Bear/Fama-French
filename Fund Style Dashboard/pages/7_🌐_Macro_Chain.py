"""Macro Chain (หน้า 7) — ความไวของกอง E ต่อ 7 ปัจจัยมหภาค: implied (chain ผ่าน country/sector) คู่ direct (regress NAV ตรง).

เฉพาะกอง E (config.MACRO_POLICY) — กรองตั้งแต่ pipeline เหมือนหน้า 6
รายละเอียดวิธีคำนวณ: docs/pages/7-macro-chain.md
"""

import streamlit as st

import config
import data_access
import page_common
import viz
from data import style_factor

st.set_page_config(page_title="Macro Chain", page_icon="🌐", layout="wide")
st.title("🌐 Macro Chain")

try:
    loadings = data_access.get_macro_loadings()
    betas = data_access.get_macro_index_betas()
except style_factor.SnapshotMissingError as e:   # ยังไม่มี snapshot macro — แอปไม่ดึงเน็ตเอง
    st.warning(f"{e}\n\nจากนั้นรัน `./.venv/bin/python data_access.py macro` เพื่อสร้างผลของหน้านี้")
    st.stop()
except Exception as e:  # noqa: BLE001
    st.error(f"โหลดผล macro ไม่สำเร็จ: {type(e).__name__}: {e}")
    st.stop()

results = page_common.results_or_stop()
FACTORS = config.MACRO_FACTOR_COLS
funds = results[results["FundCode"].isin(loadings["FundCode"])]
st.caption(f"เฉพาะกอง {config.MACRO_POLICY} ({len(funds)} กอง) · กองขยับกี่ % ในเดือนที่ macro ขยับ 1 SD · "
           "🔵 implied = อนุมานผ่าน country/sector ของกอง · 🟠 direct = regress NAV รายเดือนตรง · "
           f"◆ = median ของกอง {config.MACRO_POLICY} ทั้งหมด")

labels = (funds["FundCode"] + "  —  " + funds["FundName"].fillna("")).tolist()
fundcode = st.selectbox("เลือกกองทุน", labels).split("  —  ")[0]
sub = loadings[loadings["FundCode"] == fundcode]
r2 = sub.groupby("method")["r2"].first()
n_months = int(sub["n_months"].iloc[0])

m1, m2, m3 = st.columns(3)
m1.metric("R² implied", "—" if r2.isna()["implied"] else f"{r2['implied']:.2f}",
          help="corr² ของค่าที่ chain ทำนายกับ return รายเดือนจริง (ไม่ได้ fit กับกองนี้เลย)")
m2.metric("R² direct", "—" if r2.isna()["direct"] else f"{r2['direct']:.2f}",
          help="R² ของ OLS รายเดือน 7 factor (ในตัวอย่าง — 8 พารามิเตอร์ต่อ ~60 เดือน สูงเกินจริงเล็กน้อย)")
m3.metric("จำนวนเดือน", n_months)

if r2.isna()["direct"]:
    st.info(f"กองนี้มีข้อมูล {n_months} เดือน (< {config.MACRO_MIN_MONTHS}) — ไม่คำนวณ direct")

peer_median = loadings.pivot_table(index="factor", columns="method", values="impact_1sd", aggfunc="median")
factor_sd = betas.groupby("factor")["factor_sd"].first()
st.plotly_chart(viz.macro_bar(loadings, fundcode, factor_sd, peer_median), **page_common.CHART_WIDTH)
st.info("implied เป็นค่า**อนุมาน**ผ่านโครงสร้าง country/sector ที่โมเดลจับได้ ไม่ใช่พฤติกรรมจริงของกอง — "
        "ไม่เห็น FX hedge หรือการเลือกหุ้นที่เบี่ยงจาก index · ทั้งสองวิธีเป็นความสัมพันธ์เชิงสถิติย้อนหลัง")

with st.expander("ℹ️ อ่านหน้านี้ยังไง"):
    st.markdown(
        f"""
**แท่งกราฟ** = return รายเดือนของกองที่เปลี่ยนไปเมื่อ macro ขยับ 1 SD (ขนาด 1 SD อยู่ใต้ชื่อ factor)
บวก = เคลื่อนทางเดียวกับ macro · ใช้ 1 SD เพราะหน่วยดิบต่างกัน (return / จุด VIX / pp yield) เทียบข้าม factor ไม่ได้
◆ = median ของกอง {config.MACRO_POLICY} ทั้งหมด ใช้ดูว่ากองนี้ไวกว่าหรือน้อยกว่ากองหุ้นทั่วไป

**🔵 implied** = β ของกองต่อ 28 index (หน้า 1-3 แปลงเป็นหน่วยจริงแล้ว) × β ของ index ต่อ macro (Stage 1)
คำนวณแยก country กับ sector แล้ว**เฉลี่ย** (แต่ละชุดอธิบายกองทั้งก้อน — บวกกันจะนับตลาดซ้ำ)
**🟠 direct** = regress NAV รายเดือนของกองกับ macro ตรงๆ (≥ {config.MACRO_MIN_MONTHS} เดือน) เห็นทุกอย่างรวม hedge ค่าเงิน แต่ noise สูงกว่า
**สองแท่งห่างกันมาก** = กองมี exposure ที่ index หุ้นไม่ได้จับ (เช่น หุ้นเหมืองทอง · REIT · hedge ค่าเงิน) หรือ direct เป็น noise

**ทำไมมีแต่กอง {config.MACRO_POLICY}** — implied มองผ่าน index หุ้นเท่านั้น จึงมองไม่เห็นความไวของกองบอนด์ต่อ US10Y
หรือกองทองต่อ Gold (กองทอง: direct Gold ~0.7-0.9 แต่ implied ~0.1)

**ข้อควรระวัง**
- **VIX** ≈ proxy ตลาดหุ้นโลก (ขยับสวนตลาด) — กองหุ้นเกือบทุกกองจึงติดลบกับ VIX มากสุด
- **USDTHB กับ DXY** เคลื่อนด้วยกัน (corr 0.71) — แยกผลสองตัวนี้ได้ไม่เสถียร ให้ดูผลรวม
- **Oil / Gold / DXY** มีนัยสำคัญใน Stage 1 เพียงไม่กี่ index (ยกเว้น Energy กับ Oil) — implied ของ 3 ตัวนี้ส่วนใหญ่เป็น noise
- implied เล็กกว่าจริงเล็กน้อย (~15-25%) เพราะ ElasticNet หดค่า coef · Oil/Gold/Copper เป็น futures ต่อเนื่อง (มี roll gap)
- Stage 1 ใช้ {int(betas['n_obs'].iloc[0])} เดือน — ตัวอย่างไม่ใหญ่ ควรดูความเสถียรเมื่อข้อมูลสะสมมากขึ้น
"""
    )

with st.expander("📋 ตาราง impact ทุกกอง (% ต่อ 1 SD — เรียงคอลัมน์ได้)"):
    method = st.radio("วิธี", list(viz.MACRO_METHOD_STYLE), horizontal=True)
    tbl = loadings[loadings["method"] == method].pivot(index="FundCode", columns="factor", values="impact_1sd")
    tbl = results.set_index("FundCode")[["FundName"]].join(tbl[FACTORS] * 100, how="inner")
    pct = {c: st.column_config.NumberColumn(format="%.2f%%") for c in FACTORS}
    st.dataframe(tbl, **page_common.TABLE_WIDTH, column_config=pct)

with st.expander("🧭 Stage 1 — index ไวต่อ macro แค่ไหน (% ต่อ 1 SD)"):
    s1 = betas.pivot(index="index", columns="factor", values="impact_1sd")[FACTORS] * 100
    meta = betas.groupby("index")[["scope", "r2"]].first()
    s1.insert(0, "R²", meta["r2"])
    s1.index = [viz.short(ix, meta.loc[ix, "scope"]) for ix in s1.index]
    st.dataframe(s1.sort_values("R²", ascending=False), **page_common.TABLE_WIDTH,
                 column_config={**pct, "R²": st.column_config.NumberColumn(format="%.2f")})
