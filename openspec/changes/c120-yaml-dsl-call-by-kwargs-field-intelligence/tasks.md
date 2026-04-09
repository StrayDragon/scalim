## 1. Cursor Extraction (call_by args)

- [ ] 1.1 在 `call_by` 字符串内实现 kwargs value token 抽取（仅 `=` 右侧；返回精确 range；失败降级为空 + warnings）
- [ ] 1.2 支持空值抽取（`x=` / `x= <cursor>`）以启用 Ctrl+Space completion
- [ ] 1.3 增加回归：确保光标在 `pkg.mod:fn` head 区间时仍按现有规则抽取 Python reference（不受参数段影响）

## 2. LSP Features (field intelligence in call_by kwargs values)

- [ ] 2.1 hover：对 kwargs value token 返回字段卡片；不可解析时返回空但不崩溃
- [ ] 2.2 definition：kwargs value token → 跳转到字段声明（含跨 imports 展开）
- [ ] 2.3 completion：kwargs value token/空值位置 Ctrl+Space 返回 field ids 候选
- [ ] 2.4 明确边界：kwargs 名称（`=` 左侧）不提供 field hover/definition/completion

## 3. Regression & Fixtures

- [ ] 3.1 单元测试：覆盖 `call_by: "pkg.mod:fn(x=a)"` 的 token 抽取（value 命中 / name 不命中 / 空值）
- [ ] 3.2 LSP server 测试：对 kwargs value token 验证 completion/definition/hover（至少覆盖 demo/fixture 中的真实 call_by 样例）
- [ ] 3.3 notebooks 回归：将 call_by kwargs value token 纳入 fixtures-derived 操作回归（不得崩溃；允许空结果但必须有 warnings）

## 4. Spec / QA

- [ ] 4.1 实现完成后运行 `just openspec-check`，确保本 change 的 delta specs 结构与 sanitize 校验通过
- [ ] 4.2 运行 `just qa`，确保 lint/tests/drift gates 通过
