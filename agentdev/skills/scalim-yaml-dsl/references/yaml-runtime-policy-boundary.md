# YAML vs Python runtime policy boundary（agent）

c40 已落地（0.10.*）：换环境就会改的配置收口 Python typed oneof；YAML 保留可移植编排与内容/资源身份。细则见 upgrade 卡与 design。

## 何时读取

- 用户问「这个旋钮该写 YAML 还是 Python」
- 涉及 keys 分片、`cache_mode`、或已迁出键回流
- 混淆 `sources.*.cache_mode` 与 `$rows.cache_mode`

## 三栏启发式（工作用）

| 栏 | 含义 | 例子 |
|----|------|------|
| **宜留在 YAML** | 换环境仍应相同的图、字段、loader 协议 | `runs`/deps、`fields`/`relations`、`params`（`$keys`/`$rows`）、资源 path；`sources.*.cache_mode` / `$rows.cache_mode`（可被 Python 覆盖） |
| **宜收口到 Python** | 换部署/配额/入口就会改 | 已迁出的 `batch_size`/`retry`/`guardrails`；**`Lookup_chunk_size` → `LookupChunking`**；片间并行嵌在 `sized(..., parallel=True)` |
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

## 指针

- Upgrade：`references/upgrades/2026-08-09-lookup-chunking-python-ssot.md`
- Design / evidence（归档后）：`llmanspec/changes/archive/*-c40-yaml-runtime-policy-boundary/`
- Live 合约：`llmanspec/specs/yaml-dsl-runtime-policy-boundary/`（r1003–r1005）
- 人类：`docs/doc/yaml-dsl/review-checklist.md`、`capability-matrix.md`、`user-guide.md` §4.4.3
