# parallel-execution Specification

## Purpose
定义执行层对外并发语义 `seq|adaptive`,以及 `adaptive` 下的调度边界、后端选择、结果提交与事件回放契约.

## Related Concepts
- 执行引擎
- 执行运行时
- LoadRef 调度器
- Adaptive pool/backends
- 策略配置
- Capture 机制

## Requirements

### Requirement: 对外并发模式与参数
系统 MUST 支持 `parallel_mode=seq|adaptive`;其它值 MUST 失败并提示合法值.
历史 `parallel_mode="thread"|"process"` MUST 视为已移除并给出迁移提示(使用 `adaptive` 或 `seq`).
`max_workers` 作为 `adaptive` 并发上限提示,`0=自动`,在 `seq` 下忽略.

#### Scenario: 非法并发模式失败
- **WHEN** `parallel_mode="invalid"`
- **THEN** 系统 MUST 失败并提示期望值为 `seq|adaptive`

### Requirement: adaptive 并发边界仅限批次内 LoadRef(keys)
系统 MUST 将 `adaptive` 的并发边界限定为:单个批次内、同一依赖层、互不依赖的 `LoadRef(keys)` fan-out/fan-in.
系统 MUST NOT 并行多个批次;`load/compute/write/release` 等非 LoadRef 算子 MUST 仍按计划顺序串行.
`bind.mode=rows` MUST 作为层级并行屏障:该层任务串行执行.

#### Scenario: adaptive 仅并行 LoadRef(keys)
- **WHEN** `parallel_mode=adaptive`
- **THEN** 系统 MUST 仅对符合条件的 LoadRef(keys) 启用并发,其它算子仍按计划顺序串行执行

#### Scenario: rows 屏障触发串行
- **WHEN** 同层存在任一 `bind.mode=rows` 的 LoadRef
- **THEN** 该层 LoadRef MUST 串行执行

### Requirement: adaptive runtime shared caches MUST document CPython+GIL-only safety
系统 MUST 明确声明:`parallel_mode=adaptive` 并发路径中的共享 `dict/set` 缓存与计数器仅在 **GIL-backed CPython** 下承诺正确性(依赖实现细节而非语言语义保证)。

当 `parallel_mode=adaptive` 启用批次内并发时,执行层会在多个 worker 线程间共享部分 `dict/set` 缓存与计数器(例如 key normalize cache 与 load-ref cache)。系统 MUST 明确声明以下契约:
- 这些结构当前不提供显式锁保护
- 其并发正确性仅在 **GIL-backed CPython** 下成立
- free-threaded/no-GIL Python 不在支持范围内(若要支持,必须引入锁或等价同步策略)

系统 MUST 在对应实现的模块/类级别或关键字段附近以 `NOTE:` / `WARN:` 注释形式写出上述信息,使维护者在阅读热点代码时能直接看到契约边界。

#### Scenario: maintainer can discover the CPython+GIL-only contract near the hot caches
- **WHEN** 维护者阅读 `ExecutionRuntime` 及 `LoadRef` key-normalize cache 相关实现
- **THEN** 必须能在关键共享缓存/计数器附近看到 `NOTE:` / `WARN:` 注释
- **AND** 注释必须明确包含 "CPython" 与 "GIL" 的支持边界说明

### Requirement: 阈值 gate 与并发上限决定退化行为
系统 MUST 使用阈值策略决定是否启用并发(如同层任务数、keys 规模).
当任务规模不足或 `resolve_adaptive_max_workers(...)<=1` 时 MUST 退化为串行语义.
`max_workers=0` 时自动解析并发上限,自动值 MUST >= 1.

#### Scenario: 小规模任务退化串行
- **WHEN** 同层仅 1 个可并行任务或阈值判定不满足
- **THEN** 该层 MUST 串行执行

### Requirement: tuning/policy 为 adaptive 内部调度扩展点
系统 MUST 支持 `AdaptiveTuning`(或等价对象)配置 pools、source-pool 映射、阈值与并发上限.
系统 MUST 支持 `AdaptivePolicy`(或等价接口)作为高级扩展;当 policy 与 tuning 同时存在时,以 policy 决策为准.

#### Scenario: source 受 pool 限流
- **WHEN** tuning 配置 `source_pools={"customers":"db"}` 且 `pools={"db":2}`
- **THEN** `customers` 相关并发任务同时运行数 MUST 不超过 2

### Requirement: backend 选择为高级 opt-in 且同次运行保持一致
系统 MUST 默认 thread backend.
系统 MUST 保留对 process/async backend 的"选择接口形状"(例如 policy 常量/返回值),但在当前版本中,process/async backend MUST NOT 被实际启用.
系统 MUST 在创建 adaptive pool/executor 时确定 backend,并在同一次运行内复用该 backend(例如缓存于 runtime),调度器不得按层反复改选 backend.

#### Scenario: backend 决策单次复用
- **GIVEN** policy 的 `choose_backend` 多次调用可能返回不同值
- **WHEN** 一次运行创建并执行 adaptive pool
- **THEN** 实际执行 backend MUST 在本次运行内保持一致

#### Scenario: 选择未实现 backend 失败
- **WHEN** policy 选择 process 或 async backend
- **THEN** 系统 MUST 立即失败并明确指出"该 backend 暂不支持,当前仅支持 thread"
- **AND** 错误信息 MUST 指引"请将 backend 改为 thread"

### Requirement: 并发结果采用完成优先回收与计划顺序提交
系统 MUST 对并发任务采用完成优先回收(避免慢队头阻塞回收),并按计划顺序提交结果到上下文.
系统 MUST 采用首错优先异常传播,并对未完成任务执行 best-effort 取消.

#### Scenario: 回收与提交顺序分离
- **WHEN** task#2 先完成、task#1 后完成
- **THEN** 系统可先回收 task#2 结果,但最终提交顺序 MUST 为 task#1 再 task#2

### Requirement: hooks/observers 采用 capture + commit-time replay
在 `adaptive` 下,worker 线程 MUST 仅记录事件,不直接执行用户 hook/observer 回调.
系统 MUST 在提交点按确定性顺序回放事件,且回放顺序与结果提交顺序一致.
capture 记录 MUST 有界并具备明确超限策略(raise 或确定性丢弃).
系统 MUST 保持 wants-gated:未订阅事件不得构建 payload 或记录事件.

#### Scenario: adaptive 回放顺序稳定
- **WHEN** 同层任务完成顺序与计划顺序不一致
- **THEN** hook/observer 感知到的回放顺序 MUST 与计划提交顺序一致

### Requirement: 与流式 sink 兼容
系统 MUST 允许 `parallel_mode=seq|adaptive` 下使用 `IRowSink`/`IColumnSink`,不得因并发模式拒绝流式 sink.

#### Scenario: adaptive 允许流式 sink
- **WHEN** `parallel_mode=adaptive` 且传入 IRowSink 或 IColumnSink
- **THEN** pipeline MUST 正常执行且不抛出"并行模式禁用流式"错误

### Requirement: adaptive worker runtimes MUST inherit run-level key_normalization
当 `parallel_mode=adaptive` 创建 worker 子运行时(用于在提交点前执行 `LoadRef(keys)` 的 fan-out/fan-in)时,系统 MUST 继承本次 run-level 的 `key_normalization` 配置到该子运行时,以避免并发路径与串行路径语义漂移.

说明:
- 子运行时内部可以使用 `parallel_mode="seq"` 执行单个任务以保持确定性,但其 key space 语义 MUST 与父运行时一致。
- 该要求不改变 `key_normalization` 的算法,仅要求"配置传播"一致。

#### Scenario: worker 子运行时继承父运行时的 key_normalization
- **GIVEN** run-level `key_normalization="canonical"`
- **WHEN** `parallel_mode=adaptive` 创建 worker 子运行时执行 LoadRef(keys)
- **THEN** worker 子运行时的 `key_normalization` MUST 为 `"canonical"`
- **AND** 返回的字段键 MUST 与串行路径一致
