"""port — PORT-FX (ก): อธิบายพอร์ต M052 ด้วย factor ของ F5-EO (S014 + S015 · เชิงอธิบาย · ไม่นับ trial)
ไม่แก้ไฟล์ lib เดิม · ใช้ factor ไฟล์ noaqr เท่านั้น (ห้ามโหลดไฟล์ที่มี AQR) · β ประมาณด้วยข้อมูล ≤ t (rolling 156 สัปดาห์)
ส่วน A: pins · โหลด · mapping · ตารางไตรมาส / ธง   ส่วน B: factor · β ณ t · exposure · Euler
ส่วน C: น้ำหนักลอย · attribution L1 / L2 · กระทบยอด (S2) · reconcile · ภาคผนวก P-A…P-E · ข้อมูลจำลอง"""
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

import io_l1
import l1eo
import l3
import regress as rg

TEAM = io_l1.TEAM
ROOT = io_l1.ROOT
DAT = io_l1.DATA
REF = ROOT / "base_data" / "reference"
PANEL_END = pd.Timestamp("2025-12-26")
GAP_START = pd.Timestamp("2023-12-15")
WINDOW_WEEKS = 156
MIN_OBS = 52
FIX_X = 0.57
SEED = 20261015

# ───────────────────────── ส่วน A ─────────────────────────
# sha256 เต็ม (S014 ข้อ 2 + S015 ข้อ 5.1 · 6) · base: team | root | ref
PINS = {
    ("team", "data/panel_weekly.parquet"): "95c16ee651d3a936788b7cb3c6372bbf5f1e84cb39daf5680343771dca24270b",
    ("team", "data/factors_weekly.parquet"): "115b87139d2bec0fd57a77a1593c46d36bb23f3f35f83236cdb07be642af47a8",
    ("team", "data/factors_ext_weekly.parquet"): "3105b6e7fe32ffd3648e8feac8dbd03a8db22b7e8eb245c5faf462b14da5e296",
    ("team", "data/factors_eo_noaqr_weekly.parquet"): "715b4b252235b49b155c9d53554c00380d4d4430eb5c2c2e25751a3678570b3a",
    ("team", "data/manifest_eo_noaqr.json"): "6be080b10ee236937e401e9ac1680671b31b279292e3e392e482e6de78f476c9",
    ("team", "data/universe.csv"): "fdfb7830df78ce032465ac9d8cddc2c98f9aa86cfa0f3925fdb83026aa3f7252",
    ("team", "specs/S012_group_map.csv"): "898a86867b3f832060f7620d039fd95338d24e1bb71f531d76bb58004223fceb",
    ("root", "base_data/FundProfile.csv"): "9516281426fc854c8f3a0833f119cad0ce581adb39450732e579084cb4cedfaf",
    ("ref", "m052_frontier_holdings.csv"): "b877510f177bc5a113b6587393dbdc543c63f033d9573a169172e403658e233d",
    ("ref", "m052_frontier_realized.csv"): "488c38e5d0f749979ceaa49a682cd792e2710dbfffd8dd319427dda0ad1efe43",
    ("ref", "m052_frontier_weekly.csv"): "2e1ccdbae5a646e8ec633b786e560f827648c82ddc001d1c99fe04824c6e7600",
    ("team", "data/qa_friday_gap_E_units.csv"): "1756f83765dc2fe41654ceb4f90b2bd6dae4ceb9be1e7c8df88b601dd78ef6e9",
    ("team", "data/QA_GOLD.md"): "1955b2813e89a3d3c2b1b9bf244803a1a3f79124ef18695c69b7bdd490bc02e7",
    ("team", "specs/S014_PORT_M052_attribution.md"): "e3864a965a88e5f181e9a242b69efa78de4701e883306946b33bff3fdbad9310",
    ("team", "scratch/factor-designer_s015_quarters.csv"): "d6ad3ac3440ca4390719a871238fe89c0c803816c47ecbd21a1a86aa216333dd",
    ("team", "scratch/factor-designer_s015_holdings.csv"): "c8d3d66ed9cc98cf38fe2619ea58cdd410d6422ebd98c4ac04ba932b62ae52db",
}


def _pin_path(base, rel):
    return {"team": TEAM, "root": ROOT, "ref": REF}[base] / rel


def check_pins(pins=None):
    """ตรวจ sha256 เต็มทุกไฟล์ที่ spec ระบุ · ไม่ตรง = raise (หยุด)"""
    pins = PINS if pins is None else pins
    out = {}
    for (base, rel), want in pins.items():
        got = io_l1.sha256_file(_pin_path(base, rel))
        if got != want:
            raise ValueError(f"sha256 ไม่ตรง: {rel}: {got} != {want}")
        out[f"{base}:{rel}"] = got
    return out


def load_m052(ref_dir=REF, check=True):
    """holdings M052 (ข้าม comment `#` · ตรวจ sha · Σw = 1 ต่อไตรมาส)"""
    p = Path(ref_dir) / "m052_frontier_holdings.csv"
    if check and io_l1.sha256_file(p) != PINS[("ref", "m052_frontier_holdings.csv")]:
        raise ValueError("sha256 holdings ไม่ตรง")
    H = pd.read_csv(p, comment="#", parse_dates=["t", "e"])
    H = H[["t", "e", "FundCode", "kind", "weight", "x_model"]].copy()
    s = H.groupby("t")["weight"].sum()
    assert np.allclose(s.to_numpy(), 1.0, atol=1e-12), "Σw ≠ 1"
    return H


REALIZED_META = ["t", "portfolio", "horizon", "e", "end", "days", "truncated"]
REALIZED_FULL = ["cost", "ret", "ret_gross", "rf_ann", "weights"]      # เปิดได้เฉพาะ phase full (S015 ข้อ 4.9)
MODEL_ROW = "ERC (กติกาโมเดล)"


def load_realized(ref_dir=REF, full=False, check=True):
    """realized ของแถว `ERC (กติกาโมเดล)` · horizon Q · full=False อ่านเฉพาะคอลัมน์โครง (ห้ามเปิดค่าผลตอบแทน) · full=True เพิ่ม ret/ret_gross/cost/rf_ann/weights"""
    p = Path(ref_dir) / "m052_frontier_realized.csv"
    if check and io_l1.sha256_file(p) != PINS[("ref", "m052_frontier_realized.csv")]:
        raise ValueError("sha256 realized ไม่ตรง")
    cols = REALIZED_META + (REALIZED_FULL if full else [])
    Z = pd.read_csv(p, comment="#", usecols=cols, parse_dates=["t", "e", "end"])
    Z = Z[(Z["portfolio"] == MODEL_ROW) & (Z["horizon"] == "Q")]
    assert Z["t"].is_unique
    return Z.set_index("t").sort_index()


def parse_weights(s):
    """คอลัมน์ weights ของ realized → dict รหัส → น้ำหนัก (รองรับ JSON dict · 'A:0.1;B:0.2' · 'A=0.1|B=0.2')"""
    s = str(s).strip()
    if s.startswith("{"):
        return {k: float(v) for k, v in json.loads(s).items()}
    out = {}
    for part in re.split(r"[;|]", s):
        part = part.strip()
        if not part:
            continue
        k, v = re.split(r"[:=](?=[^:=]*$)", part)
        out[k.strip()] = float(v)
    return out


def load_eo_noaqr(freq="W"):
    """factor ไฟล์ noaqr · ตรวจ manifest_eo_noaqr.json + sha256 · assert ไม่มีคอลัมน์ AQR · ตัดแถว > 2025-12-26"""
    f = {"W": "factors_eo_noaqr_weekly.parquet", "M": "factors_eo_noaqr_monthly.parquet"}[freq]
    man = json.load(open(DAT / "manifest_eo_noaqr.json"))
    entries = {e["file"]: e["sha256"] for e in man["outputs"] if "sha256" in e}
    key = ".claude/factor_team/data/" + f
    got = io_l1.sha256_file(DAT / f)
    if key not in entries or entries[key] != got:
        raise ValueError(f"sha256 {f} ไม่ตรง manifest_eo_noaqr.json")
    df = pd.read_parquet(DAT / f)
    assert not any(str(c).upper().startswith("AQR") for c in df.columns), "พบคอลัมน์ AQR"
    if freq == "W":
        return df.loc[io_l1.MAIN_START:io_l1.MAIN_END].copy()
    return df.loc[io_l1.MONTH_START:io_l1.MONTH_END].copy()


HOLDING_UNIT = {"KKP GINFRAEQ-H-F": "KKP GINFRAEQ-H", "ONE-INDIAOPP-IA": "ONE-INDIAOPP-RA", "PRINCIPAL GOPP-C": "PRINCIPAL GOPP-A"}   # ล็อก S014 ข้อ 0.2 / S015 ข้อ 3
GOLD_GRP_A = {"BGOLD", "TGOLD", "PRINCIPAL iGOLD-A", "K-GOLD-A(A)", "KT-GOLD"}                    # QA_GOLD §2.2
GOLD_QA_SET = GOLD_GRP_A | {"I-GOLD", "IGOLD-G", "UOBSG-N"}
GROUP_LABEL = {"e_CHINA(grp)": "CHINA", "e_HC": "HC", "e_IT": "IT", "e_ARKK": "ARKK", "e_IGF": "IGF"}


def group_label(gf):
    if gf == "ไม่มี":
        return "-"
    return GROUP_LABEL.get(gf, gf[2:])


def bd(a, b):
    """จำนวนวันทำการ จ–ศ ใน (a, b] (ไม่หักวันหยุด) · ติดลบถ้า b < a"""
    a, b, one = np.datetime64(pd.Timestamp(a).date(), "D"), np.datetime64(pd.Timestamp(b).date(), "D"), np.timedelta64(1, "D")
    if b >= a:
        return int(np.busday_count(a + one, b + one))
    return -int(np.busday_count(b + one, a + one))


def map_holdings(H, universe, gmap, profile):
    """ตาราง mapping ต่อรหัส holding (S014 0.2 / S015 §3): หน่วย panel (รหัสเดียวกัน → ตัวแทน family) · ใน U · factor กลุ่ม (gmap → กฎชื่อ) · FX flag
    universe: DataFrame index FundCode (family · included) · gmap: DataFrame (FundCode · unit · group · group_factor · policy) · profile: DataFrame index Fund Code (Fund Name EN · FX Risk Flag)"""
    gm_units = gmap.drop_duplicates("unit").set_index("unit")
    gm_codes = set(gmap["FundCode"])
    groups_ok = {g for g, d in gmap[gmap["policy"] == "E"].groupby("group") if (d["group_factor"] != "ไม่มี").any()}
    rows = []
    for code, kind in H.drop_duplicates("FundCode")[["FundCode", "kind"]].itertuples(index=False):
        if code in HOLDING_UNIT:
            unit, how = HOLDING_UNIT[code], "ตัวแทน family"
            fam = universe.loc[code, "family"]
            rep = sorted(universe.index[(universe["family"] == fam) & universe["included"]])
            assert unit in rep, (code, rep)
        else:
            unit, how = code, "รหัสเดียวกัน"
            assert bool(universe.loc[code, "included"]), f"{code} ไม่อยู่ใน panel"
        in_U = unit in gm_codes
        if kind == "G":
            gf, gsrc = "GOLD_XS + FX", "ชุดทอง"
        elif in_U:
            gf, gsrc = gm_units.loc[unit, "group_factor"], "S012_group_map"
        else:
            name = profile.loc[unit, "Fund Name EN"]
            lvl, key, word, syn = l1eo.apply_name_rules(name)
            gf = l1eo.RMAP[key][4] if (key in l1eo.ALLOWED and key in groups_ok) else "ไม่มี"
            gsrc = f"กฎชื่อ '{word}' → {key}"
        fxh, fxu = profile["FX Risk Flag"].get(code), profile["FX Risk Flag"].get(unit)
        rows.append(dict(FundCode=code, kind=kind, unit=unit, how=how, in_U=in_U, group_factor=gf, group_source=gsrc, group=("GOLD" if kind == "G" else group_label(gf)),
                         class_diff=(code != unit), fx_flag_holding=fxh, fx_flag_unit=fxu, fx_flag_diff=(fxh != fxu)))
    return pd.DataFrame(rows).sort_values("FundCode", kind="stable").reset_index(drop=True)


def quarter_table(H, RZm, idx, panel_end=PANEL_END):
    """ตารางไตรมาส (S015 ข้อ 1): ช่วงถือ = anchor ศุกร์ใน (e_q, e_{q+1}] · ไตรมาสสุดท้ายถึง min(end ทางการ, ขอบ panel) · e / end ตรง realized
    → (DataFrame, dict t → DatetimeIndex ของ anchor ช่วงถือ)"""
    idx = pd.DatetimeIndex(idx)
    ts_ = sorted(H["t"].unique())
    es = [H.loc[H["t"] == t, "e"].iloc[0] for t in ts_]
    rows, anchors, owner = [], {}, {}
    for i, t in enumerate(ts_):
        e = es[i]
        e_next_off = es[i + 1] if i + 1 < len(ts_) else RZm.loc[t, "end"]
        assert RZm.loc[t, "e"] == e and RZm.loc[t, "end"] == e_next_off, f"e / end ไม่ตรง realized: {t}"
        e_next = min(e_next_off, pd.Timestamp(panel_end))
        a = idx[(idx > e) & (idx <= e_next)]
        for d in a:
            assert d not in owner, "anchor ซ้ำ"
            owner[d] = t
        anchors[t] = a
        hq = H[H["t"] == t]
        rows.append(dict(t=t.date(), t_wd=t.day_name()[:3], e=e.date(), e_wd=e.day_name()[:3], e_next_official=e_next_off.date(), first_anchor=a[0].date(),
                         last_anchor=a[-1].date(), n_weeks=len(a), start_mis_bd=bd(a[0] - pd.Timedelta(days=7), e), end_mis_bd=bd(a[-1], e_next_off),
                         anchors_t_to_e=int(((idx > t) & (idx <= e)).sum()), n_hold=len(hq), x_hold=float(hq.loc[hq["kind"] == "E", "weight"].sum()),
                         x_model=float(hq["x_model"].iloc[0]), has_gold=bool((hq["kind"] == "G").any()), w_gold=float(hq.loc[hq["kind"] == "G", "weight"].sum()),
                         realized_days=int(RZm.loc[t, "days"]), truncated=bool(RZm.loc[t, "truncated"])))
    return pd.DataFrame(rows), anchors


def holding_table(H, mp, anchors, idx, notna, qa_units):
    """ธงต่อ (t, holding) (S015 §3 · designer): n_win156 · n_hold_rows · FX flag · กลุ่ม A ช่องว่าง · nav_fri_gap
    notna: DataFrame bool (idx × unit) · qa_units: Series bool index unit (grp_A)"""
    idx = pd.DatetimeIndex(idx)
    rows = []
    mpi = mp.set_index("FundCode")
    for t, a in anchors.items():
        win = (idx <= t) & (idx > t - pd.Timedelta(weeks=WINDOW_WEEKS))
        hold = idx.isin(a)
        for h in H[H["t"] == t].itertuples(index=False):
            m = mpi.loc[h.FundCode]
            u = m["unit"]
            n_gap = int((a >= GAP_START).sum())
            if h.kind == "G":
                grpA = "Y" if u in GOLD_GRP_A else ("na" if u not in GOLD_QA_SET else "N")
            else:
                grpA = ("Y" if bool(qa_units[u]) else "N") if u in qa_units.index else "na"
            rows.append(dict(t=t.date(), FundCode=h.FundCode, kind=h.kind, weight=round(float(h.weight), 6), unit=u, group=m["group"],
                             n_win156=int(notna.loc[win, u].sum()), n_hold_rows=int(notna.loc[hold, u].sum()), n_hold_anchor=int(hold.sum()),
                             fx_flag_holding=m["fx_flag_holding"], fx_flag_unit=m["fx_flag_unit"], fx_flag_diff=bool(m["fx_flag_diff"]),
                             fri_gap_grpA=grpA, n_gap_anchor_in_hold=n_gap, nav_fri_gap=(grpA == "Y" and n_gap > 0)))
    return pd.DataFrame(rows)


# ───────────────────────── ส่วน B ─────────────────────────
CORE = ["MKT", "FX", "CMA"]


def factor_frames(F, Fext, Feo):
    """MKT · FX · CMA · GOLD_XS · TDEXX · I_g (ดิบ ยังไม่ตั้งฉาก) · rf — นิยามเดียวกับ S012 ข้อ 3.1–3.2 (Feo = ไฟล์ noaqr)"""
    rf = F["RF_BOT"]
    base = pd.DataFrame({"MKT": F["MSCI_ACWI"] - rf, "FX": F["SHV_THB"] - rf, "CMA": Feo["KF_DEV_CMA"], "GOLD_XS": Feo["GLD_USD"] - F["SHV_USD"],
                         "TDEXX": F["TDEX_THB"] - rf}, index=F.index)
    return dict(base=base, I=l1eo.group_I(F, Fext, False), rf=rf, gld_thb=Feo["GLD_THB"])


def window_mask(index, t, weeks=WINDOW_WEEKS):
    """หน้าต่าง ≤ t และ > t − weeks สัปดาห์"""
    idx = pd.DatetimeIndex(index)
    t = pd.Timestamp(t)
    return np.asarray((idx <= t) & (idx > t - pd.Timedelta(weeks=weeks)))


def group_factors_at(I, X1, mask):
    """e_g ของไตรมาส: residualize(I_g | X1 · lag 0 · เก็บค่าคงที่) ด้วย b̂ ของหน้าต่างไตรมาส → (E ทุกแถว, coef)"""
    return l3.residualize(I, X1, mask)


def betas_at(R, unit, D, mask, min_obs=MIN_OBS, L=4):
    """Dimson lag 1 + HAC · D = DataFrame design (factor lag 0) → dict(α · b0 · b1 · β · se_beta · σ²_ε = ssr/(n − p) · adj R² · n · resid) หรือ None"""
    fit = rg.fit_funds(R, rg.CommonFactors(D), mask, min_obs, L, funds=[unit])
    if not fit.ok[0]:
        return None
    K = D.shape[1]
    n = int(fit.n[0])
    return dict(unit=unit, names=list(D.columns), alpha=float(fit.alpha[0]), b0=fit.b0[0].copy(), b1=fit.b1[0].copy(), beta=fit.beta[0].copy(), se_beta=fit.se_beta[0].copy(),
                s2=float(fit.ssr[0] / (n - (1 + 2 * K))), adj_r2=float(fit.adj_r2[0]), r2=float(fit.r2[0]), n=n, resid=fit.resid[:, 0].copy(), design=D)


def design_for(h, FRb, EG, variant="main"):
    """design ของ holding ต่อ variant: main = E: MKT FX CMA (+ e_g) · G: GOLD_XS FX · PB = ตัด CMA · PA = DAOL-GOLD เพิ่ม GOLD_XS · FCSCBSETE เพิ่ม TDEXX"""
    if h["kind"] == "G":
        return FRb[["GOLD_XS", "FX"]]
    cols = ["MKT", "FX"] if variant == "PB" else ["MKT", "FX", "CMA"]
    D = FRb[cols].copy()
    if variant == "PA" and h["FundCode"] == "DAOL-GOLD":
        D["GOLD_XS"] = FRb["GOLD_XS"]
    if variant == "PA" and h["FundCode"] == "FCSCBSETE":
        D["TDEXX"] = FRb["TDEXX"]
    gf = h["group_factor"]
    if gf != "ไม่มี":
        nm = l1eo.GNAME[gf]
        D[nm] = EG[nm]
    return D


def union_names(designs):
    seen = []
    for D in designs:
        for c in D.columns:
            if c not in seen:
                seen.append(c)
    order = ["MKT", "FX", "CMA", "GOLD_XS", "TDEXX"]
    return [c for c in order if c in seen] + sorted(c for c in seen if c not in order)


def quarter_fit(R, FR, t, hold, mp, variant="main", weeks=WINDOW_WEEKS, min_obs=MIN_OBS):
    """β ณ t (ข้อมูล ≤ t เท่านั้น) ของ holding ทุกตัวในไตรมาส → dict
    hold: DataFrame (FundCode · kind · weight) ของไตรมาส · mp: mapping ต่อรหัส (index FundCode · unit · group_factor)"""
    mask = window_mask(R.index, t, weeks)
    FRb = FR["base"]
    X1 = FRb[["MKT", "FX"] if variant == "PB" else CORE]
    need = sorted({l1eo.GNAME[mp.loc[c, "group_factor"]] for c, k in zip(hold["FundCode"], hold["kind"]) if k == "E" and mp.loc[c, "group_factor"] != "ไม่มี"})
    I = FR["I"]
    if need:
        EG, coef = group_factors_at(I[need], X1, mask)
    else:
        EG, coef = pd.DataFrame(index=R.index), pd.DataFrame()
    fits, designs = [], []
    for h in hold.itertuples(index=False):
        row = dict(FundCode=h.FundCode, kind=h.kind, group_factor=mp.loc[h.FundCode, "group_factor"])
        D = design_for(row, FRb, EG, variant)
        b = betas_at(R, mp.loc[h.FundCode, "unit"], D, mask, min_obs)
        if b is None:
            raise RuntimeError(f"fit ไม่ได้: {h.FundCode} t={t} (spec: ไม่ควรเกิด)")
        b.update(code=h.FundCode, w=float(h.weight), kind=h.kind)
        fits.append(b)
        designs.append(D)
    names = union_names(designs)
    FU = pd.concat([FRb[[c for c in names if c in FRb.columns]], EG[[c for c in names if c in EG.columns]]], axis=1)[names]
    return dict(t=pd.Timestamp(t), mask=mask, fits=fits, EG=EG, coef=coef, names=names, FU=FU, variant=variant)


def sigma_f(qf):
    """covariance ตัวอย่าง (ddof 1 · lag 0) ของ factor ของพอร์ตบนแถวหน้าต่างที่ factor ครบ → (Σ, n)"""
    X = qf["FU"].to_numpy(float)
    ok = qf["mask"] & np.isfinite(X).all(axis=1)
    return np.cov(X[ok], rowvar=False, ddof=1).reshape(len(qf["names"]), len(qf["names"])), int(ok.sum())


def exposure(qf):
    """B_k = Σ_i w_i β_ik (0 ถ้า holding ไม่มี factor นั้น) · se_B โดยประมาณ √(Σ w² se²) · σ² เฉพาะตัว"""
    names = qf["names"]
    B, S2, s2 = np.zeros(len(names)), np.zeros(len(names)), []
    for f in qf["fits"]:
        for j, c in enumerate(f["names"]):
            k = names.index(c)
            B[k] += f["w"] * f["beta"][j]
            S2[k] += f["w"] ** 2 * f["se_beta"][j] ** 2
        s2.append(f["s2"])
    w = np.array([f["w"] for f in qf["fits"]])
    return B, np.sqrt(S2), w, np.array(s2)


def var_decomp(B, Sigma, w, s2eps):
    """V = B′ΣB + Σ w² σ²_ε · Euler: share_k = B_k (ΣB)_k / V · share_ε = Σ w² σ²_ε / V → dict"""
    SB = Sigma @ B
    sys_ = float(B @ SB)
    eps = float(np.sum(w ** 2 * s2eps))
    V = sys_ + eps
    return dict(V=V, systematic=sys_, eps=eps, share=B * SB / V, share_eps=eps / V)


def cov_resid_appendix(qf, B, Sigma):
    """ภาคผนวก P-E: Ω = Ẽ′Ẽ / n_common (ไม่ demean) บนแถวร่วมของ residual ทุกกองที่ถือ → share_ε แบบ cov เต็ม / แบบทแยง (แถวร่วมเดียวกัน)"""
    Rm_ = np.column_stack([f["resid"] for f in qf["fits"]])
    ok = np.isfinite(Rm_).all(axis=1)
    E = Rm_[ok]
    n = int(ok.sum())
    Om = E.T @ E / n
    w = np.array([f["w"] for f in qf["fits"]])
    sys_ = float(B @ Sigma @ B)
    full = float(w @ Om @ w)
    diag = float(np.sum(w ** 2 * np.diag(Om)))
    return dict(n_common=n, share_eps_full=full / (sys_ + full), share_eps_diag=diag / (sys_ + diag))


# ───────────────────────── ส่วน C ─────────────────────────
def drift_weights(w0, R_hold):
    """น้ำหนักลอย buy-and-hold: คืน (Wstart n_weeks × n = น้ำหนักก่อนสัปดาห์ s · r_p รายสัปดาห์) · R_hold = ผลตอบแทนรวม (ไม่หัก rf) · Σ = 1 ทุกสัปดาห์"""
    R_hold = np.asarray(R_hold, float)
    T, n = R_hold.shape
    W = np.zeros((T, n))
    rp = np.zeros(T)
    w = np.asarray(w0, float).copy()
    for s in range(T):
        W[s] = w
        rp[s] = float(w @ R_hold[s])
        g = w * (1.0 + R_hold[s])
        w = g / g.sum()
    return W, rp


def attribute_weekly(qf, anchors, R, rf, extra_detail=False):
    """เอกลักษณ์ L1 รายสัปดาห์ (S014 3.4): x_s = r_p,s − rf_s = Σ_k C_k,s + A_s + E_s · C_k,s = Σ_i w_{i,s−1}(b0_ik f_k,s + b1_ik f_k,s−1) · A_s = Σ w α · E_s = Σ w ε
    qf: ผล quarter_fit · anchors: anchor ช่วงถือ · R: ผลตอบแทนส่วนเกินของหน่วย · rf: Series RF_BOT → DataFrame รายสัปดาห์ (+ detail ต่อ holding × factor)"""
    idx = R.index
    pos = np.array([idx.get_loc(a) for a in anchors])
    fits = qf["fits"]
    names = qf["names"]
    n = len(fits)
    rf_s = rf.to_numpy(float)[pos]
    Rex = np.column_stack([R[f["unit"]].to_numpy(float)[pos] for f in fits])
    Rraw = Rex + rf_s[:, None]
    W, rp = drift_weights([f["w"] for f in fits], Rraw)
    x = Rex_p = np.sum(W * Rex, axis=1)
    C = np.zeros((len(pos), len(names)))
    A = np.zeros(len(pos))
    E = np.zeros(len(pos))
    det = {}
    for i, f in enumerate(fits):
        D = f["design"].to_numpy(float)
        cur, lag = D[pos], D[pos - 1]
        fitted = f["alpha"] + cur @ f["b0"] + lag @ f["b1"]
        eps = Rex[:, i] - fitted
        A += W[:, i] * f["alpha"]
        E += W[:, i] * eps
        for j, c in enumerate(f["names"]):
            contrib = W[:, i] * (f["b0"][j] * cur[:, j] + f["b1"][j] * lag[:, j])
            C[:, names.index(c)] += contrib
            if extra_detail:
                det[(f["code"], c)] = contrib
    df = pd.DataFrame(C, columns=["C_" + c for c in names], index=pd.DatetimeIndex(anchors))
    df.insert(0, "r_p", rp)
    df.insert(1, "rf", rf_s)
    df.insert(2, "x", x)
    df["A"], df["E"] = A, E
    df["id_err"] = df["x"] - df[[c for c in df.columns if c.startswith("C_")]].sum(axis=1) - df["A"] - df["E"]
    return (df, W, det) if extra_detail else (df, W)


def reconcile_period(df):
    """กระทบยอดช่วงสรุป (S015 ข้อ 2 · แบบ ก): SUM = Σ x_s · CEX = Π(1+r_p) − Π(1+rf) · K = CEX − SUM → dict"""
    comp = {c: float(df[c].sum()) for c in df.columns if c.startswith("C_")}
    comp.update(A=float(df["A"].sum()), E=float(df["E"].sum()))
    s = float(df["x"].sum())
    gp, gf = float(np.prod(1.0 + df["r_p"])), float(np.prod(1.0 + df["rf"]))
    cex = gp - gf
    return dict(components=comp, SUM=s, CEX=cex, K=cex - s, cum_rp=gp - 1.0, cum_rf=gf - 1.0, n=len(df))


def shares_table(rec, min_base=0.02):
    """ส่วนแบ่ง % ตามกติกา S2: share = ΣC / CEX พร้อมแถว A · E · K (รวม = 100%) · |CEX| < 2 pp → N/A"""
    cex = rec["CEX"]
    items = dict(rec["components"])
    items["K"] = rec["K"]
    if abs(cex) < min_base:
        return {k: np.nan for k in items}
    return {k: v / cex for k, v in items.items()}


def attribute_L2(qf, B, ret_gross, rf_off, F_sum, n_weeks):
    """L2 (S015 ข้อ 4.3): R^off,ex = ret_gross − rf_off = Σ_k B_k F_k + A_q + ε_L2 · B ใช้น้ำหนักต้นไตรมาส · A_q = (Σ w α) × n_weeks → dict"""
    names = qf["names"]
    w = np.array([f["w"] for f in qf["fits"]])
    A = float(np.sum(w * np.array([f["alpha"] for f in qf["fits"]])) * n_weeks)
    BF = {c: float(B[k] * F_sum[k]) for k, c in enumerate(names)}
    R_ex = float(ret_gross - rf_off)
    eps = R_ex - sum(BF.values()) - A
    return dict(R_ex=R_ex, BF=BF, A=A, eps=eps)


def reconcile_L2(rows):
    """หลายไตรมาส L2: SUM^off = Σ R_ex · CEX^off = Π(1+ret_gross) − Π(1+rf_off) · K^off = CEX − SUM · rows: list of dict(ret_gross · rf_off · R_ex · BF · A · eps)"""
    names = sorted({c for r in rows for c in r["BF"]})
    BF = {c: float(sum(r["BF"].get(c, 0.0) for r in rows)) for c in names}
    A = float(sum(r["A"] for r in rows))
    eps = float(sum(r["eps"] for r in rows))
    SUM = float(sum(r["R_ex"] for r in rows))
    CEX = float(np.prod([1 + r["ret_gross"] for r in rows]) - np.prod([1 + r["rf_off"] for r in rows]))
    return dict(BF=BF, A=A, eps=eps, SUM=SUM, CEX=CEX, K=CEX - SUM, cum_gross=float(np.prod([1 + r["ret_gross"] for r in rows]) - 1),
                cum_rf=float(np.prod([1 + r["rf_off"] for r in rows]) - 1))


def split_returns(qf, anchors, R, rf, gld_thb, x_model=None, fix_x=FIX_X):
    """P-C (S015 ข้อ 4.2): R_E = Σ_{i∈E}(w_i/x)[Π(1+r_i) − 1] · R_G = Π(1+r_G) − 1 (ทองกองเดียว) · x_q = Σw ขา E · x = 1 → R_G* = Π(1 + GLD_THB) − 1 + ธง
    เอกลักษณ์ R_panel = x R_E + (1 − x) R_G · AE = (x − fix_x)(R_E − R_G) = R_panel − R_FIX"""
    idx = R.index
    pos = np.array([idx.get_loc(a) for a in anchors])
    rf_s = rf.to_numpy(float)[pos]
    fits = qf["fits"]
    Rraw = np.column_stack([R[f["unit"]].to_numpy(float)[pos] for f in fits]) + rf_s[:, None]
    W, rp = drift_weights([f["w"] for f in fits], Rraw)
    is_e = np.array([f["kind"] == "E" for f in fits])
    w0 = np.array([f["w"] for f in fits])
    x = float(w0[is_e].sum())
    cumi = np.prod(1.0 + Rraw, axis=0) - 1.0
    R_panel = float(np.prod(1.0 + rp) - 1.0)
    R_E = float(np.sum(w0[is_e] / x * cumi[is_e])) if x > 0 else np.nan
    has_g = bool((~is_e).any())
    if has_g:
        R_G = float(np.sum(w0[~is_e] / w0[~is_e].sum() * cumi[~is_e]))
        proxy = False
    else:
        R_G = float(np.prod(1.0 + gld_thb.to_numpy(float)[pos]) - 1.0)
        proxy = True
    R_fix = fix_x * R_E + (1 - fix_x) * R_G
    AE = (x - fix_x) * (R_E - R_G)
    return dict(x_hold=x, x_model=x_model, R_E=R_E, R_G=R_G, RG_proxy=proxy, R_panel=R_panel, R_FIX=R_fix, AE=AE,
                id_err=R_panel - (x * R_E + (1 - x) * R_G), ae_err=(R_panel - R_fix) - AE)


def reconcile_PC(rows):
    """P-C หลายไตรมาส: ΣAE + K_PC = G_act − G_fix · G = Π(1+R_q) − 1 · rows: list of dict(R_panel · R_FIX · AE)"""
    g_act = float(np.prod([1 + r["R_panel"] for r in rows]) - 1)
    g_fix = float(np.prod([1 + r["R_FIX"] for r in rows]) - 1)
    sae = float(sum(r["AE"] for r in rows))
    return dict(G_act=g_act, G_fix=g_fix, sum_AE=sae, K_PC=(g_act - g_fix) - sae, diff=g_act - g_fix)


def reconcile_panel_official(R_panel, ret_gross, ret, cost, flags=""):
    """ส่วนต่าง panel vs ทางการ: Δ = ret_gross − R_panel · ต้นทุน = ret_gross − ret"""
    return dict(R_panel=R_panel, ret_gross=ret_gross, ret=ret, delta=ret_gross - R_panel, cost=ret_gross - ret, cost_col=cost, flags=flags)


def pd_betas(R, FR, qf, wk, ret_col, min_rows=40, L=4):
    """P-D: fit E-X2 / ชุดทองของ holding บนผลตอบแทน 'quant weekly' (ตัดแถวที่ไม่ใช่ศุกร์ · ผลตอบแทนรวม − rf ที่ anchor เดียวกัน) · lag จาก factor ณ anchor ก่อนหน้า
    wk: DataFrame (FundCode · week · ret) ของ (t) นั้น → list dict(FundCode · beta · names · n_rows · n_dropped_nonfri)"""
    idx = R.index
    rf = FR["rf"]
    out = []
    for f in qf["fits"]:
        d = wk[wk["FundCode"] == f["code"]]
        fri = d[d["week"].dt.weekday == 4]
        pos = np.array([idx.get_loc(x) for x in fri["week"]])
        y = fri[ret_col].to_numpy(float) - rf.to_numpy(float)[pos]
        D = f["design"].to_numpy(float)
        X = np.column_stack([np.ones(len(pos)), D[pos], D[pos - 1]])
        ok = np.isfinite(X).all(axis=1) & np.isfinite(y)
        r = rg.ols_hac(y[ok], X[ok], L)
        K = D.shape[1]
        out.append(dict(FundCode=f["code"], names=f["names"], beta=r["coef"][1:1 + K] + r["coef"][1 + K:], n_rows=int(ok.sum()), n_dropped_nonfri=int(len(d) - len(fri)),
                        adj_r2=float(r["adj_r2"])))
    return out


# ───────────── ข้อมูลจำลอง (test · smoke) ─────────────
def sim_world(seed=SEED, n_quarters=4, n_units=6, T=260):
    """โลกจำลองเล็ก: factor (คอลัมน์/ดัชนีจริงของ noaqr เฉพาะรูปร่าง) · ผลตอบแทนกองจำลอง · holdings จำลอง → dict"""
    F0 = io_l1.load_factors("W")
    F = l1eo.sim_factors(F0, seed)
    Fext = l1eo.sim_factors(l1eo.load_ext("W"), seed + 1)
    Feo = l1eo.sim_factors(pd.read_parquet(DAT / "factors_eo_noaqr_weekly.parquet").loc[io_l1.MAIN_START:io_l1.MAIN_END], seed + 2)
    rng = np.random.default_rng(seed + 3)
    idx = F.index
    FR = factor_frames(F, Fext, Feo)
    units = [f"U{i}" for i in range(n_units)]
    base = FR["base"]
    R = pd.DataFrame(index=idx)
    for i, u in enumerate(units):
        if i % 3 == 2:
            R[u] = 0.9 * base["GOLD_XS"] + 0.3 * base["FX"] + 0.004 * rng.normal(size=len(idx))
        else:
            R[u] = 0.7 * base["MKT"] + 0.2 * base["FX"] + 0.1 * base["CMA"] + 0.3 * FR["I"]["e_USA"] + 0.004 * rng.normal(size=len(idx))
    return dict(F=F, Fext=Fext, Feo=Feo, FR=FR, R=R, units=units, idx=idx)
