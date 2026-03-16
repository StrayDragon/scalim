## ADDED Requirements

### Requirement: `demo_big_data_report` 章节 notebooks 作为 SSOT 并可对拍回归
系统 MUST 将 `demo_big_data_report` 的每个纳入 examples gate 的章节 notebook 同时视为教学入口与 SSOT 执行入口：

- 每个章节 notebook MUST 提供一个可被导入调用的 SSOT 入口函数（例如 `run_<chapter_id>()` 或 `run()`），用于执行 deterministic 对拍回归。
- `notebooks/marimo/run_examples.py` 与 pytest MUST 复用该入口执行该章节的对拍回归（不得再通过 `packages/scalim-misc` 的章节实现作为唯一真相来源）。

#### Scenario: chapter SSOT 入口可被 headless runner 调用
- **WHEN** `notebooks/marimo/run_examples.py` 运行 `demo_big_data_report` 的某个章节
- **THEN** runner MUST 通过导入该章节 notebook 的 SSOT 入口函数来执行
- **AND** runner MUST 输出可定位的 PASS/FAIL 与章节级 summary

## MODIFIED Requirements

### Requirement: `demo_big_data_report` 提供章节化 Marimo notebooks
系统 MUST 在 `notebooks/marimo/demo_big_data_report/` 下提供 `chapters/` 目录,并为主线 demo 的每个 SSOT 章节提供一份对应的 Marimo notebook.

初始章节集合 MUST 至少覆盖以下 `chapter_id`:
- `basics`
- `yaml_dsl`
- `workflow_yaml`
- `sinks`
- `memory_opt`
- `observability`
- `parallel_mode`
- `diagnostics`
- `guardrails`
- `loader_retry`
- `output_composition`
- `derived_set_aggregations`

并额外覆盖稳定公开入口模块的教学/回归章节(以其 `__all__` 为覆盖清单来源):
- `public_api_dsl_by_yaml`
- `public_api_spec_ir`
- `public_api_planning`
- `public_api_execution`
- `public_api_ob`
- `public_api_hooks_events`

章节 notebook 文件名 MUST 以 `<chapter_id>.py` 结尾,且 MAY 额外包含有序前缀(例如 `01_`),用于稳定排序与导航.

#### Scenario: 章节 notebooks 存在
- **WHEN** 维护者检查 `notebooks/marimo/demo_big_data_report/chapters/` 的文件集合
- **THEN** 上述每个 `chapter_id` 都存在至少一份以 `<chapter_id>.py` 结尾的 notebook 文件

### Requirement: `demo_main.py` 保持为 hub/index 入口并可一键跑完章节
系统 MUST 保持 `notebooks/marimo/demo_big_data_report/demo_main.py` 为 `demo_big_data_report` 的 Marimo hub/index 入口.

`demo_main.py` MUST 提供:
- 一键执行全部章节(通过 `demo_big_data_report` 的章节 registry `run_all_chapters(...)`)
- 对章节结果的汇总展示(至少包含每章 `chapter_id/passed/summary`)
- 指向 `chapters/` 内各章节 notebook 的导航信息

#### Scenario: hub 可发现并可汇总
- **WHEN** 读者打开 `notebooks/marimo/demo_big_data_report/demo_main.py`
- **THEN** 能看到章节列表/导航
- **AND** 能运行全部章节并获得汇总结果

### Requirement: notebook-support helpers 必须 headless 且不依赖 marimo
当引入 notebook 复用 helper(例如路径解析、结果结构化展示、YAML 片段摘录等)时,这些 helper MUST 为纯 Python 且 MUST NOT 依赖 marimo UI server.

这些 helper MAY 位于：
- `packages/scalim-misc/src/scalim_misc/notebook_support/`（仅工具函数/不承载教学主流程）
- 或 `notebooks/marimo/` 下的受控纯 Python 支撑模块（用于多个 notebooks 复用）

#### Scenario: helper 可被 headless runner 导入
- **WHEN** 在不启动 marimo UI server 的 Python 进程中导入这些 helper 模块
- **THEN** 导入成功且不触发 marimo UI server 依赖

## REMOVED Requirements

### Requirement: 章节 notebooks 复用 `packages/scalim-misc` 章节 SSOT
**Reason**: 本变更将教学主流程代码迁回 notebooks，以便在 Marimo 中展示过程与 UI 组件；`scalim-misc` 不再作为章节 SSOT 的唯一真相来源。

**Migration**: 将 `packages/scalim-misc/src/scalim_misc/demo_big_data_report/chapters/*.py` 的章节主流程迁移为 notebooks 侧 SSOT 入口（同章节 notebook 或 notebooks 侧支撑模块），并更新章节 registry、headless runner 与 coverage 生成器的映射口径。

