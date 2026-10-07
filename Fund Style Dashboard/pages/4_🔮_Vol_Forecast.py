"""Vol Forecast page (หน้า 4) — EWMA vs GARCH annualized-vol forecast ของ MSCI index (index-level)."""

import contextlib
import os

import plotly.graph_objects as go
import streamlit as st

import config
import data_access
import page_common
import viz
from analysis import vol_forecast as vf

st.set_page_config(page_title="Vol Forecast", page_icon="🔮", layout="wide")
st.title("🔮 Vol Forecast")
st.caption(f"ทำนาย annualized volatility ของ MSCI index {config.VOL_FORECAST_HORIZON} วันข้างหน้า · "
           "EWMA (baseline) vs GARCH(1,1) · walk-forward expanding window")

# ถ้ายังไม่มี cache -> get_* จะ auto-build (~10 วิ) -> โชว์ spinner ให้รู้ว่าไม่ได้ค้าง
_building = not (os.path.exists(data_access.VOL_BACKTEST_CSV) and os.path.exists(data_access.VOL_LATEST_CSV))
_guard = st.spinner("กำลัง build vol forecast cache ครั้งแรก (~10 วิ: EWMA/GARCH 28 index)…") \
    if _building else contextlib.nullcontext()
try:
    with _guard:
        bt = data_access.get_vol_forecast_backtest()
        latest = data_access.get_vol_forecast_latest()
except Exception as e:  # noqa: BLE001
    st.error(f"โหลด vol forecast cache ไม่สำเร็จ: {type(e).__name__}: {e}\n\n"
             "รัน `./.venv/bin/python data_access.py vol` เพื่อ build cache")
    st.stop()

c1, c2 = st.columns([1, 3])
with c1:
    scope = st.radio("scope", ["country", "sector"], horizontal=True)
with c2:
    opts = sorted(latest[latest["scope"] == scope]["index"])
    ix = st.selectbox("เลือก index", opts, format_func=lambda x: viz.short(x, scope))

row = latest[(latest["scope"] == scope) & (latest["index"] == ix)].iloc[0]
H = config.VOL_FORECAST_HORIZON

# --- Section A: forecast ล่าสุด ---
st.subheader("📍 Forecast ล่าสุด")
m1, m2, m3 = st.columns(3)
m1.metric(f"Realized vol ({H}d ที่ผ่านมา)", f"{row['last_realized']:.1%}")
m2.metric(f"EWMA forecast (→{H}d)", f"{row['ewma_forecast']:.1%}")
m3.metric(f"GARCH forecast (→{H}d)", f"{row['garch_forecast']:.1%}",
          delta="fallback→EWMA" if row["garch_fallback"] else None, delta_color="off")

# --- Section B: walk-forward backtest line chart ---
st.subheader("📈 Walk-forward backtest")
d = bt[(bt["scope"] == scope) & (bt["index"] == ix)].sort_values("window_end")
fig = go.Figure()
fig.add_scatter(x=d["window_end"], y=d["realized_vol"], name="Realized",
                mode="lines", line=dict(color="#d62728", width=2.8))   # แดงทึบ = ค่าจริง (เด่นทั้งธีมมืด/สว่าง)
fig.add_scatter(x=d["window_end"], y=d["ewma_forecast"], name="EWMA",
                mode="lines", line=dict(color="#e5b700", dash="dash"))
fig.add_scatter(x=d["window_end"], y=d["garch_forecast"], name="GARCH",
                mode="lines", line=dict(color="#1f77b4", dash="dash"))
fig.update_layout(yaxis_tickformat=".0%", yaxis_title="annualized vol", xaxis_title="",
                  legend_title_text="", hovermode="x unified")
st.plotly_chart(fig, **page_common.CHART_WIDTH)

# --- Section C: model comparison ---
st.subheader("🏆 Model comparison — RMSE/MAE บน vol · QLIKE บน variance (ต่ำ = ดีกว่า)")
# ประเมินเฉพาะ scope ปัจจุบัน -> "ALL" = รวมทุก index ใน scope นี้ (ไม่ปน country กับ sector)
mt = vf.evaluation_metrics(bt[bt["scope"] == scope])
n_ix = bt[bt["scope"] == scope]["index"].nunique()
sel = mt[mt["index"].isin(["ALL", ix])].copy()
sel["index"] = sel["index"].map(lambda x: f"ทุก {scope} ({n_ix})" if x == "ALL" else viz.short(x, scope))
st.dataframe(sel[["index", "model", "n", "RMSE", "MAE", "QLIKE"]].round(4),
             **page_common.TABLE_WIDTH, hide_index=True)

st.caption(f"⚠️ ข้อจำกัด: ~{len(d)} window/index (non-overlap {H}d) — sample เล็กทางสถิติ · "
           "ช่วง 2021-2026 ไม่ครอบคลุม regime วิกฤตรุนแรง (2008/2020) · เป็น index-level ไม่ใช่ fund-level · "
           "GARCH ที่ fit ไม่ผ่านจะ fallback เป็น EWMA")
