# marimo-demo-big-data-report-chapters Specification

**状态: ✅ 已实现**

## Purpose
定义 `demo_big_data_report` 主线示例在 `notebooks/marimo/` 下的章节化组织要求:以 `demo_main.py` 作为 hub,每个 SSOT chapter 对应一本 Marimo notebook,并与 headless runner/pytest 同源对拍.

## Related Code (as implemented)
- `notebooks/marimo/demo_big_data_report/demo_main.py` (hub/index)
- `notebooks/marimo/demo_big_data_report/chapters_of_yaml_dsl/*.py` (YAML DSL 主线教学; 每章 notebook 既是教学入口也是 SSOT 执行入口)
- `notebooks/marimo/demo_big_data_report/chapters_of_yaml_dsl/registry.py` (章节 registry + gate/pytest 复用入口)
- `notebooks/marimo/demo_big_data_report/chapters_of_ir/*.py` (IR 视角回归章节; 不作为主线教学)
- `notebooks/marimo/demo_big_data_report/chapters_of_ir/registry.py` (IR chapters registry + gate/pytest 复用入口)
- `justfile` (`just examples` 统一 gate 入口; runner 内联实现)
## Requirements
### Requirement: `demo_big_data_report` 提供章节化 Marimo notebooks
系统 MUST 在 `notebooks/marimo/demo_big_data_report/` 下提供 `chapters_of_yaml_dsl/` 目录,并为主线 demo 的每个 SSOT 章节提供一份对应的 Marimo notebook.

主线章节 MUST 以 **YAML DSL 场景化**为主（面向工程使用方），并避免以 IR/Plan 等底层视角作为主线教学内容。

系统 MAY 额外提供 `chapters_of_ir/` 目录用于承载 IR 视角的回归章节,但这些章节不得作为主线教学内容。

初始章节集合 MUST 至少覆盖以下 `chapter_id`:
- `yaml_dsl_ecommerce`
- `yaml_dsl_ads`
- `yaml_dsl_support`
- `workflow_yaml`
- `workflow_demo_big_data_report`
- `yaml_dsl_debugging`

public API 覆盖章节（`__all__` 覆盖断言 + hooks/ob 扩展点）不再属于该主线章节集合，迁移为独立 suite 并仍纳入 examples gate（见对应规范）。

章节 notebook 文件名 MUST 以 `<chapter_id>.py` 结尾,且 MAY 额外包含有序前缀(例如 `01_`),用于稳定排序与导航.

#### Scenario: 章节 notebooks 存在
- **WHEN** 维护者检查 `notebooks/marimo/demo_big_data_report/chapters_of_yaml_dsl/` 的文件集合
- **THEN** 上述每个 `chapter_id` 都存在至少一份以 `<chapter_id>.py` 结尾的 notebook 文件

### Requirement: `demo_big_data_report` 章节 notebooks 作为 SSOT 并可对拍回归
系统 MUST 将 `demo_big_data_report` 的每个纳入 examples gate 的章节 notebook 同时视为教学入口与 SSOT 执行入口：

- 每个章节 notebook MUST 提供一个可被导入调用的 SSOT 入口函数（例如 `run_<chapter_id>()` 或 `run()`），用于执行 deterministic 对拍回归。
- `just examples` 的 headless runner（`justfile` 内联实现）与 pytest MUST 复用该入口执行该章节的对拍回归（不得再通过 `packages/scalim-misc` 的章节实现作为唯一真相来源）。

#### Scenario: chapter SSOT 入口可被 headless runner 调用
- **WHEN** 开发者运行 `just examples` 执行 `demo_big_data_report` 的某个章节
- **THEN** runner MUST 通过导入该章节 notebook 的 SSOT 入口函数来执行
- **AND** runner MUST 输出可定位的 PASS/FAIL 与章节级 summary

### Requirement: `demo_main.py` 保持为 hub/index 入口并可一键跑完章节
系统 MUST 保持 `notebooks/marimo/demo_big_data_report/demo_main.py` 为 `demo_big_data_report` 的 Marimo hub/index 入口.

`demo_main.py` MUST 提供:
- 一键执行全部章节(通过 `demo_big_data_report` 的章节 registry `run_all_chapters(...)`)
- 对章节结果的汇总展示(至少包含每章 `chapter_id/passed/summary`)
- 指向 `chapters_of_yaml_dsl/` 与 `chapters_of_ir/` 内各章节 notebook 的导航信息

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
当引入 notebook 复用 helper(例如路径解析、结果结构化展示、YAML 片段摘录等)时,这些 helper MUST 为纯 Python 且 MUST NOT 依赖 marimo UI server.

这些 helper MAY 位于：
- `packages/scalim-misc/src/scalim_misc/notebook_support/`（仅工具函数/不承载教学主流程）
- 或 `notebooks/marimo/` 下的受控纯 Python 支撑模块（用于多个 notebooks 复用）

#### Scenario: helper 可被 headless runner 导入
- **WHEN** 在不导入 marimo 的 Python 进程中导入这些 helper 模块
- **THEN** 导入成功且不触发 marimo 依赖
