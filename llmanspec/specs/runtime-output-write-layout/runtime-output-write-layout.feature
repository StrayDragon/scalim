# language: zh-CN
# capability: runtime-output-write-layout
# purpose: 闭集 OutputWriteLayout（row_stream/column_buffered/column_chunked）作为 Python SSOT，统一文件 sink 工厂选择与互斥 fail-fast；禁止 YAML authoring 与静默自动切换。
# scope: src/scalim/execution/, src/scalim/dsl/yaml_dsl/

功能: runtime-output-write-layout

  @req:r1101 @human
  场景: OutputWriteLayout is a closed Python StrEnum SSOT
    - 系统 MUST 提供闭集 `OutputWriteLayout`（`StrEnum`），取值至少包含：`row_stream`、`column_buffered`、`column_chunked`。公共构造/options（如 `DemandRunRuntimeOptions` / `ExecutionRequest`）MUST 仅接受该 Enum（拒 builtin str）。落盘/JSON/状态出站 MUST 使用 builtin `str`（`.value`）。

  @req:r1102 @human
  场景: Effective layout resolution priority
    - 当装配文件 sink（非手写 `ExecutionRequest.sink`）时，系统 MUST 按以下优先级解析 effective layout：1) 显式 `output_write_layout`；2) 由 `OutputSpec.streaming` 与 `ExcelColumnResidency` 按文档化推导表推导；3) 默认（存在 `output_composition` 时为 `row_stream`；否则保持历史默认：行文件 streaming 或列缓冲）。系统 MUST NOT 静默忽略显式 layout。

  @req:r1103 @human
  场景: Factory maps layout to concrete sinks
    - 对 csv/excel 文件 sink，系统 MUST 按 effective layout 选择实现：`row_stream`→行式 `CSVSink`/`ExcelSink`；`column_buffered`→`ColumnCSVSink`/`ColumnExcelSink`；`column_chunked`→仅 excel 的 `StreamingColumnExcelSink`。手写传入的 `sink` MUST 绕过该映射。

  @req:r1104 @human
  场景: Illegal combinations MUST fail-fast
    - 下列组合 MUST fail-fast 并给出可诊断提示，MUST NOT 静默降级：`column_chunked` 用于非 excel（含 csv）；effective `column_buffered` 或 `column_chunked` 与 `output_composition`（YAML books 行组合）同时存在。`ExcelColumnResidency.CHUNKED` 与 composition 的既有 fail-fast MUST 保持或被本规则覆盖且文案不弱化。

  @req:r1105 @human
  场景: YAML MUST NOT author write layout knobs
    - YAML authoring MUST NOT 声明 `output_write_layout` / residency / streaming sink 实现字段。出现时 MUST fail-fast（与 runtime policy boundary 一致）。

  @req:r1106 @human
  场景: Unset layout MUST not change historical sink selection
    - 当调用方未设置显式 `output_write_layout` 时，系统 MUST 选择与本 change 之前相同的 concrete sink 类型（对相同 streaming/residency/composition 输入）。

  @req:r1101 @human
  场景: rejects-string-layout
    - 必须成立：当 调用方以 builtin str 传入 output_write_layout；那么 系统 MUST 拒绝（TypeError 或等价）
    当 调用方以 builtin str 传入 output_write_layout
    那么 系统 MUST 拒绝（TypeError 或等价）

  @req:r1102 @human
  场景: explicit-layout-wins-over-streaming
    - 必须成立：当 显式 column_buffered 且 OutputSpec.streaming=true；那么 effective layout MUST 为 column_buffered（或在非法组合下 fail-fast，不得静默改回 row_stream）
    当 显式 column_buffered 且 OutputSpec.streaming=true
    那么 effective layout MUST 为 column_buffered（或在非法组合下 fail-fast，不得静默改回 row_stream）

  @req:r1103 @human
  场景: row-stream-selects-excel-sink
    - 必须成立：当 effective row_stream 且 format=excel；那么 工厂 MUST 产出行式 ExcelSink（或等价 IRowSink）
    当 effective row_stream 且 format=excel
    那么 工厂 MUST 产出行式 ExcelSink（或等价 IRowSink）

  @req:r1103 @human
  场景: column-chunked-selects-streaming-column-excel
    - 必须成立：当 effective column_chunked 且 format=excel 且无 composition；那么 工厂 MUST 产出 StreamingColumnExcelSink
    当 effective column_chunked 且 format=excel 且无 composition
    那么 工厂 MUST 产出 StreamingColumnExcelSink

  @req:r1104 @human
  场景: csv-column-chunked-fails-fast
    - 必须成立：当 format=csv 且显式 column_chunked；那么 系统 MUST fail-fast
    当 format=csv 且显式 column_chunked
    那么 系统 MUST fail-fast

  @req:r1104 @human
  场景: composition-plus-column-layout-fails-fast
    - 必须成立：当 存在 output_composition 且显式 column_buffered 或 column_chunked；那么 系统 MUST fail-fast
    当 存在 output_composition 且显式 column_buffered 或 column_chunked
    那么 系统 MUST fail-fast

  @req:r1105 @human
  场景: yaml-layout-field-rejected
    - 必须成立：当 demand YAML 声明 output_write_layout 或 write.streaming；那么 validate/parse MUST fail-fast
    当 demand YAML 声明 output_write_layout 或 write.streaming
    那么 validate/parse MUST fail-fast

  @req:r1106 @human
  场景: unset-layout-preserves-legacy-sink
    - 必须成立：当 未设 output_write_layout 的历史 streaming/residency 组合；那么 concrete sink 类型 MUST 与变更前一致
    当 未设 output_write_layout 的历史 streaming/residency 组合
    那么 concrete sink 类型 MUST 与变更前一致
