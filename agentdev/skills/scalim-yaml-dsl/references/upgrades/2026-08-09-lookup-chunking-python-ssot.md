# 2026-08-09 — YAML `lookup_chunk_size` → Python `LookupChunking`（c40）

## Breaking

`sources.*.lookup_chunk_size` 已从 YAML authoring 迁出。继续写该字段会 **fail-fast**，并提示改用：

```python
from scalim.dsl.yaml_dsl import (
    DemandRunOptions,
    DemandRunRuntimeOptions,
    LookupChunking,
    compile,  # 或 run
)

options = DemandRunOptions(
    security=...,
    runtime=DemandRunRuntimeOptions(
        lookup_chunking={
            "customers": LookupChunking.sized(800),                 # 串行分片
            # "customers": LookupChunking.sized(800, parallel=True),  # 片间并行（须 parallel_mode=adaptive）
            # "customers": LookupChunking.off(),
        },
        # 推荐：并行挂在 sized 上。旧 parallelize_lookup_chunks 仅在未经 LookupChunking
        # 写入 per-source parallel 标志的 IR 路径仍可继承；已用 sized(...) 时请写 parallel=True。
        parallel_mode="adaptive",
    ),
)
```

## 相关覆盖（非 breaking）

- `SourceCache` / `RowsReuse`：YAML `cache_mode` / `$rows.cache_mode` **可保留**；Python 显式覆盖优先（`DemandRunRuntimeOptions.source_cache` / `rows_reuse`）。
- `RunOverrides.csv_file` / `xlsx_file_single_sheet`：`header_fields_output_by` 工厂默认从 `field_id` 改为 **`name`**（与 YAML 省略一致）。若依赖旧工厂默认，请显式传 `header_fields_output_by="field_id"`。

## 指针

- 何时用 / Observer·Hook 自证：`references/lookup-chunking-guidance.md`
- 可运行 oracle：`notebooks/marimo/example_public_api_suite/chapters/ch164_public_api_lookup_chunking.py`（pytest 主线 `ch164`）
- Design：`llmanspec/changes/c40-yaml-runtime-policy-boundary/design.md`
- Spec：`llmanspec/specs/yaml-dsl-runtime-policy-boundary`（r1003/r1004/r1005）
