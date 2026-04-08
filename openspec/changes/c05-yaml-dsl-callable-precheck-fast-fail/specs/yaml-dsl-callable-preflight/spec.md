## ADDED Requirements

### Requirement: callable preflight MUST run at the resolver boundary and fail-fast

系统 MUST 在 demand runtime compile（以及 workflow preflight 中对每个 run 的 demand compile）阶段,在“resolver 已就绪”边界执行 callable preflight,并在发现第一个可推理错误时立即 fail-fast 抛出配置/编译错误:

- callable preflight MUST 在 allowlist/builtin vocabulary 已生效的 resolver 可用后执行（不得在缺失安全边界的情况下尝试导入/解析用户引用）。
- callable preflight MUST 覆盖所有“用户可配置为 Python callable”的入口点（至少包含 `loader`、派生字段 `call_by`、聚合后派生字段 `call_by`、`normalize.call_by`、`should_retry` 以及 `compute` 的安全内置函数调用形态检查）。
- callable preflight MUST NOT 执行用户 callable（不得调用函数体）,仅允许解析引用与做签名/形态/固定 contract 校验。
- callable preflight 失败 MUST 被归类为 compile/config error,不得进入运行期 guardrails 的 quiet/吞错语义。

#### Scenario: call_by signature mismatch fails at compile time
- **GIVEN** 派生字段声明 `call_by: "pkg.mod:fn(x)"` 且 `fn` 的 Python 签名为 keyword-only（例如 `fn(*, x)`）
- **WHEN** 调用方执行 demand `compile/run`（或 workflow preflight 执行到 demand compile）
- **THEN** 系统 MUST 在编译期失败并报告“参数绑定不匹配”
- **AND** MUST NOT 进入运行期执行（不得把该错误吞掉并将字段写为 `None`）

### Requirement: callable preflight diagnostics MUST be actionable and include rewrite hints

当 callable preflight 因“参数绑定不匹配”失败时,错误诊断 MUST 至少包含:

- callsite location（例如 `派生字段 '<field_id>'` / `outputs.<name>.aggregate.fields.<field_id>` / `sources.<id>.normalize.call_by`）
- callable reference（例如 `pkg.mod:fn`）
- `inspect.signature` 形式的签名文本（当可用）
- `TypeError` 的绑定失败原因摘要
- 至少一个可照抄的迁移建议（例如把位置参数改写为关键字参数 `x=x`）

#### Scenario: keyword-only rewrite hint is provided
- **GIVEN** `call_by: "pkg.mod:fn(group_name)"` 且目标函数签名为 `fn(*, group_name)`
- **WHEN** 系统执行 callable preflight
- **THEN** 编译失败的错误信息 MUST 包含可照抄的改写建议 `fn(group_name=group_name)`
