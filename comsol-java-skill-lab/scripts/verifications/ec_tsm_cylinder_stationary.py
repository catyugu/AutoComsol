#!/usr/bin/env python3
"""
ec_tsm_cylinder_stationary.py — 实验 EcTSmCylinderStationary: 3D 同轴双材料稳态电→热→力耦合 验证

案例: ETM1 (src/EcTSmCylinderStationary.java)。
物理: ConductiveMedia(ec) + HeatTransfer(ht) + SolidMechanics(solid)
      + ElectromagneticHeating (焦耳热→热) + ThermalExpansion 域特征 (热→力)。
几何: 3D 同轴圆柱（内芯 r1=0.15 + 外壳 r1<r<r2=0.3, L=1, 中心原点, 2 个域）。
电:   顶面 V0=0.3V, 底面 Ground; 电流只流经内芯(外壳 σ≈0 绝缘)。
热:   全对流 h=200 → T∞=293K; 稳态径向温度（内芯抛物线 + 外壳对数）。
力:   广义平面应变 ε_z=0（两端 Roller uz=0, 径向自由）+ 刚体抑制。

解析解（E,ν 两相相同, α 分片不同 → 界面自动连续, 单常数解）:
  温度（中平面 z≈0, 与 ET2 相同）:
    T_c(r)=T∞+Q1·r1²/(2r2h)+Q1·r1²/(2k2)·ln(r2/r1)+Q1·(r1²-r²)/(4k1)   内芯
    T_o(r)=T∞+Q1·r1²/(2r2h)+Q1·r1²/(2k2)·ln(r2/r)                       外壳
  热应力（ε_z=0 轴对称）:
    定义 ψ(r)=α(r)·(T(r)-Tref), Q(r)=∫₀ʳ ψ(r')·r' dr'（分片）
    m=(1+ν)/(1-ν), G=E/(2(1+ν)), λ=Eν/((1+ν)(1-2ν))
    C1 = G·m·Q(r2) / ((λ+G)·r2²)
    σ_r(r) = -2G·m·Q(r)/r² + 2(λ+G)C1
    σ_θ(r) = -2G·m·ψ(r) + 2G·m·Q(r)/r² + 2(λ+G)C1
    σ_z(r) = 2λ·C1 - 2G·m·ψ(r)
  注意: σ_θ, σ_z 在界面 (α 跳跃) 不连续, 采样避开界面窄带。

CSV 列: x,y,z,V (V),T (K),solid.sx (Pa),solid.sy (Pa),solid.sz (Pa),solid.disp。
验证在 y=0 半轴 (θ=0): σ_r=sx, σ_θ=sy, σ_z=sz。

用法:
    python etm1_coaxial_stationary.py <csv-path> <json-out> <md-out>
"""
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import CASE_KEY, check, emit_report, load_csv

CASE_KEY = "EcTSmCyl"

# ---- 物理参数 (与 ETM1.java 一致) ----
R1 = 0.15
R2 = 0.30
L = 1.0
V0 = 0.3
SIGMA1 = 1.0e6
K1 = 15.0
K2 = 30.0
TINF = 293.0
H = 200.0
E = 200.0e9
NU = 0.3
ALPHA1 = 1.2e-5
ALPHA2 = 0.6e-5
TREF = 293.0

Q1 = SIGMA1 * (V0 / L) ** 2  # 内芯均匀焦耳热 W/m^3


# ---- 温度解析解 ----
def T_core(r):
    """内芯温度（含源抛物线）。"""
    return (TINF
            + Q1 * R1 * R1 / (2 * R2 * H)
            + Q1 * R1 * R1 / (2 * K2) * math.log(R2 / R1)
            + Q1 * (R1 * R1 - np.asarray(r, float) ** 2) / (4 * K1))


def T_shell(r):
    """外壳温度（无源对数）。"""
    r = np.asarray(r, float)
    return (TINF
            + Q1 * R1 * R1 / (2 * R2 * H)
            + Q1 * R1 * R1 / (2 * K2) * np.log(R2 / np.maximum(r, 1e-9)))


def T_analytic(r):
    """分片温度。r 为标量或数组。"""
    r = np.asarray(r, float)
    return np.where(r <= R1, T_core(r), T_shell(r))


def alpha_r(r):
    """分片热膨胀系数。"""
    r = np.asarray(r, float)
    return np.where(r <= R1, ALPHA1, ALPHA2)


# ---- 热应力解析解（广义平面应变 ε_z=0, E,ν 两相相同）----
G = E / (2 * (1 + NU))
LAM = E * NU / ((1 + NU) * (1 - 2 * NU))
M = (1 + NU) / (1 - NU)


def Q_integral(psi_r, rr):
    """Q(r)=∫₀ʳ ψ·r' dr', 分片数值积分。psi_r/rr 为网格数组。"""
    return np.trapezoid(psi_r * rr, rr)


def stress_analytic(r_grid):
    """在 1D 径向网格 r_grid 上解析计算 σ_r, σ_θ, σ_z。

    返回 (sigr, sigt, sigz) 数组。
    """
    r = np.asarray(r_grid, float)
    rr = np.linspace(1e-9, R2, 20001)
    TT = T_analytic(rr)
    psi = alpha_r(rr) * (TT - TREF)
    Q_total = Q_integral(psi, rr)  # Q(r2)

    # C1 = G·m·Q(r2) / ((λ+G)·r2²)
    C1 = G * M * Q_total / ((LAM + G) * R2 * R2)

    # 对每个采样点, 数值积分 Q(r)
    sigr = np.zeros_like(r)
    sigt = np.zeros_like(r)
    sigz = np.zeros_like(r)
    for i, ri in enumerate(r):
        mask = rr <= ri
        Qi = np.trapezoid(psi[mask] * rr[mask], rr[mask])
        psii = alpha_r(ri) * (T_analytic(ri) - TREF)
        sigr[i] = -2 * G * M * Qi / (ri * ri) + 2 * (LAM + G) * C1
        sigt[i] = -2 * G * M * psii + 2 * G * M * Qi / (ri * ri) + 2 * (LAM + G) * C1
        sigz[i] = 2 * LAM * C1 - 2 * G * M * psii
    return sigr, sigt, sigz


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

    # 列: x=0,y=1,z=2,V=3,T=4,sx=5,sy=6,sz=7,disp=8
    vcol, tcol = 3, 4
    sx, sy, sz = 5, 6, 7

    # ---- V_linear_core: 内芯 V=V0·(z+0.5)/L ----
    vdevs = []
    for row in rows:
        if r_of(row[0], row[1]) < R1 - 0.02:
            vdevs.append(abs(row[vcol] - V0 * (row[2] + 0.5) / L))
    if vdevs:
        vmax = max(vdevs)
        checks.append(check("V_linear_core", vmax < 1e-3, vmax,
                            "max|V-V0(z+0.5)/L| < 1e-3 V (core)", "V"))
    else:
        checks.append(check("V_linear_core", False, None, "no core samples", "V"))

    # ---- T_profile: 中平面 (r,T) 对分片温度解析解 ----
    mid_rows = [row for row in rows if abs(row[2]) < 0.02]
    if mid_rows:
        tdevs = [abs(row[tcol] - T_analytic(r_of(row[0], row[1]))) for row in mid_rows]
        tmax = max(tdevs)
        checks.append(check("T_profile", tmax < 3.0, tmax,
                            "max|T-T_analytic(r)| < 3 K (mid-plane)", "K"))
    else:
        checks.append(check("T_profile", False, None, "no mid-plane samples", "K"))

    # ---- Stress: 中平面 y≈0 半轴 (θ≈0, σ_r≈sx, σ_θ≈sy) ----
    # 网格节点很少精确落在 y=0, 放宽 |y|<0.03。σ_r/σ_θ 在 θ→0 近似:
    # σ_r = sx cos²θ + sy sin²θ ≈ sx, σ_θ ≈ sy (θ 小)。采样避开界面窄带与轴心/外壁。
    sample = []  # (r, sx, sy, sz)
    for row in mid_rows:
        x, y, z = row[0], row[1], row[2]
        if abs(y) > 0.03:
            continue  # 仅 y≈0 半轴
        r = r_of(x, y)
        if r < 0.02 or abs(r - R1) < 0.008 or abs(r - R2) < 0.008:
            continue  # 避开轴心/界面/外壁
        # θ=atan2(y,x), 用 θ 校正 σ_r/σ_θ (y 小但非零)
        theta = math.atan2(y, x)
        ct, st = math.cos(theta), math.sin(theta)
        sxv, syv = row[sx], row[sy]
        sigr_fem = sxv * ct * ct + syv * st * st + 0.0  # 略去 sxy (θ 小)
        sigt_fem = sxv * st * st + syv * ct * ct
        sample.append((r, sigr_fem, sigt_fem, row[sz]))

    if len(sample) >= 4:
        rr = np.array([s[0] for s in sample])
        fem_sx = np.array([s[1] for s in sample])
        fem_sy = np.array([s[2] for s in sample])
        fem_sz = np.array([s[3] for s in sample])
        sigr, sigt, sigz = stress_analytic(rr)

        dev_r = np.max(np.abs(fem_sx - sigr))
        dev_t = np.max(np.abs(fem_sy - sigt))
        dev_z = np.max(np.abs(fem_sz - sigz))
        # 应力量级参考 (σ_z 量级): 取 σ_z 解析 max
        ref = max(1.0, np.max(np.abs(sigz)))
        checks.append(check("stress_sr", dev_r < 0.15 * ref, float(dev_r),
                            f"max|sx-σ_r| < 15% of σ_z scale", "Pa"))
        checks.append(check("stress_st", dev_t < 0.15 * ref, float(dev_t),
                            f"max|sy-σ_θ| < 15% of σ_z scale", "Pa"))
        checks.append(check("stress_sz", dev_z < 0.15 * ref, float(dev_z),
                            f"max|sz-σ_z| < 15% of σ_z scale", "Pa"))

        # 物理守恒: 外壁 σ_r≈0 (自由壁)
        wall = [row for row in mid_rows
                if abs(row[1]) < 0.03 and r_of(row[0], row[1]) > R2 - 0.03 and abs(row[0]) > 0.1]
        if wall:
            sr_wall = 0.0
            for row in wall:
                theta = math.atan2(row[1], row[0])
                ct, st = math.cos(theta), math.sin(theta)
                sr_wall = max(sr_wall, abs(row[sx] * ct * ct + row[sy] * st * st))
            checks.append(check("sr_wall_zero", sr_wall < 0.05 * ref, float(sr_wall),
                                "max|σ_r| at free outer wall < 5% of σ_z scale", "Pa"))
    else:
        for nm in ("stress_sr", "stress_st", "stress_sz", "sr_wall_zero"):
            checks.append(check(nm, False, None, "no y=0 mid-plane samples", "Pa"))

    evidence = {
        "analytic": "E,nu-equal two-material generalized plane strain (ε_z=0): "
                    "σ_r/σθ/σz from piecewise α·ΔT integral",
        "constraint": "Roller uz=0 top+bottom, RigidMotionSuppression radial",
    }
    return emit_report(CASE_KEY, csv_path, checks, json_out, md_out,
                       evidence=evidence)


if __name__ == "__main__":
    sys.exit(main())
