"""Score Screen (หน้า 8) — 3 ส่วน: คะแนนโซน country×sector · Top 5 ที่กระจายความเสี่ยง · efficient frontier.

สเปก: PAGE8_PORTFOLIO_OPTIMIZE_PLAN.md §14 + §19-§22 · รายละเอียดที่ใช้จริง: docs/pages/8-score-screen.md
"""

import numpy as np
import pandas as pd
import streamlit as st

import config
import data_access
import page_common
import viz
from analysis import portfolio, screening

st.set_page_config(page_title="Score Screen", page_icon="🧭", layout="wide")
st.title("🧭 Score Screen")
st.caption(f"คัดกอง {config.SCORE_POLICY} จากโซนของดัชนี: ผลตอบแทน {config.SCORE_RETURN_WINDOW} วัน "
           f"(ข้าม {config.SCORE_RETURN_SKIP} วันล่าสุด) **ต่อหนึ่งหน่วยความเสี่ยง**ของช่วงเดียวกันสูง × ความแน่นของ match (R²) "
           f"· เลือกให้แต่ละกองเกาะคนละ country/sector · แล้วหาน้ำหนักพอร์ตที่เป็นไปได้ทั้งหมด")
try:   # ตัวเลขอ่านจาก cache หน้า 9 (ไม่พิมพ์ตายตัว · ไม่ build ให้ถ้ายังไม่มี) — M001 = โมเดลหน้านี้ ณ วันที่ทีม quant ทดสอบ
    if not data_access.tf_cache_ready():
        raise FileNotFoundError
    _m = data_access.get_tf_cache()["metrics"].set_index(["series", "case"])["sharpe"]
    st.info(f"ใน walk-forward backtest (เม.ย. 2022 – ธ.ค. 2025 · ค่าธรรมเนียมจริง) โมเดลแบบหน้านี้ (M001) ได้ Sharpe "
            f"{_m[('M001', 'full')]:.2f} **ใกล้เคียงการถือทุกกองเท่ากัน ({_m[('B0', 'full')]:.2f}) และต่ำกว่าโมเดลหน้า 9 "
            f"({_m[(config.TF_MODEL_ID, 'full')]:.2f})** — หน้านี้เหมาะใช้ดู exposure / การกระจายตามประเทศ-sector / "
            "frontier ของกองที่สนใจ ไม่ใช่เครื่องมือเลือกพอร์ต · M001 ทดสอบก่อนปรับ greedy / shrinkage / vol เฉพาะตัว "
            "(2026-10-02) ผลของหน้านี้ตอนนี้จึงอาจต่างจาก M001 เล็กน้อย")
except Exception:  # noqa: BLE001 — ไม่มี cache หน้า 9 ไม่ควรทำให้หน้านี้พัง
    pass
st.page_link("pages/9_📈_TF_Portfolio.py", label="ดูโมเดลที่ผ่าน backtest ที่หน้า 9 · TF Portfolio", icon="📈")

results = page_common.results_or_stop()
try:
    snapshot = data_access.get_index_snapshot()
except Exception as e:  # noqa: BLE001
    st.error(f"โหลด index snapshot ไม่สำเร็จ: {type(e).__name__}: {e}")
    st.stop()

c1, c2, c3 = st.columns(3)
with c1:
    universe = st.radio("Country universe", ["VIF-cleaned (11)", "ทั้งหมด (18)"],
                        help="ชุด 11 ตัวตัด index รวม (ACWI/WORLD/EM…) ที่ทับซ้อนกันเองออก — ในชุด 18 "
                             "primary ของกองส่วนใหญ่ (133/209) เป็น index รวม ซึ่งบอกไม่ได้ว่ากองลงทุนตลาดไหน "
                             "และมี 4 กองที่ primary coef ติดลบ (ชุด 11 ไม่มี) · secondary ติดลบพอๆ กันทั้ง 2 ชุด "
                             "แต่ถูกตัดด้วย band อยู่แล้ว")
with c2:
    mode = st.radio("Matching mode", ["Primary + Secondary", "Primary only"],
                    help="Primary only = ถ้าคู่ primary ชนกับกองที่เลือกไปแล้ว หรือ score < "
                         f"{config.SCORE_MIN_ELIGIBLE} ตกรอบทันที ไม่ลองคู่สำรอง")
with c3:
    strict = st.radio("Diversification", ["ใหม่ทั้ง country และ sector (AND)", "ใหม่อย่างใดอย่างหนึ่ง (OR)"],
                      help="เลือกกองแล้วนับ country และ sector ของคู่ที่ใช้เป็น used เสมอ · โหมด Primary + Secondary "
                           "นับคู่ primary และคู่สำรองที่ผ่าน band ของกองนั้นด้วย (กันกองที่ profile ซ้ำเข้ามาทางคู่ที่ยังว่าง)")

clean = universe.startswith("VIF")
country_ids = config.SCORE_COUNTRY_CLEAN if clean else config.MSCI_COUNTRY_COLS
try:
    matches = data_access.get_score_matches(clean_country=clean)
except Exception as e:  # noqa: BLE001
    st.error(f"โหลด match ของกองไม่สำเร็จ: {type(e).__name__}: {e}\n\n"
             "ลองรัน `./.venv/bin/python data_access.py score` เพื่อสร้าง cache")
    st.stop()

country = screening.zone_scores(snapshot, "country", config.SCORE_COUNTRY_CLEAN if clean else None)
sector = screening.zone_scores(snapshot, "sector")
matrix = screening.score_matrix(country, sector)
scored = screening.fund_scores(matches, matrix)
selected = screening.greedy_select(scored, n=config.SCORE_TOP_N,
                                   use_secondary=mode == "Primary + Secondary",
                                   strict_and=strict.endswith("(AND)"), min_score=config.SCORE_MIN_ELIGIBLE,
                                   groups=data_access.get_share_class_groups())   # ≤ 1 share class ต่อกอง

# ---------- ส่วนที่ 1 — คะแนนโซน ----------
st.subheader("1 · คะแนนโซน country × sector")
st.plotly_chart(viz.score_heatmap(matrix), **page_common.CHART_WIDTH)
if config.SCORE_ZONE_METHOD == "ret_over_realized_vol":
    zone_formula = (f"percentile(return {config.SCORE_RETURN_WINDOW}d ข้าม {config.SCORE_RETURN_SKIP} วันล่าสุด "
                    "÷ realized vol ช่วงเดียวกัน)")
else:   # สูตรเดิม — เก็บไว้ A/B 1 รอบ (§12.14)
    zone_formula = (f"percentile(return {config.SCORE_RETURN_WINDOW}d ข้าม {config.SCORE_RETURN_SKIP} วันล่าสุด) "
                    "× percentile(GARCH vol forecast แบบกลับด้าน)")
st.caption(f"score = {zone_formula} ของ country × ของ sector × {config.SCORE_MATRIX_SCALE} "
           "· percentile จัดอันดับ**ภายใน universe ที่เลือก**เท่านั้น (rescale เป็น 0.01–0.99)")

with st.expander("📋 คะแนนรายดัชนี (return / vol แยกกัน)"):
    for name, tbl in [("country", country), ("sector", sector)]:
        show = tbl.copy()
        show.index = [viz.short(i, name) if name == "country" else config.SECTOR_FULL_NAMES.get(i, i)
                      for i in show.index]
        st.write(f"**{name}**")
        st.dataframe(show.round(3), **page_common.TABLE_WIDTH)

# ---------- ส่วนที่ 2 — Top 5 ที่ผ่านเกณฑ์ ----------
picked = selected[selected["eligible"]].head(config.PORTFOLIO_TOP_N).reset_index(drop=True)
n_ok = len(picked)
st.subheader(f"2 · {config.PORTFOLIO_TOP_N} กองแรกที่ผ่านเกณฑ์กระจายความเสี่ยง (score ≥ {config.SCORE_MIN_ELIGIBLE})")

enough = n_ok >= config.PORTFOLIO_MIN_FUNDS
if not enough:
    st.error(f"**ไม่สามารถคำนวณ efficient frontier ได้ — มีกองทุนที่ผ่านเงื่อนไขน้อยเกินไป ({n_ok} กอง)** "
             f"ต้องมีอย่างน้อย {config.PORTFOLIO_MIN_FUNDS} กอง (เพดานน้ำหนัก {config.PORTFOLIO_MAX_W:.0%} × {config.PORTFOLIO_MIN_FUNDS - 1} กอง = "
             f"{(config.PORTFOLIO_MIN_FUNDS - 1) * config.PORTFOLIO_MAX_W:.0%} ไม่ถึง 100%) · เกณฑ์ score ≥ {config.SCORE_MIN_ELIGIBLE} "
             "ตัดกองที่คะแนนต่ำออกด้วย — ลองสลับเป็นโหมด OR / Primary + Secondary หรือ Country universe อีกชุด")
elif n_ok < config.PORTFOLIO_TOP_N:
    st.warning(f"ผ่านเกณฑ์แค่ {n_ok} กอง (< {config.PORTFOLIO_TOP_N}) — ส่วนที่ 3 จะใช้ {n_ok} กองนี้")

funds = tuple(picked["FundCode"])
sigma = info = mu = None
if enough:
    with st.spinner(f"fit risk model ของ {n_ok} กอง (หน้าต่าง {config.PORTFOLIO_LOOKBACK_DAYS} วันล่าสุด)…"):
        try:
            sigma, info = data_access.get_portfolio_risk_model(funds, tuple(country_ids))
        except Exception as e:  # noqa: BLE001 — ยังโชว์ตารางส่วนที่ 2 ต่อ แล้วค่อยหยุดก่อนส่วนที่ 3
            st.error(f"สร้าง risk model ไม่สำเร็จ: {type(e).__name__}: {e}")
            enough = False
if enough:
    w_ref = portfolio.reference_weights(results.set_index("FundCode").loc[list(funds), "aum"])
    sigma_sys = portfolio.systematic_covariance(sigma, info["idio_vol"].astype(float) ** 2)
    mu = portfolio.implied_returns(sigma_sys, w_ref)      # Π จาก Σ_sys (ไม่รวม D) · risk พอร์ตยังใช้ Σ เต็ม

# picked มี FundName มาจาก score_matches อยู่แล้ว — merge เฉพาะที่ยังไม่มี ไม่งั้น pandas เติม _x/_y ให้
tbl = picked.merge(results[["FundCode", "ann_return", "ann_vol"]], on="FundCode", how="left")
tbl.insert(0, "#", range(1, len(tbl) + 1))
tbl["ใช้คู่"] = tbl["pair"].map({"primary": "primary", "secondary": "secondary (สำรอง)"})
tbl["used_country"] = tbl["used_country"].map(lambda x: viz.short(x, "country"))
tbl["used_sector"] = tbl["used_sector"].map(lambda x: config.SECTOR_FULL_NAMES.get(x, "—"))
cols = ["#", "FundCode", "FundName", "score", "pair_score", "ใช้คู่", "used_country", "used_sector",
        "country_r2", "sector_r2", "ann_return", "ann_vol"]
col_cfg = {
    "score": st.column_config.NumberColumn(format="%.2f", help="R²(country×sector) × คะแนนโซนของคู่ primary — ใช้เรียงลำดับ"),
    "pair_score": st.column_config.NumberColumn("score คู่ที่ใช้", format="%.2f",
                                                help=f"คะแนนของคู่ที่ใช้เลือกจริง (primary หรือคู่สำรอง) — ตัวที่ต้อง ≥ {config.SCORE_MIN_ELIGIBLE}"),
    "country_r2": st.column_config.NumberColumn("R² country", format="%.2f"),
    "sector_r2": st.column_config.NumberColumn("R² sector", format="%.2f"),
    "ann_return": st.column_config.NumberColumn("ann return (ทั้งช่วง)", format="percent"),
    "ann_vol": st.column_config.NumberColumn("ann vol (ทั้งช่วง)", format="percent"),
}
if enough:
    yrs = config.PORTFOLIO_LOOKBACK_DAYS // config.TRADING_DAYS
    tbl["implied_return"] = tbl["FundCode"].map(mu)
    tbl["vol_win"] = tbl["FundCode"].map(info["ann_vol_win"])
    tbl["r2_win"] = tbl["FundCode"].map(info["r2"])
    cols += ["implied_return", "vol_win", "r2_win"]
    col_cfg |= {
        "implied_return": st.column_config.NumberColumn(f"Π implied return", format="percent",
                                                        help="Black-Litterman: Π = γ Σ_sys w (Σ_sys = B·F·Bᵀ ไม่รวมความเสี่ยงเฉพาะตัว · "
                                                             f"w = {config.PORTFOLIO_REF_WEIGHT} · γ คงที่ {config.PORTFOLIO_GAMMA}) — ตัวที่ส่วนที่ 3 ใช้จริง"),
        "vol_win": st.column_config.NumberColumn(f"vol {yrs} ปี", format="percent",
                                                 help=f"vol ของ return กองต่อจุด NAV (winsorize 1–99% ชุดเดียวกับที่ fit risk model) "
                                                      f"× √(จำนวนจุด NAV ต่อปีจริง) ในหน้าต่าง {yrs} ปีล่าสุด · ส่วนที่ 3 ใช้ vol ตามโมเดล (√diag Σ) "
                                                      "ซึ่งต่างจากค่านี้ได้ (F รายวันของดัชนีคนละฐานกับ D) — ดูข้อควรระวังในเอกสารหน้า 8"),
        "r2_win": st.column_config.NumberColumn("R² risk model", format="%.2f",
                                                help="R² ของ joint regression ที่ใช้สร้าง B — ต่ำ = idiosyncratic สูง"),
    }
st.dataframe(tbl[cols], **page_common.TABLE_WIDTH, hide_index=True, column_config=col_cfg)
if not enough:
    st.stop()

# ---------- ส่วนที่ 3 — Efficient frontier ----------
st.subheader("3 · Efficient frontier")
st.info(f"**Π ไม่ใช่การพยากรณ์** — เป็นผลตอบแทนที่ *สมมติว่าตลาดอยู่ในดุลยภาพ* แล้วถอดกลับจากความเสี่ยง "
        f"(Π = γΣ_sys·w, γ = {config.PORTFOLIO_GAMMA} คงที่, w = {config.PORTFOLIO_REF_WEIGHT} weight, Σ_sys = B·F·Bᵀ ไม่รวมความเสี่ยงเฉพาะตัว) "
        f"· **ความเสี่ยงพอร์ตมาจาก Σ เต็ม** (B·F·Bᵀ + D) ซึ่งเป็น factor model ไม่ใช่ correlation ของ NAV ตรงๆ "
        f"· ใช้ข้อมูล {config.PORTFOLIO_LOOKBACK_DAYS} วันล่าสุด · **ไม่ใช่คำแนะนำการลงทุน**")

w1, w2, w3 = st.columns(3)
min_w = w1.number_input("น้ำหนักต่ำสุดต่อกอง (%)", 0, 100, int(config.PORTFOLIO_MIN_W * 100), 1)
max_w = w2.number_input("น้ำหนักสูงสุดต่อกอง (%)", 1, 100, int(config.PORTFOLIO_MAX_W * 100), 1)
step_w = w3.selectbox("ขยับทีละ (%)", config.PORTFOLIO_STEP_CHOICES,
                      index=config.PORTFOLIO_STEP_CHOICES.index(int(config.PORTFOLIO_STEP_W * 100)),
                      help="เฉพาะค่าที่หาร 100 ลงตัว · min/max ที่ไม่ลงตัวกับ step จะถูกปัดเข้าในช่วง")

if min_w * n_ok > 100 or max_w * n_ok < 100:
    st.warning(f"เงื่อนไขนี้เป็นไปไม่ได้กับ {n_ok} กอง — ต่ำสุดรวม {min_w * n_ok}% · สูงสุดรวม {max_w * n_ok}% "
               "(ต้องคร่อม 100%) ปรับค่าแล้วลองใหม่")
    st.stop()
try:
    grid = portfolio.weight_grid(n_ok, min_w / 100, max_w / 100, step_w / 100)
except ValueError as e:
    st.warning(str(e))
    st.stop()
if len(grid) == 0:
    st.warning("ไม่มีชุดน้ำหนักที่ผ่านเงื่อนไขนี้เลย — ลองขยายช่วง min/max หรือลด step")
    st.stop()

points = portfolio.portfolio_points(grid, mu, sigma)
mask = portfolio.pareto_mask(points["risk"].to_numpy(), points["ret"].to_numpy())
frontier = points[mask].sort_values("risk").reset_index(drop=True)
front_w = grid[mask][points[mask]["risk"].to_numpy().argsort()]
singles = pd.DataFrame({"risk": np.sqrt(np.diag(sigma)), "ret": mu.reindex(sigma.index)}, index=sigma.index)
eq = portfolio.portfolio_points(np.full((1, n_ok), 1 / n_ok), mu, sigma).iloc[0]
i_ms = portfolio.max_sharpe_index(frontier)          # tangency portfolio (rf = 0 — ระบบไม่มี risk-free rate)
ms = frontier.iloc[i_ms]

m1, m2, m3, m4 = st.columns(4)
m1.metric("พอร์ตที่เป็นไปได้", f"{len(points):,}")
m2.metric("จุดบน frontier", f"{len(frontier):,}")
m3.metric("ช่วงความเสี่ยงบนเส้น", f"{frontier['risk'].min():.1%} – {frontier['risk'].max():.1%}")
m4.metric("max Sharpe (rf = 0)", f"{ms['ret'] / ms['risk']:.2f}",
          help=f"พอร์ตที่ให้ผลตอบแทนคาดหวังต่อหนึ่งหน่วยความเสี่ยงสูงสุด — risk {ms['risk']:.1%} · return {ms['ret']:.1%} "
               f"(equal weight {eq['ret'] / eq['risk']:.2f} · min-variance "
               f"{frontier['ret'].iat[0] / frontier['risk'].iat[0]:.2f})")
st.plotly_chart(viz.frontier_chart(points, frontier, singles, eq, ms), **page_common.CHART_WIDTH)

# label ต้องไม่ซ้ำ — Streamlit แปลง label กลับเป็นค่าด้วยตัวข้อความ (ซ้ำ = ได้ตัวท้าย) · ปัด 1 ตำแหน่ง 1,631 จุดเหลือ 58 label
labels = [f"#{i + 1} · risk {r:.2%} · return {q:.2%}"
          for i, (r, q) in enumerate(zip(frontier["risk"], frontier["ret"]))]
labels[i_ms] += "  ★ max Sharpe"
labels[0] += "  ◀ min variance"
if len(frontier) > 1:
    pick = st.select_slider("เลือกจุดบนเส้น (ซ้าย = เสี่ยงต่ำสุด · ขวา = ผลตอบแทนคาดหวังสูงสุด · ค่าเริ่มต้น = max Sharpe)",
                            options=list(range(len(frontier))), value=int(i_ms), format_func=lambda i: labels[i])
else:
    pick = 0
    st.caption("เงื่อนไขนี้เหลือพอร์ตบน frontier จุดเดียว — ขยายช่วง min/max เพื่อให้มีทางเลือก")
w_pick = pd.Series(front_w[pick], index=sigma.index, name="น้ำหนัก")
detail = pd.DataFrame({
    "FundCode": w_pick.index, "น้ำหนัก": w_pick.to_numpy(),
    "ส่วนแบ่งความเสี่ยง": portfolio.risk_contribution(w_pick, sigma).to_numpy(),
    "Π": mu.reindex(w_pick.index).to_numpy(),
    "vol (โมเดล)": np.sqrt(np.diag(sigma)),
    "R² risk model": info["r2"].reindex(w_pick.index).to_numpy(),
}).merge(results[["FundCode", "FundName"]], on="FundCode", how="left")
st.dataframe(detail[["FundCode", "FundName", "น้ำหนัก", "ส่วนแบ่งความเสี่ยง", "Π", "vol (โมเดล)", "R² risk model"]],
             **page_common.TABLE_WIDTH, hide_index=True,
             column_config={"น้ำหนัก": st.column_config.NumberColumn(format="percent"),
                            "ส่วนแบ่งความเสี่ยง": st.column_config.NumberColumn(format="percent"),
                            "Π": st.column_config.NumberColumn(format="percent"),
                            "vol (โมเดล)": st.column_config.NumberColumn(format="percent", help="√diag(Σ) — ตัวที่ใช้คำนวณความเสี่ยงพอร์ต"),
                            "R² risk model": st.column_config.NumberColumn(format="%.2f")})
st.caption(f"พอร์ตนี้: ความเสี่ยง **{frontier.loc[pick, 'risk']:.1%}** · ผลตอบแทนคาดหวัง **{frontier.loc[pick, 'ret']:.1%}** "
           f"· Sharpe (rf = 0) **{frontier.loc[pick, 'ret'] / frontier.loc[pick, 'risk']:.2f}** "
           f"· เทียบ equal weight ({1 / n_ok:.0%} ทุกกอง): ความเสี่ยง {eq['risk']:.1%} · ผลตอบแทน {eq['ret']:.1%} "
           f"· Sharpe {eq['ret'] / eq['risk']:.2f}")

with st.expander("ℹ️ อ่านหน้านี้ยังไง"):
    st.markdown(
        f"""
**ส่วนที่ 1 — คะแนนโซน** ดัชนีที่ให้ผลตอบแทน 11 เดือน (ข้ามเดือนล่าสุด) **ต่อหนึ่งหน่วยความเสี่ยง**ของช่วงเดียวกันสูง
(return ÷ realized vol — ขึ้นแรงแต่ผันผวนหนักได้คะแนนน้อยกว่าขึ้นพอดีแต่นิ่ง) · percentile จัดอันดับภายใน universe ที่เลือกเท่านั้น
· ทั้งสองขาเป็นข้อมูลอดีตช่วงเดียวกัน ไม่ใช่การพยากรณ์ · momentum ติดลบ: ตัวที่ vol ต่ำจะได้ ratio ติดลบมากกว่า (ข้อจำกัดของการหาร)

**ส่วนที่ 2 — คัดกอง** `score = (R² country × R² sector) × คะแนนโซนของคู่ (country, sector) ของกอง`
ไล่จากคะแนนสูงสุด เลือกกองที่ยังไม่ซ้ำ country/sector กับที่เลือกไปแล้ว (คู่สำรองต้องอยู่ในทิศเดียวกับ primary
และแรงอย่างน้อย {1 - config.SCORE_SECONDARY_BAND_PCT:.0%} ของ primary ถึงจะใช้ได้) · เอาเฉพาะ {config.PORTFOLIO_TOP_N} กองแรกที่ผ่านเกณฑ์

**ส่วนที่ 3 — frontier** ลองน้ำหนัก**ทุกชุดที่เป็นจำนวนเต็ม %** ตามเงื่อนไขที่ตั้งไว้ (ไม่ใช้ solver — จึงไม่มีปัญหา
convergence และน้ำหนักที่ได้ซื้อขายได้จริง) แล้วเก็บเฉพาะจุดที่ไม่มีพอร์ตอื่นให้ผลตอบแทนสูงกว่าที่ความเสี่ยงเท่ากัน

- **จุดสีฟ้าเทาจาง** = พอร์ตที่ทำได้แต่ไม่ efficient (สุ่มแสดงไม่เกิน {config.PORTFOLIO_CLOUD_MAX_POINTS:,} จุด) · **จุดน้ำเงิน** = เส้น frontier · **เพชรแดง** = ถือกองเดียว 100%
  (อยู่นอกเงื่อนไข {min_w}-{max_w}% จึงเป็นแค่จุดอ้างอิงว่า diversification ช่วยลดความเสี่ยงได้แค่ไหน)
- **ดาวส้ม = max Sharpe** (ผลตอบแทนคาดหวังต่อหนึ่งหน่วยความเสี่ยงสูงสุด · คิดที่ rf = 0 เพราะระบบไม่มี risk-free rate
  จึงไม่ใช่ Sharpe ratio ตามนิยามเต็ม) — เป็นค่าเริ่มต้นของ slider · **ดาวเขียว** = equal weight
- **Σ** = B·F·Bᵀ + D — B คือ exposure ต่อ {len(country_ids)} country + 10 sector (ชุดเดียวกับ toggle ด้านบน)
  F คือ covariance ของ factor แบบ Ledoit-Wolf shrinkage · D คือความเสี่ยงเฉพาะตัวของกอง = (1 − R²) × variance รวม
- **Π** = γΣ_sys·w — Σ_sys คือส่วนความเสี่ยงที่มาจาก factor ร่วม (ไม่รวม D เพราะความเสี่ยงเฉพาะตัวกระจายทิ้งได้ ไม่ควรได้ค่าตอบแทน) · w ใช้น้ำหนักเท่ากัน ไม่ใช้ AUM เพราะ {n_ok} กองนี้ถูกคัดมาเอง AUM ไม่ใช่พอร์ตตลาด (เคยทำให้กอง AUM ใหญ่+vol สูงได้ Π สูงจากตัวมันเอง 93%)

**ข้อควรระวัง**
- **Π ไม่ได้มาจากคะแนนโซน** — สัญญาณที่ใช้คัดกอง (ส่วนที่ 2) ไม่ได้ไหลเข้าไปในขั้นจัดน้ำหนัก ถ้าอยากให้ไหลต่อ
  ต้องเพิ่มเป็น Black-Litterman views ซึ่งยังไม่ได้ทำ
- **ความเสี่ยงมาจากโมเดล ไม่ใช่ correlation จริงของ NAV** — กองที่คล้ายกันด้วยเหตุผลนอกเหนือจาก factor (เช่นทีมบริหารเดียวกัน)
  โมเดลจะมองไม่เห็น · กองที่ R² ต่ำมี D ใหญ่ อาจถูกให้น้ำหนักน้อยทั้งที่จริงแค่ fit กับ factor set นี้ไม่เข้า
- **สัญญาณคัดกองยังไม่แน่นอน** — dry run 55 รอบ: IC ของคะแนนกองต่อ return กองจริง 63 วันข้างหน้า ~0.13 แต่ exposure ประมาณจาก
  ข้อมูลทั้งช่วงและใช้เฉพาะกองที่ยังอยู่ (มี look-ahead/survivorship) ตัวเลขจริงน่าจะต่ำกว่านี้ · ใช้จัดลำดับความน่าสนใจ ไม่ใช่คำพยากรณ์
- **ไม่ใช่คำแนะนำการลงทุน** — เป็นการคำนวณเชิงสถิติจากข้อมูลย้อนหลัง {config.PORTFOLIO_LOOKBACK_DAYS} วัน
"""
    )
