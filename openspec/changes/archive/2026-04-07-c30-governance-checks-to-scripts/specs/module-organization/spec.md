# module-organization (delta)

## ADDED Requirements

### Requirement: 主包导入图 MUST 无环且禁止函数内导入
系统 MUST 保持 `src/IMPL_ROOT/`（排除 `src/IMPL_ROOT/vendor/**`）的模块导入图无环.

同时,主包模块 MUST NOT 在函数体内出现 `import ...` 或 `from ... import ...`（包括 `def` 与 `async def`）,以避免通过局部导入绕开依赖方向约束并隐藏导入副作用.

该约束 MUST 由可独立运行的静态门禁守护,并在 `just qa` 的 fail-fast 阶段执行（例如 `uv run scripts/check-import-graph.py --check`）。

#### Scenario: import graph gate reports cycles
- **WHEN** 开发者运行导入图门禁脚本（例如 `uv run scripts/check-import-graph.py --check`）
- **THEN** 若导入图存在环,门禁 MUST 失败并输出至少一个可定位的最小导入环（模块序列）

#### Scenario: import graph gate reports function-local imports
- **WHEN** 开发者运行导入图门禁脚本（例如 `uv run scripts/check-import-graph.py --check`）
- **THEN** 若主包存在函数内导入,门禁 MUST 失败并输出文件路径与行号

### Requirement: by_yaml runtime MUST NOT contain workflow runtime modules
系统 MUST 保持 `src/IMPL_ROOT/dsl/by_yaml/runtime/**` 不包含 workflow runtime 语义模块（例如 `workflow_*.py`）,以避免把 workflow 层实现符号误放入 DSL runtime 子包.

该约束 MUST 由可独立运行的静态门禁守护,并在 `just qa` 的 fail-fast 阶段执行（例如 `uv run scripts/check-workflow-layering.py --check`）。

#### Scenario: workflow_* modules are rejected under by_yaml runtime
- **WHEN** 维护者运行 workflow layering 的静态门禁
- **THEN** 若 `src/IMPL_ROOT/dsl/by_yaml/runtime/**` 下出现 `workflow_*.py`,门禁 MUST 失败并输出违规路径列表

## MODIFIED Requirements

### Requirement: workflow framework MUST NOT import DSL modules
系统 MUST 保持核心层级依赖方向可审计且单向；workflow runtime/framework 层 MUST NOT 反向依赖 DSL 层实现符号（例如 `IMPL_ROOT.dsl.by_yaml` 及其子模块）。

该约束 MUST 由可独立运行的自动化门禁守护（例如 `uv run scripts/check-workflow-layering.py --check`）,并在 `just qa` 的 fail-fast 阶段执行（pytest 之前）.

补充约束: workflow 层 MUST NOT 通过动态导入绕开该限制（例如 `importlib.import_module("...dsl...")` 或等价字符串导入）。

#### Scenario: workflow does not import dsl
- **WHEN** 维护者运行 workflow layering 的静态门禁
- **THEN** 结果 MUST 不出现 `workflow -> dsl` 的反向依赖
- **AND** 结果 MUST 不出现通过动态导入引入 `dsl` 的行为

