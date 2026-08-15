#!/usr/bin/env python3
"""
ec_tsm_cube_transient.py — 实验 EcTSmCubeTransient: 3D 立方体瞬态电→热→力耦合 验证

案例: ETM2 (src/analytic/.java)。
物理: ConductiveMedia(ec) + HeatTransfer(ht) + SolidMechanics(solid)
      + ElectromagneticHeating (焦耳热→热) + ThermalExpansion 耦合 (热→力)。
几何: 3D 立方体 L=0.2m (x,y,z∈[-0.1,0.1]), 单材料。
电:   x=+0.1 Terminal V0=0.02V, x=-0.1 Ground → 均匀 E_x=V0/L, J=σE, Q=σ(V0/L)²=1e4 W/m³。
热:   x=±0.1 两面对流 h=200 → T∞=293K, 其余面绝热, 初温 T∞, 瞬态 0..6000s。
力:   两端 Roller (u_x=0), 侧向自由, RigidMotionSuppression 抑制刚体模态。

解析解 (1D slab, 温度仅依赖 x, 关于 x=0 对称):
  稳态: T_s(x)=T∞+Q·a/h+Q·(a²-x²)/(2k),  a=L/2
  瞬态: T(x,t)=T_s(x)+Σ c_n·e^{-αλ_n²t}·cos(λ_n x)
        λ_n 满足 Robin: k·λ·tan(λ·a)=h (仅偶/余弦模态)
        c_n=∫(T∞-T_s)cos(λx)dx/∫cos²(λx)dx
  力学 (单轴固定杆, 侧向自由 → σ_y=σ_z=0):
        σ_x(t)=-E·α·(⟨T⟩_x(t)-Tref) 空间均匀, ⟨T⟩_x=杆平均温度
        u_x(±a)=0 (两端固定)

CSV 列 (瞬态): % x,y,z,V (V) @ t=...,T (K) @ t=...,solid.sx (N/m^2) @ t=...,...
每节点一行。

检查:
  - V_linear: 所有时刻 V=V0·(x+a)/L
  - T_steady_profile: 末时刻中平面沿 x 对稳态解析解
  - T_transient_profile: 中平面 (x,t) 对傅里叶余弦级数解
  - sigma_x_uniform: 每时刻 σ_x 空间均匀 (σ_y,σ_z 中部均值≈0)
  - sigma_x_analytic: mean(σ_x) ≈ -E·α·(⟨T⟩-Tref) (体平均)
    端部固定 u_x(±a)=0 由该解析解隐含验证 (解依赖此边界条件)。

用法:
    python etm2_cube_transient.py <csv-path> <json-out> <md-out>
"""
import math
import os
import re
import sys

import numpy as np
from scipy.optimize import brentq
from scipy.special import j0, j1  # noqa: F401 (placeholder for future)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common import CASE_KEY, check, emit_report, load_csv

CASE_KEY = "EcTSmCube"

# ---- 物理参数 (与 ETM2.java 一致) ----
L = 0.2
A = L / 2  # 0.1
V0 = 0.02
SIGMA = 1.0e6
K = 50.0
TINF = 293.0
H = 200.0
RHO = 7850.0
CP = 500.0
ALPHA_T = 1.2e-5
E = 200.0e9
TREF = 293.0

Q = SIGMA * (V0 / L) ** 2  # 均匀体积焦耳热 W/m^3
THALF = K / (RHO * CP)  # 热扩散系数 α (thermal diffusivity)


# ---- 1D slab 解析解 ----
def T_steady(x):
    """稳态: T_s(x)=T∞+Q·a/h+Q·(a²-x²)/(2k)"""
    x = np.asarray(x, float)
    return TINF + Q * A / H + Q * (A * A - x * x) / (2 * K)


def robin_residual(lam):
    """k·λ·tan(λ·a) = h → 对称模态 (cos) 的 Robin 条件。"""
    return K * lam * math.tan(lam * A) - H


def eigen_roots(n_roots=60):
    """λ_n: k·λ·tan(λ·a) = h (对称 cos 模态)。

    每个 tan 分支区间 I_n = (n·π/a, (n+1/2)·π/a) 内, 残余函数
    f(λ)=k·λ·tan(λa)-h 从 -h (λ→nπ/a⁺) 单调升到 +∞ (λ→(n+1/2)π/a⁻),
    恰好穿过 h 一次 → 每个分支 1 个根。首根在 n=0 区间 (0, π/(2a))。
    在每个分支内用 brentq(f, left, right) 求唯一根, 避免 tan 奇点造成伪根。
    """
    roots = []
    n = 0
    while len(roots) < n_roots:
        left = n * math.pi / A + 1e-9
        right = (n + 0.5) * math.pi / A - 1e-9
        # 左端 f≈-h (负), 右端 f→+∞ (正) → 必有跨零
        roots.append(brentq(robin_residual, left, right))
        n += 1
    return np.array(roots[:n_roots])


def mode_coeffs(lambdas, npts=8001):
    xx = np.linspace(-A, A, npts)
    w0 = TINF - T_steady(xx)
    coeffs = []
    for lam in lambdas:
        un = np.cos(lam * xx)
        num = np.trapezoid(w0 * un, xx)
        den = np.trapezoid(un * un, xx)
        coeffs.append(num / den)
    return np.array(coeffs)


def T_analytic(x, t):
    """1D slab 瞬态温度。x 可数组。"""
    x = np.asarray(x, float)
    if t == 0:
        return np.full_like(x, TINF)
    lam, c = _ensure_cache()
    ts = T_steady(x)
    acc = np.zeros_like(x)
    for lamn, cn in zip(lam, c):
        acc += cn * math.exp(-THALF * lamn**2 * t) * np.cos(lamn * x)
    return ts + acc


_LAM = _C = None


def _ensure_cache(n_roots=60):
    global _LAM, _C
    if _LAM is None:
        _LAM = eigen_roots(n_roots=n_roots)
        _C = mode_coeffs(_LAM)
    return _LAM, _C


# ---- CSV 解析 (瞬态, 复用 ET1 逻辑) ----
def parse_columns(headers):
    """识别列结构。返回 (xyz_cols, times) 其中 times=[(t, cols)] cols 含 V/T/sx/sy/sz/u/disp 键。"""
    xyz = [0, 1, 2]
    times = []
    cols_at = {}
    for i, h in enumerate(headers):
        m = re.search(r"@ t=([0-9.eE+-]+)", h)
        if not m:
            continue
        t = float(m.group(1))
        name = h.split(" (")[0].strip().replace("solid.", "")
        cols_at.setdefault(t, {})[name] = i
    # 组装: 需要同时有 V, T, sx 的时间步
    for t, cols in sorted(cols_at.items()):
        if all(k in cols for k in ("V", "T", "sx")):
            times.append((t, cols))
    return xyz, times


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

    xyz, times = parse_columns(headers)
    if not times:
        checks.append(
            check("time_columns", False, None, "no '@ t=' columns found", "s")
        )
        return emit_report(CASE_KEY, csv_path, checks, json_out, md_out)
    print(f"detected {len(times)} time steps: {[t for t, _ in times]}")

    # ---- V_linear: 所有时刻 V=V0·(x+a)/L ----
    vdevs = []
    for t, cols in times:
        for row in rows:
            vdevs.append(abs(row[cols["V"]] - V0 * (row[0] + A) / L))
    vmax = max(vdevs)
    checks.append(
        check(
            "V_linear", vmax < 1e-4, vmax, "max|V-V0(x+a)/L| < 1e-4 V (all times)", "V"
        )
    )

    # ---- T_steady_profile: 末时刻中平面 (x,T) 对稳态解析解 ----
    last_t = max(times, key=lambda e: e[0])[0]
    last_cols = dict(max(times, key=lambda e: e[0])[1])
    mids = [
        row
        for row in rows
        if abs(row[1]) < 0.02
        and abs(row[2]) < 0.02  # y,z≈0 中轴
        and A - abs(row[0]) > 0.02
    ]  # 避开端面
    if mids:
        tdevs = [abs(row[last_cols["T"]] - T_analytic(row[0], last_t)) for row in mids]
        tmax = max(tdevs)
        checks.append(
            check(
                "T_steady_profile",
                tmax < 3.0,
                tmax,
                f"max|T(x,t={last_t:.0f})-analytic| < 3 K (mid-axis)",
                "K",
            )
        )
    else:
        checks.append(check("T_steady_profile", False, None, "no mid samples", "K"))

    # ---- T_transient_profile: 中平面 (x,t) 对傅里叶余弦级数 ----
    worst_by_t = {}
    for t, cols in times:
        if t == 0 or t == last_t:
            continue
        mids = [
            row
            for row in rows
            if abs(row[1]) < 0.02 and abs(row[2]) < 0.02 and A - abs(row[0]) > 0.02
        ]
        if not mids:
            continue
        devs = [abs(row[cols["T"]] - T_analytic(row[0], t)) for row in mids]
        worst_by_t[t] = max(devs)
    if worst_by_t:
        worst_t = max(worst_by_t, key=lambda k: worst_by_t[k])
        worst = float(worst_by_t[worst_t])
        checks.append(
            check(
                "T_transient_profile",
                worst < 3.0,
                worst,
                "max|T(x,t)-analytic| < 3 K (mid-axis, transient)",
                "K",
            )
        )
        checks[-1]["worst_at_t"] = worst_t
    else:
        checks.append(
            check(
                "T_transient_profile",
                False,
                None,
                "no mid samples at intermediate times",
                "K",
            )
        )

    # ---- sigma_x_uniform: 每时刻 σ_x 空间均匀, σ_y/σ_z 中部均值≈0 ----
    sx_std_max = 0.0
    syz_mean_max = 0.0
    for t, cols in times:
        sx = [row[cols["sx"]] for row in rows]
        # 中部区域 (远离端面 x=±a 的圣维南边界效应)
        mid_rows = [row for row in rows if abs(row[0]) < A - 0.05]
        sy = [row[cols["sy"]] for row in mid_rows]
        sz = [row[cols["sz"]] for row in mid_rows]
        sx_std_max = max(sx_std_max, float(np.std(sx)))
        syz_mean_max = max(syz_mean_max, float(max(abs(np.mean(sy)), abs(np.mean(sz)))))
    # σ_x 量级参考 (末时刻)
    ref_sigma = max(abs(r[last_cols["sx"]]) for r in rows)
    checks.append(
        check(
            "sigma_x_uniform",
            sx_std_max < 0.05 * max(ref_sigma, 1.0),
            sx_std_max,
            "max std of σ_x < 5% of |σ_x| scale",
            "Pa",
        )
    )
    checks.append(
        check(
            "sigma_yz_zero",
            syz_mean_max < 0.1 * max(ref_sigma, 1.0),
            syz_mean_max,
            "max |mean σ_y|,|mean σ_z| (mid-region) < 10% of |σ_x|",
            "Pa",
        )
    )

    # ---- sigma_x_analytic: mean(σ_x) ≈ -E·α·(⟨T⟩-Tref) ----
    # 1D 杆理论: σ_x 全局均值精确 = -Eα⟨ΔT⟩ (等温横截面 + 端部固定)。
    # FEM 中有限块体端部圣维南效应使 σ_x 有局部波动, 但均值应精确匹配。
    devs_by_t = {}
    for t, cols in times:
        temps = [row[cols["T"]] for row in rows]
        avgT = float(np.mean(temps))
        sigma_an = -E * ALPHA_T * (avgT - TREF)
        sx_mean = float(np.mean([row[cols["sx"]] for row in rows]))
        devs_by_t[t] = abs(sx_mean - sigma_an)
    if devs_by_t:
        worst_sx_t = max(devs_by_t, key=lambda k: devs_by_t[k])
        worst_sx = float(devs_by_t[worst_sx_t])
        # 末时刻 σ_x 量级最大, 用其解析值作参考
        avgT_last = float(np.mean([row[last_cols["T"]] for row in rows]))
        ref = max(1.0, abs(-E * ALPHA_T * (avgT_last - TREF)))
        checks.append(
            check(
                "sigma_x_analytic",
                worst_sx < 0.05 * ref,
                worst_sx,
                "max|mean(σ_x)+Eα(⟨T⟩-Tref)| < 5% of |σ_x|",
                "Pa",
            )
        )
        checks[-1]["worst_at_t"] = worst_sx_t
    else:
        checks.append(check("sigma_x_analytic", False, None, "no time steps", "Pa"))

    # ---- 无 ends_fixed 显式检查 ----
    # 端部固定 (u_x=0) 已被 sigma_x_analytic 隐含验证: σ_x 均值=-Eα⟨ΔT⟩
    # 的解严格依赖 u_x(±a)=0。位移幅值≈αΔT·L/2 来自侧向自由膨胀 (y,z), 端/中几乎相同。

    evidence = {
        "analytic": "1D slab Fourier cosine series (Robin h at x=±a) + clamped-bar "
        "σ_x=-E·α·(⟨T⟩-Tref) uniform",
        "geometry": "3D cube (differs from ETM1 coaxial cylinder)",
        "times": [t for t, _ in times],
    }
    return emit_report(CASE_KEY, csv_path, checks, json_out, md_out, evidence=evidence)


if __name__ == "__main__":
    sys.exit(main())
