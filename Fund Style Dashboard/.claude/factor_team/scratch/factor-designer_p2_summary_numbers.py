"""factor-designer: เลขคณิตสำหรับ reports/P2_summary.md
อ่านเฉพาะไฟล์ผลใน runs/S010/ + trials.csv (ไม่อ่านผลตอบแทน · ไม่ fit model · ไม่คำนวณ IC ใหม่)
"""
import json
from pathlib import Path

import pandas as pd

T = Path(__file__).resolve().parents[1]
R = T / "runs" / "S010"
out = {}

ts = pd.read_csv(R / "trial_summary.csv")
ic = ts[ts.trial.isin(["P2-B0", "P2-A2", "P2-C1", "P2-A1", "P2-A3", "P2-C2", "P2-D1", "P2-C3", "P2-D3", "P2-B2"])].copy()
ic["mde106"] = 1.06 * ic.s_sigmaIC
ic["mde138_bh97"] = 1.38 * ic.s_sigmaIC  # ตัวคูณ BH m 97 ของ S011 ข้อ 7.1
ic["absmean_lt_mde106"] = ic["mean"].abs() < ic.mde106
ic["mde106_gt_010"] = ic.mde106 > 0.10
out["per_trial"] = ic[["trial", "target", "mean", "s_sigmaIC", "ic_min80_realized_sim", "mde106", "mde138_bh97",
                       "absmean_lt_mde106", "mde106_gt_010", "t_dec", "h1", "h2", "lag1",
                       "ic_inS_mean", "ic_outS_mean", "ic_no_first_week_mean"]].round(4).to_dict("records")
out["mde106_range"] = [round(ic.mde106.min(), 4), round(ic.mde106.max(), 4)]
out["mde106_range_PCA3a"] = [round(ic[ic.target != "tot"].mde106.min(), 4), round(ic[ic.target != "tot"].mde106.max(), 4)]
out["mde106_range_tot"] = [round(ic[ic.target == "tot"].mde106.min(), 4), round(ic[ic.target == "tot"].mde106.max(), 4)]
out["mde138_range"] = [round(ic.mde138_bh97.min(), 4), round(ic.mde138_bh97.max(), 4)]
out["n_absmean_lt_mde"] = int(ic.absmean_lt_mde106.sum())
out["n_mde_gt_010"] = int(ic.mde106_gt_010.sum())
out["sim_col_equals_106s"] = bool(((ic.ic_min80_realized_sim - ic.mde106).abs() < 1e-9).all())

main = ts[ts.trial.str.match(r"P2-(A|B|C|D)")]
out["max_abs_t_main"] = main.loc[main.t_dec.abs().idxmax(), ["trial", "t_dec"]].tolist()
out["halves_both_registered_sign"] = main[(main.h1 > 0) & (main.h2 > 0)].trial.tolist()

rb = pd.read_csv(R / "robustness.csv")
out["robustness_cols"] = rb.columns.tolist()

exp = pd.read_csv(R / "expectations_vs_results.csv")
out["exp_match"] = int(exp.match.sum())
out["exp_mismatch"] = exp[~exp.match].n.tolist()

sc = pd.read_csv(R / "scorecard_wf.csv")
for c in ["median_R2_E", "median_R2oos_week_E", "median_R2_F", "median_R2oos_week_F", "median_R2_O",
          "median_R2oos_week_O", "mean_abs_alpha_annual", "corr_f1_MSCI_WORLD", "corr_f2_MSCI_CHINA_ALL_SHARES",
          "tucker_PC1", "tucker_PC2", "tucker_PC3", "tucker_PC4", "corr_beta_PC4", "corr_beta_FX"]:
    out[f"sc_{c}"] = [round(sc[c].min(), 3), round(sc[c].max(), 3)]
out["tucker_PC4_from_2022-12"] = round(sc[sc.t >= "2022-12-30"].tucker_PC4.min(), 3)
pdg = pd.read_csv(R / "pca_diag.csv")
out["eig_share_PC1_4"] = [round(pdg.eig_share_PC1_4.min(), 3), round(pdg.eig_share_PC1_4.max(), 3)]

ub = pd.read_csv(R / "universe_by_quarter.csv")
for c in ["S_t", "U_pre", "U_t", "N_eff", "gold_cut", "div_cut", "dup_cut", "gone_u0", "E", "F", "O"]:
    out[f"u_{c}"] = [int(ub[c].min()), int(ub[c].max())]
out["u_U_t_median"] = float(ub.U_t.median())
out["u_dropped_target_total"] = int(ub.dropped_target.sum())

dsr = pd.read_csv(R / "dsr_appendix.csv")
out["dsr_max"] = {c: [dsr.loc[dsr[c].idxmax(), "trial"], round(dsr[c].max(), 3)] for c in ["DSR_n20", "DSR_n122", "DSR_nA", "DSR_nB"]}

tr = pd.read_csv(T / "trials.csv")
out["trials_rows"] = len(tr)
out["trials_by_kind"] = tr.row_kind.value_counts().to_dict()
out["trials_counts"] = {"A": int(tr.counts_mode_A.sum()), "B": int(tr.counts_mode_B.sum()),
                        "n_combined_A": int(tr.n_combined.iloc[-1]), "n_combined_B": int(tr.n_combined_B.iloc[-1])}
rob_t = tr[(tr.row_kind == "robustness") & tr.t_dec.notna()]
out["max_abs_t_robustness"] = rob_t.loc[rob_t.t_dec.abs().idxmax(), ["trial_id", "t_dec"]].tolist()
out["min_p_robustness"] = tr[tr.row_kind == "robustness"].nsmallest(3, "p_two")[["trial_id", "p_two"]].values.tolist()

fam = json.loads((R / "family_m97_check.json").read_text())
out["family_check"] = {k: fam[k] for k in ["BH_reject_m97_J1eq1", "BH_reject_m97_J1real", "BY_reject_m97_J1eq1",
                                            "BH_reject_m17_J1eq1", "all_R5_p1_BH_reject", "C1R5_p", "C1R5_BH_threshold",
                                            "n_main", "n_conditional", "n_robustness", "n_ran"]}

(T / "scratch" / "factor-designer_p2_summary_numbers.json").write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str))
print(json.dumps(out, ensure_ascii=False, indent=1, default=str))
