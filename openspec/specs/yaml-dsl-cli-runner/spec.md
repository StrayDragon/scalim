# yaml-dsl-cli-runner Specification

## Purpose
定义 `scalim-cli yaml-dsl` 的命令边界：CLI 仅承载 authoring/tooling（schema/validate/editor integration），执行入口统一收敛为 Python API。
## Requirements
### Requirement: CLI MUST be tooling-only and MUST NOT execute YAML DSL
系统 MUST 将 `scalim-cli yaml-dsl` 定位为 authoring/tooling 工具集合（schema/validate/editor integration），并且 MUST NOT 提供 demand/workflow 的执行子命令。

说明：

- demand YAML 执行入口：`scalim.dsl.by_yaml.run(..., options=RunOptions(...))`
- workflow YAML 执行入口：`scalim.dsl.by_yaml.run_workflow(..., options=RunOptions(...), ...)`

#### Scenario: yaml-dsl help does not list run commands
- **WHEN** 用户执行 `scalim-cli yaml-dsl --help`
- **THEN** 输出 MUST 不包含 `run` 或 `workflow run` 执行子命令

