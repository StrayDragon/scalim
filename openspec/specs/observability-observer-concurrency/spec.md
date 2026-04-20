# observer-concurrency-contract Specification

**状态: ✅ 已实现**

## Purpose
定义 workflow 并发执行时 observers/hooks/components 的默认并发语义,确保在不要求 observer 实现方线程安全的前提下仍具备可解释、可复现的事件回放顺序,并保持 `no-external-callback-under-lock` 护栏不被破坏.

## Related Concepts
- Workflow 并发执行引擎 (workflow execute)
- 统一 IR 编排入口 (run_ir_capture_events)
- 可视化事件发射器 (viz output emitter)
- Observer/hook 并发安全
- Capture+replay 机制
- 单写者边界

## Requirements
### Requirement: observer callbacks MUST be safe under workflow concurrency by default

当 workflow 以并发模式执行（例如 `max_concurrency>1`）且注册了 observers/hooks/components 时,系统 MUST 默认保证回调调用在并发下安全:

- 系统 MUST NOT 要求 observer 实现方必须是线程安全的才能正确工作
- 系统 MUST 通过序列化回调或 capture+replay（单线程回放）提供默认保障
- 系统 MUST 仍满足 `no-external-callback-under-lock`（不得把回调放回锁内）

#### Scenario: a non-thread-safe observer works correctly under concurrency
- **GIVEN** workflow 并发执行且注册了一个带可变状态的 observer
- **WHEN** workflow 产生多条事件并触发该 observer
- **THEN** observer 的回调 MUST 不被并发调用（同一时刻最多一个回调在执行）
- **AND** 事件序列 MUST 可解释且可复现

### Requirement: workflow capture+replay MUST summarize loader_call payloads

当 workflow 以并发模式执行且启用 components（observers/hooks）导致进入 capture+replay 路径时，系统 MUST 避免在捕获队列中保活 `loader_call` 的完整 loader result：

- 对 observer 的 loader call 事件，系统 MUST 使用 summary 级别的 loader result payload（包含类型与可选大小信息），而不是完整数据结构。
- 系统 MUST NOT 在捕获队列中保留对完整 loader result 的强引用（避免延长生命周期）。
- 对 typed hook 的 loader call 记录，系统 MUST 同样使用 summary 级别的 payload（或等价的轻量结构）。

该要求仅约束 capture+replay 捕获阶段的 payload 形态，不改变执行正确性，也不要求串行模式下改变原有事件 payload。

#### Scenario: observer loader_call payload is summarized under workflow concurrency
- **GIVEN** workflow 以并发模式运行且注册了订阅 loader call 事件的 observer
- **WHEN** 某个 loader 返回一个大结果并触发 loader call 事件
- **THEN** 被 capture 的事件 payload MUST 为 summary 结构（包含类型信息）
- **AND** 该 payload MUST NOT 等于完整 loader result 对象

#### Scenario: typed hook loader_call payload is summarized under workflow concurrency
- **GIVEN** workflow 以并发模式运行且注册了订阅 loader_call 的 typed hook
- **WHEN** 某个 loader 返回一个大结果并触发 loader call hook
- **THEN** 被 capture 的 loader_call 记录中 result MUST 为 summary 结构（包含类型信息）

### Requirement: file-based observers MUST provide a single-writer boundary by default

当系统处于并发执行模式且启用 file-based observers 时，系统 MUST 默认提供单写者边界以保证安全：

- observer 的文件写出 MUST NOT 依赖调用方线程安全
- 系统 MUST 串行化写出动作（single writer 或等价机制），避免回调线程直接并发写文件
- 该串行化机制 MUST 不破坏 `no-external-callback-under-lock`（不得把外部回调放回锁内）

#### Scenario: non-thread-safe observer does not corrupt file outputs under concurrency
- **GIVEN** 并发执行且启用了文件输出
- **WHEN** 多个执行单元触发事件写出
- **THEN** 输出文件 MUST 保持可解析且不发生并发写入损坏

### Requirement: a deterministic event ordering policy MUST be defined

系统 MUST 定义并发下事件的稳定排序策略（例如按声明顺序、按时间戳、或按节点/批次拓扑顺序），并用于 replay/drain 阶段。

#### Scenario: repeating a concurrent run yields the same event order
- **WHEN** 对同一 workflow 配置在并发模式下重复运行多次
- **THEN** 关键编排级事件序列 MUST 保持一致顺序
