## ADDED Requirements

### Requirement: canonical schema 允许顶层 `extensions` 块
系统 MUST 在生成的 YAML DSL JSON Schema(`demand.gen.json`)中新增并允许可选顶层对象 `extensions`,用于承载对外扩展声明.

约束:
- `extensions` MUST 为对象
- schema-only 校验 MUST 不因 `extensions` 的存在而失败
- 顶层 `additionalProperties` MUST 保持为 `false`(未知顶层键仍应失败/告警)
- `extensions` MUST 支持同时表达 BUNDLE/ANALYZE/direct config 三类形态(至少包含 `enabled/bundles/analyze/compute/components/outputs/aggregates/transform` 的通用形状)
- `extensions` 内部允许出现扩展自定义的额外键(至少在 `extensions` 对象层级提供 `additionalProperties: true` 的容器能力),以避免“每个扩展点都必须随框架发版更新 schema”

#### Scenario: schema-only 校验接受 extensions
- **GIVEN** 一份 YAML DSL 顶层包含 `extensions: {enabled: true}`
- **WHEN** 使用 canonical schema 进行 schema-only 校验
- **THEN** 校验 MUST 通过

#### Scenario: runtime loader 不因 extensions 触发 schema error
- **GIVEN** 一份 YAML DSL 顶层包含 `extensions`(含额外键)
- **WHEN** 通过 `YamlDemandLoader.load(<yaml_path>)` 加载并触发 jsonschema 校验
- **THEN** 系统 MUST 不因 `additionalProperties` 限制而抛出 schema validation error

#### Scenario: 顶层未知键仍会被 schema-only 捕获
- **GIVEN** 一份 YAML DSL 顶层包含未知键 `foo: 1`
- **WHEN** 使用 canonical schema 进行 schema-only 校验
- **THEN** 校验 MUST 失败(或至少产生未知字段告警)

### Requirement: schema 为 bundles/analyze/direct config 提供最小可提示形状
系统 SHALL 在 canonical schema 中为 `extensions` 提供常用键的最小结构,以确保 editor/hover/outline 不会把扩展配置视为“未知结构”.

至少包括:
- `extensions.api: integer`
- `extensions.enabled: boolean`
- `extensions.bundles: array[item]` (item 支持 `{ref: <python-ref>, config: <any>}` 形态)
- `extensions.analyze: array[item]` (同上)
- `extensions.compute.functions: object[name -> <python-ref>]`
- `extensions.components: array[item]` (item 支持 `<python-ref>` 或 `{ref, config}` 形态)
- `extensions.outputs.formats: object[format_id -> <python-ref>|{ref, config}]`
- `extensions.aggregates.kinds: object[kind_id -> <python-ref>|{ref, config}]`
- `extensions.transform.*: array[item]` (raw/config/ir/request)
- `extensions.conflicts: object` (至少可表达 compute_functions/output_formats/aggregate_kinds/analyzer_failure 的策略)

#### Scenario: schema-only 接受 bundles/analyze/direct config 同时存在
- **GIVEN** YAML 同时包含 `extensions.bundles`、`extensions.analyze`、`extensions.compute.functions`
- **WHEN** 使用 canonical schema 进行 schema-only 校验
- **THEN** 校验 MUST 通过
