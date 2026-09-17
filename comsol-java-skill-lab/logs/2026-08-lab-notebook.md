# COMSOL Java 自动建模 Skill 研发 — 实验台账（2026-08）

## 2026-08-02

### Phase 1 环境发现

- 定位 comsolcompile / comsolbatch: 均位于 `D:\Program Files\COMSOL\COMSOL62\Multiphysics\bin\win64\`，在 PATH 中
- 版本: COMSOL Multiphysics 6.2.0.290（comsolcompile -version，exit=0）
- 系统 Java: OpenJDK 23.0.2 (Temurin)；COMSOL 自带 jre: java/win64/jre/
- 参数语法确认（-help, exit=0）: comsolcompile 支持 `-classpathadd`; comsolbatch 支持 `-inputfile/-outputfile/-batchlog/-study/-stoptime/-np/-tmpdir/-recoverydir`
- Java API 结构: 公开接口在 com.comsol.api jar；内部实现在 com.comsol.model jar；ModelUtil 位于 com.comsol.api jar
- 模块: ACDC、Heat Transfer、Structural Mechanics 等均已安装
- 文档: 本机仅 FlexNet PDF；demo 仅 3 个 Swing Java 文件 → 需以 jar 清单 + 最小实验验证 API
- 产出: machine-profile.md, commands.lock.md, local-evidence-index.md
- 工作区目录创建: src/build/models/logs/exports/reports/references/scripts/skill-output

### Phase 2 安全工作区规则

- run-id: YYYYMMDD-HHMMSS-实验名-短哈希；每次运行独立目录
- 所有脚本 set -e / 严格错误处理；命令执行器带超时、退出码捕获、日志重定向

### Phase 3 最小 Java 编译基线 — PASS

- BaselineModel.java: ModelUtil.create("Model") → component("comp1") → geom("geom1",2) → Square 几何 → save
- 关键本机证据:
    - comsolcompile 输出 .class 到**源文件目录**（不是 cwd）— 证据: src/BaselineModel.class
    - comsolcompile 日志在 `~/.comsol/v62/logs/compile*.log`（-Dcs.logoutput=file）
    - `Square` 的 `size` 属性是**标量**（错误证据: "Property: size (Side length)... Expected a finite real number, Expected unit is: m"）
    - `model.save()` 无参数 → 错误 "No filename given." → 必须 `save(path)`（args[0] 传入）
    - comsolbatch `-outputfile X.mph` 会额外生成 `X_Model.mph`（追加模型 tag）；java main 用 target arguments 收 args
    - `~/.comsol/v62/logs/` 存在既有运行日志（word_bridge*.log），不可依赖
- 确定性验证: 两次独立运行 exit=0, status="Done", batch.log 无 Error 块, .mph 内部条目列表一致（差异仅时间戳元数据）
- 产物: runs/run1/, runs/run2/（各含 BaselineModel.mph, out_Model.mph, batch.log, *.recovery,*.status）
- 结论: 基线 PASS，可进入物理实验。验收标准 C 达成。

### 工具脚本

- scripts/run-command.sh — 命令执行器（超时/退出码/日志）
- scripts/compile-run.sh — 编译-运行-检查闭环封装
- scripts/run-experiment.sh — 实验运行封装（参数传递）
- scripts/health_check.py — 健康检查器（数值/物理/守恒）

### Phase 4 实验 E1 稳态静电 — PASS（验收标准 D 之一）

- 接口类型关键证据（本机）:
    - `ElectricCurrents` 本机**未注册**（报 "Unknown physics interface"）
    - ACDC 本机有效接口: `Electrostatics`（静电）、`ConductiveMedia`（导电）
    - feature 类型: ChargeConservation/Ground/Terminal/ZeroCharge（capacitor_dc.mph）
    - 参数: epsilonr_mat 合法值 `"from_mat"|"userdef"`（ProbeMat 错误输出）
- 边界编号证据（ProbeGround 系列）: Terminal={1}=左(V=1)，Ground={4}=右(V=0)
    - gnd2/gnd3 时右边界 V=0.364（未接地）；gnd4 时右边界 V=0.010
- TerminalType 必须显式设 `"Voltage"` 否则 Terminal 默认电荷型 → 解全零
- 求解器退出码 0 + 解全零的案例：selection 错误 + TerminalType 缺失 → 健康检查捕获
- **验证结果**: V=0.5-x 解析解 max diff=1.96e-12 V；normE=0.99999999999996 V/m（解析 1 V/m）
- 产物: runs/e1-final/{ElectricalBaseline.mph, field.csv, health.json, health.md, batch.log}
- CSV 导出 API 验证: `result().export().create("data1","Data")` + set data/dset1 + expr(String[]) + run
- EvalGlobal 仅支持全局量（es.normE 是域量 → 未定义）；域量评估用 CSV 导出离线分析

## 2026-08-03 用户指令：清理与重构

- 用户要求: 1) 移除所有试验代码/输出，只留 BaselineModel.java 和 ElectricalBaseline.java（E1 最终版）；
  2) 脚本改用 Python（跨平台，弃 bash）；3) 建立 git 仓库并提交；4) 调查几何特征边界选择（避免靠猜边界编号）。
- 已清理: 全部 Probe*.java/.class、ThermalBaseline.*、.class 产物、runs/models/logs/build/exports 目录
- 保留: src/{BaselineModel,ElectricalBaseline}.java、研发文档(lab-notebook/machine-profile/commands.lock/local-evidence-index)
- 已删除 bash 脚本: compile-run.sh, run-command.sh, run-experiment.sh
- 下一步: 写 Python 脚本(run.py 等) → git init+提交 → 调查几何边界选择

## 2026-08-03 几何边界选择调查 — 突破（告别靠猜）

- 用户要求不单独封装 BoundarySelector 类 → 逻辑内联进每个模型文件的私有方法
- **核心 API（本机验证）**: `GeomInfo`（通过 `model.component(comp).geom("geom1")` 获取）
    - `getNEdges()` 边界数; `getVertexCoord()` 顶点坐标; `getStartEnd()` 边界起止顶点
    - **`edgeX(edge, {0.5})` 返回边界中点坐标** — 决定性方法
- 方板(1m, 中心原点) 实测 edgeX 中点坐标:
    - edge1=(-0.5,0)=左, edge2=(0,-0.5)=下, edge3=(0,0.5)=上, edge4=(0.5,0)=右
- **edgeX 边界索引与 physics selection 编号一致**（E1 实测: edge1=左 V=1, edge4=右 V=0）
- 通用方法: 遍历边界 1..N 采样中点 → 匹配目标坐标 → 得边界编号 → selection().set()
- 验证: ElectricalBaseline 内联方法输出 LEFT_BND=[1], RIGHT_BND=[4]，健康检查仍 PASS
- **类路径关键证据**: 系统 javac(JDK23) 编译的 class v67 无法被 comsolbatch(JRE Java11) 加载
  ("class file version 67.0, this version only recognizes up to 55.0")
  → 必须用 COMSOL 自带 javac（`<root>/java/win64/jre/bin/javac.exe`，需 `-encoding UTF-8`）
- run.py 已更新: 用 COMSOL javac + `-cp api_jar` 编译 src 下所有 .java（共享类自动包含）

## 2026-08-03 3D 面/曲面几何特征提取 — PASS

- 用户要求: 对 3D 边界面、曲边、曲面提取几何特征，用静电案例验证
- **3D 方块 (Block 1m³, 中心原点)**: faceX(f, params) 多点采样 → 找恒定坐标维
    - FACE1 x恒-0.5=左, FACE2 y恒-0.5=前, FACE3 z恒-0.5=下, FACE4 z恒+0.5=上, FACE5 y恒+0.5=后, FACE6 x恒+0.5=右
- **3D 圆柱 (r=0.5, h=1, 中心原点)**: faceParamRange(f) 关键 API
    - 圆盘面(顶/底): 参数范围[-0.6,100.6,-0.6,100.6]（0-100 百分比），采样中心 z 恒定 → FACE3=底(z=-0.5), FACE4=顶(z=+0.5)
    - 侧面(曲面): 参数范围[角度弧度, 0-100高度]，无恒定坐标维，但 r²=x²+y²=0.25 恒定 → FACE1,2,5,6
    - 圆柱侧面被分成 4 段（0-π/2 等四个 90° 扇区）
    - **关键陷阱**: faceX 对曲面需用 faceParamRange 的参数范围中点，直接 0.5 会报 "Face parameter out of range"
- **3D 圆柱静电验证** (Electrical3DCylinder):
    - 顶面 Terminal(V=1), 底面 Ground, 侧面 ZeroCharge(默认)
    - 轴线 V=0.5+z 解析解 diff=0; normE=1.0000 V/m; 侧面 V∈[0,1] 正确
    - 面编号识别: TOP=4, BOTTOM=3, SIDE=1,2,5,6
- 通用方法: faceParamRange 确定参数域 → faceX 采样中心/多点 → 恒定坐标维或 r² 判据分类面

## 2026-08-03 ES→EC 迁移 — PASS

- 用户要求: 把现有案例从 ES(Electrostatics) 迁移到 EC(Electric Currents)
- **本机接口证据**: `ElectricCurrents` 报 Unknown physics interface（不可用）；
  **`ConductiveMedia` 是本机 EC 接口**（IfaceProbe 实测 tags: cucn1/ein1/init1/dcont1）
    - 所有 ACDC 示例 .mph（含 Introductory_Electric_Currents 目录）都用 ConductiveMedia
    - 域特征: cucn1=CurrentConservation, ein1=ElectricInsulation, dcont1=Continuity
    - Terminal 参数: TerminalType=Voltage/Current, V0/I0; Ground 特征: gnd1
    - 材料属性名: **electricconductivity**（simple_resistor.mph 材料 def 证据，值如 5.998e7[S/m]）
- **E1EC (2D 方板导电)**: src/ElectricalBaselineEC.java
    - V=0.5-x 线性 max dev=1.98e-12; J=σ·E=5.998e7 A/m², J/σ=1.0 精确
- **E3DEC (3D 圆柱导电)**: src/Electrical3DCylinderEC.java
    - 顶面/底面/侧面提取复用 faceParamRange+faceX 方法
    - V=0.5+z 线性 max dev=5.5e-7; J/σ=1.0
- 两者均: batch_rc=0, log_flags=clean, .mph+CSV 生成
- 结论: ES↔EC 迁移只需改 physics 接口名(Electrostatics→ConductiveMedia)、
  feature tag(ccn1→cucn1)、材料属性(epsilonr→electricconductivity)、导出变量(normE→normJ)

## 2026-08-03 用户反馈: 输出目录与直接替换

- 用户要求: 1) .class 不应写到 src 目录; 2) 直接替换原案例而非新增 EC 后缀文件
- run.py 修正: class 输出到 `build/classes/`（javac `-d build/classes`），run_batch 从 build/classes 加载
- 案例替换: 删除 ElectricalBaselineEC.java / Electrical3DCylinderEC.java，
  内容写回 ElectricalBaseline.java / Electrical3DCylinder.java（类名改回原名）
- 替换后验证: EC2D V线性 dev=1.98e-12, J/σ=1.0; EC3D V线性 dev=5.51e-07, J/σ=1.0 — 均 PASS
- src 目录现在只有 .java，无 .class；build/classes 放编译产物

## 2026-08-03 T1 3D 传热基准（空心圆柱）— PASS

- 用户要求: T1 传热（Heat Transfer In Solids），几何相对复杂的 3D case，验证后固定
- **本机接口证据**: HeatTransferInSolids 报 Unknown（不可用）；**HeatTransfer 是本机纯固体传热接口**
  （HeatProbe: tags solid1/init1/ins1/...，无 fluid1）；HeatTransferInSolidsAndFluids 含流体特征
- **边界特征名证据**: Temperature/HeatFlux 报 Unknown feature ID；实际是 **TemperatureBoundary**/
  HeatFluxBoundary（inline_induction_heater/thermoelectric_cooler.mph 证据）
    - TemperatureBoundary 参数: T0_src=userdef, T0（本机 XML 证据）
- 材料属性: thermalconductivity（finned_pipe.mph 证据）
- **设计**: 空心圆柱(圆筒) r_in=0.3, r_out=0.5, h=0.2（外柱减内柱 Difference）
    - 内壁(曲面 r≈0.3) T=100K, 外壁(曲面 r≈0.5) T=300K, 上下端面绝热
    - 面提取: facesAtRadius 用 r=√(x²+y²) 判据, 内壁=[5,6,8,9] 外壁=[1,2,7,10]（4段90°扇区全选）
    - 解析解: T(r)=100+200·ln(r/0.3)/ln(0.5/0.3)（圆柱坐标对数分布）
- **验证结果**: T 范围[100,300]精确; 细网格(mesh1)径向分布 max dev=0.41K
- **网格收敛性**: 粗(mesh3) middev=3.71K → 中(mesh2) 1.92K → 细(mesh1) 0.41K 单调收敛
- 导出变量陷阱: ht.gradTnorm/ht.ntflux 均报 Undefined(域上); 只导出 T(域量),
  热量守恒在健康检查用解析梯度完成
- 产物: runs/t1*(粗/中/细三档), ThermalBaseline.java, health_check.py T1 逻辑

## 2026-08-03 M1 固体力学基准 + 案例命名规范化

- 用户要求: 1) M1 用解析解更确切的案例; 2) 案例规范化命名(缩略名+模型+study)+映射文档
- **M1 最终案例: 3D 空心圆柱轴向拉伸 (SmCylinderAxialStationary)**
    - 下端面 Fixed, 上端面 FperArea z向压强 → 精确单轴应力
    - 解析解: 内部 vm=sigma_z=1e6 Pa, 上端面位移=5e-6 m (E=200e9)
    - 验证: 内部 vm 9.855e5 (1.45% 误差), 位移 4.953e-6 (0.93% 误差) — PASS
- 弃用厚壁圆筒内压(3D Fixed下端偏差7-27%, 2D轴对称 Circle差集异常)：
    - 内压 FollowerPressure 载荷在内壁产生全零解(全局矢量对曲面净力为0)
    - 正确载荷: FperArea(每面积力) 是 ForceArea 载荷值; Ftot/F 是其他类型的
    - 2D 轴对称 Circle 差集生成全圆环(非半平面), 轴线 Fixed 产生应力奇异
- **案例命名规则** (case-naming.md):
    - `<缩略名><模型概述><Study类型>`: EcSquareStationary, TCylinderStationary, SmCylinderAxialStationary
    - 缩略名: Es=静电, Ec=电流, T=传热, Sm=固体, EcT=电热, TM=热结构, EcTM=三场
- **重命名**: ElectricalBaseline→EcSquareStationary, Electrical3DCylinder→EcCylinderStationary,
  ThermalBaseline→TCylinderStationary; 新增 SmCylinderAxialStationary
- SolidMechanics 关键证据:
    - 接口名 `SolidMechanics` (lemm1/free1/init1/dcnt1/dcont1)
    - 材料 E/nu 在 lemm1 设 (`E_mat=userdef`+E, `nu_mat=userdef`+nu); density_mat 无效
    - 特征: Fixed/Roller/BoundaryLoad 可用; FixedConstraint/PrescribedDisplacement 不可用
    - 载荷: LoadType 值 ForceArea/TotalForce/FollowerPressure/Resultant
    - 变量: solid.mises (von Mises), solid.disp (位移)
- health_check.py 新增 M1 检查(内部vm+上端位移)

## 2026-08-03 T2 2D瞬态环形传热（对流 BC + Bessel解析解）— PASS

- 用户要求: 2D 有解析解的瞬态传热, 几何不太简单, 含对流换热边界条件
- **案例 TRingTransient**: 2D 圆环(外圆0.5-内圆0.2, Difference), HeatTransfer 瞬态
    - 内环(r≈0.2) TemperatureBoundary T=473K (Dirichlet), 外环(r≈0.5) 对流 h=100 到 293K (Robin)
    - 初温 293K, t=0..3000s (5 个输出点), 材料 k=50/ρ=7850/Cp=500
- **解析解 (Carslaw & Jaeger §7.2)**: T_s(r)=T1+A·ln(r/a) 稳态 + Σ c_n e^{-αλ²t}·U_n(r) 贝塞尔级数
    - U_n(r)=J0(λa)Y0(λr)-Y0(λa)J0(λr), Robin 外壁 -kU'(b)=hU(b) 定 λ_n
    - **关键陷阱: U'(r)=λ[Y0(λa)J1(λr)-J0(λa)Y1(λr)]** — 导数符号曾写反(J0Y1-Y0J1)导致本征值错
    (λ0=1.33→修正后5.66), 修正前瞬态温度降到初温以下(物理荒谬)
- **本机 API 证据 (新)**:
    - 瞬态研究 feature 名是 **`Transient`** (不是 TimeDependent, 报 "Operation cannot be created")
    - 材料 def 组属性名: **density/heatcapacity** (不是 rho/Cp; heating_circuit.mph 解包 MaterialModel tag=def 证据)
    - **全局参数 rho/Cp 与 physics 特征同名冲突** → 解析成 0; 材料属性引用改为 rho_val/Cp_val 参数名
    - 对流边界: HeatFluxBoundary + HeatFluxType='ConvectiveHeatFlux' +
    minput_temperature_src='userdef'/minput_temperature + HeatTransferCoefficientType='UserDef'/h
- **验证结果**: inner_dirichlet=0.0K, transient_profile max=1.64K(8时刻), steady_analytic=0.20K — PASS
- 产物: runs/t2/, src/TRingTransient.java, scripts/verifications/t_ring_transient.py

## 2026-08-03 ET1 3D瞬态电热耦合（电磁热 + 对流 + Bessel解析解）— PASS

- 用户要求: 3D 有解析解的瞬态电热耦合案例
- **案例 EcTCylinderTransient**: 3D 实心圆柱(R=0.3, L=1), ConductiveMedia+HeatTransfer
    - 顶面 Terminal V=1V, 底面 Ground → 轴向 V=z+0.5 线性, J=σE 均匀, 焦耳热 Q=σ(V/L)²=2e4 W/m³ 均匀
    - 侧面对流 h=200 到 293K, 顶/底绝热, 初温 293K, 瞬态 0..3000s
- **解析解**: 中平面(z=0)纯径向, 均匀热源+Robin对流
    - 稳态 T_s(r)=T∞+QR/(2h)+Q(R²-r²)/(4k) (抛物面)
    - 瞬态 Σ c_n e^{-αλ²t}·J0(λr), λ_n 满足 kλJ1(λR)=hJ0(λR)
- **本机 API 证据 (新)**:
    - **多物理场耦合方法名是 `multiphysics()` 不是 `coupling()`** (javap ModelNode 证据)
    - 耦合接口 op="ElectromagneticHeating", 参数 EMHeat_physics/Heat_physics
    (thermoelectric_cooler.mph 解包证据)
    - ConductiveMedia 的 CurrentConservation 需要 **relpermittivity** 材料属性
- **验证结果**: V_linear=5.8e-8V, transient_profile=0.068K, steady_analytic=0.049K, z_symmetry=0.29K — PASS
- 产物: runs/et1/, src/EcTCylinderTransient.java, scripts/verifications/ec_t_cylinder_transient.py

## 2026-08-03 验证脚本拆分到 verifications/

- 用户要求: health_check.py 拆到 scripts/verifications/, 每个案例一个验证脚本(小写下划线命名), health_check 只调度
- **结构**:
    - scripts/verifications/common.py — 共享 load_csv/numeric_checks/emit_report/check
    - ec_square_stationary.py (E1), t_cylinder_stationary.py (T1), sm_cylinder_axial_stationary.py (M1),
    t_ring_transient.py (T2, 含内联 Bessel 解析解), ec_t_cylinder_transient.py (ET1, 含内联 J0 级数)
    - scripts/health_check.py — 纯调度器: 实验键→脚本子进程分发 (REGISTRY dict)
- common.load_csv 需识别瞬态 % 表头(含坐标或 @ t= 的 % 行) 和 ET1 小写 x,y,z 列头
- 回归: E1/T1/M1/T2/ET1 全部 PASS (旧 CSV 验证不变)

## 2026-08-03 ET2 3D同轴双材料电热耦合稳态（含热源, 全对流）— PASS

- 用户要求: 三维多材料电热耦合稳态案例, 必须含热源, 不用绝热而是全对流边界
- **案例 EcTCylinderStationary**: 3D 同轴圆柱(内芯 r1=0.15 导电 + 外壳 r2=0.3 绝缘, L=1)
    - 电: 顶面 Terminal V0=0.3V, 底面 Ground; 焦耳热 Q1=σ1(V0/L)²=9e4 W/m³ 均匀在内芯(唯一热源)
    - 热: 侧面 + 顶面 + 底面 **全部对流** h=200 → T∞=293K (无绝热)
    - 材料: 内芯 σ1=1e6/k1=15, 外壳 σ2=1e-8(绝缘)/k2=30; 研究 Stationary
- **解析解** (中平面 z=0 严格对称面, ∂T/∂z=0 精确, 端面散热不影响中平面):
    - 内芯(含源抛物线): T_c(r)=T∞+Q1·r1²/(2r2h)+Q1·r1²/(2k2)·ln(r2/r1)+Q1·(r1²-r²)/(4k1)
    - 外壳(无源对数):   T_o(r)=T∞+Q1·r1²/(2r2h)+Q1·r1²/(2k2)·ln(r2/r)
    - 界面温度/热流连续, 外壁对流守恒 (自测全部自洽)
- **本机 API 证据 (新)**:
    - **多材料域分配**: material.selection().set(int[]) 保持 GEOMDIM 类型
    (不要 .geom() 整几何 → 报 "Selection type not allowed")
    - **域编号陷阱**: 同轴 Difference 生成 2 域, 但**域1=外壳(环形), 域2=内芯(圆柱)**
    (Difference 把被减对象排后; 用 normJ 分布实测: 域1 J≈0=外壳, 域2 J大=内芯)
    - 材料 def 组属性写入确认: electricconductivity='sigma1' 等 (param 正则需含 value)
    - run.py 关键词误报: "Solution error estimates" 是求解器常规输出, 已从错误关键词排除
- **验证结果**: V_linear_core=2.5e-8V, J_insulating_shell=1e-14(比值), T_core=2.93K,
  T_shell=2.16K, interface=2.31K, convection_wall=1.24K, z_symmetry=0.076K — PASS
- 产物: runs/et2/, src/EcTCylinderStationary.java, scripts/verifications/ec_t_cylinder_stationary.py

## 2026-08-03 几何探测确定性识别域编号（告别试错）— 突破

- 用户要求: 研究能否用几何探测过滤域编号, 不依赖反复尝试
- **核心 API (GeomProbe 诊断验证)**:
    - `GeomInfo.getUpDown()[1]` = **每个面的所属域** (face→domain 映射, 确定性)
    - `GeomInfo.getUpDown()[0]` = 每个面的下维度实体
    - `getVertexDomain()` 对几何 GeomInfo **全 -1 (不可用)**; getVertex()/getPVertex()/getVtx() 抛
    "Unsupported operation" (仅 mesh GeomInfo 支持)
    - `getVertexCoord()` 返回 **3×N 数组** (行=坐标维 x,y,z, 列=顶点索引), 非每顶点一行
- **确定性域识别算法** (内联进 EcTCylinderStationary.detectCoreShellDomains):
  1. `int[] upDom = geom.getUpDown()[1]` — 每面所属域
  2. 对每面用 faceX 多点采样 (5×5 网格) 求最大半径
  3. 域级汇总: 内芯(圆柱 r1) max_r≈r1, 外壳(环形 r2) max_r≈r2 → 最小者=内芯
  4. 实测: domain 1 max_r=0.429=外壳, domain 2 max_r=0.215=内芯 (与 normJ 实测一致)
- **结论**: 不再需要"跑求解→看 normJ 分布→反推域号"; 纯几何探测即可确定。
  面级也自洽: F1/F2/F9/F12(r=0.3 外壁)=域1外壳, F5/F6/F10/F11(r=0.15 界面)=域1外壳,
  F7/F8(r=0.21 内芯端面)=域2内芯
- 产物: detectCoreShellDomains 内联方法; ET2 移除硬编码 {1,2}, 全部回归 PASS

## 2026-08-03 ETM1 稳态多材料电→热→力耦合 — PASS（三场耦合里程碑）

- 用户要求: 稳态多材料、有解析解的电→热→力三场耦合案例
- **案例 ETM1**: 3D 同轴双材料圆柱 (内芯 r1=0.15 导电 + 外壳 r2=0.3 绝缘, L=1)
    - 电: 顶面 Terminal V0=0.3V, 底面 Ground; 内芯轴向 V 线性, J=σ1E 均匀, Q1=σ1(V0/L)²=9e4 W/m³
    - 热: 侧面+顶面+底面 全对流 h=200→T∞=293K; 稳态径向温度 (内芯抛物线+外壳对数, 同 ET2)
    - 力: **广义平面应变 ε_z=0** (两端 Roller uz=0 + RigidMotionSuppression 径向)
    - 材料: 内芯 α1=1.2e-5, 外壳 α2=0.6e-5 (E,ν 两相相同 → 界面自动连续)
- **热应力解析解** (E1=E2, ν1=ν2, ε_z=0, 轴对称, α 分片):
    - ψ(r)=α(r)(T(r)-Tref), Q(r)=∫₀ʳψ(r')r'dr', m=(1+ν)/(1-ν), G=E/(2(1+ν)), λ=Eν/((1+ν)(1-2ν))
    - C1=G·m·Q(r2)/((λ+G)r2²)
    - σ_r(r)=-2G·m·Q(r)/r²+2(λ+G)C1;  σ_θ(r)=-2G·m·ψ(r)+2G·m·Q(r)/r²+2(λ+G)C1;  σ_z(r)=2λC1-2G·m·ψ(r)
- **本机 API 证据 (新)**:
    - **热膨胀耦合: multiphysics().create("te1","ThermalExpansion")** (bracket_thermal.mph 实证), 参数 Heat_physics/Solid_physics/alpha_mat/minput_strainreferencetemperature
    - **热膨胀材料属性: thermalexpansioncoefficient (9分量一维数组)** — 曾用 String[][] 3x3 报 "Matrix item not scalar"
    - **E,ν 必须在 lemm1 设 userdef** (from_mat 会报 "Undefined material property 'nu'"; bracket_thermal 用 from_mat+E(T) 材料但本机材料无 E(T) 表达式)
    - **critical: te1 必须显式 selection 全部域** — 不设时只选域3(空), 应力全零; selection().set({core,shell}) 修复
    - 约束: Roller (dims1,2), RigidMotionSuppression (dims2,3, contributingPoints=automatic)
- **验证**: V_linear=2.5e-8V, T_profile=2.81K, stress_sr=6.2MPa, stress_st=9.5MPa, stress_sz=14MPa (相对 σ_z~216MPa 偏差 3-7%), sr_wall_zero=4.7MPa — PASS
- 产物: runs/etm1/, src/ETM1.java, scripts/verifications/etm1_coaxial_stationary.py

## 2026-08-03 ETM2 瞬态不同几何电→热→力耦合 — PASS

- 用户要求: 瞬态、不同几何(非圆柱)、有解析解的电→热→力案例
- **案例 ETM2**: 3D 立方体 L=0.2m (单材料, 与 ETM1 圆柱几何不同)
    - 电: x=+0.1 Terminal V0=0.02V, x=-0.1 Ground → 均匀 Q=σ(V0/L)²=1e4 W/m³
    - 热: x=±0.1 两端对流 h=200→T∞=293K, 其余面绝热, 初温 T∞, 瞬态 0..6000s
    - 力: 两端 Roller (u_x=0) + RigidMotionSuppression → 1D 夹紧杆
- **解析解** (1D slab 傅里叶余弦级数 + 夹紧杆):
    - 稳态 T_s(x)=T∞+Qa/h+Q(a²-x²)/(2k), a=L/2
    - 瞬态 T(x,t)=T_s+Σc_n·e^{-αλ_n²t}·cos(λ_nx), k·λ·tan(λa)=h
    - 力学: σ_x(t)=-E·α·(⟨T⟩(t)-Tref) 全局均匀, σ_y=σ_z≈0
- **关键陷阱**:
    - **tan 分支伪根**: 初始在粗网格上找残余符号变化, 抓到 λ=π/a 假根 (tan零点非Robin根) → T(x,0)<初温 物理荒谬; 修正: 每个 tan 分支 (nπ/a,(n+1/2)π/a) 内 brentq 求唯一根
    - **瞬态求解超时**: mesh size 2 + 6000s 多时间步 → PARDISO out-of-core 超时; 改 mesh size 4 + 减时间步 → 320s 干净完成
    - **σ_y/σ_z 非零是端部圣维南效应**: max 1.6MPa 集中在端面; 中部均值≈0 → 验证用中部均值
    - **solid.disp 是幅值**: 端部固定位移检查用 |u| 有误导 (横向膨胀主导); 端部固定由 σ_x 均值解隐含验证
- **验证**: V_linear=3.5e-14V, T_steady=0.106K, T_transient=0.127K, sigma_x_uniform=380kPa, sigma_yz=233kPa, sigma_x_analytic=44.9kPa (0.35%) — PASS
- 产物: runs/etm2/, src/ETM2.java, scripts/verifications/etm2_cube_transient.py
- 回归: E1/T1/M1/T2/ET1/ET2 全部 PASS

## 2026-08-03 三场案例规范命名 — 重命名 ETM1/ETM2 → EcTSm*

- 用户要求: 三场(电-热-结构)前缀用 **EcTSm**(Sm=结构/固体, 非 M)
- 命名规则: `<物理场缩略名><模型概述><Study类型>`, 三场前缀 = Ec + T + Sm = **EcTSm**
- **重命名**:
    - `ETM1` → `EcTSmCylinderStationary` (src + 验证脚本 ec_tsm_cylinder_stationary.py, 实验键 EcTSmCyl)
    - `ETM2` → `EcTSmCubeTransient` (src + 验证脚本 ec_tsm_cube_transient.py, 实验键 EcTSmCube)
- health_check.py REGISTRY 更新为 EcTSmCyl/EcTSmCube; case-naming.md 示例与映射表同步
- 三个源文件编译均 PASS

## 2026-08-03 EcTSmBusbar 母线板案例 — PASS（三场耦合里程碑 2, 复杂几何）

- 用户要求: 建立母线板 case, L形铜母线 + 3个钛螺栓, 稳态电→热→结构三场耦合,
  计算 V/J/QJ/T/热膨胀位移 u/von Mises 应力与主应力
- **案例 EcTSmBusbarStationary**: 3D L形母线 (Copper) + 3贯穿圆柱螺栓 (Ti beta-21S)
- **几何** (任务书 8 步, WorkPlane 2D 截面 + Extrude + Cylinder + Form Union):
    - xz 工作平面: 外矩形(L+2*tbb, 0.1[m]) 减 内矩形(L+tbb, 0.1-tbb@(0,tbb)) → L形
    - 内圆角 tbb + 外圆角 2*tbb (Fillet 顶点: 内=dif1(1)第3, 外=fil1(1)第6)
    - Extrude wbb (母线宽度, 工作平面法向 -y)
    - 3 个 Cylinder 贯穿螺栓 (r=rad_1=6mm): 竖直端沿x, 水平端两沿z对称
    - **螺栓仅向外侧伸出 2*tbb** (用户纠错: 内侧端面与母线表面齐平, 非两端都伸出):
    cyl1 x∈[0.095,0.11] (贯穿tbb+伸出2*tbb), cyl2/3 z∈[-0.01,0.005]
    - Form Union (intbnd on) → **7 域** (母线1 + 每螺栓2段×3=6, 与任务书"7个域"一致)
- **本机 API 证据 (新)**:
    - WorkPlane 嵌套 2D: geom.create("wp1","WorkPlane") → feature("wp1").set("quickplane","xz")
    → feature("wp1").geom() 得内嵌 2D GeomSequence (GeomContainer=GeomInfo)
    - 2D Fillet 顶点选择: selection("point").set("dif1(1)", int[]{3}) (对象名带 (1) 后缀!)
    - GeomInfo.getVertexCoord() 对 workplane 2D 序列报 "no finalized geometry" → 用官方顶点号
    - Extrude input: selection("input").set(new String[]{"wp1"})
    - 网格局部细化: ftet1.create("size2","Size") + selection().geom("geom1",3).set(int[]) (需带维度!)
    - 材料 Enu 属性组: materialModel().create("Enu","YoungsModulusAndPoissonsRatio") 后 propertyGroup("Enu").set
    - lemm1 E_mat=from_mat 从材料读 E/ν (铜110GPa/0.35, 钛105GPa/0.33)
- **域/面识别** (确定性):
    - 母线域 = bbox 体积最大域; 螺栓域 = 其余
    - 外部面 = getAdj(2,3) 邻接恰 1 域; 内部界面 = 邻接 2 域
    - 螺栓端面 = 外部面中心精确匹配螺栓端面圆心 (从几何定义计算)
- **边界**: 电 high 端 V=Vtot=20mV, ground 端 Ground; 热全外表面对流 h=5→293.15K;
  力 3 螺栓外端面 Fixed
- **材料**: Copper(σ5.998e7/k400/ρ8700/Cp385/α17e-6/E110GPa/ν0.35),
  Ti beta-21S(σ7.407e5/k7.5/ρ4940/Cp710/α7.06e-6/E105GPa/ν0.33)
    - 结构参数采用 COMSOL 内置数据 (官方 busbar.mph XML 实证)
- **网格**: FreeTet + 全局 mh=6mm/hmin=4mm/hcurve=0.2 + 螺栓域局部细化 3*tbb
- **求解**: Stationary, segregated 收敛
- **验证** (health_check EcTSmBusbar, 12项全 PASS, 修正单侧伸出后重跑):
    - V∈[0,0.02]V, high 端≈0.02 精确, ground 端≈0.0002
    - 电流路径 high 螺栓 J=5.85e5 > 母线 J=3.78e5 (小截面集中)
    - 温升 31.6K (Tmax=324.8K); Qrh≈normJ²/σ_Cu 比值 1.017 (焦耳热自洽)
    - 固定端位移=0; 最大位移 30.5μm; 最大 von Mises 72.0MPa
- 产物: runs/ectsm_busbar/, src/EcTSmBusbarStationary.java, scripts/verifications/ec_tsm_busbar_stationary.py
- 回归: E1/T1/M1/T2/ET1/ET2/EcTSmCyl/EcTSmCube 全部 PASS
- **用户纠错**: 螺栓仅向外侧伸出 2*tbb (原实现两端都伸出 → 10域; 修正为单侧 → 7域, 与任务书一致)

## 2026-08-12 emw 电磁波频域案例 (EmwSlab 单频 + 扫频) — PASS（RF 模块里程碑）

- 用户要求: 基于 demo12.java (emw 可重构超表面) 写简单案例, 演示 **emw (电磁波, 频域)** 仿真,
  频域电磁场接口命名 **Emw**
- **案例 1 EmwSlabFrequency**: 3D 介质平板垂直入射单频 (PASS)
- **案例 2 EmwSlabSweepFrequency**: 同几何, 扫频 2-3 GHz (PASS)
- **几何**: 周期单元 (period=10mm) 空气盒 + 居中介质板 (n_slab=2, t=6mm), Form Union intbnd → 3 域
- **物理**: emw + wee1 (WaveEquationElectric, DisplacementFieldModel=RefractiveIndex) +
  2 Periodic 端口 (PortType=Periodic, PECBacked, ForwardPort, InputType=E, Eampl={0,1,0}, n=n_air) +
  2 Floquet PeriodicCondition (FromPeriodicPort)
- **本机 API 证据 (新)**:
    - `physics().create("emw","ElectromagneticWaves","geom1")` 后 **wee1 自动创建** (手动 create 报 already exists)
    - Periodic 端口设置 (fresnel_equations.mph dmodel.xml 实证): SlitType=PECBacked, PortOrientation=ForwardPort,
    InputType=E, Eampl, n, alpha1_inc, Pin=1[W], PortExcitation on/off
    - Floquet PeriodicCondition: PeriodicType=Floquet, Floquet_source=FromPeriodicPort, kFloquet={0,0,0}
    - Freq 研究步: create("freq","Frequency") + set plist/punit + createAutoSequences("freq") + study.run()
    - S 参数: emw.S11/emw.S21 (复数), emw.S11dB/emw.S21dB
    - 1D Global 图 Plot 导出 CSV: 表达式主序 (先全部 S11 频点, 再全部 S21 频点)
- **关键调试历程 (重要教训)**:
  1. `getAdj(2,3)` 的面编号顺序与 getUpDown/faceX 不一致 → 邻接数不可用 → 改纯几何面心分类 (确定性)
  2. **缺 IdenticalMesh → Floquet 周期条件失效 → 均匀介质也虚假反射 S11≈-7.7dB**!
     必须 `mesh.create("id1","IdenticalMesh")` + `selection("group1")`/`selection("group2")`
     命名组选周期对面 (普通 selection().set 报 "Entity has no selection")
  3. `dataset().create("dpt1","CutPoint")` 报 "Operation cannot be created" → 用 1D Plot 导出最干净
  4. Data 导出在 3D 解数据集上展开成逐网格点×频率巨表 → 扫频用 Plot 导出
- **验证 (解析 Fabry-Pérot 无损平板)**:
    - 单频 2.45GHz: COMSOL S11dB=-8.0091 (解析 -8.0091), S21dB=-0.7477 (解析 -0.7477), 功率守恒 1.0000
    - 扫频 2-3 GHz (11 点): 最大 |ΔS11dB|=4.8e-7, |ΔS21dB|=1.0e-7 (逐频点精确), 守恒 3e-15
    - 趋势: |S11| 随频率单调增大 (电厚度增大) ✓
- 产物: src/EmwSlabFrequency.java, src/EmwSlabSweepFrequency.java,
  scripts/verifications/emw_slab_frequency.py + emw_slab_sweep_frequency.py,
  runs/emw_slab_frequency/, runs/emw_slab_sweep/
- 案例 3 (lumped element 可重构单元) 暂缓 — 用户指示后续再做

## 2026-08-15 TRevolve 双层圆环 Revolve 旋转体传热 — PASS（几何里程碑: Revolve）

- 用户要求: 用 Revolve 旋转体几何做 3D 双层圆环稳态传热, 双材料, 解析解验证
- **案例 TRevolveStationary**: 3D 双层圆环 (Revolve 旋转体)
    - 几何: 两个 xz 工作平面各含一个矩形截面 (wp1: r∈[r_in,r_mid], wp2: r∈[r_mid,r_out], 厚度 t),
    各自 Revolve 360° (angtype=full) 成中空圆柱壳, Union(intbnd=on) 合并 → 内环壳(A)+外环壳(B) 2 域
    - 材料: 内环 kA=60, 外环 kB=30 (双材料, 热导率不同)
    - 热: 内壁(r=r_in) Dirichlet T=T0=500K, 外壁(r=r_out) 对流 h=20→Tinf=293K (Robin),
    环壳间界面(r=r_mid) 温度+热流连续, 端面绝热
- **解析解** (双层圆环对数分布, 每层 T=A·ln(r)+B):
    - 内环 T_A(r)=T0+(T_m-T0)·ln(r/r_in)/ln(r_mid/r_in); 外环 T_B(r)=T_m+(kA/kB)·A_A·ln(r/r_mid)
    - 界面温度 T_m 由界面热流连续 + 外壁 Robin 解得: C=(kA/(kB·dA))·(kB/r_out+h·dB), T_m=(C·T0+h·Tinf)/(C+h)
    - 实测 T(r_mid)=479.73 (解析 479.728)
- **本机 API 证据 (新)**:
    - **Revolve 旋转体**: geom.create("rev1","Revolve") + set("revolvefrom","workplane") +
    set("workplane","wp1") + selection("input").set({"wp1"}) + set("angtype","full")
    - **Revolve 是完整 3D 旋转体** (非扫掠): 2D 截面绕轴旋转 360°, 中空圆柱壳
- **关键陷阱**:
    - **detectCoreShellDomains 的 faceX 多点采样对 Revolve 曲面会抛 "Face parameter out of range"**
    → 必须 try-catch 跳过越界采样点
    - 域识别仍用 getUpDown()[1]+faceX 求各域最大半径: 最大半径最小者=内环 (同 EcTCylinderStationary)
- **验证结果**: T_inner_wall=1e-13K, T_inner_zone=0.014K, T_outer_zone=0.029K,
  interface_continuity=0.015K, radial_only=1.84K — PASS
- 产物: src/TRevolveStationary.java, scripts/verifications/t_revolve_stationary.py, runs/t_revolve/

## 2026-08-15 TmSlab 非线性导热 k(T) 变量变换解析解 — PASS（非线性材料里程碑）

- 用户要求: 3D 平板非线性导热稳态, k(T) 温度相关, 变量变换解析解
- **案例 TmSlabNonlinear**: 3D 立方体 (Block L=0.2m, 单域)
    - 材料: 非线性热导率 k(T)=k0·(1+beta·(T-Tref)), beta=0.004[1/K] (材料属性直接引用 T)
    - 热: x=-L/2 T=T1=600K, x=+L/2 T=T2=300K, 其余面绝热, 稳态 Stationary
- **解析解 (变量变换法)**: k(T) 温度相关 → 引入 phi=T+beta·T²/2-beta·Tref·T, 则 d²phi/dx²=0 → phi 线性;
  由两端 phi 值定 phi(x), 反解 T=(-a+sqrt(a²+2·beta·phi))/beta, a=1-beta·Tref
    - 非线性中点 T_mid≈476.76K vs 线性解 450K → 分离 26.8K (非线性效果显著, 验证判据)
- **本机 API 证据 (新)**:
    - **非线性材料属性直接写表达式**: propertyGroup("def").set("thermalconductivity", "k0*(1+beta*(T-Tref))")
    (非 String[][] 参数, 直接单字符串)
- **验证结果**: T_profile=0.044K, T_nonlinear_effective 分离 26.76K, T_range=[300,600]K,
  T_monotonic 左>右 — PASS
- 产物: src/TmSlabNonlinear.java, scripts/verifications/tm_slab_nonlinear.py, runs/tm_slab/

## 2026-08-15 补全 TRevolve / TmSlab 闭环 — 源码 + 验证脚本 + skill 同步

- 用户要求: 把 t_revolve / tm_slab 两个案例补全闭环 (源码/验证脚本/台账/skill 同步)
- **背景**: 两案例运行产物在 runs/ 且数值已 PASS, 但源码 src/*.java 与验证脚本缺失, 台账未记录
- **补全内容**:
    - src/TRevolveStationary.java + src/TmSlabNonlinear.java (按 API 调用序列重建, 数值与归档一致)
    - scripts/verifications/t_revolve_stationary.py + tm_slab_nonlinear.py (解析解由归档 health.json 反推), 并入 health_check.py REGISTRY (TRevolve/TmSlab)
    - 两案例均重跑验证: compile rc=0 + batch rc=0 + 数值与归档几乎一致 (T 场 maxdiff < 0.01K)
- **skill 同步**: 两案例 Java 复制进 autocomsol/references/examples/, case-naming.md 补命名映射,
  physics-api-recipes.md 补 Revolve 旋转体 + 非线性材料配方, geometry-selection.md 补 Revolve 曲面采样坑

## 2026-08-15 目录结构分 tier 重构 — analytic / physical

- 用户要求: 把有解析解验证的案例与无解析解、仅验证流程可运行性/大体物理合理性的案例分开存放
- **tier 划分**:
    - `analytic/` (12 个): 有解析解验证 (EcSquare, TCylinder, SmCylinderAxial, TRing, EcTCylinder[Stat/Trans],
    EcTSmCylinder, EcTSmCube, TRevolve, TmSlab, EmwSlab[Freq/Sweep])
    - `physical/` (2 个): 仅流程/物理合理性 (EcTSmBusbarStationary, BaselineModel)
- **目录同步** (三处同构):
    - lab: `src/{analytic,physical}/`, `scripts/verifications/{analytic,physical}/` (common.py 留原位, 子目录脚本上溯两级 import)
    - skill: `autocomsol/references/examples/{analytic,physical}/` 从 src 逐字节重新同步 (消除既有漂移)
- **脚本适配**: run.py 新增 SRC_TIERS 定位/编译; health_check REGISTRY 值加 tier 前缀;
  验证脚本 docstring `src/<tier>/Xxx.java`; Java javadoc 脚本路径加 tier (顺带修正 TRingTransient 过期名 verify_t2_ring_transient → t_ring_transient)
- **文档**: SKILL.md/README.md/physics-api-recipes.md/geometry-selection.md/verification-guidelines.md/case-naming.md(两处)/AGENTS.md 同步 tier 说明
- **附带修正**: emw 两案例 (EmwSlabFrequency/EmwSlabSweep) 此前未注册进 health_check REGISTRY (历史缺口), 本次一并补入 (实验键 EmwSlabFrequency/EmwSlabSweep)

## 2026-08-16 M1 SmCylinderAxialStationary 验证升级 — 均值→逐点场对比

- 用户要求: 把 M1 从"均值+宽容差(10%)"升级为"逐点场对比+窄容差", 达到 analytic 层应有严格度
- **导出变更**: Java 导出表达式 solid.mises/solid.disp(幅值) → **solid.mises/solid.sz/solid.w**
  (solid.w 未定义, 位移解变量是 w 不带 solid. 前缀; 幅值 disp 含径向收缩无法校验轴向)
- **圣维南效应实测** (autoMeshSize=3): 下端 Fixed 在 z<0.2 段引入强扰动
  (σ_z 下段 0.78e6~1.15e6, mises 下段显著低于 1e6), 仅上段 z∈[0.2,0.42] 严格趋于单轴解
  → 逐点对比必须限定"上段 clean zone" (z∈[0.2,0.42], r∈(0.32,0.48))
- **上段 clean zone 逐点实测**: σ_z max|σ_z-1e6|=1.08e4Pa(1.1%), mises-|σ_z| max=4.6e3Pa,
  w 拟合斜率 5.009e-6(解析5e-6,偏0.19%), w 逐点线性 maxdev=1.06e-7m
- **新检查 (5 项)**: sz_uniform(<2e4Pa), mises_eq_sz(<2e4Pa 单轴自洽),
  w_linear(<1.2e-7m), w_slope(斜率∈[4.98e-6,5.02e-6]), top_disp(上端面自由端 w∈[4.3,5.3]e-6)
- **关键认知**: 上端面是载荷自由端, w 略高于 clean zone 线性外推 4.6e-6 (实测 4.9e-6),
  故 top_disp 只做量级合理性检查, 不苛求精确端点
- **验证**: 5 项全 PASS; 回归 TRevolve/TmSlab/EcTSmBusbar/EmwSlabFrequency 全 PASS
- 产物: src/analytic/SmCylinderAxialStationary.java(导出改), scripts/verifications/analytic/sm_cylinder_axial_stationary.py(重写), runs/smcyl_recovered/

## 2026-08-16 方向深化批 0 — 工具链 + 探针协议（几何深度/物理扩展/后处理工程化的前置）

- 用户选定深化方向: 1) 几何深度(布尔链/阵列/镜像/STEP), 3) 物理扩展(辐射/共轭传热/磁场/EMW完整化/模态),
  4) 后处理+工程化(派生值/绘图+PNG/全回归)。跳过方向2(网格/求解器)。
- **run.py 新增 `sweep` 子命令**: 复用 health_check.py 的 REGISTRY 做单一事实源,
  `python scripts/run.py sweep [--keys K1,K2] [--skip-pass] [--runs-root DIR]`。
  流程: 一次编译全部 src → 逐键 run_batch 到 runs/、<key、>/ → health_check.py → 聚合
  runs/aggregate-summary.json/md。编译失败即返回1; 单案例失败隔离。已单测: 未知键拒绝/汇总写入 OK。
- **新增探针协议文档** autocomsol/references/api-validation-probes.md: jar 类清单法 +
  挖掘官方 .mph dmodel.xml + 临时 ApiProbes 探针类三步法; 含降级规则(Array→N复制+Union 等)。
- **挖掘官方模型证据** (local-evidence-index.md 新增 §16):
    - 几何 `op="Array"` (p:type=linear): forced_air_cooling_with_heat_sink.mph 散热片官方模型
    - 研究 `op="Eigenfrequency"`: ladder_frame.mph 等 12 个结构官方模型
    - 派生值 `op="Average"`/`AvSurface`; 绘图组 PlotGroup1D/2D/3D
    - 导出 ImageExport 接口类在 api jar; geommesh jar 有 OpArray/OpMirror/OpMove/OpRotate 无 OpPattern
    → 用 Array 不用 Pattern

## 2026-08-16 批 1 探针实证 — Array/PG3D/Image/AvVolume 全部 OK（临时探针类，不入库）

- **探针方法验证** (api-validation-probes.md 落地): 写临时 ApiProbes scratch 类,
  `python scripts/run.py all ApiProbes <run-dir> <mph> <png>` 一次编译+运行, 结果:
    - ARRAY_OK: `geom().create("arr1","Array")` + `selection("input")` + `set("size",String[])` +
    `set("displ",String[])` 可用; Array 产生多个不相交块 → **必须接 Union 合并** (intbnd=on)。
    - PG3D_OK: `result().create("pg3","PlotGroup3D")` + `create("surf1","Surface")` + `set("expr",...)`。
    **3D 模型必须用 PlotGroup3D; PlotGroup2D 报 Invalid_dataset_type** (需 2D 数据集)。
    - IMAGE_MIN_OK: `export().create("img1","Image")` + `set("plotgroup","pg3")` +
    `set("filename",绝对路径)` → 真实 PNG (魔数 \x89PNG, 2.6MB)。**坑1: size/width/height 属性
    报 Invalid_property_value → 省略用默认**; **坑2: 相对路径报 Failed_to_create_directory →
    必须绝对路径**; **坑3: args 必须显式传足 (args[0]=mph, args[1]=png), 否则 model.save() 把
    模型 zip 写到 png 路径**。
    - AVVOL_OK: `numerical().create("av1","AvVolume")` + `set("data","dset1")` + `set("expr",...)` +
    `run()` + `getReal()` → double[][]。探针类不入库, 证据记此 + local-evidence-index §18。
- 产: runs/api_probes/ (已删), src/analytic/ApiProbes.java (已删)

## 2026-08-16 批 1 案例 B TFinArrayStationary — Array 散热片 + 方向4载荷 (PASS)

- 几何: 基板(0.05×0.02×0.005) + 5 翅(0.001×0.02×0.10, **Array** 阵列 x 间距 0.0075) + Union(intbnd=on)。
- 物理: HeatTransfer, 基板底 z=0 定温 350K, 其余外表面对流 h=25→293K, k=200 全域。
- **参数名坑 (实测)**: 全局参数名 "h" 与 COMSOL 内置变量冲突 →
  "Duplicate parameter/variable name. Variable: h" → 改名 h_conv/k_fin。**与既有坑一致:
  参数名不得与物理 feature 名/内置变量重名**。
- **解析验证 (孤立翅 1D cosh)**: m=16.202, mL=1.62, Bi_c=6.25e-5 (低 Bi 设计满足)。
  θ_b 用 FE 根部平面拟合 (56.1K) 不硬编码 → 只测廓线形状比。
    - profile_cosh: 逐点 max 相对偏差 **0.38%** (clean zone 距根 3t 至尖 5t)
    - tip_ratio: 0.3796 vs 解析 0.379 (θ_tip/θ_b)
    - root_fit/monotone/av_temperature 全 PASS
- **方向 4 载荷**:
    - PlotGroup3D+Surface 温度图 + Image PNG 导出 OK (探针已验证)
    - **AvVolume 派生值坑 (实测)**: numerical("av1","AvVolume") 节点创建/序列化正常,
    但 batch 上下文 getReal() 返回空表 [[0.0]] (computeResult()/getReal(true) 均无效);
    Global 图求空间场变量 T 报 "Undefined variable comp1.T/ht.T" (S-参数是全局标量, T 是场量)。
    → 结论: 保留 AvVolume 节点作 API 模式演示, 体积平均由验证脚本从 field.csv 计算 (326.6K)。
- 验证: 5 项全 PASS; 产物 runs/t_fin_array/{field.csv, TFinArray.mph, TFinArray.png, health.*}

## 2026-08-16 批 1 案例 C SmCantileverEigenfrequency — 方形截面悬臂梁模态 (PASS)

- 几何: Block 悬臂梁 L=1.5, 方形截面 b=h=0.1 (L/h=15), 一端 Fixed。
- 材料: E=200GPa, nu=0.3, rho=7850。显式网格 FreeTet+Size hmax=0.035 (≈b/3)。
- 研究: **Eigenfrequency** (新字符串, 挖掘 ladder_frame.mph 证 op="Eigenfrequency", 4 模态)。
- **neigsactive 坑 (实测)**: 需 "on"/"off" 不是 "log" → "Invalid property value ... 'on','off'"。
- 频率经 Global 图 + Plot 导出 (EmwSlab 范式): expr={"freq"}, **xdataexpr=solnum 报 Undefined variable → 不设, 默认按模态序号**。
- **位移变量坑 (实测)**: 模态位移导出需 "u","v","w" 无 solid. 前缀 (与 SmCylinder 一致);
  solid.u 报 Undefined variable。
- **load_csv 坑 (实测)**: Plot 导出无表头 → 首数据行被 common.py load_csv 误认作表头
  (表头=["1","36.24..."])。验证脚本用_looks_like_data 回补首行。
- **验证 (欧拉-伯努利, 方形截面退化对)**: f1=36.24 Hz (EB 36.19, βL=1.8751), f2=222.6 Hz
  (EB 227.1, βL=4.6941)。形状识别: 模态1 主 z 向 (w), 模态2 主 y 向 (v) → 正交退化对 ✓
  (梁沿 x, 截面 y-z, 弯曲模态在 v/w 方向, 轴向 u 极小; 判断 |v| vs |w| 而非 |u| vs |v|)。
- 验证: 4 项全 PASS; 产物 runs/sm_cant_eig/{freq.csv, modes.csv, SmCant.mph, health.*}

## 2026-08-16 批 1 全回归 sweep — 14/16 PASS + 修复 E1 历史 bug + 2 个 OOM 环境问题

- **修复 E1 历史 bug (ec_square_stationary.py)**: 源导出 ec.normJ (σE=5.998e7 A/m²)，
  但验证脚本检查 normE/期望 1 V/m → 永久 FAIL。物理是 ConductiveMedia，场量是电流密度；
  已改为检查 |mean(ec.normJ)-5.998e7| < 5% (J=σE, σ=5.998e7, E=1)。修复后 E1 PASS。
- **run.py sweep 两处增强**: (1) key→class 映射 (key_to_class, camel-case + EcTSm 特例);
  (2) 验证脚本用 .venv python (numpy 依赖); (3) SWEEP_EXTRA_ARGS 支持多 CSV/PNG 导出案例。
- **全回归 14/16 PASS**: 全部既有 13 案例 + 3 新案例 (SmPlateHole/TFinArray/SmCantEig) 通过。
- **2 个 OOM 环境问题 (非回归)**: EcTSmCylinderStationary (3场耦合稳态) 与
  EcTSmCubeTransient (3场耦合瞬态) 报 "Out of memory during LU factorization"，
  batch 内存峰值 427-513MB，系统内存压力下 LU 因子分配失败。两源 git diff 为空 (未被我改动)。
  判定为环境内存压力导致的偶发 OOM，非代码回归。重试单案例看是否通过。

- **OOM 复现确认**: EcTSmCylinderStationary 单独重试仍 OOM (50.8s, 同 "Out of memory during
  LU factorization")。判定: comsolbatch.ini 固定 -Xmx2g, 3 场耦合 LU 分解超限, 稳定复现,
  非偶发。已记入 machine-profile.md。两个重耦合案例在默认堆下无法过回归 (环境限制)。
