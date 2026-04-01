# yaml-dsl-imports Delta Specification (c0-yaml-dsl-surface-consolidation)

## ADDED Requirements

### Requirement: imports/$import support matrix MUST be explicit and enforceable

系统 MUST 明确并可校验地表达 imports/$import 的支持矩阵，避免 “schema 暴露但 runtime 不支持” 的漂移：

- demand v1：支持 `imports` + `$import`（仅文件路径入口展开）
- workflow v1：不支持 `$import`（除非明确实现并提供一致性门禁）
- vNext：MUST 进一步收敛 `$import` 的可用范围（见下一条 requirement）

#### Scenario: workflow rejects imports/$import with actionable hint
- **WHEN** 用户在 workflow YAML 中使用 `$import`
- **THEN** 校验 MUST 失败
- **AND** 错误信息 MUST 明确指出 workflow 不支持 imports/$import，并给出替代路径（显式写出 mapping 或 Python overrides/profile）

### Requirement: vNext MUST restrict $import to a small stable set of mapping nodes

为避免 overlay 语义扩散，vNext MUST 将 `$import` 的允许范围收敛到少数稳定的“纯建模 mapping 节点”，并禁止在运行时策略/诊断/治理区域使用 `$import`。

至少 MUST 禁止在以下区域使用 `$import`：
- `resources.*`
- `outputs[*].write`（若仍存在）
- `retry.*` / `guardrails.*` / `observability.*`
- workflow 任意节点（除非 workflow 明确引入 imports expansion 并具备 drift gate）

#### Scenario: vNext rejects $import under resources
- **WHEN** vNext demand YAML 在 `resources.books`（或其子节点）出现 `$import`
- **THEN** 校验 MUST 失败并指出 `$import` 在该区域已被收敛禁用

