## ADDED Requirements

### Requirement: removed internal modules MUST be blocked from reappearing in user-facing materials

系统 MUST 将 `scalim.vendor.literich` 视为已移除的内部实现模块，并通过用户材料门禁阻止其再次出现在用户可见材料中（docs / skills / notebooks）。

#### Scenario: user-material import boundary gate rejects scalim.vendor.literich
- **GIVEN** 任一用户材料文件（docs/skills/notebooks）包含文本 `scalim.vendor.literich`
- **WHEN** 维护者运行 `scripts/check-user-material-import-boundaries.py --check`
- **THEN** gate MUST fail-fast 并提示移除该导入/引用

### Requirement: runtime code MUST NOT depend on non-cataloged console renderers

系统 MUST 禁止将仅用于“漂亮输出”的渲染器当作运行时依赖或事实公共契约扩散。

具体而言：当某模块仅用于 console 展示且不在 public API curated 入口中，系统 SHOULD 将其实现放在 internal 边界内并允许被移除；本变更中 `scalim.vendor.literich` 即为该类模块并被移除。

#### Scenario: removing a console renderer is treated as breaking and does not require compatibility
- **WHEN** 维护者移除 `scalim.vendor.literich`
- **THEN** 该变更 MUST 被视为 BREAKING（不提供兼容层/弃用期）
- **AND** 代码库中的引用 MUST 被一次性升级到新的 dependency-free console 输出方案
