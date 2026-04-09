## 1. Cursor Extraction

- [ ] 1.1 扩展 cursor extraction：识别 `outputs[*].aggregate.group_by[*]` 的 field-id 引用点（含空 list item / 空 scalar）
- [ ] 1.2 扩展 cursor extraction：识别 `aggregate.fields.*.*.field` 与 `aggregate.fields.*.*.fields[*]` 的 field-id 引用点
- [ ] 1.3 扩展 cursor extraction：识别 rank 的 `aggregate.fields.*.rank.*.by` 引用点，并确保不会误命中其它 `by:` 场景

## 2. LSP Features

- [ ] 2.1 completion：为上述 aggregate 引用点返回 field ids（Ctrl+Space 必须可用；空值场景也可用）
- [ ] 2.2 definition：为上述 aggregate 引用点跳转到字段声明（跨 imports 展开也可定位）
- [ ] 2.3 hover：为上述 aggregate 引用点返回字段摘要；不可解析时降级为空结果 + 可诊断 warnings（不得崩溃）

## 3. Regression & Fixtures

- [ ] 3.1 单元测试：补齐 cursor extraction 的覆盖（覆盖空 list item、fields 列表、rank.by）
- [ ] 3.2 LSP server 测试：对 aggregate 引用点验证 completion/definition/hover（至少覆盖 demo `ecommerce_report.yaml` 的真实结构）
- [ ] 3.3 notebooks 回归：将 aggregate 引用点纳入 fixtures-derived 操作回归（不得崩溃；允许空结果但必须有 warnings）

## 4. Spec / QA

- [ ] 4.1 在实现完成后运行 `just openspec-check`，确保本 change 的 delta specs 结构与 sanitize 校验通过
- [ ] 4.2 在归档前运行 `just qa`，确保无 drift/测试失败（specs 同步/归档由后续流程处理）
