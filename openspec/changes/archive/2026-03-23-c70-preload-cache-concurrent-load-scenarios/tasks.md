## 1. Specs 同步（边界清晰 + 可复现）

- [ ] 1.1 更新 `openspec/specs/source-cache/spec.md`：补充 `preloaded_cache/PreloadCache` 的并发触发场景与 key 空间说明（强调仅 in-flight 去重；跨不同 signature 复用 `source_id` 的风险与责任边界）
- [ ] 1.2 更新 `openspec/specs/source-cache/spec.md`：将 “loader SHOULD be idempotent（或等价约束）” 提升为显式条款（至少 SHOULD），并明确其适用背景（多 engine / workflow 并发与重复加载不可完全避免）
- [ ] 1.3 更新 `openspec/specs/workflow-cache-pool/spec.md`：补充 workflow 多 node 并发请求同一 signature 的 in-flight 去重语义与复现路径（fixture/测试引用）
- [ ] 1.4 运行 `just openspec-check` 确保 specs 结构与 OpenSpec 校验通过

## 2. Repro / Tests（最小可运行）

- [ ] 2.1 复核并在 spec 中引用现有回归测试：`tests/test_preload_cache.py::test_preload_cache_get_or_load_returns_cached_value_inside_lock`
- [ ] 2.2 若缺少 workflow cache_pool 并发复现测试：新增单测覆盖“同一 signature 同时最多一次真实 load_fn 执行，其余等待并复用结果/异常”
- [ ] 2.3 创建后置 change（仅 proposal.md 即可）：`c7x-*`（或 `c700-*`）用于 `PreloadCache` signature guardrail（检测跨不同 signature 复用同一 `source_id` 时 fail-fast/告警）的行为变更设计与验收口径

## 3. Final Gates

- [ ] 3.1 运行 `just qa` 确保无 lint/test 回归
