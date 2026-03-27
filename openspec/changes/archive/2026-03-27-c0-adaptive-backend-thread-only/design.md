## Context

当前 execution 的 `parallel_mode=adaptive` 同时维护 thread/process/async 三套 backend 的实现与测试覆盖.这使得:
- 维护与回归成本高(分支多、测试矩阵大)。
- process/async backend 的运行时语义/guardrails(可序列化性、事件 capture/replay、失败策略等)复杂,在 Python 3.6 运行时边界下更难保证长期稳定。

本变更采用“扩展 seam 保留、实现裁剪”的方式降低维护面:保留 policy/overrides/scheduler 的接口形状与分发结构,但主线仅内置 thread backend。

## Goals / Non-Goals

**Goals:**
- 保留 `adaptive` 架构与扩展 seam,调用链路仍以 `policy.choose_backend(...)` 为入口。
- 主线实现收敛为 thread-only:仅创建 `ThreadPoolExecutor` 路径。
- 当 policy 选择 `process/async` 时,稳定 fail-fast 并给出明确错误信息(说明 backend 暂不支持,当前仅支持 thread)。
- 删除 process/async backend 的实现文件与对应测试,并将所有测试/文档改写为 thread-only。

**Non-Goals:**
- 不在本变更中回加或“兼容保留” process/async 行为。
- 不改变 `adaptive` 的调度语义边界(仍为批次内 LoadRef fan-out/fan-in)。
- 不对 `seq` 模式做任何行为调整。

## Decisions

### 1) 保留 policy 常量与接口,但裁剪非 thread 实现
**Decision:** 保留 `AdaptivePolicy.choose_backend()` 与 `ADAPTIVE_BACKEND_THREAD/PROCESS/ASYNC` 常量,默认仍返回 thread;实际执行仅允许 thread,若返回 process/async 立即抛错。

**Why:** 这是稳定 seam:既不破坏外部策略代码的 import/接口形状,也让未来回加实现的落点明确。

**Alternatives considered:**
- 直接移除常量/接口并统一为 thread-only:会破坏外部策略/代码引用,且未来回加需要大规模接口恢复。
- 静默 fallback 到 thread:会掩盖用户配置/策略错误,导致“看似成功但并未按预期使用 backend”。

### 2) overrides 收敛为 thread-only 注入点
**Decision:** `PipelineOverrides` 仅保留 `adaptive_executor_cls` 等 thread 可用注入点;移除 `adaptive_process_executor_cls` / `adaptive_async_executor_cls` 字段及其引用,以缩小维护面。

**Why:** 既然实现被裁剪,保留无效字段会误导用户并增加文档与测试成本。

### 3) scheduler 分发结构保留,但仅保留 thread 路径
**Decision:** `AdaptiveLoadRefScheduler` 继续保留 backend 分发结构的“形状”,但实现仅包含 thread 路径。

**Why:** 避免未来回加时需要同时改调度器对外语义/内部组织;同时保持当前对外行为简洁明确。

## Risks / Trade-offs

- [破坏性变更] 依赖 process/async backend 的调用方将失败 → 缓解:错误信息明确指出“backend 暂不支持;当前仅支持 thread;请将 backend 改为 thread”。
- [规范/文档漂移] 并发规范仍描述 process/async 语义 → 缓解:同步增量规范修改 `parallel-execution` 与 `explicit-extension-points`,并更新 `docs/doc/architecture/parallel-modes.md`。
- [遗漏分支/死代码] process/async 分支散落在 scheduler/pool/support 模块中 → 缓解:实现阶段用 ripgrep 全仓库搜索 `process`/`async` adaptive 相关符号,并以 thread-only 测试回归兜底。

## Migration Plan

- 代码裁剪与测试改写应在同一变更中完成,避免“实现删了但测试仍覆盖旧语义”的中间态。
- 文档治理边界:
  - 不直接编辑任何包含 `.gen.` 的文件。
  - 不编辑任何 `<!-- BEGIN AUTOGEN:<id> -->` / `<!-- END AUTOGEN:<id> -->` 注入区块内部。
  - 手写 SSOT 文档(如 `docs/doc/architecture/parallel-modes.md`)可直接修改;若其包含注入区块,仅修改区块外内容。
  - 需要刷新生成物时,入口为 `just gen-docs`,并以 `just qa`/CI 的 drift gate 校验收尾。

## Resolved Questions

- `PipelineOverrides` 当前确实包含 `adaptive_process_executor_cls` / `adaptive_async_executor_cls` 且在测试与文档中有引用;本变更将统一移除并同步改写对应用例/段落。
- 错误类型选择:优先最小改动,在 pool 创建处统一抛 `ValueError` 以保持与既有参数校验错误类型一致。
