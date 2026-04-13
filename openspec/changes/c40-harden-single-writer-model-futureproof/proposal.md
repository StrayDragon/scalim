## Why

工作流执行层的**单写者模型**（write 节点只在无 in-flight demand future 时在控制器线程同步执行）消除了对 `WorkflowCtxStore` / `WorkflowArtifactsDirectory` 的锁需求。这是一个优雅且高性能的设计，但存在两个隐患：

1. **隐式契约**：该不变量仅通过调度逻辑保证，没有运行时验证。如果未来修改调度逻辑不慎破坏该不变量，不会有任何信号。
2. **free-threaded Python 风险**：CPython GIL 提供了隐式的 happens-before 保证。在 free-threaded Python (PEP 703, 3.13t/3.14t) 下，无 GIL 的 dict 读写需要额外保护。

需要一个兼容 Python 3.6 到 3.14t 的前瞻方案。

## What Changes

方案：**debug-mode 断言 + 可选 threading.Lock 保护**

1. 在 `WorkflowCtxStore` 和 `WorkflowArtifactsDirectory` 的写方法中添加 `_owner_thread_id` 检查：`assert threading.current_thread().ident == self._owner_thread_id`（仅在 debug/assert 模式下生效）。
2. 新增 `_FREE_THREADED` 检测标志（检查 `sys.flags` 或 `sysconfig`）。当运行在 free-threaded Python 下时，自动为这些共享结构启用 `threading.Lock` 保护读写。
3. 在 `WorkflowRunController` 调度循环中添加断言：提交 write 节点时 `len(self._state.submitted) == 0`。
4. 文档化单写者模型的契约和假设。

该方案在 3.6 上零开销（断言可被 `-O` 禁用），在 3.14t 上提供正确性保护。

## Capabilities

### New Capabilities

### Modified Capabilities

## Impact

- 文件：`src/scalim/workflow/execute_controller.py`、`src/scalim/workflow/execute.py`（`WorkflowCtxStore`）、`src/scalim/workflow/artifacts.py`。
- 3.6-3.12 正常模式：零性能开销（仅断言）。
- 3.13t/3.14t：自动启用锁保护，性能影响可忽略（写操作频率极低）。
