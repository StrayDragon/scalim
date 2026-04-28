## Context

- `template_vars` 预编译入口位于:
  - `src/scalim/dsl/yaml_dsl/_internal/config_parsing/template_precompile.py` (最终调用 `litejinja2.Template.render(..., template_sandbox=...)`)
  - `src/scalim/vendor/litejinja2/__init__.py` (实现 `template_sandbox` 的具体行为)
  - `src/scalim/dsl/yaml_dsl/runtime/unsafe_entrypoints.py` (非公共入口仍允许 legacy)
- 现状问题:
  - `LiteJinja2.Template.render` 默认 `template_sandbox="legacy"`
  - legacy 模式允许无参方法调用 `x.y()`，且会对对象做 `getattr`/call
  - 测试与 specs 中仍包含 legacy 分支描述

## Goals / Non-Goals

Goals:
- 移除 legacy sandbox: code/spec/tests 三者一致,只保留 safe 语义。
- 默认行为安全化: `LiteJinja2` 内部默认 sandbox 为 safe。
- 错误信息保持可诊断: 当发现 method call 或 legacy 参数时 fail-fast 并提供迁移提示。

Non-Goals:
- 不引入更强的表达式能力(例如 tojson/toyaml 等过滤器)。
- 不改变 safe 模式下允许的 JSON-like 渲染与属性访问规则(除去 method call)。

## Decisions

1. legacy sandbox 完全移除 (BREAKING)
- `template_sandbox` 参数仍可保留其“形状”用于显式声明 safe,但允许值集合收敛为 `{"safe"}`。
- 所有入口(包括 unsafe)收到 `legacy` MUST fail-fast。

2. LiteJinja2 内部默认值改为 safe
- `Template._template_sandbox` 与 `Template.render(..., template_sandbox=...)` 的默认值统一为 safe。

3. method call 语法统一禁止
- 在模板节点扫描阶段与渲染阶段都保持 fail-fast:
  - 扫描阶段: `template_precompile._scan_template_expr_sandbox_violation` 已能发现 `()` 并报错
  - 渲染阶段: litejinja2 的变量解析中遇到 `()` 一律抛 `TemplateError`

## Risks / Trade-offs

- [风险] 外部调用方仍使用 legacy 将直接失败。
  - 缓解: 错误信息提供明确迁移动作: 删除参数或改为 `safe`。

- [风险] 代码删除 legacy 分支后,可能暴露出此前仅在 legacy 测试覆盖的边界。
  - 缓解: 补充 safe-only 测试覆盖,尤其是 method call fail-fast 与 `_` 属性访问 fail-fast。

## Migration Plan

- 删除或替换所有 `template_sandbox="legacy"` 的调用点(仓库内测试/示例优先)。
- 更新 OpenSpec `yaml-template-vars` 规范,将 legacy 相关要求移入 REMOVED(附带 Migration)。

## Open Questions

- 是否要把 `template_sandbox` 参数从公开 API 中完全移除(仅保留 safe 默认),以进一步减少误用面?
> 需要 完全删除 并且尽可能保留内部可以快速复原, 以保证万一之后需要调整支持 也可以处理