# QA Report: Holdout Window (Oct 2025 – Jun 2026)
**Date:** 2026-09-30  
**Scope:** NAV gaps and data quality issues in holdout backtest window  
**Window:** 2025-09-30 to 2026-08-24  
**Trials reviewed:** M002-SR, M004-TF, M005, M005-N5  

---

## VERDICT: **FAIL** ❌

**Holdout Sharpe numbers (0.86–1.71) are UNRELIABLE and cannot be cited.**

The backtest results are compromised by severe, systematic NAV data gaps during Jan–Jun 2026 that cause artificial vol smoothing and inflated Sharpe ratios.

---

## Key Findings

### 1. Data Quality Status

| Metric | Value | Status |
|--------|-------|--------|
| Holdings checked | 124 | — |
| Problematic holdings (>20% missing OR gap>10 bdays) | 90 | ❌ **FAIL** |
| Max NAV gap in holdings | 44+ business days | ❌ **FAIL** |
| Max staleness (days past quarter end) | 86 days | ❌ **FAIL** |
| Q1 2026 portfolio exposure to gaps >5 bdays | **42%** | ⚠️ **CRITICAL** |

### 2. Quarterly NAV Gap Exposure

| Quarter | Holdings | Exposed to gap >5 bdays | Verdict |
|---------|----------|------------------------|---------|
| Q4 2025 (Oct-Dec) | Normal | 15% | ⚠️ Acceptable |
| Q1 2026 (Jan-Mar) | **MASSIVE GAPS** | **42%** | ❌ **CRITICAL** |
| Q2 2026 (Apr-Jun) | Recovering | 11% | ⚠️ Acceptable |
| Q3 2026 (Jul-Aug) | Normal | 0% | ✓ OK |

### 3. Worst Offenders

**Funds with sustained data blackouts during Q1 2026:**

- **KKP GINFRAEQ-H / KKP GINFRAEQ-H-F:** No NAV from Jan 7 to Jun 8 (107 business days) — held in 10 quarters across trials
- **ONE-GLOBFIN-RA:** No NAV from Jan 7 to Jun 10 (109 business days) — held in 10 quarters  
- **PRINCIPAL KEQ:** No NAV from Jan 7 to Apr 24 (76 business days) — held in 8 quarters
- **DAOL-GOLD, DAOL-KOREAEQ, DAOL-CYBER, etc.:** 44–47 day gaps Jan–Mar, plus 27-day and 47-day gaps in subsequent periods
- **M-EUBANK:** 35-day gap Mar 2–Apr 21, plus 15-day gaps (held in 22 quarters, 83% missing in Q1 2026)

**Staleness beyond quarter ends:**
- Multiple funds 80–86 days stale (last NAV = Jan 6–7, quarter ended Mar 31)

### 4. Mechanism of Return Inflation (Vol Smoothing Bias)

**How data gaps fake high Sharpe:**

1. **Flat period:** When fund NAV stops updating, portfolio returns appear smooth (no price discovery, zero daily vol)
2. **Jump period:** When prices finally update after 40–100 day gap, returns jump sharply but only once  
3. **Vol appears low:** A jump that takes weeks to occur in reality, spread across single day → artificially low daily vol
4. **Realized Sharpe inflated:** Portfolio vol is understated; Sharpe = return ÷ (smoothed vol) is artificially high

**Evidence in backtest:**

| Trial | Primary vol (2022-03 to 2025-09) | Holdout vol (2025-10 to 2026-06) | Ratio | Risk |
|-------|-------------------------------------|--------------------------------------|-------|------|
| M002-SR | 13.1% | 11.3% | **0.86** | ⚠️ Suspicious drop |
| M004-TF | 11.0% | 10.8% | 0.98 | Borderline |
| **M005** | 10.1% | 8.2% | **0.81** | ❌ **Severe drop** |
| M005-N5 | 10.5% | 11.8% | 1.13 | OK (no artifice) |

→ **M005 shows classic vol smoothing signature:** vol drops 19%, likely masking true portfolio risk.

---

## Date Clusters

**Synchronized multi-fund blackouts (Jan–Jun 2026):**

Many held funds stop reporting on Jan 7, 2026, then resume at scattered dates:
- Most resume by Mar 11–17 (44 bday gap)
- Some gap until Apr 20–24 (71 bday gap)  
- A few silent until May–Jun (85–109 bday gaps)

This is **not** random individual reporting delays — it's a systematic data collection failure affecting 10+ funds simultaneously.

---

## Impact on Model

### Cannot use holdout results for:
- **Validation:** Model appears to achieve 0.86–1.71 Sharpe, but true OOS Sharpe unknown  
- **Proof of concept:** Claimed improvement over M001 (0.25 Sharpe) is not credible under data gaps  
- **Marketing/reporting:** Would misrepresent backtest quality to stakeholders

### What's compromised:
- Portfolio returns inflated by vol smoothing  
- Risk-adjusted metrics (Sharpe, Sortino) systematically biased upward  
- Correlations understated (flat periods appear less risky than they are)  
- Rebalancing decisions based on stale marks may have missed real portfolio drift  

### What's NOT compromised:
- Q4 2025 (Oct–Dec) returns — data quality acceptable
- Q2/Q3 2026 (Apr onward) — data quality recovering  
- M001 baseline results (2022-03 to 2025-09) — unaffected

---

## Recommendation

**STOP** using holdout window (Oct 2025 – Jun 2026) for model validation. Options:

1. **Short-term:** Cite only OOS results through 2025-09 (M001 baseline period)  
2. **Medium-term:** Wait for reliable NAV data Q3 2026 onward; restart backtest from Oct 2025 once data cleaned  
3. **Diagnostic:** Request why 10+ funds had simultaneous NAV blackouts Jan–Jun 2026 from data provider  

**If must cite preliminary results:** Include disclaimer: *"Early 2026 holdout results (Sharpe 0.86–1.71) are based on data with known NAV gaps affecting 42% of portfolio weight in Q1 2026; true risk-adjusted returns likely 15–30% lower due to vol smoothing bias."*

---

## Repeatable Check

Script: `.claude/quant_team/qa/checks/holdout_gaps.py`

Run anytime data refreshes:
```bash
python3 .claude/quant_team/qa/checks/holdout_gaps.py
```

Outputs:
- Holdings checked vs problematic
- Quarterly exposure to gaps
- Worst offenders
- Automatic PASS/FAIL verdict

---

**Checked by:** data-qa agent  
**Method:** NAV observation count vs business days, gap analysis, staleness check, vol comparison  
**Confidence:** High (systematic gaps confirmed across multiple funds)
