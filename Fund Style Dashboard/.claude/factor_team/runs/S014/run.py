"""S014 run (PORT-FX ก = S014 + S015) — เรียก lib เท่านั้น · ใช้ (จาก root ด้วย PYTHONPATH=.):
  python run.py --phase pre   [--out DIR]   # mapping · ตารางไตรมาส · β ณ t · e_g · exposure · concentration (ไม่เปิดค่าผลตอบแทน realized)
  python run.py --phase full  [--out DIR]   # attribution L1/L2 · ภาคผนวก · รายงาน (คำนวณ phase pre ซ้ำแล้วตรวจว่าตรงทุกบิต)
  --sim ข้อมูลจำลอง (smoke · ต้องใส่ --out)   --smoke ลดจำนวนรอบ (ไม่ใช่ผลรายงาน)
เชิงอธิบาย · ไม่นับ trial · ไม่แตะ trials.csv ทั้งสองทีม · ใช้ factor ไฟล์ noaqr เท่านั้น"""
import hashlib
import json
import platform
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

LIB = Path(__file__).resolve().parents[2] / "lib"
sys.path.insert(0, str(LIB))
import io_l1  # noqa: E402
import l1eo  # noqa: E402
import port  # noqa: E402

SEED = 20261015
ARGV = sys.argv
PHASE = ARGV[ARGV.index("--phase") + 1] if "--phase" in ARGV else "pre"
SIM = "--sim" in ARGV
SMOKE = "--smoke" in ARGV
assert PHASE in ("pre", "full")
DEFAULT_OUT = Path(__file__).resolve().parent
OUT = Path(ARGV[ARGV.index("--out") + 1]) if "--out" in ARGV else DEFAULT_OUT
if SIM and OUT.resolve() == DEFAULT_OUT.resolve():
    sys.exit("--sim ต้องใส่ --out ที่ไม่ใช่ runs/S014")
OUT.mkdir(parents=True, exist_ok=True)
T0 = time.time()
RUN_SHA = io_l1.sha256_file(Path(__file__))
LOGF = open(OUT / ("run_pre.log" if PHASE == "pre" else "run.log"), "w")
TEAM, ROOT = io_l1.TEAM, io_l1.ROOT
SPEC_FILES = ["specs/S014_PORT_M052_attribution.md", "specs/S015_PORT_addendum_to_S014.md"]


def log(msg):
    line = f"[{datetime.now().isoformat(timespec='seconds')} +{time.time() - T0:7.1f}s] {msg}"
    LOGF.write(line + "\n")
    LOGF.flush()
    print(line, flush=True)


def _jdef(o):
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.floating):
        return float(o)
    if isinstance(o, np.bool_):
        return bool(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, (pd.Timestamp,)):
        return str(o)
    raise TypeError(type(o))


def pre_write(name, content):
    """ไฟล์ phase pre: phase pre เขียน · phase full คำนวณซ้ำแล้วต้องตรงทุกบิต"""
    p = OUT / name
    b = content if isinstance(content, bytes) else content.encode("utf-8")
    if PHASE == "pre":
        p.write_bytes(b)
    else:
        assert p.exists(), f"phase pre ยังไม่ได้เขียน {name}"
        assert p.read_bytes() == b, f"{name}: ผลคำนวณซ้ำใน phase full ต่างจาก phase pre"


def pre_csv(df, name):
    pre_write(name, df.to_csv(index=False))


def save(df, name):
    assert PHASE == "full"
    df.to_csv(OUT / name, index=False)
    return df


def md(df, nd=3, maxrows=400):
    if df is None or len(df) == 0:
        return "(ว่าง)\n"
    cols = list(df.columns)
    out = ["| " + " | ".join(str(c) for c in cols) + " |", "|" + "|".join("---" for _ in cols) + "|"]
    for _, r in df.head(maxrows).iterrows():
        cells = []
        for c in cols:
            v = r[c]
            if isinstance(v, (float, np.floating)):
                cells.append("–" if not np.isfinite(v) else (str(int(v)) if float(v).is_integer() and abs(v) < 1e6 else f"{v:.{nd}f}"))
            elif isinstance(v, (bool, np.bool_)):
                cells.append("✓" if v else "✗")
            else:
                cells.append(str(v).replace("|", "/"))
        out.append("| " + " | ".join(cells) + " |")
    return "\n".join(out) + "\n"


def pp(x, nd=2):
    return float(x) * 100.0


# ───────────────────────── 0) ตรวจก่อนแตะข้อมูล ─────────────────────────
log(f"run.py sha256={RUN_SHA} phase={PHASE} sim={SIM} smoke={SMOKE}")
PIN, LIBH, DEC_SHA = {}, io_l1.lib_hash(), "sim"
if not SIM:
    if PHASE == "pre":
        shutil.copyfile(Path(__file__), OUT / "run_pre.py")
        log("เก็บสำเนา run.py → run_pre.py")
    PIN = port.check_pins()
    log(f"sha256 เต็ม {len(PIN)} ไฟล์ตาม S014/S015 ตรง")
    s12 = json.load(open(TEAM / "runs" / "S012" / "run_meta.json"))["lib_sha256"]
    assert {k: v for k, v in LIBH.items() if k != "port.py"} == s12 and set(LIBH) - set(s12) == {"port.py"}, "lib เดิม 16 ไฟล์ต่างจาก runs/S012/run_meta.json"
    DEC = TEAM / "runs" / "S014" / "decisions_pre_run.md"
    assert DEC.exists(), "ต้องเขียน decisions_pre_run.md ก่อนคำนวณผล"
    DEC_SHA = io_l1.sha256_file(DEC)
    log(f"lib เดิม 16 ไฟล์ตรง runs/S012 + port.py · decisions_pre_run.md sha {DEC_SHA[:12]}…")

# ───────────────────────── 1) ข้อมูล ─────────────────────────
H = port.load_m052()
RZm = port.load_realized(full=False)                 # phase pre: เฉพาะคอลัมน์โครง (S015 ข้อ 4.9)
universe = pd.read_csv(TEAM / "data" / "universe.csv").set_index("FundCode")
gmap = l1eo.load_group_map()
profile = pd.read_csv(ROOT / "base_data" / "FundProfile.csv", encoding="utf-8-sig", low_memory=False,
                      usecols=["Fund Code", "Fund Name EN", "FX Risk Flag"]).drop_duplicates("Fund Code").set_index("Fund Code")
qa = pd.read_csv(TEAM / "data" / "qa_friday_gap_E_units.csv").set_index("unit")["grp_A"].astype(bool)
MP = port.map_holdings(H, universe, gmap, profile)
MPI = MP.set_index("FundCode")
UNITS = sorted(set(MP["unit"]))
F0 = io_l1.load_factors("W")
if SIM:
    F = l1eo.sim_factors(F0, SEED + 1)
    Fext = l1eo.sim_factors(l1eo.load_ext("W"), SEED + 2)
    Feo = l1eo.sim_factors(pd.read_parquet(TEAM / "data" / "factors_eo_noaqr_weekly.parquet").loc[io_l1.MAIN_START:io_l1.MAIN_END], SEED + 3)
    FRs = port.factor_frames(F, Fext, Feo)
    rng = np.random.default_rng(SEED + 4)
    R = pd.DataFrame(index=F.index)
    for i, u in enumerate(UNITS):
        gf = MP.loc[MP["unit"] == u, "group_factor"].iloc[0]
        kd = MP.loc[MP["unit"] == u, "kind"].iloc[0]
        if kd == "G":
            y = 0.9 * FRs["base"]["GOLD_XS"] + 0.3 * FRs["base"]["FX"]
        else:
            y = 0.6 * FRs["base"]["MKT"] + 0.1 * FRs["base"]["FX"] + 0.1 * FRs["base"]["CMA"]
            if gf != "ไม่มี":
                y = y + 0.3 * FRs["I"][l1eo.GNAME[gf]]
        R[u] = y + 0.004 * rng.normal(size=len(F.index))
else:
    F = F0
    Fext, Feo = l1eo.load_ext("W"), port.load_eo_noaqr("W")
    R = io_l1.load_returns("W")
assert (F.index == Fext.index).all() and (F.index == Feo.index).all() and F.index.max() <= pd.Timestamp("2025-12-26")
assert not any(str(c).upper().startswith("AQR") for c in Feo.columns)
FR = port.factor_frames(F, Fext, Feo)
idx = R.index
rf = FR["rf"]
if SIM:
    NN = R[UNITS].notna()
else:
    P_ = pd.read_parquet(TEAM / "data" / "panel_weekly.parquet", columns=["FundCode", "date", "ret"])
    P_ = P_[P_["FundCode"].isin(set(UNITS))]
    NN = P_.assign(v=P_["ret"].notna()).pivot(index="date", columns="FundCode", values="v").reindex(idx).fillna(False).astype(bool)
    del P_
QT, ANCH = port.quarter_table(H, RZm, idx)
HT = port.holding_table(H, MP, ANCH, idx, NN, qa)
if not SIM:
    DQ = pd.read_csv(TEAM / "scratch" / "factor-designer_s015_quarters.csv")
    DH = pd.read_csv(TEAM / "scratch" / "factor-designer_s015_holdings.csv")
    for c in ("t", "e", "e_next_official", "first_anchor", "last_anchor", "n_weeks", "start_mis_bd", "end_mis_bd", "anchors_t_to_e", "n_hold", "has_gold", "realized_days", "truncated", "t_wd", "e_wd"):
        assert (QT[c].astype(str).to_numpy() == DQ[c].astype(str).to_numpy()).all(), f"ตารางไตรมาสไม่ตรง: {c}"
    for c in ("x_hold", "x_model", "w_gold"):
        assert np.allclose(QT[c].to_numpy(float), DQ[c].to_numpy(float), atol=1e-12), c
    for c in ("t", "FundCode", "kind", "unit", "group", "n_win156", "n_hold_rows", "n_hold_anchor", "fx_flag_holding", "fx_flag_unit", "fx_flag_diff", "fri_gap_grpA", "n_gap_anchor_in_hold", "nav_fri_gap"):
        assert (HT[c].astype(str).to_numpy() == DH[c].astype(str).to_numpy()).all(), f"ตาราง mapping/ธงไม่ตรง: {c}"
    assert np.allclose(HT["weight"].to_numpy(float), DH["weight"].to_numpy(float), atol=1e-9)
    assert H["FundCode"].nunique() == 23 and len(MP) == 23 and MP["unit"].nunique() == 23 and len(H) == 58
    assert (MP["fx_flag_diff"].sum() == 1) and (HT["n_hold_rows"] == 13).all()
    log("ตารางไตรมาส 15 แถว + ตาราง mapping/ธง 58 แถว ตรงตาราง S015 (designer) ทุกช่อง · 23 รหัส → 23 หน่วย")
allh = sorted(d for a in ANCH.values() for d in a)
assert len(allh) == 195 and allh[0] == pd.Timestamp("2022-04-08") and allh[-1] == pd.Timestamp("2025-12-26")
PERIODS = {"ปี 2022 (เม.ย.–ธ.ค.)": [pd.Timestamp(x) for x in ("2022-03-31", "2022-06-30", "2022-09-30")],
           "ปี 2023": [pd.Timestamp(x) for x in ("2022-12-30", "2023-03-31", "2023-06-30", "2023-09-29")],
           "ปี 2024": [pd.Timestamp(x) for x in ("2023-12-29", "2024-03-29", "2024-06-28", "2024-09-30")],
           "ปี 2025": [pd.Timestamp(x) for x in ("2024-12-31", "2025-03-31", "2025-06-30", "2025-09-30")]}
PERIODS["ทั้งช่วง (2022-04 → 2025-12)"] = sorted(H["t"].unique())
PERIODS = {k: [pd.Timestamp(t) for t in v] for k, v in PERIODS.items()}
assert [len(sum((list(ANCH[t]) for t in v), [])) for v in PERIODS.values()] == [39, 52, 52, 52, 195]

# ───────────────────────── 2) ไฟล์ phase pre ─────────────────────────
TS = sorted(H["t"].unique())
HOLD = {t: H[H["t"] == t].reset_index(drop=True) for t in TS}
QF = {t: port.quarter_fit(R, FR, t, HOLD[t], MPI, "main") for t in TS}
ALLN = port.CORE + ["GOLD_XS", "TDEXX"] + sorted(set(l1eo.GNAME[g] for g in l1eo.GNAME if g != "e_AH"))
mp_out = MP.copy()
pre_csv(mp_out, "mapping_codes.csv")
_QS = QT[["t", "e", "first_anchor", "last_anchor", "n_weeks", "start_mis_bd", "end_mis_bd"]].assign(t=lambda d: d["t"].astype(str)).rename(columns={"n_weeks": "n_hold_weeks"})
pre_csv(HT.assign(t=HT["t"].astype(str)).merge(_QS, on="t", how="left"), "mapping.csv")
pre_csv(QT, "quarters.csv")
brow, erow, crow, ecoef = [], [], [], []
for t, qf in QF.items():
    Sig, nS = port.sigma_f(qf)
    B, seB, wv, s2 = port.exposure(qf)
    d = port.var_decomp(B, Sig, wv, s2)
    for f in qf["fits"]:
        r = dict(t=t.date(), FundCode=f["code"], unit=f["unit"], kind=f["kind"], w=f["w"], alpha=f["alpha"], s2_eps=f["s2"], adj_r2=f["adj_r2"], n=f["n"], beta_fallback=False)
        for c in ALLN:
            if c in f["names"]:
                j = f["names"].index(c)
                r.update({"b0_" + c: f["b0"][j], "b1_" + c: f["b1"][j], "beta_" + c: f["beta"][j], "se_beta_" + c: f["se_beta"][j]})
            else:
                r.update({"b0_" + c: np.nan, "b1_" + c: np.nan, "beta_" + c: np.nan, "se_beta_" + c: np.nan})
        brow.append(r)
    hq = HOLD[t]
    gw = {}
    for f in qf["fits"]:
        gname = MPI.loc[f["code"], "group"]
        gw[gname] = gw.get(gname, 0.0) + f["w"]
    er = dict(t=t.date(), x_hold=float(hq.loc[hq["kind"] == "E", "weight"].sum()), x_model=float(hq["x_model"].iloc[0]), HHI=float(np.sum(wv ** 2)), n_sigma_rows=nS)
    er.update({"wgroup_" + k: v for k, v in sorted(gw.items())})
    cr = dict(t=t.date(), V=d["V"], V_def="longrun", systematic=d["systematic"], eps=d["eps"], share_eps=d["share_eps"], vol_ann_expected=float(np.sqrt(52 * d["V"])), n_sigma_rows=nS)
    for c in ALLN:
        k = qf["names"].index(c) if c in qf["names"] else None
        er["B_" + c] = B[k] if k is not None else 0.0
        er["se_B_" + c] = seB[k] if k is not None else 0.0
        cr["share_" + c] = d["share"][k] if k is not None else 0.0
        cr["share_sys_" + c] = (d["share"][k] * d["V"] / d["systematic"]) if k is not None else 0.0
    top = int(np.argmax(np.abs(d["share"])))
    cr.update(top_factor=qf["names"][top], top_share=float(d["share"][top]))
    erow.append(er)
    crow.append(cr)
    for c, row in qf["coef"].set_index("index").iterrows() if len(qf["coef"]) else []:
        ecoef.append(dict(t=t.date(), factor=c, a=row["a"], b_MKT=row["b_MKT"], b_FX=row["b_FX"], b_CMA=row["b_CMA"], r2_train=row["r2_train"], n=row["n"]))
BETAS, EXPO, CONC, ECOEF = pd.DataFrame(brow), pd.DataFrame(erow), pd.DataFrame(crow), pd.DataFrame(ecoef)
pre_csv(BETAS, "betas.csv")
pre_csv(EXPO, "exposure.csv")
pre_csv(CONC, "concentration.csv")
pre_csv(ECOEF, "eg_coef.csv")
log("เขียน mapping_codes.csv · mapping.csv · quarters.csv · betas.csv · exposure.csv · concentration.csv · eg_coef.csv (β ณ t ด้วยข้อมูล ≤ t)")

if PHASE == "pre":
    meta_pre = dict(created=datetime.now().isoformat(timespec="seconds"), phase="pre", run_py_sha256=RUN_SHA, seed=SEED, sim=SIM, smoke=SMOKE, spec_files=SPEC_FILES,
                    lib_sha256=LIBH, decisions_sha256=DEC_SHA, runtime_sec=round(time.time() - T0, 1))
    (OUT / "run_meta_pre.json").write_text(json.dumps(meta_pre, indent=1, ensure_ascii=False, default=_jdef))
    log("phase pre เสร็จ · ไม่ได้เปิดค่าผลตอบแทน realized / weekly ของ quant")
    sys.exit(0)

# ═════════════════════════ phase full ═════════════════════════
log("เริ่ม phase full: คำนวณไฟล์ phase pre ซ้ำแล้วตรวจตรงทุกบิตแล้ว → attribution")
META_PRE = json.load(open(OUT / "run_meta_pre.json"))
RUN_SHA_PRE = META_PRE["run_py_sha256"]
RUN_CHANGED = RUN_SHA_PRE != RUN_SHA
if RUN_CHANGED:
    log(f"คำเตือน: sha256 run.py ต่างจาก phase pre ({RUN_SHA_PRE[:12]}… → {RUN_SHA[:12]}…) — ต้องมี diff ใน results.md (BRIEF 106)")

# realized ฉบับเต็ม (S015 ข้อ 4.9: เปิดค่า ret_gross / ret / cost / rf_ann / weights ใน phase full เท่านั้น)
if SIM:
    ZF = RZm.copy()
    rng2 = np.random.default_rng(SEED + 9)
    ZF["rf_ann"] = 0.01
    ZF["cost"] = 0.002
    ZF["ret_gross"] = 0.0
    ZF["ret"] = 0.0
    ZF["weights"] = ""
else:
    ZF = port.load_realized(full=True)
    for t in TS:
        wt = port.parse_weights(ZF.loc[t, "weights"])
        mine = dict(zip(HOLD[t]["FundCode"], HOLD[t]["weight"]))
        assert set(wt) == set(mine) and max(abs(wt[k] - mine[k]) for k in mine) <= 1e-9, f"weights ใน realized ไม่ตรง holdings: {t}"
    log("realized.weights ตรง holdings ทุกไตรมาส (ความคลาดเคลื่อนสูงสุด ≤ 1e-9)")

# variants
QFA = {t: port.quarter_fit(R, FR, t, HOLD[t], MPI, "PA") for t in TS}
QFB = {t: port.quarter_fit(R, FR, t, HOLD[t], MPI, "PB") for t in TS}
WK = {"main": [], "PA": [], "PB": []}
DET_PA = {}
for v, qfs in (("main", QF), ("PA", QFA), ("PB", QFB)):
    for t in TS:
        if v == "PA":
            df, W, det = port.attribute_weekly(qfs[t], ANCH[t], R, rf, extra_detail=True)
            DET_PA[t] = det
        else:
            df, W = port.attribute_weekly(qfs[t], ANCH[t], R, rf)
        df.insert(0, "t", t)
        WK[v].append(df)
WKD = {v: pd.concat(l).fillna(0.0) for v, l in WK.items()}
for v in WKD:
    assert WKD[v]["id_err"].abs().max() < 1e-12, "เอกลักษณ์ L1 ไม่ตรง"
    assert len(WKD[v]) == 195
CNAMES = {v: sorted(c[2:] for c in WKD[v].columns if c.startswith("C_")) for v in WKD}
log(f"attribution L1 รายสัปดาห์ 3 variant (main · P-A · P-B) · เอกลักษณ์ตรง ≤ {max(WKD[v]['id_err'].abs().max() for v in WKD):.1e}")
wk_out = WKD["main"].copy()
wk_out.insert(1, "anchor", wk_out.index.astype(str))
wk_out["t"] = wk_out["t"].dt.date.astype(str)
save(wk_out.reset_index(drop=True), "attribution_weekly.csv")


def rec_for(v, ts_):
    df = WKD[v][WKD[v]["t"].isin(ts_)]
    return port.reconcile_period(df)


# ───────────── ตารางไตรมาส L1 (+ คู่ P-A) ─────────────
qrows = []
for t in TS:
    qr = QT[QT["t"].astype(str) == str(t.date())].iloc[0]
    rec = rec_for("main", [t])
    recA = rec_for("PA", [t])
    recB = rec_for("PB", [t])
    r = dict(t=t.date(), e=qr["e"], first_anchor=qr["first_anchor"], last_anchor=qr["last_anchor"], n_weeks=int(qr["n_weeks"]), start_mis_bd=int(qr["start_mis_bd"]),
             end_mis_bd=int(qr["end_mis_bd"]), x_hold=qr["x_hold"], x_model=qr["x_model"])
    for c in ALLN:
        r["C_" + c] = rec["components"].get("C_" + c, 0.0)
    r.update(A=rec["components"]["A"], sumE=rec["components"]["E"], SUM=rec["SUM"], K_q=rec["K"], CEX_q=rec["CEX"], R_panel=rec["cum_rp"], rf_cum=rec["cum_rf"],
             sumE_PA=recA["components"]["E"], PA_C_TDEXX=sum(v.sum() for (c, f_), v in DET_PA[t].items() if f_ == "TDEXX"),
             PA_C_GOLD_XS_Eleg=sum(v.sum() for (c, f_), v in DET_PA[t].items() if f_ == "GOLD_XS" and MPI.loc[c, "kind"] == "E"), K_q_PA=recA["K"], sumE_PB=recB["components"]["E"],
             beta_rows_min=int(min(f["n"] for f in QF[t]["fits"])), beta_rows_max=int(max(f["n"] for f in QF[t]["fits"])))
    qrows.append(r)
ATTQ = pd.DataFrame(qrows)
save(ATTQ, "attribution_q.csv")

# ───────────── L2 + reconcile ─────────────
l2rows, rcrows = [], []
L2LIST = {}
for t in TS:
    qf = QF[t]
    a = ANCH[t]
    B = port.exposure(qf)[0]
    Fsum = qf["FU"].loc[a].sum().to_numpy()
    z = ZF.loc[t]
    rf_off = float(z["rf_ann"] * z["days"] / 365.0)
    rec = rec_for("main", [t])
    ret_gross = float(z["ret_gross"]) if not SIM else rec["cum_rp"] + 0.001
    ret_net = float(z["ret"]) if not SIM else ret_gross - 0.002
    d = port.attribute_L2(qf, B, ret_gross, rf_off, Fsum, len(a))
    d.update(ret_gross=ret_gross, rf_off=rf_off)
    L2LIST[t] = d
    qr = QT[QT["t"].astype(str) == str(t.date())].iloc[0]
    htq = HT[HT["t"].astype(str) == str(t.date())]
    end_label = "ปลายช่วง panel 2025-12-26 vs ทางการ 2025-12-31 (end_mis 3 วันทำการ)" if t == TS[-1] else ""
    row = dict(t=t.date(), ret_gross=ret_gross, rf_off=rf_off, days=int(z["days"]), rf_ann=float(z["rf_ann"]), R_off_ex=d["R_ex"])
    for c in ALLN:
        row["BF_" + c] = d["BF"].get(c, 0.0)
    row.update(A_q=d["A"], eps_L2=d["eps"], K_L1_q=rec["K"], delta_reconcile=ret_gross - rec["cum_rp"], B_basis="น้ำหนักต้นไตรมาส (w ณ e · ไม่ลอย)", end_label=end_label)
    l2rows.append(row)
    flags = []
    if bool(htq["fx_flag_diff"].any()):
        flags.append("fx_flag_diff")
    if (MPI.loc[HOLD[t]["FundCode"], "class_diff"]).any():
        flags.append("class ต่าง")
    if bool(htq["nav_fri_gap"].any()):
        flags.append("nav_fri_gap")
    flags.append(f"start_mis {int(qr['start_mis_bd'])} / end_mis {int(qr['end_mis_bd'])} วันทำการ")
    rc = port.reconcile_panel_official(rec["cum_rp"], ret_gross, ret_net, float(z["cost"]), "; ".join(flags))
    rc.update(t=t.date(), rf_off=rf_off, rf_cum_panel=rec["cum_rf"], note=("ส่วนต่าง panel vs ทางการอาจมาจาก hedge (class C flag N vs -A flag Y) ไม่ใช่ค่าธรรมเนียม · น้ำหนัก 0.076" if t == pd.Timestamp("2024-12-31") else "") + (" · " + end_label if end_label else ""))
    rcrows.append(rc)
L2Q = pd.DataFrame(l2rows)
RECON = pd.DataFrame(rcrows)[["t", "R_panel", "ret_gross", "ret", "delta", "cost", "cost_col", "rf_off", "rf_cum_panel", "flags", "note"]]
save(L2Q, "attribution_L2.csv")
save(RECON, "reconcile.csv")

# ───────────── ตารางสรุปช่วง (L1 · L1_PA · L1_PB · L2) ─────────────
srows = []
SUMMARY_REC = {}
for pname, ts_ in PERIODS.items():
    for v, lens in (("main", "L1"), ("PA", "L1_PA"), ("PB", "L1_PB")):
        rec = rec_for(v, ts_)
        sh = port.shares_table(rec)
        SUMMARY_REC[(pname, lens)] = (rec, sh)
        for c, val in rec["components"].items():
            srows.append(dict(period=pname, lens=lens, component=c.replace("C_", ""), value=val, share=sh.get(c)))
        srows.append(dict(period=pname, lens=lens, component="K (ผลของการทบต้น)", value=rec["K"], share=sh.get("K")))
        srows.append(dict(period=pname, lens=lens, component="SUM รายสัปดาห์", value=rec["SUM"], share=np.nan))
        srows.append(dict(period=pname, lens=lens, component="CEX = Π(1+r_p) − Π(1+rf)", value=rec["CEX"], share=1.0 if abs(rec["CEX"]) >= 0.02 else np.nan))
        srows.append(dict(period=pname, lens=lens, component="Π(1+r_p) − 1", value=rec["cum_rp"], share=np.nan))
        srows.append(dict(period=pname, lens=lens, component="Π(1+rf) − 1", value=rec["cum_rf"], share=np.nan))
    r2 = port.reconcile_L2([L2LIST[t] for t in ts_])
    cexo = r2["CEX"]
    for c, val in r2["BF"].items():
        srows.append(dict(period=pname, lens="L2", component="BF_" + c, value=val, share=(val / cexo) if abs(cexo) >= 0.02 else np.nan))
    for nm, val in (("A (Σ w α × สัปดาห์)", r2["A"]), ("eps_L2", r2["eps"]), ("K^off (ผลของการทบต้น)", r2["K"])):
        srows.append(dict(period=pname, lens="L2", component=nm, value=val, share=(val / cexo) if abs(cexo) >= 0.02 else np.nan))
    srows.append(dict(period=pname, lens="L2", component="SUM^off", value=r2["SUM"], share=np.nan))
    srows.append(dict(period=pname, lens="L2", component="CEX^off = Π(1+ret_gross) − Π(1+rf_off)", value=cexo, share=1.0 if abs(cexo) >= 0.02 else np.nan))
    srows.append(dict(period=pname, lens="L2", component="Π(1+ret_gross) − 1", value=r2["cum_gross"], share=np.nan))
    srows.append(dict(period=pname, lens="L2", component="Π(1+rf_off) − 1", value=r2["cum_rf"], share=np.nan))
    SUMMARY_REC[(pname, "L2")] = r2
SUM = pd.DataFrame(srows)
for pname, ts_ in PERIODS.items():
    for lens in ("L1", "L1_PA", "L1_PB"):
        rec = SUMMARY_REC[(pname, lens)][0]
        assert abs(sum(rec["components"].values()) + rec["K"] - rec["CEX"]) < 1e-12
    r2 = SUMMARY_REC[(pname, "L2")]
    assert abs(sum(r2["BF"].values()) + r2["A"] + r2["eps"] + r2["K"] - r2["CEX"]) < 1e-12
    assert abs(SUMMARY_REC[(pname, "L1")][0]["K"] - SUMMARY_REC[(pname, "L1_PA")][0]["K"]) < 1e-15 and abs(SUMMARY_REC[(pname, "L1")][0]["K"] - SUMMARY_REC[(pname, "L1_PB")][0]["K"]) < 1e-15
n_win_22 = HT[HT["t"].astype(str).isin([str(t.date()) for t in PERIODS["ปี 2022 (เม.ย.–ธ.ค.)"]])]["n_win156"]
SUM["note"] = np.where(SUM["period"].str.startswith("ปี 2022"), f"β จาก {int(n_win_22.min())}–{int(n_win_22.max())} แถว (สองไตรมาสแรก ≤ 77) · E-X2 มี 9 พารามิเตอร์ต่อกอง", "")
save(SUM, "attribution_summary.csv")

# ───────────── ภาคผนวก P-A ─────────────
pa_rows = []
for t in TS:
    for fm, fa in zip(QF[t]["fits"], QFA[t]["fits"]):
        if fm["code"] in ("DAOL-GOLD", "FCSCBSETE"):
            pa_rows.append(dict(t=t.date(), FundCode=fm["code"], w=fm["w"], adj_r2_main=fm["adj_r2"], adj_r2_PA=fa["adj_r2"], d_adj_r2=fa["adj_r2"] - fm["adj_r2"], r2_main=fm["r2"], r2_PA=fa["r2"],
                                s2_main=fm["s2"], s2_PA=fa["s2"], n=fm["n"], extra_factor="GOLD_XS" if fm["code"] == "DAOL-GOLD" else "TDEXX (TDEX_THB − RF)",
                                beta_extra=fa["beta"][fa["names"].index("GOLD_XS" if fm["code"] == "DAOL-GOLD" else "TDEXX")]))
PA = pd.DataFrame(pa_rows)
CONC_PA = []
for t in TS:
    B, seB, wv, s2 = port.exposure(QFA[t])
    Sig, nS = port.sigma_f(QFA[t])
    CONC_PA.append(dict(t=t.date(), share_eps_main=CONC.loc[CONC["t"] == t.date(), "share_eps"].iloc[0], share_eps_PA=port.var_decomp(B, Sig, wv, s2)["share_eps"]))
PA = PA.merge(pd.DataFrame(CONC_PA), on="t", how="left")
save(PA, "appendix_PA.csv")


def conc_row(qf, prefix):
    B, seB, wv, s2 = port.exposure(qf)
    Sig, nS = port.sigma_f(qf)
    d = port.var_decomp(B, Sig, wv, s2)
    nm = qf["names"]
    sh = dict(zip(nm, d["share"]))
    top = nm[int(np.argmax(np.abs(d["share"])))]
    r = {prefix + "top": top, prefix + "top_share": float(sh[top]), prefix + "B_MKT": float(B[nm.index("MKT")]) if "MKT" in nm else 0.0, prefix + "B_FX": float(B[nm.index("FX")]),
         prefix + "B_GOLD_XS": float(B[nm.index("GOLD_XS")]) if "GOLD_XS" in nm else 0.0, prefix + "share_MKT": float(sh.get("MKT", 0.0)), prefix + "share_FX": float(sh["FX"]),
         prefix + "share_GOLD_XS": float(sh.get("GOLD_XS", 0.0)), prefix + "share_eps": float(d["share_eps"])}
    return r


CPD = []
for t in TS:
    r = dict(t=t.date())
    r.update(conc_row(QF[t], "main_"))
    r.update(conc_row(QFA[t], "PA_"))
    r["holds_P_A_holding"] = ";".join(sorted(set(HOLD[t]["FundCode"]) & {"DAOL-GOLD", "FCSCBSETE"}))
    r["label"] = "เพิ่มหลังรีวิว (S014_result_review S1 · BRIEF 124) · diagnostic บรรยาย · ไม่เปลี่ยนตารางหลัก"
    CPD.append(r)
CONC_PAD = pd.DataFrame(CPD)
save(CONC_PAD, "concentration_PA.csv")

# ───────────── ภาคผนวก P-B ─────────────
pb_rows = []
for pname in PERIODS:
    rm, rb = SUMMARY_REC[(pname, "L1")][0], SUMMARY_REC[(pname, "L1_PB")][0]
    for c in sorted(set(rm["components"]) | set(rb["components"])):
        pb_rows.append(dict(period=pname, component=c.replace("C_", ""), main=rm["components"].get(c, 0.0), PB_noCMA=rb["components"].get(c, 0.0), diff=rb["components"].get(c, 0.0) - rm["components"].get(c, 0.0)))
    pb_rows.append(dict(period=pname, component="K", main=rm["K"], PB_noCMA=rb["K"], diff=rb["K"] - rm["K"]))
PB = pd.DataFrame(pb_rows)
save(PB, "appendix_PB.csv")

# ───────────── ภาคผนวก P-C ─────────────
pcrows = []
PCL = {}
for t in TS:
    d = port.split_returns(QF[t], ANCH[t], R, rf, FR["gld_thb"], float(HOLD[t]["x_model"].iloc[0]))
    PCL[t] = d
    pcrows.append(dict(t=t.date(), x_hold=d["x_hold"], x_model=d["x_model"], R_E=d["R_E"], R_G=d["R_G"], RG_proxy=d["RG_proxy"], R_panel=d["R_panel"], R_FIX57=d["R_FIX"], AE=d["AE"],
                       id_err=d["id_err"], ae_err=d["ae_err"], note="R_G* = GLD_THB (ทองบาท) แทนขาทอง · ธง" if d["RG_proxy"] else ""))
PC = pd.DataFrame(pcrows)
pc_sum = []
for pname, ts_ in PERIODS.items():
    for lab, sel in (("รวมทุกไตรมาส", ts_), ("ไม่นับไตรมาสธง RG_proxy", [t for t in ts_ if not PCL[t]["RG_proxy"]])):
        if not sel:
            continue
        rr = port.reconcile_PC([PCL[t] for t in sel])
        pc_sum.append(dict(period=pname, variant=lab, n_quarters=len(sel), G_act=rr["G_act"], G_fix57=rr["G_fix"], diff=rr["diff"], sum_AE=rr["sum_AE"], K_PC=rr["K_PC"]))
PCS = pd.DataFrame(pc_sum)
save(pd.concat([PC.assign(kind="รายไตรมาส"), PCS.assign(kind="สรุปช่วง")], ignore_index=True), "appendix_PC.csv")

# ───────────── ภาคผนวก P-D ─────────────
if SIM:
    WQ = pd.read_csv(ROOT / "base_data" / "reference" / "m052_frontier_weekly.csv", comment="#", usecols=["t", "FundCode", "week"], parse_dates=["t", "week"])
    unit_of = MPI["unit"].to_dict()
    fri = WQ["week"].dt.weekday == 4
    WQ["ret"] = np.nan
    ok = fri & WQ["week"].isin(R.index)
    WQ.loc[ok, "ret"] = [R.loc[w, unit_of[c]] + rf.loc[w] for c, w in zip(WQ.loc[ok, "FundCode"], WQ.loc[ok, "week"])]
    WQ["ret"] = WQ["ret"].fillna(0.0)
else:
    WQ = pd.read_csv(ROOT / "base_data" / "reference" / "m052_frontier_weekly.csv", comment="#", parse_dates=["t", "week"])
pdrows = []
agree = []
for t in TS:
    out = port.pd_betas(R, FR, QF[t], WQ[WQ["t"] == t], "ret")
    for o in out:
        f = next(x for x in QF[t]["fits"] if x["code"] == o["FundCode"])
        for j, c in enumerate(o["names"]):
            pdrows.append(dict(t=t.date(), FundCode=o["FundCode"], factor=c, beta_PD=o["beta"][j], beta_main=f["beta"][f["names"].index(c)], n_rows=o["n_rows"], n_dropped_nonfri=o["n_dropped_nonfri"], adj_r2_PD=o["adj_r2"]))
        d_ = WQ[(WQ["t"] == t) & (WQ["FundCode"] == o["FundCode"]) & (WQ["week"].dt.weekday == 4)]
        if o["FundCode"] == MPI.loc[o["FundCode"], "unit"] and len(d_):
            panel_raw = np.array([R.loc[w, o["FundCode"]] + rf.loc[w] for w in d_["week"]])
            agree.append(dict(t=t.date(), FundCode=o["FundCode"], n=len(d_), max_abs_diff_vs_panel_raw=float(np.max(np.abs(panel_raw - d_["ret"].to_numpy(float))))))
PD_ = pd.DataFrame(pdrows)
pooled = float(np.corrcoef(PD_["beta_PD"], PD_["beta_main"])[0, 1])
perq = PD_.groupby("t").apply(lambda g: np.corrcoef(g["beta_PD"], g["beta_main"])[0, 1], include_groups=False).rename("corr_beta_PD_vs_main").reset_index()
AGR = pd.DataFrame(agree)
save(pd.concat([PD_.assign(kind="รายกอง×factor"), perq.assign(kind="corr ต่อไตรมาส"), pd.DataFrame([dict(kind="corr รวมทุก (t · holding · factor)", corr_beta_PD_vs_main=pooled)]),
                AGR.assign(kind="ความตรงกับ panel (ผลตอบแทนรวมศุกร์ · รหัสเดียวกับหน่วย)")], ignore_index=True), "appendix_PD.csv")

# ───────────── ภาคผนวก P-E ─────────────
pe_rows = []
for t in TS:
    B, seB, wv, s2 = port.exposure(QF[t])
    Sig, nS = port.sigma_f(QF[t])
    pe = port.cov_resid_appendix(QF[t], B, Sig)
    grp = MPI.loc[HOLD[t]["FundCode"], "group"]
    dupg = sorted({g for g in grp if g not in ("-", "GOLD") and (grp == g).sum() > 1})
    pe.update(t=t.date(), share_eps_main_indep=CONC.loc[CONC["t"] == t.date(), "share_eps"].iloc[0], diff_full_minus_diag=pe["share_eps_full"] - pe["share_eps_diag"], same_group=";".join(dupg))
    pe_rows.append(pe)
PE = pd.DataFrame(pe_rows)[["t", "n_common", "share_eps_main_indep", "share_eps_diag", "share_eps_full", "diff_full_minus_diag", "same_group"]]
save(PE, "appendix_PE.csv")
log("ภาคผนวก P-A…P-E เสร็จ")

# ═════════════════════════ ความคาดหมายล่วงหน้า (S014 ข้อ 5 + S015) vs ผล ═════════════════════════
EXP = []
_LAST = []


def ex_add(i, expect, result, flags, label=""):
    flags = [bool(f) for f in flags]
    status = "ตรง" if all(flags) else ("ไม่ตรง" if not any(flags) else "บางส่วน")
    EXP.append(dict(id=i, expectation=expect, result=result, sub_ok=f"{sum(flags)}/{len(flags)}", sub_flags=";".join("1" if f else "0" for f in flags), status=status, label=label))


E_ = EXPO.set_index("t")
C_ = CONC.set_index("t")
nq = len(TS)
ex_add(1, "mapping: 23 รหัส → 23 หน่วย · ตัวแทน family 3 (KKP GINFRAEQ-H-F · ONE-INDIAOPP-IA · PRINCIPAL GOPP-C) · นอก U 3 (LHJAPE-A · ONE-INDIAOPP-RA · SCBGOLDHP) · FX flag ต่าง 1 (PRINCIPAL GOPP-C) · ไม่มี fallback ของ β",
       f"{H['FundCode'].nunique()} รหัส → {MP['unit'].nunique()} หน่วย · ตัวแทน {sorted(MP.loc[MP['how'] == 'ตัวแทน family', 'FundCode'])} · นอก U {sorted(MP.loc[~MP['in_U'], 'unit'])} · FX ต่าง {sorted(MP.loc[MP['fx_flag_diff'], 'FundCode'])} · fallback {int(BETAS['beta_fallback'].sum())}",
       [H["FundCode"].nunique() == 23 and MP["unit"].nunique() == 23, set(MP.loc[MP["how"] == "ตัวแทน family", "FundCode"]) == {"KKP GINFRAEQ-H-F", "ONE-INDIAOPP-IA", "PRINCIPAL GOPP-C"},
        set(MP.loc[~MP["in_U"], "unit"]) == {"LHJAPE-A", "ONE-INDIAOPP-RA", "SCBGOLDHP"}, list(MP.loc[MP["fx_flag_diff"], "FundCode"]) == ["PRINCIPAL GOPP-C"], int(BETAS["beta_fallback"].sum()) == 0])
cm = float(np.corrcoef(E_["B_MKT"], E_["x_model"])[0, 1])
ex_add(2, "exposure MKT: corr ข้ามไตรมาสระหว่าง B_MKT กับ x_model ≥ 0.8 · B_MKT อยู่ในช่วง 0.15–1.0",
       f"corr {cm:.3f} · B_MKT {E_['B_MKT'].min():.3f}…{E_['B_MKT'].max():.3f}", [cm >= 0.8, bool(((E_["B_MKT"] >= 0.15) & (E_["B_MKT"] <= 1.0)).all())])
gq = E_[E_["x_hold"] < 1 - 1e-9]
ratio = gq["B_GOLD_XS"] / (1 - gq["x_hold"])
xq1 = E_[E_["x_hold"] >= 1 - 1e-9]
ex_add(3, "exposure GOLD_XS ≈ (1 − x) × 0.85–1.0 ทุกไตรมาสที่มีขาทอง (x = Σw ขา E) · ไตรมาส x = 1 → B_GOLD_XS = 0",
       f"ไตรมาสมีทอง {len(gq)}: B/(1−x) {ratio.min():.3f}…{ratio.max():.3f} · ไตรมาส x = 1 ({len(xq1)}): B_GOLD_XS {xq1['B_GOLD_XS'].abs().max():.2e}",
       [bool(((ratio >= 0.85) & (ratio <= 1.0)).all()), bool((xq1["B_GOLD_XS"].abs() < 1e-12).all())])
gold_q = [t for t in TS if HOLD[t].loc[HOLD[t]["kind"] == "G", "weight"].sum() >= 0.5]
hi_q = [t for t in TS if E_.loc[t.date(), "x_hold"] >= 0.75]
grp_cols = [c for c in CONC.columns if c.startswith("share_e_")]
gsum = C_[grp_cols].sum(axis=1)
ex_add(4, "การกระจุก: ไตรมาสน้ำหนักทอง ≥ 0.5 → share GOLD_XS ≥ 50% ของ V · ไตรมาส x ≥ 0.75 → MKT ≥ 35% ของ V และ factor กลุ่มรวม 10–45%",
       f"ไตรมาสทอง ≥ 0.5: {len(gold_q)} · share GOLD_XS min {min(C_.loc[t.date(), 'share_GOLD_XS'] for t in gold_q):.3f} · ไตรมาส x ≥ 0.75: {len(hi_q)} · share MKT min {min(C_.loc[t.date(), 'share_MKT'] for t in hi_q):.3f} · กลุ่มรวม {min(gsum[t.date()] for t in hi_q):.3f}…{max(gsum[t.date()] for t in hi_q):.3f}",
       [all(C_.loc[t.date(), "share_GOLD_XS"] >= 0.5 for t in gold_q), all(C_.loc[t.date(), "share_MKT"] >= 0.35 for t in hi_q), all(0.10 <= gsum[t.date()] <= 0.45 for t in hi_q)])
ex_add(5, "FX: B_FX อยู่ระหว่าง −0.8 ถึง +0.4 · ส่วนแบ่ง V ของ FX < 15% ทุกไตรมาส",
       f"B_FX {E_['B_FX'].min():.3f}…{E_['B_FX'].max():.3f} · share_FX {C_['share_FX'].min():.3f}…{C_['share_FX'].max():.3f}",
       [bool(((E_["B_FX"] >= -0.8) & (E_["B_FX"] <= 0.4)).all()), bool((C_["share_FX"] < 0.15).all())])
sumE_ok = int((ATTQ["sumE"].abs() <= 0.03).sum())
ex_add(6, "ε ของพอร์ต: share_ε 5–30% ของ V ทุกไตรมาส · |ΣE_s ไตรมาส (L1 · ไม่รวม K)| ≤ 3% ใน ≥ 10 จาก 15 ไตรมาส",
       f"share_ε {C_['share_eps'].min():.3f}…{C_['share_eps'].max():.3f} · |ΣE| ≤ 3%: {sumE_ok}/{nq}",
       [bool(((C_["share_eps"] >= 0.05) & (C_["share_eps"] <= 0.30)).all()), sumE_ok >= 10])
d_ok = int((RECON["delta"].abs() <= 0.01).sum())
ex_add(7, "ส่วนต่าง panel vs ทางการ Δ_q = ret_gross − R_panel: |Δ| ≤ 1% ใน ≥ 12 จาก 15 ไตรมาส", f"|Δ| ≤ 1%: {d_ok}/{nq} · |Δ| สูงสุด {RECON['delta'].abs().max() * 100:.2f}%", [d_ok >= 12])
rall, rallB = SUMMARY_REC[("ทั้งช่วง (2022-04 → 2025-12)", "L1")][0], SUMMARY_REC[("ทั้งช่วง (2022-04 → 2025-12)", "L1_PB")][0]


def top_c(rec):
    comps = {k: v for k, v in rec["components"].items() if k.startswith("C_")}
    return max(comps, key=lambda k: abs(comps[k]))


ex_add(8, "CMA: |ผลรวม contribution ทั้งช่วง| < 2% · ไม่เปลี่ยนข้อสรุปหลัก (P-B: factor ที่ |contribution| มากสุดเท่าเดิม)",
       f"ΣC_CMA ทั้งช่วง {rall['components'].get('C_CMA', 0) * 100:+.2f} pp · top (ชุดหลัก) {top_c(rall)[2:]} · top (P-B) {top_c(rallB)[2:]}",
       [abs(rall["components"].get("C_CMA", 0.0)) < 0.02, top_c(rall) == top_c(rallB)])
r22 = SUMMARY_REC[("ปี 2022 (เม.ย.–ธ.ค.)", "L1")][0]
pc22 = PCS[(PCS["period"] == "ปี 2022 (เม.ย.–ธ.ค.)") & (PCS["variant"] == "รวมทุกไตรมาส")].iloc[0]
ex_add(9, "ปี 2022: factor ที่ |contribution| (L1 · 39 สัปดาห์) มากสุดคือ GOLD_XS หรือ MKT (ไม่ใช่ factor กลุ่ม) · P-C: ΣAE ปี 2022 เป็นบวก",
       f"top 2022 = {top_c(r22)[2:]} ({r22['components'][top_c(r22)] * 100:+.2f} pp) · ΣAE 2022 = {pc22['sum_AE'] * 100:+.2f} pp",
       [top_c(r22)[2:] in ("GOLD_XS", "MKT"), pc22["sum_AE"] > 0], label="designer เห็นผลจริงไตรมาสแรกของ ERC แล้ว (ราว −8% ขณะถือทอง 75%) — ไม่อิสระบางส่วน")
dd = PA[PA["FundCode"] == "DAOL-GOLD"]["d_adj_r2"].median()
df_ = PA[PA["FundCode"] == "FCSCBSETE"]["d_adj_r2"].median()
ex_add(10, "P-A: DAOL-GOLD เพิ่ม GOLD_XS แล้ว adj R² เพิ่ม ≥ 0.15 · FCSCBSETE เพิ่ม TDEX แล้ว adj R² เพิ่ม ≥ 0.20 (median ข้ามไตรมาสที่ถือ)",
       f"DAOL-GOLD Δadj R² median {dd:+.3f} (n={int((PA['FundCode'] == 'DAOL-GOLD').sum())} ไตรมาส) · FCSCBSETE {df_:+.3f} (n={int((PA['FundCode'] == 'FCSCBSETE').sum())})", [dd >= 0.15, df_ >= 0.20])
ex_add(11, "P-D: corr(β ข้อ 3.2, β จากไฟล์ weekly 52 สัปดาห์ของ quant) ข้าม (t · holding · factor) ≥ 0.7", f"corr รวม {pooled:.3f} · จำนวนคู่ {len(PD_)}", [pooled >= 0.7])
EXPDF = pd.DataFrame(EXP)
n_ok = int((EXPDF["status"] == "ตรง").sum())
n_ok_ex9 = int(((EXPDF["status"] == "ตรง") & (EXPDF["id"] != 9)).sum())
save(EXPDF, "expectations_vs_results.csv")
log(f"ความคาดหมาย: ตรง {n_ok}/11 · ไม่นับข้อ 9: {n_ok_ex9}/10")

# ═════════════════════════ results.md ═════════════════════════
def pivot_lens(lens, periods=None):
    d = SUM[(SUM["lens"] == lens)]
    rows = []
    for p in (periods or PERIODS):
        s = d[d["period"] == p].set_index("component")["value"]
        sh = d[d["period"] == p].set_index("component")["share"]
        r = {"ช่วง": p}
        for c in s.index:
            if c in ("SUM รายสัปดาห์", "SUM^off", "Π(1+r_p) − 1", "Π(1+rf) − 1", "Π(1+ret_gross) − 1", "Π(1+rf_off) − 1") or c.startswith("CEX"):
                continue
            r[c] = s[c] * 100
        cexn = [c for c in s.index if c.startswith("CEX")][0]
        r["CEX (pp)"] = s[cexn] * 100
        r["Π(1+r_p)−1 (pp)"] = s[[c for c in s.index if c in ("Π(1+r_p) − 1", "Π(1+ret_gross) − 1")][0]] * 100
        rows.append(r)
    return pd.DataFrame(rows)


def share_tab(lens, p):
    d = SUM[(SUM["lens"] == lens) & (SUM["period"] == p)]
    d = d[~d["component"].str.startswith(("CEX", "SUM", "Π"))]
    return pd.DataFrame({"component": d["component"], "contribution_pp": d["value"] * 100, "ส่วนแบ่ง % ของ CEX": d["share"] * 100})


LABELS = ("**ป้ายบังคับ:** (P1) **เชิงอธิบาย** — exposure / ที่มาผลตอบแทนของพอร์ตที่สร้างแล้ว ไม่ใช่การทำนาย · factor ส่วนใหญ่ลงทุนไม่ได้ (long–short / ส่วนตั้งฉาก) · "
          "(P2) ช่วง 2022-04 → 2025-12 คือช่วงเดียวกับที่ทีม quant ใช้เลือก M052 → **ผลไม่ใช่หลักฐานอิสระ** · "
          "(P3) ชุด factor (MKT · FX · CMA) ถูกคัดใน S012 ด้วยข้อมูล 2021–2023 → ไตรมาสที่ถือก่อน 2024 มี look-ahead ของ 'การเลือกชุด' (β ยังประมาณด้วยข้อมูล ≤ t) · "
          "(P4) **NAV ศุกร์ขาด (BRIEF 121):** ตั้งแต่ ธ.ค. 2023 กองที่ NAVDate = AsOfDate ไม่มี NAV วันศุกร์ — holding ที่โดน: **K-GOLD-A(A) (ถือในช่องว่าง 7 ไตรมาส · 2023-09-29 บางส่วน 3/13 สัปดาห์)** · "
          "**TISCOCH (2025-03-31)** · **ONE-INDIAOPP-IA (2024-09-30 · สถานะ 'ไม่ทราบ' ในตารางล็อก)** · หน้าต่างประมาณ β หลัง 2023-12 ของหน่วยกลุ่ม A มีสัปดาห์ช่องว่างปน · "
          "(P5) **ไม่ใช่คำแนะนำการลงทุน** · ห้ามใช้เลือกกอง")
M = []
A = M.append
A("# S014_PORT results — อธิบายพอร์ต M052 ด้วย factor ของ F5-EO (S014 + S015) · เชิงอธิบาย · ไม่นับ trial\n")
A(f"รันโดย `factor-analyst` · phase pre + full · run.py sha256 `{RUN_SHA}` · ข้อมูล sha256 เต็มตาม S014 ข้อ 2 / S015 ข้อ 5.1 ตรง · lib เดิม 16 ไฟล์ตรง `runs/S012/run_meta.json` + `port.py` · "
  f"{'**ข้อมูลจำลอง (--sim) — ไม่ใช่ผลรายงาน**' if SIM else 'ข้อมูลจริง'} · factor ไฟล์ noaqr เท่านั้น (ไม่มี AQR · ไม่เรียกตัวโหลดไฟล์เดิม) · ไม่แตะ `factor_team/trials.csv` และ `quant_team/trials.csv` · seed {SEED}\n")
A(LABELS + "\n")
A("> **ห้ามอ่านเกินหลักฐาน:** ตารางนี้อธิบายพอร์ตที่ทีม quant สร้าง ไม่ได้บอกว่า factor ใดควรถือ · attribution ใช้ผลตอบแทนรายสัปดาห์ของ panel (anchor ศุกร์) ไม่ใช่วันซื้อจริง · ส่วนแบ่ง % แสดงเฉพาะช่วงสรุปที่ |CEX| ≥ 2 pp และต้องอ่านคู่แถว K (ผลของการทบต้น) เสมอ\n")
A("**การเปิดเผย (S015 m12):** ตอนดูหัวไฟล์ `m052_frontier_realized.csv` / `m052_frontier_weekly.csv` เพื่อดูรูปแบบคอลัมน์ analyst เห็นแถวแรกโดยไม่ได้ตั้งใจ — realized: MVP ไตรมาส 2022-03-31 ผลตอบแทน −0.0829 (ตัวเลขเดียวกับที่ designer เปิดเผยแล้ว) · weekly: ผลตอบแทน ASP-VIET สัปดาห์ 2021-04-09 = +0.0117 — **ไม่ได้ใช้ตัวเลขเหล่านี้ในการออกแบบหรือเลือกใดๆ** (บันทึกใน decisions_pre_run.md ก่อนรัน)\n")
A("## 1. mapping และช่วงถือ (S015 ข้อ 1 · 3)\n")
A(md(MP[["FundCode", "kind", "unit", "how", "in_U", "group_factor", "group_source", "class_diff", "fx_flag_holding", "fx_flag_unit", "fx_flag_diff"]], 3))
A("ตารางไตรมาส (ช่วงถือ = anchor ศุกร์ใน (e_q, e_{q+1}] · 13 สัปดาห์ต่อไตรมาส · ความเหลื่อมจากช่วงทางการ start/end_mis 1–4 วันทำการต่อขอบ):\n")
A(md(QT[["t", "t_wd", "e", "e_wd", "e_next_official", "first_anchor", "last_anchor", "n_weeks", "start_mis_bd", "end_mis_bd", "x_hold", "x_model", "w_gold"]], 4))
fl = HT[HT["nav_fri_gap"] | (HT["fx_flag_diff"]) | (HT["fri_gap_grpA"] == "na")][["t", "FundCode", "weight", "fx_flag_diff", "fri_gap_grpA", "n_gap_anchor_in_hold", "nav_fri_gap"]]
A("ธงเด่นของ holding (ไตรมาสที่ NAV ศุกร์ขาด · FX flag ต่าง · สถานะ 'na'):\n")
A(md(fl, 3))
A("## 2. exposure ต่อ factor รายไตรมาส (β ณ t ด้วยข้อมูล ≤ t · rolling 156 สัปดาห์)\n")
ecols = ["t", "x_hold", "x_model", "HHI"] + ["B_" + c for c in ALLN if (EXPO["B_" + c].abs() > 1e-12).any()]
A(md(EXPO[ecols], 3))
A("`se_B_*` (SE โดยประมาณ √Σw²se² · ไม่รวม cov ข้ามกอง) และ β รายกอง (`betas.csv`) อยู่ในไฟล์ · β ปี 2022 จาก " + f"{int(n_win_22.min())}–{int(n_win_22.max())} แถว (สองไตรมาสแรก ≤ 77) · E-X2 มี 9 พารามิเตอร์ต่อกอง\n")
A("## 3. การกระจุกของความเสี่ยง (Euler · V = ความแปรปรวนแบบระยะยาว)\n")
A("**ป้าย V:** V = B′Σ_f B + Σ w² σ²_ε ใช้ β = b0 + b1 กับ Σ_f lag 0 = ความแปรปรวนแบบระยะยาว (ปรับ NAV ไม่พร้อมกัน) **ไม่ใช่**ความแปรปรวนของผลตอบแทนรายสัปดาห์ใน panel (ซึ่งมีพจน์ b0′Σb0 + b1′Σb1 + autocov) · σ²_ε มาจาก residual รายสัปดาห์แบบ Dimson · ส่วนเฉพาะตัวสมมติอิสระข้ามกอง (P-E แสดงแบบ cov เต็ม) · vol ที่คาด √(52 V) อ่านตามป้ายนี้\n")
ccols = ["t", "vol_ann_expected", "share_eps"] + [c for c in CONC.columns if c.startswith("share_") and c not in ("share_eps",) and not c.startswith("share_sys_") and (CONC[c].abs() > 1e-12).any()] + ["top_factor", "top_share"]
A(md(CONC[ccols], 3))
A("### 3.1 diagnostic การกระจุกแบบ P-A (DAOL-GOLD + GOLD_XS · FCSCBSETE + TDEX) — **เพิ่มหลังรีวิว · บรรยาย · ไม่เปลี่ยนตารางหลัก** (`concentration_PA.csv`)\n")
_cp = CONC_PAD[CONC_PAD["holds_P_A_holding"] != ""][["t", "holds_P_A_holding", "main_top", "main_B_FX", "main_share_FX", "main_share_GOLD_XS", "PA_top", "PA_B_FX", "PA_share_FX", "PA_share_GOLD_XS", "main_share_eps", "PA_share_eps"]]
A(md(_cp, 3))
A("factor ที่ครองสูงสุดรายไตรมาส (15 ไตรมาส): ชุดหลัก " + ", ".join(f"{k} {v}" for k, v in CONC_PAD["main_top"].value_counts().items()) + " · P-A " + ", ".join(f"{k} {v}" for k, v in CONC_PAD["PA_top"].value_counts().items()) + " (ไตรมาสที่ไม่ได้ถือ DAOL-GOLD / FCSCBSETE ค่าเท่ากัน)\n")
A("## 4. ที่มาของผลตอบแทน (attribution)\n")
A("**กระทบยอด (S015 ข้อ 2 · แบบ ก):** CEX = Π(1 + r_p) − Π(1 + rf) · SUM = Σ_s (r_p,s − rf_s) = Σ_k ΣC_k + ΣA + ΣE · K = CEX − SUM = 'ผลของการทบต้น' (เท่ากันทุกการแยก) · Σ component + K = CEX ทุกช่วง (ตรวจ 1e-12) · หน่วย = จุด % (pp) · ส่วนแบ่ง % = ΣC / CEX พร้อมแถว A · E · K\n")
A("### 4.1 L1 รายสัปดาห์ (lens หลัก) — ชุดหลัก (MKT · FX · CMA · GOLD_XS · factor กลุ่ม) · หน่วย pp\n")
t1 = pivot_lens("L1")
A(md(t1, 2))
A("### 4.2 L2 รายไตรมาส (ผลทางการ gross · ลดผลเวลาตีราคา · B ใช้น้ำหนักต้นไตรมาส) · หน่วย pp\n")
t2 = pivot_lens("L2")
A(md(t2, 2))
A("### 4.3 ส่วนแบ่ง % ของ CEX (เฉพาะช่วงสรุป · L1) — แถว A · E · K รวมอยู่ด้วย\n")
for p in ("ปี 2022 (เม.ย.–ธ.ค.)", "ทั้งช่วง (2022-04 → 2025-12)"):
    A(f"**{p}** · {'β จาก ' + str(int(n_win_22.min())) + '–' + str(int(n_win_22.max())) + ' แถว (สองไตรมาสแรก ≤ 77)' if p.startswith('ปี 2022') else ''}\n")
    stab_ = share_tab("L1", p)
    if p.startswith("ปี 2022"):
        stab_ = stab_.drop(columns=["ส่วนแบ่ง % ของ CEX"])
        A("(ปี 2022: ฐาน CEX = " + f"{SUMMARY_REC[(p, 'L1')][0]['CEX'] * 100:.1f} pp เล็ก → ส่วนแบ่ง % ไม่มีความหมายเชิงสัดส่วน (ไฟล์ attribution_summary.csv ยังเก็บค่าตามกติกา ≥ 2 pp) · ใช้หน่วย pp อย่างเดียว · m3)\n")
    A(md(stab_, 2))
A("### 4.4 คู่ P-A (ปี 2022 · 2023 · 2025 · ทั้งช่วง — ช่วงที่ถือ FCSCBSETE / DAOL-GOLD) · L1 ชุดหลัก เทียบ P-A · pp\n")
rowsA = []
for p in ("ปี 2022 (เม.ย.–ธ.ค.)", "ปี 2023", "ปี 2025", "ทั้งช่วง (2022-04 → 2025-12)"):
    rm, ra = SUMMARY_REC[(p, "L1")][0], SUMMARY_REC[(p, "L1_PA")][0]
    ts_ = PERIODS[p]
    q_ = ATTQ[ATTQ["t"].astype(str).isin([str(t.date()) for t in ts_])]
    rowsA.append({"ช่วง": p, "ΣE ชุดหลัก": rm["components"]["E"] * 100, "ΣE P-A": ra["components"]["E"] * 100, "contrib factor เพิ่ม: TDEX": q_["PA_C_TDEXX"].sum() * 100,
                  "contrib factor เพิ่ม: GOLD_XS ของกอง E": q_["PA_C_GOLD_XS_Eleg"].sum() * 100, "K (เท่าเดิม)": rm["K"] * 100,
                  "A ชุดหลัก": rm["components"]["A"] * 100, "A P-A": ra["components"]["A"] * 100, "A+E ชุดหลัก": (rm["components"]["A"] + rm["components"]["E"]) * 100,
                  "A+E P-A": (ra["components"]["A"] + ra["components"]["E"]) * 100})
A(md(pd.DataFrame(rowsA), 2))
A("**ลำดับ factor ตาม |ΣC| (pp) — ชุดหลัก เทียบ P-A (เพิ่มหลังรีวิว S1 · บรรยาย · ไม่เปลี่ยนชุดหลัก):**\n")


def comp_rank(rec, top=5):
    cs = {k[2:]: v for k, v in rec["components"].items() if k.startswith("C_")}
    return " > ".join(f"{k} {v * 100:+.1f}" for k, v in sorted(cs.items(), key=lambda kv: -abs(kv[1]))[:top])


A(md(pd.DataFrame([{"ช่วง": p, "ชุดหลัก (top 5)": comp_rank(SUMMARY_REC[(p, "L1")][0]), "P-A (top 5)": comp_rank(SUMMARY_REC[(p, "L1_PA")][0])} for p in ("ปี 2022 (เม.ย.–ธ.ค.)", "ปี 2025", "ทั้งช่วง (2022-04 → 2025-12)")]), 2))
A("**ห้ามอ่านว่า 'factor อธิบายไม่ได้' สำหรับช่วง FCSCBSETE (t = 2022-06-30 · 09-30 · 2022-12-30) และ DAOL-GOLD (2025-03-31 · 06-30 · 09-30) โดยไม่ดูแถว P-A ข้างบน** (ไตรมาสรายตัวใน `attribution_q.csv`)\n")
A("### 4.5 รายไตรมาส L1 (pp · ΣE = ส่วนที่เหลือ · K_q = ผลของการทบต้นของไตรมาส)\n")
qcols = ["t", "x_hold", "R_panel", "rf_cum", "K_q", "CEX_q"] + ["C_" + c for c in ALLN if (ATTQ["C_" + c].abs() > 1e-12).any()] + ["A", "sumE", "sumE_PA", "PA_C_TDEXX", "PA_C_GOLD_XS_Eleg"]
qq = ATTQ[qcols].copy()
for c in qq.columns:
    if c not in ("t", "x_hold"):
        qq[c] = qq[c] * 100
A(md(qq, 2))
A("### 4.5b รายไตรมาส L2 (ผลทางการ gross · lens ที่ควรอ้างสำหรับเรื่องเล่ารายไตรมาส — L1 ต่างจากผลทางการ > 1% ใน 9/15 ไตรมาส · m7) · pp\n")
_l2 = L2Q.copy()
_l2["BF กลุ่ม (รวม)"] = _l2[[c for c in _l2.columns if c.startswith("BF_e_")]].sum(axis=1)
_l2q = _l2[["t", "R_off_ex", "BF_MKT", "BF_FX", "BF_CMA", "BF_GOLD_XS", "BF กลุ่ม (รวม)", "A_q", "eps_L2"]].copy()
for c in _l2q.columns[1:]:
    _l2q[c] = _l2q[c] * 100
A(md(_l2q, 2))
A("### 4.6 reconcile: panel vs ทางการ (Δ = ret_gross − R_panel · ต้นทุน = ret_gross − ret) · หน่วย pp\n")
rr = RECON.copy()
for c in ("R_panel", "ret_gross", "ret", "delta", "cost"):
    rr[c] = rr[c] * 100
A(md(rr[["t", "R_panel", "ret_gross", "ret", "delta", "cost", "flags", "note"]], 2))
A("## 5. ปี 2022 (เม.ย.–ธ.ค. · ช่วงถือของ t = 2022-03-31 / 06-30 / 09-30 · 39 สัปดาห์)\n")
A(f"β จาก {int(n_win_22.min())}–{int(n_win_22.max())} แถว (สองไตรมาสแรก ≤ 77 · 9 พารามิเตอร์ต่อกอง) · ช่วงเดียวกับที่ทีม quant ใช้เลือก M052 (P2) · รายละเอียด: §4.1–4.3 แถวปี 2022 · P-C ด้านล่างแยกผลของการแบ่งหุ้น/ทอง\n")
A("## 6. ภาคผนวก (บรรยาย · ไม่ใช้สรุปหลัก)\n")
A("**P-A** (factor ตรงสินทรัพย์ของ DAOL-GOLD + GOLD_XS · FCSCBSETE + TDEX):\n")
A(md(PA, 3))
A("**P-B** (ตัด CMA · pp):\n")
pbv = PB.copy()
for c in ("main", "PB_noCMA", "diff"):
    pbv[c] = pbv[c] * 100
A(md(pbv[pbv["period"].isin(["ปี 2022 (เม.ย.–ธ.ค.)", "ทั้งช่วง (2022-04 → 2025-12)"])], 2))
A("**P-C** ผลของการแบ่งหุ้น / ทอง (ไม่ใช่ factor attribution · เทียบสัดส่วนหุ้นคงที่ 0.57 บนขาเดียวกัน — ไม่ใช่ benchmark FIX57 ของ quant ทุกบิต · ไตรมาส x = 1 ใช้ R_G* = ทองบาท + ธง):\n")
pcv = PC.copy()
for c in ("R_E", "R_G", "R_panel", "R_FIX57", "AE"):
    pcv[c] = pcv[c] * 100
A(md(pcv.drop(columns=["id_err", "ae_err", "note"]), 2))
pcs_v = PCS.copy()
for c in ("G_act", "G_fix57", "diff", "sum_AE", "K_PC"):
    pcs_v[c] = pcs_v[c] * 100
A(md(pcs_v, 2))
A("**P-D** (β จากไฟล์ weekly 52 สัปดาห์ของ quant · ตัดแถวที่ไม่ใช่ศุกร์ · เทียบ β ข้อ 3.2):\n")
A(f"corr รวม (t · holding · factor) = **{pooled:.3f}** · ต่อไตรมาส: {', '.join(f'{r.t}: {r.corr_beta_PD_vs_main:.2f}' for r in perq.itertuples())}\n")
A(md(AGR, 6) if len(AGR) else "(ไม่มีคู่เทียบ)\n")
A("**P-E** (ส่วนเฉพาะตัวแบบ cov เต็ม เทียบแบบทแยง · ตารางหลักไม่เปลี่ยน · ไตรมาสถือ 2 กองกลุ่มเดียวกัน: 2023-06-30 JAPAN · 2024-09-30 INDIA):\n")
A(md(PE, 3))
A("## 7. ความคาดหมายเทียบผล\n")
A(md(EXPDF[["id", "expectation", "result", "sub_ok", "status", "label"]], 3))
A(f"**ยอดรวม: ตรง {n_ok} / 11 · ไม่นับข้อ 9 (ไม่อิสระบางส่วน): {n_ok_ex9} / 10** · 'ตรง' ต้องครบทุกส่วนย่อย (คอลัมน์ sub_ok) · เกณฑ์ตัวเลขเขียนก่อนเห็นผล\n")
A("## 8. สิ่งที่พบ\n")
fnd = []
fnd.append(f"exposure หลัก: B_MKT {E_['B_MKT'].min():.2f}…{E_['B_MKT'].max():.2f} (corr กับ x_model {cm:.2f}) · B_FX {E_['B_FX'].min():+.2f}…{E_['B_FX'].max():+.2f} · B_GOLD_XS {E_['B_GOLD_XS'].min():.2f}…{E_['B_GOLD_XS'].max():.2f} · B_CMA {E_['B_CMA'].min():+.2f}…{E_['B_CMA'].max():+.2f}")
fnd.append(f"ผลตอบแทนทั้งช่วง (L1 · 195 สัปดาห์): Π(1+r_p)−1 = {rall['cum_rp'] * 100:.1f}% · CEX = {rall['CEX'] * 100:.1f} pp = " + " + ".join(f"{k.replace('C_', '')} {v * 100:+.1f}" for k, v in sorted(rall["components"].items(), key=lambda kv: -abs(kv[1])) if abs(v) >= 0.0005) + f" + K {rall['K'] * 100:+.1f} (pp)")
fnd.append(f"ปี 2022 (L1 · 39 สัปดาห์): Π(1+r_p)−1 = {r22['cum_rp'] * 100:.1f}% · CEX = {r22['CEX'] * 100:.1f} pp = " + " + ".join(f"{k.replace('C_', '')} {v * 100:+.1f}" for k, v in sorted(r22["components"].items(), key=lambda kv: -abs(kv[1])) if abs(v) >= 0.0005) + f" + K {r22['K'] * 100:+.1f} (pp) · P-C ΣAE 2022 = {pc22['sum_AE'] * 100:+.2f} pp")
fnd.append(f"การกระจุก: share ε ของ V {C_['share_eps'].min():.2f}…{C_['share_eps'].max():.2f} · factor ที่ครองสูงสุดรายไตรมาส: " + ", ".join(f"{k} {v}" for k, v in CONC["top_factor"].value_counts().items()))
fnd.append(f"reconcile: |Δ ทางการ − panel| ≤ 1% ใน {d_ok}/15 ไตรมาส (สูงสุด {RECON['delta'].abs().max() * 100:.2f} pp) · P-D corr β {pooled:.2f}")
_rm_all, _ra_all = SUMMARY_REC[("ทั้งช่วง (2022-04 → 2025-12)", "L1")][0], SUMMARY_REC[("ทั้งช่วง (2022-04 → 2025-12)", "L1_PA")][0]
_rm_25, _ra_25 = SUMMARY_REC[("ปี 2025", "L1")][0], SUMMARY_REC[("ปี 2025", "L1_PA")][0]
_ae = lambda r: (r["components"]["A"] + r["components"]["E"]) * 100
fnd.append(f"**ชุดหลักคู่ P-A (เพิ่มหลังรีวิว · BRIEF 124):** อันดับที่มาทั้งช่วงขึ้นกับว่า DAOL-GOLD มี GOLD_XS หรือไม่ — ชุดหลัก: {comp_rank(_rm_all, 3)} · P-A: {comp_rank(_ra_all, 3)} (pp)")
fnd.append(f"ส่วนที่ factor อธิบายไม่ได้ (A + E): ทั้งช่วง {_ae(_rm_all):.1f} pp (ชุดหลัก) → {_ae(_ra_all):.1f} pp (P-A) · ปี 2025 {_ae(_rm_25):.1f} → {_ae(_ra_25):.1f} pp · K เท่าเดิม {_rm_all['K'] * 100:.1f} pp")
_q25 = CONC_PAD[CONC_PAD["t"].astype(str).isin(["2025-06-30", "2025-09-30"])]
fnd.append("การกระจุกปี 2025-Q2/Q3 (diagnostic): ชุดหลัก top = " + "/".join(_q25["main_top"]) + f" (B_FX {_q25['main_B_FX'].min():+.2f}…{_q25['main_B_FX'].max():+.2f}) → P-A top = " + "/".join(_q25["PA_top"]) +
           f" (B_FX {_q25['PA_B_FX'].min():+.2f}…{_q25['PA_B_FX'].max():+.2f}) — 'FX ครองความเสี่ยง' เป็นผลของ β(FX) แบบมีเงื่อนไขของ DAOL-GOLD ที่ไม่มี factor ทอง · **ห้ามสรุปว่า FX เป็นความเสี่ยงหลักของ M052 ในปี 2025**")
fnd.append("**A (α) ไม่ใช่หลักฐานฝีมือหรือ α ที่ได้จริง:** เป็นค่าคงที่ที่ประมาณจากหน้าต่าง ≤ t แล้วยกไปใช้ในช่วงถือ (กองที่ถูกเลือกด้วยกติกาที่ดูผลตอบแทนย้อนหลังมักมี α ในหน้าต่างสูงโดยการคัดเลือก) · ส่วนที่ factor อธิบายไม่ได้ในช่วงถือจริงคือ A + E (m1)")
fnd.append("**K ไม่ใช่แหล่งผลตอบแทนแยก:** K = พจน์ทบต้นข้ามสัปดาห์ของทุกส่วนรวมกัน (รวมของ factor ด้วย) → ส่วนแบ่ง ΣC/CEX ของ factor ต่ำกว่าบทบาทจริงของทุกตัว (เช่น MKT 21.8% ของ CEX ทั้งช่วง) (m2) · ปี 2022 ใช้ pp ไม่ใช้ส่วนแบ่ง % (m3) · เรื่องเล่ารายไตรมาสอ้าง L2 (§4.5b) ใช้ L1 สำหรับผลรวมช่วง (m7)")
for f_ in fnd:
    A("- " + f_)
A("\n## 9. ข้อจำกัด\n")
for t_ in ["ป้าย (P1)–(P5) · 15 ไตรมาส · กองหุ้น 3 กองต่อไตรมาส → exposure ของกลุ่มแกว่งตามการหมุนกอง · ไม่มี p-value / เกณฑ์ผ่านไม่ผ่าน (เชิงอธิบาย)",
           "β จากหน้าต่าง 64–156 สัปดาห์ (9 พารามิเตอร์ต่อกองใน E-X2) → ความคลาดเคลื่อนของ β สูงในไตรมาสแรกๆ · SE ของ B ไม่รวม cov ข้ามกอง",
           "ช่วงถือใช้สัปดาห์ศุกร์ ไม่ใช่วันซื้อจริง (เหลื่อม 1–4 วันทำการต่อขอบ) · class ต่างใช้ตัวแทน family (ค่าธรรมเนียม/hedge ต่าง — PRINCIPAL GOPP-C flag N เทียบ -A flag Y) · K-GOLD-A(A) โดน NAV ศุกร์ขาด 7 ไตรมาส",
           "(m10) t วันศุกร์ 8 ไตรมาส: แถว anchor t ของหน้าต่าง β ใช้ราคาปิด NY ของวัน t หลังเวลาตัดสินใจไทยไม่กี่ชั่วโมง · รับได้เพราะซื้อจริงที่ e",
           "V เป็นความแปรปรวนแบบระยะยาว (ป้ายใน §3) · ส่วนเฉพาะตัวอิสระข้ามกองในตารางหลัก · Σ_f lag 0",
           "DAOL-GOLD / FCSCBSETE ไม่มี factor ตรงสินทรัพย์ในชุดหลัก (P-A) · CMA 'ผ่านแบบขอบ' ใน S012 (P-B) · CANARY / VSL / GC เป็นกติกาจัดสรร ไม่ใช่ factor (ผลของการจัดสรรอยู่ใน P-C เท่านั้น)",
           "ผลรวมรายสัปดาห์ ≠ ผลตอบแทนทบต้น → แสดงบรรทัด K เสมอ · ห้ามใช้ Carino / log linking (ไม่ลงทะเบียน)",
           "ช่วง 2022-04 → 2025-12 ไม่อิสระกับการเลือก M052 (P2) · ความคาดหมายข้อ 9 ไม่อิสระบางส่วน",
           "A (α) เป็นค่าคงที่จากหน้าต่าง ≤ t ยกไปใช้ในช่วงถือ ไม่ใช่ α ที่ได้จริง · K เป็นพจน์ทบต้นของทุกส่วน ไม่ใช่แหล่งแยก · ส่วนแบ่ง % ปี 2022 ฐานเล็ก (ใช้ pp) · ข้อสรุปเรื่องอันดับที่มา / การกระจุก / A + E ขึ้นกับ P-A (ดู §3.1 §4.4 §8) · ความคาดหมายข้อ 4 เทียบ x ≥ 0.75 แบบไม่มีค่าเผื่อ (งานถัดไปใช้ 1e-9)"]:
    A("- " + t_)
A("\n## 10. ต้องให้ผู้ใช้ตัดสินใจ\n")
A("- ไม่มีข้อเปิด (ค่าเริ่มต้น BRIEF 123 ใช้ครบ) · **จุดหยุด BRIEF 122:** หลังอธิบายพอร์ต → ทีม factor เสนอกติกาคุมความเสี่ยงตอนเลือกกอง (ส่วน (ข)) ก่อนทีม quant รัน backtest\n")
NOTES_F = DEFAULT_OUT / "analyst_notes.md"
if NOTES_F.exists() and not SIM:
    A("\n" + NOTES_F.read_text(encoding="utf-8"))
A("\n## 11. การรันและความสอดคล้อง (BRIEF 106)\n")
if not SIM:
    A("- **รอบแก้หลังรีวิวผล (REVISE · BRIEF 124):** รอบแรก (v1) run.py sha `a81a840219a2…` เก็บที่ `run_v1.py` · log `run_pre_v1.log` / `run_v1.log` · ผลก่อนแก้เก็บที่ `v1_before_review/` · รอบนี้ phase pre และ full ใช้ run.py ตัวเดียวกัน · การแก้ทั้งหมด (ข้อความ / ตารางเพิ่ม / ไฟล์ `concentration_PA.csv`) อยู่ใน `decisions_post_review.md` (เขียนก่อนรันใหม่) · ไม่เปลี่ยนส่วนคำนวณชุดหลัก")
    _oldp = {l.split()[1]: l.split()[0] for l in (DEFAULT_OUT / "v1_before_review" / "pre_files_sha.txt").read_text().splitlines() if l.strip()}
    _same = {k: io_l1.sha256_file(OUT / k) == v for k, v in _oldp.items()}
    _oldm = {l.split()[1]: l.split()[0] for l in (DEFAULT_OUT / "v1_before_review" / "main_files_sha.txt").read_text().splitlines() if l.strip()}
    _samem = {k: io_l1.sha256_file(OUT / k) == v for k, v in _oldm.items()}
    A(f"- **ไฟล์ phase pre เทียบรอบ v1: {sum(_same.values())}/{len(_same)} ไฟล์ตรงทุกบิต · ไฟล์ผลชุดหลัก (attribution · reconcile · ภาคผนวก · expectations) {sum(_samem.values())}/{len(_samem)} ไฟล์ตรงทุกบิต** ({'ครบ' if all(_same.values()) and all(_samem.values()) else 'ต่าง: ' + ', '.join(k for k, v in {**_same, **_samem}.items() if not v)})")
    A("- **m6 (เปิดเผย):** ในรอบแรก (v1) มีการรัน phase full จริง 2 ครั้งด้วยโค้ดเดียวกัน (21:18:12 แล้วอีกครั้ง 21:20:33 หลังเพิ่ม `analyst_notes.md`) · `run.log` บันทึกเฉพาะครั้งหลัง · ผลเหมือนกันทุกไฟล์ยกเว้น results.md (ฝัง notes) · ไม่กระทบผล")
    A("- **m5:** การตรวจ NAVDate ของ ONE-INDIAOPP-RA (n1) เก็บสคริปต์ที่ `check_navdate_one.py` → `navdate_check.csv` (อ่านเฉพาะ FundCode / NAVDate จาก `nav_history_db.csv` แบบอ่านอย่างเดียว) — รันซ้ำได้ ไม่อยู่ใน repro ของ run.py")
A(f"- run.py sha256 phase pre `{RUN_SHA_PRE}` · phase full `{RUN_SHA}` · {'**ต่างกัน — diff ด้านล่าง**' if RUN_CHANGED else 'เท่ากัน (ไม่มีการแก้ run.py ระหว่าง phase)'} · สำเนา `run_pre.py` เก็บไว้ตอนเริ่ม phase pre · ไฟล์ phase pre ถูกคำนวณซ้ำใน phase full และตรงทุกบิต · ผลซ้ำ: `repro_check.json` · pytest: `pytest_all.log`")
if RUN_CHANGED and (OUT / "run_pre.py").exists():
    import difflib
    dl = list(difflib.unified_diff((OUT / "run_pre.py").read_text().splitlines(), Path(__file__).read_text().splitlines(), "run_pre.py", "run.py", lineterm="", n=0))
    A("```diff\n" + "\n".join(dl[:400]) + "\n```")
(OUT / "results.md").write_text("\n".join(M) + "\n", encoding="utf-8")

# ───────────── run_meta.json ─────────────
import scipy  # noqa: E402
import statsmodels  # noqa: E402
SKIP_OUT = {"run.log", "run_pre.log", "run_meta.json", "run_meta_pre.json", "results.md", "repro_check.json", "pytest_all.log", "run_pre.py", "run.py", "decisions_pre_run.md",
            "repro_check.py", "analyst_notes.md", "run_v1.py", "run_v1.log", "run_pre_v1.log", "check_navdate_one.py", "navdate_check.csv", "decisions_post_review.md", "addendum_s1.py",
            "addendum_s1.csv", "addendum_s1_check.json"}
OUTS = {p.name: io_l1.sha256_file(p) for p in sorted(OUT.iterdir()) if p.is_file() and p.name not in SKIP_OUT}
meta = dict(created=datetime.now().isoformat(timespec="seconds"), phase="full", seed=SEED, sim=SIM, smoke=SMOKE, runtime_sec=round(time.time() - T0, 1), python=platform.python_version(),
            versions=dict(numpy=np.__version__, pandas=pd.__version__, scipy=scipy.__version__, statsmodels=statsmodels.__version__), spec_files=SPEC_FILES,
            spec_sha256={f: io_l1.sha256_file(TEAM / f) for f in SPEC_FILES}, run_py_sha256=RUN_SHA, run_py_sha256_pre=RUN_SHA_PRE, run_py_changed_between_phases=RUN_CHANGED,
            data_pins_sha256=PIN, lib_sha256=LIBH, decisions_sha256=DEC_SHA, expectations=dict(ok=n_ok, ok_excl_9=n_ok_ex9), output_sha256=OUTS)
(OUT / "run_meta.json").write_text(json.dumps(meta, indent=1, ensure_ascii=False, default=_jdef))
log(f"เสร็จ · runtime {time.time() - T0:.1f}s")
