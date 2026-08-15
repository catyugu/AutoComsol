#!/usr/bin/env python3
"""
ec_t_cylinder_transient.py — 实验 ET1: 3D 实心圆柱瞬态电热耦合 验证

案例: EcTCylinderTransient (src/analytic/.java)。
物理: ConductiveMedia(ec) + HeatTransfer(ht) + ElectromagneticHeating 耦合。
几何: 3D 实心圆柱 R=0.3m, L=1m, 中心原点。
电:   顶面 V0=1V, 底面 Ground → 轴向 V(z)=z+0.5 线性, J 均匀, Q=σ(V0/L)² 均匀。
热:   侧面对流 h=200 W/m²K 到 T∞=293K, 顶/底绝热, 初温 293K, 瞬态 0..3000s。

解析解:
  电流: V(z)=z+0.5 (V), E=V0/L=1 V/m, J=σE, Q=σ(V0/L)²=2e4 W/m³
  稳态热(中平面纯径向): T_s(r)=T∞+Q·R/(2h)+Q·(R²-r²)/(4k)
  瞬态热: T(r,t)=T_s(r)+Σ c_n e^{-αλ_n²t}·J0(λ_n r)
          λ_n 满足 Robin: k·λ·J1(λR)=h·J0(λR)
          c_n=∫r(Tinf-T_s)J0(λr)dr / ∫r J0²(λr)dr

CSV 列 (COMSOL 瞬态 Data 导出, 2 表达式 V,T 交替):
  % x,y,z,V (V) @ t=0,T (K) @ t=0,V (V) @ t=100,T (K) @ t=100,...
  每节点一行; (x,y,z) + 每时刻 (V,T)。

检查:
  - V_linear: 所有时刻 V=z+0.5 (电流瞬态内即时平衡, V 不随时间变)
  - transient_profile: 中平面(r 离壁, z≈0)采样 (r,t) 对解析 T 偏差 < 阈值
  - steady_analytic: 末时刻中平面 ≈ 解析 T(r,tmax)
  - symmetry: 中平面上下对称(顶/底绝热, 轴向均匀) → z 对称点 T 一致

用法:
    python ec_t_cylinder_transient.py <csv-path> <json-out> <md-out>
"""
import math
import os
import re
import sys

import numpy as np
from scipy.optimize import brentq
from scipy.special import j0, j1

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common import CASE_KEY, check, emit_report, load_csv

CASE_KEY = "ET1"

# ---- 物理参数 (与 EcTCylinderTransient.java 一致) ----
R = 0.3
L = 1.0
V0 = 1.0
SIGMA = 2.0e4
TINF = 293.0
H = 200.0
K = 50.0
RHO = 7850.0
CP = 500.0
ALPHA = K / (RHO * CP)
Q = SIGMA * (V0 / L) ** 2  # 均匀体积焦耳热


# ---- 解析解 ----
def steady_cyl(r):
    """均匀热源 + 侧面对流稳态: T_s(r)=Tinf+QR/(2h)+Q(R²-r²)/(4k)"""
    return TINF + Q * R / (2 * H) + Q * (R * R - np.asarray(r, float) ** 2) / (4 * K)


def robin_residual(lam):
    """k·λ·J1(λR) = h·J0(λR) → Robin 外壁。"""
    if lam <= 1e-9:
        return 1e9
    return K * lam * j1(lam * R) - H * j0(lam * R)


def eigen_roots(n_roots=60):
    spacing = math.pi / R
    max_lam = spacing * n_roots * 1.3
    npts = max(int(max_lam / spacing) * 40, 2000)
    xs = np.linspace(1e-4, max_lam, npts)
    vals = np.array([robin_residual(x) for x in xs])
    roots = []
    for i in range(len(xs) - 1):
        if vals[i] * vals[i + 1] < 0:
            roots.append(brentq(robin_residual, xs[i], xs[i + 1]))
        if len(roots) >= n_roots:
            break
    if len(roots) < n_roots:
        raise RuntimeError(f"only {len(roots)} roots, need {n_roots}")
    return np.array(roots[:n_roots])


def mode_coeffs(lambdas, npts=8001):
    rr = np.linspace(1e-6, R, npts)
    w0 = TINF - steady_cyl(rr)
    coeffs, ufs = [], []
    for lam in lambdas:
        un = j0(lam * rr)
        num = np.trapezoid(rr * w0 * un, rr)
        den = np.trapezoid(rr * un * un, rr)
        coeffs.append(num / den)
        ufs.append(lambda r, lamn=lam: j0(lamn * np.asarray(r, float)))
    return np.array(coeffs), ufs


def T_analytic(r, t):
    """中平面纯径向瞬态解 (使用模块级缓存)。r 可为数组。"""
    r = np.asarray(r, float)
    ts = steady_cyl(r)
    if t == 0:
        return np.full_like(r, TINF)
    lam, c, u = _ensure_cache()
    acc = np.zeros_like(r)
    for lamn, cn, uf in zip(lam, c, u):
        acc += cn * math.exp(-ALPHA * lamn**2 * t) * uf(r)
    return ts + acc


_LAM = _C = _U = None


def _ensure_cache(n_roots=60):
    global _LAM, _C, _U
    if _LAM is None:
        _LAM = eigen_roots(n_roots=n_roots)
        _C, _U = mode_coeffs(_LAM)
    return _LAM, _C, _U


# ---- CSV 解析 ----
def parse_columns(headers):
    """识别列结构。返回 (xyz_cols, times) 其中 times=[(t, vcol, tcol)]。"""
    xyz = [0, 1, 2]
    times = []
    seen = set()
    for i, h in enumerate(headers):
        m = re.search(r"@ t=([0-9.eE+-]+)", h)
        if m:
            t = float(m.group(1))
            if "V (" in h:
                if t not in seen:
                    seen.add(t)
                    times.append([t, i, None])
            elif "T (" in h:
                for entry in times:
                    if entry[0] == t and entry[2] is None:
                        entry[2] = i
                        break
    times = [(t, vc, tc) for t, vc, tc in times if tc is not None]
    return xyz, times


def r_of(x, y):
    return math.sqrt(x * x + y * y)


# ---- 验证 ----
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
    print(f"detected {len(times)} time steps: {[t for t, _, _ in times]}")

    # ---- V_linear: 所有时刻 V = z + 0.5 ----
    vdevs = []
    for t, vc, tc in times:
        for row in rows:
            vdevs.append(abs(row[vc] - (row[2] + 0.5)))
    vmax = max(vdevs)
    checks.append(
        check("V_linear", vmax < 1e-3, vmax, "max|V-(z+0.5)| < 1e-3 V (all times)", "V")
    )

    # ---- transient_profile: 中平面 (r,t) 对解析解 ----
    worst_by_t = {}
    for t, vc, tc in times:
        mids = [
            (r_of(row[0], row[1]), row[tc])
            for row in rows
            if abs(row[2]) < 0.02  # 中平面 z≈0
            and r_of(row[0], row[1]) > 0.03  # 远离轴心(避免 r=0 奇异)
            and R - r_of(row[0], row[1]) > 0.03
        ]  # 远离侧壁
        if not mids:
            continue
        devs = [abs(T - T_analytic(r, t)) for r, T in mids]
        worst_by_t[t] = max(devs)
    if worst_by_t:
        worst_t = max(worst_by_t, key=lambda k: worst_by_t[k])
        worst = float(worst_by_t[worst_t])
        checks.append(
            check(
                "transient_profile",
                worst < 3.0,
                worst,
                "max|T(r,t)-analytic| < 3 K (mid-plane)",
                "K",
            )
        )
        checks[-1]["worst_at_t"] = worst_t
    else:
        checks.append(
            check("transient_profile", False, None, "no mid-plane samples", "K")
        )

    # ---- steady_analytic: 末时刻中平面 ≈ 解析 T(r,tmax) ----
    last_t = max(times, key=lambda e: e[0])
    t_last, vc_last, tc_last = last_t
    mids = [
        (r_of(row[0], row[1]), row[tc_last])
        for row in rows
        if abs(row[2]) < 0.02
        and r_of(row[0], row[1]) > 0.03
        and R - r_of(row[0], row[1]) > 0.03
    ]
    if mids:
        ssdev = max(float(abs(T - T_analytic(r, t_last))) for r, T in mids)
        checks.append(
            check(
                "steady_analytic",
                ssdev < 3.0,
                ssdev,
                f"max|T(r,t={t_last:.0f})-analytic| < 3 K",
                "K",
            )
        )
    else:
        checks.append(
            check("steady_analytic", False, None, "no mid samples at last time", "K")
        )

    # ---- symmetry: z 对称点温度一致 (顶/底绝热) ----
    sym_devs = []
    for t, vc, tc in times:
        by_key = {}
        for row in rows:
            key = (round(r_of(row[0], row[1]), 2), round(abs(row[2]), 2))
            by_key.setdefault(key, []).append(row[tc])
        for key, vals in by_key.items():
            if len(vals) >= 2:
                sym_devs.append(max(vals) - min(vals))
    if sym_devs:
        smax = max(sym_devs)
        checks.append(
            check("z_symmetry", smax < 0.5, smax, "max T asym across z=0 < 0.5 K", "K")
        )
    else:
        checks.append(check("z_symmetry", False, None, "no paired z samples", "K"))

    evidence = {
        "analytic": "Uniform Joule source + Robin convection: "
        "T_s(r) parabola + J0 Bessel series"
    }
    return emit_report(CASE_KEY, csv_path, checks, json_out, md_out, evidence=evidence)


if __name__ == "__main__":
    sys.exit(main())
