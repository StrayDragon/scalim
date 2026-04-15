# observer-concurrency-contract (delta) Specification

## ADDED Requirements

### Requirement: workflow capture+replay MUST summarize loader_call payloads
当 workflow 以并发模式执行（例如 `max_concurrency>1`）且启用 components（observers/hooks）导致进入 capture+replay 路径时，系统 MUST 避免在捕获队列中保活 `loader_call` 的完整 loader result：

- 对 observer 事件 `EVENT_LOADER_CALL`：
  - 系统 MUST 使用 `summary` 级别的 loader result payload（例如 `{type: <T>, size?: <N>}`），而不是完整 mapping/list。
  - 系统 MUST NOT 在捕获队列中保留对完整 loader result 的强引用（避免延长生命周期到 replay/commit）。
- 对 typed hook 的 `loader_call`（例如 `HookCaptureManager.trigger_loader_call(...)` 捕获的记录）：
  - 系统 MUST 同样使用 `summary` 级别的 loader result payload（或等价的轻量结构）。

该要求仅约束“capture+replay 捕获阶段的 payload 形态”，不改变执行正确性，也不要求串行模式下改变原有事件 payload。

#### Scenario: observer loader_call payload is summarized under workflow concurrency
- **GIVEN** workflow 以 `max_concurrency=2` 运行且注册了订阅 `EVENT_LOADER_CALL` 的 observer
- **WHEN** 某个 loader 返回一个大 mapping/list 结果并触发 `EVENT_LOADER_CALL`
- **THEN** 被 capture 的 `EVENT_LOADER_CALL.payload.result` MUST 为 `summary` 结构（例如包含 `type` 且可选包含 `size`）
- **AND** 该 payload MUST NOT 等于完整 loader result 对象（不得把 mapping/list 作为事件 result 直接保留在捕获队列中）

#### Scenario: typed hook loader_call payload is summarized under workflow concurrency
- **GIVEN** workflow 以 `max_concurrency=2` 运行且注册了订阅 loader_call 的 typed hook
- **WHEN** 某个 loader 返回一个大 mapping/list 结果并触发 typed loader_call hook
- **THEN** 被 capture 的 typed hook `loader_call` 记录中 `result` MUST 为 `summary` 结构（例如包含 `type` 且可选包含 `size`）

