## 1. Resolver trusted-mode + wildcard 语义收敛（默认 fail-fast）

- [ ] 1.1 为 `RunOptions` 与 `scalim.dsl.by_yaml.run/compile` 增加 `resolver_trusted_mode`（enum；默认 `strict_allowlist`），并在所有错误/告警文案中统一该命名
- [ ] 1.2 在校验层实现 `"*"` 默认拒绝：`resolver_trusted_mode=strict_allowlist` 且 allowlist 含 `"*"` 时 fail-fast，错误信息包含迁移建议（trusted-mode / 显式 allowlist）
- [ ] 1.3 `resolver_trusted_mode=trusted_allow_all_modules` 下允许“全放开模块”配置，并发出强 warning（稳定前缀 + `k=v` 字段；不依赖 observer/hook 才可见）
- [ ] 1.4 一律拒绝 `allowed_functions={"*"}`（以及其与 `allowed_modules` 的混用）；错误信息必须给出替代方案（仅 allowed_modules / trusted-mode）
- [ ] 1.5 `resolver_trusted_mode=trusted_allow_all_modules` 与显式 allowlist（`allowed_modules/allowed_functions`）混用 MUST fail-fast（避免“部分约束仍生效”的错觉）

## 2. 移除 denylist-only escape hatch（严格失败 + 友好提示）

- [ ] 2.1 移除 `ConfigToIRConverter(allow_unsafe_resolver=...)` 参数（或将其改为内部不可达的明确 unsafe entrypoint；以实现时最终决定为准）
- [ ] 2.2 缺少 allowlist 时一律严格失败（fail-fast），并在错误信息中给出可复制的修复示例（如何配置 `allowed_modules`/`allowed_functions`）
- [ ] 2.3 若代码中仍保留任何 denylist-only 入口：必须显式标注 `unsafe`，且不得通过环境变量隐式改变框架行为（本变更倾向不保留）

## 3. Tests（可验证、可回归）

- [ ] 3.1 新增测试：`allowed_modules={"*"}` 在 `resolver_trusted_mode=strict_allowlist` 时必须 fail-fast（断言错误信息包含迁移建议）
- [ ] 3.2 新增测试：`resolver_trusted_mode=trusted_allow_all_modules` + 全放开模块配置允许执行且会发出强 warning（一次运行去重可选）
- [ ] 3.3 新增测试：`allowed_functions={"*"}` 必须 fail-fast（含与 `allowed_modules` 混用场景）
- [ ] 3.4 新增测试：`resolver_trusted_mode=trusted_allow_all_modules` 与显式 allowlist 混用必须 fail-fast
- [ ] 3.5 新增测试：推荐用法“仅 allowed_modules 不设置 allowed_functions”仍保持“模块约束 + 函数不约束”的语义（避免引入意外收紧）
- [ ] 3.6 新增测试：不依赖 observer/hook 时也可观测到 trusted-mode 的强告警（例如使用 `warnings` 或 fallback logger 之一；以实现为准）

## 4. Final Gates

- [ ] 4.1 运行 `just openspec-check` 确保 OpenSpec 工件通过校验
- [ ] 4.2 运行 `just qa`（或最小子集）确保无 lint/test 回归
