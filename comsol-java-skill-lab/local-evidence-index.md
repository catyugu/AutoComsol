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

- `comsolcompile -help` → logs/comsolcompile-help.log (exit=0, 32 行)
- `comsolbatch -help` → logs/comsolbatch-help.log (exit=0, 115 行)
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
