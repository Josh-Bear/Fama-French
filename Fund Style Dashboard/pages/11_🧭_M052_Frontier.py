"""M052 Frontier (หน้า 11) — efficient frontier ของกองที่ M052 ถือจริง 4 ไตรมาส (สุ่มคงที่ · ชุดเดียวกับหน้า 10).

M052 = M019 + ลดค่าธรรมเนียม (FEE0 + SIW + BAND5) + CANARY (MSCI EM + บอนด์จริง AGG) + VSL — ตัวที่ดีสุดใน TOP5 (บอนด์จริง)
หุ้น 3 กอง กองละ 0–40% ของส่วนหุ้น (ขาทอง/ตลาดเงินล็อก) · จุด Model Portfolio = น้ำหนักที่ถือจริง (มี BAND5 จึงไม่ใช่ ERC ล้วน)
คำนวณ: analysis/gc75_frontier.py + page_frontier.py · input: base_data/reference/m052_frontier_*.csv · เอกสาร: docs/pages/11-m052-frontier.md
"""

import streamlit as st

import config
import data_access
import page_frontier

st.set_page_config(page_title="M052 Frontier", page_icon="🧭", layout="wide")
st.title("🧭 M052 Frontier")
st.caption(f"efficient frontier ของกองที่ **M052** ถือจริง ณ สิ้นไตรมาส (backtest เม.ย. 2022 – ธ.ค. 2025) · "
           "M052 = M019 + ลดค่าธรรมเนียม (FEE0 · SIW · BAND5) + **CANARY** (ลดหุ้นเมื่อโมเมนตัม MSCI EM / บอนด์ AGG ติดลบ) + **VSL** "
           f"(ลดหุ้นเมื่อหุ้นที่ถือผันผวนกว่า ACWI) · ขาทอง/ตลาดเงิน**ล็อก**ตามน้ำหนักจริง · กองหุ้นละ {0:.0%}–{config.GC75_FRONTIER_MAX_W:.0%} "
           f"ของส่วนหุ้น ทีละ {config.GC75_FRONTIER_STEP:.0%} · {config.GC75_FRONTIER_N_QUARTERS} ไตรมาสสุ่มแบบคงที่ (ชุดเดียวกับหน้า 10)")
st.warning("**ไม่ใช่คำแนะนำการลงทุน** · μ และ Σ มาจาก weekly return 52 สัปดาห์**ก่อน**วันตัดสินใจ · กติกา M052 ถูกเลือกหลังเห็นผล "
           "(ทีมลอง 102 แบบบนข้อมูลชุดเดียวกัน) · ผลดีส่วนใหญ่มาจากไตรมาส 1 ปี 2025 ที่ถือทอง 75%")

EXPORT = "สร้างด้วย `PYTHONPATH=. ./.venv/bin/python .claude/quant_team/backtest/run_r6.py export52`"
try:
    data = data_access.get_m052_frontier()
except Exception as e:  # noqa: BLE001
    st.error(f"โหลดไฟล์ input ไม่สำเร็จ: {type(e).__name__}: {e}\n\n{EXPORT}")
    st.stop()


def note(h_t):
    r = h_t.iloc[0]
    eq = h_t.loc[h_t["kind"] == "E", "weight"].sum()
    return (f"ถือหุ้น {eq:.0%} — GC75 k = {int(r['gc_k'])} → {r['x_gc']:.0%} · CANARY b = {r['canary_b']:g} → เพดาน "
            f"{max(0.25, 1 - r['canary_b'] / 2):.0%} · VSL × {r['vsl_mult']:.3f} → เป้า {r['x_model']:.1%} (ส่วนต่างจากเป้า = BAND5 ไม่ปรับกองที่ห่าง ≤ 5 pt)")


page_frontier.render(data, model_name="M052", use_held_weights=True, export_hint=EXPORT, quarter_note=note)

with st.expander("ℹ️ อ่านหน้านี้ยังไง"):
    st.markdown(
        f"""
- **โมเดล M052** — ทุกสิ้นไตรมาส:
  1. คัดหุ้น 3 กองแบบ M019 (อันดับ 1 ตาม SR12′ + เติมกองที่ correlation ต่ำสุดจากอันดับ ≤ 9) · ถ้าคะแนนเกือบเสมอเลือกตัวที่ค่าธรรมเนียมขาเข้าถูกกว่า
     (FEE0) โดยนับช่องทางสับเปลี่ยนใน บลจ. เดียวกัน (SIW) · ERC เพดาน 40%
  2. สัดส่วนหุ้น = max(25%, min(GC75 × VSL, 1 − b/2)) · GC75 = 100/75/50/25% ตาม ACWI 3/6/12 เดือนชนะดอกเบี้ย ·
     b = จำนวนตัวเตือน (MSCI EM, บอนด์ AGG) ที่โมเมนตัม 13612W ≤ 0 · VSL = min(1, vol ACWI ÷ vol หุ้น 3 กอง)
  3. ส่วนที่เหลือ = กองทอง AUM ใหญ่สุด · กองที่ถือต่อและห่างเป้า ≤ 5 pt ไม่ปรับ (BAND5)
- **กรอบน้ำหนัก** — ขาตั้งรับ**ล็อก** · หุ้น 3 กองจัดใหม่ได้กองละ 0–{config.GC75_FRONTIER_MAX_W:.0%} ทีละ {config.GC75_FRONTIER_STEP:.0%}
- **สี่เหลี่ยมม่วง Model Portfolio** = น้ำหนักที่ M052 ถือจริงหลัง BAND5 (บางกองอาจเกิน 40% ของส่วนหุ้นจาก drift จึงอยู่นอกกริดได้)
- **ตาราง**: `Exp` = ค่าคาดหวัง ณ วันตัดสินใจ · `T_*_Q1` = ผลจริงช่วงไตรมาสที่ถือ · `T_*_Y1` = ผลจริง 1 ปี ("-" = ยังไม่ครบปี)
  · ผลจริงถือแบบไม่ rebalance และหักค่าธรรมเนียมจริงของการสลับจากพอร์ต M052 ไตรมาสก่อน · ต่อผล Q1 ของ Model ทุกไตรมาส = backtest M052
"""
    )
