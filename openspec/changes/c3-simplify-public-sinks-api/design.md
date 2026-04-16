## Context

`scalim.sinks` 作为 Tier1 curated entrypoint，既要提供稳定 contracts（`ISink`/`IRowSink`/`IColumnSink` 等），也承载了大量内建 sinks（CSV/Excel/内存 sinks/可选依赖 sinks）。

当前问题集中在 “public surface 的分组与承诺不清晰”：

- `scalim.sinks` 顶层 `__all__` 同时暴露了 contracts + 常用 sinks + 可选依赖相关 sinks，用户难以判断推荐路径。
- “捕获结果以二次处理”在用户侧呈现为多种形态（RowData 列表 vs typed `InMemoryRows`），导致后续能力（DSL capture、workflow intermediate store）难以对齐。

同时，治理约束要求：

- public surface 必须通过 `__all__` 显式固定，且变更要可审计（`public-api-manifest`）。
- internal 目录必须封口 `__all__ = ()`（`public-api-surface-governance`）。

## Goals / Non-Goals

**Goals:**

- 将 sinks public surface 按职责重新分组，并提供清晰稳定的导入路径：
  - `scalim.sinks`：contracts + 常用 sinks（默认推荐）
  - `scalim.sinks.rows`：typed rows artifact（`InMemoryRows`）稳定入口（已存在）
  - `scalim.sinks.pandas`：pandas 相关 sinks（显式可选依赖边界）
  - `scalim.sinks.memory`：调试/测试/捕获用途的内存 sinks（显式语义边界）
- 统一推荐的“捕获 rows 工件”形态为 `InMemoryRows`：
  - 明确字段顺序、值域与转换/适配入口
  - 避免把 “sink 是否有 get_data/to_dataframe” 当作不稳定接口来依赖
- public API catalog/docs 与用户材料（tests/notebooks/docs）一次性升级（不做兼容层）。

**Non-Goals:**

- 不改变 sinks 的底层写出语义（CSV/Excel 的输出行为不在本 change 调整范围内）。
- 不新增新的输出格式（Parquet/Arrow 等不在本 change）。
- 不在本 change 内重做 workflow 的中间态协议（仅对齐稳定导入路径与推荐形态）。

## Decisions

### Decision 1: 顶层 `scalim.sinks` 只承诺 “默认推荐集合”

定义：

- “默认推荐集合”应满足：无额外可选依赖、可被大多数用户直接使用、且长期兼容压力可控。

因此：

- pandas sinks 不再出现在 `scalim.sinks.__all__`（改为 `scalim.sinks.pandas`）。
- debug/test 取向的内存 sinks 不再与 contracts 平铺混在顶层（改为 `scalim.sinks.memory`）。

备选方案：

- 继续把所有 sinks 暴露在顶层并靠文档解释 → 无法形成可 gate 的边界，且用户材料更容易误用。

### Decision 2: 为可选依赖 sinks 提供显式稳定入口 `scalim.sinks.pandas`

原因：

- 可选依赖存在时，功能可用；不存在时必须给出清晰错误提示（`sinks-contracts` 已要求）。
- 把它们从顶层移出能避免用户误以为 “安装框架即包含 pandas 能力”。

### Decision 3: `InMemoryRows` 作为对外推荐的 rows 工件 SSOT

原因：

- `InMemoryRows` 是 typed rows（字段顺序/值域更严格），更适合做 framework 级的稳定工件。
- 与 execution 的 `capture_in_memory_rows` 和 workflow 的 intermediate store 更自然对齐。

落地策略：

- `scalim.sinks.rows` 继续作为稳定入口，并在 docs/示例中作为 “capture rows” 的首选返回类型。
- 若仍保留 “RowData 列表” 形式的 sink，必须被明确标注为调试/测试用途，而非框架承诺的稳定工件。

## Risks / Trade-offs

- [风险] Breaking：大量导入路径变更 → [缓解] 一次性升级全仓（tests/notebooks/docs），不做兼容层；用 public API suite + catalog 漂移门禁兜底。
- [风险] 增加模块数导致用户选择困难 → [缓解] 顶层只保留默认推荐集合；其余能力通过显式子模块表达语义边界。
- [风险] `InMemoryRows` 更严格可能暴露边界问题 → [缓解] 严格是治理目标；必要时在转换/适配层提供明确错误信息与迁移指引。

## Migration Plan

1. 新增/调整模块：
   - `scalim.sinks.pandas`（稳定入口，显式可选依赖）
   - `scalim.sinks.memory`（稳定入口，debug/test/capture sinks）
2. 收敛 `scalim.sinks.__all__` 到默认推荐集合，并更新 Tier1 curated entrypoints（必要时新增 marker）。
3. 更新 docs/skills/notebooks/tests 的导入路径与示例，优先使用 `InMemoryRows` 表达 capture 语义。
4. 跑门禁：`just qa`、`just openspec-check`。

## Open Questions

- `InMemoryRowSink` 是否应保留为 `scalim.sinks.memory.InMemoryRowSink`（更清晰），还是重命名为更语义化的名字（例如 `InMemoryRowDataSink`）。
