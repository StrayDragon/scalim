## ADDED Requirements

### Requirement: schema hover documents `$keys/$rows` directive nodes under `params`
系统 MUST 在生成的 YAML DSL JSON Schema 中,为 `main_source.params` 与 `sources.*.params` 提供明确的 hover 文档,解释:
- `$keys` 指令节点的用途、`as=set|list` 选项与最小示例
- `$rows` 指令节点的用途、`cache_mode=batch|none` 选项与最小示例
- `$rows` 会触发 rows barrier(并行退化)的提示
- `$keys/$rows` 仅在 ref loader 上下文可用,main_source/preload 禁止

#### Scenario: params hover 包含 `$keys/$rows` 示例
- **WHEN** 生成 `src/IMPL_ROOT/dsl/by_yaml/schema/demand.gen.json`
- **THEN** `main_source.params` 与 `sources.*.params` 的 `markdownDescription` MUST 包含 `$keys/$rows` 指令节点说明与示例片段

