# Inventory: YAML keys vs Python policy (c40 R1)

> 来源：`docs/doc/yaml-dsl/capability-matrix.md` + workflow 文档 + AGENTS Hard Rules。  
> 分类：**编排/身份** | **策略/调优** | **内容/映射** | **已迁出/已移除**。  
> 成本：迁移到 Python-only 的粗估（低/中/高）。本表**不授权删键**。

## 已迁出 / 已移除（保留作边界证据）

| YAML key | 类 | Python 覆盖 | 成本 | 备注 |
|----------|----|-------------|------|------|
| `batch_size` | 策略 | `DemandRunRuntimeOptions.batch_size` | — | fail-fast |
| `main_source.retry` / `sources.*.retry` | 策略 | `loader_retry` | — | fail-fast |
| `guardrails` | 策略 | `DemandRunRuntimeOptions.guardrails` | — | fail-fast |
| `failure_policy` | 策略 | `demand_failure_policy` | — | fail-fast |
| `include_full_error_message` | 策略 | `demand_diagnostics` | — | fail-fast |
| `meta` / `audit` | 策略/输出 extras | `RunOverrides.output_extras` | — | 迁出 YAML 主线 |
| `resources.books.*.write_defaults` | 策略 | `BookWritePolicy` / `ResourcesPolicy` | — | fail-fast |
| `resources.books.*.budget` 等 | 策略 | **能力删除** | — | fail-fast；勿复活 |
| `outputs.*.container` | 编排旧形 | `to.file` / `to.book` | — | 已移除 |
| `workflow.options.*` / `share_preload_cache` | 策略 | `WorkflowRuntimeOptions` | — | fail-fast |
| aggregate 基数护栏 / 旧 `metrics` / DedupBy / TwoStage | 策略/派生 | 上游 dedupe / 两 demand | — | 已移除 |

## Demand：仍在 YAML 主线

| YAML key | 类 | 已有 Python 覆盖？ | 迁移成本 | 建议 |
|----------|----|-------------------|----------|------|
| `name` / `description` | 编排/身份 | n/a | — | 留 YAML |
| `imports` / `$import` / `_templates` | 编排 | n/a | — | 留 YAML |
| `main_source.source_id` / `loader` / `order_by` / `fields.*` | 编排+内容 | allowlist 仅安全 | — | 留 YAML |
| `main_source.params` | 内容/映射 | `init_vars` | 低（边缘） | 留 YAML；动态进 `init_vars` |
| `sources.*.loader` / `key` / `lookup_cast` / `normalize` / `fields.*` | 编排+内容 | — | — | 留 YAML |
| `sources.*.params`（含 `$keys`/`$rows`） | 内容/映射 | — | 高 | **留 YAML**（数据流协议） |
| `sources.*.lookup_chunk_size` | **策略/调优**（分片大小） | 并行在 Python：`parallelize_lookup_chunks` | 中 | **中长期仍留 YAML**（c30 立场：大小≠并行；下游 IN/payload 上限常随 demand 声明） |
| `sources.*.cache_mode` | **策略/调优**（粗缓存） | 细策略需 Python | 中 | **暂留 YAML**；更细粒度只扩 Python，不先删 `none/preload_forever` |
| `fields.*` / `compute` / `call_by` | 内容 | allowlist | — | 留 YAML |
| `relations.*` | 编排 | — | — | 留 YAML |
| `resources.files.*.path` / `resources.books.*.path`(+kind) | 编排/身份 | overrides | — | 留 YAML |
| `outputs[]` / `to` / `fields` / `where` / `aggregate` / `from` | 编排+内容 | `RunOverrides.outputs` 可替换子集 | — | 留 YAML；写策略仍 Python |
| `outputs.*.write`（header 局部） | 编排（output-local） | BookWritePolicy 不管 header | 低 | **留 YAML**（仅 `include_header` / `header_fields_output_by`） |

## Workflow YAML

| YAML key | 类 | Python 覆盖 | 建议 |
|----------|----|-------------|------|
| `workflow.runs` / deps | 编排 | — | 留 YAML |
| `workflow.resources` 身份 | 编排/身份 | `ResourcesPolicy` 只管写策略 | 留 YAML |
| 运行期：`cache_pool` / `resources_wait` / 并发 / 失败策略 | 策略 | `WorkflowRuntimeOptions` | **已不在 YAML** |

## 不在 YAML（应保持 Python-only）

allowlist、`init_vars`、`parallel_mode`/`max_workers`、`parallelize_lookup_chunks`、自定义 sink、observers/hooks、viz_config、`BookWritePolicy`、workflow cache_pool 等——见 capability-matrix §6。

## R1 摘要

- **大头策略键已迁完**；c40 不是「再砍一轮 YAML」，而是**收口叙事 + 钉死残留争议**。
- 仍偏策略、但建议**暂不迁**的主争议：`lookup_chunk_size`、`cache_mode`。
- `params`/`$rows.cache_mode` 属内容/调用协议，勿误标为 runtime policy。
