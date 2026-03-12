## Why

当前 YAML DSL 能力边界已经很强,但仍存在几类“即使不做完整重写,也能用较低成本显著减痛”的问题:

- 若干关键路径仍依赖 YAML anchors/alias 的解析细节与“对象身份”(尤其是 `output.fields`),对普通 YAML 用户不直觉,且对未来解析器升级/替换不友好。
- 概念命名存在误导(顶层 `fields` 实际只允许派生字段),容易写错且文档解释成本高。
- params 语言形态不一致(字符串占位符 `$runtime.*` vs 映射指令节点 `$keys/$rows`),让“模板 vs 运行期渲染”的心智负担偏高。
- relation steps 的 `field_id vs data_key` 误用诊断仍不够“可操作”,迁移/排错成本高。

此前 `yaml-dsl-syntax-overhaul` 已输出了若干候选方案与对照材料,review 后决定暂不推进激进语法重写,优先落地一组无争议的 micro-tunes,先把痛点降下来,并为后续更大改动降低风险。

## What Changes

- relation 引用支持字符串 ref:
  - 允许 `relation: <relation_id>` (string),并要求存在同名 `relations.<id>`。
  - 仍允许 `relation: {steps: [...]}`(steps 对象写法)。
- `output.fields` 引入更直觉的 string sugar:
  - 允许 `output.fields: [order_id, order_date, customer_name]` 作为 `field_id` 列表 sugar。
  - 允许 `output.fields: [orders.order_id, customers.customer_name]` 作为显式 `source.field_id` sugar(用于消歧)。
  - 仍保留对象条目用于覆写 `name/relation/value_cast/...`。
- **BREAKING**: 顶层派生字段入口从 `fields` 改名为 `derived_fields`:
  - 仓内示例/fixtures/docs/skills/frontend examples 一次性升级为 `derived_fields`。
  - `fields` 名称预留给未来“跨多数据源/多需求的字段处理入口”(本 change 不实现该能力)。
- **BREAKING**: runtime vars 统一为指令节点形态:
  - 以 `{$runtime: order_ids}` 取代字符串占位符 `$runtime.order_ids`,与 `$keys/$rows` 的映射指令形态统一。
- 强化静态提示与自动修复建议:
  - 当 relation steps 误写 data_key 时,错误消息附带最可能的 `field_id` 建议与可直接复制的修复片段。

## Capabilities

### New Capabilities
- `yaml-dsl-micro-tunes`: 当前 YAML DSL 的低风险语法/校验改良(减少 alias 依赖、统一命名与 params 指令形态、提升诊断可操作性)。

### Modified Capabilities
- (none)

## Impact

- YAML DSL JSON Schema 与 editor schema:
  - `src/scalim/dsl/by_yaml/schema/demand.gen.json` + `scripts/gen-yaml-dsl-schema.py`
  - `frontend/scalim-yaml-dsl-editor/**/schema/demand.gen.json`
- 语义 validator / parser:
  - `src/scalim/dsl/by_yaml/config_parsing/**`
- CLI validate 行为与报错:
  - `src/scalim/cli/yaml_dsl.py`
- Docs/skills/examples:
  - `docs/doc/yaml-dsl/**`
  - `artifacts/skills/scalim-yaml-dsl/**`
  - `tests/fixtures/**`
  - `notebooks/marimo/examples/**`
