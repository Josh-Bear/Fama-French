"""Style Match (หน้า 6) — scatter กอง E × style tilt (Momentum / Quality / Value / Low-Vol).

regress กองกับ [control 3 ตัว (ตลาดโลกฝั่ง MSCI + ฝั่ง ETF, US ชนะโลก) + 4 style factor] แล้วติดป้าย style ตามเครื่องหมาย coef
รายละเอียดวิธีคำนวณ: docs/pages/6-style-match.md
"""

import streamlit as st

import config
import data_access
import page_common
from data import style_factor

st.set_page_config(page_title="Style Match", page_icon="🎯", layout="wide")

try:
    style = data_access.get_style_results()
except style_factor.SnapshotMissingError as e:   # ยังไม่มี snapshot ETF — แอปไม่ดึงเน็ตเอง (FileNotFoundError อื่นไปทาง error ปกติ)
    st.title("🎯 Style Match")
    st.warning(f"{e}\n\nจากนั้นรัน `./.venv/bin/python data_access.py style` เพื่อสร้างผลของหน้านี้")
    st.stop()
except Exception as e:  # noqa: BLE001
    st.title("🎯 Style Match")
    st.error(f"โหลดผล style ไม่สำเร็จ: {type(e).__name__}: {e}")
    st.stop()

base = page_common.results_or_stop()
merged = base.merge(style, on="FundCode", how="inner")    # เฉพาะกองที่มีผล style (กอง E)

page_common.scatter_page(
    "style", "🎯 Style Match",
    extra_caption=f"เฉพาะกอง {config.STYLE_POLICY} · R² = incremental (ส่วนที่ style อธิบายเพิ่มจากตลาด)",
    results=merged,
    extra_table_cols=["mkt_beta", "style_r2_full"],
    r2_slider=(0.20, 0.01), r2_label="incremental R²",   # median ~0.04 · p90 ~0.09 -> สเกล 0-1 ใช้ไม่ได้
)

with st.expander("ℹ️ อ่านหน้านี้ยังไง"):
    labels = " · ".join(f"{f}: **{pos}** (+) / **{neg}** (−)" for f, (pos, neg) in config.STYLE_LABELS.items())
    st.markdown(
        f"""
**ป้าย style ดูเครื่องหมายด้วย** — {labels}
เช่น coefficient ของ Value ติดลบมาก = กองนั้นเอียงไปทาง **Growth** (ต่างจากหน้า 1-3 ที่ดูแค่ขนาด)

**style factor มาจากไหน** — iShares MSCI factor ETF (MTUM/QUAL/VLUE ผสมกับ IMTM/IQLT/IVLU สัดส่วน US {config.STYLE_US_WEIGHT:.0%}
และ ACWV) แล้ว **หารด้วย ACWI** เพื่อตัดผลตลาดออก เหลือเฉพาะ "ส่วนที่ต่างจากตลาด" (ETF พวกนี้เคลื่อนตามตลาด 0.80-0.95)

**ตัวแปรควบคุม 3 ตัว (ไม่นับเป็น style)** — ตลาดโลกทั้ง "โลก MSCI" (MSCI_ACWI, THB — ตรงกับ NAV กอง)
และ "โลก ETF" (ACWI ETF, USD — ตรงกับ style factor) + "US ชนะโลก" (MSCI_USA÷MSCI_ACWI)
ถ้าไม่คุมตลาดทั้งสองโลก กองเกือบทั้งหมดจะติดป้าย High-Beta ปลอม · ถ้าไม่คุม US ชนะโลก กองที่หนัก US จะดูเป็น Growth เกินจริง

**R² ของหน้านี้คือ incremental R²** = R²(ตลาด+style) − R²(ตลาดอย่างเดียว) — ค่า**ต่ำเป็นเรื่องปกติ** เพราะตลาดอธิบายกองหุ้นไปเกือบหมดแล้ว
style คือส่วนเสี้ยวที่เหลือ ค่าต่ำ ≠ โมเดลผิด · `style_r2_full` ในตาราง = R² รวมทั้งตลาด · `mkt_beta` = beta ตลาดโลกรวมของกอง (ทั้งสองโลก จากโมเดลที่มีแค่ตัวแปรควบคุม) — ~1 เคลื่อนตามตลาด · >1 แรงกว่า · <1 นิ่งกว่า

**ข้อจำกัด** — ETF ทุกตัวปิดตามเวลา US (ข้อจำกัดเดียวกับ MSCI_USA ในหน้า 1) ความพอดีจึงหยาบกว่ากองที่ลงทุนเอเชีย ·
ช่วงข้อมูล 2021-2026 · เป็นความสัมพันธ์เชิงสถิติ ไม่ใช่พอร์ตถือครองจริง
"""
    )
