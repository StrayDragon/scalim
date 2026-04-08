## ADDED Requirements

### Requirement: demand compile MUST run callable preflight before building the execution request

系统 MUST 在 demand runtime compile 中引入明确的 callable preflight 阶段,并保证该阶段发生在:

- resolver/allowlist/builtin vocabulary 已就绪之后
- DemandIr 与 ExecutionRequest 构建之前

callable preflight MUST 覆盖所有可推理的 callable 误配（例如“参数绑定不匹配”/“固定 contract 不满足”）,并在失败时直接 fail-fast 抛出配置/编译错误。

（包含但不限于: `call_by` 绑定错误、`compute` SAFE_FUNCTIONS 的可推理调用形态错误、`sources.*.normalize.call_by` / `retry.should_retry` 签名不匹配、以及 loader `params` kwargs keys 与签名不一致。）

#### Scenario: preflight prevents silent compute swallowing
- **GIVEN** 某派生字段 `call_by` 将位置参数传给 keyword-only 函数签名
- **WHEN** 调用方执行 demand `compile/run`
- **THEN** 系统 MUST 在 compile 阶段失败
- **AND** MUST NOT 继续进入 engine 执行并将该字段写为 `None`

### Requirement: callable preflight MUST be independent of runtime guardrails mode

callable preflight 属于配置/编译错误边界,系统 MUST 保证其 fail-fast 语义不受运行期 guardrails 的 `mode=quiet|fast_fail` 与 `guardrails.compute.on_error` 等策略影响。

#### Scenario: quiet guardrails does not suppress preflight errors
- **GIVEN** `guardrails.enabled=true` 且 `guardrails.mode=quiet`
- **AND** demand 配置中存在可推理的 callable preflight 失败（例如 `call_by` 参数绑定不匹配）
- **WHEN** 调用方执行 demand `compile/run`
- **THEN** 系统 MUST 仍然 fail-fast 抛出编译错误
