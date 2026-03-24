## 1. Specs

- [ ] 1.1 更新 `openspec/specs/source-cache/spec.md`: 增加 guardrail 的开关与策略语义（默认关闭；`error|warn`）
- [ ] 1.2 更新 `openspec/specs/source-cache/spec.md`: 明确 signature digest 的 SSOT 与字段覆盖范围（对齐 `WorkflowCacheEntrySignature`）
- [ ] 1.3 运行 `just openspec-check`

## 2. Implementation

- [ ] 2.1 为 `PreloadCache` 增加 signature 记录与冲突检测（按策略 `error|warn`）
- [ ] 2.2 在 preload 调用点计算并传入 signature digest（不引入旧入口兼容层,全量升级 call sites）
- [ ] 2.3 补齐最小单测: 同 `source_id` 不同 signature 的误用 fail-fast/告警

## 3. Final Gates

- [ ] 3.1 运行 `just qa`
