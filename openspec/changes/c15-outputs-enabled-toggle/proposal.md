## Why

来自 cus_collect_infos 迁移实践反馈（基于 Scalim 0.3.2 实际使用；FR6）：当业务希望“结构性地禁用某个 output”（例如占位、暂时下线、分支报表），目前常见写法是 `where: "False"`。

但 `where` 的语义本质是“按行过滤/路由”，不是“启用开关”。仓库内也已在 schema 文档中明确提示该问题（例如 `src/scalim/dsl/by_yaml/schema_dsl/models/outputs.py` 的 `where` 文档里写到未来应有 `enabled_if`/类似字段）。

现状带来的问题：

- 可读性差：读者难判断这是 bug 还是刻意禁用
- required fields/编译期依赖注入仍可能被该 output 牵引（即使 `where=False` 最终不产出行）
- workflow writes 若引用该 output，意图更不清晰（写入一个永远为空的输出）

本变更希望给 outputs 提供一个明确、低风险的“静态禁用”入口：`enabled: false`，用于替代 `where: "False"` 的误导性用法。

## What Changes

- 在 demand YAML 的 `outputs[*]` 上新增可选字段：
  - `enabled: bool`（默认 `true`）
- 语义（v1 仅做静态禁用，不引入表达式条件）：
  - 当 `enabled=false`：
    - 该 output 不参与 required fields 解析与编译期依赖注入（避免“禁用但仍拖动计算”的隐性成本）
    - execution/output composition 不创建该目标的 sink，不写入任何内容
    - 若启用 meta/audit，框架应将该 output 标记为 disabled（便于对拍与审计）
  - `where` 语义保持不变：仍是 row-level filter/router，不再承担“禁用开关”的角色
- Non-Goals：
  - v1 不引入 `enabled_if`（避免表达式上下文/可见性/静态分析复杂度）
  - 不改变存量 `where: "False"` 行为（仍按过滤表达式处理）

## Capabilities

### New Capabilities
- `outputs-enabled-toggle`: YAML outputs 支持显式静态禁用（`enabled: false`），并定义其对 required fields / sink 创建 / meta/audit 的影响。

### Modified Capabilities
- `output-composition`: 多目标输出组合需要在规范层明确“disabled target”的统计与 meta/audit 表现。
- `yaml-dsl-schema`: demand schema 增加 `outputs[*].enabled` 字段（SSOT 在 `schema_dsl`，生成物由脚本刷新）。

## Impact

- 受影响代码（示例）：
  - schema SSOT：`src/scalim/dsl/by_yaml/schema_dsl/models/outputs.py`
  - YAML → output composition 编译：`src/scalim/dsl/by_yaml/runtime/output_composition_yaml.py`
  - execution：`src/scalim/execution/output_composition.py`（内部已存在 `disabled` 状态概念，可作为实现落点）
- 兼容性：新增可选字段，默认行为不变。
- 文档治理：
  - schema 生成物：`src/scalim/dsl/by_yaml/schema/demand.gen.json`（禁止手改；后续通过脚本/`just` 入口刷新）
  - docs 生成物（`.gen.`/AUTOGEN blocks）如需同步，走 `just gen-docs`
