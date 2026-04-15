## Context

workflow 并发（`max_concurrency>1`）下，为了不要求 observers/hooks 实现线程安全，框架采用 **capture + replay**：worker 线程仅捕获事件与结果，随后在单线程以确定性顺序回放事件。

该默认安全策略在真实业务中会被一个隐含成本放大：

- `loader_call` 的事件/typed hook 负载可能携带 **完整 loader result**（例如大 dict/list）。
- 捕获阶段会把这些 payload 暂存在内存结构中，直到 replay/commit；这会把“本应按批次生命周期释放”的大对象延长为“整次 run / workflow 常驻”，造成内存尖峰、GC 压力与整体耗时上升。

此外，workflow 入口的 per-run patch（`run_options_patches_by_run_id`）目前不覆盖 `parallel_mode/max_workers`，导致调用侧只能做“全局并发策略”的粗粒度控制。真实场景往往需要对不同 run 做差异化策略（例如重 IO run 串行、轻 run 允许 intrabatch 并发且限制 worker 数），否则用户会转向手写调度/拆 workflow，降低可维护性。

约束：
- 运行时兼容 Python 3.6（`src/scalim/`）。
- 不新增 YAML authoring 字段（保持 runtime policy boundary）。
- 不降低 workflow 并发下 observers/hooks 的默认安全性与确定性顺序。

## Goals / Non-Goals

**Goals:**
- 在 workflow 并发 capture+replay 模式下，避免捕获 `loader_call` 的完整 result 造成的内存保活；默认采用轻量摘要 payload（例如 `type/size`）。
- 扩展 workflow per-run patch 覆盖面，支持 per-run 覆盖 `parallel_mode/max_workers`（inherit/override 语义清晰且 typed）。
- 保持现有执行正确性（计算结果与输出不变），变更仅限可观测性 payload 与 runtime knobs 的组合能力。
- 增加针对 workflow 并发路径的测试覆盖，避免回归。

**Non-Goals:**
- 不引入 workflow“分组并行 / 资源标签调度 / wave scheduler”等新的调度器能力。
- 不实现 DataLoader 式“跨批次 keys 自动 batching/merge”或 SQL join 重写（属于独立能力）。
- 不新增/修改需求 YAML 的语法字段来承载并发策略。

## Decisions

### Decision 1: workflow 并发捕获模式下，`loader_call` 默认使用 summary payload（而不是 full result）

策略：当 workflow 处于并发且需要 capture+replay（即“并发 + 注册了 components”）的路径时，捕获侧 MUST 避免把完整 loader result 作为事件 payload 持久化到内存。

落点：
- 对 **observer 事件**：在捕获用的 `ObserverManager(mode="capture")` 上强制使用 `loader_result_policy="summary"`（或等价策略），使 `EVENT_LOADER_CALL` 的 payload 仅包含 `type/size` 摘要，而不是完整 mapping/list。
- 对 **typed hook**：在捕获用的 `HookCaptureManager` 上同样使用 `loader_result_policy="summary"`，确保 typed `loader_call` 不保活完整 result。

理由：
- `summary` 足以满足常见的性能日志与诊断需求（loader 名称、耗时、结果规模）。
- 最大化收益：避免把大对象延长生命周期，降低内存与 GC 压力，改善 wall time。
- 保持“wants-gated”特性：未订阅的事件不构建 payload；订阅了也仅保留摘要。

备选方案：
- (A) 保持 full result，但为 capture 队列设置 `max_recorded_events` 上限并丢弃 → 会导致 replay 事件不完整，且丢弃策略难解释。
- (B) 为每类事件引入更细粒度的 payload policy（例如 batch_start 仅记录 row_count）→ 覆盖面更广但复杂度更高；v0 先聚焦最重的 `loader_call`。

### Decision 2: per-run patch 增量支持 `parallel_mode/max_workers`

扩展 `WorkflowRunOptionsPatch`：
- 新增字段：
  - `parallel_mode: UNSET | "seq" | "adaptive"`
  - `max_workers: UNSET | int`（约束 `>=0`，`0=auto`）
- 继承/覆盖语义：
  - `UNSET`：继承 workflow 全局 `RunOptions`
  - 非 `UNSET`：覆盖对应字段

理由：
- 让 workflow 能对不同 run 采用差异化并发策略，不需要拆 workflow 或手写调度。
- 满足“每个 batch 内 source lookup 并行”的诉求：对包含多个独立 `LoadRef(keys)` 的 run，可设置 `parallel_mode="adaptive"` 并限制 `max_workers`，在可控范围内降低 per-batch I/O latency。

备选方案：
- (A) 新增 workflow YAML authoring 字段承载并发 knobs → 违反 runtime policy boundary，且会带来 schema/LSP 维护成本。
- (B) 仅允许全局 `RunOptions.parallel_mode` → 不能解决 per-run 细粒度治理需求。

### Decision 3: 文档与生成边界

- 本变更涉及的 OpenSpec artifacts（proposal/design/specs/tasks）均为手工维护文件，不包含 `.gen.` 生成物或 injected blocks。
- 规范变更通过更新 `openspec/specs/*/spec.md` 与本 change 的 delta specs 体现；无需手工编辑任何 `*.gen.*` 文件。
- 提交前验证：
  - `just openspec-check`（sanitize + validate）
  - `just qa`（覆盖漂移门禁与回归测试）

## Risks / Trade-offs

- [行为差异] workflow 并发（capture+replay）下 `loader_call` 的 event/hook payload 不再包含完整 result → 缓解：该差异仅在并发捕获模式出现；若必须拿 full result 做诊断，建议临时改为 `max_concurrency=1` 的串行运行，或改用更合适的专用诊断输出。
- [不覆盖所有大 payload] 仅对 `loader_call` 做瘦身，其他事件若携带大对象仍可能造成压力 → 缓解：v0 先解决最常见/最重路径；后续可按需求扩展到其他事件类型。
- [调参复杂度上升] per-run 可覆盖 `parallel_mode/max_workers` 可能被误用导致 DB 压力上升 → 缓解：保持默认行为不变；在 specs/文档中强调“限制 max_workers、按 run 细分策略”。

## Migration Plan

- 无破坏性迁移要求：现有 workflow 调用不需要修改。
- 若调用侧希望使用 per-run 并发策略：
  - 在 `run_workflow(..., run_options_patches_by_run_id=...)` 中为目标 run 增量添加 `WorkflowRunOptionsPatch(parallel_mode=..., max_workers=...)`。

## Open Questions

- 是否需要为 capture 模式提供一个显式的 runtime knob（例如 `capture_loader_result_policy=summary|full`）用于“debug vs perf”的可控切换？
- 是否需要把 `max_recorded_events` 的默认值从 `None` 收敛为“有界 + 可诊断丢弃策略”，以进一步防止极端事件量导致的内存风险？
