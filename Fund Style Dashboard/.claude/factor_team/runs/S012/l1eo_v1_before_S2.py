"""l1eo — F5-EO (S012 + S013 addendum) · แยกกอง E / O · ไม่แก้ไฟล์ lib เดิม · ไม่นับ trial
ส่วน A: pins · โหลด · ตารางจับคู่กลุ่ม (กฎชื่อ) · ต่อรหัส · ชุดกอง
ส่วน B: pool factor · stepwise · placebo · factor กลุ่ม · E-PCA · hybrid · ชุด O
ส่วน C: Shapley · sig_count · cluster_bootstrap · รายงานราย factor · GRS พอร์ต · lead diagnostic
"""
import re
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

import external as ex
import forms as fm_
import hybrid as hy
import io_l1
import l2
import l3
import l4
import pca as pc
import regress as rg
import samples as sp
import scorecard as sc
import tests_stat as ts

SEED = 20261015
TEAM = io_l1.TEAM
ROOT = io_l1.ROOT
DAT = io_l1.DATA
MAIN_START, MAIN_END = io_l1.MAIN_START, io_l1.MAIN_END
MONTH_START, MONTH_END = io_l1.MONTH_START, io_l1.MONTH_END
SPLICE_WEEK = "2023-12-08"
GMAP_SHA = "898a86867b3f832060f7620d039fd95338d24e1bb71f531d76bb58004223fceb"
PCASETS_SHA = "175023c5cf978c550b40397e608523577e376dcf63d3c43cde38b33ef4770bbf"

# ───────────────────────── ส่วน A ─────────────────────────
# sha256 เต็มของ S013 §4 (base: team = .claude/factor_team · root = Fund Style Dashboard)
S013_PINS = {
    ("team", "data/panel_weekly.parquet"): "95c16ee651d3a936788b7cb3c6372bbf5f1e84cb39daf5680343771dca24270b",
    ("team", "data/panel_monthly.parquet"): "e8e8cb5d5f04fba9bb35558ef7c3d8195c656334119e56f82775cc1ae21ccaed",
    ("team", "data/factors_weekly.parquet"): "115b87139d2bec0fd57a77a1593c46d36bb23f3f35f83236cdb07be642af47a8",
    ("team", "data/factors_monthly.parquet"): "f7c4248b4fa889853024449e72ae8909cf1f8d3226a54eebc37448a2a485bb72",
    ("team", "data/factors_ext_weekly.parquet"): "3105b6e7fe32ffd3648e8feac8dbd03a8db22b7e8eb245c5faf462b14da5e296",
    ("team", "data/factors_ext_monthly.parquet"): "ce53d371ae847ee8d8dcd2d33a7b0f30f5db01bb993bef8599598e05af4db792",
    ("team", "data/factors_eo_weekly.parquet"): "87b793508d83d2a4235eb07f1ff584cd32493375d5f73f8c6711f172f2a0bfca",
    ("team", "data/factors_eo_monthly.parquet"): "c13c36e7dd2b039116131092b757160ae83460478829af3b7234afdd67bef82f",
    ("team", "data/manifest_eo.json"): "281756a4787e4ade4b8474571e8c49a9dac4b11b995b21b74d9197334b052681",
    ("team", "data/aum_fam.parquet"): "e442f6ae8f09ff01fb23a3b25aa89e2b98da8af9134143f0a873913e7ef2db46",
    ("team", "data/universe.csv"): "fdfb7830df78ce032465ac9d8cddc2c98f9aa86cfa0f3925fdb83026aa3f7252",
    ("team", "data/dup_pairs.csv"): "b1f0f0c745947fa70803a4f40526c0a1967c72925be985a2bedc1057d8b8aef3",
    ("root", "base_data/FundProfile.csv"): "9516281426fc854c8f3a0833f119cad0ce581adb39450732e579084cb4cedfaf",
    ("team", "specs/S012_group_map.csv"): GMAP_SHA,
    ("team", "specs/S013_pca_sets.csv"): PCASETS_SHA,
    ("team", "runs/S003/factors_S003_weekly.parquet"): "be3ceb2e34b0df1f1a3db27d59e1a103cf5f5a5ca38f2e87f7c812c1c53944ac",
    ("team", "runs/S005/primary_index.csv"): "5a94ab9b498bb107600938d37f665c7263d9f0a5973460159c09ae83a799275c",
    ("team", "runs/S006/resid_B_coef.csv"): "71af654fc789a24d79999d96d7149e05e75007ac6e8f83d33bd0355d292eef0b",
    ("team", "runs/S009/alpha_fund.csv"): "7a2dea7a928cb529547e8edde8e1f0f31a7ab603bcffd69cd6f2ef6400302894",
    ("team", "runs/S003/run.py"): "9f21e388306cea0f63d6591580f03c505006fd6ca8d6161e2ef13cfcdce5590f",
    ("team", "runs/S006/run.py"): "5515b2893fe0188c9135fa7728dd45f091534f03754bf529609b244c03c4f760",
}


def _pin_path(base, rel):
    return (TEAM if base == "team" else ROOT) / rel


def check_pins(pins=None):
    """ตรวจ sha256 เต็มทุกไฟล์ในตาราง S013 §4 · ไม่ตรง = raise (หยุด) · คืน dict rel → sha"""
    pins = S013_PINS if pins is None else pins
    out = {}
    for (base, rel), want in pins.items():
        got = io_l1.sha256_file(_pin_path(base, rel))
        if got != want:
            raise ValueError(f"sha256 ไม่ตรง S013 §4: {rel}: {got} != {want}")
        out[rel if base == "team" else rel] = got
    return out


def load_eo(freq="W", verify=True):
    """ตรวจ manifest_eo.json (sha256 ของไฟล์ factor EO) → factor EO ช่วงหลัก (ตัดแถว > 2025-12-26 สำหรับการ fit)"""
    if verify:
        io_l1.verify_manifest(
            paths=[".claude/factor_team/data/factors_eo_weekly.parquet", ".claude/factor_team/data/factors_eo_monthly.parquet"],
            root=ROOT, manifest_path=DAT / "manifest_eo.json",
            expected={".claude/factor_team/data/factors_eo_weekly.parquet": S013_PINS[("team", "data/factors_eo_weekly.parquet")],
                      ".claude/factor_team/data/factors_eo_monthly.parquet": S013_PINS[("team", "data/factors_eo_monthly.parquet")]})
    if freq == "W":
        return pd.read_parquet(DAT / "factors_eo_weekly.parquet").loc[MAIN_START:MAIN_END].copy()
    return pd.read_parquet(DAT / "factors_eo_monthly.parquet").loc[MONTH_START:MONTH_END].copy()


def load_ext(freq="W"):
    if freq == "W":
        return pd.read_parquet(DAT / "factors_ext_weekly.parquet").loc[MAIN_START:MAIN_END].copy()
    return pd.read_parquet(DAT / "factors_ext_monthly.parquet").loc[MONTH_START:MONTH_END].copy()


# ───────────── กฎชื่อกอง (S012 ข้อ 4.4.1 · m13: \b นำหน้า EX) ─────────────
def norm_name(s):
    s = " " + str(s).upper() + " "
    s = re.sub(r"\bEX[\s\-]*JAPAN", " ", s)
    s = re.sub(r"\bEX[\s\-]*US\b", " ", s)
    s = re.sub(r"[^A-Z0-9&\.]+", " ", s)
    return " " + re.sub(r"\s+", " ", s).strip() + " "


# (ลำดับ, key, regex คำตาม F-R006 (stem ขึ้นต้นคำ), regex คำพ้อง, factor, I_g column, ที่มา, ให้ factor ได้?)
RULES = [
    (0, "TH", r"\bSET\b|\bTHAI", "", "TDEX", "TDEX_THB", "ป้าย designer", False),
    (0, "METAL", r"\bGOLD\b|\bSILVER\b|\bMINING\b|\bMETALS?\b", "", "GLD", "GLD_THB", "ป้าย designer", False),
    (1, "CHINA", r"\bCHINA", r"\bCHINESE", "e_CHINA(grp)", "MSCI_CHINA_ALL_SHARES", "F-R006 E1/E2", True),
    (1, "INDIA", r"\bINDIA", r"\bBHARAT", "e_INDIA", "MSCI_INDIA", "F-R006 E2 (C11)", True),
    (1, "VIETNAM", r"\bVIETNAM", "", "e_VIETNAM", "MSCI_VIETNAM", "F-R006 E2 (C11)", True),
    (1, "JAPAN", r"\bJAPAN", r"\bNIPPON", "e_JAPAN", "MSCI_JAPAN", "F-R006 E2 (C11)", True),
    (1, "KOREA", r"\bKOREA", "", "e_KOREA", "MSCI_KOREA", "C11", True),
    (1, "TAIWAN", r"\bTAIWAN", "", "e_TAIWAN", "MSCI_TAIWAN", "C11", True),
    (1, "BRAZIL", r"\bBRAZIL", "", "e_BRAZIL", "MSCI_BRAZIL", "C11", True),
    (1, "ASEAN", r"\bASEAN", "", "e_ASEAN", "MSCI_ASEAN", "F-R006 E2 (C11)", True),
    (1, "EUROPE", r"\bEURO", "", "e_EUROPE", "MSCI_EUROPE", "F-R006 E2 (C11)", True),
    (1, "USA", r"\bUS\b|\bUSA\b|\bS&P", r"\bU\.S\.|\bAMERICA|\bNASDAQ|\bNDQ", "e_USA", "MSCI_USA", "F-R006 E2 (C11)", True),
    (1, "ASIA", r"\bASIA|\bPACIFIC\b|\bAPAC\b", "", "e_ASIA", "MSCI_ASIA_EX_JAPAN", "designer · ผู้ใช้รับ (BRIEF 115(5))", True),
    (1, "EM", r"\bEMERGING\b|\bEM\b|\bGEM\b", "", "e_EM", "MSCI_EM", "ป้าย designer", False),
    (2, "HEALTH", r"\bHEALTH|\bMEDIC|\bBIOTECH|\bGENOM", "", "e_HC", "MSCI_ACWI_HC", "F-R006 E3", True),
    (2, "CLEAN", r"\bCLEAN|\bRENEW|\bNEW ?ENERGY|\bNEWENGY|\bCLIMATE", "", "e_ICLN", "ICLN_THB", "F-R006 E3", True),
    (2, "INFRA", r"\bINFRA", "", "e_IGF", "IGF_THB", "F-R006 E3", True),
    (2, "PROP", r"\bPROP|\bREIT", "", "e_REET", "REET_THB", "F-R006 E3", True),
    (2, "FIN", r"\bFINANCIAL|\bFINANCE\b|\bBANK", "", "e_FN", "MSCI_ACWI_FN", "ป้าย designer", False),
    (2, "CONSUMER", r"\bBRANDS?\b|\bLUXURY|\bCONSUMER|\bLIFESTYLE", "", "e_CD", "MSCI_ACWI_CD", "ป้าย designer", False),
    (2, "INNOV", r"\bINNOVAT|\bDISRUPT|\bNEXT ?GEN", "", "e_ARKK", "ARKK_THB", "F-R006 E3", True),
    (2, "TECH", r"TECH|\bDIGITAL|\bAI\b|\bROBOT|\bCYBER|\bCLOUD|\bSEMI", "", "e_IT", "MSCI_ACWI_IT", "F-R006 E3", True),
    (3, "STYLE", r"DIVIDEND|\bINCOME\b|LOW VOLATILITY|\bVALUE\b|\bQUALITY\b|\bMOAT\b|SMALL|\bMID\b", "", None, None, "ป้าย (ใช้ style ร่วม)", False),
    (4, "GLOBAL", r"\bGLOBAL\b|\bWORLD\b|\bINTERNATIONAL\b", "", None, None, "ป้าย (ไม่มี factor กลุ่ม)", False),
]
RMAP = {r[1]: r for r in RULES}
ALLOWED = {r[1] for r in RULES if r[7]}
ASIAN = ("CHINA", "INDIA", "VIETNAM", "ASEAN", "KOREA", "TAIWAN")
# คำที่ designer เพิ่มเองและถูกตัด (BRIEF 115(1)) — ห้ามอยู่ใน regex ที่ให้ factor (test_eo_10)
CUT_WORDS = ("BATTERY", "TRANSITION", "PLANETARY", "GREEN ENERGY", "INTERNET", "METAVERSE", "BLOCKCHAIN", "E-COMMERCE", "ESPORT",
             "ARTIFICIAL", "PHARMA", "REAL ESTATE", "AEC", "INDONESIA", "MALAYSIA", "PHILIPPIN", "SINGAPORE", "SOUTHEAST",
             "CONTINENTAL", "VIET", "VN")


def apply_name_rules(name_en, syn=True):
    """→ (ลำดับ, กลุ่มชื่อ, คำที่ตรง, ใช้คำพ้องหรือไม่) · คำแรกที่ตรงตามลำดับชนะ"""
    n = norm_name(name_en)
    for lvl, key, rx, rxs, fac, col, src, allowed in RULES:
        m = re.search(rx, n)
        if m:
            return lvl, key, m.group(0).strip(), False
        if syn and rxs:
            m = re.search(rxs, n)
            if m:
                return lvl, key, m.group(0).strip(), True
    return 9, "NONE", "", False


def _fc_key(df):
    fc = df["fund_class"]
    cnt = fc.groupby(fc).size()
    return [(s if isinstance(s, str) and s else (f if isinstance(f, str) and cnt.get(f, 0) > 1 else c))
            for c, f, s in zip(df["FundCode"], fc, df["splice_id"].fillna(""))]


def build_groups(df, basis_min=5):
    """df: ตารางกองทั้งหมดใน U (คอลัมน์ FundCode · name_en · fund_class · splice_id · policy) → DataFrame ของกอง E:
    name_group · group (กลุ่มแม่) · group_factor · alt_factor_no_synonym · group_n_U · group_ok (S012 ข้อ 4.4.2 · เกณฑ์ ≥ 5 จาก U_E ทั้งหมด)"""
    df = df.copy()
    df["fc_key"] = _fc_key(df)
    E = df[df["policy"] == "E"].copy()
    rows = [apply_name_rules(n) for n in E["name_en"]]
    E["name_group"] = [r[1] for r in rows]
    E["matched_word"] = [r[2] for r in rows]
    E["by_synonym"] = [r[3] for r in rows]
    E["name_group_nosyn"] = [apply_name_rules(n, syn=False)[1] for n in E["name_en"]]

    def build(col):
        g0 = E.groupby(col)["fc_key"].nunique().to_dict()
        grp = E[col].copy()
        for k in ASIAN:
            if g0.get(k, 99) < 5:
                grp[E[col] == k] = "ASIA"
        cnts = E.assign(_g=grp).groupby("_g")["fc_key"].nunique().to_dict()
        fac, ok = [], []
        for g in grp:
            if g not in ALLOWED or cnts[g] < basis_min:
                fac.append("ไม่มี"); ok.append(False)
            else:
                fac.append(RMAP[g][4]); ok.append(True)
        return g0, grp, cnts, fac, ok

    g0, grp, cnts, fac, ok = build("name_group")
    _, _, _, fac_ns, _ = build("name_group_nosyn")
    E["group"] = grp
    E["group_factor"] = fac
    E["group_ok"] = ok
    E["alt_factor_no_synonym"] = fac_ns
    E["group_n_U"] = [cnts[g] for g in grp]
    return E


def load_group_map(path=None, sha=GMAP_SHA):
    """CSV ตารางจับคู่ (ตรวจ sha · ทุกกอง ≤ 1 factor) + คอลัมน์ unit = splice_id หรือ FundCode"""
    path = Path(path) if path else TEAM / "specs" / "S012_group_map.csv"
    if sha is not None:
        got = io_l1.sha256_file(path)
        if got != sha:
            raise ValueError(f"sha256 group_map ไม่ตรง: {got}")
    g = pd.read_csv(path)
    assert g["FundCode"].is_unique, "FundCode ซ้ำใน group_map"
    assert g["group_factor"].map(lambda x: isinstance(x, str)).all()
    g["splice_id"] = g["splice_id"].fillna("")
    g["unit"] = np.where(g["splice_id"] != "", g["splice_id"], g["FundCode"])
    return g


# ───────────── ต่อรหัส (S013 §2 · ตารางล็อก · ไม่สร้าง id ด้วยการตัดสตริง) ─────────────
SPLICE_TABLE = {
    "I-GOLD*": ("I-GOLD", "IGOLD-G"),
    "ES-GCG*": ("TMB-ES-GCG", "ES-GCG-A"),
    "ES-GINNO*": ("TMB-ES-GINNO", "ES-GINNO-A"),
    "ES-GINFRA*": ("TMBGINFRA", "ES-GINFRA-A"),
}


def code_to_unit(table=SPLICE_TABLE):
    m = {}
    for u, (o, n) in table.items():
        m[o] = u
        m[n] = u
    return m


def splice_units(R, table=SPLICE_TABLE, week=SPLICE_WEEK):
    """R (date × FundCode) → (RU คอลัมน์หน่วย เรียงตามตัวอักษร, ตารางต่อรหัส)
    อนุกรม = รหัสเก่าทุกแถวก่อน `week` + รหัสใหม่ตั้งแต่ `week` (S013 §2 · สัปดาห์ซ้อนใช้รหัสใหม่) · panel L0 ไม่ถูกแก้"""
    wk = pd.Timestamp(week)
    RU = R.copy()
    rows = []
    for u, (o, n) in table.items():
        if o not in RU.columns or n not in RU.columns:
            raise KeyError(f"ไม่มีรหัสต่อ {u}: {o} / {n}")
        old, new = R[o], R[n]
        s = old.where(R.index < wk, new)
        rows.append(dict(unit=u, old=o, new=n, week=week, n_old_rows=int(old.notna().sum()), n_new_rows=int(new.notna().sum()),
                         n_overlap_rows=int((old.notna() & new.notna()).sum()),
                         old_ret_at_week=float(old.loc[wk]) if wk in old.index and np.isfinite(old.loc[wk]) else np.nan,
                         new_ret_at_week=float(new.loc[wk]) if wk in new.index and np.isfinite(new.loc[wk]) else np.nan,
                         old_rows_after_week=int(old.loc[old.index > wk].notna().sum()), new_rows_before_week=int(new.loc[new.index < wk].notna().sum())))
        RU = RU.drop(columns=[o, n])
        RU[u] = s
    RU = RU[sorted(RU.columns)]
    tbl = pd.DataFrame(rows)
    return RU, tbl


def splice_monthly(Rm, table=SPLICE_TABLE):
    """รายเดือน: อนุกรมต่อ = รหัสใหม่ถ้ามีค่า · ไม่มี → รหัสเก่า (สอดคล้องกติกา S013 §2: เดือนซ้อนใช้รหัสใหม่)"""
    RU = Rm.copy()
    for u, (o, n) in table.items():
        s_ = Rm[n].combine_first(Rm[o])
        RU = RU.drop(columns=[o, n])
        RU[u] = s_
    return RU[sorted(RU.columns)]


def detect_splice_pairs(meta, NN):
    """ตรวจกติกา S012 ข้อ 2.3 (ก–จ) บนตารางกองใน U · meta: DataFrame index FundCode (policy · name_en · reg_date · fund_class) ·
    NN: bool (date × FundCode) ผลตอบแทนไม่ว่าง → list ของ dict(old, new, overlap)"""
    def _nm(x):
        x = re.sub(r"\b(TMB|EASTSPRING|FUND)\b", " ", str(x).upper())
        return re.sub(r"\s+", " ", x).strip()

    out = []
    for reg, grp_ in meta.groupby("reg_date"):
        if len(grp_) < 2:
            continue
        codes = sorted(grp_.index)
        for i in range(len(codes)):
            for j in range(i + 1, len(codes)):
                a_, b_ = codes[i], codes[j]
                if meta.policy[a_] != meta.policy[b_] or _nm(meta.name_en[a_]) != _nm(meta.name_en[b_]):
                    continue
                ov = int((NN[a_] & NN[b_]).sum())
                fa, fb = meta.fund_class[a_], meta.fund_class[b_]
                if isinstance(fa, str) and fa == fb and ov > 1:
                    continue
                if ov > 1:
                    continue
                old, new = sorted([a_, b_], key=lambda c: NN.index[NN[c]].min())
                out.append(dict(old=old, new=new, overlap=ov))
    return out


# ───────────── ชุดกอง (S013 §1) ─────────────
def eo_sets(RU, pol, dup_pairs, c2u=None):
    """RU: ผลตอบแทนระดับหน่วย (date × unit · ช่วงหลักเท่านั้น) · pol: Series unit → E/O ·
    dup_pairs: DataFrame a,b (รหัสระดับ L0 → แปลงเป็นหน่วยก่อน dedup_keep) →
    DataFrame(unit, policy, n_weeks_main, n_train_raw, n_train_dimson, n_test, sel, eval, eval52, stab, dedup_keep, pca_balanced, pca_unbal52)
    n_weeks_main = จำนวนแถวที่มีผลตอบแทนในช่วงหลัก ≤ 2025-12-26 (S013 §1)"""
    c2u = code_to_unit() if c2u is None else c2u
    idx = RU.index
    pos1 = np.arange(len(idx)) >= 1
    mtr, mte = sp.window_mask(idx, "train"), sp.window_mask(idx, "test")
    mh1, mh2 = sp.window_mask(idx, "H1"), sp.window_mask(idx, "H2")
    nn = RU.notna()
    n_main = nn.sum()
    n_raw = nn.loc[mtr].sum()
    n_trd = nn.loc[mtr & pos1].sum()
    n_te = nn.loc[mte].sum()
    n_h1 = nn.loc[mh1 & pos1].sum()
    n_h2 = nn.loc[mh2 & pos1].sum()
    dupu = pd.DataFrame({"a": dup_pairs["a"].map(lambda z: c2u.get(z, z)), "b": dup_pairs["b"].map(lambda z: c2u.get(z, z))})
    keep_all = set()
    for p in ("E", "O"):
        units = [u for u in RU.columns if pol[u] == p]
        d = dupu[dupu["a"].isin(units) & dupu["b"].isin(units)]
        keep_all |= set(sp.dedup_keep(d, n_main[units]))
    full_tr = int(mtr.sum())
    rows = []
    for u in sorted(RU.columns):
        ev = bool(n_trd[u] >= 104 and n_te[u] >= 52)
        dk = u in keep_all
        rows.append(dict(unit=u, policy=pol[u], n_weeks_main=int(n_main[u]), n_train_raw=int(n_raw[u]), n_train_dimson=int(n_trd[u]),
                         n_test=int(n_te[u]), sel=bool(n_trd[u] >= 104), eval=ev, eval52=bool(n_trd[u] >= 52 and n_te[u] >= 52),
                         stab=bool(ev and n_h1[u] >= 104 and n_h2[u] >= 104), dedup_keep=dk,
                         pca_balanced=bool(dk and n_raw[u] == full_tr), pca_unbal52=bool(dk and n_raw[u] >= 52)))
    return pd.DataFrame(rows)


SET_COLS = ["sel", "eval", "eval52", "stab", "dedup_keep", "pca_balanced", "pca_unbal52"]


def compare_sets(sets, csv):
    """เทียบรายชื่อหน่วยทุกชุดกับ S013_pca_sets.csv (ไม่ใช่แค่จำนวน) → dict ชุด → (ขาด, เกิน) ว่าง = ตรง"""
    a = sets.set_index("unit")
    b = csv.set_index("unit")
    out = {}
    if set(a.index) != set(b.index):
        out["__units__"] = (sorted(set(b.index) - set(a.index)), sorted(set(a.index) - set(b.index)))
    common = sorted(set(a.index) & set(b.index))
    for c in SET_COLS:
        A = set(x for x in common if bool(a.loc[x, c]))
        B = set(x for x in common if bool(b.loc[x, c]))
        if A != B:
            out[c] = (sorted(B - A), sorted(A - B))
    for c in ("n_weeks_main", "n_train_raw", "n_train_dimson", "n_test"):
        bad = [x for x in common if int(a.loc[x, c]) != int(b.loc[x, c])]
        if bad:
            out[c] = (bad, [])
    return out


def set_lists(sets):
    return {c: sorted(sets.loc[sets[c], "unit"]) for c in SET_COLS}


# ───────────────────────── ส่วน B ─────────────────────────
POOL_E = ["e_CHINA", "EMDM", "TERM", "SMB", "HML", "RMW", "CMA", "WML", "JKP_EM_value", "JKP_EM_momentum", "FX"]
POOL_A1 = ["e_CHINA", "EMDM", "TERM", "Momentum", "Quality", "Value", "LowVol", "JKP_EM_value", "JKP_EM_momentum", "FX"]
KF5 = ["SMB", "HML", "RMW", "CMA", "WML"]
LONG_SHORT_DAILY = ("SMB", "HML", "RMW", "CMA", "WML", "JKP_EM_value", "JKP_EM_momentum")  # factor ที่ทบจากรายวัน (lead diagnostic)


def _nanmed(a, axis=0):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        return np.nanmedian(a, axis=axis)


def _nanmean(a, axis=0):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        return np.nanmean(a, axis=axis)


def mkt_series(F):
    return (F["MSCI_ACWI"] - F["RF_BOT"]).rename("MKT")


def fx_series(F):
    return (F["SHV_THB"] - F["RF_BOT"]).rename("FX")


def china_excess(F):
    return (F["MSCI_CHINA_ALL_SHARES"] - F["RF_BOT"]).rename("e_CHINA")


def pool_E(F, Fext, Feo, mask_tr, variant="main", kf_prefix="KF_DEV_"):
    """→ (core DataFrame[MKT], pool DataFrame (11 หรือ 10 คอลัมน์ ตามลำดับล็อก), coef ของ residualize e_CHINA)
    e_CHINA = residualize(MSCI_CHINA_ALL_SHARES − RF | [MKT], train · lag 0 · เก็บค่าคงที่)"""
    mkt = mkt_series(F)
    e_china, coef = l3.residualize(china_excess(F), mkt.to_frame(), mask_tr)
    cols = {"e_CHINA": e_china["e_CHINA"], "EMDM": F["MSCI_EM"] - F["MSCI_WORLD"], "TERM": F["IEF_USD"] - F["SHV_USD"]}
    for s in KF5:
        cols[s] = Feo[kf_prefix + s]
    for s in ("Momentum", "Quality", "Value", "LowVol"):
        cols[s] = F[s]
    cols["JKP_EM_value"] = Feo["JKP_EM_value"]
    cols["JKP_EM_momentum"] = Feo["JKP_EM_momentum"]
    cols["FX"] = fx_series(F)
    order = POOL_E if variant == "main" else POOL_A1
    pool = pd.DataFrame({c: cols[c] for c in order}, index=F.index)
    return mkt.to_frame(), pool, coef


def resid_spec_E(F):
    """ตัวแปร residualize ที่ด่าน G3 ต้องประมาณ β ใหม่จาก pseudo-train (e_CHINA)"""
    mkt = mkt_series(F).to_frame()
    ch = china_excess(F)
    return {"e_CHINA": lambda m: l3.residualize(ch, mkt, m)[0]["e_CHINA"]}


def sel_reps(R, funds, mask_tr, thr=0.95, min_overlap=52):
    """ตัวแทนกลุ่มกองอิสระ (S012 ข้อ 4.2 ข้อ 1): corr ≥ thr (train · single linkage) → 1 หน่วยต่อกลุ่ม = แถว train (Dimson) มากสุด · เสมอ → ตามตัวอักษร
    → (reps DataFrame(group_id, rep, n_train_rows, group_size), clusters DataFrame(FundCode, group_id, group_size))"""
    funds = list(funds)
    cl = l2.fund_clusters(R, mask_tr, funds, thr, min_overlap)
    pos1 = np.arange(len(R.index)) >= 1
    ntr = R.loc[np.asarray(mask_tr, bool) & pos1, funds].notna().sum()
    rows = []
    for gid, d in cl.groupby("group_id", sort=True):
        rep = sorted(d["FundCode"], key=lambda c: (-int(ntr[c]), c))[0]
        rows.append(dict(group_id=int(gid), rep=rep, n_train_rows=int(ntr[rep]), group_size=int(len(d))))
    return pd.DataFrame(rows), cl


def _pseudo_delta(y, DM, Dj, m_tr, m_te, min_tr=52, min_te=26):
    """ΔR²_pseudo = R²(M+j) − R²(M) · fit บน pseudo-train (แถวร่วม) ทำนาย pseudo-test ด้วย coef ตรึง · ไม่ครบแถว → NaN"""
    DMj = np.hstack([DM, Dj])
    ok_all = np.isfinite(y) & np.isfinite(DMj).all(1)
    itr, ite = m_tr & ok_all, m_te & ok_all
    if itr.sum() < min_tr or ite.sum() < min_te:
        return np.nan

    def r2(D):
        X = np.column_stack([np.ones(int(itr.sum())), D[itr]])
        b = np.linalg.lstsq(X, y[itr], rcond=None)[0]
        return rg.r2_oos(y[ite], b[0] + D[ite] @ b[1:])
    return r2(DMj) - r2(DM)


def stepwise_eo(R, core, pool, mask_tr, reps, tau=-2.0, k_max=6, pseudo=None, resid_spec=None, tag="real"):
    """forward stepwise ของ factor ร่วม (S012 ข้อ 4.2 · train เท่านั้น) → (selected, log DataFrame, all_candidates DataFrame)
    score_j = median_i ΔBIC_ij ข้ามตัวแทน (แถวร่วมของ M และ M+j · m8) · j* = argmin (เสมอ → ลำดับใน pool) ·
    ด่านตามลำดับ: (G1) เพดาน |M| ≤ k_max (G2) score ≤ τ (G3) median ΔR²_pseudo > 0 · ด่านใดตก → หยุด (ไม่ลองอันดับถัดไป)
    pseudo = (mask pseudo-train, mask pseudo-test) · resid_spec: dict ตัวแปร → ฟังก์ชัน(mask) ประมาณใหม่บน pseudo-train (None = ไม่ residualize ซ้ำ)"""
    reps = list(reps)
    selected, logs, allc = [], [], []
    cand_all = l3._cand_dict(pool)
    Rv = R[reps].to_numpy(float)
    r = 0
    while True:
        r += 1
        rest = [c for c in pool.columns if c not in selected]
        n_core = core.shape[1] + len(selected)
        if not rest:
            logs.append(dict(tag=tag, round=r, best="", best_score=np.nan, second="", second_score=np.nan, tau=tau, n_core_before=n_core,
                             g1_cap_ok=False, g2_score_ok=False, g3_pseudo_ok=False, g3_median=np.nan, g3_n=0, action="stop_no_candidate", n_selected=len(selected)))
            break
        M = pd.concat([core, pool[selected]], axis=1) if selected else core
        Dcore = rg.lag_stack(M.to_numpy(float))
        dB, _, names = l3._delta_table(R, reps, mask_tr, Dcore, {c: cand_all[c] for c in rest})
        score = _nanmed(dB, axis=0)
        fin = np.isfinite(dB)
        share = np.array([float(np.mean(dB[fin[:, j], j] <= -2.0)) if fin[:, j].any() else np.nan for j in range(dB.shape[1])])
        order = np.argsort(np.where(np.isfinite(score), score, np.inf), kind="stable")
        for rk, j in enumerate(order, 1):
            allc.append(dict(tag=tag, round=r, candidate=names[j], score_median_dBIC=float(score[j]), share_reps_dBIC_le_m2=float(share[j]),
                             n_reps_used=int(fin[:, j].sum()), rank=rk))
        j = int(order[0])
        sec = int(order[1]) if len(order) > 1 else None
        best, bs = names[j], float(score[j])
        g1 = bool(n_core < k_max)
        g2 = bool(np.isfinite(bs) and bs <= tau)
        g3, g3med, g3n = True, np.nan, 0
        if pseudo is not None and np.isfinite(bs):
            m_ptr, m_pte = pseudo
            Mp = M.copy()
            if resid_spec:
                for c in list(Mp.columns):
                    if c in resid_spec:
                        Mp[c] = resid_spec[c](m_ptr)
            sj = pool[best]
            if resid_spec and best in resid_spec:
                sj = resid_spec[best](m_ptr)
            DM = rg.lag_stack(Mp.to_numpy(float))
            Dj = rg.lag_stack(sj.to_numpy(float).reshape(-1, 1))
            dl = np.array([_pseudo_delta(Rv[:, i], DM, Dj, m_ptr, m_pte) for i in range(len(reps))])
            g3n = int(np.isfinite(dl).sum())
            g3med = float(_nanmed(dl)) if g3n else np.nan
            g3 = bool(g3n > 0 and g3med > 0)
        ok = g1 and g2 and g3
        if ok:
            action = "added"
        elif not g1:
            action = "stop_cap"
        elif not g2:
            action = "stop_tau"
        else:
            action = "stop_g3_pseudo_oos"
        logs.append(dict(tag=tag, round=r, best=best, best_score=bs, second=names[sec] if sec is not None else "",
                         second_score=float(score[sec]) if sec is not None else np.nan, tau=tau, n_core_before=n_core,
                         g1_cap_ok=g1, g2_score_ok=g2, g3_pseudo_ok=g3, g3_median=g3med, g3_n=g3n, action=action,
                         n_selected=len(selected) + int(ok)))
        if not ok:
            break
        selected.append(best)
    return selected, pd.DataFrame(logs), pd.DataFrame(allc)


def tau_from_placebo(n_selected, best_scores, tau0=-2.0):
    """กฎ τ (S012 ข้อ 4.3): placebo เลือก 0 ตัวทุก shift → τ = τ₀ · เลือก ≥ 1 ตัวที่ shift ใด → τ = min(τ₀, min_s τ_s) (τ_s = score ดีที่สุดรอบแรก) → (τ, any_selected)"""
    any_sel = any(n > 0 for n in n_selected)
    return (min(tau0, min(best_scores)) if any_sel else tau0), bool(any_sel)


def placebo_eo(R, core, pool, mask_tr, reps, shifts=(26, 52), tau0=-2.0, k_max=6, pseudo=None):
    """S012 ข้อ 4.3: รัน stepwise (ด่าน G1–G3 · τ₀) โดยแทน candidate ทุกตัวด้วย circular_shift (MKT ไม่เลื่อน · e_CHINA เลื่อนหลัง residualize ·
    G3 ไม่ residualize ซ้ำ) → dict(shifts, tau, any_selected) · กฎ: เลือก 0 ทั้งคู่ → τ = τ₀ · เลือก ≥ 1 → τ = min(τ₀, min_s τ_s)"""
    out, taus, logs, allc = {}, [], [], []
    for s in shifts:
        P = l2.circular_shift(pool, mask_tr, s) if s else pool
        sel, lg, ac = stepwise_eo(R, core, P, mask_tr, reps, tau=tau0, k_max=k_max, pseudo=pseudo, resid_spec=None, tag=f"placebo{s}")
        out[int(s)] = dict(selected=list(sel), n_selected=len(sel), best_score_round1=float(lg["best_score"].iloc[0]), rounds=int(len(lg)))
        taus.append(out[int(s)]["best_score_round1"])
        logs.append(lg)
        allc.append(ac)
    tau, any_sel = tau_from_placebo([v["n_selected"] for v in out.values()], taus, tau0)
    return dict(shifts=out, tau=float(tau), tau0=tau0, any_selected=bool(any_sel),
                rule="placebo เลือก 0 ทั้งสอง shift → τ = −2" if not any_sel else "placebo เลือก ≥ 1 → τ = min(−2, min_s τ_s) + ป้าย 'selection ต้องปรับเกณฑ์ตาม placebo'",
                n_candidates_evaluated=int(sum(len(a) for a in allc)), logs=pd.concat(logs, ignore_index=True), cands=pd.concat(allc, ignore_index=True))


GNAME = {"e_CHINA(grp)": "e_CHINAg", "e_AH": "e_AH", "e_USA": "e_USA", "e_ASIA": "e_ASIA", "e_HC": "e_HC", "e_IT": "e_IT", "e_EUROPE": "e_EUROPE",
         "e_JAPAN": "e_JAPAN", "e_ARKK": "e_ARKK", "e_IGF": "e_IGF", "e_INDIA": "e_INDIA", "e_VIETNAM": "e_VIETNAM"}


def group_I(F, Fext, use_ah=False):
    """I_g ของ factor กลุ่ม (S012 ข้อ 3.2) · use_ah: CHINA = MSCI_CHINA_A_SHARES − MSCI_CHINA_H_SHARES (e_AH)"""
    rf = F["RF_BOT"]
    ch = (F["MSCI_CHINA_A_SHARES"] - F["MSCI_CHINA_H_SHARES"]).rename("e_AH") if use_ah else (F["MSCI_CHINA_ALL_SHARES"] - rf).rename("e_CHINAg")
    d = {ch.name: ch}
    for nm, col in (("e_ASIA", "MSCI_ASIA_EX_JAPAN"), ("e_EUROPE", "MSCI_EUROPE"), ("e_USA", "MSCI_USA"), ("e_JAPAN", "MSCI_JAPAN"),
                    ("e_INDIA", "MSCI_INDIA"), ("e_HC", "MSCI_ACWI_HC"), ("e_IT", "MSCI_ACWI_IT"), ("e_VIETNAM", "MSCI_VIETNAM")):
        d[nm] = (F[col] - rf).rename(nm)
    d["e_ARKK"] = (Fext["ARKK_THB"] - rf).rename("e_ARKK")
    d["e_IGF"] = (Fext["IGF_THB"] - rf).rename("e_IGF")
    return pd.DataFrame(d)


def group_factors(gmap_units, F, Fext, X1, mask_tr):
    """factor กลุ่มของ E-X2: e_g = residualize(I_g | X1 · train · lag 0 · เก็บค่าคงที่) · e_CHINA ∈ X1 → CHINA ใช้ A − H (e_AH) ·
    gmap_units: DataFrame(unit, group_factor) เฉพาะหน่วย E · → (E_g DataFrame, per_fund dict unit → Series, pf_name dict unit → ชื่อ factor, coef DataFrame, span DataFrame)"""
    use_ah = "e_CHINA" in X1.columns
    I = group_I(F, Fext, use_ah)
    need = sorted({g for g in gmap_units["group_factor"] if g != "ไม่มี"})
    names = {g: ("e_AH" if (g == "e_CHINA(grp)" and use_ah) else GNAME[g]) for g in need}
    sub = I[[names[g] for g in need]]
    E_g, coef = l3.residualize(sub, X1, mask_tr)
    span = []
    I0 = group_I(F, Fext, False)
    for g in need:
        nm = names[g]
        chk = I[nm]
        span.append(dict(group_factor=g, factor=nm, in_span_of_X1=bool(l2.in_span(X1, chk)),
                         raw_China_All_in_span=bool(l2.in_span(X1, I0["e_CHINAg"])) if g == "e_CHINA(grp)" else np.nan))
    per_fund, pf_name = {}, {}
    for u, g in zip(gmap_units["unit"], gmap_units["group_factor"]):
        if g == "ไม่มี":
            continue
        per_fund[u] = E_g[names[g]]
        pf_name[u] = names[g]
    return E_g, per_fund, pf_name, coef, pd.DataFrame(span)


def epca_build(R, bal, unbal, mask_tr, kmax=10, n_perm=500, seed=SEED, k_override=None):
    """E-PCA ของ E ล้วน (S012 ข้อ 4.1): k* จาก Z ของ balanced (IC_p1/p2 · ER · GR · ED · PA → combine_k) ·
    a1 = pca_fit corr บน balanced · a2 = em_pca บน unbalanced · factor return = factor_returns (ไม่หัก μ) ทุกช่วง"""
    bal, unbal = list(bal), list(unbal)
    Xb = R.loc[mask_tr, bal].to_numpy(float)
    assert np.isfinite(Xb).all(), "balanced ต้องไม่มีค่าว่างใน train"
    T, N = Xb.shape
    Z = (Xb - Xb.mean(0)) / Xb.std(0, ddof=0)
    ks, kstar, eig = fm_.nfactor_report(Z, N, T, kmax, n_perm, seed)
    k = kstar if k_override is None else int(k_override)
    Lam, mu_a, sd_a, eig_a = pc.pca_fit(Xb, k, "corr")
    cols = [f"PC{i + 1}" for i in range(k)]
    a1 = pd.DataFrame(pc.factor_returns(R[bal].to_numpy(float), Lam, sd_a), index=R.index, columns=cols)
    Xc = R.loc[mask_tr, unbal].to_numpy(float)
    Lam_c, mu_c, sd_c, it, conv = pc.em_pca(Xc, k)
    a2 = pd.DataFrame(pc.factor_returns(R[unbal].to_numpy(float), Lam_c, sd_c), index=R.index, columns=cols)
    return dict(a1=a1, a2=a2, ks=ks, kstar=int(kstar), k=int(k), eig=eig, Lam_a=Lam, sd_a=sd_a, mu_a=mu_a, Lam_c=Lam_c, sd_c=sd_c,
                em_iter=int(it), em_conv=bool(conv), bal=bal, unbal=unbal, T=T, N=N)


def hybrid_eo(R, X1, mask_tr, bal, kmax=3):
    """E-H (S012 ข้อ 4.5): E-X1 + residual PC (k_res = IC_p2 · เพดาน 3) · k_res = 0 → E-H = E-X1"""
    rp = hy.residual_pc(R, X1, mask_tr, list(bal), kmax=kmax)
    g = hy.hybrid_factor(R, X1, rp["W"], rp["s"], rp["coef"], list(bal))
    EH = pd.concat([X1, g], axis=1) if rp["k_res"] > 0 else X1.copy()
    return dict(EH=EH, rpc=g, W=rp["W"], s=rp["s"], coef=rp["coef"], k_res=int(rp["k_res"]), eig=rp["eig"], T=int(rp["T"]))


def o_factors(F, Fext, Feo, mask_tr):
    """ชุด O ตายตัว (S012 ข้อ 3.3) → dict(gold, reit, gold_simple, reit_simple, tilt_us, tilt_sg)"""
    mkt = mkt_series(F)
    gold = pd.DataFrame({"GOLD_XS": Feo["GLD_USD"] - F["SHV_USD"], "FX": fx_series(F)})
    reit_raw = (Fext["REET_USD"] - F["SHV_USD"]).rename("REIT_e")
    reit_e, rcoef = l3.residualize(reit_raw, mkt.to_frame(), mask_tr)
    reit = pd.DataFrame({"MKT": mkt, "REIT_e": reit_e["REIT_e"], "FX": fx_series(F), "TERM": F["IEF_USD"] - F["SHV_USD"]})
    rf = F["RF_BOT"]
    return dict(gold=gold, reit=reit, gold_simple=(Feo["GLD_THB"] - rf).to_frame("GOLD_THB"),
                reit_simple=(Fext["REET_THB"] - rf).to_frame("REET_THB"),
                tilt_us=(Feo["VNQ_USD"] - Fext["REET_USD"]).rename("VNQ_m_REET"),
                tilt_sg=(Feo["REITCLRSI_THB"] - Fext["REET_THB"]).rename("CLRSI_m_REET"), reit_coef=rcoef)


def build_M1(F, base_1a, prim_csv, coef_csv, units, splice_units_set=()):
    """M1 = ①a + FX + e_p(i) ของ P4 (S012 ข้อ 3.4 · runs/S009) เฉพาะกองที่ primary (form 1a@4) ∈ P4 · หน่วยต่อรหัสไม่มี primary → ①a + FX
    → (base_df, per_fund dict)"""
    I, blocks = l2.index_set(F)
    M28 = I[blocks["M28"]]
    E_a = l4.e_from_s006(M28, base_1a, coef_csv, "1a")
    pdf = pd.read_csv(prim_csv)
    prim = pdf[pdf["form"] == "1a@4"].set_index("FundCode")["index"]
    cand = [u for u in units if u not in set(splice_units_set)]
    pf = l3.perfund_from_primary(E_a, prim, cand)
    base_df = pd.concat([base_1a, l4.fx_factor(F).to_frame("FX")], axis=1)
    return base_df, pf


# ───────────────────────── ส่วน C ─────────────────────────
import math  # noqa: E402


def _solve_r2(G, g, sst, cols):
    if not cols:
        return 0.0
    Gs = G[np.ix_(cols, cols)]
    gs = g[cols]
    try:
        b = np.linalg.solve(Gs, gs)
    except np.linalg.LinAlgError:
        b = np.linalg.lstsq(Gs, gs, rcond=None)[0]
    return float(gs @ b / sst)


def _shapley_from_v(v, K):
    fact = [math.factorial(i) for i in range(K + 1)]
    phi = np.zeros(K)
    pcnt = [bin(m).count("1") for m in range(1 << K)]
    for k in range(K):
        for m in range(1 << K):
            if (m >> k) & 1:
                continue
            s = pcnt[m]
            phi[k] += fact[s] * fact[K - s - 1] / fact[K] * (v[m | (1 << k)] - v[m])
    return phi


def shapley_r2(y, blocks, rows=None):
    """Shapley R² (S012 ข้อ 6.4): ผู้เล่น = block (ค่าคู่ lag = ผู้เล่นเดียว) · v(S) = R² ของ OLS [1, S] บนแถวที่ y และทุก block ครบ ·
    คำนวณ 2^K ครบ · Σφ = R² เต็ม (v(∅) = 0) → dict(phi, r2, n, v)"""
    y = np.asarray(y, float)
    bl = [np.asarray(b, float).reshape(len(y), -1) for b in blocks]
    K = len(bl)
    X = np.hstack(bl)
    sizes = [b.shape[1] for b in bl]
    starts = np.r_[0, np.cumsum(sizes)]
    ok = np.isfinite(y) & np.isfinite(X).all(axis=1)
    if rows is not None:
        ok &= np.asarray(rows, bool)
    n = int(ok.sum())
    if n <= X.shape[1] + 2:
        return dict(phi=np.full(K, np.nan), r2=np.nan, n=n, v=None)
    yc = y[ok] - y[ok].mean()
    Xc = X[ok] - X[ok].mean(axis=0)
    G, g, sst = Xc.T @ Xc, Xc.T @ yc, float(yc @ yc)
    cols_of = [list(range(starts[k], starts[k + 1])) for k in range(K)]
    v = np.empty(1 << K)
    for m in range(1 << K):
        cols = []
        for k in range(K):
            if (m >> k) & 1:
                cols += cols_of[k]
        v[m] = _solve_r2(G, g, sst, cols)
    return dict(phi=_shapley_from_v(v, K), r2=float(v[-1]), n=n, v=v)


def shapley_oos(y, blocks, rows_tr, rows_te):
    """Shapley ของ R²_oos (ภาคผนวก · ป้าย ข): v(S) = R²_oos ของโมเดล [1, S] ที่ fit บน train ทำนาย test (ติดลบได้) · Σφ = v(เต็ม) − v(∅)"""
    y = np.asarray(y, float)
    bl = [np.asarray(b, float).reshape(len(y), -1) for b in blocks]
    K = len(bl)
    X = np.hstack(bl)
    sizes = [b.shape[1] for b in bl]
    starts = np.r_[0, np.cumsum(sizes)]
    fin = np.isfinite(y) & np.isfinite(X).all(axis=1)
    itr = fin & np.asarray(rows_tr, bool)
    ite = fin & np.asarray(rows_te, bool)
    if itr.sum() <= X.shape[1] + 2 or ite.sum() < 2:
        return dict(phi=np.full(K, np.nan), v_full=np.nan, v_empty=np.nan)
    cols_of = [list(range(starts[k], starts[k + 1])) for k in range(K)]
    v = np.empty(1 << K)
    for m in range(1 << K):
        cols = []
        for k in range(K):
            if (m >> k) & 1:
                cols += cols_of[k]
        A = np.column_stack([np.ones(int(itr.sum())), X[itr][:, cols]]) if cols else np.ones((int(itr.sum()), 1))
        b = np.linalg.lstsq(A, y[itr], rcond=None)[0]
        yh = b[0] + (X[ite][:, cols] @ b[1:] if cols else 0.0)
        v[m] = rg.r2_oos(y[ite], np.broadcast_to(yh, y[ite].shape))
    return dict(phi=_shapley_from_v(v, K), v_full=float(v[-1]), v_empty=float(v[0]))


def sig_count(beta, se, codes, clusters, q=0.10):
    """กองที่ β มีนัย: t = β / SE(HAC ของ b0 + b1) · p สองข้าง (normal) · BH q ภายใน factor ข้ามกลุ่มอ้างอิง →
    dict(n_tested, n_sig, n_groups (กลุ่มกองอิสระ), n_pos, n_neg, frac_p05 · สัดส่วนที่ p < 0.05 โดยไม่แก้)"""
    beta, se = np.asarray(beta, float), np.asarray(se, float)
    codes = np.asarray(list(codes))
    with np.errstate(divide="ignore", invalid="ignore"):
        t = beta / se
    ok = np.isfinite(t)
    if ok.sum() == 0:
        return dict(n_tested=0, n_sig=0, n_groups=0, n_pos=0, n_neg=0, frac_p05=np.nan)
    p = 2 * stats.norm.sf(np.abs(t[ok]))
    rej, _ = ts.bh(p, q)
    sig = codes[ok][rej]
    sgn = beta[ok][rej]
    return dict(n_tested=int(ok.sum()), n_sig=int(rej.sum()), n_groups=int(l2.count_groups(list(sig), clusters)) if len(sig) else 0,
                n_pos=int((sgn > 0).sum()), n_neg=int((sgn < 0).sum()), frac_p05=float(np.mean(p < 0.05)))


def cluster_bootstrap(stat_fn, clusters, n=2000, seed=SEED, q=(2.5, 97.5)):
    """bootstrap แบบสุ่ม**กลุ่มกองอิสระทั้งก้อน**ใส่คืน (S013 m4) · stat_fn(idx) → vector สถิติ (ส่วนต่างจับคู่ใช้ชุดสุ่มเดียวกันในเวกเตอร์เดียว) ·
    clusters: array id กลุ่มต่อตำแหน่งกอง → dict(draws (n × S), lo, hi)"""
    cl = np.asarray(clusters)
    ids = np.unique(cl)
    members = {i: np.where(cl == i)[0] for i in ids}
    rng = np.random.default_rng(seed)
    out = []
    for _ in range(n):
        draw = rng.choice(len(ids), size=len(ids), replace=True)
        idx = np.concatenate([members[ids[d]] for d in draw])
        out.append(np.asarray(stat_fn(idx), float))
    D = np.asarray(out)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        lo, hi = np.nanpercentile(D, q[0], axis=0), np.nanpercentile(D, q[1], axis=0)
    return dict(draws=D, lo=lo, hi=hi)


def top_groups(beta, groups, min_n=5, top=3):
    """S012 ข้อ 6.9: median β ต่อกลุ่มชื่อ (กลุ่มที่มี ≥ min_n หน่วย) → 3 อันดับตาม |median β| พร้อมเครื่องหมาย (list ของ (group, median, n))"""
    d = pd.DataFrame({"b": np.asarray(beta, float), "g": list(groups)}).dropna()
    rows = []
    for g, s in d.groupby("g"):
        if len(s) >= min_n:
            rows.append((g, float(s["b"].median()), int(len(s))))
    rows.sort(key=lambda r: (-abs(r[1]), r[0]))
    return rows[:top]


def vif_set(X, mask):
    """VIF ของชุด factor (train): lag 0 และ design Dimson (max ของคอลัมน์ lag 0 / lag 1 ของ factor เดียวกัน · m1) → DataFrame(factor, vif_lag0, vif_dimson)"""
    Xv = X.to_numpy(float)
    K = Xv.shape[1]
    mask = np.asarray(mask, bool)
    ok0 = mask & np.isfinite(Xv).all(axis=1)
    v0 = ts.vif(Xv[ok0]) if K > 1 else np.ones(1)
    D = rg.lag_stack(Xv)
    ok1 = mask & np.isfinite(D).all(axis=1)
    vD = ts.vif(D[ok1])
    return pd.DataFrame(dict(factor=list(X.columns), vif_lag0=v0, vif_dimson=[max(vD[j], vD[K + j]) for j in range(K)]))


def max_abs_corr(X, j, mask):
    """max |corr| ของคอลัมน์ j กับคอลัมน์อื่นของ X ในแถว mask (ครบ) · K = 1 → NaN"""
    Xv = X.to_numpy(float)
    ok = np.asarray(mask, bool) & np.isfinite(Xv).all(axis=1)
    if X.shape[1] < 2 or ok.sum() < 5:
        return np.nan
    C = np.corrcoef(Xv[ok], rowvar=False)
    return float(np.max(np.abs(np.delete(C[j], j))))


def lead_diag(R, F, lead_cols, funds, mask_tr, L=4):
    """S012 ข้อ 6.11: y ~ [F, F_lag1, lead 1 ของ lead_cols] (HAC) บนแถว train ที่ t+1 ยังอยู่ใน train → สัดส่วนกอง |t_lead| > 2 ต่อ lead factor"""
    lead_cols = [c for c in lead_cols if c in F.columns]
    if not lead_cols:
        return {}
    Fv = F.to_numpy(float)
    D = rg.lag_stack(Fv)
    ld = np.full((len(F), len(lead_cols)), np.nan)
    ld[:-1] = F[lead_cols].to_numpy(float)[1:]
    mtr = np.asarray(mask_tr, bool)
    m = mtr & np.r_[mtr[1:], False]
    Xall = np.hstack([D, ld])
    Rv = R[list(funds)].to_numpy(float)
    tl = np.full((len(funds), len(lead_cols)), np.nan)
    for i in range(len(funds)):
        ok = m & np.isfinite(Rv[:, i]) & np.isfinite(Xall).all(axis=1)
        if ok.sum() < Xall.shape[1] + 20:
            continue
        r = rg.ols_hac(Rv[ok, i], np.column_stack([np.ones(int(ok.sum())), Xall[ok]]), L)
        tl[i] = r["t"][-len(lead_cols):]
    return {c: float(np.nanmean(np.abs(tl[:, k]) > 2)) if np.isfinite(tl[:, k]).any() else np.nan for k, c in enumerate(lead_cols)}


def grs_ports(group, min_group=5):
    """พอร์ต GRS (S012 ข้อ 7): กลุ่มชื่อที่มี ≥ min_group หน่วย → พอร์ตของตัวเอง · ที่เหลือรวม OTHER · group: Series unit → ชื่อกลุ่ม"""
    cnt = group.value_counts()
    big = set(cnt.index[cnt >= min_group])
    return group.map(lambda g: g if g in big else "OTHER")


def port_returns(R, ports):
    cols = sorted(ports.unique())
    X = np.full((len(R.index), len(cols)), np.nan)
    C = np.zeros((len(R.index), len(cols)), int)
    for j, p in enumerate(cols):
        mem = list(ports.index[ports == p])
        V = R[mem].to_numpy(float)
        C[:, j] = np.isfinite(V).sum(axis=1)
        with np.errstate(invalid="ignore"):
            X[:, j] = np.where(C[:, j] > 0, np.nansum(V, axis=1) / np.maximum(C[:, j], 1), np.nan)
    return cols, X, C


def run_grs(cols, X, C, Xdes, mask, min_members=3, min_dof=10):
    """GRS บนพอร์ต EW · ตัดสัปดาห์ที่พอร์ตใดมีสมาชิก < min_members (แบบ S003) → dict"""
    bad = (C < min_members).any(axis=1) & mask
    fin_f = np.isfinite(Xdes).all(axis=1)
    use = mask & ~bad & fin_f & np.isfinite(X).all(axis=1)
    d = dict(N_ports=len(cols), T_used=int(use.sum()), n_drop_ports=int((mask & bad).sum()), n_drop_factor_nan=int((mask & ~bad & ~fin_f).sum()))
    if use.sum() - len(cols) - Xdes.shape[1] <= min_dof:
        d.update(F=np.nan, p=np.nan, L=Xdes.shape[1], dof2=int(use.sum() - len(cols) - Xdes.shape[1]), mean_abs_alpha_pct=np.nan, note="N/A (T ไม่พอ)")
        return d
    g = ts.grs(X[use], Xdes[use])
    d.update(F=g["F"], p=g["p"], L=g["L"], dof2=g["dof2"], mean_abs_alpha_pct=float(np.mean(np.abs(g["alpha"])) * 5200), note="")
    return d


# ───────────── โมเดลและการ fit ─────────────
class Model:
    """แถวแข่ง: base = factor ร่วม (T × K) · per_fund = dict หน่วย → Series (factor กลุ่ม 1 ตัว) · pf_name = ชื่อ factor กลุ่มต่อหน่วย"""

    def __init__(self, name, base, per_fund=None, pf_name=None, kind="x", eig=None):
        self.name = name
        self.base = base
        self.per_fund = per_fund or {}
        self.pf_name = pf_name or {}
        self.kind = kind
        self.eig = eig
        self.K = base.shape[1]

    def players(self, unit):
        out = [(c, self.base[c].to_numpy(float)) for c in self.base.columns]
        if unit in self.per_fund:
            out.append((self.pf_name[unit], np.asarray(self.per_fund[unit], float)))
        return out

    def group_factor_names(self):
        return sorted(set(self.pf_name.values()))

    def members(self, name):
        return [u for u, n in self.pf_name.items() if n == name]

    def series(self, name):
        if name in self.base.columns:
            return self.base[name]
        u = self.members(name)[0]
        return self.per_fund[u].rename(name)


def fit_model(R, model, mask, mask_te, funds, min_obs=52, L=4):
    """→ (fit, r2oos) · มี per_fund → l3.fit_perfund"""
    funds = list(funds)
    if model.per_fund:
        fit, ro, _ = l3.fit_perfund(R, model.base, model.per_fund, mask, mask_te, funds, min_obs, L)
        return fit, ro
    prov = rg.CommonFactors(model.base)
    fit = rg.fit_funds(R, prov, mask, min_obs, L, funds=funds)
    ro = rg.oos_r2_funds(R, prov, fit, mask_te) if mask_te is not None else np.full(len(funds), np.nan)
    return fit, ro


def fit_df(R, df, mask, funds, mask_te=None, min_obs=52, L=4):
    prov = rg.CommonFactors(df)
    fit = rg.fit_funds(R, prov, mask, min_obs, L, funds=list(funds))
    ro = rg.oos_r2_funds(R, prov, fit, mask_te) if mask_te is not None else np.full(len(fit.codes), np.nan)
    return fit, ro


def factor_cols(model, fit):
    """ชื่อ factor ของแถว → (ดัชนีคอลัมน์ใน fit.beta, สมาชิก bool ต่อกองใน fit.codes)"""
    codes = list(fit.codes)
    out = {}
    for j, c in enumerate(model.base.columns):
        out[c] = (j, np.ones(len(codes), bool))
    for g in model.group_factor_names():
        mem = set(model.members(g))
        out[g] = (model.K, np.array([c in mem for c in codes]))
    return out


def model_stability(R, model, stab, masks, fit_min_h1=104, fit_min_h2=104):
    """ความเสถียรต่อ factor บนชุด `stab` (S012 ข้อ 6.8): r ดิบ β ระหว่าง H1 / H2 ข้ามกอง (factor กลุ่ม: สมาชิก STAB · < 10 → N/A) +
    rolling 104 สัปดาห์ step 4: corr หน้าต่างแรก vs หน้าต่างสุดท้าย (ตัวหลัก) + median เทียบช่วงเต็ม → DataFrame(factor, n, r_h1h2, roll_first_last, roll_median_vs_full)"""
    stab = [u for u in stab]
    f1, _ = fit_model(R, model, masks["H1"] & masks["pos1"], None, stab, fit_min_h1)
    f2, _ = fit_model(R, model, masks["H2"], None, stab, fit_min_h2)
    bw, full, _ = l3.rolling_perfund(R, model.base, model.per_fund, stab, masks["full"] & masks["pos1"])
    fc = factor_cols(model, f1)
    rows = []
    for name, (j, mem) in fc.items():
        n = int(mem.sum())
        if name not in model.base.columns and n < 10:
            rows.append(dict(factor=name, n=n, r_h1h2=np.nan, roll_first_last=np.nan, roll_median_vs_full=np.nan, note="N/A (สมาชิก STAB < 10)"))
            continue
        b1, b2 = f1.beta[mem, j], f2.beta[mem, j]
        r = sc._corr(b1, b2)
        wins = bw[:, mem, j]
        fl = sc._corr(wins[0], wins[-1])
        cs = np.array([sc._corr(wins[w], full[mem, j]) for w in range(wins.shape[0])])
        rows.append(dict(factor=name, n=n, r_h1h2=r, roll_first_last=fl, roll_median_vs_full=float(_nanmed(cs)) if np.isfinite(cs).any() else np.nan, note=""))
    return pd.DataFrame(rows)


def shapley_table(R, model, funds, masks, with_oos=True):
    """Shapley R² (train) ต่อกอง × factor ของแถว (ผู้เล่นต่อกอง = factor ของกองนั้น) → (long DataFrame(unit, factor, phi, r2_full, share, phi_oos), R² เต็ม Series)"""
    rows = []
    mtr = masks["train"] & masks["pos1"]
    for u in funds:
        pl = model.players(u)
        y = R[u].to_numpy(float)
        sh = shapley_r2(y, [b for _, b in pl], rows=mtr)
        if with_oos:
            so = shapley_oos(y, [b for _, b in pl], mtr, masks["test"])
        for k, (nm, _) in enumerate(pl):
            ph = sh["phi"][k]
            rows.append(dict(unit=u, factor=nm, phi=ph, r2_full=sh["r2"], share=(ph / sh["r2"]) if (np.isfinite(sh["r2"]) and sh["r2"] > 1e-12) else np.nan,
                             phi_oos=so["phi"][k] if with_oos else np.nan, v_full_oos=so["v_full"] if with_oos else np.nan,
                             v_empty_oos=so["v_empty"] if with_oos else np.nan))
    return pd.DataFrame(rows)


def beta_placebo(R, model, name, funds, mask_tr, shifts=(26, 52), min_obs=52):
    """S012 ข้อ 6.5: เลื่อน factor นั้นแบบวน 26 / 52 สัปดาห์ในช่วง train (ตัวอื่นคงเดิม) → สัดส่วนกองที่ p < 0.05 (β = b0 + b1 · t HAC) ต่อ shift"""
    out = {}
    for s in shifts:
        if name in model.base.columns:
            Fs = model.base.copy()
            Fs[name] = l2.circular_shift(Fs[[name]], mask_tr, s)[name]
            fit, _ = fit_df(R, Fs, mask_tr, funds, None, min_obs)
            j = list(Fs.columns).index(name)
            b, se = fit.beta[:, j], fit.se_beta[:, j]
        else:
            mem = [u for u in funds if u in model.per_fund and model.pf_name[u] == name]
            ser = model.per_fund[mem[0]]
            sh = l2.circular_shift(ser.to_frame("x"), mask_tr, s)["x"]
            pf = {u: sh for u in mem}
            fit, _ , _ = l3.fit_perfund(R, model.base, pf, mask_tr, None, mem, min_obs)
            b, se = fit.beta[:, model.K], fit.se_beta[:, model.K]
        with np.errstate(divide="ignore", invalid="ignore"):
            t = b / se
        ok = np.isfinite(t)
        out[int(s)] = float(np.mean(2 * stats.norm.sf(np.abs(t[ok])) < 0.05)) if ok.any() else np.nan
    return out


def _med(a):
    a = np.asarray(a, float)
    a = a[np.isfinite(a)]
    return float(np.median(a)) if len(a) else np.nan


def interpret_factor(series, ref, mtr, mte, min_obs=100):
    """ชื่อของ factor ที่ไม่มีนิยามตรง (PC / RPC): 3 อันดับ |corr| train กับชุดอ้างอิง · ≥ 0.7 '≈' (ต้อง corr test ≥ 0.6 ด้วย) · 0.5–0.7 'คล้าย' · < 0.5 'ไม่มีชื่อ'
    → dict(label, ref1..3, corr1..3, test_corr1)"""
    s = series.to_frame(series.name or "f")
    it = sc.interpret(s.loc[mtr], ref.loc[mtr], min_obs=min_obs)
    out = dict(name_label="", name_ref1="", name_corr1=np.nan, name_ref2="", name_corr2=np.nan, name_ref3="", name_corr3=np.nan, name_test_corr1=np.nan)
    if len(it) == 0:
        out["name_label"] = "ไม่มีชื่อ"
        return out
    for _, r in it.iterrows():
        out[f"name_ref{int(r['rank'])}"] = r["ref"]
        out[f"name_corr{int(r['rank'])}"] = float(r["corr"])
        if int(r["rank"]) == 1:
            out["name_label"] = r["label"]
    top = out["name_ref1"]
    d = pd.concat([s.loc[mte].iloc[:, 0], ref.loc[mte, top]], axis=1).dropna()
    tc = float(d.iloc[:, 0].corr(d.iloc[:, 1])) if len(d) > 5 else np.nan
    out["name_test_corr1"] = tc
    if out["name_label"].startswith("≈") and not (np.isfinite(tc) and abs(tc) >= 0.6):
        out["name_label"] = out["name_label"] + " (ไม่ยืนนอกช่วง)"
    return out


def factor_report(R, model, fit, ro, funds, ctx, interpret_names=(), with_oos_shap=True, detail_common=True, shap=None):
    """รายงานราย factor (S012 ข้อ 6.1–6.10 · 1 แถว = แถวแข่ง × factor) · funds = กองที่ใช้เป็นกลุ่มอ้างอิง (EVAL) · fit/ro = fit ของแถวบน fit.codes ⊇ funds
    ctx: masks · stab · clusters (dict หน่วย → group_id) · group (Series หน่วย → กลุ่มชื่อ) · ref (DataFrame อ้างอิงชื่อ) · a1 (DataFrame PC ของ ①a) ·
         axis (ชื่อ) · axis_series (Series)"""
    masks = ctx["masks"]
    mtr, mte = masks["train"], masks["test"]
    codes = list(fit.codes)
    pos = {c: i for i, c in enumerate(codes)}
    evs = set(funds)
    ev = [u for u in codes if u in evs and fit.ok[pos[u]]]
    fc = factor_cols(model, fit)
    if shap is None:
        shap = shapley_table(R, model, ev, masks, with_oos=with_oos_shap)
    stab = model_stability(R, model, ctx["stab"], masks).set_index("factor")
    vifc = vif_set(model.base, mtr & masks["pos1"]).set_index("factor") if model.K >= 1 else None
    Dfull = rg.lag_stack(model.base.to_numpy(float))
    rows_tr = mtr & np.isfinite(Dfull).all(axis=1)
    rows_te = mte & np.isfinite(Dfull).all(axis=1)
    ref_all, a1 = ctx["ref"], ctx["a1"]
    axis, axser = ctx["axis"], ctx["axis_series"]
    rows = []
    for name, (j, mem) in fc.items():
        is_g = name not in model.base.columns
        refu = [u for u, m in zip(codes, mem) if m and u in evs and fit.ok[pos[u]]]
        ri = np.array([pos[u] for u in refu], int)
        row = dict(row=model.name, factor=name, kind="group" if is_g else "common", n_ref=len(refu))
        if len(refu) == 0:
            rows.append(row)
            continue
        ser = model.series(name)
        # 6.1 Shapley
        s = shap[(shap["factor"] == name) & shap["unit"].isin(refu)]
        row.update(shap_share_med=_med(s["share"]), shap_share_mean=float(np.nanmean(s["share"])) if s["share"].notna().any() else np.nan,
                   shap_phi_med=_med(s["phi"]), shap_oos_phi_med=_med(s["phi_oos"]))
        if model.eig is not None and not is_g and name.startswith("PC"):
            eig, N = model.eig
            row["lambda_share"] = float(eig[int(name[2:]) - 1] / N)
        full_detail = detail_common or is_g
        if full_detail:
            # 6.2 ใส่เดี่ยว
            f1, r1 = fit_df(R, ser.to_frame(name), mtr, refu, mte)
            row.update(single_adjr2_med=_med(f1.adj_r2), single_r2oos_med=_med(r1))
            if name != axis:
                f2, r2_ = fit_df(R, pd.concat([axser.rename(axis), ser.rename(name)], axis=1), mtr, refu, mte)
                f0, r0 = fit_df(R, axser.rename(axis).to_frame(), mtr, refu, mte)
                row.update(axis=axis, pair_adjr2_med=_med(f2.adj_r2), pair_r2oos_med=_med(r2_), axis_adjr2_med=_med(f0.adj_r2), axis_r2oos_med=_med(r0),
                           d_pair_axis_adjr2_med=_med(f2.adj_r2 - f0.adj_r2), d_pair_axis_r2oos_med=_med(r2_ - r0))
            else:
                row["axis"] = axis + " (เป็นแกน)"
            # 6.3 drop-one
            if is_g:
                pf = {u: ser for u in refu}
                fa, ra, _ = l3.fit_perfund(R, model.base, pf, rows_tr, rows_te, refu, 52)
                fb, rb = fit_df(R, model.base, rows_tr, refu, rows_te)
                ok = fa.ok & fb.ok
                row.update(drop_d_adjr2_med=_med((fa.adj_r2 - fb.adj_r2)[ok]), drop_d_r2oos_med=_med((np.asarray(ra) - np.asarray(rb))[ok]),
                           drop_d_bic_med=_med((fa.bic - fb.bic)[ok]), drop_n=int(ok.sum()))
            elif model.K > 1:
                ff, rf_ = fit_df(R, model.base, rows_tr, refu, rows_te)
                fd, rd = fit_df(R, model.base.drop(columns=[name]), rows_tr, refu, rows_te)
                ok = ff.ok & fd.ok
                row.update(drop_d_adjr2_med=_med((ff.adj_r2 - fd.adj_r2)[ok]), drop_d_r2oos_med=_med((np.asarray(rf_) - np.asarray(rd))[ok]),
                           drop_d_bic_med=_med((ff.bic - fd.bic)[ok]), drop_n=int(ok.sum()))
        # 6.5 β มีนัย
        sg = sig_count(fit.beta[ri, j], fit.se_beta[ri, j], refu, ctx["clusters"])
        row.update(n_beta_tested=sg["n_tested"], n_beta_sig_bh=sg["n_sig"], n_beta_sig_groups=sg["n_groups"], n_beta_pos=sg["n_pos"],
                   n_beta_neg=sg["n_neg"], frac_p05=sg["frac_p05"], frac_abs_t_b1_gt2=float(np.nanmean(np.abs(fit.t_b1[ri, j]) > 2)),
                   beta_med=_med(fit.beta[ri, j]))
        if full_detail:
            pl = beta_placebo(R, model, name, refu, mtr)
            row.update(placebo26=pl[26], placebo52=pl[52], placebo_flag="นับตรงไม่ได้ (> 8%)" if max(pl.values()) > 0.08 else "")
        # 6.6 ชื่อ
        if name in interpret_names:
            row.update(interpret_factor(ser, ref_all, mtr, mte))
        else:
            row["name_label"] = "นิยามตรง"
        # 6.7 VIF · ความตั้งฉาก
        if is_g:
            X = pd.concat([model.base, ser.rename(name)], axis=1)
            v = vif_set(X, mtr & masks["pos1"]).set_index("factor").loc[name]
            jx = X.shape[1] - 1
            row.update(vif_lag0=float(v["vif_lag0"]), vif_dimson=float(v["vif_dimson"]), vif_fund_max=float(v["vif_dimson"]), vif_fund_med=float(v["vif_dimson"]),
                       maxcorr_other_train=max_abs_corr(X, jx, mtr), maxcorr_other_test=max_abs_corr(X, jx, mte))
        else:
            row.update(vif_lag0=float(vifc.loc[name, "vif_lag0"]), vif_dimson=float(vifc.loc[name, "vif_dimson"]),
                       maxcorr_other_train=max_abs_corr(model.base, list(model.base.columns).index(name), mtr),
                       maxcorr_other_test=max_abs_corr(model.base, list(model.base.columns).index(name), mte))
        # 6.8 ความเสถียร
        if name in stab.index:
            st = stab.loc[name]
            row.update(stab_n=int(st["n"]), r_h1h2=st["r_h1h2"], roll_first_last=st["roll_first_last"], roll_median_vs_full=st["roll_median_vs_full"],
                       stab_note=st["note"])
        # 6.9 กลุ่มกองที่ loading สูงสุด
        tg = top_groups(fit.beta[ri, j], [ctx["group"][u] for u in refu], min_n=ctx.get("min_n_group", 5))
        row["top_groups"] = " · ".join(f"{g} {m:+.2f} (n={n})" for g, m, n in tg)
        # 6.10 corr กับ PC ของ ①a
        trr = mtr & np.isfinite(ser.to_numpy(float))
        cc = {c: float(np.corrcoef(ser.to_numpy(float)[trr], a1[c].to_numpy(float)[trr])[0, 1]) for c in a1.columns}
        best = max(cc, key=lambda c: abs(cc[c]))
        row.update(max_corr_1a_pc=cc[best], max_corr_1a_which=best)
        rows.append(row)
    return pd.DataFrame(rows)


# ───────────────────────── ส่วน D: ข้อมูลจำลอง (test · smoke ด้วย --sim) ─────────────────────────
def sim_factors(like, seed=SEED, common=0.6):
    """DataFrame จำลองที่มี index / คอลัมน์เหมือน `like` (ไม่คัดลอกค่า) · คอลัมน์ผลตอบแทนมี factor ตลาดร่วม"""
    rng = np.random.default_rng(seed)
    T = len(like)
    m = rng.normal(size=T)
    out = {}
    for c in like.columns:
        if c in ("RF_BOT", "KF_RF"):
            out[c] = 0.0004 + 0.00002 * rng.normal(size=T)
        elif c.endswith("_lvl") or "_late_" in c or c.endswith("_est_ret"):
            out[c] = np.full(T, 0.03)
        else:
            w = 1.0 if (c.startswith("MSCI_") or c.endswith(("_USD", "_THB", "_LOC")) or c in ("Gold", "Gold_THB", "ACWI_ETF_USD")) else 0.0
            out[c] = 0.012 * (common * w * m + np.sqrt(1 - (common * w) ** 2) * rng.normal(size=T))
    return pd.DataFrame(out, index=like.index)


_SIM_IDX = ["MSCI_CHINA_ALL_SHARES", "MSCI_USA", "MSCI_EUROPE", "MSCI_JAPAN", "MSCI_ASIA_EX_JAPAN", "MSCI_INDIA", "MSCI_ACWI_HC", "MSCI_ACWI_IT"]


def sim_returns(units, pol, F, Feo, Fext, seed=SEED, n_weeks=None):
    """ผลตอบแทนส่วนเกินจำลองระดับหน่วย (เวลา × หน่วย) · E = β·MKT + γ·ดัชนีประเทศ/ธีม + noise · ทอง = GOLD_XS + FX · REIT = MKT + REET + FX ·
    n_weeks: Series หน่วย → จำนวนแถวที่มีค่า (ท้ายช่วง) → NaN นำหน้า"""
    rng = np.random.default_rng(seed + 1)
    rf = F["RF_BOT"]
    mkt = (F["MSCI_ACWI"] - rf).to_numpy()
    fx = (F["SHV_THB"] - rf).to_numpy()
    gold = (Feo["GLD_USD"] - F["SHV_USD"]).to_numpy()
    reit = (Fext["REET_USD"] - F["SHV_USD"]).to_numpy()
    T = len(F)
    out = {}
    for i, u in enumerate(units):
        e = 0.008 * rng.normal(size=T)
        if pol[u] == "O":
            if i % 2 == 0:
                y = 0.95 * gold + 0.7 * fx + e
            else:
                y = 0.6 * mkt + 0.5 * reit + 0.3 * fx + e
        else:
            ix = (F[_SIM_IDX[i % len(_SIM_IDX)]] - rf).to_numpy()
            y = (0.5 + 0.4 * ((i % 5) / 4)) * mkt + 0.4 * ix + 0.1 * (i % 3) * fx + e
        s = pd.Series(y, index=F.index)
        if n_weeks is not None and u in n_weeks.index:
            k = int(n_weeks[u])
            s.iloc[: max(0, T - k)] = np.nan
        out[u] = s
    return pd.DataFrame(out)
