## Why

`PreloadCache.get_or_load(source_id, load_fn)` 的 key 仅为 `source_id`。当调用方在多次执行之间**共享同一个** `PreloadCache`（或其它 `preloaded_cache` 容器）时,若同名 `source_id` 在不同 demand/不同上下文下实际对应不同的 loader/params/normalize,则可能发生**静默错误复用**:

- 第二次执行命中旧值,`load_fn` 不再触发
- 结果看似“性能更好”,但数据语义已经错了

这类误用在并发/多 engine/workflow 场景更容易出现（参见 `preload-cache-concurrent-load-scenarios`）,因此需要一个可选的 guardrail 让问题在开发/测试阶段被尽早暴露。

## What Changes

为 `PreloadCache` 增加可选的 signature guardrail,用于在共享容器场景下检测“同一 `source_id` 被不同 signature 复用”的风险:

- 调用点在 preload 阶段为 `source_id` 计算可复现的 signature（至少包含 `loader_ref` / 渲染后的 `params` / `normalize` / `key` / `lookup_cast` 等关键字段）
- `PreloadCache` 记录每个 `source_id` 对应的 signature digest
- 当同一 `source_id` 再次被请求但 signature digest 不一致时,按策略处理（至少支持 `error|warn`）
  - `error`: fail-fast,并给出可诊断差异摘要/迁移提示
  - `warn`: 继续执行但产生强告警（用于迁移窗口）

非目标:
- 不把本变更与 `workflow-cache-pool` 合并（workflow 的 signature-based 复用仍由 `WorkflowCachePool` 承担）
- 不把 `PreloadCache` 默认语义从 `source_id` key 变成 signature key（默认仍是“按 `source_id` 做 `in-flight` 去重与结果复用”）

## Acceptance

- 新增回归测试覆盖误用场景:
  - **GIVEN** 共享同一个 `PreloadCache`
  - **WHEN** 第一次执行以 signature A preload `source_id="s1"`
  - **AND** 第二次执行以 signature B preload 同一 `source_id="s1"` 且 A!=B
  - **THEN** 在 `error` 策略下 MUST fail-fast（错误信息包含 `source_id`、两次 digest、diff 字段或迁移提示）
- 在正常场景（同 signature 重复执行或并发 wait）下,行为 MUST 与当前实现一致（不引入额外数据竞态/死锁）
- `just qa` 与 `just openspec-check` 全绿

## Notes

- 本变更属于行为增强/护栏,需要同步 `source-cache` spec（明确 guardrail 的默认关闭/开启方式与策略语义）。
- 具体 signature 结构建议复用 `WorkflowCacheEntrySignature` 的 canonicalization/digest 口径,以减少重复设计与漂移风险。
