# Future — c10-fix-duplicate-display-headers

本文件为候选待办池。审查以下条目并归类为 `now`/`later`/`drop`。

## Deferred Items

### later — sink `write_row_aligned`/`write_column_aligned` 重复键硬化

- 触发信号: 任何 sink 在非唯一键下出现末次覆盖式坍缩(`{key: i for ...}` 会保留末次出现索引)。
- 落地路径: 单独小提案; 受影响 capability `output-sink-contracts`。
- 来源: 本提案 `design.md` 关联潜在隐患;与本次根因同源(按可重复键建索引),当前因 field_id 唯一未触发。
- 备注: 源头修复后对齐永远在 field_id 上运行,该隐患的触发面进一步收窄;但 sink 层的 `{key: i}` 仍是脆弱点,建议后续一并硬化。

## Branch Options

- 方法 A(源头对齐统一)已在主变更落地;方法 B(仅 identity patch)已被取代为次要防御。

## Triggers to Reopen

- 用户反馈 `append` 乱序重复展示名仍错位(源头修复后应已消除,若复现需复查 export_header 透传链路)。
- `xlsx_file`/`csv` 中间工件 header 语义被改动时需复核对齐键是否仍为 field_id。
