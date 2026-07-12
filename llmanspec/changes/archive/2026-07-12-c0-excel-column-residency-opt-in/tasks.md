# Tasks: excel-column-residency-opt-in

## 1. Types + wiring

- [x] 1.1 新增 `ExcelColumnResidency`（`StrEnum`；`HOLD`/`WINDOW`）；确定稳定导入路径并导出
- [x] 1.2 `DemandRunRuntimeOptions.excel_column_residency`（默认 HOLD；严格 Enum）
- [x] 1.3 `ExecutionRequest.excel_column_residency`；compile/`run`/`run_ir` 透传
- [x] 1.4 `_create_file_sink`：excel + not streaming 按 residency 选 sink
- [x] 1.5 composition 存在且 WINDOW → fail-fast

## 2. Tests / docs / skills

- [x] 2.1 HOLD 默认仍为 `ColumnExcelSink`
- [x] 2.2 WINDOW + 列式 IR 使用 `StreamingColumnExcelSink`
- [x] 2.3 WINDOW + output_composition fail-fast
- [x] 2.4 更新 `streaming-column-excel-guidance.md` / public-api 短文（对齐本 change）
- [x] 2.5 futures R2 residual → 本 change / 归档后路径

## 3. Validate

- [x] 3.1 `llman sdd validate c0-excel-column-residency-opt-in --strict --no-interactive`
- [x] 3.2 `just qa`（或等效子集）
