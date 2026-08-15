#!/usr/bin/env python3
"""
t_fin_array_stationary.py — 案例 TFinArrayStationary 验证（孤立翅 1D cosh 解析解）

案例: TFinArrayStationary (src/analytic/TFinArrayStationary.java)。
物理: HeatTransfer 稳态, 基板(0.05×0.02×0.005) + 5 翅片(0.001×0.02×0.10, Array 阵列,
      间距 0.0075)。基板底面 z=0 定温 T0=350K, 其余外表面对流 h=25 W/m²K → Tinf=293K。
      材料 k=200 W/mK 全域。自动网格 autoMeshSize=3。

解析解（孤立翅 1D, 对流端, 均匀截面）:
  θ(z) = T(z)-Tinf
  θ(z)/θ_b = [cosh(m(L-s)) + (h/mk)·sinh(m(L-s))] / [cosh(mL) + (h/mk)·sinh(mL)]
  s = z - baseZ (距根部), L = finL = 0.10 (翅高), m² = h·P/(k·A_c)
  P=2(w+t)=0.042, A_c=w·t=2e-5 → m=16.20, mL=1.62, h/(mk)=0.00772
  Bi_c = h·t/(2k) = 6.25e-5 << 0.05 (横向均匀假设成立)

1D 假设的成立条件（设计值）: 低 Bi 翅 (Bi_c<<0.05), mL∈[1,2] (显著降温但未过冷)。
基板底定温 → 翅根温度 ≈ T0 但受基板导热影响略低于 350K,
故 **θ_b 用 FE 根部平面拟合** (不硬编码 350K), 只校验廓线形状比 (消除基温误差)。

检查 (形状比对, 逐点, 窄容差):
  - profile_cosh: 翅中面廓线逐点 |θ(z)/θ_b - cosh_ratio(z)| 相对偏差 < 8% (clean zone)
  - root_fit:     θ_b 拟合值 ∈ [0.95, 1.05]·(T0-Tinf) (根部接近基温, 合理性)
  - tip_ratio:    翅尖 θ_tip/θ_b vs 解析值 [0.21, 0.33] 带内
  - monotone:     翅根→尖 T 单调递减 (无异常翻转)

CSV 列: x,y,z,T (4 列)。

用法:
    python t_fin_array_stationary.py <csv-path> <json-out> <md-out>
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common import CASE_KEY, check, emit_report, load_csv

CASE_KEY = "TFinArray"

# 物性/几何 (与 Java 一致)
K = 200.0       # W/mK
H = 25.0        # W/m²K
T0 = 350.0
TINF = 293.0
BASEZ = 0.005   # 翅根面 z
FINL = 0.10     # 翅高
FINY = 0.02     # 翅深 (y)
FINX0 = 0.005   # 首翅 x
PITCH = 0.0075  # 翅距
# 孤立翅解析参数
P_PER = 2 * (0.02 + 0.001)   # 湿周 0.042
A_C = 0.02 * 0.001           # 截面积 2e-5
M = (H * P_PER / (K * A_C)) ** 0.5
ML = M * FINL
HMK = H / (M * K)
# clean zone: 距根部 3 倍翅厚起, 避开根部圣维南/基板耦合; 尖端也留边 (L-5t)
CLEAN_LO = BASEZ + 3 * 0.001
CLEAN_HI = BASEZ + FINL - 5 * 0.001


def cosh_ratio(s):
    """孤立翅解析解 θ(s)/θ_b, s = 距根部距离。"""
    x = ML - M * s
    return (np.cosh(x) + HMK * np.sinh(x)) / (np.cosh(ML) + HMK * np.sinh(ML))


def main():
    if len(sys.argv) < 4:
        print(__doc__, file=sys.stderr)
        sys.exit(2)
    csv_path, json_out, md_out = sys.argv[1], sys.argv[2], sys.argv[3]

    headers, rows = load_csv(csv_path)
    checks = []
    if len(rows) == 0:
        checks.append(check("data_present", False, None, "non-empty CSV", "rows"))
        return emit_report(CASE_KEY, csv_path, checks, json_out, md_out)

    if len(rows[0]) < 4:
        checks.append(check("data_columns", False, len(rows[0]), "need 4 cols", ""))
        return emit_report(CASE_KEY, csv_path, checks, json_out, md_out)

    arr = np.array(rows, dtype=float)
    x, y, z, T = arr[:, 0], arr[:, 1], arr[:, 2], arr[:, 3]

    # 取中间翅 (x≈finX0+2*pitch) 的翅中面 (y≈FINY/2) 内点
    mid_fin = FINX0 + 2 * PITCH
    in_fin = (np.abs(x - mid_fin) < 4e-4) & (np.abs(y - FINY / 2) < 4e-4) & (z >= BASEZ) & (z <= BASEZ + FINL)
    if in_fin.sum() < 20:
        checks.append(check("fin_samples", False, int(in_fin.sum()), ">=20 in-fin samples", ""))
        return emit_report(CASE_KEY, csv_path, checks, json_out, md_out)

    zs, Ts = z[in_fin], T[in_fin]
    theta = Ts - TINF

    # ---- root_fit: 根部平面 (z 略高于 baseZ) 拟合 θ_b ----
    root_mask = (zs >= BASEZ) & (zs < BASEZ + 1e-3)
    if root_mask.sum() == 0:
        checks.append(check("root_fit", False, None, "no root samples", ""))
        return emit_report(CASE_KEY, csv_path, checks, json_out, md_out)
    theta_b = float(np.mean(theta[root_mask]))
    norm = T0 - TINF
    checks.append(check("root_fit", 0.95 * norm <= theta_b <= 1.05 * norm,
                        round(theta_b, 1), "theta_b in [0.95,1.05]*(T0-Tinf)", "K"))

    # ---- profile_cosh: clean zone 廓线逐点比对 (相对偏差) ----
    cz = (zs >= CLEAN_LO) & (zs <= CLEAN_HI)
    if cz.sum() < 10:
        checks.append(check("profile_cosh", False, int(cz.sum()), ">=10 clean-zone samples", ""))
        return emit_report(CASE_KEY, csv_path, checks, json_out, md_out)

    s_arr = zs[cz] - BASEZ
    t_arr = theta[cz]
    ratio_fe = t_arr / theta_b
    ratio_an = cosh_ratio(s_arr)
    # 相对偏差 (相对解析值)
    rel = np.abs(ratio_fe - ratio_an) / ratio_an
    max_rel = float(rel.max())
    checks.append(check("profile_cosh", max_rel < 0.08, round(max_rel, 4),
                        "max |ratio_fe/ratio_an - 1| < 8% (clean zone)", ""))

    # ---- tip_ratio: 翅尖带 θ_tip/θ_b vs 解析 ----
    tip_mask = zs >= BASEZ + FINL - 2e-3
    if tip_mask.sum() > 0:
        ratio_tip_fe = float(np.mean(theta[tip_mask] / theta_b))
        ratio_tip_an = float(cosh_ratio(FINL))
        lo, hi = ratio_tip_an * 0.8, ratio_tip_an * 1.2
        checks.append(check("tip_ratio", lo <= ratio_tip_fe <= hi,
                            round(ratio_tip_fe, 4),
                            f"tip theta/theta_b in [{lo:.3f},{hi:.3f}]", ""))
    else:
        checks.append(check("tip_ratio", False, None, "no tip samples", ""))

    # ---- monotone: 翅内 T 沿 z 单调递减 ----
    # 分 bin 求均值, 检查均值序列非增
    bins = np.arange(BASEZ, BASEZ + FINL, 0.01)
    means = [float(theta[(zs >= b) & (zs < b + 0.01)].mean()) for b in bins]
    mono = all(means[i] >= means[i + 1] - 0.5 for i in range(len(means) - 1))
    checks.append(check("monotone", mono, None, "fin theta monotonically decreasing", ""))

    # ---- av_temperature: 全域体平均温度合理 (在 Tinf 与 T0 之间) ----
    tavg = float(T.mean())
    checks.append(check("av_temperature", TINF < tavg < T0, round(tavg, 1),
                        "volume-avg T in (Tinf, T0)", "K"))

    evidence = {
        "analytic": "isolated fin 1D: cosh profile, m=%.3f, mL=%.2f, h/(mk)=%.4f"
                    % (M, ML, HMK),
        "theta_b": round(theta_b, 1),
        "max_rel_dev": round(max_rel, 4),
        "av_temperature": round(tavg, 1),
    }
    return emit_report(CASE_KEY, csv_path, checks, json_out, md_out, evidence=evidence)


if __name__ == "__main__":
    sys.exit(main())
