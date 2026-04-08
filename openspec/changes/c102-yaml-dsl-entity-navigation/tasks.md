## 1. Cursor Extraction（range 精度）

- [ ] 1.1 支持复合引用子 token range：`source_id.field_id`（区分 source/field 两段）
- [ ] 1.2 覆盖 workflow run 引用等位置的 scalar value token 提取
- [ ] 1.3 单元测试：range 精度（引号/空格/点号/边界）与“无结果但可诊断”降级

## 2. Entity Index（单文件）

- [ ] 2.1 从当前 YAML 文档结构构建 entity index：sources/relations/fields/outputs/workflow runs
- [ ] 2.2 提供 SSOT API：resolve → locations + hover summary + completion items

## 3. LSP Feature 接入

- [ ] 3.1 definition：跳到实体 key；歧义返回多 locations（依赖 `yaml-dsl-lsp-resolution-infra` 的排序/去重）
- [ ] 3.2 completion：按引用位置补全 sources/relations/fields/run ids（含 snippet）
- [ ] 3.3 hover：展示实体摘要卡片（静态，只读）
- [ ] 3.4 unknown id：返回空 + hint 级 diagnostic（不 crash）

## 4. Validation

- [ ] 4.1 fixtures：覆盖 `fields.*.source`、`relations.*.steps[*].from/to`、workflow run 引用
- [ ] 4.2 运行 `just qa` + LSP notebooks regression
- [ ] 4.3 运行 `just openspec-check`
