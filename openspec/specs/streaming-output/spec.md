# streaming-output Specification

**状态: ✅ 已实现**
## Purpose
支持 IRowSink 与 IColumnSink 的流式写入路径,定义 main source 行流、分批与 `row_id` 规则,并约束行式路径“行就绪即写出 + rows 绑定 release 屏障”语义.

## Context
**FR023: 流式写入(列or行)**

需要支持即时写入模式,不过多占用运行时内存占用.

## Related Code (as implemented)
- `src/IMPL_ROOT/execution/pipeline/base/pipeline.py` (batching/order_by + row/column emission)
- `src/IMPL_ROOT/execution/pipeline/base/_row_emission.py` (RowEmissionCoordinator)
- `src/IMPL_ROOT/sinks/sink_base.py` (IRowSink/IColumnSink contracts)
- `src/IMPL_ROOT/sinks/sink_csv.py` / `src/IMPL_ROOT/sinks/sink_excel.py` (file sinks)
## Requirements
### Requirement: 行流输入与分批规则
系统 SHALL 支持 main source loader 返回 `Iterable[RowData]`,并将其中每个元素视为一行进行处理;支持在 main_source 中声明 `params` 并透传给 loader.
main_source 不支持 bindings 机制.
系统 SHALL 按 `batch_size` 对行流分批处理,并按 loader 原始行顺序为每行分配 `row_id`(全局递增).
`batch_size` MUST 允许 `null` 或整数且 `>=1`:
- `batch_size=null` 表示禁用分批,本次运行对 main source 行流执行单批处理.
- `batch_size=<int>=1` 表示按固定批大小分批处理.
`0`、负数、布尔值、浮点数、字符串等非法取值 MUST 被拒绝(避免出现“静默处理 0 行”或隐式截断).
当未配置 `main_source.order_by` 时,系统 SHALL 保持原始行顺序作为批次内写入顺序.
当配置 `main_source.order_by` 时,系统 SHALL 在每个批次写入前按主数据源字段进行稳定排序(`null` 始终在最后),排序仅影响写入顺序与事件 `row_index`,不改变计算顺序与 `row_id` 分配;列式 sink 的 `set_row_ids` 顺序也应遵循该排序.
排序字段可不在输出字段中,系统仍应使用其值进行排序.

#### Scenario: 行流批次切分保持原始顺序
- **WHEN** main source 行数为 5、`batch_size=2` 且未配置 `main_source.order_by`
- **THEN** 引擎应处理 3 个批次并按原始顺序输出 5 行

#### Scenario: batch_size 为 null 时单批执行
- **WHEN** main source 行数为 5 且 `batch_size=null`
- **THEN** 引擎应仅处理 1 个批次并输出 5 行

#### Scenario: 批次内稳定排序
- **WHEN** 某批次主数据源 `order_id` 顺序为 `[3, 1, 2, 2]` 且 `main_source.order_by=["order_id"]`
- **THEN** 该批次输出顺序为 `[1, 2(原第3行), 2(原第4行), 3]`

#### Scenario: 非法 batch_size 被拒绝
- **WHEN** 配置 `batch_size` 为 `0` 或 `-1` 或 `true` 或 `1.5` 或 `"oops"`
- **THEN** 校验 MUST 失败并给出 `batch_size` 字段路径

### Requirement: row_id 语义与事件暴露
系统 SHALL 为每行分配内部 `batch_row_nth`(一次运行内全局递增)作为 `row_id`,用于上下文索引、sink 写入对齐与 hook 事件标识;该值不是业务主键.

#### Scenario: 重复业务键不应被覆盖
- **WHEN** main source 中存在两行业务键相同的记录
- **THEN** 引擎应分配不同 `row_id` 并输出两行结果

### Requirement: 流式 sink 行/列写入与事件触发
系统 SHALL 在 IRowSink 路径按行写入并在每行写入后触发 RowWriteEvent 与 RowReleaseEvent.
系统 SHALL 在 IColumnSink 路径先调用 set_row_ids,再在字段就绪时写入列并触发 ColumnWriteEvent.

#### Scenario: 行式写入
- **WHEN** pipeline 使用 IRowSink
- **THEN** 系统应逐行调用 write_row 并触发行写入/释放事件

#### Scenario: 列式写入
- **WHEN** pipeline 使用 IColumnSink
- **THEN** 系统应调用 set_row_ids 后按列写入并触发 ColumnWriteEvent

### Requirement: IRowSink 路径行就绪即写出
系统 SHALL 在 IRowSink 路径采用行就绪驱动:当某行目标字段全部就绪时 MUST 立即写出并释放该行可释放字段,不得整体等待批次结束.

#### Scenario: 行在批次结束前写出
- **WHEN** 批次内前半部分行已满足目标字段就绪条件
- **THEN** 系统应在批次结束前写出这些行

### Requirement: rows 绑定会触发 release 屏障
系统 SHALL 在执行计划存在 rows 绑定 LoadRef 时启用 release 屏障:在屏障未解除前暂停行级释放(`release`),避免 rows 绑定依赖的批次上下文被提前清理.
该语义是当前实现中的保守策略:写出仍可按“行就绪即写出”发生,但字段释放会被整体延后到屏障解除之后.

#### Scenario: rows 绑定触发全局 release 延后
- **WHEN** 执行计划中存在 rows 绑定 LoadRef 且屏障未解除
- **THEN** 行式路径可以继续写出已就绪行
- **AND** 行级 release 不应提前清理字段缓存

### Requirement: YAML 输出配置驱动 sink
系统 SHALL 根据 output.format 与 output.streaming 选择 CSV/Excel 的行式或列式 sink.

#### Scenario: CSV 流式输出
- **WHEN** output.format=csv 且 output.streaming=true
- **THEN** 系统应使用 IRowSink 实现进行写入

### Requirement: 表头生成规则
系统 SHALL 通过 `output.header_fields_output_by` 控制 header 字段来源,并通过 `output.include_header` 控制是否写入表头行.
- `header_fields_output_by=field_id`(默认): 使用字段 key
- `header_fields_output_by=name`: 使用字段 name,缺失时 fallback 为 field_id

#### Scenario: include_header=false
- **WHEN** output.include_header=false 且输出格式为 CSV 或 Excel
- **THEN** 输出文件不包含表头行,第一行即为数据行

### Requirement: 行式 Sink 缓冲 flush 策略
文件型行式 sink SHALL 支持 flush 策略;当前默认策略为 `flush_policy=every_n_rows`,并使用 `flush_every_rows=1000`(`run_ir` 内置默认).
底层 sink 实现支持 `flush_policy=always` 与 `flush_policy=every_n_rows`(`flush_every_rows>=1`),但 YAML `output` 配置当前不暴露该策略字段.

#### Scenario: 按 N 行 flush
- **WHEN** CSV 行式 sink 配置 flush_policy=every_n_rows 且 flush_every_rows=1000
- **THEN** sink MUST 至多每 1000 行 flush 一次

## Notes
- RowReleaseEvent 用于标记该行缓存字段已真实释放;通常紧随 RowWriteEvent,但在 rows 绑定屏障存在时可能被推迟.
- 并发模式与流式 sink 的兼容性语义见 `parallel-execution`(`seq|adaptive` 均允许 IRowSink/IColumnSink).
