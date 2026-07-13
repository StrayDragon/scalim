# MVP — 统一 `xlsx`（虚构）

| 文件 | 角色 |
|---|---|
| `before.workflow.yaml` | 今日双 kind：`xlsx_memory` 总线 + `xlsx_file` 落盘 |
| `after.workflow.yaml` | 统一 `xlsx`：无 path=总线，有 path=落盘 |
| `stage_*.demand.yaml` / `summary.demand.yaml` | **shape-only** 同构示意（非完整可跑 demand） |

可执行同构夹具：`tests/yaml_dsl/test_c20_unified_xlsx_book_kind.py`。

不对应任何外部业务仓。
