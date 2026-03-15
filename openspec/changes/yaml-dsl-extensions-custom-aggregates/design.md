## Context

该 change 为 `outputs[*].aggregate` 引入可扩展的 kind/ref 形态。

umbrella 设计见:

- `openspec/changes/yaml-dsl-extensibility-preproposal/design.md` 的 Decision 9/9.1

## Decisions

1) 编译产物:
- aggregate factory 必须返回“编译后的聚合描述”(至少包含 `derived: IDerivedAggregationSpec` + `output_field_ids`)
- 该编译产物需要在两个阶段被使用:
  - outputs parse 阶段: 用 `derived.required_fields()` 注入 required 字段闭包(字段裁剪前)
  - output composition build 阶段: 用 `derived` 构建聚合器并用 `output_field_ids` 构造派生输出的 `ExportLayout`

2) required_fields 闭包:
- 必须在字段裁剪/fields parse 前可得,以注入 required 字段闭包
- 落点应在 YAML outputs 解析阶段(产生 required_field_ids 的地方),而不是在 runtime output composition 才临时计算

3) 并发校验:
- 在装配阶段执行并发边界校验,对不支持的 `parallel_mode` fail-fast
- 建议调用 `IDerivedAggregationSpec.validate_parallel_mode(parallel_mode)` 并把错误包装为可行动错误(含 yaml_path/kind_id/ref)

## Non-Goals

- 不在本 change 中引入 output format registry(由对应 change 处理)
