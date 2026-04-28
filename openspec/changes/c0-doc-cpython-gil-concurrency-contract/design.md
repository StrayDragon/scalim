## Context

- 现状：`parallel_mode=adaptive` 在同一批次内并发执行多个 `LoadRef(keys)`。
- 扫描结果（见 `_REPORT.md` 的 R-1/R-2）：
  - `ExecutionRuntime.key_normalize_cache` / `load_ref_cache` 为普通 `dict`，在并发下存在 check-then-act / 并发写入导致重复工作等理论竞态。
  - `LoadRefExecutionContext.default_applied_counts` 存在典型 read-modify-write（`get()+1`）非原子序列。
- CPython 当前实现下，由于 GIL 保护了单条 dict/set 操作且大多数路径不释放 GIL，竞态通常不会表现为内存破坏，但这是实现依赖。

## Goals / Non-Goals

Goals:
- 把并发正确性的**支持边界**显式化：仅承诺 GIL-backed CPython。
- 在关键共享状态附近用 `NOTE:` / `WARN:` 注释明确说明：并发读写点、依赖假设、未来风险。
- 在 `parallel-execution` 规范中补齐该契约，避免“实现注释”与“规范承诺”脱节。

Non-Goals:
- 不引入锁或线程安全容器；不改变现有调度/并发模型。
- 不新增 free-threaded/no-GIL 的兼容实现与测试矩阵（后续如需支持再单独立项）。

## Decisions

1. 选择“文档化契约”而非“立即加锁”
- 原因：加锁会引入新开销与潜在死锁/锁顺序问题；同时需要更大范围的测试与性能评估。
- 替代方案：
  - A. 对所有共享 dict/set 加锁：正确性更强，但实现侵入性高且需性能回归验证。
  - B. 使用线程安全容器/原子计数：Python 3.6 环境下选型有限，且仍需要定义清晰的 happens-before。

2. 注释规范化
- 在代码中使用清晰的 `NOTE:` / `WARN:` 前缀：
  - `NOTE:` 用于阐述“当前依赖的事实/假设”（例如“此结构在 adaptive 下会被多线程读写，但在 CPython+GIL 下依赖实现细节通常安全”）。
  - `WARN:` 用于阐述“未来风险/不支持边界”（例如“free-threaded/no-GIL 不在支持范围内；若启用该 runtime，需要显式锁保护”）。

## Risks / Trade-offs

- [风险] 文档化不等于修复：未来如果有人误在 no-GIL 解释器上运行，仍可能触发真实竞态。
  - 缓解：规范与注释都明确写出“不支持”；如果检测到 free-threaded runtime（未来），应 fail-fast 或另开变更实现锁。

- [风险] 注释漂移：实现改动后注释可能过期。
  - 缓解：在规范中将该契约写成 REQUIREMENT（需要维护者在演进并发模型时同步更新）。

## Migration Plan

- 无运行期迁移；仅文档化与规范补齐。

## Open Questions

- 是否要在未来引入“检测 free-threaded runtime 并 fail-fast”的主动防护？
> 可以增加一个判断 我们明确知道 在 3.14+ 会有相关问题可以加一些判断或者主动防护, 可以通过以下判断是否是no gil
import sysconfig

if sysconfig.get_config_var('Py_GIL_DISABLED') == 1:
    print("这是一个自由线程版本。")
else:
    print("这是一个常规版本。")

- 如果未来需要支持 no-GIL，哪些数据结构必须加锁，哪些可通过所有权/单写者模型规避？
> 这个可以延后处理 我们目前仅官方支持 py3.6 和 py3.10
