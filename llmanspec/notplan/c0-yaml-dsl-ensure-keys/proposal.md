# Proposal: yaml-dsl-ensure-keys

> 一句话描述: 为聚合（derived）输出增加 `outputs[*].ensure_keys`，在 finalize 后按维度 source 的 mapping keys 补全缺失 group（零绩效/全维度覆盖）。

> **状态（2026-08-10）**：**范围重置为 ensure_keys only**。  
> 原 `c0-yaml-dsl-ensure-keys-defaults` 中的 field-level `default` 已落地，**不在本草案范围**。  
> 目录已由 `c0-yaml-dsl-ensure-keys-defaults` 重命名为本名，避免与已实现的 defaults 混淆。

## 已落地（勿再写入本 change）

| 能力 | 现状（代码锚点） |
|------|------------------|
| relation miss `default` ordered cases | `FieldDefaultCaseIr` + `fields.*.default: [{when: relation_miss, literal\|call_by}]`；LoadRef miss 写回：`execution/executor/operators/load_ref/flow.py` |
| 语法合并 | 旧提案的 `default`/`default_by` 双键 → 现为单一 `default` case 列表；`literal` 与 `call_by` 二选一 |
| builtin | `^defaults/default()`（及兼容 `^defaults/default_of_value_cast()`）；`^defaults/zero_of_value_cast` **fail-fast 提示迁移** |
| 归档 | `2026-04-18-c0-yaml-dsl-ref-miss-default-cases`（冻结于 `freezed_changes.7z.archived`，commit `da948ba8`） |

## Why（仅 ensure_keys）

聚合输出的 row universe 来自 **main_source 上实际出现过的 group_by 键**。事实表缺键时，维度 roster（如全量员工）上的「零绩效」行不会出现。业务侧只能在 loader/后处理里硬补，DSL/Planner 不可见。

`ensure_keys` 把「按维度键空间补全缺失 aggregate group」收成声明式原语，落在 derived output finalize（after_aggregate），不改 main_source 行集。

## What Changes

在 `outputs[*]`（且 MUST 同时声明 `aggregate`）增加可选块：

```yaml
outputs:
  - name: kpi_summary
    aggregate:
      group_by: [employee_id]
      fields:
        order_count: { count: true }
        amount_sum: { sum: amount }
    ensure_keys:
      from: employees          # 维度 source；mapping keys = 期望键集合
      # on: [employee_id]      # 可选；缺省=group_by；若写则必须与 group_by 完全一致
      defaults:                # 可选；补全行字段覆盖
        order_count: 0
        amount_sum: 0
```

### 语义（v1）

- **时机**：`AggregatingRowSink.close` → `aggregator.finalize_rows()` **之后** 补行（after_aggregate）。
- **期望键**：`ensure_keys.from` 指向 `sources.<id>` 的 loader mapping keys。
- **已产出键**：聚合行上 `group_by` 字段组成的 key（与 derived output 的 key_normalization 对齐）。
- **补全行填充优先级**：
  1. `ensure_keys.defaults.<out_field_id>`
  2. producer identity（`count`/`sum`/`count_distinct`/… → `0`；`min`/`max` → `None`）
  3. 其余（含 rank / post）→ `None`
- **顺序**：无 `rank_fields` → 按 group_by 稳定序 merge 插入；有 `rank_fields` → 保持原序，补全行确定性追加末尾（rank 默认 `None`）。
- **预加载**：`from` 源若为 `preload_forever`（YAML `cache_mode` 或 Python `SourceCache.preload_forever()`），MUST 复用 PreloadCache，禁止二次 loader。

### 非目标（v1）

- detail output（无 `aggregate`）上的 ensure_keys
- before_aggregate / 让补全行参与 rank
- FULL OUTER JOIN / 改 main_source row universe
- 再改 field-level `default`（已冻结）

## Capabilities

### New
- `yaml-dsl-ensure-keys` — 见本目录 `specs/yaml-dsl-ensure-keys/spec.md`

### Not in scope
- `yaml-dsl-field-defaults` / `source-relations` miss 缺省 — **已归档落地**，本草案 specs 已删除对应 delta

## Impact

- Schema SSOT：`OutputTargetConfig` + `just gen-yaml-dsl-schema`
- 校验：aggregate-only；`from` 存在；`on`≡`group_by`；`defaults` 键 ∈ 输出字段
- 运行时：建议包装 aggregator 或在 `AggregatingRowSink.close` / `derived_outputs.py` finalize 后补行；诊断走现有 `aggregator.diagnostics()` → router meta/audit
- 文档：示例 demand；禁止手改 `*.gen.*`
