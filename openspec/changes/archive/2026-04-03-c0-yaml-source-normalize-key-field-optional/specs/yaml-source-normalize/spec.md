## MODIFIED Requirements

### Requirement: lookup sources support declarative whole-result `normalize`

系统 SHALL 支持在 lookup source 上声明 `normalize`,用于在字段读取前对 loader 的整个返回值做一次 whole-result normalization。

系统 MUST 至少支持:
- `kind: index_by_key`
- `on_conflict: error|first|last`(默认 `error`)
- `key_field: <field_name>`（可选,仅对 `index_by_key` 有意义）

当 `normalize.kind=index_by_key` 时:
- 若 `normalize.key_field` 为非空字符串,系统 MUST 使用其作为 effective `key_field`,并且 MUST 校验 `normalize.key_field == sources.<id>.key`（避免语义漂移）
- 若 `normalize.key_field` 缺失或为空字符串,系统 MUST 将 effective `key_field` 推导为 `sources.<id>.key`
- 若 `sources.<id>.key` 为复合键(tuple/list),系统 MUST fail-fast（`index_by_key` 仍不支持 composite key）

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
