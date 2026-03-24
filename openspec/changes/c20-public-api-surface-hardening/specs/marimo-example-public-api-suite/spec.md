## ADDED Requirements

### Requirement: public API suite MUST cover curated facade imports

系统 MUST 扩展 public API suite，使其覆盖本轮确认的 curated public surface，而不只是零散的 `__all__` 冒烟。

该 suite 至少 MUST 覆盖：

- `scalim.dsl.by_yaml` 的 facade imports
- workflow 辅助公开模块（`workflow` / `workflow_types` / `workflow_paths`）
- `scalim.spec.ir`

#### Scenario: public API suite exercises curated public imports
- **WHEN** 开发者运行 public API suite
- **THEN** suite MUST 对 curated public surface 做稳定导入断言
- **AND** 这些断言 MUST 与公共表面白名单保持一致

### Requirement: public API suite MUST guard against internal-path drift

系统 MUST 通过 suite、辅助检查或等价 gate 防止内部实现路径重新出现在教学示例与公开入口覆盖中。

#### Scenario: suite detects drift back to internal imports
- **WHEN** 面向用户的示例或 suite 章节重新引用内部实现路径作为官方用法
- **THEN** 对应 gate MUST 失败或给出明确回归提示
