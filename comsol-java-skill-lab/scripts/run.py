#!/usr/bin/env python3
"""
run.py — COMSOL Java 实验封装（跨平台）
用法:
    python run.py compile <class-name>              # 编译 src/{analytic,physical}/<class>.java
    python run.py run <class-name> <run-dir> [args...]   # 批处理运行
    python run.py all <class-name> <run-dir> [args...]   # 编译+运行

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

SRC_DIR = Path(__file__).resolve().parent.parent / "src"
BUILD_DIR = Path(__file__).resolve().parent.parent / "build" / "classes"
TIMEOUT_SEC = 600  # 默认单次求解超时（秒）
# 源码按验证 tier 分层; 编译时合并编译全部 tier（共享辅助类自动包含）
SRC_TIERS = [SRC_DIR / "analytic", SRC_DIR / "physical"]


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
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    out = BUILD_DIR / f"{class_name}.compile.stdout.log"
    err = BUILD_DIR / f"{class_name}.compile.stderr.log"

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
        label = "comsol-javac"
    else:
        # 回退: comsolcompile 逐个编译（class 输出到源文件旁，需后续移动）
        rc = 0
        for s in all_sources:
            p = subprocess.run(
                [comp, str(s)], cwd=cwd or s.parent, capture_output=True, text=True
            )
            out.write_text(p.stdout, encoding="utf-8")
            err.write_text(p.stderr, encoding="utf-8")
            if p.returncode != 0:
                rc = p.returncode
                break
        class_file = SRC_DIR / f"{class_name}.class"
        return rc, class_file.exists()

    proc = subprocess.run(cmd, capture_output=True, text=True)
    out.write_text(proc.stdout, encoding="utf-8")
    err.write_text(proc.stderr, encoding="utf-8")
    class_file = BUILD_DIR / f"{class_name}.class"
    print(f"[compile] tool={label} rc={proc.returncode} class={class_file}")
    return proc.returncode, class_file.exists()


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


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    action = sys.argv[1]
    if action == "compile":
        class_name = sys.argv[2]
        rc, ok = compile_java(class_name)
        print(f"compile rc={rc} class_exists={ok}")
        sys.exit(0 if rc == 0 and ok else 1)
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
        print(f"compile rc={rc} class_exists={ok}")
        if rc != 0 or not ok:
            sys.exit(1)
        rc, status = run_batch(class_name, run_dir, args)
        print(json.dumps(status, indent=2))
        sys.exit(0 if rc == 0 else 1)
    else:
        print(f"unknown action: {action}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
