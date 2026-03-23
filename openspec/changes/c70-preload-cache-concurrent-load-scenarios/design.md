## Context

近期围绕 `cache_mode=preload_forever` 的“同一个 load 是否可能被不同线程同时触发”出现理解偏差，主要集中在两件事：

1) **并发边界**：单个 `ScalimEngine` 实例的 `run()` 有实例级锁保护，但多实例/工作流多 node 场景仍可能并发请求同一缓存 key。
2) **key 空间**：`PreloadCache.get_or_load(source_id, ...)` 的 key 为 `source_id`（不包含 loader/params/normalize signature），而 `WorkflowCachePool.get_or_load(signature, ...)` 的 key 为完整 signature（包含 params/normalize 等）。

当前仓库中已存在实现与测试：

- `src/scalim/execution/preload_cache.py`：`PreloadCache` 的 per-key inflight 去重（同 key 同时最多一个 `load_fn` 实际执行；其余等待并复用结果/异常）。
- `tests/test_preload_cache.py`：覆盖多线程并发等待与异常传播。

约束：

- 运行时需兼容 Python 3.6。
- 本变更的交付物以“文档化 + 可复现说明”为主；不引入新的运行时语义变更（除非发现现有行为与规范不一致且必须修复）。

## Goals / Non-Goals

**Goals:**

- 明确“同一个 load”的定义：在不同缓存容器中，何为同一 key、何为同一 load。
- 明确并发触发场景与边界，并提供可运行的复现路径（至少覆盖：多线程共享 `preloaded_cache`、workflow 多 node 并发）。
- 将上述说明沉淀到规范（spec）与关键实现点附近的可发现注释/文档中，避免继续依赖口头约定。

**Non-Goals:**

- 不将 `PreloadCache` 的 key 由 `source_id` 改为 signature（属于潜在后续增强/guardrail，不在本变更落地）。
- 不引入跨进程去重或全局缓存语义；默认语义仍是 in-flight 去重。
- 不在本变更中新增/调整 workflow cache_pool 的冲突策略（`error|warn|separate`）语义。

## Decisions

### 1) 以“规范 + 可运行复现”作为本变更的 SSOT

本变更的核心是**减少误解**而非新增功能，因此把交付物收敛为：

- OpenSpec：`preload-cache-concurrent-load-scenarios` 作为本变更的新增 capability/spec；
- 对应主 specs（`source-cache`、`workflow-cache-pool`）补充引用与边界说明；
- 复现路径优先引用仓库内现成测试与 fixture（避免引入新的 demo 脚本导致维护负担）。

### 2) 明确两个缓存容器的 key 空间与“同一个 load”的含义差异

- `PreloadCache.get_or_load(source_id, ...)`：
  - key：`source_id`
  - 语义：仅承诺 per-key in-flight 去重（同 key 同时最多一次真实 load）
  - 风险：跨不同 demand/不同 loader/不同 params 复用同一 `source_id` 时，可能发生**错误复用**（这是使用方责任边界，需要在文档中明确）。
- `WorkflowCachePool.get_or_load(signature, ...)`：
  - key：完整 signature
  - 语义：workflow-scope 的正确复用 + in-flight 去重

### 3) 并发边界按“调用入口”而非“实现直觉”描述

避免 “engine 有锁所以不会并发” 的误解，本变更把并发边界写成可验证的两类入口：

- 多线程并发多个 `ScalimEngine.run()`，且共享同一个 `preloaded_cache` 容器；
- workflow 多 node 并发执行（`ThreadPoolExecutor(max_concurrency)`），并发请求同一 `WorkflowCachePool` signature。

## Risks / Trade-offs

- [风险] 仅文档化可能不足以阻止误用（例如把 `PreloadCache` 作为长期缓存复用）。
  → 缓解：在 `source-cache` spec 中明确“仅 in-flight 去重 + key 空间不足以表达 signature”的风险提示，并在未来 change 中评估是否需要 guardrail。

- [风险] 复现依赖现有 fixture/测试路径，后续重构可能导致引用漂移。
  → 缓解：优先引用稳定的测试名（pytest node id）与 fixture 文件路径；若重构移动文件，测试本身应随之更新（被 `just qa` 覆盖）。

## Migration Plan

1. 将本变更 spec 的边界说明同步到主 specs（`source-cache`、`workflow-cache-pool`）。
2. 在必要的实现点补充简短注释（强调 key 空间与 in-flight 语义），避免与 spec 口径漂移。
3. 复核并补齐最小可运行复现（优先复用已有 `tests/test_preload_cache.py`；workflow 场景若缺回归测试则补齐）。
4. 验收：运行 `just openspec-check` 与 `just qa`。

## Open Questions

- 是否需要为 `PreloadCache` 增加可选 guardrail：当调用方跨不同 signature 复用同一 `source_id` 时给出警告或拒绝（需要明确 signature 的定义与可得性）。
> 需要，但不建议塞进本 change 的 MVP：`c70` 以“边界澄清 + 复现口径 + spec 同步”为交付。guardrail 属于行为变更，应作为后置 change 落地（避免把 doc/spec change 变成大范围实现改动）。
- 是否需要把 “loader SHOULD be idempotent” 等建议提升到 `source-cache` 的显式约束（可能影响用户实现与错误语义）。
> 需要：至少提升为 SHOULD，并明确其背景是“并发/重复加载在现实场景不可完全避免（多 engine / workflow 并发）”。若 loader 非幂等，应在文档中明确风险与建议（例如不要跨不同配置复用同一 `PreloadCache`，或启用后续 guardrail）。
