# Inventory: YAML keys vs Python policy (c40 R1)

> 来源：`docs/doc/yaml-dsl/capability-matrix.md` + `demand.gen.json` sources/books + workflow 文档 + AGENTS Hard Rules + `validator_migrations` fail-fast 表。  
> 本表**不授权删键**。迁移成本 = 迁到 Python-only 的粗估（低/中/高）。

## 术语（全仓统一）

| 标签 | 含义 | 行动默认 |
|------|------|----------|
| **MUST 留 YAML** | 编排 / 资源身份 / 内容与数据流协议 | 不得迁出；误标为 runtime policy 则拒 |
| **MUST 仅 Python** | 环境/性能/集成/诊断策略；已迁出或从未进 YAML | 不得回流 YAML |
| **灰区（YAML 可选提示）** | 偏策略，但与 demand 可移植声明绑定；Python 可覆盖/扩展 | **暂不迁**；细能力只扩 Python |
| **内容/映射** | loader 调用协议、字段映射、模板指令 | 留 YAML（勿与 runtime policy 混谈） |
| **已迁出 / 已移除** | fail-fast 或能力删除 | 勿复活；删残留字段 |

对照：`design.md` R2；文档叙事 follow-up 走 **quick**（见 `design.md` R3 Q1–Q6），不另开 change。

## 已迁出 / 已移除（边界证据）

| YAML key | 类 | Python 覆盖 | 成本 | 备注 |
|----------|----|-------------|------|------|
| `batch_size` | MUST 仅 Python | `DemandRunRuntimeOptions.batch_size` | — | fail-fast |
| `main_source.retry` / `sources.*.retry` | MUST 仅 Python | `loader_retry` | — | fail-fast |
| `guardrails` | MUST 仅 Python | `DemandRunRuntimeOptions.guardrails` | — | fail-fast |
| `failure_policy`（demand 顶层） | MUST 仅 Python | `demand_failure_policy` | — | fail-fast |
| `include_full_error_message` | MUST 仅 Python | `demand_diagnostics` | — | fail-fast |
| `validate_unique_field_names` | MUST 仅 Python | runtime diagnostics knobs | — | fail-fast；parser-only 路径不跑 |
| `meta` / `audit` | MUST 仅 Python | `RunOverrides.output_extras` | — | 迁出 YAML 主线 |
| `resources.books.*.write_defaults` | MUST 仅 Python | `BookWritePolicy` / `ResourcesPolicy` | — | fail-fast |
| `resources.books.*.budget` 等 | 已移除 | **能力删除** | — | fail-fast；勿复活 |
| `outputs.*.container` | 编排旧形 | `to.file` / `to.book` | — | 已移除 |
| `workflow.options.*` / `share_preload_cache` | MUST 仅 Python | `WorkflowRuntimeOptions` | — | fail-fast |
| aggregate 基数护栏 / 旧 `metrics` / DedupBy / TwoStage | 已移除 | 上游 dedupe / 两 demand | — | 已移除 |

## Demand：仍在 YAML 主线

| YAML key | 类 | 已有 Python 覆盖？ | 迁移成本 | 建议 |
|----------|----|-------------------|----------|------|
| `name` / `description` | MUST 留 YAML | n/a | — | 留 |
| `imports` / `$import` / `_templates` | MUST 留 YAML | n/a | — | 留 |
| `main_source.source_id` / `loader` / `order_by` / `fields.*` | MUST 留 YAML | allowlist 仅安全 | — | 留 |
| `main_source.params` | 内容/映射 | `init_vars` | 低（边缘） | 留；动态进 `init_vars` |
| `sources.*.loader` / `key` / `lookup_cast` / `normalize` / `fields.*` | MUST 留 YAML | — | — | 留 |
| `sources.*.params`（含 `$keys`/`$rows`） | 内容/映射 | — | 高 | **留**（数据流协议） |
| `sources.*.lookup_chunk_size` | **灰区**（分片大小提示） | 并行：`parallelize_lookup_chunks` | 中 | **中长期仍留**（大小≠并行；IN/payload 上限常随 demand） |
| `sources.*.cache_mode` | **灰区**（粗缓存 `none`/`preload_forever`） | 细策略需扩 Python | 中 | **暂留**；不先删粗枚举 |
| `$rows.cache_mode`（`batch`/`none`） | 内容/映射（批次内 relation 复用） | — | 高 | **留**；**不是** `sources.*.cache_mode` |
| `fields.*` / `compute` / `call_by` | 内容/映射 | allowlist | — | 留 |
| `relations.*` | MUST 留 YAML | — | — | 留 |
| `resources.files.*.path` / `resources.books.*.xlsx`(+可选 `path`) | MUST 留 YAML | overrides | — | 留 |
| `resources.books.*.xlsx.allow_formulas` | 灰区（通常静态） | — | 低 | **暂留 YAML**（AGENTS：may remain） |
| `encoding`（若出现在资源/输出侧） | 灰区（通常静态） | — | 低 | **暂留 YAML**；环境强绑再议 |
| `outputs[]` / `to` / `fields` / `where` / `aggregate` / `from` | MUST 留 YAML | `RunOverrides.outputs` 可替换子集 | — | 留；写策略仍 Python |
| `outputs.*.write`（header 局部） | MUST 留 YAML（output-local） | BookWritePolicy 不管 header | 低 | 留（仅 `include_header` / `header_fields_output_by`） |

### 易混：两套 `cache_mode`

| 位置 | 枚举 | 语义 |
|------|------|------|
| `sources.<id>.cache_mode` | `none` / `preload_forever` | source 级预加载/不缓存 |
| `params` 内 `$rows.cache_mode` | `batch` / `none` | 批次内 relation 行复用；默认 `batch` |

文档与 skill **MUST** 分栏写清，禁止「把 cache_mode 当 parallel」或两套混称。

## Workflow YAML

| YAML key | 类 | Python 覆盖 | 建议 |
|----------|----|-------------|------|
| `workflow.runs` / deps | MUST 留 YAML | — | 留 |
| `workflow.resources` 身份 | MUST 留 YAML | `ResourcesPolicy` 只管写策略 | 留 |
| 运行期：`cache_pool` / `resources_wait` / 并发 / 失败策略 | MUST 仅 Python | `WorkflowRuntimeOptions` | **已不在 YAML** |

## 不在 YAML（应保持 Python-only）

allowlist、`init_vars`、`parallel_mode`/`max_workers`、`parallelize_lookup_chunks`、自定义 sink、observers/hooks、viz_config、`BookWritePolicy`、workflow `cache_pool`、ExcelColumnResidency 等——见 capability-matrix §6 与 live `yaml-dsl-runtime-policy-boundary`。

## R1 摘要

- **大头策略键已迁完**；c40 是**收口叙事 + 钉死灰区**，不是再砍一轮 YAML。
- 灰区主争议：`lookup_chunk_size`、`sources.*.cache_mode`（另：`allow_formulas` / `encoding` 为静态暂留）。
- `params` / `$rows.cache_mode` 属内容协议，勿标 runtime policy。
- schema `definitions.source` 键集已对拍：`$import` / `cache_mode` / `fields` / `key` / `loader` / `lookup_cast` / `lookup_chunk_size` / `normalize` / `params`。
