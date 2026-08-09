# Inventory: YAML authoring surface（c40 全量清点）

> **性质**：开放盘点表，**不是**终局决议。目标方向见 `design.md`：运行可变 / 环境敏感 knobs → Python；YAML 保留可移植编排与内容语义。  
> **来源**：`src/scalim/dsl/yaml_dsl/schema/{demand,workflow}.gen.json`（全树约 demand 198 / workflow 19 paths）+ `validator_migrations` 已迁出表 + `DemandRunRuntimeOptions` / `RunOverrides` / `WorkflowRunOptions`。  
> **轴（工作标注，可改）**  
> - `A` — authoring：图结构 / 身份 / 内容语义（默认可移植）  
> - `R` — runtime：部署/环境/宿主可变，或需按入口覆盖（**目标收口 Python**）  
> - `C` — content-protocol：loader 调用协议（常留 YAML，但勿与 runtime 粗策略混称）  
> - `M` — migrated：已迁出 YAML，fail-fast  
> - `X` — removed：能力删除  
> - `?` — 待证：尚缺产品/下游证据，禁止在本文写死去留  

列含义：`py_today` = 今日是否已有 typed Python 覆盖；空 = 无对等旋钮。

---

## 0) 已迁出 / 已移除（边界证据，非新决议）

| path | 轴 | py_today | 备注 |
|------|----|----------|------|
| `batch_size` | M | `DemandRunRuntimeOptions.batch_size` | fail-fast |
| `guardrails` | M | `DemandRunRuntimeOptions.guardrails` | fail-fast |
| demand `failure_policy` | M | `demand_failure_policy` | fail-fast |
| `include_full_error_message` | M | `demand_diagnostics` | fail-fast |
| `validate_unique_field_names` | M | diagnostics knobs | fail-fast；parser-only 不跑 |
| `main_source.retry` / `sources.*.retry` | M | `loader_retry` | fail-fast |
| `meta` / `audit` | M | `RunOverrides.output_extras` | |
| `resources.books.*.write_defaults` | M | `BookWritePolicy` / `ResourcesPolicy` | fail-fast |
| `resources.books.*.budget` / 旧 `xlsx_memory.budget` | X | — | 能力删除；勿复活 |
| `workflow.options.*` | M | `WorkflowRuntimeOptions` 等 | fail-fast |
| `outputs.*.container` | X | `to.file` / `to.book` | |
| aggregate 基数护栏 / 旧 metrics / DedupBy / TwoStage | X | — | |

**Python-only（本就不在 YAML）摘录**：`parallel_mode` / `max_workers` / `parallelize_lookup_chunks` / `max_chunk_workers` / `key_normalization` / `excel_column_residency` / `sink_type_precheck` / allowlist / `init_vars` / observers·hooks / viz / `cache_pool` / `resources_wait`。

---

## 1) Demand：顶层与 main_source

| path | 轴 | py_today | 备注 |
|------|----|----------|------|
| `name` | A | — | |
| `description` | A | — | |
| `imports` / `$import` / `_templates` | A | — | authoring 复用 |
| `main_source.source_id` | A | — | |
| `main_source.loader` | A | allowlist 解析 | |
| `main_source.params` | C | `init_vars`（动态注入） | 静态可 YAML；动态走 init_vars |
| `main_source.order_by` | A | — | 批次内顺序 |
| `main_source.fields.*`（`source`/`extract`/`name`/`relation`/`value_cast`/`default`） | A | — | 源字段声明 |

## 2) Demand：sources（含争议 knobs）

| path | 轴 | py_today | 备注 |
|------|----|----------|------|
| `sources.*.loader` | A | allowlist | |
| `sources.*.key` | A | — | |
| `sources.*.lookup_cast` | A | — | |
| `sources.*.normalize`（及子策略） | A/? | — | 语义 reshape；是否有环境差异待证 |
| `sources.*.params`（含 `$keys`/`$rows`） | C | — | 数据流协议 |
| `sources.*.params` → `$rows.cache_mode` | C/? | — | `batch`/`none`；批次内复用；**≠** source `cache_mode` |
| `sources.*.fields.*` | A | — | |
| `sources.*.lookup_chunk_size` | R/? | 并行侧：`parallelize_lookup_chunks`；**无** chunk size 的 Python 覆盖 | IN/payload/宿主上限常随部署变 → **优先按 R 评估** |
| `sources.*.cache_mode` | R/? | 细策略无；仅 YAML `none`/`preload_forever` | 缓存寿命/预加载常随入口变 → **优先按 R 评估** |

## 3) Demand：fields / relations

| path | 轴 | py_today | 备注 |
|------|----|----------|------|
| `fields.*`（`compute`/`call_by`/…） | A | allowlist | |
| `relations.*` | A | — | |

## 4) Demand：resources

| path | 轴 | py_today | 备注 |
|------|----|----------|------|
| `resources.books.*.xlsx.path` | A | `RunOverrides` resources | 身份；可 `$init_var` |
| `resources.books.*.xlsx.allow_formulas` | ?/R | extras 侧有类似覆写面 | 常静态，也可能按环境禁公式 → 开放 |
| `resources.files.*.csv_file.path` | A | overrides | |
| `resources.files.*.csv_file.encoding` | ?/R | — | 常静态；宿主编码差异 → 开放 |

## 5) Demand：outputs

| path | 轴 | py_today | 备注 |
|------|----|----------|------|
| `outputs[].name` / `from` / `to` / `fields` / `where` / `aggregate.*` | A | `RunOverrides.outputs` 可替换子集 | 写策略仍 Python |
| `outputs[].write.include_header` | ? | `OutputWriteOverride` | output-local；是否环境相关开放 |
| `outputs[].write.header_fields_output_by` | ? | `OutputWriteOverride` | 同上 |

## 6) Workflow YAML

| path | 轴 | py_today | 备注 |
|------|----|----------|------|
| `workflow.runs[]`（`id`/`demand`/`depends_on`/`main_rows_from`/`init_vars`） | A | patches / options | 编排 |
| `workflow.resources.books|files…` | A | `ResourcesPolicy` 只管写策略 | 身份与 demand 同构 |
| （无）运行期 concurrency / cache_pool / failure | M | `WorkflowRuntimeOptions` | 已不在 YAML |

---

## 7) Schema 全树索引（防漏盘）

以下为 `demand.gen.json` / `workflow.gen.json` **全部 property path**（生成快照；嵌套字段模板已展开）。评审迁出时以此核对漏项；分类以上表 §1–6 为准，全树不逐行标轴。

### demand.gen.json（198）

<details>
<summary>展开 path 列表</summary>

```
name
imports
_templates
description
main_source
main_source.source_id
main_source.loader
main_source.fields
main_source.fields.$import
main_source.fields.*.source
main_source.fields.*.extract
main_source.fields.*.name
main_source.fields.*.relation
main_source.fields.*.relation.steps
main_source.fields.*.relation.steps[].from
main_source.fields.*.relation.steps[].to
main_source.fields.*.relation.steps[].lookup_cast
main_source.fields.*.relation.steps[].lookup_cast.auto|int|str|sep_first(.sep)
main_source.fields.*.value_cast
main_source.fields.*.default(+when/literal/call_by)
main_source.params
main_source.order_by
sources (+$import)
sources.*.loader|key|lookup_cast|lookup_chunk_size|normalize(+子树)|cache_mode|fields(+子树)|params
fields (+compute/call_by/…)
relations
resources.books.*.xlsx.path|allow_formulas
resources.files.*.csv_file.path|encoding
outputs[] name|from|to|write|fields|where|aggregate(+ops)
```

完整枚举以仓库内 `just gen-yaml-dsl-schema` 产物为准；需要机器可读全表时可再导出 `.tmp/`（不入库）。

</details>

### workflow.gen.json（19）

`workflow.runs[]`（id/demand/depends_on/main_rows_from/init_vars）、`workflow.resources.books|files`（path/`allow_formulas`/`encoding`）。

---

## 8) 开放问题（禁止在本文件写死答案）

1. `lookup_chunk_size`：YAML 默认 + Python 覆盖？仅 Python？保留 YAML 但文档标明「可被入口覆盖」？  
2. `sources.*.cache_mode`：与 workflow `cache_pool` 的职责切分；迁出时兼容窗？  
3. `$rows.cache_mode` 是否始终属 C（内容协议）而非 R？  
4. `allow_formulas` / `encoding` / `outputs.write.*`：静态 authoring 还是 R？  
5. `normalize.*` 冲突策略：语义（A）还是运维（R）？  
6. 一步到位迁移范围：仅 R 候选，还是连带 schema/docs/skill/upgrade 同发？

盘点完成标志：§1–6 每行有轴标注且 `?` 行有证据笔记（另附）；§7 无未归类顶层 knob。
