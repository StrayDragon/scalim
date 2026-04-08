## 1. Cursor Extraction（表达式 token）

- [x] 1.1 在 scalar 文本内提取 identifier token（`[A-Za-z_][A-Za-z0-9_]*`）并返回精确 range
- [x] 1.2 覆盖位置：`fields.*.compute` / `outputs[*].where` / `outputs[*].aggregate.fields.*.compute`

## 2. Scope Index（可解释且尽量贴近运行时）

- [x] 2.1 构建 doc 级 FieldDefIndex + per-output scope index（缓存于 DocumentState）
- [x] 2.2 scope 规则：
  - `fields.*.compute`: 全字段（歧义需可解释）
  - `outputs[*].where`: 不收窄（与运行时允许集合对齐为下界），仅在排序/提示上增强
  - `outputs[*].aggregate.fields.*.compute`: 仅 `group_by` + `aggregate.fields`

## 3. LSP 接入（completion / hover / definition）

- [x] 3.1 completion：按 scope 输出候选并稳定排序
- [x] 3.2 definition：field token → 字段定义（歧义返回多 locations，依赖 `yaml-dsl-lsp-resolution-infra`）
- [x] 3.3 hover：字段摘要 + scope explain（为何在此处可用）

## 4. Validation

- [x] 4.1 fixtures：拼写错误、歧义、aggregate scope 等覆盖
- [x] 4.2 运行 `just qa` + LSP notebooks regression
- [x] 4.3 运行 `just openspec-check`
