import pandas as pd
p = pd.read_csv("base_data/FundProfile.csv", dtype=str, encoding="utf-8-sig"); p.columns=[c.strip() for c in p.columns]
print(len(p), p["Fund Code"].nunique())
print(p["Fund Policy"].value_counts().head(15))
f = p[p["Fund Policy"]=="F"].drop_duplicates("Fund Code")
print("F classes", len(f))
for c in ["Tax Type","FIF Flag","Fund Risk Level","Auto redeem fund","buy period flag","Fund Class","Project Retail Type","Plain / Complex Fund","Dividend_Flag","sell_settlement_day"]:
    print("==",c); print(f[c].value_counts(dropna=False).head(12).to_string())
print(f[["Fund Code","Fund Name EN","Tax Type","FIF Flag","Fund Risk Level","Auto redeem fund","buy period flag","Beg IPO Date","fst_lowbuy_val"]].sample(25,random_state=1).to_string())
