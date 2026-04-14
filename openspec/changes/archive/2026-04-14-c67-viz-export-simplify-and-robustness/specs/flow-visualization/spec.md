# flow-visualization (delta) Specification

## ADDED Requirements

### Requirement: viz JSONL event streams MUST remain parseable under concurrency

当系统输出 `viz_events.jsonl`/`viz_trace.jsonl` 时，系统 MUST 保证在进程内并发/重入场景下文件内容始终可逐行解析：

- 每一行 MUST 为完整的 JSON 对象（以 `\\n` 分隔）
- 系统 MUST 避免并发写入导致的“半行”或“交错拼接”JSON（即使发生并发 emit）
- 系统 MUST 通过 single writer 或等价的写出串行化边界保证上述完整性

#### Scenario: concurrent emit does not corrupt JSONL lines
- **GIVEN** 多个线程并发调用同一个 emitter 的 `emit()`
- **WHEN** 事件写入完成并读取输出文件逐行解析
- **THEN** 每一行 MUST 为可解析的 JSON

