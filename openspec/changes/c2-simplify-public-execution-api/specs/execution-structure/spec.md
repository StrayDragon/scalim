# execution-structure Specification (Delta)

## ADDED Requirements

### Requirement: execution Tier1 facade MUST expose an options-only `run_ir` entrypoint

系统 MUST 将 execution 层的统一编排入口（`run_ir`）与其 DSL-agnostic contracts（`ExecutionRequest`/`ExecutionResult` 等）作为官方推荐 public facade 的一部分，
确保用户材料无需引用内部模块路径即可完成执行编排。

该 facade MUST 满足：

- `scalim.execution` MUST 提供 `run_ir` 与 `ExecutionRequest` 的稳定导入路径（通过 re-export 或等价方式）。
- 调用入口 MUST 以单一 request/options 对象驱动（`ExecutionRequest` 为唯一运行期契约承载）。

#### Scenario: user imports and runs execution via curated facade
- **WHEN** 调用方执行 `from scalim.execution import ExecutionRequest, run_ir`
- **THEN** 导入 MUST 成功
- **AND** 调用方 MUST 能以 `run_ir(demand_ir, request=ExecutionRequest(...))` 的方式运行而无需导入 `scalim.execution.run_ir` 模块路径
