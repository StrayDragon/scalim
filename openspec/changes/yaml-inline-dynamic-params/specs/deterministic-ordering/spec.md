## ADDED Requirements

### Requirement: `$keys.as=list` ordering is stable and repeatable
系统 SHALL 在 `$keys.as=list` 路径输出稳定顺序的 keys 列表,并保证在相同输入 lookup_keys 集合下跨运行可重复(不受 `PYTHONHASHSEED` 影响).

#### Scenario: `$keys.as=list` 顺序稳定
- **WHEN** loader params 模板使用 `$keys: {as: list}` 且输入 lookup_keys 集合相同
- **THEN** 传递给 loader 的 keys 列表顺序必须一致

