#!/usr/bin/env python3
"""
emw_slab_sweep_frequency.py — 实验 EmwSlabSweep: 介质平板 emw 扫频 (2-3 GHz) 验证

案例: EmwSlabSweepFrequency (src/EmwSlabSweepFrequency.java)。
物理: 电磁波, 频域 (emw), TE 平面波垂直入射到无损介质平板 (n_slab=2, t_slab=6mm),
      周期单元 + Periodic 端口 + Floquet 周期 + IdenticalMesh。
研究: 频域扫描 range(2,0.1,3) GHz (11 频点)。

验证 (解析法, Fabry-Pérot 无损平板, 逐频点):
  1. 每个频点 COMSOL S11dB ≈ 解析 S11dB (容差 0.5 dB)。
  2. 每个频点 COMSOL S21dB ≈ 解析 S21dB (容差 0.5 dB)。
  3. 每个频点功率守恒 |S11|²+|S21|² ≈ 1 (容差 0.02)。
  4. 趋势: |S11| 随频率增大 (平板电厚度增大 → 反射增强)。
  5. 频点覆盖 2.0-3.0 GHz (11 个)。

CSV 格式 (1D Global 图导出): 列名行 "% Frequency (GHz),S11, S21",
  数据行 "x, value" 按表达式主序 (先全部 S11 频点, 再全部 S21 频点)。

用法:
    python emw_slab_sweep_frequency.py <csv-path> <json-out> <md-out>
"""
import cmath
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import CASE_KEY, check, emit_report

CASE_KEY = "EmwSlabSweep"

# ---- 物理参数 (与 EmwSlabSweepFrequency.java 一致) ----
N_AIR = 1.0
N_SLAB = 2.0
T_SLAB = 0.006  # m
C0 = 299792458.0
F_MIN, F_MAX, F_STEP = 2.0e9, 3.0e9, 0.1e9


def load_global_csv(path):
    """解析 1D Global 图导出 CSV。返回 (colnames, rows[(x,value),...])。"""
    colnames = None
    rows = []
    with open(path, encoding="utf-8-sig") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            if line.startswith("%"):
                body = line[1:].strip()
                if "," in body and not body.split(",")[0].startswith(
                    (
                        "Model",
                        "Version",
                        "Date",
                        "Dimension",
                        "Nodes",
                        "Expressions",
                        "Description",
                    )
                ):
                    colnames = [c.strip() for c in body.split(",")]
                continue
            parts = [p.strip() for p in line.split(",")]
            if colnames is None:
                colnames = parts
                continue
            try:
                rows.append([float(p) for p in parts])
            except ValueError:
                continue
    return colnames, rows


def reshape_by_expr(rows, n_expr):
    """按表达式主序切分 (x,value) 行 → list of n_expr (xs[], vals[])。"""
    n = len(rows)
    if n_expr >= 1 and n % n_expr == 0:
        per = n // n_expr
        return [
            (
                [g[0] for g in rows[j * per : (j + 1) * per]],
                [g[1] for g in rows[j * per : (j + 1) * per]],
            )
            for j in range(n_expr)
        ]
    return [([r[0] for r in rows], [r[1] for r in rows])]


def analytic_slab(n_slab, t, f, n1=1.0):
    lam0 = C0 / f
    r = (n1 - n_slab) / (n1 + n_slab)
    delta = 2 * math.pi * n_slab * t / lam0
    e2 = cmath.exp(-2j * delta)
    e1 = cmath.exp(-1j * delta)
    s11 = r * (1 - e2) / (1 - r * r * e2)
    s21 = (1 - r * r) * e1 / (1 - r * r * e2)
    return s11, s21


def main():
    if len(sys.argv) < 4:
        print(__doc__, file=sys.stderr)
        sys.exit(2)
    csv_path, json_out, md_out = sys.argv[1], sys.argv[2], sys.argv[3]

    colnames, rows = load_global_csv(csv_path)
    checks = []
    if not rows:
        checks.append(check("data_present", False, None, "non-empty CSV", "rows"))
        return emit_report(CASE_KEY, csv_path, checks, json_out, md_out)

    seqs = reshape_by_expr(rows, 2)
    xs11, s11 = seqs[0]
    xs21, s21 = seqs[1] if len(seqs) > 1 else ([], [])

    if not xs11 or not xs21:
        checks.append(
            check("data_present", False, None, "S11/S21 series present", "rows")
        )
        return emit_report(CASE_KEY, csv_path, checks, json_out, md_out)

    n_freq = len(xs11)
    n_freq = min(n_freq, len(xs21))
    # 期望频点数
    n_expect = int(round((F_MAX - F_MIN) / F_STEP)) + 1

    # 逐频点解析对比
    max_s11_err = 0.0
    max_s21_err = 0.0
    max_pass_err = 0.0
    worst_f = None
    for i in range(n_freq):
        fghz = xs11[i]
        f = fghz * 1e9
        s11a, s21a = analytic_slab(N_SLAB, T_SLAB, f)
        s11a_db = 20 * math.log10(abs(s11a))
        s21a_db = 20 * math.log10(abs(s21a))
        s11_abs = 10 ** (s11[i] / 20)
        s21_abs = 10 ** (s21[i] / 20)
        err11 = abs(s11[i] - s11a_db)
        err21 = abs(s21[i] - s21a_db)
        passv = s11_abs**2 + s21_abs**2
        max_s11_err = max(max_s11_err, err11)
        max_s21_err = max(max_s21_err, err21)
        max_pass_err = max(max_pass_err, abs(passv - 1.0))
        if worst_f is None or err11 + err21 > max_s11_err + max_s21_err - 1e-9:
            worst_f = fghz

    checks.append(
        check(
            "freq_coverage",
            n_freq == n_expect,
            [n_freq, n_expect],
            f"freq points == {n_expect}",
            "points",
        )
    )
    checks.append(
        check(
            "S11_sweep_analytic",
            max_s11_err < 0.5,
            [max_s11_err, worst_f],
            "max |ΔS11dB| < 0.5 dB across sweep",
            "dB",
        )
    )
    checks.append(
        check(
            "S21_sweep_analytic",
            max_s21_err < 0.5,
            [max_s21_err, worst_f],
            "max |ΔS21dB| < 0.5 dB across sweep",
            "dB",
        )
    )
    checks.append(
        check(
            "passivity_sweep",
            max_pass_err < 0.02,
            max_pass_err,
            "max |S11|²+|S21|²-1 < 0.02",
            "ratio",
        )
    )

    # 趋势: 反射随频率单调增大 (薄板电厚度增大 → |S11| 增大 → S11dB 上升)
    monotonic = all(s11[i + 1] > s11[i] - 1e-6 for i in range(n_freq - 1))
    checks.append(
        check(
            "S11_trend",
            monotonic,
            [s11[0], s11[-1]],
            "S11dB increases with f (thicker electrically)",
            "dB",
        )
    )

    # 末端值合理性 (2GHz 与 3GHz)
    s11_first, s11_last = s11[0], s11[-1]
    checks.append(
        check(
            "S11_bounds",
            -15 < s11_first < -5 and -10 < s11_last < -4,
            [s11_first, s11_last],
            "thin-slab S11 bounds 2-3 GHz",
            "dB",
        )
    )

    evidence = {
        "geometry": "periodic unit cell 10mm, air box + centered n=2 slab (6mm), IdenticalMesh on periodic pairs",
        "study": f"Frequency sweep range(2,0.1,3) GHz ({n_freq} points)",
        "fields": f"max ΔS11dB={max_s11_err:.4f}, max ΔS21dB={max_s21_err:.4f}, "
        f"max passivity err={max_pass_err:.2e}; "
        f"S11dB {s11[0]:.3f}→{s11[-1]:.3f} over 2→3 GHz",
    }
    return emit_report(CASE_KEY, csv_path, checks, json_out, md_out, evidence=evidence)


if __name__ == "__main__":
    sys.exit(main())
