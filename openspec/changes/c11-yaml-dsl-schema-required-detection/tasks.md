## 1. Schema(required) 读取与缓存（SSOT）

- [ ] 1.1 在 `packages/scalim-yaml-dsl-lsp` core 中新增/完善 helper：从 `demand.gen.json` / `workflow.gen.json` 读取顶层 `required` 并缓存（允许缺失时降级为空集合）
- [ ] 1.2 为 required 读取逻辑补充单测：确保能稳定得到 `demand={"name","main_source"}` / `workflow={"workflow"}`，并覆盖异常/缺失时的降级路径

## 2. LSP core/server 的 DSL 探测与 kind 分类对齐

- [ ] 2.1 更新 `is_probably_yaml_dsl_document()`：优先依据 schema(required) + 最小结构约束（workflow 值为 mapping）判定；required 未满足时仅允许 DSL 专属特征（`$import/$init_var`、`loader/call_by`、schema modeline）触发 permissive fallback
- [ ] 2.2 更新 `classify_yaml_dsl_kind()`：优先 schema(required) 判定 workflow/demand；未命中时保持确定性降级（默认 demand），并确保与 `yaml-dsl-editor-project-discovery` spec 一致
- [ ] 2.3 补充/更新 editor semantics core 单测：覆盖
  - workflow: `workflow: { ... }` 被分类为 workflow
  - demand: `name + main_source` 被分类为 demand
  - in-progress: 仅 `loader:`（无 required）仍会被视为“可能是 DSL”（gating 允许）但 kind 仍可稳定降级为 demand
  - non-DSL: 普通 YAML 不触发 DSL gating（server 不发布 diagnostics）
- [ ] 2.4 复核 `packages/scalim-yaml-dsl-lsp` server gating：非 DSL 文档 diagnostics/definition/hover/completion/codeAction 均返回空，且不影响正常 YAML 编辑体验

## 3. VSCode 扩展的 schema 绑定与自动启用对齐

- [ ] 3.1 扩展在 schemaPaths 可用时读取 schema(required) 并用于单文件 kind 推断（demand/workflow）；schemaPaths 不可用时保持现有启发式 fallback
- [ ] 3.2 复核自动启用逻辑：优先 required 命中；未命中时仅在出现 DSL 专属语法特征时才尝试自动启动 LSP（避免 `workflow:` 这种泛化 key 造成误触发）
- [ ] 3.3 手工验收：打开 `notebooks/.../ecommerce_report.yaml` 能自动启动并支持 go-to-definition；打开非 DSL YAML 不出现 scalim diagnostics/Quick Fix

## 4. Spec/工件校验（无生成物修改）

- [ ] 4.1 运行 `just openspec-check`，确保 change 工件通过 sanitize + validate（注意：`src/scalim/dsl/by_yaml/schema/*.gen.json` 为生成物，仅读取不修改）

