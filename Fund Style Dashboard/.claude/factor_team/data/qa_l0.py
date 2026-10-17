"""qa_l0.py — ส่วน QA + รายงานของ build_l0.py (สร้าง QA_L0.md และ reports/L0_summary.md จากตัวเลขที่คำนวณในรอบนี้)."""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

QS = [0.5, 0.75, 0.9, 0.95, 0.99, 1.0]
THR_GRID = [0.01, 0.02, 0.03, 0.05, 0.1, 0.2, 0.3, 0.5]


def tbl(df: pd.DataFrame, floatfmt="{:.3f}") -> str:
    cols = [str(c) for c in df.columns]
    out = ["| " + " | ".join(cols) + " |", "|" + "|".join(["---"] * len(cols)) + "|"]
    for _, r in df.iterrows():
        cells = []
        for v in r.tolist():
            if isinstance(v, (float, np.floating)):
                cells.append("" if pd.isna(v) else floatfmt.format(v))
            elif isinstance(v, pd.Timestamp):
                cells.append("" if pd.isna(v) else f"{v:%Y-%m-%d}")
            else:
                cells.append(str(v))
        out.append("| " + " | ".join(cells) + " |")
    return "\n".join(out)


def run(ctx: dict) -> None:
    u, cls, sel, n0, Rw, Rm, main_w = ctx["uni"], ctx["cls"], ctx["sel"], ctx["n0"], ctx["Rw"], ctx["Rm"], ctx["main_w"]
    Fw, Fm, cov, dup, pol, nav = ctx["Fw"], ctx["Fm"], ctx["cov"], ctx["dup"], ctx["pol"], ctx["nav"]
    spikes, thr, sc = ctx["spikes"], ctx["ZERO_THRESH"], ctx["sc"]
    MAIN_END, PANEL_END, MIN_WEEKS = ctx["MAIN_END"], ctx["PANEL_END"], ctx["MIN_WEEKS"]
    P = ("E", "F", "O")
    status: list[tuple[str, str, str]] = []   # (ข้อ, สถานะ, ตัวเลข)
    L: list[str] = []
    A = L.append

    # ---------------- Q1 ขั้นของ universe
    def cnt(mask):
        return {p: int((mask & (cls["policy"] == p)).sum()) for p in P}

    st = [("FundProfile 9 เกณฑ์", cnt(pd.Series(True, index=cls.index))),
          ("มี NAV ใช้ได้", cnt(cls["has_nav"])),
          (f"≥{MIN_WEEKS} ผลตอบแทนรายสัปดาห์ (2021–2025)", cnt(cls["has_nav"] & cls["ok_n"])),
          ("ผ่านเกณฑ์ zero-return (ชั่วคราว)", cnt(cls["eligible"])),
          ("1 class ต่อกอง (family) = panel", cnt(cls["selected"]))]
    stage_df = pd.DataFrame([{"ขั้น": k, **v, "รวม": sum(v.values())} for k, v in st])
    tot0 = sum(n0.values())
    exp_ok = (n0.get("E"), n0.get("F"), n0.get("O")) == (600, 77, 38)
    status.append(("Universe 9 เกณฑ์ = 715 (E600/F77/O38)", "ผ่าน" if exp_ok else "เตือน", f"{tot0} = E{n0.get('E')}/F{n0.get('F')}/O{n0.get('O')}"))

    # ---------------- Q2 zero-return
    base = cls[cls["has_nav"] & cls["ok_n"]]
    qz = base.groupby("policy")["zero_frac"].quantile(QS).unstack()
    qz.columns = [f"q{int(q * 100)}" for q in QS]
    qz.insert(0, "n_class", base.groupby("policy").size())
    qz = qz.reset_index()
    rows = []
    for p in P:
        b = base[base["policy"] == p]
        rows.append({"policy": p, **{f">{t:.2f}": int((b["zero_frac"] > t).sum()) for t in THR_GRID}})
    ex_df = pd.DataFrame(rows)
    # กองที่ถูกตัดเพราะ zero_frac ที่เกณฑ์ชั่วคราว
    cut = cls[cls["has_nav"] & cls["ok_n"] & ~cls["ok_zero"]]
    status.append(("สัดส่วนสัปดาห์ return=0 (เกณฑ์ชั่วคราว E/F/O = " + "/".join(f"{thr[p]:.2f}" for p in P) + ")",
                   "เตือน", f"ตัด {len(cut)} class (E{(cut.policy == 'E').sum()}/F{(cut.policy == 'F').sum()}/O{(cut.policy == 'O').sum()}) · รอผู้ใช้ยืนยัน"))

    # ---------------- Q3 family
    diff = [(c, ctx["fam_old"][c], ctx["fam_new"][c]) for c in ctx["codes"] if ctx["fam_old"][c] != ctx["fam_new"][c]]
    multi_pol = cls.groupby("family")["policy"].nunique()
    multi_pol = multi_pol[multi_pol > 1]
    divonly = sel[sel["div_flag"] == "Y"]
    fam_n = cls.groupby("family").size()
    status.append(("family: ตัด suffix/ CSV", "ผ่าน" if len(multi_pol) == 0 else "เตือน",
                   f"{cls['family'].nunique()} family จาก {len(cls)} class · family ที่มี policy ปนกัน {len(multi_pol)} · fixed=False vs True ต่างกัน {len(diff)} กอง"))
    status.append(("panel มี class ปันผลเพราะ family ไม่มี class อื่นที่ผ่าน", "เตือน" if len(divonly) else "ผ่าน",
                   f"{len(divonly)} กอง (E{(divonly.policy == 'E').sum()}/F{(divonly.policy == 'F').sum()}/O{(divonly.policy == 'O').sum()})"))

    # ---------------- Q4 ความสด
    s = sel.copy()
    s["nav_last"] = pd.to_datetime(s["nav_last"])
    fr = []
    for p in P:
        x = s[s.policy == p]
        fr.append({"policy": p, "n": len(x), "last NAV < 2025-12-31": int((x.nav_last < MAIN_END).sum()),
                   "last NAV < 2026-07-31 (ปลาย panel)": int((x.nav_last < PANEL_END - pd.Timedelta(days=10)).sum()),
                   "last NAV ≥ 2026-07-21": int((x.nav_last >= PANEL_END - pd.Timedelta(days=10)).sum())})
    fresh_df = pd.DataFrame(fr)
    stale_main = int((s.nav_last < MAIN_END).sum())
    status.append(("ความสดของ NAV (point-in-time · กองเลิก/stale อยู่ใน panel เฉพาะช่วงที่มี NAV)", "เตือน" if stale_main else "ผ่าน",
                   f"{stale_main} กองใน panel มี NAV สุดท้ายก่อน 2025-12-31 (จบก่อนสิ้นช่วงหลัก)"))

    # ---------------- Q5/Q6 รู + จำนวนกองต่อสัปดาห์
    nsel = {p: int((s.policy == p).sum()) for p in P}
    sel2 = sel.copy()
    nf = pd.to_datetime(sel2["nav_first"]).to_numpy("datetime64[D]")
    nl = pd.to_datetime(sel2["nav_last"]).to_numpy("datetime64[D]")
    wkD = pd.DatetimeIndex(cov.index).to_numpy("datetime64[D]")
    alive = pd.Series([int(((nf <= d - np.timedelta64(7, "D")) & (nl >= d)).sum()) for d in wkD], index=cov.index)
    ratio = cov["ALL"] / alive.replace(0, np.nan)
    mainc = cov.loc[(cov.index > ctx["MAIN_START"]) & (cov.index <= MAIN_END)]
    cdf = pd.DataFrame({p: [nsel[p], int(mainc[p].min()), float(mainc[p].median()), int(mainc[p].max()),
                            int(cov[p].iloc[0]), int(mainc[p].iloc[-1])] for p in P},
                       index=["n กองใน panel", "min/สัปดาห์ (2021–25)", "median", "max", "สัปดาห์แรก (2021-01-08)", "สัปดาห์สุดท้ายช่วงหลัก"]).reset_index().rename(columns={"index": "รายการ"})
    qi = pd.PeriodIndex(cov.index, freq="Q")
    q_df = pd.DataFrame({"ไตรมาส": cov.groupby(qi).size().index.astype(str),
                         "กองที่ NAV ยังอยู่ (alive)": alive.groupby(qi).mean().to_numpy(),
                         "กองที่มี return": cov["ALL"].groupby(qi).mean().to_numpy(),
                         "สัดส่วน (มี return/alive)": ratio.groupby(qi).mean().to_numpy()})
    q_show = q_df[(q_df["สัดส่วน (มี return/alive)"] < 0.95)]

    def runs_of(mask):
        out, start, ix = [], None, list(mask.index)
        for i, d in enumerate(ix):
            if mask.iloc[i] and start is None:
                start = d
            if start is not None and (not mask.iloc[i] or i == len(ix) - 1):
                out.append((start, ix[i - 1] if not mask.iloc[i] else d))
                start = None
        return out

    runs = runs_of(ratio < 0.5)
    runs2 = runs_of(ratio < 0.9)
    runs_txt = "; ".join(f"{a:%Y-%m-%d}→{b:%Y-%m-%d}" for a, b in runs) or "ไม่มี"
    runs2_txt = "; ".join(f"{a:%Y-%m-%d}→{b:%Y-%m-%d}" for a, b in runs2) or "ไม่มี"
    med_all = float(mainc["ALL"].median())
    status.append(("รูที่เกิดพร้อมกันหลายกอง (มี return/alive < 50%)", "เตือน" if runs else "ผ่าน", runs_txt))
    status.append(("รูย่อย (มี return/alive < 90%)", "เตือน" if runs2 else "ผ่าน", runs2_txt))
    status.append(("จำนวนกองต่อสัปดาห์ในช่วงหลัก (ALL · unbalanced เพราะกองเปิดใหม่ทยอยเข้า)", "เตือน" if cov["ALL"].iloc[0] < 0.6 * med_all else "ผ่าน",
                   f"min {int(mainc['ALL'].min())} (สัปดาห์แรก) / median {med_all:.0f} / max {int(mainc['ALL'].max())}"))

    # สาเหตุที่ class ไม่ถึง 52 สัปดาห์
    nn = cls[cls["has_nav"] & ~cls["ok_n"]].copy()
    def why(r):
        if pd.notna(r.nav_first) and r.nav_first > pd.Timestamp("2024-12-31"):
            return "NAV เริ่มหลัง 2024-12-31 (กองใหม่)"
        if pd.notna(r.nav_last) and r.nav_last < pd.Timestamp("2022-01-01"):
            return "NAV จบก่อน 2022"
        if r.nav_holes > 0:
            return "มีรู NAV > 10 วันทำการ"
        return "อื่นๆ (NAV ถี่ไม่พอ/สั้น)"
    nn["สาเหตุ"] = [why(r) for r in nn.itertuples()]
    why_df = nn.groupby(["สาเหตุ", "policy"]).size().unstack(fill_value=0).reindex(columns=list(P), fill_value=0).reset_index()
    noNav = cls[~cls["has_nav"]]

    # สัญญาณ F-rule (quant_team M015 §4.2) แบบตรวจอย่างเดียว
    spk_f = ctx["spk_f"]
    fr_df = pd.DataFrame([{"policy": p, "จุดที่เข้า F-rule": int((spk_f.policy == p).sum()),
                           "ถูกใช้เป็น NAV asof ของสัปดาห์": int(((spk_f.policy == p) & spk_f.used_as_weekly_asof).sum()),
                           "กองที่เกี่ยวข้อง": int(spk_f[spk_f.policy == p].FundCode.nunique())} for p in P])

    # ---------------- Q7 spike
    sp_in = spikes[spikes["FundCode"].isin(sc)] if len(spikes) else spikes
    mag = (spikes["nav_before"] / spikes["nav_after"] - 1).abs() if len(spikes) else pd.Series(dtype=float)
    status.append(("spike ที่แก้ (clean_nav_spikes)", "ผ่าน",
                   f"{len(spikes)} จุด/{spikes['FundCode'].nunique() if len(spikes) else 0} กอง (ใน panel {len(sp_in)} จุด/{sp_in['FundCode'].nunique() if len(sp_in) else 0} กอง) · |ขนาด| สูงสุด {mag.max() if len(mag) else 0:.1%}"))
    status.append(("spike กอง F ที่กฎ F-rule ของ quant_team จับได้แต่ตัวแก้หุ้นไม่แก้ (ตรวจอย่างเดียว)", "เตือน" if len(ctx["spk_f"]) else "ผ่าน",
                   f"{len(ctx['spk_f'])} จุด ใน {ctx['spk_f'].FundCode.nunique()} กอง · ถูกใช้เป็น NAV asof ของสัปดาห์ {int(ctx['spk_f'].used_as_weekly_asof.sum())} จุด"))
    # return สุดโต่งที่เหลือใน panel
    ext = main_w[sc].abs()
    big = int((ext > 0.5).sum().sum())
    ii, jj = np.where(ext.to_numpy() > 0.5)
    bigl = [(ext.columns[j], ext.index[i], main_w.loc[ext.index[i], ext.columns[j]]) for i, j in zip(ii, jj)]
    status.append(("return รายสัปดาห์ |r|>50% ที่เหลือใน panel (ช่วงหลัก)", "เตือน" if big else "ผ่าน", f"{big} จุด" + (": " + ", ".join(f"{c}@{d:%Y-%m-%d}={r:+.0%}" for c, d, r in bigl[:8]) if big else "")))

    # ---------------- Q8 factor inputs
    fgroup = ctx["fgroup"]
    mw = Fw.loc[(Fw.index > ctx["MAIN_START"]) & (Fw.index <= MAIN_END)]
    mm = Fm.loc[(Fm.index > ctx["MAIN_START"]) & (Fm.index <= MAIN_END)]
    rows = []
    for c in Fw.columns:
        x = mw[c]
        z = (x - x.mean()) / x.std()
        xm = mm[c]
        rows.append({"factor": c, "group": fgroup.get(c, ""), "n_w": int(x.notna().sum()), "NaN_w": int(x.isna().sum()),
                     "zero_w": float(((x == 0) & x.notna()).sum() / max(x.notna().sum(), 1)),
                     "zero_m": float(((xm == 0) & xm.notna()).sum() / max(xm.notna().sum(), 1)),
                     "mean_w": x.mean(), "sd_w": x.std(), "min_w": x.min(), "max_w": x.max(), "n|z|>6": int((z.abs() > 6).sum()),
                     "first_valid": Fw.index[Fw[c].notna()].min() if Fw[c].notna().any() else pd.NaT})
    fq = pd.DataFrame(rows)
    nan_main = fq[(fq["NaN_w"] > 0) & ~fq["factor"].str.contains("late")]
    zero_hi = fq[(fq["zero_w"] > 0.10) & ~fq["factor"].str.contains("_d|_lvl|late")]
    outl = fq[fq["n|z|>6"] > 0]
    status.append(("factor inputs: NaN ในช่วงหลัก (ไม่นับ spread IG/HY)", "ผ่าน" if nan_main.empty else "เตือน",
                   "ไม่มี" if nan_main.empty else ", ".join(f"{r.factor}:{r.NaN_w}" for r in nan_main.itertuples())))
    od = []
    for _, r in outl.iterrows():
        x = mw[r["factor"]]
        z = ((x - x.mean()) / x.std()).abs()
        od.append(f"{r['factor']}@{z.idxmax():%Y-%m-%d}({x[z.idxmax()]:+.3g})")
    status.append(("factor inputs: ค่าสุดโต่ง |z|>6 รายสัปดาห์ (เหตุการณ์จริงของตลาด · ไม่แก้)", "เตือน" if od else "ผ่าน", "ไม่มี" if not od else ", ".join(od)))
    tdw, tdm = fq.loc[fq.factor == "TDEX_THB", "zero_w"].iloc[0], fq.loc[fq.factor == "TDEX_THB", "zero_m"].iloc[0]
    status.append(("TDEX (proxy หุ้นไทย): สัปดาห์ที่ return = 0", "เตือน" if tdw > 0.03 else "ผ่าน", f"รายสัปดาห์ {tdw:.1%} · รายเดือน {tdm:.1%} (รายวันตามไฟล์ ~11.8%)"))
    ig = Fw["IG_OAS_late_d"].notna()
    status.append(("IG/HY spread FRED (มีแค่ 2023-10+)", "เตือน", f"valid ตั้งแต่ {Fw.index[ig].min():%Y-%m-%d} · ใช้ในช่วงหลัก 2021–2025 ไม่ได้ (เก็บไว้ ติดป้าย _late)"))
    # THB check
    from_acwi = (Fw["ACWI_ETF_USD"] + 1) * (Fw["USDTHB"] + 1) - 1
    cc = pd.concat([Fw["MSCI_ACWI"], from_acwi], axis=1).dropna()
    ccorr = float(cc.corr().iloc[0, 1])
    status.append(("MSCI_ACWI (บาท) vs ACWI ETF USD×USDTHB (รายสัปดาห์)", "ผ่าน" if ccorr > 0.8 else "เตือน", f"corr {ccorr:.3f} (n={len(cc)}) · ต่างเวลาปิด NY/เอเชีย"))
    rf_ann = float(mw["RF_BOT"].mean() * 52)
    status.append(("rf ธปท. ทบต้นรายวัน", "ผ่าน", f"ค่าเฉลี่ยรายสัปดาห์ ×52 = {rf_ann:.2%}/ปี (2021–2025) · ต่ำสุด {mw['RF_BOT'].min():.5f} สูงสุด {mw['RF_BOT'].max():.5f}"))
    est = [c for c in Fw.columns if c.endswith("_est_ret")]
    est_rows = pd.DataFrame({"est_ret": est, "mean_w": [mw[c].mean() for c in est], "sd_w": [mw[c].std() for c in est]})
    emon = {c: float(mw[c].corr(mw[c.replace("_est_ret", "_d")])) for c in est}
    status.append(("ผลตอบแทนบอนด์ไทยประมาณจาก yield (สูตร duration)", "เตือน", "ชั่วคราว · ต้องให้ผู้ใช้ตัดสินใจ · corr กับ Δyield: " + ", ".join(f"{k.split('_est')[0]} {v:.2f}" for k, v in emon.items())))

    # ---------------- Q9 เทียบ cache quant_team
    cdir = os.path.join(ctx["ROOT"], ".claude", "quant_team", "backtest", "cache")
    cmp_rows = []
    nv = nav.copy()
    nv["NAVDate"] = pd.to_datetime(nv["NAVDate"])
    mine_fix = set(zip(spikes["FundCode"], pd.to_datetime(spikes["NAVDate"]))) if len(spikes) else set()
    for name, fn in (("F: m015_navF_clean", "m015_navF_clean.parquet"), ("O: r1_navO_all", "r1_navO_all.parquet")):
        ca = pd.read_parquet(os.path.join(cdir, fn))
        ca["NAVDate"] = pd.to_datetime(ca["NAVDate"])
        ca["FundCode"] = ca["FundCode"].astype(str).str.strip()
        if "spike_fixed" not in ca:
            ca["spike_fixed"] = False
        ca = ca[["FundCode", "NAVDate", "NAV", "spike_fixed"]]
        common = sorted(set(ca["FundCode"]) & set(nv["FundCode"]))
        c1 = ca[ca["FundCode"].isin(common)]
        m1 = nv[nv["FundCode"].isin(common) & (nv["NAVDate"] >= c1["NAVDate"].min())]
        mg = c1.merge(m1[["FundCode", "NAVDate", "NAV"]], on=["FundCode", "NAVDate"], how="outer", suffixes=("_c", "_m"), indicator=True)
        both = mg[mg["_merge"] == "both"].copy()
        both["rel"] = (both["NAV_c"] - both["NAV_m"]).abs() / both["NAV_m"]
        dif = both[both["rel"] > 1e-9]
        lo = mg[mg["_merge"] == "right_only"]
        cmax = c1["NAVDate"].max()
        dif_l0fix = int(sum((a, b) in mine_fix for a, b in zip(dif["FundCode"], dif["NAVDate"])))
        cmp_rows.append({"cache": name, "funds ซ้อน": len(common), "keys ซ้อน": len(both),
                         "เฉพาะ cache": int((mg["_merge"] == "left_only").sum()),
                         "เฉพาะ L0 (NAVDate>cache max)": int((lo["NAVDate"] > cmax).sum()),
                         "เฉพาะ L0 (อื่น)": int((lo["NAVDate"] <= cmax).sum()),
                         "keys NAV ต่าง": len(dif),
                         "..ต่างเพราะ cache แก้ spike (F-rule) แต่ L0 ไม่": int(dif["spike_fixed"].sum()),
                         "..ต่างเพราะ L0 แก้ แต่ cache ไม่": dif_l0fix,
                         "..ต่างอื่น": int(len(dif) - dif["spike_fixed"].sum() - dif_l0fix)})
    cmp_df = pd.DataFrame(cmp_rows)
    oth = int(cmp_df["เฉพาะ L0 (อื่น)"].sum() + cmp_df["เฉพาะ cache"].sum() + cmp_df["..ต่างอื่น"].sum())
    status.append(("เทียบ NAV กับ cache quant_team (กองที่ซ้อนกัน)", "ผ่าน" if oth == 0 else "เตือน",
                   f"keys ซ้อน {int(cmp_df['keys ซ้อน'].sum())} · NAV ต่างเพราะกฎ spike ต่างกัน {int(cmp_df.iloc[:,7].sum() + cmp_df.iloc[:,8].sum())} key · NAV ต่างอื่น/แถวไม่ตรงนอกจากข้อมูลใหม่หลังวันสร้าง cache = {oth}"))

    # ---------------- Q10 corr ซ้ำ
    n_dup_cross = int((~dup["same_family"]).sum()) if len(dup) else 0
    par = {}

    def find(x):
        par.setdefault(x, x)
        while par[x] != x:
            par[x] = par[par[x]]
            x = par[x]
        return x
    for r in dup.itertuples():
        par[find(r.a)] = find(r.b)
    comp = {}
    for x in list(par):
        comp.setdefault(find(x), []).append(x)
    n_comp, n_drop = len(comp), sum(len(v) - 1 for v in comp.values())
    status.append((f"กองที่ return ซ้ำกัน corr>{0.99} (ข้าม family)", "เตือน" if n_dup_cross else "ผ่าน", f"{n_dup_cross} คู่ (ภายใน family เดียวกัน {int(dup['same_family'].sum()) if len(dup) else 0} คู่) · {n_comp} กลุ่ม ตัดได้ {n_drop} กอง"))

    # ---------------- monthly
    mcov = Rm[sc].notna().sum(axis=1)
    status.append(("panel รายเดือน", "ผ่าน", f"{len(Rm)} เดือน (2021-01 → 2026-07) · กองมี return/เดือน: min {int(mcov.min())} median {mcov.median():.0f} max {int(mcov.max())} · Jan-2021: MSCI ไม่มีระดับ ธ.ค.-2020 → factor MSCI เดือนแรก = NaN"))

    # ---------------- Q11 ขนาด sub-panel ที่ L1 ใช้ได้
    mw_all = main_w[sc]
    h1 = mw_all.loc[mw_all.index <= pd.Timestamp("2023-12-31")]
    h2 = mw_all.loc[mw_all.index > pd.Timestamp("2023-12-31")]
    nfull = len(mw_all)
    bal_rows = []
    for p in P:
        cc = [c for c in sc if pol[c] == p]
        v, v1, v2 = mw_all[cc].notna().sum(), h1[cc].notna().sum(), h2[cc].notna().sum()
        bal_rows.append({"policy": p, "กองใน panel": len(cc), f"ครบ {nfull} สัปดาห์ (balanced เต็ม)": int((v == nfull).sum()),
                         f"≥90% ของ {nfull}": int((v >= 0.9 * nfull).sum()),
                         f"ครบ {len(h1)} สัปดาห์ 2021–23": int((v1 == len(h1)).sum()),
                         f"≥52 สัปดาห์ใน 2021–23 และ ≥52 ใน 2024–25": int(((v1 >= 52) & (v2 >= 52)).sum()),
                         f"ครบ {len(h2)} สัปดาห์ 2024–25": int((v2 == len(h2)).sum())})
    bal_df = pd.DataFrame(bal_rows)

    # ---------------- เขียน QA_L0.md
    A(f"# QA L0 — panel และ factor inputs ({ctx['today']})")
    A("")
    A("สร้างโดย `build_l0.py` (รันซ้ำได้) · ตัวเลขทั้งหมดมาจากการรันรอบนี้ · ช่วงหลัก 2021-01-01 → 2025-12-31 · panel ถึง 2026-07-31 (2026 ดูประกอบ)")
    A("รอบก่อน: ไม่มี (L0 รอบแรก) → ไม่มี \"สิ่งที่เปลี่ยนจากรอบก่อน\"")
    A("")
    A("## สรุปสถานะ")
    A("")
    A(tbl(pd.DataFrame(status, columns=["ข้อ QA", "สถานะ", "ตัวเลข / หมายเหตุ"])))
    A("")
    A("## Q1 จำนวนกองแต่ละขั้น")
    A("")
    A(tbl(stage_df))
    A("")
    A("## Q2 หลักฐานเกณฑ์ zero-return ต่อ policy")
    A("")
    A("zero_frac = สัดส่วนสัปดาห์ (ผลตอบแทนที่คำนวณได้ในช่วง 2021-01-08 → 2025-12-31) ที่ return = 0 พอดี (NAV asof เท่าเดิม) · ฐาน = class ที่มี NAV และผ่านเกณฑ์ ≥52 สัปดาห์")
    A("")
    A("การกระจาย (quantile) ของ zero_frac:")
    A("")
    A(tbl(qz))
    A("")
    A("จำนวน class ที่ถูกตัดถ้าตั้งเกณฑ์ \"zero_frac > t\":")
    A("")
    A(tbl(ex_df))
    A("")
    A(f"เกณฑ์ที่ใช้ชั่วคราวใน build นี้: E {thr['E']:.2f} · F {thr['F']:.2f} · O {thr['O']:.2f} (ดู \"ต้องให้ผู้ใช้ตัดสินใจ\")")
    A("")
    A("## Q3 family และ 1 class ต่อกอง")
    A("")
    A(f"- {len(cls)} class → {cls['family'].nunique()} family · เลือก {len(sel)} class (ตัวแทน = ไม่ปันผลก่อน → n_weeks มากสุด → NAV เริ่มเร็วสุด → ชื่อ)")
    A(f"- family_of(fixed={ctx['FAMILY_FIXED']}) ใช้เป็นหลัก · เทียบกับ fixed={not ctx['FAMILY_FIXED']} ต่างกัน {len(diff)} กอง" + (": " + ", ".join(f"{a}: {b} → {c}" for a, b, c in diff[:12]) if diff else ""))
    A(f"- family ที่ policy ปนกัน: {len(multi_pol)}" + (" — " + ", ".join(multi_pol.index[:10]) if len(multi_pol) else ""))
    A(f"- กองใน panel ที่เป็น class ปันผล (family ไม่มี class ไม่ปันผลที่ผ่านเกณฑ์): {len(divonly)} — NAV ไม่รวมปันผล → return ต่ำกว่าจริง: " + ", ".join(divonly["FundCode"].tolist()[:30]))
    A("")
    A("## Q4 ความสดของ NAV (กองใน panel)")
    A("")
    A(tbl(fresh_df))
    A("")
    A("## Q5–Q6 รูที่เกิดพร้อมกัน และจำนวนกองต่อสัปดาห์")
    A("")
    A(tbl(cdf, "{:.0f}"))
    A("")
    A(f"- ช่วงที่กองที่มี return < 50% ของกองที่ NAV ยังอยู่ (alive): {runs_txt}")
    A(f"- ช่วงที่ < 90%: {runs2_txt}")
    A("- alive = nav_first ≤ วัน−7 และ nav_last ≥ วัน · จำนวนกองใน panel เพิ่มขึ้นตลอดช่วงเพราะกองเปิดใหม่ (unbalanced) ไม่ใช่รู")
    A("- ไตรมาสที่ สัดส่วน (มี return/alive) < 95%:")
    A("")
    A(tbl(q_show))
    A("")
    A("รายสัปดาห์เต็ม: `coverage_weekly.csv`")
    A("")
    A("### class ที่ NAV มีแต่ไม่ถึง 52 ผลตอบแทนรายสัปดาห์ (2021–2025) — สาเหตุ")
    A("")
    A(tbl(why_df, "{:.0f}"))
    A("")
    A(f"- ไม่มี NAV ใช้ได้เลย {len(noNav)} class: " + ", ".join(noNav["FundCode"].tolist()[:40]) + (" ..." if len(noNav) > 40 else ""))
    A("")
    A("## Q7 spike")
    A("")
    A(f"- แก้ในหน่วยความจำด้วย `clean_nav_spikes`: {len(spikes)} จุด · log: `spike_fixes.csv`")
    A(f"- return รายสัปดาห์ |r|>50% ที่เหลือใน panel: {big} จุด")
    A("- ตัวแก้ของหุ้น (8×MAD) อาจพลาด spike ในกอง F ที่ vol ต่ำ · quant_team M015 §4.2 ใช้กฎ |r_in|>0.5% & |r_out|>0.5% & ตรงข้าม & |รวม|<0.1% กับกอง F — ที่นี่ตรวจเฉพาะกอง F ใน panel (กับ E/O ลองแล้วจับ noise รายวันปกติเป็นพัน จึงไม่ใช้) **ตรวจอย่างเดียว ไม่แก้** (รายชื่อ: `spike_candidates_Frule.csv`):")
    A("")
    A(tbl(fr_df, "{:.0f}"))
    A("")
    A("## Q8 factor inputs (ช่วงหลัก รายสัปดาห์)")
    A("")
    A("`_d` = Δ ระดับ (pp หรือจุด) · `_lvl` = ระดับปลายช่วง · `_est_ret` = ผลตอบแทนบอนด์ไทยประมาณ (ชั่วคราว) · `_late` = FRED spread ใช้ในช่วงหลักไม่ได้ · กลุ่มของทุกคอลัมน์: `factor_groups.csv`")
    A("")
    show = fq.drop(columns=["group"]).copy()
    A(tbl(show, "{:.4f}"))
    A("")
    A("ผลตอบแทนบอนด์ไทยประมาณ (สูตร: ret = y₀·days/365 − D_mod(y₀,n)·Δy · D_mod = (1−(1+y₀/2)^(−2n))/y₀ · n = " + ", ".join(f"{k}:{v}" for k, v in ctx["YIELD_TENORS"].items()) + " ปี):")
    A("")
    A(tbl(est_rows, "{:.5f}"))
    A("")
    A("## Q9 เทียบ NAV กับ cache ของ quant_team (อ่านอย่างเดียว)")
    A("")
    A(tbl(cmp_df, "{:.2e}"))
    A("")
    A("## Q10 คู่กองที่ return ซ้ำกัน (corr > 0.99 · ช่วงหลักรายสัปดาห์ · ≥52 จุดซ้อน)")
    A("")
    A(tbl(dup[["a", "b", "corr", "same_family"]].head(60), "{:.4f}") if len(dup) else "ไม่มี")
    A("")
    A(f"รวม {len(dup)} คู่ (ข้าม family {n_dup_cross}) — {n_comp} กลุ่มที่เชื่อมกัน · ถ้าเหลือ 1 กองต่อกลุ่มจะตัด {n_drop} กอง — ยังคงอยู่ใน panel ทั้งหมด (ไม่ตัดอัตโนมัติ) · รายคู่ทั้งหมด `dup_pairs.csv`")
    A("")
    A("## Q11 ขนาด sub-panel สำหรับ L1 (กระทบชั้นถัดไป)")
    A("")
    A(tbl(bal_df, "{:.0f}"))
    A("")
    A("## ต้องให้ผู้ใช้ตัดสินใจ")
    A("")
    A(_decisions(ctx, qz, ex_df, cut, n_dup_cross, divonly, runs))
    A("")
    A("## ข้อจำกัด")
    A("")
    A("- FundProfile เป็น snapshot ปัจจุบัน (ไม่ใช่ point-in-time) · NAV class ปันผลไม่รวมปันผล · NAV 2026 มีรูใหญ่ · ETF ปิดเวลา NY, ค่าเงิน/MSCI ต่างเวลาปิดกับ NAV ไทย")
    A("- ผลตอบแทนใช้ NAV asof ณ วันศุกร์ (ห่างไม่เกิน 10 วันปฏิทิน) → กองที่ NAV ออกไม่ทุกวันจะมีสัปดาห์ return=0 (นับใน zero_frac)")
    A("- `RF_BOT` สมมติอัตรามีผลวันประกาศ MPC · act/365")
    A("- ความสามารถ reproduce: ดู `repro_check.json` (เทียบ sha256 ผล 2 รอบ)")
    with open(os.path.join(ctx["OUT"], "QA_L0.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")

    # ---------------- L0_summary.md
    S = []
    S.append(f"# L0 summary — ข้อมูลพื้นฐานทีม factor ({ctx['today']})")
    S.append("")
    S.append("รายละเอียด/ตาราง QA: `.claude/factor_team/data/QA_L0.md` · สร้างโดย `.claude/factor_team/data/build_l0.py`")
    S.append("")
    S.append("## จำนวนกองแต่ละขั้น")
    S.append("")
    S.append(tbl(stage_df))
    S.append("")
    S.append("## ช่วงข้อมูล")
    S.append("")
    S.append(f"- ช่วงหลัก 2021-01-01 → 2025-12-31 · panel รายสัปดาห์ {Rw.index[0]:%Y-%m-%d} → {Rw.index[-1]:%Y-%m-%d} ({len(Rw)} สัปดาห์) · รายเดือน {Rm.index[0]:%Y-%m} → {Rm.index[-1]:%Y-%m} ({len(Rm)} เดือน) · 2026 ดูประกอบ (NAV มีรู)")
    S.append(f"- factor inputs: MSCI 28 (บาท) · style 4 + ACWI ETF · macro 7 + ทองบาท · rf ธปท. · AGG/IEF/SHV/LQD/HYG/EMB (USD และบาท) · TDEX (proxy หุ้นไทย) · yield บอนด์ไทย (ระดับ, Δ, ผลตอบแทนประมาณ) · DTB3 · IG/HY spread (_late)")
    S.append("")
    S.append("## สถานะ QA")
    S.append("")
    S.append(tbl(pd.DataFrame(status, columns=["ข้อ QA", "สถานะ", "ตัวเลข / หมายเหตุ"])))
    S.append("")
    S.append("## กระทบ L1: ขนาด sub-panel (ช่วงหลักรายสัปดาห์)")
    S.append("")
    S.append(tbl(bal_df, "{:.0f}"))
    S.append("")
    S.append("## ข้อจำกัด")
    S.append("")
    S.append("- FundProfile เป็น snapshot ปัจจุบัน · NAV class ปันผลไม่รวมปันผล · NAV 2026 มีรู (ม.ค.–มิ.ย.) · ETF ปิดเวลา NY · TDEX เป็น SET50 สภาพคล่องต่ำ ไม่ใช่ SET ทั้งตลาด")
    S.append("- IG/HY spread มีแค่ 2023-10+ (ใช้ LQD/HYG แทน) · ผลตอบแทนบอนด์ไทยเป็นค่าประมาณจาก yield (ชั่วคราว)")
    S.append("")
    S.append("## ต้องให้ผู้ใช้ตัดสินใจ")
    S.append("")
    S.append(_decisions(ctx, qz, ex_df, cut, n_dup_cross, divonly, runs))
    with open(os.path.join(ctx["REPORT_DIR"], "L0_summary.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(S) + "\n")


def _decisions(ctx, qz, ex_df, cut, n_dup_cross, divonly, runs) -> str:
    thr = ctx["ZERO_THRESH"]
    cls = ctx["cls"]
    base = cls[cls["has_nav"] & cls["ok_n"]]
    mx = base.groupby("policy")["zero_frac"].max()
    e3 = ex_df.set_index("policy")[">0.03"]
    e2 = ex_df.set_index("policy")[">0.02"]
    spk = ctx["spk_f"]
    T = []
    T.append(f"1. **เกณฑ์สัดส่วนสัปดาห์ return=0 ต่อ policy** — ข้อมูลจริง: zero_frac สูงสุด E {mx.get('E', float('nan')):.3f} / F {mx.get('F', float('nan')):.3f} / O {mx.get('O', float('nan')):.3f} (ตาราง Q2) · "
             f"กอง F ที่นี่ไม่ใช่ตลาดเงิน (policy M ถูกตัดโดย 9 เกณฑ์แล้ว) จึงไม่ต้องผ่อนเกณฑ์ให้ F · **เสนอ 0.10 ทุก policy** (ใช้ชั่วคราวใน build นี้ = ตัด {len(cut)} class เพราะเกณฑ์นี้) · "
             f"ถ้าเข้มกว่านี้: เกณฑ์ 0.03 ตัด E{e3.get('E', 0)}/F{e3.get('F', 0)}/O{e3.get('O', 0)} class · 0.02 ตัด E{e2.get('E', 0)}/F{e2.get('F', 0)}/O{e2.get('O', 0)} class · "
             "ตัวกรองที่มีผลจริงคือเกณฑ์ ≥52 สัปดาห์ + กฎรู NAV 10 วันทำการ (กองที่ NAV ไม่รายวันหลุดตรงนั้น) · ขอให้ยืนยัน/ระบุค่าใหม่")
    T.append("2. **ผลตอบแทนบอนด์ไทย** — ไม่มีราคาบอนด์ จึงเก็บ yield ระดับ + Δyield (ตัวหลัก) และประมาณผลตอบแทนด้วย ret = y₀·days/365 − D_mod(y₀,n)·Δy (D_mod ของ par bond รายครึ่งปี · n = 1/5/10 ปี, T-bill 3M = 0.25 ปี · ไม่มี convexity) ติดป้าย `_est_ret` = ชั่วคราว · ถ้าจะใช้เป็นตัวหลัก ขอให้ยืนยันสูตร/duration หรือเสนอแหล่งดัชนีบอนด์ไทยจริง (ต้องดาวน์โหลดเพิ่ม)")
    T.append(f"3. **spike ในกอง F ที่ vol ต่ำ** — ใช้ `clean_nav_spikes` ตามบทบาท (แก้ {len(ctx['spikes'])} จุด) แต่กฎ F-rule ของ quant_team (M015 §4.2) จับเพิ่มได้ {len(spk)} จุด ใน {spk.FundCode.nunique()} กอง (ถูกใช้เป็น NAV asof ของสัปดาห์ {int(spk.used_as_weekly_asof.sum())} จุด) · ขอให้เลือก: คงตามเดิม (ตรวจอย่างเดียว) / ใช้ F-rule แก้เพิ่มกับกอง F ใน panel")
    T.append(f"4. **กองที่ return ซ้ำกันข้าม family (corr>0.99)** — {n_dup_cross} คู่ (รายคู่ `dup_pairs.csv`) · ยังไม่ตัด · ขอให้เลือก: คงไว้ทั้งหมด / เหลือ 1 กองต่อกลุ่ม (ตัวที่ประวัติยาวสุด)")
    T.append(f"5. **class ปันผลที่เป็นตัวแทน family เพราะไม่มี class อื่นผ่านเกณฑ์** — {len(divonly)} กอง · NAV ไม่รวมปันผล → return ต่ำกว่าจริง · ขอให้เลือก: คงไว้ (ติดป้ายใน universe.csv) / ตัดออก")
    T.append("6. **ปลาย panel 2026** — ใช้ 2026-01 ถึง 2026-07 ดูประกอบเท่านั้น (รูใหญ่ " + ("; ".join(f"{a:%Y-%m-%d}→{b:%Y-%m-%d}" for a, b in runs) or "ไม่พบ") + ") · ยืนยันว่าตัดออกจากการประมาณทุกชั้นตามที่ BRIEF กำหนด")
    T.append("7. **TDEX แทน SET** — ใช้ได้ระดับสัปดาห์/เดือนเท่านั้น (รายวัน 11.8% ไม่ขยับ) · เป็น SET50 ไม่ใช่ SET ทั้งตลาด · ถ้าต้องการ SET จริงต้องหาแหล่งดาวน์โหลดใหม่")
    return "\n".join(T)
