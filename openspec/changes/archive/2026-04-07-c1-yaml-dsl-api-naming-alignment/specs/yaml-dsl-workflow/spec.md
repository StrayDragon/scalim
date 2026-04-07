## MODIFIED Requirements

### Requirement: workflow public guidance MUST use curated stable entrypoints

在 workflow 分层稳定后，系统 MUST 将 workflow 的用户侧导入与示例统一收敛到 curated stable entrypoints。

系统 MUST 允许面向用户的 workflow 官方用法通过以下路径表达：

- `scalim.dsl.yaml_dsl.run_workflow`
- `scalim.dsl.yaml_dsl.workflow`
- `scalim.dsl.yaml_dsl.workflow_types`
- `scalim.dsl.yaml_dsl.workflow_paths`

系统 MUST NOT 再把 workflow 的内部实现路径写成官方用户导入路径。

#### Scenario: workflow examples use stable facade paths
- **WHEN** 维护者编写或更新 workflow 相关 examples、skills 与 gate
- **THEN** 这些材料 MUST 使用 curated stable entrypoints
- **AND** 不得把内部 workflow runtime 模块路径写成推荐用户路径

### Requirement: workflow entrypoints MUST be importable under Python 3.6
系统 MUST 保证在 Python 3.6 + `typing-extensions==4.1.1` 的最小依赖环境中, workflow 入口实现模块可被导入:

- `scalim.dsl.yaml_dsl.workflow_entrypoints`

系统 MUST 确保该 import 不依赖 `openpyxl`/`pandas` 等可选依赖。

#### Scenario: workflow_entrypoints imports in a minimal Py3.6 environment
- **GIVEN** 仅安装了 `PyYAML` 与 `typing-extensions==4.1.1` 的 Python 3.6 环境
- **WHEN** 执行 `python -c "from scalim.dsl.yaml_dsl import workflow_entrypoints"`
- **THEN** import MUST 成功

#### Scenario: optional dependencies remain optional for core imports
- **GIVEN** 环境中未安装 `openpyxl`
- **WHEN** 用户仅导入 Scalim 核心入口模块（包含 workflow 相关实现模块）
- **THEN** import MUST NOT 因 `openpyxl` 缺失而失败
