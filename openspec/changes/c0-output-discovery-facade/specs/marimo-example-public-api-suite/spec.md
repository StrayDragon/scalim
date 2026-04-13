# marimo-example-public-api-suite (delta) Specification

## MODIFIED Requirements

### Requirement: public API suite MUST cover curated facade imports

系统 MUST 扩展 public API suite，使其覆盖 curated public surface，而不只是零散的 `__all__` 冒烟。

该 suite 至少 MUST 覆盖：

- `scalim.dsl.yaml_dsl` 的 facade imports
- workflow 辅助公开模块（`workflow` / `workflow_types` / `workflow_paths`）
- `scalim.spec.ir`
- `scalim.shortcuts.resources`（资源类 shortcut 稳定入口 package）
- `scalim.shortcuts.resources.outputs`（输出发现/最新产物定位 facade）

#### Scenario: public API suite exercises curated public imports
- **WHEN** 开发者运行 public API suite
- **THEN** suite MUST 对 curated public surface 做稳定导入断言
- **AND** 这些断言 MUST 与公共表面白名单保持一致
