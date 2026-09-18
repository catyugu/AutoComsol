# COMSOL Java 自动建模 Skill 研发 — 实验台账（2026-09）

本文件为 2026-09 的实验台账，随实验推进持续追加，禁止事后凭记忆补写。
归档约定、全局设置与运行规则见同目录 `README.md`；本文件覆盖：高阶物理场离散阶次、二阶几何网格导出、案例精简与日志归档。

## 2026-09-17 高阶物理场离散阶次 (ShapeProperty) — 案例 SmCantileverBendingStationary

- 用户要求: 跑通至少两个高阶物理场 (p>1 Lagrange) 案例; 先做悬臂梁弯曲的稳态解析解验证。
- **本机 API 实证 (ShapeProperty 入口)**:
    - 挖掘官方 mph dmodel.xml (carbon_fibers / heat_convection_2d / loaded_spring) 发现:
    `<PhysicsProp tag="ShapeProperty"><param param="order_temperature" value="1|1,'2'"/></PhysicsProp>`
    SolidMechanics 同样的 PhysicsProp 但参数是 `order_displacement="2s"` (数字 + 可选 's' = serendipity)
    - API: `physics().prop("ShapeProperty").set("order", "1/2/3/4")` 对 HeatTransfer/ConductiveMedia 全部通过
    - API: SolidMechanics 只能用 `order_displacement` (探针实测 `order` 拒绝); 接受 "1","2","3","4","2s","3s"
    - 直接 setString 反序列化得到 "Geometry shape function: Quadratic Lagrange" — 即真改求解器阶次
- **案例 SmCantileverBendingStationary**: 2D 矩形悬臂梁 (L=10, h=2), 左端 Fixed, 右端
  BoundaryLoad ForceArea FperArea=[M·y/I, 0, 0] (端部弯矩精确等效); 物理 SolidMechanics ν=0
  (消除 σ_yy/u_y); 显式 p=2 (二次 Lagrange); hmax=0.4 中等密度网格
- **解析解**: σ_xx(y) = M·y/I = 1.5·y (M=1, I=h³/12=2/3); σ_yy=0, σ_xy=0; u_x 沿 y 线性 (Euler-Bernoulli)
  注: 2D plane stress ν=0 时 u_y 仍有非零值 (自由 ε_yy), 不作验证
- **验证 (5 项, 全 PASS)**:
    - σ_xx 全场 max_err = 3.33e-10 (机器精度, 阈值 1e-6; 直接体现 p=2 优势)
    - σ_xx 中段 x_std = 6.63e-11 (纯弯曲判据)
    - u_x 在 x=4 沿 y 线性残差 = 1.78e-15 (机器精度)
    - σ_yy 中线最大 = 1.48e-13; σ_xy 中线最大 = 2.09e-11
- **对比基线 (探针运行 p=1 同网格)**:
    - p=1: σ_xx 中段 max_err = 6.40e-1 (~64% 相对误差, O(h))
    - p=2: σ_xx 中段 max_err = 3.33e-10 (机器精度)
    - 同一 hmax=0.4 网格, 阶次提升一档误差降低 10 个数量级 — p-refinement 强收敛的实证
- **关键调试**:
    - Java 反射调用 `prop("ShapeProperty")` 必须从 `getClass()` 拿 Method (`PhysicsPropClient` 接口无 prop 方法签名)
    - SolidMechanics 用 `set("order_displacement", "2")` (不是 `set("order", "2")`, 后者报 InvocationTargetException)
    - 2D 几何必须用 `Rectangle` 不能用 `Block` (Block 仅 3D); 2D 边界特征维度参数为 1 (不是 2)
    - BoundaryLoad LoadType 值是 `"ForceArea"` (不是 `"ForcePerArea"`); FperArea 是 [fx, fy, fz] 三分量字符串数组
    - SolidMechanics 应力分量变量名是大写 `solid.SX/SY/SXY` (本机实测, 2D plane stress)
- **3 处同步**: src/analytic/SmCantileverBendingStationary.java + scripts/verifications/analytic/sm_cantilever_bending_stationary.py +
  autocomsol/references/examples/analytic/SmCantileverBendingStationary.java + 同目录验证脚本
- **skill 同步**: case-naming.md 加 SmCantileverBendingStationary 映射 + 命名规则说明;
  physics-api-recipes.md 加 Element order (p-refinement) 行 + pitfall 段
- **回归**: sweep --keys SmCantileverBendingStationary,M1,SmCantEig,SmPlateHole 4/4 PASS
- 用户决策: 暂时只加这一个案例, 第二个高阶案例延后; run.py / health_check.py 注册 SmCantileverBendingStationary

## 2026-09-17 二阶几何网格导出 (sorder + Mesh 导出) — 案例 EcHollowCylinderStationary

- 用户要求: 把"导出二阶网格"的方法并入 autocomsol (来源: hellofem 的 EcCylinderOrder2Stationary 案例)。
- **探针 (ApiProbes, 临时类已删) 实证**:
    - 几何形状阶次 API: `component().sorder("automatic"|"linear"|"quadratic"|"cubic"|"quartic")`, 默认 automatic;
      数值字符串 "2" 被拒 (FlException "Invalid geometry shape function")。签名证据: `javap` 的 `ModelNode.sorder(String)`。
    - 官方模型挖掘: 7 个官方 .mph 的 action 历史里有 `t(s("/component/comp1")) m(s("sorder")) s("quadratic"|"linear")`
      (如 ultrasound_flow_meter_generic.mph) — 该 API 的权威字符串来源。
    - 导出单元阶次由几何形状阶次决定 (同一圆柱几何逐值实测): automatic/quadratic → edg2/tri2/tet2;
      linear → edg/tri/tet; cubic/quartic → 求解器日志 "Cubic/Quartic Lagrange" 但导出**仍是** P2 (导出上限二阶)。
    - 平面几何 (Block) + sorder("quadratic") → 仍导出 edg/tri/tet: 没有曲面实体就没有曲单元。
    - **Mesh 导出必须已有求解数据集**: 只建几何+网格时 `export().run()` 不抛异常但**不写文件** (静默无输出)。
- **案例 EcHollowCylinderStationary**: 3D 空心圆柱 (r_in=0.01, r_out=0.03, h=0.02) 导电稳态,
  内表面 Terminal V0=1V / 外表面 Ground / 端面默认绝缘; FreeTet hmax=3mm; 解析 V(r)=V0·ln(r/r_out)/ln(r_in/r_out)。
  导出 args[2]=mesh.mphtxt (SWEEP_EXTRA_ARGS 新增项), 验证脚本从 CSV 同目录读 mesh.mphtxt。
- **踩坑 (真实错误, 被验证脚本的 V 剖面检查拦住)**: Difference 把每个圆柱面切成 4 片
  (面 1,2,7,10 = r_out; 5,6,8,9 = r_in)。只选 1 片时 BC 只覆盖部分边界 → V 与解析解差 0.5 V,
  而 COMSOL 不报任何错。改为按半径取全部面 (facesAtRadius → int[]) 后恢复。
- **验证 (10 项全 PASS, runs/_dev_EcHollowCyl)**:
    - 网格: 类型集 = {vtx, edg2, tri2, tet2}, 每单元 1/3/6/10 节点
    - 边中点贴解析圆柱面: max|r-R|/R = 1.7e-16 (内) / 2.3e-16 (外); 中点/弦中点偏离比 ≤ 8.7e-10
    - 场: max|V-V_ana(r)| = 3.1e-4 V (阈值 1e-3); 内壁 V=1 / 外壁 V=0 (偏差 0); 同半径桶散布 7.4e-3 V
- **反例对照 (fails-before)**: 同一案例改 sorder("linear") → 日志 "Linear Lagrange", 导出 edg/tri/tet,
  验证脚本 mesh_quadratic_types / mesh_nodes_per_elem 两项 FAIL (临时探针类已删)。
- **3 处同步**: src/analytic/EcHollowCylinderStationary.java + scripts/verifications/analytic/ec_hollow_cylinder_stationary.py +
  autocomsol/references/examples/analytic/EcHollowCylinderStationary.java; health_check.py REGISTRY 与 run.py SWEEP_EXTRA_ARGS 已注册。
- **skill 同步**: case-naming.md 加案例行; physics-api-recipes.md 加 Geometry shape order 行 + 3 条 pitfall
  (布尔切片选面 / sorder 与 ShapeProperty 的区别 / Mesh 导出静默无输出) + .mphtxt 块结构读法。

## 2026-09-17 案例精简 + 日志按月归档

- 用户要求: (1) 案例库过多、易污染知识库，删除无独特展示价值的案例; (2) 日志按年-月归档。
- **精简判据**: 案例入 `src/` + `scripts/verifications/` + `autocomsol/references/examples/` 三处的前提是
  **独特 API 模式**或**独特验证方法**；仅物理场景不同而 API 覆盖与既有案例重合者删除。
  方法: 对 19 个案例抽取 API token（create/set/导出表达式），计算 token 子集关系与唯一 token。
- **删除 4 例（三处同步删除）**:
    - `EcTCylinderTransient` (ET1) — 电热耦合瞬态的 API 覆盖是 `EcTSmCubeTransient` 的子集（仅几何/时序不同）
    - `EmwSlabFrequency` — token 与 `EmwSlabSweepFrequency` **互为子集**（同一几何/边界，仅单频 vs 扫频），保留扫频版
    - `SmCylinderAxialStationary` (M1) — 与 `SmPlateHoleStationary` 同为 SolidMechanics 应力/位移验证，
      且其 clean-zone 逐点对比方法在后者（Kirsch 应力集中，更强）中保留
    - `EcTSmCylinderStationary` (EcTSmCyl) — 三场耦合稳态与 `EcTSmCubeTransient` 的 API 覆盖重合；
      且受 comsolbatch `-Xmx2g` 限制 LU 分解稳定 OOM（machine-profile.md），本机无法回归
- **保留 15 例** (13 analytic + 2 physical): E1, T1, T2, ET2, EcTSmCube, EcTSmBusbar, TRevolve, TmSlab,
  EmwSlabSweep, SmPlateHole, TFinArray, SmCantEig, SmCantileverBendingStationary, EcHollowCyl, BaselineModel。
  每个保留案例都持有唯一 API/验证特征（如 Extrude+Fillet+Enu、Revolve、Array、Eigenfrequency、
  order_displacement、sorder+Mesh 导出、3D Difference+Kirsch、k(T) 非线性 …）。
- **REGISTRY 同步**: health_check.py REGISTRY 19 → 14 键（单一事实源），删除 4 个验证脚本；
  文档引用（skill case-naming.md / physics-api-recipes.md / verification-guidelines.md /
  api-validation-probes.md 与 lab case-naming.md）逐一改指保留案例；skill README 的案例计数 15 → 13。
- **runs/ 清理**: 删除 27 个目录（已删案例 + `_dev_*`/`_probe_*`/小写别名/恢复副本），1.1G → 445M；
  保留 14 个 REGISTRY 键目录 + aggregate-summary。
- **日志归档**: 台账 637 行按条目日期切分（2026-08 553 行 / 2026-09 65 行）为
  `logs/2026-08-lab-notebook.md` + `logs/2026-09-lab-notebook.md`（**年-月做文件名前缀，logs/ 下不建子目录**），
  全局设置/运行规则/月份索引移入 `logs/README.md`；`logs/2026-09-*-help.log` 为 -help 输出重新捕获归档；
  主题型文档（local-evidence-index / machine-profile / commands.lock / case-naming）不按月切分留在 lab 根。
  `.gitignore`: `logs/*` + `!logs/*.md`（只入库台账）。约定写入 AGENTS.md。
- **回归 (删减后)**: `python scripts/run.py sweep` **14/14 PASS**（runs/aggregate-summary.md）;
  删除案例的源码与验证脚本均已不在工作树，保留案例三处（src / verifications / skill examples）逐字节一致。

## 2026-09-17 工具链修复: 子进程输出解码丢失 (comsol 工具输出 GBK)

- **发现**: 精简后首次全回归的日志里出现 `UnicodeDecodeError: 'utf-8' codec can't decode byte 0xca`
  (subprocess reader 线程崩溃), 编译输出被**静默丢空** (`build/classes/*.compile.stderr.log` 为 0 字节)。
- **根因 (本机实测)**: COMSOL 自带 javac 在中文 Windows 上以 **GBK (cp936)** 输出中文提示
  (`注: 某些输入文件使用或覆盖了已过时的 API。`); 而本机 Python 处于 UTF-8 模式
  (`PYTHONUTF8=1` → `sys.flags.utf8_mode=1`, 故 `subprocess(text=True)` 按 UTF-8 解码)
  → reader 线程抛异常, `proc.stdout/stderr` 变成 None, 日志被写成空文件。
- **影响**: 编译/批处理/健康检查的中文诊断 (含中文报错) 会整段消失; `run_batch` 里
  `write_text(proc.stdout)` 在 None 时还会抛 TypeError (被 sweep 的逐键 try 吞掉, 表现为难解的错误标记)。
- **修复 (run.py, 4 处 subprocess.run)**: `text=True, encoding=locale.getencoding(), errors="replace"`,
  并在写日志处加 `or ""` 兜底。`locale.getencoding()` = 本机控制台编码 (本机 cp936 → 中文可读;
  UTF-8 机器上自动为 utf-8), 无需硬编码, 也不再丢输出。
- **验证**: 修复后 `run.py compile` 无 traceback, `EcSquareStationary.compile.stderr.log` 162 字节且中文可读;
  `run.py sweep --keys E1,T2,EcHollowCyl` 3/3 PASS; 随后全量 sweep **14/14 PASS**
  (日志无 traceback, `build/classes/sweep.compile.stderr.log` 133 字节中文正常)。

## 2026-09-19 非标量场的有限元离散类型控制 + 新增 demonstration tier

- 用户要求: 探索非标量场 (结构力学、频域电磁场等) 的有限元离散类型如何在 Java API 里控制。
- **方法**: 先挖官方 .mph 的序列化模型 (1839 个, 全部模块) 定位 `ShapeProperty` 的键与合法值,
  再用 4 个临时探针类 (ApiDiscProbe 1-4, 已删) 在真实模型上逐项验证。**未依赖任何记忆中的 API 名**。
- **入口与键名**: `physics("<tag>").prop("ShapeProperty")` → `PhysicsProp`;
  键 = `order_<场标识>`, 场标识 = `physics().field(tag).field()` (COMSOL 场名)。
  **非标量场的分量由物理接口声明**: solid `displacement: u -> [u,v,w]`; emw `electricfield: E -> [Ex,Ey,Ez]`;
  分量名不是键 (`order_u` 被拒)。**纠正旧记录**: 该入口无需反射 (`Physics.prop(String)` 与
  `PhysicsProp.set(String,String)` 都在公开 API), SmCantileverBendingStationary 的反射调用已简化为直调并回归通过。
- **合法离散码随接口族不同** (探针 `getAllowedPropertyValues` 实测, 括号为默认):
    - SolidMechanics `order_displacement` = 1,2,2s,3,3s,4,4s,5 (2s); Shell 只有 1,2 (2)
    - HeatTransfer/PressureAcoustics = 1,2,2s,3,3s,4,4s,5 (2); Electrostatics/ConductiveMedia = 1,2,3,4,5 (2, 无 's')
    - InductionCurrents `order_magneticvectorpotential` = 1,2,3; MagneticFieldsCurrentsOnly = 1,2,3,4
    - ElectromagneticWaves(FrequencyDomain) `order_electricfield` = 1,1t2,2,2t2,…,7,7t2 (2)
    - 键名不是 `order_*` 的接口: BeamEnvelopes 与 BEM 用 `shapeorder`
      (BEM = p11,p21,p22,p32,p33,p43,p44,p54,p55, 默认 p21)
    - LaminarFlow 只有 `order_fluid` = 1..5 (1), `order_velocity`/`order_pressure` 被拒 (速度压力同阶)
- **离散码语义 (dof 计数实测)**: `s` = serendipity — 单纯形上等于同阶 Lagrange
  (3D 四面体 2/2s 都是 717), 四边形上更少 (2D 四边形 p=2→50 vs 2s→42);
  `t2` = curl type 2 — **单纯形上也不同** (3D 四面体 emw 2→894 vs 2t2→1341; 2D 三角 2→115 vs 2t2→154)。
  求解器日志对 2 与 2t2 都打印 "Geometry shape function: Quadratic Lagrange" — 日志不能区分, 要看 dof。
- **数值对照**: EmwSlabSweepFrequency 同网格只改 `order_electricfield`:
  p=1 → max|ΔS11dB| = 0.0064, max|ΔS21dB| = 0.0012; p=2 与 p=2t2 对解析解 4 位小数一致
  (dof 61710 vs 92564) — 二次阶下两者在该网格上等价, 差异只在自由度数与单元族。
- **旁证**: `MagneticFields` / `MagneticFieldsNoCurrents` / `MagneticAndElectricFields` 不是合法 op
  (Unknown physics interface); 可用的是 `InductionCurrents` / `MagneticFieldsCurrentsOnly` /
  `ElectricInductionCurrents` / `ConductiveMedia`。SolidMechanics 的 `AddMixedFormPressure` 接受 "1" 但
  不新增压力场与 order 键 (该版本无 u/p 混合离散 API 面)。
- **新增 demonstration tier (用户决策)**: `comsol-java-skill-lab/src/demonstration/` 专放 **API 演示型案例** —
  只说明 API 用法, 无验证脚本、不进 REGISTRY/sweep; 命名 `<ApiTopic>Demonstration`;
  `run.py` 的 `SRC_TIERS` 加入该目录 (可编译可运行), 目录内 README.md 记录 tier 约定。
- **案例 FieldDiscretizationDemonstration**: 3D Block 上同时建 SolidMechanics / emw / HeatTransfer,
  打印各接口的场清单与 `order_*` 键的当前值+合法值, 再逐项 set+读回
  (solid 1→2s, emw 1→2t2, ht 3), 并演示 `component().sorder()` 与 `order_*` 是两个独立旋钮。
  实测 `run.py all` rc=0, 17.2 s, batch.log 无错误标记。
- **三处同步**: demonstration 案例同步到 `autocomsol/references/examples/demonstration/` (逐字节一致);
  证据写入 `local-evidence-index.md` §20; skill 侧 `physics-api-recipes.md` 补全离散契约与陷阱,
  `case-naming.md` 补 tier 与案例行, `SKILL.md` 路由加 demonstration 层。
- **回归**: `python scripts/run.py sweep` 全量 **14/14 PASS** (含改动后的 SmCantileverBendingStationary)。

## 2026-09-19 Java 格式化改为 clang-format (弃用 google-java-format)

- **动机**: google-java-format 不可配置, 把 COMSOL 的长 builder 链
  (`model.component(comp).physics("sm").feature("lemm1").set(...)`) 拆成每次调用一行、
  还把 Javadoc 的列表/换行重排 (如 `<li>` 的 `</li>` 被挪位、代码示例行被合并), 可读性反而变差。
- **方案 (本机实测)**:
    - 仓库根新增 `.clang-format`: 两段配置 —— `Language: Java` (`BasedOnStyle: Google` +
      `IndentWidth: 4` / `ContinuationIndentWidth: 8` / `ColumnLimit: 120` / `ReflowComments: false` /
      `AllowShortFunctionsOnASingleLine: Empty` / `AllowShortIfStatementsOnASingleLine: AllIfsAndElse` /
      `BinPackArguments: false` / `BinPackParameters: false` / `LineEnding: DeriveCRLF`)
      与 `Language: Cpp` (保留当前默认 LLVM)。
      **必须有 C++ 段**: clang-format 22 遇到不含 C++ 的配置会直接报
      "Configuration file(s) do(es) not support C++" 并 rc=1, 会让 C++ 文件格式化失败。
    - `LineEnding: DeriveCRLF`: 本机 git `core.autocrlf=true` 且 blob 存 CRLF, 工作树为 CRLF;
      默认 `DeriveLF` 会把整文件改成 LF (git diff 全文件重写)。实测输入 CRLF/LF 均输出 CRLF。
    - `AllowShortIfStatementsOnASingleLine: AllIfsAndElse`: 否则 clang-format 会把
      `if (x) continue;` / `else y.add(d);` 逐条拆成两行, 净增行数。
    - `clang-format.exe` = `E:\scoop_files\apps\llvm\current\bin\clang-format.exe` (22.1.8);
      VSCodium 侧 `[java] editor.defaultFormatter = xaver.clang-format` + `clang-format.style = file`
      (全局 settings.json 已改, 原 google-java-format 扩展保留未卸载)。
- **结果**: 16 个 Java 源文件统一重排 (净 -约 300 行, 主要为链式调用合并与 if 单行化);
  `src/` 与 `autocomsol/references/examples/` 逐字节一致, 行尾 CRLF。
- **回归**: 格式化后 `python scripts/run.py sweep` 全量 **14/14 PASS**。

## 2026-09-19 run.py 求解核数改为多核 (`-np`)

- 用户要求: 单案例求解太慢, 提高 COMSOL 求解的并发数 (不是并发跑多个案例)。
- **`-np auto` 不可用 (本机实测)**: comsolbatch 6.2 把它映射成非法 JVM 选项
  `-XX:ParallelGCThreads=auto` → stdout 只有该报错, **exit=127 且不生成 batch.log**
  (run.py 会把它记为 `csv missing` FAIL, 排查成本高)。必须传显式核数。
- **实现**: `run_batch(..., np=COMSOL_NP)`, `COMSOL_NP = os.environ.get("COMSOL_NP") or min(8, cpu_count())`;
  `run.py` 顶部与 `commands.lock.md` 记明约束。案例之间仍串行 (一个 batch 子进程), 不抢内存。
- **交错 A/B 实测** (同案例同二进制交替 np=1 / np=8):
    - `EcTSmCube` (最大案例): np=1 → 374.2 / 403.3 s; np=8 → 150.3 / 168.6 s (约 **2.4x**)。
    - `EcTSmBusbar` (小案例): np=1 → 37.7 / 31.0 / 31.5 s; np=8 → 40.6 / 38.9 / 40.9 s —
      小案例多核反而略慢, 故默认只设 8 核上限, 不追求"核越多越好"。
    - np=14 对 `EcTSmCube` 比 np=8 慢 (204.9 vs 175.7)。
- **正确性**: np=8 / np=14 各跑 4 案例 (EcTSmCube, EcTSmBusbar, SmPlateHole, TFinArray) 回归,
  健康检查 4/4 PASS, 解析解容差内与 np=1 一致; 数值不受核数影响。
- **文档**: `machine-profile.md` (CPU/核数实测)、`commands.lock.md` (`-np` 约束)、
  `local-evidence-index.md` §21、`AGENTS.md` 回归纪律各补一条。
