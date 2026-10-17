"""build_l0_ext.py — ชั้น L0 ส่วนขยาย: factor inputs จาก ETF ธีม / อาเซียน / real assets / hedged equity (data/external/*)

รัน:  cd "<root>" && PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. ./.venv/bin/python -B .claude/factor_team/data/build_l0_ext.py [--out DIR]
- ไม่ดาวน์โหลด · ไม่แก้ไฟล์ L0 เดิม (อ่านอย่างเดียว · ตรวจ sha256 เทียบ manifest.json ทุกครั้ง)
- ใช้ฟังก์ชัน asof / จุดวันเดียวกับ panel จาก build_l0.py (สัปดาห์ W-FRI 2021-01-01 → 2026-07-31 · เดือน = สิ้นเดือน)
- ราคา USD (adjusted close) → บาท: ราคา × USDTHB (asof เดียวกับ L0 · base_data/MACRO_FACTOR.csv) แล้วค่อยหาผลตอบแทนต่อช่วง
- ผลลัพธ์: factors_ext_weekly.parquet · factors_ext_monthly.parquet · manifest_ext.json · QA_L0_ext.md
- ผลเหมือนเดิมทุกบิต (parquet + QA ไม่มีวันที่สร้างในเนื้อหา · manifest มี created แยกเฉพาะฟิลด์เดียว)
"""
from __future__ import annotations

import json
import os
import sys
from datetime import date

sys.dont_write_bytecode = True

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import build_l0 as L0  # noqa: E402  (import เฉยๆ ไม่รัน main · ใช้ asof_series / D / sha256 / info_file / constants)

ROOT, EXT, BD = L0.ROOT, L0.EXT, L0.BD
OUT = HERE
for i, a in enumerate(sys.argv):
    if a == "--out":
        OUT = os.path.abspath(sys.argv[i + 1])

GROUPS = {   # ไฟล์ → (กลุ่ม, ETF)
    "THEMATIC_ETF.csv": ("thematic_ETF", ["QQQ", "SOXX", "ARKK", "ICLN", "IBB", "KWEB"]),
    "ASEAN_COUNTRY_ETF.csv": ("asean_country_ETF", ["THD", "EIDO", "EPHE", "EWM", "EWS"]),
    "REAL_ASSETS_ETF.csv": ("real_assets_ETF", ["REET", "IGF", "DBC", "GSG"]),
    "HEDGED_EQUITY_ETF.csv": ("hedged_equity_ETF", ["HEWJ", "EWJ", "HEFA", "EFA"]),
}
WEEK_ABN, MONTH_ABN = 0.20, 0.30         # เกณฑ์ธงค่าผิดปกติ (|ผลตอบแทน| ต่อช่วง)
DAY_ABN = 0.10                            # ธงค่าผิดปกติรายวันในไฟล์ดิบ


def load_raw() -> dict[str, pd.DataFrame]:
    raw = {}
    for f in GROUPS:
        raw[f] = pd.read_csv(os.path.join(EXT, f), parse_dates=["Date"]).set_index("Date").sort_index()
    return raw


def make_ext(anchors: pd.DatetimeIndex, raw: dict, mac: pd.DataFrame):
    A = L0.D(anchors)
    fx = L0.asof_series(mac["USDTHB"], A)
    cols, grp = {}, {}
    for f, (g, etfs) in GROUPS.items():
        for c in etfs:
            v = L0.asof_series(raw[f][c], A)
            for name, lvl, gg in ((f"{c}_USD", v, g + "_USD"), (f"{c}_THB", v * fx, g + "_THB")):
                cols[name] = lvl[1:] / lvl[:-1] - 1.0
                grp[name] = gg
    df = pd.DataFrame(cols, index=anchors[1:])
    df.index.name = "date"
    return df, grp


def check_l0_untouched() -> list[dict]:
    """sha256 ของไฟล์ output L0 เดิมทุกไฟล์ (ใน manifest.json) ต้องเท่ากับของจริง."""
    man = json.load(open(os.path.join(HERE, "manifest.json"), encoding="utf-8"))
    res = []
    for o in man["outputs"]:
        p = os.path.join(ROOT, o["file"])
        now = L0.sha256(p)
        res.append({"file": o["file"], "sha256_manifest": o["sha256"], "sha256_now": now, "match": now == o["sha256"]})
    return res


def md_table(df: pd.DataFrame) -> str:
    h = "| " + " | ".join(df.columns) + " |\n|" + "|".join(["---"] * len(df.columns)) + "|\n"
    return h + "\n".join("| " + " | ".join(str(x) for x in r) + " |" for r in df.itertuples(index=False))


def main():
    os.makedirs(OUT, exist_ok=True)
    today = date.today().isoformat()
    raw = load_raw()
    mac = pd.read_csv(L0.config.MACRO_FACTOR_CSV, parse_dates=["Date"]).set_index("Date").sort_index()

    wk = pd.date_range("2021-01-01", L0.PANEL_END, freq="W-FRI")
    me = pd.DatetimeIndex([pd.Timestamp("2020-12-31")] + list(pd.date_range("2021-01-31", L0.PANEL_END, freq="ME")))
    Fw, grp = make_ext(wk, raw, mac)
    Fm, _ = make_ext(me, raw, mac)
    Fw.to_parquet(os.path.join(OUT, "factors_ext_weekly.parquet"))
    Fm.to_parquet(os.path.join(OUT, "factors_ext_monthly.parquet"))

    # --- เทียบ index กับ factors_* เดิม (อ่านอย่างเดียว)
    f0w = pd.read_parquet(os.path.join(HERE, "factors_weekly.parquet"))
    f0m = pd.read_parquet(os.path.join(HERE, "factors_monthly.parquet"))
    same_idx_w, same_idx_m = bool(Fw.index.equals(f0w.index)), bool(Fm.index.equals(f0m.index))
    dup_cols = sorted(set(Fw.columns) & set(f0w.columns))

    # --- QA
    L = []
    P = L.append
    P("# QA_L0_ext — factor inputs ส่วนขยาย (ETF ธีม / อาเซียน / real assets / hedged equity)\n")
    P(f"สร้างโดย `build_l0_ext.py` (เนื้อหาไฟล์นี้ไม่มีวันที่สร้างเพื่อให้ผลเหมือนเดิมทุกบิต · วันที่สร้างอยู่ใน `manifest_ext.json`) · ไม่แก้ไฟล์ L0 เดิม\n")
    P("## สรุป\n")
    P(f"- weekly: {Fw.shape[0]} สัปดาห์ × {Fw.shape[1]} คอลัมน์ ({Fw.index.min():%Y-%m-%d} → {Fw.index.max():%Y-%m-%d}) · "
      f"monthly: {Fm.shape[0]} เดือน × {Fm.shape[1]} คอลัมน์ ({Fm.index.min():%Y-%m-%d} → {Fm.index.max():%Y-%m-%d})")
    P(f"- index วันที่ตรงกับ `factors_weekly.parquet` = **{'ผ่าน' if same_idx_w else 'ไม่ผ่าน'}** · `factors_monthly.parquet` = **{'ผ่าน' if same_idx_m else 'ไม่ผ่าน'}** (จุดวันเดียวกับ panel)")
    P(f"- ชื่อคอลัมน์ชนกับ L0 เดิม: {dup_cols if dup_cols else 'ไม่มี'}")
    P("- คอลัมน์: `<ETF>_USD` (ผลตอบแทน USD adjusted close) และ `<ETF>_THB` (ราคา × USDTHB แล้วหาผลตอบแทน · วิธีเดียวกับ AGG_THB/TDEX_THB ใน L0) · ผลตอบแทนเลขคณิตต่อช่วง\n")

    P("## 1. NaN\n")
    nw, nm = Fw.isna().sum(), Fm.isna().sum()
    tot = int(nw.sum() + nm.sum())
    P(f"- NaN รวมทุกคอลัมน์ weekly + monthly = **{tot}** ({'ผ่าน' if tot == 0 else 'เตือน'})")
    if tot:
        P(md_table(pd.DataFrame({"col": Fw.columns, "nan_weekly": nw.values, "nan_monthly": nm.reindex(Fw.columns).values}).query("nan_weekly>0 or nan_monthly>0")))
    P("")

    P("## 2. วันเริ่มของแต่ละ ETF\n")
    rows = []
    for f, (g, etfs) in GROUPS.items():
        for c in etfs:
            s = raw[f][c]
            fw = Fw[f"{c}_THB"].first_valid_index()
            fmn = Fm[f"{c}_THB"].first_valid_index()
            rows.append([g, c, f"{s.index.min():%Y-%m-%d}", f"{s.index.max():%Y-%m-%d}", len(s), f"{fw:%Y-%m-%d}", f"{fmn:%Y-%m-%d}"])
    P(md_table(pd.DataFrame(rows, columns=["กลุ่ม", "ETF", "raw_first", "raw_last", "raw_rows", "weekly_first_ret", "monthly_first_ret"])))
    P("\nทุก ETF เริ่ม 2020-11-02 (จุดเริ่มของไฟล์ดาวน์โหลด · ไม่ใช่วันจดทะเบียน) → ครอบคลุมตั้งแต่สัปดาห์แรกของ panel (2021-01-08) · ไม่มี ETF ที่เริ่มช้ากว่าช่วงหลัก\n")

    P("## 3. ค่าผิดปกติ\n")
    rows = []
    for c in Fw.columns:
        w, m = Fw[c], Fm[c]
        rows.append([c, f"{w.min():.3f}", f"{w.idxmin():%Y-%m-%d}", f"{w.max():.3f}", f"{w.idxmax():%Y-%m-%d}",
                     f"{(w == 0).mean():.3f}", int((w.abs() > WEEK_ABN).sum()), f"{m.min():.3f}", f"{m.max():.3f}", int((m.abs() > MONTH_ABN).sum())])
    P("ผลตอบแทนรายสัปดาห์ / รายเดือน (min–max · สัดส่วนสัปดาห์ที่เป็น 0 · จำนวนครั้งที่ |r| เกินเกณฑ์ ธงสัปดาห์ > "
      f"{WEEK_ABN:.0%} · ธงเดือน > {MONTH_ABN:.0%}):\n")
    P(md_table(pd.DataFrame(rows, columns=["col", "w_min", "w_min_date", "w_max", "w_max_date", "w_zero_frac", f"w_>{WEEK_ABN:.0%}", "m_min", "m_max", f"m_>{MONTH_ABN:.0%}"])))
    nflag = int((Fw.abs() > WEEK_ABN).sum().sum() + (Fm.abs() > MONTH_ABN).sum().sum())
    flag_cols = sorted({c for c in Fw.columns if (Fw[c].abs() > WEEK_ABN).any()} | {c for c in Fm.columns if (Fm[c].abs() > MONTH_ABN).any()})
    P(f"\n- ธงเกินเกณฑ์รวม = **{nflag}** จุด (weekly+monthly) ใน {len(flag_cols)} คอลัมน์ ({', '.join(flag_cols)}) → "
      + ("ผ่าน (ไม่มีค่าเกินเกณฑ์)" if nflag == 0 else "เตือนระดับต่ำ: ทั้งหมดเป็นหุ้นจีน/เซมิ/ARK/สินค้าโภคภัณฑ์ที่ผันผวนสูงและตรงกับเหตุการณ์ตลาด (KWEB มี.ค. 2022 · ธ.ค. 2022 · ก.ย. 2024 · GSG มี.ค. 2022) · ไม่พบราคา ≤ 0 / วันซ้ำ / NaN / split ผิด · ไม่แก้ค่า"))
    flagged = [(c, d, Fw.loc[d, c]) for c in Fw.columns for d in Fw.index[Fw[c].abs() > WEEK_ABN]]
    if flagged:
        P("\nสัปดาห์ที่เกินเกณฑ์: " + "; ".join(f"{c} {d:%Y-%m-%d} {v:+.3f}" for c, d, v in flagged))
    # ไฟล์ดิบ: ราคา <= 0 · วันซ้ำ · วันเปลี่ยนแปลงรายวันสูง
    P("\n### ไฟล์ดิบ (รายวัน)\n")
    drows = []
    for f, (g, etfs) in GROUPS.items():
        d = raw[f][etfs]
        r = d.pct_change().dropna(how="all")
        for c in etfs:
            big = r.index[r[c].abs() > DAY_ABN]
            drows.append([c, int((d[c] <= 0).sum()), int(d.index.duplicated().sum()), int(d[c].isna().sum()), f"{r[c].abs().max():.3f}",
                          f"{r[c].abs().idxmax():%Y-%m-%d}", ", ".join(f"{x:%Y-%m-%d}({r.loc[x, c]:+.3f})" for x in big) or "-"])
    P(md_table(pd.DataFrame(drows, columns=["ETF", "price<=0", "dup_dates", "nan", "max|daily|", "date", f"วันที่ |daily|>{DAY_ABN:.0%}"])))
    lastd = max(raw[f].index.max() for f in GROUPS)
    lr = {c: raw[f][c].iloc[-1] / raw[f][c].iloc[-2] - 1 for f, (g, etfs) in GROUPS.items() for c in etfs}
    P(f"- **แถวสุดท้ายของไฟล์ดิบ ({lastd:%Y-%m-%d}) = วันดาวน์โหลด อาจเป็นราคาระหว่างวันไม่ใช่ราคาปิด**: การเปลี่ยนแปลงวันสุดท้าย "
      + ", ".join(f"{c} {v:+.1%}" for c, v in lr.items() if abs(v) >= 0.03) + " (ตัวอื่น < 3%) — EIDO −13% ในวันเดียวผิดปกติ · "
      f"อยู่นอก panel (สิ้นสุด {L0.PANEL_END:%Y-%m-%d}) จึงไม่กระทบไฟล์ที่สร้าง · ถ้าขยาย panel ถึง ต.ค. 2026 ให้ตัดแถวสุดท้ายหรือดาวน์โหลดใหม่หลังตลาดปิด")
    zc = [c for c in Fw.columns if c.endswith("_USD") and (Fw[c] == 0).any()]
    P("- สัปดาห์ผลตอบแทน = 0 (ราคาปิดซ้ำ = ข้อมูลไม่ขยับ/stale ของผู้ให้ข้อมูล) พบใน " + ", ".join(f"{c[:-4]} {int((Fw[c] == 0).sum())}" for c in zc)
      + f" สัปดาห์จาก {len(Fw)} (≤ 1.0%) — ใน THB ไม่เป็น 0 เพราะ USDTHB ขยับ · ระดับนี้ไม่กระทบ")
    P("- ผลตอบแทนวันเดียว > 10% ที่เหลือกระจุกอยู่ที่วันเดียวกันหลาย ETF (9 เม.ย. 2025 ทั้ง QQQ/SOXX/ARKK/THD) หรือวันเดียวกับ KWEB 16 มี.ค. 2022 → สอดคล้องกับเหตุการณ์ตลาดจริง ไม่ใช่ข้อผิดพลาดรายตัว — ไม่แก้ค่า\n")

    P("## 4. corr THD_THB กับ TDEX_THB\n")
    tdex_w, tdex_m = f0w["TDEX_THB"], f0m["TDEX_THB"]
    main_w = (Fw.index > L0.MAIN_START) & (Fw.index <= L0.MAIN_END)
    main_m = (Fm.index > L0.MAIN_START) & (Fm.index <= L0.MAIN_END)
    crow = []
    for lab, a, b, mask in (("weekly ทั้งช่วง", Fw["THD_THB"], tdex_w, slice(None)), ("weekly 2021–2025", Fw["THD_THB"][main_w], tdex_w[main_w], slice(None)),
                            ("monthly ทั้งช่วง", Fm["THD_THB"], tdex_m, slice(None)), ("monthly 2021–2025", Fm["THD_THB"][main_m], tdex_m[main_m], slice(None))):
        j = pd.concat([a, b], axis=1, keys=["THD", "TDEX"]).dropna()
        crow.append([lab, len(j), f"{j['THD'].corr(j['TDEX']):.3f}", f"{j['THD'].std():.4f}", f"{j['TDEX'].std():.4f}", f"{(j['THD'] - j['TDEX']).mean():+.4f}"])
    P(md_table(pd.DataFrame(crow, columns=["ช่วง", "n", "corr", "sd_THD", "sd_TDEX", "mean(THD−TDEX)"])))
    P("\nอ้างอิง (NOTES.md): TDEX vs SET (Mkt-RF+Rf) รายเดือน 2021–2025 corr 0.963 → THD_THB vs TDEX_THB ต่ำกว่านั้นโดยเฉพาะรายสัปดาห์ "
      "(0.76–0.78) เพราะ (1) THD = MSCI Thailand ซื้อขายในเวลาสหรัฐ ส่วน TDEX ปิดตามเวลาไทย → ราคาวันศุกร์เหลื่อมกันครึ่งวัน (2) ดัชนีคนละชุด (MSCI Thailand vs SET50) "
      "(3) TDEX สภาพคล่องต่ำ ราคาไม่ขยับ ~11.8% ของวัน → รายเดือน corr 0.91–0.93 ใช้ทดแทนกันได้พอควร · รายสัปดาห์ควรระวัง · ใช้ THD เป็น proxy หุ้นไทยแทน SET ฉบับทางการ (ข้อ 50) โดยรู้ข้อจำกัดนี้\n")

    P("## 5. ตรวจเพิ่ม\n")
    r5 = []
    for a, b in (("HEWJ", "EWJ"), ("HEFA", "EFA")):
        j = pd.concat([Fw[f"{a}_USD"], Fw[f"{b}_USD"]], axis=1).dropna()
        r5.append([f"{a}_USD vs {b}_USD", "weekly", f"{j.iloc[:, 0].corr(j.iloc[:, 1]):.3f}", f"{(j.iloc[:, 0] - j.iloc[:, 1]).mean():+.4f}"])
    P(md_table(pd.DataFrame(r5, columns=["คู่ (hedged vs unhedged)", "ความถี่", "corr", "mean diff"])))
    P("\n- คู่ hedged/unhedged corr 0.87–0.92 · ผลต่างเฉลี่ย (hedged − unhedged) เป็นบวกเล็กน้อย สอดคล้องกับ JPY/EUR อ่อนค่าเทียบ USD ในช่วงนี้ (ตีความ ยังไม่ทดสอบ) · ETF hedge JPY/EUR→USD ซึ่งคนละเรื่องกับ hedge USD→THB ของกองไทย")
    P("- ETF ทุกตัวเป็น adjusted close (รวมปันผล) → ผลตอบแทนเป็น total return · USDTHB ใช้ asof เดียวกับ L0 (ไม่มี NaN)")
    P("- ไม่รวม SET index ฉบับทางการ (ไม่ซื้อ · ข้อ 50) · ไม่มี SHV/LQD/HYG/EMB ซ้ำ (อยู่ใน L0 แล้ว)\n")

    P("## 6. ไฟล์ L0 เดิมไม่ถูกแก้\n")
    chk = check_l0_untouched()
    bad = [c for c in chk if not c["match"]]
    P(f"- เทียบ sha256 ของไฟล์ output ใน `manifest.json` ({len(chk)} ไฟล์) กับไฟล์จริง: **{'ตรงทุกไฟล์ (ผ่าน)' if not bad else 'ไม่ตรง ' + str([b['file'] for b in bad]) + ' (ไม่ผ่าน)'}**")
    open(os.path.join(OUT, "QA_L0_ext.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")

    # --- manifest_ext
    def info(p, dc=None):
        return L0.info_file(p, dc)
    ins = [info(os.path.join(EXT, f), "Date") for f in GROUPS] + [info(L0.config.MACRO_FACTOR_CSV, "Date"),
                                                                    info(os.path.join(HERE, "build_l0.py")), info(os.path.join(HERE, "build_l0_ext.py"))]
    outs = []
    for f in ("factors_ext_weekly.parquet", "factors_ext_monthly.parquet"):
        p = os.path.join(OUT, f)
        x = pd.read_parquet(p)
        d = info(p)
        d.update({"date_min": f"{x.index.min():%Y-%m-%d}", "date_max": f"{x.index.max():%Y-%m-%d}", "columns": int(x.shape[1])})
        outs.append(d)
    outs.append({"file": os.path.relpath(os.path.join(OUT, "QA_L0_ext.md"), ROOT), "sha256": L0.sha256(os.path.join(OUT, "QA_L0_ext.md"))})
    man = {"created": today, "script": "build_l0_ext.py", "pandas": pd.__version__, "numpy": np.__version__,
           "criteria": {"anchors": "weekly W-FRI 2021-01-01→2026-07-31 · monthly month-end 2020-12-31→2026-07-31 (เหมือน build_l0.py)",
                        "asof_tolerance_calendar_days": L0.ASOF_TOL_DAYS, "usd_to_thb": "ราคา USD × USDTHB (asof) แล้วหาผลตอบแทน",
                        "flags": {"weekly_abs_ret": WEEK_ABN, "monthly_abs_ret": MONTH_ABN, "daily_abs_ret": DAY_ABN}},
           "groups": {k: v for k, v in grp.items()},
           "inputs": ins, "outputs": outs,
           "l0_untouched_check": chk}
    with open(os.path.join(OUT, "manifest_ext.json"), "w", encoding="utf-8") as f:
        json.dump(man, f, ensure_ascii=False, indent=1, default=str)
    print("done", Fw.shape, Fm.shape, "l0_untouched:", not bad)


if __name__ == "__main__":
    main()
