# tasks: c15-remove-derived-outputs-cardinality-guardrails

> 完整移除派生输出基数护栏体系（`max_groups` / `max_distinct` / `distinct_on_overflow` / `dedup_by.on_overflow`）。
> **保留** `dedup_by.on_conflict` / `DedupOnConflictPolicy`（去重本职语义，非护栏）。
> BREAKING：IR 构造参数、YAML 字段、指纹、错误类、截断审计均受影响。

## Propose（已完成）

- [x] 0.1 写好 `proposal.md` / `design.md`（完整移除 vs 仅移除 fail-only 权衡；on_conflict 必须保留决策）
- [x] 0.2 delta：`execution-derived-outputs`（remove r723 / r217；modify r577 / r242；add r800）
- [x] 0.3 delta：`yaml-dsl-write-policy-and-output-extras`（add r801）
- [x] 0.4 `llman sdd validate c15-remove-derived-outputs-cardinality-guardrails --strict --no-interactive`

## Apply

### 运行期核心：derived_outputs.py

- [x] 1.1 移除 `_BoundedDistinctKeySet` 类（整体）；`_CountDistinctMetric` distinct 状态退化为普通 `set`（`__init__`/`accumulate`/`finalize`），移除 `truncated` / `key_count` 护栏属性
- [x] 1.2 `GroupByAggregator` / `RankedGroupByAggregator` / `DedupByThenAggregator`：移除 `max_groups` / `max_distinct` / `distinct_on_overflow` / `on_overflow` 构造参数与限界逻辑
- [x] 1.3 移除错误类 `ScalimAggregationKeyLimitExceededError` / `ScalimDistinctKeyLimitExceededError`

### IR 层：specs.py

- [x] 2.1 `DerivedGroupBySpec`：移除 `max_groups` / `max_distinct` / `distinct_on_overflow` 字段
- [x] 2.2 `DedupBySpec`：移除 `max_distinct` / `on_overflow` 字段；**保留** `on_conflict`
- [x] 2.3 `fingerprint_parts` / `validate_parallel_mode` / `build_aggregator`：移除护栏引用
- [x] 2.4 `TwoStageGroupBySpec.build_aggregator`：透传清理

### policy enum：_output_composition_policies.py

- [x] 3.1 移除 `DerivedOverflowPolicy` enum（**保留** `DedupOnConflictPolicy`）

### build 警告：build.py

- [x] 4.1 移除 `_warn_derived_guardrails` / `_collect_specs_for_derived_warnings`；移除 `_append_derived_target_routes` 调用点

### YAML schema：schema_dsl/models/outputs.py

- [x] 5.1 移除 `max_groups` / `max_distinct` / `distinct_on_overflow` 字段定义

### YAML parser：config_parsing/parsers/outputs.py

- [x] 6.1 移除相关解析与负值校验；为残留 `max_groups` / `max_distinct` / `distinct_on_overflow` / `dedup_by.on_overflow` 字段加 fail-fast + 迁移提示

### YAML runtime bridge：runtime/output_composition_yaml.py

- [x] 7.1 移除 `DerivedGroupBySpec` / `DedupBySpec` 构造时的护栏字段透传

### 测试

- [x] 8.1 删除护栏警告测试（`tests/execution/test_output_composition.py` 中 `max_groups=0` warn 等用例）
- [x] 8.2 删除 overflow 行为测试、parser 负值校验测试（`tests/yaml_dsl/test_yaml_parser_outputs_internal.py`）
- [x] 8.3 更新受影响指纹快照

### 文档 + 重生成

- [x] 9.1 更新升级说明 `agentdev/skills/scalim-yaml-dsl/references/upgrades/2026-03-13-derived-outputs-set-aggregations.md` 中护栏段落
- [x] 9.2 `just gen-docs` 重生成受影响 `.gen.*`（JSON schema、`syntax-catalog.gen.md` 等，禁止手改）

### 校验

- [x] 10.1 `just qa` 全绿
- [x] 10.2 `llman sdd validate c15-remove-derived-outputs-cardinality-guardrails --strict --no-interactive`
- [x] 10.3 `llman sdd validate --all --strict --no-interactive`
