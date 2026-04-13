# exception-chain-convention Specification

## Purpose
TBD - created by archiving change c10-fix-exception-chain-consistency. Update Purpose after archive.
## Requirements
### Requirement: `src/scalim/` 内 `raise ... from` 异常链规范

在 `src/scalim/` 中，将捕获的异常重新包装为另一异常时，默认 MUST 使用 `from exc`（或等价的显式 cause）以保留异常链与根因诊断信息。

仅在公共 API 边界且显式需要向调用方隐藏第三方或内部实现细节时 MAY 使用 `from None`；每一处 `from None` MUST 附带相邻注释说明抑制链的原因与适用边界（例如 YAML 解析边界隐藏解析器内部栈）。

内部配置/编译路径（例如将 `ValueError` / `TypeError` 包装为 `ScalimWorkflowConfigError`）MUST 使用 `from exc`，除非该路径属于上述已文档化的 API 边界例外。

#### Scenario: 内部错误包装保留链

- **WHEN** 代码在 `src/scalim/` 内捕获异常 `exc` 并抛出包装后的领域异常
- **AND** 该路径不属于已注释说明的允许 `from None` 的 API 边界
- **THEN** `raise` MUST 使用 `from exc`

#### Scenario: 允许的 `from None` 具备理由

- **WHEN** 代码使用 `raise ... from None`
- **THEN** 相邻注释 MUST 说明为何在此边界抑制 cause 链

