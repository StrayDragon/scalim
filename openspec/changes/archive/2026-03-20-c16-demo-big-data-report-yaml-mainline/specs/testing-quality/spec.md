## MODIFIED Requirements

### Requirement: 稳定公开入口模块 `__all__` 必须被 examples gate 100% 覆盖
系统 MUST 将以下稳定公开入口模块的 `__all__` 视为“面向框架用户的公开 API 覆盖清单”，并在 `notebooks/marimo/` 下的 **独立 public API suite** 中提供 deterministic 的最小可运行示例以覆盖其全部导出符号：

- `scalim.dsl.by_yaml`
- `scalim.spec.ir`
- `scalim.planning`
- `scalim.execution`
- `scalim.ob`

覆盖要求：

- 每个入口模块 MUST 至少对应一个纳入 `just examples` 的章节 notebook。
- 每个章节 MUST 在执行时对其覆盖清单做断言：当模块 `__all__` 增加新符号而章节未更新时，该章节 MUST fail-fast 并给出可定位 summary（提示缺失符号集合）。
- 系统 MUST 额外提供至少一个章节演示扩展点（例如 hook/observer/events 或 `components` 注入），并将其纳入 `just examples` 的回归范围。

#### Scenario: `__all__` 新增符号但未被章节覆盖时 fail-fast
- **GIVEN** 某稳定入口模块的 `__all__` 增加了新符号
- **WHEN** 开发者运行 `just examples`
- **THEN** 对应公开入口覆盖章节 MUST 失败并报告缺失符号集合

### Requirement: `just examples` 入口收敛为 `notebooks/marimo/run_examples.py`
系统 MUST 将 `just examples` 的执行入口收敛为单一脚本 `notebooks/marimo/run_examples.py`,并使其覆盖:

- `demo_big_data_report` 的示例/对拍（YAML DSL 主线教程 + 场景化回归）
- public API suite 的示例/对拍（`__all__` 覆盖断言 + 扩展点演示）

#### Scenario: `just examples` 统一入口覆盖示例套件
- **WHEN** 开发者运行 `just examples`
- **THEN** 系统 MUST 执行 `notebooks/marimo/run_examples.py`
- **AND** 该 runner MUST 覆盖上述示例套件的全部回归点

