"""app.py — Streamlit entrypoint (MSCI Fund Country/Sector Classification Dashboard).

หน้าแรก: ภาพรวม + สถานะผลวิเคราะห์. หน้ากราฟอยู่ใน pages/
"""

import streamlit as st

import config
import data_access

st.set_page_config(page_title="MSCI Fund Style Dashboard", page_icon="🌍", layout="wide")

st.title("🌍 MSCI Fund Country/Sector Classification Dashboard")
st.caption("จัดกลุ่มกองทุนไทย (FIF) ตาม exposure ประเทศ/sector ด้วย multi-factor regression กับ MSCI index")

try:
    results = data_access.get_results()
except Exception as e:  # noqa: BLE001 — สื่อสารชัด ไม่ crash เงียบ
    st.error(f"โหลดผลวิเคราะห์ไม่สำเร็จ: {type(e).__name__}: {e}\n\n"
             "ลองรัน `./.venv/bin/python data_access.py` เพื่อ build cache ใหม่")
    st.stop()

c1, c2, c3 = st.columns(3)
c1.metric(f"กองหุ้นที่วิเคราะห์ ({config.APP_POLICY})", f"{len(results)}")
c2.metric("R² เฉลี่ย (country)", f"{results['country_r2'].mean():.2f}")
c3.metric("R² เฉลี่ย (sector)", f"{results['sector_r2'].mean():.2f}")

st.info(f"วิเคราะห์ **{len(results)} กองหุ้น (policy {config.APP_POLICY})** — กองตราสารหนี้/อื่นๆ ถูกตัดตั้งแต่ pipeline "
        f"เพราะ 28 ดัชนีที่ใช้เป็นดัชนีหุ้นล้วน อธิบายกองพวกนั้นไม่ได้ (R² เฉลี่ย 0.15-0.17) · "
        f"นับเฉพาะกองที่มีจุดข้อมูล NAV > {config.MIN_DATA_POINTS} จุด · ใช้เมนูซ้าย: "
        "**🌍 Country Match** · **🏭 Sector Match** · **📊 Match Strength** · **🔮 Vol Forecast** · "
        "**📉 Filtered Scatter** · **🎯 Style Match** · **🌐 Macro Chain** · **🧭 Score Screen** · **📈 TF Portfolio** · **🗺 M019 Frontier** · **🧭 M052 Frontier**")

st.markdown(
    """
**วิธีทำงาน:** กรองกองทุน FIF ตามเกณฑ์ → สร้าง return series จาก NAV (align ด้วย NAVDate + ทบต้น index
ตลอดช่วงที่กองไม่รายงาน) → regress กับ MSCI index ทั้งชุด (ElasticNet, standardize) →
จัด primary/secondary exposure จากขนาด coefficient → พล็อต scatter + match strength
"""
)

with st.expander("ℹ️ ข้อจำกัด / สมมติที่ควรรู้"):
    st.markdown(
        "- **ครอบคลุม {n_funds}/{n_univ} กอง ({pct:.0%})** — กองที่รายงาน NAV น้อย (< {n} จุด) หรือมีข้อมูล"
        "ในช่วง MSCI ไม่พอ หรือ NAV ล่าสุดเก่ากว่าดัชนีเกิน {stale} วัน / เลิกกองแล้ว ถูกตัดออก ไม่ใช่ทุกกอง FIF\n"
        "- **MSCI_COUNTRY ไม่มี index ไทยตรงๆ** (ใกล้สุด = ASEAN)\n"
        "- **collinearity**: ชุด 18 country index มี index รวม (ACWI/WORLD) → บางกอง (โดยเฉพาะกอง US) "
        "อาจถูก aggregate แย่ง primary ไป — ดู R² ประกอบ\n"
        "- **เฉพาะกอง {policy}** (`APP_POLICY`) — กอง F/O ถูกตัดตั้งแต่ build_pipeline เพราะ factor เป็นดัชนีหุ้นล้วน\n"
        "- ช่วงข้อมูล {start} → 2026-07 · primary/secondary จาก |standardized coefficient|".format(
            n_funds=len(results), n_univ=config.EXPECTED_FILTERED_FUNDS_E, policy=config.APP_POLICY,
            pct=len(results) / config.EXPECTED_FILTERED_FUNDS_E,
            n=config.MIN_DATA_POINTS, start=config.DATA_START, stale=config.NAV_STALE_MAX_DAYS)
    )

if st.button("🔄 Rebuild ผลวิเคราะห์ใหม่ (ช้า ~3-4 นาที)"):
    try:
        with st.spinner("กำลัง build pipeline ใหม่ (โหลด nav 336MB + regress กอง E ×2 scope + vol + style + macro + score + TF portfolio)…"):
            data_access.rebuild()
        st.success("rebuild เสร็จ")
        st.rerun()
    except Exception as e:  # noqa: BLE001
        st.error("rebuild ไม่ครบ — ขั้นที่เสร็จก่อน error ถูกบันทึกแล้ว ขั้นที่เหลือยังเป็น cache เดิม: "
                 f"{type(e).__name__}: {e}")
