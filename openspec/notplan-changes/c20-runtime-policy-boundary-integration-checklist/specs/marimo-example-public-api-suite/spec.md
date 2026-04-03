## ADDED Requirements

### Requirement: user-entry smoke coverage MUST exist for runtime-policy boundary regressions

当某个 runtime-only policy 的错误可能通过 `run_workflow(...)`、public API example 或 notebook 示例暴露给用户时，系统 MUST 在用户侧入口保留至少一条 smoke coverage，用于验证真实入口没有绕过底层边界修复。

#### Scenario: public API example exercises a runtime-policy boundary
- **WHEN** 某个 runtime-only policy 既影响底层 compile/runtime 行为，也影响用户可直接调用的 public API 入口
- **THEN** review 文档 MUST 指出至少一个 notebook / public API smoke 入口
- **AND** 该 smoke 入口 MUST 被设计为最小 fixture + 明确 oracle，而不是依赖偶然覆盖

### Requirement: user-entry smoke MUST complement lower-layer tests rather than replace them

notebook / public API smoke coverage MUST 作为补充层存在，不能替代 compile / runtime / workflow 层的定向测试。

#### Scenario: review distinguishes smoke from branch coverage
- **WHEN** 维护者为 runtime-policy boundary 问题补充用户侧 smoke
- **THEN** review 文档 MUST 同时说明下层定向测试的职责
- **AND** MUST NOT 把 notebook / public API smoke 视为唯一回归保障
