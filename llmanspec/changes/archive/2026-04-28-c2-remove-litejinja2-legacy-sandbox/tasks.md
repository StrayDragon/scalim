## 1. Remove Legacy Sandbox Support

- [x] 1.1 在 `src/scalim/vendor/litejinja2/__init__.py` 中移除 `template_sandbox=legacy` 分支:
  - 默认值改为 `safe`
  - 允许值集合收敛为 `{safe}`
  - method call 语法(`x.y()`)在渲染阶段一律 fail-fast
- [x] 1.2 在 `src/scalim/dsl/yaml_dsl/_internal/config_parsing/template_precompile.py` 中移除 legacy 允许值与 warning 分支,仅允许 safe
- [x] 1.3 在 `src/scalim/dsl/yaml_dsl/runtime/unsafe_entrypoints.py` 中移除 legacy 允许值与弃用 warning 分支,仅允许 safe

## 2. Update Tests

- [x] 2.1 删除/改写所有 `template_sandbox="legacy"` 的测试用例,改为覆盖 safe-only 行为
- [x] 2.2 增补回归测试: method call 在 safe-only 下必须 fail-fast,且错误信息可诊断

## 3. Specs

- [x] 3.1 按本 change 的 delta spec 更新 `yaml-template-vars` 契约(legacy removed)

## 4. Verification

- [x] 4.1 运行 `just qa`
- [x] 4.2 运行 `just openspec-check`
