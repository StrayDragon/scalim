# module-organization (delta) Specification

## ADDED Requirements

### Requirement: `# noqa: C901` hotspots MUST be decomposed into named, testable boundaries

当核心热点函数因复杂度门禁（C901）被 `# noqa: C901` 放行时，系统 MUST 将其视为治理对象，并满足：

- 维护者 MUST 优先通过“纯函数/规则函数提取”降低复杂度，而不是仅增加 `noqa` 或在长函数中继续堆叠分支
- 被提取的规则函数 MUST 具备明确输入输出，并可通过单元测试覆盖其分支矩阵
- `# noqa: C901` SHOULD 作为阶段性措施；每个放行点 SHOULD 有对应的治理任务（在 change/tasks 中可追踪）
- 新增或保留 `# noqa: C901` 时，维护者 MUST 同时标注可追踪的拆分计划引用（例如 `# pragma: allow-c901 plan: <ref>`），避免匿名/永久放行

#### Scenario: rules extracted from a C901 function are unit-testable
- **GIVEN** 某个热点函数包含多个 `on_mismatch` / alignment / budget 等规则分支
- **WHEN** 维护者治理该热点
- **THEN** 规则决策 MUST 被提取到可单测的函数（例如返回 action=error/warn/skip）
- **AND** 单元测试 MUST 覆盖主要分支组合
