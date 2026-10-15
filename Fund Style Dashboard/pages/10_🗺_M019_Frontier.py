"""M019 Frontier (หน้า 10) — efficient frontier ของกองที่ M019-LC3-GCGOLD ถือจริง 4 ไตรมาส (สุ่มคงที่).

หุ้น 3 กอง กองละ 0–40% ของส่วนหุ้น (ขาทอง/ตลาดเงินล็อกตามกติกาโมเดล) · เทียบ max Sharpe กับ ERC ของโมเดล
คำนวณ: analysis/gc75_frontier.py · input: base_data/reference/gc75_frontier_*.csv (ทีม quant) · เอกสาร: docs/pages/10-gc75-frontier.md
"""

import streamlit as st

import config
import data_access
import page_frontier
from analysis import gc75_frontier as gf

st.set_page_config(page_title="M019 Frontier", page_icon="🗺", layout="wide")
st.title("🗺 M019 Frontier")
st.caption(f"efficient frontier ของกองที่ **M019** (หุ้น 3 กอง + ขาทอง ตาม GC75) ถือจริง ณ สิ้นไตรมาส (backtest เม.ย. 2022 – ธ.ค. 2025) · "
           f"ขาทอง/ตลาดเงิน**ล็อก**ตามน้ำหนักจริงของไตรมาส · กองหุ้นแต่ละกอง {0:.0%}–{config.GC75_FRONTIER_MAX_W:.0%} ของส่วนหุ้น "
           f"ทีละ {config.GC75_FRONTIER_STEP:.0%} (= เพดาน ERC ของ M019) · {config.GC75_FRONTIER_N_QUARTERS} ไตรมาสสุ่มแบบคงที่")
st.warning("**ไม่ใช่คำแนะนำการลงทุน** · μ และ Σ มาจาก weekly return 52 สัปดาห์**ก่อน**วันตัดสินใจ (สิ่งที่เห็นได้ ณ วันนั้น) "
           "ไม่ใช่ผลที่เกิดหลังซื้อ · ค่าเฉลี่ยผลตอบแทน 1 ปีคลาดเคลื่อนสูงมาก → max Sharpe ไวต่อ μ และมักไปชนเพดาน")

EXPORT = "สร้างด้วย `PYTHONPATH=. ./.venv/bin/python .claude/quant_team/backtest/export_gc75_frontier.py`"
try:
    data = data_access.get_gc75_frontier()
except Exception as e:  # noqa: BLE001
    st.error(f"โหลดไฟล์ input ไม่สำเร็จ: {type(e).__name__}: {e}\n\n{EXPORT}")
    st.stop()

page_frontier.render(data, model_name="M019", use_held_weights=False, export_hint=EXPORT,
                     quarter_note=lambda h_t: f"GC75 ถือหุ้น {h_t.loc[h_t['kind'] == 'E', 'weight'].sum():.0%}")

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
