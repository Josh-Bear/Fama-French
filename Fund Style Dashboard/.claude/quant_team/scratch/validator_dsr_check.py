"""validator_dsr_check.py -- self-check เบาๆ หลังแก้บั๊ก unit ของ simulate.deflated_sharpe (2026-09-30)
รันแบบ read-only เท่านั้น ไม่แตะ trials.csv / backtest output ใดๆ

เช็ค 2 เรื่อง:
1. iid normal monthly returns ที่คุม sr_m (per-period Sharpe) ไว้ล่วงหน้า -> PSR(N=1, n_trials=1, ไม่มี deflation)
   ต้องใกล้เคียงสูตรวิเคราะห์ (analytic) ของ Bailey&Lopez de Prado กรณี skew=0, kurt=3 (normal):
       SE = sqrt(1/(n_eff-1))  ,  SR0 = 0 (เพราะ n_trials=1)  =>  PSR = Phi(sr_m * sqrt(n_eff-1))
   ถ้า n ใหญ่พอ (autocorrelation ของ iid noise ~0) n_eff ~= n จึงเทียบกับ Phi(sr_m*sqrt(n-1)) ได้ตรงๆ
2. DSR ต้องลดลงเมื่อ n_trials มากขึ้น (fix ค่า sr_m/returns เดียวกัน เพิ่มแค่ n_trials) -- สมบัติพื้นฐานของ
   deflation (ยิ่งค้นหาหลาย trial ยิ่งต้องการ evidence มากขึ้นก่อนเชื่อว่า Sharpe จริง > 0)
"""
import sys
import numpy as np

sys.path.insert(0, ".")
sys.path.insert(0, ".claude/quant_team/backtest")
import simulate  # noqa: E402
from scipy import stats  # noqa: E402


def check_analytic_psr():
    """z สูงเกินไป (CDF อิ่มตัวใกล้ 1) ทำให้ sampling noise ของ skew/kurtosis ต่อ 1 draw ขยับ CDF ได้มาก
    (derivative ของ Phi เล็กแต่ z ไวต่อ noise ของ SE) จึงตั้ง sr_m ระดับกลาง (CDF ~0.6-0.7 ที่ z ไม่สุดขั้ว)
    และเฉลี่ยหลาย draw เพื่อลด noise ของ skew/kurtosis estimate แทนการเทียบทีละ draw."""
    rng = np.random.default_rng(42)
    n = 200
    rf_annual = 0.0
    sr_m_target = 0.03  # per-period Sharpe ระดับกลาง (ไม่ annualize) -> z ~0.38-0.42, CDF ~0.65-0.66
    sd = 1.0
    n_reps = 300
    psrs = []
    n_effs = []
    for _ in range(n_reps):
        r = __import__("pandas").Series(rng.normal(sr_m_target, sd, size=n))
        psrs.append(simulate.deflated_sharpe(r, rf_annual, n_trials=1))  # N=1 -> ไม่มี deflation -> = PSR ธรรมดา
        n_effs.append(simulate.effective_n(r))
    mean_psr = float(np.mean(psrs))
    mean_n_eff = float(np.mean(n_effs))
    analytic = float(stats.norm.cdf(sr_m_target * np.sqrt(max(mean_n_eff - 1, 1e-9))))
    diff = abs(mean_psr - analytic)
    # หมายเหตุ: E[Phi(Z)] != Phi(E[Z]) (Jensen's inequality, Phi concave สำหรับ z>0 -- ผลจาก skew/kurt ต่อ draw
    # ที่มี sampling noise) ดังนั้น mean_psr ต่ำกว่า analytic เล็กน้อยอย่างเป็นระบบ เป็นเรื่องคาดไว้ได้ ไม่ใช่บั๊ก
    # -- tolerance กว้างกว่าปกติ (0.08) เพื่อรองรับผลนี้ ยังพอแยกบั๊ก unit (~sqrt12 เฟ้อ, diff จะ >> 0.3) ออกได้ชัด
    status = "OK" if diff < 0.08 else "FAIL"
    print(f"  mean over {n_reps} draws: PSR(code)={mean_psr:.4f}  "
          f"analytic~Phi(sr_m*sqrt(n_eff-1))={analytic:.4f}  mean n_eff={mean_n_eff:.1f}  diff={diff:.4f}  [{status}]")
    return status == "OK"


def check_monotonic_in_n_trials():
    rng = np.random.default_rng(7)
    n = 44  # เท่ากับ n_months ของ primary period จริงที่ทีมใช้
    r = __import__("pandas").Series(rng.normal(0.10 / np.sqrt(12), 0.13 / np.sqrt(12), size=n))
    dsr_prev = 2.0  # เริ่มจากค่าที่สูงเกิน 1 แน่ๆ เพื่อให้ loop แรกผ่าน
    ok_all = True
    for n_trials in (1, 2, 5, 10, 13, 50):
        dsr = simulate.deflated_sharpe(r, 0.02, n_trials)
        status = "OK" if dsr <= dsr_prev + 1e-9 else "FAIL"
        if status == "FAIL":
            ok_all = False
        print(f"  n_trials={n_trials:>3}: DSR={dsr:.4f}  (prev={dsr_prev:.4f})  [{status}]")
        dsr_prev = dsr
    return ok_all


def check_no_more_near_one_bug():
    """sanity เพิ่ม: ก่อนแก้บั๊ก, sr annualized (~0.6-0.85) เข้าสูตรตรงๆ ทำให้ DSR ~0.8-1.0 แทบทุกเคส (ดู
    reviews/M002-M005_review.md ตารางปัญหา #1) -- หลังแก้ sr_m ~0.15-0.25/เดือน ต้องให้ DSR อยู่ช่วงสมเหตุสมผล
    กว่ามาก (ไม่ใช่เกาะ 1.0 เกือบทุกตัวที่ sharpe annualized 0.5-0.85 เหมือนเดิม)"""
    rng = np.random.default_rng(1)
    n = 44
    sr_annual = 0.65
    sr_m = sr_annual / np.sqrt(12)
    r = __import__("pandas").Series(rng.normal(sr_m * 0.13 / np.sqrt(12) + 0.02 / 12, 0.13 / np.sqrt(12), size=n))
    dsr13 = simulate.deflated_sharpe(r, 0.02, 13)
    status = "OK" if dsr13 < 0.6 else "FAIL (ยังติดบั๊กเดิม -- DSR สูงเกินจริงที่ n_trials=13)"
    print(f"  sr_annual~{sr_annual}, n_trials=13: DSR={dsr13:.4f}  [{status}]")
    return dsr13 < 0.6


if __name__ == "__main__":
    print("[1] iid normal, sr_m คุมไว้ล่วงหน้า -> PSR(N=1) เทียบสูตรวิเคราะห์")
    ok1 = check_analytic_psr()
    print("\n[2] DSR ต้องไม่เพิ่มขึ้นเมื่อ n_trials มากขึ้น (fix returns เดิม)")
    ok2 = check_monotonic_in_n_trials()
    print("\n[3] sanity: annualized SR ~0.65 ไม่ควรให้ DSR สูงเกือบ 1 อีกต่อไป (บั๊กเดิม)")
    ok3 = check_no_more_near_one_bug()
    print(f"\n=== สรุป: [1] PSR-analytic {'PASS' if ok1 else 'FAIL'} | "
          f"[2] monotonic-in-n_trials {'PASS' if ok2 else 'FAIL'} | "
          f"[3] no-near-one-bug {'PASS' if ok3 else 'FAIL'} ===")
    if not (ok1 and ok2 and ok3):
        sys.exit(1)
