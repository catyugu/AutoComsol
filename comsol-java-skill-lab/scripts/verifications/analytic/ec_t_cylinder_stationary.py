#!/usr/bin/env python3
"""
ec_t_cylinder_stationary.py — 实验 ET2: 3D 同轴双材料电热耦合稳态 验证

案例: EcTCylinderStationary (src/analytic/EcTCylinderStationary.java)。
物理: ConductiveMedia(ec) + HeatTransfer(ht) + ElectromagneticHeating 耦合。
几何: 3D 同轴圆柱（内芯 r1=0.15 + 外壳 r1<r<r2=0.3, L=2, 中心原点, 2 个域）。
电:   顶面 V0=0.6V, 底面 Ground; 电流只流经内芯(外壳 σ≈0 绝缘)。
      内芯 V(z)=V0·(z+L/2)/L 线性, E=V0/L=0.3 V/m, J=σ1E, 焦耳热 Q1=σ1(V0/L)²。
热:   侧面 + 顶面 + 底面 全部对流 h=200 → T∞=293K（无绝热）。
      内芯 k1=15, 外壳 k2=30。

解析解（中平面 z=0 严格对称面, ∂T/∂z=0; 端面散热对中平面的影响要求 L 足够大:
L=2 时实测中平面偏差 0.27 K, L=1 时为 3.1 K）:
  内芯 0≤r≤r1 (含源抛物线):  T_c(r)=T∞+Q1·r1²/(2r2h)+Q1·r1²/(2k2)·ln(r2/r1)
                                    +Q1·(r1²-r²)/(4k1)
  外壳 r1≤r≤r2 (无源对数):    T_o(r)=T∞+Q1·r1²/(2r2h)+Q1·r1²/(2k2)·ln(r2/r)
  电流: V(z)=V0·(z+0.5)/L, 外壳内 V≈0（绝缘, 无电流）。

CSV 列: x,y,z,V (V),T (K)。稳态 5 列。

检查:
  - V_linear_core: 内芯(r<r1) z 轴 V=V0·(z+0.5)/L
  - V_zero_shell:  外壳(r>r1) 内 V≈0 (绝缘无电流)
  - T_core_profile: 中平面内芯 0≤r≤r1 对抛物线解析解
  - T_shell_profile: 中平面外壳 r1≤r≤r2 对对数解析解
  - interface:      r≈r1 处温度连续 (内芯/外壳解析解衔接)
  - convection:     外壁 r≈r2 处 T-T∞ 与对流散热自洽 (T_s(r2) 解析)
  - z_symmetry:     z 对称点温度一致 (顶/底对流对称)

用法:
    python ec_t_cylinder_stationary.py <csv-path> <json-out> <md-out>
"""
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common import CASE_KEY, check, emit_report, load_csv

CASE_KEY = "ET2"

# ---- 物理参数 (与 EcTCylinderStationary.java 一致) ----
R1 = 0.15
R2 = 0.30
L = 2.0
V0 = 0.6
SIGMA1 = 1.0e6
SIGMA2 = 1.0e-8
K1 = 15.0
K2 = 30.0
TINF = 293.0
H = 200.0

Q1 = SIGMA1 * (V0 / L) ** 2  # 内芯均匀焦耳热 W/m^3


def steady_core(r):
    """内芯解析解 (含源抛物线)。"""
    r = np.asarray(r, float)
    return (
        TINF
        + Q1 * R1 * R1 / (2 * R2 * H)
        + Q1 * R1 * R1 / (2 * K2) * math.log(R2 / R1)
        + Q1 * (R1 * R1 - r * r) / (4 * K1)
    )


def steady_shell(r):
    """外壳解析解 (无源对数)。"""
    r = np.asarray(r, float)
    return (
        TINF
        + Q1 * R1 * R1 / (2 * R2 * H)
        + Q1 * R1 * R1 / (2 * K2) * np.log(R2 / np.maximum(r, 1e-9))
    )


def r_of(x, y):
    return math.sqrt(x * x + y * y)


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

    # 列索引: x=0,y=1,z=2,V=3,T=4,normJ=5
    vcol, tcol, jcol = 3, 4, 5
    has_J = len(rows[0]) >= 6

    # ---- V_linear_core: 内芯 V=V0·(z+L/2)/L ----
    vdevs = []
    for row in rows:
        r = r_of(row[0], row[1])
        if r < R1 - 0.02:
            vdevs.append(abs(row[vcol] - V0 * (row[2] + L / 2) / L))
    if vdevs:
        vmax = max(vdevs)
        checks.append(
            check(
                "V_linear_core",
                vmax < 1e-3,
                vmax,
                "max|V-V0(z+L/2)/L| < 1e-3 V (core)",
                "V",
            )
        )
    else:
        checks.append(check("V_linear_core", False, None, "no core samples", "V"))

    # ---- J_insulating_shell: 外壳电流密度≈0 (真正绝缘判据) ----
    # 注意: 电位场在外壳内连续(V 线性, Laplace 解), 但绝缘 σ→0 ⇒ J≈0。
    if has_J:
        jsh = [row[jcol] for row in rows if r_of(row[0], row[1]) > R1 + 0.02]
        jmax_sh = max(jsh) if jsh else 0.0
        # 外壳 J 应比内芯 J 小多个量级: 用 J 比值而非绝对值
        jcore = [row[jcol] for row in rows if r_of(row[0], row[1]) < R1 - 0.02]
        jmax_core = max(jcore) if jcore else 0.0
        ratio = jmax_sh / jmax_core if jmax_core > 0 else 1.0
        checks.append(
            check(
                "J_insulating_shell",
                ratio < 1e-3,
                ratio,
                "max J_shell / max J_core < 1e-3 (insulating)",
                "",
            )
        )
    else:
        checks.append(check("J_insulating_shell", False, None, "need normJ column", ""))

    # ---- T_core_profile: 中平面内芯抛物线 ----
    core_mids = [
        row for row in rows if abs(row[2]) < 0.02 and r_of(row[0], row[1]) < R1 - 0.03
    ]
    if core_mids:
        devs = [abs(row[tcol] - steady_core(r_of(row[0], row[1]))) for row in core_mids]
        cdev = max(devs)
        checks.append(
            check(
                "T_core_profile",
                cdev < 3.0,
                cdev,
                "max|T-T_c(r)| < 3 K (core mid-plane)",
                "K",
            )
        )
    else:
        checks.append(
            check("T_core_profile", False, None, "no core mid-plane samples", "K")
        )

    # ---- T_shell_profile: 中平面外壳对数 ----
    shell_mids = [
        row
        for row in rows
        if abs(row[2]) < 0.02
        and r_of(row[0], row[1]) > R1 + 0.03
        and R2 - r_of(row[0], row[1]) > 0.03
    ]
    if shell_mids:
        devs = [
            abs(row[tcol] - steady_shell(r_of(row[0], row[1]))) for row in shell_mids
        ]
        sdev = max(devs)
        checks.append(
            check(
                "T_shell_profile",
                sdev < 3.0,
                sdev,
                "max|T-T_o(r)| < 3 K (shell mid-plane)",
                "K",
            )
        )
    else:
        checks.append(
            check("T_shell_profile", False, None, "no shell mid-plane samples", "K")
        )

    # ---- interface: r≈r1 温度连续 (内芯/外壳解析解在界面同一温度) ----
    # 用窄带 |r-R1|<0.005 采样界面, 避免混入两侧温度梯度。
    both = []
    for row in rows:
        r = r_of(row[0], row[1])
        if abs(row[2]) < 0.02 and abs(r - R1) < 0.005:
            both.append(row[tcol])
    if both:
        T_expected = steady_core(R1)  # = steady_shell(R1), 界面同一温度
        idev = max(abs(T - T_expected) for T in both)
        checks.append(
            check(
                "interface_continuity",
                idev < 3.0,
                idev,
                "max|T-T(r1)| < 3 K at interface",
                "K",
            )
        )
    else:
        checks.append(
            check("interface_continuity", False, None, "no interface samples", "K")
        )

    # ---- convection: 外壁 r≈r2 温度应≈解析外壁温 ----
    wall = [
        row[tcol]
        for row in rows
        if abs(row[2]) < 0.02 and abs(r_of(row[0], row[1]) - R2) < 0.02
    ]
    if wall:
        Twall_analytic = steady_shell(R2)
        wdev = max(abs(T - Twall_analytic) for T in wall)
        checks.append(
            check(
                "convection_wall",
                wdev < 3.0,
                wdev,
                "max|T(r2)-T_analytic(r2)| < 3 K",
                "K",
            )
        )
    else:
        checks.append(check("convection_wall", False, None, "no wall samples", "K"))

    # ---- z_symmetry: z 对称点温度一致 ----
    # 精确配对: 对每个 (x,y,z) 节点, 匹配 (x,y,-z) 的节点 (网格对称)。
    # 用坐标精确匹配(容差1e-3), 避免按半径分桶混入不同位置。
    nodes_by_key = {}
    for row in rows:
        key = (round(row[0], 3), round(row[1], 3), round(abs(row[2]), 3))
        nodes_by_key.setdefault(key, []).append((row[2], row[tcol]))
    sdevs = [
        max(t for _, t in v) - min(t for _, t in v)
        for v in nodes_by_key.values()
        if len(v) >= 2
    ]
    if sdevs:
        smax = max(sdevs)
        checks.append(
            check("z_symmetry", smax < 0.5, smax, "max T asym across z=0 < 0.5 K", "K")
        )
    else:
        checks.append(check("z_symmetry", False, None, "no paired z samples", "K"))

    evidence = {
        "analytic": "Coaxial 2-material: Joule core parabola + insulating shell log, "
        "full convective exterior"
    }
    return emit_report(CASE_KEY, csv_path, checks, json_out, md_out, evidence=evidence)


if __name__ == "__main__":
    sys.exit(main())
