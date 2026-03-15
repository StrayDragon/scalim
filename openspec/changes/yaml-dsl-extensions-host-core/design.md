## Context

本 change 定义并实现 `ExtensionHost` 的“解析 + 合并 + 摘要(可对拍)”核心,作为后续所有 extensions-aware 行为的 SSOT。
本 change 只负责把 YAML `extensions` 编译成一个稳定的扩展视图(含 provenance/diagnostics),并提供 YAML components 注入的装配边界。
compute/output/aggregate/transform/analyze 的“具体运行语义”由后续 changes wire-up(它们读取同一个 `ExtensionHost`)。

完整 umbrella 设计见:

- `openspec/changes/yaml-dsl-extensibility-preproposal/design.md`

## YAML Inputs (subset)

本 change 关注的 YAML 形态(由 `yaml-dsl-extensions-schema` 先保证 schema/loader 可承载):

- `extensions.enabled: bool` (缺省视为 `true`;为 `false` 时整个 extensions 被跳过)
- `extensions.api: int` (缺省视为 `1`;未知值 fail-fast)
- `extensions.bundles: [{ref: <python-ref>, config?: <object>}]`
- `extensions.compute.functions: {<name>: <python-ref>}`
- `extensions.outputs.formats: {<format_id>: <python-ref>|{ref: <python-ref>, config?: <object>}}`
- `extensions.aggregates.kinds: {<kind_id>: <python-ref>|{ref: <python-ref>, config?: <object>}}`
- `extensions.transform.{raw|config|ir|request}: [{ref: <python-ref>, config?: <object>}]`
- `extensions.analyze: [{ref: <python-ref>, config?: <object>}]`
- `extensions.components: [<python-ref>|{ref: <python-ref>, config?: <object>}]`
- `extensions.conflicts: { ... }` (冲突策略,见下文)

约束:

- 相对引用 `.`/`..` 只有在提供 `yaml_path` 以推导 `base_module_path` 时才允许(与现有 `SecurePythonReferenceResolver` 语义一致)。
- `load_string(...)` 等无路径入口遇到相对引用 MUST fail-fast,并提示改用 file entrypoint 或改写为绝对引用。

## Decisions

1) 合并顺序(默认,确定性):

- direct config → 编译为“隐式 bundle”
- `extensions.bundles` 按 YAML 声明顺序依次调用并合并贡献

2) `ref + config` 统一解析/实例化/调用约定:

- 所有扩展引用统一用 `SecurePythonReferenceResolver` 解析(显式 allowlist)。
- 对 `{ref, config}` 条目,系统统一执行“实例化/调用”策略以兼容函数/类/工厂:
  - 解析得到 `obj`
  - 以“最少惊讶”的优先级尝试调用(示意): `(config, ctx)` → `(config)` → `(**config, ctx=ctx)` → `(**config)` → `(ctx)` → `()`
  - 其中 `ctx` 为只读上下文(至少包含 `yaml_path` 与 stage 信息);`config` 允许为任意对象,但当需要 `**config` 时必须为 mapping
- bundle factory 的返回值 MUST 为 `ExtensionBundle`(或等价结构);否则 fail-fast 并包含 ref/stage 上下文

3) 冲突策略(默认建议,可配置):

- registry 键(如 compute function name / output format id / aggregate kind id)同名冲突默认 **error**
- 允许通过 `extensions.conflicts` 配置为 `last_wins`
- 冲突错误必须包含: 冲突键名 + 贡献来源(ref/yaml_path)

4) 摘要与诊断:

- `ExtensionHost.summary` 必须包含最终启用的 bundles/analyzers/registries/transformers/components 列表(含来源 ref),用于对拍与排障
- 任意扩展加载/调用失败必须包含 `yaml_path/ref/stage` 上下文
- 建议的 stage 命名(稳定可 grep): `extensions.resolve_ref` / `extensions.instantiate` / `extensions.call_bundle` / `extensions.merge` / `extensions.components`

5) components 装配:

- YAML 注入的 components MUST 复用 `split_components` 做严格类型切分并 fail-fast
- 装配顺序建议为: driver `components` → `extensions.components` → `observability.*` observers
  - 目的: 保持现有 driver+observability 行为稳定,并使 extensions 注入具备确定性位置

## Non-Goals

- 不在本 change 中接入 compute/output/aggregate/transform/analyze 的具体运行语义(只提供 SSOT 产物与合并规则)
- 不提供 CLI flags(由后续 change 处理)
