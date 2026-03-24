# preload-cache-concurrent-load-scenarios Specification

## Purpose
TBD - created by archiving change c70-preload-cache-concurrent-load-scenarios. Update Purpose after archive.
## Requirements
### Requirement: concurrency scenarios MUST be explicit and reproducible
系统 MUST 明确并提供可复现的说明，至少覆盖：

- 多线程并发多个 `ScalimEngine.run()` 且共享同一个 `preloaded_cache`（当 `preloaded_cache` 提供 `get_or_load` 时，应按 key 做 in-flight 去重）
- workflow 多节点并发请求同一 `WorkflowCachePool` signature（同一 signature 同一时刻最多一个实际 `load_fn` 运行）

系统 MUST 明确默认语义仅为 **in-flight 去重**，不承诺跨进程去重。

#### Scenario: two concurrent callers trigger at most one in-flight load per key
- **GIVEN** 两个并发执行单元（线程或 workflow node）请求同一缓存 key（`source_id` 或 signature）
- **WHEN** 该 key 当前为 miss
- **THEN** 系统 MUST 保证同一时刻最多一个实际 `load_fn` 被执行
- **AND** 其余请求 MUST 等待并复用该次 load 的结果或异常

### Requirement: loader idempotency expectations MUST be explicit
当系统允许出现“同一逻辑数据源在并发场景下被重复触发 load”的可能性时（例如多 engine 共享 `PreloadCache`、workflow 多 node 并发请求），系统 MUST 明确并文档化 loader 的幂等性期望与风险边界：

- 文档 MUST 明确说明：loader 实现 SHOULD 尽量满足幂等性（重复调用应产生等价结果或在可接受范围内一致）
- 文档 MUST 明确说明：不应依赖“永不并发/永不重复调用”的隐式假设来保证正确性
- 若 loader 不可幂等（例如包含外部副作用），文档 MUST 明确提示风险，并建议调用方避免跨不同配置/不同 signature 复用同一 `PreloadCache`，或在后续启用更强 guardrail（若提供）

#### Scenario: preload_forever docs mention idempotency expectations
- **WHEN** 系统文档描述 `preload_forever` / `PreloadCache` 的并发边界与 in-flight 去重语义
- **THEN** 文档 MUST 同时包含关于 loader 幂等性（SHOULD）与非幂等风险的明确说明

