## 1. LiteJinja2 sandbox/legacy 开关（SSOT：yaml-template-vars-sandbox）

- [ ] 1.1 为 `src/scalim/vendor/litejinja2/__init__.py` 增加 `template_sandbox` 控制参数（`safe|legacy`；建议通过 `Template.render(..., template_sandbox=...)` 向下传递）
- [ ] 1.2 在变量解析处实现 gate：
  - `template_sandbox="safe"`：禁止 `part.endswith(\"()\")` 的无参方法调用；禁止以下划线开头属性访问（含 dict/非 dict 两条路径）
  - `template_sandbox="legacy"`：允许无参方法调用与非 `_` 属性访问
  - 两种模式下都 MUST 禁止 `_`/`__dunder__` 属性访问（不提供放宽开关）
- [ ] 1.3 错误必须可诊断：抛出 `TemplateError`，错误信息明确指出是 method call 还是 underscore attribute 被禁止

## 2. YAML 预编译入口：默认 sandbox + 显式 legacy opt-in

- [ ] 2.1 更新 `maybe_precompile_yaml_text(...)`：在 `template_vars is not None` 时默认 `template_sandbox=\"safe\"`；并新增参数暴露 `template_sandbox=\"legacy\"`（显式 opt-in）
- [ ] 2.2 增加 `template_vars` 的 JSON/YAML-like 输入护栏（v1 窄版本）：递归校验类型；dict key MUST 为 `str`；遇到非安全类型默认 fail-fast（错误信息不包含值明细）
- [ ] 2.3 将 `template_sandbox` 接入高层入口（`RunOptions` / `scalim.dsl.by_yaml.run/compile`），并在启用 `legacy` 时输出强 warning（稳定前缀 + `k=v` 字段；不依赖 observer/hook 才可见）

## 3. Tests（可验证、可回归）

- [ ] 3.1 新增测试：默认 `template_sandbox=\"safe\"` 下 `{{ p.open().read() }}` 必须 fail-fast（错误信息指向 method call 禁止）
- [ ] 3.2 新增测试：两种模式下访问 `_`/`__dunder__` 属性都必须 fail-fast（错误信息指向 underscore 属性禁止）
- [ ] 3.3 新增测试：常见替换用法保持可用（变量、dict key、list/tuple index）
- [ ] 3.4 新增测试：`template_sandbox=\"legacy\"` 允许无参方法调用/非 `_` 属性访问，且会发出强 warning（warning 仅作为提示；不应依赖 observer/hook 才可见）
- [ ] 3.5 新增测试：`template_vars` 注入非安全类型（例如 `Path`）在默认策略下 fail-fast（并且错误信息不泄露值明细）
- [ ] 3.6 新增测试：dict key 非 `str`（例如 `{1: \"x\"}`）在 v1 护栏下 fail-fast，并指出路径与类型

## 4. Final Gates

- [ ] 4.1 运行 `just openspec-check` 确保 OpenSpec 工件通过校验
- [ ] 4.2 运行 `just qa`（或最小子集）确保无 lint/test 回归
