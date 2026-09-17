#!/usr/bin/env python3
"""
run.py — COMSOL Java 实验封装（跨平台）
用法:
    python run.py compile <class-name>              # 编译 src/{analytic,physical}/<class>.java
    python run.py run <class-name> <run-dir> [args...]   # 批处理运行
    python run.py all <class-name> <run-dir> [args...]   # 编译+运行
    python run.py sweep [--keys K1,K2] [--skip-pass] [--runs-root DIR]  # 全案例回归

不硬编码 COMSOL 安装路径：通过 PATH 发现 comsolcompile/comsolbatch，
或通过环境变量 COMSOL_COMPILE / COMSOL_BATCH 指定。

行为:
- 每个运行写入独立目录（run-dir），输出 stdout/stderr/batch.log/status.json
- 严格检查: 编译产物存在、批处理退出码、日志错误标志
- status.json 记录 compile_rc/batch_rc/mph_exists/log_flags

tier 结构:
- src/analytic/  有解析解验证的案例
- src/physical/  仅流程可运行/物理合理性的案例
"""
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

# sweep 复用 health_check 的 REGISTRY（单一事实源，避免两处维护漂移）。
# 实验键 → "tier/script.py"，键同时决定 runs/<key>/ 目录名。
sys.path.insert(0, str(Path(__file__).resolve().parent))
from health_check import REGISTRY

SRC_DIR = Path(__file__).resolve().parent.parent / "src"
BUILD_DIR = Path(__file__).resolve().parent.parent / "build" / "classes"
TIMEOUT_SEC = 600  # 默认单次求解超时（秒）
# 源码按验证 tier 分层; 编译时合并编译全部 tier（共享辅助类自动包含）
SRC_TIERS = [SRC_DIR / "analytic", SRC_DIR / "physical"]
RUNS_ROOT = Path(__file__).resolve().parent.parent / "runs"


def find_bin(name):
    """在 PATH 中定位可执行文件；找不到返回 None。"""
    return shutil.which(name)


def get_comsol_commands():
    """定位 comsolcompile / comsolbatch。优先环境变量，其次 PATH。"""
    comp = os.environ.get("COMSOL_COMPILE") or find_bin("comsolcompile")
    batch = os.environ.get("COMSOL_BATCH") or find_bin("comsolbatch")
    if not comp or not batch:
        print(
            "ERROR: comsolcompile/comsolbatch not found. "
            "Set COMSOL_COMPILE/COMSOL_BATCH or add to PATH.",
            file=sys.stderr,
        )
        sys.exit(2)
    return comp, batch


def locate_source(class_name):
    """在 tier 子目录中定位 <class>.java；找不到返回 None。"""
    for tier in SRC_TIERS:
        p = tier / f"{class_name}.java"
        if p.exists():
            return p
    return None


def compile_java(class_name, cwd=None):
    """编译 src/<tier>/<class>.java（含共享辅助类）。

    关键: 必须用 COMSOL 自带 javac（或 comsolcompile），因为系统 JDK(23)
    编译的 class 是 v67，comsolbatch 内置 JRE(Java11) 只识别到 v55。
    证据: "class file version 67.0, this version only recognizes up to 55.0"

    策略: 用 COMSOL 自带 javac 编译 src 下所有 .java（共享辅助类自动包含），
    输出 .class 到 build/classes/。若自带 javac 不存在则回退 comsolcompile。
    """
    src = locate_source(class_name)
    if src is None:
        tiers = " ".join(str(t) for t in SRC_TIERS)
        print(
            f"ERROR: source not found in {tiers}: {class_name}.java",
            file=sys.stderr,
        )
        sys.exit(2)
    return compile_all_sources(label=class_name)


def compile_all_sources(label="all"):
    """编译 src/{analytic,physical}/ 全部 .java（共享辅助类自动包含）。

    返回 (rc, class_file_exists)。label 用于编译日志文件名。
    sweep 用该函数一次编译全部源；compile_java 复用。
    """
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    out = BUILD_DIR / f"{label}.compile.stdout.log"
    err = BUILD_DIR / f"{label}.compile.stderr.log"

    # 定位 COMSOL 自带 javac（在 comsolcompile 同级目录 java/.../bin/javac.exe）
    comp, _ = get_comsol_commands()
    comsol_javac = None
    if comp:
        # comsolcompile 位于 <root>/bin/win64/comsolcompile
        root = Path(comp).resolve().parents[2]
        cand = root / "java" / "win64" / "jre" / "bin" / "javac.exe"
        if cand.exists():
            comsol_javac = cand

    api_jar = None
    if comsol_javac:
        # javac 位于 <root>/java/win64/jre/bin/javac.exe；root = Multiphysics
        # 向上: javac/bin/jre/win64/java/... <root>/java/win64/jre/bin
        # javac.parents: 0=bin 1=jre 2=win64 3=java 4=root(Multiphysics)
        root = comsol_javac.resolve().parents[4]
        plugins = root / "plugins"
        api_jar = plugins / "com.comsol.api_1.0.0.jar"
        print(f"[compile] comsol_root={root} api_jar_exists={api_jar.exists()}")
        if not api_jar.exists():
            # 兜底: 在 plugins 目录搜索 com.comsol.api_*.jar
            candidates = sorted(plugins.glob("com.comsol.api_*.jar"))
            api_jar = candidates[0] if candidates else None

    all_sources = sorted(p for tier in SRC_TIERS for p in tier.glob("*.java"))
    if comsol_javac:
        cmd = [str(comsol_javac), "-encoding", "UTF-8"]
        if api_jar and api_jar.exists():
            cmd += ["-cp", str(api_jar)]
        cmd += ["-d", str(BUILD_DIR)] + [str(s) for s in all_sources]
        tool = "comsol-javac"
        proc = subprocess.run(cmd, capture_output=True, text=True)
        rc = proc.returncode
        out.write_text(proc.stdout or "", encoding="utf-8")
        err.write_text(proc.stderr or "", encoding="utf-8")
    else:
        # 回退: comsolcompile 逐个编译（class 输出到源文件旁，需后续移动）
        rc = 0
        for s in all_sources:
            p = subprocess.run(
                [comp, str(s)], cwd=s.parent, capture_output=True, text=True
            )
            out.write_text(p.stdout, encoding="utf-8")
            err.write_text(p.stderr, encoding="utf-8")
            if p.returncode != 0:
                rc = p.returncode
                break
        tool = "comsolcompile"
    print(f"[compile] tool={tool} rc={rc} sources={len(all_sources)} "
          f"class_dir={BUILD_DIR}")
    return rc, True


def run_batch(class_name, run_dir, args, timeout=TIMEOUT_SEC):
    """运行 comsolbatch。返回 (rc, status_dict)。"""
    comp, batch = get_comsol_commands()
    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    class_file = BUILD_DIR / f"{class_name}.class"
    if not class_file.exists():
        print(f"ERROR: class not found: {class_file}. Compile first.", file=sys.stderr)
        sys.exit(2)

    # 默认 target args: args[0]=mph 保存路径, args[1]=CSV 导出路径。
    # 若调用方未传，则落到 run-dir 内，避免 CSV/mph 写到未知工作目录导致
    # 相对路径丢失（实测: 无 args 时 export 相对路径抛 NPE）。
    if not args:
        args = [str(run_dir / f"{class_name}.mph"), str(run_dir / "field.csv")]

    cmd = [
        batch,
        "-inputfile",
        str(class_file),
        "-outputfile",
        str(run_dir / "out.mph"),
        "-batchlog",
        str(run_dir / "batch.log"),
        "-stoptime",
        str(timeout),
        "-np",
        "1",
        # target arguments（紧跟在 options 之后，传给 Java main 的 args）
        *args,
    ]

    start = time.time()
    proc = subprocess.run(cmd, capture_output=True, text=True)
    elapsed = time.time() - start

    (run_dir / "run.stdout.log").write_text(proc.stdout, encoding="utf-8")
    (run_dir / "run.stderr.log").write_text(proc.stderr, encoding="utf-8")

    # 状态汇总
    batch_log = run_dir / "batch.log"
    flags = "clean"
    if batch_log.exists():
        text = batch_log.read_text(encoding="utf-8", errors="replace").lower()
        # 排除 "error estimates"/"solution error estimates" (求解器常规输出)。
        # 这些是残差估计, 不是错误。
        error_kw = (
            "error running",
            "exception",
            " failed",
            "failed to",
            "diverged",
            "out of memory",
            "license",
        )
        if any(k in text for k in error_kw):
            flags = "error_present"

    mph_found = any(p.suffix == ".mph" for p in run_dir.iterdir())
    status = {
        "class": class_name,
        "batch_rc": proc.returncode,
        "elapsed_sec": round(elapsed, 1),
        "mph_exists": mph_found,
        "batchlog_exists": batch_log.exists(),
        "log_flags": flags,
    }
    (run_dir / "status.json").write_text(json.dumps(status, indent=2), encoding="utf-8")
    return proc.returncode, status


def key_to_class(key):
    """REGISTRY 键 → Java 类名。

    验证脚本名 (sm_plate_hole_stationary.py) → 类名 (SmPlateHoleStationary)。
    camel-case 规则, 特例: EcTSm 前缀 (脚本 ec_tsm_* → 类 EcTSm*, 非 EcTsm*)。
    """
    script = REGISTRY[key]
    base = os.path.basename(script).replace(".py", "")
    cls = "".join(p.title() for p in base.split("_"))
    if cls.startswith("EcTsm"):
        cls = "EcTSm" + cls[len("EcTsm"):]
    return cls


# 需额外 target args 的案例: 键 → 追加的文件名 (相对 run_dir)。
# 约定 args[0]=mph, args[1]=field.csv (验证脚本读取), 追加项从 args[2] 起。
SWEEP_EXTRA_ARGS = {
    "TFinArray": ["TFinArray.png"],          # args[2] = 图像导出路径 (探针: 必须绝对)
    "SmCantEig": ["modes.csv"],              # args[2] = 模态位移导出路径
}


def run_sweep(keys=None, skip_pass=False, runs_root=None):
    """全案例回归：按 REGISTRY 逐键 编译→运行→健康检查→聚合。

    - 一次编译全部 src（既有 compile_java 语义），单个源编译错误会中断
      编译并报出该源（sweep 报错并继续，不静默）。
    - 每键独立运行到 runs/<key>/（案例互相独立，无共享状态）。
    - 逐键调用 health_check.py 生成 health.json/health.md（验证脚本隔离异常）。
    - 聚合各 health.json → runs/aggregate-summary.json + aggregate-summary.md。
    - 退出码: 全 PASS=0；任一 FAIL 或缺验证脚本=1。

    参数:
      keys: 只运行指定实验键列表（默认全部 REGISTRY）。
      skip_pass: 跳过上次 health.json 已 PASS 的键（只重跑失败/缺失）。
    """
    runs_root = Path(runs_root) if runs_root else RUNS_ROOT
    runs_root.mkdir(parents=True, exist_ok=True)

    if keys:
        missing = [k for k in keys if k not in REGISTRY]
        if missing:
            print(f"ERROR: unknown keys {missing}. Known: {sorted(REGISTRY)}",
                  file=sys.stderr)
            sys.exit(2)
        order = [k for k in REGISTRY if k in keys]
    else:
        order = sorted(REGISTRY)

    # ---- 一次编译全部源 ----
    print(f"[sweep] compile all sources ({len(SRC_TIERS)} tiers) ...")
    rc, _ = compile_all_sources(label="sweep")
    if rc != 0:
        print(f"[sweep] COMPILE FAILED rc={rc} (fix failing source then retry).",
              file=sys.stderr)
        return 1

    rows = []
    any_fail = False
    for key in order:
        script = REGISTRY[key]
        run_dir = runs_root / key
        json_out = run_dir / "health.json"
        md_out = run_dir / "health.md"

        # --skip-pass: 上次已 PASS 且 CSV 存在 → 跳过
        if skip_pass and json_out.exists():
            try:
                prev = json.loads(json_out.read_text(encoding="utf-8"))
                if prev.get("overall_status") == "PASS":
                    print(f"[sweep] skip {key} (already PASS)")
                    rows.append(_summary_row(key, script, prev))
                    continue
            except (OSError, ValueError):
                pass

        try:
            class_name = key_to_class(key)
            print(f"[sweep] run {key} (class {class_name}) -> {run_dir}")
            args = [str(run_dir / f"{class_name}.mph"),
                    str(run_dir / "field.csv")]
            args += [str(run_dir / f) for f in SWEEP_EXTRA_ARGS.get(key, [])]
            _, status = run_batch(class_name, run_dir, args)
        except SystemExit as e:
            status = {"batch_rc": e.code if isinstance(e.code, int) else -1,
                      "elapsed_sec": 0, "mph_exists": False,
                      "batchlog_exists": False, "log_flags": "compile_or_run_error"}
        except Exception as e:  # noqa: BLE001 — 每键隔离，失败不中断 sweep
            status = {"batch_rc": -1, "elapsed_sec": 0, "mph_exists": False,
                      "batchlog_exists": False, "log_flags": f"error: {e}"}

        csv_path = run_dir / "field.csv"
        if not csv_path.exists():
            # run_batch 默认 args 落在 run-dir/field.csv；若不存在则无法验证
            print(f"[sweep] {key}: csv not found {csv_path}", file=sys.stderr)
            rows.append(_summary_row(key, script, {
                "experiment": key, "overall_status": "FAIL",
                "reason": "csv missing", "elapsed_sec": status.get("elapsed_sec", 0),
                "log_flags": status.get("log_flags")}))
            any_fail = True
            continue

        ver_rc = _run_verification(key, csv_path, json_out, md_out)
        try:
            health = json.loads(json_out.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            health = {"experiment": key, "overall_status": "FAIL",
                      "reason": "health.json unreadable"}
        health.setdefault("elapsed_sec", status.get("elapsed_sec", 0))
        health.setdefault("log_flags", status.get("log_flags"))
        if ver_rc != 0 or health.get("overall_status") != "PASS":
            any_fail = True
        rows.append(_summary_row(key, script, health))

    summary = {
        "aggregate_status": "PASS" if not any_fail else "FAIL",
        "cases": rows,
        "total": len(rows),
        "pass": sum(1 for r in rows if r["status"] == "PASS"),
        "fail": sum(1 for r in rows if r["status"] != "PASS"),
    }
    _write_summary(summary, runs_root)
    print(f"[sweep] {summary['pass']}/{summary['total']} PASS")
    return 0 if not any_fail else 1


def _lab_python():
    """优先 .venv 的 python (验证脚本依赖 numpy); 无则回退 sys.executable。"""
    venv = Path(__file__).resolve().parent.parent / ".venv"
    cand = venv / "Scripts" / "python.exe"
    return str(cand) if cand.exists() else sys.executable


def _run_verification(key, csv_path, json_out, md_out):
    """子进程调用 health_check.py 做健康检查；返回其退出码。"""
    hc = Path(__file__).resolve().parent / "health_check.py"
    proc = subprocess.run(
        [_lab_python(), str(hc), key, str(csv_path), str(json_out), str(md_out)],
        capture_output=True, text=True)
    if proc.returncode != 0:
        print(f"[sweep] {key}: health_check rc={proc.returncode}\n"
              f"{proc.stdout}\n{proc.stderr}", file=sys.stderr)
    return proc.returncode


def _summary_row(key, script, health):
    """从 health dict 抽取汇总行；容忍缺失字段。"""
    checks = health.get("checks", []) or []
    failed = [c["name"] for c in checks if not c.get("ok")]
    return {
        "key": key,
        "script": script,
        "tier": script.split("/")[0],
        "status": health.get("overall_status", "FAIL"),
        "num_checks": len(checks),
        "failed_checks": failed,
        "elapsed_sec": health.get("elapsed_sec", 0),
        "log_flags": health.get("log_flags", "n/a"),
        "reason": health.get("reason"),
    }


def _write_summary(summary, runs_root):
    """写出 aggregate-summary.json + aggregate-summary.md。"""
    json_path = runs_root / "aggregate-summary.json"
    md_path = runs_root / "aggregate-summary.md"
    json_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False),
                         encoding="utf-8")
    lines = ["# Aggregate Sweep Summary", "",
             f"**Overall: {summary['aggregate_status']}**  "
             f"({summary['pass']}/{summary['total']} PASS)", ""]
    lines.append("| key | tier | status | checks | failed | elapsed(s) | flags |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- |")
    for r in summary["cases"]:
        lines.append(
            f"| {r['key']} | {r['tier']} | {r['status']} | {r['num_checks']} | "
            f"{','.join(r['failed_checks']) or '-'} | {r['elapsed_sec']} | "
            f"{r['log_flags']} |")
    md_path.write_text("\n".join(lines), encoding="utf-8")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    action = sys.argv[1]
    if action == "compile":
        class_name = sys.argv[2]
        rc, ok = compile_java(class_name)
        class_exists = (BUILD_DIR / f"{class_name}.class").exists()
        print(f"compile rc={rc} class_exists={class_exists}")
        sys.exit(0 if rc == 0 and class_exists else 1)
    elif action == "run":
        class_name, run_dir = sys.argv[2], sys.argv[3]
        args = sys.argv[4:]
        rc, status = run_batch(class_name, run_dir, args)
        print(json.dumps(status, indent=2))
        sys.exit(0 if rc == 0 else 1)
    elif action == "all":
        class_name, run_dir = sys.argv[2], sys.argv[3]
        args = sys.argv[4:]
        rc, ok = compile_java(class_name)
        class_exists = (BUILD_DIR / f"{class_name}.class").exists()
        print(f"compile rc={rc} class_exists={class_exists}")
        if rc != 0 or not class_exists:
            sys.exit(1)
        rc, status = run_batch(class_name, run_dir, args)
        print(json.dumps(status, indent=2))
        sys.exit(0 if rc == 0 else 1)
    elif action == "sweep":
        keys = None
        skip_pass = False
        runs_root = None
        i = 2
        while i < len(sys.argv):
            arg = sys.argv[i]
            if arg == "--keys":
                keys = [k.strip() for k in sys.argv[i + 1].split(",") if k.strip()]
                i += 2
            elif arg == "--skip-pass":
                skip_pass = True
                i += 1
            elif arg == "--runs-root":
                runs_root = sys.argv[i + 1]
                i += 2
            else:
                print(f"unknown sweep option: {arg}", file=sys.stderr)
                sys.exit(2)
        sys.exit(run_sweep(keys=keys, skip_pass=skip_pass, runs_root=runs_root))
    else:
        print(f"unknown action: {action}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
