## ADDED Requirements

### Requirement: `normalize` is allowed on `sources.*` and rejected on `main_source`
系统 SHALL 在 `sources.<id>` 上支持可选对象 `normalize`,并将其用于 lookup source 的 whole-result normalization.
系统 MUST 拒绝 `main_source.normalize`.

#### Scenario: `sources.*.normalize` 通过校验
- **WHEN** `sources.order_recommends.normalize.kind: index_by_key`
- **THEN** YAML 校验与 IR 转换 MUST 通过

#### Scenario: `main_source.normalize` 被拒绝
- **WHEN** YAML 声明 `main_source.normalize`
- **THEN** 校验 MUST 失败并指出 `main_source.normalize`
