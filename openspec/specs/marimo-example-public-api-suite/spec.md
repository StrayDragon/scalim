# marimo-example-public-api-suite Specification

## Purpose
TBD - created by archiving change c16-demo-big-data-report-yaml-mainline. Update Purpose after archive.
## Requirements
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

### Requirement: public API suite MUST cover curated facade imports

系统 MUST 扩展 public API suite，使其覆盖 curated public surface，而不只是零散的 `__all__` 冒烟。

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

### Requirement: public API suite MUST stay consistent with the public API manifest

系统 MUST 将 public API suite 与 public API manifest 视为同一份“稳定公开面 SSOT”的两个投影：
- manifest 表达“允许的公开入口与导出面”
- suite 通过可运行示例与 `__all__` 覆盖断言表达“可用且可回归”

两者 MUST 保持一致：
- suite 覆盖的稳定公开入口集合 MUST 与 manifest 对齐
- suite 中的导入示例 MUST 仅使用 manifest 的 curated entrypoints

#### Scenario: manifest/suite drift is rejected
- **WHEN** suite 覆盖集合与 manifest 不一致（缺失/新增模块或导出）
- **THEN** gate MUST fail-fast 并指出差异
