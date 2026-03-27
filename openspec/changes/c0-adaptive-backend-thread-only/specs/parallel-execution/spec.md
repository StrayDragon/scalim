## MODIFIED Requirements

### Requirement: backend 选择为高级 opt-in 且同次运行保持一致
系统 MUST 默认 thread backend。
系统 MUST 保留对 process/async backend 的“选择接口形状”(例如 policy 常量/返回值),但在当前裁剪版本中,process/async backend MUST NOT 被实际启用。

系统 MUST 在创建 adaptive pool/executor 时确定 backend,并在同一次运行内复用该 backend(例如缓存于 runtime),调度器不得按层反复改选 backend。

#### Scenario: backend 决策单次复用
- **GIVEN** policy 的 `choose_backend` 多次调用可能返回不同值
- **WHEN** 一次运行创建并执行 adaptive pool
- **THEN** 实际执行 backend MUST 在本次运行内保持一致

#### Scenario: 选择未实现 backend 失败
- **WHEN** policy 选择 process 或 async backend
- **THEN** 系统 MUST 立即失败并明确指出“该 backend 已被裁剪,当前仅支持 thread”
- **AND** 错误信息 MUST 指引“如需回加请恢复对应实现模块与测试”

## REMOVED Requirements

### Requirement: process/async backend 需明确 guardrails 与失败语义
**Reason**：process/async backend 的实现已被裁剪,该要求描述的 guardrails 与运行时语义不再适用。

**Migration**：使用默认的 thread backend(或显式选择 thread)。若确有 process/async 需求,需在代码库中恢复对应实现模块与测试后再启用。

