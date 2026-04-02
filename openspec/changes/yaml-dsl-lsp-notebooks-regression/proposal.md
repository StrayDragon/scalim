## Why

当前 YAML DSL 的 editor/LSP 语义已经抽离为可复用的 core（`scalim-yaml-dsl-lsp`），但回归主要依赖少量“合成”测试用例，无法持续覆盖真实 YAML 场景下的关键交互：

- diagnostics 在跨文件 imports、不同目录结构下是否仍然可用且可定位
- go-to-definition / hover / completion 对 `loader`/`call_by` 等 Python 引用是否能稳定工作

同时，本仓库已经在 `notebooks/` 下维护了一套“真实且持续演进”的 YAML fixtures（demo_big_data_report 的 declared_yaml_dsl 场景库）。将其复用为 core 的回归输入，可以以很低成本获得高价值的稳定性保障，并为后续 LSP server / IDE 集成路线提供可审计的基线。

## What Changes

- 新增一套基于 notebooks fixtures 的 pytest 回归（不执行用户代码、不中转 CLI）：
  - 自动发现并遍历 `notebooks/marimo/demo_big_data_report/chapters_of_yaml_dsl/declared_yaml_dsl/` 下的 `*.yaml/*.yml`（排除 `.tmp/**` 等产物目录）
  - 对每个 YAML 运行 editor-semantics core diagnostics：要求无 errors（warnings 允许但结构必须健全且可定位）
  - 从 YAML 中抽取 `loader`/`call_by`/`retry.should_retry` 等 Python 引用字符串，回归 go-to-definition + hover + completion 的最小可用性
- 为 fixtures 增补最小 `scalim.yaml`（位于 declared_yaml_dsl 根目录），用于 editor project discovery：
  - 通过 `yaml_dsl.import_allowed_roots` 允许 fixtures 内部跨子目录 imports（例如 `support/` 引用 `../_shared/...`）
  - 通过 `yaml_dsl.editor.python_roots` 明确静态解析 Python 引用时的搜索根（例如 `src/` 与 `packages/scalim-misc/src`）
- 加固 editor-semantics core 的 Python 引用解析：对 `call_by` 常见的 `reference(args...)` 形态支持导航与补全（以静态方式解析可调用头部，忽略参数段）。

非目标（本变更不做）：
- 交付可安装的 VSCode 扩展或 LSP server 发行物
- 运行 notebooks / 执行 loaders / 引入 runtime side-effects
- 改动 YAML DSL 的运行时语义边界（仅提升 tooling 侧可用性与回归覆盖）

## Capabilities

### New Capabilities
- `yaml-dsl-lsp-notebooks-regression`: 复用 notebooks 的 YAML fixtures 作为 editor-semantics/LSP core 的静态回归输入（diagnostics + definition/hover/completion），提供稳定 gate。

### Modified Capabilities
- `yaml-dsl-editor-semantics-core`: 扩展 Python 引用静态解析的输入形态，允许对 `reference(args...)`（例如 `call_by`）进行 go-to-definition/hover/completion（解析可调用头部并保持 side-effect free）。
- `yaml-dsl-lsp-server`: 明确 server 层对 `loader`/`call_by` 的导航能力需覆盖 `reference(args...)` 形态，并继续以 shared core 作为唯一语义 SSOT。

## Impact

- 影响代码/资产：
  - `packages/scalim-yaml-dsl-lsp/`（tooling core 逻辑小幅加固）
  - `notebooks/.../declared_yaml_dsl/`（新增 `scalim.yaml` 作为 editor discovery 配置；YAML fixtures 仍为 SSOT 示例库）
  - `tests/`（新增独立 pytest 回归模块）
- CI/质量门禁：新增的回归仅做文件系统读取 + AST 解析，预期稳定且执行成本低于运行示例。
