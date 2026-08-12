#!/usr/bin/env python3
"""
health_check.py — 健康度检查调度器（跨平台，纯 Python）

用法:
    python health_check.py <experiment-key> <csv-path> <json-out> <md-out>

职责: 仅调度。根据实验键分发到 scripts/verifications/ 下对应案例验证脚本，
      自身不包含任何物理/解析解检查逻辑。

支持实验:
    E1  ec_square_stationary         2D 方板导电稳态
    T1  t_cylinder_stationary        3D 空心圆柱稳态传热
    M1  sm_cylinder_axial_stationary 3D 空心圆柱轴向拉伸
    T2  t_ring_transient             2D 圆环瞬态传热(对流 BC)
    ET1 ec_t_cylinder_transient      3D 圆柱瞬态电热耦合
    ET2 ec_t_cylinder_stationary  3D 同轴双材料电热耦合稳态
    EcTSmCyl ec_tsm_cylinder_stationary  3D 同轴双材料稳态电热力耦合
    EcTSmCube ec_tsm_cube_transient      3D 立方体瞬态电热力耦合
    EcTSmBusbar ec_tsm_busbar_stationary    铜母线+钛螺栓电热结构多物理场
"""
import os
import subprocess
import sys

VERIF_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "verifications")

# 实验键 → 案例验证脚本文件名 (small_underscore)
REGISTRY = {
    "E1": "ec_square_stationary.py",
    "T1": "t_cylinder_stationary.py",
    "M1": "sm_cylinder_axial_stationary.py",
    "T2": "t_ring_transient.py",
    "ET1": "ec_t_cylinder_transient.py",
    "ET2": "ec_t_cylinder_stationary.py",
    "EcTSmCyl": "ec_tsm_cylinder_stationary.py",
    "EcTSmCube": "ec_tsm_cube_transient.py",
    "EcTSmBusbar": "ec_tsm_busbar_stationary.py",
}


def main():
    if len(sys.argv) < 5:
        print(
            "usage: health_check.py <experiment> <csv> <json-out> <md-out> [stdout-log]",
            file=sys.stderr,
        )
        sys.exit(2)
    exp, csv_path, json_out, md_out = sys.argv[1:5]
    stdout_log = sys.argv[5] if len(sys.argv) > 5 else None

    script = REGISTRY.get(exp)
    if script is None:
        print(
            f"ERROR: unknown experiment key '{exp}'. " f"Known: {sorted(REGISTRY)}",
            file=sys.stderr,
        )
        sys.exit(2)

    script_path = os.path.join(VERIF_DIR, script)
    if not os.path.exists(script_path):
        print(f"ERROR: verification script not found: {script_path}", file=sys.stderr)
        sys.exit(2)

    # 子进程调用案例验证脚本（隔离异常, 独立退出码）
    cmd = [sys.executable, script_path, csv_path, json_out, md_out]
    if stdout_log:
        cmd.append(stdout_log)
    rc = subprocess.call(cmd)
    return rc


if __name__ == "__main__":
    sys.exit(main())
