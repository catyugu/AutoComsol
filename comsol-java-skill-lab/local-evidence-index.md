# local-evidence-index.md — 环境发现证据索引

本文件记录第一阶段发现的每个关键知识点的证据来源（本机路径或命令输出）。

## 1. 可执行文件定位

- 证据: `command -v comsolcompile` → `/d/Program Files/COMSOL/COMSOL62/Multiphysics/bin/win64/comsolcompile`
- 证据: `command -v comsolbatch` → `/d/Program Files/COMSOL/COMSOL62/Multiphysics/bin/win64/comsolbatch`
- 两者均在 PATH 中，exit=0

## 2. 版本

- 证据: `comsolcompile -version` → `COMSOL Multiphysics 6.2.0.290` (exit=0)
- 证据: `readme.txt` → `COMSOL 6.2.0.290 README`

## 3. 参数语法

- `comsolcompile -help` → logs/2026-09-comsolcompile-help.log (exit=0, 32 行)
- `comsolbatch -help` → logs/2026-09-comsolbatch-help.log (exit=0, 115 行)
- ini 文件: `bin/win64/comsolcompile.ini`, `bin/win64/comsolbatch.ini` — 显示 Eclipse Equinox 启动参数、JVM 堆 (Xmx2g)、自带 jre 路径、osgi workspace 策略

## 4. Java API 类路径

- 公开 API 接口 (com.comsol.model.Model 等): `plugins/com.comsol.api_1.0.0.jar`
- 内部实现: `plugins/com.comsol.model_1.0.0.jar` (6715 classes)
- ModelUtil: `com/comsol/model/util/ModelUtil.class` 位于 com.comsol.api jar (9135 字节)
- 模块实现: com.comsol.heat, com.comsol.solid, com.comsol.acdc, com.comsol.guiheat 等 jar

## 5. 文档与示例

- 本地 PDF 仅 FlexNet License 管理: `doc/pdf/COMSOL_Multiphysics/FlexNet/fnp_LicAdmin.pdf`
- Java 示例: `demo/api/beammodel/` 3 个文件（Swing 相关，非建模示例）
- 结论: 无本机建模 Java 示例/手册 → API 验证必须依赖 jar 清单 + 最小编译实验

## 6. 模块可用性（applications/ 目录）

- ACDC_Module, Heat_Transfer_Module, Structural_Mechanics_Module 确认存在
- plugins: com.comsol.acdc_1.0.0.jar, com.comsol.heat_1.0.0.jar, com.comsol.solid_1.0.0.jar 确认存在

## 7. 系统 Java

- OpenJDK 23.0.2 (Temurin)，JAVA_HOME=E:\env\java\.jdks\temurin-23.0.2
- COMSOL 自带 jre: COMSOL62/Multiphysics/java/win64/jre/

## 8. WorkPlane 嵌套 2D 几何 (EcTSmBusbarStationary 实证)

- WorkPlane 创建: `geom("geom1").create("wp1","WorkPlane")`; 平面: `feature("wp1").set("quickplane","xz")`
- 内嵌 2D 序列: `feature("wp1").geom()` 返回 GeomSequence (extends GeomContainer=GeomInfo)
- 2D 特征 (Rectangle/Difference/Fillet) 在 2D 序列上创建
- Fillet 顶点选择: `selection("point").set("dif1(1)", int[]{3})` — 对象名必须带 `(1)` 后缀
- GeomInfo.getVertexCoord() 对 workplane 2D 序列报 "This sequence has no finalized geometry"
- Extrude 从工作平面: `selection("input").set(new String[]{"wp1"})`, `set("distance","wbb")`
- 参考: 官方 busbar.mph (applications/COMSOL_Multiphysics/Multiphysics/) 解包 dmodel.xml

## 9. 材料 Enu 属性组 (MaterialEnuProbe 实证)

- `material.materialModel().create("Enu", "YoungsModulusAndPoissonsRatio")` 创建 E/ν 材料模型
- 然后 `material.propertyGroup("Enu").set("E", ...)` / `.set("nu", ...)`
- solid.lemm1 用 `E_mat=from_mat` 从材料读 (多材料不同 E/ν 时必须)
- 官方材料参数 (busbar.mph): Copper E=110GPa ν=0.35 α=17e-6; Ti beta-21S E=105GPa ν=0.33 α=7.06e-6

## 10. 网格局部细化 (EcTSmBusbarStationary 实证)

- `mesh("mesh1").create("ftet1","FreeTet")` 创建自由四面体序列
- 局部 Size: `ftet1.create("size2","Size")` + `size2.selection().geom("geom1",3).set(int[])` — geom 需带维度 3!
- 全局尺寸: Size 特征 set("custom","on")/hmax/hmin/hcurve/hgrad
- 错误教训: mesh1 顶层 create("Size") 报 "Operation cannot be created";
  selection().set(int[]) 报 "No entity dimension specified" → 必须 .geom("geom1",3)

## 11. 面邻接与域识别 (EcTSmBusbarStationary 实证)

- `GeomInfo.getAdj(2,3)` 返回每面邻接的域数组; 外部面=邻接1域, 内部界面=邻接2域
- `getUpDown()[1]` = face→domain 映射; `getVertexCoord()` = 3×N 顶点坐标数组
- 母线域识别: bbox 体积最大域; 螺栓端面: 面中心匹配螺栓端面圆心

## 12. emw 电磁波频域接口 (RF Module, EmwSlab 实证)

- 官方证据: `applications/RF_Module/Verification_Examples/fresnel_equations.mph` (解包 dmodel.xml) —
  物理场 op=`ElectromagneticWaves`, tag=emw; wee1 WaveEquationElectric; port1/2 Port; pc1/2 PeriodicCondition。
- 物理场创建: `physics().create("emw", "ElectromagneticWaves", "geom1")` — **wee1 (WaveEquationElectric)
  自动创建**, 直接 `.feature("wee1").set(...)`, 手动 create 会报 "already exists"。
- 材料: RefractiveIndex 模型 (`materialModel().create("RefractiveIndex","RefractiveIndex")`,
  `propertyGroup("RefractiveIndex").set("n", 9元素对角))`, wee1 DisplacementFieldModel=RefractiveIndex 从材料读 n。
- 端口 (Periodic Port, fresnel 标准): PortType=Periodic, SlitType=PECBacked, PortOrientation=ForwardPort,
  InputType=E, Eampl={0,1,0}, n=n_air 对角, alpha1_inc=alpha, PortName, Pin=1[W], PortExcitation on/off。
- PeriodicCondition: PeriodicType=Floquet, Floquet_source=FromPeriodicPort, kFloquet 默认 {0,0,0}。
- 研究: `create("freq","Frequency")` + `feature("freq").set("plist","range(2,0.1,3)")` + `.set("punit","GHz")`,
  `createAutoSequences("freq")` + `study.run()` (自动 Stationary+Parametric+Advanced complexfun+Direct)。
- S 参数全局变量: `emw.S11`/`emw.S21` (复数), `emw.S11dB`/`emw.S21dB` (20log10|S|)。
- 验证结果: n=2 t=6mm 平板 2.45GHz S11dB=-8.0091 (解析 -8.0091), 扫频 2-3GHz 最大偏差 5e-7 dB。
- 关键坑: 参考系 (单界面 vs 有限平板) 由端口 n 决定 — fresnel 模型 port2 n=n_slab (匹配介质半空间)
  得单界面 S 参数; 有限平板两端口都要 n=n_air 得 Fabry-Pérot。

## 13. IdenticalMesh 周期对 mesh (Floquet 必需)

- Floquet PeriodicCondition 要求周期对面 mesh 一致; **必须显式 IdenticalMesh**, 否则 S 参数完全错误
  (均匀介质仍得 S11≈-7.7dB 虚假反射)。
- API: `mesh("mesh1").create("id1","IdenticalMesh")` + 命名组选择:
  `id1.selection("group1").geom("geom1",2).set(一侧面)` + `id1.selection("group2").geom("geom1",2).set(对侧面)`。
- 普通 `selection().set(...)` 报 "Entity has no selection"; 必须用 `selection("groupN")` 命名组。

## 14. emw 结果导出 (S 参数 CSV)

- 1D PlotGroup+Global 图 (`result().create("pg1","PlotGroup1D")` + `feature("glob1")` 设 expr/xdataexpr)
  → `export().create("data1","Plot")` + `set("plotgroup","pg1")`。
- 导出格式: 列名行 "% Frequency (GHz),S11, S21", 数据行 "x,value" **按表达式主序**
  (先全部 S11 频点, 再全部 S21 频点); 单频→每表达式 1 行。
- 已知坑: `result().dataset().create("dpt1","CutPoint")` 报 "Operation cannot be created in this context";
  Data 导出在 3D 解数据集上会展开成逐网格点×频率的巨表 → 用 Plot 导出最干净。

## 15. emw 几何识别坑 (EmwSlab 实证)

- **`getAdj(2,3)` 的面编号顺序与 getUpDown/faceX 的枚举不一致** (本几何): 邻接数无法用于外部面判定。
- 改为纯几何法: 用 faceParamRange+faceX 采样面心, 按面心坐标分类
  (z=±H/2 端口, |x|=period/2 周期面, |y|=period/2 周期面) — 确定性且可靠。

## 16. 几何/研究/派生值/绘图 官方字符串 (2026-08-16 挖掘 applications/ 证据)

方法见 `autocomsol/references/api-validation-probes.md`。证据来自解包官方 .mph 的 dmodel.xml
与 plugins jar 类清单:

- 几何 op=`Array` (p:type="linear", p:size): `Heat_Transfer_Module/Applications/forced_air_cooling_with_heat_sink.mph`
  (官方散热片模型, 用 Array 排布 4/7 个翅片)。**用 Array 不用 Pattern** (geommesh jar 无 OpPattern, 有 OpArray/OpMirror/OpMove/OpRotate)。
- 研究 op=`Eigenfrequency` (StudyFeature tag="eig"; `s("eig") s("Eigenfrequency")`):
  `Structural_Mechanics_Module/Beams_and_Shells/ladder_frame.mph` 等 12 个结构官方模型。
- 派生值 op=`Average` / `AvSurface`: `Heat_Transfer_Module/Applications/concentric_tube_heat_exchanger.mph`,
  `forced_air_cooling_with_heat_sink.mph`。
- 绘图组 PlotGroup1D/2D/3D: 多个官方模型 (concentric_tube_heat_exchanger 全三型)。
- 导出 ImageExport 接口类: `com.comsol.api_1.0.0.jar`; op="Image" 见 AppBuilderFeature
  (concentric_tube_heat_exchanger.mph) — 导出类型字符串 (Java `export().create(tag,"Image")`)
  待探针实证。

## 17. run.py sweep 全回归 (2026-08-16 新增)

- `python scripts/run.py sweep [--keys K1,K2] [--skip-pass] [--runs-root DIR]`
- REGISTRY 单一事实源: run.py `from health_check import REGISTRY` 复用, 消除两处漂移。
- 流程: 一次编译全部 src → 逐键 run_batch 到 runs/、<key、>/ → health_check.py → 聚合
  aggregate-summary.json/md (runs/ 根)。--skip-pass 跳过上次已 PASS 的键。
- 编译失败即返回 1 (不静默); 单案例失败隔离不中断。

## 18. Array/PG3D/Image/AvVolume 探针实证 (2026-08-16, ApiProbes 临时探针)

- `geom().create("arr1","Array")` + `selection("input").set({"blk1"})` +
  `set("size",String[]{n1,n2,n3})` + `set("displ",String[]{dx,dy,dz})` — 可用。
- **Array 产生多个不相交块 → 必须接 Union (intbnd=on) 合并成域**, 否则 SolidMechanics 刚体奇异。
- `result().create("pg3","PlotGroup3D")` + `feature("surf1","Surface")` — 3D 模型用 PG3D;
  PlotGroup2D 需 2D 数据集, 3D 上报 Invalid_dataset_type。
- Image 导出: `export().create("img1","Image")` + `set("plotgroup","pg3")` +
  `set("filename",<绝对路径>)` → 真实 PNG。**size/width/height 属性报 Invalid_property_value →
  省略用默认**; **相对路径报 Failed_to_create_directory → 必须绝对路径**;
  **args 必须显式传足 (args[0]=mph,args[1]=png)**。
- 派生值: `numerical().create("av1","AvVolume")` + `set("data","dset1")` + `set("expr",...)` +
  `run()` + `getReal()` → double[][]。

## 19. 二阶几何网格导出 (sorder + Mesh 导出, 2026-09-17)

- API 字符串来源 (官方 .mph 的 action 历史挖掘, 方法见 api-validation-probes.md):
  `<actions> ... t(s("/component/comp1")) m(s("sorder")) s("quadratic")</actions>` —
  证据模型 7 个: `Acoustics_Module/Ultrasound/ultrasound_flow_meter_generic.mph` (quadratic)、
  `ACDC_Module/Tutorials,_Coils/resonant_spiral_coil_3d.mph` (linear) 等。
- 公开 API 签名 (javap com.comsol.api_1.0.0.jar): `com.comsol.model.ModelNode.sorder()` /
  `sorder(String)` — 挂在 **component** 节点上 (`model.component("comp1").sorder(...)`)。
- 取值: `automatic`(默认)/`linear`/`quadratic`/`cubic`/`quartic`; 数值字符串 `"2"` 被拒
  (FlException "Invalid geometry shape function")。
- 导出单元类型 (逐值探针, 同一圆柱几何 r=0.03):
  automatic/quadratic/cubic/quartic → `vtx/edg2/tri2/tet2`; linear → `vtx/edg/tri/tet`。
  求解器日志相应报 Quadratic/Cubic/Quartic/Linear Lagrange → **导出上限为二阶**。
- 平面几何 (Block 0.03³) + sorder("quadratic") → 仍 `vtx/edg/tri/tet` (无曲面实体 → 无曲单元)。
- Mesh 导出节点集 = 3D 解数据集的采样点 (空心圆柱案例 5979 点, 与 hellofem 案例的 result.txt 一致)。
- Mesh 导出无已求解数据集时: `run()` 不抛异常且**不写文件** (探针 nostudy_box exists=false)。
- .mphtxt 块结构: `<n> # number of mesh vertices` → `# Mesh vertex coordinates`;
  块头 `<npe> <name> # type name` → `# number of vertices per element` / `# number of elements` /
  `# Elements`; 二阶单元中点节点排在角点之后 (tri2 边序 (0,1),(1,2),(2,0))。
- 布尔切片: `Difference(cyl, cyl)` 后每个圆柱面是 4 片 (探针面清单: 1,2,7,10 = r_out; 5,6,8,9 = r_in;
  3,4 = 端面)。只选 1 片 → BC 只覆盖部分边界, 电位场偏差 0.5 V 且 COMSOL 无任何报错。

## 20. 非标量场的有限元离散类型 API (2026-09-19, ApiDiscProbe 1-4 临时探针)

- 入口: `physics("<tag>").prop("ShapeProperty")` 返回 `PhysicsProp`（`Physics.prop(String)` 在公开
  API 里，**无需反射**；`set(String,String)` 也是接口方法 — 早前 SmCantileverBendingStationary 里的
  反射调用已按此简化）。键名 = `order_<场标识>`；同节点还有 `boundaryFlux_<场>` / `boundaryFluxSmooth_<场>`
  / `valueType` / `frame` / `hiddenRowLabels`。自省: `prop.properties()` / `hasProperty(key)` / `getString(key)`
  / `getAllowedPropertyValues(key)`。
- **非标量场的分量由物理接口声明**: `physics(tag).field(tag2)` → `PhysicsField.field()`（COMSOL 场名，
  即 `order_` 后缀用的标识）、`.fieldname()`（分量名）、`.component()`（分量）。实测:
  SolidMechanics `displacement: u -> [u, v, w]`; emw `electricfield: E -> [Ex, Ey, Ez]`;
  HeatTransfer `temperature: T -> [T]`。分量名不是合法键（`order_u` 被拒）。
- **合法离散码随接口族不同**（探针 getAllowedPropertyValues 实测, 括号内为默认值）:
    - SolidMechanics `order_displacement` = 1,2,2s,3,3s,4,4s,5 (2s)；Shell `order_displacement` = 1,2 (2)
    - HeatTransfer `order_temperature` = 1,2,2s,3,3s,4,4s,5 (2)；PressureAcoustics `order_pressure` 同
    - Electrostatics / ConductiveMedia `order_electricpotential` = 1,2,3,4,5 (2, 无 's')
    - InductionCurrents `order_magneticvectorpotential` = 1,2,3；MagneticFieldsCurrentsOnly = 1,2,3,4；
      ElectricInductionCurrents = A:1,2,3 + V:1,2,3,4
    - ElectromagneticWaves / ...FrequencyDomain `order_electricfield` = 1,1t2,2,2t2,…,7,7t2 (2)
    - ElectromagneticWavesBeamEnvelopes 键名是 **`shapeorder`**（无 order_ 前缀）= 1,1t2,2,2t2,3,3t2 (2)
    - 边界元接口 (ElectrostaticsBoundaryElements) 键名 **`shapeorder`** = p11,p21,p22,p32,p33,p43,p44,p54,p55 (p21)
    - LaminarFlow 只有 `order_fluid` = 1,2,3,4,5 (1)；`order_velocity` / `order_pressure` 被拒（速度压力同阶）
    - 不连续场 (HeatTransfer 辐射等) 键名带 `_disc` 后缀，允许值含 0（如 `order_incidentradiation_disc` = 1..5）
- **离散码语义（dof 计数实证, batch.log "Number of degrees of freedom solved for"）**:
    - `s` = serendipity: **单纯形上等于同阶 Lagrange，四边形/六面体上更少**。2D 四边形 4 单元 plane stress:
      p=1→18, p=2→50, **2s→42**, p=3→98；三角 14 单元: 2→74, 2s→74；3D 四面体 106 单元: 2→717, 2s→717。
    - `t2` = curl type 2（H(curl) 场）: **单纯形上也不同**。2D 三角 14 单元 emw: 1→37, 2→115, **2t2→154**；
      3D 四面体 106 单元: 1→193, 2→894, **2t2→1341**, 3→2421。求解器日志对 2 与 2t2 **都**只打印
      "Geometry shape function: Quadratic Lagrange"，日志无法区分两者，须看 dof 数。
    - 数值对照 (EmwSlabSweepFrequency 同网格只改阶次): p=1 max|ΔS11dB|=0.0064 / max|ΔS21dB|=0.0012；
      p=2 与 p=2t2 都 ≈0（对解析解 4 位小数一致），dof 61710 (2) vs 92564 (2t2)。
- **ACDC 磁接口 op 字符串实测**: `InductionCurrents` / `MagneticFieldsCurrentsOnly` /
  `ElectricInductionCurrents` / `ConductiveMedia` 可用；`MagneticFields`、`MagneticFieldsNoCurrents`、
  `MagneticAndElectricFields` 报 "Unknown physics interface"。官方 .mph 里出现过的 `MagnetostaticsNoCurrents`
  未做探针（仅挖掘证据）。
- **SolidMechanics 混合格式**: `prop("AddMixedFormPressure").set("AddMixedFormPressure","1")` 被接受，
  但**不新增压力场、不新增 order 键**（field 列表不变, `hasProperty("order_pressure")=false`）——
  该版本无 u/p 混合离散的 API 面。
- **挖掘离散键的通用方法**（官方 .mph 全库 1839 个）:
  `re.findall(r'param="(order_[A-Za-z_0-9]+)" value="1\|1,\'([^\']*)\'"', dmodel)`；
  跨模块的 `shapeorder` 键（BEM/beam envelopes 等）用
  `re.findall(r'param="shapeorder[a-zA-Z_0-9]*" value="[^"]*"', dmodel)` 定位物理接口 op。

## 21. comsolbatch 求解核数 `-np` (2026-09-19 实测)

- **`-np auto` 不可用**: comsolbatch 6.2 把它映射成非法 JVM 选项
  `-XX:ParallelGCThreads=auto` → stdout 只有该报错, **exit=127, 不生成 batch.log**。
  必须传显式核数 (`-np 8` 生效, batch.log 报 `Using 1 socket with 8 cores in total`)。
- **交错 A/B 实测 (本机 14 物理核 / 20 逻辑核, 16 GB)**: 同案例同二进制交替 np=1 / np=8 跑多轮,
  取 status.json 的 elapsed_sec:
    - `EcTSmCube` (最大案例, 3 场瞬态耦合): np=1 → 374.2 / 403.3 s; np=8 → 150.3 / 168.6 s
      → **约 2.4x 加速**, 两轮一致。
    - `EcTSmBusbar` (3 场稳态, 小): np=1 → 37.7 / 31.0 / 31.5 s; np=8 → 40.6 / 38.9 / 40.9 s
      → **小案例多核反而略慢** (线程/装配开销 > 并行收益), 且两档各自离散度都小于档间差异。
    - 单次测量的 `SmPlateHole` 67.8 (np=1) → 91.8 (np=8) → 42.8 (np=14)、
      `TFinArray` 47.9 → 29.4 → 34.9 属同一现象, 不能只看单次数字。
    - np=14 对 `EcTSmCube` 反而比 np=8 慢 (204.9 vs 175.7), 故默认核数上限取 8。
- **数值不受影响**: np=8 与 np=14 的 4 案例回归健康检查全 PASS (解析解容差内), 与 np=1 同结论。
- **案例之间仍串行**: 一个案例一个 batch 子进程, 避免多个案例同时抢内存 (最大案例峰值约 4 GB)。
