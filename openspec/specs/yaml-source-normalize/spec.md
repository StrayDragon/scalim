# yaml-source-normalize Specification

## Purpose
TBD - created by archiving change yaml-source-normalize. Update Purpose after archive.
## Requirements
### Requirement: lookup sources support declarative whole-result `normalize`

系统 SHALL 支持在 lookup source 上声明 `normalize`,用于在字段读取前对 loader 的整个返回值做一次 whole-result normalization。

系统 MUST 至少支持:
- `kind: index_by_key`
- `on_conflict: error|first|last`(默认 `error`)
- `on_none: raise|skip`(默认 `raise`,仅对 `index_by_key` 有意义)
- `key_field: <field_name>`（可选,仅对 `index_by_key` 有意义）

当 `normalize.kind=index_by_key` 时:
- 若 `normalize.key_field` 为非空字符串,系统 MUST 使用其作为 effective `key_field`,并且 MUST 校验 `normalize.key_field == sources.<id>.key`（避免语义漂移）
- 若 `normalize.key_field` 缺失或为空字符串,系统 MUST 将 effective `key_field` 推导为 `sources.<id>.key`
- 若 `sources.<id>.key` 为复合键(tuple/list),系统 MUST fail-fast（`index_by_key` 仍不支持 composite key）
- 若任一 row 缺失 effective `key_field`,系统 MUST fail-fast
- 若任一 row 的 effective `key_field` 值为 `None`:
  - 若 `normalize.on_none` 缺失或为 `raise`,系统 MUST fail-fast
  - 若 `normalize.on_none=skip`,系统 MUST 跳过该 row
- 若任一 row 的 effective `key_field` 值非 hashable,系统 MUST fail-fast

`index_by_key` 的语义 MUST 为:
- 输入: `list[row]`
- 输出: `mapping[lookup_key, row]`

#### Scenario: `index_by_key` 省略 `key_field` 默认取 source key
- **WHEN** source 配置为:
  ```yaml
  key: order_id
  normalize:
    kind: index_by_key
  ```
- **AND** loader 返回:
  ```python
  [{"order_id": 101, "score": 0.9}, {"order_id": 102, "score": 0.7}]
  ```
- **THEN** 系统 MUST 将其归一化为:
  ```python
  {101: {"order_id": 101, "score": 0.9}, 102: {"order_id": 102, "score": 0.7}}
  ```

#### Scenario: `on_none` 缺省(或 `raise`)遇到 `None` key fail-fast
- **WHEN** source 配置为:
  ```yaml
  key: order_id
  normalize:
    kind: index_by_key
  ```
- **AND** loader 返回:
  ```python
  [{"order_id": 101, "score": 0.9}, {"order_id": None, "score": 0.0}]
  ```
- **THEN** 归一化 MUST 失败并指出 `order_id` 不允许为 `None`

#### Scenario: `on_none=skip` 跳过 `key_field is None` 的 row
- **WHEN** source 配置为:
  ```yaml
  key: order_id
  normalize:
    kind: index_by_key
    on_none: skip
  ```
- **AND** loader 返回:
  ```python
  [
    {"order_id": 101, "score": 0.9},
    {"order_id": None, "score": 0.0},
    {"order_id": 102, "score": 0.7},
  ]
  ```
- **THEN** 系统 MUST 将其归一化为:
  ```python
  {
    101: {"order_id": 101, "score": 0.9},
    102: {"order_id": 102, "score": 0.7},
  }
  ```

#### Scenario: `index_by_key` 显式指定 `key_field` 与 `key` 一致仍可工作
- **WHEN** source 配置为:
  ```yaml
  key: order_id
  normalize:
    kind: index_by_key
    key_field: order_id
  ```
- **AND** loader 返回:
  ```python
  [{"order_id": 101, "score": 0.9}, {"order_id": 102, "score": 0.7}]
  ```
- **THEN** 系统 MUST 将其归一化为:
  ```python
  {101: {"order_id": 101, "score": 0.9}, 102: {"order_id": 102, "score": 0.7}}
  ```

#### Scenario: `key_field` 与 `key` 不一致被拒绝
- **WHEN** source 配置为:
  ```yaml
  key: order_id
  normalize:
    kind: index_by_key
    key_field: user_id
  ```
- **THEN** 系统 MUST fail-fast 并指出 `normalize.key_field` 必须与 `sources.<id>.key` 一致

#### Scenario: composite key + `index_by_key` 被拒绝
- **WHEN** source 配置为:
  ```yaml
  key: [order_id, user_id]
  normalize:
    kind: index_by_key
  ```
- **THEN** 系统 MUST fail-fast 并指出 `index_by_key` 不支持 composite key

#### Scenario: duplicate key 默认报错
- **WHEN** `normalize.kind=index_by_key`
- **AND** loader 返回两个 effective `key_field` 相同的 row
- **AND** 未显式设置 `on_conflict`
- **THEN** 归一化 MUST 失败

#### Scenario: duplicate key 可按 `first` 保留第一条
- **WHEN** `normalize.kind=index_by_key`
- **AND** `normalize.on_conflict=first`
- **AND** loader 返回多个相同 key 的 row
- **THEN** 系统 MUST 保留第一条 row 作为该 key 的归一化结果

### Requirement: whole-result `normalize` runs before field extraction
系统 MUST 在字段级 `extract` / flat field 读取之前完成 `normalize`,使后续字段读取总是面对归一化后的 row mapping。

#### Scenario: 字段读取基于 normalized mapping 执行
- **WHEN** source 声明 `normalize.kind=index_by_key`
- **AND** 字段配置为 `extract: score`
- **THEN** 字段读取 MUST 直接针对 `index_by_key` 生成的单条 row 执行

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

