#!/usr/bin/env python3
"""Orchestrator ของการโต้แย้งหน้า 8 (Defender vs Critic -> Judge).

ทำอะไร: ประกอบ prompt ของแต่ละบทบาทจาก `.claude/agents/page8-*.md` + BRIEF.md,
รัน 2 รอบ (รอบ 2 ส่งรายงานของอีกฝ่ายให้ตอบ) แล้วให้ Judge สรุป
บันทึกผลลง `.claude/page8_debate/results/`.

วิธีรัน agent: เรียก `claude -p` (Claude Code แบบ non-interactive) ต่อ 1 บทบาท/1 รอบ
  * `--model <ค่า model: ใน frontmatter>` ส่งต่อบทบาทอัตโนมัติ (ตอนนี้ทุกบทบาทตั้งเป็น opus)
  * `--allowedTools "Read,Grep,Glob,Bash"` -> บทบาทเหล่านี้ไม่มี Edit/Write (read-only เชิงเครื่องมือ;
    Bash ยังเขียนไฟล์ได้ในทางเทคนิค จึงมีกฎ READ-ONLY ใน BRIEF.md ประกอบ)
  * ยังไม่ได้ทดสอบกับ `claude` CLI จริง (ทดสอบแล้วเฉพาะ --dry-run) — ถ้า flag ต่างจากเวอร์ชันที่ติดตั้ง
    ให้แก้ฟังก์ชัน `run_agent` ที่เดียว

ตัวอย่าง:
  python3 .claude/page8_debate/orchestrator.py --dry-run          # พิมพ์ prompt ไม่รัน
  python3 .claude/page8_debate/orchestrator.py --rounds 2         # รันจริง (ใช้โทเคนมาก)
  python3 .claude/page8_debate/orchestrator.py --only round1      # เฉพาะรอบ 1
"""
import argparse
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]                 # root โปรเจกต์ (มี app.py)
AGENTS = ROOT / ".claude" / "agents"
RESULTS = HERE / "results"
ALLOWED_TOOLS = "Read,Grep,Glob,Bash"


def load_role(name: str) -> str:
    """อ่านเนื้อหา agent .md ตัด frontmatter ออก"""
    text = (AGENTS / f"page8-{name}.md").read_text(encoding="utf-8")
    return re.sub(r"\A---\n.*?\n---\n", "", text, flags=re.S).strip()


def load_model(name: str) -> str:
    """อ่านค่า `model:` จาก frontmatter ของ agent (เช่น opus / sonnet / inherit)"""
    text = (AGENTS / f"page8-{name}.md").read_text(encoding="utf-8")
    m = re.search(r"^model:\s*(\S+)", text, flags=re.M)
    return m.group(1) if m else "inherit"


def run_agent(prompt: str, dry_run: bool, role: str) -> str:
    """จุดเดียวที่ผูกกับเครื่องมือภายนอก: ส่ง prompt ให้ claude -p แล้วคืนข้อความตอบ
    ส่ง --model ตามที่ตั้งใน frontmatter (ถ้า inherit ไม่ส่ง = ใช้โมเดลเริ่มต้นของ CLI)"""
    model = load_model(role)
    if dry_run:
        return f"[dry-run: ไม่ได้เรียก agent role={role} model={model}]"
    cmd = ["claude", "-p", prompt, "--allowedTools", ALLOWED_TOOLS]
    if model != "inherit":
        cmd += ["--model", model]
    proc = subprocess.run(
        cmd,
        cwd=ROOT, capture_output=True, text=True,
    )
    if proc.returncode != 0:
        sys.exit(f"claude -p ล้มเหลว: {proc.stderr[:500]}")
    return proc.stdout.strip()


def build_round1(role: str) -> str:
    return (f"{load_role(role)}\n\n---\nทำรอบ 1 ตามรูปแบบคำตอบรอบ 1 ข้างต้น "
            f"(อ่าน .claude/page8_debate/BRIEF.md ก่อน)")


def build_round2(role: str, opponent_name: str, opponent_report: str) -> str:
    return (f"{load_role(role)}\n\n---\nรอบ 2: นี่คือรายงานรอบ 1 ของ {opponent_name} "
            f"ให้ตอบตามรูปแบบคำตอบรอบ 2 ข้างต้น (รัน what-if ตรวจซ้ำเองเมื่อทำได้)\n\n"
            f"=== รายงานของ {opponent_name} ===\n{opponent_report}")


def build_judge() -> str:
    files = ["round1_defender", "round1_critic", "round2_defender", "round2_critic"]
    bundle = "\n\n".join(
        f"=== {f}.md ===\n{(RESULTS / (f + '.md')).read_text(encoding='utf-8')}" for f in files
    )
    return f"{load_role('judge')}\n\n---\nรายงานทั้งหมดของรอบ 1–2:\n\n{bundle}"


def save(name: str, text: str, dry_run: bool) -> None:
    if dry_run:
        return
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / f"{name}.md").write_text(text + "\n", encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rounds", type=int, default=2, choices=(1, 2))
    ap.add_argument("--only", choices=("round1", "round2", "judge"))
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    dr = a.dry_run

    def show(title: str, prompt: str) -> None:
        if dr:
            print(f"\n######## {title} ({len(prompt)} ตัวอักษร) ########\n{prompt[:1200]}\n...")

    if a.only in (None, "round1"):
        for role in ("defender", "critic"):
            p = build_round1(role)
            show(f"round1 {role}", p)
            save(f"round1_{role}", run_agent(p, dr, role), dr)

    if a.rounds == 2 and a.only in (None, "round2"):
        d1 = "" if dr and not (RESULTS / "round1_defender.md").exists() else (RESULTS / "round1_defender.md").read_text(encoding="utf-8")
        c1 = "" if dr and not (RESULTS / "round1_critic.md").exists() else (RESULTS / "round1_critic.md").read_text(encoding="utf-8")
        pd_ = build_round2("defender", "Critic", c1)
        pc_ = build_round2("critic", "Defender", d1)
        show("round2 defender", pd_)
        show("round2 critic", pc_)
        save("round2_defender", run_agent(pd_, dr, "defender"), dr)
        save("round2_critic", run_agent(pc_, dr, "critic"), dr)

    if a.only in (None, "judge"):
        p = build_judge()
        show("judge", p)
        save("judge_summary", run_agent(p, dr, "judge"), dr)


if __name__ == "__main__":
    main()
