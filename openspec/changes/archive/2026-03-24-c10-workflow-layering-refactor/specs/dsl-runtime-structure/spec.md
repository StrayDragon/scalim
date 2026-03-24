## MODIFIED Requirements

### Requirement: by_yaml runtime 是纯 adapter/编译器
系统 MUST 将 `IMPL_ROOT.dsl.by_yaml.runtime`(以及其对外入口)的职责收敛为 DSL adapter:
- YAML 解析/校验
- allowlist 安全边界(动态引用解析)
- `DemandConfig -> DemandIr` 编译
- 将 `output`/`observability` 编译为 DSL-agnostic 的运行请求对象
- 将 execution core result 包装为 YAML wrapper result

by_yaml runtime MUST NOT 直接承担执行编排主流程(如 plan 构建、engine 实例化/调用、sink finalize、observer manager 生命周期),这些 MUST 由 execution 的统一 IR 编排入口负责.

by_yaml runtime 同时 MUST NOT 承载 workflow 的执行编排；workflow runtime MUST 位于 framework 层(例如 `scalim.workflow.*`),YAML workflow 入口仅做前端编译与依赖注入.

#### Scenario: runtime 仅作为适配层
- **WHEN** 审阅 YAML DSL 的运行路径
- **THEN** 运行编排应委托 execution 层统一入口,而非在 by_yaml/runtime 内部自行拼装完整执行链

#### Scenario: workflow orchestration is not implemented in by_yaml runtime
- **WHEN** 调用方通过 workflow 的稳定入口运行 workflow YAML
- **THEN** workflow 的调度执行与资源/ctx/事件桥接 MUST 由 framework 层实现,而不是 by_yaml/runtime

