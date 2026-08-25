# language: zh-CN
# capability: streaming-output
# purpose: 支持 IRowSink 与 IColumnSink 的流式写入路径,定义 main source 行流、分批与 `row_id` 规则,并约束行式路径"行就绪即写出 + rows 绑定 release 屏障"语义. [scope-review-2026-07-13-c25-xlsx-ir-path-presence]
# scope: src/scalim/

功能: streaming-output

  @req:r75 @human
  场景: 行流输入与分批规则
    - 系统 SHALL 支持 main source loader 返回 `Iterable[RowData]`,并将其中每个元素视为一行进行处理;支持在 main_source 中声明 `params` 并透传给 loader. main_source 不支持 bindings 机制. 系统 SHALL 按 `batch_size` 对行流分批处理,并按 loader 原始行顺序为每行分配 `row_id`(全局递增). `batch_size` MUST 允许 `null` 或整数且 `>=1`: - `batch_size=null` 表示禁用分批,本次运行对 main source 行流执行单批处理. - `batch_size=<int>=1` 表示按固定批大小分批处理. `0`、负数、布尔值、浮点数、字符串等非法取值 MUST 被拒绝(避免出现"静默处理 0 行"或隐式截断). 当未配置 `main_source.order_by` 时,系统 SHALL 保持原始行顺序作为批次内写入顺序. 当配置 `main_source.order_by` 时,系统 SHALL 在每个批次写入前按主数据源字段进行稳定排序(`null` 始终在最后),排序仅影响写入顺序与事件 `row_index`,不改变计算顺序与 `row_id` 分配;列式 sink 的 `set_row_ids` 顺序也应遵循该排序. 排序字段可不在输出字段中,系统仍应使用其值进行排序.

  @req:r319 @human
  场景: row_id 语义与事件暴露
    - 系统 SHALL 为每行分配内部 `batch_row_nth`(一次运行内全局递增)作为 `row_id`,用于上下文索引、sink 写入对齐与 hook 事件标识;该值不是业务主键.

  @req:r442 @human
  场景: 流式 sink 行/列写入与事件触发
    - 系统 SHALL 在 IRowSink 路径按行写入并在每行写入后触发 RowWriteEvent 与 RowReleaseEvent. 系统 SHALL 在 IColumnSink 路径先调用 set_row_ids,再在字段就绪时写入列并触发 ColumnWriteEvent.

  @req:r531 @human
  场景: IRowSink 路径行就绪即写出
    - 系统 SHALL 在 IRowSink 路径采用行就绪驱动:当某行目标字段全部就绪时 MUST 立即写出并释放该行可释放字段,不得整体等待批次结束.

  @req:r605 @human
  场景: rows 绑定会触发 release 屏障
    - 系统 SHALL 在执行计划存在 rows 绑定 LoadRef 时启用 release 屏障:在屏障未解除前暂停行级释放(`release`),避免 rows 绑定依赖的批次上下文被提前清理. 该语义是当前实现中的保守策略:写出仍可按"行就绪即写出"发生,但字段释放会被整体延后到屏障解除之后.

  @req:r1108 @human
  场景: File sink factory MUST honor OutputWriteLayout
    - 当通过文件 sink 工厂（非手写 `ExecutionRequest.sink`）装配输出时，系统 MUST 按 `runtime-output-write-layout` 的 effective `OutputWriteLayout` 选择行式或列式 concrete sink；本 spec 的行/列写出与 release 语义仍适用于所选 sink 类型。本条不重复 layout 闭集与互斥矩阵细节。
  @req:r75 @human
  场景: 行流批次切分保持原始顺序
    - 必须成立：当 main source 行数为 5、`batch_size=2` 且未配置 `main_source.order_by`；那么 引擎应处理 3 个批次并按原始顺序输出 5 行
    当 main source 行数为 5、`batch_size=2` 且未配置 `main_source.order_by`
    那么 引擎应处理 3 个批次并按原始顺序输出 5 行

  @req:r75 @human
  场景: batch-size-为-null-时单批执行
    - 必须成立：当 main source 行数为 5 且 `batch_size=null`；那么 引擎应仅处理 1 个批次并输出 5 行
    当 main source 行数为 5 且 `batch_size=null`
    那么 引擎应仅处理 1 个批次并输出 5 行

  @req:r75 @human
  场景: 批次内稳定排序
    - 必须成立：当 某批次主数据源 `order_id` 顺序为 `[3, 1, 2, 2]` 且 `main_source.order_by=["order_id"]`；那么 该批次输出顺序为 `[1, 2(原第3行), 2(原第4行), 3]`
    当 某批次主数据源 `order_id` 顺序为 `[3, 1, 2, 2]` 且 `main_source.order_by=["order_id"]`
    那么 该批次输出顺序为 `[1, 2(原第3行), 2(原第4行), 3]`

  @req:r75 @human
  场景: 非法-batch-size-被拒绝
    - 必须成立：当 配置 `batch_size` 为 `0` 或 `-1` 或 `true` 或 `1.5` 或 `"oops"`；那么 校验 MUST 失败并给出 `batch_size` 字段路径
    当 配置 `batch_size` 为 `0` 或 `-1` 或 `true` 或 `1.5` 或 `"oops"`
    那么 校验 MUST 失败并给出 `batch_size` 字段路径
  @req:r319 @human
  场景: 重复业务键不应被覆盖
    - 必须成立：当 main source 中存在两行业务键相同的记录；那么 引擎应分配不同 `row_id` 并输出两行结果
    当 main source 中存在两行业务键相同的记录
    那么 引擎应分配不同 `row_id` 并输出两行结果
  @req:r442 @human
  场景: 行式写入
    - 必须成立：当 pipeline 使用 IRowSink；那么 系统应逐行调用 write_row 并触发行写入/释放事件
    当 pipeline 使用 IRowSink
    那么 系统应逐行调用 write_row 并触发行写入/释放事件

  @req:r442 @human
  场景: 列式写入
    - 必须成立：当 pipeline 使用 IColumnSink；那么 系统应调用 set_row_ids 后按列写入并触发 ColumnWriteEvent
    当 pipeline 使用 IColumnSink
    那么 系统应调用 set_row_ids 后按列写入并触发 ColumnWriteEvent
  @req:r531 @human
  场景: 行在批次结束前写出
    - 必须成立：当 批次内前半部分行已满足目标字段就绪条件；那么 系统应在批次结束前写出这些行
    当 批次内前半部分行已满足目标字段就绪条件
    那么 系统应在批次结束前写出这些行
  @req:r605 @human
  场景: rows-绑定触发全局-release-延后
    - 必须成立：当 执行计划中存在 rows 绑定 LoadRef 且屏障未解除；那么 行式路径可以继续写出已就绪行
    当 执行计划中存在 rows 绑定 LoadRef 且屏障未解除
    那么 行式路径可以继续写出已就绪行

  @req:r1108 @human
  场景: factory-selects-sink-by-layout
    - 必须成立：当 effective layout 为 row_stream 或 column_* 且走文件 sink 工厂；那么 系统 MUST 选用与 layout 匹配的 IRowSink 或 IColumnSink 实现（详见 runtime-output-write-layout）
    当 effective layout 为 row_stream 或 column_* 且走文件 sink 工厂
    那么 系统 MUST 选用与 layout 匹配的 IRowSink 或 IColumnSink 实现（详见 runtime-output-write-layout）
