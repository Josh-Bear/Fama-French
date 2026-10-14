"""TF Portfolio (หน้า 9) — โมเดล M004-TF-FX ที่ผ่าน walk-forward backtest: พอร์ตแนะนำ ณ วันที่เลือก + ผลย้อนหลัง.

โมเดล: analysis/tf_model.py · cache: data_access.build_tf_cache (CLI `data_access.py tf`) · เอกสาร: docs/pages/9-tf-portfolio.md
"""

import os

import pandas as pd
import streamlit as st

import config
import data_access
import page_common
import viz
from analysis import gc75_frontier as gf
from analysis import fund_backtest, tf_model

st.set_page_config(page_title="TF Portfolio", page_icon="📈", layout="wide")
TH_MONTHS = "ม.ค. ก.พ. มี.ค. เม.ย. พ.ค. มิ.ย. ก.ค. ส.ค. ก.ย. ต.ค. พ.ย. ธ.ค.".split()


def th_month(d) -> str:
    d = pd.Timestamp(d)
    return f"{TH_MONTHS[d.month - 1]} {d.year}"
st.title("📈 TF Portfolio")
st.caption(f"โมเดล **{config.TF_MODEL_ID}**: ทุกสิ้นไตรมาสคัด {config.TF_N_FUNDS} กองหุ้นที่ **Sharpe ย้อนหลัง 11 เดือน (SR12)** สูงสุด "
           f"(1 class ต่อกอง · กองที่ถืออยู่ถือต่อได้ถ้ายังติดอันดับ ≤ {config.TF_HYSTERESIS_K}) · ให้น้ำหนักแบบ ERC "
           f"(ทุกกองมีส่วนในความเสี่ยงเท่ากัน · เพดาน {config.TF_WEIGHT_CAP:.0%}) · ถือเงินสด {config.TF_TREND_CASH:.0%} "
           f"เมื่อ MSCI ACWI ต่ำกว่าเส้นเฉลี่ย {config.TF_TREND_SMA} วัน")

try:
    cache = data_access.get_tf_cache()
except Exception as e:  # noqa: BLE001
    st.error(f"โหลด cache ของหน้านี้ไม่สำเร็จ: {type(e).__name__}: {e}\n\n"
             "รัน `./.venv/bin/python data_access.py tf` หรือกด 🔄 Rebuild ที่หน้าแรก")
    st.stop()
for msg in cache["stale"]:
    st.warning(f"cache อาจไม่ตรงข้อมูลปัจจุบัน: {msg} — รัน `./.venv/bin/python data_access.py tf` หรือกด 🔄 Rebuild")

try:
    top3 = data_access.get_tf_top3()
except Exception as e:  # noqa: BLE001
    st.error(f"โหลดไฟล์ผล backtest TOP3 ไม่สำเร็จ: {type(e).__name__}: {e}\n\n"
             f"ต้องมี `{os.path.relpath(config.TF_TOP3_CURVES_CSV, config.BASE_DIR)}` และ "
             f"`{os.path.relpath(config.TF_TOP3_METRICS_CSV, config.BASE_DIR)}`")
    st.stop()
metrics = top3["metrics"].set_index(["series", "case"])
full = metrics.loc[("TREND25", "full")]
st.warning(
    f"**ไม่ใช่คำแนะนำการลงทุน** · backtest walk-forward เม.ย. 2022 – {th_month(config.TF_EVAL_END)} ได้ Sharpe "
    f"{full['sharpe']:.2f} (ค่าธรรมเนียมจริง · rf จริง) แต่**ยังพิสูจน์ทางสถิติไม่ได้**: CI95% [{full['ci_lo']:.2f}, {full['ci_hi']:.2f}] คร่อม 0 · "
    f"deflated Sharpe {full['dsr']:.2f} หลังลอง {config.TF_TOP3_N_TRIALS} แบบบนข้อมูลชุดเดียวกัน · ไม่มีข้อมูลทดสอบนอกช่วง "
    "(NAV ม.ค.–มิ.ย. 2026 ขาดหลายร้อยกอง) · พอร์ตมักกระจุกในธีมเดียว (บางไตรมาสเกินครึ่งพอร์ต)")

# ---------- ส่วนที่ 1 — พอร์ตแนะนำ ----------
st.subheader("1 · พอร์ตแนะนำ ณ วันที่เลือก")
quarters = cache["quarters"]
cov_ref = cache["meta"]["coverage_ref"]
options = data_access.tf_asof_options(cache)
ok_q = quarters[(~quarters["skipped"]) & (quarters["t"] >= pd.Timestamp(config.TF_COVERAGE_REF))]
default = ok_q["t"].max() if len(ok_q) else options[-1]
q_by_t = quarters.set_index("t")


def _label(t: pd.Timestamp) -> str:
    if t in q_by_t.index:
        row = q_by_t.loc[t]
        tag = " · ข้าม (กองสดน้อย)" if row["skipped"] else ""
        return f"{t:%Y-%m-%d} · กองสด {int(row['n_fresh'])} ({row['coverage']:.0%}){tag}"
    return f"{t:%Y-%m-%d} · ข้อมูลล่าสุด (ไม่ใช่สิ้นไตรมาส)"


as_of = st.selectbox("คำนวณ ณ วันที่", options, index=options.index(default), format_func=_label,
                     help=f"กองสด = NAV ล่าสุดห่างจากวันนั้นไม่เกิน {config.TF_FRESH_DAYS} วัน · % เทียบกับ "
                          f"{pd.Timestamp(config.TF_COVERAGE_REF):%Y-%m-%d} ({cov_ref} กอง) · สถานะถือครองมาจากการไล่ "
                          f"rebalance ทุกไตรมาสตั้งแต่ {config.TF_START_Q} (ข้ามไตรมาสที่กองสด < {config.TF_COVERAGE_MIN:.0%})")
with st.spinner("คำนวณสัญญาณ ณ วันที่เลือก…"):
    live = data_access.get_tf_live(str(as_of.date()))

if live["coverage"] < config.TF_COVERAGE_MIN:
    st.error(f"**ข้อมูล NAV ณ วันนี้บางมาก** — มีกองสดแค่ {live['n_fresh']} กอง ({live['coverage']:.0%} ของ {cov_ref} กอง ณ "
             f"{th_month(config.TF_COVERAGE_REF)}) พอร์ตด้านล่างเลือกจากกองน้อยกว่าที่ backtest ทดสอบไว้ราว "
             f"{1 / max(live['coverage'], 1e-9):.1f} เท่า ใช้ประกอบการพิจารณาเท่านั้น")

trend = live["trend"]
c1, c2, c3, c4 = st.columns(4)
c1.metric("ACWI vs SMA200", "ต่ำกว่า ⚠️" if trend["below"] else "เหนือ ✅",
          f"{trend['level'] / trend['sma'] - 1:+.1%}" if trend["sma"] == trend["sma"] else None)
c2.metric("เงินสด", f"{trend['cash']:.0%}")
c3.metric("กองสด / universe", f"{live['n_fresh']}/{live['counts']['n_universe']}")
c4.metric("คัดได้ (I_t)", f"{live['counts']['n_investable']}")
if live["fallback"]:
    st.warning(f"คัดกองได้น้อยกว่า {config.TF_MIN_FUNDS} กอง — ใช้แบบ B0 (ถือทุกกองเท่ากัน) ตามกติกาโมเดล")
elif live["weight_source"] != "ledoit_wolf":
    st.info("ข้อมูลรายสัปดาห์ร่วมกันไม่พอสำหรับ covariance — น้ำหนักใช้ inverse-vol แทน ERC")

left, right = st.columns([2, 3])
left.plotly_chart(viz.tf_weights_bar(live["weights"]), **page_common.CHART_WIDTH)
fam_of = {fc: fam for fam, fc in live["selected"].items()}
table = live["table"]
picked = table[table["FundCode"].isin(fam_of)].copy() if len(table) else table
if len(picked):
    picked["น้ำหนัก"] = picked["FundCode"].map(live["weights"])
    picked["สถานะ"] = picked["family"].map(lambda f: "ถือต่อ" if f in live["kept"] else "เพิ่มใหม่")
    right.dataframe(
        picked[["rank", "FundCode", "family", "น้ำหนัก", "SR12", "R12_1", "vol52", "สถานะ"]],
        hide_index=True, **page_common.TABLE_WIDTH,
        column_config={"rank": st.column_config.NumberColumn("อันดับ"),
                       "น้ำหนัก": st.column_config.NumberColumn(format="percent"),
                       "SR12": st.column_config.NumberColumn("SR12", format="%.2f",
                                                             help="(R12-1 − rf×11/12) ÷ vol52 — Sharpe ย้อนหลัง 11 เดือน"),
                       "R12_1": st.column_config.NumberColumn("return 12-1", format="percent"),
                       "vol52": st.column_config.NumberColumn("vol 52 สัปดาห์", format="percent")})
if live["dropped"]:
    dropped = pd.DataFrame(live["dropped"])
    n_data = int(dropped["data_issue"].sum())
    st.markdown(f"**กองที่ถืออยู่แต่ไม่ถือต่อ ({len(dropped)} กอง)**"
                + (f" — ⚠️ {n_data} กองเพราะ**ข้อมูล NAV ไม่พร้อม** ไม่ใช่สัญญาณขาย" if n_data else ""))
    st.dataframe(dropped[["FundCode", "family", "reason"]], hide_index=True, **page_common.TABLE_WIDTH,
                 column_config={"reason": st.column_config.TextColumn("เหตุผล")})

with st.expander("📋 สัญญาณของทุก family ณ วันที่เลือก (เรียงตามอันดับ)"):
    st.dataframe(table, hide_index=True, **page_common.TABLE_WIDTH)
with st.expander("🔁 ไตรมาสที่ไล่ rebalance มา (สถานะถือครอง)"):
    log = quarters.copy()
    log["t"] = log["t"].dt.date
    st.dataframe(log[["t", "n_universe", "n_fresh", "coverage", "skipped", "n_selected", "n_kept", "cash", "fallback"]],
                 hide_index=True, **page_common.TABLE_WIDTH,
                 column_config={"coverage": st.column_config.NumberColumn("กองสด (เทียบ ธ.ค. 2025)", format="percent"),
                                "cash": st.column_config.NumberColumn("เงินสด", format="percent")})

# ---------- ส่วนที่ 1b — พอร์ต M019 (จากไฟล์อ้างอิงของทีม quant) ----------
st.markdown("#### ★ พอร์ต M019 (หุ้น 3 กอง + ทอง) — จาก backtest ของทีม quant")
try:
    m019 = data_access.get_gc75_frontier()["holdings"]
except Exception as e:  # noqa: BLE001
    st.error(f"โหลดไฟล์พอร์ต M019 ไม่สำเร็จ: {type(e).__name__}: {e}\n\n"
             "สร้างด้วย `PYTHONPATH=. ./.venv/bin/python .claude/quant_team/backtest/export_gc75_frontier.py`")
    m019 = None
if m019 is not None:
    m_q = sorted(m019["t"].unique())
    usable = [t for t in m_q if t <= as_of]
    if not usable:
        st.info(f"M019 เริ่มถือ {pd.Timestamp(m_q[0]):%Y-%m-%d} — ยังไม่มีพอร์ต ณ วันที่เลือก")
    else:
        t_m = pd.Timestamp(usable[-1])
        h_m = m019[m019["t"] == t_m].copy()
        eq_m = h_m.loc[h_m["kind"] == "E", "weight"].sum()
        if as_of > pd.Timestamp(m_q[-1]):
            st.warning(f"พอร์ต M019 ล่าสุดในไฟล์คือไตรมาส {pd.Timestamp(m_q[-1]):%Y-%m-%d} (ไม่ได้คำนวณสดในแอป) — "
                       "หลังจากนั้นทีม quant ยังไม่ได้ export · ใช้ดูโครงพอร์ตเท่านั้น")
        a1, a2, a3 = st.columns(3)
        a1.metric("ไตรมาส (ตัดสินใจ)", f"{t_m:%Y-%m-%d}", f"ซื้อขาย {pd.Timestamp(h_m['e'].iloc[0]):%Y-%m-%d}", delta_color="off")
        a2.metric("สัดส่วนหุ้น (GC75)", f"{eq_m:.0%}")
        d_m = h_m[h_m["kind"] != "E"]
        a3.metric("ขาตั้งรับ", f"{d_m['weight'].sum():.0%}",
                  (f"{gf.KIND_LABEL[d_m['kind'].iloc[0]]} {d_m['FundCode'].iloc[0]}" if len(d_m) else "ไม่มี (หุ้น 100%)"), delta_color="off")
        h_m["ชนิด"] = h_m["kind"].map(gf.KIND_LABEL)
        st.dataframe(h_m.sort_values(["kind", "weight"], ascending=[True, False])[["ชนิด", "FundCode", "family", "weight", "sr12p", "rank"]],
                     hide_index=True, **page_common.TABLE_WIDTH,
                     column_config={"weight": st.column_config.NumberColumn("น้ำหนัก", format="percent"),
                                    "sr12p": st.column_config.NumberColumn("SR12′", format="%.2f",
                                                                           help="(R12-1 − ดอกเบี้ยนโยบายจริงทบต้น 11 เดือน) ÷ vol52"),
                                    "rank": st.column_config.NumberColumn("อันดับ", format="%d"), "family": "family"})
        st.caption("M019: หุ้น 3 กอง = อันดับ 1 ตาม SR12′ (เกณฑ์คุณภาพ AUM ≥ 100 ล้าน · อายุ ≥ 2 ปี) + เติมกองที่ correlation กับกองที่เลือกแล้ว"
                   "ต่ำสุดจากอันดับ ≤ 9 · ERC เพดาน 40% · สัดส่วนหุ้นตาม GC75 · ส่วนที่เหลือ = กองทอง AUM ใหญ่สุด · "
                   "efficient frontier ของพอร์ตนี้ดูที่หน้า 🗺 M019 Frontier")

# ---------- ส่วนที่ 2 — ผลย้อนหลัง TOP3 ----------
st.subheader(f"2 · ผล backtest walk-forward — TOP3 (ถึง {pd.Timestamp(config.TF_EVAL_END):%Y-%m-%d})")
st.caption("① **GC75 + กองตลาดเงิน** — กองชุดเดียวกับ ③ แต่สัดส่วนหุ้นไล่ระดับ 100/75/50/25% ตามผลตอบแทน MSCI ACWI "
           "3/6/12 เดือนเทียบดอกเบี้ย (ปรับทุกไตรมาส) · ส่วนที่ไม่ถือหุ้นพักในกองตลาดเงิน AUM ใหญ่สุด ⚠️ เลือกหลังเห็นผลบางส่วน  \n"
           "② **Trend 25** — โมเดลของหน้านี้ (ส่วนที่ 1): 8 กอง SR12 + ERC + เงินสด 25% เมื่อ ACWI < SMA200  \n"
           "③ **M012-QF-S** — Trend 25 + ดอกเบี้ยจริงใน SR12 + เกณฑ์คุณภาพ (AUM ≥ 100 ล้าน · อายุกอง ≥ 2 ปี)  \n"
           "★ **M019** — หุ้น 3 กอง (อันดับ 1 + correlation ต่ำ) · ERC เพดาน 40% · สัดส่วนหุ้น GC75 · ส่วนที่เหลือถือกองทอง AUM ใหญ่สุด "
           "⚠️ เลือกหลังเห็นผลหลายรอบ (ทีมลอง 88 แบบ) · ระดับที่ไม่ขึ้นกับเดือน rebalance ราว Sharpe 0.6–1.5 ตาม offset")
case_labels = {"full": "ค่าธรรมเนียมจริง (จ่ายเต็ม)", "nofront": "ยกเว้นค่าธรรมเนียมขาย (front-end)",
               "flat": f"ต้นทุนคงที่ {config.TF_COST_FLAT:.1%} ต่อข้าง"}
case = st.radio("ต้นทุนซื้อขาย", list(case_labels), format_func=case_labels.get, horizontal=True,
                help="ค่าธรรมเนียมจริงรายกองจาก SecFundFee (อัตรา ณ วันซื้อขาย · สลับใน บลจ. เดียวกันใช้ช่องทางสับเปลี่ยนถ้าถูกกว่า) · "
                     "ค่าบริหารกอง (TER) หักใน NAV แล้ว · เงินสด/กองตลาดเงินไม่มีค่าธรรมเนียมซื้อขาย")
curves = top3["curves"]
st.plotly_chart(viz.tf_equity_chart(curves, case), **page_common.CHART_WIDTH)
st.plotly_chart(viz.tf_drawdown_chart(curves, case), **page_common.CHART_WIDTH)

rows = []
for series in config.TF_TOP3_SERIES:
    if (series, case) in metrics.index:
        m = metrics.loc[(series, case)]
        g = curves[(curves["series"] == series) & (curves["case"] == case)].set_index("date")["value"]
        yr = tf_model.year_returns(g)
        rows.append({"พอร์ต": viz.TF_SERIES_LABELS[series], "Sharpe": m["sharpe"], "Return/ปี": m["cagr"],
                     "Vol/ปี": m["vol"], "Max DD": m["max_dd"], "ต้นทุน/ปี": m["cost_pct_yr"] / 100, "DSR": m["dsr"],
                     **{f"ปี {y}": v for y, v in yr.items()}})
pct = st.column_config.NumberColumn(format="percent")
st.dataframe(pd.DataFrame(rows), hide_index=True, **page_common.TABLE_WIDTH,
             column_config={"Sharpe": st.column_config.NumberColumn(format="%.2f"),
                            "DSR": st.column_config.NumberColumn(format="%.2f",
                                                                 help=f"deflated Sharpe หลังลอง {config.TF_TOP3_N_TRIALS} แบบ (0–1)"),
                            "Return/ปี": pct, "Vol/ปี": pct, "Max DD": pct, "ต้นทุน/ปี": pct,
                            **{c: pct for r in rows for c in r if c.startswith("ปี ")}})
st.caption("universe เต็ม (ซื้อได้ทุก class) · rf = ดอกเบี้ยนโยบาย ธปท. จริง · rebalance ตัดสินใจสิ้น มี.ค./มิ.ย./ก.ย./ธ.ค. "
           "ซื้อขายวันทำการที่ 2 · ปีแรกนับจากวันซื้อแรก (4 เม.ย. 2022) · B0 = ถือทุกกองใน universe เท่ากัน (1 class ต่อกอง) · "
           "ผลของ ① ③ มาจากไฟล์อ้างอิงคงที่ของทีม quant (`base_data/reference/tf_top3_*.csv`) ไม่ได้คำนวณในแอป  \n"
           "**ความไวต่อเดือน rebalance:** เลื่อนเดือนตัดสินใจไป เม.ย./ก.ค./ต.ค./ม.ค. หรือ พ.ค./ส.ค./พ.ย./ก.พ. "
           "Sharpe (ค่าธรรมเนียมจริง) อยู่ในช่วง ① 0.35–0.98 · ② 0.41–1.00 — ส่วนต่างระหว่างโมเดลแยกไม่ออกทางสถิติ")

events = cache["meta"].get("sim_events", [])
if events:
    st.info("ระหว่าง backtest มีไตรมาสที่ซื้อกองไม่ได้ (ส่วนนั้นถือเป็นเงินสด) หรือถือกองที่ NAV ค้างเกิน "
            f"{config.NAV_STALE_MAX_DAYS} วัน (มูลค่าเป็นราคาเก่า): "
            + " · ".join(f"{e['t']}: " + ", ".join(e["cannot_buy"] + [f"{s} (NAV ค้าง)" for s in e["stale_marks"]])
                         for e in events))
if cache["meta"].get("fee_median_fallback"):
    st.warning("ไฟล์ค่าธรรมเนียมไม่มีค่าที่ใช้ได้สำหรับ " + ", ".join(cache["meta"]["fee_median_fallback"])
               + f" — ใช้ต้นทุนคงที่ {config.TF_COST_FLAT:.1%} แทน")

with st.expander("🗂 กองที่ถือในแต่ละไตรมาสของ backtest (② Trend 25)"):
    h = cache["holdings"]
    bt_t = quarters.loc[quarters["in_backtest"], "t"]
    h = h[h["t"].isin(bt_t)].copy()
    h["FundCode"] = h["FundCode"].replace({fund_backtest.CASH: "เงินสด"})
    pivot = h.pivot_table(index="FundCode", columns=h["t"].dt.strftime("%Y-%m"), values="weight", aggfunc="sum")
    st.dataframe(pivot.sort_index(), **page_common.TABLE_WIDTH,
                 column_config={c: st.column_config.NumberColumn(format="percent") for c in pivot.columns})

with st.expander("⚠️ ข้อจำกัดที่ต้องรู้"):
    st.markdown(
        f"- **พิสูจน์ทางสถิติไม่ได้**: ข้อมูล 45 เดือน มีขาลงจริงครั้งเดียว (2022) · ลองไปแล้ว {config.TF_TOP3_N_TRIALS} แบบบนข้อมูลชุดเดียวกัน\n"
        "- **ผลส่วนใหญ่มาจากตลาดขาขึ้น 2023–2025** · ปี 2022 ยังขาดทุน · ตัดไตรมาสที่ดีที่สุด (2024Q1) ออก Sharpe เหลือราว 0.4\n"
        "- **กระจุกในธีม**: เพดาน 25% ต่อกองไม่กันกองต่างค่ายที่ลงทุนธีมเดียวกัน (infra, อินเดีย, เทค บางไตรมาส 45–63%) · "
        "ลองจำกัดกลุ่มแล้ว (M008) Sharpe ลดลง\n"
        "- **ความเสี่ยงพอร์ตน่าจะสูงกว่าที่ประมาณ**: NAV กองไทยออกไม่พร้อมกัน ทำให้ correlation รายสัปดาห์ต่ำเกินจริง "
        "(ค่ากลาง 0.35 → 0.49 เมื่อปรับ lead-lag · กองธีมเดียวกันบางคู่ 0.25 → 0.99) · น้ำหนัก ERC คลาดราว 5% · "
        "vol พอร์ตที่ประมาณต่ำไปราว 7% (เทียบที่เกิดจริงต่ำไป 15–25%) · 8 กองกระจายจริงแค่ ~1.5–2 การเดิมพันอิสระ\n"
        "- **ค่าธรรมเนียม**: มีข้อมูลตั้งแต่ พ.ค. 2023 — ปี 2022 ใช้อัตราปี 2023 แทน · ผลไวมากต่อการได้ยกเว้น front-end · "
        "ยังไม่คิดภาษีและเงินค้างรอรับค่าขาย (T+n)\n"
        f"- **rf**: ผล backtest ส่วนที่ 2 ใช้ดอกเบี้ยนโยบาย ธปท. จริง · พอร์ตแนะนำส่วนที่ 1 ยังใช้ hurdle {config.TF_RF_SIGNAL:.0%} คงที่ใน SR12 · NAV class ปันผล (-D) ไม่รวมปันผล\n"
        "- **พอร์ตแนะนำปี 2026** เลือกจากกองสดน้อยกว่าช่วงที่ทดสอบมาก — ดูจำนวนกองสดทุกครั้ง")
