import sys; sys.path.insert(0,"."); sys.path.insert(0,".claude/quant_team/backtest")
import run_m017 as m, run_m010 as r10
E = m.build_env(0)
st = m.stream_idx(E["ctx15"], E["quals"], E["exs"], E["idx_tabs"], r10.RhoCache())
for rec in st["recs"]:
    lg = rec["log"]
    print(rec["t"].date(), "fb", rec["fallback"], "kept", rec["n_kept"], [(fc, X.replace("MSCI_",""), k) for fc,X,k in rec["chosen"].values()],
          "walk", lg["walked"], "str", len(lg["structural"]), "noel", len(lg["no_eligible"]), "occ", len(lg["occupied"]), "blk", len(lg["blocked"]), "a/b/c", lg["rej_a"], lg["rej_b"], lg["rej_c"])
print(E["idx_tabs"][0])
