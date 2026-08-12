#!/usr/bin/env python3
"""
common.py — 验证脚本共享基础设施（跨平台，纯 Python）

被 scripts/verifications/ 下各案例验证脚本调用。

提供:
  load_csv(path)           解析 COMSOL Data 导出 CSV → (headers, rows)
  numeric_checks(h, rows)  数值健康检查（空数据/NaN/Inf/列范围）
  emit_report(...)         输出 health.json + health.md，返回退出码
  REQUIREMENTS_MARKER      调度器识别每个案例验证脚本的标记
"""
import csv
import json
import math
import os
import sys

# 案例验证脚本以这个 marker 声明自己的实验键。调度器据此分发。
# 每个脚本定义: CASE_KEY = "E1"  等。
CASE_KEY = None


def _looks_like_header(line):
    """判断 % 注释行是否实为表头（COMSOL 把列名写在 % 行）。

    表头特征: 首字段为坐标名 x/y/X/Y（大小写不敏感），或行内含 '@ t='。
    """
    first = line[0].strip().lower()
    return first in ("x", "y", "z", "x (m)", "y (m)", "z (m)", "t") or \
        any("@ t=" in cell for cell in line)


def load_csv(path):
    """解析 COMSOL Data 导出 CSV。返回 (headers, rows[list of float lists])。

    跳过 % 开头注释行；表头为第一行非注释非空行。
    兼容瞬态导出: COMSOL 把列名写在 % 注释行里 (如 "% x,y,T (K) @ t=0,...")，
    此时若 headers 尚未赋值且 % 行像表头, 也认作表头。
    """
    headers = None
    rows = []
    with open(path, newline="", encoding="utf-8-sig") as f:
        rd = csv.reader(f)
        for line in rd:
            if not line or line[0].startswith("%"):
                if headers is None and _looks_like_header(line):
                    headers = [h.strip() for h in line]
                continue
            if headers is None:
                headers = [h.strip() for h in line]
                continue
            try:
                rows.append([float(v) for v in line[: len(headers)]])
            except (ValueError, IndexError):
                continue
    return headers, rows


def numeric_checks(headers, rows):
    """数值健康检查。返回 dict。"""
    n = len(rows)
    nan_inf = sum(1 for row in rows for v in row if math.isnan(v) or math.isinf(v))
    cols = []
    if headers and rows:
        for c in range(len(headers)):
            col = [r[c] for r in rows if c < len(r)]
            cols.append(
                {
                    "name": headers[c],
                    "min": float(min(col)),
                    "max": float(max(col)),
                    "mean": float(sum(col) / len(col)) if col else None,
                }
            )
    return {"num_rows": n, "nan_inf": nan_inf, "empty": n == 0, "columns": cols}


def emit_report(case_key, csv_path, checks, json_out, md_out, evidence=None):
    """输出 health.json + health.md，返回进程退出码（PASS=0/FAIL=1）。

    checks: list[dict]，每项含 name/ok/value/threshold/unit（value 需 JSON 可序列化）。
    evidence: 可选 dict，附加到报告。
    """
    if os.path.exists(csv_path):
        numeric = numeric_checks(*load_csv(csv_path))
    else:
        numeric = {"num_rows": 0, "nan_inf": 0, "empty": True, "columns": []}
    all_ok = (
        (not numeric["empty"])
        and numeric["nan_inf"] == 0
        and all(c["ok"] for c in checks)
    )
    status = "PASS" if all_ok else "FAIL"

    health = {
        "experiment": case_key,
        "overall_status": status,
        "csv": csv_path,
        "numeric": numeric,
        "checks": checks,
        "evidence": evidence or {},
    }
    with open(json_out, "w", encoding="utf-8") as f:
        json.dump(health, f, indent=2, ensure_ascii=False)

    with open(md_out, "w", encoding="utf-8") as f:
        f.write(f"# Health Check: {case_key}\n\n**Overall: {status}**\n\n")
        f.write(f"- CSV rows: {numeric['num_rows']}\n")
        f.write(f"- NaN/Inf: {numeric['nan_inf']}\n\n## Checks\n\n")
        for c in checks:
            f.write(
                f"- **{c['name']}**: {'PASS' if c['ok'] else 'FAIL'} "
                f"(value={c.get('value')}, threshold={c['threshold']}, "
                f"unit={c.get('unit')})\n"
            )
        if evidence:
            f.write("\n## Evidence\n\n")
            for k, v in evidence.items():
                f.write(f"- {k}: {v}\n")
    print(f"health status={status}")
    return 0 if status == "PASS" else 1


def check(name, ok, value, threshold, unit=""):
    """构造一个检查项 dict。"""
    return {
        "name": name,
        "ok": bool(ok),
        "value": value,
        "threshold": threshold,
        "unit": unit,
    }


if __name__ == "__main__":
    print("common.py: shared verification helpers (import, don't run)")
