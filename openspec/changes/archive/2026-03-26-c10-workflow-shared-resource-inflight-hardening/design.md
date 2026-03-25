## Context

为 workflow 共享资源（`csv/workbook/sheetbook`）的 joinable get-or-create 引入 liveness diagnostics 与 commit/discard 并发安全语义.

参考实现: `PreloadCache` 的 `PreloadCacheWaitDiagnostics`（`src/scalim/execution/preload_cache.py`）.

## Goals / Non-Goals

**Goals:**
- waiter 等待可观测（warn-after + repeat-every 告警）
- 可选的 max-wait 超时 fail-fast
- commit_all/discard_all 与 inflight 创建并发交错有确定性语义

**Non-Goals:**
- 不改变正常路径的行为（diagnostics 默认禁用）
- 不改变资源创建的原子性/joinable 语义（c0 已固化）
- 不涉及 sheetbook 的 inflight 模式引入（sheetbook 当前走不同的创建路径）

## Decisions

### 1) Wait diagnostics 配置结构

复用 `PreloadCacheWaitDiagnostics` 的设计模式:

```python
@dataclass
class WorkflowResourceWaitDiagnostics:
    enabled: bool
    warn_after_s: float = 30.0
    repeat_every_s: Optional[float] = None
    capture_owner_callsite: bool = False
```

通过 `_WorkflowResourceManagerBase.__init__` 接收,默认 `enabled=False`.

### 2) 超时策略

在 `_get_or_create_joinable_plan` 的 waiter 路径中:
- `inflight_state.done.wait()` → `inflight_state.done.wait(timeout=poll_s)` + poll loop
- 超时检测与告警复用 diagnostics 配置
- 可选 `max_wait_s: Optional[float] = None`（None = 不超时,仅告警）

### 3) commit/discard 与 inflight 并发交错

推荐 **drain** 策略:

```
commit_all():
    # 1. 等待所有 inflight 完成
    for inflight_state in list(self._inflight_workbooks.values()) + list(self._inflight_csvs.values()):
        inflight_state.done.wait(...)  # 复用 diagnostics
    # 2. 再 commit 所有 plans
    for plan in list(self._workbooks.values()): ...
    for plan in list(self._csvs.values()): ...
    for plan in list(self._sheetbooks.values()): ...
```

理由: drain 更贴合 workflow 的"节点全部完成后才 commit"语义; fail-fast 可能在正常并发时误触.

### 4) 告警输出路径

优先走 `self._instrumentation.emit(...)` 发事件（与现有 workflow resource 事件对齐）. 如 instrumentation 不可用,fallback 到 `loggingx.get_logger("workflow-resources").warning(...)`.

## Risks / Trade-offs

- drain 策略下 commit_all 可能等待较长时间 → 复用 diagnostics 的 warn-after 暴露问题
- poll interval 过大可能导致告警延迟 → 参考 PreloadCache 的 `_compute_poll_interval_s` 逻辑

## Migration Plan

- 默认 `enabled=False`,不改变任何现有行为
- 通过 workflow 配置或 driver 参数显式启用

## Implementation Pitfalls (代码探索 2026-03-25)

### P1: `on_create` 失败时 owner 与 waiter 语义分裂

`_get_or_create_joinable_plan` 中,当 `create_fn` 成功但 `on_create` 抛异常时:
- plan 已写入 `plans` dict
- `done.set()` 在 `finally` 中执行
- **owner 收到异常,但 waiters 通过 `plans.get(key)` 拿到了 plan 并成功返回**

这是一个跨线程语义分裂——owner 认为创建失败,waiters 认为成功。hardening 时需决定:是否在 `on_create` 失败时移除 plan 并设置 error,使 waiters 也感知到失败。

### P2: `apply_*` 在 `self._lock` 内做 I/O

`resources_csv.py` / `resources_workbook.py` 中部分 `apply_*` 路径在持有 `self._lock` 时读取输入文件（如 `_read_csv_header`）。慢 FS 场景下这会阻塞**所有其他资源**的操作（不仅仅是同一 resource_id）,与 inflight 等待叠加可能加剧整体阻塞。

### P3: `_cleanup_workflow_finally` 中 `suppress(Exception)` 隐藏 discard 失败

`workflow/execute.py` 的 `_cleanup_workflow_finally` 在 `finally` 中用 `contextlib.suppress(Exception)` 包裹 `discard_all()`,会完全静默 discard 过程中的锁泄漏或写入错误。hardening 应改为日志记录而非完全抑制。

### P4: sheetbook 不使用 inflight 模式

`resources_sheetbook.py` 的 `_get_or_create_sheetbook` 在 `self._lock` 内完成全部创建（不走 `_get_or_create_joinable_plan`）。hardening 需决定:是否为 sheetbook 引入 inflight 模式以保持一致性,或明确文档化其"不需要 inflight"的设计理由。

### P5: diagnostics 配置需穿透到 `_prepare_workflow_run_ir`

`WorkflowResourceManager` 在 `workflow/execute.py` 的 `_prepare_workflow_run_ir` 中构造。wait diagnostics 参数需要从 workflow 配置层传递下来,当前没有现成的配置路径——需要在 YAML DSL runtime 或 driver 装配层新增参数入口。

### P6: `commit_all`/`discard_all` 无锁执行

`_commit_*`/`_discard_*` 做重 I/O 但不持有 `self._lock`。当前安全依赖于"executor 线程池已 drain 后才 commit"的架构假设,但未强制执行。drain 策略应先断言 inflight 为空,并考虑是否需要在 commit 路径加 assert。
