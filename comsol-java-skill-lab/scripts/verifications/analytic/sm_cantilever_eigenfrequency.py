#!/usr/bin/env python3
"""
sm_cantilever_eigenfrequency.py — 案例 SmCantileverEigenfrequency 验证（欧拉-伯努利模态）

案例: SmCantileverEigenfrequency (src/analytic/SmCantileverEigenfrequency.java)。
物理: SolidMechanics 特征频率, 方形截面悬臂梁 (L=1.5, b=h=0.1, L/h=15), 一端 Fixed。
      材料 E=200GPa, nu=0.3, rho=7850。显式网格 hmax=0.035 (≈b/3)。

解析解（欧拉-伯努利悬臂梁, 方形截面 → 两个一阶弯曲模态退化）:
  f_n = (βL)_n² · sqrt(E·I/(ρ·A·L⁴)) / (2π),  I = b·h³/12 = b⁴/12
  (βL)₁ = 1.875104, (βL)₂ = 4.694091
  → f₁ = 36.19 Hz, f₂ = 226.7 Hz (ratio 6.267)

形状识别（防模态排序错配）: 模态位移 CSV (modes.csv) 每模态 u/v 列,
  |u|>|v| → x 向弯曲 (绕 z 轴), |v|>|u| → y 向弯曲 (绕 x 轴)。
  主检查只断言两个最低频率都 ≈ f₁ (退化对), 不依赖具体排序。

检查:
  - f1_deg1: 最低频率 ∈ [0.92, 1.08]·f₁
  - f1_deg2: 次低频率 ∈ [0.92, 1.08]·f₁ (退化对)
  - f2_pair: 第 3/4 频率 ∈ [0.85, 1.15]·f₂ (二阶弯曲对, 网格分辨则报)
  - shape_identified: 最低两模态一个 x 向弯曲一个 y 向弯曲 (退化对正交)

CSV: freq.csv (模态序号,频率); modes.csv (x,y,z, u,v,w @每模态, 同目录自动推导)。

用法:
    python sm_cantilever_eigenfrequency.py <freq-csv> <json-out> <md-out>
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common import CASE_KEY, check, emit_report, load_csv

CASE_KEY = "SmCantEig"

# 欧拉-伯努利解析 (与 Java 一致)
L, B = 1.5, 0.1
E, RHO = 200e9, 7850.0
I_M = B ** 4 / 12.0
A_C = B * B
BETA1, BETA2 = 1.875104, 4.694091


def f_n(beta):
    return beta * beta * np.sqrt(E * I_M / (RHO * A_C * L ** 4)) / (2 * np.pi)


F1 = f_n(BETA1)
F2 = f_n(BETA2)


def _looks_like_data(cells):
    """表头单元格全是可转 float 的数值 → 实为首数据行被误认作表头。"""
    if not cells:
        return False
    try:
        [float(c) for c in cells]
        return True
    except ValueError:
        return False


def main():
    # 标准契约 3 参数: <freq-csv> <json-out> <md-out>; modes.csv 由 freq.csv 同目录推导。
    if len(sys.argv) < 4:
        print(__doc__, file=sys.stderr)
        sys.exit(2)
    freq_csv, json_out, md_out = sys.argv[1], sys.argv[2], sys.argv[3]
    modes_csv = os.path.join(os.path.dirname(freq_csv), "modes.csv")

    checks = []
    headers, rows = load_csv(freq_csv)
    # Plot 导出无表头行 → 首数据行被 load_csv 误认作表头; 当表头形如数据时回补
    if headers and rows and _looks_like_data(headers):
        rows = [[float(h) for h in headers]] + rows
        headers = None
    if len(rows) < 2:
        checks.append(check("data_present", False, None, ">=2 modes in freq.csv", ""))
        return emit_report(CASE_KEY, freq_csv, checks, json_out, md_out)

    freqs = np.array([r[1] for r in rows if len(r) >= 2])
    freqs = np.sort(freqs)
    if len(freqs) < 4:
        checks.append(check("modes_count", False, len(freqs), ">=4 eigenfrequencies", ""))
        return emit_report(CASE_KEY, freq_csv, checks, json_out, md_out)

    # ---- f1_deg1 / f1_deg2: 两个最低频率都 ≈ f₁ (退化对) ----
    for i, label in [(0, "f1_deg1"), (1, "f1_deg2")]:
        f = float(freqs[i])
        ok = 0.92 * F1 <= f <= 1.08 * F1
        checks.append(check(label, ok, round(f, 2),
                            f"mode{i+1} freq in [0.92,1.08]*f1={F1:.1f} Hz", "Hz"))

    # ---- f2_pair: 第 3/4 频率 ≈ f₂ (报告, 网格分辨则核验) ----
    f3, f4 = float(freqs[2]), float(freqs[3])
    f2_ok = 0.85 * F2 <= f3 <= 1.15 * F2 and 0.85 * F2 <= f4 <= 1.15 * F2
    checks.append(check("f2_pair", f2_ok,
                        f"[{f3:.1f},{f4:.1f}] vs f2={F2:.1f} Hz",
                        "3rd/4th freq in [0.85,1.15]*f2", "Hz"))

    # ---- shape_identified: 最低两模态位移轴正交 (退化对) ----
    # 梁沿 x, 截面在 y-z → 弯曲模态在 y (v) 或 z (w) 方向, 轴向 u 很小。
    # 判断每模态主弯曲方向 (|v| vs |w|), 断言最低两模态正交。
    h2, r2 = load_csv(modes_csv)
    if len(r2) > 0 and len(r2[0]) >= 9:
        arr = np.array(r2, dtype=float)
        # 尖部 (x 最大) 平均位移幅值
        tip = arr[arr[:, 0] > L - 0.1]
        axes = []
        for m in range(4):
            c0 = 3 + m * 3
            vv = np.abs(tip[:, c0 + 1]).mean()
            ww = np.abs(tip[:, c0 + 2]).mean()
            axes.append("y" if vv > ww else "z")
        orth = (axes[0] != axes[1])
        checks.append(check("shape_identified", orth,
                            "axes=" + "".join(axes[:2]),
                            "two lowest modes bend about orthogonal axes", ""))
    else:
        checks.append(check("shape_identified", False, None, "modes.csv unreadable", ""))

    evidence = {
        "analytic": "Euler-Bernoulli: f1=%.2f Hz (betaL=1.8751), f2=%.2f Hz (betaL=4.6941)"
                    % (F1, F2),
        "fe_freqs": [round(float(f), 2) for f in freqs[:4]],
        "shape_axes": axes if len(axes) == 4 else None,
    }
    return emit_report(CASE_KEY, freq_csv, checks, json_out, md_out, evidence=evidence)


if __name__ == "__main__":
    sys.exit(main())
