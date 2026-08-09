# YAML vs Python runtime policy boundary（agent）

0.10.* 心智收口：大头策略键已迁出 YAML；**暂不迁**灰区键。本页只做判定，细节以调研 SSOT 为准。

## 何时读取

- 用户问「这个旋钮该写 YAML 还是 Python」
- 想迁出 / 删除 `lookup_chunk_size`、`cache_mode` 或回流 `batch_size`/`retry`/`write_defaults`
- 混淆 `sources.*.cache_mode` 与 `$rows.cache_mode`，或把 `lookup_chunk_size` 当并行开关

## 三栏判定

| 栏 | 放哪里 | 例子 |
|----|--------|------|
| **MUST 留 YAML** | 编排 / 身份 / 内容协议 | `runs`/deps、`sources`/`fields`/`relations`、`resources.*.path`、`outputs.to`、`params`（含 `$keys`/`$rows`） |
| **MUST 仅 Python** | 环境 / 性能 / 诊断 / 写策略 | `batch_size`、`retry`、`guardrails`、`failure_policy`、`parallelize_lookup_chunks`、`BookWritePolicy`、`workflow.options.*`（已 fail-fast） |
| **灰区（暂留 YAML）** | 需求侧提示；细能力只扩 Python | `lookup_chunk_size`；`sources.*.cache_mode`（`none`/`preload_forever`）；`allow_formulas` |

禁止：未读 inventory 就删 YAML 键；复活 `budget` / `write_defaults`；静默忽略 YAML 改语义。

## 易混钉死

| 写法 | 含义 | 不是 |
|------|------|------|
| `sources.<id>.lookup_chunk_size` | keys 分片**大小** | 并行开关 → 用 `DemandRunRuntimeOptions.parallelize_lookup_chunks`（须 `parallel_mode=adaptive`） |
| `sources.<id>.cache_mode` | source 粗缓存 `none` / `preload_forever` | `$rows.cache_mode` |
| `params` 内 `$rows.cache_mode` | 批次内 relation 复用 `batch` / `none` | source 级 `cache_mode` |

## 反例（不要做）

```yaml
# BAD: 以为 chunk_size 能开并行
sources:
  dim:
    lookup_chunk_size: 800   # 只拆片；并行仍要 Python opt-in
```

```python
# GOOD: 并行在 runtime
DemandRunRuntimeOptions(parallel_mode="adaptive", parallelize_lookup_chunks=True)
```

```yaml
# BAD: 混称两套 cache_mode
sources:
  dim:
    cache_mode: batch   # 非法；source 只有 none/preload_forever
```

## 指针

- 调研 SSOT：`llmanspec/changes/c40-yaml-runtime-policy-boundary/inventory.md`（+ `design.md` R2）
- 人类：`docs/doc/yaml-dsl/review-checklist.md`、`capability-matrix.md`、`index.md`
- 0.10 性能三项（YAML 无强制迁移）：`references/0.10-release-highlights.md`
- Live 合约：`llmanspec/specs/yaml-dsl-runtime-policy-boundary/`、`governance-mainline-principles`
