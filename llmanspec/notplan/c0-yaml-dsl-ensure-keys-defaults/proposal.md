> 一句话描述: 为 YAML DSL 引入两个声明式原语——字段级 relation miss 缺省（`default`）与聚合输出的维度键空间补全（`outputs[*].ensure_keys`）。

> **状态（2026-08-11）**：**部分转正** —— `default`（field-defaults）已由 `2026-04-18-c0-yaml-dsl-ref-miss-default-cases`（冻结于 `freezed_changes.7z.archived`，commit `da948ba8`）落地实现；`ensure_keys` 仍未实现，本提案仅剩该部分有效。
> 语法偏差说明：实现将 `default`/`default_by` 合并为 `default` ordered cases（`when: relation_miss` + `literal`/`call_by` 二选一）；内置词汇表 `^defaults/zero_of_value_cast` 改名 `^defaults/default()`（旧名出现即 fail-fast 提示迁移）。

## Why

当前 Scalim YAML DSL 在“缺失数据”场景下缺少声明式原语：

- **Row universe 固定为 main_source**：当事实表缺少某些维度键时，输出天然缺行（典型的“零绩效员工也要出现/零销量门店也要出现”）。
- **Relation miss 固定返回 `None`**：用户只能用 `_safe_*` 派生字段或在 loader 里硬编码补零，导致逻辑分散在 Python 与 YAML 之间，编译器/Planner 不可见，难以校验、诊断与复用。

这类问题在报表/对账/维度完整性场景中高频出现，属于通用的数据流声明需求；将其内建到 DSL 可以显著降低业务侧样板代码与运行期开销，并提升诊断与治理能力。

## What Changes

本变更引入两个正交原语，分别覆盖“字段级 miss 兜底”和“聚合后缺行补全”：

### 1) Field defaults: `default` / `default_by`（只处理 relation miss）

- **配置位置**：`main_source.fields.*` 与 `sources.*.fields.*` 的 source 字段配置中（ref 字段）
- **新增字段**：
  - `default`: YAML 字面量
  - `default_by`: 受控 callable 引用（语法与 `call_by` 一致，支持 `^<id>` builtin 引用与 allowlist 约束）
- **内置 vocabulary（v1）**：
  - `default_by: ^defaults/zero_of_value_cast`：按字段 `value_cast` 推导“零/空”缺省值（int→0、decimal→Decimal(0)、str→""、bool→False，其它→None）
  - `default_by: ^defaults/null`：显式返回 `None`（用于可读性/占位；语义等价于不写 default）
- **适用条件**：仅当该字段发生 **relation lookup miss** 时生效（不改变 hit 行）
  - miss 覆盖范围包括：外键为 `None` / 无法归一化、任一步 miss、最终 step miss
- **边界澄清（v1）**：
  - default 不用于“hit 但 extract 路径缺失/字段值为 None”的场景（那是数据内容缺失，不是 relation miss）
  - `value_cast`/value transform 在 default 选值后仍会执行（即：先决定 hit/miss → 再对返回值做类型转换），以保持字段类型语义一致
  - `default_by` 可引用行内字段，但仅允许依赖 **LoadRef 之前可用** 的字段（main_source non-ref + pre-ref derived），否则 fail-fast（避免“默认值依赖尚未计算的字段”导致隐式 None）

示例（relation miss 时返回 0/或按状态计算默认值）：

```yaml
sources:
  rating_stats:
    loader: myapp.loaders:load_ratings
    key: employee_id
    fields:
      total_reviews:
        relation: metrics_to_ratings
        value_cast: int
        default: 0
      custom_score:
        relation: metrics_to_ratings
        value_cast: int
        default_by: myapp.defaults:score_for_status(status)
```

### 2) Ensure keys: `outputs[*].ensure_keys`（只对 aggregate/derived output 生效）

- **配置位置**：`outputs[*].ensure_keys`（且该 output MUST 声明 `aggregate`）
- **语义**：在 derived output finalize 阶段补全缺失的 group-by 键（after-aggregate，不改变 main_source 行集）
- **期望键集合来源**：`ensure_keys.from` 引用一个维度 source，系统将该 source loader 结果 mapping 的 keys 视为“期望键集合”
  - 推荐该 source 具有稳定、低成本、幂等的 loader；若同时用于 lookup，通常建议 `cache_mode: preload_forever`
  - **性能契约（v1）**：当维度源启用 `cache_mode: preload_forever` 时，ensure_keys MUST 复用 preload cache（避免同一 source 被重复加载）
- **配置形态（v1）**：
  - `from`: 必填，source_id
  - `on`: 可选；缺省等于 `aggregate.group_by`；若显式提供，必须与 `aggregate.group_by` 完全一致（避免多输出歧义并保留未来扩展空间）
  - `defaults`: 可选；对补全行的字段级默认值覆盖（key 为 out_field_id）
- **补全行的字段填充值优先级**：
  1) `ensure_keys.defaults.<out_field_id>` 显式覆盖
  2) 聚合指标 identity 推导（count/sum/count_distinct→0；min/max→None）
  3) 其余字段为 None（rank 字段、score_by_rank 等保持 None，除非 defaults 覆盖）

示例（按维度 roster 补全缺失 group）：

```yaml
outputs:
  - name: kpi_summary
    aggregate:
      group_by: [employee_id]
      fields:
        order_count: { count: true }
        amount_sum: { sum: amount }
    ensure_keys:
      from: employees
      defaults:
        order_count: 0
        amount_sum: 0
```

> 备注（语法调整）：RFC 将 `ensure_keys` 放在 `main_source` 下，但其语义严格依赖 output 的 aggregate/group_by 与字段集合；为避免多输出歧义并降低维护成本，本变更将 `ensure_keys` 设计为 output-level 配置（仅对声明了 `aggregate` 的 output 生效）。如需“对所有输出复用同一补全策略”，后续可在不破坏语义的前提下增加 sugar（例如 demand-level defaults + per-output override）。
>
> 备注（范围边界）：`ensure_keys` v1 为 **after_aggregate** 且仅支持 derived outputs；“before_aggregate”/detail output 的含义与取舍见 `design.md` 的 Clarifications。

## Capabilities

### New Capabilities
- `yaml-dsl-field-defaults`: 为 source 字段提供 relation miss 的 `default` / `default_by` 缺省值原语，并提供编译期校验与运行期诊断统计。
- `yaml-dsl-ensure-keys`: 为聚合输出提供维度键空间补全（after-aggregate），支持 identity 推导、显式 defaults 覆盖与运行期补全统计诊断。

### Modified Capabilities
- `source-relations`: 更新关联缺失语义：relation miss 的字段值默认仍为 `None`，但当字段声明了 `default/default_by` 时，miss MUST 按声明返回缺省值（保持 left join 的“行不丢失”语义不变）。

## Impact

- YAML authoring surface：
  - `main_source.fields.*` / `sources.*.fields.*` 新增 `default` / `default_by`（互斥）
  - `outputs[*]`（且仅当存在 `aggregate`）新增 `ensure_keys` 配置块（`from/on/defaults`）
- 解析/校验：
  - schema_dsl dataclasses 与严格 validator 更新（互斥校验、builtin 策略存在性、allowlist 校验、类型兼容诊断等）
- 运行时执行：
  - `LoadRef` 写回缺失值路径支持字段级 default（避免业务侧 `_safe_*`）
  - derived outputs finalize 阶段支持补全缺失 group，并输出补全统计诊断
- 文档与治理：
  - 更新/新增 OpenSpec specs（本 change 的 `specs/**`）
  - 代码实现完成后需通过 `just gen-yaml-dsl-schema` 刷新 `src/scalim/dsl/yaml_dsl/schema/demand.gen.json`（生成物禁止手改）
