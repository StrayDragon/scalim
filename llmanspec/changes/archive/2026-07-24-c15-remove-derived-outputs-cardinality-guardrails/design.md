# Design: 移除派生输出基数护栏

## 背景

派生输出（derived outputs）的基数护栏体系由 `max_groups` / `max_distinct` / `distinct_on_overflow` / `dedup_by.on_overflow` 四个配置 + `DerivedOverflowPolicy` enum + `_BoundedDistinctKeySet` 限界类 + 2 个错误类 + build 阶段警告构成。本变更完整移除该体系，只保留与去重本职语义耦合的 `dedup_by.on_conflict` / `DedupOnConflictPolicy`。

## 关键决策与权衡

### 决策 1：完整移除 vs 仅移除 fail-only 部分

**选项 A（仅移除 fail-only）**：保留 `max_distinct` + `on_overflow: truncate` 降级。
**选项 B（完整移除，本次采纳）**：移除全部护栏。

选择 B 的理由：

- `max_groups`（纯 fail）无任何恢复路径，价值为零，必移除。
- `max_distinct: truncate` 虽是「能恢复」的 graceful degradation（`_BoundedDistinctKeySet.add` 驱逐最差键、保留最优 N 个），但其 top-N 近似语义对当前业务无意义；保留它意味着继续维护 `_BoundedDistinctKeySet` 整套限界逻辑、`DerivedOverflowPolicy` enum、截断审计、对应测试与文档，**维护成本与使用价值严重不匹配**。
- OOM 风险由系统层 OOM killer 进程级兜底，用户明确接受此代价。
- 完整移除后 spec / 运行期 / YAML schema / parser / runtime bridge 多处简化，净维护面积下降明显。

**被牺牲的能力（需在升级说明显式标注）**：

- `truncate` 的稳定 top-N 降级路径——高基数场景不再有受控降级，只剩进程被 OOM killer 杀掉。
- meta/audit 的 `truncated` 标记与截断审计行（spec r242 子项）——对拍/审计会少一类信号。

### 决策 2：`on_conflict` / `DedupOnConflictPolicy` 必须保留

`_output_composition_policies.py` 有两个独立 enum：

| Enum | Values | 性质 |
|---|---|---|
| `DerivedOverflowPolicy` | `error` / `truncate` | 基数护栏（本变更移除） |
| `DedupOnConflictPolicy` | `error` / `first` / `last` | 去重本职语义（**保留**） |

`DedupBySpec.on_conflict` 决定同一 dedup key 命中多行时选哪行，是 `dedup_by` 功能的核心（spec r160 强制要求：「系统 MUST 对 `dedup_by` 在同一 key 命中多行时的冲突策略提供显式配置」）。它不是护栏，移除它等于废掉 `dedup_by`。本变更**不动** `on_conflict` / `DedupOnConflictPolicy`。

> 注意命名易混淆：`distinct_on_overflow` / `dedup_by.on_overflow` 是护栏（移除）；`dedup_by.on_conflict` 是去重语义（保留）。三者不可混为一谈。

### 决策 3：迁移策略（YAML 残留字段）

遵循项目既有 removed YAML kind 的 fail-fast + 迁移提示模式（参考 `2026-07-20-c999-remove-deprecated-xlsx-file-memory-kinds`）：

- YAML 中出现 `max_groups` / `max_distinct` / `distinct_on_overflow` / `dedup_by.on_overflow` → parser 报错，提示「字段已移除，请删除；OOM 风险由系统层兜底」。
- `dedup_by.on_conflict` 不触发迁移提示。

理由：硬删 + fail-fast 比静默忽略更安全，能立即暴露用户配置漂移；与项目 `xlsx_file`/`xlsx_memory` 移除的既有做法一致。

### 决策 4：`count_distinct` 状态承载

移除 `_BoundedDistinctKeySet` 后，`_CountDistinctMetric` 的 distinct 集合退化为普通 `set`：

- `_CountDistinctMetric.__init__`：`self._distinct = set()`（替代 `_BoundedDistinctKeySet(...)`）。
- `_CountDistinctMetric.accumulate`：`self._distinct.add(key)`（忽略返回值）。
- `_CountDistinctMetric.finalize`：`return len(self._distinct)`。
- `truncated` / `key_count` 属性：移除 `truncated`；`key_count` 可保留为 `len(self._distinct)` 供内部使用，或直接内联。

NULL 语义（spec r137：任一组成字段为 None 则忽略该行）保持不变。

## 影响面清单（实现顺序参考）

1. 运行期核心：`derived_outputs.py`（`_BoundedDistinctKeySet`、3 个 aggregator 构造签名、`_CountDistinctMetric`、错误类）。
2. IR 层：`specs.py`（3 个 spec dataclass 字段 + `fingerprint_parts` + `validate_parallel_mode` + `build_aggregator`）。
3. policy enum：`_output_composition_policies.py`（移除 `DerivedOverflowPolicy`）。
4. build 警告：`build.py`（`_warn_derived_guardrails` / `_collect_specs_for_derived_warnings` + 调用点）。
5. YAML schema：`schema_dsl/models/outputs.py`（字段定义）。
6. YAML parser：`config_parsing/parsers/outputs.py`（解析 + 校验 + 迁移 fail-fast）。
7. YAML runtime bridge：`runtime/output_composition_yaml.py`（spec 构造透传）。
8. 测试：删除护栏相关测试，更新指纹快照。
9. 文档：升级说明 + `just gen-docs` 重生成 `.gen.*`。
10. 校验：`just qa` + `llman sdd validate <id> --strict --no-interactive`。

## 不在本变更范围

- `dedup_by.on_conflict` / `DedupOnConflictPolicy`：保留。
- `count_distinct` / `count_true_gte` / `two_stage_group_by` 等聚合原语本身：保留。
- `adaptive` 并发一致性边界（spec r683 / r181）：保留。
- 聚合指纹机制（spec r242 主体）：保留，仅移除 `truncated` 相关子项。
