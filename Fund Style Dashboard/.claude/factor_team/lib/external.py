"""external — สาย ③ (factor ภายนอก) · FX = SHV_THB − RF_BOT (N1 · ค่าชั่วคราวข้อ 20) + ดัชนีอ้างอิง"""
import pandas as pd


def line3(F, variant):
    """F: factors raw (weekly หรือ monthly) → DataFrame factor ของ ③a/③b/③c (excess หรือส่วนต่าง)"""
    rf = F["RF_BOT"]
    out = pd.DataFrame(index=F.index)
    out["MKT"] = F["MSCI_ACWI"] - rf
    out["BOND"] = F["AGG_THB"] - rf
    out["GOLD"] = F["Gold_THB"] - rf
    out["FX"] = F["SHV_THB"] - rf
    if variant in ("3b", "3c"):
        out["EMDM"] = F["MSCI_EM"] - F["MSCI_WORLD"]
        out["USX"] = F["MSCI_USA"] - F["MSCI_ACWI"]
        out["TH"] = F["TDEX_THB"] - rf
        out["TERM"] = F["IEF_THB"] - F["SHV_THB"]
        out["IG"] = F["LQD_THB"] - F["IEF_THB"]
        out["HY"] = F["HYG_THB"] - F["LQD_THB"]
        out["EMD"] = F["EMB_THB"] - F["IEF_THB"]
    if variant == "3c":
        for c in ("Momentum", "Quality", "Value", "LowVol", "VIX_d", "US10Y_d", "Oil_Brent", "TH5Y_d"):
            out[c] = F[c]
    if variant not in ("3a", "3b", "3c"):
        raise KeyError(variant)
    return out


REGION_IDX = ["MSCI_USA", "MSCI_EUROPE", "MSCI_JAPAN", "MSCI_CHINA_ALL_SHARES", "MSCI_ASIA_EX_JAPAN",
              "MSCI_INDIA", "MSCI_VIETNAM", "MSCI_ACWI"]


def region_returns(F):
    """ดัชนีภูมิภาค 8 ตัว (−rf) + USDTHB + GOLDX/TDEXX (−rf) สำหรับสาย ②"""
    rf = F["RF_BOT"]
    out = pd.DataFrame(index=F.index)
    for c in REGION_IDX:
        out[c] = F[c] - rf
    out["USDTHB"] = F["USDTHB"]
    out["GOLDX"] = F["Gold_THB"] - rf
    out["TDEXX"] = F["TDEX_THB"] - rf
    return out


def reference_set(F):
    """ชุดอ้างอิง I ของข้อ 6 (ตีความ)"""
    rf = F["RF_BOT"]
    out = pd.DataFrame(index=F.index)
    for c in F.columns:
        if c.startswith("MSCI_"):
            out[c] = F[c] - rf
    for c in ("Momentum", "Quality", "Value", "LowVol"):
        out[c] = F[c]
    out["Gold_THB"] = F["Gold_THB"] - rf
    for c in ("AGG_THB", "IEF_THB", "SHV_THB", "LQD_THB", "HYG_THB", "EMB_THB"):
        out[c] = F[c] - rf
    out["USDTHB"] = F["USDTHB"]
    out["TDEX_THB"] = F["TDEX_THB"] - rf
    for c in ("Oil_Brent", "VIX_d", "US10Y_d", "TH5Y_d", "DTB3_d"):
        out[c] = F[c]
    return out
