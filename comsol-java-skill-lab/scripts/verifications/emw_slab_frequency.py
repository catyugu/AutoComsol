#!/usr/bin/env python3
"""
emw_slab_frequency.py — 实验 EmwSlab: 3D 介质平板 频域电磁波 (emw) 垂直入射 验证

案例: EmwSlabFrequency (src/EmwSlabFrequency.java)。
物理: 电磁波, 频域 (ElectromagneticWaves, emw)。TE 平面波 (y 偏振) 垂直入射到
      无损介质平板 (n_slab=2, t_slab=6mm)。周期单元: 空气盒 + 居中介质板 (3 域),
      顶/底面 Periodic 端口 (port1 激励/port2 接收), 四侧面 Floquet 周期条件,
      IdenticalMesh 保证周期对 mesh 一致。单频 2.45 GHz。

验证 (解析法, Fabry-Pérot 无损平板):
  r  = (n1-n2)/(n1+n2),  δ = 2π·n_slab·t_slab/λ0
  S11 = r(1-e^{-2iδ})/(1-r²e^{-2iδ})
  S21 = (1-r²)e^{-iδ}/(1-r²e^{-2iδ})
  检查:
    1. COMSOL S11dB ≈ 解析 S11dB (容差 0.5 dB)。
    2. COMSOL S21dB ≈ 解析 S21dB (容差 0.5 dB)。
    3. 功率守恒 |S11|²+|S21|² ≈ 1 (无损介质, 容差 0.02)。
    4. 数值健康检查 (非空/无 NaN/Inf)。

CSV 格式 (COMSOL 全局变量导出, 1 行/表达式):
  % 注释头 + "% Frequency (GHz),S11, S21" 列名行
  数据行: "x, value"  每行一个表达式 (S11 在前, S21 在后)。
  单频 → 2 行; 扫频 → 每组 N 行 (表达式主序)。

用法:
    python emw_slab_frequency.py <csv-path> <json-out> <md-out>
"""
import cmath
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import CASE_KEY, check, emit_report

CASE_KEY = "EmwSlab"

# ---- 物理参数 (与 EmwSlabFrequency.java 一致) ----
N_AIR = 1.0
N_SLAB = 2.0
T_SLAB = 0.006  # m
F0 = 2.45e9  # Hz
C0 = 299792458.0


def load_global_csv(path):
    """解析 COMSOL 全局变量导出 (1 行/表达式)。返回 (colnames, rows[(x,value),...])。

    COMSOL 把列名写在 % 注释行: "% Frequency (GHz),S11, S21"。
    """
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
                colnames = [c.strip() for c in parts]
                continue
            try:
                rows.append([float(p) for p in parts])
            except ValueError:
                continue
    return colnames, rows


def reshape_by_expr(rows, n_expr):
    """把 (x,value) 行按表达式主序重排 → list of n_expr (xs[], vals[]) 序列。

    若行数恰为 n_expr 的整数倍则按组切分; 否则退化为每组单行。
    """
    n = len(rows)
    if n_expr >= 1 and n % n_expr == 0:
        per = n // n_expr
        out = []
        for j in range(n_expr):
            grp = rows[j * per : (j + 1) * per]
            out.append(([g[0] for g in grp], [g[1] for g in grp]))
        return out
    return [([r[0] for r in rows], [r[1] for r in rows])]


def analytic_slab(n_slab, t, f, n1=1.0):
    """Fabry-Pérot 无损平板 S11/S21 (复数)。"""
    lam0 = C0 / f
    r = (n1 - n_slab) / (n1 + n_slab)
    delta = 2 * math.pi * n_slab * t / lam0  # beta*t
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

    # 解析 S11/S21 (单频: 2 行; 表达式顺序 = 列名顺序)
    n_expr = 2
    seqs = reshape_by_expr(rows, n_expr)
    s11db = seqs[0][1][0] if len(seqs) >= 1 and seqs[0][1] else float("nan")
    s21db = seqs[1][1][0] if len(seqs) >= 2 and seqs[1][1] else float("nan")

    # 解析 S11/S21 (mag) — 若列多于 2 取后列, 这里只用 dB 列反推
    s11_abs = 10 ** (s11db / 20) if math.isfinite(s11db) else float("nan")
    s21_abs = 10 ** (s21db / 20) if math.isfinite(s21db) else float("nan")
    passivity = s11_abs**2 + s21_abs**2

    # 解析法
    s11a, s21a = analytic_slab(N_SLAB, T_SLAB, F0)
    s11a_db = 20 * math.log10(abs(s11a))
    s21a_db = 20 * math.log10(abs(s21a))

    # ---- 检查 ----
    checks.append(
        check(
            "data_present",
            math.isfinite(s11db) and math.isfinite(s21db),
            [s11db, s21db],
            "finite S11/S21 values",
            "dB",
        )
    )
    checks.append(
        check(
            "S11_analytic",
            abs(s11db - s11a_db) < 0.5,
            [s11db, s11a_db],
            "S11dB ≈ analytic (tol 0.5 dB)",
            "dB",
        )
    )
    checks.append(
        check(
            "S21_analytic",
            abs(s21db - s21a_db) < 0.5,
            [s21db, s21a_db],
            "S21dB ≈ analytic (tol 0.5 dB)",
            "dB",
        )
    )
    checks.append(
        check(
            "passivity",
            abs(passivity - 1.0) < 0.02,
            passivity,
            "|S11|²+|S21|² ≈ 1 (lossless)",
            "ratio",
        )
    )
    # 反射在合理区间 (薄板, 远低于半波谐振)
    checks.append(
        check(
            "S11_reasonable",
            -20 < s11db < -2,
            s11db,
            "thin-slab S11 in (-20,-2) dB",
            "dB",
        )
    )

    evidence = {
        "geometry": "periodic unit cell 10mm, air box + centered n=2 slab (6mm), 3 domains, IdenticalMesh on periodic pairs",
        "excitation": "Periodic port1 (bottom, 1W) TE y-pol, port2 (top, receive), Floquet periodic sides, normal incidence",
        "study": "Frequency @ 2.45 GHz",
        "fields": f"S11dB={s11db:.3f} (ana {s11a_db:.3f}), S21dB={s21db:.3f} (ana {s21a_db:.3f}), "
        f"passivity={passivity:.4f}",
    }
    return emit_report(CASE_KEY, csv_path, checks, json_out, md_out, evidence=evidence)


if __name__ == "__main__":
    sys.exit(main())
