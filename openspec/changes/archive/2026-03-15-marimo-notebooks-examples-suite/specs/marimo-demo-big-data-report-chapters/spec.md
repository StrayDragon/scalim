## ADDED Requirements

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

章节 notebook 文件名 MUST 以 `<chapter_id>.py` 结尾,且 MAY 额外包含有序前缀(例如 `01_`),用于稳定排序与导航.

#### Scenario: 章节 notebooks 存在
- **WHEN** 维护者检查 `notebooks/marimo/demo_big_data_report/chapters/` 的文件集合
- **THEN** 上述每个 `chapter_id` 都存在至少一份以 `<chapter_id>.py` 结尾的 notebook 文件

### Requirement: 章节 notebooks 复用 `packages/scalim-misc` 章节 SSOT
每个章节 notebook MUST 通过调用 `packages/scalim-misc/src/scalim_misc/demo_big_data_report/chapters/*.py` 中对应的 `run_*()` 入口来执行该章节,并展示 `ChapterResult` 的可观察输出(至少包含 `passed` 与 `summary`).

章节 notebook MUST NOT 直接在 notebook 内部复制实现一套独立的 demo 执行逻辑(例如自行构建 `DemandIr`/`PlanBuilder`/`ScalimEngine` 作为章节主路径),以避免出现第二套真相.

#### Scenario: notebook 执行路径同源
- **WHEN** 读者在 marimo 中运行任一章节 notebook
- **THEN** 该 notebook 的核心执行入口来自对应 `scalim_misc.demo_big_data_report.chapters.*` 的 `run_*()` 函数
- **AND** notebook 展示 PASS/FAIL 与可定位的章节级 summary

### Requirement: `demo_main.py` 保持为 hub/index 入口并可一键跑完章节
系统 MUST 保持 `notebooks/marimo/demo_big_data_report/demo_main.py` 为 `demo_big_data_report` 的 Marimo hub/index 入口.

`demo_main.py` MUST 提供:
- 一键执行全部章节(通过 `scalim_misc.demo_big_data_report.chapters.registry.run_all_chapters(...)`)
- 对章节结果的汇总展示(至少包含每章 `chapter_id/passed/summary`)
- 指向 `chapters/` 内各章节 notebook 的导航信息

#### Scenario: hub 可发现并可汇总
- **WHEN** 读者打开 `notebooks/marimo/demo_big_data_report/demo_main.py`
- **THEN** 能看到章节列表/导航
- **AND** 能运行全部章节并获得汇总结果

### Requirement: canonical YAML SSOT 路径不变
系统 MUST 保持 canonical YAML SSOT 文件路径不变,至少包括:
- `notebooks/marimo/demo_big_data_report/by_yaml_dsl/ecommerce_report.yaml`
- `notebooks/marimo/demo_big_data_report/by_yaml_dsl/ecommerce_report_fragments.yaml`

#### Scenario: canonical YAML 路径稳定
- **WHEN** 维护者检查上述 canonical YAML 文件路径
- **THEN** 文件存在且路径未被移动或重命名

### Requirement: notebook-support helpers 必须 headless 且不依赖 marimo
当引入 notebook 复用 helper(例如路径解析、`ChapterResult` 结构化展示、YAML 片段摘录等)时,这些 helper MUST 下沉到 `packages/scalim-misc/src/scalim_misc/` 下的受控模块中,并 MUST NOT 依赖 marimo.

#### Scenario: helper 可被 headless runner 导入
- **WHEN** 在不导入 marimo 的 Python 进程中导入这些 helper 模块
- **THEN** 导入成功且不触发 marimo 依赖

