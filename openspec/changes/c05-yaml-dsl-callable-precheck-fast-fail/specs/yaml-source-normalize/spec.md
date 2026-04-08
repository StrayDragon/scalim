## ADDED Requirements

### Requirement: normalize.call_by signature MUST be prechecked at compile time when possible

当 source 声明 `sources.<id>.normalize.call_by` 时,系统 MUST 在编译期执行可推理的签名/形态预检查:

- 系统 MUST 在编译期解析引用为 callable（受 allowlist/builtin vocabulary 约束）。
- 当 callable 的签名可通过 `inspect.signature` 获取时,系统 MUST 在编译期预检查其可接受的入参形态:
  - MUST 至少接受 `result` 作为第一个位置参数（或 `*args` 覆盖该位置）
  - `ctx` MAY 以第二个位置参数或关键字参数形式被接受（例如 `fn(result, ctx)` / `fn(result, ctx=ctx)` / `fn(result, *, ctx)` / `fn(result, **kw)`）
- 预检查失败 MUST fail-fast 作为配置/编译错误（不得延迟到运行期再失败）。

#### Scenario: keyword-only result is rejected early
- **GIVEN** `sources.s1.normalize.call_by: "pkg.mod:norm"`
- **AND** `norm` 的签名为 `def norm(*, result): ...`（不接受任何位置参数）
- **WHEN** 系统编译 demand
- **THEN** 编译 MUST fail-fast 并指出 `normalize.call_by` 至少需要一个位置参数 `result`

#### Scenario: result + ctx positional signature is accepted
- **GIVEN** `sources.s1.normalize.call_by: "pkg.mod:norm"`
- **AND** `norm` 的签名为 `def norm(result, ctx): ...`
- **WHEN** 系统编译 demand
- **THEN** 编译 MUST 通过 callable preflight
