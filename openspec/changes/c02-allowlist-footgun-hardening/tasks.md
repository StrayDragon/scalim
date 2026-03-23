## 1. Resolver trusted-mode + wildcard 语义收敛（默认 fail-fast）

- [ ] 1.1 为 `RunOptions` 与 `scalim.dsl.by_yaml.run/compile` 增加显式 trusted-mode（命名在实现时最终确定，并在文档/错误信息中统一）
- [ ] 1.2 在 resolver policy 层实现 `"*"` 默认拒绝：`trusted_mode=false` 且 allowlist 含 `"*"` 时 fail-fast，错误信息包含迁移建议（trusted-mode / 显式 allowlist）
- [ ] 1.3 trusted-mode 下允许“全放开模块”配置，并发出强 warning（至少 warning 日志；可选诊断事件但不得依赖其可见性）
- [ ] 1.4 拒绝 `allowed_functions={"*"}`（以及其与 `allowed_modules` 的混用），并在错误信息中给出等价替代方案（仅 allowed_modules / trusted-mode）

## 2. denylist-only（不安全）模式：重命名 + 双确认 gate

- [ ] 2.1 将 `ConfigToIRConverter(allow_unsafe_resolver=...)` 改为更不易误解的命名（denylist-only），并更新所有引用点（含类型/文档）
- [ ] 2.2 实现双确认 gate：参数显式启用 + 环境变量（例如 `SCALIM_UNSAFE_DENYLIST_ONLY=1`）同时满足才允许继续；缺失时 fail-fast 并提示如何正确启用
- [ ] 2.3 互斥规则：denylist-only 与 allowlist/trusted-mode 同时出现必须 fail-fast（避免“看起来安全其实不安全”）

## 3. Tests（可验证、可回归）

- [ ] 3.1 新增测试：`allowed_modules={"*"}` 在 `trusted_mode=false` 时必须 fail-fast（断言错误信息包含迁移建议）
- [ ] 3.2 新增测试：`trusted_mode=true` + 全放开模块配置允许执行且会发出强 warning（一次运行去重可选）
- [ ] 3.3 新增测试：`allowed_functions={"*"}` 必须 fail-fast（含与 `allowed_modules` 混用场景）
- [ ] 3.4 新增测试：denylist-only 缺环境变量确认时 fail-fast；具备确认信号时允许继续并发出强 warning
- [ ] 3.5 新增测试：推荐用法“仅 allowed_modules 不设置 allowed_functions”仍保持“模块约束 + 函数不约束”的语义（避免引入意外收紧）

## 4. Final Gates

- [ ] 4.1 运行 `just openspec-check` 确保 OpenSpec 工件通过校验
- [ ] 4.2 运行 `just qa`（或最小子集）确保无 lint/test 回归
