# Evidence: ColumnExcelSink 列驻留 A/B

结果目录: `.tmp/evidence/column-excel-column-residency-ab/`（勿提交）

## 脚本

| Script | Purpose |
|---|---|
| `repro_column_residency_ab.py` | Fresh-process A/B: hold 全列至 close 结束 vs close 分块释放已写出行的列切片 |

## 命令

```bash
uv run python llmanspec/changes/c0-column-excel-sink-column-residency/evidence-mvp/repro_column_residency_ab.py --rows 30000 --cols 300 --chunk-rows 2000
```
