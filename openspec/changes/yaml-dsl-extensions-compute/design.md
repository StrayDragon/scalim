## Context

该 change 只处理 compute/where 的扩展函数与依赖推导一致性。

关键约束:
- 仍使用既有安全表达式模型(`SecureComputeEngine`),不放宽 AST 白名单
- 依赖推导必须把函数名与字段名解耦,否则扩展函数名会被当作字段依赖
- validator/config parsing/runtime 必须共享同一套“扩展后的 compute engine”,否则会出现 validate/compile/run 漂移

umbrella 设计见:

- `openspec/changes/archive/2026-03-15-yaml-dsl-extensibility-preproposal/design.md` 的 Decision 6/6.1

## Decisions

1) 扩展函数注入:
- ExtensionHost 提供 `compute_functions`
- compiler/validator/runtime 都从同一处构造 compute engine(SSOT),并保证以下链路使用同一实例或等价实例(相同函数映射):
  - `ConfigValidator`(语义校验 + where 编译校验)
  - YAML `outputs` parser 的 where 校验(`src/scalim/dsl/by_yaml/config_parsing/parsers/outputs.py`)
  - `ConfigToIRConverter`(派生字段 compute 编译/转换)
  - runtime output composition 的 where predicate 编译(`src/scalim/dsl/by_yaml/runtime/output_composition_yaml.py`)

2) 依赖推导:
- `Call.func` 的函数名 MUST NOT 计入字段依赖
- 仅对 `Call.args/keywords` 继续递归收集字段依赖

## Non-Goals

- 不在本 change 中引入 output format registry/custom aggregates 等其它扩展面
