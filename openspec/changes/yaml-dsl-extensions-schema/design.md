## Context

本 change 只解决 “schema/loader 接受 `extensions`” 的前置条件;扩展解析、合并与执行在后续 changes 实现(见 `openspec/changes/yaml-dsl-extensibility-preproposal/` 的 umbrella 设计)。

关键约束:

- 顶层仍保持 `additionalProperties: false`,避免 YAML 漫游未知字段
- 仅对 `extensions` 命名空间放开可扩展形状
- 本 change 不导入/执行扩展引用,只改变 “可承载/可校验” 能力

## Decisions

1) `extensions` 为顶层可选对象;缺省不影响现有 YAML。

2) `extensions` 内部采用“最小结构 + 可扩展容器”:

- 常用键提供结构(便于 editor/hover/outline)
- `functions/formats/kinds` 等采用 `additionalProperties` 映射,支持 dynamic keys
- `config/options` 允许自由 dict,避免扩展点内部细节反复推动 schema 发版

3) runtime loader 的 jsonschema 校验必须接受 `extensions`(即便其内部出现扩展自定义键)。

4) **顶层严格性不变**:
- schema 仍 MUST 对未知顶层键报错/告警(依据 strict 模式)
- 仅 `extensions` 命名空间内放开扩展自定义键

## Non-Goals

- 不实现 `ExtensionHost` / bundles / transformers / analyzers
- 不引入 CLI flags
