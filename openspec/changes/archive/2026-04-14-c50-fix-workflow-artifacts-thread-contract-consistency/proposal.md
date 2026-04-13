## Why

当前 workflow 并发执行（`max_concurrency > 1`）下的单写者模型要求“所有 workflow-managed 的共享可变状态更新”只能发生在 controller 线程。
但 `WorkflowArtifactsDirectory` 目前仅对 `publish/discard` 做了 owner thread 断言，部分 `discard_in_memory_*` / `discard_all_in_memory_*` 辅助方法仍可能在非 controller 线程被调用而不 fail-fast，导致并发 bug 更隐蔽、契约不一致。

## What Changes

- 为 `WorkflowArtifactsDirectory` 的所有会写内部状态的 API 补齐一致的 owner thread 断言（包括 `discard_in_memory_*` 与 `discard_all_in_memory_*`）。
- 为该契约补齐最小回归测试覆盖（避免未来重构时“无意放开写入线程约束”）。
- 必要时补充规范文字，明确这些辅助方法同属“workflow-managed state writer”边界。

## Capabilities

### New Capabilities
- (none)

### Modified Capabilities
- `workflow-shared-output-containers`: 单写者模型的“sole writer”要求覆盖 `WorkflowArtifactsDirectory` 的所有写路径（不仅限于 `publish/get/discard`，也包括 in-memory artifact 的 discard/cleanup helpers），并在误用时 fail-fast。

## Impact

- 受影响代码：`src/scalim/workflow/artifacts.py` 及其相关测试。
- 行为影响：在非 controller 线程误用 artifacts discard/cleanup API 时将更早抛出 `RuntimeError`（作为实现错误的 fail-fast）。
- 对外 API：无预期变更（属于内部并发契约收敛/加固）。
