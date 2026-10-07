"""quant_m015_fnav.py — สำรวจความพร้อมข้อมูล NAV กอง F (นับจำนวนเท่านั้น ไม่คำนวณ return/Sharpe) · read-only"""
import sys, os; sys.path.insert(0, ".")
import pandas as pd, numpy as np
from data.nav_loader import _detect_and_fix_spikes   # ฟังก์ชันบริสุทธิ์ (ไม่เขียนไฟล์)
p = pd.read_csv("base_data/FundProfile.csv", dtype=str, encoding="utf-8-sig"); p.columns=[c.strip() for c in p.columns]
p = p.drop_duplicates("Fund Code").set_index("Fund Code")
F = p[p["Fund Policy"]=="F"]
codes = set(F.index)
parts=[]
for ch in pd.read_csv("base_data/nav_history_db.csv", usecols=["FundCode","NAV","NAVDate","AUM","UpdateTime"], chunksize=500_000, dtype={"FundCode":str}):
    parts.append(ch[ch["FundCode"].isin(codes)])
d = pd.concat(parts); d["NAVDate"]=pd.to_datetime(d["NAVDate"], errors="coerce")
d = d.sort_values(["FundCode","NAVDate","UpdateTime"]).drop_duplicates(["FundCode","NAVDate"], keep="last")
d.to_parquet("/private/tmp/claude-501/-Users-doyinratnavardhana-Fama-French/6c152800-b697-48fc-bf2e-df01662e9e0e/scratchpad/fnav.parquet")
print("F classes in profile", len(codes), "| with any NAV", d.FundCode.nunique(), "| rows", len(d), "| NAVDate range", d.NAVDate.min().date(), d.NAVDate.max().date())
w = d[(d.NAVDate>="2021-01-01")&(d.NAVDate<="2025-12-31")]
g = w.groupby("FundCode").agg(first=("NAVDate","min"), last=("NAVDate","max"), n=("NAVDate","nunique"))
print("with NAV in 2021-2025:", len(g), "| first<=2021-03-31 & last>=2025-12-01:", int(((g["first"]<="2021-03-31")&(g["last"]>="2025-12-01")).sum()))
# base eligibility (snapshot)
base = F[(F["Tax Type"].isna()) & (F["buy period flag"]=="N") & (F["Project Retail Type"]=="R")]
fb = pd.to_numeric(base["fst_lowbuy_val"], errors="coerce"); base = base[fb<=100_000]
base = base[~base["Fund Name EN"].fillna("").str.contains("Not for Retail|NOT FOR RETAIL|TEST", regex=True)]
print("snapshot-eligible F (no tax class, buy period N, retail R, min<=100k, not AI/test):", len(base),
      "| FIF Y", int((base["FIF Flag"]=="Y").sum()), "| risk1-2 (MMF)", int(base["Fund Risk Level"].isin(["1","2"]).sum()),
      "| Dividend Y", int((base["Dividend_Flag"]=="Y").sum()), "| auto-redeem", int(base["Auto redeem fund"].notna().sum()))
# per quarter PIT counts
cal = pd.date_range("2021-12-31","2025-12-31",freq="QE")
reg = pd.to_datetime(F["Registration_date"], format="%Y%m%d", errors="coerce")
bs=set(base.index); rows=[]
for t in cal:
    sub = d[d.NAVDate<=t]; gg = sub.groupby("FundCode")
    last = gg["NAVDate"].max(); hist = sub[sub.NAVDate>="2021-01-01"].groupby("FundCode")["NAVDate"].nunique().reindex(last.index).fillna(0)
    aum = sub[(sub.AUM>0)&(sub.NAVDate>=t-pd.Timedelta(days=90))].groupby("FundCode")["AUM"].last().reindex(last.index).fillna(0)
    ok = ((t-last).dt.days<=90)&(hist>=252)
    ok10 = ok & ((t-last).dt.days<=10)
    q = ok10 & (aum>=1e8) & (reg.reindex(last.index)<=t-pd.Timedelta(days=730)) & last.index.isin(bs)
    rows.append({"t":t.date(),"U90":int(ok.sum()),"fresh10":int(ok10.sum()),"pass_all":int(q.sum()),
                 "pass&AUM>=1bn":int((q&(aum>=1e9)).sum()),"pass&MMF":int((q&F["Fund Risk Level"].reindex(last.index).isin(["1","2"])).sum()),
                 "pass&domestic":int((q&(F["FIF Flag"].reindex(last.index)=="N")).sum())})
print(pd.DataFrame(rows).to_string(index=False))
# gaps & spikes for funds ever passing (2021-2025)
el = w[w.FundCode.isin(bs)]
gap_n=0; spk=0; spk_f=0; flat_f=0; nf=0
for fc, gg in el.groupby("FundCode"):
    if len(gg)<252: continue
    nf+=1
    bd = np.busday_count(gg.NAVDate.values[:-1].astype("datetime64[D]"), gg.NAVDate.values[1:].astype("datetime64[D]"))
    gap_n += int((bd>10).sum())
    _, fl = _detect_and_fix_spikes(gg["NAV"].to_numpy(dtype=float)); k=int(np.sum(fl)); spk+=k; spk_f+=int(k>0)
    flat_f += int((np.diff(gg["NAV"].to_numpy())==0).mean()>0.2)
print(f"eligible F with >=252 pts 2021-25: {nf} | gaps>10bd: {gap_n} | spikes flagged: {spk} in {spk_f} funds | funds with >20% zero-change days: {flat_f}")
# 2021 Q1 and 2026 hole check (count of funds reporting per month)
m = el.groupby(el.NAVDate.dt.to_period("M"))["FundCode"].nunique()
print("funds reporting per month (eligible): min", m.min(), "at", m.idxmin(), "| median", int(m.median()), "| 2021-01..03:", m.loc["2021-01":"2021-03"].tolist(), "| 2025-10..12:", m.loc["2025-10":"2025-12"].tolist())
# fee coverage
fee = pd.read_csv("base_data/SecFundFee.csv", dtype=str, encoding="utf-8-sig")
fee = fee[(fee["Complex Type Code"]=="FEEUH")&fee["Code"].isin(["FF","BF","SI","SO"])]
cov = fee[fee["Fund Code"].isin(bs)].groupby("Code")["Fund Code"].nunique()
print("fee coverage among snapshot-eligible F:", cov.to_dict(), "of", len(bs))
