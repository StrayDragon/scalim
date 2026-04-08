## ADDED Requirements

### Requirement: should_retry callback signature MUST be prechecked when enabled

当 loader retry policy 启用（`enabled=true`）且提供 `should_retry` 回调时,系统 MUST 在首次执行前完成签名预检查:

- 系统 MUST 在编译期（或构建 effective policy 时）解析 `should_retry` 为 callable（若其来源为安全引用,仍受 allowlist/builtin vocabulary 约束）。
- 当 `inspect.signature(should_retry)` 可用时,系统 MUST 预检查其能接受 `should_retry(exc, ctx)` 调用形态（至少 2 个位置参数或 `*args` 覆盖该形态）。
- 预检查失败 MUST fail-fast 作为配置/编译错误（不得在第一次 loader 异常后才触发 `TypeError`）。

#### Scenario: keyword-only should_retry is rejected early
- **GIVEN** 用户启用 retry 且 `should_retry` 的签名为 `def should_retry(*, exc, ctx): ...`
- **WHEN** 系统构建 effective retry policy 并执行 callable preflight
- **THEN** MUST fail-fast 并提示 `should_retry` 需要接受位置参数 `(exc, ctx)`
