# Proposal: column-excel-sink-column-residency

## Why

已归档 `c0-column-excel-sink-write-memory` 用 `Workbook(write_only=True)` 砍掉 close 阶段 workbook 峰：

| shape | 改前 peak | 改后 peak |
|---|---:|---:|
| 100k×300 | ~9GB | ~2.4GB |
| 300k×300 | ~26.5GB | ~5.7GB |

残留瓶颈：**列 dict（`_columns`）仍驻留到 `close()` 结束**。memray（20k×300）显示 close/append 曾占分配主导；write_only 后 pre_close RSS 仍随 cells 近似线性（100k→~2.4GB 已接近列缓存本身）。

notplan `c1-streaming-xlsx-output` 过大且倾向 YAML knobs；本 change **收窄**为 Python sink 内部契约，禁止 YAML 回流。

## What Changes

1. **证据**: `evidence-mvp/` hold vs close 分块释放列切片 A/B（30k×300：peak 无收益）
2. **定案 A**: 仅文档化列驻留契约；**不**落地 B/C 运行时变更
3. **MUST NOT**: YAML `write.streaming` / books knobs；新三方写库；默认路径隐式 flush

## Capabilities

### Modified Capabilities

- `output-sink-contracts` — ColumnExcelSink 列驻留文档契约

## Impact

- **破坏性**: 无（仅文档/规范）
- **证据**: `.tmp/evidence/column-excel-column-residency-ab/` + change 内 `evidence-mvp/`
- **关联**: notplan `c1-streaming-xlsx-output`（C 仍 later）

## Ethics

- `ethics.risk_level`: low（本 change 锁定为文档-only）
- `ethics.prohibited_actions`: 不默认破坏原子写出；不引入 YAML streaming knobs

## 进度

- [x] design 收敛 A/B/C → **A**
- [x] evidence-mvp A/B
- [x] delta specs + tasks（骨架）
- [ ] apply 文档 + validate / qa / archive
