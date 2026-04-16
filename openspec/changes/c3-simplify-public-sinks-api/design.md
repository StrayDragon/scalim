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
  - `scalim.sinks.pandas`：pandas 相关 sinks（显式可选依赖边界）
  - `scalim.sinks.memory`：调试/测试/捕获用途的内存 sinks（显式语义边界）
- 统一推荐的“捕获 rows 工件”形态为 `List[RowData]`（通过 `InMemoryRowDataSink`）：
  - 避免在 public surface 中同时暴露 `RowData list` 与 `typed rows` 两套近似概念
  - 让调试/测试/二次处理的最短路径保持简单（拿到 `List[RowData]` 就能用）
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

### Decision 3: `List[RowData]`（`InMemoryRowDataSink.get_data()`）作为对外推荐的 capture rows SSOT

原因：

- public surface 的目标是“少概念 + 易上手”；同时存在 `InMemoryRowSink`（RowData list）与 `InMemoryRows*`（typed rows）会造成理解与维护负担。
- `RowData` 本身已是 sinks contracts 的核心数据结构；对外直接用 `List[RowData]` 是最直接、最一致的契约。

落地策略：

- `scalim.sinks.memory.InMemoryRowDataSink` 提供稳定的 `get_data() -> List[RowData]`，作为调试/测试/捕获 rows 的唯一推荐路径。
- `typed rows`（例如现有的 `InMemoryRows`）若仍对 workflow 内部有价值，应留在 internal 实现层（不进入 curated public surface，不在 docs/示例中出现）。

### Decision 4: `RowData` 列表 sink 采用更明确的命名 `InMemoryRowDataSink`

背景：

- 当前同时存在 `InMemoryRowSink`（存 `List[RowData]`）与 `InMemoryRowsSink`（产出 typed `InMemoryRows`）两套“看起来很像”的内存 sink。
- 当前还存在 `scalim.sinks.rows` 这类 typed rows facade（按本 change 将移出 Tier1）；即使它们位于不同入口，`Row` vs `Rows` 的差异仍不足以避免误解与误用。

结论：

- 将 “RowData 列表” 形态的内存 sink 命名为 **`InMemoryRowDataSink`**（对齐 `RowData` 类型别名，语义清晰、维护成本更低）。
- 不再在 public surface 中保留 `InMemoryRows` / `InMemoryRowsSink` 这套 typed rows 概念（若需要仅内部保留）。
- 不保留旧别名（breaking change 可接受），实现阶段将全仓一次性升级。

## Public Surface Diffs

以 “Tier1 curated entrypoint = `scalim.sinks`” 为基准，预期对外变化为：

- **新增（Tier1）**：
  - `scalim.sinks.memory`（内存 sinks：debug/test/capture 语义边界）
  - `scalim.sinks.pandas`（pandas sinks：显式可选依赖边界）
- **移除 / 下沉（从 `scalim.sinks` 顶层）**：
  - pandas sinks 从 `scalim.sinks.__all__` 移除，改为 `scalim.sinks.pandas.*`
  - 内存 sinks 从 `scalim.sinks.__all__` 移除，改为 `scalim.sinks.memory.*`
- **移除（从 Tier1 curated surface）**：
  - `scalim.sinks.rows`（typed rows entrypoint，不再对外承诺；内部如需可保留实现）
- **更新**：
  - `InMemoryRowSink` → `InMemoryRowDataSink`（作为 `scalim.sinks.memory` 的稳定导出名；不再引入第二套“typed rows” public 类型）

## Risks / Trade-offs

- [风险] Breaking：大量导入路径变更 → [缓解] 一次性升级全仓（tests/notebooks/docs），不做兼容层；用 public API suite + catalog 漂移门禁兜底。
- [风险] 增加模块数导致用户选择困难 → [缓解] 顶层只保留默认推荐集合；其余能力通过显式子模块表达语义边界。
- [风险] 移除 typed rows 的对外入口会影响依赖方 → [缓解] 不做兼容层，一次性升级调用点；typed rows 若仍需要仅内部保留，或后续以独立 change 重新引入（需有明确 SSOT 与门禁）。

## Migration Plan

1. 新增/调整模块：
   - `scalim.sinks.pandas`（稳定入口，显式可选依赖）
   - `scalim.sinks.memory`（稳定入口，debug/test/capture sinks）
2. 收敛 `scalim.sinks.__all__` 到默认推荐集合，并更新 Tier1 curated entrypoints（必要时新增 marker）。
3. 更新 docs/skills/notebooks/tests 的导入路径与示例，优先使用 `InMemoryRowDataSink`（`get_data()`）表达 capture 语义。
4. 跑门禁：`just qa`、`just openspec-check`。
