"""page_frontier.py — ส่วนแสดงผลร่วมของหน้า frontier (หน้า 10 = M019 · หน้า 11 = M052).

ต่อไตรมาส (สุ่มคงที่ · บนลงล่าง): กราฟ frontier 1 รูป → ตารางเดียว Exp / T_*_Q1 / T_*_Y1 ของ MVP · Max Sharpe · Model Portfolio
→ กองที่ถือ (กราฟแท่ง Max Sharpe vs Model + ตารางน้ำหนักทั้งพอร์ต) · คำนวณ analysis/gc75_frontier.py · input จากไฟล์อ้างอิงของทีม quant
"""
from __future__ import annotations

import json
from typing import Callable

import pandas as pd
import streamlit as st

import config
import page_common
import viz
from analysis import gc75_frontier as gf

AXES = ("ความเสี่ยง (vol ต่อปี)", "ผลตอบแทนคาดหวัง (ต่อปี)")
# legend ใต้กราฟ (ค่าเริ่มต้นหน้า 8 ไม่เปลี่ยน) · แกน x ทศนิยม 2 ตำแหน่ง: กรอบ 0–40% × 3 กอง ทำให้ช่วงความเสี่ยงแคบ
LAYOUT = dict(height=560, legend=dict(orientation="h", y=-0.15, x=0, yanchor="top"), margin=dict(t=10, b=10),
              xaxis_tickformat=".2%")
MS, MODEL = "max Sharpe", "ERC (กติกาโมเดล)"                                # ชื่อคอลัมน์จาก gf.frontier_case / ไฟล์ผลจริง
LABEL = {"MVP": "MVP", MS: "Max Sharpe", MODEL: "Model Portfolio"}           # ชื่อที่แสดง (Model Portfolio = พอร์ตที่โมเดลถือจริง)
POINTS = (("MVP", "mvp", "#2ca02c", "diamond"), (LABEL[MODEL], "erc", "#9467bd", "square"))
COMPARE_COLORS = {LABEL[MS]: "#ff7f0e", LABEL[MODEL]: "#9467bd"}
SHARPE_MIN_RISK = 0.005   # แสดงผลเท่านั้น: พอร์ต vol ต่ำมาก → (ret − rf)/σ ระดับ −100 ที่ไม่มีความหมาย
TABLE_COLS = ["Exp vol", "Exp return", "Exp Sharpe", "T_vol_Q1", "T_return_Q1", "T_sharpe_Q1", "T_vol_Y1", "T_return_Y1", "T_sharpe_Y1"]


def defensive_text(h_t: pd.DataFrame) -> str:
    d = h_t[h_t["kind"] != "E"]
    if len(d) == 0:
        return "ไม่มีขาตั้งรับ (หุ้น 100%)"
    r = d.iloc[0]
    return f"{gf.KIND_LABEL[r['kind']]} {r['FundCode']} {r['weight']:.0%} (ล็อกในทุกพอร์ต)"


def _p(x) -> str:
    return "-" if x is None or pd.isna(x) else f"{x:.2%}"


def _s(x) -> str:
    return "-" if x is None or pd.isna(x) else f"{x:.2f}"


def compare_table(t, res: dict, realized: pd.DataFrame | None, model_name: str, export_hint: str) -> pd.DataFrame:
    """ตารางเดียวต่อไตรมาส: คาดหวัง ณ วันตัดสินใจ + จริงช่วงไตรมาสที่ถือ (Q1) + จริง 1 ปี (Y1 · ยังไม่ครบปี = "-")."""
    names = list(res["weights"].columns)
    s = res["summary"]
    r = realized[realized["t"] == t] if realized is not None else pd.DataFrame(columns=["portfolio", "horizon"])
    stale, rows = [], []
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
        st.info(f"ยังไม่มีไฟล์ผลจริง — {export_hint}")
    elif stale:                                                  # กริด/ค่าคงที่เปลี่ยนหลัง export → น้ำหนักไม่ตรงกราฟ
        st.warning("น้ำหนักในไฟล์ผลจริงไม่ตรงกับกราฟ (ไฟล์เก่ากว่าค่าตั้งของหน้านี้): " + ", ".join(sorted(set(stale)))
                   + f" — {export_hint}")
    tab = pd.DataFrame(rows)[TABLE_COLS]
    st.dataframe(tab, **page_common.TABLE_WIDTH)
    q, y = r[r["horizon"] == "Q"], r[r["horizon"] == "1Y"]
    if len(q):
        cap = (f"`Exp` = จาก weekly return 52 สัปดาห์ก่อนวันตัดสินใจ (ต่อปี) · `T_*_Q1` = ถือจริง {q['e'].iloc[0]:%Y-%m-%d} → "
               f"{q['end'].iloc[0]:%Y-%m-%d} ({int(q['days'].iloc[0])} วัน) · `T_*_Y1` = ถือจริง 1 ปี")
        cap += (" (ยังไม่ครบปี — ข้อมูลถึง " + f"{y['end'].iloc[0]:%Y-%m-%d})" if len(y) and bool(y["truncated"].iloc[0]) else "")
        cap += (f" · ผลตอบแทนจริง/ปี = ช่วงถือ × 365/วัน หลังหักค่าธรรมเนียมจริงของการสลับจากพอร์ต {model_name} ไตรมาสก่อน · "
                f"vol จริงจาก NAV รายวัน · Sharpe จริงใช้ rf จริงของช่วงถือ ({q['rf_ann'].iloc[0]:.2%}/ปี ช่วงไตรมาส)")
        st.caption(cap)
    return tab


def render(data: dict, *, model_name: str, use_held_weights: bool, export_hint: str,
           quarter_note: Callable[[pd.DataFrame], str] | None = None) -> None:
    """วาดทุกไตรมาสที่สุ่มได้ · use_held_weights = จุด Model Portfolio ใช้น้ำหนักที่ถือจริง (False = ERC ตามกติกา M019)."""
    holdings, weekly, realized = data["holdings"], data["weekly"], data.get("realized")
    pct = st.column_config.NumberColumn(format="percent")
    for t in gf.pick_quarters(holdings["t"]):
        h_t = holdings[holdings["t"] == t]
        w_t = weekly[weekly["t"] == t]
        eq_share = h_t.loc[h_t["kind"] == "E", "weight"].sum()
        st.subheader(f"ไตรมาส {t:%Y-%m-%d} (ซื้อขาย {h_t['e'].iloc[0]:%Y-%m-%d})")
        note = quarter_note(h_t) if quarter_note else f"ถือหุ้น {eq_share:.0%}"
        st.caption(f"{note} · {defensive_text(h_t)} · rf (ดอกเบี้ยนโยบาย ธปท.) {h_t['rf'].iloc[0]:.2%}")
        try:
            held = h_t.set_index("FundCode")["weight"] if use_held_weights else None
            res = gf.frontier_case(h_t, w_t, model_weights=held)
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

        compare_table(t, res, realized, model_name, export_hint)

        st.markdown("**กองที่ถือ** — น้ำหนักในพอร์ตรวม")
        eq_codes = list(res["funds"].loc[res["funds"]["kind"] == "E", "FundCode"])
        bars = res["weights"].loc[eq_codes, [MS, MODEL]].rename(columns=LABEL)
        st.plotly_chart(viz.weights_compare_bar(bars, COMPARE_COLORS), **page_common.CHART_WIDTH, key=f"cmp_{t:%Y%m%d}")
        w = res["weights"].rename(columns=LABEL)
        info = res["funds"].set_index("FundCode")
        w.insert(0, "SR12′", info["sr12p"])
        w.insert(0, "ชนิด", info["kind"].map(gf.KIND_LABEL))
        st.dataframe(w, **page_common.TABLE_WIDTH,
                     column_config={"SR12′": st.column_config.NumberColumn(format="%.2f"),
                                    **{LABEL[c]: pct for c in res["weights"].columns}})
        st.caption(f"ส่วนหุ้น {eq_share:.0%} · ที่เหลือคือขาตั้งรับที่ล็อกไว้ · เพดานกริด {config.GC75_FRONTIER_MAX_W:.0%} ของส่วนหุ้น "
                   f"= {config.GC75_FRONTIER_MAX_W * eq_share:.0%} ของพอร์ตรวม")
        st.divider()
