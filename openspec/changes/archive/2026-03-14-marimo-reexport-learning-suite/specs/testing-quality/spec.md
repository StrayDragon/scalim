## ADDED Requirements

### Requirement: `notebooks/marimo/` 提供以稳定 re-export 入口为索引的 `example_public_api` 套件
系统 MUST 在 `notebooks/marimo/` 下提供 `example_public_api` 套件,用于面向框架用户展示与回归以下稳定入口模块(以其 `__all__` 为覆盖清单来源):

- `scalim.dsl.by_yaml`
- `scalim.spec.ir`
- `scalim.planning`
- `scalim.execution`
- `scalim.ob`

`example_public_api` MUST 至少包含:

- 一份“主线串联” notebook,用于说明如何运行示例/如何阅读覆盖矩阵/如何定位失败
- 每个稳定入口模块至少一份 notebook,覆盖其 `__all__` 导出符号的最小可运行用法与关键边界说明

#### Scenario: `example_public_api` 目录存在且可发现
- **WHEN** 维护者检查 `notebooks/marimo/` 目录
- **THEN** 目录下 MUST 存在 `notebooks/marimo/example_public_api/`
- **AND** 该目录下 MUST 存在一份主线 notebook 与每个稳定入口模块对应的 notebook

### Requirement: `example_public_api` 的示例执行与对拍不依赖 marimo UI
系统 MUST 将 `example_public_api` 的可运行示例与对拍逻辑下沉到 `packages/scalim-misc/`,并提供一个 headless runner 供 `just examples` 与 pytest 复用:

- runner MUST 不依赖 marimo UI
- runner MUST 为每个章节输出 PASS/FAIL 与可定位的 summary
- 底层实现 MUST 组织在 `packages/scalim-misc/src/scalim_misc/examples/` 下,专门承接 `notebooks/marimo/example_*` 的可复用逻辑

#### Scenario: runner 可在 CI 中执行并给出可定位输出
- **WHEN** 开发者运行 `just examples`(或等价入口)
- **THEN** runner MUST 执行 `example_public_api` 的章节并输出章节级 PASS/FAIL
- **AND** 当存在失败时,输出 MUST 包含可定位的章节 id 与失败摘要

### Requirement: 产物/数据输出示例必须提供 deterministic oracle
当 `example_public_api` 的某个章节产生数据结果或文件产物时,系统 MUST 提供 deterministic oracle 用于对拍:

- oracle MUST 优先通过运行时计算得到 expected(小数据确定性)
- 当需要固化 expected fixtures 时,必须在章节或测试中明确其来源与更新策略
- 当使用“大但固定”的 expected fixtures 时,fixtures MUST 存放在 `packages/scalim-misc/**/fixtures/` 下(由 runner/测试引用),避免散落在 `tests/fixtures/`

#### Scenario: 产物章节的 oracle 可稳定对拍
- **WHEN** 在 pytest 中运行该章节的回归用例
- **THEN** oracle 对拍 MUST 通过且结果确定(顺序与数值口径稳定)

### Requirement: `just examples` 入口收敛为 `notebooks/marimo/run_examples.py`
系统 MUST 将 `just examples` 的执行入口收敛为单一脚本 `notebooks/marimo/run_examples.py`,并使其覆盖:

- `demo_big_data_report` 的示例/对拍
- `example_public_api` 的示例/对拍

#### Scenario: `just examples` 统一入口覆盖两类示例
- **WHEN** 开发者运行 `just examples`
- **THEN** 系统 MUST 执行 `notebooks/marimo/run_examples.py`
- **AND** 该 runner MUST 同时覆盖 `demo_big_data_report` 与 `example_public_api` 的回归点

### Requirement: `demo_big_data_report` 覆盖 workflow YAML 的可运行对拍
系统 MUST 在 `demo_big_data_report` 主线中提供至少一个 deterministic 的 workflow YAML 示例,并将其纳入 `just examples` 的对拍回归范围。

该 workflow 示例 MUST 至少覆盖:
- `scalim.dsl.by_yaml.run_workflow(...)` 的运行入口
- `workflow.options.share_preload_cache=true` 的共享 `preload_forever` 行为(需可对拍/可断言)

#### Scenario: workflow 示例在 examples gate 中通过
- **WHEN** 开发者运行 `just examples`(或等价 `notebooks/marimo/run_examples.py`)
- **THEN** workflow 示例 MUST 被执行
- **AND** 示例 MUST 通过对拍验证并返回稳定 summary(失败时可定位到章节/用例上下文)

### Requirement: `demo_big_data_report` 覆盖派生聚合 set 口径的可对拍边界
系统 MUST 在 `demo_big_data_report` 主线中提供至少一个示例,覆盖派生聚合 set 口径的关键原语与护栏边界,并可在 CI 中稳定回归。

该示例 SHOULD 覆盖(至少其一):
- `dedup_by`
- `two_stage_group_by`
- `count_distinct` 的 `max_distinct` / `distinct_on_overflow`

#### Scenario: 派生聚合示例在 examples gate 中通过
- **WHEN** 开发者运行 `just examples`(或等价 `notebooks/marimo/run_examples.py`)
- **THEN** 派生聚合示例 MUST 被执行
- **AND** 示例 MUST 通过对拍验证且结果确定(输出顺序/数值口径稳定)

### Requirement: coverage_matrix.md 作为可检查的“用户功能组合覆盖(cov)”口径
系统 MUST 提供 `notebooks/marimo/coverage_matrix.md` 作为 SSOT,用于把“公开入口 + YAML DSL 能力清单”映射到具体回归点:

- MUST 覆盖上述 5 个稳定入口模块(至少列出模块名与对应 notebook/章节/回归点)
- MUST 覆盖 YAML DSL 的两套 schema 能力清单:
  - demand YAML(`demand.gen.json`)
  - workflow YAML(`workflow.gen.json`)
- MUST 能表达“组合覆盖(cov)”(例如近期归档变更引入的关键组合场景)与其对应回归点

#### Scenario: coverage_matrix.md 存在并包含入口清单
- **WHEN** 维护者检查 `notebooks/marimo/` 目录
- **THEN** MUST 存在 `notebooks/marimo/coverage_matrix.md`
- **AND** 该文件 MUST 明确列出 5 个稳定入口模块与 demand/workflow 能力清单的覆盖映射
