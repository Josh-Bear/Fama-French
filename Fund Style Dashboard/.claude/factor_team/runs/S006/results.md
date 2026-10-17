# S006 (L3 VIF-cleaned) — ผลรัน

รายงานตัวเลขอย่างเดียว · ไม่ตีความเกินตัวเลข · ระยะ 1 ไม่นับ trial

**ป้ายบังคับ:** (ก) ED ตรงกับแหล่งรอง ยังไม่เปิดต้นฉบับ Onatski 2010 [22, 47] · (ก2) PY ตรงต้นฉบับ JFEc 2024 [24] แต่คงป้าย (N−1)ρ̄²>1 + p_boot · (ข) ช่วง test 2024–2025 ถูกใช้เลือกรูปแบบตั้งแต่ L1 และตัดสิน P1(ข) ของ L2 — **ไม่ใช่หลักฐานนอกช่วงที่อิสระ** · (ค) ผลขึ้นกับค่าที่ยืนยัน 1–21 และค่าชั่วคราว 22–63 · (ง) เกณฑ์ L3 ออกแบบหลังเห็นผล L2 · (จ) แถว ⚠️ (ไม่มี Vietnam) = เกณฑ์เปลี่ยนหลังเห็นผล

**Q1a ไม่ใช่หลักฐานนอกช่วงใหม่:** drop-one ΔR²_oos วัดในช่วง test เดียวกับที่ P4 ถูกเลือก (`evidence_independent = False`) · pseudo-OOS ภายในช่วง train เป็น diagnostic (b̂ ของ e ประมาณจาก train เต็ม)

## 0. เงื่อนไขทางเทคนิค
- sha256 ข้อมูล + ไฟล์ pin ตรง · lib เดิม 12 ไฟล์ตรง S005 · regression S003/S005 ทุกไฟล์ตรงทุกบิต (`regression_S003_S005.json`) · ตัวเลข n กอง: {'base': 277, 'bal': 134, 'EVAL': 207, 'STAB': 191, 'PYTR': 148, 'PYTE': 206, 'E67': 67}
- span test (i)(ii)+อ้างอิง: max |Δ| = 4.55e-13 (เกณฑ์ 1e-10) · (iii) C closure max |Δ| = 1.15e-10 (เกณฑ์ 1e-8 บรรยาย)

```
test            base
i_Ball_vs_raw   1a      4.547474e-13
                1c      4.547474e-13
ii_Bprim_vs_L2  1a      2.273737e-13
                1c      2.273737e-13
iii_Cclosure    C0      1.145843e-10
ref_vs_S003     3a      2.273737e-13
ref_vs_S005     1a      4.547474e-13
                1c      2.273737e-13
```

## 1. A0 — VIF / κ (บรรยาย)

| base | window | set | n_cols | kappa | vif_max | n_ge5 |
|---|---|---|---|---|---|---|
| 1a | full_2021_2025 | C11 | 11 | 4.075 | 2.215 | 0 |
| 1a | full_2021_2025 | C11+S10 | 21 | 56.824 | 229.990 | 8 |
| 1a | full_2021_2025 | S10 | 10 | 8.225 | 8.218 | 1 |
| 1a | full_2021_2025 | f+C11+S10 | 25 | 65.099 | 280.131 | 12 |
| 1a | train | C11 | 11 | 4.260 | 2.700 | 0 |
| 1a | train | C11+S10 | 21 | 62.391 | 267.136 | 9 |
| 1a | train | S10 | 10 | 8.954 | 9.325 | 3 |
| 1a | train | f+C11+S10 | 25 | 75.001 | 355.586 | 15 |
| 1c | full_2021_2025 | C11 | 11 | 4.075 | 2.215 | 0 |
| 1c | full_2021_2025 | C11+S10 | 21 | 56.824 | 229.990 | 8 |
| 1c | full_2021_2025 | S10 | 10 | 8.225 | 8.218 | 1 |
| 1c | full_2021_2025 | f+C11+S10 | 25 | 65.186 | 280.134 | 11 |
| 1c | train | C11 | 11 | 4.260 | 2.700 | 0 |
| 1c | train | C11+S10 | 21 | 62.391 | 267.136 | 9 |
| 1c | train | S10 | 10 | 8.954 | 9.325 | 3 |
| 1c | train | f+C11+S10 | 25 | 74.980 | 354.896 | 14 |

## 2. A1 — ตัดแบบแอป (เกณฑ์หลัก: ดัชนีทุกตัว VIF < 5 · ชุด (ข) = เดิน log ต่อจนทุกคอลัมน์รวม f < 5)

**①a:** S_A (15) = ['MSCI_BRAZIL', 'MSCI_CHINA_A_SHARES', 'MSCI_CHINA_H_SHARES', 'MSCI_INDIA', 'MSCI_JAPAN', 'MSCI_KOREA', 'MSCI_ASEAN', 'MSCI_TAIWAN', 'MSCI_VIETNAM', 'MSCI_ACWI_CS', 'MSCI_ACWI_EN', 'MSCI_ACWI_HC', 'MSCI_ACWI_MT', 'MSCI_ACWI_TC', 'MSCI_ACWI_UT']

ชุด (ข) (15) = ['MSCI_BRAZIL', 'MSCI_CHINA_A_SHARES', 'MSCI_CHINA_H_SHARES', 'MSCI_INDIA', 'MSCI_JAPAN', 'MSCI_KOREA', 'MSCI_ASEAN', 'MSCI_TAIWAN', 'MSCI_VIETNAM', 'MSCI_ACWI_CS', 'MSCI_ACWI_EN', 'MSCI_ACWI_HC', 'MSCI_ACWI_MT', 'MSCI_ACWI_TC', 'MSCI_ACWI_UT']

ตัดตามลำดับ (main): MSCI_USA(355.6), MSCI_ACWI_IN(11.4), MSCI_ACWI_CD(9.0), MSCI_ACWI_IT(6.7), MSCI_ACWI_FN(6.5), MSCI_EUROPE(5.1)

หมายเหตุ STOP: 

**①c:** S_A (16) = ['MSCI_BRAZIL', 'MSCI_CHINA_A_SHARES', 'MSCI_CHINA_H_SHARES', 'MSCI_EUROPE', 'MSCI_INDIA', 'MSCI_JAPAN', 'MSCI_KOREA', 'MSCI_ASEAN', 'MSCI_TAIWAN', 'MSCI_VIETNAM', 'MSCI_ACWI_CS', 'MSCI_ACWI_EN', 'MSCI_ACWI_HC', 'MSCI_ACWI_MT', 'MSCI_ACWI_TC', 'MSCI_ACWI_UT']

ชุด (ข) (16) = ['MSCI_BRAZIL', 'MSCI_CHINA_A_SHARES', 'MSCI_CHINA_H_SHARES', 'MSCI_EUROPE', 'MSCI_INDIA', 'MSCI_JAPAN', 'MSCI_KOREA', 'MSCI_ASEAN', 'MSCI_TAIWAN', 'MSCI_VIETNAM', 'MSCI_ACWI_CS', 'MSCI_ACWI_EN', 'MSCI_ACWI_HC', 'MSCI_ACWI_MT', 'MSCI_ACWI_TC', 'MSCI_ACWI_UT']

ตัดตามลำดับ (main): MSCI_USA(354.9), MSCI_ACWI_IN(11.4), MSCI_ACWI_CD(9.3), MSCI_ACWI_IT(7.0), MSCI_ACWI_FN(6.4)

หมายเหตุ STOP: 

**A-mem (P4 อยู่ใน S_A):**

| index | in_S_A_1a | in_S_A_1c | in_S_A_b_1a | in_S_A_b_1c | Q1a_A_survives_both |
|---|---|---|---|---|---|
| MSCI_ACWI_HC | True | True | True | True | True |
| MSCI_ACWI_UT | True | True | True | True | True |
| MSCI_EUROPE | False | True | False | True | False |
| MSCI_INDIA | True | True | True | True | True |
| MSCI_JAPAN | True | True | True | True | True |
| MSCI_VIETNAM | True | True | True | True | True |
P4′ (ไม่มี Vietnam) ใน S_A: {'1a': 4, '1c': 5}

## 3. B — residualize
| base | col | vif | kappa |
|---|---|---|---|
| 1a | PC1 | 1 | 2.549 |
| 1a | PC2 | 1 | 2.549 |
| 1a | PC3 | 1 | 2.549 |
| 1a | PC4 | 1.000 | 2.549 |
| 1a | MSCI_ACWI_HC | 2.120 | 2.549 |
| 1a | MSCI_ACWI_UT | 1.613 | 2.549 |
| 1a | MSCI_EUROPE | 1.295 | 2.549 |
| 1a | MSCI_INDIA | 1.124 | 2.549 |
| 1a | MSCI_JAPAN | 1.024 | 2.549 |
| 1a | MSCI_VIETNAM | 1.215 | 2.549 |
| 1c | PC1 | 1.000 | 2.411 |
| 1c | PC2 | 1.000 | 2.411 |
| 1c | PC3 | 1.000 | 2.411 |
| 1c | PC4 | 1.000 | 2.411 |
| 1c | MSCI_ACWI_HC | 1.904 | 2.411 |
| 1c | MSCI_ACWI_UT | 1.586 | 2.411 |
| 1c | MSCI_EUROPE | 1.279 | 2.411 |
| 1c | MSCI_INDIA | 1.133 | 2.411 |
| 1c | MSCI_JAPAN | 1.047 | 2.411 |
| 1c | MSCI_VIETNAM | 1.420 | 2.411 |

| base | index | r2_train | max_abs_corr_test_e_f | max_abs_corr_train_e_e | max_abs_corr_test_e_e |
|---|---|---|---|---|---|
| 1a | MSCI_ACWI_HC | 0.452 | 0.276 | 0.613 | 0.458 |
| 1a | MSCI_ACWI_UT | 0.347 | 0.254 | 0.613 | 0.344 |
| 1a | MSCI_EUROPE | 0.658 | 0.311 | 0.341 | 0.458 |
| 1a | MSCI_INDIA | 0.690 | 0.548 | 0.235 | 0.430 |
| 1a | MSCI_JAPAN | 0.403 | 0.327 | 0.128 | 0.116 |
| 1a | MSCI_VIETNAM | 0.146 | 0.161 | 0.318 | 0.275 |
| 1c | MSCI_ACWI_HC | 0.423 | 0.270 | 0.596 | 0.489 |
| 1c | MSCI_ACWI_UT | 0.369 | 0.295 | 0.596 | 0.387 |
| 1c | MSCI_EUROPE | 0.595 | 0.366 | 0.286 | 0.489 |
| 1c | MSCI_INDIA | 0.537 | 0.345 | 0.292 | 0.286 |
| 1c | MSCI_JAPAN | 0.383 | 0.283 | 0.166 | 0.102 |
| 1c | MSCI_VIETNAM | 0.493 | 0.056 | 0.292 | 0.286 |

fallback B-all′ ใช้: {'1a': False, '1c': False}

## 4. C — ลำดับชั้น
placebo: {"26": 0, "52": 0} · best score รอบแรก {"26": 6.892, "52": 6.586} · τ=0.0000 (placebo เลือก 0 → τ = 0)

บล็อกที่เลือก: ['MSCI_ACWI_CD']

| round | candidate | score | second | second_score | tau | action | n_selected |
|---|---|---|---|---|---|---|---|
| 1 | MSCI_ACWI_CD | -2.098 | MSCI_USA | -0.408 | 0 | added | 1 |
| 2 | MSCI_USA | 0.211 | MSCI_ASIA_EX_JAPAN | 1.634 | 0 | stop_tau | 1 |

## 5. ตารางคะแนน (EVAL 207 · E / ALL) — ทุกแถว R1–R12 + อ้างอิง

| row | label | policy | n | p_regressors_max | adjr2_med | adjr2_iqr | r2oos_med | r2oos_iqr | r2gap_med | mean_abs_alpha_pct | bic_med | med_d_adj_r2 | med_d_r2_oos | med_d_bic | bh_reject |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ref_base_1a | ฐาน ①a | ALL | 207 | 9 | 0.734 | 0.216 | 0.611 | 0.285 | 0.128 | 4.456 | -1295.095 | – | – | – | 0 |
| ref_base_1a | ฐาน ①a | E | 175 | 9 | 0.751 | 0.187 | 0.618 | 0.306 | 0.125 | 4.659 | -1277.222 | – | – | – | 0 |
| ref_base_1a | ฐาน ①a | F | 18 | 9 | 0.689 | 0.224 | 0.540 | 0.451 | 0.111 | 1.575 | -1708.562 | – | – | – | 0 |
| ref_base_1a | ฐาน ①a | O | 14 | 9 | 0.308 | 0.510 | 0.177 | 0.527 | 0.183 | 5.621 | -1282.937 | – | – | – | 0 |
| ref_L2_1a | L2-1 | ALL | 207 | 11 | 0.781 | 0.146 | 0.648 | 0.241 | 0.115 | 4.479 | -1318.680 | 0.009 | 0.011 | 1.765 | 2 |
| ref_L2_1a | L2-1 | E | 175 | 11 | 0.796 | 0.127 | 0.687 | 0.228 | 0.103 | 4.678 | -1305.164 | 0.011 | 0.027 | -0.969 | 1 |
| ref_L2_1a | L2-1 | F | 18 | 11 | 0.691 | 0.224 | 0.535 | 0.472 | 0.130 | 1.686 | -1699.502 | 0.001 | -0.005 | 7.477 | 1 |
| ref_L2_1a | L2-1 | O | 14 | 11 | 0.349 | 0.488 | 0.240 | 0.560 | 0.210 | 5.587 | -1283.847 | 0.013 | -0.016 | 5.169 | 0 |
| ref_base_1c | ฐาน ①c | ALL | 207 | 9 | 0.722 | 0.253 | 0.590 | 0.310 | 0.134 | 4.695 | -1297.672 | – | – | – | 2 |
| ref_base_1c | ฐาน ①c | E | 175 | 9 | 0.754 | 0.232 | 0.635 | 0.306 | 0.124 | 4.926 | -1281.516 | – | – | – | 0 |
| ref_base_1c | ฐาน ①c | F | 18 | 9 | 0.577 | 0.213 | 0.374 | 0.342 | 0.189 | 2.131 | -1667.548 | – | – | – | 2 |
| ref_base_1c | ฐาน ①c | O | 14 | 9 | 0.572 | 0.360 | 0.436 | 0.250 | 0.168 | 5.099 | -1327.341 | – | – | – | 0 |
| ref_L2_1c | L2-3 | ALL | 207 | 11 | 0.783 | 0.162 | 0.671 | 0.276 | 0.110 | 4.666 | -1329.966 | 0.011 | 0.007 | -0.729 | 2 |
| ref_L2_1c | L2-3 | E | 175 | 11 | 0.804 | 0.119 | 0.703 | 0.209 | 0.094 | 4.836 | -1306.437 | 0.012 | 0.015 | -1.739 | 0 |
| ref_L2_1c | L2-3 | F | 18 | 11 | 0.603 | 0.197 | 0.373 | 0.312 | 0.200 | 2.389 | -1659.817 | 0.002 | -0.009 | 7.334 | 2 |
| ref_L2_1c | L2-3 | O | 14 | 11 | 0.590 | 0.314 | 0.431 | 0.186 | 0.204 | 5.469 | -1321.597 | -0.000 | -0.012 | 7.953 | 0 |
| ref_3a | ③a (= C0) | ALL | 207 | 9 | 0.486 | 0.309 | 0.347 | 0.461 | 0.133 | 9.220 | -1202.571 | – | – | – | 5 |
| ref_3a | ③a (= C0) | E | 175 | 9 | 0.469 | 0.290 | 0.326 | 0.475 | 0.128 | 10.401 | -1167.351 | – | – | – | 3 |
| ref_3a | ③a (= C0) | F | 18 | 9 | 0.595 | 0.351 | 0.441 | 0.431 | 0.110 | 2.136 | -1662.389 | – | – | – | 2 |
| ref_3a | ③a (= C0) | O | 14 | 9 | 0.632 | 0.131 | 0.417 | 0.100 | 0.242 | 3.570 | -1286.982 | – | – | – | 0 |
| R1 | A-prim@1a | ALL | 207 | 11 | 0.774 | 0.160 | 0.650 | 0.252 | 0.122 | 4.528 | -1317.674 | 0.007 | 0.010 | 2.590 | 0 |
| R1 | A-prim@1a | E | 175 | 11 | 0.798 | 0.139 | 0.665 | 0.235 | 0.111 | 4.749 | -1296.557 | 0.007 | 0.012 | 1.820 | 0 |
| R1 | A-prim@1a | F | 18 | 11 | 0.688 | 0.231 | 0.549 | 0.450 | 0.127 | 1.624 | -1704.222 | 0.001 | -0.008 | 7.624 | 0 |
| R1 | A-prim@1a | O | 14 | 11 | 0.355 | 0.477 | 0.232 | 0.593 | 0.198 | 5.501 | -1283.058 | 0.026 | 0.008 | 2.486 | 0 |
| R2 | B-all@1a | ALL | 207 | 21 | 0.795 | 0.152 | 0.641 | 0.311 | 0.172 | 4.612 | -1282.884 | 0.030 | 0.010 | 26.341 | 4 |
| R2 | B-all@1a | E | 175 | 21 | 0.819 | 0.131 | 0.668 | 0.258 | 0.162 | 4.805 | -1274.839 | 0.038 | 0.010 | 22.863 | 2 |
| R2 | B-all@1a | F | 18 | 21 | 0.726 | 0.250 | 0.473 | 0.472 | 0.249 | 1.601 | -1660.004 | 0.016 | -0.036 | 40.553 | 2 |
| R2 | B-all@1a | O | 14 | 21 | 0.368 | 0.521 | 0.233 | 0.479 | 0.219 | 6.064 | -1242.812 | 0.011 | 0.021 | 42.683 | 0 |
| R3 | B-prim@1a | ALL | 207 | 11 | 0.769 | 0.183 | 0.646 | 0.268 | 0.116 | 4.569 | -1309.220 | 0 | 0 | 0 | 0 |
| R3 | B-prim@1a | E | 175 | 11 | 0.788 | 0.149 | 0.662 | 0.246 | 0.103 | 4.792 | -1291.613 | 0 | 0 | 0 | 0 |
| R3 | B-prim@1a | F | 18 | 11 | 0.690 | 0.224 | 0.540 | 0.453 | 0.118 | 1.579 | -1704.845 | 0 | 0 | 0 | 0 |
| R3 | B-prim@1a | O | 14 | 11 | 0.308 | 0.510 | 0.177 | 0.527 | 0.183 | 5.621 | -1282.937 | 0 | 0 | 0 | 0 |
| R4 | B-all5@1a ⚠️ | ALL | 207 | 19 | 0.788 | 0.188 | 0.645 | 0.311 | 0.155 | 4.470 | -1284.166 | 0.027 | 0.014 | 22.518 | 3 |
| R4 | B-all5@1a ⚠️ | E | 175 | 19 | 0.810 | 0.150 | 0.673 | 0.256 | 0.148 | 4.632 | -1276.466 | 0.030 | 0.014 | 20.974 | 1 |
| R4 | B-all5@1a ⚠️ | F | 18 | 19 | 0.720 | 0.249 | 0.495 | 0.486 | 0.222 | 1.657 | -1668.342 | 0.020 | -0.021 | 33.581 | 2 |
| R4 | B-all5@1a ⚠️ | O | 14 | 19 | 0.365 | 0.516 | 0.257 | 0.468 | 0.201 | 6.070 | -1250.103 | 0.017 | 0.028 | 34.988 | 0 |
| R5 | B-prim5@1a ⚠️ | ALL | 207 | 11 | 0.763 | 0.200 | 0.640 | 0.282 | 0.108 | 4.439 | -1296.852 | 0 | 0 | 0 | 0 |
| R5 | B-prim5@1a ⚠️ | E | 175 | 11 | 0.776 | 0.162 | 0.662 | 0.251 | 0.100 | 4.639 | -1284.095 | 0 | 0 | 0 | 0 |
| R5 | B-prim5@1a ⚠️ | F | 18 | 11 | 0.690 | 0.224 | 0.540 | 0.453 | 0.118 | 1.579 | -1704.845 | 0 | 0 | 0 | 0 |
| R5 | B-prim5@1a ⚠️ | O | 14 | 11 | 0.308 | 0.510 | 0.177 | 0.527 | 0.183 | 5.621 | -1282.937 | 0 | 0 | 0 | 0 |
| R6 | A-prim@1c | ALL | 207 | 11 | 0.786 | 0.175 | 0.659 | 0.260 | 0.119 | 4.674 | -1329.816 | 0.009 | 0.005 | 0.351 | 5 |
| R6 | A-prim@1c | E | 175 | 11 | 0.803 | 0.129 | 0.704 | 0.203 | 0.105 | 4.868 | -1308.354 | 0.012 | 0.009 | -0.899 | 3 |
| R6 | A-prim@1c | F | 18 | 11 | 0.573 | 0.206 | 0.359 | 0.328 | 0.206 | 2.321 | -1658.991 | -0.001 | -0.011 | 8.369 | 2 |
| R6 | A-prim@1c | O | 14 | 11 | 0.608 | 0.305 | 0.418 | 0.212 | 0.206 | 5.273 | -1324.903 | 0.024 | -0.000 | 3.601 | 0 |
| R7 | B-all@1c | ALL | 207 | 21 | 0.797 | 0.176 | 0.648 | 0.283 | 0.166 | 4.656 | -1300.136 | 0.030 | 0.001 | 24.557 | 8 |
| R7 | B-all@1c | E | 175 | 21 | 0.828 | 0.140 | 0.687 | 0.240 | 0.159 | 4.869 | -1273.730 | 0.033 | 0.000 | 22.618 | 5 |
| R7 | B-all@1c | F | 18 | 21 | 0.615 | 0.221 | 0.330 | 0.445 | 0.356 | 2.215 | -1619.492 | 0.008 | -0.044 | 44.213 | 2 |
| R7 | B-all@1c | O | 14 | 21 | 0.671 | 0.325 | 0.579 | 0.233 | 0.172 | 5.135 | -1299.774 | 0.042 | 0.043 | 25.795 | 1 |
| R8 | B-prim@1c | ALL | 207 | 11 | 0.772 | 0.188 | 0.652 | 0.276 | 0.113 | 4.760 | -1316.472 | 0 | 0 | 0 | 2 |
| R8 | B-prim@1c | E | 175 | 11 | 0.790 | 0.163 | 0.691 | 0.231 | 0.100 | 5.002 | -1296.726 | 0 | 0 | 0 | 0 |
| R8 | B-prim@1c | F | 18 | 11 | 0.577 | 0.213 | 0.374 | 0.347 | 0.189 | 2.135 | -1663.853 | 0 | 0 | 0 | 2 |
| R8 | B-prim@1c | O | 14 | 11 | 0.572 | 0.360 | 0.436 | 0.250 | 0.168 | 5.099 | -1327.341 | 0 | 0 | 0 | 0 |
| R9 | B-all5@1c ⚠️ | ALL | 207 | 19 | 0.791 | 0.192 | 0.641 | 0.290 | 0.154 | 4.629 | -1297.137 | 0.026 | 0.006 | 21.668 | 8 |
| R9 | B-all5@1c ⚠️ | E | 175 | 19 | 0.814 | 0.155 | 0.667 | 0.227 | 0.137 | 4.832 | -1271.226 | 0.026 | 0.004 | 18.468 | 5 |
| R9 | B-all5@1c ⚠️ | F | 18 | 19 | 0.608 | 0.229 | 0.343 | 0.415 | 0.364 | 2.223 | -1627.786 | 0.007 | -0.038 | 36.340 | 2 |
| R9 | B-all5@1c ⚠️ | O | 14 | 19 | 0.611 | 0.321 | 0.469 | 0.238 | 0.199 | 5.179 | -1305.171 | 0.033 | 0.033 | 24.645 | 1 |
| R10 | B-prim5@1c ⚠️ | ALL | 207 | 11 | 0.762 | 0.212 | 0.649 | 0.280 | 0.106 | 4.647 | -1315.123 | 0 | 0 | 0 | 2 |
| R10 | B-prim5@1c ⚠️ | E | 175 | 11 | 0.782 | 0.170 | 0.689 | 0.235 | 0.097 | 4.869 | -1291.791 | 0 | 0 | 0 | 0 |
| R10 | B-prim5@1c ⚠️ | F | 18 | 11 | 0.577 | 0.213 | 0.374 | 0.347 | 0.189 | 2.135 | -1663.853 | 0 | 0 | 0 | 2 |
| R10 | B-prim5@1c ⚠️ | O | 14 | 11 | 0.572 | 0.360 | 0.436 | 0.250 | 0.168 | 5.099 | -1327.341 | 0 | 0 | 0 | 0 |
| R11 | C-blk | ALL | 207 | 11 | 0.526 | 0.296 | 0.328 | 0.444 | 0.221 | 6.517 | -1212.637 | 0.028 | -0.018 | -2.098 | 4 |
| R11 | C-blk | E | 175 | 11 | 0.517 | 0.295 | 0.281 | 0.467 | 0.219 | 7.242 | -1175.103 | 0.037 | -0.024 | -5.513 | 2 |
| R11 | C-blk | F | 18 | 11 | 0.595 | 0.341 | 0.424 | 0.449 | 0.135 | 1.968 | -1653.218 | 0.001 | -0.009 | 7.350 | 2 |
| R11 | C-blk | O | 14 | 11 | 0.633 | 0.111 | 0.409 | 0.095 | 0.261 | 3.306 | -1278.817 | -0.002 | -0.009 | 8.669 | 0 |
| R12 | C-prim | ALL | 207 | 13 | 0.723 | 0.154 | 0.577 | 0.281 | 0.154 | 5.447 | -1276.028 | 0.157 | 0.185 | -51.342 | 8 |
| R12 | C-prim | E | 175 | 13 | 0.729 | 0.151 | 0.580 | 0.257 | 0.154 | 5.951 | -1240.377 | 0.186 | 0.216 | -57.893 | 3 |
| R12 | C-prim | F | 18 | 13 | 0.625 | 0.309 | 0.436 | 0.443 | 0.193 | 1.994 | -1658.007 | 0.036 | 0.011 | -6.977 | 3 |
| R12 | C-prim | O | 14 | 13 | 0.729 | 0.194 | 0.473 | 0.461 | 0.228 | 3.591 | -1390.327 | 0.088 | 0.067 | -15.496 | 2 |

### 5.1 bootstrap CI ของ median Δ (E · CI สุ่มกองแบบอิสระภายใน policy — กองสัมพันธ์กัน → CI แคบกว่าจริง)
| row | label | stat | median | lo | hi |
|---|---|---|---|---|---|
| ref_L2_1a | L2-1 | median_d_adj_r2 | 0.011 | 0.006 | 0.019 |
| ref_L2_1a | L2-1 | median_d_r2_oos | 0.027 | 0.009 | 0.041 |
| ref_L2_1a | L2-1 | median_d_bic | -0.969 | -8.527 | 2.281 |
| ref_L2_1c | L2-3 | median_d_adj_r2 | 0.012 | 0.008 | 0.024 |
| ref_L2_1c | L2-3 | median_d_r2_oos | 0.015 | 0.005 | 0.026 |
| ref_L2_1c | L2-3 | median_d_bic | -1.739 | -10.179 | 0.720 |
| R1 | A-prim@1a | median_d_adj_r2 | 0.007 | 0.005 | 0.013 |
| R1 | A-prim@1a | median_d_r2_oos | 0.012 | 0.008 | 0.019 |
| R1 | A-prim@1a | median_d_bic | 1.820 | -2.660 | 3.863 |
| R2 | B-all@1a | median_d_adj_r2 | 0.038 | 0.028 | 0.045 |
| R2 | B-all@1a | median_d_r2_oos | 0.010 | 0.003 | 0.020 |
| R2 | B-all@1a | median_d_bic | 22.863 | 18.178 | 26.662 |
| R3 | B-prim@1a | median_d_adj_r2 | 0 | 0 | 0 |
| R3 | B-prim@1a | median_d_r2_oos | 0 | 0 | 0 |
| R3 | B-prim@1a | median_d_bic | 0 | 0 | 0 |
| R4 | B-all5@1a ⚠️ | median_d_adj_r2 | 0.030 | 0.024 | 0.037 |
| R4 | B-all5@1a ⚠️ | median_d_r2_oos | 0.014 | 0.007 | 0.025 |
| R4 | B-all5@1a ⚠️ | median_d_bic | 20.974 | 16.882 | 22.851 |
| R5 | B-prim5@1a ⚠️ | median_d_adj_r2 | 0 | 0 | 0 |
| R5 | B-prim5@1a ⚠️ | median_d_r2_oos | 0 | 0 | 0 |
| R5 | B-prim5@1a ⚠️ | median_d_bic | 0 | 0 | 0 |
| R6 | A-prim@1c | median_d_adj_r2 | 0.012 | 0.006 | 0.023 |
| R6 | A-prim@1c | median_d_r2_oos | 0.009 | 0.004 | 0.015 |
| R6 | A-prim@1c | median_d_bic | -0.899 | -9.198 | 1.140 |
| R7 | B-all@1c | median_d_adj_r2 | 0.033 | 0.025 | 0.042 |
| R7 | B-all@1c | median_d_r2_oos | 0.000 | -0.017 | 0.007 |
| R7 | B-all@1c | median_d_bic | 22.618 | 18.220 | 25.478 |
| R8 | B-prim@1c | median_d_adj_r2 | 0 | 0 | 0 |
| R8 | B-prim@1c | median_d_r2_oos | 0 | 0 | 0 |
| R8 | B-prim@1c | median_d_bic | 0 | 0 | 0 |
| R9 | B-all5@1c ⚠️ | median_d_adj_r2 | 0.026 | 0.022 | 0.034 |
| R9 | B-all5@1c ⚠️ | median_d_r2_oos | 0.004 | -0.005 | 0.009 |
| R9 | B-all5@1c ⚠️ | median_d_bic | 18.468 | 14.928 | 22.496 |
| R10 | B-prim5@1c ⚠️ | median_d_adj_r2 | 0 | 0 | 0 |
| R10 | B-prim5@1c ⚠️ | median_d_r2_oos | 0 | 0 | 0 |
| R10 | B-prim5@1c ⚠️ | median_d_bic | 0 | 0 | 0 |
| R11 | C-blk | median_d_adj_r2 | 0.037 | 0.028 | 0.047 |
| R11 | C-blk | median_d_r2_oos | -0.024 | -0.031 | -0.016 |
| R11 | C-blk | median_d_bic | -5.513 | -8.193 | -2.259 |
| R12 | C-prim | median_d_adj_r2 | 0.186 | 0.147 | 0.213 |
| R12 | C-prim | median_d_r2_oos | 0.216 | 0.163 | 0.271 |
| R12 | C-prim | median_d_bic | -57.893 | -74.415 | -49.853 |

### 5.2 ภาคผนวก E67 (E เท่านั้น)
| row | label | n | adjr2_med | r2oos_med | med_d_r2_oos | med_d_bic |
|---|---|---|---|---|---|---|
| ref_base_1a | ฐาน ①a | 67 | 0.734 | 0.602 | – | – |
| ref_L2_1a | L2-1 | 67 | 0.766 | 0.629 | 0.011 | 3.714 |
| ref_base_1c | ฐาน ①c | 67 | 0.751 | 0.635 | – | – |
| ref_L2_1c | L2-3 | 67 | 0.788 | 0.670 | 0.005 | 2.745 |
| ref_3a | ③a (= C0) | 67 | 0.427 | 0.292 | – | – |
| R1 | A-prim@1a | 67 | 0.771 | 0.632 | 0.011 | -0.264 |
| R2 | B-all@1a | 67 | 0.789 | 0.608 | 0.003 | 27.445 |
| R3 | B-prim@1a | 67 | 0.758 | 0.622 | 0 | 0 |
| R4 | B-all5@1a ⚠️ | 67 | 0.773 | 0.609 | 0.003 | 22.786 |
| R5 | B-prim5@1a ⚠️ | 67 | 0.740 | 0.617 | 0 | 0 |
| R6 | A-prim@1c | 67 | 0.787 | 0.669 | 0.007 | 0.377 |
| R7 | B-all@1c | 67 | 0.814 | 0.657 | -0.014 | 25.120 |
| R8 | B-prim@1c | 67 | 0.767 | 0.681 | 0 | 0 |
| R9 | B-all5@1c ⚠️ | 67 | 0.791 | 0.647 | -0.006 | 21.668 |
| R10 | B-prim5@1c ⚠️ | 67 | 0.752 | 0.671 | 0 | 0 |
| R11 | C-blk | 67 | 0.494 | 0.241 | -0.031 | -7.142 |
| R12 | C-prim | 67 | 0.727 | 0.569 | 0.220 | -56.195 |

### 5.3 GRS (17 พอร์ต · แถว factor ร่วม; แถวต่อกอง = N/A)
| row | label | window | N_ports | T_used | L | dof2 | F | p | mean_abs_alpha_pct |
|---|---|---|---|---|---|---|---|---|---|
| ref_base_1a | ฐาน ①a | train | 17 | 155 | 8 | 130 | 1.947 | 0.019 | 2.989 |
| ref_base_1a | ฐาน ①a | test | 17 | 104 | 8 | 79 | 1.485 | 0.122 | 4.006 |
| ref_base_1c | ฐาน ①c | train | 17 | 155 | 8 | 130 | 1.870 | 0.026 | 3.162 |
| ref_base_1c | ฐาน ①c | test | 17 | 104 | 8 | 79 | 1.432 | 0.144 | 4.546 |
| ref_3a | ③a (= C0) | train | 17 | 155 | 8 | 130 | 1.835 | 0.030 | 6.996 |
| ref_3a | ③a (= C0) | test | 17 | 104 | 8 | 79 | 0.888 | 0.590 | 6.568 |
| R2 | B-all@1a | train | 17 | 155 | 20 | 118 | 2.211 | 0.007 | 3.075 |
| R2 | B-all@1a | test | 17 | 104 | 20 | 67 | 1.476 | 0.131 | 4.176 |
| R4 | B-all5@1a ⚠️ | train | 17 | 155 | 18 | 120 | 2.031 | 0.014 | 2.925 |
| R4 | B-all5@1a ⚠️ | test | 17 | 104 | 18 | 69 | 1.460 | 0.137 | 3.860 |
| R7 | B-all@1c | train | 17 | 155 | 20 | 118 | 2.059 | 0.013 | 3.143 |
| R7 | B-all@1c | test | 17 | 104 | 20 | 67 | 1.245 | 0.256 | 4.271 |
| R9 | B-all5@1c ⚠️ | train | 17 | 155 | 18 | 120 | 1.823 | 0.032 | 3.143 |
| R9 | B-all5@1c ⚠️ | test | 17 | 104 | 18 | 69 | 1.272 | 0.237 | 4.490 |
| R11 | C-blk | train | 17 | 155 | 10 | 128 | 1.828 | 0.031 | 4.791 |
| R11 | C-blk | test | 17 | 104 | 10 | 77 | 0.891 | 0.586 | 6.423 |

### 5.4 PY + null bootstrap (ช่วง test หลัก) 
| row | label | J | p | p_boot | note |
|---|---|---|---|---|---|
| ref_base_1a | ฐาน ①a | -0.158 | 0.563 | 0.238 | (N−1)ρ̄²>1  |
| ref_L2_1a | L2-1 | -0.035 | 0.514 | 0.185 | (N−1)ρ̄²>1 regressor ต่างกันรายกอง — นอกกรอบทฤษฎี (บรรยาย) |
| ref_base_1c | ฐาน ①c | 0.674 | 0.250 | 0.073 | (N−1)ρ̄²>1  |
| ref_L2_1c | L2-3 | 0.395 | 0.346 | 0.092 | (N−1)ρ̄²>1 regressor ต่างกันรายกอง — นอกกรอบทฤษฎี (บรรยาย) |
| ref_3a | ③a (= C0) | 0.898 | 0.185 | 0.082 | (N−1)ρ̄²>1  |
| R1 | A-prim@1a | -0.001 | 0.500 | 0.180 | (N−1)ρ̄²>1 regressor ต่างกันรายกอง — นอกกรอบทฤษฎี (บรรยาย) |
| R2 | B-all@1a | 0.039 | 0.485 | 0.207 | (N−1)ρ̄²>1  |
| R3 | B-prim@1a | – | – | – | N/A — แถวต่อกองที่ K = 4 หรือ 5 (py_null_bootstrap ต้องการ K คงที่ · ห้ามแก้ lib เดิม · decisions_pre_run ข้อ 1) |
| R4 | B-all5@1a ⚠️ | 0.125 | 0.450 | 0.184 | (N−1)ρ̄²>1  |
| R5 | B-prim5@1a ⚠️ | – | – | – | N/A — แถวต่อกองที่ K = 4 หรือ 5 (py_null_bootstrap ต้องการ K คงที่ · ห้ามแก้ lib เดิม · decisions_pre_run ข้อ 1) |
| R6 | A-prim@1c | 0.648 | 0.259 | 0.072 | (N−1)ρ̄²>1 regressor ต่างกันรายกอง — นอกกรอบทฤษฎี (บรรยาย) |
| R7 | B-all@1c | 0.292 | 0.385 | 0.143 | (N−1)ρ̄²>1  |
| R8 | B-prim@1c | – | – | – | N/A — แถวต่อกองที่ K = 4 หรือ 5 (py_null_bootstrap ต้องการ K คงที่ · ห้ามแก้ lib เดิม · decisions_pre_run ข้อ 1) |
| R9 | B-all5@1c ⚠️ | 0.993 | 0.160 | 0.064 | (N−1)ρ̄²>1  |
| R10 | B-prim5@1c ⚠️ | – | – | – | N/A — แถวต่อกองที่ K = 4 หรือ 5 (py_null_bootstrap ต้องการ K คงที่ · ห้ามแก้ lib เดิม · decisions_pre_run ข้อ 1) |
| R11 | C-blk | 0.893 | 0.186 | 0.084 | (N−1)ρ̄²>1  |
| R12 | C-prim | 1.218 | 0.112 | 0.029 | (N−1)ρ̄²>1 regressor ต่างกันรายกอง — นอกกรอบทฤษฎี (บรรยาย) |

### 5.5 ความเสถียร r ดิบ H1/H2 (STAB 191 · E)
| row | label | policy | factor | n_funds | r_raw |
|---|---|---|---|---|---|
| ref_base_1a | ฐาน ①a | E | PC1 | 159 | 0.864 |
| ref_base_1a | ฐาน ①a | E | PC2 | 159 | 0.924 |
| ref_base_1a | ฐาน ①a | E | PC3 | 159 | 0.666 |
| ref_base_1a | ฐาน ①a | E | PC4 | 159 | 0.762 |
| ref_L2_1a | L2-1 | E | PC1 | 159 | 0.857 |
| ref_L2_1a | L2-1 | E | PC2 | 159 | 0.865 |
| ref_L2_1a | L2-1 | E | PC3 | 159 | 0.463 |
| ref_L2_1a | L2-1 | E | PC4 | 159 | 0.705 |
| ref_L2_1a | L2-1 | E | PRIM | 159 | 0.739 |
| ref_L2_1a | L2-1 | by_index | PRIM:MSCI_ACWI | 16 | 0.650 |
| ref_L2_1a | L2-1 | by_index | PRIM:MSCI_ACWI_CD | 37 | 0.252 |
| ref_L2_1a | L2-1 | by_index | PRIM:MSCI_ACWI_IT | 13 | 0.923 |
| ref_L2_1a | L2-1 | by_index | PRIM:MSCI_ASIA_EX_JAPAN | 13 | 0.857 |
| ref_L2_1a | L2-1 | by_index | PRIM:MSCI_CHINA_ALL_SHARES | 20 | 0.189 |
| ref_L2_1a | L2-1 | by_index | PRIM:MSCI_WORLD_EX_US | 10 | 0.939 |
| ref_base_1c | ฐาน ①c | E | PC1 | 159 | 0.896 |
| ref_base_1c | ฐาน ①c | E | PC2 | 159 | 0.917 |
| ref_base_1c | ฐาน ①c | E | PC3 | 159 | 0.699 |
| ref_base_1c | ฐาน ①c | E | PC4 | 159 | 0.703 |
| ref_L2_1c | L2-3 | E | PC1 | 159 | 0.888 |
| ref_L2_1c | L2-3 | E | PC2 | 159 | 0.843 |
| ref_L2_1c | L2-3 | E | PC3 | 159 | 0.573 |
| ref_L2_1c | L2-3 | E | PC4 | 159 | 0.449 |
| ref_L2_1c | L2-3 | E | PRIM | 159 | 0.737 |
| ref_L2_1c | L2-3 | by_index | PRIM:MSCI_ACWI | 16 | 0.604 |
| ref_L2_1c | L2-3 | by_index | PRIM:MSCI_ACWI_CD | 37 | 0.151 |
| ref_L2_1c | L2-3 | by_index | PRIM:MSCI_ACWI_IT | 13 | 0.872 |
| ref_L2_1c | L2-3 | by_index | PRIM:MSCI_ASIA_EX_JAPAN | 13 | 0.802 |
| ref_L2_1c | L2-3 | by_index | PRIM:MSCI_CHINA_ALL_SHARES | 20 | 0.254 |
| ref_L2_1c | L2-3 | by_index | PRIM:MSCI_WORLD_EX_US | 10 | 0.846 |
| ref_3a | ③a (= C0) | E | MKT | 159 | 0.640 |
| ref_3a | ③a (= C0) | E | BOND | 159 | 0.153 |
| ref_3a | ③a (= C0) | E | GOLD | 159 | 0.260 |
| ref_3a | ③a (= C0) | E | FX | 159 | 0.481 |
| R1 | A-prim@1a | E | PC1 | 159 | 0.882 |
| R1 | A-prim@1a | E | PC2 | 159 | 0.906 |
| R1 | A-prim@1a | E | PC3 | 159 | 0.611 |
| R1 | A-prim@1a | E | PC4 | 159 | 0.647 |
| R1 | A-prim@1a | E | PRIM | 159 | 0.737 |
| R1 | A-prim@1a | by_index | PRIM:MSCI_ACWI_MT | 49 | 0.555 |
| R1 | A-prim@1a | by_index | PRIM:MSCI_ACWI_TC | 43 | 0.687 |
| R1 | A-prim@1a | by_index | PRIM:MSCI_ASEAN | 10 | 0.943 |
| R1 | A-prim@1a | by_index | PRIM:MSCI_CHINA_A_SHARES | 13 | 0.595 |
| R1 | A-prim@1a | by_index | PRIM:MSCI_CHINA_H_SHARES | 20 | 0.452 |
| R1 | A-prim@1a | by_index | PRIM:MSCI_JAPAN | 11 | 0.719 |
| R1 | A-prim@1a | by_index | PRIM:MSCI_KOREA | 14 | 0.843 |
| R2 | B-all@1a | E | PC1 | 159 | 0.885 |
| R2 | B-all@1a | E | PC2 | 159 | 0.941 |
| R2 | B-all@1a | E | PC3 | 159 | 0.602 |
| R2 | B-all@1a | E | PC4 | 159 | 0.832 |
| R2 | B-all@1a | E | MSCI_ACWI_HC | 159 | 0.698 |
| R2 | B-all@1a | E | MSCI_ACWI_UT | 159 | 0.189 |
| R2 | B-all@1a | E | MSCI_EUROPE | 159 | 0.227 |
| R2 | B-all@1a | E | MSCI_INDIA | 159 | 0.534 |
| R2 | B-all@1a | E | MSCI_JAPAN | 159 | 0.459 |
| R2 | B-all@1a | E | MSCI_VIETNAM | 159 | 0.713 |
| R3 | B-prim@1a | E | PC1 | 159 | 0.877 |
| R3 | B-prim@1a | E | PC2 | 159 | 0.928 |
| R3 | B-prim@1a | E | PC3 | 159 | 0.660 |
| R3 | B-prim@1a | E | PC4 | 159 | 0.789 |
| R3 | B-prim@1a | E | PRIM | 159 | 0.539 |
| R4 | B-all5@1a ⚠️ | E | PC1 | 159 | 0.881 |
| R4 | B-all5@1a ⚠️ | E | PC2 | 159 | 0.942 |
| R4 | B-all5@1a ⚠️ | E | PC3 | 159 | 0.609 |
| R4 | B-all5@1a ⚠️ | E | PC4 | 159 | 0.828 |
| R4 | B-all5@1a ⚠️ | E | MSCI_ACWI_HC | 159 | 0.684 |
| R4 | B-all5@1a ⚠️ | E | MSCI_ACWI_UT | 159 | 0.164 |
| R4 | B-all5@1a ⚠️ | E | MSCI_EUROPE | 159 | 0.355 |
| R4 | B-all5@1a ⚠️ | E | MSCI_INDIA | 159 | 0.523 |
| R4 | B-all5@1a ⚠️ | E | MSCI_JAPAN | 159 | 0.460 |
| R5 | B-prim5@1a ⚠️ | E | PC1 | 159 | 0.871 |
| R5 | B-prim5@1a ⚠️ | E | PC2 | 159 | 0.928 |
| R5 | B-prim5@1a ⚠️ | E | PC3 | 159 | 0.654 |
| R5 | B-prim5@1a ⚠️ | E | PC4 | 159 | 0.784 |
| R5 | B-prim5@1a ⚠️ | E | PRIM | 159 | 0.662 |
| R6 | A-prim@1c | E | PC1 | 159 | 0.892 |
| R6 | A-prim@1c | E | PC2 | 159 | 0.901 |
| R6 | A-prim@1c | E | PC3 | 159 | 0.589 |
| R6 | A-prim@1c | E | PC4 | 159 | 0.608 |
| R6 | A-prim@1c | E | PRIM | 159 | 0.771 |
| R6 | A-prim@1c | by_index | PRIM:MSCI_ACWI_MT | 29 | 0.614 |
| R6 | A-prim@1c | by_index | PRIM:MSCI_ACWI_TC | 38 | 0.705 |
| R6 | A-prim@1c | by_index | PRIM:MSCI_ASEAN | 10 | 0.917 |
| R6 | A-prim@1c | by_index | PRIM:MSCI_CHINA_A_SHARES | 13 | 0.669 |
| R6 | A-prim@1c | by_index | PRIM:MSCI_CHINA_H_SHARES | 20 | 0.540 |
| R6 | A-prim@1c | by_index | PRIM:MSCI_EUROPE | 28 | 0.825 |
| R6 | A-prim@1c | by_index | PRIM:MSCI_JAPAN | 11 | 0.775 |
| R6 | A-prim@1c | by_index | PRIM:MSCI_KOREA | 12 | 0.878 |
| R7 | B-all@1c | E | PC1 | 159 | 0.891 |
| R7 | B-all@1c | E | PC2 | 159 | 0.941 |
| R7 | B-all@1c | E | PC3 | 159 | 0.757 |
| R7 | B-all@1c | E | PC4 | 159 | 0.632 |
| R7 | B-all@1c | E | MSCI_ACWI_HC | 159 | 0.768 |
| R7 | B-all@1c | E | MSCI_ACWI_UT | 159 | 0.170 |
| R7 | B-all@1c | E | MSCI_EUROPE | 159 | 0.477 |
| R7 | B-all@1c | E | MSCI_INDIA | 159 | 0.642 |
| R7 | B-all@1c | E | MSCI_JAPAN | 159 | 0.495 |
| R7 | B-all@1c | E | MSCI_VIETNAM | 159 | 0.602 |
| R8 | B-prim@1c | E | PC1 | 159 | 0.894 |
| R8 | B-prim@1c | E | PC2 | 159 | 0.923 |
| R8 | B-prim@1c | E | PC3 | 159 | 0.731 |
| R8 | B-prim@1c | E | PC4 | 159 | 0.713 |
| R8 | B-prim@1c | E | PRIM | 159 | 0.551 |
| R9 | B-all5@1c ⚠️ | E | PC1 | 159 | 0.887 |
| R9 | B-all5@1c ⚠️ | E | PC2 | 159 | 0.942 |
| R9 | B-all5@1c ⚠️ | E | PC3 | 159 | 0.761 |
| R9 | B-all5@1c ⚠️ | E | PC4 | 159 | 0.626 |
| R9 | B-all5@1c ⚠️ | E | MSCI_ACWI_HC | 159 | 0.718 |
| R9 | B-all5@1c ⚠️ | E | MSCI_ACWI_UT | 159 | 0.208 |
| R9 | B-all5@1c ⚠️ | E | MSCI_EUROPE | 159 | 0.465 |
| R9 | B-all5@1c ⚠️ | E | MSCI_INDIA | 159 | 0.688 |
| R9 | B-all5@1c ⚠️ | E | MSCI_JAPAN | 159 | 0.500 |
| R10 | B-prim5@1c ⚠️ | E | PC1 | 159 | 0.893 |
| R10 | B-prim5@1c ⚠️ | E | PC2 | 159 | 0.923 |
| R10 | B-prim5@1c ⚠️ | E | PC3 | 159 | 0.724 |
| R10 | B-prim5@1c ⚠️ | E | PC4 | 159 | 0.699 |
| R10 | B-prim5@1c ⚠️ | E | PRIM | 159 | 0.729 |
| R11 | C-blk | E | MKT | 159 | 0.602 |
| R11 | C-blk | E | BOND | 159 | 0.139 |
| R11 | C-blk | E | GOLD | 159 | 0.103 |
| R11 | C-blk | E | FX | 159 | 0.497 |
| R11 | C-blk | E | MSCI_ACWI_CD | 159 | 0.721 |
| R12 | C-prim | E | MKT | 159 | 0.883 |
| R12 | C-prim | E | BOND | 159 | 0.286 |
| R12 | C-prim | E | GOLD | 159 | -0.123 |
| R12 | C-prim | E | FX | 159 | 0.681 |
| R12 | C-prim | E | MSCI_ACWI_CD | 159 | 0.483 |
| R12 | C-prim | E | PRIM | 159 | 0.878 |
| R12 | C-prim | by_index | PRIM:ARKK | 14 | 0.616 |
| R12 | C-prim | by_index | PRIM:IBB | 11 | 0.757 |
| R12 | C-prim | by_index | PRIM:MSCI_ACWI_IT | 11 | 0.800 |
| R12 | C-prim | by_index | PRIM:MSCI_ASEAN | 13 | 0.942 |
| R12 | C-prim | by_index | PRIM:MSCI_ASIA_EX_JAPAN | 41 | 0.858 |
| R12 | C-prim | by_index | PRIM:MSCI_JAPAN | 11 | 0.881 |

### 5.6 rolling 104 (E · เฉลี่ยข้าม factor แยกรวม/ไม่รวม PRIM · corr หน้าต่างแรกกับสุดท้ายไม่ซ้อนกัน)

| row | label | mean_roll_median_exPRIM | mean_roll_median_inclPRIM | min_roll_min | mean_first_last_exPRIM | min_first_last |
|---|---|---|---|---|---|---|
| R1 | A-prim@1a | 0.887 | 0.891 | 0.674 | 0.693 | 0.487 |
| R10 | B-prim5@1c ⚠️ | 0.927 | 0.921 | 0.784 | 0.750 | 0.609 |
| R11 | C-blk | 0.781 | 0.781 | 0.328 | 0.455 | 0.095 |
| R12 | C-prim | 0.784 | 0.812 | 0.363 | 0.439 | -0.142 |
| R2 | B-all@1a | 0.842 | 0.842 | 0.463 | 0.566 | 0.153 |
| R3 | B-prim@1a | 0.922 | 0.914 | 0.763 | 0.747 | 0.489 |
| R4 | B-all5@1a ⚠️ | 0.850 | 0.850 | 0.434 | 0.564 | 0.158 |
| R5 | B-prim5@1a ⚠️ | 0.918 | 0.916 | 0.770 | 0.747 | 0.538 |
| R6 | A-prim@1c | 0.893 | 0.898 | 0.639 | 0.677 | 0.488 |
| R7 | B-all@1c | 0.844 | 0.844 | 0.487 | 0.594 | 0.137 |
| R8 | B-prim@1c | 0.928 | 0.918 | 0.774 | 0.756 | 0.527 |
| R9 | B-all5@1c ⚠️ | 0.854 | 0.854 | 0.473 | 0.591 | 0.147 |
| ref_3a | ③a (= C0) | 0.775 | 0.775 | 0.356 | 0.429 | 0.244 |
| ref_L2_1a | L2-1 | 0.875 | 0.881 | 0.723 | 0.640 | 0.318 |
| ref_L2_1c | L2-3 | 0.872 | 0.876 | 0.654 | 0.610 | 0.327 |
| ref_base_1a | ฐาน ①a | 0.915 | 0.915 | 0.786 | 0.736 | 0.545 |
| ref_base_1c | ฐาน ①c | 0.920 | 0.920 | 0.742 | 0.735 | 0.593 |

แถว ALL ใน `rolling_104.csv` ปนความต่างของ β ระหว่าง policy — สูงเชิงกล · PRIM/e ต่อกองข้ามกองต่างดัชนี

### 5.7 รายเดือน (E / ALL)
| base | variant | policy | n | adjr2_med | r2_oos_med | d_r2_oos_med | d_adj_r2_med | note |
|---|---|---|---|---|---|---|---|---|
| 1a | base | E | 175 | 0.779 | 0.449 | – | – | รายเดือน Dimson lag 1 เดือน · HAC L=3 · ดัชนีดิบ (span เท่ากับ e) · A-prim = ดัชนี S_A · B-prim = primary ของ L2 ใน P4 · แถวอื่น N/A (p>13) |
| 1a | base | ALL | 207 | 0.773 | 0.439 | – | – | รายเดือน Dimson lag 1 เดือน · HAC L=3 · ดัชนีดิบ (span เท่ากับ e) · A-prim = ดัชนี S_A · B-prim = primary ของ L2 ใน P4 · แถวอื่น N/A (p>13) |
| 1a | A-prim | E | 175 | 0.830 | 0.485 | 0.004 | 0.013 | รายเดือน Dimson lag 1 เดือน · HAC L=3 · ดัชนีดิบ (span เท่ากับ e) · A-prim = ดัชนี S_A · B-prim = primary ของ L2 ใน P4 · แถวอื่น N/A (p>13) |
| 1a | A-prim | ALL | 207 | 0.823 | 0.434 | 0.002 | 0.012 | รายเดือน Dimson lag 1 เดือน · HAC L=3 · ดัชนีดิบ (span เท่ากับ e) · A-prim = ดัชนี S_A · B-prim = primary ของ L2 ใน P4 · แถวอื่น N/A (p>13) |
| 1a | B-prim | E | 175 | 0.815 | 0.509 | 0 | 0 | รายเดือน Dimson lag 1 เดือน · HAC L=3 · ดัชนีดิบ (span เท่ากับ e) · A-prim = ดัชนี S_A · B-prim = primary ของ L2 ใน P4 · แถวอื่น N/A (p>13) |
| 1a | B-prim | ALL | 207 | 0.809 | 0.489 | 0 | 0 | รายเดือน Dimson lag 1 เดือน · HAC L=3 · ดัชนีดิบ (span เท่ากับ e) · A-prim = ดัชนี S_A · B-prim = primary ของ L2 ใน P4 · แถวอื่น N/A (p>13) |
| 1a | B-prim5 | E | 175 | 0.808 | 0.509 | 0 | 0 | รายเดือน Dimson lag 1 เดือน · HAC L=3 · ดัชนีดิบ (span เท่ากับ e) · A-prim = ดัชนี S_A · B-prim = primary ของ L2 ใน P4 · แถวอื่น N/A (p>13) |
| 1a | B-prim5 | ALL | 207 | 0.801 | 0.489 | 0 | 0 | รายเดือน Dimson lag 1 เดือน · HAC L=3 · ดัชนีดิบ (span เท่ากับ e) · A-prim = ดัชนี S_A · B-prim = primary ของ L2 ใน P4 · แถวอื่น N/A (p>13) |
| 1c | base | E | 175 | 0.782 | 0.451 | – | – | รายเดือน Dimson lag 1 เดือน · HAC L=3 · ดัชนีดิบ (span เท่ากับ e) · A-prim = ดัชนี S_A · B-prim = primary ของ L2 ใน P4 · แถวอื่น N/A (p>13) |
| 1c | base | ALL | 207 | 0.775 | 0.431 | – | – | รายเดือน Dimson lag 1 เดือน · HAC L=3 · ดัชนีดิบ (span เท่ากับ e) · A-prim = ดัชนี S_A · B-prim = primary ของ L2 ใน P4 · แถวอื่น N/A (p>13) |
| 1c | A-prim | E | 175 | 0.844 | 0.524 | 0.003 | 0.015 | รายเดือน Dimson lag 1 เดือน · HAC L=3 · ดัชนีดิบ (span เท่ากับ e) · A-prim = ดัชนี S_A · B-prim = primary ของ L2 ใน P4 · แถวอื่น N/A (p>13) |
| 1c | A-prim | ALL | 207 | 0.826 | 0.475 | -0.003 | 0.011 | รายเดือน Dimson lag 1 เดือน · HAC L=3 · ดัชนีดิบ (span เท่ากับ e) · A-prim = ดัชนี S_A · B-prim = primary ของ L2 ใน P4 · แถวอื่น N/A (p>13) |
| 1c | B-prim | E | 175 | 0.822 | 0.536 | 0 | 0 | รายเดือน Dimson lag 1 เดือน · HAC L=3 · ดัชนีดิบ (span เท่ากับ e) · A-prim = ดัชนี S_A · B-prim = primary ของ L2 ใน P4 · แถวอื่น N/A (p>13) |
| 1c | B-prim | ALL | 207 | 0.800 | 0.499 | 0 | 0 | รายเดือน Dimson lag 1 เดือน · HAC L=3 · ดัชนีดิบ (span เท่ากับ e) · A-prim = ดัชนี S_A · B-prim = primary ของ L2 ใน P4 · แถวอื่น N/A (p>13) |
| 1c | B-prim5 | E | 175 | 0.802 | 0.540 | 0 | 0 | รายเดือน Dimson lag 1 เดือน · HAC L=3 · ดัชนีดิบ (span เท่ากับ e) · A-prim = ดัชนี S_A · B-prim = primary ของ L2 ใน P4 · แถวอื่น N/A (p>13) |
| 1c | B-prim5 | ALL | 207 | 0.794 | 0.504 | 0 | 0 | รายเดือน Dimson lag 1 เดือน · HAC L=3 · ดัชนีดิบ (span เท่ากับ e) · A-prim = ดัชนี S_A · B-prim = primary ของ L2 ใน P4 · แถวอื่น N/A (p>13) |

### 5.8 ความเอียงจาก argmax (m6) — median(Δadj R² train − ΔR²_oos) (E)
| row | label | med_d_adj_r2_train | med_d_r2_oos | med_bias |
|---|---|---|---|---|
| ref_L2_1a | L2-1 | 0.011 | 0.027 | -0.005 |
| ref_L2_1c | L2-3 | 0.012 | 0.015 | -0.001 |
| R1 | A-prim@1a | 0.007 | 0.012 | -0.003 |
| R6 | A-prim@1c | 0.012 | 0.009 | 0.000 |
| R12 | C-prim | 0.186 | 0.216 | -0.032 |

### 5.9 B-prim / B-prim5: ผลเฉพาะกอง E ที่ได้ตัวเพิ่ม (median ทั้งชุด EVAL = 0 เชิงโครงสร้าง) เทียบ A-prim (ทุกกอง E)
| row | label | n_funds_with_extra_E | med_d_adj_r2 | med_d_r2_oos | med_d_bic |
|---|---|---|---|---|---|
| R3 | B-prim@1a | 38 | 0.118 | 0.189 | -53.780 |
| R5 | B-prim5@1a ⚠️ | 32 | 0.106 | 0.189 | -46.736 |
| R8 | B-prim@1c | 38 | 0.172 | 0.242 | -74.562 |
| R10 | B-prim5@1c ⚠️ | 32 | 0.165 | 0.258 | -64.717 |
| R1 | A-prim@1a | 175 | 0.007 | 0.012 | 1.820 |
| R6 | A-prim@1c | 175 | 0.012 | 0.009 | -0.899 |

### 5.10 C-prim: สัดส่วนที่ตัวเลือกเป็น ETF ส่วนขยาย แยกตามกลุ่ม primary ของ L2 (none · M28)
| group | n | share_etf | top_choice |
|---|---|---|---|
| MSCI_ACWI_CD | 40 | 0.600 | ARKK |
| MSCI_CHINA_ALL_SHARES | 21 | 0 | MSCI_ASIA_EX_JAPAN |
| MSCI_ACWI | 16 | 0.938 | IBB |
| MSCI_ACWI_IT | 15 | 0.333 | MSCI_ACWI_IT |
| MSCI_ASIA_EX_JAPAN | 15 | 0 | MSCI_ASIA_EX_JAPAN |
| MSCI_ACWI_EX_US | 12 | 0.167 | MSCI_USA |
| MSCI_WORLD_EX_US | 11 | 0.091 | MSCI_EUROPE |
| MSCI_ASEAN | 8 | 0.625 | THD |
| MSCI_JAPAN | 8 | 0 | MSCI_JAPAN |
| MSCI_INDIA | 8 | 0 | MSCI_INDIA |
| MSCI_EM | 8 | 0 | MSCI_ASIA_EX_JAPAN |
| MSCI_ACWI_HC | 7 | 0 | MSCI_ACWI_HC |
| MSCI_EUROPE | 6 | 0.167 | MSCI_EUROPE |
| MSCI_VIETNAM | 6 | 0 | MSCI_VIETNAM |
| MSCI_ACWI_UT | 5 | 0.600 | IGF |

สัดส่วน ETF ทั้งหมด = 0.304

### 5.11 elastic net: จำนวนดัชนี (จาก 43) ที่ π ≥ 0.6 ต่อกอง และ median π ทุกคู่
| base | mean | median | max |
|---|---|---|---|
| 1a | 4.237 | 3 | 16 |
| 1c | 4.406 | 3 | 26 |

median π ทุกคู่ (กอง × ดัชนี): {'1a': 0.12, '1c': 0.11}

## 6. VIF / κ ทุกแถว
| row | label | kind | n_funds | vif_max_lag0 | vif_median_lag0 | vif_max_dimson | vif_median_dimson | kappa |
|---|---|---|---|---|---|---|---|---|
| ref_base_1a | ฐาน ①a | factor ร่วม | 207 | 1.000 | 1 | 1.141 | 1.047 | 1.000 |
| ref_L2_1a | L2-1 | ต่อกอง (VIF ของ PRIM กับฐาน) | 207 | 6.215 | 4.782 | 6.639 | 4.849 | – |
| ref_base_1c | ฐาน ①c | factor ร่วม | 207 | 1.000 | 1.000 | 1.174 | 1.027 | 1.004 |
| ref_L2_1c | L2-3 | ต่อกอง (VIF ของ PRIM กับฐาน) | 207 | 6.405 | 4.646 | 6.831 | 4.941 | – |
| ref_3a | ③a (= C0) | factor ร่วม | 207 | 2.154 | 1.576 | 2.219 | 1.626 | 2.542 |
| R1 | A-prim@1a | ต่อกอง (VIF ของ PRIM กับฐาน) | 207 | 3.228 | 2.185 | 3.352 | 2.409 | – |
| R2 | B-all@1a | factor ร่วม | 207 | 2.120 | 1.074 | 2.317 | 1.237 | 2.549 |
| R3 | B-prim@1a | ต่อกอง (VIF ของ PRIM กับฐาน) | 40 | 1.000 | 1 | 1.105 | 1.055 | – |
| R4 | B-all5@1a ⚠️ | factor ร่วม | 207 | 1.861 | 1.017 | 2.046 | 1.168 | 2.321 |
| R5 | B-prim5@1a ⚠️ | ต่อกอง (VIF ของ PRIM กับฐาน) | 34 | 1.000 | 1 | 1.086 | 1.050 | – |
| R6 | A-prim@1c | ต่อกอง (VIF ของ PRIM กับฐาน) | 207 | 2.469 | 2.051 | 2.569 | 2.211 | – |
| R7 | B-all@1c | factor ร่วม | 207 | 1.904 | 1.090 | 2.019 | 1.231 | 2.411 |
| R8 | B-prim@1c | ต่อกอง (VIF ของ PRIM กับฐาน) | 40 | 1.000 | 1 | 1.094 | 1.055 | – |
| R9 | B-all5@1c ⚠️ | factor ร่วม | 207 | 1.631 | 1.027 | 1.718 | 1.132 | 2.159 |
| R10 | B-prim5@1c ⚠️ | ต่อกอง (VIF ของ PRIM กับฐาน) | 34 | 1.000 | 1 | 1.094 | 1.046 | – |
| R11 | C-blk | factor ร่วม | 207 | 2.154 | 1.052 | 2.247 | 1.095 | 2.584 |
| R12 | C-prim | ต่อกอง (VIF ของ PRIM กับฐาน) | 207 | 1.584 | 1.119 | 1.756 | 1.293 | – |
| A1_S_A@1a | [f, S_A] (15 ดัชนี) | ชุดคัดแบบแอป (ไม่ใช่แถวคะแนน) | – | 4.485 | 2.881 | 5.629 | 3.188 | 8.059 |
| A1_S_A@1c | [f, S_A] (16 ดัชนี) | ชุดคัดแบบแอป (ไม่ใช่แถวคะแนน) | – | 4.669 | 2.883 | 6.002 | 3.442 | 9.033 |

## 7. Q1 — ผล L2 ยังอยู่ไหม (Q1a ของ B คู่ Q1a-A เสมอ · **ไม่ใช่หลักฐานนอกช่วงใหม่**)
| index | n_primary_1a | med_dR2oos_primary_1a | med_dBIC_primary_1a | vif_e_1a | pass_1a | med_dR2oos_allEVAL_1a | n_groups_dR2oos_ge_002_1a | pseudo_med_dR2oos_primary_1a | pseudo_med_dBIC_primary_1a | vif_dimson_ge5_lag0_lt5_1a | n_primary_1c | med_dR2oos_primary_1c | med_dBIC_primary_1c | vif_e_1c | pass_1c | med_dR2oos_allEVAL_1c | n_groups_dR2oos_ge_002_1c | pseudo_med_dR2oos_primary_1c | pseudo_med_dBIC_primary_1c | vif_dimson_ge5_lag0_lt5_1c | Q1a | Q1a_A_survives_both | in_S_A_1a | in_S_A_1c | in_S_A_b_1a | in_S_A_b_1c | evidence_independent | note |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| MSCI_ACWI_HC | 7 | 0.306 | -40.792 | 2.120 | True | -0.000 | 42 | 0.078 | -13.415 | False | 7 | 0.545 | -70.124 | 1.904 | True | -0.000 | 33 | 0.249 | -23.665 | False | ยังอยู่ | True | True | True | True | True | False | Q1a ไม่ใช่หลักฐานนอกช่วงใหม่ · pseudo-OOS = diagnostic |
| MSCI_ACWI_UT | 5 | 0.131 | -16.092 | 1.613 | True | -0.001 | 19 | 0.018 | 3.122 | False | 5 | 0.162 | -14.973 | 1.586 | True | -0.000 | 21 | 0.023 | 2.397 | False | ยังอยู่ | True | True | True | True | True | False | Q1a ไม่ใช่หลักฐานนอกช่วงใหม่ · pseudo-OOS = diagnostic |
| MSCI_EUROPE | 6 | 0.133 | -52.270 | 1.295 | True | -0.000 | 17 | 0.019 | -41.375 | False | 6 | 0.223 | -74.261 | 1.279 | True | 0.004 | 39 | 0.148 | -50.425 | False | ยังอยู่ | False | False | True | False | True | False | Q1a ไม่ใช่หลักฐานนอกช่วงใหม่ · pseudo-OOS = diagnostic |
| MSCI_INDIA | 8 | 0.108 | -64.701 | 1.124 | True | 0.002 | 44 | 0.267 | -10.559 | False | 8 | 0.417 | -117.321 | 1.133 | True | -0.001 | 17 | 0.728 | -33.409 | False | ยังอยู่ | True | True | True | True | True | False | Q1a ไม่ใช่หลักฐานนอกช่วงใหม่ · pseudo-OOS = diagnostic |
| MSCI_JAPAN | 8 | 0.152 | -51.123 | 1.024 | True | -0.005 | 11 | 0.292 | -20.224 | False | 8 | 0.163 | -49.244 | 1.047 | True | -0.004 | 14 | 0.261 | -19.598 | False | ยังอยู่ | True | True | True | True | True | False | Q1a ไม่ใช่หลักฐานนอกช่วงใหม่ · pseudo-OOS = diagnostic |
| MSCI_VIETNAM | 6 | 0.295 | -194.639 | 1.215 | True | -0.003 | 9 | 0.939 | -97.993 | False | 6 | 0.091 | -103.245 | 1.420 | True | -0.003 | 14 | 0.268 | -59.738 | False | ยังอยู่ | True | True | True | True | True | False | Q1a ไม่ใช่หลักฐานนอกช่วงใหม่ · pseudo-OOS = diagnostic |

**Q1b (ทั้งบล็อก B-all):**

| base | row | med_dR2oos_E | med_dBIC_E | Q1b_pass |
|---|---|---|---|---|
| 1a | R2 | 0.010 | 22.863 | False |
| 1c | R7 | 0.000 | 22.618 | False |

### 7.1 Wald (b0_j, b1_j)=0 ใน B-all (บรรยาย) + placebo ราคาถูก
| base | index | n_funds_sig | n_groups_sig | frac_padj05 | placebo26_frac_padj05 | placebo52_frac_padj05 | note |
|---|---|---|---|---|---|---|---|
| 1a | MSCI_ACWI_HC | 42 | 36 | 0.290 | 0.029 | 0.092 | บรรยาย · คาลิเบรตจาก single-index ของ L2 (ขั้น 2) + placebo ราคาถูก (m5) |
| 1a | MSCI_ACWI_UT | 35 | 28 | 0.208 | 0.068 | 0.077 | บรรยาย · คาลิเบรตจาก single-index ของ L2 (ขั้น 2) + placebo ราคาถูก (m5) |
| 1a | MSCI_EUROPE | 42 | 35 | 0.266 | 0.068 | 0.048 | บรรยาย · คาลิเบรตจาก single-index ของ L2 (ขั้น 2) + placebo ราคาถูก (m5) |
| 1a | MSCI_INDIA | 51 | 44 | 0.300 | 0.029 | 0.097 | บรรยาย · คาลิเบรตจาก single-index ของ L2 (ขั้น 2) + placebo ราคาถูก (m5) |
| 1a | MSCI_JAPAN | 66 | 57 | 0.420 | 0.092 | 0.029 | บรรยาย · คาลิเบรตจาก single-index ของ L2 (ขั้น 2) + placebo ราคาถูก (m5) |
| 1a | MSCI_VIETNAM | 51 | 38 | 0.309 | 0.082 | 0.097 | บรรยาย · คาลิเบรตจาก single-index ของ L2 (ขั้น 2) + placebo ราคาถูก (m5) |
| 1c | MSCI_ACWI_HC | 32 | 27 | 0.232 | 0.029 | 0.053 | บรรยาย · คาลิเบรตจาก single-index ของ L2 (ขั้น 2) + placebo ราคาถูก (m5) |
| 1c | MSCI_ACWI_UT | 32 | 25 | 0.198 | 0.063 | 0.097 | บรรยาย · คาลิเบรตจาก single-index ของ L2 (ขั้น 2) + placebo ราคาถูก (m5) |
| 1c | MSCI_EUROPE | 49 | 37 | 0.309 | 0.072 | 0.082 | บรรยาย · คาลิเบรตจาก single-index ของ L2 (ขั้น 2) + placebo ราคาถูก (m5) |
| 1c | MSCI_INDIA | 26 | 20 | 0.198 | 0.034 | 0.048 | บรรยาย · คาลิเบรตจาก single-index ของ L2 (ขั้น 2) + placebo ราคาถูก (m5) |
| 1c | MSCI_JAPAN | 64 | 56 | 0.401 | 0.097 | 0.043 | บรรยาย · คาลิเบรตจาก single-index ของ L2 (ขั้น 2) + placebo ราคาถูก (m5) |
| 1c | MSCI_VIETNAM | 66 | 52 | 0.391 | 0.077 | 0.169 | บรรยาย · คาลิเบรตจาก single-index ของ L2 (ขั้น 2) + placebo ราคาถูก (m5) |

## 8. Q2 — ธงของชุดที่เป็นไปได้ (ไม่มีการเลือกอัตโนมัติ)
| row | label | vif_max_lag0 | f1_vif_lt5 | vif_dimson_max | flag_dimson_ge5_lag0_lt5 | med_dR2oos_E | f2_dR2oos_ge0 | med_dBIC_E | f3_dBIC_le0 | r_raw_median_E | r_raw_min_E | f4_r_ge06 | gap_E | f5_gap_le015 | f6_named | r2oos_E | r2oos_E_below_1a | note |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| R1 | A-prim@1a | 3.228 | True | 3.352 | False | 0.012 | True | 1.820 | False | 0.764 | 0.611 | True | 0.111 | True | True | 0.665 | – | ไม่มีการเลือกอัตโนมัติ · PRIM/e ต่อกองนับเป็นมีชื่อ (ดัชนี) |
| R2 | B-all@1a | 2.120 | True | 2.317 | False | 0.010 | True | 22.863 | False | 0.650 | 0.189 | True | 0.162 | False | True | 0.668 | – | ไม่มีการเลือกอัตโนมัติ · PRIM/e ต่อกองนับเป็นมีชื่อ (ดัชนี) |
| R3 | B-prim@1a | 1.000 | True | 1.105 | False | 0 | True | 0 | True | 0.833 | 0.660 | True | 0.103 | True | True | 0.662 | – | ไม่มีการเลือกอัตโนมัติ · PRIM/e ต่อกองนับเป็นมีชื่อ (ดัชนี) |
| R4 | B-all5@1a ⚠️ | 1.861 | True | 2.046 | False | 0.014 | True | 20.974 | False | 0.609 | 0.164 | True | 0.148 | True | True | 0.673 | – | ไม่มีการเลือกอัตโนมัติ · PRIM/e ต่อกองนับเป็นมีชื่อ (ดัชนี) |
| R5 | B-prim5@1a ⚠️ | 1.000 | True | 1.086 | False | 0 | True | 0 | True | 0.828 | 0.654 | True | 0.100 | True | True | 0.662 | – | ไม่มีการเลือกอัตโนมัติ · PRIM/e ต่อกองนับเป็นมีชื่อ (ดัชนี) |
| R6 | A-prim@1c | 2.469 | True | 2.569 | False | 0.009 | True | -0.899 | True | 0.750 | 0.589 | True | 0.105 | True | True | 0.704 | – | ไม่มีการเลือกอัตโนมัติ · PRIM/e ต่อกองนับเป็นมีชื่อ (ดัชนี) |
| R7 | B-all@1c | 1.904 | True | 2.019 | False | 0.000 | True | 22.618 | False | 0.637 | 0.170 | True | 0.159 | False | True | 0.687 | – | ไม่มีการเลือกอัตโนมัติ · PRIM/e ต่อกองนับเป็นมีชื่อ (ดัชนี) |
| R8 | B-prim@1c | 1.000 | True | 1.094 | False | 0 | True | 0 | True | 0.813 | 0.713 | True | 0.100 | True | True | 0.691 | – | ไม่มีการเลือกอัตโนมัติ · PRIM/e ต่อกองนับเป็นมีชื่อ (ดัชนี) |
| R9 | B-all5@1c ⚠️ | 1.631 | True | 1.718 | False | 0.004 | True | 18.468 | False | 0.688 | 0.208 | True | 0.137 | True | True | 0.667 | – | ไม่มีการเลือกอัตโนมัติ · PRIM/e ต่อกองนับเป็นมีชื่อ (ดัชนี) |
| R10 | B-prim5@1c ⚠️ | 1.000 | True | 1.094 | False | 0 | True | 0 | True | 0.809 | 0.699 | True | 0.097 | True | True | 0.689 | – | ไม่มีการเลือกอัตโนมัติ · PRIM/e ต่อกองนับเป็นมีชื่อ (ดัชนี) |
| R11 | C-blk | 2.154 | True | 2.247 | False | -0.024 | False | -5.513 | True | 0.497 | 0.103 | False | 0.219 | False | True | 0.281 | 0.336 | ไม่มีการเลือกอัตโนมัติ · PRIM/e ต่อกองนับเป็นมีชื่อ (ดัชนี) |
| R12 | C-prim | 1.584 | True | 1.756 | False | 0.216 | True | -57.893 | True | 0.483 | -0.123 | False | 0.154 | False | True | 0.580 | 0.038 | ไม่มีการเลือกอัตโนมัติ · PRIM/e ต่อกองนับเป็นมีชื่อ (ดัชนี) |

## 9. Q3 — primary เทียบแอป (บรรยาย)
| source | grouping | group | n | n_country | n_sector | n_either | rate_country | rate_sector | rate_either | base_either_mean | base_either_lo | base_either_hi |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| L2(none,M28) | policy | E | 108 | 37 | 29 | 66 | 0.343 | 0.269 | 0.611 | 0.119 | 0.065 | 0.176 |
| L2(none,M28) | policy | ALL | 108 | 37 | 29 | 66 | 0.343 | 0.269 | 0.611 | 0.118 | 0.065 | 0.176 |
| L2(none,M28) | L2_primary_is_aggregate | ดัชนีรวมใน L2 | 27 | 9 | 0 | 9 | 0.333 | 0 | 0.333 | 0.163 | 0.037 | 0.296 |
| L2(none,M28) | L2_primary_is_aggregate | ไม่ใช่ดัชนีรวม | 81 | 28 | 29 | 57 | 0.346 | 0.358 | 0.704 | 0.143 | 0.074 | 0.210 |
| L2(none,M28) | L2_primary_is_aggregate | ALL | 108 | 37 | 29 | 66 | 0.343 | 0.269 | 0.611 | 0.146 | 0.083 | 0.204 |
| A-prim@1a | policy | E | 108 | 17 | 26 | 43 | 0.157 | 0.241 | 0.398 | 0.134 | 0.093 | 0.176 |
| A-prim@1a | policy | ALL | 108 | 17 | 26 | 43 | 0.157 | 0.241 | 0.398 | 0.134 | 0.092 | 0.185 |
| A-prim@1a | L2_primary_is_aggregate | ดัชนีรวมใน L2 | 27 | 1 | 11 | 12 | 0.037 | 0.407 | 0.444 | 0.377 | 0.296 | 0.444 |
| A-prim@1a | L2_primary_is_aggregate | ไม่ใช่ดัชนีรวม | 81 | 16 | 15 | 31 | 0.198 | 0.185 | 0.383 | 0.087 | 0.037 | 0.136 |
| A-prim@1a | L2_primary_is_aggregate | ALL | 108 | 17 | 26 | 43 | 0.157 | 0.241 | 0.398 | 0.160 | 0.120 | 0.204 |
| A-prim@1c | policy | E | 108 | 19 | 16 | 35 | 0.176 | 0.148 | 0.324 | 0.085 | 0.046 | 0.120 |
| A-prim@1c | policy | ALL | 108 | 19 | 16 | 35 | 0.176 | 0.148 | 0.324 | 0.086 | 0.046 | 0.130 |
| A-prim@1c | L2_primary_is_aggregate | ดัชนีรวมใน L2 | 27 | 2 | 6 | 8 | 0.074 | 0.222 | 0.296 | 0.212 | 0.148 | 0.296 |
| A-prim@1c | L2_primary_is_aggregate | ไม่ใช่ดัชนีรวม | 81 | 17 | 10 | 27 | 0.210 | 0.123 | 0.333 | 0.061 | 0.025 | 0.111 |
| A-prim@1c | L2_primary_is_aggregate | ALL | 108 | 19 | 16 | 35 | 0.176 | 0.148 | 0.324 | 0.100 | 0.065 | 0.139 |
| C-prim(ETF=ไม่ตรง) | policy | E | 108 | 21 | 13 | 34 | 0.194 | 0.120 | 0.315 | 0.054 | 0.019 | 0.093 |
| C-prim(ETF=ไม่ตรง) | policy | ALL | 108 | 21 | 13 | 34 | 0.194 | 0.120 | 0.315 | 0.054 | 0.019 | 0.093 |
| C-prim(ETF=ไม่ตรง) | L2_primary_is_aggregate | ดัชนีรวมใน L2 | 27 | 5 | 0 | 5 | 0.185 | 0 | 0.185 | 0.076 | 0 | 0.148 |
| C-prim(ETF=ไม่ตรง) | L2_primary_is_aggregate | ไม่ใช่ดัชนีรวม | 81 | 16 | 13 | 29 | 0.198 | 0.160 | 0.358 | 0.061 | 0.012 | 0.111 |
| C-prim(ETF=ไม่ตรง) | L2_primary_is_aggregate | ALL | 108 | 21 | 13 | 34 | 0.194 | 0.120 | 0.315 | 0.064 | 0.028 | 0.102 |
| C-prim(ETF=ไม่ตรง) | สัดส่วนที่ primary เป็น ETF ส่วนขยาย | ALL | 207 | – | – | – | – | – | 0.304 | – | – | – |

| source | ours | app_country | n |
|---|---|---|---|
| L2(none,M28) | MSCI_ACWI_CD | MSCI_ACWI | 6 |
| L2(none,M28) | MSCI_ACWI_CD | MSCI_ACWI_EX_US | 6 |
| L2(none,M28) | MSCI_ACWI_CD | MSCI_WORLD_EX_US | 3 |
| L2(none,M28) | MSCI_ACWI_EX_US | MSCI_WORLD_EX_US | 2 |
| L2(none,M28) | MSCI_ASIA_EX_JAPAN | MSCI_CHINA_ALL_SHARES | 2 |
| L2(none,M28) | MSCI_EM | MSCI_ASIA_EX_JAPAN | 2 |
| L2(none,M28) | MSCI_EUROPE | MSCI_ACWI_EX_US | 2 |
| L2(none,M28) | MSCI_JAPAN | MSCI_WORLD_EX_US | 2 |
| L2(none,M28) | MSCI_WORLD_EX_US | MSCI_ACWI_EX_US | 2 |
| L2(none,M28) | MSCI_ACWI | MSCI_USA | 1 |
| L2(none,M28) | MSCI_ACWI | MSCI_WORLD | 1 |
| L2(none,M28) | MSCI_ACWI | MSCI_WORLD_EX_US | 1 |
| L2(none,M28) | MSCI_ACWI_CD | MSCI_ASIA_EX_JAPAN | 1 |
| L2(none,M28) | MSCI_ACWI_CD | MSCI_CHINA_ALL_SHARES | 1 |
| L2(none,M28) | MSCI_ACWI_CD | MSCI_WORLD | 1 |
| A-prim@1a | MSCI_ACWI_TC | MSCI_USA | 10 |
| A-prim@1a | MSCI_ACWI_TC | MSCI_ACWI | 8 |
| A-prim@1a | MSCI_CHINA_H_SHARES | MSCI_CHINA_ALL_SHARES | 7 |
| A-prim@1a | MSCI_ACWI_MT | MSCI_ACWI | 6 |
| A-prim@1a | MSCI_ACWI_TC | MSCI_ACWI_EX_US | 5 |
| A-prim@1a | MSCI_CHINA_A_SHARES | MSCI_CHINA_ALL_SHARES | 5 |
| A-prim@1a | MSCI_ACWI_TC | MSCI_CHINA_ALL_SHARES | 4 |
| A-prim@1a | MSCI_ACWI_MT | MSCI_WORLD_EX_US | 3 |
| A-prim@1a | MSCI_CHINA_H_SHARES | MSCI_ASIA_EX_JAPAN | 3 |
| A-prim@1a | MSCI_ACWI_TC | MSCI_WORLD | 2 |
| A-prim@1a | MSCI_JAPAN | MSCI_WORLD_EX_US | 2 |
| A-prim@1a | MSCI_ACWI_MT | MSCI_ACWI_EX_US | 1 |
| A-prim@1a | MSCI_ACWI_TC | MSCI_ASIA_EX_JAPAN | 1 |
| A-prim@1a | MSCI_ACWI_TC | MSCI_WORLD_EX_US | 1 |
| A-prim@1a | MSCI_CHINA_A_SHARES | MSCI_ASIA_EX_JAPAN | 1 |
| A-prim@1c | MSCI_ACWI_TC | MSCI_USA | 10 |
| A-prim@1c | MSCI_ACWI_TC | MSCI_ACWI | 8 |
| A-prim@1c | MSCI_CHINA_H_SHARES | MSCI_CHINA_ALL_SHARES | 7 |
| A-prim@1c | MSCI_ACWI_MT | MSCI_ACWI | 6 |
| A-prim@1c | MSCI_ACWI_TC | MSCI_ACWI_EX_US | 5 |
| A-prim@1c | MSCI_CHINA_A_SHARES | MSCI_CHINA_ALL_SHARES | 5 |
| A-prim@1c | MSCI_EUROPE | MSCI_ACWI_EX_US | 5 |
| A-prim@1c | MSCI_EUROPE | MSCI_WORLD_EX_US | 5 |
| A-prim@1c | MSCI_ACWI_TC | MSCI_CHINA_ALL_SHARES | 4 |
| A-prim@1c | MSCI_CHINA_H_SHARES | MSCI_ASIA_EX_JAPAN | 3 |
| A-prim@1c | MSCI_JAPAN | MSCI_WORLD_EX_US | 2 |
| A-prim@1c | MSCI_ACWI_MT | MSCI_ACWI_EX_US | 1 |
| A-prim@1c | MSCI_ACWI_MT | MSCI_WORLD_EX_US | 1 |
| A-prim@1c | MSCI_ACWI_TC | MSCI_ASIA_EX_JAPAN | 1 |
| A-prim@1c | MSCI_ACWI_TC | MSCI_WORLD | 1 |
| C-prim(ETF=ไม่ตรง) | MSCI_ASIA_EX_JAPAN | MSCI_CHINA_ALL_SHARES | 13 |
| C-prim(ETF=ไม่ตรง) | IBB | MSCI_ACWI | 4 |
| C-prim(ETF=ไม่ตรง) | MSCI_EUROPE | MSCI_ACWI_EX_US | 4 |
| C-prim(ETF=ไม่ตรง) | ARKK | MSCI_ACWI | 3 |
| C-prim(ETF=ไม่ตรง) | ARKK | MSCI_ACWI_EX_US | 3 |
| C-prim(ETF=ไม่ตรง) | ICLN | MSCI_ACWI | 3 |
| C-prim(ETF=ไม่ตรง) | MSCI_ASEAN | MSCI_ACWI | 3 |
| C-prim(ETF=ไม่ตรง) | MSCI_CHINA_ALL_SHARES | MSCI_CHINA_A_SHARES | 3 |
| C-prim(ETF=ไม่ตรง) | MSCI_JAPAN | MSCI_WORLD_EX_US | 3 |
| C-prim(ETF=ไม่ตรง) | ARKK | MSCI_CHINA_ALL_SHARES | 2 |
| C-prim(ETF=ไม่ตรง) | ICLN | MSCI_ACWI_EX_US | 2 |
| C-prim(ETF=ไม่ตรง) | IGF | MSCI_ACWI_EX_US | 2 |
| C-prim(ETF=ไม่ตรง) | MSCI_ACWI_IT | MSCI_ACWI_EX_US | 2 |
| C-prim(ETF=ไม่ตรง) | MSCI_ASEAN | MSCI_WORLD_EX_US | 2 |
| C-prim(ETF=ไม่ตรง) | MSCI_ASIA_EX_JAPAN | MSCI_EM | 2 |

### 9.1 elastic net stability (บรรยาย · ไม่ใช้เลือกอะไร)
| base | index | in_P4 | in_S_A | in_blockC | med_pi_primary | n_primary_L2 | n_funds_pi_ge_0.6 | n_groups_pi_ge_0.6 | n_funds_pi_ge_0.8 | n_groups_pi_ge_0.8 |
|---|---|---|---|---|---|---|---|---|---|---|
| 1a | MSCI_ASIA_EX_JAPAN | False | False | False | 0.360 | 15 | 16 | 15 | 6 | 5 |
| 1a | MSCI_BRAZIL | False | True | False | – | 0 | 15 | 14 | 4 | 4 |
| 1a | MSCI_CHINA_A_SHARES | False | True | False | 1 | 4 | 26 | 21 | 18 | 14 |
| 1a | MSCI_CHINA_H_SHARES | False | True | False | – | 0 | 18 | 16 | 9 | 7 |
| 1a | MSCI_CHINA_ALL_SHARES | False | False | False | 0.140 | 21 | 19 | 17 | 7 | 6 |
| 1a | MSCI_EUROPE | True | False | False | 1 | 6 | 24 | 21 | 11 | 9 |
| 1a | MSCI_INDIA | True | True | False | 1 | 8 | 48 | 41 | 34 | 28 |
| 1a | MSCI_JAPAN | True | True | False | 1 | 8 | 32 | 29 | 19 | 16 |
| 1a | MSCI_KOREA | False | True | False | 0.060 | 3 | 25 | 24 | 14 | 13 |
| 1a | MSCI_ASEAN | False | True | False | 0.765 | 8 | 24 | 22 | 11 | 11 |
| 1a | MSCI_TAIWAN | False | True | False | – | 0 | 24 | 21 | 13 | 11 |
| 1a | MSCI_USA | False | False | False | 1 | 3 | 10 | 9 | 4 | 4 |
| 1a | MSCI_VIETNAM | True | True | False | 1 | 6 | 37 | 26 | 22 | 17 |
| 1a | MSCI_ACWI_EX_US | False | False | False | 0.035 | 12 | 6 | 6 | 1 | 1 |
| 1a | MSCI_ACWI_CD | False | False | True | 0.080 | 40 | 15 | 14 | 7 | 7 |
| 1a | MSCI_ACWI_CS | False | True | False | 1 | 1 | 18 | 16 | 8 | 8 |
| 1a | MSCI_ACWI_EN | False | True | False | – | 0 | 10 | 10 | 3 | 3 |
| 1a | MSCI_ACWI_FN | False | False | False | 1 | 3 | 20 | 18 | 17 | 15 |
| 1a | MSCI_ACWI_HC | True | True | False | 1 | 7 | 41 | 37 | 27 | 23 |
| 1a | MSCI_ACWI_IN | False | False | False | 0.895 | 2 | 12 | 11 | 4 | 4 |
| 1a | MSCI_ACWI_IT | False | False | False | 0.630 | 15 | 22 | 17 | 14 | 9 |
| 1a | MSCI_ACWI_MT | False | True | False | 0.595 | 2 | 15 | 15 | 5 | 5 |
| 1a | MSCI_ACWI_TC | False | True | False | – | 0 | 13 | 12 | 5 | 5 |
| 1a | MSCI_ACWI_UT | True | True | False | 0.830 | 5 | 18 | 16 | 9 | 8 |
| 1a | QQQ | False | False | False | – | 0 | 31 | 25 | 16 | 13 |
| 1a | SOXX | False | False | False | – | 0 | 25 | 21 | 10 | 10 |
| 1a | ARKK | False | False | False | – | 0 | 43 | 37 | 30 | 25 |
| 1a | ICLN | False | False | False | – | 0 | 18 | 16 | 12 | 11 |
| 1a | IBB | False | False | False | – | 0 | 28 | 24 | 12 | 11 |
| 1a | KWEB | False | False | False | – | 0 | 24 | 22 | 10 | 9 |
| 1a | THD | False | False | False | – | 0 | 32 | 28 | 18 | 15 |
| 1a | EIDO | False | False | False | – | 0 | 17 | 16 | 5 | 5 |
| 1a | EPHE | False | False | False | – | 0 | 13 | 11 | 3 | 2 |
| 1a | EWM | False | False | False | – | 0 | 11 | 10 | 4 | 4 |
| 1a | EWS | False | False | False | – | 0 | 21 | 18 | 8 | 8 |
| 1a | REET | False | False | False | – | 0 | 38 | 31 | 19 | 13 |
| 1a | IGF | False | False | False | – | 0 | 24 | 21 | 11 | 10 |
| 1a | DBC | False | False | False | – | 0 | 14 | 12 | 3 | 3 |
| 1a | TDEX | False | False | False | – | 0 | 22 | 21 | 8 | 8 |
| 1c | MSCI_ASIA_EX_JAPAN | False | False | False | 0.420 | 15 | 18 | 16 | 7 | 6 |
| 1c | MSCI_BRAZIL | False | True | False | – | 0 | 15 | 14 | 5 | 5 |
| 1c | MSCI_CHINA_A_SHARES | False | True | False | 1 | 4 | 26 | 21 | 17 | 14 |
| 1c | MSCI_CHINA_H_SHARES | False | True | False | – | 0 | 17 | 15 | 7 | 5 |
| 1c | MSCI_CHINA_ALL_SHARES | False | False | False | 0.110 | 21 | 26 | 22 | 12 | 11 |
| 1c | MSCI_EM | False | False | False | 0.430 | 8 | 5 | 5 | 2 | 2 |
| 1c | MSCI_EUROPE | True | True | False | 1 | 6 | 25 | 21 | 10 | 9 |
| 1c | MSCI_INDIA | True | True | False | 1 | 8 | 31 | 27 | 18 | 14 |
| 1c | MSCI_JAPAN | True | True | False | 1 | 8 | 33 | 29 | 13 | 12 |
| 1c | MSCI_KOREA | False | True | False | 0.100 | 3 | 20 | 18 | 12 | 10 |
| 1c | MSCI_ASEAN | False | True | False | 0.945 | 8 | 22 | 18 | 13 | 12 |
| 1c | MSCI_TAIWAN | False | True | False | – | 0 | 25 | 23 | 11 | 11 |
| 1c | MSCI_USA | False | False | False | 1 | 3 | 13 | 9 | 5 | 4 |
| 1c | MSCI_VIETNAM | True | True | False | 1 | 6 | 45 | 35 | 29 | 21 |
| 1c | MSCI_ACWI_EX_US | False | False | False | 0.035 | 12 | 9 | 7 | 4 | 4 |
| 1c | MSCI_ACWI_CD | False | False | True | 0.055 | 40 | 16 | 14 | 6 | 6 |
| 1c | MSCI_ACWI_CS | False | True | False | 1 | 1 | 17 | 16 | 6 | 6 |
| 1c | MSCI_ACWI_EN | False | True | False | – | 0 | 10 | 10 | 1 | 1 |
| 1c | MSCI_ACWI_FN | False | False | False | 1 | 3 | 24 | 20 | 12 | 10 |
| 1c | MSCI_ACWI_HC | True | True | False | 1 | 7 | 32 | 27 | 22 | 19 |
| 1c | MSCI_ACWI_IN | False | False | False | 0.930 | 2 | 14 | 12 | 6 | 6 |
| 1c | MSCI_ACWI_IT | False | False | False | 0.680 | 15 | 21 | 16 | 10 | 6 |
| 1c | MSCI_ACWI_MT | False | True | False | 0.620 | 2 | 16 | 14 | 4 | 4 |
| 1c | MSCI_ACWI_TC | False | True | False | – | 0 | 17 | 16 | 9 | 9 |
| 1c | MSCI_ACWI_UT | True | True | False | 0.820 | 5 | 18 | 16 | 7 | 6 |
| 1c | QQQ | False | False | False | – | 0 | 27 | 22 | 13 | 10 |
| 1c | SOXX | False | False | False | – | 0 | 35 | 28 | 16 | 14 |
| 1c | ARKK | False | False | False | – | 0 | 42 | 34 | 30 | 25 |
| 1c | ICLN | False | False | False | – | 0 | 32 | 29 | 13 | 12 |
| 1c | IBB | False | False | False | – | 0 | 24 | 21 | 12 | 9 |
| 1c | KWEB | False | False | False | – | 0 | 33 | 31 | 15 | 13 |
| 1c | THD | False | False | False | – | 0 | 32 | 27 | 20 | 17 |
| 1c | EIDO | False | False | False | – | 0 | 17 | 13 | 10 | 9 |
| 1c | EPHE | False | False | False | – | 0 | 16 | 14 | 6 | 6 |
| 1c | EWM | False | False | False | – | 0 | 13 | 13 | 5 | 5 |
| 1c | EWS | False | False | False | – | 0 | 19 | 16 | 8 | 8 |
| 1c | REET | False | False | False | – | 0 | 37 | 31 | 12 | 9 |
| 1c | IGF | False | False | False | – | 0 | 27 | 23 | 14 | 13 |
| 1c | DBC | False | False | False | – | 0 | 19 | 17 | 5 | 4 |
| 1c | TDEX | False | False | False | – | 0 | 18 | 16 | 10 | 10 |

## 10. เทียบความคาดหมายล่วงหน้า (ข้อ 9 ของ spec)
| item | expectation | observed | met |
|---|---|---|---|
| 1 (A0) | C11 ลำพัง max VIF<5 ทั้ง train และ 2021–2025 · S10 ลำพังมี ≥1 ตัว VIF≥5 · f+C11+S10 มี ≥5 ตัว VIF≥5 | C11 max VIF {'full_2021_2025': 2.214537358380515, 'train': 2.7004900186177467} · S10 max VIF {'full_2021_2025': 8.217739548670819, 'train': 9.324613920953466} · f+C11+S10 (train, ①a) VIF≥5 = 15 ตัว | True |
| 2 (A1) | ตัด 4–10 ดัชนี · USA ถูกตัดทั้งสองฐาน · sector ที่ถูกตัด ≥3 · P4 อยู่ใน S_A ≥4 ใน 6 ทั้งสองฐาน | ตัด {'1a': 6, '1c': 5} · USA ถูกตัดทั้งสองฐาน=True · sector ที่ถูกตัด {b: len}={'1a': 4, '1c': 4} · P4 อยู่ใน S_A {'1a': 5, '1c': 6} · ตัด={'1a': ['MSCI_USA', 'MSCI_ACWI_IN', 'MSCI_ACWI_CD', 'MSCI_ACWI_IT', 'MSCI_ACWI_FN', 'MSCI_EUROPE'], '1c': ['MSCI_USA', 'MSCI_ACWI_IN', 'MSCI_ACWI_CD', 'MSCI_ACWI_IT', 'MSCI_ACWI_FN']} | True |
| 3 (A-prim) | median ΔR²_oos (E) ของ A-prim เทียบฐาน 0.010–0.030 (①a) และ ≤ L2-1 · ต่ำกว่า L2-1/L2-3 ไม่เกิน 0.01 | A-prim ①a=0.0120 (L2-1=0.0266) · ①c=0.0085 (L2-3=0.0147) | False |
| 4 (B VIF) | max VIF [f,e(P4)]<5 ทั้งสองฐาน (ไม่ใช้ fallback) · |corr(e_j,e_k)| train ≤0.6 · corr(e,f) test ≤0.3 | VIF max={'1a': 2.12, '1c': 1.904} · max|corr e,e| train=0.613 · max|corr(e,f)| test=0.548 · fallback={'1a': False, '1c': False} | False |
| 5 (B-all) | B-all: median ΔR²_oos (E) −0.01…+0.02 · ΔBIC>0 → Q1b ไม่ผ่านทั้งสองฐาน · GRS/PY ไม่ปฏิเสธที่ 5% ช่วง test | ①a ΔR²_oos=0.0102 ΔBIC=22.86 · ①c ΔR²_oos=0.0002 ΔBIC=22.62 · GRS p(test) ①a=0.131 ①c=0.256 · PY p_boot ①a=0.207 ①c=0.143 | True |
| 6 (B-prim) | B-prim: median ΔR²_oos (E) 0.005–0.020 · ΔBIC ≤ 0 | ①a ΔR²_oos=0.0000 ΔBIC=0.000 · ①c ΔR²_oos=0.0000 ΔBIC=0.000 | False |
| 7 (drop-one) | median Δ_j R²_oos ในกองหลัก ภายใน ±0.03 ของ single-index L2 ทุกดัชนี · ผ่าน Q1a ทั้งสองฐาน ≥5 ใน 6 | Δ(drop-one − single-index L2) = {'1a:MSCI_ACWI_HC': -0.0711, '1a:MSCI_ACWI_UT': 0.0008, '1a:MSCI_EUROPE': -0.0225, '1a:MSCI_INDIA': -0.0872, '1a:MSCI_JAPAN': 0.0309, '1a:MSCI_VIETNAM': -0.0017, '1c:MSCI_ACWI_HC': 0.0984, '1c:MSCI_ACWI_UT': 0.0248, '1c:MSCI_EUROPE': 0.0778, '1c:MSCI_INDIA': -0.0568, '1c:MSCI_JAPAN': 0.0528, '1c:MSCI_VIETNAM': 0.0249} · ผ่าน Q1a ต่อฐาน {'1a': 6, '1c': 6} · Q1a รายดัชนี {'MSCI_ACWI_HC': 'ยังอยู่', 'MSCI_ACWI_UT': 'ยังอยู่', 'MSCI_EUROPE': 'ยังอยู่', 'MSCI_INDIA': 'ยังอยู่', 'MSCI_JAPAN': 'ยังอยู่', 'MSCI_VIETNAM': 'ยังอยู่'} | False |
| 8 (span) | span test (i)(ii) ≤1e-12 จริง (เกณฑ์ 1e-10) · (iii) ≤1e-9 | (i)(ii)+อ้างอิง max=4.55e-13 · (iii) max=1.15e-10 | True |
| 9 (C placebo) | placebo เลือก 0 ตัวทั้ง shift 26/52 → τ=0 | เลือก {26: 0, 52: 0} · best_score_step1 {26: 6.892, 52: 6.586} · τ=0.000 | True |
| 10 (C-blk) | m=2–5 · ตัวแรก ∈ {CHINA_ALL, ASIA_EX_JAPAN, USA, IT} · R²_oos E 0.40–0.55 (>③a 0.326, <①a 0.618) · ΔBIC(E) เทียบ ③a < −20 | บล็อก (1): ['MSCI_ACWI_CD'] · R²_oos E C-blk=0.281 (③a=0.326 · ①a=0.618) · ΔBIC(E) เทียบ ③a=-5.5 | False |
| 11 (C-prim) | C-prim: ΔR²_oos จาก C-blk 0.02–0.06 · ต่ำกว่า ①a · ACWI_CD ที่ ETF ธีมเป็นตัวเลือก ≥15 กอง · THD เป็นตัวเลือกกอง L2 primary=ASEAN ≥1 | ΔR²_oos C-prim เทียบ C-blk=0.2160 · R²_oos E=0.580 (①a 0.618) · กลุ่ม ACWI_CD ใน EVAL=40 กอง ที่ C-prim เป็น ETF ธีม=23 · L2 primary=ASEAN แล้ว C-prim=THD 4 กอง | False |
| 12 (elastic net) | ①a: ดัชนี π≥0.6 ใน ≥7 กลุ่ม ครอบ P4 ≥4 · Europe π ต่ำกว่า India/Vietnam/HC · ETF ธีม ≥1 ตัวถึงเกณฑ์ | ①a: P4 ที่ π≥0.6 ใน ≥7 กลุ่ม = 6/6 · med π primary Europe=1.000 vs India/Vietnam/HC=[1.0, 1.0, 1.0] · ETF ที่ถึงเกณฑ์ (≥1 กลุ่ม)=['QQQ', 'SOXX', 'ARKK', 'ICLN', 'IBB', 'KWEB', 'THD', 'EIDO', 'EPHE', 'EWM', 'EWS', 'REET', 'IGF', 'DBC'] | False |
| 13 (Q3) | ตรงแอป 50–75% · กลุ่มที่ L2 primary เป็นดัชนีรวมตรงสูงกว่ากลุ่มอื่น | L2 ตรงแอป (country หรือ sector) 0.611 (n=108) · baseline 0.118 · ดัชนีรวม=0.333 vs อื่น=0.704 | False |
| 14 (เสถียร) | r ดิบ (E) ของ B-all ≥0.6 แต่ต่ำกว่าฐาน (0.804) | r ดิบ (E) median ข้าม factor: B-all vs ฐาน {'1a': (0.65, 0.813), '1c': (0.637, 0.8)} | True |
| 15 (รายเดือน) | ΔR²_oos รายเดือนของ A-prim/B-prim สูงกว่ารายสัปดาห์ | รายเดือน vs รายสัปดาห์ ΔR²_oos(E) {'1a:A-prim': (0.0037, 0.012), '1a:B-prim': (0.0, 0.0), '1c:A-prim': (0.003, 0.0085), '1c:B-prim': (0.0, 0.0)} | False |

## 11. การตัดสินใจของ analyst (ดู `decisions_pre_run.md`)
- PY/p_boot ของ R3, R5, R8, R10 = N/A (K ต่างรายกอง) · test 39 ใช้เกณฑ์ π ตัวอื่น ≤ 0.6 แทน 0.3 · Q2 ธง (4) ใช้ median ข้าม factor · เกณฑ์หยุด A1 = (ก) + (ข) เชิงบรรยาย
## 12. ต้องให้ผู้ใช้ตัดสินใจ
ไม่มีข้อที่ analyst ต้องหยุด (ผลเลือกชุดสุดท้ายเป็นของผู้ใช้ที่ gate L3)

## 13. การรันก่อนรอบสุดท้าย (เพิ่มหลังรีวิวผล · m8 · ค่าชั่วคราวข้อ 66) — แก้เฉพาะข้อความ ไม่รันใหม่ ไม่เปลี่ยนตัวเลข/CSV
- ลำดับจริง: `decisions_pre_run.md` → รันข้อมูลจริงเต็มชุด **1 รอบ** (ลง `scratch/factor-analyst_s006_dbg`, runtime 68.5s, ไม่มี Traceback) → แก้ 2 ไฟล์ → รันสุดท้าย 2 รอบ (`runs/S006` + `scratch/factor-analyst_s006_run2`) → `repro_check.json` ตรง 32 ไฟล์. ก่อนรอบ dbg รันเฉพาะ pytest และ regression S003/S005 (ไม่ใช่การรัน S006)
- **diff กู้ไม่ได้** (ไฟล์ไม่อยู่ใน git · โฟลเดอร์ dbg ถูกลบก่อนรอบสุดท้าย) → บรรยายทีละจุด:
  - `lib/l3.py` (1 จุด): ใน `enet_stability` เพิ่ม `warnings.simplefilter("ignore", FutureWarning)` ต่อจากตัวกรอง ConvergenceWarning เดิม (กัน sklearn 1.9 เตือน `n_alphas` ซ้ำท่วม stdout) · ไม่แตะการคำนวณ
  - `run.py` (ก่อนรอบ dbg เขียนเสร็จแล้วแก้ก่อนสั่งรัน): (1) ลบคอลัมน์ `vif_dimson` ที่เขียนผิดใน B ใส่ `vif_dimson_max_all` แทน (2) เปลี่ยนการคิด Dimson VIF ของ e_j ใน Q1 เป็น max(lag0, lag1) ของคอลัมน์ j (3) ลบโค้ดตกค้างในลูป stability และ `if False` ในรายเดือน (4) เขียน expectation ข้อ 15 ใหม่ให้เทียบรายเดือนกับรายสัปดาห์ (5) ความคลาดเคลื่อน t_HAC ใน span (i) ตั้ง 1e-8 (อื่น 1e-10)
  - `run.py` (หลังรอบ dbg): เพิ่มหัวข้อ 5.9–5.11 (`bprim_subset.csv`, `primary_C_by_group.csv`, สถิติ elastic net) — เป็นการรายงานเพิ่ม ไม่เปลี่ยนไฟล์เดิม
- ยืนยัน: select_C ทุกบรรทัดของรอบ dbg (ACWI_CD −2.098151 ; USA +0.211464 ; stop_tau) เหมือนรอบสุดท้ายทุกค่าที่เห็น (analyst เทียบจากผลที่อ่านตอนนั้น ไม่ได้เก็บไฟล์ dbg ไว้เทียบ hash ซ้ำ · reviewer ตรวจว่าตรงทุกบรรทัด)

## 14. ข้อสังเกตจากรีวิวผล (ข้อความล้วน)
- **m2:** เกณฑ์ π ≥ 0.6 ของ elastic net ใกล้ระดับ noise (ข้อมูลจำลอง ~0.49 ต่อดัชนีไม่จริง · ต่อกอง ~4.2–4.4 ดัชนีจาก 43 ถึง 0.6) → อ้างเฉพาะ π ≥ 0.8 หรือไม่อ้างจำนวนกอง · test 39 ใช้เกณฑ์ผ่อน (decisions ข้อ 2)
- **m4:** B-prim บนกองเดียวกัน (38 กอง E) ตรง L2-1/L2-3 ทุกหลัก (span test ii ≤ 4.55e-13) จึง**ไม่ใช่ผลใหม่** · `bprim_subset.csv` = ชุดย่อยที่ P4 ถูกเลือก ไม่ใช่หลักฐานใหม่
- **m6:** baseline Q3 ของกลุ่มย่อย "ดัชนีรวมใน L2" สลับป้ายภายในกลุ่มย่อย (ไม่ใช่ภายใน policy) → ใช้เทียบได้เฉพาะแถว policy ทั้งหมด: baseline 0.146 (กลุ่มย่อยทั้งชุด) vs 0.118 (policy) · ตัวหลัก 61.1% vs 11.8%
- **m7:** C closure max 1.15e-10 มาจาก `t_alpha_hac` ที่ analyst เพิ่มเอง · ตัวชี้ตาม spec (adj R², R²_oos, α, BIC) สูงสุด 3.4e-11 (เกณฑ์ 1e-8)
- **m10:** placebo Wald ของ B-all (วนเลื่อน 26/52) เกิน 8% ใน 9 จาก 24 คู่ (ฐาน × ดัชนี × shift) → Wald B เป็นบรรยาย ไม่ใช้เป็นเกณฑ์
