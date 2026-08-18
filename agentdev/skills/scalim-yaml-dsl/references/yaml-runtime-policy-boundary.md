# YAML vs Python runtime policy boundary（agent）

c40 已落地（0.10.*）：换环境就会改的配置收口 Python typed oneof；YAML 保留可移植编排与内容/资源身份。细则见 upgrade 卡与 design。

## 何时读取

- 用户问「这个旋钮该写 YAML 还是 Python」
- 涉及 keys 分片、`cache_mode`、或已迁出键回流
- 问「要不要设 LookupChunking / chunk 会不会更快」→ 改读 `references/lookup-chunking-guidance.md`
- 混淆 `sources.*.cache_mode` 与 `$rows.cache_mode`

## 三栏启发式（工作用）

| 栏 | 含义 | 例子 |
|----|------|------|
| **宜留在 YAML** | 换环境仍应相同的图、字段、loader 协议 | `runs`/deps、`fields`/`relations`、`params`（`$keys`/`$rows`）、资源 path；`sources.*.cache_mode` / `$rows.cache_mode`（可被 Python 覆盖） |
| **宜收口到 Python** | 换部署/配额/入口就会改 | 已迁出的 `batch_size`/`retry`/`guardrails`；**`Lookup_chunk_size` → `LookupChunking`**；片间并行嵌在 `sized(..., parallel=True)`；**写出布局 `OutputWriteLayout`**（`row_stream` / `column_buffered` / `column_chunked`） |
| **默认已钉死 + overrides** | 省略走 builtin；Python `RunOverrides` 可改 | `encoding`≡utf-8、`allow_formulas`≡true、`include_header`≡true、`header_fields_output_by`≡name |

禁止：回流 `budget`/`write_defaults`；静默忽略 YAML；新增 YAML 并行键。

## 易混钉死

| 写法 | 含义 | 不是 |
|------|------|------|
| ~~`sources.<id>.lookup_chunk_size`~~ | **已迁出** → `DemandRunRuntimeOptions.lookup_chunking` / `LookupChunking` | 再写 YAML 会 fail-fast |
| `LookupChunking.sized(size=N)` | keys 分片大小 |  alone 不是并行开关 |
| `LookupChunking.sized(..., parallel=True)` | 片间并行（须 `parallel_mode=adaptive`） | 不可挂在 `off()` 上 |
| `sources.<id>.cache_mode` | `none` / `preload_forever`（Python：`SourceCache`） | `$rows.cache_mode` |
| `$rows.cache_mode` | `batch` / `none`（Python：`RowsReuse`） | source 级 `cache_mode` |

覆盖优先级：**显式 Python > YAML > builtin**。

## 图边 vs 目录（c50）

- 存盘图：`FieldIr.source_id` / `LookupStepIr.to_source_id` 只存 `str`
- live `SourceIr`（含 `LookupChunking` / `SourceCache` / `RowsReuse` overlay）只住 `DemandIr.sources`
- 新 overlay 只 `replace()` 目录；**禁止**写进 `LookupStepIr` / `FieldIr`
- 作者态 `infer_lookup_path(..., to_source=活对象)` 仍合法；`DemandIr.from_irs` / YAML compile 出口 intern 成 id
- 指针：`references/upgrades/2026-08-18-source-id-graph-refs.md`；change `llmanspec/changes/c50-source-id-graph-refs/`

## 指针

- Upgrade：`references/upgrades/2026-08-09-lookup-chunking-python-ssot.md`
- 图边 vs 目录：`references/upgrades/2026-08-18-source-id-graph-refs.md`
- Design / evidence（归档后）：`llmanspec/changes/archive/*-c40-yaml-runtime-policy-boundary/`
- Live 合约：`llmanspec/specs/yaml-dsl-runtime-policy-boundary/`（r1003–r1005）
- 人类：`docs/doc/yaml-dsl/review-checklist.md`、`capability-matrix.md`、`user-guide.md` §4.4.3
- 何时用 / 事件自证：`references/lookup-chunking-guidance.md`
- 可运行 oracle：`notebooks/marimo/example_public_api_suite/chapters/ch164_public_api_lookup_chunking.py`
