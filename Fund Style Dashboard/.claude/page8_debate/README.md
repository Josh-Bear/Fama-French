# page8_debate — sub-agent โต้แย้งหน้า 8 (Score Screen)

ชุด sub-agent 3 บทบาท (Defender / Critic / Judge) สำหรับตรวจวิธีวิทยาของหน้า 8 เท่านั้น
สร้างจาก session 2026-09-29. **ไม่แก้โค้ดโปรเจกต์** (read-only).

## โครงสร้าง
```
.claude/
├── agents/                      # นิยาม agent (Claude Code อ่านจากที่นี่)
│   ├── page8-defender.md        # ปกป้องดีไซน์ปัจจุบัน
│   ├── page8-critic.md          # red-team หาข้อบกพร่อง
│   └── page8-judge.md           # อ่านรายงานทั้งหมดแล้วสรุป (ห้ามแก้โค้ด)
└── page8_debate/
    ├── BRIEF.md                 # บริบทร่วม + กฎ READ-ONLY + ระบบปัจจุบัน
    ├── orchestrator.py          # ประกอบ prompt + ลำดับรอบ (ยัง --dry-run เท่านั้นที่ทดสอบ)
    ├── whatif/                  # สคริปต์ what-if จริงที่ agent รันใน session แรก
    │   ├── def/base.py, wi.py   #   Defender: ตัวช่วยเลือกกอง/คำนวณ frontier
    │   └── run1..run11.py       #   Critic (ดูตารางด้านล่าง)
    └── results/
        ├── round1_defender.md, round1_critic.md
        ├── round2_defender.md, round2_critic.md
        └── judge_summary.md     # ตารางสรุปเรียงตามความรุนแรง
```
เหตุผลที่ `agents/` มีแต่ `.md` นิยาม agent: Claude Code จะโหลดทุกไฟล์ `.md` ในโฟลเดอร์นั้นเป็น agent จึงแยกรายงาน/สคริปต์ไปไว้ใน `page8_debate/`.

## agent ทำงานอย่างไร
- แต่ละ agent = ไฟล์ `.md` (frontmatter: `name`, `description`, `tools`, `model`) + ตัวเนื้อหาคือคำสั่งบทบาท
- `model: opus` ในทั้ง 3 ไฟล์ (เปลี่ยนเป็น `sonnet`/`haiku`/`inherit` ได้ที่บรรทัดเดียว); `orchestrator.py` อ่านค่านี้แล้วส่ง `--model` ให้ `claude -p` เอง
- `tools: Read, Grep, Glob, Bash` — **ไม่มี Edit/Write** เลยแก้ไฟล์ตรงๆ ไม่ได้; แต่ Bash เขียนไฟล์ได้ในทางเทคนิค จึงมีกฎ READ-ONLY ใน `BRIEF.md` ให้ทุก agent อ่านก่อนเริ่ม
- sub-agent ไม่เห็นบทสนทนาหลัก → ทุกอย่างที่ต้องรู้อยู่ใน `BRIEF.md` + ไฟล์โค้ด
- ลำดับ: รอบ 1 (Defender ∥ Critic ทำอิสระ) → รอบ 2 (ส่งรายงานของอีกฝ่ายให้ตอบ) → Judge สรุป

## วิธีใช้
1. **ใน Claude Code** (เปิดที่ root โปรเจกต์): เรียก `page8-defender` และ `page8-critic` พร้อมกัน (subagent_type) ให้ทำรอบ 1 → ส่งรายงานให้กันแล้วทำรอบ 2 → เรียก `page8-judge`
2. **ด้วยสคริปต์:** `python3 .claude/page8_debate/orchestrator.py --dry-run` เพื่อดู prompt; ถอด `--dry-run` เพื่อรันจริงผ่าน `claude -p` (ใช้โทเคนมาก; ยังไม่ได้ทดสอบกับ CLI จริง แก้ `run_agent()` ที่เดียวถ้า flag ต่างกัน)
3. รัน what-if เองจาก root โปรเจกต์: `PYTHONDONTWRITEBYTECODE=1 python3 .claude/page8_debate/whatif/run6.py`

## สคริปต์ what-if (ทั้งหมด import โมดูลโปรเจกต์ + print ผล; รันจาก root โปรเจกต์)
| ไฟล์ | ทดสอบอะไร |
|---|---|
| `run1.py` | จำนวนกองที่ผ่าน min_score 0.7 ทุกโหมด (clean/ไม่ clean × AND/OR × primary/secondary) |
| `run2.py` | ตารางกองที่เลือกในแต่ละโหมด |
| `run3.py` | ช่องว่างวัน NAV (median/mean gap) ต่อกองใน window 756 → ข้อ annualize |
| `run4.py` | กองที่ NAV เก่า (stale < 2026-06-30) และกองที่ผ่านเกณฑ์ → ข้อ freshness gate |
| `run5.py` | (a) placebo R² (circular shift) (b) NAV lag (c) annualisation แบบ gap-normalised vs √252 → R² in-sample bias / ข้อ annualize |
| `run6.py` | max-Sharpe/RC ต่อชุดกอง และตรวจว่าชนเพดาน/floor หรือไม่ (ฟังก์ชัน `report`) |
| `run7.py` | snapshot zone score, (f) ความไวต่อ window/skip ของ momentum, (g) คุณภาพของ label |
| `run8.py` | split-half ความเสถียรของ primary label (top-40) |
| `run9.py` | corr โมเดล vs corr จริงบน NAVDate ร่วม |
| `run10.py` | ความเสี่ยงพอร์ตจริง vs โมเดลที่น้ำหนัก tangency |
| `run11.py` | subsample ทุก 1/5/10 NAVDate เพื่อเช็กความคงที่ของ corr |
| `def/base.py`, `def/wi.py` | ตัวช่วยของ Defender (รอบ 1): เลือกกอง, คำนวณ frontier/RC พร้อมแปรค่า γ, ref, lookback, maxw. **หมายเหตุ:** ใช้ `data_access.get_index_snapshot`/`get_score_matches`; สคริปต์ `run*.py` ใช้ `_load_index_snapshot`/`score_matches` — ชื่อฟังก์ชันภายในของ data_access ที่ agent ใช้ตอนรัน ถ้าไม่ตรงกับโค้ดปัจจุบันให้ปรับชื่อ |

สคริปต์เหล่านี้คัดลอกมาจาก `/tmp` ตามที่ agent เขียน **ไม่ได้ผ่านการรีวิวหรือรันซ้ำหลังคัดลอก**; สคริปต์ที่ Defender รอบ 2 รันเป็นคำสั่ง inline ไม่ได้ถูกเก็บไว้.

## ข้อควรระวัง
- `import data_access` เรียก `nav_loader` ที่เขียนทับ `cache/nav_spike_fixes.csv` (mtime เปลี่ยน) — ตรวจว่าเนื้อหาไม่เปลี่ยนหลังรัน
- ผลลัพธ์ใน `results/` เป็นความเห็นของ agent ไม่ใช่ข้อสรุปที่ผ่านการตรวจโดยผู้ใช้; ตัวเลขที่ฝ่ายหนึ่งรับต่อจากอีกฝ่ายมีหมายเหตุกำกับไว้
- รอบ 1 แต่ละ agent จัดตัวอักษรหัวข้อ A–D ไม่ตรงกัน จึงใช้ชื่อหัวข้อเต็มใน `BRIEF.md`
