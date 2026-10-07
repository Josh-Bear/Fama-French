"""vol_forecast.py — EWMA + GARCH(1,1) volatility forecast (index-level) + walk-forward backtest.

Spec: VOL_FORECAST_PLAN.md (โดยเฉพาะ §0.1 ข้อสรุป 2026-09-07)
Target = annualized average-daily-vol ตลอด horizon (เทียบ realized ตรงหน่วย):
  forecast = √(mean ของ daily variance ทำนาย h=1..H) × √252
  realized = std(daily return ใน window, ddof=1) × √252   (สูตรเดียวกับ metrics.annualized_volatility)
"""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd

import config

_ANN = np.sqrt(config.TRADING_DAYS)   # √252


def realized_vol(returns) -> float:
    """ground truth ของ backtest — annualized std ของ daily return จริงใน window."""
    r = pd.Series(returns).dropna()
    if len(r) < 2:
        return np.nan
    return float(r.std(ddof=1) * _ANN)


def ewma_forecast(returns, lam: float | None = None, horizon: int | None = None) -> float:
    """annualized vol จาก EWMA daily variance ล่าสุด (σ²_t = λσ²_{t-1} + (1-λ)r²_{t-1}).

    EWMA ไม่มี mean-reversion -> h-step แบน -> avg daily variance ตลอด horizon = σ²_t (horizon ไม่กระทบค่า)
    """
    lam = config.EWMA_LAMBDA if lam is None else lam
    r = pd.Series(returns).dropna().to_numpy(dtype=float)
    if len(r) < 2:
        return np.nan
    var = float(np.var(r))              # seed ด้วย sample variance ของ training
    for x in r:
        var = lam * var + (1 - lam) * x * x
    if not np.isfinite(var) or var <= 0:
        return np.nan
    return float(np.sqrt(var) * _ANN)


def garch_forecast(returns, horizon: int | None = None) -> tuple[float, bool]:
    """(annualized vol, fallback_flag) — fit GARCH(1,1); ถ้า fit ไม่ผ่าน -> fallback EWMA.

    ทำนาย daily variance h=1..H (หน่วย %² เพราะ fit บน returns×100) แล้ว **เฉลี่ย** ก่อนหารกลับ 100²
    """
    from arch import arch_model

    horizon = config.VOL_FORECAST_HORIZON if horizon is None else horizon
    r = pd.Series(returns).dropna()
    if len(r) < 2:
        return np.nan, True
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            # dist="t" (Student-t): ผลตอบแทนดัชนีมี fat tail กว่า Normal -> ประมาณ vol ได้เหมาะกว่า
            am = arch_model(r.to_numpy(dtype=float) * 100.0, mean="Zero", vol="Garch", p=1, q=1,
                            dist=config.GARCH_DIST)
            res = am.fit(disp="off", show_warning=False)
            if getattr(res, "convergence_flag", 0) != 0:
                return ewma_forecast(r), True
            fc = res.forecast(horizon=horizon, reindex=False)
            var_path = np.asarray(fc.variance.values, dtype=float)[-1]   # (horizon,) หน่วย %²
            mean_daily_var = float(np.mean(var_path)) / (100.0 ** 2)      # หารกลับเป็นสัดส่วน
        if not np.isfinite(mean_daily_var) or mean_daily_var <= 0:
            return ewma_forecast(r), True
        return float(np.sqrt(mean_daily_var) * _ANN), False
    except Exception:  # noqa: BLE001 — fit ล้ม (series ผันผวนน้อย/สั้น) -> fallback ไม่ให้ crash ทั้ง pipeline
        return ewma_forecast(r), True


def walk_forward_backtest(returns, index_name: str, min_train: int | None = None,
                          step: int | None = None, horizon: int | None = None) -> pd.DataFrame:
    """expanding-window walk-forward — fit ที่ t, ทำนาย vol 21 วันถัดไป, เทียบ realized เมื่อครบจริง.

    เลื่อน t += step; รวมเฉพาะ window ที่มี horizon วันอนาคตครบ (window สุดท้ายที่ไม่ครบถูกข้าม)
    คืน DataFrame ยาว 1 แถว/window: index, window_start/end, ewma/garch forecast, garch_fallback, realized_vol
    """
    min_train = config.VOL_FORECAST_MIN_TRAIN if min_train is None else min_train
    step = config.VOL_FORECAST_STEP if step is None else step
    horizon = config.VOL_FORECAST_HORIZON if horizon is None else horizon

    r = pd.Series(returns).dropna()
    idx = r.index
    n = len(r)
    rows = []
    t = min_train
    while t + horizon <= n:
        train = r.iloc[:t]
        future = r.iloc[t:t + horizon]
        garch_f, fb = garch_forecast(train, horizon)
        rows.append({
            "index": index_name,
            "window_start": idx[t],                 # วันแรกของ forecast window
            "window_end": idx[t + horizon - 1],
            "ewma_forecast": ewma_forecast(train),
            "garch_forecast": garch_f,
            "garch_fallback": fb,
            "realized_vol": realized_vol(future),
        })
        t += step
    return pd.DataFrame(rows)


def evaluation_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """สรุป error ต่อโมเดล ต่อ index (+ รวม index='ALL'): RMSE/MAE บน vol, QLIKE บน variance.

    QLIKE (Patton 2011, robust) = mean( realized²/forecast² + log(forecast²) )
    """
    groups = [("ALL", df)] + list(df.groupby("index"))
    out = []
    for key, g in groups:
        for model in ["ewma", "garch"]:
            f = g[f"{model}_forecast"].to_numpy(dtype=float)
            a = g["realized_vol"].to_numpy(dtype=float)
            mask = np.isfinite(f) & np.isfinite(a) & (f > 0)
            f, a = f[mask], a[mask]
            if len(f) == 0:
                continue
            fv, av = f ** 2, a ** 2      # variance
            out.append({
                "index": key, "model": model, "n": int(len(f)),
                "RMSE": float(np.sqrt(np.mean((f - a) ** 2))),
                "MAE": float(np.mean(np.abs(f - a))),
                "QLIKE": float(np.mean(av / fv + np.log(fv))),
            })
    return pd.DataFrame(out)
