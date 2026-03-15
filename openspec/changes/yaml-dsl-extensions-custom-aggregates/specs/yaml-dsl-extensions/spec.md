## ADDED Requirements

### Requirement: 自定义 aggregate kind/ref 可编译为派生聚合
系统 SHALL 允许 YAML `outputs[*].aggregate` 使用自定义 kind/ref 形态,并通过扩展工厂编译为派生聚合输出.

约束:
- 自定义 aggregate 工厂 MUST 返回可执行的派生聚合描述(至少包含 `IDerivedAggregationSpec` 与输出字段列表)
- 系统 MUST 使用该派生聚合的 `required_fields()` 将依赖字段注入到 required_demand_fields,以保证 planner/executor 可得到完整依赖闭包

#### Scenario: 自定义 aggregate 注入 required fields
- **GIVEN** YAML `outputs[0].aggregate` 使用自定义 kind 且其 `required_fields()` 返回字段 `a/b`
- **WHEN** 编译并执行该 YAML
- **THEN** 系统 MUST 将 `a/b` 纳入本次运行的 required 字段集合,确保执行期不会因缺失依赖字段而失败

### Requirement: 自定义 aggregate 的 required_fields 必须进入 required 字段闭包
系统 MUST 确保自定义 aggregate 的 `derived.required_fields()` 在字段裁剪/IR 构造前即可生效,避免 composed outputs 运行时缺字段.

#### Scenario: required_fields 注入到 required 闭包
- **GIVEN** YAML outputs 使用自定义 aggregate kind/ref
- **AND** 该 aggregate 的 `derived.required_fields()` 返回字段 `a/b`
- **WHEN** 系统编译该 YAML 并构建执行计划
- **THEN** 执行计划 MUST 包含 `a/b` 作为 required 字段(不会因字段裁剪缺失而失败)
