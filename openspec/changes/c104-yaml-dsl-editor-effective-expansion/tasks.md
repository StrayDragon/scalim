## 1. Effective Expansion（editor 视角）

- [ ] 1.1 以内存态 YAML 文本为输入：缓存 ruamel parse + effective expansion（`document_uri + document_version`）
- [ ] 1.2 Phase 1：支持 anchors/aliases/merge key + `outputs[*].fields` nested list flatten
- [ ] 1.3 Phase 2：imports/$import 展开（受 allowed-roots 约束）+ `(path, mtime_ns)` 缓存 + in-flight 去重
- [ ] 1.4 展开失败必须可诊断且降级为空结果（不 crash、不阻塞编辑）

## 2. `outputs[*].fields` 导航（基于 effective view）

- [ ] 2.1 基于展开结果构建 outputs.fields 的 field_id 列表（含 alias 展开）
- [ ] 2.2 completion：补全可用 field_id
- [ ] 2.3 definition/hover：field_id → 字段定义（主文件或 fragment 文件）
- [ ] 2.4 alias token：definition 跳到 anchor 定义；hover 展示展开摘要（规模/片段）

## 3. Validation

- [ ] 3.1 fixtures：anchors/aliases/flatten/imports 覆盖（含失败降级与 trace）
- [ ] 3.2 运行 `just qa` + LSP notebooks regression
- [ ] 3.3 运行 `just openspec-check`
