## ADDED Requirements

### Requirement: `IMPL_ROOT.dsl.by_yaml` MUST be the preferred public facade

系统 MUST 将 `IMPL_ROOT.dsl.by_yaml` 作为 YAML DSL 的首选公开 facade，用于承载用户最常见且受支持的运行入口与运行期契约。

系统可以保留 `runtime` 子模块作为实现分层和内部组合边界，但这些路径 MUST NOT 再作为面向普通用户的首选公开入口被文档、skills 或 examples 推荐。

#### Scenario: public guidance prefers facade over runtime internals
- **WHEN** 用户查阅 YAML DSL 的官方导入示例
- **THEN** 示例 MUST 优先使用 `IMPL_ROOT.dsl.by_yaml`
- **AND** 不得把 `IMPL_ROOT.dsl.by_yaml.runtime.entrypoints`、`runtime.contracts` 或 `runtime.introspection` 作为默认推荐入口

### Requirement: official facade MUST preserve current extension seams

在公共表面收敛过程中，系统 MUST 保持当前已确认的受控扩展点继续可经由官方 facade 使用，而不是通过删减能力来完成“收敛”。

本轮至少包括：

- `sink`
- `components`
- `output_composition`
- `allowed_modules` / `allowed_functions`
- `allowed_yaml_roots`

#### Scenario: public facade remains behavior-complete for supported extension seams
- **WHEN** 调用方通过 `IMPL_ROOT.dsl.by_yaml.run(...)` 或 `compile(...)` 使用上述受控扩展点
- **THEN** 系统 MUST 继续支持这些能力
- **AND** 公共表面收敛 MUST 体现为“入口与契约明确”,而不是静默删除这些受支持能力
