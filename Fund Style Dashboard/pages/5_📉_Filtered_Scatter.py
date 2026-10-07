"""Filtered Scatter (หน้า 5) — index scatter (return ที่ผ่านมา × vol ที่ทำนาย) + drill-down กองทุน.

ซ้าย = country (18 index) · ขวา = sector (10 index) แกน y = percentile rank ของ forecast vol
(ไม่ใช่ค่าจริงตรงๆ — กัน outlier เช่น MSCI_KOREA ดันจุดอื่นกระจุกกัน ค่าจริงดูได้ที่ hover; ยืนยันกับ
ผู้ใช้ 2026-09-09 หลังลอง linear/log แล้วยังอ่านยาก)
ตารางกองทุนด้านล่างรวมทั้ง 2 scope เป็นตารางเดียว: ไม่คลิกอะไร = โชว์กองทุนทั้งหมดเรียงตาม return 21 วันล่าสุด
คลิกจุดกราฟใดกราฟหนึ่ง = กรองตามกราฟนั้น · คลิกทั้ง 2 กราฟพร้อมกัน = intersection (ต้อง match ทั้งคู่)
"""

import streamlit as st

import config
import data_access
import page_common
import viz
from analysis import matching

st.set_page_config(page_title="Filtered Scatter", page_icon="📉", layout="wide")
st.title("📉 Filtered Scatter")
st.caption(f"แกน x = **return {config.RECENT_RETURN_WINDOW} วันล่าสุด** ของ index (ราคาดิบ ไม่ annualize) · "
           "แกน y = **percentile rank ของ forecast vol** (GARCH(1,1) Student-t, ทำนาย 21 วันข้างหน้า — "
           "ไม่ใช่ค่าจริงตรงๆ กัน index ที่ vol พุ่งสูงผิดปกติดันจุดอื่นกระจุกกัน **ดูค่าจริงที่ hover**) · "
           "สี = 4 quadrant จากค่าจริง (เส้นแบ่ง x=0, y=median ของกราฟนั้น) — "
           "**คลิกจุดเพื่อกรองตารางกองทุนด้านล่าง**")

results = page_common.results_or_stop()
if "return_21d" not in results.columns:
    st.warning("`results.csv` ยังไม่มีคอลัมน์ `return_21d` — รัน `./.venv/bin/python data_access.py` "
               "หรือกดปุ่ม 🔄 Rebuild ที่หน้าแรกก่อน")
    st.stop()

try:
    snapshot = data_access.get_index_snapshot()
    coefs = data_access.get_coefs()
except Exception as e:  # noqa: BLE001
    st.error(f"โหลดข้อมูลไม่สำเร็จ: {type(e).__name__}: {e}")
    st.stop()

# vol forecast มาจาก cache หน้า 4 ซึ่งไม่ rebuild ตามไฟล์ MSCI เอง -> เตือนถ้าเก่ากว่าข้อมูลดัชนีล่าสุด
stale = snapshot[snapshot["vol_asof"] < snapshot["msci_last"]]
if len(stale):
    st.warning(f"vol forecast ของ {len(stale)} index เป็นของวันที่ {stale['vol_asof'].min():%Y-%m-%d} "
               f"แต่ข้อมูล MSCI ล่าสุดถึง {snapshot['msci_last'].max():%Y-%m-%d} — แกน y อาจไม่ตรงปัจจุบัน · "
               "กด 🔄 Rebuild ที่หน้าแรก หรือรัน `./.venv/bin/python data_access.py vol`")
if snapshot["garch_fallback"].any():
    st.caption("⚠️ GARCH fit ไม่ผ่าน ใช้ EWMA แทน: "
               + ", ".join(viz.short(i, s) for i, s in snapshot.loc[snapshot["garch_fallback"], ["index", "scope"]].values))


def _clicked_index(event) -> str | None:
    """ดึงชื่อ index ที่ถูกคลิกจาก event ของ st.plotly_chart(on_select=...).

    รองรับทั้ง dict-access และ attribute-access เพราะ Streamlit คืนคนละรูปแบบกันในแต่ละเวอร์ชัน
    """
    try:
        sel = event["selection"] if isinstance(event, dict) else getattr(event, "selection", None)
        if sel is None:
            return None
        points = sel["points"] if isinstance(sel, dict) else getattr(sel, "points", None)
        if not points:
            return None
        p = points[0]
        cd = p.get("customdata") if isinstance(p, dict) else getattr(p, "customdata", None)
        if cd is None:
            return None
        return cd[0] if isinstance(cd, (list, tuple)) else cd
    except Exception:  # noqa: BLE001 — โครงสร้าง event เปลี่ยน ไม่ควรทำทั้งหน้าพัง
        return None


@st.cache_data(show_spinner=False)
def _matches(scope: str, index_name: str):
    """กอง + บทบาท (primary/secondary) ของ index ที่คลิก — cache ไว้ (สแกน 368 กอง ~130ms/ครั้ง)."""
    return matching.get_index_matches(data_access.get_coefs(), index_name, scope)


def _panel(scope: str, title: str) -> str | None:
    """แสดงกราฟ scope นี้ + warning GARCH fallback (ถ้ามี) -> คืนชื่อ index ที่ถูกคลิก (หรือ None)."""
    st.subheader(title)
    df = snapshot[snapshot["scope"] == scope]
    event = st.plotly_chart(viz.vol_return_scatter(df, scope), key=f"vrs_{scope}",
                            on_select="rerun", selection_mode="points", **page_common.CHART_WIDTH)
    fb = df[df.get("garch_fallback", False) == True]["index"]   # noqa: E712
    if len(fb):
        # sector โชว์ชื่อเต็ม (config.SECTOR_FULL_NAMES) — country ยังคงชื่อสั้นเหมือนเดิม
        name = (lambda i: config.SECTOR_FULL_NAMES.get(i, i)) if scope == "sector" else (lambda i: viz.short(i, scope))
        st.warning(f"⚠️ {len(fb)} index ที่ GARCH fit ไม่ผ่าน ค่าบนแกน y เป็น **EWMA fallback** ไม่ใช่ GARCH: "
                   + ", ".join(name(i) for i in fb))
    return _clicked_index(event)


left, right = st.columns(2)
with left:
    clicked_country = _panel("country", "🌍 Country (18 index)")
with right:
    clicked_sector = _panel("sector", "🏭 Sector (10 index)")

st.divider()

# --- ตารางกองทุนรวม (country + sector) ---
# ไม่คลิกอะไร -> กองทุนทั้งหมด เรียงตาม return_21d
# คลิก 1 กราฟ -> กรองด้วยจุดนั้น (primary หรือ secondary แบบ band-based)
# คลิกทั้ง 2 กราฟ -> intersection ต้อง match ทั้งคู่ (ยืนยันกับผู้ใช้ 2026-09-09)
# กรองกองที่ return_21d เป็น NaN ออกไปเลย (ช่วงข้อมูลห่างเกิน config.RECENT_RETURN_MAX_GAP_DAYS วัน
# คำนวณ return 21 วันไม่น่าเชื่อถือ) -> ตารางนี้โชว์แต่กองที่มี return จริงเท่านั้น (ยืนยันกับผู้ใช้ 2026-09-09)
n_before_gap_filter = len(results)
show = results[results["return_21d"].notna()].copy()
n_excluded_gap = n_before_gap_filter - len(show)
active_labels = []

if clicked_country:
    m = _matches("country", clicked_country).rename(columns={"role": "role_country"})
    show = show.merge(m, on="FundCode", how="inner")
    active_labels.append(f"country = `{viz.short(clicked_country, 'country')}`")

if clicked_sector:
    m = _matches("sector", clicked_sector).rename(columns={"role": "role_sector"})
    show = show.merge(m, on="FundCode", how="inner")
    active_labels.append(f"sector = `{config.SECTOR_FULL_NAMES.get(clicked_sector, clicked_sector)}`")

show = show.sort_values("return_21d", ascending=False)

table_cols = ["FundCode", "FundName", "return_21d"]
col_config = {
    "return_21d": st.column_config.NumberColumn(
        f"return {config.RECENT_RETURN_WINDOW}d", format="percent"),
}
if "role_country" in show.columns:
    table_cols.append("role_country")
    col_config["role_country"] = st.column_config.TextColumn(
        "country match", help="primary/secondary (band-based, ≥{:.0%} ของ primary)".format(
            1 - config.SECONDARY_BAND_PCT))
if "role_sector" in show.columns:
    table_cols.append("role_sector")
    col_config["role_sector"] = st.column_config.TextColumn(
        "sector match", help="primary/secondary (band-based, ≥{:.0%} ของ primary)".format(
            1 - config.SECONDARY_BAND_PCT))

gap_note = (f" (ซ่อน {n_excluded_gap} กองที่ return {config.RECENT_RETURN_WINDOW}d "
            f"คำนวณไม่ได้ — ช่วงข้อมูลห่างเกิน {config.RECENT_RETURN_MAX_GAP_DAYS} วัน)"
            if n_excluded_gap else "")

if not active_labels:
    st.markdown(f"**📋 กองทุนทั้งหมด — {len(show)} กอง เรียงตาม return "
                f"{config.RECENT_RETURN_WINDOW} วันล่าสุด**{gap_note}")
    st.caption("👆 คลิกจุดบนกราฟด้านบน (กราฟใดก็ได้ หรือทั้งสองกราฟพร้อมกัน) เพื่อกรองตาราง")
else:
    suffix = " — ต้อง match ทั้งคู่ (intersection)" if len(active_labels) > 1 else ""
    st.markdown(f"**📋 กองทุนที่ match กับ {' และ '.join(active_labels)}{suffix} — "
                f"{len(show)} กอง**{gap_note}")

if show.empty:
    st.info("ไม่มีกองทุนที่ match กับจุดที่เลือกทั้งหมด")
else:
    st.dataframe(show[table_cols], **page_common.TABLE_WIDTH, hide_index=True, column_config=col_config)

st.caption("⚠️ return ของกองทุนนับจาก **NAV observation ที่ 22 จากท้าย** ไม่ใช่ 21 วันทำการตามปฏิทิน — "
           "กองที่รายงาน NAV ไม่ครบทุกวันจะคลาดเคลื่อนบ้าง (ข้อจำกัดเดียวกับ n_obs) · "
           "ส่วน index MSCI ข้อมูลครบทุกวันทำการจึงไม่มีปัญหานี้ · "
           f"กองที่ 22 จุดล่าสุดกระจายเกิน **{config.RECENT_RETURN_MAX_GAP_DAYS} วัน** ตามปฏิทิน "
           "(รายงาน NAV ห่างเกินไปในช่วงนั้น) ถูก**ตัดออกจากตารางนี้ไปเลย** เพราะ return ที่ได้ไม่น่าเชื่อถือ")
