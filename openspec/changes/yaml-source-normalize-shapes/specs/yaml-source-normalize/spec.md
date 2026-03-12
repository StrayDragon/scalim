## ADDED Requirements

### Requirement: `normalize.kind=take_first`
系统 SHALL 支持 `normalize.kind=take_first`,用于将 `mapping[key -> list[row]]` 归一化为 `mapping[key -> row]`,并定义 `on_empty` 行为.

#### Scenario: `mapping[key -> list[row]]` 取第一条
- **WHEN** loader 返回 `mapping[key -> list[row]]`
- **AND** 配置 `normalize.kind=take_first`
- **THEN** 系统 MUST 将每个 value list 取第一条并输出为 `mapping[key -> row]`

#### Scenario: 顶层 `list[row]` + `take_first` 被拒绝
- **WHEN** loader 返回 `list[row]`
- **AND** 配置 `normalize.kind=take_first`
- **THEN** 系统 MUST fail-fast 并提示使用 `normalize.kind=index_by_key`(用 `on_conflict` 定义冲突策略)

### Requirement: `normalize.kind=map_values`
系统 SHALL 支持 `normalize.kind=map_values`,用于对 `mapping` 的 values 批量应用 normalization pipeline(例如 `take_first` + `project_fields`).

#### Scenario: `mapping[key -> list[row]]` 批量 take_first
- **WHEN** loader 返回 `mapping[key -> list[row]]`
- **AND** 配置 `normalize.kind=map_values` 且 values pipeline 包含 `take_first`
- **THEN** 系统 MUST 输出 `mapping[key -> row]`

### Requirement: `normalize.kind=project_fields`
系统 SHALL 支持 `normalize.kind=project_fields`,用于对 row 或 nested mapping 做投影与重命名,并允许 key 为任意标量(含 int)的定位方式(例如 `"[1].clearn_reason_level"`).

#### Scenario: nested dict 投影包含 int key
- **GIVEN** loader 返回的 row 含嵌套结构且中间 key 为 int
- **WHEN** `project_fields` 声明其投影规则
- **THEN** 系统 MUST 以确定性方式输出投影后的 row

### Requirement: 受控扩展点 `normalize.call_by`
系统 SHALL 提供受控扩展点 `normalize.call_by` 用于复用 allowlist 引用解析能力.
当使用该扩展点时,系统 MUST 固定 contract: 输入与输出均为 `Mapping`(否则 fail-fast),避免不可解释形状漂移.

#### Scenario: `normalize.call_by` 返回非 Mapping 被拒绝
- **WHEN** `normalize.call_by` 返回非 `Mapping` 值
- **THEN** 归一化 MUST 失败并指出 contract 违反
