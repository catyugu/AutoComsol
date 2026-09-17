# logs/ — 实验日志归档

## 命名约定

日志以**文件名前缀 `YYYY-MM`**（年-月）归档，**不建子目录**：

- `logs/YYYY-MM-lab-notebook.md` — 该月的实验台账（按时间顺序追加，最新在底部）。
  条目标题用 `## YYYY-MM-DD <标题>`；同一日期下的短条目可归入一个 `## YYYY-MM-DD` 段，
  段内条目降为 `### <标题>`。新条目写入**当前月份**的台账；跨月时新建
  `logs/<YYYY-MM>-lab-notebook.md`，并在下面的月份索引补一行。
- `logs/YYYY-MM-<命令名>-help.log` 等 — 本机捕获的命令输出/探针日志，前缀同捕获月份。
- 主题型参考文档不按月切分，留在 lab 根目录：`local-evidence-index.md`（证据索引）、
  `machine-profile.md`（本机环境）、`commands.lock.md`（命令模板）、`case-naming.md`（命名与映射）。
- 只有台账 `.md` 入库（见 `.gitignore`）；其余捕获日志属机器本地产物，不入库。
- `runs/<key>/` 下的 `batch.log` / `run.stdout.log` 是单次运行产物（每次覆盖），不按月归档。

## 月份索引

| 月份 | 台账 | 内容 |
| --- | --- | --- |
| 2026-08 | `2026-08-lab-notebook.md` | 环境发现 → 最小编译基线 → 各物理场与耦合案例（emw / Revolve / 非线性 / Array / 模态） |
| 2026-09 | `2026-09-lab-notebook.md` | 高阶物理场离散阶次、二阶几何网格导出、案例精简与日志归档 |

## 全局设置（跨月不变）

- 工作根目录: `E:\code\playground\AutoComsol\comsol-java-skill-lab`
- 资源上限（占位符未定义，采用保守值）: 单次求解 10 min，内存 8 GB，并发 1
- 平台: Windows 11 Home China 10.0.26200，shell: bash (Git Bash 风格)
- 起止时间: 2026-08-02 开始

## 运行规则

- 每运行使用独立 run-id 目录: `YYYYMMDD-HHMMSS-实验名-短哈希`
- 命令执行记录: 退出码、耗时、关键 stdout/stderr、生成文件清单
- 结果分类: PASS / PASS_WITH_WARNINGS / FAIL / SKIPPED / RESOURCE_LIMIT
