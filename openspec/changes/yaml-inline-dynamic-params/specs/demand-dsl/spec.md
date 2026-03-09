## ADDED Requirements

### Requirement: source loader params are rendered from a declarative kwargs template
系统 SHALL 将 `main_source.params` 与 `sources.<id>.params` 视为 loader kwargs 模板,并在调用 loader 前渲染为最终的 kwargs.

渲染规则:
- `main_source.params` 仅允许静态值(禁止 `$keys/$rows`)
- `sources.<id>.params` 允许包含 `yaml-inline-dynamic-params` 定义的 `$keys/$rows` 指令节点

#### Scenario: sources.<id>.params 渲染为嵌套 kwargs
- **WHEN** `sources.order_evaluations.params` 为:
  ```yaml
  params:
    params:
      order_id_set: {$keys: {as: set}}
      include_deleted: false
  ```
- **THEN** ref loader 调用 MUST 接收到 `kwargs["params"]["order_id_set"] == set(lookup_keys)`
- **AND** ref loader 调用 MUST 接收到 `kwargs["params"]["include_deleted"] == false`

### Requirement: static `sources.<id>.params` MUST be passed even without legacy bind/to_bind
系统 MUST 在 ref loader 调用时透传渲染后的 `sources.<id>.params` kwargs,即使未声明 legacy `bind/to_bind`.

#### Scenario: 仅声明静态 params 仍被透传
- **WHEN** `sources.customers` 未声明 `bind/to_bind`
- **AND** `sources.customers.params` 为:
  ```yaml
  params:
    region: "CN"
  ```
- **THEN** ref loader 调用 MUST 以 `loader(region="CN")` 的形式透传该参数(而非零参调用)

### Requirement: params directives and legacy bind/to_bind are mutually exclusive
系统 MUST 禁止在同一 source/step 上同时使用 `$keys/$rows` 指令节点与 legacy `bind/to_bind`,以避免冲突与语义分裂.

#### Scenario: 同时声明模板指令与 bind 被拒绝
- **WHEN** `sources.customers` 同时声明:
  - `bind: {use_keys: {param: ids}}`
  - `params` 模板中包含 `$keys` 或 `$rows`
- **THEN** 校验 MUST 失败并提示迁移为模板写法

