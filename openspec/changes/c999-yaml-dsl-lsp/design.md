## Context

当前 Scalim YAML DSL 的编辑体验主要依赖通用 YAML 扩展（例如 VSCode 的 `redhat.vscode-yaml`）提供的 JSON Schema 结构能力，但 DSL 语义层（诊断、跳转、补全、hover）仍缺少稳定的编辑器侧 API。

仓库当前已经具备:

- 语义校验器（validator）与 CLI 校验输出（含源码位置索引/可跳转定位）
- 内置 schema 资源（`demand.gen.json` / `workflow.gen.json`）
- `scalim.yaml` 项目配置（当前用于 imports allow roots / aliases 等）
- 辅助工具：`src/scalim/cli/yaml_dsl_lsp.py` 用于写入 schema modelines

但这些能力仍分散在不同模块中，且部分运行时解析逻辑带有动态导入/副作用假设，不适合直接用于 LSP 的“静态导航”。

本 change 的目标是：在不调用 CLI、复用 `scalim` library 的前提下，定义并落地可复用的“编辑器静态语义层”边界，并配套定义 LSP server 与 VSCode 扩展 v1 能力。

约束:

- `src/scalim/**` 运行时边界保持 Python 3.6 兼容。
- LSP server 作为独立仓库产物，可使用更高 Python 版本（建议 `>=3.9`），但不得通过 shell-out 调用 `scalim-cli`。
- 不替换通用 YAML server；schema 仍由 `redhat.vscode-yaml` 等扩展负责。

## Goals / Non-Goals

**Goals:**

- 定义跨编辑器的项目发现/文件识别/Python roots 方案，并以 `scalim.yaml` 作为优先 SSOT（零配置可用，显式配置可覆盖）。
- 在 `scalim` 内提供稳定、可导入的编辑器语义 API（Diagnostics/Definition/Completion/Hover 的最小集合）。
- demand 诊断复用现有 validator + location index；workflow v1 仅做 schema-only 校验（与当前实现边界一致）。
- 明确 docs/生成物边界与 drift gate：schema 与 docs 的 SSOT 与生成入口必须写清。

**Non-Goals:**

- 不实现/不复刻通用 YAML language server；不替换 `redhat.vscode-yaml`。
- 不在本仓库内交付完整 VSCode 扩展或 LSP server 发行产物（本仓库只定义/提供可复用语义层与规范）。
- 不冻结 DSL 语法，也不引入新的 DSL 语义特性（本 change 聚焦 editor integration）。
- v1 不承诺覆盖所有 Python 动态构造的定义解析（只做 best-effort，失败需可诊断且不崩溃）。

## Decisions

1) **Project discovery SSOT**

- 复用现有 `scalim.yaml`（nearest-wins）作为项目级配置入口，并扩展 `yaml_dsl` 下的 editor/lsp 子配置：
  - `python_roots`（用于静态解析 `loader`/`call_by` 的搜索根）
  - 可选的文件分类覆盖（demand/workflow）
- 零配置兜底：当未找到 `scalim.yaml` 时，以入口 YAML 所在目录作为 project root/默认允许根。

2) **Static semantics boundary inside `scalim`**

- 新增（或收敛）一组不依赖 CLI 输出格式的语义 API：
  - YAML kind classification（demand/workflow）
  - demand 语义 diagnostics（复用 validator）
  - workflow schema-only diagnostics
  - Python symbol definition resolution（不执行用户代码；基于 `importlib.util.find_spec` + AST 解析定义位置）
- 这些 API 必须可在 Python 3.6 下导入，并对缺失可选依赖（如 `jsonschema`）有清晰降级策略（warning，而不是 crash）。

3) **Diagnostics contract**

- 对编辑器输出统一结构（路径 + range + message + severity）：
  - 逻辑 path 口径与 CLI 保持一致（点号分段 + 数字段索引）。
  - range 来自 YAML location index；无法定位时落到 `(root)` 或文件级范围。
- workflow v1 不引入 runtime compile/run 语义诊断；保持“结构/unknown-fields”为主。

4) **Docs / Generated boundaries & drift gates**

- schema SSOT：`src/scalim/dsl/by_yaml/schema_dsl/**`；生成物：`src/scalim/dsl/by_yaml/schema/*.gen.json`（用 `just gen-yaml-dsl-schema`/`just gen` 刷新）。
- docs SSOT：`docs/doc/**`（若涉及 injected blocks，用 `just gen-docs` 刷新）。
- OpenSpec 工件提交前必须通过 `just openspec-check`；实现期通过 `just qa` 兜底 drift。

## Risks / Trade-offs

- [静态 Python 定义解析不完备] 动态导入/运行时生成对象无法静态定位 → 缓解：仅对明确的 `module:attr`/`module.attr` 做 best-effort；失败时返回空结果并给出可诊断的 warning。
- [多根工作区复杂度] Python roots/项目发现若配置不当会导致跳转不稳定 → 缓解：nearest-wins + 显式 override；在输出中包含“使用了哪个 scalim.yaml/roots”用于排障。
- [可选依赖差异] `jsonschema` 在 LSP 运行环境可能缺失 → 缓解：workflow v1 允许 schema-only 诊断在依赖缺失时降级为 warning（并建议 extension 侧提示安装）。

## Migration Plan

- v1 先落地 `scalim` 内可复用语义 API + 规范，LSP server/VSCode extension 作为独立仓库实现按该规范对接。
- 未来若 workflow 语义校验边界扩展，再在此基础上增强（保持 editor API 稳定）。

## Open Questions

- `scalim.yaml` 的 editor/lsp 子配置最终 schema：是否需要单独的 `scalim.config.yaml`？（v1 先以 `scalim.yaml` 扩展为主）
- workflow v2 何时引入语义级 diagnostics（非 schema-only），以及与 runtime `workflow validate` 的一致性策略。
