"""viz.py — helper สร้างกราฟ plotly สำหรับหน้า dashboard (Phase 5).

รวม logic ที่ Country/Sector page ใช้ร่วมกัน (scatter + quadrant) และ Match Strength bar
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

import config
from analysis import matching

# 4-quadrant: เส้นตั้ง return=0, เส้นนอน volatility=median (config.QUADRANT_VOL_SPLIT)
Q1, Q2, Q3, Q4 = ("🟢 กำไร·ผันผวนสูง", "🔴 ขาดทุน·ผันผวนสูง",
                  "🟡 ขาดทุน·ผันผวนต่ำ", "🔵 กำไร·ผันผวนต่ำ")
# สีตามที่ผู้ใช้กำหนด (2026-09-09): 🔵 กำไร·ต่ำ · 🟢 กำไร·สูง · 🟡 ขาดทุน·ต่ำ · 🔴 ขาดทุน·สูง
# (สลับจากเดิมที่ Q2/Q3 ใช้สีตรงข้าม — แดง=แย่ที่สุด(ขาดทุน+ผันผวนสูง), เหลือง=ยังพอรับได้(ขาดทุน+ผันผวนต่ำ))
QUADRANT_COLORS = {Q1: "#2ca02c", Q2: "#d62728", Q3: "#e5b700", Q4: "#1f77b4"}

PRIMARY_C, SECONDARY_C, OTHER_C = "#1f77b4", "#2ca02c", "#b0b0b0"


NO_EXPOSURE = "ไม่พบ exposure ชัดเจน"   # กองที่ ElasticNet ตัด coefficient เหลือ 0 หมด (ตามที่ confirm ในแผน)


def short(name, scope: str = "country") -> str:
    """ตัด prefix ให้อ่านง่าย — sector ตัด MSCI_ACWI_ ด้วย (single source ใช้ทั้ง scatter/filter/bar)."""
    if pd.isna(name):
        return "—"
    s = str(name)
    if scope == "sector":
        s = s.replace("MSCI_ACWI_", "")
    return s.replace("MSCI_", "")


def primary_label(name, scope: str = "country") -> str:
    """ชื่อ index สำหรับช่อง primary — NaN (ไม่มี exposure) โชว์ข้อความเต็มตามแผน ไม่ใช่ '—'."""
    return short(name, scope) if pd.notna(name) else NO_EXPOSURE


def _percentile_range(s: pd.Series, lo_q: float = 0.01, hi_q: float = 0.99,
                       pad_frac: float = 0.08, floor_zero: bool = False) -> tuple[float, float] | None:
    """ช่วงแกนตัดที่ percentile (กันจุด outlier ดันสเกลจนจุดอื่นดูแบนราบ) + เผื่อขอบ pad_frac.

    คืน None ถ้าข้อมูลน้อยเกินไปจน range คำนวณไม่ได้ (เช่น <2 จุด หรือค่าเท่ากันหมด) -> ให้ Plotly autorange แทน
    """
    s = s.dropna()
    if len(s) < 2:
        return None
    lo, hi = s.quantile([lo_q, hi_q])
    if hi <= lo:
        return None
    pad = (hi - lo) * pad_frac
    lo, hi = lo - pad, hi + pad
    if floor_zero:
        lo = max(0.0, lo)
    return float(lo), float(hi)


def quadrant_of(ret: float, vol: float, ret_split: float = 0.0, vol_split: float = 0.0) -> str:
    """ป้าย quadrant ของจุดหนึ่ง — **ฟังก์ชันกลาง** ใช้ทั้ง scatter หน้า 1/2 และ vol-return หน้า 5."""
    hi, pos = vol > vol_split, ret > ret_split
    if pos and hi:
        return Q1
    if not pos and hi:
        return Q2
    if not pos and not hi:
        return Q3
    return Q4


def add_quadrant(results: pd.DataFrame) -> tuple[pd.DataFrame, float]:
    """เพิ่มคอลัมน์ quadrant (สี) ตาม return>0 และ vol เทียบ median. คืน (df, median_vol)."""
    df = results.copy()
    med = df["ann_vol"].median()
    df["quadrant"] = [quadrant_of(r, v, 0.0, med) for r, v in zip(df["ann_return"], df["ann_vol"])]
    return df, med


def scatter(results: pd.DataFrame, scope: str, r2_label: str = "R²") -> go.Figure:
    """scatter: x=ann_return, y=ann_vol, ขนาดจุดคงที่ (AUM ยังดูได้ใน hover), สี=quadrant. scope='country'|'sector'|'style'.

    r2_label: ชื่อ R² ใน hover (หน้า 6 = "incremental R²" — คนละความหมายกับ R² หน้า 1/2)
    """
    df, med = add_quadrant(results)
    df["match"] = df[f"{scope}_primary"].map(lambda x: primary_label(x, scope))
    fig = px.scatter(
        df, x="ann_return", y="ann_vol", color="quadrant",
        color_discrete_map=QUADRANT_COLORS,
        hover_name="FundCode",
        hover_data={"FundName": True, "match": True,
                    f"{scope}_r2": ":.2f", "aum": ":,.0f",
                    "ann_return": ":.1%", "ann_vol": ":.1%",
                    "n_obs": True,          # จำนวนจุดข้อมูล — ช่วยประเมินความน่าเชื่อถือของ ann_return/vol
                    "quadrant": False},
        labels={"ann_return": "Annualized Return", "ann_vol": "Annualized Volatility",
                "match": f"{scope} primary", f"{scope}_r2": r2_label},
    )
    fig.update_traces(marker=dict(size=10, opacity=0.85, line=dict(width=0.5, color="rgba(0,0,0,0.3)")))
    fig.add_vline(x=0, line_dash="dash", line_color="gray", opacity=0.5)
    fig.add_hline(y=med, line_dash="dash", line_color="gray", opacity=0.5)

    # rescale แกน: ตัดที่ 1st-99th percentile ของกองที่กำลังแสดงอยู่ (เผื่อขอบ 8%)
    # กันกรณีมีกอง outlier ผันผวนสูงผิดปกติ (เช่น vol 60-70%+) มาดันสเกลจนกองส่วนใหญ่กระจุกกันแบนราบที่มุมกราฟ
    # จุด outlier ยังอยู่ใน data ครบ แค่อาจถูกตัดขอบมองไม่เห็นในมุมมองเริ่มต้น — ซูมออก/ลาก range เองได้ตามปกติ
    x_range = _percentile_range(df["ann_return"])
    y_range = _percentile_range(df["ann_vol"], floor_zero=True)
    if x_range:
        fig.update_xaxes(range=x_range)
    if y_range:
        fig.update_yaxes(range=y_range)

    fig.update_layout(xaxis_tickformat=".0%", yaxis_tickformat=".0%", legend_title_text="")
    return fig


def match_strength_bar(coefs: pd.DataFrame, fundcode: str, scope: str, model: str) -> go.Figure | None:
    """bar ต่อกอง: แกน y = coefficient ของ model ที่เลือก, สี primary/secondary/อื่นๆ.

    primary/secondary คำนวณจาก |coefficient| ของ **model ที่เลือก** เอง (ไม่ยึด ElasticNet)
    -> สี bar ตรงกับความสูงที่แสดงเสมอ ไม่ว่าจะดู elastic/lasso/ridge

    secondary ใช้นิยาม **band-based** (config.SECONDARY_BAND_PCT): ทุก index นอกจาก primary
    ที่ |coef| >= |primary| × (1 − band) -> กองที่มี exposure หลายตัวใกล้เคียงกันได้ secondary หลายตัว
    (นิยามเดิมเป็น rank-based ได้ตายตัวแค่ 1 ตัว ทำให้ตัวที่ 3-4 ที่แรงพอกันถูกจัดเป็น "อื่นๆ")
    คืน None ถ้าทุก coefficient ของ model นั้น = 0 -> caller โชว์ placeholder
    """
    sub = coefs[(coefs["FundCode"] == fundcode) & (coefs["scope"] == scope)].copy()
    sub = sub[sub[model].abs() > 1e-9]
    if sub.empty:
        return None
    sub = sub.reindex(sub[model].abs().sort_values(ascending=False).index)
    # ใช้ฟังก์ชันกลาง matching.classify_exposure() ตัวเดียวกับหน้า 5 -> threshold อยู่ที่เดียว
    primary, secondary = matching.classify_exposure(sub.set_index("index")[model])
    color = [PRIMARY_C if ix == primary else SECONDARY_C if ix in secondary else OTHER_C
             for ix in sub["index"]]

    band_txt = f"≥{1 - config.SECONDARY_BAND_PCT:.0%} ของ primary"   # ผูกกับ config ไม่ hardcode
    fig = go.Figure(go.Bar(
        x=[short(i, scope) for i in sub["index"]], y=sub[model], marker_color=color,
        hovertemplate="%{x}: %{y:.3f}<extra></extra>"))
    fig.update_layout(yaxis_title=f"{model} standardized coefficient", xaxis_title="",
                      title=f"{fundcode} — {scope} exposure "
                            f"(🔵 primary · 🟢 secondary ({band_txt}) · ⚪ อื่นๆ)")
    return fig


MACRO_METHOD_STYLE = {                       # method -> (ชื่อบน legend, สี)
    "implied": ("implied (ผ่าน country/sector)", "#1f77b4"),
    "direct": ("direct (regress NAV ตรง)", "#ff7f0e"),
}


def macro_factor_tick(factor: str, sd: float) -> str:
    """ชื่อ factor + ขนาด 1 SD รายเดือน (return -> %, Δ -> หน่วยของมันเอง)."""
    size = f"{sd:.1%}" if factor in config.MACRO_RETURN_COLS else f"{sd:.2f} {config.MACRO_DELTA_UNITS[factor]}"
    return f"{factor}<br>(1 SD = {size})"


def macro_bar(loadings: pd.DataFrame, fundcode: str, factor_sd: pd.Series,
              peer_median: pd.DataFrame | None = None) -> go.Figure:
    """หน้า 7: bar ต่อกอง — return รายเดือนของกองเมื่อ macro ขยับ 1 SD, implied คู่ direct, factor เรียงตาม config.

    ไม่เรียงตาม |ค่า| และไม่มีสี primary/secondary (ต่างจาก match_strength_bar): factor 7 ตัวตายตัว
    ตำแหน่งคงที่ช่วยเทียบข้ามกอง · peer_median (index=factor, columns=method) -> ◆ วางตรงแท่งของวิธีเดียวกัน
    """
    sub = loadings[loadings["FundCode"] == fundcode]
    x = [macro_factor_tick(f, factor_sd[f]) for f in config.MACRO_FACTOR_COLS]
    fig = go.Figure()
    for method, (label, color) in MACRO_METHOD_STYLE.items():
        s = sub[sub["method"] == method].set_index("factor").reindex(config.MACRO_FACTOR_COLS)
        fig.add_bar(x=x, y=s["impact_1sd"], name=label, marker_color=color, offsetgroup=method,
                    customdata=s["loading"],
                    hovertemplate=f"%{{x}}<br>{method}: %{{y:.2%}} ต่อ 1 SD (loading %{{customdata:.3f}})<extra></extra>")
        if peer_median is not None and method in peer_median:
            fig.add_scatter(x=x, y=peer_median[method].reindex(config.MACRO_FACTOR_COLS), mode="markers",
                            name=f"median กอง {config.MACRO_POLICY}", legendgroup="median",
                            showlegend=method == "implied", offsetgroup=method,
                            marker=dict(symbol="diamond", size=10, color="#333", line=dict(width=1, color="white")),
                            hovertemplate=f"%{{x}}<br>median กอง {config.MACRO_POLICY} ({method}): "
                                          "%{y:.2%}<extra></extra>")
    fig.add_hline(y=0, line_color="gray", opacity=0.5)
    fig.update_layout(barmode="group", scattermode="group", yaxis_tickformat=".1%",
                      yaxis_title="return กองต่อ macro ขยับ 1 SD (รายเดือน)", xaxis_title="",
                      legend=dict(orientation="h", y=1.12), margin=dict(t=40, b=10), height=440)
    return fig


def score_heatmap(matrix: pd.DataFrame) -> go.Figure:
    """หน้า 8: heatmap คะแนนโซน country × sector (ยิ่งเข้ม = ทั้งประเทศและ sector อยู่โซนดีพร้อมกัน)."""
    z = matrix.to_numpy()
    fig = px.imshow(
        z, x=[config.SECTOR_FULL_NAMES.get(c, c) for c in matrix.columns],
        y=[short(i, "country") for i in matrix.index],
        color_continuous_scale="Blues", aspect="auto", text_auto=".1f",
        labels={"x": "sector", "y": "country", "color": "score"},
    )
    fig.update_xaxes(side="top", tickangle=-35)
    fig.update_traces(hovertemplate="%{y} × %{x}<br>score %{z:.2f}<extra></extra>")
    fig.update_layout(margin=dict(t=90, b=10), height=max(360, 26 * len(matrix)), coloraxis_showscale=False)
    return fig


def _ref_point(fig: go.Figure, point: pd.Series, name: str, color: str, symbol: str) -> None:
    """จุดอ้างอิงบนกราฟ frontier — ต้องเป็น Scattergl เหมือนกลุ่มเมฆ ไม่งั้นโดน canvas ของ WebGL วาดทับจนมองไม่เห็น."""
    fig.add_trace(go.Scattergl(
        x=[point["risk"]], y=[point["ret"]], mode="markers+text", name=name,
        text=[name], textposition="bottom center", textfont=dict(size=11, color=color),
        marker=dict(size=18, color=color, symbol=symbol, line=dict(width=1.5, color="white")),
        hovertemplate=f"{name}<br>risk %{{x:.1%}}<br>return %{{y:.1%}}<extra></extra>"))


def frontier_chart(cloud: pd.DataFrame, frontier: pd.DataFrame, singles: pd.DataFrame | None,
                   equal_weight: pd.Series | None = None,
                   max_sharpe: pd.Series | None = None,
                   extra_points: list[tuple[str, pd.Series, str, str]] | None = None,
                   axis_titles: tuple[str, str] | None = None) -> go.Figure:
    """หน้า 8 ส่วนที่ 3 (และหน้า 10): เมฆของทุกพอร์ตที่เป็นไปได้ + เส้น efficient frontier + จุดอ้างอิง.

    cloud/frontier : DataFrame[risk, ret] · singles : DataFrame[risk, ret] index=FundCode (ถือกองเดียว 100%)
    extra_points   : จุดอ้างอิงเพิ่ม [(ชื่อ, Series[risk, ret], สี, symbol)] (หน้า 10: MVP / ERC)
    axis_titles    : (แกน x, แกน y) — None = ชื่อแกนของหน้า 8 (Σ / Π)
    ทุก trace ใช้ Scattergl (WebGL) — จุดเป็นแสน SVG วาดไม่ไหว และถ้าผสม SVG กับ WebGL
    จุดอ้างอิงที่อยู่ "ในกลุ่มเมฆ" จะถูก canvas ทับหายไป (เจอกับ equal weight มาแล้ว)
    กลุ่มเมฆสุ่มแสดงไม่เกิน PORTFOLIO_CLOUD_MAX_POINTS (seed คงที่) — frontier วาดครบทุกจุดเสมอ
    """
    n_all = len(cloud)
    if n_all > config.PORTFOLIO_CLOUD_MAX_POINTS:
        cloud = cloud.sample(config.PORTFOLIO_CLOUD_MAX_POINTS, random_state=0)
    shown = "" if len(cloud) == n_all else f" · แสดงสุ่ม {len(cloud):,}"
    fig = go.Figure()
    fig.add_trace(go.Scattergl(
        x=cloud["risk"], y=cloud["ret"], mode="markers", name=f"พอร์ตที่เป็นไปได้ ({n_all:,}{shown})",
        marker=dict(size=3, color="#c9d6e3", opacity=0.30),
        hovertemplate="risk %{x:.1%}<br>return %{y:.1%}<extra></extra>"))
    fig.add_trace(go.Scattergl(
        x=frontier["risk"], y=frontier["ret"], mode="markers", name=f"efficient frontier ({len(frontier):,})",
        marker=dict(size=5, color="#1f77b4"),
        hovertemplate="frontier<br>risk %{x:.1%}<br>return %{y:.1%}<extra></extra>"))
    if singles is not None:   # None = ไม่แสดง (หน้า 10: ถือกองเดียว 100% อยู่นอกกรอบเพดาน/สัดส่วนหุ้นที่ล็อก)
        fig.add_trace(go.Scattergl(
            x=singles["risk"], y=singles["ret"], mode="markers+text", name="ถือกองเดียว 100%",
            text=[str(i) for i in singles.index], textposition="top center", textfont=dict(size=9),
            marker=dict(size=10, color="#d62728", symbol="diamond", line=dict(width=1, color="white")),
            hovertemplate="%{text}<br>risk %{x:.1%}<br>return %{y:.1%}<extra></extra>"))
    if max_sharpe is not None:
        _ref_point(fig, max_sharpe, "max Sharpe", "#ff7f0e", "star")
    if equal_weight is not None:
        _ref_point(fig, equal_weight, "equal weight", "#2ca02c", "star")
    for name, point, color, symbol in extra_points or []:
        _ref_point(fig, point, name, color, symbol)
    x_title, y_title = axis_titles or ("ความเสี่ยง — annualized volatility ของพอร์ต (จาก Σ)",
                                       "ผลตอบแทนคาดหวัง — Black-Litterman implied (Π)")
    fig.update_layout(xaxis_title=x_title, yaxis_title=y_title,
                      xaxis_tickformat=".1%", yaxis_tickformat=".1%",
                      legend=dict(orientation="h", y=1.12), margin=dict(t=40, b=10), height=480)
    return fig


def weights_compare_bar(weights: pd.DataFrame, colors: dict[str, str] | None = None) -> go.Figure:
    """แท่งน้ำหนักแนวนอนของหลายพอร์ตคู่กัน (index = กอง · columns = ชื่อพอร์ต) — หน้า 10: max Sharpe vs ERC."""
    fig = go.Figure()
    for name in weights.columns:
        fig.add_bar(y=list(weights.index), x=weights[name], name=name, orientation="h",
                    marker_color=(colors or {}).get(name), text=["" if pd.isna(v) else f"{v:.1%}" for v in weights[name]],
                    textposition="outside", cliponaxis=False,
                    hovertemplate="%{y}: %{x:.1%}<extra>" + name + "</extra>")
    top = float(np.nanmax(weights.to_numpy())) if weights.notna().any().any() else 0.0
    fig.update_layout(barmode="group", height=60 + 44 * len(weights), margin=dict(l=10, r=10, t=10, b=10),
                      xaxis=dict(tickformat=".0%", range=[0, max(top, 1e-9) * 1.3]),   # เผื่อที่ให้ป้ายท้ายแท่ง
                      yaxis=dict(autorange="reversed"), legend=dict(orientation="h", y=1.08))
    return fig


def vol_return_scatter(df: pd.DataFrame, scope: str) -> go.Figure:
    """หน้า 5: scatter ระดับ index — x=return 21 วันล่าสุด (ค่าจริง), y=**percentile rank ของ forecast vol**.

    ทำไมใช้ percentile rank แทนค่าจริงตรงๆ: กลุ่ม index (18 country / 10 sector) มักมี 1-2 ตัวที่ forecast
    vol พุ่งสูงผิดปกติ (เช่น MSCI_KOREA ~120%) เทียบกับตัวอื่นที่กระจุกกัน 12-40% ลอง linear แล้วจุดอื่นแบน
    ลอง log แล้ว tick หนาแน่นอ่านยาก (ยืนยันกับผู้ใช้ 2026-09-09) -> ใช้ rank(pct=True) แทน
    ข้อดี: จุดกระจายเท่าๆกันเสมอไม่ว่าค่าจริงจะห่างกันแค่ไหน (ทนต่อ outlier โดยธรรมชาติ)
    ข้อเสีย: แกน y ไม่ใช่ค่า vol จริงตรงๆ -> โชว์ค่าจริงผ่าน hover เสมอ
    median ของ vol จริง = นิยาม rank 50% พอดี -> เส้นแบ่งอยู่ที่ y=0.5 ตายตัวทุกกราฟ (ไม่ต้องคำนวณใหม่)

    สี = 4 quadrant เดียวกับหน้า 1/2 (คำนวณจาก **ค่าจริง** ผ่าน quadrant_of ไม่ใช่จาก rank — สียังสะท้อน
    ค่าจริงถูกต้อง แค่ตำแหน่งบนแกนที่เปลี่ยนไปเป็น rank)
    customdata = (ชื่อ index เต็ม, vol_forecast ค่าจริง) -> รู้ว่าคลิกจุดไหน + โชว์ค่าจริงใน hover
    """
    vol_med = df["vol_forecast"].median()
    vol_rank = df["vol_forecast"].rank(pct=True)   # 0-1 กระจายเท่าๆกันเสมอ ไม่ขึ้นกับสเกลค่าจริง (แก้ปัญหา outlier)
    quads = [quadrant_of(r, v, 0.0, vol_med) for r, v in zip(df["return_21d"], df["vol_forecast"])]
    fig = go.Figure(go.Scatter(
        x=df["return_21d"], y=vol_rank, mode="markers",
        marker=dict(color=[QUADRANT_COLORS[q] for q in quads], size=13,
                    line=dict(width=0.5, color="rgba(0,0,0,0.35)")),
        customdata=list(zip(df["index"], df["vol_forecast"])),
        # sector โชว์ชื่อเต็ม (config.SECTOR_FULL_NAMES เหมือนหน้า 8) — country ยังคงชื่อสั้นเหมือนเดิม
        text=[config.SECTOR_FULL_NAMES.get(i, i) if scope == "sector" else short(i, scope)
              for i in df["index"]],
        hovertemplate="<b>%{text}</b><br>return 21d: %{x:.1%}"
                      "<br>forecast vol: %{customdata[1]:.1%} (percentile rank %{y:.0%})<extra></extra>",
    ))
    fig.add_vline(x=0, line_dash="dash", line_color="gray", opacity=0.5)
    fig.add_hline(y=0.5, line_dash="dash", line_color="gray", opacity=0.5)
    fig.update_yaxes(range=[-0.05, 1.05], tickformat=".0%")
    fig.update_layout(xaxis_title="return 21 วันล่าสุด",
                      yaxis_title="forecast vol — percentile rank (ค่าจริงดูที่ hover)",
                      xaxis_tickformat=".0%",
                      margin=dict(t=30, b=10), height=420)
    return fig


# --- TF Portfolio (หน้า 9) ---
TF_SERIES_COLORS = {config.TF_MODEL_ID: "#1f77b4", "M001": "#ff7f0e", "B0": "#7f7f7f",
                    "GC75_MMF": "#2ca02c", "TREND25": "#1f77b4", "M012_QFS": "#9467bd", "M019": "#d62728"}
TF_SERIES_LABELS = {config.TF_MODEL_ID: f"{config.TF_MODEL_ID} (หน้านี้)", "M001": "M001 (หน้า 8)",
                    "B0": "B0 ถือทุกกองเท่ากัน",
                    "GC75_MMF": "① GC75 + กองตลาดเงิน ⚠️", "TREND25": "② Trend 25 (M004-TF-FX · หน้านี้)",
                    "M012_QFS": "③ M012-QF-S (Trend 25 + เกณฑ์คุณภาพ)",
                    "M019": "★ M019 (หุ้น 3 กอง + ทอง) ⚠️"}
TF_SERIES_BOLD = {config.TF_MODEL_ID, "GC75_MMF", "TREND25", "M012_QFS", "M019"}   # เส้นหลัก (หนา) · อื่น = เส้นอ้างอิง


def tf_equity_chart(curves: pd.DataFrame, case: str) -> go.Figure:
    """มูลค่าพอร์ต (เริ่ม 100 ณ วันซื้อแรก) ของแต่ละ series ในกรณีต้นทุนที่เลือก."""
    fig = go.Figure()
    for series, g in curves[curves["case"] == case].groupby("series", sort=False):
        fig.add_trace(go.Scatter(x=g["date"], y=g["value"], name=TF_SERIES_LABELS.get(series, series), mode="lines",
                                 line=dict(color=TF_SERIES_COLORS.get(series), width=2.6 if series in TF_SERIES_BOLD else 1.6,
                                           dash="dot" if series == "B0" else None),
                                 hovertemplate="%{x|%Y-%m}: %{y:.1f}<extra>" + series + "</extra>"))
    fig.update_layout(height=380, margin=dict(l=10, r=10, t=10, b=10), yaxis_title="มูลค่าพอร์ต (เริ่ม 100)",
                      legend=dict(orientation="h", y=1.08), hovermode="x unified")
    return fig


def tf_drawdown_chart(curves: pd.DataFrame, case: str) -> go.Figure:
    """drawdown จากจุดสูงสุดก่อนหน้า (%)."""
    fig = go.Figure()
    for series, g in curves[curves["case"] == case].groupby("series", sort=False):
        dd = g["value"] / g["value"].cummax() - 1
        fig.add_trace(go.Scatter(x=g["date"], y=dd, name=TF_SERIES_LABELS.get(series, series), mode="lines",
                                 line=dict(color=TF_SERIES_COLORS.get(series), width=2 if series in TF_SERIES_BOLD else 1.2),
                                 fill="tozeroy" if series == config.TF_MODEL_ID else None,
                                 hovertemplate="%{x|%Y-%m}: %{y:.1%}<extra>" + series + "</extra>"))
    fig.update_layout(height=260, margin=dict(l=10, r=10, t=10, b=10), yaxis_tickformat=".0%",
                      showlegend=False, hovermode="x unified")
    return fig


def tf_weights_bar(weights: dict) -> go.Figure:
    """น้ำหนักพอร์ตแนะนำ (เงินสดเป็นแท่งสีเทา)."""
    items = sorted(weights.items(), key=lambda kv: (kv[0] == "__CASH__", -kv[1]))
    names = ["เงินสด" if k == "__CASH__" else k for k, _ in items]
    fig = go.Figure(go.Bar(x=[v for _, v in items], y=names, orientation="h",
                           marker_color=[OTHER_C if k == "__CASH__" else TF_SERIES_COLORS[config.TF_MODEL_ID] for k, _ in items],
                           text=[f"{v:.1%}" for _, v in items], textposition="outside",
                           hovertemplate="%{y}: %{x:.1%}<extra></extra>"))
    fig.update_layout(height=40 + 32 * len(items), margin=dict(l=10, r=40, t=10, b=10),
                      xaxis_tickformat=".0%", yaxis=dict(autorange="reversed"))
    return fig
