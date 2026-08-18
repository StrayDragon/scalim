# 2026-08-18 — 图边存 `source_id`，策略只住目录（c50）

> 日期：2026-08-18  
> 相关 change：`c50-source-id-graph-refs`  
> YAML authoring **不变**；破坏面在手写 Python IR / 规划图。

## 一句话

存盘 `DemandIr` 的关联图只存 `FieldIr.source_id` / `LookupStepIr.to_source_id`（`str`）。live `SourceIr`（含 `LookupChunking` / `SourceCache` / `RowsReuse` overlay）只住 `DemandIr.sources`。缺 catalog id **fail-fast**，没有嵌套句柄回退。

## 何时读

- 手写 `LookupStepIr` / `FieldIr` 编译失败（`to_source=` / `source=` 已删除）
- overlay 后 lookup 仍像旧策略（把图边当 live 源）
- 问「新旋钮该挂 field 还是 source」——本 change **不**做 per-field overlay；只写 source 目录

## 迁移

| 旧 | 新 |
|----|----|
| `LookupStepIr(to_source=source)` | `LookupStepIr(to_source_id=source.source_id)` + `DemandIr.sources` / `ExecutionRuntime.sources` 放入同一对象 |
| `FieldIr(source=source)` | `FieldIr(source_id=source.source_id)` |
| `step.to_source.lookup_chunk_size` | `SourceIr.from_catalog(runtime.sources, step.to_source_id).lookup_chunk_size` |
| 空 catalog + 嵌套句柄 | **禁止**；单测必须组 `sources={id: source}` |

作者态 `RelationIr.infer_lookup_path(from_source=..., to_source=活 SourceIr)` 仍吃对象；`DemandIr.from_irs` / YAML compile 出口 intern 成 id。

## 指针

- Design / tasks：`llmanspec/changes/c50-source-id-graph-refs/`
- 边界卡：`references/yaml-runtime-policy-boundary.md`
- LookupChunking 自证：`references/lookup-chunking-guidance.md`；oracle `ch164_public_api_lookup_chunking`
- workflow 同名 `source_id` 隔离：`notebooks/marimo/example_public_api_suite/chapters/ch166_public_api_source_catalog_workflow.py`
