## 1. workflow books patch helper（方案 B）

- [ ] 1.1 新增 `src/scalim/dsl/yaml_dsl/_internal/patch_apply.py`：提供通用 helper（unknown key 检测、类型窄化 mapping/bool/str/int、path 拼接与一致的错误口径）
- [ ] 1.2 使用 `_internal/patch_apply.py` 的 helper 重构 `src/scalim/dsl/yaml_dsl/workflow_compile.py` 中 `_overlay_book_write_defaults_patch` 与 `_apply_book_patch`：降低复杂度并尽量移除 `# noqa: C901` 放行（保持行为与调用顺序不变）

## 2. 回归对拍（行为不变 + 错误口径稳定）

- [ ] 2.1 增加/整理 workflow compile 对拍用例：unknown key 报错 path；write_defaults 枚举校验；budget/export_xlsx 嵌套字段错误口径
- [ ] 2.2 跑 `just quick-qa-only-py` 确认 workflow layering gate 与 tests suites gate 不回归

## 3. 规范同步与验收门禁

- [ ] 3.1 将本 change 的 delta 规范同步到 SSOT：更新 `openspec/specs/yaml-dsl-books-resources/spec.md` 补充 “book patches MUST be validated strictly and consistently” 的要求
- [ ] 3.2 运行 `just openspec-check` 校验 OpenSpec 工件
