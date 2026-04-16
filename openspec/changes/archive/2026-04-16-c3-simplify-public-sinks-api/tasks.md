## 1. Sinks Facade Restructure (Tier1 Boundaries)

- [x] 1.1 引入稳定子模块 `scalim.sinks.memory` 与 `scalim.sinks.pandas`（作为 facade：显式 `__all__` 白名单导出；内部实现仍在 `scalim.sinks._internal.*`），并为其补齐 Tier1 markers（验收：`from scalim.sinks.memory import InMemoryRowDataSink` 与 `from scalim.sinks.pandas import PandasRowSink` 可导入）。
- [x] 1.2 收敛 `scalim.sinks` 顶层 `__all__` 到 “contracts + 常用 sinks”（移除内存 sinks 与 pandas sinks 的默认导出；移除 Tier1 entrypoint `scalim.sinks.rows`），并更新 marker 描述与顺序（验收：`from scalim.sinks import PandasRowSink` 失败；Tier1 表格不再包含 `scalim.sinks.rows`）。

## 2. Unify Capture Rows Shape (`List[RowData]`)

- [x] 2.1 将 “RowData 列表” 内存 sink 重命名为 `InMemoryRowDataSink` 并固定 `get_data() -> List[RowData]`（breaking：不保留旧别名；验收：类型/语义与 design 对齐，调用侧可以最短路径拿到 `List[RowData]`）。
- [x] 2.2 typed rows（`InMemoryRows`/`InMemoryRowsSink`）若仍需保留，仅作为 internal 实现存在；不得进入 curated public surface 与用户材料（验收：docs/示例不再出现 `InMemoryRows*` 作为推荐导入）。

## 3. Optional Dependency Boundary for Pandas Sinks

- [x] 3.1 满足 spec 场景：默认入口 `scalim.sinks` 不直接导出 pandas sinks；显式子模块 `scalim.sinks.pandas` 承载（验收：新增/更新测试断言 `from scalim.sinks import PandasRowSink` 失败但 `from scalim.sinks.pandas import PandasRowSink` 成功）。
- [x] 3.2 保持可选依赖错误提示清晰（验收：缺少 pandas 时，调用需要 pandas 的能力会抛出 `ImportError` 且包含可读提示）。

## 4. Migrate Call Sites (Docs / Notebooks / Tests)

- [x] 4.1 迁移全仓导入路径与示例：`InMemoryRowSink` → `InMemoryRowDataSink`，并按新分组改为从 `scalim.sinks.memory`/`scalim.sinks.pandas` 导入（验收：README、docs、notebooks、tests 全绿；用户材料不引用 `scalim.sinks._internal.*`）。
- [x] 4.2 刷新 public API 文档与生成物（验收：不手改任何 `*.gen.*` 与 injected blocks；运行 `just gen-docs` 后无 drift，且 Tier1 表格/exports 列表反映新的 sinks 分组）。
  - SSOT：`src/scalim/sinks/**` 的字面量 `__all__` + Tier1 markers
  - 生成入口：`just gen-docs`

## 5. QA / Drift Gates

- [x] 5.1 OpenSpec 校验（验收：`just openspec-check` 通过；包含 sanitize + validate）。
- [x] 5.2 Repo 质量门禁（验收：`just qa` 通过，包含 lint/tests + drift checks）。
