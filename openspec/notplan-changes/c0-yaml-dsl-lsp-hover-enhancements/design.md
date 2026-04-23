## Context

PRD（`.tmp/prd/c0-scalim-yaml-dsl-lsp-hover-enhancements.md`）指出当前 `scalim-yaml-dsl-lsp` hover 信息偏“声明式文本”，对引用类场景（`relation.steps` 的 `source.field_id`、`call_by(...)` 的 field token、builtin callable 等）缺少上下文与结构化展示。

现状（代码走读结论，细节以实现为准）：

- Hover 入口在 `packages/scalim-yaml-dsl-lsp/src/scalim_yaml_dsl_lsp/server.py`，通过多路 `_try_handle_*` 判断不同 extraction 类型，并把 core 的 `result.text` 包装成 `types.Hover(contents=MarkupContent(kind=PlainText, ...))`。
- Hover 数据来源分散：
  - `entity_index = build_yaml_dsl_entity_index(...)`：静态 YAML mapping 扫描，用于 `source_id/relation_id/output_name/workflow_run_id` 及 relation step 的 `source_id.field_id` 子 token。
  - `effective_view = build_yaml_dsl_editor_effective_view(...)`：面向 demand YAML 的“effective view”，包含 `field_infos_by_id` / `field_definitions_by_id` / outputs effective fields / YAML anchors 等。
  - `expression_scope_index = build_yaml_dsl_expression_scope_index(...)`：表达式 token 的 scope/aggregate 相关信息。
  - Python/builtin callable hover 目前仅返回 docstring（或拼接少量字段）。
- `scalim.yaml` 的 project config 与 schema 由 `src/scalim` 维护，且 `src/scalim/` 必须保持 Python 3.6 兼容；JSON Schema 生成物为 `*.gen.*`，禁止手工编辑，统一通过 `just gen-yaml-dsl-schema` 刷新。

因此本变更需要在 **两条边界** 上推进：

1. **项目配置与 schema（Python 3.6）**：在 `scalim.yaml yaml_dsl.lsp.*` 增加 hover 配置，并纳入 `scalim_yaml.gen.json` 生成物。
2. **LSP hover 渲染（Python 3.10+）**：把 hover 输出升级为 Markdown，并让不同 hover 类型按配置渲染为“卡片”式结构。

## Goals / Non-Goals

**Goals:**

- 为 `scalim.yaml` 增加 `yaml_dsl.lsp.hover` 配置面：按 hover 类型配置“展示字段列表 + 顺序”，并提供默认值。
- `scalim-yaml-dsl-lsp` hover 输出统一切换为 Markdown（`MarkupKind.Markdown`），并以结构化 card 的方式呈现。
- Hover 内容聚焦“引用语义 + 上下文”，避免与 YAML schema hover 重复（schema hover 仍由 YAML LSP + JSON Schema 提供）。
- 变更纳入 SSOT → 生成物 → drift gate 链路：更新 schema SSOT 并通过 `just gen-yaml-dsl-schema` 刷新生成物。

**Non-Goals:**

- 不引入多版本 DSL（不新增 `dsl_version`，不维护并行 schema/parser）。
- 不改变 demand/workflow 的 runtime 语义与编译/执行链路；仅增强 editor/LSP 展示与配置。
- 不承诺跨编辑器 hover 展示完全一致（不同客户端对 Markdown 支持程度不同）；以 LSP 规范能力为基线。

## Decisions

1. **配置落点：`scalim.yaml yaml_dsl.lsp.hover`**
   - 与现有 `python_roots/kind_overrides` 同属 LSP/discovery 配置面，避免引入新的顶层段落或 legacy 路径。
   - 在 `src/scalim/dsl/yaml_dsl/_internal/config_parsing/project_config.py` 增加解析与校验（Python 3.6 兼容）。
   - 在 `src/scalim/dsl/yaml_dsl/schema_dsl/models/scalim_yaml.py` 增加 schema SSOT，并通过 `just gen-yaml-dsl-schema` 生成 `src/scalim/dsl/yaml_dsl/schema/scalim_yaml.gen.json`。

2. **渲染策略：按 hover 类型 + 字段 renderer 映射**
   - 每种 hover 类型维护一组允许字段名（枚举）与 renderer 映射。
   - 配置为“字段列表”，用于控制顺序与取舍；未配置时使用默认字段列表。
   - 渲染输出统一使用 Markdown card 模板（标题 + sections/list/table），并集中做必要的 escaping。

3. **数据来源优先级：复用既有索引，必要时降级**
   - entity 引用：优先 `entity_index`（稳定、静态、覆盖面广）。
   - demand 字段与表达式场景：优先 `effective_view` / `expression_scope_index`（已具备 field defs、outputs effective、aggregate scope 等）。
   - relation step 的 `source.field_id`：当 `effective_view` 可用时，用 `field_infos_by_id/field_definitions_by_id`（可按 `source_id` 消歧）；否则降级到 entity_index 的 source_fields。
   - Python/builtin callable：沿用 AST-based 解析，但增强 hover 输出字段（type/module/defined_at/parameters/docstring），并允许配置裁剪。

4. **热更新：mtime-aware cache，而非“强制重启 server”**
   - 设计为：以 `scalim_yaml_path` 为 key，缓存解析结果与文件 mtime；在 hover/diagnostics 计算时按需 reload。
   - 好处：无需编辑器侧 restart，且避免每次 hover 都做全量解析；同时保持行为确定性。

## Risks / Trade-offs

- **[不同客户端对 Markdown 支持不一致]** → 仅使用 LSP 标准 Markdown 片段（粗体/代码/列表/表格），避免依赖特定扩展；必要时允许 fallback 到纯文本（作为实现细节）。
- **[字段“类型/required”等信息在 DSL 中并非统一显式存在]** → hover 字段设计以“可稳定静态获得的信息”为 SSOT（例如 `name/extract/value_cast/relation`、定义位置、解析结果摘要）；对无法静态推断的字段明确为可选/降级。
- **[在 core.py 中增加渲染逻辑会进一步增大文件体量]** → 将 markdown 渲染与 renderer 分层（独立 helper + 小型 renderer 函数），并优先复用既有结果结构（summary/detail/definitions）。
- **[scalim.yaml schema 为生成物，易出现 drift]** → 变更任务中必须包含 `just gen-yaml-dsl-schema` 与 drift gate（例如 `just schema-drift-check`/`just qa`）验证步骤。
