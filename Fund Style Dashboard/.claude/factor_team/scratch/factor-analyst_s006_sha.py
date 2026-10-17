import hashlib, json, glob, os
R=".claude/factor_team/"
pins = {
"data/panel_weekly.parquet":"95c16ee651d3a936788b7cb3c6372bbf5f1e84cb39daf5680343771dca24270b",
"data/panel_monthly.parquet":"e8e8cb5d5f04fba9bb35558ef7c3d8195c656334119e56f82775cc1ae21ccaed",
"data/factors_weekly.parquet":"115b87139d2bec0fd57a77a1593c46d36bb23f3f35f83236cdb07be642af47a8",
"data/factors_monthly.parquet":"f7c4248b4fa889853024449e72ae8909cf1f8d3226a54eebc37448a2a485bb72",
"data/factors_ext_weekly.parquet":"3105b6e7fe32ffd3648e8feac8dbd03a8db22b7e8eb245c5faf462b14da5e296",
"runs/S003/factors_S003_weekly.parquet":"be3ceb2e34b0df1f1a3db27d59e1a103cf5f5a5ca38f2e87f7c812c1c53944ac",
"runs/S003/fund_level.csv":"36b41161d6a13c1184a4052d9e799f660f431c2694dc57fafd747f8e695bf8cf",
"runs/S003/grs_ports.csv":"d55011094898acdf6e0419c90a3b2713479451380cacc0bf950559c43b98ba19",
"runs/S003/regions.csv":"2fa3ce691c9dd66ef523e1baca228a635369d2971857797a05c105c1306e6866",
"runs/S005/primary_index.csv":"5a94ab9b498bb107600938d37f665c7263d9f0a5973460159c09ae83a799275c",
"runs/S005/fund_clusters.csv":"072cd97ade7e01a32edb9aaf5b949381d1500dcb1ed909558bee3a373e2fc0cb",
"runs/S005/criteria_P4.json":"0db21831202f8ff2378923740074d2517be1a37563d5f09a64e103d8651cbfb2",
"runs/S005/fund_level.csv":"1be9d49e70f385cd9a6e09d586f16ec3677622ee87b598826a34bebd69a89cf5",
"runs/S005/placebo_rule.json":"0460b5b2ff9721c3be97c134fd15c19d28c6596c0a5f6ad5dd08d842ec3f78dc",
"specs/S005_L2_addendum_to_S004.md":"c71ad963b64347d463c8d8a30fe55240b851be85d364f35a6ab121a7112f8468",
}
def sha(p):
    h=hashlib.sha256(open(p,'rb').read()).hexdigest(); return h
bad=0
for k,v in pins.items():
    h=sha(R+k); ok=h==v; bad+= (not ok); print("OK " if ok else "BAD", k, h[:12])
pre={"data/universe.csv":"fdfb7830","data/dup_pairs.csv":"b1f0f0c7","data/factor_groups.csv":"42bf1cfb"}
for k,v in pre.items():
    h=sha(R+k); ok=h.startswith(v); bad+=(not ok); print("OK " if ok else "BAD",k,h[:12])
for k,v in {"config.py":"711d5738ecf25fc0064e10134ae4cf5d8cfb0cee22d8dd5fbf0174fe925a7d66","cache/results.csv":"7c0ce137c4a8692e0136cefe1c4ddbad4cea42cca5e0af8aaa8bb36a05239cfc"}.items():
    h=sha(k); ok=h==v; bad+=(not ok); print("OK " if ok else "BAD",k,h[:12])
for k,v in {"runs/S003/run.py":"9f21e388","runs/S005/run.py":"c51e3d61"}.items():
    h=sha(R+k); ok=h.startswith(v); bad+=(not ok); print("OK " if ok else "BAD",k,h[:12])
m=json.load(open(R+"runs/S005/run_meta.json"))["lib_sha256"]
for k,v in m.items():
    h=sha(R+"lib/"+k); ok=h==v; bad+=(not ok); print("OK " if ok else "BAD","lib/"+k,h[:12])
print("extra lib:", sorted(set(os.path.basename(f) for f in glob.glob(R+"lib/*.py"))-set(m)))
print("BAD COUNT",bad)
