## ADDED Requirements

### Requirement: Adaptive runtime shared caches MUST document CPython+GIL-only safety

系统 MUST 明确声明: `parallel_mode=adaptive` 并发路径中的共享 `dict/set` 缓存与计数器仅在 **GIL-backed CPython** 下承诺正确性,并在实现中以 `NOTE:` / `WARN:` 注释形式标注该契约边界。

当 `parallel_mode=adaptive` 启用批次内并发时,执行层会在多个 worker 线程间共享部分 `dict/set` 缓存与计数器(例如 key normalize cache 与 load-ref cache)。

系统 MUST 明确声明以下契约:
- 这些结构当前不提供显式锁保护
- 其并发正确性仅在 **GIL-backed CPython** 下成立(依赖实现细节而非语言语义保证)
- free-threaded/no-GIL Python 不在支持范围内(若要支持,必须引入锁或等价的同步策略)

系统 MUST 在对应实现的模块/类级别或关键字段附近以 `NOTE:` / `WARN:` 注释形式写出上述信息,使维护者在阅读热点代码时能直接看到契约边界。

#### Scenario: maintainer can discover the CPython+GIL-only contract near the hot caches
- **WHEN** 维护者阅读 `ExecutionRuntime` 及 `LoadRef` key-normalize cache 相关实现
- **THEN** 必须能在关键共享缓存/计数器附近看到 `NOTE:` / `WARN:` 注释
- **AND** 注释必须明确包含 "CPython" 与 "GIL" 的支持边界说明
