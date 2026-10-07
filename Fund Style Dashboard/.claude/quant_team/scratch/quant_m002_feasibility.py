"""quant_m002_feasibility.py — read-only feasibility for M002-M005 (ไม่คำนวณ Sharpe/return ไปข้างหน้า).
เช็ค: suffix share class, ความครอบคลุมของ share_class_groups, ขนาด universe/กลุ่ม ณ t, ความถี่ NAV, จำนวนกองที่มี 12-1 ครบ."""
import os, sys, re
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backtest"))
import common  # noqa
import numpy as np, pandas as pd

nav = common.load_nav()
codes = sorted(nav.FundCode.unique())
suf = pd.Series([c.rsplit("-", 1)[-1] if "-" in c else "(none)" for c in codes])
print("n codes", len(codes)); print("suffix top:", suf.value_counts().head(25).to_dict())
groups = common.load_groups()
print("groups csv funds", len(groups), "groups", len(set(groups.values())))
# base name by stripping known class suffixes
CLS = r"-(A|D|R|RA|RD|SSF|SSFX|RMF|TESG|ThaiESG|ThaiESGX|P|E|N|I|X|H|UH|AE|SSFE|C|M)$"
base = pd.Series({c: re.sub(CLS, "", c, flags=re.I) for c in codes})
multi = base.value_counts(); multi = multi[multi > 1]
print("inferred multi-class bases", len(multi), "funds in them", int(multi.sum()))
not_in_csv = [c for c in codes if base[c] in multi.index and c not in groups]
print("multi-class funds not in groups csv", len(not_in_csv), not_in_csv[:30])
cal = common.load_calendar()
qs = common.quarter_ends(cal, "2022-03-31", "2025-09-30")
for t in qs[::2] + [qs[-1]]:
    u = common.universe_at(nav, t)
    g = u.FundCode.map(lambda f: groups.get(f, f)).nunique()
    gb = u.FundCode.map(lambda f: groups.get(f, base[f])).nunique()
    sub = nav[(nav.NAVDate <= t) & (nav.FundCode.isin(u.FundCode))]
    # 12-1 coverage: NAV at <= t-365d exists within 10 days and at t-30d
    first = sub.groupby("FundCode").NAVDate.min()
    ok121 = (first <= t - pd.Timedelta(days=372)).sum()
    ok24 = (first <= t - pd.Timedelta(days=730)).sum()
    last = sub.groupby("FundCode").NAVDate.max()
    fresh10 = ((t - last).dt.days <= 10).sum()
    n252 = sub[sub.NAVDate > t - pd.Timedelta(days=365)].groupby("FundCode").NAVDate.nunique()
    print(t.date(), "U", len(u), "groups(csv)", g, "groups(csv+suffix)", gb, "hist>=372d", ok121,
          ">=730d", ok24, "fresh<=10d", fresh10, "navpts/yr median", int(n252.median()), "p10", int(n252.quantile(.1)))
