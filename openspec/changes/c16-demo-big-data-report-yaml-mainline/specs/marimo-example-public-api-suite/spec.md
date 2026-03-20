## ADDED Requirements

### Requirement: public API 覆盖必须迁移为独立 suite 并纳入 examples gate
系统 MUST 将稳定公开入口模块 `__all__` 的覆盖回归从 `demo_big_data_report` 主线教学套件中解耦，迁移为独立示例套件（suite），并保持确定性回归门禁不降级。

该 suite MUST：

- 位于 `notebooks/marimo/` 下的独立目录（例如 `notebooks/marimo/example_public_api_suite/`）
- 为每个稳定公开入口模块提供至少一个纳入 gate 的章节入口（章节对 `__all__` 做 fail-fast 覆盖断言）
- 至少包含一个章节演示扩展点（hook/observer/events/components 注入）

#### Scenario: public API suite 与主线解耦
- **WHEN** 维护者检查 `notebooks/marimo/`
- **THEN** MUST 能找到一个独立于 `demo_big_data_report/` 的 public API suite 目录

### Requirement: headless runner 必须覆盖 public API suite
系统 MUST 更新 `notebooks/marimo/run_examples.py`，使其默认执行：

- `demo_big_data_report`（YAML DSL 主线教学 + 场景化对拍）
- public API suite（`__all__` 覆盖 + 扩展点演示）

#### Scenario: `just examples` 覆盖 public API suite
- **WHEN** 开发者运行 `just examples`（或等价 `python notebooks/marimo/run_examples.py`）
- **THEN** runner MUST 执行 public API suite 的章节
- **AND** public API suite MUST 通过并输出可定位 summary

