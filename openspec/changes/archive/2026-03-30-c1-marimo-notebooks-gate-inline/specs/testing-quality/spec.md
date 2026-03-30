## REMOVED Requirements

### Requirement: `just examples` 入口收敛为 `notebooks/marimo/run_examples.py`
**Reason**: examples gate 不再依赖仓库内固定脚本路径；runner 迁移为 `justfile` 内联实现以降低耦合并支持自动发现与并行策略。

**Migration**: 使用 `just examples`（`justfile` 内联 headless runner）执行示例对拍；不要再运行 `python notebooks/marimo/run_examples.py`。

## ADDED Requirements

### Requirement: `just examples` 入口收敛为 `justfile` 内联 headless runner
系统 MUST 将 `just examples` 的执行入口收敛为 `justfile` 内联的 headless runner,并使其覆盖:

- `demo_big_data_report` 的示例/对拍（YAML DSL 主线教程 + IR 回归章节）
- public API suite 的示例/对拍（`__all__` 覆盖断言 + 扩展点演示）

该 runner MUST 自动发现并执行 `notebooks/marimo/` 下的 suites 与章节集合,并输出可定位的 PASS/FAIL 与章节级 summary.

#### Scenario: `just examples` 统一入口覆盖示例套件
- **WHEN** 开发者运行 `just examples`
- **THEN** 系统 MUST 执行 `justfile` 内联的 headless runner
- **AND** 该 runner MUST 覆盖上述示例套件的全部回归点
- **AND** 当存在失败时,进程退出码 MUST 非零

## MODIFIED Requirements

### Requirement: `demo_big_data_report` 覆盖 workflow YAML 的可运行对拍
系统 MUST 在 `demo_big_data_report` 主线中提供至少一个 deterministic 的 workflow YAML 示例,并将其纳入 `just examples` 的对拍回归范围。

该 workflow 示例 MUST 至少覆盖:
- `scalim.dsl.by_yaml.run_workflow(...)` 的运行入口
- 启用 `workflow.options.cache_pool` 的共享 `preload_forever` 行为(需可对拍/可断言)

#### Scenario: workflow 示例在 examples gate 中通过
- **WHEN** 开发者运行 `just examples`
- **THEN** workflow 示例 MUST 被执行
- **AND** 示例 MUST 通过对拍验证并返回稳定 summary(失败时可定位到章节/用例上下文)

### Requirement: `demo_big_data_report` 覆盖派生聚合 set 口径的可对拍边界
系统 MUST 在 `demo_big_data_report` 主线中提供至少一个示例,覆盖派生聚合 set 口径的关键原语与护栏边界,并可在 CI 中稳定回归。

该示例 SHOULD 覆盖(至少其一):
- `dedup_by`
- `two_stage_group_by`
- `count_distinct` 的 `max_distinct` / `distinct_on_overflow`

#### Scenario: 派生聚合示例在 examples gate 中通过
- **WHEN** 开发者运行 `just examples`
- **THEN** 派生聚合示例 MUST 被执行
- **AND** 示例 MUST 通过对拍验证且结果确定(输出顺序/数值口径稳定)

### Requirement: marimo_coverage.gen.md 作为可检查的 examples coverage 报告
系统 MUST 提供 `notebooks/marimo/marimo_coverage.gen.md` 作为 SSOT,用于将 `notebooks/marimo/` 下的示例套件回归点映射到:

- Marimo notebooks(教学入口)
- notebooks 侧 SSOT 入口/实现文件（执行真相）
- headless gate(`just examples`)与 pytest 复用点(如存在)
- canonical YAML fixtures 与其 schema 绑定(至少 demand/workflow 两类 schema)

该 coverage 报告 MUST 由脚本 `scripts/gen-marimo-coverage.py` 生成,不得手工维护.

#### Scenario: coverage 报告存在且可再生
- **WHEN** 维护者检查 `notebooks/marimo/` 目录
- **THEN** MUST 存在 `notebooks/marimo/marimo_coverage.gen.md`
- **AND** 运行 `just gen-marimo-coverage` MUST 能稳定生成相同内容
- **AND** 运行 `just marimo-coverage-drift-check` MUST 在无漂移时返回 0

