## MODIFIED Requirements

### Requirement: Source/Bind 结构与 keys 分片参数
系统 SHALL 支持为数据源定义 `key`、`lookup_cast`、`cache_mode`、`params` 与 `lookup_chunk_size`.

其中:
- `main_source.params` 与 `sources.<id>.params` MUST 被视为 loader kwargs 模板
- `main_source.params` 仅允许静态值(禁止 `$keys/$rows`)
- `sources.<id>.params` 允许包含 `$keys/$rows` 指令节点
- `sources.*.bind` 不再属于该能力的稳定 YAML authoring surface

当 `sources.<id>.params` 中使用 `$keys: {as: list}` 时,从 YAML 转换到运行时参数构建器的行为 MUST 产生稳定顺序列表。
系统 MUST 使用语义清晰且无歧义的 key 常量公开命名,并在解析器/校验器中统一使用该命名.

以下命名 MUST 生效:
- `BIND_KEY_CONFIG_KEYS`
- `MEMORY_OPTIMIZATION_KEYS`
- `RELATION_CONFIG_KEYS`
- `RELATIONS_CONFIG_KEYS`

旧命名(`BIND_KEYS_KEYS`、`MEMORY_OPT_KEYS`、`RELATION_KEYS`、`RELATIONS_KEYS`)MUST NOT 继续作为公开常量提供.

#### Scenario: source params 模板构造动态参数
- **WHEN** source 配置:
  ```yaml
  params:
    params:
      ids: {$keys: {as: set}}
  ```
- **THEN** loader 调用应包含 `params={"ids": set(lookup_keys)}`

#### Scenario: `sources.*.bind` 旧写法被拒绝
- **WHEN** source 配置 `bind: {use_keys: {param: ids}}`
- **THEN** 校验 MUST 失败并提示迁移到 `params` 模板
- **AND** 错误信息 MUST 包含可直接照抄的替换建议片段(至少覆盖该常见形态),例如:
  ```yaml
  params:
    ids:
      $keys: {as: set}
  ```

#### Scenario: `$keys.as=list` 顺序稳定
- **WHEN** source 配置 `params` 模板中使用 `$keys: {as: list}` 且 lookup_keys 集合相同
- **THEN** 运行时传给 loader 的 keys 列表顺序必须稳定

#### Scenario: 解析器使用新常量
- **WHEN** 执行 YAML `bind/observability/relations` 解析
- **THEN** 解析路径应使用新常量命名

#### Scenario: 旧常量不可导入
- **WHEN** 调用方尝试导入旧常量名
- **THEN** 导入 MUST 失败
