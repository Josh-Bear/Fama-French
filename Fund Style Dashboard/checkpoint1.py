"""checkpoint1.py — Phase 1 Recheck (Data Ingestion & Filtering).

รัน: ./.venv/bin/python checkpoint1.py
ตรวจตาม "Unit test / Recheck" ของ Phase 1 ในแผน (715 / 680 / 368 + MSCI)
"""

from __future__ import annotations

import config
from data import fund_profile, msci_index, nav_loader


def main() -> None:
    ok = True

    print("=" * 64)
    print("Phase 1 Recheck — Data Ingestion & Filtering")
    print("=" * 64)

    # --- 1) FundProfile + filter ---
    fp = fund_profile.load_fund_profile()
    filt = fund_profile.filter_funds(fp)
    n = len(filt)
    policy = fund_profile._norm(filt[config.FUND_POLICY_COL]).value_counts().to_dict()
    dup = filt[config.FUND_CODE_COL].duplicated().sum()
    print(f"\n[1] กรองกอง: {n} (คาด {config.EXPECTED_FILTERED_FUNDS})  "
          f"policy={policy}  dupFundCode={dup}")
    ok &= _check("filtered == 715", n == config.EXPECTED_FILTERED_FUNDS)
    ok &= _check("E=600 F=77 O=38", policy.get("E") == 600 and policy.get("F") == 77 and policy.get("O") == 38)
    ok &= _check("no dup Fund Code", dup == 0)

    universe = fund_profile.fund_universe(filt)

    # --- 2) nav_history join ---
    print("\n[2] โหลด nav_history (chunked ~336MB) ...")
    nav = nav_loader.load_nav_history(universe)
    matched = nav[config.NAV_FUND_CODE_COL].nunique()
    print(f"    matched with nav = {matched} (คาด {config.EXPECTED_WITH_NAV})  "
          f"rows(dedup)={len(nav):,}")
    ok &= _check("matched == 680", matched == config.EXPECTED_WITH_NAV)

    # --- 3) threshold ---
    passed = nav_loader.funds_passing_threshold(nav)
    print(f"\n[3] ผ่าน threshold >{config.MIN_DATA_POINTS} จุด = {len(passed)} "
          f"(คาด {config.EXPECTED_PASS_THRESHOLD})")
    ok &= _check("pass threshold == 368", len(passed) == config.EXPECTED_PASS_THRESHOLD)

    pol_map = fund_profile.policy_map(filt)          # pipeline ใช้เฉพาะ APP_POLICY (ดู config)
    passed_e = [f for f in passed if pol_map.get(f) == config.APP_POLICY]
    print(f"    เฉพาะ policy {config.APP_POLICY} = {len(passed_e)} (คาด {config.EXPECTED_PASS_THRESHOLD_E})")
    ok &= _check(f"policy {config.APP_POLICY} == {config.EXPECTED_PASS_THRESHOLD_E}",
                 len(passed_e) == config.EXPECTED_PASS_THRESHOLD_E)

    navd = nav[config.NAV_DATE_COL]
    print(f"    NAVDate range: {navd.min():%Y-%m-%d} → {navd.max():%Y-%m-%d}")

    # --- 4) MSCI index ---
    cty = msci_index.load_country_index()
    sec = msci_index.load_sector_index()
    cty_r = msci_index.to_daily_return(cty)
    sec_r = msci_index.to_daily_return(sec)
    print(f"\n[4] MSCI country {cty.shape} sector {sec.shape}  "
          f"NaN(level)={int(cty.isna().sum().sum())}/{int(sec.isna().sum().sum())}")
    print(f"    date range {cty.index.min():%Y-%m-%d} → {cty.index.max():%Y-%m-%d}  "
          f"daily-return rows {len(cty_r)}")
    ok &= _check("country 18 cols", cty.shape[1] == 18)
    ok &= _check("sector 10 cols", sec.shape[1] == 10)
    ok &= _check("no NaN in MSCI levels", cty.isna().sum().sum() == 0 and sec.isna().sum().sum() == 0)

    print("\n" + ("✅ Phase 1 PASSED" if ok else "❌ Phase 1 FAILED"))
    if not ok:
        raise SystemExit(1)


def _check(label: str, cond: bool) -> bool:
    print(f"    {'✅' if cond else '❌'} {label}")
    return cond


if __name__ == "__main__":
    main()
