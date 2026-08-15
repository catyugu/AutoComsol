#!/usr/bin/env python3
"""
t_revolve_stationary.py — 实验 TRevolve: 3D 双层圆环稳态传热（Revolve 旋转体, 双材料）验证

案例: TRevolveStationary (src/TRevolveStationary.java)。
物理: HeatTransfer(ht) 纯固体传热, 稳态 Stationary。
几何: 3D 双层圆环 (Revolve 旋转体): 内环壳 A (r_in=0.1 ≤ r ≤ r_mid=0.25, kA=60) +
      外环壳 B (r_mid ≤ r ≤ r_out=0.4, kB=30), 厚度 t=0.05, 2 个独立域。
热:   内壁 (r=r_in): Dirichlet T=T0=500K。
      外壁 (r=r_out): Robin 对流 h=h_conv=20 → T∞=Tinf=293K。
      环壳间界面 (r=r_mid): 温度 + 热流连续。
      上/下端面 (z=±t/2): 默认绝热 → T 仅径向变化。

解析解 (双层圆环对数分布, 每层 T=A·ln(r)+B):
  T_A(r) = T0 + A_A·ln(r/r_in),   A_A = (T_m-T0)/ln(r_mid/r_in)
  T_B(r) = T_m + A_B·ln(r/r_mid), A_B = (kA/kB)·A_A
  界面温度 T_m 由外壁 Robin + 界面热流连续解得:
    C = (kA/(kB·dA))·(kB/r_out + h·dB),  dA=ln(r_mid/r_in), dB=ln(r_out/r_mid)
    T_m = (C·T0 + h·Tinf)/(C + h)
  实测 T(r_mid)=479.73 (归档 479.728)。

CSV 列: x,y,z,T (K)。稳态 4 列 (无表头, 首数据行被当列名)。

检查:
  - T_inner_wall:      内壁 r≈r_in 处 |T-T0| < 3 K
  - T_inner_zone:      内环 r_in<r<r_mid |T-T_A(r)| < 3 K
  - T_outer_zone:      外环 r_mid<r<r_out |T-T_B(r)| < 3 K
  - interface_continuity: r≈r_mid |T-T(r_mid)| < 3 K
  - radial_only:       每个半径桶内 T 最大散布 < 3 K (验证 T 仅径向依赖)

用法:
    python t_revolve_stationary.py <csv-path> <json-out> <md-out>
"""
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import CASE_KEY, check, emit_report, load_csv

CASE_KEY = "TRevolve"

# ---- 物理参数 (与 TRevolveStationary.java 一致) ----
R_IN = 0.10
R_MID = 0.25
R_OUT = 0.40
T0 = 500.0
TINF = 293.0
H = 20.0
KA = 60.0
KB = 30.0


def analytic_fields():
    """计算界面温度 T_m, 以及内/外层解析系数 A_A, A_B。"""
    dA = math.log(R_MID / R_IN)
    dB = math.log(R_OUT / R_MID)
    C = (KA / (KB * dA)) * (KB / R_OUT + H * dB)
    Tm = (C * T0 + H * TINF) / (C + H)
    A_A = (Tm - T0) / dA
    A_B = (KA / KB) * A_A
    return Tm, A_A, A_B


def t_inner(r):
    """内环解析解 T_A(r)。"""
    r = np.asarray(r, float)
    return T0 + _A_A * np.log(r / R_IN)


def t_outer(r):
    """外环解析解 T_B(r)。"""
    r = np.asarray(r, float)
    return _Tm + _A_B * np.log(r / R_MID)


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

    # 列索引: x=0,y=1,z=2,T=3
    tcol = 3
    global _Tm, _A_A, _A_B
    _Tm, _A_A, _A_B = analytic_fields()

    # ---- T_inner_wall: 内壁 |T-T0| ----
    inner = [
        row[tcol]
        for row in rows
        if abs(r_of(row[0], row[1]) - R_IN) < 0.01
    ]
    if inner:
        wdev = max(abs(T - T0) for T in inner)
        checks.append(
            check(
                "T_inner_wall",
                wdev < 3.0,
                wdev,
                "max|T(r_in)-T0| < 3 K",
                "K",
            )
        )
    else:
        checks.append(check("T_inner_wall", False, None, "no inner wall samples", "K"))

    # ---- T_inner_zone: 内环 T_A(r) ----
    inner_zone = [
        row for row in rows if R_IN + 0.01 < r_of(row[0], row[1]) < R_MID - 0.01
    ]
    if inner_zone:
        devs = [abs(row[tcol] - t_inner(r_of(row[0], row[1]))) for row in inner_zone]
        zdev = max(devs)
        checks.append(
            check(
                "T_inner_zone",
                zdev < 3.0,
                zdev,
                "max|T-T_A(r)| < 3 K",
                "K",
            )
        )
    else:
        checks.append(check("T_inner_zone", False, None, "no inner zone samples", "K"))

    # ---- T_outer_zone: 外环 T_B(r) ----
    outer_zone = [
        row for row in rows if R_MID + 0.01 < r_of(row[0], row[1]) < R_OUT - 0.01
    ]
    if outer_zone:
        devs = [abs(row[tcol] - t_outer(r_of(row[0], row[1]))) for row in outer_zone]
        zdev = max(devs)
        checks.append(
            check(
                "T_outer_zone",
                zdev < 3.0,
                zdev,
                "max|T-T_B(r)| < 3 K",
                "K",
            )
        )
    else:
        checks.append(check("T_outer_zone", False, None, "no outer zone samples", "K"))

    # ---- interface_continuity: r≈r_mid |T-T(r_mid)| ----
    inter = [
        row[tcol]
        for row in rows
        if abs(r_of(row[0], row[1]) - R_MID) < 0.005
    ]
    if inter:
        idev = max(abs(T - _Tm) for T in inter)
        checks.append(
            check(
                "interface_continuity",
                idev < 3.0,
                idev,
                "max|T-T(r_mid)| < 3 K",
                "K",
            )
        )
    else:
        checks.append(
            check("interface_continuity", False, None, "no interface samples", "K")
        )

    # ---- radial_only: 每个半径桶内 T 最大散布 (T 仅径向依赖) ----
    buckets = {}
    for row in rows:
        key = round(r_of(row[0], row[1]), 2)
        buckets.setdefault(key, []).append(row[tcol])
    spreads = [max(v) - min(v) for v in buckets.values() if len(v) >= 2]
    if spreads:
        smax = max(spreads)
        checks.append(
            check(
                "radial_only",
                smax < 3.0,
                smax,
                "max T spread per radius < 3 K",
                "K",
            )
        )
    else:
        checks.append(check("radial_only", False, None, "no radius buckets", "K"))

    evidence = {
        "analytic": "Double-layer annulus: inner Dirichlet + outer Robin, "
        "interface flux continuity, T=A*ln(r)+B per layer",
        "T(r_mid)": round(_Tm, 3),
    }
    return emit_report(CASE_KEY, csv_path, checks, json_out, md_out, evidence=evidence)


if __name__ == "__main__":
    sys.exit(main())
