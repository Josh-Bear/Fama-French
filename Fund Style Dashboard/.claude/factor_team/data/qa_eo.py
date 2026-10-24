"""qa_eo.py — ตรวจซ้ำผลของ build_eo.py (รันซ้ำได้ · ไม่แก้ไฟล์ข้อมูล · ไม่ดาวน์โหลด)

รัน:  cd "<root>" && PYTHONDONTWRITEBYTECODE=1 ./.venv/bin/python -I -B .claude/factor_team/data/qa_eo.py [--dir DIR] [--repro]
- ค่าเริ่มต้นตรวจไฟล์ใน data/ · `--dir DIR` ตรวจไฟล์ในโฟลเดอร์อื่น
- `--repro` = รัน build_eo.py ซ้ำไปที่ scratch/factor-data-engineer_eo_rerun แล้วเทียบ sha256 ทุกไฟล์ผลลัพธ์ → เขียน repro_check_eo.json (เฉพาะเมื่อไม่ได้ใช้ --dir)
ตรวจ (ทุกข้อต้องผ่าน · ออกด้วยรหัส 1 ถ้าไม่ผ่าน):
  1 จุดวันที่ตรงกับ factors_weekly/monthly เดิม · ไม่มีชื่อซ้ำ · ไม่มี inf · ช่วงหลักไม่มี NaN
  2 ไม่มีแถว > 2025-12-31 ในส่วนที่ใช้ fit (flag แยกใน eo_row_flags.csv) · JKP เป็น NaN หลังข้อมูลจบ
  3 คำนวณใหม่แบบอื่น (รวมรายวันต่อสัปดาห์ด้วย np.prod) เทียบคอลัมน์ตัวอย่างจากไฟล์ดิบ
  4 AUM_fam / อายุ family คำนวณใหม่ด้วยโค้ดอีกชุด (อ่าน nav_history_db.csv ใหม่) · ใช้แถว NAVDate ≤ 2023-12-31 เท่านั้น
  5 ไม่มีกอง F ใน U · U ⊂ included · นิยาม pass_aum / pass_age / in_U ตรงตามข้อ 109 · O ทอง/REIT ตรงกฎชื่อ
  6 ไฟล์ L0 เดิม (manifest.json / manifest_ext.json) sha256 ไม่เปลี่ยน · ไฟล์ต้นฉบับใน raw_eo/ ตรงกับ sha256 ใน NOTES.md และ manifest_eo.json
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys

sys.dont_write_bytecode = True

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
_argv = list(sys.argv)
sys.argv = [_argv[0]]            # build_eo อ่าน --out จาก argv ตอน import — ไม่ส่งต่อ
import build_eo as B  # noqa: E402

sys.argv = _argv
L0, config = B.L0, B.config
DIR = HERE
for i, a in enumerate(_argv):
    if a == "--dir":
        DIR = os.path.abspath(_argv[i + 1])
REPRO = "--repro" in _argv

RES: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    RES.append((name, bool(ok), detail))
    print(("PASS " if ok else "FAIL ") + name + (f" — {detail}" if detail else ""))


def sha(path: str) -> str:
    return L0.sha256(path)


def main() -> int:
    Fw = pd.read_parquet(os.path.join(DIR, "factors_eo_weekly.parquet"))
    Fm = pd.read_parquet(os.path.join(DIR, "factors_eo_monthly.parquet"))
    aum = pd.read_parquet(os.path.join(DIR, "aum_fam.parquet"))
    fg = pd.read_csv(os.path.join(DIR, "factor_groups_eo.csv"))
    fl = pd.read_csv(os.path.join(DIR, "eo_row_flags.csv"), parse_dates=["date"])
    man = json.load(open(os.path.join(DIR, "manifest_eo.json"), encoding="utf-8"))
    f0w = pd.read_parquet(os.path.join(HERE, "factors_weekly.parquet"))
    f0m = pd.read_parquet(os.path.join(HERE, "factors_monthly.parquet"))
    e0w = pd.read_parquet(os.path.join(HERE, "factors_ext_weekly.parquet"))
    uni = pd.read_csv(os.path.join(HERE, "universe.csv"), parse_dates=["first", "last", "nav_first", "nav_last"])
    mw, mm = B.main_mask(Fw.index), B.main_mask(Fm.index)

    # ---------------------------------------------------------------- 1 โครงสร้าง
    check("1.1 index weekly ตรง factors_weekly เดิม", Fw.index.equals(f0w.index) and Fw.index.name == "date")
    check("1.2 index monthly ตรง factors_monthly เดิม", Fm.index.equals(f0m.index))
    check("1.3 ชื่อคอลัมน์ไม่ซ้ำและไม่ชนกับ L0 / ext", not Fm.columns.duplicated().any() and not (set(Fm.columns) & (set(f0w.columns) | set(e0w.columns))))
    check("1.4 คอลัมน์ weekly = คอลัมน์ monthly ที่ไม่ใช่ KFM_*", list(Fw.columns) == [c for c in Fm.columns if not c.startswith("KFM_")])
    check("1.5 factor_groups_eo.csv ครอบทุกคอลัมน์ monthly ไม่ซ้ำ", list(fg["factor"]) == list(Fm.columns))
    check("1.6 ไม่มี inf", not np.isinf(Fw.to_numpy(float)).any() and not np.isinf(Fm.to_numpy(float)).any())
    check("1.7 ช่วงหลักไม่มี NaN (weekly + monthly ทุกคอลัมน์)", not Fw.loc[mw].isna().any().any() and not Fm.loc[mm].isna().any().any(),
          f"weekly main {int(mw.sum())} แถว · monthly main {int(mm.sum())} แถว")
    check("1.8 manifest_eo: จำนวนคอลัมน์ตรงไฟล์", man["counts"]["weekly_cols"] == Fw.shape[1] and man["counts"]["monthly_cols"] == Fm.shape[1])
    ls_cols = fg[fg["kind"].isin(["daily_ls_compound", "monthly_native"])]
    check("1.9 factor long–short ทุกตัวติดป้าย 'ลงทุนไม่ได้' หรือเป็นตลาด/rf อ้างอิง และเป็น USD ไม่แปลงบาท",
          ls_cols["investable"].str.contains("ไม่ได้|rf").all() and ls_cols["currency"].str.contains("ไม่แปลงบาท").all())

    # ---------------------------------------------------------------- 2 ไม่มีแถวหลัง fit ในส่วน fit
    for freq, F in (("weekly", Fw), ("monthly", Fm)):
        f = fl[fl["freq"] == freq].set_index("date")
        check(f"2.{1 if freq == 'weekly' else 2} flag ครบทุกแถว ({freq}) และตรงกับ index", f.index.equals(F.index))
        fit_idx = f.index[f["main_period_fit_ok"]]
        check(f"2.{3 if freq == 'weekly' else 4} ส่วน fit ({freq}) ไม่มีวันที่ > 2025-12-31 และ > 2021-01-01",
              (fit_idx.max() <= L0.MAIN_END) and (fit_idx.min() > L0.MAIN_START), f"{fit_idx.min():%Y-%m-%d} … {fit_idx.max():%Y-%m-%d} ({len(fit_idx)} แถว)")
        post = f.index[f["display_only_post_2025"]]
        check(f"2.{5 if freq == 'weekly' else 6} แถวหลัง 2025-12-31 ({freq}) ถูก flag ดูประกอบทั้งหมด และไม่ทับกับส่วน fit",
              (post > L0.MAIN_END).all() and len(post) + len(fit_idx) == len(f) - int((f.index <= L0.MAIN_START).sum()),
              f"{len(post)} แถวดูประกอบ")
        jk = [c for c in F.columns if c.startswith("JKP_")]
        check(f"2.{7 if freq == 'weekly' else 8} JKP ({freq}) เป็น NaN ทุกแถวหลัง 2025-12-31 (ข้อมูลจบ 2025-12-31)", F.loc[F.index > pd.Timestamp("2025-12-31"), jk].isna().all().all())
    fit = Fw.loc[fl[(fl["freq"] == "weekly") & fl["main_period_fit_ok"]]["date"]]
    check("2.9 ส่วน fit ที่ใช้ (weekly) ทั้งก้อนไม่มีวันที่หลัง 2025-12-31", fit.index.max() <= pd.Timestamp("2025-12-31"))

    # ---------------------------------------------------------------- 3 คำนวณใหม่แบบอื่น
    kf = B.load_kf_daily()
    jkp = B.load_jkp()
    aq, _ = B.read_aqr(os.path.join(B.RAW, B.AQR_FILES["AQR_BAB"][0]), B.AQR_FILES["AQR_BAB"][1], B.AQR_SERIES)
    wk, me = pd.date_range("2021-01-01", L0.PANEL_END, freq="W-FRI"), pd.DatetimeIndex([pd.Timestamp("2020-12-31")] + list(pd.date_range("2021-01-31", L0.PANEL_END, freq="ME")))

    def loop_compound(r: pd.Series, anchors: pd.DatetimeIndex) -> np.ndarray:
        r = r.dropna()
        out = []
        for a0, a1 in zip(anchors[:-1], anchors[1:]):
            if a1 > r.index.max():
                out.append(np.nan)
                continue
            sub = r[(r.index > a0) & (r.index <= a1)]
            out.append(float(np.prod(1.0 + sub.to_numpy()) - 1.0))
        return np.array(out)

    samples = [("KF_DEV_SMB", kf["KF_DEV"]["SMB"]), ("KF_JP_WML", kf["KF_JP"]["WML"]), ("KF_EU_HML", kf["KF_EU"]["HML"]),
               ("JKP_EM_value", jkp["JKP_EM"]["value"]), ("JKP_DEV_quality", jkp["JKP_DEV"]["quality"]), ("AQR_BAB_GLOBAL", aq["GLOBAL"])]
    for nm, r in samples:
        a = Fw[nm].to_numpy(float)
        b = loop_compound(r, wk)
        d = np.nanmax(np.abs(a - b))
        same_nan = bool((np.isnan(a) == np.isnan(b)).all())
        check(f"3.1 {nm} weekly ตรงกับการทบต้นรายช่วงแบบ np.prod", same_nan and d < 1e-11, f"max|ต่าง| {d:.2e}")
        a = Fm[nm].to_numpy(float)
        b = loop_compound(r, me)
        d = np.nanmax(np.abs(a - b))
        check(f"3.2 {nm} monthly ตรงกับการทบต้นรายช่วงแบบ np.prod", bool((np.isnan(a) == np.isnan(b)).all()) and d < 1e-11, f"max|ต่าง| {d:.2e}")
    # ราคา ETF: คำนวณใหม่ด้วย Series.asof (ต่างจาก asof_series เดิม)
    alt, _ = B.load_yahoo("EO_ALT_ETF.csv")
    mac = pd.read_csv(config.MACRO_FACTOR_CSV, parse_dates=["Date"]).set_index("Date").sort_index()
    gld = alt["GLD"].dropna()
    fxs = mac["USDTHB"].dropna()
    lv = np.array([gld.asof(a) * fxs.asof(a) for a in wk])
    chk = lv[1:] / lv[:-1] - 1.0
    check("3.3 GLD_THB ตรงกับการคำนวณใหม่ด้วย Series.asof (≤ anchor)", np.nanmax(np.abs(chk - Fw["GLD_THB"].to_numpy(float))) < 1e-12)
    fr = pd.read_csv(os.path.join(B.EXT, "US_DOLLAR_REALRATE_FRED.csv"), parse_dates=["Date"]).set_index("Date").sort_index()["DFII10"].dropna()
    lv = np.array([fr.asof(a) for a in wk])
    check("3.4 DFII10_d / DFII10_lvl ตรงกับการคำนวณใหม่", np.nanmax(np.abs((lv[1:] - lv[:-1]) - Fw["DFII10_d"].to_numpy(float))) < 1e-12 and
          np.nanmax(np.abs(lv[1:] - Fw["DFII10_lvl"].to_numpy(float))) < 1e-12)
    # KF หน่วย: สัดส่วน (÷100) — ค่าสัปดาห์สูงสุดต้องไม่เกิน 0.5 (ถ้ายังเป็น % จะเกิน 1)
    check("3.5 หน่วย factor long–short เป็นสัดส่วน (|ผลตอบแทนรายสัปดาห์| < 0.5)", Fw[[c for c in Fw.columns if c.startswith(("KF_", "JKP_", "AQR_"))]].abs().max().max() < 0.5)

    # ---------------------------------------------------------------- 4 AUM_fam (โค้ดอีกชุด)
    c = config
    prof = L0.fund_profile.load_fund_profile()
    prof["code"] = prof[c.FUND_CODE_COL].astype(str).str.strip()
    reg = pd.to_datetime(prof["Registration_date"].fillna("").astype(str).str.strip(), format="%Y%m%d", errors="coerce")
    reg = pd.Series(reg.to_numpy(), index=prof["code"]).groupby(level=0).first()
    grp = pd.read_csv(os.path.join(B.BD, "share_class_groups.csv"), encoding="utf-8-sig")
    groups = dict(zip(grp["FundCode"].str.strip(), grp["group"].str.strip()))
    t = B.AUM_ASOF
    lo = t - pd.Timedelta(days=90)
    first, parts = {}, []
    for ch in pd.read_csv(c.NAV_HISTORY_CSV, usecols=c.NAV_USECOLS, dtype={c.NAV_FUND_CODE_COL: str}, chunksize=c.NAV_CHUNKSIZE):
        ch = ch.rename(columns={c.NAV_FUND_CODE_COL: "code", c.NAV_DATE_COL: "d", c.NAV_COL: "nav", c.NAV_AUM_COL: "aum", c.NAV_UPDATE_COL: "upd"})
        ch["code"] = ch["code"].str.strip()
        ch["d"] = pd.to_datetime(ch["d"], errors="coerce")
        ch["nav"] = pd.to_numeric(ch["nav"], errors="coerce")
        ch["aum"] = pd.to_numeric(ch["aum"], errors="coerce")
        ch = ch[(ch["nav"] > 0) & ch["d"].notna()]
        for k, v in ch.groupby("code")["d"].min().items():
            first[k] = min(first.get(k, v), v)
        parts.append(ch[(ch["d"] <= t) & (ch["d"] >= lo)])
    w = pd.concat(parts)
    w["u"] = L0.nav_loader.parse_update_time(w["upd"])
    w = w.sort_values(["code", "d", "u"], na_position="first", kind="stable").groupby(["code", "d"], as_index=False).last()
    check("4.1 แถวที่ใช้คำนวณ AUM มี NAVDate ≤ 2023-12-31 ทุกแถว", w["d"].max() <= t, f"max NAVDate ที่ใช้ {w['d'].max():%Y-%m-%d}")
    w = w[w["aum"] > 0].sort_values(["code", "d"]).groupby("code").last()
    allc = sorted(set(first) | set(prof["code"]))
    fam = {k: L0.family_of(k, groups, True) for k in allc}
    cdf = pd.DataFrame({"code": allc})
    cdf["family"] = cdf["code"].map(fam)
    cdf["aum"] = cdf["code"].map(w["aum"]).fillna(0.0)
    cdf["fn"] = cdf["code"].map(pd.Series(first))
    cdf["rg"] = cdf["code"].map(reg)
    cdf["fc"] = pd.concat([cdf["rg"].where(cdf["rg"] <= B.AGE_ASOF), cdf["fn"].where(cdf["fn"] <= B.AGE_ASOF)], axis=1).min(axis=1)
    g = cdf.groupby("family").agg(aum=("aum", "sum"), fc=("fc", "min"))
    a2 = aum.set_index("family")
    d_aum = (g["aum"].reindex(a2.index) - a2["aum_fam_2023"]).abs().max()
    check("4.2 AUM_fam ตรงกับการคำนวณใหม่ทุก family (โค้ดอีกชุด)", d_aum < 1e-6, f"{len(a2)} family · max|ต่าง| {d_aum:.2e}")
    d_age = ((B.AGE_ASOF - g["fc"].reindex(a2.index)).dt.days - a2["age_days_2025"]).abs().max()
    check("4.3 อายุ family ตรงกับการคำนวณใหม่ทุก family", d_age == 0 or np.isnan(d_age), f"max|ต่าง| {d_age}")
    check("4.4 pass_aum = (AUM_fam ≥ 100 ล้านบาท) และ pass_age = (อายุ ≥ 730 วัน)",
          (aum["pass_aum"] == (aum["aum_fam_2023"] >= 1e8)).all() and (aum["pass_age"] == (aum["age_days_2025"] >= 730)).all())

    # ---------------------------------------------------------------- 5 U
    pol = uni.drop_duplicates("family").set_index("family")["policy"]
    rep = uni[uni["included"]].set_index("family")
    check("5.1 ไม่มีกอง F ใน U", not (aum["in_U"] & (aum["policy"] == "F")).any() and set(aum.loc[aum["in_U"], "policy"]) <= {"E", "O"})
    check("5.2 U ⊂ included (ตัวแทน family ใน panel L0 เดิม) และ FundCode ตรงตัวแทน",
          aum.loc[aum["in_U"], "included"].all() and (aum.loc[aum["in_U"], "FundCode"].values == rep["FundCode"].reindex(aum.loc[aum["in_U"], "family"]).values).all())
    check("5.3 in_U = included & policy ∈ {E,O} & pass_aum & pass_age", (aum["in_U"] == (aum["included"] & aum["policy"].isin(["E", "O"]) & aum["pass_aum"] & aum["pass_age"])).all())
    check("5.4 policy ตรง universe.csv ของตัวแทน", (aum.loc[aum["included"], "policy"].values == rep["policy"].reindex(aum.loc[aum["included"], "family"]).values).all())
    ue = int(((aum["policy"] == "E") & aum["in_U"]).sum())
    uo = int(((aum["policy"] == "O") & aum["in_U"]).sum())
    check("5.5 U_E / U_O ตรง manifest_eo", ue == man["counts"]["U_E"] and uo == man["counts"]["U_O"], f"U_E={ue} U_O={uo}")
    prof_n = prof.drop_duplicates("code").set_index("code")
    gold_ok = True
    try:
        sys.path.insert(0, os.path.join(L0.ROOT, ".claude", "factor_team", "lib"))
        import p2  # noqa: WPS433  (โค้ดของทีม lib/p2.py · อ่านอย่างเดียว)
        o = aum[(aum["policy"] == "O") & aum["included"]]
        for r in o.itertuples():
            nth = prof_n["Fund Name TH"].get(r.FundCode)
            if p2.is_gold(r.name_en, nth) != (r.o_kind == "gold"):
                gold_ok = False
        check("5.6 o_kind ทองตรงกับ lib/p2.is_gold (ทั้ง 27 family O)", gold_ok, "ใช้ p2.is_gold จริง")
    except Exception as e:  # noqa: BLE001
        check("5.6 o_kind ทองตรงกับกฎ is_gold (import lib.p2 ไม่ได้ → ตรวจด้วย regex สำเนา)", all(
            B.is_gold(r.name_en, prof_n["Fund Name TH"].get(r.FundCode)) == (r.o_kind == "gold") for r in aum[(aum["policy"] == "O") & aum["included"]].itertuples()), repr(e)[:80])
    check("5.7 ไม่มี O ที่จัดเป็น 'other' (ทั้งหมดเป็นทองหรือ REIT/อสังหา)", not (aum.loc[(aum["policy"] == "O") & aum["included"], "o_kind"] == "other").any())

    # ---------------------------------------------------------------- 6 ไฟล์เดิม / ต้นฉบับไม่เปลี่ยน
    bad = [x for x in B.check_untouched() if not x["match"]]
    check("6.1 ไฟล์ L0 เดิมตาม manifest.json + manifest_ext.json ไม่เปลี่ยน (sha256)", not bad, str([b["file"] for b in bad]))
    notes = open(os.path.join(B.EXT, "NOTES.md"), encoding="utf-8").read()
    want = dict(re.findall(r"`(raw_eo/[^`]+)`[^|]*\|[^|]*\|\s*\d+\s*\|\s*`([0-9a-f]{64})`", notes))
    want.update({k: v for k, v in re.findall(r"`((?:EO_ALT_ETF|US_DOLLAR_REALRATE_FRED|ASIA_REIT_LOCAL)\.csv)`[^|]*\|[^|]*\|\s*\d+\s*\|\s*`([0-9a-f]{64})`", notes)})
    mism = [k for k, v in want.items() if sha(os.path.join(B.EXT, k)) != v]
    check("6.2 ไฟล์ต้นฉบับที่ดาวน์โหลด (raw_eo/* + 3 CSV) ตรง sha256 ใน NOTES.md", len(want) == 20 and not mism, f"ตรวจ {len(want)} ไฟล์ · ไม่ตรง {mism}")
    mi = {os.path.relpath(os.path.join(L0.ROOT, x["file"]), B.EXT): x["sha256"] for x in man["inputs"] if "external" in x["file"]}
    mism2 = [k for k, v in mi.items() if sha(os.path.join(B.EXT, k)) != v]
    check("6.3 sha256 ของ input ใน manifest_eo.json ตรงไฟล์ปัจจุบัน", not mism2, f"{len(mi)} ไฟล์")
    outm = [x for x in man["outputs"] if os.path.exists(os.path.join(L0.ROOT, x["file"]))]
    mism3 = [x["file"] for x in outm if sha(os.path.join(L0.ROOT, x["file"])) != x["sha256"]] if DIR == HERE else []
    check("6.4 sha256 ของ output ใน manifest_eo.json ตรงไฟล์ปัจจุบัน", not mism3, str(mism3))

    # ---------------------------------------------------------------- repro
    if REPRO and DIR == HERE:
        rr = os.path.join(L0.ROOT, ".claude", "factor_team", "scratch", "factor-data-engineer_eo_rerun")
        os.makedirs(rr, exist_ok=True)
        cmd = [sys.executable, "-I", "-B", os.path.join(HERE, "build_eo.py"), "--out", rr]
        subprocess.run(cmd, check=True, cwd=L0.ROOT, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}, capture_output=True)
        files = ("factors_eo_weekly.parquet", "factors_eo_monthly.parquet", "aum_fam.parquet", "factor_groups_eo.csv", "eo_row_flags.csv", "QA_EO.md")
        rep_ = {f: {"run1": sha(os.path.join(HERE, f)), "run2": sha(os.path.join(rr, f))} for f in files}
        for f in files:
            rep_[f]["identical"] = rep_[f]["run1"] == rep_[f]["run2"]
        m1 = json.load(open(os.path.join(HERE, "manifest_eo.json"), encoding="utf-8"))
        m2 = json.load(open(os.path.join(rr, "manifest_eo.json"), encoding="utf-8"))
        for m_ in (m1, m2):
            m_.pop("created", None)
            for x in m_["outputs"]:
                x["file"] = os.path.basename(x["file"])
        rep_["manifest_eo.json (ไม่นับ created)"] = {"identical": m1 == m2}
        ok = all(v["identical"] for v in rep_.values())
        json.dump({"checked": "sha256 ผลจาก build_eo.py 2 รอบ (รอบ 2 เขียนที่ scratch/factor-data-engineer_eo_rerun) · อ่าน nav_history_db.csv + ไฟล์ดิบใหม่ทั้งสองรอบ",
                   "all_identical": ok, "files": rep_}, open(os.path.join(HERE, "repro_check_eo.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        check("7.1 รัน build_eo.py ซ้ำ 2 รอบ ได้ไฟล์ตรงทุกบิต (repro_check_eo.json)", ok, ", ".join(k for k, v in rep_.items() if not v["identical"]) or "ทุกไฟล์ตรง")

    n_fail = sum(1 for _, ok, _ in RES if not ok)
    print(f"\nสรุป: ผ่าน {len(RES) - n_fail} / {len(RES)} · ไม่ผ่าน {n_fail}")
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
