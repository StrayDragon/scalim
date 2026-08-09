# YAML vs Python runtime policy boundary（agent）

c40 **重开盘点中**：换环境就会改的配置 **目标收口 Python**；YAML 保留可移植编排与内容。本页只给判定启发式与易混钉死；**去留与示例片段以 `evidence-notes.md` 为准**，不要引用旧「暂不迁」结论。

## 何时读取

- 用户问「这个旋钮该写 YAML 还是 Python」
- 涉及 `lookup_chunk_size`、`cache_mode`、或已迁出键回流
- 混淆 `sources.*.cache_mode` 与 `$rows.cache_mode`

## 三栏启发式（工作用）

| 栏 | 含义 | 例子 |
|----|------|------|
| **宜留在 YAML** | 换环境仍应相同的图、字段、loader 协议 | `runs`/deps、`fields`/`relations`、`params`（`$keys`/`$rows`）、资源 path |
| **宜收口到 Python** | 换部署/配额/入口就会改 | 已迁出的 `batch_size`/`retry`/`guardrails`；候选 `lookup_chunk_size`、`sources.*.cache_mode`；并行 `parallelize_lookup_chunks` |
| **尚待证据** | 未决；常见已有 overrides | `allow_formulas`、`encoding`、`outputs.write.*`、部分 `normalize.*` |

禁止：未读 `evidence-notes.md` 就删键；回流 `budget`/`write_defaults`；静默忽略 YAML。

## 易混钉死（语义事实，不是去留决议）

| 写法 | 含义 | 不是 |
|------|------|------|
| `sources.<id>.lookup_chunk_size` | keys 分片**大小** | 并行开关 → `parallelize_lookup_chunks` + `parallel_mode=adaptive` |
| `sources.<id>.cache_mode` | `none` / `preload_forever` | `$rows.cache_mode` |
| `$rows.cache_mode` | `batch` / `none`（批次内复用） | source 级 `cache_mode` |

## 指针

- 开放盘点 SSOT（含真实片段）：`llmanspec/changes/c40-yaml-runtime-policy-boundary/evidence-notes.md`（+ `design.md` 第一刀草案）
- 人类：`docs/doc/yaml-dsl/review-checklist.md`、`capability-matrix.md`、`index.md`
- 0.10 性能三项：`references/0.10-release-highlights.md`
- Live 合约：`llmanspec/specs/yaml-dsl-runtime-policy-boundary/`、`governance-mainline-principles`
