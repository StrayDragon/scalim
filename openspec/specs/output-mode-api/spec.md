# output-mode-api Specification

**状态: ✅ 已实现**
## Purpose
定义运行时输出语义为“显式 sink 驱动”: 是否保留内存数据、是否写文件、以及是否同时写入(tee)都通过 sink 选择表达,而不是通过 `return_data` 等布尔参数驱动 runtime 隐式装配.
同时要求稳定的执行元数据(例如 `ExecutionResult.total_rows`)以及异常路径的 best-effort 资源清理.

## Related Code (as implemented)
- `src/IMPL_ROOT/execution/run_ir.py` (output plan, tee, `total_rows`, null sink)
- `src/IMPL_ROOT/sinks/sink_base.py` (`ISink`/`IRowSink`/`IColumnSink`)
- `src/IMPL_ROOT/sinks/_internal/memory.py` (`InMemoryRowDataSink`)
- `src/IMPL_ROOT/sinks/sink_csv.py` / `src/IMPL_ROOT/sinks/sink_excel.py` (file sinks)

## Requirements

### Requirement: 输出是否保留内存数据由 sink 表达
系统 MUST 将“是否在内存中保留结果数据”的表达权交还给 sink 选择,并破坏性移除 `return_data: Optional[bool]`(及其隐式推断/tee 装配).

#### Scenario: 需要内存数据时显式使用内存 sink
- **WHEN** 用户需要在运行后获取内存数据
- **THEN** 用户应显式传入内存 sink(例如 `InMemoryRowDataSink`)并通过 sink 读取数据,而不是通过 `return_data=True` 触发 runtime 侧隐式拼装

### Requirement: 无输出时避免构造返回列表
系统 MUST 在“无文件输出且未提供显式 sink”的情况下避免 pipeline 构造返回列表造成的内存分配.
execution 编排入口 MUST 使用 NullSink/DiscardSink(或等价实现)作为默认 sink.

#### Scenario: 无文件输出且无显式 sink
- **WHEN** `OutputSpec.path` 为空且未提供显式 sink
- **THEN** 系统不应构造/返回结果列表,且不应在内存中累积结果行

### Requirement: 允许 tee 同时写文件与显式 sink
系统 SHALL 支持在存在文件输出(`OutputSpec.path`)且提供显式 sink 时通过 tee 同时写入二者,前提是 sink 类型兼容:
- row sink + row sink
- column sink + column sink

若二者类型不兼容,系统 MUST 抛出清晰错误并提示如何修正.

#### Scenario: streaming 输出同时写文件与内存 sink
- **WHEN** `output.streaming=true` 且提供 `InMemoryRowDataSink`
- **THEN** 系统应通过 tee 同时写文件与内存 sink,且二者内容一致

### Requirement: total_rows 为稳定元数据
系统 MUST 在执行结果元数据中提供稳定的行数统计(例如 `ExecutionResult.total_rows`),且该值 MUST 不依赖“是否返回 data”.
系统 MUST 通过内部统计器计算该值,且统计口径 SHOULD 贴近用户直觉: **以实际写出/产出(emit)的行数为准**.
系统 MUST 明确该口径为 emitted_rows: 以实际写出/产出(emit)到 effective sink 的行数为准(包括 NullSink),而非输入 `row_ids` 数量.
若同时启用性能观测插件(例如 `PerformanceObserver`),其 `PerformanceMetrics.total_rows` 允许使用 input row_ids 口径用于吞吐估算;系统 SHOULD 在文档/类型注释中显式区分二者以避免监控误读.
实现方式可以是:
- 通过内部 `CountingSink`/row-counter wrapper 统计 sink 写入行数
- 或基于批次/写入事件统计(需保证与写出行数一致)

#### Scenario: total_rows 不依赖是否保留内存数据
- **WHEN** 使用相同输入分别运行: (a) 仅写文件 (b) 仅写内存 sink (c) 无输出(NullSink)
- **THEN** `ExecutionResult.total_rows` 在三种情况下应一致

### Requirement: 成功路径 sink.close 失败必须使 run 失败
系统 MUST 将 sink 的 close 视为输出落盘/提交的最终阶段.
当 `engine.run(...)` 已成功完成时,`run_ir` MUST 调用 `sink.close()` 并将其异常向上传播,不得返回“成功”的 `ExecutionResult`.

#### Scenario: run 成功但 close 失败导致 run_ir 失败
- **GIVEN** `engine.run(...)` 成功完成
- **WHEN** `sink.close()` 在 close 阶段抛出异常
- **THEN** `run_ir(...)` MUST 失败并抛出该异常

### Requirement: 异常路径 close 不得覆盖原异常
当 `engine.run(...)` 在执行中抛异常时,系统 MUST best-effort 调用 `sink.close()` 做清理,但 close 异常 MUST NOT 覆盖原始执行异常.

#### Scenario: engine.run 抛异常且 close 同时失败
- **GIVEN** `engine.run(...)` 抛出异常 `E1`
- **WHEN** `sink.close()` 额外抛出异常 `E2`
- **THEN** `run_ir(...)` MUST 抛出 `E1`(不得被 `E2` 覆盖)

### Requirement: 异常路径 best-effort 关闭 sink
系统 MUST 在执行过程中发生异常时尽最大努力关闭 sink,以减少临时文件遗留与句柄泄漏风险.

#### Scenario: sink.write 触发异常
- **WHEN** sink 在写入过程中抛出异常
- **THEN** execution 编排入口仍应 best-effort 调用 sink.close()
