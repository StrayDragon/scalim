# Design: StreamingColumnExcelSink multi-batch `set_row_ids`

## 约束

- `write_only` 只能按行序 `append`；行未齐备则 `_flush_ready_prefix` 停在缺口
- pipeline 每 batch 写满全部列后再开下一批 → 前缀齐备即可刷盘

## 语义

```
set_row_ids(batch1)  # 首次：开 workbook + header；分配 batch1 缓冲
write all columns for batch1 → flush batch1 rows
set_row_ids(batch2)  # 追加 row_ids + 缓冲；不重建 workbook
write all columns for batch2 → flush batch2 rows
close()
```

## 决策

| 点 | 选择 |
|---|---|
| 重复 pk | fail-fast `RuntimeError` |
| 空序列 | no-op |
| 已 close | fail-fast |
| pipeline 接线 | **本 change 不做**（follow-up） |

## 为何不做 on_source_complete

按列 flush 与 `write_only` 整行 append 冲突；多 batch 行窗已覆盖真实 peak 路径。
