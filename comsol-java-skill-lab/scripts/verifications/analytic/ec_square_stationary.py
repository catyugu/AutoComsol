#!/usr/bin/env python3
"""
ec_square_stationary.py — 实验 E1: 2D 方板导电稳态 验证

解析解: V=0.5-x（线性），E=1 V/m，J=σE=5.998e7 A/m²（σ=5.998e7 S/m 均匀）。
列约定: x,y,V,ec.normJ。
注意: 物理场是 ConductiveMedia（导电），场量是电流密度 ec.normJ；J=σE=5.998e7 A/m²
（历史修复: 原检查量名 normE/期望 1 与导出列 ec.normJ 不符）。

用法:
    python ec_square_stationary.py <csv-path> <json-out> <md-out>
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common import CASE_KEY, check, emit_report, load_csv

CASE_KEY = "E1"


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

    # V 范围: 应为 [0,1] V
    vs = [r[2] for r in rows if len(r) >= 3]
    vmin, vmax = min(vs), max(vs)
    checks.append(
        check(
            "V_range",
            vmin >= -1e-6 and vmax <= 1 + 1e-6,
            [vmin, vmax],
            "V in [0,1]",
            "V",
        )
    )

    # V 线性: 在 x 轴(y≈0)采样, V=0.5-x
    mids = [r for r in rows if len(r) >= 3 and abs(r[1]) < 0.02]
    maxdev = max(abs(r[2] - (0.5 - r[0])) for r in mids) if mids else float("inf")
    checks.append(
        check("V_linearity", maxdev < 1e-3, maxdev, "max|V-(0.5-x)| < 1e-3 V", "V")
    )

    # normJ ≈ 5.998e7 A/m² (J = σE, σ=5.998e7 S/m, E=1 V/m)
    es = [r[3] for r in rows if len(r) >= 4]
    emean = sum(es) / len(es) if es else None
    checks.append(
        check(
            "normJ_value",
            emean is not None and abs(emean - 5.998e7) < 0.05 * 5.998e7,
            emean,
            "|mean(ec.normJ)-5.998e7| < 5% A/m^2",
            "A/m^2",
        )
    )

    return emit_report(CASE_KEY, csv_path, checks, json_out, md_out)


if __name__ == "__main__":
    sys.exit(main())
