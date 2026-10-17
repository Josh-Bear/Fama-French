"""io_l1 — โหลดข้อมูล L0 + ตรวจ sha256 (S003 = S002 + addendum)."""
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
TEAM = ROOT / ".claude" / "factor_team"
DATA = TEAM / "data"
LIB = TEAM / "lib"

MAIN_START = "2021-01-08"
MAIN_END = "2025-12-26"
MONTH_START = "2021-01-31"
MONTH_END = "2025-12-31"
FORBIDDEN_PATTERNS = ("_late_", "_lvl", "_est_ret")

_D = ".claude/factor_team/data/"
SPEC_SHA = {
    _D + "panel_weekly.parquet": "95c16ee651d3a936788b7cb3c6372bbf5f1e84cb39daf5680343771dca24270b",
    _D + "panel_monthly.parquet": "e8e8cb5d5f04fba9bb35558ef7c3d8195c656334119e56f82775cc1ae21ccaed",
    _D + "factors_weekly.parquet": "115b87139d2bec0fd57a77a1593c46d36bb23f3f35f83236cdb07be642af47a8",
    _D + "factors_monthly.parquet": "f7c4248b4fa889853024449e72ae8909cf1f8d3226a54eebc37448a2a485bb72",
    _D + "aum_weekly.parquet": "48c34c73ae22ebffc6112f93e03f729223a496297bb65c324b693b817a723d26",
    _D + "universe.csv": "fdfb7830df78ce032465ac9d8cddc2c98f9aa86cfa0f3925fdb83026aa3f7252",
    _D + "dup_pairs.csv": "b1f0f0c745947fa70803a4f40526c0a1967c72925be985a2bedc1057d8b8aef3",
    _D + "factor_groups.csv": "42bf1cfb270721ae6112799ab795ebc4c91212e7584d5cdfee23b9b70b1b1731",
}


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_manifest(paths=None, root=ROOT, manifest_path=None, expected=None):
    """ตรวจ sha256 ของไฟล์ (path สัมพัทธ์กับ root) กับ manifest และ expected (spec) — ไม่ตรง = raise"""
    manifest = json.load(open(manifest_path or (DATA / "manifest.json")))
    entries = {e["file"]: e["sha256"] for e in manifest["inputs"] + manifest["outputs"] if "sha256" in e}
    if paths is None:
        paths = list(SPEC_SHA)
    if expected is None and manifest_path is None:
        expected = SPEC_SHA
    out = {}
    for rel in paths:
        actual = sha256_file(Path(root) / rel)
        if rel not in entries:
            raise ValueError(f"ไม่มีใน manifest: {rel}")
        if actual != entries[rel]:
            raise ValueError(f"sha256 ไม่ตรง manifest: {rel}")
        if expected and rel in expected and actual != expected[rel]:
            raise ValueError(f"sha256 ไม่ตรง spec: {rel}")
        out[rel] = actual
    return out


def lib_hash(lib_dir=None):
    d = Path(lib_dir) if lib_dir else LIB
    return {p.name: sha256_file(p) for p in sorted(d.glob("*.py"))}


def load_universe():
    return pd.read_csv(DATA / "universe.csv")


def load_dup_pairs():
    return pd.read_csv(DATA / "dup_pairs.csv")


def _clean_factor_cols(df):
    keep = [c for c in df.columns if not any(p in c for p in FORBIDDEN_PATTERNS)]
    return df[keep]


def load_factors(freq="W"):
    """factor inputs ช่วงหลัก (ตัดคอลัมน์ *_late_* / *_lvl / *_est_ret และข้อมูล 2026)"""
    if freq == "W":
        F = pd.read_parquet(DATA / "factors_weekly.parquet")
        return _clean_factor_cols(F.loc[MAIN_START:MAIN_END]).copy()
    F = pd.read_parquet(DATA / "factors_monthly.parquet")
    return _clean_factor_cols(F.loc[MONTH_START:MONTH_END]).copy()


def load_returns(freq="W"):
    """ผลตอบแทนส่วนเกิน (ret - RF_BOT) wide (date x FundCode) ช่วงหลัก"""
    if freq == "W":
        P = pd.read_parquet(DATA / "panel_weekly.parquet")
        rf = pd.read_parquet(DATA / "factors_weekly.parquet")["RF_BOT"]
        s, e = MAIN_START, MAIN_END
    else:
        P = pd.read_parquet(DATA / "panel_monthly.parquet")
        rf = pd.read_parquet(DATA / "factors_monthly.parquet")["RF_BOT"]
        s, e = MONTH_START, MONTH_END
    W = P.pivot(index="date", columns="FundCode", values="ret").sort_index()
    W = W.loc[s:e]
    W = W.sub(rf.loc[W.index], axis=0)
    W.columns.name = None
    return W


def load_aum():
    A = pd.read_parquet(DATA / "aum_weekly.parquet")
    W = A.pivot(index="date", columns="FundCode", values="aum").sort_index()
    W.columns.name = None
    return W
