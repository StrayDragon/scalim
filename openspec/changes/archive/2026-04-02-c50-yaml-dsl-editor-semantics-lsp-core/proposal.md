## Why

`YAML DSL` 的编辑器语义（project discovery、diagnostics、Python 引用的 definition/hover/completion）目前直接实现在主包 `scalim` 的运行时代码树下（`src/scalim/...`）。
这会把 **编辑器/LSP 的演进速度** 绑定到 **Python 3.6 运行时兼容边界**，并导致：

- 无法在编辑器侧自由使用 `pygls`/`lsprotocol` 等现代依赖与类型系统能力；
- “编辑器静态分析” 与 “运行时编译/执行” 的信任边界容易混在一起（例如全局状态污染、并发模型不清晰）；
- LSP server / VSCode extension / CLI 的 editor 能力难以复用，重复实现与漂移风险上升。

因此需要将 editor 语义抽离为一个 **>=3.10 的独立包**，作为 LSP server 与工具链的共享 core。

## What Changes

- 新增包：`packages/scalim-yaml-dsl-lsp/`（`requires-python >= 3.10`），提供可复用的 editor core。
- 新增模块：`scalim_yaml_dsl_lsp.core`（具体命名以 design.md 为准），承载：
  - project discovery（nearest-wins `scalim.yaml`、roots 策略输出）；
  - diagnostics（demand/workflow 诊断与 schema 校验入口）；
  - Python 引用的 definition/hover/completion（静态解析，不执行用户代码）。
- 主包 `scalim` 不再提供 `scalim.dsl.by_yaml.editor_semantics`；仓库内统一迁移为从 `scalim_yaml_dsl_lsp.core` 导入。
- 后续 LSP server（以及 VSCode extension）统一依赖该 core，避免复制粘贴实现与规则漂移。

**BREAKING**：如果下游直接 import `scalim.dsl.by_yaml.editor_semantics`，需要迁移到 `scalim_yaml_dsl_lsp.core`（并安装 `scalim-yaml-dsl-lsp` 或 `scalim[yaml-dsl-lsp]`）。

## Capabilities

### New Capabilities

- `yaml-dsl-editor-semantics-core`: 定义 editor core 的公共 API、信任边界与并发/全局状态约束（例如禁止改写进程级 `sys.path`，禁止执行用户代码）。

### Modified Capabilities

- `yaml-dsl-lsp-server`: 明确 server 侧 MUST 使用抽离后的 editor core，并以其输出作为 diagnostics/definition/completion 的 SSOT。

## Impact

- 新增一个独立发布包与其 `pyproject.toml`/lockfile 变更；
- LSP/编辑器相关实现从 `src/scalim/` 抽离，主包运行时边界更清晰；
- 测试迁移到 core 包导入路径，补足行为/边界测试；
- 若涉及 docs/specs：`openspec/specs/*/spec.md` 为 SSOT；文档站点相关生成物需通过 `just gen-docs` 刷新（禁止手改 `*.gen.*` / AUTOGEN 区块）。
