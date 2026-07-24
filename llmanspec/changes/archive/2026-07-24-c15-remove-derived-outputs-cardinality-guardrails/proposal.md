depends_on: []
---

## Why

派生输出（derived outputs）在 build 阶段会为每个未显式配置护栏的 derived target 发出 `scalim.derived_outputs` WARNING：

- `max_groups=0(不设上限), 高基数分组可能耗尽内存; 建议设置 max_groups`
- `max_distinct=0(不设上限), count_distinct 高基数可能耗尽内存; 建议设置 max_distinct`
- `dedup_by.max_distinct=0(不设上限), 高基数去重可能耗尽内存; 建议设置 dedup_by.max_distinct`

这些警告在真实业务中普遍构成恼人噪音：业务分组字段多为低基数维度（`customer_name` / `region_name` / `country_dim_name` 等），而护栏默认值 `0=不设上限`，导致**每个** derived target 都触发警告。用户必须为每个低基数维度手工估算并填一个略大于真实基数的整数，仅为了消音——维护成本高、收益低。

更深层的动机是护栏能力的实际价值有限：

1. **`max_groups` 只能失败、无法恢复**：超限直接抛 `ScalimAggregationKeyLimitExceededError`，无降级路径（`derived_outputs.py:756-757`）。
2. **`max_distinct` + `on_overflow: truncate` 虽有 graceful degradation**（驱逐最差键、近似 top-N，`derived_outputs.py:376-389`），但该降级语义对当前业务无意义；OOM 风险已由系统层 OOM killer 进程级兜底。
3. 护栏体系在 spec / 运行期 / YAML schema / parser / runtime bridge / 错误类 / overflow policy enum / 测试 / 文档多处铺开，**维护面积与实际保护价值不成比例**。

权衡后选择完整移除护栏体系，换取更低的维护成本；失去的 `truncate` 降级与截断审计由用户明确接受。

## What Changes

**移除（全部基数护栏相关）**：

- `DerivedGroupBySpec`：移除 `max_groups` / `max_distinct` / `distinct_on_overflow` 三字段（`specs.py:97-99`）及其在 `fingerprint_parts` / `validate_parallel_mode` / `build_aggregator` 的引用。
- `DedupBySpec`：移除 `max_distinct` / `on_overflow` 两字段（`specs.py:172-173`）；**保留** `on_conflict`（去重本职语义，非护栏）。
- `TwoStageGroupBySpec.build_aggregator`：透传清理（`specs.py:283-285, 291-293`）。
- 运行期 `GroupByAggregator` / `RankedGroupByAggregator` / `DedupByThenAggregator`：移除 `max_groups` / `max_distinct` / `distinct_on_overflow` / `on_overflow` 构造参数与限界逻辑。
- `_BoundedDistinctKeySet`（`derived_outputs.py:315-389`）：整体移除；`count_distinct` 的 distinct 状态退化为普通 `set`。
- `_CountDistinctMetric`：不再依赖 bounded set，简化为无界 set。
- 错误类 `ScalimAggregationKeyLimitExceededError` / `ScalimDistinctKeyLimitExceededError`：移除。
- `DerivedOverflowPolicy` enum（`_output_composition_policies.py`）：移除（**保留** `DedupOnConflictPolicy`，服务于 `on_conflict`）。
- 警告函数 `_warn_derived_guardrails` / `_collect_specs_for_derived_warnings`（`build.py:158-193`）：整体移除；`_append_derived_target_routes:211-212` 调用点移除。
- meta/audit 的 `truncated` 标记与截断审计行（spec r242 相关子项）：随护栏移除而清理。
- YAML DSL `schema_dsl/models/outputs.py`：移除 `max_groups` / `max_distinct` / `distinct_on_overflow` 字段定义（`outputs.py:788-810`）。
- YAML DSL parser `config_parsing/parsers/outputs.py`：移除相关解析与负值校验（`outputs.py:470-477, 494-500`）。
- YAML DSL runtime `output_composition_yaml.py`：移除 `DerivedGroupBySpec` / `DedupBySpec` 构造时的字段透传（`output_composition_yaml.py:409-417` 等）。
- 测试：移除警告测试（`tests/execution/test_output_composition.py:395-426, 628-705`）、overflow 行为测试、parser 负值校验测试（`tests/yaml_dsl/test_yaml_parser_outputs_internal.py:327-337`）。
- 文档：`agentdev/skills/scalim-yaml-dsl/references/upgrades/2026-03-13-derived-outputs-set-aggregations.md` 中护栏相关段落、`syntax-catalog.gen.md`（通过 `just gen-docs` 重生成）。
- 重生成受影响 `.gen.*` 文件（JSON schema、syntax-catalog.gen.md 等，通过 `just gen-docs`，禁止手改）。

**迁移（遵循项目既有 removed YAML kind 模式，参考 `2026-07-20-c999-remove-deprecated-xlsx-file-memory-kinds`）**：

- 对 YAML 中残留的 `max_groups` / `max_distinct` / `distinct_on_overflow` / `dedup_by.on_overflow` 字段，在 parser 层 fail-fast 报错并给出迁移提示（建议：移除该字段，OOM 风险交由系统层兜底）。
- `dedup_by.on_conflict` **保留**，不做迁移提示。

## Capabilities

- `execution-derived-outputs`：移除 r723（`max_groups=0` warn 合约）、r217（distinct/去重护栏合约）；修改 r577（聚合状态资源控制——收窄为「不提供进程内护栏，OOM 由系统层兜底」）；修改 r242（移除截断审计子项，保留指纹与错误审计）。
- `yaml-dsl-write-policy-and-output-extras`：移除 YAML `aggregate.max_groups` / `max_distinct` / `distinct_on_overflow` 字段；新增残留字段 fail-fast + 迁移提示。

## Impact

**Breaking change**：

- Python IR：`DerivedGroupBySpec(max_groups=..., max_distinct=..., distinct_on_overflow=...)` / `DedupBySpec(max_distinct=..., on_overflow=...)` 构造参数移除——传入会报 `TypeError`。
- YAML DSL：`outputs.<name>.aggregate.{max_groups,max_distinct,distinct_on_overflow}` / `dedup_by.on_overflow` 字段移除——残留配置 fail-fast 并提示迁移。
- 日志：`scalim.derived_outputs` 不再发出上述三类 WARNING。
- meta/audit：`truncated` 标记与截断审计行不再产生。
- 指纹：`DerivedGroupBySpec.fingerprint_parts` / `DedupBySpec.fingerprint_parts` 输出变化（移除若干行）——meta sheet 中的聚合指纹值会变，属显式破坏性变更，需在升级说明中标注。
- 错误类型：`ScalimAggregationKeyLimitExceededError` / `ScalimDistinctKeyLimitExceededError` 移除——下游若 try/except 这两个类型会失效。
- 失去的能力：`max_distinct + truncate` 的稳定 top-N 降级路径。高基数场景由 OOM killer 进程级兜底（不可控 victim 选择、整进程被杀）。
