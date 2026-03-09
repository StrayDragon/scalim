## ADDED Requirements

### Requirement: by_yaml runtime compiles `runtime_vars` into loader params templates
系统 SHALL 扩展 by_yaml runtime 的对外入口 `run/compile` 与 `RunOptions`,允许调用方提供可选的 `runtime_vars` 用于 loader 参数模板注入.
adapter MUST 在 `DemandConfig -> DemandIr` 转换前完成 `$runtime.*` 占位符解析,以确保:
- `DemandIr` 内持有的静态 params 可包含运行期对象(例如 `datetime`)
- execution 层无需理解 `$runtime.*` 语法

#### Scenario: 编译期完成占位符解析
- **WHEN** 调用方执行 `compile(..., runtime_vars=...)`
- **THEN** adapter 返回的 `Compilation.demand_ir` MUST 已反映占位符解析后的 params 值
- **AND** execution 层不需要再做二次解析

