# machine-profile.md — 本机环境证据

生成时间: 2026-08-02
证据方式: 本机命令实际执行输出，全部为只读探测，无副作用。

## 操作系统

- Windows 11 Home China，版本 10.0.26200（OS Version 来自会话环境）
- Shell: bash (Git Bash / MSYS2 风格)，`/c`、`/d` 驱动器路径写法
- 路径含空格: 已用引号包裹验证（`"/d/Program Files/COMSOL/..."`）

## 架构

- x86-64 (PE32+ console executable for MS Windows 6.00, x86-64) — 证据: comsolcompile.exe 的 `file` 输出

## Java

- 系统 Java: OpenJDK 23.0.2 (Temurin-23.0.2+7)，JAVA_HOME=`E:\env\java\.jdks\temurin-23.0.2` — 证据: `java -version` 输出
- javac 在 PATH: `E:\env\java\.jdks\temurin-23.0.2\bin\javac`
- COMSOL 自带 JRE: `D:\Program Files\COMSOL\COMSOL62\Multiphysics\java\win64\jre\` — 证据: 目录存在 + comsolbatch.ini 中 `-vm ..\..\java\win64\jre\bin\server\jvm.dll`
- COMSOL Java API 的编译/运行环境要求: JavaSE-11（model jar manifest）、JavaSE-1.8（api jar manifest）

## COMSOL 版本与安装

- 版本: COMSOL Multiphysics 6.2.0.290 — 证据: `comsolcompile -version` 输出 "COMSOL Multiphysics 6.2.0.290"，exit=0
- 安装根目录: `D:\Program Files\COMSOL\COMSOL62\Multiphysics\` — 证据: `command -v comsolcompile` 解析路径
- readme.txt: "COMSOL 6.2.0.290 README"

## 可执行文件

| 命令 | 实际路径 | PATH 中 |
| --- | --- | --- |
| comsolcompile | `D:\Program Files\COMSOL\COMSOL62\Multiphysics\bin\win64\comsolcompile` | 是 |
| comsolbatch | `D:\Program Files\COMSOL\COMSOL62\Multiphysics\bin\win64\comsolbatch` | 是 |
| comsolmphserver 等 | 同 bin/win64 目录 | 是 |

两者均为 PE32+ x86-64 console 可执行文件（.exe），使用 Eclipse Equinox launcher 启动。

## 可用模块（applications 目录证据）

已安装模块（按 applications/ 目录列出）：

- ACDC_Module, Heat_Transfer_Module, Structural_Mechanics_Module
- 其余: Acoustics, Battery_Design, CAD_Import, CFD, Chemical_Reaction_Engineering, Composite_Materials, Corrosion, Design, ECAD_Import, Electrochemistry, Electrodeposition, Fatigue, Fuel_Cell_and_Electrolyzer, Geomechanics, Liquid_and_Gas_Properties, MEMS, Metal_Processing, Microfluidics, Mixer, Molecular_Flow, Multibody_Dynamics, Nonlinear_Structural_Materials, Optimization, Particle_Tracing, Pipe_Flow, Plasma, Polymer_Flow, Porous_Media_Flow, Ray_Optics, RF, Rotordynamics, Semiconductor, Subsurface_Flow, Uncertainty_Quantification, Wave_Optics, LiveLink 系列
- plugins 中确认: com.comsol.acdc_1.0.0.jar, com.comsol.heat_1.0.0.jar, com.comsol.solid_1.0.0.jar 存在
- 总数: 300 个 jar（plugins 目录 `.jar` 计数）

## Java API 类路径结构（jar 归属证据）

| 包 | 所在 jar | 证据 |
| --- | --- | --- |
| `com.comsol.model.Model`, `ModelNode`, `Selection`, `Study`, `Physics`, `Geometry`, `Mesh`, `Solver`, `Dataset`, `util.ModelUtil` 等公开接口 | `plugins/com.comsol.api_1.0.0.jar` (9.1MB, 662 行清单) | unzip -l 输出 |
| `com.comsol.model.*` 内部实现 | `plugins/com.comsol.model_1.0.0.jar` (9.7MB, 6715 类) | unzip -l 输出 |
| 物理场/模块实现 | `com.comsol.heat`, `com.comsol.solid`, `com.comsol.acdc` 等 jar | unzip -l plugins |
| 基础 util | `com.comsol.util_1.0.0.jar` | ls plugins |

comsolcompile 使用 Eclipse RCP 启动（equinox launcher），自动解析 OSGi bundle 类路径，无需手工拼接全部 jar；若需额外类路径使用 `-classpathadd`。

## 文档与示例

- 本地 PDF 文档仅安装了 License 管理 (FlexNet/fnp_LicAdmin.pdf)，未安装完整 Programming Reference 手册（doc/pdf 下只有 FlexNet）
- demo 目录仅有 3 个 Java 文件（beammodel Swing 示例），无建模 Java 示例
- 关键结论: 本机缺少 COMSOL 官方 Java 建模示例和 PDF 手册，API 方法名必须以 jar 内类清单 + 最小验证实验为准，不得凭记忆臆造

## 资源限制（占位符未定义，采用保守值）

- 单次求解: 10 min
- 内存: 8 GB
- 并发: 1
