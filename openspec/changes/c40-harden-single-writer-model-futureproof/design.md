## Context

工作流执行层的单写者模型通过 `WorkflowRunController.submit_ready_nodes()` 的调度逻辑保证：write 节点只在无 in-flight demand future 时同步执行。这避免了对 `WorkflowCtxStore` / `WorkflowArtifactsDirectory` 加锁。

但该不变量是隐式的（仅靠调度逻辑保证），且依赖 CPython GIL 提供 happens-before 保证。

约束：
- 必须兼容 Python 3.6 到 3.14t（free-threaded）
- 正常模式（有 GIL）下零开销
- 不改变调度语义

## Goals / Non-Goals

**Goals:**
- 添加运行时断言验证单写者不变量
- 在 free-threaded Python 下自动启用锁保护
- 文档化线程安全契约

**Non-Goals:**
- 不将共享结构全面改为线程安全容器（过度工程）
- 不改变调度模型

## Decisions

### 1) Debug-mode 断言

在 `WorkflowCtxStore` 和 `WorkflowArtifactsDirectory` 的写方法中：

```python
class WorkflowCtxStore:
    def __init__(self, ...):
        self._owner_thread_id = threading.current_thread().ident

    def publish(self, ...):
        assert threading.current_thread().ident == self._owner_thread_id, \
            "WorkflowCtxStore.publish must be called from controller thread"
        ...
```

断言在 `-O`（优化模式）下自动禁用，生产环境零开销。

### 2) 调度不变量断言

在 `WorkflowRunController._submit_one_ready_node` 中，当节点是 write 节点时：

```python
assert len(self._state.submitted) == 0, \
    "write node must not be scheduled while demand futures are in-flight"
```

### 3) Free-threaded Python 自动降级

检测 free-threaded runtime：

```python
import sys
_FREE_THREADED = hasattr(sys.flags, "nogil") and sys.flags.nogil
# 或 Python 3.13+: sys.flags.no_gil
```

当 `_FREE_THREADED` 为 True 时，`WorkflowCtxStore` 和 `WorkflowArtifactsDirectory` 的读写方法自动使用 `threading.Lock` 保护。

在 3.6 上 `hasattr(sys.flags, "nogil")` 返回 False，自然走无锁路径。

### 4) 实现模式

使用条件装饰器或 mixin：

```python
class _ThreadSafeReadWriteMixin:
    """当 _FREE_THREADED 时为读写加锁，否则 no-op。"""
    def __init__(self):
        self._rw_lock = threading.Lock() if _FREE_THREADED else None

    def _read_guard(self):
        if self._rw_lock is not None:
            return self._rw_lock
        return contextlib.nullcontext()  # 需要 3.7+，3.6 用 no-op CM
```

考虑到 3.6 兼容性，不使用 `contextlib.nullcontext()`（3.7+），而是：

```python
@contextmanager
def _noop_cm():
    yield

_GUARD = threading.Lock if _FREE_THREADED else _noop_cm
```

## Risks / Trade-offs

- `_FREE_THREADED` 检测依赖 `sys.flags` 属性，需要在 3.13t 实际验证。
- 断言在 `-O` 模式下不生效——但这是 debug 辅助而非安全屏障，可接受。
- 在 free-threaded 下自动加锁可能引入微小的性能回退（写操作频率极低，影响可忽略）。

## Migration Plan

- 修改 `execute.py`（WorkflowCtxStore）和 `artifacts.py`
- 修改 `execute_controller.py` 添加调度断言
- 添加测试验证断言触发
- 验证：`just qa`

## Open Questions

- 无。
