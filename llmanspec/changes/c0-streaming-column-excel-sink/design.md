# Design: StreamingColumnExcelSink（收窄 MVP）

## 背景证据

| 阶段 | 结论 |
|---|---|
| write_only | close workbook 峰大幅下降 |
| mid-close 列切片释放 | peak 不降（`peak≈pre_close`） |
| 本 change | 必须在 **写入过程中** 释放，才能动 `pre_close` |

## 方案对比

| 方案 | 说明 | 本 change |
|---|---|---|
| A 改默认 `ColumnExcelSink` | 风险高 | **否** |
| B mid-close flush | 已证无 peak ROI | **否** |
| C 新 opt-in sink | 默认不变；可证据驱动 | **是** |

## 已固定：证据 MVP（本轮只做这个）

> **不写入 `src/scalim/` 生产代码。** 验证实现放在 `evidence-mvp/repro_streaming_ab.py`。

### 为何不能「按列写满再 flush」

若每次 `write_column` 写入**全部行**的一列，则任一行使字段齐备都要等到**最后一列**到达 → 峰值仍是 O(rows×cols)。  
因此证据臂必须用**行窗（row window）**写出模式，才能在过程中释放缓冲。

### MVP 语义（证据内 `MvpStreamingColumnExcel`）

1. `set_row_ids` 后打开 `Workbook(write_only=True)` + `create_sheet`（表头可立即写）
2. `write_column(field, values)`：按 `row_ids` 填入行缓冲；当某行 `field_names` 全集齐备 → `ws.append` 该行并释放该行缓冲
3. `close()`：断言无残留未齐备行（或 fail-fast）；原子 `save` + 清理（复用 `openpyxl_helpers` / atomic paths）
4. **A/B 写出模式**:
   - **hold**: 一次性构建全列 → `ColumnExcelSink` → `close`
   - **streaming_window**: 按 `window_rows` 切窗；每窗写入全部列（仅该窗 `row_id`）→ 窗内行齐备即刷盘释放 → 下一窗
5. **对拍**: 小 shape 全表单元格相等；大 shape fresh-process 比 `peak` / 过程最大 RSS

### 成功门槛（证据）

- 正确性：`ok=true`
- 效果：同 shape 下 streaming 的 `peak_rss_gb_observed` **明显低于** hold（经验阈值：≥20% 或绝对值差 ≥0.2GB，以 result.json 为准记录）

## 生产落地（后续 apply，非本轮）

1. 将证据 MVP 迁入 `StreamingColumnExcelSink`（opt-in）
2. API 对齐 `ColumnExcelSink` + 显式行窗/flush 文档
3. **MUST NOT**: YAML；改默认 `ColumnExcelSink`

## Follow-up

- execution 自动按 source 完成触发 flush
- 更细的 pending 字段集合优化
