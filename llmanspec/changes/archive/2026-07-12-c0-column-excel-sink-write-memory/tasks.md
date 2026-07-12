# Tasks: column-excel-sink-write-memory

## 0. 证据与设计

- [x] 0.1 宽表爬坡 / memray / write_only A/B（见 `.tmp/evidence/` 与 `design.md`）
- [x] 0.2 收敛最小改动为 write_only close

## 1. 实现

- [x] 1.1 `ColumnExcelSink.close` → `Workbook(write_only=True)` + `create_sheet`
- [x] 1.2 异常路径 best-effort close write_only worksheets
- [x] 1.3 更新 sinks 回归测试夹具

## 2. 规范与验收

- [x] 2.1 delta `output-sink-contracts`（r9）
- [x] 2.2 `llman sdd validate c0-column-excel-sink-write-memory --strict --no-interactive`
- [x] 2.3 `uv run pytest tests/sinks/ -q`

## 后续（非本 change 阻塞项）

- `just qa` / archive：用户确认后再做
