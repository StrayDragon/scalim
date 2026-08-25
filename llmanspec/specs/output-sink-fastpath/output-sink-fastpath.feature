# language: zh-CN
# capability: output-sink-fastpath
# purpose: 为 sinks 提供可选的 aligned-write fastpath 接口（`write_column_aligned`/`write_row_aligned`），pipeline 优先使用 fastpath 以避免中间 dict 分配，回退兼容现有接口。 [scope-review-2026-07-13-c25-xlsx-ir-path-presence]
# scope: src/scalim/

功能: output-sink-fastpath

  @req:r66 @human
  场景: Optional aligned-write fastpath interfaces
    - 系统 MUST 为 sinks 提供可选的 aligned-write fastpath，以减少执行层在写出前构造中间 `dict` 的分配开销。 系统 MUST 定义以下可选接口（方法名为稳定契约）： - 对 `IColumnSink`：`write_column_aligned(field_key, row_ids, values)` - `row_ids` 与 `values` MUST 为等长序列 - `values[i]` 对应 `row_ids[i]` 的值 - 对 `IRowSink`：`write_row_aligned(field_keys, values)` - `field_keys` 与 `values` MUST 为等长序列 - `values[i]` 对应 `field_keys[i]` 的值

  @req:r310 @human
  场景: Pipeline prefers fastpath when available
    - 当 sink 支持 aligned-write fastpath 时，pipeline MUST 优先使用 fastpath，并且 MUST 避免构造等价的 `{row_id: value}` / `{field_key: value}` 中间 `dict`。

  @req:r433 @human
  场景: Backwards compatible fallback behavior
    - 当 sink 未实现 aligned-write fastpath 时，pipeline MUST 回退使用现有接口（`write_column`/`write_row` 等），并保持输出语义一致。
  @req:r66 @human
  场景: aligned-column-write-validates-lengths
    - 必须成立：当 `write_column_aligned` 收到长度不一致的 `row_ids` 与 `values`；那么 sink 实现 MUST fail-fast 抛出错误并指出不一致
    当 `write_column_aligned` 收到长度不一致的 `row_ids` 与 `values`
    那么 sink 实现 MUST fail-fast 抛出错误并指出不一致
  @req:r310 @human
  场景: column-mode-uses-aligned-write-when-supported
    - 必须成立：当 pipeline 运行在列式 sink 且 sink 支持 `write_column_aligned`；那么 pipeline MUST 通过 aligned-write 写出列数据
    当 pipeline 运行在列式 sink 且 sink 支持 `write_column_aligned`
    那么 pipeline MUST 通过 aligned-write 写出列数据

  @req:r310 @human
  场景: streaming-row-mode-uses-aligned-write-when-supported
    - 必须成立：当 pipeline 运行在行式流式 sink 且 sink 支持 `write_row_aligned`；那么 pipeline MUST 通过 aligned-write 写出行数据
    当 pipeline 运行在行式流式 sink 且 sink 支持 `write_row_aligned`
    那么 pipeline MUST 通过 aligned-write 写出行数据
  @req:r433 @human
  场景: existing-sinks-still-work-without-fastpath
    - 必须成立：当 用户提供的 sink 仅实现现有接口且不包含 aligned-write 方法；那么 pipeline MUST 仍可运行并产出与 fastpath 语义一致的结果
    当 用户提供的 sink 仅实现现有接口且不包含 aligned-write 方法
    那么 pipeline MUST 仍可运行并产出与 fastpath 语义一致的结果
