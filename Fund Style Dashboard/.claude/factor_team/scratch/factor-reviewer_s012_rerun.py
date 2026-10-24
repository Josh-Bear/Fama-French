"""factor-designer · S012 · ตรวจโครงข้อมูล + สร้างตารางจับคู่กอง → factor กลุ่ม (จากชื่อกองเท่านั้น)

ใช้เฉพาะ: ชื่อกอง / รหัส / policy / Fund Class / ธง (FundProfile) · aum_fam.parquet (in_U) · universe.csv (n_weeks, div_flag) ·
dup_pairs.csv (คู่ซ้ำของ L0) · จำนวนแถวที่ **ไม่ว่าง** ของผลตอบแทนต่อช่วง (notna เท่านั้น — ไม่อ่านค่า) ·
runs/S005/primary_index.csv ใช้**นับ**ความครอบคลุมของตัวเทียบ M1 เท่านั้น (ไม่ใช้จับคู่กลุ่ม)
ไม่ดูค่าผลตอบแทน · ไม่ fit model
เขียน: specs/S012_group_map.csv + scratch/factor-designer_s012_structure.json
"""
import json
import re
import hashlib
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]          # .claude/factor_team
APP = ROOT.parents[1]                                # Fund Style Dashboard
D = ROOT / "data"


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


# ───────────── ข้อมูลโครง ─────────────
A = pd.read_parquet(D / "aum_fam.parquet")
U = A[A.in_U].copy()
uni = pd.read_csv(D / "universe.csv").set_index("FundCode")
dup = pd.read_csv(D / "dup_pairs.csv")
fp = pd.read_csv(APP / "base_data" / "FundProfile.csv", encoding="utf-8-sig", low_memory=False)
fp = fp.drop_duplicates("Fund Code").set_index("Fund Code")

P = pd.read_parquet(D / "panel_weekly.parquet", columns=["FundCode", "date"] + ["ret"])
P = P[P.FundCode.isin(U.FundCode)]
NN = P.assign(v=P["ret"].notna()).pivot(index="date", columns="FundCode", values="v").fillna(False).astype(bool)
del P  # ไม่เก็บค่าผลตอบแทน
idx = NN.index


def wmask(s, e):
    return (idx >= pd.Timestamp(s)) & (idx <= pd.Timestamp(e))


m_tr = wmask("2021-01-08", "2023-12-29").copy()
m_tr[0] = False  # Dimson: แถวแรกไม่มี lag
m_te = wmask("2024-01-05", "2025-12-26")
m_h1 = wmask("2021-01-08", "2023-06-30").copy(); m_h1[0] = False
m_h2 = wmask("2023-07-07", "2025-12-26")
m_tr_raw = wmask("2021-01-08", "2023-12-29")
cnt = pd.DataFrame({
    "n_tr": NN.loc[m_tr].sum(), "n_te": NN.loc[m_te].sum(),
    "n_h1": NN.loc[m_h1].sum(), "n_h2": NN.loc[m_h2].sum(),
    "n_tr_raw": NN.loc[m_tr_raw].sum(),
    "n_post": NN.loc[idx > pd.Timestamp("2025-12-26")].sum(),
})
cnt["fit"] = cnt.n_tr >= 104
cnt["eval"] = (cnt.n_tr >= 104) & (cnt.n_te >= 52)
cnt["stab"] = cnt["eval"] & (cnt.n_h1 >= 104) & (cnt.n_h2 >= 104)
cnt["balanced"] = cnt.n_tr_raw == int(m_tr_raw.sum())
cnt["unbal52"] = cnt.n_tr_raw >= 52

U = U.set_index("FundCode")
U = U.join(cnt, how="left")
U["name_en"] = U["name_en"].fillna("")
U["name_th"] = [fp["Fund Name TH"].get(c, "") for c in U.index]
U["fund_class"] = [fp["Fund Class"].get(c, np.nan) for c in U.index]
U["fif"] = [fp["FIF Flag"].get(c, np.nan) for c in U.index]
U["prev_code"] = [fp["Previous Fund Code"].get(c, np.nan) for c in U.index]
U["div_flag"] = [uni["div_flag"].get(c, np.nan) for c in U.index]
U["reg_date"] = [fp["Registration_date"].get(c, np.nan) for c in U.index]
U["fx_risk_flag"] = [fp["FX Risk Flag"].get(c, np.nan) for c in U.index]

# ───────────── กฎต่อรหัส (splice · ล็อกใน spec ข้อ 2.3) ─────────────
# คู่ใน U ที่ (ก) Registration_date เท่ากัน (ข) policy เดียวกัน (ค) ชื่อ EN เท่ากันหลังตัดคำแบรนด์ TMB / EASTSPRING
# (ง) ช่วงที่มีผลตอบแทนซ้อนกัน ≤ 1 สัปดาห์ → กองเดียวกันเปลี่ยนรหัส → ต่ออนุกรม (รหัสเก่าก่อน · สัปดาห์ซ้อนใช้รหัสเก่า)
def _nm(x):
    x = re.sub(r"\b(TMB|EASTSPRING|FUND)\b", " ", str(x).upper())
    return re.sub(r"\s+", " ", x).strip()


SPLICE = {}
for reg, grp_ in U.groupby("reg_date"):
    if len(grp_) < 2:
        continue
    codes = list(grp_.index)
    for i in range(len(codes)):
        for j in range(i + 1, len(codes)):
            a_, b_ = codes[i], codes[j]
            if U.policy[a_] != U.policy[b_] or _nm(U.name_en[a_]) != _nm(U.name_en[b_]):
                continue
            if isinstance(U.fund_class[a_], str) and U.fund_class[a_] == U.fund_class[b_] and (NN[a_] & NN[b_]).sum() > 1:
                continue   # class คู่ขนานของกองเดียวกัน (Fund Class ซ้ำ) ไม่ใช่การเปลี่ยนรหัส
            ov = int((NN[a_] & NN[b_]).sum())
            if ov > 1:
                continue
            old, new = sorted([a_, b_], key=lambda c: NN.index[NN[c]].min())
            sid = (new.split("-A")[0] if new.endswith("-A") else new.split("-G")[0]) + "*"
            if old == "I-GOLD":
                sid = "I-GOLD*"
            SPLICE[old] = dict(sid=sid, old=old, new=new, overlap=ov)
            SPLICE[new] = dict(sid=sid, old=old, new=new, overlap=ov)
U["splice_id"] = [SPLICE[c]["sid"] if c in SPLICE else "" for c in U.index]
# ความครอบคลุมหลังต่อ (รหัสเก่า ∪ รหัสใหม่)
SPL_CNT = {}
for c, v in SPLICE.items():
    if v["sid"] in SPL_CNT:
        continue
    s_ = NN[v["old"]] | NN[v["new"]]
    SPL_CNT[v["sid"]] = dict(old=v["old"], new=v["new"], overlap=v["overlap"], n_tr=int(s_[m_tr].sum()), n_te=int(s_[m_te].sum()),
                             n_h1=int(s_[m_h1].sum()), n_h2=int(s_[m_h2].sum()))
for c, v in SPLICE.items():
    sc = SPL_CNT[v["sid"]]
    U.loc[c, "eval_spliced"] = (sc["n_tr"] >= 104) and (sc["n_te"] >= 52)
    U.loc[c, "fit_spliced"] = sc["n_tr"] >= 104

# ───────────── I-GOLD / IGOLD-G (โครงการต่อ) ─────────────
ig = {}
for c in ("I-GOLD", "IGOLD-G"):
    s = NN[c]
    d = s.index[s]
    ig[c] = dict(first=str(d.min().date()), last=str(d.max().date()), n=int(s.sum()))
ig["overlap_weeks"] = int((NN["I-GOLD"] & NN["IGOLD-G"]).sum())
gap = NN.index[(NN.index > pd.Timestamp(ig["I-GOLD"]["last"])) & (NN.index < pd.Timestamp(ig["IGOLD-G"]["first"]))]
ig["gap_weeks_between"] = int(len(gap))
spl = NN["I-GOLD"] | NN["IGOLD-G"]
ig["spliced"] = dict(n_tr=int(spl[m_tr].sum()), n_te=int(spl[m_te].sum()), n_h1=int(spl[m_h1].sum()), n_h2=int(spl[m_h2].sum()))

# ───────────── กฎจับคู่ชื่อกอง (ล็อกใน spec S012 ข้อ 4) ─────────────
def norm(s):
    s = " " + s.upper() + " "
    s = re.sub(r"EX[\s\-]*JAPAN", " ", s)      # 'Asia Pacific ex Japan' ไม่นับเป็น Japan
    s = re.sub(r"EX[\s\-]*US\b", " ", s)
    s = re.sub(r"[^A-Z0-9&\.]+", " ", s)
    return " " + re.sub(r"\s+", " ", s).strip() + " "


# (ลำดับ, key, regex คำตาม F-R006 (stem · ขึ้นต้นคำ), regex คำพ้องของประเทศเดียวกัน, factor_name, data_column, ที่มา, ให้ factor ได้?)
# BRIEF 115(1): ใช้เฉพาะคำตาม F-R006 §2 ⑤ / E2 · ตัดคำที่ designer เพิ่มเอง · ป้ายของ designer (TH/METAL/EM/FIN/CONSUMER/STYLE/GLOBAL) ไม่ให้ factor
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
SUB = {"SEMI": (r"\bSEMI", "TECH", "SOXX_THB"), "BIOTECH": (r"\bBIOTECH|\bGENOM", "HEALTH", "IBB_THB"),
       "CHINA_A": (r"\bA SHARES?\b|\bASHARES\b", "CHINA", "MSCI_CHINA_A_SHARES"),
       "CHINA_TECH": (r"TECH|\bINTERNET", "CHINA", "KWEB_THB")}


def match(name, syn=True):
    n = norm(name)
    for lvl, key, rx, rxs, fac, col, src, allowed in RULES:
        m = re.search(rx, n)
        if m:
            return lvl, key, m.group(0).strip(), False
        if syn and rxs:
            m = re.search(rxs, n)
            if m:
                return lvl, key, m.group(0).strip(), True
    return 9, "NONE", "", False


E = U[U.policy == "E"].copy()
O = U[U.policy == "O"].copy()
for c in O.index:
    if U.splice_id[c]:
        O.loc[c, "eval"] = bool(U.loc[c, "eval_spliced"]); O.loc[c, "fit"] = bool(U.loc[c, "fit_spliced"])
rows = [match(n) for n in E.name_en]
E["lvl"] = [r[0] for r in rows]
E["name_group"] = [r[1] for r in rows]
E["matched_word"] = [r[2] for r in rows]
E["by_synonym"] = [r[3] for r in rows]
rows_ns = [match(n, syn=False) for n in E.name_en]
E["name_group_nosyn"] = [r[1] for r in rows_ns]

# Fund Class ซ้ำ (กองเดียวกันหลายรหัส) และหน่วยที่ต่อรหัส → นับ 1
fc_counts = U.groupby("fund_class").size()
U["fc_dup"] = U.fund_class.map(lambda x: fc_counts.get(x, 0) > 1 if isinstance(x, str) else False)
E["fc_key"] = [(U.splice_id[code] if U.splice_id[code] else (fc if isinstance(fc, str) and fc_counts.get(fc, 0) > 1 else code)) for code, fc in zip(E.index, E.fund_class)]
for c in E.index:
    if U.splice_id[c]:
        E.loc[c, "eval"] = bool(U.loc[c, "eval_spliced"]); E.loc[c, "fit"] = bool(U.loc[c, "fit_spliced"])


def gcount(df, key, col="name_group"):
    sub = df[df[col] == key]
    return dict(n_U=int(sub.fc_key.nunique()), n_fit=int(sub[sub.fit].fc_key.nunique()),
                n_eval=int(sub[sub["eval"]].fc_key.nunique()), n_rows=int(len(sub)))


RMAP = {r[1]: r for r in RULES}
ALLOWED = {r[1] for r in RULES if r[7]}
ASIAN = ("CHINA", "INDIA", "VIETNAM", "ASEAN", "KOREA", "TAIWAN")   # ลูกของ ASIA ตามลำดับชั้น L3 (HIER)
BASIS = "n_U"   # BRIEF 115(2): นับจากกองใน U_E ทั้งหมด (หน่วยหลังต่อรหัส · Fund Class ซ้ำนับ 1)


def build(col):
    g0 = {k: gcount(E, k, col) for k in E[col].unique()}
    grp = E[col].copy()
    for k in ASIAN:
        if k in g0 and g0[k][BASIS] < 5:
            grp[E[col] == k] = "ASIA"          # ประเทศเอเชียที่ < 5 → ภูมิภาคแม่
    gk = E.assign(_g=grp)
    cnts = {k: gcount(gk, k, "_g") for k in grp.unique()}
    fac, colm, ok = [], [], []
    for g in grp:
        if g not in ALLOWED or cnts[g][BASIS] < 5:
            fac.append("ไม่มี"); colm.append(""); ok.append(False)
        else:
            r = RMAP[g]; fac.append(r[4]); colm.append(r[5]); ok.append(True)
    return g0, grp, cnts, fac, colm, ok


groups0, E["group"], groups, E["group_factor"], E["factor_column"], E["group_ok"] = build("name_group")
_, _, groups_ns, fac_ns, _, _ = build("name_group_nosyn")
E["alt_factor_no_synonym"] = fac_ns
E["group_n_U"] = [groups[g]["n_U"] for g in E.group]
E["group_n_fit"] = [groups[g]["n_fit"] for g in E.group]
E["group_n_eval"] = [groups[g]["n_eval"] for g in E.group]

# กลุ่มย่อยที่ไม่ถึง 5 (บันทึกเพื่อดู)
subcnt = {}
for sk, (rx, parent, col) in SUB.items():
    mm = [bool(re.search(rx, norm(n))) and g == parent for n, g in zip(E.name_en, E.group)]
    subcnt[sk] = dict(parent=parent, n_U=int(E[mm].fc_key.nunique()), codes=sorted(E.index[mm]), column=col)


def hedge_label(name):
    n = norm(name)
    if re.search(r"UNHEDGED|\bUH\b", n):
        return "ไม่ hedge (ชื่อ)"
    if re.search(r"HEDGED|HEDGE\b|\bH\b$", n):
        return "hedge (ชื่อ)"
    return ""


def note_e(code, r):
    notes = []
    if not r.fit:
        notes.append(f"ไม่ครบ train (แถว train {int(r.n_tr)} < 104) → ไม่ถูก fit / ไม่อยู่ใน EVAL")
    elif not r["eval"]:
        notes.append(f"ไม่ครบ test (แถว test {int(r.n_te)} < 52) → ไม่อยู่ใน EVAL")
    if r.fx_risk_flag == "N":
        notes.append("FX Risk Flag = N (FundProfile)")
    if U.splice_id[code]:
        sc = SPL_CNT[U.splice_id[code]]
        notes.append(f"ต่อรหัส {sc['old']} → {sc['new']} เป็น 1 กอง `{U.splice_id[code]}` (Registration_date เดียวกัน · ชื่อเดียวกันหลังตัดแบรนด์ · ซ้อน {sc['overlap']} สัปดาห์ · ต่อใน run ไม่แก้ panel L0 · BRIEF 115(3)) · หลังต่อ train {sc['n_tr']} / test {sc['n_te']}")
    elif r.fc_key != code:
        notes.append(f"Fund Class ซ้ำ ({r.fund_class}) · นับ 1 กองในการนับกลุ่ม")
    if r.div_flag == "Y":
        notes.append("class ปันผล (NAV ไม่รวมปันผล)")
    if r.by_synonym:
        notes.append(f"จับคู่ด้วยคำพ้องของประเทศเดียวกัน '{r.matched_word}' (ไม่อยู่ในรายการคำ F-R006 · ข้อเปิดใน spec ข้อ 14)")
    if r.name_group != r.group:
        notes.append(f"กลุ่ม {r.name_group} มี {groups0[r.name_group]['n_U']} กองใน U < 5 → ใช้กลุ่มแม่ {r.group}")
    if r.group not in ALLOWED and r.group != "NONE":
        notes.append(f"ป้าย {r.group} ไม่ใช่กลุ่มตามคำ F-R006 → ไม่มี factor กลุ่ม (BRIEF 115(1))")
    elif r.group in ALLOWED and not r.group_ok:
        notes.append(f"กลุ่ม {r.group} มี {groups[r.group]['n_U']} กองใน U < 5 → ไม่มี factor กลุ่ม")
    if r.group_ok and groups[r.group]["n_eval"] < 5:
        notes.append(f"กลุ่มผ่านเกณฑ์ U แต่กอง EVAL {groups[r.group]['n_eval']} < 5 → คำตัดสินกลุ่มติดป้าย 'n เล็ก'")
    if r.alt_factor_no_synonym != r.group_factor:
        notes.append(f"ถ้าไม่ใช้คำพ้อง = {r.alt_factor_no_synonym}")
    for sk, v in subcnt.items():
        if code in v["codes"]:
            notes.append(f"กลุ่มย่อย {sk} มี {v['n_U']} กอง < 5 → รวมใน {v['parent']}")
    if r.group == "CHINA":
        notes.append("ถ้า e_CHINA ถูก stepwise เลือกเป็น factor ร่วม → factor กลุ่มของกองจีนเปลี่ยนเป็น e_AH = resid(MSCI_CHINA_A_SHARES − MSCI_CHINA_H_SHARES | factor ร่วม) (spec ข้อ 3.2)")
    if r.group == "ASIA" and r.group_ok:
        notes.append("MSCI_ASIA_EX_JAPAN ไม่อยู่ใน C11 (designer เสนอ · ผู้ใช้รับค่าเริ่มต้น BRIEF 115(5))")
    h = hedge_label(r.name_en)
    if h:
        notes.append(h)
    if pd.notna(r.prev_code) and str(r.prev_code).strip():
        notes.append(f"Previous Fund Code = {r.prev_code}")
    if r.fif != "Y":
        notes.append(f"FIF Flag = {r.fif}")
    return " · ".join(notes)


E["note"] = [note_e(c, r) for c, r in E.iterrows()]
E["rule"] = [(f"ลำดับ {r.lvl} · คำ '{r.matched_word}'{' (คำพ้อง)' if r.by_synonym else ''} → {r.name_group}" if r.matched_word else "ไม่มีคำจับคู่") for _, r in E.iterrows()]

# ───────────── O ─────────────
def o_sub(name, kind):
    n = norm(name)
    if kind == "gold":
        return "ทอง"
    if re.search(r"\bUS\b|\bUSA\b|AMERICA", n):
        return "REIT-US"
    if re.search(r"SINGAPORE", n):
        return "REIT-Singapore"
    if re.search(r"JAPAN", n):
        return "REIT-Japan"
    if re.search(r"ASIA|PACIFIC", n):
        return "REIT-Asia"
    return "REIT-Global"


O["o_group"] = ["ทอง" if k == "gold" else "REIT" for k in O.o_kind]
O["o_sub"] = [o_sub(n, k) for n, k in zip(O.name_en, O.o_kind)]
O["group_factor"] = ["GOLD_XS + FX" if k == "gold" else "MKT + REIT_e + FX + TERM" for k in O.o_kind]
O["factor_column"] = ["GLD_USD−SHV_USD ; SHV_THB−RF_BOT" if k == "gold" else "MSCI_ACWI−RF_BOT ; resid(REET_USD−SHV_USD | MKT) ; SHV_THB−RF_BOT ; IEF_USD−SHV_USD" for k in O.o_kind]
O["appendix_tilt"] = [("VNQ_USD−REET_USD" if s == "REIT-US" else ("REITCLRSI_THB−REET_THB" if s == "REIT-Singapore" else "")) for s in O.o_sub]


def note_o(code, r):
    notes = []
    if code in ("I-GOLD", "IGOLD-G"):
        sc = SPL_CNT["I-GOLD*"]
        notes.append(f"กองเดียวกันเปลี่ยนรหัส (ชื่อ EN + Fund Class + Registration_date เดียวกัน) → ต่ออนุกรมเป็น 1 กอง `I-GOLD*` (BRIEF 114(2)) · ซ้อน {sc['overlap']} สัปดาห์ (ใช้รหัสเก่า) · หลังต่อ train {sc['n_tr']} / test {sc['n_te']}")
    notes.append(f"FX Risk Flag = {r.fx_risk_flag} (FundProfile · ใช้แบ่งกลุ่มย่อย hedge ของทอง)" if r.o_kind == "gold" else f"FX Risk Flag = {r.fx_risk_flag}")
    if not r.fit:
        notes.append(f"รายรหัสไม่ครบ train ({int(r.n_tr)})")
    elif not r["eval"]:
        notes.append(f"รายรหัสไม่ครบ test ({int(r.n_te)})")
    if r.div_flag == "Y":
        notes.append("class ปันผล (NAV ไม่รวมปันผล)")
    if r.fif != "Y":
        notes.append(f"FIF Flag = {r.fif}")
    th = r.name_th if isinstance(r.name_th, str) else ""
    if re.search(r"ป้องกันความเสี่ยง", th) and not re.search(r"ไม่ป้องกัน", th):
        notes.append("ชื่อไทยระบุป้องกันความเสี่ยงค่าเงิน")
    if re.search(r"ไม่ป้องกัน", th):
        notes.append("ชื่อไทยระบุไม่ป้องกันความเสี่ยงค่าเงิน")
    h = hedge_label(r.name_en)
    if h:
        notes.append(h)
    return " · ".join(notes)


O["note"] = [note_o(c, r) for c, r in O.iterrows()]
og = O.copy()
og["k"] = [("I-GOLD*" if c in ("I-GOLD", "IGOLD-G") else c) for c in og.index]
ocount = og.groupby("o_group").k.nunique().to_dict()
osub = og.groupby("o_sub").k.nunique().to_dict()
O["group_n_U"] = [ocount[g] for g in O.o_group]
O["rule"] = ["กฎ is_gold (EN 'gold' ไม่รวม 'golden' หรือ TH 'ทองคำ') = QA_EO §9.1" if k == "gold" else "ชื่อมี REIT / PROPERTY / REAL ESTATE (QA_EO §9.1)" for k in O.o_kind]

# ───────────── CSV ─────────────
out_e = pd.DataFrame({
    "FundCode": E.index, "family": E.family, "name_en": E.name_en, "policy": "E", "o_group": "",
    "name_group": E.name_group, "group": E.group, "group_factor": E.group_factor, "factor_column": E.factor_column,
    "match_rule": E.rule, "group_n_U": E.group_n_U, "group_n_fit": E.group_n_fit, "group_n_eval": E.group_n_eval,
    "group_ge5": E.group_ok, "alt_factor_no_synonym": E.alt_factor_no_synonym, "n_train_rows": E.n_tr.astype(int), "n_test_rows": E.n_te.astype(int),
    "fit_train": E.fit, "eval": E["eval"], "splice_id": E.splice_id, "fx_risk_flag": E.fx_risk_flag, "fund_class": E.fund_class, "note": E.note,
})
out_o = pd.DataFrame({
    "FundCode": O.index, "family": O.family, "name_en": O.name_en, "policy": "O", "o_group": O.o_group,
    "name_group": O.o_sub, "group": O.o_group, "group_factor": O.group_factor, "factor_column": O.factor_column,
    "match_rule": O.rule + [(" · ภาคผนวก tilt: " + t) if t else "" for t in O.appendix_tilt], "group_n_U": O.group_n_U,
    "group_n_fit": np.nan, "group_n_eval": np.nan, "group_ge5": True, "alt_factor_no_synonym": O.group_factor,
    "n_train_rows": O.n_tr.astype(int), "n_test_rows": O.n_te.astype(int), "fit_train": O.fit, "eval": O["eval"],
    "splice_id": O.splice_id, "fx_risk_flag": O.fx_risk_flag, "fund_class": O.fund_class, "note": O.note,
})
out_e = out_e.reset_index(drop=True)
out_o = out_o.reset_index(drop=True)
out = pd.concat([out_e.sort_values(["group", "FundCode"], kind="stable"), out_o.sort_values(["o_group", "FundCode"], kind="stable")], ignore_index=True)
csv_path = ROOT / "scratch" / "factor-reviewer_s012_group_map_rerun.csv"
out.to_csv(csv_path, index=False, encoding="utf-8")

# ───────────── นับโครงอื่น ─────────────
keepE = None
nw = uni.loc[[c for c in E.index if c in uni.index], "n_weeks"]
from importlib import util
spec = util.spec_from_file_location("samples", ROOT / "lib" / "samples.py")
samples = util.module_from_spec(spec); spec.loader.exec_module(samples)
keepE = samples.dedup_keep(dup, nw)
dE = E.loc[keepE]
pca_bal = sorted(dE.index[dE.balanced])
pca_unb = sorted(dE.index[dE.unbal52])
nwO = uni.loc[[c for c in O.index if c in uni.index], "n_weeks"]
keepO = samples.dedup_keep(dup, nwO)
dup_in_U = dup[dup.a.isin(U.index) & dup.b.isin(U.index)]

prim = pd.read_csv(ROOT / "runs" / "S005" / "primary_index.csv")
P4 = ["MSCI_ACWI_HC", "MSCI_ACWI_UT", "MSCI_EUROPE", "MSCI_INDIA", "MSCI_JAPAN", "MSCI_VIETNAM"]
pr = prim[prim.form == "1a@4"] if "form" in prim.columns else prim
pcol = [c for c in pr.columns if c not in ("FundCode", "form")]
m1_cov = {}
if "FundCode" in pr.columns:
    pr = pr.set_index("FundCode")
    pc = "primary" if "primary" in pr.columns else pcol[0]
    in_prim = [c for c in E.index if c in pr.index]
    m1_cov = dict(primary_col=pc, n_E_with_L2_primary=len(in_prim),
                  n_E_primary_in_P4=int(sum(pr.loc[c, pc] in P4 for c in in_prim)),
                  n_E_eval=int(E["eval"].sum()))

js = dict(
    sha256=dict(aum_fam=sha(D / "aum_fam.parquet"), universe=sha(D / "universe.csv"), dup_pairs=sha(D / "dup_pairs.csv"),
                panel_weekly=sha(D / "panel_weekly.parquet"), fundprofile=sha(APP / "base_data" / "FundProfile.csv"),
                group_map_csv=sha(csv_path)),
    U=dict(E=int(len(E)), O=int(len(O)), F_in_U=int((U.policy == "F").sum())),
    E_counts=dict(fit=int(E.fit.sum()), eval=int(E["eval"].sum()), stab=int(E.stab.sum()), balanced=int(E.balanced.sum()),
                  unbal52=int(E.unbal52.sum()), no_train=int((E.n_tr == 0).sum()), no_test=int((E.n_te == 0).sum()),
                  any_post_2025=int((E.n_post > 0).sum()),
                  dedup_keep=len(keepE), pca_balanced=len(pca_bal), pca_unbal52=len(pca_unb),
                  fund_class_dup_groups={k: sorted(E.index[E.fund_class == k]) for k in fc_counts.index if fc_counts[k] > 1 and (E.fund_class == k).sum() > 1}),
    O_counts=dict(fit=int(O.fit.sum()), eval=int(O["eval"].sum()), stab=int(O.stab.sum()), dedup_keep=len(keepO), keepO=keepO,
                  groups=ocount, subgroups=osub, igold=ig),
    dup_pairs_in_U=int(len(dup_in_U)), dup_pairs_in_U_list=[(a, b) for a, b in zip(dup_in_U.a, dup_in_U.b)],
    E_groups_before_fallback=groups0, E_groups=groups, E_groups_nosyn=groups_ns, sub_groups=subcnt,
    alt_nosyn_counts=pd.Series(fac_ns).value_counts().to_dict(),
    E_group_factor_counts=E.groupby("group_factor").size().to_dict(),
    E_group_factor_counts_eval=E[E["eval"]].groupby("group_factor").size().to_dict(),
    E_group_factor_counts_fit=E[E.fit].groupby("group_factor").size().to_dict(),
    fif_not_Y=sorted(E.index[E.fif != "Y"]) + sorted(O.index[O.fif != "Y"]),
    div_Y=dict(E=sorted(E.index[E.div_flag == "Y"]), O=sorted(O.index[O.div_flag == "Y"])),
    M1_coverage=m1_cov, splices=SPL_CNT,
    O_fx_flag=O.fx_risk_flag.to_dict(),
    not_fit_E=sorted(E.index[~E.fit]), not_eval_E=sorted(E.index[~E["eval"]]),
    not_eval_O=sorted(O.index[~O["eval"]]),
)
(ROOT / "scratch" / "factor-reviewer_s012_structure_rerun.json").write_text(json.dumps(js, ensure_ascii=False, indent=1, default=str))
print(json.dumps({k: js[k] for k in ("U", "E_counts", "O_counts", "E_groups_before_fallback", "E_groups", "sub_groups",
                                     "E_group_factor_counts", "E_group_factor_counts_eval", "E_group_factor_counts_fit",
                                     "fif_not_Y", "div_Y", "M1_coverage", "not_eval_E", "not_eval_O", "dup_pairs_in_U")},
                 ensure_ascii=False, indent=1, default=str))
