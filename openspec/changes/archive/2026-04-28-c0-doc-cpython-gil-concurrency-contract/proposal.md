## Why

`parallel_mode=adaptive` 会在同一批次内并发执行多个 `LoadRef(keys)` 任务。当前实现中存在若干共享的 `dict/set` 缓存（例如 `ExecutionRuntime.key_normalize_cache` / `load_ref_cache`），在 CPython + GIL 下通常“看起来没问题”，但这依赖实现细节（check-then-act、read-modify-write 在 free-threaded/no-GIL 或其它实现下会变成真实竞态）。

我们不打算在这一轮为这些缓存引入锁或线程安全容器（成本与复杂度较高），而是选择把**支持边界**写清楚：此路径仅承诺在 **GIL-backed CPython** 下成立，并通过 `NOTE:` / `WARN:` 注释与规范说明把风险显式化，避免未来扩展/重构时误以为“已具备跨实现线程安全语义”。

## What Changes

- 在执行层并发相关的共享缓存/计数器附近补齐明确的 `NOTE:` / `WARN:` 注释：
  - 指明它们在 `adaptive` 下会被多线程读写
  - 指明当前 correctness 依赖 CPython GIL（而非语言语义保证）
  - 指明 free-threaded/no-GIL Python 不在支持范围内（需要锁或线程安全容器才能支持）
- 更新 OpenSpec：将该支持边界写入并发相关规范（作为明确的对外契约，而非仅散落的实现注释）。

## Capabilities

### New Capabilities

- （无）

### Modified Capabilities

- `parallel-execution`: 补充“GIL-backed CPython only”的并发正确性契约说明（尤其是 execution runtime 内部共享缓存的线程安全假设）。

## Impact

- 受影响代码（注释与契约标注，原则上不改语义）：
  - `src/scalim/execution/executor/runtime/runtime.py`
  - `src/scalim/execution/executor/operators/load_ref/context.py`
  - `src/scalim/execution/executor/operators/load_ref/loader.py`
  - `src/scalim/execution/executor/guardrails.py`
- 受影响规范：
  - `openspec/specs/parallel-execution/spec.md`
- 风险：
  - 这是“文档化约束”，不会修复潜在竞态；如果未来需要支持 free-threaded/no-GIL，需要另开 change 引入锁与测试矩阵。
