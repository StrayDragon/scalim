## Context

假设 `c0-xlsx-memory-internal-field-headers` 已实现后,`xlsx_memory` 的内部键空间已经被收敛到 canonical field key,display header 也已退出内部链路。剩余的主要问题是值域仍沿用 `CSV` 等价字符串化语义:

- workflow-managed outputs 写入 `xlsx_memory` 时走 `InMemoryCsv` / `List[List[str]]`
- `sheetbook` 内部 segments 存的是字符串 rows
- `book_sheet_rows` 读回的也是字符串 rows

这导致两类直接成本:

1. 正确性成本: `_auto_cast` 这类猜测式恢复会把 `"007"` 误变成 `7`,也无法可靠处理 `Decimal`、`bool` 和真实 `None`
2. 性能成本: 对 workflow 内部非结束节点的 `in memory` 路径而言,“typed value -> str -> typed value”是纯额外开销

仓库当前已经存在 typed 基础设施 `InMemoryRows`,但它是按整个 demand run 捕获的,不是按 output 捕获的; 而 workflow 写节点消费的是 `input_output_id` 级别的 managed artifact。这意味着本 change 不能只写“读的时候做类型恢复”,还必须解决“类型与 typed rows 如何跟随具体 output 进入 `xlsx_memory`”,并把“是否 workflow-managed”与“artifact 语义”从现有 `OutputSpec(format=csv)` 假设中拆出来。

约束:

- Python 3.6 runtime 兼容
- 不新增 book kind
- 不增加 `typed: true` 之类的 opt-in DSL
- 不改变 `xlsx_file` / `csv_file` 行为
- 不发明基于空串的猜测性 `None` 恢复
- 不负责 `compute/call_by` 如何产生 `Decimal`; 该职责由独立的 `yaml-compute-decimal` change 约束
- 假设 header 纯化 change 已经使 `xlsx_memory` 内部只使用 canonical field key

## Goals / Non-Goals

**Goals:**
- 让 `xlsx_memory` 在 workflow 内部链路中保留 `FieldValue` 类型域,避免热点路径字符串化
- 让 `book_sheet_rows` 默认返回 typed rows,同时保持 canonical field key
- 将 spreadsheet/export 专属转换压缩到最终 `export_xlsx` commit 边界
- 对 exact numeric values 保持“原样保真”: 上游若产出 `Decimal`,内部链路不得隐式降级为 `float`
- 在现有 `xlsx_memory` book kind 内完成升级,不引入并行 authoring surface

**Non-Goals:**
- 不为 `xlsx_file` / `csv_file` 或外部文件重读链路补 typed 语义
- 不新增 typed book kind
- 不新增 `typed` 参数或兼容式双语义读取 API
- 不自动把用户已有 `float` 数据改写成 `Decimal`
- 不把字符串空串 `\"\"` 猜测性提升为 `None`

## Decisions

### 1. 现有 `xlsx_memory` 直接升级为 typed internal container

`xlsx_memory` 继续保留现有 book kind,但其内部运行时语义改为 typed:

- sheetbook internal rows/segments 使用 `FieldValue` 值域
- `book_sheet_rows` / `iter_sheetbook_sheet_rows` 返回 typed row mappings
- 内部 append/read/baseline 契约不再以字符串 rows 为 SSOT

这样做的原因:

- 与“workflow 内部 in-memory 容器”定位一致
- 能真正消除热点路径上的 stringify/recast 开销
- 避免引入新的 book kind 和新的 DSL surface

备选方案是“仍保存字符串 rows,同时保存 field type sidecar,读取时再做确定性反序列化”。这个方案可以解决语义错误,但仍把热点路径保留为 `typed -> str -> typed`,对性能目标不够彻底。因此它最多只能作为短期实现桥接,不能作为最终设计 SSOT。

### 2. 为 workflow-managed 输出建立显式 typed runtime contract

当前 workflow write nodes 以 `input_output_id` 为消费粒度,而现有 runtime 通过 `OutputSpec(format="csv", path=None)` 与 `in_memory_csv_outputs` 把 workflow-managed 语义硬编码成“内存 CSV”。本 change 要求把这两层解耦:

- `OutputTargetSpec` / `ExecutionResult` / workflow artifacts 必须显式区分 managed artifact 语义,而不是继续把它们伪装成 `OutputSpec(format=csv)`
- 对所有将被 `xlsx_memory` 写节点消费的 workflow-managed outputs,系统必须提供按 output 粒度的 typed managed artifact
- 若同一 producer output 同时服务于 `xlsx_memory` 和 `CSV` 等价 consumer,系统可以从 typed artifact 派生字符串 artifact,但 `xlsx_memory` 路径不能再以字符串 artifact 为 SSOT

选择显式 runtime contract + per-output typed artifact,而不是继续复用 `OutputSpec(format=csv)` 或仅存 `field_id -> type` metadata 的原因:

- 现有 `OutputSpec(format=csv)` 会把 internal runtime semantics 与外部文件导出语义混在一起
- 只存 metadata 仍然保留了字符串 rows,无法消除热路径转换
- `book_sheet_rows` 的目标是直接返回 typed values,最短路径就是从 typed rows 写入 `sheetbook`
- output 粒度与 workflow write 节点的输入模型天然对齐

### 3. `sheetbook` 与 write path 基于统一的 tabular artifact 适配协议

为了避免 `sheetbook` 内部继续暴露 `input_csv` 这类历史命名,本 change 采用统一的 tabular artifact 适配协议:

- `header() -> Sequence[str]`
- `iter_rows() -> Iterable[Sequence[FieldValue]]`
- 仅在明确需要字符串 consumer 时,再显式做 `to_csv_rows()` 或等价转换

这样 `sheetbook` / `xlsx_memory` write path 内部只关心 typed row model,而 CSV 只是其中一种 adapter。

采用该协议而不是把 `WorkflowCsvInput` 扩成更大的 union 的原因:

- API 名称和心智模型更干净
- `sheetbook` 运行时不再被“CSV 是默认内部模型”绑住
- 后续若再出现新的 internal artifact,不需要继续扩大 union 分支

### 4. `sheetbook` plan 保留 typed rows,header metadata 仍留在结果侧

在 header 纯化 change 的基础上,`sheetbook` 需要同时满足两条约束:

- 内部字段键空间继续只认 canonical field key
- 内部 row 值域升级为 `FieldValue`

也就是说,`sheetbook` plan 中:

- baseline header 仍然是 canonical field key 列表
- rows 从 `List[List[str]]` 升级为 `List[List[FieldValue]]`
- 结果侧 export header metadata 继续保存在 `sheetbook` plan 内部结构,不回流到内部键空间

这样可以把“键空间纯化”和“值域 typed 化”分开推进,同时保持与 `export_xlsx` 的结果侧语义兼容。

### 5. spreadsheet/export 转换只发生在最终 commit 边界

`xlsx_memory` 的最终 `.xlsx` 导出仍然存在,但这是结果侧能力,不应该反向污染内部语义。最终 commit/export 时:

- 仅在写 openpyxl workbook 的边界做 spreadsheet-friendly 转换
- 对 `str` 继续应用 formula escaping 规则
- 对 `int` / `bool` / `Decimal` / `float` / `None` 保持 typed cell value 语义,避免先统一 `str(...)`

这意味着:

- 内部 in-memory path 不再承担“为了最终 xlsx 导出而提前字符串化”的成本
- exact numeric values 可以一路保留到最终输出边界

### 6. `book_sheet_rows` 默认返回 typed rows,不引入 `typed` 开关

本 change 不做兼容式双语义:

- `book_sheet_rows` 默认行为直接升级为“canonical field key + preserved FieldValue values”
- 不新增 `typed: true` 参数
- 不保留“默认字符串,可选 typed”的长期双轨 API

原因:

- 仓库规则要求新需求/重构默认一步到位,除非用户明确要求兼容
- `xlsx_memory` 的定位已经是 workflow 内部数据容器,typed rows 是更合理的默认契约
- 长期保留双轨 API 会让测试、文档和用户心智都维持两套语义

### 7. 空值与数值边界采用“保真,不猜测”的规则

本次 change 明确以下边界:

- 如果上游实际值是 `None`,typed path 中必须保留 `None`
- 如果上游实际值是 `Decimal`,typed path 中必须保留 `Decimal`,不得隐式降级为 `float`
- 如果上游实际值是 `str("007")`,typed path 中必须保留该字符串,不得自动转成 `int`
- 如果上游实际值是 `float`,typed path 可以保留 `float`,但系统不得为了内部 in-memory 语义额外引入 `float`
- 对 legacy string artifact 中的 `\"\"`,本 change 不定义 `\"\" -> None` 猜测恢复; 若未来需要这项能力,应基于显式 null sentinel / field nullability 语义另开 change
- 本 change 不定义 `Decimal` 如何由 `compute/call_by` 产生; 它只要求“如果值已经是 `Decimal`,则 internal path 不得把它弄丢”

## Risks / Trade-offs

- [运行时改动面扩大] → 需要同时调整 execution result、workflow managed artifacts、sheetbook plan 与 export 边界
- [mixed consumer path 更复杂] → 同一 output 可能同时服务 typed consumer 与字符串 consumer; 缓解方式是以 typed artifact 为 SSOT,字符串 artifact按需派生,并显式建模 artifact kind
- [测试基线需要整体升级] → 现有依赖字符串 rows 的测试必须重写为 typed 断言
- [bridge 期间可能存在过渡实现] → 若分阶段落地,允许内部短期 bridge,但外部契约与 OpenSpec 必须以 typed 语义为准
- [空串/None 仍有边界] → 本次刻意不做猜测性恢复,避免把语义修复重新变成启发式 cast
- [Decimal 来源可能与其它 change 耦合] → 将“Decimal 如何被 produce”明确留给 `yaml-compute-decimal`,本 change 只做 preservation

## Migration Plan

1. 更新 OpenSpec,把 `xlsx_memory` 的用户契约和内部契约都改为 typed internal semantics
2. 扩展 execution / workflow artifacts,把 workflow-managed 从 `OutputSpec(format=csv)` 假设中解耦,并为 `xlsx_memory` 写节点引入按 output 粒度的 typed managed artifact
3. 引入统一的 tabular artifact 适配协议,重构 `sheetbook` plan 与 `book_sheet_rows` 读取链路,用 typed rows 替代字符串 rows
4. 将 `export_xlsx` 的字符串化/转义逻辑下沉到最终 commit 边界
5. 增加回归测试:
   - `int` / `Decimal` / `bool` 在 `book_sheet_rows` 中保持原类型
   - `str("007")` 保持字符串
   - `Decimal` 不被内部路径降级为 `float`
   - 不再需要 `_auto_cast` 风格的恢复逻辑
6. 运行 `just openspec-check` 与最小相关 pytest 子集验证

回滚策略:

- 若 typed artifact wiring 与并行 change 冲突,可以先保留 OpenSpec 工件并拆分实现提交
- 不接受将最终设计退回“长期字符串 rows + 用户自行恢复”的兼容方案

## Open Questions

- per-output typed managed artifact 是直接复用 `InMemoryRows`,还是抽出更贴近 output composition 的结构更合适
- tabular artifact 适配协议是否应作为独立内部模块沉淀,还是先以内聚 helper 形态落地
