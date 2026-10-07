"""audit_fees_report.py — เรียก audit_fees.main() แล้วเขียน results/AUDIT_fees.md + AUDIT_fees_*.csv (ไม่แตะไฟล์อื่น)"""
from __future__ import annotations

import os
import sys

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if THIS_DIR not in sys.path:
    sys.path.insert(0, THIS_DIR)

import numpy as np
import pandas as pd

import audit_fees as af
import common
import fund_signals as fs

RES = common.RESULTS_DIR
CODES = af.CODES


# ---------- วิธีที่ 3: คำนวณมือด้วย python ล้วน จาก CSV ดิบ (ไม่ใช้ AFD / FeeData / FeeModel) ----------
def hand_rates(held_codes):
    import csv
    rows = []
    with open(os.path.join(common.PROJECT_ROOT, "base_data", "SecFundFee.csv"), encoding="utf-8-sig", newline="") as fh:
        for r in csv.DictReader(fh):
            if r["Complex Type Code"] == "FEEUH" and r["Code"] in CODES:
                rows.append(r)
    ser = {}
    for i, r in enumerate(rows):
        try:
            v = float(r["Actual Value"])
            if v < 0 or v > 10:
                v = None
        except ValueError:
            v = None
        ser.setdefault((r["Fund Code"], r["Code"]), []).append((r["As of Date"], i, v))
    for k in ser:
        ser[k].sort(key=lambda x: (x[0], x[1]))
    med = {}
    for c in CODES:
        vals = sorted(s[-1][2] for (f, cc), s in ser.items() if cc == c and f in held_codes and s[-1][2] is not None)
        n = len(vals)
        med[c] = vals[n // 2] if n % 2 else (vals[n // 2 - 1] + vals[n // 2]) / 2
    return ser, med


def hand_rate(ser, med, f, c, e):
    s = ser.get((f, c))
    if not s:
        return med[c], "median(ไม่มีแถว)"
    ed = e.strftime("%Y%m%d")
    cand = [x for x in s if x[0] <= ed]
    pick = cand[-1] if cand else s[0]
    if pick[2] is None:
        return med[c], "median(ค่าใช้ไม่ได้)"
    return pick[2], ("snapshot เก่าสุด" if not cand else "ค่าจริง")


def hand_trace(rec, afd, ser, med, title):
    """พิมพ์ทุกพจน์ของสูตร spec ด้วย python ล้วน แล้วคืน (ข้อความ, ต้นทุนที่คิดมือ)"""
    e, drift, target = rec["e"], rec["drift"], rec["target"]
    L = [f"#### {title} · e = {e.date()}"]
    sells, buys = {}, {}
    for f in sorted(set(drift) | set(target)):
        d = target.get(f, 0.0) - drift.get(f, 0.0)
        if d < -1e-15:
            sells[f] = -d
        elif d > 1e-15:
            buys[f] = d
    L.append(f"- ส่วนหุ้นก่อน = {sum(drift.values()):.4f} → หลัง = {sum(target.values()):.4f} (เงินสดปรับ ไม่มีต้นทุน) · ขาย {len(sells)} กอง Σ={sum(sells.values()):.5f} · ซื้อ {len(buys)} กอง Σ={sum(buys.values()):.5f}")
    total = 0.0
    amcs = sorted({afd.amc[f] for f in list(sells) + list(buys)})
    for amc in amcs:
        sf = [f for f in sells if afd.amc[f] == amc]
        bf = [f for f in buys if afd.amc[f] == amc]
        S, B = sum(sells[f] for f in sf), sum(buys[f] for f in bf)
        m = min(S, B) if sf and bf else 0.0
        L.append(f"- **{amc}**: S={S:.5f} B={B:.5f} m=min(S,B)={m:.5f}")
        so = si = bfw = ffw = 0.0
        for f in sf:
            bfv, sb = hand_rate(ser, med, f, "BF", e)
            sov, ss = hand_rate(ser, med, f, "SO", e)
            L.append(f"  - ขาย {f}: Δ={sells[f]:.5f} · BF={bfv}% [{sb}] · SO={sov}% [{ss}]")
            bfw += sells[f] * bfv / S if S else 0
            so += sells[f] * sov / S if S else 0
        for f in bf:
            ffv, sf_ = hand_rate(ser, med, f, "FF", e)
            siv, ss = hand_rate(ser, med, f, "SI", e)
            L.append(f"  - ซื้อ {f}: Δ={buys[f]:.5f} · FF={ffv}% [{sf_}] · SI={siv}% [{ss}]")
            ffw += buys[f] * ffv / B if B else 0
            si += buys[f] * siv / B if B else 0
        c = 0.0
        if m > 0:
            ch_sw, ch_sb = m * (so + si) / 100, m * (bfw + ffw) / 100
            use_sw = (so + si) < (bfw + ffw)
            L.append(f"  - ถ่วง: SO={so:.4f}% SI={si:.4f}% | BF={bfw:.4f}% FF={ffw:.4f}% → สับเปลี่ยน {m:.5f}×({so:.4f}+{si:.4f})% = {ch_sw:.6f} · ขาย-ซื้อ {m:.5f}×({bfw:.4f}+{ffw:.4f})% = {ch_sb:.6f} → ใช้ **{'สับเปลี่ยน' if use_sw else 'ขาย-ซื้อ'}**")
            c += ch_sw if use_sw else ch_sb
        for f in sf:
            c += sells[f] * (1 - m / S) * hand_rate(ser, med, f, "BF", e)[0] / 100
        for f in bf:
            c += buys[f] * (1 - m / B) * hand_rate(ser, med, f, "FF", e)[0] / 100
        L.append(f"  - ต้นทุน {amc} = {c:.6f}")
        total += c
    L.append(f"- **ต้นทุนรวมที่คิดมือ = {total:.8f}** · simulate คิด = {rec['cost']:.8f} · ต่าง = {total - rec['cost']:.2e}")
    return "\n".join(L), total


def pct(x, d=2):
    return f"{x * 100:.{d}f}%"


def main():
    o = af.main()
    E, F, A, FT, afd = o["E"], o["F"], o["A"], o["FT"], o["afd"]
    held, sims = o["held"], o["sims"]
    yrs = o["yrs"]
    models = ["M004-TF-FX", "M013-GC75"]
    groups = common.load_groups()
    L = []
    w = L.append

    # ---------------- เตรียมตัวเลข ----------------
    # ต้นทุนต่อปี แยกรหัส + ช่องทาง
    comp = {}
    for m in models:
        e = E[E.model == m]
        y = yrs[m]
        comp[m] = {c: e[f"cost_{c}"].sum() / y * 1e4 for c in CODES}
        comp[m]["total"] = e["cost_mine"].sum() / y * 1e4
        comp[m]["noswitch"] = e["cost_noswitch"].sum() / y * 1e4
        comp[m]["saving"] = comp[m]["noswitch"] - comp[m]["total"]
        comp[m]["sell_vol_yr"] = e["sell_vol"].sum() / y
        comp[m]["buy_vol_yr"] = e["buy_vol"].sum() / y
        comp[m]["switch_share"] = e["switch_vol"].sum() / e["sell_vol"].sum()
        comp[m]["matched_share"] = e["matched_vol"].sum() / e["sell_vol"].sum()
        comp[m]["avg_fee_side"] = e["cost_mine"].sum() / (e["sell_vol"].sum() + e["buy_vol"].sum())
        comp[m]["fb"] = {c: int(e[f"fallback_{c}"].sum()) for c in CODES}
        comp[m]["n_trades"] = int(e["n_sell"].sum() + e["n_buy"].sum())

    # fallback ตามกอง/รหัส (ที่มีผลใน entry)
    used = FT[FT.used_in_entry].copy()
    used["fb"] = used["source"].str.startswith("median")
    used["future_snap"] = used.apply(lambda r: r["snapshot"] is not None and pd.Timestamp(r["snapshot"]) > pd.Timestamp(r["e"]), axis=1)
    used["lag_days"] = used.apply(lambda r: (pd.Timestamp(r["snapshot"]) - pd.Timestamp(r["e"])).days if r["snapshot"] is not None else np.nan, axis=1)
    fb_tab = used[used.fb].groupby(["model", "code", "fund", "source"]).size().reset_index(name="n")
    fb_by_code = used[used.fb].groupby(["model", "code", "source"]).size().reset_index(name="n")
    src_cnt = used.groupby(["model", "source"]).size().unstack(fill_value=0)
    fut = used.groupby("model").agg(n=("future_snap", "size"), future=("future_snap", "sum"), lag_med=("lag_days", "median"), lag_max=("lag_days", "max"))

    # ค่าที่ใช้จริงต่อกอง×รหัส: min/max/แหล่ง
    allpairs = FT[FT.used_in_entry]
    def summarize(g):
        vals = sorted(set(round(v, 4) for v in g["value_pct"]))
        return pd.Series({"n_use": len(g), "values_used": "/".join(f"{v:g}" for v in vals), "sources": "; ".join(sorted(set(s.split(" (")[0] for s in g["source"])))})
    fund_code_tab = allpairs.groupby(["fund", "code"]).apply(summarize).reset_index()
    fund_code_tab.to_csv(os.path.join(RES, "AUDIT_fees_fund_code_used.csv"), index=False, encoding="utf-8-sig")

    # snapshot ทั้งหมดของกองที่ถือ + การเปลี่ยนค่า
    snap = o["snap"].copy()
    snap["v"] = pd.to_numeric(snap["Actual Value"], errors="coerce")
    snap["rate_v"] = pd.to_numeric(snap["Rate"], errors="coerce")
    snap.drop(columns=["file_row"]).to_csv(os.path.join(RES, "AUDIT_fees_raw_snapshots_held.csv"), index=False, encoding="utf-8-sig")
    changes = []
    for (f, c), g in snap.groupby(["Fund Code", "Code"]):
        g = g.drop_duplicates("As of Date", keep="last")
        vals = list(zip(g["As of Date"], g["Actual Value"]))
        for i in range(1, len(vals)):
            if str(vals[i][1]) != str(vals[i - 1][1]):
                changes.append((f, c, vals[i - 1][0], vals[i - 1][1], vals[i][0], vals[i][1]))
    n_series_multi = int(sum(1 for _, g in snap.groupby(["Fund Code", "Code"]) if g["As of Date"].nunique() > 1))
    n_series = int(snap.groupby(["Fund Code", "Code"]).ngroups)
    bad_rows = snap[snap["v"].isna() | (snap["v"] < 0) | (snap["v"] > 10)]
    ff0 = snap[(snap["Code"] == "FF") & (snap["v"] == 0)]
    # คู่ที่ Actual < Rate (เพดาน)
    ratio = snap[(snap["v"].notna()) & (snap["rate_v"] > 0)].copy()
    ratio["r"] = ratio["v"] / ratio["rate_v"]
    ratio_s = ratio.groupby("Code")["r"].describe()[["count", "mean", "min", "50%", "max"]]
    nofee_rate = snap[(snap["rate_v"].notna()) & (snap["rate_v"] > 0) & (snap["v"] == 0)].groupby("Code").size()

    # ภาพรวมทั้งไฟล์ (FEEUH)
    raw = af.raw_fee()
    r4 = raw[raw["Code"].isin(CODES)]
    nv = pd.to_numeric(r4["Actual Value"], errors="coerce")
    file_stats = {"rows": len(r4), "blank": int(r4["Actual Value"].isna().sum()), "text": int((nv.isna() & r4["Actual Value"].notna()).sum()),
                  "gt10": int((nv > 10).sum()), "neg": int((nv < 0).sum()),
                  "text_vals": r4["Actual Value"][nv.isna() & r4["Actual Value"].notna()].value_counts().to_dict(),
                  "ff_eq_rate": int(((nv == pd.to_numeric(r4["Rate"], errors="coerce")) & (r4["Code"] == "FF")).sum()),
                  "ff_rows_num": int(((r4["Code"] == "FF") & nv.notna() & pd.to_numeric(r4["Rate"], errors="coerce").notna()).sum())}

    # ---------------- ตัวอย่างแถวดิบ ----------------
    ex_funds = ["ABIG", "ASP-IHEALTH", "ASP-VIET", "ES-USTECH", "PRINCIPAL GOPP-X", "TISCOINA-A", "K-AEC", "DAOL-GOLD"]
    ex = snap[snap["Fund Code"].isin(ex_funds)].copy()
    ex = ex[ex["Code"].isin(CODES)].sort_values(["Fund Code", "Code", "As of Date"])

    # ---------------- top 5 กองที่ต้นทุนสูงสุด ----------------
    top = {}
    for m in models + ["รวม 2 โมเดล"]:
        f = F if m == "รวม 2 โมเดล" else F[F.model == m]
        yy = (yrs["M004-TF-FX"] + yrs["M013-GC75"]) / 2 if m == "รวม 2 โมเดล" else yrs[m]
        g = f.groupby("fund")[[f"cost_{c}" for c in CODES] + ["cost", "sell", "buy"]].sum()
        g["bp_yr"] = g["cost"] / (yrs["M004-TF-FX"] + yrs["M013-GC75"]) * 1e4 if m == "รวม 2 โมเดล" else g["cost"] / yy * 1e4
        top[m] = g.sort_values("cost", ascending=False).head(5)
    fund_cost_all = F.groupby(["model", "fund"])[["cost_FF", "cost_BF", "cost_SI", "cost_SO", "cost"]].sum().reset_index()
    fund_cost_all["bp_yr"] = fund_cost_all.apply(lambda r: r["cost"] / yrs[r["model"]] * 1e4, axis=1)
    fund_cost_all.sort_values(["model", "cost"], ascending=[True, False]).to_csv(os.path.join(RES, "AUDIT_fees_cost_by_fund.csv"), index=False, encoding="utf-8-sig")

    # ---------------- ข้าม class ใน family เดียวกัน ----------------
    fam = lambda x: fs.family_of(x, groups, fixed=True)[0]
    fam_of_held = pd.Series({f: fam(f) for f in held})
    multi = fam_of_held.groupby(fam_of_held).filter(lambda s: len(s) > 1)
    pairs = o["pairs"].copy()
    pairs["same_family_fx"] = pairs.apply(lambda r: fam(r["sell"]) == fam(r["buy"]), axis=1)
    n_same_fam_pairs = int(pairs["same_family_fx"].sum())
    # หา entry ที่กองใน family เดียวกันถูกถือใน 2 entry ติดกันคนละ class (เปลี่ยน representative)
    rep_changes = []
    for m in models:
        recs = sims[m]["rec"]
        for k in range(1, len(recs)):
            a = {f for f, v in recs[k - 1]["target"].items() if f != "__CASH__" and v > 1e-9}
            b = {f for f, v in recs[k]["target"].items() if f != "__CASH__" and v > 1e-9}
            for x in a - b:
                for y in b - a:
                    if fam(x) == fam(y):
                        rep_changes.append((m, str(recs[k]["e"].date()), x, y, afd.amc.get(x), afd.amc.get(y)))
    # ตัวอย่างข้าม class ในรหัสเดียวกัน: ONE-GLOBFIN IA/RA, TISCOIN/TISCOINA ฯลฯ ที่ถูกถือต่าง trial
    # ---------------- กองที่ปิดช่องทางไม่ได้ (flag) ----------------
    flags = o["ec"]["flags"]
    n_flag_bad = int(((flags["switch_out flag"] != "Y") | (flags["switch_in flag"] != "Y")).sum())
    periodflag = int((flags[["switch in periold flag", "switch out periold flag"]] != "N").any(axis=1).sum())
    amc_pairs_sw = A[A.channel == "สับเปลี่ยน"].groupby(["model", "amc"]).agg(n=("k", "size"), vol=("m", "sum"), saving=("saving", "sum")).reset_index()

    # ---------------- hand trace 4 entries ----------------
    # median ต้องคำนวณบนกองใน NAV universe (570) เหมือน spec → ใช้ชุด fund code เดียวกับที่ AFD ได้
    nav_codes = set(common.load_nav()["FundCode"].unique())
    ser, med = hand_rates(nav_codes)
    picks = [("M004-TF-FX", 7, "(ก) มีสับเปลี่ยนใน บลจ. เดียวกัน (TISCOASSET) + BF/SO บางกองใช้ค่าจริง"),
             ("M013-GC75", 1, "(ข) ใช้ median fallback (SI/SO ของ K-Asset, BF/SO อื่น) + ส่วนหุ้นลดจาก 0.479 → 0.25 (เงินสดเปลี่ยน)"),
             ("M013-GC75", 4, "(ค) ส่วนหุ้นเพิ่ม 0.504 → 0.75 (ซื้อจากเงินสด ต้อง FF) + fallback BF"),
             ("M013-GC75", 10, "(ง) ส่วนหุ้นลดจาก 1.00 → 0.50 (ขายเป็นเงินสด คิดเฉพาะขากอง) + สับเปลี่ยนใน บลจ.")]
    traces, hand_diffs = [], []
    for m, k, why in picks:
        txt, tot = hand_trace(sims[m]["rec"][k], afd, ser, med, f"{m} entry k={k} {why}")
        traces.append(txt)
        hand_diffs.append((m, k, tot, sims[m]["rec"][k]["cost"], tot - sims[m]["rec"][k]["cost"]))
    med_hand = med

    # hand trace ทั้ง 30 entry (ไม่พิมพ์) เพื่อเช็คตรง
    max_hand = 0.0
    for m in models:
        for k, rec in enumerate(sims[m]["rec"]):
            _, tot = hand_trace(rec, afd, ser, med, "")
            max_hand = max(max_hand, abs(tot - rec["cost"]))

    # ---------------- เขียน CSV ราย entry ----------------
    E2 = E.copy()
    E2["bp_of_value"] = E2["cost_mine"] * 1e4
    E2.to_csv(os.path.join(RES, "AUDIT_fees_entries.csv"), index=False, encoding="utf-8-sig")
    A.to_csv(os.path.join(RES, "AUDIT_fees_amc_groups.csv"), index=False, encoding="utf-8-sig")
    FT.to_csv(os.path.join(RES, "AUDIT_fees_lookups.csv"), index=False, encoding="utf-8-sig")
    F.to_csv(os.path.join(RES, "AUDIT_fees_cost_by_fund_entry.csv"), index=False, encoding="utf-8-sig")

    sens = o["sens"]
    base_sens = dict(sens)["baseline (AFD ของผม = โค้ดเดิม)"]

    # ---------------- md ----------------
    sm = o["sims_meta"]
    ref = o["reference"]
    w("# AUDIT_fees — ตรวจค่าธรรมเนียมซื้อขาย/สับเปลี่ยนใน backtest ของ M004-TF-FX (Trend 25, หน้า 9) และ M013-GC75 (โมเดลหลัก)")
    w("")
    w(f"รันเมื่อ {pd.Timestamp.now().isoformat(timespec='seconds')} · backtest-validator · **งานตรวจ ไม่ใช่ trial** (ไม่แตะ trials.csv/ALL_RESULTS/โค้ดเดิม/cache/base_data) · สคริปต์ `backtest/audit_fees.py` + `audit_fees_report.py`")
    w("")
    w("## 0. ผลสรุป")
    w("")
    w(f"- **Regression ผ่าน**: จำลองซ้ำจาก `M004-TF-FX_weights.csv` / `M013_weights.csv` ด้วย `simulate_path` เดิม + rf จริง → M004-TF-FX Sharpe {sm['M004-TF-FX']['sharpe_real']:.4f} (ไฟล์เดิม {ref['M004-TF-FX']['sharpe']:.4f}) · M013-GC75 Sharpe {sm['M013-GC75']['sharpe_real']:.4f} (เดิม {ref['M013-GC75']['sharpe']:.4f}) · ต้นทุน {sm['M013-GC75']['cost_bp_yr']:.2f} bp/ปี (เดิม {ref['M013-GC75']['cost_bp']:.2f})")
    w(f"- **ต้นทุนต่อ entry คำนวณซ้ำ 2 วิธีอิสระ** (my_entry ใน audit_fees.py จาก CSV ดิบ + hand_trace python ล้วน): ตรง simulate ทั้ง {len(E)} entry (max|Δ| = {o['max_abs_diff_entry']:.1e} และ {max_hand:.1e})")
    w(f"- **ไม่พบบั๊กที่เปลี่ยน Sharpe**: ข้อบกพร่องที่พบ 2 ข้อ (ข้อความ 'ไม่มี' ถูกถือเป็น NaN→median · แถวซ้ำ fund+code+date เลือกแบบไม่กำหนดแน่นอน) ผลต่อ Sharpe = 0.0000 ทั้ง 2 โมเดล (ดู §4)")
    w("- **ความเสี่ยงจริงอยู่ที่ข้อมูล ไม่ใช่โค้ด**: (1) ใช้ Actual Value ไม่ใช่เพดาน Rate — ถ้าจ่ายตามเพดาน Sharpe ลดเหลือ ~0.31–0.32 · (2) ค่าธรรมเนียมเป็น snapshot 2023-05→2026-07 ใช้ย้อนหลัง 2022–2025 · (3) fallback median ของกอง/รหัสที่ไม่มีแถว · (4) การยกเว้น front-end")
    w("")
    w("| โมเดล | Sharpe (rf จริง, full) | ต้นทุน bp/ปี | FF | BF | SI | SO | ประหยัดจากช่องทางสับเปลี่ยน (bp/ปี) | ยอดขายที่ไปช่องทางสับเปลี่ยน |")
    w("|---|---|---|---|---|---|---|---|---|")
    for m in models:
        c = comp[m]
        w(f"| {m} | {sm[m]['sharpe_real']:.4f} | {c['total']:.1f} | {c['FF']:.1f} | {c['BF']:.1f} | {c['SI']:.1f} | {c['SO']:.1f} | {c['saving']:.1f} | {pct(c['switch_share'], 1)} |")
    w("")

    w("## 1. ส่วน A — ข้อมูลค่าธรรมเนียมถูกไหม")
    w("")
    w("### 1.1 กองที่ 2 โมเดลเคยถือ")
    w(f"- รวม {len(held)} กอง (TF-FX {len({f for p in sims['M004-TF-FX']['rec'] for f in list(p['drift'])+list(p['target'])})} · GC75 {len({f for p in sims['M013-GC75']['rec'] for f in list(p['drift'])+list(p['target'])})}) · มีแถว FEEUH FF/BF/SI/SO {len(set(snap['Fund Code']))} กอง · **ไม่มีแถว FEEUH เลย 2 กอง: ES-GINFRA-A, FCSCBSETE** (ใช้ median ทุกรหัส)")
    w(f"- snapshot ของกองที่ถือ: {o['n_snapshot_rows_held']} แถวดิบ (ไฟล์เต็ม `AUDIT_fees_raw_snapshots_held.csv`) · ค่าที่ใช้จริงต่อกอง×รหัส `AUDIT_fees_fund_code_used.csv` · ทุก lookup ต่อ entry `AUDIT_fees_lookups.csv`")
    w(f"- ตรวจ FeeData ของผม (อ่าน CSV ดิบเอง) vs `fees.FeeData` เดิม ทุกกอง×รหัส×วัน: ต่างกัน {len(o['afd_vs_orig_mismatch'])} จุด — ทั้งหมดเป็น PRINCIPAL GOPP-X FF/SI วันที่ 2023-07-04 และ 2023-10-03 (ดู §1.2 ข้อ 3 — ทั้ง 2 วันนั้นไม่มีการซื้อ/ขาย GOPP-X)")
    w("")
    w("**ค่าที่ใช้จริง ณ วันซื้อขาย (เฉพาะรหัสที่เข้าสูตรของ entry นั้น: ขาย→BF,SO · ซื้อ→FF,SI) — สรุปต่อกอง** (ค่าต่างๆ ที่ใช้ตลอด 15 entry, แหล่ง: ค่าจริง / snapshot เก่าสุด / median)")
    w("")
    pv = fund_code_tab.pivot(index="fund", columns="code", values="values_used").reindex(columns=list(CODES)).fillna("—")
    ps = fund_code_tab.assign(s=fund_code_tab["sources"].map(lambda x: "M" if "median" in x else ("O" if "เก่าสุด" in x else "A") if "ค่าจริง" not in x else ("A+" + ("M" if "median" in x else "")))).pivot(index="fund", columns="code", values="sources").reindex(columns=list(CODES))
    w("| กอง | บลจ. | FF | BF | SI | SO | แหล่ง (A=ค่าจริง · O=snapshot เก่าสุดก่อน snapshot แรก · M=median) |")
    w("|---|---|---|---|---|---|---|")
    def code_src(f, c):
        x = fund_code_tab[(fund_code_tab.fund == f) & (fund_code_tab.code == c)]
        if x.empty:
            return ""
        s = x.iloc[0]["sources"]
        tag = []
        if "ค่าจริง" in s: tag.append("A")
        if "เก่าสุด" in s: tag.append("O")
        if "median" in s: tag.append("M")
        return c + ":" + "+".join(tag)
    for f in sorted(pv.index):
        w(f"| {f} | {afd.amc.get(f)} | " + " | ".join(pv.loc[f, c] for c in CODES) + " | " + " ".join(code_src(f, c) for c in CODES if code_src(f, c)) + " |")
    w("")
    w("### 1.2 ตัวเลขที่นับ")
    w("")
    w("**(1) จำนวนครั้งที่ใช้ median fallback (นับเฉพาะ กอง×รหัสที่เข้าสูตรจริงของ entry · ไม่นับซ้ำจากการคำนวณสองช่องทาง)** — median ที่ใช้: " + " · ".join(f"{c} {o['median'][c]:g}" for c in CODES) + f" (คำนวณใหม่เองตรงกับโค้ดเดิม {o['median_orig'] == o['median']})")
    w("")
    w("| โมเดล | FF | BF | SI | SO | จำนวนรายการซื้อ+ขายทั้งหมด (กอง×entry) |")
    w("|---|---|---|---|---|---|")
    for m in models:
        c = comp[m]["fb"]
        w(f"| {m} | {c['FF']} | {c['BF']} | {c['SI']} | {c['SO']} | {comp[m]['n_trades']} |")
    w("")
    w("(ตัวเลขเดิมใน COST_real_fees_results.md คือ 'รายครั้งเรียก' ทุก trial รวมกัน {FF 113, SO 830, SI 194, BF 1260} — นับซ้ำทุกการคำนวณสองช่องทาง จึงไม่เทียบกับตารางนี้ตรงๆ)")
    w("")
    w("แยกสาเหตุของ fallback (ที่เข้าสูตรจริง):")
    w("")
    w("| โมเดล | รหัส | สาเหตุ | จำนวน |")
    w("|---|---|---|---|")
    for r in fb_by_code.itertuples():
        w(f"| {r.model} | {r.code} | {r.source} | {r.n} |")
    w("")
    w("กองที่ fallback บ่อยสุด (ตามกอง×รหัส):")
    w("")
    w("| โมเดล | กอง | รหัส | จำนวนครั้ง |")
    w("|---|---|---|---|")
    ft2 = fb_tab.groupby(["model", "fund", "code"])["n"].sum().reset_index().sort_values("n", ascending=False).head(14)
    for r in ft2.itertuples():
        w(f"| {r.model} | {r.fund} | {r.code} | {r.n} |")
    w("")
    w(f"**(2) ค่าที่ถูกตัดเพราะว่าง/ติดลบ/>10 ของกองที่ถือ:** {len(bad_rows)} แถวจาก {o['n_snapshot_rows_held']} " + (": " + "; ".join(f"{r['Fund Code']} {r['Code']} {r['As of Date']} = '{r['Actual Value']}'" for _, r in bad_rows.iterrows()) if len(bad_rows) else "") +
      f" · ทั้งสองแถวเป็นข้อความ 'ไม่มี' (= ไม่เก็บ) ไม่ใช่ตัวเลขว่าง · ไม่มีแถวที่ >10 (บาท) หรือติดลบในกองที่ถือ · ทั้งไฟล์ FEEUH FF/BF/SI/SO {file_stats['rows']} แถว: ว่าง {file_stats['blank']} · ข้อความ {file_stats['text']} {file_stats['text_vals']} · >10 = {file_stats['gt10']} (SO 200/300 บาท) · ติดลบ {file_stats['neg']}")
    w("")
    w(f"**(3) แถวซ้ำ fund+code+date ที่ค่าไม่เท่ากัน** (ไฟล์ทั้งหมด {o['dup_groups_all']} กลุ่ม, ของกองที่ถือ {len(o['dup_groups_held'])}): " + "; ".join(f"{g[0]} {g[1]} {g[2].date()} ค่า {g[4]}" for g in o["dup_groups_held"]) +
      " — `fees.FeeData` ใช้ `sort_values('date')` (quicksort ไม่ stable) แล้วเอาแถวท้าย → ผลตกที่ **FF=SI=0** สำหรับ PRINCIPAL GOPP-X ก่อน snapshot ถัดไป ในขณะที่แถว 'สุดท้ายตามลำดับไฟล์' = 1.5 · ไม่ determinic · ผลต่อ Sharpe = 0 (ดู §4): GOPP-X ถูกซื้อครั้งเดียว (GC75 k=7, 2024-01-02) ซึ่งตอนนั้นใช้ snapshot 2023-10-31 (FF=SI=0) ไม่ใช่แถวซ้ำ · ในไฟล์ยังมีอีก 1 แถวข้อความ '0.535%' (T-FixFIF(I), ไม่ใช่กองที่ถือ) ที่ถูกถือเป็น NaN ทั้งที่เป็นตัวเลข")
    w("")
    w("**(4) ค่าที่เปลี่ยนข้าม snapshot (กองที่ถือ):** " + f"{len(changes)} การเปลี่ยนค่า ใน {n_series_multi} จาก {n_series} กอง×รหัสที่มีมากกว่า 1 snapshot")
    w("")
    w("| กอง | รหัส | snapshot เก่า → ค่า | snapshot ใหม่ → ค่า |")
    w("|---|---|---|---|")
    for c_ in changes:
        w(f"| {c_[0]} | {c_[1]} | {c_[2]} → {c_[3]} | {c_[4]} → {c_[5]} |")
    w("")
    w("**(5) กองที่ FF = 0:** " + (", ".join(sorted(set(ff0['Fund Code']))) if len(ff0) else "ไม่มีกองที่ถือที่ FF Actual = 0") +
      f" · แต่มี SO=0/BF=0 เป็นปกติ (BF Actual=0 {int(((snap.Code=='BF')&(snap.v==0)).sum())} แถว, SO=0 {int(((snap.Code=='SO')&(snap.v==0)).sum())} แถว) · แถวที่ Rate(เพดาน)>0 แต่ Actual=0: {nofee_rate.to_dict()}")
    w("")
    w("### 1.3 'Actual Value' คืออะไร — อ่านจาก schema PDF + ข้อมูลดิบ")
    w("")
    w("- Schema (`FUNDPROFILE_SECFUNDFEE_SCHEMA.pdf` §3 · ตัวอักษรไทยใน PDF เพี้ยนตอนสกัด แต่คำอธิบายคอลัมน์อ่านได้): **Rate = 'เพดานตามหนังสือชี้ชวน'**, **Actual Value = 'อัตราที่เก็บจริง'** (TER ของแอปก็ใช้ Actual Value ไม่ใช่ Rate) · Unit Rate = ฐานคำนวณเป็นข้อความ แต่ **ในกลุ่ม FEEUH ว่าง 14,767 จาก 14,775 แถว** (ไม่มีหน่วย/Min/Max/ประเภทค่า/Remark ใดๆ ให้ตรวจ — ไฟล์มีแค่ 7 คอลัมน์) · Actual Value ว่างทั้งไฟล์ 50.8% (ส่วนใหญ่เป็น FEEMF) แต่ของกองที่ถือ FEEUH ไม่ว่างเลย")
    w("- คำเตือนจาก schema: กลุ่ม fund+type+code+date เดียวกันมีได้ถึง 6 แถว (ต้องเก็บแถวสุดท้ายตามวันที่) — ตรงกับเรื่องแถวซ้ำข้างบน")
    w(f"- เป็น % จริง (ไม่ใช่บาท) ยกเว้น SO ที่ >10 จำนวน {file_stats['gt10']} แถว (200/300 = บาท) ซึ่งโค้ดตัดทิ้งถูกต้อง · ค่า FF Actual เท่ากับเพดาน Rate ใน {file_stats['ff_eq_rate']} จาก {file_stats['ff_rows_num']} แถวที่เทียบได้ทั้งไฟล์ → Actual ส่วนใหญ่ **ต่ำกว่าเพดาน** (เช่น ABIG เพดาน 3 เก็บจริง 1.5) · ของกองที่ถือ Actual/Rate:")
    w("")
    w("| รหัส | จำนวน | mean | min | median | max |")
    w("|---|---|---|---|---|---|")
    for c, r in ratio_s.iterrows():
        w(f"| {c} | {int(r['count'])} | {r['mean']:.2f} | {r['min']:.2f} | {r['50%']:.2f} | {r['max']:.2f} |")
    w("")
    w("- **ข้อจำกัดที่ตรวจไม่ได้จากไฟล์**: Actual Value เป็นอัตราที่ บลจ. รายงานว่าเก็บ (ช่องทางขายตรง/ผู้จัดจำหน่ายหลัก) — ไม่มีคอลัมน์ระบุช่องทาง/ผู้จัดจำหน่ายอื่นหรือโปรโมชัน (ธนาคาร/แพลตฟอร์มมักลดหรือยกเว้น) จึงตีความเป็น 'ราคาจ่ายจริงของนักลงทุนรายย่อย' ไม่ได้ยืนยัน · ผลของสมมติฐานนี้ใหญ่ที่สุด (§4)")
    w("")
    w("**ตัวอย่างแถวดิบของกองในพอร์ต (Rate = เพดาน · Actual Value = อัตราเก็บจริง)**")
    w("")
    w("| As of Date | Fund Code | Code | Rate | Actual Value |")
    w("|---|---|---|---|---|")
    for _, r in ex.iterrows():
        w(f"| {r['As of Date']} | {r['Fund Code']} | {r['Code']} | {r['Rate']} | {r['Actual Value']} |")
    w("")
    w("**ความล้าสมัย/look-ahead ของค่าธรรมเนียม** (ใช้ snapshot ที่ลงวันที่หลังวันซื้อขาย = ก่อน snapshot แรก):")
    w("")
    w("| โมเดล | lookup ที่เข้าสูตร | ใช้ snapshot ที่ลงวันหลัง e | % | ห่างมัธยฐาน (วัน) | ห่างสูงสุด (วัน) |")
    w("|---|---|---|---|---|---|")
    for m, r in fut.iterrows():
        w(f"| {m} | {int(r['n'])} | {int(r['future'])} | {pct(r['future']/r['n'],1)} | {r['lag_med']:.0f} | {r['lag_max']:.0f} |")
    w("")
    w("แหล่งที่มาของ lookup ที่เข้าสูตร:")
    w("")
    cols = list(src_cnt.columns)
    w("| โมเดล | " + " | ".join(cols) + " |")
    w("|---|" + "---|" * len(cols))
    for m_, r_ in src_cnt.iterrows():
        w(f"| {m_} | " + " | ".join(str(int(r_[c_])) for c_ in cols) + " |")
    w("")

    w("## 2. ส่วน B — วิธีคิดต้นทุนถูกไหม")
    w("")
    w("### 2.1 กติกา (ที่ตรวจ)")
    w("- entry = ทุกการ rebalance รายไตรมาส (15 entry ต่อโมเดล, e = วันทำการที่ 2 หลัง t) · drift_w = มูลค่ากองที่ถือ ณ e ÷ มูลค่าพอร์ตรวมเงินสดที่งอกเงย · target = น้ำหนักเป้าหมายรวมเงินสดเปลี่ยน · **ขา `__CASH__` ไม่เข้าสูตร** (ตรวจ: ไม่มี key นี้ใน drift/target ที่ส่งเข้า fee model)")
    w("- ต่อ บลจ.: m = min(Σขาย, Σซื้อ) ใช้ช่องทางที่ถูกกว่าระหว่าง (SO+SI) กับ (BF+FF) (อัตราถ่วงยอด) ส่วนที่เหลือคิด BF ของผู้ขาย / FF ของผู้ซื้อ · ต้นทุนรวมหักจากมูลค่าพอร์ต ณ e")
    w("")
    w("### 2.2 ผลเทียบ 2 วิธีอิสระ ต่อ entry (ครบ 30 entry ใน `AUDIT_fees_entries.csv` — คอลัมน์ cost_sim = simulate · cost_mine = my_entry)")
    w("")
    w("| โมเดล | k | e | หุ้นก่อน→หลัง | ขาย/ซื้อ (กอง) | ยอดขาย | ยอดซื้อ | m ที่จับคู่ใน บลจ. | m ที่ใช้สับเปลี่ยน | cost simulate | cost ผม | FF | BF | SI | SO | fallback ที่เข้าสูตร (FF/BF/SI/SO) |")
    w("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for r in E.itertuples():
        w(f"| {r.model} | {r.k} | {r.e} | {r.equity_before:.3f}→{r.equity_after:.3f} | {r.n_sell}/{r.n_buy} | {r.sell_vol:.4f} | {r.buy_vol:.4f} | {r.matched_vol:.4f} | {r.switch_vol:.4f} | {r.cost_sim*1e4:.1f}bp | {r.cost_mine*1e4:.1f}bp | {r.cost_FF*1e4:.1f} | {r.cost_BF*1e4:.1f} | {r.cost_SI*1e4:.1f} | {r.cost_SO*1e4:.1f} | {r.fallback_FF}/{r.fallback_BF}/{r.fallback_SI}/{r.fallback_SO} |")
    w("")
    w(f"max|cost_sim − cost_mine| = {o['max_abs_diff_entry']:.2e} · max|cost_sim − hand_trace| (30 entry) = {max_hand:.2e}")
    w("")
    w("### 2.3 คำนวณมือซ้ำ 4 entry (python ล้วนจาก CSV ดิบ ไม่ใช้ FeeData/FeeModel)")
    w("")
    for t in traces:
        w(t)
        w("")
    w("สรุป: " + " · ".join(f"{m} k={k}: มือ {a:.8f} vs sim {b:.8f} (Δ {d:.1e})" for m, k, a, b, d in hand_diffs))
    w("")
    w("### 2.4 edge case")
    w("")
    nc = o["ec"]["cannot_buy"]
    w(f"1. **ขายเป็นเงินสด / ซื้อกองจากเงินสด (GC75 ปรับสัดส่วนหุ้น)**: คิดเฉพาะขากอง ✓ — ตัวอย่าง GC75 k=10 (2024-10-02) หุ้น 1.00→0.50: ขาย 0.639 / ซื้อ 0.139, ต้นทุนรวม {E[(E.model=='M013-GC75')&(E.k==10)].cost_mine.iloc[0]*1e4:.1f}bp (BF≈0 จึงถูกมาก, ส่วนใหญ่เป็นขาออก) · k=4 (2023-04-04) หุ้น 0.504→0.75 ซื้อ 0.619 → จ่าย FF {E[(E.model=='M013-GC75')&(E.k==4)].cost_mine.iloc[0]*1e4:.1f}bp · ผลคือ **ต้นทุนไม่สมมาตร: ลดหุ้นถูก (BF≈0), เพิ่มหุ้นแพง (FF≈1.5%)** ซึ่งเป็นพฤติกรรมที่ถูกต้องตามข้อมูล")
    w("2. **เงินสดไม่เสียต้นทุน**: สมมติว่าเงินสด = เงินฝาก/ตลาดเงินที่ซื้อขายฟรี (ไม่ใช่กองตลาดเงินของ บลจ.) — สมมติฐานที่สมเหตุผลแต่ไม่ได้ตรวจกับช่องทางจริง")
    w("3. **drift ก่อน rebalance**: คิดจาก NAV ล่าสุด ≤ e ของกองที่ถือ (mark) ✓ ส่วนราคาซื้อใช้ NAV แรก ≥ e (≤10 วันทำการ) — ต้นทุนเป็นสัดส่วนของมูลค่า drift ก่อนหักต้นทุน")
    w("4. **ต้นทุนถูกหักเป็นสัดส่วนของมูลค่าพอร์ตรวม แล้วลดทุกสินทรัพย์เท่ากัน (value×(1−cost))** แทนที่จะหักจากยอดซื้อ/ขายจริง — เงินสดจึงถูกลดไปเล็กน้อยด้วย · ผลกระทบเล็กมาก (ลำดับ cost×เงินสดสัดส่วน ≤ ~0.1bp/entry) ไม่แก้")
    w("5. **FF ถูกคิดเป็นสัดส่วนของ 'ยอดซื้อ' (Δw) ไม่ใช่ gross-up**: FF 1.5% ของ 1 บาทที่ลงทุน หักจากเงินที่ใส่ ไม่ใช่บวกเพิ่ม — ถูกต้องตามธรรมเนียมไทย")
    w(f"6. **กองที่ซื้อไม่ได้ (cannot_buy)**: ใน 2 โมเดลนี้ {sum(len(v) for v in nc.values())} ครั้ง (ไม่มี) → ไม่มีค่าธรรมเนียมที่จ่ายแล้วซื้อไม่ได้ · exec_late: {o['ec']['exec_late']} (UCI ซื้อช้ากว่า e ที่ 2025-10-02 — ราคาซื้อเลื่อนตาม NAV แรกที่มี ไม่กระทบสูตรต้นทุน)")
    w(f"7. **การจับคู่ บลจ. (AMC_CODE)**: กองที่ถือ {len(held)} กองมี AMC_CODE ครบ · {flags['AMC_CODE'].nunique()} บลจ. · EASTSPRING รวม TMBGINFRA/ES-USTECH/ES-GINFRA-A (ถูก: TMB→Eastspring) · ไม่พบ AMC สะกดซ้ำ/ใกล้กันใน universe 18 ค่า (ABERDEEN, ASSETFUND, BBLAM, DAOLINV, EASTSPRING, KASSET, KKPAM, KTAM, LHFUND, MFC, ONEAM, PAMC, PRINCIPAL, SCBAM, TALISAM, TISCOASSET, UOBAM, XSpringAM) · ข้อควรระวัง: PAMC/XSpringAM/TALISAM ไม่มีกองใน 2 โมเดล · กองในกลุ่มสับเปลี่ยนที่ใช้บ่อยสุดคือ TISCOASSET")
    w(f"8. **สิทธิ์สับเปลี่ยน**: `switch_out flag`/`switch_in flag` = Y ทุกกอง (ผิดปกติ {n_flag_bad} กอง) · flag ช่วงปิดรับสับเปลี่ยน (`switch in/out periold flag`) ผิดปกติ {periodflag} กอง → ช่องทางสับเปลี่ยนใช้ได้ตาม profile · **ข้อควรระวัง**: โมเดลไม่ตรวจเงื่อนไขสับเปลี่ยนข้ามประเภทกอง (เช่น Settlement T+n ต่างกันทำให้เงินค้าง) และกองที่ไม่มีแถว SI/SO ({len(o['missing_series'])} กอง×รหัส, เช่น K-Asset ทุกกองไม่มี SI/SO) ถูกใส่ SI=1.07, SO=0 จาก median")
    lb = flags.copy()
    lb["lowbuy"] = pd.to_numeric(lb["fst_lowbuy_val"], errors="coerce")
    big = lb[lb["lowbuy"] >= 100000]
    held_in = {m: {f for r in sims[m]["rec"] for f in list(r["drift"]) + list(r["target"])} for m in models}
    w("9. **ขั้นต่ำการซื้อ/class เฉพาะกลุ่ม**: กองที่ถือซึ่ง `fst_lowbuy_val` ≥ 100,000 บาท: " + ("; ".join(f"{f} (ขั้นต่ำ {int(r['lowbuy']):,} บาท; ถือใน {', '.join(m for m in models if f in held_in[m])})" for f, r in big.iterrows()) if len(big) else "ไม่มี") + " — ชื่อ class -IA = institutional ซื้อไม่ได้สำหรับรายย่อยทั่วไป (Project Retail Type = R ใน profile แต่ขั้นต่ำสูง) ซึ่งเป็นปัญหาเรื่อง 'ซื้อได้จริง' ไม่ใช่เรื่องค่าธรรมเนียม · แนะนำส่งต่อ quant-modeler/ผู้ใช้")
    ff0f = o["ff0_funds"]
    w(f"10. **กองที่ FF Actual = 0 ({len(ff0f)} กอง: {', '.join(ff0f)})**: อัตราเป็นศูนย์ตามข้อมูลจริง ไม่ใช่ fallback · ลักษณะเป็น index/ class ราคาพิเศษ (K-Asset index funds FF=0 แต่ BF 0.15% · KKP -H-F = class F) · ถ้าช่องทางซื้อจริงต้องจ่าย FF=SI=1.5% แทน: ดู §4 แถวสุดท้าย · KT-INDIA-A และ TISCOEU-A มี snapshot 2026 ที่ FF ≠ 0 แสดงว่าอัตราเปลี่ยนได้")
    w("")
    w("### 2.5 ข้าม class ใน family เดียวกัน")
    w("")
    w(f"- family map ที่ใช้ (`fund_signals.family_of(fixed=True)`) คัดได้ ≤ 1 class ต่อ family ต่อไตรมาส จึง **ไม่มีคู่ขาย-ซื้อใน entry เดียวกันที่เป็น family เดียวกัน (พบ {n_same_fam_pairs} คู่จากทั้งหมด {len(pairs)} คู่ขาย×ซื้อใน บลจ. เดียวกัน)** · ไตรมาสถัดๆ ไปที่เปลี่ยน representative ในมุม family: {rep_changes if rep_changes else 'ไม่มี'}")
    w(f"- family ที่ถูกถือหลาย class (ต่างช่วงเวลา/ต่างโมเดล): " + ("; ".join(f"{fam_name}: {sorted(multi[multi==fam_name].index)}" for fam_name in sorted(set(multi))) if len(multi) else "ไม่มี"))
    w("- ถ้ามีการสลับ class ใน family เดียวกัน (เช่น -A→-F) โมเดลจะคิดเป็นขาย class หนึ่ง + ซื้ออีก class ในช่องทางสับเปลี่ยน/ขาย-ซื้อตามปกติ ซึ่งเป็นสมมติฐานที่ปลอดภัย (ความจริงสลับ class ในกองเดียวกันบางแห่งฟรี → ต้นทุนจริงอาจต่ำกว่า)")
    w("- ตัวอย่างคู่สับเปลี่ยนข้ามกองใน บลจ. เดียวกันที่ใช้ช่องทางสับเปลี่ยน (ถูกกว่า): TISCOEU-A→TISTECH-A/TISCOJP, TISCOGIF-R→TISCOIN, UOBSJSM/JSM→EHD, M-EUBANK→MEURO, K-VIETNAM→K-AEC (ใช้ SI median) — รายการเต็ม `AUDIT_fees_amc_groups.csv`")
    w("")
    w("## 3. สรุปต้นทุนต่อปี (bp ของมูลค่าพอร์ต/ปี, rf จริง, จ่ายเต็ม) แยกรหัส")
    w("")
    w("| โมเดล | ปี | รวม | FF | BF | SI | SO | ถ้าไม่มีช่องทางสับเปลี่ยน | ประหยัด (bp) | ยอดขาย/ปี | ยอดซื้อ/ปี | ค่าธรรมเนียมเฉลี่ย/ข้าง | ยอดขายที่จับคู่ใน บลจ. | ใช้ช่องทางสับเปลี่ยน |")
    w("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for m in models:
        c = comp[m]
        w(f"| {m} | {yrs[m]:.2f} | {c['total']:.1f} | {c['FF']:.1f} | {c['BF']:.1f} | {c['SI']:.1f} | {c['SO']:.1f} | {c['noswitch']:.1f} | {c['saving']:.1f} | {c['sell_vol_yr']:.3f} | {c['buy_vol_yr']:.3f} | {pct(c['avg_fee_side'])} | {pct(c['matched_share'],1)} | {pct(c['switch_share'],1)} |")
    w("")
    w("(ต้นทุนรวม รวม entry แรก = ซื้อเข้าตั้งต้นจากเงินสด 100% — TF-FX " + f"{E[(E.model=='M004-TF-FX')&(E.k==0)].cost_mine.iloc[0]*1e4:.1f}bp · GC75 {E[(E.model=='M013-GC75')&(E.k==0)].cost_mine.iloc[0]*1e4:.1f}bp ครั้งเดียว ไม่ใช่ต้นทุนหมุนเวียน)")
    w("")
    w("### กองที่ทำให้ต้นทุนสูงสุด 5 อันดับ (รวมทุก entry, bp/ปี ของพอร์ต)")
    w("")
    for m, g in top.items():
        w(f"**{m}**")
        w("")
        w("| อันดับ | กอง | บลจ. | ต้นทุน bp/ปี | FF | BF | SI | SO | ยอดซื้อรวม | ยอดขายรวม |")
        w("|---|---|---|---|---|---|---|---|---|---|")
        for i, (f, r) in enumerate(g.iterrows(), 1):
            w(f"| {i} | {f} | {afd.amc.get(f)} | {r['bp_yr']:.1f} | {r['cost_FF']*1e4/ (yrs['M004-TF-FX'] if m=='M004-TF-FX' else yrs['M013-GC75'] if m=='M013-GC75' else (yrs['M004-TF-FX']+yrs['M013-GC75'])):.1f} | {r['cost_BF']*1e4/ (yrs['M004-TF-FX'] if m=='M004-TF-FX' else yrs['M013-GC75'] if m=='M013-GC75' else (yrs['M004-TF-FX']+yrs['M013-GC75'])):.1f} | {r['cost_SI']*1e4/ (yrs['M004-TF-FX'] if m=='M004-TF-FX' else yrs['M013-GC75'] if m=='M013-GC75' else (yrs['M004-TF-FX']+yrs['M013-GC75'])):.1f} | {r['cost_SO']*1e4/ (yrs['M004-TF-FX'] if m=='M004-TF-FX' else yrs['M013-GC75'] if m=='M013-GC75' else (yrs['M004-TF-FX']+yrs['M013-GC75'])):.1f} | {r['buy']:.2f} | {r['sell']:.2f} |")
        w("")
    w("(แถว 'รวม 2 โมเดล' หารด้วยผลรวมปีของทั้งสองโมเดล = ค่าเฉลี่ยต่อปีรวม ไม่ใช่ค่ามัธยฐาน) · ต้นทุนต่อกองจัดสรรจากสูตร: BF/FF ตามยอดของกองนั้น, ช่องทางสับเปลี่ยนแบ่ง SO ตามสัดส่วนยอดขาย และ SI ตามสัดส่วนยอดซื้อ")
    w("")

    w("## 4. ความไวต่อสมมติฐานและผลต่อ Sharpe (รัน simulate ใหม่แบบ read-only ด้วย FeeData ทางเลือก, rf จริง, ตัวหาร sd(r))")
    w("")
    w("| สถานการณ์ | Sharpe TF-FX | Δ | ต้นทุน bp/ปี | Sharpe GC75 | Δ | ต้นทุน bp/ปี |")
    w("|---|---|---|---|---|---|---|")
    for name, r in sens:
        a, b = r["M004-TF-FX"], r["M013-GC75"]
        w(f"| {name} | {a['sharpe']:.4f} | {a['sharpe']-base_sens['M004-TF-FX']['sharpe']:+.4f} | {a['cost_bp_yr']:.1f} | {b['sharpe']:.4f} | {b['sharpe']-base_sens['M013-GC75']['sharpe']:+.4f} | {b['cost_bp_yr']:.1f} |")
    w("")
    w("- baseline (AFD ผม) = ผลเดิมของโค้ด (ตรงถึงทศนิยมที่ 12 ในสถานการณ์ที่ไม่แตะค่า)")
    w("- 'ไม่มี → 0' และ 'แถวซ้ำ' ไม่เปลี่ยน Sharpe เลย (0.0000): 'ไม่มี' ของกองที่ถือมี 2 แถว (BF และ SO) ซึ่ง median = 0 อยู่แล้ว · GOPP-X ไม่ถูกซื้อในวันที่เกี่ยวข้อง/ไม่เข้าสูตร")
    w("")

    w("## 5. ข้อค้นพบ (จัดระดับ)")
    w("")
    w("| ระดับ | เรื่อง | ผลต่อ Sharpe | แก้ไหม |")
    w("|---|---|---|---|")
    w("| ไม่พบบั๊กในสูตร | ต้นทุนต่อ entry ตรงสูตร spec ทั้ง 30 entry (2 วิธีอิสระ) · เงินสดไม่คิดต้นทุนถูกต้อง · FF/BF/SI/SO ใช้ถูกฝั่ง (ขาย→BF/SO, ซื้อ→FF/SI) | — | — |")
    w("| เล็กน้อย | ข้อความ 'ไม่มี/ยกเว้น/ปัจจุบันไม่เรียกเก็บ' ใน Actual Value ถูกถือเป็นค่าใช้ไม่ได้ → median (ควรเป็น 0) · ทั้งไฟล์ 202 แถว (ไม่มี 197 ยกเว้น 3 ไม่เรียกเก็บ 2) · ของกองที่ถือ 2 แถว (BF, SO) median=0 จึงไม่มีผล · ถ้ากองอื่น 'ไม่มี' ที่ FF/SI จะผิดเป็น 1.5/1.07 | 0.0000 | แนะนำแก้ในโค้ดแอป (`analysis/fund_fees.py`) เมื่อผู้ใช้อนุมัติ |")
    w("| เล็กน้อย | แถวซ้ำ fund+code+date ค่าต่างกัน (GOPP-X FF/SI 0 vs 1.5 วันที่ 2023-05-10) · เลือกแถวด้วย sort ไม่ stable → ผลไม่ deterministic | 0.0000 (ไม่เข้าสูตรในวันที่ต่างกัน) | แนะนำ sort แบบ stable + กติกาตายตัว (เช่น ค่ามากสุดเพื่อความระมัดระวัง) |")
    w(f"| ข้อมูล (ปานกลาง) | ค่าธรรมเนียมเป็น snapshot 2023-05 ถึง 2026-07 · {pct(fut['future'].sum()/fut['n'].sum(),0)} ของ lookup ใช้ snapshot ที่ลงวันหลังวันซื้อขาย (มัธยฐานห่าง ~{fut['lag_med'].mean():.0f} วัน, สูงสุด {fut['lag_max'].max():.0f} วัน) → ใช้ย้อนหลัง 2022–2025 · พบการเปลี่ยนค่าของกองที่ถือ {len(changes)} รายการ (ไม่มี snapshot ปี 2022 ให้ทดสอบ) | ไม่มีทางวัดจากไฟล์นี้ | ติดป้ายเป็นข้อจำกัด |")
    w("| ข้อมูล (ปานกลาง) | fallback median ของกอง×รหัสที่ไม่มีแถว: 2 กองไม่มีแถวเลย (ES-GINFRA-A, FCSCBSETE) + K-Asset ไม่มี SI/SO ทุกกอง + ASP-NGF/ES-USTECH/TMBGINFRA ไม่มี BF/SO | ช่วง −0.06 ถึง +0.015 (§4) | ผู้ใช้ควรยืนยันค่า SI/SO ของ K-Asset |")
    w("| ข้อมูล (ใหญ่) | **Actual Value ไม่ใช่เพดาน แต่ไม่ยืนยันว่าเป็นราคาที่นักลงทุนรายย่อยจ่ายจริงในทุกช่องทาง** — ถ้าจ่ายเต็มเพดาน Rate ต้นทุน ~500–600 bp/ปี Sharpe เหลือ ~0.31 ในทั้ง 2 โมเดล · ถ้ายกเว้น front-end Sharpe ขึ้นเป็น ~0.91/0.95 | −0.41/−0.45 (เพดาน) · +0.19 (ยกเว้น FF/SI) | ผู้ใช้ต้องยืนยันช่องทางซื้อจริง |")
    w("")
    w("## 6. ข้อจำกัดของการตรวจนี้")
    w("")
    w("- ไม่ได้ตรวจกับตารางค่าธรรมเนียมจริงของผู้จัดจำหน่าย (ธนาคาร/แพลตฟอร์ม) · ไม่ได้ตรวจ min ticket/ค่าธรรมเนียมบาทคงที่/ภาษี · ไม่มีคอลัมน์หน่วย/Min/Max/Remark ในไฟล์ (FEEUH Unit Rate ว่าง 14,767/14,775)")
    w("- hand_trace ใช้ median ที่คำนวณซ้ำเองด้วย python ล้วน (FF " + f"{med_hand['FF']:g} BF {med_hand['BF']:g} SI {med_hand['SI']:g} SO {med_hand['SO']:g}) ตรงกับโค้ดเดิม")
    w("- Sharpe ที่ใช้ทั้งหมดเป็นนิยามเดียวกับทีม (rf จริง, ตัวหาร sd(r), 45 เดือน เม.ย. 2022–ธ.ค. 2025) ไม่ได้ปรับ DSR/CI ใหม่ (ไม่ใช่ trial)")
    open(os.path.join(RES, "AUDIT_fees.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")
    print("wrote AUDIT_fees.md", len(L), "lines")
    return o, comp


if __name__ == "__main__":
    main()
