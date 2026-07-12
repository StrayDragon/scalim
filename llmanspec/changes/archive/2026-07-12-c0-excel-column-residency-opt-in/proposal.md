# Proposal: excel-column-residency-opt-in

## Why

`StreamingColumnExcelSink` + 多 batch `set_row_ids` 已落地，证据显示相对 `ColumnExcelSink` hold 可大幅砍峰（100k×300 ≈97%）。  
调用方今日只能手写构造 sink；框架 IR 工厂 `_create_file_sink` 在 `excel` + `streaming=False` 时仍固定 `ColumnExcelSink`。

产品目标（已定）：**IR/Python 列式路径**提供显式 opt-in，默认不变。  
**不是**让 YAML books 自动获得列式 WINDOW（组合层仍是 `ROW_STREAMING`）。

## What Changes

1. 新增闭集 `StrEnum`：`ExcelColumnResidency` = `HOLD` | `WINDOW`（Python SSOT；严格 Enum in）
2. 挂载：
   - `DemandRunRuntimeOptions.excel_column_residency`（默认 `HOLD`）
   - `ExecutionRequest.excel_column_residency`（默认 `HOLD`；由 compile/`run` 透传）
3. `_create_file_sink`：`format=excel` 且 `streaming=False` 时按 residency 选择
   - `HOLD` → `ColumnExcelSink`（现状）
   - `WINDOW` → `StreamingColumnExcelSink`
4. 若存在 `output_composition`（YAML books 行组合）且 residency=`WINDOW` → **fail-fast**（禁止假开关）
5. **MUST NOT**：YAML knobs；改默认 `ColumnExcelSink`；改 `ResourcesPolicy`；shared-book 插 Streaming

## Capabilities

### Modified Capabilities

- `output-sink-contracts` — 列式 Excel residency 与工厂选择
- `yaml-dsl-runtime-policy-boundary` — residency 仅 Python；与 composition 冲突 fail-fast

## Impact

- **破坏性**: 无（默认 HOLD；仅显式 WINDOW 改行为）
- **用户口子**: Python 调用方在 `DemandRunOptions.runtime` / `ExecutionRequest` 显式选择
- **YAML**: 无 authoring 字段；误用 WINDOW + composition → 可诊断错误
- **ethics.risk_level**: low–medium
- **ethics.prohibited_actions**: 不引入 YAML streaming knobs；不静默忽略 WINDOW 于 YAML 路径
