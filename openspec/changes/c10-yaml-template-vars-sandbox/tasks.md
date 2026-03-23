## 1. LiteJinja2 sandbox/legacy 开关（SSOT：yaml-template-vars-sandbox）

- [ ] 1.1 为 `src/scalim/vendor/litejinja2/__init__.py` 增加 sandbox/legacy 控制参数（建议通过 `Template.render(..., sandbox_mode=...)` 或等价方式向下传递）
- [ ] 1.2 在变量解析处实现默认 sandbox gate：禁止 `part.endswith(\"()\")` 的无参方法调用、禁止以下划线开头属性访问（含 dict/非 dict 两条路径），并抛出可诊断的 `TemplateError`
- [ ] 1.3 legacy 模式下保持现有行为，但必须提供调用方显式 opt-in 的入口（不得默认开启）

## 2. YAML 预编译入口：默认 sandbox + 显式 legacy opt-in

- [ ] 2.1 更新 `maybe_precompile_yaml_text(...)`：在 `template_vars is not None` 时默认启用 sandbox；并新增可选参数暴露 legacy opt-in（命名以实现时统一）
- [ ] 2.2 增加 `template_vars` 的 JSON/YAML-like 输入护栏：递归校验类型与 dict key 口径；遇到非安全类型默认 fail-fast（错误信息不包含值明细）
- [ ] 2.3 将 legacy opt-in 开关接入高层入口（建议：`RunOptions` / `scalim.dsl.by_yaml.run/compile`），并在启用 legacy 时输出强 warning（至少日志 warning；可选诊断事件）

## 3. Tests（可验证、可回归）

- [ ] 3.1 新增测试：默认 sandbox 下 `{{ p.open().read() }}` 必须 fail-fast（错误信息指向 method call 禁止）
- [ ] 3.2 新增测试：默认 sandbox 下访问 `_`/`__dunder__` 属性必须 fail-fast（错误信息指向 underscore 属性禁止）
- [ ] 3.3 新增测试：常见替换用法保持可用（变量、dict key、list/tuple index）
- [ ] 3.4 新增测试：legacy 模式允许方法调用/属性访问，且会发出强 warning（warning 仅作为提示；不应依赖 observer/hook 才可见）
- [ ] 3.5 新增测试：`template_vars` 注入非安全类型（例如 `Path`）在默认策略下 fail-fast（并且错误信息不泄露值明细）

## 4. Final Gates

- [ ] 4.1 运行 `just openspec-check` 确保 OpenSpec 工件通过校验
- [ ] 4.2 运行 `just qa`（或最小子集）确保无 lint/test 回归
