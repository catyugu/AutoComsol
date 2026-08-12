#!/usr/bin/env python3
"""
t_cylinder_stationary.py — 实验 T1: 3D 空心圆柱稳态传热 验证

解析解: T(r) = T1 + (T2-T1)*ln(r/r_in)/ln(r_out/r_in)
r_in=0.3, r_out=0.5, T1=100, T2=300。
列约定: x,y,z,T。用中平面(z=0)采样点按半径分箱对比。

用法:
    python t_cylinder_stationary.py <csv-path> <json-out> <md-out>
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import CASE_KEY, check, emit_report, load_csv

CASE_KEY = "T1"

R_IN, R_OUT, T1, T2 = 0.3, 0.5, 100.0, 300.0


def tana(r):
    return T1 + (T2 - T1) * math.log(r / R_IN) / math.log(R_OUT / R_IN)


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

    # 中平面采样
    mid = [
        r
        for r in rows
        if len(r) >= 4 and abs(r[2]) < 0.01 and r[0] * r[0] + r[1] * r[1] > 0.001
    ]
    # 按半径分箱
    bins = {}
    for r in mid:
        key = round(math.sqrt(r[0] ** 2 + r[1] ** 2), 2)
        bins.setdefault(key, []).append(r[3])
    # 内/外壁边界检查
    t_min, t_max = min(r[3] for r in rows), max(r[3] for r in rows)
    checks.append(
        check(
            "T_range",
            abs(t_min - T1) < 1e-3 and abs(t_max - T2) < 1e-3,
            [t_min, t_max],
            "T in [100,300] at walls",
            "K",
        )
    )

    # 径向分布偏差（排除边界桶 0.30/0.50，取中间桶）
    mid_devs = []
    for key in sorted(bins):
        if 0.32 <= key <= 0.48:
            comsol = sum(bins[key]) / len(bins[key])
            mid_devs.append(abs(comsol - tana(key)))
    if mid_devs:
        checks.append(
            check(
                "T_radial_profile",
                max(mid_devs) < 5.0,
                max(mid_devs),
                "max|T(r)-analytic| < 5 K (mid-plane)",
                "K",
            )
        )
    else:
        checks.append(
            check("T_radial_profile", False, None, "no mid-plane samples", "K")
        )

    return emit_report(CASE_KEY, csv_path, checks, json_out, md_out)


if __name__ == "__main__":
    sys.exit(main())
