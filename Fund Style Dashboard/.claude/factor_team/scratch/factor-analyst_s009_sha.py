import hashlib, sys
from pathlib import Path
R = Path("/Users/doyinratnavardhana/Fama French/Fund Style Dashboard")
T = R/".claude/factor_team"
pins = {
 "specs/S007_L4_group_factors_fund_alpha.md":"5dfddfc42f381679f423bdfb9ec7401222272450f3e5c1644ac46ab0a2ab2996",
 "specs/S008_L4_addendum_to_S007.md":"6483b4aaabe8bb3f48c6e6c95a97b28c6f6e78fd68f565d9ad48e3dbad0b3f66",
 "reviews/S008_spec_review.md":"a8ce7113dd0f2710c1551aa42765e2bf5e21e39116b1a601fa0b9a777f62908c",
 "data/panel_weekly.parquet":"95c16ee651d3a936788b7cb3c6372bbf5f1e84cb39daf5680343771dca24270b",
 "data/panel_monthly.parquet":"e8e8cb5d5f04fba9bb35558ef7c3d8195c656334119e56f82775cc1ae21ccaed",
 "data/factors_weekly.parquet":"115b87139d2bec0fd57a77a1593c46d36bb23f3f35f83236cdb07be642af47a8",
 "data/factors_monthly.parquet":"f7c4248b4fa889853024449e72ae8909cf1f8d3226a54eebc37448a2a485bb72",
 "data/factors_ext_weekly.parquet":"3105b6e7fe32ffd3648e8feac8dbd03a8db22b7e8eb245c5faf462b14da5e296",
 "data/universe.csv":"fdfb7830df78ce032465ac9d8cddc2c98f9aa86cfa0f3925fdb83026aa3f7252",
 "data/dup_pairs.csv":"b1f0f0c745947fa70803a4f40526c0a1967c72925be985a2bedc1057d8b8aef3",
 "data/factor_groups.csv":"42bf1cfb270721ae6112799ab795ebc4c91212e7584d5cdfee23b9b70b1b1731",
 "data/aum_weekly.parquet":"48c34c73ae22ebffc6112f93e03f729223a496297bb65c324b693b817a723d26",
 "runs/S003/factors_S003_weekly.parquet":"be3ceb2e34b0df1f1a3db27d59e1a103cf5f5a5ca38f2e87f7c812c1c53944ac",
 "runs/S003/fund_level.csv":"36b41161d6a13c1184a4052d9e799f660f431c2694dc57fafd747f8e695bf8cf",
 "runs/S003/grs_ports.csv":"d55011094898acdf6e0419c90a3b2713479451380cacc0bf950559c43b98ba19",
 "runs/S005/primary_index.csv":"5a94ab9b498bb107600938d37f665c7263d9f0a5973460159c09ae83a799275c",
 "runs/S005/fund_clusters.csv":"072cd97ade7e01a32edb9aaf5b949381d1500dcb1ed909558bee3a373e2fc0cb",
 "runs/S005/criteria_P4.json":"0db21831202f8ff2378923740074d2517be1a37563d5f09a64e103d8651cbfb2",
 "runs/S006/fund_level.csv":"2fc1d735f52669d1034707c5d9c0194b087e91aff5dbfb91b2fd59ac4f85f5d2",
 "runs/S006/resid_B_coef.csv":"71af654fc789a24d79999d96d7149e05e75007ac6e8f83d33bd0355d292eef0b",
 "runs/S006/run_meta.json":"3abb04b19c97223ed72d062a21216d3befc0e67805e3f60298a22e02603ec5ef",
}
bad=0
for k,v in pins.items():
    g=hashlib.sha256((T/k).read_bytes()).hexdigest()
    if g!=v: print("MISMATCH",k,g); bad+=1
for k,v in {"base_data/SecFundFee.csv":"94f0b7716a7979303ef6ba063746061d7e454c8e966731b567aa29316f0134cd","base_data/FundProfile.csv":"9516281426fc854c8f3a0833f119cad0ce581adb39450732e579084cb4cedfaf"}.items():
    g=hashlib.sha256((R/k).read_bytes()).hexdigest()
    if g!=v: print("MISMATCH",k,g); bad+=1
print("S009 spec sha: ", hashlib.sha256((T/"specs/S009_L4_addendum_to_S008.md").read_bytes()).hexdigest())
print("S009 review sha:", hashlib.sha256((T/"reviews/S009_spec_review.md").read_bytes()).hexdigest())
print("bad",bad, "n", len(pins)+2)
