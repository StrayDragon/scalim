## MODIFIED Requirements

### Requirement: workflow entrypoints MUST be importable under Python 3.6
系统 MUST 保证在 Python 3.6 + `typing-extensions==4.1.1` 的最小依赖环境中, workflow 入口实现模块可被导入:

- `scalim.dsl.by_yaml.workflow_entrypoints`

系统 MUST 确保该 import 不依赖 `openpyxl`/`pandas` 等可选依赖。

#### Scenario: workflow_entrypoints imports in a minimal Py3.6 environment
- **GIVEN** 仅安装了 `PyYAML` 与 `typing-extensions==4.1.1` 的 Python 3.6 环境
- **WHEN** 执行 `python -c "from scalim.dsl.by_yaml import workflow_entrypoints"`
- **THEN** import MUST 成功

#### Scenario: optional dependencies remain optional for core imports
- **GIVEN** 环境中未安装 `openpyxl`
- **WHEN** 用户仅导入 Scalim 核心入口模块（包含 workflow 相关实现模块）
- **THEN** import MUST NOT 因 `openpyxl` 缺失而失败

