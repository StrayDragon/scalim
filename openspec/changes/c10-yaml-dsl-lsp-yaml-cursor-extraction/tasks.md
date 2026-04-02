## 1. Shared core API 设计与对外契约

- [ ] 1.1 定义 cursor-extraction 的返回结构（`yaml_path`/`reference`/`range`/`warnings`），并明确 core 使用 1-based（server 负责转 0-based）
- [ ] 1.2 明确 v1 支持字段集合：`loader`/`call_by`/`retry.should_retry`，并定义 canonical dot path 口径

## 2. 实现：YAML 光标抽取

- [ ] 2.1 在 `packages/scalim-yaml-dsl-lsp/` 新增 cursor-extraction 模块（静态解析、无副作用、失败降级）
- [ ] 2.2 实现 `call_by` 头部解析（`ref(args...) -> ref`）并精确计算 head range
- [ ] 2.3 将 cursor-extraction 接入 shared core 的公共 API（供 server/测试调用）

## 3. 测试与验证

- [ ] 3.1 添加单元测试覆盖：引号/不带引号、`module:attr`/`module.attr`、`call_by(args)` head range、光标在值外返回空
- [ ] 3.2 添加降级测试：YAML 语法错误/解析异常时返回空结果 + warnings（不得 crash）
- [ ] 3.3 运行 `just openspec-check` 确认 OpenSpec 工件结构与 schema 校验通过

