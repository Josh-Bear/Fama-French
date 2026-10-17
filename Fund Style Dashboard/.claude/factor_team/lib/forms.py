"""forms — ประกอบ 10 รูปแบบ (① 3 · ② 3 · ③ 3 · ④ 1) จาก R, F, ชุดกอง"""
import numpy as np
import pandas as pd

from external import line3
from fundff import build_line2
from hybrid import residual_pc, hybrid_factor
from nfactors import corr_eig, bai_ng_ic, ahn_horenstein, onatski_ed, parallel_analysis, combine_k
from pca import pca_fit, em_pca, factor_returns
from regress import CommonFactors
from samples import window_mask

FORM_NAMES = ["1a", "1b", "1c", "2a", "2b", "2c", "3a", "3b", "3c", "4a"]
LINE_OF = {"1": "pure stat", "2": "FF กองทุน", "3": "factor ภายนอก", "4": "factor ใหม่"}


class Form:
    def __init__(self, name, provider, plain, window="train", per_fund=False, meta=None):
        self.name = name
        self.provider = provider
        self.plain = plain  # DataFrame (T x K) ไม่ LOO (สำหรับตีความ/GRS/spanning)
        self.window = window
        self.per_fund = per_fund
        self.meta = meta or {}
        self.names = list(provider.names)
        self.K = provider.K


def nfactor_report(Z, N, T, kmax=10, n_perm=500, seed=20261015):
    eig = corr_eig(Z)
    ks = dict(
        IC_p1=bai_ng_ic(eig, N, T, kmax, "p1"),
        IC_p2=bai_ng_ic(eig, N, T, kmax, "p2"),
    )
    ks["ER"], ks["GR"] = ahn_horenstein(eig, kmax)
    ks["ED"] = onatski_ed(eig, kmax)
    ks["PA"] = parallel_analysis(Z, n_perm=n_perm, seed=seed)
    kstar = combine_k([ks["IC_p2"], ks["ER"], ks["ED"], ks["PA"]])
    return ks, kstar, eig


def build_line1(R, bal, base, kstar=None, seed=20261015, n_perm=500):
    """① a/b/c → dict(forms, nf, eig, parts) · R = excess weekly (T x N) ทุกกอง"""
    mtr = window_mask(R.index, "train")
    Xb = R.loc[mtr, bal].to_numpy(float)
    T, N = Xb.shape
    mu, sd = Xb.mean(0), Xb.std(0, ddof=0)
    Z = (Xb - mu) / sd
    ks, k_auto, eig = nfactor_report(Z, N, T, 10, n_perm, seed)
    k = k_auto if kstar is None else kstar
    Lam_a, mu_a, sd_a, _ = pca_fit(Xb, k, "corr")
    Lam_b, mu_b, sd_b, eig_b = pca_fit(Xb, k, "cov")
    fa = factor_returns(R[bal].to_numpy(float), Lam_a, sd_a)
    fb = factor_returns(R[bal].to_numpy(float), Lam_b, None)
    Xc = R.loc[mtr, base].to_numpy(float)
    Lam_c, mu_c, sd_c, it, conv = em_pca(Xc, k)
    fc = factor_returns(R[base].to_numpy(float), Lam_c, sd_c)
    cols = [f"PC{i + 1}" for i in range(k)]
    out = {}
    for nm, f in (("1a", fa), ("1b", fb), ("1c", fc)):
        df = pd.DataFrame(f, index=R.index, columns=cols)
        out[nm] = Form(nm, CommonFactors(df), df)
    parts = dict(Lam_a=Lam_a, sd_a=sd_a, mu_a=mu_a, Lam_b=Lam_b, Lam_c=Lam_c, sd_c=sd_c, em_iter=it, em_conv=conv,
                 bal=list(bal), base=list(base), eig=eig, eig_cov=eig_b)
    return dict(forms=out, nf=ks, k=k, k_auto=k_auto, eig=eig, parts=parts)


def build_line1_k(R, bal, ks):
    """①a ที่ k = 1..8 (บรรยาย) → dict k→DataFrame factor"""
    mtr = window_mask(R.index, "train")
    Xb = R.loc[mtr, bal].to_numpy(float)
    out = {}
    for k in ks:
        Lam, mu, sd, _ = pca_fit(Xb, k, "corr")
        out[k] = pd.DataFrame(factor_returns(R[bal].to_numpy(float), Lam, sd), index=R.index,
                              columns=[f"PC{i + 1}" for i in range(k)])
    return out


def build_line3(F):
    out = {}
    for nm in ("3a", "3b", "3c"):
        df = line3(F, nm)
        out[nm] = Form(nm, CommonFactors(df), df)
    return out


def build_line4(R, F3a, bal, kmax=5):
    mtr = window_mask(R.index, "train")
    rp = residual_pc(R, F3a, mtr, bal, kmax=kmax)
    g = hybrid_factor(R, F3a, rp["W"], rp["s"], rp["coef"], bal)
    df = pd.concat([F3a, g], axis=1)
    return dict(form=Form("4a", CommonFactors(df), df, meta=dict(k_res=rp["k_res"])), rp=rp, g=g)


def build_line2_forms(R, chars, loo=True, min_n=5):
    out = {}
    for v in ("a", "b", "c"):
        prov = build_line2(R, chars, v, loo=loo, min_n=min_n)
        out["2" + v] = Form("2" + v, prov, prov.plain(), window="train_c" if v == "c" else "train", per_fund=loo)
    return out


def train_characteristics(R, F, aum, pol, base):
    """คุณลักษณะรายกองจาก **train เท่านั้น** (ภูมิภาค · FX beta · ACT · ธง nonFX_eq · log AUM · σ) → dict"""
    from external import region_returns, REGION_IDX
    from fundff import single_index_r2, assign_region, nonfx_flags, regional_stats
    IDX = region_returns(F)
    mtr = window_mask(R.index, "train")
    EO = [c for c in base if pol[c] in ("E", "O")]
    r2 = single_index_r2(R, IDX, mtr, EO, cols=REGION_IDX + ["GOLDX", "TDEXX"])
    cm = pd.Series([pol[c] == "E" for c in EO], index=EO)
    reg = assign_region(r2[REGION_IDX], cm)
    fl = nonfx_flags(r2[REGION_IDX], r2["GOLDX"], r2["TDEXX"])
    fl.loc[~cm.values, "flag"] = False
    fl.loc[~cm.values, "reason"] = ""
    fx, act = regional_stats(R, IDX, reg["label_post"], r2[REGION_IDX], mtr, EO)
    mt = window_mask(aum.index, "train")
    a = aum.loc[mt]
    aumlog = np.log(a.where(a > 0)).median()
    sigma = R.loc[mtr, list(base)].std()
    return dict(IDX=IDX, r2=r2, reg=reg, flags=fl, fx=fx, act=act, aumlog=aumlog, sigma=sigma, EO=EO)


def make_ports(members, pol, tab):
    """พอร์ต GRS ของชุดสมาชิก (เกณฑ์กลุ่ม < 10 นับภายใน members)"""
    from external import REGION_IDX
    from fundff import assign_region, grs_portfolios
    members = list(members)
    EO = [c for c in members if pol[c] in ("E", "O")]
    cm = pd.Series([pol[c] == "E" for c in EO], index=EO)
    reg = assign_region(tab["r2"].loc[EO, REGION_IDX], cm)
    return grs_portfolios(members, pol, reg["label_post"], tab["fx"], tab["sigma"])


def make_chars(R, members, pol, tab, min_group=10):
    from external import REGION_IDX
    from fundff import line2_characteristics
    return line2_characteristics(R, members, pol, tab["r2"][REGION_IDX], tab["fx"], tab["act"],
                                 tab["flags"]["flag"], tab["aumlog"], min_group=min_group)
