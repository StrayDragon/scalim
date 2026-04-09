## Why

`call_by: "pkg.mod:fn(order_amount=order_amount, ...)"` 这种写法在真实报表里非常常见：左侧是 Python 形参名，右侧往往引用 YAML DSL 的 `fields.*`。但目前 LSP 只能对 `pkg.mod:fn` 本身做 Python definition/hover/completion，无法对 `=` 右侧的 field-id 做跳转与 hover，导致排错、重构和理解成本偏高。

## What Changes

- 在 `call_by`/同类可调用引用字符串中，识别 kwargs 的 `=` **右侧** field-id token，并提供：
  - hover：展示字段摘要（Field 卡片/预览）
  - definition：跳转到字段声明（含跨 imports 展开）
  - completion：在 `=` 右侧（含空值）提供 field ids 候选（Ctrl+Space 必须可用）
- 明确边界：`=` 左侧的 kwargs 名称视为 Python 语义，不作为 field-id 解析对象（hover/definition 返回空）。
- 保持性能与稳定性：不引入每字符全量重算；复用现有 debounce/缓存；解析失败时降级为空结果 + warnings（不崩溃）。

覆盖范围补充：
- `fields.*.call_by`（派生字段）
- `outputs[*].aggregate.fields.*.call_by`（聚合后派生字段；scope 优先 aggregate out_field_id + group_by）
- builtin callable 引用 `call_by: "^<id>(...)"`（head 为 builtin id，但 kwargs RHS 仍需字段智能）

completion 候选分层（稳定排序 + 标注）：
- 在 `fields.*.call_by`：全局可见 field_id 为主（允许补充其它候选但低优先）
- 在 `outputs[*].aggregate.fields.*.call_by`：`aggregate.fields` 的 out_field_id（最高优先）→ `group_by` field_id（次优先）→ 全局 field_id（低优先 fallback，明确标注以避免误用）

## Capabilities

### New Capabilities

- (none)

### Modified Capabilities

- `yaml-dsl-editor-semantics-core`: 扩展光标抽取与 token 解析，支持从 `call_by` kwargs 值抽取 field-id 引用。
- `yaml-dsl-lsp-server`: 在 `call_by` kwargs 值位置提供 field hover/definition/completion。
- `yaml-dsl-lsp-notebooks-regression`: 增加 fixtures 回归点，覆盖 `call_by` kwargs 值的字段智能（不得崩溃）。

## Impact

- 主要影响 `packages/scalim-yaml-dsl-lsp/` 的 cursor extraction 与 LSP handlers（completion/hover/definition）分流逻辑。
- 将新增/调整 pytest 覆盖（token 抽取、LSP server 行为、notebooks fixtures 回归）。
