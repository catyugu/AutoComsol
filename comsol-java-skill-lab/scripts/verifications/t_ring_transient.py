#!/usr/bin/env python3
"""
t_ring_transient.py — 实验 T2: 2D 圆环瞬态传热(对流 BC) 验证

案例: TRingTransient (src/TRingTransient.java), HeatTransfer 瞬态。
几何: 2D 圆环 r_in=0.2, r_out=0.5; 内壁 Dirichlet T=473K, 外壁对流
      h=100 W/m²K, T∞=293K; 初温 293K; 瞬态 0..3000s。

解析解 (Carslaw & Jaeger §7.2 圆环 Dirichlet内壁 + Robin外壁):
  T(r,t) = T_s(r) + Σ c_n e^{-α λ_n² t} U_n(r)

  稳态:   T_s(r) = T1 + A·ln(r/a),  A = -(hb/k)(T1-Tinf)/(1+(hb/k)ln(b/a))
  本征:   U_n(r) = J0(λa)Y0(λr) - Y0(λa)J0(λr)   (内壁 U_n(a)=0)
          Robin 外壁: -k·U_n'(b) = h·U_n(b) → 求 λ_n
  系数:   c_n = ∫ r·w0·U_n dr / ∫ r·U_n² dr,  w0(r)=Tinf-T_s(r)
  注意:   U'(r) = λ[Y0(λa)J1(λr) - J0(λa)Y1(λr)] (J0'=-λJ1, Y0'=-λY1),
          导数符号错误会导致本征值错误(旧值 λ0=1.33 → 修正后 λ0=5.66)。

CSV 列结构 (COMSOL 瞬态 Data 导出):
  % X,Y,T (K) @ t=0,T (K) @ t=100,T (K) @ t=200,...
  每节点一行, 每列一个时间步的 T。

用法:
    python t_ring_transient.py <csv-path> <json-out> <md-out>
"""
import math
import os
import re
import sys

import numpy as np
from scipy.optimize import brentq
from scipy.special import j0, j1, y0, y1

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import CASE_KEY, check, emit_report, load_csv

CASE_KEY = "T2"

# ---- 物理参数 (与 TRingTransient.java 一致) ----
R_IN = 0.2
R_OUT = 0.5
T1 = 473.0
TINF = 293.0
H = 100.0
K = 50.0
RHO = 7850.0
CP = 500.0
ALPHA = K / (RHO * CP)  # 热扩散率 m²/s


# ---- 解析解 ----
def steady_annulus(r, a=R_IN, b=R_OUT, t1=T1, tinf=TINF, h=H, k=K):
    """稳态对数温度分布 T_s(r)。"""
    bi = h * b / k
    A = -bi * (t1 - tinf) / (1.0 + bi * math.log(b / a))
    return t1 + A * np.log(np.asarray(r, dtype=float) / a)


def _robin_residual(lam, a=R_IN, b=R_OUT, h=H, k=K):
    """Robin 外壁残差: -k·U'(b) - h·U(b) = 0。"""
    if lam <= 1e-9:
        return 1e9
    ub = j0(lam * a) * y0(lam * b) - y0(lam * a) * j0(lam * b)
    udb = lam * (y0(lam * a) * j1(lam * b) - j0(lam * a) * y1(lam * b))
    return -k * udb - h * ub


def eigen_roots(n_roots=60):
    """返回前 n_roots 个本征值 λ_n。根密度≈π/(b-a), 采样自适应。"""
    spacing = math.pi / (R_OUT - R_IN)
    max_lam = spacing * n_roots * 1.3
    npts = max(int(max_lam / spacing) * 40, 2000)
    xs = np.linspace(1e-3, max_lam, npts)
    vals = np.array([_robin_residual(x) for x in xs])
    roots = []
    for i in range(len(xs) - 1):
        if vals[i] * vals[i + 1] < 0:
            roots.append(brentq(_robin_residual, xs[i], xs[i + 1]))
        if len(roots) >= n_roots:
            break
    if len(roots) < n_roots:
        raise RuntimeError(f"only found {len(roots)} roots, need {n_roots}")
    return np.array(roots[:n_roots])


def mode_coeffs(lambdas, npts=8001):
    """对每个 λ_n 预计算 c_n = ∫ r·w0·U_n dr / ∫ r·U_n² dr。

    返回 (lambdas, coeffs, un_funcs)。
    """
    rr = np.linspace(R_IN, R_OUT, npts)
    w0 = TINF - steady_annulus(rr)
    coeffs = []
    un_funcs = []
    for lam in lambdas:
        un = j0(lam * R_IN) * y0(lam * rr) - y0(lam * R_IN) * j0(lam * rr)
        num = np.trapezoid(rr * w0 * un, rr)
        den = np.trapezoid(rr * un * un, rr)
        coeffs.append(num / den)

        def make(lamn=lam):
            def uf(r):
                r = np.asarray(r, dtype=float)
                return j0(lamn * R_IN) * y0(lamn * r) - y0(lamn * R_IN) * j0(lamn * r)

            return uf

        un_funcs.append(make())
    return lambdas, np.array(coeffs), un_funcs


def analytic_t(r, t, lambdas, coeffs, un_funcs):
    """完整瞬态解析解 T(r,t)。r 可为数组。"""
    r = np.asarray(r, dtype=float)
    ts = steady_annulus(r)
    if t == 0.0:
        return np.full_like(r, TINF)
    acc = np.zeros_like(r)
    for lam, cn, uf in zip(lambdas, coeffs, un_funcs):
        acc += cn * math.exp(-ALPHA * lam**2 * t) * uf(r)
    return ts + acc


# 模块级缓存: 一次性求根与系数（验证脚本多次调用 T_analytic 复用）
_LAMBDAS = None
_COEFFS = None
_UNS = None


def _ensure_cache(n_roots=60):
    global _LAMBDAS, _COEFFS, _UNS
    if _LAMBDAS is None:
        _LAMBDAS = eigen_roots(n_roots=n_roots)
        _LAMBDAS, _COEFFS, _UNS = mode_coeffs(_LAMBDAS)
    return _LAMBDAS, _COEFFS, _UNS


def T_analytic(r, t):
    """便捷入口: 使用模块级缓存。"""
    lam, c, u = _ensure_cache()
    return analytic_t(r, t, lam, c, u)


# ---- CSV 解析 ----
def parse_time_columns(headers):
    """从列头提取 (col_index, time) 对。列名形如 'T (K) @ t=100'。"""
    times = []
    for i, h in enumerate(headers):
        m = re.search(r"@ t=([0-9.eE+-]+)", h)
        if m:
            times.append((i, float(m.group(1))))
    return times


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

    # 解析时间列
    times = parse_time_columns(headers)
    if not times:
        checks.append(
            check("time_columns", False, None, "no '@ t=' columns found", "s")
        )
        return emit_report(CASE_KEY, csv_path, checks, json_out, md_out)

    # 去重保序 (range 拼接导致重复时刻)
    seen = set()
    uniq_times = []
    for col, t in times:
        if t not in seen:
            seen.add(t)
            uniq_times.append((col, t))
    times = uniq_times
    print(f"detected {len(times)} time steps: {[t for _, t in times]}")

    # 按时间步收集 (r, T) 采样
    time_samples = {t: [] for _, t in times}
    for row in rows:
        r = r_of(row[0], row[1])
        for col, t in times:
            time_samples[t].append((r, row[col]))

    # ---- inner_dirichlet: 所有时刻 r≈a 处 T≈T1 ----
    inner_devs = []
    for t, samples in time_samples.items():
        near = [T for r, T in samples if abs(r - R_IN) < 0.01]
        if near:
            inner_devs.append(max(abs(T - T1) for T in near))
    if inner_devs:
        checks.append(
            check(
                "inner_dirichlet",
                float(max(inner_devs)) < 1.0,
                float(max(inner_devs)),
                "max|T(inner)-473| < 1 K (all times)",
                "K",
            )
        )
    else:
        checks.append(check("inner_dirichlet", False, None, "no inner samples", "K"))

    # ---- transient_profile: 中平面 (r,t) 对解析解 ----
    worst_by_t = {}
    for t, samples in time_samples.items():
        mids = [(r, T) for r, T in samples if r - R_IN > 0.02 and R_OUT - r > 0.02]
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
                worst < 5.0,
                worst,
                "max|T(r,t)-analytic| < 5 K",
                "K",
            )
        )
        checks[-1]["worst_at_t"] = worst_t
    else:
        checks.append(
            check("transient_profile", False, None, "no mid-plane samples", "K")
        )

    # ---- steady_analytic: 最晚时刻 ≈ 解析解 T(r, tmax) ----
    # tmax=3000s 尚未完全稳态(最低模特征时间~2460s), 对比完整解析解而非稳态 T_s。
    last_t = max(times, key=lambda ct: ct[1])
    col_last, t_last = last_t
    mids = [
        (r_of(row[0], row[1]), row[col_last])
        for row in rows
        if r_of(row[0], row[1]) - R_IN > 0.02 and R_OUT - r_of(row[0], row[1]) > 0.02
    ]
    if mids:
        ssdev = max(float(abs(T - T_analytic(r, t_last))) for r, T in mids)
        checks.append(
            check(
                "steady_analytic",
                ssdev < 5.0,
                ssdev,
                f"max|T(r,t={t_last:.0f})-analytic| < 5 K",
                "K",
            )
        )
    else:
        checks.append(
            check("steady_analytic", False, None, "no mid samples at last time", "K")
        )

    evidence = {
        "analytic": "Carslaw-Jaeger Bessel series " "(Dirichlet inner + Robin outer)"
    }
    return emit_report(CASE_KEY, csv_path, checks, json_out, md_out, evidence=evidence)


if __name__ == "__main__":
    sys.exit(main())
