# AGENTS

## 项目目标

我们将进行java的各种试验，目的是不断完善和强化 `autocomsol` 这个 skill。这个 skill 旨在让 agent 可以从 Java 开始，借助 `comsolcompile` 编译成 `.mph` 文件，并通过 `comsolbatch` 运行，完成全链路的仿真。
我们不尝试用大量代码来规训 AI 的行为，而是试图通过精炼的文档和大量案例，让 AI 能够掌握如何做几何建模、材料分配、参数化扫描、求解配置、后处理与结果导出等工作。

## 目录结果

- `comsol-java-skill-lab` 目录下是用于试验的各类模型 Java 代码和详细的经验、日志文档等。
- `autocomsol` 目录下是成品发布的 skill。
- `playground` 作为尚不稳定的实验进行的地方。

## 目录分层约定

- 案例按验证严谨度分三层（`src/`、`scripts/verifications/`、`autocomsol/references/examples/` 下均同构）:
    - `analytic/` — 有解析解验证的案例
    - `physical/` — 无解析解、仅流程可运行/物理合理性的案例
    - `demonstration/` — 纯 API 用法演示案例（只说明 API 入口/键名/合法取值，无验证脚本、
      不进 REGISTRY/sweep；命名 `<ApiTopic>Demonstration`；只在 `src/` 与 `references/examples/` 两处同步）
- 有解析解的案例进 analytic 层；无解析解时才进 physical 层；只为说明 API 用法、不做验证的进 demonstration 层。

## 回归与探针纪律

- 全案例回归用 `python scripts/run.py sweep`（复用 `scripts/health_check.py` 的 REGISTRY 为单一事实源，
  逐键 编译→运行→健康检查→聚合 `runs/aggregate-summary.json/md`；支持 `--keys/--skip-pass`）。
  案例之间串行，单案例内部按 `-np`（默认 `min(8, CPU 核数)`，可用环境变量 `COMSOL_NP` 覆盖）多核求解。
  新增案例三处同步后，必须 `run.py sweep` 全回归通过。
- 任何未经验证的新 COMSOL API 字符串，先按 `autocomsol/references/api-validation-probes.md` 验证
  （jar 类清单 / 挖掘官方 .mph / 临时探针），再写进正式案例；探针类不入库。
- 验证脚本用 `.venv/Scripts/python.exe` 运行（依赖 numpy）。
- 案例库保持精简：案例入 `src/` + `scripts/verifications/` + `autocomsol/references/examples/` 三处的前提是
  它带来**独特展示价值**（独特 API 模式，或独特验证方法）。仅物理场景不同、API 覆盖与既有案例重合的案例不入库；
  新增前先核对既有案例的 API 覆盖（REGISTRY 是唯一清单）。

## 日志与归档约定

- 实验台账按**年-月前缀**归档: `comsol-java-skill-lab/logs/YYYY-MM-lab-notebook.md`
  （`logs/` 下不建子目录，`YYYY-MM` 直接做文件名前缀）。新条目写入当前月份台账，跨月新建
  对应前缀的文件。约定、全局设置与月份索引见 `logs/README.md`。
- 命令捕获日志（`YYYY-MM-*-help.log` 等）前缀同捕获月份；主题型参考文档（local-evidence-index /
  machine-profile / commands.lock / case-naming）不按月切分，留在 lab 根目录。只有台账 `.md`
  入库，其余日志为机器本地产物。
