## Why

仓库宣称运行时兼容 Python 3.6（`pyproject.toml` 的 `requires-python=">=3.6"`），但目前 workflow 相关入口在 Python 3.6 环境下会在 **import 阶段** 因类型注解求值差异直接失败（见 `.tmp/downstream_report/gaps/05_workflow_preload_cache_py36.md`）。

此外，日常开发在 Python 3.10+，仅靠语法编译检查很容易漏掉“import 时炸”的兼容性问题，因此需要把该风险前置到 `just qa` 的 Py3.6 门禁路径中，避免回归。

## What Changes

- 修复 Python 3.6 下 workflow 入口可 import（聚焦 `execution.preload_cache` 的泛型注解兼容）。
- 强化 `just qa` 的 Py3.6 检查：在 docker 的 Py3.6 + `typing-extensions==4.1.1` 隔离环境中加入关键模块的 import smoke test（覆盖 workflow 入口）。
- 保持 openpyxl/pandas 等可选依赖的“可选性”：核心入口的 import 不应因为未安装可选依赖而失败；当且仅当使用对应能力时才提示安装依赖。

## Capabilities

### New Capabilities

（无）

### Modified Capabilities

- `yaml-dsl-workflow`: workflow 入口在 Python 3.6 下 MUST 可被导入并可运行（含 `share_preload_cache` 路径的基础可用性）。
- `testing-quality`: `just qa` 的 Py3.6 门禁 MUST 覆盖“import 时炸”的兼容性问题，而不只做语法编译检查。

## Impact

- 代码影响面：`src/scalim/execution/preload_cache.py`、`src/scalim/execution/output_composition.py`（仅 import 行为调整与懒加载，不改变运行语义）。
- QA 影响面：`scripts/check-py36-typingext-docker.sh`（更全面的 import smoke 覆盖）。

