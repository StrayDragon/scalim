## ADDED Requirements

### Requirement: ValidationIssue path MUST be normalized to a single canonical format for location mapping
系统 MUST 对 `ValidationIssue.path` 采用单一 canonical 口径,并确保该口径可以稳定映射到 YAML 源码位置:

- canonical 口径 MUST 使用点号分段
- 数组索引 MUST 使用数字段(`outputs.0.fields.1`)
- CLI/定位层 MUST 对旧 bracket 风格 path 做 normalization,至少支持将 `foo[0].bar[1]` 归一化为 `foo.0.bar.1`

#### Scenario: bracket path still yields precise location
- **GIVEN** 某 validator 仍产出 issue path `outputs[0].container.path`
- **WHEN** 用户运行 `scalim-cli yaml-dsl validate <file.yaml>`
- **THEN** CLI 输出 MUST 能定位到 `outputs.0.container.path` 对应的 `path:line[:column]`

#### Scenario: CLI outputs canonical dot path
- **WHEN** CLI 输出某条诊断
- **THEN** 该诊断展示的逻辑路径 MUST 为 canonical 点号口径(不出现 bracket)

