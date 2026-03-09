## MODIFIED Requirements

### Requirement: schema 元数据生成与 hover 指引
系统 SHALL 使用 `src/IMPL_ROOT/dsl/by_yaml/schema_dsl/` 的元数据(见 `constants.py` 与 `models/__init__.py`)生成 `src/IMPL_ROOT/dsl/by_yaml/schema/demand.gen.json` 并将其视为唯一 canonical schema.
- schema 顶层不包含 `dsl_version`
- schema 顶层仅保留 `relations`(排除 `relations_sql_like`/`relations_graph`)
- `relations.steps.from/to` 支持 `source.field` 字符串或同源字符串列表
- 数组字段 `items_choices` 映射为 `items.enum`
- schema 提供 steps/fields/sources/params 的中文 hover 描述与示例
- 对枚举/choices 字段提供简洁 hover 说明(逐项解释语义)并附带示例

#### Scenario: 生成器不产出 dsl_version
- **WHEN** 执行 schema 生成脚本
- **THEN** `demand.gen.json` 顶层不包含 `dsl_version` 属性

#### Scenario: Schema 支持 step 点号表达式
- **WHEN** 执行 schema 生成脚本
- **THEN** `steps.from` 与 `steps.to` SHALL 通过 `oneOf` 接受字符串或字符串数组

#### Scenario: enum hover 说明与示例
- **WHEN** 执行 schema 生成脚本
- **THEN** `output.format`/`output.header_fields_output_by`/`value_cast`/`lookup_cast.name`/`performance.report.format`/`relations.report.format`/`observability.viz.payload_policy` 的 `markdownDescription` 均包含选项语义说明且具备示例值
- **AND** `output.path` 的 `markdownDescription` MUST 说明相对路径以进程 CWD 为基准、会自动创建父目录且可能覆盖同名文件(并提示不要对不可信 YAML 开启文件输出)

### Requirement: schema hover 提供常见错误与迁移提示
系统 MUST 在 YAML DSL JSON Schema 的关键字段上提供可读且简短的常见错误/迁移提示,以提升编辑器 LSP 体验并减少试错成本:

- `relations.*.steps.from/to` 的 hover MUST 提示 steps 仅接受 **field_id**(YAML key)而非 loader 的 data_key,并给出简短示例.
- `lookup_cast` 的 hover MUST 提示 float lookup key 会被拒绝(避免歧义)并建议通过 `lookup_cast`/`value_cast` 显式归一化.
- `params` 的 hover MUST 提示 `$keys/$rows` 是新的稳定动态入参写法,并说明 legacy `bind/to_bind` 已迁移到 `params` 模板.

#### Scenario: hover 包含 field_id/data_key 提示
- **WHEN** 生成 `demand.gen.json`
- **THEN** `relations.*.steps.from/to` 的 `markdownDescription` MUST 提及 field_id 与 data_key 的区别并包含示例

#### Scenario: hover 包含 float key 策略提示
- **WHEN** 生成 `demand.gen.json`
- **THEN** `lookup_cast` 的 `markdownDescription` MUST 提示 float 被拒绝并给出修复建议

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

## REMOVED Requirements

### Requirement: bind/to_bind oneOf Schema
**Reason**: `bind/to_bind` 不再是稳定 YAML authoring surface;继续把它们作为 schema 主路径会与新 `params` 模板方案并存并制造双轨心智模型.

**Migration**: 将 `bind.use_keys` / `bind.use_rows` / `to_bind.use_keys` / `to_bind.use_rows` 迁移为 `main_source.params` 或 `sources.<id>.params` 中的 `$keys` / `$rows` 指令节点.
