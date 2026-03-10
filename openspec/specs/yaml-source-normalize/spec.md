# yaml-source-normalize Specification

## Purpose
TBD - created by archiving change yaml-source-normalize. Update Purpose after archive.
## Requirements
### Requirement: lookup sources support declarative whole-result `normalize`
系统 SHALL 支持在 lookup source 上声明 `normalize`,用于在字段读取前对 loader 的整个返回值做一次 whole-result normalization。

v1 MUST 至少支持:
- `kind: index_by_key`
- `key_field: <field_name>`
- `on_conflict: error|first|last`(默认 `error`)

`index_by_key` 的语义 MUST 为:
- 输入: `list[row]`
- 输出: `mapping[lookup_key, row]`

#### Scenario: `index_by_key` 将列表归一化为映射
- **WHEN** source 配置为:
  ```yaml
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

#### Scenario: duplicate key 默认报错
- **WHEN** `normalize.kind=index_by_key`
- **AND** loader 返回两个 `key_field` 相同的 row
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

