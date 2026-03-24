## Context

`PreloadCache` 以 `source_id` 作为 key,默认语义是 per-key `in-flight` 去重与结果复用。该 key 空间不足以表达 loader/params/normalize 等影响结果的 signature,因此在“跨不同 demand/不同上下文共享同一个 `PreloadCache`”时存在错误复用风险。

本变更为后置治理: 在不改变默认 key 空间的前提下,为共享场景提供可选 guardrail,并给出明确且可诊断的失败/告警口径。

## Decisions

- guardrail 默认关闭（不改变默认行为）；由调用方显式开启（例如 runtime option 或 `PreloadCache` 初始化参数）。
- signature digest 的 SSOT:
  - 优先复用 `WorkflowCacheEntrySignature` 的 canonicalization/digest（同一份 `rendered_params` / `normalize` / `key` / `lookup_cast` 口径）
  - 由 preload 调用点计算 digest 并传入 `PreloadCache`（避免 `PreloadCache` 依赖 `SourceIr` 结构）
- 策略:
  - MVP: `error|warn`
  - 以后若需要 `separate`,应作为显式扩展（这会改变 key 空间,需要更完整的迁移设计）

## Risks

- 需要改造 `PreloadCache.get_or_load` 调用链以携带 signature 信息（可能涉及公共 API 变更）；本仓库倾向“全量升级并改完所有 call sites”,避免双轨兼容层。
- 错误信息必须可诊断且稳定（用于 CI/排障）；同时避免泄漏敏感字面量（必要时仅输出 digest 与字段名差异）。
