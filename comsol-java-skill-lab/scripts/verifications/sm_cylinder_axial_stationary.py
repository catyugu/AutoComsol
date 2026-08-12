#!/usr/bin/env python3
"""
sm_cylinder_axial_stationary.py — 实验 M1: 3D 空心圆柱轴向拉伸 验证

解析解: 轴向应力 sigma_z=1e6 Pa, E=200e9, 内部 vm=sigma_z=1e6,
上端面位移 u_z = sigma*L/E = 5e-6 m (L=1m)。
列约定: x,y,z,solid.mises,solid.disp。

用法:
    python sm_cylinder_axial_stationary.py <csv-path> <json-out> <md-out>
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import CASE_KEY, check, emit_report, load_csv

CASE_KEY = "M1"


def main():
    if len(sys.argv) < 4:
        print(__doc__, file=sys.stderr)
        sys.exit(2)
    csv_path, json_out, md_out = sys.argv[1], sys.argv[2], sys.argv[3]

    headers, rows = load_csv(csv_path)
    checks = []

    ms = [r[3] for r in rows if len(r) >= 4]
    ds = [r[4] for r in rows if len(r) >= 5]
    if not ms or not ds:
        checks.append(
            check("M1_data", False, None, "need x,y,z,mises,disp columns", "Pa")
        )
        return emit_report(CASE_KEY, csv_path, checks, json_out, md_out)

    # 1. 内部(远离端部) von Mises ≈ sigma_z = 1e6 Pa
    inner = [r[3] for r in rows if len(r) >= 4 and -0.4 < r[2] < 0.4]
    inner_mean = sum(inner) / len(inner) if inner else None
    checks.append(
        check(
            "vm_axial",
            inner_mean is not None and abs(inner_mean - 1e6) < 0.1e6,
            inner_mean,
            "interior vm in [0.9,1.1]e6 Pa",
            "Pa",
        )
    )

    # 2. 上端面位移 ≈ 5e-6 m
    top = [r[4] for r in rows if len(r) >= 5 and r[2] > 0.45]
    top_max = max(top) if top else None
    checks.append(
        check(
            "top_disp",
            top_max is not None and abs(top_max - 5e-6) < 0.5e-6,
            top_max,
            "top face disp in [4.5,5.5]e-6 m",
            "m",
        )
    )

    return emit_report(CASE_KEY, csv_path, checks, json_out, md_out)


if __name__ == "__main__":
    sys.exit(main())
