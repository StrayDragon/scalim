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
- 在 `scalim` 内提供稳定、可导入的编辑器语义接口（Diagnostics/Definition/Completion/Hover 的最小集合）。
  - 这组接口可作为 editor/tooling 的内部导出特例存在,不强制纳入普通用户 public API 面。
- demand 诊断复用现有 validator + location index；workflow v1 仅做结构导向诊断（与当前 parser/schema 边界一致）。
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

这里有一个需要写清的事实:

- `scalim.yaml` 不是假想中的新配置文件,也不是废弃提案
- 当前代码已经通过 `project_config.py` 实现了 nearest-wins 查找,并实际承载:
  - `yaml_dsl.import_aliases`
  - `yaml_dsl.import_allowed_roots`

因此 editor/LSP 子配置如果要加入,是在一个已经存在且已被 YAML DSL 使用的项目配置入口上继续扩展,而不是再引入一份平行配置。

2) **Static semantics boundary inside `scalim`**

- 新增（或收敛）一组不依赖 CLI 输出格式的语义接口：
  - YAML kind classification（demand/workflow）
  - demand 语义 diagnostics（复用 validator）
  - workflow schema-only diagnostics
  - Python symbol definition resolution（不执行用户代码；基于 `importlib.util.find_spec` + AST 解析定义位置）
- 这些接口必须可在 Python 3.6 下导入，并对缺失可选依赖（如 `jsonschema`）有清晰降级策略（warning，而不是 crash）。
- 这些接口默认服务于 LSP / editor / tooling,可以采用“尽量隐藏的内部导出”形态,作为 public API 治理中的特例。

3) **Diagnostics contract**

- 对编辑器输出统一结构（路径 + range + message + severity）：
  - 逻辑 path 口径与 CLI 保持一致（点号分段 + 数字段索引）。
  - range 来自 YAML location index；无法定位时落到 `(root)` 或文件级范围。
- workflow v1 不引入 runtime compile/run 语义诊断；保持“结构/unknown-fields”为主。

这里要对现状说得更准确一些:

- 当前 `yaml_dsl_lsp.py` 主要只是 schema modeline 工具
- 当前 workflow 编辑器校验入口 `validate_workflow_yaml_text_json(...)` 虽然带 `schema_path` 参数,但实际上并不执行 JSON Schema 校验,而是走 parser-only 验证

所以 v1 不应过度承诺“workflow 已有完整语义 LSP”。

4) **workflow v2 semantic diagnostics 作为后续增量层**

这里的“workflow v2 semantic diagnostics”指的不是再做一遍 schema 校验,而是补上那些**只有理解 workflow 语义关系后才能报出的错误**。

几个具体例子:

- `depends_on` / `main_rows_from` 关系不一致
  - 例如 `main_rows_from.run: a`,但当前节点并没有 `depends_on: [a]`
- workflow 节点引用不存在
  - 例如 `$ctx` 或 `depends_on` 引用了不存在的 run id
- workflow 共享资源冲突
  - 两个 demand 对同一个 `book_id` 给出了冲突定义,但 workflow 没有在 `workflow.resources.books.<id>` 统一覆盖
- 输出绑定语义不成立
  - 例如某个 output 引用了不存在的 `resources.books.<id>` / `resources.files.<id>`
  - 或 workbook/sheet 绑定组合在静态上就不合法

这些问题今天很多已经在 workflow compile 路径里有运行前 fail-fast,但还没有抽成 editor 友好的稳定语义接口。

因此本提案的节奏应是:

- v1: 先把 demand 语义诊断 + workflow 结构诊断接口稳定下来
- v2: 再逐步把 workflow compile 前的静态语义检查抽出来,供 LSP 直接复用

5) **Docs / Generated boundaries & drift gates**

- schema SSOT：`src/scalim/dsl/by_yaml/schema_dsl/**`；生成物：`src/scalim/dsl/by_yaml/schema/*.gen.json`（用 `just gen-yaml-dsl-schema`/`just gen` 刷新）。
- docs SSOT：`docs/doc/**`（若涉及 injected blocks，用 `just gen-docs` 刷新）。
- OpenSpec 工件提交前必须通过 `just openspec-check`；实现期通过 `just qa` 兜底 drift。

## Risks / Trade-offs

- [静态 Python 定义解析不完备] 动态导入/运行时生成对象无法静态定位 → 缓解：仅对明确的 `module:attr`/`module.attr` 做 best-effort；失败时返回空结果并给出可诊断的 warning。
- [多根工作区复杂度] Python roots/项目发现若配置不当会导致跳转不稳定 → 缓解：nearest-wins + 显式 override；在输出中包含“使用了哪个 scalim.yaml/roots”用于排障。
- [可选依赖差异] `jsonschema` 在 LSP 运行环境可能缺失 → 缓解：workflow v1 允许 schema-only 诊断在依赖缺失时降级为 warning（并建议 extension 侧提示安装）。
- [与 public API 治理的张力] editor semantics 接口需要稳定,但又不希望扩大普通用户 public API 面 → 缓解：将其明确标记为 editor/tooling 特例接口,文档化其用途与边界。

## Migration Plan

- v1 先落地 `scalim` 内可复用语义接口 + 规范，LSP server/VSCode extension 作为独立仓库或 `packages/` 目录下产物按该规范对接。
- 未来若 workflow 语义校验边界扩展，再在此基础上增强（保持 editor API 稳定）。
- 未来可进一步评估把 LSP server 放在 `packages/` 侧用 Python 3.10+ 调主包,并继续评估 Pyodide / WASM 等形态，以改善 VSCode / 浏览器侧集成体验。
