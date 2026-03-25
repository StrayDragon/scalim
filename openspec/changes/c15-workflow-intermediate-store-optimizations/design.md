## Context

`workflow-intermediate-store` 的 v1 已落地 workflow-managed pathless CSV 的内存中间态 `InMemoryCsv`，并形成一条清晰的分层边界：

- execution/output composition 负责把 pathless CSV 物化为内存 sink，并通过 `ExecutionResult.in_memory_csv_outputs` 暴露给上层（`src/scalim/execution/output_composition.py`、`src/scalim/execution/run_ir.py`）。
- workflow runtime 负责发布/可见性检查/消费者释放（`src/scalim/workflow/execute.py::WorkflowArtifactsDirectory` + “最终消费者后释放”计数逻辑）。

但 workflow 与 demand 之间仍存在两个关键缺口，使得“非 CSV 的纯 Python 数据流”和“typed 中间态”无法成立：

1) **缺少稳定的 typed 中间态契约**  
当前 `InMemoryCsv` 是字符串化 CSV 语义（`src/scalim/sinks/sink_csv.py::InMemoryCsv`）。下游若要保留 `FieldValue` 类型（`Decimal/bool/int/...`）只能自行 parse 字符串，无法复用框架的类型语义。

2) **workflow 无法把上游数据作为下游 demand 的 main source**  
尽管 `ScalimEngine.run(main_rows=...)` 已支持注入主行流（`src/scalim/execution/engine.py`），但 `run_ir` 目前未透传该参数（`src/scalim/execution/run_ir.py` 只调用 `engine.run(sink=...)`）。workflow 也没有对应的 YAML authoring surface / IR 字段来声明“下游 run 的 main_rows 来自上游 run 的中间态”。

约束与护栏：

- `src/scalim/` 运行时必须兼容 Python 3.6。
- 文档治理：任何 `.gen.` 文件禁止手改；需要修改生成物时以 SSOT 为准并运行 `just gen-docs`/`just qa`。
- OpenSpec 校验：共享前必须 `just openspec-check`；本 change 的 drift gate 以 `just qa` 为兜底。

本设计假设以下能力已在本 change 之前合入且可作为基座：

- workflow runtime 的 SSOT 在 `src/scalim/workflow/*`（已完成 layering/refactor）。
- workflow-managed pathless CSV 的 `InMemoryCsv`、`ExecutionResult.in_memory_csv_outputs`、以及 workflow artifacts 发布/释放逻辑已存在。
- workflow-scope 的 `workflow-cache-pool` 已实现并用于 `preload_forever` 的跨 node 复用（本 change 不与其职责重叠）。

## Goals / Non-Goals

**Goals:**

- 引入稳定 typed 中间态 `InMemoryRows`（值域为 `FieldValue`），并保证与 `InMemoryCsv` 契约互不耦合。
- workflow runtime 支持显式声明/显式授权（allowlist）的 “`InMemoryRows` → 下游 demand `main_rows`” wiring，形成 workflow 内部的纯 Python 数据流（source 传递）。
- 明确 typed artifact 的发布/可见性/生命周期边界：支持多个 consumer 并发读取，并在“最后一个 consumer 结束后”释放。
- 收敛文档/生成边界与 drift gate：哪些文件手写、哪些生成、用什么命令生成/校验。

**Non-Goals:**

- 不在本 change 引入内存预算、spill-to-disk/tmpfs、LRU、OOM 防护（后续单独建模）。
- 不在本 change 引入非 rows 的 columnar/自定义格式（parquet/arrow/sqlite 等）。
- 不改变 demand YAML 的既有 authoring surface（本 change 仅扩展 workflow YAML；standalone demand 规则不放宽）。
- 不在本 change 让 write nodes 直接消费 `InMemoryRows`（先打通 dataflow/main_rows；typed 写入作为后续增量切片）。

## Decisions

### 1) `InMemoryRows` 作为独立 typed artifact（不与 `InMemoryCsv` 绑定）

- 新增 `InMemoryRows`（稳定表结构）：
  - `header: list[str]`：以 **field_id** 作为 SSOT（用于后续还原为 `RowData` 并作为 `main_rows` 注入）
  - `rows: list[list[FieldValue]]`：每行长度 MUST 与 `header` 等长
- 新增显式转换工具 `InMemoryRows -> InMemoryCsv`（不自动生成、调用侧显式请求），并复用 `CSVSink` 的值规范化语义。

> 备注：选择 `field_id` 作为 header，而不是 display header_names，是为了保证 `main_rows` 注入后下游字段解析仍以框架内部字段键为准；用户可见 header_names 仍由输出层处理。

### 2) `run_ir` 透传 `main_rows`，并提供可选的 `InMemoryRows` 捕获通道

- 扩展 `ExecutionRequest`：
  - `main_rows: Optional[Iterable[RowData]]`：用于注入主数据行流（workflow dataflow 的承载点）
  - `capture_in_memory_rows: bool = False`：当且仅当 workflow 需要 publish typed rows 时启用
- 修改 `run_ir`：调用 `engine.run(main_rows=request.main_rows, sink=...)`，并在 `capture_in_memory_rows` 启用时将输出行流 tee 到 `InMemoryRowsSink`，最终回填到 `ExecutionResult.in_memory_rows`。

### 3) workflow YAML/IR 增量：`workflow.runs[*].main_rows_from`

新增 workflow YAML authoring surface（显式声明/显式授权）：

- `workflow.runs[*].main_rows_from`：mapping，至少包含：
  - `run`: 上游 run_id（producer）
- 约束：
  - consumer run MUST `depends_on` producer run（保证执行顺序 + 可见性边界显式化）
  - producer run MUST 被至少一个 consumer 引用时才会启用 `capture_in_memory_rows`（避免无意间常驻大对象）

对应 IR：

- 扩展 `WorkflowNodeIr`，增加 `main_rows_from_run_id: Optional[str]`（artifact_id 固定为 `in_memory_rows`，后续如需泛化再增量扩展）。

### 4) 生命周期与释放：参照 workflow-managed CSV 的“最终 consumer 释放”

- workflow 在编译/准备阶段推导 `producer_run_id -> remaining_main_rows_consumers` 的计数上界。
- demand 节点成功完成且启用了捕获时，workflow artifacts 发布 `in_memory_rows`。
- 每个 consumer demand 节点结束（done/failed/cancelled 均视为不再消费）后递减计数；计数归零时丢弃 producer 的 `in_memory_rows` artifact。
- workflow 失败/取消时，统一丢弃未释放的 `in_memory_rows` artifacts（与 `in_memory_csv_outputs` 的失败清理策略对齐）。

### 5) 文档/生成边界与 drift gate（SSOT）

- 手写（SSOT）：`openspec/changes/c15-workflow-intermediate-store-optimizations/{proposal,design,tasks}.md`、本 change 下的 delta specs。
- 生成物：`src/scalim/dsl/by_yaml/schema/*.gen.json`、`docs/doc/**/*.gen.md`、以及任何 `<!-- BEGIN AUTOGEN:... -->` 注入区块（禁止手改）。
- 生成入口：
  - schema：`just gen-yaml-dsl-schema` / `just qa`（drift gate）
  - 文档：`just gen-docs`
- 校验入口：`just openspec-check`、`just qa`

## Risks / Trade-offs

- [内存峰值上升] 捕获 typed rows 会把数据常驻到 workflow 级别，且本 change 不做预算/spill → 通过显式 allowlist + “最后 consumer 释放”降低常驻时长；预算/spill 留给后续 change。
- [并发消费与可变对象] 多个 consumer 可能并发读取同一份 `InMemoryRows` → `InMemoryRows` 设计为只读数据结构；consumer 侧每次生成独立迭代器，避免 generator 被多次消费。
- [公共 API 牵连] `ExecutionRequest/ExecutionResult` 增量字段会扩展 API surface → 均为可选字段且默认关闭；需补充测试覆盖并通过 `just qa` 的 public-surface 门禁。
- [YAML authoring 扩面] workflow YAML 增加新字段会引入学习成本 → 保持可选、明确校验报错路径，并提供最小示例与迁移说明（后续补齐 docs）。

## Migration Plan

- 现有 workflow YAML 不需要迁移；不使用 `main_rows_from` 时无行为变化。
- 新增能力仅在 workflow YAML 显式声明时启用；standalone demand 不受影响。
- 若需要回滚，只需禁用/移除 `main_rows_from` 配置并关闭捕获，不影响其它 workflow 能力。

## Open Questions

- `InMemoryRows.header` 是否需要支持 “field_id 与 display header_names” 双轨（例如增加可选 metadata），以便后续 typed 写入 workbook 时保留用户可见表头？
- typed rows 是否需要携带 `row_id` 语义（作为显式列还是独立字段），以支持更强的 join/lookup 场景？
- 对超大 rows 的护栏策略：是否需要在 workflow options 中增加上限（max_rows/max_bytes）作为 fail-fast 预防？
