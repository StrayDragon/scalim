# sinks-contracts Specification (Delta)

## ADDED Requirements

### Requirement: sinks public facade MUST separate optional-dependency sinks into explicit submodules

系统 MUST 将带可选依赖的 sinks 从默认推荐的 public facade 中隔离出来，以避免用户误认为其属于默认 runtime 基线能力。

系统 MUST 提供显式稳定导入路径（例如 `scalim.sinks.pandas`）承载该类 sinks，并满足：

- 默认入口 `scalim.sinks` 的 `__all__` MUST NOT 直接导出 pandas sinks 等可选依赖 sinks。
- 显式子模块（例如 `scalim.sinks.pandas`）MUST 存在并可导入，用于承载相关 sinks 类型。

#### Scenario: optional sinks are not exported from default facade
- **WHEN** 调用方执行 `from scalim.sinks import PandasRowSink`
- **THEN** 该导入 MUST 失败（符号不在 `scalim.sinks` 默认导出面中）
- **AND** 调用方 MUST 能通过显式子模块导入（例如 `from scalim.sinks.pandas import PandasRowSink`）
