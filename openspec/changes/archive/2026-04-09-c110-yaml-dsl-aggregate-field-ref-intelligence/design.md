## Context

目前 `scalim-yaml-dsl-lsp` 已经对部分“field-id 引用点”提供了 completion/hover/definition（例如 `outputs[*].fields`、表达式内 token、以及部分实体引用）。但在 `outputs[*].aggregate` 结构中仍存在大量 field-id 引用点（`group_by`、各类 metric 的 `{field: ...}` / `{fields: [...]}`、以及 rank 的 `by:`），这些位置缺少同等级的编辑器智能，导致用户无法通过 Ctrl+Space 发现可用字段，也无法快速跳转到字段定义。

另外，aggregate 语义中存在两个“字段命名空间”：

- **输入行字段**：`field_id`（来自 `fields.*`、`main_source.fields.*`、`sources.*.fields.*`）
- **聚合输出字段**：`out_field_id`（即 `outputs[*].aggregate.fields` mapping 的 key，例如 `sum_order_amount`）

在 rank/派生字段相关配置中，很多引用点允许引用 `group_by` 或 `aggregate.fields` 的任意字段，因此同一 token 既可能表示 `out_field_id` 也可能表示 `field_id`。LSP 需要支持多候选 definition，并在 completion 中明确标注与排序。

约束与背景：
- LSP 必须支持 Ctrl+Space 手动触发；自动弹出应基于有限 triggerCharacters（避免每字符触发造成卡顿）。
- 不引入每次 didChange 的全量重算；复用已有 debounce 与缓存（effective_view/entity_index 等）。
- 只扩展编辑器能力，不改变 runtime DSL 行为。

## Goals / Non-Goals

**Goals:**
- 在 `outputs[*].aggregate` 中所有“field-id scalar / list item”位置支持：
  - completion：列出 field ids（并尽可能带简要 detail）
  - definition：跳转到字段声明（跨 imports 展开仍可定位）
  - hover：展示字段摘要（如已存在字段卡片样式）
- 覆盖典型结构：
  - `aggregate.group_by: [field_id, ...]`（含复合 key：`group_by: [[a, b], c]`）
  - `aggregate.fields.<out_field_id>.*.field: field_id`
  - `aggregate.fields.<out_field_id>.*.fields: [field_id, ...]`
  - `aggregate.fields.<out_field_id>.(row_number|rank|dense_rank).by: <token>`
  - `aggregate.fields.<out_field_id>.(row_number|rank|dense_rank).partition_by[*]: <token>`
  - `aggregate.fields.<out_field_id>.(row_number|rank|dense_rank).order_by[*]: <token>`
  - `aggregate.fields.<out_field_id>.score_by_rank.rank_field: <out_field_id>`
- 完整回归测试：cursor extraction + LSP server completion/definition。

**Non-Goals:**
- 不在本变更中扩展 runtime aggregation 支持范围（仅 editor/LSP）。
- 不在本变更中引入“按输入字母实时过滤/排序”的复杂评分模型（保持现有简单排序策略）。

## Decisions

1) **将 aggregate 内的 field 引用视为“output field reference”的扩展**
- 复用现有 output-field completion/definition 的候选来源（effective_view 的可见 fields），避免引入新的索引体系。
- 在 cursor extraction 层新增/扩展路径匹配，识别 aggregate 对应的 YAML 位置，并产出与现有 completion handler 可兼容的 `kind`。

2) **completion 的触发策略**
- 保持 Ctrl+Space 可触发（关键），并额外在 `/`、`@` 等已有 triggerCharacters 的基础上，不新增“字母触发”以规避性能回归。
- 对于空值与空 list item（`group_by:\n  - <cursor>`、`fields:\n  - <cursor>`）在光标抽取中提供稳定的 value_range，使 completion handler 能工作。

3) **completion 的候选来源与排序策略（含“推断候选”）**
- completion 在 rank/派生字段引用点支持“多命名空间候选”，并用 `detail` 明确标注来源：
  1) `aggregate.fields` 的 `out_field_id`（最高优先）
  2) `group_by` 引用的 `field_id`（次优先）
  3) 全局可见 `field_id`（低优先；用于方便用户跳转/重构）
- 对语义上更严格的位置（例如 `partition_by` 必须为 group_by 子集），仍允许显示全局字段作为低优先候选，但必须标注为“fallback / 可能不合法”，避免误导。

4) **definition/hover 的定位策略（多 locations + 稳定排序）**
- token 命中 `out_field_id` 时：definition 第一候选必须跳转到 `outputs[*].aggregate.fields.<out_field_id>` 的 key 位置。
- 同时命中全局 `field_id` 时：追加其 field 定义 locations 作为后续候选（稳定排序+去重）。
- token 仅命中全局 `field_id` 时：按现有 field 定义解析返回。
- 对 `fields: [a, b]` / `group_by: [[a, b], c]` / `order_by: [[x, y], z]` 的内层 list item，分别在 a/b/x/y token 上定位。

## Risks / Trade-offs

- [覆盖不全] aggregate 结构存在多种 metric 形态 → 用测试驱动枚举真实 demo（`ecommerce_report.yaml`）出现的结构，并补齐路径匹配。
- [性能] 增加路径检测可能提升 cursor extraction 成本 → 保持纯文本/轻量 YAML token 定位（不引入额外 parse），并复用已有缓存。
- [歧义] `by:` 等通用 key 可能在其他位置出现 → extraction 必须依赖完整路径上下文（outputs[*].aggregate.fields.*.rank.*.by），避免误命中。
- [候选噪声] completion 列出全局 field_id 可能带来噪声 → 通过严格的优先级与清晰标注降低误用；定义/跳转能力仍为主要价值点。
