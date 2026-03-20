# YAML DSL Capability Coverage Matrix (SSOT)

本文件是 `demo_big_data_report/by_yaml_dsl/` 的维护入口，用于把 **最新 schema** 的关键能力点映射到：

1) 覆盖该能力点的 YAML fixtures（demand/workflow）
2) 对拍入口（章节/纯 Python oracle/断言点）

基准（SSOT）：

- Demand schema: `src/scalim/dsl/by_yaml/schema/demand.gen.json`
- Workflow schema: `src/scalim/dsl/by_yaml/schema/workflow.gen.json`
- 语法索引（generated）：`artifacts/skills/scalim-yaml-dsl/references/syntax-catalog.gen.md`

约定：

- “章节”指 `notebooks/marimo/**/chapters/*.py` 中的 headless `run_*()` SSOT 入口。
- “oracle”优先指 `packages/scalim-misc/src/scalim_misc/**` 下的纯 Python 对照/断言函数。
- 本矩阵允许先落 “YAML+oracle”，章节后续再补齐；但最终以 `just examples` 可回归为准。

---

## Demand YAML (demand.gen.json)

### 1) 顶层结构与复用

- `name`/`description`
  - YAML: `notebooks/marimo/demo_big_data_report/by_yaml_dsl/ecommerce_report.yaml`
  - YAML: `notebooks/marimo/demo_big_data_report/by_yaml_dsl/ads/ads_campaign_report.yaml`
  - YAML: `notebooks/marimo/demo_big_data_report/by_yaml_dsl/support/support_sla_report.yaml`
  - YAML: `notebooks/marimo/demo_big_data_report/by_yaml_dsl/support/support_output_failure_primary_only_redacted.yaml`
  - Oracle: 各场景对应 `verify_*`（见下文）
- `batch_size`（含 `null` 禁用分批）
  - YAML: `notebooks/marimo/demo_big_data_report/by_yaml_dsl/support/support_sla_report.yaml`（`null`）
  - YAML: `notebooks/marimo/demo_big_data_report/by_yaml_dsl/ecommerce_report.yaml`（整数）
- `imports` + 顶层 `$import`（跨文件 fragments, V1 同目录约束; 支持 string 或 list 合并）
  - YAML: `notebooks/marimo/demo_big_data_report/by_yaml_dsl/ecommerce_report.yaml`（imports + `$import`）
  - YAML: `notebooks/marimo/demo_big_data_report/by_yaml_dsl/ecommerce_report_fragments.yaml`
  - YAML: `notebooks/marimo/demo_big_data_report/by_yaml_dsl/support/support_output_failure_primary_only_redacted.yaml`（顶层 `$import: [..]`）
  - YAML: `notebooks/marimo/demo_big_data_report/by_yaml_dsl/support/support_output_failure_fragments.yaml`
- `_templates`（用于 anchors/merge 复用；`_templates.retry.*` 受 schema 校验）
  - YAML: `notebooks/marimo/demo_big_data_report/by_yaml_dsl/ecommerce_report.yaml`
  - YAML: `notebooks/marimo/demo_big_data_report/by_yaml_dsl/ads/ads_campaign_report.yaml`

### 2) Loader 引用与参数指令

- `main_source.loader` / `sources.*.loader`（安全引用 + allowlist）
  - YAML: 各场景 demand YAML（见上）
  - Loader impl:
    - `packages/scalim-misc/src/scalim_misc/demo_big_data_report/loaders.py`
    - `packages/scalim-misc/src/scalim_misc/demo_big_data_report/by_yaml_dsl/ads_scenario.py`
    - `packages/scalim-misc/src/scalim_misc/demo_big_data_report/by_yaml_dsl/support_scenario.py`
- `params` directives
  - `{$init_var: ...}`: `notebooks/marimo/demo_big_data_report/by_yaml_dsl/workflow_demo_big_data_report_detail_demand.yaml`
  - `{$keys: {as: list/set}}`: 同上（sources.params.ids）
- `sources.*.normalize`（whole-result normalize, 支持多种形态）
  - `index_by_key`: `notebooks/marimo/demo_big_data_report/by_yaml_dsl/ecommerce_report.yaml`（payment_methods）
  - `map_values` + `steps`（take_first/project_fields）: `notebooks/marimo/demo_big_data_report/by_yaml_dsl/ecommerce_report.yaml`（payment_methods_candidates）
  - Oracle: `notebooks/marimo/demo_big_data_report/chapters/01_yaml_dsl_ecommerce.py`（对拍由 `verify_scalim_output` 覆盖）

### 3) 字段定义（source fields vs derived fields）

- source fields（仅 extract/relation/value_cast；禁止 compute）
  - YAML: `notebooks/marimo/demo_big_data_report/by_yaml_dsl/ads/ads_campaign_report.yaml`（`extract`/`value_cast`）
  - YAML: `notebooks/marimo/demo_big_data_report/by_yaml_dsl/workflow_demo_big_data_report_detail_demand.yaml`
- derived fields：`compute`
  - YAML: `notebooks/marimo/demo_big_data_report/by_yaml_dsl/ads/ads_campaign_report.yaml`（`is_click/is_conversion/cost_usd_adjusted`）
  - YAML: `notebooks/marimo/demo_big_data_report/by_yaml_dsl/support/support_sla_report.yaml`（`is_sla_breach`）
- derived fields：`call_by`
  - YAML: `notebooks/marimo/demo_big_data_report/by_yaml_dsl/ecommerce_report.yaml`
  - YAML: `notebooks/marimo/demo_big_data_report/by_yaml_dsl/ads/ads_campaign_report.yaml`（`micros_to_usd`）

### 4) Relations（steps-only, cast, 多级/复合键）

- 单级关联
  - YAML: `notebooks/marimo/demo_big_data_report/by_yaml_dsl/ecommerce_report.yaml`
- 多级关联（2 级链路）
  - YAML: `notebooks/marimo/demo_big_data_report/by_yaml_dsl/ads/ads_campaign_report.yaml`（impressions → adgroups → campaigns）
  - YAML: `notebooks/marimo/demo_big_data_report/by_yaml_dsl/workflow_demo_big_data_report_detail_demand.yaml`
- 复合键关联（from/to 都是数组）
  - YAML: `notebooks/marimo/demo_big_data_report/by_yaml_dsl/ads/ads_campaign_report.yaml`（placement+country）
  - YAML: `notebooks/marimo/demo_big_data_report/by_yaml_dsl/ecommerce_report.yaml`（region_id+product_category_id）
- `lookup_cast`（int/sep_first）
  - YAML: `notebooks/marimo/demo_big_data_report/by_yaml_dsl/ads/ads_campaign_report.yaml`（creative_id cast to int）
  - YAML: `notebooks/marimo/demo_big_data_report/by_yaml_dsl/support/support_lookup_cast_sep_first_type_error_guardrail.yaml`（sep_first + sep）
  - 断言点（章节）：
    - `notebooks/marimo/demo_big_data_report/chapters/12_yaml_dsl_lookup_cast_sep_first_type_error_guardrail.py`

### 5) Retry（loader_retry）

- 顶层 `retry`（policy + should_retry 回调）
  - YAML: `notebooks/marimo/demo_big_data_report/by_yaml_dsl/ads/ads_campaign_report.yaml`
  - Loader/should_retry:
    - `packages/scalim-misc/src/scalim_misc/demo_big_data_report/by_yaml_dsl/ads_scenario.py`（`load_ads_creatives` + `should_retry_ads_transient`）
  - 断言点（oracle/章节）：
    - ads oracle: `packages/scalim-misc/src/scalim_misc/demo_big_data_report/by_yaml_dsl/ads_scenario.py`（`get_ads_creatives_retry_counter_calls`）

### 6) Outputs（output_target/output_container/output_aggregate）

- container types: `csv`/`workbook`
  - CSV:
    - `notebooks/marimo/demo_big_data_report/by_yaml_dsl/ads/ads_campaign_report.yaml`
    - `notebooks/marimo/demo_big_data_report/by_yaml_dsl/support/support_sla_report.yaml`
  - Workbook:
    - `notebooks/marimo/demo_big_data_report/by_yaml_dsl/ecommerce_report.yaml`
- `outputs.*.container.path` 支持 `{$init_var: ...}`
  - YAML: `notebooks/marimo/demo_big_data_report/by_yaml_dsl/ads/ads_campaign_report.yaml`
  - YAML: `notebooks/marimo/demo_big_data_report/by_yaml_dsl/support/support_sla_report.yaml`
- `outputs.*.fields` 支持 YAML alias/object 条目
  - YAML: `notebooks/marimo/demo_big_data_report/by_yaml_dsl/ads/ads_campaign_report.yaml`
  - YAML: `notebooks/marimo/demo_big_data_report/by_yaml_dsl/support/support_sla_report.yaml`
- `from`（继承 fields/container）
  - YAML: `notebooks/marimo/demo_big_data_report/by_yaml_dsl/ads/ads_campaign_report.yaml`（`detail_clicks` from `detail_all`）
- `where`（安全表达式谓词）
  - YAML: `notebooks/marimo/demo_big_data_report/by_yaml_dsl/ads/ads_campaign_report.yaml`（`where: "is_click"`）
  - YAML: `notebooks/marimo/demo_big_data_report/by_yaml_dsl/support/support_sla_report.yaml`（`where: "agent_team"`）
- aggregate ops（示例覆盖）
  - `count`/`sum`: `notebooks/marimo/demo_big_data_report/by_yaml_dsl/workflow_demo_big_data_report_metrics_demand.yaml`
  - `count_true`/`count_true_gte`: `notebooks/marimo/demo_big_data_report/by_yaml_dsl/ads/ads_campaign_report.yaml`、`notebooks/marimo/demo_big_data_report/by_yaml_dsl/support/support_sla_report.yaml`
  - `count_distinct`: `notebooks/marimo/demo_big_data_report/by_yaml_dsl/ecommerce_report.yaml`
  - `dense_rank`: `notebooks/marimo/demo_big_data_report/by_yaml_dsl/ecommerce_report.yaml`
  - `row_number` + `partition_by`: `notebooks/marimo/demo_big_data_report/by_yaml_dsl/ecommerce_rank_score_report.yaml`
  - `score_by_rank`（rank_field/base/step）: `notebooks/marimo/demo_big_data_report/by_yaml_dsl/ecommerce_rank_score_report.yaml`
  - 断言点（章节）：
    - `notebooks/marimo/demo_big_data_report/chapters/10_yaml_dsl_row_number_score_by_rank.py`
  - aggregate `compute`（DAG 派生）: `notebooks/marimo/demo_big_data_report/by_yaml_dsl/ads/ads_campaign_report.yaml`、`notebooks/marimo/demo_big_data_report/by_yaml_dsl/support/support_sla_report.yaml`

### 7) Guardrails（运行期护栏）

- `guardrails.enabled` + `mode: quiet`
  - YAML: `notebooks/marimo/demo_big_data_report/by_yaml_dsl/support/support_sla_report.yaml`
  - 断言点（oracle/章节）：
    - `packages/scalim-misc/src/scalim_misc/demo_big_data_report/by_yaml_dsl/support_scenario.py`
      - `GuardrailCaptureObserver`
      - `expected_support_guardrail_codes`
- `guardrails.loader.required_fields` 支持 field_id string + YAML alias
  - YAML: `notebooks/marimo/demo_big_data_report/by_yaml_dsl/support/support_sla_report.yaml`
- `guardrails.relations.null_key_max_rate`
  - YAML: `notebooks/marimo/demo_big_data_report/by_yaml_dsl/support/support_sla_report.yaml`
- `guardrails.compute.on_error`
  - YAML: `notebooks/marimo/demo_big_data_report/by_yaml_dsl/support/support_guardrails_compute_on_error.yaml`
  - 断言点（章节）：
    - `notebooks/marimo/demo_big_data_report/chapters/11_yaml_dsl_guardrails_compute_on_error.py`
- `guardrails.relations.type_error_max_rate`
  - YAML: `notebooks/marimo/demo_big_data_report/by_yaml_dsl/support/support_lookup_cast_sep_first_type_error_guardrail.yaml`
  - 断言点（章节）：
    - `notebooks/marimo/demo_big_data_report/chapters/12_yaml_dsl_lookup_cast_sep_first_type_error_guardrail.py`

### 8) Observability（可观测性）

- `observability.performance` + report（csv）+ thresholds
  - YAML: `notebooks/marimo/demo_big_data_report/by_yaml_dsl/ecommerce_report.yaml`
- `observability.relations` + report（json）
  - YAML: `notebooks/marimo/demo_big_data_report/by_yaml_dsl/ecommerce_report.yaml`
- `observability.logging`
  - YAML: `notebooks/marimo/demo_big_data_report/by_yaml_dsl/support/support_observability_full.yaml`
  - 断言点（章节）：
    - `notebooks/marimo/demo_big_data_report/chapters/08_yaml_dsl_observability_full.py`
- `observability.trace`
  - YAML: `notebooks/marimo/demo_big_data_report/by_yaml_dsl/support/support_observability_full.yaml`
  - 断言点（章节）：
    - `notebooks/marimo/demo_big_data_report/chapters/08_yaml_dsl_observability_full.py`
- `observability.viz`
  - YAML: `notebooks/marimo/demo_big_data_report/by_yaml_dsl/support/support_observability_full.yaml`
  - 断言点（章节）：
    - `notebooks/marimo/demo_big_data_report/chapters/08_yaml_dsl_observability_full.py`
- `observability.viz.output_path` / `observability.viz.snapshot_path`
  - YAML: `notebooks/marimo/demo_big_data_report/by_yaml_dsl/support/support_viz_custom_paths.yaml`
  - 断言点（章节）：
    - `notebooks/marimo/demo_big_data_report/chapters/13_yaml_dsl_viz_custom_paths.py`
- `observability.row_gap`
  - YAML: `notebooks/marimo/demo_big_data_report/by_yaml_dsl/support/support_sla_report.yaml`
  - 断言点（oracle/章节）：
    - `packages/scalim-misc/src/scalim_misc/demo_big_data_report/by_yaml_dsl/support_scenario.py:expected_support_row_gap_totals`
- `observability.memory_opt`
  - YAML: `notebooks/marimo/demo_big_data_report/by_yaml_dsl/support/support_observability_full.yaml`
  - 断言点（章节）：
    - `notebooks/marimo/demo_big_data_report/chapters/08_yaml_dsl_observability_full.py`

### 9) Outputs failure policy（多输出失败策略）

- `failure_policy`（demand 多输出失败策略：all_fail/primary_only）
  - YAML: `notebooks/marimo/demo_big_data_report/by_yaml_dsl/support/support_output_failure_primary_only_redacted.yaml`
  - YAML: `notebooks/marimo/demo_big_data_report/by_yaml_dsl/support/support_output_failure_all_fail.yaml`
  - 断言点（章节）：
    - `notebooks/marimo/demo_big_data_report/chapters/07_yaml_dsl_output_failure_policy.py`
- `include_full_error_message`（错误信息是否包含全文）
  - YAML: `notebooks/marimo/demo_big_data_report/by_yaml_dsl/support/support_output_failure_primary_only_redacted.yaml`
  - YAML: `notebooks/marimo/demo_big_data_report/by_yaml_dsl/support/support_output_failure_primary_only_full.yaml`
  - 断言点（章节）：
    - `notebooks/marimo/demo_big_data_report/chapters/07_yaml_dsl_output_failure_policy.py`

---

## Workflow YAML (workflow.gen.json)

### 核心结构与 DAG

- `workflow.runs[*].id` / `demand`
  - YAML: `notebooks/marimo/demo_big_data_report/by_yaml_dsl/workflow_fixture.yaml`
- `depends_on`（显式 DAG）
  - YAML: `notebooks/marimo/demo_big_data_report/by_yaml_dsl/workflow_demo_big_data_report.yaml`
- `$ctx` 注入（下游 demand 使用上游 output_path）
  - YAML: `notebooks/marimo/demo_big_data_report/by_yaml_dsl/workflow_demo_big_data_report.yaml`
  - Demand YAML: `notebooks/marimo/demo_big_data_report/by_yaml_dsl/workflow_demo_big_data_report_metrics_demand.yaml`

### resources + writes（多输出资源托管）

- `workflow.resources.sheetbooks` / `csvs`
  - YAML: `notebooks/marimo/demo_big_data_report/by_yaml_dsl/workflow_demo_big_data_report.yaml`
- `workflow.resources.workbooks`
  - YAML: `notebooks/marimo/demo_big_data_report/by_yaml_dsl/workflow_demo_shared_workbooks.yaml`
- `writes`（sheetbook_sheet + csv_append）
  - YAML: `notebooks/marimo/demo_big_data_report/by_yaml_dsl/workflow_demo_big_data_report.yaml`
- `writes.sheetbook_append`
  - YAML: `notebooks/marimo/demo_big_data_report/by_yaml_dsl/workflow_demo_shared_workbooks.yaml`
- `writes.workbook_sheet` / `writes.workbook_append`
  - YAML: `notebooks/marimo/demo_big_data_report/by_yaml_dsl/workflow_demo_shared_workbooks.yaml`
  - 断言点（章节）：
    - `notebooks/marimo/demo_big_data_report/chapters/09_workflow_shared_workbooks.py`

### options

- `max_concurrency`
  - YAML: `notebooks/marimo/demo_big_data_report/by_yaml_dsl/workflow_demo_big_data_report.yaml`
- `failure_policy`
  - YAML: `notebooks/marimo/demo_big_data_report/by_yaml_dsl/workflow_demo_big_data_report.yaml`
- `ctx` guardrails（max_value_bytes/max_bytes）
  - YAML: `notebooks/marimo/demo_big_data_report/by_yaml_dsl/workflow_demo_big_data_report.yaml`
- `cache_pool`（budget + conflict/release policy）
  - YAML: `notebooks/marimo/demo_big_data_report/by_yaml_dsl/workflow_demo_big_data_report.yaml`
- `cache_pool.pin`
  - YAML: `notebooks/marimo/demo_big_data_report/by_yaml_dsl/workflow_fixture_cache_pool_pin.yaml`
  - 断言点（章节）：
    - `notebooks/marimo/demo_big_data_report/chapters/14_workflow_cache_pool_pin.py`
