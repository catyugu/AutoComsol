#!/usr/bin/env python3
"""
tm_slab_nonlinear.py — 实验 TmSlab: 3D 平板非线性导热稳态（k(T), 变量变换解析解）验证

案例: TmSlabNonlinear (src/TmSlabNonlinear.java)。
物理: HeatTransfer(ht) 纯固体传热, 稳态 Stationary。
几何: 3D 立方体 (Block L=0.2m, 中心原点, 单域)。
材料: 非线性热导率 k(T)=k0·(1+beta·(T-Tref)), k0=50, beta=0.004[1/K], Tref=293K。
热:   x=-L/2: Dirichlet T=T1=600K;  x=+L/2: Dirichlet T=T2=300K; 其余面绝热。

解析解 (变量变换法, 非线性导热 exact):
  k(T) = k0·(1+beta·(T-Tref)), 引入 phi = T + beta·T²/2 - beta·Tref·T,
  则 d/dx [k(T)·dT/dx] = 0 → d²phi/dx² = 0 → phi 沿 x 线性:
    phi(x) = phi1 + (phi2-phi1)·(x+L/2)/L,  phi_i = T_i + beta·T_i²/2 - beta·Tref·T_i
  反解: T = (-a + sqrt(a² + 2·beta·phi))/beta, a = 1 - beta·Tref
  线性参考解 (beta=0): T_lin(x) = T1 + (T2-T1)·(x+L/2)/L
  非线性中点 T_mid≈476.76 K vs 线性中点 450 K → 偏差 26.8 K (非线性效果显著)。

CSV 列: x,y,z,T (K)。稳态 4 列 (无表头)。

检查:
  - T_profile:         全空间 |T-T_analytic(x)| < 5 K
  - T_nonlinear_effective: 中点非线性解与线性解分离 > 10 K, 且数值解贴近非线性解析解
  - T_range:           T ∈ [290,610] K (边界值 300/600 成立)
  - T_monotonic:       左半均值 > 右半均值 (T 沿 x 单调递减)

用法:
    python tm_slab_nonlinear.py <csv-path> <json-out> <md-out>
"""
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import CASE_KEY, check, emit_report, load_csv

CASE_KEY = "TmSlab"

# ---- 物理参数 (与 TmSlabNonlinear.java 一致) ----
L = 0.2
T1 = 600.0
T2 = 300.0
TREF = 293.0
K0 = 50.0
BETA = 0.004


def phi_of(T):
    """变量变换: phi = T + beta·T²/2 - beta·Tref·T。"""
    return T + BETA * T * T / 2.0 - BETA * TREF * T


def T_from_phi(phi):
    """变量变换反解: T = (-a + sqrt(a² + 2·beta·phi))/beta, a = 1 - beta·Tref。"""
    a = 1.0 - BETA * TREF
    return (-a + math.sqrt(a * a + 2.0 * BETA * phi)) / BETA


def analytic_T(x):
    """非线性解析解 T(x)。"""
    phi1 = phi_of(T1)
    phi2 = phi_of(T2)
    phi = phi1 + (phi2 - phi1) * (x + L / 2.0) / L
    return T_from_phi(phi)


def linear_T(x):
    """线性参考解 (beta=0)。"""
    return T1 + (T2 - T1) * (x + L / 2.0) / L


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

    # ---- T_profile: 全空间对解析解 ----
    devs = [abs(row[tcol] - analytic_T(row[0])) for row in rows]
    pdev = max(devs)
    checks.append(
        check(
            "T_profile",
            pdev < 5.0,
            pdev,
            "max|T-T_analytic(x)| < 5 K",
            "K",
        )
    )

    # ---- T_nonlinear_effective: 中点非线性 vs 线性解分离 ----
    # 数值中点取 x≈0 的平均; 与非线性解析解(476.76)对比, 与线性解(450)对比。
    mid = [row[tcol] for row in rows if abs(row[0]) < 0.01]
    if mid:
        T_num_mid = float(np.mean(mid))
        T_anl_mid = analytic_T(0.0)
        T_lin_mid = linear_T(0.0)
        separation = T_anl_mid - T_lin_mid
        dev_analytic = abs(T_num_mid - T_anl_mid)
        dev_linear = abs(T_num_mid - T_lin_mid)
        ok = separation > 10.0 and dev_analytic < dev_linear
        checks.append(
            check(
                "T_nonlinear_effective",
                ok,
                {
                    "separation_mid": round(separation, 2),
                    "dev_analytic": round(dev_analytic, 3),
                    "dev_linear": round(dev_linear, 3),
                },
                "|T_anl(mid)-T_lin(mid)|>10K; T_numeric near analytic",
                "K",
            )
        )
    else:
        checks.append(
            check("T_nonlinear_effective", False, None, "no mid-plane samples", "K")
        )

    # ---- T_range ----
    Ts = [row[tcol] for row in rows]
    Tmin, Tmax = min(Ts), max(Ts)
    checks.append(
        check(
            "T_range",
            290.0 <= Tmin and Tmax <= 610.0,
            [round(Tmin, 1), round(Tmax, 1)],
            "T in [290,610] K",
            "K",
        )
    )

    # ---- T_monotonic: 左半均值 > 右半均值 ----
    left = [row[tcol] for row in rows if row[0] < 0.0]
    right = [row[tcol] for row in rows if row[0] > 0.0]
    if left and right:
        ml, mr = float(np.mean(left)), float(np.mean(right))
        checks.append(
            check(
                "T_monotonic",
                ml > mr,
                [round(ml, 2), round(mr, 2)],
                "mean T(left half) > mean T(right half)",
                "K",
            )
        )
    else:
        checks.append(check("T_monotonic", False, None, "no left/right samples", "K"))

    evidence = {
        "analytic": "Variable transform phi=T+beta*T^2/2-beta*Tref*T -> linear in x; "
        "T=(-a+sqrt(a^2+2*beta*phi))/beta, a=1-beta*Tref",
        "k(T)": "k0*(1+beta*(T-Tref)) with beta=0.004",
        "T_mid_analytic": round(analytic_T(0.0), 2),
    }
    return emit_report(CASE_KEY, csv_path, checks, json_out, md_out, evidence=evidence)


if __name__ == "__main__":
    sys.exit(main())
