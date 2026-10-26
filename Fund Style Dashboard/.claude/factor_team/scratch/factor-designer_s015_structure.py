"""factor-designer · S015 (addendum ของ S014) · โครงข้อมูลของช่วงถือแบบ (e_q, e_{q+1}]
อ่านเฉพาะ: วันที่ · น้ำหนัก · notna ของผลตอบแทน (ไม่อ่านค่าผลตอบแทน) · ธงจาก FundProfile / QA · ไม่ fit
ผล: scratch/factor-designer_s015_quarters.csv · scratch/factor-designer_s015_holdings.csv"""
from pathlib import Path
import pandas as pd, numpy as np

APP = Path(__file__).resolve().parents[3]
FT = APP / ".claude" / "factor_team"
REF = APP / "base_data/reference"
PANEL_END = pd.Timestamp("2025-12-26")
GAP_START = pd.Timestamp("2023-12-15")            # QA_FRIDAY_GAP §1 · QA_GOLD §2.3 (ก่อน 2023-12-08 มี NAV ศุกร์)
GOLD_GRP_A = {"BGOLD", "TGOLD", "PRINCIPAL iGOLD-A", "K-GOLD-A(A)", "KT-GOLD"}   # QA_GOLD §2.2
UNIT = {"KKP GINFRAEQ-H-F": "KKP GINFRAEQ-H", "ONE-INDIAOPP-IA": "ONE-INDIAOPP-RA", "PRINCIPAL GOPP-C": "PRINCIPAL GOPP-A"}
GROUP = {"ASP-NGF": "JAPAN", "ASP-VIET": "VIETNAM", "B-BHARATA": "INDIA", "DAOL-GOLD": "-", "FCSCBSETE": "-",
         "K-EUX": "EUROPE", "K-GINFRA-A(D)": "IGF", "KKP GINFRAEQ-H-F": "IGF", "KKP TECH-H": "IT", "KT-INDIA-A": "INDIA",
         "LHJAPE-A": "JAPAN", "ONE-INDIAOPP-IA": "INDIA", "PRINCIPAL GOPP-C": "-", "TBIOTECH": "HC", "TISCOCH": "CHINA",
         "TISCOJP": "JAPAN", "TNEXTGEN-A": "ARKK", "TUSEQ-UH": "USA", "TUSFIN-A": "USA", "UCI": "CHINA",
         "K-GOLD-A(A)": "GOLD", "BGOLD": "GOLD", "SCBGOLDHP": "GOLD"}


def bd(a, b):
    """จำนวนวันทำการ จ–ศ ใน (a, b] (ไม่หักวันหยุด) · ติดลบถ้า b < a"""
    a, b, one = np.datetime64(a.date(), "D"), np.datetime64(b.date(), "D"), np.timedelta64(1, "D")
    if b >= a:
        return int(np.busday_count(a + one, b + one))
    return -int(np.busday_count(b + one, a + one))


H = pd.read_csv(REF / "m052_frontier_holdings.csv", comment="#", parse_dates=["t", "e"])
H = H[["t", "e", "FundCode", "kind", "weight", "x_model"]]
RZ = pd.read_csv(REF / "m052_frontier_realized.csv", comment="#", usecols=["t", "portfolio", "horizon", "e", "end", "days", "truncated"],
                 parse_dates=["t", "e", "end"])
RZ = RZ[(RZ.portfolio == "ERC (กติกาโมเดล)") & (RZ.horizon == "Q")]
assert RZ.t.is_unique and len(RZ) == H.t.nunique()
RZ = RZ.set_index("t")

P = pd.read_parquet(FT / "data/panel_weekly.parquet", columns=["FundCode", "date", "ret"])
cal = pd.DatetimeIndex(sorted(P.date.unique()))
assert (cal.weekday == 4).all() and (np.diff(cal.values).astype("timedelta64[D]").astype(int) == 7).all()
units = sorted({UNIT.get(c, c) for c in H.FundCode.unique()})
NN = P[P.FundCode.isin(units)].assign(v=lambda d: d.ret.notna()).pivot(index="date", columns="FundCode", values="v")
NN = NN.reindex(cal).fillna(False).astype(bool)
del P

prof = pd.read_csv(APP / "base_data/FundProfile.csv", usecols=["Fund Code", "FX Risk Flag"]).drop_duplicates("Fund Code")
fx = dict(zip(prof["Fund Code"], prof["FX Risk Flag"]))
qa = pd.read_csv(FT / "data/qa_friday_gap_E_units.csv").set_index("unit")

ts = sorted(H.t.unique())
es = [H.loc[H.t == t, "e"].iloc[0] for t in ts]
Q, HR, owner = [], [], {}
for i, t in enumerate(ts):
    e = es[i]
    e_next_off = es[i + 1] if i + 1 < len(ts) else RZ.loc[t, "end"]
    assert RZ.loc[t, "e"] == e and RZ.loc[t, "end"] == e_next_off
    e_next = min(e_next_off, PANEL_END)
    hold = (cal > e) & (cal <= e_next)
    a = cal[hold]
    for d in a:
        assert d not in owner
        owner[d] = t
    hq = H[H.t == t]
    grp = hq.FundCode.map(GROUP)
    dup = sorted({g for g in grp if g not in ("-", "GOLD") and (grp == g).sum() > 1})
    Q.append(dict(t=t.date(), t_wd=t.day_name()[:3], e=e.date(), e_wd=e.day_name()[:3], e_next_official=e_next_off.date(),
                  first_anchor=a[0].date(), last_anchor=a[-1].date(), n_weeks=len(a),
                  start_mis_bd=bd(a[0] - pd.Timedelta(days=7), e), end_mis_bd=bd(a[-1], e_next_off),
                  anchors_t_to_e=int(((cal > t) & (cal <= e)).sum()),
                  n_hold=len(hq), x_hold=hq.loc[hq.kind == "E", "weight"].sum(), x_model=hq.x_model.iloc[0],
                  has_gold=bool((hq.kind == "G").any()), w_gold=hq.loc[hq.kind == "G", "weight"].sum(),
                  same_group=";".join(f"{g}:" + "+".join(hq.FundCode[grp == g]) for g in dup),
                  realized_days=int(RZ.loc[t, "days"]), truncated=RZ.loc[t, "truncated"]))
    win = (cal <= t) & (cal > t - pd.Timedelta(weeks=156))
    for h in hq.itertuples(index=False):
        u = UNIT.get(h.FundCode, h.FundCode)
        n_gap = int((a >= GAP_START).sum())
        if h.kind == "G":
            grpA = "Y" if u in GOLD_GRP_A else ("na" if u not in {"BGOLD", "TGOLD", "PRINCIPAL iGOLD-A", "K-GOLD-A(A)", "KT-GOLD", "I-GOLD", "IGOLD-G", "UOBSG-N"} else "N")
        else:
            grpA = ("Y" if bool(qa.loc[u, "grp_A"]) else "N") if u in qa.index else "na"
        HR.append(dict(t=t.date(), FundCode=h.FundCode, kind=h.kind, weight=round(h.weight, 6), unit=u, group=GROUP[h.FundCode],
                       n_win156=int(NN.loc[win, u].sum()), n_hold_rows=int(NN.loc[hold, u].sum()), n_hold_anchor=int(hold.sum()),
                       fx_flag_holding=fx.get(h.FundCode), fx_flag_unit=fx.get(u), fx_flag_diff=fx.get(h.FundCode) != fx.get(u),
                       fri_gap_grpA=grpA, n_gap_anchor_in_hold=n_gap, nav_fri_gap=(grpA == "Y" and n_gap > 0)))
QD, HD = pd.DataFrame(Q), pd.DataFrame(HR)
# ความต่อเนื่องของช่วงถือ: ยูเนียน = ทุก anchor ตั้งแต่ anchor แรกถึง 2025-12-26 · ไม่ซ้ำ
allh = pd.DatetimeIndex(sorted(owner))
assert (allh == cal[(cal >= allh[0]) & (cal <= PANEL_END)]).all()
yr = pd.Series({d: owner[d] for d in allh})
for y, g in yr.groupby(yr.index.year):
    qs = sorted(set(g))
    whole = all(set(yr[yr == q].index.year) == {y} for q in qs)
    print("year", y, "anchors", g.index.min().date(), "→", g.index.max().date(), "n", len(g), "quarters", [q.date().isoformat() for q in qs], "whole_quarters", whole)
QD.to_csv(FT / "scratch/factor-designer_s015_quarters.csv", index=False)
HD.to_csv(FT / "scratch/factor-designer_s015_holdings.csv", index=False)
pd.set_option("display.width", 250)
print(QD.to_string())
print(HD.groupby("FundCode").agg(n_q=("t", "size"), fx_h=("fx_flag_holding", "first"), fx_u=("fx_flag_unit", "first"),
                                   grpA=("fri_gap_grpA", "first"), gap_q=("nav_fri_gap", "sum"),
                                   min_hold=("n_hold_rows", "min"), min_win=("n_win156", "min")).to_string())
print("codes", H.FundCode.nunique(), "rows", len(H), H.kind.value_counts().to_dict())
print("hold rows == anchors:", bool((HD.n_hold_rows == HD.n_hold_anchor).all()))
print("2022 window rows (t ≤ 2022-09-30):", HD[pd.to_datetime(HD.t) <= "2022-09-30"].groupby("t").n_win156.agg(["min", "max"]).to_dict("index"))
print("DAOL/FCSCBSETE:", HD[HD.FundCode.isin(["DAOL-GOLD", "FCSCBSETE"])][["t", "FundCode", "weight"]].to_string())
W = pd.read_csv(REF / "m052_frontier_weekly.csv", comment="#", usecols=["t", "FundCode", "week"], parse_dates=["t", "week"])
nf = W[W.week.dt.weekday != 4]
print("quant weekly rows", len(W), "per (t,code)", W.groupby(["t", "FundCode"]).size().unique().tolist())
print("non-Friday rows by weekday", nf.week.dt.day_name().value_counts().to_dict(), "quarters", sorted(nf.t.dt.date.astype(str).unique()),
      "non-Fri week == t:", bool((nf.week == nf.t).all()))
