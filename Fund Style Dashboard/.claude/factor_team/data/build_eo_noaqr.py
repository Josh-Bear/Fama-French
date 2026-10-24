"""build_eo_noaqr.py — งาน GOLD-QA (BRIEF 120): สร้างสำเนา factors_eo_* ที่ไม่มีคอลัมน์ AQR_* (commit ได้)

รัน:  cd "<root>" && PYTHONDONTWRITEBYTECODE=1 ./.venv/bin/python -I -B .claude/factor_team/data/build_eo_noaqr.py [--out DIR]
- อ่าน factors_eo_weekly.parquet / factors_eo_monthly.parquet / factor_groups_eo.csv เดิมแบบอ่านอย่างเดียว (ตรวจ sha256 กับ manifest_eo.json ก่อน)
- ตัดคอลัมน์ที่ขึ้นต้นด้วย "AQR_" (รายสัปดาห์ 9 · รายเดือน 9) · คอลัมน์ที่เหลือ index / ลำดับ / dtype / ค่า ต้องเท่าเดิมทุกบิต (assert)
- ผลลัพธ์: factors_eo_noaqr_weekly.parquet · factors_eo_noaqr_monthly.parquet · factor_groups_eo_noaqr.csv · manifest_eo_noaqr.json
- ไม่แก้ manifest_eo.json (sha ถูกล็อกใน lib/l1eo.py S013_PINS → แก้แล้ว S012 รันซ้ำไม่ได้) · ไม่ดาวน์โหลด · ไม่แตะไฟล์ต้นฉบับ
- ไฟล์ผลลัพธ์ต้องไม่มีสตริง "AQR" (ตัวอักษรตัวใหญ่/เล็ก) ทั้งในชื่อคอลัมน์ · metadata parquet · csv (assert)
- ผลเหมือนเดิมทุกบิต (manifest มีฟิลด์ created ฟิลด์เดียวที่เปลี่ยนตามเวลา)
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import date

sys.dont_write_bytecode = True

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
REL = ".claude/factor_team/data/"
OUT = HERE
if "--out" in sys.argv:
    OUT = os.path.abspath(sys.argv[sys.argv.index("--out") + 1])
    os.makedirs(OUT, exist_ok=True)


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def bit_equal(a: pd.DataFrame, b: pd.DataFrame) -> bool:
    """index / columns / dtype เท่ากัน และค่า float เท่ากันทุกบิต (NaN ตำแหน่งเดียวกัน · เทียบ bytes ของ float64)"""
    if not (a.index.equals(b.index) and list(a.columns) == list(b.columns) and (a.dtypes == b.dtypes).all()):
        return False
    return a.index.name == b.index.name and np.ascontiguousarray(a.to_numpy(np.float64)).tobytes() == np.ascontiguousarray(b.to_numpy(np.float64)).tobytes()


def main():
    man_src = json.load(open(os.path.join(HERE, "manifest_eo.json")))
    want = {e["file"]: e["sha256"] for e in man_src["outputs"] if "sha256" in e}
    srcs = {}
    for fn in ("factors_eo_weekly.parquet", "factors_eo_monthly.parquet", "factor_groups_eo.csv"):
        p = os.path.join(HERE, fn)
        got = sha256(p)
        assert got == want[REL + fn], f"sha256 ไม่ตรง manifest_eo.json: {fn}"
        srcs[fn] = got

    res = {}
    for fq, fn in (("weekly", "factors_eo_weekly.parquet"), ("monthly", "factors_eo_monthly.parquet")):
        src = pd.read_parquet(os.path.join(HERE, fn))
        aq = [c for c in src.columns if c.startswith("AQR_")]
        assert len(aq) == 9, (fq, aq)
        assert not any("AQR" in c.upper() for c in src.columns if c not in aq), "มีชื่อ AQR นอกคำนำหน้า AQR_"
        keep = [c for c in src.columns if not c.startswith("AQR_")]
        new = src[keep].copy()
        assert bit_equal(new, src[keep]) and list(new.columns) == keep
        outp = os.path.join(OUT, f"factors_eo_noaqr_{fq}.parquet")
        new.to_parquet(outp)
        back = pd.read_parquet(outp)
        assert bit_equal(back, src[keep]), f"อ่านกลับไม่ตรงต้นฉบับ ({fq})"           # ทุกคอลัมน์ที่เหลือเท่าต้นฉบับทุกบิต
        assert back.shape == (src.shape[0], src.shape[1] - 9)
        res[fq] = dict(file=REL + os.path.basename(outp), sha256=sha256(outp), rows=int(len(back)), columns=int(back.shape[1]),
                       date_min=str(back.index.min().date()), date_max=str(back.index.max().date()), dropped_columns=len(aq))
    gsrc = pd.read_csv(os.path.join(HERE, "factor_groups_eo.csv"))
    g = gsrc[~gsrc["factor"].str.startswith("AQR_")].reset_index(drop=True)
    assert len(gsrc) - len(g) == 9
    # ทุกแถวที่เหลือต้องเท่าเดิมทุกค่า
    assert gsrc[~gsrc["factor"].str.startswith("AQR_")].reset_index(drop=True).equals(g)
    # แถวกลุ่มต้องครอบคอลัมน์รายเดือนพอดี (เหมือนไฟล์เดิม: factor_groups_eo = คอลัมน์รายเดือน)
    mcols = list(pd.read_parquet(os.path.join(OUT, "factors_eo_noaqr_monthly.parquet")).columns)
    assert list(g["factor"]) == mcols, "factor_groups_eo_noaqr ไม่ตรงคอลัมน์รายเดือน"
    gp = os.path.join(OUT, "factor_groups_eo_noaqr.csv")
    g.to_csv(gp, index=False)
    assert pd.read_csv(gp).equals(g)

    # ห้ามมีสตริง AQR ในไฟล์ผลลัพธ์ใดๆ (ชื่อคอลัมน์ · metadata · ค่าใน csv)
    for fn in ("factors_eo_noaqr_weekly.parquet", "factors_eo_noaqr_monthly.parquet", "factor_groups_eo_noaqr.csv"):
        b = open(os.path.join(OUT, fn), "rb").read().lower()
        assert b"aqr" not in b, f"พบสตริง AQR ใน {fn}"

    man = dict(
        created=str(date.today()),
        script="build_eo_noaqr.py",
        script_sha256=sha256(os.path.join(HERE, "build_eo_noaqr.py")),
        pandas=pd.__version__, numpy=np.__version__, python=sys.version.split()[0],
        purpose="BRIEF 120/119(3): สำเนา factors_eo_* ไม่มีคอลัมน์ AQR_* (commit ได้) · ไฟล์เดิมคงไว้ในเครื่องให้ S012 รันซ้ำได้",
        why_separate_manifest="manifest_eo.json ถูกล็อก sha ใน lib/l1eo.py S013_PINS (281756a4…2681) · แก้แล้ว S012 รันซ้ำ (check_pins) ไม่ผ่าน → ใช้ไฟล์นี้แยก",
        inputs=[dict(file=REL + k, sha256=v) for k, v in srcs.items()] + [dict(file=REL + "manifest_eo.json", sha256=sha256(os.path.join(HERE, "manifest_eo.json")))],
        outputs=[res["weekly"], res["monthly"],
                 dict(file=REL + "factor_groups_eo_noaqr.csv", sha256=sha256(gp), rows=int(len(g)))],
        checks=dict(remaining_columns_bit_equal_to_source=True, aqr_string_absent_in_outputs=True,
                    weekly_columns=f"{res['weekly']['columns'] + 9} → {res['weekly']['columns']}",
                    monthly_columns=f"{res['monthly']['columns'] + 9} → {res['monthly']['columns']}"),
    )
    with open(os.path.join(OUT, "manifest_eo_noaqr.json"), "w", encoding="utf-8") as f:
        json.dump(man, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print(json.dumps({k: man[k] for k in ("outputs", "checks")}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
