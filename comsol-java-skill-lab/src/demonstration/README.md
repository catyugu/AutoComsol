# src/demonstration/ — API 演示型案例

本目录专放 **API 用法演示**类 Java 模型：目的是把某个 COMSOL Java API 的调用方式
（入口、键名、合法取值、读回方式）写成一个可直接编译运行的完整模型，作为文档的活样本。

## 与 analytic/ physical/ 的区别

|                  | analytic/ physical/                   | demonstration/                                   |
| ---------------- | :------------------------------------ | ------------------------------------------------ |
| 目的             | 验证物理/数值正确性                   | 说明 API 怎么调用                                |
| 验证脚本         | 有（`scripts/verifications/<tier>/`） | **无**                                           |
| REGISTRY / sweep | 注册，参与全回归                      | **不注册**，不参与 sweep                         |
| 是否求解         | 求解并导出结果                        | 通常只建模 + 保存，不做诊断                      |
| 三处同步         | src + verifications + skill examples  | src + skill `references/examples/demonstration/` |

编译仍走既有工具链（`run.py` 的 `SRC_TIERS` 已包含本目录）：

```bash
python scripts/run.py all <ClassName> <run-dir> <run-dir>/<ClassName>.mph
```

## 命名约定

`<ApiTopic>Demonstration`，`ApiTopic` 用 API 主题的驼峰名（不是物理场缩略名），
例如 `FieldDiscretizationDemonstration`（非标量场的有限元离散类型控制）。

## 现有案例

- `FieldDiscretizationDemonstration` — 非标量场（结构力学位移 `[u,v,w]`、频域电磁场
  `[Ex,Ey,Ez]`）的有限元离散类型控制：`physics().prop("ShapeProperty").set("order_<场标识>", <离散码>)`、
  `getAllowedPropertyValues` 的接口族差异（Lagrange `2s` / curl `2t2` / BEM `p21`）、
  以及它与几何形状阶次 `component().sorder(...)` 的区别。
