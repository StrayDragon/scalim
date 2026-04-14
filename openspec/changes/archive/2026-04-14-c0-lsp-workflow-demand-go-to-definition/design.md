## Context

当前 `scalim-yaml-dsl-lsp` 已在 LSP server 层提供了多类 go-to-definition（Python 引用、`$import`、`imports.*`、实体引用等），但 workflow YAML 的 `workflow.runs[*].demand` 仍是纯字符串，缺少跳转能力。

workflow demand path 的 runtime 解析规则已在 `scalim.dsl.yaml_dsl.workflow_config.resolve_workflow_demand_path` 中实现（相对路径基于 workflow 文件目录、支持 `@/...` 与 `ALIAS:/...`、并进行 allowed roots 越界校验）。LSP 侧应复用该 library 语义而不是在 server 层复制实现。

文档/生成边界：
- 本变更只修改 LSP 实现与 OpenSpec 工件；不触碰任何 `*.gen.*` 生成物或 `BEGIN/END AUTOGEN` 注入区块，因此无需 `just gen-docs`。
- 漂移门禁：完成后以 `just openspec-check`（工件）+ `just qa`（代码质量门禁）兜底。

## Goals / Non-Goals

**Goals:**
- 在 workflow YAML 中对 `workflow.runs[*].demand` 支持 go-to-definition：跳转到解析后的 demand YAML 文件。
- 解析语义与 runtime 一致：相对路径基于 workflow 文件所在目录；支持 `@/...` 与 `ALIAS:/...`。
- 在 editor discovery 的 allowed roots 约束下解析并拒绝越界，失败时可诊断降级（不 crash、空结果）。

**Non-Goals:**
- 不引入 workflow 的 runtime compile 语义诊断（保持 workflow diagnostics v1 schema-only 边界）。
- 不新增文件路径 completion/路径补全（仅做 definition）。
- 不新增独立的 LSP-only path_aliases 配置入口（优先复用 `scalim.yaml` 已有 import roots alias 作为 editor 侧默认）。

## Decisions

1) **Cursor extraction 增量扩展**
- 在 `scalim_yaml_dsl_lsp.cursor_extraction` 增加对 `workflow.runs.<idx>.demand` 的光标抽取（单行 scalar string），产出引用文本与 value range。
- 复用现有抽取框架（ruamel compose + range 计算），并提供 “空值 + 光标在冒号后空白” 的保守 fallback（与 `imports.*` 类似）。

2) **Definition handler 复用 runtime 解析**
- 在 LSP server 的 definition handler 链上增加 workflow-demand 分支：
  - 仅在抽取命中 `workflow.runs[*].demand` 时处理；
  - 使用 `scalim.dsl.yaml_dsl.workflow_config.resolve_workflow_demand_path` 解析并校验；
  - `allowed_yaml_roots` 取自 editor discovery（与 import/$import 解析一致）。
- `path_aliases` 的来源选择：
  - 若可加载到 `scalim.yaml` 的 YAML DSL project config，则以 `yaml_dsl.import_roots[].alias`（`import_aliases`）作为 editor 侧默认 `path_aliases`；
  - 若无配置或加载失败，则不提供 aliases（仍支持相对路径）。

3) **Location 输出策略**
- 解析成功返回 1 个 `Location`，指向 resolved demand YAML 文件的 `(0,0)`（不尝试定位到 YAML 内更细粒度位置）。
- 任何异常/解析失败都返回空结果，并记录 warnings（不得 crash）。

## Risks / Trade-offs

- [alias 语义不完全等价] runtime 允许 Python 入口/CLI 注入 `path_aliases`，LSP 无法可靠获知；采用 `scalim.yaml import_roots.alias` 作为 editor 默认值可能与运行时不一致 → 缓解：不阻塞相对路径场景；别名解析失败时降级为空结果并给出可诊断信息。
- [allowed roots 过于严格导致无法跳转] 若用户未配置 `import_roots`/workspace root discovery 不覆盖目标 demand 路径，解析会被拒绝 → 缓解：遵循现有安全边界，必要时引导用户在 `scalim.yaml` 配置 `yaml_dsl.import_roots`。
