"""run_m017cc.py — M017-CC (trial #35): M017-IDX + เพดานประเทศ 40% ของส่วนหุ้น + กฎเลือก ≤ 2 กอง/ประเทศ · specs/M017CC_country_cap.md
reuse run_m017 (build_env, stream_idx, plan_diag ...) · รันหลัง run_m017.py เสร็จ (ต้องมี M017-IDX ok ใน trials.csv)
(A) regression: country_rule=False + weigher ERC/cap25 = sleeves ของ M017-IDX (เส้นทางเดียวกัน) + Sharpe full M017-IDX = M017_results.csv + M012-QF-S/Trend25 ตรงค่าเดิม
รัน: PYTHONPATH=. ./.venv/bin/python .claude/quant_team/backtest/run_m017cc.py
"""
from __future__ import annotations

import json
import os
import sys
import time
import traceback

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if THIS_DIR not in sys.path:
    sys.path.insert(0, THIS_DIR)

import numpy as np
import pandas as pd

import common
import weighting as wt
import run_m010 as r10
import run_m011 as r11
import run_m012 as r12
import run_m017 as m17
import remeasure_real_rf as rr
import robust_offsets as ro

RES = common.RESULTS_DIR
SCRATCH = m17.SCRATCH
TRIALS_CSV = m17.TRIALS_CSV
NAME, N_TRIAL = "M017-CC", 35
FCAP, CCAP = 0.25, 0.40
KINDS = m17.KINDS
PHASE_B = False
CAPLOG = {}          # (offset, qi) -> dict


def joint_cap(w0: pd.Series, countries: dict, fcap=FCAP, ccap=CCAP, tol=1e-12, max_iter=500):
    """w0 รวม = 1 · คืน (w, residual_to_cash, n_iter). ส่วนเกินกระจายตามสัดส่วนให้กองที่ < fcap และประเทศ < ccap."""
    w = w0.astype(float).copy() / w0.sum()
    resid = 0.0
    it = 0
    for it in range(max_iter):
        excess = 0.0
        over = w > fcap + tol
        if over.any():
            excess += float((w[over] - fcap).sum())
            w[over] = fcap
        cs = w.groupby(pd.Series(countries)).sum()
        for c, s in cs.items():
            if s > ccap + tol:
                idx = [f for f in w.index if countries[f] == c]
                w[idx] = w[idx] * (ccap / s)
                excess += s - ccap
        if excess <= tol:
            break
        cs = w.groupby(pd.Series(countries)).sum()
        recv = [f for f in w.index if w[f] < fcap - tol and cs[countries[f]] < ccap - tol]
        if not recv:
            resid += excess
            break
        base = w[recv]
        add = excess * (base / base.sum()) if base.sum() > 0 else pd.Series(excess / len(recv), index=recv)
        w[recv] = w[recv] + add
    assert (w <= fcap + 1e-9).all()
    assert (w.groupby(pd.Series(countries)).sum() <= ccap + 1e-9).all()
    assert abs(w.sum() + resid - 1.0) < 1e-9
    return w, resid, it + 1


def make_weigher(offset):
    def weigher(funds, ctx, ex):
        w, _ = wt.risk_parity_weights(funds, ctx["wk"], ctx["vol_map"], method="erc")
        w = w / w.sum()
        cmap = {f: m17.country_of(ex, f) for f in funds}
        w2, resid, n = joint_cap(w, cmap)
        CAPLOG[(offset, ctx["qi"])] = {"resid_cash": resid, "n_iter": n, "n_countries": len(set(cmap.values())),
                                       "max_country_eq": float(w2.groupby(pd.Series(cmap)).sum().max())}
        return w2                       # รวม = 1 − resid (ส่วนที่เหลือ -> เงินสดใน add_resid_cash)
    return weigher


def add_resid_cash(plan):
    out = []
    for p in plan:
        w = dict(p["weights"])
        tot = sum(w.values())
        res = 1.0 - tot
        assert res > -1e-9
        if res > 1e-12:
            w["__CASH__"] = w.get("__CASH__", 0.0) + res
        out.append({**p, "weights": w})
    return out


def main():
    global PHASE_B
    t0 = time.time()
    txt = open(TRIALS_CSV, encoding="utf-8").read()
    assert any(l.startswith("M017-IDX,") and ",ok," in l for l in txt.splitlines()), "ต้องรัน M017-IDX ให้เสร็จก่อน"
    envs, P, S, ST = {}, {}, {}, {}
    reg_sl = True
    for k in ro.OFFSETS:
        E = m17.build_env(k)
        envs[k] = E
        st_idx = m17.stream_idx(E["ctx15"], E["quals"], E["exs"], E["idx_tabs"], r10.RhoCache())
        st_off = m17.stream_idx(E["ctx15"], E["quals"], E["exs"], E["idx_tabs"], r10.RhoCache(), False,
                                lambda f, c, e: m17.erc_cap25(f, c, e))
        reg_sl &= all(set(st_idx["sleeves"][q].index) == set(st_off["sleeves"][q].index) and
                      np.allclose(st_idx["sleeves"][q].sort_index().to_numpy(), st_off["sleeves"][q].sort_index().to_numpy(), atol=1e-12) for q in range(15))
        st_cc = m17.stream_idx(E["ctx15"], E["quals"], E["exs"], E["idx_tabs"], r10.RhoCache(), True, make_weigher(k))
        st_s = r12.stream(E["ctx15"], E["quals"], "S", {})
        ST[k] = {NAME: st_cc, "M017-IDX": st_idx, "M012-QF-S": st_s}
        P[k] = {NAME: add_resid_cash(r12.to_plan(st_cc, E["q15"], E["calendar"], E["acwi"])),
                "M017-IDX": r12.to_plan(st_idx, E["q15"], E["calendar"], E["acwi"]),
                "M012-QF-S": r12.to_plan(st_s, E["q15"], E["calendar"], E["acwi"]),
                "Trend25": r11.build_plan(E["ctx_old"], E["q15"], E["calendar"], E["acwi"], E["fd_dec"], {})[0]}
        for p in P[k][NAME]:
            assert abs(sum(p["weights"].values()) - 1.0) < 1e-9
        kinds = KINDS if k == 0 else ["full", "c0"]
        S[k] = {m: m17.sim(P[k][m], E, kinds) for m in P[k]}
        print(f"[off{k}] done ({time.time()-t0:.0f}s)", flush=True)
    E0, real = envs[0], envs[0]["real"]

    R17 = pd.read_csv(os.path.join(RES, "M017_results.csv")).set_index(["model", "fee"])
    O17 = pd.read_csv(os.path.join(RES, "M017_offsets.csv")).set_index(["model", "offset"])
    reg = {"sleeves_off_eq_M017": bool(reg_sl)}
    for m in ("M017-IDX", "M012-QF-S", "Trend25"):
        got = rr.metrics(S[0][m]["full"]["values"], real)["sharpe"]
        reg[m] = (got, float(R17.loc[(m, "full"), "sharpe"]))
    reg["offsets_M017"] = max(abs(ro.win_metrics(S[k]["M017-IDX"]["full"]["values"], real)["sharpe"] - float(O17.loc[("M017-IDX", k), "sharpe"])) for k in ro.OFFSETS)
    reg["ok"] = bool(reg_sl and all(abs(reg[m][0] - reg[m][1]) < 5e-7 for m in ("M017-IDX", "M012-QF-S", "Trend25")) and reg["offsets_M017"] < 5e-7)
    print("REGRESSION:", json.dumps(reg, default=str), flush=True)
    json.dump(reg, open(os.path.join(SCRATCH, "validator_m017cc_regression.json"), "w"), default=str)
    if not reg["ok"]:
        print("REGRESSION FAIL — หยุด (ไม่นับ trial)", flush=True)
        return 2
    PHASE_B = True

    names = [NAME, "M017-IDX", "Trend25", "M012-QF-S"]
    rows, MR = [], {}
    for m in names:
        for kind in KINDS:
            x = rr.metrics(S[0][m][kind]["values"], real)
            MR[(m, kind)] = x
            lo, hi = rr.boot_ci(x["r"], x["rfm"])
            yr = m17.yearly(x["r"])
            rows.append({"model": m, "fee": kind, "sharpe": x["sharpe"], "cagr": x["cagr"], "vol": x["vol"], "max_dd": x["max_dd"],
                         "cost_pct_yr": S[0][m][kind]["cost_bp_yr"] / 100.0, "turn_yr": S[0][m][kind]["turn_yr"],
                         "dsr35": rr.dsr_s(x["r"], x["rfm"], N_TRIAL), "ci_lo": lo, "ci_hi": hi,
                         "sharpe_2022": x["sharpe_2022"], "sharpe_2307_2512": x["sharpe_2307_2512"], "n_months": x["n_months"],
                         **{f"ret_{y}": yr.get(y, np.nan) for y in (2022, 2023, 2024, 2025)}})
    R = pd.DataFrame(rows)
    R.to_csv(os.path.join(RES, "M017CC_results.csv"), index=False)
    pr = []
    for other in ("Trend25", "M012-QF-S", "M017-IDX"):
        for kind in ("full", "nofront", "flat"):
            lo, hi, pt = r11.paired_real(MR[(NAME, kind)]["r"], MR[(other, kind)]["r"], MR[(NAME, kind)]["rfm"], "r")
            pr.append({"vs": other, "fee": kind, "d_sharpe": pt, "ci_lo": lo, "ci_hi": hi, "d_cagr": MR[(NAME, kind)]["cagr"] - MR[(other, kind)]["cagr"]})
    PR = pd.DataFrame(pr)
    PR.to_csv(os.path.join(RES, "M017CC_paired.csv"), index=False)
    orow = []
    for m in names:
        for k in ro.OFFSETS:
            w = ro.win_metrics(S[k][m]["full"]["values"], real)
            o = rr.metrics(S[k][m]["full"]["values"], real)
            orow.append({"model": m, "offset": k, "sharpe": w["sharpe"], "cagr": w["cagr"], "vol": w["vol"], "max_dd": w["max_dd"], "n_months": w["n_months"],
                         "cost_pct_yr": S[k][m]["full"]["cost_bp_yr"] / 100.0, "turn_yr": S[k][m]["full"]["turn_yr"],
                         "sharpe_origwin": o["sharpe"], "cagr_origwin": o["cagr"], "maxdd_origwin": o["max_dd"], "n_months_origwin": o["n_months"]})
    OF = pd.DataFrame(orow)
    OF.to_csv(os.path.join(RES, "M017CC_offsets.csv"), index=False)

    dgs = {}
    for k in ro.OFFSETS:
        d = m17.plan_diag(P[k][NAME], ST[k][NAME], envs[k])
        d["rej_country"] = [r["log"]["rej_country"] for r in ST[k][NAME]["recs"]]
        d["resid_cash_eq"] = [CAPLOG.get((k, r["qi"]), {}).get("resid_cash", 0.0) for r in ST[k][NAME]["recs"]]
        dgs[k] = d
    # เงินสดรวมของ plan = trend cash + ส่วน infeasible; trend cash = cash ของ M012-QF-S ในไตรมาสเดียวกัน (ใช้กฎ ACWI เดียวกัน)
    for k, d in dgs.items():
        d["trend_cash"] = [P[k]["M012-QF-S"][i]["weights"].get("__CASH__", 0.0) for i in range(len(d))]
        d["resid_cash_total"] = d["cash"] - d["trend_cash"]
        d["max_country_w_sleeve"] = d["max_country_w_total"] / (1.0 - d["trend_cash"])
    DG = dgs[0]
    DG.to_csv(os.path.join(RES, "M017CC_quarter_diag.csv"), index=False)
    pd.concat([d.assign(offset=k) for k, d in dgs.items()]).to_csv(os.path.join(RES, "M017CC_quarter_diag_offsets.csv"), index=False)
    wr = []
    for k in ro.OFFSETS:
        for en in S[k][NAME]["full"]["entries"]:
            for f, w in en["target"].items():
                if w > 1e-12:
                    wr.append({"offset": k, "t": en["t"].date(), "e": en["e"].date(), "FundCode": f, "weight": w})
    pd.DataFrame(wr).to_csv(os.path.join(RES, "M017CC_weights.csv"), index=False)
    pd.DataFrame({f"{m}_{kind}": S[0][m][kind]["values"] for m in names for kind in ("full", "c0")}).to_csv(os.path.join(RES, "M017CC_equity_curve.csv"))

    mm = MR[(NAME, "full")]
    verdict = "ผ่าน" if (mm["max_dd"] >= m17.DD_FLOOR and mm["cagr"] > m17.TARGET_CAGR) else "ไม่ผ่าน"
    out = {"R": R, "PR": PR, "OF": OF, "DG": DG, "dgs": dgs, "verdict": verdict, "reg": reg}
    write_md(out)
    append_trial(out)
    pd.set_option("display.width", 250)
    print(R.round(4).to_string()); print(PR.round(4).to_string()); print(OF.round(4).to_string())
    print(DG[["t", "fallback_B0", "n_funds", "picks", "rej_country", "rej_c_corr", "n_countries", "max_country", "max_country_w_sleeve", "resid_cash_eq", "resid_cash_total"]].to_string())
    print("verdict", verdict, f"DONE {time.time()-t0:.0f}s", flush=True)
    return 0


pc = m17.pc


def write_md(o):
    R, PR, OF, DG = o["R"], o["PR"], o["OF"], o["DG"]
    g = lambda m, k: R[(R.model == m) & (R.fee == k)].iloc[0]
    L = []
    A = L.append
    A("# M017-CC — M017-IDX + เพดานประเทศ 40% ของส่วนหุ้น — ผลวัด\n")
    A(f"รันเมื่อ {pd.Timestamp.now().isoformat()} · spec `specs/M017CC_country_cap.md` (ลงทะเบียนก่อนรัน) · **trial #35** · ทุกอย่างอื่น = M017-IDX · โค้ด `backtest/run_m017cc.py`\n")
    rg = o["reg"]
    A(f"**Regression (ผ่าน)**: ปิดกฎประเทศ → sleeves = M017-IDX ทุก offset ({rg['sleeves_off_eq_M017']}) · M017-IDX full {rg['M017-IDX'][0]:.6f} (= `M017_results.csv`) · "
      f"M012-QF-S {rg['M012-QF-S'][0]:.6f} · Trend 25 {rg['Trend25'][0]:.6f} · offset M017-IDX max|Δ| {rg['offsets_M017']:.1e}\n")
    m = g(NAME, "full")
    A(f"## 1. ผลตามเกณฑ์ที่ล็อก (fee full): **{o['verdict']}**\n- CAGR {pc(m.cagr)} (> 9.09%: {'✓' if m.cagr > m17.TARGET_CAGR else '✗'}) · maxDD {pc(m.max_dd)} (≥ −20%: {'✓' if m.max_dd >= m17.DD_FLOOR else '✗'}) · Sharpe {m.sharpe:.3f}\n")
    A("## 2. ตารางหลัก (offset 0, 45 เดือน, rf จริง)\n")
    A("| โมเดล | fee | Sharpe | CAGR | vol | maxDD | ต้นทุน %/ปี | turnover/ปี | DSR@35 | CI95% | 2022 (เม.ย.–) | 2023 | 2024 | 2025 |")
    A("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    lab = {"full": "full", "nofront": "nofront", "flat": "flat 0.5%/ข้าง", "c0": "0%"}
    for mm in (NAME, "M017-IDX", "Trend25", "M012-QF-S"):
        for k in KINDS:
            x = g(mm, k)
            A(f"| {mm} | {lab[k]} | {x.sharpe:.3f} | {pc(x.cagr)} | {pc(x.vol)} | {pc(x.max_dd)} | {x.cost_pct_yr:.2f} | {x.turn_yr:.2f} | {x.dsr35:.3f} | "
              f"[{x.ci_lo:.2f}, {x.ci_hi:.2f}] | {pc(x.ret_2022,1)} | {pc(x.ret_2023,1)} | {pc(x.ret_2024,1)} | {pc(x.ret_2025,1)} |")
    A("\n## 3. Paired Δ (M017-CC − อ้างอิง)\n\n| เทียบ | fee | Δ Sharpe | CI95% | Δ CAGR |\n|---|---|---|---|---|")
    for r in PR.itertuples():
        A(f"| {r.vs} | {r.fee} | {r.d_sharpe:+.3f} | [{r.ci_lo:+.2f}, {r.ci_hi:+.2f}] | {r.d_cagr*100:+.2f} pt |")
    A("\n## 4. offset 0/1/2 (fee full · ช่วงร่วม 42 เดือน)\n\n| โมเดล | offset | Sharpe | CAGR | vol | maxDD | ต้นทุน %/ปี | ช่วงเต็มของ offset |\n|---|---|---|---|---|---|---|---|")
    for r in OF.itertuples():
        A(f"| {r.model} | {r.offset} | {r.sharpe:.3f} | {pc(r.cagr)} | {pc(r.vol)} | {pc(r.max_dd)} | {r.cost_pct_yr:.2f} | {r.sharpe_origwin:.3f} / {pc(r.cagr_origwin)} / {pc(r.maxdd_origwin)} |")
    A("\n## 5. กลไก (offset 0)\n")
    A(f"- ปัดเพราะกฎประเทศ รวม {int(DG.rej_country.sum())} ครั้ง · ไตรมาสที่มีเงินสดจาก infeasible {int((DG.resid_cash_total > 1e-9).sum())}/15 (สูงสุด {pc(DG.resid_cash_total.max(),1)} ของพอร์ตรวม) · "
      f"B0 {int(DG.fallback_B0.sum())} · ประเทศเฉลี่ย {DG.n_countries.mean():.2f} · ประเทศสูงสุด {pc(DG.max_country_w_sleeve.max(),1)} ของส่วนหุ้น (ไม่รวมเงินสด Trend)")
    for k, d in o["dgs"].items():
        A(f"- offset {k}: rej_country {int(d.rej_country.sum())} · ไตรมาสมีเงินสด infeasible {int((d.resid_cash_total > 1e-9).sum())} (สูงสุด {pc(d.resid_cash_total.max(),1)}) · B0 {int(d.fallback_B0.sum())}")
    A("\n| t | กองที่เลือก → ดัชนี | ปัด ประเทศ/corr | ประเทศ | ประเทศสูงสุด (ส่วนหุ้น) | เงินสด infeasible | B0 |\n|---|---|---|---|---|---|---|")
    for r in DG.itertuples():
        A(f"| {r.t} | {r.picks.replace('MSCI_', '') or '—'} | {r.rej_country}/{r.rej_c_corr} | {r.n_countries} | {str(r.max_country).replace('MSCI_', '')} {pc(r.max_country_w_sleeve,1)} | "
          f"{pc(r.resid_cash_total,1)} | {'B0' if r.fallback_B0 else '-'} |")
    A("\n## 6. ไฟล์\n`M017CC_results.csv`, `M017CC_paired.csv`, `M017CC_offsets.csv`, `M017CC_quarter_diag.csv`, `M017CC_quarter_diag_offsets.csv`, `M017CC_weights.csv`, `M017CC_equity_curve.csv`")
    open(os.path.join(RES, "M017CC_summary.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")


def append_line(vals):
    txt = open(TRIALS_CSV, encoding="utf-8", newline="").read()
    assert not any(l.startswith(f"{NAME},") and ",ok," in l for l in txt.splitlines())
    line = ",".join(str(v).replace(",", ";") for v in vals)
    with open(TRIALS_CSV, "a", encoding="utf-8", newline="") as f:
        if not txt.endswith("\n"):
            f.write("\r\n")
        f.write(line + "\r\n")


def append_trial(o):
    R, PR, DG = o["R"], o["PR"], o["DG"]
    m = R[(R.model == NAME) & (R.fee == "full")].iloc[0]
    sh = {k: R[(R.model == NAME) & (R.fee == k)].iloc[0].sharpe for k in KINDS}
    d = {v: PR[(PR.vs == v) & (PR.fee == "full")].iloc[0] for v in ("Trend25", "M012-QF-S", "M017-IDX")}
    of = o["OF"][o["OF"].model == NAME]
    crashed_before = any(l.startswith(f"{NAME},") for l in open(TRIALS_CSV, encoding="utf-8").read().splitlines())
    params = (f"{NAME}: M017-IDX + country = PIT country_primary (11 clean; any R2); fill skips candidate if >=2 chosen share its country (kept never force-sold); "
              f"ERC then joint cap fund 25% & country 40% of equity sleeve pro-rata to funds below both caps; infeasible remainder -> cash; B0 unchanged")
    note = (f"pass rule CAGR>9.09% & maxDD>=-20% -> {o['verdict']}; Sharpe 0%={sh['c0']:.3f} flat={sh['flat']:.3f} full={sh['full']:.3f} nofront={sh['nofront']:.3f}; "
            f"CAGR full {m.cagr:.4f}; CI95 ({m.ci_lo:.3f};{m.ci_hi:.3f}); "
            + "; ".join(f"dSharpe vs {v} {x.d_sharpe:+.3f} CI ({x.ci_lo:.3f};{x.ci_hi:.3f})" for v, x in d.items())
            + f"; offsets 0/1/2 common-42m Sharpe {'/'.join(f'{x:.3f}' for x in of.sharpe)}; rej_country {int(DG.rej_country.sum())}; "
            f"infeasible-cash quarters {int((DG.resid_cash_total > 1e-9).sum())} max {DG.resid_cash_total.max():.3f}; B0 {int(DG.fallback_B0.sum())}; n_months=45"
            + ("; rerun after crashed row (same locked spec; same trial #35)" if crashed_before else ""))
    vals = [NAME, pd.Timestamp.now().isoformat(), "M017CC_country_cap.md", params, "2022-03-31", "2025-12-31",
            "BOT policy rate daily (TH_POLICY_RATE.csv)", "real fees SecFundFee FEEUH (full; FeeData legacy=False)",
            round(m.sharpe, 4), round(m.cagr, 4), round(m.vol, 4), round(m.max_dd, 4), round(m.turn_yr, 4), N_TRIAL, round(m.dsr35, 4), "ok", note]
    print("trials backup ->", m17.backup_trials(), flush=True)
    append_line(vals)


if __name__ == "__main__":
    try:
        rc = main()
    except Exception:
        tb = traceback.format_exc()
        print(tb, flush=True)
        try:
            txt = open(TRIALS_CSV, encoding="utf-8", newline="").read()
            if PHASE_B and not any(l.startswith(f"{NAME},") for l in txt.splitlines()):
                m17.backup_trials()
                last = tb.strip().splitlines()[-1].replace(",", ";")[:200]
                append_line([NAME, pd.Timestamp.now().isoformat(), "M017CC_country_cap.md", f"{NAME} run crashed", "2022-03-31", "2025-12-31",
                             "BOT policy rate daily (TH_POLICY_RATE.csv)", "real fees SecFundFee FEEUH (full)", "", "", "", "", "", N_TRIAL, "", "crashed", last])
        except Exception:
            pass
        rc = 1
    sys.exit(rc)
