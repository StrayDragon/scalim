## MODIFIED Requirements

### Requirement: `demo_big_data_report` 提供章节化 Marimo notebooks
系统 MUST 在 `notebooks/marimo/demo_big_data_report/` 下提供 `chapters/` 目录,并为主线 demo 的每个 SSOT 章节提供一份对应的 Marimo notebook.

主线章节 MUST 以 **YAML DSL 场景化**为主（面向工程使用方），并避免以 IR/Plan 等底层视角作为主线教学内容。

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
- **WHEN** 维护者检查 `notebooks/marimo/demo_big_data_report/chapters/` 的文件集合
- **THEN** 上述每个 `chapter_id` 都存在至少一份以 `<chapter_id>.py` 结尾的 notebook 文件

