# marimo-example-public-api-suite Specification

## ADDED Requirements

### Requirement: public API suite MUST cover `events.type_groups` and `sinks.pandas` via stable facades
public API suite MUST 补齐 Tier1 curated entrypoints 的缺口覆盖，并将其纳入 `just examples` 的确定性回归范围：

- `scalim.events.type_groups`（事件类型分组视图）
- `scalim.sinks.pandas`（可选依赖 pandas sinks 门面）

覆盖 MUST 以“稳定 facade 导入 + 最小可运行闭环 + oracle 断言”的章节形式存在。

#### Scenario: type_groups is exercised in the suite
- **WHEN** 开发者运行 `just examples`
- **THEN** suite MUST 执行一个覆盖 `scalim.events.type_groups` 的章节/用例
- **AND** 该章节/用例 MUST 通过并输出可定位 summary

#### Scenario: pandas sinks are exercised in the suite
- **WHEN** 开发者运行 `just examples`
- **THEN** suite MUST 执行一个覆盖 `scalim.sinks.pandas` 的章节/用例
- **AND** 该章节/用例 MUST 在缺失 pandas 依赖时 fail-fast 给出明确提示（或在 dev 依赖中确保 pandas 可用）

### Requirement: a static gate MUST reject drift between Tier1 curated entrypoints and suite/pytest coverage
系统 MUST 提供一个静态治理 gate（`scripts/check-*.py --check` 形式），用于检测并拒绝以下漂移：

- Tier1 curated entrypoints 集合发生变化，但 `example_public_api_suite` 未同步补齐覆盖
- pytest public_api suite 覆盖集合与 examples 覆盖集合不一致（至少在 Tier1 范围内）

该 gate MUST 输出缺失/新增模块列表，并提供可操作的修复建议（新增章节/更新 pytest 章节选择）。

#### Scenario: adding a tier1 entrypoint without examples coverage is rejected
- **GIVEN** 贡献者新增/修改了 Tier1 marker
- **WHEN** 对应入口模块未被 `example_public_api_suite` 覆盖
- **THEN** gate MUST fail-fast 并指出缺失模块

#### Scenario: pytest and examples drift is rejected
- **GIVEN** examples suite 覆盖了某个 Tier1 入口模块
- **WHEN** pytest public_api suite 未覆盖该入口模块（直接或通过执行章节间接覆盖）
- **THEN** gate MUST fail-fast 并指出差异集合

