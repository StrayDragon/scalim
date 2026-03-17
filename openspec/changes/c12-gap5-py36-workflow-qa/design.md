## Context

Scalim 运行时边界要求兼容 Python 3.6（`pyproject.toml` 的 `requires-python=">=3.6"`），但当前 workflow 相关入口在 Python 3.6 环境中会因为**类型注解在 import 阶段求值**而直接失败（见 `.tmp/downstream_report/gaps/05_workflow_preload_cache_py36.md`）。

同时，日常开发通常在 Python 3.10+，仅靠 `compileall` 的语法检查很容易漏掉 “import 时炸” 的兼容性问题（尤其是 `collections.abc` 泛型下标、以及可选依赖在 import 阶段被意外拉起）。

本变更聚焦把这类风险前置到 `just qa` 的 Py3.6 门禁中，并确保可选依赖（例如 `openpyxl`）保持可选：仅在使用对应能力时才要求安装。

## Goals / Non-Goals

**Goals:**
- 修复 Python 3.6 下 workflow 入口可被导入并可运行（重点修复 `execution.preload_cache` 的注解兼容问题）。
- 强化 `just qa` 的 Py3.6 门禁：在 docker 的 Python 3.6 + `typing-extensions==4.1.1` 环境中加入关键模块的 import smoke test，覆盖 workflow 入口路径。
- 保持 `openpyxl` 等可选依赖的“可选性”：核心模块 import 不因未安装可选依赖而失败。

**Non-Goals:**
- 不改变 workflow 的调度语义（并发、失败策略、共享 preload cache 的逻辑保持不变）。
- 不引入新的可选依赖或改变依赖锁定策略（仅调整 import 结构与 QA 覆盖）。

## Decisions

1) **修复 Python 3.6 注解求值差异**
- 将会在 import 阶段求值且在 Py3.6 下不可下标的 `collections.abc.Iterator` 泛型注解替换为 `typing.Iterator`（在 Py3.6 下可下标）。

2) **避免可选依赖在 import 阶段被拉起**
- 将 `Excel` 相关 sink 的 import 改为按需导入（仅在创建 excel sink 时触发），并将类型注解改为 `TYPE_CHECKING` / 字符串前向引用，避免 `openpyxl` 缺失时影响核心入口 import。

3) **把风险前置到 Py3.6 门禁**
- 在 `scripts/check-py36-typingext-docker.sh` 中加入 import smoke test，显式导入 workflow 实现模块（`scalim.dsl.by_yaml.runtime.workflow_entrypoints`）以及核心入口模块，确保问题在 QA 阶段 fail-fast。

## Risks / Trade-offs

- **风险：smoke import 覆盖过大导致可选依赖被“变相必选”。**
  - 缓解：只导入“应当无可选依赖”的核心入口与 workflow 实现模块；涉及 `Excel` 的模块只在运行时按需触发，并使用 `require_optional_dependency` 给出清晰错误。

- **风险：未来新增模块依赖链变长，引入新的 import-time 兼容性回归。**
  - 缓解：将 smoke import 作为门禁长期保留，优先覆盖稳定入口（`scalim.dsl.by_yaml`、workflow entrypoints、execution core）。

## Migration Plan

- 对使用方：无迁移步骤。行为变化仅体现在 import 可用性与 QA 更早暴露错误。
- 对仓库维护：保持 `just qa` 作为唯一门禁入口；在 docker 环境中运行 Py3.6 检查以保证语义一致。

## Open Questions

- 是否需要额外补充一个最小 workflow e2e 测试（在 pytest 里跑，覆盖 `share_preload_cache` 的 happy-path）以补强运行期行为回归？

