## Context

- VSCode 侧 YAML schema 校验由 YAML extension（yaml-language-server）完成；其行为为“纯 schema 校验”，不会执行 Scalim 的 imports expansion，因此看不到 `$import` 片段中的字段。
- Scalim 自身（CLI / library）在 schema/语义校验前会展开 imports（`imports` + `$import`），因此同一份 YAML 在 CLI 下可通过，但编辑器会出现误报红线（典型为 `definitions.book` 的 `xlsx_memory` 分支要求 `budget`）。
- 当前 `scalim-yaml-dsl-lsp` 已提供 Python 引用的 definition/hover/completion，但未覆盖 `$import` 的导航能力。

约束：

- LSP 侧必须静态解析、无副作用、不得 shell-out CLI。
- 生成物约束：禁止手改 `*.gen.*`；schema 变更必须修改 SSOT（schema_dsl）并通过 generator 漂移门禁。

## Goals / Non-Goals

**Goals:**

- 为 `$import` 引用提供 go-to-definition 与 hover：
  - 从 `$import: <alias>(.<segment>)*` 跳转到对应 fragment YAML 文件中的 mapping key（尽可能精确到 key 的位置）。
  - hover 展示 alias 解析后的来源文件路径与 ref logical path。
- 修复 demand/workflow JSON schema 在 `$import` 场景下的误报：
  - kind-based `if/then` 分支在 `kind` 缺失时不得触发，避免“Missing property `budget`”等假阳性。

**Non-Goals:**

- 不尝试让 VSCode YAML extension 支持 imports expansion（不可控、超范围）。
- 不通过禁用全局 YAML validation 来“压过” YAML extension（会误伤用户其它 YAML 文件）。
- 暂不新增 `$import` 的 completion（仅 definition/hover + schema 误报修复）。

## Decisions

### Decision: `$import` 导航在 LSP 中独立实现，不依赖展开后 IR

原因：

- `$import` 的 go-to-definition 需要定位到 fragment YAML 的源码位置；展开后的 mapping 丢失位置信息。
- 直接基于 ruamel compose 节点（带 start_mark/end_mark）可稳定定位 key/value 范围，且不执行用户代码。

实现要点：

- 在 `cursor_extraction` 增加对 `$import` 光标抽取（string / list element 两种形态）。
- 在 server 的 `definition`/`hover` handler 中：
  1) 先尝试解析 Python 引用（现有逻辑）
  2) 若无命中，再尝试 `$import` 抽取与解析
- `$import` 解析与路径解析遵循 runtime 规则：
  - `imports.<alias>` 必须存在且为字符串路径
  - 相对路径基于 anchor YAML 目录解析
  - 支持 `scalim.yaml` 中的 `import_aliases` 重写
  - 校验 `allowed_yaml_roots` 与 `import_allowed_roots` 边界（越界则不跳转，仅提示）
- fragment YAML 定位：
  - 读取目标 YAML 文本并 ruamel compose
  - 逐段下钻到目标 mapping，并返回最终 key 的 `start_mark` 作为跳转位置

### Decision: schema 误报通过修正 `if/then` 的 `if` 条件实现

原因：

- JSON schema 中 `if: {properties: {kind: {const: ...}}}` 在 `kind` 缺失时会“通过”（properties 不会对缺失字段失败），导致 then 被错误触发。
- schema 已通过 `anyOf: [required kind, required $import]` 表达 `$import` 形态；只需保证 kind 分支在 kind 缺失时不触发即可。

实施：

- 在 schema DSL 的 kind-variant 生成处，统一为 `if` 增加 `required: ["kind"]`。
- 覆盖 `demand.gen.json` 与 `workflow.gen.json` 的 book 等资源分支（并扫描其它同类模式）。

## Risks / Trade-offs

- [风险] `$import` 引用指向 preset（`scalim://...`）无法跳转到文件 → [缓解] hover 提示来源为 preset，definition 返回空结果且提供可诊断 warnings。
- [风险] fragments 可能很大，频繁解析有性能成本 → [缓解] 仅在 definition/hover 时按需解析；后续可加 LRU cache（不作为本次必做）。
- [风险] schema 更宽松可能掩盖部分错误 → [缓解] 仅改变 kind 分支触发条件；真正的语义校验仍由 scalim validator（LSP diagnostics/CLI）在 imports expansion 后兜底。

