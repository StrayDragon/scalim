## ADDED Requirements

### Requirement: workflow public guidance MUST use curated stable entrypoints

在 `workflow-layering-refactor` 已先合并的前提下，系统 MUST 将 workflow 的用户侧导入与示例统一收敛到 curated stable entrypoints。

系统 MUST 允许面向用户的 workflow 官方用法通过以下路径表达：

- `scalim.dsl.by_yaml.run_workflow`
- `scalim.dsl.by_yaml.workflow`
- `scalim.dsl.by_yaml.workflow_types`
- `scalim.dsl.by_yaml.workflow_paths`

系统 MUST NOT 再把 workflow 的内部实现路径写成官方用户导入路径。

#### Scenario: workflow examples use stable facade paths
- **WHEN** 维护者编写或更新 workflow 相关 examples、skills 与 gate
- **THEN** 这些材料 MUST 使用 curated stable entrypoints
- **AND** 不得把内部 workflow runtime 模块路径写成推荐用户路径
