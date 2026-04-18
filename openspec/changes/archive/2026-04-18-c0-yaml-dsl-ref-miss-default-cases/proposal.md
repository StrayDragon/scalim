## Why

下游报表类需求中，大量指标字段来自 relation lookup（典型：客服/员工维度做 KPI 汇总，指标来自多个事实/汇总表）。当前语义是 **relation miss 一律返回 `None`**，业务侧只能用 `_safe_*: int(x or 0)`、`or ""` 等派生字段兜底，带来：

- YAML 中间字段膨胀（维护成本高，新增指标必新增兜底字段）
- per-row `compute` 解释执行开销（本可在 ref 写回阶段一次性处理）
- 逻辑分散在 Python workaround 与 YAML 之间（编译器/Planner 不可见，难做校验/诊断）

以 `/home/l8ng/CoProjects/ET/.../d70_summary_ranking.demand.yaml` 为代表，`create_order_count/year_user_count/...` 等 ref 字段在 miss 时变 `None`，被迫引入一大段 `_safe_*` 字段；其根因是“ref miss 缺省值”不可声明。

## What Changes

本变更提供一个 **最小交付** 的 DSL 原语：在 **ref 字段**（带 `relation:` 的 source 字段）上声明 “当 relation miss 时的默认值”。

### 1) 新增：ref 字段 `default`（ordered cases）

配置位置：`main_source.fields.*` 与 `sources.*.fields.*` 的 **source field** 配置中，且该字段 MUST 声明 `relation:`。

语法（v1）：

```yaml
sources:
  create_metrics:
    fields:
      create_order_count:
        relation: paid_to_create
        value_cast: int
        default:
          - when: relation_miss
            literal: 0
```

- `default` 为列表（按顺序 first-match）
- 每个 case MUST 包含：
  - `when: relation_miss`（v1 仅支持该枚举）
  - 且在 `literal` 与 `call_by` 中二选一（oneOf）
    - `literal`: YAML 标量（`int|float|str|bool|null`）
    - `call_by`: 可调用引用字符串，语法与现有 `call_by` 一致，且 MUST 显式包含 `()`（例如 `^defaults/zero_of_value_cast()` / `myapp.defaults:fn(status=employee_status)`）

语义（v1）：
- **仅当 relation lookup miss** 时应用 default（包括：外键为 `None`、cast/normalize 失败、任一步 miss、最终 key 未命中）
- hit 行不受影响
- 不处理 “hit 但值为空/提取结果为空（hit-but-null）” 的场景（留待后续扩展新的 `when`）

### 2) 内置：`^defaults/zero_of_value_cast()`（可选）

提供一个 builtin callable（通过 builtin vocabulary 暴露），用于按字段 `value_cast` 推导缺省值：
- `int → 0`
- `decimal → Decimal(0)`（若该 cast 存在）
- `str → ""`
- `bool → False`
- 其他/未知 → `None`

业务可不依赖内置，直接使用 `literal` 或 allowlisted 的 `call_by`。

### 3) 校验与诊断（最小集合）

- `default` 仅允许出现在带 `relation:` 的字段上；否则校验失败（避免语义歧义）
- `default` cases 必须满足 oneOf（`literal`/`call_by`）与 `when` 枚举；未知 `when` 直接 fail-fast
- `call_by` 必须通过 allowlist 校验（builtin `^...` 不要求 allowlist）
- `default[*].call_by` MUST 仅依赖 “pre-ref 可用字段”（main_source 非 ref 字段 + 仅依赖这些字段的 derived 字段）；一旦依赖到 ref 字段（或依赖 ref 的派生字段），编译期/校验 MUST fail-fast（避免隐式 None 吞错）
- 运行期 SHOULD 输出 ref miss 命中 default 的统计诊断（按 field_id 聚合），用于发现数据缺失与配置效果

## Capabilities

### New Capabilities
- `yaml-dsl-ref-miss-default-cases`: 为 ref 字段提供 ordered-cases 的 relation miss 默认值声明（`default: [{when, literal|call_by}]`），并提供编译期校验与运行期诊断统计。

### Modified Capabilities
- `source-relations`: 更新“关联缺失（relation miss）”语义：默认仍返回 `None`；但当 ref 字段声明了 `default` 且命中 `relation_miss` case 时，系统 MUST 写回该默认值（保持 left join 的“行不丢失”语义不变）。

## Impact

- YAML authoring surface：`main_source.fields.*` / `sources.*.fields.*` 的 ref 字段新增 `default` 配置（cases 列表）
- Schema/validator：更新 schema_dsl dataclasses + 严格 validator；实现 oneOf/枚举/位置约束/allowlist 校验；随后通过 `just gen-yaml-dsl-schema` 刷新 `src/scalim/dsl/yaml_dsl/schema/demand.gen.json`（生成物禁止手改）
- Runtime execution：`LoadRef` miss 写回路径支持 default；并增加 miss/default 命中统计诊断
- Downstream 代码影响：可删除大量 `_safe_*` 中间字段；比率类字段可进一步迁移到 aggregate/post 计算（不在本变更范围内）
- Editor/LSP 影响：上述依赖校验与 callable 引用错误 SHOULD 在编辑期 diagnostics 中可见（复用同一 validator 语义）
