# Design: ColumnExcelSink 列驻留（已取证）

## 证据（2026-07-12，30k×300，fresh process）

脚本: `evidence-mvp/repro_column_residency_ab.py`  
结果: `.tmp/evidence/column-excel-column-residency-ab/20260712T100525Z/result.json`

| arm | pre_close RSS | peak RSS | post_close RSS | close_s | 正确性 |
|---|---:|---:|---:|---:|---|
| hold（现状） | 0.658GB | 0.681GB | 0.681GB | 48.5 | — |
| chunk_release（close 分块释放列切片） | 0.658GB | 0.681GB | 0.416GB | 49.6 | 小 shape 对拍 OK |

要点:

- **peak ≈ pre_close**：close 阶段几乎不再抬峰；列 dict 与 write_only 双驻留对 peak 的增量可忽略。
- chunk_release 只降低 **post_close** RSS，对观测 peak 无收益，close 略慢。
- 因此 **B（同类型 flush+释放）对 peak ROI ≈ 0**；真正要砍 pre_close 需更早流式写出（C），成本高且另案。

## 定案

**选 A**：不改 `ColumnExcelSink` 运行时默认行为；在 sink 契约/文档中明确：

- 调用方在 `write_column` 后可丢弃**源列**；
- sink **仍持有副本**直至 `close()` 完成；
- 不引入 YAML streaming knobs；不新增默认路径的 flush API。

## 非目标（本 change）

- `StreamingColumnExcelSink`（C）实现
- shared-book spill / YAML knobs
- 默认路径破坏 discard 原子性
