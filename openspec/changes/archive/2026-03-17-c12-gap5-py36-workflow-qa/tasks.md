## 1. Runtime fixes (Py3.6 importability)

- [x] 1.1 修复 `src/scalim/execution/preload_cache.py` 中 Python 3.6 下会在 import 阶段触发的注解求值不兼容问题（避免 `collections.abc` 泛型下标）。
- [x] 1.2 调整 `src/scalim/execution/output_composition.py` 的 import 结构，确保未安装 `openpyxl` 时核心入口仍可 import（按需导入 excel sink + `TYPE_CHECKING` 前向引用）。

## 2. QA gate (py36 + typing-extensions==4.1.1)

- [x] 2.1 增强 `scripts/check-py36-typingext-docker.sh`：在 docker 的 Python 3.6 隔离环境中加入关键模块 import smoke test（至少覆盖 `scalim.dsl.by_yaml.runtime.workflow_entrypoints`）。
- [x] 2.2 确保 smoke import 列表不会把 `openpyxl` 等可选依赖变成隐式必选（仅导入“应当无可选依赖”的核心入口与 workflow 实现模块）。

## 3. Verification

- [x] 3.1 在临时目录用 `/home/l8ng/.pyenv/versions/3.6.15/bin/python -m venv .venv` 快速验证：`compileall` + workflow 模块 import smoke（用于开发机快速迭代）。
- [x] 3.2 运行 `just py36-typingext-check` 进行 docker 版本验证（作为 `just qa` 的最终门禁口径）。
