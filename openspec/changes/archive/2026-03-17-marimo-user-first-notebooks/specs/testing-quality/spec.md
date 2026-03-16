## ADDED Requirements

### Requirement: 稳定公开入口模块 `__all__` 必须被 examples gate 100% 覆盖
系统 MUST 将以下稳定公开入口模块的 `__all__` 视为“面向框架用户的公开 API 覆盖清单”，并在 `notebooks/marimo/demo_big_data_report/chapters/` 的主线章节中提供 deterministic 的最小可运行示例以覆盖其全部导出符号：

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

## MODIFIED Requirements

### Requirement: 产物/数据输出示例必须提供 deterministic oracle
当纳入 `just examples` 的某个章节产生数据结果或文件产物时,系统 MUST 提供 deterministic oracle 用于对拍:

- oracle MUST 优先通过运行时计算得到 expected(小数据确定性)
- 当需要固化 expected fixtures 时,必须在章节或测试中明确其来源与更新策略
- 当使用“大但固定”的 expected fixtures 时,fixtures MUST 存放在 `packages/scalim-misc/**/fixtures/` 下(由 runner/测试引用),避免散落在 `tests/fixtures/`

#### Scenario: 产物章节的 oracle 可稳定对拍
- **WHEN** 在 pytest 中运行该章节的回归用例
- **THEN** oracle 对拍 MUST 通过且结果确定(顺序与数值口径稳定)

### Requirement: `just examples` 入口收敛为 `notebooks/marimo/run_examples.py`
系统 MUST 将 `just examples` 的执行入口收敛为单一脚本 `notebooks/marimo/run_examples.py`,并使其覆盖:

- `demo_big_data_report` 的示例/对拍（包括其集成的公开入口覆盖章节与扩展点演示）

#### Scenario: `just examples` 统一入口覆盖主线示例
- **WHEN** 开发者运行 `just examples`
- **THEN** 系统 MUST 执行 `notebooks/marimo/run_examples.py`
- **AND** 该 runner MUST 覆盖 `demo_big_data_report` 的全部回归点

### Requirement: marimo_coverage.gen.md 作为可检查的 examples coverage 报告
系统 MUST 提供 `notebooks/marimo/marimo_coverage.gen.md` 作为 SSOT,用于将 `notebooks/marimo/` 下的示例套件回归点映射到:

- Marimo notebooks(教学入口)
- notebooks 侧 SSOT 入口/实现文件（执行真相）
- headless runner(`notebooks/marimo/run_examples.py`)与 pytest 复用点(如存在)
- canonical YAML fixtures 与其 schema 绑定(至少 demand/workflow 两类 schema)

该 coverage 报告 MUST 由脚本 `scripts/gen-marimo-coverage.py` 生成,不得手工维护.

#### Scenario: coverage 报告存在且可再生
- **WHEN** 维护者检查 `notebooks/marimo/` 目录
- **THEN** MUST 存在 `notebooks/marimo/marimo_coverage.gen.md`
- **AND** 运行 `just gen-marimo-coverage` MUST 能稳定生成相同内容
- **AND** 运行 `just marimo-coverage-drift-check` MUST 在无漂移时返回 0

## REMOVED Requirements

### Requirement: `notebooks/marimo/` 提供以稳定 re-export 入口为索引的 `example_public_api` 套件
**Reason**: 本变更将公开入口覆盖并入主线章节并删除独立套件目录，以避免教学路径割裂与“双套件治理成本”。

**Migration**: 将 `notebooks/marimo/example_public_api/` 的每个入口模块示例迁移为 `demo_big_data_report` 的主线章节，并确保其按 `__all__` 做 100% 覆盖断言；同时更新 runner/pytest/coverage 报告与 docs/spec 引用。

### Requirement: `example_public_api` 的示例执行与对拍不依赖 marimo UI
**Reason**: 本变更允许 headless gate/pytest 直接 import notebook/marimo 代码以复用同源 SSOT；不再强制将公开入口示例 SSOT 下沉到 `packages/scalim-misc`。

**Migration**: 将 `packages/scalim-misc/src/scalim_misc/examples/public_api/*` 的示例主流程迁移为 notebooks 侧 SSOT 入口（或 notebooks 侧纯 Python 支撑模块），runner/pytest 改为导入 notebooks 侧入口执行；`packages/scalim-misc` 仅保留 fixtures/oracle/工具函数与 YAML allowlist 所需 loader。

