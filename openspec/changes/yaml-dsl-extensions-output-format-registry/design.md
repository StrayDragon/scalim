## Context

该 change 引入统一的 output format registry,用于解耦 “YAML authoring surface” 与 “输出格式实现”。

umbrella 设计见:

- `openspec/changes/yaml-dsl-extensibility-preproposal/design.md` 的 Decision 8/8.1/8.2

## Decisions

1) 单输出与 composed outputs 共享 registry:
- 避免“单输出支持某格式但 composed outputs 不支持(或反之)”的漂移

1.1) format_id 命名空间与 YAML 映射:

- execution 层的 format_id MUST 沿用现有 `OutputSpec.format` 语义(内置 `csv`/`excel`)
- YAML `outputs[*].container.type` 的内置值保持 `workbook/csv`
- mapping(已确认,确定性):
  - `container.type: workbook` → execution format_id `excel`
  - `container.type: csv` → execution format_id `csv`
  - 其它值 → 视为自定义 format_id,直接透传到 registry

2) `container.options` 作为扩展配置载体:
- schema 允许自由 dict
- factory 必须可接收该 options(内置 `csv/excel` 可忽略;YAML `workbook` 对应 `excel`)

3) 容器型输出(handle):
- 以确定性 `container_key` 复用底层资源(如 workbook/sqlite)
- 生命周期结束必须 close

## Type Friendliness (Notes)

当前方案把 `container.type` 从“固定枚举”放开为“string format_id”,以支持扩展输出。代价是 schema/editor 可能不再对 `workbook/csv` 提供强 enum 补全。

如后续需要更“类型友好”的 schema 提示,可以考虑两种增强(均不改变 runtime 语义):

1) 在 JSON Schema 中将 `container.type` 表达为 `anyOf`:
   - `enum: ["workbook","csv"]`(保留补全)
   - `type: "string"`(允许自定义 format_id)

2) 引入更语义化的新字段(较重,可能需要迁移):
   - `container.format_id` 表达 format id
   - `container.type` 回归为“容器/内置形态”(例如 workbook/csv)

## Non-Goals

- 不在本 change 中引入自定义 aggregate(kind/ref)语义(由对应 change 处理)
