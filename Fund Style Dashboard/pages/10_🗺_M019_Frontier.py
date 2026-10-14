"""M019 Frontier (หน้า 10) — efficient frontier ของกองที่ M019-LC3-GCGOLD ถือจริง 4 ไตรมาส (สุ่มคงที่).

หุ้น 3 กอง กองละ 0–40% ของส่วนหุ้น (ขาทอง/ตลาดเงินล็อกตามกติกาโมเดล) · เทียบ max Sharpe กับ ERC ของโมเดล
คำนวณ: analysis/gc75_frontier.py · input: base_data/reference/gc75_frontier_*.csv (ทีม quant) · เอกสาร: docs/pages/10-gc75-frontier.md
"""

import json

import pandas as pd
import streamlit as st

import config
import data_access
import page_common
import viz
from analysis import gc75_frontier as gf

st.set_page_config(page_title="M019 Frontier", page_icon="🗺", layout="wide")
st.title("🗺 M019 Frontier")
st.caption(f"efficient frontier ของกองที่ **M019** (หุ้น 3 กอง + ขาทอง ตาม GC75) ถือจริง ณ สิ้นไตรมาส (backtest เม.ย. 2022 – ธ.ค. 2025) · "
           f"ขาทอง/ตลาดเงิน**ล็อก**ตามน้ำหนักจริงของไตรมาส · กองหุ้นแต่ละกอง {0:.0%}–{config.GC75_FRONTIER_MAX_W:.0%} ของส่วนหุ้น "
           f"ทีละ {config.GC75_FRONTIER_STEP:.0%} (= เพดาน ERC ของ M019) · {config.GC75_FRONTIER_N_QUARTERS} ไตรมาสสุ่มแบบคงที่")
st.warning("**ไม่ใช่คำแนะนำการลงทุน** · μ และ Σ มาจาก weekly return 52 สัปดาห์**ก่อน**วันตัดสินใจ (สิ่งที่เห็นได้ ณ วันนั้น) "
           "ไม่ใช่ผลที่เกิดหลังซื้อ · ค่าเฉลี่ยผลตอบแทน 1 ปีคลาดเคลื่อนสูงมาก → max Sharpe ไวต่อ μ และมักไปชนเพดาน")

try:
    data = data_access.get_gc75_frontier()
except Exception as e:  # noqa: BLE001
    st.error(f"โหลดไฟล์ input ไม่สำเร็จ: {type(e).__name__}: {e}\n\n"
             "สร้างด้วย `PYTHONPATH=. ./.venv/bin/python .claude/quant_team/backtest/export_gc75_frontier.py`")
    st.stop()
holdings, weekly, realized = data["holdings"], data["weekly"], data.get("realized")

AXES = ("ความเสี่ยง (vol ต่อปี)", "ผลตอบแทนคาดหวัง (ต่อปี)")
# legend ใต้กราฟ (เฉพาะหน้านี้ · ค่าเริ่มต้นหน้า 8 ไม่เปลี่ยน) · แกน x ทศนิยม 2 ตำแหน่ง: กรอบ 0–40% × 3 กอง ทำให้ช่วงความเสี่ยงแคบ
LAYOUT = dict(height=560, legend=dict(orientation="h", y=-0.15, x=0, yanchor="top"), margin=dict(t=10, b=10),
              xaxis_tickformat=".2%")
MS, ERC = "max Sharpe", "ERC (กติกาโมเดล)"                                  # ชื่อคอลัมน์จาก gf.frontier_case / ไฟล์ผลจริง
LABEL = {"MVP": "MVP", MS: "Max Sharpe", ERC: "Model Portfolio"}             # ชื่อที่แสดง (Model Portfolio = M019 ถือจริง)
POINTS = (("MVP", "mvp", "#2ca02c", "diamond"), (LABEL[ERC], "erc", "#9467bd", "square"))
COMPARE_COLORS = {LABEL[MS]: "#ff7f0e", LABEL[ERC]: "#9467bd"}
pct = st.column_config.NumberColumn(format="percent")
SHARPE_MIN_RISK = 0.005   # แสดงผลเท่านั้น: พอร์ต vol ต่ำมาก → (ret − rf)/σ ระดับ −100 ที่ไม่มีความหมาย


def defensive_text(h_t):
    d = h_t[h_t["kind"] != "E"]
    if len(d) == 0:
        return "ไม่มีขาตั้งรับ (หุ้น 100%)"
    r = d.iloc[0]
    return f"{gf.KIND_LABEL[r['kind']]} {r['FundCode']} {r['weight']:.0%} (ล็อกในทุกพอร์ต)"


def _p(x):
    return "-" if x is None or pd.isna(x) else f"{x:.2%}"


def _s(x):
    return "-" if x is None or pd.isna(x) else f"{x:.2f}"


def compare_table(t, res):
    """ตารางเดียวต่อไตรมาส: คาดหวัง ณ วันตัดสินใจ + จริงช่วงไตรมาสที่ถือ (Q1) + จริง 1 ปี (Y1 · ยังไม่ครบปี = "-")."""
    names = list(res["weights"].columns)
    s = res["summary"]
    r = realized[realized["t"] == t] if realized is not None else pd.DataFrame(columns=["portfolio", "horizon"])
    stale = []
    rows = []
    for n in names:
        row = {"Exp vol": _p(s.loc[n, "risk"]), "Exp return": _p(s.loc[n, "ret"]),
               "Exp Sharpe": _s(s.loc[n, "sharpe"] if s.loc[n, "risk"] >= SHARPE_MIN_RISK else None)}
        for hz, tag in (("Q", "Q1"), ("1Y", "Y1")):
            x = r[(r["portfolio"] == n) & (r["horizon"] == hz)]
            ok = len(x) == 1 and not (hz == "1Y" and bool(x["truncated"].iloc[0]))     # 1 ปียังไม่ครบ → "-"
            if len(x) == 1 and max(abs(json.loads(x["weights"].iloc[0]).get(f, 0.0) - float(w))
                                   for f, w in res["weights"][n].items()) > 1e-9:
                stale.append(n)
            row[f"T_vol_{tag}"] = _p(x["vol_ann"].iloc[0]) if ok else "-"
            row[f"T_return_{tag}"] = _p(x["ret_ann"].iloc[0]) if ok else "-"
            row[f"T_sharpe_{tag}"] = _s(x["sharpe"].iloc[0]) if ok else "-"
        rows.append(pd.Series(row, name=LABEL[n]))
    if realized is None:
        st.info("ยังไม่มีไฟล์ผลจริง — รัน `export_gc75_frontier.py`")
    elif stale:                                                  # กริด/ค่าคงที่เปลี่ยนหลัง export → น้ำหนักไม่ตรงกราฟ
        st.warning("น้ำหนักในไฟล์ผลจริงไม่ตรงกับกราฟ (ไฟล์เก่ากว่าค่าตั้งของหน้านี้): " + ", ".join(sorted(set(stale)))
                   + " — รัน `export_gc75_frontier.py` ใหม่")
    st.dataframe(pd.DataFrame(rows), **page_common.TABLE_WIDTH)
    q = r[r["horizon"] == "Q"]
    y = r[r["horizon"] == "1Y"]
    if len(q):
        cap = (f"`Exp` = จาก weekly return 52 สัปดาห์ก่อนวันตัดสินใจ (ต่อปี) · `T_*_Q1` = ถือจริง {q['e'].iloc[0]:%Y-%m-%d} → "
               f"{q['end'].iloc[0]:%Y-%m-%d} ({int(q['days'].iloc[0])} วัน) · `T_*_Y1` = ถือจริง 1 ปี")
        cap += (" (ยังไม่ครบปี — ข้อมูลถึง " + f"{y['end'].iloc[0]:%Y-%m-%d})" if len(y) and bool(y["truncated"].iloc[0]) else "")
        cap += (" · ผลตอบแทนจริง/ปี = ช่วงถือ × 365/วัน หลังหักค่าธรรมเนียมจริงของการสลับจากพอร์ต M019 ไตรมาสก่อน · "
                f"vol จริงจาก NAV รายวัน · Sharpe จริงใช้ rf จริงของช่วงถือ ({q['rf_ann'].iloc[0]:.2%}/ปี ช่วงไตรมาส)")
        st.caption(cap)


for t in gf.pick_quarters(holdings["t"]):
    h_t = holdings[holdings["t"] == t]
    w_t = weekly[weekly["t"] == t]
    eq_share = h_t.loc[h_t["kind"] == "E", "weight"].sum()
    st.subheader(f"ไตรมาส {t:%Y-%m-%d} (ซื้อขาย {h_t['e'].iloc[0]:%Y-%m-%d})")
    st.caption(f"GC75 ถือหุ้น {eq_share:.0%} · {defensive_text(h_t)} · rf (ดอกเบี้ยนโยบาย ธปท.) {h_t['rf'].iloc[0]:.2%}")
    try:
        res = gf.frontier_case(h_t, w_t)
    except ValueError as e:
        st.error(str(e))
        continue
    fig = viz.frontier_chart(
        res["points"], res["frontier"], None, max_sharpe=res["max_sharpe"],
        extra_points=[(name, res[key], color, sym) for name, key, color, sym in POINTS], axis_titles=AXES)
    fig.update_layout(**LAYOUT)
    st.plotly_chart(fig, **page_common.CHART_WIDTH, key=f"ef_{t:%Y%m%d}")
    st.caption(f"{len(res['points']):,} พอร์ต · frontier {len(res['frontier']):,} จุด · {res['n_weeks']} สัปดาห์ร่วม · "
               f"max Sharpe คิดที่ rf {res['rf']:.2%}")

    compare_table(t, res)

    st.markdown("**กองที่ถือ** — น้ำหนักในพอร์ตรวม")
    eq_codes = list(res["funds"].loc[res["funds"]["kind"] == "E", "FundCode"])
    bars = res["weights"].loc[eq_codes, [MS, ERC]].rename(columns=LABEL)
    st.plotly_chart(viz.weights_compare_bar(bars, COMPARE_COLORS), **page_common.CHART_WIDTH, key=f"cmp_{t:%Y%m%d}")
    w = res["weights"].rename(columns=LABEL)
    info = res["funds"].set_index("FundCode")
    w.insert(0, "SR12′", info["sr12p"])
    w.insert(0, "ชนิด", info["kind"].map(gf.KIND_LABEL))
    st.dataframe(w, **page_common.TABLE_WIDTH,
                 column_config={"SR12′": st.column_config.NumberColumn(format="%.2f"),
                                **{LABEL[c]: pct for c in res["weights"].columns}})
    st.caption(f"ส่วนหุ้น {eq_share:.0%} · ที่เหลือคือขาตั้งรับที่ล็อกไว้ · เพดาน {config.GC75_FRONTIER_MAX_W:.0%} ของส่วนหุ้น "
               f"= {config.GC75_FRONTIER_MAX_W * eq_share:.0%} ของพอร์ตรวม")
    st.divider()

with st.expander("ℹ️ อ่านหน้านี้ยังไง"):
    st.markdown(
        f"""
- **โมเดล M019** — ทุกสิ้นไตรมาส: กองหุ้น 3 กอง = อันดับ 1 ตาม SR12′ (หลังเกณฑ์คุณภาพ) แล้วเติมกองที่ correlation (ρ_adj แบบ lead-lag)
  สูงสุดกับกองที่เลือกแล้ว**ต่ำสุด** จากอันดับ ≤ 9 · ถือต่อถ้ายังอยู่ในอันดับ ≤ 9 · น้ำหนักในส่วนหุ้น = ERC เพดาน 40%
- **สัดส่วนหุ้น (GC75)** 100/75/50/25% ตามผลตอบแทน ACWI 3/6/12 เดือนเทียบดอกเบี้ย · ส่วนที่เหลือ = **กองทองที่ AUM ใหญ่สุด**
  (ไม่มีกองทองผ่านเกณฑ์ → กองตลาดเงิน) · ไตรมาสที่หุ้น 100% ไม่มีขาตั้งรับ
- **กรอบน้ำหนัก** — ขาตั้งรับ**ล็อก**ตามน้ำหนักจริงของไตรมาส · หุ้น 3 กองจัดใหม่ได้กองละ 0–{config.GC75_FRONTIER_MAX_W:.0%}
  ของส่วนหุ้น ทีละ {config.GC75_FRONTIER_STEP:.0%} (เพดาน ERC ของโมเดลก็ 40%) → มีพอร์ตให้เลือก {len(gf.portfolio.composition_grid(3, config.GC75_FRONTIER_STEP, config.GC75_FRONTIER_MAX_W)):,} ชุด ทุกชุดมีสัดส่วนหุ้น/ทองเท่ากับที่ M019 ถือ
- **จุดน้ำเงิน** = frontier · **ดาวส้ม max Sharpe** = (μ − rf) ÷ σ สูงสุดบน frontier · **เพชรเขียว MVP** = ความเสี่ยงต่ำสุด
  · **สี่เหลี่ยมม่วง Model Portfolio** = พอร์ตที่ M019 ถือจริง (ERC ส่วนหุ้น เพดาน 40% × สัดส่วนหุ้น + ขาตั้งรับ)
- **μ / Σ** = weekly return 52 สัปดาห์ ≤ วันตัดสินใจ (จุดสัปดาห์ชุดเดียวกับที่ ERC ใช้) · ไม่ใช่ผลหลังซื้อ
  · Σ ของกองหุ้น = Ledoit-Wolf เป้า constant correlation **เฉพาะกองหุ้น** · ขาตั้งรับใช้ variance/covariance จริง
- **ตาราง**: `Exp` = ค่าคาดหวัง ณ วันตัดสินใจ · `T_*_Q1` = ผลจริงช่วงไตรมาสที่ถือ · `T_*_Y1` = ผลจริง 1 ปี ("-" = ยังไม่ครบปี)
  · ผลจริงถือแบบไม่ rebalance และหักค่าธรรมเนียมจริงของการสลับจากพอร์ต M019 ไตรมาสก่อน
- ERC ไม่ได้ใช้ μ เลย จึงไม่ควรอยู่บน frontier ที่สร้างจาก μ ย้อนหลัง — ระยะห่างคือ "ส่วนที่ ERC ไม่เชื่อ μ ย้อนหลัง" ไม่ใช่ความผิดพลาด
"""
    )
