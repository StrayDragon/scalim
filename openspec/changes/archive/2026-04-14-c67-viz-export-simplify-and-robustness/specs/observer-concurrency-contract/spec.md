# observer-concurrency-contract (delta) Specification

## ADDED Requirements

### Requirement: file-based observers MUST provide a single-writer boundary by default

当系统处于并发执行模式（例如多线程/并行调度）且启用 file-based observers（例如 viz JSONL 输出）时，系统 MUST 默认提供单写者边界以保证安全：

- observer 的文件写出 MUST NOT 依赖调用方线程安全；
- 系统 MUST 串行化写出动作（single writer 或等价机制），避免回调线程直接并发写文件；
- 该串行化机制 MUST 不破坏 `no-external-callback-under-lock` 的护栏（不得把外部回调放回锁内）。

#### Scenario: non-thread-safe observer does not corrupt file outputs under concurrency
- **GIVEN** 并发执行且启用了 viz 输出
- **WHEN** 多个执行单元触发事件写出
- **THEN** 输出文件 MUST 保持可解析且不发生并发写入损坏

