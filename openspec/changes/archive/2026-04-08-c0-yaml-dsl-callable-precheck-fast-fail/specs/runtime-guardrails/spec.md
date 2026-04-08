## ADDED Requirements

### Requirement: runtime guardrails MUST NOT swallow callable preflight failures

系统 MUST 将 callable preflight 失败定义为配置/编译错误边界:

- callable preflight 失败 MUST 在 engine 执行前 fail-fast 抛出（例如 demand compile 或 workflow preflight 阶段）。
- 运行期 guardrails（包括 `guardrails.mode=quiet` 与 `guardrails.compute.on_error`）MUST NOT 将此类错误降级为 `None` 或静默记录后继续执行。

#### Scenario: compute quiet mode does not convert preflight failure to None
- **GIVEN** `guardrails.enabled=true` 且 `guardrails.mode=quiet`
- **AND** demand 配置存在可推理的 callable preflight 失败（例如 `call_by` 位置参数绑定到 keyword-only 签名）
- **WHEN** 调用方执行 demand `run`
- **THEN** 系统 MUST 在运行前失败并抛出编译错误
- **AND** MUST NOT 继续执行并将该字段写为 `None`
