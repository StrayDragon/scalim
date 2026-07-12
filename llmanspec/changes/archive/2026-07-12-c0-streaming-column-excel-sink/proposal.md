# Proposal: streaming-column-excel-sink

## Why

`ColumnExcelSink` 在 `write_only` 后，**peak ≈ pre_close**，瓶颈是列 dict 全量驻留到 `close()`。  
归档证据：

- `archive/2026-07-12-c0-column-excel-sink-write-memory`：close workbook 峰已砍
- `archive/2026-07-12-c0-column-excel-sink-column-residency`：mid-close 分块释放列切片 **不降 peak**（定案 A）

要砍 `pre_close`，必须在写出更早阶段释放缓冲；且不得破坏默认 sink。  
本 change 自 notplan `c1-streaming-xlsx-output` **收窄升格**：只做 Python opt-in sibling。

## What Changes

1. **新增** `StreamingColumnExcelSink`（`IColumnSink`），默认路径仍用 `ColumnExcelSink`
2. **MVP 语义（design 可收紧）**:
   - 固定 `row_ids` 后按列写入；当一行字段齐备时可刷入 `write_only` sheet 并释放该行缓冲
   - 显式 `flush()` / 完成列组 API（Python）；**禁止** YAML `write.streaming`
3. **证据**: `evidence-mvp/` 对拍 hold vs streaming 的 `pre_close`/`peak` RSS + 正确性
4. **非目标（本 change）**: YAML knobs；改默认 `ColumnExcelSink`；框架 execution 自动 flush 接线（可 follow-up）

## Capabilities

### Modified Capabilities

- `output-sink-contracts` — 新增 opt-in streaming column Excel sink 契约

## Impact

- **破坏性**: 无（新类型；旧类不变）
- **关联**: futures R2；notplan `c1-streaming-xlsx-output`（历史草案）
- **ethics.risk_level**: medium（错误释放 → 错行/丢列）
- **ethics.prohibited_actions**: 不引入 YAML streaming；不默认破坏原子 discard

## 证据进度（2026-07-12）

`evidence-mvp/repro_streaming_ab.py`（**不进生产代码**）：

### 20k×200 / window=2000

| arm | peak RSS | pre_close | 正确性 |
|---|---:|---:|---|
| hold | 0.348GB | 0.251GB | — |
| streaming_window | 0.259GB | 0.235GB | 小 shape 对拍 OK |

- `peak_reduction_ratio` ≈ **25.8%**；`gate_peak_reduced=true`

### 100k×300 / window=2000（复测）

| arm | peak RSS | pre_close | duration_s |
|---|---:|---:|---:|
| hold | **3.58GB** | 2.39GB | 159 |
| streaming_window | **1.11GB** | 1.06GB | 167 |

- 正确性：`ok=true`
- `peak_reduction_ratio` ≈ **69.0%**（Δpeak ≈ 2.47GB）；`gate_peak_reduced=true`
- 产物：`.tmp/evidence/streaming-column-excel-ab/20260712T104647Z/result.json`
- 结论：行窗 MVP **随 shape 放大收益更明显**；已 apply 迁入生产 `StreamingColumnExcelSink`
