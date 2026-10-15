# 🧭 หน้า 11 — M052 Frontier

**ไฟล์:** `pages/11_🧭_M052_Frontier.py` · ส่วนแสดงผลร่วมกับหน้า 10: `page_frontier.py` · คำนวณ `analysis/gc75_frontier.py`
(`frontier_case(..., model_weights=น้ำหนักที่ถือจริง)`) · ค่าคงที่กริด/ไตรมาส `config.GC75_FRONTIER_*` · ไฟล์ `config.M052_FRONTIER_*`

## หน้านี้ทำอะไร
efficient frontier แบบเดียวกับหน้า 10 แต่ใช้กองและสัดส่วนที่ **M052** (ตัวที่ดีสุดใน TOP5 · `.claude/quant_team/debate/TOP5.md`) ถือจริง
— 4 ไตรมาสชุดเดียวกับหน้า 10 (2022-09-30 · 2024-03-29 · 2024-09-30 · 2025-09-30) บนลงล่าง · ต่อไตรมาส: กราฟ → ตาราง `Exp` / `T_*_Q1` / `T_*_Y1`
ของ MVP · Max Sharpe · Model Portfolio → กองที่ถือ (กราฟแท่ง + ตารางน้ำหนัก)

**M052** = M019 + ลดค่าธรรมเนียม (FEE0 · SIW · BAND5) + **CANARY** (MSCI EM + บอนด์จริง AGG) + **VSL**
· สัดส่วนหุ้น = max(25%, min(GC75 × VSL, 1 − b/2)) · หัวไตรมาสแสดง k / b / ตัวคูณ VSL / เป้า x

## ต่างจากหน้า 10
| | หน้า 10 (M019) | หน้า 11 (M052) |
|---|---|---|
| จุด Model Portfolio | ERC ตามกติกา (= ที่ถือจริง) | **น้ำหนักที่ถือจริง** — มี BAND5 จึงไม่ใช่ ERC ล้วน · บางกองอาจเกิน 40% ของส่วนหุ้น (อยู่นอกกริด) |
| ชุดกองหุ้น | M019 | M033 (FEE0/SIW เปลี่ยนการเลือกบางไตรมาส) |
| สัดส่วนหุ้น/ทอง | GC75 | GC75 + CANARY + VSL (เช่น 2024-12-31 หุ้น 25% · 2025-03-31 38.7%) |

## ข้อมูล
`base_data/reference/m052_frontier_{holdings,weekly,realized}.csv` — holdings มีคอลัมน์ต่อไตรมาส `gc_k`, `x_gc`, `canary_b`, `vsl_mult`, `x_model`
```bash
PYTHONPATH=. ./.venv/bin/python .claude/quant_team/backtest/run_r6.py export52
```
regression ในสคริปต์: Sharpe = M052 ใน `R6_results.csv` · ต่อผล Q1 ของ Model ทุกไตรมาส = มูลค่าพอร์ตจาก simulate (1.9644811526) ·
export นี้เขียน `results/EXPORT_m052_*` ด้วย → รัน `export_top3.py` ต่อเพื่ออัปเดตหน้า 9 · test `tests/test_m052_frontier.py`

## ⚠️ ข้อควรระวัง
เหมือนหน้า 10 + กติกา M052 ถูกเลือกหลังเห็นผล (102 trials) · benchmark หุ้น 57% + ทอง 43% คงที่ได้ Sharpe 1.41 (ดู `reports/M052_portfolio_logic.md` §4.7) · ผลดีส่วนใหญ่มาจากไตรมาส 1 ปี 2025 · ไม่ใช่คำแนะนำการลงทุน
