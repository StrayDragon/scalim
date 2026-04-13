## Context

Workflow 并发执行（`max_concurrency > 1`）采用单写者模型：worker 线程只做纯计算并回传结果，controller 线程负责统一落地 workflow-managed 的共享可变状态（artifacts / ctx / resources）。

当前实现已对部分写路径做了 owner thread 断言（例如 `WorkflowArtifactsDirectory.publish/discard`、`WorkflowCtxStore.publish*`），但 artifacts 的 in-memory discard/cleanup helpers 仍存在“写内部状态但未断言”的不一致点，削弱了 fail-fast 与契约可读性。

## Goals / Non-Goals

**Goals:**
- 将 `WorkflowArtifactsDirectory` 的所有内部状态写路径统一纳入 owner thread fail-fast 契约。
- 在不改变 workflow 执行语义的前提下，提升并发 bug 的可诊断性（更早、更明确地失败）。
- 保持实现轻量，避免引入锁/同步复杂度，继续贯彻单写者模型。

**Non-Goals:**
- 不把 artifacts 容器改造成“多写者线程安全”结构（不引入锁来容忍误用）。
- 不改变既有 artifact 的可见性/依赖校验语义（例如 `get` 的可见性检查保持不变）。
- 不在本变更内扩展或重构 workflow scheduler/controller 的整体结构。

## Decisions

- **全量写路径断言**：在 `WorkflowArtifactsDirectory` 中，对所有会写 `_values_by_producer_node_id` 或其子结构的 API（包括 `discard_in_memory_*`、`discard_all_in_memory_*`、`discard_all_in_memory_rows`）统一在方法入口调用 `_assert_owner_thread()`。
- **fail-fast 而非同步**：保持“误用即实现错误”的策略，线程不匹配时直接抛出 `RuntimeError`，避免锁导致的隐藏竞态或性能回退。
- **最小回归测试**：以“owner_thread_id 人工篡改”方式构造 mismatch，覆盖每个新增断言的分支，作为重构护栏（避免未来新增 helper 又遗漏断言）。
- **文档/生成边界**：变更仅涉及手工维护的 Python 源码与 pytest 用例；不触及任何生成物或 injected blocks。质量门禁由 `just qa`（含 `test-gate`）与相关单测兜底。

## Risks / Trade-offs

- [风险] 现有测试或未来新代码在非 controller 线程调用 artifacts discard helpers 会更早失败 → [缓解] 明确该行为为实现错误；通过回归测试约束并在必要时修正调用点至 controller 上下文。
- [风险] 断言增加了极少量运行期开销 → [缓解] 仅为一次 thread ident 比较，成本可忽略，且只在写路径触发。
