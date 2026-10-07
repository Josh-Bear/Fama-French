"""page_common.py — helper ที่หน้า scatter (Country/Sector) ใช้ร่วมกัน + guard โหลด cache.

รวม logic ที่เดิม copy-paste ระหว่าง pages/1 กับ pages/2 (F9) และ guard get_results (F5)
"""

from __future__ import annotations

import inspect

import pandas as pd
import streamlit as st

import data_access
import viz


def _full_width(element) -> dict:
    """kwargs ให้ตาราง/กราฟกว้างเต็มคอลัมน์ได้ทั้ง Streamlit ใหม่และเก่า.

    รุ่นใหม่ (width ค่าเริ่มต้น "stretch") เลิกใช้ use_container_width · รุ่นเก่า (เช่น 1.40) รับ width เป็นตัวเลขเท่านั้น
    → ส่ง width="stretch" ให้รุ่นเก่าแล้ว TypeError ทั้งหน้า
    """
    width = inspect.signature(element).parameters.get("width")
    return {"width": "stretch"} if width is not None and width.default == "stretch" else {"use_container_width": True}


# ใช้แทน width="stretch" / use_container_width=True: st.dataframe(df, **TABLE_WIDTH) · st.plotly_chart(fig, **CHART_WIDTH)
TABLE_WIDTH = _full_width(st.dataframe)
CHART_WIDTH = _full_width(st.plotly_chart)


def results_or_stop():
    """โหลดผลวิเคราะห์ พร้อม guard — cache เสีย/ว่าง แสดงข้อความชัดแทน traceback ดิบ."""
    try:
        results = data_access.get_results()
    except Exception as e:  # noqa: BLE001
        st.error(f"โหลดผลวิเคราะห์ไม่สำเร็จ: {type(e).__name__}: {e}\n\n"
                 "ลองรัน `./.venv/bin/python data_access.py` เพื่อ build cache ใหม่")
        st.stop()
    if results is None or results.empty:
        st.warning("ยังไม่มีผลวิเคราะห์ใน cache — รัน `./.venv/bin/python data_access.py` ก่อน")
        st.stop()
    return results


def scatter_page(scope: str, title: str, extra_caption: str = "",
                 results: pd.DataFrame | None = None,
                 extra_table_cols: list[str] | None = None,
                 r2_slider: tuple[float, float] = (1.0, 0.05), r2_label: str = "R²") -> None:
    """เรนเดอร์หน้า scatter (country/sector/style) — x=return, y=vol, สี=4 quadrant + filter.

    results          : None = โหลด results.csv เอง (หน้า 1/2 เดิม) · ส่งมาเอง = ใช้ DataFrame นั้น (หน้า 6 ที่ต้อง merge style)
    extra_table_cols : คอลัมน์เพิ่มท้ายตารางข้อมูล (เช่น mkt_beta ของหน้า 6)
    r2_slider / r2_label : (ค่าสูงสุด, step) ของ slider และชื่อ R² — หน้า 6 ใช้ incremental R² (~0-0.1) ต้องสเกลต่างจากหน้า 1/2
    ต้องมีคอลัมน์ {scope}_primary / {scope}_secondary / {scope}_r2 ใน results
    """
    st.title(title)
    results = results_or_stop() if results is None else results
    st.caption(f"{len(results)} กอง · x=annualized return · y=annualized volatility · "
               f"สี=4 quadrant (เส้นแบ่ง: return=0, volatility=median) · ขนาดจุดคงที่ (AUM ดูได้ใน hover)")

    prim_col = f"{scope}_primary"
    # ไม่มีตัวกรอง Fund Policy แล้ว — ทั้งแอปเหลือ config.APP_POLICY อย่างเดียวตั้งแต่ pipeline (2026-09-29)
    c2, c3 = st.columns([4, 1])
    with c2:
        opts = sorted({viz.short(x, scope) for x in results[prim_col].dropna().unique()})
        pick = st.multiselect(f"primary {scope} (ว่าง=ทั้งหมด)", opts)
    with c3:
        min_r2 = st.slider(f"{r2_label} ขั้นต่ำ", 0.0, r2_slider[0], 0.0, r2_slider[1],
                           help=f"ซ่อนกองที่ match ไม่มั่นใจ ({r2_label} {scope} ต่ำ)")

    df = results[results[f"{scope}_r2"] >= min_r2]
    if pick:
        df = df[df[prim_col].map(lambda x: viz.short(x, scope)).isin(pick)]

    if df.empty:
        st.warning("ไม่มีกองที่ตรงเงื่อนไข filter")
        return

    st.plotly_chart(viz.scatter(df, scope, r2_label=r2_label), **CHART_WIDTH)
    st.caption(f"แสดง {len(df)}/{len(results)} กอง" + (f" · {extra_caption}" if extra_caption else "")
               + " · แกนตัดที่ 1-99 percentile ของกองที่แสดงอยู่ (กันกอง outlier ผันผวนสูงดันสเกล) "
                 "— ซูมออกได้ตามปกติถ้าอยากเห็นกอง outlier ที่หลุดขอบ")
    with st.expander("📋 ตารางข้อมูล"):
        show = df[["FundCode", "FundName", prim_col, f"{scope}_secondary",
                   f"{scope}_r2", "ann_return", "ann_vol", "n_obs", "aum"]
                  + list(extra_table_cols or [])].copy()
        show[prim_col] = show[prim_col].map(lambda x: viz.primary_label(x, scope))
        show[f"{scope}_secondary"] = show[f"{scope}_secondary"].map(lambda x: viz.short(x, scope))
        st.dataframe(show, **TABLE_WIDTH, hide_index=True)
