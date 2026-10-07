"""Match Strength page (Phase 5, Chart 3) — bar ต่อกอง แสดงความแรงของแต่ละ index ที่ match ได้."""

import streamlit as st

import data_access
import page_common
import viz

st.set_page_config(page_title="Match Strength", page_icon="📊", layout="wide")
st.title("📊 Match Strength")
st.caption("เลือกกอง → bar ของ standardized coefficient แต่ละ index · "
           "🔵 primary · 🟢 secondary · ⚪ อื่นๆ (non-zero)")

results = page_common.results_or_stop()   # guard: cache ว่าง/เสีย -> หยุดพร้อมข้อความ (กัน selectbox=None)
coefs = data_access.get_coefs()

c1, c2, c3 = st.columns([3, 1, 1])
with c1:
    labels = (results["FundCode"] + "  —  " + results["FundName"].fillna("")).tolist()
    choice = st.selectbox("เลือกกองทุน", labels)
    fundcode = choice.split("  —  ")[0]
with c2:
    scope = st.radio("มุมมอง", ["country", "sector"], horizontal=False)
with c3:
    model = st.radio("โมเดล", ["elastic", "lasso", "ridge"], horizontal=False,
                     help="elastic=ElasticNet (หลัก) · เทียบกับ lasso/ridge")

row = results[results["FundCode"] == fundcode].iloc[0]
m1, m2, m3 = st.columns(3)
m1.metric(f"R² ({scope})", f"{row[f'{scope}_r2']:.2f}")
m2.metric("Annualized Return", f"{row['ann_return']:.1%}")
m3.metric("Annualized Vol", f"{row['ann_vol']:.1%}")

if model != "elastic":
    st.caption(f"⚠️ primary/secondary ในหน้านี้จัดอันดับจากโมเดล **{model}** ที่เลือก จึงอาจไม่ตรงกับ "
               "Country/Sector Match + ตารางผลลัพธ์ ที่ยึด **ElasticNet** เสมอ (สลับกลับเป็น elastic เพื่อให้ตรงกัน)")

fig = viz.match_strength_bar(coefs, fundcode, scope, model)
if fig is None:
    st.info(f"กองนี้ไม่พบ exposure ชัดเจนกับ {scope} index (โมเดล {model} ตัด coefficient เหลือ 0 ทุกตัว)")
else:
    st.plotly_chart(fig, **page_common.CHART_WIDTH)
