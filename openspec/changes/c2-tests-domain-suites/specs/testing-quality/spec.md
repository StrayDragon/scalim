## ADDED Requirements

### Requirement: pytest MUST cover the public API catalog via a dedicated public_api suite
系统 MUST 在 pytest 非 bench 套件中提供一个专用的 `public_api` domain suite,用于从用户使用视角覆盖 public API catalog 与核心链路 API 的最小闭环回归.

该 suite MUST 至少覆盖:
- catalog 中模块的稳定导入（import smoke）
- catalog 中模块的 `__all__` 可解析（避免意外导出/导出破坏）
- 最小运行闭环（例如 `compile/run/run_workflow`、`PlanBuilder`、`ScalimEngine`、`Observability`、`events/sinks` 的基本用法）

#### Scenario: public API catalog is covered in pytest non-bench gates
- **WHEN** 开发者运行默认 pytest 非 bench 套件
- **THEN** `public_api` suite MUST 被收集并执行
- **AND** suite MUST 覆盖 public API catalog 的最小闭环并通过

### Requirement: examples gate and pytest public_api suite MUST both cover the public API catalog
系统 MUST 同时通过两条链路覆盖 public API catalog:
- `just examples`（public API suite 的示例/对拍）
- pytest `tests/public_api/`（用户侧最小闭环回归）

两者 MUST 覆盖同一份 public API catalog;若存在缺失/新增导致覆盖集合不一致,系统 MUST fail-fast 并输出差异.

#### Scenario: drift between examples and pytest public_api coverage is rejected
- **GIVEN** public API catalog 发生变化（新增/删除/重命名模块或导出）
- **WHEN** 维护者运行 `just examples` 与默认 pytest 非 bench 套件
- **THEN** 系统 MUST 检测到覆盖集合差异并 fail-fast
- **AND** 错误信息 MUST 指出缺失/新增的模块集合（或导出集合）
